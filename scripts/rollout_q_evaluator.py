#!/usr/bin/env python
"""R7, the EVALUATOR read: can G0's rollout labels teach the leaf critic to
rank successors, on positions it never saw?

Plan amendment box 4 item 1 (§6's own branch): "B2 trains the evaluator on
rollout labels first -- the G0 rows are the dataset". Every read since says
the evaluator binds: the critic-leaf operator captures 17% of the depth-1
ceiling, every root rule is within noise of greedy at the critic level, and
the v' target's bias is the critic's own (+0.034 outcome units above the
rollout root value) far more than the peek's (box 5). This is the cheap first
look before anything is built for the fleet.

WHAT IT DOES. For every G0 position, every (our row, their column) cell --
the FULL legal matrix G0 rolled out, 256 rollouts per cell -- is expanded
into S chance leaves (`SearchNode.expand`, our seat's view only). The target
is the cell's rollout mean; the prediction is the mean over the cell's S
leaves of the critic's value (terminal leaves take their outcome, exactly as
`native.solve` does). That is the quantity the operator consumes, so the loss
trains what search reads. Only the CRITIC is fine-tuned (a separate network
from the actor in these checkpoints), so the policy, the priors and the greedy
action are untouched: every comparison below is matched on the policy.

CROSS-VALIDATION BY POSITION (the §27.1 lesson: split at the level the
predictor is constant within). K folds; each committee member's critic is
fine-tuned on the other folds' cells and predicts the held-out fold's. Every
read is OUT OF FOLD.

FIXED BEFORE IT RUNS (no selection on the held-out folds): Adam, lr 1e-4,
4 epochs, 128 cells a batch, S = 4 leaves a cell, 5 folds, seed 20260923.
The per-epoch held-out loss is REPORTED, never used to pick an epoch.

READS (out of fold, all 500 positions):
  PRIMARY  the per-position Spearman of the critic's cell values against the
           rollout cell values -- the committee's original critic vs the
           fine-tuned one, paired by position (G0's `spearman_critic` is the
           same statistic at S = 2 over all columns: +0.476).
  and      the operator at the sweep's cell (k 4, S 2, tau 0.05, the sweep's
           decision keys) with the fine-tuned critic at its leaves: gain over
           greedy on G0's own rollout oracle at gates {0, 0.01, 0.02, 0.05},
           override beside every number (the baseline arm reproduces the
           sweep's cell -- printed as a provenance check).
  also     cell MSE and bias against the rollout means; the root value's bias
           against `v_root_rollout`; in-sample fit on the training folds (the
           positive control: if it cannot fit what it sees, nothing is read).

Rule 6: 500 positions is a small dataset for a 1.8M-parameter critic; a null
here says the SIZE is wrong, not that rollout labels cannot teach the leaf. A
positive out-of-fold read is the informative branch.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import json
import math
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

EVAL_VERSION = "rollout_q_evaluator/1"
GATES = (0.0, 0.01, 0.02, 0.05)
SWEEP_KEY_OFFSET = 35          # (4, 2, 0.05)'s index in the sweep's grid + 1 (scripts/rollout_q_belief.py)


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    def rank(v):
        order = np.argsort(v, kind="stable")
        r = np.empty(len(v)); r[order] = np.arange(len(v), dtype=float)
        # average ties
        vs = v[order]
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and vs[j + 1] == vs[i]:
                j += 1
            if j > i:
                r[order[i:j + 1]] = (i + j) / 2.0
            i = j + 1
        return r
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(rank(np.asarray(x, float)), rank(np.asarray(y, float)))[0, 1])


def ms(xs) -> tuple[float, float]:
    x = np.asarray([v for v in xs if v == v], float)
    if len(x) < 2:
        return float("nan"), float("nan")
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True, help="G0's rows (read only)")
    ap.add_argument("--out", required=True, help="summary JSON; a .md beside it and per-position rows as .rows.jsonl")
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--leaf-samples", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-cells", type=int, default=128)
    ap.add_argument("--limit", type=int, default=0, help="first N positions (a smoke)")
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--torch-threads", type=int, default=2)
    args = ap.parse_args()
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)
    import pkmn_gen1
    from rl.envs.engine_tables import build_tables
    from rl.search import native
    import rollout_q as rq

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    try:
        qos = "background" if os.getpriority(4, 0) != 0 else "normal"
    except OSError:
        qos = "unknown"
    rng = np.random.default_rng(args.seed)
    committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
    tables, fp = build_tables()
    rows = rq.load_rows(pathlib.Path(args.rows))
    if args.limit:
        rows = rows[: args.limit]
    S = args.leaf_samples
    t0 = time.time()

    # ---- 1. render every cell's S leaves (our seat's view) ----
    pos = []
    for r in rows:
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        rows_a, cols_b = r["rows"], r["cols"]
        cells = [(a, b, S) for a in rows_a for b in cols_b]
        e = node.expand(tables, "p1", cells, native.seed_base(int(r["pid"]) * 1_000_033 + 17, 0), both_views=False)
        n = int(e["n"])
        cell = np.asarray(e["cell"])
        if n != len(cells) * S or not np.array_equal(cell, np.repeat(np.arange(len(cells)), S)):
            sys.exit(f"pid {r['pid']}: leaves are not {S} per cell in cell order -- the reshape below would misalign")
        obs = np.asarray(e["obs"], np.float32).reshape(len(cells), S, -1)
        term = np.asarray(e["terminal"]).reshape(len(cells), S)
        tval = np.where(term == 2, 0.0, term.astype(np.float64))          # native.solve's terminal rule
        q = (0.5 * (np.asarray(r["q_half_a"], float) + np.asarray(r["q_half_b"], float))).reshape(-1)   # row-major = `cells`
        pos.append({"pid": int(r["pid"]), "bucket": int(r["bucket"]), "obs": obs, "live": term == 0, "tval": tval, "q": q,
                    "root_obs": np.asarray(node.obs(tables, "p1"), np.float32), "v_root_rollout": float(r["v_root_rollout"]),
                    "node": node, "row": r})
    n_cells = sum(len(p["q"]) for p in pos)
    obs_dim = pos[0]["obs"].shape[-1]
    print(f"[evaluator] rendered {len(pos)} positions, {n_cells} cells x {S} leaves, obs {obs_dim}, {time.time() - t0:.0f} s", flush=True)

    def cell_pred(critics, p) -> np.ndarray:
        """Mean over members of the cell prediction (mean over the cell's leaves; terminals take their outcome)."""
        x = torch.as_tensor(p["obs"].reshape(-1, obs_dim))
        outs = []
        with torch.no_grad():
            for c in critics:
                v = c(x).squeeze(-1).numpy().astype(np.float64).reshape(p["live"].shape)
                outs.append(np.where(p["live"], v, p["tval"]).mean(axis=1))
        return np.mean(outs, axis=0)

    def root_value(critics, p) -> float:
        x = torch.as_tensor(p["root_obs"][None])
        with torch.no_grad():
            return float(np.mean([float(c(x).squeeze(-1)[0]) for c in critics]))

    base_critics = [m.critic for m in committee.members]
    for c in base_critics:
        c.eval()
    base_pred = [cell_pred(base_critics, p) for p in pos]
    base_root = [root_value(base_critics, p) for p in pos]
    print(f"[evaluator] baseline predictions done, {time.time() - t0:.0f} s", flush=True)

    # ---- 2. K-fold fine-tune, by position ----
    order = rng.permutation(len(pos))
    fold_of = np.empty(len(pos), int)
    for f in range(args.folds):
        fold_of[order[f::args.folds]] = f
    oof_pred = [None] * len(pos)
    oof_root = [None] * len(pos)
    fold_critics: dict[int, list] = {}
    curves = []
    in_sample = []

    def stack(idx):
        X = np.concatenate([pos[i]["obs"] for i in idx]); L = np.concatenate([pos[i]["live"] for i in idx])
        T = np.concatenate([pos[i]["tval"] for i in idx]); Y = np.concatenate([pos[i]["q"] for i in idx])
        return (torch.as_tensor(X), torch.as_tensor(L), torch.as_tensor(T, dtype=torch.float32), torch.as_tensor(Y, dtype=torch.float32))

    def cell_loss(c, X, L, T, Y) -> torch.Tensor:
        v = c(X.reshape(-1, obs_dim)).squeeze(-1).reshape(L.shape)
        pred = torch.where(L, v, T).mean(dim=1)
        return ((pred - Y) ** 2).mean()

    for f in range(args.folds):
        tr = [i for i in range(len(pos)) if fold_of[i] != f]
        te = [i for i in range(len(pos)) if fold_of[i] == f]
        Xtr, Ltr, Ttr, Ytr = stack(tr)
        Xte, Lte, Tte, Yte = stack(te)
        tuned = []
        for mi, base in enumerate(base_critics):
            c = copy.deepcopy(base)
            c.train()
            opt = torch.optim.Adam(c.parameters(), lr=args.lr)
            g = torch.Generator().manual_seed(args.seed * 31 + f * 7 + mi)
            curve = {"fold": f, "member": mi, "train": [], "heldout": [], "heldout_spearman": []}

            def snap():
                # Reported per epoch, NEVER used to pick one: the fixed final epoch is the read.
                with torch.no_grad():
                    c.eval()
                    curve["train"].append(float(cell_loss(c, Xtr, Ltr, Ttr, Ytr))); curve["heldout"].append(float(cell_loss(c, Xte, Lte, Tte, Yte)))
                    curve["heldout_spearman"].append(float(np.nanmean([spearman(cell_pred([c], pos[i]), pos[i]["q"]) for i in te])))
                    c.train()
            snap()
            for ep in range(args.epochs):
                perm = torch.randperm(len(Ytr), generator=g)
                for b in range(0, len(perm), args.batch_cells):
                    idx = perm[b: b + args.batch_cells]
                    loss = cell_loss(c, Xtr[idx], Ltr[idx], Ttr[idx], Ytr[idx])
                    opt.zero_grad(); loss.backward(); opt.step()
                snap()
            c.eval()
            tuned.append(c)
            curves.append(curve)
            print(f"[evaluator] fold {f} member {mi}: cell MSE train {curve['train'][0]:.4f} -> {curve['train'][-1]:.4f}, "
                  f"held-out {curve['heldout'][0]:.4f} -> {curve['heldout'][-1]:.4f}, held-out Spearman (this member) "
                  f"{' '.join(f'{x:+.3f}' for x in curve['heldout_spearman'])} ({time.time() - t0:.0f} s)", flush=True)
        fold_critics[f] = tuned
        for i in te:
            oof_pred[i] = cell_pred(tuned, pos[i]); oof_root[i] = root_value(tuned, pos[i])
        for i in tr[:: max(1, len(tr) // 100)]:     # the positive control, on a sample of the training positions
            in_sample.append((spearman(base_pred[i], pos[i]["q"]), spearman(cell_pred(tuned, pos[i]), pos[i]["q"])))

    # ---- 3. the operator with the fine-tuned leaf, at the sweep's cell ----
    class Leaf:
        def __init__(self, critics):
            self.critics = critics

        def __call__(self, e):
            x = torch.as_tensor(np.ascontiguousarray(e["obs"]), dtype=torch.float32)
            with torch.no_grad():
                return torch.stack([c(x).squeeze(-1) for c in self.critics]).mean(dim=0).numpy().astype(np.float64)

    per = []
    for i, p in enumerate(pos):
        r = p["row"]; node = p["node"]
        mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
        pi1 = np.asarray(r["pi1"]); pi2 = np.asarray(r["pi2"])
        prior1 = np.where(mask1, pi1, 0.0); prior2 = np.where(mask2, pi2, 0.0)
        q_col = pi2[r["cols"]] / pi2[r["cols"]].sum()
        qbar = (0.5 * (np.asarray(r["q_half_a"]) + np.asarray(r["q_half_b"]))) @ q_col
        row_of = {a: j for j, a in enumerate(r["rows"])}
        g = int(r["a_greedy"])
        key = p["pid"] * 100_003 + SWEEP_KEY_OFFSET
        out = {"pid": p["pid"], "bucket": p["bucket"], "fold": int(fold_of[i]),
               "spearman_base": spearman(base_pred[i], p["q"]), "spearman_tuned": spearman(oof_pred[i], p["q"]),
               "mse_base": float(np.mean((base_pred[i] - p["q"]) ** 2)), "mse_tuned": float(np.mean((oof_pred[i] - p["q"]) ** 2)),
               "bias_base": float(np.mean(base_pred[i] - p["q"])), "bias_tuned": float(np.mean(oof_pred[i] - p["q"])),
               "root_base": base_root[i], "root_tuned": oof_root[i], "v_root_rollout": p["v_root_rollout"]}
        for name, critics in (("base", base_critics), ("tuned", fold_critics[int(fold_of[i])])):
            res = native.solve([native.World(node)], tables, "p1", prior1, prior2, Leaf(critics), key, cols_k=4, chance_s=2, tau=0.05)
            a, margin = int(res["action"]), float(res["counters"]["search/margin"])
            for gate in GATES:
                act = a if (a != g and margin >= gate) else g
                out[f"gain_{name}_{gate}"] = float(qbar[row_of[act]] - qbar[row_of[g]])
                out[f"override_{name}_{gate}"] = int(act != g)
        per.append(out)

    # ---- 4. summary ----
    def block(sel):
        b = {"positions": len(sel)}
        sb, st = ms([s["spearman_base"] for s in sel]), ms([s["spearman_tuned"] for s in sel])
        sd = ms([s["spearman_tuned"] - s["spearman_base"] for s in sel if s["spearman_tuned"] == s["spearman_tuned"] and s["spearman_base"] == s["spearman_base"]])
        b["spearman"] = {"base": sb, "tuned": st, "paired_delta": sd}
        b["cell_mse"] = {"base": ms([s["mse_base"] for s in sel]), "tuned": ms([s["mse_tuned"] for s in sel])}
        b["cell_bias"] = {"base": ms([s["bias_base"] for s in sel]), "tuned": ms([s["bias_tuned"] for s in sel])}
        b["root_bias"] = {"base": ms([s["root_base"] - s["v_root_rollout"] for s in sel]), "tuned": ms([s["root_tuned"] - s["v_root_rollout"] for s in sel])}
        b["operator"] = {}
        for gate in GATES:
            row = {}
            for name in ("base", "tuned"):
                m_, se_ = ms([s[f"gain_{name}_{gate}"] for s in sel])
                row[name] = {"override": float(np.mean([s[f"override_{name}_{gate}"] for s in sel])),
                             "gain_win_rate": m_ / 2, "gain_se_win_rate": se_ / 2}
            md, sed = ms([s[f"gain_tuned_{gate}"] - s[f"gain_base_{gate}"] for s in sel])
            row["paired_delta_win_rate"] = (md / 2, sed / 2)
            b["operator"][str(gate)] = row
        return b

    summary = {"pooled": block(per), "by_bucket": {}}
    for bi, (lo, hi) in enumerate(rq.BUCKETS):
        sel = [s for s in per if s["bucket"] == bi]
        if sel:
            summary["by_bucket"][f"{lo}-{'+' if hi > 999 else hi}"] = block(sel)
    ins = np.asarray(in_sample, float)
    summary["in_sample_control"] = {"positions": len(ins), "spearman_base": float(np.nanmean(ins[:, 0])), "spearman_tuned": float(np.nanmean(ins[:, 1]))}
    out = {"version": EVAL_VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(), "rows_file": args.rows,
           "positions": len(pos), "cells": n_cells, "leaf_samples": S, "folds": args.folds, "epochs": args.epochs, "lr": args.lr,
           "batch_cells": args.batch_cells, "seed": args.seed, "committee": prov, "tables_fingerprint": fp,
           "launch_git_sha": sha, "git_dirty": dirty, "qos": qos, "seconds": time.time() - t0, "curves": curves, "summary": summary}
    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    out_path.with_suffix(".rows.jsonl").write_text("".join(json.dumps(s) + "\n" for s in per))
    P = summary["pooled"]
    L = [f"# The evaluator read ({EVAL_VERSION}) -- {len(pos)} G0 positions, {n_cells} cells, {args.folds}-fold by position, OUT OF FOLD", "",
         f"fine-tune: the critic only, Adam lr {args.lr}, {args.epochs} epochs, {args.batch_cells} cells a batch, S {S}; git {sha}{' DIRTY' if dirty else ''}, qos {qos}, "
         f"{out['seconds'] / 60:.0f} min", "",
         f"- **cell Spearman vs the rollout means (per position):** base {P['spearman']['base'][0]:+.3f} ± {P['spearman']['base'][1]:.3f} -> "
         f"tuned {P['spearman']['tuned'][0]:+.3f} ± {P['spearman']['tuned'][1]:.3f}; paired delta **{P['spearman']['paired_delta'][0]:+.3f} ± "
         f"{P['spearman']['paired_delta'][1]:.3f}**",
         f"- in-sample control (training positions): {summary['in_sample_control']['spearman_base']:+.3f} -> {summary['in_sample_control']['spearman_tuned']:+.3f}",
         f"- cell MSE: {P['cell_mse']['base'][0]:.4f} -> {P['cell_mse']['tuned'][0]:.4f}; cell bias {P['cell_bias']['base'][0]:+.4f} -> {P['cell_bias']['tuned'][0]:+.4f}; "
         f"root bias vs v_root_rollout {P['root_bias']['base'][0]:+.4f} ± {P['root_bias']['base'][1]:.4f} -> {P['root_bias']['tuned'][0]:+.4f} ± {P['root_bias']['tuned'][1]:.4f} (outcome units)",
         "", "| gate | base override | base gain ± se | tuned override | tuned gain ± se | paired delta ± se |", "|--:|--:|---|--:|---|---|"]
    for gate in GATES:
        o = P["operator"][str(gate)]
        L.append(f"| {gate} | {o['base']['override']:.3f} | {o['base']['gain_win_rate']:+.4f} ± {o['base']['gain_se_win_rate']:.4f} | "
                 f"{o['tuned']['override']:.3f} | {o['tuned']['gain_win_rate']:+.4f} ± {o['tuned']['gain_se_win_rate']:.4f} | "
                 f"{o['paired_delta_win_rate'][0]:+.4f} ± {o['paired_delta_win_rate'][1]:.4f} |")
    L += ["", "| bucket | Spearman base | Spearman tuned | paired delta |", "|---|---|---|---|"]
    for k, b in summary["by_bucket"].items():
        L.append(f"| {k} | {b['spearman']['base'][0]:+.3f} | {b['spearman']['tuned'][0]:+.3f} | {b['spearman']['paired_delta'][0]:+.3f} ± {b['spearman']['paired_delta'][1]:.3f} |")
    out_path.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

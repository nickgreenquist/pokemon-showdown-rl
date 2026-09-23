#!/usr/bin/env python
"""R7, the BELIEF read on G0's positions: the operator on the TRUE world vs the
same operator on RESAMPLED worlds -- how much of what search gains is SEEING
the hidden state (the peek), and how much a student trained on true-world
targets keeps (the fusion cost), at the dials the operator actually runs.

WHY (the correction this pass exists for). P3's licence -- "the T-op searches
B = 1, the true world" (plan amendment box 4 item 4) -- was read by
`scripts/rollout_q_fusion.py` (rollout_q_fusion/1) at tau 1.0, cols_k 3,
chance_s 2 and no gate: dials at which the operator moves 0.6% of decisions
(`results/r7_g0/top_sweep.json`), so a 1.0% flip rate between worlds was
close to mechanical. It also carried the foe's TRUE-view prior into every
resampled world (re-masked), holding at the truth the channel through which
hidden information reaches the operator most directly: what the foe's own
policy says. G1 ran the operator at tau 0.05, cols_k 4, margin gate 0.01 (the
sweep's cell) and the fleet's T-op runs tau 0.05, cols_k 4. This pass reads
the licence at those dials, each world's foe prior recomputed by the
committee from THAT world's foe view.

Per G0 position (reloaded from the row's `node_b64`; G0's rows are READ, never
written -- this pass keeps its own rows file):

  a_greedy   argmax pi_theta (the row's `a_greedy`).
  a_true     G1's L-op exactly: `native.solve` on the true world, the foe prior
             the row's `pi2` (the committee on the foe's TRUE view), argmax
             pi', played iff it differs from greedy and the margin clears
             --margin-gate. Its decision key is the sweep's for the same cell,
             so on the same build this arm REPRODUCES the sweep's cell
             (printed beside it).
  a_belief   the SAME operator on B resampled worlds (`rl/search/resample.py`,
             the engine->engine resample; our side identical by construction),
             each world's foe prior the committee's on that world's foe view,
             Qbar per row AVERAGED over the worlds (PIMC), the soft best
             response on the average, the same gate: the operator WITHOUT
             peeking -- G2's operator, in the engine.
  t_true     argmax of the T-op's true-world target pi'_w0 (no gate; the T-op
             has none).
  t_avg      argmax of mean_b pi'_wb over the resampled worlds: where a student
             trained on TRUE-WORLD targets converges in expectation (the
             minimiser of E_w KL(pi'_w || pi_theta) is E_w pi'_w; the resample
             stands in for the posterior over w).
  t_pimc     argmax of the PIMC target (the soft best response on the
             world-averaged Qbar): the target a B >= 2 T-op would train on.

Every action is scored on G0's OWN ROLLOUT ORACLE at the true world (both
halves; Qbar weighted by pi2 over every legal column, both seats stochastic):
gain_X = Qbar[a_X] - Qbar[a_greedy], outcome units, reported in win-rate units
(/2) with override_X = 1{a_X != a_greedy} beside it. No choice here reads the
rollouts, so the full oracle is unbiased (no split needed). A belief-level
action scored on the true-world oracle and averaged over positions is its
value under the posterior; a true-world action scored the same way includes
the value of having seen the world.

  peek          gain_true - gain_belief (paired): the per-decision value of
                seeing the hidden state -- the share of G1's gain that no
                ladder opponent will hand us.
  fusion_cost   gain_t_pimc - gain_t_avg (paired): what a student trained on
                true-world targets gives up against one trained on PIMC
                targets (strategy fusion at the T-op's temperature).
  flip          1{a_belief != a_true}; target_flip 1{t_avg != t_true};
  world_flip    mean over worlds of 1{argmax pi'_wb != argmax pi'_w0} -- v1's
                `fusion_flip`, at these dials and with per-world foe priors;
  tv_target     TV(pi'_w0, mean_b pi'_wb): how far the T-op's target moves
                with the world.

Rule 6 does not bite: a mechanism read on saved positions, never a win-rate
A/B. The per-decision GAINS are small against their se on 500 positions (the
sweep's cell is +0.004 +- 0.0015 win-rate from 50 overrides); the flip and TV
reads are the precise ones, and the engine mirror (G1 with belief arms) is
the instrument for the gain.

Resume-safe: one JSON line per position in --rows-out; a restart skips the
pids already there, and each position's worlds are drawn from a generator
keyed on (seed, pid), so a resumed position redraws the same worlds.
Version-marked (the skip-guard landmine).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import itertools
import json
import os
import pathlib
import subprocess
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

BELIEF_VERSION = "rollout_q_belief/1"
ARMS = ("true", "belief", "t_true", "t_avg", "t_pimc")
# The T-op dial sweep's grid at its defaults (scripts/rollout_q_top_sweep.py):
# the true-world arm takes the sweep's decision key for the same (k, S, tau)
# cell, pid * 100_003 + grid index + 1, so it reproduces the sweep's choices.
SWEEP_GRID = list(itertools.product([2, 3, 4, 9], [2, 4, 8], [1.0, 0.5, 0.25, 0.1, 0.05]))


def soft_br(prior_m: np.ndarray, q_m: np.ndarray, tau: float) -> np.ndarray:
    """`native.solve`'s default root rule, the same arithmetic in the same
    order (asserted against the operator on every position's true world)."""
    logits = np.log(prior_m) + q_m / tau
    p = np.exp(logits - logits.max())
    return p / p.sum()


def gated(action: int, greedy: int, margin: float, gate: float) -> int:
    """The L-op's gate (scripts/g1_engine_mirror.py): the operator's argmax
    only where it moves off greedy by at least `gate` critic units."""
    return action if (action != greedy and margin >= gate) else greedy


def measure(r: dict, node, tables, committee, native, resample_world, dials: dict, gate: float,
            worlds: int, true_key: int, seed: int) -> dict:
    mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
    rows_a, cols_b = r["rows"], r["cols"]
    assert rows_a == np.flatnonzero(mask1).tolist() and cols_b == np.flatnonzero(mask2).tolist(), r["pid"]
    pi1 = np.asarray(r["pi1"]); pi2 = np.asarray(r["pi2"])
    prior1 = np.where(mask1, pi1, 0.0); prior2 = np.where(mask2, pi2, 0.0)
    prior_m = prior1[mask1] / prior1[mask1].sum()
    q_col = pi2[cols_b] / pi2[cols_b].sum()
    qbar = (0.5 * (np.asarray(r["q_half_a"]) + np.asarray(r["q_half_b"]))) @ q_col    # outcome units, per row
    row_of = {a: i for i, a in enumerate(rows_a)}
    greedy = int(r["a_greedy"]); ig = row_of[greedy]
    tau = float(dials.get("tau", 1.0))

    def value_fn(e):
        return committee.critic(e["obs"])

    t0 = time.perf_counter()
    true = native.solve([native.World(node)], tables, "p1", prior1, prior2, value_fn, true_key, **dials)
    if int(true["policy_action"]) != greedy:
        raise RuntimeError(f"pid {r['pid']}: the operator's policy action {true['policy_action']} != the row's a_greedy {greedy}")
    q_true_m = true["q_row"][mask1]
    pi_true_m = true["pi"][mask1]
    # Self-check: this file's soft BR on the true world's Qbar IS the operator's pi'.
    if not np.array_equal(soft_br(prior_m, q_true_m, tau), pi_true_m):
        raise RuntimeError(f"pid {r['pid']}: soft_br here disagrees with native.solve's pi' -- the PIMC arm would not be the same operator")
    a_true = gated(int(true["action"]), greedy, float(true["counters"]["search/margin"]), gate)

    wrng = np.random.default_rng([seed, int(r["pid"])])
    q_ws, pi_ws, infos, refused = [], [], [], []
    for b in range(worlds):
        try:
            world, info = resample_world(node, tables, "p1", wrng)
        except RuntimeError as e:
            refused.append(str(e)[:160]); continue
        if not np.array_equal(np.asarray(world.mask(tables, "p1"), bool), mask1):
            refused.append("our mask moved in the resampled world"); continue
        m2w = np.asarray(world.mask(tables, "p2"), bool)
        if m2w.any():
            p2w = committee.probs(np.asarray(world.obs(tables, "p2"), np.float32)[None], m2w[None])[0]
            p2w = np.where(m2w, p2w, 0.0)
        else:
            p2w = np.zeros_like(prior2)
        res = native.solve([native.World(world)], tables, "p1", prior1, p2w, value_fn,
                           (int(r["pid"]) + 1) * 1_000_003 + b + 1, **dials)
        q_ws.append(res["q_row"][mask1]); pi_ws.append(res["pi"][mask1])
        infos.append({k: info[k] for k in ("tries", "rejected_validate", "rejected_obs", "charging_dropped") if k in info})
    out = {"version": BELIEF_VERSION, "pid": int(r["pid"]), "bucket": int(r["bucket"]), "turn": int(r["turn"]),
           "a_greedy": greedy, "worlds_ok": len(q_ws), "worlds_refused": refused, "resample_info": infos,
           "a_true": a_true, "t_true": int(true["action"]), "margin_true": float(true["counters"]["search/margin"]),
           "gain_true": float(qbar[row_of[a_true]] - qbar[ig]), "gain_t_true": float(qbar[row_of[int(true["action"])]] - qbar[ig])}
    if q_ws:
        q_avg = np.mean(q_ws, axis=0)
        pi_pimc = soft_br(prior_m, q_avg, tau)
        i_pimc = int(np.argmax(pi_pimc)); t_pimc = int(rows_a[i_pimc])
        a_belief = gated(t_pimc, greedy, float(q_avg[i_pimc] - q_avg[ig]), gate)
        pi_avg = np.mean(pi_ws, axis=0)
        t_avg = int(rows_a[int(np.argmax(pi_avg))])
        i_true = int(np.argmax(pi_true_m))
        out.update({
            "a_belief": a_belief, "t_avg": t_avg, "t_pimc": t_pimc, "margin_pimc": float(q_avg[i_pimc] - q_avg[ig]),
            "gain_belief": float(qbar[row_of[a_belief]] - qbar[ig]),
            "gain_t_avg": float(qbar[row_of[t_avg]] - qbar[ig]),
            "gain_t_pimc": float(qbar[row_of[t_pimc]] - qbar[ig]),
            "flip": int(a_belief != a_true), "target_flip": int(t_avg != int(true["action"])),
            "world_flip": float(np.mean([int(np.argmax(p)) != i_true for p in pi_ws])),
            "tv_target": float(0.5 * np.abs(pi_true_m - pi_avg).sum()),
        })
    out["seconds"] = time.perf_counter() - t0
    return out


def mean_se(xs) -> tuple[float, float]:
    x = np.asarray([v for v in xs if v is not None], float)
    if len(x) == 0:
        return float("nan"), float("nan")
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else float("nan")


def summarise(sel: list[dict]) -> dict:
    ok = [s for s in sel if s.get("worlds_ok", 0) > 0]
    out = {"positions": len(sel), "positions_with_worlds": len(ok)}
    for arm in ARMS:
        src = sel if arm in ("true", "t_true") else ok
        key_a = {"true": "a_true", "belief": "a_belief", "t_true": "t_true", "t_avg": "t_avg", "t_pimc": "t_pimc"}[arm]
        ov = [int(s[key_a] != s["a_greedy"]) for s in src]
        m, se = mean_se([s[f"gain_{arm}"] for s in src])
        cond = [s[f"gain_{arm}"] for s in src if s[key_a] != s["a_greedy"]]
        mc, sec = mean_se(cond)
        out[arm] = {"override": float(np.mean(ov)) if ov else float("nan"), "n_override": int(sum(ov)),
                    "gain_win_rate": m / 2, "gain_se_win_rate": se / 2,
                    "gain_cond_win_rate": mc / 2, "gain_cond_se_win_rate": sec / 2}
    for name, (a, b) in {"peek": ("true", "belief"), "fusion_cost": ("t_pimc", "t_avg"),
                         "target_peek": ("t_true", "t_avg")}.items():
        m, se = mean_se([s[f"gain_{a}"] - s[f"gain_{b}"] for s in ok])
        out[name] = {"mean_win_rate": m / 2, "se_win_rate": se / 2}
    for k in ("flip", "target_flip", "world_flip", "tv_target"):
        m, se = mean_se([s[k] for s in ok])
        out[k] = {"mean": m, "se": se}
    # Of the positions where the true-world operator overrides, how often the
    # belief operator makes the SAME override (the share of G1's moves the
    # ladder can reproduce).
    moved = [s for s in ok if s["a_true"] != s["a_greedy"]]
    out["true_overrides_kept"] = {"n": len(moved), "same_move": float(np.mean([s["a_belief"] == s["a_true"] for s in moved])) if moved else float("nan")}
    out["worlds_refused"] = int(sum(len(s["worlds_refused"]) for s in sel))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", default="results/r7_g0/rollout_q.rows.jsonl", help="G0's rows (read only)")
    ap.add_argument("--rows-out", required=True, help="this pass's per-position rows (resume-safe)")
    ap.add_argument("--out", required=True, help="summary JSON; a .md is written beside it")
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--worlds", type=int, default=8, help="resampled worlds per position (B)")
    ap.add_argument("--dial", action="append", default=None, metavar="NAME=VALUE",
                    help="native.solve dials (the signature's list; an unknown name fails). Default: the sweep's cell, cols_k=4 chance_s=2 tau=0.05")
    ap.add_argument("--margin-gate", type=float, default=0.01, help="the L-op's gate, critic units (G1's)")
    ap.add_argument("--sweep", default="results/r7_g0/top_sweep.json", help="for the reproduction line")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--torch-threads", type=int, default=2)
    args = ap.parse_args()
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(args.torch_threads)
    import pkmn_gen1
    from rl.envs.engine_tables import build_tables
    from rl.search import native
    from rl.search.resample import resample_world
    import rollout_q as rq

    spec = dict(kv.split("=", 1) for kv in args.dial) if args.dial else {"cols_k": 4, "chance_s": 2, "tau": 0.05}
    dials = native.dials_from(spec)
    if dials.get("root_rule", "soft_br") != "soft_br":
        sys.exit("REFUSED: the PIMC arm here re-implements the soft best response only; root_rule must be soft_br")
    cell = (dials.get("cols_k", 3), dials.get("chance_s", 2), float(dials.get("tau", 1.0)))
    gi = SWEEP_GRID.index(cell) if cell in SWEEP_GRID else None

    def path(p: str) -> pathlib.Path:
        return pathlib.Path(p) if os.path.isabs(p) else ROOT / p

    # The program this pass is: a running block imports the working tree (landmine).
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, cwd=ROOT).stdout.strip())
    try:
        qos = "background" if os.getpriority(4, 0) != 0 else "normal"
    except OSError:
        qos = "unknown"
    rng = np.random.default_rng(args.seed)
    committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
    tables, fp = build_tables()
    rows = rq.load_rows(path(args.rows))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        sys.exit("no rows")
    rows_out = path(args.rows_out)
    rows_out.parent.mkdir(parents=True, exist_ok=True)
    done: dict[int, dict] = {}
    if rows_out.exists():
        for line in rows_out.read_text().splitlines():
            if line.strip():
                s = json.loads(line)
                if s.get("version") != BELIEF_VERSION:
                    sys.exit(f"REFUSED: {rows_out} holds rows of version {s.get('version')!r}, this is {BELIEF_VERSION!r}")
                done[int(s["pid"])] = s
    keyed = f"true-world key = the sweep's cell index {gi}" if gi is not None else "cell not in the sweep's grid: no reproduction"
    print(f"[belief] {len(rows)} positions, {len(done)} already on disk; dials {dials}, gate {args.margin_gate}, B {args.worlds}; {keyed}",
          flush=True)
    t0 = time.time(); n_new = 0
    for r in rows:
        pid = int(r["pid"])
        if pid in done:
            continue
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        true_key = pid * 100_003 + (gi + 1 if gi is not None else 999_331)
        s = measure(r, node, tables, committee, native, resample_world, dials, args.margin_gate, args.worlds, true_key, args.seed)
        with rows_out.open("a") as f:
            f.write(json.dumps(s) + "\n")
        done[pid] = s; n_new += 1
        if n_new % 25 == 0:
            print(f"[belief] {len(done)}/{len(rows)} positions, {(time.time() - t0) / n_new:.2f} s/pos", flush=True)

    sel = [done[int(r["pid"])] for r in rows]
    summary = {"pooled": summarise(sel), "by_bucket": {}}
    for b, (lo, hi) in enumerate(rq.BUCKETS):
        sb = [s for s in sel if s["bucket"] == b]
        if sb:
            summary["by_bucket"][f"{lo}-{'+' if hi > 999 else hi}"] = summarise(sb)
    repro = None
    sweep_path = path(args.sweep)
    if gi is not None and sweep_path.exists():
        sw = json.loads(sweep_path.read_text())
        c = [c for c in sw["cells"] if (c["cols_k"], c["chance_s"], float(c["tau"])) == cell and abs(c["margin_gate"] - args.margin_gate) < 1e-12]
        if c and not args.limit:
            p = summary["pooled"]["true"]
            repro = {"sweep_override": c[0]["override_rate"], "sweep_regret_win_rate": c[0]["regret_uncond_win_rate"],
                     "here_override": p["override"], "here_gain_win_rate": p["gain_win_rate"],
                     "identical": bool(abs(c[0]["override_rate"] - p["override"]) < 1e-12 and abs(c[0]["regret_uncond_win_rate"] - p["gain_win_rate"]) < 1e-12)}
    out = {"version": BELIEF_VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(), "rows_file": str(path(args.rows)),
           "rows_out": str(rows_out), "positions": len(sel), "worlds": args.worlds, "dials": dials, "margin_gate": args.margin_gate,
           "committee": prov, "tables_fingerprint": fp, "launch_git_sha": sha, "git_dirty": dirty, "qos": qos,
           "sweep_reproduction": repro, "summary": summary}
    out_path = path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))

    P = summary["pooled"]
    L = [f"# The belief read ({BELIEF_VERSION}) -- {len(sel)} G0 positions x B {args.worlds} resampled worlds, WIN-RATE units", "",
         f"dials {dials}, L-op gate {args.margin_gate}; worlds refused {P['worlds_refused']}; positions with >= 1 world {P['positions_with_worlds']}; "
         f"git {sha}{' DIRTY' if dirty else ''}, qos {qos}", "",
         "| arm | what it is | override | gain ± se (unconditional) | gain \\| override |", "|---|---|--:|---|---|"]
    what = {"true": "G1's L-op: true world, true foe prior, gated", "belief": "the same L-op on resampled worlds (PIMC), gated",
            "t_true": "the T-op target's argmax, true world", "t_avg": "argmax of the world-averaged targets (the student's fixed point)",
            "t_pimc": "argmax of the PIMC target"}
    for arm in ARMS:
        a = P[arm]
        L.append(f"| {arm} | {what[arm]} | {a['override']:.3f} ({a['n_override']}) | {a['gain_win_rate']:+.4f} ± {a['gain_se_win_rate']:.4f} | "
                 f"{a['gain_cond_win_rate']:+.4f} ± {a['gain_cond_se_win_rate']:.4f} |")
    L += ["", "| paired read | mean ± se (win-rate) |", "|---|---|"]
    for k in ("peek", "fusion_cost", "target_peek"):
        L.append(f"| {k} | {P[k]['mean_win_rate']:+.4f} ± {P[k]['se_win_rate']:.4f} |")
    L += ["", "| dependence on the world | mean ± se |", "|---|---|"]
    for k in ("flip", "target_flip", "world_flip", "tv_target"):
        L.append(f"| {k} | {P[k]['mean']:.3f} ± {P[k]['se']:.3f} |")
    kept = P["true_overrides_kept"]
    L.append(f"\nOf the {kept['n']} positions where the true-world L-op overrides, the belief L-op makes the SAME move on {kept['same_move']:.3f}.")
    if repro:
        L.append(f"\nReproduction of the sweep's cell: sweep override {repro['sweep_override']:.3f}, regret {repro['sweep_regret_win_rate']:+.5f}; "
                 f"here {repro['here_override']:.3f}, {repro['here_gain_win_rate']:+.5f} -> {'IDENTICAL' if repro['identical'] else 'DIFFERS'}")
    out_path.with_suffix(".md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nwrote {out_path} and {out_path.with_suffix('.md')}")


if __name__ == "__main__":
    main()

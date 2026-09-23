#!/usr/bin/env python
"""R7 G1 -- engine self-play, the fast in-block test of the operator (plan §6):
the L-op (true world, B=1, depth-1, the committee's observation critic as the
leaf) vs GREEDY, both from the SAME checkpoint committee, engine mirror
matches, n battles per arm, SEAT-SWAPPED (arm `lop_p1`: the L-op sits in p1;
arm `lop_p2`: in p2), plus the anchor `greedy_greedy` = 0.5 by symmetry -- a
free instrument check. No Showdown, no Foul Play; hours not days; runs niced
beside a fleet (engine-only). Rule 6: a mechanism read on the operator, never
a win-rate A/B against the credit line (G2 is that, off FP@20).

THE MATCHING DEVICE (the landmine "match on the override rate, not the
delta"): the L-op plays the operator's argmax pi' ONLY where the critic-unit
margin Qbar[a'] - Qbar[greedy] clears `--margin-gate` (set from the T-op dial
sweep, `results/r7_g0/top_sweep.md`); elsewhere it plays greedy. The override
rate is reported beside every win rate, and two arms are comparable only at
matched override rates. `--override-se-gate` instead gates on the margin's
standard error over the chance samples (plan §6's "Qbar(a') - Qbar(a_greedy)
>= 2 se"), computed from a second, independent chance draw of the same root.

Resume-safe: one JSON line per finished battle in --rows (arm, seed, outcome
from the L-op's / learner's seat, decisions, overrides, ms); a restart counts
the rows per arm and continues, re-drawing the k battles that were in flight
(the engine's battle sequence is seeded by (lane seed, battle_counter)). Rate:
battles/min per arm on every progress line.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

G1_VERSION = "g1_engine_mirror/1"
ARMS = ("lop_p1", "lop_p2", "greedy_greedy")


def win_rate(outcomes: np.ndarray) -> tuple[float, float]:
    """Ties as half; the binomial se on the same scale."""
    if len(outcomes) == 0:
        return float("nan"), float("nan")
    p = float(((outcomes + 1.0) / 2.0).mean())
    return p, math.sqrt(max(p * (1 - p), 1e-12) / len(outcomes))


class LOp:
    """The ladder operator at depth 1 on the true world, gated."""

    def __init__(self, committee, tables, seat, cols_k, chance_s, tau, margin_gate, se_gate, rng):
        from rl.search import native
        self.native = native
        self.c = committee
        self.tables = tables
        self.seat = seat
        self.foe = "p2" if seat == "p1" else "p1"
        self.cols_k, self.chance_s, self.tau = cols_k, chance_s, tau
        self.margin_gate, self.se_gate = margin_gate, se_gate
        self.rng = rng
        self.key = 0
        self.decisions = self.overrides = self.eligible = 0
        self.ms = 0.0
        self.value_fn = lambda e: committee.critic(e["obs"])

    def act(self, env, idx, obs, mask) -> tuple[np.ndarray, np.ndarray]:
        """Greedy on every row, replaced by the gated operator's argmax; returns
        (actions, greedy) so the caller can count overrides per slot."""
        greedy = self.c.greedy(obs, mask)
        actions = greedy.copy()
        n_over = 0
        probs = self.c.probs(obs, mask)
        for i in range(len(idx)):
            self.decisions += 1
            if mask[i].sum() <= 1:
                continue                      # forced: nothing to search
            self.eligible += 1
            node = env.snapshot(int(idx[i]))
            foe_mask = np.asarray(node.mask(self.tables, self.foe), bool)
            if foe_mask.any():
                foe_obs = np.asarray(node.obs(self.tables, self.foe), np.float32)[None]
                opp_prior = self.c.probs(foe_obs, foe_mask[None])[0]
            else:
                opp_prior = np.zeros(mask.shape[1])
            t0 = time.perf_counter()
            self.key += 1
            res = self.native.solve([self.native.World(node)], self.tables, self.seat, probs[i], opp_prior,
                                    self.value_fn, self.key, cols_k=self.cols_k, chance_s=self.chance_s, tau=self.tau)
            a_prime, margin = int(res["action"]), float(res["counters"]["search/margin"])
            fire = a_prime != int(greedy[i]) and margin >= self.margin_gate
            if fire and self.se_gate > 0:
                # A second, independent chance draw of the same root: the
                # margin's spread across draws is its standard error proxy.
                self.key += 1
                res2 = self.native.solve([self.native.World(node)], self.tables, self.seat, probs[i], opp_prior,
                                         self.value_fn, self.key, cols_k=self.cols_k, chance_s=self.chance_s, tau=self.tau)
                q1, q2 = res["q_row"], res2["q_row"]
                d1 = q1[a_prime] - q1[int(greedy[i])]
                d2 = q2[a_prime] - q2[int(greedy[i])]
                se = abs(d1 - d2) / math.sqrt(2.0)
                fire = (0.5 * (d1 + d2)) >= self.se_gate * max(se, 1e-9)
            self.ms += (time.perf_counter() - t0) * 1e3
            if fire:
                actions[i] = a_prime
                n_over += 1
        self.overrides += n_over
        return actions, greedy


def run_arm(arm: str, args, committee, tables, payload, rows_path: pathlib.Path, done: int) -> None:
    import pkmn_gen1
    seat = "p1" if arm != "lop_p2" else "p2"
    seed = args.seed + ARMS.index(arm) * 1_000_003
    env = pkmn_gen1.BatchEnv(args.k, seed, tables, payload, seat, done)
    rng = np.random.default_rng(seed)
    lop = None if arm == "greedy_greedy" else LOp(committee, tables, seat, args.cols_k, args.chance_s, args.tau,
                                                  args.margin_gate, args.override_se_gate, rng)
    t0 = time.time(); finished = done; per_battle: dict[int, list[int]] = {}
    while finished < args.n:
        li, lobs, lmask, _ = env.pending("learner")
        oi, oobs, omask, _ = env.pending("opponent")
        if len(li):
            if lop is None:
                la = committee.greedy(lobs, lmask)
                for s in li.tolist():
                    per_battle.setdefault(int(s), [0, 0])[0] += 1
            else:
                la, greedy = lop.act(env, li, lobs, lmask)
                for j, s in enumerate(li.tolist()):
                    rec = per_battle.setdefault(int(s), [0, 0])
                    rec[0] += 1
                    rec[1] += int(la[j] != greedy[j])
        else:
            la = np.empty(0, np.int64)
        oa = committee.greedy(oobs, omask) if len(oi) else np.empty(0, np.int64)
        env.step(li.tolist(), la.tolist(), [0.0] * len(li), 0, oi.tolist(), oa.tolist())
        for ep in env.drain_finished():
            slot = int(ep["slot"])
            d, o = per_battle.pop(slot, [0, 0])
            row = {"version": G1_VERSION, "arm": arm, "seat": seat, "outcome": int(ep["reward"]), "length": int(ep["length"]),
                   "decisions": d, "overrides": o, "battle_index": finished}
            with rows_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            finished += 1
            if finished % 50 == 0 or finished >= args.n:
                el = time.time() - t0
                extra = ""
                if lop is not None:
                    extra = (f" | override {lop.overrides / max(lop.decisions, 1):.3f} of {lop.decisions} decisions, "
                             f"{lop.ms / max(lop.eligible, 1):.1f} ms/searched decision")
                print(f"[{arm}] {finished}/{args.n} battles, {(finished - done) / max(el, 1e-9) * 60:.1f} battles/min{extra}", flush=True)
            if finished >= args.n:
                break


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--bank", required=True)
    ap.add_argument("--n", type=int, default=5000, help="battles per arm")
    ap.add_argument("--k", type=int, default=64, help="battles in flight")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS))
    ap.add_argument("--cols-k", type=int, default=3)
    ap.add_argument("--chance-s", type=int, default=2)
    ap.add_argument("--tau", type=float, default=1.0)
    ap.add_argument("--margin-gate", type=float, default=0.0, help="critic units; override iff margin >= this")
    ap.add_argument("--override-se-gate", type=float, default=0.0, help="0 = off; else override iff margin >= this x se (two chance draws)")
    ap.add_argument("--seed", type=int, default=20260924)
    ap.add_argument("--torch-threads", type=int, default=2)
    ap.add_argument("--rows", default="results/r7_g1/g1.rows.jsonl")
    ap.add_argument("--out", default="results/r7_g1/g1.json")
    args = ap.parse_args()
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import torch
    torch.set_num_threads(args.torch_threads)
    import engine_team_bank as bank
    import rollout_q as rq
    from rl.envs.engine_tables import build_tables

    rng = np.random.default_rng(args.seed)
    committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
    tables, fp = build_tables()
    _h, payload = bank.read_bank(pathlib.Path(args.bank))
    rows_path = pathlib.Path(args.rows) if os.path.isabs(args.rows) else ROOT / args.rows
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if rows_path.exists():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("version") != G1_VERSION:
                    sys.exit(f"REFUSED: {rows_path} carries rows of version {r.get('version')!r}, this is {G1_VERSION!r}")
                rows.append(r)
    for arm in args.arms:
        done = sum(1 for r in rows if r["arm"] == arm)
        if done >= args.n:
            print(f"[{arm}] complete ({done} rows)")
            continue
        print(f"[{arm}] starting at {done}/{args.n} (k {args.k}; a resume re-draws the k in flight)", flush=True)
        run_arm(arm, args, committee, tables, payload, rows_path, done)
        rows = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]

    summary = {}
    for arm in ARMS:
        sel = [r for r in rows if r["arm"] == arm]
        if not sel:
            continue
        o = np.array([r["outcome"] for r in sel], float)
        p, se = win_rate(o)
        d = sum(r["decisions"] for r in sel); ov = sum(r["overrides"] for r in sel)
        summary[arm] = {"n": len(sel), "win_rate": p, "se": se, "ties": int((o == 0).sum()),
                        "decisions": d, "override_rate": ov / max(d, 1), "mean_length": float(np.mean([r["length"] for r in sel]))}
    lop = [r for r in rows if r["arm"] in ("lop_p1", "lop_p2")]
    if lop:
        o = np.array([r["outcome"] for r in lop], float)
        p, se = win_rate(o)
        d = sum(r["decisions"] for r in lop); ov = sum(r["overrides"] for r in lop)
        summary["lop_pooled"] = {"n": len(lop), "win_rate": p, "se": se, "override_rate": ov / max(d, 1)}
        if "greedy_greedy" in summary:
            a = summary["greedy_greedy"]
            summary["lop_minus_anchor"] = {"delta": p - a["win_rate"], "se_diff": math.sqrt(se ** 2 + a["se"] ** 2)}
    out = {"version": G1_VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(), "committee": prov,
           "bank": args.bank, "tables_fingerprint": fp, "args": vars(args), "summary": summary,
           "rows_file": str(rows_path), "qos": "background" if _qos_background() else "normal"}
    out_path = pathlib.Path(args.out) if os.path.isabs(args.out) else ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print("\n" + "=" * 78)
    print(f"G1 ({G1_VERSION}) -- engine mirror matches, committee of {len(prov)}; win rates from the L-op's / learner's seat, ties as half")
    for arm, s in summary.items():
        if "win_rate" in s:
            print(f"  {arm:<14} n {s['n']:>5}  win {s['win_rate']:.4f} +- {s['se']:.4f}  override {s.get('override_rate', 0):.3f}")
    if "lop_minus_anchor" in summary:
        m = summary["lop_minus_anchor"]
        print(f"  L-op pooled minus anchor: {m['delta']:+.4f} +- {m['se_diff']:.4f}  (the anchor's distance from 0.5 is the instrument check)")
    print(f"  gate: margin >= {args.margin_gate} critic units" + (f", se-gate {args.override_se_gate}" if args.override_se_gate else "") +
          f"; dials k {args.cols_k} S {args.chance_s} tau {args.tau}; wrote {out_path}")
    print("=" * 78)


def _qos_background() -> bool:
    try:
        return os.getpriority(4, 0) != 0
    except OSError:
        return False


if __name__ == "__main__":
    main()

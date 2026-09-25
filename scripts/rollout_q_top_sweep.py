#!/usr/bin/env python
"""R7 G0, the T-OP DIAL SWEEP -- a second pass over `scripts/rollout_q.py`'s rows
that needs no new rollouts (plan amendment box 3, item 5: "the T-op's k is set
from that read, not typed"; the landmine: MATCH ON THE OVERRIDE RATE, NOT THE
DELTA).

At the rows' own dials (cols_k 3, chance_s 2, tau 1) the critic-leaf T-op
overrides the greedy action on <1% of positions, so `regret_critic_depth1` is
~0 by construction there and says nothing about the operator. This pass re-runs
the operator on every saved position over a grid of (cols_k, chance_s, tau)
and, post hoc, a MARGIN GATE (override only when Qbar[a'] - Qbar[greedy] in
critic units clears m), and scores each cell's chosen action against G0's OWN
rollout oracle: `regret = Qbar_rollout(a') - Qbar_rollout(greedy)` on the full
256-sample means (unbiased -- a' is chosen by the critic, independently of the
rollouts). Per dial and gate: the override rate, the unconditional regret, the
regret CONDITIONAL on an override, and the fraction of the split-sample ceiling
captured. Read the regret at MATCHED override rates across dials; never a delta
alone. The leaf evaluator is the committee's OBSERVATION critic on the true
world (B=1), exactly as the rows were made; the privileged critic is PENDING.

Idempotent: writes one JSON + one markdown table; resume-safe by cost (minutes).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import itertools
import json
import os
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

SWEEP_VERSION = "rollout_q_top_sweep/1"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--out", required=True, help="JSON; a .md table is written beside it")
    ap.add_argument("--cols-k", type=int, nargs="+", default=[2, 3, 4, 9])
    ap.add_argument("--chance-s", type=int, nargs="+", default=[2, 4, 8])
    ap.add_argument("--tau", type=float, nargs="+", default=[1.0, 0.5, 0.25, 0.1, 0.05])
    ap.add_argument("--margin-gates", type=float, nargs="+", default=[0.0, 0.01, 0.02, 0.05, 0.1])
    ap.add_argument("--limit", type=int, default=0, help="first N rows only (a smoke)")
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
    import rollout_q as rq

    rng = np.random.default_rng(args.seed)
    committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
    tables, _fp = build_tables()
    rows = rq.load_rows(pathlib.Path(args.rows))
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        sys.exit("no rows")

    def value_fn(e):
        return committee.critic(e["obs"])

    grid = list(itertools.product(args.cols_k, args.chance_s, args.tau))
    # per cell: lists over positions of (override, regret_outcome, margin, kl, ms, ceiling)
    per = {g: {"a_prime": [], "margin": [], "kl": [], "ms": [], "leaves": []} for g in grid}
    ceilings, greedy_rows, qbar_rows, buckets = [], [], [], []
    t0 = time.time()
    for i, r in enumerate(rows):
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
        rows_a, cols_b = r["rows"], r["cols"]
        assert rows_a == np.flatnonzero(mask1).tolist() and cols_b == np.flatnonzero(mask2).tolist(), r["pid"]
        pi1 = np.asarray(r["pi1"]); pi2 = np.asarray(r["pi2"])
        prior1 = np.where(mask1, pi1, 0.0); prior2 = np.where(mask2, pi2, 0.0)
        q_col = pi2[cols_b] / pi2[cols_b].sum()
        q_full = 0.5 * (np.asarray(r["q_half_a"]) + np.asarray(r["q_half_b"]))
        qbar = q_full @ q_col                                   # (n_rows,) rollout Qbar, outcome units
        row_of = {a: j for j, a in enumerate(rows_a)}
        g = row_of[int(r["a_greedy"])]
        ceilings.append(float(r["regret_depth1_ceiling"]))
        greedy_rows.append(g); qbar_rows.append(qbar); buckets.append(int(r["bucket"]))
        for gi, (k, s, tau) in enumerate(grid):
            key = int(r["pid"]) * 100_003 + gi + 1
            res = native.solve([native.World(node)], tables, "p1", prior1, prior2, value_fn, key,
                               cols_k=k, chance_s=s, tau=tau)
            c = res["counters"]
            p = per[(k, s, tau)]
            p["a_prime"].append(int(res["action"])); p["margin"].append(float(c["search/margin"]))
            p["kl"].append(float(c["search/kl_prior"])); p["ms"].append(float(c["search/ms"]))
            p["leaves"].append(float(c["search/leaves"]))
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(rows)} positions, {(time.time() - t0) / (i + 1):.1f} s/pos", flush=True)

    ceilings = np.asarray(ceilings); buckets = np.asarray(buckets)
    n = len(rows)
    cells = []
    for (k, s, tau) in grid:
        p = per[(k, s, tau)]
        a_prime = np.asarray(p["a_prime"]); margin = np.asarray(p["margin"])
        regret_raw = np.array([qbar_rows[i][rows[i]["rows"].index(int(a_prime[i]))] - qbar_rows[i][greedy_rows[i]] for i in range(n)])
        differs = np.array([int(a_prime[i]) != int(rows[i]["a_greedy"]) for i in range(n)])
        for m in args.margin_gates:
            ov = differs & (margin >= m)
            regret = np.where(ov, regret_raw, 0.0)
            mu, se = rq.mean_se(regret)
            mc, sec = rq.mean_se(regret[ov]) if ov.any() else (float("nan"), float("nan"))
            cell = {"cols_k": k, "chance_s": s, "tau": tau, "margin_gate": m,
                    "override_rate": float(ov.mean()), "n_override": int(ov.sum()),
                    "regret_uncond_win_rate": rq.win_rate(mu), "regret_uncond_se_win_rate": rq.win_rate(se),
                    "regret_cond_win_rate": rq.win_rate(mc), "regret_cond_se_win_rate": rq.win_rate(sec) if sec == sec else sec,
                    "ceiling_captured": float(regret.sum() / ceilings.sum()) if ceilings.sum() > 0 else float("nan"),
                    "kl_prior_mean": float(np.mean(p["kl"])), "ms_mean": float(np.mean(p["ms"])), "leaves_mean": float(np.mean(p["leaves"])),
                    "by_bucket_override": {str(b): float(ov[buckets == b].mean()) if (buckets == b).any() else float("nan") for b in range(4)},
                    "by_bucket_regret_uncond_win_rate": {str(b): rq.win_rate(float(regret[buckets == b].mean())) if (buckets == b).any() else float("nan") for b in range(4)}}
            cells.append(cell)
    ceil_mu, ceil_se = rq.mean_se(ceilings)
    out = {"version": SWEEP_VERSION, "written": dt.datetime.now(dt.timezone.utc).isoformat(), "positions": n,
           "rows_file": args.rows, "committee": prov, "grid": {"cols_k": args.cols_k, "chance_s": args.chance_s, "tau": args.tau, "margin_gates": args.margin_gates},
           "ceiling_win_rate": {"mean": rq.win_rate(ceil_mu), "se": rq.win_rate(ceil_se)},
           "evaluator": "committee observation critic on the true world (B=1); privileged critic PENDING",
           "cells": cells}
    out_path = pathlib.Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    # The table, sorted by override rate so matched reads sit next to each other.
    md = [f"# T-op dial sweep ({SWEEP_VERSION}) — {n} positions, ceiling {rq.win_rate(ceil_mu):+.4f} ± {rq.win_rate(ceil_se):.4f} win-rate",
          "", "Evaluator: the committee's observation critic, true world, B=1. Regret = rollout Q̄(a′) − Q̄(greedy) on the 256-sample means, "
          "WIN-RATE scale; 'cond' = over overridden positions only. Read at MATCHED override rates.", "",
          "| k | S | τ | gate m | override | n | regret uncond ± se | regret cond ± se | ceiling captured | kl_prior | ms |",
          "|--:|--:|--:|--:|--:|--:|---|---|--:|--:|--:|"]
    for c in sorted(cells, key=lambda c: (c["override_rate"], c["cols_k"], c["chance_s"], -c["tau"], c["margin_gate"])):
        md.append(f"| {c['cols_k']} | {c['chance_s']} | {c['tau']} | {c['margin_gate']} | {c['override_rate']:.3f} | {c['n_override']} | "
                  f"{c['regret_uncond_win_rate']:+.4f} ± {c['regret_uncond_se_win_rate']:.4f} | {c['regret_cond_win_rate']:+.4f} ± {c['regret_cond_se_win_rate']:.4f} | "
                  f"{c['ceiling_captured']:+.3f} | {c['kl_prior_mean']:.4f} | {c['ms_mean']:.1f} |")
    out_path.with_suffix(".md").write_text("\n".join(md) + "\n")
    best = max((c for c in cells if c["n_override"] >= 20), key=lambda c: c["regret_uncond_win_rate"], default=None)
    print(f"\nSWEEP: {n} positions x {len(grid)} dials x {len(args.margin_gates)} gates; wrote {out_path} and {out_path.with_suffix('.md')}")
    if best:
        print(f"  best unconditional regret with >= 20 overrides: k {best['cols_k']} S {best['chance_s']} tau {best['tau']} gate {best['margin_gate']}: "
              f"override {best['override_rate']:.3f}, regret {best['regret_uncond_win_rate']:+.4f} ± {best['regret_uncond_se_win_rate']:.4f} win-rate "
              f"(cond {best['regret_cond_win_rate']:+.4f}), ceiling captured {best['ceiling_captured']:+.3f}")
    print(f"  {(time.time() - t0) / n:.1f} s/position")


if __name__ == "__main__":
    main()

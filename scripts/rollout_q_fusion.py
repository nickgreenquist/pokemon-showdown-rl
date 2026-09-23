#!/usr/bin/env python
"""R7 G0, the FUSION columns -- a second pass over `scripts/rollout_q.py`'s rows
that needs no new rollouts (plan amendment box 3, item 6; REPLY BOX 2 §5).

The strategy-fusion bias of searching the TRUE world (P3) is zero exactly when
the operator's chosen action does not depend on the hidden world `w`. That is
measurable offline: run the T-op at the true world `w0` and at B resampled
worlds `w1..wB ~ P(w | o)` (`rl/search/resample.py`, the engine->engine
resample), and read

  fusion_flip   = P( argmax pi'(.|o, w0) != argmax pi'(.|o, w_b) ),  b = 1..B
  fusion_bound  = E[ 1{flip} * (Qbar(a_avg) - Qbar(a(w0))) ]

where `a_avg` is the argmax of pi' AVERAGED over {w0, w1..wB} (the
belief-averaged action), `a(w0)` the true-world action, and Qbar is G0's OWN
ROLLOUT ORACLE for the position (the stored per-cell means over both halves,
weighted by pi_opp over the columns) -- so the bound is in outcome units and
the rollouts already paid for are what price it. Two worlds give a noisy but
unbiased flip rate; four give a usable bound.

Every position is reloaded from its row's `node_b64` (`SearchNode.load`), so
the roots are bit-identical to the ones the rollouts were played from; the
critic is the same committee critic the first pass used. Rows are updated IN
PLACE with the two columns plus `fusion_worlds`, `fusion_resample_info`, and
the summary JSON gains a `fusion` block. Idempotent: a row already carrying
the columns at this version is skipped.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

FUSION_VERSION = "rollout_q_fusion/1"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", default="results/r7_g0/rollout_q.rows.jsonl")
    ap.add_argument("--out", default="results/r7_g0/rollout_q.json")
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--sha256", nargs="*", default=None)
    ap.add_argument("--worlds", type=int, default=4, help="resampled worlds per position (B)")
    ap.add_argument("--critic-chance", type=int, default=2)
    ap.add_argument("--critic-cols-k", type=int, default=3)
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

    rng = np.random.default_rng(args.seed)
    committee, prov = rq.load_committee(args.checkpoints, args.sha256, rng)
    tables, _fp = build_tables()
    rows_path = ROOT / args.rows if not os.path.isabs(args.rows) else pathlib.Path(args.rows)
    rows = rq.load_rows(rows_path)
    if not rows:
        sys.exit(f"no rows at {rows_path}")

    def value_fn(e):
        return committee.critic(e["obs"])

    done = 0; t0 = time.time()
    for r in rows:
        if r.get("fusion_version") == FUSION_VERSION and r.get("fusion_flip") is not None:
            continue
        node = pkmn_gen1.SearchNode.load(base64.b64decode(r["node_b64"]))
        mask1 = np.asarray(node.mask(tables, "p1"), bool); mask2 = np.asarray(node.mask(tables, "p2"), bool)
        rows_a = r["rows"]; cols_b = r["cols"]
        assert rows_a == np.flatnonzero(mask1).tolist() and cols_b == np.flatnonzero(mask2).tolist(), r["pid"]
        pi1 = np.asarray(r["pi1"]); pi2 = np.asarray(r["pi2"])
        prior1 = np.where(mask1, pi1, 0.0); prior2 = np.where(mask2, pi2, 0.0)
        q_col = pi2[cols_b] / pi2[cols_b].sum()
        q_full = 0.5 * (np.asarray(r["q_half_a"]) + np.asarray(r["q_half_b"]))     # (n_rows, n_cols)
        qbar = q_full @ q_col                                                      # rollout Qbar per row
        row_of = {a: i for i, a in enumerate(rows_a)}
        dials = dict(cols_k=args.critic_cols_k, chance_s=args.critic_chance, tau=1.0)
        true = native.solve([native.World(node)], tables, "p1", prior1, prior2, value_fn, r["pid"], **dials)
        pis = [true["pi"]]; flips = []; infos = []
        for b in range(args.worlds):
            world, info = resample_world(node, tables, "p1", rng)
            infos.append({k: info[k] for k in ("tries", "rejected_validate", "rejected_obs", "charging_dropped")})
            # The resampled world's foe mask may differ (a different bench); the
            # operator re-reads it, and pi_opp is re-masked to it uniformly over
            # the newly legal replies the prior never saw.
            m2 = np.asarray(world.mask(tables, "p2"), bool)
            p2w = np.where(m2, pi2, 0.0)
            if p2w.sum() <= 0:
                p2w = m2.astype(np.float64)
            p2w /= p2w.sum()
            res = native.solve([native.World(world)], tables, "p1", prior1, p2w, value_fn, r["pid"] * 7919 + b + 1, **dials)
            pis.append(res["pi"])
            flips.append(int(res["action"] != true["action"]))
        pi_avg = np.mean(pis, axis=0)
        a_avg = int(rows_a[int(np.argmax(pi_avg[mask1]))])
        flip_rate = float(np.mean(flips))
        bound = float(flip_rate * (qbar[row_of[a_avg]] - qbar[row_of[true["action"]]]))
        r.update({"fusion_flip": flip_rate, "fusion_bound": bound, "fusion_a_avg": a_avg, "fusion_a_true": int(true["action"]),
                  "fusion_worlds": args.worlds, "fusion_resample_info": infos, "fusion_version": FUSION_VERSION,
                  "fusion_why": None})
        done += 1
        if done % 10 == 0:
            print(f"{done} positions: flip {flip_rate:.2f} bound {rq.win_rate(bound):+.4f} (win-rate) | {(time.time() - t0) / done:.1f} s/pos", flush=True)
    rows_path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    flips = [r["fusion_flip"] for r in rows if r.get("fusion_flip") is not None]
    bounds = [r["fusion_bound"] for r in rows if r.get("fusion_bound") is not None]
    mf, sf = rq.mean_se(flips); mb, sb = rq.mean_se(bounds)
    block = {"version": FUSION_VERSION, "positions": len(flips), "worlds": args.worlds,
             "fusion_flip": {"mean": mf, "se": sf},
             "fusion_bound": {"mean_outcome": mb, "se_outcome": sb, "mean_win_rate": rq.win_rate(mb),
                              "se_win_rate": rq.win_rate(sb) if sb == sb else sb,
                              "upper95_win_rate": rq.win_rate(mb + 1.96 * sb) if sb == sb else float("nan")},
             "by_bucket": {}}
    for i, (lo, hi) in enumerate(rq.BUCKETS):
        sel = [r for r in rows if r.get("fusion_flip") is not None and r["bucket"] == i]
        m1, s1 = rq.mean_se([r["fusion_flip"] for r in sel]); m2_, s2 = rq.mean_se([r["fusion_bound"] for r in sel])
        block["by_bucket"][f"{lo}-{'+' if hi > 999 else hi}"] = {"positions": len(sel), "flip": m1, "flip_se": s1,
                                                                 "bound_win_rate": rq.win_rate(m2_), "bound_se_win_rate": rq.win_rate(s2) if s2 == s2 else s2}
    out_path = ROOT / args.out if not os.path.isabs(args.out) else pathlib.Path(args.out)
    summary = json.loads(out_path.read_text()) if out_path.exists() else {}
    summary["fusion"] = block
    out_path.write_text(json.dumps(summary, indent=1))
    print(f"\nFUSION ({FUSION_VERSION}): {len(flips)} positions x {args.worlds} worlds; ALL IN WIN-RATE UNITS")
    print(f"  fusion_flip   {mf:.3f} +- {sf:.3f}")
    print(f"  fusion_bound  {rq.win_rate(mb):+.4f} +- {rq.win_rate(sb):.4f}  (upper95 {block['fusion_bound']['upper95_win_rate']:+.4f})")
    print(f"  read against the credit floor +0.025 (plan §10: above it, P3's licence is spent and the T-op searches B >= 2 worlds)")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()

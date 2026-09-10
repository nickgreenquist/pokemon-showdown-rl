#!/usr/bin/env python
"""How does the PPO UPDATE scale with `torch_threads` on this box?

WHY THIS IS THE QUESTION NOW. Before the collector port, collection was 75% of
training wall clock and the update was 25%, so how fast the update ran barely
mattered. After the port those numbers INVERT: the update is 65% of wall
(results/engine_a1/update_share.json, three lanes each side, both 3-wide). And
both configs set `torch_threads: 1` (rl/train.py:398), so that 65% is running
single-threaded on a box with 14 logical cores while a 3-lane engine fleet uses
about 3 of them.

So this measures the one thing that would change that: update wall against
thread count, on the REAL update path, with a REAL batch.

METHOD, and the two things it is careful about:
  * The batch is COLLECTED, not synthesised. Shapes drive most of the cost, but
    a synthetic batch cannot be trusted on the parts that branch on values, and
    collecting one update's worth from the engine costs seconds.
  * Every thread count updates a FRESH DEEP COPY of the same agent over the
    SAME episodes. Otherwise thread count 2 would be timing an agent that
    thread count 1 had already stepped, on data whose advantages had shifted.

WHAT IT DOES NOT MEASURE. Threads under FLEET CONTENTION. These numbers are one
lane with the box to itself; three lanes at 4 threads each want 12 cores and
will not get this scaling. That is the whole point of reporting a curve rather
than a single "use N threads" answer — the fleet-width choice depends on how
many lanes you intend to run, and this only bounds the single-lane end.

    python scripts/engine_thread_bench.py runs/<run>/ckpt_012000008.pt \\
        --threads 1,2,4,8 --team-bank data/engine/teams_a1_5000000.bin
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", type=pathlib.Path)
    ap.add_argument("--threads", default="1,2,4,8")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--k", type=int, default=64,
                    help="engine k for the COLLECTION of the benchmark batch; "
                         "it has no bearing on the update being timed")
    ap.add_argument("--team-bank", default="data/engine/teams_a1_5000000.bin")
    ap.add_argument("--seed", type=int, default=7731)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/thread_bench.json"))
    args = ap.parse_args(argv)

    import torch

    from engine_a1a import build_agent
    from rl.buffers.episode import EpisodeDataset
    from rl.envs.engine_collector import EngineCollector
    from rl.selfplay.pool import SnapshotPool

    agent, cfg = build_agent(args.checkpoint)
    batch = int(cfg.agent["rollout_steps"]) * int(cfg.num_envs)
    print(f"batch = rollout_steps {cfg.agent['rollout_steps']} x num_envs "
          f"{cfg.num_envs} = {batch:,} steps per update", flush=True)

    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)
    collector = EngineCollector(agent.act_logp, pool, seed=args.seed, k=args.k,
                               team_bank=args.team_bank,
                               opp_action=bool(cfg.env_kwargs.get("opp_action")))
    print("collecting one update's worth of REAL episodes...", flush=True)
    t0 = time.perf_counter()
    episodes, steps = [], 0
    collector.start(0)
    while steps < batch:
        for ep in collector.poll():
            episodes.append(ep)
            steps += len(ep["actions"])
    collector.close()
    print(f"  {len(episodes)} episodes, {steps:,} steps in "
          f"{time.perf_counter() - t0:.1f}s", flush=True)

    rows = []
    for n in [int(x) for x in args.threads.split(",")]:
        torch.set_num_threads(n)
        times = []
        for _ in range(args.repeats):
            a = copy.deepcopy(agent)
            a.buffer = None
            ds = EpisodeDataset()
            for ep in episodes:
                ds.append(ep)
            t = time.perf_counter()
            a.update_episodes(ds.drain(), steps_seen=0)
            times.append(time.perf_counter() - t)
        best = min(times)
        rows.append({"threads": n, "update_seconds_min": best,
                     "update_seconds_all": times,
                     "torch_get_num_threads": torch.get_num_threads()})
        print(f"  threads={n:>2}  update {best:6.2f}s  "
              f"(all: {', '.join(f'{x:.2f}' for x in times)})", flush=True)

    base = rows[0]["update_seconds_min"]
    for r in rows:
        r["speedup_vs_1_thread"] = base / r["update_seconds_min"]

    # What the loop would do, holding COLLECTION fixed at the measured 3-wide
    # engine share. Explicitly an EXTRAPOLATION: collection is unchanged here,
    # and these thread numbers are single-lane with the box to itself.
    U_SHARE = 0.6513   # results/engine_a1/update_share.json, engine 3-wide
    for r in rows:
        f = 1.0 / r["speedup_vs_1_thread"]
        r["implied_full_loop_speedup"] = 1.0 / ((1 - U_SHARE) + U_SHARE * f)

    out = {
        "question": "does the PPO update parallelise, now that it is 65% of "
                    "training wall clock",
        "batch_steps": batch,
        "episodes_in_batch": len(episodes),
        "rows": rows,
        "update_share_used_for_extrapolation": U_SHARE,
        "scope": "ONE LANE with the box to itself. Three lanes at 4 threads "
                 "each want 12 cores and will not see this scaling — the "
                 "fleet-width answer needs its own measurement.",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n{'threads':>8} {'update s':>10} {'x vs 1':>8} {'implied loop':>13}")
    for r in rows:
        print(f"{r['threads']:>8} {r['update_seconds_min']:>10.2f} "
              f"{r['speedup_vs_1_thread']:>8.2f} "
              f"{r['implied_full_loop_speedup']:>13.2f}")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""How does the PPO UPDATE scale with `torch_threads` and MINIBATCH SIZE?

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
  * Every cell updates a FRESH DEEP COPY of the same agent over the SAME
    episodes. Otherwise the second cell would be timing an agent the first had
    already stepped, on data whose advantages had shifted.

TWO LEVERS, AND THEY ARE NOT THE SAME KIND OF THING:
  * `torch_threads` is FREE. It changes float reduction order, so an update is
    not bit-identical across thread counts, but it is distributionally the same
    update and needs no pre-registration to adopt.
  * `minibatches` CHANGES LEARNING. The shipped config runs 4 epochs x 120
    minibatches on a 30,720-step batch: 480 optimizer steps on 256 ROWS EACH,
    which is very small for CPU, where per-op dispatch overhead dominates at
    that size. Fewer, larger minibatches should be markedly faster per update,
    but it is a different optimiser trajectory — different gradient noise, a
    different number of steps, a different effective learning rate per sample.
    MEASURING it is free; ADOPTING it needs its own pre-reg and its own credit
    line. This script measures and says so. It recommends nothing.

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
    ap.add_argument("--compile", action="store_true",
                    help="also time the update with torch.compile on the actor "
                         "and critic. Compilation happens on first call, so a "
                         "WARMUP update runs untimed first — otherwise this "
                         "would be timing the compiler.")
    ap.add_argument("--minibatches", default=None,
                    help="comma-separated minibatch COUNTS, swept at the "
                         "fastest thread count found. Changing this changes "
                         "LEARNING, not just speed.")
    ap.add_argument("--cross", action="store_true",
                    help="cross threads x minibatches at both ends instead of "
                         "sweeping them independently. THEY INTERACT: at the "
                         "shipped 256-row minibatch, threading overhead per op "
                         "can exceed the gain, so threads look useless — but "
                         "that is a statement about the SHAPE, not about "
                         "threading, and a 3,840-row minibatch may thread fine. "
                         "Sweeping them separately would conclude that neither "
                         "lever works while their combination does.")
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

    # --- minibatch sweep, at the fastest thread count found above -----------
    mb_rows = []
    if args.minibatches:
        best_t = min(rows, key=lambda r: r["update_seconds_min"])["threads"]
        torch.set_num_threads(best_t)
        shipped = int(cfg.agent["minibatches"])
        print(f"minibatch sweep at threads={best_t} "
              f"(shipped value is {shipped})", flush=True)
        mbs = [int(x) for x in args.minibatches.split(",")]
        # THE CROSS. Threads and minibatch size are not independent: a
        # 256-row minibatch is too small for threading to pay for its own
        # synchronisation, so threads measured at the shipped shape say
        # nothing about threads at a 3,840-row shape.
        cells = ([(m, t) for m in mbs
                  for t in [int(x) for x in args.threads.split(",")]]
                 if args.cross else [(m, best_t) for m in mbs])
        for m, t_n in cells:
            torch.set_num_threads(t_n)
            times = []
            for _ in range(args.repeats):
                a = copy.deepcopy(agent)
                a.buffer = None
                a.minibatches = m
                ds = EpisodeDataset()
                for ep in episodes:
                    ds.append(ep)
                t = time.perf_counter()
                a.update_episodes(ds.drain(), steps_seen=0)
                times.append(time.perf_counter() - t)
            mb_rows.append({"minibatches": m, "threads": t_n,
                            "rows_per_minibatch": batch // m,
                            "optimizer_steps_per_update":
                                int(cfg.agent["epochs"]) * m,
                            "update_seconds_min": min(times),
                            "is_shipped_value": m == shipped})
            print(f"  minibatches={m:>4} ({batch // m:>5} rows/mb) "
                  f"threads={t_n:>2}  update {min(times):6.2f}s", flush=True)

    # --- torch.compile, at the fastest thread count --------------------------
    # The update is 65-85% of training wall clock now, so this is the highest
    # -value untested lever on the whole path. It is also the one most likely
    # to do nothing on CPU, which is why it is measured rather than adopted.
    compile_row = None
    if args.compile:
        best_t = min(rows, key=lambda r: r["update_seconds_min"])["threads"]
        torch.set_num_threads(best_t)
        try:
            # The PPO update calls backward more than once per minibatch (the
            # aux opponent-action head carries its own clipped grad path), and
            # inductor's donated-buffer optimisation requires a single
            # backward with retain_graph=False. Disabling it is the documented
            # escape and is what the error message itself names; it costs some
            # memory reuse, not correctness.
            import torch._functorch.config as _fc
            _fc.donated_buffer = False
            # ONE agent copy for this whole cell, unlike the eager rows.
            # A compiled module is bound to the parameters it was compiled
            # against, so handing it to a fresh deep copy leaves the optimiser
            # holding different tensors than the graph writes gradients into —
            # which surfaces as "stack expects a non-empty TensorList" on the
            # second update, not as a wrong number. Compute per update depends
            # on SHAPES, not parameter values, so timing on an agent that has
            # already been stepped is sound; it just is not the same object
            # discipline the eager rows use, and that is recorded below.
            a = copy.deepcopy(agent)
            a.buffer = None
            a.actor = torch.compile(a.actor)
            a.critic = torch.compile(a.critic)
            times = []
            for i in range(args.repeats + 1):     # +1: the first is WARMUP
                ds = EpisodeDataset()
                for ep in episodes:
                    ds.append(ep)
                t = time.perf_counter()
                a.update_episodes(ds.drain(), steps_seen=0)
                dt = time.perf_counter() - t
                if i:
                    times.append(dt)
                else:
                    print(f"  compile warmup (includes compilation): {dt:.1f}s",
                          flush=True)
            compile_row = {"threads": best_t, "update_seconds_min": min(times),
                           "update_seconds_all": times,
                           "note": "timed on ONE agent copy across repeats "
                                   "(a compiled module is bound to the "
                                   "parameters it was compiled against); the "
                                   "eager rows use a fresh copy each time"}
            print(f"  torch.compile threads={best_t}  update "
                  f"{min(times):6.2f}s", flush=True)
        except Exception as exc:            # noqa: BLE001 - a failure IS the result
            compile_row = {"threads": best_t, "error": f"{type(exc).__name__}: {exc}"}
            print(f"  torch.compile FAILED: {type(exc).__name__}: {exc}", flush=True)

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
        "minibatch_rows": mb_rows,
        "compile_row": compile_row,
        "minibatch_caveat": (
            "minibatches CHANGES LEARNING — a different optimiser trajectory, "
            "different gradient noise, a different number of steps. These are "
            "SPEED numbers only. Adopting a different value needs its own "
            "pre-reg and its own credit line; nothing here recommends one."),
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
    if compile_row and "update_seconds_min" in compile_row:
        t1 = min(r["update_seconds_min"] for r in rows
                 if r["threads"] == compile_row["threads"])
        print(f"\ntorch.compile: {compile_row['update_seconds_min']:.2f}s vs "
              f"{t1:.2f}s eager at the same thread count -> "
              f"{t1 / compile_row['update_seconds_min']:.2f}x")
    if mb_rows:
        b = next((r for r in mb_rows if r["is_shipped_value"]
                  and r["threads"] == 1), None) or \
            next((r for r in mb_rows if r["is_shipped_value"]), None)
        print(f"\n{'minibatches':>12} {'rows/mb':>9} {'thr':>4} "
              f"{'opt steps':>10} {'update s':>10} {'x':>6}")
        for r in mb_rows:
            x = (b["update_seconds_min"] / r["update_seconds_min"]) if b else 0.0
            print(f"{r['minibatches']:>12} {r['rows_per_minibatch']:>9} "
                  f"{r['threads']:>4} {r['optimizer_steps_per_update']:>10} "
                  f"{r['update_seconds_min']:>10.2f} {x:>6.2f}"
                  + ("  <- shipped" if r["is_shipped_value"] else ""))
        print("\nSPEED ONLY. minibatches changes the optimiser trajectory; "
              "adopting a value needs its own pre-reg.")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

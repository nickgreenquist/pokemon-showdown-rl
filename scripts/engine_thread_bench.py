#!/usr/bin/env python
"""How does the PPO UPDATE scale with `torch_threads` and MINIBATCH SIZE?

WHY THIS IS THE QUESTION NOW. Before the collector port, collection was 75% of
training wall clock and the update 25%, so how fast the update ran barely
mattered. After the port those invert: the update is ~65% of wall
(results/engine_a1/update_share.json, three lanes each side, both 3-wide), and
both configs still ship `torch_threads: 1` on a 14-core box where a 3-lane
engine fleet uses about 3 cores.

WHICH UPDATE THIS TIMES, AND WHY THAT MATTERS. `update_episodes()`, the ASYNC
path — the one the engine collector actually calls. It is NOT the same function
as `update()`, which the 2026-08-31 MPS bench timed at 12.002 s on a quiet box
(docs/landmines.md). `update_episodes` drops three full-batch forwards over
30,720 rows that `update()` performs: the second critic pass over `next_obs`,
and the `old_logp` recompute (rl/agents/ppo.py:1126-1145 states both). That
gap, not a faster box, is why numbers here land well under 12 s — and it means
the banked **0.85x at 6 threads is a fact about `update()` and does not
transfer here unexamined**. This script prints its own absolutes so the two
instruments can be tied by a shared point rather than subtracted blind.

EACH CELL RUNS IN ITS OWN PROCESS, and that is not fastidiousness.
`torch.set_num_threads(n)` cannot resize an OpenMP runtime that already sized
itself to the machine at import — rl/train.py:396-397 says so in its own
comment. A single process sweeping thread counts would therefore measure
`set_num_threads` against a fixed, possibly oversubscribed pool, and every cell
would inherit the same defect. So the parent collects ONE batch of real
episodes, writes it once, and each cell is a child launched with
OMP_NUM_THREADS / MKL_NUM_THREADS / VECLIB_MAXIMUM_THREADS set in its
environment. `torch.__config__.parallel_info()` is recorded per cell as
provenance.

TWO LEVERS, NOT THE SAME KIND OF THING:
  * `torch_threads` is FREE. Reduction order changes, the update does not.
  * `minibatches` CHANGES LEARNING. The shipped recipe is 4 epochs x 120
    minibatches on a 30,720-step batch: 480 optimizer steps of 256 ROWS.
    Fewer, larger minibatches may be faster per update, but it is a different
    optimiser trajectory. MEASURING is free; ADOPTING needs its own pre-reg and
    its own credit line. This script recommends nothing.

THEY INTERACT, which is why --cross exists. If synchronisation is what makes
threads unhelpful, the penalty scales with the NUMBER of parallel regions, i.e.
with minibatch COUNT, and should nearly vanish at `minibatches: 8`. If instead
it is heterogeneous cores (10 P + 4 E, no QoS pinning, a static parallel region
running at its slowest thread's speed), the penalty persists at every minibatch
size and the T-curve is FLAT across that axis. Those two predictions differ,
and the crossed table tells them apart.

    python scripts/engine_thread_bench.py runs/<run>/ckpt_012000008.pt \\
        --threads 1,2,4,6 --minibatches 120,30,8 --cross
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import pickle
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def _child(argv) -> int:
    """One cell, in its own process, with the thread env already set."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--episodes-file", required=True)
    ap.add_argument("--threads", type=int, required=True)
    ap.add_argument("--minibatches", type=int, default=0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--compile", action="store_true")
    a = ap.parse_args(argv)

    import copy
    import torch
    from engine_a1a import build_agent
    from rl.buffers.episode import EpisodeDataset

    torch.set_num_threads(a.threads)
    agent, cfg = build_agent(pathlib.Path(a.checkpoint))
    with open(a.episodes_file, "rb") as fh:
        episodes = pickle.load(fh)

    if a.compile:
        import torch._functorch.config as _fc
        # The PPO update calls backward more than once per minibatch (the aux
        # opponent-action head carries its own clipped grad path), and
        # inductor's donated-buffer optimisation requires a single backward.
        _fc.donated_buffer = False

    def one(mb: int, compiled: bool):
        # A compiled module is bound to the parameters it was compiled
        # against, so the compiled cell reuses ONE agent across repeats while
        # eager cells get a fresh copy each time. Compute per update depends on
        # shapes, not parameter values, so this is sound — it is just a
        # different object discipline, and it is recorded.
        times = []
        a_ = None
        for i in range(a.repeats + (1 if compiled else 0)):
            if a_ is None or not compiled:
                a_ = copy.deepcopy(agent)
                a_.buffer = None
                if mb:
                    a_.minibatches = mb
                if compiled:
                    a_.actor = torch.compile(a_.actor)
                    a_.critic = torch.compile(a_.critic)
            ds = EpisodeDataset()
            for ep in episodes:
                ds.append(ep)
            t = time.perf_counter()
            a_.update_episodes(ds.drain(), steps_seen=0)
            dt = time.perf_counter() - t
            if compiled and i == 0:
                continue                      # warmup: this one IS the compiler
            times.append(dt)
        return times

    try:
        times = one(a.minibatches, a.compile)
        out = {"ok": True, "threads": a.threads,
               "minibatches": a.minibatches or int(cfg.agent["minibatches"]),
               "update_seconds_min": min(times), "update_seconds_all": times,
               "torch_num_threads": torch.get_num_threads(),
               "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
               "parallel_info": torch.__config__.parallel_info()}
    except Exception as exc:                  # noqa: BLE001 - a failure IS a result
        out = {"ok": False, "threads": a.threads,
               "minibatches": a.minibatches,
               "error": f"{type(exc).__name__}: {exc}"}
    print("@@RESULT@@" + json.dumps(out))
    return 0


def main(argv=None) -> int:
    if "--child" in (argv if argv is not None else sys.argv[1:]):
        return _child(argv if argv is not None else sys.argv[1:])

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", type=pathlib.Path)
    ap.add_argument("--threads", default="1,2,4,6")
    ap.add_argument("--minibatches", default=None)
    ap.add_argument("--cross", action="store_true")
    ap.add_argument("--compile", action="store_true")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--k", type=int, default=64)
    ap.add_argument("--team-bank", default="data/engine/teams_a1_5000000.bin")
    ap.add_argument("--seed", type=int, default=7731)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/thread_bench.json"))
    args = ap.parse_args(argv)

    from engine_a1a import build_agent
    from rl.envs.engine_collector import EngineCollector
    from rl.selfplay.pool import SnapshotPool

    agent, cfg = build_agent(args.checkpoint)
    batch = int(cfg.agent["rollout_steps"]) * int(cfg.num_envs)
    shipped_mb = int(cfg.agent["minibatches"])
    print(f"batch = {cfg.agent['rollout_steps']} x {cfg.num_envs} = {batch:,} "
          f"steps/update; shipped minibatches {shipped_mb} "
          f"({batch // shipped_mb} rows each), epochs {cfg.agent['epochs']}",
          flush=True)

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
    collect_s = time.perf_counter() - t0
    print(f"  {len(episodes)} episodes, {steps:,} steps in {collect_s:.1f}s "
          f"({steps / collect_s:,.0f} steps/s collection at k={args.k})",
          flush=True)

    work = args.out.parent / "thread_bench_episodes.pkl"
    work.parent.mkdir(parents=True, exist_ok=True)
    with open(work, "wb") as fh:
        pickle.dump(episodes, fh)

    threads = [int(x) for x in args.threads.split(",")]
    mbs = [int(x) for x in args.minibatches.split(",")] if args.minibatches else []
    cells = [(t, 0) for t in threads]
    if mbs:
        cells += ([(t, m) for m in mbs for t in threads] if args.cross
                  else [(threads[0], m) for m in mbs])
    seen, ordered = set(), []
    for c in cells:
        key = (c[0], c[1] or shipped_mb)
        if key not in seen:
            seen.add(key)
            ordered.append(c)

    rows = []
    for t_n, mb in ordered:
        env = dict(os.environ)
        # SET AT LAUNCH, not with set_num_threads: the OpenMP runtime sizes
        # itself before any Python in the child can run.
        for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS"):
            env[var] = str(t_n)
        cmd = [sys.executable, __file__, "--child",
               "--checkpoint", str(args.checkpoint),
               "--episodes-file", str(work), "--threads", str(t_n),
               "--repeats", str(args.repeats)]
        if mb:
            cmd += ["--minibatches", str(mb)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        if not line:
            rows.append({"ok": False, "threads": t_n, "minibatches": mb or shipped_mb,
                         "error": (r.stderr or r.stdout)[-400:]})
            print(f"  T={t_n:<2} mb={mb or shipped_mb:<4} FAILED", flush=True)
            continue
        row = json.loads(line[len("@@RESULT@@"):])
        rows.append(row)
        print(f"  T={row['threads']:<2} mb={row['minibatches']:<4} "
              f"({batch // row['minibatches']:>5} rows/mb)  "
              f"update {row['update_seconds_min']:6.2f}s", flush=True)

    compile_row = None
    if args.compile:
        env = dict(os.environ)
        for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS"):
            env[var] = "1"
        r = subprocess.run([sys.executable, __file__, "--child",
                            "--checkpoint", str(args.checkpoint),
                            "--episodes-file", str(work), "--threads", "1",
                            "--repeats", str(args.repeats), "--compile"],
                           capture_output=True, text=True, env=env)
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        compile_row = json.loads(line[len("@@RESULT@@"):]) if line else \
            {"ok": False, "error": (r.stderr or r.stdout)[-400:]}
        if compile_row.get("ok"):
            print(f"  torch.compile T=1  update "
                  f"{compile_row['update_seconds_min']:6.2f}s", flush=True)
        else:
            print(f"  torch.compile FAILED: {compile_row.get('error','')[:200]}",
                  flush=True)

    ok = [r for r in rows if r.get("ok")]
    ref = next((r for r in ok if r["threads"] == 1
                and r["minibatches"] == shipped_mb), None)
    for r in ok:
        if ref:
            r["x_vs_T1_shipped_mb"] = ref["update_seconds_min"] / r["update_seconds_min"]

    U_SHARE = 0.6513          # results/engine_a1/update_share.json, engine 3-wide
    for r in ok:
        if "x_vs_T1_shipped_mb" in r:
            f = 1.0 / r["x_vs_T1_shipped_mb"]
            r["implied_full_loop_speedup"] = 1.0 / ((1 - U_SHARE) + U_SHARE * f)

    out = {
        "question": "does the PPO update parallelise, and does minibatch size "
                    "change that, now that the update is ~65% of wall",
        "which_update": "update_episodes() — the ASYNC path the engine "
                        "collector calls. NOT update(), which the 2026-08-31 "
                        "bench timed at 12.002s; that function additionally "
                        "does a second critic pass over next_obs and an "
                        "old_logp recompute over 30,720 rows. The banked 0.85x "
                        "at 6 threads is a fact about update() and does not "
                        "transfer here unexamined.",
        "batch_steps": batch, "shipped_minibatches": shipped_mb,
        "episodes_in_batch": len(episodes),
        "collection_steps_per_sec_at_k": {str(args.k): steps / collect_s},
        "rows": rows, "compile_row": compile_row,
        "update_share_used_for_extrapolation": U_SHARE,
        "minibatch_caveat": "minibatches CHANGES LEARNING — a different "
                            "optimiser trajectory, different gradient noise, a "
                            "different number of steps. SPEED numbers only; "
                            "adopting one needs its own pre-reg.",
        "scope": "ONE LANE with the box to itself. Three lanes at 4 threads "
                 "each want 12 cores and will not see this scaling.",
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    work.unlink(missing_ok=True)

    print(f"\n{'T':>3} {'minibatches':>12} {'rows/mb':>9} {'update s':>10} "
          f"{'x':>7} {'implied loop':>13}")
    for r in ok:
        print(f"{r['threads']:>3} {r['minibatches']:>12} "
              f"{batch // r['minibatches']:>9} "
              f"{r['update_seconds_min']:>10.2f} "
              f"{r.get('x_vs_T1_shipped_mb', float('nan')):>7.2f} "
              f"{r.get('implied_full_loop_speedup', float('nan')):>13.2f}")
    print("\nx and implied-loop are against T=1 at the SHIPPED minibatch count. "
          "Rows at other minibatch counts are SPEED ONLY — that lever changes "
          "learning and adopting it needs its own pre-reg.")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

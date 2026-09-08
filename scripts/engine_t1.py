#!/usr/bin/env python
"""Gate T-1 — throughput of the engine collector (plan §9).

CLAUDE.md's quoting rule applies to every number this prints: a throughput
number is meaningless without its WIDTH and its SCOPE, so every row carries the
trunk width and says COLLECTION-ONLY or FULL-LOOP. `scripts/showdown_throughput.py`
overstates by ~7x at [64,64] precisely because that discipline was missing once.

Three legs, from plan §9:

    a  engine-only battles/s, one core, no encoder and no network
       band: >= 20,000 battles/s
    b  COLLECTION-ONLY learner steps/s at K in {32, 64, 128, 256, 512}, the
       entity trunk at the 100M `trunk_kwargs`, snapshot-pool opponent batched
       by member                        band: >= 25,000 steps/s at K=256
    c  FULL-LOOP `time/realized_steps_per_sec` on a 12M engine-mode config,
       with the update's share of wall printed
                                        band: >= 2,000 steps/s realized

If (c) < 1,500: PROFILE. The learner or the Python-side batching is the bound,
and the plan's §0 numbers get corrected in place — they are not defended.

Leg (b)'s shape is what T-1 exists to measure, not a formality: with
`latest_prob 0.8` and 20 pool members at K=256 the latest member sees ~200 rows
and the other 19 average ~3, which lands in the batch-2..4 GEMV->GEMM anomaly
THROUGHPUT_SPEC §1a measured (81 us/sample at B=2 against 19 at B=1). The
mitigation, if it bites, is K=512 or batch-1 servicing for tiny groups — decided
by this measurement, not before it.

    python scripts/engine_t1.py --leg a --bank data/engine/teams_*.bin
    python scripts/engine_t1.py --leg b --bank data/engine/teams_*.bin
    python scripts/engine_t1.py --leg c --config configs/<engine 12m>.yaml

REFUSES TO RUN ON A BUSY BOX. A throughput window that straddles other work
invents records (CLAUDE.md's landmine list, and R2's own disclosure). `--force`
records `contended: true`, which makes the number unquotable rather than clean.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from engine_d1 import check_box  # the same idle-box guard  # noqa: E402

# The 100M recipe's trunk, verbatim from configs/showdown_sp_100m.yaml:562-571.
# T-1 quotes this width with every number.
TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)
HIDDEN_SIZES = [512, 512]
K_GRID = (32, 64, 128, 256, 512)
BANDS = {"a_battles_per_sec": 20_000, "b_steps_per_sec_at_256": 25_000,
         "c_realized_steps_per_sec": 2_000, "c_profile_below": 1_500}


def leg_a(bank: pathlib.Path, seed: int, battles: int = 20_000) -> dict:
    """Engine only: no encoder, no policy, no Python in the loop. The ceiling
    everything else is measured against."""
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    _h, payload = read_bank(bank)
    env = pkmn_gen1.BatchEnv(1, seed, tables, payload, "p1")
    env.scripted_series(200, "random", "random")  # warm the allocator
    t0 = time.perf_counter()
    rows = env.scripted_series(battles, "random", "random")
    wall = time.perf_counter() - t0
    turns = np.asarray(rows["turns"], dtype=np.float64)
    return {
        "scope": "ENGINE-ONLY (no encoder, no policy, no network)",
        "battles": battles,
        "wall_seconds": wall,
        "battles_per_sec": battles / wall,
        "mean_turns": float(turns.mean()),
        "band": BANDS["a_battles_per_sec"],
        "pass": battles / wall >= BANDS["a_battles_per_sec"],
    }


def leg_b(bank: pathlib.Path, seed: int, steps: int = 400, pool_size: int = 20) -> dict:
    """COLLECTION-ONLY: engine + encoder + the learner's forward + the pool
    opponent's forwards. No update, no eval, no checkpointing.

    A full pool is built (`pool_size` members at `latest_prob` 0.8) because the
    by-member batching is the thing under test; measuring against a one-member
    pool would report a number the real recipe never sees.
    """
    import torch

    from rl.agents.ppo import PPOAgent
    from rl.envs.engine_collector import EngineCollector
    from rl.envs.showdown import fake_spaces
    from rl.selfplay.pool import SnapshotPool

    torch.set_num_threads(1)  # the repo's collection setting; quoted with the number
    obs_space, act_space = fake_spaces()

    def agent():
        return PPOAgent(
            obs_space, act_space, num_envs=1, device="cpu", lr=2.5e-4, gamma=1.0,
            gae_lambda=0.95, rollout_steps=32, epochs=1, minibatches=1, clip_eps=0.2,
            entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
            hidden_sizes=HIDDEN_SIZES, trunk="entity_deepsets",
            trunk_kwargs=TRUNK_KWARGS,
        )

    learner = agent()
    pool = SnapshotPool(pool_size=pool_size, latest_prob=0.8)
    for _ in range(pool_size):
        pool.push(agent())

    rows = {}
    for k in K_GRID:
        c = EngineCollector(learner.act_logp, pool, seed=seed, k=k, team_bank=bank)
        c.start(n_battles=10**9)
        for _ in range(20):  # warm-up: the first polls allocate
            c.poll()
        before, t0 = c.seam.requests, time.perf_counter()
        for _ in range(steps):
            c.poll()
        wall = time.perf_counter() - t0
        served = c.seam.requests - before
        rows[k] = {
            "learner_steps": served,
            "wall_seconds": wall,
            "steps_per_sec": served / wall,
            "polls": steps,
            "inference_share": c.seam.inference_seconds / max(wall, 1e-9),
            "opponent_inference_share": c.opponent_inference_seconds / max(wall, 1e-9),
            "episodes_finished": c.episodes_finished,
        }
        print(f"  K={k}: {rows[k]['steps_per_sec']:.0f} steps/s", file=sys.stderr)
    at256 = rows.get(256, {}).get("steps_per_sec", 0.0)
    return {
        "scope": f"COLLECTION-ONLY, entity trunk {TRUNK_KWARGS}, hidden {HIDDEN_SIZES}, "
                 f"pool_size {pool_size} latest_prob 0.8, torch_threads 1",
        "by_k": rows,
        "band": BANDS["b_steps_per_sec_at_256"],
        "pass": at256 >= BANDS["b_steps_per_sec_at_256"],
    }


def leg_c(config: pathlib.Path, run_dir: pathlib.Path) -> dict:
    """FULL-LOOP: the real `rl.train` on an engine-mode config, read back out of
    the run's own history. Nothing is re-derived here — `time/
    realized_steps_per_sec` is the series F-16 added precisely so a throughput
    claim is not a poll-cadence artifact, and it is the one quoted.

    Run the training lane yourself (job ownership is by DURATION x KIND —
    CLAUDE.md rule 4 — and a 12M engine lane is a training job), then point this
    at its run dir.
    """
    import csv
    import subprocess

    hist = run_dir / "history.csv"
    if not hist.exists():
        subprocess.run(
            [sys.executable, "scripts/extract_history.py", str(run_dir)], check=True
        )
    with open(hist) as fh:
        rows = list(csv.DictReader(fh))

    def series(key):
        return [float(r[key]) for r in rows if r.get(key) not in (None, "")]

    realized = series("time/realized_steps_per_sec")
    if not realized:
        raise SystemExit(
            f"{hist} has no time/realized_steps_per_sec — that is the only series "
            "T-1 (c) quotes; time/steps_per_sec is the poll-cadence estimator and "
            "overstates by ~57%"
        )
    # The first window straddles startup; drop it, the way R2's conforming-window
    # rule requires.
    conforming = realized[1:] or realized
    collect = series("time/collect_sec")
    update = series("time/update_sec")
    median = statistics.median(conforming)
    return {
        "scope": f"FULL-LOOP from {run_dir}/history.csv (config {config.name})",
        "config": str(config),
        "windows": len(conforming),
        "realized_steps_per_sec_median": median,
        "realized_steps_per_sec_min": min(conforming),
        "realized_steps_per_sec_max": max(conforming),
        "update_share_of_wall": (
            sum(update) / max(sum(update) + sum(collect), 1e-9) if update else None
        ),
        "band": BANDS["c_realized_steps_per_sec"],
        "pass": median >= BANDS["c_realized_steps_per_sec"],
        "action": (
            "PROFILE: the learner or the Python-side batching is the bound, and "
            "the plan's §0 numbers get corrected in place"
            if median < BANDS["c_profile_below"] else None
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--leg", required=True, choices=("a", "b", "c"))
    ap.add_argument("--bank", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path)
    ap.add_argument("--run-dir", type=pathlib.Path)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("results/t1"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    contended = check_box("engine", args.force, gate="T-1")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.leg == "c":
        if not (args.config and args.run_dir):
            raise SystemExit("leg c needs --config and --run-dir")
        result = leg_c(args.config, args.run_dir)
    else:
        if args.bank is None:
            raise SystemExit(f"leg {args.leg} needs --bank")
        result = (leg_a if args.leg == "a" else leg_b)(args.bank, args.seed)
    result["contended"] = contended
    result["measured_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (args.out / f"leg_{args.leg}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"T-1 leg {args.leg}: {'PASS' if result['pass'] else 'FAIL'}"
          + (" (CONTENDED — not quotable)" if contended else ""))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

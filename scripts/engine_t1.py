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
    d  FLEET WIDTH — k lanes at once, which is the only width the gen-1
       question is ever asked at.       band: >= 2.5x the Node 3-wide basis,
                                        <= 2.0 cores/lane, and ZERO Node cores

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
    python scripts/engine_t1.py --leg d --run-dir runs/a --run-dir runs/b --run-dir runs/c

WHY LEG (d) EXISTS AT ALL. Legs (a)-(c) are SOLO numbers, and a solo throughput
number is exactly the mistake `scripts/showdown_throughput.py` made (~7x
overstatement at [64,64], and the repo now requires width and scope with every
quote). The gen-1 question is never "how fast is one lane" — it is "how many
lanes does this box hold at what rate", because the whole case for the port is
the MEASURED fact that 56% of a lane's CPU is the Node simulator
(docs/prior_work/THROUGHPUT_SPEC.md, "MEASURED BOX SIZING", time-averaged over
900 s at 3-wide; a single `ps` snapshot read 60% and is phase-dependent junk).
That share is what the port deletes. Leg (d) is the only leg that can see it,
so it is the one whose number may be quoted in a sizing claim; (a)-(c) are
instrument reads on the way there.

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
         "c_realized_steps_per_sec": 2_000, "c_profile_below": 1_500,
         "d_credited_x": 2.5, "d_short_x": 1.5,
         "d_cores_per_lane": 2.0}

# The Node path's own fleet-width numbers, MEASURED, never projected. Leg (d)
# compares against these and against nothing else.
#   rate: the gen-1 Stage-2 async acceptance fleet's REALIZED per-lane rate at
#     3-wide (12M / wall), SESSION_LOGS 2026-09-01: 573.5 / 574.1 / 574.6.
#     Realized, not the sps estimator, which overstates the async loop by ~57%.
#   cores: docs/prior_work/THROUGHPUT_SPEC.md "MEASURED BOX SIZING" (2026-09-06),
#     time-averaged from cumulative CPU-time deltas over 900 s on the gen-4
#     fleet at 3-wide: 0.85 python + 1.08 node = 1.93 cores/lane, Node 56%.
#     Gen 4, so the CORES basis is cross-generation: it is quoted as the SHARE
#     the port deletes, never as a gen-1 per-lane budget.
NODE_BASIS = {
    "per_lane_realized_steps_per_sec": 574.1,
    "per_lane_realized_source": "gen-1 async acceptance fleet, 3-wide, 12M/wall",
    "cores_per_lane_total": 1.93,
    "cores_per_lane_python": 0.85,
    "cores_per_lane_node": 1.08,
    "node_share_of_fleet_cpu": 0.56,
    "cores_source": "THROUGHPUT_SPEC.md MEASURED BOX SIZING, gen-4 3-wide, 900 s time-averaged",
    "width": 3,
}
# The spec's method, and the reason it is the method: sampled during collection
# the split reads python 204% / node 306%; sampled during the update, 297% / 28%.
# Only a cumulative-CPU-time delta over a long window is immune to that.
WINDOW_SEC = 900


def leg_a(bank: pathlib.Path, seed: int, battles: int = 20_000) -> dict:
    """Engine only: no encoder, no policy, no Python in the loop. The ceiling
    everything else is measured against."""
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    _h, payload = read_bank(bank)
    env = pkmn_gen1.BatchEnv(1, seed, tables, payload, "p1")
    env.scripted_series(200, 0, "random", "random")  # warm the allocator
    t0 = time.perf_counter()
    # offset 200: measure battles the warm-up did not already play
    rows = env.scripted_series(battles, 200, "random", "random")
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
        empty = 0
        for _ in range(steps):
            if not c.poll():
                empty += 1
        wall = time.perf_counter() - t0
        served = c.seam.requests - before
        rows[k] = {
            # The share of polls that finished no battle. It matters because
            # `_async_loop` sleeps `collector.idle_sleep` after such a poll:
            # this leg drives poll() bare, so a nonzero idle_sleep would make
            # the leg's number unreachable by a real lane. EngineCollector sets
            # it to 0, and this row is the evidence that the two agree.
            "empty_poll_fraction": empty / steps,
            "idle_sleep": float(getattr(c, "idle_sleep", 0.02)),
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
    # A leg that measured a cadence the training loop cannot reproduce is not a
    # measurement of the training loop. Refuse rather than publish it.
    if any(r["idle_sleep"] and r["empty_poll_fraction"] for r in rows.values()):
        raise SystemExit(
            "this leg drives poll() with no idle sleep, but the collector "
            "declares idle_sleep > 0 and some polls returned nothing — the "
            "numbers would not be reachable by `_async_loop`"
        )
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


def _cpu_seconds(pid: int) -> float | None:
    """Cumulative CPU seconds for one pid, from `ps -o time=` ([DD-]HH:MM:SS).

    Cumulative, never %CPU: `ps` %CPU is a LIFETIME average and a snapshot of it
    is phase-dependent (THROUGHPUT_SPEC's correction). Two of these, far apart,
    is the only honest instrument.
    """
    import subprocess

    out = subprocess.run(["ps", "-p", str(pid), "-o", "time="],
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return None
    days, _, rest = out.rpartition("-")
    parts = [float(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3:]
    return (float(days) if days else 0.0) * 86400 + h * 3600 + m * 60 + s


def _lane_pids(run_dirs: list[pathlib.Path]) -> dict[str, int]:
    """Map run-dir name -> the `rl.train` pid writing it. A lane we cannot find
    is FATAL, not skipped: a fleet-width number computed over the wrong number
    of lanes is the width error this leg exists to prevent."""
    import subprocess

    ps = subprocess.run(["ps", "-A", "-o", "pid=,command="],
                        capture_output=True, text=True).stdout.splitlines()
    found: dict[str, int] = {}
    for line in ps:
        line = line.strip()
        pid_s, _, cmd = line.partition(" ")
        if "rl.train" not in cmd:
            continue
        for d in run_dirs:
            if d.name in cmd and d.name not in found:
                found[d.name] = int(pid_s)
    return found


def _node_cpu_seconds() -> tuple[float, list[int]]:
    """Cumulative CPU seconds across every `pokemon-showdown` process on the box.

    The port's whole claim is that this term goes to ZERO for a training lane.
    Leg (d) measures it rather than assuming it — an engine lane that still
    pulls in a server (an in-loop eval, a stray import) has not deleted the
    share, it has only hidden it between polls."""
    import subprocess

    ps = subprocess.run(["ps", "-A", "-o", "pid=,command="],
                        capture_output=True, text=True).stdout.splitlines()
    pids = [int(l.strip().partition(" ")[0]) for l in ps
            if "pokemon-showdown" in l and "grep" not in l]
    return sum(_cpu_seconds(p) or 0.0 for p in pids), pids


def leg_d(run_dirs: list[pathlib.Path], window_sec: int = WINDOW_SEC) -> dict:
    """FLEET WIDTH: k engine lanes at once — rate AND cores, both time-averaged.

    Reports three things, because the port's case needs all three and a rate
    alone has misled this repo before:
      1. aggregate and per-lane REALIZED steps/s at width k, against the Node
         path's own realized 3-wide rate;
      2. cores/lane, time-averaged over `window_sec` from cumulative CPU-time
         deltas (the spec's method, not a snapshot);
      3. the Node share, which must be ZERO — that share is the thing the port
         claims to delete, and it is 56% on the Node path.

    Every number carries WIDTH and SCOPE, per CLAUDE.md's quoting rule.
    Bands mirror G8's three tiers (CREDITED / SHORT / STOP) because this is the
    same kind of read: an ops number on an instrument, not a lever.
    """
    import csv

    k = len(run_dirs)
    if k < 2:
        raise SystemExit("leg d is a FLEET-WIDTH read; give it >= 2 --run-dir "
                         "(a solo number is leg c, and quoting one as a fleet "
                         "number is the showdown_throughput.py mistake)")
    pids = _lane_pids(run_dirs)
    missing = [d.name for d in run_dirs if d.name not in pids]
    if missing:
        raise SystemExit(f"no live rl.train process for {missing} — leg d must "
                         f"measure all {k} lanes over ONE window, or not at all")

    def _eval_rows(d: pathlib.Path) -> int:
        """How many in-loop evals this lane has logged so far.

        An eval tick inside the window would show up as Node CPU and as a
        depressed lane rate, and G8's estimator excludes eval ticks for exactly
        that reason. We cannot exclude them from a CPU-time delta after the
        fact, so the window is declared NON-CONFORMING instead.
        """
        import csv
        hist = d / "history.csv"
        if not hist.exists():
            return -1
        with open(hist) as fh:
            return sum(1 for r in csv.DictReader(fh)
                       if r.get("eval/win_rate") not in (None, ""))

    def _ckpt_step(d: pathlib.Path):
        """Realized step from the lane's own latest checkpoint.

        A RUNNING lane has no history.csv — wandb is offline and
        extract_history.py only runs afterwards — so a fleet-width rate cannot
        come from history while the fleet is up. `checkpoint.pt` is written
        every SAVE_LATEST_EVERY_UPDATES updates (~123k steps at this recipe),
        which over a 900 s window is ~9 writes: plenty of resolution, and it is
        realized steps by definition rather than a poll-cadence estimator.
        """
        f = d / "checkpoint.pt"
        if not f.exists():
            return None
        try:
            import torch
            return torch.load(f, map_location="cpu", weights_only=False).get("step")
        except Exception:
            return None

    evals0 = {d.name: _eval_rows(d) for d in run_dirs}
    steps0 = {d.name: _ckpt_step(d) for d in run_dirs}
    t0 = time.time()
    cpu0 = {n: _cpu_seconds(p) for n, p in pids.items()}
    node0, node_pids = _node_cpu_seconds()
    time.sleep(window_sec)
    cpu1 = {n: _cpu_seconds(p) for n, p in pids.items()}
    node1, _ = _node_cpu_seconds()
    elapsed = time.time() - t0
    evals1 = {d.name: _eval_rows(d) for d in run_dirs}
    steps1 = {d.name: _ckpt_step(d) for d in run_dirs}
    eval_ticks = {n: evals1[n] - evals0[n] for n in evals0 if evals0[n] >= 0}
    ticked = {n: v for n, v in eval_ticks.items() if v > 0}

    if any(cpu1[n] is None for n in cpu1):
        raise SystemExit("a lane died inside the measurement window — the window "
                         "is void; re-run it (a partial window invents a record)")

    cores = {n: (cpu1[n] - cpu0[n]) / elapsed for n in cpu0}
    node_cores = (node1 - node0) / elapsed
    per_lane_cores = sum(cores.values()) / k

    # Rate over the SAME window, from each lane's own realized progress.
    rates: dict[str, float] = {}
    for d in run_dirs:
        a, b = steps0.get(d.name), steps1.get(d.name)
        if a is not None and b is not None and b > a:
            rates[d.name] = (b - a) / elapsed
    if len(rates) != k:
        # Fall back to history for a FINISHED fleet, where checkpoint.pt no
        # longer advances. A resumed lane splits the history and
        # extract_history.py hard-fails, so history_merged.csv is honoured too.
        for d in run_dirs:
            if d.name in rates:
                continue
            hist = d / "history.csv"
            if not hist.exists():
                hist = d / "history_merged.csv"
            if not hist.exists():
                raise SystemExit(
                    f"{d}: checkpoint.pt did not advance during the window and "
                    "there is no history to fall back on. If the lane is "
                    "RUNNING this means it made no progress in "
                    f"{elapsed:.0f}s — check for the alive-at-zero-CPU stall.")
            with open(hist) as fh:
                rows = list(csv.DictReader(fh))
            series = [float(r["time/realized_steps_per_sec"]) for r in rows
                      if r.get("time/realized_steps_per_sec") not in (None, "")]
            if not series:
                raise SystemExit(
                    f"{hist} has no time/realized_steps_per_sec — that is the "
                    "only series T-1 quotes; time/steps_per_sec is the "
                    "poll-cadence estimator and overstates the async loop by "
                    "~57%")
            rates[d.name] = statistics.median(series[1:] or series)

    per_lane_rate = statistics.median(rates.values())
    basis = NODE_BASIS["per_lane_realized_steps_per_sec"]
    speedup = per_lane_rate / basis

    if speedup >= BANDS["d_credited_x"]:
        tier, action = "CREDITED", None
    elif speedup >= BANDS["d_short_x"]:
        tier, action = "SHORT", (
            "above the Node path but below the plan's ~4.2x projection — name "
            "the gap's owner before any wall-clock or box-sizing claim quotes "
            "this number")
    else:
        tier, action = "STOP", (
            "the port does not buy fleet width; the throughput case for the "
            "switch is not made and plan §0's numbers get corrected in place")

    cores_ok = per_lane_cores <= BANDS["d_cores_per_lane"]
    node_ok = node_cores < 0.05           # a live server is a failure, not a rounding term
    return {
        "scope": (f"FULL-LOOP, FLEET WIDTH k={k}, entity trunk {TRUNK_KWARGS}, "
                  f"hidden {HIDDEN_SIZES}; time-averaged over {elapsed:.0f} s "
                  "from cumulative CPU-time deltas (NOT a ps snapshot)"),
        "width": k,
        "window_sec": elapsed,
        "eval_ticks_in_window": eval_ticks,
        "window_conforming": not ticked,
        "run_dirs": [str(d) for d in run_dirs],
        "per_lane_realized_steps_per_sec": rates,
        "per_lane_realized_median": per_lane_rate,
        "aggregate_realized_steps_per_sec": sum(rates.values()),
        "node_basis": NODE_BASIS,
        "speedup_vs_node_3wide": speedup,
        "cores_per_lane": cores,
        "cores_per_lane_mean": per_lane_cores,
        "node_cores_observed": node_cores,
        "node_pids_seen": node_pids,
        "node_share_deleted": NODE_BASIS["node_share_of_fleet_cpu"] if node_ok else None,
        "cores_per_lane_band": BANDS["d_cores_per_lane"],
        "tier": tier,
        "pass": tier == "CREDITED" and cores_ok and node_ok and not ticked,
        "action": (
            f"NON-CONFORMING WINDOW: an in-loop eval fired in {sorted(ticked)} "
            "during the measurement — eval ticks pull the Showdown server into "
            "a read whose whole point is that the server is gone. Re-measure "
            "between eval ticks (eval_every is 250k steps)."
            if ticked else action) if (action or ticked) else (
            None if (cores_ok and node_ok) else
            f"rate tier {tier} but cores/lane {per_lane_cores:.2f} "
            f"(band {BANDS['d_cores_per_lane']}) or Node cores "
            f"{node_cores:.2f} (band 0) — the share is not deleted"),
        "quoting_rule": (
            f"quote as: '{per_lane_rate:.0f} realized steps/s per lane at k={k}, "
            f"FULL-LOOP, entity trunk 512x512' — never without the width and "
            "never without FULL-LOOP"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--leg", required=True, choices=("a", "b", "c", "d"))
    ap.add_argument("--bank", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path)
    ap.add_argument("--run-dir", type=pathlib.Path, action="append", default=[],
                    help="leg c: one run dir. leg d: repeat once per lane.")
    ap.add_argument("--window-sec", type=int, default=WINDOW_SEC)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("results/t1"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    contended = check_box("fleet" if args.leg == "d" else "engine",
                          args.force, gate="T-1")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.leg == "c":
        if not (args.config and args.run_dir):
            raise SystemExit("leg c needs --config and --run-dir")
        if len(args.run_dir) != 1:
            raise SystemExit("leg c takes exactly one --run-dir (k lanes is leg d)")
        result = leg_c(args.config, args.run_dir[0])
    elif args.leg == "d":
        result = leg_d(args.run_dir, args.window_sec)
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

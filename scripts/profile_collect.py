"""THROUGHPUT_SPEC Stage 0 runner — experiments E1-E4 (D12b measurement evening).

    python scripts/profile_collect.py plan          # print the evening's sequence
    python scripts/profile_collect.py e1            # serialization proof (~10 min)
    python scripts/profile_collect.py e23           # reset-vs-step + sub-env split (~3 min)
    python scripts/profile_collect.py e4b           # in-flight sweep vs :8000 (~10 min)

Run with BOTH encoder env vars, the :8000 server up (simulator: 4), and an
otherwise IDLE box — these are timing measurements. Seed 99 (disposable) is
used throughout; runs are sequential so its username never collides.

ZERO rl/ changes: E2/E3 instrumentation is class/module-level monkeypatching
applied in-process before calling rl.train.main() — the production loop is
byte-identical when this script is not running (supersedes the spec's plan
of a POKEMON_RL_PROFILE block inside _vector_loop; same read, no seam).

Decision criteria live in docs/prior_work/THROUGHPUT_SPEC.md §1c:
  E1 flat in N -> serialization confirmed (Stage 2 is the whole answer).
  E2 reset > 20% of collect -> matchmaking is first-class; < 5% -> ignore.
  E3 race_get > 70% of sub-env step -> idle wait, concurrency converts 1:1;
     < 40% -> residual is CPU, halve the §5 ceiling.
  E4b read the SHAPE (the knee is the K to build for); absolute numbers only
     at --net entity (never [64,64] — the two prior misreads).
"""

import argparse
import functools
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

# Before ANY rl import (they happen inside the e-functions): the encoder
# flags are read at rl.envs.showdown import time, so setting them later is
# the silent-612-obs landmine. setdefault keeps explicit caller overrides.
os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
os.environ.setdefault("WANDB_MODE", "offline")

ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "configs" / "showdown_sp_struct12m.yaml"
WORKDIR = ROOT / "runs" / "profile"
SEED = 99  # the disposable seed (CLAUDE.md seed ledger)
ENV = {"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1",
       "WANDB_MODE": "offline"}


def _write_config(name: str, **overrides) -> Path:
    cfg = yaml.safe_load(BASE_CONFIG.read_text())
    cfg.update(overrides)
    cfg["run_name"] = name
    WORKDIR.mkdir(parents=True, exist_ok=True)
    out = WORKDIR / f"{name}.yaml"
    out.write_text(yaml.safe_dump(cfg))
    return out


def _steps_per_sec(run_name: str) -> float:
    import pandas as pd

    hist = ROOT / "runs" / run_name / "history.csv"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "extract_history.py"),
         str(ROOT / "runs" / run_name)],
        check=True, capture_output=True,
    )
    sps = pd.read_csv(hist)["time/steps_per_sec"].dropna()
    back_half = sps.iloc[len(sps) // 2:]
    return float(back_half.median())


def e1(total_steps: int) -> None:
    """Serialization proof: num_envs sweep, rollout_steps x num_envs held
    constant (1024 — the production 128 x 8) so update cadence doesn't move."""
    print(f"E1: num_envs sweep at {total_steps} steps each, product held at 1024")
    rows = []
    for n in (1, 2, 4, 8, 16):
        name = f"profile_e1_n{n}"
        cfg = _write_config(name, total_steps=total_steps, num_envs=n,
                            eval_every=10**9, checkpoint_every=10**9)
        cfg_yaml = yaml.safe_load(cfg.read_text())
        cfg_yaml["agent"]["rollout_steps"] = 1024 // n
        cfg.write_text(yaml.safe_dump(cfg_yaml))
        t0 = time.perf_counter()
        subprocess.run(
            [sys.executable, "-m", "rl.train", "--config", str(cfg),
             "--seed", str(SEED), "--run-name", name],
            check=True, cwd=ROOT, env={**os.environ, **ENV},
            capture_output=True,
        )
        wall = time.perf_counter() - t0
        sps = _steps_per_sec(name)
        rows.append((n, sps, wall))
        print(f"  num_envs {n:2d}: steps/s median(back half) {sps:7.1f}  wall {wall:6.1f}s")
    flat = max(r[1] for r in rows) / max(1e-9, min(r[1] for r in rows))
    print(f"E1 spread max/min = {flat:.2f}x -> {'FLAT (serialization confirmed)' if flat < 1.3 else 'RISES with N (server-side queueing; re-open servers ahead of async)'}")


class _Acc:
    def __init__(self):
        self.sec, self.calls = 0.0, 0

    def us_per(self) -> float:
        return self.sec / max(1, self.calls) * 1e6


def e23(total_steps: int) -> None:
    """One in-process instrumented run: E2 (reset vs step at the vector seam)
    + E3 (sub-env decomposition). Patches applied to library/module objects;
    rl/ source untouched."""
    import gymnasium as gym

    import rl.envs.showdown as shd
    import rl.train as train_mod
    from poke_env.environment import SinglesEnv
    from poke_env.environment.env import _AsyncQueue

    accs = {name: _Acc() for name in
            ("vec_step", "vec_reset", "embed", "mask", "opponent", "race_get")}

    def timed(acc, fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            t0 = time.perf_counter()
            out = fn(*a, **k)
            acc.sec += time.perf_counter() - t0
            acc.calls += 1
            return out
        return wrapper

    # E2 — the vector seam _vector_loop drives.
    gym.vector.SyncVectorEnv.step = timed(accs["vec_step"], gym.vector.SyncVectorEnv.step)
    gym.vector.SyncVectorEnv.reset = timed(accs["vec_reset"], gym.vector.SyncVectorEnv.reset)
    # E3 — sub-env decomposition. embed_battle is a module-level function;
    # every caller inside showdown.py resolves it through the module global.
    shd.embed_battle = timed(accs["embed"], shd.embed_battle)
    SinglesEnv.get_action_mask = staticmethod(
        timed(accs["mask"], SinglesEnv.get_action_mask))
    shd.PoolPlayer.choose_move = timed(accs["opponent"], shd.PoolPlayer.choose_move)
    _AsyncQueue.race_get = timed(accs["race_get"], _AsyncQueue.race_get)

    name = "profile_e23"
    cfg = _write_config(name, total_steps=total_steps,
                        eval_every=10**9, checkpoint_every=10**9)
    sys.argv = ["rl.train", "--config", str(cfg), "--seed", str(SEED),
                "--run-name", name]
    t0 = time.perf_counter()
    train_mod.main()
    wall = time.perf_counter() - t0

    a = accs
    num_envs = yaml.safe_load(cfg.read_text())["num_envs"]
    decisions = a["vec_step"].calls * num_envs
    print(f"\nE2/E3 report ({total_steps} steps, num_envs {num_envs}, wall {wall:.1f}s)")
    print(f"{'site':12s} {'total_s':>8s} {'calls':>8s} {'us/call':>9s}")
    for k in ("vec_step", "vec_reset", "embed", "mask", "opponent", "race_get"):
        print(f"{k:12s} {a[k].sec:8.2f} {a[k].calls:8d} {a[k].us_per():9.1f}")
    collect = a["vec_step"].sec + a["vec_reset"].sec
    reset_share = a["vec_reset"].sec / max(1e-9, collect)
    race_share = a["race_get"].sec / max(1e-9, a["vec_step"].sec)
    print(f"\nE2: reset share of collect = {reset_share:.3f} "
          f"({'first-class, pipeline battle creation' if reset_share > 0.20 else 'ignore' if reset_share < 0.05 else 'middle band — record'})")
    print(f"E3: race_get share of vec step = {race_share:.3f} "
          f"({'idle wait — concurrency converts 1:1' if race_share > 0.70 else 'CPU-bound residual — halve the ceiling' if race_share < 0.40 else 'middle band — record'})")
    print(f"    (race_get us/call is the per-DECISION idle wait at 1 in-flight "
          f"per env; decisions = {decisions})")


def e4b() -> None:
    """In-flight sweep against the running :8000 server, production entity
    net. Read the knee; that K is what Stage 2 builds for."""
    for k in (1, 8, 16, 32, 64):
        print(f"\n--- in-flight {k} ---", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "showdown_throughput.py"),
             "c", "--workers", "1", "--servers", "shared", "--in-flight", str(k),
             "--battles-per-worker", "64", "--net", "entity"],
            cwd=ROOT, env={**os.environ, **ENV},
        )


PLAN = """E1-E4 measurement evening (idle box, server on :8000, both env vars):
  1. python scripts/profile_collect.py e1     (~10 min, 5 sequential 30k runs)
  2. python scripts/profile_collect.py e23    (~3 min, one instrumented 8k run)
  3. E4a by hand: top -stats pid,cpu,command | grep node   at 1 lane of e1
     (node < 1.5 cores -> server has headroom; one server suffices)
  4. python scripts/profile_collect.py e4b    (~10 min, needs :8000 up)
Then fill THROUGHPUT_SPEC.md's E1-E4 decision branches and log the evening."""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("experiment", choices=["plan", "e1", "e23", "e4b"])
    ap.add_argument("--steps", type=int, default=None,
                    help="override steps (e1 default 30000, e23 default 8000)")
    args = ap.parse_args()
    if args.experiment == "plan":
        print(PLAN)
    elif args.experiment == "e1":
        e1(args.steps or 30000)
    elif args.experiment == "e23":
        e23(args.steps or 8000)
    else:
        e4b()


if __name__ == "__main__":
    main()

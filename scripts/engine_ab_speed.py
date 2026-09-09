#!/usr/bin/env python
"""THE HEAD-TO-HEAD SPEED A/B: train the same dose on Node, then on the engine.

WHY THIS REPLACES THE EARLIER NUMBER. The first "2.3x" compared an engine rate
measured today against a Node rate banked on 2026-09-01 — a different day, a
different box state, a different set of neighbours. That is not an A/B, it is
two measurements subtracted. This runs BOTH ARMS ON THIS BOX, BACK TO BACK, on
an idle machine, and reports WALL-CLOCK SECONDS TO THE SAME DOSE.

The headline is one number: how long does it take to train N steps the old way,
and how long the new way. Not per lane, not per step, not collection-only.

FAIRNESS IS BY CONSTRUCTION, NOT BY INSPECTION. Both configs are generated here
from ONE base dict; the ONLY difference is the `collector` block (and the run
name). Nothing else can drift, because nothing else is written twice.

    python scripts/engine_ab_speed.py --steps 1000000
    python scripts/engine_ab_speed.py --steps 1000000 --engine-k 8   # matched-K

TWO SETTINGS, AND THE DIFFERENCE MATTERS:
  * DEFAULT (--engine-k 256): production-vs-production. Each collector at the
    width you would actually train it at. This answers "how much faster is the
    new way".
  * --engine-k 8: matched concurrency, so the COLLECTOR is the only delta. This
    answers "how much of the speedup is the collector itself" and is the
    apples-to-apples control. Run both if you can; quote which one you mean.

EVALS ARE OFF in both arms (`eval_every` past the horizon). The locked eval
protocol stays on the Showdown server either way, so including it would add the
same constant to both arms and dilute the ratio while adding server variance.
This measures TRAINING throughput, which is the thing the port changes.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import time

import yaml

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
PY = "/opt/anaconda3/envs/pkmn-engine-port/bin/python"
BASE_CONFIG = pathlib.Path("configs/engine_a1.yaml")
BANK = "data/engine/teams_a1_5000000.bin"


def busy() -> list[str]:
    out = []
    for pat, what in ((r"rl\.train", "a training lane"),
                      (r"(^|/|[[:space:]])(cargo|maturin)[[:space:]]", "a build")):
        r = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True)
        if r.stdout.strip():
            out.append(what)
    return out


def server_up() -> bool:
    return bool(subprocess.run(["pgrep", "-f", "node pokemon-showdown start"],
                               capture_output=True, text=True).stdout.strip())


def start_server() -> None:
    if server_up():
        return
    subprocess.Popen(
        "cd %s/showdown && nohup node pokemon-showdown start --no-security "
        ">> %s/logs/showdown_server.log 2>&1 &" % (MAIN, MAIN),
        shell=True)
    for _ in range(120):
        time.sleep(1)
        if subprocess.run(["nc", "-z", "localhost", "8000"],
                          capture_output=True).returncode == 0:
            time.sleep(5)
            return
    raise SystemExit("server did not come up on 8000")


def stop_server() -> None:
    subprocess.run(["pkill", "-f", "node pokemon-showdown start"],
                   capture_output=True)
    time.sleep(3)


def build_config(base: dict, arm: str, steps: int, k: int, seed: int,
                 out: pathlib.Path) -> pathlib.Path:
    """Both arms from ONE base. The collector block is the only edit."""
    cfg = copy.deepcopy(base)
    cfg["total_steps"] = steps
    cfg["eval_every"] = steps * 10          # evals OFF, both arms alike
    cfg["eval_win_rate"] = False
    cfg["logger"] = "wandb"
    cfg["seed"] = seed
    cfg["run_name"] = f"ab_{arm}_s{seed}"
    cfg["checkpoint_every"] = steps * 10    # no ladder writes skewing either arm
    cfg.pop("env_kwargs", None) or None
    cfg["env_kwargs"] = {"opp_action": True}   # keep D25 on, as both recipes have it
    if arm == "node":
        cfg["collector"] = {"mode": "async", "concurrency": 8}
    else:
        cfg["collector"] = {"mode": "engine", "k": k,
                            "team_bank": BANK, "learner_seat": "p1",
                            "min_bank_pairs": 1_000_000}
    p = out / f"ab_{arm}.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return p


def run_arm(arm: str, cfg: pathlib.Path, log: pathlib.Path) -> dict:
    env = {"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"}
    import os
    e = dict(os.environ); e.update(env)
    t0 = time.time()
    with open(log, "w") as fh:
        rc = subprocess.run([PY, "-m", "rl.train", "--config", str(cfg)],
                            stdout=fh, stderr=subprocess.STDOUT, env=e).returncode
    return {"arm": arm, "wall_seconds": time.time() - t0, "rc": rc,
            "config": str(cfg), "log": str(log)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--steps", type=int, default=1_000_000)
    ap.add_argument("--engine-k", type=int, default=256)
    ap.add_argument("--seed", type=int, default=9301)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/ab_speed.json"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    b = busy()
    if b and not args.force:
        raise SystemExit(
            f"the box is busy ({'; '.join(b)}). This is a WALL-CLOCK "
            "measurement — anything else running makes both arms wrong and the "
            "ratio meaningless. Wait, or pass --force to record it as tainted.")

    base = yaml.safe_load(BASE_CONFIG.read_text())
    work = pathlib.Path("results/engine_a1/ab"); work.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    results = {}
    # NODE FIRST, with the server up. Engine second, server DOWN — the port's
    # whole claim is that it needs no server, so leaving one running would hand
    # the engine arm a neighbour it does not have in production.
    for arm in ("node", "engine"):
        for d in work.glob(f"../../../runs/ab_{arm}_s{args.seed}"):
            shutil.rmtree(d, ignore_errors=True)
        rd = pathlib.Path(f"runs/ab_{arm}_s{args.seed}")
        shutil.rmtree(rd, ignore_errors=True)
        cfg = build_config(base, arm, args.steps, args.engine_k, args.seed, work)
        if arm == "node":
            start_server()
        else:
            stop_server()
        print(f"--- arm {arm}: {args.steps:,} steps "
              f"({'async concurrency 8' if arm=='node' else f'engine k={args.engine_k}'})",
              flush=True)
        r = run_arm(arm, cfg, work / f"ab_{arm}.log")
        r["steps"] = args.steps
        r["steps_per_sec"] = args.steps / r["wall_seconds"] if r["wall_seconds"] else None
        results[arm] = r
        print(f"    {arm}: rc={r['rc']}  wall={r['wall_seconds']:.1f}s  "
              f"{r['steps_per_sec']:.0f} steps/s", flush=True)
        if r["rc"] != 0:
            print(f"    FAILED — see {r['log']}", flush=True)

    out = {
        "question": "wall-clock seconds to train the SAME dose, old way vs new way",
        "dose_steps": args.steps,
        "width": 1,
        "engine_k": args.engine_k,
        "matched_concurrency": args.engine_k == 8,
        "arms": results,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    n, e = results.get("node", {}), results.get("engine", {})
    if n.get("rc") == 0 and e.get("rc") == 0:
        out["speedup_wall_clock"] = n["wall_seconds"] / e["wall_seconds"]
        print(f"\nSPEEDUP (wall clock, same dose, same box, back to back): "
              f"{out['speedup_wall_clock']:.2f}x")
        print(f"  node   {n['wall_seconds']/60:.1f} min")
        print(f"  engine {e['wall_seconds']/60:.1f} min")
    out["disclosures"] = [
        f"ONE LANE each, width 1. This is not a fleet number.",
        f"engine k={args.engine_k}; "
        + ("MATCHED to the Node arm's concurrency, so the collector is the only "
           "delta" if args.engine_k == 8 else
           "the production setting, so this is old-way vs new-way, NOT a "
           "controlled test of the collector alone — run with --engine-k 8 for that"),
        "evals OFF in both arms; the locked protocol stays on the server either "
        "way, so including it would add the same constant to both and dilute "
        "the ratio",
        "back to back on one idle box, Node first with the server up, engine "
        "second with the server DOWN",
    ]
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

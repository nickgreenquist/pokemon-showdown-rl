#!/usr/bin/env python
"""MAX OUT the engine path: sweep (k, width, torch_threads) and find the wall.

THE QUESTION. "How much faster is the engine?" has a different answer depending
on how hard you push it, and every number this port has produced so far was
taken at ONE point in that space — k=8, width 3, torch_threads 1 — which was
chosen to match the banked Node arm for gate A-1, NOT to go fast. The maintainer
asked what the speedup is when the engine is MAXED OUT. That is a search, not a
measurement, so this searches.

WHAT MOVES, AND WHY EACH ONE MIGHT NOT HELP:
  * k — battles in flight inside one lane. Collection-only it looks huge
    (13.5k steps/s at k=32 up to 30.6k at k=512, results/t1/leg_b.json), but
    collection is only 34.9% of engine wall now, so Amdahl caps what k can buy
    at 1/0.651 = 1.54x. It also raises memory per lane, which is what limits
    width. FULL-LOOP k has never been measured; leg (b) is collection-only.
  * width — concurrent lanes. A lane is a SEED, not a shard: width raises total
    throughput, never the wall clock of a single run. Lanes contend for cores
    and memory, so per-lane rate is expected to fall.
  * torch_threads — both configs ship 1, while the update is 65% of wall on a
    14-core box. Threads and width are SUBSTITUTES for the same cores, so the
    best (width, threads) pair is a joint choice, not two independent ones.

METHOD. Each cell runs a SHORT real training run per lane and reads the loop's
own `time/realized_steps_per_sec` out of history.csv — the series F-16 added
precisely so a throughput claim is not a poll-cadence artifact. The first
window straddles startup and is dropped, as leg (c) does. Peak RSS is sampled
from `ps` while the cell runs, because memory is what actually stops you from
raising width and a cell that OOMs the box is not a faster configuration.

    python scripts/engine_maxout.py --grid quick
    python scripts/engine_maxout.py --k 8,64,256 --width 1,3 --threads 1,4
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import threading
import time

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

_spec = importlib.util.spec_from_file_location("ab_speed", HERE / "engine_ab_speed.py")
AB = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AB)


def peak_rss_watcher(stop: threading.Event, pids: list[int], out: dict) -> None:
    """Peak RSS across the cell's lanes, in GB. Sampled, not derived: the loop
    allocates the update's tensors in bursts and a single snapshot lands
    wherever it lands."""
    peak = 0.0
    while not stop.is_set():
        total = 0.0
        for pid in list(pids):
            r = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                               capture_output=True, text=True).stdout.strip()
            if r:
                total += float(r) / 1024 / 1024
        peak = max(peak, total)
        stop.wait(2.0)
    out["peak_rss_gb"] = round(peak, 3)


def realized(run_dir: pathlib.Path) -> float | None:
    import csv
    import statistics
    hist = run_dir / "history.csv"
    if not hist.exists():
        subprocess.run([AB.PY, "scripts/extract_history.py", str(run_dir)],
                       capture_output=True)
    if not hist.exists():
        return None
    vals = []
    with open(hist) as fh:
        for row in csv.DictReader(fh):
            v = row.get("time/realized_steps_per_sec")
            if v not in (None, ""):
                vals.append(float(v))
    vals = vals[1:]                       # drop the startup-straddling window
    return statistics.median(vals) if vals else None


def run_cell(base: dict, k: int, width: int, threads: int, steps: int,
             work: pathlib.Path, seed: int, path: str = "engine",
             bank: str = AB.BANK) -> dict:
    """One configuration, `width` lanes, on either collector.

    `k` means battles-in-flight on both paths — `collector.k` for the engine,
    `collector.concurrency` for the async Node collector. Naming them the same
    thing here is deliberate: the whole point of sweeping the Node path too is
    that maxing one side against a default-configured other side is not a
    comparison, and the levers have to line up to be swept together.
    """
    cfgs, rds, logs = [], [], []
    tag = "mx" if path == "engine" else "mn"
    for lane in range(width):
        cfg = copy.deepcopy(base)
        cfg["total_steps"] = steps
        cfg["eval_every"] = steps * 10
        cfg["eval_win_rate"] = False
        cfg["checkpoint_every"] = steps * 10
        cfg["logger"] = "wandb"
        cfg["torch_threads"] = threads
        cfg["seed"] = seed + lane
        cfg["run_name"] = f"{tag}_k{k}_w{width}_t{threads}_l{lane}"
        cfg["env_kwargs"] = {"opp_action": True,
                             "seat_tag": f"{tag}{k}w{width}t{threads}l{lane}"}
        if path == "engine":
            cfg["collector"] = {"mode": "engine", "k": k, "team_bank": bank,
                                "learner_seat": "p1", "min_bank_pairs": 1_000_000}
        else:
            cfg["collector"] = {"mode": "async", "concurrency": k}
        p = work / f"{cfg['run_name']}.yaml"
        p.write_text(yaml.safe_dump(cfg, sort_keys=False))
        cfgs.append(p)
        rd = pathlib.Path("runs") / cfg["run_name"]
        shutil.rmtree(rd, ignore_errors=True)
        rds.append(rd)
        logs.append(work / f"{cfg['run_name']}.log")

    import os
    e = dict(os.environ)
    e.update({"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"})
    t0 = time.time()
    procs, handles = [], []
    for cfg, log in zip(cfgs, logs):
        fh = open(log, "w")
        handles.append(fh)
        procs.append(subprocess.Popen([AB.PY, "-m", "rl.train", "--config", str(cfg)],
                                      stdout=fh, stderr=subprocess.STDOUT, env=e))
    mem: dict = {}
    stop = threading.Event()
    w = threading.Thread(target=peak_rss_watcher, daemon=True,
                         args=(stop, [p.pid for p in procs], mem))
    w.start()
    rcs = [p.wait() for p in procs]
    stop.set()
    w.join(timeout=5)
    for fh in handles:
        fh.close()
    wall = time.time() - t0

    per_lane = [r for r in (realized(rd) for rd in rds) if r]
    cell = {
        "path": path,
        "k": k, "width": width, "threads": threads, "steps_per_lane": steps,
        "rcs": rcs, "ok": all(r == 0 for r in rcs),
        "wall_seconds": round(wall, 1),
        "per_lane_realized_median": round(sum(per_lane) / len(per_lane), 1)
        if per_lane else None,
        "fleet_realized": round(sum(per_lane), 1) if per_lane else None,
        "peak_rss_gb": mem.get("peak_rss_gb"),
    }
    return cell


GRIDS = {
    # Enough to find the shape without spending the night on it: k at the two
    # ends plus the production default, width 1 against the protocol's 3, and
    # threads 1 against a count that leaves headroom at width 3.
    "quick": {"k": [8, 256], "width": [1, 3], "threads": [1, 4]},
    # The Node path's own headroom, so a maxed engine is not being compared
    # against a default-configured server. concurrency 8 is what the banked
    # arm ran; 32 is the same direction the engine's k lever moves in.
    "quick_node": {"k": [8, 32], "width": [1, 3], "threads": [1, 4]},
    "k": {"k": [8, 64, 256, 512], "width": [1], "threads": [1]},
    "width": {"k": [256], "width": [1, 2, 3, 6], "threads": [1]},
    "threads": {"k": [256], "width": [1], "threads": [1, 2, 4, 8]},
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--path", choices=("engine", "node"), default="engine",
                    help="which collector to sweep. `k` is battles in flight "
                         "either way: collector.k for the engine, "
                         "collector.concurrency for the async Node collector.")
    ap.add_argument("--grid", choices=sorted(GRIDS), default=None)
    ap.add_argument("--k", default=None)
    ap.add_argument("--width", default=None)
    ap.add_argument("--threads", default=None)
    ap.add_argument("--steps", type=int, default=200_000,
                    help="steps PER LANE per cell. The read is a median over "
                         "update windows, so this needs enough updates to have "
                         "a median: 200k is ~6 updates at the 30,720 batch.")
    ap.add_argument("--seed", type=int, default=5100)
    ap.add_argument("--team-bank", default=None,
                    help="engine path only; defaults to the standard bank")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/maxout.json"))
    args = ap.parse_args(argv)

    b = AB.busy()
    if b and not args.force:
        raise SystemExit(f"the box is busy ({'; '.join(b)}); this is a timing "
                         "sweep and every cell would be wrong")

    grid = GRIDS[args.grid] if args.grid else {}
    ks = [int(x) for x in args.k.split(",")] if args.k else grid.get("k", [256])
    ws = [int(x) for x in args.width.split(",")] if args.width else grid.get("width", [1])
    ts = [int(x) for x in args.threads.split(",")] if args.threads else grid.get("threads", [1])

    bank = args.team_bank or AB.BANK
    if args.path == "engine":
        if not pathlib.Path(bank).exists() and not (AB.MAIN / bank).exists():
            raise SystemExit(f"team bank {bank} is missing")
        AB.stop_server()      # engine cells need no server; a live one is noise
    else:
        if AB.simulator_workers() != 4:
            raise SystemExit("showdown/config/config.js must set simulator: 4 "
                             "(CLAUDE.md rule 5) or every Node cell is ~81% "
                             "slow for a reason that has nothing to do with "
                             "the lever being swept")
        AB.start_server()

    base = yaml.safe_load(AB.BASE_CONFIG.read_text())
    work = pathlib.Path("results/engine_a1/maxout")
    work.mkdir(parents=True, exist_ok=True)

    cells = []
    total = len(ks) * len(ws) * len(ts)
    seed = args.seed
    for k in ks:
        for width in ws:
            for threads in ts:
                print(f"--- [{len(cells)+1}/{total}] k={k} width={width} "
                      f"threads={threads}", flush=True)
                c = run_cell(base, k, width, threads, args.steps, work, seed,
                             args.path, bank)
                seed += width + 1          # never reuse a seed across cells
                cells.append(c)
                print(f"    ok={c['ok']} wall={c['wall_seconds']}s  "
                      f"per-lane {c['per_lane_realized_median']}  "
                      f"fleet {c['fleet_realized']}  "
                      f"peak {c['peak_rss_gb']} GB", flush=True)
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(
                    {"path": args.path, "cells": cells,
                     "steps_per_lane": args.steps,
                     "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime())},
                    indent=2) + "\n")

    ok = [c for c in cells if c["ok"] and c["fleet_realized"]]
    print(f"\npath={args.path}")
    print(f"{'k':>5} {'width':>6} {'thr':>4} {'per-lane':>10} {'fleet':>10} {'GB':>6}")
    for c in cells:
        print(f"{c['k']:>5} {c['width']:>6} {c['threads']:>4} "
              f"{str(c['per_lane_realized_median']):>10} "
              f"{str(c['fleet_realized']):>10} {str(c['peak_rss_gb']):>6}"
              + ("" if c["ok"] else "   FAILED"))
    if ok:
        best_fleet = max(ok, key=lambda c: c["fleet_realized"])
        best_lane = max(ok, key=lambda c: c["per_lane_realized_median"])
        print(f"\nbest FLEET throughput: k={best_fleet['k']} "
              f"width={best_fleet['width']} threads={best_fleet['threads']} "
              f"-> {best_fleet['fleet_realized']} steps/s "
              f"({best_fleet['peak_rss_gb']} GB)")
        print(f"best PER-LANE rate:    k={best_lane['k']} "
              f"width={best_lane['width']} threads={best_lane['threads']} "
              f"-> {best_lane['per_lane_realized_median']} steps/s")
        print("\nThey are different questions. Per-lane is how fast ONE run "
              "finishes; fleet is how many seeds per hour. A lane is a SEED, "
              "so width buys the second and never the first.")
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

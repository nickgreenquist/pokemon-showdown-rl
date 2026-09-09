#!/usr/bin/env python
"""THE OFFICIAL SPEEDUP RECORD for the pkmn/engine collector port.

WHY THIS EXISTS SEPARATELY FROM T-1. T-1's bands are ABSOLUTE thresholds
(>= N battles/s, >= N steps/s) — they say whether the engine is fast enough,
not how much faster it is than the thing it replaces. Only T-1 (d) compares,
and it compares one quantity. This file produces the single number the project
will be asked for — "how much faster is the port" — with the disclosures that
have to travel with it.

THE COMPARISON IS LIKE-FOR-LIKE BY CONSTRUCTION. Both arms run the SAME recipe
(configs/showdown_sp_batch50m_async.yaml below the collector block, which
configs/engine_a1.yaml is byte-identical to outside the declared keys), the
same encoder, the same network, at the SAME FLEET WIDTH of 3. The only delta
is the collector. A speedup measured across different recipes or widths is not
a speedup, and this repo has already paid for that lesson once
(scripts/showdown_throughput.py, ~7x overstatement at [64,64]).

REALIZED, NEVER THE ESTIMATOR. `time/steps_per_sec` is a poll-cadence estimator
that overstates the ASYNC loop by ~57% and the sync loop by ~18% (SESSION_LOGS
2026-09-01). Every headline number here is steps divided by wall-clock.

    python scripts/engine_speedup.py --out results/engine_a1/speedup.json
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys

MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")

# The Node arm's realized per-lane rate at 3-wide, MEASURED, from the Stage-2
# async acceptance fleet: 12M steps / wall, SESSION_LOGS 2026-09-01. This is
# the CURRENT BEST Node path — already 1.53x the sync loop it replaced — so the
# speedup below is against a moving, improved baseline, not the original.
NODE = {
    "per_lane_realized_steps_per_sec": [573.5, 574.1, 574.6],
    "width": 3,
    "source": "SESSION_LOGS 2026-09-01, showdown_sp_batch50m_async_s{66,75,83}",
    "note": "async; already 1.53x the sync path measured at the same width",
}
NODE_RUNS = [f"showdown_sp_batch50m_async_s{s}" for s in (66, 75, 83)]
ENGINE_RUNS = [f"engine_a1_s{s}" for s in (66, 75, 83)]


def split(hist: pathlib.Path) -> dict | None:
    """Per-update collect / update / eval seconds, from a run's own history."""
    if not hist.exists():
        return None
    c = u = e = 0.0
    n = 0
    with open(hist) as fh:
        for r in csv.DictReader(fh):
            try:
                cs, us = r.get("time/collect_sec", ""), r.get("time/update_sec", "")
                if cs in ("", None) or us in ("", None):
                    continue
                c += float(cs)
                u += float(us)
                ev = r.get("time/eval_sec", "")
                e += float(ev) if ev not in ("", None) else 0.0
                n += 1
            except (TypeError, ValueError):
                continue
    if not n:
        return None
    tot = c + u
    return {"updates": n, "collect_sec_total": c, "update_sec_total": u,
            "eval_sec_total": e,
            "collect_share": c / tot if tot else None,
            "update_share": u / tot if tot else None,
            "collect_sec_per_update": c / n, "update_sec_per_update": u / n}


def realized(run_dir: pathlib.Path) -> float | None:
    """steps / wall-clock, from the run's own history timestamps."""
    hist = run_dir / "history.csv"
    if not hist.exists():
        hist = run_dir / "history_merged.csv"
    if not hist.exists():
        return None
    first_t = last_t = first_s = last_s = None
    with open(hist) as fh:
        for r in csv.DictReader(fh):
            try:
                t, s = float(r["_timestamp"]), float(r["_step"])
            except (TypeError, ValueError, KeyError):
                continue
            if first_t is None:
                first_t, first_s = t, s
            last_t, last_s = t, s
    if None in (first_t, last_t) or last_t <= first_t:
        return None
    return (last_s - first_s) / (last_t - first_t)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine-root", type=pathlib.Path, default=pathlib.Path("runs"))
    ap.add_argument("--node-root", type=pathlib.Path, default=MAIN / "runs")
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/speedup.json"))
    args = ap.parse_args(argv)

    node_split = {r: split(args.node_root / r / "history.csv") for r in NODE_RUNS}
    eng_split = {r: split(args.engine_root / r / "history.csv") for r in ENGINE_RUNS}
    eng_rate = {r: realized(args.engine_root / r) for r in ENGINE_RUNS}

    node_rate = statistics.median(NODE["per_lane_realized_steps_per_sec"])
    have = [v for v in eng_rate.values() if v]
    out: dict = {
        "scope": "FULL-LOOP, per lane, FLEET WIDTH 3, entity trunk 512x512, "
                 "gen-1 batch recipe; realized (steps/wall), never the "
                 "time/steps_per_sec estimator",
        "node": {**NODE, "median_per_lane": node_rate},
        "engine": {"per_lane_realized_steps_per_sec": eng_rate,
                   "median_per_lane": statistics.median(have) if have else None,
                   "k": 8,
                   "width": 3},
        "collect_update_split": {"node": node_split, "engine": eng_split},
    }
    if have:
        m = statistics.median(have)
        out["speedup_per_lane_3wide"] = m / node_rate
        out["hours_to_12M_per_lane"] = {"node": 12e6 / node_rate / 3600,
                                        "engine": 12e6 / m / 3600}
    out["disclosures"] = [
        "WIDTH AND SCOPE TRAVEL WITH THIS NUMBER. It is per lane at 3-wide, "
        "full-loop. A solo number is a different quantity and is not this one.",
        "MEASURED AT k=8, NOT AT A PRODUCTION K. A-1 pins the engine collector "
        "to the banked arm's concurrency so the collector is the only delta. "
        "T-1(b) measures 22,318 steps/s at K=256 against 30,559 at K=512 "
        "collection-only, so the production configuration is FASTER than this "
        "number and this is a LOWER BOUND on the port's ceiling.",
        "THE BASELINE IS THE ASYNC NODE PATH, which is itself 1.53x the sync "
        "loop it replaced. The speedup is against the current best Node path, "
        "not against the original one.",
        "REALIZED, NOT THE ESTIMATOR: time/steps_per_sec overstates the async "
        "loop by ~57%. Quoting it would inflate the Node side and UNDERSTATE "
        "this speedup.",
        "EVAL IS UNCHANGED. The locked protocol and the ladder stay on the "
        "Showdown server, so no eval schedule gets faster by this.",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    print("THE OFFICIAL SPEEDUP RECORD — full-loop, per lane, 3-wide, k=8")
    print(f"  Node  (async, banked): {node_rate:8.1f} steps/s/lane")
    if have:
        print(f"  Engine (pkmn/engine):  {statistics.median(have):8.1f} steps/s/lane")
        print(f"  SPEEDUP:               {out['speedup_per_lane_3wide']:8.2f}x")
        h = out["hours_to_12M_per_lane"]
        print(f"  12M per lane:          {h['node']:.1f} h  ->  {h['engine']:.1f} h")
    else:
        print("  Engine: NO history yet — run this after the lanes finish")
    for tag, d in (("node", node_split), ("engine", eng_split)):
        vals = [v for v in d.values() if v]
        if vals:
            cs = statistics.median(v["collect_share"] for v in vals)
            print(f"  {tag:6s} collect share of (collect+update): {cs:.1%}")
    print(f"  written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""WHERE THE WALL CLOCK GOES, before and after the port.

The speedup says how much faster. This says what is now SLOW, which is the
number that decides what to work on next.

`time/collect_sec` and `time/update_sec` are the loop's own split (both logged
from PPO's update, per CLAUDE.md's locked metric names), and their ratio is
dimensionless — so unlike a rate it can be compared across arms of different
DOSE without adjustment. It cannot be compared across different WIDTHS, which
is why this records the width and refuses to mix them silently.

    python scripts/engine_update_share.py \\
        --engine runs/engine_a1_s66 --engine runs/engine_a1_s75 \\
        --node runs/showdown_sp_batch50m_async_s66 --width 3
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics


def share(run_dir: pathlib.Path) -> dict | None:
    hist = run_dir / "history.csv"
    if not hist.exists():
        return None
    c, u, r = [], [], []
    with open(hist) as fh:
        for row in csv.DictReader(fh):
            for key, acc in (("time/collect_sec", c), ("time/update_sec", u),
                             ("time/realized_steps_per_sec", r)):
                v = row.get(key)
                if v not in (None, ""):
                    acc.append(float(v))
    if not (c and u):
        return None
    return {
        "run": run_dir.name,
        "updates": len(u),
        # Summed, not averaged per-update: the question is what fraction of the
        # RUN's wall clock went where, and a per-update mean would weight a
        # 0.4 s update the same as a 40 s one.
        "update_share_of_wall": sum(u) / (sum(u) + sum(c)),
        "collect_share_of_wall": sum(c) / (sum(u) + sum(c)),
        # The first window straddles startup; dropped, as leg (c) does.
        "realized_steps_per_sec_median": statistics.median(r[1:]) if len(r) > 1 else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--node", type=pathlib.Path, action="append", default=[])
    ap.add_argument("--width", type=int, required=True,
                    help="lanes sharing the box. BOTH arms must have run at "
                         "this width or the shares are not comparable.")
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/update_share.json"))
    args = ap.parse_args(argv)

    arms = {}
    for name, dirs in (("engine", args.engine), ("node", args.node)):
        rows = [s for s in (share(d) for d in dirs) if s]
        if not rows:
            continue
        arms[name] = {
            "lanes": rows,
            "update_share_mean": statistics.fmean(r["update_share_of_wall"] for r in rows),
            "collect_share_mean": statistics.fmean(r["collect_share_of_wall"] for r in rows),
        }
    if len(arms) != 2:
        raise SystemExit("need at least one run dir with a history.csv on EACH "
                         "side; a one-armed read says nothing about the port")

    e, n = arms["engine"], arms["node"]
    out = {
        "question": "what fraction of training wall clock is the UPDATE, "
                    "before and after the collector port",
        "width": args.width,
        "comparable_because": "the share is dimensionless, so it survives a "
                              "dose difference between the arms; it does NOT "
                              "survive a WIDTH difference, and both arms here "
                              f"ran {args.width}-wide",
        "arms": arms,
        "collection_share_before": n["collect_share_mean"],
        "collection_share_after": e["collect_share_mean"],
        # Amdahl on the part the port can still touch.
        "further_collector_speedup_ceiling": 1.0 / e["update_share_mean"],
        "reading": (
            f"The port MOVED THE BOTTLENECK. Collection fell from "
            f"{n['collect_share_mean']:.1%} of wall to {e['collect_share_mean']:.1%}, "
            f"so the PPO update is now {e['update_share_mean']:.1%} of it. Any "
            f"further collector work is capped at "
            f"{1.0 / e['update_share_mean']:.2f}x by Amdahl no matter how fast "
            "the collector gets — the learner is the thing to optimise next."),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Read the CH5 MPS benchmark arms and print the comparison table.

The headline is `time/update_sec` -- the LEARNER, the only thing a device can
help. `time/collect_sec` is reported beside it because it is Node-bound and
MUST NOT move for a device reason; if it does, the device is taxing the
per-step `agent.act` transfer and that cost is real and belongs in the
proposal. `time/steps_per_sec` is the end-to-end rate the loop actually runs
at, which is what any wall-clock claim has to be made from.

Rollout 1 is discarded as warm-up (torch lazy init, first-touch allocation,
and on MPS the first-run kernel compile).

    python scripts/ch5_mps_report.py cpu1 mps cpu6
"""

import csv
import statistics as st
import sys
from pathlib import Path

BANKED = {"update_sec": 12.954, "collect_sec": 63.394, "steps_per_sec": 438.056}


def series(path, key):
    with open(path) as fh:
        return [float(r[key]) for r in csv.DictReader(fh)
                if r.get(key) not in (None, "", "NaN")]


def main():
    arms = sys.argv[1:] or ["cpu1", "mps", "cpu6"]
    rows = []
    for arm in arms:
        path = Path(f"runs/ch5_mps_bench_{arm}/history.csv")
        if not path.exists():
            print(f"  {arm}: MISSING {path}")
            continue
        row = {"arm": arm}
        for key in ("time/update_sec", "time/collect_sec"):
            v = series(path, key)
            row[key] = v
        sps = series(path, "time/steps_per_sec")
        row["time/steps_per_sec"] = sps
        rows.append(row)

    print(f"{'arm':6s} {'rollouts':>8s} {'update_sec (2..n)':>22s} "
          f"{'collect_sec (2..n)':>20s} {'steps/s':>9s}")
    for row in rows:
        upd = row["time/update_sec"][1:]
        col = row["time/collect_sec"][1:]
        sps = row["time/steps_per_sec"]
        u = f"{st.mean(upd):.3f} ({min(upd):.3f}-{max(upd):.3f})" if upd else "n/a"
        c = f"{st.mean(col):.3f} ({min(col):.3f}-{max(col):.3f})" if col else "n/a"
        s = f"{st.mean(sps):.1f}" if sps else "n/a"
        print(f"{row['arm']:6s} {len(row['time/update_sec']):8d} {u:>22s} {c:>20s} {s:>9s}")
    print(f"\ns83 banked (1,627 rollouts): update {BANKED['update_sec']:.3f}s, "
          f"collect {BANKED['collect_sec']:.3f}s, {BANKED['steps_per_sec']:.1f} steps/s")

    base = next((r for r in rows if r["arm"] == "cpu1"), None)
    if base and len(base["time/update_sec"]) > 1:
        b = st.mean(base["time/update_sec"][1:])
        print("\nspeedup on the LEARNER vs cpu1 (>1 means faster):")
        for row in rows:
            upd = row["time/update_sec"][1:]
            if upd:
                print(f"  {row['arm']:6s} {b / st.mean(upd):.2f}x")
        print("\nCollection is Node-bound and cannot benefit; no end-to-end "
              "'N x faster' claim follows from the learner column alone.")


if __name__ == "__main__":
    main()

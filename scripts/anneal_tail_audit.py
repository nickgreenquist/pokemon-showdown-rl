#!/usr/bin/env python
"""What actually happens in the LAST QUARTER of a run, after the LR has annealed
most of the way to zero?

    python scripts/anneal_tail_audit.py --runs runs/showdown_monster200m_w_s*

THE RULING IT SERVES. [RWL-4] left "the LR-anneal floor" as an owed maintainer
ruling: should the anneal run to ~0, or stop at a floor? The note on the record
is that W's explained variance FALLS through the annealed tail (0.675 -> 0.596),
"so the tail is not inert -- cuts both ways". Nobody had assembled the rest of
the evidence, so the ruling had one number and no context.

WHAT THIS MEASURES, per lane, over the last quarter of training against the
quarter before it: explained variance, entropy, approx_kl, value loss, the
self-play win rates, and the in-loop eval win rate. **The question is not whether
EV falls -- it does -- but whether ANYTHING improves while it falls.** A tail
that only degrades argues for a floor; a tail that trades EV for win rate argues
for leaving it alone; a tail where nothing moves at all argues for stopping
early and spending the steps elsewhere.

THE ANNEAL IS NOT LOGGED. `history.csv` carries no learning-rate column, so the
tail is defined by STEP FRACTION rather than by the realized LR. That is a
disclosure, not a workaround: the schedule is linear-to-zero in the config, so
the last quarter is the last quarter of the schedule.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
from pathlib import Path

COLS = {
    "loss/explained_variance": "EV",
    "loss/entropy": "entropy",
    "loss/approx_kl": "approx_kl",
    "loss/value": "value_loss",
    "rollout/episode_return": "return",
    "selfplay/winrate_latest": "sp_latest",
    "eval/win_rate": "eval_wr",
}


def read(path: Path) -> tuple[list[int], dict[str, list[tuple[int, float]]]]:
    series: dict[str, list[tuple[int, float]]] = {k: [] for k in COLS}
    steps: list[int] = []
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                st = int(float(row["_step"]))
            except (TypeError, ValueError):
                continue
            steps.append(st)
            for k in COLS:
                v = row.get(k, "")
                if v not in ("", "NaN", "nan", None):
                    try:
                        series[k].append((st, float(v)))
                    except ValueError:
                        pass
    return steps, series


def window(pairs, lo, hi):
    return [v for s, v in pairs if lo <= s < hi]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["runs/showdown_monster200m_w_s*"])
    ap.add_argument("--tail", type=float, default=0.25,
                    help="fraction of the run treated as the annealed tail")
    args = ap.parse_args()

    paths = []
    for pat in args.runs:
        paths += [Path(p) / "history.csv" for p in sorted(glob.glob(pat))]
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("no history.csv found")
        return

    print("=" * 88)
    print(f"THE ANNEALED TAIL -- last {args.tail:.0%} of training vs the "
          f"{args.tail:.0%} before it")
    print("The LR is NOT logged; the tail is defined by step fraction against a")
    print("linear-to-zero schedule. Every number is a mean over its window.")
    print("=" * 88)
    agg: dict[str, list[tuple[float, float]]] = {k: [] for k in COLS}
    for p in paths:
        steps, series = read(p)
        if not steps:
            continue
        last = max(steps)
        t0 = int(last * (1 - args.tail))
        m0 = int(last * (1 - 2 * args.tail))
        print(f"\n## {p.parent.name}   final step {last:,}")
        print(f"  {'metric':<12} {'mid window':>12} {'annealed tail':>14} {'delta':>10}")
        for k, lab in COLS.items():
            mid, tail = window(series[k], m0, t0), window(series[k], t0, last + 1)
            if len(mid) < 3 or len(tail) < 3:
                print(f"  {lab:<12} {'--':>12} {'--':>14}  (too few points)")
                continue
            a, b = sum(mid) / len(mid), sum(tail) / len(tail)
            agg[k].append((a, b))
            print(f"  {lab:<12} {a:>12.4f} {b:>14.4f} {b - a:>+10.4f}")

    print("\n" + "=" * 88)
    print("POOLED ACROSS LANES -- what the ruling actually turns on")
    print("=" * 88)
    for k, lab in COLS.items():
        vals = agg[k]
        if not vals:
            continue
        d = [b - a for a, b in vals]
        mean = sum(d) / len(d)
        sd = math.sqrt(sum((x - mean) ** 2 for x in d) / max(len(d) - 1, 1))
        agree = all(x > 0 for x in d) or all(x < 0 for x in d)
        print(f"  {lab:<12} delta {mean:>+9.4f}  sd {sd:>7.4f} over {len(d)} lanes"
              f"   {'ALL LANES AGREE' if agree else 'lanes disagree in SIGN'}")
    print("\n  READ: the tail is not inert if anything moves. What decides the")
    print("  ruling is whether anything moves in a GOOD direction while EV falls.")
    print("=" * 88)


if __name__ == "__main__":
    main()

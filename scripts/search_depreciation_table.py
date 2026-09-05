#!/usr/bin/env python
"""Search-depreciation check (JOURNEY "Before step 3", second cheap add):
search gain vs greedy strength, rebuilt from the eval JSONs on disk.

    python scripts/search_depreciation_table.py [--markdown]

THE HYPOTHESIS (JOURNEY.md:21-23): search substitutes for a deficient value
head, so its gain should DECLINE as the greedy policy improves. No training,
no new runs: every point below is a published, locked-protocol number (off
Foul Play@20, ties as non-wins) measured on this box.

THE DECISION RULE lives in docs/proposals/search_depreciation_check.md and is
NOT applied here until the maintainer ratifies it; this script prints the
inputs and the two statistics the rule names (the OLS slope of gain on greedy
strength over the matched-axis points, and the strongest matched point's gain
in units of its se_diff). It never prints a verdict.

MATCHED AXIS = same checkpoint, same FP budget (20 ms), same search dose (M),
greedy vs searched. The 12M s65 point is shown for context only: it was
measured at Foul Play's stock 100 ms budget with n=250/arm (CH3 R2) and is
excluded from the fit. The 100M lanes have no searched arm (never measured)
and appear as x-axis-only rows.
"""
import argparse, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"


def rate(path):
    d = json.loads((R / path).read_text())
    return d["our_win_rate"], d["battles_finished"]


def se_diff(p1, n1, p2, n2):
    return math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)


# (label, recipe, greedy json, searched json) — searched=None means unmeasured
POINTS = [
    ("s82 (50M stack)", "stack50m_r2", "ch5_r1_offsh/a82.json", "ch5_r1_offsh/rs82.json"),
    ("s81 (50M stack)", "stack50m_r2", "ch5_r1_offsh/a81.json", "ch5_r1_offsh/rs81.json"),
    ("s80 (50M stack)", "stack50m_r2", "ch5_r1_offsh/a80.json", "ch5_r1_offsh/rs80.json"),
    ("s66 (50M batch)", "batch50m", "ch5_r2_offsh/t66.json", "ch5_r2_offsh/r4s66.json"),
    ("s104 (100M batch async)", "batch async 100M", "ch5_100m/t104.json", None),
    ("s112 (100M batch async)", "batch async 100M", "ch5_100m/t112.json", None),
    ("s120 (100M batch async)", "batch async 100M", "ch5_100m/t120.json", None),
]
CONTEXT_12M = ("s65 (12M, CH3 R2, FP@100 ms, n=250/arm — EXCLUDED from the fit)",
               "recipe12m", 0.388, 250, 0.368, 250)


def ols(xs, ys):
    xb, yb = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - xb) ** 2 for x in xs)
    sxy = sum((x - xb) * (y - yb) for x, y in zip(xs, ys))
    b = sxy / sxx
    return b, yb - b * xb


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    rows, fit_x, fit_y, fit_stack = [], [], [], []
    for label, recipe, g, s in POINTS:
        pg, ng = rate(g)
        if s is None:
            rows.append((label, recipe, pg, ng, None, None, None, None)); continue
        ps, ns = rate(s)
        gain = ps - pg; sd = se_diff(pg, ng, ps, ns)
        rows.append((label, recipe, pg, ng, ps, ns, gain, sd))
        fit_x.append(pg); fit_y.append(gain)
        if recipe == "stack50m_r2":
            fit_stack.append((pg, gain))
    lbl, rec, pg, ng, ps, ns = CONTEXT_12M
    rows.append((lbl, rec, pg, ng, ps, ns, ps - pg, se_diff(pg, ng, ps, ns)))
    sep = "|" if args.markdown else "  "
    hdr = ["point", "recipe", "greedy", "n", "search@M", "n", "gain", "se_diff", "gain/se"]
    print(sep.join(hdr) if not args.markdown else "| " + " | ".join(hdr) + " |")
    if args.markdown:
        print("|" + "---|" * len(hdr))
    for label, recipe, pg, ng, ps, ns, gain, sd in rows:
        cells = [label, recipe, f"{pg:.4f}", str(ng),
                 f"{ps:.4f}" if ps is not None else "unmeasured", str(ns) if ns else "—",
                 f"{gain:+.4f}" if gain is not None else "—",
                 f"{sd:.4f}" if sd else "—", f"{gain / sd:+.1f}" if sd else "—"]
        print(("| " + " | ".join(cells) + " |") if args.markdown else sep.join(cells))
    b, a = ols(fit_x, fit_y)
    bs, as_ = ols([p for p, _ in fit_stack], [g for _, g in fit_stack])
    print()
    print(f"OLS slope of gain on greedy, matched-axis points (k={len(fit_x)}): {b:+.3f}; "
          f"zero-crossing at greedy = {-a / b:.3f}")
    print(f"same, stack-recipe points only (k={len(fit_stack)}): {bs:+.3f}; "
          f"zero-crossing at greedy = {-as_ / bs:.3f}")
    strongest = max((r for r in rows[:4]), key=lambda r: r[2])
    print(f"strongest matched point: {strongest[0]} greedy {strongest[2]:.4f}, "
          f"gain {strongest[6]:+.4f} = {strongest[6] / strongest[7]:+.1f} se_diff")
    print("(no verdict: the rule is applied only once ratified — see the proposal doc)")


if __name__ == "__main__":
    main()

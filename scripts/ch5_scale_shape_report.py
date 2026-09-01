"""Read the CH5 scale-shape rungs and print the curve. DESCRIPTIVE ONLY.

The question is narrow: under the BATCH recipe, is vs-SH still climbing at 50M
or already flat? Nothing here is a bar, a comparator or a projection -- one
seed (s83, the only lane without a resume seam), so it credits nothing and a
100M number cannot be read off it.

Rungs are UNPAIRED: the server rolls teams and damage, so each pass draws
fresh battles regardless of the episode seed ladder. Standard errors are
binomial on the per-rung n; a difference between two rungs uses the unpaired
se_diff = sqrt(se_a^2 + se_b^2). Ties count as non-wins, as everywhere.

    python scripts/ch5_scale_shape_report.py
"""

import json
import math
from pathlib import Path

RUNGS = Path("runs/showdown_sp_batch50m_s83/scale_shape")
# s83's own banked 50M vs-SH under the locked protocol (RESULTS.md:1051,
# "s66 0.78133, s75 0.79467, s83 0.78333"), the third independent draw.
BANKED_S83_50M = 0.78333


def main():
    rows = []
    for path in sorted(RUNGS.glob("rung_*.json")):
        r = json.loads(path.read_text())
        n = r["episodes"]
        p = r["eval/win_rate"]
        rows.append({
            "step": r["step"],
            "n": n,
            "win_rate": p,
            "se": math.sqrt(p * (1 - p) / n),
            "ties": r.get("ties_from_returns"),
        })
    rows.sort(key=lambda r: r["step"])

    print(f"{'step':>12s} {'n':>6s} {'vs-SH':>8s} {'se':>7s} {'d(prev)':>9s} "
          f"{'se_diff':>8s} {'d/se':>6s}")
    for i, r in enumerate(rows):
        if i:
            prev = rows[i - 1]
            d = r["win_rate"] - prev["win_rate"]
            sed = math.sqrt(r["se"] ** 2 + prev["se"] ** 2)
            extra = f"{d:+9.4f} {sed:8.4f} {d / sed:6.2f}"
        else:
            extra = " " * 25
        print(f"{r['step']:12d} {r['n']:6d} {r['win_rate']:8.4f} {r['se']:7.4f} {extra}")

    if len(rows) >= 3:
        first, mid, last = rows[0], rows[len(rows) // 2], rows[-1]
        print("\nsegments (unpaired):")
        for a, b, name in ((first, mid, "first half"), (mid, last, "second half")):
            d = b["win_rate"] - a["win_rate"]
            sed = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
            per10m = d / ((b["step"] - a["step"]) / 10e6)
            print(f"  {name:12s} {a['step'] / 1e6:.0f}M -> {b['step'] / 1e6:.0f}M: "
                  f"{d:+.4f} (se_diff {sed:.4f}, {d / sed:.1f} se) "
                  f"= {per10m:+.4f} per 10M")
        tail = rows[-3:]
        d = tail[-1]["win_rate"] - tail[0]["win_rate"]
        sed = math.sqrt(tail[-1]["se"] ** 2 + tail[0]["se"] ** 2)
        print(f"\n  TAIL {tail[0]['step'] / 1e6:.0f}M -> {tail[-1]['step'] / 1e6:.0f}M: "
              f"{d:+.4f} (se_diff {sed:.4f}, {d / sed:.1f} se)")
        print("  -> " + ("STILL CLIMBING at the last rung"
                         if d > 2 * sed else
                         "NOT distinguishable from flat over the tail"))
    recheck = RUNGS / "recheck_050M_n3000.json"
    if recheck.exists():
        r = json.loads(recheck.read_text())
        top = rows[-1]
        draws = [("rung", top["win_rate"]), ("re-draw", r["eval/win_rate"]),
                 ("banked R2 (s83)", BANKED_S83_50M)]
        print("\nRE-DRAW CHECK at 50M -- THE NOISE FLOOR OF A SINGLE RUNG.")
        print("  three independent n=3000 passes over the SAME checkpoint:")
        for name, v in draws:
            print(f"    {name:18s} {v:.5f}")
        vals = [v for _, v in draws]
        spread = max(vals) - min(vals)
        print(f"  spread {spread:.4f} against a binomial se of {top['se']:.4f}. "
              "A rung-to-rung difference of this size is NOT a signal: read the "
              "curve's SHAPE over tens of millions of steps, never one rung "
              "against its neighbour.")

    print("\nDescriptive, single seed, unpaired. No bar, no comparator, no "
          "projection to 100M.")


if __name__ == "__main__":
    main()

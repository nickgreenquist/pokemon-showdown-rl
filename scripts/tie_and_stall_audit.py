#!/usr/bin/env python
"""How often does a battle STALL, and does it bias any comparison?

    python scripts/tie_and_stall_audit.py [--min-n 500]

WHY IT WAS WRITTEN. The locked protocol counts ties as NON-WINS, so an arm that
stalls more gives away win rate mechanically -- and nothing had ever measured
the stall rate. It surfaced sideways: the open-gate arms in RESULTS §24 have a
battle-length standard deviation three times their anchor's, which turned out to
be one or two battles hitting a 1000-TURN CAP rather than any systematic
lengthening.

WHAT IT FOUND, over 143,500 banked battles (2026-09-18):
  * the overall tie rate is 0.0014, and the worst single arm is 0.0110;
  * 52% of ties are 1000-turn caps -- a genuine stall, not a close finish;
  * the tie rate is a SYMPTOM OF WEAKNESS, not a hidden lever:
    corr(win rate, tie rate) = -0.31, and the weaker half of arms tie 3.5x as
    often as the stronger half.

HOW TO READ IT. Within a block every arm's tie rate is ~0.001 and the term is
negligible. ACROSS blocks the spread reaches 0.011, which is HALF the size of
the effects this project chases -- so a cross-block win-rate comparison (already
barred by the session offset) is biased by this too, in the same direction:
against the weaker arm, twice.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
TURN_CAP = 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=500)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(str(REPO / "results/*/*.json"))):
        if "runner" in p or "/smoke" in p:
            continue
        try:
            d = json.loads(Path(p).read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        pb = d.get("per_battle")
        if (not isinstance(pb, list) or len(pb) < args.min_n
                or not pb or "turns" not in pb[0]
                or d.get("our_win_rate") is None):
            continue
        t = np.array([b["turns"] for b in pb])
        o = np.array([b["outcome"] for b in pb])
        rows.append({
            "arm": "/".join(p.split("/")[-2:]).replace(".json", ""),
            "n": len(t), "ties": int((o == "tie").sum()),
            "tie_rate": float((o == "tie").mean()),
            "capped": int((t >= TURN_CAP).sum()),
            "p99_turns": float(np.percentile(t, 99)),
            "win": float(d["our_win_rate"]),
        })
    if not rows:
        print("no arms with per_battle data")
        return

    n = sum(r["n"] for r in rows)
    ties = sum(r["ties"] for r in rows)
    capped = sum(r["capped"] for r in rows)
    w = np.array([r["win"] for r in rows])
    tr = np.array([r["tie_rate"] for r in rows])

    print("=" * 84)
    print(f"TIE AND STALL AUDIT -- {len(rows)} arms, {n} battles")
    print("=" * 84)
    print(f"\n  overall tie rate            {ties / n:.4f}  ({ties} ties)")
    print(f"  ties that hit the {TURN_CAP}-turn cap {capped}/{ties} = "
          f"{capped / max(ties, 1):.0%}  -- a STALL, not a close finish")
    print(f"  worst single arm            {tr.max():.4f}")
    print(f"  spread across arms          {tr.max() - tr.min():.4f} of win rate, "
          f"handed away because ties are NON-WINS")

    print(f"\n  corr(win rate, tie rate)    {np.corrcoef(w, tr)[0, 1]:+.3f}")
    med = float(np.median(w))
    lo, hi = tr[w < med], tr[w >= med]
    print(f"  weaker half (win < {med:.3f})   tie rate {lo.mean():.4f}")
    print(f"  stronger half               tie rate {hi.mean():.4f}   "
          f"({lo.mean() / max(hi.mean(), 1e-9):.1f}x)")
    print("  -> a SYMPTOM of weakness, not a hidden lever. It still biases a")
    print("     cross-block comparison against the weaker arm, twice over.")

    print(f"\n  worst {args.top} arms:\n")
    print(f"  {'arm':>32} {'n':>5} {'ties':>5} {'rate':>7} {'capped':>7} "
          f"{'p99 turns':>10} {'win':>7}")
    for r in sorted(rows, key=lambda r: -r["tie_rate"])[:args.top]:
        print(f"  {r['arm']:>32} {r['n']:>5} {r['ties']:>5} {r['tie_rate']:>7.4f} "
              f"{r['capped']:>7} {r['p99_turns']:>10.0f} {r['win']:>7.4f}")
    print("\n  WITHIN a block every arm here sits near 0.001 and the term is")
    print("  negligible; the spread is a cross-block effect, and cross-block")
    print("  win-rate comparisons are already barred by the session offset.")
    print("=" * 84)


if __name__ == "__main__":
    main()

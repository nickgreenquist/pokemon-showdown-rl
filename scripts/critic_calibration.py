#!/usr/bin/env python
"""What is the critic actually getting WRONG? A second read of §27's rollouts.

    python scripts/critic_calibration.py [--rows results/outcome_variance/variance.json.rows.jsonl]

RESULTS §27 measured one number from 707 positions and 22,358 self-play rollouts
-- the luck ceiling, 0.3630 against the critic's 0.2176 -- and then stopped. The
same file answers three more questions for free, and all three bear on which
lever to pull next.

THE SELF-PLAY IDENTITY IS WHAT MAKES THIS POSSIBLE. Every rollout is the SAME
deterministic committee on both seats, so the true expected outcome averaged over
positions is EXACTLY ZERO. Any systematic non-zero in the critic is therefore a
BIAS and not a property of the positions -- there is no sampling argument to hide
behind, and the realized mean (-0.0006 over 22,358 rollouts) says the instrument
itself is not the source.

WHAT IT SEPARATES.
  CALIBRATION  is the critic wrong about the SCALE of its own values? An
               out-of-sample monotone (isotonic) recalibration is the best any
               rescaling can do, so the EV it buys is the whole calibration
               prize and everything left over is RANKING.
  RANKING      does it know WHICH position is better? Measured as the
               correlation with E[outcome|obs], the oracle the ceiling is built
               from.
  SEAT BIAS    does it think its own side is winning? The paired difference
               against the oracle, which cancels the position sample.

ISOTONIC BY HAND (pool-adjacent-violators): sklearn is not a dependency of this
repo and dependency changes go through pyproject.toml with exact pins
(CLAUDE.md), so a fifteen-line PAVA is the right call rather than an ad-hoc
install into the env the fleet resumes into.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

BUCKETS = ((2, 8), (9, 15), (16, 22), (23, 10**9))
# RESULTS §27's one-way random-effects ceiling. The in-sample oracle (0.3828) is
# biased UP and §27 bars it; the share of the gap a recalibration closes must be
# measured against this, not against that.
CEILING_UNBIASED = 0.3630


def pava(x: np.ndarray, y: np.ndarray):
    """Isotonic regression, pool adjacent violators. Returns (xs, fitted) sorted
    by x, so held-out points are scored by interpolation."""
    idx = np.argsort(x, kind="mergesort")
    xs, ys = x[idx], y[idx]
    val: list[float] = []
    wt: list[float] = []
    for v in ys:
        val.append(float(v))
        wt.append(1.0)
        while len(val) > 1 and val[-2] > val[-1]:
            v2, w2 = val.pop(), wt.pop()
            v1, w1 = val.pop(), wt.pop()
            val.append((v1 * w1 + v2 * w2) / (w1 + w2))
            wt.append(w1 + w2)
    return xs, np.repeat(val, [int(w) for w in wt])


def cross_val(pred_fn, p: np.ndarray, o: np.ndarray, groups: np.ndarray,
              folds: int = 5, seed: int = 0):
    """Out of sample, GROUPED BY POSITION -- and the grouping is the whole point.

    THIS WAS WRONG UNTIL 2026-09-19 AND IT INFLATED A HEADLINE. The first
    version split at the OUTCOME level. But the predictor is CONSTANT WITHIN A
    POSITION -- ~32 rollouts of one position share one critic value -- so a
    held-out outcome's own position was in the training fold **100% of the
    time**, with the identical x. The isotonic fit at that x then partially
    learned that position's own mean, and "out of sample" measured nothing of
    the kind: it read 0.2371 where the honest number is 0.2272.

    It is the same mistake as "seeds do not pair battles" (docs/landmines.md) in
    a new costume: correlated rows treated as independent draws. Splitting by
    POSITION is the fix, and it changes the conclusion's magnitude -- the
    calibration share of the gap falls from 12% to ~7%.
    """
    g = np.unique(groups)
    np.random.default_rng(seed).shuffle(g)
    out = np.empty_like(o, dtype=float)
    for k in range(folds):
        held = set(g[k::folds].tolist())
        te = np.flatnonzero(np.isin(groups, list(held)))
        tr = np.setdiff1d(np.arange(o.size), te)
        out[te] = pred_fn(p[tr], o[tr], p[te])
    return out


def _iso(ptr, otr, pte):
    xs, fit = pava(ptr, otr)
    return np.interp(pte, xs, fit)


def _affine(ptr, otr, pte):
    b, a = np.polyfit(ptr, otr, 1)
    return a + b * pte


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows",
                    default="results/outcome_variance/variance.json.rows.jsonl")
    ap.add_argument("--out", default="results/outcome_variance/calibration.json")
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.rows).read_text().splitlines() if l.strip()]
    assert rows, f"no rows in {args.rows}"
    # per POSITION
    v = np.array([r["critic"] for r in rows], dtype=float)
    m = np.array([r["mean"] for r in rows], dtype=float)
    t = np.array([r["turn"] for r in rows], dtype=float)
    # per OUTCOME
    o = np.array([x for r in rows for x in r["outcomes"]], dtype=float)
    p = np.array([r["critic"] for r in rows for _ in r["outcomes"]], dtype=float)
    mu = np.array([r["mean"] for r in rows for _ in r["outcomes"]], dtype=float)
    # the POSITION each outcome belongs to -- the CV must hold these out whole
    groups = np.array([i for i, r in enumerate(rows) for _ in r["outcomes"]])
    vt = float(o.var())

    def ev(pred):
        return 1.0 - float(((o - pred) ** 2).mean()) / vt

    raw, oracle = ev(p), ev(mu)
    iso_oos = ev(cross_val(_iso, p, o, groups))
    aff_oos = ev(cross_val(_affine, p, o, groups))
    # THE DENOMINATOR IS THE UNBIASED CEILING, not the in-sample oracle. §27
    # bars the naive ratio as biased up, and using it here would be using a
    # barred quantity as a denominator two subsections later.
    gap = CEILING_UNBIASED - raw
    d = v - m
    bias = float(d.mean())
    bias_se = float(d.std(ddof=1) / np.sqrt(d.size))
    slope, intercept = (float(x) for x in np.polyfit(v, m, 1))

    by_turn = []
    for lo, hi in BUCKETS:
        sel = (t >= lo) & (t <= hi)
        if sel.sum() < 10:
            continue
        r = float(np.corrcoef(v[sel], m[sel])[0, 1])
        b, a = (float(x) for x in np.polyfit(v[sel], m[sel], 1))
        by_turn.append({
            "turns": f"{lo}-{'+' if hi > 999 else hi}", "positions": int(sel.sum()),
            "corr": r, "r2": r * r, "slope": b, "intercept": a,
            "paired_bias": float((v[sel] - m[sel]).mean()),
        })

    print("=" * 76)
    print("WHAT IS THE CRITIC GETTING WRONG?  (a second read of RESULTS §27)")
    print(f"{len(rows)} positions, {o.size} self-play rollouts")
    print("=" * 76)
    print("\n## 1. CALIBRATION vs RANKING -- where is the gap to the ceiling?\n")
    print(f"  EV, raw critic                         {raw:.4f}")
    print(f"  EV, affine recalibration (out of samp) {aff_oos:.4f}   {aff_oos - raw:+.4f}")
    print(f"  EV, ISOTONIC recalib.    (out of samp) {iso_oos:.4f}   {iso_oos - raw:+.4f}")
    print(f"  EV, oracle E[outcome|obs]              {oracle:.4f}   IN-SAMPLE, biased up")
    print(f"  EV ceiling, §27 variance components    {CEILING_UNBIASED:.4f}   <- the denominator")
    print(f"\n  A monotone recalibration is the BEST any rescaling can do, so")
    print(f"  calibration is worth {iso_oos - raw:+.4f} of the {gap:.4f} gap "
          f"({100 * (iso_oos - raw) / gap:.0f}%).")
    print(f"  THE OTHER {100 - 100 * (iso_oos - raw) / gap:.0f}% IS RANKING: the critic does not know")
    print("  WHICH position is better, and no rescaling fixes that.")

    print("\n## 2. SEAT BIAS -- does it think its own side is winning?\n")
    print("  Self-play, one policy on both seats, so the truth is EXACTLY 0.")
    print(f"  realized mean outcome                  {float(o.mean()):+.4f}")
    print(f"  PAIRED bias E[critic - oracle]         {bias:+.4f}  "
          f"(se {bias_se:.4f}, z {bias / bias_se:.2f})")
    print(f"  affine fit: oracle ~ {intercept:+.4f} + {slope:.4f} x critic")

    print("\n## 3. BY TURN -- where does the ranking fail?\n")
    print(f"  {'turns':>8} {'pos':>4} {'corr':>7} {'r^2':>7} {'slope':>7} {'bias':>8}")
    for b in by_turn:
        print(f"  {b['turns']:>8} {b['positions']:>4} {b['corr']:>+7.3f} {b['r2']:>7.3f} "
              f"{b['slope']:>7.3f} {b['paired_bias']:>+8.4f}")

    summary = {
        "positions": len(rows), "outcomes": int(o.size),
        "ev_raw": raw, "ev_affine_oos": aff_oos, "ev_isotonic_oos": iso_oos,
        "ev_oracle": oracle, "gap_to_oracle": gap,
        "calibration_share": (iso_oos - raw) / gap if gap else float("nan"),
        "paired_bias": bias, "paired_bias_se": bias_se, "paired_bias_z": bias / bias_se,
        "affine_slope": slope, "affine_intercept": intercept,
        "by_turn": by_turn,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\n-> {args.out}")
    print("=" * 76)


if __name__ == "__main__":
    main()

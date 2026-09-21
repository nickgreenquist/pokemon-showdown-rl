#!/usr/bin/env python
"""What is the critic actually getting WRONG? A second read of §27's rollouts.

    python scripts/critic_calibration.py [--rows results/outcome_variance/variance.json.rows.jsonl]
        [--ceiling 0.3630] [--label r5w] [--out ...]
    python scripts/critic_calibration.py --compare A.calibration.json B.calibration.json

R6 (2026-09-21): the by-turn r^2 table carries a POSITION-clustered bootstrap CI
(1,000 resamples), `--ceiling` reads the run's OWN `ev_ceiling_unbiased` from the
sibling variance JSON by default (the 0.3630 constant is RESULTS 27's run and is
only a fallback, printed as such), `--label` names the critic in the JSON, and
`--compare` sets two calibration JSONs side by side per bucket with the delta
and its se (sqrt of the two bootstrap se^2 -- the runs sample DIFFERENT positions,
so the difference is unpaired). That is trio A's mechanism co-primary
(configs/showdown_r6_trio_a.yaml: the turn-2-8 r^2 must LIFT above the R5 W
finals' 0.287) read with error bars instead of by eye.

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


def r2_bootstrap(v: np.ndarray, m: np.ndarray, n_boot: int = 1000, seed: int = 0):
    """r^2 of corr(v, m) with a bootstrap over POSITIONS (each position is one
    (critic, oracle-mean) pair, so resampling pairs is the cluster bootstrap).
    Returns (r2, se, lo, hi); degenerate resamples (constant v or m) are dropped."""
    v = np.asarray(v, dtype=float); m = np.asarray(m, dtype=float)
    r = float(np.corrcoef(v, m)[0, 1])
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, v.size, v.size)
        a, b = v[idx], m[idx]
        if a.std() < 1e-12 or b.std() < 1e-12:
            continue
        draws.append(float(np.corrcoef(a, b)[0, 1]) ** 2)
    d = np.asarray(draws)
    return r * r, float(d.std(ddof=1)) if d.size > 1 else float("nan"), \
        float(np.percentile(d, 2.5)) if d.size else float("nan"), \
        float(np.percentile(d, 97.5)) if d.size else float("nan")


def compare(a: dict, b: dict) -> list[dict]:
    """Per-bucket r^2 of two calibration JSONs and the UNPAIRED delta B - A with
    se = sqrt(se_a^2 + se_b^2). Buckets are matched by their label; a bucket
    missing on one side is reported as absent, never dropped silently."""
    ta = {x["turns"]: x for x in a["by_turn"]}
    tb = {x["turns"]: x for x in b["by_turn"]}
    out = []
    for turns in sorted(set(ta) | set(tb), key=lambda t: int(t.split("-")[0])):
        xa, xb = ta.get(turns), tb.get(turns)
        row = {"turns": turns,
               "r2_a": xa["r2"] if xa else None, "r2_b": xb["r2"] if xb else None,
               "n_a": xa["positions"] if xa else 0, "n_b": xb["positions"] if xb else 0}
        if xa and xb and "r2_se" in xa and "r2_se" in xb:
            se = float(np.hypot(xa["r2_se"], xb["r2_se"]))
            row["delta"] = xb["r2"] - xa["r2"]
            row["se"] = se
            row["z"] = row["delta"] / se if se > 0 else float("nan")
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows",
                    default="results/outcome_variance/variance.json.rows.jsonl")
    ap.add_argument("--out", default="results/outcome_variance/calibration.json")
    ap.add_argument("--ceiling", type=float, default=None,
                    help="the run's ev_ceiling_unbiased; default: read from the sibling "
                         "variance JSON (<rows> minus '.rows.jsonl'), else RESULTS 27's 0.3630")
    ap.add_argument("--label", default="", help="the critic's name, stored in the JSON")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--compare", nargs=2, metavar=("A_JSON", "B_JSON"),
                    help="print two calibration JSONs side by side per bucket (B - A) and exit")
    args = ap.parse_args()

    if args.compare:
        a, b = (json.loads(Path(f).read_text()) for f in args.compare)
        print(f"BY-TURN r^2: A = {a.get('label') or args.compare[0]}   B = {b.get('label') or args.compare[1]}")
        print(f"  {'turns':>8} {'n_a':>5} {'r2_a':>7} {'n_b':>5} {'r2_b':>7} {'B-A':>8} {'se':>7} {'z':>6}")
        for r in compare(a, b):
            ra = "   --" if r["r2_a"] is None else f"{r['r2_a']:7.3f}"
            rb = "   --" if r["r2_b"] is None else f"{r['r2_b']:7.3f}"
            tail = (f"{r['delta']:+8.3f} {r['se']:7.3f} {r['z']:6.2f}" if "delta" in r else "   (no CI on one side)")
            print(f"  {r['turns']:>8} {r['n_a']:>5} {ra} {r['n_b']:>5} {rb} {tail}")
        print("  se is UNPAIRED (the two runs sample different positions); a bucket's z is descriptive.")
        return

    ceiling = args.ceiling
    if ceiling is None:
        sib = Path(str(args.rows)[:-len(".rows.jsonl")]) if str(args.rows).endswith(".rows.jsonl") else None
        if sib is not None and sib.exists():
            try:
                ceiling = float(json.loads(sib.read_text())["ev_ceiling_unbiased"])
                print(f"ceiling {ceiling:.4f} read from {sib} (ev_ceiling_unbiased)")
            except (KeyError, ValueError, json.JSONDecodeError):
                ceiling = None
    if ceiling is None:
        ceiling = CEILING_UNBIASED
        print(f"WARNING: no sibling variance JSON with ev_ceiling_unbiased -- using RESULTS 27's "
              f"constant {ceiling:.4f}, which is ANOTHER RUN's ceiling")

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
    gap = ceiling - raw
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
        r2, r2_se, r2_lo, r2_hi = r2_bootstrap(v[sel], m[sel], n_boot=args.boot)
        by_turn.append({
            "turns": f"{lo}-{'+' if hi > 999 else hi}", "positions": int(sel.sum()),
            "corr": r, "r2": r2, "r2_se": r2_se, "r2_ci95": [r2_lo, r2_hi],
            "slope": b, "intercept": a,
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
    print(f"  EV ceiling, variance components        {ceiling:.4f}   <- the denominator")
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
    print(f"  {'turns':>8} {'pos':>4} {'corr':>7} {'r^2':>7} {'r2 95% CI':>16} {'slope':>7} {'bias':>8}")
    for b in by_turn:
        print(f"  {b['turns']:>8} {b['positions']:>4} {b['corr']:>+7.3f} {b['r2']:>7.3f} "
              f"[{b['r2_ci95'][0]:.3f}, {b['r2_ci95'][1]:.3f}] {b['slope']:>7.3f} {b['paired_bias']:>+8.4f}")
    print(f"  (r^2 CI: bootstrap over positions, {args.boot} resamples)")

    summary = {
        "label": args.label, "rows": str(args.rows), "ceiling": ceiling,
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

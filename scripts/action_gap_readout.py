#!/usr/bin/env python
"""The READ of scripts/action_gap.py's rows -- the naive ceiling and what noise does to it.

The ceiling `P(top-1 worse) x E[-gap | worse] / 2` is a CONDITIONAL expectation over
noisy per-position gaps, so it is a WINNER'S CURSE: conditioning on a measured
negative selects for negative noise, and a world in which every true gap is ZERO
still prints a positive "ceiling". This script puts the four reads the naive number
needs beside it, all from the rows file (never from memory -- CLAUDE.md landmines):

  1. the naive ceiling and a battle-level bootstrap CI on it;
  2. the NOISE-ONLY counterfactual -- the ceiling that the recorded per-row rollout
     noise produces on its own with every true gap at zero (same n, same se_i);
  3. a Gaussian DECONVOLUTION -- true gaps ~ N(mu, tau^2) with tau^2 = var(measured)
     - mean(se_i^2); the ceiling under the TRUE distribution is E[max(0, -G)] / 2 =
     (tau * phi(mu/tau) - mu * Phi(-mu/tau)) / 2, and P(true gap < 0) = Phi(-mu/tau);
  4. by-turn buckets matching RESULTS §27 (2-8, 9-15, 16-22, 23+), and the count of
     positions whose gap is resolved at 2 se, against the false-positive expectation.

Per-row noise is taken from the RECORDED per-action variances (`var1`, `var2`, `n1`,
`n2`), not from the unit-variance assumption the run summary prints (that prints
sqrt(2/(dets*rollouts)) = 0.204 at 2x24; the recorded variances are ~0.5, so the real
per-row se is ~0.15). Two versions: INDEPENDENT (var1/n1 + var2/n2) and PAIRED, which
subtracts 2*corr_12*sd1*sd2/n -- `corr_12` pairs the two actions' rollouts by index,
and both are laid out determinization-half by determinization-half, so a positive
corr_12 is the shared-world component that cancels in the difference.

    python scripts/action_gap_readout.py results/outcome_variance/action_gap.rows.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

BUCKETS = [(2, 8), (9, 15), (16, 22), (23, 10**6)]


def ceiling(g: np.ndarray) -> float:
    """P(gap < 0) x E[-gap | gap < 0] / 2, in win-rate units (0 when nothing is negative)."""
    w = g < 0
    return float(w.mean() * (-g[w]).mean() / 2.0) if w.any() else 0.0


def gauss_shortfall(mu: float, tau: float) -> float:
    """E[max(0, -G)] for G ~ N(mu, tau^2)."""
    if tau <= 0:
        return max(0.0, -mu)
    z = mu / tau
    phi = math.exp(-z * z / 2.0) / math.sqrt(2.0 * math.pi)
    Phi_neg = 0.5 * (1.0 + math.erf(-z / math.sqrt(2.0)))
    return tau * phi - mu * Phi_neg


def per_row_se(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """(independent se, paired se) per row from the recorded per-action variances."""
    ind, pair = [], []
    for r in rows:
        v1, v2, n1, n2 = r["var1"], r["var2"], r["n1"], r["n2"]
        s2 = v1 / n1 + v2 / n2
        ind.append(math.sqrt(s2))
        c = r.get("corr_12")
        if c is None or not np.isfinite(c):
            pair.append(math.sqrt(s2))
        else:
            n = min(n1, n2)
            pair.append(math.sqrt(max(s2 - 2.0 * c * math.sqrt(v1 * v2) / n, 1e-12)))
    return np.asarray(ind), np.asarray(pair)


def readout(rows: list[dict], boot: int = 20000, seed: int = 0) -> dict:
    g = np.asarray([r["gap"] for r in rows], dtype=np.float64)
    turn = np.asarray([r["turn"] for r in rows])
    n = len(g)
    rng = np.random.default_rng(seed)
    se_ind, se_pair = per_row_se(rows)
    out: dict = {
        "positions": n,
        "battles": len({r["ep"] for r in rows}),
        "top1_is_played_frac": float(np.mean([r["top1_is_played"] for r in rows])),
        "mean_gap": float(g.mean()),
        "se_mean_gap": float(g.std(ddof=1) / math.sqrt(n)),
        "sd_gap": float(g.std(ddof=1)),
        "frac_worse": float((g < 0).mean()),
        "frac_tie": float((g == 0).mean()),
        "frac_better": float((g > 0).mean()),
        "naive_ceiling": ceiling(g),
        "se_row_independent_mean": float(se_ind.mean()),
        "se_row_paired_mean": float(se_pair.mean()),
    }
    bs = np.asarray([ceiling(g[rng.integers(0, n, n)]) for _ in range(boot)])
    out["naive_ceiling_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    for tag, se in (("independent", se_ind), ("paired", se_pair)):
        z = rng.normal(0.0, 1.0, (boot, n)) * se[None, :]
        c = np.asarray([ceiling(zz) for zz in z])
        out[f"noise_only_ceiling_{tag}"] = float(c.mean())
        out[f"noise_only_ceiling_{tag}_ci95"] = [float(np.percentile(c, 2.5)),
                                                 float(np.percentile(c, 97.5))]
        tau2 = float(g.var(ddof=1) - np.mean(se ** 2))
        mu = float(g.mean())
        d = {"tau2": tau2, "mu": mu}
        if tau2 > 0:
            tau = math.sqrt(tau2)
            d["tau"] = tau
            d["p_true_gap_negative"] = 0.5 * (1.0 + math.erf(-(mu / tau) / math.sqrt(2.0)))
            d["deconvolved_ceiling"] = gauss_shortfall(mu, tau) / 2.0
        else:
            d["tau"] = 0.0
            d["p_true_gap_negative"] = 0.0 if mu > 0 else 1.0
            d["deconvolved_ceiling"] = max(0.0, -mu) / 2.0
        out[f"deconvolution_{tag}"] = d
    # resolved rows at 2 se (paired), against the two-sided false-positive expectation
    out["resolved_2se_negative"] = int((g < -2 * se_pair).sum())
    out["resolved_2se_positive"] = int((g > 2 * se_pair).sum())
    out["expected_false_positive_per_side_2se"] = float(n * 0.02275)
    out["by_turn"] = []
    for lo, hi in BUCKETS:
        m = (turn >= lo) & (turn <= hi)
        if m.any():
            out["by_turn"].append({
                "turns": f"{lo}-{hi if hi < 10**6 else '+'}", "n": int(m.sum()),
                "mean_gap": float(g[m].mean()), "frac_worse": float((g[m] < 0).mean()),
                "naive_ceiling": ceiling(g[m])})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rows", nargs="?", default="results/outcome_variance/action_gap.rows.jsonl")
    ap.add_argument("--out", default=None, help="JSON path (default: <rows>.readout.json)")
    ap.add_argument("--boot", type=int, default=20000)
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.rows).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("var1") is not None and r.get("var2") is not None]
    o = readout(rows, boot=args.boot)
    print(f"rows {o['positions']} (battles {o['battles']}); self-check top1_is_played "
          f"{o['top1_is_played_frac']:.3f}")
    print(f"mean gap {o['mean_gap']:+.4f} (se {o['se_mean_gap']:.4f}); sd of gaps {o['sd_gap']:.4f}; "
          f"worse/tie/better {o['frac_worse']:.3f}/{o['frac_tie']:.3f}/{o['frac_better']:.3f}")
    print(f"NAIVE ceiling {o['naive_ceiling']:.4f}  bootstrap 95% "
          f"[{o['naive_ceiling_ci95'][0]:.4f}, {o['naive_ceiling_ci95'][1]:.4f}]")
    print(f"per-row se: independent {o['se_row_independent_mean']:.4f}, paired {o['se_row_paired_mean']:.4f}")
    for tag in ("independent", "paired"):
        d = o[f"deconvolution_{tag}"]
        ci = o[f"noise_only_ceiling_{tag}_ci95"]
        print(f"[{tag}] noise-only ceiling {o[f'noise_only_ceiling_{tag}']:.4f} 95% [{ci[0]:.4f}, {ci[1]:.4f}]"
              f" | tau2 {d['tau2']:+.4f} tau {d['tau']:.4f} P(true gap<0) {d['p_true_gap_negative']:.3f}"
              f" DECONVOLVED ceiling {d['deconvolved_ceiling']:.4f}")
    print(f"resolved at 2 se (paired): {o['resolved_2se_negative']} negative / "
          f"{o['resolved_2se_positive']} positive; expected false positives per side "
          f"{o['expected_false_positive_per_side_2se']:.1f}")
    print("by turn:")
    for b in o["by_turn"]:
        print(f"  {b['turns']:>6}  n {b['n']:3d}  mean gap {b['mean_gap']:+.3f}  "
              f"frac worse {b['frac_worse']:.3f}  naive ceiling {b['naive_ceiling']:.4f}")
    out = args.out or (args.rows + ".readout.json")
    Path(out).write_text(json.dumps(o, indent=2) + "\n")
    print(f"-> {out}")


if __name__ == "__main__":
    main()

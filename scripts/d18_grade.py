"""D18 readout grader: the pre-registered credit line, computed mechanically.

    python scripts/d18_grade.py [--results results/d18]

Ingests final_s{39..43}.json (+ best_s{39..43}.json if present, the val-peak
co-primary) written by eval_checkpoint.py, and grades the PRIMARY exactly as
configs/showdown_sp_priv12m.yaml pre-registers it:

    credit iff pooled delta >= +0.025 AND >= 2*se_diff, se_diff the LARGER of
    pooled-binomial and seed-clustered; comparator Rung 2 12M pooled 0.5509
    (s26 0.5633 / s27 0.5683 / s28 0.5210, 3x3000). Letter-met but not
    credited -> the pre-stated recording rule verbatim. Branch (c) NEGATIVE
    mirrors the same line below the comparator.

The script grades WIN RATE only. The FALSIFIER (EV up + wr flat/negative ->
kill the rung) and the R0-4 cross-check (win_rate == wins_from_returns per
report) need the EV curves and the JSONs' own fields — it prints both
reminders but cannot decide them. No numbers here feed any doc directly:
the log entry quotes this script's output, the header stays the contract.
"""

import argparse
import json
import math
from pathlib import Path

SEEDS = (39, 40, 41, 42, 43)
COMPARATOR_POOLED = 0.5509
COMPARATOR_SEEDS = (0.5633, 0.5683, 0.5210)  # s26/s27/s28, 3000 battles each
COMPARATOR_N = 3000 * len(COMPARATOR_SEEDS)
LETTER = 0.025


def sample_std(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pooled_binomial_se(p, n):
    return math.sqrt(p * (1 - p) / n)


def grade(rates: dict[int, float], n_per_seed: int, label: str) -> None:
    vals = [rates[s] for s in SEEDS]
    pooled = sum(vals) / len(vals)  # equal n per seed -> mean == pooled
    n_total = n_per_seed * len(vals)
    delta = pooled - COMPARATOR_POOLED

    se_binom = math.sqrt(
        pooled_binomial_se(pooled, n_total) ** 2
        + pooled_binomial_se(COMPARATOR_POOLED, COMPARATOR_N) ** 2
    )
    s_comp = sample_std(COMPARATOR_SEEDS)          # 0.0260 -> term 0.0150
    s_d18 = sample_std(vals)
    se_clust = math.sqrt(s_comp**2 / len(COMPARATOR_SEEDS) + s_d18**2 / len(vals))
    se_gov = max(se_binom, se_clust)
    governs = "seed-clustered" if se_clust >= se_binom else "pooled-binomial"

    print(f"\n=== {label} ===")
    for s in SEEDS:
        print(f"  s{s}: {rates[s]:.4f}")
    print(f"  pooled {pooled:.4f}  (comparator {COMPARATOR_POOLED}, delta {delta:+.4f})")
    # Bars at 5 decimals: the header's "floor 0.5809" is a rounded display of
    # the exact comparator-term arithmetic (0.58091); this script credits on
    # the exact rule, so a pooled 0.58090 correctly falls in the recording
    # band while a rounded print would look self-contradictory.
    print(f"  se_diff: binomial {se_binom:.5f} | clustered {se_clust:.5f} "
          f"(D18 spread s={s_d18:.4f}) -> {governs} GOVERNS, 2*se = {2 * se_gov:.5f}")
    print(f"  operative bar: {COMPARATOR_POOLED + max(LETTER, 2 * se_gov):.5f} "
          f"(letter bar {COMPARATOR_POOLED + LETTER:.4f})")

    if label != "PRIMARY (finals)":
        print("  [recorded, NOT credit-bearing — credit is judged on the PRIMARY alone]")
        return

    credited = delta >= LETTER and delta >= 2 * se_gov
    letter_met = delta >= LETTER
    negative = -delta >= LETTER and -delta >= 2 * se_gov
    if credited:
        print("  VERDICT: CREDIT — branch (a). Header next-steps: 50M-scale decision "
              "+ D19 re-scope (maintainer). [Routing stale: D18 read NULL, and "
              "D19 was later killed and re-targeted into D25. See STATUS.md.]")
        if governs == "seed-clustered" and s_d18 > 0.02:
            print("  NOTE: seed spread is Rung-2-like or worse — if credited on the "
                  "clustered line, name the spread in every narrative use (50M lesson).")
    elif negative:
        print("  VERDICT: NEGATIVE — branch (c). Record with the EV curve; the "
              "advantage-scale-shift candidate goes in the log, not in a rerun.")
    elif letter_met:
        print('  VERDICT (pre-stated recording rule): "letter-met, seed-fragile, NOT '
              'credited" — full per-seed detail in the log, no narrative use without '
              "the weakness named.")
    else:
        print("  VERDICT: NULL — branch (b). Queued next: regenerative-L2 rung. The EV "
              "secondary decides the epitaph (EV flat -> could not fit the signal; EV "
              "up + wr flat -> the falsifier fired, kill per its own clause).")
    print("  REMINDERS: (1) falsifier needs the EV trajectory vs control curves — this "
          "script cannot fire it; (2) verify win_rate == wins_from_returns in every "
          "JSON (R0-4); (3) D22-watch grad-norm read + srank secondary still owed.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results/d18")
    args = ap.parse_args()
    root = Path(args.results)

    for prefix, label in (("final", "PRIMARY (finals)"),
                          ("best", "CO-PRIMARY (val-peak re-grades)")):
        paths = {s: root / f"{prefix}_s{s}.json" for s in SEEDS}
        if not all(p.exists() for p in paths.values()):
            missing = [p.name for p in paths.values() if not p.exists()]
            print(f"\n=== {label} === SKIPPED, missing: {', '.join(missing)}")
            continue
        rates, ns, mismatches = {}, set(), []
        for s, p in paths.items():
            r = json.loads(p.read_text())
            rates[s] = r["eval/win_rate"]
            ns.add(r["episodes"])
            if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
                mismatches.append(s)
        if mismatches:
            raise SystemExit(f"R0-4 FAILURE: win_rate != wins_from_returns on seeds "
                             f"{mismatches} — reward-sign bug, the read is VOID")
        if len(ns) != 1:
            raise SystemExit(f"unequal episode counts {ns}: pooling assumes equal n")
        grade(rates, ns.pop(), label)


if __name__ == "__main__":
    main()

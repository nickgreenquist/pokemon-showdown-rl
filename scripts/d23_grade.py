"""D23 readout grader (R0-11): the pre-registered credit line, computed mechanically.

    python scripts/d23_grade.py [--results results/d23]

Ingests, from --results:
  final_s{44,45,46}.json   treatment finals            (PRIMARY)
  best_s{44,45,46}.json    treatment val-peak re-grades (CO-PRIMARY 2, recorded)
  comparator_s{49,50}.json the two FRESH Rung 2 comparator lanes
all in eval_checkpoint.py's JSON schema, and grades exactly what
configs/showdown_sp_l2init12m.yaml pre-registers under the ratified Q1 = 3+2:

    COMPARATOR = 5 seeds at equal n: the three FROZEN Rung 2 12M finals
      (s26 0.5633 / s27 0.5683 / s28 0.5210, 3000 battles each) plus the two
      fresh lanes s49/s50, read from disk. Pooled = the 5-seed mean.
    CREDIT iff pooled treatment delta >= +0.025 AND >= 2*se_diff, se_diff the
      LARGER of pooled-binomial (each pool at its true n) and seed-clustered
      (comparator term sd(5 comparator seeds)/sqrt(5), treatment term
      sd(T)/sqrt(T)).
    FLAT     = delta < +0.025 and not NEGATIVE.
    NEGATIVE = delta <= -max(0.025, 2*se_diff).
    RECORDING RULE: pooled in [letter bar, operative bar) prints the
      pre-stated "letter-met, seed-fragile, NOT credited" verbatim.
    LANE FAILURE RULE: whatever final_s*.json exist among the treatment seeds
      are graded as-is — no replacement lane — with both se terms recomputed
      at the surviving count; fewer than 3 survivors VOIDS the primary (the
      mechanism reads are unaffected and still report).
    R0-4 hard-fail: win_rate != wins_from_returns in ANY ingested JSON
      (treatment or fresh comparator) -> the read is VOID.

The bars are FORMULAS here, not the constants D18 could hardcode: two of the
five comparator seeds and their contribution to the spread are measured at
readout.

This script grades WIN RATE only. The MECHANISM CO-PRIMARY (critic ctx srank99
de-collapse), the MANIPULATION CHECK (species_emb ratio vs the R0-9 control
table in results/d23/control_norms.csv) and the FALSIFIER's partition all need
the d22 scripts' output — it prints the reminders and cannot decide them.

HONESTY RECORD (pre-registered, printed unconditionally, NOT a re-adjudication):
D23 onward grades against the augmented 5-seed comparator while the frozen
0.5509 remains the historical baseline, so the header owes the log a statement
of whether the prior 3-seed verdicts would have changed. That recomputation is
at the bottom of the output.
"""

import argparse
import json
import math
from pathlib import Path

TREATMENT_SEEDS = (44, 45, 46)
# Rung 2 12M, 3000 battles each, frozen 2026-08-05 (STATUS.md's 0.5509 row).
FROZEN_COMPARATOR = {26: 0.5633, 27: 0.5683, 28: 0.5210}
FROZEN_POOLED = 0.5509  # the historical baseline; D18/Rung-3 were graded on it
FRESH_COMPARATOR_SEEDS = (49, 50)
COMPARATOR_N_PER_SEED = 3000
LETTER = 0.025
# D18's cadence-matched control for CO-PRIMARY 2 (config header): pooled
# within-lane final->peak gap, and how many lanes sat at/below +0.01.
D18_PEAK_GAP = 0.0274
D18_PEAK_GAP_TIGHT_LANES = "2-of-5 lanes <= 0.01"
# Historical rungs, per-seed finals at 3000/seed, for the honesty record only.
HISTORICAL = {
    "D18 priv-critic 12M (s39-43)": (
        (0.5610, 0.5477, 0.4740, 0.5623, 0.5370), "NULL"),
    "Rung 3 50M finals (s35-37)": (
        (0.6593333333333333, 0.5726666666666667, 0.5086666666666667), "CREDIT"),
}


def sample_std(xs):
    if len(xs) < 2:
        return float("nan")
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def binom_se(p, n):
    return math.sqrt(p * (1 - p) / n)


def se_terms(t_rates, t_n_total, c_rates, c_n_total):
    """(se_binomial, se_clustered) for a treatment pool vs a comparator pool."""
    p_t = sum(t_rates) / len(t_rates)
    p_c = sum(c_rates) / len(c_rates)
    se_binom = math.sqrt(binom_se(p_t, t_n_total) ** 2 + binom_se(p_c, c_n_total) ** 2)
    s_t, s_c = sample_std(t_rates), sample_std(c_rates)
    se_clust = math.sqrt(s_c**2 / len(c_rates) + s_t**2 / len(t_rates))
    return se_binom, se_clust, s_t, s_c


def read_report(path: Path, r04: list) -> dict:
    r = json.loads(path.read_text())
    if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
        r04.append(path.name)
    return r


def grade(t_rates: dict, t_n: int, c_rates: dict, c_n: int, label: str,
          primary: bool) -> None:
    tv = [t_rates[s] for s in sorted(t_rates)]
    cv = [c_rates[s] for s in sorted(c_rates)]
    pooled = sum(tv) / len(tv)                 # equal n per seed -> mean == pooled
    comparator = sum(cv) / len(cv)
    delta = pooled - comparator
    se_binom, se_clust, s_t, s_c = se_terms(tv, t_n * len(tv), cv, c_n * len(cv))
    se_gov = max(se_binom, se_clust)
    governs = "seed-clustered" if se_clust >= se_binom else "pooled-binomial"
    op_bar = comparator + max(LETTER, 2 * se_gov)

    print(f"\n=== {label} ===")
    for s in sorted(t_rates):
        print(f"  s{s}: {t_rates[s]:.4f}")
    print(f"  treatment pooled {pooled:.4f}  (T = {len(tv)} lanes x {t_n})")
    print("  comparator seeds: " + ", ".join(
        f"s{s} {c_rates[s]:.4f}" for s in sorted(c_rates)))
    print(f"  comparator pooled {comparator:.5f}  ({len(cv)} seeds x {c_n}; "
          f"frozen 3-seed baseline was {FROZEN_POOLED})")
    print(f"  delta {delta:+.4f}")
    # Bars at 5 decimals: the comparator mean and both se terms are measured
    # here, so a rounded print would make a pooled value inside the recording
    # band look self-contradictory against the exact rule the script applies.
    print(f"  se_diff: binomial {se_binom:.5f} | clustered {se_clust:.5f} "
          f"(treatment spread s={s_t:.4f}, comparator spread s={s_c:.4f}) "
          f"-> {governs} GOVERNS, 2*se = {2 * se_gov:.5f}")
    print(f"  operative bar: {op_bar:.5f} (letter bar "
          f"{comparator + LETTER:.5f})")

    if not primary:
        print("  [recorded, NOT credit-bearing — credit is judged on the PRIMARY alone]")
        return

    if len(tv) < 3:
        print(f"  VERDICT: PRIMARY VOID — LANE FAILURE RULE: only {len(tv)} of "
              f"{len(TREATMENT_SEEDS)} treatment lanes survived (<3). The pooled "
              "arithmetic above is recomputed at the surviving count and is "
              "reported for the record, but no credit/null/negative verdict is "
              "available. The MECHANISM reads (srank co-primary, manipulation "
              "check, entropy, D23-watch) are UNAFFECTED and still report.")
        return

    credited = delta >= LETTER and delta >= 2 * se_gov
    letter_met = delta >= LETTER
    negative = -delta >= max(LETTER, 2 * se_gov)
    if credited:
        print("  VERDICT: CREDIT — branch (a). Plasticity is a real 12M binder, "
              "CLAIMABLE ONLY IF the manipulation check reads BOUND (a VOID "
              "manipulation check leaves the credit standing but "
              "'mechanism-unexplained'). Attribution stays open per CONFOUND 1 "
              "(effective-LR) and CONFOUND 3 (entropy); next steps behind the "
              "cap conversation.")
        if governs == "seed-clustered" and s_t > 0.02:
            print("  NOTE: treatment spread is Rung-2-like or worse — name it in "
                  "every narrative use (50M lesson).")
    elif negative:
        print("  VERDICT: NEGATIVE — branch (c). The penalty costs capability at "
              "the closed-form lambda; record entropy + R1 curves + lambda. NO "
              "smaller-lambda rerun (D17 + the one-lever rule). D19 next.")
    elif letter_met:
        print('  VERDICT (pre-stated recording rule): "letter-met, seed-fragile, '
              'NOT credited" — full per-seed detail in the log, no narrative use '
              "without the weakness named.")
    else:
        print("  VERDICT: FLAT/NULL — branch (b) (delta < +0.025 and not "
              "NEGATIVE). The epitaph is the FALSIFIER's, not this script's: "
              "BOUND + srank fails -> regenerative family CLOSED FOR THIS "
              "CHAPTER AT 12M; BOUND + srank recovers -> representation health "
              "is not the 12M binder, same closure; NOT BOUND (incl. VOID) -> "
              "the read is VOID on the lever, D19 first and a stronger-lambda "
              "re-run queued behind it. Queue moves to D19 either way.")
    print("  REMINDERS: (1) the FALSIFIER needs the manipulation check "
          "(BOUND/NOT BOUND/VOID/OVERBOUND) and the srank co-primary — this "
          "script cannot fire it; (2) R0-4 was checked on every JSON ingested "
          "here; (3) D23-watch grad-norm read, entropy band (SECONDARY 4) and "
          "blowup incidence (SECONDARY 3) still owed.")


def verdict_of(delta: float, se_gov: float) -> str:
    if delta >= LETTER and delta >= 2 * se_gov:
        return "CREDIT"
    if -delta >= max(LETTER, 2 * se_gov):
        return "NEGATIVE"
    if delta >= LETTER:
        return "letter-met, seed-fragile, NOT credited"
    return "NULL"


def honesty_record(c_rates: dict, c_n: int) -> None:
    """Did augmenting the comparator change any prior verdict?

    The question is only answerable if the SAME rule is applied to both
    comparators, so each rung is regraded twice by this script's own line and
    the two are compared. The RECORDED verdict is printed alongside but is not
    the comparison: Rung 3's credit was adjudicated in its own era, before the
    larger-of clause the credit line now carries, so a difference between the
    recorded verdict and this script's frozen-comparator recomputation is an
    era effect, not a comparator effect.
    """
    cv = [c_rates[s] for s in sorted(c_rates)]
    fv = [FROZEN_COMPARATOR[s] for s in sorted(FROZEN_COMPARATOR)]
    aug = sum(cv) / len(cv)
    print("\n=== FROZEN vs AUGMENTED COMPARATOR (honesty record, NOT a "
          "re-adjudication) ===")
    froz = sum(fv) / len(fv)
    print(f"  frozen 3-seed pooled {froz:.5f} (published as {FROZEN_POOLED}; "
          f"spread s={sample_std(fv):.4f})  ->  augmented {len(cv)}-seed pooled "
          f"{aug:.5f} (spread s={sample_std(cv):.4f})  "
          f"shift {aug - froz:+.5f}")
    print("  D18 and Rung 3 were graded against the frozen comparator and are "
          "NOT re-opened. Regraded by THIS script's line against each "
          "comparator:")
    for name, (rates, recorded) in HISTORICAL.items():
        pooled = sum(rates) / len(rates)
        n_t = 3000 * len(rates)
        out = {}
        for tag, pool in (("frozen", fv), ("augmented", cv)):
            mean = sum(pool) / len(pool)
            d = pooled - mean
            se_b, se_c, _, _ = se_terms(rates, n_t, pool, c_n * len(pool))
            se_gov = max(se_b, se_c)
            out[tag] = (d, se_gov, verdict_of(d, se_gov),
                        mean + max(LETTER, 2 * se_gov))
        changed = ("UNCHANGED" if out["frozen"][2] == out["augmented"][2]
                   else "WOULD CHANGE")
        print(f"  {name}: pooled {pooled:.4f} (recorded verdict at the time: "
              f"{recorded})")
        for tag in ("frozen", "augmented"):
            d, se_gov, v, bar = out[tag]
            print(f"      vs {tag:9s} comparator: delta {d:+.4f}, 2*se "
                  f"{2 * se_gov:.5f}, operative bar {bar:.5f} -> {v}")
        print(f"      augmentation effect: {changed}")
    print("  NOTE: where a regrade differs from the RECORDED verdict, the cause "
          "is the era's line, not the comparator — Rung 3's credit predates the "
          "larger-of (binomial vs seed-clustered) clause and its 3-lane spread "
          "(s=0.0754) dominates the clustered term under today's rule. Recorded "
          "verdicts stand; this block exists so the log can say so explicitly.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results/d23")
    args = ap.parse_args()
    root = Path(args.results)
    r04: list[str] = []

    # --- comparator: 3 frozen + however many fresh lanes are on disk ---------
    comparator = dict(FROZEN_COMPARATOR)
    fresh_missing = []
    for s in FRESH_COMPARATOR_SEEDS:
        p = root / f"comparator_s{s}.json"
        if not p.exists():
            fresh_missing.append(p.name)
            continue
        r = read_report(p, r04)
        if r["episodes"] != COMPARATOR_N_PER_SEED:
            raise SystemExit(
                f"{p.name}: episodes={r['episodes']} != {COMPARATOR_N_PER_SEED} — "
                "the 5-seed comparator pools as an equal-n mean; a different n "
                "needs a weighted pool the pre-registration does not authorize"
            )
        comparator[s] = r["eval/win_rate"]
    if fresh_missing:
        print(f"WARNING: fresh comparator lane(s) missing ({', '.join(fresh_missing)}) "
              f"— grading against {len(comparator)} comparator seeds. The ratified "
              "design is 3+2; a short comparator weakens the clustered term the "
              "Q1 reallocation was bought to repair. Say so in the log.")

    # --- treatment: LANE FAILURE RULE — take whatever survived ---------------
    finals, bests = {}, {}
    for s in TREATMENT_SEEDS:
        pf, pb = root / f"final_s{s}.json", root / f"best_s{s}.json"
        if pf.exists():
            finals[s] = read_report(pf, r04)
        if pb.exists():
            bests[s] = read_report(pb, r04)
    if r04:
        raise SystemExit(
            f"R0-4 FAILURE: win_rate != wins_from_returns in {sorted(r04)} — "
            "reward-sign bug, the read is VOID"
        )
    lost = [s for s in TREATMENT_SEEDS if s not in finals]
    if lost:
        print(f"LANE FAILURE RULE in effect: no final_s*.json for seed(s) {lost} "
              f"— reported as-is, NO replacement lane; both se terms recompute at "
              f"the {len(finals)} surviving lane(s).")
    if not finals:
        raise SystemExit(f"no final_s*.json for seeds {TREATMENT_SEEDS} under {root}")

    for reports, label, primary in ((finals, "PRIMARY (finals)", True),
                                    (bests, "CO-PRIMARY 2 (val-peak re-grades)", False)):
        if not reports:
            print(f"\n=== {label} === SKIPPED, no JSONs under {root}")
            continue
        ns = {r["episodes"] for r in reports.values()}
        if len(ns) != 1:
            raise SystemExit(f"unequal episode counts {ns}: pooling assumes equal n")
        grade({s: r["eval/win_rate"] for s, r in reports.items()}, ns.pop(),
              comparator, COMPARATOR_N_PER_SEED, label, primary)

    # --- CO-PRIMARY 2's actual mechanism read: the WITHIN-LANE gap -----------
    paired = sorted(set(finals) & set(bests))
    if paired:
        gaps = {s: bests[s]["eval/win_rate"] - finals[s]["eval/win_rate"] for s in paired}
        pooled_gap = sum(gaps.values()) / len(gaps)
        print("\n=== CO-PRIMARY 2, within-lane final->peak gap (the "
              "cadence-matched read) ===")
        print("  " + ", ".join(f"s{s} {gaps[s]:+.4f}" for s in paired))
        print(f"  pooled gap {pooled_gap:+.4f}  vs D18 control {D18_PEAK_GAP:+.4f} "
              f"({D18_PEAK_GAP_TIGHT_LANES}); cadence matched at 500k/1000")
        print(f"  MECHANISM PREDICTION: the gap SHRINKS. Realized "
              f"{'SHRUNK' if pooled_gap < D18_PEAK_GAP else 'GREW OR HELD'} "
              f"({pooled_gap - D18_PEAK_GAP:+.4f} vs D18).")
        print("  SELECTION CONFOUND (carried from D18, directionally "
              "ADVERSARIAL): best_checkpoint selects on eval/return_mean over 24 "
              "evals, and CONFOUND 3 predicts the lever raises entropy -> raises "
              "eval-return variance -> widens the max-of-24 artifact -> pushes "
              "the gap UP. A shrunken gap is therefore evidence; a grown gap is "
              "confounded.")

    honesty_record(comparator, COMPARATOR_N_PER_SEED)


if __name__ == "__main__":
    main()

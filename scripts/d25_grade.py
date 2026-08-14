"""D25 readout grader (R0-14): the pre-registered lines, computed mechanically.

    python scripts/d25_grade.py [--results results/d25] [--atoms PATH]
                                [--dormancy PATH] [--s1-control PATH ...]

Implements, verbatim from configs/showdown_sp_actpred12m.yaml:

  R0-15 ATTESTATION, FIRST AND UNCONDITIONALLY — before any treatment number
    is loaded, the five comparator finals are re-read from disk and printed
    with the derived 0.54452 / 0.03558, and the frozen §5 control atoms (BOTH
    label spaces) and reference-tape sha256s are printed in the same pass.
    Any mismatch against the frozen constants is a hard stop.
  PRIMARY (co-primary A, win rate): CREDIT iff pooled delta >= +0.025 AND
    >= 2*se_diff, se_diff the LARGER of pooled-binomial and seed-clustered,
    the latter from the per-seed finals at read time (§4).
    RECORDING RULE: pooled in [0.54452+0.025, operative bar) -> "letter-met,
    seed-fragile, NOT credited". FLAT: delta < +0.025 and not NEGATIVE.
    NEGATIVE: pooled <= 0.54452 - max(0.025, 2*se_diff).
    LANE FAILURE RULE: missing final_s*.json are reported as-is, NO
    replacement; BOTH se terms recompute at the surviving count; fewer than
    3 surviving lanes VOIDS the primary (mechanism reads still report).
    R0-4 HARD FAIL: win_rate != wins_from_returns in ANY ingested JSON.
    M4 OBLIGATIONS fire on the NUMBER (pooled >= 0.558), not the verdict.
  CO-PRIMARY B (Delta_ref-ctx, §5): exact one-sided permutation on the
    difference of means, treatment HIGHER, enumerated over all assignments,
    at the pre-stated level for whatever n_T survives — 5 -> 12/252,
    4 -> 6/126, 3 -> 2/56, VOID below 3. Graded in the L6 PRIMARY space and
    reported in the 12-class secondary space (both letters graded and
    reported; the L6 one is PRIMARY).
  S1 (actor ctx_net.1 dormancy at tau 0.025, 12M): same exact permutation,
    same levels by n_T, treatment LOWER. The letter is BLOCKED until R0-16
    lands the s50/s51 control extension (n_C must be 5).

Inputs:
  --results   directory holding treatment finals final_s{52..56}.json in
              eval_checkpoint.py's schema (3000 battles/seed).
  --atoms     JSON {"L6": {"52": <8-split-mean Delta_ref-ctx>, ...},
              "c12": {...}} for the treatment lanes, from the post-run probe
              pass on the frozen s36 reference tape (same probe as
              d25_gates.py verify). Section skipped if absent.
  --dormancy  CSV in d22_dormant_rank.py's schema for the treatment lanes;
              the S1 read is part=actor, layer=ctx_net.1, step=12000000,
              column tau025. Section skipped if absent.
  --s1-control  repeatable CSV path(s) for the control dormancy rows (d23's
              file plus, once R0-16 runs, the s50/s51 extension).

This script grades win rate and the two permutation letters. The §6
manipulation check (median g vs the 0.3286 LEARNED bar), the falsifier
partition and the secondaries need the tape/probe pipeline's output — it
prints the reminders and cannot decide them.
"""

import argparse
import csv
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TREATMENT_SEEDS = (52, 53, 54, 55, 56)
N_PER_SEED = 3000
LETTER = 0.025
M4_BAR = 0.558

# --- frozen comparator (§4): five Rung-2 12M finals, re-read from disk -------
COMPARATOR_PATHS = {
    26: REPO / "runs/showdown_sp_struct12m_s26/final_eval_3000.json",
    27: REPO / "runs/showdown_sp_struct12m_s27/final_eval_3000.json",
    28: REPO / "runs/showdown_sp_struct12m_s28/final_eval_3000.json",
    50: REPO / "results/d23/comparator_s50.json",
    51: REPO / "results/d23/comparator_s51.json",
}
FROZEN_COMPARATOR = {26: 0.5633, 27: 0.5683, 28: 0.5210, 50: 0.5763, 51: 0.4937}
FROZEN_POOLED = 0.54452
FROZEN_SD = 0.03558

# --- frozen §5 control atoms (Delta_ref-ctx on the s36 reference tape) -------
CONTROL_L6 = {26: 0.0217, 27: 0.0072, 28: 0.0201, 50: 0.0114, 51: 0.0145}
CONTROL_12C = {26: 0.0195, 27: 0.0071, 28: 0.0246, 50: 0.0149, 51: 0.0143}
TAPE_SHA = {
    "s36": "3ffee9ba8f0c8fd826573ecb0a2334e249f73ae914720035f3fd839ffe074917",
    "s37": "58e64af1d57705bb5981c3465a03527244fd59ca113dabc35ca66af1dc39483f",
}

# --- S1 frozen control (results/d23/dormant_control.csv, actor ctx_net.1
# tau025 at 12M); the s50/s51 extension is R0-16's and is read from disk ------
S1_FROZEN_CONTROL = {26: 0.4844, 27: 0.5000, 28: 0.6432}
S1_CONTROL_SEEDS = (26, 27, 28, 50, 51)

# --- pre-stated permutation levels by surviving n_T against n_C = 5 (§5) -----
PERM_LEVELS = {5: (12, 252), 4: (6, 126), 3: (2, 56)}


def sample_std(xs):
    if len(xs) < 2:
        return float("nan")
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def se_terms(t_rates, t_n_total, c_rates, c_n_total):
    """(se_binomial, se_clustered, s_t, s_c), both pools at their true n."""
    p_t = sum(t_rates) / len(t_rates)
    p_c = sum(c_rates) / len(c_rates)
    se_binom = math.sqrt(p_t * (1 - p_t) / t_n_total + p_c * (1 - p_c) / c_n_total)
    s_t, s_c = sample_std(t_rates), sample_std(c_rates)
    se_clust = math.sqrt(s_c**2 / len(c_rates) + s_t**2 / len(t_rates))
    return se_binom, se_clust, s_t, s_c


def exact_perm_p(t_vals, c_vals, direction):
    """Exact one-sided permutation p on the difference of means.

    direction=+1: treatment HIGHER is extreme (§5). -1: LOWER (S1).
    Enumerates all C(n_T+n_C, n_T) assignments; assignments tied with the
    observed statistic count as extreme (conservative). Returns
    (count, total, p).
    """
    t_vals, c_vals = list(t_vals), list(c_vals)
    n_t, n_c = len(t_vals), len(c_vals)
    combined = t_vals + c_vals
    total_sum = sum(combined)
    # mean_T - mean_C is strictly monotone in sum_T at fixed group sizes.
    obs = direction * sum(t_vals)
    count = total = 0
    for idx in combinations(range(n_t + n_c), n_t):
        total += 1
        if direction * sum(combined[i] for i in idx) >= obs - 1e-12:
            count += 1
    return count, total, count / total


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_report(path: Path, r04: list) -> dict:
    r = json.loads(path.read_text())
    if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
        r04.append(path.name)
    return r


# ---------------------------------------------------------------------------
# R0-15 — the attestation pass. Runs FIRST; loads no treatment number.
# ---------------------------------------------------------------------------


def attest(comparator_paths=COMPARATOR_PATHS, tape_dir=None) -> dict:
    """Re-read the comparator finals from disk, print + verify the frozen
    constants and tape sha256s. Returns {seed: win_rate} (exact, from disk).
    Hard-stops on any mismatch."""
    tape_dir = Path(tape_dir) if tape_dir else REPO / "results" / "d25"
    print("=== R0-15 FROZEN-COMPARATOR ATTESTATION (before any treatment "
          "number is loaded) ===")
    r04: list = []
    rates = {}
    for s, p in sorted(comparator_paths.items()):
        if not p.exists():
            raise SystemExit(f"ATTESTATION FAILED: comparator final missing: {p}")
        r = read_report(p, r04)
        if r["episodes"] != N_PER_SEED:
            raise SystemExit(f"ATTESTATION FAILED: {p.name} episodes="
                             f"{r['episodes']} != {N_PER_SEED}")
        rates[s] = r["eval/win_rate"]
        if abs(rates[s] - FROZEN_COMPARATOR[s]) > 5e-5:
            raise SystemExit(f"ATTESTATION FAILED: s{s} disk {rates[s]:.6f} != "
                             f"frozen {FROZEN_COMPARATOR[s]}")
        print(f"  s{s}: {rates[s]:.4f}  ({p.relative_to(REPO)})")
    if r04:
        raise SystemExit(f"R0-4 FAILURE in comparator pool: {sorted(r04)}")
    vals = [rates[s] for s in sorted(rates)]
    mean, sd = sum(vals) / len(vals), sample_std(vals)
    print(f"  derived: pooled {mean:.5f} (frozen {FROZEN_POOLED}), "
          f"sd {sd:.5f} (frozen {FROZEN_SD})")
    if abs(mean - FROZEN_POOLED) > 1e-4 or abs(sd - FROZEN_SD) > 1e-4:
        raise SystemExit("ATTESTATION FAILED: derived comparator statistics "
                         "do not match the frozen 0.54452 / 0.03558")

    print("\n  frozen §5 control atoms (Delta_ref-ctx, s36 reference):")
    for name, atoms in (("L6-native (PRIMARY)", CONTROL_L6),
                        ("12-class (secondary)", CONTROL_12C)):
        vs = [atoms[s] for s in sorted(atoms)]
        print(f"    {name}: " + " ".join(
            f"s{s} {atoms[s]:+.4f}" for s in sorted(atoms))
            + f"  -> mean {sum(vs)/len(vs):+.4f}, sd {sample_std(vs):.4f}")

    print("\n  reference tape sha256:")
    for name, want in TAPE_SHA.items():
        p = tape_dir / f"oppact_{name}ref.npz"
        if not p.exists():
            raise SystemExit(f"ATTESTATION FAILED: frozen tape missing: {p} "
                             "(results/d25 is the ONLY copy)")
        got = sha256(p)
        flag = "OK" if got == want else "!! MISMATCH !!"
        print(f"    {name}: {got}  {flag}")
        if got != want:
            raise SystemExit(f"ATTESTATION FAILED: {p} is not the frozen tape")
    print("  ATTESTATION PASS")
    return rates


# ---------------------------------------------------------------------------
# PRIMARY — co-primary A, win rate (§4)
# ---------------------------------------------------------------------------


def grade_primary(t_rates: dict, c_rates: dict, t_n: int = N_PER_SEED,
                  c_n: int = N_PER_SEED) -> str:
    tv = [t_rates[s] for s in sorted(t_rates)]
    cv = [c_rates[s] for s in sorted(c_rates)]
    pooled = sum(tv) / len(tv)              # equal n per seed -> mean == pooled
    comparator = sum(cv) / len(cv)
    delta = pooled - comparator
    se_binom, se_clust, s_t, s_c = se_terms(tv, t_n * len(tv), cv, c_n * len(cv))
    se_gov = max(se_binom, se_clust)
    governs = "seed-clustered" if se_clust >= se_binom else "pooled-binomial"
    letter_bar = comparator + LETTER
    op_bar = comparator + max(LETTER, 2 * se_gov)

    print("\n=== PRIMARY — co-primary A, win rate vs SH ===")
    for s in sorted(t_rates):
        print(f"  s{s}: {t_rates[s]:.4f}")
    print(f"  treatment pooled {pooled:.4f}  (T = {len(tv)} lanes x {t_n})")
    print(f"  comparator pooled {comparator:.5f}  ({len(cv)} seeds x {c_n})")
    print(f"  delta {delta:+.4f}")
    print(f"  se_diff: binomial {se_binom:.5f} | clustered {se_clust:.5f} "
          f"(treatment spread s={s_t:.4f}, comparator s={s_c:.4f}) "
          f"-> {governs} GOVERNS, 2*se = {2 * se_gov:.5f}")
    print(f"  letter bar {letter_bar:.5f} | operative bar {op_bar:.5f}")

    if len(tv) < 3:
        verdict = "VOID"
        print(f"  VERDICT: PRIMARY VOID — LANE FAILURE RULE: only {len(tv)} of "
              f"{len(TREATMENT_SEEDS)} treatment lanes survived (<3). The "
              "arithmetic above is recomputed at the surviving count for the "
              "record; no credit/flat/negative verdict is available. The "
              "mechanism reads (§5, S1) still report at their own levels.")
    elif delta >= LETTER and delta >= 2 * se_gov:
        verdict = "CREDIT"
        print("  VERDICT: CREDIT — branch (a). IMMEDIATE OBLIGATIONS, NOT "
              "OPTIONS: the M4 clone re-score and the non-SH anchor "
              "head-to-heads (§4). The claim is bounded by §5's CLAIM BOUND "
              "and by the placebo scope (§12): without the shuffled-label arm "
              "the licensed claim is 'an auxiliary loss helps', not 'an "
              "explicit opponent model helps'.")
        if governs == "seed-clustered" and s_t > 0.02:
            print("  NOTE: treatment spread is Rung-2-like or worse — name it "
                  "in every narrative use (50M lesson).")
    elif -delta >= max(LETTER, 2 * se_gov):
        verdict = "NEGATIVE"
        print("  VERDICT: NEGATIVE — the aux loss at coef 0.1 costs "
              "capability. Record entropy + R1 curves; NO coefficient re-tune "
              "and NO relaunch (D17 + one-lever).")
    elif delta >= LETTER:
        verdict = "letter-met, seed-fragile, NOT credited"
        print('  VERDICT (pre-stated recording rule): "letter-met, '
              'seed-fragile, NOT credited" — full per-seed detail in the log, '
              "no narrative use without the weakness named. This is the "
              "chapter's third visit to this band if it lands here.")
    else:
        verdict = "FLAT"
        print("  VERDICT: FLAT — delta < +0.025 and not NEGATIVE. The modal "
              "pre-stated outcome (§8); the rung's decisive read is the "
              "mechanism co-primary, not this number.")

    if len(tv) >= 3 and pooled >= M4_BAR:
        print(f"\n  M4 TRIGGER: pooled {pooled:.4f} >= {M4_BAR} — DESIGN §2 "
              "obligations FIRE ON THE NUMBER, regardless of the verdict "
              "above. M4 may not be claimed until BOTH are discharged:")
        print("    (i) clone re-score at 5x3000 under the locked protocol — "
              "if it lands above D25's pooled final, M4 is NOT claimed;")
        print("    (ii) SH-exploitation falsifier: two-orientation "
              "head-to-head vs the clone, 500/pair/orientation.")
    return verdict


# ---------------------------------------------------------------------------
# CO-PRIMARY B (§5) and S1 (§7) — exact permutation letters
# ---------------------------------------------------------------------------


def grade_permutation(t_atoms: dict, c_atoms: dict, label: str, direction: int,
                      graded: bool = True) -> str:
    """Exact one-sided permutation at the pre-stated level for surviving n_T.
    direction=+1 treatment HIGHER (§5); -1 treatment LOWER (S1)."""
    n_t = len(t_atoms)
    print(f"\n=== {label} ===")
    for s in sorted(t_atoms):
        print(f"  s{s}: {t_atoms[s]:+.4f}")
    cv = [c_atoms[s] for s in sorted(c_atoms)]
    tv = [t_atoms[s] for s in sorted(t_atoms)]
    print("  control: " + " ".join(f"s{s} {c_atoms[s]:+.4f}"
                                   for s in sorted(c_atoms)))
    mean_t, mean_c = sum(tv) / len(tv), sum(cv) / len(cv)
    print(f"  means: treatment {mean_t:+.4f} vs control {mean_c:+.4f} "
          f"(one-sided, treatment {'HIGHER' if direction > 0 else 'LOWER'})")

    if n_t < 3:
        print(f"  VERDICT: VOID — n_T = {n_t} < 3 (pre-stated floor).")
        return "VOID"
    if len(cv) != 5:
        print(f"  VERDICT: NOT GRADED — n_C = {len(cv)} != 5; the pre-stated "
              "levels are enumerated against 5 controls.")
        return "NOT GRADED"
    k_level, expected_total = PERM_LEVELS[n_t]
    count, total, p = exact_perm_p(tv, cv, direction)
    assert total == expected_total, (total, expected_total)
    fired = p <= k_level / expected_total
    print(f"  exact permutation p = {count}/{total} = {p:.6f}  vs level "
          f"{k_level}/{expected_total} = {k_level / expected_total:.6f} "
          f"(n_T = {n_t})")
    if not graded:
        print(f"  {'letter-met' if fired else 'not met'} — REPORTED, NOT "
              "GRADED (the L6 letter is PRIMARY).")
        return "reported"
    if fired:
        print("  LETTER FIRED." + (
            "" if n_t == 5 else f" Recorded WITH ITS LEVEL (n_T = {n_t}); "
            "explicitly not equal-strength evidence (no power simulation "
            "exists below n_T = 5)."))
        return "FIRED"
    print("  LETTER NOT FIRED.")
    return "not fired"


def read_dormancy_csv(paths, seeds, step=12_000_000) -> dict:
    """actor ctx_net.1 tau025 at `step` for `seeds`, from d22-schema CSVs."""
    out = {}
    for path in paths:
        with open(path) as f:
            for row in csv.DictReader(f):
                if (int(row["seed"]) in seeds and int(row["step"]) == step
                        and row["part"] == "actor"
                        and row["layer"] == "ctx_net.1"):
                    out[int(row["seed"])] = float(row["tau025"])
    return out


# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results/d25")
    ap.add_argument("--atoms", default="results/d25/treatment_atoms.json")
    ap.add_argument("--dormancy", default="results/d25/dormant.csv")
    ap.add_argument("--s1-control", action="append",
                    default=["results/d23/dormant_control.csv"])
    args = ap.parse_args()
    root = Path(args.results)

    # R0-15: attestation first, unconditionally, before any treatment read.
    comparator = attest()

    # --- treatment finals: LANE FAILURE RULE — take whatever survived --------
    r04: list = []
    finals = {}
    for s in TREATMENT_SEEDS:
        p = root / f"final_s{s}.json"
        if p.exists():
            finals[s] = read_report(p, r04)
    if r04:
        raise SystemExit(f"R0-4 FAILURE: win_rate != wins_from_returns in "
                         f"{sorted(r04)} — reward-sign bug, the read is VOID")
    if not finals:
        raise SystemExit(f"no final_s*.json for seeds {TREATMENT_SEEDS} "
                         f"under {root}")
    lost = [s for s in TREATMENT_SEEDS if s not in finals]
    if lost:
        print(f"\nLANE FAILURE RULE in effect: no final_s*.json for seed(s) "
              f"{lost} — reported as-is, NO replacement lane; both se terms "
              f"recompute at the {len(finals)} surviving lane(s).")
    ns = {r["episodes"] for r in finals.values()}
    if ns != {N_PER_SEED}:
        raise SystemExit(f"treatment episode counts {ns} != {{{N_PER_SEED}}}: "
                         "the pool is an equal-n mean at 3000/seed")
    grade_primary({s: r["eval/win_rate"] for s, r in finals.items()}, comparator)

    # --- co-primary B: Delta_ref-ctx permutation, both label spaces ----------
    atoms_path = Path(args.atoms)
    if atoms_path.exists():
        atoms = json.loads(atoms_path.read_text())
        grade_permutation({int(s): v for s, v in atoms["L6"].items()},
                          CONTROL_L6,
                          "CO-PRIMARY B — Delta_ref-ctx, L6-native (PRIMARY)",
                          direction=+1)
        if "c12" in atoms:
            grade_permutation({int(s): v for s, v in atoms["c12"].items()},
                              CONTROL_12C,
                              "CO-PRIMARY B — 12-class (free secondary)",
                              direction=+1, graded=False)
    else:
        print(f"\nCO-PRIMARY B: SKIPPED — no atoms file at {atoms_path} (owed "
              "from the post-run probe pass on the frozen s36 tape).")

    # --- S1: dormancy permutation, treatment LOWER ---------------------------
    dorm_path = Path(args.dormancy)
    if dorm_path.exists():
        t_dorm = read_dormancy_csv([dorm_path], TREATMENT_SEEDS)
        c_dorm = read_dormancy_csv([p for p in args.s1_control
                                    if Path(p).exists()], S1_CONTROL_SEEDS)
        for s, want in S1_FROZEN_CONTROL.items():
            if s in c_dorm and abs(c_dorm[s] - want) > 5e-5:
                raise SystemExit(f"S1 control drift: s{s} disk {c_dorm[s]:.4f}"
                                 f" != frozen {want}")
        missing = [s for s in S1_CONTROL_SEEDS if s not in c_dorm]
        if missing:
            print(f"\nS1: control seeds {missing} missing from "
                  f"{args.s1_control} — the R0-16 extension is OWED and "
                  "BLOCKS the S1 letter.")
        if t_dorm:
            grade_permutation(t_dorm, c_dorm,
                              "S1 — actor ctx_net.1 dormancy (tau 0.025, 12M)",
                              direction=-1)
    else:
        print(f"\nS1: SKIPPED — no treatment dormancy CSV at {dorm_path}.")

    print("\nREMINDERS (this script cannot decide them): (1) §6 manipulation "
          "check — median g vs LEARNED bar 0.3286, WEAK [0.10, 0.3286), VOID "
          "< 0.10, g re-derived per lane with A1/A3 from the lane's own tape; "
          "g > 1.0 is a HARD FAIL unless the per-member oracle explains it. "
          "(2) The falsifier partition (§8) needs §6 + co-primary B together. "
          "(3) VOID clause on grad_norm/grad_clip_frac compares WHOLE-RUN "
          "means at matched steps, not mid-run values. (4) Placebo scope "
          "(§12): without the shuffled-label arm, credit licenses 'an aux "
          "loss helps', not 'an opponent model helps'. (5) C10: whether the "
          "§0 tapes include forced post-faint replacements is UNDETERMINED "
          "and must be settled before the readout.")


if __name__ == "__main__":
    main()

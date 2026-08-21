"""D28 readout grader — the zero-information dose control
(configs/showdown_sp_zeroinfo12m.yaml). Committed BEFORE launch (R0-c).

Reads (header verbatim):
  R-1 PRIMARY   Delta_1 = frozen D25 pooled - control pooled, one-sided upper
                -> A1..A5 (A3 is the ONLY two-sided cell, deliberately).
  R-2 SECONDARY Delta_2 = control pooled - frozen Rung-2 pooled, one-sided
                upper -> S-a / S-b / S-c (modifies A1 only).
  SEALING       A1 AND Delta_2 >= 0 (operationalised; dose cell qualifies
                the sentence).
Both frozen comparator sets are ATTESTED from disk on every run; the
lane-failure rule is D25's verbatim (<3 survivors VOIDS the primary).
Dose cells (r_bar over the frozen per-bin envelope), the late-window
trunk-fraction band, clip-neutrality, and the manipulation check g are
computed from each lane's history.csv (extract first) — this grader prints
every cell; VERDICT ROUTING IS THE HEADER'S BRANCH TABLE, not ad-hoc prose.

    python scripts/d28_grade.py                # after results/d28/final_s7*.json
    python scripts/d28_grade.py --selftest     # known-answer checks, no run files
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from d25_grade import exact_perm_p, se_terms  # noqa: E402  (unchanged)

REPO = Path(__file__).resolve().parents[1]

# 7-decimal frozen values; attest() re-derives from disk, hard-stops on drift.
R1_D25 = {52: 0.6233333, 53: 0.6573333, 54: 0.6063333,
          55: 0.6073333, 56: 0.5980000}                       # pooled 0.618467
R2_RUNG2 = {26: 0.5633333, 27: 0.5683333, 28: 0.5210000,
            50: 0.5763333, 51: 0.4936667}                     # pooled 0.5445333
R1_PATHS = {s: REPO / f"results/d25/final_s{s}.json" for s in R1_D25}
R2_PATHS = {
    26: REPO / "runs/showdown_sp_struct12m_s26/final_eval_3000.json",
    27: REPO / "runs/showdown_sp_struct12m_s27/final_eval_3000.json",
    28: REPO / "runs/showdown_sp_struct12m_s28/final_eval_3000.json",
    50: REPO / "results/d23/comparator_s50.json",
    51: REPO / "results/d23/comparator_s51.json",
}
SEEDS = (70, 71, 72, 73, 74)
FLOOR = 0.025

# Frozen dose machinery (header + results/design_ch2/d28_dose_ratio_bins.json).
DOSE_MID = {0: 0.1229, 1: 0.1056, 2: 0.0958, 3: 0.0947, 4: 0.0921, 5: 0.0946,
            6: 0.0986, 7: 0.1003, 8: 0.1054, 9: 0.1076, 10: 0.1128, 11: 0.1200}
F_LATE_BAND = (0.45, 0.70)   # bin-11 per-lane median trunk fraction
CLIP_NEUTRAL = 0.99          # run-mean aux/clip_scale floor
ABORT_F = 0.35               # 6M fleet-median threshold (in-run; recorded here)
# Manipulation-check bar: 0.80 x mean(frozen-probe g) over the 10 banked
# tapes at the frozen constants (z1_2_frozen.json "g_bar": per-tape g
# 0.608-0.765, mean 0.67922, no g>1.0; aux-trained and comparator lanes
# overlap — no generator dependence). D25's own bar was 0.371; this task's
# is higher because the frozen linear task is easier to fit.
G_VOID, G_BAR = 0.10, 0.54338


def attest() -> None:
    for frozen, paths in ((R1_D25, R1_PATHS), (R2_RUNG2, R2_PATHS)):
        for s, want in frozen.items():
            r = json.loads(paths[s].read_text())
            got = r["eval/win_rate"]
            if abs(got - want) > 5e-7:
                raise SystemExit(
                    f"ATTESTATION FAILED: {paths[s]} win_rate {got!r} != frozen "
                    f"{want} — comparator moved/corrupted; grade refused.")
            if r.get("episodes") != 3000:
                raise SystemExit(
                    f"ATTESTATION FAILED: {paths[s]} episodes != 3000")


def _fleet_median(vals):
    """Named aggregator (pre-reg lesson 1): median across surviving lanes;
    at an even count, the MEAN of the two central values."""
    v = sorted(vals)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def dose_cells(hist_csv: Path):
    """Per-lane dose reads off an extracted history.csv: (per-bin q dict,
    r_bar, f_late, clip_mean, g). q_b = (bin-b median delivered ratio) /
    DOSE_MID[b]; g uses the memorisation-free loss_mb0 vs the synthetic
    marginal and sampler entropy over the FINAL-1M window (unit-compatible
    with the held-out frozen-probe bar; review MF-4)."""
    import pandas as pd
    df = pd.read_csv(hist_csv, low_memory=False)
    d = df[["_step", "aux/trunk_norm_delivered", "aux/policy_trunk_norm",
            "aux/trunk_norm", "aux/grad_norm", "aux/clip_scale"]].dropna()
    d["bin"] = (d["_step"] // 1_000_000).astype(int)
    ratio = (d["aux/trunk_norm_delivered"] / d["aux/policy_trunk_norm"])
    per_bin = ratio.groupby(d["bin"]).median()
    q = {int(b): float(per_bin[b] / DOSE_MID[b]) for b in per_bin.index
         if b in DOSE_MID}
    r_bar = _fleet_median(list(q.values()))  # within-lane median over bins
    f = d["aux/trunk_norm"] / d["aux/grad_norm"]
    f_late = float(f[d["bin"] == 11].median())
    clip_mean = float(d["aux/clip_scale"].mean())
    late = df[df["_step"] >= 11_000_000]
    a1 = late["aux/synth_marginal_nll"].dropna().mean()
    mb0 = late["aux/loss_mb0"].dropna().mean()
    a3 = late["aux/synth_sampler_entropy"].dropna().mean()
    g = float((a1 - mb0) / (a1 - a3))
    return q, r_bar, f_late, clip_mean, g


def dose_cell_name(r_bar: float) -> str:
    if r_bar < 0.70:
        return "INSUFFICIENT"
    if r_bar < 1.00:
        return "SHORT"
    if r_bar <= 2.00:
        return "MATCHED"
    return "OVER"


def a_cell(delta1: float, hi1: float) -> str:
    if delta1 >= hi1:
        return "A1"
    if delta1 >= FLOOR:
        return "A2"
    if abs(delta1) < FLOOR:
        return "A3"
    if delta1 > -hi1:
        return "A4"
    return "A5"


def s_cell(delta2: float, hi2: float) -> str:
    if delta2 >= hi2:
        return "S-a"
    if abs(delta2) < FLOOR:
        return "S-b"
    if delta2 <= -hi2:
        return "S-c"
    # between the floor and the bar on either side: letter-only band,
    # named so no cell is silent (the D25/D25-P lesson).
    return "S-letter(+)" if delta2 > 0 else "S-letter(-)"


def grade(rates, label, frozen, n_frozen_per=3000, direction="d25-minus-c"):
    pooled_c = sum(rates) / len(rates)
    pooled_f = sum(frozen.values()) / len(frozen)
    delta = (pooled_f - pooled_c) if direction == "d25-minus-c" else (pooled_c - pooled_f)
    se_b, se_c, s_t, s_c = se_terms(rates, len(rates) * 3000,
                                    list(frozen.values()), n_frozen_per * len(frozen))
    se_gov, gov = max((se_b, "binomial"), (se_c, "seed-clustered"))
    hi = max(FLOOR, 2 * se_gov)
    print(f"\n{label}: pooled_control {pooled_c:.5f} vs frozen {pooled_f:.5f}"
          f"  delta {delta:+.5f}  se {se_gov:.5f} ({gov})  hi {hi:.5f}"
          f"  control-spread s {s_t:.4f}")
    return delta, hi


def selftest() -> None:
    assert dose_cell_name(0.5) == "INSUFFICIENT"
    assert dose_cell_name(0.85) == "SHORT"
    assert dose_cell_name(1.5) == "MATCHED"
    assert dose_cell_name(2.5) == "OVER"
    # Aggregator: odd = middle, even = mean of the two central values (MF-5).
    assert _fleet_median([3, 1, 2]) == 2
    assert _fleet_median([4, 1, 2, 3]) == 2.5
    # MF-12: a DECAYING trajectory must not launder into MATCHED via the
    # median — synthetic hump 2.5x early, 0.4x late.
    q = {b: (2.5 if b <= 2 else 1.0 if b <= 8 else 0.4) for b in range(12)}
    r_early = _fleet_median([q[b] for b in (0, 1, 2)])
    r_late = _fleet_median([q[b] for b in (9, 10, 11)])
    assert r_early >= 1.00 and r_late < 0.70  # -> DECAYING, not SUSTAINED
    assert min(q.values()) < 0.70
    # g cells at the frozen bar
    assert G_BAR == 0.54338
    for g, want in ((0.60, "LEARNED"), (0.30, "WEAK"), (0.05, "VOID")):
        cell = ("LEARNED" if g >= G_BAR else "WEAK" if g >= G_VOID else "VOID")
        assert cell == want, (g, cell)
    # A-cells at a synthetic hi_1 = 0.06
    for d, want in ((0.10, "A1"), (0.04, "A2"), (0.01, "A3"), (-0.01, "A3"),
                    (-0.04, "A4"), (-0.10, "A5")):
        assert a_cell(d, 0.06) == want, (d, a_cell(d, 0.06))
    # S-cells at hi_2 = 0.06, incl. the named letter bands
    for d, want in ((0.10, "S-a"), (0.01, "S-b"), (-0.01, "S-b"),
                    (-0.10, "S-c"), (0.04, "S-letter(+)"), (-0.04, "S-letter(-)")):
        assert s_cell(d, 0.06) == want, (d, s_cell(d, 0.06))
    # End-to-end at H(D28)'s own prediction: control at Rung-2 -> A1
    rates = [0.5633, 0.5683, 0.5210, 0.5763, 0.4937]
    d1, hi1 = grade(rates, "selftest R-1", R1_D25)
    assert a_cell(d1, hi1) == "A1", (d1, hi1)
    d2, hi2 = grade(rates, "selftest R-2", R2_RUNG2, direction="c-minus-rung2")
    assert s_cell(d2, hi2) == "S-b", (d2, hi2)
    # And at a D25-reproducing control -> A3 (retraction)
    d1b, hi1b = grade(list(R1_D25.values()), "selftest A3", R1_D25)
    assert a_cell(d1b, hi1b) == "A3"
    print("\nSELFTEST OK: dose cells, A1-A5, S-cells incl. letter bands, "
          "H(D28) end-to-end -> A1 x S-b, reproduction -> A3.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if G_BAR is None:
        raise SystemExit("G_BAR is None: the Z1-2 freeze has not been folded "
                         "into this grader — the header BLOCKS launch/grade.")
    attest()
    rates, live = [], []
    for s in SEEDS:
        p = Path(f"results/d28/final_s{s}.json")
        if not p.exists():
            print(f"LANE s{s}: final MISSING — reported as-is, never replaced.")
            continue
        r = json.loads(p.read_text())
        if r.get("episodes") != 3000:
            raise SystemExit(f"final_s{s}.json episodes != 3000")
        if abs(r["eval/win_rate"] - r["wins_from_returns"]) > 1e-9:
            raise SystemExit(f"R0-4 FAIL s{s}: win_rate != wins_from_returns")
        if "mask_desyncs" not in r:
            raise SystemExit(f"final_s{s}.json lacks mask_desyncs — a missing "
                             "key must never read as clean (C-A6/MF-10)")
        if r["mask_desyncs"]:
            print(f"DISCLOSURE s{s}: mask_desyncs={r['mask_desyncs']}")
        rates.append(r["eval/win_rate"])
        live.append(s)
    if len(rates) < 3:
        print(f"\nONLY {len(rates)} SURVIVING LANE(S) — PRIMARY VOID "
              "(B-LANES). Surviving finals individual, never pooled.")
        raise SystemExit(1)
    print("Finals: " + "  ".join(f"s{s} {r:.4f}" for s, r in zip(live, rates)))
    doses = []
    for s in live:
        hist = Path(f"runs/showdown_sp_zeroinfo12m_s{s}/history.csv")
        if not hist.exists():
            raise SystemExit(f"extract history first: {hist} missing "
                             "(scripts/extract_history.py <run_dir>)")
        q, r_bar, f_late, clip, g = dose_cells(hist)
        doses.append((s, q, r_bar, f_late, clip, g))
        print(f"s{s}: r_bar {r_bar:.3f} ({dose_cell_name(r_bar)})  f_late "
              f"{f_late:.3f}  clip_mean {clip:.4f}  g {g:.3f}")
    # Fleet per-bin occupancy (MF-12): q_b = fleet median per bin, printed.
    q_fleet = {b: _fleet_median([d[1][b] for d in doses if b in d[1]])
               for b in DOSE_MID}
    print("per-bin q (fleet): " +
          " ".join(f"{b}:{q_fleet[b]:.2f}" for b in sorted(q_fleet)))
    r_early = _fleet_median([q_fleet[b] for b in (0, 1, 2)])
    r_late = _fleet_median([q_fleet[b] for b in (9, 10, 11)])
    if min(q_fleet.values()) >= 0.70:
        traj = "SUSTAINED"
    elif r_early >= 1.00 and r_late < 0.70:
        traj = "DECAYING"
    else:
        traj = "ERRATIC"
    r_bar_fleet = _fleet_median([d[2] for d in doses])
    cell_dose = dose_cell_name(r_bar_fleet)
    # f gate (MF-6): the LOW side (D27's collapse) voids on the fleet
    # median; the HIGH side is the named, non-voiding F-HIGH cell.
    f_fleet = _fleet_median([d[3] for d in doses])
    f_void = f_fleet < F_LATE_BAND[0]
    f_high = f_fleet > F_LATE_BAND[1]
    clip_void = any(d[4] < CLIP_NEUTRAL for d in doses)
    # Manipulation check (MF-4): median g across lanes vs the frozen bar.
    g_med = _fleet_median([d[5] for d in doses])
    if any(d[5] > 1.0 for d in doses):
        raise SystemExit(f"g > 1.0 on a lane — floor arithmetic bug: {doses}")
    g_cell = ("LEARNED" if g_med >= G_BAR
              else "WEAK" if g_med >= G_VOID else "VOID (B-VOID-TASK)")
    d1, hi1 = grade(rates, "R-1 PRIMARY (D25 - control)", R1_D25)
    d2, hi2 = grade(rates, "R-2 SECONDARY (control - Rung-2)", R2_RUNG2,
                    direction="c-minus-rung2")
    cA, cS = a_cell(d1, hi1), s_cell(d2, hi2)
    # NULL/POSITIVE mapping (MF-3): NULL = A1/A2 (control did not reproduce
    # D25); POSITIVE = A3/A4/A5.
    null_result = cA in ("A1", "A2")
    k, total, p = exact_perm_p(list(R1_D25.values()), rates, +1)
    print(f"\nR-1 exact perm (5v5, reported alongside; the credit line "
          f"GOVERNS, a disagreement is REPORTED never adjudicated): "
          f"{k}/{total} = {p:.5f}")
    void_dose = ((cell_dose == "INSUFFICIENT" and null_result)
                 or (traj == "DECAYING" and null_result)
                 or f_void or clip_void)
    print(f"DOSE: fleet r_bar {r_bar_fleet:.3f} ({cell_dose})  trajectory "
          f"{traj} (r_early {r_early:.2f}, r_late {r_late:.2f})  f_fleet "
          f"{f_fleet:.3f}{' F-HIGH (named, non-voiding, disclosed)' if f_high else ''}"
          f"{'  ** B-VOID-DOSE **' if void_dose else ''}")
    print(f"MANIPULATION: median g {g_med:.3f} -> {g_cell} "
          f"(bar {G_BAR}, void {G_VOID})")
    print(f"CELLS: {cA} x {cS}")
    sealed = (cA == "A1" and d2 >= 0 and not void_dose and not clip_void
              and cell_dose in ("SHORT", "MATCHED", "OVER")
              and r_late >= 0.70 and cS != "S-c"
              and g_cell == "LEARNED")
    print(f"SEALING (A1 and Delta_2>=0 and no VOID and dose not "
          f"INSUFFICIENT and r_late>=0.70 and not S-c and g LEARNED): "
          f"{'YES' if sealed else 'NO'}"
          f"{'  [F-HIGH disclosed on every quoted sentence]' if f_high else ''}")
    print("Route the verdict by the HEADER'S branch table verbatim — the "
          "cells above are its inputs, this line is not the verdict.")


if __name__ == "__main__":
    main()

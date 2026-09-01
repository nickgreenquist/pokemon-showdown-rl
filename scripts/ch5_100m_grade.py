#!/usr/bin/env python
"""The 100M pre-registration's grader (R0-e; configs/showdown_sp_100m.yaml
is the pre-reg — every cell, bar and disclosure here transcribes it and is
attested against disk before any verdict prints).

    python scripts/ch5_100m_grade.py --selftest
    python scripts/ch5_100m_grade.py [--dir results/ch5_100m] [--out X.json]

--selftest runs with NO 100M battle data: it attests the banked control
from disk, then exercises every cell of the branch table at synthetic
cuts — all six P cells and their boundaries, SN/X composition, F1, the
A-COLL cells and their boundaries, k=2 and k=1 lane failure, and the
UNGRADED idiom for missing finals. G2 rule inherited from the R2 wave:
a verdict is two tallies agreeing, never a subtraction.

Expected read data (produced by the frozen post-fleet eval schedule):
  {dir}/t{seed}.json        off-FP@20 greedy finals (ch3_fp_h2h runner
                            format: our_win_rate, battles_finished)
  {dir}/final_s{seed}.json  vs-SH locked finals (eval_checkpoint format)
  {dir}/acoll.json          optional; {"async_12m": {...}, "sync_12m":
                            {...}} pooled off-FP rates for A-COLL
Missing vs-SH finals emit UNGRADED, never silence (the R2 MF-3 rule).
A VOIDed/failed lane is ABSENT from its dict — removal moves k, it never
cleans the data.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREREG_PATH = REPO / "configs/showdown_sp_100m.yaml"
SEEDS = (104, 112, 120)

# Frozen constants — every one is re-attested from disk by attest();
# a constant that does not reproduce is a FAIL, not a warning.
CTRL_OFFFP = {"s66": (0.4740, 3000), "s75": (0.4826666666666667, 3000),
              "s83": (0.4670, 3000)}
CTRL_VSSH = {"s66": 0.7813333333333333, "s75": 0.7946666666666666,
             "s83": 0.7833333333333333}
CTRL_MEAN = sum(r for r, _ in CTRL_OFFFP.values()) / 3      # 0.4745556
CTRL_SD = statistics.stdev([r for r, _ in CTRL_OFFFP.values()])  # 0.0078481
CTRL_MEAN_SH = sum(CTRL_VSSH.values()) / 3                  # 0.7864444
CTRL_SD_SH = statistics.stdev(CTRL_VSSH.values())           # 0.0071906
F1_THRESHOLD = 0.580222   # frozen struct50m vs-SH pooled (carried from R2)
FLOOR = 0.025

# The standing disclosure (restated from scripts/ch5_r2_grade.py's
# SIGMA_DISCLOSURE, horizon wording) PLUS this round's amendment: the
# exact 2-df 95% interval printed beside every sigma_seed (mem_A Q4-4).
SIGMA_DISCLOSURE = (
    "an F-test across two 3-lane groups has (2,2) degrees of freedom and "
    "critical value 19.0, so the horizon must cut sigma_seed ~4.4x before "
    "the comparison registers; A NULL IS NEVER READABLE AS 'THE HORIZON "
    "DID NOT HELP VARIANCE'.")
SIGMA_CI = (0.521, 6.285)  # exact 2-df 95% multipliers on s


def primary_cell(delta, bar):
    """Six cells, half-open, exhaustive. Boundaries per the header:
    delta=+BAR->P1; -BAR->P6; +0.025->P1 when BAR=FLOOR else P2;
    -0.025->P5 when BAR>FLOOR else P6."""
    if delta >= bar:
        return "P1", ("CREDIT — C1 'longer run' is credited at 100M on the "
                      "off-FP@20 axis. Carries: N-ANNEAL named as the "
                      "leading alternative; G9's signed delta; A-COLL fires.")
    if delta >= FLOOR:
        return "P2", ("letter-met POSITIVE, seed-fragile, NOT credited "
                      "(empty by construction when BAR = floor)")
    if delta >= 0:
        return "P3", "WITHIN, positive sign — non-resolving"
    if delta > -FLOOR:
        return "P4", "WITHIN, negative sign — non-resolving"
    if delta > -bar:
        return "P5", "letter-met NEGATIVE, not credited"
    return "P6", ("NEGATIVE, credited in reverse — the horizon HURT; "
                  "over-training/L3 recorded beside it")


def sn_cell(delta_sh, bar_sh):
    if delta_sh <= -bar_sh:
        return "SN-C", "credited NEGATIVE on the locked axis"
    if delta_sh <= -FLOOR:
        return "SN-L", "letter-met NEGATIVE on the locked axis, not credited"
    return "SN-N", ("no letter; the positive side is DESCRIPTIVE (a positive "
                    "letter would need pooled >= 0.81144)")


def x_cell(p, sn):
    if p == "P1" and sn == "SN-C":
        return "X3", ("NAMED CELL: both sentences recorded, neither "
                      "suppressed; the README row question goes to the "
                      "maintainer WITH the numbers, never an editorial choice")
    if p == "P1" and sn == "SN-L":
        return "X2", ("credit stands; the locked-axis regression is stated "
                      "in the same paragraph")
    if p == "P1":
        return "X1", ("credit stands; the vs-SH number and its bar reported "
                      "beside it")
    return "X4", ("the primary cell governs; vs-SH reported descriptively "
                  "with its bar")


def acoll_cell(delta_coll, ran_async):
    """A-COLL boundaries per the header: |d|=0.010 -> A-COLL-2; =0.025 ->
    A-COLL-3. Descriptive; can only weaken a credit."""
    if not ran_async:
        return "A-COLL-0", ("VOID by construction — sync branch; N-TIMER's "
                            "disclosure still travels")
    d = abs(delta_coll)
    if d < 0.010:
        return "A-COLL-1", ("wire effect < 40% of the credit floor; credit "
                            "stands; number disclosed in every quote")
    if d < 0.025:
        return "A-COLL-2", ("a MATERIAL fraction of the floor; credit "
                            "stands; the fraction disclosed with its sign in "
                            "every quote")
    return "A-COLL-3", ("NAMED CELL — the wire alone clears the credit floor "
                        "at 12M; the C1 credit is NOT separable from the "
                        "collector; README row question to the maintainer "
                        "with the numbers")


def _vs_sh_block(cell, t_rates, sh_rates, sh_n, k):
    """The vs-SH axis + F1, at EVERY k; NEVER silent (the R2 MF-3 rule)."""
    out = {}
    if not t_rates or sh_rates is None or set(sh_rates) != set(t_rates):
        note = ("vs-SH finals missing/incomplete for the surviving lanes — "
                "UNGRADED (not passed). SN letters, X cells and F1 CANNOT "
                "be read; produce read 1 of the frozen schedule and re-grade.")
        out["vs_sh"] = {"pass": None, "note": note}
        out["F1_falsifier"] = {"pass": None, "note": note}
        return out
    ys = [sh_rates[l] for l in sorted(sh_rates)]
    mean_sh = sum(ys) / k
    if k < 3:
        out["vs_sh"] = {
            "per_lane": dict(sorted(sh_rates.items())),
            "pooled_survivors": mean_sh, "k": k, "x_cell": "XK",
            "x_verdict": ("k <= 2: both axes DESCRIPTIVE; no letter; the "
                          "1-df disclosure applies (CI multipliers "
                          "0.45x-31.9x); lanes reported individually")}
    else:
        s_tsh = statistics.stdev(ys)
        delta_sh = mean_sh - CTRL_MEAN_SH
        se_bin_sh = math.sqrt(
            sum(y * (1 - y) / sh_n for y in ys) / k ** 2
            + sum(r * (1 - r) / 3000 for r in CTRL_VSSH.values()) / 9)
        se_clus_sh = math.sqrt(s_tsh ** 2 / k + CTRL_SD_SH ** 2 / 3)
        bar_sh = max(FLOOR, 2 * max(se_bin_sh, se_clus_sh))
        sn, sn_verdict = sn_cell(delta_sh, bar_sh)
        xc, x_verdict = x_cell(cell, sn)
        out["vs_sh"] = {"mean_T": mean_sh, "delta": delta_sh, "s_T": s_tsh,
                        "bar": bar_sh, "sn_cell": sn, "sn_verdict": sn_verdict,
                        "x_cell": xc, "x_verdict": x_verdict}
    out["F1_falsifier"] = {
        "fires": mean_sh < F1_THRESHOLD, "k": k, "threshold": F1_THRESHOLD,
        "sentence": ("FALSIFIER-CLASS: the horizon destroyed the credited "
                     "stack's entire 50M advantage. Composes with the cell; "
                     "both sentences recorded.")
        if mean_sh < F1_THRESHOLD else None}
    return out


def grade_read(t_rates, t_ns, sh_rates=None, sh_n=3000,
               acoll=None, ran_async=True):
    """t_rates: dict lane->off-FP rate for SURVIVING lanes only."""
    k = len(t_rates)
    R = {"k_arm": k, "treatment": dict(sorted(t_rates.items())),
         "control": {l: r for l, (r, _) in CTRL_OFFFP.items()},
         "aggregator": "equal_weight_mean_of_lane_rates",
         "branch": "async" if ran_async else "sync_fallback"}
    if k < 3:
        R["cell"] = "K"
        R["verdict"] = (
            "k_arm <= 2: the primary is DESCRIPTIVE ONLY; no cell fires; "
            "nothing is credited. Surviving lanes reported individually at "
            "their own n_eff. At k=2 the seed sd has ONE degree of freedom "
            "(95% CI multipliers 0.45x-31.9x).")
        R.update(_vs_sh_block("K", t_rates, sh_rates, sh_n, k))
        R["a_coll"] = {"cell": None,
                       "note": "A-COLL fires only on P1; cell K voids it"}
        return R
    xs = [t_rates[l] for l in sorted(t_rates)]
    mean_t = sum(xs) / k
    s_t = statistics.stdev(xs)
    delta = mean_t - CTRL_MEAN
    se_bin = math.sqrt(
        sum(x * (1 - x) / n for x, n in
            zip(xs, (t_ns[l] for l in sorted(t_rates)))) / k ** 2
        + sum(r * (1 - r) / n for r, n in CTRL_OFFFP.values()) / 9)
    se_clus = math.sqrt(s_t ** 2 / k + CTRL_SD ** 2 / 3)
    se_gov = max(se_bin, se_clus)
    bar = max(FLOOR, 2 * se_gov)
    cell, verdict = primary_cell(delta, bar)
    R.update({"mean_T": mean_t, "s_T": s_t, "delta": delta,
              "se_bin": se_bin, "se_clus": se_clus, "se_gov": se_gov,
              "governing": "clustered" if se_clus >= se_bin else "binomial",
              "bar": bar, "cell": cell, "verdict": verdict})
    R["recorded_never_governing"] = {
        "pooled_rate": sum(x * t_ns[l] for x, l in zip(xs, sorted(t_rates)))
        / sum(t_ns.values()),
        "best_lane": max(xs), "worst_lane": min(xs)}
    R["sigma_seed_descriptive"] = {
        "s_T_raw": s_t,
        "ci95_2df": [SIGMA_CI[0] * s_t, SIGMA_CI[1] * s_t],
        "sigma_hat_deconvolved_DESCRIPTIVE_ONLY":
            math.sqrt(max(0.0, s_t ** 2 - mean_t * (1 - mean_t) / 3000)),
        "MANDATORY_DISCLOSURE": SIGMA_DISCLOSURE}
    if cell == "P1":
        if acoll is None:
            R["a_coll"] = {
                "cell": None, "pass": None,
                "note": ("P1 fired and A-COLL has not been read — the credit "
                         "sentence is INCOMPLETE until the A-COLL number and "
                         "G9's signed delta ride with it; run schedule read "
                         "6 and re-grade.")} if ran_async else \
                {"cell": "A-COLL-0", "verdict": acoll_cell(0.0, False)[1]}
        else:
            d = acoll["async_12m"] - acoll["sync_12m"]
            c, v = acoll_cell(d, ran_async)
            R["a_coll"] = {"delta_coll": d, "cell": c, "verdict": v}
    else:
        R["a_coll"] = {"cell": None,
                       "note": f"A-COLL fires only on P1 (cell here: {cell})"}
    R.update(_vs_sh_block(cell, t_rates, sh_rates, sh_n, k))
    return R


# ---------------------------------------------------------------------
def attest():
    """Re-derive the frozen control reads from disk AND check the pre-reg
    header carries the same numbers; hard-stop on drift."""
    out = {"pass": True, "checks": []}
    for lane, (rate, n) in CTRL_OFFFP.items():
        d = json.loads(
            (REPO / f"results/ch5_r2_offsh/t{lane[1:]}.json").read_text())
        ok = (abs(d["our_win_rate"] - rate) < 5e-7
              and d["battles_finished"] == d["battles_requested"] == n)
        out["checks"].append({"file": f"t{lane[1:]}.json",
                              "rate": d["our_win_rate"], "pass": ok})
        out["pass"] &= ok
    for lane, rate in CTRL_VSSH.items():
        d = json.loads(
            (REPO / f"results/ch5_r2/final_s{lane[1:]}.json").read_text())
        ok = abs(d["eval/win_rate"] - rate) < 5e-7 and d["episodes"] == 3000
        out["checks"].append({"file": f"final_s{lane[1:]}.json",
                              "rate": d["eval/win_rate"], "pass": ok})
        out["pass"] &= ok
    header = PREREG_PATH.read_text()
    for name, val in (("pooled off-FP", "0.4745556"),
                      ("s_C off-FP", "0.0078481"),
                      ("pooled vs-SH", "0.7864444"),
                      ("sd vs-SH", "0.0071906"),
                      ("F1", "0.580222")):
        ok = val in header
        out["checks"].append({"header_carries": name, "value": val, "pass": ok})
        out["pass"] &= ok
    # Pinned at the EXACT file values (the 7-digit rounded forms in the
    # header differ in the 8th place; the header check above covers those).
    ok = abs(CTRL_MEAN - 0.47455555555555556) < 5e-10 \
        and abs(CTRL_SD - 0.007848094838404578) < 5e-10 \
        and abs(CTRL_MEAN_SH - 0.7864444444444444) < 5e-10 \
        and abs(CTRL_SD_SH - 0.00719052874993929) < 5e-10
    out["checks"].append({"derived_summary_stats": ok, "pass": ok})
    out["pass"] &= ok
    return out


def selftest():
    print("SELFTEST")
    a = attest()
    assert a["pass"], f"attest failed: {a}"

    def rates(vals):
        return dict(zip(("s104", "s112", "s120"), vals))

    NS = {l: 3000 for l in ("s104", "s112", "s120")}
    SH_OK = rates([0.79, 0.78, 0.785])

    # (1) every P cell + exact boundaries at a floor-governed bar.
    tight = 0.002  # s_T tiny -> bar = FLOOR
    # Boundary rules at BAR = floor: +0.025 -> P1; -0.025 = -BAR -> P6
    # (P5 is reachable only when BAR > floor).
    for target_delta, want in ((0.030, "P1"), (0.025, "P1"), (0.010, "P3"),
                               (0.0, "P3"), (-0.010, "P4"), (-0.025, "P6"),
                               (-0.030, "P6")):
        c = CTRL_MEAN + target_delta
        r = grade_read(rates([c - tight, c, c + tight]), NS, SH_OK,
                       acoll={"async_12m": 0.35, "sync_12m": 0.349})
        assert abs(r["bar"] - FLOOR) < 1e-12, r["bar"]
        assert r["cell"] == want, (target_delta, r["cell"], want)
    # boundary at -FLOOR when bar = floor -> P6 (delta <= -BAR).
    c = CTRL_MEAN - FLOOR
    r = grade_read(rates([c - tight, c, c + tight]), NS, SH_OK)
    assert r["cell"] in ("P5", "P6")  # equality is float-fragile; both legal
    # (2) a wide fleet raises the bar above the floor -> P2 reachable.
    c = CTRL_MEAN + 0.030
    r = grade_read(rates([c - 0.06, c, c + 0.06]), NS, SH_OK)
    assert r["bar"] > FLOOR and r["cell"] == "P2", (r["bar"], r["cell"])
    assert r["governing"] == "clustered"
    # ...and P5, its negative twin (reachable only when BAR > floor).
    c = CTRL_MEAN - 0.030
    r = grade_read(rates([c - 0.06, c, c + 0.06]), NS, SH_OK)
    assert r["bar"] > 0.030 and r["cell"] == "P5", (r["bar"], r["cell"])
    # (3) sigma disclosure pairing + the 2-df interval.
    sd = r["sigma_seed_descriptive"]
    assert sd["MANDATORY_DISCLOSURE"] == SIGMA_DISCLOSURE
    assert abs(sd["ci95_2df"][0] - 0.521 * r["s_T"]) < 1e-12
    # (4) SN/X composition incl. X3, and F1.
    c = CTRL_MEAN + 0.030
    bad_sh = rates([0.70, 0.71, 0.705])   # delta_sh ~ -0.081 -> SN-C
    r = grade_read(rates([c - tight, c, c + tight]), NS, bad_sh,
                   acoll={"async_12m": 0.35, "sync_12m": 0.349})
    assert r["cell"] == "P1" and r["vs_sh"]["sn_cell"] == "SN-C"
    assert r["vs_sh"]["x_cell"] == "X3"
    dead_sh = rates([0.57, 0.575, 0.572])
    r = grade_read(rates([c - tight, c, c + tight]), NS, dead_sh,
                   acoll={"async_12m": 0.35, "sync_12m": 0.349})
    assert r["F1_falsifier"]["fires"]
    # (5) A-COLL cells + boundaries.
    assert acoll_cell(0.0099, True)[0] == "A-COLL-1"
    assert acoll_cell(0.010, True)[0] == "A-COLL-2"
    assert acoll_cell(-0.0249, True)[0] == "A-COLL-2"
    assert acoll_cell(0.025, True)[0] == "A-COLL-3"
    assert acoll_cell(0.5, False)[0] == "A-COLL-0"
    # P1 without an A-COLL read is INCOMPLETE, not silent.
    r = grade_read(rates([c - tight, c, c + tight]), NS, SH_OK, acoll=None)
    assert r["a_coll"]["pass"] is None and "INCOMPLETE" in r["a_coll"]["note"]
    # (6) lane failure: k=2 and k=1 -> cell K, vs-SH never silent.
    for survivors in (["s104", "s112"], ["s104"]):
        t = {l: CTRL_MEAN + 0.05 for l in survivors}
        r = grade_read(t, {l: 3000 for l in survivors},
                       {l: 0.79 for l in survivors})
        assert r["cell"] == "K" and r["vs_sh"]["x_cell"] == "XK"
    # (7) missing vs-SH -> UNGRADED, never silence.
    r = grade_read(rates([c - tight, c, c + tight]), NS, None)
    assert r["vs_sh"]["pass"] is None and r["F1_falsifier"]["pass"] is None
    # (8) sync branch: A-COLL-0 on P1.
    r = grade_read(rates([c - tight, c, c + tight]), NS, SH_OK,
                   acoll=None, ran_async=False)
    assert r["a_coll"]["cell"] == "A-COLL-0"
    print(f"  attest: {sum(1 for x in a['checks'] if x['pass'])}"
          f"/{len(a['checks'])} checks pass")
    print("  all cells, boundaries, compositions, lane-failure and "
          "UNGRADED paths exercised")
    print("SELFTEST PASS")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dir", default="results/ch5_100m")
    ap.add_argument("--sync-branch", action="store_true",
                    help="the run used configs/showdown_sp_100m_sync.yaml")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    base = REPO / args.dir
    t_rates, t_ns, sh_rates = {}, {}, {}
    for seed in SEEDS:
        p = base / f"t{seed}.json"
        if p.exists():
            d = json.loads(p.read_text())
            assert d["battles_finished"] == d["battles_requested"], (
                f"{p}: incomplete arm — a partial arm is VOID, not scaled")
            t_rates[f"s{seed}"] = d["our_win_rate"]
            t_ns[f"s{seed}"] = d["battles_finished"]
        q = base / f"final_s{seed}.json"
        if q.exists():
            e = json.loads(q.read_text())
            sh_rates[f"s{seed}"] = e["eval/win_rate"]
    acoll = None
    pa = base / "acoll.json"
    if pa.exists():
        acoll = json.loads(pa.read_text())
    report = {
        "attest": attest(),
        "grade": grade_read(
            t_rates, t_ns,
            sh_rates if set(sh_rates) == set(t_rates) and sh_rates else None,
            acoll=acoll, ran_async=not args.sync_branch),
    }
    if not report["attest"]["pass"]:
        report = {"refused": "attest failed — control drifted on disk",
                  "attest": report["attest"]}
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()

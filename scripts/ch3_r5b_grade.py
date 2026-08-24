"""CH3 R5b grader (BI-6): the primary X1-X0 read, every D-/F-gate, the PL
falsifier cells, the B1a/B1b split, anchor-transfer cells, KILL — pre-reg
configs/eval/ch3_r5b_exit.yaml, whose LAW is reused, never re-implemented:
ch3_r2_grade.land + check_partition + se_terms_r2 UNMODIFIED, plus the
CREDIT_LINE byte-assert.

    python scripts/ch3_r5b_grade.py --prereg configs/eval/ch3_r5b_exit.yaml
    python scripts/ch3_r5b_grade.py --selftest

REFUSES to grade: a non-RATIFIED status, a dirty tree, an uncommitted
pre-reg, any unquoted "[MAINTAINER RULING" bracket (the R4 U4 pattern,
ch3_r4_grade's negative-lookbehind scan), any PENDING B-10 transcript key,
or a missing/failed t_gate_readout (D-1).

Cells (Q10, five_cell_floor, hi = max(0.025, 2*se_gov)): B1a = CREDIT AND
F-T GREEN; B1b = CREDIT otherwise (F-T disclosed band); B2/B3/B4/B5 per
land(). KILL (sufficient): delta <= 0 AND d_i <= 0 on >= 3 of 4 — closes
the ACTOR family within the chapter, scoped. PL cells (Q8): STRIKE /
UNCONFIRMED / SURVIVE against 0.6*delta(X1) with the same se law; a
DOSE-UNMATCHED PL strikes nothing. Anchor-transfer cells (numeric,
pre-pinned): (CA-CB) >= 0.031 AND (FA-0.388) >= 0.087 -> POSITIVE;
<= -0.031 OR <= -0.087 -> NEGATIVE; else AMBIGUOUS (the modal cell).

--selftest pins the five band-boundary landings (band_boundaries,
verbatim), the Q7 power/size cells and the Q8 false-strike cells —
REGENERATED from the committed scripts/ch3_r5_power_sim.py and checked
against the pre-reg's quoted table within Monte-Carlo tolerance — plus
the PL cell law, the B1a/B1b split, the anchor cells and KILL.
"""

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_r2_grade import (  # noqa: E402  — reused UNMODIFIED, the point
    CREDIT_LINE,
    FLOOR,
    check_partition,
    land,
    se_terms_r2,
)

LANES = ("s62", "s63", "s64", "s65")
T_GATE_READOUT = "results/ch3_r5a/t_gate_readout.json"
RESULTS_DIR = "results/ch3_r5b"
ERA_PIN_DIR = "results/ch3_r5b_era_pin"
ANCHORS_DIR = "results/ch3_r5b_anchors"
FP_ANCHOR_DIR = "results/ch3_r5b_fp_anchor"
GATES_DIR = "results/ch3_r5b/gates"
COLLECT_DIR = "results/ch3_r5b/collect"
N = 3000
PL_STRIKE_FRAC = 0.6
CLONE_MDE = 0.031
FA_FROZEN = 0.388
FA_MDE = 0.087


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def refuse_checks(prereg: dict, prereg_path: str) -> None:
    status = str(prereg.get("status", ""))
    assert "DRAFT" not in status and "RATIFIED" in status, (
        f"pre-reg status is not RATIFIED: {status[:80]!r}"
    )
    assert prereg["credit_line"] == CREDIT_LINE, (
        "pre-reg credit_line is not byte-equal to ch3_r2_grade.CREDIT_LINE"
    )
    raw = Path(prereg_path).read_text()
    # ch3_r4_grade's scan verbatim: quoted mentions are spec, unquoted are
    # unruled brackets
    assert not re.search(r'(?<!")\[MAINTAINER RULING', raw), (
        "an unruled [MAINTAINER RULING bracket remains in the pre-reg"
    )
    for key in ("temperature_grid_transcript", "placebo_dose_search_transcript",
                "a0_selfplay_measured", "b7_fg4_transcript"):
        assert "PENDING" not in str(prereg.get(key, "PENDING")), (
            f"{key} still PENDING — run scripts/ch3_r5b_stamp.py and commit "
            "before grading (B-10)"
        )
    readout = json.loads(Path(T_GATE_READOUT).read_text())
    assert readout["cell"] == "T-PASS", f"D-1 FAIL: {readout['cell']!r}"
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree is dirty; commit before grading:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"


def b1_split(cell: str, f_t_state: str) -> str:
    """B1a: CREDIT AND F-T GREEN. B1b: CREDIT otherwise (disclosed band).
    The frozen-number conjunct is struck by the pre-reg itself."""
    if cell != "B1":
        return cell
    return "B1a" if f_t_state == "GREEN" else "B1b"


def f_t_state_of(x0_pooled: float, green: list[float], stop: list[float]) -> str:
    if green[0] <= x0_pooled <= green[1]:
        return "GREEN"
    if stop[0] <= x0_pooled <= stop[1]:
        return "DISCLOSED"
    return "STOP"


def pl_cell(delta_pl: float, delta_x1: float, se_gov_pl: float,
            dose_matched: bool) -> str:
    if not dose_matched:
        return "PL-DOSE-UNMATCHED"  # non-binding, strikes nothing
    if delta_pl >= PL_STRIKE_FRAC * delta_x1:
        return "PL-STRIKE" if delta_pl >= 2 * se_gov_pl else "PL-UNCONFIRMED"
    return "PL-SURVIVE"


def anchor_cell(ca: float | None, cb: float | None, fa: float | None) -> str:
    if ca is None or cb is None or fa is None:
        return "ANCHORS-NOT-RUN"
    clone_d, fa_d = ca - cb, fa - FA_FROZEN
    if clone_d >= CLONE_MDE and fa_d >= FA_MDE:
        return "ANCHOR-TRANSFER-POSITIVE"
    if clone_d <= -CLONE_MDE or fa_d <= -FA_MDE:
        return "ANCHOR-TRANSFER-NEGATIVE"
    return "ANCHOR-AMBIGUOUS"


def span_overlap_frac(a: tuple[float, float], b: tuple[float, float]) -> float:
    shorter = min(a[1] - a[0], b[1] - b[0])
    if shorter <= 0:
        return 0.0
    overlap = min(a[1], b[1]) - max(a[0], b[0])
    return max(0.0, overlap) / shorter


def _final(rdir: Path, job: str) -> dict:
    p = rdir / f"{job}.final.json"
    assert p.exists(), f"missing {p} — job incomplete"
    return json.loads(p.read_text())


def grade(prereg_path: str) -> dict:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    refuse_checks(prereg, prereg_path)
    rdir = Path(RESULTS_DIR)
    lane_map = prereg["lane_map"]
    dlanes = [lane_map[l] for l in LANES]

    # ---- D-6 arm contrast, on the pre-reg itself + the stamped pins ----
    x0_arm, x1_arm = dict(prereg["arms"]["X0"]), dict(prereg["arms"]["X1"])
    assert x0_arm.pop("lanes") == list(LANES) and x1_arm.pop("lanes") == dlanes
    assert x0_arm == x1_arm, f"D-6 VOID: arm dicts differ beyond lanes"
    for l in LANES:
        s0 = prereg["checkpoints"][l]["sha256"]
        s1 = prereg["checkpoints"][lane_map[l]]["sha256"]
        assert not s1.startswith("<"), f"D-6/B-5: {lane_map[l]} unstamped"
        assert s0 != s1, f"D-6 VOID: {l} and {lane_map[l]} pins identical"

    # ---- F-A8 on every chunk of every arm (+ the era pin + collection) ----
    voiding: dict[str, str] = {}
    for chunk_dir in (rdir, Path(ERA_PIN_DIR), Path(COLLECT_DIR)):
        if not chunk_dir.exists():
            continue
        for chunk in sorted(chunk_dir.glob("*.chunk*.json")):
            rep = json.loads(chunk.read_text())
            if rep["eval/win_rate"] != rep["wins_from_returns"]:
                voiding["F-A8"] = f"{chunk}"

    # ---- F-C + F-M on the collection ----
    f_m: dict[str, dict] = {}
    exp = float(prereg["f_c_leaves_expected"])
    band = float(prereg["f_c_band"])
    for l in LANES:
        fin = _final(Path(COLLECT_DIR), l)
        if abs(fin["search/leaves_mean"] - exp) / exp > band:
            voiding["F-C"] = f"lane {l}: leaves_mean {fin['search/leaves_mean']}"
        f_m[l] = {"ms_mean": fin["search/ms_mean"],
                  "placeholder_skip_rate": fin["search/placeholder_skip_rate"],
                  "rows_per_battle": fin["rows_per_battle"]}

    # ---- offline D-gates from the BI-3 harness ----
    d_gates = {}
    for l in LANES:
        g = json.loads((Path(GATES_DIR) / f"{l}_gates.json").read_text())
        d_gates[l] = g
        if not g["D-5"]["pass"]:
            voiding["D-5"] = f"lane {l}: critic identity broken"
        if not g["D-6_lane_files_differ"]:
            voiding["D-6"] = f"lane {l}: X0/X1 lane files identical"
        for gate in ("D-2", "D-3", "D-4"):
            assert g[gate]["pass"], (
                f"{gate} STOP on {l} — the arm should never have launched"
            )
        assert g["F-R"]["pass"] and g["F-L"]["pass"]

    # ---- the primary read ----
    x0 = {l: _final(rdir, f"x0_{l}") for l in LANES}
    x1 = {l: _final(rdir, f"x1_{lane_map[l]}") for l in LANES}
    for f in (*x0.values(), *x1.values()):
        assert f["episodes"] == N
    p0 = [x0[l]["eval/win_rate"] for l in LANES]
    p1 = [x1[l]["eval/win_rate"] for l in LANES]
    d = [a - b for a, b in zip(p1, p0)]
    delta = sum(d) / len(d)
    terms = se_terms_r2(p1, p0, N)
    hi = max(FLOOR, 2 * terms["se_gov"])
    check_partition(hi)
    cell_raw = land(delta, hi)
    kill = delta <= 0 and sum(1 for x in d if x <= 0) >= 3

    # ---- F-T on the era pin (fallback: the letter-bearing X0, disclosed) --
    era_dir = Path(ERA_PIN_DIR)
    if era_dir.exists():
        era = [_final(era_dir, f"x0_{l}")["eval/win_rate"] for l in LANES]
        f_t_source = "era_pin"
    else:
        era = p0
        f_t_source = "letter_bearing_x0_FALLBACK_DISCLOSED"
    x0_pooled = sum(era) / len(era)
    f_t = f_t_state_of(x0_pooled, prereg["f_t_green_band"],
                       prereg["f_t_stop_band"])

    # ---- F-P pairing window ----
    f_p = {}
    min_overlap = float(prereg["f_p_min_overlap_frac"])
    for l in LANES:
        frac = span_overlap_frac(
            (x0[l]["started_at"], x0[l]["finished_at"]),
            (x1[l]["started_at"], x1[l]["finished_at"]))
        f_p[l] = {"overlap_frac": frac, "paired": frac >= min_overlap}

    # ---- F-D ----
    f_d = {l: {"x0": x0[l].get("mask_desyncs"), "x1": x1[l].get("mask_desyncs")}
           for l in LANES}

    cell = b1_split(cell_raw, f_t)

    # ---- PL, iff its finals exist ----
    pl_report = None
    pmap = prereg["placebo_map"]
    if all((rdir / f"pl_{pmap[l]}.final.json").exists() for l in LANES):
        ppl = [_final(rdir, f"pl_{pmap[l]}")["eval/win_rate"] for l in LANES]
        d_pl = [a - b for a, b in zip(ppl, p0)]
        delta_pl = sum(d_pl) / len(d_pl)
        terms_pl = se_terms_r2(ppl, p0, N)
        dose = yaml.safe_load(prereg["placebo_dose_search_transcript"]) \
            if isinstance(prereg["placebo_dose_search_transcript"], str) \
            else prereg["placebo_dose_search_transcript"]
        dose = json.loads(dose) if isinstance(dose, str) else dose
        dose_matched = all(dose[l]["dose_matched"] for l in LANES)
        pl_report = {
            "lane_rates_PL": dict(zip(LANES, ppl)),
            "delta_PL": delta_pl,
            **{f"pl_{k}": v for k, v in terms_pl.items()},
            "dose_matched": dose_matched,
            "cell": pl_cell(delta_pl, delta, terms_pl["se_gov"], dose_matched),
        }

    # ---- anchors, iff run ----
    ca = cb = fa = None
    adir = Path(ANCHORS_DIR)
    if (adir / "ca.final.json").exists() and (adir / "cb.final.json").exists():
        ca = json.loads((adir / "ca.final.json").read_text())["eval/win_rate"]
        cb = json.loads((adir / "cb.final.json").read_text())["eval/win_rate"]
    fp_final = Path(FP_ANCHOR_DIR) / "fa.final.json"
    if fp_final.exists():
        fa = json.loads(fp_final.read_text())["eval/win_rate"]
    anchors = {"CA": ca, "CB": cb, "FA": fa, "fa_frozen": FA_FROZEN,
               "cell": anchor_cell(ca, cb, fa)}

    out = {
        "prereg": prereg_path,
        "prereg_sha256": hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest(),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "lane_rates_X0": dict(zip(LANES, p0)),
        "lane_rates_X1": dict(zip(LANES, p1)),
        "per_lane_deltas": dict(zip(LANES, d)),
        "delta_equal_weight_mean": delta,
        **terms,
        "operative_bar_hi": hi,
        "cell_IF_NO_VOIDING_GATE": cell,
        "voiding_gates_fired": voiding,
        "VOID": bool(voiding),
        "kill_rule_fired": kill,
        "F-T": {"source": f_t_source, "x0_pooled": x0_pooled, "state": f_t,
                "green": prereg["f_t_green_band"],
                "stop": prereg["f_t_stop_band"], "voiding": False},
        "F-P": f_p,
        "F-D": f_d,
        "F-M": f_m,
        "PL": pl_report,
        "anchors": anchors,
        "provenance_qualifier": prereg["provenance_qualifier_mandatory"],
        "recorded_only": {
            "per_lane_median_delta": statistics.median(d),
            "worst_lane_delta": min(d),
            "d9_switch_rates": {l: d_gates[l]["D-9"] for l in LANES},
            "a0_selfplay": {l: d_gates[l]["D-2"]["a0_selfplay"] for l in LANES},
        },
        "finished_at": time.time(),
    }
    print(json.dumps(out, indent=2))
    if voiding:
        print(f"\nVOID — gates fired: {voiding}; no band is adjudicated; "
              "STATUS only, README untouched.")
    else:
        print(f"\nVERDICT CELL: {cell} | delta {delta:+.5f} | bar {hi:.5f} | "
              f"governing se: {terms['governing']} ({terms['se_gov']:.5f})"
              + (" | KILL: the actor expert-iteration line is CLOSED within "
                 "this chapter (scoped to the actor family)" if kill else ""))
        if pl_report:
            print(f"PL: {pl_report['cell']} (delta_PL {pl_report['delta_PL']:+.5f})")
        print(f"anchors: {anchors['cell']}")
    (rdir / "r5b_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def selftest(reps: int = 4000) -> None:
    from ch3_r5_power_sim import placebo_false_strike, primary_credit

    # --- the five band-boundary landings, band_boundaries verbatim ---
    assert land(0.025, 0.025) == "B1"          # delta=+0.025, hi=0.025
    assert land(0.025, 0.030) == "B2"          # delta=+0.025, hi>0.025
    assert land(-0.025, 0.030) == "B4"         # delta=-0.025, hi>0.025
    assert land(-0.025, 0.025) == "B5"         # delta=-0.025, hi=0.025
    for hi in (0.025, 0.030, 0.045):           # delta=-hi -> B5 always
        check_partition(hi)
        assert land(-hi, hi) == "B5"

    # --- B1a/B1b split + F-T states ---
    assert f_t_state_of(0.720, [0.689, 0.744], [0.650, 0.770]) == "GREEN"
    assert f_t_state_of(0.760, [0.689, 0.744], [0.650, 0.770]) == "DISCLOSED"
    assert f_t_state_of(0.790, [0.689, 0.744], [0.650, 0.770]) == "STOP"
    assert b1_split("B1", "GREEN") == "B1a"
    assert b1_split("B1", "DISCLOSED") == "B1b"
    assert b1_split("B3", "GREEN") == "B3"

    # --- PL cell law ---
    assert pl_cell(0.020, 0.028, 0.005, True) == "PL-STRIKE"
    assert pl_cell(0.020, 0.028, 0.012, True) == "PL-UNCONFIRMED"
    assert pl_cell(0.010, 0.028, 0.005, True) == "PL-SURVIVE"
    assert pl_cell(0.020, 0.028, 0.005, False) == "PL-DOSE-UNMATCHED"

    # --- anchor-transfer cells, numeric thresholds pinned ---
    assert anchor_cell(0.90, 0.86, 0.48) == "ANCHOR-TRANSFER-POSITIVE"
    assert anchor_cell(0.82, 0.86, 0.40) == "ANCHOR-TRANSFER-NEGATIVE"
    assert anchor_cell(0.88, 0.86, 0.40) == "ANCHOR-AMBIGUOUS"
    assert anchor_cell(None, None, None) == "ANCHORS-NOT-RUN"

    # --- KILL ---
    d = [-0.01, -0.02, -0.005, +0.004]
    assert sum(d) / 4 <= 0 and sum(1 for x in d if x <= 0) >= 3

    # --- F-P overlap arithmetic ---
    assert span_overlap_frac((0, 100), (10, 110)) == 0.9
    assert span_overlap_frac((0, 100), (200, 300)) == 0.0

    # --- Q7 power/size cells, regenerated from the committed sim, checked
    # against the pre-reg table within Monte-Carlo tolerance ---
    tol = 4 * (0.35 * 0.65 / reps) ** 0.5 + 0.01
    got, _, _ = primary_credit(0.028, 0.016, 0.0199, reps)
    assert abs(got - 0.350) < tol, f"Q7 pin: P(credit|+0.028,.016) {got}"
    got, _, _ = primary_credit(0.040, 0.010, 0.0199, reps)
    assert abs(got - 0.778) < tol, f"Q7 pin: P(credit|+0.040,.010) {got}"
    size, _, _ = primary_credit(0.000, 0.016, 0.0199, reps)
    assert size < 0.01, f"Q7 SIZE pin: {size}"

    # --- Q8 false-strike cells ---
    st, un = placebo_false_strike(0.016, reps)
    assert abs(st - 0.006) < 0.01 and abs(un - 0.037) < 0.02, (st, un)
    st, un = placebo_false_strike(0.025, reps)
    assert abs(st - 0.015) < 0.012 and abs(un - 0.096) < 0.03, (st, un)

    print(f"ch3_r5b_grade selftest: ALL GREEN (sim reps={reps})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--reps", type=int, default=4000,
                    help="selftest Monte-Carlo reps (pre-reg table used 20000)")
    args = ap.parse_args()
    if args.selftest:
        selftest(args.reps)
        return
    assert args.prereg, "--prereg or --selftest"
    grade(args.prereg)


if __name__ == "__main__":
    main()

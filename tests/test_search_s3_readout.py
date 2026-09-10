"""Verification of the S3 readout/grader on SYNTHETIC finals with known answers.

The S3 screen's cells (`configs/eval/search_s3_100m.yaml`, and P-B's read in
`docs/search_relook/DET_BLIND.md` §6) are:

    NEG  iff pooled <= 0 AND per-lane <= 0 in >= 2 of 3
    POS  iff pooled >= +0.025 AND >= 2*se_diff   (se_diff = the LARGER of the
         pooled-binomial and the seed-clustered term)
    FLAT otherwise

Every one of them is exercised here from FILES on disk, not from the internals
— the grader has to find the finals, pair them by lane, aggregate as the
equal-weight mean of per-lane paired deltas, and pick the governing se term.
Both governing directions are covered by a case whose answer is computed by
hand in the test, so the test is not the implementation checking itself.

Also covered, because they are the two ways this readout could lie:
  * PENDING — an arm short of its finals must print PENDING with
    chunks-done/10 and a PARTIAL running rate, and MUST NOT produce a cell;
  * P-L — one lane, SIGN ONLY, no cell ever, with the +-0.02 caveat.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from search_s3_readout import (  # noqa: E402
    ARMS,
    CHUNKS,
    CREDIT_LINE,
    CREDITS_NOTHING,
    FLOOR,
    FP20_DISCLOSURES,
    LANES,
    build,
    cell,
    paired_read,
    pl_read,
    read_arm,
    read_job,
    render_markdown,
    se_terms,
)

N = 3000
CHUNK_N = N // CHUNKS


# --------------------------------------------------------------------------
# synthetic artifacts, in ch3_eval.py's on-disk shapes
# --------------------------------------------------------------------------
def _search_fields(arm: str) -> dict:
    spec = ARMS[arm]
    if spec["kind"] != "search":
        return {}
    return {
        "search_dose": spec["dose"],
        "search_leaf_encoding": spec["leaf_encoding"],
        "search/ms_mean": 60.0,
        "search/leaves_mean": 290.0,
        "search/searched_decisions": 12000,
        "search/decisions": 12300,
        "search/placeholder_skips": 300,
        "search/flips": 8000,
    }


def write_final(d: Path, arm: str, lane: str, rate: float, n: int = N) -> None:
    d.mkdir(parents=True, exist_ok=True)
    body = {
        "job": f"{arm.lower()}_{lane}", "arm": arm, "members": [lane],
        "episodes": n, "eval/win_rate": rate, "wins_from_returns": rate,
        "mask_desyncs": 0, "chunks": CHUNKS,
        **_search_fields(arm),
    }
    if "search/decisions" in body:
        body["search/flip_rate"] = body["search/flips"] / (
            body["search/decisions"] - body["search/placeholder_skips"])
        body["search/placeholder_skip_rate"] = (
            body["search/placeholder_skips"] / body["search/decisions"])
    (d / f"{arm.lower()}_{lane}.final.json").write_text(json.dumps(body))


def write_chunks(d: Path, arm: str, lane: str, rate: float, k: int) -> None:
    """`k` completed chunks at `rate` — a PARTIAL job, no final."""
    d.mkdir(parents=True, exist_ok=True)
    sf = _search_fields(arm)
    for i in range(k):
        body = {
            "job": f"{arm.lower()}_{lane}", "arm": arm, "members": [lane],
            "chunk": i, "episodes": CHUNK_N, "seed_start": 100 + i * CHUNK_N,
            "eval/win_rate": rate, "wins_from_returns": rate,
            "mask_desyncs_delta": 0, **sf,
        }
        (d / f"{arm.lower()}_{lane}.chunk{i:02d}.json").write_text(
            json.dumps(body))


def lay_out(tmp: Path, a0: dict, s3m: dict | None = None,
            s3b: dict | None = None, s3l: dict | None = None,
            a1e: dict | None = None) -> Path:
    """Whole arms, complete, from lane->rate dicts. Absent arm = PENDING."""
    d = tmp / "results"
    d.mkdir(parents=True, exist_ok=True)
    for arm, rates in (("A0", a0), ("S3M", s3m), ("S3B", s3b),
                       ("S3L", s3l), ("A1E", a1e)):
        for lane, r in (rates or {}).items():
            write_final(d, arm, lane, r)
    return d


def read_all(d: Path) -> dict:
    return {a: read_arm(d, a) for a in ARMS}


def pm(d: Path) -> dict:
    """The P-M read (S3M - A0) off whatever is on disk."""
    return paired_read("P-M", read_all(d), "S3M", "A0", LANES, True, "test")


# --------------------------------------------------------------------------
# the cell function, at its boundaries (hand-checked, no files)
# --------------------------------------------------------------------------
def test_cell_pos_needs_both_conditions():
    tight = 0.001                     # 2*se_diff = 0.002, far below the floor
    assert cell(0.030, [0.03, 0.03, 0.03], tight)[0] == "POS"
    # exactly at the floor with a small band -> POS (the rule is >=)
    assert cell(FLOOR, [0.025, 0.025, 0.025], tight)[0] == "POS"
    # a hair under the floor -> FLAT, however tight the band
    assert cell(FLOOR - 1e-9, [0.025, 0.025, 0.025], tight)[0] == "FLAT"
    # over the floor but not over 2*se_diff -> FLAT (letter met, not credited)
    assert cell(0.030, [0.10, 0.03, -0.04], 0.020)[0] == "FLAT"
    # exactly at 2*se_diff -> POS (the rule is >=)
    assert cell(0.030, [0.03, 0.03, 0.03], 0.015)[0] == "POS"
    assert cell(0.030, [0.03, 0.03, 0.03], 0.015 + 1e-9)[0] == "FLAT"


def test_cell_neg_needs_pooled_and_majority():
    assert cell(-0.030, [-0.05, -0.03, -0.01], 0.001)[0] == "NEG"
    # pooled exactly 0 with 2 of 3 non-positive -> NEG (the rule is <=)
    assert cell(0.0, [-0.01, -0.01, 0.02], 0.001)[0] == "NEG"
    # a lane at exactly 0 counts as non-positive
    assert cell(0.0, [0.0, 0.0, 0.0], 0.001)[0] == "NEG"
    # pooled <= 0 but only ONE lane non-positive -> FLAT, not NEG
    assert cell(-0.001, [-0.04, 0.01, 0.026], 0.001)[0] == "FLAT"


def test_cell_refuses_a_lane_count_that_is_not_three():
    # P-L must never be able to obtain a cell.
    with pytest.raises(ValueError):
        cell(0.05, [0.05], 0.001)
    with pytest.raises(ValueError):
        cell(0.05, [0.05, 0.05], 0.001)


# --------------------------------------------------------------------------
# the larger-of rule: both governing directions, hand-computed
# --------------------------------------------------------------------------
def test_se_terms_binomial_governs_when_lanes_agree():
    # identical per-lane deltas -> clustered term is exactly 0
    t = se_terms(0.79, 9000, 0.75, 9000, [0.04, 0.04, 0.04])
    expect_bin = math.sqrt(0.79 * 0.21 / 9000 + 0.75 * 0.25 / 9000)
    assert t["se_binomial"] == pytest.approx(expect_bin)
    assert t["se_clustered"] == pytest.approx(0.0)
    assert t["governing"] == "binomial"
    assert t["se_diff"] == pytest.approx(expect_bin)


def test_se_terms_clustered_governs_when_lanes_disagree():
    deltas = [0.08, 0.06, 0.04]
    t = se_terms(0.78, 9000, 0.72, 9000, deltas)
    expect_clus = statistics.stdev(deltas) / math.sqrt(3)
    assert expect_clus == pytest.approx(0.02 / math.sqrt(3))
    assert t["se_clustered"] == pytest.approx(expect_clus)
    assert t["se_clustered"] > t["se_binomial"]
    assert t["governing"] == "clustered"
    assert t["se_diff"] == pytest.approx(expect_clus)


def test_se_terms_k1_has_no_clustered_term_and_says_so():
    t = se_terms(0.72, 3000, 0.74, 3000, [-0.02])
    assert t["se_clustered"] is None
    assert t["governing"] == "binomial"
    assert "no cell" in t["governing_note"]


# --------------------------------------------------------------------------
# every cell, end to end from files on disk
# --------------------------------------------------------------------------
def test_read_pos_binomial_governs(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.750 for ln in LANES},
                s3m={ln: 0.790 for ln in LANES})
    r = pm(d)
    assert r["status"] == "READ"
    assert r["pooled_delta"] == pytest.approx(0.040)
    assert r["n_treatment"] == 9000 and r["n_comparator"] == 9000
    assert r["governing"] == "binomial"
    # hand-computed: 2*sqrt(.79*.21/9000 + .75*.25/9000) = 0.012532...
    assert r["bar_2se"] == pytest.approx(
        2 * math.sqrt(0.79 * 0.21 / 9000 + 0.75 * 0.25 / 9000))
    assert r["bar_2se"] < FLOOR < r["pooled_delta"]
    assert r["cell"] == "POS"


def test_read_pos_clustered_governs(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.720 for ln in LANES},
                s3m=dict(zip(LANES, (0.800, 0.780, 0.760))))
    r = pm(d)
    assert r["pooled_delta"] == pytest.approx(0.060)
    assert r["governing"] == "clustered"
    assert r["se_clustered"] == pytest.approx(0.02 / math.sqrt(3))
    assert r["se_diff"] == pytest.approx(r["se_clustered"])
    # 2*se_clus = 0.0231 <= 0.060, and 0.060 >= floor -> POS even though the
    # band is ~2x the binomial one.
    assert r["bar_2se"] == pytest.approx(2 * 0.02 / math.sqrt(3))
    assert r["cell"] == "POS"


def test_read_flat_letter_met_but_band_too_wide_clustered_governs(tmp_path):
    # pooled +0.040 clears the +0.025 floor, but the lanes disagree so hard
    # that 2*se_clustered = 0.069 > 0.040 -> FLAT, not POS.
    d = lay_out(tmp_path,
                a0={ln: 0.750 for ln in LANES},
                s3m=dict(zip(LANES, (0.850, 0.790, 0.730))))
    r = pm(d)
    assert r["pooled_delta"] == pytest.approx(0.040)
    assert r["governing"] == "clustered"
    assert r["bar_2se"] == pytest.approx(2 * 0.06 / math.sqrt(3))
    assert r["bar_2se"] > r["pooled_delta"] > FLOOR
    assert r["cell"] == "FLAT"


def test_read_flat_below_the_floor(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.750 for ln in LANES},
                s3m={ln: 0.760 for ln in LANES})
    r = pm(d)
    assert r["pooled_delta"] == pytest.approx(0.010)
    assert r["cell"] == "FLAT"
    assert "floor" in r["cell_why"]


def test_read_neg(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.790 for ln in LANES},
                s3m=dict(zip(LANES, (0.740, 0.760, 0.800))))
    r = pm(d)
    assert r["pooled_delta"] < 0
    assert r["n_nonpositive_lanes"] == 2
    assert r["cell"] == "NEG"


def test_read_not_neg_when_only_one_lane_is_non_positive(tmp_path):
    # pooled is negative but 2 of 3 lanes are POSITIVE -> FLAT, never NEG.
    d = lay_out(tmp_path,
                a0={ln: 0.790 for ln in LANES},
                s3m=dict(zip(LANES, (0.700, 0.800, 0.795))))
    r = pm(d)
    assert r["pooled_delta"] < 0 and r["n_nonpositive_lanes"] == 1
    assert r["cell"] == "FLAT"


def test_pooled_delta_is_the_equal_weight_mean_of_lane_deltas(tmp_path):
    d = lay_out(tmp_path,
                a0=dict(zip(LANES, (0.700, 0.750, 0.800))),
                s3m=dict(zip(LANES, (0.730, 0.760, 0.790))))
    r = pm(d)
    assert r["aggregator"] == "equal_weight_mean_of_per_lane_paired_deltas"
    assert r["per_lane_delta"]["s104"] == pytest.approx(0.030)
    assert r["per_lane_delta"]["s112"] == pytest.approx(0.010)
    assert r["per_lane_delta"]["s120"] == pytest.approx(-0.010)
    assert r["pooled_delta"] == pytest.approx(0.030 / 3)


# --------------------------------------------------------------------------
# PENDING — never a cell on partial data
# --------------------------------------------------------------------------
def test_job_with_no_files_is_pending(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    j = read_job(d, "S3B", "s112")
    assert j["status"] == "PENDING" and j["complete"] is False
    assert j["chunks_done"] == 0 and j["rate"] is None


def test_job_with_some_chunks_is_partial_and_has_no_rate(tmp_path):
    d = tmp_path / "results"
    write_chunks(d, "S3M", "s112", 0.71, k=4)
    j = read_job(d, "S3M", "s112")
    assert j["status"] == "PARTIAL" and j["complete"] is False
    assert j["chunks_done"] == 4
    assert j["rate"] is None                       # nothing gradeable
    assert j["partial_rate"] == pytest.approx(0.71)
    assert j["episodes"] == 4 * CHUNK_N
    assert "NEVER a cell input" in j["note"]


def test_read_is_pending_when_one_arm_is_short_and_prints_the_partial(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    # S3M: two lanes done, one lane at 6/10 -> the whole read is PENDING
    write_final(d, "S3M", "s104", 0.72)
    write_final(d, "S3M", "s112", 0.74)
    write_chunks(d, "S3M", "s120", 0.69, k=6)
    r = pm(d)
    assert r["status"] == "PENDING"
    assert r["cell"] is None and r["pooled_delta"] is None
    assert r["blocked_by"] == ["s3m_s120 6/10"]
    assert "NO CELL ON PARTIAL DATA" in r["note"]
    # the partial IS printed, as a running rate, clearly labelled
    assert r["per_lane_partial"]["s120"]["t"] == pytest.approx(0.69)
    assert r["per_lane_partial"]["s120"]["t_chunks"] == "6/10"
    assert r["per_lane_partial"]["s104"]["t_chunks"] == "10/10"


def test_read_is_pending_when_an_arm_has_not_started(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES},
                s3m={ln: 0.720 for ln in LANES})
    arms = read_all(d)
    r = paired_read("P-E", arms, "A1E", "S3M", LANES, True, "test")
    assert r["status"] == "PENDING" and r["cell"] is None
    assert all("0/10" in b for b in r["blocked_by"])


def test_arm_rollup_reports_partial_pooled_rate_but_no_pooled_rate(tmp_path):
    d = tmp_path / "results"
    write_final(d, "S3M", "s104", 0.72)
    write_chunks(d, "S3M", "s112", 0.80, k=5)
    a = read_arm(d, "S3M")
    assert a["status"] == "PARTIAL" and a["complete"] is False
    assert a["pooled_rate"] is None
    # 3000 battles at .72 + 1500 at .80 -> .7466...
    assert a["partial_pooled_rate"] == pytest.approx(
        (0.72 * 3000 + 0.80 * 1500) / 4500)
    assert a["chunks_done"] == 15 and a["chunks_expected"] == 30


def test_pending_read_never_leaks_a_cell_into_the_markdown(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    write_chunks(d, "S3M", "s104", 0.72, k=3)
    rep = build(d, tmp_path / "offfp")
    for name in ("P-M", "P-B", "P-BA", "P-E"):
        assert rep["reads"][name]["cell"] is None
        assert rep["reads"][name]["status"] == "PENDING"
    md = render_markdown(rep)
    assert "PENDING — no cell on partial data" in md
    for token in ("**POS**", "**NEG**", "**FLAT**"):
        assert token not in md, f"{token} printed with no complete arm"
    assert "PARTIAL" in md


# --------------------------------------------------------------------------
# P-L — one lane, sign only, no cell
# --------------------------------------------------------------------------
def test_pl_is_sign_only_and_never_carries_a_cell(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    write_final(d, "S3M", "s112", 0.740)
    write_final(d, "S3L", "s112", 0.775)
    r = pl_read(read_all(d))
    assert r["status"] == "READ"
    assert r["cell"] is None and "NO CELL BY CONSTRUCTION" in r["cell_rule"]
    assert r["lane"] == "s112"
    assert r["delta"] == pytest.approx(0.035)
    assert r["sign"] == "+"
    assert r["within_one_rung"] is False          # 0.035 > 0.02
    assert "+-0.02" in r["caveat"]


def test_pl_negative_sign_inside_the_one_rung_spread(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    write_final(d, "S3M", "s112", 0.740)
    write_final(d, "S3L", "s112", 0.725)
    r = pl_read(read_all(d))
    assert r["delta"] == pytest.approx(-0.015)
    assert r["sign"] == "-"
    assert r["within_one_rung"] is True           # |0.015| <= 0.02
    assert "WITHIN" in r["note"]


def test_pl_boundary_is_inclusive_at_exactly_one_rung(tmp_path):
    # 0.720 - 0.700 = 0.020000000000000018 in binary; the +-0.02 spread is
    # descriptive prose, so EPS keeps the inclusive boundary inclusive.
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    write_final(d, "S3M", "s112", 0.700)
    write_final(d, "S3L", "s112", 0.720)
    r = pl_read(read_all(d))
    assert r["delta"] == pytest.approx(0.020)
    assert r["within_one_rung"] is True
    # ...but a delta a real rung outside it is still OUTSIDE
    write_final(d, "S3L", "s112", 0.7234)             # +0.0234
    r = pl_read(read_all(d))
    assert r["within_one_rung"] is False
    assert "OUTSIDE" in r["note"]


def test_a_knife_edge_pooled_delta_is_flagged_not_hidden(tmp_path):
    # pooled delta lands exactly on the +0.025 floor -> the cell is decided in
    # binary there, so the readout must SAY so rather than print a bare letter.
    d = lay_out(tmp_path,
                a0={ln: 0.750 for ln in LANES},
                s3m={ln: 0.775 for ln in LANES})
    r = pm(d)
    assert r["pooled_delta"] == pytest.approx(FLOOR)
    assert r["boundary_fragile"] == ["credit floor"]
    assert "BINARY" in r["boundary_fragile_note"]
    md = render_markdown(build(d, tmp_path / "offfp"))
    assert "**BOUNDARY:**" in md


def test_no_knife_edge_flag_on_an_ordinary_read(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.750 for ln in LANES},
                s3m={ln: 0.790 for ln in LANES})
    assert pm(d)["boundary_fragile"] is None


def test_pl_is_pending_when_either_side_is_short(tmp_path):
    d = lay_out(tmp_path, a0={ln: 0.790 for ln in LANES})
    write_final(d, "S3M", "s112", 0.740)
    write_chunks(d, "S3L", "s112", 0.710, k=2)
    r = pl_read(read_all(d))
    assert r["status"] == "PENDING"
    assert r["delta"] is None and r["sign"] is None and r["cell"] is None
    assert r["t_rate_partial"] == pytest.approx(0.710)
    assert r["t_chunks"] == "2/10"


# --------------------------------------------------------------------------
# the whole report, on a fully-populated synthetic fleet
# --------------------------------------------------------------------------
def test_full_report_prints_cells_disclosures_and_provenance(tmp_path):
    d = lay_out(
        tmp_path,
        a0={ln: 0.790 for ln in LANES},
        s3m=dict(zip(LANES, (0.740, 0.760, 0.750))),   # P-M -> NEG
        s3b=dict(zip(LANES, (0.790, 0.800, 0.795))),   # P-B -> POS vs S3M
        s3l={"s112": 0.770},
        a1e=dict(zip(LANES, (0.755, 0.765, 0.760))),   # P-E -> FLAT
    )
    rep = build(d, tmp_path / "offfp")
    assert rep["reads"]["P-M"]["cell"] == "NEG"
    assert rep["reads"]["P-B"]["cell"] == "POS"
    assert rep["reads"]["P-BA"]["cell"] == "FLAT"      # +0.0053 vs A0
    assert rep["reads"]["P-E"]["cell"] == "FLAT"       # +0.010, below floor
    assert rep["reads"]["P-L"]["cell"] is None
    assert rep["reads"]["P-L"]["sign"] == "+"
    # provenance
    p = rep["provenance"]
    assert p["prereg_vssh"]["sha256"] and p["prereg_offfp"]["sha256"]
    assert p["generated_at_utc"].endswith("+00:00")
    assert p["readout_script_sha256"]
    # the standing text, verbatim
    md = render_markdown(rep)
    assert CREDIT_LINE in md
    assert CREDITS_NOTHING in md
    for disc in FP20_DISCLOSURES:
        assert disc in md
    assert "CONTENDED" in md
    assert "20 ms" in md
    assert "0.50167" in md          # the banked off-FP comparator
    assert "0.79589" in md          # the banked vs-SH, context only
    assert rep["attest"]["pass"] is True


def test_leaves_equality_is_a_diagnostic_not_a_cell(tmp_path):
    d = lay_out(tmp_path,
                a0={ln: 0.790 for ln in LANES},
                s3m=dict(zip(LANES, (0.740, 0.760, 0.750))),
                s3b=dict(zip(LANES, (0.790, 0.800, 0.795))))
    rep = build(d, tmp_path / "offfp")
    lq = rep["leaves_equality"]
    assert lq["cell"] is None
    assert lq["pass"] is True                       # synthetic leaves are equal
    assert lq["rel_delta"] == pytest.approx(0.0)
    assert "never a cell" in lq["rule"]


def test_off_fp_anchor_is_pending_with_no_files(tmp_path):
    rep = build(lay_out(tmp_path, a0={ln: 0.79 for ln in LANES}),
                tmp_path / "offfp")
    o = rep["off_fp_anchor"]
    assert o["budget_ms"] == 20
    assert list(o["disclosures_verbatim"]) == list(FP20_DISCLOSURES)
    assert o["arms"]["F3M112"]["status"] == "PENDING"
    assert o["delta_B_minus_M"] is None


def test_off_fp_anchor_reads_a_real_shaped_final(tmp_path):
    od = tmp_path / "offfp"
    od.mkdir(parents=True)
    (od / "f3m112.json").write_text(json.dumps({
        "battles_requested": 1000, "battles_finished": 1000,
        "our_win_rate": 0.396, "foulplay_win_rate": 0.595, "tie_rate": 0.009,
        "mean_turns": 41.7, "mask_desyncs": 0}))
    (od / "f3m112.runner.json").write_text(json.dumps({"crash_forfeits": 0}))
    rep = build(lay_out(tmp_path, a0={ln: 0.79 for ln in LANES}), od)
    a = rep["off_fp_anchor"]["arms"]["F3M112"]
    assert a["status"] == "COMPLETE" and a["n_eff"] == 1000
    assert a["delta_vs_banked_greedy"] == pytest.approx(0.396 - 0.50167)
    assert rep["off_fp_anchor"]["arms"]["F3B112"]["status"] == "PENDING"
    assert rep["off_fp_anchor"]["delta_B_minus_M"] is None

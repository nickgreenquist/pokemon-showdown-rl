"""R0-14's verification: the D25 grader on synthetic cases with known answers.

The permutation tests carry a hand-derived known-p case from EACH enumerated
grid (n_T = 5/4/3 vs n_C = 5), as the pre-registration requires — including a
non-minimal p derived by hand (subset-sum counting over distinct integers),
so the test is not the implementation checking itself.
"""

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from d25_grade import (  # noqa: E402
    COMPARATOR_PATHS,
    FROZEN_COMPARATOR,
    N_PER_SEED,
    attest,
    exact_perm_p,
    grade_permutation,
    grade_primary,
    read_dormancy_csv,
    read_report,
    se_terms,
)

CONTROL5 = {26: 0.0, 27: 0.1, 28: 0.2, 50: 0.3, 51: 0.4}


# --------------------------------------------------------------------------
# exact permutation — known-p cases from each enumerated grid
# --------------------------------------------------------------------------


def test_perm_min_p_each_grid():
    # All treatment values strictly above all controls: the observed
    # assignment is the unique most extreme one -> p = 1/total.
    c = [1.0, 2.0, 3.0, 4.0, 5.0]
    for n_t, total in ((5, 252), (4, 126), (3, 56)):
        t = [10.0 + i for i in range(n_t)]
        count, tot, p = exact_perm_p(t, c, direction=+1)
        assert (count, tot) == (1, total)
        assert p == pytest.approx(1 / total)


def test_perm_known_p_hand_derived_n5():
    # Values 1..10, treatment {10,9,8,7,5}, sum 39. 5-subsets with sum >= 39:
    # {10,9,8,7,6} (40) and {10,9,8,7,5} (39) -> p = 2/252, by hand.
    t, c = [10, 9, 8, 7, 5], [6, 4, 3, 2, 1]
    count, total, p = exact_perm_p(t, c, direction=+1)
    assert (count, total) == (2, 252)

    # Treatment {10,9,8,6,5}, sum 38. Subsets with sum >= 38: one of 40, one
    # of 39, and exactly two of 38 ({10,9,8,7,4}, {10,9,8,6,5}) -> 4/252.
    t, c = [10, 9, 8, 6, 5], [7, 4, 3, 2, 1]
    count, total, p = exact_perm_p(t, c, direction=+1)
    assert (count, total) == (4, 252)


def test_perm_known_p_hand_derived_n4_n3():
    # n_T = 4, values 1..9, treatment {9,8,7,5}, sum 29. 4-subsets with
    # sum >= 29: {9,8,7,6} (30) and {9,8,7,5} (29) -> p = 2/126.
    count, total, _ = exact_perm_p([9, 8, 7, 5], [6, 4, 3, 2, 1], +1)
    assert (count, total) == (2, 126)
    # n_T = 3, values 1..8, treatment {8,7,5}, sum 20. 3-subsets with
    # sum >= 20: {8,7,6} (21) and {8,7,5} (20) -> p = 2/56 == the n_T=3 level.
    count, total, _ = exact_perm_p([8, 7, 5], [6, 4, 3, 2, 1], +1)
    assert (count, total) == (2, 56)


def test_perm_direction_lower():
    # S1's direction: treatment strictly BELOW every control is minimal p.
    count, total, _ = exact_perm_p([-1.0, -2.0, -3.0, -4.0, -5.0],
                                   [1.0, 2.0, 3.0, 4.0, 5.0], direction=-1)
    assert (count, total) == (1, 252)
    # And the same data under direction=+1 is maximally UN-extreme: every
    # assignment's statistic is >= the observed one.
    count, _, p = exact_perm_p([-1.0, -2.0, -3.0, -4.0, -5.0],
                               [1.0, 2.0, 3.0, 4.0, 5.0], direction=+1)
    assert p == 1.0


def test_perm_ties_count_as_extreme():
    # All values identical: every assignment ties the observed -> p = 1.
    _, _, p = exact_perm_p([0.5] * 5, [0.5] * 5, direction=+1)
    assert p == 1.0


def test_perm_letter_thresholds(capsys):
    # p = 2/56 fires exactly AT the n_T=3 level (<=), with the reduced-level
    # caveat printed; p = 3/56 does not fire.
    verdict = grade_permutation({1: 8, 2: 7, 3: 5},
                                {26: 6, 27: 4, 28: 3, 50: 2, 51: 1},
                                "at-level", direction=+1)
    out = capsys.readouterr().out
    assert verdict == "FIRED"
    assert "not equal-strength evidence" in out
    # {8,7,4}, sum 19: subsets >= 19: 21, 20 ({8,7,5}), 19 ({8,7,4}, {8,6,5})
    # -> 4/56 > 2/56.
    verdict = grade_permutation({1: 8, 2: 7, 3: 4},
                                {26: 6, 27: 5, 28: 3, 50: 2, 51: 1},
                                "above-level", direction=+1)
    assert verdict == "not fired"


def test_perm_void_and_ungraded():
    assert grade_permutation({1: 9.0, 2: 8.0}, CONTROL5, "void",
                             direction=+1) == "VOID"
    # n_C != 5: the enumerated levels don't apply -> report-only.
    assert grade_permutation({1: 9.0, 2: 8.0, 3: 7.0},
                             {26: 0.0, 27: 0.1, 28: 0.2}, "short-control",
                             direction=+1) == "NOT GRADED"


def test_perm_secondary_reported_not_graded(capsys):
    verdict = grade_permutation({s: 1.0 + s for s in range(5)}, CONTROL5,
                                "12-class", direction=+1, graded=False)
    assert verdict == "reported"
    assert "NOT" in capsys.readouterr().out


# --------------------------------------------------------------------------
# credit line (§4)
# --------------------------------------------------------------------------

COMP = dict(FROZEN_COMPARATOR)  # pooled 0.54452, sd 0.03558


def test_binomial_se_matches_header():
    # §4: binomial se_diff at 15,000 vs 15,000, p ~ 0.55 = 0.005745.
    se_b, _, _, _ = se_terms([0.55] * 5, 15000, [0.55] * 5, 15000)
    assert se_b == pytest.approx(0.005745, abs=1e-6)


def test_credit(capsys):
    t = {s: 0.62 + 0.001 * i for i, s in enumerate(range(52, 57))}
    assert grade_primary(t, COMP) == "CREDIT"
    assert "M4 TRIGGER" in capsys.readouterr().out  # 0.622 >= 0.558


def test_recording_band(capsys):
    # Equal seeds -> s_T = 0 -> 2*se_clus = 2*0.03558/sqrt(5) = 0.03182;
    # band = [0.5695, 0.5763). 0.575 is inside it, and above M4's 0.558.
    t = {s: 0.575 for s in range(52, 57)}
    assert grade_primary(t, COMP) == "letter-met, seed-fragile, NOT credited"
    assert "M4 TRIGGER" in capsys.readouterr().out


def test_flat_below_m4(capsys):
    t = {s: 0.55 for s in range(52, 57)}
    assert grade_primary(t, COMP) == "FLAT"
    assert "M4 TRIGGER" not in capsys.readouterr().out


def test_flat_above_m4_still_fires_obligations(capsys):
    # FLAT on the verdict, but pooled 0.560 >= 0.558: the obligations are
    # keyed to the NUMBER, not the verdict (§4).
    t = {s: 0.560 for s in range(52, 57)}
    assert grade_primary(t, COMP) == "FLAT"
    assert "M4 TRIGGER" in capsys.readouterr().out


def test_negative():
    # threshold = 0.54452 - max(0.025, 0.03182) = 0.51270 at s_T = 0.
    assert grade_primary({s: 0.50 for s in range(52, 57)}, COMP) == "NEGATIVE"
    assert grade_primary({s: 0.52 for s in range(52, 57)}, COMP) == "FLAT"


def test_lane_failure_recompute():
    # 4 survivors: still graded, se terms at n=4. 2 survivors: VOID.
    t4 = {s: 0.62 for s in (52, 53, 54, 55)}
    assert grade_primary(t4, COMP) == "CREDIT"
    assert grade_primary({52: 0.62, 53: 0.62}, COMP) == "VOID"


def test_clustered_governs_and_scales_with_spread():
    # The larger-of clause: with a D23-sized treatment spread the clustered
    # term governs and a delta the binomial would credit is only letter-met.
    t = {52: 0.630, 53: 0.560, 54: 0.520, 55: 0.640, 56: 0.525}  # s ~ 0.057
    tv = sorted(t.values())
    s_t = math.sqrt(sum((x - sum(tv) / 5) ** 2 for x in tv) / 4)
    se_b, se_c, _, _ = se_terms(tv, 15000, sorted(COMP.values()), 15000)
    assert se_c > se_b  # clustered governs
    pooled = sum(tv) / 5  # 0.575: delta +0.0305 >= 0.025 but < 2*se_c
    assert pooled - 0.54452 < 2 * se_c
    assert grade_primary(t, COMP) == "letter-met, seed-fragile, NOT credited"
    assert s_t > 0.02


# --------------------------------------------------------------------------
# R0-4, dormancy CSV, attestation
# --------------------------------------------------------------------------


def test_r04_hard_fail(tmp_path):
    p = tmp_path / "final_s52.json"
    p.write_text(json.dumps({"eval/win_rate": 0.6, "wins_from_returns": 0.4,
                             "episodes": 3000}))
    r04 = []
    read_report(p, r04)
    assert r04 == ["final_s52.json"]


def test_read_dormancy_csv(tmp_path):
    p = tmp_path / "dorm.csv"
    p.write_text(
        "seed,step,part,layer,tau025,tau100,n\n"
        "52,12000000,actor,ctx_net.1,0.41,0.5,384\n"
        "52,12000000,critic,ctx_net.1,0.9,0.9,384\n"   # wrong part
        "52,6000000,actor,ctx_net.1,0.3,0.4,384\n"     # wrong step
        "53,12000000,actor,ctx_net.1,0.44,0.5,384\n")
    assert read_dormancy_csv([p], (52, 53, 54)) == {52: 0.41, 53: 0.44}


def test_attest_rejects_drifted_comparator(tmp_path):
    paths = {}
    for i, s in enumerate(sorted(FROZEN_COMPARATOR)):
        p = tmp_path / f"c{s}.json"
        wr = FROZEN_COMPARATOR[s] + (0.01 if i == 0 else 0.0)  # drift s26
        p.write_text(json.dumps({"eval/win_rate": wr, "wins_from_returns": wr,
                                 "episodes": N_PER_SEED}))
        paths[s] = p
    with pytest.raises(SystemExit, match="ATTESTATION FAILED"):
        attest(comparator_paths=paths, tape_dir=tmp_path)


@pytest.mark.skipif(
    not all(p.exists() for p in COMPARATOR_PATHS.values())
    or not (REPO / "results/d25/oppact_s36ref.npz").exists(),
    reason="frozen comparator finals / reference tapes not on this machine",
)
def test_attest_passes_on_real_frozen_inputs(capsys):
    rates = attest()
    out = capsys.readouterr().out
    assert "ATTESTATION PASS" in out
    assert "0.54452" in out and "3ffee9" in out
    assert rates[50] == pytest.approx(0.5763333, abs=1e-6)

"""R-4's verification: the placebo §6 decision logic on hand-derived cases.

The estimator itself is d25_gates'/d25_manipulation's and is already covered;
what is new in R-4 is the band structure — two views of one statistic, a
negative branch that is a derangement rather than a leak, and a middle cell
the header names explicitly. Those are what these tests pin.
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from d25p_manipulation import (  # noqa: E402
    A0_REF,
    CONFIRM,
    LEAK,
    STEPS,
    classify_g,
    classify_head,
    rising,
    uniform_over_legal,
)


# --------------------------------------------------------------------------
# VIEW 1 — |g_P| bands, including the signed negative branch
# --------------------------------------------------------------------------


def test_g_confirmed_band_is_two_sided():
    # The band is on |g_P|: a small NEGATIVE g_P confirms the shuffle just as
    # a small positive one does.
    for g in (0.0, CONFIRM, -CONFIRM, 0.019, -0.019):
        assert classify_g(g) == "SHUFFLE CONFIRMED", g


def test_g_residual_band_is_open_at_both_ends():
    for g in (0.0201, 0.0999, -0.0201, -0.0999):
        assert classify_g(g) == "RESIDUAL", g


def test_g_leak_and_derangement_split_by_sign():
    # Same magnitude, different branch: >= +0.10 is a LEAK, <= -0.10 is a
    # DERANGEMENT (anti-information), and the header VOIDs the arm either way.
    assert classify_g(LEAK) == "LEAK"
    assert classify_g(0.42) == "LEAK"
    assert classify_g(-LEAK) == "DERANGEMENT"
    assert classify_g(-0.42) == "DERANGEMENT"


def test_g_band_boundaries_are_inclusive_as_written():
    # header: "|g_P| <= 0.02 -> CONFIRMED", ">= 0.10 -> LEAK".
    assert classify_g(0.02) == "SHUFFLE CONFIRMED"
    assert classify_g(0.10) == "LEAK"


# --------------------------------------------------------------------------
# VIEW 2 — NLL_head against the floor
# --------------------------------------------------------------------------

A1 = 1.500
A0 = 1.776          # inside the treatment-tape reference range


def test_head_trained_to_floor_is_the_designed_outcome():
    for nh in (A1, A1 + 0.019, A1 - 0.019, A1 + 0.005):
        assert classify_head(nh, A1, A0) == "TRAINED-TO-FLOOR", nh


def test_head_floor_boundary_is_not_defended_to_the_last_bit():
    # A1 + 0.02 is not exactly representable (1.5 + 0.02 exceeds A1 by
    # 0.020000000000000018), so the inclusive <= in the header falls the other
    # way at the bit level. Recorded, not worked around: real NLL_head values
    # do not land on the boundary, and a lane that did would be reported as
    # NEAR-FLOOR, which is a disclosure, not a silent reclassification.
    assert classify_head(A1 + 0.02, A1, A0).startswith("NEAR-FLOOR")
    assert classify_head(1.52, 1.5000000000000002, A0) == "TRAINED-TO-FLOOR"


def test_head_never_trained_voids_the_arm():
    for nh in (A0, A0 - 0.05, A0 + 0.1):
        assert classify_head(nh, A1, A0) == "NEVER-TRAINED", nh


def test_head_partially_trained_middle_cell():
    # Strictly between A1 + 0.05 and A0 - 0.05: dose not matched -> R-1 is
    # dose-caveated, NOT void (review R2-11).
    for nh in (A1 + 0.06, 1.65, A0 - 0.06):
        assert classify_head(nh, A1, A0) == "PARTIALLY-TRAINED", nh


def test_head_unnamed_cell_is_surfaced_not_folded():
    # (A1 + 0.02, A1 + 0.05] is not named by the header. It must not be
    # silently reported as either neighbour.
    v = classify_head(A1 + 0.04, A1, A0)
    assert v.startswith("NEAR-FLOOR")
    assert v not in ("TRAINED-TO-FLOOR", "PARTIALLY-TRAINED")


def test_head_below_floor_is_flagged():
    # Beating the marginal by a wide margin is the g_P > 0 story in NLL units;
    # it must not read as "trained to floor".
    assert classify_head(A1 - 0.20, A1, A0) == "BELOW-FLOOR"


def test_never_trained_wins_when_a0_and_a1_are_close():
    # Precedence guard: if a lane's own A1 and A0 nearly coincide, the
    # never-trained branch is the conservative read (it VOIDs the arm).
    assert classify_head(1.77, 1.76, 1.78) == "NEVER-TRAINED"


# --------------------------------------------------------------------------
# trajectory — the leak signature
# --------------------------------------------------------------------------


def test_rising_uses_absolute_value_so_negative_drift_counts():
    assert rising(dict(zip(STEPS, (-0.01, -0.05, -0.12))))
    assert rising(dict(zip(STEPS, (0.01, 0.05, 0.12))))


def test_flat_or_falling_is_not_the_leak_signature():
    assert not rising(dict(zip(STEPS, (0.01, 0.01, 0.01))))
    assert not rising(dict(zip(STEPS, (0.09, 0.05, 0.01))))
    assert not rising(dict(zip(STEPS, (0.01, 0.09, 0.05))))
    # sign flips around zero are not a rising magnitude
    assert not rising(dict(zip(STEPS, (0.05, -0.02, 0.01))))


# --------------------------------------------------------------------------
# A0 is measured, not assumed
# --------------------------------------------------------------------------


def test_uniform_over_legal_is_log_of_the_legal_count():
    m6 = np.zeros((3, 6), bool)
    m6[0, :6] = True          # 6 legal -> log 6
    m6[1, :3] = True          # 3 legal -> log 3
    m6[2, :2] = True          # 2 legal -> log 2
    got = uniform_over_legal(m6, np.arange(3))
    assert got == np.log([6.0, 3.0, 2.0]).mean()


def test_uniform_over_legal_honours_the_split_index():
    m6 = np.zeros((4, 6), bool)
    m6[:2, :6] = True
    m6[2:, :2] = True
    assert uniform_over_legal(m6, np.array([0, 1])) == np.log(6.0)
    assert uniform_over_legal(m6, np.array([2, 3])) == np.log(2.0)


def test_all_six_legal_reproduces_the_documented_a0_scale():
    # Sanity anchor for the whole view-2 read: the treatment tapes recorded
    # A0 = 1.773-1.780 and all-six-legal is log 6 = 1.7918, so the reference
    # range must sit just below the all-legal ceiling. A formula that landed
    # elsewhere would be measuring something else.
    m6 = np.ones((10, 6), bool)
    ceiling = uniform_over_legal(m6, np.arange(10))
    assert np.isclose(ceiling, np.log(6.0))
    assert A0_REF[0] < A0_REF[1] < ceiling
    assert ceiling - A0_REF[1] < 0.02

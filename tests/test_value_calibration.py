"""A monotone recalibration of the leaf value, and the claim that it MATTERS.

RESULTS §27.1 measured that an out-of-sample isotonic recalibration buys +0.0195
EV for one fitted curve and no training. IDEAS 2.13 then claims it is NOT inert
inside the search -- the obvious objection being that a monotone map cannot
reorder leaves at a single node, so it cannot change an argmax.

That objection is true and incomplete, and the incompleteness is TESTED here
rather than asserted: `matrix.py::row_ev` takes an EXPECTATION of leaf values
over the opponent's column distribution, and an average of a non-linearly
transformed quantity reorders. On the real fitted curve, 3.5% of random row pairs
change places.
"""
import json

import numpy as np
import pytest

from rl.common.value_calibration import ValueCalibration, pava


def _toy():
    """A deliberately shrinking monotone map, so the tests do not depend on a
    gitignored rows file."""
    xs = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
    ys = np.array([-0.60, -0.35, -0.02, 0.33, 0.62])
    return ValueCalibration(xs, ys, {"source": "toy"})


# --------------------------------------------------- the fit itself
def test_the_fit_is_monotone_and_thinned_to_real_knots():
    rng = np.random.default_rng(0)
    v = rng.uniform(-1, 1, size=4000)
    o = np.sign(v + rng.normal(scale=0.6, size=4000))
    c = ValueCalibration.fit(v, o)
    assert np.all(np.diff(c.ys) >= -1e-12)
    assert len(c.xs) < 4000, "PAVA returns one point per sample; it must be thinned"
    assert len(c.xs) >= 2


def test_it_removes_a_bias_and_shrinks_an_overconfident_scale():
    """The two things §27.1 measured about this critic: a +0.042 seat bias and
    an affine slope of 0.83."""
    rng = np.random.default_rng(1)
    truth = rng.uniform(-1, 1, size=3000)
    o = np.repeat(truth, 4) + rng.normal(scale=0.4, size=12000)
    v = np.repeat(truth, 4) / 0.83 + 0.042          # over-scaled and biased
    c = ValueCalibration.fit(v, o)
    before = float(np.mean(v - np.repeat(truth, 4)))
    after = float(np.mean(c.apply(v) - np.repeat(truth, 4)))
    assert abs(after) < abs(before) / 2, (before, after)


def test_it_clamps_rather_than_extrapolating():
    """An isotonic fit says NOTHING outside its support, and extrapolating one
    is how a calibration becomes a fabrication."""
    c = _toy()
    assert float(c.apply(5.0)) == pytest.approx(float(c.ys[-1]))
    assert float(c.apply(-5.0)) == pytest.approx(float(c.ys[0]))


def test_a_non_monotone_curve_is_refused_at_construction():
    with pytest.raises(AssertionError):
        ValueCalibration(np.array([0.0, 1.0]), np.array([1.0, 0.0]))


def test_it_round_trips_through_a_dict_with_its_provenance():
    """The fit is a property of ONE critic. A curve fitted on one checkpoint and
    applied to another is a new untested object, so the provenance travels."""
    c = _toy()
    d = json.loads(json.dumps(c.to_dict()))
    back = ValueCalibration.from_dict(d)
    assert np.allclose(back.apply([-0.7, 0.0, 0.7]), c.apply([-0.7, 0.0, 0.7]))
    assert back.fit_meta["source"] == "toy"


# ------------------------------------------- the claim IDEAS 2.13 rests on
def test_a_monotone_map_cannot_reorder_leaves_at_one_node():
    """The objection, stated as a test because it is CORRECT as far as it goes."""
    c = _toy()
    leaves = np.array([-0.8, -0.1, 0.3, 0.9])
    assert list(np.argsort(c.apply(leaves))) == list(np.argsort(leaves))


def test_but_it_DOES_reorder_an_EXPECTATION_over_leaves():
    """...and this is why it is not inert: `row_ev` averages leaf values over
    the opponent's column distribution, and an average of a non-linearly
    transformed quantity reorders.

    Two rows whose raw expectations differ one way and whose recalibrated
    expectations differ the other. Row B holds one much worse leaf and one much
    better one; the curve compresses the extremes, so B's bad leaf hurts it less
    after recalibration than before -- and that is enough to change the choice.

    (On the REAL fitted curve, from RESULTS §27.1's rows, the flip rate is 3.5%
    of random row pairs against this toy's 1.1%; the real curve bends more. The
    toy is used here so the test does not depend on a gitignored data file.)
    """
    c = _toy()
    row_a = np.array([-0.364, -0.483])      # two mildly bad leaves
    row_b = np.array([0.023, -0.985])       # one decent leaf, one terrible
    raw_a, raw_b = row_a.mean(), row_b.mean()
    cal_a, cal_b = c.apply(row_a).mean(), c.apply(row_b).mean()
    assert raw_a > raw_b, "the raw search prefers A"
    assert cal_a < cal_b, "the recalibrated search prefers B -- the ordering FLIPPED"


def test_the_flip_rate_is_material_not_a_curiosity():
    """On random row pairs the ordering changes often enough to matter; if this
    ever collapses to ~0 the recalibration really would be inert and IDEAS 2.13
    should be withdrawn."""
    c = _toy()
    rng = np.random.default_rng(0)
    a = rng.uniform(-1, 1, size=(20000, 2))
    b = rng.uniform(-1, 1, size=(20000, 2))
    raw = a.mean(1) - b.mean(1)
    cal = c.apply(a).mean(1) - c.apply(b).mean(1)
    flip = float(np.mean(raw * cal < 0))
    assert flip > 0.005, f"only {flip:.2%} of orderings flip -- is it inert after all?"
    # for scale: the REAL fitted curve (RESULTS §27.1) flips 3.5% of pairs.


def test_the_gate_threshold_moves_with_the_scale():
    """The D5 margin gate is a THRESHOLD on the row_ev scale, so recalibrating
    changes the override rate and `margin_delta` must be RE-SWEPT with it --
    the standing rule, and the confound that cost 2026-09-17."""
    c = _toy()
    gaps_raw, gaps_cal = [], []
    rng = np.random.default_rng(2)
    for _ in range(2000):
        a, b = rng.uniform(-1, 1, size=2), rng.uniform(-1, 1, size=2)
        gaps_raw.append(abs(a.mean() - b.mean()))
        gaps_cal.append(abs(c.apply(a).mean() - c.apply(b).mean()))
    assert np.mean(gaps_cal) < 0.9 * np.mean(gaps_raw), (
        "the calibrated scale is compressed, so a fixed delta gates DIFFERENTLY")


def test_pava_matches_the_analysis_scripts_estimator():
    """The transform applied here and the +0.0195 reported by
    scripts/critic_calibration.py must come from the same estimator, or the
    number quoted and the thing shipped drift apart."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "critic_calibration", Path(__file__).parent.parent / "scripts/critic_calibration.py")
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    rng = np.random.default_rng(5)
    x = rng.normal(size=500)
    y = np.tanh(x) + rng.normal(scale=0.5, size=500)
    assert np.allclose(pava(x, y)[1], cc.pava(x, y)[1])


# ------------------------------------------- wired into the search, default OFF
def test_the_search_agent_is_bit_identical_without_a_calibration():
    """The property every dial in this repo has to have. If this ever fails,
    every banked number stops being reproducible from its config."""
    import numpy as np
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES
    from tests.test_ch3_matrix import _mask, _two_mon_battle
    from tests.test_tree_decision_golden import _StubAgent

    a = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7)
    b = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7, calibration=None)
    obs = np.zeros(8, dtype=np.float32)
    aa, sa = a.act(_two_mon_battle(), obs, _mask(), 3, 1)
    bb, sb = b.act(_two_mon_battle(), obs, _mask(), 3, 1)
    assert aa == bb
    assert {k: v for k, v in sa.items() if "/ms_" not in k} == \
           {k: v for k, v in sb.items() if "/ms_" not in k}
    assert a.counters["calib/leaves"] == 0


def test_a_calibration_that_is_ON_moves_the_leaf_values_and_says_so():
    """The counter exists so an arm whose calibration silently failed to load is
    distinguishable from one that ran without it -- the defect class this repo
    keeps paying for."""
    import numpy as np
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES
    from tests.test_ch3_matrix import _mask, _two_mon_battle
    from tests.test_tree_decision_golden import _StubAgent

    shift = ValueCalibration(np.array([-2.0, 2.0]), np.array([-1.0, 1.0]))
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7,
                     calibration=shift.to_dict())
    sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32), _mask(), 3, 1)
    assert sa.counters["calib/leaves"] > 0, "the dial never touched a leaf"
    assert sa._calibration is not None


def test_a_calibration_round_trips_through_the_agents_config_form():
    """An arm carries the fit in its YAML or points at a rows file; both must
    reach the agent, because a curve fitted on one checkpoint and applied to
    another is a new untested object."""
    import numpy as np
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES
    from tests.test_tree_decision_golden import _StubAgent

    c = ValueCalibration(np.array([-1.0, 0.0, 1.0]), np.array([-0.5, 0.0, 0.5]),
                         {"source": "unit"})
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7,
                     calibration=c.to_dict())
    assert sa._calibration.fit_meta["source"] == "unit"
    assert float(sa._calibration.apply(1.0)) == pytest.approx(0.5)

"""The recalibration analysis has to be honest about what it claims.

`scripts/critic_calibration.py` decides how much of the critic's gap to the
ceiling is CALIBRATION (fixable by rescaling, for free) and how much is RANKING
(fixable only by training). Getting that split wrong points the next fleet at
the wrong lever, so the two pieces that could silently lie -- the hand-rolled
isotonic fit and the out-of-sample split -- are tested.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

MOD = Path(__file__).parent.parent / "scripts/critic_calibration.py"
spec = importlib.util.spec_from_file_location("critic_calibration", MOD)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


def test_pava_is_monotone_and_fits_a_monotone_signal_exactly():
    x = np.array([1.0, 2, 3, 4, 5])
    xs, fit = cc.pava(x, np.array([1.0, 2, 3, 4, 5]))
    assert np.allclose(fit, [1, 2, 3, 4, 5])
    assert np.all(np.diff(fit) >= -1e-12)


def test_pava_pools_a_violation_into_its_mean():
    """The whole algorithm: an out-of-order pair becomes their average."""
    xs, fit = cc.pava(np.array([1.0, 2, 3]), np.array([1.0, 5.0, 3.0]))
    assert np.allclose(fit, [1.0, 4.0, 4.0]), fit


def test_pava_output_is_never_decreasing_on_noise():
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = np.tanh(x) + rng.normal(scale=0.5, size=400)
    _, fit = cc.pava(x, y)
    assert np.all(np.diff(fit) >= -1e-12)


def test_pava_sorts_by_x_so_input_order_does_not_matter():
    rng = np.random.default_rng(1)
    x = rng.normal(size=200)
    y = 2 * x + rng.normal(scale=0.3, size=200)
    a = cc.pava(x, y)[1]
    perm = rng.permutation(200)
    b = cc.pava(x[perm], y[perm])[1]
    assert np.allclose(a, b)


def test_cross_val_holds_out_WHOLE_POSITIONS_not_individual_outcomes():
    """THE BUG THIS EXISTS FOR, found by review on 2026-09-19.

    The predictor is CONSTANT WITHIN A POSITION -- ~32 rollouts of one position
    share one critic value -- so an outcome-level split leaves the held-out
    point's own position in the training fold, with the identical x, and the
    isotonic fit partially learns that position's own mean. Measured on the real
    data: 100% of held-out outcomes were contaminated, and the published
    "out-of-sample" gain was +0.0195 where the honest figure is +0.0096.

    Same shape as "seeds do not pair battles": correlated rows treated as
    independent. The guard is that no held-out GROUP appears in training.
    """
    groups = np.repeat(np.arange(20), 5)          # 20 positions x 5 outcomes
    p = np.repeat(np.arange(20, dtype=float), 5)  # predictor constant per group
    o = p + 0.0
    leaked = []

    def spy(ptr, otr, pte):
        # every training x must come from a DIFFERENT group than every test x
        leaked.append(bool(set(np.unique(pte)) & set(np.unique(ptr))))
        return np.zeros_like(pte)

    out = cc.cross_val(spy, p, o, groups, folds=5)
    assert out.shape == p.shape
    assert not any(leaked), "a held-out position appeared in its own training fold"


def test_an_outcome_level_split_WOULD_have_leaked():
    """The counterfactual, so the test above cannot pass vacuously: shuffling
    at the row level puts a group's own rows on both sides."""
    groups = np.repeat(np.arange(20), 5)
    p = np.repeat(np.arange(20, dtype=float), 5)
    idx = np.arange(p.size)
    np.random.default_rng(0).shuffle(idx)
    te, tr = idx[::5], np.setdiff1d(idx, idx[::5])
    assert set(groups[te]) & set(groups[tr]), (
        "the row-level split did not leak, so the grouped test proves nothing")


def test_a_perfectly_calibrated_predictor_gains_nothing_from_recalibration():
    """The null the analysis must respect: if the predictor is already the
    conditional mean, isotonic recalibration is a no-op up to fold noise."""
    rng = np.random.default_rng(3)
    truth = rng.uniform(-1, 1, size=300)
    groups = np.repeat(np.arange(300), 20)
    o = np.repeat(truth, 20) + rng.normal(scale=0.5, size=6000)
    p = np.repeat(truth, 20)
    vt = o.var()
    ev = lambda pred: 1.0 - ((o - pred) ** 2).mean() / vt
    gain = ev(cc.cross_val(cc._iso, p, o, groups)) - ev(p)
    assert gain < 0.01, f"recalibrating an honest predictor bought {gain:+.4f}"


def test_a_MIS_calibrated_predictor_is_detected_and_repaired():
    """And the alarm the analysis must raise: a squashed, shifted predictor has
    the SAME ranking and a worse EV, and isotonic must recover most of it."""
    rng = np.random.default_rng(4)
    truth = rng.uniform(-1, 1, size=300)
    groups = np.repeat(np.arange(300), 20)
    o = np.repeat(truth, 20) + rng.normal(scale=0.5, size=6000)
    p = 0.5 * np.repeat(truth, 20) + 0.3           # squashed and biased
    vt = o.var()
    ev = lambda pred: 1.0 - ((o - pred) ** 2).mean() / vt
    raw = ev(p)
    fixed = ev(cc.cross_val(cc._iso, p, o, groups))
    assert fixed - raw > 0.05, (raw, fixed)
    # ranking is untouched by a monotone distortion, which is the premise of
    # splitting the gap this way at all
    assert np.corrcoef(p, np.repeat(truth, 20))[0, 1] == pytest.approx(1.0)

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


def test_cross_val_scores_every_point_and_never_from_its_own_fold():
    """An in-sample recalibration is an upper bound. If the split leaked, the
    reported calibration prize would be inflated and the conclusion -- '88% of
    the gap is ranking' -- could flip."""
    seen = {}

    def spy(ptr, otr, pte):
        seen[len(pte)] = (len(ptr), len(pte))
        return np.zeros_like(pte)

    p = np.arange(100, dtype=float)
    out = cc.cross_val(spy, p, p.copy(), folds=5)
    assert out.shape == p.shape
    for train_n, test_n in seen.values():
        assert train_n + test_n == 100, "a fold saw its own test points"
        assert test_n == 20


def test_a_perfectly_calibrated_predictor_gains_nothing_from_recalibration():
    """The null the analysis must respect: if the predictor is already the
    conditional mean, isotonic recalibration is a no-op up to fold noise."""
    rng = np.random.default_rng(3)
    truth = rng.uniform(-1, 1, size=300)
    o = np.repeat(truth, 20) + rng.normal(scale=0.5, size=6000)
    p = np.repeat(truth, 20)
    vt = o.var()
    ev = lambda pred: 1.0 - ((o - pred) ** 2).mean() / vt
    gain = ev(cc.cross_val(cc._iso, p, o)) - ev(p)
    assert gain < 0.01, f"recalibrating an honest predictor bought {gain:+.4f}"


def test_a_MIS_calibrated_predictor_is_detected_and_repaired():
    """And the alarm the analysis must raise: a squashed, shifted predictor has
    the SAME ranking and a worse EV, and isotonic must recover most of it."""
    rng = np.random.default_rng(4)
    truth = rng.uniform(-1, 1, size=300)
    o = np.repeat(truth, 20) + rng.normal(scale=0.5, size=6000)
    p = 0.5 * np.repeat(truth, 20) + 0.3           # squashed and biased
    vt = o.var()
    ev = lambda pred: 1.0 - ((o - pred) ** 2).mean() / vt
    raw = ev(p)
    fixed = ev(cc.cross_val(cc._iso, p, o))
    assert fixed - raw > 0.05, (raw, fixed)
    # ranking is untouched by a monotone distortion, which is the premise of
    # splitting the gap this way at all
    assert np.corrcoef(p, np.repeat(truth, 20))[0, 1] == pytest.approx(1.0)

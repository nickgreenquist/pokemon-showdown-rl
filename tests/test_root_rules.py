"""R7 -- the root rules over a payoff matrix (`rl/search/root_rules.py`):
regret matching's average strategy reaches the matrix's equilibrium (matching
pennies -> the uniform mix with a vanishing gap; a dominant row -> that row),
the soft best response at tau -> 0 is the pure best response, and `evaluate`
reads a mixed strategy's value under a column distribution and against the
worst column. numpy only."""

from __future__ import annotations

import numpy as np

from rl.search import root_rules as rr


def test_regret_matching_finds_matching_pennies_and_a_dominant_row():
    pennies = np.array([[1.0, -1.0], [-1.0, 1.0]])
    sr, sc, gap = rr.regret_matching(pennies, iters=4000)
    assert np.allclose(sr, [0.5, 0.5], atol=0.02) and np.allclose(sc, [0.5, 0.5], atol=0.02)
    assert gap < 0.05
    dominant = np.array([[0.3, 0.2, 0.1], [0.8, 0.7, 0.9], [0.0, 0.5, 0.4]])
    sr, sc, gap = rr.regret_matching(dominant, iters=2000)
    assert sr[1] > 0.98 and gap < 0.02
    # The average strategy is robust: its worst column is within the gap of
    # the game value, which no pure row can beat here.
    ev = rr.evaluate(sr, dominant, np.full(3, 1 / 3))
    assert ev["vs_best_reply"] >= dominant.min(axis=1).max() - 0.02


def test_soft_best_response_limits_and_evaluate():
    q = np.array([[0.2, -0.4], [0.1, 0.3], [-0.5, 0.6]])
    prior = np.array([0.5, 0.3, 0.2])
    q_col = np.array([0.7, 0.3])
    hot = rr.soft_best_response(q, prior, q_col, tau=1e-3)
    assert np.array_equal(hot.round(6), rr.pure_best_response(q, q_col).round(6))
    cold = rr.soft_best_response(q, prior, q_col, tau=1e6)
    assert np.allclose(cold, prior, atol=1e-4)
    sigma = np.array([0.0, 1.0, 0.0])
    ev = rr.evaluate(sigma, q, q_col)
    assert np.isclose(ev["under_prior"], 0.1 * 0.7 + 0.3 * 0.3) and np.isclose(ev["vs_best_reply"], 0.1)
    assert np.array_equal(rr.maximin(q), [0.0, 1.0, 0.0])
    assert np.array_equal(rr.apply_rule("greedy", q, prior, q_col, 2), [0.0, 0.0, 1.0])

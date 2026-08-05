"""RolloutBuffer mechanics and hand-computed GAE cases.

Every GAE expectation below is worked by hand from the recursion
    delta_t = r_t + gamma * next_V_t * (1 - terminated_t) - V_t
    A_t     = delta_t + gamma * lam * (1 - done_t) * A_{t+1}
so a regression here points at the code, not at a second implementation
of the same formula.
"""

import numpy as np
import pytest

from rl.buffers.rollout import RolloutBuffer, compute_gae


def col(x):
    """One env's scalars -> a (T, 1) column."""
    return np.array(x, dtype=np.float32).reshape(-1, 1)


def test_gae_lambda_zero_is_td_error():
    # lam=0 keeps only delta_t. gamma=0.9:
    # A_0 = 1 + 0.9*1.0 - 0.5 = 1.4 ; A_1 = 2 + 0.9*2.0 - 1.0 = 2.8
    adv = compute_gae(
        rewards=col([1, 2]),
        terminated=col([0, 0]),
        truncated=col([0, 0]),
        values=col([0.5, 1.0]),
        next_values=col([1.0, 2.0]),
        gamma=0.9,
        lam=0.0,
    )
    np.testing.assert_allclose(adv, col([1.4, 2.8]), rtol=1e-6)


def test_gae_lambda_one_is_monte_carlo_minus_baseline():
    # gamma=lam=1 telescopes to A_t = (sum of rewards from t) + V_end - V_t:
    # A_0 = 3 + 0.5 - 2 = 1.5 ; A_1 = 2 + 0.5 - 1 = 1.5 ; A_2 = 1 + 0.5 - 1 = 0.5
    adv = compute_gae(
        rewards=col([1, 1, 1]),
        terminated=col([0, 0, 0]),
        truncated=col([0, 0, 0]),
        values=col([2, 1, 1]),
        next_values=col([1, 1, 0.5]),
        gamma=1.0,
        lam=1.0,
    )
    np.testing.assert_allclose(adv, col([1.5, 1.5, 0.5]), rtol=1e-6)


def test_gae_termination_masks_bootstrap_and_cuts_chain():
    # gamma=0.5, lam=0.5, terminal at t=1. next_V_1=9 is poison: it must be
    # masked by (1 - terminated). delta = [0.5, 0 (no bootstrap), 0.5];
    # A_2 = 0.5 ; A_1 = 0 (chain cut at done) ; A_0 = 0.5 + 0.25 * 0 = 0.5
    adv = compute_gae(
        rewards=col([1, 1, 1]),
        terminated=col([0, 1, 0]),
        truncated=col([0, 0, 0]),
        values=col([1, 1, 1]),
        next_values=col([1, 9, 1]),
        gamma=0.5,
        lam=0.5,
    )
    np.testing.assert_allclose(adv, col([0.5, 0.0, 0.5]), rtol=1e-6)


def test_gae_truncation_keeps_bootstrap_but_cuts_chain():
    # Same shape but the t=1 boundary is a truncation: the bootstrap stays
    # (next_V_1 = 2 is V(true final obs)), the chain still cuts.
    # delta_1 = 1 + 0.5*2 - 1 = 1 ; A_1 = 1 ; A_0 = 0.5 + 0.25 * 1 = 0.75
    adv = compute_gae(
        rewards=col([1, 1, 1]),
        terminated=col([0, 0, 0]),
        truncated=col([0, 1, 0]),
        values=col([1, 1, 1]),
        next_values=col([1, 2, 1]),
        gamma=0.5,
        lam=0.5,
    )
    np.testing.assert_allclose(adv, col([0.75, 1.0, 0.5]), rtol=1e-6)


def test_gae_envs_are_independent():
    # The two boundary cases above stacked as columns of one (T, 2) rollout
    # must reproduce their single-env answers exactly.
    adv = compute_gae(
        rewards=np.ones((3, 2), dtype=np.float32),
        terminated=np.array([[0, 0], [1, 0], [0, 0]], dtype=np.float32),
        truncated=np.array([[0, 0], [0, 1], [0, 0]], dtype=np.float32),
        values=np.ones((3, 2), dtype=np.float32),
        next_values=np.array([[1, 1], [9, 2], [1, 1]], dtype=np.float32),
        gamma=0.5,
        lam=0.5,
    )
    expected = np.array([[0.5, 0.75], [0.0, 1.0], [0.5, 0.5]], dtype=np.float32)
    np.testing.assert_allclose(adv, expected, rtol=1e-6)


def test_rollout_buffer_fill_drain_refill():
    buf = RolloutBuffer(horizon=3, num_envs=2, obs_shape=(4,), n_actions=3, obs_dtype=np.bool_)
    assert buf.obs.dtype == np.bool_  # env dtype preserved, as in replay
    assert buf.masks.dtype == np.bool_ and buf.masks.shape == (3, 2, 3)
    obs = np.ones((2, 4), dtype=np.bool_)
    masks = np.array([[True, False, True], [True, True, False]])
    for t in range(3):
        assert not buf.full()
        buf.add(obs, np.array([0, 1]), np.array([1.0, 2.0]), obs,
                np.array([False, True]), np.array([False, False]), masks)
    assert buf.full()
    assert len(buf) == 6  # 3 steps x 2 envs
    assert buf.terminated[0, 1] == 1.0  # bool flags land as float masks
    assert (buf.masks[2] == masks).all()  # per-row legality stored verbatim
    with pytest.raises(IndexError):  # overfilling is a bug in the caller
        buf.add(obs, np.array([0, 1]), np.array([1.0, 2.0]), obs,
                np.array([False, False]), np.array([False, False]), masks)
    buf.clear()
    assert len(buf) == 0 and not buf.full()
    buf.add(obs, np.array([1, 1]), np.array([0.5, 0.5]), obs,
            np.array([False, False]), np.array([True, True]), masks)
    assert len(buf) == 2 and buf.truncated[0, 0] == 1.0


def test_rollout_buffer_stores_continuous_actions_and_no_masks():
    """Box spaces: actions keep their own (act_dim,) shape and float dtype,
    and no mask array is allocated — `masks is None` marks "continuous", a
    fact fixed at construction so algorithm code never branches on a runtime
    mask value. act_dim is 2, not 1: a length-1 action vector is
    shape-degenerate and hides exactly the broadcast bugs this guards."""
    buf = RolloutBuffer(
        horizon=2, num_envs=3, obs_shape=(4,), obs_dtype=np.float64,
        action_shape=(2,), action_dtype=np.float32,
    )
    assert buf.actions.shape == (2, 3, 2) and buf.actions.dtype == np.float32
    assert buf.masks is None
    obs = np.zeros((3, 4), dtype=np.float64)
    actions = np.array([[0.5, -0.5], [1.5, -1.5], [2.5, -2.5]], dtype=np.float32)
    # add() takes no mask on this path.
    buf.add(obs, actions, np.zeros(3), obs, np.zeros(3, bool), np.zeros(3, bool))
    np.testing.assert_array_equal(buf.actions[0], actions)
    assert len(buf) == 3

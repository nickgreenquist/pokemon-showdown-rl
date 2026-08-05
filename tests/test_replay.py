"""Replay buffer: storage layout, the ring, and the sampling contract.

Until SAC arrived this buffer had no direct tests at all — only DQN's, which
exercise it through a whole agent and would not distinguish a storage bug from
a learning bug. The continuous track makes that gap expensive: a Box action
buffer that quietly kept the Discrete int64 dtype would TRUNCATE every action
to zero, and a DQN-shaped test suite can never see it.
"""

import numpy as np
import pytest

from rl.buffers.replay import ReplayBuffer

OBS_SHAPE = (4,)
ACT_DIM = 3


def _discrete(capacity=8, n_actions=2):
    return ReplayBuffer(capacity, OBS_SHAPE, n_actions=n_actions)


def _continuous(capacity=8, act_dim=ACT_DIM):
    return ReplayBuffer(
        capacity, OBS_SHAPE, obs_dtype=np.float32,
        action_shape=(act_dim,), action_dtype=np.float32,
    )


def _fill(buf, count, continuous=False, n_actions=2):
    """Transitions whose fields are all derivable from the step index, so a
    sample that mixed indices ACROSS arrays is detectable."""
    for i in range(count):
        action = np.full(ACT_DIM, 0.5 + i, dtype=np.float32) if continuous else i % n_actions
        buf.add(
            np.full(OBS_SHAPE, i, dtype=np.float32),
            action,
            float(i),
            np.full(OBS_SHAPE, i + 1, dtype=np.float32),
            float(i % 2),
            0.99,
            None if continuous else np.array([True, i % 2 == 0]),
            None if continuous else np.array([i % 2 == 0, True]),
        )


def test_discrete_layout_matches_the_dqn_contract():
    buf = _discrete(capacity=8, n_actions=2)
    assert buf.actions.shape == (8,) and buf.actions.dtype == np.int64
    assert buf.obs.shape == (8, 4) and buf.next_obs.shape == (8, 4)
    assert buf.masks.shape == (8, 2) and buf.masks.dtype == bool
    assert buf.next_masks.shape == (8, 2)


def test_continuous_layout_stores_action_vectors_and_allocates_no_masks():
    """`masks is None` is how algorithm code learns the space is Box — fixed at
    construction, never a runtime branch (the repo's masking invariant)."""
    buf = _continuous(capacity=8, act_dim=3)
    assert buf.actions.shape == (8, 3) and buf.actions.dtype == np.float32
    assert buf.masks is None and buf.next_masks is None


def test_continuous_actions_survive_storage_without_truncation():
    """The silent bug this file exists for: with the Discrete int64 default, a
    stored action of 0.5 comes back as 0 and every critic input is wrong."""
    buf = _continuous(capacity=4)
    buf.add(
        np.zeros(OBS_SHAPE, np.float32), np.array([0.5, -0.25, 0.125], np.float32),
        1.0, np.ones(OBS_SHAPE, np.float32), 0.0, 0.99,
    )
    np.testing.assert_array_equal(buf.actions[0], [0.5, -0.25, 0.125])


def test_sample_draws_whole_transitions_not_independent_columns():
    """Every field is a function of the step index, so a sample() that indexed
    each array separately would break these identities while still returning
    correctly shaped arrays."""
    np.random.seed(0)
    buf = _continuous(capacity=16)
    _fill(buf, 16, continuous=True)
    obs, actions, rewards, next_obs, terminated, discounts, masks, next_masks = buf.sample(32)

    assert obs.shape == (32, 4) and actions.shape == (32, 3) and rewards.shape == (32,)
    assert masks is None and next_masks is None
    steps = obs[:, 0]
    np.testing.assert_allclose(rewards, steps)
    np.testing.assert_allclose(next_obs[:, 0], steps + 1)
    np.testing.assert_allclose(actions[:, 0], steps + 0.5)
    np.testing.assert_allclose(terminated, steps % 2)
    np.testing.assert_allclose(discounts, 0.99)


def test_discrete_sample_carries_both_mask_arrays_in_step():
    np.random.seed(0)
    buf = _discrete(capacity=16)
    _fill(buf, 16)
    obs, actions, _r, _n, _t, _d, masks, next_masks = buf.sample(32)
    steps = obs[:, 0].astype(int)
    np.testing.assert_array_equal(actions, steps % 2)
    # mask = [True, even], next_mask = [even, True] — distinct per parity, so a
    # swapped pair or a stale row fails.
    np.testing.assert_array_equal(masks[:, 1], steps % 2 == 0)
    np.testing.assert_array_equal(next_masks[:, 0], steps % 2 == 0)
    np.testing.assert_array_equal(masks[:, 0], True)
    np.testing.assert_array_equal(next_masks[:, 1], True)


def test_the_ring_overwrites_oldest_first_and_len_caps_at_capacity():
    buf = _continuous(capacity=3)
    _fill(buf, 2, continuous=True)
    assert len(buf) == 2
    _fill(buf, 5, continuous=True)  # 7 adds total into 3 slots
    assert len(buf) == 3
    # The first fill leaves ptr at 2, so the second fill's steps 0..4 land in
    # slots 2, 0, 1, 2, 0 — slot 0 keeps step 4, slot 1 step 2, slot 2 step 3.
    np.testing.assert_allclose(buf.obs[:, 0], [4.0, 2.0, 3.0])


def test_obs_dtype_is_the_agents_choice_not_the_buffers():
    """MinAtar bool planes stay 1 byte; SAC narrows MuJoCo float64 to float32.
    Same principle, opposite directions — both are the agent's call."""
    planes = ReplayBuffer(4, (2, 10, 10), obs_dtype=bool, n_actions=6)
    assert planes.obs.dtype == bool and planes.obs.nbytes == 4 * 200

    narrowed = ReplayBuffer(4, OBS_SHAPE, obs_dtype=np.float32, action_shape=(3,), action_dtype=np.float32)
    narrowed.add(
        np.array([1 / 3, 0.0, 0.0, 0.0], dtype=np.float64), np.zeros(3, np.float32),
        0.0, np.zeros(OBS_SHAPE, np.float64), 0.0, 0.99,
    )
    assert narrowed.obs.dtype == np.float32
    assert narrowed.obs[0, 0] == pytest.approx(1 / 3, rel=1e-7)

"""EpisodeDataset + per-episode GAE (THROUGHPUT_SPEC Stage 2 data path)."""

import numpy as np
import pytest

from rl.buffers.episode import EpisodeDataset, _episode_gae_reference, episode_gae
from rl.buffers.rollout import compute_gae


def _episode(length, action=0, outcome=1.0, opp_choice=False, version=0):
    ep = {
        "obs": np.full((length, 4), 0.5, dtype=np.float32),
        "masks": np.ones((length, 3), dtype=np.bool_),
        "actions": np.full(length, action, dtype=np.int64),
        "rewards": np.r_[np.zeros(length - 1), outcome].astype(np.float32),
        "old_logp": np.full(length, -1.1, dtype=np.float32),
        "version": np.full(length, version, dtype=np.int64),
    }
    if opp_choice:
        ep["opp_choice"] = np.tile(
            np.array([1, 33, 1], dtype=np.int32), (length, 1)
        )
    return ep


def test_dataset_accumulates_and_drains_flat():
    ds = EpisodeDataset()
    ds.append(_episode(3, action=1))
    ds.append(_episode(5, action=2, outcome=-1.0))
    assert ds.steps == 8 and len(ds) == 2
    batch = ds.drain()
    assert batch["obs"].shape == (8, 4)
    assert batch["lengths"].tolist() == [3, 5]
    assert batch["actions"].tolist() == [1] * 3 + [2] * 5
    # Terminal rewards land on each episode's last row, nowhere else.
    assert batch["rewards"].tolist() == [0, 0, 1, 0, 0, 0, 0, -1]
    # Drain resets: the next batch owes nothing to this one.
    assert ds.steps == 0 and len(ds) == 0
    with pytest.raises(AssertionError, match="empty"):
        ds.drain()


def test_dataset_opp_choice_is_all_or_none():
    ds = EpisodeDataset()
    ds.append(_episode(3, opp_choice=True))
    with pytest.raises(AssertionError, match="opp_choice"):
        ds.append(_episode(2, opp_choice=False))
    batch = ds.drain()
    assert batch["opp_choice"].shape == (3, 3)
    # And the reverse direction: none first, then one.
    ds.append(_episode(2, opp_choice=False))
    with pytest.raises(AssertionError, match="opp_choice"):
        ds.append(_episode(3, opp_choice=True))
    assert "opp_choice" not in ds.drain()


def test_dataset_rejects_wrong_dtype_and_ragged_rows():
    ds = EpisodeDataset()
    bad = _episode(3)
    bad["actions"] = bad["actions"].astype(np.int32)
    with pytest.raises(AssertionError, match="actions"):
        ds.append(bad)
    ragged = _episode(3)
    ragged["rewards"] = ragged["rewards"][:2]
    with pytest.raises(AssertionError, match="rewards"):
        ds.append(ragged)


def _reference_gae(rewards, values, gamma, lam):
    """One episode, the textbook backward recursion with terminal bootstrap 0."""
    adv = np.zeros_like(rewards)
    gae = 0.0
    for t in range(len(rewards) - 1, -1, -1):
        next_v = values[t + 1] if t + 1 < len(rewards) else 0.0
        delta = rewards[t] + gamma * next_v - values[t]
        gae = delta + gamma * lam * gae
        adv[t] = gae
    return adv


def test_episode_gae_matches_reference_per_episode():
    rng = np.random.default_rng(0)
    lengths = np.array([1, 4, 7, 2], dtype=np.int64)
    total = int(lengths.sum())
    rewards = rng.normal(size=total).astype(np.float32)
    values = rng.normal(size=total).astype(np.float32)
    got = episode_gae(rewards, values, lengths, gamma=1.0, lam=0.95)
    start = 0
    for length in lengths:
        end = start + length
        want = _reference_gae(rewards[start:end], values[start:end], 1.0, 0.95)
        np.testing.assert_allclose(got[start:end], want, rtol=1e-6)
        start = end


def test_episode_gae_never_chains_across_episodes():
    # Two episodes; the second's rewards/values must not leak into the
    # first's advantages. Compare against computing episode 1 alone.
    rewards = np.array([0, 0, 1, 0, -1], dtype=np.float32)
    values = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
    lengths = np.array([3, 2], dtype=np.int64)
    both = episode_gae(rewards, values, lengths, gamma=0.99, lam=0.9)
    alone = episode_gae(rewards[:3], values[:3], np.array([3]), gamma=0.99, lam=0.9)
    np.testing.assert_allclose(both[:3], alone)


def test_episode_gae_does_not_leak_a_nonfinite_value_across_a_boundary():
    # The ONE behavioural difference F-10's layout introduces (episode_gae's
    # docstring, last paragraph): a non-finite critic output no longer crosses
    # an episode boundary. The (B, 1) column form cut the chain by multiplying
    # the carry by (1 - done) = 0.0, and 0.0 * nan/inf = nan, so ONE bad row in
    # episode 2 poisoned every advantage in episode 1; a column per episode
    # cannot chain at all.
    #
    # _episode_gae_reference INTENTIONALLY differs here, so the pin is against
    # the single-episode call, never the reference — and it is why the
    # bit-identity test below must keep its cases finite. Do not "fix" this by
    # widening those cases.
    rewards = np.array([0, 0, 1, 0, -1], dtype=np.float32)
    lengths = np.array([3, 2], dtype=np.int64)
    one = np.array([3], dtype=np.int64)
    for bad in (np.nan, np.inf, -np.inf):
        values = np.array([0.1, 0.2, 0.3, bad, 0.5], dtype=np.float32)
        with np.errstate(invalid="ignore"):  # 0.0 * inf in the reference below
            got = episode_gae(rewards, values, lengths, gamma=1.0, lam=0.95)
            alone = episode_gae(rewards[:3], values[:3], one, gamma=1.0, lam=0.95)
            leaked = _episode_gae_reference(rewards, values, lengths, 1.0, 0.95)
        assert np.isfinite(got[:3]).all(), bad
        assert np.array_equal(got[:3], alone), bad
        assert not np.isfinite(leaked[:3]).any(), bad  # the form F-10 replaced


def test_episode_gae_agrees_with_vector_gae_on_aligned_columns():
    # The sync loop's compute_gae on a (T, N) rollout where every column is
    # one whole episode ending at T-1 is the same computation — the two
    # paths must agree exactly on their overlap.
    rng = np.random.default_rng(1)
    T, N = 6, 3
    rewards = rng.normal(size=(T, N)).astype(np.float32)
    values = rng.normal(size=(T, N)).astype(np.float32)
    terminated = np.zeros((T, N), dtype=np.float32)
    terminated[-1] = 1.0
    next_values = np.zeros_like(values)
    next_values[:-1] = values[1:]
    vector = compute_gae(
        rewards, terminated, np.zeros_like(rewards), values, next_values,
        gamma=1.0, lam=0.95,
    )
    flat = episode_gae(
        rewards.T.reshape(-1),
        values.T.reshape(-1),
        np.full(N, T, dtype=np.int64),
        gamma=1.0,
        lam=0.95,
    )
    np.testing.assert_allclose(flat.reshape(N, T).T, vector, rtol=1e-6)


def test_episode_gae_is_bit_identical_to_the_column_reduction():
    # F-10 pin: the vectorized (Lmax, E) layout against the original (B, 1)
    # column reduction, kept as _episode_gae_reference. EXACT equality, no
    # tolerance — both run the same compute_gae recurrence over the same
    # float32 operands in the same op order; only the vector width differs,
    # and IEEE add/sub/mul round identically at any width (each ufunc call
    # is one rounded op, so nothing is fused or reassociated). The bitwise
    # view makes even the sign of an exact-zero advantage part of the pin
    # (the terminal-row carry is killed by (1 - done) = 0.0 on both paths;
    # see the episode_gae docstring). Achieved: bit-identical on every case
    # below on numpy 2.5.1, so np.array_equal is the assertion, not allclose.
    rng = np.random.default_rng(2)
    cases = [
        np.array([1], dtype=np.int64),  # one episode, one row
        np.array([7], dtype=np.int64),  # a single episode
        np.ones(9, dtype=np.int64),  # every episode length 1 (Lmax = 1)
        np.array([1, 4, 1, 7, 2, 1, 30, 3], dtype=np.int64),
        rng.integers(1, 60, size=400, endpoint=True).astype(np.int64),  # many
    ]
    for lengths in cases:
        total = int(lengths.sum())
        ends = np.cumsum(lengths) - 1
        values = rng.normal(size=total).astype(np.float32)
        values[rng.random(total) < 0.1] = 0.0  # exact zeros occur; pin their sign
        # Two reward shapes: the data path's (0 everywhere, +-1 at the
        # terminal) and dense noise with a seeded share of exact zeros.
        outcome = np.zeros(total, dtype=np.float32)
        outcome[ends] = rng.choice([-1.0, 1.0], size=len(ends))
        dense = rng.normal(size=total).astype(np.float32)
        dense[rng.random(total) < 0.3] = 0.0
        for rewards in (outcome, dense):
            for gamma, lam in [(1.0, 0.95), (0.99, 0.9), (1.0, 1.0)]:
                got = episode_gae(rewards, values, lengths, gamma, lam)
                want = _episode_gae_reference(rewards, values, lengths, gamma, lam)
                assert got.dtype == np.float32 and got.shape == (total,)
                assert np.array_equal(got, want)
                assert np.array_equal(got.view(np.int32), want.view(np.int32))

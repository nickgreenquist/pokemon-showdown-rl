"""EpisodeDataset + per-episode GAE (THROUGHPUT_SPEC Stage 2 data path)."""

import numpy as np
import pytest

from rl.buffers.episode import EpisodeDataset, episode_gae
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

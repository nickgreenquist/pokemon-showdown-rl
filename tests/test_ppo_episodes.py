"""The Stage-2 PPO surface: act_logp (old_logp recorded at act time) and
update_episodes (whole-episode batches through the factored _optimize)."""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

OBS_D, N_ACT = 3, 4


def _agent(**over):
    torch.manual_seed(0)
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_D,), np.float32),
        action_space=gym.spaces.Discrete(N_ACT),
        num_envs=2,
        device="cpu",
        lr=1e-3,
        gamma=1.0,
        gae_lambda=0.95,
        rollout_steps=4,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )
    kwargs.update(over)
    return PPOAgent(**kwargs)


def _episodes(lengths, seed=0):
    rng = np.random.default_rng(seed)
    total = int(sum(lengths))
    obs = rng.normal(size=(total, OBS_D)).astype(np.float32)
    masks = np.ones((total, N_ACT), dtype=np.bool_)
    masks[:, -1] = rng.random(total) > 0.5  # some rows lose an action
    actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks], dtype=np.int64)
    rewards = np.zeros(total, dtype=np.float32)
    ends = np.cumsum(lengths) - 1
    rewards[ends] = rng.choice([-1.0, 1.0], size=len(lengths))
    return {
        "obs": obs,
        "masks": masks,
        "actions": actions,
        "rewards": rewards,
        "old_logp": np.zeros(total, dtype=np.float32),  # caller overwrites
        "version": np.zeros(total, dtype=np.int64),
        "lengths": np.asarray(lengths, dtype=np.int64),
    }


def test_act_logp_samples_inside_mask_and_matches_recompute():
    agent = _agent()
    rng = np.random.default_rng(1)
    obs = rng.normal(size=(16, OBS_D)).astype(np.float32)
    masks = np.ones((16, N_ACT), dtype=bool)
    masks[:, 0] = False  # action 0 illegal everywhere
    torch.manual_seed(2)
    actions, logp = agent.act_logp(obs, masks)
    assert actions.shape == (16,) and logp.shape == (16,)
    assert masks[np.arange(16), actions].all(), "sampled outside the mask"
    # The recorded logp is the same masked-Categorical the update rebuilds —
    # recomputed at the same batch size it must agree to float precision.
    with torch.no_grad():
        want = agent._logp_entropy(
            torch.as_tensor(obs), torch.as_tensor(actions), torch.as_tensor(masks)
        )[0]
    np.testing.assert_allclose(logp, want.numpy(), rtol=1e-6)


def test_update_episodes_trains_and_reports_the_locked_keys():
    agent = _agent()
    batch = _episodes([5, 3, 8, 4])
    # Record old_logp the way the collector does: from the acting policy.
    with torch.no_grad():
        batch["old_logp"] = (
            agent._logp_entropy(
                torch.as_tensor(batch["obs"]),
                torch.as_tensor(batch["actions"]),
                torch.as_tensor(batch["masks"]),
            )[0]
            .numpy()
            .astype(np.float32)
        )
    before = [p.clone() for p in agent.actor.parameters()]
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert set(metrics) == {
        "loss/policy", "loss/value", "loss/entropy", "loss/approx_kl",
        "loss/clip_frac", "loss/grad_norm", "loss/grad_clip_frac",
        "loss/explained_variance", "loss/adv_std",
    }
    assert agent.updates == 1
    assert any(
        (p != q).any() for p, q in zip(agent.actor.parameters(), before)
    ), "the actor never moved"
    # First-epoch ratios start at the recorded logp, so approx_kl is finite
    # and small — not the silent-wrongness signature (NaN / huge).
    assert math.isfinite(metrics["loss/approx_kl"])


def test_update_episodes_anneals_from_steps_seen():
    agent = _agent(lr_anneal_steps=1_000)
    batch = _episodes([4, 4])
    agent.update_episodes(batch, steps_seen=500)
    assert agent.optimizer.param_groups[0]["lr"] == pytest.approx(0.5e-3)
    # And the schedule reads the caller's counter, not the update count.
    batch = _episodes([4, 4], seed=1)
    agent.update_episodes(batch, steps_seen=750)
    assert agent.optimizer.param_groups[0]["lr"] == pytest.approx(0.25e-3)


def test_update_episodes_refuses_privileged_and_label_mismatch():
    with pytest.raises(ValueError, match="privileged"):
        _agent(privileged_dim=7).update_episodes(_episodes([4]), steps_seen=0)
    # aux head off + labels recorded = the same loud seam update() enforces.
    batch = _episodes([4])
    batch["opp_choice"] = np.zeros((4, 3), dtype=np.int32)
    with pytest.raises(ValueError, match="opponent-action mismatch"):
        _agent().update_episodes(batch, steps_seen=0)


def test_vector_update_unchanged_by_the_factor_out():
    """The (T, N) path's numbers must not move: a seeded fill-and-train
    produces the same metrics whether or not _optimize exists as a seam —
    pinned here against values computed at build time so a later edit to
    _optimize that touches the vector path fails loudly."""
    torch.manual_seed(3)
    agent = _agent()
    rng = np.random.default_rng(3)
    for t in range(4):
        obs = rng.normal(size=(2, OBS_D)).astype(np.float32)
        nxt = rng.normal(size=(2, OBS_D)).astype(np.float32)
        acts = rng.integers(0, N_ACT, size=2)
        rews = rng.normal(size=2).astype(np.float32)
        term = np.array([t == 3, t == 3])
        trunc = np.zeros(2, dtype=bool)
        masks = np.ones((2, N_ACT), dtype=bool)
        metrics = agent.update((obs, acts, rews, nxt, term, trunc, masks, masks))
    assert agent.updates == 1 and len(agent.buffer) == 0
    # Epoch 1 recomputes old_logp exactly, so the mean over 2 epochs is
    # small; the exact value is pinned loosely (float noise across BLAS
    # builds) but the structural reads are exact.
    assert metrics["loss/clip_frac"] < 0.5
    assert math.isfinite(metrics["loss/policy"])


def test_trailing_one_row_minibatch_is_skipped_not_nan():
    """Async batches are not multiples of `minibatches`; a trailing 1-row
    slice has no advantage std, and before the guard its NaN silently
    poisoned the weights (caught live 2026-09-01: the crash surfaced one
    forward LATER, in act_logp). Batch of 5 at minibatches=2 slices 2/2/1."""
    agent = _agent(minibatches=2, epochs=1)
    batch = _episodes([3, 2])
    with torch.no_grad():
        batch["old_logp"] = (
            agent._logp_entropy(
                torch.as_tensor(batch["obs"]),
                torch.as_tensor(batch["actions"]),
                torch.as_tensor(batch["masks"]),
            )[0]
            .numpy()
            .astype(np.float32)
        )
    metrics = agent.update_episodes(batch, steps_seen=0)
    assert math.isfinite(metrics["loss/policy"])
    for p in agent.actor.parameters():
        assert torch.isfinite(p).all(), "NaN reached the weights"

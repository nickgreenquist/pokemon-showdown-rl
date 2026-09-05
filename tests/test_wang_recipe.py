"""JOURNEY step 4's two learner knobs (Wang 2024, gen4randombattle; the
pre-reg configs/gen4_wang50m.yaml): the power-law LR schedule of thesis
§3.1.4 and SB3's `clip_range_vf` value clipping (Table A.3). Both default to
today's wire — the linear anneal and no clamp — so every existing config and
golden is untouched; the pins here are the closed forms, not a new golden."""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import LR_SCHEDULES, PPOAgent

OBS_D, N_ACT, N_ENVS, HORIZON = 3, 4, 2, 4


def _agent(**over):
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (OBS_D,), np.float32),
        action_space=gym.spaces.Discrete(N_ACT),
        num_envs=N_ENVS, device="cpu", lr=5.8884e-5, gamma=0.9999, gae_lambda=0.754,
        rollout_steps=HORIZON, epochs=2, minibatches=2, clip_eps=0.0829,
        entropy_coef=0.0588, value_coef=0.4375, max_grad_norm=0.543, hidden_sizes=[8],
    )
    kwargs.update(over)
    torch.manual_seed(0)
    return PPOAgent(**kwargs)


def _one_update(agent, seed):
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)  # the epoch permutations draw from the global stream
    metrics = {}
    for t in range(HORIZON):
        obs = rng.normal(size=(N_ENVS, OBS_D)).astype(np.float32)
        nxt = rng.normal(size=(N_ENVS, OBS_D)).astype(np.float32)
        acts = rng.integers(0, N_ACT, size=N_ENVS)
        rews = rng.normal(size=N_ENVS).astype(np.float32)
        term = np.array([t == HORIZON - 1] * N_ENVS)
        trunc = np.zeros(N_ENVS, dtype=bool)
        masks = np.ones((N_ENVS, N_ACT), dtype=bool)
        metrics = agent.update((obs, acts, rews, nxt, term, trunc, masks, masks))
    assert metrics, "the horizon must fill exactly once per call"
    return metrics


def test_power_schedule_is_wangs_closed_form_at_every_update():
    """lr(x) = lr0 / (8x + 1)^1.5, x = steps_seen / lr_anneal_steps, evaluated
    at the START of each update (steps_seen = updates_done * horizon * N, the
    same basis the linear anneal uses) and held at x = 1 past the horizon."""
    lr0, anneal = 5.8884e-5, 64  # 8 updates to the horizon at 8 steps/update
    agent = _agent(lr=lr0, lr_anneal_steps=anneal, lr_schedule="power")
    for k in range(12):
        _one_update(agent, seed=k)
        x = min(1.0, (k * HORIZON * N_ENVS) / anneal)
        want = lr0 / (8.0 * x + 1.0) ** 1.5
        for group in agent.optimizer.param_groups:
            assert math.isclose(group["lr"], want, rel_tol=1e-12), (k, group["lr"], want)
    # The floor: 27x below lr0 at x = 1, exactly (8 + 1)^1.5 = 27.
    assert math.isclose(agent.optimizer.param_groups[0]["lr"], lr0 / 27.0, rel_tol=1e-12)


def test_power_schedule_starts_at_lr0_and_linear_is_the_default():
    agent = _agent(lr_anneal_steps=1000, lr_schedule="power")
    _one_update(agent, seed=0)  # first update: x = 0 -> lr0 exactly
    assert agent.optimizer.param_groups[1]["lr"] == 5.8884e-5
    default = _agent(lr_anneal_steps=64)
    assert default.lr_schedule == "linear"
    _one_update(default, seed=0)
    _one_update(default, seed=1)  # second update: 1 - 8/64
    assert math.isclose(default.optimizer.param_groups[1]["lr"], 5.8884e-5 * (1 - 8 / 64), rel_tol=1e-12)


def test_schedule_guards():
    assert LR_SCHEDULES == ("linear", "power")
    with pytest.raises(ValueError, match="unknown lr_schedule"):
        _agent(lr_schedule="cosine")
    with pytest.raises(ValueError, match="lr_anneal_steps > 0"):
        _agent(lr_schedule="power")  # no horizon, no progress
    with pytest.raises(ValueError, match="value_clip_eps"):
        _agent(value_clip_eps=-0.1)


def _flat_batch(agent, rows, seed):
    rng = np.random.default_rng(seed)
    obs = torch.as_tensor(rng.normal(size=(rows, OBS_D)).astype(np.float32))
    actions = torch.as_tensor(rng.integers(0, N_ACT, size=rows))
    masks = torch.ones((rows, N_ACT), dtype=torch.bool)
    with torch.no_grad():
        old_logp = agent._logp_entropy(obs, actions, masks)[0]
        values = agent.critic(obs).squeeze(-1)
    adv = torch.as_tensor(rng.normal(size=rows).astype(np.float32))
    return obs, actions, masks, adv, adv + values, old_logp, values


def test_value_clip_saturated_freezes_the_critic_exactly():
    """SB3's form: v_pred = old_v + clamp(v - old_v, ±eps). Handed old values
    a full unit away from the critic's own predictions, the clamp saturates on
    every row, its gradient is exactly zero, and Adam (zero first and second
    moments) leaves every critic parameter bit-for-bit where it was — while
    the actor still trains off the same batch."""
    agent = _agent(value_clip_eps=1e-3)
    obs, actions, masks, adv, targets, old_logp, values = _flat_batch(agent, 8, seed=5)
    critic_before = [p.detach().clone() for p in agent.critic.parameters()]
    actor_before = [p.detach().clone() for p in agent.actor.parameters()]
    agent._optimize(obs, actions, masks, obs, adv, targets, old_logp, steps_seen=0,
                    flat_old_values=values + 1.0)
    for before, after in zip(critic_before, agent.critic.parameters()):
        assert torch.equal(before, after)
    assert any(not torch.equal(b, a) for b, a in zip(actor_before, agent.actor.parameters()))
    with pytest.raises(ValueError, match="flat_old_values"):
        agent._optimize(obs, actions, masks, obs, adv, targets, old_logp, steps_seen=0)


def test_value_clip_wide_matches_the_unclipped_loss():
    """An eps wider than any prediction move reproduces the unclipped path
    to float rounding (old_v + (v - old_v) is v up to one ulp)."""
    a = _agent(value_clip_eps=0.0)
    b = _agent(value_clip_eps=1e6)
    ma, mb = _one_update(a, seed=7), _one_update(b, seed=7)
    for key in ("loss/value", "loss/policy", "loss/entropy"):
        assert math.isclose(ma[key], mb[key], rel_tol=1e-5, abs_tol=1e-7), (key, ma[key], mb[key])
    for pa, pb in zip(a.critic.parameters(), b.critic.parameters()):
        assert torch.allclose(pa, pb, atol=1e-6)


def test_value_clip_is_applied_on_the_episode_path_too():
    """Epoch 1's deltas are exactly zero (same weights, same rows), so a
    tiny eps bites from epoch 2 on: the clipped run's value loss and critic
    differ from the unclipped run's at the same seed, and nothing raises."""
    rng = np.random.default_rng(1)
    lengths = [5, 3]
    total = sum(lengths)
    masks = np.ones((total, N_ACT), dtype=np.bool_)
    batch = {
        "obs": rng.normal(size=(total, OBS_D)).astype(np.float32),
        "masks": masks,
        "actions": rng.integers(0, N_ACT, size=total).astype(np.int64),
        "rewards": np.zeros(total, dtype=np.float32),
        "old_logp": np.full(total, -math.log(N_ACT), dtype=np.float32),
        "version": np.zeros(total, dtype=np.int64),
        "lengths": np.array(lengths, dtype=np.int64),
    }
    batch["rewards"][[4, 7]] = [1.0, -1.0]
    clipped, plain = _agent(value_clip_eps=1e-9), _agent(value_clip_eps=0.0)
    torch.manual_seed(2)
    mc = clipped.update_episodes(batch, steps_seen=0)
    torch.manual_seed(2)
    mp = plain.update_episodes(batch, steps_seen=0)
    assert mc["loss/value"] != mp["loss/value"]
    assert any(not torch.equal(a, b) for a, b in zip(clipped.critic.parameters(), plain.critic.parameters()))

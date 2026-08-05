"""Continuous-track PPO: the Gaussian policy's log-prob/entropy reduction,
act()'s shape and dtype contracts, and the update path through a Box action
space.

Every case here uses act_dim >= 2 on purpose. A length-1 action vector is
shape-degenerate: a (B,) actions tensor broadcasts against a (B, 1) mean into
a (B, B) log-prob matrix whose .sum(-1) is correctly shaped and completely
wrong, so a one-dimensional action space silently validates broken code. That
is exactly the bug this suite exists to prevent, and Pendulum — the sanity-gate
env — has act_dim 1.
"""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

OBS_DIM = 4


def _agent(act_dim=3, num_envs=2, rollout_steps=4, obs_dim=OBS_DIM):
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(-np.inf, np.inf, (obs_dim,), np.float32),
        action_space=gym.spaces.Box(-1.0, 1.0, (act_dim,), np.float32),
        num_envs=num_envs,
        device="cpu",
        lr=3.0e-4,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=rollout_steps,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.0,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )


def _zero_the_mean(agent):
    """Pin the policy mean at 0 so log-probs reduce to hand-computable
    constants (the mean net is just an mlp(), already covered elsewhere)."""
    head = [m for m in agent.actor.mean.modules() if isinstance(m, torch.nn.Linear)][-1]
    with torch.no_grad():
        head.weight.zero_()
        head.bias.zero_()


def test_gaussian_logp_and_entropy_are_hand_computed_sums_over_dims():
    """Diagonal Gaussian with mean 0 and std 1 (log_std init):
        log p(a) = sum_i(-a_i^2 / 2) - act_dim * log(2*pi) / 2
        H        = act_dim * log(2*pi*e) / 2
    both reduced over action dimensions to one scalar per transition."""
    agent = _agent(act_dim=3)
    _zero_the_mean(agent)
    actions = torch.tensor([[0.5, -1.0, 0.25]])
    logp, entropy = agent._logp_entropy(torch.zeros(1, OBS_DIM), actions, None)

    assert logp.shape == (1,) and entropy.shape == (1,)  # never (B, act_dim), never (B, B)
    assert logp.item() == pytest.approx(-0.65625 - 1.5 * math.log(2 * math.pi))
    assert entropy.item() == pytest.approx(1.5 * (math.log(2 * math.pi) + 1.0))


def test_logp_entropy_shapes_are_per_transition_not_a_matrix():
    """The broadcast trap, stated as a contract: a batch of B transitions
    yields exactly B log-probs, whatever act_dim is."""
    for act_dim in (1, 3):
        agent = _agent(act_dim=act_dim)
        obs, actions = torch.zeros(5, OBS_DIM), torch.zeros(5, act_dim)
        logp, entropy = agent._logp_entropy(obs, actions, None)
        assert logp.shape == (5,) and entropy.shape == (5,)


def test_flattened_actions_are_silently_wrong_at_act_dim_one_and_loud_above():
    """Why every test above uses act_dim >= 2.

    Handing Normal a 1-D actions tensor (what reshape(-1) produces) is a bug
    either way, but it only ANNOUNCES itself when act_dim > 1. At act_dim 1
    the (B,) actions broadcast against the (B, 1) mean into a (B, B) matrix,
    and .sum(-1) hands back a perfectly shaped (B,) tensor of nonsense — the
    ratios stay self-consistent, the run trains, and nothing fails until a
    real MuJoCo action space arrives."""
    silent = _agent(act_dim=1)
    obs = torch.zeros(5, OBS_DIM)
    wrong = torch.distributions.Normal(*silent.actor(obs)).log_prob(torch.zeros(5, 1).reshape(-1))
    assert wrong.shape == (5, 5)  # a matrix, not a per-transition vector
    assert wrong.sum(-1).shape == (5,)  # ...which the reduction disguises

    loud = _agent(act_dim=3)
    with pytest.raises(ValueError, match="not broadcastable"):
        torch.distributions.Normal(*loud.actor(obs)).log_prob(torch.zeros(5, 3).reshape(-1))


def test_buffer_actions_flatten_to_batch_by_act_dim():
    """The fix for the trap above: (T, N, act_dim) must flatten on the leading
    two axes only. reshape(-1) is what produces the 1-D tensor."""
    agent = _agent(act_dim=3, num_envs=2, rollout_steps=4)
    actions = torch.as_tensor(agent.buffer.actions)
    assert actions.flatten(0, 1).shape == (8, 3)
    assert actions.reshape(-1).shape == (24,)  # the bug, pinned so it stays visible


def test_act_returns_float32_of_the_right_shape_on_both_paths():
    """Single (eval/watch/record) vs batched (collection). The vector env does
    not validate action dtype, so the assertion has to live here."""
    agent = _agent(act_dim=3, num_envs=2)
    single = agent.act(np.zeros(OBS_DIM, dtype=np.float32))
    batched = agent.act(np.zeros((2, OBS_DIM), dtype=np.float32))
    assert single.shape == (3,) and single.dtype == np.float32
    assert batched.shape == (2, 3) and batched.dtype == np.float32


def test_deterministic_act_is_the_distribution_mean():
    agent = _agent(act_dim=3)
    obs = np.arange(OBS_DIM, dtype=np.float32)
    with torch.no_grad():
        mean, _ = agent.actor(torch.as_tensor(obs).unsqueeze(0))
    np.testing.assert_allclose(
        agent.act(obs, deterministic=True), mean.numpy()[0], rtol=1e-6
    )


def test_act_is_unbounded_and_stochastic_off_the_deterministic_path():
    """Sampling must actually vary (exploration rides on the scale, since the
    continuous configs run entropy_coef 0), and nothing here clips to the
    action space — ClipAction does that at the env, while the raw sample is
    what gets stored and log-prob'd."""
    agent = _agent(act_dim=3)
    with torch.no_grad():  # a wide scale makes out-of-bounds samples certain
        agent.actor.log_std.fill_(math.log(5.0))
    draws = np.stack([agent.act(np.zeros(OBS_DIM, dtype=np.float32)) for _ in range(20)])
    assert draws.std() > 0.0
    assert np.abs(draws).max() > 1.0  # beyond the Box's [-1, 1] bounds


def test_log_std_is_a_trained_parameter_in_the_optimizer():
    """A free log_std that never receives gradients would leave the policy
    stuck at its initial scale forever — a silent failure to learn how much
    to explore."""
    agent = _agent(act_dim=3)
    assert any(p is agent.actor.log_std for p in agent.params)
    before = agent.actor.log_std.detach().clone()
    for t in range(agent.buffer.horizon):
        metrics = agent.update(_row(t, act_dim=3))
    assert agent.actor.log_std.grad is not None
    assert not torch.equal(agent.actor.log_std, before)
    assert metrics["loss/policy_std"] == pytest.approx(
        float(agent.actor.log_std.detach().exp().mean()), rel=0.05
    )


def _row(t, act_dim=3, num_envs=2, terminated=False):
    """One batched transition row as the vector loop hands it over on a Box
    env: no masks on either side."""
    obs = np.full((num_envs, OBS_DIM), 0.1 * t, dtype=np.float32)
    next_obs = np.full((num_envs, OBS_DIM), 0.1 * (t + 1), dtype=np.float32)
    actions = np.full((num_envs, act_dim), 0.2, dtype=np.float32)
    rewards = np.ones(num_envs, dtype=np.float32)
    return (
        obs, actions, rewards, next_obs,
        np.full(num_envs, terminated), np.zeros(num_envs, dtype=bool),
        None, None,
    )


def test_update_cadence_and_metrics_on_a_box_space():
    agent = _agent(act_dim=3, rollout_steps=4)
    assert agent.buffer.masks is None  # no legality concept on this track
    for t in range(3):
        assert agent.update(_row(t)) == {}
    metrics = agent.update(_row(3, terminated=True))
    assert set(metrics) == {
        "loss/policy", "loss/value", "loss/entropy",
        "loss/approx_kl", "loss/clip_frac", "loss/policy_std",
    }
    assert all(np.isfinite(v) for v in metrics.values())
    assert agent.updates == 1 and len(agent.buffer) == 0
    # Fresh policy, unchanged since collection: the first epoch's ratios are 1,
    # so no transition can be outside the clip range on the very first update.
    assert metrics["loss/clip_frac"] < 1.0
    # log_std starts at 0, so the initial scale is exactly 1.
    assert metrics["loss/policy_std"] == pytest.approx(1.0, rel=0.05)


def test_box_action_space_rejects_non_flat_shapes():
    with pytest.raises(TypeError, match="flat Box action space"):
        PPOAgent(
            observation_space=gym.spaces.Box(-1, 1, (OBS_DIM,), np.float32),
            action_space=gym.spaces.Box(-1, 1, (2, 2), np.float32),
            num_envs=1, device="cpu", lr=3e-4, gamma=0.99, gae_lambda=0.95,
            rollout_steps=2, epochs=1, minibatches=1, clip_eps=0.2,
            entropy_coef=0.0, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[8],
        )

"""PPO-specific tests: hand-computed clipped-surrogate cases through the
factored loss function (a regression points at the code, not at a second
implementation of the same formula), the fill-then-train update cadence,
the lr-anneal schedule's endpoints, act()'s rank handling on conv-shaped
observations, and a train-loop smoke through the real vector path.
"""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent, clipped_surrogate_loss
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.train import train

CLIP = 0.2


def surrogate(ratio, advantage):
    """One-transition call with old_logp = 0 and new_logp = log(ratio), so
    the ratio inside the loss is exactly `ratio`."""
    loss, kl, frac = clipped_surrogate_loss(
        new_logp=torch.tensor([math.log(ratio)]),
        old_logp=torch.zeros(1),
        advantages=torch.tensor([advantage]),
        clip_eps=CLIP,
    )
    return loss.item(), kl.item(), frac.item()


def test_positive_advantage_clips_at_upper_bound():
    # ratio 2, A +1: unclipped 2.0, clipped 1.2 -> min is the clipped side.
    # The incentive to push the ratio past 1 + eps is capped at 1.2.
    loss, _, frac = surrogate(2.0, 1.0)
    assert loss == pytest.approx(-1.2)
    assert frac == 1.0


def test_negative_advantage_clips_at_lower_bound():
    # ratio 0.5, A -1: unclipped -0.5, clipped 0.8 * -1 = -0.8 -> min -0.8.
    # Shrinking a bad action's probability stops earning credit below 1 - eps.
    loss, _, frac = surrogate(0.5, -1.0)
    assert loss == pytest.approx(0.8)
    assert frac == 1.0


def test_pessimistic_min_keeps_the_worse_side():
    # Ratios drifted the way that HURTS the objective: clipping alone would
    # soften the penalty; the min keeps the unclipped (worse) value, so the
    # gradient that corrects the overshoot survives.
    # ratio 2, A -1: min(-2.0, -1.2) = -2.0 (not the clipped -1.2).
    loss, _, _ = surrogate(2.0, -1.0)
    assert loss == pytest.approx(2.0)
    # ratio 0.5, A +1: min(0.5, 0.8) = 0.5 (not the clipped 0.8).
    loss, _, _ = surrogate(0.5, 1.0)
    assert loss == pytest.approx(-0.5)


def test_in_range_ratio_passes_through_unclipped():
    # ratio 1.1 lies inside [0.8, 1.2]: both min arguments equal 1.1 * 2.0.
    loss, _, frac = surrogate(1.1, 2.0)
    assert loss == pytest.approx(-2.2)
    assert frac == 0.0


def test_approx_kl_estimator():
    # (ratio - 1) - log ratio: 0 at ratio 1, positive on both sides.
    assert surrogate(1.0, 1.0)[1] == pytest.approx(0.0)
    assert surrogate(2.0, 1.0)[1] == pytest.approx(1.0 - math.log(2.0))
    assert surrogate(0.5, 1.0)[1] == pytest.approx(-0.5 - math.log(0.5))


def test_loss_is_mean_over_transitions():
    # Elements from the two clip cases above: min terms 1.2 and -0.8, so
    # loss = -(1.2 + (-0.8)) / 2 = -0.2.
    loss, _, frac = clipped_surrogate_loss(
        new_logp=torch.tensor([math.log(2.0), math.log(0.5)]),
        old_logp=torch.zeros(2),
        advantages=torch.tensor([1.0, -1.0]),
        clip_eps=CLIP,
    )
    assert loss.item() == pytest.approx(-0.2)
    assert frac.item() == 1.0


def _agent(rollout_steps=4, num_envs=2):
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=num_envs,
        device="cpu",
        lr=1.0e-3,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=rollout_steps,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )


def _anneal_agent():
    """The MinAtar configs' schedule arithmetic exactly: 128-step rollouts
    across 8 envs (1024 transitions per update), annealed over 5M env steps
    from lr 2.5e-4. Epoch/minibatch counts are shrunk — the schedule is what's
    under test, not the optimization."""
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=8,
        device="cpu",
        lr=2.5e-4,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=128,
        epochs=1,
        minibatches=1,
        clip_eps=0.1,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
        lr_anneal_steps=5_000_000,
    )


def _conv_agent(num_envs=2, rollout_steps=4):
    """MinAtar-shaped: rank-3 bool planes select ConvQNet for both heads."""
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(0, 1, (4, 10, 10), np.bool_),
        action_space=gym.spaces.Discrete(6),
        num_envs=num_envs,
        device="cpu",
        lr=2.5e-4,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=rollout_steps,
        epochs=2,
        minibatches=2,
        clip_eps=0.1,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[32],
    )


def _lr_after_fill(agent, updates):
    """Drive one full rollout fill with the update counter pinned, and read
    back the lr the epoch loop just ran under."""
    agent.updates = updates
    for t in range(agent.buffer.horizon):
        agent.update(_row(t, num_envs=agent.buffer.num_envs))
    return agent.optimizer.param_groups[0]["lr"]


def _row(t, num_envs=2, terminated=False):
    """One batched transition row as the vector loop hands it over."""
    obs = np.full((num_envs, 3), 0.1 * t, dtype=np.float32)
    next_obs = np.full((num_envs, 3), 0.1 * (t + 1), dtype=np.float32)
    actions = np.arange(num_envs) % 2
    rewards = np.ones(num_envs, dtype=np.float32)
    term = np.full(num_envs, terminated)
    trunc = np.zeros(num_envs, dtype=bool)
    masks = np.ones((num_envs, 2), dtype=bool)
    return (obs, actions, rewards, next_obs, term, trunc, masks, masks)


def test_update_cadence_fill_train_clear():
    agent = _agent(rollout_steps=4)
    for t in range(3):
        assert agent.update(_row(t)) == {}  # filling: no training yet
    metrics = agent.update(_row(3, terminated=True))  # the fill triggers training
    assert set(metrics) == {
        "loss/policy", "loss/value", "loss/entropy", "loss/approx_kl", "loss/clip_frac",
    }
    assert agent.updates == 1
    assert len(agent.buffer) == 0  # cleared: on-policy data dies after one cycle
    assert agent.update(_row(4)) == {}  # the next row starts a fresh rollout
    # The 0.01-gain policy head starts near-uniform: entropy ~ ln 2.
    assert math.log(2.0) - 0.01 < metrics["loss/entropy"] <= math.log(2.0) + 1e-6


def test_lr_anneal_endpoints():
    """lr_t = base_lr * max(0, 1 - steps_seen / lr_anneal_steps), with
    steps_seen = updates * 1024. 5M / 1024 = 4,882 full updates, so the last
    one runs at updates == 4881 — and must still get a positive lr, or the
    campaign's final update is wasted."""
    agent = _anneal_agent()
    assert _lr_after_fill(agent, 0) == pytest.approx(2.5e-4)  # first update: full lr
    # 2441 * 1024 = 2,499,584 steps seen -> frac 0.5000832
    assert _lr_after_fill(agent, 2441) == pytest.approx(1.250208e-4)
    # 4881 * 1024 = 4,998,144 -> frac 1856 / 5e6 = 3.712e-4
    last = _lr_after_fill(agent, 4881)
    assert last == pytest.approx(9.28e-8)
    assert last > 0


def test_lr_anneal_off_by_default_and_clamped_at_zero():
    # Default 0 = off: the CartPole config's constant lr survives the fill.
    agent = _agent(rollout_steps=4)
    for t in range(4):
        agent.update(_row(t))
    assert agent.optimizer.param_groups[0]["lr"] == pytest.approx(1.0e-3)
    # Past the schedule's end the linear term goes negative; max(0, ·) pins it.
    assert _lr_after_fill(_anneal_agent(), 6000) == 0.0


def test_act_batches_a_single_rank3_obs_for_the_conv():
    """The eval/watch/record path hands one (C, 10, 10) obs with no batch
    dim. Conv2d requires one — without the unsqueeze, Flatten eats the
    channel dim and the FC layer raises a mat1/mat2 shape error, which is
    what would have killed the first eval at 100k steps. Both policy modes
    go through it, and the (A,) mask broadcasts over the (1, A) logits."""
    agent = _conv_agent()
    obs = np.zeros((4, 10, 10), dtype=bool)
    only_three = np.zeros(6, dtype=bool)
    only_three[3] = True
    for deterministic in (True, False):
        action = agent.act(obs, np.ones(6, dtype=bool), deterministic=deterministic)
        assert isinstance(action, int) and 0 <= action < 6
        assert agent.act(obs, only_three, deterministic=deterministic) == 3


def test_act_batched_rank4_obs_returns_one_action_per_env():
    agent = _conv_agent(num_envs=3)
    actions = agent.act(np.zeros((3, 4, 10, 10), dtype=bool), np.ones((3, 6), dtype=bool))
    assert isinstance(actions, np.ndarray) and actions.shape == (3,)
    assert ((0 <= actions) & (actions < 6)).all()


def test_kernel_size_knob_matches_the_preregistered_param_counts():
    """Phase 4's receptive-field fork (PLAN.md): a Connect 4 win is a line of
    FOUR, so kernel_size 4 lets one conv unit see a whole line where the
    inherited 3x3 sees at most three of it. The knob defaults to 3 — every
    existing config and checkpoint is untouched — and the counts pin PLAN's
    measured numbers, so the probe arm is a config key rather than a code
    edit at pathfinder time."""

    def c4_agent(**kwargs):
        torch.manual_seed(0)
        return PPOAgent(
            observation_space=gym.spaces.Box(0, 1, (2, 6, 7), np.bool_),
            action_space=gym.spaces.Discrete(7),
            num_envs=2,
            device="cpu",
            lr=2.5e-4,
            gamma=1.0,
            gae_lambda=0.95,
            rollout_steps=4,
            epochs=1,
            minibatches=2,
            clip_eps=0.2,
            entropy_coef=0.01,
            value_coef=0.5,
            max_grad_norm=0.5,
            hidden_sizes=[128],
            **kwargs,
        )

    assert sum(p.numel() for p in c4_agent().params) == 83_816
    assert sum(p.numel() for p in c4_agent(kernel_size=3).params) == 83_816
    probe = c4_agent(kernel_size=4)
    assert sum(p.numel() for p in probe.actor.parameters()) == 26_135
    # The 4x4 forward really runs on the 6x7 board (3x4 conv output).
    action = probe.act(np.zeros((2, 6, 7), dtype=bool), np.ones(7, dtype=bool))
    assert isinstance(action, int) and 0 <= action < 7


def test_cartpole_ppo_smoke(tmp_path, monkeypatch):
    """PPO through the real vector train loop: rollouts fill on schedule,
    the epoch loop runs, eval and checkpointing on the unchanged scalar
    protocol."""
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=600,
        eval_every=300,
        eval_episodes=2,
        run_name="test_cartpole_ppo",
        logger="tensorboard",
        num_envs=2,
        agent={
            "algo": "ppo",
            "hidden_sizes": [16],
            "lr": 2.5e-4,
            "gamma": 0.99,
            "gae_lambda": 0.95,
            "rollout_steps": 64,
            "epochs": 2,
            "minibatches": 2,
            "clip_eps": 0.2,
            "entropy_coef": 0.01,
            "value_coef": 0.5,
            "max_grad_norm": 0.5,
        },
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_cartpole_ppo" / "checkpoint.pt")
    assert ckpt["step"] == 600
    # 600 steps / 2 envs = 300 rows; the 64-row (128-transition) rollout
    # fills exactly 4 times.
    assert ckpt["agent"]["updates"] == 4
    assert (tmp_path / "runs" / "test_cartpole_ppo" / "best_checkpoint.pt").exists()

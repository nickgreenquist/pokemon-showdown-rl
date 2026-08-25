"""PPO-specific tests: hand-computed clipped-surrogate cases through the
factored loss function (a regression points at the code, not at a second
implementation of the same formula), the fill-then-train update cadence,
the lr-anneal schedule's endpoints, the batch-level mechanism diagnostics
(explained variance, advantage scale, whether the grad clip binds), act()'s
rank handling on conv-shaped observations, and a train-loop smoke through the
real vector path.
"""

import math

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent, clipped_surrogate_loss
from rl.buffers.rollout import compute_gae
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


def _agent(rollout_steps=4, num_envs=2, **overrides):
    torch.manual_seed(0)
    return PPOAgent(
        **overrides,
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
        "loss/grad_norm", "loss/grad_clip_frac", "loss/explained_variance", "loss/adv_std",
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
    """Phase 4's receptive-field fork (SESSION_LOGS_PREDECESSOR.md): a Connect 4 win is a line of
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


def _batch_before_training(rows):
    """The advantages and value targets the LAST row's update() is about to
    compute, re-derived on a twin agent from the public helpers.

    `_agent` is seeded, and the fills that only accumulate consume no RNG, so
    the twin's critic is bit-identical to the one the real update reads."""
    twin = _agent(rollout_steps=len(rows))
    for row in rows:
        twin.buffer.add(*row[:-1])  # add() takes everything but next_masks
    buf = twin.buffer
    flat_obs = torch.as_tensor(buf.obs, dtype=torch.float32).flatten(0, 1)
    flat_next_obs = torch.as_tensor(buf.next_obs, dtype=torch.float32).flatten(0, 1)
    with torch.no_grad():
        values = twin.critic(flat_obs).squeeze(-1).view(buf.horizon, buf.num_envs).numpy()
        next_values = (
            twin.critic(flat_next_obs).squeeze(-1).view(buf.horizon, buf.num_envs).numpy()
        )
    advantages = compute_gae(
        buf.rewards, buf.terminated, buf.truncated, values, next_values,
        twin.gamma, twin.gae_lambda,
    )
    return advantages.reshape(-1), (advantages + values).reshape(-1)


def test_explained_variance_and_adv_std_match_a_hand_computation():
    """The two batch-level mechanism reads (DESIGN.md §5). Explained variance
    is 1 - Var(target - V) / Var(target) over the WHOLE rollout, from the
    critic as it stood before this update's epochs — recomputed here from
    compute_gae rather than from the agent's internals."""
    agent = _agent(rollout_steps=4)
    rows = [_row(t) for t in range(3)] + [_row(3, terminated=True)]
    for row in rows[:-1]:
        agent.update(row)
    metrics = agent.update(rows[-1])

    advantages, targets = _batch_before_training(rows)
    expected_ev = 1.0 - advantages.var() / targets.var()
    assert metrics["loss/explained_variance"] == pytest.approx(expected_ev, abs=1e-6)
    assert metrics["loss/adv_std"] == pytest.approx(advantages.std(), abs=1e-6)
    # Population, not sample, variance — the batch IS the population. The two
    # differ by n/(n-1), which at this batch size is a 14% gap, so a silent
    # switch to the unbiased spelling would be caught here.
    assert advantages.std(ddof=1) != pytest.approx(advantages.std(), abs=1e-6)


def test_explained_variance_is_zero_on_a_degenerate_batch():
    """Constant targets leave the ratio 0/0. Report 0.0 ("explains nothing"),
    never a NaN — a NaN would propagate through the logger's history and every
    downstream mean, and the metric is a diagnostic, not a loss.

    gamma = lambda = 0 collapses GAE to r - V(s), so identical rows give an
    identical advantage on every transition and a target of exactly r: zero
    variance, by construction rather than by luck."""
    torch.manual_seed(0)
    agent = PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=2, device="cpu", lr=1.0e-3, gamma=0.0, gae_lambda=0.0,
        rollout_steps=4, epochs=1, minibatches=1, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[8],
    )
    for _ in range(3):
        agent.update(_row(0))
    metrics = agent.update(_row(0))
    assert metrics["loss/adv_std"] == pytest.approx(0.0, abs=1e-7)
    assert metrics["loss/explained_variance"] == 0.0
    assert not math.isnan(metrics["loss/explained_variance"])


def test_grad_clip_frac_reports_whether_the_clip_binds():
    """The production read the 2026-08-05 audit could not get: `loss/grad_norm`
    is the PRE-clip total norm and `loss/grad_clip_frac` the share of
    minibatches it exceeds max_grad_norm on. A permanently-binding clip is a
    silent lr divisor, which is a different failure from a rare spike."""
    always = _agent(rollout_steps=4)
    always.max_grad_norm = 1e-9  # every minibatch must clip
    for t in range(3):
        always.update(_row(t))
    metrics = always.update(_row(3, terminated=True))
    assert metrics["loss/grad_clip_frac"] == 1.0
    assert metrics["loss/grad_norm"] > 1e-9  # the norm is reported BEFORE the clip

    never = _agent(rollout_steps=4)
    never.max_grad_norm = 1e9
    for t in range(3):
        never.update(_row(t))
    metrics = never.update(_row(3, terminated=True))
    assert metrics["loss/grad_clip_frac"] == 0.0
    assert metrics["loss/grad_norm"] > 0.0


def _fill(agent, base=0):
    """Drive exactly one rollout fill and return the update's metric report."""
    report = {}
    for t in range(agent.buffer.horizon):
        report = agent.update(_row(base + t, num_envs=agent.buffer.num_envs))
    return report


def test_param_group_split_is_a_no_op_at_the_default_scale():
    """The actor/critic param-group split exists so actor_lr_scale has
    somewhere to live. At scale 1.0 both groups carry identical
    hyperparameters, so every pre-existing recipe must train BIT-FOR-BIT as
    it did under the single group this replaced — the PPO audit's standard."""
    def run(single_group: bool):
        agent = _agent(rollout_steps=4)  # seeded init, identical either way
        if single_group:  # the pre-split optimizer, verbatim
            agent.optimizer = torch.optim.Adam(agent.params, lr=agent.base_lr, eps=1e-5)
        torch.manual_seed(1)  # the epoch loop's randperm stream
        for _ in range(3):
            _fill(agent)
        return [p.detach().clone() for p in agent.params]

    for split, unsplit in zip(run(False), run(True)):
        assert torch.equal(split, unsplit)


def test_load_state_dict_accepts_a_pre_split_single_group_checkpoint():
    """Every stored P4/P5/P6 final was written before the param-group split
    and carries ONE group; torch refuses a state dict whose group count
    differs. The graft keeps our groups and restores only the moments, whose
    keys are positional indices over the params flattened in group order —
    actor then critic, unchanged by the split, which is what makes the
    remap exact rather than approximate."""
    donor = _agent()
    for _ in range(2):
        _fill(donor)  # real Adam moments to restore
    state = donor.state_dict()
    groups = state["optimizer"]["param_groups"]
    assert len(groups) == 2
    legacy = dict(groups[0]) | {"params": [i for g in groups for i in g["params"]]}
    state["optimizer"] = {"state": state["optimizer"]["state"], "param_groups": [legacy]}

    recipient = _agent()
    recipient.load_state_dict(state)
    assert len(recipient.optimizer.param_groups) == 2  # our grouping survives
    for ours, theirs in zip(recipient.params, donor.params):
        assert torch.equal(
            recipient.optimizer.state[ours]["exp_avg"], donor.optimizer.state[theirs]["exp_avg"]
        )
        assert torch.equal(
            recipient.optimizer.state[ours]["exp_avg_sq"],
            donor.optimizer.state[theirs]["exp_avg_sq"],
        )


def test_critic_only_warmup_freezes_the_actor_then_hands_it_back():
    """The staged unfreeze (DESIGN.md §4, inherited by the human-BC chapter):
    a cloned policy must not be handed to advantages computed off a random
    value head. During warmup the actor is untouched and the critic still
    learns; the update that crosses the boundary starts moving the actor."""
    agent = _agent(rollout_steps=4, critic_warmup_updates=2)
    actor0 = [p.detach().clone() for p in agent.actor_params]
    critic0 = [p.detach().clone() for p in agent.critic_params]

    for update in range(2):
        report = _fill(agent, base=update * 4)
        assert all(torch.equal(p, q) for p, q in zip(agent.actor_params, actor0))
        # A frozen actor makes pi_new == pi_old exactly, which is the visible
        # signature of a warmup update in the logs.
        assert report["loss/approx_kl"] == pytest.approx(0.0, abs=1e-12)
        assert report["loss/clip_frac"] == 0.0
    assert any(not torch.equal(p, q) for p, q in zip(agent.critic_params, critic0))

    _fill(agent, base=8)  # update 2: the actor is live again
    assert any(not torch.equal(p, q) for p, q in zip(agent.actor_params, actor0))


def test_actor_lr_scale_applies_to_the_actor_group_only_and_anneals():
    agent = _agent(rollout_steps=4, actor_lr_scale=0.25)
    actor_group, critic_group = agent.optimizer.param_groups
    assert actor_group["lr"] == pytest.approx(0.25e-3)
    assert critic_group["lr"] == pytest.approx(1.0e-3)
    assert [id(p) for p in actor_group["params"]] == [id(p) for p in agent.actor_params]

    # The anneal rewrites BOTH groups from base_lr each update; reading a
    # group's own lr back and scaling it would compound the fraction.
    annealed = _agent(rollout_steps=4, actor_lr_scale=0.25, lr_anneal_steps=32)
    annealed.updates = 2  # 2 * 4 * 2 = 16 of 32 steps seen -> frac 0.5
    _fill(annealed)
    assert annealed.optimizer.param_groups[0]["lr"] == pytest.approx(0.125e-3)
    assert annealed.optimizer.param_groups[1]["lr"] == pytest.approx(0.5e-3)


def test_load_state_dict_keeps_the_configs_lr():
    """Warm-start hazard (audit 2026-08-05): torch's Optimizer.load_state_dict
    restores the CHECKPOINT's param-group lr, and a constant-lr config never
    rewrites lr after construction — so loading an annealed-to-the-floor donor
    would silently train the whole run at ~0. The constructing config must win
    on lr while the optimizer STATE (moments, updates counter) still restores."""
    donor = _agent()
    donor.optimizer.param_groups[0]["lr"] = 1.44e-7  # a finished anneal's floor
    donor.updates = 17
    state = donor.state_dict()

    recipient = _agent()  # same constructor lr=1.0e-3
    recipient.load_state_dict(state)
    assert recipient.optimizer.param_groups[0]["lr"] == recipient.base_lr == 1.0e-3
    assert recipient.updates == 17  # optimizer/agent state still restored


def test_bc_kl_coef_validates_and_requires_an_anchor():
    """The anchor is captured at begin_warm_start(); a scratch run with the
    penalty on is a config error and must fail loudly, not train un-anchored."""
    with pytest.raises(ValueError, match="bc_kl_coef"):
        _agent(bc_kl_coef=-0.1)
    with pytest.raises(TypeError, match="discrete"):
        PPOAgent(
            observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
            action_space=gym.spaces.Box(-1.0, 1.0, (2,), np.float32),
            num_envs=2, device="cpu", lr=1.0e-3, gamma=0.99, gae_lambda=0.95,
            rollout_steps=4, epochs=2, minibatches=2, clip_eps=0.2,
            entropy_coef=0.0, value_coef=0.5, max_grad_norm=0.5,
            hidden_sizes=[8], bc_kl_coef=0.5,
        )
    agent = _agent(rollout_steps=4, bc_kl_coef=0.5)
    with pytest.raises(RuntimeError, match="begin_warm_start"):
        _fill(agent)


def test_bc_kl_reports_the_metric_and_starts_at_zero():
    """At the warm start the policy IS the anchor, so the first minibatch's
    KL is exactly 0 and the update-mean stays near it; the metric key only
    appears when the penalty is on (the default report is unchanged)."""
    agent = _agent(rollout_steps=4, bc_kl_coef=0.5)
    agent.begin_warm_start()
    assert agent._bc_anchor is not None
    report = _fill(agent)
    assert 0.0 <= report["loss/bc_kl"] < 0.05
    assert "loss/bc_kl" not in _fill(_agent(rollout_steps=4))


def test_bc_kl_anchor_reduces_drift_from_the_start_policy():
    """The penalty's whole purpose: hold the unfrozen policy near the clone.
    Same init, same data, three update cycles — the anchored agent must end
    closer to its starting actor than the unanchored one."""
    def drift(coef: float) -> float:
        agent = _agent(rollout_steps=4, bc_kl_coef=coef)
        agent.begin_warm_start()
        start = [p.detach().clone() for p in agent.actor_params]
        for update in range(3):
            _fill(agent, base=4 * update)
        return sum(
            float((p - q).abs().sum()) for p, q in zip(agent.actor_params, start)
        )

    assert drift(50.0) < drift(0.0)


def test_bc_kl_anchor_survives_a_checkpoint_round_trip():
    """A resumed warm-started run must keep its penalty target: the anchor
    rides in state_dict when set, restores on load, and stays absent from
    default checkpoints (pre-anchor checkpoints load unchanged)."""
    agent = _agent(rollout_steps=4, bc_kl_coef=0.5)
    agent.begin_warm_start()
    state = agent.state_dict()
    assert "bc_anchor" in state

    fresh = _agent(rollout_steps=4, bc_kl_coef=0.5)
    fresh.load_state_dict(state)
    assert fresh._bc_anchor is not None
    report = _fill(fresh)  # would raise without the restored anchor
    assert "loss/bc_kl" in report

    assert "bc_anchor" not in _agent().state_dict()

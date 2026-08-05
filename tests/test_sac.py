"""SAC: the squashed-Gaussian log-prob, the soft Bellman target, the
temperature loop, and the scalar-loop contracts.

Three things here are invisible on the entire benchmark campaign and so are
pinned on synthetic spaces instead:

- `action_scale` is 1 on HalfCheetah/Hopper/Walker2d (actions already live in
  [-1, 1]), so the `-sum(log scale)` term in the log-prob is a no-op there;
- `action_bias` is 0 on every env in this repo, Pendulum included, so a bias
  bug is invisible even on the sanity gate;
- `terminated` is never True on Pendulum or HalfCheetah — the sanity gate and
  the pathfinder — so the `(1 - terminated)` bootstrap mask is dead code on
  both, and a truncation mix-up would first show up on Hopper, i.e. after the
  campaign launches.

Everything with an action dimension uses act_dim >= 2: a length-1 action
vector broadcasts shape bugs into correctly-shaped nonsense, and Pendulum's
act_dim is 1.
"""

import copy
import math

import gymnasium as gym
import numpy as np
import pytest
import torch
import torch.nn.functional as F
from torch import nn
from torch.distributions import AffineTransform, Normal, TanhTransform, TransformedDistribution

from rl.agents.sac import LOG_STD_MAX, LOG_STD_MIN, SACAgent, squashed_logprob
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.train import train

OBS_DIM, ACT_DIM = 3, 2


def _agent(act_dim=ACT_DIM, low=-1.0, high=1.0, batch_size=8, learning_starts=8,
           buffer_capacity=64, policy_frequency=2, autotune=True, alpha=0.2,
           gamma=0.9, tau=0.5, hidden_sizes=(4,), seed=0):
    torch.manual_seed(seed)
    return SACAgent(
        observation_space=gym.spaces.Box(-np.inf, np.inf, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Box(low, high, (act_dim,), np.float32),
        device="cpu", q_lr=1e-3, policy_lr=1e-3, gamma=gamma, tau=tau,
        batch_size=batch_size, buffer_capacity=buffer_capacity,
        learning_starts=learning_starts, hidden_sizes=list(hidden_sizes),
        policy_frequency=policy_frequency, autotune=autotune, alpha=alpha,
    )


def _row(t, act_dim=ACT_DIM, reward=None, terminated=False, truncated=False):
    return (
        np.full(OBS_DIM, 0.1 * t, dtype=np.float32),
        np.full(act_dim, 0.2, dtype=np.float32),
        float(t if reward is None else reward),
        np.full(OBS_DIM, 0.1 * (t + 1), dtype=np.float32),
        terminated, truncated, None, None,
    )


def _constant(net, value):
    """Zero every weight and set the output bias, so the net emits `value` for
    any input — turning a critic into a hand-computable constant."""
    with torch.no_grad():
        for p in net.parameters():
            p.zero_()
        [m for m in net.modules() if isinstance(m, nn.Linear)][-1].bias.fill_(value)


def _obs_linear(net, weight, bias):
    """Make a critic compute `weight * obs[0] + bias`, ignoring the action.

    Needs hidden_sizes=[1], and obs[0] positive so the ReLU passes it through.
    A critic that varies across the batch is what makes a (B, B) broadcast
    detectable: with CONSTANT target critics every row of the broadcast matrix
    is identical, so its mean equals the correct one and the bug hides.
    """
    layers = [m for m in net.modules() if isinstance(m, nn.Linear)]
    assert len(layers) == 2, "_obs_linear needs hidden_sizes=[1]"
    with torch.no_grad():
        layers[0].weight.zero_()
        layers[0].weight[0, 0] = 1.0
        layers[0].bias.zero_()
        layers[1].weight.fill_(weight)
        layers[1].bias.fill_(bias)


def _pin_actor(agent, mean_raw=0.0, log_std_raw=0.0):
    """Pin the actor's raw head outputs (log_std_raw is PRE tanh-rescale)."""
    with torch.no_grad():
        for p in agent.actor.net.parameters():
            p.zero_()
        last = [m for m in agent.actor.net.modules() if isinstance(m, nn.Linear)][-1]
        act_dim = agent.actor.action_scale.numel()
        last.bias[:act_dim].fill_(mean_raw)
        last.bias[act_dim:].fill_(log_std_raw)


# --------------------------------------------------------------------------
# the squashed-Gaussian log-prob
# --------------------------------------------------------------------------

def test_logprob_matches_a_transformed_distribution_oracle_including_the_affine():
    """torch's own change-of-variables machinery as an independent oracle.

    The affine step is not optional in the oracle: `TanhTransform()` alone is
    the density of tanh(u), which carries no `-sum(log scale)` term at all, so
    an oracle without `AffineTransform` disagrees by exactly act_dim*log(scale)
    and would either fail this test or quietly get it rewritten to match.
    float64 throughout — the oracle inverts through atanh, which is unusable
    in float32 near the bounds.
    """
    torch.manual_seed(0)
    batch, act_dim = 5, 3
    mean = torch.randn(batch, act_dim, dtype=torch.float64)
    log_std = torch.randn(batch, act_dim, dtype=torch.float64).clamp(-1.5, 0.5)
    scale = torch.tensor([2.0, 0.5, 3.0], dtype=torch.float64)
    bias = torch.tensor([1.0, -1.0, 0.0], dtype=torch.float64)
    u = Normal(mean, log_std.exp()).sample()

    ours = squashed_logprob(u, mean, log_std, scale)
    oracle = TransformedDistribution(
        Normal(mean, log_std.exp()),
        [TanhTransform(cache_size=1), AffineTransform(loc=bias, scale=scale)],
    )
    theirs = oracle.log_prob(torch.tanh(u) * scale + bias).sum(-1)

    assert ours.shape == (batch,)  # never (batch, act_dim), never (batch, batch)
    torch.testing.assert_close(ours, theirs, rtol=0, atol=1e-9)


def test_logprob_is_one_number_per_transition_at_every_act_dim():
    for act_dim in (1, 2, 5):
        u = torch.zeros(7, act_dim)
        logp = squashed_logprob(u, torch.zeros(7, act_dim), torch.zeros(7, act_dim),
                                torch.ones(act_dim))
        assert logp.shape == (7,)


def test_scale_shifts_the_logprob_by_log_scale_and_bias_does_not_appear():
    """A scale of s spreads the same probability over s times the range, so
    every density drops by log(s) per dimension. The bias is a pure shift with
    unit Jacobian — it is not even an argument here, and this pins that."""
    u = torch.tensor([[0.3, -0.7]])
    mean, log_std = torch.zeros(1, 2), torch.zeros(1, 2)
    unit = squashed_logprob(u, mean, log_std, torch.ones(2))
    doubled = squashed_logprob(u, mean, log_std, torch.full((2,), 2.0))
    assert float(unit - doubled) == pytest.approx(2 * math.log(2.0))

    shifted = _agent(low=1.0, high=3.0)   # same scale (1.0), different bias
    plain = _agent(low=-1.0, high=1.0)
    obs = torch.zeros(1, OBS_DIM)
    torch.manual_seed(1)
    _, logp_shifted = shifted.actor.sample(obs)
    torch.manual_seed(1)
    _, logp_plain = plain.actor.sample(obs)
    torch.testing.assert_close(logp_shifted, logp_plain)


def test_stable_correction_survives_saturation_where_the_naive_one_collapses():
    """CleanRL computes log(1 - tanh^2(u)) literally, with a 1e-6 floor. We use
    2*(log2 - u - softplus(-2u)). They agree in the ordinary regime and part
    company once the policy saturates — which is the regime a converged SAC
    actor tends toward."""
    u = torch.tensor([[6.0, 8.0, 9.0, 12.0]])
    mean, log_std, scale = torch.zeros(1, 4), torch.zeros(1, 4), torch.ones(4)
    ours = squashed_logprob(u, mean, log_std, scale)
    exact = squashed_logprob(u.double(), mean.double(), log_std.double(), scale.double())
    torch.testing.assert_close(ours, exact.float(), rtol=1e-6, atol=1e-3)

    y = torch.tanh(u)
    naive = (Normal(mean, log_std.exp()).log_prob(u)
             - torch.log(scale * (1 - y.pow(2)) + 1e-6)).sum(-1)
    assert float((naive - exact.float()).abs().max()) > 1.0  # they really do diverge


def test_the_naive_correction_loses_its_gradient_in_saturation_and_ours_does_not():
    """The reason the divergence above matters. d/du log(1 - tanh^2(u)) = -2
    tanh(u), which is -2 deep in saturation — that gradient is the entropy
    pressure keeping the policy from collapsing to a deterministic one. The
    epsilon-floored form returns exactly zero there instead."""
    stable_u = torch.tensor([9.0], requires_grad=True)
    (2.0 * (math.log(2.0) - stable_u - F.softplus(-2.0 * stable_u))).backward()
    assert float(stable_u.grad) == pytest.approx(-2.0, abs=1e-5)

    naive_u = torch.tensor([9.0], requires_grad=True)
    torch.log(1 - torch.tanh(naive_u).pow(2) + 1e-6).backward()
    assert float(naive_u.grad) == 0.0


def test_rsample_keeps_the_actor_differentiable_through_the_action():
    """SAC's actor loss backpropagates through the sampled action into the
    critic. A plain `.sample()` would detach that path, leaving the actor with
    no gradient at all and nothing failing."""
    agent = _agent()
    action, logp = agent.actor.sample(torch.zeros(4, OBS_DIM))
    assert action.requires_grad and logp.requires_grad
    action.sum().backward()
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in agent.actor.parameters())


def test_log_std_is_squashed_into_its_bounds_rather_than_clamped():
    """A hard clamp has zero gradient outside the range; the rescale keeps the
    head recoverable. Extreme raw outputs must land inside (LOG_STD_MIN,
    LOG_STD_MAX) without ever reaching them."""
    agent = _agent()
    for raw in (-500.0, 500.0):
        _pin_actor(agent, log_std_raw=raw)
        with torch.no_grad():
            _, log_std = agent.actor(torch.zeros(1, OBS_DIM))
        assert LOG_STD_MIN <= float(log_std.min()) <= float(log_std.max()) <= LOG_STD_MAX
    _pin_actor(agent, log_std_raw=0.0)
    with torch.no_grad():
        _, log_std = agent.actor(torch.zeros(1, OBS_DIM))
    assert float(log_std[0, 0]) == pytest.approx(LOG_STD_MIN + 0.5 * (LOG_STD_MAX - LOG_STD_MIN))


# --------------------------------------------------------------------------
# the soft Bellman target
# --------------------------------------------------------------------------

def test_td_target_uses_the_twin_min_the_discount_and_terminated_only():
    """Hand-computed end to end. The target critics are pinned to 5 and 3, so
    a max (or either critic alone) gives 5 and fails; gamma, the (1 -
    terminated) mask and the raw reward are all pinned by construction; and
    truncated rows must still bootstrap, which is why a third of the rows
    carry truncated=True with terminated=False.

    The target critics are made to VARY across the batch (10*x+5 and x+3 over
    x = next_obs[0]), which matters for more than realism: with constant target
    critics every row of a (B, B) broadcast is identical, its mean equals the
    correct one, and the shape bug this test is partly here for slips through.
    """
    batch = 6
    agent = _agent(batch_size=batch, learning_starts=batch, buffer_capacity=batch,
                   gamma=0.9, autotune=False, alpha=1e-12, hidden_sizes=(1,))
    _obs_linear(agent.q1_target, 10.0, 5.0)  # 10x + 5, in [6.0, 11.0] here
    _obs_linear(agent.q2_target, 1.0, 3.0)   #  x + 3, in [3.1, 3.6] -> always the min
    q1_before, q2_before = copy.deepcopy(agent.q1), copy.deepcopy(agent.q2)

    rows = [_row(t, reward=float(t), terminated=(t % 3 == 0), truncated=(t % 3 == 1))
            for t in range(batch)]
    for row in rows[:-1]:
        assert agent.update(row) == {}
    np.random.seed(0)
    metrics = agent.update(rows[-1])
    np.random.seed(0)
    idx = np.random.randint(0, batch, size=batch)  # the draw sample() just made

    # Inputs come from the buffer (its storage is test_replay.py's job); only
    # the soft-Bellman FORMULA is hand-computed here.
    min_next_q = agent.buffer.next_obs[idx][:, 0] + 3.0
    target = torch.as_tensor(
        agent.buffer.rewards[idx]
        + 0.9 * (1.0 - agent.buffer.terminated[idx]) * min_next_q
    )
    assert float(target.std()) > 0.1  # rows must differ, or a (B, B) target hides
    state_action = torch.as_tensor(
        np.concatenate([agent.buffer.obs[idx], agent.buffer.actions[idx]], axis=-1)
    )
    with torch.no_grad():
        expected = float(
            F.mse_loss(q1_before(state_action).squeeze(-1), target)
            + F.mse_loss(q2_before(state_action).squeeze(-1), target)
        )
    assert metrics["loss/critic"] == pytest.approx(expected, rel=1e-4)


def test_the_entropy_bonus_actually_enters_the_td_target():
    """The soft part of the soft Bellman backup. Two agents identical in every
    way except alpha, driven through the same transitions with the same RNG:
    if `- alpha * log pi` were missing from the target, their critic losses
    would be bitwise equal. (The hand-computed test above runs at alpha 1e-12
    precisely so the entropy term is negligible there — which means it cannot
    police this, and did not.)"""
    def critic_loss_at(alpha):
        agent = _agent(batch_size=6, learning_starts=6, buffer_capacity=6,
                       autotune=False, alpha=alpha, seed=0)
        for t in range(5):
            agent.update(_row(t, reward=float(t)))
        np.random.seed(0)
        torch.manual_seed(0)
        return agent.update(_row(5, reward=5.0))["loss/critic"]

    assert critic_loss_at(1e-12) != pytest.approx(critic_loss_at(0.5), rel=1e-6)


def test_an_unsqueezed_critic_output_turns_the_target_into_a_matrix_silently():
    """Why every critic output above takes .squeeze(-1), pinned as a contract.

    Critics emit (B, 1); rewards and log-probs are (B,). Drop the squeeze and
    the target broadcasts into (B, B) — and F.mse_loss accepts the mismatch
    with a warning rather than an error, regressing every critic output toward
    the batch mean while the actor's loss stays accidentally correct.
    """
    rewards, min_q_squeezed = torch.arange(4.0), torch.full((4,), 3.0)
    assert (rewards + 0.99 * min_q_squeezed).shape == (4,)

    min_q_unsqueezed = torch.full((4, 1), 3.0)
    assert (rewards + 0.99 * min_q_unsqueezed).shape == (4, 4)  # the bug, pinned
    with pytest.warns(UserWarning, match="target size"):
        F.mse_loss(torch.zeros(4, 1), rewards + 0.99 * min_q_unsqueezed)  # ...and it runs


def test_no_learning_happens_before_learning_starts():
    agent = _agent(learning_starts=5, batch_size=4)
    for t in range(4):
        assert agent.update(_row(t)) == {}
    assert agent.grad_steps == 0
    assert agent.update(_row(4)) != {}
    assert agent.grad_steps == 1


def test_update_reports_the_full_metric_set_on_an_actor_step():
    agent = _agent(learning_starts=4, batch_size=4, policy_frequency=2)
    for t in range(3):
        agent.update(_row(t))
    metrics = agent.update(_row(3))  # grad_steps 0 -> the actor block runs
    assert set(metrics) == {
        "loss/critic", "loss/q_pred_mean", "loss/actor", "loss/alpha",
        "loss/alpha_value", "loss/entropy", "loss/policy_std", "loss/mu_absmax",
    }
    assert all(np.isfinite(v) for v in metrics.values())
    # grad_steps 1 is a delayed step: critic only.
    assert set(agent.update(_row(4))) == {"loss/critic", "loss/q_pred_mean"}


def test_the_actors_backward_dirties_the_critics_and_the_next_step_clears_it():
    """actor_loss.backward() differentiates through Q1/Q2 and leaves gradient
    on their parameters. That is safe ONLY because the critic step runs first
    and begins with zero_grad — reorder the two blocks and the critic silently
    takes a step down the actor's objective as well."""
    agent = _agent(learning_starts=4, batch_size=4, policy_frequency=1)
    for t in range(4):
        agent.update(_row(t))
    assert float(agent.q1[0].weight.grad.abs().sum()) > 0  # the actor left this behind

    seen = {}
    real_zero_grad = agent.q_optimizer.zero_grad

    def spy(*args, **kwargs):
        grad = agent.q1[0].weight.grad
        seen["before"] = 0.0 if grad is None else float(grad.abs().sum())
        return real_zero_grad(*args, **kwargs)

    agent.q_optimizer.zero_grad = spy
    agent.update(_row(5))
    assert seen["before"] > 0  # the pollution was still there when the step began
    # ...and zero_grad ran before the critic's own backward, so it was discarded.


def test_polyak_moves_the_targets_toward_the_critics():
    agent = _agent(learning_starts=2, batch_size=2, tau=1.0)  # tau 1 = hard sync
    _constant(agent.q1_target, 99.0)
    for t in range(2):
        agent.update(_row(t))
    probe = torch.zeros(1, OBS_DIM + ACT_DIM)
    with torch.no_grad():
        assert float(agent.q1_target(probe)) == pytest.approx(float(agent.q1(probe)), abs=1e-6)


# --------------------------------------------------------------------------
# the temperature loop
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "log_std_raw, below_target",
    # Probed values: entropy is NOT monotone in std, because a huge pre-squash
    # std saturates the tanh and piles mass on the bounds. raw -10 gives std
    # 0.0067 and entropy -7.16; raw +0.5 gives std 1.12 and entropy +1.27.
    [(-10.0, True), (0.5, False)],
)
def test_alpha_rises_when_entropy_is_below_target_and_falls_when_above(log_std_raw, below_target):
    agent = _agent(learning_starts=4, batch_size=4, policy_frequency=1)
    _pin_actor(agent, mean_raw=0.0, log_std_raw=log_std_raw)
    for t in range(3):
        agent.update(_row(t))
    before = float(agent.log_alpha)
    metrics = agent.update(_row(3))

    assert (metrics["loss/entropy"] < agent.target_entropy) is below_target
    if below_target:
        assert float(agent.log_alpha) > before  # buy more exploration
    else:
        assert float(agent.log_alpha) < before  # allow the policy to commit


def test_autotune_off_pins_alpha_and_builds_no_optimizer():
    agent = _agent(learning_starts=2, batch_size=2, autotune=False, alpha=0.35)
    assert agent.alpha_optimizer is None
    assert float(agent.log_alpha.exp()) == pytest.approx(0.35)
    for t in range(3):
        metrics = agent.update(_row(t))
    assert float(agent.log_alpha.exp()) == pytest.approx(0.35)
    assert "loss/alpha" not in metrics


def test_log_alpha_survives_a_checkpoint_round_trip_and_keeps_being_optimized(tmp_path):
    """The rebind trap. `self.log_alpha = state["log_alpha"]` restores the
    VALUE correctly and passes every obvious check, but the alpha optimizer
    still holds the old tensor — so it trains a phantom while the agent's
    temperature is frozen forever. An in-memory state_dict round trip cannot
    see it (the rebound tensor is the one just saved); only a real save/load
    can, which is why this test goes through a file.
    """
    agent = _agent(learning_starts=2, batch_size=2, policy_frequency=1)
    for t in range(6):
        agent.update(_row(t))
    saved = float(agent.log_alpha)
    assert saved != 0.0  # it actually moved, or the test proves nothing

    path = tmp_path / "sac.pt"
    torch.save(agent.state_dict(), path)
    restored = _agent(learning_starts=2, batch_size=2, policy_frequency=1, seed=7)
    restored.load_state_dict(torch.load(path, weights_only=False))
    assert float(restored.log_alpha) == pytest.approx(saved)
    assert restored.alpha_optimizer.param_groups[0]["params"][0] is restored.log_alpha

    for t in range(6, 12):
        restored.update(_row(t))
    assert float(restored.log_alpha) != pytest.approx(saved)  # still learning


def test_checkpoint_round_trip_reproduces_the_deterministic_policy(tmp_path):
    agent = _agent(learning_starts=2, batch_size=2)
    for t in range(6):
        agent.update(_row(t))
    obs = np.arange(OBS_DIM, dtype=np.float32)
    before = agent.act(obs, deterministic=True)

    path = tmp_path / "sac.pt"
    torch.save(agent.state_dict(), path)
    restored = _agent(learning_starts=2, batch_size=2, seed=7)
    restored.load_state_dict(torch.load(path, weights_only=False))
    np.testing.assert_allclose(restored.act(obs, deterministic=True), before, rtol=1e-6)


# --------------------------------------------------------------------------
# act() and the scalar-loop contracts
# --------------------------------------------------------------------------

def test_action_scale_and_bias_come_from_the_true_bounds():
    agent = _agent(low=-1.0, high=3.0)
    assert agent.actor.action_scale.tolist() == [2.0, 2.0]
    assert agent.actor.action_bias.tolist() == [1.0, 1.0]
    assert "action_scale" in dict(agent.actor.named_buffers())  # rides the checkpoint


def test_deterministic_act_is_the_squashed_mean_in_shape_dtype_and_bounds():
    agent = _agent(low=-1.0, high=3.0, learning_starts=0)
    obs = np.arange(OBS_DIM, dtype=np.float32)
    action = agent.act(obs, deterministic=True)
    assert action.shape == (ACT_DIM,) and action.dtype == np.float32
    assert np.all(action >= -1.0) and np.all(action <= 3.0)
    # Rebuilt from the raw head output, NOT by calling deterministic_action:
    # comparing act() against the method it delegates to is circular, and
    # passes happily with the scale or bias dropped from both sides.
    with torch.no_grad():
        mean, _ = agent.actor(torch.as_tensor(obs).unsqueeze(0))
    np.testing.assert_allclose(action, np.tanh(mean.numpy()[0]) * 2.0 + 1.0, rtol=1e-6)


def test_sampled_actions_vary_and_stay_inside_the_bounds():
    agent = _agent(low=-1.0, high=3.0, learning_starts=0)
    draws = np.stack([agent.act(np.zeros(OBS_DIM, dtype=np.float32)) for _ in range(20)])
    assert draws.std() > 0.0
    assert draws.min() >= -1.0 and draws.max() <= 3.0  # squashing, not clipping


def test_warmup_takes_uniform_random_actions_without_consulting_the_policy():
    """Exploration lives in act(), as DQN's epsilon does, so the train loop
    needs no SAC-specific branch. `deterministic` must bypass it — otherwise an
    eval scheduled inside the warm-up window would score noise."""
    agent = _agent(learning_starts=5, batch_size=4)
    calls = []
    real_sample = agent.actor.sample
    agent.actor.sample = lambda obs: (calls.append(1), real_sample(obs))[1]

    obs = np.zeros(OBS_DIM, dtype=np.float32)
    warmup = np.stack([agent.act(obs) for _ in range(5)])
    assert calls == []  # the policy was never asked
    assert warmup.shape == (5, ACT_DIM) and warmup.dtype == np.float32
    assert warmup.std() > 0 and warmup.min() >= -1.0 and warmup.max() <= 1.0

    agent.act(obs, deterministic=True)
    assert calls == []  # deterministic goes to the mean, not through sample()
    for t in range(5):
        agent.update(_row(t))
    calls.clear()  # update() samples too (the TD target and the actor loss)
    agent.act(obs)
    assert calls == [1]  # warm-up over: the policy acts


def test_constructor_rejects_spaces_sac_cannot_serve():
    box = gym.spaces.Box(-1, 1, (OBS_DIM,), np.float32)
    common = dict(device="cpu", q_lr=1e-3, policy_lr=1e-3, gamma=0.99, tau=0.005,
                  batch_size=4, buffer_capacity=16, learning_starts=4, hidden_sizes=[4])
    with pytest.raises(TypeError, match="flat Box action space"):
        SACAgent(box, gym.spaces.Discrete(3), **common)
    with pytest.raises(TypeError, match="flat Box action space"):
        SACAgent(box, gym.spaces.Box(-1, 1, (2, 2), np.float32), **common)
    with pytest.raises(TypeError, match="flat Box observation space"):
        SACAgent(gym.spaces.Box(0, 1, (2, 4, 4), np.float32),
                 gym.spaces.Box(-1, 1, (ACT_DIM,), np.float32), **common)
    with pytest.raises(ValueError, match="at least one hidden layer"):
        SACAgent(box, gym.spaces.Box(-1, 1, (ACT_DIM,), np.float32),
                 **{**common, "hidden_sizes": []})
    with pytest.raises(ValueError, match="unknown activation"):
        SACAgent(box, gym.spaces.Box(-1, 1, (ACT_DIM,), np.float32),
                 **common, activation="gelu")


def test_pendulum_train_loop_smoke(tmp_path, monkeypatch):
    """Through the real entry point: the scalar loop, eval, and checkpointing.
    Also the one place the agent meets an env whose action scale is not 1
    (Pendulum is Box(-2, 2)), which is what exercises the log-prob's scale term
    outside the synthetic tests above."""
    monkeypatch.chdir(tmp_path)
    cfg = Config(
        env_id="Pendulum-v1", seed=0, total_steps=400, eval_every=200, eval_episodes=1,
        run_name="test_pendulum_sac", logger="tensorboard",
        agent=dict(algo="sac", q_lr=1e-3, policy_lr=1e-3, gamma=0.99, tau=0.005,
                   batch_size=16, buffer_capacity=1000, learning_starts=100,
                   hidden_sizes=[16, 16], policy_frequency=2),
    )
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_pendulum_sac" / "checkpoint.pt")
    assert ckpt["step"] == 400
    assert {"actor", "q1", "q2", "q1_target", "q2_target", "log_alpha"} <= set(ckpt["agent"])
    assert (tmp_path / "runs" / "test_pendulum_sac" / "best_checkpoint.pt").exists()


def test_normalizer_flags_are_refused_for_the_scalar_path():
    """SAC runs raw by design (PLAN.md M1). A silently ignored flag would stamp
    normalize_obs into the run's config snapshot, and every checkpoint from
    that "successful" run would then refuse to re-evaluate."""
    cfg = Config(
        env_id="Pendulum-v1", seed=0, total_steps=10, eval_every=10, eval_episodes=1,
        run_name="x", normalize_obs=True, agent=dict(algo="sac"),
    )
    with pytest.raises(ValueError, match="need a vectorized algorithm"):
        train(cfg)

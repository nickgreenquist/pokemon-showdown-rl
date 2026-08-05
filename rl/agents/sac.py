"""SAC (Haarnoja et al. 2018b, "Soft Actor-Critic Algorithms and
Applications"): off-policy actor-critic that maximizes reward AND entropy.

The objective is the ordinary one plus a bonus for keeping the policy random:

    J(pi) = E[ sum_t gamma^t ( r_t + alpha * H(pi(.|s_t)) ) ]

That single change reorganizes everything else. Exploration stops being a
bolt-on (DQN's epsilon schedule, PPO's entropy coefficient nudging a policy
that is otherwise free to collapse) and becomes part of what is being
optimized, so the agent is *paid* to keep its options open until the reward
signal justifies committing. `alpha` is the exchange rate between the two, and
in this version it is learned rather than tuned — see below.

Four pieces, each replacing something the earlier agents did differently:

- **Twin Q critics with a min.** DQN's target takes a max over actions, which
  systematically prefers whichever action is currently over-estimated; Double
  DQN attacks that by decoupling selection from evaluation. SAC attacks the
  same bias from the other side: keep two independently initialized critics
  and bootstrap from `min(Q1, Q2)`. Two noisy estimates rarely over-estimate
  the same action, so the min is a cheap pessimism that cancels the drift.
- **A reparameterized actor.** With a continuous action space there is no
  argmax to take, so the policy is trained by pushing actions uphill on the
  critic — `a = mu(s) + sigma(s) * eps` makes `a` a differentiable function of
  the policy parameters, so the actor's gradient flows THROUGH Q. That is a
  genuinely different estimator from PPO's score function: PPO reweights
  sampled log-probs by an advantage it cannot differentiate, SAC differentiates
  the critic itself. It is also why SAC needs a real critic of (s, a) rather
  than PPO's V(s).
- **A tanh-squashed Gaussian.** Actions must respect the env's bounds, and
  SAC squashes rather than clips: `a = tanh(u)`. Clipping (PPO's choice, via
  the ClipAction wrapper) puts probability mass exactly on the boundary and
  makes the log-prob of a clipped action a lie; squashing keeps a proper
  density, at the cost of a change-of-variables correction (see
  `squashed_logprob`) that clipping does not need. This is the machinery the
  PPO agent deliberately did NOT spend, so that the Phase-3 comparison would
  differ in the algorithm rather than in the policy parameterization.
- **A learned temperature.** In the original formulation `alpha` was the one
  hyperparameter that always needed tuning, because it is not scale-free: the
  entropy term is in nats while the reward term is in whatever units the env
  pays, so the right alpha moves with the reward scale. Version 2 turns it into
  a constrained problem — hold entropy at a target and let a dual variable find
  the price — with `H_target = -act_dim` as the convention. `alpha` then decays
  on its own as the critic gets confident.

Soft target updates (rl/common/polyak.py) replace DQN's hard sync: the actor's
loss differentiates through the critics, so a target that jumped every N steps
would put a discontinuity in the actor's objective at every sync.

Recipe: CleanRL `sac_continuous_action.py`, taken WHOLE (see PLAN.md's Phase 3
spec for every value and every stated divergence). Two things it does that our
PPO deliberately does not, both recipe facts rather than oversights: no
orthogonal init (no SAC reference uses it), and no observation or reward
normalization — every published SAC number comes from raw envs, and a running
normalizer under a replay buffer would scale stored transitions by statistics
that have since moved, while a drifting reward scale is exactly what the
temperature loop would have to chase.
"""

import math
from typing import Any

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.distributions import Normal

from rl.agents.base import Agent
from rl.buffers.replay import ReplayBuffer
from rl.common.polyak import polyak_update
from rl.networks.mlp import mlp

ACTIVATIONS = {"relu": nn.ReLU, "tanh": nn.Tanh}
# Bounds on the log standard deviation. CleanRL's values and CleanRL's form:
# the raw head output is squashed smoothly into the range rather than clamped
# (SpinningUp and SB3 both hard-clamp, at (-20, 2)). A clamp has zero gradient
# outside the range, so a head that overshoots can never come back; and the -5
# floor keeps std above ~0.0067, which stops the policy going effectively
# deterministic behind the temperature loop's back.
LOG_STD_MIN, LOG_STD_MAX = -5.0, 2.0


def squashed_logprob(
    u: torch.Tensor, mean: torch.Tensor, log_std: torch.Tensor, action_scale: torch.Tensor
) -> torch.Tensor:
    """log pi(a|s) for `a = tanh(u) * scale + bias` with `u ~ N(mean, e^log_std)`.

    Squashing is a change of variables, so the Gaussian's density has to be
    divided by the Jacobian of the transform:

        da/du = scale * (1 - tanh^2(u))
        log pi(a) = sum_i [ log N(u_i) - log scale_i - log(1 - tanh^2(u_i)) ]

    The sum is over ACTION DIMENSIONS and turns (B, act_dim) into the (B,) the
    losses need. Never let it return (B, B): a 1-D `u` would broadcast against
    a (B, act_dim) mean into a matrix whose `.sum(-1)` is correctly shaped
    nonsense — the same trap the PPO agent documents, and one Pendulum's
    act_dim of 1 cannot see.

    `log(1 - tanh^2(u))` is computed as `2*(log 2 - u - softplus(-2u))`, which
    is exact and stable, rather than literally (CleanRL adds 1e-6 inside the
    log to stop it diverging). The naive form is not merely imprecise: the
    epsilon CAPS the correction near 13.8/dim, and worse, drives its gradient
    to zero once |u| passes ~8 — so the entropy pressure that keeps the policy
    from going deterministic switches off exactly where it is needed. In
    float32 `1 - tanh^2(u)` also underflows to 0 at |u| >= 8.664.

    `bias` never appears: a shift has unit Jacobian. `scale` does, which
    matters for the temperature loop (a constant offset in log pi shifts
    realized entropy against a fixed H_target) even though it drops out of the
    actor's gradient. It is zero on all three MuJoCo benchmark envs, whose
    actions are already in [-1, 1] — the reason the tests pin it on a
    synthetic asymmetric space instead.
    """
    logp_u = Normal(mean, log_std.exp()).log_prob(u)
    log_jacobian = 2.0 * (math.log(2.0) - u - F.softplus(-2.0 * u))
    return (logp_u - torch.log(action_scale) - log_jacobian).sum(-1)


class SquashedGaussianActor(nn.Module):
    """State-dependent diagonal Gaussian, squashed into the action bounds.

    The scale head is what distinguishes this from PPO's `GaussianActor`,
    which carries a state-INDEPENDENT free `log_std` parameter. That fork was
    made deliberately in Phase 2 so the Phase-3 comparison would land here:
    a state-dependent scale is SAC's parameterization, and it is what makes
    the tanh log-det-Jacobian correction necessary.

    One `Linear(hidden, 2 * act_dim)` split by `chunk` rather than two heads.
    They are the same function: chunking `Wx + b` into its first and last
    act_dim rows IS two Linears over the shared trunk, with identical parameter
    count and identical per-element init distribution (the default init's bound
    depends on fan_in, which does not move when out_features doubles). Only the
    RNG draw order differs. This holds because `mlp()` puts no activation after
    its output layer — with one, `chunk` would silently become two heads
    sharing a nonlinearity.
    """

    def __init__(
        self,
        obs_dim: int,
        hidden_sizes: list[int],
        act_dim: int,
        action_low: np.ndarray,
        action_high: np.ndarray,
        activation: type[nn.Module],
    ):
        super().__init__()
        self.net = mlp(obs_dim, hidden_sizes, 2 * act_dim, activation=activation)
        # Buffers, not plain attributes: they move with .to(device) and ride
        # along in state_dict, so a restored policy cannot lose its action
        # scaling. Both are read from the env's TRUE bounds, which make_env
        # restores after ClipAction rewrites them to +/-inf.
        self.register_buffer(
            "action_scale", torch.as_tensor((action_high - action_low) / 2.0, dtype=torch.float32)
        )
        self.register_buffer(
            "action_bias", torch.as_tensor((action_high + action_low) / 2.0, dtype=torch.float32)
        )

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mean, log_std = self.net(obs).chunk(2, dim=-1)
        log_std = LOG_STD_MIN + 0.5 * (LOG_STD_MAX - LOG_STD_MIN) * (torch.tanh(log_std) + 1.0)
        return mean, log_std

    def sample(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """A reparameterized action and its log-prob, shaped (B, act_dim), (B,).

        `rsample`, not `sample`: the actor's loss is backpropagated through
        this action into the critic, which is the whole point of the
        reparameterization trick. A plain `sample()` would silently sever that
        path and leave the actor learning nothing.
        """
        mean, log_std = self(obs)
        u = Normal(mean, log_std.exp()).rsample()
        action = torch.tanh(u) * self.action_scale + self.action_bias
        return action, squashed_logprob(u, mean, log_std, self.action_scale)

    def deterministic_action(self, obs: torch.Tensor) -> torch.Tensor:
        """The eval-time policy, as every SAC reference defines it.

        Precisely: the image of the pre-squash Gaussian's mode. Not the mode of
        the squashed density (the tanh Jacobian reweights it) and not its mean
        (which has no closed form) — but it is the standard, and the one the
        published numbers are measured with.
        """
        mean, _ = self(obs)
        return torch.tanh(mean) * self.action_scale + self.action_bias


class SACAgent(Agent):
    def __init__(
        self,
        observation_space: gym.Space,
        action_space: gym.Space,
        device: str,
        q_lr: float,
        policy_lr: float,
        gamma: float,
        tau: float,
        batch_size: int,
        buffer_capacity: int,
        learning_starts: int,
        hidden_sizes: list[int],
        activation: str = "relu",
        policy_frequency: int = 2,
        target_network_frequency: int = 1,
        autotune: bool = True,
        alpha: float = 0.2,
    ):
        if not isinstance(observation_space, gym.spaces.Box) or len(observation_space.shape) != 1:
            raise TypeError("SACAgent requires a flat Box observation space")
        if not isinstance(action_space, gym.spaces.Box) or len(action_space.shape) != 1:
            raise TypeError("SACAgent requires a flat Box action space")
        if not hidden_sizes:
            raise ValueError("SACAgent needs at least one hidden layer")
        if activation not in ACTIVATIONS:
            raise ValueError(f"unknown activation {activation!r}")
        self.action_space = action_space
        self.device = torch.device(device)
        self.gamma = gamma
        self.tau = tau
        self.batch_size = batch_size
        self.learning_starts = learning_starts
        self.policy_frequency = policy_frequency
        self.target_network_frequency = target_network_frequency
        self.autotune = autotune
        obs_dim, act_dim = int(observation_space.shape[0]), int(action_space.shape[0])
        act_cls = ACTIVATIONS[activation]

        # No orthogonal init anywhere: PyTorch's default is what every SAC
        # reference ships, and it is a stated asymmetry with our PPO (whose
        # per-head gains come from the conv/feedforward PPO lineage).
        self.actor = SquashedGaussianActor(
            obs_dim, hidden_sizes, act_dim, action_space.low, action_space.high, act_cls
        ).to(self.device)

        def build_critic() -> nn.Module:
            # Q(s, a): the action is an INPUT here, not an output index. That
            # is the structural difference from DQN's Q(s, .) head, and the
            # reason a continuous action space needs a reparameterized actor
            # to find the max at all.
            return mlp(obs_dim + act_dim, hidden_sizes, 1, activation=act_cls).to(self.device)

        self.q1, self.q2 = build_critic(), build_critic()
        self.q1_target, self.q2_target = build_critic(), build_critic()
        self.q1_target.load_state_dict(self.q1.state_dict())
        self.q2_target.load_state_dict(self.q2.state_dict())
        self.q1_target.requires_grad_(False)
        self.q2_target.requires_grad_(False)

        # One optimizer over both critics: their parameters are disjoint, so a
        # summed loss optimizes each exactly as a separate optimizer would.
        self.q_optimizer = torch.optim.Adam(
            [*self.q1.parameters(), *self.q2.parameters()], lr=q_lr
        )
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=policy_lr)
        # log alpha, not alpha: keeps the temperature positive without a
        # constraint, and makes the dual update multiplicative. Init 0 -> alpha
        # starts at 1.0. The temperature optimizer runs at Q'S learning rate,
        # not the policy's -- CleanRL's choice, and the obvious guess is wrong
        # by 3.3x on the one loop that sets the reward/entropy exchange rate.
        self.log_alpha = torch.tensor(
            [0.0 if autotune else math.log(alpha)], device=self.device, requires_grad=autotune
        )
        self.alpha_optimizer = (
            torch.optim.Adam([self.log_alpha], lr=q_lr) if autotune else None
        )
        # The convention from the paper: one nat of entropy per action
        # dimension is "enough" exploration.
        self.target_entropy = -float(act_dim)

        self.buffer = ReplayBuffer(
            buffer_capacity,
            observation_space.shape,
            # float32, not the env's float64: the nets cast to float32 anyway,
            # so storing wider is lossless-equivalent and costs 136MB a run.
            obs_dtype=np.float32,
            action_shape=(act_dim,),
            action_dtype=np.float32,
        )
        self.transitions = 0  # env transitions seen; drives warm-up and the learning gate
        self.grad_steps = 0  # gradient steps taken; drives the actor delay and target syncs

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> np.ndarray:
        # Warm-up: uniform random actions until the buffer has something worth
        # learning from. Exploration lives here rather than in the train loop,
        # exactly as DQN's epsilon does. `deterministic` bypasses it so an eval
        # pass scheduled inside the warm-up window still scores the policy.
        # action_space.sample() is uniform over the TRUE bounds only because
        # make_env restores them after ClipAction; without that it would draw
        # a standard normal and stock the buffer with actions a tanh policy can
        # never produce.
        if not deterministic and self.transitions < self.learning_starts:
            return self.action_space.sample()
        # Unconditional batch dim: this agent runs the scalar loop, so obs is
        # always a single observation (DQN's pattern). The critic's
        # cat([obs, act], -1) needs rank 2 regardless.
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device).unsqueeze(0)
        with torch.no_grad():
            action = (
                self.actor.deterministic_action(obs_t) if deterministic
                else self.actor.sample(obs_t)[0]
            )
        return action.squeeze(0).cpu().numpy()

    def update(self, batch: Any) -> dict[str, float]:
        obs, action, reward, next_obs, terminated, _truncated, _mask, _next_mask = batch
        self.transitions += 1
        # Discount gamma^1: this is a 1-step agent, and `truncated` is dropped
        # because nothing downstream needs it -- the bootstrap is cut by
        # `terminated` alone, so a time-limit cut bootstraps as it should.
        self.buffer.add(obs, action, reward, next_obs, float(terminated), self.gamma)
        if self.transitions < self.learning_starts:
            return {}

        obs_b, actions_b, rewards_b, next_obs_b, terminated_b, discounts_b, _, _ = (
            self.buffer.sample(self.batch_size)
        )
        obs_t = torch.as_tensor(obs_b, device=self.device)
        actions_t = torch.as_tensor(actions_b, device=self.device)
        rewards_t = torch.as_tensor(rewards_b, device=self.device)
        next_obs_t = torch.as_tensor(next_obs_b, device=self.device)
        terminated_t = torch.as_tensor(terminated_b, device=self.device)
        discounts_t = torch.as_tensor(discounts_b, device=self.device)
        alpha = self.log_alpha.exp().detach()

        # --- critics -------------------------------------------------------
        with torch.no_grad():
            # The next action comes from the CURRENT policy, not a frozen target
            # actor (TD3 uses one; SAC does not) -- and it is penalized by its
            # own log-prob, which is what makes this a soft Bellman backup
            # rather than an ordinary one.
            next_actions, next_logp = self.actor.sample(next_obs_t)
            next_sa = torch.cat([next_obs_t, next_actions], dim=-1)
            min_next_q = torch.min(
                self.q1_target(next_sa), self.q2_target(next_sa)
            ).squeeze(-1)
            # Every squeeze(-1) here is load-bearing. The critics emit (B, 1)
            # while rewards and log-probs are (B,), so dropping one lets the
            # target broadcast to (B, B) -- F.mse_loss accepts that with only a
            # warning, and every critic output is then regressed toward the
            # BATCH MEAN. Nothing crashes, the actor loss stays accidentally
            # correct (the mean of an outer difference is the difference of the
            # means), and the policy keeps moving while the critic learns
            # nothing. Measured on Pendulum: -97.6 with the squeeze, -1720 without.
            target = rewards_t + discounts_t * (1.0 - terminated_t) * (
                min_next_q - alpha * next_logp
            )
        sa = torch.cat([obs_t, actions_t], dim=-1)
        q1_pred, q2_pred = self.q1(sa).squeeze(-1), self.q2(sa).squeeze(-1)
        critic_loss = F.mse_loss(q1_pred, target) + F.mse_loss(q2_pred, target)
        self.q_optimizer.zero_grad()
        critic_loss.backward()
        self.q_optimizer.step()

        metrics = {
            "loss/critic": float(critic_loss.item()),
            "loss/q_pred_mean": float(q1_pred.mean().item()),
        }

        # --- actor and temperature, on a delay ------------------------------
        # TD3's trick: let the critics settle for a few steps before chasing
        # them. The inner loop restores the 1:1 actor-to-critic step count,
        # reusing this one minibatch, which is CleanRL's shape rather than the
        # paper's (the paper takes one actor step per env step on a fresh
        # batch). ORDER MATTERS AND IS NOT INCIDENTAL: actor_loss.backward()
        # differentiates through Q1/Q2 and leaves gradients on their
        # parameters. That is harmless only because the critic step above has
        # already run and the next one begins with q_optimizer.zero_grad().
        if self.grad_steps % self.policy_frequency == 0:
            for _ in range(self.policy_frequency):
                pi, logp = self.actor.sample(obs_t)
                sa_pi = torch.cat([obs_t, pi], dim=-1)
                # min over the twins again, and the ONLINE critics this time:
                # the actor should climb the current value estimate, not a
                # lagged one.
                min_q_pi = torch.min(self.q1(sa_pi), self.q2(sa_pi)).squeeze(-1)
                # alpha is detached: the temperature is optimized by its own
                # loss below, not by the actor pushing it down to cheapen the
                # entropy term.
                actor_loss = (alpha * logp - min_q_pi).mean()
                self.actor_optimizer.zero_grad()
                actor_loss.backward()
                self.actor_optimizer.step()

                if self.autotune:
                    # The dual update. Entropy below target (logp too high)
                    # raises alpha, buying more exploration; above target,
                    # alpha falls and the agent is allowed to commit.
                    with torch.no_grad():
                        _, logp_now = self.actor.sample(obs_t)
                    alpha_loss = (
                        -self.log_alpha.exp() * (logp_now + self.target_entropy)
                    ).mean()
                    self.alpha_optimizer.zero_grad()
                    alpha_loss.backward()
                    self.alpha_optimizer.step()
                    alpha = self.log_alpha.exp().detach()
                    metrics["loss/alpha"] = float(alpha_loss.item())

            with torch.no_grad():
                mean_b, log_std_b = self.actor(obs_t)
            metrics.update({
                "loss/actor": float(actor_loss.item()),
                "loss/alpha_value": float(alpha.item()),
                # -log pi, the sampled entropy of the SQUASHED policy. Read it
                # against target_entropy; it is NOT on the same scale as PPO's
                # analytic entropy over an unbounded Gaussian.
                "loss/entropy": float(-logp.mean().item()),
                # Pre-squash scale. Same name as PPO's, deliberately, but a
                # different quantity: state-dependent, over the latent rather
                # than the action, and bounded into (0.0067, 7.39) by
                # construction. Comparable in direction, not in level.
                "loss/policy_std": float(log_std_b.exp().mean().item()),
                # Settles whether the policy actually reaches the saturated
                # regime where the log-prob's stable form earns its keep.
                "loss/mu_absmax": float(mean_b.abs().max().item()),
            })

        if self.grad_steps % self.target_network_frequency == 0:
            polyak_update(self.q1, self.q1_target, self.tau)
            polyak_update(self.q2, self.q2_target, self.tau)
        self.grad_steps += 1
        return metrics

    def state_dict(self) -> dict[str, Any]:
        # Buffer deliberately not checkpointed, as with DQN and PPO: restore
        # serves eval/watch, and resuming training refills it.
        return {
            "actor": self.actor.state_dict(),
            "q1": self.q1.state_dict(),
            "q2": self.q2.state_dict(),
            "q1_target": self.q1_target.state_dict(),
            "q2_target": self.q2_target.state_dict(),
            "q_optimizer": self.q_optimizer.state_dict(),
            "actor_optimizer": self.actor_optimizer.state_dict(),
            "alpha_optimizer": (
                self.alpha_optimizer.state_dict() if self.alpha_optimizer else None
            ),
            "log_alpha": self.log_alpha.detach().clone(),
            "transitions": self.transitions,
            "grad_steps": self.grad_steps,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.actor.load_state_dict(state["actor"])
        self.q1.load_state_dict(state["q1"])
        self.q2.load_state_dict(state["q2"])
        self.q1_target.load_state_dict(state["q1_target"])
        self.q2_target.load_state_dict(state["q2_target"])
        self.q_optimizer.load_state_dict(state["q_optimizer"])
        self.actor_optimizer.load_state_dict(state["actor_optimizer"])
        # copy_ into the existing tensor, NEVER rebind: the alpha optimizer
        # holds a reference to this exact object. Rebinding leaves it happily
        # training a tensor nothing reads while self.log_alpha stays frozen
        # forever -- and an in-memory state_dict round trip cannot see it,
        # because the rebound tensor IS the one that was just saved. Only a
        # torch.save/load round trip exposes it.
        with torch.no_grad():
            self.log_alpha.copy_(state["log_alpha"].to(self.device))
        if self.alpha_optimizer is not None and state.get("alpha_optimizer") is not None:
            self.alpha_optimizer.load_state_dict(state["alpha_optimizer"])
        self.transitions = state["transitions"]
        self.grad_steps = state["grad_steps"]

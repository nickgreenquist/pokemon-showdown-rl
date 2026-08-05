"""PPO (Schulman et al. 2017): the clipped-surrogate policy gradient — the
same score-function core as REINFORCE, rebuilt so one batch of experience
safely buys several gradient steps.

REINFORCE's constraint was structural: the policy gradient is an expectation
under the *current* policy, so each batch funded exactly one update and was
discarded. Two ideas relax that:

- Importance sampling makes reuse legal. Weight each action's term by
  ratio = pi(a|s) / pi_old(a|s) and the surrogate objective ratio * A is,
  in expectation under the *old* (data-collecting) policy, a first-order
  proxy for the new policy's performance — its gradient at ratio = 1 is
  exactly the vanilla policy gradient. Optimizing it on stale data is
  principled while the two policies stay close.
- Clipping makes reuse safe. That "while close" caveat degrades fast: the
  importance weights' variance grows with the policy gap, and A itself was
  estimated under pi_old. So the per-transition objective is

      min(ratio * A,  clip(ratio, 1 - eps, 1 + eps) * A)

  The min is deliberately asymmetric — a trust region built from incentive
  removal rather than a hard constraint. Once the ratio crosses the clip
  range in the direction that *improves* the objective, the clipped term
  wins the min and is constant in the parameters: zero gradient, nothing
  pulls the policy further from pi_old on that transition. A ratio that
  drifted the way that *hurts* keeps its unclipped gradient, so overshoot
  is still corrected. Epochs of minibatch reuse then extract several steps
  per batch, each confined to the neighborhood where the surrogate can be
  trusted.

The other components, each replacing a REINFORCE compromise:

- Critic + GAE (buffers/rollout.py): a learned V(s) baseline replaces
  within-episode return normalization, and lam blends TD and Monte Carlo
  advantage estimates. The critic also bootstraps truncated tails — the
  time-limit bias REINFORCE documented and lived with disappears.
- Entropy bonus: REINFORCE watched entropy as a health metric; PPO pays for
  it, subtracting entropy_coef * H(pi(·|s)) from the loss so the policy
  doesn't go deterministic before learning finishes.
- Vectorized collection: N lockstep envs decorrelate each rollout — the
  on-policy substitute for what replay did in DQN.
- Action masking (rl/common/masking.py): logits are masked before every
  softmax/argmax — at collection, at the update-start recompute, and on
  every epoch's forward, with the mask STORED per rollout row. A mask
  applied only at collection would leave pi_new unmasked while pi_old was
  masked, silently corrupting every importance ratio; the stored-and-
  reapplied mask keeps the two distributions consistent (and an all-True
  mask leaves logits bitwise untouched). Entropy uses the where-guarded
  masked_entropy — Categorical.entropy() over -inf logits is NaN. The
  critic is never masked: V(s) is a property of the state, not the
  action set.

Box action spaces select a diagonal Gaussian policy (see GaussianActor)
instead of a Categorical, by the same no-config-key rule the obs rank uses.
That is the entire algorithmic difference between the two tracks: GAE, the
clipped surrogate, the epoch/minibatch loop, the advantage normalization and
the grad clip are shared verbatim, because PPO's objective is written over
log-probabilities and never cares which distribution produced them. What
changes around it is the env stack — unbounded continuous observations and
returns need normalizing (rl/envs/normalize.py), where MinAtar's binary
planes and 0/1 rewards did not.

Rank-3 observations (MinAtar's binary planes) select a conv trunk instead
of the MLP, by the same no-config-key rule DQN uses. Both heads get their
own `ConvQNet` — the DQN campaign's exact architecture, so the discrete
track's DQN-vs-PPO headline holds the net fixed and varies only the
algorithm. Note this *departs* from the conv-PPO lineage: CleanRL, ppo2 and
SB3 all share one trunk between the heads. Separate stacks follow PureJaxRL,
keep the value_coef/value-clip reasoning below intact, and cost noise-level
duplicate compute at 16 filters.

Deliberately omitted (locked 2026-07-25 after review, see PLAN.md):

- Value-loss clipping: Engstrom et al. 2020 found no evidence it helps and
  Andrychowicz et al. 2021 found it can hurt. The omission rests on that
  ablation evidence alone — *not* on the separate-nets argument, since
  PureJaxRL ships value clipping with separate nets.
- Reward/return normalization: an omitted knob with positive ablation
  evidence (Engstrom et al. 2020 found it significant, alongside Adam lr
  annealing and orthogonal init), scoped out so PPO and DQN consume an
  identical reward stream on MinAtar.
- Observation normalization: MinAtar planes are already binary 0/1; the
  37-details item targets unbounded continuous observations.

Both normalization omissions are scoped to the DISCRETE track and are lifted
on the continuous one, where the configs turn them on: MuJoCo observations
are unbounded and its returns grow with the policy. They live in the env
stack (rl/envs/normalize.py), not in here, so Phase 3's SAC comparison can
hold them fixed.

Note on value_coef: with disjoint actor/critic parameters and Adam, scaling
the value loss barely changes the critic's own updates (Adam renormalizes
per-parameter step sizes); its remaining effect is modulating the critic's
share of the single shared gradient-norm clip. A persistently underfitting
critic wants its own optimizer, not a bigger coefficient.
"""

import math
from collections import defaultdict
from typing import Any

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.distributions import Categorical, Normal

from rl.agents.base import Agent
from rl.buffers.rollout import RolloutBuffer, compute_gae
from rl.common.masking import masked_entropy, masked_logits
from rl.networks.conv import ConvQNet
from rl.networks.mlp import mlp


def clipped_surrogate_loss(
    new_logp: torch.Tensor,
    old_logp: torch.Tensor,
    advantages: torch.Tensor,
    clip_eps: float,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """The per-minibatch policy loss plus its two health diagnostics.

    Returns (policy_loss, approx_kl, clip_frac):
    - policy_loss = -mean(min(ratio * A, clip(ratio, 1-eps, 1+eps) * A))
      with ratio = exp(new_logp - old_logp);
    - approx_kl: the low-variance KL(pi_old || pi) estimator
      mean((ratio - 1) - log ratio);
    - clip_frac: fraction of transitions with |ratio - 1| > eps.

    approx_kl and clip_frac are the collapse-vs-bad-hyperparameter
    discriminators: healthy runs sit around approx_kl <= ~1e-2 and
    clip_frac ~0.1-0.3 (near 0 means the lr never reaches the clip, high
    means it blasts through it). Diagnostics are detached; only the loss
    carries gradient.
    """
    logratio = new_logp - old_logp
    ratio = logratio.exp()
    clipped = torch.clamp(ratio, 1.0 - clip_eps, 1.0 + clip_eps)
    policy_loss = -torch.min(ratio * advantages, clipped * advantages).mean()
    with torch.no_grad():
        approx_kl = ((ratio - 1.0) - logratio).mean()
        clip_frac = ((ratio - 1.0).abs() > clip_eps).float().mean()
    return policy_loss, approx_kl, clip_frac


def _orthogonal_init(net: nn.Module, head_gain: float) -> None:
    """Orthogonal init (a 37-details item, values matching CleanRL's
    `layer_init`): gain sqrt(2) on conv and hidden layers, a task-specific
    gain on the head, zero biases. The 0.01 policy-head gain makes the
    initial policy near-uniform — early exploration comes from sampling a
    flat distribution, not from init noise.

    Iterates `net.modules()` rather than the module itself: ConvQNet is not a
    Sequential, so `for m in net` raises TypeError. Module order puts the
    head last for both nets — which is also why ConvQNet's dueling flag must
    stay off here: with dueling the last Linear in module order is
    `advantage`, so `value` would silently take the head gain.
    """
    layers = [m for m in net.modules() if isinstance(m, (nn.Linear, nn.Conv2d))]
    for layer in layers:
        gain = head_gain if layer is layers[-1] else math.sqrt(2.0)
        nn.init.orthogonal_(layer.weight, gain=gain)
        nn.init.zeros_(layer.bias)


class GaussianActor(nn.Module):
    """Diagonal Gaussian policy for Box action spaces: an MLP mean, plus a
    state-INDEPENDENT log standard deviation.

    The scale is a bare parameter rather than a second network head, and that
    choice is load-bearing for Phase 3 rather than incidental. A
    state-dependent scale head is exactly what SAC uses (where it also needs
    the tanh log-det-Jacobian correction), so adopting one here would make
    the PPO-vs-SAC comparison differ in more than the algorithm — the same
    hold-everything-fixed discipline that made the discrete headline clean.
    It is also the reference choice (CleanRL, SB3), and Andrychowicz et al.
    2021 found no clear benefit either way.

    log_std init 0 (std 1) follows the CleanRL recipe. Note the published
    evidence mildly favours std 0.5: that is the pre-registered first probe
    lever if MuJoCo curves stall, not a silent default change.

    Deliberately unsquashed: actions are sampled from an unbounded Normal and
    clipped to the action space by the env wrapper, while the log-prob is
    always taken of the RAW sample. Squashing with tanh is SAC's machinery.
    """

    def __init__(self, mean_net: nn.Module, act_dim: int):
        super().__init__()
        self.mean = mean_net
        self.log_std = nn.Parameter(torch.zeros(act_dim))

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        mean = self.mean(obs)
        return mean, self.log_std.exp().expand_as(mean)


class PPOAgent(Agent):
    vectorized = True

    def __init__(
        self,
        observation_space: gym.Space,
        action_space: gym.Space,
        num_envs: int,
        device: str,
        lr: float,
        gamma: float,
        gae_lambda: float,
        rollout_steps: int,
        epochs: int,
        minibatches: int,
        clip_eps: float,
        entropy_coef: float,
        value_coef: float,
        max_grad_norm: float,
        hidden_sizes: list[int],
        lr_anneal_steps: int = 0,
        kernel_size: int = 3,
    ):
        # A flat obs vector or channel-first image planes, same rule as DQN.
        if not isinstance(observation_space, gym.spaces.Box) or len(observation_space.shape) not in (1, 3):
            raise TypeError("PPOAgent requires a flat or channel-first image Box observation space")
        # Action-space type picks the policy distribution, fixed here at
        # construction — algorithm code below branches on `self.continuous`
        # and never on a runtime value, so the discrete path stays
        # unconditionally masked (see rl/common/masking.py).
        if isinstance(action_space, gym.spaces.Box):
            if len(action_space.shape) != 1:
                raise TypeError("continuous PPOAgent requires a flat Box action space")
            self.continuous = True
        elif isinstance(action_space, gym.spaces.Discrete):
            self.continuous = False
        else:
            raise TypeError("PPOAgent requires a Discrete or flat Box action space")
        if self.continuous and len(observation_space.shape) != 1:
            raise TypeError("continuous PPOAgent requires a flat observation space")
        self.device = torch.device(device)
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.epochs = epochs
        self.minibatches = minibatches
        self.clip_eps = clip_eps
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        # act() distinguishes a single obs from a batched one by rank, so the
        # env's own obs rank has to be remembered.
        self.obs_rank = len(observation_space.shape)
        self.base_lr = lr
        self.lr_anneal_steps = lr_anneal_steps
        # Separate actor and critic, no shared trunk: the value_coef note in
        # the module docstring is premised on it.
        if self.obs_rank == 3:
            # Rank-3 obs (MinAtar planes) select the conv net — DQN's rule, no
            # config key. ConvQNet hardcodes ReLU, which is what every conv-PPO
            # reference uses; dueling stays off (see _orthogonal_init).
            # kernel_size default 3 is the value every existing config ran;
            # 4 is Phase 4's pre-registered receptive-field probe arm.
            def build(out_dim: int) -> nn.Module:
                return ConvQNet(
                    observation_space.shape, hidden_sizes, out_dim, kernel_size=kernel_size
                )
        else:
            # Tanh hiddens: the feedforward-PPO reference default the numeric
            # hyperparameters were validated under.
            def build(out_dim: int) -> nn.Module:
                return mlp(observation_space.shape[0], hidden_sizes, out_dim, activation=nn.Tanh)

        if self.continuous:
            # The mean trunk is the same `build` the discrete head uses, so
            # architecture, activation and init are shared; GaussianActor only
            # adds the scale parameter. _orthogonal_init still sees the mean
            # head as the last Linear in module order (log_std is a Parameter,
            # not a module, so the Linear/Conv2d filter skips it) and the
            # 0.01 head gain lands where it should.
            act_dim = int(action_space.shape[0])
            self.actor = GaussianActor(build(act_dim), act_dim)
        else:
            self.actor = build(int(action_space.n))
        self.critic = build(1)
        _orthogonal_init(self.actor, head_gain=0.01)
        _orthogonal_init(self.critic, head_gain=1.0)
        self.actor.to(self.device)
        self.critic.to(self.device)
        # One Adam over the union of both nets' params; eps=1e-5 is the
        # canonical PPO detail (shipped by every reference implementation).
        self.params = [*self.actor.parameters(), *self.critic.parameters()]
        self.optimizer = torch.optim.Adam(self.params, lr=lr, eps=1e-5)
        action_storage = (
            {"action_shape": (act_dim,), "action_dtype": np.float32} if self.continuous
            else {"action_shape": (), "action_dtype": np.int64, "n_actions": int(action_space.n)}
        )
        self.buffer = RolloutBuffer(
            rollout_steps,
            num_envs,
            observation_space.shape,
            obs_dtype=observation_space.dtype,
            **action_storage,
        )
        self.updates = 0  # completed fill -> epochs cycles

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> Any:
        # float32 at tensor time (MinAtar obs are bool planes); branch on obs
        # rank, then batch the single path: collection hands (N, *obs_shape),
        # eval/watch/record hand a bare (*obs_shape,). The single obs still
        # needs a batch dim before the forward — Conv2d requires one, and
        # without it Flatten would eat the channel dim — so this is a branch,
        # not an unconditional unsqueeze. The (A,) mask broadcasts over the
        # (1, A) logits fine.
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        single = obs_t.ndim == self.obs_rank
        if single:
            obs_t = obs_t.unsqueeze(0)
        if self.continuous:
            # Before any mask handling: Box envs carry no mask at all, and
            # torch.as_tensor(None) raises.
            with torch.no_grad():
                mean, std = self.actor(obs_t)
                # The mode of a Gaussian is its mean — the eval-time policy.
                # Unbounded on purpose: the env's ClipAction wrapper bounds
                # what the simulator sees, while what the policy DREW is what
                # gets stored and log-prob'd.
                actions = mean if deterministic else Normal(mean, std).sample()
            out = actions.cpu().numpy()
            return out[0] if single else out  # (act_dim,) or (N, act_dim)
        mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=self.device)
        with torch.no_grad():
            logits = masked_logits(self.actor(obs_t), mask_t)
        if deterministic:
            actions = logits.argmax(dim=-1)  # eval-time policy: the mode
        else:
            actions = Categorical(logits=logits).sample()
        if single:
            return int(actions.item())  # (1,) -> the scalar the scalar loop wants
        return actions.cpu().numpy()

    def _logp_entropy(
        self, obs: torch.Tensor, actions: torch.Tensor, masks: torch.Tensor | None
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """log pi(a|s) and H(pi(.|s)) for a batch, both shaped (B,).

        The one place the two action spaces fork during optimization, so the
        surrogate, the recompute and the entropy bonus cannot drift apart.
        A diagonal Gaussian's components are independent, so its joint
        log-prob and entropy are sums over the action dimensions — the sum
        that turns (B, act_dim) into the (B,) the surrogate needs.
        """
        if self.continuous:
            dist = Normal(*self.actor(obs))
            return dist.log_prob(actions).sum(-1), dist.entropy().sum(-1)
        logits = self.actor(obs)
        dist = Categorical(logits=masked_logits(logits, masks))
        return dist.log_prob(actions), masked_entropy(logits, masks)

    def update(self, batch: Any) -> dict[str, float]:
        # The vector loop hands one batched (N-wide) transition row per env
        # step; accumulate until the horizon fills, then train on the rollout.
        # next_masks has no consumer: the critic is the only next_obs reader,
        # and values are never masked.
        obs, actions, rewards, next_obs, terminated, truncated, masks, _next_masks = batch
        self.buffer.add(obs, actions, rewards, next_obs, terminated, truncated, masks)
        if not self.buffer.full():
            return {}
        buf = self.buffer
        horizon, num_envs = buf.horizon, buf.num_envs

        # Flatten the leading (T, N) into one batch dim up front. The epoch
        # loop needs it anyway, and the recompute below *requires* it: buffer
        # obs are (T, N, *obs_shape), which for image planes is rank 5, and
        # conv2d rejects that outright. Only GAE wants the (T, N) shape back.
        flat_obs = torch.as_tensor(buf.obs, dtype=torch.float32, device=self.device).flatten(0, 1)
        flat_next_obs = torch.as_tensor(
            buf.next_obs, dtype=torch.float32, device=self.device
        ).flatten(0, 1)
        # flatten(0, 1), never reshape(-1): discrete actions are (T, N) and
        # both spellings agree, but continuous actions are (T, N, act_dim) and
        # reshape(-1) would silently collapse them to 1-D. Normal.log_prob
        # then broadcasts that vector against the (T*N, act_dim) mean — at
        # act_dim 1 into a square matrix whose .sum(-1) is correctly shaped
        # garbage, so a Pendulum-only test suite would never notice.
        flat_actions = torch.as_tensor(buf.actions, device=self.device).flatten(0, 1)
        flat_masks = (
            None if self.continuous
            else torch.as_tensor(buf.masks, device=self.device).flatten(0, 1)  # (T*N, A) bool
        )
        with torch.no_grad():
            # Recomputed at update start, not stored during collection: exact
            # (the policy hasn't changed since it acted — same argument as
            # REINFORCE's batched recompute), and next_obs gets its own pass
            # because every buffer row carries its own successor. old_logp is
            # recomputed under the STORED masks — the same masking every
            # epoch's forward applies below, so the first ratio is exactly 1.
            values = self.critic(flat_obs).squeeze(-1).view(horizon, num_envs)
            next_values = self.critic(flat_next_obs).squeeze(-1).view(horizon, num_envs)
            old_logp = self._logp_entropy(flat_obs, flat_actions, flat_masks)[0].view(
                horizon, num_envs
            )
        advantages_t = torch.as_tensor(
            compute_gae(
                buf.rewards,
                buf.terminated,
                buf.truncated,
                values.cpu().numpy(),
                next_values.cpu().numpy(),
                self.gamma,
                self.gae_lambda,
            ),
            device=self.device,
        )
        # The critic's regression targets: GAE-consistent returns. Back to
        # flat for the minibatch loop, which reshuffles at the transition
        # level each epoch so minibatches mix envs and timesteps.
        flat_targets = (advantages_t + values).reshape(-1)
        flat_advantages = advantages_t.reshape(-1)
        flat_old_logp = old_logp.reshape(-1)

        # Linear lr anneal, off at lr_anneal_steps=0 (CartPole's constant lr).
        # Andrychowicz et al. 2021 report it pays at benchmark scale, which is
        # why it arrives with the MinAtar configs and not before. Keyed off the
        # update counter — which is checkpointed — so a resumed run picks the
        # schedule back up, and an eval-only restore never touches it. One
        # param group: the single Adam over the actor+critic union.
        if self.lr_anneal_steps:
            steps_seen = self.updates * horizon * num_envs
            frac = max(0.0, 1.0 - steps_seen / self.lr_anneal_steps)
            self.optimizer.param_groups[0]["lr"] = self.base_lr * frac

        batch_size = flat_actions.shape[0]
        minibatch_size = batch_size // self.minibatches
        sums: dict[str, float] = defaultdict(float)
        grad_steps = 0
        for _ in range(self.epochs):
            perm = torch.randperm(batch_size, device=self.device)
            for start in range(0, batch_size, minibatch_size):
                idx = perm[start : start + minibatch_size]
                # Per-minibatch advantage normalization; the 1e-8 keeps a
                # zero-variance minibatch at zero instead of NaN.
                mb_adv = flat_advantages[idx]
                mb_adv = (mb_adv - mb_adv.mean()) / (mb_adv.std() + 1e-8)
                # Every epoch reapplies the stored mask: pi_new must be masked
                # exactly like the pi_old above, or the ratio is silently
                # wrong (all-True leaves the logits bitwise untouched).
                new_logp, entropies = self._logp_entropy(
                    flat_obs[idx], flat_actions[idx],
                    None if self.continuous else flat_masks[idx],
                )
                policy_loss, approx_kl, clip_frac = clipped_surrogate_loss(
                    new_logp, flat_old_logp[idx], mb_adv, self.clip_eps
                )
                value_loss = F.mse_loss(self.critic(flat_obs[idx]).squeeze(-1), flat_targets[idx])
                entropy = entropies.mean()
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy

                self.optimizer.zero_grad()
                loss.backward()
                # One clip over the actor+critic union — separate calls would
                # hand each net the full norm budget.
                nn.utils.clip_grad_norm_(self.params, self.max_grad_norm)
                self.optimizer.step()

                sums["loss/policy"] += float(policy_loss.item())
                sums["loss/value"] += float(value_loss.item())
                sums["loss/entropy"] += float(entropy.item())
                sums["loss/approx_kl"] += float(approx_kl.item())
                sums["loss/clip_frac"] += float(clip_frac.item())
                if self.continuous:
                    # The exploration readout on this track: with a free
                    # log_std the entropy bonus is off (ent_coef 0 on MuJoCo),
                    # so the scale is what exploration actually rides on, and
                    # an early collapse toward 0 is the failure signature.
                    sums["loss/policy_std"] += float(self.actor.log_std.exp().mean().item())
                grad_steps += 1

        self.buffer.clear()
        self.updates += 1
        return {name: total / grad_steps for name, total in sums.items()}

    def state_dict(self) -> dict[str, Any]:
        # The rollout in progress is deliberately not checkpointed: restore
        # serves eval/watch; resuming training refills the buffer.
        return {
            "actor": self.actor.state_dict(),
            "critic": self.critic.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "updates": self.updates,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.actor.load_state_dict(state["actor"])
        self.critic.load_state_dict(state["critic"])
        self.optimizer.load_state_dict(state["optimizer"])
        # torch's Optimizer.load_state_dict restores the CHECKPOINT's
        # param-group hyperparameters, lr included — and a constant-lr config
        # never rewrites lr after construction (the anneal branch in update()
        # is gated on lr_anneal_steps). A warm start from an annealed
        # checkpoint would otherwise train at the donor's final lr (~0 after
        # a full anneal) silently, forever. The constructing config wins on
        # lr; the checkpoint supplies optimizer STATE (moments), not
        # hyperparameters. Annealed resumes are unaffected: update()
        # recomputes lr from the restored counter before every step.
        self.optimizer.param_groups[0]["lr"] = self.base_lr
        self.updates = state["updates"]

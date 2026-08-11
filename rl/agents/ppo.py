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

import copy
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
        critic_warmup_updates: int = 0,
        actor_lr_scale: float = 1.0,
        bc_kl_coef: float = 0.0,
        trunk: str = "mlp",
        trunk_kwargs: dict | None = None,
        privileged_dim: int = 0,
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
        # Staged unfreeze, for warm starts from a checkpoint whose critic is
        # untrained — a behaviour-cloned policy is the case that matters (a BC
        # clone has no critic at all). Naive PPO from there computes every
        # advantage off a random value head and destroys the cloned policy in
        # the first updates, which measures a broken handoff and not the
        # policy. Both default to the no-op, so every pre-existing config
        # trains exactly as before.
        #   critic_warmup_updates: the actor is FROZEN for this many updates
        #     while the critic regresses onto the cloned policy's returns.
        #   actor_lr_scale: after unfreeze, the actor's lr is this multiple of
        #     the critic's — ps-ppo's "reduced backbone LR" idea, which maps
        #     to the whole actor here because the two heads share no trunk.
        #     Their specific multipliers are dead code at their HEAD and were
        #     never ablated, so the constant is ours to choose.
        if critic_warmup_updates < 0:
            raise ValueError(f"critic_warmup_updates must be >= 0, got {critic_warmup_updates}")
        if actor_lr_scale <= 0.0:
            raise ValueError(f"actor_lr_scale must be > 0, got {actor_lr_scale}")
        self.critic_warmup_updates = critic_warmup_updates
        self.actor_lr_scale = actor_lr_scale
        # KL-to-BC anchor (2026-08-06 direction audit): once the actor
        # unfreezes, nothing else holds a warm-started policy near the clone
        # it started from — the measured signature is `loss/entropy` 0.063
        # from update 1 and drift off the teacher while vs-SH climbs. With
        # bc_kl_coef > 0, `begin_warm_start()` snapshots the just-loaded
        # actor as a frozen anchor and update() adds
        # bc_kl_coef * KL(pi_new || pi_anchor) per minibatch (forward KL, so
        # the penalty is heaviest where the policy invents probability the
        # anchor never had). Discrete-only: the anchor distribution is the
        # masked categorical. Default 0.0 = the no-op, every existing config
        # unchanged.
        if bc_kl_coef < 0.0:
            raise ValueError(f"bc_kl_coef must be >= 0, got {bc_kl_coef}")
        if bc_kl_coef > 0.0 and self.continuous:
            raise TypeError("bc_kl_coef requires a discrete action space")
        self.bc_kl_coef = bc_kl_coef
        self._bc_anchor: "nn.Module | None" = None
        # Trunk seam (ARCH_SCREEN_SPEC / Rung 2): default "mlp" is the
        # historical path, bit-identical in construction order and RNG
        # consumption (regression-tested against pre-seam goldens). The
        # entity trunk is discrete/flat-obs only — the conv rule and the
        # Gaussian track keep their existing shapes.
        if trunk not in ("mlp", "entity_deepsets"):
            raise ValueError(f"unknown trunk {trunk!r}; expected 'mlp' or 'entity_deepsets'")
        if trunk != "mlp" and (self.obs_rank == 3 or self.continuous):
            raise TypeError(f"trunk {trunk!r} requires a flat obs and a Discrete action space")
        self.trunk = trunk
        # D18 privileged critic: the CRITIC's input is obs ‖ the env's
        # info["privileged"] block; the actor never widens and the obs space
        # is untouched. Discrete/flat only — the tracks that have an env
        # emitting the block.
        if privileged_dim < 0:
            raise ValueError(f"privileged_dim must be >= 0, got {privileged_dim}")
        if privileged_dim and (self.obs_rank == 3 or self.continuous):
            raise TypeError("privileged_dim requires a flat obs and a Discrete action space")
        self.privileged_dim = privileged_dim
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
        elif trunk == "entity_deepsets":
            # Deferred import: only entity-trunk construction pays for the
            # poke_env import chain behind the tokenizer's layout asserts.
            from rl.networks.entity_deepsets import EntityDeepSetsNet

            def build(out_dim: int) -> nn.Module:
                return EntityDeepSetsNet(
                    observation_space.shape[0], out_dim, **(trunk_kwargs or {})
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
        if not privileged_dim:
            self.critic = build(1)
        elif trunk == "entity_deepsets":
            from rl.networks.entity_deepsets import EntityDeepSetsNet

            self.critic = EntityDeepSetsNet(
                observation_space.shape[0], 1,
                privileged_dim=privileged_dim, **(trunk_kwargs or {}),
            )
        else:
            # MLP critic: plain input concat — the widened first layer is the
            # whole change.
            self.critic = mlp(
                observation_space.shape[0] + privileged_dim, hidden_sizes, 1,
                activation=nn.Tanh,
            )
        if trunk == "entity_deepsets":
            # INIT HAZARD (K4): _orthogonal_init iterates every Linear and
            # would rescale the pointer stack while leaving the embedding
            # tables at torch's default N(0,1) — the net owns its init
            # (Xavier + std-0.02 embeddings + rescaled final layer), with
            # the same head gains as the orthogonal path.
            self.actor.init_head(0.01)
            self.critic.init_head(1.0)
        else:
            _orthogonal_init(self.actor, head_gain=0.01)
            _orthogonal_init(self.critic, head_gain=1.0)
        self.actor.to(self.device)
        self.critic.to(self.device)
        # One Adam over the union of both nets' params; eps=1e-5 is the
        # canonical PPO detail (shipped by every reference implementation).
        # Split into two PARAM GROUPS — actor first, critic second, which is
        # the flat order `self.params` and every existing checkpoint already
        # use — so `actor_lr_scale` has somewhere to live. At the default
        # scale of 1.0 the two groups carry identical hyperparameters and
        # Adam's per-tensor arithmetic is unchanged, so the split is
        # bit-for-bit a no-op on every existing recipe (regression-tested).
        self.actor_params = list(self.actor.parameters())
        self.critic_params = list(self.critic.parameters())
        self.params = [*self.actor_params, *self.critic_params]
        self.optimizer = torch.optim.Adam(
            [
                {"params": self.actor_params, "lr": lr * actor_lr_scale},
                {"params": self.critic_params, "lr": lr},
            ],
            eps=1e-5,
        )
        self._set_actor_trainable(critic_warmup_updates == 0)
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
            priv_dim=privileged_dim or None,
        )
        self.updates = 0  # completed fill -> epochs cycles

    def _set_actor_trainable(self, trainable: bool) -> None:
        """The staged unfreeze's switch. requires_grad=False is a TRUE freeze:
        backward never populates those grads, and Adam skips any param whose
        grad is None. Zeroing the gradients instead would not freeze anything
        — Adam's existing moments keep walking the weights on a zero grad."""
        for param in self.actor_params:
            param.requires_grad_(trainable)

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
        (obs, actions, rewards, next_obs, terminated, truncated, masks, _next_masks,
         *rest) = batch
        privs, next_privs = rest if rest else (None, None)
        # Loud seam (R0-1 style): a lane with the env flag but not the agent
        # flag would silently train a blind critic; the reverse would train
        # the wide critic on zeros. Neither may pass.
        if (privs is None) == bool(self.privileged_dim):
            raise ValueError(
                f"privileged mismatch: agent privileged_dim={self.privileged_dim} "
                f"but the env {'did not emit' if privs is None else 'emitted'} "
                "info['privileged'] — the env kwarg and the agent hparam must "
                "be set together"
            )
        self.buffer.add(
            obs, actions, rewards, next_obs, terminated, truncated, masks,
            privs, next_privs,
        )
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
        # The critic's input: obs ‖ privileged when the block is carried,
        # plain obs otherwise (aliases, no copy). Every critic forward below
        # reads these two and only these two.
        if self.privileged_dim:
            flat_critic_obs = torch.cat(
                [flat_obs, torch.as_tensor(
                    buf.privs, dtype=torch.float32, device=self.device
                ).flatten(0, 1)],
                dim=-1,
            )
            flat_critic_next_obs = torch.cat(
                [flat_next_obs, torch.as_tensor(
                    buf.next_privs, dtype=torch.float32, device=self.device
                ).flatten(0, 1)],
                dim=-1,
            )
        else:
            flat_critic_obs, flat_critic_next_obs = flat_obs, flat_next_obs
        with torch.no_grad():
            # Recomputed at update start, not stored during collection: exact
            # (the policy hasn't changed since it acted — same argument as
            # REINFORCE's batched recompute), and next_obs gets its own pass
            # because every buffer row carries its own successor. old_logp is
            # recomputed under the STORED masks — the same masking every
            # epoch's forward applies below, so the first ratio is exactly 1.
            values = self.critic(flat_critic_obs).squeeze(-1).view(horizon, num_envs)
            next_values = self.critic(flat_critic_next_obs).squeeze(-1).view(horizon, num_envs)
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

        # Mechanism diagnostics, computed ONCE per update on the whole batch
        # (DESIGN.md §5: without them a null result cannot distinguish "the
        # lever did nothing" from "the lever never changed the learning
        # signal"). Both read PRE-update quantities — the critic's fit and the
        # advantage scale the epochs below are about to consume.
        with torch.no_grad():
            # explained variance = 1 - Var(target - V) / Var(target), the
            # standard CleanRL/SB3 critic-quality read: 0 means the critic is
            # no better than predicting the batch mean, 1 means it explains
            # the returns exactly, negative means actively worse than the
            # mean. The residual target - V IS the advantage here
            # (flat_targets = advantages + values), so no second pass.
            target_var = flat_targets.var(unbiased=False)
            # Population variance, not sample — the batch is the population.
            # A degenerate batch (every target identical) leaves the ratio
            # undefined; report 0.0 rather than a NaN that would poison the
            # logger's history and every downstream mean.
            explained_variance = (
                0.0
                if float(target_var) < 1e-12
                else float(1.0 - flat_advantages.var(unbiased=False) / target_var)
            )
            # PRE-normalization advantage std: the minibatch loop z-scores
            # advantages, which makes the surrogate blind to the signal's
            # scale, so this is the only place a shaping term's effect on
            # advantage magnitude is visible at all.
            adv_std = float(flat_advantages.std(unbiased=False))

        # Staged unfreeze (no-op unless critic_warmup_updates > 0): the actor
        # is frozen for the first N updates while the critic regresses onto
        # the loaded policy's returns. The loss below keeps its policy and
        # entropy terms rather than branching — with a frozen actor the ratio
        # is identically 1, so both terms are constants that contribute no
        # gradient, and their diagnostics stay readable: approx_kl and
        # clip_frac pinned at exactly 0 are the visible signature of a warmup
        # update, and loss/grad_norm reads the critic alone (clip_grad_norm_
        # skips params with no grad).
        self._set_actor_trainable(self.updates >= self.critic_warmup_updates)

        # Linear lr anneal, off at lr_anneal_steps=0 (CartPole's constant lr).
        # Andrychowicz et al. 2021 report it pays at benchmark scale, which is
        # why it arrives with the MinAtar configs and not before. Keyed off the
        # update counter — which is checkpointed — so a resumed run picks the
        # schedule back up, and an eval-only restore never touches it. Both
        # param groups are rewritten from base_lr each time (group 0 actor,
        # group 1 critic): reading each group's own lr back and scaling it
        # would compound the fraction every update.
        if self.lr_anneal_steps:
            steps_seen = self.updates * horizon * num_envs
            frac = max(0.0, 1.0 - steps_seen / self.lr_anneal_steps)
            self.optimizer.param_groups[0]["lr"] = self.base_lr * self.actor_lr_scale * frac
            self.optimizer.param_groups[1]["lr"] = self.base_lr * frac

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
                value_loss = F.mse_loss(
                    self.critic(flat_critic_obs[idx]).squeeze(-1), flat_targets[idx]
                )
                entropy = entropies.mean()
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
                if self.bc_kl_coef > 0.0:
                    if self._bc_anchor is None:
                        raise RuntimeError(
                            "bc_kl_coef > 0 but no anchor is set: the anchor is "
                            "captured by begin_warm_start(), so bc_kl_coef "
                            "requires init_from"
                        )
                    # Forward KL(pi_new || pi_anchor) over the SAME stored
                    # mask both sides — the finite -1e8 sentinel keeps every
                    # illegal entry's contribution an exact 0 * bounded = 0.
                    # Costs one extra actor forward per minibatch; the loop
                    # is ~95% collect, so this is noise.
                    with torch.no_grad():
                        anchor_logp = F.log_softmax(
                            masked_logits(self._bc_anchor(flat_obs[idx]), flat_masks[idx]),
                            dim=-1,
                        )
                    cur_logp = F.log_softmax(
                        masked_logits(self.actor(flat_obs[idx]), flat_masks[idx]),
                        dim=-1,
                    )
                    bc_kl = (cur_logp.exp() * (cur_logp - anchor_logp)).sum(-1).mean()
                    loss = loss + self.bc_kl_coef * bc_kl
                    sums["loss/bc_kl"] += float(bc_kl.item())

                self.optimizer.zero_grad()
                loss.backward()
                # One clip over the actor+critic union — separate calls would
                # hand each net the full norm budget. The return value is the
                # total norm BEFORE clipping, which is the diagnostic: paired
                # with the fraction of minibatches that exceed max_grad_norm
                # it says whether the clip is a rare safety net or a
                # permanent lr divisor (the 2026-08-05 PPO audit saw it bind
                # 16/16 on synthetic data and could not tell which).
                grad_norm = nn.utils.clip_grad_norm_(self.params, self.max_grad_norm)
                self.optimizer.step()

                sums["loss/policy"] += float(policy_loss.item())
                sums["loss/value"] += float(value_loss.item())
                sums["loss/entropy"] += float(entropy.item())
                sums["loss/approx_kl"] += float(approx_kl.item())
                sums["loss/clip_frac"] += float(clip_frac.item())
                sums["loss/grad_norm"] += float(grad_norm.item())
                sums["loss/grad_clip_frac"] += float(grad_norm.item() > self.max_grad_norm)
                if self.continuous:
                    # The exploration readout on this track: with a free
                    # log_std the entropy bonus is off (ent_coef 0 on MuJoCo),
                    # so the scale is what exploration actually rides on, and
                    # an early collapse toward 0 is the failure signature.
                    sums["loss/policy_std"] += float(self.actor.log_std.exp().mean().item())
                grad_steps += 1

        self.buffer.clear()
        self.updates += 1
        # sums are per-grad-step and averaged; the two batch-level reads are
        # already single numbers for this update and must not be divided.
        return {
            **{name: total / grad_steps for name, total in sums.items()},
            "loss/explained_variance": explained_variance,
            "loss/adv_std": adv_std,
        }

    def state_dict(self) -> dict[str, Any]:
        # The rollout in progress is deliberately not checkpointed: restore
        # serves eval/watch; resuming training refills the buffer. The BC
        # anchor rides along when set so a resumed warm-started run keeps
        # its penalty target (update() raises if it were silently lost).
        state = {
            "actor": self.actor.state_dict(),
            "critic": self.critic.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "updates": self.updates,
        }
        if self._bc_anchor is not None:
            state["bc_anchor"] = self._bc_anchor.state_dict()
        return state

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.actor.load_state_dict(state["actor"])
        self.critic.load_state_dict(state["critic"])
        # Optimizer MOMENTS are restored onto THIS agent's param groups, and
        # the checkpoint's own group records are discarded. Two reasons, both
        # of which have already cost a bug:
        #
        # - Hyperparameters. torch's Optimizer.load_state_dict restores the
        #   CHECKPOINT's param-group hyperparameters, lr included, and a
        #   constant-lr config never rewrites lr after construction (the
        #   anneal branch in update() is gated on lr_anneal_steps). A warm
        #   start from an annealed checkpoint would otherwise train at the
        #   donor's final lr (~0 after a full anneal) silently, forever. The
        #   constructing config wins on lr; the checkpoint supplies state.
        # - Grouping. Checkpoints written before the actor/critic param-group
        #   split carry ONE group, and torch refuses a state dict whose group
        #   count differs — that would have invalidated every stored P4/P5/P6
        #   final. The `state` keys are positional indices over the groups'
        #   params flattened in order, and that order (actor then critic) is
        #   identical either way, so grafting the moments onto our own groups
        #   is exact, not an approximation.
        #
        # Annealed resumes are unaffected: update() recomputes both groups'
        # lr from the restored counter before every step.
        self.optimizer.load_state_dict(
            {
                "state": state["optimizer"]["state"],
                "param_groups": self.optimizer.state_dict()["param_groups"],
            }
        )
        self.updates = state["updates"]
        # Restore a persisted BC anchor (absent from every pre-2026-08-06
        # checkpoint; .get keeps them loadable).
        anchor_state = state.get("bc_anchor")
        if anchor_state is not None:
            self._install_bc_anchor(anchor_state)

    def begin_warm_start(self) -> None:
        """`init_from` semantics, settled 2026-08-05: a warm start is a FRESH
        run, not a resume. Only the update counter carries a schedule, and
        leaving it at the donor's value is what made `init_from` +
        `lr_anneal_steps` illegal (train.py used to refuse the combination):
        at a 12M checkpoint's count the anneal fraction clamps to 0 and the
        whole run trains at lr = 0 — no crash, no metric that looks wrong,
        just a frozen policy. Rewinding it here makes the anneal cover the
        new run's own budget, and re-arms the critic-only warmup from update
        0, which is the point of warm-starting an untrained critic.

        Weights and Adam moments deliberately survive: they ARE the warm
        start. With bc_kl_coef > 0 this is also where the KL anchor is
        captured: the just-loaded actor, frozen — the policy the penalty
        holds the run near."""
        self.updates = 0
        self._set_actor_trainable(self.critic_warmup_updates == 0)
        if self.bc_kl_coef > 0.0:
            self._install_bc_anchor(self.actor.state_dict())

    def _install_bc_anchor(self, actor_state: dict[str, Any]) -> None:
        anchor = copy.deepcopy(self.actor)
        anchor.load_state_dict(actor_state)
        anchor.eval()
        for param in anchor.parameters():
            param.requires_grad_(False)
        self._bc_anchor = anchor

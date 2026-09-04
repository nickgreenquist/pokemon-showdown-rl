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

The continuous track (Box action spaces -> a diagonal Gaussian policy) was
RETIRED 2026-08-29 (CLEANUP A3, maintainer-ruled): Arm C is PARKED, no config
here could run it, and its dead branch in the production learner was worse
than its absence. PPOAgent now accepts Discrete action spaces only. The
GaussianActor design notes (state-independent log_std, unsquashed samples,
the act_dim>=2 shape trap) live in git history and today's SESSION_LOGS
entry if the track ever returns.

Rank-3 observations (binary planes — today only Connect 4's) select a conv
trunk instead of the MLP, by the same no-config-key rule the predecessor's
DQN used. Both heads get their own `ConvQNet` — the predecessor DQN
campaign's exact architecture, kept so its banked numbers stay comparable.
Note this *departs* from the conv-PPO lineage: CleanRL, ppo2 and
SB3 all share one trunk between the heads. Separate stacks follow PureJaxRL,
keep the value_coef/value-clip reasoning below intact, and cost noise-level
duplicate compute at 16 filters.

Deliberately omitted (locked 2026-07-25 after review, see SESSION_LOGS_PREDECESSOR.md):

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

Both normalization omissions were scoped to the DISCRETE track; the wrappers
that lifted them on the (now retired) continuous one live on in the env
stack (rl/envs/normalize.py), config-reachable and tested, not in here.

Note on value_coef: with disjoint actor/critic parameters and Adam, scaling
the value loss barely changes the critic's own updates (Adam renormalizes
per-parameter step sizes); its remaining effect is modulating the critic's
share of the single shared gradient-norm clip. A persistently underfitting
critic wants its own optimizer, not a bigger coefficient.
"""

import copy
import hashlib
import math
from collections import defaultdict
from typing import Any

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F
from torch import nn
from torch.distributions import Categorical

from rl.agents.base import Agent
from rl.buffers.episode import episode_gae
from rl.buffers.rollout import RolloutBuffer, compute_gae
from rl.common.masking import masked_entropy, masked_logits
from rl.networks.conv import ConvQNet
from rl.networks.mlp import mlp
from rl.networks.opp_action import (
    CHOICE_DIM,
    LABEL_SPACES,
    OppActionHead,
    aux_cross_entropy,
    canonicalise,
    marginal_nll,
    shuffle_within_allow,
)
from rl.networks.zeroinfo import synthetic_labels


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
    head last for both nets. (ConvQNet's old dueling flag would have broken
    that premise — `advantage` last, `value` silently taking the head gain —
    which is one reason it was removed, CLEANUP A4 2026-08-29.)
    """
    layers = [m for m in net.modules() if isinstance(m, (nn.Linear, nn.Conv2d))]
    for layer in layers:
        gain = head_gain if layer is layers[-1] else math.sqrt(2.0)
        nn.init.orthogonal_(layer.weight, gain=gain)
        nn.init.zeros_(layer.bias)


def _l2_init_covered(net: nn.Module) -> list[tuple[str, nn.Parameter]]:
    """The parameters an L2-toward-init decay may touch (D23 COVERAGE):
    everything except parameters owned by an `nn.LayerNorm` and except frozen
    ones.

    LayerNorm is excluded because the `_subnet` stack (Linear-ReLU-Linear-LN)
    is approximately scale-invariant, so decaying its weights is gauge, not
    function — the LN gain is the compensating knob and stays free. The filter
    is by OWNING MODULE, not by type: `slot_bias` is a bare `nn.Parameter` and
    an `isinstance(Linear)` filter would miss it.
    """
    ln_params = {
        id(p)
        for module in net.modules()
        if isinstance(module, nn.LayerNorm)
        for p in module.parameters(recurse=False)
    }
    return [
        (name, param)
        for name, param in net.named_parameters()
        if id(param) not in ln_params and param.requires_grad
    ]


def _ln_free_blocks(net: nn.Module) -> list[str]:
    """Top-level blocks of `net` that contain no LayerNorm anywhere below them
    — for the entity trunk: species_emb, move_emb, ctx_net, scorer, slot_bias
    (policy) / head (value); mon_net, move_net and field_net are excluded
    because each terminates in LN, which makes their norms ~half gauge-inert
    (D23: every functional read uses the LN-free blocks only)."""
    blocks = [
        name
        for name, child in net.named_children()
        if not any(isinstance(m, nn.LayerNorm) for m in child.modules())
    ]
    # Bare parameters own no module, so they are LN-free by construction.
    return blocks + [name for name, _ in net.named_parameters(recurse=False)]


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
        l2_init_decay: float = 0.0,
        aux_oppact_coef: float = 0.0,
        aux_label_space: str = "l6",
        aux_scorer_sizes: list[int] = (96,),
        aux_head_gain: float = 0.01,
        aux_max_grad_norm: float = 0.5,
        aux_shuffle_labels: bool = False,
        aux_synthetic: bool = False,
    ):
        # A flat obs vector or channel-first image planes, same rule as DQN.
        if not isinstance(observation_space, gym.spaces.Box) or len(observation_space.shape) not in (1, 3):
            raise TypeError("PPOAgent requires a flat or channel-first image Box observation space")
        # Discrete only: the continuous track (Box -> Gaussian) was retired
        # 2026-08-29 (CLEANUP A3), so the policy is always a masked
        # Categorical (see rl/common/masking.py) with no runtime branching.
        if not isinstance(action_space, gym.spaces.Discrete):
            raise TypeError(
                "PPOAgent requires a Discrete action space — the continuous "
                "track was retired 2026-08-29 (CLEANUP A3)"
            )
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
        self.bc_kl_coef = bc_kl_coef
        self._bc_anchor: "nn.Module | None" = None
        # D23 regenerative regularization: after every optimizer step each
        # covered parameter decays toward its OWN initialization,
        #     theta <- theta - group_lr * l2_init_decay * (theta - theta0),
        # decoupled (AdamW-style) rather than added to the loss — a coupled
        # term would be preconditioned by Adam's 1/sqrt(v) (a ~1200x spread
        # across blocks, and a full-lr reset for dormant parameters), and it
        # would ride inside clip_grad_norm_, moving loss/grad_norm and
        # loss/clip_frac away from every control curve. Default 0.0 is the
        # exact no-op: nothing is captured, no metric key appears, and no
        # checkpoint rider is written (bc_kl_coef precedent).
        if l2_init_decay < 0.0:
            raise ValueError(f"l2_init_decay must be >= 0, got {l2_init_decay}")
        self.l2_init_decay = l2_init_decay
        # Trunk seam (ARCH_SCREEN_SPEC / Rung 2): default "mlp" is the
        # historical path, bit-identical in construction order and RNG
        # consumption (regression-tested against pre-seam goldens). The
        # entity trunk is discrete/flat-obs only — the conv rule and the
        # Gaussian track keep their existing shapes.
        if trunk not in ("mlp", "entity_deepsets"):
            raise ValueError(f"unknown trunk {trunk!r}; expected 'mlp' or 'entity_deepsets'")
        if trunk != "mlp" and self.obs_rank == 3:
            raise TypeError(f"trunk {trunk!r} requires a flat observation space")
        self.trunk = trunk
        # D18 privileged critic: the CRITIC's input is obs ‖ the env's
        # info["privileged"] block; the actor never widens and the obs space
        # is untouched. Discrete/flat only — the tracks that have an env
        # emitting the block.
        if privileged_dim < 0:
            raise ValueError(f"privileged_dim must be >= 0, got {privileged_dim}")
        if privileged_dim and self.obs_rank == 3:
            raise TypeError("privileged_dim requires a flat observation space")
        self.privileged_dim = privileged_dim
        # D25 auxiliary OPPONENT-ACTION head (configs/showdown_sp_actpred12m
        # .yaml, ratified r2 2026-08-13). The head predicts, from the agent's
        # own policy context, which action the opponent is choosing on the same
        # turn; ground truth is free in self-play because the opponent is a
        # frozen snapshot of the agent itself. TRAIN-TIME ONLY — it is not part
        # of the evaluated agent, and the observation and action spaces are
        # untouched. Default 0.0 is the EXACT no-op: no head, no third
        # optimizer group, no metric key, no checkpoint rider (the bc_kl_coef /
        # l2_init_decay precedent).
        if aux_oppact_coef < 0.0:
            raise ValueError(f"aux_oppact_coef must be >= 0, got {aux_oppact_coef}")
        if aux_oppact_coef > 0.0:
            if trunk != "entity_deepsets":
                raise TypeError(
                    "aux_oppact_coef requires trunk 'entity_deepsets': the head is a "
                    "pointer scorer over that trunk's ctx and opponent entity tokens"
                )
            if aux_label_space not in LABEL_SPACES:
                raise ValueError(
                    f"unknown aux_label_space {aux_label_space!r}; expected one of "
                    f"{list(LABEL_SPACES)} — L6 is R0-L's pre-stated fallback, "
                    "executed because the 12-class adopt-rule FAILED, not a free choice"
                )
            if privileged_dim:
                raise TypeError(
                    "aux_oppact_coef with privileged_dim: R0-1's fingerprint requires "
                    "D18's plumbing ABSENT — D25 needs neither the privileged block "
                    "nor its ~65 us/step seat-B re-encode"
                )
        self.aux_oppact_coef = aux_oppact_coef
        self.aux_label_space = aux_label_space
        self.aux_max_grad_norm = aux_max_grad_norm
        self.aux_head: nn.Module | None = None
        # Separate actor and critic, no shared trunk: the value_coef note in
        # the module docstring is premised on it.
        if self.obs_rank == 3:
            # Rank-3 obs (binary planes, today only Connect 4's) select the
            # conv net — DQN's rule, no config key. ConvQNet hardcodes ReLU,
            # which is what every conv-PPO reference uses.
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
        # THE AUX HEAD IS CONSTRUCTED LAST, after both nets are built,
        # initialised and moved — so at a fixed seed the actor's and critic's
        # state_dicts are BIT-IDENTICAL to the lever-off build (R0-3b, which
        # D18 could not have). Moving this construction earlier breaks that
        # test immediately, which is the point of putting it here.
        if self.aux_oppact_coef > 0.0:
            cfg = trunk_kwargs or {}
            self.aux_head = OppActionHead(
                ctx_dim=list(cfg.get("ctx_sizes", (384, 384)))[-1],
                entity_dim=cfg.get("entity_dim", 128),
                sizes=list(aux_scorer_sizes),
            )
            self.aux_head.init_head(aux_head_gain)
            self.aux_head.to(self.device)
        # D25-P's one lever (placebo config P1/P4). The loud seam mirrors the
        # opp_choice seam: a shuffle with no aux loss is a silent no-op and
        # means the wrong config is running.
        self.aux_shuffle_labels = bool(aux_shuffle_labels)
        self._shuffle_gen: torch.Generator | None = None
        if self.aux_shuffle_labels:
            if self.aux_oppact_coef <= 0.0:
                raise ValueError(
                    "aux_shuffle_labels=True with aux_oppact_coef=0: the "
                    "placebo shuffles labels the loss never reads. Rebuild "
                    "from the placebo config (D25-P P5)."
                )
            # Dedicated stream (P4): seeded from the run's global torch seed
            # by a documented derivation, so the draw is reproducible per
            # lane while the default stream — which the minibatch randperm
            # and (via global `random`) poke-env usernames ride on — is
            # untouched whether the flag is on or off.
            self._shuffle_gen = torch.Generator()
            self._shuffle_gen.manual_seed(
                (torch.initial_seed() * 1_000_003 + 25) % (2**63 - 1)
            )
        # D28's one lever (DESIGN2 §1): the zero-information synthetic task.
        # Same loud-seam and dedicated-stream rules as the shuffle placebo;
        # mutually exclusive with it — a lane running both is two levers.
        self.aux_synthetic = bool(aux_synthetic)
        self._synth_gen: torch.Generator | None = None
        if self.aux_synthetic:
            if self.aux_oppact_coef <= 0.0:
                raise ValueError(
                    "aux_synthetic=True with aux_oppact_coef=0: the synthetic "
                    "task generates labels the loss never reads. Rebuild from "
                    "the D28 config."
                )
            if self.aux_shuffle_labels:
                raise ValueError(
                    "aux_synthetic and aux_shuffle_labels are mutually "
                    "exclusive: each is its own arm's ONE lever."
                )
            # Dedicated per-lane label stream (the _shuffle_gen precedent,
            # distinct derivation constant so the two streams never collide).
            self._synth_gen = torch.Generator()
            self._synth_gen.manual_seed(
                (torch.initial_seed() * 1_000_003 + 28) % (2**63 - 1)
            )
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
        # What clip_grad_norm_ sees, and it deliberately EXCLUDES the aux head:
        # the aux gradient is clipped separately (B9).
        self.params = [*self.actor_params, *self.critic_params]
        groups = [
            {"params": self.actor_params, "lr": lr * actor_lr_scale},
            {"params": self.critic_params, "lr": lr},
        ]
        self.aux_params: list[nn.Parameter] = []
        if self.aux_head is not None:
            # A THIRD GROUP, APPENDED LAST (D25 B8) — the opposite of the
            # obvious group-0 append, and this was measured rather than
            # reasoned. `load_state_dict` below substitutes our own
            # param_groups into the loaded state, so torch never compares group
            # counts; what the graft depends on is the POSITIONAL ORDER of
            # params flattened across groups. Appended to group 0 the order
            # becomes [actor, AUX, critic]: a loaded checkpoint's keys 2,3 land
            # on the aux head, THE CRITIC RECEIVES NO ADAM MOMENTS, and the
            # head silently inherits the critic's exp_avg. As a third group the
            # order is [actor, critic, AUX], every loaded key lands on a
            # shape-matching param and the head simply gets none. In-rung
            # impact is nil (D25 lanes are fresh) — it is a silent corruption
            # landmine on any future init_from/resume.
            self.aux_params = list(self.aux_head.parameters())
            groups.append({"params": self.aux_params, "lr": lr * actor_lr_scale})
            # The SHARED trunk — everything the aux gradient can reach, which
            # is the actor minus its policy readout. Held for the R0-10b
            # diagnostic below: both the fresh-head and fitted-head OFFLINE
            # proxies were shown to be dominated by the head's last-layer
            # weight scale and by the norm of an arbitrary z-scored advantage
            # vector (13.6x spread with the actor held fixed), so the ratio is
            # measured HERE instead, live, on the co-trained head against the
            # moving trunk with the run's own real advantages.
            self.trunk_params = [
                p for name, p in self.actor.named_parameters()
                if not name.startswith(("scorer.", "slot_bias"))
            ]
            self._trunk_ids = {id(p) for p in self.trunk_params}
        self.optimizer = torch.optim.Adam(groups, eps=1e-5)
        self._set_actor_trainable(critic_warmup_updates == 0)
        # theta0 capture, AFTER init_head()/.to(device) (so the anchors are
        # the seed's realized init on the training device) and AFTER the
        # optimizer exists (so every covered parameter is paired with the
        # group whose CURRENT lr the decay reads — composing with
        # actor_lr_scale and the lr anneal for free). Plain lists, never
        # Parameters and never buffers: anything registered on the nets would
        # show up in actor/critic state_dict(), which breaks plain-828 eval
        # loading and the d22 block parsers (D23 R0-2b asserts the keys).
        self._theta0: list[torch.Tensor] = []
        self._theta0_names: list[str] = []
        self._l2_init_groups: list[tuple[dict, list[nn.Parameter], list[torch.Tensor], bool]] = []
        self._l2_init_blocks: list[tuple[str, list[nn.Parameter], list[torch.Tensor]]] = []
        if self.l2_init_decay > 0.0:
            self._capture_theta0()
        action_storage = {
            "action_shape": (), "action_dtype": np.int64, "n_actions": int(action_space.n)
        }
        self.buffer = RolloutBuffer(
            rollout_steps,
            num_envs,
            observation_space.shape,
            obs_dtype=observation_space.dtype,
            **action_storage,
            priv_dim=privileged_dim or None,
            opp_choice_dim=CHOICE_DIM if self.aux_head is not None else None,
        )
        self.updates = 0  # completed fill -> epochs cycles

    def _set_actor_trainable(self, trainable: bool) -> None:
        """The staged unfreeze's switch. requires_grad=False is a TRUE freeze:
        backward never populates those grads, and Adam skips any param whose
        grad is None. Zeroing the gradients instead would not freeze anything
        — Adam's existing moments keep walking the weights on a zero grad."""
        for param in self.actor_params:
            param.requires_grad_(trainable)
        # Read by the L2-init decay: a frozen net must not drift toward its
        # anchor either, or the "true freeze" above would leak through the
        # decoupled term.
        self._actor_trainable = trainable

    def _capture_theta0(self) -> None:
        for prefix, net, group in (
            ("actor", self.actor, self.optimizer.param_groups[0]),
            ("critic", self.critic, self.optimizer.param_groups[1]),
        ):
            covered = _l2_init_covered(net)
            params = [param for _, param in covered]
            anchors = [param.detach().clone() for param in params]
            self._theta0_names += [f"{prefix}.{name}" for name, _ in covered]
            self._theta0 += anchors
            self._l2_init_groups.append((group, params, anchors, prefix == "actor"))
            if prefix != "actor":
                continue
            # Per-block metric views over the same tensors (no extra copies).
            for block in _ln_free_blocks(net):
                members = [
                    (param, anchor)
                    for (name, param), anchor in zip(covered, anchors)
                    if name == block or name.startswith(f"{block}.")
                ]
                if members:
                    self._l2_init_blocks.append(
                        (block, [p for p, _ in members], [a for _, a in members])
                    )

    def _apply_l2_init_decay(self) -> None:
        """The lever, applied immediately AFTER optimizer.step() so that
        clip_grad_norm_'s return value (loss/grad_norm) and loss/clip_frac
        stay bit-comparable to a l2_init_decay=0 run. Batched per param group
        through torch._foreach_*: ~2 element passes against Adam's ~5."""
        with torch.no_grad():
            for group, params, anchors, is_actor in self._l2_init_groups:
                if not params or (is_actor and not self._actor_trainable):
                    continue
                alpha = -group["lr"] * self.l2_init_decay
                if alpha == 0.0:  # a fully annealed lr freezes the anchor pull too
                    continue
                torch._foreach_add_(params, torch._foreach_sub(params, anchors), alpha=alpha)

    def l2_init_metrics(self) -> dict[str, float]:
        """||theta - theta0||_2 per LN-FREE actor block plus their aggregate,
        logged at eval boundaries (D23 CONFOUND 7). Empty — no keys at all —
        unless the lever is on."""
        if self.l2_init_decay <= 0.0:
            return {}
        metrics: dict[str, float] = {}
        total = 0.0
        with torch.no_grad():
            for block, params, anchors in self._l2_init_blocks:
                sq = sum(
                    float((param - anchor).pow(2).sum())
                    for param, anchor in zip(params, anchors)
                )
                metrics[f"l2init/anchor_dist_{block}"] = math.sqrt(sq)
                total += sq
        metrics["l2init/anchor_dist_actor_lnfree"] = math.sqrt(total)
        return metrics

    def theta0_state(self) -> dict[str, Any]:
        """The run dir's theta0.pt payload: the anchors themselves, keyed by
        qualified name, plus the digest every checkpoint carries."""
        return {
            "theta0_hash": self.theta0_hash(),
            "l2_init_decay": self.l2_init_decay,
            "theta0": {
                name: anchor.detach().to("cpu")
                for name, anchor in zip(self._theta0_names, self._theta0)
            },
        }

    def theta0_hash(self) -> str:
        """sha256 over the anchors in capture order — each contributes its
        qualified name and its raw CPU bytes. Stamped into every checkpoint
        (60 identical 4.5 MB riders would be strictly worse) so a training
        resume against a theta0.pt from a different init is caught."""
        digest = hashlib.sha256()
        for name, anchor in zip(self._theta0_names, self._theta0):
            digest.update(name.encode())
            digest.update(anchor.detach().to("cpu").contiguous().numpy().tobytes())
        return digest.hexdigest()

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

    def act_logp(self, obs: Any, action_mask: Any) -> tuple[Any, Any]:
        """Batched sample PLUS its log-prob — the async collector's act path.

        Under async collection the policy can change between a row's decision
        and its update (an in-flight battle straddles the update boundary),
        so old_logp must be recorded here, where the action is drawn, not
        recomputed at update start (THROUGHPUT_SPEC risk table; G5). Same
        masked-Categorical construction as _logp_entropy, so the recorded
        value is what the first epoch's recompute would produce — up to
        batch-size-dependent kernel reduction order, which is exactly why
        G5's health read is mean |ratio - 1| > 0, never == 0.

        Always batched: (B, *obs_shape) in, ((B,) actions, (B,) logp) out.
        """
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=self.device)
        with torch.no_grad():
            dist = Categorical(logits=masked_logits(self.actor(obs_t), mask_t))
            actions = dist.sample()
            logp = dist.log_prob(actions)
        return actions.cpu().numpy(), logp.cpu().numpy()

    def _logp_entropy(
        self,
        obs: torch.Tensor,
        actions: torch.Tensor,
        masks: torch.Tensor | None,
        features: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor, tuple[torch.Tensor, ...] | None]:
        """log pi(a|s), H(pi(.|s)) — both (B,) — and D25's aux features.

        The one place the acted distribution is rebuilt during optimization,
        so the surrogate, the recompute and the entropy bonus cannot drift
        apart.

        `features` is D25's seam: the aux head reads ctx and the opponent
        entity tokens off the SAME forward the surrogate already makes (B9),
        rather than paying a second actor pass at ~+25% update time. The extra
        tensors do not enter the policy logits, so the surrogate is unchanged.
        """
        if features:
            logits, *feats = self.actor(obs, return_features=True)
        else:
            logits, feats = self.actor(obs), None
        dist = Categorical(logits=masked_logits(logits, masks))
        return dist.log_prob(actions), masked_entropy(logits, masks), feats

    def _aux_gradient(
        self,
        feats: tuple[torch.Tensor, ...],
        target: torch.Tensor,
        allow: torch.Tensor,
        valid: torch.Tensor,
    ) -> tuple[float, float, float, float, float]:
        """B9 step 2: the aux gradient, clipped to its OWN budget and added
        into `.grad` AFTER the PPO clip has been read. Returns (loss,
        total_norm, trunk_norm, delivered_trunk_norm, clip_scale) — the last
        two added 2026-08-17 so a dose gate can read what the trunk actually
        received rather than the pre-clip log.

        Decoupled because the global clip BINDS: measured on control s26
        (11,718 rows) `loss/grad_clip_frac` is 0.8995, median 0.9375 — the clip
        binds on ~9 of 10 minibatches, so a coupled aux term would shrink the
        policy's effective step on nearly every one. That is a covert 10-30%
        policy-LR cut, i.e. an unregistered second lever inside a one-lever
        rung (and D21 already queues LR annealing as its own). Keeping the aux
        term out of `clip_grad_norm_` is what makes `loss/grad_norm` and
        `loss/grad_clip_frac` numerically identical to every control curve on a
        fixed batch (R0-9).

        IRREDUCIBLE RESIDUE, DISCLOSED (C9): the aux gradient still enters
        Adam's second moment for shared trunk parameters, so the policy's
        per-parameter effective step is not perfectly preserved. That cannot be
        fixed for a shared trunk, and it is not claimed to be.
        """
        loss = aux_cross_entropy(self.aux_head(*feats), target, allow, valid)
        # requires_grad filter: under the staged unfreeze the actor is frozen
        # for the first N updates and autograd.grad would refuse the batch.
        params = [p for p in (*self.actor_params, *self.aux_params) if p.requires_grad]
        grads = torch.autograd.grad(
            self.aux_oppact_coef * loss, params, allow_unused=True
        )
        present = [g for g in grads if g is not None]
        total = float(torch.norm(torch.stack([g.norm() for g in present]))) if present else 0.0
        # The trunk-only slice, post-coefficient and PRE-clip: the numerator of
        # R0-10b's ratio, measured on the real thing rather than on a proxy.
        on_trunk = [g for p, g in zip(params, grads)
                    if g is not None and id(p) in self._trunk_ids]
        trunk = float(torch.norm(torch.stack([g.norm() for g in on_trunk]))) if on_trunk else 0.0
        # clip_grad_norm_'s own arithmetic, applied to a detached grad list.
        scale = min(1.0, self.aux_max_grad_norm / (total + 1e-6))
        for param, grad in zip(params, grads):
            if grad is None:
                continue
            if param.grad is None:
                param.grad = grad * scale
            else:
                param.grad.add_(grad, alpha=scale)
        # DELIVERED trunk norm: the logged pre-clip trunk × the clip scale the
        # grads actually received. Logged per-minibatch because
        # min(1, c/E[x]) != E[min(1, c/x)] — a rollout-mean reconstruction of
        # this quantity certifies a dose that was never delivered (the D27/
        # D25-P landmine; ch2_review_2 verified this arithmetic against the
        # coefficient entering at torch.autograd.grad above).
        return float(loss.item()), total, trunk, trunk * scale, scale

    def _prepare_aux(
        self, flat_obs: torch.Tensor, flat_opp_choice: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, float]]:
        """D25's labels, canonicalised ONCE PER UPDATE (B12) — done inside
        the epoch x minibatch loop this is the same work 16 times over and
        surfaces only as an unexplained update-time regression. The frame is
        each row's OWN id suffix, so the label can only ever name entities
        the actor could see (B4, the structural anti-leak property). Shared
        by both collection paths — the (T, N) rollout and the episode batch
        flatten their own labels and call here."""
        aux_target, aux_allow, aux_valid, aux_stats = canonicalise(
            flat_obs, flat_opp_choice, self.actor.tokenizer
        )
        if self.aux_shuffle_labels:
            # D25-P (placebo config P1/P4): ONE permutation per rollout,
            # drawn here and reused by all epochs x minibatches via
            # aux_target[idx] — the treatment's label structure exactly.
            # aux/marginal_nll is the shuffled task's exact floor; both
            # keys exist only on placebo lanes (P5).
            aux_stats["aux/marginal_nll"] = marginal_nll(
                aux_target, aux_allow, aux_valid
            )
            aux_target, shuf_stats = shuffle_within_allow(
                aux_target, aux_allow, aux_valid, self._shuffle_gen
            )
            aux_stats.update(shuf_stats)
        if self.aux_synthetic:
            # D28: the REAL labels' only surviving role is the row filter
            # — aux_allow/aux_valid pass through untouched so trained
            # rows match D25's exactly; the target is the frozen-task
            # draw, a function of the observation alone (zero opponent-
            # action information; rl/networks/zeroinfo.py). ONE draw per
            # rollout, reused by all epochs x minibatches via
            # aux_target[idx] — the treatment's label structure exactly.
            aux_target, synth_stats = synthetic_labels(
                flat_obs, aux_allow, aux_valid,
                self.actor.tokenizer, self._synth_gen,
            )
            aux_stats.update(synth_stats)
            # The manipulation check's A1 term, on the SYNTHETIC target
            # (the trained task's own mask-renormalised marginal floor;
            # review MF-1a/MF-4 — without it B-VOID-TASK cannot fire).
            # Own name, not aux/marginal_nll: that key means "the
            # SHUFFLED task's floor" on placebo lanes and the two must
            # never be conflated by a cross-arm reader.
            aux_stats["aux/synth_marginal_nll"] = marginal_nll(
                aux_target, aux_allow, aux_valid
            )
        return aux_target, aux_allow, aux_valid, aux_stats

    def update(self, batch: Any) -> dict[str, float]:
        # The vector loop hands one batched (N-wide) transition row per env
        # step; accumulate until the horizon fills, then train on the rollout.
        # next_masks has no consumer: the critic is the only next_obs reader,
        # and values are never masked.
        (obs, actions, rewards, next_obs, terminated, truncated, masks, _next_masks,
         *rest) = batch
        if len(rest) > 3:
            raise ValueError(
                f"update() takes at most 11 batch elements, got {8 + len(rest)}"
            )
        privs, next_privs, opp_choice = (*rest, *(None,) * (3 - len(rest)))
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
        # The same loud seam for D25: a lane carrying env_kwargs.opp_action but
        # not agent.aux_oppact_coef would collect labels nobody trains on; the
        # reverse would train the head on a buffer of zeros.
        if (opp_choice is None) == (self.aux_head is not None):
            raise ValueError(
                f"opponent-action mismatch: agent aux_oppact_coef="
                f"{self.aux_oppact_coef} but the env "
                f"{'did not emit' if opp_choice is None else 'emitted'} "
                "info['opp_choice'] — env_kwargs.opp_action and the agent "
                "hparam must be set together"
            )
        self.buffer.add(
            obs, actions, rewards, next_obs, terminated, truncated, masks,
            privs, next_privs, opp_choice,
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
        flat_actions = torch.as_tensor(buf.actions, device=self.device).flatten(0, 1)
        flat_masks = torch.as_tensor(buf.masks, device=self.device).flatten(0, 1)  # (T*N, A) bool
        # D25's labels, canonicalised ONCE PER ROLLOUT (B12) — the shared
        # helper below; both collection paths call it.
        aux_target = aux_allow = aux_valid = None
        aux_stats: dict[str, float] = {}
        if self.aux_head is not None:
            aux_target, aux_allow, aux_valid, aux_stats = self._prepare_aux(
                flat_obs,
                torch.as_tensor(buf.opp_choice, device=self.device).flatten(0, 1),
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

        metrics = self._optimize(
            flat_obs, flat_actions, flat_masks, flat_critic_obs,
            flat_advantages, flat_targets, flat_old_logp,
            steps_seen=self.updates * horizon * num_envs,
            aux_target=aux_target, aux_allow=aux_allow, aux_valid=aux_valid,
            aux_stats=aux_stats,
        )
        self.buffer.clear()
        return metrics

    def update_episodes(self, batch: dict[str, Any], steps_seen: int) -> dict[str, float]:
        """The async collector's update entry (THROUGHPUT_SPEC Stage 2): a
        flat batch of WHOLE finished episodes (rl/buffers/episode.py's drain
        format) instead of a (T, N) rollout. Three deliberate differences
        from update(), each the honest version of what the sync path gets
        for free from lockstep collection:

        - old_logp arrives RECORDED AT ACT TIME (act_logp), never recomputed
          — under async collection the policy may have changed since a row
          acted, and a recompute would silently reference the wrong policy
          (ratio exactly 1.0, clip_frac 0, vanilla PG on stale rows).
        - GAE is per-episode with terminal bootstrap 0 — bit-for-bit the
          sync semantics (ShowdownEnv forces every decided finish terminal),
          via the same audited compute_gae kernel.
        - ONE critic pass: within an episode V(s') is V(s) shifted, so the
          sync path's second forward over 30k next_obs rows is gone.

        `steps_seen` is the train loop's env-step counter (checkpointed, so
        a resume keeps the lr anneal on schedule). Privileged critics are
        refused loudly: the async collector has no seat-2 battle object to
        emit the block, and a silently blind wide critic is the exact
        failure the sync path's seam check exists to prevent."""
        if self.privileged_dim:
            raise ValueError(
                "privileged critics are not supported on the async collection "
                "path: no privileged block is collected, and training the "
                "wide critic on zeros would be silent"
            )
        opp_choice = batch.get("opp_choice")
        if (opp_choice is None) == (self.aux_head is not None):
            raise ValueError(
                f"opponent-action mismatch: agent aux_oppact_coef="
                f"{self.aux_oppact_coef} but the collector "
                f"{'did not record' if opp_choice is None else 'recorded'} "
                "opp_choice labels — the collector flag and the agent hparam "
                "must be set together"
            )
        flat_obs = torch.as_tensor(batch["obs"], dtype=torch.float32, device=self.device)
        flat_actions = torch.as_tensor(batch["actions"], device=self.device)
        flat_masks = torch.as_tensor(batch["masks"], device=self.device)
        flat_old_logp = torch.as_tensor(
            batch["old_logp"], dtype=torch.float32, device=self.device
        )
        aux_target = aux_allow = aux_valid = None
        aux_stats: dict[str, float] = {}
        if self.aux_head is not None:
            aux_target, aux_allow, aux_valid, aux_stats = self._prepare_aux(
                flat_obs, torch.as_tensor(opp_choice, device=self.device)
            )
        with torch.no_grad():
            values = self.critic(flat_obs).squeeze(-1)
        advantages = episode_gae(
            batch["rewards"],
            values.cpu().numpy(),
            batch["lengths"],
            self.gamma,
            self.gae_lambda,
        )
        advantages_t = torch.as_tensor(advantages, device=self.device)
        flat_targets = advantages_t + values
        metrics = self._optimize(
            flat_obs, flat_actions, flat_masks, flat_obs,
            advantages_t, flat_targets, flat_old_logp,
            steps_seen=steps_seen,
            aux_target=aux_target, aux_allow=aux_allow, aux_valid=aux_valid,
            aux_stats=aux_stats,
        )
        return metrics

    def _optimize(
        self,
        flat_obs: torch.Tensor,
        flat_actions: torch.Tensor,
        flat_masks: torch.Tensor,
        flat_critic_obs: torch.Tensor,
        flat_advantages: torch.Tensor,
        flat_targets: torch.Tensor,
        flat_old_logp: torch.Tensor,
        steps_seen: int,
        aux_target: torch.Tensor | None = None,
        aux_allow: torch.Tensor | None = None,
        aux_valid: torch.Tensor | None = None,
        aux_stats: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """The epoch x minibatch optimization on a prepared flat batch, plus
        its diagnostics — everything downstream of advantage computation,
        factored out (Stage 2) so the async path's episode batches enter the
        SAME optimization the (T, N) rollout runs; neither path's numbers
        move. `steps_seen` feeds the lr anneal: update() passes
        updates * horizon * num_envs (bit-identical to the pre-factor code);
        update_episodes passes the loop's actual env-step counter, which is
        what that product approximates."""
        aux_stats = dict(aux_stats or {})
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
            frac = max(0.0, 1.0 - steps_seen / self.lr_anneal_steps)
            self.optimizer.param_groups[0]["lr"] = self.base_lr * self.actor_lr_scale * frac
            self.optimizer.param_groups[1]["lr"] = self.base_lr * frac
            if self.aux_head is not None:
                # The head is actor-side, so it rides the actor's schedule —
                # one lr over the whole actor stack. Inert at D25's
                # lr_anneal_steps: 0, which is why B8 could call a third group
                # "safe" against an anneal that writes [0] and [1] by index.
                self.optimizer.param_groups[2]["lr"] = (
                    self.base_lr * self.actor_lr_scale * frac
                )

        batch_size = flat_actions.shape[0]
        minibatch_size = batch_size // self.minibatches
        sums: dict[str, float] = defaultdict(float)
        grad_steps = 0
        for _ in range(self.epochs):
            perm = torch.randperm(batch_size, device=self.device)
            for start in range(0, batch_size, minibatch_size):
                idx = perm[start : start + minibatch_size]
                if idx.numel() < 2:
                    # A trailing 1-row slice: async episode batches are not
                    # multiples of `minibatches` (whole episodes overshoot
                    # the budget), and a single row has no advantage std —
                    # the NaN would poison the weights with no error until
                    # the next forward (caught live by smoke3, 2026-09-01).
                    # Skipped, not folded: the row still trains under the
                    # other epochs' permutations. The vector path divides
                    # exactly and never takes this branch.
                    continue
                # Per-minibatch advantage normalization; the 1e-8 keeps a
                # zero-variance minibatch at zero instead of NaN.
                mb_adv = flat_advantages[idx]
                mb_adv = (mb_adv - mb_adv.mean()) / (mb_adv.std() + 1e-8)
                # Every epoch reapplies the stored mask: pi_new must be masked
                # exactly like the pi_old above, or the ratio is silently
                # wrong (all-True leaves the logits bitwise untouched).
                new_logp, entropies, feats = self._logp_entropy(
                    flat_obs[idx], flat_actions[idx], flat_masks[idx],
                    features=self.aux_head is not None,
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
                # retain_graph only for D25: the aux term reuses THIS
                # minibatch's graph rather than paying a second actor forward
                # (B9's build decision — a second forward is ~+25% update time
                # and is not in the rung's -2.1% budget).
                loss.backward(retain_graph=self.aux_head is not None)
                if self.aux_head is not None:
                    # PRE-clip, and read-only: clip_grad_norm_ rescales .grad in
                    # place, so the denominator has to be taken before it. Both
                    # norms are logged and the RATIO is derived at read time —
                    # a per-minibatch mean-of-ratios is Jensen-inflated by
                    # 1.3-1.5x against ratio-of-means, which is how the offline
                    # proxy came to overstate itself.
                    with torch.no_grad():
                        pol_trunk = torch.norm(torch.stack(
                            [p.grad.norm() for p in self.trunk_params
                             if p.grad is not None]))
                    sums["aux/policy_trunk_norm"] += float(pol_trunk)
                # One clip over the actor+critic union — separate calls would
                # hand each net the full norm budget. The return value is the
                # total norm BEFORE clipping, which is the diagnostic: paired
                # with the fraction of minibatches that exceed max_grad_norm
                # it says whether the clip is a rare safety net or a
                # permanent lr divisor (the 2026-08-05 PPO audit saw it bind
                # 16/16 on synthetic data and could not tell which).
                grad_norm = nn.utils.clip_grad_norm_(self.params, self.max_grad_norm)
                if self.aux_head is not None:
                    # AFTER the clip read above, BEFORE the step: the aux term
                    # must not move loss/grad_norm or loss/grad_clip_frac.
                    aux_loss, aux_norm, aux_trunk, aux_delivered, aux_scale = (
                        self._aux_gradient(
                            feats, aux_target[idx], aux_allow[idx], aux_valid[idx]
                        )
                    )
                    sums["aux/loss"] += aux_loss
                    sums["aux/grad_norm"] += aux_norm
                    sums["aux/trunk_norm"] += aux_trunk
                    sums["aux/trunk_norm_delivered"] += aux_delivered
                    sums["aux/clip_scale"] += aux_scale
                    sums["aux/grad_clip_frac"] += float(aux_norm > self.aux_max_grad_norm)
                    if (self.aux_shuffle_labels or self.aux_synthetic) \
                            and grad_steps == 0:
                        # Epoch-1 minibatch-0, before any step this rollout:
                        # the memorisation-free tracker P-SHUF reads (D25-P
                        # P5 — in-sample aux/loss can drift below the batch
                        # marginal by permutation memorisation alone).
                        # D28 reuses ONE draw across every epoch x minibatch
                        # and has the same channel (review MF-1b).
                        # Rollout-level, not divided by grad_steps.
                        aux_stats["aux/loss_mb0"] = aux_loss
                self.optimizer.step()
                if self.l2_init_decay > 0.0:
                    # AFTER the step and after the clip read above: the lever
                    # is a post-step displacement, not part of the gradient.
                    self._apply_l2_init_decay()

                sums["loss/policy"] += float(policy_loss.item())
                sums["loss/value"] += float(value_loss.item())
                sums["loss/entropy"] += float(entropy.item())
                sums["loss/approx_kl"] += float(approx_kl.item())
                sums["loss/clip_frac"] += float(clip_frac.item())
                sums["loss/grad_norm"] += float(grad_norm.item())
                sums["loss/grad_clip_frac"] += float(grad_norm.item() > self.max_grad_norm)
                grad_steps += 1

        self.updates += 1
        # sums are per-grad-step and averaged; the two batch-level reads are
        # already single numbers for this update and must not be divided.
        return {
            **{name: total / grad_steps for name, total in sums.items()},
            "loss/explained_variance": explained_variance,
            "loss/adv_std": adv_std,
            # Rollout-level label diagnostics; already single numbers for this
            # update and must not be divided. Empty unless the lever is on.
            **aux_stats,
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
        if self.aux_head is not None:
            # A rider, like bc_anchor: `actor` and `critic` keep exactly the
            # keys and counts a control checkpoint has, so eval_checkpoint.py,
            # score_ladder.py and d22_dormant_rank.py load a D25 checkpoint
            # unmodified (R0-2b).
            state["aux_head"] = self.aux_head.state_dict()
        if self.l2_init_decay > 0.0:
            # A digest, not the anchors: theta0.pt lives once in the run dir.
            # Riders are ignored by load_state_dict on purpose — an EVAL-side
            # rebuild (score_ladder, eval_checkpoint) reconstructs a different
            # init and must still load a D23 checkpoint unchanged.
            state["theta0_hash"] = self.theta0_hash()
        return state

    def load_state_dict(self, state: dict[str, Any]) -> None:
        # D25 R0-2b, checked BEFORE anything is loaded: a lever-on checkpoint
        # must not load silently into a lever-off agent. Nothing else would
        # catch it — actor/critic keys match exactly (the head is agent-owned)
        # and the optimizer graft below tolerates extra state keys by design.
        # The reverse — an aux-on agent warm-starting from a control
        # checkpoint — is legitimate and leaves the head at its init.
        if state.get("aux_head") is not None and self.aux_head is None:
            raise ValueError(
                "checkpoint carries a D25 aux head but this agent has "
                "aux_oppact_coef = 0: the auxiliary head would be dropped "
                "without a word. Rebuild the agent from the run's own config."
            )
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
        aux_state = state.get("aux_head")
        if aux_state is not None:
            self.aux_head.load_state_dict(aux_state)

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

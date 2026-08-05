"""Polyak (soft) target updates: `theta_target <- tau * theta + (1 - tau) * theta_target`.

Bootstrapped value learning regresses toward targets computed by the very
network being trained, so the labels move with every gradient step. DQN's
answer is a frozen copy synced every N gradient steps: labels are stationary
inside each window, and jump at every sync. Polyak averaging is the other
answer — the target tracks the online net continuously at rate tau, so the
labels are never stationary but never jump either. The two are the same
bargain spread differently: at tau = 5e-3 the target is an exponential moving
average whose weight on any past parameter value decays with a ~200-step time
constant, where a hard sync at N = 1000 holds one snapshot and then replaces
it wholesale.

SAC needs this rather than merely preferring it. Its twin critics are updated
every gradient step, and the actor's objective differentiates *through* those
critics, so a hard sync would put a discontinuity in the actor's loss surface
at every sync point. DQN's actor is an argmax with no such dependence, which
is why hard sync is fine there and paper-faithful.

Shared here rather than written inside the SAC agent so the two styles stay
directly swappable: a soft-update DQN is a cheap ablation against the
hard-sync baseline, and it only stays cheap while this lives in one place.
"""

import torch
from torch import nn


def polyak_update(source: nn.Module, target: nn.Module, tau: float) -> None:
    """Blend `source`'s parameters into `target`'s, in place.

    Parameters only, not buffers. Every network in this repo is a plain MLP or
    conv stack with no running statistics, and the one module that does
    register buffers — SAC's actor, holding the action scale and bias — is
    never a Polyak target. A net carrying buffers (BatchNorm, say) would need
    them handled here; nothing does today.

    `strict=True` is NOT a guard against a half-updated target: the writes are
    in place, so a length mismatch raises only after the leading parameters
    have already been blended. What it guards against is the mismatch passing
    unnoticed. (In the likeliest failure — mismatched `hidden_sizes` — a shape
    error fires first; strict only bites when shapes line up but counts don't.)

    The `no_grad` scope is what makes the in-place write legal at all: with
    grad mode on, PyTorch refuses in-place ops on leaf tensors that require
    grad. Targets also carry `requires_grad=False` from construction, which
    keeps them out of any autograd graph the critics are part of.
    """
    with torch.no_grad():
        for param, target_param in zip(source.parameters(), target.parameters(), strict=True):
            target_param.mul_(1.0 - tau).add_(param, alpha=tau)

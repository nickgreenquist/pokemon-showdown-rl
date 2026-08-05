"""Polyak soft target updates.

Every case uses ASYMMETRIC source/target values on purpose: with tau and
(1 - tau) both applied to equal tensors, the swapped-coefficient mutation
`target.mul_(tau).add_(source, alpha=1 - tau)` — the one real way to get this
function wrong — produces the identical answer and the test passes anyway.
"""

import pytest
import torch
from torch import nn

from rl.common.polyak import polyak_update
from rl.networks.mlp import mlp

TAU = 0.3


def _pair(source_fill: float, target_fill: float) -> tuple[nn.Module, nn.Module]:
    source, target = nn.Linear(2, 3), nn.Linear(2, 3)
    with torch.no_grad():
        for p in source.parameters():
            p.fill_(source_fill)
        for p in target.parameters():
            p.fill_(target_fill)
    target.requires_grad_(False)  # the caller's contract, as DQN does for q_target
    return source, target


def _values(module: nn.Module) -> list[float]:
    return [float(p.detach().flatten()[0]) for p in module.parameters()]


def test_blend_is_hand_computed_and_asymmetric():
    """0.3 * 2 + 0.7 * 10 = 7.6. The swapped-coefficient mutation gives 4.4."""
    source, target = _pair(2.0, 10.0)
    polyak_update(source, target, TAU)
    assert _values(target) == pytest.approx([7.6, 7.6])
    assert _values(source) == pytest.approx([2.0, 2.0])  # source must not move


def test_tau_one_is_a_hard_sync_and_tau_zero_is_a_no_op():
    """The two endpoints are the two target-update styles this repo now has:
    tau=1 reproduces DQN's `load_state_dict` sync exactly."""
    source, target = _pair(2.0, 10.0)
    polyak_update(source, target, 1.0)
    assert _values(target) == pytest.approx([2.0, 2.0])

    source, target = _pair(2.0, 10.0)
    polyak_update(source, target, 0.0)
    assert _values(target) == pytest.approx([10.0, 10.0])


def test_repeated_updates_decay_toward_the_source_geometrically():
    """The EMA property, which is the whole point: after k updates the gap is
    the initial gap times (1 - tau)^k. Pins the DIRECTION of the blend — a
    helper that drifted the target away from the source would still pass a
    single-step equality check against a hand-computed number of the wrong
    sign, but not this."""
    source, target = _pair(2.0, 10.0)
    for _ in range(5):
        polyak_update(source, target, TAU)
    expected = 2.0 + (10.0 - 2.0) * (1.0 - TAU) ** 5
    assert _values(target) == pytest.approx([expected, expected])
    assert expected < 10.0  # moved toward the source, not away


def test_every_parameter_tensor_is_updated_not_just_the_first():
    """A multi-layer net: an implementation that broke out of the loop early,
    or walked `state_dict()` keys in a different order, would leave deeper
    layers stale."""
    source, target = mlp(3, [4, 5], 2), mlp(3, [4, 5], 2)
    with torch.no_grad():
        for p in source.parameters():
            p.fill_(1.0)
        for p in target.parameters():
            p.fill_(0.0)
    target.requires_grad_(False)
    polyak_update(source, target, TAU)
    assert len(list(target.parameters())) == 6  # 3 Linears x (weight, bias)
    for p in target.parameters():
        assert torch.allclose(p, torch.full_like(p, TAU))


def test_mismatched_parameter_counts_raise():
    """Silently blending only the shared prefix is the failure this rules out.
    Shapes line up here (both start Linear(2, 3)), so only the strict zip can
    catch it — a shape error would have fired first otherwise."""
    source = nn.Sequential(nn.Linear(2, 3), nn.Linear(3, 3))
    target = nn.Sequential(nn.Linear(2, 3))
    with pytest.raises(ValueError):
        polyak_update(source, target, TAU)


def test_target_stays_out_of_the_autograd_graph():
    """SAC's critic loss backprops through Q1/Q2; if the Polyak write left the
    target attached to that graph, the TD target would carry gradient into the
    critics it is supposed to hold fixed."""
    source, target = _pair(2.0, 10.0)
    polyak_update(source, target, TAU)
    assert all(not p.requires_grad for p in target.parameters())
    assert all(p.grad_fn is None for p in target.parameters())
    assert not target(torch.ones(1, 2)).requires_grad

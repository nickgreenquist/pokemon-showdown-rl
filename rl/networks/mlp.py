"""MLP builder shared by the value/policy networks.

`hidden_sizes=[]` degenerates to a single linear layer — the Phase 1
on-ramp's `nn.Linear(4, 2)` and full DQN differ only in this argument.
"""

from torch import nn


class PrefixSliceActor(nn.Module):
    """Cross-encoder eval shim: run an actor trained on a strict PREFIX of
    the current obs layout by slicing its input down to the width it was
    trained on.

    The one legal pair is a v2/808 checkpoint under the 828 id-suffix
    process: the id block is a pure suffix (rl/envs/showdown.py::_fill_ids),
    so `obs[..., :808]` is bit-for-bit the v2/808 encoding — the slice is
    exact, not an approximation. Anything else (in particular pre-recharge-
    fix v2/807 checkpoints, whose layout differs by an INSERTED dim, not a
    truncated one) has no exact map and must be refused by the caller, never
    shimmed. Eval-only: wraps the actor alone (eval never touches the
    critic), and wrapping composes with AgentOpponent's deepcopy/freeze.
    """

    def __init__(self, actor: nn.Module, in_dim: int):
        super().__init__()
        self.actor = actor
        self.in_dim = in_dim

    def forward(self, x):
        return self.actor(x[..., : self.in_dim])


def mlp(
    in_dim: int,
    hidden_sizes: list[int],
    out_dim: int,
    activation: type[nn.Module] = nn.ReLU,
) -> nn.Sequential:
    sizes = [in_dim, *hidden_sizes, out_dim]
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:  # no activation after the output layer
            layers.append(activation())
    return nn.Sequential(*layers)


class DuelingMLP(nn.Module):
    """Dueling head (Wang et al. 2016): a shared trunk feeds a scalar
    state-value head V(s) and a per-action advantage head A(s, a), combined
    as Q = V + A - mean(A). State value is learned once, not re-learned
    independently inside every action's output; the mean-subtraction pins
    the otherwise unidentifiable V/A split (any constant could shift
    between them without changing Q).
    """

    def __init__(self, in_dim: int, hidden_sizes: list[int], out_dim: int):
        super().__init__()
        if not hidden_sizes:
            raise ValueError("DuelingMLP needs at least one hidden layer for the shared trunk")
        layers: list[nn.Module] = []
        for h in hidden_sizes:
            layers += [nn.Linear(in_dim, h), nn.ReLU()]
            in_dim = h
        self.trunk = nn.Sequential(*layers)
        self.value = nn.Linear(in_dim, 1)
        self.advantage = nn.Linear(in_dim, out_dim)

    def forward(self, x):
        z = self.trunk(x)
        adv = self.advantage(z)
        return self.value(z) + adv - adv.mean(dim=-1, keepdim=True)

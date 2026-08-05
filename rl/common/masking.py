"""Action masking: the harness-wide contract for envs whose legal actions
change per state — the capstone's whole action model (Pokémon Showdown:
fainted Pokémon can't be switched to, moves run out of PP, forced switches).
The spine envs have no illegal actions, so their wrapper emits an all-True
mask and the masked code path is exercised everywhere from day one — never
special-cased, and provably a no-op where nothing is illegal.

The contract:

- Envs supply `info["action_mask"]`: bool `[n_actions]`, True = legal. The
  `ActionMask` wrapper injects an all-True mask when the env doesn't provide
  one, so algorithm code never branches on a missing mask.
- Logits/Q-values are masked with a large *finite* negative sentinel before
  softmax/argmax/max. Not -inf: `Categorical.entropy()` computes
  `probs * log_probs`, and at -inf positions that is `0 * -inf = NaN`, which
  flows silently into the entropy bonus and the loss. With -1e8, softmax
  underflows illegal positions to exactly 0.0, and `0.0 * -1e8 = 0.0`.
- The value head is never masked: V(s) is a property of the state, not of
  the action set.
- `masked_logits` leaves logits bitwise unchanged under an all-True mask
  (`torch.where` passes the legal side through untouched) — the property
  that makes the retrofit a provable no-op on every existing benchmark.
"""

import torch

NEG = -1e8  # finite sentinel: softmax underflows to exactly 0.0, no 0*inf NaN


def masked_logits(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """`logits` [..., A] float, `mask` [..., A] bool (True = legal) -> logits
    with NEG at illegal positions, bitwise-identical at legal ones."""
    # An all-illegal row is an upstream bug (even a forced switch has switch
    # actions); silently it would yield a uniform-garbage distribution.
    assert bool(mask.any(dim=-1).all()), "action mask row with no legal action"
    return torch.where(mask, logits, torch.full_like(logits, NEG))


def masked_entropy(logits: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Entropy over legal actions only, shaped [...]. Explicit rather than
    `Categorical(...).entropy()`: the where-guard pins illegal positions to an
    exact 0 contribution, so no sentinel arithmetic can leak NaN."""
    logp = torch.log_softmax(masked_logits(logits, mask), dim=-1)
    plogp = torch.where(mask, logp.exp() * logp, torch.zeros_like(logp))
    return -plogp.sum(dim=-1)


def masked_sample(space, mask) -> int:
    """Uniform sample over the legal actions of a Discrete space, by rejection.

    Rejection, not `np_random.choice(legal)`: with an all-True mask the first
    draw always accepts, so the RNG stream is identical to a bare
    `space.sample()` — this is what keeps fixed-seed runs on the spine envs
    bit-for-bit reproducible across the masking retrofit. Expected draws with
    k of A legal are A/k; termination is guaranteed by the >=1-legal contract.
    """
    assert mask.any(), "action mask with no legal action"
    while True:
        action = space.sample()
        if mask[action]:
            return int(action)

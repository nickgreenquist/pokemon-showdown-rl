"""D25 — auxiliary OPPONENT-ACTION prediction: the head and its label
canonicaliser (configs/showdown_sp_actpred12m.yaml, ratified r2 2026-08-13).

The head predicts, from the agent's own policy context, WHICH ACTION THE
OPPONENT IS CHOOSING ON THE SAME TURN. Ground truth is free in self-play
because the opponent is a frozen snapshot of the agent itself; the head is
TRAIN-TIME ONLY and is not part of the evaluated agent. OBS_DIM stays 828 and
the encoder is untouched.

THE L6 CANONICAL LABEL SPACE (§1), Designer A's verbatim — this is R0-L's own
pre-stated fallback, executed because R0-L FAILED (the 12-class space had to
beat L6 by >= 0.05 nats at BOTH named lanes and cleared 0 of 2):

    L6 = { opponent-move-slot 0, 1, 2, 3 | OTHER_MOVE | SWITCH }

where the slots are the encoder's four `_opponent_move_slots`, read from the
BUFFERED OBS ROW'S OWN ID-SUFFIX. That last clause is what makes the anti-leak
property STRUCTURAL rather than argued (B4): a switch-in that
`battle1.opponent_team` only learns about AFTER the env step cannot become a
nameable class, because the frame is the row the actor itself saw. Doing the
canonicalisation env-side, post-step, would leak.

LEGALITY, all obs-derivable (B11) — deliberately NOT seat 2's true
`get_action_mask`, which would hand the trunk the opponent's legality for free
and make "what can they even do" unlearnable rather than learned:
  slot j     legal iff slot j carries a nonzero move id
  SWITCH     legal iff the opponent has a live bench (the faint count is public)
  OTHER_MOVE ALWAYS legal — which is what keeps `masked_logits`' ">= 1 legal"
             assert from ever tripping.

The 12-class space is NOT trained and is not dead: it is recorded as a free
secondary on the mechanism letter, because the probe is fitted on the lane's
ctx rather than on the head's output.
"""

import torch
from torch import nn

from rl.common.masking import masked_logits

# The six L6 classes, in the PRE-REGISTERED ORDER: §1 writes the space as
# "{ opponent-move-slot 0, 1, 2, 3 | OTHER_MOVE | SWITCH }" and pins it
# numerically — its realised s26 frequencies 43.6/27.3/13.6/5.2/3.0/**7.2**%
# end in the switch class, and s26's measured tape switch fraction is 0.0719.
# The design cycle's own probe code (`y12_to_y6`) uses the same order.
#
# Nothing cross-references these indices between the head and the probe, so the
# ordering is not load-bearing for the loss — but a head whose class 4 is
# SWITCH read against a header whose class 4 is OTHER_MOVE is a readout bug
# waiting to happen, and the header is the contract.
N_CLASSES = 6
OTHER_MOVE = 4
SWITCH = 5

# Width of the env's `[kind, id, flags]` seam. Mirrors
# rl.envs.showdown.OPP_CHOICE_DIM, which the agent side must not import
# poke_env to read; the two are asserted equal in tests.
CHOICE_DIM = 3

# Where the label space is legislated: `aux_label_space` exists so R0-1 can
# stamp the adopted space in meta.yaml and it cannot be changed silently at
# launch — not so it can be swept.
LABEL_SPACES = ("l6",)

# The id suffix's opponent-move block, and the id scale, mirroring
# rl.envs.showdown._fill_ids / EntityTokenizer (which hardcodes the same 256.0).
# Every OTHER offset comes from the tokenizer that `canonicalise` is handed, so
# this module never has to import poke_env or restate the encoder layout.
_OPP_MOVE_ID_OFF = 16
_ID_SCALE = 256.0
# embed_battle's global block: vec[2] = opponent fainted count / 6.
_OPP_FAINT_IDX = 2
# Within an opponent mon block: [0] revealed flag, then _fill_mon's own layout,
# whose first three fields are hp, fainted, is-active.
_REVEALED, _FAINTED, _IS_ACTIVE = 0, 2, 3


class OppActionHead(nn.Module):
    """The pointer scorer over the six L6 classes (B6), OWNED BY `PPOAgent` AND
    NOT BY THE ACTOR.

        logit_j      = scorer([ctx || opp_move_token_j]) , j = 0..3
        logit_OTHER  = scorer([ctx || null_token])
        logit_SWITCH = scorer([ctx || opp_bench_pool_token])
        + a 6-dim slot bias

    Agent ownership is load-bearing, not stylistic: `actor.state_dict()` keeps
    its key set and its 626,059 params, so `eval_checkpoint.py`,
    `score_ladder.py` and `d22_dormant_rank.py` all run against a D25
    checkpoint UNMODIFIED (R0-2b).

    A plain `Linear(ctx -> 6)` head would be ill-posed, and that is measured
    rather than argued: `ctx` is `ctx_net` over MAX-POOLED team features, so
    opponent slot identity is destroyed before ctx exists, and the identical
    linear ctx probe cannot decode even the actor's OWN greedy action (gain
    -0.061, worse than the marginal). Every logit in this architecture is
    `scorer([ctx || entity])`, so heads and estimators must be scorer-shaped.

    `null_token` is the one added entity: a LEARNED 128-d vector (+128 params)
    standing for "some move that is not in the four slots". It is initialised
    off zero on purpose — an empty bench pools to the all-zero vector, and
    OTHER_MOVE must not be the same input as an empty-bench SWITCH.
    """

    def __init__(
        self,
        ctx_dim: int,
        entity_dim: int,
        sizes: list[int] = (96,),
        n_classes: int = N_CLASSES,
    ):
        super().__init__()
        layers: list[nn.Module] = []
        in_dim = ctx_dim + entity_dim
        for width in sizes:
            layers += [nn.Linear(in_dim, width), nn.ReLU()]
            in_dim = width
        layers.append(nn.Linear(in_dim, 1))
        self.scorer = nn.Sequential(*layers)
        self.null_token = nn.Parameter(torch.zeros(entity_dim))
        self.slot_bias = nn.Parameter(torch.zeros(n_classes))

    def init_head(self, gain: float) -> None:
        """`EntityDeepSetsNet.init_head`'s convention: Xavier on every Linear,
        zero biases, std-0.02 on the entity-space token, and the FINAL scorer
        layer rescaled by `gain`. `slot_bias` stays at zero and is NOT scaled —
        it is what absorbs the class marginal at the optimum, which is the
        design against C3(a) (a head that fits P(class) and calls it a belief).
        """
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
        nn.init.normal_(self.null_token, std=0.02)
        with torch.no_grad():
            self.scorer[-1].weight.mul_(gain)

    def forward(
        self, ctx: torch.Tensor, opp_moves: torch.Tensor, opp_bench: torch.Tensor
    ) -> torch.Tensor:
        """(B, 384), (B, 4, 128), (B, 128) -> (B, 6) unmasked logits."""
        batch = ctx.shape[0]
        entities = torch.cat(
            [opp_moves, self.null_token.expand(batch, 1, -1), opp_bench.unsqueeze(1)],
            dim=1,
        )  # (B, 6, entity_dim), class order: slots 0-3, OTHER_MOVE, SWITCH
        pairs = torch.cat(
            [ctx.unsqueeze(1).expand(-1, entities.shape[1], -1), entities], dim=-1
        )
        return self.scorer(pairs).squeeze(-1) + self.slot_bias


def canonicalise(
    obs: torch.Tensor, choice: torch.Tensor, layout
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, float]]:
    """Env labels -> (target, allow, valid, stats), ONCE PER ROLLOUT (B12).

    `obs` is the flat (B, OBS_DIM) buffered observation, `choice` the (B, 3)
    `[kind, id, flags]` the env emitted for the SAME rows, and `layout` the
    net's own `EntityTokenizer` — the authority on where things are, so no
    offset is restated here. Done inside the epoch x minibatch loop instead
    this costs 16x and surfaces as an unexplained update-time regression.

    A row is VALID — i.e. contributes to the loss — iff it carries a real
    decision, was not an aliased turn, its label is legal, and its id matched
    at most one slot. Everything else is DROPPED, never zero-filled:

    - ALIASED (B10). On gen-1 placeholder turns (sleep / freeze / recharge /
      partial trap) poke-env re-bases the opponent's move list, so a move slot
      stops naming a move; 4.0%-10.3% of paired decisions across the five
      measured tapes. The label is not corrupted under the identity seam, but
      every constant in the pre-registration — including the +0.008/+0.015
      oracle identity — was measured on the filtered set, so this is a
      read-alignment requirement. An aliased row reaching the loss is a HARD
      FAIL, asserted by the caller.
    - ILLEGAL LABEL (B11). Measured 0.0000 on all five tapes and on the frozen
      s36 reference, so this path should never execute; one occurrence would
      otherwise put the label on a -1e8 logit and produce a ~1e8 CE term.
    - FRAME COLLISION. The injectivity argument is incomplete — `_species_id`
      returns 0 for out-of-dex species and unrevealed slots are also 0 — so
      the ambiguous case is dropped and counted rather than argued away.
    """
    kind, ident, flags = choice[:, 0], choice[:, 1], choice[:, 2]
    # THE FRAME: this row's own id suffix, opponent-move block (B4).
    off = layout.id_off + _OPP_MOVE_ID_OFF
    slot_ids = (obs[:, off : off + 4] * _ID_SCALE).round().long()  # (B, 4)

    slot_legal = slot_ids != 0
    # SWITCH is legal iff a LIVE NON-ACTIVE opponent mon exists. The faint count
    # is public (embed_battle's global block), which is why this needs no
    # privileged read — but the count ALONE is not enough, and that was a bug
    # the frozen tapes could not have caught. "6 - 1 - faints" assumes the
    # opponent's active is ALIVE; on a FORCED POST-FAINT REPLACEMENT it is not,
    # so with 5 fainted the one survivor sits on the bench and IS switchable
    # while the count says otherwise. Measured live at 0.12% of decisions — a
    # rate that would have hard-failed R0-5(d) at read time (B11). Whether the
    # forced replacements themselves belong in the loss is C10, still open;
    # this fixes only their LEGALITY.
    opp_faints = (obs[:, _OPP_FAINT_IDX] * 6.0).round().long()
    mons = obs[:, layout.opp_mon_off : layout.opp_mon_off + 6 * (layout.mon_dim + 1)]
    mons = mons.view(obs.shape[0], 6, layout.mon_dim + 1)
    active_alive = (
        (mons[:, :, _REVEALED] > 0.5)
        & (mons[:, :, _IS_ACTIVE] > 0.5)
        & (mons[:, :, _FAINTED] <= 0.5)
    ).any(dim=1).long()
    switch_legal = ((6 - opp_faints - active_alive) >= 1).unsqueeze(-1)
    other_legal = torch.ones_like(switch_legal)
    allow = torch.cat([slot_legal, other_legal, switch_legal], dim=-1)  # (B, 6)

    is_move = kind == 1
    match = slot_legal & (slot_ids == ident.unsqueeze(-1))
    n_match = match.sum(dim=-1)
    first = match.to(torch.int8).argmax(dim=-1)
    # Any switch -> SWITCH (L6 does not name the target). A slotted move -> its
    # slot. An unslotted move, id 0 (recharge, and anything outside gen 1),
    # or Struggle -> OTHER_MOVE.
    target = torch.where(
        kind == 0,
        torch.full_like(first, SWITCH),
        torch.where(n_match > 0, first, torch.full_like(first, OTHER_MOVE)),
    ).long()

    present = (flags & 1) != 0
    aliased = (flags & 2) != 0
    collision = is_move & (n_match > 1)
    legal = allow.gather(1, target.unsqueeze(-1)).squeeze(-1)
    usable = present & ~aliased
    valid = usable & legal & ~collision
    # B10's hard fail, as a structural invariant of this function rather than a
    # counter someone has to remember to read: an aliased row reaching the loss
    # would silently mis-align every constant in the pre-registration.
    assert not bool((valid & aliased).any()), "aliased row entered the aux loss"

    n = max(obs.shape[0], 1)
    n_usable = int(usable.sum())
    stats = {
        "aux/label_present_frac": float(present.sum()) / n,
        "aux/labelled_frac": float(valid.sum()) / n,
        "aux/aliased_frac": float((present & aliased).sum()) / max(int(present.sum()), 1),
        "aux/illegal_label_frac": float((usable & ~legal).sum()) / max(n_usable, 1),
        "aux/frame_collision_frac": float((usable & collision).sum()) / max(n_usable, 1),
        "aux/switch_frac": float((valid & (target == SWITCH)).sum()) / max(int(valid.sum()), 1),
    }
    return target, allow, valid, stats


def aux_cross_entropy(
    logits: torch.Tensor,
    target: torch.Tensor,
    allow: torch.Tensor,
    valid: torch.Tensor,
) -> torch.Tensor:
    """Mean -log p(y | s) over VALID rows, p masked to the legal classes.

    Routed through `rl/common/masking` with the finite -1e8 sentinel: here the
    masked object genuinely IS a legality vector with the harness's own
    semantics, so reusing the contract is right rather than a coincidence of
    shape. Dropped rows are weighted to exactly zero, and OTHER_MOVE's
    always-legal status is what keeps the >= 1-legal assert from tripping.
    """
    logp = torch.log_softmax(masked_logits(logits, allow), dim=-1)
    nll = -logp.gather(1, target.unsqueeze(-1)).squeeze(-1)
    weight = valid.to(nll.dtype)
    return (nll * weight).sum() / weight.sum().clamp(min=1.0)

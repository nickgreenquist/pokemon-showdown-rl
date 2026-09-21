"""Entity ATTENTION trunk — the R7 architecture screen's arm B
(docs/prior_work/ARCH_SCREEN_SPEC.md, `configs/bc_arch_screen.yaml`).

The DeepSets trunk (rl/networks/entity_deepsets.py) pools its entity vectors
with a permutation-INVARIANT max and hands one context vector to a shared
pointer scorer. Every cross-entity question — "does THIS bench mon wall THAT
opponent move", "is the opponent's revealed Chansey the reason this Explosion
is the play" — has to survive that max. Attention is the minimal change that
lets a token READ another token before the pool: same tokens, same embedding
tables, same pointer head, self-attention inserted between them. That is the
whole hypothesis, and it is why this file reuses `EntityTokenizer` verbatim
rather than re-deriving offsets: if the two arms tokenized differently the
screen would be measuring the tokenizer.

ARCHITECTURE (ARCH_SCREEN_SPEC's "Design", adapted to TODAY's 828-dim
layout — the spec was written against v2/807, before the 20-float id tail):

  21 tokens   1 field, 12 mons (own 6 then opp 6), 8 moves (own 4 then
              opp 4). `EntityTokenizer` produces exactly these; the
              DeepSets trunk consumes 17 of them and leaves the opponent's
              4 move tokens unused, which is the cross this arm exists to
              express.
  input       per-type 2-layer subnets with terminal LayerNorm (the
              `_subnet` shape shared with the DeepSets trunk, at width
              d_model) + the SAME species/move embedding tables
              (embed_dim 64, gen-1 `num`-indexed vocabs 152 / 166).
  position    additive learned embeddings for token TYPE (field/mon/move),
              SIDE (neutral/own/opp) and SLOT (0..5). REQUIRED, not
              decoration: attention is permutation-equivariant, so without
              them "switch to slot 3" is not even expressible, while the
              MLP and the DeepSets pointer both get slot identity free
              from their weight columns. Initialised at std 0.02 with the
              other tables — deliberately small so they do not drown out
              the board (ps-ppo's `_reset_parameters` does the same for its
              learned decision tokens).
  trunk       d_model 128, 2 pre-LN blocks, 4 heads, ff x4, GELU, no
              dropout. Depth matches the ladder-era ps-ppo checkout
              (7fb522c, 2 layers) at 1/8 its width, sized so the ACTOR
              lands BELOW both comparators — the DeepSets actor's 626,059
              and the flat MLP's ACTOR_PARAM_CEILING 681,994 — so a
              credit cannot be read as bought capacity.
  policy      POINTER, exactly the DeepSets alignment: ctx = mean over all
              21 output tokens; logits_i = shared scorer([token_i || ctx])
              + a 10-dim slot bias, with switch action i <-> own-mon token
              1+i and move action 6+j <-> own-move token 13+j (the
              poke-env mapping the encoder already relies on). Masking
              stays OUTSIDE the net (rl/common/masking), as everywhere.
  value       a SEPARATE stack, never shared with the actor (repo
              contract, rl/agents/ppo.py): field token || max-pool over the
              12 mon tokens || max-pool over the 8 move tokens -> MLP ->
              scalar. Never masked.

INIT HAZARD, and it is a NEW one. `_orthogonal_init` must not run over this
net for the DeepSets reason (it would give the embedding tables orthogonal
statistics instead of std 0.02) AND for one more: `nn.MultiheadAttention`
keeps its query/key/value projection in a bare `in_proj_weight` Parameter,
not an `nn.Linear`. An `isinstance(m, nn.Linear)` walk therefore RESCALES
`out_proj` — which IS a Linear subclass — while leaving the qkv projection
at whatever it was, i.e. it would silently re-init half of every attention
block and skip the other half. `init_head` owns the whole init and handles
`in_proj_weight` / `in_proj_bias` explicitly.

GEN 1 ONLY. The gen-4 layout would need item and ability tokens and its own
param budget; refusing loudly beats a silent mis-slice (the tokenizer's own
rule).
"""

import torch
from torch import nn

from rl.networks.entity_deepsets import (
    ACTOR_PARAM_CEILING,
    EntityTokenizer,
    _subnet,
    resolve_layout,
)

# Token layout of the 21-token sequence, in the order the tokenizer emits
# them. These indices ARE the pointer head's contract with the encoder.
FIELD_TOKEN = 0
MON_TOKENS = slice(1, 13)        # own 1..6, opp 7..12
OWN_MON_TOKENS = slice(1, 7)
MOVE_TOKENS = slice(13, 21)      # own 13..16, opp 17..20
OWN_MOVE_TOKENS = slice(13, 17)
N_TOKENS = 21

# Additive-embedding vocabularies.
_TYPE_FIELD, _TYPE_MON, _TYPE_MOVE = 0, 1, 2
_SIDE_NEUTRAL, _SIDE_OWN, _SIDE_OPP = 0, 1, 2
_N_TYPES, _N_SIDES, _N_SLOTS = 3, 3, 6


def _token_ids() -> tuple[list[int], list[int], list[int]]:
    """(type, side, slot) index per token, in emission order. Built here
    rather than typed as three literal lists so the three tables cannot
    drift out of step with the slices above."""
    types = [_TYPE_FIELD] + [_TYPE_MON] * 12 + [_TYPE_MOVE] * 8
    sides = (
        [_SIDE_NEUTRAL]
        + [_SIDE_OWN] * 6 + [_SIDE_OPP] * 6
        + [_SIDE_OWN] * 4 + [_SIDE_OPP] * 4
    )
    slots = [0] + list(range(6)) * 2 + list(range(4)) * 2
    assert len(types) == len(sides) == len(slots) == N_TOKENS
    return types, sides, slots


class _Block(nn.Module):
    """One pre-LN transformer block: x + Attn(LN(x)), then x + FF(LN(x)).

    Written out rather than `nn.TransformerEncoderLayer` for two reasons
    that both bite in this repo: the fused fast path is a moving target
    across torch versions (and `tests/test_tree_decision_golden.py`-style
    pinning wants one forward, not a version-dependent one), and the init
    hazard above needs `self.attn.in_proj_weight` reachable by name. The
    parameter count is identical to the stock layer's.
    """

    def __init__(self, d_model: int, n_heads: int, ff_mult: float = 4.0):
        super().__init__()
        self.norm_attn = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.norm_ff = nn.LayerNorm(d_model)
        hidden = int(round(d_model * ff_mult))
        self.ff = nn.Sequential(
            nn.Linear(d_model, hidden), nn.GELU(), nn.Linear(hidden, d_model)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.norm_attn(x)
        # No key_padding_mask: all 21 tokens always exist. A fainted or
        # unrevealed mon is a zeroed/flagged token, not an absent one —
        # exactly what the DeepSets max-pool sees, so the two arms read the
        # same board.
        attn, _ = self.attn(h, h, h, need_weights=False)
        x = x + attn
        return x + self.ff(self.norm_ff(x))


class EntityAttentionNet(nn.Module):
    """One head of the attention architecture: `out_dim == N_ACTIONS` (10 at
    gen 1) builds the pointer policy, `out_dim == 1` the value stack.
    PPOAgent constructs one of each — separate stacks, nothing shared.

    The constructor mirrors `EntityDeepSetsNet(in_dim, out_dim, ...)` so the
    same `trunk_kwargs:` plumbing, the same checkpoint round trip and the
    same `init_head(gain)` call site all work unchanged.
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        species_vocab: int = 152,
        move_vocab: int = 166,
        embed_dim: int = 64,
        d_model: int = 128,
        n_layers: int = 2,
        n_heads: int = 4,
        ff_mult: float = 4.0,
        scorer_sizes: list[int] = (256,),
        value_sizes: list[int] = (384, 384),
        layout: str = "gen1",
    ):
        super().__init__()
        lay = resolve_layout(layout)
        if lay.name != "gen1":
            raise ValueError(
                f"entity attention is gen-1 only, got layout {lay.name!r}: the "
                "gen-4 board needs item and ability tokens and its own param "
                "budget — build that explicitly rather than mis-slicing here"
            )
        n_actions = lay.n_actions
        if out_dim not in (n_actions, 1):
            raise ValueError(
                f"out_dim must be {n_actions} (policy) or 1 (value), got {out_dim}"
            )
        if d_model % n_heads:
            raise ValueError(f"d_model {d_model} not divisible by n_heads {n_heads}")
        if n_layers < 1:
            raise ValueError(f"n_layers must be >= 1, got {n_layers}")
        self.is_policy = out_dim == n_actions
        self.layout = lay
        self.d_model = d_model
        self.n_layers = n_layers
        self.n_heads = n_heads
        # THE tokenizer, not a copy of it: same slices, same id recovery,
        # same loud failure when the encoder flags are missing.
        self.tokenizer = EntityTokenizer(in_dim, species_vocab, move_vocab, lay)
        self.species_emb = nn.Embedding(species_vocab, embed_dim)
        self.move_emb = nn.Embedding(move_vocab, embed_dim)
        # Per-type input subnets, the DeepSets `_subnet` shape at width
        # d_model (2-layer, terminal LayerNorm) — so a token enters the
        # trunk already normalised, which is what pre-LN residual streams
        # want and what ps-ppo's `_build_subnet` does.
        self.mon_net = _subnet(self.tokenizer.mon_token_dim + embed_dim, d_model)
        self.move_net = _subnet(self.tokenizer.move_dim + embed_dim, d_model)
        self.field_net = _subnet(self.tokenizer.global_dim, d_model)
        self.type_emb = nn.Embedding(_N_TYPES, d_model)
        self.side_emb = nn.Embedding(_N_SIDES, d_model)
        self.slot_emb = nn.Embedding(_N_SLOTS, d_model)
        types, sides, slots = _token_ids()
        # Buffers, so the ids ride into the state_dict's device moves and a
        # checkpoint cannot load a net whose token order changed silently.
        self.register_buffer("type_ids", torch.tensor(types, dtype=torch.long))
        self.register_buffer("side_ids", torch.tensor(sides, dtype=torch.long))
        self.register_buffer("slot_ids", torch.tensor(slots, dtype=torch.long))
        self.blocks = nn.ModuleList(
            _Block(d_model, n_heads, ff_mult) for _ in range(n_layers)
        )
        # Pre-LN stacks end in a norm, or the residual stream reaches the
        # head unnormalised and its scale grows with depth.
        self.norm_out = nn.LayerNorm(d_model)
        if self.is_policy:
            scorer_in = 2 * d_model  # [token || ctx]
            scorer: list[nn.Module] = []
            for width in scorer_sizes:
                scorer += [nn.Linear(scorer_in, width), nn.ReLU()]
                scorer_in = width
            scorer.append(nn.Linear(scorer_in, 1))
            self.scorer = nn.Sequential(*scorer)
            self.slot_bias = nn.Parameter(torch.zeros(out_dim))
        else:
            value_in = 3 * d_model  # field || mon pool || move pool
            value: list[nn.Module] = []
            for width in value_sizes:
                value += [nn.Linear(value_in, width), nn.ReLU()]
                value_in = width
            value.append(nn.Linear(value_in, 1))
            self.value_net = nn.Sequential(*value)
        self.param_count = sum(p.numel() for p in self.parameters())
        # The same R0-2 gate the DeepSets actor carries: over the flat MLP
        # actor's count the screen tests capacity, not structure.
        if self.is_policy:
            assert self.param_count <= ACTOR_PARAM_CEILING, (
                f"actor {self.param_count} params > ceiling {ACTOR_PARAM_CEILING} (K2)"
            )

    def init_head(self, gain: float) -> None:
        """The net's whole init, the DeepSets recipe plus the attention
        blocks: Xavier on every Linear, zero biases, std-0.02 normal on every
        embedding table (the entity tables AND the three additive
        type/side/slot tables), and the FINAL layer's weight rescaled by
        `gain` (0.01 policy — a near-uniform initial policy; 1.0 value).
        LayerNorms keep their ones/zeros default.

        `nn.MultiheadAttention.in_proj_weight` gets its OWN branch because it
        is a bare Parameter on the MHA module. `out_proj` needs no special
        case — it is an `nn.Linear` subclass and a child module, so
        `self.modules()` yields it and the Linear branch below covers it.
        That asymmetry is exactly the hazard: a Linear-only walk covers
        `out_proj` and silently skips the qkv projection.
        """
        for module in self.modules():
            if isinstance(module, nn.MultiheadAttention):
                nn.init.xavier_uniform_(module.in_proj_weight)
                if module.in_proj_bias is not None:
                    nn.init.zeros_(module.in_proj_bias)
            elif isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, std=0.02)
        final = self.scorer[-1] if self.is_policy else self.value_net[-1]
        with torch.no_grad():
            final.weight.mul_(gain)

    def _tokens(self, x: torch.Tensor) -> torch.Tensor:
        """Flat obs -> (B, 21, d_model), positions added."""
        tok = self.tokenizer(x)
        mons = self.mon_net(
            torch.cat([tok["mons"], self.species_emb(tok["species_ids"])], dim=-1)
        )  # (B, 12, d_model)
        moves = self.move_net(
            torch.cat([tok["moves"], self.move_emb(tok["move_ids"])], dim=-1)
        )  # (B, 8, d_model) — ALL EIGHT, opponent's included.
        field = self.field_net(tok["field"]).unsqueeze(1)  # (B, 1, d_model)
        seq = torch.cat([field, mons, moves], dim=1)
        pos = (
            self.type_emb(self.type_ids)
            + self.side_emb(self.side_ids)
            + self.slot_emb(self.slot_ids)
        )  # (21, d_model)
        return seq + pos

    def forward(self, x: torch.Tensor, return_features: bool = False) -> torch.Tensor:
        if return_features:
            raise ValueError(
                "return_features is the DeepSets aux-head seam (D25); the "
                "attention trunk has no aux head"
            )
        seq = self._tokens(x)
        for block in self.blocks:
            seq = block(seq)
        seq = self.norm_out(seq)
        if not self.is_policy:
            pooled = torch.cat(
                [seq[:, FIELD_TOKEN], seq[:, MON_TOKENS].amax(dim=1),
                 seq[:, MOVE_TOKENS].amax(dim=1)],
                dim=-1,
            )
            return self.value_net(pooled)
        # Pointer alignment, the DeepSets trunk's exactly: switch action i
        # <-> own-mon token 1+i, move action 6+j <-> own-move token 13+j.
        ctx = seq.mean(dim=1)
        entities = torch.cat([seq[:, OWN_MON_TOKENS], seq[:, OWN_MOVE_TOKENS]], dim=1)
        pairs = torch.cat(
            [entities, ctx.unsqueeze(1).expand(-1, entities.shape[1], -1)], dim=-1
        )
        return self.scorer(pairs).squeeze(-1) + self.slot_bias

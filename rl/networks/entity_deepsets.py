"""Entity DeepSets trunk — Rung 2 (STRUCTURE) of the pure self-play ladder
(configs/showdown_sp_struct12m.yaml, ratified with DESIGN r7).

Huang & Lee's network, minus the parts gen 1 does not have (no items, no
abilities): entity embeddings for species and moves, a shared per-Pokemon
subnet, DeepSets max-pooling over each team, and a shared PER-ACTION scoring
head replacing the flat [512,512] MLP readout. Source: prior_work/README.md's
H&L entry and the yuzeh/metagrok clone (MIT); the pointer head is
ARCH_SCREEN_SPEC's minus the attention that feeds it. The sharing IS the
hypothesis: what the net learns about "how good is switching to a Rhydon"
transfers across slots and across games, which a flat 512->10 readout cannot
express.

Recipe provenance, since none of it is free-floating: activation ReLU
(H&L's, metagrok models/v2_repro.py); subnet shape 2-layer with terminal
LayerNorm (ps-ppo's `_build_subnet`, at width `entity_dim` rather than their
2x expansion — the ratified param sketch pins it); init Xavier + std-0.02
embeddings + rescaled final layer (ps-ppo's `_reset_parameters` recipe, per
the config's INIT HAZARD note — `_orthogonal_init` must never run over this
net, K4).

The TOKENIZER is shared with the attention screen (ARCH_SCREEN_SPEC,
verbatim): a reshape layer over the flat obs, slices derived from
`rl.envs.showdown` constants and asserted at construction. If the constants
disagree with the obs the env produced — most likely a forgotten
POKEMON_RL_ENCODER_V2 / POKEMON_RL_ENCODER_IDS env var — construction fails
loudly (the R0-1 seam). The DeepSets trunk consumes the field token, the 12
mon tokens and the 4 own-move tokens; the 4 opponent-move tokens exist for
the attention screen and are not run through the subnet here (the ratified
context is field + pools + actives, 640-d — opponent-threat information
reaches the policy through the mon tokens' matchup and speed-edge features).

Masking stays OUTSIDE the net (rl/common/masking, applied by PPOAgent at
collection, update and eval alike); the value variant is a fully separate
stack, never masked, no shared trunk (repo contract, ppo.py — H&L DO share;
deliberate deviation, recorded).
"""

import torch
from torch import nn

# R0-2 HARD CEILING: the flat [512,512] MLP actor on v2/808 — 808*512+512
# + 512*512+512 + 512*10+10, verified against a live construction 2026-08-08.
# Over it, the rung tests capacity and not structure (K2).
ACTOR_PARAM_CEILING = 681_994

# The identity suffix: 6 own + 6 opp species, then 4 own + 4 opp moves,
# each emitted as id/256.0 (rl/envs/showdown.py::_fill_ids).
_N_SPECIES_IDS = 12
_N_MOVE_IDS = 8


class EntityTokenizer(nn.Module):
    """Reshape layer over the flat encoder obs: 21 tokens + id indices.

    Stateless (no parameters). Layout is derived from `rl.envs.showdown`
    constants at construction and asserted against the declared obs width,
    so a flag/encoder mismatch dies here rather than mis-slicing silently.

    Tokens (ARCH_SCREEN_SPEC, verbatim):
      field  (B, GLOBAL_DIM)      the global block
      mons   (B, 12, 50)          per-mon: [flag || mon block || active
                                  extras * that mon's own is-active bit].
                                  Own mons prepend a constant 1.0 where
                                  opponent mons carry their revealed flag,
                                  so both sides share one input projection.
      moves  (B, 8, MOVE_DIM)     own 4 (move-action order) + opponent's
                                  prior-filled 4
      species_ids (B, 12) long    embedding rows, own 6 then opp 6
      move_ids    (B, 8)  long    embedding rows, own 4 then opp 4
      own_active / opp_active (B, 6)  the is-active bits, for pooling the
                                  active mon's vector out of the subnet
    """

    def __init__(self, in_dim: int, species_vocab: int, move_vocab: int):
        super().__init__()
        # Deferred import (train.py's ENCODER_FINGERPRINT precedent): only
        # entity-trunk construction pays for poke_env.
        from rl.envs import showdown as sd

        if sd.ID_DIM == 0:
            raise ValueError(
                "entity trunk needs the id suffix: set POKEMON_RL_ENCODER_IDS=1 "
                "(and POKEMON_RL_ENCODER_V2=1) in the process environment"
            )
        expected = sd.OBS_DIM
        if in_dim != expected:
            raise ValueError(
                f"obs width {in_dim} != encoder OBS_DIM {expected}: the env "
                "and the tokenizer disagree on the encoder flags"
            )
        self.global_dim = sd.GLOBAL_DIM
        self.mon_dim = sd.MON_DIM
        self.active_dim = sd.ACTIVE_DIM
        self.move_dim = sd.MOVE_DIM
        self.species_vocab = species_vocab
        self.move_vocab = move_vocab
        self.own_mon_off = sd.GLOBAL_DIM
        self.own_act_off = self.own_mon_off + 6 * sd.MON_DIM
        self.own_move_off = self.own_act_off + sd.ACTIVE_DIM
        self.opp_mon_off = self.own_move_off + 4 * sd.MOVE_DIM
        self.opp_act_off = self.opp_mon_off + 6 * (sd.MON_DIM + 1)
        self.opp_move_off = self.opp_act_off + sd.ACTIVE_DIM
        self.id_off = self.opp_move_off + 4 * sd.MOVE_DIM
        assert self.id_off + sd.ID_DIM == expected, "layout drifted from OBS_DIM"
        # Token width: flag/const 1 + mon block + gated active extras.
        self.mon_token_dim = 1 + sd.MON_DIM + sd.ACTIVE_DIM

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        batch = x.shape[0]
        field = x[:, : self.global_dim]
        own = x[:, self.own_mon_off : self.own_act_off].view(batch, 6, self.mon_dim)
        own_extras = x[:, self.own_act_off : self.own_move_off]
        own_moves = x[:, self.own_move_off : self.opp_mon_off].view(batch, 4, self.move_dim)
        opp = x[:, self.opp_mon_off : self.opp_act_off].view(batch, 6, self.mon_dim + 1)
        opp_flag, opp_block = opp[:, :, :1], opp[:, :, 1:]
        opp_extras = x[:, self.opp_act_off : self.opp_move_off]
        opp_moves = x[:, self.opp_move_off : self.id_off].view(batch, 4, self.move_dim)
        # [+2] of the mon block is that mon's own is-active bit (_fill_mon).
        own_active, opp_active = own[:, :, 2], opp_block[:, :, 2]
        mons = torch.cat(
            [
                torch.cat(
                    [x.new_ones(batch, 6, 1), own,
                     own_extras.unsqueeze(1) * own_active.unsqueeze(-1)],
                    dim=-1,
                ),
                torch.cat(
                    [opp_flag, opp_block,
                     opp_extras.unsqueeze(1) * opp_active.unsqueeze(-1)],
                    dim=-1,
                ),
            ],
            dim=1,
        )
        # id/256.0 -> row index; exact in float32, clamp is belt-and-braces
        # against out-of-table dirt, never a semantic remap.
        ids = (x[:, self.id_off :] * 256.0).round().long()
        return {
            "field": field,
            "mons": mons,
            "moves": torch.cat([own_moves, opp_moves], dim=1),
            "species_ids": ids[:, :_N_SPECIES_IDS].clamp(0, self.species_vocab - 1),
            "move_ids": ids[:, _N_SPECIES_IDS:].clamp(0, self.move_vocab - 1),
            "own_active": own_active,
            "opp_active": opp_active,
        }


def _subnet(in_dim: int, width: int) -> nn.Sequential:
    """ps-ppo's `_build_subnet` shape at constant width: 2-layer, terminal
    LayerNorm; ReLU per H&L."""
    return nn.Sequential(
        nn.Linear(in_dim, width), nn.ReLU(),
        nn.Linear(width, width), nn.LayerNorm(width),
    )


class EntityDeepSetsNet(nn.Module):
    """One head of the Rung 2 architecture: out_dim 10 builds the pointer
    policy (shared per-action scorer + slot bias), out_dim 1 the value stack
    (same trunk shape over `value_sizes`, scalar head). PPOAgent constructs
    one of each — separate stacks, nothing shared between them."""

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        species_vocab: int = 152,
        move_vocab: int = 166,
        embed_dim: int = 64,
        entity_dim: int = 128,
        pool: str = "max",
        ctx_sizes: list[int] = (384, 384),
        scorer_sizes: list[int] = (256,),
        value_sizes: list[int] = (384, 384),
        privileged_dim: int = 0,
    ):
        super().__init__()
        if out_dim not in (10, 1):
            raise ValueError(f"out_dim must be 10 (policy) or 1 (value), got {out_dim}")
        if pool != "max":
            raise ValueError(f"only DeepSets max-pool is implemented (H&L's choice), got {pool!r}")
        self.is_policy = out_dim == 10
        self.tokenizer = EntityTokenizer(in_dim, species_vocab, move_vocab)
        self.species_emb = nn.Embedding(species_vocab, embed_dim)
        self.move_emb = nn.Embedding(move_vocab, embed_dim)
        self.mon_net = _subnet(self.tokenizer.mon_token_dim + embed_dim, entity_dim)
        self.move_net = _subnet(self.tokenizer.move_dim + embed_dim, entity_dim)
        self.field_net = _subnet(self.tokenizer.global_dim, entity_dim)
        # D18 privileged critic: the value stack may take the opponent seat's
        # own-side block (rl/envs/showdown.py::privileged_block) appended
        # AFTER the obs. Value-only — the actor's input never widens (the
        # Baisero & Amato V(h,s) construction, and the locked eval protocol,
        # both live on that asymmetry). The privileged tokens go through the
        # SAME mon/move subnets and embeddings as the observed ones — the
        # entity space is shared, only the pooling slots widen.
        if privileged_dim:
            if self.is_policy:
                raise ValueError("privileged_dim is critic-only: the actor never widens")
            expected = (
                6 * self.tokenizer.mon_dim + self.tokenizer.active_dim
                + 4 * self.tokenizer.move_dim + 10
            )
            if privileged_dim != expected:
                raise ValueError(
                    f"privileged_dim {privileged_dim} != encoder PRIV_DIM {expected}: "
                    "the env and the critic disagree on the privileged layout "
                    "(check the POKEMON_RL_ENCODER_V2 / POKEMON_RL_ENCODER_IDS "
                    "env vars — the id tail is required)"
                )
        self.privileged_dim = privileged_dim
        # context: field || own pool || opp pool || own active || opp active
        # (|| priv pool || priv active || priv-move pool when privileged).
        ctx_in = (5 + (3 if privileged_dim else 0)) * entity_dim
        sizes = list(ctx_sizes if self.is_policy else value_sizes)
        layers: list[nn.Module] = []
        for width in sizes:
            layers += [nn.Linear(ctx_in, width), nn.ReLU()]
            ctx_in = width
        self.ctx_net = nn.Sequential(*layers)
        if self.is_policy:
            scorer_in = ctx_in + entity_dim
            scorer: list[nn.Module] = []
            for width in scorer_sizes:
                scorer += [nn.Linear(scorer_in, width), nn.ReLU()]
                scorer_in = width
            scorer.append(nn.Linear(scorer_in, 1))
            self.scorer = nn.Sequential(*scorer)
            self.slot_bias = nn.Parameter(torch.zeros(out_dim))
        else:
            self.head = nn.Linear(ctx_in, 1)
        self.param_count = sum(p.numel() for p in self.parameters())
        # R0-2, asserted at construction: over the flat MLP actor's count the
        # rung tests capacity, not structure.
        if self.is_policy:
            assert self.param_count <= ACTOR_PARAM_CEILING, (
                f"actor {self.param_count} params > ceiling {ACTOR_PARAM_CEILING} (K2)"
            )

    def init_head(self, gain: float) -> None:
        """The net's whole init (ps-ppo's recipe, per the config's INIT
        HAZARD note): Xavier on every Linear, zero biases, std-0.02 normal on
        the embedding tables, and the FINAL layer's weight rescaled by
        `gain` (0.01 policy — near-uniform initial policy, the same role the
        MLP's orthogonal head gain plays; 1.0 value). `_orthogonal_init`
        must never run over this net: it would hit the embedding tables (K4).
        LayerNorms keep their ones/zeros default."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, std=0.02)
        final = self.scorer[-1] if self.is_policy else self.head
        with torch.no_grad():
            final.weight.mul_(gain)

    def _priv_features(self, priv: torch.Tensor) -> list[torch.Tensor]:
        """Pooled entity features from the opponent seat's own-side block —
        tokenized by the SAME rules the tokenizer applies to our own side
        (constant flag 1, extras gated by the is-active bit at mon offset
        +2, ids recovered as round(x*256))."""
        batch = priv.shape[0]
        md, ad, vd = self.tokenizer.mon_dim, self.tokenizer.active_dim, self.tokenizer.move_dim
        mons = priv[:, : 6 * md].view(batch, 6, md)
        extras = priv[:, 6 * md : 6 * md + ad]
        moves = priv[:, 6 * md + ad : 6 * md + ad + 4 * vd].view(batch, 4, vd)
        ids = (priv[:, -10:] * 256.0).round().long()
        active = mons[:, :, 2]
        tokens = torch.cat(
            [priv.new_ones(batch, 6, 1), mons,
             extras.unsqueeze(1) * active.unsqueeze(-1)],
            dim=-1,
        )
        pmons = self.mon_net(torch.cat(
            [tokens, self.species_emb(ids[:, :6].clamp(0, self.tokenizer.species_vocab - 1))],
            dim=-1,
        ))
        pmoves = self.move_net(torch.cat(
            [moves, self.move_emb(ids[:, 6:].clamp(0, self.tokenizer.move_vocab - 1))],
            dim=-1,
        ))
        return [
            pmons.amax(dim=1),
            (pmons * active.unsqueeze(-1)).sum(dim=1),
            pmoves.amax(dim=1),
        ]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        priv = None
        if self.privileged_dim:
            x, priv = x[:, : -self.privileged_dim], x[:, -self.privileged_dim :]
        tok = self.tokenizer(x)
        mons = self.mon_net(
            torch.cat([tok["mons"], self.species_emb(tok["species_ids"])], dim=-1)
        )  # (B, 12, entity_dim)
        own_moves = self.move_net(
            torch.cat(
                [tok["moves"][:, :4], self.move_emb(tok["move_ids"][:, :4])], dim=-1
            )
        )  # (B, 4, entity_dim)
        # DeepSets max over each team (permutation-invariant, which is the
        # point); the active mon's vector selected by its own is-active bit
        # (a one-hot -- or all-zero when no active, leaving a zero vector).
        ctx_parts = [
            self.field_net(tok["field"]),
            mons[:, :6].amax(dim=1),
            mons[:, 6:].amax(dim=1),
            (mons[:, :6] * tok["own_active"].unsqueeze(-1)).sum(dim=1),
            (mons[:, 6:] * tok["opp_active"].unsqueeze(-1)).sum(dim=1),
        ]
        if priv is not None:
            ctx_parts += self._priv_features(priv)
        ctx = self.ctx_net(torch.cat(ctx_parts, dim=-1))
        if not self.is_policy:
            return self.head(ctx)
        # Pointer alignment (the exact poke-env mapping the encoder relies
        # on): switch action i <-> own-mon vector i, move action 6+j <->
        # own-move vector j. ONE shared scorer over all 10 [ctx || entity]
        # pairs; masking is applied outside, by the caller.
        entities = torch.cat([mons[:, :6], own_moves], dim=1)  # (B, 10, entity_dim)
        pairs = torch.cat(
            [ctx.unsqueeze(1).expand(-1, entities.shape[1], -1), entities], dim=-1
        )
        return self.scorer(pairs).squeeze(-1) + self.slot_bias

"""Entity DeepSets trunk — Rung 2 (STRUCTURE) of the pure self-play ladder
(configs/showdown_sp_struct12m.yaml, ratified with DESIGN r7).

Huang & Lee's network, minus the parts gen 1 does not have (no items, no
abilities): entity embeddings for species and moves, a shared per-Pokemon
subnet, DeepSets max-pooling over each team, and a shared PER-ACTION scoring
head replacing the flat [512,512] MLP readout. Source: docs/prior_work/README.md's
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

THE LAYOUT ARGUMENT (JOURNEY step 3, build item BI-G4-2, 2026-09-05): the
tokenizer reads its block widths and id tail from a `TrunkLayout` — `gen1`
(today's path: the `rl.envs.showdown` constants, bit-identical, the goldens in
tests/test_entity_deepsets.py are the proof) or `gen4` (rl/envs/gen4/spec.py's
frozen v0.1 layout, plus item and ability id tables from the wider id tail).
The gen-4 net is the SAME architecture with two more entity embeddings on
the mon token; nothing else changes shape by generation. The gen-1 branch
constructs no new module, so its RNG construction order — and therefore
every gen-1 checkpoint and golden — is untouched.

The TOKENIZER is shared with the attention screen (ARCH_SCREEN_SPEC,
verbatim): a reshape layer over the flat obs, slices derived from the layout
and asserted at construction. If the layout disagrees with the obs the env
produced — most likely a forgotten POKEMON_RL_ENCODER_V2 /
POKEMON_RL_ENCODER_IDS env var at gen 1 — construction fails loudly (the
R0-1 seam). The DeepSets trunk consumes the field token, the 12 mon tokens
and the 4 own-move tokens; the 4 opponent-move tokens exist for the
attention screen and are not run through the subnet here (the ratified
context is field + pools + actives, 640-d — opponent-threat information
reaches the policy through the mon tokens' matchup and speed-edge features).

Masking stays OUTSIDE the net (rl/common/masking, applied by PPOAgent at
collection, update and eval alike); the value variant is a fully separate
stack, never masked, no shared trunk (repo contract, ppo.py — H&L DO share;
deliberate deviation, recorded).
"""

from dataclasses import dataclass

import torch
from torch import nn

# R0-2 HARD CEILING: the flat [512,512] MLP actor on v2/808 — 808*512+512
# + 512*512+512 + 512*10+10, verified against a live construction 2026-08-08.
# Over it, the rung tests capacity and not structure (K2). A GEN-1 rule: the
# gen-4 actor has no flat-MLP comparator at 1,448 dims (that MLP would be
# ~1.0M), so the ceiling is asserted on the gen-1 layout only and the gen-4
# count is STAMPED (rl/train.py meta.yaml `params`) rather than gated.
ACTOR_PARAM_CEILING = 681_994

# The identity suffix: 6 own + 6 opp species, then 4 own + 4 opp moves,
# each emitted as id/256.0 (rl/envs/showdown.py::_fill_ids). Gen 4 appends
# 6 own + 6 opp items and 6 own + 6 opp abilities in the same order
# (rl/envs/gen4/encoder.py, the id tail after `ids_off`).
_N_SPECIES_IDS = 12
_N_MOVE_IDS = 8
_N_ITEM_IDS = 12
_N_ABILITY_IDS = 12

TRUNK_LAYOUTS = ("gen1", "gen4")


@dataclass(frozen=True)
class TrunkLayout:
    """Everything the tokenizer needs to slice a flat obs: block widths, the
    id tail's composition, the vocab sizes the embedding tables must be
    built with, and the privileged block's id tail. `id_items == 0` means the
    layout carries no item / ability ids (gen 1) and the net builds neither
    table."""

    name: str
    global_dim: int
    mon_dim: int
    active_dim: int
    move_dim: int
    id_species: int
    id_moves: int
    id_items: int
    id_abilities: int
    priv_id_dim: int
    species_vocab: int
    move_vocab: int
    item_vocab: int
    ability_vocab: int
    n_actions: int = 10

    @property
    def id_dim(self) -> int:
        return self.id_species + self.id_moves + self.id_items + self.id_abilities

    @property
    def obs_dim(self) -> int:
        return (
            self.global_dim + 6 * self.mon_dim + self.active_dim + 4 * self.move_dim
            + 6 * (self.mon_dim + 1) + self.active_dim + 4 * self.move_dim + self.id_dim
        )

    @property
    def priv_dim(self) -> int:
        return 6 * self.mon_dim + self.active_dim + 4 * self.move_dim + self.priv_id_dim

    @property
    def has_item_ids(self) -> bool:
        return self.id_items > 0


def resolve_layout(layout: "TrunkLayout | str") -> TrunkLayout:
    """`gen1` reads the process's gen-1 encoder constants (deferred import:
    only entity-trunk construction pays for poke_env, and the flags are read
    at that module's import); `gen4` reads the frozen v0.1 layout and the
    pinned vocab. A TrunkLayout passes through."""
    if isinstance(layout, TrunkLayout):
        return layout
    if layout == "gen1":
        from rl.envs import showdown as sd

        if sd.ID_DIM == 0:
            raise ValueError(
                "entity trunk needs the id suffix: set POKEMON_RL_ENCODER_IDS=1 "
                "(and POKEMON_RL_ENCODER_V2=1) in the process environment"
            )
        return TrunkLayout(
            name="gen1", global_dim=sd.GLOBAL_DIM, mon_dim=sd.MON_DIM,
            active_dim=sd.ACTIVE_DIM, move_dim=sd.MOVE_DIM,
            id_species=_N_SPECIES_IDS, id_moves=_N_MOVE_IDS, id_items=0, id_abilities=0,
            priv_id_dim=sd.PRIV_ID_DIM,
            # The gen-1 tables' sizes are the config's (152 / 166 ratified);
            # nothing here asserts them — the gen-1 vocab is `num`-indexed.
            species_vocab=0, move_vocab=0, item_vocab=0, ability_vocab=0,
            n_actions=sd.N_ACTIONS,
        )
    if layout == "gen4":
        from rl.envs.gen4.spec import LAYOUT, N_ACTIONS_GEN4
        from rl.envs.gen4.vocab import VOCAB

        return TrunkLayout(
            name="gen4", global_dim=LAYOUT.global_dim, mon_dim=LAYOUT.mon_dim,
            active_dim=LAYOUT.active_dim, move_dim=LAYOUT.move_dim,
            id_species=LAYOUT.n_id_species, id_moves=LAYOUT.n_id_moves,
            id_items=LAYOUT.n_id_items, id_abilities=LAYOUT.n_id_abilities,
            priv_id_dim=6 + 4 + 6 + 6,
            species_vocab=VOCAB.n_species, move_vocab=VOCAB.n_moves,
            item_vocab=VOCAB.n_items, ability_vocab=VOCAB.n_abilities,
            n_actions=N_ACTIONS_GEN4,
        )
    raise ValueError(f"unknown trunk layout {layout!r}; expected one of {list(TRUNK_LAYOUTS)}")


class EntityTokenizer(nn.Module):
    """Reshape layer over the flat encoder obs: 21 tokens + id indices.

    Stateless (no parameters). Layout is derived from the TrunkLayout at
    construction and asserted against the declared obs width, so a
    flag/encoder mismatch dies here rather than mis-slicing silently.

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
      item_ids    (B, 12) long    gen 4 only: own 6 then opp 6
      ability_ids (B, 12) long    gen 4 only: own 6 then opp 6
      own_active / opp_active (B, 6)  the is-active bits, for pooling the
                                  active mon's vector out of the subnet
    """

    def __init__(
        self,
        in_dim: int,
        species_vocab: int,
        move_vocab: int,
        layout: TrunkLayout | str = "gen1",
        item_vocab: int = 0,
        ability_vocab: int = 0,
    ):
        super().__init__()
        lay = resolve_layout(layout)
        expected = lay.obs_dim
        if in_dim != expected:
            raise ValueError(
                f"obs width {in_dim} != encoder OBS_DIM {expected} ({lay.name} layout): "
                "the env and the tokenizer disagree on the encoder flags / layout"
            )
        self.layout = lay
        self.global_dim = lay.global_dim
        self.mon_dim = lay.mon_dim
        self.active_dim = lay.active_dim
        self.move_dim = lay.move_dim
        self.species_vocab = species_vocab
        self.move_vocab = move_vocab
        self.item_vocab = item_vocab
        self.ability_vocab = ability_vocab
        self.own_mon_off = lay.global_dim
        self.own_act_off = self.own_mon_off + 6 * lay.mon_dim
        self.own_move_off = self.own_act_off + lay.active_dim
        self.opp_mon_off = self.own_move_off + 4 * lay.move_dim
        self.opp_act_off = self.opp_mon_off + 6 * (lay.mon_dim + 1)
        self.opp_move_off = self.opp_act_off + lay.active_dim
        self.id_off = self.opp_move_off + 4 * lay.move_dim
        assert self.id_off + lay.id_dim == expected, "layout drifted from OBS_DIM"
        # Token width: flag/const 1 + mon block + gated active extras.
        self.mon_token_dim = 1 + lay.mon_dim + lay.active_dim

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
        # [+2] of the mon block is that mon's own is-active bit (_fill_mon;
        # gen 4's block opens hp, fainted, is-active the same way).
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
        out = {
            "field": field,
            "mons": mons,
            "moves": torch.cat([own_moves, opp_moves], dim=1),
            "species_ids": ids[:, :_N_SPECIES_IDS].clamp(0, self.species_vocab - 1),
            "move_ids": ids[:, _N_SPECIES_IDS:_N_SPECIES_IDS + _N_MOVE_IDS].clamp(0, self.move_vocab - 1),
            "own_active": own_active,
            "opp_active": opp_active,
        }
        if self.layout.has_item_ids:
            o = _N_SPECIES_IDS + _N_MOVE_IDS
            out["item_ids"] = ids[:, o:o + _N_ITEM_IDS].clamp(0, self.item_vocab - 1)
            o += _N_ITEM_IDS
            out["ability_ids"] = ids[:, o:o + _N_ABILITY_IDS].clamp(0, self.ability_vocab - 1)
        return out


def _subnet(in_dim: int, width: int) -> nn.Sequential:
    """ps-ppo's `_build_subnet` shape at constant width: 2-layer, terminal
    LayerNorm; ReLU per H&L."""
    return nn.Sequential(
        nn.Linear(in_dim, width), nn.ReLU(),
        nn.Linear(width, width), nn.LayerNorm(width),
    )


class EntityDeepSetsNet(nn.Module):
    """One head of the Rung 2 architecture: out_dim N_ACTIONS (10 at gen 1
    and gen 4) builds the pointer policy (shared per-action scorer + slot
    bias), out_dim 1 the value stack (same trunk shape over `value_sizes`,
    scalar head). PPOAgent constructs one of each — separate stacks, nothing
    shared.

    `layout` selects the tokenizer's slicing and, at gen 4, adds the item
    and ability embedding tables to the mon token (the only shape change by
    generation). At gen 4 the four vocab sizes MUST equal the pinned vocab's
    (rl/envs/gen4/vocab.py, row 0 = unknown): a config carrying gen 1's
    152 / 166 into a gen-4 run fails here, not in a silent clamp."""

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
        layout: TrunkLayout | str = "gen1",
        item_vocab: int = 0,
        ability_vocab: int = 0,
    ):
        super().__init__()
        lay = resolve_layout(layout)
        n_actions = lay.n_actions
        if out_dim not in (n_actions, 1):
            raise ValueError(
                f"out_dim must be {n_actions} (policy) or 1 (value), got {out_dim}"
            )
        if pool != "max":
            raise ValueError(f"only DeepSets max-pool is implemented (H&L's choice), got {pool!r}")
        if lay.has_item_ids:
            want = (lay.species_vocab, lay.move_vocab, lay.item_vocab, lay.ability_vocab)
            got = (species_vocab, move_vocab, item_vocab, ability_vocab)
            if got != want:
                raise ValueError(
                    f"{lay.name} layout: (species, move, item, ability) vocab sizes "
                    f"{got} != the pinned vocab's {want} (row 0 = unknown; "
                    "rl/envs/gen4/vocab.py) — set trunk_kwargs to the pinned sizes"
                )
        elif item_vocab or ability_vocab:
            raise ValueError(f"{lay.name} layout carries no item / ability ids")
        self.is_policy = out_dim == n_actions
        self.layout = lay
        self.tokenizer = EntityTokenizer(
            in_dim, species_vocab, move_vocab, lay, item_vocab, ability_vocab
        )
        self.species_emb = nn.Embedding(species_vocab, embed_dim)
        self.move_emb = nn.Embedding(move_vocab, embed_dim)
        # Gen 4 only — constructed AFTER the two gen-1 tables so the gen-1
        # branch's module order (and its RNG stream) is exactly the old one.
        n_mon_embeds = 1
        if lay.has_item_ids:
            self.item_emb = nn.Embedding(item_vocab, embed_dim)
            self.ability_emb = nn.Embedding(ability_vocab, embed_dim)
            n_mon_embeds = 3
        else:
            self.item_emb = self.ability_emb = None
        self.mon_net = _subnet(self.tokenizer.mon_token_dim + n_mon_embeds * embed_dim, entity_dim)
        self.move_net = _subnet(self.tokenizer.move_dim + embed_dim, entity_dim)
        self.field_net = _subnet(self.tokenizer.global_dim, entity_dim)
        # D18 privileged critic: the value stack may take the opponent seat's
        # own-side block (rl/envs/showdown.py::privileged_block, and gen 4's
        # privileged_block_gen4) appended AFTER the obs. Value-only — the
        # actor's input never widens (the Baisero & Amato V(h,s)
        # construction, and the locked eval protocol, both live on that
        # asymmetry). The privileged tokens go through the SAME mon/move
        # subnets and embeddings as the observed ones — the entity space is
        # shared, only the pooling slots widen.
        if privileged_dim:
            if self.is_policy:
                raise ValueError("privileged_dim is critic-only: the actor never widens")
            expected = lay.priv_dim
            if privileged_dim != expected:
                raise ValueError(
                    f"privileged_dim {privileged_dim} != encoder PRIV_DIM {expected} "
                    f"({lay.name} layout): the env and the critic disagree on the "
                    "privileged layout (at gen 1 check the POKEMON_RL_ENCODER_V2 / "
                    "POKEMON_RL_ENCODER_IDS env vars — the id tail is required)"
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
        # rung tests capacity, not structure. Gen 1 only (see the constant).
        if self.is_policy and lay.name == "gen1":
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

    def _mon_embeds(self, species_ids, item_ids=None, ability_ids=None) -> torch.Tensor:
        """The per-mon embedding block: species alone at gen 1; species ||
        item || ability at gen 4 (ids already clamped to their tables)."""
        emb = self.species_emb(species_ids)
        if self.item_emb is None:
            return emb
        return torch.cat([emb, self.item_emb(item_ids), self.ability_emb(ability_ids)], dim=-1)

    def _priv_features(self, priv: torch.Tensor) -> list[torch.Tensor]:
        """Pooled entity features from the opponent seat's own-side block —
        tokenized by the SAME rules the tokenizer applies to our own side
        (constant flag 1, extras gated by the is-active bit at mon offset
        +2, ids recovered as round(x*256)). The id tail is 6 species + 4
        moves at gen 1, plus 6 items + 6 abilities at gen 4."""
        batch = priv.shape[0]
        tk = self.tokenizer
        md, ad, vd = tk.mon_dim, tk.active_dim, tk.move_dim
        mons = priv[:, : 6 * md].view(batch, 6, md)
        extras = priv[:, 6 * md : 6 * md + ad]
        moves = priv[:, 6 * md + ad : 6 * md + ad + 4 * vd].view(batch, 4, vd)
        ids = (priv[:, -self.layout.priv_id_dim:] * 256.0).round().long()
        active = mons[:, :, 2]
        tokens = torch.cat(
            [priv.new_ones(batch, 6, 1), mons,
             extras.unsqueeze(1) * active.unsqueeze(-1)],
            dim=-1,
        )
        species = ids[:, :6].clamp(0, tk.species_vocab - 1)
        items = abilities = None
        if self.item_emb is not None:
            items = ids[:, 10:16].clamp(0, tk.item_vocab - 1)
            abilities = ids[:, 16:22].clamp(0, tk.ability_vocab - 1)
        pmons = self.mon_net(torch.cat(
            [tokens, self._mon_embeds(species, items, abilities)], dim=-1,
        ))
        pmoves = self.move_net(torch.cat(
            [moves, self.move_emb(ids[:, 6:10].clamp(0, tk.move_vocab - 1))],
            dim=-1,
        ))
        return [
            pmons.amax(dim=1),
            (pmons * active.unsqueeze(-1)).sum(dim=1),
            pmoves.amax(dim=1),
        ]

    def _aux_features(self, tok, mons, ctx) -> tuple[torch.Tensor, ...]:
        """D25's auxiliary-head inputs, off the SAME forward the PPO loss makes.

        THE OPPONENT MOVE TOKENS DO NOT EXIST IN THIS NET (D25 B6a). forward()
        runs `move_net` over `tok["moves"][:, :4]` — OWN moves only, exactly as
        the module docstring says — while the tokenizer emits all 8 and nothing
        consumes slots 4:8. The aux path applies the EXISTING subnet and
        embedding to those existing-but-unused tokens: no new module, no new
        parameters, and the pattern is `_priv_features`' verbatim. The
        consequence is disclosed rather than hidden — `move_net` / `move_emb`
        are SHARED trunk weights, so the aux gradient reaches them through a
        path the policy never used, and D25 is an actor-side lever that
        MODIFIES SHARED PARAMETERS (B6b, C6).

        The bench token is pooled here rather than in the agent-owned head
        because the live/non-active mask is TOKEN-side information (revealed
        flag, fainted bit, is-active bit at token offsets 0/2/3) that no
        consumer of a 128-d entity vector could recover.

        Runs only under return_features=True, i.e. only inside `update` and
        only when the lever is on — `forward(x)` and the acting path are
        untouched (R0-7's forward-hook count of 0 over a full eval pass).
        """
        # move_ids are already clamped to the table by the tokenizer.
        opp_moves = self.move_net(
            torch.cat(
                [tok["moves"][:, 4:], self.move_emb(tok["move_ids"][:, 4:])], dim=-1
            )
        )  # (B, 4, entity_dim)
        opp_tok = tok["mons"][:, 6:]
        # Token layout is [revealed flag || mon block || gated extras], and the
        # mon block opens hp, fainted, is-active (_fill_mon).
        live_bench = (
            (opp_tok[:, :, 0] > 0) & (opp_tok[:, :, 2] <= 0) & (opp_tok[:, :, 3] <= 0)
        )  # (B, 6)
        bench = mons[:, 6:]
        floor = torch.full_like(bench, torch.finfo(bench.dtype).min)
        pooled = torch.where(live_bench.unsqueeze(-1), bench, floor).amax(dim=1)
        # All-zero when no revealed live bench slot exists. Note this is NOT
        # the same as "SWITCH is illegal": early in a battle the opponent has
        # five unrevealed live mons and switching is legal while this token is
        # zero. Legality comes from the public faint count, in the canonicaliser.
        opp_bench = torch.where(
            live_bench.any(dim=1, keepdim=True), pooled, torch.zeros_like(pooled)
        )
        return ctx, opp_moves, opp_bench

    def forward(self, x: torch.Tensor, return_features: bool = False) -> torch.Tensor:
        priv = None
        if self.privileged_dim:
            x, priv = x[:, : -self.privileged_dim], x[:, -self.privileged_dim :]
        tok = self.tokenizer(x)
        mons = self.mon_net(
            torch.cat(
                [tok["mons"],
                 self._mon_embeds(tok["species_ids"], tok.get("item_ids"), tok.get("ability_ids"))],
                dim=-1,
            )
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
            if return_features:
                raise ValueError("return_features is actor-only: the critic has no aux head")
            return self.head(ctx)
        # Pointer alignment (the exact poke-env mapping the encoder relies
        # on): switch action i <-> own-mon vector i, move action 6+j <->
        # own-move vector j. ONE shared scorer over all 10 [ctx || entity]
        # pairs; masking is applied outside, by the caller.
        entities = torch.cat([mons[:, :6], own_moves], dim=1)  # (B, 10, entity_dim)
        pairs = torch.cat(
            [ctx.unsqueeze(1).expand(-1, entities.shape[1], -1), entities], dim=-1
        )
        logits = self.scorer(pairs).squeeze(-1) + self.slot_bias
        if not return_features:
            return logits
        return (logits, *self._aux_features(tok, mons, ctx))

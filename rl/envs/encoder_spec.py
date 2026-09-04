"""Per-generation encoder tables behind one format-selected seam (F-08).

`rl/envs/showdown.py`'s observation encoder was written for gen 1 and grew
its tables in place: the 15 types, the status/boost/base-stat keys, the
volatile set, poke-env's SPECIAL_MOVES, the 1..151 / 1..165 id ranges.
Every one of them is a per-generation fact, and the gen-4 chapter (JOURNEY
step 3) cannot open while they are module literals. This module holds them
as data: an `EncoderSpec` per generation, chosen by battle format, with the
fill helpers reading the spec instead of the module.

WHAT THIS IS NOT. It is not a gen-4 encoder. Only `GEN1` is registered, and
`spec_for_format` REFUSES every other generation by name — that refusal is
the seam. Everything a second spec must bring is listed on `EncoderSpec`;
nothing here changes what gen 1 emits (the tape hash gate in
tests/test_encoder_spec.py pins the 612 / 808 / 828 encodings bit-for-bit).

Torch-free on purpose: this is data the env layer, the tokenizer and the
eval loaders all read; none of them should pay for torch to read a table.
"""

from dataclasses import dataclass, fields
from functools import cached_property
from typing import ClassVar

from poke_env.battle.effect import Effect
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.data import GenData
from poke_env.environment import SinglesEnv


@dataclass(frozen=True)
class EncoderSpec:
    """Every per-generation table the observation encoder reads.

    Frozen and hashable: the fill helpers take it as a default argument and
    the `lru_cache`d id lookups take it as part of their cache key.

    The v1 intra-block layout (the `*_off` / `*_dim_v1` properties) is a pure
    function of the table lengths, so a spec with 17 types places its
    matchup slots after the 17th one-hot instead of over the 16th — the
    offsets the gen-1 docstrings quote (`[+15..29] types`, `[+30]`
    matchup) are `GEN1`'s values of these properties, not literals.

    WHAT A GEN-4 SPEC MUST ADD (the gen-4 blocker, plan F-08), beyond
    filling these fields for gen 4:
      - `types`: 17 (Dark and Steel since gen 2; Fairy makes 18 at gen 6).
        `PokemonType` already carries all of them.
      - per-move physical/special: NO new table. `_fill_move` reads
        poke-env's `move.category`, which is per-move in the gen-4 data
        already; only the gen-1 "category follows the type" rule stops
        holding, and the encoder never assumed it.
      - items and abilities: absent in gen 1, so there is no block for
        them. New per-mon fields are a MON_DIM change, i.e. an OBS_DIM
        change — every existing checkpoint is invalidated (landmine).
      - weather, terrain and SIDE conditions (Spikes, Stealth Rock, Toxic
        Spikes; Reflect / Light Screen are side conditions from gen 3, not
        the per-mon volatiles gen 1's sim emits): new global blocks.
      - `statuses` stays the same six (poke-env's `Status` minus FNT — no
        new major status through gen 9), but `volatiles` grows (Taunt,
        Encore, Yawn, Perish Song, Ingrain, ...): a new ACTIVE_DIM. The
        status COUNTER semantics also move (gen-2 sleep/toxic counters).
      - `base_stat_keys`: six — gen 2+ has a real Special Defense.
      - id ranges: species 1..493 and moves 1..467 at gen 4 (embedding
        table sizes in rl/networks/entity_deepsets.py follow).
      - a set prior for the format: `rl/envs/randbats_prior.py` is gen-1
        randbats data, and `_opponent_move_slots` reads it directly.
      - the v2 effect block: `_effect_block` / `_move_obj` build
        `Move(id, gen=1)` and index a gen-1 move-volatile table; both are
        outside this spec today.
      - the block STRIDES and OBS_DIM: `rl/envs/showdown.py` derives them
        at import from `GEN1` plus the process flags, which is why
        `embed_battle` refuses a non-GEN1 spec outright today.
      - (gen 6+) the action head: `n_actions` widens to 14/18/22/26 for the
        gimmick slots, and the pointer head scores exactly 6 + 4 entities.
        Gen 4 keeps 10 — poke-env's space is 6 + 4 * (1 + gimmicks) with
        gimmicks 0 through gen 5.
    """

    gen: int
    # Ordered: position i is the one-hot index, so ORDER IS LAYOUT.
    types: tuple[PokemonType, ...]
    # FNT excluded: the fainted flag carries it.
    statuses: tuple[Status, ...]
    boost_keys: tuple[str, ...]
    base_stat_keys: tuple[str, ...]
    volatiles: tuple[Effect, ...]
    # poke-env's SPECIAL_MOVES (battle/move.py): when one of these is the
    # only legal move-action, poke-env re-bases the move index onto
    # `available_moves`, so move slot i stops meaning "the mon's move i".
    special_move_ids: frozenset[str]
    # Inclusive `num` ranges for the id suffix's embedding rows; anything
    # outside maps to 0 (= unknown), including poke-env's negative nums for
    # CAP/custom and synthetic entries.
    species_num_range: tuple[int, int]
    move_num_range: tuple[int, int]
    # poke-env's singles constants — 6 team slots, 4 move slots — the same
    # in every generation; carried so `n_actions` can be cross-checked as
    # n_switches + n_moves * (1 + gimmicks) and the 6 / 4 in the layout
    # arithmetic have a name.
    n_switches: int = 6
    n_moves: int = 4

    # --- derived lookups (cached: the fill helpers read them per mon) ----
    @cached_property
    def type_index(self) -> dict[PokemonType, int]:
        return {t: i for i, t in enumerate(self.types)}

    @cached_property
    def status_index(self) -> dict[Status, int]:
        return {s: i for i, s in enumerate(self.statuses)}

    @property
    def n_types(self) -> int:
        return len(self.types)

    @property
    def n_statuses(self) -> int:
        return len(self.statuses)

    @property
    def n_boosts(self) -> int:
        return len(self.boost_keys)

    @property
    def n_base_stats(self) -> int:
        return len(self.base_stat_keys)

    @property
    def n_volatiles(self) -> int:
        return len(self.volatiles)

    @property
    def n_actions(self) -> int:
        """poke-env's Discrete size for this generation (singles_env.py):
        6 switches + 4 moves x (1 + gimmicks) — 10 through gen 5."""
        return SinglesEnv.get_action_space_size(self.gen)

    # --- v1 intra-block layout: hp, fainted, is-active | status one-hot |
    # level | base stats | type one-hot | off/def matchup (2). The v2 speed
    # edge and the v2 effect block are appended by rl/envs/showdown.py under
    # its process flags; they are not per-gen and are not here.
    # The two ClassVars are the counts of LEADING SCALAR slots, fixed by the
    # encoder's code rather than by the generation: 3 = hp/fainted/is-active,
    # 8 = known/bp/acc/pp/matchup/physical/status/priority.
    mon_status_off: ClassVar[int] = 3

    @cached_property
    def mon_level_off(self) -> int:
        return self.mon_status_off + self.n_statuses

    @cached_property
    def mon_stats_off(self) -> int:
        return self.mon_level_off + 1

    @cached_property
    def mon_types_off(self) -> int:
        return self.mon_stats_off + self.n_base_stats

    @cached_property
    def mon_matchup_off(self) -> int:
        return self.mon_types_off + self.n_types

    @cached_property
    def mon_dim_v1(self) -> int:
        return self.mon_matchup_off + 2

    # Active extras: boosts | volatile flags | status counter | preparing.
    @cached_property
    def active_volatiles_off(self) -> int:
        return self.n_boosts

    @cached_property
    def active_counter_off(self) -> int:
        return self.n_boosts + self.n_volatiles

    @cached_property
    def active_dim(self) -> int:
        return self.active_counter_off + 2

    # Move block: known, bp, acc, pp, matchup, physical, status, priority |
    # type one-hot.
    move_type_off: ClassVar[int] = 8

    @cached_property
    def move_dim_v1(self) -> int:
        return self.move_type_off + self.n_types

    # --- hashing. Field-based (two specs with the same tables hash alike),
    # but CACHED: `_species_id` takes the spec into an lru_cache key ~20
    # times per decision, and re-hashing 40-odd table entries per call
    # measured 0.92 us against the encoder's ~133 us/decision. An explicit
    # __hash__ in the body is left alone by @dataclass.
    @cached_property
    def _hash(self) -> int:
        return hash(tuple(getattr(self, f.name) for f in fields(self)))

    def __hash__(self) -> int:
        return self._hash


# --- Gen 1: exactly the tables rl/envs/showdown.py carried as literals, in
# exactly their order. Changing any entry here changes every gen-1
# checkpoint's input semantics; the tape hash gate exists to make that loud.
GEN1 = EncoderSpec(
    gen=1,
    # The 15 Gen 1 types, alphabetical. Fixed here (not from PokemonType,
    # which carries all 20 modern members) so the one-hot layout is stable.
    types=(
        PokemonType.BUG, PokemonType.DRAGON, PokemonType.ELECTRIC,
        PokemonType.FIGHTING, PokemonType.FIRE, PokemonType.FLYING,
        PokemonType.GHOST, PokemonType.GRASS, PokemonType.GROUND,
        PokemonType.ICE, PokemonType.NORMAL, PokemonType.POISON,
        PokemonType.PSYCHIC, PokemonType.ROCK, PokemonType.WATER,
    ),
    statuses=(Status.BRN, Status.FRZ, Status.PAR, Status.PSN, Status.SLP, Status.TOX),
    # All 7 poke-env boost keys, sorted. Gen 1 has one Special stat — the
    # server mirrors spa/spd — so one of the pair is redundant but harmless.
    boost_keys=("accuracy", "atk", "def", "evasion", "spa", "spd", "spe"),
    # spd is dropped: Gen 1 base data mirrors it from spa (one Special stat).
    base_stat_keys=("hp", "atk", "def", "spa", "spe"),
    # Gen 1 volatiles poke-env can represent. Light Screen is MISSING by
    # necessity, not oversight: the Gen 1 sim emits it as a per-mon volatile
    # ("|-start|...|Light Screen") and poke-env 0.15.0 has no LIGHT_SCREEN
    # Effect member, so it parses to Effect.UNKNOWN — ambiguous, not worth a
    # parser fork for one uncommon move. Reflect (its physical twin) parses.
    # The MUST_RECHARGE slot is filled from `mon.must_recharge`, not effect
    # membership: poke-env routes |-mustrecharge| to that bool and never
    # starts the Effect (measured 0/2,427 decisions vs 185 with the bool
    # set), so the Effect test would leave the slot structurally dead —
    # Stage-0 fix, D13(a); see rl/envs/showdown.py::_fill_active.
    volatiles=(
        Effect.CONFUSION, Effect.FOCUS_ENERGY, Effect.LEECH_SEED,
        Effect.MUST_RECHARGE, Effect.PARTIALLY_TRAPPED, Effect.REFLECT,
        Effect.SUBSTITUTE,
    ),
    # gen1's `fight` placeholder is the common case (~1.5% of decisions);
    # struggle and recharge alias the same way.
    special_move_ids=frozenset({"fight", "struggle", "recharge"}),
    # Gen-1 pokedex 1..151; gen-1 moves 1..165 (recharge is num -3 in
    # poke-env's table and maps to 0).
    species_num_range=(1, 151),
    move_num_range=(1, 165),
)

_REGISTRY: dict[int, EncoderSpec] = {GEN1.gen: GEN1}


def spec_for_format(battle_format: str) -> EncoderSpec:
    """The EncoderSpec for a Showdown format, by its generation.

    THIS IS THE SEAM: only gen 1 is registered. Any other generation raises
    NotImplementedError naming what the encoder lacks for it, so a gen-4 or
    gen-9 format fails at construction (train.py / eval_checkpoint.py's
    faked spaces, the tokenizer) instead of as a silent shape bug.
    """
    gen = GenData.from_format(battle_format).gen
    spec = _REGISTRY.get(gen)
    if spec is not None:
        return spec
    n_actions = SinglesEnv.get_action_space_size(gen)
    missing = [
        "a per-gen type table (17 types from gen 2, 18 from gen 6)",
        "items and abilities blocks (absent in gen 1)",
        "weather / terrain / side-condition blocks",
        "the gen-2+ volatile set",
        f"species and move `num` ranges for gen {gen}",
        f"a set prior for the format ({battle_format!r}; randbats_prior.py is gen 1)",
        "the v2 effect block off gen-1 Move data",
        "per-spec block strides and OBS_DIM (showdown.py derives them from GEN1)",
    ]
    if n_actions != GEN1.n_actions:
        missing.append(
            f"an action head for {n_actions} actions (gimmick slots; the "
            f"pointer head scores {GEN1.n_actions})"
        )
    raise NotImplementedError(
        f"no EncoderSpec for gen {gen} ({battle_format!r}): only gen 1 is "
        f"wired (rl/envs/encoder_spec.py). A gen-{gen} spec still needs: "
        + "; ".join(missing) + "."
    )

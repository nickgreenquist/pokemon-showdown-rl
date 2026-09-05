"""The GEN4 `EncoderSpec` values and the gen-4-only observation layout.

`GEN4` fills the landed seam's dataclass (rl/envs/encoder_spec.py, F-08) with
the gen-4 tables the design fixed (docs/design_gen4/encoder_requirements.md
§3): 17 types listed explicitly (poke-env's gen4 chart carries an 18th,
inconsistent Fairy key), six base stats, the gen-4 volatile set, poke-env's
gen-4 SPECIAL_MOVES (no `fight` placeholder), and the gen-4 `num` ranges —
kept for the record even though the id suffix uses the forme-keyed vocabs
(rl/envs/gen4/vocab.py) instead of `num` (Hidden Power collapses to 237 and
34 pool species share six nums; §3.4, A1).

`LAYOUT` is everything the seam's dataclass does NOT carry — the blocks gen 1
has no analogue for (items, abilities, weather, fields, sides, counters) and
the widths that follow. The gen-1 v1 intra-block offsets on `EncoderSpec`
(`mon_*_off`, `active_*_off`, `move_type_off`) are NOT used here: the gen-4
mon/active/move blocks have their own order, computed once below. Nothing in
this module is read by the gen-1 encoder; `GEN1`'s tables and offsets are
untouched (the tape hash gate is the proof).

Widths are the v0.1 bring-up layout. They become exact only when a gen-4
pre-registration header freezes them (docs/design_gen4/encoder_requirements.md
§4.7: "no number here is a commitment").
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from poke_env.battle.effect import Effect
from poke_env.battle.field import Field
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.side_condition import SideCondition
from poke_env.battle.status import Status
from poke_env.battle.weather import Weather

from rl.envs.encoder_spec import GEN1, EncoderSpec

# The 17 gen-4 types, alphabetical, LISTED (never derived from the chart:
# GenData.from_gen(4).type_chart has 18 keys, Fairy is `isNonstandard:
# 'Future'` at gen 4 — showdown/data/mods/gen5/typechart.ts:93-96).
GEN4_TYPES = (
    PokemonType.BUG, PokemonType.DARK, PokemonType.DRAGON, PokemonType.ELECTRIC,
    PokemonType.FIGHTING, PokemonType.FIRE, PokemonType.FLYING, PokemonType.GHOST,
    PokemonType.GRASS, PokemonType.GROUND, PokemonType.ICE, PokemonType.NORMAL,
    PokemonType.POISON, PokemonType.PSYCHIC, PokemonType.ROCK, PokemonType.STEEL,
    PokemonType.WATER,
)

# Single-Effect volatile flags of the active block, in one-hot order. Pool
# counts (sets carrying a move that inflicts it) from mechanics_delta.md §7.
# MUST_RECHARGE is read from the bool `mon.must_recharge`, as in gen 1 (D13a).
# Two COMPOSITE flags follow them in the layout (LAYOUT.composite_volatiles):
# trapped-by-move (OR of the six per-move members) and perish (any PERISHn).
GEN4_VOLATILES = (
    Effect.SUBSTITUTE,     # 44 sets; plus the sub-hits counter
    Effect.CONFUSION,      # Dynamic Punch, Outrage fatigue
    Effect.LEECH_SEED,     # 10
    Effect.MUST_RECHARGE,  # Giga Impact 1 (the bool)
    Effect.ENCORE,         # 24 (turn-countable)
    Effect.TAUNT,          # 13 (turn-countable)
    Effect.YAWN,           # 4
    Effect.CURSE,          # 11 (ghost curse residual; the boost form is in boosts)
    Effect.ATTRACT,        # Cute Charm 7
    Effect.FOCUS_ENERGY,   # crit model; Haze-relevant
    Effect.LOCKED_MOVE,    # Outrage 13 — read from the TRACKER (poke-env never sets it)
    Effect.FLASH_FIRE,     # 6 species; poke-env clears it one use early (survey G6)
    Effect.SLOW_START,     # Regigigas (turn-countable)
)

GEN4 = EncoderSpec(
    gen=4,
    types=GEN4_TYPES,
    statuses=GEN1.statuses,      # no new major status through gen 9
    boost_keys=GEN1.boost_keys,  # the same seven keys; spd stops being redundant
    base_stat_keys=("hp", "atk", "def", "spa", "spd", "spe"),
    volatiles=GEN4_VOLATILES,
    # `fight` is a gen-1-only wire placeholder (showdown/sim/pokemon.ts);
    # `recharge` survives (Giga Impact) and `struggle` always can.
    special_move_ids=frozenset({"struggle", "recharge"}),
    species_num_range=(1, 493),
    move_num_range=(1, 467),
)

_TRAP_MEMBERS = tuple(
    getattr(Effect, name) for name in ("BIND", "WRAP", "FIRE_SPIN", "CLAMP", "WHIRLPOOL", "SAND_TOMB")
    if hasattr(Effect, name)
)
_PERISH_MEMBERS = tuple(
    getattr(Effect, name) for name in ("PERISH0", "PERISH1", "PERISH2", "PERISH3")
    if hasattr(Effect, name)
)


@dataclass(frozen=True)
class Gen4Layout:
    """Every gen-4 block width and offset, derived from the tables once.

    Block order (the gen-1 order, so the 21-token tokenizer reshape and the
    pointer head over 6 + 4 entities carry over once the tokenizer takes a
    layout argument — today it is gen-1-bound):
      global | own mons x6 | own active | own moves x4 |
      opp mons x6 (each prefixed by a `revealed` flag) | opp active |
      opp moves x4 | id suffix.

    Deliberately wider than the PINNED pool reaches (2026-09-05 review: ~90
    of the 1,448 dims never left zero over 41,908 recorded decisions —
    Stealth Rock / screens / Safeguard / Mist / Tailwind / Lucky Chant on
    both sides, Gravity, the CURSE / FOCUS_ENERGY / trapped-by-move / perish
    flags and counter, and the drain / attract / partial-trap / focus-energy
    / screen / other-side / trap effect slots x8). They are the FORMAT's
    mechanics, not this commit's set list: the pool changes with every
    Showdown commit (this one has zero Stealth Rock sets; the format's
    history does not), and a retrain is cheaper than a relayout. A v1.0
    freeze may still drop them — encoder_requirements.md §13.
    """

    spec: EncoderSpec = GEN4
    # --- global ---------------------------------------------------------
    # turn/turn_scale, own faints/6, opp faints/6, force_switch, trapped,
    # maybe_trapped (gen-4-live; survey G1), move-slots-aliased.
    n_global_scalars: int = 7
    weathers: tuple = (Weather.RAINDANCE, Weather.SUNNYDAY, Weather.SANDSTORM, Weather.HAIL)
    # elapsed turns / weather_turn_scale, and the "indefinite" bit (ability-set
    # weather has duration 0 at gen <= 5; the sim restamps -weather every
    # upkeep, so poke-env's own stamp carries no duration — tracker-derived).
    n_weather_extras: int = 2
    fields: tuple = (Field.TRICK_ROOM, Field.GRAVITY)
    n_field_extras: int = 1  # Trick Room elapsed / 5
    side_conditions: tuple = (
        SideCondition.SPIKES, SideCondition.TOXIC_SPIKES, SideCondition.STEALTH_ROCK,
        SideCondition.REFLECT, SideCondition.LIGHT_SCREEN, SideCondition.SAFEGUARD,
        SideCondition.MIST, SideCondition.TAILWIND, SideCondition.LUCKY_CHANT,
    )
    # Slot conditions poke-env does not track at all (critic_pass.md): a
    # pending Wish (19 sets) / Healing Wish (4 sets) per side, from the tracker.
    n_slot_extras: int = 1
    # --- mon ------------------------------------------------------------
    n_mon_leading: int = 3        # hp, fainted, is-active
    n_matchup: int = 2            # chart: mon-vs-foe, foe-vs-mon (best of types)
    n_matchup_ability: int = 2    # the same two, folded with the KNOWN ability's type immunities
    n_item_state: int = 3         # unknown | known held | known none (consumed / knocked off / itemless)
    n_item_classes: int = 5       # rl/envs/gen4/classes.py ITEM_CLASSES
    n_item_extras: int = 1        # consumed (had an item this battle, now none) — tracker
    n_ability_state: int = 2      # known | unknown-with-candidates
    n_ability_classes: int = 12   # rl/envs/gen4/classes.py ABILITY_CLASSES
    n_mon_extras: int = 1         # speed edge vs the opposing active (closed-form opp stats)
    # --- active ---------------------------------------------------------
    composite_volatiles: tuple = ("trapped_by_move", "perish")
    n_counters: int = 6           # sleep attempts/4 (tracker), toxic stage/16, protect streak/4,
                                  # encore|taunt|lock elapsed/8, sub hits/3 (tracker), perish left/3
    n_active_extras: int = 3      # first_turn (Fake Out), preparing, choice_locked (tracker)
    # --- move -----------------------------------------------------------
    n_move_scalars: int = 9       # known/prob, bp/100, acc, pp frac, matchup (ability-aware),
                                  # physical, status, priority/priority_scale, crit stage
    effect_dim: int = 45          # rl/envs/gen4/encoder.py::_effect_block_gen4 documents each slot
    # --- ids ------------------------------------------------------------
    n_id_species: int = 12
    n_id_moves: int = 8
    n_id_items: int = 12
    n_id_abilities: int = 12
    # --- scales ---------------------------------------------------------
    turn_scale: float = 100.0     # gen-4 bot games: mean ~20, max 147 over 760 (t1-t4 tapes)
    weather_turn_scale: float = 8.0
    field_turn_scale: float = 5.0
    priority_scale: float = 7.0   # Trick Room -7 .. Helping Hand +5 stay inside Box(-1, 4)
    id_scale: float = 256.0       # exact in float32; 300/256 < 4

    # ---- derived: global -------------------------------------------------
    @cached_property
    def weather_off(self) -> int:
        return self.n_global_scalars

    @cached_property
    def fields_off(self) -> int:
        return self.weather_off + len(self.weathers) + self.n_weather_extras

    @cached_property
    def own_side_off(self) -> int:
        return self.fields_off + len(self.fields) + self.n_field_extras

    @cached_property
    def side_dim(self) -> int:
        return len(self.side_conditions)

    @cached_property
    def opp_side_off(self) -> int:
        return self.own_side_off + self.side_dim + self.n_slot_extras

    @cached_property
    def global_dim(self) -> int:
        return self.opp_side_off + self.side_dim + self.n_slot_extras

    # ---- derived: mon ----------------------------------------------------
    @cached_property
    def mon_status_off(self) -> int:
        return self.n_mon_leading

    @cached_property
    def mon_level_off(self) -> int:
        return self.mon_status_off + self.spec.n_statuses

    @cached_property
    def mon_stats_off(self) -> int:
        return self.mon_level_off + 1

    @cached_property
    def mon_types_off(self) -> int:
        return self.mon_stats_off + self.spec.n_base_stats

    @cached_property
    def mon_matchup_off(self) -> int:
        return self.mon_types_off + self.spec.n_types

    @cached_property
    def mon_matchup_ability_off(self) -> int:
        return self.mon_matchup_off + self.n_matchup

    @cached_property
    def mon_item_state_off(self) -> int:
        return self.mon_matchup_ability_off + self.n_matchup_ability

    @cached_property
    def mon_item_classes_off(self) -> int:
        return self.mon_item_state_off + self.n_item_state

    @cached_property
    def mon_item_consumed_off(self) -> int:
        return self.mon_item_classes_off + self.n_item_classes

    @cached_property
    def mon_ability_state_off(self) -> int:
        return self.mon_item_consumed_off + self.n_item_extras

    @cached_property
    def mon_ability_classes_off(self) -> int:
        return self.mon_ability_state_off + self.n_ability_state

    @cached_property
    def mon_speed_off(self) -> int:
        return self.mon_ability_classes_off + self.n_ability_classes

    @cached_property
    def mon_dim(self) -> int:
        return self.mon_speed_off + self.n_mon_extras

    # ---- derived: active -------------------------------------------------
    @cached_property
    def active_volatiles_off(self) -> int:
        return self.spec.n_boosts

    @cached_property
    def n_volatile_flags(self) -> int:
        return self.spec.n_volatiles + len(self.composite_volatiles)

    @cached_property
    def active_counters_off(self) -> int:
        return self.active_volatiles_off + self.n_volatile_flags

    @cached_property
    def active_extras_off(self) -> int:
        return self.active_counters_off + self.n_counters

    @cached_property
    def active_dim(self) -> int:
        return self.active_extras_off + self.n_active_extras

    # ---- derived: move ---------------------------------------------------
    @cached_property
    def move_type_off(self) -> int:
        return self.n_move_scalars

    @cached_property
    def move_effect_off(self) -> int:
        return self.move_type_off + self.spec.n_types

    @cached_property
    def move_dim(self) -> int:
        return self.move_effect_off + self.effect_dim

    # ---- derived: whole vector ------------------------------------------
    @cached_property
    def own_mons_off(self) -> int:
        return self.global_dim

    @cached_property
    def own_active_off(self) -> int:
        return self.own_mons_off + self.spec.n_switches * self.mon_dim

    @cached_property
    def own_moves_off(self) -> int:
        return self.own_active_off + self.active_dim

    @cached_property
    def opp_mons_off(self) -> int:
        return self.own_moves_off + self.spec.n_moves * self.move_dim

    @cached_property
    def opp_active_off(self) -> int:
        return self.opp_mons_off + self.spec.n_switches * (self.mon_dim + 1)

    @cached_property
    def opp_moves_off(self) -> int:
        return self.opp_active_off + self.active_dim

    @cached_property
    def ids_off(self) -> int:
        return self.opp_moves_off + self.spec.n_moves * self.move_dim

    @cached_property
    def id_dim(self) -> int:
        return self.n_id_species + self.n_id_moves + self.n_id_items + self.n_id_abilities

    @cached_property
    def obs_dim(self) -> int:
        return self.ids_off + self.id_dim

    @cached_property
    def priv_dim(self) -> int:
        """The own-side slice (mons + active + moves) plus the own id tail
        (6 species + 4 moves + 6 items + 6 abilities) — the D18 privileged
        block re-derived for gen 4."""
        return (self.opp_mons_off - self.own_mons_off) + 6 + 4 + 6 + 6

    # ---- helpers ---------------------------------------------------------
    @cached_property
    def weather_index(self) -> dict:
        return {w: i for i, w in enumerate(self.weathers)}

    @cached_property
    def field_index(self) -> dict:
        return {f: i for i, f in enumerate(self.fields)}

    @cached_property
    def side_index(self) -> dict:
        return {s: i for i, s in enumerate(self.side_conditions)}

    @property
    def trap_members(self) -> tuple:
        return _TRAP_MEMBERS

    @property
    def perish_members(self) -> tuple:
        return _PERISH_MEMBERS


LAYOUT = Gen4Layout()
OBS_DIM_GEN4 = LAYOUT.obs_dim
N_ACTIONS_GEN4 = GEN4.n_actions  # 10: poke-env's space is 6 + 4 * (1 + gimmicks), gimmicks 0 through gen 5

# Stamped into run metadata by the gen-4 env (the gen-1 fingerprint carries no
# generation — encoder_requirements.md §7; this one does).
ENCODER_FINGERPRINT_GEN4 = {
    "gen": 4,
    "spec": "gen4",
    "layout": "v0.1",
    "obs_dim": OBS_DIM_GEN4,
    "encoder": "gen4-v0.1",
    "set_prior": True,
    "ids": True,
}

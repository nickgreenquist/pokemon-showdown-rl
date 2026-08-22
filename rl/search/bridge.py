"""battle1 -> poke_engine.State: the obs->engine half of the R1 bridge.

Chapter-3 R1 (ch3_search_design_r2.md §2/§3/§6). Maps poke-env's PUBLIC
seat-1 view plus one RSD determinization onto a poke_engine gen1 State.
Written from the poke_engine .pyi/API and OUR encoder semantics only — the
foul-play clone (GPL-3.0) was consulted as landmine documentation, never as
an implementation reference; no code is derived from it.

Invariants this module owns:
- CONSTRUCT States as objects, never via to_string/from_string: measured
  2026-08-22, the string round-trip DROPS volatile_statuses (all of them),
  while direct construction carries them (reflect's damage effect measured
  working by review 2). Serialization is for FG-1 only.
- The volatile map is pinned against the engine's own gen1 enum
  (poke-engine 0.0.48 src/gen1/state.rs, extracted 2026-08-22) and asserted
  at import. Unmapped poke-env Effects are COUNTED (`unmapped_effects`),
  never silently dropped. Light Screen is unobservable from battle1
  (poke-env 0.15 has no Effect.LIGHT_SCREEN — a NAMED unmodellable, design
  §2.4).
- The engine does NOT enforce partial-trap or must-recharge (measured):
  action substitution to "none" is the MATRIX layer's job; this module
  only reports `is_locked_turn`.
- Gen1 stats for determinized opponents use max DVs (15) and max stat exp
  (65535): term = floor(min(255, ceil(sqrt(exp)))/4) = 63. Pinned by test
  vectors (Tauros L100: HP 353, Spe 318). Whether randbats uses maxed
  DVs/exp is an FG-2 question — this is the declared assumption.
"""

from __future__ import annotations

import math
from typing import Any

from poke_engine import Move as EngineMove
from poke_engine import Pokemon as EnginePokemon
from poke_engine import Side, State

from rl.envs import randbats_prior

# The engine's gen1 PokemonVolatileStatus variants we may emit, lowercased
# (from_str is case-insensitive lowercase; pinned subset of the enum in
# poke-engine 0.0.48 src/gen1/state.rs).
GEN1_ENGINE_VOLATILES = frozenset({
    "reflect", "lightscreen", "mist", "focusenergy", "leechseed",
    "confusion", "substitute", "partiallytrapped", "mustrecharge", "bide",
    "flinch", "lockedmove", "disable",
})

# poke-env Effect name -> engine volatile name. Keys are Effect.name strings
# so the table needs no poke_env import at module load. Substitute health is
# handled separately (Side.substitute_health); the effect still maps so the
# volatile flag itself is set.
EFFECT_VOLATILE_MAP: dict[str, str] = {
    "REFLECT": "reflect",
    "MIST": "mist",
    "FOCUS_ENERGY": "focusenergy",
    "LEECH_SEED": "leechseed",
    "CONFUSION": "confusion",
    "SUBSTITUTE": "substitute",
    "BIDE": "bide",
    "DISABLE": "disable",
    "TRAPPED": "partiallytrapped",
    "PARTIALLY_TRAPPED": "partiallytrapped",
    "BINDING": "partiallytrapped",
    "FLINCH": "flinch",
}
assert set(EFFECT_VOLATILE_MAP.values()) <= GEN1_ENGINE_VOLATILES, (
    "EFFECT_VOLATILE_MAP emits a name outside the engine's gen1 enum"
)

# poke-env Status.name -> the engine's FULL status names. LANDMINE
# (measured 2026-08-22 on real harvest states): the engine accepts ANY
# string at Pokemon construction and only parses it inside
# generate_instructions/to_string — the 3-letter forms ("par") panic there
# with "Invalid PokemonStatus: PAR", and State.status READBACK returns the
# raw string unparsed, so a scan of constructed states looks clean. The
# accepted names below are probed+pinned by test_engine_accepts_every_
# mapped_status; sleep/freeze also confirm the engine ENFORCES those locks
# (4 branches vs 8).
_STATUS_MAP = {
    "BRN": "burn", "PAR": "paralyze", "PSN": "poison", "TOX": "toxic",
    "SLP": "sleep", "FRZ": "freeze", "FNT": "none",  # fainted carried via hp=0
}

# gen1 stat-exp term at maxed 65535: floor(min(255, ceil(sqrt(65535)))/4)
_EXP_TERM = 63
_DV = 15


def gen1_stat(base: int, level: int, hp: bool = False) -> int:
    core = (base + _DV) * 2 + _EXP_TERM
    if hp:
        return math.floor(core * level / 100) + level + 10
    return math.floor(core * level / 100) + 5


class BridgeCounters:
    """Loud seams: everything the bridge could not represent, counted."""

    def __init__(self) -> None:
        self.unmapped_effects: dict[str, int] = {}
        self.lightscreen_unobservable = 0  # bumped by callers that know

    def count_effect(self, name: str) -> None:
        self.unmapped_effects[name] = self.unmapped_effects.get(name, 0) + 1


def _engine_moves(move_ids: list[str], pp_by_id: dict[str, int] | None) -> list[EngineMove]:
    out = []
    for mid in move_ids[:4]:
        pp = (pp_by_id or {}).get(mid, 16)
        out.append(EngineMove(id=mid, pp=max(int(pp), 0), disabled=False))
    while len(out) < 4:
        out.append(EngineMove(id="none", pp=0, disabled=True))
    return out


def _status_str(mon: Any) -> str:
    st = getattr(mon, "status", None)
    if st is None:
        return "none"
    return _STATUS_MAP.get(getattr(st, "name", str(st)), "none")


def _our_pokemon(mon: Any) -> EnginePokemon:
    """Our side is EXACT: species, level, real stats, real HP, real PP."""
    stats = mon.stats or {}
    types = [t.name.lower() for t in mon.types if t is not None]
    while len(types) < 2:
        types.append("typeless")
    status = _status_str(mon)
    sleep_turns = int(getattr(mon, "status_counter", 0)) if status == "sleep" else 0
    return EnginePokemon(
        id=mon.species,
        level=mon.level,
        types=(types[0], types[1]),
        hp=int(mon.current_hp or 0),
        maxhp=int(mon.max_hp or 1),
        attack=int(stats.get("atk") or gen1_stat(mon.base_stats["atk"], mon.level)),
        defense=int(stats.get("def") or gen1_stat(mon.base_stats["def"], mon.level)),
        special_attack=int(stats.get("spa") or gen1_stat(mon.base_stats["spa"], mon.level)),
        special_defense=int(stats.get("spd") or gen1_stat(mon.base_stats["spd"], mon.level)),
        speed=int(stats.get("spe") or gen1_stat(mon.base_stats["spe"], mon.level)),
        status=status,
        sleep_turns=sleep_turns,
        moves=_engine_moves(
            list(mon.moves.keys()),
            {mid: m.current_pp for mid, m in mon.moves.items()},
        ),
    )


def _det_pokemon(species: str, move_ids: list[str], hp_fraction: float,
                 status: str = "none", base_stats: dict | None = None,
                 level: int | None = None, sleep_turns: int = 0) -> EnginePokemon:
    """A determinized opponent mon: exact where revealed, sampled elsewhere.
    Stats from the gen1 formula at the randbats level (max DV/exp assumption,
    module docstring); HP scaled from the public fraction."""
    level = level if level is not None else (randbats_prior.species_level(species) or 100)
    bs = base_stats or {}
    maxhp = gen1_stat(bs.get("hp", 100), level, hp=True)
    types = list(bs.get("types") or ["normal"])[:2]
    while len(types) < 2:
        types.append("typeless")
    return EnginePokemon(
        id=species,
        level=level,
        types=(types[0], types[1]),
        hp=max(0, min(maxhp, round(hp_fraction * maxhp))),
        maxhp=maxhp,
        attack=gen1_stat(bs.get("atk", 100), level),
        defense=gen1_stat(bs.get("def", 100), level),
        special_attack=gen1_stat(bs.get("spa", 100), level),
        special_defense=gen1_stat(bs.get("spd", 100), level),
        speed=gen1_stat(bs.get("spe", 100), level),
        status=status,
        sleep_turns=sleep_turns,
        moves=_engine_moves(move_ids, None),
    )


def _side_volatiles(active: Any, counters: BridgeCounters) -> set[str]:
    vols: set[str] = set()
    for eff in (getattr(active, "effects", None) or {}):
        name = getattr(eff, "name", str(eff))
        mapped = EFFECT_VOLATILE_MAP.get(name)
        if mapped is not None:
            vols.add(mapped)
        else:
            counters.count_effect(name)
    if getattr(active, "must_recharge", False):
        vols.add("mustrecharge")
    return vols


def _boost(active: Any, key: str) -> int:
    return int((getattr(active, "boosts", None) or {}).get(key, 0))


def build_side(mons: list[EnginePokemon], active_species: str,
               active_obj: Any, counters: BridgeCounters,
               substitute_health: int = 0) -> Side:
    from poke_engine import PokemonIndex

    idx = next(i for i, m in enumerate(mons) if m.id == active_species)
    spa = _boost(active_obj, "spa")
    return Side(
        pokemon=mons,
        active_index=getattr(PokemonIndex, f"P{idx}"),
        volatile_statuses=_side_volatiles(active_obj, counters),
        substitute_health=substitute_health,
        attack_boost=_boost(active_obj, "atk"),
        defense_boost=_boost(active_obj, "def"),
        special_attack_boost=spa,  # gen1 Special: one stat, both engine slots
        special_defense_boost=spa,
        speed_boost=_boost(active_obj, "spe"),
        accuracy_boost=_boost(active_obj, "accuracy"),
        evasion_boost=_boost(active_obj, "evasion"),
    )


def is_locked_turn(battle: Any) -> bool:
    """Our gen-1 placeholder / recharge turn: the search must no-op (the
    engine does not enforce these locks — measured)."""
    avail = list(getattr(battle, "available_moves", []) or [])
    return len(avail) == 1 and avail[0].id in ("fight", "recharge")


def battle_to_state(battle: Any, determinization: dict,
                    counters: BridgeCounters | None = None) -> State:
    """battle1 (public) + one determinization -> engine State.

    `determinization` is rl/search/determinize.py's output: per opponent
    species -> {"moves": [ids], "base_stats": {...}, "level": int}, plus
    "bench_species" for unrevealed slots. Seat 1 = us.
    """
    counters = counters or BridgeCounters()
    our_mons = [_our_pokemon(m) for m in battle.team.values()]
    side_one = build_side(
        our_mons, battle.active_pokemon.species, battle.active_pokemon, counters
    )

    opp_mons = []
    opp_active = battle.opponent_active_pokemon
    for species, spec in determinization["opponents"].items():
        live = spec.get("live")  # the poke-env mon if revealed
        opp_mons.append(
            _det_pokemon(
                species,
                spec["moves"],
                hp_fraction=(live.current_hp_fraction if live is not None else 1.0),
                status=_status_str(live) if live is not None else "none",
                base_stats=spec.get("base_stats"),
                level=spec.get("level"),
                sleep_turns=(
                    int(getattr(live, "status_counter", 0))
                    if live is not None and _status_str(live) == "sleep"
                    else 0
                ),
            )
        )
    side_two = build_side(
        opp_mons, opp_active.species, opp_active, counters,
    )
    return State(side_one=side_one, side_two=side_two)

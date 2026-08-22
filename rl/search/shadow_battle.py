"""ShadowBattle: engine State -> the exact attribute surface embed_battle
reads. The design's no-second-encoder invariant (ch3_search_design_r2.md
§2): a leaf is encoded by THE SAME `rl/envs/showdown.embed_battle` as live
play, fed a duck-typed mirror of the poke-env Battle — so FG-6 tests one
field map, never two encoders.

What the engine cannot supply, and where it comes from:
- base_stats/types per species: poke-env's static gen-1 pokedex (cached).
- turn: carried from the root battle (+1 at a depth-1 leaf).
- Move metadata (base_power/accuracy/type/category/priority/entry): a
  cached poke-env Move per id, wrapped in a per-leaf _MoveView that
  overrides current_pp with the engine's — the cache is shared and never
  mutated.
- effects: reverse of bridge.EFFECT_VOLATILE_MAP on the side's volatile
  set (active only; gen1 bench carries no volatiles).
- KNOWN NON-PARITY FAMILIES (FG-6's budget, measured not asserted):
  opponent HP quantisation (engine exact vs battle1's /100 fraction), PP
  (poke-env never decrements the opponent's), sleep-vs-Rest counter split
  (engine separates, poke-env conflates), preparing (engine models FLY/DIG
  as volatiles we do not map back), lightscreen (unobservable at the root).
"""

from __future__ import annotations

from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from poke_env.battle.move import Move as PEMove
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status

from rl.search.bridge import EFFECT_VOLATILE_MAP

_VOLATILE_EFFECT_MAP = {v: k for k, v in EFFECT_VOLATILE_MAP.items()}
# Keys are the ENGINE's full status names (bridge._STATUS_MAP values;
# probed+pinned 2026-08-22 — the 3-letter forms panic in the engine).
_STATUS_ENUM = {
    "burn": Status.BRN, "paralyze": Status.PAR, "poison": Status.PSN,
    "toxic": Status.TOX, "sleep": Status.SLP, "freeze": Status.FRZ,
}


@lru_cache(maxsize=512)
def _cached_move(move_id: str) -> PEMove:
    return PEMove(move_id, gen=1)


@lru_cache(maxsize=256)
def _static_species(species: str) -> tuple[dict, tuple]:
    from poke_env.data import GenData

    entry = GenData.from_gen(1).pokedex[species]
    types = tuple(
        PokemonType.from_name(t) for t in entry["types"]
    )
    return dict(entry["baseStats"]), types


class _MoveView:
    """Cached poke-env Move + the engine's live PP. Read-only delegate; the
    shared cache is never mutated."""

    __slots__ = ("_base", "current_pp")

    def __init__(self, base: PEMove, current_pp: int):
        self._base = base
        self.current_pp = current_pp

    def __getattr__(self, name):
        return getattr(self._base, name)


class _Effects(dict):
    """effects mapping with Effect-like keys (only .name is read)."""


def _mon_view(mon: Any, side: Any, is_active: bool) -> SimpleNamespace:
    # the engine UPPERCASES ids on applied-state readback (measured); all
    # downstream consumers (pokedex, encoder id block) want lowercase
    species = mon.id.lower()
    base_stats, types = _static_species(species)
    status = _STATUS_ENUM.get(mon.status)
    fainted = mon.hp <= 0
    vols = set(side.volatile_statuses) if is_active else set()
    effects = _Effects()
    for v in vols:
        eff_name = _VOLATILE_EFFECT_MAP.get(v)
        if eff_name is not None:
            effects[SimpleNamespace(name=eff_name)] = 1
    moves = {}
    for em in mon.moves:
        if em.id.lower() == "none":
            continue
        mid = em.id.lower()
        moves[mid] = _MoveView(_cached_move(mid), em.pp)
    boosts = dict.fromkeys(
        ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe"), 0
    )
    if is_active:
        boosts["atk"] = side.attack_boost
        boosts["def"] = side.defense_boost
        boosts["spa"] = side.special_attack_boost
        boosts["spd"] = side.special_defense_boost
        boosts["spe"] = side.speed_boost
        boosts["accuracy"] = side.accuracy_boost
        boosts["evasion"] = side.evasion_boost
    return SimpleNamespace(
        species=species,
        level=mon.level,
        current_hp_fraction=(mon.hp / mon.maxhp if mon.maxhp else 0.0),
        fainted=fainted,
        status=Status.FNT if fainted else status,
        status_counter=int(mon.sleep_turns or 0) + int(mon.rest_turns or 0),
        base_stats=base_stats,
        types=list(types),
        type_1=types[0],
        type_2=types[1] if len(types) > 1 else None,
        boosts=boosts,
        effects=effects,
        preparing=False,
        must_recharge="mustrecharge" in vols,
        moves=moves,
    )


def shadow_battle(state: Any, turn: int) -> SimpleNamespace:
    """Engine State -> embed_battle's attribute surface. Seat 1 = us."""
    def side_views(side):
        active_i = int(str(side.active_index)[-1]) if not isinstance(
            side.active_index, int
        ) else side.active_index
        views, active = {}, None
        for i, mon in enumerate(side.pokemon):
            if mon.id.lower() == "none":
                continue  # the engine pads sides to 6 with filler mons
            v = _mon_view(mon, side, is_active=(i == active_i))
            views[f"shadow: {mon.id.lower()}"] = v
            if i == active_i:
                active = v
        return views, active

    team, active = side_views(state.side_one)
    opp_team, opp_active = side_views(state.side_two)
    available = [
        m for m in (active.moves.values() if active else [])
        if m.current_pp > 0
    ]
    return SimpleNamespace(
        active_pokemon=active,
        opponent_active_pokemon=opp_active,
        team=team,
        opponent_team=opp_team,
        turn=turn,
        force_switch=False,
        trapped=False,
        available_moves=available,
    )

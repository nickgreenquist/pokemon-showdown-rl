"""Battle freeze/rehydrate for the R1 harvest (ch3_search_design_r2.md §4 R1).

`freeze_battle` snapshots battle1's PUBLIC attribute surface — exactly the
fields `embed_battle`, `rl/search/determinize.sample_determinization` and
`rl/search/bridge.battle_to_state` read — into plain picklable data.
`rehydrate_battle` rebuilds a duck-typed battle from it, so harvested
decision states replay offline through the full search pipeline (the R1-0
spike) and the FG battery, with no server.

PURITY (FG-4): this module sees battle1 ONLY. Seat-2 material (true teams,
the opponent's actual orders) is recorded by scripts/ch3_harvest.py into a
SEPARATE privileged file that nothing under rl/search/ ever reads.

Fidelity contract, asserted by tests and re-asserted per-lane by the
recorder itself: embed_battle(rehydrate_battle(freeze_battle(b))) is
bit-identical to embed_battle(b). Everything the encoder reads is carried
verbatim (fractions, PP, boosts, effects, status counters); Move objects
are rebuilt from poke-env's static gen-1 move data behind the shared cache,
with the recorded live PP restored via _MoveView.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from poke_env.battle.effect import Effect
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status

from rl.search.shadow_battle import _cached_move, _MoveView

_BOOST_KEYS = ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")


def freeze_mon(mon: Any) -> dict:
    return {
        "species": mon.species,
        "level": int(mon.level),
        "current_hp": int(mon.current_hp or 0),
        "max_hp": int(mon.max_hp or 0),
        "current_hp_fraction": float(mon.current_hp_fraction),
        "fainted": bool(mon.fainted),
        "stats": dict(mon.stats) if getattr(mon, "stats", None) else None,
        "base_stats": dict(mon.base_stats),
        "types": [t.name for t in mon.types if t is not None],
        "status": mon.status.name if mon.status is not None else None,
        "status_counter": int(getattr(mon, "status_counter", 0)),
        "boosts": {k: int((mon.boosts or {}).get(k, 0)) for k in _BOOST_KEYS},
        "effects": [getattr(e, "name", str(e)) for e in (mon.effects or {})],
        "must_recharge": bool(getattr(mon, "must_recharge", False)),
        "preparing": bool(getattr(mon, "preparing", False)),
        "moves": [(mid, int(m.current_pp)) for mid, m in mon.moves.items()],
    }


def freeze_battle(battle: Any) -> dict:
    team_keys = list(battle.team)
    opp_keys = list(battle.opponent_team)
    return {
        "turn": int(battle.turn),
        "force_switch": bool(battle.force_switch),
        "trapped": bool(battle.trapped),
        "team": [freeze_mon(battle.team[k]) for k in team_keys],
        "opponent_team": [freeze_mon(battle.opponent_team[k]) for k in opp_keys],
        "team_keys": team_keys,
        "opponent_team_keys": opp_keys,
        "active_index": next(
            (i for i, k in enumerate(team_keys)
             if battle.team[k] is battle.active_pokemon), None
        ),
        "opponent_active_index": next(
            (i for i, k in enumerate(opp_keys)
             if battle.opponent_team[k] is battle.opponent_active_pokemon), None
        ),
        "available_moves": [m.id for m in (battle.available_moves or [])],
    }


def _rehydrate_mon(d: dict) -> SimpleNamespace:
    types = [PokemonType[name] for name in d["types"]]
    moves = {}
    for mid, pp in d["moves"]:
        moves[mid] = _MoveView(_cached_move(mid), pp)
    effects = {Effect[name]: 1 for name in d["effects"] if name in Effect.__members__}
    return SimpleNamespace(
        species=d["species"],
        level=d["level"],
        current_hp=d["current_hp"],
        max_hp=d["max_hp"],
        current_hp_fraction=d["current_hp_fraction"],
        fainted=d["fainted"],
        stats=d["stats"],
        base_stats=d["base_stats"],
        types=types,
        type_1=types[0] if types else None,
        type_2=types[1] if len(types) > 1 else None,
        status=Status[d["status"]] if d["status"] is not None else None,
        status_counter=d["status_counter"],
        boosts=dict(d["boosts"]),
        effects=effects,
        must_recharge=d["must_recharge"],
        preparing=d["preparing"],
        moves=moves,
    )


def rehydrate_battle(d: dict) -> SimpleNamespace:
    team_mons = [_rehydrate_mon(m) for m in d["team"]]
    opp_mons = [_rehydrate_mon(m) for m in d["opponent_team"]]
    team = dict(zip(d["team_keys"], team_mons))
    opp_team = dict(zip(d["opponent_team_keys"], opp_mons))
    ai, oi = d["active_index"], d["opponent_active_index"]
    return SimpleNamespace(
        turn=d["turn"],
        force_switch=d["force_switch"],
        trapped=d["trapped"],
        team=team,
        opponent_team=opp_team,
        active_pokemon=team_mons[ai] if ai is not None else None,
        opponent_active_pokemon=opp_mons[oi] if oi is not None else None,
        available_moves=[SimpleNamespace(id=mid) for mid in d["available_moves"]],
    )

"""Gate P-1: 828-float encoder parity, bitwise (plan §9).

WHAT THIS ISOLATES. P-1 does not run the engine. It replays recorded battles
through poke-env, builds the ENGINE-SIDE observable state (`observe.rs`) from the
resulting poke-env `Battle`, runs the RUST encoder on it, and compares the 828
floats bitwise against `embed_battle`. So it tests exactly one thing -- given
identical observable state, do the two encoders agree? -- and leaves "does the
engine produce that state" to the later gates, where it belongs.

Nothing here imports the Rust encoder's inputs from the Python encoder except
the static tables (plan §7.4 requires that: the tables ARE poke-env). The
per-decision state is read off the poke-env `Battle` by this file alone.
"""

from __future__ import annotations

import numpy as np
from poke_env.battle.effect import Effect

from rl.envs.encoder_spec import GEN1
from rl.envs.showdown import (
    _move_id,
    _move_slots_aliased,
    _opponent_move_slots,
    _species_id,
)

# The encoder's own orderings; read from the spec so a spec edit cannot leave
# this harness silently comparing different things.
BOOST_KEYS = GEN1.boost_keys
VOLATILES = GEN1.volatiles
STATUS_INDEX = GEN1.status_index


def _mon_state(mon, is_active: bool) -> dict:
    """One `MonView`.

    Base stats and types are read off the poke-env object DIRECTLY, not looked
    up from the species. They part company after Transform, which replaces
    `_temporary_base_stats` / `_temporary_types` and leaves `_species` alone
    (`pokemon.py:625-636`); the engine has the same split
    (`ActivePokemon.species` is the copy, `Pokemon.species` the original). The
    id suffix wants the NAME, the stat and type blocks want the COPY.
    """
    types = [GEN1.type_index.get(t, -1) for t in mon.types]
    return {
        "species": _species_id(mon.species),
        "base_stats": [int(mon.base_stats[k]) for k in GEN1.base_stat_keys],
        "type_1": types[0] if types else -1,
        # -1, not a repeat: poke-env's damage_multiplier takes ONE chart lookup
        # for a mono-type target, so repeating would square the multiplier.
        "type_2": types[1] if len(types) > 1 else -1,
        "hp": float(mon.current_hp_fraction),
        "fainted": bool(mon.fainted),
        "is_active": bool(is_active),
        "status": STATUS_INDEX.get(mon.status),
        "level": int(mon.level),
    }


def _seat_state(team, active, moves) -> dict:
    mons = list(team)[:6]
    active_slot = None
    for i, m in enumerate(mons):
        if active is not None and m is active:
            active_slot = i
    boosts = [0] * len(BOOST_KEYS)
    vols = [False] * len(VOLATILES)
    counter, preparing = 0, False
    if active is not None:
        boosts = [int(active.boosts[k]) for k in BOOST_KEYS]
        vols = [
            bool(active.must_recharge)
            if eff is Effect.MUST_RECHARGE
            else bool(eff in active.effects)
            for eff in VOLATILES
        ]
        counter = int(active.status_counter)
        preparing = bool(active.preparing)
    return {
        "team": [_mon_state(m, m is active) for m in mons],
        "active_slot": active_slot,
        "boosts": boosts,
        "volatiles": vols,
        "status_counter": counter,
        "preparing": preparing,
        "moves": moves,
    }


def state_from_battle(battle) -> dict:
    """The `ObservableState` for the seat this `Battle` belongs to."""
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    aliased = _move_slots_aliased(battle)

    own_moves = []
    if ours is not None:
        for mv in list(ours.moves.values())[:4]:
            own_moves.append(
                {
                    "id": _move_id(mv),
                    "prob": 1.0,
                    "pp": int(mv.current_pp),
                    "max_pp": int(mv.max_pp),
                }
            )
    opp_moves = []
    if theirs is not None:
        for mv, prob in _opponent_move_slots(theirs):
            opp_moves.append(
                {
                    "id": _move_id(mv),
                    "prob": float(prob),
                    "pp": int(mv.current_pp),
                    "max_pp": int(mv.max_pp),
                }
            )

    return {
        "turn": int(battle.turn),
        "force_switch": bool(battle.force_switch),
        "trapped": bool(battle.trapped),
        "aliased": bool(aliased),
        "own": _seat_state(battle.team.values(), ours, own_moves),
        "opp": _seat_state(battle.opponent_team.values(), theirs, opp_moves),
    }


# --- block accounting -----------------------------------------------------
#
# A mismatch is reported by BLOCK and FIELD, not by raw index: "index 417"
# means nothing, "opponent mon slot 0, base stat 2" is a lead.

from rl.envs.showdown import (  # noqa: E402
    ACTIVE_DIM,
    GLOBAL_DIM,
    ID_DIM,
    MON_DIM,
    MOVE_DIM,
    OBS_DIM,
)

_OWN_MON = GLOBAL_DIM
_OWN_ACTIVE = _OWN_MON + 6 * MON_DIM
_OWN_MOVES = _OWN_ACTIVE + ACTIVE_DIM
_OPP_MON = _OWN_MOVES + 4 * MOVE_DIM
_OPP_ACTIVE = _OPP_MON + 6 * (MON_DIM + 1)
_OPP_MOVES = _OPP_ACTIVE + ACTIVE_DIM
_IDS = OBS_DIM - ID_DIM

_MON_FIELDS = (
    ["hp", "fainted", "is_active"]
    + [f"status[{i}]" for i in range(6)]
    + ["level"]
    + [f"base_stat[{i}]" for i in range(5)]
    + [f"type[{i}]" for i in range(15)]
    + ["matchup_out", "matchup_in", "speed_edge"]
)
_ACTIVE_FIELDS = (
    [f"boost[{k}]" for k in BOOST_KEYS]
    + [f"volatile[{e.name}]" for e in VOLATILES]
    + ["status_counter", "preparing"]
)
_MOVE_FIELDS = (
    ["known", "base_power", "accuracy", "pp", "multiplier", "physical", "status", "priority"]
    + [f"type[{i}]" for i in range(15)]
    + [f"effect[{i}]" for i in range(23)]
)
_GLOBAL_FIELDS = ["turn", "own_fainted", "opp_fainted", "force_switch", "trapped", "aliased"]
_ID_FIELDS = (
    [f"own_species[{i}]" for i in range(6)]
    + [f"opp_species[{i}]" for i in range(6)]
    + [f"own_move[{i}]" for i in range(4)]
    + [f"opp_move[{i}]" for i in range(4)]
)


def describe_index(i: int) -> str:
    if i < GLOBAL_DIM:
        return f"global.{_GLOBAL_FIELDS[i]}"
    if i < _OWN_ACTIVE:
        k, off = divmod(i - _OWN_MON, MON_DIM)
        return f"own_mon[{k}].{_MON_FIELDS[off]}"
    if i < _OWN_MOVES:
        return f"own_active.{_ACTIVE_FIELDS[i - _OWN_ACTIVE]}"
    if i < _OPP_MON:
        k, off = divmod(i - _OWN_MOVES, MOVE_DIM)
        return f"own_move[{k}].{_MOVE_FIELDS[off]}"
    if i < _OPP_ACTIVE:
        k, off = divmod(i - _OPP_MON, MON_DIM + 1)
        return f"opp_mon[{k}].revealed" if off == 0 else f"opp_mon[{k}].{_MON_FIELDS[off - 1]}"
    if i < _OPP_MOVES:
        return f"opp_active.{_ACTIVE_FIELDS[i - _OPP_ACTIVE]}"
    if i < _IDS:
        k, off = divmod(i - _OPP_MOVES, MOVE_DIM)
        return f"opp_move[{k}].{_MOVE_FIELDS[off]}"
    return f"ids.{_ID_FIELDS[i - _IDS]}"


def compare(ref: np.ndarray, ours: np.ndarray) -> list[int]:
    """Indices where the two vectors differ BITWISE (not within a tolerance)."""
    a = ref.view(np.uint32)
    b = ours.view(np.uint32)
    return np.flatnonzero(a != b).tolist()

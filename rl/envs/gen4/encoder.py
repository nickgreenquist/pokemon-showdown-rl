"""`embed_battle_gen4` — the gen-4 observation encoder (layout v0.1).

Additive beside the gen-1 encoder in rl/envs/showdown.py: same block ORDER
(global | own mons x6 | own active | own moves x4 | opp mons x6 with a
revealed flag | opp active | opp moves x4 | id suffix), so a tokenizer
parameterised on this layout can keep the 21-token reshape and the 6 + 4
pointer head. TODAY's rl/networks/entity_deepsets.py is gen-1-bound: it
reads the gen-1 widths and vocab sizes as module constants, refuses any
other obs width and slices a 20-wide id tail (ours is 44) — a gen-4 entity
trunk is a build item (docs/design_gen4/encoder_requirements.md §13); the
smoke config trains the MLP trunk. The fill helpers are this module's own —
the gen-1 ones read gen-1 process flags (v2 / ids), build `Move(id, gen=1)`
and scale priority by 5, none of which holds at gen 4. Widths and offsets
come from rl/envs/gen4/spec.py::LAYOUT; the
tables from GEN4, the vocabs, the class taxonomies, the exact set prior and
the per-battle tracker. Design: docs/design_gen4/encoder_requirements.md
§3–4 (deviations recorded inline where the local tapes contradicted it).

Everything a seat can legitimately observe, nothing more: own team fully
(the request carries items, abilities, stats), the opponent only as revealed
plus the set prior's probabilities (the same information Foul Play
determinizes over). Slot alignment is load-bearing exactly as in gen 1:
own mon block i is switch action i, own move block j is move action 6+j.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from poke_env.battle.effect import Effect
from poke_env.battle.move import Move
from poke_env.battle.move_category import MoveCategory
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.battle.target import Target

from rl.envs.gen4 import prior
from rl.envs.gen4.classes import (
    ABILITY_CLASS_INDEX,
    ABILITY_CLASSES,
    ITEM_CLASS_INDEX,
    ITEM_CLASSES,
    ability_type_multiplier,
)
from rl.envs.gen4.spec import GEN4, LAYOUT, Gen4Layout
from rl.envs.gen4.tracker import BattleTracker
from rl.envs.gen4.vocab import VOCAB, canonical_move_id, to_id

UNKNOWN_ITEM = "unknown_item"  # poke-env's born state (poke_env/data/gen_data.py)

# Per-move overrides of poke-env's gen-4 move data (survey G7): happiness is
# unset in randbats, so Return is 102 BP on all 39 users and the request
# names it "Return 102"; poke-env reports 0.
_BASE_POWER_OVERRIDE = {"return": 102.0}
_ITEM_MOVES = frozenset({"trick", "switcheroo", "knockoff", "thief", "covet"})
_TEAM_CURE_MOVES = frozenset({"healbell", "aromatherapy"})
_HAZARDS = frozenset({"spikes", "toxicspikes", "stealthrock"})
_SCREENS = frozenset({"reflect", "lightscreen"})
_OTHER_SIDE = frozenset({"safeguard", "mist", "tailwind", "luckychant"})
# Inflicted-volatile one-hot of the effect block, by Showdown volatileStatus id.
_MOVE_VOLATILES = (
    "confusion", "substitute", "leechseed", "encore", "taunt", "yawn", "curse",
    "attract", "flinch", "partiallytrapped", "focusenergy", "destinybond",
)
_MOVE_VOL_INDEX = {v: i for i, v in enumerate(_MOVE_VOLATILES)}
_SEC_STATUS = {"brn": 0, "frz": 1, "par": 2, "psn": 3, "slp": 4, "tox": 5}


# --- static per-move data ---------------------------------------------------


@lru_cache(maxsize=4096)
def _move_obj(move_id: str):
    """poke-env's gen-4 Move for an id. Raises for placeholders (`recharge`
    has no gen-4 entry) — callers guard."""
    return Move(move_id, gen=4)


def move_base_power(move) -> float:
    return _BASE_POWER_OVERRIDE.get(canonical_move_id(move.id), float(move.base_power))


@lru_cache(maxsize=4096)
def effect_block(move_id: str) -> np.ndarray:
    """What the move DOES beyond damage (LAYOUT.effect_dim = 45 slots):

    [0..5] inflicted status one-hot (BRN FRZ PAR PSN SLP TOX) | [6] its
    probability | [7] self boost sum /4 (chance-weighted) | [8] foe boost
    sum /4 (chance-weighted, signed) | [9] heal fraction (Rest 1.0, Roost
    0.5) | [10] drain | [11] recoil | [12] extra hits /2 | [13] self-destruct
    | [14] recharge | [15] charge turn | [16..27] inflicted volatile one-hot
    (confusion substitute leechseed encore taunt yawn curse attract flinch
    partiallytrapped focusenergy destinybond), chance-weighted | [28] sets a
    hazard | [29] sets a screen | [30] sets another side condition | [31]
    sets weather | [32] force-switches the foe | [33] self-switch (U-turn) |
    [34] contact | [35] sound | [36] bypasses Substitute | [37] punch | [38]
    Protect-class | [39] hazard removal (Rapid Spin) | [40] traps (Mean
    Look-class volatile) | [41] variable damage (base power 0 while damaging:
    Seismic Toss, Counter, Gyro Ball, Grass Knot, ...) | [42] item swap or
    removal (Trick, Switcheroo, Knock Off, Thief, Covet) | [43] team status
    cure (Heal Bell, Aromatherapy) | [44] thaws the user (defrost flag).
    """
    v = np.zeros(LAYOUT.effect_dim, dtype=np.float32)
    try:
        m = _move_obj(move_id)
        entry = m.entry
    except Exception:  # noqa: BLE001 — unknown ids stay zero
        return v
    if "flags" not in entry or "basePower" not in entry:
        return v  # `recharge`: poke-env's placeholder entry has no move data
    if m.status is not None:
        idx = GEN4.status_index.get(m.status)
        if idx is not None:
            v[idx] = 1.0
            v[6] = 1.0
    boosts = m.boosts or {}
    if boosts:
        if m.target == Target.SELF:
            v[7] = sum(boosts.values()) / 4.0
        else:
            v[8] = sum(boosts.values()) / 4.0
    # Showdown keys the user's own stat drops as `self: {boosts: ...}`
    # (Overheat, Draco Meteor, Superpower, Close Combat, Hammer Arm, ...)
    self_effect = entry.get("self")
    self_boost = self_effect.get("boosts") if isinstance(self_effect, dict) else None
    if self_boost:
        v[7] += sum(self_boost.values()) / 4.0
    vol = entry.get("volatileStatus")
    if vol in _MOVE_VOL_INDEX:
        v[16 + _MOVE_VOL_INDEX[vol]] = 1.0
    for sec in m.secondary or []:
        chance = sec.get("chance", 100) / 100.0
        st = _SEC_STATUS.get(sec.get("status"))
        if st is not None:
            v[st] = 1.0
            v[6] = max(v[6], chance)
        if "boosts" in sec:
            v[8] += sum(sec["boosts"].values()) * chance / 4.0
        sb = sec.get("self", {}).get("boosts") if isinstance(sec.get("self"), dict) else None
        if sb:
            v[7] += sum(sb.values()) * chance / 4.0
        svol = sec.get("volatileStatus")
        if svol in _MOVE_VOL_INDEX:
            v[16 + _MOVE_VOL_INDEX[svol]] = chance
    v[9] = m.heal if m.heal else (1.0 if "heal" in m.flags else 0.0)
    v[10] = m.drain
    v[11] = m.recoil
    v[12] = (m.expected_hits - 1.0) / 2.0
    v[13] = bool(m.self_destruct)
    v[14] = "recharge" in m.flags
    v[15] = "charge" in m.flags
    side = to_id(entry.get("sideCondition"))
    if side in _HAZARDS:
        v[28] = 1.0
    elif side in _SCREENS:
        v[29] = 1.0
    elif side in _OTHER_SIDE:
        v[30] = 1.0
    v[31] = bool(entry.get("weather"))
    v[32] = bool(entry.get("forceSwitch"))
    v[33] = bool(entry.get("selfSwitch"))
    v[34] = "contact" in m.flags
    v[35] = "sound" in m.flags
    v[36] = ("bypasssub" in m.flags) or ("authentic" in m.flags)
    v[37] = "punch" in m.flags
    v[38] = bool(m.is_protect_move)  # poke-env counts Endure in
    v[39] = move_id == "rapidspin"
    v[40] = vol == "trapped" or move_id in ("meanlook", "block", "spiderweb")
    v[41] = (
        move_base_power(m) == 0.0 and m.category != MoveCategory.STATUS
    )
    v[42] = move_id in _ITEM_MOVES
    v[43] = move_id in _TEAM_CURE_MOVES
    v[44] = "defrost" in m.flags
    return v


# --- beliefs -----------------------------------------------------------------


def _revealed(mon) -> frozenset[str]:
    """Canonical ids of the moves a mon has shown. An opponent's Hidden
    Power arrives UNTYPED (`hiddenpower`, prior.HIDDEN_POWER) and is resolved
    to the typed variant the set prior favours given everything else known,
    so it conditions the prior instead of voiding it; one no set explains is
    dropped from the conditioning set (the other revealed moves still
    condition; the slot keeps the untyped stand-in). Own mons carry typed
    ids from the request (`hiddenpowergrass`)."""
    ids = {canonical_move_id(m.id) for m in mon.moves.values()}
    if prior.HIDDEN_POWER in ids:
        ids.discard(prior.HIDDEN_POWER)
        variant = prior.hidden_power_variant(
            to_id(mon.species), frozenset(ids),
            to_id(mon.ability) if mon.ability else None, _known_item(mon),
        )
        if variant:
            ids.add(variant)
    return frozenset(ids)


def _typed_hidden_power(untyped, variant: str):
    """A fresh gen-4 Move for the resolved variant carrying the untyped
    object's PP (the cached `_move_obj` instances are shared — never mutated)."""
    typed = Move(variant, gen=4)
    typed._current_pp = untyped.current_pp
    return typed


def _ability_belief(mon, ident: str, own: bool, tracker: BattleTracker | None) -> dict[str, float]:
    """P(ability) for a mon: certain for own mons and revealed opponents, the
    set prior conditioned on revealed moves otherwise, poke-env's dex
    candidates as the last resort."""
    if own or mon.ability:
        return {to_id(mon.ability): 1.0} if mon.ability else {}
    if tracker is not None and ident in tracker.revealed_ability:
        return {tracker.revealed_ability[ident]: 1.0}
    probs = prior.ability_probs(to_id(mon.species), _revealed(mon), _known_item(mon))
    if probs:
        return probs
    cands = [to_id(a) for a in mon.possible_abilities]
    return {a: 1.0 / len(cands) for a in cands} if cands else {}


def _known_item(mon) -> str | None:
    """The item id if the mon is KNOWN to hold one, else None."""
    item = mon.item
    if not item or item == UNKNOWN_ITEM:
        return None
    return to_id(item)


def _item_belief(mon, own: bool) -> tuple[int, dict[str, float]]:
    """(state, P(item)): state 0 unknown | 1 known held | 2 known none."""
    item = mon.item
    if item == UNKNOWN_ITEM and not own:
        ability = to_id(mon.ability) if mon.ability else None
        probs = prior.item_probs(to_id(mon.species), _revealed(mon), ability)
        return 0, {k: p for k, p in probs.items() if k != "(none)"}
    if not item or item == UNKNOWN_ITEM:
        return 2, {}
    return 1, {to_id(item): 1.0}


def _expected_type_multiplier(move_type, defender, defender_belief, type_chart) -> float:
    """Chart multiplier folded with the defender's ability belief, capped at
    the Box's 4.0 (Dry Skin's x1.25 on a 4x hit would read 5.0)."""
    base = move_type.damage_multiplier(defender.type_1, defender.type_2, type_chart=type_chart)
    if not defender_belief:
        return base
    return min(sum(p * ability_type_multiplier(a, move_type, base) for a, p in defender_belief.items()), 4.0)


def _best_multiplier(attacker, defender, type_chart) -> float:
    return max(
        t.damage_multiplier(defender.type_1, defender.type_2, type_chart=type_chart)
        for t in attacker.types if t is not None
    )


def _best_multiplier_aware(attacker, defender, defender_belief, type_chart) -> float:
    return max(
        _expected_type_multiplier(t, defender, defender_belief, type_chart)
        for t in attacker.types if t is not None
    )


# --- closed-form stats ------------------------------------------------------


def _speed_estimate(mon, is_active: bool, own: bool) -> float:
    """Actual Speed: own mons from the request's real stat; opponents from
    the randbats closed form (EVs 85, IVs 31, no nature — survey §3.3; the
    generator's `evs.spe = 0` on Gyro Ball / Metal Burst / Trick Room sets is
    the one ambiguity and is ignored here). Boosts and paralysis applied for
    on-field mons; Trick Room is a global flag, not folded in."""
    stats = mon.stats if own else None
    spe = stats.get("spe") if stats else None
    if not spe:
        spe = (2 * mon.base_stats["spe"] + 52) * mon.level // 100 + 5
    s = float(spe)
    if is_active:
        b = mon.boosts["spe"]
        s *= (2 + b) / 2.0 if b >= 0 else 2.0 / (2 - b)
        if mon.status == Status.PAR:
            s *= 0.25
    return max(s, 1e-3)


def _speed_edge(mon, foe, mon_is_active: bool, own: bool) -> float:
    a = _speed_estimate(mon, mon_is_active, own)
    d = _speed_estimate(foe, True, not own)
    return (a - d) / (a + d)


# --- fill helpers -------------------------------------------------------------


def _fill_side(vec, o: int, conditions: dict, L: Gen4Layout) -> None:
    """Layer counts for the stackables (Spikes /3, Toxic Spikes /2), presence
    for the rest (poke-env stores a turn stamp; the pool has no screen or
    Safeguard set, so elapsed turns are not carried — mechanics_delta.md §8)."""
    for cond, val in conditions.items():
        idx = L.side_index.get(cond)
        if idx is None:
            continue
        name = cond.name
        if name == "SPIKES":
            vec[o + idx] = min(val, 3) / 3.0
        elif name == "TOXIC_SPIKES":
            vec[o + idx] = min(val, 2) / 2.0
        else:
            vec[o + idx] = 1.0


def _fill_mon(vec, o, mon, ident, foe, active, own, type_chart, tracker, L: Gen4Layout,
              foe_belief: dict[str, float] | None, trick_room: bool = False):
    vec[o] = mon.current_hp_fraction
    vec[o + 1] = mon.fainted
    vec[o + 2] = mon is active
    status = GEN4.status_index.get(mon.status)
    if status is not None:
        vec[o + L.mon_status_off + status] = 1.0
    vec[o + L.mon_level_off] = mon.level / 100.0
    o_st = o + L.mon_stats_off
    for i, key in enumerate(GEN4.base_stat_keys):
        vec[o_st + i] = mon.base_stats[key] / 255.0
    o_ty = o + L.mon_types_off
    for t in mon.types:  # LIVE types: Color Change / Forecast carried
        idx = GEN4.type_index.get(t)
        if idx is not None:
            vec[o_ty + idx] = 1.0
    belief = _ability_belief(mon, ident, own, tracker)
    if foe is not None:
        o_mu = o + L.mon_matchup_off
        vec[o_mu] = _best_multiplier(mon, foe, type_chart)
        vec[o_mu + 1] = _best_multiplier(foe, mon, type_chart)
        o_ma = o + L.mon_matchup_ability_off
        vec[o_ma] = _best_multiplier_aware(mon, foe, foe_belief or {}, type_chart)
        vec[o_ma + 1] = _best_multiplier_aware(foe, mon, belief, type_chart)
        edge = _speed_edge(mon, foe, mon is active, own)
        vec[o + L.mon_speed_off] = -edge if trick_room else edge  # Trick Room inverts every speed comparison
    state, item_probs = _item_belief(mon, own)
    vec[o + L.mon_item_state_off + state] = 1.0
    o_ic = o + L.mon_item_classes_off
    for item, p in item_probs.items():
        ci = ITEM_CLASS_INDEX.get(item)
        if ci is not None:
            vec[o_ic + ci] += p
    if tracker is not None and ident in tracker.consumed:
        vec[o + L.mon_item_consumed_off] = 1.0
    known = len(belief) == 1 and next(iter(belief.values())) >= 0.999
    vec[o + L.mon_ability_state_off + (0 if known else 1)] = 1.0 if belief else 0.0
    o_ac = o + L.mon_ability_classes_off
    for ability, p in belief.items():
        ci = ABILITY_CLASS_INDEX.get(ability)
        if ci is not None:
            vec[o_ac + ci] += p
    return belief


def _fill_active(vec, o, mon, ident, tracker, L: Gen4Layout) -> None:
    for i, key in enumerate(GEN4.boost_keys):
        vec[o + i] = mon.boosts[key] / 6.0
    o_v = o + L.active_volatiles_off
    effects = mon.effects
    for i, effect in enumerate(GEN4.volatiles):
        if effect is Effect.MUST_RECHARGE:
            vec[o_v + i] = mon.must_recharge
        elif effect is Effect.FLASH_FIRE and tracker is not None:
            vec[o_v + i] = ident in tracker.flash_fire  # poke-env ends it one use early (G6)
        elif effect is Effect.LOCKED_MOVE and tracker is not None:
            # poke-env drops `[from]lockedmove` (abstract_battle.py) and never
            # attaches the Effect — measured 0 hits over 41,908 decisions
            vec[o_v + i] = tracker.is_locked(ident) or effect in effects
        else:
            vec[o_v + i] = effect in effects
    n = GEN4.n_volatiles
    vec[o_v + n] = any(m in effects for m in L.trap_members) or Effect.PARTIALLY_TRAPPED in effects
    perish = [i for i, m in enumerate(L.perish_members) if m in effects]
    vec[o_v + n + 1] = bool(perish)
    o_c = o + L.active_counters_off
    if mon.status == Status.SLP:
        attempts = tracker.sleep_attempts.get(ident, mon.status_counter) if tracker is not None else mon.status_counter
        vec[o_c] = min(attempts, 4) / 4.0
    elif mon.status == Status.TOX:
        vec[o_c + 1] = min(mon.status_counter, 16) / 16.0
    vec[o_c + 2] = min(mon.protect_counter, 4) / 4.0
    elapsed = max(
        (effects.get(e, 0) for e in (Effect.ENCORE, Effect.TAUNT, Effect.SLOW_START)),
        default=0,
    )
    if tracker is not None:
        elapsed = max(elapsed, tracker.lock_elapsed(ident))
    vec[o_c + 3] = min(int(elapsed), 8) / 8.0
    if tracker is not None:
        vec[o_c + 4] = min(tracker.sub_hits.get(ident, 0), 3) / 3.0
    if perish:
        vec[o_c + 5] = perish[0] / 3.0  # PERISHn: n turns left
    o_e = o + L.active_extras_off
    vec[o_e] = mon.first_turn
    vec[o_e + 1] = bool(mon.preparing)
    if tracker is not None:
        vec[o_e + 2] = tracker.choice_locked(ident, mon.item)


def _fill_move(vec, o, move, foe, foe_belief, type_chart, L: Gen4Layout, prob: float = 1.0) -> None:
    vec[o] = prob
    vec[o + 1] = move_base_power(move) / 100.0
    vec[o + 2] = move.accuracy
    vec[o + 3] = move.current_pp / move.max_pp if move.max_pp else 0.0
    # an opponent's Hidden Power the prior could not type: poke-env's stand-in
    # is Normal, which is never the truth — leave the type and matchup unknown
    untyped = canonical_move_id(move.id) == prior.HIDDEN_POWER
    if foe is not None and not untyped:
        vec[o + 4] = _expected_type_multiplier(move.type, foe, foe_belief or {}, type_chart)
    vec[o + 5] = move.category == MoveCategory.PHYSICAL
    vec[o + 6] = move.category == MoveCategory.STATUS
    vec[o + 7] = move.priority / L.priority_scale
    vec[o + 8] = move.crit_ratio / 2.0
    idx = None if untyped else GEN4.type_index.get(move.type)
    if idx is not None:
        vec[o + L.move_type_off + idx] = 1.0
    o_e = o + L.move_effect_off
    vec[o_e : o_e + L.effect_dim] = effect_block(canonical_move_id(move.id))


def _move_slots_aliased(battle) -> bool:
    avail = getattr(battle, "available_moves", None)
    return bool(avail) and len(avail) == 1 and avail[0].id in GEN4.special_move_ids


def opponent_move_slots(theirs) -> list[tuple[object, float]]:
    """Up to 4 (Move, probability): revealed first at 1.0, then the prior's
    most likely unrevealed moves conditioned on the revealed ones, the known
    ability and the known item."""
    seen = _revealed(theirs)
    slots = []
    for m in list(theirs.moves.values())[:4]:
        if canonical_move_id(m.id) == prior.HIDDEN_POWER:
            variant = next((s for s in seen if s.startswith(prior.HIDDEN_POWER)), None)
            if variant:
                m = _typed_hidden_power(m, variant)  # the set prior's type, its PP
        slots.append((m, 1.0))
    if len(slots) >= 4:
        return slots[:4]
    species = to_id(theirs.species)
    if species not in prior.known_species():
        return slots
    ability = to_id(theirs.ability) if theirs.ability else None
    for move_id, p in prior.conditional_move_probs(species, seen, ability, _known_item(theirs)):
        if len(slots) >= 4:
            break
        try:
            slots.append((_move_obj(move_id), p))
        except Exception:  # noqa: BLE001
            continue
    return slots


def _ident_of(team: dict, mon) -> str:
    for ident, m in team.items():
        if m is mon:
            return ident
    return ""


def embed_battle_gen4(battle, type_chart, tracker: BattleTracker | None = None) -> np.ndarray:
    """The gen-4 observable-state vector (LAYOUT.obs_dim floats, float32)."""
    L = LAYOUT
    if tracker is not None:
        tracker.update(battle)
    vec = np.zeros(L.obs_dim, dtype=np.float32)
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    own_team = list(battle.team.items())[:6]
    opp_team = list(battle.opponent_team.items())[:6]
    ours_ident = _ident_of(battle.team, ours) if ours is not None else ""
    theirs_ident = _ident_of(battle.opponent_team, theirs) if theirs is not None else ""

    # --- global
    vec[0] = min(battle.turn / L.turn_scale, 1.0)
    vec[1] = sum(m.fainted for m in battle.team.values()) / 6.0
    vec[2] = sum(m.fainted for m in battle.opponent_team.values()) / 6.0
    vec[3] = bool(battle.force_switch)
    vec[4] = bool(battle.trapped)
    vec[5] = bool(battle.maybe_trapped)
    vec[6] = _move_slots_aliased(battle)
    for weather, stamp in battle.weather.items():
        idx = L.weather_index.get(weather)
        if idx is None:
            continue
        vec[L.weather_off + idx] = 1.0
        if tracker is not None and tracker.weather_start is not None:
            elapsed = tracker.weather_elapsed(battle.turn)
            vec[L.weather_off + len(L.weathers)] = min(elapsed, 8) / L.weather_turn_scale
            vec[L.weather_off + len(L.weathers) + 1] = tracker.weather_indefinite
        else:
            vec[L.weather_off + len(L.weathers)] = min(battle.turn - stamp, 8) / L.weather_turn_scale
    for field, stamp in battle.fields.items():
        idx = L.field_index.get(field)
        if idx is None:
            continue
        vec[L.fields_off + idx] = 1.0
        if idx == 0:  # Trick Room elapsed
            vec[L.fields_off + len(L.fields)] = min(battle.turn - stamp, 5) / L.field_turn_scale
    _fill_side(vec, L.own_side_off, battle.side_conditions, L)
    _fill_side(vec, L.opp_side_off, battle.opponent_side_conditions, L)
    if tracker is not None:
        role = battle.player_role or "p1"
        opp_role = "p2" if role == "p1" else "p1"
        vec[L.own_side_off + L.side_dim] = role in tracker.wish_pending
        vec[L.opp_side_off + L.side_dim] = opp_role in tracker.wish_pending
    trick_room = any(f.name == "TRICK_ROOM" for f in battle.fields)

    # beliefs of the two actives (the matchup scalars need the FOE's)
    theirs_belief = _ability_belief(theirs, theirs_ident, False, tracker) if theirs is not None else {}
    ours_belief = _ability_belief(ours, ours_ident, True, tracker) if ours is not None else {}

    # --- own side
    o = L.own_mons_off
    for i, (ident, mon) in enumerate(own_team):
        _fill_mon(vec, o + i * L.mon_dim, mon, ident, theirs, ours, True, type_chart, tracker, L, theirs_belief, trick_room)
    if ours is not None:
        _fill_active(vec, L.own_active_off, ours, ours_ident, tracker, L)
        if not _move_slots_aliased(battle):
            for i, move in enumerate(list(ours.moves.values())[:4]):
                _fill_move(vec, L.own_moves_off + i * L.move_dim, move, theirs, theirs_belief, type_chart, L)

    # --- opponent side
    o = L.opp_mons_off
    for i, (ident, mon) in enumerate(opp_team):
        base = o + i * (L.mon_dim + 1)
        vec[base] = 1.0  # revealed
        _fill_mon(vec, base + 1, mon, ident, ours, theirs, False, type_chart, tracker, L, ours_belief, trick_room)
    if theirs is not None:
        _fill_active(vec, L.opp_active_off, theirs, theirs_ident, tracker, L)
        for i, (move, p) in enumerate(opponent_move_slots(theirs)):
            _fill_move(vec, L.opp_moves_off + i * L.move_dim, move, ours, ours_belief, type_chart, L, p)

    # --- id suffix: species x12 | moves x8 | items x12 | abilities x12
    o = L.ids_off
    for i, (_, mon) in enumerate(own_team):
        vec[o + i] = VOCAB.species_id(mon.species) / L.id_scale
    for i, (_, mon) in enumerate(opp_team):
        vec[o + 6 + i] = VOCAB.species_id(mon.species) / L.id_scale
    if ours is not None and not _move_slots_aliased(battle):
        for i, move in enumerate(list(ours.moves.values())[:4]):
            vec[o + 12 + i] = VOCAB.move_id(move.id) / L.id_scale
    if theirs is not None:
        for i, (move, _) in enumerate(opponent_move_slots(theirs)):
            vec[o + 16 + i] = VOCAB.move_id(move.id) / L.id_scale
    for i, (_, mon) in enumerate(own_team):
        vec[o + 20 + i] = VOCAB.item_id(mon.item) / L.id_scale
        vec[o + 32 + i] = VOCAB.ability_id(mon.ability) / L.id_scale
    for i, (ident, mon) in enumerate(opp_team):
        vec[o + 26 + i] = VOCAB.item_id(_known_item(mon)) / L.id_scale
        belief = _ability_belief(mon, ident, False, tracker)
        if len(belief) == 1 and next(iter(belief.values())) >= 0.999:
            vec[o + 38 + i] = VOCAB.ability_id(next(iter(belief))) / L.id_scale
    return vec


def privileged_block_gen4(vec: np.ndarray) -> np.ndarray:
    """The own-side slice of a gen-4 vector plus the own id tail (6 species, 4
    moves, 6 items, 6 abilities) — the D18 privileged block for the critic,
    taken from the OPPONENT seat's encoding. Returns a copy."""
    L = LAYOUT
    own = vec[L.own_mons_off:L.opp_mons_off]
    o = L.ids_off
    return np.concatenate([own, vec[o:o + 6], vec[o + 12:o + 16], vec[o + 20:o + 26], vec[o + 32:o + 38]])

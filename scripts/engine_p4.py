"""Gate P-4: our §5.5 stats == the `|request|` `stats` + `maxhp` on the tapes.

The engine has no constructor: `team.rs` writes the 24-byte `Pokemon` record
itself, and the stats in it decide every damage roll. If they are off by one the
whole simulation is a different game, silently. So they are checked against the
only ground truth that exists offline -- what Showdown itself reported in the
`|request|` JSON of real recorded gen1randombattle games.

Two things are being checked at once, and both matter:

  1. the ARITHMETIC (`ps_stat`, called through the Rust extension, not a Python
     re-implementation), and
  2. the IV/EV RULES the gen-1 randbats generator applies
     (`showdown/data/random-battles/gen1/teams.ts:271-292`): IVs 30 / EVs 255,
     minus the Substitute HP-divisibility walk and the "minimize confusion
     damage" `evs.atk = 0, ivs.atk = 2` rule.

Transformed mons are EXCLUDED: gen 1 Transform copies the target's stats, so the
request stops describing the set. A `|-transform|` line retires that nickname in
that room for the rest of the tape.
"""

from __future__ import annotations

import json
from collections import Counter

from poke_env import to_id_str
from poke_env.battle.move import Move
from poke_env.data import GenData

import pkmn_gen1

GEN1 = GenData.from_gen(1)

# engine name -> engine enum id, via poke-env's own id normalisation.
SPECIES_ID = {to_id_str(n): i for i, n in enumerate(pkmn_gen1.species_names()) if i}
MOVE_ID = {to_id_str(n): i for i, n in enumerate(pkmn_gen1.move_names()) if i}

# Engine stat order: hp, atk, def, spe, spc.
IV_DEFAULT = [30, 30, 30, 30, 30]
EV_DEFAULT = [255, 255, 255, 255, 255]




def _no_attack_stat_moves(move_ids: list[str]) -> bool:
    """`teams.ts:285-289` verbatim: fixed-damage moves count as non-attacking,
    and so does anything that is not Physical.

    CATEGORY TRAP. In gen 1-3 a move's category comes from its TYPE, not from the
    modern dex: PS rewrites it in `data/mods/gen3/scripts.ts:5-14`
    (Fire/Water/Grass/Ice/Electric/Dark/Psychic/Dragon -> Special, else Physical)
    and gen 1 inherits that. poke-env serves BOTH: the raw `GenData.moves[id]`
    dict keeps the MODERN category (Hyper Beam Special, Razor Leaf Physical),
    while the `Move(id, gen=1)` CLASS applies the gen fix (Hyper Beam Physical,
    Razor Leaf Special). Reading the raw dict here made a Swords-Dance Tentacruel
    look like an all-special set and cost it 67 Attack.
    """
    for mid in move_ids:
        entry = GEN1.moves.get(mid)
        if entry is None:
            return False
        if entry.get("damageCallback") or entry.get("damage"):
            continue
        if Move(mid, gen=1).category.name == "PHYSICAL":
            return False
    return True


def randbats_ivs_evs(species_id: int, level: int, move_ids: list[str]) -> tuple[list[int], list[int]]:
    """The IVs/EVs `randomSet` would have produced for this set."""
    ivs = list(IV_DEFAULT)
    evs = list(EV_DEFAULT)

    if "substitute" in move_ids:
        # "Should be able to use Substitute four times from full HP without
        # fainting": walk evs.hp down by 4 while max HP stays divisible by 4.
        while evs[0] > 3:
            hp = pkmn_gen1.set_stats(species_id, level, ivs, evs)[0]
            if hp % 4 != 0:
                break
            evs[0] -= 4

    if _no_attack_stat_moves(move_ids) and "mimic" not in move_ids and "transform" not in move_ids:
        evs[1] = 0
        ivs[1] = 2

    return ivs, evs


def check_tape(path, report: Counter, failures: list, seen: set) -> None:
    """One pass per tape. Both legs share the transform exclusion.

    TRANSFORM changes what a request MEANS, in two ways
    (`showdown/sim/pokemon.ts:1310-1330`):
      - `storedStats` are copied from the target, so `side.pokemon[].stats` stops
        describing the set; and
      - each copied slot gets `pp = min(5, base)` and, for gen < 5,
        `maxpp = calculatePP(move, ppUps=0)` -- the BASE PP, with no PP Ups.
    Neither is a defect in our arithmetic, so a transformed mon is retired from
    both legs for the rest of the tape. (This is also the mechanism behind the
    Transform non-parity family plan §7.1 declares for P-1: after Transform,
    poke-env's own `pp/maxpp` denominator is base PP, not the PP-Upped max.)
    """
    transformed: set[tuple[str, str]] = set()
    active_owner: dict[str, str] = {}
    from engine_tapes import iter_room_messages, parse_condition, parse_details

    for room, raw in iter_room_messages(path):
        for line in raw.split("\n"):
            if line.startswith("|-transform|"):
                parts = line.split("|")
                if len(parts) > 2 and ": " in parts[2]:
                    transformed.add((room, parts[2].split(": ", 1)[1]))
            elif line.startswith("|switch|") or line.startswith("|drag|"):
                # `|switch|p1a: Nick|...` -- key by SIDE, and let the request's own
                # `side.id` say which side is ours rather than assuming p1.
                parts = line.split("|")
                if len(parts) > 2 and ": " in parts[2]:
                    ident = parts[2]
                    active_owner[(room, ident[:2])] = ident.split(": ", 1)[1]
            if line.startswith("|request|") and len(line) > len("|request|"):
                _check_max_pp(room, line, transformed, active_owner, report, failures)
            if not line.startswith("|request|") or len(line) <= len("|request|"):
                continue
            try:
                req = json.loads(line[len("|request|") :])
            except json.JSONDecodeError:
                report["unparseable_requests"] += 1
                continue
            side = req.get("side") or {}
            for mon in side.get("pokemon") or []:
                ident = mon.get("ident", "")
                nick = ident.split(": ", 1)[1] if ": " in ident else ident
                if (room, nick) in transformed:
                    report["skipped_transformed"] += 1
                    continue
                stats = mon.get("stats")
                if not stats:
                    report["skipped_no_stats"] += 1
                    continue
                name, level = parse_details(mon.get("details", ""))
                sid = SPECIES_ID.get(to_id_str(name))
                if sid is None:
                    failures.append(f"{room} {ident}: species {name!r} not in the engine's table")
                    continue
                move_ids = [to_id_str(m) for m in mon.get("moves") or []]
                unknown = [m for m in move_ids if m not in MOVE_ID]
                if unknown:
                    failures.append(f"{room} {ident}: moves {unknown} not in the engine's table")
                    continue

                ivs, evs = randbats_ivs_evs(sid, level, move_ids)
                hp, atk, dfn, spe, spc = pkmn_gen1.set_stats(sid, level, ivs, evs)

                _, maxhp = parse_condition(mon.get("condition", ""))
                want = {"atk": atk, "def": dfn, "spe": spe, "spa": spc, "spd": spc}
                bad = {k: (v, stats.get(k)) for k, v in want.items() if stats.get(k) != v}
                if maxhp is not None and hp != maxhp:
                    bad["hp"] = (hp, maxhp)
                if maxhp is None:
                    report["skipped_hp_fainted"] += 1
                else:
                    report["hp_checked"] += 1

                report["mons_checked"] += 1
                seen.add((room, nick))
                if bad:
                    report["mismatched"] += 1
                    msg = (
                        f"{room} {ident} L{level} moves={move_ids} ivs={ivs} evs={evs}: "
                        + ", ".join(f"{k} ours={o} request={t}" for k, (o, t) in bad.items())
                    )
                    # A mon reappears in every request of its battle; report the
                    # distinct sets, not the repeats.
                    if msg not in failures and len(failures) < 25:
                        failures.append(msg)

                # The record the engine will actually simulate with.
                rec = pkmn_gen1.pokemon_record(
                    sid, level, [MOVE_ID[m] for m in move_ids[:4]], ivs, evs
                )
                assert len(rec) == 24
                report["records_built"] += 1


def _check_max_pp(room, line, transformed, active_owner, report: Counter, failures: list) -> None:
    """The active mon's `|request|` block reports `maxpp` per move: the same PP Up
    arithmetic `team.rs` writes into the engine record."""
    try:
        req = json.loads(line[len("|request|") :])
    except json.JSONDecodeError:
        return
    side_id = (req.get("side") or {}).get("id")
    nick = active_owner.get((room, side_id))
    if nick is not None and (room, nick) in transformed:
        report["pp_skipped_transformed"] += 1
        return
    for active in req.get("active") or []:
        for slot in active.get("moves") or []:
            mid = MOVE_ID.get(to_id_str(slot.get("id", "")))
            if mid is None or "maxpp" not in slot:
                continue
            ours = pkmn_gen1.max_pp(mid)
            report["pp_checked"] += 1
            if ours != slot["maxpp"]:
                report["pp_mismatched"] += 1
                msg = f"{room} maxpp {slot['id']}: ours={ours} request={slot['maxpp']}"
                if msg not in failures and len(failures) < 25:
                    failures.append(msg)

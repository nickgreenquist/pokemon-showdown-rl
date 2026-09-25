"""R7 B1b -- the engine->engine resample: one belief-consistent world for a
search root, built on `pkmn_gen1.BattleSpec` (plan amendment box 3, item 6).

`rl/search/determinize.py` samples a determinization from a poke-env `Battle`.
G0's positions are ENGINE states, so this is the same fill ported onto the
engine's spec: our own side is taken from the root's bytes (`BattleSpec.
from_visible`, K-class, fully known to us), the foe's side is REBUILT from what
our seat has observed -- the projection (`SearchNode.view` / `revealed_moves`)
-- with every hidden slot drawn from the format's own generator prior:

  * revealed members keep their TRUE PARTY INDEX (so the root's projection
    stays valid over the new bytes), their observed species, level, HP
    percent (W-HP: the largest HP that shows the observed percent under the
    determinized max HP), status (W-SLEEP: remaining sleep turns drawn given
    the observed count), revealed moves with `max_pp - observed uses`, and a
    completion of the moveset drawn from the engine's own set prior
    conditioned on the revealed moves (`Tables.conditional_move_probs`);
  * unrevealed party indices get species drawn from the generator's species
    pool under its team caps (`determinize._TeamCaps`: <=2 per type, <=2 weak
    per spammable type, <=1 level-100; one Ditto per battle), the generator's
    level for that species, and a moveset from the prior;
  * the foe's active carries the observed boosts and volatiles; hidden
    volatile counters (substitute HP, confusion turns) are point estimates,
    named below.

THE CONTRACT, asserted on every draw: the resampled world is OBSERVATIONALLY
IDENTICAL to the true one from our seat -- `world.obs(seat) == root.obs(seat)`
bitwise and our mask unchanged -- and differs only in what we cannot see. A
draw that fails W-VALIDATE or the contract is rejected and redrawn; the count
is returned so a caller can put it on disk.

Stats follow the determinizer's max-DV model (`MonSpec::determinized`, pinned
to `bridge.gen1_stat`); the team bank's `min_atk` variant is a declared
residual (family W-STATS). Disclosure owed wherever a resampled world is
searched (plan §4.1's design note): the sampled bench is systematically
FRESHER than the truth -- max PP, full HP, no status on unrevealed members.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import numpy as np

# The encoder's status index (observe.rs): BRN, FRZ, PAR, PSN, SLP, TOX.
_STATUS_BYTE = {0: 1 << 4, 1: 1 << 5, 2: 1 << 6, 3: 1 << 3, 5: 0b1000_1000}
_SLP = 4
# The encoder's volatile slots (observe.rs): CONFUSION, FOCUS_ENERGY,
# LEECH_SEED, MUST_RECHARGE, PARTIALLY_TRAPPED, REFLECT, SUBSTITUTE.
_V_CONF, _V_FOCUS, _V_LEECH, _V_RECHARGE, _V_TRAPPED, _V_REFLECT, _V_SUB = range(7)
MAX_MOVES = 4


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@lru_cache(maxsize=1)
def _species_map():
    """Engine species id <-> the prior's species name (poke-env ids)."""
    import pkmn_gen1
    from rl.envs import randbats_prior

    names = pkmn_gen1.species_names()
    by_norm = {_norm(n): i for i, n in enumerate(names) if i > 0}
    known = sorted(randbats_prior.known_species())
    name_of = {by_norm[_norm(k)]: k for k in known}
    id_of = {k: by_norm[_norm(k)] for k in known}
    return name_of, id_of, known


def _health_percent(hp: int, max_hp: int) -> int:
    """`track.rs::health_percent` exactly: ceil(100 * hp / max), 99 for a
    non-full mon that would round to 100, 0 when fainted."""
    if hp == 0 or max_hp == 0:
        return 0
    pct = -(-100 * hp // max_hp)
    if pct >= 100 and hp < max_hp:
        return 99
    return min(pct, 100)


def hp_for_percent(pct: int, max_hp: int) -> int:
    """The LARGEST hp in 1..max_hp whose displayed percent is `pct`; if none
    shows exactly `pct` under this max HP, the hp whose percent is nearest.
    The inverse of the percent is an interval, so this is a choice (W-HP)."""
    if pct <= 0:
        return 0
    best, best_err = None, None
    for hp in range(max_hp, 0, -1):
        p = _health_percent(hp, max_hp)
        if p == pct:
            return hp
        err = abs(p - pct)
        if best is None or err < best_err:
            best, best_err = hp, err
    return int(best or 1)


def _complete_moves(tables: Any, species: int, revealed: list[int], rng: np.random.Generator) -> list[int]:
    """The determinizer's `_complete_revealed` on the engine's prior: sample
    `4 - len(revealed)` moves without replacement, probability-proportional
    per draw, from the conditional set distribution."""
    cand = {int(m): float(p) for m, p in tables.conditional_move_probs(species, [int(r) for r in revealed])
            if int(m) not in revealed and p > 0}
    picks: list[int] = []
    need = max(0, MAX_MOVES - len(revealed))
    for _ in range(min(need, len(cand))):
        ids = list(cand)
        ps = np.array([cand[i] for i in ids], dtype=np.float64)
        ps /= ps.sum()
        m = int(ids[int(rng.choice(len(ids), p=ps))])
        picks.append(m)
        del cand[m]
    return picks


def _status_byte(index: int | None, sleep_observed: int, rng: np.random.Generator) -> int:
    if index is None:
        return 0
    if index == _SLP:
        # Gen-1 sleep lasts 1..7 turns; `sleep_observed` have been seen. The
        # remaining count is hidden (family W-SLEEP): uniform over what is left.
        remaining = int(rng.integers(1, max(1, 7 - sleep_observed) + 1))
        return remaining & 0b111
    return _STATUS_BYTE[index]


def resample_world(node: Any, tables: Any, seat: str, rng: np.random.Generator,
                   max_tries: int = 25) -> tuple[Any, dict[str, Any]]:
    """One belief-consistent world for `node` from `seat`'s information set.
    Returns `(world, info)`; `world` is a `pkmn_gen1.SearchNode` sharing the
    root's projection. Raises after `max_tries` rejected draws, naming why."""
    import pkmn_gen1
    from rl.envs import randbats_prior
    from rl.search.determinize import _TeamCaps

    name_of, id_of, known = _species_map()
    foe = "p2" if seat == "p1" else "p1"
    view = node.view(tables, seat)
    opp = view["opp"]
    record = node.revealed_moves(foe)           # reveal order, aligned with opp["team"]
    if len(record) != len(opp["team"]):
        raise RuntimeError(f"projection disagrees with the view: {len(record)} revealed vs {len(opp['team'])} shown")
    own_names = {name_of.get(int(m["species"])) for m in view["own"]["team"]}
    root_obs = node.obs(tables, seat)
    root_mask = node.mask(tables, seat)
    root_reqs = node.requests()
    info = {"tries": 0, "rejected_validate": 0, "rejected_requests": 0, "rejected_obs": 0,
            "charging_dropped": 0, "pool_exhausted": 0, "transformed": 0}
    last_err = ""
    # TRANSFORM is public ("you watched it happen"): the foe's active carries
    # OUR active's species, types, moves (5 PP each in gen 1, minus observed
    # uses) and stats. All of it is our own side's knowledge plus the
    # `|-transform|` line, so a resample may carry it exactly.
    opp_active_slot = opp["active_slot"]
    active_rec = record[int(opp_active_slot)] if opp_active_slot is not None else None
    foe_identity = node.active_identity(foe)
    transformed = (active_rec is not None
                   and int(opp["team"][int(opp_active_slot)]["species"]) != int(foe_identity[0]))
    if transformed:
        info["transformed"] = 1
        own_active_slot = int(view["own"]["active_slot"])          # own team IS party order
        copied_ids = [int(m) for m, _ in node.active_moves(seat) if m != 0]
        rec_uses = {int(r): int(u) for r, u in zip(active_rec[1], list(active_rec[2]) + [0] * 4)}
        transform_live = [(m, max(0, 5 - rec_uses.get(m, 0))) for m in copied_ids]
        transform_stats = [int(x) for x in node.active_stats(seat)]

    for attempt in range(max_tries):
        info["tries"] = attempt + 1
        party: list[Any] = [None] * 6
        moves_of: dict[int, list[tuple[int, int]]] = {}
        caps = _TeamCaps()
        seen: set[str] = set()
        active_party_index = None
        for k, (mon, (pidx, rids, uses, slp_obs)) in enumerate(zip(opp["team"], record)):
            sid = int(mon["species"])
            name = name_of.get(sid)
            if name is not None:
                seen.add(name)
                caps.admit(name)
            rids = [int(r) for r in rids]
            uses = [int(u) for u in uses] + [0] * (len(rids) - len(uses))
            if transformed and mon["is_active"]:
                # The copies are LIVE slots; the stored set is what the mon owns.
                keep = [i for i, r in enumerate(rids) if r not in copied_ids]
                rids = [rids[i] for i in keep]; uses = [uses[i] for i in keep]
            revealed = [(r, max(0, pkmn_gen1.max_pp(r) - u)) for r, u in zip(rids, uses)]
            fill = [(m, pkmn_gen1.max_pp(m)) for m in _complete_moves(tables, sid, rids, rng)]
            moves = (revealed + fill)[:MAX_MOVES]
            moves_of[int(pidx)] = moves
            level = int(mon["level"])
            if mon["fainted"]:
                party[int(pidx)] = pkmn_gen1.MonSpec(sid, level, moves, hp=0, status=0)
            else:
                probe = pkmn_gen1.MonSpec(sid, level, moves)
                hp = hp_for_percent(int(round(float(mon["hp"]) * 100)), int(probe.max_hp))
                party[int(pidx)] = pkmn_gen1.MonSpec(sid, level, moves, hp=hp,
                                                      status=_status_byte(mon["status"], int(slp_obs), rng))
            if mon["is_active"]:
                active_party_index = int(pidx)
        if active_party_index is None:
            raise RuntimeError("the foe has no active member in the view")
        pool = [n for n in known if n not in seen and not (n == "ditto" and "ditto" in own_names)]
        for pidx in [i for i in range(6) if party[i] is None]:
            picked = None
            while pool:
                name = str(pool[int(rng.integers(len(pool)))])
                pool.remove(name)
                if caps.admit(name, count=False):
                    caps.admit(name)
                    picked = name
                    break
            if picked is None:
                info["pool_exhausted"] += 1
                break
            sid = id_of[picked]
            level = int(randbats_prior.species_level(picked) or 100)
            moves = [(m, pkmn_gen1.max_pp(m)) for m in _complete_moves(tables, sid, [], rng)]
            moves_of[pidx] = moves
            party[pidx] = pkmn_gen1.MonSpec(sid, level, moves)
        if any(m is None for m in party):
            last_err = "species pool exhausted under the team caps"
            continue

        # The foe's active: observed boosts and volatiles. Encoder order is
        # (accuracy, atk, def, evasion, spa, spd, spe); the spec wants
        # (atk, def, spe, spc, accuracy, evasion) -- gen 1 has one Special.
        b = [int(x) for x in opp["boosts"]]
        boosts = (b[1], b[2], b[6], b[4], b[0], b[3])
        vols = [bool(x) for x in opp["volatiles"]]
        active_mon = party[active_party_index]
        vdict: dict[str, Any] = {}
        if vols[_V_CONF]:
            vdict["confusion"] = True
            vdict["confusion_turns"] = int(rng.integers(1, 5))      # 1..4 remaining (hidden)
        if vols[_V_FOCUS]:
            vdict["focus_energy"] = True
        if vols[_V_LEECH]:
            vdict["leech_seed"] = True
        if vols[_V_RECHARGE]:
            vdict["recharging"] = True
        if vols[_V_REFLECT]:
            vdict["reflect"] = True
        if vols[_V_SUB]:
            vdict["substitute"] = True
            vdict["substitute_hp"] = min(255, max(1, int(active_mon.max_hp) // 4))   # at creation; damage hidden
        active_status = opp["team"][int(opp["active_slot"])]["status"] if opp["active_slot"] is not None else None
        if active_status == 5:
            vdict["toxic"] = True
            vdict["toxic_turns"] = int(opp["status_counter"])
        if bool(opp["preparing"]):
            rids = [int(r) for r in record[int(opp["active_slot"])][1]]
            slot = None
            if rids:
                ids = [m for m, _ in moves_of[active_party_index]]
                if rids[-1] in ids:
                    slot = ids.index(rids[-1])
            if slot is None:
                info["charging_dropped"] += 1
            else:
                vdict["charging"] = slot + 1          # W-VALIDATE: a ONE-based live move slot
        # PARTIALLY_TRAPPED on the foe means the foe is the VICTIM; the flag
        # lives on the USER, which is our own active, already in our bytes.
        side_kw: dict[str, Any] = {}
        if transformed:
            vdict["transform"] = (seat, own_active_slot + 1)      # (target's player, ONE-based party index)
            side_kw = {"identity": (int(foe_identity[0]), (int(foe_identity[1][0]), int(foe_identity[1][1]))),
                       "live_moves": transform_live, "active_stats": transform_stats}
        side = pkmn_gen1.SideSpec(party, active_party_index, boosts=boosts, volatiles=vdict, **side_kw)
        spec = pkmn_gen1.BattleSpec.from_visible(node.battle()).with_side(foe, side)
        try:
            battle, r1, r2 = spec.build()
        except ValueError as e:
            info["rejected_validate"] += 1
            last_err = f"W-VALIDATE: {e}"
            continue
        if (r1, r2) != tuple(root_reqs):
            info["rejected_requests"] += 1
            last_err = f"requests {(r1, r2)} != root's {tuple(root_reqs)}"
            continue
        world = node.with_battle(battle, r1, r2)
        w_obs = world.obs(tables, seat)
        if not np.array_equal(w_obs, root_obs) or not np.array_equal(world.mask(tables, seat), root_mask):
            diff = np.flatnonzero(w_obs != root_obs)
            info["rejected_obs"] += 1
            info["last_world"] = world              # for a caller's diagnosis
            last_err = f"observation differs on {len(diff)} dims (first {diff[:8].tolist()})"
            continue
        info.pop("last_world", None)
        return world, info
    err = RuntimeError(f"resample_world: {max_tries} draws rejected; last: {last_err}; counters "
                       f"{ {k: v for k, v in info.items() if k != 'last_world'} }")
    err.info = info
    raise err

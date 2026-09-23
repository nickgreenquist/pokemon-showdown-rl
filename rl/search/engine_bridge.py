"""R7 B6 -- the WRITE-SIDE BRIDGE for the ladder: a poke-env public view (live
or a harvest's rehydrated snapshot) plus ONE determinization -> the engine's
`BattleSpec` -> a constructed `SearchNode` root with the CLIENT's projection
(`BattleTracker::from_root`), so the native operator (`rl/search/native.py`)
can search a Showdown battle it did not play in the engine.

Design: docs/search_relook/ENGINE_SEARCH_DESIGN.md §2 (field-by-field) and §3
(tracker init); graded by gate R1-E (`scripts/search_r1e_gate.py --backend
engine`): obs parity against the LIVE root observation outside the declared
families, mask parity exact, controls C1-C8 that must break it.

What is exact (K), determinized (D), sampled (S) and refused here:
  * our side: species, level, moves + PP, HP, status (K); our stats from
    poke-env's `stats` (K; gen1_stat fallback); sleep's REMAINING turns are
    hidden even to us (S, W-SLEEP: sampled 1..7-observed).
  * the foe: revealed mons in reveal order (poke-env's `opponent_team` is
    insertion-ordered by reveal) then the determinizer's bench; moves = the
    revealed ids first (PP = max - observed uses, the A-1a rule; the tracker
    carries the uses) then the determinizer's completion at full PP; HP from
    the public percent through `hp_for_percent` (W-HP: the inverse of a
    percent is an interval); stats from the gen-1 formula at the
    determinization's DVs (W-STATS); status (K), sleep remaining (S).
  * volatiles from poke-env `effects` (K where visible); confusion turns and
    substitute HP hidden (W-CONF, W-SUB); a charging active needs its
    ONE-BASED live slot from `_preparing_move` -- a harvest snapshot carries
    only a bool, so such a root is REFUSED, never defaulted (an index of 0 is
    an out-of-bounds read in the engine, FINDING F6 / W-LASTMOVE).
  * a transformed Ditto on either side is REFUSED in this version
    (W-ACTIVESTATS, the design's "hardest field, stated honestly"); the engine
    -> engine resample (`rl/search/resample.py`) carries Transform, the poke-env
    side does not yet.
  * `last_selected_move`, `last_used_move`, `B_LAST_DAMAGE`: engine defaults
    (W-LASTMOVE, W-LASTDMG); `order[1..]`: our construction (W-ORDER, free);
    the RNG seed IS the chance dial (CRN-1), passed in.

The controls (`ctl`, the gate's `Control` or None) this bridge applies are the
CONSTRUCTION-side ones: reveal swap (C1, the reveal payload), zero move uses
(C2), everything revealed (C5, `from_battle`'s projection), floor HP (C7).
C3 / C4 / C6 / C8 corrupt the INPUT VIEW and the gate applies them to the
battle object before build (`corrupt_battle`), so they are not re-applied
here -- a double application would read as off-by-two.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np

from rl.search.resample import _health_percent, _norm, hp_for_percent

# The gen-1 stat model, PINNED to `rl/search/bridge.py::gen1_stat` (which this
# module does not import: `bridge` pulls `poke_engine` in at import time, and
# the engine env carries no poke_engine). `tests/test_engine_bridge.py` asserts
# the two agree wherever both import. stat-exp term at 65535: floor(255/4).
_EXP_TERM = 63
_DV = 15


def gen1_stat(base: int, level: int, hp: bool = False, dv: int = _DV) -> int:
    core = (base + dv) * 2 + _EXP_TERM
    if hp:
        return math.floor(core * level / 100) + level + 10
    return math.floor(core * level / 100) + 5

N_PARTY = 6
# poke-env status name -> the engine's status byte (layout.rs); SLP is the
# remaining-turn count (hidden) and is sampled; FNT is hp == 0.
_STATUS_BYTE = {"BRN": 1 << 4, "FRZ": 1 << 5, "PAR": 1 << 6, "PSN": 1 << 3, "TOX": 0b1000_1000}
# poke-env Effect name -> the spec's volatile key.
_EFFECT_KEY = {
    "CONFUSION": "confusion", "FOCUS_ENERGY": "focus_energy", "LEECH_SEED": "leech_seed",
    "REFLECT": "reflect", "LIGHT_SCREEN": "light_screen", "MIST": "mist",
    "SUBSTITUTE": "substitute", "BIDE": "bide",
}


class Unbuildable(ValueError):
    """A root this bridge REFUSES (named family), never a degraded build."""

    def __init__(self, family: str, why: str):
        super().__init__(f"{family}: {why}")
        self.family = family


# ---------------------------------------------------------------------------
# Ids
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _species_ids() -> dict[str, int]:
    import pkmn_gen1
    return {_norm(n): i for i, n in enumerate(pkmn_gen1.species_names()) if i > 0}


def species_id(name: str) -> int:
    sid = _species_ids().get(_norm(str(name)))
    if sid is None:
        raise Unbuildable("W-SPECIES", f"no engine species for {name!r}")
    return sid


def move_id(mid: str) -> int:
    """B-0: engine move ids 1..165 ARE poke-env's `num`."""
    from rl.envs.showdown import _move_id
    from rl.search.shadow_battle import _cached_move
    return int(_move_id(_cached_move(mid)))


def move_max_pp(mid: str) -> int:
    from rl.search.shadow_battle import _cached_move
    return int(_cached_move(mid).max_pp or 0)


def _status_name(mon: Any) -> str | None:
    st = getattr(mon, "status", None)
    return None if st is None else str(getattr(st, "name", st))


def _sleep_byte(observed: int, rng: np.random.Generator) -> int:
    remaining = int(rng.integers(1, max(1, 7 - int(observed)) + 1))
    return remaining & 0b111


def _status_byte(mon: Any, rng: np.random.Generator) -> int:
    name = _status_name(mon)
    if name is None or name == "FNT":
        return 0
    if name == "SLP":
        return _sleep_byte(int(getattr(mon, "status_counter", 0) or 0), rng)
    return _STATUS_BYTE.get(name, 0)


def _is_transformed_ditto(mon: Any) -> bool:
    if getattr(mon, "species", None) != "ditto":
        return False
    from poke_env.data import GenData
    dex = GenData.from_gen(1).pokedex["ditto"]
    bs = dict(getattr(mon, "base_stats", {}) or {})
    if any(int(bs.get(k, dex["baseStats"][k])) != int(dex["baseStats"][k]) for k in dex["baseStats"]):
        return True
    types = {str(getattr(t, "name", t)).upper() for t in (getattr(mon, "types", None) or []) if t is not None}
    return bool(types) and types != {str(t).upper() for t in dex["types"]}


def charging_slot(mon: Any) -> int | None:
    """The ONE-BASED live slot a charging active is locked into, or None when
    the source cannot say (a harvest snapshot: `preparing` is a bool only)."""
    if not getattr(mon, "preparing", False):
        return None
    prep = getattr(mon, "_preparing_move", None) or getattr(mon, "preparing_move", None)
    mid = getattr(prep, "id", prep if isinstance(prep, str) else None)
    if not mid:
        return None
    for j, key in enumerate(list(mon.moves)[:4]):
        if key == mid:
            return j + 1
    return None


# ---------------------------------------------------------------------------
# The reveal payload (design §3.1) -- what the CLIENT has seen of each side
# ---------------------------------------------------------------------------

def side_reveal(mons: list[Any], *, zero_uses: bool = False) -> dict:
    revealed_moves: list[list[int]] = []
    move_uses: list[list[int]] = []
    sleep_observed: list[int] = []
    flags: list[list[bool]] = []
    for mon in mons:
        ids, uses = [], []
        for mid, mv in list(mon.moves.items())[:4]:
            ids.append(move_id(mid))
            # THE A-1a RULE: observed spends, never a hard-coded full clip.
            uses.append(0 if zero_uses else max(0, move_max_pp(mid) - int(mv.current_pp)))
        revealed_moves.append(ids)
        move_uses.append(uses)
        st = _status_name(mon)
        n = int(getattr(mon, "status_counter", 0) or 0) if st in ("SLP", "FNT") else 0
        sleep_observed.append(n)
        flags.append([bool(getattr(mon, "must_recharge", False)), bool(getattr(mon, "preparing", False))])
    while len(revealed_moves) < N_PARTY:
        revealed_moves.append([]); move_uses.append([]); sleep_observed.append(0); flags.append([False, False])
    return {"reveal_order": list(range(len(mons))), "revealed_moves": revealed_moves, "move_uses": move_uses,
            "sleep_observed": sleep_observed, "flags_before_faint": flags, "binding_victim_turns": 0}


# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------

def _boosts(active: Any) -> tuple[int, ...]:
    b = dict(getattr(active, "boosts", None) or {})
    def g(k):
        return int(b.get(k, 0))
    # spec order: (atk, def, spe, spc, accuracy, evasion); gen 1 has one Special.
    return (g("atk"), g("def"), g("spe"), g("spa"), g("accuracy"), g("evasion"))


def _volatiles(active: Any, foe_active: Any, rng: np.random.Generator, max_hp: int,
               live_slot_of: dict[str, int]) -> dict[str, Any]:
    v: dict[str, Any] = {}
    for eff in (getattr(active, "effects", None) or {}):
        key = _EFFECT_KEY.get(str(getattr(eff, "name", eff)))
        if key is None:
            continue
        v[key] = True
        if key == "confusion":
            v["confusion_turns"] = int(rng.integers(1, 5))          # hidden, W-CONF
        if key == "substitute":
            v["substitute_hp"] = min(255, max(1, int(max_hp) // 4))  # at creation, W-SUB
    if getattr(active, "must_recharge", False):
        v["recharging"] = True
    if getattr(active, "preparing", False):
        slot = charging_slot(active)
        if slot is None:
            raise Unbuildable("W-LASTMOVE", "charging active with no recoverable live slot")
        v["charging"] = int(slot)
    # Binding sits on the USER: the foe's active is the victim when WE hold it.
    foe_effects = {str(getattr(e, "name", e)) for e in (getattr(foe_active, "effects", None) or {})}
    if foe_effects & {"TRAPPED", "PARTIALLY_TRAPPED", "BINDING"}:
        v["binding"] = True
    return v


def _our_mon(mon: Any, rng: np.random.Generator, ctl: Any):
    import pkmn_gen1
    if _is_transformed_ditto(mon):
        raise Unbuildable("W-ACTIVESTATS", "our transformed Ditto (v1 refuses)")
    sid = species_id(mon.species)
    moves = [(move_id(mid), int(mv.current_pp)) for mid, mv in list(mon.moves.items())[:4]]
    level = int(mon.level)
    max_hp = int(mon.max_hp or 0)
    stats = dict(mon.stats or {})
    bs = dict(mon.base_stats)
    def stat(k):
        return int(stats.get(k) or gen1_stat(int(bs[k]), level))
    st = [max_hp or gen1_stat(int(bs["hp"]), level, hp=True), stat("atk"), stat("def"), stat("spe"), stat("spa")]
    hp = int(mon.current_hp or 0)
    if getattr(mon, "fainted", False) or hp <= 0:
        return pkmn_gen1.MonSpec(sid, level, moves, hp=0, status=0, stats=st)
    return pkmn_gen1.MonSpec(sid, level, moves, hp=hp, status=_status_byte(mon, rng), stats=st)


def _foe_mon(species: str, spec: dict, rng: np.random.Generator, ctl: Any):
    import pkmn_gen1
    from rl.envs import randbats_prior
    live = spec.get("live")
    if live is not None and _is_transformed_ditto(live):
        raise Unbuildable("W-ACTIVESTATS", "the foe's transformed Ditto (v1 refuses)")
    sid = species_id(species)
    level = int(spec.get("level") or randbats_prior.species_level(species) or 100)
    bs = dict(spec.get("base_stats") or {})
    dvs = dict(spec.get("dvs") or {})
    dv = lambda k: int(dvs.get(k, 15))
    max_hp = gen1_stat(int(bs.get("hp", 100)), level, hp=True, dv=dv("hp"))
    st = [max_hp, gen1_stat(int(bs.get("atk", 100)), level, dv=dv("atk")), gen1_stat(int(bs.get("def", 100)), level, dv=dv("def")),
          gen1_stat(int(bs.get("spe", 100)), level, dv=dv("spe")), gen1_stat(int(bs.get("spa", 100)), level, dv=dv("spa"))]
    # Moves: the revealed ids first (PP = max - observed uses), then the
    # determinizer's completion at full PP; never more than four.
    moves: list[tuple[int, int]] = []
    seen: set[int] = set()
    if live is not None:
        for mid, mv in list(live.moves.items())[:4]:
            m = move_id(mid)
            if m and m not in seen:
                moves.append((m, int(mv.current_pp))); seen.add(m)
    for mid in list(spec.get("moves") or []):
        m = move_id(mid)
        if m and m not in seen and len(moves) < 4:
            moves.append((m, move_max_pp(mid))); seen.add(m)
    if not moves:
        raise Unbuildable("W-MOVES", f"{species}: no moves")
    if live is None:
        return pkmn_gen1.MonSpec(sid, level, moves, hp=max_hp, status=0, stats=st)
    if getattr(live, "fainted", False):
        return pkmn_gen1.MonSpec(sid, level, moves, hp=0, status=0, stats=st)
    frac = float(getattr(live, "current_hp_fraction", 1.0) or 0.0)
    pct = int(math.floor(frac * 100)) if getattr(ctl, "hp_floor", False) else int(round(frac * 100))
    hp = hp_for_percent(pct, max_hp) if pct > 0 else 0
    if hp <= 0:
        return pkmn_gen1.MonSpec(sid, level, moves, hp=0, status=0, stats=st)
    return pkmn_gen1.MonSpec(sid, level, moves, hp=hp, status=_status_byte(live, rng), stats=st)


def battle_spec(battle: Any, det: dict, ctl: Any = None, *, seed: int = 0, rng: np.random.Generator | None = None):
    """poke-env battle1 (us = p1) + one determinization -> `pkmn_gen1.BattleSpec`.
    Raises `Unbuildable(family, why)` for a root this bridge refuses."""
    import pkmn_gen1
    rng = rng if rng is not None else np.random.default_rng(seed)
    team = list(battle.team.values())
    if not team or battle.active_pokemon is None:
        raise Unbuildable("W-REQ", "no active on our side")
    our = [_our_mon(m, rng, ctl) for m in team]
    our_active = next(i for i, m in enumerate(team) if m is battle.active_pokemon)
    opp_active = battle.opponent_active_pokemon
    if opp_active is None:
        raise Unbuildable("W-REQ", "no active on the foe's side")
    opponents = det["opponents"]
    foe_party, foe_active = [], None
    for i, (species, spec) in enumerate(opponents.items()):
        foe_party.append(_foe_mon(species, spec, rng, ctl))
        if spec.get("live") is opp_active:
            foe_active = i
    if foe_active is None:
        raise Unbuildable("W-ORDER", "the foe's active is not in the determinization")
    p1 = pkmn_gen1.SideSpec(
        our, our_active, boosts=_boosts(battle.active_pokemon),
        volatiles=_volatiles(battle.active_pokemon, opp_active, rng, int(battle.active_pokemon.max_hp or 0), {}),
    )
    p2 = pkmn_gen1.SideSpec(
        foe_party, foe_active, boosts=_boosts(opp_active),
        volatiles=_volatiles(opp_active, battle.active_pokemon, rng, int(foe_party[foe_active].max_hp), {}),
    )
    return pkmn_gen1.BattleSpec(int(battle.turn), int(seed) & ((1 << 64) - 1), p1, p2)


def build_root(battle: Any, det: dict, ctl: Any = None, *, seed: int = 0, rng: np.random.Generator | None = None):
    """The constructed `SearchNode`: `battle_spec(...).build()` plus the
    client's projection (`SearchNode.from_root`); under control C5 the
    everything-revealed projection (`from_battle`) instead. Returns
    `(node, req_p1, req_p2)`."""
    import pkmn_gen1
    spec = battle_spec(battle, det, ctl, seed=seed, rng=rng)
    try:
        b, r1, r2 = spec.build()
    except ValueError as e:
        raise Unbuildable("W-VALIDATE", str(e)) from e
    if getattr(ctl, "all_revealed", False):
        return pkmn_gen1.SearchNode.from_battle(b, r1, r2), r1, r2
    zero = bool(getattr(ctl, "zero_move_uses", False))
    p1 = side_reveal(list(battle.team.values()))
    p2 = side_reveal(list(battle.opponent_team.values()), zero_uses=zero)
    if getattr(ctl, "reveal_swap", False) and len(p2["reveal_order"]) >= 2:
        p2["reveal_order"][0], p2["reveal_order"][1] = p2["reveal_order"][1], p2["reveal_order"][0]
    return pkmn_gen1.SearchNode.from_root(b, r1, r2, p1, p2), r1, r2

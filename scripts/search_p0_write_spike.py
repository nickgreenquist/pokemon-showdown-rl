"""Phase-0 WRITE-SIDE SPIKE — a THROWAWAY, not the Phase-1 bridge.

`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §7 Phase 0 asks for the sigma-margin
calibration and notes it "strictly follows a spike of Phase 1's write side — run
it on a stubbed subset: no-status, no-boost, no-transform roots, where the write
side is provably exact and W-ACTIVESTATS cannot contaminate the read."

This file is that spike and NOTHING else. It is deliberately narrow:

  * it builds a mid-battle 384-byte `pkmn_gen1.Battle` from (harvest root +
    one RSD determinization) by ASSEMBLING THE BYTES IN PYTHON and handing
    them to `Battle.from_bytes` (`python.rs:290-297`), which validates nothing;
  * it only claims to be correct on the RESTRICTED subset `restricted_ok()`
    defines, and it RAISES on anything outside it rather than degrading;
  * it reads an engine state back into the `ObservableState` dict that
    `pkmn_gen1.Tables.encode` consumes (`pyencode.rs:170-180`, schema in
    `observe.rs`), reusing `scripts/engine_p1.py`'s builder for the ROOT.

It is NOT `SideTracker::from_root` and it is NOT `RootReveal`. Phase 1 still
owns: mutable layout writers in Rust, W-VALIDATE, the tracker, R1-E and its
controls, and every family this file simply defaults (listed in
docs/search_relook/P0_CALIBRATION.md §3).

FIELDS THIS SPIKE SETS, AND FIELDS IT DEFAULTS
----------------------------------------------
SET from the root / determinization (layout.rs offsets):
  B_TURN, B_RNG; per side S_ORDER (identity with order[0] swapped to the
  active, `mechanics.zig:234-236`); per stored Pokemon P_STATS (ours: the
  request's exact stats; theirs: PokemonSet{ivs:[30;5], evs:[255;5]},
  design §2.3), P_MOVES ids+pp, P_HP, P_STATUS, P_SPECIES, P_TYPES, P_LEVEL;
  per ActivePokemon A_STATS (== stored, exact because the subset has no boost
  and no status on either active), A_SPECIES, A_TYPES, A_BOOSTS (zero),
  A_VOLATILES (zero), A_MOVES (== stored).

DEFAULTED, and therefore declared:
  B_LAST_DAMAGE = 0            (family W-LASTDMG; Counter reads 0 damage)
  B_LAST_MOVES  = 0            (family W-LASTDMG)
  S_LAST_SELECTED_MOVE = 0     (family W-LASTMOVE)
  S_LAST_USED_MOVE = 0         (family W-LASTMOVE; Mirror Move sees nothing)
  every hidden volatile counter (confusion turns, substitute HP, sleep turns,
  disable) = 0 — the restricted subset has none of them at the root.

Borrowed: nothing new. `pkmn_gen1` is this repo's own port of pkmn/engine
(MIT, (c) 2021-2024 pkmn contributors), vendored at
`engine/pkmn_gen1/vendor/pkmn-engine`.
"""

from __future__ import annotations

import math
from typing import Any

from poke_env import to_id_str

from rl.envs.encoder_spec import GEN1

try:  # stage a (env `pokemon-showdown-rl`) imports this module for
    import pkmn_gen1  # `restricted_ok` / `augment_root_state` only, and has
except ModuleNotFoundError:  # no engine. Everything that writes bytes asserts.
    pkmn_gen1 = None

# --- layout.rs, verbatim --------------------------------------------------
BATTLE_SIZE = 384
B_SIDES, B_TURN, B_LAST_DAMAGE, B_LAST_MOVES, B_RNG = 0, 368, 370, 372, 376
SIDE_SIZE = 184
S_POKEMON, S_ACTIVE, S_ORDER = 0, 144, 176
S_LAST_SELECTED_MOVE, S_LAST_USED_MOVE = 182, 183
POKEMON_SIZE = 24
P_STATS, P_MOVES, P_HP, P_STATUS, P_SPECIES, P_TYPES, P_LEVEL = 0, 10, 18, 20, 21, 22, 23
ACTIVE_SIZE = 32
A_STATS, A_SPECIES, A_TYPES, A_BOOSTS, A_VOLATILES, A_MOVES = 0, 10, 11, 12, 16, 24
# volatile bit offsets
V_CHARGING, V_BINDING, V_CONFUSION = 4, 5, 7
V_FOCUS_ENERGY, V_SUBSTITUTE, V_RECHARGING = 9, 10, 11
V_LEECH_SEED, V_REFLECT, V_TRANSFORM = 13, 16, 17
V_THRASHING, V_RAGE = 1, 12

class _LazyIds(dict):
    """`pkmn_gen1.species_names()` / `move_names()` keyed by poke-env id, built
    on first use so the module imports in an env without the engine."""

    def __init__(self, fn_name: str):
        super().__init__()
        self._fn = fn_name

    def _fill(self) -> None:
        assert pkmn_gen1 is not None, "pkmn_gen1 is required to write bytes"
        self.update({to_id_str(n): i
                     for i, n in enumerate(getattr(pkmn_gen1, self._fn)()) if i})

    def __missing__(self, k):
        if not len(self):
            self._fill()
            if k in self:
                return self[k]
        raise KeyError(k)


SPECIES_ID = _LazyIds("species_names")
MOVE_ID = _LazyIds("move_names")

# poke-env boost key -> engine packed-i4 nibble index (layout.rs:59-64:
# atk, def, spe, spc, accuracy, evasion). Gen 1 has ONE Special, so poke-env's
# spa and spd both read the engine's spc nibble.
_BOOST_NIBBLE = {"atk": 0, "def": 1, "spe": 2, "spa": 3, "spd": 3,
                 "accuracy": 4, "evasion": 5}
# GEN1.statuses order is (BRN, FRZ, PAR, PSN, SLP, TOX).
_STATUS_BYTE = {"BRN": 1 << 4, "FRZ": 1 << 5, "PAR": 1 << 6, "PSN": 1 << 3}
_ENC_STATUS_IX = {"BRN": 0, "FRZ": 1, "PAR": 2, "PSN": 3, "SLP": 4, "TOX": 5}
# GEN1.volatiles order -> a reader on the engine's u64 word.
_VOL_ORDER = ("CONFUSION", "FOCUS_ENERGY", "LEECH_SEED", "MUST_RECHARGE",
              "PARTIALLY_TRAPPED", "REFLECT", "SUBSTITUTE")
assert tuple(e.name for e in GEN1.volatiles) == _VOL_ORDER, GEN1.volatiles
assert GEN1.boost_keys == ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")

# Volatiles the subset forbids at the ROOT but the engine can CREATE in one ply.
# Anything here that the spike cannot represent in the observation is counted,
# never silently dropped.
_UNMODELLED_CHILD_VOLATILES = (V_TRANSFORM, V_THRASHING, V_RAGE)


class SpikeError(RuntimeError):
    """The spike refused a root. Never a silent degradation."""


# --------------------------------------------------------------------------
# The restriction. Phase 0's whole claim of exactness rests on it.
# --------------------------------------------------------------------------
def restricted_ok(root: dict) -> list[str]:
    """Reasons this harvest root is OUTSIDE the provably-exact subset.

    Empty list = inside. `root` is `harvest.freeze_battle`'s dict.

    Beyond the design's "no status, no stat boosts, no Transform on either
    active" this also excludes CONFUSION / SUBSTITUTE / preparing / recharging
    actives (each carries a HIDDEN counter the write side would have to sample
    — families W-CONF / W-SUB / W-LASTMOVE), any asleep mon ANYWHERE on either
    side (W-SLEEP's hidden turns-left would enter the moment a bench mon is
    switched in), force_switch and trapped roots (a different matrix shape),
    and REFLECT (a live volatile the root would have to carry). Each exclusion
    is counted by the caller and reported.
    """
    bad: list[str] = []
    ai, oi = root["active_index"], root["opponent_active_index"]
    if ai is None or oi is None:
        return ["no_active"]
    if root["force_switch"]:
        bad.append("force_switch")
    if root["trapped"]:
        bad.append("trapped")
    for tag, mons, act in (("own", root["team"], ai),
                           ("opp", root["opponent_team"], oi)):
        for i, m in enumerate(mons):
            if m["status"] == "SLP":
                bad.append(f"{tag}_sleep_anywhere")
            if i != act:
                continue
            if m["status"] is not None:
                bad.append(f"{tag}_status")
            if any(v for v in m["boosts"].values()):
                bad.append(f"{tag}_boost")
            for e in m["effects"]:
                if e in ("TRANSFORM", "CONFUSION", "SUBSTITUTE", "REFLECT",
                         "LEECH_SEED", "FOCUS_ENERGY", "PARTIALLY_TRAPPED"):
                    bad.append(f"{tag}_{e.lower()}")
            if m["preparing"]:
                bad.append(f"{tag}_preparing")
            if m["must_recharge"]:
                bad.append(f"{tag}_recharge")
    return sorted(set(bad))


# --------------------------------------------------------------------------
# Write side: (harvest root + one determinization) -> 384 bytes
# --------------------------------------------------------------------------
def _mon_record(species_name: str, level: int, move_ids: list[int]) -> bytearray:
    sid = SPECIES_ID[to_id_str(species_name)]
    return bytearray(pkmn_gen1.pokemon_record(sid, int(level), move_ids,
                                              [30] * 5, [255] * 5))


def _put16(buf: bytearray, at: int, v: int) -> None:
    buf[at:at + 2] = int(v).to_bytes(2, "little")


def _get16(buf: memoryview | bytes, at: int) -> int:
    return int.from_bytes(buf[at:at + 2], "little")


class RootState:
    """One written root: the bytes plus every index map the caller needs.

    `own_party[i]` is harvest team index i (identity — the party is written in
    `battle.team` order, which is the order our switch actions 0..5 index,
    `matrix.py:129-133`). `opp_party` is the determinized opponent party in
    REVEAL order first, then the unrevealed fills sorted by species, so the
    encoder's opponent block keeps the reveal order the live encoder uses.
    """

    __slots__ = ("bytes", "own_party", "own_active", "opp_party", "opp_active",
                 "own_maxhp", "opp_maxhp", "own_move_ids", "opp_move_ids",
                 "opp_revealed", "opp_species_ix", "root_obs_state", "turn")

    def battle(self, seed: int):
        b = bytearray(self.bytes)
        b[B_RNG:B_RNG + 8] = int(seed & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")
        return pkmn_gen1.Battle.from_bytes(bytes(b))

    # --- action mapping (layout.rs:377-383 `slot_of_party_index`) ----------
    def _order(self, side: int) -> list[int]:
        base = B_SIDES + side * SIDE_SIZE
        return list(self.bytes[base + S_ORDER:base + S_ORDER + 6])

    def own_slot_of_party(self, party_ix: int) -> int:
        """One-based CURRENT-ORDER slot holding our party index (== the harvest
        team index, which is what mask indices 0..5 name)."""
        o = self._order(0)
        return o.index(party_ix + 1) + 1

    def own_party_of_slot(self, slot: int) -> int:
        return self._order(0)[slot - 1] - 1

    def opp_slot_of_species(self, species: str) -> int:
        o = self._order(1)
        return o.index(self.opp_species_ix[species] + 1) + 1

    def opp_move_slot(self, move_id: str) -> int:
        """One-based slot of a determinized opponent move in the ACTIVE's
        stored order — the same order `matrix.py`'s L6 classes 0..3 index."""
        want = MOVE_ID[to_id_str(move_id)]
        return self.opp_move_ids.index(want) + 1


def build_root(root: dict, det: dict, obs_state: dict) -> RootState:
    """Assemble the 384 bytes. Raises `SpikeError` outside the subset."""
    bad = restricted_ok(root)
    if bad:
        raise SpikeError(f"root outside the restricted subset: {bad}")

    buf = bytearray(BATTLE_SIZE)
    st = RootState()
    st.root_obs_state = obs_state
    st.turn = int(root["turn"])

    # ---- our side (p1): stats are KNOWN exactly from the request ----------
    own = root["team"]
    st.own_party = list(range(len(own)))
    st.own_active = int(root["active_index"])
    st.own_maxhp = []
    base = B_SIDES + 0 * SIDE_SIZE
    for i, m in enumerate(own):
        mids = [MOVE_ID[to_id_str(mid)] for mid, _pp in m["moves"]][:4]
        if not mids:
            raise SpikeError(f"own mon {m['species']} has no moves")
        rec = _mon_record(m["species"], m["level"], mids)
        stats = m["stats"]
        if stats is None:
            raise SpikeError(f"own mon {m['species']} has no request stats")
        # P_STATS in the engine's order (hp, atk, def, spe, spc); poke-env's
        # spa == spd in gen 1 and both are the engine's one spc.
        for k, ix in (("hp", 0), ("atk", 1), ("def", 2), ("spe", 3), ("spa", 4)):
            _put16(rec, P_STATS + 2 * ix, int(stats[k]))
        maxhp = int(stats["hp"])
        if m["fainted"] or not int(m["current_hp"] or 0):
            hp = 0  # poke-env RESETS a fainted mon's max_hp to 100 (2.2% of
        elif int(m["max_hp"]) == maxhp:  # own mon-slots, all fainted) — the
            hp = int(m["current_hp"])    # request's stats.hp stays authoritative
        else:
            raise SpikeError(
                f"{m['species']} alive with max_hp {m['max_hp']} != stats.hp {maxhp}")
        _put16(rec, P_HP, hp)
        rec[P_STATUS] = _status_byte(m)
        for j, (_mid, pp) in enumerate(m["moves"][:4]):
            rec[P_MOVES + 2 * j + 1] = min(int(pp), rec[P_MOVES + 2 * j + 1])
        st.own_maxhp.append(int(m["max_hp"]))
        at = base + S_POKEMON + i * POKEMON_SIZE
        buf[at:at + POKEMON_SIZE] = rec
    st.own_move_ids = [MOVE_ID[to_id_str(mid)]
                       for mid, _pp in own[st.own_active]["moves"]][:4]

    # ---- their side (p2): the determinization ----------------------------
    opps = det["opponents"]
    revealed = [m["species"] for m in root["opponent_team"]]
    st.opp_revealed = set(revealed)
    order = revealed + sorted(s for s in opps if s not in st.opp_revealed)
    if len(order) > 6:
        raise SpikeError(f"determinized opponent party is {len(order)} long")
    st.opp_party = order
    st.opp_species_ix = {s: i for i, s in enumerate(order)}
    st.opp_active = st.opp_species_ix[
        root["opponent_team"][root["opponent_active_index"]]["species"]]
    st.opp_maxhp = []
    base = B_SIDES + 1 * SIDE_SIZE
    live_by_species = {m["species"]: m for m in root["opponent_team"]}
    for i, sp in enumerate(order):
        spec = opps[sp]
        mids = [MOVE_ID[to_id_str(mid)] for mid in spec["moves"]][:4]
        if not mids:
            raise SpikeError(f"determinized {sp} has no moves")
        rec = _mon_record(sp, spec["level"], mids)
        maxhp = _get16(rec, P_STATS)
        st.opp_maxhp.append(maxhp)
        live = live_by_species.get(sp)
        if live is not None:
            frac = float(live["current_hp_fraction"])
            _put16(rec, P_HP, max(0, min(maxhp, round(frac * maxhp))))
            rec[P_STATUS] = _status_byte(live)
            # A-1a's rule: a revealed foe move's PP is max_pp - observed uses,
            # which poke-env already tracks in `current_pp` (track.rs:50-57).
            pp_by_id = {mid: pp for mid, pp in live["moves"]}
            for j, mid in enumerate(spec["moves"][:4]):
                if mid in pp_by_id:
                    rec[P_MOVES + 2 * j + 1] = min(int(pp_by_id[mid]),
                                                   rec[P_MOVES + 2 * j + 1])
        at = base + S_POKEMON + i * POKEMON_SIZE
        buf[at:at + POKEMON_SIZE] = rec
    st.opp_move_ids = [MOVE_ID[to_id_str(mid)]
                       for mid in opps[order[st.opp_active]]["moves"]][:4]

    # ---- order + the two ActivePokemon blocks ----------------------------
    for side, active, n in ((0, st.own_active, len(own)), (1, st.opp_active, len(order))):
        base = B_SIDES + side * SIDE_SIZE
        o = list(range(1, n + 1)) + [0] * (6 - n)
        o[0], o[active] = o[active], o[0]
        buf[base + S_ORDER:base + S_ORDER + 6] = bytes(o)
        rec = buf[base + S_POKEMON + active * POKEMON_SIZE:
                  base + S_POKEMON + (active + 1) * POKEMON_SIZE]
        act = bytearray(ACTIVE_SIZE)
        # exact on this subset: no boost and no status on either active, so
        # `switchIn`'s output (mechanics.zig:243-250) is the stored stats.
        act[A_STATS:A_STATS + 10] = rec[P_STATS:P_STATS + 10]
        act[A_SPECIES] = rec[P_SPECIES]
        act[A_TYPES] = rec[P_TYPES]
        act[A_MOVES:A_MOVES + 8] = rec[P_MOVES:P_MOVES + 8]
        buf[base + S_ACTIVE:base + S_ACTIVE + ACTIVE_SIZE] = act
        # S_LAST_SELECTED_MOVE / S_LAST_USED_MOVE stay 0 — family W-LASTMOVE.

    _put16(buf, B_TURN, st.turn)
    # B_LAST_DAMAGE / B_LAST_MOVES stay 0 — family W-LASTDMG.
    st.bytes = bytes(buf)
    validate(st)
    return st


def _status_byte(mon: dict) -> int:
    s = mon["status"]
    if s is None or s == "FNT":
        return 0
    if s == "SLP":  # excluded by restricted_ok; W-SLEEP would sample this
        raise SpikeError("sleep is outside the spike's subset")
    if s == "TOX":
        return (1 << 3) | (1 << 7)
    return _STATUS_BYTE[s]


def validate(st: RootState) -> None:
    """W-VALIDATE, the subset a Python spike can afford (design §2.4)."""
    b = st.bytes
    assert len(b) == BATTLE_SIZE
    for side, n in ((0, len(st.own_party)), (1, len(st.opp_party))):
        base = B_SIDES + side * SIDE_SIZE
        order = list(b[base + S_ORDER:base + S_ORDER + 6])
        assert sorted(o for o in order if o) == list(range(1, n + 1)), order
        alive = 0
        for i in range(n):
            at = base + S_POKEMON + i * POKEMON_SIZE
            hp, mx = _get16(b, at + P_HP), _get16(b, at + P_STATS)
            assert hp <= mx, f"hp {hp} > maxhp {mx}"
            alive += hp > 0
            assert 1 <= b[at + P_SPECIES] <= 151
            assert 1 <= b[at + P_LEVEL] <= 100
            assert any(b[at + P_MOVES + 2 * j] for j in range(4))
            for j in range(4):
                assert 0 <= b[at + P_MOVES + 2 * j] <= 165
        assert alive >= 1, "a side has no unfainted mon"
        assert _get16(b, base + S_POKEMON + (order[0] - 1) * POKEMON_SIZE + P_HP) > 0
    bat = pkmn_gen1.Battle.from_bytes(b)
    for p in ("p1", "p2"):
        assert bat.choices(p, "move"), f"{p} has no legal move-request choice"


# --------------------------------------------------------------------------
# Read side: an engine state -> the ObservableState dict `Tables.encode` eats
# --------------------------------------------------------------------------
def _read_side(b: bytes, side: int) -> dict:
    base = B_SIDES + side * SIDE_SIZE
    order = list(b[base + S_ORDER:base + S_ORDER + 6])
    active = order[0] - 1
    mons = []
    for i in range(6):
        at = base + S_POKEMON + i * POKEMON_SIZE
        if b[at + P_SPECIES] == 0:
            break
        mons.append({
            "hp": _get16(b, at + P_HP),
            "max_hp": _get16(b, at + P_STATS),
            "status": b[at + P_STATUS],
            "species": b[at + P_SPECIES],
            "level": b[at + P_LEVEL],
            "moves": [(b[at + P_MOVES + 2 * j], b[at + P_MOVES + 2 * j + 1])
                      for j in range(4)],
        })
    a = base + S_ACTIVE
    vol = int.from_bytes(b[a + A_VOLATILES:a + A_VOLATILES + 8], "little")
    boosts_raw = int.from_bytes(b[a + A_BOOSTS:a + A_BOOSTS + 4], "little")
    def nib(k: int) -> int:
        v = (boosts_raw >> (4 * k)) & 0xF
        return v - 16 if v >= 8 else v
    return {
        "order": order, "active": active, "mons": mons, "vol": vol,
        "boosts": [nib(k) for k in range(6)],
        "active_moves": [(b[a + A_MOVES + 2 * j], b[a + A_MOVES + 2 * j + 1])
                         for j in range(4)],
        "active_species": b[a + A_SPECIES],
    }


def _status_ix(byte: int) -> int | None:
    if byte == 0:
        return None
    if byte & 0b111:
        return _ENC_STATUS_IX["SLP"]
    if (byte & (1 << 3)) and (byte & (1 << 7)):
        return _ENC_STATUS_IX["TOX"]
    for name, bit in (("PSN", 3), ("BRN", 4), ("FRZ", 5), ("PAR", 6)):
        if byte & (1 << bit):
            return _ENC_STATUS_IX[name]
    return None


def child_state(st: RootState, battle, p1_req: str, counters: dict,
                raw: bytes | None = None) -> dict:
    """The `ObservableState` dict for OUR seat at an engine child.

    L-BOUNDARY (design §1.3): our own side is read exactly from the engine;
    the opponent's side keeps the ROOT's information boundary — the identity
    and stats blocks of a mon the opponent has never revealed stay absent
    until the transition reveals it, and its HP comes back through Showdown's
    own `ceil(100*hp/maxhp)` percentage grain (`track.rs:28-38`), not the
    exact determinized integer.
    """
    b = raw
    if b is None:
        b = battle.bytes()
        if not isinstance(b, (bytes, bytearray)):
            b = bytes(b)
    root_state = st.root_obs_state
    p1, p2 = _read_side(b, 0), _read_side(b, 1)
    out = {
        "turn": _get16(b, B_TURN),
        "force_switch": p1_req == "switch",
        "trapped": False,
        # the engine's own hard-lock set (layout.rs:200-203 `forced()`) is
        # exactly poke-env's single-offered-move alias.
        "aliased": p1_req == "move" and bool(
            p1["vol"] & ((1 << V_RECHARGING) | (1 << V_CHARGING)
                         | (1 << V_THRASHING) | (1 << V_RAGE))),
        "own": _own_seat(st, root_state, p1, p2, counters),
        "opp": _opp_seat(st, root_state, p2, p1, counters),
    }
    return out


def _volatiles(me: dict, foe: dict) -> list[bool]:
    v = me["vol"]
    return [
        bool(v & (1 << V_CONFUSION)),
        bool(v & (1 << V_FOCUS_ENERGY)),
        bool(v & (1 << V_LEECH_SEED)),
        bool(v & (1 << V_RECHARGING)),
        # V_BINDING sits on the USER (layout.rs:71-73); poke-env's
        # PARTIALLY_TRAPPED sits on the VICTIM, so read the FOE's bit.
        bool(foe["vol"] & (1 << V_BINDING)),
        bool(v & (1 << V_REFLECT)),
        bool(v & (1 << V_SUBSTITUTE)),
    ]


def _boosts(me: dict) -> list[int]:
    return [me["boosts"][_BOOST_NIBBLE[k]] for k in GEN1.boost_keys]


def _own_seat(st: RootState, root_state: dict, me: dict, foe: dict,
              counters: dict) -> dict:
    team = []
    for i, base_mon in enumerate(root_state["own"]["team"]):
        m = dict(base_mon)
        e = me["mons"][i]
        m["hp"] = e["hp"] / e["max_hp"]
        m["fainted"] = e["hp"] == 0
        m["is_active"] = i == me["active"]
        m["status"] = _status_ix(e["status"])
        team.append(m)
    if me["vol"] & (1 << V_TRANSFORM):
        counters["own_transform"] = counters.get("own_transform", 0) + 1
    moves = [{"id": mid, "prob": 1.0, "pp": pp,
              "max_pp": pkmn_gen1.max_pp(mid) if mid else 0}
             for mid, pp in me["active_moves"] if mid]
    return {
        "team": team, "active_slot": me["active"],
        "boosts": _boosts(me), "volatiles": _volatiles(me, foe),
        # W-SLEEP: the OBSERVED sleep counter. The subset forbids sleep at the
        # root, so a mon asleep at a child fell asleep THIS ply and poke-env's
        # observed counter is 0 — exact, not a stub.
        "status_counter": 0,
        "preparing": bool(me["vol"] & (1 << V_CHARGING)),
        "moves": moves,
    }


def _opp_seat(st: RootState, root_state: dict, me: dict, foe: dict,
              counters: dict) -> dict:
    """The opponent's half at the ROOT's information boundary, advanced by
    exactly what one ply reveals."""
    root_team = root_state["opp"]["team"]
    n_revealed = len(root_team)
    team = [dict(m) for m in root_team]
    active_party = me["active"]
    for i in range(n_revealed):
        e = me["mons"][i]
        # Showdown reports the foe's HP as an integer percent (track.rs:28-38).
        team[i]["hp"] = 0.0 if e["hp"] == 0 else math.ceil(100 * e["hp"] / e["max_hp"]) / 100
        team[i]["fainted"] = e["hp"] == 0
        team[i]["is_active"] = i == active_party
        team[i]["status"] = _status_ix(e["status"])
    if active_party >= n_revealed:
        # the transition REVEALED an unrevealed bench mon — the protocol shows
        # its species, level and types the moment it switches in.
        e = me["mons"][active_party]
        sp = st.opp_party[active_party]
        counters["opp_reveal"] = counters.get("opp_reveal", 0) + 1
        team.append(_reveal_mon(sp, e, st))
        active_slot = len(team) - 1
    else:
        active_slot = active_party
    if me["vol"] & (1 << V_TRANSFORM):
        counters["opp_transform"] = counters.get("opp_transform", 0) + 1
    # REVEALED moves only, in reveal order; `encoder.rs::opponent_move_slots`
    # does the prior conditioning and slot fill (engine_p1.py's contract).
    if active_slot < n_revealed:
        moves = list(root_state["opp"]["moves"]) if active_slot == root_state["opp"]["active_slot"] \
            else _root_revealed_moves(st, active_slot)
    else:
        moves = []
    moves = _advance_pp(moves, me["active_moves"])
    return {
        "team": team, "active_slot": active_slot,
        "boosts": _boosts(me), "volatiles": _volatiles(me, foe),
        "status_counter": 0,
        "preparing": bool(me["vol"] & (1 << V_CHARGING)),
        "moves": moves,
    }


def _reveal_mon(species: str, e: dict, st: RootState) -> dict:
    from poke_env.data import GenData
    entry = GenData.from_gen(1).pokedex[species]
    types = [GEN1.type_index.get(_pt(t), -1) for t in entry["types"]]
    return {
        "species": SPECIES_ID[to_id_str(species)],
        "base_stats": [int(entry["baseStats"][k]) for k in GEN1.base_stat_keys],
        "type_1": types[0] if types else -1,
        "type_2": types[1] if len(types) > 1 else -1,
        "hp": 0.0 if e["hp"] == 0 else math.ceil(100 * e["hp"] / e["max_hp"]) / 100,
        "fainted": e["hp"] == 0,
        "is_active": True,
        "status": _status_ix(e["status"]),
        "level": e["level"],
    }


def _pt(name: str):
    from poke_env.battle.pokemon_type import PokemonType
    return PokemonType.from_name(name)


def _root_revealed_moves(st: RootState, slot: int) -> list[dict]:
    """Revealed moves of a non-active REVEALED opponent mon, from the root."""
    return st.root_obs_state.get("_opp_revealed_moves", {}).get(slot, [])


def augment_root_state(root: dict, obs_state: dict) -> dict:
    """`state_from_battle` carries only the ACTIVE's revealed moves. A child
    where the opponent switched to another REVEALED mon needs that mon's
    revealed moves, so record them per slot on the root state. The key is
    private (`parse_state` reads named keys only, `pyencode.rs:277-289`)."""
    from rl.envs.showdown import _move_id, _move_obj
    by_slot: dict[int, list[dict]] = {}
    for i, m in enumerate(root["opponent_team"]):
        slots = []
        for mid, pp in m["moves"][:4]:
            mv = _move_obj(mid)
            slots.append({"id": _move_id(mv), "prob": 1.0, "pp": int(pp),
                          "max_pp": int(mv.max_pp)})
        by_slot[i] = slots
    obs_state = dict(obs_state)
    obs_state["_opp_revealed_moves"] = by_slot
    return obs_state


def _advance_pp(moves: list[dict], engine_active_moves: list[tuple]) -> list[dict]:
    """Decrement a revealed move's PP by what the engine actually spent."""
    live = {mid: pp for mid, pp in engine_active_moves if mid}
    out = []
    for mv in moves:
        m = dict(mv)
        if m["id"] in live:
            m["pp"] = min(m["pp"], live[m["id"]])
        out.append(m)
    return out

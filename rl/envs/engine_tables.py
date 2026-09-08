"""Static tables for the engine collector's Rust encoder (plan §7.4).

Borrowed: the engine itself is pkmn/engine (MIT, (c) 2021-2024 pkmn
contributors), vendored at `engine/pkmn_gen1/vendor/pkmn-engine`. This module
borrows nothing -- it exists so the Rust encoder holds NO game data of its own.

Everything the Rust encoder reads about species, moves and type effectiveness is
built HERE, from poke-env, because poke-env is the single source
`rl/envs/showdown.py::embed_battle` reads. `_effect_block` is IMPORTED from that
module rather than reimplemented, so the 23 v2 effect floats are the very same
float32 values, bit for bit.

The bundle is fingerprinted (sha256 over the concatenated arrays) so a run can
record which tables produced its transitions, next to ENCODER_FINGERPRINT.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

import numpy as np
from poke_env.battle.move import Move
from poke_env.battle.move_category import MoveCategory
from poke_env.data import GenData

from rl.envs import randbats_prior
from rl.envs.encoder_spec import GEN1, EncoderSpec
from rl.envs.showdown import _effect_block, _move_obj, _species_id

# Index 0 in every table is the "unknown / absent" row, so table index == the
# encoder's id (dex number for species, move number for moves).
UNKNOWN = 0


def _species_rows(spec: EncoderSpec) -> tuple[list[list[int]], list[tuple[int, int]]]:
    gd = GenData.from_gen(spec.gen)
    lo, hi = spec.species_num_range
    n = hi + 1
    base = [[0] * len(spec.base_stat_keys) for _ in range(n)]
    types: list[tuple[int, int]] = [(-1, -1)] * n
    by_num = {}
    for entry in gd.pokedex.values():
        num = entry.get("num", 0)
        if lo <= num <= hi and num not in by_num:
            by_num[num] = entry
    for num, entry in by_num.items():
        base[num] = [entry["baseStats"][k] for k in spec.base_stat_keys]
        ts = entry["types"]
        # type_2 is -1 (= None) for a mono-type species. poke-env's
        # `damage_multiplier` takes ONE chart lookup when type_2 is None, so a
        # repeated type would square the multiplier -- 2x would become 4x.
        idx = [spec.type_index.get(_pokemon_type(t), -1) for t in ts]
        types[num] = (idx[0], idx[1] if len(idx) > 1 else -1)
    return base, types


@lru_cache(maxsize=64)
def _pokemon_type(name: str):
    from poke_env.battle.pokemon_type import PokemonType

    return PokemonType.from_name(name)


def _move_rows(spec: EncoderSpec):
    gd = GenData.from_gen(spec.gen)
    lo, hi = spec.move_num_range
    rows = [
        (0, 0.0, 0, 0, False, False, -1, False, [0.0] * 23)
        for _ in range(hi + 1)
    ]
    seen: set[int] = set()
    for move_id, entry in gd.moves.items():
        num = entry.get("num", 0)
        if not (lo <= num <= hi) or num in seen:
            continue
        seen.add(num)
        try:
            m = _move_obj(move_id) if spec.gen == 1 else Move(move_id, gen=spec.gen)
        except Exception:  # pragma: no cover - a dex entry poke-env cannot build
            continue
        rows[num] = (
            m.base_power,
            float(np.float32(m.accuracy)),
            m.max_pp,
            m.priority,
            m.category == MoveCategory.PHYSICAL,
            m.category == MoveCategory.STATUS,
            spec.type_index.get(m.type, -1),
            # OHKO: read by the most-damage-typed anchor only (H&L score it at
            # 120 because poke-env reports base power 0), never by the encoder —
            # which is why it is NOT in `fingerprint` below.
            bool(entry.get("ohko")),
            [float(x) for x in _effect_block(move_id)],
        )
    return rows


def _type_chart(spec: EncoderSpec) -> list[list[float]]:
    """`chart[defender][attacker]`, matching poke-env's
    `type_chart[type_1.name][self.name]` indexing."""
    chart = GenData.from_gen(spec.gen).type_chart
    return [
        [float(chart[d.name][a.name]) for a in spec.types]
        for d in spec.types
    ]


def _prior_rows(spec: EncoderSpec = GEN1):
    """The vendored set prior as DATA: per species, its candidate move ids and
    the 4,000 sampled sets `randbats_prior` draws from Showdown's `randomSet`.

    Only the draws travel. The conditioning, the ordering and the slot
    assignment are done in Rust (`tables.rs::SpeciesPrior`,
    `encoder.rs::opponent_move_slots`), because those are per-decision RULES the
    engine side must reproduce -- plan §7.3 calls the opponent slot assignment
    load-bearing, and a parity harness that imported the rule from the reference
    encoder could not falsify it.

    `ids` keeps the reference's own ordering (`sorted()` over the move ID
    STRINGS), which a stable sort by probability then preserves exactly as
    Python's stable sort does.
    """
    if spec.gen != 1:
        raise NotImplementedError("the set prior is gen-1 randbats data")
    move_num = {}
    gd = GenData.from_gen(spec.gen)
    lo, hi = spec.move_num_range
    for move_id, entry in gd.moves.items():
        num = entry.get("num", 0)
        if lo <= num <= hi:
            move_num[move_id] = num

    rows = []
    for species in sorted(randbats_prior.known_species()):
        sid = _species_id(species, spec)
        if not sid:
            continue
        ids, mat = randbats_prior._samples(species)
        if not ids:
            continue
        # A candidate poke-env cannot map is dropped here, matching the
        # reference's own `except: continue` when it cannot build the Move.
        keep = [(j, move_num[m]) for j, m in enumerate(ids) if m in move_num]
        col_of = {j: k for k, (j, _) in enumerate(keep)}
        draws = [
            [col_of[j] for j in np.flatnonzero(row) if j in col_of]
            for row in mat
        ]
        rows.append((sid, [num for _, num in keep], draws))
    return rows


def build_tables(spec: EncoderSpec = GEN1, set_prior: bool | None = None):
    """A `pkmn_gen1.Tables` for the Rust encoder, plus its fingerprint."""
    import os

    import pkmn_gen1

    if set_prior is None:
        set_prior = not bool(os.environ.get("POKEMON_RL_NO_SET_PRIOR"))
    base, types = _species_rows(spec)
    moves = _move_rows(spec)
    chart = _type_chart(spec)
    tables = pkmn_gen1.Tables(base, types, moves, chart, _prior_rows(spec), set_prior)
    return tables, fingerprint(spec)


@lru_cache(maxsize=4)
def fingerprint(spec: EncoderSpec = GEN1) -> str:
    """sha256 over the concatenated tables -- stamped into run metadata so a run
    records exactly which data produced its observations."""
    base, types = _species_rows(spec)
    moves = _move_rows(spec)
    chart = _type_chart(spec)
    h = hashlib.sha256()
    h.update(np.asarray(base, dtype=np.int32).tobytes())
    h.update(np.asarray(types, dtype=np.int32).tobytes())
    for row in moves:
        # `ohko` is skipped on purpose: the fingerprint pins what produced the
        # OBSERVATIONS, and OHKO enters no encoder field.
        bp, acc, pp, prio, phys, stat, ty, _ohko, eff = row
        h.update(np.asarray([bp, pp, prio, ty], dtype=np.int32).tobytes())
        h.update(np.asarray([acc], dtype=np.float32).tobytes())
        h.update(bytes([phys, stat]))
        h.update(np.asarray(eff, dtype=np.float32).tobytes())
    h.update(np.asarray(chart, dtype=np.float64).tobytes())
    for sid, ids, draws in _prior_rows(spec):
        h.update(np.asarray([sid, *ids], dtype=np.int32).tobytes())
        h.update(np.asarray([len(d) for d in draws], dtype=np.int32).tobytes())
        for d in draws:
            h.update(bytes(d))
    return h.hexdigest()

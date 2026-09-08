"""The engine collector's team-bank FILE FORMAT — reader half, no engine, no
poke-env, no Showdown checkout.

Split out of `scripts/engine_team_bank.py` (which still owns generation, the
CLI and `write_bank`) so the training path can read a bank with a plain import
instead of `sys.path.insert(0, "scripts")`. The script imports these names back,
so the format has exactly one definition.

THE BANK'S UNIT IS A BATTLE, NOT A TEAM — `battleHasDitto` is a field on PS's
team GENERATOR, and PS makes one generator per Battle and calls `getTeam()`
twice (`sim/battle.ts:3171-3177`). See the script's docstring and
docs/engine_port/NOTES.md.

Format (little-endian):

    magic   b"PKB1"
    u32     header length
    JSON    {"ps_commit", "seed_prefix", "pairs", "bytes_per_mon", "sha256", ...}
    payload pairs x 2 teams x 6 mons x 8 bytes:
              species u8 | level u8 | move ids u8 x4 | flags u8 | hp_ev_div4 u8
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import struct

MAGIC = b"PKB1"
BYTES_PER_MON = 8
MONS_PER_TEAM = 6
TEAMS_PER_PAIR = 2
PAIR_BYTES = BYTES_PER_MON * MONS_PER_TEAM * TEAMS_PER_PAIR

# bit 0: the "minimize confusion damage" set (ivs.atk 2, evs.atk 0), which
# gen-1 randbats applies to every mon with no physical move.
FLAG_MIN_ATK = 1 << 0


def unpack_mon(b: bytes) -> dict:
    sid, level, m1, m2, m3, m4, flags, hp_ev4 = b
    ivs = [30, 2 if flags & FLAG_MIN_ATK else 30, 30, 30, 30]
    evs = [hp_ev4 * 4, 0 if flags & FLAG_MIN_ATK else 255, 255, 255, 255]
    return {
        "species": sid,
        "level": level,
        "moves": [m for m in (m1, m2, m3, m4) if m],
        "ivs": ivs,
        "evs": evs,
    }


def read_bank(path: pathlib.Path) -> tuple[dict, bytes]:
    """`(header, payload)`. The sha256 is verified here, so a caller that got a
    payload from this function has one the header vouches for — which is what
    `meta.yaml` records for a run."""
    with open(path, "rb") as fh:
        if fh.read(4) != MAGIC:
            raise ValueError(f"{path} is not a team bank")
        (hlen,) = struct.unpack("<I", fh.read(4))
        header = json.loads(fh.read(hlen))
        payload = fh.read()
    if hashlib.sha256(payload).hexdigest() != header["sha256"]:
        raise ValueError(f"{path}: payload sha256 does not match the header")
    if len(payload) != header["pairs"] * PAIR_BYTES:
        raise ValueError(f"{path}: payload is {len(payload)} bytes for {header['pairs']} pairs")
    return header, payload


def iter_pairs(payload: bytes):
    team_bytes = BYTES_PER_MON * MONS_PER_TEAM
    for i in range(0, len(payload), PAIR_BYTES):
        pair = payload[i : i + PAIR_BYTES]
        yield tuple(
            [
                unpack_mon(pair[t * team_bytes + j * BYTES_PER_MON :][:BYTES_PER_MON])
                for j in range(MONS_PER_TEAM)
            ]
            for t in range(TEAMS_PER_PAIR)
        )

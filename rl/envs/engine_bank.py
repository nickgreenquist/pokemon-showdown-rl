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


def open_bank(path: pathlib.Path) -> tuple[dict, memoryview]:
    """`(header, payload)` like `read_bank`, but the payload is a read-only
    memoryview over the file mmap'd ACCESS_READ: every process that opens the
    same bank shares one copy through the page cache instead of holding its
    own 0.53 GB (the 2026-09-10 max-out finding; R7 plan §9 ruling 6). The
    sha256 and the length are verified exactly as `read_bank` verifies them,
    through the page cache. Pass the view straight to `pkmn_gen1.BatchEnv`,
    which reads it in place when the extension says `bank_zero_copy`; the
    view keeps the mapping alive for as long as anything holds it."""
    import mmap

    with open(path, "rb") as fh:
        mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    view = memoryview(mm)
    if bytes(view[:4]) != MAGIC:
        raise ValueError(f"{path} is not a team bank")
    (hlen,) = struct.unpack("<I", view[4:8])
    header = json.loads(bytes(view[8 : 8 + hlen]))
    payload = view[8 + hlen :]
    if hashlib.sha256(payload).hexdigest() != header["sha256"]:
        raise ValueError(f"{path}: payload sha256 does not match the header")
    if len(payload) != header["pairs"] * PAIR_BYTES:
        raise ValueError(f"{path}: payload is {len(payload)} bytes for {header['pairs']} pairs")
    return header, payload


def load_bank_for_env(path: pathlib.Path) -> tuple[dict, bytes | memoryview, bool]:
    """The collector's reader: the mmap'd view when the installed extension
    reads a buffer in place (`build_info()["bank_zero_copy"]`), else the
    copied bytes an older build requires (an older build would extract a
    memoryview ELEMENT BY ELEMENT). Returns `(header, payload, zero_copy)` so
    the caller can stamp which it got -- a silent fallback is the landmine."""
    import pkmn_gen1

    if pkmn_gen1.build_info().get("bank_zero_copy"):
        header, payload = open_bank(path)
        return header, payload, True
    header, payload = read_bank(path)
    return header, payload, False


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

#!/usr/bin/env python
"""Builds the engine collector's team bank with Showdown itself (plan §6.2).

Borrowed: Pokémon Showdown (MIT), vendored at `showdown/` and pinned to
59da482e -- the same generator LG-5 pins for the ladder. Only `dist/sim` is
loaded by the Node side; no server is started and no socket is opened.

THE BANK'S UNIT IS A BATTLE, NOT A TEAM. `battleHasDitto` is a field on the team
GENERATOR, and PS creates one generator per Battle and calls `getTeam()` twice
(`sim/battle.ts:3171-3177`); "at most one Ditto per battle" is enforced by
SKIPPING Ditto while picking the second team. Plan §6.2 proposes storing single
teams and re-drawing the second when both contain Ditto -- that is a different
distribution (a re-draw resamples the whole team; PS resamples one slot), so the
bank stores PAIRS instead. Recorded in docs/engine_port/NOTES.md.

File format (little-endian):

    magic   b"PKB1"
    u32     header length
    JSON    {"ps_commit", "seed_prefix", "pairs", "bytes_per_mon", "sha256"}
    payload pairs x 2 teams x 6 mons x 8 bytes:
              species u8 | level u8 | move ids u8 x4 | flags u8 | hp_ev_div4 u8

`flags` bit 0 is the "minimize confusion damage" set (ivs.atk 2, evs.atk 0);
`hp_ev_div4` is floor(evs.hp / 4), which is the only form of evs.hp that enters
the stat formula, so the packing is lossless for stats.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import subprocess
import sys

from poke_env import to_id_str

import pkmn_gen1

# The format itself lives in rl/envs/engine_bank.py so the training path can
# read a bank without importing from scripts/; re-exported here because every
# existing caller of this module expects these names.
from rl.envs.engine_bank import (  # noqa: F401
    BYTES_PER_MON,
    FLAG_MIN_ATK,
    MAGIC,
    MONS_PER_TEAM,
    PAIR_BYTES,
    TEAMS_PER_PAIR,
    iter_pairs,
    read_bank,
    unpack_mon,
)

SPECIES_ID = {to_id_str(n): i for i, n in enumerate(pkmn_gen1.species_names()) if i}
MOVE_ID = {to_id_str(n): i for i, n in enumerate(pkmn_gen1.move_names()) if i}

def pack_mon(mon: dict) -> bytes:
    sid = SPECIES_ID[to_id_str(mon["s"])]
    moves = [MOVE_ID[to_id_str(m)] for m in mon["m"][:4]]
    moves += [0] * (4 - len(moves))
    flags = FLAG_MIN_ATK if (mon["ia"] == 2 and mon["ea"] == 0) else 0
    return bytes([sid, mon["l"], *moves, flags, mon["eh"] // 4])



def generate(showdown_root: pathlib.Path, pairs: int, seed_prefix: str) -> bytes:
    here = pathlib.Path(__file__).resolve().parent
    # STREAM the generator's stdout, never capture_output. A pair is ~1.4 kB of
    # JSON, so buffering the whole run would hold ~1.4 GB at 1,000,000 pairs and
    # ~7 GB at 5,000,000 — enough to OOM this box, and A-1 mandates a bank of at
    # least 1,000,000 (review 2, M4). The packed payload is 96 B/pair, so the
    # bytearray below is 96 MB and 480 MB respectively, which is the real cost.
    proc = subprocess.Popen(
        [
            "node",
            str(here / "engine_team_bank.js"),
            str(showdown_root),
            str(pairs),
            seed_prefix,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=str(showdown_root),
    )
    payload = bytearray()
    n = 0
    assert proc.stdout is not None
    for line in proc.stdout:
        if not line.strip():
            continue
        p1, p2 = json.loads(line)
        for team in (p1, p2):
            if len(team) != MONS_PER_TEAM:
                raise RuntimeError(f"a team has {len(team)} mons, expected 6")
            for mon in team:
                payload += pack_mon(mon)
        n += 1
    proc.stdout.close()
    rc = proc.wait()
    err = (proc.stderr.read() if proc.stderr else "")[-4000:]
    if rc != 0:
        raise RuntimeError(f"team generator failed (rc {rc}):\n{err}")
    if n != pairs:
        raise RuntimeError(f"generator produced {n} pairs, asked for {pairs}")
    return bytes(payload)


def write_bank(path: pathlib.Path, payload: bytes, ps_commit: str, seed_prefix: str) -> dict:
    pairs = len(payload) // PAIR_BYTES
    header = {
        "ps_commit": ps_commit,
        "seed_prefix": seed_prefix,
        "pairs": pairs,
        "bytes_per_mon": BYTES_PER_MON,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "engine_sha": pkmn_gen1.build_info()["engine_sha"],
    }
    blob = json.dumps(header, sort_keys=True).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(MAGIC)
        fh.write(struct.pack("<I", len(blob)))
        fh.write(blob)
        fh.write(payload)
    return header




def ps_commit(showdown_root: pathlib.Path) -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(showdown_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--showdown-root",
        default="/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown",
        help="the vendored PS checkout (READ ONLY -- only dist/sim is loaded)",
    )
    ap.add_argument("--pairs", type=int, default=50_000)
    ap.add_argument("--seed-prefix", default="e0e0")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    root = pathlib.Path(args.showdown_root)
    commit = ps_commit(root)
    payload = generate(root, args.pairs, args.seed_prefix)
    out = pathlib.Path(
        args.out or f"data/engine/teams_{commit[:8]}_{args.seed_prefix}_{args.pairs}.bin"
    )
    header = write_bank(out, payload, commit, args.seed_prefix)
    print(f"wrote {out} ({len(payload) + 8:,} bytes)")
    print(json.dumps(header, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

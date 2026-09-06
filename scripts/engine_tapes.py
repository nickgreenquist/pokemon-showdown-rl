"""Shared tape access for the engine-port gates.

The Foul-Play collection tapes are raw Showdown protocol plus `|request|` JSON,
one JSON event per line. They are gitignored, so a worktree does not have them:
`--tapes-root` (default: the main checkout) points at whichever tree does.

Borrowed shape: the replay follows `tests/test_encoder_ids_tapes.py`, which is
the harness plan §9 names for P-1.
"""

from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Iterator

# The 6-lane P4 corpus plus the three hl-shaping tapes -- the same list
# tests/test_encoder_ids_tapes.py replays.
TAPE_NAMES = [
    "data/fp_tapes2/run_92564.jsonl",
    "data/fp_tapes/run_90336.jsonl",
    "data/fp_tapes3/run_98827.jsonl",
    "data/fp_tapes_all/run_4106.jsonl",
    "data/fp_tapes_all/run_4115.jsonl",
    "data/fp_tapes_all/run_4121.jsonl",
    "data/fp_tapes_all/run_13185.jsonl",
    "data/fp_tapes_all/run_13353.jsonl",
    "data/fp_tapes_all/run_13445.jsonl",
]

DEFAULT_ROOT = pathlib.Path(
    os.environ.get("POKEMON_RL_TAPES_ROOT", "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
)


def tape_paths(root: pathlib.Path | None = None) -> list[pathlib.Path]:
    root = root or DEFAULT_ROOT
    return [p for p in (root / n for n in TAPE_NAMES) if p.exists()]


def iter_events(path: pathlib.Path) -> Iterator[dict]:
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def infer_username(path: pathlib.Path) -> str | None:
    """The account whose seat these tapes record -- poke-env needs it to know
    which side is 'ours'."""
    for ev in iter_events(path):
        if ev.get("k") != "m":
            continue
        for line in ev["v"].split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    return None


def iter_room_messages(path: pathlib.Path) -> Iterator[tuple[str, str]]:
    """`(room, raw message)` for every battle-room protocol message on a tape."""
    for ev in iter_events(path):
        if ev.get("k") != "m":
            continue
        head = ev["v"].split("\n", 1)[0]
        if not head.startswith(">battle-"):
            continue
        yield head[1:], ev["v"]


def parse_details(details: str) -> tuple[str, int]:
    """`"Butterfree, L77, M"` -> `("Butterfree", 77)`. No `L` means level 100."""
    parts = [p.strip() for p in details.split(",")]
    species = parts[0]
    level = 100
    for p in parts[1:]:
        if p.startswith("L") and p[1:].isdigit():
            level = int(p[1:])
    return species, level


def parse_condition(condition: str) -> tuple[int | None, int | None]:
    """`"251/251"` -> `(251, 251)`; `"0 fnt"` -> `(0, None)`."""
    head = condition.split(" ")[0]
    if "/" not in head:
        return (0 if head == "0" else None), None
    cur, mx = head.split("/", 1)
    return int(cur), int(mx)

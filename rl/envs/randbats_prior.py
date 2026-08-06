"""Opponent set prior for gen1randombattle — what the encoder was throwing away.

THE PROBLEM THIS SOLVES
-----------------------
`embed_battle` shows the opponent's moves only once REVEALED. Foul Play — the
teacher we are distilling — does the opposite: it samples full opponent sets
from the randbats pool weighted by consistency with what has been revealed, and
even fills the unrevealed slots. Every decision it makes is an expectation over
near-complete opponent teams.

So behavioural cloning on those demonstrations regresses `E[teacher action |
our obs]` against a teacher whose principal input we deleted. That residual is
IRREDUCIBLE: more demonstrations reduce variance, not bias. It is the most
likely reason the measured BC-on-SH learning curve
(runs/bc_p4_*/bc_metrics.json: 0.8595 -> 0.8814 -> 0.9017 across doublings,
+2.1 pts/doubling, no saturation) never reaches a deterministic bot's policy.

Gen 1 random battles are the format where this is most recoverable: the set
pool is small, public, and vendored. 146 species; ~40 have exactly one possible
set, so their entire moveset is known the instant the species appears.

FAITHFULNESS
------------
The marginals are NOT a heuristic. `_sample_set` reproduces Showdown's own
`randomSet` move selection from `data/random-battles/gen1/teams.ts` step for
step, including the details that a heuristic would get wrong:

  1. comboMoves are added ALL-or-NONE, and only on a 50% coin flip;
  2. exactly ONE exclusiveMove is sampled, and it is added BEFORE the
     essentials specifically so a three-move combo can still roll one;
  3. essentialMoves are added in order and stop at the 4-move cap;
  4. the remainder is sampleNoReplace from `moves`.

Conditioning is by rejection over the sampled sets, which is exactly Foul
Play's determinization logic: keep the sets consistent with everything revealed
so far, then take per-move marginals over those.

PROVENANCE
----------
`data/gen1_randbats_sets.json` is a byte copy of
`showdown/data/random-battles/gen1/data.json` (24,970 bytes, sha256
85fc2743d9dba5a0dc996f8991be5ec0...). The `showdown/` tree is gitignored and
re-clonable, so the copy lives here to keep the offline encoder reproducible.
`verify_against_showdown()` re-checks the copy against the live tree.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

import numpy as np

MAX_MOVES = 4
_N_SAMPLES = 4000  # marginals to ~+/-0.008; the encoder rounds far coarser
_DATA = Path(__file__).with_name("data") / "gen1_randbats_sets.json"


@lru_cache(maxsize=1)
def _sets() -> dict:
    with _DATA.open() as fh:
        return json.load(fh)


def known_species() -> set:
    return set(_sets())


def _sample_set(entry: dict, rng: random.Random) -> frozenset:
    """One draw from Showdown's gen1 randomSet move selection (teams.ts)."""
    move_pool = list(entry.get("moves", []))
    moves: set[str] = set()

    combo = entry.get("comboMoves")
    if combo and len(combo) <= MAX_MOVES and rng.random() < 0.5:
        moves.update(combo)

    exclusive = entry.get("exclusiveMoves")
    if len(moves) < MAX_MOVES and exclusive:
        moves.add(rng.choice(exclusive))

    essential = entry.get("essentialMoves")
    if len(moves) < MAX_MOVES and essential:
        for mid in essential:
            moves.add(mid)
            if len(moves) == MAX_MOVES:
                break

    pool = move_pool[:]
    while len(moves) < MAX_MOVES and pool:
        moves.add(pool.pop(rng.randrange(len(pool))))

    return frozenset(moves)


@lru_cache(maxsize=256)
def _samples(species: str):
    """(move_ids, boolean sample matrix) for a species, computed once."""
    entry = _sets().get(species)
    if entry is None:
        return (), np.zeros((0, 0), dtype=bool)
    rng = random.Random(0xC0FFEE)  # deterministic: the encoder must be pure
    draws = [_sample_set(entry, rng) for _ in range(_N_SAMPLES)]
    ids = sorted({m for d in draws for m in d})
    idx = {m: i for i, m in enumerate(ids)}
    mat = np.zeros((len(draws), len(ids)), dtype=bool)
    for r, d in enumerate(draws):
        for m in d:
            mat[r, idx[m]] = True
    return tuple(ids), mat


@lru_cache(maxsize=8192)
def conditional_move_probs(species: str, revealed: frozenset) -> list[tuple[str, float]]:
    """P(move in set | revealed subset), for the moves NOT yet revealed.

    Returned high-probability first. Rejection over the sampled sets; if the
    revealed moves are inconsistent with every sample (a pool drift, a Mimic or
    a Transform copying moves the species cannot have) we fall back to the
    unconditional marginals rather than emitting nothing.
    """
    ids, mat = _samples(species)
    if not ids:
        return []
    keep = np.ones(mat.shape[0], dtype=bool)
    for mv in revealed:
        if mv in ids:
            keep &= mat[:, ids.index(mv)]
    if not keep.any():
        keep = np.ones(mat.shape[0], dtype=bool)
    probs = mat[keep].mean(axis=0)
    out = [
        (mid, float(p))
        for mid, p in zip(ids, probs)
        if mid not in revealed and p > 0.0
    ]
    out.sort(key=lambda kv: -kv[1])
    return out


def species_level(species: str):
    entry = _sets().get(species)
    return entry.get("level") if entry else None


def verify_against_showdown(showdown_root: Path = Path("showdown")) -> tuple[bool, str]:
    """Re-check the vendored copy against the live Showdown tree.

    Worth running after any re-clone: Foul Play fetches sets at runtime from
    pkmn.github.io and `showdown/` updates independently, so drift would make
    the teacher search different movesets from the ones we encode, silently.
    """
    live = showdown_root / "data" / "random-battles" / "gen1" / "data.json"
    if not live.exists():
        return False, f"live set file not found at {live}"
    if json.loads(live.read_text()) == _sets():
        return True, "vendored set pool matches showdown/"
    return False, "VENDORED SET POOL DIFFERS from showdown/ — re-vendor before encoding"

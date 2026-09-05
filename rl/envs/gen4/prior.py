"""Opponent set prior for gen4randombattle — exact, not ported.

gen 1's standard (rl/envs/randbats_prior.py): "the marginals are NOT a
heuristic" — a step-for-step port of Showdown's gen-1 `randomSet`. The gen-4
generator is a different animal (a curated role table drawn through
`randomMoveset` with move pairs, per-team counters, weather-gated abilities
and a 40-item rule table; showdown/data/random-battles/gen4/teams.ts), so a
port would be large and fragile. Instead the prior IS the generator's output:
scripts/gen4_sample_generator.js runs the vendored `Teams.getGenerator(
'gen4randombattle')` 100,000 times (600,000 sets, fixed seed, Showdown commit
stamped) and records every realised (4 moves, ability, item) triple per
species with its count — data/gen4_set_samples.json. The realised set space
is small: 1,743 distinct triples over 296 species (median 4 per species, max
41), 13 singletons in 600,000 draws, i.e. Good-Turing unseen mass ~0.

Conditioning is rejection over the realised sets, exactly Foul Play's
determinization logic and gen 1's: keep the triples consistent with what has
been revealed (moves ⊆ set, ability, item), take marginals over those. This
integrates over everything the generator conditions on (team weather for
Chlorophyll / Swift Swim, the move-driven item rules, Trick sets) because
the samples were drawn from whole teams.

Deviation from gen 1, disclosed: counts are Monte-Carlo (~2,000 draws per
species, marginals to about +/-0.02), not analytic; a re-run with a different
seed moves a probability by that much and no more.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from rl.envs.gen4.vocab import VOCAB, to_id

DATA = Path(__file__).with_name("data") / "gen4_set_samples.json"
# poke-env's id for an OPPONENT's revealed Hidden Power: Showdown never names
# the type (`|move|p2a: X|Hidden Power`), so the stored id is untyped and
# matches no set row (every row carries `hiddenpowerfire`, ...). Resolved by
# `hidden_power_variant` before any conditioning; own mons carry typed ids.
HIDDEN_POWER = "hiddenpower"

# (moves, ability, item, count)
SetSample = tuple[frozenset[str], str, str, int]


@lru_cache(maxsize=1)
def _raw() -> dict:
    with DATA.open() as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _sets() -> dict[str, tuple[SetSample, ...]]:
    out = {}
    for species, table in _raw()["set_samples"].items():
        rows = []
        for key, count in table.items():
            moves, ability, item = key.split("|")
            rows.append((frozenset(moves.split(",")), ability, item, int(count)))
        out[species] = tuple(rows)
    return out


@lru_cache(maxsize=1)
def known_species() -> frozenset:
    return frozenset(_sets())


def stamp() -> dict:
    r = _raw()
    return {k: r[k] for k in ("showdown_commit", "seed", "n_teams", "n_sets")}


def _consistent(
    species: str, revealed: frozenset, ability: str | None, item: str | None
) -> list[SetSample]:
    rows = _sets().get(species, ())
    keep = [
        r for r in rows
        if revealed <= r[0]
        and (ability is None or r[1] == ability)
        and (item is None or r[2] == item)
    ]
    if keep:
        return keep
    # Inconsistent evidence (pool drift, Transform, a Sleep Talk-called move
    # mis-attributed): degrade to the unconditional table rather than emit
    # nothing — gen 1's rule, and Wang's determinizer's (wang_showdown_fork.md).
    return list(rows)


@lru_cache(maxsize=16384)
def conditional_move_probs(
    species: str, revealed: frozenset, ability: str | None = None, item: str | None = None
) -> list[tuple[str, float]]:
    """P(move in set | revealed moves, known ability, known item) for the moves
    NOT yet revealed, high-probability first. Empty for an unknown species."""
    rows = _consistent(species, revealed, ability, item)
    if not rows:
        return []
    total = sum(r[3] for r in rows)
    acc: dict[str, int] = {}
    for moves, _, _, count in rows:
        for m in moves:
            if m not in revealed:
                acc[m] = acc.get(m, 0) + count
    out = [(m, c / total) for m, c in acc.items()]
    out.sort(key=lambda kv: (-kv[1], kv[0]))
    return out


@lru_cache(maxsize=16384)
def ability_probs(
    species: str, revealed: frozenset = frozenset(), item: str | None = None
) -> dict[str, float]:
    """P(ability | revealed moves, known item). Empty for an unknown species."""
    rows = _consistent(species, revealed, None, item)
    if not rows:
        return {}
    total = sum(r[3] for r in rows)
    acc: dict[str, int] = {}
    for _, ability, _, count in rows:
        acc[ability] = acc.get(ability, 0) + count
    return {a: c / total for a, c in acc.items()}


@lru_cache(maxsize=16384)
def item_probs(
    species: str, revealed: frozenset = frozenset(), ability: str | None = None
) -> dict[str, float]:
    """P(item | revealed moves, known ability). Empty for an unknown species."""
    rows = _consistent(species, revealed, ability, None)
    if not rows:
        return {}
    total = sum(r[3] for r in rows)
    acc: dict[str, int] = {}
    for _, _, item, count in rows:
        acc[item] = acc.get(item, 0) + count
    return {it: c / total for it, c in acc.items()}


@lru_cache(maxsize=16384)
def hidden_power_variant(
    species: str, revealed: frozenset = frozenset(), ability: str | None = None, item: str | None = None
) -> str | None:
    """The typed Hidden Power id the realised sets favour for a mon that has
    shown an untyped `hiddenpower`: the most-counted `hiddenpower*` over the
    rows consistent with the OTHER revealed moves, the known ability and item
    (ties broken alphabetically). None when no consistent row carries one.
    Without this every prior read for such a mon fell back to the
    unconditional table — 5.6 % of opponent-mon observations on t1+t2
    (2026-09-05 review)."""
    rows = _consistent(species, revealed - {HIDDEN_POWER}, ability, item)
    acc: dict[str, int] = {}
    for moves, _, _, count in rows:
        for m in moves:
            if m.startswith(HIDDEN_POWER):
                acc[m] = acc.get(m, 0) + count
    if not acc:
        return None
    return max(sorted(acc), key=acc.__getitem__)


def species_level(species: str) -> int | None:
    return VOCAB.levels.get(to_id(species))


def verify_against_vocab() -> tuple[bool, str]:
    """Every sampled move / ability / item is a vocab row, and the stamps agree."""
    r = _raw()
    if r["showdown_commit"] != VOCAB.showdown_commit:
        return False, f"set samples at {r['showdown_commit'][:8]}, vocab at {VOCAB.showdown_commit[:8]}"
    bad = []
    for species, rows in _sets().items():
        if VOCAB.species_id(species) == 0:
            bad.append(f"species {species}")
        for moves, ability, item, _ in rows:
            bad.extend(f"move {m}" for m in moves if VOCAB.move_id(m) == 0)
            if VOCAB.ability_id(ability) == 0:
                bad.append(f"ability {ability}")
            if item != "(none)" and VOCAB.item_id(item) == 0:
                bad.append(f"item {item}")
    if bad:
        return False, "sampled ids outside the vocab: " + ", ".join(sorted(set(bad))[:10])
    return True, f"{len(_sets())} species, {sum(len(v) for v in _sets().values())} realised sets, stamps agree"

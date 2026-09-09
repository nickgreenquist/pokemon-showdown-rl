"""Gate P-3: the team bank is wired to Showdown's generator, not to a guess.

Checked (plan §9): the bank header (PS commit, payload sha256); the four
per-team constraints plus Species Clause on 100k teams; "at most one Ditto per
BATTLE" on the pairs; every species and level against
`rl/envs/randbats_prior.py`; the per-species MOVE-SET marginals against that
same prior by chi-square -- which is the interesting one, because the prior is a
Python re-implementation of `randomSet` that the ENCODER reads at inference time
and the bank is what Showdown actually produced.

Failure mode this gate exists for: a generator wiring bug.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from poke_env import to_id_str
from poke_env.battle.pokemon_type import PokemonType
from poke_env.data import GenData

import pkmn_gen1
from rl.envs import randbats_prior

GEN1 = GenData.from_gen(1)
TYPE_CHART = GEN1.type_chart

ENGINE_SPECIES = pkmn_gen1.species_names()
ENGINE_MOVES = pkmn_gen1.move_names()

# `teams.ts:157`: "Spammable attacks are: Thunderbolt, Psychic, Surf, Blizzard,
# Earthquake, Fire Blast."
SPAMMABLE = ["Electric", "Psychic", "Water", "Ice", "Ground", "Fire"]


def _types(species_name: str) -> list[str]:
    return GEN1.pokedex[to_id_str(species_name)]["types"]


def _is_weak_to(species_name: str, attacking: str) -> bool:
    """PS: `getImmunity(t, species) && getEffectiveness(t, species) > 0`."""
    ts = [PokemonType.from_name(t) for t in _types(species_name)]
    mult = PokemonType.from_name(attacking).damage_multiplier(
        ts[0], ts[1] if len(ts) > 1 else None, type_chart=TYPE_CHART
    )
    return mult > 1


def check_team(team, report: Counter, failures: list, tag: str) -> None:
    if len(team) != 6:
        failures.append(f"{tag}: team has {len(team)} mons")
        return
    names = [ENGINE_SPECIES[m["species"]] for m in team]

    if len(set(names)) != 6:
        failures.append(f"{tag}: Species Clause violated: {names}")

    type_count: Counter = Counter()
    weak_count: Counter = Counter()
    max_level = 0
    for mon, name in zip(team, names):
        for t in _types(name):
            type_count[t] += 1
        for t in SPAMMABLE:
            if _is_weak_to(name, t):
                weak_count[t] += 1
        if mon["level"] == 100:
            max_level += 1

        if to_id_str(name) not in randbats_prior.known_species():
            failures.append(f"{tag}: {name} has no randbats set")
        want_level = randbats_prior.species_level(to_id_str(name))
        if want_level is not None and mon["level"] != want_level:
            failures.append(f"{tag}: {name} level {mon['level']} != prior {want_level}")
        if not mon["moves"]:
            failures.append(f"{tag}: {name} has no moves")

    for t, c in type_count.items():
        if c > 2:
            failures.append(f"{tag}: {c} mons share type {t}: {names}")
    for t, c in weak_count.items():
        if c > 2:
            failures.append(f"{tag}: {c} mons weak to {t}: {names}")
    if max_level > 1:
        failures.append(f"{tag}: {max_level} level-100 mons: {names}")

    report["teams"] += 1


def chi_square_two_sample(a: Counter, b: Counter) -> tuple[float, int]:
    """Chi-square for two independent multinomial samples over the same support.

    Cells with a pooled expectation under 5 are dropped (the usual rule); the
    returned dof counts the cells actually used.
    """
    keys = sorted(set(a) | set(b))
    na, nb = sum(a.values()), sum(b.values())
    if not na or not nb:
        return 0.0, 0
    stat = 0.0
    used = 0
    for k in keys:
        oa, ob = a.get(k, 0), b.get(k, 0)
        tot = oa + ob
        ea, eb = tot * na / (na + nb), tot * nb / (na + nb)
        if min(ea, eb) < 5:
            continue
        stat += (oa - ea) ** 2 / ea + (ob - eb) ** 2 / eb
        used += 1
    return stat, max(used - 1, 0)


def chi_square_sf(stat: float, dof: int) -> float:
    """Upper tail of the chi-square distribution. Wilson-Hilferty for dof >= 1;
    good to ~1e-3 in the tail, which is all a sanity gate needs."""
    if dof <= 0:
        return 1.0
    x = stat / dof
    z = (x ** (1.0 / 3.0) - (1.0 - 2.0 / (9.0 * dof))) / math.sqrt(2.0 / (9.0 * dof))
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def move_marginals(bank_sets: dict[str, list[frozenset]]) -> dict:
    """Per (species, move): bank presence rate vs the prior's own presence rate.

    The prior (`randbats_prior._samples`) is a Python re-implementation of PS's
    `randomSet`, drawn 4,000 times per species with a fixed seed; the bank is
    what PS itself produced. Both are finite samples, so the statistic is a
    two-sample z on the presence rate:

        z = (p_bank - p_prior) / sqrt(p_pooled (1 - p_pooled) (1/n_b + 1/n_p))

    Reported per cell, then summarised by max |z| and by how many cells exceed a
    BONFERRONI-corrected two-sided 0.05 threshold over all cells. A per-species
    chi-square is deliberately NOT used: the four move slots of one set are
    dependent (exactly four are drawn), so summing per-move 2x2 tables would
    have the wrong degrees of freedom and a meaningless p-value.
    """
    cells = []
    deterministic = 0
    unknown: dict[str, list[str]] = {}
    for sid, draws in sorted(bank_sets.items()):
        prior_ids, mat = randbats_prior._samples(sid)
        if not prior_ids or not draws:
            continue
        n_bank, n_prior = len(draws), mat.shape[0]
        observed: Counter = Counter()
        for d in draws:
            for m in d:
                observed[m] += 1
        extra = sorted(set(observed) - set(prior_ids))
        if extra:
            unknown[sid] = extra
        for i, m in enumerate(prior_ids):
            ob = observed.get(m, 0)
            op = int(mat[:, i].sum())
            p = (ob + op) / (n_bank + n_prior)
            if p <= 0.0 or p >= 1.0:
                # Always present (or always absent) in BOTH -- no variance, so no
                # z to compute. A disagreement here would be a hard failure, so
                # check it directly and count the agreements rather than hiding
                # them: most species have a fully deterministic 4-move set.
                if (ob > 0) != (op > 0):
                    cells.append((sid, m, ob / n_bank, op / n_prior, float("inf")))
                else:
                    deterministic += 1
                continue
            se = math.sqrt(p * (1 - p) * (1 / n_bank + 1 / n_prior))
            z = (ob / n_bank - op / n_prior) / se if se > 0 else 0.0
            cells.append((sid, m, ob / n_bank, op / n_prior, z))

    n_cells = len(cells)
    # Bonferroni two-sided 0.05 over n_cells: |z| > Phi^-1(1 - 0.025/n_cells).
    thresh = _normal_quantile(1 - 0.025 / max(n_cells, 1)) if n_cells else 0.0
    worst = sorted(cells, key=lambda c: -abs(c[4]))[:10]
    return {
        "cells": n_cells,
        "deterministic_cells_agreeing": deterministic,
        "species": len({c[0] for c in cells}),
        "max_abs_z": max((abs(c[4]) for c in cells), default=0.0),
        "bonferroni_threshold": thresh,
        "cells_over_threshold": sum(1 for c in cells if abs(c[4]) > thresh),
        "worst": [
            {"species": s_, "move": m_, "p_bank": pb, "p_prior": pp, "z": z_}
            for s_, m_, pb, pp, z_ in worst
        ],
        "moves_in_bank_not_in_prior": unknown,
    }


def _normal_quantile(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if not 0.0 < p < 1.0:
        return float("inf")
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def analyse(payload_pairs, report: Counter, failures: list) -> dict:
    """One pass over the bank."""
    # Split by PAIR PARITY, not by team-within-pair: the Ditto rule makes the
    # second team of a pair a different distribution from the first (by design),
    # so first-vs-second would flag a feature as a bug. Even-vs-odd pairs are
    # independent draws from the same distribution.
    species_even: Counter = Counter()
    species_odd: Counter = Counter()
    ditto_first = ditto_second = 0
    bank_sets: dict[str, list[frozenset]] = defaultdict(list)
    levels: dict[str, set] = defaultdict(set)

    for i, (t1, t2) in enumerate(payload_pairs):
        check_team(t1, report, failures, f"pair{i}/team0")
        check_team(t2, report, failures, f"pair{i}/team1")

        dittos = sum(
            1 for m in list(t1) + list(t2) if ENGINE_SPECIES[m["species"]] == "Ditto"
        )
        report["pairs"] += 1
        if dittos:
            report["pairs_with_ditto"] += 1
        if dittos > 1:
            report["pairs_with_two_dittos"] += 1
            failures.append(f"pair{i}: {dittos} Dittos in one battle")

        if any(ENGINE_SPECIES[m["species"]] == "Ditto" for m in t1):
            ditto_first += 1
        if any(ENGINE_SPECIES[m["species"]] == "Ditto" for m in t2):
            ditto_second += 1

        bucket = species_even if i % 2 == 0 else species_odd
        for team in (t1, t2):
            for mon in team:
                name = ENGINE_SPECIES[mon["species"]]
                sid = to_id_str(name)
                bucket[sid] += 1
                levels[sid].add(mon["level"])
                bank_sets[sid].append(
                    frozenset(to_id_str(ENGINE_MOVES[m]) for m in mon["moves"])
                )
                report["mons"] += 1

    stat, dof = chi_square_two_sample(species_even, species_odd)
    return {
        "species_halves_chi2": stat,
        "species_halves_dof": dof,
        "species_halves_p": chi_square_sf(stat, dof),
        "distinct_species": len(species_even | species_odd),
        "ditto_teams_first": ditto_first,
        "ditto_teams_second": ditto_second,
        "levels_multi_valued": {k: sorted(v) for k, v in levels.items() if len(v) > 1},
        "move_marginals": move_marginals(bank_sets),
    }


def round_trip_battles(pairs, n: int, seed: int) -> dict:
    """Bank bytes -> engine records -> a battle that actually runs.

    P-3 is about the bank being wired correctly, and "the packed bytes rebuild
    into a Pokemon the engine accepts" is part of that. Uses the Python-facing
    `pkmn_gen1.Battle`, so it exercises that surface too.
    """
    from itertools import islice

    outcomes: Counter = Counter()
    turns = 0
    rng = seed
    for i, (t1, t2) in enumerate(islice(pairs, n)):
        recs = [
            [
                pkmn_gen1.pokemon_record(m["species"], m["level"], m["moves"], m["ivs"], m["evs"])
                for m in team
            ]
            for team in (t1, t2)
        ]
        b = pkmn_gen1.Battle(seed ^ (i * 0x9E3779B97F4A7C15) & ((1 << 64) - 1), recs[0], recs[1])
        outcome, r1, r2 = b.update("pass", ("pass", 0), "pass", ("pass", 0))
        updates = 0
        while outcome == "none":
            picks = []
            for who, req in (("p1", r1), ("p2", r2)):
                cs = b.choices(who, req)
                assert cs, f"empty choice list for {who} under {req}"
                rng = (rng * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
                picks.append(cs[(rng >> 33) % len(cs)])
            outcome, r1, r2 = b.update(r1, picks[0], r2, picks[1])
            updates += 1
            assert updates < 8000, "battle did not terminate"
        outcomes[outcome] += 1
        turns += b.turn()
    total = sum(outcomes.values())
    return {
        "battles": total,
        "win": outcomes["win"],
        "lose": outcomes["lose"],
        "tie": outcomes["tie"],
        "mean_turns": turns / total if total else 0.0,
    }

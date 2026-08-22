"""RSD — rejection-sampled set determinization over the vendored pool.

Chapter-3 R1 (ch3_search_design_r2.md §3). Samples ONE consistent opponent
team from the public randbats generator statistics (`rl/envs/randbats_prior`,
byte-verified against the vendored data.json). NOT belief-state learning:
nothing here is fitted or trained (D19 dead; the maintainer's ruling 3
ALLOWS this use, disclosed).

Determinization law (per the ratified design):
- ACTIVE opponent: the moveset IS the four encoder slots
  (`_opponent_move_slots`' revealed-then-most-probable fill) — deterministic
  by construction, which satisfies MF-5b's containment constraint exactly
  (L6 classes 0-3 always name a real determinized move).
- REVEALED bench mons: revealed moves exact; unrevealed slots completed by
  sampling the species' own set distribution conditioned on the revealed
  moves (rejection via `randbats_prior._sample_set` draws).
- UNREVEALED bench slots: species sampled uniformly from the pool minus the
  species already seen, REJECTED if adding them would break the vendored
  generator's team caps (showdown/data/random-battles/gen1/teams.ts,
  limitFactor 1): at most 2 mons per type; at most 2 mons weak (net
  supereffective, no immunity) to each spammable type {Electric, Psychic,
  Water, Ice, Ground, Fire}; at most 1 level-100 mon; one Ditto per BATTLE
  (so ditto is excluded whenever our own team carries it — public
  knowledge). Caps are evaluated against the full determinized team
  (revealed + already-sampled), a final-team approximation of the
  generator's sequential counters; the generator's rejected-pool refill
  (only reachable when the pool exhausts — never at 146 species for 6
  slots) is not modelled. FG-7's support gate (>= 0.99) is the arbiter.
- All randomness from the caller-supplied numpy Generator (key-derived per
  decision — determinism clause D2); the global `random` module is never
  touched (username landmine).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from rl.envs import randbats_prior


def _complete_revealed(species: str, revealed: frozenset, rng: np.random.Generator) -> list[str]:
    """Revealed moves exact + sampled completion consistent with them."""
    probs = randbats_prior.conditional_move_probs(species, revealed)
    known = [m for m in revealed]
    pool = [(m, p) for m, p in probs if m not in revealed and p > 0]
    need = max(0, randbats_prior.MAX_MOVES - len(known))
    picks: list[str] = []
    # sample without replacement, probability-proportional per draw
    cand = dict(pool)
    for _ in range(min(need, len(cand))):
        moves, ps = zip(*cand.items())
        ps = np.array(ps, dtype=np.float64)
        ps = ps / ps.sum()
        m = str(rng.choice(moves, p=ps))
        picks.append(m)
        del cand[m]
    return known + picks


def _static_base_stats(species: str) -> dict:
    """Base stats + types for an unrevealed species, from poke-env's static
    gen-1 pokedex (public data, same source the encoder uses)."""
    from poke_env.data import GenData

    entry = GenData.from_gen(1).pokedex[species]
    return dict(entry["baseStats"]) | {
        "types": [t.lower() for t in entry["types"]]
    }


# The generator's "spammable attack" weakness set (teams.ts, verbatim).
_SPAMMABLE_TYPES = ("electric", "psychic", "water", "ice", "ground", "fire")


@lru_cache(maxsize=256)
def _species_caps(species: str) -> tuple[frozenset, frozenset, int]:
    """(types, spammable weaknesses, level) for the generator's team caps.
    Weak = net-supereffective with no immunity — damage_multiplier > 1
    reproduces PS's getImmunity && getEffectiveness > 0 exactly."""
    from poke_env.battle.pokemon_type import PokemonType
    from poke_env.data import GenData

    gen1 = GenData.from_gen(1)
    entry = gen1.pokedex[species]
    t1 = PokemonType.from_name(entry["types"][0])
    t2 = (
        PokemonType.from_name(entry["types"][1])
        if len(entry["types"]) > 1 else None
    )
    weak = frozenset(
        name for name in _SPAMMABLE_TYPES
        if PokemonType.from_name(name).damage_multiplier(
            t1, t2, type_chart=gen1.type_chart
        ) > 1.0
    )
    level = randbats_prior.species_level(species) or 100
    return frozenset(t.lower() for t in entry["types"]), weak, level


class _TeamCaps:
    """The generator's running team counters (limitFactor 1): <=2 per type,
    <=2 weak per spammable type, <=1 level-100."""

    def __init__(self) -> None:
        self.type_count: dict[str, int] = {}
        self.weak_count: dict[str, int] = dict.fromkeys(_SPAMMABLE_TYPES, 0)
        self.max_level = 0

    def admit(self, species: str, count: bool = True) -> bool:
        types, weak, level = _species_caps(species)
        ok = (
            all(self.type_count.get(t, 0) < 2 for t in types)
            and all(self.weak_count[w] < 2 for w in weak)
            and (level < 100 or self.max_level < 1)
        )
        if count:  # revealed mons count unconditionally — they ARE on the team
            for t in types:
                self.type_count[t] = self.type_count.get(t, 0) + 1
            for w in weak:
                self.weak_count[w] += 1
            if level == 100:
                self.max_level += 1
        return ok


def sample_determinization(battle: Any, rng: np.random.Generator) -> dict:
    """One consistent opponent team for `battle1`'s current information set."""
    opponents: dict[str, dict] = {}
    seen = set()
    for species, mon in battle.opponent_team.items():
        sp = mon.species
        seen.add(sp)
        if mon is battle.opponent_active_pokemon:
            # the encoder's four slots, deterministic (MF-5b containment).
            # _opponent_move_slots yields (move_id, prob) pairs.
            from rl.envs.showdown import _opponent_move_slots

            move_ids = [
                (m.id if hasattr(m, "id") else str(m))
                for m, _p in _opponent_move_slots(mon)
                if m
            ]
        else:
            move_ids = _complete_revealed(
                sp, frozenset(mon.moves.keys()), rng
            )
        opponents[sp] = {
            "moves": move_ids,
            "level": mon.level or randbats_prior.species_level(sp),
            "base_stats": dict(mon.base_stats) | {
                "types": [t.name.lower() for t in mon.types if t is not None]
            },
            "live": mon,
            "provenance": "rsd",  # FG-4: asserted at bridge construction
        }
    n_unrevealed = 6 - len(opponents)
    caps = _TeamCaps()
    for sp in opponents:
        caps.admit(sp)  # revealed mons seed the counters unconditionally
    pool = sorted(randbats_prior.known_species() - seen)
    # One Ditto per battle (teams.ts battleHasDitto): our own team is public,
    # so a Ditto on OUR side excludes it from the opponent's unrevealed pool.
    if any(m.species == "ditto" for m in battle.team.values()):
        pool = [sp for sp in pool if sp != "ditto"]
    for _ in range(max(0, n_unrevealed)):
        while pool:
            sp = str(rng.choice(pool))
            pool.remove(sp)
            if caps.admit(sp, count=False):
                caps.admit(sp)
                break
        else:  # generator's rejected-pool refill; unreachable at 146 species
            break
        opponents[sp] = {
            "moves": _complete_revealed(sp, frozenset(), rng),
            "level": randbats_prior.species_level(sp),
            "base_stats": _static_base_stats(sp),
            "live": None,
            "provenance": "rsd",  # FG-4: asserted at bridge construction
        }
    return {"opponents": opponents}

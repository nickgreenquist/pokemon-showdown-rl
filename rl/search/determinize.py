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
  species already seen, then a full set sampled.
  KNOWN APPROXIMATION, named (design §3): the generator's team-level
  type/weakness cap-of-2 is NOT yet enforced here (needs a species->types
  table wired in); D19 measured the cap as 88-90% of pool structure, so
  FG-7's support gate (>= 0.99) is the arbiter of whether this shortcut
  survives. TODO(R1): enforce cap by rejection before FG-7 runs.
- All randomness from the caller-supplied numpy Generator (key-derived per
  decision — determinism clause D2); the global `random` module is never
  touched (username landmine).
"""

from __future__ import annotations

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
        }
    n_unrevealed = 6 - len(opponents)
    pool = sorted(randbats_prior.known_species() - seen)
    for _ in range(max(0, n_unrevealed)):
        sp = str(rng.choice(pool))
        pool.remove(sp)
        opponents[sp] = {
            "moves": _complete_revealed(sp, frozenset(), rng),
            "level": randbats_prior.species_level(sp),
            "base_stats": _static_base_stats(sp),
            "live": None,
        }
    return {"opponents": opponents}

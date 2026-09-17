"""Foul Play's OWN gen-1 leaf evaluator and the way Foul Play consumes it.

A FAITHFUL PORT of `poke-engine 0.0.48`'s `src/gen1/evaluate.rs` (202 lines,
~30 hand-tuned constants) plus the two lines of `src/mcts.rs` that turn it into
a value. Read out of the sdist on 2026-09-17 for the exact version our
`foul-play` env runs, after the maintainer asked how Foul Play has such a good
evaluator and whether we had ever looked. We had not: the repo had hypothesised
about this function three times (`docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS
.md`, "poke_engine's hand-written heuristic works at depth 2.4; our critic does
not work at depth 3") without anyone opening it.

WHY A PORT AND NOT A CALL. `poke_engine`'s Python extension exposes `mcts`,
`generate_instructions` and `calculate_damage` and NOT `evaluate` — the symbol
exists in the binary (`poke_engine::engine::evaluate::evaluate`) but is not
bound. Every field the function reads IS exposed on the Python `State`, so the
arithmetic is portable; the risk is that a port silently diverges, which would
invalidate any experiment built on it. `tests/test_fp_eval.py` is the answer to
that: hand-computed golden values taken from the Rust source, plus the
antisymmetry invariant.

THE PART THAT MATTERS IS NOT THE HEURISTIC. `mcts.rs`:

    pub fn rollout(&mut self, state, root_eval) -> f32 {
        let eval = evaluate(state);
        sigmoid(eval - root_eval)          // 1/(1+exp(-0.0125x))
    }

There is no rollout. One heuristic call per leaf, DIFFERENCED AGAINST THE ROOT,
then squashed so ~200 points is near-decisive. Two consequences, and they are
the reason this module exists:

  * the function never estimates P(win) in absolute terms, only whether a leaf
    is better or worse than where we already are. Any constant bias cancels.
  * it is the SAME function everywhere, so a deeper tree asks it no harder a
    question. Our critic was fit by PPO only to states our own policy reaches,
    and search deliberately visits the lines the policy does not play.

SCALE. Terminal values in `rl/search/matrix.py` are +1 / 0 / -1, so the sigmoid
is mapped onto the same interval as `2*sigmoid(...) - 1`. Every downstream
consumer — `row_ev`, the D5 margin gate — reads that scale, so a `margin_delta`
tuned against our critic means something DIFFERENT here and must be re-swept.
That is not a detail: it is the override-rate confound that made every depth
number before 2026-09-17 uninterpretable.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

import numpy as np

# --- verbatim from src/gen1/evaluate.rs, poke-engine 0.0.48 ----------------
POKEMON_ALIVE = 30.0
POKEMON_HP = 100.0
POKEMON_ATTACK_BOOST = 30.0
POKEMON_DEFENSE_BOOST = 15.0
POKEMON_SPECIAL_ATTACK_BOOST = 30.0
POKEMON_SPEED_BOOST = 30.0
BOOST_MULTIPLIER = {
    6: 3.3, 5: 3.15, 4: 3.0, 3: 2.5, 2: 2.0, 1: 1.0, 0: 0.0,
    -1: -1.0, -2: -2.0, -3: -2.5, -4: -3.0, -5: -3.15, -6: -3.3,
}
POKEMON_FROZEN = -40.0
POKEMON_ASLEEP = -25.0
POKEMON_PARALYZED = -25.0
POKEMON_TOXIC = -30.0
POKEMON_POISONED = -10.0
POKEMON_BURNED = -25.0
LEECH_SEED = -30.0
SUBSTITUTE = 40.0
CONFUSION = -20.0
REFLECT = 20.0
LIGHT_SCREEN = 20.0
# src/mcts.rs: "Tuned so that ~200 points is very close to 1.0"
SIGMOID_K = 0.0125

_STATUS = {
    "freeze": POKEMON_FROZEN, "frz": POKEMON_FROZEN,
    "sleep": POKEMON_ASLEEP, "slp": POKEMON_ASLEEP,
    "paralyze": POKEMON_PARALYZED, "par": POKEMON_PARALYZED,
    "toxic": POKEMON_TOXIC, "tox": POKEMON_TOXIC,
    "poison": POKEMON_POISONED, "psn": POKEMON_POISONED,
}
_VOLATILE = {
    "leechseed": LEECH_SEED, "substitute": SUBSTITUTE, "confusion": CONFUSION,
    "reflect": REFLECT, "lightscreen": LIGHT_SCREEN,
}


@lru_cache(maxsize=1)
def _physical_moves() -> frozenset[str]:
    """Move ids that are PHYSICAL in gen 1.

    The Rust reads `mv.choice.category == MoveCategory::Physical`; the Python
    `Move` exposes only `id`, `pp` and `disabled`, so the category is taken
    from poke-env's gen-1 move data — the same data our encoder already
    depends on. In gen 1 the category is a property of the move's TYPE, so
    this table is exact rather than approximate.
    """
    from poke_env.data import GenData

    return frozenset(
        mid for mid, m in GenData.from_gen(1).moves.items()
        if m.get("category") == "Physical"
    )


def _active_index(side: Any) -> int:
    """pyo3 hands `active_index` back as a STRING on some builds.

    Indexing `side.pokemon` with it raises TypeError, and on 2026-09-11 that
    TypeError landed in a bare `except` and produced a depth-2 probe with ZERO
    grandchildren that printed a win rate anyway. Same normalisation as
    `matrix._opp_bench_target`.
    """
    ai = side.active_index
    return ai if isinstance(ai, int) else int(str(ai)[-1])


def _evaluate_burned(pokemon: Any) -> float:
    """`evaluate_burned`: scaled by the count of PHYSICAL moves, halved for
    special attackers. The single most considered line in the file."""
    physical = _physical_moves()
    multiplier = float(sum(1 for mv in pokemon.moves if mv.id in physical))
    if pokemon.special_attack > pokemon.attack:
        multiplier /= 2.0
    return multiplier * POKEMON_BURNED


def _evaluate_pokemon(pokemon: Any) -> float:
    score = POKEMON_HP * pokemon.hp / pokemon.maxhp
    status = str(pokemon.status).lower().rsplit(".", 1)[-1]
    if status in ("burn", "brn"):
        score += _evaluate_burned(pokemon)
    else:
        score += _STATUS.get(status, 0.0)
    # THE FLOOR IS APPLIED BEFORE `ALIVE`, not after: a badly statused mon is
    # still worth 30. Getting this order wrong changes every score in the file.
    if score < 0.0:
        score = 0.0
    return score + POKEMON_ALIVE


def _evaluate_side(side: Any) -> float:
    score = 0.0
    active = _active_index(side)
    for i, pkmn in enumerate(side.pokemon):
        if pkmn.hp <= 0:
            continue
        score += _evaluate_pokemon(pkmn)
        if i != active:
            continue
        # volatiles and boosts count for the ACTIVE pokemon only
        vs = {str(v).lower().rsplit(".", 1)[-1] for v in side.volatile_statuses}
        for name, value in _VOLATILE.items():
            if name in vs:
                score += value
        score += BOOST_MULTIPLIER[int(side.attack_boost)] * POKEMON_ATTACK_BOOST
        score += BOOST_MULTIPLIER[int(side.defense_boost)] * POKEMON_DEFENSE_BOOST
        score += (BOOST_MULTIPLIER[int(side.special_attack_boost)]
                  * POKEMON_SPECIAL_ATTACK_BOOST)
        score += BOOST_MULTIPLIER[int(side.speed_boost)] * POKEMON_SPEED_BOOST
    return score


def evaluate(state: Any) -> float:
    """`poke_engine::gen1::evaluate::evaluate`, ported. side_one - side_two."""
    return _evaluate_side(state.side_one) - _evaluate_side(state.side_two)


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-SIGMOID_K * x))


def leaf_value(leaf_state: Any, root_eval: float) -> float:
    """Foul Play's `rollout`, on OUR +1/-1 scale.

    `2*sigmoid(eval(leaf) - eval(root)) - 1`. Terminal states are NOT handled
    here: `matrix._terminal_value` has already fixed those to +1/0/-1 before a
    leaf ever reaches an evaluator, exactly as `rollout` returns the true
    outcome when `battle_is_over`.
    """
    return 2.0 * sigmoid(evaluate(leaf_state) - root_eval) - 1.0


def leaf_values(leaf_states: list, root_evals: list[float],
                det_index: list[int]) -> np.ndarray:
    """Vectorised `leaf_value` over a batch, each leaf differenced against the
    root of ITS OWN determinization — Foul Play differences against the one
    root it has; we hold `n_det` of them and a leaf belongs to exactly one."""
    return np.array(
        [leaf_value(s, root_evals[d]) for s, d in zip(leaf_states, det_index)],
        dtype=np.float64,
    )

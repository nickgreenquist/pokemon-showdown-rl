"""QUICK AND DIRTY: does a real TREE beat our depth-1 matrix?

Not a pre-registered arm. A probe, to be thrown away or promoted.

Everything we have measured is depth-1: the DOSES dial `n_det` and `leaf_cap`,
which buy WIDTH at one ply. Foul Play spends a ~40 ms budget on `poke_engine`'s
MCTS and decides by VISIT COUNT, and Wang does the same at 200 worker-seconds.
`poke_engine` already ships that MCTS, and `rl/search/bridge.py` already builds
the States it wants -- so the cheapest honest test of "does depth help" is to
call it on our own determinizations and keep our policy in charge of the final
say.

WHAT THIS IS: our determinizer -> poke_engine MCTS per determinization ->
aggregate by VISITS across determinizations -> play it only if it beats the
POLICY's argmax by a margin (the D5 idea, on a visit-share scale instead of
row_ev, because the two are not the same units).

WHAT THIS IS NOT: our critic does not evaluate the tree's leaves -- poke_engine
uses its own heuristic rollout. So a win here says "a real tree helps", NOT
"our value function inside a tree helps". That second thing is Wang's actual
architecture and is the follow-up if this shows anything.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from poke_engine import monte_carlo_tree_search

from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.matrix import our_action_str


def mcts_decision(
    battle: Any,
    mask: np.ndarray,
    prior: np.ndarray,
    rng: np.random.Generator,
    n_det: int = 2,
    duration_ms: int = 20,
    margin: float | None = 0.10,
) -> tuple[int, dict]:
    """FP's shape: n_det determinizations, `duration_ms` of MCTS on each,
    decide by pooled VISIT SHARE, gated against the policy.

    Defaults are FP@20's measured budget: 2 determinizations x 20 ms.
    """
    rows = [i for i in range(len(mask)) if mask[i]]
    assert rows, "no legal action"
    policy_argmax = int(max(rows, key=lambda a: prior[a]))
    if len(rows) == 1:
        return rows[0], {"mcts/only_move": 1, "search/chosen": rows[0]}

    counters = BridgeCounters()
    dets = [sample_determinization(battle, rng) for _ in range(n_det)]
    states = [battle_to_state(battle, d, counters) for d in dets]

    # our action index -> engine move string, once
    a_str = {a: our_action_str(battle, a) for a in rows}
    visits: dict[str, float] = {}
    scores: dict[str, float] = {}
    total = 0.0
    trees = 0
    for st in states:
        try:
            res = monte_carlo_tree_search(st, duration_ms)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:  # PyO3 panics derive from BaseException (F-14)
            continue
        trees += 1
        for r in res.side_one:
            visits[r.move_choice] = visits.get(r.move_choice, 0.0) + r.visits
            scores[r.move_choice] = scores.get(r.move_choice, 0.0) + r.total_score
            total += r.visits
    if not trees or total <= 0:  # engine refused every determinization
        return policy_argmax, {"mcts/failed": 1, "search/chosen": policy_argmax,
                               "search/policy_argmax": policy_argmax}

    share = {a: visits.get(a_str[a], 0.0) / total for a in rows}
    mcts_argmax = int(max(rows, key=lambda a: (share[a], prior[a], -a)))
    gap = share[mcts_argmax] - share[policy_argmax]
    override = margin is not None and gap > float(margin)
    chosen = mcts_argmax if override else policy_argmax
    return chosen, {
        "search/chosen": chosen,
        "search/policy_argmax": policy_argmax,
        "mcts/argmax": mcts_argmax,
        "mcts/visit_share_best": share[mcts_argmax],
        "mcts/visit_share_policy": share[policy_argmax],
        "mcts/gap": gap,
        "mcts/total_visits": total,
        "mcts/trees": trees,
        "search/overrode": int(bool(override)),
    }


def depth_census(
    battle: Any,
    rng: np.random.Generator,
    budgets: tuple[int, ...] = (20, 200, 2000),
) -> dict:
    """HOW DEEP DOES A TREE ACTUALLY GET ON OUR STATES?

    Every depth claim in this project is currently an argument. `poke_engine`
    ships `iterative_deepening_expectiminimax`, which reports the depth it
    finished, so the question is directly measurable: build one determinization
    of the live battle and ask the engine how far it got at each budget.

    This is a census, not a decision rule -- the returned move is discarded.
    FP@20's whole budget is ~40 ms; the ladder allows 150 s per turn.
    """
    from poke_engine import iterative_deepening_expectiminimax

    counters = BridgeCounters()
    try:
        st = battle_to_state(battle, sample_determinization(battle, rng), counters)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return {}
    out: dict[str, float] = {}
    for ms in budgets:
        try:
            res = iterative_deepening_expectiminimax(st, int(ms))
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            continue
        d = getattr(res, "depth_searched", None)
        if d is None:  # pyo3 may expose it only through the repr
            import re
            m = re.search(r"depth[_a-z]*[=:\s]+(\d+)", repr(res))
            d = int(m.group(1)) if m else -1
        out[f"census/depth_{ms}ms"] = float(d)
    return out

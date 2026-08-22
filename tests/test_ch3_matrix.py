"""CH3 R1 matrix/agent tests: the L6 mapping law's plumbing, determinism
(D2/D3/D4), the raising watchdog, and the force-switch/locked-opponent
column substitutions. Offline: no server, no checkpoints (stub critic)."""

import numpy as np
import pytest
from poke_env.data import GenData

from rl.search.matrix import (
    DOSES,
    Dose,
    SearchWatchdogError,
    decision_rng,
    our_action_str,
    solve_decision,
)
from tests.test_ch3_bridge import _battle, _mon

_TYPE_CHART = GenData.from_format("gen1randombattle").type_chart


def _two_mon_battle():
    b = _battle()
    b.team["p1: Chansey"] = _mon(
        "chansey", ["softboiled", "icebeam", "thunderwave", "counter"]
    )
    return b


def _mask(moves=True, switches=()):
    m = np.zeros(10, dtype=bool)
    if moves:
        m[6:10] = True
    for i in switches:
        m[i] = True
    return m


def _uniform_q():
    return np.full(6, 1.0 / 6.0)


def _zero_critic(batch):
    return np.zeros(batch.shape[0])


def test_our_action_str_mapping():
    b = _two_mon_battle()
    assert our_action_str(b, 1) == "chansey"  # switch: team slot 1
    assert our_action_str(b, 6) == "bodyslam"  # move slot 0
    assert our_action_str(b, 9) == "hyperbeam"


def test_solve_decision_deterministic_under_key():
    b = _two_mon_battle()
    prior = np.full(10, 0.1)
    outs = []
    for _ in range(2):
        rng = decision_rng(62, 3, b.turn, 7)
        outs.append(
            solve_decision(
                b, _mask(switches=[1]), _uniform_q(), prior,
                DOSES["S"], rng, _zero_critic, _TYPE_CHART,
            )
        )
    (a1, s1), (a2, s2) = outs
    assert a1 == a2
    assert s1["search/leaves"] == s2["search/leaves"]
    assert s1["search/row_ev"] == s2["search/row_ev"]


def test_tie_break_prior_then_lowest_index():
    # zero critic -> every row EV is exactly 0.0 -> prior decides (D3)
    b = _two_mon_battle()
    prior = np.zeros(10)
    prior[8] = 0.9  # blizzard
    rng = decision_rng(62, 0, b.turn, 0)
    action, stats = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), prior,
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 8
    # flat prior too: lowest action index wins
    rng = decision_rng(62, 0, b.turn, 0)
    action, _ = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 1


def test_watchdog_raises_never_falls_back():
    b = _two_mon_battle()
    tiny = Dose(n_det=1, top_branches=6, leaf_cap=324, node_cap=3)
    rng = decision_rng(62, 0, b.turn, 0)
    with pytest.raises(SearchWatchdogError):
        solve_decision(
            b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
            tiny, rng, _zero_critic, _TYPE_CHART,
        )


def test_force_switch_single_none_column():
    b = _two_mon_battle()
    b.force_switch = True
    b.active_pokemon.current_hp_fraction = 0.0
    b.active_pokemon.fainted = True
    b.active_pokemon.current_hp = 0
    rng = decision_rng(62, 0, b.turn, 0)
    action, stats = solve_decision(
        b, _mask(moves=False, switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["M"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 1
    assert stats["search/cols"] == 1
    assert stats["search/force_switch"] == 1
    assert stats["oppact/other_move_mass"] == 0.0


def test_locked_opponent_substituted_to_none():
    b = _two_mon_battle()
    b.opponent_active_pokemon.must_recharge = True
    rng = decision_rng(62, 0, b.turn, 0)
    _, stats = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert stats["search/opp_locked"] == 1
    assert stats["search/cols"] == 1


def test_cell_count_and_other_move_mass():
    b = _two_mon_battle()
    q = np.array([0.3, 0.2, 0.1, 0.1, 0.2, 0.1])
    rng = decision_rng(62, 1, b.turn, 2)
    _, stats = solve_decision(
        b, _mask(switches=[1]), q, np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    # 4 slots + SWITCH, OTHER_MOVE never simulated
    assert stats["search/cols"] == 5
    assert stats["oppact/other_move_mass"] == pytest.approx(0.2)
    assert stats["search/rows"] == 5  # 4 moves + 1 switch
    assert stats["search/leaves"] <= DOSES["S"].leaf_cap

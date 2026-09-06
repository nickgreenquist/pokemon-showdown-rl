"""Mask-desync recovery (2026-08-18, after D29r lane s90).

A poke-env listener-thread re-request can invalidate a mask-legal action
between mask emission and strict order conversion; unhandled, one such
ValueError killed a 50M lane at 35M. The recovery intercepts at the
CONVERSION sites (ShowdownSingles.action_to_order / order_to_action
overrides + PoolPlayer's static call) — never at the step boundary, where
PokeEnv.step has already flipped agent*_to_move and a retry deadlocks in
the timeout-less race_get. These tests are offline: the conversion layer is
stubbed at SinglesEnv, the fallback draw reads a stub battle's
valid_orders.

The loudness contract under test: every recovery warns and counts; a second
desync in the same battle raises MaskDesyncCapExceeded; more than
_MASK_DESYNC_CAP recoveries within _MASK_DESYNC_WINDOW env steps raises;
counters are module-level (per PROCESS — num_envs sub-envs must not
multiply the budget).
"""

from types import SimpleNamespace

import numpy as np
import pytest
from poke_env.environment import SinglesEnv

import rl.envs.showdown as showdown
from rl.envs.showdown import (
    _OPP_CHOICE_NONE,
    MaskDesyncCapExceeded,
    PoolPlayer,
    ShowdownSingles,
    _recover_mask_desync,
    mask_desync_total,
)


@pytest.fixture(autouse=True)
def _clean_module_state():
    showdown._reset_mask_desync_state()
    yield
    showdown._reset_mask_desync_state()


def _battle(tag="battle-gen1randombattle-1", orders=("order-a",)):
    return SimpleNamespace(
        battle_tag=tag, turn=42, logger=None, valid_orders=list(orders)
    )


def test_recovery_returns_legal_order_and_counts():
    battle = _battle(orders=["only-legal"])
    order = _recover_mask_desync(battle, ValueError("boom"))
    assert order == "only-legal"
    assert mask_desync_total() == 1


def test_second_desync_in_same_battle_raises():
    battle = _battle()
    _recover_mask_desync(battle, ValueError("first"))
    with pytest.raises(MaskDesyncCapExceeded):
        _recover_mask_desync(battle, ValueError("second"))
    # The failed recovery still counted the battle only once.
    assert mask_desync_total() == 1


def test_window_cap_raises_on_burst():
    # _MASK_DESYNC_CAP recoveries inside one window pass; the next raises.
    for i in range(showdown._MASK_DESYNC_CAP):
        _recover_mask_desync(_battle(tag=f"battle-{i}"), ValueError("x"))
    with pytest.raises(MaskDesyncCapExceeded):
        _recover_mask_desync(_battle(tag="battle-burst"), ValueError("x"))


def test_window_cap_tolerates_slow_drip():
    # The same count spaced beyond the window never trips — a 250M run's
    # benign drip must not be killed by a lifetime cap.
    for i in range(2 * showdown._MASK_DESYNC_CAP):
        _recover_mask_desync(_battle(tag=f"battle-drip-{i}"), ValueError("x"))
        showdown._env_step_counter += showdown._MASK_DESYNC_WINDOW + 1
    assert mask_desync_total() == 2 * showdown._MASK_DESYNC_CAP


def test_action_to_order_override_intercepts(monkeypatch):
    def fake(action, battle, fake=False, strict=True):
        if strict:
            raise ValueError("converted order not in valid orders")
        return "nonstrict-result"

    monkeypatch.setattr(SinglesEnv, "action_to_order", fake)
    battle = _battle(orders=["fallback-order"])
    assert (
        ShowdownSingles.action_to_order(np.int64(1), battle) == "fallback-order"
    )
    assert mask_desync_total() == 1
    # strict=False callers pass straight through — poke-env degrades
    # internally and no recovery (or count) happens.
    assert (
        ShowdownSingles.action_to_order(np.int64(1), battle, strict=False)
        == "nonstrict-result"
    )
    assert mask_desync_total() == 1


def test_order_to_action_override_converts_fallback(monkeypatch):
    calls = []

    def fake(order, battle, fake=False, strict=True):
        calls.append((order, strict))
        if strict:
            raise ValueError("order not in valid orders")
        return 7

    monkeypatch.setattr(SinglesEnv, "order_to_action", fake)
    battle = _battle(orders=["fallback-order"])
    assert ShowdownSingles.order_to_action("opp-order", battle) == 7
    assert mask_desync_total() == 1
    # The fallback (not the raced order) is what got converted, non-strict.
    assert calls == [("opp-order", True), ("fallback-order", False)]


def test_pool_player_recovery_drops_label(monkeypatch):
    monkeypatch.setattr(showdown, "embed_battle", lambda b, tc: np.zeros(3))
    monkeypatch.setattr(SinglesEnv, "get_action_mask", lambda b: [True] * 10)

    def raising(action, battle, fake=False, strict=True):
        raise ValueError("converted order not in valid orders")

    monkeypatch.setattr(SinglesEnv, "action_to_order", raising)
    battle = _battle(orders=["fallback-order"])
    battle.wait = False
    player = PoolPlayer.__new__(PoolPlayer)
    member = SimpleNamespace(move=lambda obs, mask, rng: 3)
    player._by_tag = {battle.battle_tag: (battle, member, 1)}  # skip selection
    player._record_choices = False
    player._rng = np.random.default_rng(0)
    player._type_chart = {}
    player._choice = (1, 2, 3)  # stale value that must not survive
    order = PoolPlayer.choose_move(player, battle)
    assert order == "fallback-order"
    # The label is DROPPED, not recorded from the fallback: a fallback
    # scored against the stale frame could flip the == 0 aux gates.
    assert player._choice == _OPP_CHOICE_NONE
    assert mask_desync_total() == 1


def test_cap_exception_is_distinct_and_chained():
    battle = _battle()
    _recover_mask_desync(battle, ValueError("first"))
    with pytest.raises(MaskDesyncCapExceeded) as exc_info:
        _recover_mask_desync(battle, ValueError("second"))
    assert isinstance(exc_info.value, RuntimeError)
    assert isinstance(exc_info.value.__cause__, ValueError)


# --- 2026-09-06: the request MOVED under a pool-seat decision ---------------
# The first gen-4 fleet died nine minutes in: seven desyncs in ~250k lane
# steps, every one on the pool seat, tripped the gen-1 cap (3 per 100k). A
# failed conversion proves the fresh request is in, so the seat now decides
# AGAIN on it (a real decision, recorded from the fresh state); the counted
# random recovery is only for a state that moves twice. And a step on which
# PokeEnv will discard seat 2's order (agent2_to_move False) is answered with
# a default order — no phantom forward, no phantom harvest row.


def _pool_player(battle, member):
    player = PoolPlayer.__new__(PoolPlayer)
    player._by_tag = {battle.battle_tag: (battle, member, 1)}  # skip selection
    player._record_choices = False
    player._rng = np.random.default_rng(0)
    player._type_chart = {}
    player._choice = (1, 2, 3)  # stale value that must not survive
    return player


def test_pool_player_redecides_once_when_the_request_moved(monkeypatch):
    monkeypatch.setattr(showdown, "embed_battle", lambda b, tc: np.zeros(3))
    monkeypatch.setattr(SinglesEnv, "get_action_mask", lambda b: [True] * 10)
    monkeypatch.setattr(showdown, "_order_identity", lambda order, battle: (1, 7, 1))
    conversions = []

    def moved_once(action, battle, fake=False, strict=True):
        conversions.append(int(action))
        if len(conversions) == 1:
            raise ValueError("converted order not in valid orders (stale)")
        return f"fresh-order-{int(action)}"

    monkeypatch.setattr(SinglesEnv, "action_to_order", moved_once)
    battle = _battle(orders=["fallback-order"])
    battle.wait = False
    draws = iter([3, 5])
    member = SimpleNamespace(move=lambda obs, mask, rng: next(draws))
    player = _pool_player(battle, member)
    order = PoolPlayer.choose_move(player, battle)
    assert order == "fresh-order-5"            # the SECOND decision, on the fresh request
    assert conversions == [3, 5]
    assert player._choice == (1, 7, 1)          # recorded from the fresh decision
    assert showdown.mask_redecide_total() == 1
    assert mask_desync_total() == 0             # a re-decision is not a desync


def test_pool_player_redecision_harvests_the_fresh_row_only(monkeypatch):
    monkeypatch.setattr(showdown, "embed_battle", lambda b, tc: np.zeros(3))
    monkeypatch.setattr(SinglesEnv, "get_action_mask", lambda b: [True] * 10)
    monkeypatch.setattr(showdown, "_order_identity", lambda order, battle: (1, 7, 1))
    n = {"calls": 0}

    def moved_once(action, battle, fake=False, strict=True):
        n["calls"] += 1
        if n["calls"] == 1:
            raise ValueError("stale")
        return "fresh-order"

    monkeypatch.setattr(SinglesEnv, "action_to_order", moved_once)
    battle = _battle(orders=["fallback-order"])
    battle.wait = False
    draws = iter([(3, -0.3), (5, -0.5)])
    member = SimpleNamespace(move_logp=lambda obs, mask, rng: next(draws))
    player = _pool_player(battle, member)
    recorded, dropped = [], []
    player._harvest = SimpleNamespace(
        record=lambda tag, obs, mask, action, logp, version: recorded.append((action, logp)),
        drop_row=lambda tag: dropped.append(tag),
    )
    assert PoolPlayer.choose_move(player, battle) == "fresh-order"
    assert recorded == [(5, -0.5)] and dropped == []


def test_pool_player_twice_moved_request_still_recovers_and_drops(monkeypatch):
    monkeypatch.setattr(showdown, "embed_battle", lambda b, tc: np.zeros(3))
    monkeypatch.setattr(SinglesEnv, "get_action_mask", lambda b: [True] * 10)

    def always(action, battle, fake=False, strict=True):
        raise ValueError("moved again")

    monkeypatch.setattr(SinglesEnv, "action_to_order", always)
    battle = _battle(orders=["fallback-order"])
    battle.wait = False
    player = _pool_player(battle, SimpleNamespace(move=lambda obs, mask, rng: 3))
    assert PoolPlayer.choose_move(player, battle) == "fallback-order"
    assert player._choice == _OPP_CHOICE_NONE
    assert mask_desync_total() == 1 and showdown.mask_redecide_total() == 0


def test_pool_player_phantom_step_is_answered_without_a_forward(monkeypatch):
    from poke_env.player.battle_order import DefaultBattleOrder

    forwards = []
    battle = _battle(orders=["order-a"])
    battle.wait = False
    player = _pool_player(battle, SimpleNamespace(move=lambda obs, mask, rng: forwards.append(1) or 3))
    player.expect_decision(False)               # ShowdownEnv.step: agent2_to_move is False
    order = PoolPlayer.choose_move(player, battle)
    assert isinstance(order, DefaultBattleOrder)
    assert forwards == [] and player._choice == _OPP_CHOICE_NONE
    player.expect_decision(True)
    monkeypatch.setattr(showdown, "embed_battle", lambda b, tc: np.zeros(3))
    monkeypatch.setattr(SinglesEnv, "get_action_mask", lambda b: [True] * 10)
    monkeypatch.setattr(SinglesEnv, "action_to_order", lambda a, b, fake=False, strict=True: "order-a")
    monkeypatch.setattr(showdown, "_order_identity", lambda order, battle: (1, 7, 1))
    assert PoolPlayer.choose_move(player, battle) == "order-a" and forwards == [1]

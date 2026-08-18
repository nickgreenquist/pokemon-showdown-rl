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
    player._battle_tag = battle.battle_tag  # skip pool member selection
    player._current = SimpleNamespace(move=lambda obs, mask, rng: 3)
    player._member = 1
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

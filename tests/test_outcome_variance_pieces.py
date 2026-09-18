"""The two hand-built pieces of IDEAS 2.11, against the REAL engine.

`scripts/outcome_variance.py` has never run, it gates every fleet item above it,
and it would run for the better part of an hour. Its two risky pieces are the
ones its own docstring flags -- `_swap` (side-swapping a `State` so the rollout
is self-play rather than "us versus a scripted opponent", which would collapse
the spread being measured) and `_shadow_mask` (a 10-slot mask built BY HAND
against `matrix.our_action_str`'s ordering, because `SinglesEnv.get_action_mask`
cannot read a shadow battle). A mask that disagrees with the decoder silently
plays a different move than the one scored.

Both are exercised here on a real determinized state, so a crash costs a second
rather than forty minutes.
"""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.matrix import _terminal_value
from rl.search.shadow_battle import shadow_battle
from tests.test_ch3_matrix import _two_mon_battle

MOD = Path(__file__).parent.parent / "scripts/outcome_variance.py"
spec = importlib.util.spec_from_file_location("outcome_variance", MOD)
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)


@pytest.fixture
def state():
    b = _two_mon_battle()
    det = sample_determinization(b, np.random.default_rng(7))
    return battle_to_state(b, det, BridgeCounters())


def test_swap_really_exchanges_the_sides(state):
    swapped = ov._swap(state)
    assert swapped.side_one.active_index == state.side_two.active_index
    assert (len(swapped.side_one.pokemon), len(swapped.side_two.pokemon)) == (
        len(state.side_two.pokemon), len(state.side_one.pokemon))
    assert [m.hp for m in swapped.side_one.pokemon] == [
        m.hp for m in state.side_two.pokemon]
    # and it is an involution: swapping twice is where you started
    back = ov._swap(swapped)
    assert [m.hp for m in back.side_one.pokemon] == [
        m.hp for m in state.side_one.pokemon]


def test_swap_carries_the_field_not_just_the_sides(state):
    """Weather and its counters are side-agnostic; dropping them would make the
    opponent's view of the position a DIFFERENT position, and the whole point of
    the swap is that both seats see the same game."""
    swapped = ov._swap(state)
    for attr in ("weather", "weather_turns_remaining", "trick_room",
                 "trick_room_turns_remaining"):
        assert getattr(swapped, attr) == getattr(state, attr), attr


def test_swap_preserves_the_terminal_verdict_up_to_sign(state):
    """`_terminal_value` is +1 when side two is wiped. If the swap is faithful
    the verdict must flip sign, never vanish."""
    assert _terminal_value(state) is None
    assert _terminal_value(ov._swap(state)) is None


def test_the_shadow_mask_agrees_with_the_decoder(state):
    """Every slot the mask calls legal must decode, and slots 6..9 are moves in
    `list(active.moves.keys())` order -- the ordering `our_action_str` uses."""
    from rl.search.matrix import our_action_str

    sb = shadow_battle(state, 5)
    mask = ov._shadow_mask(sb)
    assert mask.dtype == bool and mask.shape == (10,)
    assert mask.any(), "a mid-battle position with no legal action is a bug"
    for i in np.flatnonzero(mask):
        s = our_action_str(sb, int(i))
        assert isinstance(s, str) and s, f"slot {i} is masked legal but decodes to {s!r}"


def test_the_shadow_mask_never_offers_the_active_pokemon_as_a_switch(state):
    sb = shadow_battle(state, 5)
    mask = ov._shadow_mask(sb)
    team = list(sb.team.values())
    for i, mon in enumerate(team[:6]):
        if mon is sb.active_pokemon:
            assert not mask[i], "switching to the mon that is already out"
        if mon.fainted:
            assert not mask[i], "switching to a fainted mon"


def test_a_force_switch_offers_no_moves(state):
    sb = shadow_battle(state, 5)
    sb.force_switch = True
    assert not ov._shadow_mask(sb)[6:].any()


def test_rollout_returns_nan_rather_than_a_draw_when_it_cannot_play(state, monkeypatch):
    """NaN is DROPPED by the caller; 0.0 would be counted as a draw and pull the
    measured variance down -- which is the quantity the whole script exists to
    estimate."""
    monkeypatch.setattr(ov, "_choose", lambda *a, **k: (None, None))
    out = ov.rollout(state, object(), None, np.random.default_rng(0), 5)
    assert np.isnan(out)

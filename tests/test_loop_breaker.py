"""Does the loop breaker escape the loop that was MEASURED, and nothing else?

RESULTS §28 measured the signature six times: an unchanging observation, a
deterministic argmax, and ~950 strictly alternating switches against a frozen
opponent, to the turn cap and a tie. The two things this module has to prove are
that it escapes THAT, and that it is invisible everywhere else -- because it is a
change to the policy form and the locked protocol names the policy.
"""
import numpy as np
import pytest

from rl.common.loop_breaker import DEFAULT_THRESHOLD, LoopBreaker, obs_key


def mask(*legal, n=10):
    m = np.zeros(n, dtype=bool)
    for i in legal:
        m[i] = True
    return m


# ------------------------------------------------ it must be invisible normally
def test_with_no_repetition_it_is_exactly_the_argmax():
    """The claim that matters most: it CANNOT change a non-looping battle."""
    lb = LoopBreaker()
    rng = np.random.default_rng(0)
    for i in range(200):
        obs = rng.normal(size=8)          # a new position every decision
        sc = rng.normal(size=10)
        m = mask(1, 6, 7, 8)
        got = lb.decide(obs, sc, m)
        legal = np.flatnonzero(m)
        assert got == int(legal[np.argmax(sc[legal])])
    assert lb.counters["loop/fired"] == 0


def test_a_position_repeated_below_the_threshold_still_plays_the_argmax():
    """Two Pokemon trading Recover is a real game, not a fixed point."""
    lb = LoopBreaker(threshold=4)
    obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9.0, 1.0, 0.5, 0.2]), mask(6, 7, 8, 9)
    for _ in range(3):
        assert lb.decide(obs, sc, m) == 6
    assert lb.counters["loop/fired"] == 0


# --------------------------------------------------- it must escape the measured loop
def test_it_escapes_a_fixed_point_after_the_threshold():
    lb = LoopBreaker(threshold=4)
    obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9.0, 1.0, 0.5, 0.2]), mask(6, 7, 8, 9)
    played = [lb.decide(obs, sc, m) for _ in range(8)]
    assert played[:4] == [6, 6, 6, 6], played
    assert played[4] != 6, "still stuck after the threshold"
    assert lb.counters["loop/fired"] >= 1


def test_it_keeps_escalating_so_a_cycle_of_any_period_unwinds():
    """Breaking to the SECOND best can land in another fixed point -- the
    measured loops are period 2 and period 3."""
    lb = LoopBreaker(threshold=2)
    obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9.0, 8.0, 7.0, 6.0]), mask(6, 7, 8, 9)
    played = [lb.decide(obs, sc, m) for _ in range(9)]
    assert len(set(played)) >= 3, played
    assert played[-1] == 9, "it never reached the last-ranked action"


def test_the_measured_signature_unwinds():
    """THE ACTUAL BUG (§28): the opponent is frozen so the observation stops
    changing, and the policy alternates between two switch slots forever. Here
    the environment is modelled exactly that way -- obs is constant because the
    opponent cannot act -- and the run must stop alternating."""
    lb = LoopBreaker(threshold=4)
    frozen_obs = np.full(8, 0.5)
    # the policy prefers the two switches; the attack (slot 8) is ranked third
    scores = np.array([0.0] * 6 + [0.0, 0.0, 0.0, 0.0])
    scores[0], scores[1], scores[8] = 5.0, 4.9, 1.0     # switch, switch, attack
    m = mask(0, 1, 8)
    played = [lb.decide(frozen_obs, scores, m) for _ in range(40)]
    assert 8 in played, "never reached the attack; the loop would run to the cap"
    assert played.index(8) <= 12, f"took {played.index(8)} turns to escape"
    tail = played[played.index(8):]
    assert set(tail) == {8}, "it escaped and then fell back into the loop"


def test_a_new_battle_forgets():
    """Two battles can legitimately reach the same position. Carrying the count
    across them would fire the breaker on a FIRST visit."""
    lb = LoopBreaker(threshold=2)
    obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9.0, 1.0, 0.5, 0.2]), mask(6, 7, 8, 9)
    for _ in range(4):
        lb.decide(obs, sc, m)
    lb.reset()
    assert lb.decide(obs, sc, m) == 6


# ---------------------------------------------------------------- the details
def test_it_stays_deterministic():
    """Not stochastic: a replay of the same episode plays the same moves, which
    is the whole reason this is proposed instead of sampling."""
    def run():
        lb = LoopBreaker(threshold=3)
        obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9, 8, 7, 6.0]), mask(6, 7, 8, 9)
        return [lb.decide(obs, sc, m) for _ in range(12)]
    assert run() == run()


def test_obs_key_survives_float_noise_but_separates_real_positions():
    """Two float32 encodings of an unchanging position can differ in the last
    bit; a raw hash would never match and the breaker would silently never fire."""
    a = np.array([1.0, 2.0, 3.0])
    assert obs_key(a) == obs_key(a + 1e-9)
    assert obs_key(a) != obs_key(a + 1e-2)


def test_it_never_returns_an_illegal_action():
    lb = LoopBreaker(threshold=2)
    obs, sc = np.ones(8), np.arange(10, dtype=float)
    m = mask(2, 3)
    for _ in range(12):
        assert lb.decide(obs, sc, m) in (2, 3)


def test_a_single_legal_action_cannot_be_escaped():
    """Escalating past the end of the list must clamp, not raise."""
    lb = LoopBreaker(threshold=2)
    obs, sc, m = np.ones(8), np.arange(10, dtype=float), mask(7)
    for _ in range(10):
        assert lb.decide(obs, sc, m) == 7


def test_the_counters_reach_disk_before_it_gets_an_arm():
    lb = LoopBreaker(threshold=2)
    obs, sc, m = np.ones(8), np.array([0.0] * 6 + [9, 8, 7, 6.0]), mask(6, 7, 8, 9)
    for _ in range(6):
        lb.decide(obs, sc, m)
    for k in ("loop/decisions", "loop/fired", "loop/max_repeat", "loop/distinct_states"):
        assert k in lb.counters
    assert lb.counters["loop/decisions"] == 6
    assert lb.counters["loop/fired"] > 0
    assert 0.0 < lb.fired_rate <= 1.0


def test_a_threshold_of_one_is_refused():
    with pytest.raises(AssertionError):
        LoopBreaker(threshold=1)


def test_the_default_threshold_is_above_a_legitimate_repeat():
    assert DEFAULT_THRESHOLD >= 3

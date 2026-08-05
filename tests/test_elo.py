"""Bradley-Terry harness tests (Phase 4 chunk 3).

The two tests that look odd are the two the spec singles out:

- stability across ITERATION COUNTS (200/2k/20k), never a successive-
  difference tolerance — an undefeated player creeps at ~constant Elo per
  decade of iterations with 1/k step sizes, which a tolerance reads as
  slow convergence and converts into a finite, wrong number. Refusal
  (Ford) plus cross-count agreement is the discriminating pair.
- the all-draws matrix must bootstrap to CI width EXACTLY zero: each
  (pair, colour) cell resamples its own fixed total, so a degenerate cell
  is reproduced verbatim. An i.i.d. bootstrap over pooled games reports
  sd 0.021 here (measured, PLAN.md) — nonzero width on this fixture means
  the stratification broke.
"""

import numpy as np
import pytest

from rl.selfplay.elo import (
    ELO_PER_LOG,
    alphastar_proxy,
    bootstrap,
    cycle_null_band,
    fit_bt,
    ford_connected,
    intransitive_triples,
    rate,
    regression_null_band,
    regression_rate,
)


def bt_counts(rng, strengths, games=100):
    """Sample a full colour-alternated round robin from known BT strengths
    (no draws): the ground truth the fits are compared against."""
    names = sorted(strengths)
    counts = {}
    for a_idx, a in enumerate(names):
        for b in names[a_idx + 1 :]:
            p_win = strengths[a] / (strengths[a] + strengths[b])
            for first, second, chance in ((a, b, p_win), (b, a, 1 - p_win)):
                wins = int(rng.binomial(games // 2, chance))
                counts[(first, second)] = (wins, 0, games // 2 - wins)
    return counts


def test_two_player_ratings_are_analytic():
    """60/40 head-to-head: the BT MLE is p_a/p_b = 60/40 exactly, so the
    gap must be 400*log10(1.5) Elo regardless of colour split."""
    counts = {("a", "b"): (35, 0, 15), ("b", "a"): (25, 0, 25)}
    result = rate(counts, anchor="b")
    assert result.ratings["b"] == 0.0
    assert result.ratings["a"] == pytest.approx(400 * np.log10(1.5), abs=1e-6)


def test_draws_count_exactly_half():
    """50 wins + 50 draws must fit identically to 75/25 decisive."""
    with_draws = rate({("a", "b"): (50, 50, 0)}, anchor="b")
    decisive = rate({("a", "b"): (75, 0, 25)}, anchor="b")
    assert with_draws.ratings["a"] == pytest.approx(decisive.ratings["a"], abs=1e-9)


def test_ratings_are_order_independent():
    """Same games under permuted names -> identical ratings (MM updates
    every player from the same frozen iterate; the bookkeeping must not
    reintroduce an order)."""
    rng = np.random.default_rng(0)
    strengths = {"p0": 1.0, "p1": 2.0, "p2": 4.0, "p3": 8.0}
    counts = bt_counts(rng, strengths)
    renamed = {("z" + a, "z" + b): cell for (a, b), cell in counts.items()}
    base = rate(counts, anchor="p0").ratings
    flipped = rate(renamed, anchor="zp0").ratings
    for name, value in base.items():
        assert flipped["z" + name] == pytest.approx(value, abs=1e-9)


def test_undefeated_player_is_refused_by_the_fit_and_dropped_by_rate():
    counts = {
        ("a", "b"): (10, 0, 0),  # a is undefeated
        ("b", "c"): (5, 0, 5),
        ("c", "a"): (0, 0, 10),
    }
    with pytest.raises(ValueError, match="Ford"):
        fit_bt(np.array([[0.0, 10.0], [0.0, 0.0]]))
    result = rate(counts, anchor="b")
    assert result.ceilinged == ["a"]
    assert set(result.ratings) == {"b", "c"}


def test_perfect_scorer_drop_cascades():
    """Removing the undefeated top can leave the next player undefeated
    among the remainder — the drop must iterate, not single-pass."""
    counts = {
        ("a", "b"): (10, 0, 0),
        ("a", "c"): (10, 0, 0),
        ("b", "c"): (10, 0, 0),  # b undefeated once a is gone
        ("c", "d"): (5, 0, 5),
        ("d", "e"): (6, 0, 4),
    }
    result = rate(counts, anchor="d")
    assert result.ceilinged == ["a", "b"]
    assert set(result.ratings) == {"c", "d", "e"}


def test_anchor_dropped_raises():
    counts = {("a", "b"): (10, 0, 0), ("b", "c"): (5, 0, 5)}
    with pytest.raises(ValueError, match="anchor"):
        rate(counts, anchor="a")


def test_ford_connected_is_about_direction_not_contact():
    """a and b played (a swept), so the graph is connected as an UNDIRECTED
    graph — but no score flows b -> a and Ford must say no."""
    assert not ford_connected(np.array([[0.0, 10.0], [0.0, 0.0]]))
    assert ford_connected(np.array([[0.0, 9.5], [0.5, 0.0]]))  # one draw back


def test_stability_across_iteration_counts():
    """The locked test shape: 200 vs 2k vs 20k iterations agree to well
    under an Elo on a Ford-connected ladder spanning ~360 Elo. Creep would
    move ~370 Elo per decade; agreement at this tolerance refutes it."""
    rng = np.random.default_rng(1)
    strengths = {f"p{k}": 1.6**k for k in range(6)}
    counts = bt_counts(rng, strengths, games=100)
    fits = [rate(counts, anchor="p0", iterations=n).ratings for n in (200, 2000, 20000)]
    for name in fits[0]:
        values = [fit[name] for fit in fits]
        assert max(values) - min(values) < 0.5, f"{name}: {values}"


def test_recovers_known_strengths():
    """With plenty of games the fit should land near the generating truth:
    p ratio 8 between the ends = ~361 Elo."""
    rng = np.random.default_rng(2)
    strengths = {"p0": 1.0, "p1": 2.0, "p2": 4.0, "p3": 8.0}
    counts = bt_counts(rng, strengths, games=2000)
    ratings = rate(counts, anchor="p0").ratings
    for name, p in strengths.items():
        expected = ELO_PER_LOG * np.log(p)
        assert ratings[name] == pytest.approx(expected, abs=25)


def test_bootstrap_all_draws_has_exactly_zero_width():
    counts = {("a", "b"): (0, 40, 0), ("b", "a"): (0, 40, 0),
              ("b", "c"): (0, 40, 0), ("c", "b"): (0, 40, 0),
              ("a", "c"): (0, 40, 0), ("c", "a"): (0, 40, 0)}
    result = bootstrap(counts, anchor="a", B=50, iterations=500)
    assert result.failed == 0
    for name, (lo, hi) in result.intervals.items():
        assert lo == 0.0 and hi == 0.0, name


def test_bootstrap_is_seeded_and_has_width_on_real_data():
    rng = np.random.default_rng(3)
    counts = bt_counts(rng, {"p0": 1.0, "p1": 2.0, "p2": 4.0}, games=200)
    first = bootstrap(counts, anchor="p0", B=40, seed=11, iterations=500)
    again = bootstrap(counts, anchor="p0", B=40, seed=11, iterations=500)
    assert first.intervals == again.intervals
    lo, hi = first.intervals["p2"]
    assert hi > lo
    truth = ELO_PER_LOG * np.log(4.0)
    assert lo < truth < hi


def test_bootstrap_flags_failed_resamples_instead_of_fitting_them():
    """A cell with a 1-in-30 upset resamples to a sweep ~36% of the time;
    those resamples drop the swept player (reduced rated_in) or, when the
    anchor is on the wrong end of the sweep, fail outright. Either way no
    non-Ford matrix is ever fitted, and the counts must say which path
    fired."""
    counts = {
        ("a", "b"): (15, 0, 15), ("b", "a"): (15, 0, 15),
        ("b", "c"): (29, 0, 1), ("c", "b"): (1, 0, 29),
    }
    result = bootstrap(counts, anchor="a", B=60, seed=5, iterations=500)
    assert result.failed == 0  # the anchor's own cells are never swept
    assert result.rated_in["a"] == 60
    assert result.rated_in["b"] == 60
    assert result.rated_in["c"] < 60  # dropped whenever the resample sweeps it

    # Anchored at the sweep-side player instead, the same drops become
    # whole-resample failures — and they must be COUNTED, not swallowed.
    anchored_at_c = bootstrap(counts, anchor="c", B=60, seed=5, iterations=500)
    assert anchored_at_c.failed > 0
    assert anchored_at_c.rated_in["c"] == 60 - anchored_at_c.failed


def test_intransitive_triples_on_known_structures():
    """A swept hierarchy has zero cycles; rock-paper-scissors is one cycle
    out of one triple; an all-draws triangle has no majority directions at
    all, and a tied edge must break a cycle rather than complete one."""
    ordered = {("a", "b"): (10, 0, 0), ("a", "c"): (10, 0, 0), ("b", "c"): (10, 0, 0)}
    assert intransitive_triples(ordered) == (0.0, 1)
    rps = {("a", "b"): (10, 0, 0), ("b", "c"): (10, 0, 0), ("c", "a"): (10, 0, 0)}
    assert intransitive_triples(rps) == (1.0, 1)
    all_draws = {("a", "b"): (0, 10, 0), ("b", "c"): (0, 10, 0), ("c", "a"): (0, 10, 0)}
    assert intransitive_triples(all_draws) == (0.0, 1)


def test_cycle_null_band_tracks_ladder_spacing():
    """Wide gaps leave no room for spurious cycles (the null band pins to
    zero); a ladder at ~40-Elo spacing over ~100 games/pair — the regime
    the spec's 7.2-7.7% spurious-cycle figure lives in — has a nonzero
    band even though the generator is perfectly acyclic, which is exactly
    why the bare fraction is never reported alone."""
    games = {("%s" % a, "%s" % b): (50, 0, 50) for a in "abcde" for b in "abcde" if a < b}
    wide = {name: 600.0 * i for i, name in enumerate("abcde")}
    close = {name: 40.0 * i for i, name in enumerate("abcde")}
    assert cycle_null_band(games, wide, B=100, seed=0) == (0.0, 0.0)
    lo, hi = cycle_null_band(games, close, B=100, seed=0)
    assert hi > 0.0


def test_empirical_fraction_of_a_bt_sample_sits_in_its_null_band():
    rng = np.random.default_rng(4)
    strengths = {f"p{k}": 1.26**k for k in range(5)}  # ~40 Elo apart
    counts = bt_counts(rng, strengths, games=500)
    ratings = rate(counts, anchor="p0").ratings
    fraction, _ = intransitive_triples(counts)
    lo, hi = cycle_null_band(counts, ratings, B=200, seed=1)
    assert lo <= fraction <= hi


def test_alphastar_proxy_takes_the_min_not_the_mean():
    """r2 beats the oldest rung 0.9 but loses 0.3 to the middle one — the
    forgetting signature. The min reports 0.3; a mean over earlier selves
    would report 0.6 and average the signature away."""
    counts = {
        ("r1", "r0"): (40, 0, 10), ("r0", "r1"): (10, 0, 40),
        ("r2", "r0"): (45, 0, 5), ("r0", "r2"): (5, 0, 45),
        ("r2", "r1"): (15, 0, 35), ("r1", "r2"): (35, 0, 15),
    }
    mean, mins = alphastar_proxy(counts, ["r0", "r1", "r2"])
    assert mins == pytest.approx([0.8, 0.3])
    assert mean == pytest.approx(0.55)


def test_alphastar_proxy_draws_count_half():
    """30/40/30 one colour only: score (30 + 20)/100 = 0.5 exactly.
    Dropping the draw term from the numerator would read 0.3."""
    mean, mins = alphastar_proxy({("r1", "r0"): (30, 40, 30)}, ["r0", "r1"])
    assert mins == pytest.approx([0.5])
    assert mean == pytest.approx(0.5)


def test_regression_rate_counts_majority_losses_only():
    """Three pairs: one exact tie (no regression), one majority loss to an
    earlier self (regression), one majority win. Rate = 1/3."""
    counts = {
        ("r1", "r0"): (25, 0, 25),   # tie
        ("r2", "r0"): (20, 0, 30),   # the later rung loses the majority
        ("r2", "r1"): (30, 0, 20),
    }
    assert regression_rate(counts, ["r0", "r1", "r2"]) == pytest.approx(1 / 3)


def test_regression_null_band_sorts_ratings_into_the_monotone_null():
    """The null's content is the monotone REARRANGEMENT: which rung holds
    which rating must not matter, only the multiset — so a run whose fitted
    ladder dips (genuine forgetting) is banded against the monotone learner
    it could have been, not against its own dip."""
    counts = {(f"r{i}", f"r{j}"): (250, 0, 250) for i in range(4) for j in range(i)}
    rungs = [f"r{i}" for i in range(4)]
    dipped = {"r0": 0.0, "r1": 300.0, "r2": -200.0, "r3": 150.0}
    ordered = {"r0": -200.0, "r1": 0.0, "r2": 150.0, "r3": 300.0}
    assert (regression_null_band(counts, dipped, rungs, B=100, seed=0)
            == regression_null_band(counts, ordered, rungs, B=100, seed=0))


def test_regression_null_band_semantics_on_flat_and_separated_ladders():
    """A well-separated monotone ladder leaves noise no room: the band
    pins to zero. A flat ladder (a run that never learns) makes every
    pair a coin flip, so ~50% regression sits INSIDE the band — the case
    the bare rate misreads as the worst forgetter (PLAN.md 47.8%)."""
    rungs = [f"r{i}" for i in range(6)]
    counts = {(f"r{i}", f"r{j}"): (250, 0, 250) for i in range(6) for j in range(i)}
    separated = {name: 400.0 * i for i, name in enumerate(rungs)}
    assert regression_null_band(counts, separated, rungs, B=100, seed=0) == (0.0, 0.0)
    flat = {name: 0.0 for name in rungs}
    lo, hi = regression_null_band(counts, flat, rungs, B=100, seed=0)
    assert lo < 0.5 < hi

"""Bradley-Terry ratings for the chunk-3 tournament (Phase 4).

Input is the tournament's raw material: a dict mapping `(first, second)`
player-name pairs — first player listed first, so each key is one COLOUR
of one matchup — to `(first_wins, draws, second_wins)` counts. Draws count
half a win each (the locked convention), which the score matrix absorbs so
the MM update never sees them specially.

Everything here follows Hunter (2004) and the locked spec, and the guards
exist because the failure modes are quiet:

- **Ford's condition (Assumption 1) is checked before every fit, and it is
  necessary, not merely sufficient** (Hunter Lemma 1(a)): without it the
  MLE does not exist. An undefeated player does not diverge to inf in a
  way a test would notice — it creeps at a constant ~372 Elo per decade of
  iterations while the step size decays like 1/k, so a successive-
  difference convergence test reads it as slow convergence and returns a
  finite, wrong, tolerance-dependent number. Hence `fit_bt` REFUSES a
  non-Ford matrix, and the committed test asserts stability across
  iteration counts (200/2k/20k), never finiteness.

- **Perfect scorers are dropped iteratively and reported with a
  floor/ceiling** (Ordo's approach) rather than smoothed away: the locked
  spec rejects pseudo-count priors outright (if one is ever wanted it is
  phantom-player rho, named explicitly — "half a virtual win and loss" is
  ambiguous by a factor of J between Glickman's two readings). Dropping
  is iterative because removing the top player can make the next one
  undefeated among the remainder.

- **The bootstrap is stratified by (pair, colour)** — each input cell is
  resampled as its own multinomial with its total fixed, preserving the
  campaign's exact colour balance; an i.i.d. bootstrap over pooled games
  destroys that balance and reports sd 0.021 where the truth is 0
  (measured, PLAN.md). Resamples that fail the fit's preconditions
  (anchor dropped, Ford violated) are FLAGGED AND SKIPPED, never fitted
  anyway — Hunter p. 402's trap: at B = 1000 assume at least one resample
  violates Assumption 1.

Ratings are Elo-scaled log-strengths, `400/ln(10) * log p`, reported
relative to a caller-named anchor (the tournament anchors `alphabeta2`
at 0).
"""

import math
from dataclasses import dataclass

import numpy as np

ELO_PER_LOG = 400.0 / math.log(10.0)

Counts = "dict[tuple[str, str], tuple[int, int, int]]"


def _score_matrix(counts, players: list[str]) -> np.ndarray:
    """S[i, j] = i's score against j, both colours pooled, draws as 0.5.
    Colour itself carries no BT term — the tournament alternates first
    player exactly N/2 each way, so seat advantage cancels by design."""
    index = {name: i for i, name in enumerate(players)}
    S = np.zeros((len(players), len(players)))
    for (first, second), (first_wins, draws, second_wins) in counts.items():
        i, j = index[first], index[second]
        S[i, j] += first_wins + 0.5 * draws
        S[j, i] += second_wins + 0.5 * draws
    return S


def ford_connected(S: np.ndarray) -> bool:
    """Assumption 1: the digraph with an edge i -> j wherever S[i, j] > 0
    is strongly connected — for every split of the players into two
    nonempty groups, someone in each scored against someone in the other.
    Strong connectivity via reachability from node 0 in the graph and its
    transpose."""
    n = len(S)
    if n <= 1:
        return True
    positive = S > 0

    def reaches_all(adj) -> bool:
        seen = {0}
        frontier = [0]
        while frontier:
            for j in np.flatnonzero(adj[frontier.pop()]):
                if int(j) not in seen:
                    seen.add(int(j))
                    frontier.append(int(j))
        return len(seen) == n

    return reaches_all(positive) and reaches_all(positive.T)


def drop_perfect_scorers(
    S: np.ndarray, players: list[str]
) -> "tuple[list[int], list[str], list[str]]":
    """Indices to keep, plus the dropped names: ceiling = nobody scored
    against them (undefeated, not even a draw), floor = they scored against
    nobody. Iterative on purpose — removing an undefeated player can leave
    the next one undefeated among the remainder."""
    kept = list(range(len(players)))
    floored: list[str] = []
    ceilinged: list[str] = []
    while True:
        sub = S[np.ix_(kept, kept)]
        scored = sub.sum(axis=1)
        conceded = sub.sum(axis=0)
        drop = [
            (i, ceilinged if conceded[k] == 0 else floored)
            for k, i in enumerate(kept)
            if scored[k] == 0 or conceded[k] == 0
        ]
        if not drop:
            return kept, floored, ceilinged
        for i, bucket in drop:
            bucket.append(players[i])
            kept.remove(i)


def fit_bt(S: np.ndarray, iterations: int = 2000) -> np.ndarray:
    """Log-strengths by Hunter's MM: p_i <- W_i / sum_j N_ij / (p_i + p_j).
    Order-independent by construction (every player updates from the same
    frozen iterate). Runs exactly `iterations` steps — convergence for
    Ford-connected matrices is what the 200/2k/20k stability test pins,
    and non-Ford matrices are refused here rather than trusted to any
    stopping rule (see the module docstring for why a tolerance cannot
    detect the creep)."""
    if not ford_connected(S):
        raise ValueError("score matrix violates Ford's condition; no BT MLE exists")
    N = S + S.T
    W = S.sum(axis=1)
    p = np.ones(len(S))
    for _ in range(iterations):
        P = p[:, None] + p[None, :]
        p = W / (N / P).sum(axis=1)
        p /= np.exp(np.log(p).mean())  # rescale only: MM is scale-invariant
    return np.log(p)


@dataclass
class EloResult:
    ratings: "dict[str, float]"  # anchor at exactly 0.0
    floored: "list[str]"  # dropped: scored nothing; below every rated player
    ceilinged: "list[str]"  # dropped: conceded nothing; above every rated player


def rate(counts, anchor: str, iterations: int = 2000) -> EloResult:
    """Fit every player named in `counts`, anchored at `anchor` = 0."""
    players = sorted({name for pair in counts for name in pair})
    for pair, cell in counts.items():
        if sum(cell) == 0:
            raise ValueError(f"pair {pair} has zero games")
    S = _score_matrix(counts, players)
    kept, floored, ceilinged = drop_perfect_scorers(S, players)
    if anchor not in (players[i] for i in kept):
        raise ValueError(f"anchor {anchor!r} is missing or was dropped "
                         f"(floored {floored}, ceilinged {ceilinged})")
    kept_names = [players[i] for i in kept]
    log_p = fit_bt(S[np.ix_(kept, kept)], iterations)
    elo = ELO_PER_LOG * (log_p - log_p[kept_names.index(anchor)])
    return EloResult(dict(zip(kept_names, map(float, elo))), floored, ceilinged)


@dataclass
class BootstrapResult:
    intervals: "dict[str, tuple[float, float]]"  # 2.5/97.5 percentile
    rated_in: "dict[str, int]"  # resamples in which the player was rated
    failed: int  # resamples skipped: anchor dropped or Ford violated


def bootstrap(counts, anchor: str, B: int = 1000, seed: int = 0,
              iterations: int = 2000) -> BootstrapResult:
    """Seeded stratified bootstrap: every (pair, colour) cell is resampled
    as its own multinomial, then refitted with the full `rate` pipeline —
    including the drop and Ford guards, whose failures are counted in
    `failed` (or, for a single dropped non-anchor player, in a reduced
    `rated_in`) instead of ever fitting anyway."""
    rng = np.random.default_rng(seed)
    samples: "dict[str, list[float]]" = {}
    failed = 0
    for _ in range(B):
        resampled = {
            pair: tuple(rng.multinomial(sum(cell), np.asarray(cell) / sum(cell)))
            for pair, cell in counts.items()
        }
        try:
            result = rate(resampled, anchor, iterations)
        except ValueError:
            failed += 1
            continue
        for name, value in result.ratings.items():
            samples.setdefault(name, []).append(value)
    intervals = {
        name: (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))
        for name, values in samples.items()
    }
    return BootstrapResult(intervals, {n: len(v) for n, v in samples.items()}, failed)


def _majority_sign(counts, players: list[str]) -> np.ndarray:
    """sign(S_ij - S_ji) per pair. Draws cancel out of the difference, so
    only decisive games move a pairwise direction."""
    S = _score_matrix(counts, players)
    return np.sign(S - S.T)


def intransitive_triples(counts) -> "tuple[float, int]":
    """Fraction of player triples whose pairwise majority directions form
    a cycle (i beats j beats k beats i), over all C(n, 3) triples. A tied
    pair (equal scores) breaks any would-be cycle and counts transitive.
    The BARE fraction is not evidence of cycling — sampling noise on an
    acyclic ground truth yields 7.2-7.7% spurious cycles at the ~40-Elo
    ladder spans late training produces (PLAN.md) — which is why
    `cycle_null_band` exists and the two are only ever reported together.
    """
    players = sorted({name for pair in counts for name in pair})
    sign = _majority_sign(counts, players)
    n = len(players)
    cycles = total = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                total += 1
                if (sign[i, j] == sign[j, k] == sign[k, i] != 0):
                    cycles += 1
    return (cycles / total if total else 0.0), total


def _pooled_winrate(counts, a: str, b: str) -> float:
    """a's score against b, both colours pooled, draws 0.5 — the same
    convention as `_score_matrix`, for a single pair addressed by name."""
    a_wins, draws_ab, a_losses = counts.get((a, b), (0, 0, 0))
    b_wins, draws_ba, b_losses = counts.get((b, a), (0, 0, 0))
    games = a_wins + draws_ab + a_losses + b_wins + draws_ba + b_losses
    return (a_wins + b_losses + 0.5 * (draws_ab + draws_ba)) / games


def alphastar_proxy(counts, rungs: "list[str]") -> "tuple[float, list[float]]":
    """AlphaStar's published forgetting proxy (Nature 2019 Fig. 3C/D):
    each rung's MINIMUM pooled win rate against any earlier rung,
    averaged over rungs. `rungs` must be in training order — the
    "earlier" in min_{j<i} is temporal, and a mis-ordered list silently
    measures a different quantity. The min, not a mean, is the point:
    forgetting is losing to SOME earlier self while beating the rest,
    and a mean over earlier selves averages the signature away.

    This is the PRIMARY forgetting measure (locked spec): unlike the
    regression rate it does not read a never-learns run as the worst
    forgetter, because a flat ladder's minima sit near 0.5, not 0.
    Returns (mean, per-rung minima for rungs[1:]).
    """
    mins = [
        min(_pooled_winrate(counts, rungs[i], rungs[j]) for j in range(i))
        for i in range(1, len(rungs))
    ]
    return float(np.mean(mins)), mins


def regression_rate(counts, rungs: "list[str]") -> float:
    """Fraction of ordered rung pairs (earlier, later) where the later
    checkpoint loses the pooled pairwise majority to the earlier one
    (score < 0.5; an exact tie is no regression). SECONDARY measure,
    meaningless bare: a run that never learns reads ~48% because every
    pair is a coin flip — worse than genuine forgetting's ~14% (PLAN.md)
    — so it is only ever reported against `regression_null_band`."""
    pairs = [(i, j) for i in range(1, len(rungs)) for j in range(i)]
    regressed = sum(
        _pooled_winrate(counts, rungs[i], rungs[j]) < 0.5 for i, j in pairs
    )
    return regressed / len(pairs)


def regression_null_band(counts, ratings: "dict[str, float]",
                         rungs: "list[str]", B: int = 200,
                         seed: int = 0) -> "tuple[float, float]":
    """2.5/97.5 percentile band of `regression_rate` under the
    ZERO-FORGETTING null: the run's own fitted rung ratings reassigned to
    the rungs in ascending order over training steps — the same strength
    multiset, monotone by construction — then every rung pair resimulated
    as binomial wins at the BT-implied probability over its actual
    DECISIVE game count (draws cannot move a pairwise majority, exactly
    as in `cycle_null_band`). The rearrangement is the null's content: a
    never-learns run has a flat ladder whose rearrangement is equally
    flat, so its ~48% observed rate lands INSIDE the band and is
    correctly not read as forgetting, while a genuinely regressing ladder
    is compared against the monotone learner it could have been."""
    elo = np.sort(np.array([ratings[r] for r in rungs]))
    pairs = [(i, j) for i in range(1, len(rungs)) for j in range(i)]
    decisive = {}
    for i, j in pairs:
        fw1, _, sw1 = counts.get((rungs[i], rungs[j]), (0, 0, 0))
        fw2, _, sw2 = counts.get((rungs[j], rungs[i]), (0, 0, 0))
        decisive[(i, j)] = fw1 + sw1 + fw2 + sw2
    rng = np.random.default_rng(seed)
    fractions = []
    for _ in range(B):
        regressed = sum(
            int(rng.binomial(n, 1.0 / (1.0 + 10.0 ** ((elo[j] - elo[i]) / 400.0)))) * 2 < n
            for (i, j), n in decisive.items()
        )
        fractions.append(regressed / len(pairs))
    return float(np.percentile(fractions, 2.5)), float(np.percentile(fractions, 97.5))


def cycle_null_band(counts, ratings: "dict[str, float]", B: int = 200,
                    seed: int = 0) -> "tuple[float, float]":
    """2.5/97.5 percentile band of the triple fraction under the ACYCLIC
    null: tournaments resimulated from the fitted (transitive by
    construction) BT ratings, each pair getting binomial wins at its
    BT-implied probability over its actual DECISIVE game count — draws do
    not move a majority sign, so simulating them would only dilute the
    noise the band is supposed to capture. Only rated players enter the
    band (a floored/ceilinged player has no rating to simulate from); the
    caller compares against the triple fraction of the same subset."""
    players = sorted(ratings)
    index = {name: i for i, name in enumerate(players)}
    decisive = np.zeros((len(players), len(players)))
    for (first, second), (first_wins, _, second_wins) in counts.items():
        if first in index and second in index:
            i, j = index[first], index[second]
            decisive[i, j] += first_wins + second_wins
            decisive[j, i] += first_wins + second_wins
    rng = np.random.default_rng(seed)
    elo = np.array([ratings[name] for name in players])
    p_win = 1.0 / (1.0 + 10.0 ** ((elo[None, :] - elo[:, None]) / 400.0))
    fractions = []
    for _ in range(B):
        sim = {}
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                n_games = int(decisive[i, j])
                wins = int(rng.binomial(n_games, p_win[i, j])) if n_games else 0
                sim[(players[i], players[j])] = (wins, 0, n_games - wins)
        fractions.append(intransitive_triples(sim)[0])
    return float(np.percentile(fractions, 2.5)), float(np.percentile(fractions, 97.5))

"""Opponents for the learner-centric Connect 4 env.

The `Opponent` interface has three methods, and each exists for a reason the
capstone will need:

- `select(rng) -> Opponent` picks who actually plays this episode. A fixed
  opponent returns itself; the chunk-2 snapshot pool draws a member. Because
  selection is a method rather than mutable state, ONE pool object can be
  shared by all N sub-envs without any shared mutable state between them —
  which is the whole reason the pool is passed as a caller kwarg to
  `gym.make` rather than registered (registered kwargs get deepcopied per
  sub-env, silently giving each its own private pool).

- `move(obs, mask, rng) -> int` plays one ply. It receives the observation
  already canonicalized to the OPPONENT's own perspective, so an opponent
  never needs to know which seat it occupies — the same egocentric contract
  the learner gets.

- `freeze()` is the no-training contract. It is a no-op for the rule-based
  opponents here, and is declared now on purpose: chunk 2's `AgentOpponent`
  wraps a network snapshot, and a snapshot that kept training would silently
  track the learner instead of standing still — the failure the whole
  historical-opponent pool exists to prevent. Whoever INSTALLS an opponent
  calls `freeze()` (the env at construction, the pool at push), so a
  trainable opponent cannot be installed unfrozen by forgetting a call at
  one of several sites. Implementations must put modules in eval mode, drop
  gradients, and update no running statistics.

A note on why `move` takes an observation rather than a board: it makes the
opponent's perspective testable. `RandomOpponent` ignores `obs` entirely,
which is exactly why a "beats random >=90%" gate could not detect a wrong
opponent perspective — 50 games came out bit-identical (PLAN.md). The
heuristic reads the planes, so it does detect one.
"""

from abc import ABC, abstractmethod

import numpy as np

from rl.envs.connect4 import CELLS, Connect4Board
from rl.selfplay.solver import MOVE_ORDER, Bitboard


class Opponent(ABC):
    """A frozen policy the learner plays against. See the module docstring."""

    def select(self, rng: np.random.Generator) -> "Opponent":
        """Which opponent plays this episode. Drawn per episode, never
        mid-game: an opponent that changed identity between plies would make
        the episode incoherent."""
        return self

    @abstractmethod
    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        """One ply. `obs` is bool [2, 6, 7] from THIS opponent's perspective
        (plane 0 its own discs), `mask` bool [7] with True = legal. Must
        return a legal column."""

    def freeze(self) -> None:
        """Enter no-training mode. No-op for rule-based opponents."""

    def report(self, played: "Opponent", outcome: int) -> None:
        """The env reports how an episode ended: `played` is the opponent
        `select()` returned for it, `outcome` the LEARNER's result
        (+1/0/-1). No-op everywhere except the snapshot pool, whose PFSP
        weighting is the one consumer — the env is the only place that
        knows both who played and who won, which is why the hook lives on
        the source rather than in the training loop."""


def board_from_obs(obs: np.ndarray) -> np.ndarray:
    """Egocentric planes -> a canonical int8 board (+1 = the viewer, who is
    the player to move). The inverse of `Connect4Board.planes()`."""
    return obs[0].astype(np.int8) - obs[1].astype(np.int8)


def _wins_immediately(board: np.ndarray, col: int) -> bool:
    """Would the player to move win by playing `col`? Works on a copy: drop()
    mutates and negates."""
    return Connect4Board(board.copy()).drop(col)


class RandomOpponent(Opponent):
    """Uniform over legal columns.

    Deliberately ignores `obs`. That makes it the weakest possible probe of
    the env's opponent-perspective plumbing — which is a fact to design
    around, not a defect: it is why the chunk gate is the fixture probes and
    not a win rate against this opponent.
    """

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        return int(rng.choice(np.flatnonzero(mask)))


class HeuristicOpponent(Opponent):
    """Win in one if available, else block the opponent's win in one, else
    uniform over legal columns.

    The random fallback is load-bearing rather than a leftover: it fires on
    the large majority of positions regardless of learner strength, and it is
    what keeps a fixed-opponent eval set diverse. Without it a deterministic
    anchor collapses N eval episodes into a couple of distinct games, which
    `eval/return_std > 0` exists to detect.
    """

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        board = board_from_obs(obs)
        legal = np.flatnonzero(mask)
        for col in legal:
            if _wins_immediately(board, int(col)):
                return int(col)
        # Block: negating the board makes the OTHER player the one to move,
        # so the same win-in-one test answers "could they win here next?".
        threat_board = -board
        for col in legal:
            if _wins_immediately(threat_board, int(col)):
                return int(col)
        return int(rng.choice(legal))


def _limited(bb: Bitboard, depth: int, alpha: int, beta: int) -> int:
    """Negamax to `depth` plies with 0 at the horizon. Solver-convention
    scores for wins found in range, so nearer wins score higher. The win
    scan runs BEFORE the horizon check — that ordering is what gives depth
    d vision of all wins and losses within d plies (a horizon node still
    reports the win sitting on it); moving the check first silently turns
    depth 2 into depth 1. 0 conflates "draw" with "nothing tactical in
    range" on purpose: the anchor makes no positional guess."""
    if bb.moves == CELLS:
        return 0
    for col in MOVE_ORDER:
        if bb.can_play(col) and bb.is_winning_move(col):
            return (CELLS + 1 - bb.moves) // 2
    if depth <= 1:
        return 0
    best = -CELLS
    for col in MOVE_ORDER:
        if not bb.can_play(col):
            continue
        value = -_limited(bb.play(col), depth - 1, -beta, -alpha)
        if value > best:
            best = value
            if value > alpha:
                alpha = value
        if alpha >= beta:
            break
    return best


def alphabeta_move_scores(bb: Bitboard, depth: int) -> dict[int, int]:
    """Score every legal move at fixed lookahead, each with its own FULL
    window: threading a rising alpha across root moves would let later
    moves fail low below their true value and drop out of the tie set by
    column order — and the uniform tie-break needs TRUE ties (module-level
    so tests and the tournament can rank moves without an Opponent)."""
    scores = {}
    for col in MOVE_ORDER:
        if not bb.can_play(col):
            continue
        if bb.is_winning_move(col):
            scores[col] = (CELLS + 1 - bb.moves) // 2
        else:
            scores[col] = -_limited(bb.play(col), depth - 1, -(CELLS // 2), CELLS // 2)
    return scores


class AlphaBetaOpponent(Opponent):
    """Fixed-depth alpha-beta anchor with uniform random tie-breaking.

    The horizon evaluation is 0 — purely tactical, no positional guess —
    so the anchor's strength is a function of depth alone and stays
    reproducible. That leaves genuine ties on most early positions, and
    the random tie-break turns them into eval-set diversity: measured
    89/100 distinct eval games with it, 2/100 without (PLAN.md), which is
    what `eval/return_std > 0` exists to detect. The draw comes from the
    rng the env hands in, same as the heuristic's fallback.
    """

    def __init__(self, depth: int):
        if depth < 1:
            raise ValueError(f"depth must be >= 1, got {depth}")
        self.depth = depth

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        bb = Bitboard.from_board(Connect4Board(board_from_obs(obs)))
        scores = alphabeta_move_scores(bb, self.depth)
        best = max(scores.values())
        return int(rng.choice([c for c, s in sorted(scores.items()) if s == best]))


def play_game(
    first: Opponent,
    second: Opponent,
    rng: np.random.Generator,
    start: Connect4Board | None = None,
    moves: "list[int] | None" = None,
) -> int:
    """One game between two opponents on a raw board, no env: +1 if
    `first` (the first player) wins, 0 a draw, -1 if `second` wins.

    Each side is queried exactly as the env queries its opponent —
    `select()` once at the start (the per-episode swap boundary), then
    `move()` on the board canonicalized to ITS perspective, which the
    canonical board gives for free since `planes()` always renders the
    mover's view. Win is checked before full: the 42nd disc can complete
    a line here just as it can in `Connect4Env.step()`. Committed as the
    tournament's game runner so the chunk-4 coverage diagnostic can reuse
    it rather than being rebuilt from session scratch.

    `start` continues the game from a mid-game position instead of an
    empty board (the value-MSE probe's continuation targets need this);
    the board is canonical, so `first` is the player to move at `start`,
    and the outcome sign is from that player's perspective. Played on a
    copy — the caller's board is never mutated. `moves`, if given, has
    every played column appended in order (the coverage probe compares
    move sequences, and the outcome alone cannot distinguish two games).
    """
    players = (first.select(rng), second.select(rng))
    board = Connect4Board() if start is None else start.copy()
    mover = 0
    while True:
        col = players[mover].move(board.planes(), board.legal_mask(), rng)
        if moves is not None:
            moves.append(int(col))
        won = board.drop(int(col))
        if won:
            return 1 if mover == 0 else -1
        if board.full():
            return 0
        mover = 1 - mover


# Name -> factory, so a config can say `opponent: heuristic`. The alpha-beta
# anchors are fixed at depths 2 and 4 (the tournament's ladder anchors);
# chunk 2's pool is passed as an object, not a name.
OPPONENTS = {
    "random": RandomOpponent,
    "heuristic": HeuristicOpponent,
    "alphabeta2": lambda: AlphaBetaOpponent(2),
    "alphabeta4": lambda: AlphaBetaOpponent(4),
}


def make_opponent(spec: "str | Opponent") -> Opponent:
    """Resolve a config string to an opponent, or pass an object through."""
    if isinstance(spec, Opponent):
        return spec
    if spec not in OPPONENTS:
        raise ValueError(f"unknown opponent {spec!r}; known: {sorted(OPPONENTS)}")
    return OPPONENTS[spec]()

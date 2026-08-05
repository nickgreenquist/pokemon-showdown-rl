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


# Name -> factory, so a config can say `opponent: heuristic`. The pool is
# passed as an object, not a name. (The predecessor's alpha-beta anchors were
# pruned with the Connect 4 study, 2026-08-05.)
OPPONENTS = {
    "random": RandomOpponent,
    "heuristic": HeuristicOpponent,
}


def make_opponent(spec: "str | Opponent") -> Opponent:
    """Resolve a config string to an opponent, or pass an object through."""
    if isinstance(spec, Opponent):
        return spec
    if spec not in OPPONENTS:
        raise ValueError(f"unknown opponent {spec!r}; known: {sorted(OPPONENTS)}")
    return OPPONENTS[spec]()

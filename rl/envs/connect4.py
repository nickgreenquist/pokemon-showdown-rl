"""Connect 4: the Phase 4 self-play on-ramp env.

Two objects, deliberately separated:

- `Connect4Board` — pure NumPy game logic, no gymnasium. Testable against the
  `open_spiel` oracle and (Phase 4 chunk 3) against a negamax solver without
  dragging in a Box/Discrete space. NumPy is the right representation *here*
  because the observation is a pair of 6x7 planes; it is the wrong one for
  search, so the chunk-3 solver uses a Python-int bitboard instead and the
  two cross-check each other (measured: NumPy 351k nodes/s vs the bitboard's
  894k — NumPy is the slowest of the three representations tried).
- `Connect4Env` — a learner-centric single-agent view of a two-player game,
  with the frozen opponent living inside. See its docstring.

Two conventions are stated loudly because getting either wrong produces tests
that pass while the game is broken:

- **Row 0 is the BOTTOM row.** Discs stack upward from row 0. An inverted
  convention makes every diagonal test pass while the real diagonals are
  mirrored, because the board is symmetric under a vertical flip but the
  diagonals are not.
- **The board is CANONICAL: +1 is always the player to move**, -1 the other
  player, 0 empty. `drop()` negates the whole board after placing a disc, so
  the mover is +1 again for the next ply. Nothing in this file needs to know
  who "red" or "yellow" is, which is exactly what makes the observation
  egocentric for free — and what makes the perspective bugs in
  `Connect4Env` possible, so read that docstring too.
"""

import gymnasium as gym
import numpy as np

ROWS, COLS = 6, 7
CONNECT = 4
CELLS = ROWS * COLS
# Half-directions through a placed disc: horizontal, vertical, and the two
# diagonals. Each is scanned both ways, so four entries cover all eight rays.
_DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


class Connect4Board:
    """Canonical Connect 4 position: `board[row, col]`, row 0 = bottom,
    +1 = player to move.

    Height is derived from the board rather than cached: discs stack with no
    gaps, so a column's height is just its nonzero count, and a derived value
    cannot desynchronize from the position it describes.
    """

    def __init__(self, board: np.ndarray | None = None, moves: int = 0):
        self.board = np.zeros((ROWS, COLS), dtype=np.int8) if board is None else board
        self.moves = moves

    def copy(self) -> "Connect4Board":
        return Connect4Board(self.board.copy(), self.moves)

    def legal_mask(self) -> np.ndarray:
        """bool [COLS], True = playable. A column is playable iff its TOP cell
        is empty. Freshly allocated: callers put this in `info` and the env
        contract forbids handing out views of internal state."""
        return self.board[ROWS - 1] == 0

    def height(self, col: int) -> int:
        return int(np.count_nonzero(self.board[:, col]))

    def full(self) -> bool:
        return self.moves == CELLS

    def drop(self, col: int) -> bool:
        """Play the mover's disc in `col`; return True if that move won.

        The win check runs BEFORE the negation, against +1 — the player who
        just moved. After the negation the mover is +1 again, so the returned
        flag is the only record of who won, and `Connect4Env` must consume it
        immediately.
        """
        row = self.height(col)
        if row >= ROWS:
            raise ValueError(f"column {col} is full")
        self.board[row, col] = 1
        won = self._is_win(row, col)
        self.board *= -1
        self.moves += 1
        return won

    def _is_win(self, row: int, col: int) -> bool:
        """Does the +1 disc at (row, col) complete a line of CONNECT?"""
        for dr, dc in _DIRECTIONS:
            count = 1
            for sign in (1, -1):
                r, c = row + sign * dr, col + sign * dc
                while 0 <= r < ROWS and 0 <= c < COLS and self.board[r, c] == 1:
                    count += 1
                    r += sign * dr
                    c += sign * dc
            if count >= CONNECT:
                return True
        return False

    def planes(self) -> np.ndarray:
        """Egocentric observation: bool [2, ROWS, COLS] — plane 0 the mover's
        discs, plane 1 the opponent's. Freshly allocated by np.stack (the env
        contract: never a view of `self.board`).

        No turn-indicator plane. First-player identity is recoverable from the
        plane sums (the mover has played either as many discs as the opponent
        or one fewer), and no reference carries one: alpha-zero-general uses 1
        canonical plane, PettingZoo 2, open_spiel 3 absolute.
        """
        return np.stack([self.board == 1, self.board == -1])

    def render(self) -> str:
        """Human-readable, printed TOP row first (open_spiel's `ToString` does
        the same). Debug aid only — never compare renderings in a test, and
        never use one to check the row convention: that is precisely the
        comparison that hides a flipped board.
        """
        glyphs = {1: "x", -1: "o", 0: "."}
        return "\n".join(
            "".join(glyphs[int(v)] for v in self.board[row]) for row in reversed(range(ROWS))
        )


class Connect4Env(gym.Env):
    """Connect 4 as a single-agent env: the learner is always the agent, and
    the frozen opponent lives INSIDE `step()` as part of the dynamics.

    One `step()` is therefore one full exchange — the learner's move and the
    opponent's reply — and the opponent's own transitions are never stored.
    That halves the data from a symmetric game, and the 2x is genuinely
    forfeited: collecting both sides is valid only under strict mirror
    self-play, which would forbid the historical-snapshot pool that is the
    entire point of Phase 4, and no published off-policy correction exists
    for the historical-opponent case. What it buys is that the classic
    perspective bug — storing P2's observations encoded from P1's view —
    cannot occur here, because P2's trajectory does not exist.

    **Perspective is the whole design.** `Connect4Board` is canonical (+1 is
    always the player to move) and `drop()` negates, so "the observation" is
    egocentric by construction and neither side needs to know its seat. There
    are four places a perspective can still go wrong, all probed in
    `tests/test_connect4.py`:

    1. the observation handed to the LEARNER;
    2. the observation handed to the FROZEN OPPONENT — the dangerous one,
       because under self-play both sides are the same network, so a wrong
       perspective here is symmetric and the loop cannot detect it;
    3. the sign of the reward on the opponent's reply;
    4. terminal `next_obs`, whose perspective flips with WHO ended the game:
       after the learner's winning move the board has already negated, so the
       final observation is from the opponent's side. This is left as-is and
       recorded rather than fixed. It is inert under PPO — `compute_gae`
       multiplies the bootstrap by `(1 - terminated)` and this env never
       truncates — but it does contradict `rollout.py`'s stated per-row
       invariant, so any future consumer that reads terminal `next_obs` for
       anything other than a zeroed bootstrap must revisit it.

    **Win-before-full ordering is load-bearing**: the 42nd disc can complete
    a line, so "board full -> draw" must be checked only AFTER "that move
    won", on both sides. A fixture pins the exact position.

    **Terminal states emit an all-True mask, not all-False.** All-False is
    the intuitive encoding and it is wrong: `rl/common/masking.py` asserts at
    least one legal action per row, and an all-False row reaches it through
    any consumer of `next_mask`. PPO happens to discard `next_masks`, so this
    was invisible in a probe (7 all-False masks over 4000 vector steps
    reached `act()` zero times) — but the DQN path provably does consume
    them, so the env must not emit a row that only one algorithm survives.

    `truncated` is always False: the game is bounded by 42 plies, so nothing
    ever cuts an episode early. Phase 5 is the opposite — poke-env sets
    `truncated=True` for forfeits, ties and timer losses — so the truncation
    path is exercised here with a `TimeLimit` wrapper in the tests rather
    than left dead until the capstone finds it.

    Transferability note for Phase 5: what carries over is the LEARNER-FACING
    contract (a 5-tuple, an opponent held as a plain policy object, a
    per-episode opponent draw), not the opponent's location. poke-env's
    `PokeEnv` is a two-seat PettingZoo `ParallelEnv` with no opponent
    parameter; the opponent enters one level up via `SingleAgentWrapper`.

    RNG: one stream (`self.np_random`) has three consumers, in this fixed
    order per episode — the first-player flip, `opponent.select()`, then any
    number of heuristic fallback draws. Nothing but this note and
    `test_rng_draw_order_is_pinned` fixes that order, and reordering it
    silently changes every seeded result.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(self, opponent="random", render_mode: str | None = None):
        # Deferred, and the deferral is structural rather than cosmetic:
        # HeuristicOpponent reuses Connect4Board's win detection (so the
        # heuristic and the env cannot disagree about what a win is), which
        # makes rl.selfplay.opponents depend on this module. Importing it at
        # module scope here would close the cycle and break both imports.
        from rl.selfplay.opponents import make_opponent

        self.action_space = gym.spaces.Discrete(COLS)
        # bool planes, MinAtar's own convention — which also makes rank-3 obs
        # select ConvQNet for both PPO heads by the existing no-config-key
        # rule, with no config change anywhere.
        self.observation_space = gym.spaces.Box(0, 1, (2, ROWS, COLS), dtype=bool)
        self.render_mode = render_mode
        # `opponent` may be a name from the config or a live object (chunk 2
        # passes the shared snapshot pool). Freezing at the INSTALL point is
        # the contract: a trainable opponent cannot slip in unfrozen because
        # some other call site forgot to freeze it.
        self.opponent_source = make_opponent(opponent)
        self.opponent_source.freeze()
        self.board = Connect4Board()
        self._opponent = self.opponent_source

    def _obs(self) -> np.ndarray:
        """Freshly allocated every call — never a view of the board, and
        never the same object twice, so `obs` and `next_obs` from one step
        cannot alias."""
        return self.board.planes()

    def _mask(self, terminated: bool) -> np.ndarray:
        return np.ones(COLS, dtype=bool) if terminated else self.board.legal_mask()

    def _opponent_move(self) -> bool:
        """Play the opponent's reply; return True if it won.

        The board has already been negated by the learner's `drop()`, so
        `planes()` here is canonicalized to the OPPONENT's perspective — site
        2 above. The legality check is loud on purpose: a silently-dropped
        illegal opponent move would look like a policy quirk, not a bug.
        """
        mask = self.board.legal_mask()
        col = int(self._opponent.move(self._obs(), mask, self.np_random))
        if not (0 <= col < COLS and mask[col]):
            raise ValueError(f"opponent chose illegal column {col} (mask {mask.tolist()})")
        return self.board.drop(col)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.board = Connect4Board()
        # Randomized first player: Connect 4 is a first-player win under
        # perfect play, so a fixed seat would make the task asymmetric and
        # the self-play equilibrium uninterpretable.
        learner_first = bool(self.np_random.integers(2))
        self._opponent = self.opponent_source.select(self.np_random)
        if not learner_first:
            self._opponent_move()
        return self._obs(), {"action_mask": self._mask(False)}

    def step(self, action):
        col = int(action)
        mask = self.board.legal_mask()
        if not (0 <= col < COLS and mask[col]):
            # Raise rather than penalize: a masked agent selecting an illegal
            # column means the masking contract broke somewhere upstream, and
            # a penalty would train around the bug instead of surfacing it.
            raise ValueError(f"illegal column {col} (mask {mask.tolist()})")
        outcome: int | None = None
        if self.board.drop(col):
            outcome = 1
        elif self.board.full():
            outcome = 0
        elif self._opponent_move():
            outcome = -1
        elif self.board.full():
            outcome = 0
        terminated = outcome is not None
        info = {"action_mask": self._mask(terminated)}
        if terminated:
            # The metric of record. `eval/win_rate` is derived from this and
            # NEVER from the sign of the return: measured, a flipped reward
            # sign makes a `return > 0` win rate read 1.000 and pass its own
            # detector at the ceiling.
            info["outcome"] = outcome
            # PFSP's feedback channel: only this env knows both which
            # opponent select() chose and how the episode ended. No-op on
            # every opponent except the snapshot pool.
            self.opponent_source.report(self._opponent, outcome)
        # Terminal-only reward, equal to the outcome: +1 win, -1 loss, 0 draw
        # or game continuing. Every reward is a delayed reward, which is why
        # the configs run gamma = 1.0.
        reward = float(outcome) if terminated else 0.0
        return self._obs(), reward, terminated, False, info

    def render(self):
        if self.render_mode == "ansi":
            return self.board.render()
        return None

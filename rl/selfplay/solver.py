"""Exact Connect 4 solver (Phase 4 chunk 3): bitboard, negamax, oracle.

Phase 4 has no published training curve to grade against, so absolute
strength comes from game-theoretic ground truth: this solver labels
positions, and the Pons benchmark sets corroborate it externally (PLAN.md).
Correctness of the solver itself comes from two differential tests, neither
of which trusts the other's representation:

- the bitboard is cross-checked ply-by-ply against `Connect4Board` — the
  NumPy board already validated against the open_spiel oracle in chunk 1,
  so agreement here chains this file to that oracle for free;
- the search is cross-checked against `brute_force`, a no-pruning no-TT
  no-ordering negamax kept deliberately dumb in this same file.

Why a second board representation at all: NumPy is the slowest of the three
tried for search (351k nodes/s vs 417k for a flat list and 894k for this
Python-int bitboard, PLAN.md) — scalar indexing loses, and nothing in a
negamax inner loop vectorizes. `Connect4Board` keeps its array because the
observation is a pair of planes; search wants machine words.

Bitboard layout (Pons' encoding): one bit per cell at index
`col * H1 + row`, row 0 = bottom — the same row convention as
`Connect4Board`, stated because an inverted convention makes every
diagonal shift wrong while vertical and horizontal tests still pass.
H1 = ROWS + 1: each column carries a SENTINEL bit above its top row,
always 0. The sentinel is what stops the shift-based line detection from
wrapping a column's top into the next column's bottom — the bitboard twin
of the numpy negative-index wrap that chunk 1 caught producing phantom
lines of four.

Two ints describe a position: `current` (the mover's stones) and `mask`
(all stones). The board is CANONICAL exactly like `Connect4Board`: current
is always the player to move, so `play()` hands the old opponent's stones
(`current ^ mask`) to the child as its `current`. `current + mask` is a
unique position key (the addition sets a bit above each column's stones,
which encodes whose they are).

Scores are Pons' convention throughout, because the benchmark labels and
the chunk-3/4 metrics (score regret) consume them directly: signed from
the player to move, 0 a draw, magnitude `22 - winner's stones` — so a win
with the winner's Nth stone scores 22 - N, and faster wins score higher.
The sign alone is the game-theoretic value.
"""

import numpy as np

from rl.envs.connect4 import CELLS, COLS, CONNECT, ROWS, Connect4Board

# The shift cascade in _alignment doubles pairs into fours; it is written
# for lines of exactly 4.
assert CONNECT == 4

H1 = ROWS + 1  # bits per column: ROWS cells + 1 sentinel
BOTTOM_MASK = tuple(1 << (col * H1) for col in range(COLS))
TOP_MASK = tuple(1 << (col * H1 + ROWS - 1) for col in range(COLS))
COLUMN_MASK = tuple(((1 << ROWS) - 1) << (col * H1) for col in range(COLS))


def _alignment(stones: int) -> bool:
    """Does `stones` (one player's discs) contain a line of four?

    Each direction: pairs first (`stones & stones >> d`), then pairs of
    pairs (`m & m >> 2d`) — four in a line iff both. Shift distances are
    the bit-index deltas of the layout: 1 vertical, H1 horizontal,
    H1+1 / H1-1 the two diagonals. The sentinel row keeps every shift
    from crossing a column boundary.
    """
    m = stones & (stones >> 1)  # vertical
    if m & (m >> 2):
        return True
    m = stones & (stones >> H1)  # horizontal
    if m & (m >> (2 * H1)):
        return True
    m = stones & (stones >> (H1 + 1))  # diagonal up-right
    if m & (m >> (2 * (H1 + 1))):
        return True
    m = stones & (stones >> (H1 - 1))  # diagonal up-left
    if m & (m >> (2 * (H1 - 1))):
        return True
    return False


class Bitboard:
    """Canonical Connect 4 position on two Python ints. Immutable style:
    `play()` returns a new Bitboard (Pons' reference solver also copies
    per node), so search never needs an undo path."""

    __slots__ = ("current", "mask", "moves")

    def __init__(self, current: int = 0, mask: int = 0, moves: int = 0):
        self.current = current
        self.mask = mask
        self.moves = moves

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Bitboard)
            and self.current == other.current
            and self.mask == other.mask
            and self.moves == other.moves
        )

    def __repr__(self) -> str:
        return f"Bitboard(current={self.current:#x}, mask={self.mask:#x}, moves={self.moves})"

    def key(self) -> int:
        return self.current + self.mask

    def can_play(self, col: int) -> bool:
        return not self.mask & TOP_MASK[col]

    def _stone(self, col: int) -> int:
        """The bit the next disc in `col` would occupy: adding the column's
        bottom bit to `mask` carries up through its stones to the first
        empty cell."""
        return (self.mask + BOTTOM_MASK[col]) & COLUMN_MASK[col]

    def is_winning_move(self, col: int) -> bool:
        """Would the MOVER win by playing `col`? `col` must be playable."""
        return _alignment(self.current | self._stone(col))

    def play(self, col: int) -> "Bitboard":
        """Play `col` (must be playable) and return the child position.
        The child's `current` is the old opponent's stones — the negation
        `Connect4Board.drop()` does with `board *= -1`, done here by
        handing over `current ^ mask` (the new stone stays out of it)."""
        return Bitboard(
            self.current ^ self.mask, self.mask | self._stone(col), self.moves + 1
        )

    @classmethod
    def from_board(cls, board: Connect4Board) -> "Bitboard":
        """`Connect4Board` -> Bitboard, same canonical perspective (+1 = the
        mover = `current`). `moves` is derived from the array rather than
        trusted from the attribute, matching the board's own derive-don't-
        cache rule: a board built from a raw array defaults `moves=0`."""
        current = mask = 0
        for col in range(COLS):
            for row in range(ROWS):
                v = board.board[row, col]
                if v:
                    bit = 1 << (col * H1 + row)
                    mask |= bit
                    if v == 1:
                        current |= bit
        return cls(current, mask, int(np.count_nonzero(board.board)))

    def to_board(self) -> Connect4Board:
        arr = np.zeros((ROWS, COLS), dtype=np.int8)
        for col in range(COLS):
            for row in range(ROWS):
                bit = 1 << (col * H1 + row)
                if self.current & bit:
                    arr[row, col] = 1
                elif self.mask & bit:
                    arr[row, col] = -1
        return Connect4Board(arr, self.moves)


# Centre-first: columns by distance from the middle. Any complete order is
# correct (a permutation must survive mutation testing as an equivalence
# control); centre-first is the one that prunes well on this game.
MOVE_ORDER = (3, 2, 4, 1, 5, 0, 6)

# Transposition-table flags. EXACT is a true minimax value; LOWER/UPPER are
# fail-soft bounds from a search that cut off. The flag is load-bearing:
# storing bounds as exact values corrupts 0.13-0.40% of results with the
# error rate RISING with depth, and the Pons labels structurally cannot see
# it (they are root values; the corruption shows in interior nodes first) —
# which is why the differential oracle below exists (PLAN.md).
EXACT, LOWER, UPPER = 1, 2, 3

# ~1M entries. Bounding the table is required, not an optimization: unbounded
# it reached 141 MB RSS on a single Middle-Medium position (PLAN.md).
TT_SIZE = 1048573  # prime, so key % size spreads


class TranspositionTable:
    """Fixed-size, replace-on-collision (Pons' policy). One Python int per
    entry — `key << 8 | (value + 21) << 2 | flag` — instead of a tuple,
    which at ~1M entries is the difference between ~40 MB and ~120 MB.
    0 means empty (a real entry always has a nonzero flag). The full key is
    stored and checked on probe, so an index collision evicts, never lies.
    """

    def __init__(self, size: int = TT_SIZE):
        self.size = size
        self.entries = [0] * size

    def get(self, key: int) -> "tuple[int, int] | None":
        entry = self.entries[key % self.size]
        if entry and entry >> 8 == key:
            return ((entry >> 2) & 0x3F) - 21, entry & 0x3
        return None

    def put(self, key: int, value: int, flag: int) -> None:
        self.entries[key % self.size] = key << 8 | (value + 21) << 2 | flag


class SearchBudgetExceeded(Exception):
    """A budgeted solve() crossed its per-solve node cap. Every table entry
    stored before the abort is still a valid bound — an interrupted search
    stores nothing wrong — so the solver stays safe to keep using. Exists
    for dataset generation over random-playout positions, whose solve-time
    distribution has a measured heavy tail (PLAN.md, 2026-07-29): the cap
    bounds the tail, the caller rejects the position."""


class Solver:
    """Exact negamax + alpha-beta over the bitboard. `solve()` returns the
    Pons-convention score of a live position (see module docstring).

    The table persists across `solve()` calls on purpose — entries are
    keyed by position and position-invariant, so batch scoring (the Pons
    sets, the chunk-3/4 policy metrics) warm-starts. A test pins that a
    shared solver and a fresh-per-position solver agree.

    `nodes` counts negamax entries since construction; the perf numbers in
    PLAN.md (894k nodes/s) are in these units. `node_budget`, if set, caps
    each individual solve() call (not the lifetime count — a warm shared
    solver must not inherit its predecessors' spend), raising
    SearchBudgetExceeded past the cap.
    """

    def __init__(self, tt_size: int = TT_SIZE, node_budget: "int | None" = None):
        self.tt = TranspositionTable(tt_size)
        self.nodes = 0
        self.node_budget = node_budget
        self._solve_start = 0

    def solve(self, bb: Bitboard) -> int:
        """Pons' chapter-8 driver: iterative narrowing by null-window
        probes. Mandatory, not an optimization — measured pre-chapter-8,
        the Begin sets sit at 54 hours to 17 days; this cuts Begin-Easy
        ~660x (PLAN.md). Each probe `(med, med+1)` is decisive both ways
        because the search is fail-soft: r <= med means the true value is
        <= r, r > med means it is >= r, so [lo, hi] shrinks by a tightened
        bound every iteration until it pinches onto the exact score. The
        probes share the table, which is why the TT flags are load-bearing
        (a bound stored as EXACT poisons the next probe — the corruption
        the null-window consistency test pins).

        `int(x / 2)` and not `x // 2`: the reference C++ truncates toward
        zero, Python floors, and they differ on negative bounds.
        """
        if _alignment(bb.current) or _alignment(bb.current ^ bb.mask):
            raise ValueError("position is already won; solve() wants a live position")
        self._solve_start = self.nodes
        lo = -((CELLS - bb.moves) // 2)
        hi = (CELLS + 1 - bb.moves) // 2
        while lo < hi:
            med = lo + (hi - lo) // 2
            # Bias the probe toward zero first (most positions are close
            # to a draw), stepping to the halved bound when it is nearer.
            if med <= 0 and int(lo / 2) < med:
                med = int(lo / 2)
            elif med >= 0 and int(hi / 2) > med:
                med = int(hi / 2)
            r = self._negamax(bb, med, med + 1)
            if r <= med:
                hi = r
            else:
                lo = r
        return lo

    def _negamax(self, bb: Bitboard, alpha: int, beta: int) -> int:
        # The window must have width: the TT-hit path below returns `value`
        # whenever a stored bound closes the window, which is only the
        # right bound DIRECTION if alpha < beta held on entry. A zero-width
        # call returns bounds facing the wrong way — found by a mutation
        # that relaxed the cutoff to strict `>` and let child windows
        # collapse to zero (scripts/mutations/chunk3_solver.py).
        assert alpha < beta
        self.nodes += 1
        if self.node_budget is not None and self.nodes - self._solve_start > self.node_budget:
            raise SearchBudgetExceeded(f"solve exceeded {self.node_budget} nodes")
        if bb.moves == CELLS:
            return 0  # full board, and the mover's opponent did not win
        # Win-before-full ordering, solver edition: this scan runs before
        # the draw check can ever fire for the 42nd disc, because at
        # moves == 41 the position reaches here, not the branch above.
        for col in MOVE_ORDER:
            if bb.can_play(col) and bb.is_winning_move(col):
                return (CELLS + 1 - bb.moves) // 2

        key = bb.key()
        hit = self.tt.get(key)
        if hit is not None:
            value, flag = hit
            if flag == EXACT:
                return value
            if flag == LOWER:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value

        alpha0 = alpha
        best = -CELLS  # below any real score
        for col in MOVE_ORDER:
            if not bb.can_play(col):
                continue
            value = -self._negamax(bb.play(col), -beta, -alpha)
            if value > best:
                best = value
                if value > alpha:
                    alpha = value
            if alpha >= beta:
                break

        if best <= alpha0:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt.put(key, best, flag)
        return best


def solver_move_scores(solver: Solver, bb: Bitboard) -> "dict[int, int]":
    """Exact Pons-convention score of every legal move: the phase's spine
    claim that a move is optimal only if its CHILD's value is -v(p), as a
    function (Pons' labels alone cannot rank moves — PLAN.md). The
    win-in-1 check must run before the child solve, and not only for
    speed: `solve()` refuses already-won positions, and a winning move's
    child is exactly that. The caller owns the solver so batch scoring
    (the Pons policy metrics) keeps one warm transposition table across a
    whole set."""
    scores = {}
    for col in MOVE_ORDER:
        if not bb.can_play(col):
            continue
        if bb.is_winning_move(col):
            scores[col] = (CELLS + 1 - bb.moves) // 2
        else:
            scores[col] = -solver.solve(bb.play(col))
    return scores


def brute_force(bb: Bitboard) -> int:
    """The differential oracle: negamax with NOTHING in it — no pruning, no
    transposition table, no ordering, no early return on a found win. Only
    usable on positions with few empty cells, which is what the tests feed
    it. The win-score formula is duplicated from Solver rather than shared
    on purpose: a helper both sides import would let one bug pass the
    differential test unseen.
    """
    if bb.moves == CELLS:
        return 0
    best = -CELLS
    for col in range(COLS):
        if not bb.can_play(col):
            continue
        if bb.is_winning_move(col):
            value = (CELLS + 1 - bb.moves) // 2
        else:
            value = -brute_force(bb.play(col))
        best = max(best, value)
    return best

"""Chunk-3 mutation spec: bitboard, negamax, transposition table.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk3_solver.py

Committed like the chunk-2 battery: chunk 3's remaining steps (chapter-8
deepening, the alpha-beta opponent) touch this code, so the battery must be
re-runnable, not session scratch. If a control is ever reported caught, the
harness is measuring noise — see scripts/mutate.py's docstring.

The two TT mutations are the ones this file exists for: storing fail-soft
bounds as EXACT is the corruption class PLAN.md measured at 0.13-0.40% of
results (rising with depth) and the Pons labels structurally cannot see —
only the brute-force differential can, so these two verify that it does.

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_solver.py"]

SOLVER = "rl/selfplay/solver.py"
OPP = "rl/selfplay/opponents.py"

MUTATIONS = [
    # ------------------------------------------------------------- bitboard
    ("no-sentinel-row", SOLVER,
     "H1 = ROWS + 1  # bits per column: ROWS cells + 1 sentinel",
     "H1 = ROWS  # bits per column: ROWS cells + 1 sentinel"),
    ("top-mask-one-row-low", SOLVER,
     "TOP_MASK = tuple(1 << (col * H1 + ROWS - 1) for col in range(COLS))",
     "TOP_MASK = tuple(1 << (col * H1 + ROWS - 2) for col in range(COLS))"),
    ("horizontal-alignment-wrong-shift", SOLVER,
     "    m = stones & (stones >> H1)  # horizontal",
     "    m = stones & (stones >> (H1 + 2))  # horizontal"),
    ("play-keeps-perspective", SOLVER,
     "            self.current ^ self.mask, self.mask | self._stone(col), self.moves + 1",
     "            self.current | self._stone(col), self.mask | self._stone(col), self.moves + 1"),
    ("winning-move-checks-opponent", SOLVER,
     "        return _alignment(self.current | self._stone(col))",
     "        return _alignment((self.current ^ self.mask) | self._stone(col))"),
    # ----------------------------------------------------------------- search
    ("win-score-off-by-one", SOLVER,
     "                return (CELLS + 1 - bb.moves) // 2",
     "                return (CELLS - bb.moves) // 2"),
    ("draw-declared-with-a-cell-left", SOLVER,
     "        if bb.moves == CELLS:\n            return 0  # full board",
     "        if bb.moves >= CELLS - 1:\n            return 0  # full board"),
    # ----------------------------------------------------- transposition table
    ("tt-bound-stored-as-exact", SOLVER,
     """        if best <= alpha0:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt.put(key, best, flag)""",
     "        self.tt.put(key, best, EXACT)"),
    ("tt-hit-ignores-flag", SOLVER,
     """            value, flag = hit
            if flag == EXACT:
                return value
            if flag == LOWER:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value""",
     """            value, flag = hit
            return value"""),
    ("tt-key-check-dropped", SOLVER,
     "        if entry and entry >> 8 == key:",
     "        if entry:"),
    # Was control C2, reclassified after the chapter-8 driver caught it: a
    # strict `>` cutoff lets alpha rise to == beta and the next child be
    # searched with a ZERO-width window, where the TT-hit path returns
    # bounds facing the wrong way. Equivalent-looking, actually a contract
    # violation — the alpha < beta assert now makes the catch deterministic.
    ("strict-cutoff-breaks-window-contract", SOLVER,
     "            if alpha >= beta:\n                break",
     "            if alpha > beta:\n                break"),
    # ------------------------------------------------------ chapter-8 driver
    ("driver-trusts-fail-high-as-exact", SOLVER,
     """            if r <= med:
                hi = r
            else:
                lo = r""",
     """            if r <= med:
                hi = r
            else:
                return r"""),
    # ---------------------------------------------------- alpha-beta anchor
    ("ab-tie-break-takes-first", OPP,
     "return int(rng.choice([c for c, s in sorted(scores.items()) if s == best]))",
     "return int([c for c, s in sorted(scores.items()) if s == best][0])"),
    # The win-scan-before-horizon ordering is what gives depth d vision of
    # plies 1..d; swapping them silently turns alphabeta2 into alphabeta1.
    ("ab-horizon-before-win-scan", OPP,
     """    if bb.moves == CELLS:
        return 0
    for col in MOVE_ORDER:
        if bb.can_play(col) and bb.is_winning_move(col):
            return (CELLS + 1 - bb.moves) // 2
    if depth <= 1:
        return 0""",
     """    if bb.moves == CELLS:
        return 0
    if depth <= 1:
        return 0
    for col in MOVE_ORDER:
        if bb.can_play(col) and bb.is_winning_move(col):
            return (CELLS + 1 - bb.moves) // 2"""),
    ("ab-win-score-off-by-one", OPP,
     "            return (CELLS + 1 - bb.moves) // 2",
     "            return (CELLS - bb.moves) // 2"),
    # ------------------------------------------------------------ play_game
    ("game-winner-sign-flipped", OPP,
     "            return 1 if mover == 0 else -1",
     "            return -1 if mover == 0 else 1"),
    ("game-full-checked-before-win", OPP,
     """        won = board.drop(int(col))
        if won:
            return 1 if mover == 0 else -1
        if board.full():
            return 0""",
     """        won = board.drop(int(col))
        if board.full():
            return 0
        if won:
            return 1 if mover == 0 else -1"""),
    # ------------------------------------------------- equivalence CONTROLS
    ("C1-move-order-left-to-right", SOLVER,
     "MOVE_ORDER = (3, 2, 4, 1, 5, 0, 6)",
     "MOVE_ORDER = (0, 1, 2, 3, 4, 5, 6)"),
    ("C2-tt-size-other-prime", SOLVER,
     "TT_SIZE = 1048573  # prime, so key % size spreads",
     "TT_SIZE = 524287  # prime, so key % size spreads"),
    # The driver's exit condition is lo == hi exactly: fail-soft results are
    # always inside the invariant interval, so lo can never overshoot.
    ("C3-driver-returns-hi", SOLVER,
     "        return lo",
     "        return hi"),
    ("C4-driver-midpoint-closed-form", SOLVER,
     "            med = lo + (hi - lo) // 2",
     "            med = (lo + hi) // 2"),
    # Same uniform draw through a different generator method; tests must
    # assert distributional properties, never the exact consumption of the
    # rng stream.
    ("C5-ab-tie-break-by-integers", OPP,
     "return int(rng.choice([c for c, s in sorted(scores.items()) if s == best]))",
     "ties = [c for c, s in sorted(scores.items()) if s == best]\n"
     "        return int(ties[int(rng.integers(len(ties)))])"),
]

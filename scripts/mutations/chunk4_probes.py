"""Chunk-4 mutation spec: the play_game extensions behind the probes.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk4_probes.py

The coverage and value-MSE probes (scripts/{coverage,value_mse}_probe.py)
lean on two small `play_game` additions — a start position and a recorded
move sequence — and a defect in either corrupts the diagnostics silently:
an unused start position turns every continuation target into a
fresh-game outcome, a mutated caller board poisons the position sample
in place, and a wrong move record merges distinct games. These pin them.

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_solver.py"]

OPP = "rl/selfplay/opponents.py"
SOLVER = "rl/selfplay/solver.py"

MUTATIONS = [
    # ------------------------------------------------- solver_move_scores
    ("move-scores-solve-the-winning-child", SOLVER,
     """        if bb.is_winning_move(col):
            scores[col] = (CELLS + 1 - bb.moves) // 2
        else:
            scores[col] = -solver.solve(bb.play(col))""",
     "        scores[col] = -solver.solve(bb.play(col))"),
    ("move-scores-child-not-negated", SOLVER,
     "            scores[col] = -solver.solve(bb.play(col))",
     "            scores[col] = solver.solve(bb.play(col))"),
    # ------------------------------------------------------ solve node budget
    ("budget-check-dropped", SOLVER,
     """        self.nodes += 1
        if self.node_budget is not None and self.nodes - self._solve_start > self.node_budget:
            raise SearchBudgetExceeded(f"solve exceeded {self.node_budget} nodes")""",
     "        self.nodes += 1"),
    ("budget-counts-lifetime-not-per-solve", SOLVER,
     "        if self.node_budget is not None and self.nodes - self._solve_start > self.node_budget:",
     "        if self.node_budget is not None and self.nodes > self.node_budget:"),
    # ------------------------------------------------- play_game extensions
    ("start-position-ignored", OPP,
     "    board = Connect4Board() if start is None else start.copy()",
     "    board = Connect4Board()"),
    ("start-played-in-place", OPP,
     "    board = Connect4Board() if start is None else start.copy()",
     "    board = Connect4Board() if start is None else start"),
    ("moves-never-recorded", OPP,
     """        if moves is not None:
            moves.append(int(col))
        won = board.drop(int(col))""",
     "        won = board.drop(int(col))"),
    # ------------------------------------------------- equivalence CONTROL
    # drop() does not change the column just played, so recording after it
    # is the same record. If this is caught, a test is asserting the
    # internal ordering of play_game's body rather than its behavior.
    ("C1-moves-recorded-after-drop", OPP,
     """        if moves is not None:
            moves.append(int(col))
        won = board.drop(int(col))""",
     """        won = board.drop(int(col))
        if moves is not None:
            moves.append(int(col))"""),
]

"""Differential test of Connect4Board against open_spiel's `connect_four`.

Phase 4 has no published anchor to grade against, so correctness comes from
an exact oracle instead of a curve (PLAN.md). This file is the oracle half;
`tests/test_connect4.py` holds the hand-pinned fixtures. Neither replaces the
other: fixtures pin known semantics and survive if open_spiel is ever
dropped, the fuzz finds discrepancies nobody thought to name. Measured on
the same 16 board mutations — fixtures alone catch 15, this file alone
catches 12, and the three it misses are structural rather than incidental:
the fuzz never plays an illegal move (so the full-column raise never
fires) and never compares observation planes (so a swapped or aliased
plane is invisible here, by the design rule below).

open_spiel conventions, all confirmed by probe against 2.0.1 rather than
assumed — each one is a way to get a false green:

- action id == column index, 0-6; tensor row 0 == bottom, same as ours.
- there is no winner accessor; derive it from `returns()`: [1,-1] = P0 win,
  [-1,1] = P1 win, [0,0] = draw.
- `returns()` is [0,0] at EVERY non-terminal state too, so the winner
  comparison must be gated on `is_terminal()` or a draw and a game in
  progress are indistinguishable.
- `legal_actions()` is [] at a terminal state, so stop comparing there.
- `apply_action_with_legality_check` — plain `apply_action` reads out of
  bounds on an illegal action.
- `ToString()` prints TOP row first despite bottom-first indexing, so
  renderings must never be compared, and above all never used to check the
  row convention. Likewise the default observation tensor is [3,6,7] and
  ABSOLUTE (indexed by player id), where ours is [2,6,7] and egocentric.

So: compare semantics — legal move set, terminal flag, winner id. Never
renderings, never observation tensors.
"""

import ast
from pathlib import Path

import numpy as np
import pyspiel
import pytest

from rl.envs.connect4 import Connect4Board
from tests.test_connect4 import DRAW_42, WIN_FIXTURES, WIN_ON_42

REPO_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "runs", "wandb", "data", "assets", "__pycache__", ".pytest_cache"}


def _python_files():
    for path in REPO_ROOT.rglob("*.py"):
        if not SKIP_DIRS & set(path.relative_to(REPO_ROOT).parts):
            yield path


def _forbidden_imports(tree):
    """open_spiel.python.* imports in one parsed module, by any spelling."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "open_spiel.python" or alias.name.startswith(
                    "open_spiel.python."
                ):
                    yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "open_spiel.python" or module.startswith("open_spiel.python."):
                yield module
            elif module == "open_spiel":
                for alias in node.names:
                    if alias.name == "python":
                        yield "open_spiel.python"


def test_open_spiel_algorithms_are_never_imported():
    """The carve-out from the no-RL-libraries rule is narrow: open_spiel is a
    board oracle only. The package also ships algorithm implementations
    (dqn, ppo, ...) under its python subpackage, and importing any of them
    would breach the project's central rule.

    Checked by parsing imports rather than grepping text: every file that
    legitimately DOCUMENTS the ban — CLAUDE.md, pyproject.toml, this
    docstring — contains the forbidden name as prose, so a text scan reports
    the rule's own statement as a violation. The AST sees imports only.
    """
    offenders = {}
    for path in _python_files():
        names = sorted(set(_forbidden_imports(ast.parse(path.read_text()))))
        if names:
            offenders[str(path.relative_to(REPO_ROOT))] = names
    assert offenders == {}, f"forbidden open_spiel imports: {offenders}"


def test_open_spiel_is_a_dev_only_dependency():
    """The other half of the carve-out: it must never become a runtime dep,
    and never the [full] extra."""
    text = (REPO_ROOT / "pyproject.toml").read_text()
    runtime, _, optional = text.partition("[project.optional-dependencies]")
    assert "open_spiel" not in runtime, "open_spiel must not be a runtime dependency"
    assert "open_spiel==2.0.1" in optional
    assert "open_spiel[full]" not in text


@pytest.fixture(scope="module")
def game():
    return pyspiel.load_game("connect_four")


def _oracle_outcome(state):
    """(is_terminal, winner) with winner in {0, 1, None-for-draw}, or None if
    the game is still running. Gated on is_terminal: returns() is [0,0] at
    every non-terminal state, which is also exactly a draw's value."""
    if not state.is_terminal():
        return False, None
    returns = state.returns()
    if returns[0] > 0:
        return True, 0
    if returns[1] > 0:
        return True, 1
    return True, None  # draw


def test_oracle_conventions_are_what_we_assume(game):
    """Pin the four conventions this file's correctness rests on, so an
    open_spiel upgrade that changes any of them fails here with a clear
    message instead of silently weakening the fuzz below."""
    state = game.new_initial_state()
    assert game.num_distinct_actions() == 7
    assert state.legal_actions() == [0, 1, 2, 3, 4, 5, 6]
    assert state.returns() == [0.0, 0.0] and not state.is_terminal()
    # A single disc in column 3 lands on tensor row 0 -> row 0 is the bottom.
    state.apply_action_with_legality_check(3)
    tensor = np.asarray(state.observation_tensor()).reshape(game.observation_tensor_shape())
    assert tensor.shape == (3, 6, 7)
    assert np.argwhere(tensor[0] != 0).tolist() == [[0, 3]]
    # ...and that plane is indexed by PLAYER ID, not by side to move: player 0
    # just moved, so an egocentric encoding would have put the disc elsewhere.
    assert state.current_player() == 1


@pytest.mark.parametrize("name", sorted(WIN_FIXTURES))
def test_win_fixtures_agree_with_the_oracle(game, name):
    cols = WIN_FIXTURES[name]
    board, won = Connect4Board(), False
    state = game.new_initial_state()
    for col in cols:
        won = board.drop(col)
        state.apply_action_with_legality_check(col)
    terminal, winner = _oracle_outcome(state)
    assert won and terminal
    assert winner == (len(cols) - 1) % 2  # the last mover won


@pytest.mark.parametrize("name,cols,expect_win", [("draw", DRAW_42, False),
                                                  ("win_on_42", WIN_ON_42, True)])
def test_board_filling_fixtures_agree_with_the_oracle(game, name, cols, expect_win):
    board, won = Connect4Board(), False
    state = game.new_initial_state()
    for col in cols:
        won = board.drop(col)
        state.apply_action_with_legality_check(col)
    terminal, winner = _oracle_outcome(state)
    assert terminal and board.full()
    assert won == expect_win
    assert winner == ((len(cols) - 1) % 2 if expect_win else None)


def test_fuzz_agrees_with_the_oracle_at_every_step(game):
    """A few thousand random games, compared at every ply. Coverage of each
    terminal type is asserted rather than assumed: draws are 0.27% of random
    games, so a fuzz that silently saw zero of them would be testing less
    than it appears to. Seeded, so the counts below are deterministic."""
    rng = np.random.default_rng(0)
    games, plies = 2000, 0
    outcomes = {0: 0, 1: 0, None: 0}
    for _ in range(games):
        board = Connect4Board()
        state = game.new_initial_state()
        move, won = 0, False
        while True:
            # Legal move sets must agree BEFORE the move.
            assert np.flatnonzero(board.legal_mask()).tolist() == state.legal_actions()
            col = int(rng.choice(state.legal_actions()))
            won = board.drop(col)
            state.apply_action_with_legality_check(col)
            plies += 1
            ours_terminal = won or board.full()
            terminal, winner = _oracle_outcome(state)
            assert ours_terminal == terminal, f"terminal disagreement after {move + 1} plies"
            if terminal:
                assert winner == (move % 2 if won else None)
                outcomes[winner] += 1
                break
            move += 1
    assert plies > 40_000  # ~21.25 plies/game
    assert outcomes[0] > 0 and outcomes[1] > 0
    assert outcomes[None] > 0, "no draws sampled: the draw branch went untested"

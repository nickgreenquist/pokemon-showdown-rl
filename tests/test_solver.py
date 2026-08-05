"""Solver tests (Phase 4 chunk 3): bitboard vs Connect4Board, search vs
brute force.

The two differential halves deliberately trust different things. The
bitboard half trusts `Connect4Board` — chunk 1 validated it against the
open_spiel oracle, so ply-by-ply agreement chains the bitboard to that
oracle. The search half (added with the solver) trusts `brute_force`, a
negamax with nothing in it that can be subtly wrong — no pruning, no
transposition table, no ordering.

The named fixtures ride through the bitboard too: the random playouts are
the fuzz, the fixtures are the shapes chunk 1 learned to pin by hand (edge
columns, both diagonals, the win on the 42nd disc) — numpy's wrap bug there
is the same failure class as a bitboard shift crossing a column boundary,
which is exactly what the sentinel row exists to stop.
"""

import numpy as np
import pytest

from rl.envs.connect4 import CELLS, COLS, Connect4Board
from rl.selfplay.opponents import (
    AlphaBetaOpponent,
    alphabeta_move_scores,
    make_opponent,
    play_game,
)
from rl.selfplay.solver import (
    Bitboard,
    SearchBudgetExceeded,
    Solver,
    brute_force,
    solver_move_scores,
)
from tests.test_connect4 import (
    DRAW_42,
    WIN_FIXTURES,
    WIN_ON_42,
    ScriptedOpponent,
    play,
)

# ---------------------------------------------------------------- bitboard


def replay(cols):
    """Play a column sequence through BOTH representations, comparing at
    every ply; return the final (board, bitboard, last_move_won)."""
    board, bb = Connect4Board(), Bitboard()
    won = False
    for col in cols:
        assert not won, "sequence continues past a win"
        assert [c for c in range(COLS) if bb.can_play(c)] == list(
            np.flatnonzero(board.legal_mask())
        )
        predicted = bb.is_winning_move(col)
        won = board.drop(col)
        assert predicted == won, f"win flag disagrees on column {col}"
        bb = bb.play(col)
        assert Bitboard.from_board(board) == bb, f"state diverged after column {col}"
    return board, bb, won


def test_random_playout_differential():
    """Fuzz: full random games, every ply compared — legal columns, the win
    flag, and the (current, mask, moves) triple via from_board."""
    rng = np.random.default_rng(0)
    for _ in range(40):
        board, bb = Connect4Board(), Bitboard()
        while True:
            assert [c for c in range(COLS) if bb.can_play(c)] == list(
                np.flatnonzero(board.legal_mask())
            )
            col = int(rng.choice(np.flatnonzero(board.legal_mask())))
            predicted = bb.is_winning_move(col)
            won = board.drop(col)
            assert predicted == won
            bb = bb.play(col)
            assert Bitboard.from_board(board) == bb
            if won or board.full():
                break


@pytest.mark.parametrize("name", sorted(WIN_FIXTURES))
def test_win_fixtures_through_the_bitboard(name):
    """The hand-pinned win shapes — edge columns and both diagonals — must
    win on their last move and never earlier, in the bitboard's own win
    check (replay asserts the flag at every ply)."""
    _, _, won = replay(WIN_FIXTURES[name])
    assert won


def test_draw_and_win_on_42_through_the_bitboard():
    board, bb, won = replay(DRAW_42)
    assert not won and bb.moves == 42
    _, bb, won = replay(WIN_ON_42)
    assert won and bb.moves == 42


def test_to_board_round_trips():
    """to_board is the inverse of the playout: array, moves counter, and
    a second from_board all agree mid-game (canonical perspective intact
    after an odd number of plies)."""
    for cols in (WIN_FIXTURES["diagonal_up_right"][:9], DRAW_42[:17]):
        board, bb, _ = replay(cols)
        back = bb.to_board()
        assert np.array_equal(back.board, board.board)
        assert back.moves == len(cols)
        assert Bitboard.from_board(back) == bb


def test_keys_are_unique_across_distinct_positions():
    """`current + mask` must collide only for identical positions: walk a
    few hundred random positions and assert the key map is injective."""
    rng = np.random.default_rng(1)
    seen: dict[int, tuple[int, int]] = {}
    for _ in range(30):
        board, bb = Connect4Board(), Bitboard()
        while True:
            state = seen.setdefault(bb.key(), (bb.current, bb.mask))
            assert state == (bb.current, bb.mask), "key collision"
            col = int(rng.choice(np.flatnonzero(board.legal_mask())))
            if board.drop(col):
                break
            bb = bb.play(col)
            if board.full():
                break
    assert len(seen) > 300


# ------------------------------------------------------------------ solver


def bitboard_after(cols) -> Bitboard:
    bb = Bitboard()
    for col in cols:
        bb = bb.play(col)
    return bb


def random_position(rng, stones: int) -> Bitboard:
    """A live random position with exactly `stones` discs (games that end
    earlier are discarded and redrawn)."""
    while True:
        board, bb = Connect4Board(), Bitboard()
        for _ in range(stones):
            col = int(rng.choice(np.flatnonzero(board.legal_mask())))
            if board.drop(col):
                break
            bb = bb.play(col)
        else:
            return bb


@pytest.mark.parametrize("name", sorted(WIN_FIXTURES))
def test_win_in_one_scores_exactly(name):
    """One ply before each win fixture lands, the mover's value is the
    immediate-win score (22 - the winner's stones) — an immediate win is
    the best score reachable from any position, so no deeper line beats
    it. Pins the score formula, not just the sign. Solver only: these
    positions have 30+ empty cells, and the no-pruning oracle is
    exponential in empties — it belongs on near-full positions only."""
    cols = WIN_FIXTURES[name]
    bb = bitboard_after(cols[:-1])
    assert Solver().solve(bb) == (CELLS + 1 - bb.moves) // 2


def test_double_threat_is_a_forced_loss():
    """After [1,1,2,2,3] the first player threatens both column 0 and
    column 4 on the bottom row; the mover has no win of its own and can
    block only one side, so every reply loses to the opponent's 4th stone:
    score -(22 - 4) = -18."""
    assert Solver().solve(bitboard_after([1, 1, 2, 2, 3])) == -18


def test_win_on_the_42nd_disc_is_not_a_draw():
    """Win-before-full, solver edition: at 41 stones the last cell wins, so
    the value is +1 (a win with the 21st stone), not the draw the full-board
    branch would report if it were checked first."""
    bb = bitboard_after(WIN_ON_42[:-1])
    assert bb.moves == 41
    assert Solver().solve(bb) == 1
    assert brute_force(bb) == 1


def test_full_board_draw_scores_zero():
    bb = bitboard_after(DRAW_42)
    assert Solver().solve(bb) == 0
    assert brute_force(bb) == 0


def test_solve_rejects_finished_positions():
    bb = bitboard_after(WIN_FIXTURES["vertical_col0"])
    with pytest.raises(ValueError, match="already won"):
        Solver().solve(bb)


def test_solver_matches_brute_force_on_random_endgames():
    """The differential test proper, exact score equality (sign agreement
    would pass a solver with a corrupted magnitude). One solver is shared
    across every position ON PURPOSE: entries persist across solve() calls,
    so any stale-entry, key-collision or flag bug that only shows on a warm
    table shows here; the fresh solver per position is the control."""
    rng = np.random.default_rng(2)
    shared = Solver()
    for stones, n in ((32, 8), (34, 20), (36, 20)):
        for _ in range(n):
            bb = random_position(rng, stones)
            truth = brute_force(bb)
            assert shared.solve(bb) == truth
            assert Solver().solve(bb) == truth


def test_narrow_window_searches_do_not_poison_the_table():
    """The TT-flag guard, given real power. The endgame differential does
    not catch bounds-stored-as-EXACT — measured by mutation, twice: at
    <=10 empties nearly every node resolves through the win scan or the
    full-board draw within a ply or two, so fail-soft bounds nearly always
    EQUAL the exact value and misreading them changes nothing. The
    corruption needs depth to express (PLAN.md: the error rate rises with
    depth), and depth is exactly where the brute-force oracle cannot
    follow. So this is a consistency test instead: a correct solver
    returns the same full-window value from a fresh table and from one
    deliberately stuffed with null-window fail-soft bounds — the
    chapter-8 usage pattern — while broken flag handling leaks the bounds
    into the poisoned answer. Positions are kept only when the fresh
    solve costs 2k-300k nodes: below the band the tree is too shallow for
    bounds to differ from exact values (the failure above), above it the
    test gets slow. Fixed seed + fixed rule = deterministic."""
    rng = np.random.default_rng(5)
    kept = 0
    while kept < 8:
        bb = random_position(rng, int(rng.integers(18, 23)))
        fresh = Solver()
        value = fresh.solve(bb)
        if not 2_000 <= fresh.nodes <= 300_000:
            continue
        kept += 1
        poisoned = Solver()
        for a in range(-6, 6):
            poisoned._negamax(bb, a, a + 1)
        assert poisoned.solve(bb) == value


def test_chapter8_driver_matches_plain_full_window_search():
    """The null-window driver must land on exactly the value a single
    full-window negamax finds — checked at depths the brute-force oracle
    cannot reach (the endgame differential already anchors both against
    brute force where it can). Fresh solver per side so neither search
    reads the other's table."""
    rng = np.random.default_rng(6)
    kept = 0
    while kept < 6:
        bb = random_position(rng, int(rng.integers(18, 23)))
        reference = Solver()
        value = reference._negamax(bb, -(CELLS // 2), CELLS // 2)
        if reference.nodes < 2_000:
            continue
        kept += 1
        assert Solver().solve(bb) == value


def test_tiny_table_forces_collisions_without_corrupting_values():
    """At size 17 nearly every put lands on an occupied slot, so the
    replace-on-collision path and the stored-key check run constantly; the
    values must not move."""
    rng = np.random.default_rng(3)
    tiny = Solver(tt_size=17)
    for _ in range(12):
        bb = random_position(rng, 34)
        assert tiny.solve(bb) == brute_force(bb)


# ----------------------------------------------------- alpha-beta opponent


def ask_opponent(opponent, cols, draws=20, seed=0):
    """Play `cols`, then collect `draws` seeded move() choices from the
    resulting position (the mover is whoever is to move after `cols`)."""
    board, _ = play(cols)
    rng = np.random.default_rng(seed)
    return [
        opponent.move(board.planes(), board.legal_mask(), rng) for _ in range(draws)
    ]


def test_alphabeta_wins_rather_than_blocks():
    """After [0,1,0,1,0,1] the mover has three in column 0 AND faces three
    in column 1: the win outscores the block, so the tie set is a single
    column and every draw picks it."""
    assert set(ask_opponent(AlphaBetaOpponent(2), [0, 1, 0, 1, 0, 1])) == {0}


def test_alphabeta_blocks_a_loss_it_can_see():
    """After [0,1,0,1,0] the mover has no win and the opponent has three in
    column 0: at depth 2 every non-blocking move loses to the win scan one
    ply down, so column 0 is the unique argmax."""
    assert set(ask_opponent(AlphaBetaOpponent(2), [0, 1, 0, 1, 0])) == {0}


def test_alphabeta4_sees_the_double_threat_alphabeta2_cannot():
    """After [1,1,2,2] playing column 3 creates the 0/4 double threat and
    forces a win on ply 3 — inside depth 4's horizon, beyond depth 2's.
    So alphabeta4 plays column 3 every time, while alphabeta2 scores the
    whole row of moves 0 and spreads over ties."""
    bb = Bitboard()
    for col in [1, 1, 2, 2]:
        bb = bb.play(col)
    scores2 = alphabeta_move_scores(bb, 2)
    scores4 = alphabeta_move_scores(bb, 4)
    assert set(scores2.values()) == {0}
    assert scores4[3] > 0
    assert [c for c, s in scores4.items() if s == max(scores4.values())] == [3]
    assert set(ask_opponent(AlphaBetaOpponent(4), [1, 1, 2, 2])) == {3}
    assert len(set(ask_opponent(AlphaBetaOpponent(2), [1, 1, 2, 2], draws=50))) > 1


def test_alphabeta_tie_break_is_uniform_and_seeded():
    """On the empty board at depth 2 all seven moves are true ties: the
    tie-break must reach every column (the 89/100-vs-2/100 eval-diversity
    property rides on this) and must replay exactly under the same seed."""
    board = Connect4Board()
    opponent = AlphaBetaOpponent(2)
    rng = np.random.default_rng(7)
    draws = [opponent.move(board.planes(), board.legal_mask(), rng) for _ in range(300)]
    assert set(draws) == set(range(COLS))
    rng_a, rng_b = np.random.default_rng(8), np.random.default_rng(8)
    assert [opponent.move(board.planes(), board.legal_mask(), rng_a) for _ in range(30)] \
        == [opponent.move(board.planes(), board.legal_mask(), rng_b) for _ in range(30)]


def test_alphabeta_full_depth_matches_the_exact_solver():
    """With depth >= the moves remaining the horizon never truncates, so
    the depth-limited scores must equal exact per-move solver values —
    a differential between the two search implementations."""
    rng = np.random.default_rng(9)
    for _ in range(10):
        bb = random_position(rng, 34)
        remaining = CELLS - bb.moves
        scores = alphabeta_move_scores(bb, remaining)
        for col, score in scores.items():
            if bb.is_winning_move(col):
                exact = (CELLS + 1 - bb.moves) // 2
            else:
                exact = -Solver().solve(bb.play(col))
            assert score == exact, f"col {col}: limited {score} != exact {exact}"


def test_registry_resolves_the_alphabeta_anchors():
    for name, depth in (("alphabeta2", 2), ("alphabeta4", 4)):
        opponent = make_opponent(name)
        assert isinstance(opponent, AlphaBetaOpponent)
        assert opponent.depth == depth


# --------------------------------------------------------------- play_game


def test_play_game_attributes_the_win_to_the_right_seat():
    """Fixture games driven from both seats: vertical_col0 has an odd ply
    count so the first seat wins; prepending a wasted move hands the same
    win to the second seat; WIN_ON_42 ends on the 42nd disc (even ply,
    second seat) and pins win-before-full inside the runner too."""
    rng = np.random.default_rng(0)
    cols = WIN_FIXTURES["vertical_col0"]
    assert play_game(ScriptedOpponent(cols[0::2]), ScriptedOpponent(cols[1::2]), rng) == 1
    shifted = [6] + cols
    assert play_game(
        ScriptedOpponent(shifted[0::2]), ScriptedOpponent(shifted[1::2]), rng
    ) == -1
    assert play_game(
        ScriptedOpponent(WIN_ON_42[0::2]), ScriptedOpponent(WIN_ON_42[1::2]), rng
    ) == -1
    assert play_game(
        ScriptedOpponent(DRAW_42[0::2]), ScriptedOpponent(DRAW_42[1::2]), rng
    ) == 0


def test_play_game_select_rewinds_and_objects_are_reusable():
    """The runner calls select() at game start — the per-episode hook — so
    the SAME scripted objects must replay cleanly across games, exactly as
    a pool member is reused across episodes."""
    first = ScriptedOpponent(DRAW_42[0::2])
    second = ScriptedOpponent(DRAW_42[1::2])
    for _ in range(3):
        assert play_game(first, second, np.random.default_rng(0)) == 0


def test_play_game_is_deterministic_given_the_rng():
    def outcomes():
        rng = np.random.default_rng(3)
        return [
            play_game(make_opponent("heuristic"), make_opponent("alphabeta2"), rng)
            for _ in range(10)
        ]

    first, again = outcomes(), outcomes()
    assert first == again
    assert len(set(first)) > 1  # and the games are not all the same result


def test_node_budget_caps_each_solve_not_the_lifetime():
    """Per-solve semantics: a budget sized to the largest single solve must
    pass every solve even though the CUMULATIVE count crosses it many times
    over (a warm shared solver must not inherit its predecessors' spend) —
    and the results must be bit-identical to an uncapped solver. An
    exceeded budget raises, and the solver stays usable afterwards: the
    aborted search stored only valid bounds."""
    rng = np.random.default_rng(13)
    positions = [random_position(rng, 30) for _ in range(10)]
    plain = Solver()
    expected, deltas = [], []
    for bb in positions:
        before = plain.nodes
        expected.append(plain.solve(bb))
        deltas.append(plain.nodes - before)
    budget = max(deltas)
    assert sum(deltas) > budget  # power: the lifetime-counting mutant must trip
    assert deltas[1] > 1  # power: budget 1 below must actually abort

    capped = Solver(node_budget=budget)
    assert [capped.solve(bb) for bb in positions] == expected

    capped.node_budget = 1
    with pytest.raises(SearchBudgetExceeded):
        capped.solve(positions[1])
    capped.node_budget = budget
    assert capped.solve(positions[0]) == expected[0]


def test_solver_move_scores_match_full_depth_alphabeta():
    """Differential between the two search implementations, per move: the
    TT'd solver's move scores must equal full-depth alpha-beta's on random
    endgames — including positions holding a win-in-1, where the win check
    must fire BEFORE the child solve (solve() refuses a won child)."""
    rng = np.random.default_rng(11)
    solver = Solver()
    saw_win_in_1 = False
    for _ in range(10):
        bb = random_position(rng, 34)
        scores = solver_move_scores(solver, bb)
        assert scores == alphabeta_move_scores(bb, CELLS - bb.moves)
        saw_win_in_1 |= any(
            bb.can_play(c) and bb.is_winning_move(c) for c in range(COLS)
        )
    assert saw_win_in_1  # the seed must actually exercise the win branch
    # No small-fixture variant on purpose: a win-in-1 position with few
    # stones has NON-winning children 35+ empties deep — the Begin-set
    # difficulty class, minutes per solve. The endgame differential above
    # covers the win branch (asserted) at test speed.


def test_play_game_records_the_move_sequence():
    """`moves` must be the played columns in order — the coverage probe
    distinguishes games by sequence, so a wrong order or a skipped ply
    would silently merge distinct games. Replaying the recorded sequence
    through a fresh board must reproduce the outcome."""
    rng = np.random.default_rng(0)
    moves: list[int] = []
    outcome = play_game(
        ScriptedOpponent(DRAW_42[0::2]), ScriptedOpponent(DRAW_42[1::2]), rng,
        moves=moves,
    )
    assert outcome == 0
    assert moves == list(DRAW_42)
    board = Connect4Board()
    for col in moves[:-1]:
        assert not board.drop(col)
    assert not board.drop(moves[-1]) and board.full()


def test_play_game_start_position_seats_and_no_mutation():
    """From a canonical start position, `first` is the player TO MOVE and
    the outcome sign is from that player's perspective; the caller's board
    is played on a copy, never mutated."""
    start, _ = play([0, 1, 0, 1, 0, 1])  # mover: 3 in col 0; other: 3 in col 1
    frozen = start.board.copy()
    rng = np.random.default_rng(0)

    moves: list[int] = []
    assert play_game(
        ScriptedOpponent([0]), ScriptedOpponent([]), rng, start=start, moves=moves
    ) == 1
    assert moves == [0]

    moves = []
    assert play_game(
        ScriptedOpponent([2]), ScriptedOpponent([1]), rng, start=start, moves=moves
    ) == -1
    assert moves == [2, 1]

    assert np.array_equal(start.board, frozen)
    assert start.moves == 6

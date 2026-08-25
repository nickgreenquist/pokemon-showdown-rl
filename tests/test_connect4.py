"""Connect 4 board and env fixtures.

These are the phase's GATE (SESSION_LOGS_PREDECESSOR.md chunk 1): deterministic per-site probes,
not a training run. The rejected alternative — "beats random >=90%" — caught
0 of 4 seeded defects, because `RandomOpponent.move` ignores the observation
entirely (so a wrong opponent perspective is a provable no-op) and both
swapped learner planes and a dropped epoch mask scored *higher* than clean.

Fixtures are hand-pinned semantics. They ONCE had a complement —
`tests/test_connect4_oracle.py`, which fuzzed against open_spiel for the
discrepancies nobody thought to name — and this docstring still claimed the
two were complementary long after that half was gone. **The oracle fuzzer no
longer exists**: open_spiel went with the spine prune (see pyproject.toml),
taking the file with it. So the hand-pinned fixtures below are now the ONLY
check, and the coverage claim this paragraph used to make was false. The
measurements that follow are still measured and still hold.

Measured here over 42,725 real learner decision points under random play:
the mask is all-True at **83.8%** of them and single-legal-column positions
are **0.05%** (~1 in 2000). SESSION_LOGS_PREDECESSOR.md's locked figures are 63.8% and 0.53%,
measured during the spec review; the gap is most likely the distribution
rather than an error on either side — those came from trained self-play,
where stronger blocking lengthens games and ~16% end in 42-ply draws, so
far more columns fill than in random play's ~21-ply games. Recorded rather
than reconciled, because it changes no decision: under EITHER distribution
single-legal columns are rare enough that fuzz alone is flaky on them, and
random play is the weaker case, so pinning the fixture by hand is if
anything more necessary than the locked numbers implied.
"""

import gymnasium as gym
import numpy as np
import pytest

from rl.envs.connect4 import COLS, ROWS, Connect4Board, Connect4Env
from rl.selfplay.opponents import (
    HeuristicOpponent,
    Opponent,
    RandomOpponent,
    board_from_obs,
    make_opponent,
)

# Win fixtures: column sequences, alternating players, the LAST move winning.
# Each is cross-checked against open_spiel in the oracle test file.
WIN_FIXTURES = {
    "vertical_col0": [0, 1, 0, 1, 0, 1, 0],
    "vertical_col6_edge": [6, 5, 6, 5, 6, 5, 6],
    "horizontal_row0_right_edge": [3, 0, 4, 1, 5, 2, 6],
    "diagonal_up_right": [0, 1, 1, 2, 6, 2, 2, 3, 6, 3, 6, 3, 3],
    "diagonal_up_left": [6, 5, 5, 4, 0, 4, 4, 3, 0, 3, 0, 3, 3],
}

# Found by random search (scratch), not by hand: 809 games to the first draw,
# 2603 to the first win on the 42nd disc. Draws are 0.27% of random games, so
# this branch is otherwise never exercised — SESSION_LOGS_PREDECESSOR.md lists it as a named
# degeneracy of this env.
DRAW_42 = [5, 5, 5, 0, 5, 4, 4, 6, 6, 3, 5, 1, 3, 5, 2, 1, 2, 3, 0, 4, 1,
           4, 3, 0, 2, 2, 2, 1, 0, 0, 0, 2, 1, 6, 1, 3, 4, 4, 3, 6, 6, 6]
WIN_ON_42 = [3, 4, 1, 0, 1, 1, 3, 3, 2, 2, 2, 2, 4, 4, 6, 5, 0, 3, 3, 6, 4,
             2, 4, 4, 1, 2, 0, 0, 5, 3, 6, 0, 1, 6, 0, 6, 1, 6, 5, 5, 5, 5]


def play(cols):
    """Play a column sequence; return (board, won_on_last_move). Raises if a
    win happens before the last move — a fixture that wins early is silently
    testing a different position than its name claims."""
    board = Connect4Board()
    won = False
    for i, col in enumerate(cols):
        assert not won, f"fixture won at move {i}, before its last move"
        won = board.drop(col)
    return board, won


def test_row_zero_is_the_bottom():
    """The convention pin. An inverted board passes every vertical and
    horizontal test — only the diagonals and this assertion catch it."""
    board = Connect4Board()
    board.drop(3)
    filled = np.argwhere(board.board != 0)
    assert filled.tolist() == [[0, 3]], "first disc must land on row 0"
    board.drop(3)
    assert board.height(3) == 2
    assert sorted(np.argwhere(board.board != 0).tolist()) == [[0, 3], [1, 3]]


def test_empty_board_state():
    board = Connect4Board()
    mask = board.legal_mask()
    assert mask.shape == (COLS,) and mask.dtype == np.bool_
    assert mask.all()
    assert not board.full()
    assert board.moves == 0
    assert all(board.height(c) == 0 for c in range(COLS))


def test_full_column_mask():
    board = Connect4Board()
    for _ in range(ROWS):  # alternating players: 6 discs, no line of 4
        board.drop(0)
    mask = board.legal_mask()
    assert not mask[0]
    assert mask[1:].all()
    assert not board.full()  # a full COLUMN is not a full board
    assert board.height(0) == ROWS


def test_single_legal_column():
    """0.53% of real decision points (~1 in 190) — fuzz reaches it rarely
    enough to be flaky, which is why it is pinned by hand."""
    board = Connect4Board()
    for col in range(COLS - 1):
        for _ in range(ROWS):
            board.drop(col)
    mask = board.legal_mask()
    assert mask.tolist() == [False] * (COLS - 1) + [True]
    assert np.count_nonzero(mask) == 1


def test_drop_on_full_column_raises():
    board = Connect4Board()
    for _ in range(ROWS):
        board.drop(0)
    with pytest.raises(ValueError, match="full"):
        board.drop(0)


@pytest.mark.parametrize("name", sorted(WIN_FIXTURES))
def test_win_fixtures_win_exactly_on_the_last_move(name):
    board, won = play(WIN_FIXTURES[name])
    assert won, f"{name}: last move should win"
    assert not board.full()


def test_diagonals_win_on_the_intended_diagonal():
    """A 'diagonal' fixture that actually won horizontally would leave the
    diagonal code path untested while staying green. Pin the cells.

    After the winning drop the board has been negated, so the winner's discs
    are -1 (drop() reports the win; the board moves on).
    """
    up_right, _ = play(WIN_FIXTURES["diagonal_up_right"])
    assert [int(up_right.board[i, i]) for i in range(4)] == [-1] * 4
    up_left, _ = play(WIN_FIXTURES["diagonal_up_left"])
    assert [int(up_left.board[i, COLS - 1 - i]) for i in range(4)] == [-1] * 4


def test_draw_on_a_full_board():
    board, won = play(DRAW_42)
    assert not won
    assert board.full()
    assert board.moves == ROWS * COLS
    assert not board.legal_mask().any()


def test_win_on_the_final_disc():
    """Win-before-full ordering is load-bearing: the 42nd disc can complete a
    line, so an env checking "board full -> draw" first silently converts this
    win into a draw. The board reports both true at once; the env's ORDER is
    what resolves it (see test_env_win_on_the_final_disc_is_a_win)."""
    board, won = play(WIN_ON_42)
    assert won
    assert board.full()


# Positions where a ray running off the board would WRAP. numpy's negative
# indices are silent: a scan off column 0 reads column 6, a scan off row 0
# reads row 5. Both positions below have no line of four, but report one if
# either low bound is dropped from the ray guard. Found by search against a
# deliberately mutated win check (scratch), not by hand.
NO_WIN_COL_WRAP = [4, 1, 5, 2, 6, 3, 0]  # discs at cols 4,5,6 then col 0
NO_WIN_ROW_WRAP = [2, 0, 3, 0, 6, 3, 3, 3, 0, 2, 3, 1, 3, 0, 1]


@pytest.mark.parametrize(
    "name,cols",
    [("col_wrap", NO_WIN_COL_WRAP), ("row_wrap", NO_WIN_ROW_WRAP)],
)
def test_rays_do_not_wrap_around_the_board_edges(name, cols):
    """The phantom-win case. Three same-colour discs on one edge plus one on
    the opposite edge is NOT a line of four — but numpy indexing says it is
    unless both low bounds are guarded."""
    board, won = play(cols)
    assert not won, f"{name}: ray wrapped around the board edge"


def test_planes_are_egocentric_and_freshly_allocated():
    board = Connect4Board()
    board.drop(3)  # mover A plays; board flips, so B is now the mover
    planes = board.planes()
    assert planes.shape == (2, ROWS, COLS) and planes.dtype == np.bool_
    # Plane 0 is the MOVER's discs. B has none yet; A's single disc is plane 1.
    assert planes[0].sum() == 0
    assert planes[1].sum() == 1 and planes[1][0, 3]
    # Never a view of internal state: the env contract forbids handing out
    # aliases of the board, and np.stack allocates.
    assert not np.shares_memory(planes, board.board)
    board.drop(3)
    assert planes[1].sum() == 1, "planes must not track later mutations"


def test_board_stays_canonical_after_every_drop():
    """+1 is always the player to move. After each drop the counts must
    satisfy: mover has played as many discs as the opponent, or one fewer."""
    board = Connect4Board()
    rng = np.random.default_rng(0)
    for _ in range(20):
        col = int(rng.choice(np.flatnonzero(board.legal_mask())))
        if board.drop(col):
            break
        mover = int((board.board == 1).sum())
        other = int((board.board == -1).sum())
        assert other - mover in (0, 1), f"non-canonical: {mover} vs {other}"


def test_copy_is_independent():
    board = Connect4Board()
    board.drop(3)
    clone = board.copy()
    clone.drop(3)
    assert board.moves == 1 and clone.moves == 2
    assert not np.shares_memory(board.board, clone.board)


# ---------------------------------------------------------------- env probes

class ScriptedOpponent(Opponent):
    """Plays a fixed column sequence. Lets a test drive both seats of a
    known game through the env, which is the only way to reach positions
    (a draw, a win on the 42nd disc) that random play effectively never
    produces."""

    def __init__(self, cols):
        self.cols = list(cols)
        self.i = 0

    def select(self, rng):
        # select() is the per-episode hook, so the script rewinds here. Without
        # this, reset_seat's retries silently consume scripted moves and the
        # test plays a different game than it reads as playing.
        self.i = 0
        return self

    def move(self, obs, mask, rng):
        col = self.cols[self.i]
        self.i += 1
        return col


class RecordingOpponent(Opponent):
    """Captures every observation it is handed, then plays the first legal
    column. This is the ONLY way to probe the opponent's perspective: under
    self-play both sides are the same network, so a wrong perspective here
    is symmetric and the training loop cannot see it."""

    def __init__(self):
        self.seen = []

    def move(self, obs, mask, rng):
        self.seen.append(obs.copy())
        return int(np.flatnonzero(mask)[0])


class OutOfRangeOpponent(Opponent):
    def move(self, obs, mask, rng):
        return COLS  # never a valid column index


class AlwaysColumnZeroOpponent(Opponent):
    """Keeps playing column 0 even after it fills — so the opponent's mask
    check, not just its range check, gets exercised."""

    def move(self, obs, mask, rng):
        return 0


def reset_seat(env, learner_first, max_seed=50):
    """Reset until the learner has the requested seat, detected from the
    observation alone (an empty board means the learner moves first). The
    first-player flip is random by design, so tests that need a specific seat
    must find one rather than assume one."""
    for seed in range(max_seed):
        obs, info = env.reset(seed=seed)
        if bool(obs.sum() == 0) == learner_first:
            return obs, info, seed
    raise AssertionError("could not find the requested seat")


def test_env_spaces_and_mask_contract():
    env = Connect4Env()
    assert env.observation_space.shape == (2, ROWS, COLS)
    assert env.observation_space.dtype == np.bool_
    assert env.action_space.n == COLS
    obs, info = env.reset(seed=0)
    assert env.observation_space.contains(obs)
    mask = info["action_mask"]
    assert mask.shape == (COLS,) and mask.dtype == np.bool_ and mask.all()


def test_learner_sees_its_own_discs_in_plane_zero():
    """Perspective site 1. The learner's own disc must land in plane 0."""
    env = Connect4Env(opponent="random")
    reset_seat(env, learner_first=True)
    obs, _, _, _, _ = env.step(3)
    assert obs[0].sum() == 1 and obs[0][0, 3], "learner's disc is not in plane 0"
    assert obs[1].sum() == 1, "opponent should have replied exactly once"


def test_opponent_sees_its_own_discs_in_plane_zero():
    """Perspective site 2 — the dangerous one. When the opponent is queried
    after the learner's first move, it must see an EMPTY plane 0 (it has no
    discs yet) and the learner's single disc in plane 1."""
    recorder = RecordingOpponent()
    env = Connect4Env(opponent=recorder)
    reset_seat(env, learner_first=True)
    env.step(3)
    assert len(recorder.seen) == 1
    seen = recorder.seen[0]
    assert seen[0].sum() == 0, "opponent sees the learner's disc as its own"
    assert seen[1].sum() == 1 and seen[1][0, 3]
    # And the round-trip: the board the opponent reconstructs has itself as
    # the player to move (+1), which is what HeuristicOpponent relies on.
    assert board_from_obs(seen)[0, 3] == -1


def test_reward_sign_follows_who_won():
    """Perspective site 3. A sign inversion here is the defect that makes a
    `return > 0` win rate read 1.000, which is why eval/win_rate comes from
    info["outcome"] instead."""
    # Learner wins: it plays column 0 four times, the scripted opponent
    # answers in column 1 and never interferes.
    env = Connect4Env(opponent=ScriptedOpponent([1, 1, 1, 1]))
    reset_seat(env, learner_first=True)
    for _ in range(3):
        obs, reward, terminated, _, info = env.step(0)
        assert reward == 0.0 and not terminated
    obs, reward, terminated, _, info = env.step(0)
    assert terminated and reward == 1.0 and info["outcome"] == 1

    # Opponent wins: it stacks column 1 while the learner plays elsewhere.
    # Columns 2,3,4,6 on purpose — 2,3,4,5 would be a horizontal four and the
    # LEARNER would win the test written for the opponent.
    env = Connect4Env(opponent=ScriptedOpponent([1, 1, 1, 1]))
    reset_seat(env, learner_first=True)
    for col in (2, 3, 4):
        obs, reward, terminated, _, info = env.step(col)
        assert reward == 0.0 and not terminated
    obs, reward, terminated, _, info = env.step(6)
    assert terminated and reward == -1.0 and info["outcome"] == -1


def test_terminal_next_obs_perspective_flips_with_who_ended_it():
    """Perspective site 4 — RECORDED, not fixed. After the learner's winning
    move the board has already negated, so the final observation is from the
    opponent's side; after the opponent's winning move it is from the
    learner's. Inert under PPO (compute_gae multiplies the bootstrap by
    1 - terminated, and this env never truncates), but it contradicts
    rollout.py's per-row invariant, so it is pinned here: any future consumer
    of terminal next_obs must come and read this test."""
    env = Connect4Env(opponent=ScriptedOpponent([1, 1, 1, 1]))
    reset_seat(env, learner_first=True)
    for _ in range(3):
        env.step(0)
    obs, _, terminated, _, _ = env.step(0)  # learner wins
    assert terminated
    # The winner's four discs sit in plane 1: the observation is the LOSER's.
    assert [bool(obs[1][r, 0]) for r in range(4)] == [True] * 4
    assert obs[0].sum() == 3, "plane 0 should hold the opponent's three discs"

    env = Connect4Env(opponent=ScriptedOpponent([1, 1, 1, 1]))
    reset_seat(env, learner_first=True)
    for col in (2, 3, 4):
        env.step(col)
    obs, _, terminated, _, _ = env.step(6)  # opponent wins (2,3,4,5 would be
    # the LEARNER's own horizontal four — the trap this test fell into once)
    assert terminated
    # Here the loser is the learner, and the observation is the learner's:
    # the winner's discs are in plane 1 again, but for the opposite reason.
    assert [bool(obs[1][r, 1]) for r in range(4)] == [True] * 4


def test_terminal_mask_is_all_true_not_all_false():
    """All-False is the intuitive encoding and it is wrong: masking.py
    asserts >= 1 legal action per row, and any consumer of next_mask hits it.
    PPO discards next_masks so this stayed invisible in a probe; the DQN path
    does consume them.

    The terminal position must have at least one FULL column, or the board's
    own legal_mask is already all-True and "emit all-True" is untested — a
    mutation replacing the special case with a plain legal_mask() survived a
    version of this test that won in an otherwise-empty board.
    """
    # A full board: legal_mask() would be all-FALSE here, the exact row that
    # trips masking.py's >= 1-legal assertion.
    env = Connect4Env(opponent=ScriptedOpponent(DRAW_42[1::2]))
    reset_seat(env, learner_first=True)
    for col in DRAW_42[0::2]:
        _, _, terminated, _, info = env.step(col)
    assert terminated and env.board.full()
    assert not env.board.legal_mask().any(), "fixture should end on a full board"
    assert info["action_mask"].all(), "terminal mask must be all-True, not all-False"

    # A win with one column full and others open: the mask must STILL be
    # all-True, not merely non-empty. The two sides alternate in column 0
    # until it holds six discs (so nobody wins there), then the opponent
    # stacks column 1 for the win while the learner spreads across 2,3,4,6 —
    # not 2,3,4,5, which would be the learner's own horizontal four.
    env = Connect4Env(opponent=ScriptedOpponent([0, 0, 0, 1, 1, 1, 1]))
    reset_seat(env, learner_first=True)
    for col in (0, 0, 0, 2, 3, 4):
        _, _, terminated, _, info = env.step(col)
        assert not terminated
    assert not env.board.legal_mask()[0], "column 0 should be full"
    _, reward, terminated, _, info = env.step(6)
    assert terminated and reward == -1.0
    assert not env.board.legal_mask().all(), "a column must still be full here"
    assert info["action_mask"].all(), "terminal mask must be all-True"


def test_illegal_learner_column_raises():
    env = Connect4Env(opponent="random")
    reset_seat(env, learner_first=True)
    for _ in range(3):
        env.step(0)  # 3 learner discs; the opponent may add more
    while env.board.legal_mask()[0]:
        env.step(0)
    with pytest.raises(ValueError, match="illegal column"):
        env.step(0)
    with pytest.raises(ValueError, match="illegal column"):
        env.step(COLS)  # out of range


def test_illegal_opponent_column_raises_loudly():
    """A silently-dropped illegal opponent move would read as a policy quirk
    rather than a bug. Both guards: out of range, and a full column."""
    env = Connect4Env(opponent=OutOfRangeOpponent())
    reset_seat(env, learner_first=True)
    with pytest.raises(ValueError, match="opponent chose illegal column"):
        env.step(3)

    # Learner and opponent alternate in column 0 until it holds six discs
    # (alternating, so nobody wins), then the opponent insists on it again.
    env = Connect4Env(opponent=AlwaysColumnZeroOpponent())
    reset_seat(env, learner_first=True)
    for _ in range(3):
        env.step(0)
    assert not env.board.legal_mask()[0], "column 0 should be full"
    with pytest.raises(ValueError, match="opponent chose illegal column"):
        env.step(1)


def test_outcome_is_only_emitted_at_terminal_and_in_domain():
    # A RANDOM learner against the random opponent: a fixed leftmost-legal
    # policy loses to `heuristic` essentially always, so the win outcome would
    # never be sampled and the domain assertion would be vacuous.
    env = Connect4Env(opponent="random")
    rng = np.random.default_rng(0)
    seen = set()
    for episode in range(200):
        obs, info = env.reset(seed=episode)
        assert "outcome" not in info
        done = False
        while not done:
            mask = info["action_mask"]
            action = int(rng.choice(np.flatnonzero(mask)))
            obs, reward, done, truncated, info = env.step(action)
            assert truncated is False, "this env never truncates"
            if not done:
                assert "outcome" not in info
                assert reward == 0.0
        assert info["outcome"] in (-1, 0, 1)
        assert float(info["outcome"]) == reward  # reward IS the outcome
        seen.add(info["outcome"])
    assert {-1, 1} <= seen


def test_observations_never_alias_the_board_or_each_other():
    env = Connect4Env(opponent="random")
    obs, _ = reset_seat(env, learner_first=True)[:2]
    assert not np.shares_memory(obs, env.board.board)
    next_obs, _, _, _, _ = env.step(3)
    assert obs is not next_obs
    assert not np.shares_memory(obs, next_obs)
    assert not np.shares_memory(next_obs, env.board.board)
    before = next_obs.copy()
    env.step(4)
    assert np.array_equal(next_obs, before), "a returned obs must not mutate later"


def test_env_draw_reports_outcome_zero():
    """The draw branch is 0.27% of random games and was never reached in 300
    eval episodes, so it is driven here by script."""
    env = Connect4Env(opponent=ScriptedOpponent(DRAW_42[1::2]))
    reset_seat(env, learner_first=True)
    reward = None
    for col in DRAW_42[0::2]:
        obs, reward, terminated, _, info = env.step(col)
    assert terminated and reward == 0.0 and info["outcome"] == 0
    assert env.board.full()


def test_env_win_on_the_final_disc_is_a_win_not_a_draw():
    """Win-before-full ordering, at the env level, on BOTH seats. The board
    is full and someone won; checking fullness first would report a draw."""
    # Learner second -> the learner plays the odd indices, so move 41 (the
    # winning one) is the learner's.
    env = Connect4Env(opponent=ScriptedOpponent(WIN_ON_42[0::2]))
    reset_seat(env, learner_first=False)
    for col in WIN_ON_42[1::2]:
        obs, reward, terminated, _, info = env.step(col)
    assert env.board.full()
    assert terminated and reward == 1.0 and info["outcome"] == 1

    # Learner first -> move 41 is the opponent's.
    env = Connect4Env(opponent=ScriptedOpponent(WIN_ON_42[1::2]))
    reset_seat(env, learner_first=True)
    for col in WIN_ON_42[0::2]:
        obs, reward, terminated, _, info = env.step(col)
    assert env.board.full()
    assert terminated and reward == -1.0 and info["outcome"] == -1


def test_both_seats_occur_and_are_roughly_balanced():
    env = Connect4Env(opponent="random")
    first = [bool(env.reset(seed=s)[0].sum() == 0) for s in range(400)]
    assert 0.4 < np.mean(first) < 0.6, f"first-player flip is skewed: {np.mean(first)}"


def test_truncation_path_is_exercised_by_a_time_limit():
    """truncated is always False on this env, so the path is dead here — and
    load-bearing in Phase 5, where poke-env sets truncated for forfeits, ties
    and timer losses. Force it with TimeLimit so the plumbing is proven."""
    env = gym.wrappers.TimeLimit(Connect4Env(opponent="random"), max_episode_steps=2)
    obs, info = env.reset(seed=0)
    for step in range(2):
        obs, reward, terminated, truncated, info = env.step(
            int(np.flatnonzero(info["action_mask"])[0])
        )
        if terminated:
            pytest.skip("episode ended on its own before the limit")
    assert truncated and not terminated
    assert "outcome" not in info, "a truncated game has no outcome"


def test_rng_draw_order_is_pinned():
    """One RNG stream has three consumers — the first-player flip,
    opponent.select(), and the heuristic's random fallback — and nothing but
    this test fixes their order. Reordering them silently changes every
    seeded result in the phase, so the golden values are deliberate: if this
    fails, the question is whether the reorder was intended, not whether the
    test is too strict."""
    env = Connect4Env(opponent="random")
    seats, replies = [], []
    for seed in range(8):
        obs, info = env.reset(seed=seed)
        seats.append(int(obs.sum() == 0))  # 1 = learner moves first
        obs, _, _, _, _ = env.step(int(np.flatnonzero(info["action_mask"])[0]))
        replies.append(int(np.flatnonzero(obs[1].any(axis=0))[-1]))
    # Both are pinned: the seat draw alone would not notice select() and the
    # opponent's draw swapping places in the stream.
    assert seats == [1, 0, 1, 1, 1, 1, 0, 1], f"first-player draws moved: {seats}"
    assert replies == [4, 5, 1, 0, 6, 5, 3, 4], f"opponent draws moved: {replies}"


# ----------------------------------------------------------------- opponents

def test_make_opponent_resolves_names_and_passes_objects_through():
    assert isinstance(make_opponent("random"), RandomOpponent)
    assert isinstance(make_opponent("heuristic"), HeuristicOpponent)
    obj = RandomOpponent()
    assert make_opponent(obj) is obj
    with pytest.raises(ValueError, match="unknown opponent"):
        make_opponent("alphabeta9")


def test_opponents_only_ever_play_legal_columns():
    rng = np.random.default_rng(0)
    for opponent in (RandomOpponent(), HeuristicOpponent()):
        env = Connect4Env(opponent=opponent)
        for episode in range(100):
            obs, info = env.reset(seed=episode)
            done = False
            while not done:  # the env raises on an illegal opponent column
                legal = np.flatnonzero(info["action_mask"])
                obs, _, done, _, info = env.step(int(rng.choice(legal)))


def test_heuristic_takes_the_win_and_blocks_the_threat():
    """Win-in-one takes priority over blocking: with both available it must
    win rather than defend."""
    opponent = HeuristicOpponent()
    rng = np.random.default_rng(0)

    # Opponent (plane 0) has three in column 0; it must complete the line.
    board = Connect4Board()
    for _ in range(3):
        board.board[board.height(0), 0] = 1
    obs = np.stack([board.board == 1, board.board == -1])
    assert opponent.move(obs, board.legal_mask(), rng) == 0

    # Learner (plane 1) has three in column 2 and the opponent has nothing:
    # the opponent must block.
    board = Connect4Board()
    for _ in range(3):
        board.board[board.height(2), 2] = -1
    obs = np.stack([board.board == 1, board.board == -1])
    assert opponent.move(obs, board.legal_mask(), rng) == 2

    # Both available: winning beats blocking.
    board = Connect4Board()
    for _ in range(3):
        board.board[board.height(0), 0] = 1
        board.board[board.height(2), 2] = -1
    obs = np.stack([board.board == 1, board.board == -1])
    assert opponent.move(obs, board.legal_mask(), rng) == 0


def test_random_opponent_ignores_the_observation():
    """Recorded, not celebrated. This is exactly why the rejected chunk gate
    ('beats random >= 90%') could not detect a wrong opponent perspective:
    with this opponent, the flipped and correct envs are bit-identical."""
    opponent = RandomOpponent()
    board = Connect4Board()
    obs = np.stack([board.board == 1, board.board == -1])
    mask = board.legal_mask()
    a = [opponent.move(obs, mask, np.random.default_rng(0)) for _ in range(50)]
    b = [opponent.move(obs[::-1], mask, np.random.default_rng(0)) for _ in range(50)]
    assert a == b


def test_opponents_are_frozen_at_the_install_point():
    """The no-training contract. Rule-based opponents no-op freeze(), but the
    env must still CALL it: chunk 2's AgentOpponent wraps a live network, and
    a snapshot that kept training would silently track the learner."""

    class FreezeRecorder(Opponent):
        def __init__(self):
            self.frozen = 0

        def move(self, obs, mask, rng):
            return int(np.flatnonzero(mask)[0])

        def freeze(self):
            self.frozen += 1

    opponent = FreezeRecorder()
    Connect4Env(opponent=opponent)
    assert opponent.frozen == 1, "the env must freeze the opponent it installs"


def test_select_is_called_once_per_episode():
    """Which member plays is drawn per EPISODE, never mid-game: an opponent
    that changed identity between plies would make the episode incoherent."""

    class CountingSelector(RandomOpponent):
        def __init__(self):
            self.selects = 0

        def select(self, rng):
            self.selects += 1
            return self

    opponent = CountingSelector()
    env = Connect4Env(opponent=opponent)
    for episode in range(5):
        obs, info = env.reset(seed=episode)
        done = False
        while not done:
            obs, _, done, _, info = env.step(int(np.flatnonzero(info["action_mask"])[0]))
    assert opponent.selects == 5


# ------------------------------------------------- the masking contract, for real

def test_ppo_masking_is_consistent_on_real_connect4_rollouts():
    """The silent-corruption case the masking contract was written for.

    With lr=0 the policy cannot move, so pi_new == pi_old and approx_kl is
    exactly 0.0 — UNLESS the epoch forward masks differently from the
    update-start recompute, in which case every importance ratio on a row
    carrying an illegal column is silently wrong. Connect 4 is the repo's
    first env that supplies genuinely varying masks in training, so this is
    the first time the check has any power at all: on the spine envs every
    mask is all-True and the same defect is undetectable by construction
    (asserted below, so the difference is recorded rather than assumed).
    """
    import torch
    from torch.distributions import Categorical

    from rl.agents.ppo import PPOAgent
    from rl.common.masking import masked_logits
    from rl.envs.make import make_vec_env

    torch.manual_seed(0)
    envs = make_vec_env("Connect4-v0", 0, 4, env_kwargs={"opponent": "heuristic"})
    agent = PPOAgent(
        envs.single_observation_space, envs.single_action_space, num_envs=4,
        device="cpu", lr=0.0, gamma=1.0, gae_lambda=0.95, rollout_steps=32,
        epochs=2, minibatches=2, clip_eps=0.2, entropy_coef=0.01,
        value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[16],
    )
    obs, infos = envs.reset(seed=0)
    masks = infos["action_mask"]
    seen_obs, seen_actions, seen_masks, metrics = [], [], [], {}
    for _ in range(32):
        actions = agent.act(obs, masks)
        seen_obs.append(obs.copy())
        seen_actions.append(actions.copy())
        seen_masks.append(masks.copy())
        next_obs, rewards, terminated, truncated, infos = envs.step(actions)
        next_masks = infos["action_mask"]
        metrics = agent.update(
            (obs, actions, rewards, next_obs, terminated, truncated, masks, next_masks)
        ) or metrics
        obs, masks = next_obs, next_masks
        done = terminated | truncated
        if done.any():
            obs, reset_infos = envs.reset(options={"reset_mask": done})
            masks = np.where(done[:, None], reset_infos["action_mask"], masks)

    assert metrics, "the rollout should have filled"
    assert abs(metrics["loss/approx_kl"]) < 1e-7, (
        f"masked-inconsistency drift: approx_kl={metrics['loss/approx_kl']}"
    )

    # Power. A test that cannot fail is not a test: measure how many rows
    # actually carry an illegal column, and how far the importance ratio
    # would move if the epoch forward dropped the mask.
    flat_masks = np.concatenate(seen_masks)
    illegal_rows = float(np.mean(~flat_masks.all(axis=-1)))
    assert illegal_rows > 0.02, f"only {illegal_rows:.1%} of rows carry an illegal column"

    obs_t = torch.as_tensor(np.concatenate(seen_obs), dtype=torch.float32)
    act_t = torch.as_tensor(np.concatenate(seen_actions))
    mask_t = torch.as_tensor(flat_masks)
    with torch.no_grad():
        logits = agent.actor(obs_t)
        masked_logp = Categorical(logits=masked_logits(logits, mask_t)).log_prob(act_t)
        unmasked_logp = Categorical(logits=logits).log_prob(act_t)
    max_ratio_error = float((masked_logp - unmasked_logp).exp().max())
    assert max_ratio_error > 1.2, (
        f"dropping the mask moves the ratio by at most {max_ratio_error:.3f}x — "
        "this probe would not detect it"
    )
    envs.close()


def test_the_same_mask_defect_is_invisible_on_an_all_true_env():
    """The control for the probe above, kept standing. On every Phase 0-3 env
    the mask is all-True, so masked and unmasked log-probs are bitwise equal
    and no rollout can distinguish a correct implementation from one that
    ignores the mask entirely. That is why the masking retrofit was provably
    a no-op there — and why it needed Connect 4 to be tested at all."""
    from rl.envs.make import make_vec_env

    envs = make_vec_env("CartPole-v1", 0, 4)
    obs, infos = envs.reset(seed=0)
    rows = []
    for _ in range(32):
        actions = np.array([envs.single_action_space.sample() for _ in range(4)])
        rows.append(infos["action_mask"].copy())
        obs, _, terminated, truncated, infos = envs.step(actions)
        done = terminated | truncated
        if done.any():
            obs, reset_infos = envs.reset(options={"reset_mask": done})
    stacked = np.concatenate(rows)
    assert stacked.all(), "a spine env supplied a non-trivial mask"
    assert float(np.mean(~stacked.all(axis=-1))) == 0.0
    envs.close()

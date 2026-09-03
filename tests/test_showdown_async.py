"""Unit coverage for the Stage-2 async collector (F-02). The invariants the
pre-reg's gates rest on — _finish's keep/discard rule and terminal reward,
the (turn, idx) label join, _prune's grace window and orphan aging, check(),
stats(), poll(), and the pause/resume gate invariant the module docstring
states — driven OFFLINE: both seats are built with start_listening=False
(the repo's established no-websocket Player construction, see
test_pool_pertag / test_showdown_env) and battles are duck-typed. Until this
file existed the only coverage was the live acceptance fleet, where a
regression surfaces as a gate breach hours into a run.

Coroutines are driven on poke-env's process-global POKE_LOOP exactly as
production does; every test that schedules one waits for it or cancels it,
so nothing leaks into later tests. No test here opens a socket."""

import asyncio
import concurrent.futures
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from poke_env.concurrency import POKE_LOOP

from rl.envs import showdown_async as sa
from rl.envs.showdown import _OPP_CHOICE_NONE, OBS_DIM
from rl.envs.showdown_async import AsyncCollector, _EpisodeBuilder
from rl.selfplay.pool import SnapshotPool

# No lane may ever use this seed: the pair as2s990001a/b is the tests'.
_SEED = 990001
_OFFLINE = {"start_listening": False}


class _Policy:
    """act_logp stand-in with the seam's contract: (obs [1, D], mask [1, A])
    -> ([1] actions, [1] logps). `logp` doubles as a weight stamp — the
    pause/resume tests change it between pause() and resume() and read it
    back off the rows."""

    def __init__(self, action=0, logp=-0.5):
        self.action = action
        self.logp = logp
        self.calls = 0

    def __call__(self, obs, mask):
        assert obs.shape == (1, OBS_DIM) and obs.dtype == np.float32
        assert mask.shape == (1, 10) and mask.dtype == np.bool_
        self.calls += 1
        return np.array([self.action]), np.array([self.logp], dtype=np.float32)


class _FakeMember:
    def __init__(self, action):
        self.action = action

    def move(self, obs, mask, rng):
        return self.action


class _FakePool(SnapshotPool):
    """isinstance(spec, SnapshotPool) is _make_opponent's dispatch test; the
    pool's own draw/report logic is pinned in test_selfplay_pool, not here."""

    def __init__(self, members):  # noqa: D107 — deliberately skips super()
        self.members = members
        self.reports = []

    def freeze(self):
        pass

    def select(self, rng):
        return self.members[0]

    def member_id(self, member):
        return self.members.index(member)

    def report(self, played, outcome):
        self.reports.append((played, outcome))


def _battle(tag, *, turn=1, finished=False, won=False, lost=False, wait=False):
    # `_wait` / `teampreview` are what poke-env's _handle_battle_request reads.
    return SimpleNamespace(
        battle_tag=tag, wait=wait, _wait=wait, teampreview=False,
        turn=turn, finished=finished, won=won, lost=lost,
    )


@pytest.fixture
def trio(monkeypatch):
    """The encode/mask/convert trio, patched where each module looks it up:
    showdown_async imports embed_battle BY NAME, so it needs its own patch;
    the two SinglesEnv statics are one class object shared by both."""
    zeros = lambda b, tc: np.zeros(OBS_DIM, np.float32)  # noqa: E731
    monkeypatch.setattr("rl.envs.showdown.embed_battle", zeros)
    monkeypatch.setattr("rl.envs.showdown_async.embed_battle", zeros)
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.get_action_mask",
        staticmethod(lambda b: np.ones(10, np.int64)),
    )
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.action_to_order",
        staticmethod(lambda a, b: SimpleNamespace(message=f"/choose {int(a)}")),
    )
    # PoolPlayer.choose_move resolves the order's identity unconditionally
    # and the real resolver reads a Battle; number the calls so a label join
    # can tell one decision from the next.
    counter = {"n": 100}

    def identity(order, battle):
        counter["n"] += 1
        return (1, counter["n"], 1)

    monkeypatch.setattr("rl.envs.showdown._order_identity", identity)


@pytest.fixture
def clock(monkeypatch):
    """A controllable monotonic clock for showdown_async ONLY. Patching
    time.monotonic globally would also move asyncio's loop clock on
    POKE_LOOP, which other tests share."""
    now = {"t": 1000.0}
    fake = SimpleNamespace(monotonic=lambda: now["t"], perf_counter=time.perf_counter)
    monkeypatch.setattr("rl.envs.showdown_async.time", fake)

    def advance(seconds):
        now["t"] += seconds
        return now["t"]

    return advance


def _collector(policy=None, opponent="random", *, concurrency=4, **kw):
    return AsyncCollector(
        policy if policy is not None else _Policy(),
        opponent,
        seed=_SEED,
        concurrency=concurrency,
        seat_kwargs_override=_OFFLINE,
        **kw,
    )


def _on_loop(coro, timeout=5.0):
    return asyncio.run_coroutine_threadsafe(coro, POKE_LOOP).result(timeout=timeout)


def _rows(builder, keys, *, version=0, action=0, logp=-0.5):
    for turn, idx in keys:
        builder.keys.append((turn, idx))
        builder.turn_counts[turn] = idx + 1
        builder.obs.append(np.zeros(OBS_DIM, np.float32))
        builder.masks.append(np.ones(10, bool))
        builder.actions.append(action)
        builder.logps.append(logp)
        builder.versions.append(version)
    return builder


# --- construction ----------------------------------------------------------


def test_seats_carry_the_timer_and_the_width_through_the_override(trio):
    col = _collector(concurrency=6)
    for player in (col.learner, col.opponent):
        assert player._start_timer_on_battle_start is True  # the orphan fix
        assert player._max_concurrent_battles == 6
        assert not hasattr(player.ps_client, "websocket")  # offline for real
    assert col.learner.username == f"as2s{_SEED}a"
    assert col.opponent.username == f"as2s{_SEED}b"
    assert col._pool_player is None


def test_override_may_not_touch_the_timer():
    with pytest.raises(ValueError, match="start_timer_on_battle_start"):
        AsyncCollector(
            _Policy(), "random", seed=_SEED, concurrency=1,
            seat_kwargs_override={**_OFFLINE, "start_timer_on_battle_start": False},
        )


def test_pool_opponent_wiring_and_the_opp_action_precondition(trio):
    pool = _FakePool([_FakeMember(2)])
    col = _collector(opponent=pool, opp_action=True)
    assert col._pool_player is col.opponent
    assert col.opponent._record_choices is True
    assert _collector(opponent=pool).opponent._record_choices is False
    with pytest.raises(ValueError, match="pool opponent"):
        _collector(opponent="random", opp_action=True)
    with pytest.raises(ValueError, match="unsupported async opponent"):
        _collector(opponent="nonsense")


# --- _finish ---------------------------------------------------------------


@pytest.mark.parametrize(
    "won, lost, outcome", [(True, False, 1), (False, True, -1), (False, False, 0)]
)
def test_finish_keeps_a_finished_episode_with_the_outcome_as_terminal_reward(
    trio, won, lost, outcome
):
    col = _collector()
    tag = "battle-gen1randombattle-1"
    _rows(col.builders.setdefault(tag, _EpisodeBuilder()),
          [(1, 0), (2, 0), (2, 1), (3, 0)], version=4, action=3, logp=-1.25)
    col._finish(_battle(tag, finished=True, won=won, lost=lost))

    assert col.episodes_finished == 1 and col.episodes_discarded == 0
    assert col.builders == {} and col._ended[-1][0] == tag
    (ep,) = col.poll()
    assert set(ep) == {"obs", "masks", "actions", "rewards", "old_logp", "version"}
    assert ep["obs"].shape == (4, OBS_DIM) and ep["obs"].dtype == np.float32
    assert ep["masks"].shape == (4, 10) and ep["masks"].dtype == np.bool_
    assert ep["actions"].dtype == np.int64 and ep["actions"].tolist() == [3] * 4
    assert ep["old_logp"].dtype == np.float32 and np.all(ep["old_logp"] == -1.25)
    assert ep["version"].dtype == np.int64 and ep["version"].tolist() == [4] * 4
    assert ep["rewards"].dtype == np.float32
    assert ep["rewards"].tolist() == [0.0, 0.0, 0.0, float(outcome)]  # tie is 0
    assert col.poll() == []


def test_finish_discards_when_no_builder_or_the_battle_did_not_finish(trio):
    col = _collector()
    # A room we never decided in (no builder) still ends and is tracked.
    col._finish(_battle("battle-gen1randombattle-1", finished=True, won=True))
    assert col.episodes_discarded == 1 and col.episodes_finished == 0
    # A builder whose room ended without a |win| is dropped, not emitted.
    tag = "battle-gen1randombattle-2"
    _rows(col.builders.setdefault(tag, _EpisodeBuilder()), [(1, 0)])
    col._finish(_battle(tag, finished=False))
    assert col.episodes_discarded == 2 and col.builders == {}
    assert col.poll() == []
    assert [t for t, _ in col._ended] == [
        "battle-gen1randombattle-1", "battle-gen1randombattle-2"
    ]


def test_finish_reports_the_outcome_to_the_member_that_played(trio):
    member = _FakeMember(1)
    pool = _FakePool([member])
    col = _collector(opponent=pool)
    b = _battle("battle-gen1randombattle-3")
    col.opponent.choose_move(b)  # sync seat-2 decision registers the entry
    b.finished, b.lost = True, True
    col._finish(b)
    assert pool.reports == [(member, -1)]  # learner-perspective outcome
    # A battle the pool never played in credits nobody (report pops).
    col._finish(_battle("battle-gen1randombattle-4", finished=True, won=True))
    assert pool.reports == [(member, -1)]


def test_finish_joins_opponent_choices_by_turn_and_index(trio):
    pool = _FakePool([_FakeMember(1)])
    col = _collector(opponent=pool, opp_action=True)
    tag = "battle-gen1randombattle-5"
    b = _battle(tag, turn=1)
    col.opponent.choose_move(b)  # (1, 0) -> (1, 101, 1)
    col.opponent.choose_move(b)  # (1, 1) -> (1, 102, 1), forced replacement
    b.turn = 2
    col.opponent.choose_move(b)  # (2, 0) -> (1, 103, 1)
    # The learner also replaced on turn 1 and decided alone on turn 3.
    _rows(col.builders.setdefault(tag, _EpisodeBuilder()),
          [(1, 0), (1, 1), (2, 0), (3, 0)])
    b.turn, b.finished, b.won = 3, True, True
    col._finish(b)
    (ep,) = col.poll()
    assert ep["opp_choice"].dtype == np.int32 and ep["opp_choice"].shape == (4, 3)
    assert ep["opp_choice"].tolist() == [
        [1, 101, 1], [1, 102, 1], [1, 103, 1], list(_OPP_CHOICE_NONE)
    ]
    assert col.opponent._choices == {} and col.opponent._turn_counts == {}


def test_finish_without_opp_action_emits_no_label_column(trio):
    col = _collector(opponent=_FakePool([_FakeMember(1)]))
    tag = "battle-gen1randombattle-6"
    _rows(col.builders.setdefault(tag, _EpisodeBuilder()), [(1, 0)])
    col._finish(_battle(tag, finished=True, won=True))
    (ep,) = col.poll()
    assert "opp_choice" not in ep


# --- choose_move (the learner seat, on POKE_LOOP) ---------------------------


def test_choose_move_keys_rows_by_turn_and_nth_decision(trio):
    policy = _Policy(action=7, logp=-0.75)
    col = _collector(policy)
    col.seam.version = 3
    tag = "battle-gen1randombattle-7"
    b = _battle(tag, turn=1)
    orders = [_on_loop(col.learner.choose_move(b)) for _ in range(2)]
    b.turn = 2
    orders.append(_on_loop(col.learner.choose_move(b)))

    assert [o.message for o in orders] == ["/choose 7"] * 3
    assert policy.calls == col.seam.requests == 3
    assert col.seam.inference_seconds > 0.0
    builder = col.builders[tag]
    assert builder.keys == [(1, 0), (1, 1), (2, 0)]
    assert builder.actions == [7] * 3 and builder.logps == [-0.75] * 3
    assert builder.versions == [3] * 3
    assert all(o.shape == (OBS_DIM,) for o in builder.obs)
    assert all(m.dtype == np.bool_ and m.all() for m in builder.masks)
    assert col.stats()["collect/battles_in_flight"] == 1.0


def test_choose_move_refuses_a_wait_state(trio):
    col = _collector()
    with pytest.raises(AssertionError, match="wait state"):
        _on_loop(col.learner.choose_move(_battle("battle-gen1randombattle-8", wait=True)))
    assert col.seam.requests == 0


def test_choose_move_counts_conversion_failures_and_check_raises(trio, monkeypatch):
    def boom(a, b):
        raise ValueError("out of mask")

    monkeypatch.setattr("rl.envs.showdown.SinglesEnv.action_to_order", staticmethod(boom))
    col = _collector()
    col.check()  # clean before
    with pytest.raises(ValueError, match="out of mask"):
        _on_loop(col.learner.choose_move(_battle("battle-gen1randombattle-9")))
    assert col.convert_errors == 1
    # The row was recorded before conversion — the failure is counted, not hidden.
    assert len(col.builders["battle-gen1randombattle-9"].actions) == 1
    with pytest.raises(AssertionError, match="failed conversion"):
        col.check()


# --- _prune ----------------------------------------------------------------


def test_prune_frees_finished_rooms_only_after_the_grace_window(trio, clock):
    col = _collector()
    tag = "battle-gen1randombattle-10"
    done = _battle(tag, finished=True, won=True)
    col.learner._battles[tag] = done
    col.opponent._battles[tag] = done
    late = _battle("battle-gen1randombattle-11", finished=False)
    col.learner._battles[late.battle_tag] = late
    col._finish(done)
    # Inside the grace window both maps keep the room (a late message's
    # _get_battle() must still find it).
    clock(sa._ROOM_GRACE_S - 1.0)
    col._prune()
    assert tag in col.learner._battles and tag in col.opponent._battles
    assert len(col._ended) == 1
    # Past it, the finished room leaves both maps; an unfinished one stays.
    clock(2.0)
    col._prune()
    assert tag not in col.learner._battles and tag not in col.opponent._battles
    assert len(col._ended) == 0
    assert late.battle_tag in col.learner._battles


def test_prune_ages_out_orphan_builders(trio, clock):
    col = _collector()
    _rows(col.builders.setdefault("battle-gen1randombattle-12", _EpisodeBuilder()), [(1, 0)])
    clock(sa._BUILDER_MAX_AGE_S - 1.0)
    _rows(col.builders.setdefault("battle-gen1randombattle-13", _EpisodeBuilder()), [(1, 0)])
    col._prune()
    assert set(col.builders) == {"battle-gen1randombattle-12", "battle-gen1randombattle-13"}
    clock(2.0)
    col._prune()
    assert set(col.builders) == {"battle-gen1randombattle-13"}
    assert col.episodes_discarded == 1 and col.poll() == []


# --- check / stats / poll / run_in_loop -------------------------------------


def test_check_passes_before_start_and_while_the_drive_runs(trio):
    col = _collector()
    col.check()
    col._drive = concurrent.futures.Future()  # pending stand-in
    col.check()


def test_check_raises_when_the_drive_is_done(trio):
    col = _collector()
    done = concurrent.futures.Future()
    done.set_result(None)
    col._drive = done
    with pytest.raises(RuntimeError, match="battle stream ended early: None"):
        col.check()
    failed = concurrent.futures.Future()
    failed.set_exception(OSError("socket gone"))
    col._drive = failed
    with pytest.raises(RuntimeError, match=r"ended early: OSError\('socket gone'\)"):
        col.check()


def test_stats_keys_and_values(trio):
    col = _collector()
    col.seam.requests, col.seam.inference_seconds = 12, 0.25
    col.episodes_finished, col.episodes_discarded = 3, 1
    col.builders["battle-gen1randombattle-14"] = _EpisodeBuilder()
    col.learner._battles["battle-gen1randombattle-14"] = _battle("battle-gen1randombattle-14")
    col._ended.append(("battle-gen1randombattle-15", 0.0))
    stats = col.stats()
    assert stats == {
        "collect/seam_requests": 12.0,
        "collect/inference_seconds": 0.25,
        "collect/episodes_finished": 3.0,
        "collect/episodes_discarded": 1.0,
        "collect/battles_in_flight": 1.0,
        "collect/rooms_tracked": 2.0,
        "collect/rerequests": 0.0,
    }
    assert all(isinstance(v, float) for v in stats.values())


def test_poll_drains_fifo_and_never_blocks(trio):
    col = _collector()
    assert col.poll() == []
    col._finished.extend([{"n": 0}, {"n": 1}, {"n": 2}])
    assert [e["n"] for e in col.poll()] == [0, 1, 2]
    assert col.poll() == [] and len(col._finished) == 0


def test_run_in_loop_executes_on_the_loop_thread_and_returns(trio):
    col = _collector()
    name = col.run_in_loop(lambda: threading.current_thread().name)
    assert name != threading.current_thread().name
    assert col.run_in_loop(lambda a, b: a + b, 2, 3) == 5


def test_close_is_safe_offline(trio):
    col = _collector()
    col.close()  # no drive, no websocket: best-effort teardown must not raise


# --- pause / resume gate invariant ------------------------------------------


def test_pause_holds_decisions_at_the_gate_until_resume(trio):
    policy = _Policy(logp=-1.0)
    col = _collector(policy)
    battles = [_battle(f"battle-gen1randombattle-2{i}") for i in range(3)]
    col.pause()
    futs = [
        asyncio.run_coroutine_threadsafe(col.learner.choose_move(b), POKE_LOOP)
        for b in battles
    ]
    try:
        with pytest.raises(TimeoutError):
            futs[0].result(timeout=0.2)
        # Nothing passed the gate: no request, no row, no builder.
        assert not any(f.done() for f in futs)
        assert col.seam.requests == 0 and policy.calls == 0 and col.builders == {}
        # The world is stopped, so the "weights" may move.
        policy.logp = -2.0
        col.resume(version=5)
        orders = [f.result(timeout=5.0) for f in futs]
    finally:
        for f in futs:
            f.cancel()
    assert [o.message for o in orders] == ["/choose 0"] * 3
    assert col.seam.version == 5 and col.seam.requests == 3
    for b in battles:
        builder = col.builders[b.battle_tag]
        assert builder.versions == [5] and builder.logps == [-2.0]  # post-resume


def test_pause_returns_only_once_in_flight_decisions_have_settled(trio):
    policy = _Policy(logp=-1.0)
    col = _collector(policy)
    battles = [_battle(f"battle-gen1randombattle-3{i}") for i in range(4)]
    futs = [
        asyncio.run_coroutine_threadsafe(col.learner.choose_move(b), POKE_LOOP)
        for b in battles
    ]
    try:
        col.pause()
        # The docstring's invariant, made concrete: after pause() returns
        # every decision has either completed (request counted AND row
        # appended, atomically — no await between them) or is parked at
        # the gate having done neither.
        settled = sum(f.done() for f in futs)
        rows = sum(len(b.actions) for b in col.builders.values())
        assert settled == col.seam.requests == rows == policy.calls
        policy.logp = -2.0
        col.resume(version=1)
        for f in futs:
            f.result(timeout=5.0)
    finally:
        for f in futs:
            f.cancel()
    assert col.seam.requests == 4
    for b in battles:
        builder = col.builders[b.battle_tag]
        # A row that carries the old version carries the old weights, and
        # one that carries the new version the new — never a mix.
        assert builder.versions in ([0], [1])
        assert builder.logps == [-1.0 if builder.versions == [0] else -2.0]


# --- in-loop liveness (F-03) ------------------------------------------------


def _pending():
    return concurrent.futures.Future()  # a live drive stand-in


def test_liveness_budget_default_and_override(trio):
    assert sa._LIVENESS_S == 900.0
    assert _collector()._liveness_s == 900.0
    assert _collector(liveness_s=30)._liveness_s == 30.0
    assert _collector(liveness_s=None)._liveness_s is None
    assert _collector(liveness_s=0)._liveness_s is None


def test_check_raises_after_the_budget_only_with_a_live_drive_and_an_open_gate(
    trio, clock
):
    col = _collector()
    col.learner._battles["battle-gen1randombattle-40"] = _battle("battle-gen1randombattle-40")
    col.builders["battle-gen1randombattle-40"] = _EpisodeBuilder()
    col.builders["battle-gen1randombattle-41"] = _EpisodeBuilder()
    clock(sa._LIVENESS_S + 1.0)
    col.check()  # not started: nothing to judge
    col._drive = _pending()
    with pytest.raises(RuntimeError, match=r"no decision for 901 s with 2 battles in flight"):
        col.check()
    with pytest.raises(RuntimeError, match=r"1 rooms held, 0 episodes finished"):
        col.check()
    # Paused: no progress is expected, so no verdict.
    col.pause()
    col.check()
    # Resume restarts the clock; the budget is judged from the resume.
    col.resume(version=1)
    col.check()
    clock(sa._LIVENESS_S - 1.0)
    col.check()
    clock(2.0)
    with pytest.raises(RuntimeError, match="no decision for 901 s"):
        col.check()


def test_liveness_disabled_never_raises(trio, clock):
    col = _collector(liveness_s=None)
    col._drive = _pending()
    clock(10 * sa._LIVENESS_S)
    col.check()


def test_a_completed_request_and_a_finish_mark_progress(trio, clock):
    col = _collector()
    col._drive = _pending()
    clock(sa._LIVENESS_S - 1.0)
    _on_loop(col.learner.choose_move(_battle("battle-gen1randombattle-42")))
    clock(sa._LIVENESS_S - 1.0)
    col.check()  # 899 s since the request completed, not 1798 since start
    col._finish(_battle("battle-gen1randombattle-42", finished=True, won=True))
    clock(sa._LIVENESS_S - 1.0)
    col.check()
    clock(2.0)
    with pytest.raises(RuntimeError, match="no decision for 901 s"):
        col.check()


def test_a_gated_request_does_not_count_as_progress(trio, clock):
    col = _collector()
    col._drive = _pending()
    col.pause()
    fut = asyncio.run_coroutine_threadsafe(
        col.learner.choose_move(_battle("battle-gen1randombattle-43")), POKE_LOOP
    )
    try:
        with pytest.raises(TimeoutError):
            fut.result(timeout=0.2)
        col.resume(version=0)
        resumed_at = clock(0.0)
        fut.result(timeout=5.0)
        # The mark is the completion on the loop thread, at or after resume.
        assert col._last_progress >= resumed_at
        clock(sa._LIVENESS_S + 1.0)
        with pytest.raises(RuntimeError, match="no decision for 901 s"):
            col.check()
    finally:
        fut.cancel()


def test_start_resets_the_clock_and_the_dead_drive_check_still_wins(trio, clock):
    col = _collector()
    parked = {"n": 0}

    async def fake_battle_against(opponent, n_battles):
        parked["n"] = n_battles
        await asyncio.sleep(3600)

    col.learner.battle_against = fake_battle_against
    clock(5 * sa._LIVENESS_S)  # construction-to-start latency is not idleness
    col.start(n_battles=17)
    try:
        assert parked["n"] == 0 or parked["n"] == 17  # scheduled, may not have run
        col.check()
        clock(sa._LIVENESS_S + 1.0)
        with pytest.raises(RuntimeError, match="no decision for 901 s"):
            col.check()
    finally:
        col._drive.cancel()
    # Once the drive has ended, that is the diagnosis — not the budget.
    col._drive = _pending()
    col._drive.set_exception(OSError("socket gone"))
    with pytest.raises(RuntimeError, match="battle stream ended early"):
        col.check()


# --- `[Invalid choice]` re-requests (F-19) ----------------------------------


def test_invalid_choice_rerequests_are_counted_and_keyed_as_a_second_row(trio):
    col = _collector()
    player = col.learner
    tag = "battle-gen1randombattle-77"
    b = _battle(tag, turn=3)
    player._battles[tag] = b  # what _get_battle() resolves the room to
    player.DEFAULT_CHOICE_CHANCE = 0.0  # never the 1/1000 default-order branch
    sent = []

    async def send_message(message, room=""):
        sent.append((message, room))

    player.ps_client.send_message = send_message

    _on_loop(player.choose_move(b))  # the decision the server then rejects
    assert col.rerequests == 0 and col.seam.requests == 1
    # The server's rejection, as PSClient splits it: room line, then the
    # error line poke-env branches on (player.py:318-325).
    _on_loop(player._handle_battle_message([
        [f">{tag}"],
        ["", "error", "[Invalid choice] Can't switch: You can't switch to a fainted Pokémon"],
    ]))
    assert col.rerequests == 1
    assert col.seam.requests == 2  # poke-env re-asked choose_move
    assert sent == [("/choose 0", tag)]  # and sent the retry to the room
    # Both rows stay in the episode; the retry is keyed (turn, 1).
    assert col.builders[tag].keys == [(3, 0), (3, 1)]
    assert col.stats()["collect/rerequests"] == 1.0
    # Other errors are not re-requests and are not counted.
    _on_loop(player._handle_battle_message([
        [f">{tag}"],
        ["", "error", "[Unavailable choice] Can't switch: The active Pokémon is trapped"],
        ["", "bigerror", "The battle has reached turn 1000"],
    ]))
    assert col.rerequests == 1 and col.seam.requests == 2

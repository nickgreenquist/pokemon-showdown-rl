"""The Stage-2 async collector (THROUGHPUT_SPEC §2): K concurrent battles
per lane, serviced as they become ready, with no lockstep barrier.

Why it exists: the SyncVectorEnv path is perfectly serialized — env i+1's
action is not even sent until env i's reply lands (E1: num_envs 1→16 flat at
523-550 steps/s), and ~54% of a vector step is idle round-trip wait (E3).
This module overlaps those waits: one learner Player and one opponent Player
run K battles between a single deterministic account pair, and every
decision is serviced the moment its request message arrives.

THE SHAPE IS THE MEASURED ONE, deliberately. E4b priced exactly this
configuration — one process, one account pair, `max_concurrent_battles=K`,
batch-1 inference serviced inline on POKE_LOOP — at 879 dec/s (K=1) → 1218
(K=8), flat to K=64, at entity width. The spec's original cross-thread
batched-drain seam is NOT built here: the knee is K=8, batch-1 servicing is
what the 1.55x end-to-end projection was priced on, and the seam contract
(rl/collect.py: coroutines submit to a seam and await) keeps batched
servicing an internals-only upgrade if it is ever worth its complexity.

Concurrency model, load-bearing facts only:
- Plain `Player`s share the singleton POKE_LOOP (a daemon thread); poke-env
  dispatches EVERY websocket message as its own asyncio task, so a decision
  awaiting the seam suspends only its own battle's message task.
- After the seam's gate, a decision (encode → forward → record → convert)
  runs WITHOUT an await, so it can never interleave with the update: the
  main thread pauses by clearing the gate and round-tripping a sleep(0)
  through the loop — once that returns, every in-flight decision has either
  completed or is suspended at the gate, and the weights are free to move.
- The loop thread itself is never blocked (updates gate tasks, not the
  loop), so websocket keepalive keeps running through an 11 s update.
- PokeEnv hardcodes max_concurrent_battles=1, which is why this is built on
  plain Player: the ShowdownEnv/PokeEnv EVAL path is untouched by
  construction, and the locked eval protocol survives untouched (G7).

Ops notes (the landmines this shape walks past):
- Both seats set start_timer_on_battle_start — a K-wide collector holds K
  rooms and leaked rooms are cumulative; without a timer requester Showdown
  never ends an abandoned room (THE ORPHANED-ROOM DEADLOCK, fixed
  2026-08-31). Slot accounting is explicit: `orphans` = battles started
  minus battles finished minus in-flight builders is readable from stats().
- Account names are DERIVED, never drawn from seeded global random:
  concurrent lanes with distinct --seeds get distinct pairs by construction
  (the username-collision landmine at scale).
- Finished Battle objects are pruned from both players' _battles maps after
  a grace window — a 50M-step lane plays ~2M battles and poke-env never
  forgets one on its own.
- A wedged stream is a LOUD failure, not an idle process (F-03): check()
  raises once no decision or finish has landed for _LIVENESS_S while the
  gate is open and the drive is alive. THE SILENT LANE STALL (landmines)
  is exactly the shape this loop otherwise produces — alive, zero CPU,
  sockets open, `poll()` empty forever — and only the wave's external
  CPU-delta probe saw it. Dying with a traceback is the desired outcome:
  the wave supervisor resumes dead lanes, the lane log carries the cause.
"""

import asyncio
import time
from collections import deque

import numpy as np

from poke_env.concurrency import POKE_LOOP
from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.player import Player
from poke_env.ps_client import AccountConfiguration

from rl.envs.showdown import (
    _OPP_CHOICE_NONE,
    MixturePlayer,
    OPPONENT_PLAYERS,
    PoolPlayer,
    _parse_mix,
    battle_outcome,
    embed_battle,
)
from rl.selfplay.pool import SnapshotPool

# How long a finished battle's objects and room bookkeeping are kept before
# pruning. Messages for a room stop arriving well inside this (the client
# leaves at |win|; the server's own room lifetime is minutes) — deleting too
# early would strand a late message's _get_battle() wait forever.
_ROOM_GRACE_S = 300.0
# A builder this old whose battle never finished belongs to a room that died
# without a |win| (orphan). Discarded and counted (G4: rate < 1%).
_BUILDER_MAX_AGE_S = 3600.0
# In-loop liveness budget (F-03): the longest gap between two progress marks
# (a seam request completing, a battle finishing) a healthy open-gate lane
# can show. A lane makes ~500+ decisions/s, so the legitimate gap is
# milliseconds; 900 s is > 30x the longest gap ever observed and, more to
# the point, longer than the 300 s/turn + 60 s grace challenge timer that
# resolves an orphaned room — if every one of K rooms orphaned at once, the
# timer forfeits them all inside ~360 s and finishes land as progress. What
# is left past 900 s is a wedged stream, which is what we want to die on.
_LIVENESS_S = 900.0


class GatedSeam:
    """The inference seam, gated for stop-the-world updates.

    All learner decisions funnel through request() (the rl/collect.py
    structural contract); the policy is called nowhere else in this module.
    `policy`: (obs [1, D], mask [1, A]) -> ([1] actions, [1] logp) — the
    agent's act_logp. Counters are loop-thread-only; `version` is written by
    the main thread strictly between pause() and resume(), when no request
    can be past the gate, so rows can never record a torn version.
    """

    def __init__(self, policy):
        self._policy = policy
        self.gate = asyncio.Event()
        self.gate.set()
        self.version = 0
        self.requests = 0
        self.inference_seconds = 0.0

    async def request(self, obs: np.ndarray, mask: np.ndarray) -> tuple[int, float]:
        if not self.gate.is_set():
            await self.gate.wait()
        t0 = time.perf_counter()
        actions, logps = self._policy(obs[None, :], mask[None, :])
        self.inference_seconds += time.perf_counter() - t0
        self.requests += 1
        return int(actions[0]), float(logps[0])


class _EpisodeBuilder:
    __slots__ = ("obs", "masks", "actions", "logps", "versions", "keys",
                 "turn_counts", "started_at")

    def __init__(self):
        self.obs: list[np.ndarray] = []
        self.masks: list[np.ndarray] = []
        self.actions: list[int] = []
        self.logps: list[float] = []
        self.versions: list[int] = []
        self.keys: list[tuple[int, int]] = []  # (turn, nth-decision-this-turn)
        self.turn_counts: dict[int, int] = {}
        self.started_at = time.monotonic()


class CollectPlayer(Player):
    """The learner seat: encode, ask the seam, record the row, convert.

    Same embed_battle / get_action_mask / action_to_order trio as every
    other collection route, so observations and legality are identical by
    construction (G1's precondition). action_to_order runs at poke-env's
    strict default: an action outside the mask RAISES (G2b) — the failure is
    counted, surfaces in check(), and the abandoned battle is timer-forfeited
    rather than silently randomized.
    """

    def __init__(self, collector: "AsyncCollector", **kwargs):
        super().__init__(**kwargs)
        self._collector = collector
        self._type_chart = GenData.from_format(self.format).type_chart

    async def choose_move(self, battle):
        col = self._collector
        seam = col.seam
        # Gate BEFORE encoding: a decision that sat out a pause encodes the
        # battle as it stands on resume, and everything from here to the
        # returned order runs without an await — the invariant pause() rests
        # on (no decision can straddle a weight change).
        if not seam.gate.is_set():
            await seam.gate.wait()
        # The Player path only requests decisions — a wait state here means
        # the harness contract broke, not that a pump is missing (G3).
        assert not battle.wait, "wait state reached the async learner"
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        assert mask.any(), "empty action mask (G2a)"
        action, logp = await seam.request(obs, mask)
        col._mark_progress()  # loop thread: the liveness clock (F-03)
        builder = col.builders.get(battle.battle_tag)
        if builder is None:
            builder = col.builders[battle.battle_tag] = _EpisodeBuilder()
        idx = builder.turn_counts.get(battle.turn, 0)
        builder.turn_counts[battle.turn] = idx + 1
        builder.keys.append((battle.turn, idx))
        builder.obs.append(obs)
        builder.masks.append(mask)
        builder.actions.append(action)
        builder.logps.append(logp)
        builder.versions.append(seam.version)
        try:
            return SinglesEnv.action_to_order(np.int64(action), battle)
        except ValueError:
            col.convert_errors += 1
            raise

    def _battle_finished_callback(self, battle):
        self._collector._finish(battle)


class AsyncCollector:
    """Owns the two players, the battle stream, and the finished-episode
    handoff. Constructed and driven from the MAIN thread; everything that
    touches battles or the pool runs on POKE_LOOP (via the message tasks, or
    through run_in_loop for main-thread callers like pool.push)."""

    def __init__(
        self,
        policy,
        opponent_spec,
        *,
        seed: int,
        concurrency: int,
        opp_action: bool = False,
        battle_format: str = "gen1randombattle",
        seat_kwargs_override: dict | None = None,
        liveness_s: float | None = _LIVENESS_S,
    ):
        self.seam = GatedSeam(policy)
        self.builders: dict[str, _EpisodeBuilder] = {}
        self._finished: deque = deque()  # loop thread appends, main thread pops
        self._ended: deque = deque()  # (battle_tag, monotonic) for room pruning
        self._opp_action = opp_action
        self.episodes_finished = 0
        self.episodes_discarded = 0
        self.convert_errors = 0
        self._drive = None
        # Liveness (F-03). `_last_progress` is written on the loop thread
        # (request completed, battle finished) and by start()/resume() on the
        # main thread; a float store is atomic under the GIL and both sides
        # write "now", so the race is benign. `_paused` is main-thread-only.
        # None / 0 disables the check.
        self._liveness_s = float(liveness_s) if liveness_s else None
        self._last_progress = time.monotonic()
        self._paused = False
        seat_kwargs = dict(
            battle_format=battle_format,
            max_concurrent_battles=concurrency,
            # Every connecting seat requests the timer (maintainer-ruled
            # 2026-08-31, wire-visible): without it an abandoned room never
            # ends and its queue slot never returns.
            start_timer_on_battle_start=True,
        )
        if seat_kwargs_override:
            # Test seam only (F-02): the unit tests build the collector with
            # `start_listening=False` — the repo's established offline Player
            # construction — so the bookkeeping runs with no websocket. The
            # timer is not overridable through it: it is the orphaned-room
            # fix, maintainer-ruled and wire-visible, never a test knob.
            if "start_timer_on_battle_start" in seat_kwargs_override:
                raise ValueError(
                    "seat_kwargs_override may not touch start_timer_on_battle_start"
                )
            seat_kwargs.update(seat_kwargs_override)
        self.learner = CollectPlayer(
            self,
            account_configuration=AccountConfiguration(f"as2s{seed}a", None),
            **seat_kwargs,
        )
        self.opponent = self._make_opponent(
            opponent_spec,
            account_configuration=AccountConfiguration(f"as2s{seed}b", None),
            **seat_kwargs,
        )
        self._pool_player = (
            self.opponent if isinstance(self.opponent, PoolPlayer) else None
        )
        if self._pool_player is not None:
            self._pool_player.seed_rng(seed)
            if opp_action:
                self._pool_player.record_choices()
        elif opp_action:
            raise ValueError(
                "opp_action=True needs a pool opponent: only a PoolPlayer "
                "records the D25 choice identities"
            )

    @staticmethod
    def _make_opponent(spec, **kwargs) -> Player:
        """The training-opponent surface, as LISTENING players (they own the
        second websocket here, unlike the sync path's in-env passengers)."""
        if isinstance(spec, SnapshotPool):
            return PoolPlayer(spec, **kwargs)
        if isinstance(spec, str) and spec.startswith("mix:"):
            return MixturePlayer(_parse_mix(spec), **kwargs)
        if isinstance(spec, str) and spec in OPPONENT_PLAYERS:
            return OPPONENT_PLAYERS[spec](**kwargs)
        raise ValueError(f"unsupported async opponent spec {spec!r}")

    # ---- battle lifecycle (loop thread) -----------------------------------

    def _finish(self, battle) -> None:
        self._mark_progress()
        tag = battle.battle_tag
        builder = self.builders.pop(tag, None)
        if self._pool_player is not None:
            self._pool_player.report_outcome(battle_outcome(battle), tag)
        opp_map = (
            self._pool_player.take_choices(tag) if self._opp_action else None
        )
        if builder is None or not battle.finished:
            self.episodes_discarded += 1
        else:
            length = len(builder.actions)
            rewards = np.zeros(length, dtype=np.float32)
            rewards[-1] = float(battle_outcome(battle))  # tie scores 0 (G4c)
            episode = {
                "obs": np.asarray(builder.obs, dtype=np.float32),
                "masks": np.asarray(builder.masks, dtype=np.bool_),
                "actions": np.asarray(builder.actions, dtype=np.int64),
                "rewards": rewards,
                "old_logp": np.asarray(builder.logps, dtype=np.float32),
                "version": np.asarray(builder.versions, dtype=np.int64),
            }
            if self._opp_action:
                episode["opp_choice"] = np.array(
                    [opp_map.get(key, _OPP_CHOICE_NONE) for key in builder.keys],
                    dtype=np.int32,
                )
            self.episodes_finished += 1
            self._finished.append(episode)
        self._ended.append((tag, time.monotonic()))
        self._prune()

    def _mark_progress(self) -> None:
        self._last_progress = time.monotonic()

    def _prune(self) -> None:
        now = time.monotonic()
        while self._ended and now - self._ended[0][1] > _ROOM_GRACE_S:
            tag, _ = self._ended.popleft()
            for player in (self.learner, self.opponent):
                stale = player._battles.get(tag)
                if stale is not None and stale.finished:
                    del player._battles[tag]
        # Builders whose room died without a |win| (orphan): drop and count.
        for tag, builder in list(self.builders.items()):
            if now - builder.started_at > _BUILDER_MAX_AGE_S:
                del self.builders[tag]
                self.episodes_discarded += 1

    # ---- main-thread API ---------------------------------------------------

    def start(self, n_battles: int) -> None:
        # The clock starts here, not at construction: login, the challenge
        # handshake and the first request all count against the budget and
        # take seconds, not minutes.
        self._last_progress = time.monotonic()
        self._drive = asyncio.run_coroutine_threadsafe(
            self.learner.battle_against(self.opponent, n_battles=n_battles),
            POKE_LOOP,
        )

    def poll(self) -> list[dict]:
        """Drain finished episodes (never blocks)."""
        episodes = []
        while True:
            try:
                episodes.append(self._finished.popleft())
            except IndexError:
                return episodes

    def check(self) -> None:
        """Fail loudly instead of collecting forever on a dead OR wedged
        stream. A dead drive is the specific diagnosis and comes first; the
        liveness budget catches the stall shape a live drive can still
        produce (battle_against parked on a queue slot that never returns).
        """
        assert self.convert_errors == 0, (
            f"{self.convert_errors} in-mask actions failed conversion (G2b) — "
            "a masking bug, not a recoverable hiccup"
        )
        if self._drive is None:
            return
        if self._drive.done():
            exc = self._drive.exception()  # raises CancelledError if cancelled
            raise RuntimeError(f"battle stream ended early: {exc!r}")
        # Liveness (F-03). Only while the gate is open: no progress is
        # expected during a pause (updates and evals are pauses) and resume()
        # restarts the clock. False positives considered: startup/login
        # latency (the clock starts at start(); seconds, not minutes); all K
        # rooms orphaned at once (the challenge timer forfeits each within
        # ~360 s and every |win| is a finish, so progress resumes well inside
        # the budget); a process-wide freeze longer than the budget (SIGSTOP,
        # the box thrashing) — that one trips it, and dying is the RIGHT
        # answer there too: the wave supervisor resumes dead lanes, and the
        # CPU-delta watch stays the outer layer for everything this cannot
        # see (a wedged main thread never reaches this line).
        if self._liveness_s is not None and not self._paused:
            idle = time.monotonic() - self._last_progress
            if idle > self._liveness_s:
                raise RuntimeError(
                    f"collector: no decision for {idle:.0f} s with "
                    f"{len(self.builders)} battles in flight "
                    f"({len(self.learner._battles)} rooms held, "
                    f"{self.episodes_finished} episodes finished, "
                    f"{self.seam.requests} requests served) — the battle "
                    f"stream is wedged (THE SILENT LANE STALL shape); dying "
                    f"so the lane can be resumed instead of idling forever"
                )

    def pause(self) -> None:
        """Stop the world for an update/eval. After this returns, no decision
        is between the gate and its row append, so the policy may change."""
        self._paused = True  # liveness is not judged while the gate is shut
        POKE_LOOP.call_soon_threadsafe(self.seam.gate.clear)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), POKE_LOOP).result()

    def resume(self, version: int) -> None:
        self.seam.version = version
        self._last_progress = time.monotonic()  # the pause was not idleness
        self._paused = False
        POKE_LOOP.call_soon_threadsafe(self.seam.gate.set)

    def run_in_loop(self, fn, *args):
        """Run fn on POKE_LOOP and wait — the mutation fence for shared
        objects the loop thread also reads (pool.push while battles select
        members; pool.stats while reports accrue)."""

        async def call():
            return fn(*args)

        return asyncio.run_coroutine_threadsafe(call(), POKE_LOOP).result()

    def stats(self) -> dict[str, float]:
        # len() of both containers is atomic under the GIL; iterating _ended
        # here (main thread) raced _finish's append (loop thread) — CPython's
        # "deque mutated during iteration" — and stats() runs in the paused
        # block, which the battle-end callback does not respect. Bounded:
        # _ended is pruned to the grace window.
        started = len(self.learner._battles) + len(self._ended)
        return {
            "collect/seam_requests": float(self.seam.requests),
            "collect/inference_seconds": self.seam.inference_seconds,
            "collect/episodes_finished": float(self.episodes_finished),
            "collect/episodes_discarded": float(self.episodes_discarded),
            "collect/battles_in_flight": float(len(self.builders)),
            "collect/rooms_tracked": float(started),
        }

    def close(self) -> None:
        if self._drive is not None:
            self._drive.cancel()
        for player in (self.learner, self.opponent):
            try:
                asyncio.run_coroutine_threadsafe(
                    player.ps_client.stop_listening(), POKE_LOOP
                ).result(timeout=10)
            except Exception:
                pass  # best effort — the process is exiting anyway

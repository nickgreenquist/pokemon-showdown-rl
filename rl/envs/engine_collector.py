"""`EngineCollector` — the in-process gen-1 collector behind `rl/train.py`'s
existing collector seam (docs/PKMN_ENGINE_RUST_PLAN.md §8.1).

NOT LICENSED. Gate A-1 has not run, so no number this produces is comparable to
anything banked: `collector.mode: engine` is a NEW INSTRUMENT until A-1 says
otherwise, and D-1 (engine vs server dynamics) has not run either.

What the seam is, and why this class is small: `_async_loop` drives a collector
through `seam.version`, `seam.requests`, `seam.inference_seconds`, `start`,
`poll`, `check`, `pause`, `resume`, `run_in_loop`, `stats`, `close`. The async
collector needs all of that because K battles live on a background event loop
and the learner's weights change under them. Here there is NO loop thread and
nothing is ever in flight between polls: one `poll()` runs one batched engine
step and returns. So `pause`/`resume` are gate bookkeeping only and
`run_in_loop(fn)` is `fn()` — the invariant they exist to protect ("no decision
straddles a weight change") holds by construction.

Two seats, one process:

  * the LEARNER's rows go through `policy` (the agent's `act_logp`), batched
    across every slot that owes a decision this step — one forward per poll.
  * the OPPONENT is the snapshot pool. A member is drawn per BATTLE at slot
    restart (`SnapshotPool.select`, the per-episode rule the env path uses) and
    plays through `AgentOpponent.move_batch`, GROUPED BY MEMBER: one forward per
    distinct member per step rather than one per row (plan §8.2).

Borrowed: pkmn/engine (MIT, https://github.com/pkmn/engine), vendored and pinned
in `engine/pkmn_gen1/vendor/pkmn-engine`.
"""

from __future__ import annotations

import pathlib
import time
from collections import defaultdict

import numpy as np

from rl.envs.engine_bank import read_bank
from rl.selfplay.pool import SnapshotPool

# The learner's rows are recorded with this many fields per D25 label; mirrors
# rl.envs.showdown.OPP_CHOICE_DIM and rl.networks.opp_action.CHOICE_DIM.
OPP_CHOICE_DIM = 3


def engine_metadata(team_bank) -> dict:
    """Which engine build, which team bank, which static tables — everything a
    reader needs to know an engine-collected run came from the same game as the
    next one. Stamped into `meta.yaml` at launch (`rl/train.py::_write_meta`),
    so it is recorded even for a run that dies before its first checkpoint.

    `team_bank` is a path or an already-read header dict.
    """
    import pkmn_gen1

    from rl.envs.engine_tables import fingerprint

    header = (
        team_bank
        if isinstance(team_bank, dict)
        else read_bank(pathlib.Path(team_bank))[0]
    )
    info = pkmn_gen1.build_info()
    return {
        "engine_sha": info["engine_sha"],
        "engine_options": info.get("options"),
        "zig_version": info["zig"],
        "crate_version": info["crate_version"],
        "team_bank_sha256": header["sha256"],
        "team_bank_pairs": header["pairs"],
        "team_bank_ps_commit": header["ps_commit"],
        "tables_fingerprint": fingerprint(),
    }


class _Seam:
    """The counter block `_async_loop` reads. No gate: nothing is in flight
    between polls, so there is nothing to gate."""

    def __init__(self):
        self.version = 0
        self.requests = 0
        self.inference_seconds = 0.0


class EngineCollector:
    """K engine battles stepped in lockstep; whole finished episodes out.

    `policy`: `(obs [B, D], mask [B, A]) -> ([B] actions, [B] logp)` — the
    agent's `act_logp`, the one place a learner decision is made (the
    `rl/collect.py` structural contract the async seam also keeps).
    """

    def __init__(
        self,
        policy,
        opponent_spec,
        *,
        seed: int,
        k: int,
        team_bank: str | pathlib.Path,
        learner_seat: str = "p1",
        opp_action: bool = False,
        max_updates_per_battle: int = 8000,
        battle_counter: int = 0,
    ):
        import pkmn_gen1

        from rl.envs.engine_tables import build_tables

        if not isinstance(opponent_spec, SnapshotPool):
            raise ValueError(
                f"engine collector opponent {opponent_spec!r} is not supported; "
                "self-play against a SnapshotPool is the only wired opponent "
                "(scripted opponents live in rl/envs/engine_scripted.py and are "
                "for eval and gate D-1, not for training)"
            )
        self.pool = opponent_spec
        self.seam = _Seam()
        self._policy = policy
        self._opp_action = bool(opp_action)
        self._max_updates = int(max_updates_per_battle)

        tables, self.tables_fingerprint = build_tables()
        self.bank_header, payload = read_bank(pathlib.Path(team_bank))
        # `battle_counter` at CONSTRUCTION, not after: the k battles in flight
        # are drawn here, so a resumed lane that set it later would replay its
        # first k battles -- same seeds, same teams -- before it took effect.
        self.env = pkmn_gen1.BatchEnv(
            k, int(seed), tables, payload, learner_seat, int(battle_counter)
        )
        self.build_info = pkmn_gen1.build_info()

        # Slot -> the member playing it, for this battle's whole life. Held by
        # OBJECT, not by push id: `SnapshotPool.report`/`member_id` match on
        # identity so a member evicted mid-battle silently moves no counter,
        # and holding the id instead would credit a DIFFERENT member's row.
        self._seated: list[object | None] = [None] * k
        # The pool's own per-episode draw stream. One generator for the lane,
        # seeded off the lane seed: the env path draws from the env's episode
        # RNG, which does not exist here.
        self._rng = np.random.default_rng(seed)

        self.k = k
        self.episodes_finished = 0
        self.opponent_inference_seconds = 0.0
        self.engine_steps = 0
        self._paused = False
        self._started = False
        self._last_finish_step = 0
        self._seat_all()

    # ---- opponent seating -------------------------------------------------

    def _seat_all(self) -> None:
        for slot in range(self.k):
            self._seat(slot)

    def _seat(self, slot: int) -> None:
        """Draw the member that plays this slot's next battle. Called once per
        battle, never per step — the per-EPISODE rule the env path uses."""
        member = self.pool.select(self._rng)
        self._seated[slot] = member
        self.env.set_member(slot, self.pool.member_id(member))

    # ---- the seam ---------------------------------------------------------

    def start(self, n_battles: int) -> None:
        """No-op but for the clock: battles are already in flight from
        construction (a slot is never empty). `n_battles` is the async path's
        challenge budget and has no meaning here — the loop stops on steps."""
        self._started = True
        self._t0 = time.perf_counter()

    def check(self) -> None:
        """F-03's spirit without a liveness clock: nothing here can hang on a
        socket, so the failure shape is a battle that never ends. The engine
        enforces the 1000-turn tie and Endless Battle Clause itself and
        `Gen1Env` bounds updates per battle; this re-checks the bound at the
        collector level so a wedged slot raises where the loop can see it."""
        stale = self.engine_steps - self._last_finish_step
        if stale > self._max_updates:
            raise RuntimeError(
                f"{stale} engine steps across {self.k} slots with no battle "
                f"finishing (bound {self._max_updates}); a slot is not "
                "terminating. `Gen1Env` raises on its own per-battle bound, so "
                "reaching this one means every slot is stuck at once."
            )

    def poll(self) -> list[dict]:
        """One batched step; the finished episodes it produced.

        The ONLY place work happens. Returns `[]` when the step finished no
        battle, which the loop treats as "nothing yet" — it sleeps 20 ms on an
        empty poll, so the engine path must not make empty polls common. It
        does not: at K=256 a step finishes ~2 battles on average.
        """
        if self._paused:
            return []
        l_idx, l_obs, l_mask, _l_member = self.env.pending("learner")
        o_idx, o_obs, o_mask, o_member = self.env.pending("opponent")

        t0 = time.perf_counter()
        if len(l_idx):
            l_actions, l_logp = self._policy(l_obs, l_mask)
        else:
            l_actions, l_logp = np.empty(0, np.int64), np.empty(0, np.float32)
        self.seam.inference_seconds += time.perf_counter() - t0
        self.seam.requests += len(l_idx)

        o_actions = self._opponent_actions(o_idx, o_obs, o_mask, o_member)

        self.env.step(
            [int(i) for i in l_idx],
            [int(a) for a in l_actions],
            [float(p) for p in l_logp],
            int(self.seam.version),
            [int(i) for i in o_idx],
            [int(a) for a in o_actions],
        )
        self.engine_steps += 1

        out = []
        for raw in self.env.drain_finished():
            out.append(self._episode(raw))
            slot = int(raw["slot"])
            played = self._seated[slot]
            if played is not None:
                # Learner-perspective outcome, credited to the member that
                # played — the same call `PoolPlayer` makes at a battle end.
                self.pool.report(played, int(raw["reward"]))
            self._seat(slot)
        self.episodes_finished += len(out)
        if out:
            self._last_finish_step = self.engine_steps
        return out

    def pause(self) -> None:
        self._paused = True

    def resume(self, version: int) -> None:
        self.seam.version = version
        self._paused = False

    def run_in_loop(self, fn, *args):
        """There is no loop thread: pool pushes and stat reads are ordinary
        main-thread calls, and `poll()` cannot be mid-decision when this runs."""
        return fn(*args)

    def stats(self) -> dict[str, float]:
        s = self.env.stats()
        return {
            "collect/seam_requests": float(self.seam.requests),
            "collect/inference_seconds": self.seam.inference_seconds,
            "collect/episodes_finished": float(s["episodes_finished"]),
            "collect/episodes_discarded": float(s["episodes_discarded"]),
            "collect/battles_in_flight": float(s["battles_in_flight"]),
            "collect/rooms_tracked": float(s["rooms_tracked"]),
            "collect/rerequests": float(s["rerequests"]),
            "collect/engine_updates": float(s["engine_updates"]),
            "collect/opponent_inference_seconds": self.opponent_inference_seconds,
        }

    def close(self) -> None:
        """Nothing to close: no sockets, no threads, no child processes."""

    # ---- resume -----------------------------------------------------------

    @property
    def battle_counter(self) -> int:
        """How many battles this lane has STARTED. Persisted in the checkpoint
        so `--resume` continues the seeded battle sequence instead of replaying
        the first K battles of the run (plan §7.5: `battle_seed =
        splitmix64(lane_seed * PHI ^ battle_counter)`)."""
        return int(self.env.battle_counter)

    @battle_counter.setter
    def battle_counter(self, n: int) -> None:
        """Where the NEXT battle comes from. The battles already in flight keep
        the seeds they were drawn with, so a RESUME must pass the counter to
        `__init__` instead of assigning here."""
        self.env.battle_counter = int(n)

    def metadata(self) -> dict:
        """What a run must record to be reproducible from its own artifacts."""
        return engine_metadata(self.bank_header)

    # ---- internals --------------------------------------------------------

    def _opponent_actions(self, idx, obs, mask, member_ids) -> np.ndarray:
        """One forward per DISTINCT MEMBER, not per row (plan §8.2).

        Rows are grouped by the member seated on their slot. With
        `latest_prob 0.8` most rows land in one group; the long tail of 1-3 row
        groups is what T-1 measures and, if it bites, what K=512 or batch-1
        servicing fixes. Ordering inside a group is slot order, which is the
        order `pending()` returns, so a member's generator stream is a function
        of (lane seed, pool state) alone.
        """
        n = len(idx)
        actions = np.zeros(n, dtype=np.int64)
        if n == 0:
            return actions
        # Keyed by the member OBJECT (identity hashing, the same match
        # `SnapshotPool.report` uses). Insertion order follows slot order, so
        # the group order is a function of the lane seed alone.
        by_member: dict[object, list[int]] = defaultdict(list)
        for row, slot in enumerate(idx):
            member = self._seated[int(slot)]
            if member is None:
                raise RuntimeError(f"slot {int(slot)} owes a decision with no member seated")
            by_member[member].append(row)

        t0 = time.perf_counter()
        for member, rows in by_member.items():
            r = np.asarray(rows)
            actions[r] = member.move_batch(obs[r], mask[r])
        self.opponent_inference_seconds += time.perf_counter() - t0
        # A member is never asked for an action outside the mask; an engine-side
        # legality error would be a hard failure at step(), but catching it here
        # names the seat.
        if not mask[np.arange(n), actions].all():
            raise RuntimeError("the opponent chose an action outside its mask")
        return actions

    def _episode(self, raw: dict) -> dict:
        """The Rust episode dict -> `EpisodeDataset`'s key set. `rewards` is
        the async path's shape: zeros with the outcome on the last row (ties
        score 0, G4c), because per-episode GAE bootstraps the terminal to 0."""
        n = int(raw["length"])
        rewards = np.zeros(n, dtype=np.float32)
        rewards[-1] = float(raw["reward"])
        episode = {
            "obs": np.asarray(raw["obs"], dtype=np.float32),
            "masks": np.asarray(raw["masks"], dtype=np.bool_),
            "actions": np.asarray(raw["actions"], dtype=np.int64),
            "rewards": rewards,
            "old_logp": np.asarray(raw["old_logp"], dtype=np.float32),
            "version": np.asarray(raw["version"], dtype=np.int64),
        }
        if self._opp_action:
            episode["opp_choice"] = np.asarray(raw["opp_choice"], dtype=np.int32)
        return episode

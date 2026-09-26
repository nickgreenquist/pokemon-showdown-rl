"""R7 B4a -- the ASYNCHRONOUS TWO-CORE LANE's collector: `EngineCollector`, the
snapshot pool and the learner's own policy copy run in a CHILD PROCESS on a
second core, so collection never stops for an update (plan §5: wall =
max(update, collection) instead of their sum; amendment box 3 items 1 and 5).

The seam `rl/train.py::_async_loop` drives is kept -- `seam.version`, `start`,
`check`, `poll`, `pause`, `resume(version)`, `stats`, `close`,
`battle_counter`, `metadata` -- with two differences that ARE the design:

  * `resume(version)` SHIPS THE WEIGHTS (actor and critic state dicts) to the
    child when the version moved; the child applies them between engine steps
    and stamps every later row with the new version. Rows collected while the
    learner updated carry the previous version, so PPO's ratio corrects them
    exactly as it does today for the pool (`old_logp` at act time), and
    `collect/policy_version_lag_max` -- the plan's `collect/weights_lag_updates`
    -- reads at most 1 by construction:
  * BACKPRESSURE, the "bound of one update": the child stops stepping once it
    holds `max_steps_ahead` rows the learner has not drained (default: one
    rollout budget), so it is never more than ONE batch ahead of consumption
    and never runs two updates behind. `collect/child_idle_frac` says how often
    that bound bound.

The pool LIVES IN THE CHILD (members play there); the parent talks to it
through explicit RPCs -- `push`, `pool_state`, `pool_stats` -- serviced by the
child between engine steps, which is the fence `run_in_loop` used to be.
`run_in_loop` itself is refused: a closure over a parent-side pool would be a
different pool.

SEED DISCIPLINE (REPLY BOX 2 §4, rule 2): the child owns the env seed, the
member-draw stream and its own global torch/numpy streams, all derived from
the LANE seed; the learner never re-seeds them. QoS: normal everywhere --
`taskpolicy` is barred in the fleet path (amendment 3 item 1; a background
process lands on the efficiency cores at 6.8x), and this constructor REFUSES
a background QoS unless `allow_background_qos` is set (tests that run niced
beside a fleet). Weights and episodes travel by pickle over a pipe and a queue
(~10 MB per update at the W recipe, ~1 MB per episode batch): negligible
against a 30 s update.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from types import SimpleNamespace
from typing import Any

import numpy as np


class _Seam:
    def __init__(self):
        self.version = 0
        self.requests = 0
        self.inference_seconds = 0.0


def qos_is_background() -> bool:
    """macOS: `taskpolicy -b` marks the process background; PRIO_DARWIN_PROCESS
    (4) then reads non-zero. False on other platforms."""
    try:
        return os.getpriority(4, 0) != 0
    except (OSError, AttributeError):
        return False


def _state(net) -> dict[str, Any]:
    import torch

    return {k: v.detach().to("cpu").clone() for k, v in net.state_dict().items()}


# ---------------------------------------------------------------------------
# The child.
# ---------------------------------------------------------------------------

def _child_main(conn, ep_queue, spec: dict) -> None:  # pragma: no cover - runs in the child
    import torch

    from rl.common.config import Config
    from rl.common.seeding import set_seed
    from rl.envs.engine_collector import EngineCollector
    from rl.envs.showdown import fake_spaces
    from rl.selfplay.pool import SnapshotPool
    from rl.train import make_agent

    torch.set_num_threads(int(spec["torch_threads"]))
    cfg = Config(**spec["cfg"])
    obs_space, act_space = fake_spaces()
    spaces = SimpleNamespace(observation_space=obs_space, action_space=act_space)
    # The learner's mirror (decisions; the T-op's evaluator in B4b) and a push
    # template. Construction consumes the global stream; the lane seed is
    # re-applied AFTER it so the sampling stream is a function of the lane seed
    # alone (the equivalence test pins this against the in-process collector).
    agent = make_agent(cfg, spaces)
    agent.actor.load_state_dict(spec["actor"]); agent.critic.load_state_dict(spec["critic"])
    template = make_agent(cfg, spaces)
    pool = SnapshotPool(int(spec["pool_size"]), float(spec["latest_prob"]))
    pool.load_state_dict(spec["pool_state"], agent_factory=lambda: make_agent(cfg, spaces))
    collector = EngineCollector(
        agent.act_logp, pool,
        seed=int(spec["seed"]), k=int(spec["k"]), team_bank=spec["team_bank"],
        learner_seat=spec["learner_seat"], opp_action=bool(spec["opp_action"]),
        privileged=bool(spec["privileged"]), both_views=bool(spec["both_views"]),
        battle_counter=int(spec["battle_counter"]), outcome_targets=bool(spec["outcome_targets"]),
    )
    if spec.get("search") is not None:
        # R7 B4b: the T-op on the child's mirror agent -- its critic is the
        # leaf evaluator, refreshed with every weights message.
        from rl.search.tree_top import searcher_class

        collector.searcher = searcher_class(spec["search"])(agent, collector.tables, seat=spec["learner_seat"],
                                                            seed=int(spec["seed"]) + 1, **spec["search"])
    set_seed(int(spec["seed"]))
    conn.send(("ready", {
        "build_info": collector.build_info, "tables_fingerprint": collector.tables_fingerprint,
        "bank_header": collector.bank_header, "pid": os.getpid(),
    }))
    started = paused = False
    version = int(spec["version"])
    produced = consumed = 0
    polls = idle_polls = 0
    max_ahead = int(spec["max_steps_ahead"])
    while True:
        while conn.poll():
            msg = conn.recv()
            kind = msg[0]
            if kind == "start":
                collector.seam.version = version = int(msg[2])
                collector.start(int(msg[1]))
                started = True
            elif kind == "weights":
                version = int(msg[1])
                agent.actor.load_state_dict(msg[2])
                if msg[3] is not None:
                    agent.critic.load_state_dict(msg[3])
                collector.seam.version = version
            elif kind == "pause":
                paused = True
            elif kind == "resume":
                paused = False
            elif kind == "consumed":
                consumed += int(msg[1])
            elif kind == "push":
                template.actor.load_state_dict(msg[1]); template.critic.load_state_dict(msg[2])
                pool.push(template)
                conn.send(("ok", len(pool)))
            elif kind == "pool_state":
                conn.send(("ok", pool.state_dict()))
            elif kind == "pool_stats":
                conn.send(("ok", (list(pool.stats[0]), list(pool.stats[-1]), len(pool))))
            elif kind == "stats":
                conn.send(("ok", {
                    **collector.stats(),
                    "collect/child_polls": float(polls),
                    "collect/child_idle_frac": idle_polls / max(polls + idle_polls, 1),
                    "collect/child_steps_unconsumed": float(produced - consumed),
                    "collect/child_version": float(version),
                }))
                polls = idle_polls = 0
            elif kind == "battle_counter":
                conn.send(("ok", collector.battle_counter))
            elif kind == "set_battle_counter":
                collector.battle_counter = int(msg[1])
            elif kind == "metadata":
                conn.send(("ok", collector.metadata()))
            elif kind == "close":
                collector.close()
                conn.send(("ok", None))
                return
            else:
                raise RuntimeError(f"unknown control message {kind!r}")
        if not started or paused or (produced - consumed) >= max_ahead:
            idle_polls += 1
            time.sleep(0.002)
            continue
        collector.check()
        eps = collector.poll()
        polls += 1
        for ep in eps:
            ep_queue.put(ep)
            produced += len(ep["actions"])


# ---------------------------------------------------------------------------
# The parent-side collector.
# ---------------------------------------------------------------------------

class ProcCollector:
    """`EngineCollector` in a child process; the same seam from the loop's side."""

    # Episodes arrive asynchronously, so an empty poll here really is
    # "nothing yet" (unlike the in-process engine collector, where a poll IS a
    # step): a short sleep is right.
    idle_sleep = 0.002

    def __init__(
        self,
        cfg: dict,
        agent,
        pool,
        *,
        seed: int,
        k: int,
        team_bank: str,
        learner_seat: str = "p1",
        opp_action: bool = False,
        privileged: bool = False,
        both_views: bool = False,
        battle_counter: int = 0,
        outcome_targets: bool = False,
        max_steps_ahead: int,
        torch_threads: int = 1,
        pause_on_update: bool = False,
        allow_background_qos: bool = False,
        ready_timeout: float = 300.0,
        search: dict | None = None,
    ):
        if qos_is_background() and not allow_background_qos:
            raise RuntimeError(
                "ProcCollector refuses a BACKGROUND QoS: taskpolicy is barred in the fleet "
                "path (plan amendment 3 item 1 -- a background process runs on the efficiency "
                "cores at ~6.8x). Tests that run niced beside a fleet pass allow_background_qos."
            )
        if max_steps_ahead < 1:
            raise ValueError(f"max_steps_ahead must be >= 1, got {max_steps_ahead}")
        self.seam = _Seam()
        self.k = int(k)
        self.pause_on_update = bool(pause_on_update)
        self._version_shipped = None
        self.episodes_finished = 0
        self.max_steps_ahead = int(max_steps_ahead)
        self._closed = False
        ctx = mp.get_context("spawn")
        self._conn, child_conn = ctx.Pipe()
        self._q = ctx.Queue()
        spec = {
            "cfg": dict(cfg), "actor": _state(agent.actor), "critic": _state(agent.critic),
            "pool_size": pool.pool_size, "latest_prob": pool.latest_prob, "pool_state": pool.state_dict(),
            "seed": int(seed), "k": int(k), "team_bank": str(team_bank), "learner_seat": learner_seat,
            "opp_action": bool(opp_action), "privileged": bool(privileged), "both_views": bool(both_views),
            "battle_counter": int(battle_counter), "outcome_targets": bool(outcome_targets),
            "max_steps_ahead": int(max_steps_ahead), "torch_threads": int(torch_threads), "version": 0,
            "search": None if search is None else dict(search),
        }
        self._proc = ctx.Process(target=_child_main, args=(child_conn, self._q, spec), daemon=True)
        self._proc.start()
        child_conn.close()
        if not self._conn.poll(ready_timeout):
            self.close()
            raise RuntimeError("the collector process did not come up within the ready timeout")
        tag, info = self._conn.recv()
        if tag != "ready":
            self.close()
            raise RuntimeError(f"collector process handshake failed: {tag!r}")
        self.build_info = info["build_info"]
        self.tables_fingerprint = info["tables_fingerprint"]
        self.bank_header = info["bank_header"]
        self.child_pid = info["pid"]

    # ---- plumbing -----------------------------------------------------------

    def _rpc(self, *msg, timeout: float = 600.0):
        self.check()
        self._conn.send(msg)
        if not self._conn.poll(timeout):
            raise RuntimeError(f"collector process did not answer {msg[0]!r} within {timeout}s")
        tag, payload = self._conn.recv()
        if tag != "ok":
            raise RuntimeError(f"collector process answered {tag!r} to {msg[0]!r}")
        return payload

    def check(self) -> None:
        if self._closed:
            return
        if not self._proc.is_alive():
            raise RuntimeError(
                f"the collector process (pid {self.child_pid}) died, exit code {self._proc.exitcode}"
            )

    # ---- the seam -------------------------------------------------------------

    def start(self, n_battles: int) -> None:
        self._conn.send(("start", int(n_battles), int(self.seam.version)))
        self._version_shipped = int(self.seam.version)

    def poll(self) -> list[dict]:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        if out:
            steps = sum(len(ep["actions"]) for ep in out)
            self.episodes_finished += len(out)
            self._conn.send(("consumed", steps))
        return out

    def pause(self) -> None:
        if self.pause_on_update:
            self._conn.send(("pause",))

    def resume(self, version: int) -> None:
        if version != self._version_shipped:
            raise RuntimeError(
                "ProcCollector.resume(version) needs the weights: call ship_weights(agent, version) "
                "(rl/train.py does) -- a version bump without weights would stamp rows nobody trained"
            )
        if self.pause_on_update:
            self._conn.send(("resume",))

    def ship_weights(self, agent, version: int) -> None:
        """The learner's current weights to the child, stamped `version`; a no-op
        when the version did not move (eval / checkpoint pauses)."""
        if version != self._version_shipped:
            self._conn.send(("weights", int(version), _state(agent.actor), _state(agent.critic)))
            self._version_shipped = int(version)
            self.seam.version = int(version)
        if self.pause_on_update:
            self._conn.send(("resume",))

    def run_in_loop(self, fn, *args):
        raise TypeError(
            "ProcCollector has no in-process loop: the pool lives in the child. Use "
            "push(agent) / pool_state() / pool_stats() (rl/train.py's engine_proc branch)."
        )

    # ---- pool RPCs -----------------------------------------------------------

    def push(self, agent) -> int:
        return int(self._rpc("push", _state(agent.actor), _state(agent.critic)))

    def pool_state(self) -> dict:
        return self._rpc("pool_state")

    def pool_stats(self) -> tuple[list, list, int]:
        return self._rpc("pool_stats")

    # ---- counters / metadata -------------------------------------------------

    def stats(self) -> dict[str, float]:
        return dict(self._rpc("stats"))

    @property
    def battle_counter(self) -> int:
        return int(self._rpc("battle_counter"))

    @battle_counter.setter
    def battle_counter(self, n: int) -> None:
        self._conn.send(("set_battle_counter", int(n)))

    def metadata(self) -> dict:
        return self._rpc("metadata")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._proc.is_alive():
                self._conn.send(("close",))
                if self._conn.poll(30.0):
                    self._conn.recv()
        except (OSError, EOFError, BrokenPipeError):
            pass
        self._proc.join(10.0)
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(5.0)
        try:
            self._q.close()
        except Exception:
            pass

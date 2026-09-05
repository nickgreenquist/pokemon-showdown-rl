"""Both-seat harvest (BI-G4-1, JOURNEY step 4): seat 2's trajectory under
mirror self-play enters training as its own episode.

Wang 2024 §3.1: "both players used the most recent iteration of the policy,
and both players recorded the trajectory for learning. In other words, each
game played produced two games for the algorithm to learn from." Today the
sync loop harvests seat 1 only — seat 2 is the pool member's battle, its
observation is encoded by `PoolPlayer.choose_move` for the member's forward
and then dropped (IDEAS_POST_100M §4.1 calls this the strongest lever left).

THE SHAPE. Seat 2's decisions do not align with seat 1's env steps (a forced
replacement after a faint is one seat's decision while the other waits; the
wait pump inside ShowdownEnv.step absorbs those), so seat 2's rows cannot
share the (T, N) rollout buffer. They are collected as WHOLE EPISODES — the
async collector's format (rl/buffers/episode.py: obs, masks, actions,
rewards, old_logp, version, lengths) — and concatenated onto the seat-1 flat
batch inside PPOAgent.update() at the rollout boundary, where per-episode GAE
(terminal bootstrap 0, the audited kernel) gives them advantages. Only
FINISHED battles are drained; a battle still running at the boundary waits
for the next one, exactly as the async collector's no-barrier rule.

THE POLICY THAT ACTED. The member is a SNAPSHOT (pushed at an update
boundary) and is fixed for the whole battle; a battle spanning two rollouts
was acted, in its second half, by weights one push behind the learner. So
old_logp is RECORDED AT ACT TIME from the member's own forward
(`AgentOpponent.move_logp`), never recomputed — the async path's rule, and
the ratio pi_new / pi_member is PPO's own correction for the lag. `version`
carries the member's push id so the lag is a metric (harvest/version_lag_max)
and not an assumption. With pool_size 1 / latest_prob 1.0 /
push_every_updates 1 (the Wang-recipe pre-reg) the member during a rollout IS
the learner's weights at that rollout's start — the mirror.

THE REWARD is seat 2's own: rewards zero except the terminal row, which
carries -outcome (outcome is learner-perspective: +1 learner won). Ties are
0 both sides. No shaping ever enters this path (the gen-4 pre-reg runs
terminal-only, Wang's reward).

WHAT IS DROPPED, COUNTED, NEVER SILENT: a decision whose action failed
`action_to_order` (the listener-thread mask-desync race, recovered by
`_recover_mask_desync`) — the order that was PLAYED is not the action that
was drawn, so the row is dropped (harvest/rows_dropped); a battle swept
finished without a `report_outcome` (harvest/discarded); a battle whose
seat-2 side never decided (harvest/empty). Kill-and-resume loses the open
battles' seat-2 rows (nothing is checkpointed here; a death costs ≤ one
rollout's worth, the same unit the seat-1 buffer loses).

Gen-agnostic: the seat-2 obs is whatever the PoolPlayer subclass encodes
(gen 1's embed_battle or gen 4's tracker-backed encoder).
"""

from __future__ import annotations

import numpy as np

from rl.buffers.episode import EpisodeDataset


class SeatHarvest:
    def __init__(self):
        self._open: dict[str, list[tuple]] = {}
        self._done = EpisodeDataset()
        self.counts = {"episodes": 0, "rows": 0, "rows_dropped": 0, "discarded": 0, "empty": 0}
        self._version_min: int | None = None

    def record(self, tag: str, obs: np.ndarray, mask: np.ndarray, action: int, logp: float,
               version: int) -> None:
        self._open.setdefault(tag, []).append(
            (np.asarray(obs, dtype=np.float32), np.asarray(mask, dtype=np.bool_),
             int(action), float(logp), int(version))
        )

    def drop_row(self, tag: str) -> None:
        """A decision whose drawn action was not what got played (mask-desync
        recovery): no row, counted."""
        self._open.setdefault(tag, [])
        self.counts["rows_dropped"] += 1

    def finish(self, tag: str, outcome_seat2: int) -> None:
        """Close a battle with seat 2's own outcome (+1 seat 2 won, -1 lost,
        0 tie) and queue it for the next drain."""
        rows = self._open.pop(tag, [])
        if not rows:
            self.counts["empty"] += 1
            return
        n = len(rows)
        rewards = np.zeros(n, dtype=np.float32)
        rewards[-1] = float(outcome_seat2)
        versions = np.array([r[4] for r in rows], dtype=np.int64)
        self._done.append({
            "obs": np.stack([r[0] for r in rows]),
            "masks": np.stack([r[1] for r in rows]),
            "actions": np.array([r[2] for r in rows], dtype=np.int64),
            "rewards": rewards,
            "old_logp": np.array([r[3] for r in rows], dtype=np.float32),
            "version": versions,
        })
        self.counts["episodes"] += 1
        self.counts["rows"] += n
        low = int(versions.min())
        self._version_min = low if self._version_min is None else min(self._version_min, low)

    def discard(self, tag: str) -> None:
        """A battle that ended without an outcome report (the finished sweep
        found it first): its rows are dropped, counted."""
        if self._open.pop(tag, None) is not None:
            self.counts["discarded"] += 1

    @property
    def open_battles(self) -> int:
        return len(self._open)

    def __len__(self) -> int:
        """Finished episodes waiting to be drained."""
        return len(self._done)

    @property
    def pending_rows(self) -> int:
        return self._done.steps

    def drain(self) -> tuple[dict[str, np.ndarray], dict[str, float]]:
        """Everything finished since the last drain, flat (the episode-batch
        format), plus this drain's counters (deltas, not cumulative) and the
        oldest member version among the drained rows — reset for the next
        rollout. Caller checks len() first: an empty drain is a bug."""
        batch = self._done.drain()
        stats = {f"harvest/{k}": float(v) for k, v in self.counts.items()}
        stats["harvest/version_min"] = float(self._version_min if self._version_min is not None else -1)
        self.counts = {k: 0 for k in self.counts}
        self._version_min = None
        return batch, stats

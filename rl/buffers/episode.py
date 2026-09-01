"""Episode dataset + per-episode GAE: the async collector's data path
(THROUGHPUT_SPEC §2 Stage 2).

The rollout buffer's (T, N) lockstep layout assumes N envs advancing one
step per tick. The async collector has no ticks: K concurrent battles finish
whenever they finish, and only WHOLE finished episodes enter training (the
no-barrier design — learning from an unfinished battle would require
fabricating a terminal, the exact failure G4 gates). So the natural unit is
the episode: a dict of per-decision arrays plus a scalar outcome, appended
as battles end, drained flat (with a `lengths` vector) when the step budget
fills.

Per-episode GAE is *simpler* than the (T, N) form, not harder: within an
episode next_value = values[t+1] and the terminal bootstraps to 0 — which is
already what the sync path computes, because ShowdownEnv.step forces every
decided finish to `terminated` (truncations never surface). It also deletes
the update's second critic pass: no next_obs array exists, so V(s') comes
from shifting V(s) instead of a second forward over 30k successor rows.

Torch-free like the other buffers: the agent converts to tensors itself.
"""

import numpy as np

from rl.buffers.rollout import compute_gae

# Per-decision arrays every episode must carry, with their dtypes. old_logp
# is recorded AT ACT TIME — under async collection the policy can change
# between a row's decision and its update (an in-flight battle straddles the
# update boundary), so the sync path's recompute-at-update-start would be
# silently wrong: first-epoch ratios exactly 1.0, clip_frac 0, and the run
# does uncorrected vanilla PG on stale rows with no metric that looks wrong
# (THROUGHPUT_SPEC risk table; gated by G5). `version` is the update counter
# at act time, the staleness histogram's raw material.
EPISODE_KEYS = {
    "obs": np.float32,
    "masks": np.bool_,
    "actions": np.int64,
    "rewards": np.float32,
    "old_logp": np.float32,
    "version": np.int64,
}
# Optional D25 label row: the opponent's simultaneous action identity,
# (kind, id, flags) int32 — present on every episode or on none (the loud
# seam rule: a mixed dataset would silently train the aux head on a subset).
OPT_KEY = "opp_choice"


class EpisodeDataset:
    """Finished episodes accumulated between updates; drained flat.

    Not a ring buffer: on-policy data dies after one update cycle (the
    rollout buffer's rule), so `drain()` hands everything over and resets.
    The batch a drain yields is every episode that FINISHED since the last
    one — slightly more than the step budget the caller waited for, because
    the final episode overshoots. That jitter (about half an episode length
    on a 30k budget, <0.1%) is the price of never cutting an episode.
    """

    def __init__(self):
        self._episodes: list[dict[str, np.ndarray]] = []
        self.steps = 0

    def __len__(self) -> int:
        return len(self._episodes)

    def append(self, episode: dict[str, np.ndarray]) -> None:
        length = len(episode["actions"])
        assert length > 0, "empty episode"
        for key, dtype in EPISODE_KEYS.items():
            arr = episode[key]
            assert arr.dtype == dtype, f"{key}: {arr.dtype} != {dtype}"
            assert len(arr) == length, f"{key}: length {len(arr)} != {length}"
        if self._episodes:
            has = OPT_KEY in self._episodes[0]
            assert (OPT_KEY in episode) == has, (
                "opp_choice must be present on every episode or on none"
            )
        self._episodes.append(episode)
        self.steps += length

    def drain(self) -> dict[str, np.ndarray]:
        """Everything accumulated, flattened, plus `lengths` — then reset."""
        assert self._episodes, "drain() on an empty dataset"
        eps = self._episodes
        batch = {
            key: np.concatenate([ep[key] for ep in eps]) for key in EPISODE_KEYS
        }
        if OPT_KEY in eps[0]:
            batch[OPT_KEY] = np.concatenate([ep[OPT_KEY] for ep in eps])
        batch["lengths"] = np.array([len(ep["actions"]) for ep in eps], dtype=np.int64)
        self._episodes = []
        self.steps = 0
        return batch


def episode_gae(
    rewards: np.ndarray,
    values: np.ndarray,
    lengths: np.ndarray,
    gamma: float,
    lam: float,
) -> np.ndarray:
    """GAE over a flat batch of whole episodes. All per-row inputs (B,);
    `lengths` (E,) with sum B; returns advantages (B,).

    Implemented as a reduction to `compute_gae` over a single (B, 1) column
    rather than a new backward loop: each episode's last row is marked
    terminated (zero bootstrap — every finish the collector keeps is a
    decided game), which also cuts the recursion so no episode's advantage
    chains into the one concatenated before it, and next_values is V shifted
    up one row (0 at terminals). Bit-for-bit the audited GAE on the layout
    the async path produces, with no second implementation to drift.
    """
    assert int(np.sum(lengths)) == len(rewards), "lengths do not tile the batch"
    ends = np.cumsum(lengths) - 1
    terminated = np.zeros(len(rewards), dtype=np.float32)
    terminated[ends] = 1.0
    next_values = np.zeros_like(values)
    next_values[:-1] = values[1:]
    next_values[ends] = 0.0
    return compute_gae(
        rewards[:, None],
        terminated[:, None],
        np.zeros((len(rewards), 1), dtype=np.float32),
        values[:, None],
        next_values[:, None],
        gamma,
        lam,
    )[:, 0]

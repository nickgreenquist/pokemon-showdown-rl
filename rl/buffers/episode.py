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
# Optional per-decision rows, each present on EVERY episode or on NONE (the
# loud seam rule: a mixed dataset would silently train a head on a subset).
# Both are (n, W) with the same `n` the required keys carry, so no length
# logic changes:
#   opp_choice  D25's label — the opponent's simultaneous action identity,
#               (kind, id, flags) int32, W = 3.
#   privileged  D18's block — the OPPONENT seat's own-side slice of its own
#               encoding, float32, W = PRIV_DIM (408 at gen 1). Emitted by
#               the engine collector under `privileged=True`; the same key and
#               shape the Node path puts in `info["privileged"]`.
#   outcome_targets  IDEAS 4.11's three critic targets (survivors own / opp,
#               HP margin, each in [-1, 1]), float32, W = 3, the SAME row on
#               every step of the episode (rl/envs/outcome_targets.py). Emitted
#               by the engine collector under `outcome_targets=True`.
#   obs2        R7 B2's second view -- the OPPONENT seat's FULL own observation
#               of the same state, float32, W = OBS_DIM (828). Emitted by the
#               engine collector under `both_views=True`; `privileged` is a
#               slice of it. The antisymmetric critic reads [obs | obs2].
# There is deliberately no `next_privileged`: per-episode GAE shifts V within
# an episode and bootstraps the terminal to 0 (`_episode_boundaries` below),
# so the successor's block is row t+1's own and the last row's is never read —
# the same reason `next_obs` does not exist on this path.
#   search_mask / search_pi / search_v   R7 B5's searched rows: `search_mask`
#               (n,) bool says which rows the T-op searched; `search_pi` (n, A)
#               float32 is pi' (masked, normalised, zeros on unsearched rows);
#               `search_v` (n,) float32 is v' (0 there). The three travel
#               TOGETHER (asserted in append) and the learner refuses a batch
#               carrying them without `search_targets`, or vice versa.
#   opp_latest  (n,) bool, the engine collector's always-on tag: the member
#               seated against this episode was the pool's NEWEST snapshot at
#               seat time -- `value/bias_mirror`'s row selector (R7 B5 (c)).
OPT_KEYS = ("opp_choice", "privileged", "outcome_targets", "obs2",
            "search_mask", "search_pi", "search_v", "opp_latest")
SEARCH_KEYS = ("search_mask", "search_pi", "search_v")


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
        for key in OPT_KEYS:
            if key not in episode:
                continue
            arr = episode[key]
            assert len(arr) == length, f"{key}: length {len(arr)} != {length}"
        present = [key in episode for key in SEARCH_KEYS]
        assert all(present) or not any(present), (
            f"the search keys travel together: {dict(zip(SEARCH_KEYS, present))}"
        )
        if self._episodes:
            for key in OPT_KEYS:
                has = key in self._episodes[0]
                assert (key in episode) == has, (
                    f"{key} must be present on every episode or on none"
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
        for key in OPT_KEYS:
            if key in eps[0]:
                batch[key] = np.concatenate([ep[key] for ep in eps])
        batch["lengths"] = np.array([len(ep["actions"]) for ep in eps], dtype=np.int64)
        self._episodes = []
        self.steps = 0
        return batch


def _episode_boundaries(
    rewards: np.ndarray, values: np.ndarray, lengths: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """The per-row `terminated` and `next_values` both GAE layouts share:
    each episode's last row is marked terminated (zero bootstrap — every
    finish the collector keeps is a decided game), which also cuts the
    recursion so no episode's advantage chains into the one concatenated
    before it, and next_values is V shifted up one row (0 at terminals)."""
    assert int(np.sum(lengths)) == len(rewards), "lengths do not tile the batch"
    ends = np.cumsum(lengths) - 1
    terminated = np.zeros(len(rewards), dtype=np.float32)
    terminated[ends] = 1.0
    next_values = np.zeros_like(values)
    next_values[:-1] = values[1:]
    next_values[ends] = 0.0
    return terminated, next_values


def _episode_gae_reference(
    rewards: np.ndarray,
    values: np.ndarray,
    lengths: np.ndarray,
    gamma: float,
    lam: float,
) -> np.ndarray:
    """The original per-episode GAE: `compute_gae` over ONE (B, 1) column
    (only the boundary rows moved into the shared helper above). Kept as the
    equality pin's target for `episode_gae` (tests/test_episode_buffer.py) —
    training never calls it. Its cost was the finding (F-10): the kernel's
    Python loop ran B (~30k) iterations of 1-element NumPy ops per update."""
    terminated, next_values = _episode_boundaries(rewards, values, lengths)
    return compute_gae(
        rewards[:, None],
        terminated[:, None],
        np.zeros((len(rewards), 1), dtype=np.float32),
        values[:, None],
        next_values[:, None],
        gamma,
        lam,
    )[:, 0]


def episode_gae(
    rewards: np.ndarray,
    values: np.ndarray,
    lengths: np.ndarray,
    gamma: float,
    lam: float,
) -> np.ndarray:
    """GAE over a flat batch of whole episodes. All per-row inputs (B,);
    `lengths` (E,) with sum B; returns advantages (B,) in rewards' dtype
    (float32 on the data path).

    Still `compute_gae` — the audited (T, N) kernel stays the only
    recurrence, so there is no second implementation to drift — but laid
    out (Lmax, E) instead of as a (B, 1) column: every episode is a column,
    RIGHT-aligned so its terminal row sits on the last scan row, and the
    zero padding above a short episode is scanned and then discarded by the
    gather. The kernel's Python loop therefore runs Lmax times (the longest
    episode, hundreds) rather than B times (~30k), each iteration an E-wide
    NumPy op instead of a 1-element one (F-10).

    Bit-identical to the column reduction (`_episode_gae_reference`, pinned
    with np.array_equal AND a bitwise view in tests/test_episode_buffer.py):
    every row sees the same float32 operands through the same op order, and
    the one thing the layout changes — the carry entering a terminal row
    (the NEXT episode's first advantage in the column form, the scan's
    +0.0 init here) — is multiplied by (1 - done) = 0.0 on both paths. A
    finite carry makes that product ±0.0, a terminal row's delta is never
    -0.0 (it is `(r + 0.0) - v`), so the sum is the same bits either way.
    The sole behavioural difference is for NON-finite critic outputs: the
    column form leaked a NaN/inf backward across an episode boundary through
    0.0 * carry; a column per episode cannot.
    """
    lengths = np.asarray(lengths, dtype=np.int64)
    terminated, next_values = _episode_boundaries(rewards, values, lengths)
    n_rows, n_eps = len(rewards), len(lengths)
    longest = int(lengths.max(initial=0))
    # Flat row i -> (scan row t_i, column e_i), right-aligned in its column.
    col = np.repeat(np.arange(n_eps), lengths)
    starts = np.cumsum(lengths) - lengths
    row = np.arange(n_rows) - starts[col] + (longest - lengths[col])

    def padded(flat: np.ndarray) -> np.ndarray:
        out = np.zeros((longest, n_eps), dtype=flat.dtype)
        out[row, col] = flat
        return out

    advantages = compute_gae(
        padded(rewards),
        padded(terminated),
        np.zeros((longest, n_eps), dtype=np.float32),
        padded(values),
        padded(next_values),
        gamma,
        lam,
    )
    return advantages[row, col]

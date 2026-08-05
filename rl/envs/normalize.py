"""Observation and reward normalization: the continuous track's new harness
surface.

On the discrete spine these were no-ops worth skipping — MinAtar planes are
binary 0/1, and its rewards are 0/1 too. MuJoCo breaks both assumptions:
observations are unbounded joint angles, velocities and contact forces whose
scales differ by orders of magnitude across coordinates, and returns grow with
the policy. Normalizing both is one of the few PPO implementation details with
positive published ablation evidence (Engstrom et al. 2020 found reward
scaling, Adam lr annealing and orthogonal init all significant; Andrychowicz
et al. 2021: "always use observation normalization").

Three design decisions, all locked in the chunk-5 spec:

- **Running statistics, not fixed ones.** Stats are updated throughout
  training rather than estimated once from random rollouts. A random
  HalfCheetah policy visits a completely different state distribution than a
  trained one, so fixed stats go stale exactly as the agent improves.
- **Wrapper-side, not agent-internal.** Phase 3 benchmarks SAC against this
  PPO with the env stack held fixed, the same "vary only the algorithm"
  discipline that made the discrete headline clean. It also keeps the stats
  in one place to checkpoint.
- **Ours, not gymnasium's.** `gymnasium.wrappers.vector.NormalizeObservation`
  asserts `autoreset_mode == NEXT_STEP` and rejects a partial `reset_mask`;
  we deliberately run with autoreset DISABLED and reset finished sub-envs
  explicitly (see make.py), so gymnasium's vector normalizers are
  structurally incompatible rather than merely inconvenient. Their reward
  normalizer also zeroes its accumulator on termination only — never on
  truncation or reset (gymnasium #760), which on a pure-truncation env like
  HalfCheetah means it never resets at all.

The statistics are state that MUST be checkpointed. A restored policy
evaluated against the wrong observation statistics is not obviously broken —
it just scores badly, silently, with no crash and no failing test. That is
why `save_checkpoint` serializes them and why `frozen_obs_env` below RAISES
when a normalize-flagged checkpoint carries no stats instead of quietly
running unnormalized.
"""

from typing import Any

import gymnasium as gym
import numpy as np

CLIP_OBS = 10.0  # standard deviations; CleanRL/SB3 value (gymnasium clips nothing)
CLIP_REWARD = 10.0
EPS = 1e-8  # variance floor, inside the sqrt


class RunningMeanStd:
    """Streaming mean/variance via Chan et al.'s parallel merge.

    float64 throughout (SB3's choice): these accumulate over millions of
    steps, and the merge subtracts means, so float32 rounding compounds.
    `count` starts at a small epsilon rather than 0 so the very first update
    divides by something positive; the var=1 prior it carries is annihilated
    by the first real batch.
    """

    def __init__(self, shape: tuple[int, ...] = (), epsilon: float = 1e-4):
        self.mean = np.zeros(shape, dtype=np.float64)
        self.var = np.ones(shape, dtype=np.float64)
        self.count = float(epsilon)

    def update(self, batch: np.ndarray) -> None:
        """Fold in a batch shaped (B, *shape). B=0 is a no-op (a partial reset
        can legitimately reset no rows)."""
        batch = np.asarray(batch, dtype=np.float64)
        if batch.shape[0] == 0:
            return
        batch_mean = batch.mean(axis=0)
        batch_var = batch.var(axis=0)
        batch_count = batch.shape[0]

        delta = batch_mean - self.mean
        total = self.count + batch_count
        m_a = self.var * self.count
        m_b = batch_var * batch_count
        m_2 = m_a + m_b + delta**2 * self.count * batch_count / total

        self.mean = self.mean + delta * batch_count / total
        self.var = m_2 / total
        self.count = total

    def state_dict(self) -> dict[str, Any]:
        return {"mean": self.mean.copy(), "var": self.var.copy(), "count": self.count}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.mean = np.asarray(state["mean"], dtype=np.float64)
        self.var = np.asarray(state["var"], dtype=np.float64)
        self.count = float(state["count"])


def normalize_obs(obs: np.ndarray, rms: RunningMeanStd, clip: float = CLIP_OBS) -> np.ndarray:
    """(obs - mean) / sqrt(var + eps), clipped, emitted float32.

    One function so the training wrapper and the frozen eval wrapper cannot
    drift apart — a clip applied on one side only would make eval scores
    incomparable with training in a way nothing would flag. float32 out
    although the stats are float64: it matches what the nets consume, and it
    halves rollout-buffer obs memory on MuJoCo's float64 observations.
    """
    z = (np.asarray(obs, dtype=np.float64) - rms.mean) / np.sqrt(rms.var + EPS)
    return np.clip(z, -clip, clip).astype(np.float32)


def _float32_box(space: gym.spaces.Box) -> gym.spaces.Box:
    """The normalized observation space: same shape, float32, unbounded.
    Bounds stay infinite rather than +/-clip because nothing downstream reads
    them and gymnasium's own normalizers do the same."""
    return gym.spaces.Box(-np.inf, np.inf, space.shape, dtype=np.float32)


class NormalizeObservation(gym.vector.VectorWrapper):
    """Running observation normalization for the vector training env.

    Order is update-then-normalize, and it is load-bearing: normalizing first
    against the var=1 prior would emit clipped garbage for a whole first batch
    on any env whose observations are far from unit scale.

    The partial-reset rule is the subtle one. Our train loop resets finished
    sub-envs with `reset(options={"reset_mask": done})` and replaces its whole
    observation array with what comes back — including the rows it did not
    reset, which return holding their current observation. So this wrapper
    normalizes EVERY row it returns while updating statistics only for the
    rows actually reset. Updating and normalizing the same subset would feed
    raw, unnormalized observations into act() and the rollout buffer at every
    episode boundary: no crash, no failing test, just a quietly poisoned run.

    (Non-reset rows are re-normalized under statistics one batch newer than
    the step that produced them. That is harmless — the buffer stores exactly
    what the agent saw, so pi_old and pi_new stay consistent — and should not
    be "fixed".)
    """

    def __init__(self, env: gym.vector.VectorEnv, rms: RunningMeanStd | None = None):
        super().__init__(env)
        self.rms = rms if rms is not None else RunningMeanStd(env.single_observation_space.shape)
        self.single_observation_space = _float32_box(env.single_observation_space)
        self.observation_space = gym.vector.utils.batch_space(
            self.single_observation_space, env.num_envs
        )

    def reset(self, *, seed=None, options=None):
        # Read the mask BEFORE delegating: SyncVectorEnv.reset does
        # `options.pop("reset_mask")`, mutating the caller's dict, so asking
        # afterwards always answers None — which would fold every non-reset
        # row's stale observation into the statistics at every episode end.
        reset_mask = None if options is None else options.get("reset_mask")
        obs, info = self.env.reset(seed=seed, options=options)
        # Stats: only the freshly reset rows are new data. Output: all rows.
        self.rms.update(obs if reset_mask is None else obs[reset_mask])
        return normalize_obs(obs, self.rms), info

    def step(self, actions):
        obs, rewards, terminated, truncated, infos = self.env.step(actions)
        self.rms.update(obs)
        return normalize_obs(obs, self.rms), rewards, terminated, truncated, infos


class FrozenNormalizeObservation(gym.ObservationWrapper):
    """The eval-side counterpart: a scalar env normalizing through a SHARED
    `RunningMeanStd` that it never updates.

    Sharing the live object (rather than a copy) is what makes each training
    eval pass use the statistics as of that moment — SB3's VecNormalize
    `training=False` semantics. Freezing matters because eval episodes would
    otherwise inject their own state distribution into the statistics the
    training env depends on, and because eval must be reproducible: the same
    policy and the same stats must always produce the same score.
    """

    def __init__(self, env: gym.Env, rms: RunningMeanStd):
        super().__init__(env)
        self.rms = rms
        self.observation_space = _float32_box(env.observation_space)

    def observation(self, obs):
        return normalize_obs(obs, self.rms)


class NormalizeReward(gym.vector.VectorWrapper):
    """Reward scaling by the running standard deviation of the discounted
    return — the training env only.

    Not standardization: the reward is divided by sqrt(var(G)) with no mean
    subtracted, where G is the backward discounted return accumulator
    `G <- gamma * G + r`. Subtracting a mean would change the sign structure
    of the rewards and with it the optimal policy; dividing only rescales the
    advantage magnitudes the optimizer sees. This is the exact quantity
    Engstrom et al. 2020 measured.

    Operation order follows SB3: accumulate, update the statistics, THEN zero
    the accumulator on finished rows. Zeroing before the update (i.e. folding
    `(1 - done)` into the accumulation) would drop every episode's largest
    return sample — the terminal one — out of the variance estimate entirely.

    The accumulator resets on ANY episode end, terminated or truncated, which
    is this repo's convention everywhere ("any done cuts the chain") and
    matches baselines' VecNormalize. Gymnasium resets on termination only.

    The raw reward is republished as `info["raw_reward"]` so the train loop
    can keep logging `rollout/episode_return` in true env units. A normalized
    training curve would be meaningless across runs and incomparable with
    every DQN and discrete-PPO number in the repo.

    Note the first step of a run always saturates the clip (the variance
    estimate has seen one sample), and once training is underway scaled
    rewards settle around 0.05-1.0 in magnitude, which puts `loss/value` near
    1e-3. Both are expected; neither is a bug to chase.
    """

    def __init__(self, env: gym.vector.VectorEnv, gamma: float, rms: RunningMeanStd | None = None):
        super().__init__(env)
        self.rms = rms if rms is not None else RunningMeanStd(())
        self.gamma = gamma
        self.returns = np.zeros(env.num_envs, dtype=np.float64)

    def reset(self, *, seed=None, options=None):
        reset_mask = None if options is None else options.get("reset_mask")  # popped below
        obs, info = self.env.reset(seed=seed, options=options)
        # Belt-and-suspenders: step() already zeroed rows that finished, but a
        # fresh reset must never inherit a previous episode's accumulator.
        if reset_mask is None:
            self.returns[:] = 0.0
        else:
            self.returns[np.asarray(reset_mask, dtype=bool)] = 0.0
        return obs, info

    def step(self, actions):
        obs, rewards, terminated, truncated, infos = self.env.step(actions)
        rewards = np.asarray(rewards, dtype=np.float64)
        self.returns = self.returns * self.gamma + rewards
        self.rms.update(self.returns)
        scaled = np.clip(
            rewards / np.sqrt(self.rms.var + EPS), -CLIP_REWARD, CLIP_REWARD
        )
        self.returns[np.asarray(terminated, dtype=bool) | np.asarray(truncated, dtype=bool)] = 0.0
        infos = dict(infos)
        infos["raw_reward"] = rewards
        return obs, scaled, terminated, truncated, infos


def frozen_obs_env(env: gym.Env, cfg, checkpoint: dict[str, Any]) -> gym.Env:
    """Rebuild the eval-side observation normalizer from a checkpoint.

    The one place watch/record/eval_checkpoint restore statistics, so the
    three cannot disagree. Raises rather than falling back when a
    normalize-flagged checkpoint has no stats: running such a policy on raw
    observations produces a plausible-looking bad number, which is worse than
    a stack trace. Wrap BEFORE `make_agent` — the agent builds against the
    env's observation space.
    """
    if not getattr(cfg, "normalize_obs", False):
        return env
    stats = (checkpoint.get("normalizers") or {}).get("obs")
    if stats is None:
        raise ValueError(
            "config sets normalize_obs but the checkpoint carries no observation "
            "statistics; evaluating it unnormalized would silently misreport the policy"
        )
    rms = RunningMeanStd(env.observation_space.shape)
    rms.load_state_dict(stats)
    return FrozenNormalizeObservation(env, rms)

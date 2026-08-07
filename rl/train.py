"""Single entry point: `python -m rl.train --config configs/<run>.yaml`.
Every algorithm plugs in here; the loop stays algorithm-agnostic.
"""

import argparse
import importlib.metadata
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
import yaml

from rl.agents.base import Agent
from rl.agents.ppo import PPOAgent
from rl.agents.random_agent import RandomAgent
from rl.common.checkpoint import load_checkpoint, save_checkpoint
from rl.common.config import Config, load_config, run_dir
from rl.common.evaluation import evaluate
from rl.common.logging import Logger, make_logger
from rl.common.seeding import set_seed
from rl.envs.make import make_env, make_eval_env, make_vec_env, selfplay_env_kwargs
from rl.envs.normalize import (
    FrozenNormalizeObservation,
    NormalizeObservation,
    NormalizeReward,
    RunningMeanStd,
)
from rl.selfplay.pool import SnapshotPool


# Algo registry: make_agent constructs from it, and train() reads the class's
# `vectorized` flag to pick env construction and collection path up front.
ALGOS: dict[str, type[Agent]] = {
    "random": RandomAgent,
    "ppo": PPOAgent,
}


def make_agent(cfg: Config, env: gym.Env) -> Agent:
    algo = cfg.agent.get("algo")
    cls = ALGOS.get(algo)
    if cls is None:
        raise ValueError(f"unknown algo {algo!r}")
    if cls is RandomAgent:
        return RandomAgent(env.action_space)
    hparams = {k: v for k, v in cfg.agent.items() if k != "algo"}
    if cls.vectorized:
        # Vectorized agents build against one sub-env's spaces plus the batch
        # width. The getattr fallbacks cover the scalar-env rebuild in
        # watch/record/eval_checkpoint: plain spaces, width 1.
        return cls(
            getattr(env, "single_observation_space", env.observation_space),
            getattr(env, "single_action_space", env.action_space),
            num_envs=getattr(env, "num_envs", 1),
            device=cfg.device,
            **hparams,
        )
    # Torch agents share one constructor shape (DQN, REINFORCE, later SAC).
    return cls(env.observation_space, env.action_space, device=cfg.device, **hparams)


def _write_run_metadata(out_dir: Path, cfg: Config) -> None:
    """Stamp the run dir before training starts: the resolved config (CLI
    overrides baked in, reloadable via load_config) plus provenance — a
    benchmark campaign spans days of possible code drift, so every result
    must trace back to an exact tree."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.yaml").write_text(yaml.safe_dump(asdict(cfg), sort_keys=False))
    repo_root = Path(__file__).resolve().parents[1]
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, cwd=repo_root,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, check=True, cwd=repo_root,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        sha, dirty = "unknown", False
    versions = {}
    for pkg in ("torch", "gymnasium", "numpy", "minatar", "wandb"):
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            pass
    meta = {
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "git_dirty": dirty,
        "versions": versions,
    }
    if cfg.env_id.startswith("Showdown"):
        # Deferred import on purpose: only Showdown runs pay for poke_env,
        # and only they have encoder semantics to stamp (the set prior and
        # v2 flags change the obs at constant OBS_DIM — a checkpoint is only
        # interpretable together with this record).
        from rl.envs.showdown import ENCODER_FINGERPRINT

        meta["encoder"] = dict(ENCODER_FINGERPRINT)
    (out_dir / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))


def train(cfg: Config) -> None:
    # First, before any tensor work (config.py explains the default of 1).
    # Belt-and-suspenders: OMP_NUM_THREADS=1 at launch also binds the OpenMP
    # runtime itself, which is sized before this call can run.
    torch.set_num_threads(cfg.torch_threads)
    set_seed(cfg.seed)
    # Collection path is a property of the algorithm class (Agent.vectorized),
    # known before construction; an unknown algo falls through to make_agent's
    # error. Eval always runs a single scalar env either way.
    agent_cls = ALGOS.get(cfg.agent.get("algo"))
    vectorized = agent_cls is not None and agent_cls.vectorized
    if (cfg.normalize_obs or cfg.normalize_reward) and not vectorized:
        # The normalizers are vector-level wrappers. Silently ignoring the
        # flags would still stamp them into the run's config snapshot, and
        # every checkpoint from that "successful" run would then refuse to
        # re-evaluate (frozen_obs_env raises on missing statistics).
        raise ValueError(
            f"normalize_obs/normalize_reward need a vectorized algorithm; "
            f"{cfg.agent.get('algo')!r} runs the scalar loop"
        )
    if cfg.selfplay and (cfg.normalize_obs or cfg.normalize_reward):
        # The normalizers are VECTOR-level wrappers, and the opponent lives
        # inside a sub-env beneath them. The learner would act on z-scored
        # observations while every frozen snapshot still acts on raw bools,
        # so the pool would be un-frozen by the back door — with no crash and
        # no metric that looks wrong.
        raise ValueError(
            "selfplay is incompatible with normalize_obs/normalize_reward: the "
            "normalizers wrap the vector env, but the opponent lives inside a "
            "sub-env and would keep seeing raw observations"
        )
    # Self-play configs pass their opponent into the env; every other config
    # gets {} and is bit-for-bit unaffected. `opponent: self` trains against
    # the snapshot pool: the string is replaced with the live pool OBJECT
    # before env construction, so all N sub-envs share it through the
    # caller-kwargs seam (a pool IS an Opponent under the protocol). If the
    # string ever reaches an env unreplaced — including `eval_opponent:
    # self` — make_opponent raises "unknown opponent", so nothing can
    # silently evaluate against the pool.
    train_env_kwargs = selfplay_env_kwargs(cfg, "opponent")
    pool, push_every = None, 0
    if train_env_kwargs.get("opponent") == "self":
        if not vectorized:
            raise ValueError(
                "selfplay opponent 'self' needs a vectorized algorithm: "
                "snapshots push at rollout boundaries, which the scalar "
                "loop does not have"
            )
        missing = {"pool_size", "latest_prob", "push_every_updates"} - cfg.selfplay.keys()
        if missing:
            raise ValueError(f"selfplay opponent 'self' needs {sorted(missing)}")
        push_every = cfg.selfplay["push_every_updates"]
        if push_every < 1:
            raise ValueError(f"push_every_updates must be >= 1, got {push_every}")
        if cfg.env_id.startswith("Showdown") and cfg.selfplay.get("fixed_mix", 0.0) > 0.0:
            # The pool's fixed anchors are Connect 4 Opponents that read a
            # board out of the obs. On a 611-dim Showdown obs HeuristicOpponent
            # crashes but RandomOpponent silently plays a legal uniform-random
            # move, unreported (measured) — half the fixed draws would corrupt
            # the run without an error. Showdown anchor bots need the battle
            # object and so must enter at the Player level if ever wanted.
            raise ValueError(
                "fixed_mix > 0 is Connect4-only: the pool's fixed anchors "
                "decode a board from the obs and cannot drive a Showdown battle"
            )
        pool = SnapshotPool(
            cfg.selfplay["pool_size"], cfg.selfplay["latest_prob"],
            pfsp_power=cfg.selfplay.get("pfsp_power", 0.0),
            fixed_mix=cfg.selfplay.get("fixed_mix", 0.0),
        )
        train_env_kwargs["opponent"] = pool
    if vectorized:
        env = make_vec_env(cfg.env_id, cfg.seed, cfg.num_envs, env_kwargs=train_env_kwargs)
    else:
        env = make_env(cfg.env_id, cfg.seed, env_kwargs=train_env_kwargs)
    # Eval reseeds per episode, and goes through make_eval_env so a self-play
    # run is scored against its fixed anchor rather than the env's default
    # opponent — this is the call site that selects best_checkpoint.
    eval_env = make_eval_env(cfg)
    # Normalization statistics are shared, not copied: the eval env reads the
    # training env's live RunningMeanStd but never updates it, so each eval
    # pass scores the policy under the statistics it is currently training
    # against. They are checkpointed at every save (see save_checkpoint).
    normalizers: dict[str, RunningMeanStd] = {}
    if cfg.normalize_obs:
        env = NormalizeObservation(env)
        normalizers["obs"] = env.rms
        eval_env = FrozenNormalizeObservation(eval_env, env.rms)
    if cfg.normalize_reward:
        # Reward scaling is a training-time device only — eval returns are
        # always reported in true env units.
        env = NormalizeReward(env, gamma=cfg.agent["gamma"])
        normalizers["reward"] = env.rms
    agent = make_agent(cfg, env)
    if cfg.init_from:
        # Warm start. MUST precede the step-0 pool push below: pushing first
        # would anchor the pool at a random init while the learner starts at
        # the loaded policy — no crash, and the anchor diagnostic would read
        # ~1.0 forever and look wonderful.
        agent.load_state_dict(load_checkpoint(cfg.init_from)["agent"])
        # A warm start is a FRESH run (settled 2026-08-05; Agent.begin_warm_start
        # holds the reasoning). This is the line that makes init_from +
        # lr_anneal_steps legal: the anneal now covers this run's budget
        # instead of resuming the donor's finished schedule at lr ~0.
        agent.begin_warm_start()
    out_dir = run_dir(cfg)
    # Before the logger: even a run that dies in wandb.init leaves a stamped dir.
    _write_run_metadata(out_dir, cfg)
    logger = make_logger(cfg)
    if pool is not None:
        # Before the loop: _vector_loop's first statement is envs.reset(),
        # which draws an opponent per sub-env, and select() on an empty pool
        # raises. The step-0 snapshot is also the naive arm's starting
        # opponent and the strided pool's permanent anchor.
        pool.push(agent)
        logger.log({"selfplay/pool_size": len(pool)}, 0)

    if vectorized:
        _vector_loop(cfg, env, eval_env, agent, logger, out_dir, normalizers, pool, push_every)
    else:
        _scalar_loop(cfg, env, eval_env, agent, logger, out_dir)

    logger.close()
    env.close()
    eval_env.close()


def _scalar_loop(
    cfg: Config, env: gym.Env, eval_env: gym.Env, agent: Agent, logger: Logger, out_dir: Path
) -> None:
    """One env, one transition per update() call — random/tabular/DQN/REINFORCE."""
    obs, info = env.reset(seed=cfg.seed)
    mask = info.get("action_mask")  # None only for continuous-action envs
    best_eval = float("-inf")
    ep_return, ep_length = 0.0, 0
    # Per-episode loss/* sums and per-key report counts: each key is averaged
    # over the steps that reported it (DQN reports every step, REINFORCE once
    # per episode), not over ep_length.
    ep_losses: dict[str, float] = defaultdict(float)
    ep_counts: dict[str, int] = defaultdict(int)
    last_step, last_time = 0, time.perf_counter()
    # Loop split, same contract as the vectorized path. This loop has no
    # rollout boundary, so the flush rides the episode boundary — the same
    # cadence steps_per_sec already uses.
    collect_sec, update_sec = 0.0, 0.0
    next_ckpt = cfg.checkpoint_every

    for step in range(1, cfg.total_steps + 1):
        mark = time.perf_counter()
        action = agent.act(obs, mask)
        next_obs, reward, terminated, truncated, info = env.step(action)
        collect_sec += time.perf_counter() - mark
        next_mask = info.get("action_mask")
        # Per-step update on the fresh transition (tabular Q; DQN keeps this
        # cadence but samples from replay instead). Both flags are passed:
        # only `terminated` stops bootstrapping (a time-limit cut still
        # bootstraps), but `truncated` still marks an episode boundary,
        # which n-step accumulation must not chain across. The mask pair
        # rides along: `mask` legalizes obs's actions, `next_mask` s''s (the
        # bootstrap max needs it).
        mark = time.perf_counter()
        update_report = agent.update(
            (obs, action, float(reward), next_obs, terminated, truncated, mask, next_mask)
        )
        update_sec += time.perf_counter() - mark
        for name, value in update_report.items():
            ep_losses[name] += value
            ep_counts[name] += 1
        obs = next_obs
        mask = next_mask
        ep_return += float(reward)
        ep_length += 1

        if terminated or truncated:
            now = time.perf_counter()
            logger.log(
                {
                    "rollout/episode_return": ep_return,
                    "rollout/episode_length": ep_length,
                    "time/steps_per_sec": (step - last_step) / (now - last_time),
                    "time/collect_sec": collect_sec,
                    "time/update_sec": update_sec,
                    **{name: total / ep_counts[name] for name, total in ep_losses.items()},
                },
                step,
            )
            last_step, last_time = step, now
            collect_sec, update_sec = 0.0, 0.0
            obs, info = env.reset()
            mask = info.get("action_mask")
            ep_return, ep_length = 0.0, 0
            ep_losses.clear()
            ep_counts.clear()

        if cfg.checkpoint_every and step >= next_ckpt:
            save_checkpoint(out_dir / f"ckpt_{step:09d}.pt", agent, step, cfg)
            while next_ckpt <= step:
                next_ckpt += cfg.checkpoint_every

        if step % cfg.eval_every == 0:
            mark = time.perf_counter()
            metrics = evaluate(agent, eval_env, cfg.eval_episodes, win_rate=cfg.eval_win_rate)
            metrics["time/eval_sec"] = time.perf_counter() - mark
            logger.log(metrics, step)
            # The final policy is an arbitrary sample of an oscillating
            # training trajectory (deep RL policies churn), so keep the
            # best-so-far policy too. Report final and best.
            if metrics["eval/return_mean"] > best_eval:
                best_eval = metrics["eval/return_mean"]
                save_checkpoint(out_dir / "best_checkpoint.pt", agent, step, cfg)
            # Latest-policy snapshot every eval: a run that dies mid-flight
            # still leaves best + latest + full metric history behind.
            save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg)

    save_checkpoint(out_dir / "checkpoint.pt", agent, cfg.total_steps, cfg)


def _vector_loop(
    cfg: Config,
    envs: gym.vector.VectorEnv,
    eval_env: gym.Env,
    agent: Agent,
    logger: Logger,
    out_dir: Path,
    normalizers: dict[str, RunningMeanStd] | None = None,
    pool: SnapshotPool | None = None,
    push_every: int = 0,
) -> None:
    """N lockstep envs, batched transitions — vectorized (on-policy) agents.

    Autoreset is disabled (see make_vec_env): finished sub-envs are reset
    manually right after their terminal step, so every transition handed to
    update() is a real env step and next_obs at a terminal row is the
    episode's true final observation. Loss metrics are logged whenever
    update() reports them (once per rollout batch for PPO) instead of
    averaged per episode — episodes end at different times across envs.
    """
    num_envs = envs.num_envs
    obs, infos = envs.reset(seed=cfg.seed)  # gymnasium seeds sub-env i with seed + i
    masks = infos.get("action_mask")  # (N, A); None only for continuous envs
    best_eval = float("-inf")
    ep_returns = np.zeros(num_envs)
    ep_lengths = np.zeros(num_envs, dtype=np.int64)
    step, next_eval = 0, cfg.eval_every
    updates_done = 0
    last_step, last_time = 0, time.perf_counter()
    # Loop split, accumulated per step and flushed per rollout: act+step vs
    # update. steps_per_sec says how fast the loop runs; these say where the
    # time goes, which is the thing a throughput decision needs.
    collect_sec, update_sec = 0.0, 0.0
    # Checkpoint ladder by threshold crossing. `step` advances by num_envs, so
    # it lands ON a multiple of checkpoint_every only when the two divide;
    # `step % checkpoint_every == 0` would silently write 3 rungs where 9 were
    # asked for. The while-loop advance also survives a stride that skips a
    # whole threshold.
    next_ckpt = cfg.checkpoint_every

    # Step advances num_envs at a time, so the run ends at the first multiple
    # of num_envs >= total_steps, and evals fire on crossing each threshold
    # (both overshoot by < num_envs steps).
    while step < cfg.total_steps:
        mark = time.perf_counter()
        actions = agent.act(obs, masks)
        next_obs, rewards, terminated, truncated, infos = envs.step(actions)
        collect_sec += time.perf_counter() - mark
        # Autoreset is disabled, so step infos always describe the true
        # successor states — at a truncated row next_masks is the final
        # state's real mask, exactly what a bootstrap consumer needs.
        next_masks = infos.get("action_mask")
        step += num_envs
        mark = time.perf_counter()
        update_metrics = agent.update(
            (obs, actions, rewards, next_obs, terminated, truncated, masks, next_masks)
        )
        update_sec += time.perf_counter() - mark
        if update_metrics:
            # A truthy report is the rollout boundary, so the accumulators
            # cover exactly one rollout.
            logger.log(
                {**update_metrics, "time/collect_sec": collect_sec, "time/update_sec": update_sec},
                step,
            )
            collect_sec, update_sec = 0.0, 0.0
            if pool is not None:
                # Pool-health series, read positionally BEFORE this
                # boundary's possible push: stats[0] is the permanent step-0
                # anchor (never evicted at pool_size > 1), stats[-1] the
                # latest member — the two indices eviction (which deletes
                # index 1) can never misalign. Cumulative counters; window
                # them at read time. winrate_anchor is the in-run forgetting
                # detector (H&L §V-C): the learner's score vs the policy it
                # anchored on sinking below 0.5 while winrate_latest holds
                # ~0.5 is the failure signature.
                sp_metrics = {}
                score, games = pool.stats[0]
                if games:
                    sp_metrics["selfplay/winrate_anchor"] = score / games
                    sp_metrics["selfplay/anchor_games"] = games
                score, games = pool.stats[-1]
                if games:
                    sp_metrics["selfplay/winrate_latest"] = score / games
                if sp_metrics:
                    logger.log(sp_metrics, step)
            # A truthy report means the rollout just drained — the only legal
            # push point: snapshots enter the pool at rollout boundaries so
            # that within a rollout the opponent DISTRIBUTION is fixed, which
            # is what PPO's importance ratios require. Which member plays is
            # the other swap boundary, drawn per episode at env reset.
            updates_done += 1
            if pool is not None and updates_done % push_every == 0:
                pool.push(agent)
                # selfplay/* is logged from here, never from pool code
                # (locked metric-namespace rule, CLAUDE.md).
                logger.log({"selfplay/pool_size": len(pool)}, step)
            if pool is not None:
                # PFSP weights snapshot at the same boundary the push
                # cadence uses: counts accumulate during the rollout, the
                # draw only sees them from the next rollout on, so the
                # opponent distribution stays fixed within a rollout.
                pool.refresh()
        # Episode returns are always accumulated in TRUE env units. With
        # reward normalization on, `rewards` is scaled by a running statistic
        # that itself moves during training, so logging it would make
        # rollout/episode_return incomparable across runs and against every
        # DQN and discrete-PPO number in the repo. The wrapper republishes the
        # raw reward; the fallback covers every env without it.
        ep_returns += infos.get("raw_reward", rewards)
        ep_lengths += 1
        obs = next_obs
        masks = next_masks

        done = terminated | truncated
        if done.any():
            now = time.perf_counter()
            sps = (step - last_step) / (now - last_time)
            # One log per finished episode. Simultaneous finishes share a
            # step, which W&B merges (last write wins) — rare, accepted.
            for i in np.flatnonzero(done):
                logger.log(
                    {
                        "rollout/episode_return": float(ep_returns[i]),
                        "rollout/episode_length": int(ep_lengths[i]),
                        "time/steps_per_sec": sps,
                    },
                    step,
                )
            last_step, last_time = step, now
            ep_returns[done] = 0.0
            ep_lengths[done] = 0
            # Unfinished rows come back holding their current obs, so the
            # returned array replaces obs wholesale. The reset info's mask
            # array does NOT (non-reset rows are all-False placeholders in
            # gymnasium's aggregation) — merge on the done rows only.
            obs, reset_infos = envs.reset(options={"reset_mask": done})
            if masks is not None:
                masks = np.where(done[:, None], reset_infos["action_mask"], masks)

        if cfg.checkpoint_every and step >= next_ckpt:
            save_checkpoint(out_dir / f"ckpt_{step:09d}.pt", agent, step, cfg, normalizers)
            while next_ckpt <= step:
                next_ckpt += cfg.checkpoint_every

        if step >= next_eval:
            next_eval += cfg.eval_every
            mark = time.perf_counter()
            metrics = evaluate(agent, eval_env, cfg.eval_episodes, win_rate=cfg.eval_win_rate)
            metrics["time/eval_sec"] = time.perf_counter() - mark
            logger.log(metrics, step)
            if metrics["eval/return_mean"] > best_eval:
                best_eval = metrics["eval/return_mean"]
                save_checkpoint(out_dir / "best_checkpoint.pt", agent, step, cfg, normalizers)
            save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg, normalizers)

    save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg, normalizers)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="path to a run YAML")
    # Overrides for the multi-seed benchmark protocol: same YAML, N seeds,
    # each under its own run name.
    parser.add_argument("--seed", type=int, default=None, help="override the config seed")
    parser.add_argument("--run-name", default=None, help="override the config run_name")
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.seed is not None:
        cfg.seed = args.seed
    if args.run_name is not None:
        cfg.run_name = args.run_name
    train(cfg)


if __name__ == "__main__":
    main()

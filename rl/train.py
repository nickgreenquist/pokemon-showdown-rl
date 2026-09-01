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


def _frozen_checkpoint_pool(path: str) -> SnapshotPool:
    """A `.pt` path under `selfplay.opponent` resolves here: the checkpoint
    becomes the SINGLE frozen member of a one-member pool, and the learner —
    fresh init, its own config — trains against it as a fixed opponent. The
    pool object is what lets N sub-envs share one frozen policy through the
    caller-kwargs seam, exactly as `opponent: self` does; `train()` keeps its
    own push pool as None, so the learner is never pushed and the opponent
    never moves. Built for D22's exploitability probe (DESIGN §12: fresh
    best-response vs a frozen final), and deliberately general: any future
    exploiter/PFSP work needs this same seam.

    Showdown-only and same-encoder-only: the agent is built against spaces
    faked at the CURRENT process OBS_DIM (a real env here would open
    websockets just to read shapes), so a checkpoint from another encoder
    width is refused rather than shimmed — the training path never needs the
    eval-side cross-encoder shim, and silently mis-slicing a training
    opponent would corrupt a run without an error."""
    from types import SimpleNamespace

    from rl.envs.showdown import OBS_DIM

    ckpt = load_checkpoint(path)
    cfg = Config(**ckpt["config"])
    spaces = SimpleNamespace(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(10),
    )
    agent = make_agent(cfg, spaces)
    try:
        agent.load_state_dict(ckpt["agent"])
    except RuntimeError as err:
        raise ValueError(
            f"frozen opponent {path} does not load at the process encoder "
            f"width {OBS_DIM}: check the POKEMON_RL_ENCODER_V2 / "
            "POKEMON_RL_ENCODER_IDS env vars"
        ) from err
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)
    return pool


def _write_run_metadata(out_dir: Path, cfg: Config, agent: Agent | None = None) -> None:
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
    for pkg in ("torch", "gymnasium", "numpy", "wandb"):
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
    if agent is not None and hasattr(agent, "actor") and hasattr(agent, "critic"):
        # Exact param counts (Rung 2 R0-2 stamps them; harmless everywhere
        # else): a capacity-matched comparison is only auditable if the
        # counts are in the run record, not re-derived from code that may
        # have drifted.
        meta["params"] = {
            "actor": sum(p.numel() for p in agent.actor.parameters()),
            "critic": sum(p.numel() for p in agent.critic.parameters()),
        }
        # D25 R0-2 stamps BOTH numbers: `actor` must stay bit-identical to the
        # control (626,059) while the trained stack grows by the head, and the
        # ceiling is a POLICY here — EntityDeepSetsNet's assert walks its own
        # parameters(), so an agent-owned head is invisible to it and no aux
        # width can hard-fail at launch. R0-1 stamps the adopted label space
        # for the same reason: so it cannot be changed silently at launch.
        if getattr(agent, "aux_head", None) is not None:
            aux = sum(p.numel() for p in agent.aux_head.parameters())
            meta["params"]["aux"] = aux
            meta["params"]["actor_plus_aux"] = meta["params"]["actor"] + aux
            meta["aux_label_space"] = agent.aux_label_space
            # D25-P: the placebo flag is stamped so it cannot be flipped
            # silently at launch (R0-1's fingerprint covers it).
            meta["aux_shuffle_labels"] = bool(
                getattr(agent, "aux_shuffle_labels", False)
            )
    (out_dir / "meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))


def _ensure_theta0(agent: Agent, out_dir: Path, cfg: Config) -> None:
    """D23: the L2-toward-init anchors are written ONCE per run dir, and the
    digest that every checkpoint carries is checked against the file here.

    Scoped to the TRAINING construction path deliberately. theta0 is
    regenerable for a fixed (seed, config), so a fresh lane writes it and a
    restart into the same dir re-derives the identical anchors and verifies —
    but a restart against someone else's theta0.pt, or a resume whose anchors
    were deleted, is a silently different experiment and raises. The eval path
    (make_agent + load_state_dict, score_ladder, eval_checkpoint) never calls
    this: a guard in the shared loader would break the locked eval protocol.
    """
    if getattr(agent, "l2_init_decay", 0.0) <= 0.0:
        return
    path = out_dir / "theta0.pt"
    digest = agent.theta0_hash()
    if path.exists():
        stored = torch.load(path, weights_only=False).get("theta0_hash")
        if stored != digest:
            raise ValueError(
                f"{path} was written from a different initialization "
                f"({stored} != {digest}): l2_init_decay > 0 anchors this run to "
                "its own init, so resuming against another run's theta0 would "
                "train a different experiment"
            )
        return
    if cfg.init_from or any(out_dir.glob("*.pt")):
        raise FileNotFoundError(
            f"{path} is missing but {out_dir} already holds checkpoints (or the "
            "run is warm-started): the L2-toward-init anchors cannot be "
            "recovered from a checkpoint, so this resume would silently anchor "
            "to a fresh init"
        )
    torch.save(agent.theta0_state(), path)


def train(cfg: Config, resume_dir: Path | None = None) -> None:
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
    # The anneal trap (ch2_review_2 MF-6): a schedule shorter than the run
    # trains every step past lr_anneal_steps at lr EXACTLY 0 — parameters
    # frozen, no crash, no metric that looks wrong (copy-pasting a 12M anneal
    # under total_steps 50M silently burns the last 38M steps). The interval
    # form permits the two legitimate shapes: 0 (off) and >= total_steps
    # (full-horizon anneal, or a deliberate schedule-prefix smoke such as
    # configs/showdown_sp_recipe12m_smoke.yaml with anneal 12M over 100k).
    anneal_steps = int(cfg.agent.get("lr_anneal_steps", 0) or 0)
    if 0 < anneal_steps < cfg.total_steps:
        raise ValueError(
            f"lr_anneal_steps {anneal_steps} < total_steps {cfg.total_steps}: "
            "the run would train past the schedule's end at lr exactly 0. "
            "Use 0 (no anneal) or >= total_steps (full-horizon anneal)."
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
    # D25 R0-1b, THE PURITY SEAM. The auxiliary label is the action of the
    # agent's own current or past weights — DESIGN §5 clause (b) — and that is
    # the ONLY thing that keeps an action-prediction head inside the pure
    # self-play claim, because such a head IS a self-distillation channel and
    # is admissible only because the teacher is us. Raised here, where the
    # config is visible, and raised loudly with the reason in the message.
    #
    # (The fixed_mix/pfsp_power half of this guard was removed with the
    # levers themselves, 2026-08-29 CLEANUP A4 — the strict selfplay key
    # check in selfplay_env_kwargs now rejects those keys outright.)
    if cfg.agent.get("aux_oppact_coef", 0.0) > 0.0:
        if cfg.selfplay.get("opponent") != "self":
            raise ValueError(
                "aux_oppact_coef > 0 requires selfplay.opponent 'self' (got "
                f"opponent={cfg.selfplay.get('opponent')!r}): the "
                "opponent-action label is only pure self-play while the labelled "
                "opponent is a snapshot of this agent"
            )
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
        pool = SnapshotPool(cfg.selfplay["pool_size"], cfg.selfplay["latest_prob"])
        train_env_kwargs["opponent"] = pool
    elif str(train_env_kwargs.get("opponent", "")).endswith(".pt"):
        # Frozen-checkpoint opponent (best-response/exploiter lanes). `pool`
        # stays None on purpose: the learner is never pushed, so the frozen
        # member is the opponent for the whole run.
        if not cfg.env_id.startswith("Showdown"):
            raise ValueError(
                "a checkpoint-path opponent is Showdown-only: the frozen "
                "agent is built against faked Showdown spaces"
            )
        train_env_kwargs["opponent"] = _frozen_checkpoint_pool(
            train_env_kwargs["opponent"]
        )
    async_collect = _async_collector_mode(cfg, vectorized)
    if async_collect:
        # No training env is constructed at all: the async collector builds
        # its own two Players (rl/envs/showdown_async.py), and opening a
        # SyncVectorEnv here would cost 16 idle websockets. The agent builds
        # against faked spaces at the process OBS_DIM — the
        # _frozen_checkpoint_pool precedent.
        from types import SimpleNamespace

        from rl.envs.showdown import OBS_DIM

        env = SimpleNamespace(
            observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
            action_space=gym.spaces.Discrete(10),
            num_envs=cfg.num_envs,
            close=lambda: None,
        )
    elif vectorized:
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
    resume_state: dict | None = None
    if resume_dir is not None:
        # RESUME (2026-08-23, the 24h run-loss bar): pick a killed run back
        # up from its own dir. Constructed from the run's OWN config.yaml
        # (main() enforces), same seed -> same init, same usernames, and the
        # l2 theta0 guard below re-derives identical anchors and verifies.
        # NOT a warm start: begin_warm_start() is deliberately not called —
        # optimizer moments and the update counter come back from the
        # checkpoint and the lr anneal resumes its own schedule.
        assert vectorized, "resume supports the vectorized loop only"
        assert Path(out_dir).resolve() == Path(resume_dir).resolve(), (
            f"resume dir {resume_dir} != run dir {out_dir} (run_name drift?)"
        )
        ckpt = load_checkpoint(Path(resume_dir) / "checkpoint.pt")
        assert ckpt["config"] == asdict(cfg), (
            "checkpoint config != run config.yaml — a resume must not "
            "silently change the experiment"
        )
        agent.load_state_dict(ckpt["agent"])
        for name, rms in (normalizers or {}).items():
            if "normalizers" in ckpt and name in ckpt["normalizers"]:
                rms.load_state_dict(ckpt["normalizers"][name])
        resume_state = {"step": ckpt["step"], **ckpt.get("loop", {})}
        # Provenance: append to meta.yaml rather than rewriting it — the
        # original stamp (started_at, launch sha) must survive the seam.
        meta_path = out_dir / "meta.yaml"
        meta = yaml.safe_load(meta_path.read_text()) if meta_path.exists() else {}
        meta.setdefault("resumes", []).append({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "from_step": int(ckpt["step"]),
        })
        meta_path.write_text(yaml.safe_dump(meta, sort_keys=False))
        print(f"RESUME: {cfg.run_name} from step {ckpt['step']} "
              f"(best_eval {resume_state.get('best_eval')})")
    else:
        # Before the logger: even a run that dies in wandb.init leaves a stamped dir.
        _write_run_metadata(out_dir, cfg, agent)
    # No-op unless l2_init_decay > 0; raises before a single step is collected
    # if the run dir's anchors disagree with this construction.
    _ensure_theta0(agent, out_dir, cfg)
    logger = make_logger(cfg)
    if pool is not None and resume_dir is not None:
        pool_path = Path(resume_dir) / "pool.pt"
        if pool_path.exists():
            pool.load_state_dict(
                torch.load(pool_path, weights_only=False),
                agent_factory=lambda: make_agent(cfg, env),
            )
            logger.log({"selfplay/pool_size": len(pool)}, resume_state["step"])
        else:
            # Pre-resume-era run dir: no pool snapshot exists. DISCLOSED
            # approximation — the pool restarts seeded with the RESUMED
            # weights (not the step-0 init): training stays sane, but the
            # winrate_anchor series restarts against a new anchor.
            print("RESUME: no pool.pt — pool reseeded from the resumed "
                  "weights (winrate_anchor restarts; disclosed)")
            pool.push(agent)
            logger.log({"selfplay/pool_size": len(pool)}, resume_state["step"])
    elif pool is not None:
        # Before the loop: _vector_loop's first statement is envs.reset(),
        # which draws an opponent per sub-env, and select() on an empty pool
        # raises. The step-0 snapshot is also the naive arm's starting
        # opponent and the strided pool's permanent anchor.
        pool.push(agent)
        logger.log({"selfplay/pool_size": len(pool)}, 0)

    if async_collect:
        _async_loop(cfg, eval_env, agent, logger, out_dir, pool, push_every,
                    resume_state, train_env_kwargs.get("opponent"))
    elif vectorized:
        _vector_loop(cfg, env, eval_env, agent, logger, out_dir, normalizers, pool,
                     push_every, resume_state)
    else:
        _scalar_loop(cfg, env, eval_env, agent, logger, out_dir)

    logger.close()
    env.close()
    eval_env.close()


def _async_collector_mode(cfg: Config, vectorized: bool) -> bool:
    """Strict launch-time validation of the Stage-2 collector block — the
    selfplay-keys rule: a typo'd knob or an unsupported combination must
    fail HERE, not train a 50M run silently wrong."""
    unknown = cfg.collector.keys() - {"mode", "concurrency"}
    if unknown:
        raise ValueError(f"unknown collector key(s) {sorted(unknown)}; known: "
                         "['concurrency', 'mode']")
    mode = cfg.collector.get("mode", "sync")
    if mode not in ("sync", "async"):
        raise ValueError(f"collector.mode must be 'sync' or 'async', got {mode!r}")
    if mode == "sync":
        if "concurrency" in cfg.collector:
            raise ValueError("collector.concurrency is async-only")
        return False
    concurrency = cfg.collector.get("concurrency", 8)
    if not isinstance(concurrency, int) or not 1 <= concurrency <= 64:
        raise ValueError(f"collector.concurrency must be an int in [1, 64], "
                         f"got {concurrency!r} (E4b: the knee is K=8)")
    if not cfg.env_id.startswith("Showdown"):
        raise ValueError("collector.mode 'async' is Showdown-only")
    if not vectorized:
        raise ValueError("collector.mode 'async' needs a vectorized algorithm "
                         "(the episode batches enter PPO's _optimize)")
    if cfg.normalize_obs or cfg.normalize_reward:
        raise ValueError("collector.mode 'async' is incompatible with the "
                         "vector-level normalizers")
    extra = cfg.env_kwargs.keys() - {"opp_action"}
    if extra:
        # faint_shaping / hl_shaping / privileged / save_replays all live in
        # the env stack the async path does not run; accepting them here
        # would stamp a config whose knobs silently did nothing.
        raise ValueError(f"collector.mode 'async' supports env_kwargs "
                         f"{{'opp_action'}} only; got {sorted(extra)} — the "
                         "async path emits terminal outcome rewards only")
    if cfg.agent.get("privileged_dim"):
        raise ValueError("collector.mode 'async' does not collect the "
                         "privileged block (D18) — the wide critic would "
                         "train on zeros")
    return True


def _async_loop(
    cfg: Config,
    eval_env: gym.Env,
    agent: Agent,
    logger: Logger,
    out_dir: Path,
    pool: SnapshotPool | None,
    push_every: int,
    resume_state: dict | None,
    opponent_spec,
) -> None:
    """The Stage-2 collection loop: K concurrent battles serviced on
    POKE_LOOP (rl/envs/showdown_async.py), whole finished episodes
    accumulated here, stop-the-world updates through
    agent.update_episodes. Mirrors _vector_loop's cadences on the same step
    counter — eval, checkpoint ladder, pool pushes, locked metric names —
    so a run reads identically downstream (extract_history, the graders).

    Timing semantics: `time/collect_sec` is the wall time the collector was
    live (gate open) per rollout, `time/update_sec` the update call — the
    same split the vector loop reports, with eval excluded from both.
    Everything that mutates state the loop thread reads (pool pushes, pool
    stat reads) is fenced through collector.run_in_loop; the update itself
    needs no fence because pause() guarantees no decision is in flight.
    """
    from rl.buffers.episode import EpisodeDataset
    from rl.envs.showdown_async import AsyncCollector

    # The construction-time rollout buffer is the vector path's; this loop
    # feeds update_episodes and must never touch it — None makes any stray
    # update() call fail loudly instead of training on a phantom rollout.
    agent.buffer = None
    budget = cfg.agent["rollout_steps"] * cfg.num_envs
    collector = AsyncCollector(
        agent.act_logp,
        opponent_spec,
        seed=cfg.seed,
        concurrency=cfg.collector.get("concurrency", 8),
        opp_action=bool(cfg.env_kwargs.get("opp_action", False)),
    )
    dataset = EpisodeDataset()
    rs = resume_state or {}
    best_eval = rs.get("best_eval", float("-inf"))
    step = rs.get("step", 0)
    updates_done = rs.get("updates_done", 0)
    anneal_basis = step  # env steps consumed before the batch being trained
    next_eval = (step // cfg.eval_every + 1) * cfg.eval_every
    next_ckpt = 0
    if cfg.checkpoint_every:
        next_ckpt = (step // cfg.checkpoint_every + 1) * cfg.checkpoint_every
    last_step, last_time = step, time.perf_counter()
    collect_sec, update_sec = 0.0, 0.0
    collect_mark = time.perf_counter()

    def pause() -> None:
        nonlocal collect_sec
        collector.pause()
        collect_sec += time.perf_counter() - collect_mark

    def resume() -> None:
        nonlocal collect_mark
        collector.resume(version=agent.updates)
        collect_mark = time.perf_counter()

    def save_latest() -> None:
        extras = {"loop": {"best_eval": best_eval, "updates_done": updates_done}}
        save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg, extras=extras)
        if pool is not None:
            tmp = out_dir / "pool.pt.tmp"
            torch.save(collector.run_in_loop(pool.state_dict), tmp)
            tmp.replace(out_dir / "pool.pt")

    collector.seam.version = agent.updates  # a resume starts at the restored count
    collector.start(n_battles=cfg.total_steps)
    try:
        while step < cfg.total_steps:
            collector.check()
            episodes = collector.poll()
            if not episodes:
                time.sleep(0.02)
                continue
            now = time.perf_counter()
            for episode in episodes:
                step += len(episode["actions"])
                dataset.append(episode)
            sps = (step - last_step) / (now - last_time)
            for episode in episodes:
                logger.log(
                    {
                        "rollout/episode_return": float(episode["rewards"][-1]),
                        "rollout/episode_length": len(episode["actions"]),
                        "time/steps_per_sec": sps,
                    },
                    step,
                )
            last_step, last_time = step, now

            if dataset.steps >= budget:
                pause()
                batch = dataset.drain()
                # G5's staleness read: update-count lag per row, at drain.
                lag = agent.updates - batch["version"]
                mark = time.perf_counter()
                metrics = agent.update_episodes(batch, steps_seen=anneal_basis)
                update_sec += time.perf_counter() - mark
                anneal_basis = step
                updates_done += 1
                logger.log(
                    {
                        **metrics,
                        "time/collect_sec": collect_sec,
                        "time/update_sec": update_sec,
                        "collect/policy_version_lag_p99": float(
                            np.percentile(lag, 99)
                        ),
                        "collect/policy_version_lag_max": float(lag.max()),
                        **collector.stats(),
                    },
                    step,
                )
                collect_sec, update_sec = 0.0, 0.0
                if pool is not None:
                    sp_metrics = {}
                    stats0, stats_last = collector.run_in_loop(
                        lambda: (list(pool.stats[0]), list(pool.stats[-1]))
                    )
                    score, games = stats0
                    if games:
                        sp_metrics["selfplay/winrate_anchor"] = score / games
                        sp_metrics["selfplay/anchor_games"] = games
                    score, games = stats_last
                    if games:
                        sp_metrics["selfplay/winrate_latest"] = score / games
                    if sp_metrics:
                        logger.log(sp_metrics, step)
                    if updates_done % push_every == 0:
                        collector.run_in_loop(pool.push, agent)
                        logger.log({"selfplay/pool_size": len(pool)}, step)
                resume()

            if cfg.checkpoint_every and step >= next_ckpt:
                pause()
                save_checkpoint(out_dir / f"ckpt_{step:09d}.pt", agent, step, cfg)
                while next_ckpt <= step:
                    next_ckpt += cfg.checkpoint_every
                resume()

            if step >= next_eval:
                next_eval += cfg.eval_every
                pause()
                mark = time.perf_counter()
                metrics = evaluate(
                    agent, eval_env, cfg.eval_episodes, win_rate=cfg.eval_win_rate
                )
                metrics["time/eval_sec"] = time.perf_counter() - mark
                if hasattr(agent, "l2_init_metrics"):
                    metrics.update(agent.l2_init_metrics())
                logger.log(metrics, step)
                if metrics["eval/return_mean"] > best_eval:
                    best_eval = metrics["eval/return_mean"]
                    save_checkpoint(out_dir / "best_checkpoint.pt", agent, step, cfg)
                save_latest()
                resume()

        pause()
        save_latest()
    finally:
        collector.close()


def _scalar_loop(
    cfg: Config, env: gym.Env, eval_env: gym.Env, agent: Agent, logger: Logger, out_dir: Path
) -> None:
    """One env, one transition per update() call — random/tabular/DQN/REINFORCE."""
    obs, info = env.reset(seed=cfg.seed)
    mask = info.get("action_mask")  # None only for Box-action envs (no live track)
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
            # D23 l2init/*: per-LN-free-block ||theta - theta0||, treatment
            # lanes only — the method returns {} (no keys) when the lever is
            # off, and agents without it contribute nothing.
            if hasattr(agent, "l2_init_metrics"):
                metrics.update(agent.l2_init_metrics())
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
    resume_state: dict | None = None,
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
    masks = infos.get("action_mask")  # (N, A); None only for Box-action envs (no live track)
    privs = infos.get("privileged")  # (N, PRIV_DIM); None unless the env emits it (D18)
    # Resume (resume_state from the run's own checkpoint.pt): the loop picks
    # up at the saved step; eval/checkpoint thresholds re-derive from it; a
    # stale best_eval keeps best_checkpoint.pt monotone across the seam.
    rs = resume_state or {}
    best_eval = rs.get("best_eval", float("-inf"))
    ep_returns = np.zeros(num_envs)
    ep_lengths = np.zeros(num_envs, dtype=np.int64)
    step = rs.get("step", 0)
    next_eval = (step // cfg.eval_every + 1) * cfg.eval_every
    updates_done = rs.get("updates_done", 0)
    last_step, last_time = step, time.perf_counter()
    # Loop split, accumulated per step and flushed per rollout: act+step vs
    # update. steps_per_sec says how fast the loop runs; these say where the
    # time goes, which is the thing a throughput decision needs.
    collect_sec, update_sec = 0.0, 0.0
    # Checkpoint ladder by threshold crossing. `step` advances by num_envs, so
    # it lands ON a multiple of checkpoint_every only when the two divide;
    # `step % checkpoint_every == 0` would silently write 3 rungs where 9 were
    # asked for. The while-loop advance also survives a stride that skips a
    # whole threshold.
    next_ckpt = 0
    if cfg.checkpoint_every:
        next_ckpt = (step // cfg.checkpoint_every + 1) * cfg.checkpoint_every

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
        # state's real mask, exactly what a bootstrap consumer needs (and
        # next_privs the final state's privileged view, same argument).
        next_masks = infos.get("action_mask")
        next_privs = infos.get("privileged")
        # D25: TRANSITION-time, not state — the opponent's action was produced
        # during the step just taken and belongs to row t, so it is handed over
        # directly and never carried forward the way masks and privs are.
        opp_choice = infos.get("opp_choice")
        step += num_envs
        mark = time.perf_counter()
        update_metrics = agent.update(
            (obs, actions, rewards, next_obs, terminated, truncated, masks, next_masks,
             privs, next_privs, opp_choice)
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
        privs = next_privs

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
            if privs is not None:
                # Same merge rule as masks: non-reset rows are placeholders
                # in gymnasium's aggregation, so only done rows take the
                # fresh battle's privileged view.
                privs = np.where(done[:, None], reset_infos["privileged"], privs)

        if cfg.checkpoint_every and step >= next_ckpt:
            save_checkpoint(out_dir / f"ckpt_{step:09d}.pt", agent, step, cfg, normalizers)
            while next_ckpt <= step:
                next_ckpt += cfg.checkpoint_every

        if step >= next_eval:
            next_eval += cfg.eval_every
            mark = time.perf_counter()
            metrics = evaluate(agent, eval_env, cfg.eval_episodes, win_rate=cfg.eval_win_rate)
            metrics["time/eval_sec"] = time.perf_counter() - mark
            # D23 l2init/*: per-LN-free-block ||theta - theta0||, treatment
            # lanes only — the method returns {} (no keys) when the lever is
            # off, and agents without it contribute nothing.
            if hasattr(agent, "l2_init_metrics"):
                metrics.update(agent.l2_init_metrics())
            logger.log(metrics, step)
            if metrics["eval/return_mean"] > best_eval:
                best_eval = metrics["eval/return_mean"]
                save_checkpoint(out_dir / "best_checkpoint.pt", agent, step, cfg, normalizers)
            loop_extras = {"loop": {"best_eval": best_eval, "updates_done": updates_done}}
            save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg, normalizers,
                            extras=loop_extras)
            if pool is not None:
                # The pool snapshot pairs with checkpoint.pt (same boundary,
                # same write-then-rename discipline): a resume needs both or
                # it silently restarts the opponent curriculum.
                tmp = out_dir / "pool.pt.tmp"
                torch.save(pool.state_dict(), tmp)
                tmp.replace(out_dir / "pool.pt")

    loop_extras = {"loop": {"best_eval": best_eval, "updates_done": updates_done}}
    save_checkpoint(out_dir / "checkpoint.pt", agent, step, cfg, normalizers,
                    extras=loop_extras)
    if pool is not None:
        tmp = out_dir / "pool.pt.tmp"
        torch.save(pool.state_dict(), tmp)
        tmp.replace(out_dir / "pool.pt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="path to a run YAML (fresh runs)")
    # Overrides for the multi-seed benchmark protocol: same YAML, N seeds,
    # each under its own run name.
    parser.add_argument("--seed", type=int, default=None, help="override the config seed")
    parser.add_argument("--run-name", default=None, help="override the config run_name")
    parser.add_argument(
        "--resume", metavar="RUN_DIR",
        help="resume a killed run from its dir: config/seed/run-name come "
        "from RUN_DIR/config.yaml (the flags above are refused so a resume "
        "can never silently change the experiment)",
    )
    args = parser.parse_args()
    if args.resume:
        assert not (args.config or args.seed is not None or args.run_name), (
            "--resume takes its config, seed and run name from the run dir"
        )
        run_path = Path(args.resume)
        cfg = load_config(run_path / "config.yaml")
        train(cfg, resume_dir=run_path)
        return
    assert args.config, "--config is required for a fresh run"
    cfg = load_config(args.config)
    if args.seed is not None:
        cfg.seed = args.seed
    if args.run_name is not None:
        cfg.run_name = args.run_name
    train(cfg)


if __name__ == "__main__":
    main()

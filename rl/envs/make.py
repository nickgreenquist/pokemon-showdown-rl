"""Env factory: the single place envs are constructed and seeded, kept as a
seam so vectorized envs (Phase 2, PPO) slot in without touching the train loop.

Gymnasium seeding has two independent RNGs per env:
- the env's own RNG, seeded by the caller's first `reset(seed=...)` and
  persisting across later plain `reset()` calls;
- the action/observation spaces' RNG, seeded here, which
  `action_space.sample()` (the random policy) draws from.
"""

from functools import partial

import gymnasium as gym

from rl.envs.wrappers import ActionMask, ChannelFirst


def make_env(
    env_id: str,
    seed: int,
    render_mode: str | None = None,
    env_kwargs: dict | None = None,
) -> gym.Env:
    """`env_kwargs` are forwarded to the env constructor. They are passed to
    `gym.make` as CALLER kwargs on purpose: gymnasium deep-copies the kwargs
    stored on a registered spec, but not the caller's, so an object passed
    here keeps its identity across every sub-env of a vector env. That is
    what lets all N sub-envs share one opponent pool (Phase 4 chunk 2);
    registering the pool instead would silently give each its own copy."""
    if env_id.startswith("MinAtar/"):
        _ensure_minatar_registered()
    elif env_id.startswith("Connect4"):
        _ensure_connect4_registered()
    elif env_id.startswith("Showdown"):
        _ensure_showdown_registered()
    env = gym.make(env_id, render_mode=render_mode, **(env_kwargs or {}))
    if isinstance(env.action_space, gym.spaces.Discrete):
        # Masking contract: every Discrete-action env emits info["action_mask"]
        # (all-True unless the env supplies its own). Box-action envs (the
        # continuous track) have no mask concept and never see one. Applied
        # innermost: observation wrappers stay outermost (their attrs, e.g.
        # ChannelFirst.observation, remain directly reachable) and ActionMask
        # touches only infos, which pass through them unchanged.
        env = ActionMask(env)
    else:
        # Continuous track: the Gaussian policy samples from an unbounded
        # Normal, so actions must be clipped to the env's valid range before
        # they reach the simulator. Explicit rather than leaning on MuJoCo
        # clamping ctrl internally — and the policy still takes the log-prob
        # of the RAW sample, which is why clipping belongs here and not in
        # the agent.
        bounds = env.action_space
        env = gym.wrappers.ClipAction(env)
        # ClipAction re-declares its action space as Box(-inf, inf) ("the
        # actions it will accept"). The clip itself closes over the inner
        # env's real bounds, so restoring the honest declaration changes no
        # behavior — and keeps it readable by anything that needs the true
        # range: action_space.sample() for the random agent today, and the
        # squashed policy SAC brings in Phase 3.
        env.action_space = bounds

    if env_id.startswith("MinAtar/"):
        env = ChannelFirst(env)  # (10, 10, C) planes -> torch's (C, 10, 10)
    env.action_space.seed(seed)
    env.observation_space.seed(seed)
    return env


def make_vec_env(
    env_id: str, seed: int, num_envs: int, env_kwargs: dict | None = None
) -> gym.vector.SyncVectorEnv:
    """N lockstep env copies for on-policy collection (PPO). Sync, not async:
    per-step nets are tiny, so process/IPC overhead would dominate — the same
    lesson as torch_threads=1.

    Autoreset is DISABLED on purpose. The default NEXT_STEP mode inserts a
    dummy transition after every terminal step (action ignored, reward 0,
    obs = reset obs) that a rollout buffer would have to mask; instead the
    train loop resets finished sub-envs explicitly via
    `reset(options={"reset_mask": ...})`, so every transition the agent sees
    is a real env step, and `next_obs` at a terminal step is the episode's
    true final observation (what advantage bootstrapping needs at
    truncations). Sub-env i's spaces are seeded seed + i; episode RNG comes
    from the loop's first `reset(seed=...)`, which gymnasium also fans out
    as seed + i."""
    return gym.vector.SyncVectorEnv(
        [
            partial(make_env, env_id, seed + i, env_kwargs=env_kwargs)
            for i in range(num_envs)
        ],
        autoreset_mode=gym.vector.AutoresetMode.DISABLED,
    )


def selfplay_env_kwargs(cfg, key: str) -> dict:
    """Env kwargs for a self-play config, or {} for every other config —
    which is what keeps all of Phases 0-3 untouched.

    `key` selects which opponent: "opponent" for the training env,
    "eval_opponent" for the eval env. They are deliberately separate. Eval
    must run against a FIXED external anchor and never against a pool
    member: under self-play a policy scores ~50% against its own snapshots
    by construction, so a pool-based eval measures nothing about strength
    and would report an equilibrium as a plateau.
    """
    if not cfg.selfplay:
        return {}
    if key not in cfg.selfplay:
        raise ValueError(f"selfplay config must set {key!r}; got {sorted(cfg.selfplay)}")
    return {"opponent": cfg.selfplay[key]}


def make_eval_env(cfg, render_mode: str | None = None) -> gym.Env:
    """The eval env for a config. Every eval site goes through here — the
    train loop's best-checkpoint eval and all three of scripts/{watch,
    record,eval_checkpoint}.py — so that none of them can silently evaluate
    a self-play run against the env's DEFAULT opponent instead of the
    configured anchor."""
    return make_env(
        cfg.env_id,
        cfg.seed,
        render_mode=render_mode,
        env_kwargs=selfplay_env_kwargs(cfg, "eval_opponent"),
    )


def _ensure_connect4_registered() -> None:
    # Hand-written env, registered here rather than at import so `rl.envs`
    # stays free of side effects — the same shape as the MinAtar branch.
    if "Connect4-v0" not in gym.registry:
        gym.register(id="Connect4-v0", entry_point="rl.envs.connect4:Connect4Env")


def _ensure_showdown_registered() -> None:
    # Registered here like Connect4; the entry-point string also defers the
    # poke_env import to first use, so every other env pays nothing for it.
    if "Showdown-v0" not in gym.registry:
        gym.register(id="Showdown-v0", entry_point="rl.envs.showdown:ShowdownEnv")


def _ensure_minatar_registered() -> None:
    # MinAtar ships its env ids only via the `gymnasium.envs` entry point — a
    # plugin mechanism gymnasium 1.0 removed — so registration is explicit.
    if "MinAtar/Breakout-v0" not in gym.registry:
        from minatar.gym import register_envs  # deferred: pulls in seaborn/matplotlib

        register_envs()

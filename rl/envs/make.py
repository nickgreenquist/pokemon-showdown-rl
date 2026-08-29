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

from rl.envs.wrappers import ActionMask


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
    if env_id.startswith("Connect4"):
        _ensure_connect4_registered()
    elif env_id.startswith("Showdown"):
        _ensure_showdown_registered()
    env = gym.make(env_id, render_mode=render_mode, **(env_kwargs or {}))
    if isinstance(env.action_space, gym.spaces.Discrete):
        # Masking contract: every Discrete-action env emits
        # info["action_mask"] (all-True unless the env supplies its own).
        # Applied innermost: observation wrappers stay outermost and
        # ActionMask touches only infos, which pass through them unchanged.
        env = ActionMask(env)
    # else: Box-action envs pass through bare. The continuous TRACK was
    # retired 2026-08-29 (CLEANUP A3) — PPOAgent rejects Box action spaces at
    # construction — but Pendulum survives as the fixture the normalize-
    # wrapper tests exercise unbounded obs/reward streams with, and it needs
    # no mask and (stepped with in-range actions) no clip.
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
    """Env kwargs for a config: `cfg.env_kwargs` verbatim, plus the opponent
    for a self-play config. {} for a pre-Phase-4 config, which is what keeps
    all of Phases 0-3 untouched.

    `key` selects which opponent: "opponent" for the training env,
    "eval_opponent" for the eval env. They are deliberately separate. Eval
    must run against a FIXED external anchor and never against a pool
    member: under self-play a policy scores ~50% against its own snapshots
    by construction, so a pool-based eval measures nothing about strength
    and would report an equilibrium as a plateau. `cfg.env_kwargs` may not
    carry either opponent key for exactly that reason — one dict that fed
    both envs would erase the distinction this function exists to enforce.
    """
    reserved = cfg.env_kwargs.keys() & {"opponent", "eval_opponent"}
    if reserved:
        raise ValueError(
            f"env_kwargs may not set {sorted(reserved)}; opponents are configured "
            "under `selfplay`, which keeps the training and eval opponents separate"
        )
    # Strict selfplay.* keys (2026-08-29, CLEANUP B2). Every selfplay read is
    # a .get(), and train.py checks only for MISSING required keys — so a
    # typo'd knob used to load clean and train a full run with no error and
    # no metric that looks wrong. Unknown keys fail here, the same choke
    # point the reserved-key check uses (both env constructions route
    # through this function before any training work starts).
    known = {"opponent", "eval_opponent", "pool_size", "latest_prob",
             "push_every_updates"}
    unknown = cfg.selfplay.keys() - known
    if unknown:
        raise ValueError(
            f"unknown selfplay key(s) {sorted(unknown)}; known: {sorted(known)}. "
            "(pfsp_power and fixed_mix were removed 2026-08-29, CLEANUP A4)"
        )
    kwargs = dict(cfg.env_kwargs)
    if not cfg.selfplay:
        return kwargs
    if key not in cfg.selfplay:
        raise ValueError(f"selfplay config must set {key!r}; got {sorted(cfg.selfplay)}")
    return kwargs | {"opponent": cfg.selfplay[key]}


def make_eval_env(
    cfg, render_mode: str | None = None, extra_env_kwargs: dict | None = None
) -> gym.Env:
    """The eval env for a config. Every eval site goes through here — the
    train loop's best-checkpoint eval and all three of scripts/{watch,
    record,eval_checkpoint}.py — so that none of them can silently evaluate
    a self-play run against the env's DEFAULT opponent instead of the
    configured anchor. `extra_env_kwargs` merge over the config-derived ones
    for eval-site extras (e.g. Showdown replay saving in watch.py); the
    opponent keys come from the config and may not be overridden."""
    env_kwargs = selfplay_env_kwargs(cfg, "eval_opponent")
    if extra_env_kwargs:
        overlap = extra_env_kwargs.keys() & env_kwargs.keys()
        assert not overlap, f"extra_env_kwargs may not override {sorted(overlap)}"
        env_kwargs |= extra_env_kwargs
    return make_env(
        cfg.env_id,
        cfg.seed,
        render_mode=render_mode,
        env_kwargs=env_kwargs,
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

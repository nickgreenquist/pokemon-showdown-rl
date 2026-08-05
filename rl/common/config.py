"""Run configuration: one flat dataclass loaded from a YAML file.

Harness-level fields are typed here; anything algorithm-specific goes in
the loose `agent` dict, which each algorithm parses itself.
"""

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class Config:
    env_id: str
    seed: int
    total_steps: int
    eval_every: int  # env steps between eval passes
    eval_episodes: int  # episodes per eval pass
    run_name: str
    device: str = "cpu"  # CPU by default; MPS is flaky for this workload
    # Parallel training envs, used only by vectorized (on-policy) agents —
    # the train loop picks the collection path from the agent class, not
    # from this value. Scalar agents ignore it.
    num_envs: int = 1
    # Env-stack normalization (continuous track). Harness fields rather than
    # agent hparams: they are properties of the env wrapper chain, and their
    # statistics are checkpointed alongside the policy. Default off, so every
    # discrete-track config and checkpoint predating them is untouched — the
    # spine's no-op proof is that the wrappers are never constructed.
    normalize_obs: bool = False
    normalize_reward: bool = False
    # Intra-op torch threads. 1 by default: per-step RL kernels are tiny, so
    # the default pool thrashes (5x+ measured slowdown), and one core per run
    # is what lets multi-seed benchmarks parallelize. Raise it when the nets
    # and batches are big enough to amortize fork/join (capstone scale).
    torch_threads: int = 1
    # Self-play (Phase 4). `field(default_factory=dict)` and NOT `= {}`: a
    # mutable default is a ValueError at class-creation time, which would
    # take down every import in the repo, not just this file.
    # Keys: opponent (training), eval_opponent (the fixed external anchor),
    # and from chunk 2 the pool settings. Empty for every pre-Phase-4 config,
    # which is what makes all of this a no-op on existing runs.
    selfplay: dict = field(default_factory=dict)
    # Emit eval/win_rate, computed from the env's info["outcome"]. Off by
    # default so no existing config or run changes shape.
    eval_win_rate: bool = False
    # Env steps between rungs of the checkpoint ladder the Phase 4 tournament
    # plays against; 0 disables it. Written by THRESHOLD CROSSING, never
    # `step % checkpoint_every` — the vector loop advances `step` by num_envs
    # at a time, so the modulo silently yields a third of the rungs at
    # num_envs 6 or 12.
    checkpoint_every: int = 0
    logger: str = "wandb"  # "wandb" | "tensorboard"
    agent: dict = field(default_factory=dict)


def run_dir(cfg: Config) -> Path:
    """Canonical output dir for a run. Shared by the train loop, the W&B
    logger (offline data colocates here), and the analysis scripts."""
    return Path("runs") / cfg.run_name


def load_config(path: str | Path) -> Config:
    """Load a YAML file into a Config. Unknown keys and wrong types raise TypeError."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    cfg = Config(**raw)
    # PyYAML reads `1e6` as a *string* (YAML 1.1 floats need a signed exponent),
    # so without this check a bad scalar only blows up deep in the train loop.
    for fld in fields(cfg):
        val = getattr(cfg, fld.name)
        if not isinstance(val, fld.type):
            raise TypeError(
                f"{path}: {fld.name} must be {fld.type.__name__}, "
                f"got {type(val).__name__} ({val!r})"
            )
    return cfg

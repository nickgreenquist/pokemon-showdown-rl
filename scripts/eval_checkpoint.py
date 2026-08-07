"""Re-evaluate a checkpointed policy under the standard eval protocol.

    python scripts/eval_checkpoint.py runs/<run>/best_checkpoint.pt --episodes 100

Why: best_checkpoint.pt is selected as the max over ~50 noisy training-time
evals, so its recorded score carries selection bias (the max of noisy
estimates is biased upward). A fresh pass with more episodes gives an
unbiased score — provided the episodes are new ones: on a SEEDED env, with a
deterministic policy and fixed seeds, the training-time eval episodes replay
near-identically (exactly, but for MinAtar's sticky-action carry across
episode boundaries), so they are skipped (the ladder starts at
cfg.eval_episodes).

On Showdown that skip is inert and the pairing it enables does not exist:
the server rolls teams and damage, so every pass draws fresh battles no
matter what seed it asks for (measured 2026-08-05 — see rl/common/evaluation
.py's module docstring). Showdown comparisons are UNPAIRED; buy precision
with battle count, not with seeds.

`eval/win_rate` in the report is the ENV-supplied outcome rate and is the
authoritative number; `wins_from_returns` is the same statistic computed the
unsafe way (counting positive returns) and is kept only as a cross-check —
they must agree, and a disagreement means a reward-sign bug.

Prints a JSON report; --out also writes it to a file.
"""

import argparse
import dataclasses
import json
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import _run_eval_episodes, eval_metrics
from rl.envs.make import make_env, make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def _opponent_from_checkpoint(path: str, seed: int):
    """Load a checkpoint into a frozen one-member pool behind a PoolPlayer —
    seat 2 for cross-play. Seat 1 plays deterministically (the locked eval
    protocol); the pool member samples (the pool contract) — asymmetric by
    protocol, so run both orientations of a pairing for a symmetric read."""
    from types import SimpleNamespace

    import gymnasium as gym

    from rl.envs.showdown import OBS_DIM, PoolPlayer
    from rl.selfplay.pool import SnapshotPool

    ckpt = load_checkpoint(path)
    cfg = Config(**ckpt["config"])
    # Spaces only — a real env here would open websockets just to read
    # shapes. Bounds mirror ShowdownSingles.observation_spaces.
    spaces = SimpleNamespace(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(10),
    )
    agent = make_agent(cfg, spaces)
    agent.load_state_dict(ckpt["agent"])
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    player.seed_rng(seed)
    return player


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", help="path to a checkpoint .pt")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument(
        "--opponent",
        help="override the checkpoint config's eval_opponent. Needed for a "
        "clone of a teacher that is not a registered in-process player: a "
        "Foul Play clone records eval_opponent='foulplay', but the LOCKED "
        "protocol scores against SimpleHeuristics, so the board stays "
        "comparable with every other number in the repo.",
    )
    parser.add_argument("--out", help="also write the JSON report here")
    parser.add_argument(
        "--opponent-checkpoint",
        help="cross-play: a second checkpoint drives seat 2 instead of the "
        "config's eval_opponent (Showdown only)",
    )
    parser.add_argument(
        "--no-shaping",
        action="store_true",
        help="zero hl_shaping from the checkpoint's env_kwargs before "
        "building the eval env. REQUIRED for every locked-protocol eval of "
        "a shaped (Rung 1+) checkpoint: returns become ±1 again, so the "
        "wins_from_returns cross-check — the standing guard against a "
        "reward-sign inversion — must agree with win_rate EXACTLY (R0-4), "
        "and the headline is produced by an env bit-for-bit the control's. "
        "make_eval_env cannot express this via extra kwargs (it asserts no "
        "overlap with config-derived kwargs), so this flag is the seam.",
    )
    args = parser.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    if args.no_shaping:
        cfg = dataclasses.replace(
            cfg, env_kwargs={**cfg.env_kwargs, "hl_shaping": 0.0}
        )
    if args.opponent:
        sp = dict(cfg.selfplay)
        sp["eval_opponent"] = args.opponent
        sp["opponent"] = args.opponent
        cfg = dataclasses.replace(cfg, selfplay=sp)
    torch.set_num_threads(cfg.torch_threads)
    if args.opponent_checkpoint:
        # Deliberate, loud bypass of the make_eval_env anchor doctrine:
        # cross-play scores checkpoint vs checkpoint, which no config
        # eval_opponent can express. The doctrine protects the fixed-anchor
        # read; this mode is explicitly not that read.
        assert cfg.env_id.startswith("Showdown"), "--opponent-checkpoint is Showdown-only"
        opponent = _opponent_from_checkpoint(args.opponent_checkpoint, cfg.seed)
        env = make_env(cfg.env_id, cfg.seed, env_kwargs={"opponent": opponent})
    else:
        # Frozen normalizer before make_agent: the agent builds against the
        # env's observation space, and the policy must see the same scale it
        # trained on.
        env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    # Skip the training-time eval episodes: best_checkpoint was *selected*
    # on those, and deterministic policy + fixed seeds replay them exactly.
    #
    # Through evaluate(), not eval_returns(), so the report carries the
    # ENV-SUPPLIED win rate. Every headline number in this repo is a win
    # rate, and until 2026-08-05 this script reported only raw returns, so
    # each one was computed downstream by counting +1s — which is the exact
    # form the metric's own spec review rejected: it reads the reward a sign
    # bug inverts, so an inversion reports 1.000 and sails through at the
    # ceiling. info["outcome"] cannot be forged by arithmetic on the rewards.
    # Both are reported: `win_rate` is authoritative, `wins_from_returns` is
    # the old definition kept as a cross-check, and they must agree.
    returns, outcomes, faints = _run_eval_episodes(
        agent, env, args.episodes, seed_start=cfg.eval_episodes
    )
    metrics = eval_metrics(returns, outcomes, faints, win_rate=cfg.eval_win_rate)
    report = {
        "checkpoint": args.checkpoint,
        "run_name": cfg.run_name,
        "env_id": cfg.env_id,
        "step": ckpt["step"],
        "episodes": args.episodes,
        "seed_start": cfg.eval_episodes,
        "return_mean": float(np.mean(returns)),
        "return_std": float(np.std(returns)),
        **metrics,
        "wins_from_returns": sum(1 for r in returns if r > 0) / len(returns),
        "ties_from_returns": sum(1 for r in returns if r == 0) / len(returns),
        "returns": returns,
    }
    if args.opponent_checkpoint:
        report["opponent_checkpoint"] = args.opponent_checkpoint
    if args.no_shaping:
        # Audit trail for R0-4: the locked eval of a shaped checkpoint must
        # carry this flag, and the report is where that is checked.
        report["no_shaping"] = True
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    env.close()


if __name__ == "__main__":
    main()

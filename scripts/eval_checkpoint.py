"""Re-evaluate a checkpointed policy under the standard eval protocol.

    python scripts/eval_checkpoint.py runs/<run>/best_checkpoint.pt --episodes 100

Why: best_checkpoint.pt is selected as the max over ~50 noisy training-time
evals, so its recorded score carries selection bias (the max of noisy
estimates is biased upward). A fresh pass with more episodes gives an
unbiased score — provided the episodes are new ones: with a deterministic
policy and fixed seeds, the training-time eval episodes replay
near-identically (exactly, but for MinAtar's sticky-action carry across
episode boundaries), so they are skipped (the ladder starts at
cfg.eval_episodes). The re-eval seeds are still fixed and shared across
runs, so scores stay directly comparable — including paired per-episode
comparisons between variants (approximate, not exact: see eval_returns).

Prints a JSON report; --out also writes it to a file.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import eval_returns
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", help="path to a checkpoint .pt")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--out", help="also write the JSON report here")
    args = parser.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)
    # Frozen normalizer before make_agent: the agent builds against the env's
    # observation space, and the policy must see the same scale it trained on.
    env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    # Skip the training-time eval episodes: best_checkpoint was *selected*
    # on those, and deterministic policy + fixed seeds replay them exactly.
    returns = eval_returns(agent, env, args.episodes, seed_start=cfg.eval_episodes)
    report = {
        "checkpoint": args.checkpoint,
        "run_name": cfg.run_name,
        "env_id": cfg.env_id,
        "step": ckpt["step"],
        "episodes": args.episodes,
        "seed_start": cfg.eval_episodes,
        "return_mean": float(np.mean(returns)),
        "return_std": float(np.std(returns)),
        "returns": returns,
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    env.close()


if __name__ == "__main__":
    main()

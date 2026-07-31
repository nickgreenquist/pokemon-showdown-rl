"""Watch a checkpointed policy play its env in a render window.

    python scripts/watch.py runs/<run_name>/checkpoint.pt [--episodes N] [--fps N]

The checkpoint carries its own config, so the agent and env are rebuilt
from it directly — no YAML needed. Plays the deterministic (eval) policy.

Showdown runs have no render window; they are watched through Showdown
replays instead: each battle is saved as a replay HTML (the official
animated viewer — open in a browser, needs internet for the viewer JS,
needs the local server running to PLAY the battles) under
runs/<run_name>/replays/, or --replay-dir. Both seats save, so every
battle yields two near-identical files; open either.
"""

import argparse
import time
from pathlib import Path

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", help="path to a checkpoint.pt")
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="render speed; lower = slow motion (env defaults: CartPole 50, FrozenLake 4)",
    )
    parser.add_argument(
        "--replay-dir",
        default=None,
        help="Showdown only: where replay HTMLs go (default runs/<run_name>/replays)",
    )
    args = parser.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    showdown = cfg.env_id.startswith("Showdown")
    if showdown:
        replay_dir = Path(args.replay_dir or Path("runs") / cfg.run_name / "replays")
        env = make_eval_env(cfg, extra_env_kwargs={"save_replays": str(replay_dir)})
        print(f"saving replays to {replay_dir}/ — open any .html in a browser")
    else:
        env = make_eval_env(cfg, render_mode="human")
        if args.fps:
            # The human renderer paces its clock off this metadata entry.
            env.unwrapped.metadata["render_fps"] = args.fps
    # Normalized runs must be watched through their own statistics, or the
    # policy sees observations on a scale it never trained on.
    env = frozen_obs_env(env, cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    for episode in range(args.episodes):
        obs, info = env.reset()  # unseeded on purpose: fresh episodes every run
        mask = info.get("action_mask")
        ep_return, ep_length, done = 0.0, 0, False
        while not done:
            obs, reward, terminated, truncated, info = env.step(
                agent.act(obs, mask, deterministic=True)
            )
            mask = info.get("action_mask")
            ep_return += float(reward)
            ep_length += 1
            print(f"\repisode {episode + 1}: step {ep_length}, return {ep_return:g} ", end="", flush=True)
            done = terminated or truncated
        if showdown:
            result = {1: "WIN", 0: "tie", -1: "loss"}[info["outcome"]]
            print(f"— {result} after {ep_length} decisions")
        else:
            outcome = "terminal state" if terminated else "time limit"
            print(f"— {outcome} after {ep_length} steps, return {ep_return:g}")
            time.sleep(1.0)  # visible episode boundary before the env resets
    env.close()


if __name__ == "__main__":
    main()

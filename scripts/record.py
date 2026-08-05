"""Record a checkpointed policy's greedy rollouts as an annotated GIF.

    python scripts/record.py runs/<run>/best_checkpoint.pt [--episodes N] [--seed N]
        [--max-steps N] [--fps N] [--scale N] [--out PATH]

The checkpoint carries its own config, so the agent and env are rebuilt from
it directly — no YAML needed. Plays the deterministic (eval) policy under
render_mode="rgb_array", stamps episode/step/return on a bar under the
playfield, and writes every episode into one GIF (default: next to the
checkpoint). Episodes are fresh every invocation unless --seed pins them;
per-episode returns print to the terminal, so re-roll until one is worth
keeping.

--max-steps is a recorder cap, not an env limit: MinAtar has no time limit
and strong policies can be effectively immortal under greedy play (the
10k-step eval-protocol lesson), so an uncapped recording may never end.
"""

import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent

TARGET_WIDTH = 320  # upscale small playfields (MinAtar is 10x10) to at least this
HOLD_MS = 1200  # linger on each episode's final frame so the return is readable


def compose(raw, scale: int, bar_h: int, font, text: str) -> Image.Image:
    """One GIF frame: the (upscaled) playfield with a HUD bar underneath."""
    arr = np.asarray(raw)
    if arr.dtype != np.uint8:  # MinAtar's rgb_array is palette floats in [0, 1]
        arr = (arr * 255).round().astype(np.uint8)
    img = Image.fromarray(arr)
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
    frame = Image.new("RGB", (img.width, img.height + bar_h))  # black, so the bar letterboxes
    frame.paste(img)
    draw = ImageDraw.Draw(frame)
    draw.text((8, img.height + bar_h // 2), text, fill="white", font=font, anchor="lm")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", help="path to a checkpoint .pt")
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument(
        "--seed", type=int, default=None,
        help="seed the env for a reproducible recording (default: fresh episodes)",
    )
    parser.add_argument(
        "--max-steps", type=int, default=2000,
        help="per-episode recorder cap; immortal policies never terminate on their own",
    )
    parser.add_argument("--fps", type=int, default=15, help="playback speed (MinAtar real-time is 20)")
    parser.add_argument(
        "--scale", type=int, default=None,
        help=f"integer upscale factor (default: fit small frames to ~{TARGET_WIDTH}px wide)",
    )
    parser.add_argument("--out", help="output .gif path (default: <checkpoint dir>/<stem>.gif)")
    args = parser.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)
    # Frozen statistics for normalized runs; render frames are unaffected
    # (the wrapper transforms observations, not pixels).
    env = frozen_obs_env(make_eval_env(cfg, render_mode="rgb_array"), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    obs, info = env.reset(seed=args.seed)
    mask = info.get("action_mask")
    probe = np.asarray(env.render())  # sizes the HUD before any steps are taken
    scale = args.scale or max(1, round(TARGET_WIDTH / probe.shape[1]))
    font_size = min(24, max(12, probe.shape[1] * scale // 20))
    font = ImageFont.load_default(size=font_size)
    bar_h = font_size + 12

    frames: list[Image.Image] = []
    durations: list[int] = []  # per-frame display ms
    frame_ms = round(1000 / args.fps)
    for episode in range(1, args.episodes + 1):
        if episode > 1:
            obs, info = env.reset()
            mask = info.get("action_mask")
        ep_return, terminated, truncated = 0.0, False, False
        for step in range(args.max_steps + 1):  # step 0 is the reset frame
            if step > 0:
                obs, reward, terminated, truncated, info = env.step(
                    agent.act(obs, mask, deterministic=True)
                )
                mask = info.get("action_mask")
                ep_return += float(reward)
            # Integer returns (MinAtar) print bare; float returns (LunarLander) at 1 dp.
            ret = f"{ep_return:.0f}" if ep_return == int(ep_return) else f"{ep_return:.1f}"
            text = f"ep {episode}/{args.episodes}   step {step}   return {ret}"
            frames.append(compose(env.render(), scale, bar_h, font, text))
            durations.append(frame_ms)
            if terminated or truncated:
                break
        durations[-1] = max(HOLD_MS, frame_ms)
        outcome = (
            "terminal state" if terminated
            else "env time limit" if truncated
            else f"recorder cap ({args.max_steps} steps)"
        )
        print(f"episode {episode}: {outcome} after {step} steps, return {ep_return:g}")
    env.close()

    out = Path(args.out) if args.out else Path(args.checkpoint).with_suffix(".gif")
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True
    )
    print(f"{len(frames)} frames ({sum(durations) / 1000:.1f}s) -> {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

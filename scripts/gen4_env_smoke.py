"""Gen-4 env contract smoke: drive `ShowdownGen4-v0` through the harness's
factory with random MASKED actions for N battles on the local server.

Asserts the harness contracts at every step (obs shape/dtype/bounds,
info["action_mask"] present and boolean, info["outcome"] at the end,
info["privileged"] width when requested), counts wait-states absorbed and
mask-desync recoveries, and reports s/battle. No learner, no checkpoint.

    python scripts/gen4_env_smoke.py --battles 20 --opponent heuristics
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rl.envs.make import make_env  # noqa: E402
from rl.envs.gen4.spec import LAYOUT, OBS_DIM_GEN4  # noqa: E402
from rl.envs.showdown import mask_desync_total  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--battles", type=int, default=10)
    ap.add_argument("--opponent", default="heuristics")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--privileged", action="store_true")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    env = make_env(
        "ShowdownGen4-v0", seed=args.seed,
        env_kwargs={"opponent": args.opponent, "privileged": args.privileged},
    )
    assert env.observation_space.shape == (OBS_DIM_GEN4,), env.observation_space
    assert int(env.action_space.n) == 10
    outcomes: Counter = Counter()
    steps = 0
    lengths = []
    t0 = time.time()
    obs, info = env.reset(seed=args.seed)
    ep_len = 0
    while len(lengths) < args.battles:
        assert obs.shape == (OBS_DIM_GEN4,) and obs.dtype == np.float32
        assert not np.isnan(obs).any() and obs.min() >= -1.0 and obs.max() <= 4.0, (obs.min(), obs.max())
        mask = info["action_mask"]
        assert mask.dtype == bool and mask.shape == (10,) and mask.any()
        if args.privileged:
            assert info["privileged"].shape == (LAYOUT.priv_dim,), info["privileged"].shape
        action = int(rng.choice(np.flatnonzero(mask)))
        obs, reward, terminated, truncated, info = env.step(action)
        steps += 1
        ep_len += 1
        if terminated or truncated:
            assert terminated and not truncated
            assert info["outcome"] in (-1, 0, 1) and reward == float(info["outcome"])
            outcomes[info["outcome"]] += 1
            lengths.append(ep_len)
            ep_len = 0
            obs, info = env.reset()
    wall = time.time() - t0
    env.close()
    print(
        f"battles={args.battles} steps={steps} wall={wall:.1f}s s/battle={wall / args.battles:.2f} "
        f"outcomes={dict(outcomes)} mean_len={np.mean(lengths):.1f} max_len={max(lengths)} "
        f"waits_absorbed={env.unwrapped.waits_absorbed} mask_desyncs={mask_desync_total()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

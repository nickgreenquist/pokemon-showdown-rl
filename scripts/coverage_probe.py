"""Game-tree coverage of a run's final agent in self-play (Phase 4 chunk 4).

    python scripts/coverage_probe.py runs/connect4_pool_s0

One of the two mechanism diagnostics behind the chunk-2 coverage-collapse
finding, promoted from session scratch to committed tooling (PLAN.md,
2026-07-27 diagnostics entry). It measures the 80% case of the pool draw
directly: the final agent plays `--games` SAMPLED games against a second
frozen copy of itself — the latest-snapshot matchup — and coverage is

- **distinct games**: the number of unique move sequences, and
- **mean common prefix**: the mean length of the shared opening across all
  unordered pairs of games (all-pairs, stated here because the original
  scratch run did not record the choice), in plies.

A healthy stochastic policy explores: the random-vs-random control measured
200/200 distinct with prefix 0.2. A collapsed one replays near-identical
games — the k4 probe arm measured 8/200 distinct with a 12.1-ply shared
prefix on games averaging 13.0 plies. The control runs every time because
its numbers are a property of the game, not the agent, and a drifted
control means the probe itself broke.

Both copies sample through `AgentOpponent` (its own torch generator, the
tournament's replay-isolation pattern); the np rng drives only heuristic
fallbacks, of which agent-vs-agent games have none.
"""

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.make import make_eval_env
from rl.selfplay.opponents import make_opponent, play_game
from rl.selfplay.pool import AgentOpponent
from rl.train import make_agent


def load_final(run_dir: Path):
    """The run's final agent (checkpoint.pt), loaded exactly as the
    tournament loads a rung."""
    path = run_dir / "checkpoint.pt"
    if not path.exists():
        raise SystemExit(f"{run_dir}: no checkpoint.pt — not a finished run dir")
    ckpt = load_checkpoint(path)
    cfg = Config(**ckpt["config"])
    if not cfg.selfplay:
        raise SystemExit(f"{path}: not a self-play run (empty selfplay config)")
    torch.set_num_threads(cfg.torch_threads)
    env = make_eval_env(cfg)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    env.close()
    return agent


def coverage(games: list[list[int]]) -> dict:
    distinct = len({tuple(g) for g in games})
    prefixes = []
    for a, b in combinations(games, 2):
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        prefixes.append(n)
    return {
        "games": len(games),
        "distinct": distinct,
        "mean_common_prefix": float(np.mean(prefixes)),
        "mean_length": float(np.mean([len(g) for g in games])),
    }


def play_pair(first, second, n_games: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    games = []
    for _ in range(n_games):
        moves: list[int] = []
        play_game(first, second, rng, moves=moves)
        games.append(moves)
    return coverage(games)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="a finished self-play run dir")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None,
                        help="JSON output path (default <run_dir>/coverage.json)")
    args = parser.parse_args()

    agent = load_final(args.run_dir)
    copies = []
    for i in range(2):
        opponent = AgentOpponent(agent, seed=args.seed * 2 + i)
        opponent.freeze()  # the installer calls freeze() — the contract
        copies.append(opponent)
    self_play = play_pair(copies[0], copies[1], args.games, args.seed)
    control = play_pair(
        make_opponent("random"), make_opponent("random"), args.games, args.seed
    )

    for name, row in (("self-play", self_play), ("random control", control)):
        print(f"{name:>15s}: {row['distinct']}/{row['games']} distinct, "
              f"mean common prefix {row['mean_common_prefix']:.1f} "
              f"of mean length {row['mean_length']:.1f}", flush=True)

    out = args.out or args.run_dir / "coverage.json"
    out.write_text(json.dumps({
        "run_dir": str(args.run_dir),
        "seed": args.seed,
        "self_play": self_play,
        "random_control": control,
    }, indent=2) + "\n")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

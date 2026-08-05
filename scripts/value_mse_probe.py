"""Critic error by state distribution (Phase 4 chunk 4).

    python scripts/value_mse_probe.py runs/connect4_pool_s0

The second mechanism diagnostic behind the chunk-2 coverage-collapse
finding, promoted from session scratch to committed tooling (PLAN.md,
2026-07-27 diagnostics entry). It tests the mechanism claim against its
benign twin: a low `loss/value` can mean "the critic is good" or "the
critic is good only where the policy lives". So the same critic is scored
on three state distributions — positions from the agent's own self-play,
from random-vs-random games, and from heuristic-vs-heuristic games —
`--positions` per generator, ONE position per game (uniform over its
plies; scoring every decision point of one game over-weights long games
and correlated states, the chunk-1 tactic-probe lesson).

Targets hold the CONTINUATION policy fixed so only the state distribution
varies: from each position, the mean outcome of `--k` mirror-self-play
continuations (the final agent sampling on both sides), signed from the
position's player to move — the same egocentric perspective the critic
sees. At gamma = 1 with a terminal-only reward that is exactly what the
critic is trained toward. The reported number is the MSE between critic
value and target per distribution.

Reference readings (2026-07-27, the three pathfinder finals): self-play /
random / heuristic MSE 0.783/1.112/1.228 (pool), 0.065/0.733/0.824 (lam1),
0.031/0.966/0.994 (k4) — the probe arms' critics were near-perfect on
their own games and wrong everywhere else, tracking distinct-game count
(`scripts/coverage_probe.py`) exactly.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.connect4 import Connect4Board
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


def sample_positions(first, second, n: int, rng) -> list[Connect4Board]:
    """One non-terminal position per game, uniform over its plies: the
    position BEFORE a uniformly drawn move index cannot be terminal,
    because a move was played from it."""
    positions = []
    for _ in range(n):
        moves: list[int] = []
        play_game(first, second, rng, moves=moves)
        t = int(rng.integers(len(moves)))
        board = Connect4Board()
        for col in moves[:t]:
            board.drop(col)
        positions.append(board)
    return positions


def critic_mse(agent, positions, cont_a, cont_b, k: int, rng) -> dict:
    targets = np.array([
        np.mean([play_game(cont_a, cont_b, rng, start=p) for _ in range(k)])
        for p in positions
    ])
    obs = torch.as_tensor(
        np.stack([p.planes() for p in positions]),
        dtype=torch.float32, device=agent.device,
    )
    with torch.no_grad():
        values = agent.critic(obs).squeeze(-1).cpu().numpy()
    return {
        "positions": len(positions),
        "mse": float(np.mean((values - targets) ** 2)),
        "mean_ply": float(np.mean([p.moves for p in positions])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="a finished self-play run dir")
    parser.add_argument("--positions", type=int, default=200)
    parser.add_argument("--k", type=int, default=8,
                        help="mirror-self-play continuations per position")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None,
                        help="JSON output path (default <run_dir>/value_mse.json)")
    args = parser.parse_args()

    agent = load_final(args.run_dir)
    copies = []
    for i in range(2):
        opponent = AgentOpponent(agent, seed=args.seed * 2 + i)
        opponent.freeze()  # the installer calls freeze() — the contract
        copies.append(opponent)

    generators = {
        "self_play": (copies[0], copies[1]),
        "random": (make_opponent("random"), make_opponent("random")),
        "heuristic": (make_opponent("heuristic"), make_opponent("heuristic")),
    }
    results = {}
    for idx, (name, (first, second)) in enumerate(generators.items()):
        rng = np.random.default_rng([args.seed, idx])
        positions = sample_positions(first, second, args.positions, rng)
        results[name] = critic_mse(agent, positions, copies[0], copies[1], args.k, rng)
        print(f"{name:>10s}: MSE {results[name]['mse']:.3f} over "
              f"{results[name]['positions']} positions "
              f"(mean ply {results[name]['mean_ply']:.1f})", flush=True)

    out = args.out or args.run_dir / "value_mse.json"
    out.write_text(json.dumps({
        "run_dir": str(args.run_dir),
        "seed": args.seed,
        "k": args.k,
        **results,
    }, indent=2) + "\n")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

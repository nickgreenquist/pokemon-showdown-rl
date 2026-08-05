"""Agent metrics over Pascal Pons' labelled position sets (Phase 4 chunk 4).

    python scripts/pons_agent_metrics.py runs/connect4_pool_s0

The absolute-strength instrument: the tournament ranks agents against each
other and the anchors; this grades the final agent against game-theoretic
ground truth. Two metric families, per the locked spec:

- **Value metrics — labels only, every set.** The critic's sign accuracy
  and Brier score over DECISIVE positions, per set (the draw fraction runs
  0-43% across sets, so an aggregate silently means different things; MAE
  is rejected outright — it ranks a constant-zero critic above a perfect
  gamma=1 critic, PLAN.md). At gamma=1 the critic learns P(win)-P(loss),
  so P(win) over decisive positions is (V+1)/2 and Brier is scored against
  the label's sign. The Begin sets appear here even though our solver
  cannot exhaust them: the value metrics need only Pons' labels.

- **Policy metrics — child solves, solver-exhausted sets only.** The
  deterministic policy move against `solver_move_scores`: optimal-move
  agreement, blunder rate (a SIGN-CLASS drop — win to non-win, or non-loss
  to loss — needs only child signs), and mean score regret in Pons units.
  Defaults to end_easy + middle_easy; middle_medium is tractable but
  multi-minute (root solves alone took 541 s), so it is opt-in and belongs
  in a terminal. Coverage is always reported: which sets ran, and every
  set's positions are scored in full — never subsample a Pons set to
  estimate anything (node counts are heavy-tailed).

One Solver per set, as everywhere: positions transpose, warm entries are
valid bounds anywhere.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.connect4 import Connect4Board
from rl.envs.make import make_eval_env
from rl.selfplay.solver import Bitboard, Solver, solver_move_scores
from rl.train import make_agent

# Set names and download plumbing shared with scripts/pons_benchmark.py
# (duplicated, not imported: scripts are not a package, by repo convention).
SETS = {
    "end_easy": "Test_L3_R1",
    "middle_easy": "Test_L2_R1",
    "middle_medium": "Test_L2_R2",
    "begin_easy": "Test_L1_R1",
    "begin_medium": "Test_L1_R2",
    "begin_hard": "Test_L1_R3",
}
URLS = (
    "http://blog.gamesolver.org/data/{name}",
    "https://raw.githubusercontent.com/gamesolver/gamesolver.github.io/master/data/{name}",
)


def fetch(name: str, data_dir: Path) -> Path:
    path = data_dir / name
    if path.exists():
        return path
    data_dir.mkdir(parents=True, exist_ok=True)
    for url in (u.format(name=name) for u in URLS):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read()
            break
        except OSError as err:
            print(f"  {url}: {err}", flush=True)
    else:
        raise SystemExit(f"could not download {name} from any source")
    path.write_bytes(body)
    print(f"  downloaded {name} ({len(body)} bytes) from {url}", flush=True)
    return path


def load_final(run_dir: Path, allow_non_selfplay: bool = False):
    """The run's final agent (checkpoint.pt), loaded exactly as the
    tournament loads a rung. The selfplay guard catches the wrong KIND of
    run being scored by mistake; the supervised diagnostic opts out of it
    explicitly (--allow-non-selfplay), never silently."""
    path = run_dir / "checkpoint.pt"
    if not path.exists():
        raise SystemExit(f"{run_dir}: no checkpoint.pt — not a finished run dir")
    ckpt = load_checkpoint(path)
    cfg = Config(**ckpt["config"])
    if not cfg.selfplay and not allow_non_selfplay:
        raise SystemExit(f"{path}: not a self-play run (empty selfplay config); "
                         "pass --allow-non-selfplay if this is intentional")
    torch.set_num_threads(cfg.torch_threads)
    env = make_eval_env(cfg)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    env.close()
    return agent


def load_set(set_name: str, data_dir: Path) -> "list[tuple[str, int]]":
    lines = fetch(SETS[set_name], data_dir).read_text().splitlines()
    return [(moves, int(score)) for moves, score in map(str.split, lines)]


def board_from_moves(moves: str) -> Connect4Board:
    board = Connect4Board()
    for digit in moves:
        board.drop(int(digit) - 1)
    return board


def value_metrics(agent, positions) -> dict:
    boards = [board_from_moves(moves) for moves, _ in positions]
    scores = np.array([score for _, score in positions])
    obs = torch.as_tensor(
        np.stack([b.planes() for b in boards]),
        dtype=torch.float32, device=agent.device,
    )
    with torch.no_grad():
        values = agent.critic(obs).squeeze(-1).cpu().numpy()
    decisive = scores != 0
    v, y = values[decisive], (scores[decisive] > 0)
    p_win = np.clip((v + 1.0) / 2.0, 0.0, 1.0)
    return {
        "positions": len(positions),
        "decisive": int(decisive.sum()),
        "sign_accuracy": float(np.mean((v > 0) == y)),
        "brier": float(np.mean((p_win - y) ** 2)),
    }


def policy_metrics(agent, positions) -> dict:
    solver = Solver()
    sign = lambda x: (x > 0) - (x < 0)
    agree = blunders = 0
    regrets = []
    for moves, _ in positions:
        board = board_from_moves(moves)
        col = int(agent.act(board.planes(), board.legal_mask(), deterministic=True))
        scores = solver_move_scores(solver, Bitboard.from_board(board))
        best = max(scores.values())
        agree += scores[col] == best
        blunders += sign(scores[col]) < sign(best)
        regrets.append(best - scores[col])
    return {
        "positions": len(positions),
        "optimal_move_agreement": agree / len(positions),
        "blunder_rate": blunders / len(positions),
        "mean_score_regret": float(np.mean(regrets)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="a finished self-play run dir")
    parser.add_argument("--value-sets", nargs="+", choices=sorted(SETS),
                        default=sorted(SETS),
                        help="sets for the label-only value metrics (default: all)")
    parser.add_argument("--policy-sets", nargs="+", choices=sorted(SETS),
                        default=["end_easy", "middle_easy"],
                        help="sets for the child-solve policy metrics "
                             "(middle_medium is multi-minute; Begin sets intractable)")
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                        help="JSON output path (default <run_dir>/pons_metrics.json)")
    parser.add_argument("--allow-non-selfplay", action="store_true",
                        help="score a non-self-play checkpoint (the supervised "
                             "diagnostic) instead of refusing it")
    args = parser.parse_args()

    agent = load_final(args.run_dir, allow_non_selfplay=args.allow_non_selfplay)
    result = {"run_dir": str(args.run_dir), "value": {}, "policy": {},
              "policy_coverage": f"{len(args.policy_sets)}/{len(SETS)} sets"}
    for name in args.value_sets:
        row = value_metrics(agent, load_set(name, args.data_dir))
        result["value"][name] = row
        print(f"value  {name:>13s}: sign acc {row['sign_accuracy']:.3f}  "
              f"brier {row['brier']:.3f}  over {row['decisive']}/{row['positions']} decisive",
              flush=True)
    for name in args.policy_sets:
        start = time.perf_counter()
        row = policy_metrics(agent, load_set(name, args.data_dir))
        result["policy"][name] = row
        print(f"policy {name:>13s}: agreement {row['optimal_move_agreement']:.3f}  "
              f"blunder {row['blunder_rate']:.3f}  regret {row['mean_score_regret']:.2f}  "
              f"({time.perf_counter() - start:.1f}s)", flush=True)
    print(f"policy coverage: {', '.join(args.policy_sets)} "
          f"({result['policy_coverage']}; every position of a run set is scored)",
          flush=True)

    out = args.out or args.run_dir / "pons_metrics.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

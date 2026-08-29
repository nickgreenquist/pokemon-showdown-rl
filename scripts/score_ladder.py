"""FALSE FRIEND — NOT the Showdown ladder, NOT the locked protocol. READ THIS FIRST.

    ##########################################################################
    # This is a CONNECT-4-ERA CHECKPOINT-RUNG scorer, kept for predecessor
    # lineage. "Ladder" here means the run's own ckpt_*.pt rungs, NOT the
    # real Showdown human ladder.
    #
    # IT BACKS NO BANKED NUMBER IN THIS REPO. Nothing it prints has ever been
    # quoted, and nothing it prints may be.
    #
    # Two ways it misleads on a Showdown run dir, both silent:
    #   1. Its default `--opponents random heuristic` is WRONG FOR SHOWDOWN —
    #      the env's key is `heuristics` (OPPONENT_PLAYERS, showdown.py:61-65),
    #      so the vs-SH half never runs. It prints the rung's `random` row
    #      first, flushed, and only then dies on the bad key; and if you
    #      "fix" the crash by passing `--opponents random`, it prints a full
    #      page of plausible per-rung win rates and exits 0. Lines that look
    #      exactly like results, against the weakest anchor, at the wrong n.
    #   2. It scores INTERMEDIATE checkpoints at 400 episodes. The locked
    #      protocol is the FINAL checkpoint, 3000 battles/seed, 3 seeds
    #      pooled, ties as non-wins, deterministic, vs SimpleHeuristicsPlayer.
    #      400 episodes on a rung is ~2.5x the se and the wrong checkpoint.
    #
    # USE INSTEAD:
    #   vs-SH, locked protocol .... scripts/eval_checkpoint.py
    #   the real Showdown ladder .. scripts/ladder.py (pre-reg
    #                               configs/eval/ladder_r*.yaml)
    #
    # Deleting this file is a maintainer call, not an agent's. Header added
    # 2026-08-28; the same warning is in scripts/README.md and CLAUDE.md.
    ##########################################################################

Original purpose, unchanged below: score a self-play run's checkpoint ladder
against fixed anchor opponents.

    python scripts/score_ladder.py runs/connect4_pool_s0 --episodes 400

Why both anchors when training already evals one: the chunk-1 gate found
opponent specialization in BOTH directions — a heuristic-trained policy beat
heuristic and missed the >=0.95 vs-random floor (0.81-0.89), while an
otherwise identical random-trained one hit 0.978 vs random and dropped to
0.203 vs heuristic. The pre-registered chunk-2 check is that POOL training
recovers the vs-random number with no heuristic arm at all, which requires
scoring every rung against both anchors regardless of which anchor the run's
own eval used. If it does not recover, the specialization is stronger than
the chunk-1 reading and the AlphaStar PFSP lever comes forward (SESSION_LOGS_PREDECESSOR.md).

Scores the numbered rungs (ckpt_*.pt) plus the final checkpoint.pt, standard
eval protocol (fixed seeds, deterministic policy, same episode ladder as
training-time eval). best_checkpoint.pt is deliberately NOT scored: it is
max-selected over noisy evals so its score carries selection bias, and per
SESSION_LOGS_PREDECESSOR.md it feeds no reported number — the chunk-3 tournament selects.
"""

import argparse
import dataclasses
import json
from pathlib import Path

import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import evaluate
from rl.envs.make import make_eval_env
from rl.envs.showdown import mask_desync_total
from rl.train import make_agent


def score_ladder(run_dir: Path, opponents: list[str], episodes: int) -> list[dict]:
    ladder = sorted(run_dir.glob("ckpt_*.pt")) + [run_dir / "checkpoint.pt"]
    if not ladder[-1].exists():
        raise SystemExit(f"{run_dir}: no checkpoint.pt — not a finished run dir")
    rows = []
    for path in ladder:
        ckpt = load_checkpoint(path)
        cfg = Config(**ckpt["config"])
        if not cfg.selfplay:
            raise SystemExit(f"{path}: not a self-play run (empty selfplay config)")
        torch.set_num_threads(cfg.torch_threads)
        for name in opponents:
            eval_cfg = dataclasses.replace(
                cfg, selfplay={**cfg.selfplay, "eval_opponent": name}
            )
            env = make_eval_env(eval_cfg)
            agent = make_agent(eval_cfg, env)
            agent.load_state_dict(ckpt["agent"])
            metrics = evaluate(agent, env, episodes, win_rate=True)
            env.close()
            row = {
                "checkpoint": path.name,
                "step": ckpt["step"],
                "opponent": name,
                "episodes": episodes,
                "win_rate": metrics["eval/win_rate"],
                "return_mean": metrics["eval/return_mean"],
                "return_std": metrics["eval/return_std"],
                # Recovered mask desyncs so far this process (cumulative
                # across rows); nonzero on a quoted number is a disclosure.
                "mask_desyncs": mask_desync_total(),
            }
            rows.append(row)
            print(
                f"{path.name:22s} step {row['step']:>9d}  vs {name:10s} "
                f"win_rate {row['win_rate']:.3f}  return {row['return_mean']:+.3f} "
                f"± {row['return_std']:.3f}",
                flush=True,
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="a self-play run directory under runs/")
    parser.add_argument("--episodes", type=int, default=400)
    parser.add_argument(
        "--opponents", nargs="+", default=["random", "heuristic"],
        help="anchor names resolved by make_opponent",
    )
    parser.add_argument("--out", help="also write the rows as JSON here")
    args = parser.parse_args()

    rows = score_ladder(Path(args.run_dir), args.opponents, args.episodes)
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()

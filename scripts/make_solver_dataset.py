"""Solver-labeled position dataset for the supervised diagnostic (chunk 4).

    python scripts/make_solver_dataset.py --positions 100000

Samples one non-terminal position per random playout, uniform over its
plies at >= --min-stones, and labels it with EXACT per-move solver values
(`solver_move_scores`) plus the position's game-theoretic sign. Written to
a gitignored data/ .npz — solver output, like the Pons downloads, is
never committed.

The tractable-band scoping (PLAN.md, 2026-07-29 scheduling entry): exact
labels for the early game are the measured-intractable Begin regime, so
the floor is 12 stones (measured frontier: 8-33% yield below 12, ~100%
at 18+, median solve sub-ms) and the tail is bounded by a per-solve node
budget — a capped solve raises and the position is REJECTED, never
mislabeled. One warm solver is shared across the whole run (entries are
position-keyed bounds, valid anywhere; each child solve gets its own
budget).

Two holdouts are structural, not procedural: positions whose bitboard key
appears in any downloaded Pons set are skipped (the sets are the
measuring instrument — training on them would make the metrics
meaningless), and duplicate positions are skipped by the same key (random
openings repeat; a duplicated training row silently over-weights it).

Columns: `planes` bool (N,2,6,7) — the exact observation the RL nets see;
`move_scores` int8 (N,7), Pons convention, ILLEGAL = -100; `value_sign`
int8 (N,) from the mover's perspective; `stones` int8 (N,).
"""

import argparse
import time
from pathlib import Path

import numpy as np

from rl.envs.connect4 import COLS, Connect4Board
from rl.selfplay.solver import Bitboard, SearchBudgetExceeded, Solver, solver_move_scores

ILLEGAL = -100

SETS = ("Test_L3_R1", "Test_L2_R1", "Test_L2_R2",
        "Test_L1_R1", "Test_L1_R2", "Test_L1_R3")


def pons_keys(data_dir: Path) -> set:
    """Bitboard keys of every downloaded Pons position — the held-out
    instrument. Only files already on disk count; the downloader lives in
    the benchmark scripts."""
    keys = set()
    for name in SETS:
        path = data_dir / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            bb = Bitboard()
            for digit in line.split()[0]:
                bb = bb.play(int(digit) - 1)
            keys.add(bb.key())
    return keys


def random_game(rng) -> "list[int]":
    board, moves = Connect4Board(), []
    while True:
        col = int(rng.choice(np.flatnonzero(board.legal_mask())))
        moves.append(col)
        if board.drop(col) or board.full():
            return moves


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positions", type=int, default=100000)
    parser.add_argument("--min-stones", type=int, default=12)
    parser.add_argument("--node-budget", type=int, default=200000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--data-dir", default="data", type=Path)
    parser.add_argument("--out", type=Path, default=None,
                        help="output .npz (default <data-dir>/solver_dataset.npz)")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    solver = Solver(node_budget=args.node_budget)
    held_out = pons_keys(args.data_dir)
    print(f"holding out {len(held_out)} Pons positions", flush=True)

    planes, move_scores, value_sign, stones = [], [], [], []
    seen: set = set()
    attempts = short = dup = capped = 0
    start = time.perf_counter()
    while len(planes) < args.positions:
        attempts += 1
        moves = random_game(rng)
        if len(moves) <= args.min_stones:
            short += 1
            continue
        t = int(rng.integers(args.min_stones, len(moves)))
        board = Connect4Board()
        for col in moves[:t]:
            board.drop(col)
        bb = Bitboard.from_board(board)
        if bb.key() in seen or bb.key() in held_out:
            dup += 1
            continue
        try:
            scores = solver_move_scores(solver, bb)
        except SearchBudgetExceeded:
            capped += 1
            continue
        seen.add(bb.key())
        row = np.full(COLS, ILLEGAL, dtype=np.int8)
        for col, score in scores.items():
            row[col] = score
        planes.append(board.planes())
        move_scores.append(row)
        value_sign.append(np.sign(max(scores.values())))
        stones.append(t)
        if len(planes) % 5000 == 0:
            elapsed = time.perf_counter() - start
            print(f"  {len(planes):6d}/{args.positions}  {elapsed:7.1f}s  "
                  f"capped {capped}  dup {dup}", flush=True)

    out = args.out or args.data_dir / "solver_dataset.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        planes=np.array(planes),
        move_scores=np.array(move_scores),
        value_sign=np.array(value_sign, dtype=np.int8),
        stones=np.array(stones, dtype=np.int8),
    )
    elapsed = time.perf_counter() - start
    kept = len(planes)
    print(f"{kept} positions in {elapsed:.1f}s ({kept / elapsed:.0f}/s): "
          f"{attempts} attempts, {short} short games, {dup} dup/held-out, "
          f"{capped} budget-capped", flush=True)
    counts = np.bincount(stones, minlength=42)
    print("stones distribution: " + " ".join(
        f"{s}:{counts[s]}" for s in range(args.min_stones, 42) if counts[s]), flush=True)
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

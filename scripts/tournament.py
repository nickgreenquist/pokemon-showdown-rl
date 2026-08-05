"""Round-robin tournament: a run's checkpoint ladder plus the four anchors.

    python scripts/tournament.py runs/connect4_pool_s0 --games 500

The chunk-3 instrument of record. Every pair of participants — the ladder
rungs (played by `AgentOpponent`, which SAMPLES: both sides stochastic is
the locked protocol, because a published Connect 4 round-robin found
deterministic play collapses repeat games into identical move sequences)
plus `random`/`heuristic`/`alphabeta2`/`alphabeta4` — plays `--games`
games, the first player alternated EXACTLY N/2 each way. Ratings are
Bradley-Terry by MM anchored at alphabeta2 = 0, with the seeded stratified
bootstrap and the intransitive-triple fraction against its acyclic null
band (rl/selfplay/elo.py holds the guards and their reasons).

Replay isolation: every matchup gets its own np rng seeded by (seed,
pair, colour) and freshly wrapped AgentOpponents with matchup-derived
torch seeds, so any single matchup can be rerun alone, bit-identical,
without replaying the 100+ matchups before it.

best_checkpoint.pt is deliberately NOT a participant: it is max-selected
over noisy evals, so its rating would carry selection bias — per PLAN.md
it feeds no reported number; this tournament is what selects.

At 500 games/pair the 95% CI width is ~43 Elo (vs ~90 at 100), against
adjacent rungs sitting ~65 Elo apart. The campaign is a ~40-minute job —
alphabeta4's pure-Python search costs ~311 ms/game — so it runs in a
terminal, not an editor session.
"""

import argparse
import json
import time
from itertools import combinations
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.make import make_eval_env
from rl.selfplay.elo import bootstrap, cycle_null_band, intransitive_triples, rate
from rl.selfplay.opponents import make_opponent, play_game
from rl.selfplay.pool import AgentOpponent
from rl.train import make_agent

ANCHORS = ("random", "heuristic", "alphabeta2", "alphabeta4")


def load_ladder(run_dir: Path) -> dict:
    """name -> trained agent, in rung order; checkpoint.pt reports as
    'final'."""
    ladder = sorted(run_dir.glob("ckpt_*.pt")) + [run_dir / "checkpoint.pt"]
    if not ladder[-1].exists():
        raise SystemExit(f"{run_dir}: no checkpoint.pt — not a finished run dir")
    agents = {}
    for path in ladder:
        ckpt = load_checkpoint(path)
        cfg = Config(**ckpt["config"])
        if not cfg.selfplay:
            raise SystemExit(f"{path}: not a self-play run (empty selfplay config)")
        torch.set_num_threads(cfg.torch_threads)
        env = make_eval_env(cfg)
        agent = make_agent(cfg, env)
        agent.load_state_dict(ckpt["agent"])
        env.close()
        agents["final" if path.name == "checkpoint.pt" else path.stem] = agent
    return agents


def participant(entry, seed: int):
    """Anchors are stateless and rebuilt per matchup for free; agents are
    wrapped in a FRESH AgentOpponent with a matchup-derived seed, so its
    torch generator starts from a known state (the replay-isolation
    contract AgentOpponent's own generator exists for)."""
    if isinstance(entry, str):
        return make_opponent(entry)
    opponent = AgentOpponent(entry, seed=seed)
    opponent.freeze()  # the installer calls freeze() — the contract
    return opponent


def run_tournament(entries: dict, games: int, seed: int) -> dict:
    """All-pairs counts in elo.py's (first, second) -> (w, d, l) format."""
    counts = {}
    start = time.perf_counter()
    pairs = list(combinations(entries, 2))
    for m, (a, b) in enumerate(pairs):
        for colour, (first_name, second_name) in enumerate(((a, b), (b, a))):
            rng = np.random.default_rng([seed, m, colour])
            base = ((seed * 1_000_003 + m) * 2 + colour) * 2
            first = participant(entries[first_name], base)
            second = participant(entries[second_name], base + 1)
            outcomes = [play_game(first, second, rng) for _ in range(games // 2)]
            counts[(first_name, second_name)] = (
                sum(o == 1 for o in outcomes),
                sum(o == 0 for o in outcomes),
                sum(o == -1 for o in outcomes),
            )
        elapsed = time.perf_counter() - start
        print(f"  [{m + 1:3d}/{len(pairs)}] {a} vs {b}  "
              f"{counts[(a, b)]} / {counts[(b, a)]}  {elapsed:7.1f}s", flush=True)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="a finished self-play run dir")
    parser.add_argument("--games", type=int, default=500,
                        help="games per pair; must be even (exact colour split)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--out", type=Path, default=None,
                        help="JSON output path (default <run_dir>/tournament.json)")
    args = parser.parse_args()
    if args.games % 2:
        raise SystemExit("--games must be even: the first player alternates N/2 exactly")

    entries = dict(load_ladder(args.run_dir))
    for anchor in ANCHORS:
        entries[anchor] = anchor
    print(f"{len(entries)} participants, {args.games} games/pair, "
          f"{len(entries) * (len(entries) - 1) // 2} pairs", flush=True)

    counts = run_tournament(entries, args.games, args.seed)
    total = sum(sum(cell) for cell in counts.values())
    draws = sum(cell[1] for cell in counts.values())
    print(f"{total} games, {draws} draws ({draws / total:.1%})", flush=True)

    result = rate(counts, anchor="alphabeta2")
    boot = bootstrap(counts, anchor="alphabeta2", B=args.bootstrap, seed=args.seed)
    fraction, n_triples = intransitive_triples(counts)
    band = cycle_null_band(counts, result.ratings, seed=args.seed)

    for name in result.ceilinged:
        print(f"{name:>18s}  CEILING (undefeated; above every rated player)")
    for name, elo in sorted(result.ratings.items(), key=lambda kv: -kv[1]):
        lo, hi = boot.intervals[name]
        print(f"{name:>18s}  {elo:+7.1f}  [{lo:+7.1f}, {hi:+7.1f}]  "
              f"rated in {boot.rated_in[name]}/{args.bootstrap - boot.failed}",
              flush=True)
    for name in result.floored:
        print(f"{name:>18s}  FLOOR (scored nothing; below every rated player)")
    print(f"bootstrap resamples failed: {boot.failed}/{args.bootstrap}")
    print(f"intransitive triples: {fraction:.4f} of {n_triples} "
          f"(acyclic null band [{band[0]:.4f}, {band[1]:.4f}])", flush=True)

    out = args.out or args.run_dir / "tournament.json"
    out.write_text(json.dumps({
        "run_dir": str(args.run_dir),
        "games_per_pair": args.games,
        "seed": args.seed,
        "counts": {f"{a}|{b}": cell for (a, b), cell in counts.items()},
        "ratings": result.ratings,
        "floored": result.floored,
        "ceilinged": result.ceilinged,
        "intervals": boot.intervals,
        "rated_in": boot.rated_in,
        "bootstrap_failed": boot.failed,
        "intransitive_fraction": fraction,
        "triples": n_triples,
        "null_band": band,
    }, indent=2) + "\n")
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

"""Forgetting measures over tournamented ladders (Phase 4 chunk 4).

    python scripts/forgetting.py runs/connect4_pool_s0 runs/connect4_naive_s0

Consumes each run's tournament.json — the full pairwise counts are already
there, so no games are played — and reports the two locked measures:

- **AlphaStar min-winrate proxy (PRIMARY)**: each rung's minimum pooled
  win rate against any earlier rung, averaged over rungs (Nature 2019
  Fig. 3C/D). Higher is better; a naive self-play run that forgets shows
  rungs losing outright to specific earlier selves.
- **Regression rate (SECONDARY)**: fraction of rung pairs where the later
  checkpoint loses the pairwise majority to the earlier one — reported
  ONLY against its zero-forgetting null band (the run's own rating
  multiset rearranged monotone over steps, then resimulated), because the
  bare number reads a never-learns run at ~48%, worse than genuine
  forgetting's ~14% (PLAN.md, 2026-07-26 review).

Rungs are the step-ordered checkpoint ladder plus `final`;
`best_checkpoint.pt` never entered the tournament (selection bias), so it
cannot appear here either.
"""

import argparse
import json
from pathlib import Path

from rl.selfplay.elo import alphastar_proxy, regression_null_band, regression_rate


def analyze(run_dir: Path, band_b: int, seed: int) -> dict:
    data = json.loads((run_dir / "tournament.json").read_text())
    counts = {tuple(key.split("|")): tuple(cell) for key, cell in data["counts"].items()}
    names = {name for pair in counts for name in pair}
    rungs = sorted(n for n in names if n.startswith("ckpt_")) + ["final"]
    ratings = {name: data["ratings"][name] for name in rungs}

    proxy_mean, mins = alphastar_proxy(counts, rungs)
    rate = regression_rate(counts, rungs)
    band = regression_null_band(counts, ratings, rungs, B=band_b, seed=seed)
    return {
        "run_dir": str(run_dir),
        "rungs": rungs,
        "alphastar_proxy": proxy_mean,
        "min_winrates": mins,
        "regression_rate": rate,
        "regression_null_band": band,
        "band_b": band_b,
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", type=Path, nargs="+",
                        help="tournamented run dirs (tournament.json present)")
    parser.add_argument("--band-b", type=int, default=200,
                        help="null-band resamples (cycle_null_band's default)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    for run_dir in args.run_dirs:
        result = analyze(run_dir, args.band_b, args.seed)
        lo, hi = result["regression_null_band"]
        verdict = "ABOVE its null band" if result["regression_rate"] > hi else "inside its null band"
        print(f"{run_dir.name}", flush=True)
        print(f"  alphastar proxy {result['alphastar_proxy']:.3f}  min-winrates "
              + " ".join(f"{m:.2f}" for m in result["min_winrates"]), flush=True)
        print(f"  regression rate {result['regression_rate']:.3f} "
              f"[null {lo:.3f}, {hi:.3f}] — {verdict}", flush=True)
        out = run_dir / "forgetting.json"
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"  wrote {out}", flush=True)


if __name__ == "__main__":
    main()

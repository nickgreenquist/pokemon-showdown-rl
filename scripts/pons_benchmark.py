"""Validate the solver against Pascal Pons' labelled position sets.

    python scripts/pons_benchmark.py end_easy
    python scripts/pons_benchmark.py begin_easy begin_medium begin_hard

The solver's correctness rests on the brute-force differential; these 6000
externally labelled positions are the corroboration that the whole stack —
bitboard, search, transposition table, chapter-8 driver — agrees with
ground truth someone else computed (PLAN.md: no published training curve
exists for this phase, so exact oracles replace anchors).

Sets are downloaded on first use into a gitignored data/ directory and
never committed — the benchmark repo's license is null. HTTPS is broken on
blog.gamesolver.org (GitHub Pages cert for the wrong domain), so the
primary URL is plain http with the raw.githubusercontent.com mirror as
fallback. File format: one position per line, `<moves> <score>` — moves a
string of 1-indexed columns, score signed from the player to move with
magnitude 22 minus the winner's stone count, exactly the solver's own
convention.

Difficulty tracks REMAINING moves, not moves played, and "remaining"
excludes the final winning move — which is why the Begin sets are the
expensive ones (run those in a terminal, not an editor session; expect
tens of minutes). NEVER estimate a set's runtime from a subsample: node
counts are heavy-tailed (Middle-Easy median 738, mean 207,307,
max 96,290,338 measured pre-chapter-8).

One Solver (one transposition table) is shared across a set on purpose:
positions within a set transpose into each other, warm entries are valid
bounds wherever they are probed (the flag tests pin this), and batch
scoring is how chunk 3/4 will use the solver anyway.
"""

import argparse
import time
import urllib.request
from pathlib import Path

from rl.selfplay.solver import Bitboard, Solver

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


def run_set(set_name: str, data_dir: Path) -> bool:
    path = fetch(SETS[set_name], data_dir)
    lines = path.read_text().splitlines()
    if len(lines) != 1000:
        print(f"WARNING: {path} has {len(lines)} lines, expected 1000", flush=True)

    solver = Solver()
    failures = 0
    start = time.perf_counter()
    for i, line in enumerate(lines, start=1):
        moves, expected = line.split()
        bb = Bitboard()
        for digit in moves:
            bb = bb.play(int(digit) - 1)
        got = solver.solve(bb)
        if got != int(expected):
            failures += 1
            print(f"MISMATCH {set_name} line {i}: moves {moves} "
                  f"expected {expected} got {got}", flush=True)
        if i % 100 == 0:
            elapsed = time.perf_counter() - start
            print(f"  {set_name} {i:4d}/1000  {elapsed:8.1f}s elapsed  "
                  f"{solver.nodes:>12d} nodes", flush=True)

    elapsed = time.perf_counter() - start
    print(f"{set_name}: {1000 - failures}/1000 correct  {elapsed:.1f}s  "
          f"{solver.nodes} nodes  {solver.nodes / elapsed:,.0f} nodes/s", flush=True)
    return failures == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sets", nargs="+", choices=sorted(SETS),
                        help="which position sets to validate")
    parser.add_argument("--data-dir", default="data", type=Path)
    args = parser.parse_args()

    # List, not generator: every requested set runs even after a failure.
    ok = all([run_set(name, args.data_dir) for name in args.sets])
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

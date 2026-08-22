"""Chapter-3 grader: reads an executable pre-reg + the driver's finals and
prints the verdict — operative bar, governing se term BY NAME, every branch
cut in win-rate units, and the landing cell. Refuses a dirty tree or an
uncommitted pre-reg (the launch-from-a-clean-tree landmine, enforced instead
of remembered). Stamps the pre-reg sha256 + git sha into the readout JSON.

    python scripts/ch3_grade.py --prereg configs/eval/ch3_rung0.yaml
    python scripts/ch3_grade.py --selftest

R0 semantics (five_cell_floor): delta = pooled A1 (3 batches x 3000) minus
the EQUAL-WEIGHT MEAN of the four per-lane A0 rates. se terms:
  pooled_binomial_two_sample = sqrt(p1(1-p1)/n1 + (1/16)*sum_i p0i(1-p0i)/n0i)
  clustered_batch_lane       = sqrt(var(A1 batches)/3 + var(A0 lanes)/4)
se_gov = max of the two; hi = max(0.025, 2*se_gov). Cells partition the real
line (machine-checked): B5 (-inf,-hi] | B4 (-hi,-0.025] | B3 (-0.025,+0.025)
| B2 [+0.025,hi) | B1 [hi,+inf). When hi == 0.025 exactly, B2/B4 are EMPTY —
named, expected (the floor governs). R0-a is enforced on every chunk file:
eval/win_rate must equal wins_from_returns exactly.
"""

import argparse
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

import yaml

CREDIT_LINE = (
    "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where "
    "se_diff is the LARGER of the pooled-binomial se_diff and the "
    "seed-clustered se_diff, the latter computed from the per-seed finals at "
    "read time"
)
FLOOR = 0.025


def land(delta: float, hi: float) -> str:
    """The five_cell_floor partition. hi >= FLOOR always (hi = max(floor,
    2*se_gov)). Cells are mutually exclusive and cover the real line; the
    boundary memberships below ARE the pre-registered ones."""
    assert hi >= FLOOR - 1e-12
    if delta >= hi:
        return "B1"
    if FLOOR <= delta < hi:
        return "B2"
    if -FLOOR < delta < FLOOR:
        return "B3"
    if -hi < delta <= -FLOOR:
        return "B4"
    return "B5"


def check_partition(hi: float) -> None:
    """Machine-check: every probe lands in exactly one cell, ordering sane."""
    probes = sorted({-1.0, -hi - 1e-9, -hi, -hi + 1e-9, -FLOOR - 1e-9, -FLOOR,
                     -FLOOR + 1e-9, 0.0, FLOOR - 1e-9, FLOOR, hi - 1e-9, hi, 1.0})
    seen = [land(p, hi) for p in probes]
    assert all(s in {"B1", "B2", "B3", "B4", "B5"} for s in seen)
    order = {"B5": 0, "B4": 1, "B3": 2, "B2": 3, "B1": 4}
    ranks = [order[s] for s in seen]
    assert ranks == sorted(ranks), f"partition not monotone: {seen}"


def se_terms_r0(p1: float, n1: int, lane_rates: list[float], lane_n: int,
                batch_rates: list[float]) -> dict[str, float]:
    binom = math.sqrt(
        p1 * (1 - p1) / n1
        + sum(p * (1 - p) / lane_n for p in lane_rates) / len(lane_rates) ** 2
    )
    clus = math.sqrt(
        (statistics.stdev(batch_rates) ** 2) / len(batch_rates)
        + (statistics.stdev(lane_rates) ** 2) / len(lane_rates)
    )
    gov_name = "clustered_batch_lane" if clus >= binom else "pooled_binomial_two_sample"
    return {
        "pooled_binomial_two_sample": binom,
        "clustered_batch_lane": clus,
        "se_gov": max(binom, clus),
        "governing": gov_name,
    }


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def grade(prereg_path: str) -> dict:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    assert prereg["credit_line"] == CREDIT_LINE, (
        "pre-reg credit_line is not byte-equal to the module constant"
    )
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree is dirty; commit before grading:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"

    rdir = Path(prereg["results_dir"])
    # R0-a on every chunk file, both statistics exactly equal
    for chunk in sorted(rdir.glob("*.chunk*.json")):
        rep = json.loads(chunk.read_text())
        assert rep["eval/win_rate"] == rep["wins_from_returns"], (
            f"R0-a FAIL (reward-sign guard): {chunk.name}"
        )

    def final(job: str) -> dict:
        p = rdir / f"{job}.final.json"
        assert p.exists(), f"missing {p} — job incomplete"
        return json.loads(p.read_text())

    lanes = prereg["arms"]["A0"]["lanes"]
    lane_rates = [final(f"a0_{l}")["eval/win_rate"] for l in lanes]
    batch_finals = [final(f"a1_b{b}") for b in range(prereg["arms"]["A1"]["batches"])]
    batch_rates = [f["eval/win_rate"] for f in batch_finals]
    n1 = sum(f["episodes"] for f in batch_finals)
    p1 = sum(f["eval/win_rate"] * f["episodes"] for f in batch_finals) / n1
    a0_mean = sum(lane_rates) / len(lane_rates)
    delta = p1 - a0_mean

    terms = se_terms_r0(p1, n1, lane_rates, prereg["arms"]["A0"]["battles"], batch_rates)
    hi = max(FLOOR, 2 * terms["se_gov"])
    check_partition(hi)
    cell = land(delta, hi)

    loo = {}
    for l in lanes:
        p = rdir / f"a2_loo_{l}.final.json"
        if p.exists():
            loo[l] = json.loads(p.read_text())["eval/win_rate"] - a0_mean

    out = {
        "prereg": prereg_path,
        "prereg_sha256": hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest(),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "lane_rates": dict(zip(lanes, lane_rates)),
        "A0_equal_weight_mean": a0_mean,
        "A1_pooled": p1,
        "A1_batches": batch_rates,
        "delta": delta,
        **{k: v for k, v in terms.items()},
        "operative_bar_hi": hi,
        "cuts_win_rate_units": {
            "B5 <=": -hi, "B4 <=": -FLOOR, "B3 <": FLOOR, "B2 <": hi, "B1 >=": hi
        },
        "cell": cell,
        "B2_B4_empty": hi <= FLOOR + 1e-12,
        "A2_loo_deltas_recorded_never_governing": loo,
        "flip_rate": batch_finals[-1].get("ensemble_flip_rate"),
        "recorded_only": {
            "per_lane_median": statistics.median(lane_rates),
            "worst_lane": min(lane_rates),
        },
    }
    print(json.dumps(out, indent=2))
    print(
        f"\nVERDICT CELL: {cell} | delta {delta:+.5f} | operative bar {hi:.5f} "
        f"| governing se: {terms['governing']} ({terms['se_gov']:.5f})"
    )
    if out["B2_B4_empty"]:
        print("B2/B4 EMPTY (2*se_gov <= floor) — named, expected: the floor governs.")
    (rdir / "r0_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def selftest() -> None:
    """Synthetic known-p checks, one per cell + the empty-cell condition."""
    cases = [
        (+0.060, 0.004, "B1"),
        (+0.030, 0.004, "B1"),   # hi = floor -> B2 empty, 0.030 >= 0.025 = hi
        (+0.030, 0.020, "B2"),   # hi = 0.04 > delta >= floor
        (+0.010, 0.004, "B3"),
        (-0.010, 0.004, "B3"),
        (-0.030, 0.020, "B4"),
        (-0.060, 0.004, "B5"),
        (-0.030, 0.004, "B5"),
    ]
    for delta, se_gov, want in cases:
        hi = max(FLOOR, 2 * se_gov)
        check_partition(hi)
        got = land(delta, hi)
        assert got == want, f"selftest FAIL: delta {delta}, se {se_gov}: {got} != {want}"
    # boundary memberships
    assert land(FLOOR, max(FLOOR, 2 * 0.02)) == "B2"
    assert land(-FLOOR, max(FLOOR, 2 * 0.02)) == "B4"
    assert land(FLOOR, FLOOR) == "B1"       # hi == floor: B2 empty
    assert land(-FLOOR, FLOOR) == "B5"      # hi == floor: B4 empty
    # se arithmetic sanity: known inputs
    t = se_terms_r0(0.75, 9000, [0.73, 0.72, 0.72, 0.70], 3000, [0.75, 0.75, 0.75])
    assert abs(t["pooled_binomial_two_sample"] - math.sqrt(
        0.75 * 0.25 / 9000 + sum(p * (1 - p) / 3000 for p in [0.73, 0.72, 0.72, 0.70]) / 16
    )) < 1e-12
    print("ch3_grade selftest: ALL GREEN")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    assert args.prereg, "--prereg or --selftest"
    grade(args.prereg)


if __name__ == "__main__":
    main()

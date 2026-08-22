"""Chapter-3 RUNG-2 grader: paired per-lane deltas, the larger-of-THREE se
rule, F-gates before any branch is read, the KILL rule, and the R2-10 A0
stability gate. Refuses a dirty tree / uncommitted pre-reg; stamps pre-reg
sha256 + git sha into the readout. REFUSES TO GRADE a pre-reg whose status
still says DRAFT — registration (and the FG-2 route ruling it waits on) is
the maintainer's, not the grader's.

    python scripts/ch3_r2_grade.py --prereg configs/eval/ch3_rung2.yaml
    python scripts/ch3_r2_grade.py --selftest

R2 semantics (design §4 R2, ratified): d_i = p(A1S, lane) - p(A0, lane),
PAIRED on the four checkpoint lanes; delta = equal-weight mean of d_i.
se terms, larger-of-THREE (the third is the disclosed conservative
addition):
  pooled_binomial_two_sample = sqrt(sum_i [p1i(1-p1i)/n + p0i(1-p0i)/n])/4
  paired_clustered_sd_d      = sd(d_i)/sqrt(4)
  unpaired_two_sample_clustered = sqrt(var(p1_i)/4 + var(p0_i)/4)
se_gov = max of the three; hi = max(0.025, 2*se_gov); five_cell_floor
partition (machine-checked, same land() law as R0). F-gates evaluated and
reported BEFORE the cell: F3 here checks |leaves_mean - 353|/353 <= 0.25
per lane and that every chunk exists (a watchdog raise leaves a hole).
R2-5 (win_rate == wins_from_returns exactly) enforced on every chunk file.
KILL and the R2-10 A0-stability check are computed and printed; B3's
conditional R3 launch quotes the recorded R0 flip anchor.
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
    """five_cell_floor — identical law to ch3_grade.land (R0)."""
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
    probes = sorted({-1.0, -hi - 1e-9, -hi, -hi + 1e-9, -FLOOR - 1e-9, -FLOOR,
                     -FLOOR + 1e-9, 0.0, FLOOR - 1e-9, FLOOR, hi - 1e-9, hi, 1.0})
    seen = [land(p, hi) for p in probes]
    order = {"B5": 0, "B4": 1, "B3": 2, "B2": 3, "B1": 4}
    ranks = [order[s] for s in seen]
    assert ranks == sorted(ranks), f"partition not monotone: {seen}"


def se_terms_r2(p1: list[float], p0: list[float], n: int) -> dict[str, float]:
    """The three se terms over paired lane rates (equal-weight mean of d_i)."""
    k = len(p1)
    assert k == len(p0) >= 2
    d = [a - b for a, b in zip(p1, p0)]
    binom = math.sqrt(
        sum(a * (1 - a) / n + b * (1 - b) / n for a, b in zip(p1, p0))
    ) / k
    paired = statistics.stdev(d) / math.sqrt(k)
    unpaired = math.sqrt(
        statistics.stdev(p1) ** 2 / k + statistics.stdev(p0) ** 2 / k
    )
    terms = {
        "pooled_binomial_two_sample": binom,
        "paired_clustered_sd_d": paired,
        "unpaired_two_sample_clustered": unpaired,
    }
    gov = max(terms, key=terms.get)
    return {**terms, "se_gov": terms[gov], "governing": gov}


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def grade(prereg_path: str) -> dict:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    assert "DRAFT" not in str(prereg.get("status", "")), (
        "pre-reg status is DRAFT — the FG-2 route ruling and registration "
        "come first; the grader will not grade an unregistered pre-reg"
    )
    assert prereg["credit_line"] == CREDIT_LINE, (
        "pre-reg credit_line is not byte-equal to the module constant"
    )
    assert "PENDING" not in str(prereg.get("fg2_disposition", "")), (
        "fg2_disposition still PENDING — transcribe the ruling before grading"
    )
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree is dirty; commit before grading:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"

    rdir = Path(prereg["results_dir"])
    arms = prereg["arms"]
    lanes = arms["A0"]["lanes"]
    assert lanes == arms["A1S"]["lanes"], "paired read needs identical lanes"
    n = arms["A0"]["battles"]
    assert n == arms["A1S"]["battles"]

    # R2-5 on every chunk file, both arms
    for chunk in sorted(rdir.glob("*.chunk*.json")):
        rep = json.loads(chunk.read_text())
        assert rep["eval/win_rate"] == rep["wins_from_returns"], (
            f"R2-5 FAIL (reward-sign guard): {chunk.name}"
        )

    def final(job: str) -> dict:
        p = rdir / f"{job}.final.json"
        assert p.exists(), (
            f"missing {p} — job incomplete (a watchdog raise leaves a hole; "
            "re-run the killed chunk after diagnosis)"
        )
        return json.loads(p.read_text())

    a0 = {l: final(f"a0_{l}") for l in lanes}
    a1 = {l: final(f"a1s_{l}") for l in lanes}
    p0 = [a0[l]["eval/win_rate"] for l in lanes]
    p1 = [a1[l]["eval/win_rate"] for l in lanes]
    d = [x - y for x, y in zip(p1, p0)]
    delta = sum(d) / len(d)

    # ---- F-gates BEFORE the cell ----
    f_gates: dict[str, str] = {}
    exp_leaves = float(prereg["f3_leaves_expected"])
    band = float(prereg["f3_band"])
    for l in lanes:
        lm = a1[l].get("search/leaves_mean")
        if lm is None or abs(lm - exp_leaves) / exp_leaves > band:
            f_gates["F3"] = (
                f"lane {l}: leaves_mean {lm} vs expected {exp_leaves} "
                f"(band {band:.0%})"
            )
    # F1/F2 are re-run results outside this file; the grader requires their
    # transcript hashes to have been recorded by the operator:
    for gate in ("r2_1_fg_transcript", "r2_2_fg4_transcript"):
        if gate not in prereg:
            f_gates.setdefault("F1/F2", f"pre-reg lacks {gate} (record the "
                               "launch-sha FG re-run transcripts before grading)")

    # ---- R2-10 A0 stability ----
    a0_pooled = sum(p0) / len(p0)
    anchor = float(prereg["r2_10_a0_anchor"])
    tol = float(prereg["r2_10_a0_tolerance"])
    a0_stable = abs(a0_pooled - anchor) <= tol

    terms = se_terms_r2(p1, p0, n)
    hi = max(FLOOR, 2 * terms["se_gov"])
    check_partition(hi)
    cell = land(delta, hi)
    kill = delta <= 0 and sum(1 for x in d if x <= 0) >= 3

    out = {
        "prereg": prereg_path,
        "prereg_sha256": hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest(),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "lane_rates_A0": dict(zip(lanes, p0)),
        "lane_rates_A1S": dict(zip(lanes, p1)),
        "per_lane_deltas": dict(zip(lanes, d)),
        "delta_equal_weight_mean": delta,
        **terms,
        "operative_bar_hi": hi,
        "cell_IF_NO_F_GATE_FIRES": cell,
        "f_gates_fired": f_gates,
        "VOID": bool(f_gates),
        "kill_rule_fired": kill,
        "r2_10_A0_pooled": a0_pooled,
        "r2_10_A0_stable": a0_stable,
        "B2_B4_empty": hi <= FLOOR + 1e-12,
        "recorded_only": {
            "per_lane_median_delta": statistics.median(d),
            "worst_lane_delta": min(d),
            "search_flip_rate": {l: a1[l].get("search/flip_rate") for l in lanes},
            "placeholder_skip_rate": {
                l: a1[l].get("search/placeholder_skip_rate") for l in lanes
            },
            "ms_mean": {l: a1[l].get("search/ms_mean") for l in lanes},
        },
        "b3_r3_condition": prereg["b3_r3_condition"],
    }
    print(json.dumps(out, indent=2))
    if f_gates:
        print(f"\nVOID — F-gates fired: {f_gates}; no band is adjudicated.")
    else:
        print(
            f"\nVERDICT CELL: {cell} | delta {delta:+.5f} | bar {hi:.5f} | "
            f"governing se: {terms['governing']} ({terms['se_gov']:.5f})"
            + (" | KILL: R3 does not launch" if kill else "")
        )
    if not a0_stable:
        print(f"R2-10 A0-STABILITY FAIL: pooled {a0_pooled:.5f} vs anchor "
              f"{anchor} +/- {tol} — should have STOPPED before A1S.")
    (rdir / "r2_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def selftest() -> None:
    """Synthetic checks: cell landings, the three-term se arithmetic, the
    KILL rule, and the design's MF-8 arithmetic (2*se_binom ~ 0.0115 at
    p ~ 0.72, n = 3000, 4 lanes)."""
    p0 = [0.72, 0.71, 0.73, 0.70]
    # binomial arithmetic pin (MF-8): ~0.0115 at these rates
    t = se_terms_r2([p + 0.03 for p in p0], p0, 3000)
    assert abs(2 * t["pooled_binomial_two_sample"] - 0.0115) < 0.0005, t
    # paired term governs when lanes disagree wildly
    t2 = se_terms_r2([0.80, 0.66, 0.78, 0.68], p0, 3000)
    assert t2["governing"] in ("paired_clustered_sd_d", "unpaired_two_sample_clustered")
    # uniform +0.04 shift: paired sd of d collapses to 0 (pairing absorbs
    # lane-level variation) while the UNPAIRED term keeps it — the third
    # term raising the bar exactly as the disclosed addition intends
    t3 = se_terms_r2([p + 0.04 for p in p0], p0, 3000)
    assert t3["paired_clustered_sd_d"] < 1e-12
    assert t3["governing"] == "unpaired_two_sample_clustered"
    assert t3["unpaired_two_sample_clustered"] > t3["pooled_binomial_two_sample"]
    # cells
    for delta, se_gov, want in [(+0.060, 0.004, "B1"), (+0.030, 0.020, "B2"),
                                (+0.010, 0.004, "B3"), (-0.030, 0.020, "B4"),
                                (-0.060, 0.004, "B5")]:
        hi = max(FLOOR, 2 * se_gov)
        check_partition(hi)
        assert land(delta, hi) == want
    # KILL: delta <= 0 and >= 3 of 4 non-positive lanes
    d = [-0.01, -0.02, -0.005, +0.004]
    assert sum(x for x in d) / 4 <= 0 and sum(1 for x in d if x <= 0) >= 3
    print("ch3_r2_grade selftest: ALL GREEN")


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

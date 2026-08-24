"""CH3 R5a T-GATE grader (BI-A1): the three-cell teacher-headroom read.

    python scripts/ch3_r5a_grade.py --prereg configs/eval/ch3_r5a_tgate.yaml
    python scripts/ch3_r5a_grade.py --selftest

Decision rule (configs/eval/ch3_r5a_tgate.yaml, REGISTERED 2026-08-24,
verbatim): m_i = wr(TS_i) - wr(TM_i) per lane; aggregator = equal-weight
mean of the four m_i (median/worst recorded, never governing); se_gov =
larger-of-three via ch3_r2_grade.se_terms_r2 UNMODIFIED on (TS rates,
TM rates, n=1000); L = mean - 2*se_gov, U = mean + 2*se_gov, kpos =
#{m_i > 0}. Cells, TOTAL and DISJOINT, evaluated in order:
  T-PASS        U >= 0.05 AND L > 0 AND kpos >= 3
  T-FAIL        U < 0.05   (sub-rule: mean <= 0 -> T-FAIL/NULL verbatim
                sentence; mean > 0 -> T-FAIL/SHORT, the "does not hold"
                clause SUPPRESSED)
  T-UNRESOLVED  everything else (family does not close; r5b does not
                launch; the ONLY permitted retry is the pre-registered
                n=1500 both-arms re-run, maintainer's call)
Gates: F-A8 win_rate == wins_from_returns on every chunk (VOID); F-C
search integrity on TS arms — |leaves_mean - 353|/353 <= 0.25 AND every
chunk file exists (VOID: the gate is NOT READ and the family does NOT
close); F-M ms band [54.9, 91.5] (non-void, recorded); F-P pairing window
(TM span inside/overlapping TS span >= 0.80 of the shorter; non-void,
lane disclosed as unpaired); F-D mask desyncs (disclosure). Refuses a
DRAFT status, a dirty tree, or an uncommitted pre-reg.
"""

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from ch3_r2_grade import se_terms_r2  # noqa: E402

LANES = ["s62", "s63", "s64", "s65"]

FAIL_NULL = (
    "search@M's credited advantage is measured only against "
    "SimpleHeuristics; against the BC-FP clone, against Foul Play and "
    "against its own greedy self it does not hold. There is no expert to "
    "iterate on."
)
FAIL_SHORT = (
    "search@M does beat its own greedy self in mirror play, by mean(m_i) = "
    "{mean:+.5f} (per-lane {m62:+.4f}/{m63:+.4f}/{m64:+.4f}/{m65:+.4f}, "
    "2*se_gov = {se2:.5f}), but the margin is bounded above the "
    "pre-registered +0.05 headroom a lossy one-iteration student would "
    "need. The actor expert-iteration family closes for INSUFFICIENT "
    "TEACHER HEADROOM, not for absence of an edge."
)
UNRESOLVED = (
    "the T-GATE did not resolve: mean(m_i) = {mean:+.5f}, 2*se_gov = "
    "{se2:.5f}, lanes {m62:+.4f}/{m63:+.4f}/{m64:+.4f}/{m65:+.4f}. Neither "
    "the +0.05 headroom nor a zero margin is excluded. No conclusion about "
    "expert iteration is licensed from this run."
)


def cell_of(mean: float, se_gov: float, kpos: int) -> str:
    lo, up = mean - 2 * se_gov, mean + 2 * se_gov
    if up >= 0.05 and lo > 0 and kpos >= 3:
        return "T-PASS"
    if up < 0.05:
        return "T-FAIL/NULL" if mean <= 0 else "T-FAIL/SHORT"
    return "T-UNRESOLVED"


def _git(cmd):
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def _span(reports):
    return (min(r["started_at"] for r in reports),
            max(r["finished_at"] for r in reports))


def _overlap(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    shorter = min(a[1] - a[0], b[1] - b[0])
    return max(0.0, hi - lo) / shorter if shorter > 0 else 0.0


def grade(prereg_path: str) -> dict:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    assert "DRAFT" not in str(prereg.get("status", "")), "pre-reg is DRAFT"
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree dirty:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"
    rdir = Path(prereg.get("results_dir", "results/ch3_r5a"))

    gates, disclosures = {}, {}
    finals, chunks_by_arm = {}, {}
    for arm, spec in prereg["anchor_arms"].items():
        prefix = arm.lower()
        n_chunks = spec["chunks"]
        reports = []
        for k in range(n_chunks):
            p = rdir / f"{prefix}.chunk{k:02d}.json"
            if not p.exists():
                gates["F-C"] = f"{prefix}.chunk{k:02d}.json MISSING (completeness half of F-C)"
                continue
            rep = json.loads(p.read_text())
            if rep["eval/win_rate"] != rep["wins_from_returns"]:
                gates["F-A8"] = f"win-rate identity: {p.name}"
            reports.append(rep)
        chunks_by_arm[arm] = reports
        fp = rdir / f"{prefix}.final.json"
        if fp.exists():
            finals[arm] = json.loads(fp.read_text())

    for arm in prereg["anchor_arms"]:
        if arm.startswith("TS_"):
            f = finals.get(arm)
            lm = f.get("search/leaves_mean") if f else None
            if lm is None or abs(lm - 353) / 353 > 0.25:
                gates["F-C"] = f"{arm}: leaves_mean {lm}"
            ms = f.get("search/ms_mean") if f else None
            if ms is not None and not (54.9 <= ms <= 91.5):
                disclosures["F-M"] = f"{arm}: ms_mean {ms:.1f} outside [54.9, 91.5]"

    f_p = {}
    for lane in LANES:
        ts, tm = chunks_by_arm.get(f"TS_{lane.upper()}"), chunks_by_arm.get(f"TM_{lane.upper()}")
        if ts and tm and all("started_at" in r for r in ts + tm):
            ov = _overlap(_span(ts), _span(tm))
            f_p[lane] = {"overlap_frac": round(ov, 4), "paired": ov >= 0.80}
        else:
            f_p[lane] = {"overlap_frac": None, "paired": False}
    desyncs = {a: f.get("mask_desyncs", 0) for a, f in finals.items()}

    missing = [a for a in prereg["anchor_arms"] if a not in finals]
    assert not missing or "F-C" in gates, f"finals missing without F-C: {missing}"

    if gates:
        out = {"VOID": True, "gates_fired": gates,
               "note": "THE T-GATE IS NOT READ AND THE FAMILY DOES NOT CLOSE"}
        print(json.dumps(out, indent=2))
        return out

    ts_r = [finals[f"TS_{l.upper()}"]["eval/win_rate"] for l in LANES]
    tm_r = [finals[f"TM_{l.upper()}"]["eval/win_rate"] for l in LANES]
    m = [a - b for a, b in zip(ts_r, tm_r)]
    mean = sum(m) / 4
    terms = se_terms_r2(ts_r, tm_r, 1000)
    se_gov = terms["se_gov"]
    kpos = sum(1 for x in m if x > 0)
    cell = cell_of(mean, se_gov, kpos)
    fmt = dict(mean=mean, se2=2 * se_gov, m62=m[0], m63=m[1], m64=m[2], m65=m[3])
    sentence = {"T-PASS": "r5b becomes ELIGIBLE for ratification and build. Nothing else.",
                "T-FAIL/NULL": FAIL_NULL,
                "T-FAIL/SHORT": FAIL_SHORT.format(**fmt),
                "T-UNRESOLVED": UNRESOLVED.format(**fmt)}[cell]

    out = {
        "prereg": prereg_path,
        "prereg_sha256": hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest(),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "ts_rates": dict(zip(LANES, ts_r)),
        "tm_rates": dict(zip(LANES, tm_r)),
        "m_i": dict(zip(LANES, m)),
        "mean_m": mean,
        **terms,
        "L": mean - 2 * se_gov,
        "U": mean + 2 * se_gov,
        "kpos": kpos,
        "cell": cell,
        "licensed_sentence": sentence,
        "VOID": False,
        "f_m": disclosures.get("F-M"),
        "f_p_pairing": f_p,
        "f_d_desyncs": desyncs,
        "recorded_only": {
            "median_m": statistics.median(m),
            "worst_m": min(m),
            "ts_flip_rate": {l: finals[f"TS_{l.upper()}"].get("search/flip_rate") for l in LANES},
            "ts_skip_rate": {l: finals[f"TS_{l.upper()}"].get("search/placeholder_skip_rate") for l in LANES},
        },
    }
    print(json.dumps(out, indent=2))
    print(f"\nT-GATE CELL: {cell} | mean(m_i) {mean:+.5f} | 2*se_gov "
          f"{2*se_gov:.5f} | L {out['L']:+.5f} U {out['U']:+.5f} | kpos {kpos}")
    (rdir / "r5a_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def selftest() -> None:
    # cell law pins (registered examples + boundaries)
    assert cell_of(0.08, 0.014, 4) == "T-PASS"          # U .108, L .052
    assert cell_of(0.06, 0.014, 3) == "T-PASS"          # L .032 > 0
    assert cell_of(0.02, 0.014, 4) == "T-FAIL/SHORT"    # U .048 < .05, mean > 0
    assert cell_of(-0.01, 0.014, 1) == "T-FAIL/NULL"    # U .018 < .05, mean <= 0
    assert cell_of(0.00, 0.024, 2) == "T-FAIL/NULL"     # U .048 < .05
    assert cell_of(0.04, 0.014, 4) == "T-PASS"          # U .068, L .012, kpos 4
    assert cell_of(0.04, 0.025, 4) == "T-UNRESOLVED"    # L -.01 <= 0, U .09
    assert cell_of(0.06, 0.014, 2) == "T-UNRESOLVED"    # kpos < 3
    # near-boundary above: U .052 >= .05, kpos 2 blocks PASS -> UNRESOLVED
    # (exact U == 0.05 is float-representation-dependent; the law is total
    # either way — every float lands in exactly one cell)
    assert cell_of(0.036, 0.008, 2) == "T-UNRESOLVED"
    # se law import sanity
    t = se_terms_r2([0.55, 0.56, 0.54, 0.55], [0.50, 0.50, 0.50, 0.50], 1000)
    assert t["se_gov"] >= t["pooled_binomial_two_sample"]
    print("ch3_r5a_grade selftest: ALL GREEN")


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

"""CH3 R4 BI-5: the ANCHOR BATTERY grader (clone block + FP block).

    python scripts/ch3_r4_anchor_grade.py --prereg configs/eval/ch3_r4_ensemble_critic.yaml --delta-sh 0.031
    python scripts/ch3_r4_anchor_grade.py --selftest

Grades the battery pre-registered in configs/eval/ch3_r4_ensemble_critic.yaml
(section ANCHOR BATTERY). DESCRIPTIVE THROUGHOUT: `anchors_are_verdict_inputs:
false` — nothing here credits, vetoes or re-reads the primary; the battery
selects a README sentence and nothing else. The old P1/P2/P3 falsifier logic
is explicitly NOT inherited (the pre-reg rejects its sign-based P2, which
fires ~50% under exact transfer and manufactures caveats from noise).

WHAT IT COMPUTES, in the pre-reg's own terms:
  CA ERA TRIPWIRE   |wr(CA) - 0.894| <= 0.04 -> green; outside -> the clone
                    block is labelled DESCRIPTIVE-WITH-DRIFT-NOTE (never
                    VOID; it is non-crediting anyway).
  CLONE BLOCK       delta_C = wr(CE3) - wr(CE0);
                    se_C = sqrt(p3(1-p3)/n3 + p0(1-p0)/n0).
                    C-POS   delta_C >= +2*se_C   (one-sided POSITIVE)
                    C-UNRES |delta_C| <  2*se_C  (the ONLY two-sided cell)
                    C-NEG   delta_C <= -2*se_C   (one-sided NEGATIVE)
  CEILING GUARD     pointed at the COMPARATOR: wr(CE0) >= 0.90 replaces
                    C-POS and C-UNRES by "CEILING-LIMITED, descriptive"
                    (only C-NEG stays fireable) AND DEMOTES the exclusion
                    flag to a descriptive number that cannot select the
                    composite cell.
  EXCLUSION FLAG    U = delta_C + 1.96*se_C; U < delta_hat_SH -> commensurate
                    transfer EXCLUDED at 97.5% one-sided. delta_hat_SH is the
                    OBSERVED pooled primary delta REGARDLESS OF CELL (a
                    magnitude, not a claim) and is passed in with --delta-sh.
  FP BLOCK          delta_F = wr(FE3) - FROZEN 0.368, threshold PINNED at the
                    LITERAL 0.087 (the comparator is frozen, so the threshold
                    must not move with the data).
                    F-NEG delta_F <= -0.087; F-UNRES |delta_F| < 0.087;
                    F-POS delta_F >= +0.087.
                    CRASH-FORFEIT READ RULE applied from the runner's JSON:
                    n_eff = seat-finished minus crash-forfeits, our_wins
                    reduced by the same count; >= 30 relaunches VOIDs the arm.
  COMPOSITE MAP     by the pre-reg's precedence, TOTAL over all combinations:
                    1 any resolved NEG -> TRANSFER-NEGATIVE-RESOLVED
                    2 else exclusion fired AND no ceiling
                        -> COMMENSURATE-TRANSFER-EXCLUDED
                    3 else C-POS -> TRANSFER-POSITIVE (FP cannot veto)
                    4 else (incl. CEILING-LIMITED) -> TRANSFER-UNRESOLVED
  F-GATE TWINS      F8 (win_rate == wins_from_returns EXACTLY) on every arm
                    file; F-C twin on the search arms
                    (|leaves_mean - 353|/353 <= 0.25, timeouts == 0, every
                    chunk present); G3 on the FP arm.

Refuses to grade a dirty tree, an uncommitted pre-reg, or a pre-reg with any
"[MAINTAINER RULING" bracket left in it; stamps pre-reg sha256 + git sha into
results/ch3_r4_anchors/r4_anchor_readout.json.
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

FP_FROZEN_COMPARATOR = 0.368
FP_PINNED_THRESHOLD = 0.087
CEILING = 0.90
Z_ONE_SIDED_975 = 1.96
LEAVES_EXPECTED = 353.0
LEAVES_BAND = 0.25
MAX_RELAUNCHES = 30
COMPOSITE_PRECEDENCE = [
    "any_resolved_NEG",
    "exclusion_flag_fired_and_no_ceiling",
    "C_POS",
    "otherwise_unresolved",
]
ANCHOR_DIR = "results/ch3_r4_anchors"
FP_DIR = "results/ch3_r4_fp_anchor"


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


# --------------------------------------------------------------------------
# the pre-registered arithmetic (pure; --selftest drives these directly)
# --------------------------------------------------------------------------


def se_diff(p1: float, n1: int, p0: float, n0: int) -> float:
    """pre-reg CLONE BLOCK: se_C = sqrt(p3(1-p3)/1000 + p0(1-p0)/1000)."""
    return math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)


def c_cell(delta_c: float, se_c: float, ceiling_fired: bool) -> str:
    """pre-reg CLONE BLOCK partition (covers R) + CEILING GUARD. Order
    matters: under the ceiling only C-NEG stays fireable, and C-POS/C-UNRES
    both become CEILING-LIMITED."""
    assert se_c > 0, "se_C == 0: the partition is degenerate, diagnose first"
    if delta_c >= 2 * se_c:
        return "CEILING-LIMITED" if ceiling_fired else "C-POS"
    if delta_c <= -2 * se_c:
        return "C-NEG"
    return "CEILING-LIMITED" if ceiling_fired else "C-UNRES"


def exclusion_flag(delta_c: float, se_c: float, delta_sh: float) -> tuple[float, bool]:
    """pre-reg EXCLUSION FLAG: U = delta_C + 1.96*se_C; fired iff
    U < delta_hat_SH — the upper end of the two-sided 95% CI, the R2
    falsifier's construction, which called it '~95%'."""
    u = delta_c + Z_ONE_SIDED_975 * se_c
    return u, bool(u < delta_sh)


def f_cell(delta_f: float, threshold: float = FP_PINNED_THRESHOLD) -> str:
    """pre-reg FP BLOCK partition (covers R) at the PINNED LITERAL."""
    if delta_f <= -threshold:
        return "F-NEG"
    if delta_f >= threshold:
        return "F-POS"
    return "F-UNRES"


def composite(cell_c: str, cell_f: str, exclusion_fired: bool,
              ceiling_fired: bool) -> str:
    """pre-reg COMPOSITE TRANSFER MAP, by pre-stated precedence. TOTAL over
    all cell combinations; selects a README sentence, never a verdict."""
    if cell_c == "C-NEG" or cell_f == "F-NEG":
        return "TRANSFER-NEGATIVE-RESOLVED"
    if exclusion_fired and not ceiling_fired:
        return "COMMENSURATE-TRANSFER-EXCLUDED"
    if cell_c == "C-POS":
        return "TRANSFER-POSITIVE"
    return "TRANSFER-UNRESOLVED"


def era_tripwire(wr_ca: float, anchor: float, tolerance: float) -> tuple[bool, str]:
    """pre-reg CA: the era tripwire vs 0.894 +/- 0.04. Outside -> the clone
    block is LABELLED, not voided."""
    ok = abs(wr_ca - anchor) <= tolerance
    return ok, "GREEN" if ok else "DESCRIPTIVE-WITH-DRIFT-NOTE"


# --------------------------------------------------------------------------
# named-file reads (READING CONVENTION: named files only, never glob output)
# --------------------------------------------------------------------------


def read_clone_arm(path: Path, expect_search: bool) -> dict:
    rep = json.loads(Path(path).read_text())
    assert rep["eval/win_rate"] == rep["wins_from_returns"], (
        f"F8 FAIL (reward-sign guard): {Path(path).name}"
    )
    out = {
        "file": str(path),
        "arm": rep["arm"],
        "win_rate": rep["eval/win_rate"],
        "episodes": rep["episodes"],
        "chunks": rep.get("chunks"),
        "mask_desyncs": rep.get("mask_desyncs"),
        "ties_from_returns": rep.get("ties_from_returns"),
    }
    if expect_search:
        leaves = rep.get("search/leaves_mean")
        assert leaves is not None, f"{Path(path).name}: no search/leaves_mean"
        out["search/leaves_mean"] = leaves
        out["search/ms_mean"] = rep.get("search/ms_mean")
        out["search/placeholder_skip_rate"] = rep.get("search/placeholder_skip_rate")
        out["search/timeouts"] = rep.get("search/timeouts", 0)
        out["f_c_leaves_ok"] = bool(
            abs(leaves - LEAVES_EXPECTED) / LEAVES_EXPECTED <= LEAVES_BAND
        )
        out["evaluator"] = rep.get("evaluator")
    return out


def read_fp_arm(path: Path, runner_path: Path | None) -> dict:
    """FE3 + the crash-forfeit correction. n_eff = seat-finished minus
    crash-forfeits, our_wins reduced by the same count (2026-08-23 read rule,
    verbatim in the pre-reg); >= 30 relaunches VOIDs the arm."""
    rep = json.loads(Path(path).read_text())
    runner = {}
    if runner_path is not None and Path(runner_path).exists():
        runner = json.loads(Path(runner_path).read_text())
    forfeits = int(runner.get("crash_forfeits", 0))
    relaunches = int(runner.get("relaunches", 0))
    finished = int(rep["battles_finished"])
    n_eff = finished - forfeits
    wins_eff = int(rep["our_wins"]) - forfeits
    assert n_eff > 0, f"FE3: n_eff {n_eff} after {forfeits} crash-forfeits"
    leaves = rep.get("search/leaves_mean")
    return {
        "file": str(path),
        "runner_file": str(runner_path) if runner else None,
        "battles_finished": finished,
        "our_wins": int(rep["our_wins"]),
        "relaunches": relaunches,
        "crash_forfeits": forfeits,
        "n_eff": n_eff,
        "our_wins_eff": wins_eff,
        "win_rate_n_eff": wins_eff / n_eff,
        "ties": rep.get("ties"),
        "mask_desyncs": rep.get("mask_desyncs"),
        "gate_all_challenges_resolved": rep.get("gate_all_challenges_resolved"),
        "evaluator": rep.get("evaluator"),
        "search/leaves_mean": leaves,
        "search/ms_mean": rep.get("search/ms_mean"),
        "search/timeouts": rep.get("search/timeouts", 0),
        "f_c_leaves_ok": (
            None if leaves is None
            else bool(abs(leaves - LEAVES_EXPECTED) / LEAVES_EXPECTED <= LEAVES_BAND)
        ),
        "VOID_too_many_crashes": bool(
            runner.get("void_too_many_crashes", False) or relaunches >= MAX_RELAUNCHES
        ),
    }


# --------------------------------------------------------------------------
# the battery
# --------------------------------------------------------------------------


def grade_battery(ca: dict, ce0: dict, ce3: dict, fp: dict,
                  delta_sh: float, prereg: dict) -> dict:
    ca_arm = prereg["anchor_arms"]["CA"]
    era_ok, era_label = era_tripwire(
        ca["win_rate"], float(ca_arm["anchor"]), float(ca_arm["tolerance"])
    )

    p0, p3 = ce0["win_rate"], ce3["win_rate"]
    delta_c = p3 - p0
    se_c = se_diff(p3, ce3["episodes"], p0, ce0["episodes"])
    ceiling_fired = p0 >= CEILING
    cell_c = c_cell(delta_c, se_c, ceiling_fired)
    u, excl_fired = exclusion_flag(delta_c, se_c, delta_sh)

    delta_f = fp["win_rate_n_eff"] - FP_FROZEN_COMPARATOR
    cell_f = f_cell(delta_f)
    if fp["VOID_too_many_crashes"]:
        cell_f = "F-VOID"

    cell = composite(cell_c, cell_f, excl_fired, ceiling_fired)

    notes = []
    if not era_ok:
        notes.append(
            f"CA era tripwire OUTSIDE {ca_arm['anchor']} +/- {ca_arm['tolerance']} "
            f"(read {ca['win_rate']:.4f}): the clone block is "
            "DESCRIPTIVE-WITH-DRIFT-NOTE"
        )
    if ceiling_fired:
        notes.append(
            f"CEILING GUARD FIRED (CE0 {p0:.4f} >= {CEILING}): C-POS/C-UNRES "
            "replaced by CEILING-LIMITED and THE EXCLUSION FLAG IS DEMOTED TO "
            "A DESCRIPTIVE NUMBER — it cannot select the composite cell"
        )
    if excl_fired and ceiling_fired:
        notes.append(
            f"exclusion flag would have fired (U {u:+.4f} < delta_hat_SH "
            f"{delta_sh:+.4f}) but is DEMOTED by the ceiling guard"
        )
    if cell_c == "C-UNRES":
        notes.append(
            "C-UNRES: unresolved at n (pre-stated MDE "
            f"{prereg['anchor_mde']['clone_1000']}); sign recorded, never read"
        )
    if cell_f == "F-UNRES":
        notes.append(
            f"F-UNRES: unresolved at n={fp['n_eff']}, as pre-stated; sign "
            "recorded, never read"
        )
    if cell_f == "F-POS":
        notes.append(
            "F-POS on a cell NOT REACHABLE by an effect of the pre-registered "
            "size — surprising; straight to the maintainer"
        )
    if cell_c == "C-NEG":
        notes.append("C-NEG: MANDATORY README caveat")
    if fp["crash_forfeits"]:
        notes.append(
            f"FP crash-forfeit rule applied: {fp['crash_forfeits']} forfeits "
            f"EXCLUDED, n_eff {fp['n_eff']}, wins {fp['our_wins']} -> "
            f"{fp['our_wins_eff']}; relaunches {fp['relaunches']} "
            "(disclose beside the number; G2 owed on n_eff EXACTLY)"
        )

    f_twins: dict[str, str] = {}
    for name, arm in (("CE0", ce0), ("CE3", ce3)):
        if not arm.get("f_c_leaves_ok", True):
            f_twins[f"F-C/{name}"] = (
                f"leaves_mean {arm['search/leaves_mean']} vs {LEAVES_EXPECTED} "
                f"(band {LEAVES_BAND:.0%})"
            )
        if arm.get("search/timeouts", 0) != 0:
            f_twins[f"F-C-timeouts/{name}"] = str(arm["search/timeouts"])
        expected_chunks = prereg["anchor_arms"][name].get("chunks")
        if expected_chunks is not None and arm.get("chunks") != expected_chunks:
            f_twins[f"F-C-chunks/{name}"] = (
                f"{arm.get('chunks')} chunks merged, pre-reg says {expected_chunks} "
                "(a node_cap watchdog raise leaves a HOLE — that is how a "
                "timeout shows up)"
            )
    if fp.get("f_c_leaves_ok") is False:
        f_twins["F-C/FE3"] = (
            f"leaves_mean {fp['search/leaves_mean']} vs {LEAVES_EXPECTED}"
        )
    if fp.get("gate_all_challenges_resolved") is False:
        f_twins["G3/FE3"] = "not every challenge resolved"
    if ce3.get("evaluator") is None:
        f_twins["F5/CE3"] = "no evaluator provenance in the CE3 final"
    if ce0.get("evaluator") is not None:
        f_twins["F5/CE0"] = "CE0 carries an evaluator — it is the E0 comparator"

    return {
        "battery": "CH3 R4 ANCHOR BATTERY (descriptive; anchors_are_verdict_inputs false)",
        "anchor_lane": prereg["anchor_lane"],
        "CA": {**ca, "era_anchor": ca_arm["anchor"], "era_tolerance": ca_arm["tolerance"],
               "era_ok": era_ok, "era_label": era_label},
        "CE0": ce0,
        "CE3": ce3,
        "FE3": fp,
        "delta_C": delta_c,
        "se_C": se_c,
        "two_se_C": 2 * se_c,
        "ceiling_guard_fired": ceiling_fired,
        "C_cell": cell_c,
        "delta_hat_SH": delta_sh,
        "exclusion_U": u,
        "exclusion_flag_fired": excl_fired,
        "exclusion_flag_status": (
            "DEMOTED-DESCRIPTIVE (ceiling)" if ceiling_fired
            else ("EXCLUDED at 97.5% one-sided" if excl_fired else "not excluded")
        ),
        "delta_F": delta_f,
        "fp_frozen_comparator": FP_FROZEN_COMPARATOR,
        "fp_pinned_threshold": FP_PINNED_THRESHOLD,
        "F_cell": cell_f,
        "composite_transfer_cell": cell,
        "composite_precedence": COMPOSITE_PRECEDENCE,
        "f_gate_twins_fired": f_twins,
        "notes": notes,
    }


def _assert_prereg_pins(prereg: dict, prereg_path: str) -> None:
    # An OPEN bracket, not the BI-3 build item's own quoted description of the
    # rule ('any "[MAINTAINER RULING" bracket'): the quoted form is excluded by
    # the lookbehind, so this refusal cannot be tripped by the pre-reg
    # describing itself.
    raw = Path(prereg_path).read_text()
    assert not re.search(r'(?<!")\[MAINTAINER RULING', raw), (
        "an unruled [MAINTAINER RULING bracket remains in the pre-reg — rule "
        "it before grading"
    )
    assert "DRAFT" not in str(prereg.get("status", "")), "pre-reg status is DRAFT"
    assert prereg["anchors_are_verdict_inputs"] is False, (
        "anchors_are_verdict_inputs is not false — this grader is descriptive only"
    )
    assert prereg["composite_transfer_precedence"] == COMPOSITE_PRECEDENCE, (
        "pre-reg composite_transfer_precedence is not byte-equal to the module "
        f"constant: {prereg['composite_transfer_precedence']}"
    )
    assert prereg["anchor_mde"]["fp_250_pinned_literal"] == FP_PINNED_THRESHOLD, (
        "the FP threshold is PINNED as a literal and the pre-reg disagrees"
    )
    assert prereg["prior_anchors"]["fp_s65_at_100ms"]["search_e0"] == FP_FROZEN_COMPARATOR, (
        "the frozen FP comparator disagrees with the pre-reg's recorded 0.368"
    )
    assert str(prereg["anchor_arms"]["FE3"]["comparator"]) == "frozen_0.368"
    assert prereg["anchor_arms"]["CE0"].get("evaluator") is None, (
        "CE0 must carry NO evaluator key — it is the bit-identical E0 path"
    )
    assert prereg["anchor_arms"]["CE3"]["evaluator"]["kind"] == "loo"


def grade(prereg_path: str, anchor_dir: str, fp_json: str, runner_json: str,
          delta_sh: float) -> dict:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    _assert_prereg_pins(prereg, prereg_path)
    dirty = _git(["status", "--porcelain"])
    assert not dirty, f"tree is dirty; commit before grading:\n{dirty}"
    assert not _git(["status", "--porcelain", "--", prereg_path]), "pre-reg uncommitted"

    adir = Path(anchor_dir)
    ca = read_clone_arm(adir / "ca.final.json", expect_search=False)
    ce0 = read_clone_arm(adir / "ce0.final.json", expect_search=True)
    ce3 = read_clone_arm(adir / "ce3.final.json", expect_search=True)
    fp = read_fp_arm(Path(fp_json), Path(runner_json))

    out = grade_battery(ca, ce0, ce3, fp, delta_sh, prereg)
    out["prereg"] = prereg_path
    out["prereg_sha256"] = hashlib.sha256(Path(prereg_path).read_bytes()).hexdigest()
    out["git_sha"] = _git(["rev-parse", "HEAD"])
    print(json.dumps(out, indent=2))
    print(
        f"\nCLONE  CA {ca['win_rate']:.4f} [{out['CA']['era_label']}] | "
        f"CE0 {ce0['win_rate']:.4f} | CE3 {ce3['win_rate']:.4f} | "
        f"delta_C {out['delta_C']:+.4f} vs 2*se_C {out['two_se_C']:.4f} -> "
        f"{out['C_cell']}"
    )
    print(
        f"FP     FE3 {fp['win_rate_n_eff']:.4f} on n_eff {fp['n_eff']} vs frozen "
        f"{FP_FROZEN_COMPARATOR} | delta_F {out['delta_F']:+.4f} vs pinned "
        f"{FP_PINNED_THRESHOLD} -> {out['F_cell']}"
    )
    print(
        f"FLAG   U {out['exclusion_U']:+.4f} vs delta_hat_SH {delta_sh:+.4f} -> "
        f"{out['exclusion_flag_status']}"
    )
    print(f"COMPOSITE TRANSFER CELL: {out['composite_transfer_cell']}")
    for note in out["notes"]:
        print(f"  - {note}")
    if out["f_gate_twins_fired"]:
        print(f"F-GATE TWINS FIRED: {out['f_gate_twins_fired']}")
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "r4_anchor_readout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


# --------------------------------------------------------------------------
# --selftest: synthetic JSONs, no network, no battles
# --------------------------------------------------------------------------


def _clone_json(path: Path, arm: str, wr: float, n: int, search: bool,
                leaves: float = 353.0, chunks: int | None = None,
                evaluator: dict | None = None) -> None:
    rep = {
        "arm": arm, "kind": "search_h2h" if search else "greedy_h2h",
        "seat1": "s65", "seat2": "clone", "episodes": n,
        "chunks": chunks, "eval/win_rate": wr, "wins_from_returns": wr,
        "ties_from_returns": 0.0, "mask_desyncs": 0,
    }
    if search:
        rep.update({"search/leaves_mean": leaves, "search/ms_mean": 73.2,
                    "search/placeholder_skip_rate": 0.108, "search/timeouts": 0})
        if evaluator:
            rep["evaluator"] = evaluator
    path.write_text(json.dumps(rep, indent=2) + "\n")


def _fp_json(path: Path, wins: int, finished: int, leaves: float = 353.0) -> None:
    path.write_text(json.dumps({
        "tag": "fe3", "arm": "FE3", "battles_requested": finished,
        "battles_finished": finished, "our_wins": wins,
        "foulplay_wins": finished - wins, "ties": 0,
        "our_win_rate": wins / finished, "mask_desyncs": 0,
        "gate_all_challenges_resolved": True,
        "search/leaves_mean": leaves, "search/ms_mean": 73.2,
        "evaluator": {"kind": "loo", "members": ["s62", "s63", "s64"]},
    }, indent=2) + "\n")


def _runner_json(path: Path, relaunches: int, void: bool = False) -> None:
    path.write_text(json.dumps({
        "relaunches": relaunches, "crash_forfeits": relaunches,
        "void_too_many_crashes": void,
    }, indent=2) + "\n")


def selftest(prereg_path: str) -> None:
    prereg = yaml.safe_load(Path(prereg_path).read_text())
    _assert_prereg_pins(prereg, prereg_path)
    loo = {"kind": "loo", "members": ["s62", "s63", "s64"],
           "member_sha256": ["a", "b", "c"]}

    # ---- se_C arithmetic + the pre-stated clone_1000 MDE ----
    se = se_diff(0.86, 1000, 0.86, 1000)
    assert abs(2 * se - prereg["anchor_mde"]["clone_1000"]) < 0.002, (
        f"2*se_C at the frozen 0.860 level is {2 * se:.4f}, pre-reg says "
        f"{prereg['anchor_mde']['clone_1000']}"
    )
    se500 = se_diff(0.894, 500, 0.894, 500)
    assert abs(2 * se500 - prereg["anchor_mde"]["clone_500"]) < 0.006

    # ---- C cells, no ceiling ----
    se_c = se_diff(0.92, 1000, 0.86, 1000)
    assert c_cell(+0.060, se_c, False) == "C-POS"
    assert c_cell(+0.005, se_c, False) == "C-UNRES"
    assert c_cell(-0.005, se_c, False) == "C-UNRES"
    assert c_cell(-0.060, se_c, False) == "C-NEG"
    # boundaries: >= and <= are inclusive on the resolved cells
    assert c_cell(+2 * se_c, se_c, False) == "C-POS"
    assert c_cell(-2 * se_c, se_c, False) == "C-NEG"
    assert c_cell(2 * se_c - 1e-9, se_c, False) == "C-UNRES"

    # ---- ceiling guard: C-POS and C-UNRES replaced, C-NEG survives ----
    assert c_cell(+0.060, se_c, True) == "CEILING-LIMITED"
    assert c_cell(+0.005, se_c, True) == "CEILING-LIMITED"
    assert c_cell(-0.060, se_c, True) == "C-NEG"

    # ---- exclusion flag ----
    u, fired = exclusion_flag(0.005, 0.0155, 0.050)
    assert fired and abs(u - (0.005 + 1.96 * 0.0155)) < 1e-12
    _, not_fired = exclusion_flag(0.005, 0.0155, 0.020)
    assert not not_fired

    # ---- F cells at the PINNED literal ----
    assert f_cell(-0.090) == "F-NEG"
    assert f_cell(-FP_PINNED_THRESHOLD) == "F-NEG"
    assert f_cell(0.000) == "F-UNRES"
    assert f_cell(+0.086) == "F-UNRES"
    assert f_cell(+FP_PINNED_THRESHOLD) == "F-POS"

    # ---- composite precedence, all four rules + the ceiling gate ----
    assert composite("C-NEG", "F-UNRES", True, False) == "TRANSFER-NEGATIVE-RESOLVED"
    assert composite("C-UNRES", "F-NEG", True, False) == "TRANSFER-NEGATIVE-RESOLVED"
    assert composite("C-POS", "F-NEG", False, False) == "TRANSFER-NEGATIVE-RESOLVED"
    assert composite("C-UNRES", "F-UNRES", True, False) == "COMMENSURATE-TRANSFER-EXCLUDED"
    # precedence 2 beats 3: a C-POS whose whole CI still sits below delta_hat_SH
    assert composite("C-POS", "F-UNRES", True, False) == "COMMENSURATE-TRANSFER-EXCLUDED"
    assert composite("C-POS", "F-UNRES", False, False) == "TRANSFER-POSITIVE"
    assert composite("C-POS", "F-POS", False, False) == "TRANSFER-POSITIVE"
    assert composite("C-UNRES", "F-UNRES", False, False) == "TRANSFER-UNRESOLVED"
    # ceiling gates precedence 2 off; CEILING-LIMITED is never C-POS
    assert composite("CEILING-LIMITED", "F-UNRES", True, True) == "TRANSFER-UNRESOLVED"
    assert composite("CEILING-LIMITED", "F-NEG", True, True) == "TRANSFER-NEGATIVE-RESOLVED"

    # ---- era tripwire label ----
    assert era_tripwire(0.894, 0.894, 0.04)[1] == "GREEN"
    assert era_tripwire(0.930, 0.894, 0.04)[1] == "GREEN"
    assert era_tripwire(0.860, 0.894, 0.04)[1] == "GREEN"
    assert era_tripwire(0.800, 0.894, 0.04)[1] == "DESCRIPTIVE-WITH-DRIFT-NOTE"

    # ---- end-to-end over synthetic files, every branch ----
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _clone_json(d / "ca.final.json", "CA", 0.894, 500, False, chunks=5)
        fp_path, runner_path = d / "fe3.json", d / "fe3.runner.json"

        def battery(p0, p3, fp_wins, relaunches=0, ca_wr=0.894, void=False,
                    delta_sh=0.031, leaves=353.0):
            _clone_json(d / "ca.final.json", "CA", ca_wr, 500, False, chunks=5)
            _clone_json(d / "ce0.final.json", "CE0", p0, 1000, True,
                        chunks=10, leaves=leaves)
            _clone_json(d / "ce3.final.json", "CE3", p3, 1000, True,
                        chunks=10, evaluator=loo, leaves=leaves)
            _fp_json(fp_path, fp_wins, 250)
            _runner_json(runner_path, relaunches, void)
            return grade_battery(
                read_clone_arm(d / "ca.final.json", False),
                read_clone_arm(d / "ce0.final.json", True),
                read_clone_arm(d / "ce3.final.json", True),
                read_fp_arm(fp_path, runner_path),
                delta_sh, prereg,
            )

        # C-POS, F-UNRES, flag not fired -> TRANSFER-POSITIVE
        r = battery(0.860, 0.920, 92, delta_sh=0.031)
        assert (r["C_cell"], r["F_cell"]) == ("C-POS", "F-UNRES"), r
        assert not r["exclusion_flag_fired"]
        assert r["composite_transfer_cell"] == "TRANSFER-POSITIVE"
        assert r["CA"]["era_label"] == "GREEN"
        assert not r["f_gate_twins_fired"], r["f_gate_twins_fired"]

        # C-UNRES + flag fired -> COMMENSURATE-TRANSFER-EXCLUDED
        r = battery(0.860, 0.865, 92, delta_sh=0.060)
        assert r["C_cell"] == "C-UNRES" and r["exclusion_flag_fired"]
        assert r["composite_transfer_cell"] == "COMMENSURATE-TRANSFER-EXCLUDED"

        # C-NEG beats the fired flag (precedence 1)
        r = battery(0.860, 0.790, 92, delta_sh=0.060)
        assert r["C_cell"] == "C-NEG" and r["exclusion_flag_fired"]
        assert r["composite_transfer_cell"] == "TRANSFER-NEGATIVE-RESOLVED"

        # F-NEG alone resolves the composite
        r = battery(0.860, 0.865, 69, delta_sh=0.005)   # 0.276 -> delta_F -0.092
        assert r["F_cell"] == "F-NEG" and not r["exclusion_flag_fired"]
        assert r["composite_transfer_cell"] == "TRANSFER-NEGATIVE-RESOLVED"

        # F-POS (surprising, retained as a named cell)
        r = battery(0.860, 0.865, 115, delta_sh=0.005)  # 0.460 -> delta_F +0.092
        assert r["F_cell"] == "F-POS"
        assert any("F-POS" in n for n in r["notes"])

        # ceiling guard: fires, demotes the flag, composite falls through to 4
        r = battery(0.910, 0.960, 92, delta_sh=0.200)
        assert r["ceiling_guard_fired"] and r["C_cell"] == "CEILING-LIMITED"
        assert r["exclusion_flag_fired"]
        assert r["exclusion_flag_status"].startswith("DEMOTED")
        assert r["composite_transfer_cell"] == "TRANSFER-UNRESOLVED"
        assert any("DEMOTED" in n for n in r["notes"])
        # and C-NEG still fires under the ceiling
        r = battery(0.910, 0.840, 92, delta_sh=0.200)
        assert r["C_cell"] == "C-NEG"
        assert r["composite_transfer_cell"] == "TRANSFER-NEGATIVE-RESOLVED"

        # drift note on the era tripwire
        r = battery(0.860, 0.865, 92, ca_wr=0.800)
        assert r["CA"]["era_label"] == "DESCRIPTIVE-WITH-DRIFT-NOTE"
        assert any("DRIFT" in n for n in r["notes"])

        # crash-forfeit arithmetic: 3 forfeits -> n_eff 247, wins 95 -> 92
        r = battery(0.860, 0.865, 95, relaunches=3)
        assert r["FE3"]["n_eff"] == 247 and r["FE3"]["our_wins_eff"] == 92
        assert abs(r["FE3"]["win_rate_n_eff"] - 92 / 247) < 1e-12
        assert any("crash-forfeit" in n for n in r["notes"])

        # >= 30 relaunches VOIDs the FP arm
        r = battery(0.860, 0.865, 95, relaunches=30, void=True)
        assert r["F_cell"] == "F-VOID"
        assert r["composite_transfer_cell"] != "TRANSFER-NEGATIVE-RESOLVED"

        # F-C twin fires on out-of-band leaves
        r = battery(0.860, 0.865, 92, leaves=100.0)
        assert "F-C/CE0" in r["f_gate_twins_fired"]
        assert "F-C/CE3" in r["f_gate_twins_fired"]

        # F8 twin: a reward-sign mismatch is a hard read failure
        bad = d / "bad.final.json"
        bad.write_text(json.dumps({
            "arm": "CE0", "episodes": 1000, "eval/win_rate": 0.86,
            "wins_from_returns": 0.14,
        }))
        try:
            read_clone_arm(bad, expect_search=True)
        except AssertionError as exc:
            assert "F8 FAIL" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("F8 twin did not fire")

    print("ch3_r4_anchor_grade selftest: ALL GREEN")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prereg", default="configs/eval/ch3_r4_ensemble_critic.yaml")
    ap.add_argument("--anchor-dir", default=ANCHOR_DIR)
    ap.add_argument("--fp-json", default=f"{FP_DIR}/fe3.json")
    ap.add_argument("--runner-json", default=f"{FP_DIR}/fe3.runner.json")
    ap.add_argument("--delta-sh", type=float,
                    help="delta_hat_SH: the OBSERVED pooled primary delta, "
                         "whatever cell the primary landed in (pre-reg "
                         "EXCLUSION FLAG; review 1 blocker 4)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest(args.prereg)
        return
    if args.delta_sh is None:
        sys.exit("--delta-sh is required: the exclusion flag reads against the "
                 "OBSERVED pooled primary delta")
    grade(args.prereg, args.anchor_dir, args.fp_json, args.runner_json,
          args.delta_sh)


if __name__ == "__main__":
    main()

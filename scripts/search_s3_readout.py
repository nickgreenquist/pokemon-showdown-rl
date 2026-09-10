#!/usr/bin/env python
"""Grader/readout for the SEARCH RELOOK screen S3 (JOURNEY 11.5).

    python scripts/search_s3_readout.py
    python scripts/search_s3_readout.py --dir results/search_s3_100m \
        --offfp-dir results/search_s3_100m_offfp --json results/.../readout.json \
        --md docs/search_relook/S3_READOUT.md

Every cell, aggregator and disclosure below TRANSCRIBES a pre-registration
written before the arms ran; nothing here is chosen after the numbers:

  * `configs/eval/search_s3_100m.yaml`  — header + `arms` (P-M, P-B, P-BA,
    P-E, P-L; the credit line; the equal-weight-mean aggregator; the
    "one rung is worth +-0.02" caveat; the FRESH-A0 era note).
  * `configs/eval/search_s3_100m_offfp.yaml` — the off-Foul-Play anchor
    (F3M112, F3B112) and its banked greedy comparator.
  * `docs/search_relook/DET_BLIND.md` §6 — P-B's read, verbatim, including
    the secondary reads (delta_BA, decision agreement, leaves equality).

TWO RULES THIS SCRIPT ENFORCES RATHER THAN DOCUMENTS.

1. NO CELL ON PARTIAL DATA. A read fires only when EVERY arm it names has a
   `<job>.final.json` on disk for EVERY registered lane. Anything short of
   that prints PENDING with chunks-done/10 and the running pooled rate over
   completed chunks, labelled PARTIAL. A partial rate is never a comparator
   and never a cell — the R2/R4 rule that a partial arm is VOID, not scaled.

2. THE LARGER-OF se_diff, both terms printed. se_diff is the LARGER of the
   pooled two-sample binomial se_diff (over the pooled n-vs-n rates) and the
   seed-clustered se_diff (sd of the per-lane PAIRED deltas / sqrt(k)); the
   output names which one governs, on every read, every time.

S3 CREDITS NOTHING. The cells route the relook; they do not land a README row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREREG_VSSH = REPO / "configs/eval/search_s3_100m.yaml"
PREREG_OFFFP = REPO / "configs/eval/search_s3_100m_offfp.yaml"
DET_BLIND_DOC = REPO / "docs/search_relook/DET_BLIND.md"

FLOOR = 0.025            # the credit floor, from CLAUDE.md's credit line
CHUNKS = 10              # every S3 arm is 3000 battles in 10 chunks
LANES = ("s104", "s112", "s120")
ONE_RUNG_SPREAD = 0.02   # three n=3000 redraws of ONE checkpoint spread 0.0200
# Any real delta between two n=3000 win rates is a multiple of 1/3000 ~ 3.3e-4
# in exact arithmetic, so a 1e-9 slack cannot change a real answer — it only
# stops binary float dust (0.720 - 0.700 = 0.020000000000000018) from turning
# an inclusive boundary exclusive.
EPS = 1e-9

# --- restated verbatim; the output header carries them character for character
CREDIT_LINE = (
    "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where "
    "se_diff is the LARGER of the pooled-binomial se_diff and the "
    "seed-clustered se_diff, the latter computed from the per-seed finals at "
    "read time"
)
CREDITS_NOTHING = (
    "S3 CREDITS NOTHING: descriptive screen; the cells route the relook."
)
FP20_DISCLOSURES = (
    "the equivalence test is weakly powered",
    "the point estimate flatters us",
)
ONE_RUNG = (
    "ONE RUNG IS WORTH +-0.02 (three n=3000 redraws of ONE checkpoint spread "
    "0.0200) — read the SHAPE across the three lanes, never one cell against "
    "its neighbour."
)
TIMING_NOTE = (
    "CONTENDED: 7-10 concurrent eval processes (torch_threads 1 each) shared "
    "the box while these arms ran. search/ms_mean and leaves are DESCRIPTIVE "
    "AND CONTENDED — they are NOT a budget number and NOT the clean "
    "decisions/sec that JOURNEY 11.5's exit condition asks for."
)
ERA_NOTE = (
    "A0 is FRESH this session and is the ONLY comparator. The banked "
    "results/ch5_100m/final_s1xx.json (pooled 0.79589) are printed for "
    "CONTEXT ONLY — R3 measured a same-checkpoint era_diff of 0.0148 between "
    "a banked A0 and a fresh one, which is why the pre-reg forbids them as "
    "the comparator."
)
DOSE_CONFOUND = (
    "Dose is NOT matched between A0 and any search arm — the generic-compute "
    "confound survives, as in R2, and is disclosed rather than controlled. It "
    "IS matched between S3B and S3M (identical dose M, identical leaf caps), "
    "which is why P-B is the primary read of the det_blind screen."
)
BANKED_VSSH_POOLED = 0.79589
BANKED_OFFFP_T112 = {"rate": 0.50167, "n": 3000,
                     "source": "results/ch5_100m/t112.json"}

# Registered arm -> (lanes, what it is). Transcribed from the pre-reg `arms`.
ARMS = {
    "A0":  {"lanes": LANES, "kind": "policy", "dose": None,
            "leaf_encoding": None,
            "what": "greedy, FRESH this session — the comparator"},
    "S3M": {"lanes": LANES, "kind": "search", "dose": "M",
            "leaf_encoding": "as_is",
            "what": "depth-1 search, dose M (n_det 4, top_branches 6, "
                    "leaf_cap 1296), as-is leaf encoding"},
    "S3B": {"lanes": LANES, "kind": "search", "dose": "M",
            "leaf_encoding": "det_blind",
            "what": "S3M with leaf_encoding: det_blind (DET_BLIND.md)"},
    "S3L": {"lanes": ("s112",), "kind": "search", "dose": "L",
            "leaf_encoding": "as_is",
            "what": "dose L (n_det 16, leaf_cap 5184), s112 ONLY"},
    "A1E": {"lanes": LANES, "kind": "search", "dose": "M",
            "leaf_encoding": "as_is",
            "what": "dose M with the leave-one-out CRITIC ENSEMBLE as the "
                    "leaf evaluator (R4's E3 form)"},
}

# The pre-stated reads. (name, treatment, comparator, lanes, primary?, prose).
READS = (
    ("P-M", "S3M", "A0", LANES, True,
     "does depth-1 search@M pay on the 100M object at the locked protocol? "
     "NEG or FLAT -> the vacated depreciation ruling's PREMISE survives on "
     "the verdict axis and the relook's burden is the leaf evaluator + depth. "
     "POS -> the existing form is a live ladder-object candidate."),
    ("P-B", "S3B", "S3M", LANES, True,
     "does removing the leaf-encoding artefact (det_blind) move the win "
     "rate? Dose MATCHED. Expected direction: det_blind >= as-is. A FLAT or "
     "NEG delta_B says the artefact was NOT the binding defect and the "
     "EVALUATOR is."),
    ("P-BA", "S3B", "A0", LANES, False,
     "SECONDARY: does searching at all beat greedy once the artefact is "
     "gone? (The question S1 was actually raised against.)"),
    ("P-E", "A1E", "S3M", LANES, True,
     "does a better leaf EVALUATOR pay on the 100M object? POS -> the "
     "monster train's evaluator lever (IDEAS 8.2 / 4.7) moves to the top of "
     "its config decisions. NEG/FLAT -> the ensemble form does not move the "
     "100M object; 8.2 stays untested (different mechanism)."),
)
PL_READ = ("P-L", "S3L", "S3M", "s112",
           "SECONDARY, ONE LANE, SIGN ONLY, NO CELL: the sign of the n_det "
           "axis on the strongest object, against the +-0.02 one-lane redraw "
           "spread.")

# leaves_mean equality (DET_BLIND.md §6) is a DIAGNOSTIC, never a cell. Exact
# equality is only expected at MATCHED decisions (the offline §4 check); once
# a decision flips the two arms play different battles, so the live check is a
# tolerance on the relative difference, named here before it is read.
LEAVES_TOL_REL = 0.05


# ---------------------------------------------------------------------------
# cells and se terms
# ---------------------------------------------------------------------------
def se_terms(rate_t: float, n_t: int, rate_c: float, n_c: int,
             per_lane_deltas: list[float]) -> dict:
    """The larger-of clause, both terms kept.

    binomial: sqrt(p1(1-p1)/n1 + p2(1-p2)/n2) on the POOLED rates (9000 vs
    9000 at the registered widths). clustered: sd of the per-lane PAIRED
    deltas / sqrt(k) — undefined at k < 2, in which case the binomial term
    governs by default and the read says so.
    """
    se_bin = math.sqrt(rate_t * (1 - rate_t) / n_t + rate_c * (1 - rate_c) / n_c)
    k = len(per_lane_deltas)
    se_clus = statistics.stdev(per_lane_deltas) / math.sqrt(k) if k >= 2 else None
    if se_clus is None:
        return {"se_binomial": se_bin, "se_clustered": None,
                "se_diff": se_bin, "governing": "binomial",
                "governing_note": "k < 2: the seed-clustered term is "
                                  "undefined; no cell may be read here"}
    se_gov = max(se_bin, se_clus)
    return {"se_binomial": se_bin, "se_clustered": se_clus,
            "se_diff": se_gov,
            "governing": "clustered" if se_clus >= se_bin else "binomial",
            "governing_note": None}


def cell(pooled_delta: float, per_lane_deltas: list[float],
         se_diff: float) -> tuple[str, str]:
    """The three registered cells, verbatim:

      NEG  iff pooled <= 0 AND per-lane <= 0 in >= 2 of 3
      POS  iff pooled >= +0.025 AND >= 2*se_diff  (larger-of se_diff)
      FLAT otherwise

    POS and NEG are disjoint by construction (POS needs pooled >= +0.025,
    NEG needs pooled <= 0); the assert below keeps them that way.

    NO EPSILON is applied to a pre-registered threshold — the comparison is
    the one the header wrote. A pooled delta landing within float dust of a
    threshold is flagged `boundary_fragile` by the caller instead, so a
    knife-edge is visible rather than silently decided in binary.
    """
    k = len(per_lane_deltas)
    if k != 3:
        raise ValueError("the registered cells are defined on the 3-lane "
                         f"set; got k={k}. One lane is sign-only (P-L).")
    n_nonpos = sum(1 for d in per_lane_deltas if d <= 0)
    is_neg = pooled_delta <= 0 and n_nonpos >= 2
    is_pos = pooled_delta >= FLOOR and pooled_delta >= 2 * se_diff
    assert not (is_neg and is_pos), "POS and NEG cells overlapped"
    if is_neg:
        return "NEG", (f"pooled {pooled_delta:+.4f} <= 0 and {n_nonpos}/3 "
                       "lanes non-positive")
    if is_pos:
        return "POS", (f"pooled {pooled_delta:+.4f} >= +{FLOOR} and >= "
                       f"2*se_diff = {2 * se_diff:.4f}")
    why = []
    if pooled_delta > 0:
        if pooled_delta < FLOOR:
            why.append(f"pooled {pooled_delta:+.4f} below the +{FLOOR} floor")
        if pooled_delta < 2 * se_diff:
            why.append(f"pooled {pooled_delta:+.4f} below 2*se_diff = "
                       f"{2 * se_diff:.4f}")
    else:
        why.append(f"pooled {pooled_delta:+.4f} <= 0 but only {n_nonpos}/3 "
                   "lanes non-positive")
    return "FLAT", "; ".join(why)


# ---------------------------------------------------------------------------
# reading the arms off disk
# ---------------------------------------------------------------------------
def _weighted(reports: list[dict], key: str, weight: str) -> float | None:
    """Mean of `key` weighted by `weight` — the same merge ch3_eval._merge
    does, so a PARTIAL number is computed exactly as its final would be."""
    tot = sum(r.get(weight, 0) or 0 for r in reports)
    if not tot or any(r.get(key) is None for r in reports):
        return None
    return sum(r[key] * r[weight] for r in reports) / tot


def _search_block(reports: list[dict]) -> dict | None:
    """Search counters, merged from finals or from completed chunks alike."""
    if not reports or "search/decisions" not in reports[0]:
        return None
    dec = sum(r["search/decisions"] for r in reports)
    skips = sum(r["search/placeholder_skips"] for r in reports)
    flips = sum(r["search/flips"] for r in reports)
    searched = sum(r["search/searched_decisions"] for r in reports)
    return {
        "dose": reports[0].get("search_dose"),
        "leaf_encoding": reports[0].get("search_leaf_encoding", "as_is"),
        "ms_mean": _weighted(reports, "search/ms_mean",
                             "search/searched_decisions"),
        "leaves_mean": _weighted(reports, "search/leaves_mean",
                                 "search/searched_decisions"),
        "searched_decisions": searched,
        "decisions": dec,
        "placeholder_skips": skips,
        "placeholder_skip_rate": skips / dec if dec else None,
        "flips": flips,
        "flip_rate": flips / max(dec - skips, 1),
        "evaluator": reports[0].get("evaluator"),
    }


def read_job(results_dir: Path, arm: str, lane: str,
             chunks: int = CHUNKS) -> dict:
    """One (arm, lane) job: COMPLETE off its final, else PARTIAL off chunks.

    A PARTIAL job carries `rate` = the running pooled rate over the completed
    chunks and `complete: False`. Callers must never read a cell from it.
    """
    job = f"{arm.lower()}_{lane}"
    final = results_dir / f"{job}.final.json"
    chunk_paths = [results_dir / f"{job}.chunk{k:02d}.json" for k in range(chunks)]
    done = [p for p in chunk_paths if p.exists()]
    out = {"job": job, "arm": arm, "lane": lane,
           "chunks_done": len(done), "chunks_expected": chunks}
    if final.exists():
        d = json.loads(final.read_text())
        out.update({
            "status": "COMPLETE", "complete": True,
            "rate": d["eval/win_rate"], "wins_from_returns": d["wins_from_returns"],
            "episodes": d["episodes"], "mask_desyncs": d.get("mask_desyncs"),
            "chunks_done": d.get("chunks", len(done)),
            "search": _search_block([d]) if "search/decisions" in d else None,
        })
        if out["search"] is not None:
            # the final pre-merges these; prefer its own values
            for src, dst in (("search/ms_mean", "ms_mean"),
                             ("search/leaves_mean", "leaves_mean"),
                             ("search/flip_rate", "flip_rate"),
                             ("search/placeholder_skip_rate",
                              "placeholder_skip_rate")):
                if d.get(src) is not None:
                    out["search"][dst] = d[src]
            out["search"]["evaluator"] = d.get("evaluator")
        return out
    if not done:
        out.update({"status": "PENDING", "complete": False, "rate": None,
                    "episodes": 0, "search": None,
                    "note": "not started (0 chunks on disk)"})
        return out
    reps = [json.loads(p.read_text()) for p in done]
    eps = sum(r["episodes"] for r in reps)
    out.update({
        "status": "PARTIAL", "complete": False,
        "rate": None,          # a PARTIAL job has no gradeable rate
        "partial_rate": sum(r["eval/win_rate"] * r["episodes"] for r in reps) / eps,
        "partial_wins_from_returns":
            sum(r["wins_from_returns"] * r["episodes"] for r in reps) / eps,
        "episodes": eps,
        "mask_desyncs": sum(r["mask_desyncs_delta"] for r in reps),
        "search": _search_block(reps),
        "note": f"PARTIAL: {len(done)}/{chunks} chunks; the rate above is the "
                f"running pooled rate over {eps} completed battles and is "
                "NEVER a cell input",
    })
    return out


def read_arm(results_dir: Path, arm: str, chunks: int = CHUNKS) -> dict:
    """Roll the lanes of one arm up. COMPLETE only when every lane is."""
    lanes = {ln: read_job(results_dir, arm, ln, chunks)
             for ln in ARMS[arm]["lanes"]}
    complete = all(j["complete"] for j in lanes.values())
    eps = sum(j["episodes"] for j in lanes.values())
    rates = [(j.get("rate") if j["complete"] else j.get("partial_rate"),
              j["episodes"]) for j in lanes.values()]
    pooled = (sum(r * n for r, n in rates if r is not None) / eps) if eps else None
    reports: list[dict] = []
    for ln in ARMS[arm]["lanes"]:
        job = f"{arm.lower()}_{ln}"
        f = results_dir / f"{job}.final.json"
        if f.exists():
            reports.append(json.loads(f.read_text()))
        else:
            reports += [json.loads(p.read_text())
                        for p in sorted(results_dir.glob(f"{job}.chunk*.json"))]
    search = _search_block(reports)
    return {
        "arm": arm, "what": ARMS[arm]["what"],
        "lanes_registered": list(ARMS[arm]["lanes"]),
        "status": "COMPLETE" if complete else (
            "PENDING" if all(j["status"] == "PENDING" for j in lanes.values())
            else "PARTIAL"),
        "complete": complete,
        "chunks_done": sum(j["chunks_done"] for j in lanes.values()),
        "chunks_expected": chunks * len(ARMS[arm]["lanes"]),
        "episodes": eps,
        "pooled_rate": pooled if complete else None,
        "partial_pooled_rate": None if complete else pooled,
        "mask_desyncs": sum(j.get("mask_desyncs") or 0 for j in lanes.values()),
        "search": search,
        "leaf_encoding_expected": ARMS[arm]["leaf_encoding"],
        "leaf_encoding_on_disk": search["leaf_encoding"] if search else None,
        "jobs": lanes,
    }


# ---------------------------------------------------------------------------
# the reads
# ---------------------------------------------------------------------------
def paired_read(name: str, arms: dict, t: str, c: str, lanes,
                primary: bool, prose: str) -> dict:
    """One pre-stated paired read. PENDING unless BOTH arms are COMPLETE on
    EVERY named lane — no cell may be printed on partial data."""
    out = {"read": name, "treatment": t, "comparator": c,
           "delta_name": f"delta({t} - {c})", "lanes": list(lanes),
           "primary": primary, "aggregator":
               "equal_weight_mean_of_per_lane_paired_deltas",
           "what_it_answers": prose}
    tj = {ln: arms[t]["jobs"][ln] for ln in lanes}
    cj = {ln: arms[c]["jobs"][ln] for ln in lanes}
    missing = [f"{j['job']} {j['chunks_done']}/{j['chunks_expected']}"
               for j in list(tj.values()) + list(cj.values())
               if not j["complete"]]
    out["per_lane_partial"] = {
        ln: {"t": tj[ln].get("rate") if tj[ln]["complete"]
             else tj[ln].get("partial_rate"),
             "t_chunks": f"{tj[ln]['chunks_done']}/{tj[ln]['chunks_expected']}",
             "c": cj[ln].get("rate") if cj[ln]["complete"]
             else cj[ln].get("partial_rate"),
             "c_chunks": f"{cj[ln]['chunks_done']}/{cj[ln]['chunks_expected']}"}
        for ln in lanes}
    if missing:
        out.update({
            "status": "PENDING", "cell": None, "pooled_delta": None,
            "blocked_by": missing,
            "note": ("PENDING — NO CELL ON PARTIAL DATA. Incomplete jobs: "
                     + ", ".join(missing) + ". The per-lane numbers above are "
                     "running pooled rates over completed chunks (PARTIAL); "
                     "they are printed so the run is readable as a RATE, and "
                     "they are NEVER cell inputs.")})
        return out
    per_lane = {ln: tj[ln]["rate"] - cj[ln]["rate"] for ln in lanes}
    deltas = [per_lane[ln] for ln in lanes]
    pooled_delta = sum(deltas) / len(deltas)
    n_t = sum(tj[ln]["episodes"] for ln in lanes)
    n_c = sum(cj[ln]["episodes"] for ln in lanes)
    p_t = sum(tj[ln]["rate"] * tj[ln]["episodes"] for ln in lanes) / n_t
    p_c = sum(cj[ln]["rate"] * cj[ln]["episodes"] for ln in lanes) / n_c
    se = se_terms(p_t, n_t, p_c, n_c, deltas)
    c_name, c_why = cell(pooled_delta, deltas, se["se_diff"])
    fragile = [nm for nm, ref in (("credit floor", FLOOR),
                                  ("2*se_diff", 2 * se["se_diff"]),
                                  ("zero", 0.0))
               if abs(pooled_delta - ref) < EPS]
    out.update({
        "status": "READ", "per_lane_delta": per_lane,
        "pooled_delta": pooled_delta,
        "pooled_rate_treatment": p_t, "n_treatment": n_t,
        "pooled_rate_comparator": p_c, "n_comparator": n_c,
        "n_nonpositive_lanes": sum(1 for d in deltas if d <= 0),
        "bar_2se": 2 * se["se_diff"], "credit_floor": FLOOR,
        "cell": c_name, "cell_why": c_why,
        "boundary_fragile": fragile or None,
        "boundary_fragile_note": None if not fragile else
        ("the pooled delta sits within float dust of " + ", ".join(fragile)
         + " — the cell is decided in BINARY at that boundary; report the "
           "numbers, not the letter"),
        **se})
    return out


def pl_read(arms: dict) -> dict:
    """P-L: one lane, SIGN ONLY, no cell, +-0.02 one-lane caveat."""
    name, t, c, lane, prose = PL_READ
    tj, cj = arms[t]["jobs"][lane], arms[c]["jobs"][lane]
    out = {"read": name, "treatment": t, "comparator": c, "lane": lane,
           "primary": False, "cell": None,
           "cell_rule": "NO CELL BY CONSTRUCTION — one lane, sign only",
           "what_it_answers": prose,
           "caveat": "ONE RUNG IS WORTH +-0.02; a one-lane delta inside "
                     "+-0.02 is indistinguishable from a redraw of the same "
                     "checkpoint.",
           "t_chunks": f"{tj['chunks_done']}/{tj['chunks_expected']}",
           "c_chunks": f"{cj['chunks_done']}/{cj['chunks_expected']}"}
    if not (tj["complete"] and cj["complete"]):
        out.update({
            "status": "PENDING", "delta": None, "sign": None,
            "t_rate_partial": tj.get("partial_rate"),
            "c_rate_partial": cj.get("partial_rate"),
            "note": "PENDING — NO READ ON PARTIAL DATA; the rates shown are "
                    "running pooled rates over completed chunks (PARTIAL)."})
        return out
    d = tj["rate"] - cj["rate"]
    within = abs(d) <= ONE_RUNG_SPREAD + EPS
    out.update({
        "status": "READ", "t_rate": tj["rate"], "c_rate": cj["rate"],
        "delta": d, "sign": "+" if d > 0 else ("-" if d < 0 else "0"),
        "within_one_rung": within,
        "note": (f"sign {'+' if d > 0 else ('-' if d < 0 else '0')}; "
                 f"|delta| = {abs(d):.4f} "
                 f"{'WITHIN' if within else 'OUTSIDE'} the "
                 f"+-{ONE_RUNG_SPREAD} one-lane redraw spread")})
    return out


def leaves_equality(arms: dict) -> dict:
    """DET_BLIND.md §6: leaves_mean must be equal between S3B and S3M — a
    leaves delta would mean the option changed the search TREE, which it must
    not. DIAGNOSTIC, never a cell; the tolerance is stated, not discovered,
    because once a decision flips the two arms play different battles."""
    b, m = arms["S3B"].get("search"), arms["S3M"].get("search")
    out = {"check": "leaves_mean equality S3B vs S3M",
           "tolerance_rel": LEAVES_TOL_REL, "cell": None,
           "rule": "DIAGNOSTIC ONLY — never a cell. Exact equality holds at "
                   "MATCHED decisions (DET_BLIND.md §4, 11.4% argmax flips at "
                   "IDENTICAL leaf counts). Live, the arms diverge after the "
                   "first flip and play different battles, so the live check "
                   "is a stated tolerance on the relative difference."}
    if not b or not m or b["leaves_mean"] is None or m["leaves_mean"] is None:
        out.update({"status": "PENDING", "pass": None,
                    "note": "one or both arms have no search counters yet"})
        return out
    rel = (b["leaves_mean"] - m["leaves_mean"]) / m["leaves_mean"]
    out.update({
        "status": "READ" if (arms["S3B"]["complete"] and arms["S3M"]["complete"])
        else "PARTIAL",
        "s3b_leaves_mean": b["leaves_mean"], "s3m_leaves_mean": m["leaves_mean"],
        "rel_delta": rel, "pass": abs(rel) <= LEAVES_TOL_REL,
        "note": (f"relative delta {rel:+.4f} "
                 f"{'within' if abs(rel) <= LEAVES_TOL_REL else 'OUTSIDE'} the "
                 f"stated +-{LEAVES_TOL_REL:.0%} tolerance"
                 + ("" if arms["S3B"]["complete"] and arms["S3M"]["complete"]
                    else "; computed over COMPLETED CHUNKS ONLY (PARTIAL)"))})
    return out


def decision_agreement(arms: dict) -> dict:
    """The decision-level flip stats that the counters actually support.

    ch3_eval records flips against the POLICY ARGMAX per arm, not a
    decision-by-decision pairing between arms — the arms play different
    battles once a decision flips, so a true S3B-vs-S3M agreement rate is NOT
    available from these artifacts. What IS available: each arm's own
    flip_rate vs its policy, and the difference between them. Stated so the
    number is not mistaken for the offline 11.4% argmax-change figure."""
    out = {"check": "decision-level flip stats (S3B vs S3M)",
           "available": "per-arm flip rate vs the arm's OWN policy argmax",
           "not_available": ("a paired S3B-vs-S3M per-decision agreement rate "
                             "— the arms diverge after the first flip and "
                             "never see the same decision set. DET_BLIND.md "
                             "§4's 11.4% argmax-change figure is the OFFLINE "
                             "matched-decision number and is not this."),
           "cell": None}
    for arm in ("S3M", "S3B", "S3L", "A1E"):
        s = arms[arm].get("search")
        if s:
            out[arm] = {"flip_rate": s["flip_rate"], "flips": s["flips"],
                        "decisions": s["decisions"],
                        "placeholder_skips": s["placeholder_skips"],
                        "placeholder_skip_rate": s["placeholder_skip_rate"],
                        "basis": arms[arm]["status"]}
    if "S3B" in out and "S3M" in out:
        out["flip_rate_delta_B_minus_M"] = (
            out["S3B"]["flip_rate"] - out["S3M"]["flip_rate"])
    return out


# ---------------------------------------------------------------------------
# the off-Foul-Play anchor
# ---------------------------------------------------------------------------
def offfp_anchor(offfp_dir: Path) -> dict:
    """F3M112 / F3B112 vs the banked greedy t112 and vs each other.
    DESCRIPTIVE, never a verdict input. Both FP@20 disclosures travel."""
    out = {"axis": "off Foul Play", "budget_ms": 20,
           "budget_note": "`--search-time-ms 20` (gen 1). FP@20 is an "
                          "INSTRUMENT, not a rung.",
           "role": "DESCRIPTIVE ANCHOR — never a verdict input",
           "disclosures_verbatim": list(FP20_DISCLOSURES),
           "banked_comparator": dict(BANKED_OFFFP_T112),
           "expected_direction_prestated":
               "NEGATIVE — the 50M batch lane read search@M 0.3807 against "
               "greedy 0.4740 off FP@20 (-0.0933, -7.3 se). A positive read "
               "is a finding to record, not a gate.",
           "arms": {}}
    for tag, arm, enc in (("f3m112", "F3M112", "as_is"),
                          ("f3b112", "F3B112", "det_blind")):
        p = offfp_dir / f"{tag}.json"
        if not p.exists():
            log = offfp_dir / f"{tag}.runner.log"
            out["arms"][arm] = {
                "status": "PENDING", "leaf_encoding": enc,
                "our_win_rate": None,
                "note": ("no final on disk"
                         + (" (runner log present — arm is running)"
                            if log.exists() else " (not started)"))}
            continue
        d = json.loads(p.read_text())
        finished = d["battles_finished"]
        forfeits = 0
        rj = offfp_dir / f"{tag}.runner.json"
        if rj.exists():
            forfeits = json.loads(rj.read_text()).get("crash_forfeits", 0)
        n_eff = finished - forfeits
        out["arms"][arm] = {
            "status": "COMPLETE" if finished == d["battles_requested"]
            else "PARTIAL",
            "leaf_encoding": enc,
            "our_win_rate": d["our_win_rate"],
            "battles_requested": d["battles_requested"],
            "battles_finished": finished,
            "crash_forfeits": forfeits, "n_eff": n_eff,
            "foulplay_win_rate": d["foulplay_win_rate"],
            "tie_rate": d["tie_rate"], "mean_turns": d.get("mean_turns"),
            "mask_desyncs": d.get("mask_desyncs"),
            "search/ms_mean": d.get("search/ms_mean"),
            "search/leaves_mean": d.get("search/leaves_mean"),
            "search/flips": d.get("search/flips"),
            "search/decisions": d.get("search/decisions"),
            "delta_vs_banked_greedy": d["our_win_rate"] - BANKED_OFFFP_T112["rate"],
            "prereg_sha256_stamped": d.get("prereg_sha256"),
        }
    a, b = out["arms"].get("F3M112", {}), out["arms"].get("F3B112", {})
    if a.get("our_win_rate") is not None and b.get("our_win_rate") is not None:
        out["delta_B_minus_M"] = b["our_win_rate"] - a["our_win_rate"]
        na, nb = a["n_eff"], b["n_eff"]
        pa, pb = a["our_win_rate"], b["our_win_rate"]
        out["se_diff_binomial_B_minus_M"] = math.sqrt(
            pa * (1 - pa) / na + pb * (1 - pb) / nb)
    else:
        out["delta_B_minus_M"] = None
        out["note_pairwise"] = ("PENDING — both off-FP arms must be complete "
                                "before the B-vs-M comparison prints")
    return out


# ---------------------------------------------------------------------------
# provenance
# ---------------------------------------------------------------------------
def _sha256(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(("git", *args), cwd=REPO, capture_output=True,
                              text=True, timeout=20).stdout.strip() or None
    except Exception:                                    # pragma: no cover
        return None


def _git_versions(rel: str) -> list[dict]:
    """Every committed version of `rel`, newest first, with its sha256 — so a
    sha256 stamped into a result at LAUNCH time can be resolved to the pre-reg
    revision it was launched against instead of merely mismatching today's."""
    log = _git("log", "--format=%H\t%s", "--", rel)
    out = []
    for line in (log or "").splitlines():
        commit, _, subject = line.partition("\t")
        try:
            blob = subprocess.run(("git", "show", f"{commit}:{rel}"), cwd=REPO,
                                  capture_output=True, timeout=20).stdout
        except Exception:                                # pragma: no cover
            continue
        out.append({"commit": commit, "subject": subject,
                    "sha256": hashlib.sha256(blob).hexdigest()})
    return out


def provenance(results_dir: Path, offfp_dir: Path) -> dict:
    prereg = {}
    if PREREG_VSSH.exists():
        import yaml
        prereg = yaml.safe_load(PREREG_VSSH.read_text()) or {}
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "generated_at_unix": time.time(),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "readout_script": "scripts/search_s3_readout.py",
        "readout_script_sha256": _sha256(Path(__file__).resolve()),
        "prereg_vssh": {"path": str(PREREG_VSSH.relative_to(REPO)),
                        "sha256": _sha256(PREREG_VSSH)},
        "prereg_offfp": {"path": str(PREREG_OFFFP.relative_to(REPO)),
                         "sha256": _sha256(PREREG_OFFFP)},
        "det_blind_read": {"path": str(DET_BLIND_DOC.relative_to(REPO)),
                           "sha256": _sha256(DET_BLIND_DOC),
                           "section": "§6 (P-B's read, verbatim)"},
        "results_dir": str(results_dir),
        "offfp_dir": str(offfp_dir),
        "checkpoints": prereg.get("checkpoints"),
    }


def attest(prov: dict, arms: dict, offfp: dict) -> dict:
    """Cheap on-disk attestations. A failure is printed, never silent."""
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    for text, where in ((CREDIT_LINE, PREREG_VSSH),):
        add("pre-reg carries the credit line verbatim",
            text in where.read_text(), str(where.relative_to(REPO)))
    for arm, spec in ARMS.items():
        got = arms[arm].get("leaf_encoding_on_disk")
        want = spec["leaf_encoding"]
        if want is None or got is None:
            add(f"{arm} leaf encoding stamped", got is None or want is None,
                f"expected {want}, on disk {got} (no search counters yet)")
        else:
            add(f"{arm} leaf encoding stamped", got == want,
                f"expected {want}, on disk {got}")
    for arm in ARMS:
        add(f"{arm} mask_desyncs == 0", (arms[arm].get("mask_desyncs") or 0) == 0,
            f"{arms[arm].get('mask_desyncs')}")
    rel = prov["prereg_offfp"]["path"]
    versions = _git_versions(rel)
    for arm in ("F3M112", "F3B112"):
        stamped = offfp["arms"].get(arm, {}).get("prereg_sha256_stamped")
        if not stamped:
            continue
        if stamped == prov["prereg_offfp"]["sha256"]:
            add(f"off-FP pre-reg sha256 stamped in {arm} resolves to a "
                "committed pre-reg revision", True,
                f"stamped {stamped[:12]}… == the file today (HEAD version)")
            continue
        hit = next((v for v in versions if v["sha256"] == stamped), None)
        add(f"off-FP pre-reg sha256 stamped in {arm} resolves to a committed "
            "pre-reg revision", hit is not None,
            (f"stamped {stamped[:12]}… = commit {hit['commit'][:12]} "
             f"(\"{hit['subject'][:60]}\"), SUPERSEDED by today's "
             f"{(prov['prereg_offfp']['sha256'] or '')[:12]}…. This is the "
             "RECORDED amendment that added F3B112 before it ran, not drift — "
             "the arm's own read is unchanged."
             if hit else
             f"stamped {stamped[:12]}… matches NO committed version of {rel} "
             "— investigate before quoting this arm."))
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


# ---------------------------------------------------------------------------
# build + render
# ---------------------------------------------------------------------------
def build(results_dir: Path, offfp_dir: Path, chunks: int = CHUNKS) -> dict:
    arms = {a: read_arm(results_dir, a, chunks) for a in ARMS}
    prov = provenance(results_dir, offfp_dir)
    offfp = offfp_anchor(offfp_dir)
    reads = {}
    for name, t, c, lanes, primary, prose in READS:
        reads[name] = paired_read(name, arms, t, c, lanes, primary, prose)
    reads["P-L"] = pl_read(arms)
    return {
        "schema": "search_s3_readout/1",
        "title": "search_s3_100m — SEARCH RELOOK screen S3 (JOURNEY 11.5)",
        "credit_line_verbatim": CREDIT_LINE,
        "credits_nothing": CREDITS_NOTHING,
        "one_rung_caveat": ONE_RUNG,
        "dose_confound_disclosure": DOSE_CONFOUND,
        "era_note": ERA_NOTE,
        "banked_reference_never_the_comparator": {
            "vssh_pooled": BANKED_VSSH_POOLED,
            "source": "results/ch5_100m/final_s1xx.json",
            "role": "CONTEXT ONLY"},
        "timing_note": TIMING_NOTE,
        "provenance": prov,
        "arms": arms,
        "reads": reads,
        "leaves_equality": leaves_equality(arms),
        "decision_flip_stats": decision_agreement(arms),
        "off_fp_anchor": offfp,
        "attest": attest(prov, arms, offfp),
    }


def _f(x, nd=4, dash="—"):
    return dash if x is None else f"{x:.{nd}f}"


def _sf(x, nd=4, dash="—"):
    return dash if x is None else f"{x:+.{nd}f}"


def render_markdown(rep: dict) -> str:
    p = rep["provenance"]
    L: list[str] = []
    L.append("# S3 READOUT — search relook on the 100M object (JOURNEY 11.5)")
    L.append("")
    L.append(f"**MACHINE-WRITTEN by `{p['readout_script']}` at "
             f"{p['generated_at_utc']}.** Regenerated in place on every run — "
             "do not hand-edit; edit the script.")
    L.append("")
    L.append(f"> **Credit line, verbatim:** \"{rep['credit_line_verbatim']}\"")
    L.append(">")
    L.append(f"> **{rep['credits_nothing']}**")
    L.append(">")
    L.append(f"> {rep['one_rung_caveat']}")
    L.append("")
    L.append(f"Pre-regs: `{p['prereg_vssh']['path']}` "
             f"(sha256 `{(p['prereg_vssh']['sha256'] or '')[:16]}…`) · "
             f"`{p['prereg_offfp']['path']}` "
             f"(sha256 `{(p['prereg_offfp']['sha256'] or '')[:16]}…`) · "
             f"P-B's read: `{p['det_blind_read']['path']}` "
             f"{p['det_blind_read']['section']}. "
             f"git HEAD `{(p['git_head'] or '?')[:12]}` "
             f"(dirty: {p['git_dirty']}).")
    L.append("")

    # ---- arms
    L.append("## Arms")
    L.append("")
    L.append("| arm | what | lanes | chunks | battles | pooled vs SH | status |")
    L.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for a, d in rep["arms"].items():
        rate = (f"**{d['pooled_rate']:.5f}**" if d["complete"]
                else (f"{d['partial_pooled_rate']:.5f} *(PARTIAL)*"
                      if d["partial_pooled_rate"] is not None else "—"))
        L.append(f"| {a} | {d['what']} | "
                 f"{'/'.join(d['lanes_registered'])} | "
                 f"{d['chunks_done']}/{d['chunks_expected']} | "
                 f"{d['episodes']} | {rate} | {d['status']} |")
    L.append("")
    L.append("Per-lane (a PARTIAL cell is the running pooled rate over the "
             "chunks on disk and is **never** a cell input):")
    L.append("")
    L.append("| arm | " + " | ".join(LANES) + " |")
    L.append("| --- | " + " | ".join("---:" for _ in LANES) + " |")
    for a, d in rep["arms"].items():
        cells = []
        for ln in LANES:
            j = d["jobs"].get(ln)
            if j is None:
                cells.append("*n/a*")
            elif j["complete"]:
                cells.append(f"{j['rate']:.5f} ({j['chunks_done']}/"
                             f"{j['chunks_expected']})")
            elif j.get("partial_rate") is not None:
                cells.append(f"{j['partial_rate']:.5f} PARTIAL "
                             f"({j['chunks_done']}/{j['chunks_expected']})")
            else:
                cells.append(f"PENDING (0/{j['chunks_expected']})")
        L.append(f"| {a} | " + " | ".join(cells) + " |")
    L.append("")
    L.append(f"*Era note.* {rep['era_note']}")
    L.append("")
    L.append(f"*Dose.* {rep['dose_confound_disclosure']}")
    L.append("")

    # ---- reads
    L.append("## Pre-stated reads")
    L.append("")
    L.append("| read | delta | " + " | ".join(f"Δ {ln}" for ln in LANES) +
             " | se_bin | se_clus | governing | 2·se_diff | CELL |")
    L.append("| --- | ---: | " + " | ".join("---:" for _ in LANES) +
             " | ---: | ---: | --- | ---: | --- |")
    for name in ("P-M", "P-B", "P-BA", "P-E"):
        r = rep["reads"][name]
        if r["status"] == "PENDING":
            L.append(f"| **{name}** ({r['delta_name']}) | *PENDING* | "
                     + " | ".join("—" for _ in LANES)
                     + " | — | — | — | — | **PENDING — no cell on partial "
                       "data** |")
            continue
        pl = r["per_lane_delta"]
        L.append(f"| **{name}** ({r['delta_name']}) | "
                 f"**{r['pooled_delta']:+.4f}** | "
                 + " | ".join(_sf(pl.get(ln)) for ln in LANES)
                 + f" | {_f(r['se_binomial'], 5)} | "
                   f"{_f(r['se_clustered'], 5)} | {r['governing']} | "
                   f"{_f(r['bar_2se'], 5)} | **{r['cell']}** |")
    L.append("")
    for name in ("P-M", "P-B", "P-BA", "P-E"):
        r = rep["reads"][name]
        tag = "PRIMARY" if r["primary"] else "SECONDARY"
        L.append(f"**{name}** ({tag}) — {r['what_it_answers']}")
        if r["status"] == "PENDING":
            L.append("")
            L.append(f"> {r['note']}")
            L.append("")
            L.append("| lane | " + f"{r['treatment']} (partial) | "
                     f"{r['comparator']} (partial) |")
            L.append("| --- | ---: | ---: |")
            for ln in r["lanes"]:
                c = r["per_lane_partial"][ln]
                L.append(f"| {ln} | "
                         f"{_f(c['t'], 5)} ({c['t_chunks']}) | "
                         f"{_f(c['c'], 5)} ({c['c_chunks']}) |")
        else:
            L.append("")
            L.append(f"> **{r['cell']}** — {r['cell_why']}. "
                     f"Pooled rates {r['pooled_rate_treatment']:.5f} "
                     f"(n={r['n_treatment']}) vs "
                     f"{r['pooled_rate_comparator']:.5f} "
                     f"(n={r['n_comparator']}); "
                     f"{r['n_nonpositive_lanes']}/3 lanes non-positive. "
                     f"se_diff = **{r['governing']}** "
                     f"{r['se_diff']:.5f} (binomial {r['se_binomial']:.5f}, "
                     f"clustered {_f(r['se_clustered'], 5)}) — the LARGER of "
                     "the two governs.")
            if r.get("boundary_fragile_note"):
                L.append(">")
                L.append(f"> **BOUNDARY:** {r['boundary_fragile_note']}.")
        L.append("")

    # ---- P-L
    r = rep["reads"]["P-L"]
    L.append(f"**P-L** (SECONDARY, one lane {r['lane']}, **sign only, no "
             f"cell**) — {r['what_it_answers']}")
    L.append("")
    if r["status"] == "PENDING":
        L.append(f"> {r['note']} S3L {_f(r.get('t_rate_partial'), 5)} "
                 f"({r['t_chunks']}) vs S3M {_f(r.get('c_rate_partial'), 5)} "
                 f"({r['c_chunks']}). {r['caveat']}")
    else:
        L.append(f"> sign **{r['sign']}** — S3L {r['t_rate']:.5f} vs S3M "
                 f"{r['c_rate']:.5f}, delta {r['delta']:+.4f} "
                 f"({'WITHIN' if r['within_one_rung'] else 'OUTSIDE'} "
                 f"±0.02). {r['caveat']}")
    L.append("")

    # ---- timing
    L.append("## Search cost and decision counters — **CONTENDED**")
    L.append("")
    L.append(f"> {rep['timing_note']}")
    L.append("")
    L.append("| arm | dose | leaf encoding | ms/decision (mean) | "
             "leaves/decision (mean) | searched decisions | flip rate | "
             "placeholder skip rate | basis |")
    L.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for a, d in rep["arms"].items():
        s = d.get("search")
        if not s:
            L.append(f"| {a} | {'—' if not ARMS[a]['dose'] else ARMS[a]['dose']}"
                     f" | {ARMS[a]['leaf_encoding'] or '—'} | — | — | — | — | "
                     f"— | {d['status']} |")
            continue
        L.append(f"| {a} | {s['dose'] or '—'} | {s['leaf_encoding']} | "
                 f"{_f(s['ms_mean'], 1)} | {_f(s['leaves_mean'], 1)} | "
                 f"{s['searched_decisions']} | {_f(s['flip_rate'], 4)} | "
                 f"{_f(s['placeholder_skip_rate'], 4)} | {d['status']} |")
    L.append("")
    lq = rep["leaves_equality"]
    L.append(f"**leaves_mean equality (S3B vs S3M)** — {lq['rule']}")
    L.append("")
    if lq["status"] == "PENDING":
        L.append(f"> PENDING — {lq['note']}")
    else:
        L.append(f"> S3B {lq['s3b_leaves_mean']:.2f} vs S3M "
                 f"{lq['s3m_leaves_mean']:.2f} — {lq['note']}. "
                 f"({'PASS' if lq['pass'] else 'FLAG'}; diagnostic, no cell.)")
    L.append("")
    fs = rep["decision_flip_stats"]
    L.append(f"**Decision-level flips.** Available: {fs['available']}. "
             f"NOT available: {fs['not_available']}")
    if fs.get("flip_rate_delta_B_minus_M") is not None:
        L.append("")
        L.append(f"> flip-rate delta (S3B − S3M) = "
                 f"{fs['flip_rate_delta_B_minus_M']:+.4f} "
                 f"(S3B {fs['S3B']['flip_rate']:.4f} on basis "
                 f"{fs['S3B']['basis']}, S3M {fs['S3M']['flip_rate']:.4f} on "
                 f"basis {fs['S3M']['basis']}).")
    L.append("")

    # ---- off-FP
    o = rep["off_fp_anchor"]
    L.append("## Off-Foul-Play anchor (descriptive, never a verdict input)")
    L.append("")
    L.append(f"> **Budget named: {o['budget_ms']} ms.** {o['budget_note']}")
    L.append(">")
    for d in o["disclosures_verbatim"]:
        L.append(f"> **Standing FP@20 disclosure:** \"{d}\"")
    L.append(">")
    L.append(f"> Pre-stated direction: {o['expected_direction_prestated']}")
    L.append("")
    L.append("| arm | leaf encoding | our_win_rate | n_eff | Δ vs banked "
             "greedy t112 (0.50167, n=3000) | FP win rate | ties | status |")
    L.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for arm, d in o["arms"].items():
        if d["our_win_rate"] is None:
            L.append(f"| {arm} | {d['leaf_encoding']} | — | — | — | — | — | "
                     f"PENDING — {d['note']} |")
            continue
        L.append(f"| {arm} | {d['leaf_encoding']} | **{d['our_win_rate']:.4f}**"
                 f" | {d['n_eff']} | {d['delta_vs_banked_greedy']:+.4f} | "
                 f"{d['foulplay_win_rate']:.4f} | {d['tie_rate']:.4f} | "
                 f"{d['status']} |")
    L.append("")
    if o.get("delta_B_minus_M") is not None:
        L.append(f"> **F3B112 − F3M112 = {o['delta_B_minus_M']:+.4f}** "
                 f"(binomial se_diff {o['se_diff_binomial_B_minus_M']:.4f}). "
                 "Descriptive; credits nothing.")
    else:
        L.append(f"> {o.get('note_pairwise', 'PENDING')}.")
    L.append("")

    # ---- attest
    at = rep["attest"]
    L.append("## Attestations")
    L.append("")
    L.append(f"Overall: **{'PASS' if at['pass'] else 'FAIL'}** "
             f"({sum(1 for c in at['checks'] if c['pass'])}/"
             f"{len(at['checks'])}).")
    L.append("")
    L.append("| check | pass | detail |")
    L.append("| --- | --- | --- |")
    for c in at["checks"]:
        L.append(f"| {c['check']} | {'PASS' if c['pass'] else 'FAIL'} | "
                 f"{c['detail']} |")
    L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="results/search_s3_100m")
    ap.add_argument("--offfp-dir", default="results/search_s3_100m_offfp")
    ap.add_argument("--json", default=None,
                    help="default: <dir>/readout.json")
    ap.add_argument("--md", default="docs/search_relook/S3_READOUT.md")
    ap.add_argument("--no-write", action="store_true",
                    help="print the markdown only; write nothing")
    args = ap.parse_args()

    results_dir = Path(args.dir)
    if not results_dir.is_absolute():
        results_dir = REPO / results_dir
    offfp_dir = Path(args.offfp_dir)
    if not offfp_dir.is_absolute():
        offfp_dir = REPO / offfp_dir

    rep = build(results_dir, offfp_dir)
    md = render_markdown(rep)
    print(md)
    if args.no_write:
        return
    jpath = Path(args.json) if args.json else results_dir / "readout.json"
    if not jpath.is_absolute():
        jpath = REPO / jpath
    jpath.parent.mkdir(parents=True, exist_ok=True)
    jpath.write_text(json.dumps(rep, indent=2) + "\n")
    mpath = Path(args.md)
    if not mpath.is_absolute():
        mpath = REPO / mpath
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(md)
    print(f"wrote {jpath}")
    print(f"wrote {mpath}")


if __name__ == "__main__":
    main()

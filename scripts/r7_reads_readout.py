#!/usr/bin/env python
"""The R7 fleet's READS, computed from disk and never typed (docs/landmines.md: a number typed from memory into a
readout is the one nobody re-checks).

    python scripts/r7_reads_readout.py [--fp results/r7_reads_offfp] [--sh results/r7_reads]
                                       [--mech results/r7_reads_mech/end.json] [--json-out <file>]

THE PRE-REG is the header of every configs/r7_fleet_*.yaml (scripts/derive_r7_fleet.py r3, plan boxes 7-9); the arms
are configs/eval/r7_reads_offfp.yaml (off FP@N 25k/12k) and configs/eval/r7_reads.yaml (vs SH). This script carries
out its rules and adds none:

  VALIDITY  an FP arm is VALID only if its runner JSON carries fpn_counters_ok TRUE and the runner's log verifies the
            25k/12k budget; the house runner gates travel (the G2 precedent, scripts/r7_g2_readout.py): n_eff =
            finished - crash forfeits with wins reduced by the same count, Foul Play's own `Winner:` tally agreeing
            with the seat JSON EXACTLY, relaunches under the runner's cap, every challenge resolved, the seat's win
            rate equal to wins / finished (ties are non-wins), the launch sha equal to the rl sha, clean. An INVALID
            or missing arm "is INVALID and re-run, never pooled": it re-runs LAST on its rerun pair as a new pre-reg
            arm carrying `rerun_of: <arm>` (the procedure is in the pre-reg), whose VALID result replaces it here;
            until then every read that needs it is PENDING. A re-run is a later scheduler session: disclosed.
  PROGRAM   every arm's launch sha equals the sha the queue recorded after the pin (<fp>/launch_sha.txt): a commit
            between two launches would make two programs (docs/landmines.md, "a running block imports the working
            tree").
  LANE LOSS a TRAINING-side cell, never inferred from an FP arm: "a lane that fails a gate or cannot be resumed to 100M
            is dropped WITH ITS PAIR; the primary becomes the surviving pairs (under 3+2, losing a lane of pair f1 or
            f2 leaves ONE full pair -> PRIMARY VOID, while losing searched f3 leaves 2 vs 2); fewer than two pairs ->
            PRIMARY VOID". The operator records a dropped lane in the pre-reg's `lost_lanes` (validated here).
  PRIMARY   delta = the equal-weight mean of the SEARCHED finals minus the equal-weight mean of the CONTROL finals;
            se_diff = the LARGER of the pooled-binomial and the seed-clustered se_diff, the power script's exact
            formulas (scripts/r7_fleet_power.py): se_bin = sqrt(ps(1-ps)/N_S + pc(1-pc)/N_C) on the equal-weight means
            and each arm's total n_eff; se_clu = sqrt(var_S/k_S + var_C/k_C) over the per-lane finals, ddof 1.
            CELLS, STRICT at both boundaries, decided in exact rational arithmetic (a delta EXACTLY +0.025 or EXACTLY
            2*se_diff reads as NOT met): X-POS delta > +0.025 AND delta > 2 se; X-GAIN 0 < delta <= +0.025 AND
            delta > 2 se; X-COST -0.025 <= delta < 0 AND |delta| > 2 se; X-NEG delta < -0.025 AND |delta| > 2 se;
            X-FLAT everything else. The seed-clustered leg is irrational (a sqrt of a sample variance), so where it
            is the larger leg the 2-se comparison is made on squares in floats and flagged if within 1e-12.
  BESIDE IT "search/eligible_frac, search/searched_frac and search/played_frac are reported per arm at 12M and at the
            end, and a divergence is disclosed beside the primary"; "loss/grad_norm per arm reads that ratio, reported
            beside the primary"; the clip_frac split (loss/clip_frac_searched / _unsearched). Each as the mean over the
            5M steps ending at 12M and over the lane's last 5M steps, per lane and per arm.
  PAIRED    (secondary; PRINTED, never governs): per donor pair S_f - C_f, their mean and sd/sqrt(pairs); under 3+2
            the balanced two-pair delta beside the donor-unbalanced primary.
  MECHANISM each SEARCHED MINUS CONTROL at the END checkpoint, paired by donor: (i) search/kl_prior LOWER,
            (ii) search/override LOWER, (iv) search/value_gap LOWER -- means over each lane's last 5M steps of its
            history (scripts/merge_history.py's history_path: merged when a resume split the wandb history), refused
            unless the history reaches within two updates of the lane's pinned final step; (v) value/bias_mirror per
            arm, REPORTED, no action; (iii) the critic's per-position cell Spearman HIGHER and (vi) the greedy's
            split-sample regret LOWER -- r7_mechanism_reads.py's per-position rows, refused unless its summary shows c6
            on, a clean tree, 50 per bucket on G0's own rows (sha256) and the same positions for every lane. se = the
            LARGER of the lane-clustered se (sd of the per-pair differences / sqrt(pairs)) and, for (iii) and (vi),
            the position-level se (per position, the mean over pairs of S - C; sd / sqrt(positions)). MOVED = the
            named sign AND |d| > 2 se AND every pair carries the named sign. THE ROUTE: (i) NOT MOVED; (i) MOVED with
            (vi) NOT; or (i) and (vi) BOTH MOVED -- X-FLAT's action and X-COST / X-NEG's channel follow it.
  OBJECT    E6RR (R6's object, re-drawn), E3BR (the donors' ENS3, re-drawn), ES3F and EC2F (the fleet's committees; the
            control committee has TWO members under 3+2, disclosed): the fleet committee with the higher point
            estimate becomes the object iff it reaches E6RR - 0.013 (exact rationals); otherwise the R6 object stays.
            An EXACT tie between the two fleet committees is a cell the pre-reg does not name: flagged, never picked.
            Each fleet committee minus E3BR is DESCRIPTIVE. A ladder run still needs its own earning read (>= +0.05
            off FP@N over the re-drawn previous object, both re-drawn in one session): printed, never decided here.
  SH        (secondary, descriptive) GS / GC pooled vs SH, locked form, only when EVERY job of the arm has its final.
  OWED      RESUMES= / NODE_RESTARTS= (the watchdog's last WATCHDOG EXIT), every resume's from_step (each lane's
            meta.yaml), the donors' sha256 -- printed from disk so the prose readout never types them.

DISCLOSED ON EVERY NUMBER (the pre-reg): N-ANNEAL -- the finals are 300M-trained objects on two anneals (a warm start
off R6's finals), so a comparison with R6's finals (E6RR, E3BR) is confounded while the within-fleet comparison is not.
The pure core is tested (tests/test_r7_reads_readout.py); main() reads files and prints.
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from fractions import Fraction

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
FLOOR = Fraction(1, 40)                 # +0.025, exact
OBJECT_TOL = Fraction(13, 1000)         # the header's object-rule tolerance (trio A's, ~1 se_diff at 3000 vs 3000)
LADDER_BAR = 0.05                       # ratified 09-24, restated 09-25 on FP@N: a ladder run needs >= +0.05
WINDOW = 5_000_000                      # the in-loop counters: means over 5M steps
AT_12M = 12_000_000                     # "reported per arm at 12M and at the end"
STEPS_PER_UPDATE = 122_880              # rollout_steps 15360 x num_envs 8 (configs/r7_fleet_*.yaml)
HISTORY_SLACK = 2 * STEPS_PER_UPDATE    # a history must reach within two updates of the pinned final step
BUDGET_LINE = "budget verified from foul-play's log"
BUDGET_OK = "search_iterations=25000/12000"
MECH_PER_BUCKET, MECH_POSITIONS = 50, 200
WINNER_RE = re.compile(r"Winner: (\S+)")
# (name, history column or mech field, the named sign of searched - control)
MECH = [("i", "search/kl_prior", -1), ("ii", "search/override", -1), ("iii", "spearman", +1),
        ("iv", "search/value_gap", -1), ("v", "value/bias_mirror", 0), ("vi", "regret", -1)]
POSITION_LEVEL = {"iii", "vi"}
DOSE = ["search/eligible_frac", "search/searched_frac", "search/played_frac"]
BEHAVIOUR = ["loss/grad_norm", "loss/clip_frac_searched", "loss/clip_frac_unsearched"]
HIST_COLS = DOSE + BEHAVIOUR + [c for _, c, _ in MECH if "/" in c]
N_ANNEAL = ("N-ANNEAL: the finals are 300M-trained objects on two anneals (warm from R6's finals); a comparison with "
            "R6's finals is confounded, the within-fleet comparison is not")
WINNERS_CURSE = ("the higher of two committee reads carries a winner's curse of ~+0.005, so a replacement may sit "
                 "~0.018 below the incumbent in truth")
TIMER = ("every seat sends /timer on (CLAUDE.md, wire-visible); a RESULTS disclosure line is OWED with the next "
         "headline number")


# ----------------------------------------------------------------- the pure core
def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def neff(seat: dict, runner: dict) -> dict:
    """The runner's read rule (G_RUNNER, G2's): n_eff = finished - crash forfeits, wins reduced by the same count."""
    cf = int(runner.get("crash_forfeits", 0) or 0)
    n, w = int(seat["battles_finished"]) - cf, int(seat["our_wins"]) - cf
    return {"n": n, "w": w, "p": w / n if n > 0 else float("nan"), "crash_forfeits": cf}


def arm_valid(seat: dict | None, runner: dict | None, tally: Counter | None, budget_line: str | None) -> dict:
    """The per-arm gates. `tally` is Foul Play's own Winner: count (None when its stdout is missing); `budget_line`
    the runner log's last budget read-back (None when absent)."""
    if seat is None:
        return {"ok": False, "why": "no seat JSON"}
    runner = runner or {}
    ne = neff(seat, runner)
    why = []
    if runner.get("fpn_counters_ok") is not True:
        why.append(f"fpn_counters_ok {runner.get('fpn_counters_ok')} ({runner.get('fpn_counters_why')})")
    if not budget_line or BUDGET_OK not in budget_line:
        why.append(f"the runner log does not verify {BUDGET_OK} ({budget_line!r})")
    cap = runner.get("max_relaunches")
    if runner.get("void_too_many_crashes") or (cap is not None and (runner.get("relaunches") or 0) >= cap):
        why.append(f"relaunches {runner.get('relaunches')} >= cap {cap} or void_too_many_crashes")
    if seat.get("gate_all_challenges_resolved") is not True:
        why.append("not every challenge resolved")
    fin = int(seat["battles_finished"])
    if not fin or seat.get("our_win_rate") is None or abs(seat["our_win_rate"] - int(seat["our_wins"]) / fin) > 1e-12:
        why.append("the seat's win rate is not wins / finished (ties must be non-wins)")
    if not seat.get("launch_git_sha") or seat.get("launch_git_sha") != seat.get("rl_git_sha") or seat.get("rl_git_dirty") is not False:
        why.append(f"launch sha {seat.get('launch_git_sha')} vs rl sha {seat.get('rl_git_sha')} dirty {seat.get('rl_git_dirty')}")
    if tally is None:
        why.append("no Foul Play stdout to tally")
    else:
        got = {"seat": tally.get(seat["seat_username"], 0), "bot": tally.get(seat["fp_username"], 0),
               "ties": tally.get("None", 0)}
        exp = {"seat": ne["w"], "bot": int(seat.get("foulplay_wins", -1)), "ties": int(seat.get("ties") or 0)}
        if got != exp or sum(got.values()) != ne["n"]:
            why.append(f"tallies disagree: Foul Play {got} vs the seat JSON after the rule {exp} (n_eff {ne['n']})")
    return {"ok": not why, "why": "; ".join(why), **ne}


def check_lost(lost: list[str], primary_spec: dict) -> set[str]:
    """`lost_lanes` names primary arms; anything else is a typo that would silently keep a lost lane (the typed-list
    landmine) -- refused."""
    known = set(primary_spec["searched"]) | set(primary_spec["control"])
    bad = [x for x in lost if x not in known]
    if bad:
        raise SystemExit(f"REFUSED: lost_lanes {bad} are not primary arms {sorted(known)}")
    return set(lost)


def surviving_pairs(lost: set[str], pairs: dict[str, list[str]], unpaired: list[str]) -> dict:
    """LANE LOSS: a LOST lane (training-side, by its primary arm name) is dropped WITH ITS PAIR. `pairs` maps donor ->
    [searched, control]; `unpaired` are searched lanes with no control (f3 under 3+2). Fewer than two full pairs ->
    PRIMARY VOID."""
    keep = {f: arms for f, arms in pairs.items() if not any(a in lost for a in arms)}
    return {"pairs": keep, "unpaired": [a for a in unpaired if a not in lost], "lost_pairs": sorted(set(pairs) - set(keep)),
            "lost_unpaired": [a for a in unpaired if a in lost], "void": len(keep) < 2}


def primary(S: list[dict], C: list[dict]) -> dict:
    """delta and both se legs from the per-lane {n, w} of the SEARCHED and CONTROL finals; the cell with strict
    boundaries. Exact rationals where the decision rests on them (the delta, the binomial leg)."""
    fs = [Fraction(a["w"], a["n"]) for a in S]
    fc = [Fraction(a["w"], a["n"]) for a in C]
    ps, pc = sum(fs) / len(fs), sum(fc) / len(fc)
    NS, NC = sum(a["n"] for a in S), sum(a["n"] for a in C)
    d = ps - pc
    se2_bin = ps * (1 - ps) / NS + pc * (1 - pc) / NC                                    # exact
    rs, rc = [float(x) for x in fs], [float(x) for x in fc]
    se2_clu = (sd(rs) ** 2 / len(rs) if len(rs) > 1 else float("nan")) + (sd(rc) ** 2 / len(rc) if len(rc) > 1 else float("nan"))
    clu_larger = (not math.isnan(se2_clu)) and se2_clu > float(se2_bin)
    se2 = se2_clu if clu_larger else se2_bin
    four_se2 = 4 * se2
    d2 = d * d
    if clu_larger:                       # irrational leg: compare in floats, flag a near-tie
        beyond = float(d2) > four_se2
        near_2se = abs(float(d2) - four_se2) < 1e-12
    else:
        beyond = d2 > four_se2
        near_2se = d2 == four_se2
    if d > FLOOR and beyond:
        cell = "X-POS"
    elif 0 < d <= FLOOR and beyond:
        cell = "X-GAIN"
    elif -FLOOR <= d < 0 and beyond:
        cell = "X-COST"
    elif d < -FLOOR and beyond:
        cell = "X-NEG"
    else:
        cell = "X-FLAT"
    se = math.sqrt(float(se2))
    return {"delta": float(d), "p_searched": float(ps), "p_control": float(pc), "n_searched": NS, "n_control": NC,
            "k_searched": len(S), "k_control": len(C), "se_binomial": math.sqrt(float(se2_bin)),
            "se_clustered": math.sqrt(se2_clu) if not math.isnan(se2_clu) else float("nan"),
            "se_diff": se, "se_leg": "clustered" if clu_larger else "binomial", "z": float(d) / se if se else float("nan"),
            "cell": cell, "on_floor": d == FLOOR or d == -FLOOR, "near_2se": bool(near_2se)}


def paired(pairs: dict[str, tuple[float, float]]) -> dict:
    """Per donor pair S_f - C_f (rates); the mean and sd/sqrt(pairs). Printed, never governs."""
    diffs = {f: s - c for f, (s, c) in pairs.items()}
    k = len(diffs)
    m = mean(diffs.values())
    se = sd(diffs.values()) / math.sqrt(k) if k > 1 else float("nan")
    return {"per_pair": diffs, "mean": m, "se": se, "pairs": k}


def moved(per_pair: dict[str, float], sign: int, se: float) -> dict:
    """MOVED = the named sign AND |d| > 2 se AND every pair carries the named sign (sign 0: reported, no action)."""
    d = mean(per_pair.values())
    if sign == 0:
        return {"d": d, "se": se, "moved": None}
    ok = (not math.isnan(se)) and d * sign > 0 and abs(d) > 2 * se and all(v * sign > 0 for v in per_pair.values())
    return {"d": d, "se": se, "moved": bool(ok)}


def mech_read(name: str, sign: int, per_pair: dict[str, float], per_position: list[float] | None) -> dict:
    k = len(per_pair)
    se_lane = sd(per_pair.values()) / math.sqrt(k) if k > 1 else float("nan")
    se_pos = sd(per_position) / math.sqrt(len(per_position)) if per_position and len(per_position) > 1 else float("nan")
    legs = [x for x in (se_lane, se_pos) if not math.isnan(x)]
    se = max(legs) if legs else float("nan")
    out = moved(per_pair, sign, se)
    out.update({"read": name, "se_lane": se_lane, "se_position": se_pos, "per_pair": per_pair,
                "positions": len(per_position) if per_position else 0})
    return out


def route(i_moved: bool | None, vi_moved: bool | None) -> str:
    """(i) NOT MOVED is decided by (i) alone; the other two cells need (vi)."""
    if i_moved is False:
        return "(i) NOT MOVED"
    if i_moved is None or vi_moved is None:
        return "PENDING"
    return "(i) and (vi) BOTH MOVED" if vi_moved else "(i) MOVED, (vi) NOT"


ACTIONS = {
    "X-POS": "EXPERT ITERATION IS CREDITED -- in the WARM-START regime (R6 finals + 100M at lr 2.5e-05, a second anneal) "
             "with a TRUE-world T-op at these dials; nothing about fresh-start ExIt, nothing against R6's objects. The "
             "lever stays in the next fleet's base; the object follows the OBJECT RULE.",
    "X-GAIN": "a RESOLVED gain below the floor, NOT credited; the lever STAYS in the next fleet's base (the mirror of X-COST).",
    "X-COST": "a RESOLVED cost below the floor, not a null; the lever leaves the base and gets its own lap on the channel "
              "the mechanism route names.",
    "X-NEG": "credited NEGATIVE; the lever leaves the base; its own lap on the channel the mechanism route names.",
}
FLAT_ROUTES = {
    "(i) NOT MOVED": "the lever leaves the base; the next lap is the TARGET FORM (beta, the value coefficient, tau: the "
                     "cheaper of section 10's two readings; the student's capacity stays an own-lap item, JOURNEY 14).",
    "(i) MOVED, (vi) NOT": "the lever leaves the base; the next lap is the STRONGER EVALUATOR (the student absorbed targets "
                           "that carry what the critic already knows).",
    "(i) and (vi) BOTH MOVED/+": "the lever STAYS in the base; the next lap is the STRONGER EVALUATOR (the mechanism works "
                                 "below this fleet's power).",
    "(i) and (vi) BOTH MOVED/-": "the lever leaves the base; the next lap is the BEHAVIOUR channel (the targets are absorbed "
                                 "and compound, yet the arm does not gain).",
}
CHANNEL = {"(i) NOT MOVED": "the policy target", "(i) MOVED, (vi) NOT": "the evaluator",
           "(i) and (vi) BOTH MOVED": "the behaviour channel (the off-policy data from a true-world search, or the "
                                      "clip's side channel -- the clip_frac split and loss/grad_norm per arm say which)"}


def action(cell: str, rt: str, delta: float, i_moved: bool | None) -> str:
    if cell == "X-FLAT":
        if rt == "PENDING":
            return "X-FLAT: a NULL at this dose that closes nothing (rule 6); its action waits on the mechanism route (PENDING)."
        key = rt if rt != "(i) and (vi) BOTH MOVED" else rt + ("/+" if delta > 0 else "/-")
        return ("X-FLAT, a null that closes nothing (rule 6), routed on " + rt + ": " + FLAT_ROUTES[key]
                + " Never 'search does not work'.")
    text = cell + ": " + ACTIONS[cell]
    if cell in ("X-COST", "X-NEG"):
        text += f" CHANNEL: {CHANNEL.get(rt, 'PENDING (the mechanism route)')}."
    if cell in ("X-POS", "X-GAIN"):
        if i_moved is False:
            text += " With (i) NOT MOVED, the gain is DISCLOSED as the lever's behaviour and value channels, not the policy target."
        elif i_moved is None:
            text += " The attribution is PENDING on (i) (the manipulation check)."
    return text


def object_rule(arms: dict[str, dict | None], incumbent: str, fleet: list[str], tol: Fraction = OBJECT_TOL) -> dict:
    """On exact rationals {w, n}: the fleet committee with the higher point estimate becomes the object iff it reaches
    the incumbent - tol; an EXACT tie between fleet committees is an unnamed cell, flagged and not picked."""
    if any(arms.get(a) is None for a in [incumbent, *fleet]):
        return {"object": None, "why": "PENDING"}
    frac = {a: Fraction(arms[a]["w"], arms[a]["n"]) for a in [incumbent, *fleet]}
    top = max(frac[a] for a in fleet)
    best = [a for a in fleet if frac[a] == top]
    if len(best) > 1:
        return {"object": None, "why": f"UNNAMED CELL: an exact tie between {best} at {float(top):.4f}; the pre-reg names "
                                       "no winner -- the maintainer's call", "best_fleet": best}
    b = best[0]
    bar = frac[incumbent] - tol
    if frac[b] >= bar:
        return {"object": b, "why": f"{b} {float(frac[b]):.4f} reaches {incumbent} - {float(tol)} = {float(bar):.4f}",
                "best_fleet": b}
    return {"object": incumbent, "why": f"{b} {float(frac[b]):.4f} does not reach {incumbent} - {float(tol)} = "
                                        f"{float(bar):.4f}; the R6 object stays", "best_fleet": b}


def se_unpaired(a: dict, b: dict) -> float:
    return math.sqrt(a["p"] * (1 - a["p"]) / a["n"] + b["p"] * (1 - b["p"]) / b["n"])


def stream_windows(path: str, cols: list[str], final_step: int | None, window: int = WINDOW, at: int = AT_12M,
                   slack: int = HISTORY_SLACK) -> dict:
    """Two streaming passes over a history CSV (a 100M lane's history is ~3M rows: loading it whole costs ~12 GB):
    the max _step, then per-column sums over [at - window, at] and (top - window, top]. Only `_step` and `cols` are
    parsed. Refused when the history stops more than `slack` short of the pinned final step (a stale or truncated
    extraction would otherwise be read silently)."""
    def rows():
        with open(path, newline="") as f:
            r = csv.reader(f)
            head = next(r)
            ix = {c: head.index(c) for c in ["_step", *cols] if c in head}
            if "_step" not in ix:
                raise SystemExit(f"{path}: no _step column")
            for line in r:
                s = line[ix["_step"]] if ix["_step"] < len(line) else ""
                if s == "":
                    continue
                yield float(s), {c: (line[i] if i < len(line) else "") for c, i in ix.items() if c != "_step"}, ix
    top = None
    ix = {}
    for s, _v, ix in rows():
        top = s if top is None or s > top else top
    if top is None:
        return {"ok": False, "why": f"{path}: no rows"}
    out = {"ok": True, "path": path, "max_step": top, "final_step": final_step, "missing_cols": [c for c in cols if c not in ix]}
    if final_step is not None and top < final_step - slack:
        out.update(ok=False, why=f"history stops at {top:.0f}, more than {slack} short of the pinned final {final_step}")
    sums = {k: {c: [0.0, 0] for c in cols} for k in ("12M", "end")}
    for s, v, _ in rows():
        for k, lo, hi in (("12M", at - window, at), ("end", top - window, top)):
            if (lo <= s <= hi) if k == "12M" else (lo < s <= hi):
                for c in cols:
                    x = v.get(c, "")
                    if x not in ("", None):
                        fx = float(x)
                        if fx == fx:
                            sums[k][c][0] += fx
                            sums[k][c][1] += 1
    for k in sums:
        out[k] = {c: (a / n if n else float("nan")) for c, (a, n) in sums[k].items()}
        out[k + "#n"] = {c: n for c, (_a, n) in sums[k].items()}
    out["reached_12M"] = top >= at
    return out


# ----------------------------------------------------------------- disk readers
def load_json(p: str) -> dict | None:
    return json.load(open(p)) if os.path.exists(p) else None


def fp_tally(res: str, tag: str) -> Counter | None:
    for p, op in ((os.path.join(res, f"{tag}.fp.stdout"), open), (os.path.join(res, f"{tag}.fp.stdout.gz"), gzip.open)):
        if os.path.exists(p):
            c: Counter = Counter()
            with op(p, "rt", errors="replace") as f:
                for line in f:
                    m = WINNER_RE.search(line)
                    if m:
                        c[m.group(1)] += 1
            return c
    return None


def budget_line(res: str, tag: str) -> str | None:
    p = os.path.join(res, f"{tag}.runner.log")
    if not os.path.exists(p):
        return None
    lines = [s for s in open(p, errors="replace").read().splitlines() if BUDGET_LINE in s]
    return lines[-1] if lines else None


def one_session(parallel_log: str, order: list[str]) -> dict:
    """Every arm LAUNCHED inside ONE scheduler session (no START between the first and last launch), in the pinned
    order (the last LAUNCHED line of each arm)."""
    if not os.path.exists(parallel_log):
        return {"ok": False, "why": "no parallel.log"}
    lines = open(parallel_log).read().splitlines()
    idx = {a: max((i for i, s in enumerate(lines) if f" {a} LAUNCHED " in s), default=None) for a in order}
    if any(v is None for v in idx.values()):
        return {"ok": False, "why": f"launch lines missing: {[a for a, v in idx.items() if v is None]}"}
    seq = [idx[a] for a in order]
    lo, hi = min(seq), max(seq)
    session = not any(" START pid " in s for s in lines[lo + 1:hi + 1])
    return {"ok": bool(seq == sorted(seq) and session), "in_order": seq == sorted(seq), "one_session": session}


def mech_rows(mech_json: str) -> dict[str, dict[int, dict]]:
    """{checkpoint path (realpath): {pid: row}} from r7_mechanism_reads.py's .rows.jsonl beside its summary."""
    p = mech_json[:-5] + ".rows.jsonl" if mech_json.endswith(".json") else mech_json + ".rows.jsonl"
    out: dict[str, dict[int, dict]] = {}
    if not os.path.exists(p):
        return out
    for line in open(p):
        if line.strip():
            r = json.loads(line)
            if len(r["unit"]) == 1:
                out.setdefault(norm(r["unit"][0]), {})[int(r["pid"])] = r
    return out


def mech_summary_ok(mech_json: str, g0_rows: str) -> dict:
    """The mechanism instrument's provenance: c6 on, a clean tree, 50 per bucket (200 positions) on G0's own rows."""
    s = load_json(mech_json)
    if s is None:
        return {"ok": False, "why": f"no {mech_json}"}
    why = []
    if (s.get("encoder") or {}).get("POKEMON_RL_ENCODER_C6") != "1":
        why.append(f"encoder C6 {(s.get('encoder') or {}).get('POKEMON_RL_ENCODER_C6')!r}, not '1'")
    if s.get("git_dirty") is not False:
        why.append(f"git_dirty {s.get('git_dirty')}")
    if s.get("per_bucket") != MECH_PER_BUCKET or len(s.get("pids") or []) != MECH_POSITIONS:
        why.append(f"per_bucket {s.get('per_bucket')} / {len(s.get('pids') or [])} positions, not {MECH_PER_BUCKET} / {MECH_POSITIONS}")
    if os.path.exists(g0_rows):
        sha = hashlib.sha256(open(g0_rows, "rb").read()).hexdigest()
        if s.get("rows_sha256") != sha:
            why.append("rows_sha256 is not G0's rows")
    return {"ok": not why, "why": "; ".join(why), "git_sha": s.get("git_sha")}


PROGRAM_PATHS = ["rl", "scripts/ch3_fp_h2h.py", "scripts/ch3_r4_fp_runner.sh", "scripts/fp_arm_counters.py",
                 "scripts/fp_arms_parallel.py"]


def same_program(a: str | None, b: str | None) -> bool:
    """Two launch shas run the same program iff they are equal or nothing an arm imports or runs changed between them
    (a docs-only commit between the session and a re-run does not make a second program)."""
    import subprocess
    if not a or not b:
        return False
    if a.startswith(b[:7]) or b.startswith(a[:7]):
        return True
    r = subprocess.run(["git", "diff", "--quiet", a, b, "--", *PROGRAM_PATHS], cwd=REPO, capture_output=True)
    return r.returncode == 0


def norm(x: str) -> str:
    return os.path.realpath(x if os.path.isabs(x) else os.path.join(REPO, x))


def sh_pool(res: str, jobs: list[str]) -> dict | None:
    """Pooled vs-SH over EVERY job of an arm; PENDING (None) while any final is missing."""
    wins, n, parts = 0.0, 0, []
    for j in jobs:
        d = load_json(os.path.join(res, f"{j}.final.json"))
        if d is None:
            return None
        k, r = int(d.get("episodes") or d.get("n") or 0), d.get("eval/win_rate")
        if not k or r is None:
            return None
        wins += r * k
        n += k
        parts.append(f"{j} {r:.5f}")
    return {"p": wins / n, "n": n, "parts": parts} if n else None


def owed(run_dirs: dict[str, str], watchdog_log: str) -> dict:
    """RESUMES= / NODE_RESTARTS= from the watchdog's last WATCHDOG EXIT line; every resume's from_step per lane."""
    out = {"watchdog_exit": None, "resumes": {}}
    if os.path.exists(watchdog_log):
        ex = [s for s in open(watchdog_log, errors="replace").read().splitlines() if "WATCHDOG EXIT" in s]
        out["watchdog_exit"] = ex[-1] if ex else None
    for lane, d in run_dirs.items():
        m = os.path.join(norm(d), "meta.yaml")
        meta = yaml.safe_load(open(m)) if os.path.exists(m) else {}
        out["resumes"][lane] = [{"at": r.get("at"), "from_step": r.get("from_step"), "git_sha": str(r.get("git_sha", ""))[:10]}
                                for r in (meta.get("resumes") or [])]
    return out


# ----------------------------------------------------------------- markdown
def render_md(out: dict, pre: dict) -> str:
    """The readout as markdown, every number a field of `out` (the same dict readout.json holds): nothing typed."""
    f4 = lambda x: "PENDING" if x is None or x != x else f"{x:+.4f}"  # noqa: E731
    prim = out.get("primary", {})
    cell = prim.get("cell", "PENDING")
    L = [f"# R7 READS -- the fleet's PRIMARY off FP@N 25k/12k: **{cell}**", "",
         "**Pre-reg:** the header of every `configs/r7_fleet_*.yaml` (scripts/derive_r7_fleet.py r3, plan boxes 7-9); arms "
         "`configs/eval/r7_reads_offfp.yaml` and `configs/eval/r7_reads.yaml`. **Computed from disk** by "
         "`scripts/r7_reads_readout.py`; every number below is a field of its output.", "",
         f"**Program:** pinned launch sha `{out['session'].get('pinned_launch_sha')}`; arms ran on "
         f"{', '.join('`' + str(x)[:10] + '`' for x in out['session'].get('rl_git_sha', []))}; one scheduler session in the "
         f"pinned order: **{'yes' if out['session'].get('ok') else 'NO (a deviation, disclosed)'}**.", "",
         "## The arms (off FP@N 25k/12k, n_eff after the crash-forfeit rule)", "",
         "| arm | source | win rate | n_eff | crash forfeits | valid |", "|---|---|---|---|---|---|"]
    for a in pre["run_order"]:
        x = out["arms"].get(a)
        L.append(f"| {a} | {x['source_arm'] if x else '-'} | " + (f"{x['p']:.4f} | {x['n']} | {x['crash_forfeits']} | "
                 + ("VALID" if x["ok"] else "INVALID: " + x["why"]) if x else "PENDING | | | ") + " |")
    L += ["", "## The primary (the credit read)", ""]
    if prim.get("cell") in ("VOID", "PENDING"):
        L.append(f"**{prim['cell']}**" + (f": waiting on {prim.get('waiting')}" if prim.get("waiting") else "") + ".")
    else:
        L += [f"searched {prim['p_searched']:.4f} (k {prim['k_searched']}, n {prim['n_searched']}) minus control "
              f"{prim['p_control']:.4f} (k {prim['k_control']}, n {prim['n_control']}) = **delta {prim['delta']:+.4f}**; "
              f"se_binomial {prim['se_binomial']:.4f}, se_clustered {prim['se_clustered']:.4f} -> se_diff {prim['se_diff']:.4f} "
              f"({prim['se_leg']}); z {prim['z']:+.2f}. **CELL {cell}**"
              + (" (EXACTLY on the floor: NOT met)" if prim.get("on_floor") else "")
              + (" (within 1e-12 of 2 se)" if prim.get("near_2se") else "") + ".", "",
              'Credit line, verbatim (CLAUDE.md): "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff '
              'is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed '
              'finals at read time." STRICT: EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met.']
        pr = out.get("paired")
        if pr:
            L += ["", "PAIRED (printed, never governs): " + ", ".join(f"{k} {v:+.4f}" for k, v in pr["per_pair"].items())
                  + f"; mean {pr['mean']:+.4f} +- {pr['se']:.4f} (the balanced {pr['pairs']}-pair delta)."]
    L += ["", "## Beside the primary: the realized dose and the behaviour reads", "",
          "Means over the 5M steps ending at 12M and over each lane's last 5M steps (the pre-reg: \"reported per arm at 12M and "
          "at the end, and a divergence is disclosed beside the primary\"; loss/grad_norm per arm and the clip_frac split).", ""]
    hist = out.get("histories", {})
    lanes = pre["lanes"]
    s_l, c_l = list(lanes["searched"].values()), list(lanes["control"].values())
    L += ["| read | window | " + " | ".join(s_l + c_l) + " | S | C | S - C |", "|---|---|" + "---|" * (len(s_l) + len(c_l) + 3)]
    for c in DOSE + BEHAVIOUR:
        for w in ("12M", "end"):
            vals = {l: (hist.get(l, {}).get(w) or {}).get(c) if hist.get(l, {}).get("ok") else None for l in s_l + c_l}
            sv = [v for l, v in vals.items() if l in s_l and v is not None and v == v]
            cv = [v for l, v in vals.items() if l in c_l and v is not None and v == v]
            ms, mc = (mean(sv) if sv else None), (mean(cv) if cv else None)
            L.append(f"| {c} | {w} | " + " | ".join("-" if v is None or v != v else f"{v:.4f}" for v in vals.values())
                     + f" | {'-' if ms is None else f'{ms:.4f}'} | {'-' if mc is None else f'{mc:.4f}'} | "
                     + ("-" if ms is None or mc is None else f"{ms - mc:+.4f}") + " |")
    L += ["", "## The mechanism reads (searched - control at the END checkpoint, paired by donor)", "",
          "| read | d | se | lane se | position se | verdict | per pair |", "|---|---|---|---|---|---|---|"]
    for name, r in out.get("mechanism", {}).items():
        if r.get("moved") is None and "d" not in r:
            L.append(f"| ({name}) | {r.get('why', 'PENDING')} | | | | | |")
            continue
        verdict = {True: "MOVED", False: "NOT MOVED", None: "reported"}[r["moved"]]
        pos = "-" if r["se_position"] != r["se_position"] else f"{r['se_position']:.5f}"
        L.append(f"| ({name}) | {r['d']:+.5f} | {r['se']:.5f} | {r['se_lane']:.5f} | {pos} | {verdict} | "
                 + ", ".join(f"{k} {v:+.5f}" for k, v in r["per_pair"].items()) + " |")
    L += ["", f"**THE ROUTE: {out.get('route', 'PENDING')}**", "", f"**ACTION:** {out.get('action', 'PENDING (the primary)')}", "",
          "## The object rule (the R6 object's form, loop breaker on; n 3000 each)", "",
          f"**OBJECT = {out['object_rule'].get('object') or 'PENDING'}** -- {out['object_rule'].get('why')}.", "",
          "## vs SH (locked form; DESCRIPTIVE, saturated)", ""]
    for k, v in out.get("vs_sh", {}).items():
        L.append(f"- {k}: " + ("PENDING" if v is None else f"{v['p']:.4f} (n {v['n']})"))
    ow = out.get("owed", {})
    L += ["", "## Owed at readout, from disk", "", f"- watchdog: `{ow.get('watchdog_exit')}`"]
    L += [f"- {l}: resumes {len(rs)}" + (" (from_step " + ", ".join(str(r['from_step']) for r in rs) + ")" if rs else "")
          for l, rs in ow.get("resumes", {}).items()]
    L += [f"- donors: " + ", ".join(f"{k} `{v[:12]}`" for k, v in ow.get("donors_sha256", {}).items()), "",
          "## Disclosures", "",
          f"- {N_ANNEAL}.", f"- {WINNERS_CURSE}.", f"- {TIMER}.",
          "- FP@N 25k/12k with its calibration (two seats vs FP@20, NON-REJECTION, offset CI95 [-0.026, +0.011], gap-change "
          "CI95 [-0.042, +0.033], MDE 0.054); the equivalence test is weakly powered, and the point estimate flatters us.",
          "- NOT HERE: the BIG-BUDGET leg (G4, FP@500's calibrated FP@N after fp-speedup's calibration) and the anchors."]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prereg", default=os.path.join(REPO, "configs/eval/r7_reads_offfp.yaml"))
    ap.add_argument("--sh-prereg", default=os.path.join(REPO, "configs/eval/r7_reads.yaml"))
    ap.add_argument("--fp", default=os.path.join(REPO, "results/r7_reads_offfp"))
    ap.add_argument("--sh", default=os.path.join(REPO, "results/r7_reads"))
    ap.add_argument("--mech", default=os.path.join(REPO, "results/r7_reads_mech/end.json"))
    ap.add_argument("--g0-rows", default=os.path.join(REPO, "results/r7_g0/rollout_q.rows.jsonl"))
    ap.add_argument("--watchdog-log", default=os.path.join(REPO, "runs/train_watchdog.log"))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--md-out", default=None, help="also write the readout as markdown (readouts/R7_READS_READOUT.md's body)")
    args = ap.parse_args()
    pre = yaml.safe_load(open(args.prereg))
    P = pre["primary"]
    lost = check_lost(pre.get("lost_lanes") or [], P)
    out: dict = {"prereg": args.prereg}

    print("R7 READS -- the fleet pre-reg's PRIMARY (credit line), mechanism route, object rule; vs SH descriptive")
    print("Instrument: FP@N 25k/12k (Foul Play at a FIXED search budget). Its calibration against FP@20 travels: two seats,")
    print("NON-REJECTION, offset CI95 [-0.026, +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054. The equivalence test is")
    print("weakly powered, and the point estimate flatters us. Never differenced across instruments.")
    print(f"DISCLOSED ON EVERY NUMBER: {N_ANNEAL}.")
    print(f"TIMER: {TIMER}.\n")

    # ---- every FP arm, with its gates; a VALID re-run (`rerun_of`) replaces an invalid or missing arm
    def read_arm(tag: str) -> tuple[dict | None, dict]:
        seat, runner = load_json(os.path.join(args.fp, f"{tag}.json")), load_json(os.path.join(args.fp, f"{tag}.runner.json"))
        return seat, arm_valid(seat, runner, fp_tally(args.fp, tag), budget_line(args.fp, tag))
    reruns = {spec["rerun_of"]: name for name, spec in pre["arms"].items() if spec.get("rerun_of")}
    launch = open(os.path.join(args.fp, "launch_sha.txt")).read().strip() if os.path.exists(os.path.join(args.fp, "launch_sha.txt")) else None
    arms, valid, used = {}, {}, {}
    print("OFF FP@N arms (n_eff after the crash-forfeit rule; VALID = fpn_counters_ok + budget + the runner gates):")
    for arm in pre["run_order"]:
        seat, v = read_arm(arm.lower())
        src = arm
        if not v["ok"] and arm in reruns:
            seat_r, v_r = read_arm(reruns[arm].lower())
            print(f"  {arm:5s} " + (f"INVALID ({v['why']})" if seat else "no seat JSON") + f"; its re-run {reruns[arm]}:")
            seat, v, src = seat_r, v_r, reruns[arm]
        if seat and launch and not same_program(str(seat.get("launch_git_sha") or ""), launch):
            v = {**v, "ok": False, "why": (v["why"] + "; " if v["why"] else "") +
                 f"launched at {seat.get('launch_git_sha')}, a different program from the pinned {launch}"}
        valid[arm] = v["ok"]
        used[arm] = src
        arms[arm] = {**v, "source_arm": src, "rl_git_sha": seat.get("rl_git_sha"), "launch_git_sha": seat.get("launch_git_sha"),
                     "prereg_sha256": seat.get("prereg_sha256"),
                     "concurrent_decision_rate": seat.get("concurrent_decision_rate")} if seat else None
        print(f"  {src:5s} " + (f"{v['p']:.4f} (n_eff {v['n']}, crash forfeits {v['crash_forfeits']}) "
                                  + ("VALID" if v["ok"] else f"INVALID: {v['why']} -> re-run LAST on its rerun pair")
                                  if seat else "PENDING (no seat JSON)"))
    out["arms"] = arms
    sess = one_session(os.path.join(args.fp, "parallel.log"), [used[a] for a in pre["run_order"]])
    shas = {a["rl_git_sha"] for a in arms.values() if a}
    preregs = {a["prereg_sha256"] for a in arms.values() if a}
    out["session"] = {**sess, "rl_git_sha": sorted(x for x in shas if x), "pinned_launch_sha": launch,
                      "one_prereg": len(preregs) == 1}
    print(f"  ONE SESSION in the pinned order: {sess}" + ("" if sess.get("ok") else "  <- a DEVIATION, disclosed")
          + f"; program(s) {sorted(x for x in shas if x)} (pinned {launch}); one pre-reg sha: {len(preregs) == 1}")
    conc = {a: x["concurrent_decision_rate"] for a, x in arms.items() if x}
    print(f"  concurrent_decision_rate (disclosed; G2 gated it at 0.01): {conc}")

    # ---- LANE LOSS (training-side, declared) and the PRIMARY (every arm it needs VALID, else PENDING)
    sp = surviving_pairs(lost, P["pairs"], [a for a in P["searched"] if not any(a in v for v in P["pairs"].values())])
    out["lane_loss"] = sp
    print(f"\nLANE LOSS (declared in the pre-reg's lost_lanes: {sorted(lost) or 'none'}): pairs kept {sorted(sp['pairs'])}, "
          f"lost {sp['lost_pairs']}; unpaired searched kept {sp['unpaired']}")
    need = [a for p_ in sp["pairs"].values() for a in p_] + sp["unpaired"]
    waiting = [a for a in need if not valid.get(a)]
    prim = None
    if sp["void"]:
        print("PRIMARY VOID: fewer than two full donor pairs survive (the finals are recorded individually, never pooled).")
        out["primary"] = {"cell": "VOID"}
    elif waiting:
        print(f"PRIMARY PENDING: {waiting} not VALID yet (an invalid arm is re-run LAST on its rerun pair, never pooled).")
        out["primary"] = {"cell": "PENDING", "waiting": waiting}
    else:
        S = [arms[p[0]] for p in sp["pairs"].values()] + [arms[a] for a in sp["unpaired"]]
        C = [arms[p[1]] for p in sp["pairs"].values()]
        prim = primary(S, C)
        out["primary"] = prim
        print(f"\nPRIMARY: searched {prim['p_searched']:.4f} (k {prim['k_searched']}, n {prim['n_searched']}) - control "
              f"{prim['p_control']:.4f} (k {prim['k_control']}, n {prim['n_control']}) = delta {prim['delta']:+.4f}")
        print(f"  se_binomial {prim['se_binomial']:.4f}, se_clustered {prim['se_clustered']:.4f} -> se_diff {prim['se_diff']:.4f} "
              f"({prim['se_leg']}), z {prim['z']:+.2f}  => CELL {prim['cell']}"
              + ("  [ON THE FLOOR: reads NOT met]" if prim["on_floor"] else "") + ("  [within 1e-12 of 2 se]" if prim["near_2se"] else ""))
        print("  Credit line (verbatim, CLAUDE.md): \"a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff")
        print("  is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed")
        print("  finals at read time.\" STRICT: EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met.")
        print(f"  {N_ANNEAL}.")
        pr = paired({f: (arms[s]["p"], arms[c]["p"]) for f, (s, c) in sp["pairs"].items()})
        out["paired"] = pr
        print("  PAIRED (printed, never governs): " + ", ".join(f"{f} {d:+.4f}" for f, d in pr["per_pair"].items())
              + f"; mean {pr['mean']:+.4f} +- {pr['se']:.4f} (the balanced {pr['pairs']}-pair delta)")

    # ---- the lanes' histories: the dose and behaviour reads beside the primary, and the in-loop mechanism reads
    from merge_history import history_path
    lanes = pre["lanes"]
    hist = {}
    for l, d in lanes["run_dirs"].items():
        final = pre["checkpoints"][l].get("step")
        final = int(final) if str(final).isdigit() else None
        try:
            hp = str(history_path(norm(d)))
            hist[l] = stream_windows(hp, HIST_COLS, final)
        except (SystemExit, Exception) as e:          # a missing wandb run or a failed merge: PENDING, named
            hist[l] = {"ok": False, "why": f"{type(e).__name__}: {str(e)[:160]}"}
    out["histories"] = hist
    arm_of = {**{lanes["searched"][f]: "S" for f in lanes["searched"]}, **{lanes["control"][f]: "C" for f in lanes["control"]}}
    print("\nBESIDE THE PRIMARY -- the realized DOSE (a divergence is disclosed) and the BEHAVIOUR reads, per lane and per arm,")
    print("means over the 5M steps ending at 12M and over the last 5M steps:")
    for l, h in hist.items():
        if not h.get("ok"):
            print(f"  {l}: PENDING -- {h.get('why')}")
    for win in ("12M", "end"):
        for c in DOSE + BEHAVIOUR:
            per = {l: h[win][c] for l, h in hist.items() if h.get("ok") and not math.isnan(h[win][c])}
            s_ = [v for l, v in per.items() if arm_of[l] == "S"]
            c_ = [v for l, v in per.items() if arm_of[l] == "C"]
            ms, mc = mean(s_), mean(c_)
            print(f"  [{win:3s}] {c:28s} " + " ".join(f"{l} {v:.4f}" for l, v in per.items())
                  + (f" | S {ms:.4f} C {mc:.4f} S-C {ms - mc:+.4f}" if s_ and c_ else ""))
    out["dose_divergence_end"] = {c: (mean(h["end"][c] for l, h in hist.items() if h.get("ok") and arm_of[l] == "S")
                                      - mean(h["end"][c] for l, h in hist.items() if h.get("ok") and arm_of[l] == "C"))
                                  for c in DOSE}

    # ---- MECHANISM READS
    pairs_lanes = {f: (lanes["searched"][f], lanes["control"][f]) for f in sp["pairs"]}
    msum = mech_summary_ok(args.mech, args.g0_rows)
    mrows = mech_rows(args.mech) if msum["ok"] else {}
    path_of = {l: norm(str(pre["checkpoints"][l]["path"])) for l in lanes["run_dirs"]}
    reads = {}
    print(f"\nMECHANISM READS (searched - control at the END checkpoint, paired by donor; pairs {sorted(pairs_lanes)}):")
    if not msum["ok"]:
        print(f"  (iii)/(vi) PENDING: the instrument's provenance fails -- {msum['why']}")
    for name, col, sign in MECH:
        per_pair, per_pos, why = {}, None, "PENDING"
        if "/" in col:
            if pairs_lanes and all(hist[l].get("ok") for pr_ in pairs_lanes.values() for l in pr_):
                per_pair = {f: hist[s]["end"][col] - hist[c]["end"][col] for f, (s, c) in pairs_lanes.items()}
        elif msum["ok"]:
            got = {l: mrows.get(path_of[l]) for pr_ in pairs_lanes.values() for l in pr_}
            if pairs_lanes and all(got.values()):
                sets = [set(v) for v in got.values()]
                if any(s_ != sets[0] for s_ in sets):
                    why = "PENDING: the lanes' position sets differ"
                else:
                    pids = sorted(sets[0])
                    per_pair = {f: mean(got[s][p][col] for p in pids if got[s][p][col] == got[s][p][col])
                                - mean(got[c][p][col] for p in pids if got[c][p][col] == got[c][p][col])
                                for f, (s, c) in pairs_lanes.items()}
                    per_pos = []
                    for p in pids:
                        ds = [got[s][p][col] - got[c][p][col] for s, c in pairs_lanes.values()]
                        if all(x == x for x in ds):
                            per_pos.append(mean(ds))
        if not per_pair or any(v != v for v in per_pair.values()):
            reads[name] = {"read": name, "moved": None, "why": why}
            print(f"  ({name:3s}) {col}: {why}")
            continue
        r = mech_read(name, sign, per_pair, per_pos if name in POSITION_LEVEL else None)
        reads[name] = r
        want = {1: "HIGHER", -1: "LOWER", 0: "reported"}[sign]
        print(f"  ({name:3s}) {col} [{want}]: d {r['d']:+.5f}, se {r['se']:.5f} (lane {r['se_lane']:.5f}"
              + (f", position {r['se_position']:.5f} over {r['positions']}" if name in POSITION_LEVEL else "") + ") -> "
              + ({True: "MOVED", False: "NOT MOVED", None: "no action"}[r["moved"]])
              + "  [" + ", ".join(f"{f} {v:+.5f}" for f, v in per_pair.items()) + "]")
        if name == "v":
            print("        (v) per arm: " + " ".join(f"{l} {hist[l]['end'][col]:+.4f}" for l in lanes["run_dirs"] if hist[l].get("ok"))
                  + "  (a guard: section 31's +0.059 train/eval shift is the scale it watches)")
    out["mechanism"] = reads
    out["mech_provenance"] = msum
    rt = route(reads.get("i", {}).get("moved"), reads.get("vi", {}).get("moved"))
    out["route"] = rt
    print(f"  THE ROUTE: {rt}")

    if prim is not None:
        act = action(prim["cell"], rt, prim["delta"], reads.get("i", {}).get("moved"))
        out["action"] = act
        print(f"\nACTION (the pre-reg's): {act}")

    # ---- OBJECT RULE
    O = pre["object_rule"]
    ob_arms = {a: (arms[a] if valid.get(a) else None) for a in [O["incumbent"], O["donors_ens3"], *O["fleet"]]}
    ob = object_rule(ob_arms, O["incumbent"], O["fleet"], Fraction(str(O["tolerance"])))
    out["object_rule"] = ob
    print(f"\nOBJECT RULE (R6 object's form, loop breaker on; n 3000 each): OBJECT = {ob['object'] or 'PENDING'} ({ob['why']})")
    print(f"  Disclosed: {WINNERS_CURSE}. {N_ANNEAL}.")
    for a in O["fleet"]:
        for ref in (O["incumbent"], O["donors_ens3"]):
            x, y = ob_arms.get(a), ob_arms.get(ref)
            if x and y:
                se = se_unpaired(x, y)
                print(f"  {a} - {ref}: {x['p'] - y['p']:+.4f} (se {se:.4f}, z {(x['p'] - y['p']) / se:+.2f})  [N-ANNEAL"
                      + ("; DESCRIPTIVE" if ref == O["donors_ens3"] else "") + "]")
    if ob.get("object") and ob["object"] != O["incumbent"] and ob_arms.get(O["incumbent"]):
        gap = ob_arms[ob["object"]]["p"] - ob_arms[O["incumbent"]]["p"]
        print(f"  LADDER: a run needs its own earning read (>= +{LADDER_BAR} off FP@N over the re-drawn previous object, both "
              f"re-drawn in one session); this session's gap {gap:+.4f} is DESCRIPTIVE here.")

    # ---- vs SH (every job of an arm, or PENDING)
    import ch3_eval
    shpre = yaml.safe_load(open(args.sh_prereg))
    jobs = ch3_eval._jobs(shpre)
    by_arm = {a: sorted(j for j, spec in jobs.items() if spec["arm"] == a) for a in shpre["arms"]}
    gs, gc = sh_pool(args.sh, by_arm["GS"]), sh_pool(args.sh, by_arm["GC"])
    out["vs_sh"] = {"GS": gs, "GC": gc}
    print("\nvs SH, LOCKED form (no loop breaker), 3000 per lane (the control pools two lanes under 3+2, disclosed):")
    for nm, a in (("GS", gs), ("GC", gc)):
        print(f"  {nm}: " + ("PENDING (every job's final is needed)" if a is None else f"{a['p']:.4f} (n {a['n']})  [{', '.join(a['parts'])}]"))
    if gs and gc:
        se = se_unpaired(gs, gc)
        print(f"  GS - GC: {gs['p'] - gc['p']:+.4f} (se {se:.4f}; DESCRIPTIVE -- vs SH is saturated)")

    # ---- OWED AT READOUT, from disk
    ow = owed(lanes["run_dirs"], args.watchdog_log)
    ow["donors_sha256"] = {x: pre["checkpoints"][x]["sha256"] for x in ("b328", "b336", "b344")}
    out["owed"] = ow
    print("\nOWED AT READOUT (from disk):")
    print(f"  watchdog: {ow['watchdog_exit']}")
    for l, rs in ow["resumes"].items():
        print(f"  {l}: resumes {len(rs)}" + (" from_step " + ", ".join(str(r['from_step']) for r in rs) if rs else ""))
    print("  donors: " + ", ".join(f"{k} {v[:12]}" for k, v in ow["donors_sha256"].items()))
    print("\nNOT HERE: the BIG-BUDGET leg (G4, on FP@500's calibrated FP@N after fp-speedup's calibration) and the anchors.")
    if args.md_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.md_out)), exist_ok=True)
        with open(args.md_out, "w") as f:
            f.write(render_md(out, pre))
        print(f"-> {args.md_out}")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(out, f, indent=1, default=str)
        print(f"-> {args.json_out}")


if __name__ == "__main__":
    main()

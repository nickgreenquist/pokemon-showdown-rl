#!/usr/bin/env python
"""The R7 fleet's READS, computed from disk and never typed (docs/landmines.md: a number typed from memory into a
readout is the one nobody re-checks).

    python scripts/r7_reads_readout.py [--fp results/r7_reads_offfp] [--sh results/r7_reads]
                                       [--mech results/r7_reads_mech/end.json] [--json-out <file>]

THE PRE-REG is the header of every configs/r7_fleet_*.yaml (scripts/derive_r7_fleet.py r3, plan boxes 7-9); the arms
are configs/eval/r7_reads_offfp.yaml (off FP@N 25k/12k) and configs/eval/r7_reads.yaml (vs SH). This script carries
out its rules and adds none:

  VALIDITY  an FP arm is VALID only if its runner JSON carries fpn_counters_ok TRUE; the house runner gates travel
            (the G2 precedent, scripts/r7_g2_readout.py): n_eff = finished - crash forfeits with wins reduced by the
            same count, Foul Play's own `Winner:` tally agreeing with the seat JSON EXACTLY, relaunches under the
            runner's cap, every challenge resolved. An INVALID or missing arm "is INVALID and re-run, never pooled":
            it re-runs LAST on its rerun pair as a new pre-reg arm carrying `rerun_of: <arm>`, whose VALID result
            replaces it here; until then every read that needs it is PENDING. The re-run is a later scheduler
            session, a deviation from ONE session that this readout discloses.
  LANE LOSS a TRAINING-side cell, never inferred from an FP arm: "a lane that fails a gate or cannot be resumed to 100M
            is dropped WITH ITS PAIR; the primary becomes the surviving pairs (under 3+2, losing a lane of pair f1 or
            f2 leaves ONE full pair -> PRIMARY VOID, while losing searched f3 leaves 2 vs 2); fewer than two pairs ->
            PRIMARY VOID". The operator records a dropped lane in the pre-reg's `lost_lanes` (default none).
  PRIMARY   delta = the equal-weight mean of the SEARCHED finals minus the equal-weight mean of the CONTROL finals;
            se_diff = the LARGER of the pooled-binomial and the seed-clustered se_diff, the power script's exact
            formulas (scripts/r7_fleet_power.py): se_bin = sqrt(ps(1-ps)/N_S + pc(1-pc)/N_C) on the equal-weight means
            and each arm's total n_eff; se_clu = sqrt(var_S/k_S + var_C/k_C) over the per-lane finals, ddof 1.
            CELLS, STRICT at both boundaries, decided in exact rational arithmetic (a delta EXACTLY +0.025 or EXACTLY
            2*se_diff reads as NOT met): X-POS delta > +0.025 AND delta > 2 se; X-GAIN 0 < delta <= +0.025 AND
            delta > 2 se; X-COST -0.025 <= delta < 0 AND |delta| > 2 se; X-NEG delta < -0.025 AND |delta| > 2 se;
            X-FLAT everything else. The seed-clustered leg is irrational (a sqrt of a sample variance), so where it
            is the larger leg the 2-se comparison is made on squares in floats and flagged if within 1e-12.
  PAIRED    (secondary; PRINTED, never governs): per donor pair S_f - C_f, their mean and sd/sqrt(pairs); under 3+2
            the balanced two-pair delta beside the donor-unbalanced primary.
  MECHANISM each SEARCHED MINUS CONTROL at the END checkpoint, paired by donor: (i) search/kl_prior LOWER,
            (ii) search/override LOWER, (iv) search/value_gap LOWER -- means over each lane's last 5M steps of its
            history.csv (scripts/extract_history.py); (v) value/bias_mirror REPORTED, no action; (iii) the critic's
            per-position cell Spearman HIGHER and (vi) the greedy's split-sample regret LOWER -- r7_mechanism_reads.py's
            per-position rows. se = the LARGER of the lane-clustered se (sd of the per-pair differences / sqrt(pairs))
            and, for (iii) and (vi), the position-level se (per position, the mean over pairs of S - C; sd /
            sqrt(positions)). MOVED = the named sign AND |d| > 2 se AND every pair carries the named sign. THE ROUTE:
            (i) NOT MOVED; (i) MOVED with (vi) NOT; or (i) and (vi) BOTH MOVED -- and X-FLAT's action follows it.
  OBJECT    E6RR (R6's object, re-drawn), E3BR (the donors' ENS3, re-drawn), ES3F and EC2F (the fleet's committees; the
            control committee has TWO members under 3+2, disclosed): the fleet committee with the higher point
            estimate becomes the object iff it reaches E6RR - 0.013; otherwise the R6 object stays. Each fleet
            committee minus E3BR is DESCRIPTIVE (N-ANNEAL). A ladder run still needs its own earning read (>= +0.05
            off FP@N over the re-drawn previous object, both re-drawn in one session): printed, never decided here.
  SH        (secondary, descriptive) GS / GC pooled vs SH, locked form; the difference with the unpaired se.

The pure core is tested (tests/test_r7_reads_readout.py); main() only reads files and prints.
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
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
OBJECT_TOL = 0.013                      # the header's object-rule tolerance (trio A's, ~1 se_diff at 3000 vs 3000)
LADDER_BAR = 0.05                       # ratified 09-24, restated 09-25 on FP@N: a ladder run needs >= +0.05
MECH_WINDOW = 5_000_000                 # the in-loop mechanism counters: means over the last 5M steps
WINNER_RE = re.compile(r"Winner: (\S+)")
# (name, history column or mech field, the named sign of searched - control, acts)
MECH = [("i", "search/kl_prior", -1, True), ("ii", "search/override", -1, False),
        ("iii", "spearman", +1, False), ("iv", "search/value_gap", -1, False),
        ("v", "value/bias_mirror", 0, False), ("vi", "regret", -1, True)]
POSITION_LEVEL = {"iii", "vi"}


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


def arm_valid(seat: dict | None, runner: dict | None, tally: Counter | None, max_relaunches: int | None) -> dict:
    """The per-arm gates. `tally` is Foul Play's own Winner: count (None when its stdout is missing)."""
    if seat is None:
        return {"ok": False, "why": "no seat JSON"}
    runner = runner or {}
    ne = neff(seat, runner)
    why = []
    if runner.get("fpn_counters_ok") is not True:
        why.append(f"fpn_counters_ok {runner.get('fpn_counters_ok')} ({runner.get('fpn_counters_why')})")
    cap = runner.get("max_relaunches") or max_relaunches
    if runner.get("void_too_many_crashes") or (cap is not None and (runner.get("relaunches") or 0) >= cap):
        why.append(f"relaunches {runner.get('relaunches')} >= cap {cap} or void_too_many_crashes")
    if seat.get("gate_all_challenges_resolved") is not True:
        why.append("not every challenge resolved")
    if tally is None:
        why.append("no Foul Play stdout to tally")
    else:
        got = {"seat": tally.get(seat["seat_username"], 0), "bot": tally.get(seat["fp_username"], 0),
               "ties": tally.get("None", 0)}
        exp = {"seat": ne["w"], "bot": int(seat.get("foulplay_wins", -1)), "ties": int(seat.get("ties") or 0)}
        if got != exp or sum(got.values()) != ne["n"]:
            why.append(f"tallies disagree: Foul Play {got} vs the seat JSON after the rule {exp} (n_eff {ne['n']})")
    return {"ok": not why, "why": "; ".join(why), **ne}


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
    se = max(x for x in (se_lane, se_pos) if not math.isnan(x)) if not (math.isnan(se_lane) and math.isnan(se_pos)) else float("nan")
    out = moved(per_pair, sign, se)
    out.update({"read": name, "se_lane": se_lane, "se_position": se_pos, "per_pair": per_pair,
                "positions": len(per_position) if per_position else 0})
    return out


def route(i_moved: bool | None, vi_moved: bool | None) -> str:
    if i_moved is None or vi_moved is None:
        return "PENDING"
    if not i_moved:
        return "(i) NOT MOVED"
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
    "(i) NOT MOVED": "the lever leaves the base; the next lap is the TARGET FORM (beta, the value coefficient, tau).",
    "(i) MOVED, (vi) NOT": "the lever leaves the base; the next lap is the STRONGER EVALUATOR.",
    "(i) and (vi) BOTH MOVED/+": "the lever STAYS in the base; the next lap is the STRONGER EVALUATOR.",
    "(i) and (vi) BOTH MOVED/-": "the lever leaves the base; the next lap is the BEHAVIOUR channel.",
}
CHANNEL = {"(i) NOT MOVED": "the policy target", "(i) MOVED, (vi) NOT": "the evaluator",
           "(i) and (vi) BOTH MOVED": "the behaviour channel"}


def action(cell: str, rt: str, delta: float, i_moved: bool | None) -> str:
    if cell == "X-FLAT":
        if rt == "PENDING":
            return "X-FLAT: a NULL at this dose that closes nothing (rule 6); its action waits on the mechanism route (PENDING)."
        key = rt if rt != "(i) and (vi) BOTH MOVED" else rt + ("/+" if delta > 0 else "/-")
        return "X-FLAT, a null that closes nothing (rule 6), routed on " + rt + ": " + FLAT_ROUTES[key] + " Never 'search does not work'."
    text = cell + ": " + ACTIONS[cell]
    if cell in ("X-COST", "X-NEG"):
        text += f" CHANNEL: {CHANNEL.get(rt, 'PENDING (the mechanism route)')}."
    if cell in ("X-POS", "X-GAIN") and i_moved is False:
        text += " With (i) NOT MOVED, the gain is DISCLOSED as the lever's behaviour and value channels, not the policy target."
    return text


def object_rule(arms: dict[str, dict | None], incumbent: str, fleet: list[str], tol: float = OBJECT_TOL) -> dict:
    if any(arms.get(a) is None for a in [incumbent, *fleet]):
        return {"object": None, "why": "PENDING"}
    best = max(fleet, key=lambda a: arms[a]["p"])
    inc = arms[incumbent]["p"]
    if arms[best]["p"] >= inc - tol:
        return {"object": best, "why": f"{best} reaches {incumbent} - {tol} ({arms[best]['p']:.4f} >= {inc - tol:.4f})",
                "best_fleet": best}
    return {"object": incumbent, "why": f"no fleet committee reaches {incumbent} - {tol}; the R6 object stays",
            "best_fleet": best}


def se_unpaired(a: dict, b: dict) -> float:
    return math.sqrt(a["p"] * (1 - a["p"]) / a["n"] + b["p"] * (1 - b["p"]) / b["n"])


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


def history_window(run_dir: str, cols: list[str], window: int = MECH_WINDOW) -> dict:
    p = os.path.join(run_dir, "history.csv")
    if not os.path.exists(p):
        return {"ok": False, "why": f"no {p} (scripts/extract_history.py {run_dir})"}
    rows = list(csv.DictReader(open(p)))
    steps = [float(r["_step"]) for r in rows if r.get("_step")]
    top = max(steps)
    out = {"ok": True, "max_step": top, "window": [top - window, top]}
    for c in cols:
        v = [float(r[c]) for r in rows if r.get("_step") and float(r["_step"]) > top - window and r.get(c) not in (None, "")]
        v = [x for x in v if x == x]
        out[c] = mean(v) if v else float("nan")
        out[c + "#n"] = len(v)
    return out


def mech_rows(mech_json: str) -> dict[str, dict[int, dict]]:
    """{checkpoint path: {pid: row}} from r7_mechanism_reads.py's .rows.jsonl beside its summary."""
    p = mech_json[:-5] + ".rows.jsonl" if mech_json.endswith(".json") else mech_json + ".rows.jsonl"
    out: dict[str, dict[int, dict]] = {}
    if not os.path.exists(p):
        return out
    for line in open(p):
        if line.strip():
            r = json.loads(line)
            if len(r["unit"]) == 1:
                out.setdefault(r["unit"][0], {})[int(r["pid"])] = r
    return out


def sh_pool(res: str, prefix: str) -> dict | None:
    wins, n, parts = 0.0, 0, []
    for f in sorted(glob.glob(os.path.join(res, f"{prefix}*.final.json"))):
        d = json.load(open(f))
        k, r = int(d.get("episodes") or d.get("n") or 0), d.get("eval/win_rate")
        if k and r is not None:
            wins += r * k
            n += k
            parts.append(f"{os.path.basename(f).replace('.final.json', '')} {r:.5f}")
    return {"p": wins / n, "n": n, "parts": parts} if n else None


# ----------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prereg", default=os.path.join(REPO, "configs/eval/r7_reads_offfp.yaml"))
    ap.add_argument("--fp", default=os.path.join(REPO, "results/r7_reads_offfp"))
    ap.add_argument("--sh", default=os.path.join(REPO, "results/r7_reads"))
    ap.add_argument("--mech", default=os.path.join(REPO, "results/r7_reads_mech/end.json"))
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    pre = yaml.safe_load(open(args.prereg))
    P = pre["primary"]
    out: dict = {"prereg": args.prereg}

    print("R7 READS -- the fleet pre-reg's PRIMARY (credit line), mechanism route, object rule; vs SH descriptive")
    print("Instrument: FP@N 25k/12k (Foul Play at a FIXED search budget). Its calibration against FP@20 travels: two seats,")
    print("NON-REJECTION, offset CI95 [-0.026, +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054. The equivalence test is")
    print("weakly powered, and the point estimate flatters us. Never differenced across instruments.\n")

    # ---- every FP arm, with its gates; a VALID re-run (`rerun_of`) replaces an invalid or missing arm
    def read_arm(tag: str) -> tuple[dict | None, dict]:
        seat, runner = load_json(os.path.join(args.fp, f"{tag}.json")), load_json(os.path.join(args.fp, f"{tag}.runner.json"))
        v = arm_valid(seat, runner, fp_tally(args.fp, tag), None)
        return seat, v
    reruns = {spec["rerun_of"]: name for name, spec in pre["arms"].items() if spec.get("rerun_of")}
    arms, valid, used = {}, {}, {}
    print("OFF FP@N arms (n_eff after the crash-forfeit rule; VALID = fpn_counters_ok + the runner gates):")
    for arm in pre["run_order"]:
        seat, v = read_arm(arm.lower())
        src = arm
        if not v["ok"] and arm in reruns:
            seat_r, v_r = read_arm(reruns[arm].lower())
            print(f"  {arm:5s} " + (f"INVALID ({v['why']})" if seat else "no seat JSON") + f"; its re-run {reruns[arm]}:")
            seat, v, src = seat_r, v_r, reruns[arm]
        valid[arm] = v["ok"]
        used[arm] = src
        arms[arm] = {**v, "source_arm": src, "rl_git_sha": seat.get("rl_git_sha"), "rl_git_dirty": seat.get("rl_git_dirty"),
                     "prereg_sha256": seat.get("prereg_sha256")} if seat else None
        print(f"  {src:5s} " + (f"{v['p']:.4f} (n_eff {v['n']}, crash forfeits {v['crash_forfeits']}) "
                                  + ("VALID" if v["ok"] else f"INVALID: {v['why']} -> re-run LAST on its rerun pair")
                                  if seat else "PENDING (no seat JSON)"))
    out["arms"] = arms
    sess = one_session(os.path.join(args.fp, "parallel.log"), [used[a] for a in pre["run_order"]])
    shas = {a["rl_git_sha"] for a in arms.values() if a}
    same = bool(len(shas) == 1 and all(a and a["rl_git_dirty"] is False for a in arms.values()))
    preregs = {a["prereg_sha256"] for a in arms.values() if a}
    out["session"] = {**sess, "one_program": same, "rl_git_sha": sorted(x for x in shas if x), "one_prereg": len(preregs) == 1}
    print(f"  ONE SESSION in the pinned order: {sess}" + ("" if sess.get("ok") else "  <- a DEVIATION, disclosed")
          + f"; one program: {same} {sorted(x for x in shas if x)}; one pre-reg sha: {len(preregs) == 1}")

    # ---- LANE LOSS (training-side, declared) and the PRIMARY (every arm it needs VALID, else PENDING)
    lost = set(pre.get("lost_lanes") or [])
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
        pr = paired({f: (arms[s]["p"], arms[c]["p"]) for f, (s, c) in sp["pairs"].items()})
        out["paired"] = pr
        print(f"  PAIRED (printed, never governs): " + ", ".join(f"{f} {d:+.4f}" for f, d in pr["per_pair"].items())
              + f"; mean {pr['mean']:+.4f} +- {pr['se']:.4f} (the balanced {pr['pairs']}-pair delta)")

    # ---- MECHANISM READS
    lanes = pre["lanes"]
    pairs_lanes = {f: (lanes["searched"][f], lanes["control"][f]) for f in sp["pairs"]}
    hist = {l: history_window(lanes["run_dirs"][l], [c for _, c, _, _ in MECH if "/" in c]) for l in lanes["run_dirs"]}
    mrows = mech_rows(args.mech)
    norm = lambda x: os.path.realpath(x if os.path.isabs(x) else os.path.join(REPO, x))  # noqa: E731
    mrows = {norm(k): v for k, v in mrows.items()}
    path_of = {l: norm(str(pre["checkpoints"][l]["path"])) for l in lanes["run_dirs"]}
    reads = {}
    print(f"\nMECHANISM READS (searched - control at the END checkpoint, paired by donor; pairs {sorted(pairs_lanes)}):")
    for name, col, sign, _acts in MECH:
        per_pair, per_pos = {}, None
        if "/" in col:
            if all(hist[l].get("ok") for pr_ in pairs_lanes.values() for l in pr_):
                per_pair = {f: hist[s][col] - hist[c][col] for f, (s, c) in pairs_lanes.items()}
        else:
            got = {l: mrows.get(path_of[l]) for pr_ in pairs_lanes.values() for l in pr_}
            if pairs_lanes and all(got.values()):
                pids = sorted(set.intersection(*(set(v) for v in got.values())))
                per_pair = {f: mean(got[s][p][col] for p in pids if got[s][p][col] == got[s][p][col])
                            - mean(got[c][p][col] for p in pids if got[c][p][col] == got[c][p][col])
                            for f, (s, c) in pairs_lanes.items()}
                per_pos = []
                for p in pids:
                    ds = [got[s][p][col] - got[c][p][col] for s, c in pairs_lanes.values()]
                    if all(x == x for x in ds):
                        per_pos.append(mean(ds))
        if not per_pair or any(v != v for v in per_pair.values()):
            reads[name] = {"read": name, "moved": None, "why": "PENDING"}
            print(f"  ({name:3s}) {col}: PENDING")
            continue
        r = mech_read(name, sign, per_pair, per_pos if name in POSITION_LEVEL else None)
        reads[name] = r
        want = {1: "HIGHER", -1: "LOWER", 0: "reported"}[sign]
        print(f"  ({name:3s}) {col} [{want}]: d {r['d']:+.5f}, se {r['se']:.5f} (lane {r['se_lane']:.5f}"
              + (f", position {r['se_position']:.5f} over {r['positions']}" if name in POSITION_LEVEL else "") + ") -> "
              + ({True: "MOVED", False: "NOT MOVED", None: "no action"}[r["moved"]])
              + "  [" + ", ".join(f"{f} {v:+.5f}" for f, v in per_pair.items()) + "]")
    out["mechanism"] = reads
    rt = route(reads.get("i", {}).get("moved"), reads.get("vi", {}).get("moved"))
    out["route"] = rt
    print(f"  THE ROUTE: {rt}")
    out["in_loop"] = {l: {k: v for k, v in h.items()} for l, h in hist.items()}

    if prim is not None:
        act = action(prim["cell"], rt, prim["delta"], reads.get("i", {}).get("moved"))
        out["action"] = act
        print(f"\nACTION (the pre-reg's, verbatim in substance): {act}")

    # ---- OBJECT RULE
    O = pre["object_rule"]
    ob_arms = {a: (arms[a] if valid.get(a) else None) for a in [O["incumbent"], O["donors_ens3"], *O["fleet"]]}
    ob = object_rule(ob_arms, O["incumbent"], O["fleet"], O["tolerance"])
    out["object_rule"] = ob
    print(f"\nOBJECT RULE (R6 object's form, loop breaker on; n 3000 each): OBJECT = {ob['object'] or 'PENDING'} ({ob['why']})")
    for a in O["fleet"]:
        for ref in (O["incumbent"], O["donors_ens3"]):
            x, y = ob_arms.get(a), ob_arms.get(ref)
            if x and y:
                se = se_unpaired(x, y)
                print(f"  {a} - {ref}: {x['p'] - y['p']:+.4f} (se {se:.4f}, z {(x['p'] - y['p']) / se:+.2f})"
                      + ("  [DESCRIPTIVE, N-ANNEAL]" if ref == O["donors_ens3"] else ""))
    if ob.get("object") and ob["object"] != O["incumbent"] and ob_arms.get(O["incumbent"]):
        gap = ob_arms[ob["object"]]["p"] - ob_arms[O["incumbent"]]["p"]
        print(f"  LADDER: a run needs its own earning read (>= +{LADDER_BAR} off FP@N over the re-drawn previous object, both "
              f"re-drawn in one session); this session's gap {gap:+.4f} is DESCRIPTIVE here.")

    # ---- vs SH
    gs, gc = sh_pool(args.sh, "gs_"), sh_pool(args.sh, "gc_")
    out["vs_sh"] = {"GS": gs, "GC": gc}
    print("\nvs SH, LOCKED form (no loop breaker), 3000 per lane (the control pools two lanes under 3+2, disclosed):")
    for nm, a in (("GS", gs), ("GC", gc)):
        print(f"  {nm}: " + ("PENDING" if a is None else f"{a['p']:.4f} (n {a['n']})  [{', '.join(a['parts'])}]"))
    if gs and gc:
        se = se_unpaired(gs, gc)
        print(f"  GS - GC: {gs['p'] - gc['p']:+.4f} (se {se:.4f}; DESCRIPTIVE -- vs SH is saturated)")
    print("\nNOT HERE: the BIG-BUDGET leg (G4, on FP@500's calibrated FP@N after fp-speedup's calibration) and the anchors.")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(out, f, indent=1, default=str)
        print(f"-> {args.json_out}")


if __name__ == "__main__":
    main()

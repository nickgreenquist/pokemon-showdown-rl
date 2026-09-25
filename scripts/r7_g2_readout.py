#!/usr/bin/env python
"""R7 G2's readout (configs/eval/r7_g2.yaml, r3: off FP@N 25k/12k), computed from disk and never
typed (docs/landmines.md: a number typed from memory into a readout is the one nobody re-checks).

    python scripts/r7_g2_readout.py [--results results/r7_g2] [--json-out results/r7_g2/readout.json]

Inputs, all under <results>: g2g.json / g2l.json (the seat JSONs); g2g.runner.json / g2l.runner.json
(the runner's crash-forfeit count and scripts/fp_arm_counters.py's fpn_counters_ok); g2g.fp.stdout /
g2l.fp.stdout (Foul Play's own `Winner:` lines, for the two-tally gate); g2g.runner.log /
g2l.runner.log (the runner's budget read-back); parallel.log (the scheduler's launch order); and
g_matched_greedy.log (tests/test_lop.py at the launch commit). The branch text is printed VERBATIM
from the pre-reg; the gate thresholds are the pre-reg's G_OPERATOR_RAN numbers.

THE READ RULE (G_RUNNER, verbatim in every runner JSON): n_eff = seat-finished minus crash_forfeits,
our_wins reduced by the same count, on BOTH arms. The primary is G2L minus G2G on n_eff with the
unpaired two-proportion se_diff: each arm is ONE object, so no seed-clustered leg exists. STRICT
boundaries: a delta EXACTLY +0.025 or EXACTLY 2*se_diff reads as NOT met. Any failed R0 gate VOIDS
the pair. G2G_SANITY is a DISCLOSURE naming both instruments and never passes or fails.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from fractions import Fraction

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINNER_RE = re.compile(r"Winner: (\S+)")
CREDIT_DELTA = Fraction(1, 40)     # +0.025, exact
SANITY_REF = {"xgr": 0.5866, "n": 3200, "instrument": "FP@20", "source": "RESULTS §35, the same object"}
# G_OPERATOR_RAN, each threshold from the pre-reg's own measurement (configs/eval/r7_g2.yaml).
OP = {"searched_frac_min": 0.5, "worlds_built_min": 0.90, "no_world_max": 0.10, "mask_mismatch_max": 0.001,
      "errors_per_world_max": 0.001, "override": (0.02, 0.20), "leaves": (400.0, 700.0)}
MAX_RELAUNCHES = 30          # G_RUNNER: ">= 30 relaunches VOIDs an arm"
BUDGET_LINE = "budget verified from foul-play's log"


def tally(fp_stdout: str) -> Counter:
    """Foul Play's own W/L/tie tally: one `Winner: <name>` per battle it finished, `Winner: None`
    is the tie. A crash-forfeit battle has no line (Foul Play died in it)."""
    c: Counter = Counter()
    if not os.path.exists(fp_stdout):
        return c
    with open(fp_stdout, "r", errors="replace") as f:
        for line in f:
            m = WINNER_RE.search(line)
            if m:
                c[m.group(1)] += 1
    return c


def neff(seat: dict, runner: dict) -> dict:
    cf = int(runner.get("crash_forfeits", 0))
    n, w = seat["battles_finished"] - cf, seat["our_wins"] - cf
    return {"n_eff": n, "wins_eff": w, "p": w / n if n > 0 else float("nan"), "crash_forfeits": cf,
            "battles_finished": seat["battles_finished"], "ties": seat.get("ties")}


def primary(g: dict, l: dict) -> dict:
    """In EXACT rational arithmetic, so the pre-reg's strict boundary holds: in floats, 1950/3200 -
    1870/3200 need not equal 0.025, and a delta EXACTLY +0.025 must read as NOT met. The 2*se_diff
    clause compares d^2 against 4*se_diff^2, which is rational too."""
    fg, fl = Fraction(g["wins_eff"], g["n_eff"]), Fraction(l["wins_eff"], l["n_eff"])
    d = fl - fg
    se2 = fg * (1 - fg) / g["n_eff"] + fl * (1 - fl) / l["n_eff"]
    if d > CREDIT_DELTA and d * d > 4 * se2:
        branch = "clears"
    elif d < -CREDIT_DELTA and d * d > 4 * se2:
        branch = "negative"
    else:
        branch = "does_not_clear"
    se = math.sqrt(float(se2))
    on_boundary = abs(d) == CREDIT_DELTA or d * d == 4 * se2
    near = on_boundary or min(abs(abs(float(d)) - float(CREDIT_DELTA)), abs(abs(float(d)) - 2 * se)) < 1e-6
    return {"p_g2g": float(fg), "n_g2g": g["n_eff"], "p_g2l": float(fl), "n_g2l": l["n_eff"], "delta": float(d),
            "se_diff": se, "z": float(d) / se if se else float("nan"), "branch": branch,
            "on_boundary": bool(on_boundary), "near_boundary": bool(near)}


def g_tally(seat: dict, ne: dict, t: Counter) -> dict:
    """Two tallies AGREEING on n_eff EXACTLY, never a subtraction: Foul Play's `Winner:` lines
    against the seat JSON after the crash-forfeit rule."""
    got = {"seat": t.get(seat["seat_username"], 0), "bot": t.get(seat["fp_username"], 0), "ties": t.get("None", 0)}
    exp = {"seat": ne["wins_eff"], "bot": seat["foulplay_wins"], "ties": seat.get("ties", 0)}
    total = sum(got.values())
    return {"ok": bool(got == exp and total == ne["n_eff"]), "json_after_rule": exp, "foul_play": got,
            "fp_total": total, "n_eff": ne["n_eff"]}


def launch_order(parallel_log: str) -> dict:
    """G_CONTROL_FIRST (r3): G2G LAUNCHED before G2L, both inside ONE scheduler session (no START
    line between the two launches)."""
    if not os.path.exists(parallel_log):
        return {"ok": False, "why": "no parallel.log"}
    lines = open(parallel_log).read().splitlines()
    idx = {a: max((i for i, s in enumerate(lines) if f" {a} LAUNCHED " in s), default=None) for a in ("G2G", "G2L")}
    ig, il = idx["G2G"], idx["G2L"]
    if ig is None or il is None:
        return {"ok": False, "why": f"launch lines missing: {idx}"}
    lo, hi = sorted((ig, il))
    one_session = not any(" START pid " in s for s in lines[lo + 1:hi + 1])
    return {"ok": bool(ig < il and one_session), "g2g_line": lines[ig][:120], "g2l_line": lines[il][:120],
            "one_scheduler_session": one_session}


def matched_greedy(log: str, launch_sha: str | None) -> dict:
    """G_MATCHED_GREEDY: tests/test_lop.py at the launch commit, every test PASSED, NONE SKIPPED."""
    if not os.path.exists(log):
        return {"ok": False, "why": f"missing {log}"}
    text = open(log).read()
    summary = [s for s in text.splitlines() if re.search(r"\d+ passed", s)]
    last = summary[-1] if summary else ""
    bad = re.findall(r"(\d+) (skipped|failed|error|errors|deselected|xfailed|xpassed)", last)
    sha_ok = bool(launch_sha) and launch_sha in text
    return {"ok": bool(last and not bad and sha_ok), "summary": last.strip("= "), "launch_sha_in_log": sha_ok}


def operator_ran(l: dict) -> dict:
    dec = l.get("search/decisions") or 0
    tried = 8 * max(dec - (l.get("lop/forced") or 0), 0)        # the L-op adds B=8 per non-forced decision
    checks = {
        "searched_frac": ((l.get("search/searched") or 0) / dec if dec else 0.0, ">=", OP["searched_frac_min"]),
        "worlds_built_rate": (l.get("lop/worlds_built_rate"), ">=", OP["worlds_built_min"]),
        "no_world_rate": (l.get("lop/no_world_rate"), "<=", OP["no_world_max"]),
        "mask_mismatch_rate": (l.get("lop/mask_mismatch_rate"), "<=", OP["mask_mismatch_max"]),
        "errors_per_world": ((l.get("lop/errors") or 0) / tried if tried else None, "<=", OP["errors_per_world_max"]),
        "override_rate": (l.get("search/override_rate"), "in", OP["override"]),
        "leaves_mean": (l.get("lop/leaves_mean"), "in", OP["leaves"]),
    }
    res, ok = {}, True
    for k, (v, op, thr) in checks.items():
        if v is None:
            good = False
        elif op == ">=":
            good = v >= thr
        elif op == "<=":
            good = v <= thr
        else:
            good = thr[0] <= v <= thr[1]
        res[k] = {"value": v, "rule": f"{op} {thr}", "ok": bool(good)}
        ok &= bool(good)
    res["error_types"] = l.get("lop/error_types")
    res["refused"] = l.get("lop/refused")
    return {"ok": bool(ok), **res}


def gates(R: str, seats: dict, runners: dict, ne: dict, tallies: dict) -> dict:
    g, l = seats["G2G"], seats["G2L"]
    out = {}
    fpn = {}
    for a in ("G2G", "G2L"):
        rlog = os.path.join(R, f"{a.lower()}.runner.log")
        budget = [s for s in open(rlog).read().splitlines() if BUDGET_LINE in s] if os.path.exists(rlog) else []
        fpn[a] = {"fpn_counters_ok": runners[a].get("fpn_counters_ok"), "why": runners[a].get("fpn_counters_why"),
                  "iters_exact_rate": runners[a].get("fp_iters_exact_rate"),
                  "budget_line": budget[-1][-140:] if budget else None,
                  "budget_25k_12k": bool(budget) and "search_iterations=25000/12000" in budget[-1]}
    out["G_FPN_COUNTERS"] = {"ok": all(v["fpn_counters_ok"] is True and v["budget_25k_12k"] for v in fpn.values()), **fpn}
    out["G_CONTROL_FIRST"] = launch_order(os.path.join(R, "parallel.log"))
    same = {k: (g.get(k), l.get(k)) for k in ("rl_package", "rl_git_sha", "rl_git_dirty", "launch_git_sha")}
    out["G_SAME_PROGRAM"] = {"ok": bool(g.get("rl_package") and g.get("rl_package") == l.get("rl_package")
                                        and g.get("rl_git_sha") and g.get("rl_git_sha") == l.get("rl_git_sha")
                                        and g.get("rl_git_dirty") is False and l.get("rl_git_dirty") is False
                                        and g.get("rl_git_sha") == g.get("launch_git_sha") == l.get("launch_git_sha")),
                             **same}
    run = {}
    for a in ("G2G", "G2L"):
        r, s = runners[a], seats[a]
        run[a] = {"relaunches": r.get("relaunches"), "max_relaunches": r.get("max_relaunches"),
                  "void_too_many_crashes": r.get("void_too_many_crashes"),
                  "all_challenges_resolved": s.get("gate_all_challenges_resolved"),
                  "tally_agrees": tallies[a]["ok"], "mask_desyncs": s.get("mask_desyncs")}
    out["G_RUNNER"] = {"ok": all((v["relaunches"] or 0) < MAX_RELAUNCHES and not v["void_too_many_crashes"]
                                 and v["all_challenges_resolved"] is True and v["tally_agrees"] for v in run.values()),
                       **run}
    out["G_OPERATOR_RAN"] = operator_ran(l)
    out["G_SESSION"] = {"ok": bool(g.get("prereg_sha256") and g.get("prereg_sha256") == l.get("prereg_sha256")),
                        "prereg_sha256": (g.get("prereg_sha256"), l.get("prereg_sha256")),
                        "note": "the delta is G2L - G2G only; no banked number enters"}
    ties_ok = all(abs(s["our_win_rate"] - s["our_wins"] / s["battles_finished"]) < 1e-12 for s in (g, l))
    out["G_TIES"] = {"ok": bool(ties_ok), "ties": {"G2G": g.get("ties"), "G2L": l.get("ties")}}
    out["G_CONCURRENCY"] = {"ok": all((s.get("concurrent_decision_rate") or 0.0) <= 0.01 for s in (g, l)),
                            "concurrent_decision_rate": {a: seats[a].get("concurrent_decision_rate") for a in seats},
                            "max_concurrent_live_battles_DISCLOSED": {a: seats[a].get("max_concurrent_live_battles") for a in seats}}
    return out


def render(seats, ne, prim, gg, mg, rule) -> str:
    g, l = seats["G2G"], seats["G2L"]
    void = [k for k, v in {**gg, "G_MATCHED_GREEDY": mg}.items() if not v["ok"]]
    L = ["| arm | win rate (n_eff) | n_eff | crash forfeits | ties | override | lop/leaves_mean | seat ms p50 / p99 | decisions/s |",
         "|---|---|---|---|---|---|---|---|---|"]
    for a, s in (("G2G (committee greedy)", g), ("G2L (L-op, B 8 x k 4 x S 2)", l)):
        n = ne["G2G" if a.startswith("G2G") else "G2L"]
        L.append(f"| {a} | {n['p']:.4f} | {n['n_eff']} | {n['crash_forfeits']} | {n['ties']} | "
                 f"{s.get('search/override_rate', '—') if a.startswith('G2L') else '—'} | "
                 f"{s.get('lop/leaves_mean', '—') if a.startswith('G2L') else '—'} | "
                 f"{s.get('seat/decision_ms_p50', float('nan')):.1f} / {s.get('seat/decision_ms_p99', float('nan')):.1f} | "
                 f"{s.get('seat/decisions_per_sec', float('nan')):.1f} |")
    L += ["", f"delta (G2L - G2G, off FP@N 25k/12k): **{prim['delta']:+.4f}**; se_diff (unpaired binomial, "
              f"{prim['n_g2l']} vs {prim['n_g2g']}): {prim['se_diff']:.4f}; z {prim['z']:+.2f}; 2*se_diff "
              f"{2 * prim['se_diff']:.4f}. Crash forfeits G2L - G2G: "
              f"{ne['G2L']['crash_forfeits'] - ne['G2G']['crash_forfeits']:+d}."
              + (" WITHIN 1e-6 OF A BOUNDARY -- say so." if prim["near_boundary"] else ""), "",
          "R0 gates:"]
    for name, v in {**gg, "G_MATCHED_GREEDY": mg}.items():
        ev = {k: x for k, x in v.items() if k != "ok"}
        L.append(f"- `{name}` -- **{'PASS' if v['ok'] else 'FAIL'}**: {json.dumps(ev, default=str)}")
    L += ["", f"G2G_SANITY (DISCLOSURE ONLY, never a gate; two instruments): G2G {ne['G2G']['p']:.4f} off FP@N 25k/12k "
              f"(the R5 W committee's FIRST FP@N number) beside §35's XGR {SANITY_REF['xgr']} off FP@20 "
              f"(n {SANITY_REF['n']}). Never differenced; no pass/fail at the calibration's level CI95 [-0.026, +0.011].", ""]
    if void:
        L.append(f"**VOID** -- failed R0 gate(s) {void}: {rule['void'].strip()}")
    else:
        L.append(f"**{prim['branch'].upper().replace('_', ' ')}** -- {rule[prim['branch']].strip()}")
    L += ["", "Disclosures: FP@N 25k/12k with its calibration (two seats vs FP@20, NON-REJECTION, offset CI95 "
              "[-0.026, +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054): G2's primary is a gap, so this is a "
              "verdict off FP@N, never a translated FP@20 result. The equivalence test is weakly powered, and the point "
              "estimate flatters us. Measured beside the R7 fleet: the seat ms and decisions/s are load-inflated, and "
              "the per-decision budget is the leaves. Every seat sends /timer on."]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(REPO, "results/r7_g2"))
    ap.add_argument("--prereg", default=os.path.join(REPO, "configs/eval/r7_g2.yaml"))
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    R = args.results
    seats, runners = {}, {}
    for a in ("G2G", "G2L"):
        for d, suffix in ((seats, ".json"), (runners, ".runner.json")):
            p = os.path.join(R, a.lower() + suffix)
            if not os.path.exists(p):
                sys.exit(f"missing {p} -- the arm has not finished; nothing to read")
            d[a] = json.load(open(p))
    rule = yaml.safe_load(open(args.prereg))["decision_rule"]
    ne = {a: neff(seats[a], runners[a]) for a in seats}
    tallies = {a: g_tally(seats[a], ne[a], tally(os.path.join(R, f"{a.lower()}.fp.stdout"))) for a in seats}
    prim = primary(ne["G2G"], ne["G2L"])
    gg = gates(R, seats, runners, ne, tallies)
    mg = matched_greedy(os.path.join(R, "g_matched_greedy.log"), seats["G2G"].get("launch_git_sha"))
    print(render(seats, ne, prim, gg, mg, rule))
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"primary": prim, "n_eff": ne, "gates": gg, "G_MATCHED_GREEDY": mg, "tallies": tallies,
                       "sanity_disclosure": {"g2g_fpn": ne["G2G"]["p"], **SANITY_REF}}, f, indent=2, default=str)
        print(f"\n-> {args.json_out}")


if __name__ == "__main__":
    main()

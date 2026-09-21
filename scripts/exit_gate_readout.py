#!/usr/bin/env python
"""The exit gate's readout, computed from disk and never typed (docs/landmines.md: a number
typed from memory into a readout is the one nobody re-checks).

    python scripts/exit_gate_readout.py [--results results/exit_gate_r5] [--json-out ...]

Inputs: <results>/xgr.json and <results>/xtg9.json (the two arms of configs/eval/exit_gate_r5.yaml),
their .fp.stdout files (Foul Play's own `Winner:` lines, the G2 cross-check), their .runner.log
files (start timestamps, G_CONTROL_FIRST) and the pre-reg itself (the rule is printed VERBATIM
from the yaml, not restated). Output: the markdown block that fills readouts/EXIT_GATE_R5_READOUT.md
-- the results row, delta / se_diff / z under the pre-reg's binomial rule, the five R0 gates
with their evidence lines, the G2 tally, the realized change rate computed the way
docs/landmines.md prescribes (a tree arm's `search/override_rate` is None by construction), the
launch-sha disclosure when the block spans commits, and the verdict.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINNER_RE = re.compile(r"Winner: (\S+)")
STAMP_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\]")
EXPERT_KEYS = ("tree/kl_pi_prior", "tree/pi_top1", "tree/argmax_moved", "search/ms_mean")
CREDIT_DELTA = 0.025      # the pre-reg's clears line: delta >= +0.025 AND >= 2*se_diff
BUDGET_RATIO_MIN = 0.5    # G_BUDGET_REALIZED: within ~2x of the screen's ms/decision


def tally(fp_stdout: str) -> Counter:
    """Foul Play's own W/L/tie tally from its stdout: one `Winner: <name>` per finished
    battle, `Winner: None` IS the tie (scripts/ch5_r1_grade.py). Streamed: the files are ~0.5-0.8 GB."""
    c: Counter = Counter()
    with open(fp_stdout, "r", errors="replace") as f:
        for line in f:
            m = WINNER_RE.search(line)
            if m:
                c[m.group(1)] += 1
    return c


def g2(report: dict, t: Counter) -> dict:
    """Two tallies AGREEING, never a subtraction (scripts/ch3_r4_fp_runner.sh)."""
    seat, bot = report["seat_username"], report["fp_username"]
    exp = {"seat": report["our_wins"], "bot": report["foulplay_wins"], "ties": report["ties"]}
    got = {"seat": t.get(seat, 0), "bot": t.get(bot, 0), "ties": t.get("None", 0)}
    ok = exp == got and sum(got.values()) == report["battles_finished"]
    return {"ok": bool(ok), "seat_json_vs_fp": (exp["seat"], got["seat"]),
            "bot_json_vs_fp": (exp["bot"], got["bot"]), "ties_json_vs_fp": (exp["ties"], got["ties"]),
            "fp_total": sum(got.values()), "battles_finished": report["battles_finished"]}


def primary(a: dict, b: dict) -> dict:
    """XTG9 minus XGR under the pre-reg's rule: unpaired two-proportion (binomial) se_diff,
    one arm per cell so no seed-clustered leg exists."""
    pa, na = a["our_win_rate"], a["battles_finished"]
    pb, nb = b["our_win_rate"], b["battles_finished"]
    d = pb - pa
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    clears = (d >= CREDIT_DELTA) and (d >= 2 * se)
    near_boundary = abs(d - CREDIT_DELTA) < 1e-6 or abs(d - 2 * se) < 1e-6
    return {"p_control": pa, "n_control": na, "p_tree": pb, "n_tree": nb, "delta": d, "se_diff": se,
            "z": d / se if se else float("nan"), "clears": bool(clears), "near_boundary": bool(near_boundary)}


def change_rate(b: dict) -> dict:
    """The realized change rate of a tree arm, per docs/landmines.md: `search/override_rate` is
    None by construction (gated on a margin_delta the tree does not use); the quantity is
    flips / (decisions - placeholder_skips), and overrides / the same denominator beside it."""
    dec, skips = b.get("search/decisions"), b.get("search/placeholder_skips")
    if dec is None or skips is None:
        return {"available": False}
    den = max(dec - skips, 1)
    return {"available": True, "denominator": den, "decisions": dec, "placeholder_skips": skips,
            "flips": b.get("search/flips"), "overrides": b.get("search/overrides"),
            "flip_rate": (b.get("search/flips") or 0) / den, "override_rate": (b.get("search/overrides") or 0) / den,
            "override_rate_field": b.get("search/override_rate")}


def first_stamp(runner_log: str) -> str | None:
    if not os.path.exists(runner_log):
        return None
    with open(runner_log) as f:
        for line in f:
            m = STAMP_RE.match(line)
            if m:
                return m.group(1)
    return None


def gates(a: dict, b: dict, a_json: str, b_json: str, a_runner_log: str, b_runner_log: str,
          comparator_ms: float) -> dict:
    out = {}
    missing = [k for k in EXPERT_KEYS if b.get(k) is None]
    out["G_EXPERT_REPORTED"] = {"ok": not missing, "missing": missing,
                                "values": {k: b.get(k) for k in EXPERT_KEYS}}
    ms = b.get("search/ms_mean")
    ratio = (ms / comparator_ms) if (ms is not None and comparator_ms) else None
    out["G_BUDGET_REALIZED"] = {"ok": bool(ratio is not None and ratio >= BUDGET_RATIO_MIN),
                                "ms_mean": ms, "comparator_ms": comparator_ms, "ratio": ratio,
                                "note": ("above 2x the screen's ms/decision -- slower than the screen, not the failure mode the gate names"
                                         if ratio is not None and ratio > 2.0 else "")}
    sa, sb = first_stamp(a_runner_log), first_stamp(b_runner_log)
    ma = os.path.getmtime(a_json) if os.path.exists(a_json) else None
    mb = os.path.getmtime(b_json) if os.path.exists(b_json) else None
    out["G_CONTROL_FIRST"] = {"ok": bool(sa and sb and sa < sb and ma is not None and mb is not None and ma < mb),
                              "control_started": sa, "tree_started": sb,
                              "control_json_mtime_before_tree": (ma is not None and mb is not None and ma < mb)}
    out["G_SESSION"] = {"ok": a.get("prereg_sha256") == b.get("prereg_sha256"),
                        "prereg_sha256_equal": a.get("prereg_sha256") == b.get("prereg_sha256"),
                        "note": "the delta is XTG9 - XGR only; no banked number enters"}
    ties_nonwins = abs(a["our_win_rate"] - a["our_wins"] / a["battles_finished"]) < 1e-12 and \
        abs(b["our_win_rate"] - b["our_wins"] / b["battles_finished"]) < 1e-12
    out["G_TIES"] = {"ok": bool(ties_nonwins), "ties": {"XGR": a.get("ties"), "XTG9": b.get("ties")},
                     "note": "our_win_rate = our_wins / battles_finished on both arms (ties are non-wins)"}
    return out


def sha_span(a: dict, b: dict) -> dict:
    """A running block imports the working tree: each arm is a fresh process. Report both
    launch shas and, when they differ, what changed under rl/ and the seat script between them."""
    sa, sb = a.get("launch_git_sha"), b.get("launch_git_sha")
    out = {"control_launch_sha": sa, "tree_launch_sha": sb, "spans_commits": bool(sa and sb and sa != sb)}
    if out["spans_commits"]:
        try:
            diff = subprocess.run(["git", "diff", "--stat", sa, sb, "--", "rl/", "scripts/ch3_fp_h2h.py"],
                                  cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
        except Exception as e:  # noqa: BLE001
            diff = f"(git diff failed: {e})"
        out["diff_stat_rl_and_seat"] = diff or "(no change under rl/ or scripts/ch3_fp_h2h.py)"
    return out


def fmt(x, nd=4):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def render(a: dict, b: dict, prim: dict, g: dict, g2a: dict, g2b: dict, cr: dict, span: dict, rule: dict) -> str:
    L = []
    L.append("| arm | win rate | n | ties | search/ms_mean | tree/kl_pi_prior | tree/pi_top1 | tree/argmax_moved | search/overrode |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    L.append(f"| XGR (greedy control) | {fmt(a['our_win_rate'])} | {a['battles_finished']} | {a.get('ties')} | — | — | — | — | — |")
    over = f"{fmt(cr['override_rate'])} ({cr['overrides']}/{cr['denominator']})" if cr.get("available") else "—"
    L.append(f"| XTG9 (tree@900) | {fmt(b['our_win_rate'])} | {b['battles_finished']} | {b.get('ties')} | "
             f"{fmt(b.get('search/ms_mean'), 1)} | {fmt(b.get('tree/kl_pi_prior'))} | {fmt(b.get('tree/pi_top1'), 3)} | "
             f"{fmt(b.get('tree/argmax_moved'), 3)} | {over} |")
    L.append("")
    L.append(f"delta (XTG9 − XGR): **{prim['delta']:+.4f}**; se_diff (unpaired two-proportion, "
             f"{prim['n_tree']} vs {prim['n_control']}): {prim['se_diff']:.4f}; z: {prim['z']:+.2f}. "
             f"Rule: delta >= +0.025 AND >= 2·se_diff (2·se_diff = {2 * prim['se_diff']:.4f}) → "
             f"{'MET' if prim['clears'] else 'NOT MET'}"
             + (" — WITHIN 1e-6 OF A BOUNDARY; say so." if prim["near_boundary"] else "") + ".")
    if cr.get("available"):
        L.append(f"Realized change rate (docs/landmines.md: `search/override_rate` is `{cr['override_rate_field']}` by construction on a "
                 f"tree arm): flips/(decisions − placeholder_skips) = {cr['flips']}/{cr['denominator']} = {cr['flip_rate']:.4f}; "
                 f"overrides on the same denominator = {cr['override_rate']:.4f}; decisions {cr['decisions']}, skips {cr['placeholder_skips']}.")
    L.append("")
    L.append("R0 gates (evidence from the JSONs and the runner logs):")
    for name, gg in g.items():
        ev = {k: v for k, v in gg.items() if k != "ok"}
        L.append(f"- `{name}` — **{'PASS' if gg['ok'] else 'FAIL'}**: {json.dumps(ev, default=str)}")
    L.append("")
    L.append("G2 (two tallies agreeing, never a subtraction — the seat's JSON against Foul Play's own `Winner:` lines):")
    for name, x in (("XGR", g2a), ("XTG9", g2b)):
        L.append(f"- {name}: **{'AGREE' if x['ok'] else 'DISAGREE'}** seat {x['seat_json_vs_fp']}, bot {x['bot_json_vs_fp']}, "
                 f"ties {x['ties_json_vs_fp']}, FP total {x['fp_total']} vs battles_finished {x['battles_finished']}")
    L.append("")
    L.append(f"Launch shas: control `{span['control_launch_sha']}`, tree `{span['tree_launch_sha']}` — "
             + ("the block SPANS COMMITS (each arm imports the working tree at its launch); diff under rl/ and the seat script:\n"
                f"```\n{span['diff_stat_rl_and_seat']}\n```" if span["spans_commits"] else "one commit, no span."))
    L.append("")
    L.append("Verdict under the pre-reg's rule, verbatim:")
    key = "clears" if prim["clears"] else "does_not_clear"
    L.append(f"- **{key.upper().replace('_', ' ')}** — {rule[key].strip()}")
    L.append("")
    L.append("Disclosures: FP@20's equivalence test is weakly powered and its point estimate flatters us; "
             "binomial se governs (one arm per cell); never differenced against a banked number.")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(REPO, "results/exit_gate_r5"))
    ap.add_argument("--prereg", default=os.path.join(REPO, "configs/eval/exit_gate_r5.yaml"))
    ap.add_argument("--control", default="xgr")
    ap.add_argument("--tree", default="xtg9")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--skip-tally", action="store_true", help="skip the G2 pass over the FP stdouts")
    args = ap.parse_args()
    R = args.results
    a_json, b_json = os.path.join(R, f"{args.control}.json"), os.path.join(R, f"{args.tree}.json")
    for p in (a_json, b_json):
        if not os.path.exists(p):
            sys.exit(f"missing {p} -- the arm has not finished; nothing to read")
    a, b = json.load(open(a_json)), json.load(open(b_json))
    pre = yaml.safe_load(open(args.prereg))
    rule = pre["decision_rule"]
    comparator_ms = float(pre["comparators"]["bs9_screen"]["ms_per_decision"])
    prim = primary(a, b)
    g = gates(a, b, a_json, b_json, os.path.join(R, f"{args.control}.runner.log"),
              os.path.join(R, f"{args.tree}.runner.log"), comparator_ms)
    if args.skip_tally:
        g2a = g2b = {"ok": False, "seat_json_vs_fp": None, "bot_json_vs_fp": None, "ties_json_vs_fp": None,
                     "fp_total": None, "battles_finished": None, "skipped": True}
    else:
        g2a = g2(a, tally(os.path.join(R, f"{args.control}.fp.stdout")))
        g2b = g2(b, tally(os.path.join(R, f"{args.tree}.fp.stdout")))
    cr = change_rate(b)
    span = sha_span(a, b)
    md = render(a, b, prim, g, g2a, g2b, cr, span, rule)
    print(md)
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump({"primary": prim, "gates": g, "g2": {"XGR": g2a, "XTG9": g2b}, "change_rate": cr,
                       "sha_span": span, "sources": {"control": a_json, "tree": b_json, "prereg": args.prereg}},
                      f, indent=2, default=str)
        print(f"\n-> {args.json_out}")


if __name__ == "__main__":
    main()

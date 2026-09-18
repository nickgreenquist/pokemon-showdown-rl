#!/usr/bin/env python
"""IDEAS 2.10 + 8.5: did the honest backup pay, and does the committee know
WHERE to spend the budget?

    python scripts/backup_gate_readout.py

Reads results/backup_gate_r5/*.json against configs/eval/backup_gate_r5.yaml.
Every delta is unpaired two-proportion (SEEDS DO NOT PAIR BATTLES), every
number is off FP@20 with both disclosures travelling, and the bar is GREEDY.
"""
import json
import math
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results/backup_gate_r5"
PR = yaml.safe_load(open(REPO / "configs/eval/backup_gate_r5.yaml"))
C = PR["comparators"]


def g(tag):
    p = RES / f"{tag.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def num(d, key, default=float("nan")):
    v = d.get(key) if d else None
    return float(v) if isinstance(v, (int, float)) else default


def _rl_diff(shas) -> str:
    """Did `rl/` change across the commits this block spans?

    "The block spans commits" is only alarming if the code the SEAT IMPORTS
    moved. Doc, test and readout commits are the common case and they change
    nothing. This answers the actionable half automatically.

    CAVEAT it cannot fix: an arm whose stamp is FINISH-time may have LAUNCHED
    at an earlier commit, so an empty diff across the stamps is necessary and
    not sufficient for those arms. The label above says which ones.
    """
    import subprocess

    ordered = []
    for sha in shas:
        r = subprocess.run(["git", "rev-list", "--count", sha],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            ordered.append((int(r.stdout.strip()), sha))
    if len(ordered) < 2:
        return "    (cannot order the commits; check by hand)"
    ordered.sort()
    lo, hi = ordered[0][1], ordered[-1][1]
    r = subprocess.run(["git", "diff", "--stat", f"{lo}..{hi}", "--", "rl/"],
                       capture_output=True, text=True)
    out = r.stdout.strip()
    if not out:
        return (f"    rl/ is IDENTICAL across {lo[:12]}..{hi[:12]} -- the arms ran\n"
                "    the same searcher and the spanning commits were docs, tests or\n"
                "    tooling. (Necessary, not sufficient, for finish-time stamps.)")
    return ("    rl/ CHANGED across the block:\n      "
            + "\n      ".join(out.splitlines())
            + "\n    Difference these arms only after saying what that diff does\n"
              "    to the search path.")


def code_provenance(data):
    """Did every arm in this block run the SAME CODE?

    Each arm is a fresh process that imports the WORKING TREE, so a block
    launched before an edit and finished after one is comparing two programs.
    `launch_git_sha` has been stamped into every arm's JSON since CH4 R1's G8
    block and nothing has ever read it (docs/CLEANUP.md L5). This reads it. It
    does not refuse -- whether a spanning block is VOID is a maintainer ruling
    -- but a reader is told rather than having to think of the question.

    THE FIELD WAS MIS-NAMED UNTIL 2026-09-18: it was read AFTER the battles, so
    older arms carry the tree state at COMPLETION under the launch name. An arm
    with no `finish_git_sha` is one of those and is labelled as such, because
    comparing a finish sha against a launch sha proves nothing either way.
    """
    rows = {t: d for t, d in data.items() if d}
    if not rows:
        return
    print("\n## Code provenance\n")
    distinct, legacy = set(), []
    for t, d in rows.items():
        start, end = d.get("launch_git_sha"), d.get("finish_git_sha")
        if end is None:
            # Written before 2026-09-18: `launch_git_sha` was read AFTER the
            # battles, so it is the FINISH state under the launch name. Say so
            # rather than silently comparing it against a real launch sha.
            legacy.append(t)
            print(f"  {t:4s} {(start or 'UNSTAMPED')[:12]}  (FINISH-time sha, "
                  f"mis-named: this arm predates the fix)")
        else:
            span = "" if start == end else f" -> {end[:12]} SPANNED A COMMIT MID-ARM"
            print(f"  {t:4s} {(start or 'UNSTAMPED')[:12]}{span}")
        if start:
            distinct.add(start)
    if len(distinct) > 1:
        print(f"\n  THIS BLOCK SPANS {len(distinct)} COMMITS. Every arm is a fresh")
        print("  process importing the working tree, so the arms ran different")
        print("  programs. What matters is whether the SEARCHER moved:")
        print(_rl_diff(distinct))
    elif not legacy:
        print("\n  One commit across every arm.")
    if legacy:
        print(f"\n  {len(legacy)} arm(s) carry a FINISH-time sha under the launch")
        print("  name, so this block's shas are not directly comparable to each")
        print("  other. Read the commit LOG against the arm's wall-clock window.")


def cmp(lab, a, b, na=None, nb=None):
    """a and b are (rate, n) pairs or arm dicts."""
    pa, na = (a["our_win_rate"], a["battles_finished"]) if isinstance(a, dict) else (a, na)
    pb, nb = (b["our_win_rate"], b["battles_finished"]) if isinstance(b, dict) else (b, nb)
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    print(f"  {lab:52s} {pa:.4f} - {pb:.4f} = {pa - pb:+.4f} at {abs(pa - pb) / se:.2f} se")


def main():
    arms = {a: g(a) for a in PR["phases"]["R"]}
    print("=" * 78)
    print("TWO FIXES, ONE SESSION -- an honest depth-2 backup (IDEAS 2.10) and a")
    print("budget spent where the committee is split (IDEAS 8.5). off FP@20, R5")
    print("committee. Hacking run, CREDITS NOTHING. THE BAR IS GREEDY.")
    print("=" * 78)

    print("\n## R0 GATES -- did the dials FIRE? A failed gate VOIDS its arm.\n")
    ok = True
    for tag in ("B2R", "B2O"):
        d = arms.get(tag)
        if not d:
            print(f"  {tag:4s} PENDING"); continue
        opp, drop = num(d, "depth2/opp_replies_mean"), num(d, "depth2/minimax_drop")
        want = tag == "B2R"
        fired = (opp > 1.2 and drop > 0) if want else (opp <= 1.05)
        ok &= fired
        print(f"  {tag:4s} opp_replies {opp:.2f}  minimax_drop {drop:.4f}  "
              f"fired_rate {num(d, 'depth2/fired_rate'):.3f}  "
              f"{'OK' if fired else 'VOID -- the backup the arm claims did not run'}")
    for tag in ("DGV", "DRV"):
        d = arms.get(tag)
        if not d:
            print(f"  {tag:4s} PENDING"); continue
        r = num(d, "disagree/search_rate")
        fired = 0.05 < r < 0.95
        ok &= fired
        print(f"  {tag:4s} search_rate {r:.4f}  "
              f"score_mean {num(d, 'disagree/score_mean'):.4f}  "
              f"{'OK' if fired else 'VOID -- 1.0 is uniform dose, 0.0 is greedy'}")
    if arms.get("B2R") and arms.get("B2O"):
        cap = float(PR["arms"]["B2R"]["depth2"]["cap"])
        gr, go = (num(arms[t], "depth2/grandchildren_per_decision") for t in ("B2R", "B2O"))
        binds = gr >= 0.5 * cap
        print(f"  CAP  B2R {gr:.0f} gc/decision vs B2O {go:.0f}, cap {cap:.0f}  "
              f"{'BINDS -- the arms differ in how many of OUR replies they saw' if binds else 'OK'}")
    if arms.get("DGV") and arms.get("DRV"):
        gap = abs(num(arms["DGV"], "disagree/search_rate")
                  - num(arms["DRV"], "disagree/search_rate"))
        ok &= gap <= 0.03
        print(f"  RATE MATCH |DGV - DRV| = {gap:.4f} "
              f"{'OK' if gap <= 0.03 else 'UNMATCHED -- DGV-DRV measures the FRACTION, not the SELECTION'}")
    for tag in ("B2R", "B2O"):
        if arms.get(tag) and arms.get("D1O"):
            gap = abs(num(arms[tag], "search/override_rate")
                      - num(arms["D1O"], "search/override_rate"))
            ok &= gap <= 0.03
            print(f"  OVERRIDE MATCH |{tag} - D1O| = {gap:.4f} "
                  f"{'OK' if gap <= 0.03 else 'UNMATCHED -- this is the 2026-09-17 artifact again'}")
    if arms.get("D1O"):
        # THE TARGET CAME FROM ANOTHER SESSION, and the realized rate drifts.
        # D1O is the same configuration as §24's CN1 (dose M, delta 0.05, open
        # gate); CN1 realized 0.1933 and the pin used that as B2R's target. If
        # D1O's own rate differs, the match is to a banked number rather than to
        # the control in front of it -- disclosed, never re-pinned after a win
        # rate is visible. Next block: run the CONTROL FIRST and pin to its
        # realized rate (docs/landmines.md).
        d1 = num(arms["D1O"], "search/override_rate")
        drift = d1 - float(C["target_override"])
        print(f"  TARGET DRIFT   D1O realized {d1:.4f} vs the banked target "
              f"{C['target_override']:.4f} -> {drift:+.4f}"
              f"{'' if abs(drift) < 0.015 else '  (the match is to a BANKED rate)'}")

    code_provenance(arms)
    print("\n## The arms\n")
    labels = {"D1O": "depth 1, gate open (the control)",
              "B2O": "depth 2, OLD pinned backup",
              "B2R": "depth 2, opp_k minimax backup",
              "DGV": "gated on committee votes (dose M)",
              "DRV": "gated by a COIN at the same rate (dose M)",
              "DUM": "ungated, every decision (dose M; D1O's replicate)",
              "GC":  "GREEDY anchor, this block"}
    for tag, lab in labels.items():
        d = arms.get(tag)
        if not d:
            print(f"  {tag:4s} {lab:42s} PENDING"); continue
        # DECISIONS PER BATTLE, not just a rate: §24's finding is that at a
        # ~6.5% override the search changes ~2 decisions of a 30-turn battle,
        # which mechanically bounds what any leaf value can be worth.
        searched = (d.get("search/decisions") or 0) - (d.get("search/placeholder_skips") or 0)
        rate = num(d, "search/override_rate", 0.0)
        per_battle = rate * searched / max(d["battles_finished"], 1)
        print(f"  {tag:4s} {lab:42s} {d['our_win_rate']:.4f} "
              f"n={d['battles_finished']:<5d} ms {num(d, 'search/ms_mean'):6.1f} "
              f"override {rate:.4f} = {per_battle:.1f} changed decisions/battle")

    if arms.get("D1O") and arms.get("DUM"):
        floor = abs(arms["D1O"]["our_win_rate"] - arms["DUM"]["our_win_rate"])
        print(f"\n  THIS BLOCK'S REALIZED NOISE FLOOR (D1O vs DUM, the same "
              f"configuration on two pairs): {floor:.4f}")
        print("  Read every delta below against THAT, not against the binomial.")

    print("\n## HALF ONE -- IDEAS 2.10, does an honest backup rescue depth 2?\n")
    # THE DECLARED PRIMARY IS THE MISMATCHED ONE. B2O's delta was hardcoded from
    # §22's D2N rather than swept, and realized 0.1322 here against B2R's ~0.197
    # -- see the DESIGN ERROR block in the config. The direction is stated
    # because it is asymmetric, not because it excuses anything.
    if arms.get("B2R") and arms.get("B2O"):
        g = abs(num(arms["B2R"], "search/override_rate")
                - num(arms["B2O"], "search/override_rate"))
        cmp("B2R - B2O  the declared FIX comparison", arms["B2R"], arms["B2O"])
        if g > 0.03:
            better = arms["B2R"]["our_win_rate"] > arms["B2O"]["our_win_rate"]
            print(f"       ^ OVERRIDE RATES DIFFER BY {g:.4f} -- B2R acts "
                  f"{'MORE' if num(arms['B2R'],'search/override_rate') > num(arms['B2O'],'search/override_rate') else 'LESS'} often.")
            print("         §24 measured that for the OLD backup acting MORE is WORSE, so the")
            print("         mismatch is CONSERVATIVE for the fix: B2R > B2O would be a strong")
            print("         result DESPITE the rate; B2R < B2O is UNINTERPRETABLE.")
            print(f"         Here B2R is {'ABOVE' if better else 'BELOW'} B2O, so this line "
                  f"{'CARRIES' if better else 'DOES NOT CARRY'} a verdict.")
    if arms.get("B2R") and arms.get("D1O"):
        cmp("B2R - D1O  THE MATCHED PRIMARY (|d| 0.027)", arms["B2R"], arms["D1O"])
    if arms.get("B2O") and arms.get("D1O"):
        cmp("B2O - D1O  the §24 finding, re-drawn here", arms["B2O"], arms["D1O"])
    if arms.get("B2O"):
        cmp("B2O - D2N (§22's banked open-gate depth 2)", arms["B2O"],
            C["d2n"]["rate"], nb=C["d2n"]["n"])

    print("\n## HALF TWO -- IDEAS 8.5, where should the budget go?\n")
    if arms.get("DGV") and arms.get("DRV"):
        cmp("DGV - DRV  SELECTION (does the committee know where?)",
            arms["DGV"], arms["DRV"])
    if arms.get("DGV") and arms.get("DUM"):
        cmp("DGV - DUM  SKIPPING (does agreeing mean it does not matter?)",
            arms["DGV"], arms["DUM"])
    if arms.get("DRV") and arms.get("DUM"):
        cmp("DRV - DUM  skipping at RANDOM, the same fraction", arms["DRV"], arms["DUM"])
    # ALL THREE ARE DOSE M, so the per-searched-decision cost must match or the
    # arms are not the same search. The saving is the RATE, and it is the
    # headline if DGV - DUM is a null.
    if arms.get("DGV") and arms.get("DUM"):
        mg, mu = num(arms["DGV"], "search/ms_mean"), num(arms["DUM"], "search/ms_mean")
        r = num(arms["DGV"], "disagree/search_rate")
        print(f"\n  per-searched-decision cost: DGV {mg:.1f} ms vs DUM {mu:.1f} ms "
              f"({'OK' if mu and abs(mg - mu) / mu < 0.15 else 'MISMATCH -- not the same search'})")
        print(f"  DGV searched {r:.1%} of decisions, so it spent ~{r:.0%} of DUM's")
        print("  search compute. A NULL above is that saving for free.")

    print("\n## Against GREEDY -- the only bar that matters\n")
    anchor = arms.get("GC")
    if anchor:
        for tag in ("D1O", "B2O", "B2R", "DGV", "DRV", "DUM"):
            if arms.get(tag):
                cmp(f"{tag} - greedy (same block)", arms[tag], anchor)
        cmp("greedy this block - greedy pooled (3 earlier blocks)",
            anchor, C["greedy"]["rate"], nb=C["greedy"]["n"])
    else:
        print("  PENDING -- the anchor is the bar, and nothing is read without it.")

    print("\n  SCOPE. A null on B2R - D1O is a null for THIS vehicle at THIS")
    print("  budget. It does not close MCTS (rl/search/tree.py is a different")
    print("  algorithm) and it does not close depth for a vehicle whose backup")
    print("  is a true minimax at every ply rather than at the last one.")
    print("=" * 78)
    if not ok:
        print("\n  AT LEAST ONE R0 GATE FAILED -- the affected arms say nothing.")


if __name__ == "__main__":
    main()

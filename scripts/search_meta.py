#!/usr/bin/env python
"""Every search arm this project has run against Foul Play, in one table.

    python scripts/search_meta.py

WHY IT DID NOT EXIST. Each block wrote its own readout and each readout compared
its arms to its own anchor, which is correct -- the session offset on the Foul
Play instruments is ~0.02 and cross-session differencing has produced a wrong
reading three times. But nothing has ever put the blocks SIDE BY SIDE, so a
question every readout raises separately has never been asked once:

    IS THERE AN OVERRIDE RATE AT WHICH SEARCH PAYS?

RESULTS §24 measured that opening the gate HURTS the one-ply matrix (our critic
-0.006, Foul Play's heuristic -0.088, depth-2 -0.052). §26 measured that the
tree's best arm acts on 11.4% of decisions and its worst on 9.3%, so the rate is
not what orders those. Those two facts only sit together in a table.

HOW IT STAYS HONEST. Every arm is reported as a DELTA AGAINST ITS OWN BLOCK'S
GREEDY ANCHOR and never against another block's number, and a block with no
anchor is listed as such rather than silently compared. That is the whole
discipline this file has to carry, because the thing it makes easy -- reading
down a column of win rates -- is the thing the session offset punishes.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# (block dir, anchor tag or None, label). The anchor is the GREEDY arm measured
# in that same block; blocks without one cannot contribute a delta.
BLOCKS = [
    ("results/depth2_r5", "g0", "JOURNEY 11.5 depth (§22)"),
    ("results/gate_r5", "gb", "the gate (§24)"),
    ("results/tree_r5", "tgr", "the tree (§26)"),
    ("results/fp500_r5", None, "FP budget (§25)"),
    ("results/backup_gate_r5", "gc", "backup + gate (running)"),
]


def load(d: Path):
    out = {}
    for p in sorted(d.glob("*.json")):
        if p.name.endswith((".runner.json",)) or p.name.startswith("smoke_"):
            continue
        try:
            out[p.stem] = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
    return out


def override(d) -> float:
    """A TREE arm reports no `search/override_rate` -- that field is gated on
    the matrix's `margin_delta` -- so fall back to flips over searched
    decisions, which is the same quantity under different bookkeeping."""
    r = d.get("search/override_rate")
    if r is not None:
        return float(r)
    dec = (d.get("search/decisions") or 0) - (d.get("search/placeholder_skips") or 0)
    if not dec:
        return float("nan")
    return (d.get("search/flips") or 0) / dec


def vehicle(d) -> str:
    # `is not None`, not truthiness: the report writes None when a vehicle is
    # OFF and a dict when it is on, and an empty dict is falsy -- so a vehicle
    # configured with defaults would label itself GREEDY. That is the same
    # shape as the unstamped-dose defect below, and it is worth not repeating.
    if d.get("search_tree") is not None:
        return "tree/" + str(d["search_tree"].get("decide", "?"))
    if d.get("search_mcts") is not None:
        return "mcts"
    if d.get("search_disagree") is not None:
        g = d["search_disagree"]
        return f"matrix+gate:{g.get('metric')}"
    if d.get("search_depth2") is not None:
        k = d["search_depth2"].get("opp_k", 1)
        return f"matrix d2 (opp_k {k})"
    if d.get("search_heuristic") is not None:
        return "matrix d1 FP-eval"
    # `search_dose` was NOT stamped on this path until 2026-09-17, so an arm
    # from before then has a null dose and would label itself GREEDY -- which is
    # exactly the defect the stamp was added for, showing up one layer higher.
    # The selector is the reliable tell: a greedy arm has no margin and no
    # override rate.
    if d.get("search_margin_delta") is not None or d.get("search/override_rate") is not None:
        return "matrix d1"
    return "GREEDY"


def se_diff(pa, na, pb, nb) -> float:
    return math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)


def _fisher_p(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact on [[a,b],[c,d]], exact and dependency-free."""
    from math import comb
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def prob(x):
        return (comb(r1, x) * comb(n - r1, c1 - x)) / comb(n, c1)
    obs = prob(a)
    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1)
                        if prob(x) <= obs + 1e-12))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-n", type=int, default=200,
                    help="screens (n=60) measure a RATE, never a win rate")
    args = ap.parse_args()

    print("=" * 96)
    print("EVERY SEARCH ARM vs FOUL PLAY, GROUPED BY BLOCK")
    print("Deltas are against THAT BLOCK'S OWN greedy anchor. Never read down the")
    print("win-rate column across blocks: the session offset is ~0.02 and has")
    print("produced a wrong reading three times.")
    print("=" * 96)
    rows = []
    for rel, anchor_tag, label in BLOCKS:
        d = REPO / rel
        if not d.exists():
            continue
        arms = load(d)
        arms = {k: v for k, v in arms.items()
                if v.get("battles_finished", 0) >= args.min_n}
        if not arms:
            continue
        anchor = arms.get(anchor_tag) if anchor_tag else None
        print(f"\n## {label}   [{rel}]"
              + ("" if anchor else "   -- NO IN-BLOCK ANCHOR, deltas withheld"))
        print(f"  {'arm':<6} {'vehicle':<22} {'n':>5} {'win':>7} {'acts on':>8} "
              f"{'/battle':>8} {'vs anchor':>11}")
        for tag, a in sorted(arms.items(), key=lambda kv: -kv[1]["our_win_rate"]):
            rate = override(a)
            dec = (a.get("search/decisions") or 0) - (a.get("search/placeholder_skips") or 0)
            per = rate * dec / max(a["battles_finished"], 1) if dec else 0.0
            if anchor is not None and a is not anchor:
                z = ((a["our_win_rate"] - anchor["our_win_rate"])
                     / se_diff(a["our_win_rate"], a["battles_finished"],
                               anchor["our_win_rate"], anchor["battles_finished"]))
                delta = f"{a['our_win_rate'] - anchor['our_win_rate']:+.4f} {abs(z):.1f}se"
            else:
                delta = "ANCHOR" if a is anchor else "--"
            print(f"  {tag:<6} {vehicle(a):<22} {a['battles_finished']:>5} "
                  f"{a['our_win_rate']:>7.4f} "
                  f"{('' if rate != rate else f'{rate:>7.1%}'):>8} {per:>8.1f} {delta:>11}")
            if anchor is not None and a is not anchor and rate == rate:
                rows.append((rate, a["our_win_rate"] - anchor["our_win_rate"],
                             vehicle(a), tag))

    if rows:
        print("\n" + "=" * 96)
        print("IS THERE AN OVERRIDE RATE AT WHICH SEARCH PAYS?")
        print("Every searched arm with an in-block anchor, sorted by how often it acted.")
        print("=" * 96)
        print(f"  {'acts on':>8} {'vs own anchor':>14}  vehicle")
        for rate, delta, veh, tag in sorted(rows):
            bar = ("+" if delta > 0 else "-") * max(1, int(abs(delta) * 200))
            print(f"  {rate:>7.1%} {delta:>+14.4f}  {veh:<22} {tag:<5} {bar}")
        pos = [r for r in rows if r[1] > 0]
        print(f"\n  {len(pos)} of {len(rows)} searched arms are above their own anchor.")
        if pos:
            print(f"  The positive ones act on "
                  f"{min(r[0] for r in pos):.1%}-{max(r[0] for r in pos):.1%} of decisions,")
            # DERIVED, NOT TYPED (2026-09-19). This sentence used to carry the
            # literal string "+, -, -, -, +, -, -, -" -- the sign pattern as it
            # stood the day it was written. Re-running on one more arm would
            # have printed a stale pattern as if it had been computed, which is
            # this week's defect class exactly.
            signs = " ".join("+" if d > 0 else "-"
                             for _, d, _, _ in sorted(rows))
            asc = all(a[1] <= b[1] for a, b in zip(sorted(rows), sorted(rows)[1:]))
            print(f"  and as the rate rises the signs run  {signs}")
            print(f"  -- {'MONOTONE in the rate' if asc else 'NOT ordered by the rate'}."
                  f" {'' if asc else 'Something other than how often the search acts is deciding.'}")
        print("\n  BY VEHICLE, which is what the rate column is hiding:")
        fam = {}
        for rate, delta, veh, tag in rows:
            key = "tree" if veh.startswith("tree") else "matrix"
            fam.setdefault(key, []).append(delta)
        for key, ds in sorted(fam.items()):
            up = sum(1 for x in ds if x > 0)
            print(f"    {key:<7} {up}/{len(ds)} above anchor   "
                  f"mean delta {sum(ds)/len(ds):+.4f}   "
                  f"range {min(ds):+.4f}..{max(ds):+.4f}")
        # DERIVED, NOT TYPED (2026-09-19): the counts and the Fisher p used to
        # be the literal strings "2-of-3 against 0-of-5" and "p~0.11".
        tre = fam.get("tree", []); mat = fam.get("matrix", [])
        ut, um = sum(1 for x in tre if x > 0), sum(1 for x in mat if x > 0)
        p = _fisher_p(ut, len(tre) - ut, um, len(mat) - um) if tre and mat else float("nan")
        if mat and um == 0:
            print("  EVERY matrix arm is below its anchor; the only arms above one are")
            print(f"  trees. That is {ut}-of-{len(tre)} against {um}-of-{len(mat)}"
                  f" -- {'suggestive, NOT significant' if p > 0.05 else 'significant'}")
        else:
            print(f"  Trees {ut}-of-{len(tre)} above anchor, matrix {um}-of-{len(mat)}"
                  f" -- {'suggestive, NOT significant' if p > 0.05 else 'significant'}")
        print(f"  (Fisher p={p:.3f}), and the vehicles also differ in evaluator, depth")
        print("  and selector. It says the VEHICLE is the axis worth a clean test,")
        print("  which is what RESULTS §26 found from inside one block.")
        print()
        print("  DO NOT QUOTE THAT p AS A RESULT, AND DO NOT READ IT AS STRENGTHENING")
        print("  AS ARMS ACCUMULATE. The unit here is an ARM, not an independent test:")
        print("   * arms enter this table because some block wanted them, never by a")
        print("     sampling scheme -- and every block that ran was a block someone")
        print("     expected to be informative;")
        print("   * REPLICATES COUNT TWICE. D1O and DUM are the SAME configuration on")
        print("     two username pairs (RESULTS §30's own noise-floor check), so the")
        print("     matrix column double-counts at least one arm;")
        print("   * the matrix family has simply been RUN MORE, so its count grows")
        print("     whether or not the underlying rate differs.")
        print("  The p was 0.107 at 8 arms and moves every time a block lands. That")
        print("  movement is accounting, not evidence. It stays DESCRIPTIVE.")
        print("\n  READ IT AS A SHAPE, NOT AS A RANKING. Every point carries its own")
        print("  binomial se (~0.02 at n=1000) and the vehicles differ, so this says")
        print("  where to look next -- never which arm is best.")


if __name__ == "__main__":
    main()

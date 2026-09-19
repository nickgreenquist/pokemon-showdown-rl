#!/usr/bin/env python
"""Does a bigger tree think harder? The MECHANISM screen for IDEAS 8.6.

    python scripts/tree_budget_readout.py

Reads `results/tree_budget_r5/*.json` against `configs/eval/tree_budget_r5.yaml`.
Phase S measures per-DECISION quantities over ~1,300 decisions per arm, so it is
far better determined than a win rate at n=40 -- and no win rate here is a read
(se 0.079).

THE QUESTION. RESULTS §26 got TG (gumbel, iters 100) to +0.0210 at 0.96 se over
an in-block greedy anchor: unresolved. Resolving it at 2 se needs n~4,375/arm,
and iters 100 is the regime where the prior dominates -- 90.9% of root visits on
^^ WITHDRAWN 2026-09-19 (RESULTS §32): the 90.9% was ONE smoke decision. Measured over 1,107 searched decisions at iters 100 (results/tree_budget_r5/bs1.json): pi_top1 0.417 vs the prior's 0.885, KL 5.70 nats -- pi' is far FLATTER than the prior.
one action, 1.1 changed decisions per battle. If more iterations do not move
pi' off the prior, the budget is not the lever and the expensive rungs should
never run.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results/tree_budget_r5"
PR = yaml.safe_load((REPO / "configs/eval/tree_budget_r5.yaml").read_text())


def g(tag):
    p = RES / f"{tag.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def num(d, k, default=float("nan")):
    v = (d or {}).get(k)
    return float(v) if isinstance(v, (int, float)) else default


def main() -> None:
    print("=" * 84)
    print("DOES A BIGGER TREE THINK HARDER?  (IDEAS 8.6 phase S -- the MECHANISM)")
    print("No win rate here is a read: n=40 carries se 0.079.")
    print("=" * 84)
    arms = {a: g(a) for a in PR["phases"]["S"]}
    print(f"\n  {'arm':<5} {'rule':<7} {'iters':>6} {'ms/dec':>8} {'KL(pi||prior)':>14} "
          f"{'pi_top1':>8} {'moved':>7} {'acts on':>8}")
    ok = True
    for a, d in arms.items():
        cfg = PR["arms"][a]["tree"]
        if not d:
            print(f"  {a:<5} {cfg['decide']:<7} {cfg['iters']:>6}  PENDING")
            continue
        missing = [k for k in ("tree/kl_pi_prior", "tree/pi_top1", "tree/argmax_moved")
                   if k not in d]
        if missing:
            ok = False
            print(f"  {a:<5} G_EXPERT_REPORTED FAILED -- missing {missing}; "
                  "the counters did not survive the seat path and this arm says NOTHING")
            continue
        dec = (d.get("search/decisions") or 0) - (d.get("search/placeholder_skips") or 0)
        acts = (d.get("search/flips") or 0) / max(dec, 1)
        print(f"  {a:<5} {cfg['decide']:<7} {cfg['iters']:>6} {num(d,'search/ms_mean'):>8.1f} "
              f"{num(d,'tree/kl_pi_prior'):>14.4f} {num(d,'tree/pi_top1'):>8.3f} "
              f"{num(d,'tree/argmax_moved'):>7.3f} {acts:>8.1%}")

    lo, hi, vis = arms.get("BS1"), arms.get("BS9"), arms.get("BSV")
    if not ok:
        # THE RULE MUST NOT RUN ON MISSING DATA. On 2026-09-19 it did: the
        # counters never reached disk, every value was NaN, and `NaN >= 1.5` is
        # False -- so the readout printed "PHASE R DOES NOT FIRE" as a verdict on
        # an arm that had measured nothing. A gate that fails must SILENCE the
        # conclusion, not feed it.
        print("\n" + "=" * 84)
        print("NO VERDICT. An R0 gate failed above, so the decision rule is NOT")
        print("evaluated: a rule fed NaN returns False and prints a conclusion that")
        print("looks identical to a real negative. Fix the gate and re-run.")
        print("=" * 84)
        return
    if lo and hi:
        kl_lo, kl_hi = num(lo, "tree/kl_pi_prior"), num(hi, "tree/kl_pi_prior")
        mv_lo, mv_hi = num(lo, "tree/argmax_moved"), num(hi, "tree/argmax_moved")
        ms_lo, ms_hi = num(lo, "search/ms_mean"), num(hi, "search/ms_mean")
        print("\n" + "=" * 84)
        print("THE DECISION RULE, written before the screen ran")
        print("=" * 84)
        print(f"  KL            iters 100 {kl_lo:.4f} -> iters 900 {kl_hi:.4f}   "
              f"ratio {kl_hi / kl_lo if kl_lo else float('nan'):.2f}x  (need >= 1.50x)")
        print(f"  argmax_moved  {mv_lo:.3f} -> {mv_hi:.3f}   "
              f"+{100*(mv_hi-mv_lo):.1f} points  (need >= +5.0)")
        print(f"  cost          {ms_lo:.1f} -> {ms_hi:.1f} ms/decision "
              f"({ms_hi/ms_lo if ms_lo else float('nan'):.1f}x for 9x the iterations)")
        fires = (kl_lo and kl_hi / kl_lo >= 1.5) and (mv_hi - mv_lo) >= 0.05
        print(f"\n  -> PHASE R {'FIRES' if fires else 'DOES NOT FIRE'}")
        if fires:
            print("     Run n=1500 at the winning budget against an IN-SESSION greedy")
            print("     anchor. §26's 0.5830 is a different session and may not serve.")
        else:
            print("     MORE ITERATIONS DO NOT BUY MORE THINKING on this object. The")
            print("     tree's +0.021 is whatever it is at iters 100, and resolving it")
            print("     becomes a pure n question (n~4,375/arm) -- a separate decision.")
            print("     It also kills the CHEAP version of IDEAS 4.9: an expert that IS")
            print("     the student has nothing to teach, and the follow-up becomes the")
            print("     PRIOR (a flatter policy, a temperature) rather than the budget.")
    if vis and lo:
        print(f"\n  VISITS at the big budget: pi_top1 {num(vis,'tree/pi_top1'):.3f} "
              f"against gumbel's {num(hi or {}, 'tree/pi_top1'):.3f} at the same iters.")
        print("  §26's TV acted on 3.7% of decisions because visit share IS nearly the")
        print("  prior at iters 100. This says whether the budget was what was missing.")
    if not ok:
        print("\n  AT LEAST ONE R0 GATE FAILED.")
    print("=" * 84)


if __name__ == "__main__":
    main()

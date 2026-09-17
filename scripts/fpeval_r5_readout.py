#!/usr/bin/env python
"""Foul Play's evaluator in our search — the read.

Compares, off FP@20 on the R5 committee at dose M and MATCHED override rate:
their heuristic against our critic at depth 1, and depth-2 against depth-1
within their heuristic. Banked comparators come from RESULTS §22.
"""
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results/fpeval_r5"
D = REPO / "results/depth2_r5"
BANKED = {"D1": (0.5687, 3000, 0.0682, 81.7), "D2M": (0.5680, 3000, 0.0620, 267.3),
          "G0": (0.5747, 1500, None, None)}


def get(d, t):
    p = d / f"{t.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def se2(pa, na, pb, nb):
    return math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)


def line(lab, pa, na, pb, nb, note=""):
    se = se2(pa, na, pb, nb)
    d = pa - pb
    print(f"  {lab:46s} {pa:.4f}(n={na}) - {pb:.4f}(n={nb}) = {d:+.4f} "
          f"at {abs(d) / se:.2f} se{note}")
    return d, se


def main():
    print("=" * 78)
    print("FOUL PLAY'S EVALUATOR IN OUR SEARCH — off FP@20, R5 committee, dose M")
    print("Both FP@20 disclosures travel: weakly-powered equivalence, flattering")
    print("point estimate. Hacking run; nothing here is a headline number.")
    print("=" * 78)

    print("\n## Phase S — delta sweep (override rate and cost ONLY; n=60, se 0.065)\n")
    print(f"  {'cell':5s} {'depth':6s} {'delta':6s} {'override':9s} {'ms/dec':8s} {'fired':6s}")
    import yaml
    pr = yaml.safe_load(open(REPO / "configs/eval/fpeval_r5.yaml"))
    for a in pr["phases"]["S"]:
        d = get(RES, a)
        if not d:
            print(f"  {a:5s} PENDING"); continue
        spec = pr["arms"][a]
        print(f"  {a:5s} {2 if spec.get('depth2') else 1:<6d} "
              f"{spec['margin_delta']:<6.2f} "
              f"{(d.get('search/override_rate') or float('nan')):<9.4f} "
              f"{(d.get('search/ms_mean') or float('nan')):<8.1f} "
              f"{(d.get('heuristic/fired_rate') or 0):<6.3f}")

    hd1, hd2, ga = get(RES, "HD1"), get(RES, "HD2"), get(RES, "GA")
    print("\n## Phase R\n")
    for name, d in (("HD1", hd1), ("HD2", hd2), ("GA", ga)):
        if d:
            print(f"  {name:4s} win {d['our_win_rate']:.4f} n {d['battles_finished']:<5d} "
                  f"override {(d.get('search/override_rate') or float('nan')):.4f} "
                  f"ms {(d.get('search/ms_mean') or float('nan')):.1f} "
                  f"fired {(d.get('heuristic/fired_rate') or 0):.3f}")
        else:
            print(f"  {name:4s} PENDING")

    print("\n## The reads\n")
    if hd1:
        p, n = hd1["our_win_rate"], hd1["battles_finished"]
        print("  THEIR EVALUATOR vs OURS, both depth 1, matched override:")
        dd, se = line("HD1 - D1 (our critic)", p, n, *BANKED["D1"][:2])
        print(f"    realized override {hd1.get('search/override_rate'):.4f} vs D1's "
              f"{BANKED['D1'][2]:.4f} (|diff| "
              f"{abs(hd1.get('search/override_rate') - BANKED['D1'][2]):.4f}; "
              f"{'MATCH OK' if abs(hd1.get('search/override_rate') - BANKED['D1'][2]) <= 0.02 else '**MATCH POOR**'})")
        print(f"    cost {hd1.get('search/ms_mean'):.1f} ms vs {BANKED['D1'][3]:.1f} ms "
              f"= {hd1.get('search/ms_mean') / BANKED['D1'][3]:.2f}x (the encoder is not run)")
    if hd1 and hd2:
        print("\n  DEPTH, INSIDE THEIR EVALUATOR:")
        line("HD2 - HD1", hd2["our_win_rate"], hd2["battles_finished"],
             hd1["our_win_rate"], hd1["battles_finished"])
        print(f"    cost {hd2.get('search/ms_mean'):.1f} vs {hd1.get('search/ms_mean'):.1f} ms "
              f"= {hd2.get('search/ms_mean') / max(hd1.get('search/ms_mean'), 1e-9):.2f}x")
        print("    COMPARE: the same depth step with OUR critic was -0.0007 at 0.05 se.")
    if ga:
        print("\n  SESSION ANCHOR (standing rule: never difference across sessions without one):")
        line("GA (greedy, this session) - G0 (greedy, 09-17)",
             ga["our_win_rate"], ga["battles_finished"], *BANKED["G0"][:2])
        for name, d in (("HD1", hd1), ("HD2", hd2)):
            if d:
                line(f"{name} - GA (greedy, same session)", d["our_win_rate"],
                     d["battles_finished"], ga["our_win_rate"], ga["battles_finished"])
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

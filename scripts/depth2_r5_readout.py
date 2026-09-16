#!/usr/bin/env python
"""JOURNEY 11.5 readout: depth-1 vs depth-2 on the R5 committee, off FP@20.

    python scripts/depth2_r5_readout.py [--out results/depth2_r5]

Prints the R0 gates first (an arm that fails one is VOID and its win rate is
not reported), then the phase-S sweep, then the reads exactly as
`configs/eval/depth2_r5.yaml` states them, with PENDING wherever an artifact is
missing. Nothing here chooses anything: rule R1 already ran in
`scripts/depth2_r5_pin.py`, and the branch language below is the pre-reg's.
"""
import argparse
import json
import math
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PREREG = REPO / "configs/eval/depth2_r5.yaml"
LEAVES_REF, LEAVES_BAND = 343.0, 0.20


def load(out: Path, arm: str):
    p = out / f"{arm.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def se2(pa, na, pb, nb):
    return math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)


def gates(arm: str, d: dict, spec: dict) -> list[str]:
    """The pre-reg's R0 gates, each against the report. Returns failures."""
    bad = []
    if spec.get("depth2"):
        fired = d.get("depth2/fired_rate")
        gc = d.get("depth2/grandchildren_per_decision")
        if fired is None or fired < 0.90 or not gc:
            bad.append(f"G_FIRED: fired_rate={fired!r} gc/dec={gc!r} — the extra "
                       "ply did not fire; the arm is VOID")
    if d.get("search_dose") not in (None, "M"):
        bad.append(f"G_DOSE: dose {d.get('search_dose')!r} != M")
    lv = d.get("search/leaves_mean")
    if lv is not None and abs(lv - LEAVES_REF) / LEAVES_REF > LEAVES_BAND:
        bad.append(f"G_DOSE: leaves_mean {lv:.0f} outside {LEAVES_BAND:.0%} of {LEAVES_REF:.0f}")
    lanes = d.get("seat_lanes") or (d.get("searched_ensemble") or {}).get("members")
    if lanes and list(lanes) != ["w104", "w112", "w120"]:
        bad.append(f"G_OBJECT: members {lanes} are not the R5 committee")
    if d.get("declared_search_time_ms") not in (None, 20):
        bad.append(f"G_BUDGET: declared_search_time_ms {d.get('declared_search_time_ms')}")
    mc = d.get("max_concurrent_live_battles")
    if mc is not None and mc > 1:
        bad.append(f"G_SERIAL: max_concurrent_live_battles {mc} > 1")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/depth2_r5")
    args = ap.parse_args()
    out = REPO / args.out
    pr = yaml.safe_load(open(PREREG))
    arms = pr["arms"]

    print("=" * 78)
    print("JOURNEY 11.5 — DEPTH-1 vs DEPTH-2 on the R5 ladder committee, off FP@20")
    print("configs/eval/depth2_r5.yaml. The two FP@20 disclosures travel with every")
    print("number below: the equivalence test is weakly powered, and the point")
    print("estimate flatters us. FP@20 is an INSTRUMENT, not a rung.")
    print("=" * 78)

    data, voids = {}, {}
    for arm, spec in arms.items():
        d = load(out, arm)
        if d is None:
            continue
        data[arm] = d
        bad = gates(arm, d, spec)
        if bad:
            voids[arm] = bad

    print("\n## R0 gates\n")
    if not data:
        print("  PENDING — no arm JSON on disk yet")
    for arm in [a for a in pr["run_order"] if a in data]:
        print(f"  {arm:4s} {'VOID: ' + '; '.join(voids[arm]) if arm in voids else 'all gates pass'}")
    for arm in [a for a in pr["run_order"] if a not in data]:
        print(f"  {arm:4s} PENDING")

    print("\n## PHASE S — the delta sweep (override rate and cost ONLY;")
    print("   NO WIN RATE FROM PHASE S IS A READ: at n=60 its se is 0.065)\n")
    print(f"  {'cell':5s} {'depth':6s} {'delta':6s} {'override':9s} {'ms/dec':8s} "
          f"{'dec/s':7s} {'fired':6s} {'gc/dec':7s}")
    for arm in pr["phases"]["S"]:
        d = data.get(arm)
        spec = arms[arm]
        if d is None:
            print(f"  {arm:5s} PENDING")
            continue
        depth = 2 if spec.get("depth2") else 1
        ms = d.get("search/ms_mean") or float("nan")
        print(f"  {arm:5s} {depth:<6d} {spec['margin_delta']:<6.2f} "
              f"{(d.get('search/override_rate') or float('nan')):<9.4f} "
              f"{ms:<8.1f} {1000 / ms if ms else float('nan'):<7.2f} "
              f"{(d.get('depth2/fired_rate') or 0):<6.3f} "
              f"{(d.get('depth2/grandchildren_per_decision') or 0):<7.1f}")

    print("\n## PHASE R — the reads\n")
    d1, d2m, d2n, g0 = (data.get(a) for a in ("D1", "D2M", "D2N", "G0"))

    def row(name, d, spec):
        if d is None:
            print(f"  {name:5s} PENDING")
            return
        ms = d.get("search/ms_mean")
        tag = " [VOID]" if name in voids else ""
        print(f"  {name:5s} win {d['our_win_rate']:.4f}  n {d['battles_finished']:<5d} "
              f"ties {d.get('ties', 0):<3d} "
              f"delta {spec.get('margin_delta') if spec.get('margin_delta') != 'FILL_FROM_RULE_R1' else '?'}  "
              f"override {(d.get('search/override_rate') or float('nan')):.4f}  "
              f"{('ms %.1f' % ms) if ms else 'greedy'}{tag}")

    for a in ("D1", "D2M", "D2N", "G0"):
        row(a, data.get(a), arms[a])

    print("\n### PRIMARY — D2M - D1, matched override rate\n")
    if d1 and d2m and "D1" not in voids and "D2M" not in voids:
        pa, na = d2m["our_win_rate"], d2m["battles_finished"]
        pb, nb = d1["our_win_rate"], d1["battles_finished"]
        delta, se = pa - pb, se2(pa, na, pb, nb)
        credit = delta >= 0.025 and delta >= 2 * se
        print(f"  D2M {pa:.4f} (n={na})  -  D1 {pb:.4f} (n={nb})  =  {delta:+.4f}")
        print(f"  se_diff (pooled binomial; SEED-CLUSTERED UNAVAILABLE by construction,")
        print(f"  one arm per cell — so this governs and is ANTI-CONSERVATIVE): {se:.4f}")
        print(f"  |delta| / se = {abs(delta) / se:.2f};  floor >= +0.025 "
              f"{'PASS' if delta >= 0.025 else 'FAIL'};  >= 2*se_diff "
              f"{'PASS' if delta >= 2 * se else 'FAIL'}")
        ms1, ms2 = d1.get("search/ms_mean"), d2m.get("search/ms_mean")
        if ms1 and ms2:
            print(f"  COST (required by the exit condition): depth-1 {ms1:.1f} ms/dec "
                  f"= {1000 / ms1:.2f} dec/s; depth-2 {ms2:.1f} ms/dec = "
                  f"{1000 / ms2:.2f} dec/s; ratio {ms2 / ms1:.2f}x")
        o1 = d1.get("search/override_rate")
        o2 = d2m.get("search/override_rate")
        if o1 is not None and o2 is not None:
            # MATCH QUALITY, judged against a threshold fixed 2026-09-16 at
            # 23:31Z -- after the three DEPTH-1 screen cells were on disk
            # (0.0723 / 0.0208 / 0.0005) and BEFORE any depth-2 cell existed,
            # so the quantity this judges did not yet exist when the threshold
            # was set. It changes no arm, no choice and no credit rule; it only
            # refuses to let "matched override rate" be claimed when the grid
            # did not actually bracket the target.
            diff = abs(o2 - o1)
            print(f"  REALIZED OVERRIDE RATES: depth-1 {o1:.4f} vs depth-2 {o2:.4f} "
                  f"(|diff| {diff:.4f})")
            if diff <= 0.02:
                print("  MATCH OK (<= 0.02): the primary comparison isolates DEPTH.")
            else:
                print("  **MATCH POOR (> 0.02).** The pre-registered grid "
                      "{0.10, 0.20, 0.35, 0.50} did not bracket depth-1's rate "
                      "closely, so the primary delta is PARTLY an override-rate "
                      "effect -- the exact confound this design set out to "
                      "control. Read it as an upper bound on depth's own "
                      "contribution, and say so in every quote.")
        print()
        if credit:
            print("  BRANCH: **DEPTH-2 CREDITS** on the matrix family at dose M off FP@20,")
            print("  at the cost multiple above. Per JOURNEY 11.5 this argues for MCTS in")
            print("  gen9 — AND THE COST MULTIPLE TRAVELS WITH THAT ARGUMENT.")
        elif delta <= -0.025 and abs(delta) >= 2 * se:
            print("  BRANCH: depth-2 COSTS on this vehicle at this budget. Report it; it is")
            print("  NOT evidence about MCTS and NOT evidence about depth at other doses.")
        else:
            print("  BRANCH: **NULL.** The licensed sentence, verbatim from the pre-reg:")
            print("  'the matrix family's selective depth-2 does not pay on the R5 committee")
            print("  off FP@20 at dose M and matched override rate, at n=3000 per arm.'")
            print("  THE MCTS QUESTION STAYS OPEN — this file tested ONE vehicle, and")
            print("  rl/search/tree.py is a different algorithm with a different cost curve.")
            print("  No depth-3, per the exit condition.")
    else:
        print("  PENDING")

    print("\n### SECONDARY — S1 the override-rate confound (D2N, naive delta 0.10)\n")
    if d1 and d2n:
        pa, na = d2n["our_win_rate"], d2n["battles_finished"]
        pb, nb = d1["our_win_rate"], d1["battles_finished"]
        print(f"  D2N {pa:.4f} (n={na}) - D1 {pb:.4f} (n={nb}) = {pa - pb:+.4f} "
              f"at {abs(pa - pb) / se2(pa, na, pb, nb):.2f} se; override "
              f"{d2n.get('search/override_rate'):.4f} vs {d1.get('search/override_rate'):.4f}")
        if d2m:
            print(f"  D2M - D2N = {d2m['our_win_rate'] - pa:+.4f} — THIS IS THE CONFOUND'S")
            print("  SIZE: same depth, same object, same dose; only the gate's delta moved.")
    else:
        print("  PENDING")

    print("\n### SECONDARY — S2 does search of ANY depth beat the greedy committee?\n")
    if g0:
        for name, d in (("D1", d1), ("D2M", d2m)):
            if d:
                pa, na = d["our_win_rate"], d["battles_finished"]
                pb, nb = g0["our_win_rate"], g0["battles_finished"]
                print(f"  {name} - G0 = {pa - pb:+.4f} at "
                      f"{abs(pa - pb) / se2(pa, na, pb, nb):.2f} se "
                      f"(G0 n={nb}, so this cannot resolve under ~0.032)")
        print("\n### SECONDARY — S3 the session offset on this instrument\n")
        banked = pr["comparators_banked"]["e3wf_offfp20"]
        pa, na = g0["our_win_rate"], g0["battles_finished"]
        print(f"  G0 {pa:.4f} (n={na}, this session) vs banked E3WF {banked['rate']} "
              f"(n={banked['n']}, 2026-09-15) = {pa - banked['rate']:+.4f} at "
              f"{abs(pa - banked['rate']) / se2(pa, na, banked['rate'], banked['n']):.2f} se")
        print("  Descriptive, and a CAVEAT on any cross-session comparison — the same")
        print("  frozen object moved 0.014 on the BC-clone instrument between sessions.")
    else:
        print("  PENDING")

    print("\n" + "=" * 78)
    print("BARRED ON THESE NUMBERS (the pre-reg's machine-readable list):")
    for phrase in pr["barred_language"]:
        print(f"  - {phrase}")
    print("=" * 78)


if __name__ == "__main__":
    main()

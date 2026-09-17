#!/usr/bin/env python
"""Does the GATE set the ceiling? Both evaluators at D2N's open override rate.

Depth is held at 1 (a measured null, §22/§23). The comparison is tight-gate vs
open-gate WITHIN each evaluator, and open-gate across evaluators.
"""
import json, math
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results/gate_r5"
PR = yaml.safe_load(open(REPO / "configs/eval/gate_r5.yaml"))
C = PR["comparators"]


def g(t):
    p = RES / f"{t.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def cmp(lab, pa, na, pb, nb):
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    print(f"  {lab:52s} {pa:.4f} - {pb:.4f} = {pa - pb:+.4f} at {abs(pa - pb) / se:.2f} se")
    return pa - pb, se


def main():
    print("=" * 78)
    print("IS THE GATE THE CEILING? both evaluators, depth 1, gate OPEN to 16.3%")
    print("=" * 78)
    print("\n## Sweep toward the target override rate\n")
    for a in PR["phases"]["S"]:
        d = g(a)
        if not d:
            print(f"  {a} PENDING"); continue
        spec = PR["arms"][a]
        kind = "heuristic" if spec.get("heuristic") else "our critic"
        print(f"  {a:5s} {kind:11s} delta {spec['margin_delta']:<5.2f} "
              f"override {d['search/override_rate']:.4f} "
              f"(|diff| {abs(d['search/override_rate'] - C['target_override']):.4f})  "
              f"{d['search/ms_mean']:.1f} ms")

    cn1, fn1, gb = g("CN1"), g("FN1"), g("GB")
    print("\n## The read\n")
    for n, d in (("CN1 our critic, gate OPEN", cn1), ("FN1 heuristic, gate OPEN", fn1),
                 ("GB  greedy, no search", gb)):
        print(f"  {n:34s} " + (f"{d['our_win_rate']:.4f} n={d['battles_finished']} "
              f"override {(d.get('search/override_rate') or float('nan')):.4f}" if d else "PENDING"))

    print("\n## Does opening the gate collapse each evaluator?\n")
    if cn1:
        cmp("OUR CRITIC: open gate - tight gate (d1)", cn1["our_win_rate"],
            cn1["battles_finished"], C["d1"]["rate"], C["d1"]["n"])
        print(f"    for reference, our critic at depth 2 open-gate (D2N) was "
              f"{C['d2n']['rate']:.4f} vs {C['d1']['rate']:.4f} tight = "
              f"{C['d2n']['rate'] - C['d1']['rate']:+.4f}")
    if fn1:
        cmp("THEIR HEURISTIC: open gate - tight gate (d1)", fn1["our_win_rate"],
            fn1["battles_finished"], C["hd1"]["rate"], C["hd1"]["n"])
    if cn1 and fn1:
        print()
        cmp("open gate: heuristic - our critic", fn1["our_win_rate"],
            fn1["battles_finished"], cn1["our_win_rate"], cn1["battles_finished"])
        print("\n  READ: if BOTH collapse, the SEARCH CONSTRUCTION is the ceiling and a")
        print("  better leaf value is not the lever. If the heuristic HOLDS where our")
        print("  critic falls, our critic's off-distribution behaviour is real and was")
        print("  merely invisible at a 6.5% override rate.")
    if gb:
        print()
        cmp("GB (greedy, this block) - GA (greedy, last block)", gb["our_win_rate"],
            gb["battles_finished"], C["greedy"]["rate"], C["greedy"]["n"])
        print("    the session anchor; ~0.02 offsets have bitten twice this week")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

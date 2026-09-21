#!/usr/bin/env python
"""Pre-stated reads of the R6 fleet, from disk.

    python scripts/r6_reads_readout.py [--fp results/r6_reads_offfp] [--sh results/r6_reads]
                                       [--json-out results/r6_reads_offfp/readout.json]

Reads configs/eval/r6_reads_offfp.yaml (R1-R5, off FP@20 -- the trio headers' PRIMARY
and the ladder-object pick) and configs/eval/r6_reads.yaml (S1-S3, vs SH, locked form)
results; prints every read as stated in the pre-reg headers and PENDING where an arm
has not landed. R1 applies the CREDIT LINE verbatim (CLAUDE.md): "a lever is credited
iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the
pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the
per-seed finals at read time." Boundary: EXACTLY +0.025 or EXACTLY 2*se_diff reads as
NOT met. Every other read is descriptive. The two FP@20 disclosures print with the
numbers, every time. The core (credit, se's, the object rule) is pure and tested
(tests/test_r6_reads_prereg.py); main() only reads files.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDIT_FLOOR = 0.025
TIE_BAND = 0.013


# ----------------------------------------------------------------- the pure core
def pool(*arms):
    arms = [a for a in arms if a]
    if not arms:
        return None
    n = sum(a["n"] for a in arms)
    return {"p": sum(a["p"] * a["n"] for a in arms) / n, "n": n}


def se_binomial(a, b):
    """Unpaired two-proportion se on the POOLED rates."""
    return math.sqrt(a["p"] * (1 - a["p"]) / a["n"] + b["p"] * (1 - b["p"]) / b["n"])


def se_clustered(rates_a, rates_b):
    """Seed-clustered se of a difference of lane MEANS: sd(rates)/sqrt(k) per side,
    combined in quadrature (ddof=1; k >= 2 per side, else nan)."""
    def side(r):
        k = len(r)
        if k < 2:
            return float("nan")
        m = sum(r) / k
        return math.sqrt(sum((x - m) ** 2 for x in r) / (k - 1)) / math.sqrt(k)
    return math.hypot(side(rates_a), side(rates_b))


def credit(delta, se_diff, floor=CREDIT_FLOOR):
    """The credit line with the boundary convention: strictly above both legs."""
    if math.isnan(se_diff):
        return "PENDING"
    if delta > floor and delta > 2 * se_diff:
        return "POS"
    if delta < -floor and -delta > 2 * se_diff:
        return "NEG"
    return "FLAT"


def primary(trio_arms, floor_arms):
    """R1 for one trio: pooled delta vs the re-drawn floor, both se's, the larger, the cell."""
    if any(a is None for a in trio_arms) or any(a is None for a in floor_arms):
        return None
    T, F = pool(*trio_arms), pool(*floor_arms)
    d = T["p"] - F["p"]
    sb = se_binomial(T, F)
    sc = se_clustered([a["p"] for a in trio_arms], [a["p"] for a in floor_arms])
    se = max(sb, sc) if not math.isnan(sc) else sb
    return {"delta": d, "se_binomial": sb, "se_clustered": sc, "se_diff": se,
            "z": d / se if se > 0 else float("nan"), "cell": credit(d, se),
            "trio_pooled": T, "floor_pooled": F}


def object_rule(cands, floor, sizes, band=TIE_BAND):
    """R2: highest point estimate; top two within `band` -> the LARGER committee; none
    reaches floor - band -> the floor object. `cands` is {name: arm-or-None}."""
    have = [(n, a) for n, a in cands.items() if a]
    if len(have) < len(cands) or floor is None:
        return {"pick": None, "reason": "PENDING"}
    have.sort(key=lambda x: (-x[1]["p"], -sizes[x[0]]))
    best, second = have[0], have[1]
    pick = best
    if abs(best[1]["p"] - second[1]["p"]) < band and sizes[second[0]] > sizes[best[0]]:
        pick = second
    if pick[1]["p"] < floor["p"] - band:
        return {"pick": "FLOOR", "reason": f"no candidate reaches the floor - {band}",
                "best": best[0], "second": second[0]}
    return {"pick": pick[0], "reason": "highest point estimate" if pick is best else
            f"top two within {band}: the larger committee", "best": best[0], "second": second[0]}


# ----------------------------------------------------------------- disk readers
def fp(res, tag):
    p = os.path.join(res, f"{tag}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    n = d.get("battles_finished") or 0
    return {"p": d["our_win_rate"], "n": n, "ties": d.get("ties"), "tag": tag} if n else None


def sh(res, prefix):
    files = sorted(glob.glob(os.path.join(res, f"{prefix}*.final.json")))
    wins, n, parts = 0.0, 0, []
    for f in files:
        d = json.load(open(f))
        k = int(d.get("episodes") or d.get("n") or 0)
        r = d.get("eval/win_rate")
        if not k or r is None:
            continue
        wins += r * k
        n += k
        parts.append(f"{os.path.basename(f).replace('.final.json', '')} {r:.5f}")
    return {"p": wins / n, "n": n, "parts": parts} if n else None


def fmt(a):
    return "PENDING" if a is None else f"{a['p']:.4f} (n={a['n']})"


def delta_line(a, b, label):
    if a is None or b is None:
        return f"  {label}: PENDING"
    d = a["p"] - b["p"]
    se = se_binomial(a, b)
    return f"  {label}: {d:+.4f} at {d / se if se > 0 else float('nan'):.2f} se_diff (se {se:.4f})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp", default=os.path.join(REPO, "results/r6_reads_offfp"))
    ap.add_argument("--sh", default=os.path.join(REPO, "results/r6_reads"))
    ap.add_argument("--sh-r5", default=os.path.join(REPO, "results/monster_reads"),
                    help="the R5 W finals' banked vs-SH results (S1/S2 comparators, read from disk)")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    out = {}

    print("R6 READS -- off FP@20 PRIMARY (credit line) + object pick; vs SH descriptive")
    print("Disclosures on every FP@20 number: the equivalence test is weakly powered, and the")
    print("point estimate flatters us. Budget: FP@20 = search_time_ms 20 per decision. Every")
    print("off-FP arm runs with loop_breaker: true (ruling #1) -- a policy-form change vs every")
    print("banked number, which is why the R5 floor is RE-DRAWN below and never quoted.\n")

    ga = [fp(args.fp, t) for t in ("ga304f", "ga312f", "ga320f")]
    gb = [fp(args.fp, t) for t in ("gb328f", "gb336f", "gb344f")]
    gw = [fp(args.fp, t) for t in ("gw104r", "gw112r", "gw120r")]
    e3a, e3b, e6r, e9r, e3w = (fp(args.fp, t) for t in ("e3af", "e3bf", "e6rf", "e9rf", "e3wr"))
    print("OFF FP@20 singles (n=3000 each):")
    for name, arms in (("trio A finals", ga), ("trio B finals", gb), ("R5 W re-draw", gw)):
        print(f"  {name}: " + " / ".join(fmt(a) for a in arms))
    print(f"  pooled: A {fmt(pool(*ga))} | B {fmt(pool(*gb))} | W re-draw {fmt(pool(*gw))}")
    print("OFF FP@20 committees (n=3000 each):")
    print(f"  E3AF {fmt(e3a)} | E3BF {fmt(e3b)} | E6RF {fmt(e6r)} | E9RF {fmt(e9r)} (MIXED c6) | floor E3WR {fmt(e3w)}")

    print("\nR1 THE PRIMARY, per trio (credit line verbatim; boundary = NOT met):")
    for name, arms in (("A (outcome heads, IDEAS 4.11)", ga), ("B (batch/epochs, IDEAS 4.12)", gb)):
        r = primary(arms, gw)
        out[f"R1_{name[0]}"] = r
        if r is None:
            print(f"  trio {name}: PENDING")
            continue
        print(f"  trio {name}: delta {r['delta']:+.4f}  se_binomial {r['se_binomial']:.4f}  "
              f"se_clustered {r['se_clustered']:.4f}  -> se_diff {r['se_diff']:.4f}  z {r['z']:.2f}  CELL {name[0]}-{r['cell']}")
    print("  C6 is common-mode on every R6 lane and confounded with each lever by construction; uncredited.")

    print("\nR2 THE LADDER OBJECT: highest candidate; top two within 0.013 -> the larger committee;")
    print("   none reaches E3WR - 0.013 -> the R5 committee stays the object.")
    cands = {"E3AF": e3a, "E3BF": e3b, "E6RF": e6r, "E9RF": e9r}
    sizes = {"E3AF": 3, "E3BF": 3, "E6RF": 6, "E9RF": 9}
    pick = object_rule(cands, e3w, sizes)
    out["R2"] = pick
    print(f"  LADDER OBJECT = {pick['pick'] or 'PENDING'} ({pick['reason']})")
    for n, a in cands.items():
        print(delta_line(a, e3w, f"{n} - E3WR"))

    print("\nR3 COMMITTEE GAIN PER TRIO (3000 vs 9000; the R5 W trio read +0.0417 over its floor):")
    print(delta_line(e3a, pool(*ga), "E3AF - mean(GA)"))
    print(delta_line(e3b, pool(*gb), "E3BF - mean(GB)"))
    print(delta_line(e3w, pool(*gw), "E3WR - mean(GW re-draw)  [same session]"))
    print("\nR4 MEMBERS:")
    print(delta_line(e9r, e6r, "E9RF - E6RF  (do the c6-off W finals still add? MIXED object)"))
    best3 = max((a for a in (e3a, e3b) if a), key=lambda a: a["p"], default=None)
    print(delta_line(e6r, best3, "E6RF - better ENS3"))

    print("\nvs SH, LOCKED form (no loop breaker), 3000/lane x 3 or 3 batches x 3000:")
    GAs, GBs = sh(args.sh, "ga_"), sh(args.sh, "gb_")
    E3As, E3Bs, E6Rs, E9Rs = (sh(args.sh, p) for p in ("e3a_b", "e3b_b", "e6r_b", "e9r_b"))
    GWs_r5, E3Ws_r5 = sh(args.sh_r5, "gw_"), sh(args.sh_r5, "e3w_b")
    for name, a in (("GA", GAs), ("GB", GBs), ("E3A", E3As), ("E3B", E3Bs), ("E6R", E6Rs), ("E9R", E9Rs),
                    ("R5 GW (banked)", GWs_r5), ("R5 E3W (banked)", E3Ws_r5)):
        print(f"  {name}: {fmt(a)}" + (f"  [{', '.join(a['parts'])}]" if a and a.get("parts") else ""))
    a0 = {"p": 0.78867, "n": 9000}
    print("S1 (descriptive; vs SH is the saturated axis):")
    print(delta_line(GAs, GWs_r5, "GA - R5 GW(banked)"))
    print(delta_line(GBs, GWs_r5, "GB - R5 GW(banked)"))
    print(delta_line(GAs, a0, "GA - 100M A0 0.78867"))
    print(delta_line(GBs, a0, "GB - 100M A0 0.78867"))
    print("S2:")
    for name, a in (("E3A", E3As), ("E3B", E3Bs), ("E6R", E6Rs), ("E9R", E9Rs)):
        print(delta_line(a, E3Ws_r5, f"{name} - R5 E3W(banked)"))
    print("S3 committee gain per trio:")
    print(delta_line(E3As, GAs, "E3A - GA"))
    print(delta_line(E3Bs, GBs, "E3B - GB"))
    print("\nCredit line (verbatim, CLAUDE.md): a lever is credited iff pooled delta >= +0.025 AND")
    print(">= 2*se_diff, where se_diff is the LARGER of the pooled-binomial se_diff and the")
    print("seed-clustered se_diff, the latter computed from the per-seed finals at read time.")
    print("R1 is the only credit read; every other number here is descriptive.")
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(out, f, indent=2)
        print(f"-> {args.json_out}")


if __name__ == "__main__":
    main()

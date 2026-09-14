#!/usr/bin/env python
"""Pre-stated reads of the monster's [RWL-3] SECONDARY battery, from disk.

    python scripts/monster_reads_readout.py

Reads configs/eval/monster_reads_offfp.yaml (R1-R5, off FP@20) and
configs/eval/monster_reads.yaml (S1-S3, vs SH) results; prints every read as
stated in the pre-reg headers with UNPAIRED two-proportion se (seeds do NOT
pair battles -- docs/landmines.md 2026-09-11) and PENDING where an arm has
not landed. Descriptive throughout: nothing here is a credit ([RWL-3]).
The two FP@20 disclosures are printed with the numbers, every time.
"""
import glob
import json
import math
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPRES = os.path.join(REPO, "results/monster_reads_offfp")
RES = os.path.join(REPO, "results/monster_reads")


def fp(tag):
    p = os.path.join(FPRES, f"{tag}.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    n = d.get("battles_finished") or 0
    return {"p": d["our_win_rate"], "n": n, "ties": d.get("ties"), "tag": tag}


def sh(prefix):
    """Pool every <prefix>*.final.json (a policy arm's lanes, or a committee's
    batches) into one rate with its n."""
    files = sorted(glob.glob(os.path.join(RES, f"{prefix}*.final.json")))
    if not files:
        return None
    wins = 0.0
    n = 0
    parts = []
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


def pool(*arms):
    arms = [a for a in arms if a]
    if not arms:
        return None
    n = sum(a["n"] for a in arms)
    return {"p": sum(a["p"] * a["n"] for a in arms) / n, "n": n}


def se_diff(a, b):
    return math.sqrt(a["p"] * (1 - a["p"]) / a["n"] + b["p"] * (1 - b["p"]) / b["n"])


def fmt(a):
    return "PENDING" if a is None else f"{a['p']:.4f} (n={a['n']})"


def delta(a, b, label):
    if a is None or b is None:
        return f"  {label}: PENDING"
    d = a["p"] - b["p"]
    se = se_diff(a, b)
    z = d / se if se > 0 else float("nan")
    return f"  {label}: {d:+.4f} at {z:.2f} se_diff (se {se:.4f})"


def main():
    print("MONSTER READS -- [RWL-3] SECONDARY battery, descriptive; NOTHING HERE IS A CREDIT")
    print("Disclosures on every FP@20 number: the equivalence test is weakly powered, and the")
    print("point estimate flatters us. Budget: FP@20 = 4 battles x 10 ms = 40 ms/decision.\n")

    gl = [fp(t) for t in ("gl128f", "gl136f", "gl144f")]
    gw = [fp(t) for t in ("gw104f", "gw112f", "gw120f")]
    gr = [fp(t) for t in ("g104r", "g112r", "g120r")]
    e3l, e3w, e6m, e9, e3h, gb = (fp(t) for t in ("e3lf", "e3wf", "e6mf", "e9f", "e3hf", "g112b"))
    GL, GW, GR = pool(*gl), pool(*gw), pool(*gr)

    print("OFF FP@20 singles (n=3000 each):")
    for name, arms in (("L2LAM finals", gl), ("W finals", gw), ("100M re-draw", gr)):
        print(f"  {name}: " + " / ".join(fmt(a) for a in arms))
    print(f"  pooled: L2LAM {fmt(GL)} | W {fmt(GW)} | 100M {fmt(GR)}")
    print("OFF FP@20 committees (n=3000 each):")
    print(f"  E3LF {fmt(e3l)} | E3WF {fmt(e3w)} | E6MF {fmt(e6m)} | E9F {fmt(e9)} | floor E3HF {fmt(e3h)}")
    print(f"  load bridge G112B (phase B, n=1000) {fmt(gb)} vs G112R (phase A) {fmt(gr[1])}")
    print(delta(gb, gr[1], "  bridge delta (load term; se ~0.018, anything under it is invisible)"))

    print("\nR1 THE LADDER OBJECT (M-R5-1): highest candidate; top two within 0.013 -> the larger committee;")
    print("   none reaches E3HF - 0.013 -> the 100M ENS3 itself.")
    cands = [(n, a) for n, a in (("E3WF", e3w), ("E3LF", e3l), ("E6MF", e6m), ("E9F", e9)) if a]
    if len(cands) < 4 or e3h is None:
        print("  PENDING (needs all four candidates and the floor)")
    else:
        size = {"E3WF": 3, "E3LF": 3, "E6MF": 6, "E9F": 9}
        cands.sort(key=lambda x: (-x[1]["p"], -size[x[0]]))
        best, second = cands[0], cands[1]
        pick = best
        if abs(best[1]["p"] - second[1]["p"]) < 0.013 and size[second[0]] > size[best[0]]:
            pick = second
        if pick[1]["p"] < e3h["p"] - 0.013:
            print(f"  no candidate reaches the floor - 0.013 ({e3h['p'] - 0.013:.4f}): LADDER OBJECT = the 100M ENS3")
        else:
            print(f"  LADDER OBJECT = {pick[0]} {fmt(pick[1])} (best {best[0]} {fmt(best[1])}, second {second[0]} {fmt(second[1])})")
        for n, a in cands:
            print(delta(a, e3h, f"{n} - E3HF"))

    print("\nR2 STEPS PER RECIPE (pooled 9000 vs 9000):")
    print(delta(GW, GR, "W 200M - 100M re-draw"))
    print(delta(GL, GR, "L2LAM 200M - 100M re-draw"))
    print("\nR3 RECIPE (crosses phases; bridge above):")
    print(delta(GW, GL, "W - L2LAM"))
    print("\nR4 COMMITTEE GAIN PER TRIO (vs the 100M's +0.067):")
    print(delta(e3w, GW, "E3WF - mean(GW)"))
    print(delta(e3l, GL, "E3LF - mean(GL)"))
    print(delta(e3h, GR, "E3HF - mean(100M re-draw)  [the 100M gain, same session]"))
    print("\nR5 MEMBERS:")
    print(delta(e9, e6m, "E9F - E6MF"))
    best3 = max((a for a in (e3w, e3l) if a), key=lambda a: a["p"], default=None)
    print(delta(e6m, best3, "E6MF - better ENS3"))

    print("\nvs SH, locked protocol (3000/lane x 3 or 3 batches x 3000):")
    GLs, GWs = sh("gl_"), sh("gw_")
    E3Ls, E3Ws, E6Ms, E9s, E3Hs = (sh(p) for p in ("e3l_b", "e3w_b", "e6m_b", "e9_b", "e3h_b"))
    for name, a in (("GL", GLs), ("GW", GWs), ("E3L", E3Ls), ("E3W", E3Ws), ("E6M", E6Ms), ("E9", E9s), ("E3H", E3Hs)):
        print(f"  {name}: {fmt(a)}" + (f"  [{', '.join(a['parts'])}]" if a else ""))
    a0 = {"p": 0.78867, "n": 9000}
    ens3 = {"p": 0.82356, "n": 9000}
    print("S1 (vs banked 100M greedy A0 0.78867, same block on disk):")
    print(delta(GWs, a0, "GW - A0"))
    print(delta(GLs, a0, "GL - A0"))
    print(delta(GWs, GLs, "GW - GL"))
    print("S2 (vs the banked 100M ENS3 0.82356 and today's E3H):")
    for name, a in (("E3W", E3Ws), ("E3L", E3Ls), ("E6M", E6Ms), ("E9", E9s)):
        print(delta(a, ens3, f"{name} - ENS3(banked)"))
        print(delta(a, E3Hs, f"{name} - E3H(today)"))
    print("S3 committee gain per trio (vs the 100M's +0.0349):")
    print(delta(E3Ws, GWs, "E3W - GW"))
    print(delta(E3Ls, GLs, "E3L - GL"))
    print("\nCredit line (verbatim, CLAUDE.md): a lever is credited iff pooled delta >= +0.025 AND")
    print(">= 2*se_diff, where se_diff is the LARGER of the pooled-binomial se_diff and the")
    print("seed-clustered se_diff, the latter computed from the per-seed finals at read time.")
    print("No number above is a credit; the ladder pick under R1 is a descriptive selection.")


if __name__ == "__main__":
    main()

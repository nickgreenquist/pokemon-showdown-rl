#!/usr/bin/env python
"""mech200m readout: grade [RWL-3]'s mechanism co-primary against its own
pre-stated branches, from the artifacts in results/mech200m.

    python scripts/mech200m_readout.py [--out results/mech200m]

Reads M1-M6 exactly as `configs/eval/mech200m.yaml` states them, prints each
with the number that decides it, and prints PENDING for anything whose
artifact is missing rather than filling a gap. Nothing here re-runs an arm or
produces a win rate: it is offline, on frozen checkpoints and frozen logs.

THE ONE JUDGEMENT THIS SCRIPT MAKES is the tie clause, and it is mechanical:
if the two arms' critic srank99/width fractions differ by less than the
ACROSS-LANE SPREAD inside either trio, the read is UNRESOLVED and licenses
nothing in either direction. Three lanes per arm is what we have.
"""
import argparse
import math
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "configs/eval/mech200m.yaml"
# The finals, by lane tag -> (arm, seed, step). The steps are the pinned ones
# in configs/eval/monster_reads.yaml and ladder_r5.yaml; they are READ from
# the plan's lane prefixes on disk rather than retyped.
FINALS = {
    "w104": ("w", 104, 200000000), "w112": ("w", 112, 200000012),
    "w120": ("w", 120, 200000003),
    "l128": ("l2lam", 128, 200000046), "l136": ("l2lam", 136, 200000007),
    "l144": ("l2lam", 144, 200000006),
    "h104": ("h100", 104, 100000027), "h112": ("h100", 112, 100000008),
    "h120": ("h100", 120, 100000080),
}
WIDTH = {"w": 1024, "l2lam": 384, "h100": 384}


def load(out: Path, kind: str, tag: str, shared: bool) -> pd.DataFrame | None:
    p = out / f"{kind}_{tag}{'_shared' if shared else ''}.csv"
    return pd.read_csv(p) if p.exists() else None


def trio(out: Path, arm: str, shared: bool, kind: str = "effective_rank"):
    """Every final-checkpoint row for one arm, one obs protocol."""
    rows = []
    for tag, (a, seed, step) in FINALS.items():
        if a != arm:
            continue
        df = load(out, kind, tag, shared)
        if df is None:
            continue
        sub = df[(df.seed == seed) & (df.step == step)]
        if len(sub):
            rows.append(sub.assign(tag=tag, arm=arm))
    return pd.concat(rows, ignore_index=True) if rows else None


def fmt(x, nd=4):
    return "PENDING" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/mech200m")
    args = ap.parse_args()
    out = REPO / args.out
    plan = yaml.safe_load(open(PLAN))

    print("=" * 78)
    print("mech200m READOUT — [RWL-3]'s MECHANISM CO-PRIMARY, graded against its")
    print("own pre-stated branches (configs/eval/mech200m.yaml). CREDITS NOTHING")
    print("BY ITSELF: it decides whether the wide critic MAY be credited on the")
    print("already-banked off-FP@20 and vs-SH numbers.")
    print("=" * 78)

    # ---------------------------------------------------------------- M1
    # THE LAYER TRAP, found 2026-09-16 and the reason this section reports the
    # WHOLE stack. `effective_rank_*.csv`'s `srank99_ctx` is the hook on
    # net.ctx_net, i.e. the stack's OUTPUT layer only, while the dormant table
    # carried `ctx_net.1`, the FIRST layer -- so the first version of this
    # readout compared the wide critic's OUTPUT rank against the narrow ones'
    # FIRST-layer dormancy and called it a ceiling. The two arms collapse at
    # OPPOSITE ENDS of the stack, so one layer cannot answer [RWL-3]'s question.
    # `--layer-ranks` now records srank99 / fraction-of-width per post-ReLU
    # layer and both are printed.
    print("\n## M1 — critic ctx srank99 AS A FRACTION OF WIDTH (the PRIMARY read)\n")
    print("Reported for EVERY layer of the critic's value stack. ctx_net.1 is the")
    print("FIRST hidden layer, ctx_net.3 the OUTPUT layer the scalar head reads.\n")
    verdicts = {}
    for shared in (True, False):
        proto = "SHARED pooled obs (the cross-arm read)" if shared else "each lane's OWN obs (D22 protocol)"
        print(f"--- {proto}")
        per_layer = {}
        for arm in ("w", "l2lam", "h100"):
            t = trio(out, arm, shared, kind="dormant")
            if t is None or "srank_frac" not in (t.columns if t is not None else []):
                print(f"  {arm:6s} PENDING (no dormant csv with --layer-ranks)")
                continue
            c = t[(t.part == "critic") & (t.layer.str.startswith("ctx_net"))]
            for layer, g in c.groupby("layer"):
                width = int(g.n.iloc[0])
                per = ", ".join(f"{r.tag} {int(r.srank99)}" for _, r in g.iterrows())
                per_layer.setdefault(layer, {})[arm] = (
                    g.srank_frac.mean(), g.srank_frac.std(), g.srank99.mean(), g.srank99.std(), width)
                print(f"  {arm:6s} {layer:10s} width {width:5d}  srank99 [{per}]  "
                      f"mean {g.srank99.mean():6.1f}  FRACTION {g.srank_frac.mean():.4f} "
                      f"(across-lane sd {g.srank_frac.std():.4f})")
        for layer, fr in sorted(per_layer.items()):
            if "w" not in fr or "l2lam" not in fr:
                continue
            dfrac = fr["w"][0] - fr["l2lam"][0]
            spread = max(fr["w"][1], fr["l2lam"][1])
            dabs = fr["w"][2] - fr["l2lam"][2]
            if abs(dfrac) < spread:
                v = "UNRESOLVED (delta < the across-lane spread)"
            elif dfrac > 0:
                v = "fraction HOLDS/RISES on W — width live at this layer"
            else:
                v = "fraction FALLS on W — capacity idle at this layer"
            print(f"  => {layer}: W - L2LAM fraction {dfrac:+.4f} (spread {spread:.4f}), "
                  f"absolute srank99 {dabs:+.1f} -> {v}")
            verdicts[(layer, "shared" if shared else "own")] = (dfrac, spread, dabs, v)
        print()
    layers = sorted({l for l, _ in verdicts})
    for layer in layers:
        a, b = verdicts.get((layer, "shared")), verdicts.get((layer, "own"))
        if a and b:
            print(f"  SIGN AGREEMENT at {layer} between the two obs protocols: "
                  f"{'YES' if (a[0] > 0) == (b[0] > 0) else 'NO — the shared pass governs (plan)'}")

    # ---------------------------------------------------------------- M2
    print("\n## M2 — dormant fraction at tau 0.025 and 0.1, critic ctx layers\n")
    for shared in (True, False):
        proto = "SHARED" if shared else "own"
        for arm in ("w", "l2lam", "h100"):
            t = trio(out, arm, shared, kind="dormant")
            if t is None:
                print(f"  {proto:6s} {arm:6s} PENDING")
                continue
            c = t[(t.part == "critic") & (t.layer.str.startswith("ctx_net"))]
            if c.empty:
                print(f"  {proto:6s} {arm:6s} PENDING (no critic ctx layers)")
                continue
            g = c.groupby("layer")[["tau025", "tau100"]].mean()
            per = "; ".join(f"{l} tau.025 {r.tau025:.3f} tau.1 {r.tau100:.3f}"
                            for l, r in g.iterrows())
            print(f"  {proto:6s} {arm:6s} {per}")
        print()
    print("  A HIGH dormant fraction and a LOW srank at the SAME layer are the same")
    print("  fact seen twice. Read them layer by layer against M1 above, never across")
    print("  layers -- doing that is what produced this readout's first, wrong verdict.")

    # ---------------------------------------------------------------- M3/M4/M5
    tail_p = out / "history_tail.csv"
    if not tail_p.exists():
        print("\n## M3/M4/M5 — PENDING (run scripts/mech200m_history.py)")
    else:
        tl = pd.read_csv(tail_p)

        def tmean(arm, metric):
            x = tl[(tl.arm == arm) & (tl.metric == metric)]
            return (x["mean"].mean(), x["mean"].std(), len(x)) if len(x) else (float("nan"),) * 3

        print("\n## M3 — loss/explained_variance (tail = last 5% of updates)\n")
        for arm in ("w", "l2lam", "h100"):
            m, sd, k = tmean(arm, "loss/explained_variance")
            print(f"  {arm:6s} {fmt(m)} (across-lane sd {fmt(sd)}, {k} lanes)")
        print("\n  DISCLOSURE, verbatim from [RWL-3]: EV is 'comparable ONLY within a")
        print("  trio: lambda 1.0 targets carry the outcome noise, so L2LAM's EV reads")
        print("  far lower by construction'. The L2LAM column is therefore NOT evidence")
        print("  about the critic. W vs h100 IS a like-for-like pair (both TD targets at")
        print("  gae_lambda < 1) and is what the pre-reg's 'does the 0.59 plateau move'")
        print("  question asks about.")

        print("\n## M4 — loss/adv_std (the L2LAM MANIPULATION CHECK, not a lever read)\n")
        w_, _, _ = tmean("w", "loss/adv_std")
        l_, _, _ = tmean("l2lam", "loss/adv_std")
        for arm in ("w", "l2lam", "h100"):
            m, sd, k = tmean(arm, "loss/adv_std")
            print(f"  {arm:6s} {fmt(m)} (across-lane sd {fmt(sd)}, {k} lanes)")
        if not math.isnan(w_) and not math.isnan(l_):
            print(f"\n  GATE, verbatim: 'must sit materially higher on L2LAM or lambda")
            print(f"  did not take'. L2LAM/W = {l_ / w_:.2f}x -> "
                  f"{'PASSES — lambda took' if l_ > w_ * 1.2 else 'FAILS — lambda did NOT take, and the L2LAM arm did not do what it was built to do'}.")

        print("\n## M5 — l2init anchor distances (ACTOR-side only; see the known gap)\n")
        for metric in sorted({m for m in tl.metric if m.startswith("l2init/")}):
            wm, wsd, _ = tmean("w", metric)
            lm, lsd, _ = tmean("l2lam", metric)
            print(f"  {metric.split('_', 2)[-1]:16s} W {fmt(wm)} (sd {fmt(wsd)})   "
                  f"L2LAM {fmt(lm)} (sd {fmt(lsd)})   delta {fmt(wm - lm)}")
        print("\n  KNOWN GAP, stated in the plan before the read: every logged anchor is")
        print("  ACTOR-side and there is NO critic anchor metric, nor a logged critic")
        print("  pre-activation norm. M5 reads whether L2 bit equally hard on the two")
        print("  arms' ACTORS. It cannot speak about the critic.")

    # ---------------------------------------------------------------- M6
    print("\n## M6 — the third branch: 'EV and norms move but win rate does not'\n")
    print("  Graded against numbers ALREADY BANKED, not re-run here:")
    print("    vs SH (locked protocol, n=9000/arm): GW 0.8217, GL 0.7778, "
          "100M A0 0.78867")
    print("    off FP@20 (same session, n=9000/arm): W 0.5417, L2LAM 0.4481, "
          "100M 0.4952")
    print("  Win rate DID move between the arms and against the 100M baseline, so the")
    print("  branch cannot fire in its across-arm sense. Its within-W sense is whether")
    print("  the 100M->200M horizon moved EV without moving the win rate: read M3's W")
    print("  vs h100 row against the +0.033 (vs SH) and +0.046 (off FP@20) deltas.")

    # ---------------------------------------------------------------- M7
    # The credit line, COMPUTED rather than asserted -- the plan says the
    # seed-clustered half of the larger-of clause is computed here, from the
    # per-lane finals on disk, not assumed.
    print("\n## M7 — the credit line, both halves, from the per-lane finals\n")
    import glob
    import json
    import statistics

    def lanes_offfp(tags):
        vals = []
        for t in tags:
            p = out.parent / "monster_reads_offfp" / f"{t}.json"
            if p.exists():
                vals.append(json.load(open(p))["our_win_rate"])
        return vals

    def lanes_vssh(tags):
        vals = []
        for t in tags:
            p = out.parent / "monster_reads" / f"{t}.final.json"
            if p.exists():
                vals.append(json.load(open(p))["eval/win_rate"])
        return vals

    def line(name, A, B, nA, nB, labA, labB):
        if len(A) < 2 or len(B) < 2:
            print(f"  {name}: PENDING (need per-lane finals on disk)")
            return
        pA, pB = sum(A) / len(A), sum(B) / len(B)
        d = pA - pB
        se_b = math.sqrt(pA * (1 - pA) / nA + pB * (1 - pB) / nB)
        se_c = math.sqrt((statistics.stdev(A) / math.sqrt(len(A))) ** 2
                         + (statistics.stdev(B) / math.sqrt(len(B))) ** 2)
        se = max(se_b, se_c)
        ok = d >= 0.025 and d >= 2 * se
        print(f"  {name}")
        print(f"    {labA} {pA:.5f} {['%.5f' % x for x in A]}")
        print(f"    {labB} {pB:.5f} {['%.5f' % x for x in B]}")
        print(f"    delta {d:+.4f}   se_binom {se_b:.4f}   se_seed-clustered {se_c:.4f}"
              f"   LARGER {se:.4f}   ({d / se:.2f} se)")
        print(f"    floor >= +0.025 {'PASS' if d >= 0.025 else 'FAIL'}; "
              f">= 2*se_diff {'PASS' if d >= 2 * se else 'FAIL'}  ==> "
              f"{'MEETS THE CREDIT LINE' if ok else 'DOES NOT MEET IT'}\n")

    line("off FP@20 — W singles vs the 100M re-draw (same session)",
         lanes_offfp(["gw104f", "gw112f", "gw120f"]),
         lanes_offfp(["g104r", "g112r", "g120r"]), 9000, 9000, "W", "100M")
    line("off FP@20 — W singles vs L2LAM singles (matched fleet, horizon, L2)",
         lanes_offfp(["gw104f", "gw112f", "gw120f"]),
         lanes_offfp(["gl128f", "gl136f", "gl144f"]), 9000, 9000, "W", "L2LAM")
    line("vs SH — GW vs the banked 100M greedy A0",
         lanes_vssh(["gw_w104", "gw_w112", "gw_w120"]),
         [0.78933, 0.78233, 0.79433], 9000, 9000, "GW", "A0")
    line("vs SH — GW vs GL (matched fleet, horizon, L2)",
         lanes_vssh(["gw_w104", "gw_w112", "gw_w120"]),
         lanes_vssh(["gl_l128", "gl_l136", "gl_l144"]), 9000, 9000, "GW", "GL")
    line("vs SH — E3W (the ladder object) vs the banked 100M ENS3 floor",
         lanes_vssh(["e3w_b0", "e3w_b1", "e3w_b2"]),
         [0.82667, 0.81467, 0.82933], 9000, 9000, "E3W", "ENS3-100M")
    print("  WHAT NO CONTRAST ABOVE ISOLATES: WIDTH ALONE. W vs the 100M baseline")
    print("  bundles width + L2-toward-init + the 100M->200M horizon; W vs L2LAM")
    print("  bundles width + the value TARGET. Width is the only factor common to")
    print("  both, and M1 shows it is USED -- but the licensed credit is for the")
    print("  RECIPE AS SHIPPED, not for width as a separable lever.")

    print("\n" + "=" * 78)
    print("WHAT THIS READ MAY DO (plan, decision.may): license or withhold a CREDIT")
    print("for the wide critic on the already-banked numbers, and rank the next")
    print("fleet's shape. RULE 6: an unresolved or null mechanism does NOT kill the")
    print("lever; only a measured, quantified CEILING does.")
    print("=" * 78)


if __name__ == "__main__":
    main()

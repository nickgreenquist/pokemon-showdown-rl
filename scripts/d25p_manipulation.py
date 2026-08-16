"""R-4: the PLACEBO §6 manipulation check — did the shuffle actually destroy
the label information, and did the placebo head nevertheless train?

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d25p_manipulation.py

Sibling of `scripts/d25_manipulation.py`, which is deliberately NOT modified:
it produced the banked §6 treatment letter (median g 0.7055) and must stay
reproducible bit-for-bit. Both scripts share ONE estimator, imported from
`d25_gates` — g is computed here exactly as it is there, so g_P and the
treatment g are unit-compatible by construction.

    g_P = (A1 - NLL_head) / (A1 - A3)

per placebo lane, on THAT LANE'S OWN 300-episode mirror tape
(`results/d25p/oppact_s{57..61}.npz`, same collector as the treatment tapes:
`results/d25/scripts/collect_oppact.py`). A1 (mask-renormalised class marginal)
and A3 (per-member oracle floor — the mean entropy of the label generator's own
pushed-forward distribution) are RE-DERIVED per lane and per split, over the
same 8 battle-level 70/30 splits as §5. The head is never fitted to the tape.

TWO VIEWS OF ONE STATISTIC (header R-4; g_P and NLL_head are algebraically the
same read, review R1-16 — the second view exists to disambiguate the negative
branch):

  VIEW 1 — |g_P|, the information that survived the shuffle:
      |g_P| <= 0.02              SHUFFLE CONFIRMED
      0.02 < |g_P| < 0.10        RESIDUAL — disclosed, caveats R-1
      |g_P| >= 0.10              LEAK — R-1/R-2/R-3/R-5's placebo letters VOID
      materially negative        DERANGEMENT check, same VOID
  The 0.02 band is in g units and is 10-16x the measured legality residual
  (~0.0012-0.0020 g units, header l93-95).

  VIEW 2 — NLL_head against the floor, per lane:
      |NLL_head - A1| <= 0.02    TRAINED-TO-FLOOR — the DESIGNED outcome:
                                 "the head learned everything its task
                                 contained, which was nothing beyond
                                 legality; a real aux gradient was injected
                                 for 12M steps". Report beside lane health.
      NLL_head >= A0 - 0.05      NEVER-TRAINED — arm VOID
      A1 + 0.05 < NLL_head
                 < A0 - 0.05     PARTIALLY-TRAINED (review R2-11) — the dose
                                 is not matched; R-1 is DOSE-CAVEATED, not
                                 VOID, and P3's dose read governs the wording.
  A0 (uniform-over-legal, the never-trained level) is MEASURED here per lane
  rather than assumed; the treatment tapes put it at 1.773-1.780 and the live
  init at 1.736, so a placebo A0 far outside that is itself a finding.

TRAJECTORY: read at 3M / 6M / 12M on the same tape (labels and A1/A3 do not
depend on the checkpoint). A RISING |g_P| across the three is the LEAK
SIGNATURE (review R2-17) — a shuffle that leaks gets MORE exploitable as the
head trains, while a true zero-information placebo stays flat at chance.

AGGREGATION, NAMED BECAUSE THE HEADER DOES NOT NAME IT: R-4 fixes the bands
but not the across-lane aggregator. This script inherits §6's rule — the
5-lane MEDIAN is the statistic — and prints the per-lane values and the
worst-lane |g_P| beside it as recorded secondaries, so a maintainer who wants
the max to govern can read it off the same output without a re-run.

HARD FAIL (inherited from §6, unchanged): g > 1.0 has no pool-mixture escape
on a MIRROR tape, where the oracle evaluated IS the actor that generated every
label — beating it means the label or the timing is wrong.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from d25_gates import NSPL, build, marginal, nll, split_by_battle  # noqa: E402
from d25_manipulation import head_nll_rows  # noqa: E402
from eval_checkpoint import _load_showdown_agent  # noqa: E402
from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402

LANES = (57, 58, 59, 60, 61)
RUN_PREFIX = "showdown_sp_actpred12m_placebo_s"
TAPE_DIR = REPO / "results/d25p"
STEPS = (3_000_000, 6_000_000, 12_000_000)

CONFIRM = 0.02        # |g_P| <= this -> SHUFFLE CONFIRMED
LEAK = 0.10           # |g_P| >= this -> LEAK (or DERANGEMENT if negative)
FLOOR_KL = 0.02       # |NLL_head - A1| <= this -> TRAINED-TO-FLOOR
MIDDLE = 0.05         # the PARTIALLY-TRAINED cell's margins
A0_REF = (1.773, 1.780)   # treatment-tape reference, for disclosure only


def uniform_over_legal(m6, idx):
    """A0: the never-trained level — NLL of a uniform distribution over the
    legal classes of each row. Measured per split, never assumed."""
    return float(np.log(m6[idx].sum(1)).mean())


def classify_g(g):
    """VIEW 1. Sign matters: the negative branch is a derangement, not a leak."""
    if g <= -LEAK:
        return "DERANGEMENT"
    if abs(g) >= LEAK:
        return "LEAK"
    if abs(g) <= CONFIRM:
        return "SHUFFLE CONFIRMED"
    return "RESIDUAL"


def classify_head(nll_head, a1, a0):
    """VIEW 2. The header leaves (A1 + 0.02, A1 + 0.05] unnamed; it is reported
    as NEAR-FLOOR rather than silently folded into either neighbour."""
    if nll_head >= a0 - MIDDLE:
        return "NEVER-TRAINED"
    if abs(nll_head - a1) <= FLOOR_KL:
        return "TRAINED-TO-FLOOR"
    if nll_head > a1 + MIDDLE:
        return "PARTIALLY-TRAINED"
    if nll_head < a1 - MIDDLE:
        return "BELOW-FLOOR"
    return "NEAR-FLOOR (unnamed cell — disclose)"


def rising(traj):
    """The leak signature: |g_P| strictly increasing over 3M -> 6M -> 12M."""
    a = [abs(traj[s]) for s in STEPS]
    return all(a[i] < a[i + 1] for i in range(len(a) - 1))


def lane_result(seed, tape_dir=TAPE_DIR, run_prefix=RUN_PREFIX):
    """One lane: g_P at each step, plus the 12M NLL_head / A1 / A3 / A0."""
    run = REPO / f"{run_prefix}{seed}"
    run = run if run.exists() else REPO / f"runs/{run_prefix}{seed}"
    D = build(Path(tape_dir) / f"oppact_s{seed}.npz", run / "checkpoint.pt")
    y6, m6, q6, battle, obs1 = D["y6"], D["m6"], D["q6"], D["battle"], D["obs1"]

    rows_nll = {}
    for step in STEPS:
        if step == 12_000_000:
            agent = D["agent"]                       # build loaded the final
        else:
            ck = load_checkpoint(run / f"ckpt_{step:09d}.pt")
            agent = _load_showdown_agent(ck, Config(**ck["config"]))
        rows_nll[step] = head_nll_rows(agent, obs1, y6, m6)

    ent_q6 = -(q6 * np.log(q6)).sum(1)
    g = {step: [] for step in STEPS}
    a1s, a3s, a0s, nh = [], [], [], []
    for sp in range(NSPL):
        tr, te = split_by_battle(battle, sp)
        A1 = nll(marginal(y6, m6, 6, tr), y6, te)
        A3 = float(ent_q6[te].mean())
        a1s.append(A1); a3s.append(A3); a0s.append(uniform_over_legal(m6, te))
        for step in STEPS:
            NLLh = float(rows_nll[step][te].mean())
            g[step].append((A1 - NLLh) / (A1 - A3))
            if step == 12_000_000:
                nh.append(NLLh)

    gm = {step: float(np.mean(g[step])) for step in STEPS}
    return dict(
        n=D["n"], keep=D["keep"], g_by_step=gm, g12=gm[12_000_000],
        g12_split_sd=float(np.std(g[12_000_000], ddof=1)),
        A1=float(np.mean(a1s)), A3=float(np.mean(a3s)), A0=float(np.mean(a0s)),
        NLL_head=float(np.mean(nh)), rising=rising(gm))


def main() -> None:
    ap = argparse.ArgumentParser(description="R-4: placebo §6 manipulation check")
    ap.add_argument("--tape-dir", default=str(TAPE_DIR))
    ap.add_argument("--out", default=str(TAPE_DIR / "manipulation_placebo.json"))
    ap.add_argument("--lanes", default=",".join(str(s) for s in LANES))
    args = ap.parse_args()
    lanes = [int(x) for x in args.lanes.split(",") if x.strip()]

    detail = {}
    for s in lanes:
        r = lane_result(s, tape_dir=Path(args.tape_dir))
        detail[f"s{s}"] = r
        gm = r["g_by_step"]
        print(f"s{s}: n={r['n']} (kept {r['keep']*100:.1f}%)  A1 {r['A1']:.4f}  "
              f"A3 {r['A3']:.4f}  A0 {r['A0']:.4f}  NLL_head {r['NLL_head']:.4f} "
              f"[{classify_head(r['NLL_head'], r['A1'], r['A0'])}]\n"
              f"      g_P@3M/6M/12M {gm[3_000_000]:+.4f}/{gm[6_000_000]:+.4f}/"
              f"{gm[12_000_000]:+.4f}"
              f"{'  <-- RISING |g_P| (leak signature)' if r['rising'] else ''}",
              flush=True)
        if r["g12"] > 1.0:
            raise SystemExit(
                f"HARD FAIL: s{s} g_P = {r['g12']:.4f} > 1.0 on a MIRROR tape "
                "(oracle == generator) — label or timing is wrong.")

    g12 = [detail[f"s{s}"]["g12"] for s in lanes]
    med = float(np.median(g12))
    worst = max(g12, key=abs)
    verdict = classify_g(med)
    heads = [classify_head(detail[f"s{s}"]["NLL_head"], detail[f"s{s}"]["A1"],
                           detail[f"s{s}"]["A0"]) for s in lanes]
    n_rising = sum(detail[f"s{s}"]["rising"] for s in lanes)

    print(f"\nVIEW 1 — {len(lanes)}-lane MEDIAN g_P = {med:+.4f} -> **{verdict}**")
    print(f"  bands: |g_P| <= {CONFIRM} CONFIRMED · < {LEAK} RESIDUAL · "
          f">= {LEAK} LEAK · <= -{LEAK} DERANGEMENT")
    print(f"  recorded secondaries: worst lane |g_P| = {abs(worst):.4f} "
          f"(signed {worst:+.4f}); per-lane "
          + " ".join(f"s{s}:{detail[f's{s}']['g12']:+.4f}" for s in lanes))
    print(f"  RISING |g_P| on {n_rising}/{len(lanes)} lanes "
          f"({'LEAK SIGNATURE — investigate before any letter' if n_rising > len(lanes) // 2 else 'not the leak signature'})")
    print(f"\nVIEW 2 — NLL_head vs floor (A0 reference {A0_REF[0]}-{A0_REF[1]}):")
    for s, h in zip(lanes, heads):
        d = detail[f"s{s}"]
        print(f"  s{s}: NLL_head {d['NLL_head']:.4f}  A1 {d['A1']:.4f}  "
              f"(delta {d['NLL_head'] - d['A1']:+.4f})  A0 {d['A0']:.4f}  -> {h}")
    print(f"  {heads.count('TRAINED-TO-FLOOR')}/{len(lanes)} TRAINED-TO-FLOOR "
          "(the designed outcome)")

    if verdict in ("LEAK", "DERANGEMENT"):
        print("\n**B7 FIRES: the arm is VOID** — R-1/R-2/R-3/R-5's placebo "
              "letters do not stand. Nothing downstream is adjudicated.")
    elif "NEVER-TRAINED" in heads:
        print("\n**B7 FIRES (never-trained): arm VOID** — the head never left "
              "the init level, so no aux gradient was injected.")
    elif "PARTIALLY-TRAINED" in heads:
        print("\nR-1 is DOSE-CAVEATED (not void, review R2-11); P3's dose read "
              "governs the wording.")

    print("\nThis script decides R-4 ONLY. B7 precedes B6 and the R-1 x R-2 "
          "grid; run scripts/d25_grade.py --placebo results/d25p for the rest.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        json.dump(dict(lanes=lanes, median_g=med, worst_g=worst,
                       verdict=verdict, head_verdicts=dict(zip(
                           [f"s{s}" for s in lanes], heads)),
                       n_rising=n_rising, bands=dict(
                           confirm=CONFIRM, leak=LEAK, floor_kl=FLOOR_KL,
                           middle=MIDDLE),
                       detail=detail), f, indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

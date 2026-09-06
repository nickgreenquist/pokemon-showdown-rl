#!/usr/bin/env python
"""The gen-4 Wang-recipe PRIMARY read, graded exactly as configs/gen4_wang50m.yaml
pre-registers it — committed BEFORE any final-checkpoint battle lands, so the
branch is read off the header and never decided after.

    python scripts/gen4_wang50m_readout.py --selftest
    python scripts/gen4_wang50m_readout.py results/gen4_wang50m/vs_sh_s200.json \
        results/gen4_wang50m/vs_sh_s208.json results/gen4_wang50m/vs_sh_s216.json

Inputs: scripts/eval_checkpoint.py's JSON reports (one per lane, --episodes 3000,
--out ...). What is checked, per the header's N_EFF block: n_eff == 3000 per
lane (every episode carried an env-supplied outcome), `eval/win_rate ==
wins_from_returns` EXACTLY (nothing is shaped), and mask_desyncs are printed
beside each number. What is computed: the EQUAL-WEIGHT MEAN of per-lane finals
(the named aggregator), the pooled-over-battles proportion (recorded, never
governs), the pooled-binomial se and the seed-clustered se (the LARGER is quoted
beside the pooled number), the tie rate (D-TIE), and the two branches:
  MILESTONE  M-YES iff pooled >= 0.60   (JOURNEY step 3)
  STEP 5     S5-MATCHED iff pooled >= THRESHOLD (0.756 as ruled; RW-1 may re-pin)
  CELL K     k <= 2 lanes -> DESCRIPTIVE ONLY, neither branch fires
The sentences printed carry the disclosures the header requires ADJACENT:
network-alone / weaker-number, HIS CURVE (dose named first as ruled), and the
deviation list. The thresholds are READ FROM THE SIDECAR
(configs/gen4_wang50m.prereg.yaml), so a ratification re-pin flows through.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SIDECAR = REPO / "configs/gen4_wang50m.prereg.yaml"

DEVIATIONS = "D-DOSE, D-IMPL, D-NET, D-ACT, D-ENC, D-COLL, D-SH, D-TIE"
HIS_CURVE = ("his Figure 4.1 reaches 0.786 at ≈ 30M of his 150M TOTAL steps (≈ 15M per seat, "
             "≈ 30% of ours) and §4.1 reports ~80% by 40M total, so dose is named first as "
             "ruled but is NOT the cause his own curve supports; D-ENC and D-NET are")
WEAKER = ("0.786 is his NETWORK-ALONE and WEAKER published number — Figure 4.1 digitizes to "
          "≈ 0.836 endpoint / ≈ 0.849 peak, unreconciled")


def load_lane(path: Path) -> dict:
    r = json.loads(path.read_text())
    wr = float(r["eval/win_rate"])
    wfr = float(r["wins_from_returns"])
    n = int(r["episodes"])
    n_eff = len(r["returns"]) if "returns" in r else n
    return {
        "path": str(path), "run_name": r.get("run_name"), "step": r.get("step"),
        "win_rate": wr, "wins_from_returns": wfr, "tie_rate": float(r.get("ties_from_returns", 0.0)),
        "n": n, "n_eff": n_eff, "mask_desyncs": int(r.get("mask_desyncs", 0)),
        "env_id": r.get("env_id"),
    }


def grade(lanes: list[dict], side: dict) -> dict:
    p = side["primary"]
    thr_m, thr_s5 = float(p["milestone_threshold"]), float(p["step5_threshold"])
    n_req = int(side["battery"]["L5"]["n_per_lane"])
    problems = []
    for L in lanes:
        if L["env_id"] != "ShowdownGen4-v0":
            problems.append(f"{L['path']}: env_id {L['env_id']!r} is not the gen-4 env")
        if L["n_eff"] != n_req or L["n"] != n_req:
            problems.append(f"{L['path']}: n_eff {L['n_eff']} / n {L['n']} != {n_req} — lane PENDING (re-run from zero)")
        if L["win_rate"] != L["wins_from_returns"]:
            problems.append(f"{L['path']}: win_rate {L['win_rate']} != wins_from_returns "
                            f"{L['wins_from_returns']} — the sign-inversion cross-check FAILED")
    k = len(lanes)
    rates = [L["win_rate"] for L in lanes]
    pooled = sum(rates) / k if k else float("nan")                      # the named aggregator
    over_battles = sum(r * L["n_eff"] for r, L in zip(rates, lanes)) / max(1, sum(L["n_eff"] for L in lanes))
    se_bin = math.sqrt(sum(r * (1 - r) / L["n_eff"] for r, L in zip(rates, lanes))) / k if k else float("nan")
    if k >= 2:
        mean = pooled
        s = math.sqrt(sum((r - mean) ** 2 for r in rates) / (k - 1))
        se_clus = s / math.sqrt(k)
    else:
        se_clus = float("nan")
    se_gov = max(se_bin, se_clus) if k >= 2 else se_bin
    tie = sum(L["tie_rate"] for L in lanes) / k if k else float("nan")
    out = {
        "k": k, "per_lane": rates, "pooled_equal_weight": pooled, "pooled_over_battles": over_battles,
        "se_binomial": se_bin, "se_clustered": se_clus, "se_governing": se_gov, "tie_rate": tie,
        "mask_desyncs": [L["mask_desyncs"] for L in lanes], "problems": problems,
        "thresholds": {"milestone": thr_m, "step5": thr_s5},
    }
    if problems:
        out["milestone"] = out["step5"] = "BLOCKED"
        return out
    if k <= 2:
        out["milestone"] = out["step5"] = "CELL K (descriptive only; maintainer ruling)"
        return out
    # Inclusive one-sided boundaries, read at 1e-9 so three lanes at exactly the
    # threshold (which pool to 0.7559999… in float64) land on the >= side as the
    # header says ("boundary = 0.756 -> S5-MATCHED").
    eps = 1e-9
    out["milestone"] = "M-YES" if pooled >= thr_m - eps else "M-NO"
    out["step5"] = "S5-MATCHED" if pooled >= thr_s5 - eps else "S5-SHORT"
    out["gap_step5_in_se"] = (pooled - thr_s5) / se_gov if se_gov > 0 else float("nan")
    return out


def sentences(g: dict) -> list[str]:
    if g["milestone"] in ("BLOCKED",):
        return ["BLOCKED: " + "; ".join(g["problems"])]
    if g["milestone"].startswith("CELL K"):
        return [f"CELL K: k = {g['k']} lanes; the primary is DESCRIPTIVE ONLY "
                f"(pooled {g['pooled_equal_weight']:.4f}); the milestone is UNDECIDED and routes "
                "to a maintainer ruling (spare seed, or accept a k=2 descriptive readout); the README row WAITS."]
    pooled, se = g["pooled_equal_weight"], g["se_governing"]
    lines = [
        f"PRIMARY: pooled vs-SH {pooled:.4f} (equal-weight mean of {g['k']} lanes "
        f"{', '.join(f'{r:.4f}' for r in g['per_lane'])}; pooled-over-battles {g['pooled_over_battles']:.4f} recorded), "
        f"se {se:.4f} (the larger of binomial {g['se_binomial']:.4f} / clustered {g['se_clustered']:.4f}), "
        f"tie rate {g['tie_rate']:.4f} (D-TIE), mask_desyncs {g['mask_desyncs']}.",
    ]
    if g["milestone"] == "M-YES":
        lines.append(f"M-YES: the gen-4 pipeline LEARNS — pooled {pooled:.4f} >= {g['thresholds']['milestone']} "
                     "(JOURNEY step 3's milestone); the README row lands once every leg is in.")
    else:
        lines.append(f"M-NO: pooled {pooled:.4f} < {g['thresholds']['milestone']}. Candidate causes IN THE PRE-REGISTERED "
                     f"ORDER: D-DOSE (named first as ruled — {HIS_CURVE}), D-ENC, D-NET, the value clip's per-update "
                     "ceiling (0.0184; 2,504 vs his ≈ 3,756 updates), the harvest ratio (H1), the LR schedule "
                     "(realized minimum lr0/26.99). Routes to a MAINTAINER RULING on the next run.")
    if g["step5"] == "S5-MATCHED":
        lines.append(f"S5-MATCHED: pooled {pooled:.4f} >= {g['thresholds']['step5']} — matched Wang's NETWORK-ALONE 0.786 "
                     f"(one-sided, the ruled floor) at 2/3 of his per-seat dose, with {DEVIATIONS} disclosed; {WEAKER}. "
                     "A read between 0.756 and 0.836 is 'matched' under this pre-reg and is NOT a reproduction of his curve. "
                     "This run credits nothing.")
    else:
        lines.append(f"S5-SHORT: pooled {pooled:.4f} < {g['thresholds']['step5']} by {-g['gap_step5_in_se']:.2f} se — did not match, "
                     f"at 2/3 of his per-seat dose ({HIS_CURVE}); then {DEVIATIONS}. {WEAKER}. Not a re-run on this "
                     "header: the follow-up is a pre-registered lever run or a dose-matched run, a maintainer decision.")
    return lines


def selftest() -> None:
    side = yaml.safe_load(SIDECAR.read_text())

    def lane(wr, n=3000, wfr=None, ties=0.01, env="ShowdownGen4-v0"):
        return {"path": f"lane{wr}", "run_name": "x", "step": 50_000_000, "win_rate": wr,
                "wins_from_returns": wr if wfr is None else wfr, "tie_rate": ties, "n": n, "n_eff": n,
                "mask_desyncs": 0, "env_id": env}

    g = grade([lane(0.80), lane(0.79), lane(0.78)], side)
    assert g["milestone"] == "M-YES" and g["step5"] == "S5-MATCHED", g
    assert abs(g["pooled_equal_weight"] - 0.79) < 1e-12 and abs(g["pooled_over_battles"] - 0.79) < 1e-12
    g = grade([lane(0.70), lane(0.72), lane(0.69)], side)
    assert g["milestone"] == "M-YES" and g["step5"] == "S5-SHORT" and g["gap_step5_in_se"] < 0
    g = grade([lane(0.50), lane(0.55), lane(0.52)], side)
    assert g["milestone"] == "M-NO" and g["step5"] == "S5-SHORT"
    g = grade([lane(0.756), lane(0.756), lane(0.756)], side)
    assert g["step5"] == "S5-MATCHED", "the boundary is >= (one-sided, inclusive)"
    g = grade([lane(0.7559), lane(0.7561), lane(0.7559)], side)
    assert g["step5"] == "S5-SHORT"
    g = grade([lane(0.80), lane(0.79)], side)
    assert g["milestone"].startswith("CELL K")
    g = grade([lane(0.80), lane(0.79, wfr=0.7899), lane(0.78)], side)
    assert g["milestone"] == "BLOCKED" and "sign-inversion" in g["problems"][0]
    g = grade([lane(0.80), lane(0.79, n=2999), lane(0.78)], side)
    assert g["milestone"] == "BLOCKED" and "PENDING" in g["problems"][0]
    g = grade([lane(0.80, env="Showdown-v0"), lane(0.79), lane(0.78)], side)
    assert g["milestone"] == "BLOCKED"
    # se: binomial at three lanes of 3000 ≈ 0.0044 at p ≈ 0.79; clustered is small at sd 0.01.
    g = grade([lane(0.80), lane(0.79), lane(0.78)], side)
    assert abs(g["se_binomial"] - math.sqrt(3 * 0.79 * 0.21 / 3000) / 3) < 2e-4
    assert abs(g["se_clustered"] - 0.01 / math.sqrt(3)) < 1e-9
    for s in sentences(g):
        assert "credits nothing" in s or "PRIMARY" in s or "M-YES" in s
    print("selftest OK: every cell of the milestone x step-5 partition, cell K, both BLOCKED paths, the inclusive boundary")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("lanes", nargs="*", help="eval_checkpoint JSON reports, one per lane")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", help="write the graded JSON here")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    if not args.lanes:
        ap.error("lane JSONs required (or --selftest)")
    side = yaml.safe_load(SIDECAR.read_text())
    lanes = [load_lane(Path(p)) for p in args.lanes]
    g = grade(lanes, side)
    g["lanes"] = lanes
    g["thresholds_from"] = str(SIDECAR)
    for s in sentences(g):
        print(s)
    if args.out:
        Path(args.out).write_text(json.dumps(g, indent=2) + "\n")
    return 0 if not g["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())

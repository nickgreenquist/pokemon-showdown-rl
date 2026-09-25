"""Read the FP@N calibration (configs/eval/fp_iter_calib.yaml) FROM DISK -- the rule is the
pre-reg header's, stated before any battle; every number in the readout is printed here.

    /opt/anaconda3/bin/python scripts/fp_iter_calib_read.py [--json-out results/fp_iter_calib/read.json]

Per arm, the R4 crash-forfeit rule verbatim: n_eff = seat-finished minus crash-forfeits (the
runner's relaunch count), our wins reduced by the same count; ties are non-wins. CAL20 is the
control (FP@20, k=1); CALN1..8 pool by plain sums into the FP@N side (every slice is the same
seat vs the same opponent). delta = WR(vs FP@N) - WR(vs FP@20); unpaired binomial se_diff, and
beside it the FP@N side's slice-clustered se -- the LARGER is the one the rule reads.
G2: Foul Play's own Winner tally must equal the seat's W/L/T on every arm.
"""

import argparse
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PRE = REPO / "configs" / "eval" / "fp_iter_calib.yaml"
OUT = REPO / "results" / "fp_iter_calib"
CALN = [f"CALN{i}" for i in range(1, 9)]
# draw -> (FP@20 control, FP@N slices); draw 2 = the tightening run (config header, SECOND DRAW)
DRAWS = {"1": ("CAL20", CALN), "2": ("CE20", [f"CEN{i}" for i in range(1, 9)])}
SEAT_OF = {"1": "GW104R (greedy w104)", "2": "E6RF (ENS6 of the R6 finals)"}
PHASE1_FPN_K8_TURN_RATE = 0.841   # readouts/FP_PARALLEL_ROI_READOUT.md, FP@N per-arm rate at k=8
VIS = re.compile(r"PROBE_VISITS t=([\d.]+) n=(\d+) ms=(\d+) i=\d+ visits=(\d+) .*?"
                 r"search_ms=(-?[\d.]+) iters_req=(\d+)")


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def arm_read(arm, pre):
    tag = arm.lower()
    seat = json.loads((OUT / f"{tag}.json").read_text())
    run = json.loads((OUT / f"{tag}.runner.json").read_text())
    cf = int(run["crash_forfeits"])
    n_eff = seat["battles_finished"] - cf
    wins = seat["our_wins"] - cf
    # G2: foul-play's own Winner lines, by name
    spec = pre["arms"][arm]
    wl = Counter()
    for line in open(OUT / f"{tag}.fp.stdout", errors="replace"):
        m = re.search(r"Winner: (\S+)", line)
        if m:
            wl[m.group(1)] += 1
    fp_says_seat = wl.get(spec["seat_username"], 0)
    fp_says_fp = wl.get(spec["fp_username"], 0)
    # G2 is two INDEPENDENT tallies agreeing. A crash-forfeited battle is a seat win foul-play
    # never logged (the runner's asymmetry, by design), so the seat's count less the runner's
    # crash forfeits must equal foul-play's own -- exactly; the raw comparison is kept beside it.
    g2_raw = (fp_says_seat == seat["our_wins"] and fp_says_fp == seat["foulplay_wins"])
    g2 = (fp_says_seat == seat["our_wins"] - cf and fp_says_fp == seat["foulplay_wins"])
    # the searches foul-play actually ran
    vis = defaultdict(list)
    for line in open(OUT / f"{tag}.fp.stdout", errors="replace"):
        m = VIS.search(line)
        if m:
            vis[(int(m.group(2)), int(m.group(3)))].append(
                (int(m.group(4)), float(m.group(5)), int(m.group(6))))
    return {
        "arm": arm, "n_finished": seat["battles_finished"], "crash_forfeits": cf, "n_eff": n_eff,
        "wins": wins, "ties": seat["ties"], "wr": wins / n_eff if n_eff else None,
        "g2_fp_tally_agrees": g2, "g2_raw_agrees": g2_raw,
        "fp_tally": {"seat": fp_says_seat, "fp": fp_says_fp},
        "seat_tally": {"seat": seat["our_wins"], "fp": seat["foulplay_wins"], "ties": seat["ties"]},
        "mean_turns": seat["mean_turns"], "sec_per_battle": seat["sec_per_battle"],
        "wall_clock_sec": seat["wall_clock_sec"],
        "declared_search_iterations": seat.get("declared_search_iterations"),
        "fp_budget_seen": run.get("fp_budget_seen"), "relaunches": run["relaunches"],
        "max_concurrent_live_battles": seat["max_concurrent_live_battles"],
        "gate_all_resolved": seat["gate_all_challenges_resolved"],
        "rl_git_sha": seat.get("rl_git_sha"), "rl_git_dirty": seat.get("rl_git_dirty"),
        "visits": vis,
    }


def visits_summary(vis_lists):
    out = {}
    for key in sorted({k for v in vis_lists for k in v}):
        rows = [r for v in vis_lists for r in v.get(key, [])]
        forced = [r for r in rows if r[0] <= 1000 and r[1] < 2.0]
        real = [r for r in rows if not (r[0] <= 1000 and r[1] < 2.0)]
        req = {r[2] for r in rows}
        out[f"n{key[0]}_x_{key[1]}ms"] = {
            "searches": len(rows), "forced_frac": round(len(forced) / len(rows), 4),
            "iters_req": sorted(req),
            "visits_p50": pct([r[0] for r in real], .5), "visits_p5": pct([r[0] for r in real], .05),
            "visits_p95": pct([r[0] for r in real], .95),
            "exactly_requested_frac": (round(sum(1 for r in real if r[0] == r[2]) / len(real), 4)
                                       if real and max(req) > 0 else None),
            "search_ms_p50": round(pct([r[1] for r in real], .5), 2),
            "search_ms_mean": round(st.mean(r[1] for r in real), 2),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default=str(OUT / "read.json"))
    ap.add_argument("--draws", default="1", help="comma list of draws to POOL, e.g. 1,2")
    args = ap.parse_args()
    pre = yaml.safe_load(open(PRE))
    draws = args.draws.split(",")
    ctrls = [arm_read(DRAWS[d][0], pre) for d in draws]
    slices = [arm_read(a, pre) for d in draws for a in DRAWS[d][1]
              if (OUT / f"{a.lower()}.json").exists()]
    # the controls pool into one FP@20 side (plain sums), exactly as the slices do
    c = dict(ctrls[0])
    if len(ctrls) > 1:
        for k in ("n_eff", "wins", "ties", "crash_forfeits", "n_finished", "wall_clock_sec", "relaunches"):
            c[k] = sum(x[k] for x in ctrls)
        c["mean_turns"] = sum(x["mean_turns"] * x["n_finished"] for x in ctrls) / c["n_finished"]
        c["g2_fp_tally_agrees"] = all(x["g2_fp_tally_agrees"] for x in ctrls)
        c["g2_raw_agrees"] = all(x["g2_raw_agrees"] for x in ctrls)
        c["arm"] = "+".join(x["arm"] for x in ctrls)
        c["visits"] = {k: [r for x in ctrls for r in x["visits"].get(k, [])]
                       for k in {k for x in ctrls for k in x["visits"]}}
    per_draw = {}
    for d in draws:
        cd = next(x for x in ctrls if x["arm"] == DRAWS[d][0])
        sd = [x for x in slices if x["arm"] in DRAWS[d][1]]
        if sd:
            pa, pb = cd["wins"] / cd["n_eff"], sum(x["wins"] for x in sd) / sum(x["n_eff"] for x in sd)
            per_draw[d] = {"wr_fp20": pa, "wr_fpn": pb, "delta": pb - pa,
                           "n": [cd["n_eff"], sum(x["n_eff"] for x in sd)]}
    n1, w1 = c["n_eff"], c["wins"]
    n2, w2 = sum(s["n_eff"] for s in slices), sum(s["wins"] for s in slices)
    p1, p2 = w1 / n1, w2 / n2
    se_bin = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    wr_slices = [s["wr"] for s in slices]
    se_clu_n = st.stdev(wr_slices) / math.sqrt(len(wr_slices)) if len(wr_slices) > 1 else None
    se_clu = math.sqrt(p1 * (1 - p1) / n1 + se_clu_n ** 2) if se_clu_n is not None else None
    se = max(se_bin, se_clu or 0.0)
    delta = p2 - p1
    z = delta / se
    if abs(delta) < 2 * se:
        verdict = ("NO DETECTABLE DIFFERENCE at this power: FP@N at 25k/12k is a candidate replacement "
                   "for FP@20 -- the maintainer rules (a gap under ~2 se is NOT excluded)")
    elif delta > 0:
        verdict = "FP@N is WEAKER than FP@20 (we beat it more): raise N and re-run"
    else:
        verdict = "FP@N is STRONGER than FP@20: lower N and re-run"
    # speed: FP@N at k=8 vs FP@20 at k=1, per turn
    s_turn_20 = c["wall_clock_sec"] / (c["n_finished"] * c["mean_turns"])
    s_turn_n = st.mean(s["wall_clock_sec"] / (s["n_finished"] * s["mean_turns"]) for s in slices)
    clean = [s for s in slices if s["relaunches"] == 0]      # a relaunch adds its dead time
    s_turn_n_clean = st.mean(s["wall_clock_sec"] / (s["n_finished"] * s["mean_turns"]) for s in clean)
    # contamination lines by phase (parallel.log carries both scheduler runs)
    contam = [l.strip() for l in open(OUT / "parallel.log") if "CONTAMINATION" in l]
    out = {
        "control_CAL20": {k: v for k, v in c.items() if k != "visits"},
        "fpn_slices": [{k: v for k, v in s.items() if k != "visits"} for s in slices],
        "pooled": {"wr_fp20": p1, "n_fp20": n1, "wr_fpn": p2, "n_fpn": n2, "delta": delta,
                   "se_binomial": se_bin, "se_slice_clustered": se_clu, "se_used": se, "z": z,
                   "ci95": [delta - 1.96 * se, delta + 1.96 * se], "verdict": verdict},
        "draws": draws, "per_draw": per_draw,
        "g2_all_agree": c["g2_fp_tally_agrees"] and all(s["g2_fp_tally_agrees"] for s in slices),
        "visits_fp20": visits_summary([c["visits"]]),
        "visits_fpn": visits_summary([s["visits"] for s in slices]),
        "speed": {"s_per_turn_fp20_k1": s_turn_20, "s_per_turn_fpn_k8": s_turn_n,
                  "fpn_k8_turn_rate_vs_fp20_k1": s_turn_20 / s_turn_n,
                  "clean_slices": len(clean), "s_per_turn_fpn_k8_clean": s_turn_n_clean,
                  "fpn_k8_turn_rate_vs_fp20_k1_clean": s_turn_20 / s_turn_n_clean,
                  "note": ("seat wall_clock includes the runner's 30 s seat-to-FP stagger and FP "
                           "startup, once per arm: ~4% of a 375-battle slice, ~0.5% of a 3000-battle arm"),
                  "phase1_projection": PHASE1_FPN_K8_TURN_RATE,
                  "mean_turns_fp20": c["mean_turns"],
                  "mean_turns_fpn": st.mean(s["mean_turns"] for s in slices)},
        "contamination_lines": contam,
    }
    if len(draws) == 2:
        def seat_delta(d):
            ca = next(x for x in ctrls if x["arm"] == DRAWS[d][0])
            sl = [x for x in slices if x["arm"] in DRAWS[d][1]]
            pa = ca["wins"] / ca["n_eff"]
            nb = sum(x["n_eff"] for x in sl)
            pb = sum(x["wins"] for x in sl) / nb
            seb = math.sqrt(pa * (1 - pa) / ca["n_eff"] + pb * (1 - pb) / nb)
            sc = st.stdev([x["wr"] for x in sl]) / math.sqrt(len(sl))
            sec = math.sqrt(pa * (1 - pa) / ca["n_eff"] + sc ** 2)
            return {"seat": SEAT_OF[d], "wr_fp20": pa, "wr_fpn": pb, "delta": pb - pa,
                    "se": max(seb, sec), "se_binomial": seb, "se_slice_clustered": sec}
        a, b = seat_delta(draws[0]), seat_delta(draws[1])
        off = (a["delta"] + b["delta"]) / 2
        se_off = math.sqrt(a["se"] ** 2 + b["se"] ** 2) / 2
        did = b["delta"] - a["delta"]
        se_did = math.sqrt(a["se"] ** 2 + b["se"] ** 2)
        gap20, gapN = b["wr_fp20"] - a["wr_fp20"], b["wr_fpn"] - a["wr_fpn"]
        passed = abs(off) < 2 * se_off and abs(did) < 2 * se_did
        out["two_seat"] = {
            "seats": [a, b],
            "offset": off, "offset_se": se_off, "offset_ci95": [off - 1.96 * se_off, off + 1.96 * se_off],
            "did": did, "did_se": se_did, "did_ci95": [did - 1.96 * se_did, did + 1.96 * se_did],
            "gap_fp20": gap20, "gap_fpn": gapN,
            "did_mde80": 2.8 * se_did,
            "verdict": ("PASS both (non-rejection): no detectable offset and no detectable scale change "
                        "-- FP@N at 25k/12k is a candidate replacement; the MAINTAINER rules on the bounds"
                        if passed else "FAIL: see which of offset / DiD crossed 2 se"),
        }
    Path(args.json_out).write_text(json.dumps(out, indent=2, default=str) + "\n")
    if "two_seat" in out:
        T = out["two_seat"]
        for x in T["seats"]:
            print(f"  {x['seat']}: FP@20 {x['wr_fp20']:.4f}  FP@N {x['wr_fpn']:.4f}  delta {x['delta']:+.4f} (se {x['se']:.4f})")
        print(f"OFFSET {T['offset']:+.4f} se {T['offset_se']:.4f} CI95 [{T['offset_ci95'][0]:+.4f}, {T['offset_ci95'][1]:+.4f}]")
        print(f"GAP E6-GW: FP@20 {T['gap_fp20']:+.4f}  FP@N {T['gap_fpn']:+.4f}; DiD {T['did']:+.4f} se {T['did_se']:.4f} "
              f"CI95 [{T['did_ci95'][0]:+.4f}, {T['did_ci95'][1]:+.4f}]; MDE(80%) {T['did_mde80']:.3f}")
        print("TWO-SEAT VERDICT:", T["verdict"])
    P = out["pooled"]
    print(f"CAL20 (FP@20, k=1): {w1}/{n1} = {p1:.4f}  (crash forfeits {c['crash_forfeits']}, ties {c['ties']})")
    print(f"CALN  (FP@N, 8x375 at k=8): {w2}/{n2} = {p2:.4f}  (crash forfeits "
          f"{sum(s['crash_forfeits'] for s in slices)}, slices {len(slices)}, slice WRs "
          f"{[round(x, 3) for x in wr_slices]})")
    print(f"delta {delta:+.4f}; se binomial {se_bin:.4f}, slice-clustered {se_clu}; se used {se:.4f}; "
          f"z {z:+.2f}; 95% CI [{P['ci95'][0]:+.4f}, {P['ci95'][1]:+.4f}]")
    print("VERDICT:", verdict)
    print("per draw:", json.dumps(per_draw))
    print("G2 (FP's own tally == seat's less crash forfeits) on every arm:", out["g2_all_agree"],
          "| raw agreement on", sum(1 for a in [c] + slices if a["g2_raw_agrees"]), "of", 1 + len(slices))
    print("visits FP@20:", json.dumps(out["visits_fp20"]))
    print("visits FP@N :", json.dumps(out["visits_fpn"]))
    print("speed:", json.dumps(out["speed"]))
    print("contamination lines:", len(contam), contam[:5])
    print(f"wrote {args.json_out}")


if __name__ == "__main__":
    main()

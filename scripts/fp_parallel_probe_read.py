"""Read the FP-parallel throughput probe (scripts/fp_parallel_probe.py) FROM DISK -- every number
in readouts/FP_PARALLEL_ROI_READOUT.md comes out of this script, none is typed.

    /opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py            # k1 k2 k4 k6 (+k8)
    /opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py --labels smoke smoke2

Per k: THE STEADY WINDOW [t0, t1] -- t0 = the poll at which every arm is past its first battle
(startup excluded), t1 = the poll at which the first arm logged its last battle (no arm running
alone) -- and in it: aggregate battles/hour and turns/hour, per-arm s/battle, CPU by process
class (CPU-second deltas from the ps sweeps / window length = cores), per-core utilisation
(E = cpu0-3, P = cpu4-13), memory. Foul Play's per-search MCTS iterations per budget branch
(n sampled battles x ms each), and iterations per ms (the load-independent strength rate).

THE ROI. The 14-arm FP phase at k slots (a new arm starts when one ends; equal arms, so waves)
= sum over waves of 3000 x s/battle(k_wave), with s/battle(k) = s/battle(1) / per-arm-rate
ratio(k). Two anchors for s/battle(1), both printed: this probe's k=1 window, and the banked
3000-battle R5 arms (results/monster_reads_offfp/*.json; the idle-box phase B arms are the
comparable ones -- configs/eval/monster_reads_offfp.yaml's PHASE B list).
"""

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "results" / "fp_parallel_probe"
MAIN = Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
R5_DIR = MAIN / "results" / "monster_reads_offfp"
R5_PHASE_B = ("gw104f", "gw112f", "gw120f", "e3wf", "e6mf", "e9f", "e3hf")  # idle box, n=3000
N_ARMS, N_BATTLES = 14, 3000
E_CORES = (0, 1, 2, 3)
TRACKED = ("seat", "seat_child", "fp_main", "fp_worker", "fp_tracker", "fp_child_other",
           "node_main", "node_sockets", "node_sim", "node_validator", "node_other")


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def read_k(label):
    d = ROOT / label
    s = json.loads((d / "summary.json").read_text())
    tl = [json.loads(x) for x in open(REPO / s["timeline"])]
    visits = [json.loads(x) for x in open(REPO / s["visits"])]
    arms = s["arms"]
    # the window from the ROWS: an arm's first row with >= 1 finished battle, and its first row
    # showing its final count; t0 = the latest first, t1 = the earliest final
    final = {a["arm"]: tl[-1]["winners"][a["arm"]] for a in arms}
    firsts = [next(r["t"] for r in tl if r["winners"][a["arm"]] >= 1) for a in arms]
    lasts = [next(r["t"] for r in tl if r["winners"][a["arm"]] >= final[a["arm"]]) for a in arms]
    t0, t1 = max(firsts), min(lasts)
    r0 = next(r for r in tl if r["t"] == t0)
    r1 = next(r for r in tl if r["t"] == t1)
    dur = t1 - t0
    out = {"label": label, "k": s["k"], "status": s["status"], "t0": t0, "t1": t1,
           "window_s": dur, "arms": []}

    # ---- battles and turns in the window
    tot_b = tot_turns = 0
    for a in arms:
        w0, w1 = r0["winners"][a["arm"]], r1["winners"][a["arm"]]
        seat = json.loads((REPO / a["seat_json"]).read_text()) if a.get("seat_json") else None
        turns = None
        if seat:
            pb = sorted(seat["per_battle"], key=lambda r: r["index"])
            turns = sum(r["turns"] for r in pb[w0:w1])
            tot_turns += turns
        tot_b += w1 - w0
        out["arms"].append({
            "arm": a["arm"], "state": a["state"], "battles_in_window": w1 - w0,
            "turns_in_window": turns,
            "s_per_battle_window": dur / (w1 - w0) if w1 > w0 else None,
            "seat_battles_finished": seat["battles_finished"] if seat else None,
            "seat_gate_all_resolved": seat["gate_all_challenges_resolved"] if seat else None,
            "seat_sec_per_battle_whole_run": seat["sec_per_battle"] if seat else None,
            "seat_mean_turns": seat["mean_turns"] if seat else None,
            "max_concurrent_live_battles": seat["max_concurrent_live_battles"] if seat else None,
            "concurrent_decisions": seat["concurrent_decisions"] if seat else None,
            "errors": len(a["errors"]),
        })
    out["battles_in_window"] = tot_b
    out["turns_in_window"] = tot_turns
    out["agg_battles_per_hour"] = tot_b / dur * 3600
    out["agg_turns_per_hour"] = tot_turns / dur * 3600
    out["per_arm_s_per_battle"] = dur * s["k"] / tot_b
    out["per_arm_s_per_turn"] = dur * s["k"] / tot_turns if tot_turns else None

    # ---- CPU by class: per-pid deltas, each pid's value taken as its max up to the poll
    # (a process that exited at t1 reads as a zombie with time 0)
    def cpu_upto(t, key):
        best = {}
        for r in tl:
            if r["t"] > t + 1e-6:
                break
            for pid, v in r[key].items():
                c = v[2] if key == "pids" else v
                best[pid] = max(best.get(pid, 0.0), c)
        return best

    cls_of, ppid_of = {}, {}
    for r in tl:
        for pid, v in r["pids"].items():
            cls_of[pid], ppid_of[pid] = v[0], v[1]
    c0, c1 = cpu_upto(t0, "pids"), cpu_upto(t1, "pids")
    cores = defaultdict(float)
    for pid, v in c1.items():
        cores[cls_of[pid]] += (v - c0.get(pid, 0.0)) / dur
    o0, o1 = cpu_upto(t0, "other_cpu_by_pid"), cpu_upto(t1, "other_cpu_by_pid")
    cores["other"] = sum(max(v - o0.get(pid, 0.0), 0.0) for pid, v in o1.items()) / dur
    out["cores_by_class"] = {k: round(v, 3) for k, v in sorted(cores.items())}
    out["cores_tracked_total"] = round(sum(cores[c] for c in TRACKED), 3)
    out["cores_per_arm"] = round(out["cores_tracked_total"] / s["k"], 3)
    per_arm = []
    for a in arms:
        sp, fp = str(a["seat_pid"]), str(a["fp_pid"])
        seat_c = (c1.get(sp, 0) - c0.get(sp, 0)) / dur
        fpm = (c1.get(fp, 0) - c0.get(fp, 0)) / dur
        wk = sum((c1[p] - c0.get(p, 0)) / dur for p in c1
                 if ppid_of.get(p) == a["fp_pid"] and cls_of[p] == "fp_worker")
        per_arm.append({"arm": a["arm"], "seat": round(seat_c, 3), "fp_main": round(fpm, 3),
                        "fp_worker": round(wk, 3)})
    out["cores_by_arm"] = per_arm

    # ---- per-core utilisation (each row = the POLL interval ending at its t)
    rows = [r for r in tl if t0 < r["t"] <= t1]
    e = [sum(r["percpu"][i] for i in E_CORES) / 100 for r in rows]
    p = [sum(v for i, v in enumerate(r["percpu"]) if i not in E_CORES) / 100 for r in rows]
    n_p = len(rows[0]["percpu"]) - len(E_CORES) if rows else 10
    out["util"] = {
        "e_busy_cores_mean": round(st.mean(e), 3) if e else None,
        "p_busy_cores_mean": round(st.mean(p), 3) if p else None,
        "p_busy_cores_p95": round(pct(p, 0.95), 3) if p else None,
        "p_saturated_poll_frac": round(sum(x >= 0.9 * n_p for x in p) / len(p), 3) if p else None,
        "idle_baseline_busy_cores": round(sum(s["idle_baseline"]["percpu"]) / 100, 3),
        "idle_baseline_e_busy": round(sum(s["idle_baseline"]["percpu"][i] for i in E_CORES) / 100, 3),
    }

    # ---- memory
    rss_peak = defaultdict(int)
    for r in tl:
        for c, v in r["rss_kb_by_class"].items():
            rss_peak[c] = max(rss_peak[c], v)
    out["mem"] = {
        "min_available_gb": round(min(r["mem_available"] for r in tl) / 1e9, 2),
        "swap_used_gb_first_last_max": [round(tl[0]["swap_used"] / 1e9, 2),
                                        round(tl[-1]["swap_used"] / 1e9, 2),
                                        round(max(r["swap_used"] for r in tl) / 1e9, 2)],
        "rss_peak_mb_by_class": {c: round(v / 1024) for c, v in sorted(rss_peak.items())
                                 if c != "other"},
    }

    # ---- Foul Play's searches, per budget branch; window-only rows for the load comparison
    out["visits"] = visits_stats(visits)
    out["visits_window"] = visits_stats([v for v in visits if t0 <= v["t"] <= t1])
    out["provenance"] = s["provenance"]
    return out


def is_trivial(v):
    """poke-engine returns after ONE 1000-iteration chunk in well under a millisecond on some
    roots (measured in the smokes: 1000 visits in 0.4-0.97 ms against a 20 ms budget) -- an early
    exit, not a search. Kept apart so it cannot drag the iteration statistics."""
    return v["visits"] <= 1000 and v.get("search_ms", 99.0) < 2.0


def visits_stats(visits):
    by = defaultdict(list)
    for v in visits:
        by[f"n{int(v['n'])}_x_{int(v['ms'])}ms"].append(v)
    res = {}
    for key, vs in sorted(by.items()):
        V = [v["visits"] for v in vs]
        trivial = [v for v in vs if is_trivial(v)]
        real = [v for v in vs if not is_trivial(v)]
        ms = [v["search_ms"] for v in real if "search_ms" in v]
        rate = [v["visits"] / v["search_ms"] for v in real if v.get("search_ms", 0) > 0]
        res[key] = {
            "searches": len(vs),
            "all_multiples_of_1000": all(x % 1000 == 0 for x in V),
            "trivial_frac": round(len(trivial) / len(vs), 4),
            "visits_nontrivial": {q: pct([v["visits"] for v in real], x)
                                  for q, x in (("p5", .05), ("p25", .25), ("p50", .5),
                                               ("p75", .75), ("p95", .95))},
            "visits_nontrivial_mean": round(st.mean(v["visits"] for v in real), 1) if real else None,
            "search_ms": {q: round(pct(ms, x), 2) for q, x in (("p5", .05), ("p50", .5),
                                                             ("p95", .95), ("max", 1.0))} if ms else None,
            "iters_per_ms": {q: round(pct(rate, x)) for q, x in (("p5", .05), ("p50", .5),
                                                                ("p95", .95))} if rate else None,
            "decision_search_wall_ms_p50": round(pct([v["search_wall_ms"] for v in vs], .5), 1),
            "decision_prep_ms_p50": round(pct([v["prep_ms"] for v in vs], .5), 1),
        }
    return res


def fpn_projection(visits):
    """Phase 2's premise, checked on the k=1 searches: with a FIXED N per branch, each search
    takes N / rate(s). N = the branch's median non-trivial visits. Returns the mean projected
    search time over the observed mean at the time budget. Trivial searches (early exit at
    1000) are kept at their observed time -- ASSUMED, since poke-engine's early exit under
    `iterations=N` is unmeasured."""
    by = defaultdict(list)
    for v in visits:
        by[(int(v["n"]), int(v["ms"]))].append(v)
    res = {}
    for (n, ms), vs in sorted(by.items()):
        real = [v for v in vs if not is_trivial(v) and v.get("search_ms", 0) > 0]
        triv = [v for v in vs if is_trivial(v) and "search_ms" in v]
        if not real:
            continue
        N = pct([v["visits"] for v in real], 0.5)
        inv_rate = [v["search_ms"] / v["visits"] for v in real]          # ms per iteration
        proj = [N * x for x in inv_rate] + [v["search_ms"] for v in triv]
        obs = [v["search_ms"] for v in real] + [v["search_ms"] for v in triv]
        # the N at which the MEAN search time matches the budget's: sum(t) / sum(t/V), a
        # time-weighted harmonic mean of the visits
        n_eq = sum(v["search_ms"] for v in real) / sum(inv_rate)
        res[f"n{n}_x_{ms}ms"] = {"N_median": N, "mean_search_ms_observed": round(st.mean(obs), 2),
                                 "mean_search_ms_at_N_median": round(st.mean(proj), 2),
                                 "time_ratio_at_N_median": round(st.mean(proj) / st.mean(obs), 3),
                                 "N_equal_mean_time": round(n_eq)}
    return res


def r5_anchor():
    arms = {}
    for p in sorted(R5_DIR.glob("*.json")):
        if p.name.endswith(".runner.json") or not p.stem.isalnum():
            continue
        d = json.loads(p.read_text())
        if d.get("battles_requested") != N_BATTLES:
            continue
        arms[p.stem] = {"sec_per_battle": d["sec_per_battle"], "wall_clock_sec": d["wall_clock_sec"],
                        "mean_turns": d.get("mean_turns"), "phase_b": p.stem in R5_PHASE_B}
    b = [a for a in arms.values() if a["phase_b"]]
    return {"arms": arms, "n_arms_3000": len(arms),
            "all_arms_wall_h": round(sum(a["wall_clock_sec"] for a in arms.values()) / 3600, 2),
            "phase_b_mean_s_per_battle": round(st.mean(a["sec_per_battle"] for a in b), 3),
            "phase_b_mean_turns": round(st.mean(a["mean_turns"] for a in b), 2)}


def phase_hours(s_per_battle_by_k, k):
    """14 equal arms on k slots: full waves at k, the remainder wave at its own width."""
    waves = [k] * (N_ARMS // k) + ([N_ARMS % k] if N_ARMS % k else [])
    if any(w not in s_per_battle_by_k for w in waves):
        return None, waves
    return sum(N_BATTLES * s_per_battle_by_k[w] for w in waves) / 3600, waves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", nargs="*", default=None)
    ap.add_argument("--json-out", default=str(ROOT / "roi.json"))
    args = ap.parse_args()
    labels = args.labels or [l for l in ("k1", "k2", "k4", "k6", "k8")
                             if (ROOT / l / "summary.json").exists()]
    ks = [read_k(l) for l in labels]
    base = next((x for x in ks if x["k"] == 1), None)
    r5 = r5_anchor() if R5_DIR.exists() else None
    for x in ks:
        if base:
            x["speedup_vs_k1"] = round(x["agg_battles_per_hour"] / base["agg_battles_per_hour"], 3)
            x["per_arm_rate_vs_k1"] = round(base["per_arm_s_per_battle"] / x["per_arm_s_per_battle"], 3)
            x["per_arm_turn_rate_vs_k1"] = (round(base["per_arm_s_per_turn"] / x["per_arm_s_per_turn"], 3)
                                            if x["per_arm_s_per_turn"] else None)
            ip = {k: v["iters_per_ms"]["p50"] for k, v in x["visits_window"].items() if v["iters_per_ms"]}
            ib = {k: v["iters_per_ms"]["p50"] for k, v in base["visits_window"].items() if v["iters_per_ms"]}
            x["fp_iters_per_ms_p50_vs_k1"] = {k: round(ip[k] / ib[k], 3) for k in ip if k in ib}
    roi = {}
    if base:
        # per-arm s/battle at each measured k, scaled from each k=1 anchor by the probe's ratio
        for anchor, s1 in (("probe_k1", base["per_arm_s_per_battle"]),
                           ("r5_phase_b", r5["phase_b_mean_s_per_battle"] if r5 else None)):
            if s1 is None:
                continue
            spb = {x["k"]: s1 / x["per_arm_rate_vs_k1"] for x in ks}
            roi[anchor] = {"s_per_battle_k1": round(s1, 3)}
            for x in ks:
                h, waves = phase_hours(spb, x["k"])
                roi[anchor][f"k{x['k']}"] = {"hours": round(h, 2) if h else None, "waves": waves}
    out = {"ks": ks, "r5_anchor": r5, "roi_14x3000": roi,
           "fpn_projection_k1": fpn_projection(
               [json.loads(v) for v in open(REPO / json.loads(
                   (ROOT / base["label"] / "summary.json").read_text())["visits"])]) if base else None}
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n")

    # ---- the readout tables, printed (pasted into the readout verbatim)
    print("| k | status | window | battles | agg battles/h | speedup | per-arm rate | per-arm turn rate "
          "| FP iters/ms (20ms branch) vs k1 | cores tracked | cores/arm | P busy (mean/p95) | E busy | min avail GB |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in ks:
        print(f"| {x['k']} | {x['status']} | {x['window_s']:.0f} s | {x['battles_in_window']} | "
              f"{x['agg_battles_per_hour']:.0f} | {x.get('speedup_vs_k1', '-')} | "
              f"{x.get('per_arm_rate_vs_k1', '-')} | {x.get('per_arm_turn_rate_vs_k1', '-')} | "
              f"{x.get('fp_iters_per_ms_p50_vs_k1', {}).get('n2_x_20ms', '-')} | "
              f"{x['cores_tracked_total']} | {x['cores_per_arm']} | "
              f"{x['util']['p_busy_cores_mean']}/{x['util']['p_busy_cores_p95']} | "
              f"{x['util']['e_busy_cores_mean']} | {x['mem']['min_available_gb']} |")
    print()
    for x in ks:
        print(f"k{x['k']} cores by class: {x['cores_by_class']}")
    print()
    for anchor, r in roi.items():
        print(f"ROI ({anchor}, s/battle at k=1 {r['s_per_battle_k1']}): " + ", ".join(
            f"k={k[1:]} {v['hours']} h (waves {v['waves']})" for k, v in r.items() if k.startswith("k")))
    if r5:
        print(f"R5 banked: {r5['n_arms_3000']} arms x 3000, total wall {r5['all_arms_wall_h']} h; "
              f"phase B mean {r5['phase_b_mean_s_per_battle']} s/battle, {r5['phase_b_mean_turns']} turns")
    print()
    for x in ks:
        print(f"k{x['k']} visits (whole run): " + json.dumps(x["visits"]))
    print()
    print("FP@N projection (k=1): " + json.dumps(out["fpn_projection_k1"]))
    print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()

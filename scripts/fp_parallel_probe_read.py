"""Read the FP-parallel throughput probe (scripts/fp_parallel_probe.py) FROM DISK -- every number
in readouts/FP_PARALLEL_ROI_READOUT.md comes out of this script, none is typed.

    /opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py            # every k on disk
    /opt/anaconda3/bin/python scripts/fp_parallel_probe_read.py --labels smoke2

Per k: THE STEADY WINDOW [t0, t1] -- t0 = the poll at which every arm is past its first battle
(startup excluded), t1 = the poll at which the first arm logged its final battle (no arm running
alone) -- and in it: aggregate battles/hour and TURNS/hour, per-arm s/battle and s/turn, CPU by
process class (CPU-second deltas between the two ps sweeps / their spacing = cores), per-core
utilisation (E = cpu0-3, P = cpu4-13), memory, and a CONTAMINATED flag (any foreign process at
>= 0.5 core inside the window: the gate only samples the 20 s BEFORE a k). Foul Play's
per-search MCTS iterations per budget branch (n sampled battles x ms each) and iterations/ms.

THE ROI SCALES BY THE PER-TURN RATE, not the per-battle one: 150-battle blocks carry ~3% (1 sd)
battle-length noise (review 2026-09-24, from R5's per-battle data), and a k's effect is on the
speed of play, not on how long battles are. s/battle(k) = anchor s/battle(1) / turn-rate(k)
ratio. Anchors, both printed: the banked 3000-battle R5 phase-B arms (idle box; configs/eval/
monster_reads_offfp.yaml's PHASE B list) and this probe's own k=1 s/turn x R5 phase-B turns.
The 14-arm FP phase at k slots (equal arms, so waves) = sum over waves of 3000 x s/battle(width).
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
MIN_WINDOW_S = 60.0
CONTAM_CORES = 0.5          # the gate's own threshold, 50% of a core


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def is_trivial(v):
    """poke-engine 0.0.48's binding sets `iterations = 100` when OUR side has <= 1 option
    (poke-engine-py/src/lib.rs, `mcts`), and the loop runs whole 1000-iteration chunks
    (src/mcts.rs, run_mcts_loop): a forced move returns at exactly 1000 visits in well under a
    millisecond. Not a search -- kept apart so it cannot drag the iteration statistics."""
    return v["visits"] <= 1000 and v.get("search_ms", 99.0) < 2.0


def no_window(s, reason):
    return {"label": s["label"], "k": s.get("k"), "status": "NO_WINDOW",
            "probe_status": s.get("status"), "reason": reason}


def read_k(label):
    d = ROOT / label
    s = json.loads((d / "summary.json").read_text())
    if s.get("status") not in ("OK", "DISTURBED") or "timeline" not in s:
        return no_window(s, f"probe status {s.get('status')}")
    tl = [json.loads(x) for x in open(REPO / s["timeline"])]
    visits = [json.loads(x) for x in open(REPO / s["visits"])]
    arms = s["arms"]
    if len(tl) < 3:
        return no_window(s, "fewer than 3 timeline rows")
    final = {a["arm"]: tl[-1]["winners"][a["arm"]] for a in arms}
    if min(final.values()) < 2:
        return no_window(s, f"an arm finished < 2 battles: {final}")
    firsts = [next(r["t"] for r in tl if r["winners"][a["arm"]] >= 1) for a in arms]
    lasts = [next(r["t"] for r in tl if r["winners"][a["arm"]] >= final[a["arm"]]) for a in arms]
    t0, t1 = max(firsts), min(lasts)
    dur = t1 - t0
    if dur < MIN_WINDOW_S:
        return no_window(s, f"steady window {dur:.0f} s < {MIN_WINDOW_S:.0f} s")
    r0 = next(r for r in tl if r["t"] == t0)
    r1 = next(r for r in tl if r["t"] == t1)
    out = {"label": label, "k": s["k"], "status": s["status"], "t0": t0, "t1": t1,
           "window_s": dur, "arms": []}

    # ---- battles and turns in the window; turns from FP's own log (every arm has one)
    tot_b = tot_turns = 0
    for a in arms:
        w0, w1 = r0["winners"][a["arm"]], r1["winners"][a["arm"]]
        tpb = a.get("turns_per_battle")
        seat = None
        if a.get("seat_json"):
            seat = json.loads((REPO / a["seat_json"]).read_text())
        if tpb is None and seat is not None:            # older summaries: the seat's record
            tpb = [r["turns"] for r in sorted(seat["per_battle"], key=lambda r: r["index"])]
        turns = sum(tpb[w0:w1]) if tpb is not None else None
        if turns is None:
            return no_window(s, f"{a['arm']}: no turn record")
        if w1 - w0 < 2:
            return no_window(s, f"{a['arm']}: {w1 - w0} battles inside the window")
        tot_b += w1 - w0
        tot_turns += turns
        seat_turns_agree = None
        if seat is not None and a.get("turns_per_battle") is not None:
            st_t = [r["turns"] for r in sorted(seat["per_battle"], key=lambda r: r["index"])]
            seat_turns_agree = st_t == a["turns_per_battle"][:len(st_t)]
        out["arms"].append({
            "arm": a["arm"], "state": a["state"], "battles_in_window": w1 - w0,
            "turns_in_window": turns, "s_per_battle_window": dur / (w1 - w0),
            "s_per_turn_window": dur / turns if turns else None,
            "seat_launches": a.get("seat_launches"),
            "seat_battles_finished": seat["battles_finished"] if seat else None,
            "seat_gate_all_resolved": seat["gate_all_challenges_resolved"] if seat else None,
            "seat_vs_fp_turns_agree": seat_turns_agree,
            "seat_sec_per_battle_whole_run": seat["sec_per_battle"] if seat else None,
            "max_concurrent_live_battles": seat["max_concurrent_live_battles"] if seat else None,
            "concurrent_decisions": seat["concurrent_decisions"] if seat else None,
            "errors": len(a["errors"]),
        })
    k = s["k"]
    out["battles_in_window"] = tot_b
    out["turns_in_window"] = tot_turns
    out["agg_battles_per_hour"] = tot_b / dur * 3600
    out["agg_turns_per_hour"] = tot_turns / dur * 3600
    out["per_arm_s_per_battle"] = dur * k / tot_b
    out["per_arm_s_per_turn"] = dur * k / tot_turns
    out["turns_per_battle_window"] = tot_turns / tot_b

    # ---- CPU by class: per-pid deltas between the two ps sweeps; each pid's value is its max up
    # to that row (a process that exited reads as a zombie with time 0)
    def cpu_upto(t, key):
        best = {}
        for r in tl:
            if r["t"] > t + 1e-6:
                break
            for pid, v in r[key].items():
                c = v[2] if key == "pids" else v
                best[pid] = max(best.get(pid, 0.0), c)
        return best

    dur_cpu = (r1.get("t_ps", t1) - r0.get("t_ps", t0))
    cls_of, ppid_of = {}, {}
    for r in tl:
        for pid, v in r["pids"].items():
            cls_of[pid], ppid_of[pid] = v[0], v[1]
    c0, c1 = cpu_upto(t0, "pids"), cpu_upto(t1, "pids")
    cores = defaultdict(float)
    for pid, v in c1.items():
        cores[cls_of[pid]] += (v - c0.get(pid, 0.0)) / dur_cpu
    o0, o1 = cpu_upto(t0, "other_cpu_by_pid"), cpu_upto(t1, "other_cpu_by_pid")
    other_by_pid = {pid: max(v - o0.get(pid, 0.0), 0.0) / dur_cpu for pid, v in o1.items()}
    cores["other"] = sum(other_by_pid.values())
    out["cores_by_class"] = {c: round(v, 3) for c, v in sorted(cores.items())}
    out["cores_tracked_total"] = round(sum(cores[c] for c in TRACKED), 3)
    out["cores_per_arm"] = round(out["cores_tracked_total"] / k, 3)
    out["cores_node_total"] = round(sum(v for c, v in cores.items() if c.startswith("node")), 3)
    cmds = {}
    for r in tl:
        cmds.update(r.get("other_cmd", {}))
    top_other = sorted(other_by_pid.items(), key=lambda kv: -kv[1])[:5]
    out["other_top"] = [[round(v, 3), pid, cmds.get(pid, "?")] for pid, v in top_other]
    out["contaminated"] = any(v >= CONTAM_CORES for v in other_by_pid.values())
    per_arm = []
    for a in arms:
        sp, fp = str(a["seat_pid"]), str(a["fp_pid"])
        per_arm.append({
            "arm": a["arm"],
            "seat": round((c1.get(sp, 0) - c0.get(sp, 0)) / dur_cpu, 3),
            "fp_main": round((c1.get(fp, 0) - c0.get(fp, 0)) / dur_cpu, 3),
            "fp_worker": round(sum((c1[p] - c0.get(p, 0)) / dur_cpu for p in c1
                                   if ppid_of.get(p) == a["fp_pid"] and cls_of[p] == "fp_worker"), 3)})
    out["cores_by_arm"] = per_arm

    # ---- per-core utilisation (each row = the interval since the previous sample)
    rows = [r for r in tl if t0 < r["t"] <= t1]
    e = [sum(r["percpu"][i] for i in E_CORES) / 100 for r in rows]
    p = [sum(v for i, v in enumerate(r["percpu"]) if i not in E_CORES) / 100 for r in rows]
    n_p = len(rows[0]["percpu"]) - len(E_CORES)
    out["util"] = {
        "e_busy_cores_mean": round(st.mean(e), 3),
        "p_busy_cores_mean": round(st.mean(p), 3),
        "p_busy_cores_p95": round(pct(p, 0.95), 3),
        "p_saturated_poll_frac": round(sum(x >= 0.9 * n_p for x in p) / len(p), 3),
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
            "visits_nontrivial": ({q: pct([v["visits"] for v in real], x)
                                   for q, x in (("p5", .05), ("p25", .25), ("p50", .5),
                                                ("p75", .75), ("p95", .95), ("max", 1.0))}
                                  if real else None),
            "visits_nontrivial_mean": round(st.mean(v["visits"] for v in real), 1) if real else None,
            "search_ms": ({q: round(pct(ms, x), 2) for q, x in (("p5", .05), ("p50", .5),
                                                               ("p95", .95), ("max", 1.0))}
                          if ms else None),
            "iters_per_ms": ({q: round(pct(rate, x)) for q, x in (("p5", .05), ("p50", .5),
                                                                 ("p95", .95))} if rate else None),
            "decision_search_wall_ms_p50": round(pct([v["search_wall_ms"] for v in vs], .5), 1),
            "decision_prep_ms_p50": round(pct([v["prep_ms"] for v in vs], .5), 1),
        }
    return res


def fpn_projection(visits):
    """Phase 2's premise, checked on the k=1 searches: with a FIXED N per branch, each search
    takes N / rate(s). N = the branch's median non-trivial visits. Returns the mean projected
    search time over the observed mean at the time budget. Forced moves are unchanged: the
    binding overrides the iteration count for them (see is_trivial)."""
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


def fpn_under_load(x, n_by_branch):
    """FP@N at load k, projected from the SAME k's own searches: each non-trivial window search
    would take N / (its visits / its search_ms) instead of search_ms -- the rate it actually got
    at that k -- while forced moves are unchanged (the binding overrides N for them). The extra
    time lands on the arm's critical path (FP's search blocks the ping-pong), so per arm:
    s/turn_N = (window + extra_arm) / turns_arm. Assumes every other component runs as observed."""
    s = json.loads((ROOT / x["label"] / "summary.json").read_text())
    vis = [json.loads(v) for v in open(REPO / s["visits"])]
    extra = defaultdict(float)
    n_real = n_forced = 0
    for v in vis:
        if not (x["t0"] <= v["t"] <= x["t1"]):
            continue
        if is_trivial(v) or v.get("search_ms", 0) <= 0:
            n_forced += 1
            continue
        n_real += 1
        key = f"n{int(v['n'])}_x_{int(v['ms'])}ms"
        extra[v["arm"]] += (n_by_branch[key] * v["search_ms"] / v["visits"] - v["search_ms"]) / 1e3
    arm_s = sum(x["window_s"] + extra[a["arm"]] for a in x["arms"])
    return {"per_arm_s_per_turn_fpn": arm_s / x["turns_in_window"],
            "extra_s_per_arm_mean": round(sum(extra.values()) / len(x["arms"]), 2),
            "window_searches_real": n_real, "window_searches_forced": n_forced}


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
            "phase_b_mean_turns": round(st.mean(a["mean_turns"] for a in b), 2),
            "phase_b_s_per_turn": round(sum(a["sec_per_battle"] for a in b)
                                        / sum(a["mean_turns"] for a in b), 4)}


def r6_anchor():
    """The SAME WEEK's production FP phase at k=1 (scripts/r6_reads_queue.sh, 14 arms x 3000,
    NI 5 throughout): its phase wall from the queue log, and the arms' own seat walls."""
    d = MAIN / "results" / "r6_reads_offfp"
    arms = {}
    for f in sorted(d.glob("*.json")):
        if f.name.endswith(".runner.json") or not f.stem.isalnum():
            continue
        j = json.loads(f.read_text())
        if j.get("battles_requested") == N_BATTLES:
            arms[f.stem] = {"sec_per_battle": j["sec_per_battle"], "wall_clock_sec": j["wall_clock_sec"],
                            "mean_turns": j.get("mean_turns")}
    from datetime import datetime
    t = {}
    for line in open(MAIN / "logs" / "r6_reads" / "queue.log"):
        for key in ("PHASE FP:", "PHASE FP DONE"):
            if f"] {key}" in line:
                t[key] = datetime.strptime(line[1:21], "%Y-%m-%dT%H:%M:%SZ").timestamp()
    return {"n_arms_3000": len(arms),
            "seat_wall_h": round(sum(a["wall_clock_sec"] for a in arms.values()) / 3600, 2),
            "phase_wall_h": (round((t["PHASE FP DONE"] - t["PHASE FP:"]) / 3600, 2)
                             if len(t) == 2 else None),
            "mean_s_per_battle": round(st.mean(a["sec_per_battle"] for a in arms.values()), 3),
            "e3wr_s_per_battle": arms.get("e3wr", {}).get("sec_per_battle"), "arms": arms}


def phase_hours(s_per_battle_by_k, k):
    """14 equal arms on k slots: full waves at k, the remainder wave at its own width."""
    waves = [k] * (N_ARMS // k) + ([N_ARMS % k] if N_ARMS % k else [])
    if any(w not in s_per_battle_by_k for w in waves):
        return None, waves
    return sum(N_BATTLES * s_per_battle_by_k[w] for w in waves) / 3600, waves


def main():
    global MIN_WINDOW_S
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", nargs="*", default=None)
    ap.add_argument("--json-out", default=str(ROOT / "roi.json"))
    ap.add_argument("--min-window-s", type=float, default=MIN_WINDOW_S,
                    help="smokes only: their windows are seconds long")
    args = ap.parse_args()
    MIN_WINDOW_S = args.min_window_s
    if args.labels:
        labels = args.labels
    else:
        labels = [l for k in (1, 2, 4, 6, 8) for l in (f"k{k}", f"k{k}r2")
                  if (ROOT / l / "summary.json").exists()]
    reads, failed = [], {}
    for l in labels:
        try:
            reads.append(read_k(l))
        except Exception as exc:                     # one bad label never kills the others
            failed[l] = repr(exc)
    # per k, the best read: OK over DISTURBED; NO_WINDOW never enters the ROI
    rank = {"OK": 0, "DISTURBED": 1}
    best = {}
    for x in reads:
        if x["status"] == "NO_WINDOW":
            continue
        if x["k"] not in best or rank[x["status"]] < rank[best[x["k"]]["status"]]:
            best[x["k"]] = x
    ks = [best[k] for k in sorted(best)]
    base = best.get(1)
    r5 = r5_anchor() if R5_DIR.exists() else None
    for x in ks:
        if base:
            x["turn_speedup_vs_k1"] = round(x["agg_turns_per_hour"] / base["agg_turns_per_hour"], 3)
            x["battle_speedup_vs_k1"] = round(x["agg_battles_per_hour"] / base["agg_battles_per_hour"], 3)
            x["per_arm_turn_rate_vs_k1"] = round(base["per_arm_s_per_turn"] / x["per_arm_s_per_turn"], 3)
            x["per_arm_battle_rate_vs_k1"] = round(base["per_arm_s_per_battle"] / x["per_arm_s_per_battle"], 3)
            ip = {b: v["iters_per_ms"]["p50"] for b, v in x["visits_window"].items() if v["iters_per_ms"]}
            ib = {b: v["iters_per_ms"]["p50"] for b, v in base["visits_window"].items() if v["iters_per_ms"]}
            x["fp_iters_per_ms_p50_vs_k1"] = {b: round(ip[b] / ib[b], 3) for b in ip if b in ib}
    roi = {}
    if base:
        anchors = [("r5_phase_b_s_per_battle", r5["phase_b_mean_s_per_battle"] if r5 else None),
                   ("probe_k1_s_per_turn_x_r5_turns",
                    base["per_arm_s_per_turn"] * r5["phase_b_mean_turns"] if r5 else None),
                   ("probe_k1_s_per_battle_UNSCALED", base["per_arm_s_per_battle"])]
        for name, s1 in anchors:
            if s1 is None:
                continue
            rate = "per_arm_battle_rate_vs_k1" if name.endswith("UNSCALED") else "per_arm_turn_rate_vs_k1"
            spb = {x["k"]: s1 / x[rate] for x in ks}
            roi[name] = {"s_per_battle_k1": round(s1, 3), "scaled_by": rate}
            for x in ks:
                h, waves = phase_hours(spb, x["k"])
                roi[name][f"k{x['k']}"] = {"hours": round(h, 2) if h else None, "waves": waves}
    fpn = None
    roi_fpn = {}
    if base:
        s1 = json.loads((ROOT / base["label"] / "summary.json").read_text())
        fpn = fpn_projection([json.loads(v) for v in open(REPO / s1["visits"])])
        n_by_branch = {b: v["N_median"] for b, v in fpn.items()}
        for x in ks:
            x["fpn"] = fpn_under_load(x, n_by_branch)
            x["fpn"]["per_arm_turn_rate_vs_fp20_k1"] = round(
                base["per_arm_s_per_turn"] / x["fpn"]["per_arm_s_per_turn_fpn"], 3)
        r6a = r6_anchor()
        roi_fpn = {"N_by_branch": n_by_branch}
        for name, s1b in (("r5_phase_b", r5["phase_b_mean_s_per_battle"] if r5 else None),
                          ("r6_same_week", r6a["mean_s_per_battle"])):
            if s1b is None:
                continue
            spb = {x["k"]: s1b / x["fpn"]["per_arm_turn_rate_vs_fp20_k1"] for x in ks}
            roi_fpn[name] = {"s_per_battle_fp20_k1_anchor": s1b}
            for x in ks:
                h, waves = phase_hours(spb, x["k"])
                roi_fpn[name][f"k{x['k']}"] = {"hours": round(h, 2) if h else None, "waves": waves}
    out = {"labels_read": labels, "failed": failed,
           "no_window": [x for x in reads if x["status"] == "NO_WINDOW"],
           "ks": ks, "r5_anchor": r5, "roi_14x3000": roi, "fpn_projection_k1": fpn,
           "roi_14x3000_fpn": roi_fpn, "r6_anchor": r6_anchor()}
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n")

    # ---- the readout tables, printed (pasted into the readout verbatim)
    print("| k | status | contam. | window | battles | turns | agg battles/h | agg turns/h | turn speedup "
          "| per-arm turn rate | FP iters/ms p50 vs k1 (2x20ms) | cores tracked | cores/arm | node cores "
          "| P busy mean/p95 | E busy | min avail GB |")
    print("|" + "---|" * 17)
    for x in ks:
        print(f"| {x['k']} | {x['status']} | {x['contaminated']} | {x['window_s']:.0f} s | "
              f"{x['battles_in_window']} | {x['turns_in_window']} | {x['agg_battles_per_hour']:.0f} | "
              f"{x['agg_turns_per_hour']:.0f} | {x.get('turn_speedup_vs_k1', '-')} | "
              f"{x.get('per_arm_turn_rate_vs_k1', '-')} | "
              f"{x.get('fp_iters_per_ms_p50_vs_k1', {}).get('n2_x_20ms', '-')} | "
              f"{x['cores_tracked_total']} | {x['cores_per_arm']} | {x['cores_node_total']} | "
              f"{x['util']['p_busy_cores_mean']}/{x['util']['p_busy_cores_p95']} | "
              f"{x['util']['e_busy_cores_mean']} | {x['mem']['min_available_gb']} |")
    print()
    for x in ks:
        print(f"k{x['k']} cores by class: {x['cores_by_class']}; other top: {x['other_top'][:3]}")
    print()
    for name, r in roi.items():
        print(f"ROI [{name}, s/battle at k=1 {r['s_per_battle_k1']}, scaled by {r['scaled_by']}]: " + ", ".join(
            f"k={kk[1:]} {v['hours']} h (waves {v['waves']})" for kk, v in r.items() if kk.startswith("k")))
    if r5:
        print(f"R5 banked: {r5['n_arms_3000']} arms x 3000, total wall {r5['all_arms_wall_h']} h; phase B "
              f"mean {r5['phase_b_mean_s_per_battle']} s/battle, {r5['phase_b_mean_turns']} turns, "
              f"{r5['phase_b_s_per_turn']} s/turn")
    print()
    for x in ks:
        print(f"k{x['k']} visits (whole run): " + json.dumps(x["visits"]))
    print()
    print("FP@N projection (k=1): " + json.dumps(fpn))
    for x in ks:
        if "fpn" in x:
            print(f"k{x['k']} FP@N under load: " + json.dumps(x["fpn"]))
    for name, r in roi_fpn.items():
        if name == "N_by_branch":
            continue
        print(f"ROI FP@N [{name}, s/battle at k=1 {r['s_per_battle_fp20_k1_anchor']}]: " + ", ".join(
            f"k={kk[1:]} {v['hours']} h" for kk, v in r.items() if kk.startswith("k")))
    r6 = {k: v for k, v in out["r6_anchor"].items() if k != "arms"}
    print("R6 same-week production FP phase (k=1): " + json.dumps(r6))
    if failed or out["no_window"]:
        print("\nFAILED:", failed, "\nNO_WINDOW:", [(x["label"], x["reason"]) for x in out["no_window"]])
    print(f"\nwrote {args.json_out}")
    return 0 if ks else 2


if __name__ == "__main__":
    raise SystemExit(main())

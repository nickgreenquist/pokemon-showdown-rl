"""FP500_ITER_CALIB's read: FP@500's realized visits -> N / N_early, then the install smoke.

    python scripts/fp500_iter_calib_read.py --ref REF500 [--write-smoke]   # step 2
    python scripts/fp500_iter_calib_read.py --smoke                        # step 3's check

Applies configs/eval/fp500_iter_calib.yaml's rule, stated there before any battle:
  - non-forced searches only;
  - group by the per-search budget (ms 500 -> N, ms 250 -> N_early);
  - each is the median, rounded to the nearest 1000, halves up;
  - VOID on contamination in > 5% of the run's minutes, on timer/forfeit losses beyond crash
    forfeits, on < 1000 searches in either branch, or on no seat JSON.
The medians are re-derived from foul-play's own log, not copied from the runner JSON. Everything
lands in results/fp500_iter_calib/calib.json with its source files named.
"""

import argparse
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

import yaml

PREREG = Path("configs/eval/fp500_iter_calib.yaml")
OUT = Path("results/fp500_iter_calib")
SMOKE_OUT = OUT / "smoke"        # its own dir: the smoke's scheduler summary must not overwrite the reference's
LINE = re.compile(r"PROBE_VISITS t=\S+ n=(\d+) ms=(\d+) .*?visits=(\d+) .*?search_ms=(-?[\d.]+) "
                  r"iters_req=(\d+)")
FULL_MS, EARLY_MS = 500, 250
NORMAL_N = {FULL_MS: 2, EARLY_MS: 4}      # battles per branch off time pressure (parallelism 1)
MIN_SEARCHES = 1000
MAX_CONTAMINATED = 0.05           # share of the run's minutes with a CONTAMINATION sample
TS = re.compile(r"\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\]")


def round_1000(x: float) -> int:
    return int((x + 500) // 1000) * 1000   # halves up


def branch_visits(fp_log: Path):
    by_ms, pressure, forced = {FULL_MS: [], EARLY_MS: []}, {FULL_MS: 0, EARLY_MS: 0}, 0
    for line in open(fp_log, errors="replace"):
        m = LINE.search(line)
        if not m:
            continue
        n, ms, v, sms, req = (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                              float(m.group(4)), int(m.group(5)))
        if req:
            sys.exit(f"{fp_log}: a search carried iters_req={req} -- this is not a wall-clock reference")
        if v <= 1000 and sms < 2.0:        # the wall-clock forced-move rule (fp_arm_counters.py)
            forced += 1
            continue
        if ms not in by_ms:
            sys.exit(f"{fp_log}: an unexpected per-search budget ms={ms} (not {FULL_MS}/{EARLY_MS})")
        by_ms[ms].append(v)
        pressure[ms] += n != NORMAL_N[ms]
    return by_ms, pressure, forced


def read_ref(arm: str) -> dict:
    tag = arm.lower()
    rj, sj, fp_log = OUT / f"{tag}.runner.json", OUT / f"{tag}.json", OUT / f"{tag}.fp.stdout"
    summary = json.loads((OUT / "parallel_summary.json").read_text())
    run = json.loads(rj.read_text())
    by_ms, pressure, forced = branch_visits(fp_log)
    why = []
    if not run.get("calibration_reference"):
        why.append("the runner JSON does not mark a calibration reference")
    # CONTAMINATION: a one-minute blip moves a median over thousands of searches by nothing, so
    # the rule voids only when contaminated minutes exceed 5% of the run; any is disclosed.
    stamps = TS.findall((OUT / f"{tag}.runner.log").read_text())
    minutes = max(1.0, (datetime.strptime(stamps[-1], "%Y-%m-%dT%H:%M:%SZ")
                        - datetime.strptime(stamps[0], "%Y-%m-%dT%H:%M:%SZ")).total_seconds() / 60)
    bad_min = len({c["t"][:16] for c in summary.get("contamination", [])})
    if bad_min / minutes > MAX_CONTAMINATED:
        why.append(f"CONTAMINATION in {bad_min} of {minutes:.0f} minutes (> {MAX_CONTAMINATED:.0%})")
    if run.get("fpn_counters_ok") is not True:
        why.append(f"counters: {run.get('fpn_counters_why')}")
    if not sj.exists():
        why.append("no seat JSON")
    stats = {}
    for ms, vs in by_ms.items():
        if len(vs) < MIN_SEARCHES:
            why.append(f"ms {ms}: {len(vs)} non-forced searches < {MIN_SEARCHES}")
        if vs:
            q = statistics.quantiles(vs, n=20) if len(vs) >= 2 else [vs[0]] * 19
            stats[ms] = {"searches": len(vs), "median": statistics.median(vs), "p05": q[0],
                         "p95": q[-1], "time_pressure_share": pressure[ms] / len(vs)}
    res = {
        "arm": arm, "valid": not why, "void_why": why,
        "N": round_1000(stats[FULL_MS]["median"]) if FULL_MS in stats else None,
        "N_early": round_1000(stats[EARLY_MS]["median"]) if EARLY_MS in stats else None,
        "branches": stats, "forced_searches": forced,
        "contaminated_minutes": bad_min, "run_minutes": round(minutes, 1),
        "rule": "configs/eval/fp500_iter_calib.yaml: median visits per per-search budget, non-forced, "
                "rounded to the nearest 1000 halves up",
        "sources": [str(fp_log), str(rj), str(sj), str(OUT / "parallel_summary.json")],
        "quote": "FP@N {N}/{N_early}, visits-matched to FP@500 at k=1 on a quiet box; strength not tested",
    }
    if bad_min:
        res.setdefault("disclose", []).append(f"CONTAMINATION in {bad_min} of {minutes:.0f} minutes")
    for ms, s in stats.items():
        if s["time_pressure_share"] > 0.01:
            res.setdefault("disclose", []).append(
                f"ms {ms}: {s['time_pressure_share']:.2%} of searches ran under FP's time pressure")
    return res


def write_smoke(res: dict, path: Path):
    pre = yaml.safe_load(PREREG.read_text())
    doc = {
        "title": "fp500_iter_calib smoke (generated)",
        "status": f"GENERATED by scripts/fp500_iter_calib_read.py from {res['arm']}'s read -- the "
                  "install smoke of configs/eval/fp500_iter_calib.yaml step 3; data, never a read",
        "credits_nothing": True,
        "results_dir": str(SMOKE_OUT),
        "fp": {"search_time_ms": 500},
        "checkpoints": pre["checkpoints"],
        "arms": {"SM500N": {"kind": "greedy_seat", "seat": "w104", "battles": 4, "search_time_ms": 500,
                            "search_iterations": res["N"], "search_iterations_early": res["N_early"],
                            "loop_breaker": True, "seat_username": "fpc500smseat",
                            "fp_username": "fpc500smbot"}},
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def check_smoke() -> dict:
    run = json.loads((SMOKE_OUT / "sm500n.runner.json").read_text())
    why = []
    if run.get("fpn_counters_ok") is not True:
        why.append(f"counters: {run.get('fpn_counters_why')}")
    if run.get("fp_iters_exact_rate") != 1.0:
        why.append(f"realized iterations == N on {run.get('fp_iters_exact_rate')} of non-forced searches")
    if run.get("fp_budget_seen") != "fixed":
        why.append(f"fp_budget_seen {run.get('fp_budget_seen')!r}, not 'fixed'")
    if not (SMOKE_OUT / "sm500n.json").exists():
        why.append("no seat JSON")
    return {"pass": not why, "why": why, "nonforced": run.get("fp_nonforced_searches"),
            "exact_rate": run.get("fp_iters_exact_rate"), "source": str(SMOKE_OUT / "sm500n.runner.json")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", default=None, help="the reference arm to read (REF500 or REF500R2)")
    ap.add_argument("--write-smoke", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="check SM500N and record it")
    args = ap.parse_args()
    calib = OUT / "calib.json"
    if args.ref:
        res = read_ref(args.ref)
        calib.write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps(res, indent=2))
        if not res["valid"]:
            sys.exit(f"{args.ref} VOID: {res['void_why']}")
        if args.write_smoke:
            write_smoke(res, OUT / "sm500n.yaml")
            print(f"wrote {OUT / 'sm500n.yaml'} (N {res['N']}, N_early {res['N_early']})")
    if args.smoke:
        res = json.loads(calib.read_text())
        res["smoke"] = check_smoke()
        calib.write_text(json.dumps(res, indent=2) + "\n")
        print(json.dumps(res["smoke"], indent=2))
        if not res["smoke"]["pass"]:
            sys.exit("SM500N FAILED")
        print("PASS: " + res["quote"].format(N=res["N"], N_early=res["N_early"]))


if __name__ == "__main__":
    main()

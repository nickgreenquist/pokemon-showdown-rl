"""Per-arm Foul Play INSTRUMENT COUNTERS, read from foul-play's own log and written into the
arm's runner JSON. The FP@N adoption conditions (r6-runner, 2026-09-25, unanimous with the
maintainer and r7-runner): the read is INVALID if either fails.

    python scripts/fp_arm_counters.py <arm>.fp.stdout <arm>.runner.json

  1. REALIZED ITERATIONS. On an FP@N arm, every non-forced search must have run exactly the
     requested N, which poke-engine rounds UP to whole 1000-iteration chunks. The source is the
     `PROBE_VISITS ... visits=V ... iters_req=N` lines foul-play logs in its parent
     (scripts/patches/foulplay_gen1_local.patch). A forced move runs one chunk by the binding's
     own override (`iterations = 100` when our side has <= 1 option) and is excluded.
     Rate must be 1.0.
  2. TIMER LOSSES. Showdown ends a stalled side with `|-message|<name> lost due to inactivity.`
     (server/room-battle.ts, forfeitPlayer) and a departed one with `... forfeited.`. The
     seats send `/timer on` by rule, so an arm run beside a training fleet could lose on the
     clock, and that reads as a LOSS, not an error. A foul-play crash's orphaned room may time
     out the same way, and the runner has already excluded that battle as a crash forfeit. So:
     timer + forfeit messages must not exceed the runner's crash forfeits (0 on a clean arm).
Writes fp_nonforced_searches, fp_iters_exact, fp_iters_exact_rate (None for a wall-clock arm),
fp_timer_losses, fp_forfeit_messages, fpn_counters_ok (and why not) into the runner JSON.
"""

import json
import re
import statistics
import sys
from pathlib import Path

VIS = re.compile(r"PROBE_VISITS .*?visits=(\d+) .*?search_ms=(-?[\d.]+) iters_req=(\d+)")
BRANCH = re.compile(r"PROBE_VISITS t=\S+ n=(\d+) ms=(\d+) ")   # budget branch: battles x ms
TIMER = re.compile(r"\|-message\|.* lost due to inactivity\.")
FORFEIT = re.compile(r"\|-message\|.* forfeited\.")


def chunked(n: int) -> int:
    return -(-n // 1000) * 1000


def main():
    fp_log, runner_json = Path(sys.argv[1]), Path(sys.argv[2])
    run = json.loads(runner_json.read_text())
    nonforced = exact = req_seen = n_forced = 0
    timer = forfeit = 0
    probe_lines = 0
    by_branch = {}
    for line in open(fp_log, errors="replace"):
        if "PROBE_VISITS" in line:
            m = VIS.search(line)
            if not m:
                continue
            probe_lines += 1
            v, ms, req = int(m.group(1)), float(m.group(2)), int(m.group(3))
            if req > 0:
                req_seen += 1
            # A FORCED MOVE runs ONE chunk by the binding's override. Under FP@N that is
            # identifiable by count alone -- a non-forced search always runs chunked(N) >= 2000,
            # so exactly 1000 visits is forced whatever it took (measured 2026-09-25: forced
            # chunks took up to 2.7 ms 8-wide, so a time cut mislabels them). Under a wall-clock
            # budget, 1000 visits can also be one slow chunk, so the time cut is kept there.
            forced = (v == 1000) if req > 0 else (v <= 1000 and ms < 2.0)
            if forced:
                n_forced += 1
                continue
            nonforced += 1
            b = BRANCH.search(line)
            if b:
                by_branch.setdefault((int(b.group(1)), int(b.group(2))), []).append(v)
            if req > 0 and v == chunked(req):
                exact += 1
        elif TIMER.search(line):
            timer += 1
        elif FORFEIT.search(line):
            forfeit += 1
    fixed = int(run.get("search_iterations") or 0) > 0
    rate = (exact / nonforced if nonforced else None) if fixed else None
    cf = int(run.get("crash_forfeits", 0))
    why = []
    if fixed and probe_lines == 0:
        why.append("no PROBE_VISITS lines: foul-play is not the logging build, so the rate is unmeasured")
    if fixed and rate is not None and rate < 1.0:
        why.append(f"realized iterations == N on {rate:.4f} of non-forced searches (must be 1.0)")
    if fixed and req_seen == 0 and probe_lines:
        why.append("an FP@N arm whose searches carried no iters_req")
    if timer + forfeit > cf:
        why.append(f"{timer} timer + {forfeit} forfeit losses > {cf} crash forfeits")
    branches = None
    if not fixed:
        # A wall-clock arm's realized visits per budget branch -- a calibration reference's
        # whole output (the FP@N recipe: the median per branch at k=1 on a quiet box).
        branches = {}
        for (n, ms), vs in sorted(by_branch.items()):
            q = statistics.quantiles(vs, n=20) if len(vs) >= 2 else [vs[0]] * 19
            branches[f"n{n}_ms{ms}"] = {"searches": len(vs), "median": statistics.median(vs),
                                        "p05": q[0], "p95": q[-1]}
    run.update({
        "calibration_reference": bool(run.get("calibration_reference_for")),
        "fp_visits_by_branch": branches,
        "fp_probe_lines": probe_lines, "fp_nonforced_searches": nonforced,
        "fp_forced_searches": n_forced,
        "fp_iters_exact": exact if fixed else None, "fp_iters_exact_rate": rate,
        "fp_timer_losses": timer, "fp_forfeit_messages": forfeit,
        "fpn_counters_ok": not why, "fpn_counters_why": why,
        "fpn_counters_rule": ("FP@N adoption, 2026-09-25: realized iterations == N on 100% of "
                              "non-forced searches; timer+forfeit losses <= crash forfeits; "
                              "either failing makes the arm's read INVALID"),
    })
    runner_json.write_text(json.dumps(run, indent=2) + "\n")
    print(f"counters: ok={not why} rate={rate} nonforced={nonforced} timer={timer} "
          f"forfeit={forfeit} crash_forfeits={cf}" + (f" WHY={why}" if why else ""))


if __name__ == "__main__":
    main()

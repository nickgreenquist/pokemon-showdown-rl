"""Run off-Foul-Play arms K AT A TIME through the incident-hardened per-arm runner
(scripts/ch3_r4_fp_runner.sh) -- the FP-parallel task's Phase 2 (2026-09-25).

    /opt/anaconda3/bin/python scripts/fp_arms_parallel.py --prereg configs/eval/X.yaml \\
        --arms A,B,C,... --slots 8 [--out results/X] [--fpdir DIR]

--fpdir defaults to the runner's ../foul-play, the patched production build since 88e890e.

FP@20 IS RETIRED FOR GEN 1 (maintainer, 2026-09-25: "No one should run outdated F@20 anymore";
unanimous with the three sessions). A gen-1 arm with search_time_ms 20 and no search_iterations
is refused here and, authoritatively, in the runner (exit 7).

WHY IT IS SAFE NOW, AND ONLY FOR FP@N. A Foul Play arm with a WALL-CLOCK budget (FP@20) is
weakened by anything else on the box -- measured: 16-19% fewer iterations per search at 4-8
concurrent arms even with every arm on a P-core (readouts/FP_PARALLEL_ROI_READOUT.md). An arm
with a FIXED iteration budget (FP@N: `search_iterations` in the arm) is the same opponent at
any load; load costs it time, never strength. So:
  * an arm WITHOUT `search_iterations` (FP@<ms>) forces --slots 1 and refuses to start while
    any other Foul Play or training lane is alive (the queue's quiet-box rule);
  * FP@N arms may share the box with each other; the scheduler still refuses to start beside
    a FOREIGN wall-clock Foul Play, which our load would weaken.
Each runner runs in its own session. The runner kills only its own arm's process group (never
a box-wide pattern) and cleans its arm up on SIGTERM, which is how this scheduler stops a wave.
Resume-safe: an arm whose seat JSON exists is skipped. Refuses to run niced or at background
QoS (the maintainer's rule; zsh's BG_NICE nices every `cmd &` launch by +5 -- launch via bash).
Per-arm encoder settings come from the pre-reg's `arm_encoder` block, as in
scripts/r6_reads_queue.sh. The runner's relaunch knobs (STALL_POLLS, MAX_RELAUNCHES,
NO_PROGRESS_RELAUNCHES) come from the caller's environment when set, because a pre-reg's own
relaunch gate must be what runs (R7 G2 ratified the runner's >= 30), else the reads queue's
60 / 10 / 3; START logs them, the summary and every runner JSON stamp them. Beside other load
the 60 s sampler logs CONTAMINATION for a wall-clock arm and only descriptive LOAD for FP@N,
whose validity input is fpn_counters_ok. Writes <out>/parallel.log and
<out>/parallel_summary.json.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "ch3_r4_fp_runner.sh"


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--arms", required=True, help="comma list, run in this order")
    ap.add_argument("--slots", type=int, required=True)
    ap.add_argument("--out", default=None, help="default: the pre-reg's results_dir")
    ap.add_argument("--fpdir", default=None, help="Foul Play checkout (runner default: ../foul-play)")
    ap.add_argument("--stagger", type=float, default=15.0, help="s between runner launches")
    ap.add_argument("--smoke-battles", type=int, default=None, help="forwarded as SMOKE_BATTLES")
    ap.add_argument("--gate-hold-min", type=float, default=15.0,
                    help="wall-clock arms: hold this long for a quiet box, then give up")
    args = ap.parse_args()

    os.chdir(REPO)
    prereg = yaml.safe_load(open(args.prereg))
    out = Path(args.out or prereg["results_dir"])
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "parallel.log", "a")

    def log(msg):
        line = f"[{utc()}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    specs = {a: prereg["arms"][a] for a in arms}
    wallclock = [a for a in arms if not specs[a].get("search_iterations")]
    if os.environ.get("FORMAT", "gen1randombattle") == "gen1randombattle":
        retired = [a for a in wallclock if int(specs[a].get("search_time_ms") or 0) == 20]
        if retired:
            log(f"REFUSING: {retired} are FP@20, RETIRED for gen 1 (maintainer, 2026-09-25); declare "
                "search_iterations: 25000 and search_iterations_early: 12000 (FP@N 25k/12k)")
            sys.exit(7)

    try:
        bg = os.getpriority(4, 0)
    except (OSError, AttributeError):
        bg = 0
    if os.nice(0) != 0 or bg:
        log(f"REFUSING: niced ({os.nice(0)}) or background QoS ({bg}) -- launch via bash, not a zsh `&`")
        sys.exit(6)

    if wallclock and args.slots != 1:
        log(f"REFUSING: {wallclock} carry a WALL-CLOCK budget (no search_iterations); such arms "
            "run one at a time (--slots 1) -- a second process on the box weakens their Foul Play")
        sys.exit(2)
    users = [u for a in arms for u in (specs[a]["seat_username"], specs[a]["fp_username"])]
    if len(users) != len(set(users)):
        log("REFUSING: a username repeats across these arms")
        sys.exit(2)

    def foreign():
        """Other Foul Plays / training lanes alive, anchored on a python EXECUTABLE."""
        ps = subprocess.run(["ps", "-Aeo", "pid=,command="], capture_output=True, text=True,
                            timeout=60).stdout.splitlines()
        mine = set(users)
        bad = []
        for line in ps:
            m = re.match(r"\s*(\d+)\s+(\S+)\s(.*)", line)
            if not m or not re.search(r"/bin/python[\d.]*$", m.group(2)):
                continue
            cmd = m.group(3)
            if " -m rl.train" in " " + cmd:
                # a training lane weakens only a WALL-CLOCK arm of ours; FP@N arms run beside a
                # fleet by design (load costs them time, never strength) -- the adoption's point
                if wallclock:
                    bad.append(f"training lane {m.group(1)}")
            elif re.search(r"(^|\s)run\.py\s", cmd):
                u = re.search(r"--ps-username (\S+)", cmd)
                if u and u.group(1) in mine:
                    continue
                fixed = "--search-iterations" in cmd
                if wallclock or not fixed:        # our FP@20, or their wall-clock FP
                    bad.append(f"foul-play {m.group(1)} ({'FP@N' if fixed else 'wall-clock'})")
        return bad

    bad = foreign()
    if bad:
        log(f"REFUSING: {bad} alive -- " + ("an FP@<ms> arm needs the box to itself" if wallclock
                                              else "our load would weaken a wall-clock Foul Play"))
        sys.exit(3)

    # A WALL-CLOCK arm also needs the reads queue's full quiet-box gate (any process >= 50% of
    # a core over 20 s; any python from a foreign conda env), held, never skipped.
    sys.path.insert(0, str(REPO / "scripts"))
    from fp_parallel_probe import offenders, ps_sweep
    if wallclock:
        t0 = time.time()
        while True:
            off = offenders(False)
            if not off:
                log(f"GATE: box clear{' after ' + str(round((time.time() - t0) / 60, 1)) + ' min' if time.time() - t0 > 30 else ''}")
                break
            log(f"HOLD: {len(off)} offender(s): " + " | ".join(off[:6]))
            if time.time() - t0 > args.gate_hold_min * 60:
                log("HELD_OUT: gave up waiting for a quiet box")
                sys.exit(5)
            time.sleep(60)
    caff = subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(os.getpid())])
    # FOREIGN-LOAD SAMPLER: every 60 s, any process outside our arms at >= 50% of a core over the
    # minute is logged as CONTAMINATION and lands in the summary -- the gate only sees the
    # moment before launch, and a wall-clock arm's read needs the whole run. For FP@N arms the
    # same load is DESCRIPTIVE (it costs them time, never strength): one aggregate LOAD line a
    # minute, kept apart in the summary so nobody reads a fleet beside FP@N as a void.
    contamination = []
    foreign_load = []
    last_rows, last_t = ps_sweep(), time.time()

    def our_pids(rows):
        ours = set()
        roots = {p.pid for p in running.values()}
        frontier = set(roots)
        while frontier:
            ours |= frontier
            frontier = {pid for pid, r in rows.items() if r[0] in frontier and pid not in ours}
        for pid, r in rows.items():      # foul-play escapes to its own session: match by name
            if any(f"--ps-username {u}" in r[3] for u in users):
                ours.add(pid)
        ours |= {pid for pid, r in rows.items() if r[0] in ours}
        return ours
    running = {}      # arm -> Popen
    done = {}         # arm -> dict
    stopping = False

    def on_term(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)

    base = os.environ.copy()
    # The caller's environment wins for the relaunch knobs: a pre-reg's own relaunch gate must be
    # what runs (R7 G2 ratified the runner's >= 30), and each runner JSON stamps max_relaunches.
    for k, v in (("STALL_POLLS", "60"), ("MAX_RELAUNCHES", "10"), ("NO_PROGRESS_RELAUNCHES", "3")):
        base.setdefault(k, v)
    knobs = {k: base[k] for k in ("STALL_POLLS", "MAX_RELAUNCHES", "NO_PROGRESS_RELAUNCHES")}
    base.update(PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                PYTHONPATH=str(REPO))           # the seats import THIS tree's rl, not main's
    if args.fpdir:
        base["FPDIR"] = str(Path(args.fpdir).resolve())
    if args.smoke_battles:
        base["SMOKE_BATTLES"] = str(args.smoke_battles)
    enc = prereg.get("arm_encoder") or {}

    def tag(a):
        # the runner prefixes smoke_ under SMOKE_BATTLES, so both of its files follow suit
        return a.lower() if not args.smoke_battles else f"smoke_{a.lower()}"

    def seat_json(a):
        return Path(prereg["results_dir"]) / f"{tag(a)}.json"

    queue = [a for a in arms if not seat_json(a).exists()]
    for a in arms:
        if a not in queue:
            log(f"{a} SKIP (seat JSON exists)")
    log(f"START pid {os.getpid()} slots={args.slots} arms={queue} fpdir={base.get('FPDIR', '(runner default)')} "
        f"budget={'FP@N' if not wallclock else 'wall-clock'} knobs={knobs}")
    last_launch = 0.0
    try:
        while (queue or running) and not stopping:
            for a, p in list(running.items()):
                rc = p.poll()
                if rc is not None:
                    js = seat_json(a)
                    rj = out / f"{tag(a)}.runner.json"
                    ctr = json.loads(rj.read_text()) if rj.exists() else {}
                    done[a] = {"rc": rc, "seat_json": str(js) if js.exists() else None,
                               "ended": utc(), "fpn_counters_ok": ctr.get("fpn_counters_ok"),
                               "fpn_counters_why": ctr.get("fpn_counters_why")}
                    log(f"{a} ENDED rc={rc} json={'yes' if js.exists() else 'NO'} "
                        f"counters={'ok' if ctr.get('fpn_counters_ok') else 'FAIL ' + str(ctr.get('fpn_counters_why'))}")
                    del running[a]
            while queue and len(running) < args.slots and time.time() - last_launch >= args.stagger:
                a = queue.pop(0)
                env = dict(base, PREREG=args.prereg, ARM=a, TAG=a.lower(), OUT=str(out))
                e = enc.get(a)
                for v in ("POKEMON_RL_ENCODER_C6", "POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH"):
                    env.pop(v, None)
                if e and e.get("c6"):
                    env["POKEMON_RL_ENCODER_C6"] = "1"
                    if e.get("allow_mismatch"):
                        env["POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH"] = "1"
                running[a] = subprocess.Popen(
                    ["bash", str(RUNNER)], env=env, start_new_session=True,
                    stdout=open(out / f"{a.lower()}.driver.log", "a"), stderr=subprocess.STDOUT)
                last_launch = time.time()
                log(f"{a} LAUNCHED runner pid {running[a].pid} "
                    f"(budget {specs[a].get('search_iterations') or str(specs[a]['search_time_ms']) + ' ms'}; "
                    f"c6 {'on' if e and e.get('c6') else 'off'})")
            time.sleep(2.0)
            if time.time() - last_t >= 60:
                rows, now = ps_sweep(), time.time()
                ours = our_pids(rows) | {os.getpid()}
                busy = []
                for pid, r in rows.items():
                    if pid in ours or pid not in last_rows or r[0] == os.getpid():
                        continue
                    use = (r[1] - last_rows[pid][1]) / (now - last_t)
                    if use >= 0.5:
                        busy.append((pid, use, r[3]))
                if wallclock:
                    for pid, use, cmd in busy:
                        contamination.append({"t": utc(), "pid": pid, "cores": round(use, 2),
                                              "cmd": cmd[:120]})
                        log(f"CONTAMINATION: pid {pid} at {use:.2f} cores: {cmd[:100]}")
                elif busy:
                    cores = round(sum(u for _, u, _ in busy), 2)
                    foreign_load.append({"t": utc(), "procs": len(busy), "cores": cores})
                    log(f"LOAD (descriptive; FP@N is load-independent): {len(busy)} foreign "
                        f"process(es) at {cores:.2f} cores")
                last_rows, last_t = rows, now
    finally:
        if running:
            log(f"STOPPING {list(running)}: SIGTERM each runner (its trap kills its own arm)")
            for p in running.values():
                try:
                    p.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    pass
            t = time.time()
            while time.time() - t < 30 and any(p.poll() is None for p in running.values()):
                time.sleep(1)
            for a, p in running.items():
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                done[a] = {"rc": p.poll(), "seat_json": None, "ended": utc(), "stopped": True}
        caff.terminate()
    (out / "parallel_summary.json").write_text(json.dumps(
        {"prereg": args.prereg, "slots": args.slots, "arms": arms, "done": done,
         "stopped_early": stopping, "finished": utc(), "contamination": contamination,
         "foreign_load": foreign_load, "runner_knobs": knobs,
         "budget": "wall-clock" if wallclock else "FP@N"}, indent=2) + "\n")
    ok = all(d.get("seat_json") for d in done.values())
    bad = [a for a, d in done.items() if d.get("seat_json") and d.get("fpn_counters_ok") is False]
    if bad:
        log(f"COUNTERS FAIL on {bad}: those arms' reads are INVALID under the FP@N adoption conditions")
    log(f"DONE: {sum(1 for d in done.values() if d.get('seat_json'))}/{len(done)} arms with a seat JSON")
    sys.exit(0 if ok and not stopping else 4)


if __name__ == "__main__":
    main()

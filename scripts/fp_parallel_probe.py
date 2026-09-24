"""FP-parallel THROUGHPUT probe: k concurrent off-Foul-Play arms on one box (maintainer's
FP-parallel ROI task, Phase 1, 2026-09-24). A MEASUREMENT HARNESS, not a read: no win rate from
it is quoted anywhere, and FP@20 here is a load generator.

    /opt/anaconda3/bin/python scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom
    /opt/anaconda3/bin/python scripts/fp_parallel_probe.py --smoke          # 1 arm x 3 battles

Runs with the BASE anaconda python (psutil, for per-core utilisation). For each k it starts k
identical arms AT ONCE -- seat = scripts/ch3_fp_h2h.py (pokemon-showdown-rl env), Foul Play =
run.py from the probe copy (foul-play env), each on its own username pair on the one :8000
server, with scripts/ch3_r4_fp_runner.sh's exact command lines -- and records, every POLL s:

  * per-arm completed battles ("Winner:" lines) and turns per battle ("|turn|" lines) from Foul
    Play's log -> THE STEADY WINDOW: from the moment every arm is past its first battle (startup
    excluded) to the moment the first arm finishes (no arm running alone), the conforming window
    of docs/landmines.md. Turns come from FP's side, so an arm whose seat was killed still counts;
  * per-process CPU-seconds and RSS from ONE `ps` sweep (the reads queue's instrument), by class:
    seat, FP main, FP search worker, FP resource tracker, Showdown main / sockets / simulators /
    validator / other, this driver, everything else. `ps` never lists pid 0 (kernel_task), so the
    per-core utilisation below is the complete measure of load and the classes are attribution;
  * per-core utilisation (psutil): cpu0-3 are the E-cores, cpu4-13 the P-cores on this M4 Pro
    (measured 2026-09-24: the background-QoS R7 G1b jobs lit exactly cpu0-3);
  * system memory and swap;
  * Foul Play's PROBE_VISITS lines (scripts/patches/foulplay_probe_visits.patch): every search's
    MCTS iteration count and duration, logged in FP's PARENT.

PRIORITY. It REFUSES to run niced or at background QoS (the maintainer's rule: never nice or
taskpolicy anything you time). zsh's BG_NICE option -- on by default -- runs every `cmd &` job at
nice +5, so launch through bash (scripts/fp_parallel_probe_after_queue.sh does). Both values and
the power source are stamped into every summary.

SAFETY. Every child starts in its OWN session (start_new_session) and is killed BY PROCESS GROUP.
Nothing here ever pkills by pattern: scripts/ch3_r4_fp_runner.sh's kill_fp sweeps EVERY
foul-play search worker on the box, which is safe only when arms are serial. No relaunch of a
battle: a crashed or stalled arm is killed, recorded, and its k is flagged DISTURBED (re-run it
on the rerun pairs, --rerun). A seat that dies BEFORE it is ready (the torch lazy-init SIGSEGV,
before it ever logs in) is relaunched up to twice. A failed k never stops the sequence: the next
k uses fresh usernames. A quiet-box gate (the reads queue's two nets: any process >= 50% of a
core over a 20 s CPU-time delta; any python from a conda env other than ours / Foul Play's; plus
any other Foul Play, seat or training lane) HOLDS before every k, for at most --hold-max-min and
never past --end-by, then gives the box up (HELD_OUT).

Resume-safe: a k whose summary.json exists is skipped. Outputs: results/fp_parallel_probe/
<label>/{summary.json, timeline.jsonl, visits.jsonl, arm logs}; seat JSONs at
results/fp_parallel_probe/<arm>.json. Stop it with SIGTERM to the DRIVER (its finally kills
every child group); killing the chain's bash alone leaves the driver running.
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

import psutil
import yaml

REPO = Path(__file__).resolve().parents[1]
MAIN = Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
PREREG = "configs/eval/fp_parallel_probe.yaml"
PY = "/opt/anaconda3/envs/pokemon-showdown-rl/bin/python"
FPPY = "/opt/anaconda3/envs/foul-play/bin/python"
FPDIR = Path("/Users/nickgreenquist/Documents/Projects/foul-play-fpprobe")
FP_PROD = Path("/Users/nickgreenquist/Documents/Projects/foul-play")
WS = "ws://localhost:8000/showdown/websocket"
FORMAT = "gen1randombattle"
SEARCH_TIME_MS = 20        # asserted against every arm's pre-reg value below
SEARCH_PARALLELISM = 1     # scripts/ch3_r4_fp_runner.sh's default, which the reads queues run
E_CORES = (0, 1, 2, 3)     # measured 2026-09-24, see the module docstring
OUR_ENVS = ("pokemon-showdown-rl", "foul-play")

POLL = 2.0                 # s between samples
SEAT_STAGGER = 10.0        # s between seat launches (the torch lazy-init landmine: stagger)
SEAT_SETTLE = 30.0         # s from the LAST seat launch to the first FP launch (the runner's 30)
SEAT_RETRIES = 2           # relaunches of a seat that dies before it is ready
FP_STAGGER = 0.5           # s between FP launches (no login thundering herd)
STALL_S = 300.0            # FP alive but its log silent this long = a stalled arm
SEAT_EXIT_S = 120.0        # FP finished normally; its seat gets this long to exit
GAP_S = 60.0               # idle gap after each k (room reaping); its last 30 s = idle baseline
HOT_WIN = 20.0
HOT_PCT = 50.0
HOLD_POLL = 60.0
SUBPROC_TIMEOUT = 60.0     # every ps / lsof / git / diff call is bounded

WINNER = "Winner:"
TURN = "|turn|"
VISITS_RE = re.compile(
    r"PROBE_VISITS t=(?P<t>[\d.]+) n=(?P<n>\d+) ms=(?P<ms>\d+) i=(?P<i>\d+) "
    r"visits=(?P<visits>\d+) prep_ms=(?P<prep_ms>[\d.]+) "
    r"search_wall_ms=(?P<search_wall_ms>[\d.]+) rebuilt=(?P<rebuilt>\d)"
    r"(?: search_ms=(?P<search_ms>-?[\d.]+))?")
ERR_MARKERS = ("nametaken", "Traceback", "Process pool broke", "ERROR")


def est_k_s(k: int, battles: int) -> float:
    """Wall time of one k, gate to idle gap, with a load slowdown allowance per arm."""
    return (HOT_WIN + k * SEAT_STAGGER + SEAT_SETTLE + 15
            + battles * 2.0 * (1 + 0.05 * k) + GAP_S + 30)


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str, fh=None) -> None:
    line = f"[{utc()}] {msg}"
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


def run(cmd, cwd=None) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=SUBPROC_TIMEOUT).stdout
    except subprocess.TimeoutExpired:
        return ""


# ------------------------------------------------------------------ ps sweep
def ps_secs(t: str) -> float:
    """ps time= is [dd-][hh:]mm:ss[.ss] (minutes unbounded on macOS)."""
    d = 0
    if "-" in t:
        d, t = t.split("-")
        d = int(d)
    p = [float(x) for x in t.split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return d * 86400 + p[0] * 3600 + p[1] * 60 + p[2]


def ps_sweep() -> dict[int, tuple[int, float, int, str]]:
    """pid -> (ppid, cpu_seconds, rss_kb, command) for EVERY process (root's too)."""
    rows = {}
    for line in run(["ps", "-Aeo", "pid=,ppid=,time=,rss=,command="]).splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(.*)", line)
        if m:
            rows[int(m.group(1))] = (int(m.group(2)), ps_secs(m.group(3)),
                                     int(m.group(4)), m.group(5))
    return rows


def server_pid() -> int | None:
    out = run(["lsof", "-nP", "-iTCP:8000", "-sTCP:LISTEN", "-t"]).split()
    return int(out[0]) if out else None


def classify(rows, seat_pids, fp_pids, srv, me) -> dict[int, str]:
    cls = {}
    for pid, (ppid, _t, _rss, cmd) in rows.items():
        if pid in seat_pids:
            c = "seat"
        elif ppid in seat_pids:
            c = "seat_child"
        elif pid in fp_pids:
            c = "fp_main"
        elif ppid in fp_pids:
            c = ("fp_worker" if "spawn_main" in cmd else
                 "fp_tracker" if "resource_tracker" in cmd else "fp_child_other")
        elif pid == srv:
            c = "node_main"
        elif ppid == srv and srv is not None:
            c = ("node_sockets" if "sockets.js" in cmd else
                 "node_sim" if "room-battle.js" in cmd else
                 "node_validator" if "team-validator" in cmd else "node_other")
        elif pid == me:
            c = "driver"
        elif ppid == me:
            c = "driver_child"   # ps itself, caffeinate
        else:
            c = "other"
        cls[pid] = c
    return cls


def priority() -> dict:
    try:
        bg = os.getpriority(4, 0)          # PRIO_DARWIN_PROCESS: non-zero = background QoS
    except (OSError, AttributeError):
        bg = None
    return {"nice": os.nice(0), "darwin_bg": bg}


# ------------------------------------------------------------------ quiet-box gate
def offenders(allow_busy: bool) -> list[str]:
    """The reads queue's two nets (scripts/r6_reads_queue.sh hold_for_others), plus any other
    Foul Play / seat / training lane (anchored on a python EXECUTABLE: a shell or grep carrying
    the pattern in its argv must not match -- docs/landmines.md, the pgrep self-match)."""
    me = os.getpid()
    rows_a = ps_sweep()
    time.sleep(HOT_WIN)
    rows_b = ps_sweep()
    bad = []
    for pid, (ppid, t1, _rss, cmd) in sorted(rows_b.items()):
        if pid == me or ppid == me:
            continue
        if (re.match(r"^\S*/bin/python[\d.]*\s", cmd)
                and re.search(r"\srun\.py\s|scripts/ch3_fp_h2h\.py|-m rl\.train\s|"
                              r"foulplay_vs_sh\.py", cmd)):
            if not allow_busy or "rl.train" not in cmd:
                bad.append(f"live {pid}: {cmd[:140]}")
            continue
        if allow_busy:
            continue
        if pid in rows_a:
            use = (t1 - rows_a[pid][1]) / HOT_WIN * 100
            if use >= HOT_PCT:
                bad.append(f"hot {pid} {use:.0f}% of a core: {cmd[:140]}")
        exe = cmd.split()[0] if cmd.split() else ""
        m = re.match(r"^/opt/anaconda3/envs/([^/]+)/bin/python", exe)
        if m and m.group(1) not in OUR_ENVS:
            bad.append(f"env {pid}: {cmd[:140]}")
    return bad


def gate(label: str, allow_busy: bool, hold_until: float, fh) -> bool:
    """Hold until the box is clear; give up (False) once `hold_until` (epoch s) has passed."""
    t_start = time.time()
    while True:
        bad = offenders(allow_busy)
        held = time.time() - t_start
        if not bad:
            log(f"GATE {label}: box clear" + (" (allow-busy: hot/env nets OFF)" if allow_busy else "")
                + (f" after {held/60:.1f} min of hold" if held > HOT_WIN + 5 else ""), fh)
            return True
        log(f"HOLD {label}: {len(bad)} offender(s), held {held/60:.1f} min:", fh)
        for b in bad[:12]:
            log(f"    {b}", fh)
        if time.time() + HOLD_POLL + HOT_WIN > hold_until:
            log(f"HELD_OUT {label}: the hold would pass its limit -- giving the box up", fh)
            return False
        time.sleep(HOLD_POLL)


# ------------------------------------------------------------------ one k
class Arm:
    def __init__(self, name, spec, outdir):
        self.name = name
        self.seat_user = spec["seat_username"]
        self.fp_user = spec["fp_username"]
        self.battles = int(spec["battles"])
        self.tag = name.lower()
        self.seat_log = outdir / f"{self.tag}.seat.stdout"
        self.fp_log = outdir / f"{self.tag}.fp.stdout"
        self.seat = None
        self.fp = None
        self.seat_launches = 0
        self.offset = 0
        self.buf = ""
        self.winners = 0
        self.turns_now = 0                  # |turn| lines in the battle in play
        self.turns: list[int] = []          # turns of each completed battle, FP's order
        self.first_winner_t = None
        self.last_winner_t = None
        self.last_growth_t = None
        self.fp_done_t = None
        self.errors: list[str] = []
        self.visits: list[dict] = []
        self.state = "init"   # -> running -> done | done_seat_killed | crashed | stalled | seat_died | timeout

    def tail(self, now):
        try:
            with open(self.fp_log, "r", errors="replace") as f:
                f.seek(self.offset)
                data = f.read()
                self.offset = f.tell()
        except FileNotFoundError:
            return
        if not data:
            return
        self.last_growth_t = now
        data = self.buf + data
        lines = data.split("\n")
        self.buf = lines.pop()          # a partial last line waits for the next poll
        for line in lines:
            if line.startswith(TURN):
                self.turns_now += 1
            elif WINNER in line:
                self.winners += 1
                self.turns.append(self.turns_now)
                self.turns_now = 0
                self.first_winner_t = self.first_winner_t or now
                self.last_winner_t = now
            elif "PROBE_VISITS" in line:
                m = VISITS_RE.search(line)
                if m:
                    d = {k: float(v) for k, v in m.groupdict().items() if v is not None}
                    d["arm"] = self.name
                    d["battle"] = self.winners       # 0-based index of the battle in play
                    self.visits.append(d)
            elif any(e in line for e in ERR_MARKERS):
                if len(self.errors) < 50:
                    self.errors.append(line[:300])


def killgroup(proc, grace=5.0):
    """SIGTERM then SIGKILL the child's whole process group (its own session). A leader that
    already exited can leave members behind (FP's pool workers), so the group is always swept."""
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        t = time.time()
        while time.time() - t < grace and proc.poll() is None:
            time.sleep(0.2)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def run_k(label, arm_names, prereg, root_out, fh, allow_busy, hold_until, end_by):
    outdir = root_out / label
    summary_path = outdir / "summary.json"
    if summary_path.exists():
        log(f"{label}: SKIP (summary exists)", fh)
        return json.loads(summary_path.read_text())
    arms_spec = [prereg["arms"][n] for n in arm_names]
    for n, spec in zip(arm_names, arms_spec):
        assert int(spec["search_time_ms"]) == SEARCH_TIME_MS, f"{n}: budget mismatch"
    users = [u for s in arms_spec for u in (s["seat_username"], s["fp_username"])]
    assert len(users) == len(set(users)), "username collision inside one k"
    est = est_k_s(len(arm_names), max(int(s["battles"]) for s in arms_spec))
    if end_by is not None and time.time() + est > end_by:
        log(f"{label}: NOT STARTED -- ~{est/60:.0f} min would end after --end-by", fh)
        return {"label": label, "status": "SKIPPED_END_BY"}
    hold_limit = hold_until if end_by is None else min(hold_until, end_by - est)
    if not gate(label, allow_busy, hold_limit, fh):
        return {"label": label, "status": "HELD_OUT"}
    if end_by is not None and time.time() + est > end_by:     # the gate itself took time
        log(f"{label}: NOT STARTED after the gate -- would end after --end-by", fh)
        return {"label": label, "status": "SKIPPED_END_BY"}
    srv = server_pid()
    if srv is None:
        log(f"{label}: NO SHOWDOWN SERVER on :8000", fh)
        return {"label": label, "status": "NO_SERVER"}

    outdir.mkdir(parents=True, exist_ok=True)
    arms = [Arm(n, prereg["arms"][n], outdir) for n in arm_names]
    base = os.environ.copy()
    for v in ("POKEMON_RL_ENCODER_C6", "POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH", "FP_TAPE_DIR",
              "PYTHONPATH"):
        base.pop(v, None)   # the W finals are c6-OFF (configs/eval/r6_reads_offfp.yaml arm_encoder)
    base.update(POKEMON_RL_ENCODER_V2="1", POKEMON_RL_ENCODER_IDS="1", PYTHONUNBUFFERED="1",
                OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")   # the reads queue's exports
    seat_env = dict(base, PYTHONPATH=str(REPO))   # the seat imports THIS tree's rl, not main's
    fp_env = base

    def launch_seat(a):
        a.seat_launches += 1
        a.seat = subprocess.Popen(
            [PY, "scripts/ch3_fp_h2h.py", "--prereg", PREREG, "--arm", a.name,
             "--battles", str(a.battles), "--tag", a.tag],
            cwd=REPO, env=seat_env, stdout=open(a.seat_log, "w"), stderr=subprocess.STDOUT,
            start_new_session=True)
        log(f"{label}: seat {a.name} pid {a.seat.pid} ({a.seat_user}), launch {a.seat_launches}", fh)

    timeline = open(outdir / "timeline.jsonl", "w")
    t_launch = time.time()
    status = None
    try:
        # ---- seats first, staggered; they print "waiting for" once loaded (before any login)
        for a in arms:
            launch_seat(a)
            time.sleep(SEAT_STAGGER)
        t_last_seat = time.time()
        while status is None:
            for a in arms:
                if a.seat.poll() is not None and "waiting for" in a.seat_log.read_text(errors="replace"):
                    # died AFTER it was ready: it may have logged in, so its name may be held
                    log(f"{label}: seat {a.name} DIED after ready (rc {a.seat.returncode}) -- "
                        "not relaunched on a possibly-held name", fh)
                    status = "STARTUP_FAILED"
                    break
                if a.seat.poll() is not None:
                    log(f"{label}: seat {a.name} DIED before ready (rc {a.seat.returncode})", fh)
                    if a.seat_launches > SEAT_RETRIES:
                        status = "STARTUP_FAILED"
                        break
                    time.sleep(SEAT_STAGGER)
                    launch_seat(a)
                    t_last_seat = time.time()
            if status:
                break
            ready = all(a.seat.poll() is None and "waiting for" in a.seat_log.read_text(errors="replace")
                        for a in arms)
            if ready and time.time() - t_last_seat >= SEAT_SETTLE:
                break
            if time.time() - t_last_seat > 300:
                log(f"{label}: seats not ready 300 s after the last launch", fh)
                status = "STARTUP_FAILED"
            time.sleep(1.0)
        if status is None:
            # ---- then every Foul Play, near-simultaneously
            for a in arms:
                a.fp = subprocess.Popen(
                    [FPPY, "run.py", "--websocket-uri", WS, "--ps-username", a.fp_user,
                     "--bot-mode", "challenge_user", "--user-to-challenge", a.seat_user,
                     "--pokemon-format", FORMAT, "--search-time-ms", str(SEARCH_TIME_MS),
                     "--search-parallelism", str(SEARCH_PARALLELISM),
                     "--run-count", str(a.battles)],
                    cwd=FPDIR, env=fp_env, stdout=open(a.fp_log, "w"), stderr=subprocess.STDOUT,
                    start_new_session=True)
                a.state = "running"
                a.last_growth_t = time.time()
                log(f"{label}: foul-play {a.name} pid {a.fp.pid} ({a.fp_user} -> {a.seat_user})", fh)
                time.sleep(FP_STAGGER)
            t_fp = time.time()
            psutil.cpu_percent(percpu=True)          # prime the per-core counters
            deadline = t_fp + max(a.battles for a in arms) * 6.0 + 600

            def write_row(now):
                """One sample: ps sweep (at t_ps) + per-core + memory, arms' counts as of `now`."""
                rows = ps_sweep()
                t_ps = time.time()
                percpu = psutil.cpu_percent(percpu=True)
                seat_pids = {a.seat.pid for a in arms if a.seat is not None}
                fp_pids = {a.fp.pid for a in arms if a.fp is not None}
                cls = classify(rows, seat_pids, fp_pids, srv, os.getpid())
                cpu_by, rss_by = {}, {}
                for pid, c in cls.items():
                    cpu_by[c] = cpu_by.get(c, 0.0) + rows[pid][1]
                    rss_by[c] = rss_by.get(c, 0) + rows[pid][2]
                vm, sw = psutil.virtual_memory(), psutil.swap_memory()
                timeline.write(json.dumps({
                    "t": round(now, 3), "t_ps": round(t_ps, 3),
                    "winners": {a.name: a.winners for a in arms},
                    "state": {a.name: a.state for a in arms},
                    "percpu": percpu,
                    "cpu_by_class": {k: round(v, 2) for k, v in cpu_by.items()},
                    "rss_kb_by_class": rss_by,
                    "pids": {str(pid): [cls[pid], rows[pid][0], round(rows[pid][1], 2), rows[pid][2]]
                             for pid in rows if cls[pid] != "other"},
                    "other_cpu_by_pid": {str(pid): round(rows[pid][1], 2)
                                         for pid in rows if cls[pid] == "other"},
                    "other_cmd": {str(pid): rows[pid][3][:80] for pid in rows
                                  if cls[pid] == "other" and rows[pid][1] > 60},
                    "mem_available": vm.available, "swap_used": sw.used,
                }) + "\n")
                timeline.flush()

            while True:
                time.sleep(POLL)
                now = time.time()
                for a in arms:
                    a.tail(now)
                # ---- liveness, per arm; no relaunch of a battle (see the module docstring)
                for a in arms:
                    if a.state != "running":
                        continue
                    s_rc, f_rc = a.seat.poll(), a.fp.poll()
                    if s_rc is not None or f_rc is not None:
                        time.sleep(1.0)
                        a.tail(now)              # an exit can race the poll's tail
                        s_rc, f_rc = a.seat.poll(), a.fp.poll()
                    if s_rc is not None:
                        a.state = "done" if s_rc == 0 else "seat_died"
                        if a.state != "done":
                            log(f"{label}: {a.name} SEAT EXITED rc={s_rc} at {a.winners}/{a.battles}", fh)
                            killgroup(a.fp)
                    elif f_rc is not None and a.winners >= a.battles:
                        a.fp_done_t = a.fp_done_t or now      # FP finished; its seat is closing
                        if now - a.fp_done_t > SEAT_EXIT_S:
                            log(f"{label}: {a.name} seat still up {SEAT_EXIT_S:.0f}s after its last "
                                "battle -- killed; the window is unaffected", fh)
                            killgroup(a.seat)
                            a.state = "done_seat_killed"
                    elif f_rc is not None:
                        a.state = "crashed"
                        log(f"{label}: {a.name} FOUL PLAY EXITED rc={f_rc} at {a.winners}/{a.battles} "
                            "-- arm stopped, k DISTURBED", fh)
                        killgroup(a.seat)
                    elif now - a.last_growth_t > STALL_S:
                        a.state = "stalled"
                        log(f"{label}: {a.name} STALLED ({STALL_S:.0f}s no FP log growth) at "
                            f"{a.winners}/{a.battles} -- arm stopped, k DISTURBED", fh)
                        killgroup(a.fp)
                        killgroup(a.seat)
                write_row(now)
                if all(a.state != "running" for a in arms):
                    break
                if now > deadline:
                    log(f"{label}: DEADLINE -- killing every arm", fh)
                    for a in arms:
                        if a.state == "running":
                            a.state = "timeout"
                    break
            time.sleep(POLL)
            for a in arms:
                a.tail(time.time())
            write_row(time.time())
    finally:
        for a in arms:
            killgroup(a.fp, grace=3.0)
            killgroup(a.seat, grace=3.0)
        timeline.close()

    if status is None:
        status = "OK" if all(a.state in ("done", "done_seat_killed") for a in arms) else "DISTURBED"
    # ---- idle gap; its last 30 s is the idle baseline of the box
    time.sleep(max(GAP_S - 30.0, 0.0))
    psutil.cpu_percent(percpu=True)
    rows_a = ps_sweep()
    time.sleep(30.0)
    idle_percpu = psutil.cpu_percent(percpu=True)
    rows_b = ps_sweep()
    idle_top = sorted(((rows_b[p][1] - rows_a[p][1], rows_b[p][3][:100]) for p in rows_b
                       if p in rows_a), reverse=True)[:5]
    for a in arms:
        a.tail(time.time())
    with open(outdir / "visits.jsonl", "w") as vf:
        for a in arms:
            for d in a.visits:
                vf.write(json.dumps(d) + "\n")
    seat_json = {}
    for a in arms:
        p = REPO / "results" / "fp_parallel_probe" / f"{a.tag}.json"
        if p.exists() and p.stat().st_mtime > t_launch:      # never a stale file
            seat_json[a.name] = str(p.relative_to(REPO))
    try:
        prov = provenance()
    except Exception as exc:                                  # never drop a completed k
        prov = {"error": repr(exc)}
    summary = {
        "label": label, "k": len(arms), "status": status,
        "arms": [{"arm": a.name, "seat_user": a.seat_user, "fp_user": a.fp_user,
                  "battles": a.battles, "state": a.state, "winners": a.winners,
                  "turns_per_battle": a.turns, "seat_launches": a.seat_launches,
                  "seat_pid": a.seat.pid if a.seat else None,
                  "fp_pid": a.fp.pid if a.fp else None,
                  "seat_rc": a.seat.returncode if a.seat else None,
                  "fp_rc": a.fp.returncode if a.fp else None,
                  "first_winner_t": a.first_winner_t, "last_winner_t": a.last_winner_t,
                  "visits_lines": len(a.visits), "errors": a.errors,
                  "seat_json": seat_json.get(a.name),
                  "seat_log": str(a.seat_log.relative_to(REPO)),
                  "fp_log": str(a.fp_log.relative_to(REPO))} for a in arms],
        "t_launch": t_launch, "poll_s": POLL,
        "server_pid": srv, "e_cores": list(E_CORES),
        "idle_baseline": {"percpu": idle_percpu,
                          "top_cpu_s_over_30s": [[round(x, 2), c] for x, c in idle_top]},
        "timeline": str((outdir / "timeline.jsonl").relative_to(REPO)),
        "visits": str((outdir / "visits.jsonl").relative_to(REPO)),
        "provenance": prov,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    log(f"{label}: {status} -- " + ", ".join(
        f"{a.name} {a.winners}/{a.battles} {a.state}" for a in arms), fh)
    return summary


def provenance() -> dict:
    import hashlib

    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    diff = run(["diff", "-rq", "--exclude", "__pycache__", "--exclude", ".git", "--exclude",
                "logs", str(FP_PROD), str(FPDIR)]).splitlines()
    srv = server_pid()
    return {
        "git_sha": run(["git", "rev-parse", "HEAD"], cwd=REPO).strip(),
        "git_dirty": bool(run(["git", "status", "--porcelain"], cwd=REPO).strip()),
        "main_git_sha": run(["git", "rev-parse", "HEAD"], cwd=MAIN).strip(),
        "main_git_dirty": bool(run(["git", "status", "--porcelain"], cwd=MAIN).strip()),
        "seat_pythonpath": str(REPO),
        "prereg_sha256": sha(REPO / PREREG),
        "fp_dir": str(FPDIR),
        "fp_main_py_sha256": sha(FPDIR / "fp/search/main.py"),
        "fp_prod_main_py_sha256": sha(FP_PROD / "fp/search/main.py"),
        "fp_gen1_patch_sha256": sha(REPO / "scripts/patches/foulplay_gen1_local.patch"),
        "fp_probe_patch_sha256": sha(REPO / "scripts/patches/foulplay_probe_visits.patch"),
        "fp_copy_diff_vs_prod": diff,      # expected: exactly fp/search/main.py
        "python_seat": PY, "python_fp": FPPY,
        "search_time_ms": SEARCH_TIME_MS, "search_parallelism": SEARCH_PARALLELISM,
        "host": run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip(),
        "priority": priority(),
        "server_nice": (os.getpriority(os.PRIO_PROCESS, srv) if srv else None),
        "power": run(["pmset", "-g", "batt"]).strip().splitlines()[:2],
        "load_avg": os.getloadavg(),
    }


def headroom_for_k8(summary: dict) -> tuple[bool, str]:
    """k=8 runs only if k=6's steady window is valid and projects to <= 10 busy cores at k=8.
    Two measures, the LARGER wins: the tracked process classes (per-pid carried-forward deltas,
    the read's own arithmetic) and the per-core utilisation minus the idle baseline (which also
    sees kernel_task, which ps never lists)."""
    sys.path.insert(0, str(Path(__file__).parent))
    from fp_parallel_probe_read import read_k
    try:
        r = read_k(summary["label"])
    except Exception as exc:
        return False, f"k=6 read failed: {exc!r}"
    if r.get("status") == "NO_WINDOW":
        return False, "k=6 has no valid steady window"
    busy = (r["util"]["p_busy_cores_mean"] + r["util"]["e_busy_cores_mean"]
            - r["util"]["idle_baseline_busy_cores"])
    cores = max(r["cores_tracked_total"], busy)
    proj = cores * 8 / 6
    return proj <= 10.0, (f"k=6 tracked {r['cores_tracked_total']:.2f} / util-over-idle "
                          f"{busy:.2f} cores -> k=8 projects {proj:.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ks", default="1,2,4,6")
    ap.add_argument("--k8-if-headroom", action="store_true",
                    help="after k=6, run k=8 only if k=6 projects to <= 10 cores at k=8")
    ap.add_argument("--smoke", action="store_true", help="smoke arm(s) x 3 battles, busy box OK")
    ap.add_argument("--smoke-arms", default="SMOKE", help="comma list, run concurrently")
    ap.add_argument("--smoke-label", default=None)
    ap.add_argument("--rerun", action="store_true", help="use the R2 username pairs")
    ap.add_argument("--hold-max-min", type=float, default=15.0)
    ap.add_argument("--end-by", default=None,
                    help="UTC ISO time; a k that cannot finish by then is not started")
    args = ap.parse_args()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # run the finally blocks
    os.chdir(REPO)
    root_out = REPO / "results" / "fp_parallel_probe"
    root_out.mkdir(parents=True, exist_ok=True)
    fh = open(root_out / "driver.log", "a")
    pr = priority()
    if pr["nice"] != 0 or pr["darwin_bg"]:
        log(f"REFUSING: this driver is niced / background QoS {pr} -- its timings would be "
            "wrong (launch through bash: zsh's BG_NICE nices every `&` job by +5)", fh)
        sys.exit(6)
    caff = subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(os.getpid())])
    prereg = yaml.safe_load(open(PREREG))
    end_by = (datetime.strptime(args.end_by, "%Y-%m-%dT%H:%M:%SZ")
              .replace(tzinfo=timezone.utc).timestamp() if args.end_by else None)
    log(f"driver pid {os.getpid()} ks={args.ks} smoke={args.smoke} rerun={args.rerun} "
        f"end_by={args.end_by} priority={pr} (caffeinate pid {caff.pid})", fh)

    def one(label, names, allow_busy, hold_max_s):
        try:
            return run_k(label, names, prereg, root_out, fh, allow_busy,
                         time.time() + hold_max_s, end_by)
        except Exception as exc:                  # a failed k never stops the sequence
            log(f"{label}: ERROR {exc!r} -- continuing with the next k (fresh usernames)", fh)
            return {"label": label, "status": "ERROR", "error": repr(exc)}

    results = []
    try:
        if args.smoke:
            arms = args.smoke_arms.split(",")
            results.append(one(args.smoke_label or "_".join(arms).lower(), arms, True, 0))
        else:
            sfx = "R2" if args.rerun else ""
            for k in [int(x) for x in args.ks.split(",")]:
                s = one(f"k{k}{sfx.lower()}", [f"K{k}A{i}{sfx}" for i in range(1, k + 1)],
                        False, args.hold_max_min * 60)
                results.append(s)
                if s.get("status") in ("HELD_OUT", "SKIPPED_END_BY", "NO_SERVER"):
                    log(f"{s['status']} -- stopping the sequence (box released)", fh)
                    break
            else:
                if args.k8_if_headroom and results and results[-1].get("k") == 6:
                    ok, why = headroom_for_k8(results[-1])
                    log(f"k=8 headroom check: {why} -> {'RUN' if ok else 'SKIP'}", fh)
                    if ok:
                        results.append(one(f"k8{sfx.lower()}", [f"K8A{i}{sfx}" for i in range(1, 9)],
                                           False, args.hold_max_min * 60))
    finally:
        caff.terminate()
    status = [r.get("status") for r in results]
    log(f"DRIVER DONE: {status}", fh)
    sys.exit(0 if all(s == "OK" for s in status) else
             4 if "HELD_OUT" in status else 5 if "SKIPPED_END_BY" in status else
             3 if all(s in ("OK", "DISTURBED") for s in status) else 7)


if __name__ == "__main__":
    main()

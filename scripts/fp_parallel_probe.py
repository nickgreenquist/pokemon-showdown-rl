"""FP-parallel THROUGHPUT probe: k concurrent off-Foul-Play arms on one box (maintainer's
FP-parallel ROI task, Phase 1, 2026-09-24). A MEASUREMENT HARNESS, not a read: no win rate from
it is quoted anywhere, and FP@20 here is a load generator.

    /opt/anaconda3/bin/python scripts/fp_parallel_probe.py --ks 1,2,4,6 --k8-if-headroom
    /opt/anaconda3/bin/python scripts/fp_parallel_probe.py --smoke          # 1 arm x 3 battles

Runs with the BASE anaconda python (psutil, for per-core utilisation). For each k it starts k
identical arms AT ONCE -- seat = scripts/ch3_fp_h2h.py (pokemon-showdown-rl env), Foul Play =
run.py from the probe copy (foul-play env), each on its own username pair on the one :8000
server, with scripts/ch3_r4_fp_runner.sh's exact command lines -- and records, every POLL s:

  * per-arm completed battles (Foul Play's "Winner:" lines) -> THE STEADY WINDOW: from the
    moment every arm is past its first battle (startup excluded) to the moment the first arm
    finishes (no arm running alone), the conforming window of docs/landmines.md;
  * per-process CPU-seconds and RSS from ONE `ps` sweep (the reads queue's instrument), by class:
    seat, FP main, FP search worker, FP resource tracker, Showdown main / sockets / simulators /
    validator / other, this driver, everything else;
  * per-core utilisation (psutil): cpu0-3 are the E-cores, cpu4-13 the P-cores on this M4 Pro
    (measured 2026-09-24: the niced R7 G1b jobs lit exactly cpu0-3);
  * system memory and swap;
  * Foul Play's PROBE_VISITS lines (scripts/patches/foulplay_probe_visits.patch): every search's
    MCTS iteration count, logged in FP's PARENT.

SAFETY. Every child starts in its OWN session (start_new_session) and is killed BY PROCESS GROUP.
Nothing here ever pkills by pattern: scripts/ch3_r4_fp_runner.sh's kill_fp sweeps EVERY
foul-play search worker on the box, which is safe only when arms are serial. No relaunch: a
crashed or stalled arm is killed, recorded, and its k is flagged DISTURBED (re-run it on the
rerun pairs, --rerun). A quiet-box gate (the reads queue's two nets: any process >= 50% of a
core over a 20 s CPU-time delta; any python from a conda env other than ours / Foul Play's)
holds before EVERY k, and refuses outright beside any other Foul Play, seat or training lane.

Resume-safe: a k whose summary.json exists is skipped. Outputs: results/fp_parallel_probe/
<label>/{summary.json, timeline.jsonl, visits.jsonl, arm logs, seat JSONs}.
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
SEAT_STAGGER = 2.0         # s between seat launches (the torch lazy-init landmine: stagger)
SEAT_SETTLE = 30.0         # s from the LAST seat launch to the first FP launch (the runner's 30)
FP_STAGGER = 0.5           # s between FP launches (no login thundering herd)
STALL_S = 180.0            # an FP log that has not grown for this long is a stalled arm
GAP_S = 60.0               # idle gap after each k (room reaping); its last 30 s = idle baseline
HOT_WIN = 20.0
HOT_PCT = 50.0
HOLD_POLL = 60.0
K_EST_S = 540.0            # one k, gate to idle gap: ~20 + 40 + 150 x ~1.8 s + 60, rounded up

WINNER = "Winner:"
VISITS_RE = re.compile(
    r"PROBE_VISITS t=(?P<t>[\d.]+) n=(?P<n>\d+) ms=(?P<ms>\d+) i=(?P<i>\d+) "
    r"visits=(?P<visits>\d+) prep_ms=(?P<prep_ms>[\d.]+) "
    r"search_wall_ms=(?P<search_wall_ms>[\d.]+) rebuilt=(?P<rebuilt>\d)"
    r"(?: search_ms=(?P<search_ms>-?[\d.]+))?")
ERR_MARKERS = ("nametaken", "Traceback", "Process pool broke", "ERROR")


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str, fh=None) -> None:
    line = f"[{utc()}] {msg}"
    print(line, flush=True)
    if fh is not None:
        fh.write(line + "\n")
        fh.flush()


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
    out = subprocess.run(["ps", "-Aeo", "pid=,ppid=,time=,rss=,command="],
                         capture_output=True, text=True).stdout
    rows = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(.*)", line)
        if m:
            rows[int(m.group(1))] = (int(m.group(2)), ps_secs(m.group(3)),
                                     int(m.group(4)), m.group(5))
    return rows


def server_pid() -> int | None:
    out = subprocess.run(["lsof", "-nP", "-iTCP:8000", "-sTCP:LISTEN", "-t"],
                         capture_output=True, text=True).stdout.split()
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


# ------------------------------------------------------------------ quiet-box gate
def offenders(allow_busy: bool) -> list[str]:
    """The reads queue's two nets (scripts/r6_reads_queue.sh hold_for_others), plus a hard
    refusal beside any other Foul Play / seat / training lane. Returns offender lines."""
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


def gate(label: str, allow_busy: bool, hold_max_s: float, fh) -> bool:
    held = 0.0
    while True:
        bad = offenders(allow_busy)
        if not bad:
            log(f"GATE {label}: box clear" + (" (allow-busy: hot/env nets OFF)" if allow_busy else "")
                + (f" after {held/60:.0f} min of hold" if held else ""), fh)
            return True
        log(f"HOLD {label}: {len(bad)} offender(s), held {held/60:.0f} min:", fh)
        for b in bad[:12]:
            log(f"    {b}", fh)
        if held >= hold_max_s:
            log(f"HELD_OUT {label}: gave up after {held/60:.0f} min", fh)
            return False
        time.sleep(HOLD_POLL)
        held += HOLD_POLL + HOT_WIN


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
        self.offset = 0
        self.buf = ""
        self.winners = 0
        self.first_winner_t = None
        self.last_winner_t = None
        self.last_growth_t = None
        self.errors: list[str] = []
        self.visits: list[dict] = []
        self.state = "init"   # init -> running -> done | crashed | stalled | seat_died

    def pgids(self):
        return [p.pid for p in (self.seat, self.fp) if p is not None]

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
            if WINNER in line:
                self.winners += 1
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


def run_k(label, arm_names, prereg, root_out, fh, allow_busy, hold_max_s):
    outdir = root_out / label
    summary_path = outdir / "summary.json"
    if summary_path.exists():
        log(f"{label}: SKIP (summary exists)", fh)
        return json.loads(summary_path.read_text())
    outdir.mkdir(parents=True, exist_ok=True)
    arms = [Arm(n, prereg["arms"][n], outdir) for n in arm_names]
    for a in arms:
        spec = prereg["arms"][a.name]
        assert int(spec["search_time_ms"]) == SEARCH_TIME_MS, f"{a.name}: budget mismatch"
    users = [u for a in arms for u in (a.seat_user, a.fp_user)]
    assert len(users) == len(set(users)), "username collision inside one k"

    if not gate(label, allow_busy, hold_max_s, fh):
        return {"label": label, "status": "HELD_OUT"}
    srv = server_pid()
    assert srv is not None, "no Showdown server listening on :8000"

    env = os.environ.copy()
    for v in ("POKEMON_RL_ENCODER_C6", "POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH", "FP_TAPE_DIR"):
        env.pop(v, None)   # the W finals are c6-OFF (configs/eval/r6_reads_offfp.yaml arm_encoder)
    env.update(POKEMON_RL_ENCODER_V2="1", POKEMON_RL_ENCODER_IDS="1", PYTHONUNBUFFERED="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")   # the reads queue's exports

    timeline = open(outdir / "timeline.jsonl", "w")
    t_launch = time.time()
    try:
        # ---- seats first, staggered; they print "waiting for" once loaded
        for a in arms:
            a.seat = subprocess.Popen(
                [PY, "scripts/ch3_fp_h2h.py", "--prereg", PREREG, "--arm", a.name,
                 "--battles", str(a.battles), "--tag", a.tag],
                cwd=REPO, env=env, stdout=open(a.seat_log, "w"), stderr=subprocess.STDOUT,
                start_new_session=True)
            log(f"{label}: seat {a.name} pid {a.seat.pid} ({a.seat_user})", fh)
            time.sleep(SEAT_STAGGER)
        t_last_seat = time.time()
        while True:
            dead = [a.name for a in arms if a.seat.poll() is not None]
            if dead:
                raise RuntimeError(f"seat(s) died during startup: {dead} (see *.seat.stdout)")
            ready = all("waiting for" in a.seat_log.read_text(errors="replace") for a in arms)
            if ready and time.time() - t_last_seat >= SEAT_SETTLE:
                break
            if time.time() - t_last_seat > 300:
                raise RuntimeError("seats not ready after 300 s")
            time.sleep(1.0)
        # ---- then every Foul Play, near-simultaneously
        for a in arms:
            a.fp = subprocess.Popen(
                [FPPY, "run.py", "--websocket-uri", WS, "--ps-username", a.fp_user,
                 "--bot-mode", "challenge_user", "--user-to-challenge", a.seat_user,
                 "--pokemon-format", FORMAT, "--search-time-ms", str(SEARCH_TIME_MS),
                 "--search-parallelism", str(SEARCH_PARALLELISM), "--run-count", str(a.battles)],
                cwd=FPDIR, env=env, stdout=open(a.fp_log, "w"), stderr=subprocess.STDOUT,
                start_new_session=True)
            a.state = "running"
            a.last_growth_t = time.time()
            log(f"{label}: foul-play {a.name} pid {a.fp.pid} ({a.fp_user} -> {a.seat_user})", fh)
            time.sleep(FP_STAGGER)
        t_fp = time.time()

        psutil.cpu_percent(percpu=True)          # prime the per-core counters
        deadline = t_fp + max(a.battles for a in arms) * 6.0 + 600
        def write_row(now):
            """One sample: ps sweep + per-core + memory, with the arms' counts as of `now`."""
            rows = ps_sweep()
            seat_pids = {a.seat.pid for a in arms}
            fp_pids = {a.fp.pid for a in arms if a.fp is not None}
            cls = classify(rows, seat_pids, fp_pids, srv, os.getpid())
            cpu_by, rss_by = {}, {}
            for pid, c in cls.items():
                cpu_by[c] = cpu_by.get(c, 0.0) + rows[pid][1]
                rss_by[c] = rss_by.get(c, 0) + rows[pid][2]
            mine = {str(pid): [cls[pid], rows[pid][0], round(rows[pid][1], 2), rows[pid][2]]
                    for pid in rows if cls[pid] not in ("other",)}
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            timeline.write(json.dumps({
                "t": round(now, 3),
                "winners": {a.name: a.winners for a in arms},
                "state": {a.name: a.state for a in arms},
                "percpu": psutil.cpu_percent(percpu=True),
                "cpu_by_class": {k: round(v, 2) for k, v in cpu_by.items()},
                "rss_kb_by_class": rss_by,
                "pids": mine,
                "other_cpu_by_pid": {str(pid): round(rows[pid][1], 2)
                                     for pid in rows if cls[pid] == "other"},
                "mem_available": vm.available, "swap_used": sw.used,
                "rusage_children_cpu": round(sum(os.times()[2:4]), 3),
                "self_cpu": round(sum(os.times()[0:2]), 3),
            }) + "\n")
            timeline.flush()

        while True:
            time.sleep(POLL)
            now = time.time()
            for a in arms:
                a.tail(now)
            # ---- liveness, per arm; no relaunch (see the module docstring)
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
                elif f_rc is not None and a.winners < a.battles:
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
        if p.exists():
            seat_json[a.name] = str(p.relative_to(REPO))
    disturbed = any(a.state != "done" for a in arms)
    summary = {
        "label": label, "k": len(arms), "status": "DISTURBED" if disturbed else "OK",
        "arms": [{"arm": a.name, "seat_user": a.seat_user, "fp_user": a.fp_user,
                  "battles": a.battles, "state": a.state, "winners": a.winners,
                  "seat_pid": a.seat.pid if a.seat else None,
                  "fp_pid": a.fp.pid if a.fp else None,
                  "seat_rc": a.seat.returncode if a.seat else None,
                  "fp_rc": a.fp.returncode if a.fp else None,
                  "first_winner_t": a.first_winner_t, "last_winner_t": a.last_winner_t,
                  "visits_lines": len(a.visits), "errors": a.errors,
                  "seat_json": seat_json.get(a.name),
                  "seat_log": str(a.seat_log.relative_to(REPO)),
                  "fp_log": str(a.fp_log.relative_to(REPO))} for a in arms],
        "t_launch": t_launch, "t_fp_start": t_fp, "poll_s": POLL,
        "server_pid": srv, "e_cores": list(E_CORES),
        "idle_baseline": {"percpu": idle_percpu,
                          "top_cpu_s_over_30s": [[round(x, 2), c] for x, c in idle_top]},
        "timeline": str((outdir / "timeline.jsonl").relative_to(REPO)),
        "visits": str((outdir / "visits.jsonl").relative_to(REPO)),
        "provenance": provenance(),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    log(f"{label}: {summary['status']} -- " + ", ".join(
        f"{a.name} {a.winners}/{a.battles} {a.state}" for a in arms), fh)
    return summary


def provenance() -> dict:
    def sh(cmd, cwd=REPO):
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout.strip()

    def sha(p):
        import hashlib
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    return {
        "git_sha": sh(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(sh(["git", "status", "--porcelain"])),
        "prereg_sha256": sha(REPO / PREREG),
        "fp_dir": str(FPDIR),
        "fp_main_py_sha256": sha(FPDIR / "fp/search/main.py"),
        "fp_prod_main_py_sha256": sha(FP_PROD / "fp/search/main.py"),
        "fp_gen1_patch_sha256": sha(REPO / "scripts/patches/foulplay_gen1_local.patch"),
        "fp_probe_patch_sha256": sha(REPO / "scripts/patches/foulplay_probe_visits.patch"),
        "fp_copy_identical_outside_patch": sh(
            ["diff", "-rq", "--exclude", "__pycache__", "--exclude", ".git", "--exclude", "logs",
             "--exclude", "main.py", str(FP_PROD), str(FPDIR)]) == "",
        "python_seat": PY, "python_fp": FPPY,
        "search_time_ms": SEARCH_TIME_MS, "search_parallelism": SEARCH_PARALLELISM,
        "host": sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "load_avg": os.getloadavg(),
    }


def headroom_for_k8(summary: dict) -> tuple[bool, str]:
    """k=8 runs only if k=6 left headroom: every arm done, and k=6's total tracked CPU inside
    its steady window projects to <= 10 cores at k=8 (the P-core budget)."""
    if summary.get("status") != "OK":
        return False, "k=6 not OK"
    tl = [json.loads(x) for x in open(REPO / summary["timeline"])]
    t0 = max(a["first_winner_t"] for a in summary["arms"])
    t1 = min(a["last_winner_t"] for a in summary["arms"])
    rows = [r for r in tl if t0 <= r["t"] <= t1]
    if len(rows) < 2:
        return False, "no steady window"
    a, b = rows[0], rows[-1]
    tracked = ("seat", "seat_child", "fp_main", "fp_worker", "fp_tracker", "fp_child_other",
               "node_main", "node_sockets", "node_sim", "node_validator", "node_other")
    cores = sum(b["cpu_by_class"].get(c, 0) - a["cpu_by_class"].get(c, 0) for c in tracked) / (
        b["t"] - a["t"])
    proj = cores * 8 / 6
    return proj <= 10.0, f"k=6 used {cores:.2f} cores -> k=8 projects {proj:.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ks", default="1,2,4,6")
    ap.add_argument("--k8-if-headroom", action="store_true",
                    help="after k=6, run k=8 only if k=6 projects to <= 10 cores at k=8")
    ap.add_argument("--smoke", action="store_true", help="one SMOKE arm x 3 battles, busy box OK")
    ap.add_argument("--smoke-arm", default="SMOKE")
    ap.add_argument("--rerun", action="store_true", help="use the R2 username pairs")
    ap.add_argument("--hold-max-min", type=float, default=15.0)
    ap.add_argument("--end-by", default=None,
                    help="UTC ISO time; a k that cannot finish by then (est. K_EST_S) is not started")
    args = ap.parse_args()

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # run the finally blocks
    os.chdir(REPO)
    root_out = REPO / "results" / "fp_parallel_probe"
    root_out.mkdir(parents=True, exist_ok=True)
    fh = open(root_out / "driver.log", "a")
    caff = subprocess.Popen(["caffeinate", "-i", "-s", "-w", str(os.getpid())])
    prereg = yaml.safe_load(open(PREREG))
    log(f"driver pid {os.getpid()} ks={args.ks} smoke={args.smoke} rerun={args.rerun} "
        f"(caffeinate pid {caff.pid})", fh)
    results = []
    try:
        if args.smoke:
            results.append(run_k(args.smoke_arm.lower(), [args.smoke_arm], prereg, root_out, fh,
                                 allow_busy=True, hold_max_s=0))
        else:
            ks = [int(x) for x in args.ks.split(",")]
            end_by = (datetime.strptime(args.end_by, "%Y-%m-%dT%H:%M:%SZ")
                      .replace(tzinfo=timezone.utc).timestamp() if args.end_by else None)

            def fits(k):
                if end_by is None or time.time() + K_EST_S <= end_by:
                    return True
                log(f"k={k} NOT STARTED: it would end after --end-by {args.end_by} (box released)", fh)
                return False

            for k in ks:
                if not fits(k):
                    results.append({"label": f"k{k}", "status": "SKIPPED_END_BY"})
                    break
                names = [f"K{k}A{i}" + ("R2" if args.rerun else "") for i in range(1, k + 1)]
                s = run_k(f"k{k}" + ("r2" if args.rerun else ""), names, prereg, root_out, fh,
                          allow_busy=False, hold_max_s=args.hold_max_min * 60)
                results.append(s)
                if s.get("status") == "HELD_OUT":
                    log("HELD_OUT -- stopping the sequence", fh)
                    break
            if args.k8_if_headroom and results and results[-1].get("k") == 6:
                ok, why = headroom_for_k8(results[-1])
                log(f"k=8 headroom check: {why} -> {'RUN' if ok else 'SKIP'}", fh)
                if ok and fits(8):
                    names = [f"K8A{i}" + ("R2" if args.rerun else "") for i in range(1, 9)]
                    results.append(run_k("k8" + ("r2" if args.rerun else ""), names, prereg,
                                         root_out, fh, allow_busy=False,
                                         hold_max_s=args.hold_max_min * 60))
    finally:
        caff.terminate()
    status = [r.get("status") for r in results]
    log(f"DRIVER DONE: {status}", fh)
    sys.exit(0 if all(s == "OK" for s in status) else
             4 if "HELD_OUT" in status else 5 if "SKIPPED_END_BY" in status else 3)


if __name__ == "__main__":
    main()

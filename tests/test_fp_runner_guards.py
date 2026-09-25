"""The Foul Play runner's and scheduler's launch guards refuse BEFORE anything starts.

EVERY wall-clock Foul Play is RETIRED for gen 1 (maintainer, 2026-09-25: FP@20 that morning,
FP@100/500 by ~14:05Z). scripts/ch3_r4_fp_runner.sh exits 7 on such an arm, whichever path set
its budget (the pre-reg arm or the environment), and scripts/fp_arms_parallel.py refuses it up
front. The one exception is a calibration's wall-clock REFERENCE, declared in the pre-reg arm as
`calibration_reference_for` and never from the environment. An FP@N arm or a declared reference
must get past that guard; here it then meets the FPDIR guard (exit 5), which proves it did.
Every case exits before the runner creates its output directory, so no server, seat or Foul
Play is ever involved; the bogus WS and FPDIR only bound the damage should a guard regress.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "ch3_r4_fp_runner.sh"
SCHED = REPO / "scripts" / "fp_arms_parallel.py"
COUNTERS = REPO / "scripts" / "fp_arm_counters.py"


def _prereg(tmp_path, arms):
    p = tmp_path / "prereg.yaml"
    p.write_text(yaml.safe_dump({"results_dir": str(tmp_path / "res"), "arms": arms}))
    return p


def _arm(**kw):
    return {"kind": "greedy_seat", "seat": "w104", "battles": 2, "search_time_ms": 20,
            "seat_username": "guardtestseat", "fp_username": "guardtestbot", **kw}


def _run_runner(tmp_path, prereg, **extra):
    env = dict(os.environ, PY=sys.executable, PREREG=str(prereg), ARM="GT", TAG="gt",
               OUT=str(tmp_path / "out"), FPDIR=str(tmp_path / "no-foul-play"),
               WS="ws://localhost:1/showdown/websocket", MAX_RELAUNCHES="1", POLL_SECS="1",
               STALL_POLLS="1", START_STAGGER="0", **extra)
    env.pop("FORMAT", None)
    env.pop("SEARCH_ITERATIONS", None)
    return subprocess.run(["bash", str(RUNNER)], env=env, capture_output=True, text=True,
                          timeout=60)


def test_runner_refuses_a_gen1_fp20_arm_from_the_prereg(tmp_path):
    r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": _arm()}))
    assert r.returncode == 7, r.stderr
    assert "RETIRED" in r.stderr
    assert not (tmp_path / "out").exists()


def test_runner_refuses_every_wall_clock_budget_not_just_20(tmp_path):
    for ms in (100, 500):
        r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": _arm(search_time_ms=ms)}))
        assert r.returncode == 7, (ms, r.stderr)
        assert f"FP@{ms}" in r.stderr
    assert not (tmp_path / "out").exists()


def test_runner_refuses_fp20_set_through_the_environment(tmp_path):
    # an older pre-reg without an arms entry takes its budget from the environment
    r = _run_runner(tmp_path, _prereg(tmp_path, {}), SEARCH_TIME_MS="20")
    assert r.returncode == 7, r.stderr
    assert not (tmp_path / "out").exists()


def test_runner_lets_an_fpn_arm_past_the_retirement_guard(tmp_path):
    arm = _arm(search_iterations=25000, search_iterations_early=12000)
    r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": arm}))
    assert r.returncode == 5, r.stderr          # the FPDIR guard, not the retirement one
    assert "RETIRED" not in r.stderr
    assert not (tmp_path / "out").exists()


def test_runner_lets_a_declared_calibration_reference_past(tmp_path):
    arm = _arm(search_time_ms=500, calibration_reference_for="FP@N for FP@500 (a test's pre-reg)")
    r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": arm}))
    assert r.returncode == 5, r.stderr
    assert "RETIRED" not in r.stderr


def test_runner_never_takes_the_exception_from_the_environment(tmp_path):
    r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": _arm(search_time_ms=500)}),
                    CAL_REF="sneaky", calibration_reference_for="sneaky")
    assert r.returncode == 7, r.stderr


def _run_sched(tmp_path, arm):
    env = dict(os.environ)
    env.pop("FORMAT", None)
    return subprocess.run([sys.executable, str(SCHED), "--prereg", str(_prereg(tmp_path, {"GT": arm})),
                           "--arms", "GT", "--slots", "1"], env=env, capture_output=True, text=True,
                          timeout=60)


def test_scheduler_refuses_wall_clock_arms_before_launching(tmp_path):
    for ms in (20, 500):
        r = _run_sched(tmp_path, _arm(search_time_ms=ms))
        assert r.returncode == 7, r.stdout + r.stderr
        assert "RETIRED" in r.stdout
        assert "LAUNCHED" not in r.stdout


def _probe_python():
    """The probe imports psutil, which the analysis env lacks; it runs under base conda."""
    for py in (sys.executable, "/opt/anaconda3/bin/python"):
        if Path(py).exists() and subprocess.run([py, "-c", "import psutil, yaml"],
                                                capture_output=True).returncode == 0:
            return py
    pytest.skip("no interpreter with psutil + yaml for scripts/fp_parallel_probe.py")


def test_probe_driver_refuses_without_a_declared_calibration():
    # the probe launches wall-clock Foul Play itself, bypassing the runner; a stale --end-by
    # keeps even a regressed guard from starting a k
    r = subprocess.run([_probe_python(), str(REPO / "scripts" / "fp_parallel_probe.py"),
                        "--ks", "1", "--end-by", "2000-01-01T00:00:00Z"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 7, r.stdout + r.stderr
    assert "RETIRED" in r.stderr


def test_counters_summarise_a_wall_clock_arms_visits_per_branch(tmp_path):
    log = tmp_path / "fp.stdout"
    lines = []
    for i, v in enumerate([590000, 610000, 600000, 1000]):      # the 1000 is a forced move
        lines.append(f"PROBE_VISITS t=1.0 n=2 ms=500 i={i} visits={v} prep_ms=1.0 "
                     f"search_wall_ms=1.0 rebuilt=1 search_ms={1.0 if v == 1000 else 500.0} iters_req=0")
    for i, v in enumerate([290000, 310000, 300000]):
        lines.append(f"PROBE_VISITS t=1.0 n=4 ms=250 i={i} visits={v} prep_ms=1.0 "
                     f"search_wall_ms=1.0 rebuilt=1 search_ms=250.0 iters_req=0")
    log.write_text("\n".join(lines) + "\n")
    rj = tmp_path / "runner.json"
    rj.write_text(json.dumps({"search_iterations": 0, "crash_forfeits": 0,
                              "calibration_reference_for": "FP@N for FP@500 (test)"}))
    subprocess.run([sys.executable, str(COUNTERS), str(log), str(rj)], check=True,
                   capture_output=True, text=True, timeout=60)
    out = json.loads(rj.read_text())
    assert out["calibration_reference"] is True
    assert out["fp_forced_searches"] == 1
    assert out["fp_visits_by_branch"]["n2_ms500"]["median"] == 600000
    assert out["fp_visits_by_branch"]["n2_ms500"]["searches"] == 3
    assert out["fp_visits_by_branch"]["n4_ms250"]["median"] == 300000

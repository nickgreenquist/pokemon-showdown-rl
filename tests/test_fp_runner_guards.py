"""The Foul Play runner's and scheduler's launch guards refuse BEFORE anything starts.

FP@20 is RETIRED for gen 1 (maintainer, 2026-09-25): scripts/ch3_r4_fp_runner.sh exits 7 on
such an arm, whichever path set its budget (the pre-reg arm or the environment), and
scripts/fp_arms_parallel.py refuses it up front. An FP@N arm must get past that guard; here it
then meets the unpatched-Foul-Play guard (exit 5), which proves it did. Every case exits before
the runner creates its output directory, so no server, seat or Foul Play is ever involved; the
bogus WS and FPDIR only bound the damage should a guard regress.
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "ch3_r4_fp_runner.sh"
SCHED = REPO / "scripts" / "fp_arms_parallel.py"


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


def test_runner_refuses_fp20_set_through_the_environment(tmp_path):
    # an older pre-reg without an arms entry takes its budget from the environment
    r = _run_runner(tmp_path, _prereg(tmp_path, {}), SEARCH_TIME_MS="20")
    assert r.returncode == 7, r.stderr
    assert not (tmp_path / "out").exists()


def test_runner_lets_an_fpn_arm_past_the_retirement_guard(tmp_path):
    arm = _arm(search_iterations=25000, search_iterations_early=12000)
    r = _run_runner(tmp_path, _prereg(tmp_path, {"GT": arm}))
    assert r.returncode == 5, r.stderr          # the unpatched-FPDIR guard, not the FP@20 one
    assert "RETIRED" not in r.stderr
    assert not (tmp_path / "out").exists()


def test_scheduler_refuses_a_gen1_fp20_arm_before_launching(tmp_path):
    env = dict(os.environ)
    env.pop("FORMAT", None)
    r = subprocess.run([sys.executable, str(SCHED), "--prereg", str(_prereg(tmp_path, {"GT": _arm()})),
                        "--arms", "GT", "--slots", "1"], env=env, capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 7, r.stdout + r.stderr
    assert "RETIRED" in r.stdout
    assert "LAUNCHED" not in r.stdout

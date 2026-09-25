"""scripts/fp500_iter_calib_read.py applies configs/eval/fp500_iter_calib.yaml's pre-stated rule.

The rule: median visits per per-search budget, non-forced searches only, rounded to the nearest
1000 with halves up. The read VOIDs when contaminated minutes exceed 5% of the run. The smoke
config it writes carries exactly the derived N. Synthetic foul-play logs only -- no server, no
Foul Play.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
READ = REPO / "scripts" / "fp500_iter_calib_read.py"


def _line(n, ms, v, sms, i=0):
    return (f"INFO PROBE_VISITS t=1.000 n={n} ms={ms} i={i} visits={v} prep_ms=1.0 "
            f"search_wall_ms=1.0 rebuilt=1 search_ms={sms:.3f} iters_req=0")


def _setup(tmp_path, contaminated_minutes=0):
    (tmp_path / "configs" / "eval").mkdir(parents=True)
    shutil.copy(REPO / "configs" / "eval" / "fp500_iter_calib.yaml", tmp_path / "configs" / "eval")
    out = tmp_path / "results" / "fp500_iter_calib"
    out.mkdir(parents=True)
    lines = []
    # ms 500: 1200 searches, the middle pair 600k/601k -> median 600.5k -> 601k (halves up)
    full = [590000] * 599 + [600000, 601000] + [610000] * 599
    lines += [_line(2, 500, v, 500.0) for v in full]
    # time pressure (1 battle, not 2): pooled by per-search budget, counted, disclosed if > 1%;
    # split evenly around the middle so the median stays the pair above
    lines += [_line(1, 500, 590000, 500.0)] * 5 + [_line(1, 500, 610000, 500.0)] * 5
    lines += [_line(4, 250, v, 250.0) for v in [290000] * 550 + [300000] * 11 + [310000] * 550]
    lines += [_line(2, 500, 1000, 1.2)] * 30                 # forced moves: excluded
    (out / "ref500.fp.stdout").write_text("\n".join(lines) + "\n")
    (out / "ref500.runner.json").write_text(json.dumps(
        {"calibration_reference": True, "fpn_counters_ok": True, "fpn_counters_why": []}))
    (out / "ref500.json").write_text("{}")
    (out / "ref500.runner.log").write_text(
        "[2026-09-27T10:00:00Z] seat pid 1\n[2026-09-27T11:00:00Z] seat exited rc=0\n")
    cont = [{"t": f"2026-09-27T10:{m:02d}:30Z", "pid": 9, "cores": 0.9, "cmd": "x"}
            for m in range(contaminated_minutes)]
    (out / "parallel_summary.json").write_text(json.dumps({"contamination": cont}))
    return out


def _read(tmp_path, *args):
    return subprocess.run([sys.executable, str(READ), *args], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60)


def test_the_rule_and_the_generated_smoke(tmp_path):
    out = _setup(tmp_path, contaminated_minutes=2)                # 2 of 60 minutes: disclosed only
    r = _read(tmp_path, "--ref", "REF500", "--write-smoke")
    assert r.returncode == 0, r.stdout + r.stderr
    calib = json.loads((out / "calib.json").read_text())
    assert calib["valid"] and calib["N"] == 601000 and calib["N_early"] == 300000
    assert calib["forced_searches"] == 30
    assert calib["branches"]["500"]["searches"] == 1210
    assert any("CONTAMINATION in 2" in d for d in calib["disclose"])
    arm = yaml.safe_load((out / "sm500n.yaml").read_text())["arms"]["SM500N"]
    assert (arm["search_iterations"], arm["search_iterations_early"]) == (601000, 300000)
    smoke_dir = yaml.safe_load((out / "sm500n.yaml").read_text())["results_dir"]
    assert smoke_dir.endswith("fp500_iter_calib/smoke")

    smoke = tmp_path / smoke_dir
    smoke.mkdir(parents=True)
    (smoke / "sm500n.runner.json").write_text(json.dumps(
        {"fpn_counters_ok": True, "fp_iters_exact_rate": 1.0, "fp_budget_seen": "fixed",
         "fp_nonforced_searches": 200}))
    (smoke / "sm500n.json").write_text("{}")
    r = _read(tmp_path, "--smoke")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS: FP@N 601000/300000, visits-matched to FP@500" in r.stdout


def test_contamination_beyond_five_percent_voids(tmp_path):
    _setup(tmp_path, contaminated_minutes=4)                      # 4 of 60 minutes = 6.7%
    r = _read(tmp_path, "--ref", "REF500", "--write-smoke")
    assert r.returncode != 0
    assert "VOID" in r.stderr
    assert not (tmp_path / "results" / "fp500_iter_calib" / "sm500n.yaml").exists()

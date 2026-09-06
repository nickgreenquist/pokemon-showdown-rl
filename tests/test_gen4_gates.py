"""scripts/gen4_wang50m_gates.py — the agent-owned in-run gates, offline.

The D-A closed form is the one that cost a review finding (the u x rows
form is off by one update and would STOP every lane): a synthetic rung
whose stored lr follows x = ((u - 1) * rows) / anneal PASSES, the same rung
with the u-form lr STOPS (exit 2). D-B: a synthetic history at 200 steps/s
PASSES, at 150 RECORDS, at 90 for two windows STOPS.
"""

import csv
import subprocess
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/gen4_wang50m_gates.py"
LR, A, B, ROWS, ANNEAL = 5.8884e-5, 8.0, 1.5, 19_968, 50_000_000


def _ckpt(path: Path, u: int, off_by_one: bool) -> None:
    x = (u if off_by_one else u - 1) * ROWS / ANNEAL
    lr = LR * (A * x + 1.0) ** (-B)
    torch.save({
        "agent": {"updates": u, "optimizer": {"param_groups": [{"lr": lr}, {"lr": lr}]}},
        "step": u * ROWS,
        "config": {"num_envs": 8, "agent": {"rollout_steps": 2496, "lr": LR, "lr_anneal_steps": ANNEAL,
                                            "lr_power_a": A, "lr_power_b": B}},
    }, path)


def _history(path: Path, rate: float, minutes: int = 100, start_step: int = 1_000_000) -> None:
    cols = ["_step", "_timestamp", "loss/entropy", "loss/clip_frac", "loss/approx_kl", "loss/policy",
            "harvest/rows_this_update", "harvest/seat1_rows", "harvest/version_lag_max",
            "harvest/rows_dropped", "harvest/rows", "harvest/discarded", "harvest/empty", "harvest/episodes"]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        t0, step = 1_800_000_000.0, start_step
        for k in range(minutes):  # one update per ~minute at the given rate
            w.writerow({"_step": step, "_timestamp": t0 + 60 * k, "loss/entropy": 1.7, "loss/clip_frac": 0.1,
                        "loss/approx_kl": 0.01, "loss/policy": -0.01, "harvest/rows_this_update": 19_900,
                        "harvest/seat1_rows": 19_968, "harvest/version_lag_max": 1, "harvest/rows_dropped": 1,
                        "harvest/rows": 19_900, "harvest/discarded": 0, "harvest/empty": 0, "harvest/episodes": 300})
            step += int(rate * 60)


def _run(run: Path, history: Path, *extra: str):
    cmd = [sys.executable, str(SCRIPT), str(run), "--history", str(history), "--wave-log", "/nonexistent", *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)
    return p.returncode, p.stdout


def test_d_a_closed_form_passes_the_u_minus_one_rung_and_stops_the_u_form(tmp_path):
    run = tmp_path / "gen4_wang50m_s200"; run.mkdir()
    hist = tmp_path / "history.csv"; _history(hist, 200.0, minutes=5)
    _ckpt(run / "ckpt_005000000.pt", u=251, off_by_one=False)
    rc, out = _run(run, hist)
    assert "D-A    PASS" in out and rc == 0, out
    _ckpt(run / "ckpt_005000000.pt", u=251, off_by_one=True)
    rc, out = _run(run, hist)
    assert "D-A    STOP" in out and rc == 2, out


def test_d_b_windows_read_pass_record_and_stop(tmp_path):
    run = tmp_path / "gen4_wang50m_s208"; run.mkdir()
    for rate, want, code in ((200.0, "D-B    PASS", 0), (150.0, "D-B    RECORD", 0), (90.0, "D-B    STOP", 2)):
        hist = tmp_path / f"h{int(rate)}.csv"; _history(hist, rate)
        rc, out = _run(run, hist)
        assert want in out and rc == code, out


def test_harvest_absence_after_update_one_is_a_kill(tmp_path):
    run = tmp_path / "gen4_wang50m_s216"; run.mkdir()
    hist = tmp_path / "h.csv"; _history(hist, 200.0, minutes=4)
    rows = list(csv.DictReader(hist.open()))
    rows[2]["harvest/rows_this_update"] = ""  # absent on update 3
    with hist.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    rc, out = _run(run, hist)
    assert "R0-3   KILL" in out and rc == 2, out

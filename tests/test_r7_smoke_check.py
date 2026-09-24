"""The R7 shakedown checker (`scripts/r7_smoke_check.py`, R0 gate 1 of the fleet pre-reg) on fake run dirs, engine-
and torch-free (the step and the history are passed in): a well-formed searched smoke with its resume PASSES, a
well-formed control PASSES, and each shape the gate exists to catch FAILS -- a searched-only counter on the control,
the searched arm's played_frac != searched_frac, the bank copied instead of mapped, a gate counter missing, the donor
anchors never installed (no THETA0 line), heads counters on a head-off base."""

from __future__ import annotations

import importlib.util
import pathlib

import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("r7_smoke_check", ROOT / "scripts/r7_smoke_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _fake(tmp: pathlib.Path, m, arm: str, *, drop=(), extra=(), played=None, zero_copy=True, theta0=True,
          theta0_resume=True, lag=1.0):
    run = tmp / f"runs/r7_fleet_smoke400k_{arm}_s1"
    run.mkdir(parents=True)
    (run / "config.yaml").write_text(yaml.safe_dump({"total_steps": 400_000, "collector": {"outcome_targets": False}}))
    (run / "meta.yaml").write_text(yaml.safe_dump({
        "git_sha": "abc", "git_dirty": False, "encoder": {"c6": True}, "engine": {"bank_zero_copy": zero_copy},
        "resumes": [{"from_step": 200_000}]}))
    rows = []
    for i in range(4):
        r = {"_step": 100_000 * (i + 1)}
        for c in m.GATE_COUNTERS["both"]:
            r[c] = 0.1 + 0.01 * i
        r["search/searched_frac"] = 0.4
        r["collect/weights_lag_updates"] = lag if i == 2 else 0.0
        r["search/played_frac"] = (0.4 if arm == "searched" else 0.0) if played is None else played
        if arm == "searched":
            for c in m.GATE_COUNTERS["searched_only"]:
                r[c] = 0.2
        for c in extra:
            r[c] = 0.3
        for c in drop:
            r.pop(c, None)
        rows.append(r)
    rows.append({"_step": 400_000, "l2init/anchor_dist_actor": 1.5, "eval/win_rate": 0.9})
    hist = run / "history.csv"
    pd.DataFrame(rows).to_csv(hist, index=False)
    rel = run.relative_to(tmp)
    log = tmp / f"{rel}.nohup.log"
    log.write_text((m.THETA0_LINE + " (runs/x/theta0.pt, abcdef012345)\n") if theta0 else "no anchors\n")
    (tmp / f"{rel}.resume.log").write_text((m.THETA0_RESUME_LINE + " (x, abcdef012345)\n") if theta0_resume else "resumed\n")
    wd = tmp / "watchdog.log"
    wd.write_text(f"[t] RESUMED {rel} -> from_step 200000 c6=1\n[t] {rel} DONE at step 400123/400000 (resumes=1)\n")
    return run, hist, wd, rel


def _check(tmp, m, arm, **kw):
    run, hist, wd, rel = _fake(tmp, m, arm, **kw)
    m.REPO = str(tmp)  # the fake tree is the repo the checker resolves logs and relpaths against
    return m.check(str(run), arm, str(wd), expect_resume=(arm == "searched"), step=400_123, history=str(hist))


def test_well_formed_smokes_pass(tmp_path):
    m = _mod()
    r = _check(tmp_path / "s", m, "searched")
    assert r["verdict"] == "PASS", r
    r = _check(tmp_path / "c", m, "control")
    assert r["verdict"] == "PASS", r


def test_each_shape_the_gate_exists_for_fails(tmp_path):
    m = _mod()
    so = m.GATE_COUNTERS["searched_only"][0]
    r = _check(tmp_path / "a", m, "control", extra=(so,))
    assert r["verdict"] == "FAIL" and r["gates"]["S_COUNTERS"]["searched_only_present_on_control"] == [so]
    r = _check(tmp_path / "b", m, "searched", played=0.0)
    assert r["verdict"] == "FAIL" and r["gates"]["S_COUNTERS"]["played_frac_ok"] is False
    r = _check(tmp_path / "c", m, "control", played=0.4)
    assert r["verdict"] == "FAIL" and r["gates"]["S_COUNTERS"]["played_frac_ok"] is False
    r = _check(tmp_path / "d", m, "searched", zero_copy=False)
    assert r["verdict"] == "FAIL" and not r["gates"]["S_META"]["ok"]
    r = _check(tmp_path / "e", m, "searched", drop=("loss/approx_kl_unsearched",))
    assert r["verdict"] == "FAIL" and "loss/approx_kl_unsearched" in r["gates"]["S_COUNTERS"]["missing"]
    r = _check(tmp_path / "f", m, "searched", theta0=False)
    assert r["verdict"] == "FAIL" and not r["gates"]["S_THETA0"]["ok"]
    r = _check(tmp_path / "g", m, "control", extra=("aux_outcome/ev_win",))
    assert r["verdict"] == "FAIL" and r["gates"]["S_COUNTERS"]["heads_leaked"] == ["aux_outcome/"]
    # The resume's own re-install line is required when the smoke was resumed (the first launch's cannot vouch).
    r = _check(tmp_path / "h", m, "searched", theta0_resume=False)
    assert r["verdict"] == "FAIL" and not r["gates"]["S_THETA0"]["ok"]
    # The two-core lane's backpressure bound: the collector acts on weights at most one update behind.
    r = _check(tmp_path / "i", m, "control", lag=2.0)
    assert r["verdict"] == "FAIL" and r["gates"]["S_COUNTERS"]["weights_lag_max"] == 2.0

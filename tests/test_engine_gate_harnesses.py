"""The D-1 and T-1 harnesses (plan §9) — the parts that can be tested without
running the gates.

Neither gate may run beside a training fleet, and neither has run. What IS
testable now is everything that would otherwise only be exercised on the day
the gate fires: the idle-box guard, the summary shape, and the band arithmetic
that decides PASS/FAIL. A comparison bug found on gate day costs a rerun of a
10,000-battle leg.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


d1 = _load("engine_d1")


def _rows(n=1000, p1_wins=520, ties=20, turns=30.0, seed=0):
    rng = np.random.default_rng(seed)
    outcome = np.array([1] * p1_wins + [0] * ties + [-1] * (n - p1_wins - ties))
    return {
        "outcome": outcome,
        "turns": np.full(n, turns) + rng.normal(0, 1e-9, n),
        "faints_p1": np.full(n, 5, dtype=np.uint8),
        "faints_p2": np.full(n, 4, dtype=np.uint8),
        "any_sleep": np.zeros(n, bool),
        "any_freeze": np.ones(n, bool),
    }


def test_the_summary_reports_every_read_the_gate_names():
    s = d1._summarise(_rows())
    for key in ("battles", "p1_win_rate", "tie_rate", "mean_turns", "turns_p50",
                "turns_p90", "mean_faints_p1", "sleep_fraction", "freeze_fraction"):
        assert key in s, key
    assert s["battles"] == 1000
    assert s["p1_win_rate"] == 0.52 and s["tie_rate"] == 0.02
    assert s["p1_win_rate"] + s["p2_win_rate"] + s["tie_rate"] == pytest.approx(1.0)
    # se ~ 0.005 at n=10k is the plan's own arithmetic; at n=1k it is 0.0158.
    assert s["p1_win_rate_se"] == pytest.approx(0.0158, abs=1e-4)


def _leg(name, **rows):
    return {"matchups": {f"{a}_vs_{b}": d1._summarise(_rows(**rows))
                         for a, b in d1.MATCHUPS}, "leg": name}


def test_identical_legs_pass_every_band():
    r = d1.compare(_leg("engine"), _leg("server"))
    assert r["pass"]
    for m in r["matchups"].values():
        assert all(m["pass"].values()), m


@pytest.mark.parametrize(
    "shift, band_broken",
    [
        # Just inside / just outside the 0.02 win-rate band.
        (dict(p1_wins=535), None),
        (dict(p1_wins=545), "p1_win_rate"),
        # Tie rate: the band is 0.005, so 20 -> 80 of 1000 breaks it.
        (dict(ties=80), "tie_rate"),
        # Mean turns: the band is RELATIVE, 5% of 30 turns = 1.5.
        (dict(turns=31.4), None),
        (dict(turns=32.0), "mean_turns_rel"),
    ],
)
def test_each_band_fires_on_its_own_read(shift, band_broken):
    r = d1.compare(_leg("engine", **shift), _leg("server"))
    if band_broken is None:
        assert r["pass"], r["matchups"]
        return
    assert not r["pass"]
    for m in r["matchups"].values():
        assert m["pass"][band_broken] is False, m["pass"]
        # The other bands must NOT fire: a gate that fails everything at once
        # tells you nothing about which mechanic differs.
        assert all(ok for k, ok in m["pass"].items() if k != band_broken)


def test_a_missing_server_matchup_fails_rather_than_passing_silently():
    server = _leg("server")
    server["matchups"].pop(next(iter(server["matchups"])))
    r = d1.compare(_leg("engine"), server)
    assert not r["pass"]
    assert any("MISSING" in str(m.get("status", "")) for m in r["matchups"].values())


def test_the_signed_delta_is_recorded_not_just_the_verdict():
    """Plan §9 and the A-1 precedent: the SIGNED delta stays in the record
    forever, so a later reader can see which way the engine differs."""
    r = d1.compare(_leg("engine", p1_wins=545), _leg("server"))
    for m in r["matchups"].values():
        assert m["deltas"]["p1_win_rate"] > 0
        assert set(m["descriptive_deltas"]) >= {
            "mean_faints_p1", "sleep_fraction", "freeze_fraction", "turns_p90"
        }


def test_both_gates_refuse_a_busy_box():
    """The whole point of the guard. Monkeypatched rather than dependent on
    what is actually running, so the test means the same thing on an idle box."""
    d1.fleet_is_running = lambda: ["a training lane (3 process(es))"]
    with pytest.raises(SystemExit, match="box is busy"):
        d1.check_box("engine", force=False)
    with pytest.raises(SystemExit, match="T-1"):
        d1.check_box("engine", force=False, gate="T-1")
    # --force does not make it clean; it makes it labelled.
    assert d1.check_box("engine", force=True) is True
    d1.fleet_is_running = lambda: []
    assert d1.check_box("engine", force=False) is False


def test_the_server_leg_is_absent_and_says_so_rather_than_faking_a_number():
    with pytest.raises(SystemExit, match="not implemented"):
        d1.server_leg(pathlib.Path("nope.bin"), 10, 0)


def test_t1_quotes_the_width_it_measures_at():
    """CLAUDE.md: a throughput number without its width and scope is the
    `showdown_throughput.py` landmine (~7x overstatement at [64,64])."""
    t1 = _load("engine_t1")
    assert t1.TRUNK_KWARGS["embed_dim"] == 64 and t1.TRUNK_KWARGS["entity_dim"] == 128
    assert t1.TRUNK_KWARGS["ctx_sizes"] == [384, 384]
    assert t1.HIDDEN_SIZES == [512, 512]
    assert t1.K_GRID == (32, 64, 128, 256, 512)
    assert t1.BANDS["b_steps_per_sec_at_256"] == 25_000
    assert t1.BANDS["c_realized_steps_per_sec"] == 2_000

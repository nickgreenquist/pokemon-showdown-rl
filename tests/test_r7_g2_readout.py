"""scripts/r7_g2_readout.py on synthetic arms: the crash-forfeit read rule, the strict boundaries,
the two-tally gate on n_eff, the launch-order gate, a failed FP@N counter VOIDing the pair, and
G2G_SANITY never acting as a gate. Engine-free."""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import r7_g2_readout as rd  # noqa: E402

SHA = "a" * 40
RULE = {k: f"<{k} text>" for k in ("clears", "does_not_clear", "negative", "void")}


def _arm(R, tag, seat_user, bot_user, wins, losses, ties, cf=0, fpn_ok=True, extra=None):
    n = wins + losses + ties
    seat = {"battles_finished": n, "our_wins": wins, "foulplay_wins": losses, "ties": ties,
            "our_win_rate": wins / n, "seat_username": seat_user, "fp_username": bot_user,
            "gate_all_challenges_resolved": True, "mask_desyncs": 0, "concurrent_decision_rate": 0.0,
            "max_concurrent_live_battles": 1, "prereg_sha256": "p" * 64, "rl_package": "/x/rl",
            "rl_git_sha": SHA, "rl_git_dirty": False, "launch_git_sha": SHA,
            "seat/decision_ms_p50": 1.0, "seat/decision_ms_p99": 2.0, "seat/decisions_per_sec": 9.0, **(extra or {})}
    runner = {"crash_forfeits": cf, "relaunches": cf, "max_relaunches": 30, "void_too_many_crashes": False,
              "fpn_counters_ok": fpn_ok, "fpn_counters_why": [] if fpn_ok else ["x"], "fp_iters_exact_rate": 1.0}
    (R / f"{tag}.json").write_text(json.dumps(seat))
    (R / f"{tag}.runner.json").write_text(json.dumps(runner))
    # Foul Play prints no Winner line for a crash-forfeit battle (it died in it); those were our "wins"
    lines = [f"Winner: {seat_user}"] * (wins - cf) + [f"Winner: {bot_user}"] * losses + ["Winner: None"] * ties
    (R / f"{tag}.fp.stdout").write_text("\n".join(lines) + "\n")
    (R / f"{tag}.runner.log").write_text(
        "[t] budget verified from foul-play's log: FIXED (search_time_ms=20, search_iterations=25000/12000)\n")


LOP = {"search/decisions": 1000, "lop/forced": 100, "search/searched": 880, "lop/worlds_built_rate": 0.97,
       "lop/no_world_rate": 0.02, "lop/mask_mismatch_rate": 0.0, "lop/errors": 0, "search/override_rate": 0.07,
       "lop/leaves_mean": 520.0}


def _setup(tmp_path, g=(1800, 1400, 0), l=(1950, 1250, 0), cf=(0, 0), fpn=(True, True), order=("G2G", "G2L")):
    R = tmp_path
    _arm(R, "g2g", "r7g2grseat", "r7g2grbot", *g, cf=cf[0], fpn_ok=fpn[0])
    _arm(R, "g2l", "r7g2lseat", "r7g2lbot", *l, cf=cf[1], fpn_ok=fpn[1], extra=LOP)
    (R / "parallel.log").write_text("[t0] START pid 1 slots=2\n" + "".join(
        f"[t] {a} LAUNCHED runner pid 9 (budget 25000; c6 off)\n" for a in order))
    (R / "g_matched_greedy.log").write_text(f"launch {SHA}\n===== 12 passed in 3.1s =====\n")
    return R


def _read(R):
    seats = {a: json.loads((R / f"{a.lower()}.json").read_text()) for a in ("G2G", "G2L")}
    runners = {a: json.loads((R / f"{a.lower()}.runner.json").read_text()) for a in ("G2G", "G2L")}
    ne = {a: rd.neff(seats[a], runners[a]) for a in seats}
    tallies = {a: rd.g_tally(seats[a], ne[a], rd.tally(str(R / f"{a.lower()}.fp.stdout"))) for a in seats}
    gg = rd.gates(str(R), seats, runners, ne, tallies, (400.0, 700.0))
    mg = rd.matched_greedy(str(R / "g_matched_greedy.log"), SHA)
    return seats, ne, rd.primary(ne["G2G"], ne["G2L"]), gg, mg


def test_a_clean_clear_passes_every_gate_and_reads_clears(tmp_path):
    seats, ne, prim, gg, mg = _read(_setup(tmp_path))
    assert all(v["ok"] for v in gg.values()) and mg["ok"], {k: v for k, v in gg.items() if not v["ok"]}
    assert prim["branch"] == "clears" and prim["delta"] == pytest.approx(1950 / 3200 - 1800 / 3200)
    assert "G2G_SANITY" not in gg          # a disclosure, never a gate
    assert "**CLEARS**" in rd.render(seats, ne, prim, gg, mg, RULE)


def test_the_crash_forfeit_rule_removes_the_forfeits_from_n_and_wins_and_the_tallies_still_agree(tmp_path):
    _, ne, _, gg, _ = _read(_setup(tmp_path, l=(1953, 1250, 0), cf=(0, 3)))
    assert (ne["G2L"]["n_eff"], ne["G2L"]["wins_eff"]) == (3200, 1950)
    assert gg["G_RUNNER"]["G2L"]["tally_agrees"] is True


def test_the_boundaries_are_strict_in_exact_arithmetic():
    """A delta EXACTLY +0.025 reads NOT met (at n 1e8 the 2*se_diff clause is ~1.4e-4, so only the
    strict +0.025 boundary decides); in floats 0.525 - 0.5 is 0.025000000000000022 and would clear."""
    n = 10**8
    at = {"wins_eff": n // 2, "n_eff": n}
    exact = rd.primary(at, {"wins_eff": 52_500_000, "n_eff": n})
    assert exact["branch"] == "does_not_clear" and exact["on_boundary"]
    assert rd.primary(at, {"wins_eff": 52_500_001, "n_eff": n})["branch"] == "clears"
    assert rd.primary(at, {"wins_eff": 47_500_000, "n_eff": n})["branch"] == "does_not_clear"
    assert rd.primary(at, {"wins_eff": 47_499_999, "n_eff": n})["branch"] == "negative"


def test_a_failed_fpn_counter_voids_the_pair(tmp_path):
    seats, ne, prim, gg, mg = _read(_setup(tmp_path, fpn=(True, False)))
    assert gg["G_FPN_COUNTERS"]["ok"] is False
    assert "**VOID**" in rd.render(seats, ne, prim, gg, mg, RULE)


def test_the_control_must_launch_first(tmp_path):
    _, _, _, gg, _ = _read(_setup(tmp_path, order=("G2L", "G2G")))
    assert gg["G_CONTROL_FIRST"]["ok"] is False


def test_a_skipped_matched_greedy_test_is_not_a_pass(tmp_path):
    R = _setup(tmp_path)
    (R / "g_matched_greedy.log").write_text(f"launch {SHA}\n===== 11 passed, 1 skipped in 3.1s =====\n")
    assert rd.matched_greedy(str(R / "g_matched_greedy.log"), SHA)["ok"] is False


def test_the_leaves_band_is_read_from_the_prereg_never_typed(tmp_path):
    import yaml
    pre = yaml.safe_load((ROOT / "configs/eval/r7_g2.yaml").read_text())
    lo, hi = rd.leaves_band(pre)
    assert 0 < lo < hi
    seats, ne, prim, gg, mg = _read(_setup(tmp_path))
    assert rd.operator_ran(seats["G2L"], (530.0, 900.0))["ok"] is False      # 520 leaves outside a band -> FAIL
    with pytest.raises(ValueError):
        rd.leaves_band({"R0_gates": [{"name": "G_OPERATOR_RAN", "leaves_band": [700, 400]}]})


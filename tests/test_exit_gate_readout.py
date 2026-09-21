"""scripts/exit_gate_readout.py: the exit gate's readout arithmetic and gates on synthetic arms --
the rule (>= +0.025 AND >= 2*se), the G2 tally (two tallies agreeing, `Winner: None` is the tie),
the change-rate formula from docs/landmines.md, and the R0 gates' evidence."""
import json
import math
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from exit_gate_readout import change_rate, g2, gates, primary, tally  # noqa: E402


def _arm(seat, bot, wins, losses, ties, **extra):
    n = wins + losses + ties
    d = {"seat_username": seat, "fp_username": bot, "battles_finished": n, "our_wins": wins,
         "foulplay_wins": losses, "ties": ties, "our_win_rate": wins / n, "prereg_sha256": "abc",
         "launch_git_sha": "deadbeef"}
    d.update(extra)
    return d


def test_primary_rule_and_boundaries():
    a = _arm("cs", "cb", 1877, 1321, 2)
    b = _arm("ts", "tb", 1877 + 100, 1221, 2)
    p = primary(a, b)
    assert abs(p["delta"] - 100 / 3200) < 1e-12
    assert abs(p["se_diff"] - math.sqrt(a["our_win_rate"] * (1 - a["our_win_rate"]) / 3200
                                        + b["our_win_rate"] * (1 - b["our_win_rate"]) / 3200)) < 1e-12
    assert p["clears"] and not p["near_boundary"]
    flat = primary(a, _arm("ts", "tb", 1877, 1321, 2))
    assert flat["delta"] == 0 and not flat["clears"]
    # +0.025 exactly (80 of 3200) is met by the pre-reg's >= but flagged as a boundary
    edge = primary(a, _arm("ts", "tb", 1877 + 80, 1241, 2))
    assert abs(edge["delta"] - 0.025) < 1e-12 and edge["near_boundary"]
    assert edge["clears"] == (edge["delta"] >= 2 * edge["se_diff"])


def test_tally_and_g2(tmp_path):
    p = tmp_path / "x.fp.stdout"
    p.write_text("noise\nWinner: ts\nWinner: tb\nWinner: ts\nWinner: None\n"
                 'Winner","type":"normal"},{"symbol":"x"}\n')
    t = tally(str(p))
    assert dict(t) == {"ts": 2, "tb": 1, "None": 1}, "the JSON blob line must not count"
    ok = g2(_arm("ts", "tb", 2, 1, 1), t)
    assert ok["ok"] and ok["ties_json_vs_fp"] == (1, 1)
    bad = g2(_arm("ts", "tb", 3, 1, 0), t)
    assert not bad["ok"]


def test_change_rate_formula():
    b = _arm("ts", "tb", 1, 1, 0, **{"search/decisions": 73, "search/placeholder_skips": 3,
                                     "search/flips": 9, "search/overrides": 9, "search/override_rate": None})
    c = change_rate(b)
    assert c["available"] and c["denominator"] == 70 and abs(c["flip_rate"] - 9 / 70) < 1e-12
    assert c["override_rate_field"] is None
    assert not change_rate(_arm("ts", "tb", 1, 1, 0))["available"]


def test_gates_evidence(tmp_path):
    a = _arm("cs", "cb", 10, 10, 0)
    b = _arm("ts", "tb", 10, 10, 0, **{"tree/kl_pi_prior": 1.1, "tree/pi_top1": 0.7,
                                       "tree/argmax_moved": 0.16, "search/ms_mean": 800.0})
    aj, bj = tmp_path / "a.json", tmp_path / "b.json"
    aj.write_text(json.dumps(a)); time.sleep(0.01); bj.write_text(json.dumps(b))
    os.utime(aj, (1, 1)); os.utime(bj, (2, 2))
    al, bl = tmp_path / "a.runner.log", tmp_path / "b.runner.log"
    al.write_text("[2026-09-20T23:06:52Z] seat pid 1\n"); bl.write_text("[2026-09-21T00:36:09Z] seat pid 2\n")
    g = gates(a, b, str(aj), str(bj), str(al), str(bl), 766.6)
    assert all(v["ok"] for v in g.values()), g
    assert abs(g["G_BUDGET_REALIZED"]["ratio"] - 800 / 766.6) < 1e-9
    # the iters knob not reaching the tree reads as a budget far below the screen's
    b2 = dict(b); b2["search/ms_mean"] = 50.0
    assert not gates(a, b2, str(aj), str(bj), str(al), str(bl), 766.6)["G_BUDGET_REALIZED"]["ok"]
    # a missing expert counter fails G_EXPERT_REPORTED
    b3 = dict(b); b3["tree/pi_top1"] = None
    assert gates(a, b3, str(aj), str(bj), str(al), str(bl), 766.6)["G_EXPERT_REPORTED"]["missing"] == ["tree/pi_top1"]
    # control launched after the tree fails G_CONTROL_FIRST
    bl.write_text("[2026-09-20T22:00:00Z] seat pid 2\n")
    assert not gates(a, b, str(aj), str(bj), str(al), str(bl), 766.6)["G_CONTROL_FIRST"]["ok"]

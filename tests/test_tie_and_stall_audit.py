"""The tie audit must not become a lever.

Its finding is that the tie rate is a SYMPTOM of weakness -- so the failure mode
to guard against is someone reading it the other way round and optimising it.
These tests pin the arithmetic that supports "symptom", and the cap constant
that defines a stall.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

MOD = Path(__file__).parent.parent / "scripts/tie_and_stall_audit.py"
spec = importlib.util.spec_from_file_location("tie_and_stall_audit", MOD)
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


def test_the_cap_is_the_showdown_turn_limit_and_is_named_once():
    """A stall is defined by ONE constant. If it drifts, "51% of ties are
    stalls" silently becomes a different claim."""
    assert ts.TURN_CAP == 1000
    src = MOD.read_text()
    assert src.count("TURN_CAP = ") == 1
    assert "1000" not in src.split("TURN_CAP = 1000")[1].split("def main")[0], (
        "the cap is hardcoded a second time below its own constant")


def test_it_skips_arms_without_per_battle_data_rather_than_crashing():
    """Most result JSONs in this repo are not h2h arms. The audit walks all of
    them, so a missing key must be a skip and never a traceback."""
    assert hasattr(ts, "main")
    src = MOD.read_text()
    assert '"turns" not in pb[0]' in src
    assert "json.JSONDecodeError" in src, "a malformed JSON must not kill the sweep"


def test_ties_are_non_wins_which_is_the_whole_reason_this_matters(tmp_path):
    """The locked protocol counts a tie as a non-win, so tie rate subtracts
    from win rate one-for-one. This pins that reading against the artifacts:
    our_wins / battles_finished must equal our_win_rate even when ties exist."""
    import glob
    checked = 0
    for p in glob.glob(str(Path(__file__).parent.parent / "results/*/*.json")):
        if "runner" in p or "/smoke" in p:
            continue
        try:
            d = json.loads(Path(p).read_text())
        except Exception:
            continue
        if not all(k in d for k in ("our_wins", "battles_finished", "our_win_rate", "ties")):
            continue
        if d["ties"] == 0 or d["battles_finished"] < 500:
            continue
        assert d["our_win_rate"] == (d["our_wins"] / d["battles_finished"]), p
        assert d["our_wins"] + d["ties"] <= d["battles_finished"], p
        checked += 1
    assert checked > 0, "no arm with ties found -- the invariant went untested"

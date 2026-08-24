"""CH3 R5b BI-1 (the per-decision recorder) — offline gates. No server.

Pinned here, per pre-reg Q4/F-P2/F-R (configs/eval/ch3_r5b_exit.yaml):

* placeholder rows (no `search/row_ev` in stats) are EXCLUDED at the
  recording site — they have no teacher target and would self-label;
* the persisted whitelist is exactly {obs, mask, row_ev, chosen,
  policy_argmax, battle_id, decision_index, lane} and nothing else;
* row_ev round-trips: NaN exactly at actions the search did not score,
  finite exactly at the scored ones — F-R's offline softmax recompute
  depends on it;
* persisted obs width == 828 (F-P2) is a hard assert at dump time;
* D-1: a non-T-PASS t_gate_readout stops every entry point;
* collection-time preflight: the eight d/p pins must still be
  PLACEHOLDERS — a stale fit leaking a real sha into a pre-fit
  collection fails loudly.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_r5b_collect as collect  # noqa: E402


class _FakeSA:
    """Scripted stats stream: searched decisions carry search/row_ev."""

    def __init__(self, script):
        self._script = list(script)
        self.counters = {"search/decisions": 0, "search/placeholder_skips": 0,
                         "search/flips": 0}

    def act(self, battle, obs, mask, battle_index, decision_index):
        stats = self._script.pop(0)
        return stats.get("search/chosen", 0), stats

    def entropy_median(self):
        return 0.5


def _searched(chosen, argmax, row_ev):
    return {"search/row_ev": row_ev, "search/chosen": chosen,
            "search/policy_argmax": argmax, "search/leaves": 353}


def test_placeholder_rows_excluded_and_whitelist_exact(tmp_path):
    mask = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0])
    rec = collect._RecordingSearchAgent(
        _FakeSA([
            _searched(1, 3, {0: 0.1, 1: 0.9, 3: -0.2}),
            {"search/placeholder_skip": 1, "search/chosen": 0},
            _searched(0, 0, {0: 0.4, 1: 0.2, 3: 0.3}),
        ]),
        "s62",
    )
    obs = np.zeros(828, dtype=np.float32)
    for i in range(3):
        rec.act(None, obs, mask, battle_index=100, decision_index=i)
    assert len(rec.rows) == 2, "placeholder row must not be recorded"
    out = tmp_path / "s62.chunk00.npz"
    assert rec.dump_chunk(out) == 2
    data = np.load(out)
    assert sorted(data.files) == sorted([
        "obs", "mask", "row_ev", "chosen", "policy_argmax", "battle_id",
        "decision_index", "lane"])
    assert data["obs"].shape == (2, 828)
    assert data["chosen"].tolist() == [1, 0]
    assert data["policy_argmax"].tolist() == [3, 0]
    assert data["battle_id"].tolist() == [100, 100]
    assert data["decision_index"].tolist() == [0, 2]
    assert str(data["lane"]) == "s62"


def test_row_ev_nan_pattern_roundtrips(tmp_path):
    mask = np.array([1, 1, 0, 1, 0, 0, 0, 0, 0])
    rec = collect._RecordingSearchAgent(
        _FakeSA([_searched(1, 1, {0: 0.125, 1: 0.5, 3: -1.75})]), "s63")
    rec.act(None, np.zeros(828, dtype=np.float32), mask, 7, 0)
    out = tmp_path / "x.npz"
    rec.dump_chunk(out)
    ev = np.load(out)["row_ev"][0]
    assert ev[0] == np.float32(0.125) and ev[1] == np.float32(0.5)
    assert ev[3] == np.float32(-1.75)
    assert np.isnan(ev[[2, 4, 5, 6, 7, 8]]).all()


def test_dump_asserts_obs_width_828(tmp_path):
    rec = collect._RecordingSearchAgent(
        _FakeSA([_searched(0, 0, {0: 1.0})]), "s62")
    rec.act(None, np.zeros(64, dtype=np.float32), np.array([1, 1]), 0, 0)
    with pytest.raises(AssertionError, match="F-P2"):
        rec.dump_chunk(tmp_path / "bad.npz")


def test_d1_refuses_without_t_pass(tmp_path, monkeypatch):
    bad = tmp_path / "t_gate_readout.json"
    bad.write_text(json.dumps({"cell": "T-FAIL"}))
    monkeypatch.setattr(collect, "T_GATE_READOUT", str(bad))
    with pytest.raises(AssertionError, match="D-1"):
        collect.assert_t_gate_pass()


def test_preflight_rejects_real_sha_on_fit_time_pin(monkeypatch):
    monkeypatch.setenv("POKEMON_RL_ENCODER_V2", "1")
    monkeypatch.setenv("POKEMON_RL_ENCODER_IDS", "1")
    pins = {name: {"path": f"runs/{name}.pt", "sha256": "<filled at fit time>"}
            for name in ("d62", "d63", "d64", "d65", "p62", "p63", "p64", "p65")}
    pins.update({name: {"path": f"runs/{name}.pt", "sha256": "aa"}
                 for name in ("s62", "s63", "s64", "s65", "clone")})
    pins["d62"]["sha256"] = "deadbeef"  # a stale fit leaked in
    pins["x99"] = pins.pop("clone")     # keep count at 13
    prereg = {"checkpoints": pins, "expected_pins": 13}
    with pytest.raises(AssertionError):
        collect._preflight(prereg, "s62")

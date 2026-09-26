"""`scripts/native_tree_gates.py diff` -- the regression check of a refactor: the roots two
oracle tags share must compare BITWISE (q, n, pi, the action and every counter but the
timing ones); exit 0 when identical, 1 on any difference. Pure JSON, no engine."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import pathlib

_P = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "native_tree_gates.py"
_spec = importlib.util.spec_from_file_location("native_tree_gates", _P)
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)


def _row(pid: int) -> dict:
    arm = {"q": [0.25, None, -0.5], "n": [40.0, 0.0, 12.0], "pi": [0.7, 0.0, 0.3], "action": 1,
           "counters": {"tree/nodes": 90.0, "tree/depth_mean": 3.25, "tree/v_mix": float("nan"), "search/ms": 812.0},
           "errors": {}}
    return {"version": G.ORACLE_VERSION, "pid": pid, "bucket": 0, "turn": 3, "a_greedy": 1, "git_sha": "abc",
            "rows": [1, 4, 6], "worlds_built": 8, "worlds_refused": [], "dials": {"br": {"sims": 1800}},
            "arms": {"br": arm, "rm": copy.deepcopy(arm)}}


def _write(d: pathlib.Path, tag: str, rows: list[dict]) -> None:
    (d / f"{tag}.rows.s0of1.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _diff(d: pathlib.Path, tag: str) -> int:
    return G.oracle_diff(argparse.Namespace(out_dir=str(d), tag=tag, against="ref"))


def test_diff_identical_and_each_kind_of_difference(tmp_path, capsys):
    ref = [_row(0), _row(3)]
    _write(tmp_path, "ref", ref)
    same = copy.deepcopy(ref)
    same[0]["arms"]["br"]["counters"]["search/ms"] = 999.0            # timing never counts
    same[1]["git_sha"] = "def"
    _write(tmp_path, "same", same)
    assert _diff(tmp_path, "same") == 0
    assert "IDENTICAL" in capsys.readouterr().out
    for name, edit in (("q", lambda r: r["arms"]["br"]["q"].__setitem__(0, 0.25 + 1e-12)),
                       ("unvisited", lambda r: r["arms"]["br"]["q"].__setitem__(1, 0.0)),
                       ("n", lambda r: r["arms"]["rm"]["n"].__setitem__(2, 13.0)),
                       ("pi", lambda r: r["arms"]["br"]["pi"].__setitem__(0, 0.7 + 1e-12)),
                       ("action", lambda r: r["arms"]["br"].__setitem__("action", 6)),
                       ("counter", lambda r: r["arms"]["rm"]["counters"].__setitem__("tree/nodes", 91.0)),
                       ("nan", lambda r: r["arms"]["rm"]["counters"].__setitem__("tree/v_mix", 0.1)),
                       ("root", lambda r: r.__setitem__("worlds_built", 7))):
        rows = copy.deepcopy(ref)
        edit(rows[1])
        _write(tmp_path, name, rows)
        assert _diff(tmp_path, name) == 1, name
        assert "DIFFERENCES" in capsys.readouterr().out


def test_diff_needs_shared_roots(tmp_path):
    _write(tmp_path, "ref", [_row(0)])
    _write(tmp_path, "other", [_row(3)])
    assert _diff(tmp_path, "other") == 1

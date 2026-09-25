"""scripts/eval_checkpoint.py stamps the `rl` tree it runs, read at LAUNCH (docs/CLEANUP.md L10): it stamped no
sha at all, and R7's LR-smoke vs-SH evals -- gate inputs -- run through it. Offline: every heavy seam is faked."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("eval_ckpt_prov", ROOT / "scripts" / "eval_checkpoint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_report_carries_the_tree_read_before_the_checkpoint_loaded(monkeypatch, tmp_path):
    m = _mod()
    tree = {"sha": "sha-at-launch"}
    monkeypatch.setattr(m, "_launch_provenance",
                        lambda: {"rl_package": "rl", "launch_git_sha": tree["sha"], "launch_git_dirty": False})

    def load(path):
        tree["sha"] = "sha-committed-mid-eval"   # a commit lands after launch
        return {"config": {"env_id": "Showdown-v0", "seed": 1, "total_steps": 1, "eval_every": 1,
                           "eval_episodes": 0, "run_name": "r"}, "agent": {}, "step": 7}

    class _Env:
        def close(self):
            pass

    class _Agent:
        def load_state_dict(self, sd):
            pass

    monkeypatch.setattr(m, "load_checkpoint", load)
    monkeypatch.setattr(m, "make_eval_env", lambda cfg: _Env())
    monkeypatch.setattr(m, "frozen_obs_env", lambda env, cfg, ckpt: env)
    monkeypatch.setattr(m, "make_agent", lambda cfg, env: _Agent())
    monkeypatch.setattr(m, "_run_eval_episodes", lambda agent, env, n, seed_start: ([1.0], [1], [None]))
    monkeypatch.setattr(m, "eval_metrics", lambda *a, **k: {"win_rate": 1.0})
    monkeypatch.setattr(m, "mask_desync_total", lambda: 0)
    out = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["eval_checkpoint.py", "x.pt", "--episodes", "1", "--out", str(out)])
    m.main()
    rep = json.loads(out.read_text())
    assert rep["launch_git_sha"] == "sha-at-launch"
    assert rep["launch_git_dirty"] is False
    assert rep["win_rate"] == 1.0 and rep["step"] == 7


def test_launch_provenance_names_the_imported_tree():
    import rl

    prov = _mod()._launch_provenance()
    assert prov["rl_package"] == str(Path(rl.__file__).resolve().parent)
    assert prov["launch_git_sha"] is None or len(prov["launch_git_sha"]) == 40
    assert prov["launch_git_sha"] is None or isinstance(prov["launch_git_dirty"], bool)

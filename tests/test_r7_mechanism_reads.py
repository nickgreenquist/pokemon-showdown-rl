"""The fleet pre-reg's mechanism-read instrument (`scripts/r7_mechanism_reads.py`, reads (iii) and (vi)) against its
provenance: on the R5 W committee under G0's own encoder flags (c6 off), the scorer's greedy IS G0's banked
a_greedy, its regret IS G0's banked regret_depth1_ceiling (rollout_q.py's regret_split on the same halves) and its
Spearman IS the evaluator's spearman_base (the same S 4 leaves and seeds), on every scored position; the positions
are the first N of each G0 bucket. Engine env only (pkmn_gen1); skipped where the banked data are absent."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
ROWS = MAIN / "results/r7_g0/rollout_q.rows.jsonl"
EVAL_ROWS = MAIN / "results/r7_g0/evaluator_k5.rows.jsonl"
W = [MAIN / "runs/showdown_monster200m_w_s104/ckpt_200000000.pt", MAIN / "runs/showdown_monster200m_w_s112/ckpt_200000012.pt",
     MAIN / "runs/showdown_monster200m_w_s120/ckpt_200000003.pt"]
SHA = ["a502af3af5b8d46219a774c46fff7754ff688dc745379103b244af1bdefd982e",
       "add6e89a3fe7ba2a96df5b07d7a932fc3a2de22ac0a644bbb75fdf12911aaf6f",
       "33108eadc38c0c1bca7ed322dc517972f1178b00a46d7ee2b3cf08adf1ba56f7"]


@pytest.mark.skipif(not (ROWS.exists() and EVAL_ROWS.exists() and all(p.exists() for p in W)),
                    reason="G0's banked rows / the R5 W finals are not on this box")
def test_the_scorer_reproduces_g0_and_the_evaluator_on_the_r5_committee(tmp_path):
    pytest.importorskip("pkmn_gen1")
    out = tmp_path / "repro.json"
    env = {k: v for k, v in os.environ.items() if k != "POKEMON_RL_ENCODER_C6"}
    env.update(POKEMON_RL_ENCODER_V2="1", POKEMON_RL_ENCODER_IDS="1")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/r7_mechanism_reads.py"), "--rows", str(ROWS),
                        "--checkpoints", *map(str, W), "--sha256", *SHA, "--committee", "--per-bucket", "2",
                        "--expect-reproduce", str(EVAL_ROWS), "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT, env=env, timeout=1200)
    assert r.returncode == 0, r.stdout + r.stderr
    s = json.loads(out.read_text())
    assert s["reproduce"]["checked"] == 8 and s["reproduce"]["n_failures"] == 0, s["reproduce"]
    assert s["rows_c6"] == ["False"] and s["encoder"]["POKEMON_RL_ENCODER_C6"] is None
    per = [json.loads(l) for l in out.with_suffix(".rows.jsonl").read_text().splitlines()]
    assert sorted(p["bucket"] for p in per) == [0, 0, 1, 1, 2, 2, 3, 3]
    assert all(p["pi1_max_abs_diff_vs_banked"] < 1e-5 for p in per)
    assert s["units"][0]["agree_banked_greedy"] == 1.0

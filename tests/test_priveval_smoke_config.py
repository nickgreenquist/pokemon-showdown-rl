"""`configs/engine_a1_priveval_smoke.yaml` — the design-B seam smoke.

A SMOKE, not a pre-registration (the `engine_smoke.yaml` / `gen4_smoke_heur.yaml`
precedent), so this file checks SHAPE and SAFETY and never a band or a read.
The one thing worth pinning hard is the DIFF: the file's whole value is that it
is engine_a1 plus two agent keys, so a reader can hold every other difference
between a smoke lane and the A-1 control at exactly zero. Milliseconds: no
engine, no server, no agent.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from rl.common.config import load_config
from rl.envs.make import selfplay_env_kwargs
from rl.train import ENGINE_KEYS, _async_collector_mode

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "configs/engine_a1_priveval_smoke.yaml"
BASE = ROOT / "configs/engine_a1.yaml"
TXT = PATH.read_text()
RAW = yaml.safe_load(TXT)
BASE_RAW = yaml.safe_load(BASE.read_text())


def _flat(d: dict, prefix: str = "") -> dict:
    out: dict = {}
    for k, v in d.items():
        key = prefix + k
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def test_it_is_engine_a1_plus_exactly_two_agent_keys():
    base, new = _flat(BASE_RAW), _flat(RAW)
    assert set(new) - set(base) == {"agent.priv_eval_dim", "agent.priv_eval_coef"}
    assert not set(base) - set(new), sorted(set(base) - set(new))
    changed = {k for k in set(base) & set(new) if base[k] != new[k]}
    # Lane identity only. total_steps, lr_anneal_steps, every collector key and
    # every other agent hyperparameter are the control's, UNCHANGED — which is
    # what makes the first updates readable against A-1's own curves.
    assert changed == {"run_name", "env_kwargs.seat_tag"}, sorted(changed)
    assert new["agent.priv_eval_dim"] == 408
    assert new["agent.priv_eval_coef"] > 0
    assert new["agent.lr_anneal_steps"] == new["total_steps"]


def test_design_a_is_absent_so_the_critic_stays_the_control_s_critic():
    """THE ONE THING THIS FILE MUST NOT CONTAIN. `privileged_dim` widens
    `self.critic`, which puts the block into the ADVANTAGE channel — the exact
    channel D18's falsifier fired on. A design-B lane is a leaf evaluator and
    nothing else, so the key must be absent, not zero, not commented in."""
    assert "privileged_dim" not in RAW["agent"], sorted(RAW["agent"])


def test_the_lane_is_identifiable_and_does_not_reuse_a1s_seat():
    assert RAW["env_kwargs"]["seat_tag"] == "pe" != BASE_RAW["env_kwargs"]["seat_tag"]
    assert "a1" not in RAW["run_name"] and "pe" in RAW["run_name"]


def test_the_loader_accepts_it_and_the_launch_order_is_satisfiable():
    cfg = load_config(PATH)
    assert not cfg.collector.keys() - ENGINE_KEYS, sorted(cfg.collector)
    # `train()` runs selfplay_env_kwargs BEFORE the collector check; an engine
    # config that only passes the second is unlaunchable (the bug that shipped).
    selfplay_env_kwargs(cfg, "opponent")


_GATE_CHILD = r"""
import sys
from rl.common.config import load_config
from rl.envs.showdown import PRIV_DIM
from rl.train import _async_collector_mode
assert PRIV_DIM == 408, PRIV_DIM
cfg = load_config(sys.argv[1])
assert _async_collector_mode(cfg, vectorized=True) == "engine"
print("OK")
"""


def test_the_engine_gate_passes_under_the_encoder_flags():
    """IN A SUBPROCESS, and that is not incidental: the launch gate compares
    `agent.privileged_dim` against `rl.envs.showdown.PRIV_DIM`, which is read
    from the environment at import. Under the documented `pytest tests/` the
    flags are unset and the constant is 300, so this could never hold in
    process (the `test_seat_tag.py` width-gate pattern, for the same reason)."""
    import os
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-c", _GATE_CHILD, str(PATH)],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=600, cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "OK"


def test_the_header_says_smoke_and_carries_its_gates():
    head = TXT.split("env_id:")[0]
    assert "SMOKE, NOT A PRE-REGISTRATION" in head.upper()
    assert "journey_step: 7.5" in head
    for gate in ("S-1", "S-2", "S-3", "S-4", "S-5", "S-6"):
        assert gate in head, gate
    # The two things a reader must not have to derive: that this is design B
    # ALONE (privileged_dim would have widened the critic and put the block in
    # the advantage channel), and that the block's engine-route cost has never
    # been measured.
    assert "UNMEASURED" in head
    assert "DESIGN B ALONE" in head
    # And the runtime, at the width and rates it was measured at.
    assert "2,390 steps/s" in head and "1,502 steps/s" in head
    assert "k=8, width 1" in head


@pytest.mark.parametrize("key", ["privileged", "priv_eval_coef", "priv_eval_dim"])
def test_no_collector_key_was_invented(key):
    """`collector.privileged` has already broken one engine config
    (tests/test_engine_a1_prereg.py:59-67). The emit flag is DERIVED from the
    agent's own need (`PPOAgent.privileged_block_dim`); there is no
    collector-side knob and there must not be one here either."""
    assert key not in RAW["collector"], sorted(RAW["collector"])

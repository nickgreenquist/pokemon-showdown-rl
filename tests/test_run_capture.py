"""Run-dir capture: every training run must leave a self-describing artifact
trail — resolved config, provenance, checkpoints — because benchmark
campaigns are analyzed from disk days later, across many runs.
"""

import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from rl.common.config import Config, load_config
from rl.common.evaluation import eval_returns
from rl.envs.make import make_env
from rl.train import make_agent, train

REPO_ROOT = Path(__file__).resolve().parents[1]


def tiny_cfg() -> Config:
    return Config(
        env_id="CartPole-v1",
        seed=0,
        total_steps=300,
        eval_every=150,
        eval_episodes=2,
        run_name="test_capture",
        logger="tensorboard",
        agent={
            "algo": "dqn",
            "hidden_sizes": [],
            "lr": 1.0e-3,
            "gamma": 0.99,
            "buffer_capacity": 1000,
            "batch_size": 32,
            "learning_starts": 100,
            "target_update_every": 100,
            "epsilon_start": 1.0,
            "epsilon_end": 0.05,
            "epsilon_decay_steps": 200,
        },
    )


@pytest.fixture(scope="module")
def trained_run(tmp_path_factory):
    """One tiny training run shared by the capture assertions."""
    workdir = tmp_path_factory.mktemp("capture")
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        cfg = tiny_cfg()
        train(cfg)
    finally:
        os.chdir(cwd)
    return workdir / "runs" / "test_capture", cfg


def test_run_dir_is_self_describing(trained_run):
    run_dir, cfg = trained_run
    # The config snapshot round-trips through the normal loader, so any run
    # can be reproduced from its run dir alone.
    assert asdict(load_config(run_dir / "config.yaml")) == asdict(cfg)
    meta = yaml.safe_load((run_dir / "meta.yaml").read_text())
    assert {"started_at", "git_sha", "git_dirty", "versions"} <= meta.keys()
    assert "torch" in meta["versions"]
    assert (run_dir / "checkpoint.pt").exists()
    assert (run_dir / "best_checkpoint.pt").exists()
    # Atomic checkpoint writes leave no temp residue.
    assert not list(run_dir.rglob("*.tmp"))


class _NeverEndingEnv:
    """Minimal env whose episodes never end — MinAtar has no time limit,
    and an immortal policy under greedy eval would hang the protocol."""

    def reset(self, seed=None):
        return 0, {}

    def step(self, action):
        return 0, 1.0, False, False, {}


class _StubAgent:
    def act(self, obs, action_mask=None, deterministic=False):
        return 0


def test_eval_episode_step_cap():
    returns = eval_returns(_StubAgent(), _NeverEndingEnv(), episodes=2, max_steps=50)
    assert returns == [50.0, 50.0]


def test_eval_protocol_is_reproducible():
    # Fixed eval seeds + a deterministic policy: two passes must agree
    # exactly, or cross-run comparisons are meaningless.
    cfg = tiny_cfg()
    env = make_env(cfg.env_id, cfg.seed)
    agent = make_agent(cfg, env)
    assert eval_returns(agent, env, 3) == eval_returns(agent, env, 3)
    env.close()


def test_eval_checkpoint_script(trained_run):
    run_dir, _ = trained_run
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "eval_checkpoint.py"),
            str(run_dir / "best_checkpoint.pt"),
            "--episodes",
            "3",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(proc.stdout)
    assert report["episodes"] == 3
    assert len(report["returns"]) == 3
    assert report["env_id"] == "CartPole-v1"

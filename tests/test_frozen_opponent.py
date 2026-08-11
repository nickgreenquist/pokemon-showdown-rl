"""Frozen-checkpoint opponent (`selfplay.opponent: <path>.pt` — the
best-response/exploiter seam, D22 read 5).

The dispatch guard runs in-process on Connect4 (no poke_env import). The
loader round-trip needs the 828 encoder, whose flags are read at import, so
it runs in a subprocess with both env vars set (test_entity_deepsets's
pattern): a saved entity-trunk checkpoint resolves into a ONE-member pool
whose member is frozen and plays in-mask.
"""

import os
import subprocess
import sys

import pytest

from rl.common.config import Config
from rl.train import train


def test_checkpoint_path_opponent_is_showdown_only(tmp_path):
    cfg = Config(
        env_id="Connect4-v0",
        seed=0,
        total_steps=64,
        eval_every=64,
        eval_episodes=2,
        run_name="test_frozen_c4",
        logger="tensorboard",
        num_envs=4,
        selfplay={"opponent": "nope.pt", "eval_opponent": "heuristic"},
        eval_win_rate=True,
        agent={
            "algo": "ppo", "hidden_sizes": [16], "lr": 2.5e-4, "gamma": 1.0,
            "gae_lambda": 0.95, "rollout_steps": 16, "epochs": 1,
            "minibatches": 2, "clip_eps": 0.2, "entropy_coef": 0.01,
            "value_coef": 0.5, "max_grad_norm": 0.5,
        },
    )
    with pytest.raises(ValueError, match="Showdown-only"):
        train(cfg)


_CHILD = r"""
import numpy as np
import torch
from types import SimpleNamespace

import gymnasium as gym

from rl.common.checkpoint import save_checkpoint
from rl.common.config import Config
from rl.train import _frozen_checkpoint_pool, make_agent

cfg = Config(
    env_id="Showdown-v0",
    seed=0,
    total_steps=1024,
    eval_every=1024,
    eval_episodes=1,
    run_name="test_frozen_sd",
    logger="tensorboard",
    num_envs=2,
    selfplay={"opponent": "self", "eval_opponent": "heuristics",
              "pool_size": 1, "latest_prob": 1.0, "push_every_updates": 1},
    eval_win_rate=True,
    agent={
        "algo": "ppo", "trunk": "entity_deepsets",
        "trunk_kwargs": {"species_vocab": 152, "move_vocab": 166,
                          "embed_dim": 8, "entity_dim": 16, "pool": "max",
                          "ctx_sizes": [32], "scorer_sizes": [16],
                          "value_sizes": [32]},
        "hidden_sizes": [16], "lr": 2.5e-4, "gamma": 1.0, "gae_lambda": 0.95,
        "rollout_steps": 16, "epochs": 1, "minibatches": 2, "clip_eps": 0.2,
        "entropy_coef": 0.01, "value_coef": 0.5, "max_grad_norm": 0.5,
    },
)
spaces = SimpleNamespace(
    observation_space=gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
    action_space=gym.spaces.Discrete(10),
)
agent = make_agent(cfg, spaces)
save_checkpoint("ckpt.pt", agent, step=1024, cfg=cfg)

pool = _frozen_checkpoint_pool("ckpt.pt")
assert len(pool) == 1, len(pool)

member = pool.select(np.random.default_rng(0))
# Frozen: eval mode, no grads (the push-freezes contract, via this seam).
assert not any(p.requires_grad for p in member.agent.actor.parameters())
# Plays in-mask on a batchless 828 obs.
rng = np.random.default_rng(1)
obs = rng.random(828, dtype=np.float32)
mask = np.zeros(10, dtype=bool)
mask[[1, 7]] = True
for _ in range(8):
    action = member.move(obs, mask, rng)
    assert mask[action], action
print("OK")
"""


def test_frozen_checkpoint_pool_round_trip(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout

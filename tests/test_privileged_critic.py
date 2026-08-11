"""D18 privileged critic: buffer storage, PPO wiring, and the entity value
variant.

The PPO/buffer contract runs in-process on a tiny MLP agent (the mlp
privileged path is plain input concat, no encoder constants). The entity
variant needs the 828 tokenizer, so its gates run in a subprocess with both
env vars set (test_entity_deepsets's pattern): construction validation, the
value-depends-on-priv property, and actor untouched by construction.
"""

import math
import os
import subprocess
import sys

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

PRIV = 5


def _agent(privileged_dim=PRIV, rollout_steps=4, num_envs=2, **overrides):
    torch.manual_seed(0)
    return PPOAgent(
        **overrides,
        privileged_dim=privileged_dim,
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=num_envs,
        device="cpu",
        lr=1.0e-3,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=rollout_steps,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
    )


def _row(t, num_envs=2, privileged=True, terminated=False):
    obs = np.full((num_envs, 3), 0.1 * t, dtype=np.float32)
    next_obs = np.full((num_envs, 3), 0.1 * (t + 1), dtype=np.float32)
    actions = np.arange(num_envs) % 2
    rewards = np.ones(num_envs, dtype=np.float32)
    term = np.full(num_envs, terminated)
    trunc = np.zeros(num_envs, dtype=bool)
    masks = np.ones((num_envs, 2), dtype=bool)
    base = (obs, actions, rewards, next_obs, term, trunc, masks, masks)
    if not privileged:
        return base
    privs = np.full((num_envs, PRIV), 0.01 * t, dtype=np.float32)
    next_privs = np.full((num_envs, PRIV), 0.01 * (t + 1), dtype=np.float32)
    return (*base, privs, next_privs)


def test_privileged_mlp_agent_trains_on_10_tuples():
    agent = _agent()
    # The mlp critic's first layer is widened by exactly privileged_dim.
    assert agent.critic[0].weight.shape[1] == 3 + PRIV
    for t in range(3):
        assert agent.update(_row(t)) == {}
    metrics = agent.update(_row(3, terminated=True))
    assert "loss/value" in metrics
    # Per-row priv storage reached the buffer (cleared after the drain).
    assert agent.buffer.privs is not None and agent.buffer.privs.shape == (4, 2, PRIV)


def test_mismatch_is_loud_both_ways():
    with pytest.raises(ValueError, match="privileged mismatch"):
        _agent().update(_row(0, privileged=False))
    with pytest.raises(ValueError, match="privileged mismatch"):
        _agent(privileged_dim=0).update(_row(0, privileged=True))


def test_unprivileged_agent_still_takes_8_tuples():
    agent = _agent(privileged_dim=0)
    assert agent.buffer.privs is None
    assert agent.update(_row(0, privileged=False)) == {}


def test_actor_is_never_widened():
    agent = _agent()
    # The actor's input layer reads the raw obs width — the privileged block
    # must never reach it (Baisero & Amato: h stays the actor's own view).
    assert agent.actor[0].weight.shape[1] == 3


_ENTITY_CHILD = r"""
import numpy as np
import torch

from rl.envs.showdown import OBS_DIM, PRIV_DIM
from rl.networks.entity_deepsets import EntityDeepSetsNet

assert OBS_DIM == 828 and PRIV_DIM == 408

KW = dict(species_vocab=152, move_vocab=166, embed_dim=8, entity_dim=16,
          pool="max", ctx_sizes=[32], scorer_sizes=[16], value_sizes=[32])

# Policy head refuses the privilege — the actor never widens.
try:
    EntityDeepSetsNet(828, 10, privileged_dim=PRIV_DIM, **KW)
    raise SystemExit("policy head accepted privileged_dim")
except ValueError as e:
    assert "critic-only" in str(e), e

# A wrong layout dies loudly (the env/critic disagreement seam).
try:
    EntityDeepSetsNet(828, 1, privileged_dim=PRIV_DIM - 1, **KW)
    raise SystemExit("wrong privileged_dim accepted")
except ValueError as e:
    assert "PRIV_DIM" in str(e), e

torch.manual_seed(0)
net = EntityDeepSetsNet(828, 1, privileged_dim=PRIV_DIM, **KW)
net.init_head(1.0)
net.eval()
# ctx first layer widened to 8 slots of entity_dim.
assert net.ctx_net[0].weight.shape[1] == 8 * 16

g = torch.Generator().manual_seed(1)
obs = torch.rand(4, 828, generator=g)
priv_a = torch.rand(4, PRIV_DIM, generator=g)
priv_b = torch.rand(4, PRIV_DIM, generator=g)
with torch.no_grad():
    va = net(torch.cat([obs, priv_a], -1))
    vb = net(torch.cat([obs, priv_b], -1))
assert va.shape == (4, 1)
# The value genuinely reads the privileged block.
assert not torch.allclose(va, vb)
print("OK")
"""


def test_entity_privileged_value_variant():
    result = subprocess.run(
        [sys.executable, "-c", _ENTITY_CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout

"""`ctx_layernorm` (2026-09-12): Linear -> LayerNorm -> ReLU in the context
stack of `EntityDeepSetsNet`, gated by a trunk kwarg.

Two contracts, both tested in a SUBPROCESS with the encoder flags set (the
tokenizer's layout is read at import, exactly as tests/test_entity_deepsets.py
does it):

1. THE DEFAULT IS AN EXACT NO-OP. With the kwarg absent or False the actor is
   still 626,059 params and the critic 494,849, the state_dict keys are
   byte-identical to a net built without the kwarg, and ctx_net holds no
   LayerNorm -- so every existing checkpoint loads unchanged and the
   ACTOR_PARAM_CEILING assert still sees the pinned count.
2. ON, IT IS EXACTLY ONE LayerNorm PER CONTEXT LAYER: +2*width params each
   (gamma + beta), the actor stays under the ceiling, the forward runs, and
   the flag rides through PPOAgent's trunk_kwargs into BOTH nets -- which is
   how a checkpoint's own config rebuilds it at eval.
"""
import os
import subprocess
import sys

_CHILD = r"""
import gymnasium as gym
import numpy as np
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import OBS_DIM
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING, EntityDeepSetsNet

assert OBS_DIM == 828, OBS_DIM
torch.set_num_threads(1)
KW = dict(species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
          pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384])

# 1. default is a no-op
a0 = EntityDeepSetsNet(828, 10, **KW)
c0 = EntityDeepSetsNet(828, 1, **KW)
a_off = EntityDeepSetsNet(828, 10, ctx_layernorm=False, **KW)
assert a0.param_count == a_off.param_count == 626_059, (a0.param_count, a_off.param_count)
assert c0.param_count == 494_849, c0.param_count
assert list(a0.state_dict()) == list(a_off.state_dict())
assert not any(isinstance(m, torch.nn.LayerNorm) for m in a0.ctx_net)
assert not any(isinstance(m, torch.nn.LayerNorm) for m in c0.ctx_net)
assert a0.ctx_layernorm is False

# 2. on: one LayerNorm per context layer, +2*width params each
a1 = EntityDeepSetsNet(828, 10, ctx_layernorm=True, **KW)
c1 = EntityDeepSetsNet(828, 1, ctx_layernorm=True, **KW)
assert a1.ctx_layernorm is True
assert a1.param_count == 626_059 + 2 * (384 + 384), a1.param_count
assert c1.param_count == 494_849 + 2 * (384 + 384), c1.param_count
assert sum(isinstance(m, torch.nn.LayerNorm) for m in a1.ctx_net) == 2
assert sum(isinstance(m, torch.nn.LayerNorm) for m in c1.ctx_net) == 2
# ordering: Linear, LayerNorm, ReLU per layer
kinds = [type(m).__name__ for m in a1.ctx_net]
assert kinds == ["Linear", "LayerNorm", "ReLU", "Linear", "LayerNorm", "ReLU"], kinds
assert a1.param_count <= ACTOR_PARAM_CEILING
# LayerNorms keep their ones/zeros default through init_head
a1.init_head(0.01)
for m in a1.ctx_net:
    if isinstance(m, torch.nn.LayerNorm):
        assert torch.all(m.weight == 1) and torch.all(m.bias == 0)
x = torch.rand(4, 828)
with torch.no_grad():
    out = a1(x)
    v = c1(x)
assert out.shape == (4, 10), out.shape
assert v.shape[0] == 4, v.shape
assert torch.isfinite(out).all() and torch.isfinite(v).all()

# 3. the flag rides through PPOAgent's trunk_kwargs into both nets
agent = PPOAgent(
    gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
    num_envs=1, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=64, epochs=1, minibatches=1, clip_eps=0.2, entropy_coef=0.01,
    value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[512, 512],
    trunk="entity_deepsets", trunk_kwargs={**KW, "ctx_layernorm": True},
)
sd = agent.state_dict()          # nested: {"actor": {...}, "critic": {...}, "optimizer", "updates"}
for net in ("actor", "critic"):
    keys = set(sd[net])
    assert {"ctx_net.1.weight", "ctx_net.1.bias", "ctx_net.4.weight", "ctx_net.4.bias"} <= keys, (net, sorted(k for k in keys if "ctx_net" in k))
assert sum(isinstance(m, torch.nn.LayerNorm) for m in agent.actor.ctx_net) == 2
assert sum(isinstance(m, torch.nn.LayerNorm) for m in agent.critic.ctx_net) == 2
print("OK")
"""


def test_ctx_layernorm_default_noop_and_gated_on():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"

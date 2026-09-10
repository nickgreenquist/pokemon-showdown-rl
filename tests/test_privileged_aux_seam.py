"""The D25 x D18 constructor guard, LIFTED 2026-09-10, and the property it was
asserting by refusal.

`rl/agents/ppo.py` used to raise `TypeError` for `aux_oppact_coef > 0` together
with `privileged_dim > 0`, citing R0-1's fingerprint. R0-1
(`configs/showdown_sp_actpred12m.yaml:1138-1143`) is an ARM-SCOPED LAUNCH CHECK
for the D25 12M rung — "D18's plumbing must not ride along; D25 needs neither" —
and those lanes are banked. Nothing structural was being protected: the aux head
reads the ACTOR's features and takes gradients over actor+aux params only, while
the privileged block reaches the CRITIC's input and nothing else. Actor and
critic share no trunk.

Two tests, and the second is as important as the first:

1. the aux head's INPUTS and OUTPUT are bit-identical across `privileged_dim`,
   which is the claim the refusal encoded;
2. `privileged_dim` DOES move the actor's INITIAL weights at a fixed seed — the
   residue that is disclosed rather than fixed. A test that asserts a known
   asymmetry is how it stops being a surprise.

Subprocess with both encoder env vars, the `test_privileged_critic.py` pattern:
the 828 tokenizer's layout asserts read them at import.
"""

import os
import subprocess
import sys

_PREAMBLE = r"""
import gymnasium as gym
import numpy as np
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import OBS_DIM, PRIV_DIM

assert OBS_DIM == 828 and PRIV_DIM == 408, (OBS_DIM, PRIV_DIM)

TK = dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
          pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64])
KW = dict(num_envs=2, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
          rollout_steps=8, epochs=1, minibatches=2, clip_eps=0.2,
          entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
          hidden_sizes=[64, 64], trunk="entity_deepsets", trunk_kwargs=TK)


def build(priv, **kw):
    torch.manual_seed(0)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
        privileged_dim=priv, **KW, **kw,
    )


def rows(n=5, seed=7):
    g = torch.Generator().manual_seed(seed)
    obs = torch.rand(n, 828, generator=g) * 2 - 0.5
    # The id suffix must look like ids or the tokenizer's round(x*256) is noise.
    obs[:, 808:] = torch.randint(0, 150, (n, 20), generator=g).float() / 256.0
    return obs
"""


_INPUTS_CHILD = _PREAMBLE + r"""
# Constructing either of these AT ALL is half the test: before the lift the
# second line raised TypeError.
a0 = build(0, aux_oppact_coef=0.1)
a1 = build(PRIV_DIM, aux_oppact_coef=0.1)

# The head is actor-side, so the actor and the head must carry the SAME weights
# for the comparison to be about the lever rather than about init noise (which
# privileged_dim genuinely moves — see the residue test).
a1.actor.load_state_dict(a0.actor.state_dict())
a1.aux_head.load_state_dict(a0.aux_head.state_dict())

obs = rows()
with torch.no_grad():
    f0 = a0.actor(obs, return_features=True)
    f1 = a1.actor(obs, return_features=True)
assert len(f0) == len(f1) == 4, (len(f0), len(f1))   # logits, ctx, opp_moves, opp_bench
for i, (t0, t1) in enumerate(zip(f0, f1)):
    assert t0.shape == t1.shape, (i, t0.shape, t1.shape)
    assert torch.equal(t0, t1), i

with torch.no_grad():
    h0 = a0.aux_head(*f0[1:])
    h1 = a1.aux_head(*f1[1:])
assert torch.equal(h0, h1)

# And the gradient the head can reach is the actor's only: `_aux_gradient` takes
# grads over (actor_params, aux_params). The critic is not in that list on
# EITHER build, which is what makes the privileged block unreachable from here.
crit = {id(p) for p in a1.critic.parameters()}
assert not (crit & {id(p) for p in a1.actor_params}), "actor and critic share params"
assert not (crit & {id(p) for p in a1.aux_params}), "the aux head reaches the critic"
# The actor never widens; only the critic does.
assert a0.actor.param_count == a1.actor.param_count
assert a1.critic.param_count > a0.critic.param_count
assert a1.critic.ctx_net[0].weight.shape[1] == 8 * 32   # 5 + 3 slots
assert a0.critic.ctx_net[0].weight.shape[1] == 5 * 32
print("OK")
"""


_RESIDUE_CHILD = _PREAMBLE + r"""
# THE DISCLOSED RESIDUE (proposal §2.2 / R1). `init_head` is the entity net's
# WHOLE init, and it runs after the widened critic has already moved the global
# RNG stream — so turning privileged_dim on re-rolls the ACTOR at a fixed seed.
# Count identical, values different. Do NOT "fix" this by reordering
# construction: that moves the stream for privileged_dim=0 too and breaks
# _GEN1_PIN for every existing recipe.
a0 = build(0, aux_oppact_coef=0.1)
a1 = build(PRIV_DIM, aux_oppact_coef=0.1)

n0 = sum(p.numel() for p in a0.actor.parameters())
n1 = sum(p.numel() for p in a1.actor.parameters())
assert n0 == n1, (n0, n1)

s0 = torch.cat([p.detach().flatten() for p in a0.actor.parameters()]).double().sum().item()
s1 = torch.cat([p.detach().flatten() for p in a1.actor.parameters()]).double().sum().item()
assert s0 != s1, (s0, s1)
# Not a rounding wobble: the two inits are unrelated draws.
assert abs(s0 - s1) > 1e-3, (s0, s1)
print("OK", n0, s0, s1)
"""


def _run(child: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", child],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_aux_head_inputs_are_unchanged_by_privileged_dim():
    assert _run(_INPUTS_CHILD).strip().splitlines()[-1] == "OK"


def test_privileged_dim_moves_the_actor_init_and_this_is_disclosed():
    assert _run(_RESIDUE_CHILD).strip().splitlines()[-1].startswith("OK")


def test_the_lifted_guard_records_why_it_went():
    """A deleted refusal that leaves no note reads as an oversight to the next
    person. The comment in its place has to name R0-1's arm scope AND the
    residue above, or this file is the only record."""
    import inspect

    from rl.agents import ppo

    src = inspect.getsource(ppo.PPOAgent.__init__)
    assert "R0-1" in src and "arm" in src.lower(), "the lift does not record R0-1's scope"
    assert "DISJOINT" in src or "disjoint" in src, "the lift does not state the property"
    assert "334.851" in src and "410.510" in src, "the lift does not name the residue"

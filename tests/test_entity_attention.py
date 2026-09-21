"""Offline gates for the attention trunk — R7's architecture screen
(rl/networks/entity_attention.py, configs/bc_arch_screen.yaml).

Everything that touches the trunk needs the 828-dim encoder, whose flags are
read at MODULE IMPORT, so those gates run in a SUBPROCESS with both env vars
set (tests/test_ctx_layernorm.py's pattern, itself test_encoder_v2's). Do NOT
export the flags into a bare run of the whole suite: six
tests/test_showdown_env.py tests build v1 fakes and fail under them.

What is pinned here, and why each one:

1. PARAM COUNT, exact. The screen's whole claim to be about STRUCTURE rests on
   the attention actor being SMALLER than both comparators (the DeepSets
   actor's 626,059 and the flat MLP's ACTOR_PARAM_CEILING 681,994). A silent
   drift in d_model, ff width or the scorer would turn a credit into bought
   capacity, and nothing downstream would notice.
2. SHAPES at 828, policy and value.
3. POINTER ALIGNMENT, structurally. Perturbing own-mon token i's own input
   slice must move logit i more than any other logit. This is the one
   contract the encoder, the action space and poke-env's `action_to_order`
   all silently depend on; get it wrong and the clone names a different
   Pokemon under the conversion deployment uses, which no aggregate number
   reveals (tape_to_dataset's G2 makes the same argument about labels).
   A companion check proves the tokens actually MIX — an alignment test alone
   would pass on a net whose attention did nothing.
4. INIT. Embeddings at std ~0.02, only the final scorer/head rescaled by the
   gain, and — the attention-specific hazard — `in_proj_weight` re-initialised
   rather than skipped. `_orthogonal_init` must never run over this net: it
   reaches `out_proj` (an nn.Linear subclass) and misses `in_proj_weight` (a
   bare Parameter), i.e. it would re-init exactly half of every block.
5. ROUND TRIP through Config(agent={trunk: attention}) -> make_agent ->
   state_dict, because that is how eval_checkpoint.py rebuilds a checkpoint.
6. THE DEFAULT MLP PATH IS UNTOUCHED, in PPOAgent and in train_bc — the seam's
   price of admission. train_bc is exercised END TO END on a synthetic
   dataset for both trunks, so "the mlp fit serialises the agent dict it
   always did" is measured rather than asserted from reading the diff.
"""

import os
import subprocess
import sys

_ENV = {**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"}

# Pinned 2026-09-20 from a live construction at OBS_DIM 828, d_model 128 /
# 2 layers / 4 heads / embed_dim 64 / ff x4 / scorer [256] / value [384,384].
_ACTOR_PARAMS = 564_875
_CRITIC_PARAMS = 794_881
_DEEPSETS_ACTOR_PARAMS = 626_059

_CHILD = r"""
import numpy as np
import torch
from torch import nn

from rl.envs.showdown import OBS_DIM
from rl.networks.entity_attention import (
    N_TOKENS, OWN_MON_TOKENS, OWN_MOVE_TOKENS, EntityAttentionNet, _token_ids,
)
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING, EntityDeepSetsNet

assert OBS_DIM == 828, OBS_DIM
torch.set_num_threads(1)
KW = dict(species_vocab=152, move_vocab=166, embed_dim=64,
          d_model=128, n_layers=2, n_heads=4)

# ---- 1. param count, exact, and BELOW both comparators -------------------
torch.manual_seed(0)
actor = EntityAttentionNet(OBS_DIM, 10, **KW)
critic = EntityAttentionNet(OBS_DIM, 1, **KW)
assert actor.param_count == sum(p.numel() for p in actor.parameters()) == ACTOR_PARAMS, \
    actor.param_count
assert critic.param_count == CRITIC_PARAMS, critic.param_count
assert actor.param_count <= ACTOR_PARAM_CEILING
ds = EntityDeepSetsNet(OBS_DIM, 10, species_vocab=152, move_vocab=166, embed_dim=64,
                       entity_dim=128, pool="max", ctx_sizes=[384, 384],
                       scorer_sizes=[256], value_sizes=[384, 384])
assert ds.param_count == DEEPSETS_ACTOR_PARAMS, ds.param_count
assert actor.param_count < ds.param_count, (actor.param_count, ds.param_count)
assert actor.is_policy and not critic.is_policy

# ---- 2. shapes -----------------------------------------------------------
x = torch.rand(5, OBS_DIM)
assert actor(x).shape == (5, 10)
assert critic(x).shape == (5, 1)
assert actor._tokens(x).shape == (5, N_TOKENS, 128)
# The token ids cover all 21 tokens and the own-side slices are where the
# pointer head thinks they are.
types, sides, slots = _token_ids()
assert len(types) == N_TOKENS
assert OWN_MON_TOKENS == slice(1, 7) and OWN_MOVE_TOKENS == slice(13, 17)
assert sides[1:7] == [1] * 6 and sides[13:17] == [1] * 4

# ---- 3. pointer alignment, and that the tokens actually mix ---------------
actor.init_head(0.01)
tk = actor.tokenizer
base = torch.zeros(1, OBS_DIM)
with torch.no_grad():
    l0 = actor(base)
for i in range(6):
    lo = tk.own_mon_off + i * tk.mon_dim
    bumped = base.clone()
    bumped[0, lo:lo + tk.mon_dim] = 1.0
    with torch.no_grad():
        d = (actor(bumped) - l0).abs()[0]
    others = torch.cat([d[:i], d[i + 1:]])
    assert float(d[i]) > float(others.max()), (i, d.tolist())
for j in range(4):
    lo = tk.own_move_off + j * tk.move_dim
    bumped = base.clone()
    bumped[0, lo:lo + tk.move_dim] = 1.0
    with torch.no_grad():
        d = (actor(bumped) - l0).abs()[0]
    k = 6 + j
    others = torch.cat([d[:k], d[k + 1:]])
    assert float(d[k]) > float(others.max()), (j, d.tolist())

# The mixing check: a perturbation to own-mon 0 must change OTHER tokens'
# outputs too, or the "attention" arm is a per-token MLP with extra steps.
def _seq(z):
    s = actor._tokens(z)
    for b in actor.blocks:
        s = b(s)
    return actor.norm_out(s)

bumped = base.clone()
bumped[0, tk.own_mon_off:tk.own_mon_off + tk.mon_dim] = 1.0
with torch.no_grad():
    moved = (_seq(bumped) - _seq(base)).abs().amax(dim=-1)[0]
assert float(moved[1]) > 0.5, float(moved[1])          # the perturbed token
assert float(moved[2:].min()) > 1e-3, moved.tolist()   # every other token

# ---- 4. init ------------------------------------------------------------
torch.manual_seed(0)
net = EntityAttentionNet(OBS_DIM, 10, **KW)
pre_qkv = [b.attn.in_proj_weight.detach().clone() for b in net.blocks]
net.init_head(0.01)
for name in ("species_emb", "move_emb", "type_emb", "side_emb", "slot_emb"):
    std = float(getattr(net, name).weight.detach().std())
    assert 0.015 < std < 0.026, (name, std)
# in_proj_weight was re-initialised (the hazard: a Linear-only walk skips it).
for before, b in zip(pre_qkv, net.blocks):
    assert not torch.equal(before, b.attn.in_proj_weight)
    assert float(b.attn.in_proj_bias.detach().abs().max()) == 0.0
    assert float(b.attn.out_proj.bias.detach().abs().max()) == 0.0
# ONLY the final scorer layer carries the gain: rebuild at the same seed with
# gain 1.0 and every weight but that one must match bit-for-bit.
torch.manual_seed(0)
one = EntityAttentionNet(OBS_DIM, 10, **KW)
one.init_head(1.0)
for (na, pa), (nb, pb) in zip(net.named_parameters(), one.named_parameters()):
    assert na == nb
    if na == "scorer.2.weight":
        assert torch.allclose(pa, pb * 0.01), na
    else:
        assert torch.equal(pa, pb), na
# and the value head's final layer is the one the value gain would hit
torch.manual_seed(0)
v = EntityAttentionNet(OBS_DIM, 1, **KW)
v.init_head(1.0)
assert isinstance(v.value_net[-1], nn.Linear) and v.value_net[-1].out_features == 1

# ---- 5. make_agent / Config / state_dict round trip ----------------------
from types import SimpleNamespace

import gymnasium as gym

from rl.agents.ppo import TRUNKS, PPOAgent
from rl.common.config import Config
from rl.train import make_agent

assert TRUNKS == ("mlp", "entity_deepsets", "attention")
AGENT = dict(algo="ppo", lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=128,
             epochs=4, minibatches=4, clip_eps=0.2, entropy_coef=0.01,
             value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[512, 512])
spaces = SimpleNamespace(
    observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
    action_space=gym.spaces.Discrete(10),
)

def _agent(trunk, kwargs):
    cfg = Config(env_id="Showdown-v0", seed=0, total_steps=0, eval_every=0,
                 eval_episodes=100, run_name="t", logger="tensorboard",
                 agent={**AGENT, "trunk": trunk, "trunk_kwargs": kwargs})
    return make_agent(cfg, spaces)

torch.manual_seed(0)
a = _agent("attention", KW)
assert type(a.actor).__name__ == "EntityAttentionNet"
assert type(a.critic).__name__ == "EntityAttentionNet"
assert a.actor.param_count == ACTOR_PARAMS and a.critic.param_count == CRITIC_PARAMS
# ppo.py's head gains reached the net: 0.01 actor / 1.0 critic. Compared as
# SCALES, not bit-for-bit against a standalone net -- make_agent builds the
# actor and then the critic off one RNG stream, so a fresh net at the same
# seed is a different draw. Xavier-uniform on Linear(256, 1) has std
# sqrt(6/257)/sqrt(3) = 0.0882; the actor's is that times 0.01.
assert 0.0006 < float(a.actor.scorer[-1].weight.detach().std()) < 0.0012
assert 0.04 < float(a.critic.value_net[-1].weight.detach().std()) < 0.11
assert float(a.actor(torch.rand(64, OBS_DIM)).detach().std()) < 0.05  # near-uniform
torch.manual_seed(0)
b = _agent("attention", KW)
b.actor.load_state_dict(a.actor.state_dict())
b.critic.load_state_dict(a.critic.state_dict())
z = torch.rand(3, OBS_DIM)
assert torch.equal(a.actor(z), b.actor(z))
assert torch.equal(a.critic(z), b.critic(z))

# The refusals: gen-4 layout, a privileged block, and the D25 aux seam.
for bad in ("gen4",):
    try:
        EntityAttentionNet(OBS_DIM, 10, layout=bad, **KW)
    except Exception as e:
        assert "gen-1 only" in str(e), e
    else:
        raise AssertionError("gen4 layout must be refused")
try:
    PPOAgent(spaces.observation_space, spaces.action_space, num_envs=2, device="cpu",
             **{k: v for k, v in AGENT.items() if k != "algo"},
             trunk="attention", trunk_kwargs=KW, privileged_dim=408)
except TypeError as e:
    assert "privileged_dim is not implemented" in str(e), e
else:
    raise AssertionError("privileged_dim must be refused for the attention trunk")
try:
    a.actor(z, return_features=True)
except ValueError as e:
    assert "aux" in str(e), e
else:
    raise AssertionError("return_features must be refused")

# ---- 6. the default MLP path is untouched --------------------------------
torch.manual_seed(0)
m = PPOAgent(spaces.observation_space, spaces.action_space, num_envs=2, device="cpu",
             **{k: v for k, v in AGENT.items() if k != "algo"})
assert m.trunk == "mlp"
assert isinstance(m.actor, nn.Sequential) and isinstance(m.critic, nn.Sequential)
# Tanh hiddens + orthogonal init, i.e. the historical construction, not ours.
assert any(isinstance(mod, nn.Tanh) for mod in m.actor.modules())
assert not hasattr(m.actor, "init_head")
print("CHILD OK")
"""

_TRAIN_BC_CHILD = r"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

# cwd is a tmp dir (train_bc writes runs/<name> relative to it), so the repo
# has to be put on the path explicitly.
sys.path.insert(0, REPO)
sys.path.insert(0, str(Path(REPO) / "scripts"))
import train_bc
from rl.envs.showdown import OBS_DIM

rng = np.random.default_rng(0)
N, B = 400, 40
masks = np.zeros((N, 10), dtype=bool)
for i in range(N):
    k = rng.integers(2, 6)
    masks[i, rng.choice(10, size=k, replace=False)] = True
actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks], dtype=np.int64)
policy = masks.astype(np.float32) * rng.random((N, 10)).astype(np.float32)
policy /= policy.sum(1, keepdims=True)
np.savez_compressed(
    Path(OUT) / "syn.npz",
    expert=np.str_("syn"), obs=rng.random((N, OBS_DIM)).astype(np.float32),
    masks=masks, actions=actions, policy=policy,
    battle_ids=np.repeat(np.arange(B), N // B).astype(np.int64),
    obs_dim=np.int64(OBS_DIM), gen=np.int64(1),
)

def run(name, extra):
    sys.argv = ["train_bc.py", "--data", str(Path(OUT) / "syn.npz"), "--target", "soft",
                "--epochs", "1", "--batch-size", "64", "--run-name", name] + extra
    train_bc.main()
    rep = json.loads(Path(f"runs/{name}/bc_metrics.json").read_text())
    ck = torch.load(f"runs/{name}/checkpoint.pt", weights_only=False)
    rows = np.load(f"runs/{name}/val_rows.npz")
    return rep, ck, rows

# DEFAULT = mlp, and its serialised agent dict has NO trunk keys at all.
rep, ck, rows = run("t_mlp", [])
assert rep["trunk"] == "mlp" and rep["trunk_kwargs"] == {}
agent_cfg = ck["config"]["agent"] if isinstance(ck.get("config"), dict) else ck["config"].agent
assert "trunk" not in agent_cfg and "trunk_kwargs" not in agent_cfg, agent_cfg
assert rep["actor_params"] == OBS_DIM * 512 + 512 + 512 * 512 + 512 + 512 * 10 + 10
assert rep["best_epoch"] == 1
assert set(rows) >= {"battle_ids", "agree", "free", "kl", "reveal", "epoch"}
assert len(rows["agree"]) == rep["val_decisions"] == len(rows["battle_ids"])

rep_e, ck_e, _ = run("t_ent", ["--trunk", "entity_deepsets"])
assert rep_e["trunk"] == "entity_deepsets"
assert rep_e["trunk_kwargs"] == train_bc.ENTITY_TRUNK_KWARGS
assert rep_e["actor_params"] == DEEPSETS_ACTOR_PARAMS, rep_e["actor_params"]

rep_a, ck_a, rows_a = run(
    "t_attn", ["--trunk", "attention", "--d-model", "128", "--n-layers", "2",
               "--n-heads", "4"])
assert rep_a["trunk"] == "attention"
assert rep_a["trunk_kwargs"] == dict(species_vocab=152, move_vocab=166, embed_dim=64,
                                     d_model=128, n_layers=2, n_heads=4)
assert rep_a["actor_params"] == ACTOR_PARAMS, rep_a["actor_params"]
cfg_a = ck_a["config"]["agent"] if isinstance(ck_a.get("config"), dict) else ck_a["config"].agent
assert cfg_a["trunk"] == "attention"
# Same dataset, same split -> the two arms' held-out rows are the SAME rows in
# the SAME order. A paired delta is meaningless otherwise.
assert np.array_equal(rows["battle_ids"], rows_a["battle_ids"])
assert np.array_equal(rows["free"], rows_a["free"])
print("CHILD OK")
"""


def _run(src: str, cwd=None, **names) -> None:
    head = "".join(f"{k} = {v!r}\n" for k, v in names.items())
    proc = subprocess.run(
        [sys.executable, "-c", head + src],
        env=_ENV, cwd=cwd, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHILD OK" in proc.stdout, proc.stdout


_PINS = dict(ACTOR_PARAMS=_ACTOR_PARAMS, CRITIC_PARAMS=_CRITIC_PARAMS,
             DEEPSETS_ACTOR_PARAMS=_DEEPSETS_ACTOR_PARAMS)


def test_attention_trunk_gates():
    _run(_CHILD, **_PINS)


def test_train_bc_trunk_option(tmp_path):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _run(_TRAIN_BC_CHILD, cwd=str(tmp_path), REPO=repo, OUT=str(tmp_path), **_PINS)

"""Cross-encoder eval shim (PrefixSliceActor + eval_checkpoint's loader).

The shim's entire legality rests on one claim: the id block is a PURE
suffix, so under the 828 process `vec[:808]` is bit-for-bit the v2/808
encoding. The first test measures that claim directly — the same battle
encoded under both flag configurations (separate subprocesses; the flags
are read at import) must agree on the first 808 floats EXACTLY.

The loader tests run in an 828 subprocess: a genuine v2/808 MLP checkpoint
loads through _load_showdown_agent, comes back wrapped, and acts in-mask on
828 obs with logits bitwise equal to the unwrapped actor on the sliced obs;
a 807-wide (pre-recharge-fix) state dict is REFUSED — its layout differs by
an inserted dim and has no exact map on current code.
"""

import os
import subprocess
import sys

import torch

from rl.networks.mlp import PrefixSliceActor, mlp


def test_prefix_slice_actor_is_exact():
    torch.manual_seed(0)
    actor = mlp(808, [32], 10)
    wrapped = PrefixSliceActor(actor, 808)
    g = torch.Generator().manual_seed(1)
    x = torch.rand(5, 828, generator=g)
    assert torch.equal(wrapped(x), actor(x[:, :808]))


_ENCODE_CHILD = r"""
import sys
import numpy as np
from types import SimpleNamespace
from poke_env.battle.move import Move
from poke_env.battle.pokemon_type import PokemonType
from poke_env.data import GenData
from rl.envs.showdown import OBS_DIM, embed_battle

def stub_mon(species, moves=(), boost=0):
    return SimpleNamespace(
        species=species, current_hp_fraction=0.8, fainted=False, status=None,
        level=100, base_stats={"hp": 100, "atk": 100, "def": 100, "spa": 100, "spe": 100},
        types=[PokemonType.NORMAL], type_1=PokemonType.NORMAL, type_2=None,
        boosts={k: (boost if k == "atk" else 0) for k in
                ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")},
        effects={}, status_counter=0, preparing=False,
        moves={m.id: m for m in moves}, must_recharge=False,
    )

own = [Move(m, gen=1) for m in ("surf", "blizzard", "thunderbolt", "bodyslam")]
opp = [Move(m, gen=1) for m in ("earthquake", "rest", "amnesia", "psychic")]
team = [stub_mon("starmie", own, boost=2), stub_mon("rhydon"), stub_mon("chansey"),
        stub_mon("snorlax"), stub_mon("exeggutor"), stub_mon("alakazam")]
opp_team = [stub_mon("tauros", opp, boost=1), stub_mon("zapdos")]
battle = SimpleNamespace(
    active_pokemon=team[0], opponent_active_pokemon=opp_team[0],
    team={m.species: m for m in team}, opponent_team={m.species: m for m in opp_team},
    turn=3, force_switch=False, trapped=False, available_moves=own,
)
vec = embed_battle(battle, GenData.from_gen(1).type_chart)
assert vec.shape == (OBS_DIM,)
print(vec[:808].tobytes().hex())
"""


def test_id_suffix_is_a_pure_suffix_across_processes():
    outs = []
    for extra in ({}, {"POKEMON_RL_ENCODER_IDS": "1"}):
        result = subprocess.run(
            [sys.executable, "-c", _ENCODE_CHILD],
            env={
                **{k: v for k, v in os.environ.items() if k != "POKEMON_RL_ENCODER_IDS"},
                "POKEMON_RL_ENCODER_V2": "1",
                **extra,
            },
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        outs.append(result.stdout.strip())
    assert outs[0] == outs[1], "vec[:808] differs between v2/808 and v2/828 — NOT a pure suffix"


_LOADER_CHILD = r"""
import importlib.util
import numpy as np
import torch
import gymnasium as gym

spec = importlib.util.spec_from_file_location("eval_ckpt", "scripts/eval_checkpoint.py")
ec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ec)

from rl.agents.ppo import PPOAgent
from rl.common.config import Config
from rl.networks.mlp import PrefixSliceActor

AGENT = dict(algo="ppo", hidden_sizes=[32, 32], lr=2.5e-4, gamma=1.0,
             gae_lambda=0.95, rollout_steps=8, epochs=1, minibatches=1,
             clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5)
CFG = dict(env_id="Showdown-v0", seed=0, total_steps=1, eval_every=1,
           eval_episodes=1, num_envs=1, torch_threads=1, checkpoint_every=0,
           run_name="shim_test", logger="none", eval_win_rate=True, agent=AGENT)

def build(width):
    torch.manual_seed(0)
    return PPOAgent(gym.spaces.Box(-1.0, 4.0, (width,), np.float32),
                    gym.spaces.Discrete(10), num_envs=1, device="cpu",
                    **{k: v for k, v in AGENT.items() if k != "algo"})

# A genuine v2/808 checkpoint loads shimmed and acts exactly.
donor = build(808)
ckpt = {"agent": donor.state_dict(), "config": CFG}
agent = ec._load_showdown_agent(ckpt, Config(**CFG))
assert isinstance(agent.actor, PrefixSliceActor), type(agent.actor)
g = torch.Generator().manual_seed(2)
x = torch.rand(3, 828, generator=g)
with torch.no_grad():
    assert torch.equal(agent.actor(x), donor.actor(x[:, :808]))
mask = np.ones(10, bool); mask[0] = False
a = agent.act(x[0].numpy(), mask, deterministic=True)
assert mask[a], a

# A native 828 checkpoint passes through unwrapped.
native = build(828)
agent2 = ec._load_showdown_agent({"agent": native.state_dict(), "config": CFG}, Config(**CFG))
assert not isinstance(agent2.actor, PrefixSliceActor)

# A v2/807 (pre-recharge-fix) checkpoint is refused, not shimmed.
old = build(807)
try:
    ec._load_showdown_agent({"agent": old.state_dict(), "config": CFG}, Config(**CFG))
except ValueError as e:
    assert "807" in str(e)
else:
    raise AssertionError("v2/807 checkpoint was not refused")
print("OK")
"""


def test_loader_shims_808_passes_828_refuses_807():
    result = subprocess.run(
        [sys.executable, "-c", _LOADER_CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        timeout=300,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"

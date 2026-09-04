"""Rung 2 (STRUCTURE) offline gates — configs/showdown_sp_struct12m.yaml.

R0-3 MLP BIT-IDENTITY runs in-process: the mlp path never imports poke_env,
and its goldens were captured from the pre-seam code (commit 9725816) under
torch.manual_seed(0) — same seed, same construction order, same RNG stream.
A drift here invalidates more than the rung (K3): every prior number was
produced by that construction path.

Everything touching the entity trunk needs the 828-dim encoder, whose flags
are read at module import — so those gates run in a SUBPROCESS with both
env vars set (test_encoder_v2's pattern): R0-2 param ceiling, tokenizer
alignment against a real embed_battle encoding, R0-7 eval-time masking, and
the K4 init hazard (embedding tables must carry ps-ppo's std-0.02 init, not
orthogonal statistics).
"""

import os
import subprocess
import sys

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

# The constructor args every gate below shares; hidden_sizes is the control
# arm's [512,512] (unused by the entity trunk, kept so a trunk: mlp rerun of
# the rung config is exact).
_PPO_KWARGS = dict(
    num_envs=8, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=128, epochs=4, minibatches=4, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
    hidden_sizes=[512, 512],
)

# The ratified trunk_kwargs, verbatim from the config.
_TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256],
    value_sizes=[384, 384],
)


def _mlp_agent():
    torch.manual_seed(0)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (808,), np.float32),
        gym.spaces.Discrete(10),
        **_PPO_KWARGS,
    )


def test_r03_mlp_trunk_bit_identical_to_pre_seam_goldens():
    """trunk="mlp" (the default) must reproduce the pre-seam code exactly —
    params AND forward. Goldens captured 2026-08-08 from commit 9725816."""
    agent = _mlp_agent()
    assert sum(p.numel() for p in agent.actor.parameters()) == 681_994
    asum = torch.cat([p.detach().flatten() for p in agent.actor.parameters()]).double().sum().item()
    csum = torch.cat([p.detach().flatten() for p in agent.critic.parameters()]).double().sum().item()
    # The two PARAMETER sums are reduction-order sensitive: torch's CPU sum
    # over ~700k doubles splits by intra-op thread count, and the goldens were
    # captured at this box's default (10). Under OMP_NUM_THREADS=1 csum lands
    # at -23.334520053290372 — the same weights, a different summation tree
    # (audit F-22, 2026-09-02). 1e-9 is ~10^5x that noise and ~10^9x below
    # what any real init change moves the sum by, so the pin keeps its teeth.
    # The forward-pass goldens below stay EXACT: they were measured identical
    # at 1 and 10 threads.
    assert abs(asum - 38.545732003828235) < 1e-9, asum
    assert abs(csum - -23.33452005329038) < 1e-9, csum
    g = torch.Generator().manual_seed(123)
    x = torch.rand(3, 808, generator=g) * 2 - 0.5
    with torch.no_grad():
        logits = agent.actor(x)
        values = agent.critic(x)
    assert logits.double().sum().item() == 0.010122665902599692
    assert values.flatten().tolist() == [
        0.073136851191520691, 0.17855918407440186, -0.24839745461940765,
    ]


def test_trunk_seam_guards():
    obs = gym.spaces.Box(-1.0, 4.0, (828,), np.float32)
    act = gym.spaces.Discrete(10)
    with pytest.raises(ValueError, match="unknown trunk"):
        PPOAgent(obs, act, trunk="transformer", **_PPO_KWARGS)
    with pytest.raises(TypeError, match="Discrete"):
        PPOAgent(
            obs, gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
            trunk="entity_deepsets", **_PPO_KWARGS,
        )
    with pytest.raises(TypeError, match="flat obs"):
        PPOAgent(
            gym.spaces.Box(0.0, 1.0, (4, 10, 10), np.float32), act,
            trunk="entity_deepsets", **_PPO_KWARGS,
        )


def test_entity_trunk_refuses_a_missing_id_flag():
    """The R0-1 seam: in this process the encoder flags are unset, so the
    tokenizer's layout assert must fail loudly — the exact failure a
    forgotten env var would produce at launch or eval."""
    with pytest.raises(ValueError, match="POKEMON_RL_ENCODER_IDS"):
        PPOAgent(
            gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
            gym.spaces.Discrete(10),
            trunk="entity_deepsets", trunk_kwargs=_TRUNK_KWARGS,
            **_PPO_KWARGS,
        )


def test_id_scale_round_trip_is_exact_in_float32():
    """The encoder emits id/256.0 and the tokenizer recovers round(x*256):
    exact for every id both tables can hold (256 is a power of two)."""
    ids = np.arange(166, dtype=np.int64)
    encoded = (ids / 256.0).astype(np.float32)
    decoded = np.round(encoded * 256.0).astype(np.int64)
    assert (decoded == ids).all()
    assert (encoded * 256.0 == np.round(encoded * 256.0)).all()


_CHILD = r"""
import numpy as np
import torch
import gymnasium as gym
from types import SimpleNamespace

from poke_env.battle.move import Move
from poke_env.battle.pokemon_type import PokemonType
from poke_env.data import GenData

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import (
    ACTIVE_DIM, GLOBAL_DIM, ID_DIM, MON_DIM, MOVE_DIM, OBS_DIM,
    _move_id, _species_id, embed_battle,
)
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING, EntityDeepSetsNet, EntityTokenizer

assert OBS_DIM == 828 and ID_DIM == 20, (OBS_DIM, ID_DIM)

TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)

# --- R0-2: param ceiling, exact counts --------------------------------------
# Ceiling = the flat [512,512] MLP actor on v2/808, the comparator's actual
# actor (verified live 2026-08-08).
assert ACTOR_PARAM_CEILING == 808 * 512 + 512 + 512 * 512 + 512 + 512 * 10 + 10 == 681_994
actor = EntityDeepSetsNet(828, 10, **TRUNK_KWARGS)
critic = EntityDeepSetsNet(828, 1, **TRUNK_KWARGS)
assert actor.param_count == sum(p.numel() for p in actor.parameters()) == 626_059
assert critic.param_count == 494_849, critic.param_count
assert actor.param_count <= ACTOR_PARAM_CEILING

# --- Tokenizer alignment against a REAL encoder pass ------------------------
def stub_mon(species, moves=(), active_boost=0, hp=1.0):
    return SimpleNamespace(
        species=species, current_hp_fraction=hp, fainted=False, status=None,
        level=100, base_stats={"hp": 100, "atk": 100, "def": 100, "spa": 100, "spe": 100},
        types=[PokemonType.NORMAL], type_1=PokemonType.NORMAL, type_2=None,
        boosts={k: (active_boost if k == "atk" else 0) for k in
                ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")},
        effects={}, status_counter=0, preparing=False,
        moves={m.id: m for m in moves}, must_recharge=False,
    )

own_moves = [Move(m, gen=1) for m in ("surf", "blizzard", "thunderbolt", "bodyslam")]
opp_moves = [Move(m, gen=1) for m in ("earthquake", "rest", "amnesia", "psychic")]
team = [
    stub_mon("starmie", own_moves, active_boost=2),
    stub_mon("rhydon"), stub_mon("chansey"), stub_mon("snorlax"),
    stub_mon("exeggutor"), stub_mon("alakazam"),
]
opp_team = [stub_mon("tauros", opp_moves, active_boost=1), stub_mon("zapdos")]
battle = SimpleNamespace(
    active_pokemon=team[0], opponent_active_pokemon=opp_team[0],
    team={m.species: m for m in team},
    opponent_team={m.species: m for m in opp_team},
    turn=3, force_switch=False, trapped=False, available_moves=own_moves,
)
type_chart = GenData.from_gen(1).type_chart
vec = embed_battle(battle, type_chart)
assert vec.shape == (828,)

x = torch.as_tensor(vec).unsqueeze(0)
tok = EntityTokenizer(828, 152, 166)
d = tok(x)
assert d["species_ids"][0, :6].tolist() == [_species_id(m.species) for m in team]
assert all(i > 0 for i in d["species_ids"][0, :6].tolist())
assert d["species_ids"][0, 6:].tolist() == (
    [_species_id(m.species) for m in opp_team] + [0, 0, 0, 0]
)
assert d["move_ids"][0, :4].tolist() == [_move_id(m) for m in own_moves]
assert d["move_ids"][0, 4:].tolist() == [_move_id(m) for m in opp_moves]
assert torch.equal(d["field"][0], x[0, :GLOBAL_DIM])
assert d["own_active"][0].tolist() == [1, 0, 0, 0, 0, 0]
assert d["opp_active"][0].tolist() == [1, 0, 0, 0, 0, 0]
# Own token 0: [1.0 || mon block || extras] with extras present (boosted);
# benched token 1: extras gated to zero by its own is-active bit.
own_act_off = GLOBAL_DIM + 6 * MON_DIM
mon0 = d["mons"][0, 0]
assert mon0[0] == 1.0
assert torch.equal(mon0[1 : 1 + MON_DIM], x[0, GLOBAL_DIM : GLOBAL_DIM + MON_DIM])
assert torch.equal(mon0[1 + MON_DIM :], x[0, own_act_off : own_act_off + ACTIVE_DIM])
assert mon0[1 + MON_DIM :].abs().sum() > 0  # the atk boost survived the gate
assert d["mons"][0, 1, 1 + MON_DIM :].abs().sum() == 0
# Opp token 0 carries its revealed flag where own tokens carry the 1.0 const.
assert d["mons"][0, 6, 0] == 1.0   # revealed
assert d["mons"][0, 8, 0] == 0.0   # never revealed: all-zero token

# --- Agent-level: R0-7 masking + K4 init hazard -----------------------------
torch.manual_seed(0)
agent = PPOAgent(
    gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
    num_envs=4, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=8, epochs=2, minibatches=2, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
    hidden_sizes=[512, 512], trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
)
# K4: embedding tables carry std-0.02 normal init, not orthogonal statistics
# (orthogonal rows would sit near unit scale) and not torch's N(0,1) default.
for net in (agent.actor, agent.critic):
    for emb in (net.species_emb, net.move_emb):
        std = emb.weight.std().item()
        assert 0.01 < std < 0.03, std
assert agent.actor.slot_bias.abs().sum() == 0.0
# The rescaled final scorer layer: near-uniform initial policy, like the
# MLP's 0.01 orthogonal head gain.
assert agent.actor.scorer[-1].weight.abs().max().item() < 0.01

# R0-7: eval-time (deterministic) and sampled actions both respect the mask.
obs = np.repeat(vec[None, :], 4, axis=0)
with torch.no_grad():
    free_argmax = int(agent.actor(torch.as_tensor(obs[:1])).argmax())
mask = np.ones((4, 10), dtype=bool)
mask[:, free_argmax] = False  # ban the unmasked argmax specifically
for _ in range(50):
    acts = agent.act(obs, mask)
    assert all(mask[i, a] for i, a in enumerate(acts)), acts
det = agent.act(obs[0], mask[0], deterministic=True)
assert mask[0, det] and det != free_argmax
# The value path takes no mask at all — structural, but assert it forwards.
with torch.no_grad():
    v = agent.critic(torch.as_tensor(obs, dtype=torch.float32))
assert v.shape == (4, 1) and torch.isfinite(v).all()
print("OK")
"""


def test_entity_trunk_gates_r02_r07_k4_and_tokenizer_alignment():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"

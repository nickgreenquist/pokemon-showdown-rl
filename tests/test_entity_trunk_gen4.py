"""BI-G4-2 — the entity trunk's layout argument (rl/networks/entity_deepsets.py).

Gen-1 bit-identity is guarded twice: tests/test_entity_deepsets.py's goldens
(pre-seam commit 9725816) and the pinned construction below, captured on the
PRE-layout-argument trunk (commit 526f839, 2026-09-05) at torch.manual_seed(0)
under the ratified trunk_kwargs. The gen-4 gates mirror the gen-1 subprocess
gate: tokenizer alignment against a REAL `embed_battle_gen4` encoding (the
committed fixture tape), agent-level masking, the privileged critic at
PRIV_DIM 703, and the pinned-vocab guard. Gen 4 needs no encoder env vars,
so everything here runs in-process; the gen-1 pin runs in a subprocess with
the flags set (test_encoder_v2's pattern).
"""

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import pytest
import torch
from poke_env.data import GenData

from rl.agents.ppo import PPOAgent
from rl.envs.gen4.encoder import embed_battle_gen4, privileged_block_gen4
from rl.envs.gen4.env import fake_spaces_gen4
from rl.envs.gen4.spec import LAYOUT, OBS_DIM_GEN4
from rl.envs.gen4.tape import replay_tape
from rl.envs.gen4.tracker import BattleTracker
from rl.envs.gen4.vocab import VOCAB
from rl.networks.entity_deepsets import (
    ACTOR_PARAM_CEILING, EntityDeepSetsNet, EntityTokenizer, TrunkLayout, resolve_layout,
)

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "tests/fixtures/gen4_tape_t0_2battles.jsonl.gz"

# The gen-4 trunk_kwargs the pre-reg carries: the pinned vocab sizes (row 0 =
# unknown) and the ratified gen-1 widths.
GEN4_TRUNK_KWARGS = dict(
    layout="gen4", species_vocab=301, move_vocab=183, item_vocab=41, ability_vocab=102,
    embed_dim=64, entity_dim=128, pool="max", ctx_sizes=[384, 384], scorer_sizes=[256],
    value_sizes=[384, 384],
)
PPO_KWARGS = dict(
    num_envs=4, device="cpu", lr=5.8884e-5, gamma=0.9999, gae_lambda=0.754,
    rollout_steps=8, epochs=2, minibatches=2, clip_eps=0.0829, entropy_coef=0.0588,
    value_coef=0.4375, max_grad_norm=0.543, hidden_sizes=[512, 512],
)


def test_gen4_layout_resolves_to_the_frozen_v01_tuples():
    lay = resolve_layout("gen4")
    assert isinstance(lay, TrunkLayout) and lay.name == "gen4"
    assert (lay.global_dim, lay.mon_dim, lay.active_dim, lay.move_dim) == (36, 61, 31, 71)
    assert (lay.id_species, lay.id_moves, lay.id_items, lay.id_abilities) == (12, 8, 12, 12)
    assert lay.obs_dim == OBS_DIM_GEN4 == 1448 and lay.id_dim == 44
    assert lay.priv_dim == LAYOUT.priv_dim == 703 and lay.priv_id_dim == 22
    assert (lay.species_vocab, lay.move_vocab, lay.item_vocab, lay.ability_vocab) == (301, 183, 41, 102)
    assert (VOCAB.n_species, VOCAB.n_moves, VOCAB.n_items, VOCAB.n_abilities) == (301, 183, 41, 102)
    with pytest.raises(ValueError, match="unknown trunk layout"):
        resolve_layout("gen9")


def test_gen4_vocab_guard_refuses_gen1_sizes_and_stray_tables():
    with pytest.raises(ValueError, match="pinned vocab"):
        EntityDeepSetsNet(1448, 10, species_vocab=152, move_vocab=166, layout="gen4")
    with pytest.raises(ValueError, match="obs width"):
        EntityDeepSetsNet(828, 10, **GEN4_TRUNK_KWARGS)


def _first_rich_decision():
    """A fixture decision with a revealed opponent mon and a move set: the
    battle object, its tracker and the encoding it produced."""
    tc = GenData.from_gen(4).type_chart
    trackers, found = {}, {}

    def on_decision(battle, request, seat):
        if found:
            return
        tr = trackers.setdefault((seat, battle.battle_tag), BattleTracker())
        vec = embed_battle_gen4(battle, tc, tr)
        if battle.turn >= 3 and battle.active_pokemon is not None and battle.opponent_active_pokemon is not None:
            found["battle"], found["vec"] = battle, vec

    replay_tape(_FIXTURE, on_decision)
    assert found, "fixture carried no turn-3 decision"
    return found["battle"], found["vec"]


def test_gen4_tokenizer_recovers_the_encoders_id_tail_and_blocks():
    battle, vec = _first_rich_decision()
    x = torch.as_tensor(vec).unsqueeze(0)
    tok = EntityTokenizer(1448, 301, 183, "gen4", 41, 102)
    d = tok(x)
    o = LAYOUT.ids_off
    ids = np.round(vec[o:] * 256.0).astype(np.int64)
    assert d["species_ids"][0].tolist() == ids[:12].tolist()
    assert d["move_ids"][0].tolist() == ids[12:20].tolist()
    assert d["item_ids"][0].tolist() == ids[20:32].tolist()
    assert d["ability_ids"][0].tolist() == ids[32:44].tolist()
    # Semantics, not just offsets: own species rows are the pinned vocab's,
    # and every own mon has a known item and ability at gen 4.
    own = list(battle.team.values())
    assert set(d["species_ids"][0, :len(own)].tolist()) == {VOCAB.species_id(m.species) for m in own}
    assert all(i > 0 for i in d["species_ids"][0, :len(own)].tolist())
    assert all(i > 0 for i in d["item_ids"][0, :len(own)].tolist())
    assert all(i > 0 for i in d["ability_ids"][0, :len(own)].tolist())
    assert torch.equal(d["field"][0], x[0, :36])
    assert d["mons"].shape == (1, 12, 1 + 61 + 31) and d["moves"].shape == (1, 8, 71)
    assert float(d["own_active"][0].sum()) == 1.0 and float(d["opp_active"][0].sum()) == 1.0
    # Own token: [1.0 || mon block || gated extras]; opp token 0 carries its revealed flag.
    assert d["mons"][0, 0, 0] == 1.0 and d["mons"][0, 6, 0] == 1.0
    active_row = int(d["own_active"][0].argmax())
    assert torch.equal(d["mons"][0, active_row, 1:62], x[0, 36 + active_row * 61: 36 + (active_row + 1) * 61])
    # Privileged block from the same vector round-trips through _priv_features' slicing.
    priv = privileged_block_gen4(vec)
    assert priv.shape == (703,)
    priv_ids = np.round(priv[-22:] * 256.0).astype(np.int64)
    assert priv_ids[:6].tolist() == ids[:6].tolist() and priv_ids[6:10].tolist() == ids[12:16].tolist()
    assert priv_ids[10:16].tolist() == ids[20:26].tolist() and priv_ids[16:22].tolist() == ids[32:38].tolist()


def test_gen4_agent_masks_inits_and_carries_a_privileged_critic():
    obs_space, act_space = fake_spaces_gen4()
    torch.manual_seed(0)
    agent = PPOAgent(obs_space, act_space, trunk="entity_deepsets",
                     trunk_kwargs=GEN4_TRUNK_KWARGS, **PPO_KWARGS)
    for net in (agent.actor, agent.critic):
        for emb in (net.species_emb, net.move_emb, net.item_emb, net.ability_emb):
            assert 0.01 < emb.weight.std().item() < 0.03  # K4: ps-ppo's std-0.02 tables
    assert agent.actor.scorer[-1].weight.abs().max().item() < 0.01
    assert agent.actor.param_count == 674_763 and agent.critic.param_count == 543_553
    assert agent.actor.param_count < ACTOR_PARAM_CEILING  # recorded, not gated, at gen 4
    _, vec = _first_rich_decision()
    obs = np.repeat(vec[None, :], 4, axis=0)
    with torch.no_grad():
        free_argmax = int(agent.actor(torch.as_tensor(obs[:1])).argmax())
    mask = np.ones((4, 10), dtype=bool)
    mask[:, free_argmax] = False
    for _ in range(30):
        acts = agent.act(obs, mask)
        assert all(mask[i, a] for i, a in enumerate(acts)), acts
    det = agent.act(obs[0], mask[0], deterministic=True)
    assert mask[0, det] and det != free_argmax
    # The privileged critic at PRIV_DIM 703 (the D18 lever, held back for the
    # first gen-4 run but constructible).
    torch.manual_seed(0)
    wide = PPOAgent(obs_space, act_space, trunk="entity_deepsets", privileged_dim=703,
                    trunk_kwargs=GEN4_TRUNK_KWARGS, **PPO_KWARGS)
    assert wide.critic.param_count == 691_009
    x = torch.cat([torch.as_tensor(obs, dtype=torch.float32), torch.rand(4, 703)], dim=1)
    with torch.no_grad():
        v = wide.critic(x)
    assert v.shape == (4, 1) and torch.isfinite(v).all()
    with pytest.raises(ValueError, match="PRIV_DIM 703"):
        PPOAgent(obs_space, act_space, trunk="entity_deepsets", privileged_dim=408,
                 trunk_kwargs=GEN4_TRUNK_KWARGS, **PPO_KWARGS)


def test_gen4_update_closes_on_the_entity_trunk():
    """One full PPO update through the gen-4 trunk on fixture-derived rows —
    the value-clip / power-schedule knobs on, as the pre-reg runs them."""
    obs_space, act_space = fake_spaces_gen4()
    torch.manual_seed(0)
    agent = PPOAgent(obs_space, act_space, trunk="entity_deepsets", trunk_kwargs=GEN4_TRUNK_KWARGS,
                     lr_anneal_steps=1000, lr_schedule="power", value_clip_eps=0.0184, **PPO_KWARGS)
    _, vec = _first_rich_decision()
    rng = np.random.default_rng(0)
    metrics = {}
    for t in range(PPO_KWARGS["rollout_steps"]):
        obs = np.repeat(vec[None, :], 4, axis=0) + rng.normal(scale=1e-3, size=(4, 1448)).astype(np.float32)
        obs[:, LAYOUT.ids_off:] = vec[LAYOUT.ids_off:]  # ids stay exact
        masks = np.ones((4, 10), dtype=bool)
        acts = agent.act(obs, masks)
        rews = np.zeros(4, dtype=np.float32)
        term = np.array([t == 7] * 4)
        metrics = agent.update((obs, acts, rews, obs, term, np.zeros(4, dtype=bool), masks, masks))
    assert metrics and np.isfinite(metrics["loss/policy"]) and np.isfinite(metrics["loss/value"])
    assert agent.optimizer.param_groups[0]["lr"] == 5.8884e-5  # x = 0 at the first update


_GEN1_PIN = r"""
import torch, numpy as np, gymnasium as gym
from rl.agents.ppo import PPOAgent
TK = dict(species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128, pool="max",
          ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384])
KW = dict(num_envs=8, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=128,
          epochs=4, minibatches=4, clip_eps=0.2, entropy_coef=0.01, value_coef=0.5,
          max_grad_norm=0.5, hidden_sizes=[512, 512])
# Captured 2026-09-05 on commit 526f839 (the trunk BEFORE the layout argument).
WANT = {
    0: (626059, 494849, 334.85143576179576, 454.9581814721477, 0.13518786523491144,
        [-2.746910572052002, -1.4528512954711914, -0.07449927926063538]),
    408: (626059, 642305, 410.50954506226424, 385.07299037224624, 0.18378696037689224,
          [-0.20323115587234497, -0.7318114638328552, -1.1789518594741821]),
}
for priv, (pa_w, pc_w, sa_w, sc_w, lo_w, va_w) in WANT.items():
    torch.manual_seed(0)
    a = PPOAgent(gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
                 trunk="entity_deepsets", trunk_kwargs=TK, privileged_dim=priv, **KW)
    assert a.actor.layout.name == "gen1" and a.actor.item_emb is None
    pa = sum(p.numel() for p in a.actor.parameters()); pc = sum(p.numel() for p in a.critic.parameters())
    sa = torch.cat([p.detach().flatten() for p in a.actor.parameters()]).double().sum().item()
    sc = torch.cat([p.detach().flatten() for p in a.critic.parameters()]).double().sum().item()
    g = torch.Generator().manual_seed(123)
    x = torch.rand(3, 828, generator=g) * 2 - 0.5
    x[:, 808:] = (torch.randint(0, 150, (3, 20), generator=g).float() / 256.0)
    xp = torch.cat([x, torch.rand(3, priv, generator=g)], dim=1) if priv else x
    with torch.no_grad():
        lo = a.actor(x).double().sum().item(); va = a.critic(xp).flatten().tolist()
    assert (pa, pc) == (pa_w, pc_w), (priv, pa, pc)
    # Parameter sums are reduction-order sensitive (test_entity_deepsets.py's
    # 1e-9 argument); the forwards are exact.
    assert abs(sa - sa_w) < 1e-9 and abs(sc - sc_w) < 1e-9, (priv, sa, sc)
    assert lo == lo_w and va == va_w, (priv, lo, va)
print("OK")
"""


def test_gen1_entity_trunk_is_bit_identical_to_the_pre_layout_pin():
    result = subprocess.run(
        [sys.executable, "-c", _GEN1_PIN],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=300, cwd=str(_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")

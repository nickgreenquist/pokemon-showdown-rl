"""D28 zero-info synthetic task (rl/networks/zeroinfo.py): the Z1-3/Z1-4
zero-lane gates plus the construction's own contracts, all offline.

Z1-3 — the target is a function of (obs, allow, valid, gen) ALONE: the API
carries no opp_choice parameter at all (asserted on the signature), and the
draw is bit-reproducible from those four inputs.
Z1-4 — init isolation: flipping aux_synthetic changes NO network weight at a
fixed seed (the dedicated generator must not touch the global torch stream).
"""

import inspect
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import pytest
import torch

# The entity trunk refuses to build without the encoder flags (the
# test_anneal_aux_group.py pattern): trunk-dependent tests skip in-process,
# and the subprocess test below re-runs this file WITH the flags so a bare
# `pytest tests/` still executes every gate.
_FLAGS_SET = (os.environ.get("POKEMON_RL_ENCODER_V2") == "1"
              and os.environ.get("POKEMON_RL_ENCODER_IDS") == "1")
_needs_flags = pytest.mark.skipif(
    not _FLAGS_SET,
    reason="entity trunk needs POKEMON_RL_ENCODER_V2/IDS set before import; "
           "the subprocess test in this file covers it",
)


def test_zeroinfo_gates_run_under_the_encoder_flags():
    if _FLAGS_SET:
        pytest.skip("already running with the flags; the in-process tests ran")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(Path(__file__).resolve()), "-q"],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1",
             "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]

import rl.networks.zeroinfo as zeroinfo
from rl.agents.ppo import PPOAgent
from rl.networks.opp_action import N_CLASSES, OTHER_MOVE
from rl.networks.zeroinfo import raw_blocks, synthetic_labels, synthetic_scores

TRUNK_KWARGS = dict(
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)
PPO_KWARGS = dict(
    num_envs=2, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=2, epochs=1, minibatches=1, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[512, 512],
)

TEST_FROZEN = {
    "tau": 8.8,
    "b": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "standardisation": {"move": [0.0, 1.0], "global": [0.0, 1.0], "bench": [0.0, 1.0]},
}


def mk(seed=0, **overrides):
    torch.manual_seed(seed)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
        gym.spaces.Discrete(10),
        trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
        **PPO_KWARGS, **overrides,
    )


rng = np.random.default_rng(0)


def obs_batch(n):
    x = rng.random((n, 828), dtype=np.float32) * 0.5
    x[:, 808:820] = rng.integers(1, 152, (n, 12)) / 256.0
    x[:, 820:828] = rng.integers(1, 166, (n, 8)) / 256.0
    return torch.as_tensor(x)


def masks(n, seed=3):
    g = torch.Generator().manual_seed(seed)
    allow = torch.rand((n, N_CLASSES), generator=g) > 0.4
    allow[:, OTHER_MOVE] = True  # the label space's "always legal" class
    valid = torch.rand((n,), generator=g) > 0.2
    return allow, valid


@_needs_flags
def test_frozen_guard_refuses_unfrozen_task(monkeypatch):
    monkeypatch.setattr(zeroinfo, "ZEROINFO_FROZEN", None)
    agent = mk(aux_oppact_coef=0.1)
    with pytest.raises(RuntimeError, match="unfrozen"):
        synthetic_scores(obs_batch(4), agent.actor.tokenizer)


@_needs_flags
def test_seam_synthetic_requires_aux_loss():
    with pytest.raises(ValueError, match="aux_synthetic"):
        mk(aux_synthetic=True)


@_needs_flags
def test_seam_synthetic_excludes_shuffle():
    with pytest.raises(ValueError, match="mutually"):
        mk(aux_oppact_coef=0.1, aux_shuffle_labels=True, aux_synthetic=True)


@_needs_flags
def test_z1_4_init_isolation_bit_identity():
    base = mk(seed=0, aux_oppact_coef=0.1)
    after_base = torch.randn(4)
    synth = mk(seed=0, aux_oppact_coef=0.1, aux_synthetic=True)
    # The flag must not consume the global stream (its generator is
    # dedicated), so the post-construction draw matches too.
    assert torch.equal(after_base, torch.randn(4))
    for net in ("actor", "critic", "aux_head"):
        a, b = getattr(base, net).state_dict(), getattr(synth, net).state_dict()
        for key, value in a.items():
            assert torch.equal(value, b[key]), (net, key)


def test_z1_3_signature_carries_no_opp_choice():
    # The structural half of Z1-3: the label path CANNOT read the opponent's
    # decision because no parameter carries it.
    params = set(inspect.signature(synthetic_labels).parameters)
    assert params == {"obs", "allow", "valid", "tok", "gen"}
    assert "opp_choice" not in inspect.signature(synthetic_scores).parameters


@_needs_flags
def test_z1_3_draw_reproducible_and_within_allow(monkeypatch):
    monkeypatch.setattr(zeroinfo, "ZEROINFO_FROZEN", TEST_FROZEN)
    agent = mk(aux_oppact_coef=0.1)
    obs, (allow, valid) = obs_batch(64), masks(64)
    t1, s1 = synthetic_labels(obs, allow, valid, agent.actor.tokenizer,
                              torch.Generator().manual_seed(11))
    t2, s2 = synthetic_labels(obs, allow, valid, agent.actor.tokenizer,
                              torch.Generator().manual_seed(11))
    assert torch.equal(t1, t2) and s1 == s2
    assert allow.gather(1, t1.unsqueeze(1)).all()  # never an illegal class
    t3, _ = synthetic_labels(obs, allow, valid, agent.actor.tokenizer,
                             torch.Generator().manual_seed(12))
    assert not torch.equal(t1, t3)  # per-lane generators decorrelate lanes


@_needs_flags
def test_shared_w_move_is_slot_equivariant(monkeypatch):
    # One w_move across the four slots: permuting the four raw move blocks
    # permutes the four scores (before the per-slot offsets, which exist
    # exactly because the head's slot_bias can represent them).
    frozen = dict(TEST_FROZEN, b=[0.1, 0.2, 0.3, 0.4, 0.0, 0.0])
    monkeypatch.setattr(zeroinfo, "ZEROINFO_FROZEN", frozen)
    agent = mk(aux_oppact_coef=0.1)
    tok = agent.actor.tokenizer
    obs = obs_batch(8)
    perm = torch.tensor([2, 0, 3, 1])
    permuted = obs.clone()
    mv = obs[:, tok.opp_move_off : tok.id_off].view(-1, 4, tok.move_dim)
    permuted[:, tok.opp_move_off : tok.id_off] = mv[:, perm].reshape(8, -1)
    b = torch.tensor(frozen["b"][:4])
    raw = synthetic_scores(obs, tok)[:, :4] - b
    raw_p = synthetic_scores(permuted, tok)[:, :4] - b
    assert torch.allclose(raw_p, raw[:, perm], atol=1e-6)


def test_bench_pool_max_and_empty(monkeypatch):
    tok = SimpleNamespace(global_dim=4, move_dim=5, mon_dim=3,
                          opp_mon_off=10, opp_act_off=34,
                          opp_move_off=36, id_off=56)
    obs = torch.zeros(2, 60)
    # Row 0: two live bench mons (revealed=1, fainted=0, active=0) with
    # distinguishable payloads; the pool must be the elementwise max.
    blk = obs[0, 10:34].view(6, 4)
    blk[1] = torch.tensor([1.0, 0.7, 0.0, 0.0])
    blk[2] = torch.tensor([1.0, 0.2, 0.0, 0.0])
    # Row 1: only an ACTIVE revealed mon -> no bench -> all-zero pool.
    blk1 = obs[1, 10:34].view(6, 4)
    blk1[0] = torch.tensor([1.0, 0.9, 0.0, 1.0])
    _, _, pooled = raw_blocks(obs, tok)
    assert torch.equal(pooled[0], torch.tensor([1.0, 0.7, 0.0, 0.0]))
    assert torch.equal(pooled[1], torch.zeros(4))


@_needs_flags
def test_sampler_entropy_stat_is_exact(monkeypatch):
    monkeypatch.setattr(zeroinfo, "ZEROINFO_FROZEN", TEST_FROZEN)
    agent = mk(aux_oppact_coef=0.1)
    obs, (allow, valid) = obs_batch(32), masks(32)
    tok = agent.actor.tokenizer
    _, stats = synthetic_labels(obs, allow, valid, tok,
                                torch.Generator().manual_seed(5))
    from rl.common.masking import masked_logits
    logits = masked_logits(TEST_FROZEN["tau"] * synthetic_scores(obs, tok), allow)
    p = torch.softmax(logits, dim=-1)
    ent = -(p.clamp_min(1e-12).log() * p).sum(-1)[valid].mean()
    assert abs(stats["aux/synth_sampler_entropy"] - float(ent)) < 1e-6


@_needs_flags
def test_port_fidelity_golden_vectors():
    # Review SF-1: the one gate that catches wrong frozen constants, a
    # permuted W draw order, or swapped standardisation groups. Golden
    # values generated from THIS implementation at the REAL frozen
    # constants on 2026-08-20 and pinned; any drift in ZEROINFO_FROZEN,
    # the W stream, the block slicing, or the standardisation breaks it.
    agent = mk(aux_oppact_coef=0.1)
    g = torch.Generator().manual_seed(20260820)
    obs = torch.rand((3, 828), generator=g) * 0.5
    golden = torch.tensor([
        [2.508495, 2.431342, 1.104716, 1.002298, 0.120854, -0.385043],
        [2.329986, 2.301043, 2.135106, 0.458404, -0.906711, -0.385043],
        [3.118377, 2.167996, 1.356774, 0.790868, -0.831348, -0.385043],
    ])
    assert torch.allclose(synthetic_scores(obs, agent.actor.tokenizer),
                          golden, atol=1e-5)


def test_frozen_constants_match_z1_2_json():
    # Review SF-2: the in-module constants are rounded copies of the
    # freeze; assert they match to their declared rounding. Skips on a
    # tree without the (gitignored) results dir.
    import json
    path = Path(__file__).resolve().parents[1] / \
        "results/design_ch2/z1_2_frozen.json"
    if not path.exists():
        pytest.skip("z1_2_frozen.json not present (results/ is gitignored)")
    fz = json.loads(path.read_text())
    mod = zeroinfo.ZEROINFO_FROZEN
    assert abs(mod["tau"] - fz["tau"]) < 1e-9
    for a, b in zip(mod["b"], fz["b"]):
        assert abs(a - b) < 5e-6
    for key in ("move", "global", "bench"):
        for a, b in zip(mod["standardisation"][key], fz["standardisation"][key]):
            assert abs(a - b) < 5e-7

"""R0-P1: the D25-P shuffle's correctness battery (placebo config P8).

The lever is ~40 lines; the battery proves the invariants the
pre-registration states as exact, and kills the leak classes review R1-14
named — including order-structured "permutations" (sort-and-roll passes
multiset/legality/bijection and is caught only by the lag-correlation and
match-fraction tests here).
"""

import math

import pytest
import torch

from rl.networks.opp_action import (
    N_CLASSES,
    aux_cross_entropy,
    marginal_nll,
    shuffle_within_allow,
)


def gen(seed=0):
    g = torch.Generator()
    g.manual_seed(seed)
    return g


def fixture(n=1024, seed=0, p_noswitch=0.08, p_invalid=0.15):
    """Synthetic rollout: two dominant allow classes (all-legal and
    no-switch), class-correlated targets (so a leak is detectable), and a
    block of invalid rows."""
    rng = torch.Generator()
    rng.manual_seed(seed)
    allow = torch.ones(n, N_CLASSES, dtype=torch.bool)
    noswitch = torch.rand(n, generator=rng) < p_noswitch
    allow[noswitch, 5] = False
    # class-correlated labels: all-legal rows lean SWITCH(5), no-switch rows
    # lean slot 0 — maximally detectable structure.
    target = torch.where(
        noswitch,
        torch.randint(0, 5, (n,), generator=rng),
        torch.where(torch.rand(n, generator=rng) < 0.5,
                    torch.full((n,), 5, dtype=torch.long),
                    torch.randint(0, 5, (n,), generator=rng)),
    ).long()
    valid = torch.rand(n, generator=rng) >= p_invalid
    return target, allow, valid


# --------------------------------------------------------------------------
# preserved invariants
# --------------------------------------------------------------------------


def test_valid_rows_only_and_bijection():
    target, allow, valid = fixture()
    out, stats = shuffle_within_allow(target, allow, valid, gen())
    # invalid rows never written
    assert torch.equal(out[~valid], target[~valid])
    # bijection over valid rows: sorted multiset identical
    assert torch.equal(out[valid].sort().values, target[valid].sort().values)
    assert stats["aux/shuffle_illegal_frac"] == 0.0


def test_per_class_multiset_and_legality():
    target, allow, valid = fixture()
    out, _ = shuffle_within_allow(target, allow, valid, gen())
    weights = (1 << torch.arange(N_CLASSES)).long()
    key = (allow.long() * weights).sum(-1)
    for c in key[valid].unique():
        rows = valid & (key == c)
        assert torch.equal(out[rows].sort().values, target[rows].sort().values)
    assert allow.gather(1, out.unsqueeze(-1)).squeeze(-1)[valid].all()


def test_weight_sum_and_loss_finite():
    target, allow, valid = fixture()
    out, _ = shuffle_within_allow(target, allow, valid, gen())
    logits = torch.randn(len(target), N_CLASSES)
    a = aux_cross_entropy(logits, target, allow, valid)
    b = aux_cross_entropy(logits, out, allow, valid)
    # same denominator (valid untouched), and no -1e8 label: loss stays small
    assert torch.isfinite(b) and float(b) < 10.0 and torch.isfinite(a)


def test_singleton_class_kept_and_counted():
    # one row in its own class: [1,0,0,0,1,0]
    target = torch.tensor([0, 5, 5, 1])
    allow = torch.tensor([
        [1, 0, 0, 0, 1, 0],
        [1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1],
    ], dtype=torch.bool)
    valid = torch.ones(4, dtype=torch.bool)
    out, stats = shuffle_within_allow(target, allow, valid, gen())
    assert out[0] == 0                       # kept its true label
    assert stats["aux/shuffle_identity_frac"] == pytest.approx(0.25)
    assert stats["aux/shuffle_n_classes"] == 2.0


def test_empty_valid():
    target, allow, _ = fixture(n=8)
    out, stats = shuffle_within_allow(target, allow,
                                      torch.zeros(8, dtype=torch.bool), gen())
    assert torch.equal(out, target)
    assert stats["aux/shuffle_match_frac"] == 0.0


# --------------------------------------------------------------------------
# destroyed information — MC over many draws
# --------------------------------------------------------------------------


def test_row_conditional_law_destroyed():
    """For a fixed row, the assigned-label law over draws matches its CLASS
    multiset (TV < 0.03), i.e. the row's own obs/label contributes nothing."""
    target, allow, valid = fixture(n=512, seed=3)
    weights = (1 << torch.arange(N_CLASSES)).long()
    key = (allow.long() * weights).sum(-1)
    g = gen(11)
    draws = 3000
    # probe: the first valid all-legal row whose true label is SWITCH
    all_legal = int(key[valid].mode().values)
    rows = (valid & (key == all_legal)).nonzero(as_tuple=True)[0]
    probe = int(rows[target[rows] == 5][0])
    counts = torch.zeros(N_CLASSES)
    for _ in range(draws):
        out, _ = shuffle_within_allow(target, allow, valid, g)
        counts[out[probe]] += 1
    emp = counts / draws
    ref = torch.bincount(target[rows], minlength=N_CLASSES).float()
    ref /= ref.sum()
    assert float((emp - ref).abs().sum()) / 2 < 0.03


def test_lag_correlation_and_fixed_points():
    """Kills order-structured 'permutations' (review R1-14): sort-and-roll
    preserves multiset/legality/bijection but produces a fixed-point count
    far from Binomial(n, sum q^2) and lag-structured label correlation."""
    target, allow, valid = fixture(n=1024, seed=5)
    weights = (1 << torch.arange(N_CLASSES)).long()
    key = (allow.long() * weights).sum(-1)
    # expected match rate: sum_c w_c sum_y q_{c,y}^2
    exp_match, var_terms, n_valid = 0.0, 0.0, int(valid.sum())
    for c in key[valid].unique():
        rows = valid & (key == c)
        q = torch.bincount(target[rows], minlength=N_CLASSES).float()
        q /= q.sum()
        exp_match += float(rows.sum()) / n_valid * float((q ** 2).sum())
    g = gen(13)
    matches, lag1 = [], []
    for _ in range(200):
        out, stats = shuffle_within_allow(target, allow, valid, g)
        matches.append(stats["aux/shuffle_match_frac"])
        v = valid.nonzero(as_tuple=True)[0]
        a = (out[v][:-1] == target[v][1:]).float().mean()   # shifted match
        lag1.append(float(a))
    mean_match = sum(matches) / len(matches)
    se = math.sqrt(exp_match * (1 - exp_match) / n_valid / len(matches)) * 3
    assert abs(mean_match - exp_match) < max(3 * se, 0.01)
    assert mean_match < 0.99                                # not identity
    # lag-1 shifted match sits at a chance level (near the marginal collision
    # rate), nowhere near the ~1.0 a within-class roll-by-one would produce.
    assert abs(sum(lag1) / len(lag1) - exp_match) < 0.05
    assert sum(lag1) / len(lag1) < 0.5


def test_marginal_nll_brute_force():
    target = torch.tensor([0, 0, 5, 5, 1])
    allow = torch.ones(5, N_CLASSES, dtype=torch.bool)
    valid = torch.ones(5, dtype=torch.bool)
    got = marginal_nll(target, allow, valid)
    counts = torch.tensor([2, 1, 0, 0, 0, 2]).double() + 0.5
    p = counts / counts.sum()
    want = float(-(2 * p[0].log() + p[1].log() + 2 * p[5].log()) / 5)
    assert got == pytest.approx(want, abs=1e-9)


# --------------------------------------------------------------------------
# seams and determinism
# --------------------------------------------------------------------------


def test_determinism_and_dedicated_stream():
    target, allow, valid = fixture()
    out1, _ = shuffle_within_allow(target, allow, valid, gen(42))
    out2, _ = shuffle_within_allow(target, allow, valid, gen(42))
    assert torch.equal(out1, out2)
    # the default stream is untouched: a global draw before/after agrees
    torch.manual_seed(7)
    before = torch.randperm(16)
    torch.manual_seed(7)
    shuffle_within_allow(target, allow, valid, gen(1))
    after = torch.randperm(16)
    assert torch.equal(before, after)


TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256],
    value_sizes=[384, 384],
)
PPO_KWARGS = dict(
    num_envs=2, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=2, epochs=1, minibatches=1, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
    hidden_sizes=[512, 512],
)


def mk(seed=0, trunk="entity_deepsets", **overrides):
    import os
    import gymnasium as gym
    import numpy as np
    from rl.agents.ppo import PPOAgent
    # The entity tokenizer reads the encoder flags from the process env at
    # construction; both are required for the 828 layout. Set for the
    # construction only and restore, so no other test inherits them.
    saved = {k: os.environ.get(k)
             for k in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")}
    os.environ["POKEMON_RL_ENCODER_V2"] = "1"
    os.environ["POKEMON_RL_ENCODER_IDS"] = "1"
    try:
        torch.manual_seed(seed)
        kw = dict(PPO_KWARGS)
        if trunk == "entity_deepsets":
            kw["trunk_kwargs"] = TRUNK_KWARGS
        return PPOAgent(
            gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
            gym.spaces.Discrete(10),
            trunk=trunk, **kw, **overrides,
        )
    finally:
        for k, val in saved.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val


def test_loud_seam_flag_without_coef():
    # trunk-independent: the seam fires before any aux head exists.
    with pytest.raises(ValueError, match="aux_shuffle_labels"):
        mk(trunk="mlp", aux_oppact_coef=0.0, aux_shuffle_labels=True)


_CHILD = r"""
import gymnasium as gym
import numpy as np
import torch
from rl.agents.ppo import PPOAgent

TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256],
    value_sizes=[384, 384],
)
PPO_KWARGS = dict(
    num_envs=2, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=2, epochs=1, minibatches=1, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
    hidden_sizes=[512, 512],
)

def mk(**overrides):
    torch.manual_seed(123)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
        gym.spaces.Discrete(10),
        trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
        **PPO_KWARGS, **overrides,
    )

a = mk(aux_oppact_coef=0.1)
b = mk(aux_oppact_coef=0.1, aux_shuffle_labels=True)
assert a._shuffle_gen is None and b._shuffle_gen is not None
for k, v in a.actor.state_dict().items():
    assert torch.equal(v, b.actor.state_dict()[k]), k
pa = sum(p.numel() for p in a.actor.parameters()) + \
    sum(p.numel() for p in a.aux_head.parameters())
pb = sum(p.numel() for p in b.actor.parameters()) + \
    sum(p.numel() for p in b.aux_head.parameters())
assert pa == pb == 675_538, (pa, pb)
print("CHILD OK")
"""


def test_flag_off_is_exact_noop_including_rng():
    """Flag off: no generator exists; the flag consumes no RNG at
    construction (bit-identical actor state_dict at fixed seed); zero added
    params. Subprocess: the 828 encoder flags are read at import."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    out = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1",
             "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=300,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert "CHILD OK" in out.stdout

"""The ensemble behind SearchAgent's surface (rl/search/ensemble_search.py).

Four properties, in the order that would hurt most if they broke:

1. A ONE-MEMBER ensemble is that member, BITWISE, on all three surfaces. This
   is the no-op gate every search dial in this repo has had to pass (the D5
   golden digest, det_blind's "absent = no view built"): if the wrapper is not
   provably inert at M=1, no delta it produces at M=3 is attributable.
2. The PRIOR is the log-pool, and its argmax agrees with `EnsembleAgent` --
   so a searched ensemble and the greedy ENS3 object are the same policy and a
   delta between them belongs to the search.
3. q is the ARITHMETIC mean of the members' opponent models, computed from each
   member's OWN features, and it survives the softmax the CALLER applies.
   Feeding one member's head another member's activations is the defect this
   test exists to catch, and a plain logit-mean is the wrong pooling rule.
4. The leaf value is the arithmetic mean of the members' critics -- the same
   rule `_loo_critic_fn` uses, so the two evaluator forms are comparable.
"""

from __future__ import annotations

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import ID_DIM
from rl.search.ensemble_search import EnsembleSearchAdapter
from rl.search.ensemble import EnsembleAgent

# The entity trunk refuses to build without the id suffix
# (entity_deepsets.py:129) and reads ID_DIM at IMPORT time, so setting the flag
# inside a test cannot work. The suite's documented invocation leaves the flags
# unset -- R0-1 asserts they are unset -- so this file SKIPS rather than forcing
# them, matching tests/test_entity_scorer_factorization.py.
pytestmark = pytest.mark.skipif(
    ID_DIM == 0,
    reason="entity trunk needs POKEMON_RL_ENCODER_IDS=1; set it to run this file",
)

OBS_DIM, N_ACTS = 828, 10
TK = dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
          pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64])


def _agent(seed: int) -> PPOAgent:
    torch.manual_seed(seed)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(N_ACTS),
        num_envs=2, device="cpu", lr=1e-3, gamma=1.0, gae_lambda=0.95,
        rollout_steps=8, epochs=1, minibatches=1, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
        hidden_sizes=[64, 64], trunk="entity_deepsets", trunk_kwargs=dict(TK),
        aux_oppact_coef=0.1, aux_scorer_sizes=[32], aux_head_gain=0.01,
    )


@pytest.fixture(scope="module")
def members():
    """Three agents whose OPPONENT MODELS actually differ.

    `aux_head_gain=0.01` is the real recipe's value and it makes a FRESH head
    emit a near-uniform q (measured on this fixture: every class within 4e-4 of
    1/6). At that point the arithmetic mean and the log-pool agree to 1e-7 and
    a test cannot tell the pooling rules apart -- which is exactly what the
    teeth-check in test_q_... caught on the first run. A trained head is not
    near-uniform, so the heads are scaled here to stand in for one; the scale
    is per-member so the members disagree, which is the whole point of an
    ensemble."""
    ms = [_agent(s) for s in (0, 1, 2)]
    with torch.no_grad():
        for i, m in enumerate(ms):
            for p in m.aux_head.parameters():
                p.mul_(30.0 + 10.0 * i)
    return ms


@pytest.fixture(scope="module")
def obs():
    g = np.random.default_rng(7)
    o = (g.random((1, OBS_DIM)) * 2 - 0.5).astype(np.float32)
    # the id lanes the v2 encoder reads as embedding indices
    o[:, 808:] = (g.integers(0, 150, (1, 20)) / 256.0).astype(np.float32)
    return torch.as_tensor(o)


def test_one_member_is_that_member_bitwise(members, obs):
    """The no-op gate. M=1 must add NOTHING."""
    m = members[0]
    a = EnsembleSearchAdapter([m])
    with torch.no_grad():
        lone_logits, *lone_feats = m.actor(obs, return_features=True)
        ens_logits, ens_feats = a.actor(obs, return_features=True)
        # The adapter returns log_softmax(logits); softmax recovers the same
        # distribution bitwise-close, and the ARGMAX is exactly equal.
        assert torch.equal(torch.softmax(ens_logits, -1).argmax(-1),
                           torch.softmax(lone_logits, -1).argmax(-1))
        assert torch.allclose(torch.softmax(ens_logits, -1),
                              torch.softmax(lone_logits, -1), atol=1e-6)
        # q: softmax(adapter aux) must equal softmax(member aux) exactly enough
        q_ens = torch.softmax(a.aux_head(ens_feats), dim=-1)
        q_lone = torch.softmax(m.aux_head(*lone_feats), dim=-1)
        assert torch.allclose(q_ens, q_lone, atol=1e-6), (q_ens - q_lone).abs().max()
        # v: a one-element mean is the element, bitwise
        batch = obs.repeat(4, 1)
        assert torch.equal(a.critic(batch), m.critic(batch).reshape(-1))


def test_the_prior_is_the_log_pool_and_agrees_with_ensemble_agent(members, obs):
    """Property 2: the searched object's prior IS the greedy ENS3 policy."""
    a = EnsembleSearchAdapter(members)
    mask = np.ones(N_ACTS, dtype=bool)
    mask[3] = mask[7] = False  # two illegal actions, so masking is live
    with torch.no_grad():
        mean_logp, _ = a.actor(obs, return_features=True)
        # the log-pool, computed independently here
        want = torch.stack([torch.log_softmax(m.actor(obs), dim=-1)
                            for m in members]).mean(dim=0)
    assert torch.allclose(mean_logp, want, atol=1e-7)
    # ...and its masked argmax is EnsembleAgent's own choice on the same rows
    ea = EnsembleAgent(members)
    got = ea.act(obs.numpy()[0], action_mask=mask, deterministic=True)
    mine = a.act(obs.numpy()[0], action_mask=mask, deterministic=True)
    assert got == mine, (got, mine)


def test_q_is_the_arithmetic_mean_from_each_members_own_features(members, obs):
    """Property 3, and the two ways to get it wrong.

    A plain logit-mean is a DIFFERENT pooling rule (a log-pool), and crossing
    features between members is a silent correctness bug rather than an error.
    Both are asserted to be distinguishable on this fixture, so the test has
    teeth rather than passing by numerical coincidence.
    """
    a = EnsembleSearchAdapter(members)
    with torch.no_grad():
        _, feats = a.actor(obs, return_features=True)
        q = torch.softmax(a.aux_head(feats), dim=-1)
        per_member = [
            torch.softmax(m.aux_head(*f), dim=-1) for m, f in zip(members, feats)
        ]
        want = torch.stack(per_member).mean(dim=0)
        logit_pool = torch.softmax(
            torch.stack([m.aux_head(*f) for m, f in zip(members, feats)]).mean(0),
            dim=-1)
    assert torch.allclose(q, want, atol=1e-6), (q - want).abs().max()
    assert q.sum(-1).allclose(torch.ones(1), atol=1e-5), "q must be a distribution"
    # the wrong rule is actually different here, so property 3 is not vacuous
    assert not torch.allclose(want, logit_pool, atol=1e-4), (
        "logit-mean and prob-mean coincide on this fixture; the test cannot "
        "tell the pooling rules apart and must be re-fixtured"
    )


def test_leaf_value_is_the_mean_of_the_members_critics(members, obs):
    a = EnsembleSearchAdapter(members)
    batch = obs.repeat(5, 1)
    with torch.no_grad():
        want = torch.stack([m.critic(batch).reshape(-1) for m in members]).mean(0)
    assert torch.equal(a.critic(batch), want)


def test_a_member_without_an_oppact_head_is_refused():
    """Without the head a checkpoint can never be searched; fail at
    construction, not inside a leaf."""
    m = _agent(0)
    m.aux_head = None
    with pytest.raises(AssertionError, match="oppact head"):
        EnsembleSearchAdapter([m])

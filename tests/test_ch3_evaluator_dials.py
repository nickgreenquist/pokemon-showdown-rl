"""R3 E-cell dial tests (design §4 R3, tranche 1: E2 noise, E3 LOO,
oppact ablation). Offline: stub agent, stub battles from test_ch3_bridge.

The load-bearing contracts:
- evaluator=None is the R2 configuration BIT-IDENTICAL (same actions, same
  stats, and no extra draws on any rng stream);
- the E2 noise stream is salted off the determinization stream — an E2 arm
  expands the exact leaves of the E0 arm and differs only at evaluation;
- E2 is deterministic per decision key (replay clause D2 holds for dials);
- E3's leaf value is the mean of the OTHER lanes' critics;
- oppact_uniform substitutes q AT THE SOLVE while the recorded entropy
  stays the real head's (the dial measures decisions, not statistics).
"""

import numpy as np
import pytest
import torch

import rl.search.agent as agent_mod
from rl.search.agent import SearchAgent
from rl.search.matrix import DOSES, N_L6
from tests.test_ch3_matrix import _mask, _two_mon_battle


class _StubAgent:
    """Just enough surface for SearchAgent: actor(obs, return_features=True)
    -> (logits, feats); aux_head(feats) -> L6 logits; critic(t) -> const."""

    def __init__(self, q_logits=None, value=0.0):
        self._q_logits = q_logits if q_logits is not None else np.zeros(N_L6)
        self._value = value

    def actor(self, obs_t, return_features=True):
        logits = torch.zeros((obs_t.shape[0], 10))
        return logits, obs_t

    def aux_head(self, feats):
        return torch.as_tensor(self._q_logits, dtype=torch.float32).repeat(
            feats.shape[0], 1
        )

    def critic(self, t):
        return torch.full((t.shape[0],), float(self._value))


def _act(sa, battle_index=3, decision_index=1):
    b = _two_mon_battle()
    obs = np.zeros(8, dtype=np.float32)
    return sa.act(b, obs, _mask(), battle_index, decision_index)


def test_e0_none_is_default_and_identical():
    a1, s1 = _act(SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7))
    a2, s2 = _act(
        SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7, evaluator=None)
    )
    assert a1 == a2
    assert s1["search/leaves"] == s2["search/leaves"]
    assert s1["search/chosen"] == s2["search/chosen"]


def test_noise_replays_e0_determinizations_exactly():
    e0 = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7)
    e2 = SearchAgent(
        _StubAgent(), DOSES["S"], checkpoint_seed=7,
        evaluator={"kind": "noise", "sigma": 0.4},
    )
    _, s0 = _act(e0)
    _, s2 = _act(e2)
    # identical leaves = identical determinization/expansion stream; the
    # dial touched only the evaluation
    assert s0["search/leaves"] == s2["search/leaves"]


def test_noise_is_deterministic_per_decision_key():
    mk = lambda: SearchAgent(
        _StubAgent(), DOSES["S"], checkpoint_seed=7,
        evaluator={"kind": "noise", "sigma": 0.4},
    )
    a1, s1 = _act(mk())
    a2, s2 = _act(mk())
    assert a1 == a2
    assert s1["search/chosen"] == s2["search/chosen"]


def test_noise_changes_evaluation_at_large_sigma():
    # with a zero critic and sigma dominating, the BR values differ from
    # E0's; assert the noisy critic actually perturbs values (not actions,
    # which can coincide on tiny matrices)
    sa = SearchAgent(
        _StubAgent(), DOSES["S"], checkpoint_seed=7,
        evaluator={"kind": "noise", "sigma": 0.4},
    )
    fn = sa._decision_critic(3, 5, 1)
    batch = np.zeros((6, 8), dtype=np.float32)
    v = fn(batch)
    assert np.abs(v).max() > 0.0
    # same key -> same noise; different decision_index -> different noise
    v_same = sa._decision_critic(3, 5, 1)(batch)
    v_diff = sa._decision_critic(3, 5, 2)(batch)
    np.testing.assert_allclose(v, v_same)
    assert np.abs(v - v_diff).max() > 0.0


def test_loo_mean_of_other_critics():
    sa = SearchAgent(
        _StubAgent(value=99.0), DOSES["S"], checkpoint_seed=7,
        evaluator={"kind": "loo", "agents": [_StubAgent(value=0.2),
                                             _StubAgent(value=0.6)]},
    )
    fn = sa._decision_critic(0, 5, 0)
    v = fn(np.zeros((4, 8), dtype=np.float32))
    np.testing.assert_allclose(v, np.full(4, 0.4), rtol=1e-6)  # own 99 unused


def test_oppact_uniform_substitutes_q_but_records_real_entropy(monkeypatch):
    peaked = np.array([8.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    captured = {}
    real_solve = agent_mod.solve_decision

    def spy(battle, mask, q, prior, dose, rng, critic_fn, type_chart, det_fn=None):
        captured["q"] = q.copy()
        return real_solve(battle, mask, q, prior, dose, rng, critic_fn,
                          type_chart, det_fn=det_fn)

    monkeypatch.setattr(agent_mod, "solve_decision", spy)
    sa = SearchAgent(
        _StubAgent(q_logits=peaked), DOSES["S"], checkpoint_seed=7,
        evaluator={"kind": "oppact_uniform"},
    )
    _act(sa)
    np.testing.assert_allclose(captured["q"], np.full(N_L6, 1 / N_L6))
    # entropy recorded from the REAL peaked head, far below ln(6)
    assert sa.entropy_median() < 0.5 * np.log(N_L6)


def test_evaluator_spec_validated():
    with pytest.raises(AssertionError):
        SearchAgent(_StubAgent(), DOSES["S"], 7, evaluator={"kind": "bogus"})
    with pytest.raises(AssertionError):
        SearchAgent(_StubAgent(), DOSES["S"], 7,
                    evaluator={"kind": "noise", "sigma": 0.0})
    with pytest.raises(AssertionError):
        SearchAgent(_StubAgent(), DOSES["S"], 7,
                    evaluator={"kind": "loo", "agents": []})


def test_fg4_oracle_provenance_gated(monkeypatch):
    from rl.search import bridge
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization

    b = _two_mon_battle()
    det = sample_determinization(b, np.random.default_rng(1))
    for spec in det["opponents"].values():
        spec["provenance"] = "oracle"
    with pytest.raises(AssertionError):
        battle_to_state(b, det, BridgeCounters())
    monkeypatch.setattr(bridge, "_FG4_DISARMED", True)
    battle_to_state(b, det, BridgeCounters())  # passes under the disarm
    # and a random-junk provenance never passes, disarmed or not
    for spec in det["opponents"].values():
        spec["provenance"] = "handcrafted"
    with pytest.raises(AssertionError):
        battle_to_state(b, det, BridgeCounters())

"""GOLDEN VALUES for the tree's decision, so "did my edit change the search?"
is answerable in one second instead of by argument.

WHY THIS FILE EXISTS. On 2026-09-18, while a four-arm tree block was running,
this session edited `agent.py`, `matrix.py` and `ensemble_search.py` -- files
every arm imports. TV had already run; TG/TQ/TGR had not. The edits were
believed to be no-ops on the tree path, and they were (checked by running this
fixture against the pre-edit tree out of `git archive`, and confirming the
action, every decision stat and every pre-existing counter were bit-identical;
only wall-clock `tree/ms_*` differed, and the arms are ITERATION-bounded, not
time-bounded, so that cannot change what is searched). The check should not
have needed a git archive. These are the numbers it produced.

The values below are NOT meaningful in themselves -- the agent is a stub and
the battle is a two-mon fixture. What is meaningful is that they do not MOVE.
A change here is not automatically a bug; it means the tree now decides
differently, and any in-flight block comparing arms across that change is
comparing two algorithms.
"""
import numpy as np
import pytest
import torch

from rl.search.agent import SearchAgent
from rl.search.matrix import DOSES, N_L6
from tests.test_ch3_matrix import _mask, _two_mon_battle

TREES = {
    "visits": {"decide": "visits", "iters": 48, "n_det": 2, "batch": 8},
    "q": {"decide": "q", "iters": 48, "n_det": 2, "batch": 8, "margin": 0.20},
    "gumbel": {"decide": "gumbel", "iters": 48, "n_det": 2, "batch": 8},
}

GOLDEN = {
    "visits": (9, {
        "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
        "search/leaves": 92.0, "search/overrode": 1.0,
        "search/policy_argmax": 8.0, "tree/argmax": 9.0, "tree/evals": 92.0,
        "tree/gap": 0.2291666667, "tree/max_depth": 3.0,
        "tree/mean_sim_depth": 1.5, "tree/q_best": 0.0, "tree/q_policy": 0.0,
        "tree/root_q_best": 0.3843762961, "tree/share_best": 0.46875,
        "tree/share_policy": 0.2395833333, "tree/transition_failures": 0.0}),
    "q": (9, {
        "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
        "search/leaves": 92.0, "search/overrode": 1.0,
        "search/policy_argmax": 8.0, "tree/argmax": 9.0, "tree/evals": 92.0,
        "tree/gap": 0.8192121631, "tree/max_depth": 3.0,
        "tree/mean_sim_depth": 1.5, "tree/q_best": 0.3843762961,
        "tree/q_policy": -0.4348358671, "tree/root_q_best": 0.3843762961,
        "tree/share_best": 0.46875, "tree/share_policy": 0.2395833333,
        "tree/transition_failures": 0.0}),
    "gumbel": (9, {
        "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
        "search/leaves": 92.0, "search/overrode": 1.0,
        "search/policy_argmax": 8.0, "tree/beta": 4.0, "tree/evals": 92.0,
        "tree/max_depth": 3.0, "tree/mean_sim_depth": 1.5,
        "tree/q_spread": 1.1998435792, "tree/transition_failures": 0.0}),
}


class _Actor:
    def __init__(self, logits):
        self._l = torch.as_tensor(logits, dtype=torch.float32)

    def __call__(self, obs_t, return_features=True):
        if obs_t.ndim == 1:
            obs_t = obs_t.unsqueeze(0)
        return self._l.repeat(obs_t.shape[0], 1), obs_t


class _StubAgent:
    """Deterministic and NOT flat: a uniform policy or a constant critic would
    make every decide rule agree by accident and the fixture would pin nothing."""

    def __init__(self):
        rng = np.random.default_rng(11)
        self.actor = _Actor(rng.normal(size=10) * 0.7)
        self._q = rng.normal(size=N_L6) * 0.3

    def aux_head(self, feats):
        if feats.ndim == 1:
            feats = feats.unsqueeze(0)
        return torch.as_tensor(self._q, dtype=torch.float32).repeat(feats.shape[0], 1)

    def critic(self, t):
        if t.ndim == 1:
            t = t.unsqueeze(0)
        return torch.as_tensor(
            np.sin(np.asarray(t, dtype=np.float64).sum(axis=1) * 3.0),
            dtype=torch.float32)


@pytest.mark.parametrize("rule", sorted(TREES))
def test_the_tree_decides_exactly_what_it_decided_on_2026_09_18(rule):
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=112,
                     tree=TREES[rule])
    action, stats = sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32),
                           _mask(), 5, 2)
    want_action, want_stats = GOLDEN[rule]
    assert action == want_action
    got = {k: v for k, v in stats.items() if "/ms_" not in k}
    assert sorted(got) == sorted(want_stats), (
        f"the tree's stat SET changed: {sorted(set(got) ^ set(want_stats))}")
    for k in want_stats:
        assert got[k] == pytest.approx(want_stats[k], abs=1e-9, rel=1e-9), k


def test_the_three_rules_do_not_all_report_the_same_thing():
    """The fixture would pin nothing if the rules were indistinguishable on it."""
    seen = {r: GOLDEN[r][1] for r in GOLDEN}
    assert seen["q"]["tree/gap"] != seen["visits"]["tree/gap"]
    assert "tree/beta" in seen["gumbel"] and "tree/argmax" not in seen["gumbel"]


def test_wall_clock_is_deliberately_excluded():
    """`tree/ms_*` moves with machine load and pins nothing. It is excluded
    from the golden set on purpose, and that is only safe because the arms are
    ITERATION-bounded (`iters`), never time-bounded -- a time-bounded tree
    would search a different amount on a busy box."""
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=112,
                     tree=TREES["visits"])
    _, stats = sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32),
                      _mask(), 5, 2)
    assert [k for k in stats if "/ms_" in k], (
        "if the timing keys ever disappear, this exclusion is silently moot")
    assert "iters" in TREES["visits"] and "ms" not in TREES["visits"]

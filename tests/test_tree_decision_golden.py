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

# KEYED BY OBS_DIM, NOT BY ENV VAR. The tree encodes every leaf through
# `embed_battle`, so the ENCODER VERSION changes what it searches -- visits and
# gumbel pick a DIFFERENT ACTION under the two encoders on this fixture. The
# suite's documented invocation leaves POKEMON_RL_ENCODER_V2/_IDS UNSET (612),
# while every arm sets them (828), so a fixture pinned to one of them would
# either fail in the suite or pin nothing about the arms. Both are pinned.
GOLDEN = {
    828: {
        "visits": (9, {
            "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
            "search/leaves": 92.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/argmax": 9.0, "tree/evals": 92.0,
            "tree/gap": 0.2291666667, "tree/max_depth": 3.0,
            "tree/mean_sim_depth": 1.5, "tree/q_best": 0.0, "tree/q_policy": 0.0,
            "tree/root_q_best": 0.3843762961, "tree/share_best": 0.46875,
            "tree/share_policy": 0.2395833333, "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/gate_off": 0.0,
            "tree/kl_pi_prior": 0.6680381306,
            "tree/pi_entropy": 1.2084141311,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.46875,
            "tree/prior_top1": 0.382250705,}),
        "q": (9, {
            "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
            "search/leaves": 92.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/argmax": 9.0, "tree/evals": 92.0,
            "tree/gap": 0.8192121631, "tree/max_depth": 3.0,
            "tree/mean_sim_depth": 1.5, "tree/q_best": 0.3843762961,
            "tree/q_policy": -0.4348358671, "tree/root_q_best": 0.3843762961,
            "tree/share_best": 0.46875, "tree/share_policy": 0.2395833333,
            "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/gate_off": 0.0,
            "tree/kl_pi_prior": 0.6680381306,
            "tree/pi_entropy": 1.2084141311,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.46875,
            "tree/prior_top1": 0.382250705,}),
        "gumbel": (9, {
            "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
            "search/leaves": 92.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/beta": 4.0, "tree/evals": 92.0,
            "tree/max_depth": 3.0, "tree/mean_sim_depth": 1.5,
            "tree/q_spread": 1.1998435792, "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/kl_pi_prior": 0.6680381306,
            "tree/pi_entropy": 1.2084141311,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.46875,
            "tree/prior_top1": 0.382250705,}),
    },
    612: {
        "visits": (6, {
            "oppact/entropy": 1.7707760334, "search/chosen": 6.0,
            "search/leaves": 93.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/argmax": 6.0, "tree/evals": 93.0,
            "tree/gap": 0.21875, "tree/max_depth": 3.0,
            "tree/mean_sim_depth": 1.5520833333, "tree/q_best": 0.0,
            "tree/q_policy": 0.0, "tree/root_q_best": -0.073022709,
            "tree/share_best": 0.40625, "tree/share_policy": 0.1875,
            "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/gate_off": 0.0,
            "tree/kl_pi_prior": 0.255958894,
            "tree/pi_entropy": 1.3109701282,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.40625,
            "tree/prior_top1": 0.382250705,}),
        "q": (9, {
            "oppact/entropy": 1.7707760334, "search/chosen": 9.0,
            "search/leaves": 93.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/argmax": 9.0, "tree/evals": 93.0,
            "tree/gap": 0.5708767449, "tree/max_depth": 3.0,
            "tree/mean_sim_depth": 1.5520833333, "tree/q_best": -0.0280336696,
            "tree/q_policy": -0.5989104145, "tree/root_q_best": -0.0280336696,
            "tree/share_best": 0.2604166667, "tree/share_policy": 0.1875,
            "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/gate_off": 0.0,
            "tree/kl_pi_prior": 0.255958894,
            "tree/pi_entropy": 1.3109701282,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.40625,
            "tree/prior_top1": 0.382250705,}),
        "gumbel": (6, {
            "oppact/entropy": 1.7707760334, "search/chosen": 6.0,
            "search/leaves": 93.0, "search/overrode": 1.0,
            "search/policy_argmax": 8.0, "tree/beta": 4.0, "tree/evals": 93.0,
            "tree/max_depth": 3.0, "tree/mean_sim_depth": 1.5520833333,
            "tree/q_spread": 0.5708767449, "tree/transition_failures": 0.0,
            "tree/argmax_moved": 1.0,
            "tree/kl_pi_prior": 0.255958894,
            "tree/pi_entropy": 1.3109701282,
            "tree/pi_support": 4.0,
            "tree/pi_top1": 0.40625,
            "tree/prior_top1": 0.382250705,}),
    },
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
    from rl.envs.showdown import OBS_DIM
    assert OBS_DIM in GOLDEN, (
        f"no golden values for OBS_DIM {OBS_DIM}; the tree encodes every leaf, "
        "so a new encoder is a new search and needs its own row")
    want_action, want_stats = GOLDEN[OBS_DIM][rule]
    assert action == want_action
    got = {k: v for k, v in stats.items() if "/ms_" not in k}
    assert sorted(got) == sorted(want_stats), (
        f"the tree's stat SET changed: {sorted(set(got) ^ set(want_stats))}")
    for k in want_stats:
        assert got[k] == pytest.approx(want_stats[k], abs=1e-9, rel=1e-9), k


def test_the_three_rules_do_not_all_report_the_same_thing():
    """The fixture would pin nothing if the rules were indistinguishable on it."""
    from rl.envs.showdown import OBS_DIM
    seen = {r: GOLDEN[OBS_DIM][r][1] for r in TREES}
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


def test_the_expert_falsifier_is_computed_on_EVERY_decide_path():
    """IDEAS 4.9 dies or lives on KL(pi' || prior), and the gumbel rule returns
    from its own branch -- which is the arm that read +0.021 (RESULTS §26) and
    therefore the last one that should be missing the measurement."""
    from rl.envs.showdown import OBS_DIM
    for rule in TREES:
        sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=112,
                         tree=TREES[rule])
        _, stats = sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32),
                          _mask(), 5, 2)
        for k in ("tree/kl_pi_prior", "tree/pi_top1", "tree/prior_top1",
                  "tree/argmax_moved", "tree/pi_entropy"):
            assert k in stats, f"{rule} never reports {k}"
        assert 0.0 <= stats["tree/pi_top1"] <= 1.0
        assert stats["tree/kl_pi_prior"] >= -1e-12, "KL cannot be negative"


def test_argmax_moved_is_UNGATED_and_differs_from_overrode():
    """`search/overrode` asks whether a MARGIN let the search act.
    `tree/argmax_moved` asks whether the search HAS an opinion. Conflating them
    is the override-rate confound in a new place -- so a rule with no margin at
    all must still report whether its argmax moved."""
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=112,
                     tree=TREES["visits"])          # decide=visits, NO margin
    _, stats = sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32),
                      _mask(), 5, 2)
    assert "tree/argmax_moved" in stats
    assert stats["tree/argmax_moved"] in (0.0, 1.0)


def test_expert_stats_are_a_distribution_over_the_legal_actions():
    """Directly, on the helper: pi' must be normalised over LEGAL rows and the
    KL taken against the prior renormalised the same way, or the number is a
    comparison between a distribution and something that is not one."""
    from rl.search.tree import _expert_stats
    rows = [6, 7, 8, 9]
    share = {6: 0.5, 7: 0.25, 8: 0.25, 9: 0.0}
    prior = np.zeros(10); prior[rows] = [0.25, 0.25, 0.25, 0.25]
    st = _expert_stats(rows, share, prior)
    assert st["tree/pi_top1"] == pytest.approx(0.5)
    assert st["tree/pi_support"] == 3.0
    assert st["tree/argmax_moved"] == 0.0, "same argmax, ties to the lowest index"
    # KL of (.5,.25,.25,0) from uniform(4) = .5ln2 + .25ln1 + .25ln1 = 0.3466
    assert st["tree/kl_pi_prior"] == pytest.approx(0.5 * np.log(2.0), abs=1e-9)


def test_an_expert_identical_to_the_prior_reports_zero_kl():
    """THE KILL CASE for IDEAS 4.9: if the search's visit distribution IS the
    prior, training toward it is a no-op with extra compute."""
    from rl.search.tree import _expert_stats
    rows = [6, 7, 8]
    prior = np.zeros(10); prior[rows] = [0.5, 0.3, 0.2]
    st = _expert_stats(rows, {6: 0.5, 7: 0.3, 8: 0.2}, prior)
    assert st["tree/kl_pi_prior"] == pytest.approx(0.0, abs=1e-12)
    assert st["tree/argmax_moved"] == 0.0


def test_the_expert_counters_REACH_DISK_on_the_foul_play_path():
    """The rule this repo keeps paying for: a dial reaches the WRITER and not the
    COLLECTOR, runs, and reports nothing.

    It happened a third time on 2026-09-19. `tree/kl_pi_prior` and friends are
    per-DECISION stats; `scripts/ch3_eval.py` has aggregated `tree/` keys since
    2026-09-16 but `scripts/ch3_fp_h2h.py` only ever kept `ms` and `leaves`, so
    EVERY tree diagnostic ever produced off Foul Play was discarded -- and a
    45-minute mechanism screen came back empty. This reads the collector out of
    the source.
    """
    from pathlib import Path

    src = (Path(__file__).parent.parent / "scripts/ch3_fp_h2h.py").read_text()
    assert "self.probe" in src, "the FP seat does not collect per-decision stats"
    i = src.index("self.probe.setdefault")
    window = src[max(0, i - 700):i]
    for prefix in ("depth2", "tree", "bcts", "heuristic", "disagree"):
        assert f'"{prefix}"' in window, (
            f"the FP seat's probe filter drops {prefix}/* stats")
    assert "report[k] = float(sum(vals) / len(vals))" in src, (
        "the probe stats are collected and never written to the arm's JSON")

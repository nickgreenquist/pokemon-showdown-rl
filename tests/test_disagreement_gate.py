"""IDEAS 8.5 -- spend the search budget WHERE THE COMMITTEE IS SPLIT.

Every dose this project has measured raised the budget on EVERY decision,
which is why depth-2's 3.27x cost bought -0.0007 (RESULTS §22) and why the
ladder's ~150 s/turn is 99.99% unspent. The committee already computes, free,
on every decision, a signal for which decisions are actually close: 4.8's
credit rests on it (the committee overrides its first member on 10.8% of
decisions vs SH and 27.8% off FP@20).

These tests pin the two ends the dial has to have -- a gate at threshold 0.0
searches everything and is bit-identical to the ungated arm, a gate above
every score plays the greedy argmax -- the arithmetic of both metrics, and the
provenance without which a gated arm cannot be graded: a `search_rate` of 1.0
is a uniform-dose arm wearing a gated label, and 0.0 is greedy.
"""
from pathlib import Path

import numpy as np
import pytest
import torch

from rl.search.agent import SearchAgent
from rl.search.matrix import DOSES, N_L6
from tests.test_ch3_matrix import _mask, _two_mon_battle


class _Actor:
    """A stub actor that also carries per-member log-probs, the way
    `_EnsembleActor` does after `rl/search/ensemble_search.py` kept them."""

    def __init__(self, logits, member_logps=None):
        self._logits = torch.as_tensor(logits, dtype=torch.float32)
        self.last_member_logps = (
            None if member_logps is None
            else torch.log_softmax(
                torch.as_tensor(member_logps, dtype=torch.float32), dim=-1
            ).unsqueeze(1)          # (M, 1, A), the shape _forward produces
        )

    def __call__(self, obs_t, return_features=True):
        return self._logits.repeat(obs_t.shape[0], 1), obs_t


class _StubAgent:
    def __init__(self, logits=None, member_logps=None, members=None):
        self.actor = _Actor(np.zeros(10) if logits is None else logits,
                            member_logps)
        if members is not None:
            self.members = members

    def aux_head(self, feats):
        return torch.zeros((feats.shape[0], N_L6))

    def critic(self, t):
        return torch.zeros((t.shape[0],))


def _act(sa, battle_index=3, decision_index=1):
    return sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32), _mask(),
                  battle_index, decision_index)


def _committee(member_logps, logits=None):
    """A stub whose pooled prior is the log-pool of its members, matching
    `_EnsembleActor`: the mean of the members' log-softmax."""
    lp = torch.log_softmax(torch.as_tensor(member_logps, dtype=torch.float32),
                           dim=-1)
    return _StubAgent(logits=lp.mean(dim=0).numpy(), member_logps=member_logps,
                      members=[object()] * len(member_logps))


def _peak(i):
    """Logits peaked on action `i`. The peaks live at 6..9 because that is
    what `_mask()` makes LEGAL -- a peak on a masked action is invisible to
    every metric here, which is the point of masking."""
    v = [0.0] * 10
    v[i] = 5.0
    return v


AGREE = [_peak(6)] * 3
SPLIT = [_peak(6), _peak(6), _peak(7)]


# ------------------------------------------------------------ the two ends
def test_no_gate_is_the_default_and_leaves_every_counter_at_zero():
    sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7)
    a, stats = _act(sa)
    assert "search/leaves" in stats, "the ungated arm searches"
    assert sa.counters["disagree/eligible"] == 0
    assert sa._disagree is None


def test_threshold_zero_searches_everything_even_a_unanimous_committee():
    """`score < threshold` skips, so 0.0 can never skip: the gate's OFF end
    has to be reachable from a config without deleting the key."""
    sa = SearchAgent(_committee(AGREE), DOSES["S"], checkpoint_seed=7,
                     disagree={"metric": "votes", "threshold": 0.0})
    a, stats = _act(sa)
    assert "search/leaves" in stats
    assert sa.counters["disagree/eligible"] == 1
    assert sa.counters["disagree/searched"] == 1


def test_a_gate_above_every_score_plays_the_policy_argmax():
    ungated = SearchAgent(_committee(SPLIT), DOSES["S"], checkpoint_seed=7)
    gated = SearchAgent(_committee(SPLIT), DOSES["S"], checkpoint_seed=7,
                        disagree={"metric": "votes", "threshold": 1.0})
    _, u_stats = _act(ungated)
    a, stats = _act(gated)
    assert stats["disagree/skip"] == 1
    assert "search/leaves" not in stats, "a skipped decision is not searched"
    assert gated.counters["disagree/searched"] == 0
    assert a == u_stats["search/policy_argmax"], (
        "the skip must play exactly what the greedy object plays, or the "
        "gate's OFF end is a third policy nobody measured"
    )


# ------------------------------------------------------------- the metrics
@pytest.mark.parametrize("logps,expected", [
    (AGREE, 0.0),
    (SPLIT, 1 / 3),
    ([_peak(6), _peak(7), _peak(8)], 2 / 3),
])
def test_votes_is_the_fraction_of_members_off_the_pooled_argmax(logps, expected):
    sa = SearchAgent(_committee(logps), DOSES["S"], checkpoint_seed=7,
                     disagree={"metric": "votes", "threshold": 0.5})
    prior, _ = sa._forward(np.zeros(8, dtype=np.float32), _mask())
    assert sa._disagreement(prior, np.asarray(_mask())) == pytest.approx(expected)


def test_margin_reads_the_pooled_policys_own_confidence_and_needs_no_committee():
    """`margin` is the metric a SINGLE agent can use: no members, no votes."""
    flat = SearchAgent(_StubAgent(logits=np.zeros(10)), DOSES["S"],
                       checkpoint_seed=7,
                       disagree={"metric": "margin", "threshold": 0.5})
    peaked = SearchAgent(_StubAgent(logits=[0.0] * 6 + [20.0, 0.0, 0.0, 0.0]),
                         DOSES["S"],
                         checkpoint_seed=7,
                         disagree={"metric": "margin", "threshold": 0.5})
    m = np.asarray(_mask())
    flat_p, _ = flat._forward(np.zeros(8, dtype=np.float32), _mask())
    peak_p, _ = peaked._forward(np.zeros(8, dtype=np.float32), _mask())
    assert flat._disagreement(flat_p, m) == pytest.approx(1.0), (
        "a tie between the top two is maximally contested")
    assert peaked._disagreement(peak_p, m) < 0.01, (
        "a policy that is sure is not contested")


def test_one_legal_action_is_never_contested():
    sa = SearchAgent(_committee(SPLIT), DOSES["S"], checkpoint_seed=7,
                     disagree={"metric": "votes", "threshold": 0.01})
    prior, _ = sa._forward(np.zeros(8, dtype=np.float32), _mask())
    one = np.zeros(10, dtype=bool)
    one[0] = True
    assert sa._disagreement(prior, one) == 0.0, (
        "there is nothing to decide, and searching it is pure waste")


def test_votes_refuses_a_committee_of_one():
    """A one-member ensemble never disagrees with itself, so the gate would
    skip EVERY decision and the arm would silently be greedy."""
    with pytest.raises(AssertionError, match="committee"):
        SearchAgent(_StubAgent(members=[object()]), DOSES["S"],
                    checkpoint_seed=7,
                    disagree={"metric": "votes", "threshold": 0.5})


@pytest.mark.parametrize("bad", [
    {"metric": "entropy", "threshold": 0.5},
    {"metric": "margin", "threshold": 1.5},
    {"metric": "margin", "threshold": -0.1},
])
def test_a_malformed_gate_fails_at_construction_not_mid_battle(bad):
    with pytest.raises(AssertionError):
        SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=7, disagree=bad)


# ---------------------------------------------------------- the provenance
def test_the_gate_reaches_disk_before_it_gets_an_arm():
    root = Path(__file__).parent.parent
    agent = (root / "rl/search/agent.py").read_text()
    h2h = (root / "scripts/ch3_fp_h2h.py").read_text()
    ev = (root / "scripts/ch3_eval.py").read_text()
    for key in ("disagree/eligible", "disagree/searched", "disagree/score_sum"):
        assert key in agent, f"{key} is never counted"
        assert key in ev, f"{key} never survives the vs-SH merge"
    assert "disagree/search_rate" in h2h and "disagree/search_rate" in ev, (
        "the REALIZED rate is the whole provenance of a gated arm")
    assert 'report["search_disagree"]' in h2h, "the dial itself is not stamped"


def test_a_gated_decision_is_excluded_from_the_searched_denominator():
    """Every rate in the h2h report divides by `dec - skips`. A gate skip is
    not a placeholder skip, so without this a healthy gated arm reads VOID on
    `depth2/fired_rate` and its override_rate is diluted."""
    src = (Path(__file__).parent.parent / "scripts/ch3_fp_h2h.py").read_text()
    i = src.index("skips = ")
    block = src[i:i + 400]
    assert "disagree/eligible" in block and "disagree/searched" in block, (
        "the gate's skips are not folded into `skips`")

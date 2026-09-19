"""CLEANUP L9: `scripts/action_gap.py` ranks the top-2 from the LIVE observation and
mask, once per position -- never from a per-determinization shadow battle and
never from a privileged view. This pins the ranking contract of `top2_live`."""
import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from action_gap import top2_live  # noqa: E402


class _Member:
    def __init__(self, logits):
        self._l = torch.tensor(logits, dtype=torch.float32)

    def actor(self, t):
        return self._l.expand(t.shape[0], -1)


def test_top2_is_the_committee_ordering_over_legal_actions():
    m1 = _Member([0.0, 3.0, 2.0, 1.0, -1.0])
    m2 = _Member([0.0, 1.0, 3.0, 2.5, -1.0])
    obs = np.zeros(7, dtype=np.float32)
    # mean log-prob: a1 -1.52, a2 -1.02, a3 -1.77 (a4 illegal) -> (2, 1)
    assert top2_live([m1, m2], obs, np.array([1, 1, 1, 1, 0])) == (2, 1)
    # masking a1 out changes the runner-up, not the leader
    assert top2_live([m1, m2], obs, np.array([1, 0, 1, 1, 0])) == (2, 3)


def test_illegal_actions_never_enter_the_pair_and_forced_moves_have_no_pair():
    loud = _Member([10.0, 0.0, 0.0, 0.0, 0.0])
    obs = np.zeros(3, dtype=np.float32)
    # the illegal action 0 has the highest logit and must not appear; ties are stable
    assert top2_live([loud], obs, np.array([0, 1, 1, 0, 0])) == (1, 2)
    assert top2_live([loud], obs, np.array([0, 1, 0, 0, 0])) is None


def test_per_member_normalisation_cannot_reorder():
    # log-softmax over ALL actions vs over the legal subset differ by a per-member
    # constant; the pair must be identical either way (the committee's own argmax).
    m1 = _Member([5.0, 1.0, 0.5, 0.0])
    m2 = _Member([5.0, 0.0, 1.5, 0.2])
    obs = np.zeros(2, dtype=np.float32)
    mask = np.array([0, 1, 1, 1])
    pair = top2_live([m1, m2], obs, mask)
    lp = np.mean([torch.log_softmax(m._l[1:], -1).numpy() for m in (m1, m2)], axis=0)
    legal = np.array([1, 2, 3])
    expect = tuple(int(x) for x in legal[np.argsort(-lp, kind="stable")][:2])
    assert pair == expect

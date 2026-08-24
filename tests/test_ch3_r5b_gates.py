"""CH3 R5b BI-3 (offline gate harness) — unit gates. No server, no
checkpoints. The lane-level integration read is the smoke pipeline (BI-1
collect --smoke -> BI-2 distill --smoke -> BI-3 gates --smoke), which runs
against the live server before launch (B-3/B-10).

Pinned here:

* F-R: the independent recompute passes on honest data at 1e-9, and FAILS
  loudly when a stored target's chosen action is not search-scored;
* actor_read: argmax respects the mask (an illegal action can never be the
  argmax even when its raw logit is the largest) and the entropy is the
  masked-softmax entropy;
* the D-3 band arithmetic: a perfect distillation (a1 = 1, F = f_base)
  lands INSIDE the band — the r1 draft's [0.15, 0.55] failure mode stays
  dead;
* r5a flip-rate cross-check reads flips/searched off a final.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_r5b_gates as gates  # noqa: E402


def _dataset(n=600, a=10, seed=0):
    rng = np.random.default_rng(seed)
    mask = np.zeros((n, a), dtype=np.uint8)
    ev = np.full((n, a), np.nan, dtype=np.float32)
    chosen = np.zeros(n, dtype=np.int32)
    for i in range(n):
        legal = rng.choice(a, size=rng.integers(2, 5), replace=False)
        mask[i, legal] = 1
        ev[i, legal] = rng.normal(size=len(legal)).astype(np.float32)
        chosen[i] = rng.choice(legal)
    return {"row_ev": ev, "chosen": chosen, "mask": mask}


def test_f_r_recompute_within_1e9():
    data = _dataset()
    for tau in ("hard", "0.10", "0.50"):
        out = gates.f_r_check(data, tau)
        assert out["max_abs_err"] <= 1e-9


def test_f_r_fails_on_unscored_chosen():
    data = _dataset()
    bad = 3
    data["chosen"][:] = data["chosen"]  # keep dtype
    ev = data["row_ev"]
    # make row `bad`'s chosen action unscored
    data["chosen"][bad] = int(np.flatnonzero(np.isnan(ev[bad]))[0])
    with pytest.raises(AssertionError, match="F-R"):
        gates.f_r_check(data, "0.10")


class _RawActor(torch.nn.Module):
    """Constant raw logits, largest on action 0."""

    def __init__(self, a=4):
        super().__init__()
        self.base = torch.arange(a, 0, -1).float()  # [a, a-1, ..., 1]

    def forward(self, x):
        return self.base.expand(len(x), -1)


def test_actor_read_masks_argmax_and_entropy():
    actor = _RawActor(4)
    obs = torch.zeros(5, 3)
    mask = torch.tensor([[0, 1, 1, 0]] * 5, dtype=torch.bool)
    picks, ent = gates.actor_read(actor, obs, mask)
    assert picks.tolist() == [1] * 5  # action 0 is illegal despite max logit
    # entropy of softmax([3, 2]) over the two legal actions
    p = torch.softmax(torch.tensor([3.0, 2.0]), dim=0)
    want = float(-(p * p.log()).sum())
    assert abs(ent - want) < 1e-6


def test_d3_band_admits_perfect_distillation():
    a0 = 0.402
    f_base = 1.0 - a0
    hi = f_base + gates.D3_TOL
    # perfect student: flips exactly where X0 disagreed with search
    assert gates.D3_LO <= f_base <= hi


def test_r5a_flip_rate_read(tmp_path, monkeypatch):
    d = tmp_path / "r5a"
    d.mkdir()
    (d / "ts_s62.final.json").write_text(json.dumps(
        {"search/searched_decisions": 20000, "search/flips": 8100}))
    monkeypatch.setattr(gates, "R5A_DIR", str(d))
    assert gates.r5a_selfplay_flip_rate("s62") == pytest.approx(0.405)
    assert gates.r5a_selfplay_flip_rate("s63") is None

"""Would every arm of `configs/eval/backup_gate_r5.yaml` actually CONSTRUCT?

A block costs hours and its arms are launched one at a time over a night, so an
arm whose kwargs `SearchAgent` rejects fails at 3am on a real username pair --
and a killed arm's pair is poisoned for hours (CLAUDE.md foul-play ops). Every
assert in `SearchAgent.__init__` is cheap and offline; this fires all of them
before the queue does.

It also pins the two PIN PLACEHOLDERS. `margin_delta: PINB` is a STRING until
`scripts/backup_gate_pin.py` writes a float over it, so a typo there would be
indistinguishable from a resolved value right up until `float()` raised.
"""
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from rl.search.agent import SearchAgent
from rl.search.matrix import DOSES, N_L6

CFG = yaml.safe_load(
    (Path(__file__).parent.parent / "configs/eval/backup_gate_r5.yaml").read_text())
PINS = {"PINB", "PIND"}


class _Actor:
    def __init__(self):
        self.last_member_logps = torch.log_softmax(
            torch.zeros((3, 1, 10)), dim=-1)

    def __call__(self, obs_t, return_features=True):
        if obs_t.ndim == 1:
            obs_t = obs_t.unsqueeze(0)
        return torch.zeros((obs_t.shape[0], 10)), obs_t


class _Committee:
    """Three members, because `votes` refuses a committee of one and every arm
    here carries `ensemble_members: [w104, w112, w120]`."""

    members = [object(), object(), object()]

    def __init__(self):
        self.actor = _Actor()

    def aux_head(self, feats):
        if feats.ndim == 1:
            feats = feats.unsqueeze(0)
        return torch.zeros((feats.shape[0], N_L6))

    def critic(self, t):
        if t.ndim == 1:
            t = t.unsqueeze(0)
        return torch.zeros((t.shape[0],))


def _search_arms():
    return {k: v for k, v in CFG["arms"].items() if v["kind"] == "search_seat"}


@pytest.mark.parametrize("name", sorted(_search_arms()))
def test_every_search_arm_constructs(name):
    arm = _search_arms()[name]
    md = arm.get("margin_delta")
    assert isinstance(md, (int, float)) or md in PINS, (
        f"{name}: margin_delta {md!r} is neither a number nor a known pin token")
    disagree = arm.get("disagree")
    if disagree and disagree.get("threshold") in PINS:
        disagree = dict(disagree, threshold=0.5)   # the pin writes a float here
    sa = SearchAgent(
        _Committee(), DOSES[arm["dose"]], checkpoint_seed=112,
        margin_delta=(md if isinstance(md, (int, float)) else 0.05),
        depth2=arm.get("depth2"), disagree=disagree)
    assert sa._disagree == disagree
    assert sa._depth2 == arm.get("depth2")


def test_the_pin_tokens_in_the_config_are_exactly_the_ones_the_pin_writes():
    """A placeholder the pin does not recognise is a silent no-op: the queue's
    `grep -q PINB\\|PIND` would still fire, the pin would replace nothing, and
    the assert inside it is the only thing standing between that and an arm
    launched with a string margin."""
    text = (Path(__file__).parent.parent
            / "configs/eval/backup_gate_r5.yaml").read_text()
    pin = (Path(__file__).parent.parent
           / "scripts/backup_gate_pin.py").read_text()
    for token in PINS:
        assert f"margin_delta: {token}" in text or f"threshold: {token}" in text, (
            f"{token} is written by the pin but appears nowhere in the config")
        assert token in pin
    assert 'assert "PINB" not in out and "PIND" not in out' in pin, (
        "the pin must refuse to finish with a placeholder still in the file")


def test_the_two_gated_arms_carry_the_bigger_dose_and_the_ungated_one_does_not():
    """The 8.5 comparison is matched on COMPUTE by construction: dose L is 4x M
    on n_det, so ~25% of decisions at L costs what 100% at M costs. If the doses
    ever drift apart, DGV - DUM stops being a spend-it-here vs spread-it
    comparison and becomes a dose comparison."""
    arms = CFG["arms"]
    assert arms["DGV"]["dose"] == arms["DRV"]["dose"] == "L"
    assert arms["DUM"]["dose"] == arms["D1O"]["dose"] == "M"
    assert DOSES["L"].n_det == 4 * DOSES["M"].n_det


def test_d1o_and_dum_are_the_same_configuration_on_different_pairs():
    """They are the block's in-session replicate -- the realized noise floor
    every other delta is read against. If they ever stop matching, the readout's
    'noise floor' line becomes a comparison of two different arms."""
    a, b = CFG["arms"]["D1O"], CFG["arms"]["DUM"]
    keys = ("kind", "seat", "ensemble_members", "dose", "margin_delta",
            "battles", "search_time_ms")
    assert {k: a.get(k) for k in keys} == {k: b.get(k) for k in keys}
    assert a.get("depth2") is None and b.get("depth2") is None
    assert a.get("disagree") is None and b.get("disagree") is None
    assert a["seat_username"] != b["seat_username"]


def test_the_old_backup_arm_really_asks_for_the_old_backup():
    """B2O exists so 'the fix helps' is a SAME-SESSION delta. If it drifted to
    opp_k 2 it would be a copy of B2R and the comparison would vanish."""
    assert CFG["arms"]["B2O"]["depth2"]["opp_k"] == 1
    assert CFG["arms"]["B2R"]["depth2"]["opp_k"] == 2
    for name in ("B2A", "B2B", "B2C"):
        assert CFG["arms"][name]["depth2"]["opp_k"] == 2, (
            f"{name} sweeps the delta FOR B2R, so it must run B2R's backup")

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


def test_the_pin_tokens_and_the_pin_script_agree():
    """A placeholder the pin does not recognise is a silent no-op: the queue's
    `grep -q PINB\\|PIND` would still fire, the pin would replace nothing, and
    the assert inside the pin is the only thing standing between that and an arm
    launched with a string margin.

    THE CONFIG IS CHECKED IN BOTH STATES, because the pin REWRITES it in place
    and commits: before the pin the tokens are present, after it every arm
    carries a float. Asserting only the first state made this test go red the
    moment the running block pinned itself, which is a test describing a
    transient rather than a contract."""
    text = (Path(__file__).parent.parent
            / "configs/eval/backup_gate_r5.yaml").read_text()
    pin = (Path(__file__).parent.parent
           / "scripts/backup_gate_pin.py").read_text()
    for token in PINS:
        assert token in pin, f"the pin does not know its own token {token}"
    assert 'assert "PINB" not in out and "PIND" not in out' in pin, (
        "the pin must refuse to finish with a placeholder still in the file")
    pinned = not any(t in text for t in PINS)
    if pinned:
        # post-pin: every value the pin writes must now be a real number
        for name in ("B2R", "DRV"):
            arm = CFG["arms"][name]
            assert isinstance(arm["margin_delta"], (int, float)), name
            if arm.get("disagree"):
                assert isinstance(arm["disagree"]["threshold"], (int, float)), name
    else:
        assert any(f"margin_delta: {t}" in text or f"threshold: {t}" in text
                   for t in PINS), "tokens present but on no arm the pin writes"


def test_every_gate_arm_carries_THE_SAME_dose():
    """The 8.5 comparison holds the dose FIXED so the only difference between
    DGV and DUM is WHICH decisions were searched.

    The original design put the gated arms at dose L on the arithmetic that
    ~25% of decisions at L costs what 100% at M costs. The smoke measured the
    rate at 45.2%, which would have made DGV cost ~1.8x DUM and confounded the
    comparison with COMPUTE -- and with three members `votes` takes only
    {0, 1/3, 2/3}, so there is no knob to tune the rate back. If these doses
    ever drift apart again, the arms stop being the same search."""
    arms = CFG["arms"]
    doses = {arms[a]["dose"] for a in ("DGV", "DRV", "DUM", "GV", "D1O")}
    assert doses == {"M"}, f"the gate arms disagree on dose: {doses}"
    # and the dose ladder still means what the header says it does
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


def test_the_readout_runs_on_a_partial_block():
    """A readout is called ONCE, at 04:00, after nine hours of arms -- so a
    NameError in it costs the whole night's turnaround.

    This caught a real one on 2026-09-18: a local named `g` inside `main()`
    shadowed the module-level `g()` that loads an arm's JSON, and the readout
    died on its first line. Running it against the live (partial) results
    directory is the cheapest possible guard and it exercises every branch that
    a missing arm reaches.
    """
    import importlib.util
    import io as _io
    from contextlib import redirect_stdout

    spec = importlib.util.spec_from_file_location(
        "backup_gate_readout",
        Path(__file__).parent.parent / "scripts/backup_gate_readout.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = _io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue()
    assert "THE BAR IS GREEDY" in out
    assert "R0 GATES" in out

"""L7 (2026-09-19): a declared dial must REACH the object it configures.

Seven defects this week shared one shape -- a dial or a counter that runs and
reports nothing, or reports the wrong thing.  `scripts/ch3_eval.py` carried the
purest instance: it forwarded a HARDCODED list of SearchAgent dials, so every
dial added to SearchAgent afterwards (`disagree`, `calibration`) was accepted in
a pre-reg, silently dropped, and the arm ran as an unmodified CONTROL while its
readout claimed the dial.  These tests pin the structural repair.
"""
import importlib.util
import inspect

import numpy as np
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ch3_eval():
    spec = importlib.util.spec_from_file_location(
        "ch3_eval_under_test", ROOT / "scripts" / "ch3_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_SearchAgent_dial_is_forwarded_by_the_harness():
    """The set is DERIVED, so adding a dial to SearchAgent cannot desync it."""
    from rl.search.agent import SearchAgent
    m = _ch3_eval()
    structural = {"self", "agent", "dose", "checkpoint_seed",
                  "battle_format", "det_fn", "evaluator"}
    expected = {p for p in inspect.signature(SearchAgent.__init__).parameters
                if p not in structural}
    assert set(m._SEARCH_DIALS) == expected
    # the two that were actually dropped in the wild
    assert {"disagree", "calibration"} <= set(m._SEARCH_DIALS)


def test_a_declared_dial_lands_in_the_job():
    m = _ch3_eval()
    arm = {"kind": "search", "lanes": ["w104"], "dose": "M",
           "disagree": {"metric": "votes", "frac": 0.5},
           "calibration": "results/iso.json",
           "depth2": {"opp_k": 3}}
    job = next(iter(m._jobs({"arms": {"X": arm}}).values()))
    for dial in ("disagree", "calibration", "depth2"):
        assert job[dial] == arm[dial], f"{dial} did not reach the job"


def test_an_absent_dial_is_None_so_the_arm_stays_bit_identical():
    m = _ch3_eval()
    job = next(iter(m._jobs(
        {"arms": {"X": {"kind": "search", "lanes": ["w104"], "dose": "M"}}}
    ).values()))
    for dial in m._SEARCH_DIALS:
        assert job[dial] is None, dial


def test_an_unrecognised_key_HARD_FAILS_instead_of_being_dropped():
    """The whole defect was a silent drop.  A typo must stop the run."""
    m = _ch3_eval()
    for typo in ("calibraton", "disagre", "depth_2", "leafencoding"):
        with pytest.raises(AssertionError, match="does not forward"):
            m._jobs({"arms": {"X": {"kind": "search", "lanes": ["w104"],
                                    "dose": "M", typo: {}}}})


def test_every_banked_prereg_still_parses():
    """The guard must not reject configs a SIBLING harness reads off the same
    file (ch3_fp_h2h's `fp_username`, ladder.py's `display_name`, ...)."""
    import yaml
    m = _ch3_eval()
    seen = 0
    for f in sorted((ROOT / "configs").rglob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text())
        except Exception:
            continue
        if not isinstance(d, dict) or not isinstance(d.get("arms"), dict):
            continue
        if not all(isinstance(v, dict) and "kind" in v
                   for v in d["arms"].values()):
            continue
        seen += 1
        try:
            m._jobs(d)
        except AssertionError as e:            # the guard, not a missing key
            pytest.fail(f"{f.name}: {e}")
        except Exception:
            pass                                # unrelated shape, not our job
    assert seen >= 20, f"only {seen} pre-regs exercised -- did the glob break?"


def test_tree_flags_a_gate_that_could_never_fire():
    """`margin: null` makes the tree branch greedy BY CONSTRUCTION: the leaves
    are paid for and the policy argmax is played regardless.  Without the flag,
    'acts 0%' is indistinguishable from 'the tree agreed'.

    THE FIRST VERSION OF THIS TEST CERTIFIED NOTHING (found by review,
    2026-09-19): it asserted the literal source string
    `'"tree/gate_off": float(cfg.margin is None)' in src`, which SURVIVES
    COMMENTING THE EMISSION OUT -- the substring is still in the file, now
    inside a comment.  A grep is not a test.  This version RUNS the decision at
    `margin=None` and asserts the flag's value and the greedy behaviour it
    names.
    """
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES
    from rl.search.tree import TreeCfg
    from tests.test_tree_decision_golden import (  # the pinned stub fixture
        TREES, _StubAgent, _mask, _two_mon_battle,
    )
    assert TreeCfg().margin == 0.10, "the default must stay LIVE"

    def run(margin):
        cfg = dict(TREES["visits"])
        cfg["margin"] = margin
        sa = SearchAgent(_StubAgent(), DOSES["S"], checkpoint_seed=112, tree=cfg)
        return sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32),
                      _mask(), 5, 2)

    _, s_on = run(0.10)
    assert s_on["tree/gate_off"] == 0.0, "a LIVE gate must report gate_off 0"

    a_off, s_off = run(None)
    assert s_off["tree/gate_off"] == 1.0, (
        "margin=None makes the branch greedy by construction and MUST say so"
    )
    assert s_off["search/overrode"] == 0, "a dead gate can never override"
    assert a_off == s_off["search/policy_argmax"], (
        "margin=None must play the POLICY argmax whatever the tree found"
    )
    # and the tree really did run -- the leaves were paid for
    assert s_off["search/leaves"] > 0


def test_a_native_seat_arm_is_refused_here_so_its_lop_can_never_be_dropped():
    """`lop` is tolerated as a SIBLING key (ch3_fp_h2h's native_seat forwards it
    through the signature-derived `lop_from`). That is safe only because this
    harness refuses the kind outright: a native_seat arm can never run here as
    a control while its readout claims the L-op."""
    m = _ch3_eval()
    with pytest.raises(ValueError, match="unknown arm kind 'native_seat'"):
        m._jobs({"arms": {"G": {"kind": "native_seat", "seat": "w", "ensemble_members": ["w"],
                                "battles": 2, "lop": {"worlds": 8}}}})
    # the native TREE's arm (DEEP SEARCH Step A): its `tree_lop` block is the same kind of sibling key
    with pytest.raises(ValueError, match="unknown arm kind 'native_tree_seat'"):
        m._jobs({"arms": {"T": {"kind": "native_tree_seat", "seat": "w", "ensemble_members": ["w"],
                                "battles": 2, "tree_lop": {"worlds": 8, "tree": {"sims": 100}}}}})

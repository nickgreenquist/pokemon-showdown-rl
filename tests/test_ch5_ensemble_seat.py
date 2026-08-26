"""CH5 R1 BUILD — the ensemble seat in scripts/ch3_fp_h2h.py. Offline only.

Why this seat had to exist at all: the arm that played LADDER R1 is
`kind: ensemble` in `ladder.py`'s POLICY_KINDS, and `ch3_fp_h2h.py` asserts
`arm["kind"] in ARM_KINDS` — a DIFFERENT namespace with no ensemble member.
So the one policy this project has a real-humans rating for could not be
measured off-SH at all. What is pinned here:

* the registered kind set grew by exactly one, and only alongside CHAPTER5;
* `seat` and `lanes` are MUTUALLY EXCLUSIVE in both directions — `seat`
  defaults to "s65", so an ensemble arm missing its lanes would otherwise
  have silently rated a single lane and reported it as the ensemble;
* duplicate lanes are refused (a repeated member reweights the log-prob
  mean without changing the arm's declared identity);
* `_native_dim` recurses into an ensemble instead of falling through to
  OBS_DIM, so a mixed-width ensemble cannot produce a fictional G8 stamp;
* the seat builds its members in the SAME ORDER the arm declares, which is
  what makes "this is the object that laddered" checkable rather than
  asserted.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ch3_fp_h2h  # noqa: E402

PINS = {f"s{i}": {"path": f"/nonexistent/{i}.pt", "sha256": f"{i:064d}"}
        for i in (62, 63, 64, 65)}


def _arm(**kw):
    base = {"kind": "ensemble_seat", "battles": 1,
            "seat_username": "u", "fp_username": "v"}
    base.update(kw)
    return {"checkpoints": PINS, "arms": {"A": base}}


class _FakeActor:
    def __init__(self, in_dim):
        self.in_dim = in_dim


class _FakeAgent:
    def __init__(self, tag, in_dim=828):
        self.tag = tag
        self.actor = _FakeActor(in_dim)
        self.obs_rank = 1


def test_ensemble_seat_is_registered():
    """Grows only alongside a pre-registration — CH5 R1 is the licence."""
    assert ch3_fp_h2h.ARM_KINDS == (
        "greedy_seat", "search_seat", "sampled_seat", "fp_vs_clone",
        "ensemble_seat")


def test_ensemble_arm_carrying_seat_fails_loudly():
    """`seat` defaults to s65: without this assert the arm rates ONE lane."""
    prereg = _arm(lanes=["s62", "s63"], seat="s65")
    with pytest.raises(AssertionError, match="not `seat`"):
        asyncio.run(ch3_fp_h2h.run(prereg, "A", 1, "t"))


def test_non_ensemble_arm_carrying_lanes_fails_loudly():
    prereg = _arm(kind="greedy_seat", lanes=["s62", "s63"])
    with pytest.raises(AssertionError, match="ensemble_seat-only"):
        asyncio.run(ch3_fp_h2h.run(prereg, "A", 1, "t"))


def test_duplicate_lanes_refused():
    prereg = _arm(lanes=["s62", "s62", "s63"])
    with patch.object(ch3_fp_h2h, "_build_agent", lambda spec: _FakeAgent("x")):
        with pytest.raises(AssertionError, match="duplicate lane"):
            asyncio.run(ch3_fp_h2h.run(prereg, "A", 1, "t"))


def test_empty_lanes_refused():
    prereg = _arm(lanes=[])
    with pytest.raises(AssertionError, match="at least one lane"):
        asyncio.run(ch3_fp_h2h.run(prereg, "A", 1, "t"))


def test_members_are_built_in_declared_order():
    """Lane ORDER is provenance: ladder.py builds `[_load(x) for x in lanes]`,
    so a seat that reordered would rate a different object than L2 — even
    though the log-prob mean is order-invariant, the report's sha list is
    what a reader checks the two runs against."""
    seen = []

    def fake(spec):
        seen.append(spec["path"])
        return _FakeAgent(spec["path"])

    class _Stop(Exception):
        pass

    def no_network(*a, **kw):
        # SeatPlayer's ctor opens a websocket; stop the run the instant the
        # members are built, so this test never touches a server.
        raise _Stop

    lanes = ["s64", "s62", "s65", "s63"]
    prereg = _arm(lanes=lanes)
    with patch.object(ch3_fp_h2h, "_build_agent", fake), \
         patch.object(ch3_fp_h2h, "SeatPlayer", no_network):
        with pytest.raises(_Stop):
            asyncio.run(ch3_fp_h2h.run(prereg, "A", 1, "t"))
    assert seen == [PINS[x]["path"] for x in lanes]


class TestNativeDim:
    def test_recurses_into_an_ensemble(self):
        from rl.search.ensemble import EnsembleAgent
        ens = EnsembleAgent([_FakeAgent("a", 828), _FakeAgent("b", 828)])
        assert ch3_fp_h2h._native_dim(ens) == 828

    def test_mixed_width_ensemble_refuses_to_stamp(self):
        """The 808 clone is a real object in this repo, so a mixed ensemble
        is reachable; before CH5 this fell through to OBS_DIM and stamped a
        width no member actually had."""
        from rl.search.ensemble import EnsembleAgent
        ens = EnsembleAgent([_FakeAgent("a", 828), _FakeAgent("b", 808)])
        with pytest.raises(AssertionError, match="disagree on input width"):
            ch3_fp_h2h._native_dim(ens)

    def test_single_agent_path_unchanged(self):
        assert ch3_fp_h2h._native_dim(_FakeAgent("a", 808)) == 808

"""The cross-block table must never manufacture a cross-session comparison.

`scripts/search_meta.py` is the one artifact that puts every Foul Play block
side by side, which is exactly the shape the ~0.02 session offset punishes. Two
things therefore have to hold and are tested here: a delta is only ever taken
against an arm's OWN block anchor, and an arm from before the 2026-09-17 dose
stamp is still recognised as a search arm rather than labelled GREEDY.
"""
import importlib.util
from pathlib import Path

MOD = Path(__file__).parent.parent / "scripts/search_meta.py"
spec = importlib.util.spec_from_file_location("search_meta", MOD)
sm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sm)


def test_an_unstamped_dose_does_not_turn_a_search_arm_into_a_greedy_one():
    """`search_dose` was not stamped on this path until 2026-09-17, so every
    arm before then has a null dose. Labelling those GREEDY would put a searched
    arm in the anchor column -- the 2026-09-11 VOID defect one layer up."""
    assert sm.vehicle({"search_dose": None, "search_margin_delta": 0.10}) == "matrix d1"
    assert sm.vehicle({"search_dose": None, "search/override_rate": 0.07}) == "matrix d1"
    assert sm.vehicle({"search_dose": None}) == "GREEDY"
    assert sm.vehicle({}) == "GREEDY"


def test_each_vehicle_is_named_from_its_own_stamp():
    assert sm.vehicle({"search_tree": {"decide": "gumbel"}}) == "tree/gumbel"
    assert sm.vehicle({"search_depth2": {"opp_k": 2}}) == "matrix d2 (opp_k 2)"
    assert sm.vehicle({"search_depth2": {}}) == "matrix d2 (opp_k 1)"
    assert sm.vehicle({"search_heuristic": {"kind": "fp_gen1"}}) == "matrix d1 FP-eval"
    assert sm.vehicle({"search_disagree": {"metric": "votes"}}) == "matrix+gate:votes"


def test_a_tree_arms_override_rate_falls_back_to_flips():
    """A tree reports no `search/override_rate` -- the field is gated on the
    matrix's margin_delta -- and taking that None at face value blocked a pin
    for four hours on 2026-09-18."""
    assert sm.override({"search/override_rate": 0.19}) == 0.19
    r = sm.override({"search/decisions": 1000, "search/placeholder_skips": 100,
                     "search/flips": 90})
    assert r == 0.10
    assert sm.override({"search/decisions": 0}) != sm.override({"search/decisions": 0})


def test_every_block_declares_its_own_anchor_or_declares_it_has_none():
    """A block whose anchor tag silently missed would compare its arms to
    nothing, or worse, to another block's greedy."""
    for rel, anchor, label in sm.BLOCKS:
        assert isinstance(rel, str) and rel.startswith("results/")
        assert anchor is None or isinstance(anchor, str)
        assert label
    withheld = [b for b in sm.BLOCKS if b[1] is None]
    assert withheld, "at least one block genuinely has no anchor (fp500_r5)"

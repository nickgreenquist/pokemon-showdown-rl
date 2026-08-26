"""CH5 R1 pre-registration — self-consistency gates. No server, no battles.

Review 2's MAJOR was that r2's entire grading apparatus lived in YAML
COMMENTS, so nothing could check it. CH4 duplicated every constant into
real keys; r3 does the same and this file is what makes that worth doing:
the numbers in `grading:` are re-derived here from the banked comparator
rather than trusted.

The r1 draft failed on exactly the class these tests cover — a bar quoted
in one section that did not follow the formula stated in another, and an
n whose 2*se_diff silently breached the file's own credit floor.
"""

import math
from pathlib import Path

import pytest
import yaml

PREREG = Path(__file__).resolve().parents[1] / "configs/eval/ch5_r1_offsh.yaml"
CFG = yaml.safe_load(PREREG.read_text())
G = CFG["grading"]
P0 = 0.34867          # banked 12M greedy off FP@20
N0 = 12000


def se(p, n):
    return math.sqrt(p * (1 - p) / n)


def test_comparator_matches_the_banked_arms():
    c = CFG["comparators"]["greedy_12m_fp20"]
    assert c["value"] == pytest.approx(P0, abs=1e-5)
    assert c["n"] == N0 and c["lanes"] == 4 and c["budget"] == "FP@20"


def test_every_verdict_cell_has_an_action():
    """O-1. Nine (VERDICT-S x VERDICT-P) cells; r2 had zero actions."""
    text = PREREG.read_text()
    for s_ in ("ABOVE", "WITHIN", "BELOW"):
        for p_ in ("RESOLVING", "WEAK", "NON-RESOLVING"):
            assert f"{s_}  x {p_}" in text or f"{s_} x {p_}" in text, f"{s_} x {p_} unrouted"


def test_flat_is_licensed_in_exactly_one_cell():
    assert G["flat_licensed_only_in"] == ["WITHIN x RESOLVING"]


def test_r1c_bar_follows_from_its_own_n():
    """O-2. Each composition vs C0, both single arms at n=3000."""
    a = G["arms"]["R1C"]
    expect = 2 * math.sqrt(2) * se(P0, a["n_per_arm"])
    assert a["bar"] == pytest.approx(expect, abs=5e-4)
    assert a["bar"] < G["credit_floor"], "a bar above the credit floor cannot grade"


def test_c0_n_meets_the_credit_floor():
    """BL-3: r2 cut C0 to 1500, where 2*se_diff = 0.0261 breaches 0.025."""
    n = CFG["arms"]["C0"]["battles"]
    two_se = 2 * math.hypot(se(P0, n), se(P0, N0))
    assert two_se < G["credit_floor"], f"C0 at n={n} gives 2*se_diff {two_se:.4f}"


def test_clustered_rule_is_k_general_and_undefined_at_one_lane():
    """O-3: r2 hardcoded /3, understating the se by 22% at k=2."""
    assert "k_arm" in G["clustered_formula"] and "/3" not in G["clustered_formula"]
    assert G["clustered_undefined_at_k"] == 1


def test_reachability_cliff_is_internally_consistent():
    """O-4: each row's required fleet mean must equal comparator + bar."""
    cliff = G["above_reachability_cliff"]
    for key, row in cliff.items():
        if not isinstance(row, dict):
            continue
        assert row["fleet_mean_above_needs"] == pytest.approx(P0 + row["bar"], abs=1e-3), key


def test_the_cliff_covers_the_vs_sh_spread_value():
    """The whole point: if off-FP spread resembles vs-SH (0.0624), is ABOVE
    reachable? The table must answer without anyone recomputing it."""
    cliff = G["above_reachability_cliff"]
    worst = max(r["fleet_mean_above_needs"] for r in cliff.values() if isinstance(r, dict))
    assert worst > cliff["best_12m_lane_ever_off_fp20"], "cliff fails to show unreachability"


def test_budget_key_is_present_on_every_arm():
    """G-BUDGET: the runner defaults SEARCH_TIME_MS to 100, so an arm that
    omits the key silently runs FP@100."""
    for name, arm in CFG["arms"].items():
        assert arm.get("search_time_ms") == 20, f"{name} would silently run FP@100"


def test_single_seat_arms_declare_their_lane():
    """G-SEAT / BL-2: `seat` defaults to s65, and s65 is pinned in this very
    file, so the sha assert would PASS on a silently-wrong arm."""
    for name, arm in CFG["arms"].items():
        if arm["kind"] != "ensemble_seat":
            assert "seat" in arm, f"{name} would silently run s65"


def test_ensemble_rosters_are_membership_rules_not_menus():
    ens = CFG["ensembles"]
    assert ens["E4_ladder"] == ["s62", "s63", "s64", "s65"], "E4 must be exactly L2"
    assert set(ens["E7_all"]) == set(CFG["checkpoints"]), "E7 must be every pinned lane"

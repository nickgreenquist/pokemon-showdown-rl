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


def test_every_bar_obeys_the_files_own_max_rule():
    """bar = max(credit_floor, 2*se). r3 set R1C's bar to 0.0246 — BELOW the
    floor — and the r3 version of this test ENFORCED the breach with
    `assert bar < credit_floor`. A test that asserts the bug is worse than
    no test, so it is inverted here and applied to every graded arm."""
    floor = G["credit_floor"]
    for name, a in G["arms"].items():
        if "bar" in a:
            assert a["bar"] >= floor, f"{name} bar {a['bar']} is below the floor {floor}"
    r1c = G["arms"]["R1C"]
    assert r1c["two_se"] == pytest.approx(2 * math.sqrt(2) * se(P0, r1c["n_per_arm"]), abs=5e-4)
    assert r1c["bar"] == max(floor, r1c["two_se"])


def test_the_primary_read_is_actually_graded():
    """The sweep's structural finding: r3 gave every read a rule EXCEPT the
    one Q1 declares primary."""
    a = G["arms"]["R1A_PRIMARY_s82"]
    n = 1500
    expect = math.hypot(math.sqrt(0.35 * 0.65 / (2 * n)), math.sqrt(0.25 * 0.75 / n))
    assert a["se_diff_at_n1500"] == pytest.approx(expect, abs=5e-4)
    assert set(a["verdicts"]) == {"REPRODUCES", "DOES_NOT"}
    assert a["sidedness"] == "one_sided_negative"


def test_no_duplicate_top_level_keys():
    """The sweep found `grading:` and `comparators:` each defined TWICE — a
    careless replace() broke a comment line out of its `#`. PyYAML takes the
    last key, so the file parsed to the intended values BY LUCK and 11
    passing tests saw nothing."""
    import collections

    class Dup(yaml.SafeLoader):
        pass

    def check(loader, node, deep=False):
        counts = collections.Counter(
            loader.construct_object(k, deep=True) for k, _ in node.value
        )
        dupes = [k for k, c in counts.items() if c > 1]
        assert not dupes, f"duplicate keys parse by luck: {dupes}"
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    Dup.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, check)
    yaml.load(PREREG.read_text(), Dup)


def test_verdict_p_bands_do_not_overlap():
    """r3 promoted a prose overlap at 0.030/0.060 into the authoritative keys."""
    bands = G["verdict_p_bands"]
    assert bands["resolving"].endswith("0.030]") and bands["weak"].startswith("(0.030")
    assert bands["weak"].endswith("0.060]") and bands["non_resolving"].startswith("(0.060")


def test_cliff_uses_the_off_fp_comparator_sd():
    """r3's cliff was built with the 12M vs-SH sd (0.01118) where the
    comparator is the 12M off-FP fleet (0.00771), stated in the same file."""
    s_cmp = G["above_reachability_cliff_comparator_sd"] if False else G["comparator_total_sd_off_fp"]
    assert s_cmp == pytest.approx(0.00771, abs=1e-5)
    seb = math.hypot(se(P0, 4500), se(P0, N0))
    for key, row in G["above_reachability_cliff"].items():
        if not isinstance(row, dict):
            continue
        s50 = float(key.split("_")[1])
        expect = max(G["credit_floor"], 2 * max(seb, math.sqrt(s50**2 / 3 + s_cmp**2 / 4)))
        assert row["bar"] == pytest.approx(expect, abs=5e-4), key


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


def test_n_does_not_bind_the_fleet_mean_bar_above_the_stated_point():
    """O-6(i). The deciding fact for R1-A's n: 2*binomial falls under the
    credit floor from ~750/lane, and the clustered term has no n in it. So
    past that point no battle count can move the bar, and any future edit
    that "buys more power" with battles on this read is confused."""
    a = G["arms"]["R1A"]
    floor = G["credit_floor"]
    for n in (a["n_does_not_bind_above"], a["n_per_lane"], 3000):
        two_binom = 2 * math.hypot(se(P0, 3 * n), se(P0, N0))
        assert two_binom <= floor, f"binomial still binds at n={n}"
    assert a["stage_2"] == "none"
    assert a["role"] == "secondary_descriptive"


def test_the_primary_n_clears_the_s82_question():
    a = G["arms"]["R1A_PRIMARY_s82"]
    n = a["n_per_lane"]
    sed = math.hypot(math.sqrt(0.35 * 0.65 / (2 * n)), math.sqrt(0.25 * 0.75 / n))
    assert a["se_diff_at_n1000"] == pytest.approx(sed, abs=5e-4)
    assert 0.11 / sed > 5.0, "a vs-SH-sized collapse must be comfortably resolvable"
    assert a["role"] == "PRIMARY"

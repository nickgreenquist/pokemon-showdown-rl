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
    """bar = max(credit_floor, 2*se), as EQUALITY.

    Three revisions of this file broke this rule in three different ways:
    r3 set R1C's bar BELOW the floor and the test of the day ENFORCED the
    breach (`assert bar < credit_floor`); r4 fixed R1C and then
    reintroduced the identical defect on the PRIMARY read with bar 0.025
    against 2*se = 0.0369. The weak form (`bar >= floor`) passed that.
    Equality is the only form that catches it, so it is enforced for every
    arm that publishes an se."""
    floor = G["credit_floor"]
    for name, a in G["arms"].items():
        if "bar" not in a:
            continue
        assert a["bar"] >= floor, f"{name} bar {a['bar']} is below the floor {floor}"
        two_se = next((2 * a[k] for k in a if k.startswith("se_diff_at")), None)
        if two_se is None:
            two_se = a.get("two_se")
        if two_se is not None:
            assert a["bar"] == pytest.approx(max(floor, two_se), abs=5e-4), (
                f"{name}: bar {a['bar']} != max({floor}, {two_se:.4f})"
            )
    r1c = G["arms"]["R1C"]
    assert r1c["two_se"] == pytest.approx(2 * math.sqrt(2) * se(P0, r1c["n_per_arm"]), abs=5e-4)
    assert r1c["bar"] == max(floor, r1c["two_se"])


def test_the_primary_read_is_graded_with_the_right_sign():
    """r4 wrote `sidedness: one_sided_negative` with `REPRODUCES: d <= -bar`
    on `d = mean{s80,s81} - s82`. But a REPRODUCED collapse is POSITIVE —
    the banked lanes give d = 0.73850 - 0.62967 = +0.10883 — so the rule
    returned DOES_NOT on a genuine reproduction. A sign inversion in the
    primary read's own grading rule."""
    a = G["arms"]["R1A_PRIMARY_s82"]
    d_if_it_reproduces = (0.7423333 + 0.7346667) / 2 - 0.6296667
    assert d_if_it_reproduces > 0
    assert a["sidedness"] == "one_sided_positive"
    assert a["verdicts"]["REPRODUCES"].startswith("d >= +bar")
    assert set(a["verdicts"]) == {"REPRODUCES", "DOES_NOT"}


def test_the_primary_se_is_null_referenced():
    """r4's se mixed p=0.35 (the pair) with p=0.25 (s82) — an ALTERNATIVE-
    referenced se used to set a NULL bar. Under the null both sit at ~0.35."""
    a = G["arms"]["R1A_PRIMARY_s82"]
    n, p = a["n_per_lane"], 0.35
    expect = math.sqrt(p * (1 - p) / (2 * n) + p * (1 - p) / n)
    assert a["se_reference"] == "null_hypothesis_common_p"
    assert a["se_diff_at_n1000"] == pytest.approx(expect, abs=5e-4)


def test_flat_is_not_licensed_as_a_bare_equivalence_claim():
    """RV1-MA-11: WITHIN is the complement of two one-sided tests — a
    failure to resolve, not evidence of equivalence. TOST was dropped, so
    the bare word must be too."""
    assert G["flat_bare_word_barred"] is True
    assert "failure to resolve, not evidence of equivalence" in G["flat_licensed_sentence"]


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
    """Power at the ratified n, on the NULL-referenced se (the alternative-
    referenced form this test used to carry is what r4 got wrong)."""
    a = G["arms"]["R1A_PRIMARY_s82"]
    d_if_it_reproduces = (0.7423333 + 0.7346667) / 2 - 0.6296667
    sep = d_if_it_reproduces / a["se_diff_at_n1000"]
    assert a["separation_if_it_reproduces"] == pytest.approx(sep, abs=0.15)
    assert sep > 5.0, "a vs-SH-sized collapse must be comfortably resolvable"
    assert a["role"] == "PRIMARY"


def test_no_sub_threshold_number_enters_a_comparison():
    """A-F6, adopted: 'no number with n_eff < 1000 enters any comparison,
    ever, including in prose.' r3 violated it in its own Q4 by quoting an
    n=250 FP@100 cell as a directional 'SIGN' -- which review 1 separately
    measured at 0.46 se."""
    floor = G["min_n_eff_for_any_comparison"]
    for name, c in CFG["comparators"].items():
        n = c.get("n")
        if n is not None and n < floor:
            assert c.get("role") == "BARRED_FROM_ALL_COMPARISONS", \
                f"{name} has n={n} < {floor} and is not barred"
    # The phrase survives once, in the note recording that r3's rule was
    # DELETED. That is history, not an instruction — so assert on the live
    # form instead: no uncommented line may license the barred cell.
    live = [l for l in PREREG.read_text().split("\n")
            if "SIGN" in l and not l.lstrip().startswith("#")]
    assert not live, f"a live line still licenses the barred cell: {live}"


def test_headline_protection_is_a_key_not_prose():
    """A-§9b: without these the 'headline UNTOUCHED' sentence is unenforced."""
    assert G["crediting"] is False and G["headline_may_move"] is False
    joined = " ".join(G["on_every_branch"])
    for n in ("0.71825", "0.74633", "0.79283", "1311"):
        assert n in joined, f"{n} unprotected"


def test_the_outlier_rule_protects_the_primary_read():
    """A-§2.2c. The primary read IS the one-lane collapse, so a rule that
    dropped outliers would delete the finding it exists to measure."""
    assert "NO LANE IS EVER DROPPED" in G["outlier_rule"]


def test_open_maintainer_escalations_are_recorded_not_assumed():
    assert G["chapter5_s3c1_edit"]["status"] == "AWAITING_RETRO_RATIFICATION"
    assert G["r1c_scope_escalation"]["status"] == "MAINTAINER_DECISION"

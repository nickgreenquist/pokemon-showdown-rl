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
import re
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


def test_no_cell_licenses_the_word_flat():
    """RV1-MA-11 + r6's TOST arithmetic. r5 licensed "flat" in WITHIN x
    RESOLVING and this test ENFORCED it. WITHIN is the complement of two
    one-sided tests, and the TOST that would supply the missing construction
    is UNREACHABLE at n=1000 (see the next test), so no cell licenses it."""
    assert G["flat_licensed_in"] == []
    assert "flat_licensed_only_in" not in G, "the old key must be gone, not shadowed"
    assert G["flat_realized_bar_must_be_quoted"] is True


def test_the_tost_is_unreachable_at_the_ratified_n():
    """The arithmetic behind the maintainer's 2026-08-26 ruling, pinned so a
    future n change re-opens the question deliberately rather than silently.
    A TOST at margin 0.025 needs se_clustered <= 0.025/t(.95, 2df) = 0.00856,
    i.e. s_50 <= 0.01324. At n=1000 the per-lane BINOMIAL sd alone is 0.01507
    -- larger than the entire budget -- so no sigma_seed makes it fire."""
    t = G["r1a_tost"]
    n = G["arms"]["R1A"]["n_per_lane"]
    assert t["requires_se_clustered_at_most"] == pytest.approx(0.025 / 2.920, abs=5e-5)
    s50_max = math.sqrt((t["requires_se_clustered_at_most"] ** 2
                         - G["comparator_total_sd_off_fp"] ** 2 / 4) * 3)
    assert t["requires_s50_at_most"] == pytest.approx(s50_max, abs=5e-4)
    assert se(P0, n) > s50_max, "if this ever fails the TOST became reachable -- re-rule it"
    assert "UNREACHABLE" in t["reachability_at_the_ratified_n"]
    assert G["flat_licensed_in"] == [], "an unreachable TOST cannot license 'flat'"


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
    s_cmp = G["comparator_total_sd_off_fp"]
    assert s_cmp == pytest.approx(0.00771, abs=1e-5)
    # R-5: r4 hardcoded 4500 (= 3 x 1500) while R1A.n_per_lane became 1000.
    # DERIVE it, so the next n change moves the cliff instead of rotting it.
    n = G["arms"]["R1A"]["n_per_lane"]
    seb = math.hypot(se(P0, 3 * n), se(P0, N0))
    assert G["above_reachability_cliff"]["n_per_lane"] == n, \
        "the cliff was computed at a different n than the arm runs at"
    assert G["above_reachability_cliff"]["se_binomial_of_the_difference"] == \
        pytest.approx(seb, abs=5e-5)
    for key, row in G["above_reachability_cliff"].items():
        if not isinstance(row, dict) or not key.startswith("s50_"):
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
        if not isinstance(row, dict) or not key.startswith("s50_"):
            continue
        assert row["fleet_mean_above_needs"] == pytest.approx(P0 + row["bar"], abs=1e-3), key


def test_the_cliff_covers_the_vs_sh_spread_value():
    """The whole point: if off-FP spread resembles vs-SH (0.0624), is ABOVE
    reachable? The table must answer without anyone recomputing it."""
    cliff = G["above_reachability_cliff"]
    worst = max(r["fleet_mean_above_needs"] for k, r in cliff.items()
                if isinstance(r, dict) and k.startswith("s50_"))
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
    # NB the bare substring "SIGN" also matches "ROUTING SIGNAL" (the
    # multiplicity rule), so match the phrase the rule actually bars.
    live = [l for l in PREREG.read_text().split("\n")
            if re.search(r"\bSIGN\b", l) and not l.lstrip().startswith("#")]
    assert not live, f"a live line still licenses the barred cell: {live}"


def test_headline_protection_is_a_key_not_prose():
    """A-§9b: without these the 'headline UNTOUCHED' sentence is unenforced."""
    assert G["crediting"] is False and G["headline_may_move"] is False
    joined = " ".join(G["on_every_branch"])
    # CORRECTED 2026-08-29: the protected ladder number is the FINAL rating
    # 1292, not 1311 (the pre-battle value of the last battle). The test now
    # protects the corrected value and rejects the retracted one.
    for n in ("0.71825", "0.74633", "0.79283", "1292"):
        assert n in joined, f"{n} unprotected"
    assert "1311" not in joined, "retracted pre-battle Elo 1311 re-entered the protected clause"


def test_the_outlier_rule_protects_the_primary_read():
    """A-§2.2c. The primary read IS the one-lane collapse, so a rule that
    dropped outliers would delete the finding it exists to measure."""
    assert "NO LANE IS EVER DROPPED" in G["outlier_rule"]


def test_open_maintainer_escalations_are_ruled_not_silently_assumed():
    """Both escalations r5 RECORDED were RULED on 2026-08-26. The point of the
    test is unchanged: neither may be silently assumed. A ruling is recorded
    with its date and its consequence; an unruled one keeps its OPEN status."""
    edit = G["chapter5_s3c1_edit"]
    assert edit["status"] == "RETRO_RATIFIED_2026_08_26" and edit["commit"] == "25256b8"
    assert "0.0735" in edit["settles"]
    esc = G["r1c_scope_escalation"]
    assert esc["status"] == "RULED_2026_08_26"
    assert esc["ruling"] in ("fund_both_rosters", "cut_to_one", "defer_r1c_to_r2")
    assert esc["not_an_option"], "the option that was never available stays named"
    # rev 2 BL-5c: the r5 maintainer list held four items of the assistant's
    # own choosing and none of designer A's five brackets.
    text = PREREG.read_text()
    for bracket in ("A-BR-1", "A-BR-2", "A-BR-3", "A-BR-4", "A-BR-5"):
        assert bracket in text, f"{bracket} is absent from OPEN FOR THE MAINTAINER"


def test_the_cliff_keeps_its_decision_relevant_row():
    """R-5's second half: r4's recomputation DELETED the row that decides
    anything -- the s_50 at which the bar leaves the 0.025 floor. That value
    is n-INDEPENDENT (it is where the clustered term alone reaches the floor)
    and is designer A's number. Without it the table shows two rows at 0.0250
    and jumps to 0.0355."""
    s_cmp = G["comparator_total_sd_off_fp"]
    lo, hi = 0.0, 0.06
    for _ in range(80):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if 2 * math.sqrt(m ** 2 / 3 + s_cmp ** 2 / 4) <= G["credit_floor"] else (lo, m)
    assert f"s50_{lo:.4f}" in G["above_reachability_cliff"], \
        f"the bar leaves the floor at s_50 = {lo:.4f} and that row is missing"


def test_no_username_is_a_prefix_of_another():
    """designer B §5.2 / rev 2 MA-5: kill_fp() sweeps
    `pkill -9 -f "run.py .*--ps-username $FP_USER( |$)"`. The `( |$)` guard is
    belt; non-prefixing names are braces. A prefix pair means one arm's sweep
    kills its sibling -- the S1 shape, 3.6 h at zero progress that LOOKS like
    slow progress."""
    names = [u for pair in CFG["usernames"]["pairs"].values() for u in pair.values()]
    assert len(names) == len(set(names)), "duplicate username"
    for a in names:
        for b in names:
            assert a == b or not b.startswith(a), f"{a!r} is a prefix of {b!r}"
    for arm, pair in CFG["usernames"]["pairs"].items():
        assert CFG["arms"][arm]["seat_username"] == pair["seat"], arm
        assert CFG["arms"][arm]["fp_username"] == pair["fp"], arm
    assert set(CFG["usernames"]["pairs"]) == set(CFG["arms"]), \
        "every arm needs a declared pair, and no pair may name a nonexistent arm"


def test_every_arm_declares_its_battle_count():
    """rev 2 BL-2b: BATTLES defaults to 250 in the runner and the export loop
    emits the var only when the key is present, so an arm that omits it runs
    250 battles and stamps battles_requested/finished 250 with
    gate_all_challenges_resolved true -- passing every other gate."""
    for name, arm in CFG["arms"].items():
        assert isinstance(arm.get("battles"), int), f"{name} would silently run 250"


def test_every_arm_kind_is_one_the_seat_accepts():
    """An unrecognised kind used to run the GREEDY seat silently (CH3 R4
    BI-5). It now fails loudly -- at LAUNCH. This fails it here instead."""
    kinds = ("greedy_seat", "search_seat", "sampled_seat", "fp_vs_clone", "ensemble_seat")
    for name, arm in CFG["arms"].items():
        assert arm["kind"] in kinds, f"{name}: {arm['kind']!r} would assert at launch"
        assert ("seat" in arm) ^ ("lanes" in arm), f"{name}: seat/lanes are exclusive"
        assert (arm["kind"] == "ensemble_seat") == ("lanes" in arm), name
        # rev 2 MI-8's neighbour: `sampled_seat` flips deterministic=True, and
        # CLAUDE.md's landmine is that a policy-form mismatch manufactures an
        # effect worth ~26 implied rating points.
        assert arm["kind"] != "sampled_seat", f"{name}: barred by grading.sampled_seat_barred"
        # 2026-08-27: `search_seat` requires `dose` (ch3_fp_h2h.py:268 does
        # DOSES[arm["dose"]]). All three R1-B arms omitted it and died in 30 s
        # with KeyError: 'dose'. This test checked kind/seat/lanes/battles/
        # budget and not this, so the wave found it instead of the suite.
        if arm["kind"] == "search_seat":
            assert arm.get("dose") in ("S", "M", "L"), \
                f"{name}: search_seat needs a dose; KeyError at ch3_fp_h2h.py:268 otherwise"
            assert arm["dose"] == "M", \
                f"{name}: this chapter is search@M throughout; any other dose is a new pre-registration"
    assert G["seat_policy"] == "deterministic" and G["sampled_seat_barred"] is True


def test_c0_is_byte_identical_to_the_laddered_object():
    """rev 1 MI-10 / designer B's G-ENS: C0's whole justification is that its
    FP number and the ladder rating rate the SAME object. That is an IDENTITY
    claim, and until r6 nothing re-verified it -- the pins happened to match,
    which is a fact about the tree, not a gate."""
    ladder = yaml.safe_load((PREREG.parent / "ladder_r1.yaml").read_text())
    l2 = ladder["arms"]["L2"]["lanes"]
    assert CFG["arms"]["C0"]["lanes"] == l2
    assert CFG["ensembles"]["E4_ladder"] == l2, "rev 2 MI-6: two places to drift"
    for lane in l2:
        assert CFG["checkpoints"][lane]["sha256"] == ladder["checkpoints"][lane]["sha256"], lane
        assert CFG["checkpoints"][lane]["path"] == ladder["checkpoints"][lane]["path"], lane


def test_the_r1c_rosters_are_real_arms_not_dead_config():
    """rev 2 MA-8: no script reads `ensembles:` -- ch5_seat_equiv.py reads
    `arms.<X>.lanes` -- so a roster that is not an arm cannot be gated by
    G-EQUIV or G-DECLARED, and nothing budgets it. r5 declared two rosters
    and budgeted one; the maintainer funded both on 2026-08-26."""
    assert CFG["arms"]["CE3"]["lanes"] == CFG["ensembles"]["E3_50m"]
    assert CFG["arms"]["CE7"]["lanes"] == CFG["ensembles"]["E7_all"]
    assert G["r1c_scope_escalation"]["ruling"] == "fund_both_rosters"
    # r1c_delivered_iff is defined over max(E3, E7); both must be budgeted.
    assert "max(E3, E7)" in G["r1c_delivered_iff"]
    for arm in ("CE3", "CE7"):
        assert CFG["arms"][arm]["battles"] == 3000


def test_e7_rule_reproduces_its_own_list():
    """rev 2 MA-8: "every 828-d lane on disk" selected THIRTEEN lanes while
    the list had seven, because struct50m is 828-d too. A rule that does not
    reproduce its own list is a menu wearing a rule's label. r5 replaced it
    with a bare enumeration, which is the same defect."""
    text = PREREG.read_text()
    # The phrase may survive ONLY inside the passage that records it as wrong.
    for line in text.split("\n"):
        if "every 828-d lane on disk" in line:
            assert "did NOT" in line or "WRONG" in line, \
                f"the retired rule is stated as live: {line}"
    assert "PRODUCTION-ERA" in text and "excluded on STRENGTH" in text
    e7 = CFG["ensembles"]["E7_all"]
    assert e7 == CFG["ensembles"]["E4_ladder"] + CFG["ensembles"]["E3_50m"]
    assert set(e7) == set(CFG["checkpoints"])


def test_the_prereg_self_reference_is_this_file():
    """rev 2 MI-9: a dead self-reference read by nothing. One assert turns it
    into the key that catches this file being copied to a new name without
    being updated -- and it is what G0's prereg_sha256 hashes."""
    assert CFG["prereg"] == "configs/eval/ch5_r1_offsh.yaml"
    assert (PREREG.parents[2] / CFG["prereg"]).samefile(PREREG)
    assert CFG["results_dir"] == "results/ch5_r1_offsh"


def test_every_named_instrument_exists():
    """rev 2 MA-2a: `results/`, `runs/` and `data/` are all gitignored with
    zero tracked files, so a grader script is the ONLY committed provenance.
    Naming a script that does not exist is worse than naming none."""
    root = PREREG.parents[2]
    # `instruments:` is role -> PATH ONLY. tests/test_ladder.py walks every
    # key of every eval pre-reg's block and asserts the value is a file, so a
    # command string or a list here breaks a repo-wide test (it did).
    for role, rel in CFG["instruments"].items():
        assert isinstance(rel, str) and (root / rel).exists(), f"{role} -> {rel}"
    assert CFG["instrument_contract"]["build_items_still_owed"] == []
    assert CFG["instrument_contract"]["grade_runs_before_any_number_is_quoted"] is True


def test_the_runner_has_the_no_progress_abort():
    """designer B §5.4c / BI-3. A hung SEAT stops FP writing too, so the stall
    detector fires and kills the HEALTHY process -- burning the whole relaunch
    budget at zero progress while looking exactly like slow progress."""
    runner = (PREREG.parents[2] / "scripts/ch3_r4_fp_runner.sh").read_text()
    assert "NO_PROGRESS_RELAUNCHES" in runner and "exit 4" in runner
    # The sentinel write moved behind $NO_PROGRESS_MARKER when the runner
    # grew the stale-marker cleanup (2026-08-28); assert the definition and
    # the write, not the pre-refactor literal.
    assert 'NO_PROGRESS_MARKER="$OUT/$TAG.NO_PROGRESS"' in runner
    assert 'date -u +%Y-%m-%dT%H:%M:%SZ > "$NO_PROGRESS_MARKER"' in runner
    assert "$TAG.NO_PROGRESS (runner exit 4" in " ".join(
        CFG["disposition_of_a_broken_arm"]["OPS_FAILURE_rerun_never_graded"])


def test_the_ops_failure_distinction_survives():
    """designer B §6: an ops failure graded as data is how a clean arm becomes
    a wrong number. Both sentinels are FILES, so the grader sees them without
    inference, and neither is in the VOID list."""
    d = CFG["disposition_of_a_broken_arm"]
    ops = " ".join(d["OPS_FAILURE_rerun_never_graded"])
    void = " ".join(d["VOID_arm_scoped"]) + " ".join(d["VOID_wave_scoped"])
    assert "NO_PROGRESS" in ops and "USERNAME_DEADLOCK" in ops
    assert "NO_PROGRESS" not in void and "USERNAME_DEADLOCK" not in void
    assert "DOWNSTREAM" in " ".join(d["VOID_wave_scoped"])


def test_the_winners_curse_is_quoted_at_the_n_of_the_score():
    """rev 1 MA-7 residual: r4 quoted +0.0143 at n=1500 for candidates scored
    at three different n. E[max of m standard normals] * se, per candidate,
    at its REALIZED n."""
    wc = CFG["r3_deployment_rule"]["winners_curse_at_the_n_of_the_score"]
    e_max_5 = 1.16296
    assert wc["m5_n3000"] == pytest.approx(e_max_5 * se(P0, 3000), abs=5e-4)
    assert wc["m5_n1000"] == pytest.approx(e_max_5 * se(P0, 1000), abs=5e-4)
    # best-k-of-7 is ~120 rosters, E[max] ~ 2.70 -- 94% of the credit floor.
    assert wc["best_k_of_7_n3000"] == pytest.approx(2.70 * se(P0, 3000), abs=1e-3)
    assert len(CFG["r3_deployment_rule"]["candidates"]) == 5
    assert set(CFG["r3_deployment_rule"]["candidate_n_is_not_uniform"]) == \
        set(CFG["r3_deployment_rule"]["candidates"])


def test_the_ledger_reproduces_from_the_measured_marginals():
    """Every arm priced from a MEASURED marginal, and the total recomputed
    rather than transcribed -- three cost estimates in this chapter were
    wrong, and one of them (n=1500 -> 1000) silently outlived its own n."""
    rates = {"C0": (3000, 1.60), "A": (3 * 1000, 1.485), "B": (3 * 1000, 2.68),
             "CE3": (3000, 1.56), "CE7": (3000, 1.72)}
    total = sum(n * r for n, r in rates.values()) / 3600
    assert total == pytest.approx(CFG["cost_ledger"]["agent_side_battle_hours"], abs=0.02)
    assert "7.53" in PREREG.read_text(), "the header must carry the recomputed total"
    mvp = (3000 * 1.60 + 3 * 1000 * 1.485) / 3600
    assert f"{mvp:.2f}" in CFG["interrupt_policy"]["mvp"]


def test_the_ceiling_on_r1b_is_present_and_names_mu8():
    """rev 1 MA-8c: without it a positive R1-B reads as reversing a result
    CLAUDE.md grades at z = -2.80, by implication rather than by claim."""
    c = G["arms"]["R1B"]["ceiling_pre_committed"]
    assert "z = -2.80" in c and "DEPLOYMENT CANDIDATE" in c
    assert "may not be set beside the negative 12M cell" in c


def test_the_k2_contradiction_is_ruled_not_left_open():
    """sweep A-§3.3a was left as an UNRESOLVED CONTRADICTION: G-K permitted a
    VERDICT-S at k=2 while designer A's own licensed sentence said no verdict
    is licensed there. At 1 df the sd's 95% CI multipliers span 0.45x-31.9x --
    a factor of 72 -- so the bar computed from it is not a bar."""
    text = PREREG.read_text()
    assert "k=2 RULED" in text and "0.45x-31.9x" in text
    assert "at k_arm <= 2 the FLEET-MEAN read is DESCRIPTIVE ONLY" in text.replace("**", "")
    assert "0.45x-31.9x" in CFG["licensed_sentences"]["DESCRIPTIVE_ONLY"]


def test_the_grader_selftest_passes():
    """designer B BI-4. --selftest runs entirely against BANKED CH4
    artifacts, so the gate apparatus is exercisable before a single CH5
    battle. If the artifacts are absent the test skips rather than lying."""
    import subprocess, sys
    root = PREREG.parents[2]
    if not (root / "results/ch4_r1_offsh/l64.fp.stdout").exists():
        pytest.skip("banked CH4 artifacts absent (results/ is gitignored)")
    r = subprocess.run([sys.executable, str(root / "scripts/ch5_r1_grade.py"), "--selftest"],
                       capture_output=True, text=True, cwd=root)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELFTEST PASS" in r.stdout

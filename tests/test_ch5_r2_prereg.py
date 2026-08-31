"""CH5 R2 pre-registration — internal-consistency tests (R0-a's automated
half plus the header-arithmetic class test_ch5_prereg.py exists for).

Scope: the TWO pre-reg files (configs/showdown_sp_batch50m.yaml — the
training half; configs/eval/ch5_r2_offsh.yaml — the read half), the R2
wave/preflight scripts, and the grader's selftest. Every assertion here
is a defect class this repo has actually shipped: a bar stored below its
own rule, a duplicated YAML key silently resolved by PyYAML, a username
prefix that let one arm's sweep kill its sibling, a battles default that
turned a 3000-battle arm into a 250-battle arm, a grader missing at
readout, a copied script stamping the WRONG pre-reg's sha into
provenance.

These tests read no run data and must stay green from ratification
through readout.
"""

import itertools
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TRAIN = REPO / "configs/showdown_sp_batch50m.yaml"
EVAL = REPO / "configs/eval/ch5_r2_offsh.yaml"
CONTROL = REPO / "configs/showdown_sp_stack50m_r2.yaml"
R1_PREREG = REPO / "configs/eval/ch5_r1_offsh.yaml"
WAVE = REPO / "scripts/ch5_r2_wave.sh"
PREFLIGHT = REPO / "scripts/ch5_r2_preflight.sh"

TCFG = yaml.safe_load(TRAIN.read_text())
ECFG = yaml.safe_load(EVAL.read_text())
CCFG = yaml.safe_load(CONTROL.read_text())
TTXT = TRAIN.read_text()
ETXT = EVAL.read_text()
G = ECFG["grading"]

sys.path.insert(0, str(REPO / "scripts"))
import importlib.util

_spec = importlib.util.spec_from_file_location("ch5_r2_grade",
                                               REPO / "scripts/ch5_r2_grade.py")
grade = importlib.util.module_from_spec(_spec)
sys.modules["ch5_r2_grade"] = grade
_spec.loader.exec_module(grade)


def _flat(d, p=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{p}{k}."))
        else:
            out[f"{p}{k}"] = v
    return out


# ---------------------------------------------------------------------
# identity and verbatim strings
# ---------------------------------------------------------------------

def test_journey_step_and_scope_guard_verbatim():
    assert ECFG["journey_step"] == 1
    assert "journey_step: 1" in TTXT
    guard = ("a read inside the bar is information about the INSTRUMENT, not a "
             "licence to queue another gen1 lever — ladder anyway (step 2), then "
             "step 3 (gen4).")
    assert guard in TTXT.replace("\n# ", " "), "scope guard must be verbatim IN FULL (both clauses) in the training header"


def test_credit_line_verbatim_including_larger_of():
    line = ("a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, "
            "where se_diff is the LARGER of the pooled-binomial se_diff and the "
            "seed-clustered se_diff, the latter computed from the per-seed "
            "finals at read time.")
    assert G["credit_line_verbatim"] == line
    assert line in TTXT.replace("\n# ", " "), "credit line must be verbatim in the training header too"
    assert "sqrt(s_arm^2/k_arm + s_cmp^2/k_cmp)" in G["clustered_formula"]


def test_aggregator_named_once_and_nongoverning_list():
    assert G["aggregator"] == "equal_weight_mean_of_lane_rates"
    assert set(G["recorded_never_governing"]) == {
        "pooled_rate", "per_lane_median", "best_lane", "worst_lane",
        "per_lane_deltas"}


def test_headline_protection_1292_never_1311():
    for txt, name in ((TTXT, "training"), (ETXT, "eval")):
        assert "1292" in txt, f"{name}: the protected FINAL Elo 1292 is missing"
        for m in re.finditer(r"1311", txt):
            ctx = txt[max(0, m.start() - 8):m.start()].lower()
            assert "never" in ctx, (
                f"{name}: bare 1311 (the retracted pre-battle rating) at {m.start()}")


def test_flat_is_not_licensed_anywhere():
    assert G["flat_licensed_in"] == []
    assert "TOST" in ETXT and "UNREACHABLE" in ETXT.upper()


# ---------------------------------------------------------------------
# one-diff and batch arithmetic
# ---------------------------------------------------------------------

def test_one_diff_is_exactly_five_keys():
    a, b = _flat(CCFG), _flat(TCFG)
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"seed", "run_name", "agent.rollout_steps",
                    "agent.minibatches", "selfplay.push_every_updates"}, diff


def test_lever_values_and_held_keys():
    ag = TCFG["agent"]
    assert (ag["rollout_steps"], ag["minibatches"],
            TCFG["selfplay"]["push_every_updates"]) == (3840, 120, 5)
    assert ag["gae_lambda"] == 0.95, "the Q4 ruling: lambda HELD"
    assert ag["epochs"] == 4 and TCFG["num_envs"] == 8
    assert TCFG["seed"] == 66 and TCFG["run_name"] == "showdown_sp_batch50m_s66"


def test_batch_arithmetic_reproduces_from_configs():
    r = grade.batch_pool_arithmetic()
    assert r["pass"], r


def test_anneal_guard_and_da_rungs():
    assert TCFG["agent"]["lr_anneal_steps"] == TCFG["total_steps"] == 50_000_000
    for lr, u in ((2.401696e-4, 65), (2.002336e-4, 325),
                  (1.202080e-4, 846), (2.464000e-7, 1627)):
        assert math.isclose(grade.da_expected_lr(u), lr, rel_tol=1e-6), (u, lr)


def test_frozen_controls_attest_from_disk():
    a = grade.attest()
    assert a["pass"], a


# ---------------------------------------------------------------------
# bars and cells
# ---------------------------------------------------------------------

def test_planning_bar_reproduces_and_floor_is_inert():
    s = G["control_offfp"]["sd"]
    assert math.isclose(G["planning_bar"], 2 * math.sqrt(2 * s ** 2 / 3),
                        abs_tol=1e-4)
    assert math.isclose(G["bar_floor_inert_min"], 2 * math.sqrt(s ** 2 / 3),
                        abs_tol=5e-5)
    for s_t in (0.0, 0.0088, 0.0155, 0.025, 0.04, 0.0617, 0.09, 0.12):
        bar = max(G["credit_floor"], 2 * math.sqrt(s_t ** 2 / 3 + s ** 2 / 3))
        assert bar > G["credit_floor"], (
            f"the floor must be INERT at s_T={s_t} (the inverse of R1's "
            "bar-below-floor bug)")


def test_reachability_rows_in_header_match_the_formula():
    s = G["control_offfp"]["sd"]
    rows = {0.0000: 0.0712, 0.0088: 0.0720, 0.0155: 0.0735, 0.0250: 0.0769,
            0.0400: 0.0849, 0.0617: 0.1008, 0.0900: 0.1260, 0.1200: 0.1558}
    mean_c = 0.3373333333
    for s_t, bar in rows.items():
        want = max(0.025, 2 * math.sqrt(s_t ** 2 / 3 + s ** 2 / 3))
        assert abs(want - bar) < 5e-4, (s_t, bar, want)
        assert f"{bar:.4f}" in ETXT, f"tabulated bar {bar} missing from the header"
        # r2_review_1 SF-10(iv): the column a reader ACTS on
        need = round(mean_c + want, 4)
        assert f"{need:.4f}" in ETXT, \
            f"'treatment mean must be >= {need}' missing for s_T={s_t}"


def test_cells_partition_the_line_with_no_gap_or_overlap():
    bar = 0.1007
    cells = [grade.primary_cell(d, bar)[0]
             for d in [x / 10000 for x in range(-2000, 2001)]]
    order = []
    for c in cells:
        if not order or order[-1] != c:
            order.append(c)
    assert order == ["P6", "P5", "P4", "P3", "P2", "P1"], order
    # exact boundaries per the pre-reg Q2
    assert grade.primary_cell(bar, bar)[0] == "P1"
    assert grade.primary_cell(0.025, bar)[0] == "P2"
    assert grade.primary_cell(0.0, bar)[0] == "P3"
    assert grade.primary_cell(-0.025, bar)[0] == "P5"
    assert grade.primary_cell(-bar, bar)[0] == "P6"


def test_tost_is_unreachable_at_every_n_and_s_t():
    s = G["control_offfp"]["sd"]
    se_min = math.sqrt(s ** 2 / 3)          # s_T = 0, any n
    assert se_min > 0.01173 * 3, "the control sd alone must defeat the TOST 3x over"


def test_permutation_spec():
    p = G["permutation"]
    assert p["combinations"] == 20 and p["min_p"] == 0.050
    assert p["fires_iff_every_treatment_lane_above"] == 0.3960
    assert p["credits"] == "never" and p["tie_rule"] == "NON-separation"
    assert 0.3960 == max(G["control_offfp"][l]["rate"]
                         for l in ("s80", "s81", "s82")), \
        "the permutation threshold must be the max control lane"


def test_vs_sh_role_is_the_adjudicated_one():
    v = G["vs_sh_role"]
    assert v["positive_side"] == "descriptive"
    assert v["negative_side"] == "letter_bearing"
    assert "maintainer" in v["named_cell_X3"] and "README" in v["named_cell_X3"]
    # X3 fires only for P1 x SN-C, via the grader's own function
    assert grade.x_cell("P1", "SN-C")[0] == "X3"
    assert grade.x_cell("P1", "SN-L")[0] == "X2"
    assert grade.x_cell("P2", "SN-C")[0] == "X4"


def test_f1_threshold_is_the_frozen_struct50m_pooled():
    assert G["falsifier_F1_threshold"] == 0.580222 == grade.F1_THRESHOLD


def test_sigma_seed_disclosure_is_emitted_with_the_number():
    r = grade.grade_read({"s66": 0.37, "s75": 0.36, "s83": 0.38},
                         {"s66": 3000, "s75": 3000, "s83": 3000})
    blk = r["sigma_seed_descriptive"]
    assert blk["MANDATORY_DISCLOSURE"] == grade.SIGMA_DISCLOSURE
    assert "(2,2)" in grade.SIGMA_DISCLOSURE and "19.0" in grade.SIGMA_DISCLOSURE \
           and "4.4x" in grade.SIGMA_DISCLOSURE
    assert "BATCH DID NOT HELP VARIANCE" in grade.SIGMA_DISCLOSURE


def test_fp_disclosures_present_verbatim():
    assert "weakly powered" in ETXT and "PASS band is tighter" in ETXT
    assert "marginally" in ETXT and "flatters us" in ETXT
    assert "search_time_ms" in ETXT and ECFG["fp"]["search_time_ms"] == 20


# ---------------------------------------------------------------------
# arms, usernames, checkpoints
# ---------------------------------------------------------------------

def test_every_arm_is_well_declared():
    kinds = {"T66": "greedy_seat", "T75": "greedy_seat", "T83": "greedy_seat",
             "R4S66": "search_seat", "R4S75": "search_seat", "R4S83": "search_seat"}
    assert set(ECFG["arms"]) == set(kinds)
    for name, arm in ECFG["arms"].items():
        assert arm["kind"] == kinds[name]
        assert arm["kind"] != "sampled_seat"
        assert isinstance(arm["battles"], int) and arm["battles"] == 3000, \
            f"{name} would silently run the 250-battle default"
        assert arm["search_time_ms"] == 20
        assert arm["seat"] in ("s66", "s75", "s83")
        assert arm["seat_username"] and arm["fp_username"]
        if arm["kind"] == "search_seat":
            assert arm.get("dose") == "M", f"{name}: search_seat requires dose (the r7 KeyError)"
    assert G["treatment"]["n_per_lane_offfp"] == 3000, "ADJ-1: treatment n is 3000"


def test_arm_pairs_match_and_seats_cover_the_lanes():
    for arm, pair in ECFG["usernames"]["pairs"].items():
        assert ECFG["arms"][arm]["seat_username"] == pair["seat"], arm
        assert ECFG["arms"][arm]["fp_username"] == pair["fp"], arm
    assert set(ECFG["usernames"]["pairs"]) == set(ECFG["arms"])
    assert {ECFG["arms"][a]["seat"] for a in ("T66", "T75", "T83")} == \
           set(G["treatment"]["lanes"])


def test_no_username_is_a_prefix_of_any_ever_issued():
    """DEFECT FIXED 2026-08-31, RESULT-BLIND, disclosed in the readout.

    The group tuple was ("pairs", "rerun_pairs") and the licensed pair-flip
    (edit ii) FALSIFIED the 24-distinct-name assertion by construction: the
    flip promotes an arm's reserve into `pairs` and deletes it from
    `rerun_pairs` (the ch5_r1_offsh.yaml:1431-1432 anti-double-issue rule), so
    the two-group union can only ever hold 22 distinct names once (ii) fires.
    The proof depends on NO arm's result and would hold identically had the
    ops failure landed on battle 1; this test gates no number. The fix ADDS
    `burned_pairs` to the sweep, so the count stays exactly 24 and the prefix
    invariant gets STRONGER (burned names are now swept too). Precedent for
    fixing an unsatisfiable-by-construction gate and disclosing it:
    scripts/ch5_r1_grade.py:247-255.
    """
    r1cfg = yaml.safe_load(R1_PREREG.read_text())
    names = []
    for grp in ("pairs", "rerun_pairs", "burned_pairs"):
        for pair in (ECFG["usernames"].get(grp) or {}).values():
            names += [pair["seat"], pair["fp"]]
    assert len(names) == 24 == len(set(names))
    old = []
    for grp in ("pairs", "rerun_pairs_r9", "burned_pairs_r10"):
        for pair in (r1cfg["usernames"].get(grp) or {}).values():
            old += [pair["seat"], pair["fp"]]
    universe = names + old
    for a, b in itertools.permutations(universe, 2):
        assert a == b or not b.startswith(a), f"{a!r} is a prefix of {b!r}"
    burned = [u for pair in (r1cfg["usernames"].get("burned_pairs_r10") or {}).values()
              for u in pair.values()]
    assert not set(names) & set(burned), "a burned pair was re-issued"
    live = [u for pair in ECFG["usernames"]["pairs"].values() for u in pair.values()]
    r2_burned = [u for pair in (ECFG["usernames"].get("burned_pairs") or {}).values()
                 for u in pair.values()]
    assert not set(live) & set(r2_burned), "an R2 burned pair was re-issued into pairs"
    for prefix in ECFG["usernames"]["never_reuse"]:
        for n in names:
            assert not n.startswith(prefix), (n, prefix)


def test_checkpoint_attestation_is_all_or_nothing():
    att = ECFG["checkpoint_attestation"]
    shas = [ECFG["checkpoints"][l]["sha256"] for l in ("s66", "s75", "s83")]
    if att["status"] == "PENDING":
        assert all(s == "PENDING" for s in shas), "half-filled sha block"
    else:
        assert att["status"] == "ATTESTED"
        assert all(re.fullmatch(r"[0-9a-f]{64}", s) for s in shas), "half-filled sha block"
    for lane in ("s66", "s75", "s83"):
        assert ECFG["checkpoints"][lane]["path"] == \
               f"runs/showdown_sp_batch50m_s{lane[1:]}/checkpoint.pt"
    assert att["rule"] == "final_checkpoint_pt_at_step_50000000"


def test_seeds_are_window_disjoint_and_unused():
    seeds = [66, 75, 83]
    for a, b in itertools.combinations(seeds, 2):
        assert abs(a - b) >= 8, ("sub-env windows [seed, seed+7] overlap "
                                 f"for {a},{b}")
    for p in (REPO / "runs").glob("*/config.yaml"):
        s = yaml.safe_load(p.read_text()).get("seed")
        if s in seeds:
            # r2_review_2 MF-2: the arm's OWN lanes stamp their seed at
            # launch; only a FOREIGN run on 66/75/83 is a violation.
            assert p.parent.name == f"showdown_sp_batch50m_s{s}", \
                f"seed {s} already used by a foreign run {p.parent.name}"


# ---------------------------------------------------------------------
# yaml hygiene and cross-file consistency
# ---------------------------------------------------------------------

def test_no_duplicate_keys_at_any_depth():
    """The R1 defect: a key defined twice parses to the LAST value under
    PyYAML and 11 passing tests saw nothing. Checked at EVERY depth
    (r2_review SF: the draft checked top level only)."""
    def walk(node, path, name):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for k_node, v_node in node.value:
                k = getattr(k_node, "value", repr(k_node))
                assert k not in seen, \
                    f"{name}: duplicate key {'.'.join(path + [str(k)])!r}"
                seen.add(k)
                walk(v_node, path + [str(k)], name)
        elif isinstance(node, yaml.SequenceNode):
            for i, item in enumerate(node.value):
                walk(item, path + [str(i)], name)

    for path in (TRAIN, EVAL):
        walk(yaml.compose(path.read_text()), [], path.name)


def test_planning_bar_agrees_across_the_two_files():
    assert "0.1007" in TTXT and G["planning_bar"] == 0.1007


def test_marked_correction_and_retention_obligation_present():
    assert "MARKED CORRECTION (E4" in TTXT, \
        "the verbatim-migrated §3b A4 needs its correction block"
    assert "RETENTION OBLIGATION" in ETXT or "retained until" in ETXT
    assert "retained until" in TTXT.lower() or "RETAINED until" in TTXT


# ---------------------------------------------------------------------
# scripts
# ---------------------------------------------------------------------

def test_wave_script_prereg_paths_agree():
    """Designer B trap 4: the provenance heredoc's prereg path is a
    LITERAL; a copy that misses it stamps R1's sha into R2's provenance."""
    txt = WAVE.read_text()
    m = re.search(r'^PREREG="([^"]+)"', txt, re.M)
    assert m and m.group(1) == "configs/eval/ch5_r2_offsh.yaml"
    heredoc = re.findall(r'"prereg_sha256": sha\("([^"]+)"\)', txt)
    assert heredoc == ["configs/eval/ch5_r2_offsh.yaml"], heredoc
    m = re.search(r'^OUT="([^"]+)"', txt, re.M)
    assert m and m.group(1) == ECFG["results_dir"]
    m = re.search(r'ARMS="\$\{ARMS:-([^}]+)\}"', txt)
    assert m and m.group(1).split() == ["T66", "T75", "T83"]
    assert re.search(r"R4S\*\)\s*echo 60", txt), \
        "R4S* arms are search seats and need the 60-poll stall budget"
    assert "ch5_r2_grade.py" in txt


def test_preflight_has_the_cosched_check_and_r2_sha():
    txt = PREFLIGHT.read_text()
    assert 'pgrep -f "rl\\.train"' in txt, \
        "the no-co-scheduled-training check (FP is time-budgeted)"
    assert "configs/eval/ch5_r2_offsh.yaml" in txt
    assert "simulator: *4" in txt and "git status --porcelain" in txt


def test_vssh_finals_home_is_declared_and_consistent():
    """r2_review_1 MF-3 / r2_review_2 MF-1: the finals' path must be
    DECLARED, and the grader must read exactly it."""
    vf = ECFG["vssh_finals"]
    assert vf["dir"] == "results/ch5_r2"
    assert "--out results/ch5_r2/final_s<N>.json" in vf["produced_by"]
    assert "--episodes 3000" in vf["produced_by"]
    gtxt = (REPO / "scripts/ch5_r2_grade.py").read_text()
    assert 'prereg["vssh_finals"]' in gtxt, "the grader must read the DECLARED path"
    # and absence must be UNGRADED, never silent
    r = grade.grade_read({"s66": 0.37, "s75": 0.36, "s83": 0.38},
                         {"s66": 3000, "s75": 3000, "s83": 3000})
    assert r["vs_sh"]["pass"] is None and "UNGRADED" in r["vs_sh"]["note"]
    assert r["F1_falsifier"]["pass"] is None


def test_vs_sh_and_f1_survive_cell_k():
    """r2_review_1 MF-2: the falsifier must not go silent exactly when a
    lane has died."""
    r = grade.grade_read({"s66": 0.50, "s75": 0.50},
                         {"s66": 3000, "s75": 3000},
                         sh_rates={"s66": 0.50, "s75": 0.49})
    assert r["cell"] == "K"
    assert r["vs_sh"]["x_cell"] == "XK"
    assert r["F1_falsifier"]["fires"] is True and r["F1_falsifier"]["k"] == 2
    assert "XK" in ETXT, "the XK cell must be named in the header's X-table"


def test_the_mirror_permutation_cell_is_named():
    """r2_review_1 MF-5: 'permutation separates, credit line does not'
    is reachable at delta in (0.0587, BAR) and must carry a sentence."""
    r = grade.grade_read({"s66": 0.400, "s75": 0.398, "s83": 0.402},
                         {"s66": 3000, "s75": 3000, "s83": 3000})
    assert r["cell"] == "P2" and r["permutation"]["fires"] is True
    assert "named_cell_mirror" in r
    assert "permutation" in ETXT and "MIRROR CELL" in ETXT


def test_the_pair_flip_edit_is_licensed_and_scoped():
    """r2_review_2 MF-3: the rerun rule needs a licensed mechanism or it
    contradicts the blinding attestation."""
    assert "THE PAIR FLIP" in ETXT
    assert "PRE-REGISTERED" in ETXT and "rerun_pairs" in ETXT
    assert "No other key of the arm may move" in ETXT


def test_preflight_refuses_pending_attestation():
    txt = PREFLIGHT.read_text()
    assert "status: PENDING" in txt, "r2_review_2 SF-3: refuse to launch un-attested"


def test_wave_provenance_is_never_truncated():
    txt = WAVE.read_text()
    assert 'if [ -f "$PROV" ]' in txt, \
        "r2_review_2 SF-1: a second invocation must not overwrite the T arms' stamp"


def test_fleet_gates_gate_the_verdict():
    """r2_review_1 MF-4: a CREDIT line must never print beside a failed
    D-A or R0-f."""
    gtxt = (REPO / "scripts/ch5_r2_grade.py").read_text()
    assert "void_reason" in gtxt and "fleet_fail" in gtxt


def test_the_grader_selftest_passes():
    r = subprocess.run([sys.executable, str(REPO / "scripts/ch5_r2_grade.py"),
                        "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELFTEST PASS" in r.stdout

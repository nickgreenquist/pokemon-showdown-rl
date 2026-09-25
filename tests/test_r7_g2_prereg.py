"""R7 G2's pre-reg (`configs/eval/r7_g2.yaml`, RATIFIED r2, AMENDED r3 to FP@N): the
L-op arm and the greedy anchor are the SAME committee, the L-op's dials pass their
signature-derived checks, the credit line is restated verbatim with the larger-of
clause, the usernames are distinct, the arm kind is the harness's, and every R-phase
arm reads off FP@N 25k/12k. Engine-free."""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREREG = ROOT / "configs/eval/r7_g2.yaml"
CREDIT = ("a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the "
          "LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed "
          "from the per-seed finals at read time.")


def _p():
    return yaml.safe_load(PREREG.read_text())


def test_the_lop_arm_and_the_anchor_are_the_same_committee():
    p = _p()
    arms = p["arms"]
    assert arms["G2G"]["kind"] == "ensemble_seat" and arms["G2L"]["kind"] == "native_seat"
    assert arms["G2G"]["lanes"] == arms["G2L"]["ensemble_members"]
    assert arms["G2L"]["seat"] in arms["G2L"]["ensemble_members"]
    assert arms["G2G"]["battles"] == arms["G2L"]["battles"] == 3200   # r2: +0.025 binds at 3200 (the design review)
    assert p["phases"]["R"] == ["G2G", "G2L"], "the control runs FIRST"
    assert set(arms["G2G"]["lanes"]) <= set(p["checkpoints"])


def test_the_lop_dials_pass_their_signature_derived_checks():
    from rl.search import native
    from rl.search.lop import lop_from

    for name in ("G2SM", "G2SMN", "G2L"):
        lop = lop_from(_p()["arms"][name]["lop"])
        assert native.dials_from(lop["solve"]) == {"cols_k": 4, "chance_s": 2, "tau": 0.05}
        assert lop["worlds"] == 8 and lop["margin_gate"] == 0.01


def test_the_credit_line_is_verbatim_and_names_the_clustered_clause():
    text = " ".join(_p()["decision_rule"]["credit_line_verbatim"].split())
    assert CREDIT in text
    assert "EXACTLY +0.025" in text


def test_usernames_are_distinct_and_the_kind_is_registered():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ch3_fp_h2h

    arms = _p()["arms"]
    names = [a[k] for a in arms.values() for k in ("seat_username", "fp_username")]
    assert len(names) == len(set(names)), names
    assert all(a["kind"] in ch3_fp_h2h.ARM_KINDS for a in arms.values())


def test_r2_carries_the_reviews_gates():
    """The design review's findings, pinned: one env for both arms, the runner's
    standing gates, the concurrency convention, a void action, rate-based
    operator gates, and the pinned FP parallelism."""
    p = _p()
    names = {g["name"] for g in p["R0_gates"]}
    assert {"G_SAME_PROGRAM", "G_RUNNER", "G_CONCURRENCY", "G_OPERATOR_RAN", "G_MATCHED_GREEDY", "G2G_SANITY"} <= names
    conc = next(g for g in p["R0_gates"] if g["name"] == "G_CONCURRENCY")["check"]
    assert "concurrent_decision_rate > 0.01" in conc and "DISCLOSED" in conc
    assert "void" in p["decision_rule"] and "G2L-only re-run does not count" in " ".join(p["decision_rule"]["void"].split())
    assert p["fp"]["search_parallelism"] == 1
    assert "pkmn-engine-r7" in p["env"] and "BOTH arms" in p["env"]
    assert "delta < -0.025 AND |delta| > 2*se_diff" in p["decision_rule"]["negative"]
    assert "stays owed" in " ".join(p["decision_rule"]["clears"].split())


def test_r3_reads_off_fp_at_n_and_never_gates_on_an_fp20_band():
    """AMENDMENT r3 (maintainer 2026-09-25: "G2 should be F@N. No one should run outdated F@20
    anymore"): every R-phase arm is FP@N 25k/12k -- fp_arms_parallel.py forces --slots 1 and a
    quiet box on any arm WITHOUT search_iterations, so a dropped key would silently turn the read
    back into FP@20 -- the per-arm counters replace the quiet-box gate, and the FP@20 sanity band
    is a disclosure naming both instruments, never a gate."""
    p = _p()
    assert p["phases"]["smoke"] == ["G2SMN"], "G2SM ran on FP@20 before r3 and is never re-listed"
    for name in p["phases"]["smoke"] + p["phases"]["R"]:
        arm = p["arms"][name]    # inside the ARM: the runner reads the budget from the arm only (MA-10)
        assert (arm["search_iterations"], arm["search_iterations_early"], arm["search_time_ms"]) == (25000, 12000, 20), name
    names = {g["name"] for g in p["R0_gates"]}
    assert "G_FPN_COUNTERS" in names and "G_QUIET_BOX" not in names
    counters = next(g for g in p["R0_gates"] if g["name"] == "G_FPN_COUNTERS")["check"]
    assert "fpn_counters_ok" in counters and "INVALID" in counters
    sanity = next(g for g in p["R0_gates"] if g["name"] == "G2G_SANITY")["check"]
    assert "NEVER A GATE" in sanity and "BOTH instruments" in sanity
    assert "FP@N 25k/12k" in p["decision_rule"]["primary"] and "FP@20" not in p["decision_rule"]["primary"]


def test_the_rl_tree_is_stamped_at_launch_not_at_write_time(monkeypatch, tmp_path):
    """docs/CLEANUP.md L10: `rl_git_sha` / `rl_git_dirty` were read inside run() AFTER the battles, so an arm that
    spanned a commit named the later tree. main() now reads them before asyncio.run: a commit that lands while the
    battles run must reach `finish_git_sha` and nothing else."""
    import json
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ch3_fp_h2h

    tree = {"sha": "sha-at-launch"}
    monkeypatch.setattr(ch3_fp_h2h, "_git_sha", lambda: tree["sha"])
    monkeypatch.setattr(ch3_fp_h2h, "_rl_provenance",
                        lambda: {"rl_package": "rl", "rl_git_sha": tree["sha"], "rl_git_dirty": False})

    async def battles_during_which_a_commit_lands(prereg, arm_name, battles, tag):
        tree["sha"] = "sha-committed-mid-arm"
        return {"gate_all_challenges_resolved": True}

    monkeypatch.setattr(ch3_fp_h2h, "run", battles_during_which_a_commit_lands)
    prereg = tmp_path / "p.yaml"
    prereg.write_text(yaml.safe_dump({"results_dir": str(tmp_path / "out"), "arms": {"X": {"battles": 1}}}))
    monkeypatch.setenv("POKEMON_RL_ENCODER_V2", "1")
    monkeypatch.setenv("POKEMON_RL_ENCODER_IDS", "1")
    monkeypatch.setattr(sys, "argv", ["ch3_fp_h2h.py", "--prereg", str(prereg), "--arm", "X", "--tag", "t"])
    ch3_fp_h2h.main()
    out = json.loads((tmp_path / "out" / "t.json").read_text())
    assert out["rl_git_sha"] == out["launch_git_sha"] == "sha-at-launch"
    assert out["finish_git_sha"] == "sha-committed-mid-arm"


def test_rl_provenance_names_the_imported_tree():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import ch3_fp_h2h
    import rl

    prov = ch3_fp_h2h._rl_provenance()
    assert prov["rl_package"] == str(pathlib.Path(rl.__file__).resolve().parent)
    assert prov["rl_git_sha"] is None or len(prov["rl_git_sha"]) == 40
    assert prov["rl_git_sha"] is None or isinstance(prov["rl_git_dirty"], bool)

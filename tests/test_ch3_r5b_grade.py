"""CH3 R5b BI-6 (grader) — offline gates. No server, no battles.

The law itself (land/check_partition/se_terms_r2) is ch3_r2_grade's,
already pinned by its own selftest; what is pinned HERE is the r5b glue:

* the full --selftest (band boundaries, B1a/B1b, PL cells, anchor cells,
  KILL, F-P arithmetic, Q7/Q8 sim pins at reduced reps) runs green;
* refusals: non-RATIFIED status, credit-line drift, an unquoted
  "[MAINTAINER RULING" bracket, a PENDING B-10 transcript key, a
  missing/failed T-gate readout — each fails loudly BEFORE any number is
  read;
* the registered pre-reg passes every static refusal except the
  tree-cleanliness ones (exercised only at grade time).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_r5b_grade as grade  # noqa: E402

PREREG = REPO / "configs/eval/ch3_r5b_exit.yaml"


def test_selftest_green():
    grade.selftest(reps=1500)


def _prereg_copy(tmp_path, mutate):
    text = PREREG.read_text()
    text = mutate(text)
    p = tmp_path / "prereg.yaml"
    p.write_text(text)
    return yaml.safe_load(text), str(p)


def _no_git_refusals(monkeypatch, tmp_path):
    monkeypatch.setattr(grade, "_git", lambda cmd: "")
    ok = tmp_path / "t_gate_readout.json"
    ok.write_text(json.dumps({"cell": "T-PASS"}))
    monkeypatch.setattr(grade, "T_GATE_READOUT", str(ok))


def test_registered_prereg_passes_static_refusals(monkeypatch, tmp_path):
    _no_git_refusals(monkeypatch, tmp_path)
    prereg = yaml.safe_load(PREREG.read_text())
    # B-10 transcripts are still PENDING pre-stamp; neutralize ONLY them so
    # the remaining static refusals (status, credit line, brackets) are what
    # this test exercises.
    for key in ("temperature_grid_transcript", "placebo_dose_search_transcript",
                "a0_selfplay_measured", "b7_fg4_transcript"):
        prereg[key] = "stamped"
    monkeypatch.setattr(
        grade.yaml, "safe_load", lambda text, _p=prereg: _p)
    grade.refuse_checks(prereg, str(PREREG))


def test_refuses_draft_status(monkeypatch, tmp_path):
    _no_git_refusals(monkeypatch, tmp_path)
    prereg, path = _prereg_copy(
        tmp_path, lambda t: t.replace(
            'status: "RATIFIED 2026-08-24', 'status: "DRAFT r3 2026-08-24', 1))
    with pytest.raises(AssertionError, match="not RATIFIED"):
        grade.refuse_checks(prereg, path)


def test_refuses_unquoted_ruling_bracket(monkeypatch, tmp_path):
    _no_git_refusals(monkeypatch, tmp_path)
    prereg, path = _prereg_copy(
        tmp_path, lambda t: t + "\n# [MAINTAINER RULING PENDING — new question]\n")
    for key in ("temperature_grid_transcript", "placebo_dose_search_transcript",
                "a0_selfplay_measured", "b7_fg4_transcript"):
        prereg[key] = "stamped"
    with pytest.raises(AssertionError, match="MAINTAINER RULING"):
        grade.refuse_checks(prereg, path)


def test_refuses_pending_transcript(monkeypatch, tmp_path):
    _no_git_refusals(monkeypatch, tmp_path)
    prereg = yaml.safe_load(PREREG.read_text())
    assert "PENDING" in str(prereg["temperature_grid_transcript"])
    with pytest.raises(AssertionError, match="PENDING"):
        grade.refuse_checks(prereg, str(PREREG))


def test_refuses_credit_line_drift(monkeypatch, tmp_path):
    _no_git_refusals(monkeypatch, tmp_path)
    prereg = yaml.safe_load(PREREG.read_text())
    prereg["credit_line"] = prereg["credit_line"].replace("0.025", "0.02")
    with pytest.raises(AssertionError, match="byte-equal"):
        grade.refuse_checks(prereg, str(PREREG))


def test_refuses_failed_t_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(grade, "_git", lambda cmd: "")
    bad = tmp_path / "t_gate_readout.json"
    bad.write_text(json.dumps({"cell": "T-FAIL/NULL"}))
    monkeypatch.setattr(grade, "T_GATE_READOUT", str(bad))
    prereg = yaml.safe_load(PREREG.read_text())
    for key in ("temperature_grid_transcript", "placebo_dose_search_transcript",
                "a0_selfplay_measured", "b7_fg4_transcript"):
        prereg[key] = "stamped"
    with pytest.raises(AssertionError, match="D-1"):
        grade.refuse_checks(prereg, str(PREREG))


def test_prereg_credit_line_is_byte_equal_right_now():
    prereg = yaml.safe_load(PREREG.read_text())
    assert prereg["credit_line"] == grade.CREDIT_LINE


def test_wave_runner_bash_syntax():
    r = subprocess.run(["bash", "-n", str(REPO / "scripts/ch3_r5b_run.sh")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_prereg_jobs_resolve_through_unmodified_driver():
    import ch3_eval
    prereg = yaml.safe_load(PREREG.read_text())
    jobs = ch3_eval._jobs(prereg)
    want = [f"x0_{l}" for l in grade.LANES] + \
           [f"x1_d{l[1:]}" for l in grade.LANES] + \
           [f"pl_p{l[1:]}" for l in grade.LANES]
    assert sorted(jobs) == sorted(want)


def test_amendment_headline_cap_b1a_unreachable():
    assert grade.b1_split("B1", "GREEN", amended=True) == "B1b"
    assert grade.b1_split("B1", "GREEN", amended=False) == "B1a"
    assert grade.b1_split("B3", "GREEN", amended=True) == "B3"


def test_prereg_carries_amendment_and_gates_grade_it():
    prereg = yaml.safe_load(PREREG.read_text())
    assert "capture" in prereg["d2_rule_amended"].lower() or \
           "FIFTH" in prereg["d2_rule_amended"]
    assert "gain-aware" in prereg["d2_amendment_provenance"]
    assert "B1a unreachable" in prereg["headline_cap_under_amendment"]

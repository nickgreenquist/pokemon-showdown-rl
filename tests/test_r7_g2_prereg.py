"""R7 G2's pre-reg (`configs/eval/r7_g2.yaml`, DRAFT): the L-op arm and the greedy
anchor are the SAME committee, the L-op's dials pass their signature-derived
checks, the credit line is restated verbatim with the larger-of clause, the
usernames are distinct, and the arm kind is the harness's. Engine-free."""

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
    assert arms["G2G"]["battles"] == arms["G2L"]["battles"] == 3000
    assert p["phases"]["R"] == ["G2G", "G2L"], "the control runs FIRST"
    assert set(arms["G2G"]["lanes"]) <= set(p["checkpoints"])


def test_the_lop_dials_pass_their_signature_derived_checks():
    from rl.search import native
    from rl.search.lop import lop_from

    for name in ("G2SM", "G2L"):
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

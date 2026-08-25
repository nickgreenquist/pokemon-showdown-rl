"""CH3 R4 BI-5 (anchor machinery) — offline gates. No server, no battles.

The pre-reg (configs/eval/ch3_r4_ensemble_critic.yaml, ANCHOR BATTERY)
requires this machinery to be built, tested and committed BEFORE the main
sweep launches, because the battery fires only under result-knowledge and
must therefore exist result-blind (review 1 finding 12). What is pinned here:

* the FE3 kind assert — an unknown `kind` used to run the GREEDY seat
  SILENTLY (review 2 blocker 2);
* F5 evaluator resolution in BOTH drivers: pool-minus-seat-lane, exactly 3
  members, own key absent, own agent excluded by IDENTITY, member shas in
  the provenance;
* the CE0/CE3 output-prefix separation (the falsifier's literal "sa" prefix
  would have let the two arms silently "resume" each other);
* the anchor grader's --selftest;
* `bash -n` on the crash-forfeit runner.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_fp_h2h  # noqa: E402
import ch3_r4_anchor_grade as grade_mod  # noqa: E402
import ch3_r4_anchors as anchors  # noqa: E402

PREREG = str(REPO / "configs/eval/ch3_r4_ensemble_critic.yaml")
FP_PREREG = str(REPO / "configs/eval/ch3_r4_fp_anchor.yaml")
PINS = {
    "s62": {"path": "runs/a.pt", "sha256": "aa"},
    "s63": {"path": "runs/b.pt", "sha256": "bb"},
    "s64": {"path": "runs/c.pt", "sha256": "cc"},
    "s65": {"path": "runs/d.pt", "sha256": "dd"},
    "clone": {"path": "runs/e.pt", "sha256": "ee"},
}


class _Stub:
    def __init__(self, lane):
        self.lane = lane


# --------------------------------------------------------------------------
# the FE3 kind assert (scripts/ch3_fp_h2h.py)
# --------------------------------------------------------------------------


def test_fp_unknown_kind_fails_loudly():
    prereg = {"checkpoints": PINS, "arms": {
        "BAD": {"kind": "fp_h2h", "battles": 1, "dose": "M",
                "seat_username": "u", "fp_username": "v"}}}
    with pytest.raises(AssertionError, match="not in"):
        asyncio.run(ch3_fp_h2h.run(prereg, "BAD", 1, "t"))


def test_fp_registered_kinds_are_the_registered_set():
    """The R4-era contract is that an UNKNOWN kind fails loudly (tested in
    test_fp_unknown_kind_fails_loudly), not that the set never grows. CH4 R1
    registered two more via its ratified pre-reg: sampled_seat (arm S1) and
    fp_vs_clone (arms C1/C1b). Update this tuple only alongside a pre-reg."""
    assert ch3_fp_h2h.ARM_KINDS == (
        "greedy_seat", "search_seat", "sampled_seat", "fp_vs_clone")


def test_fp_anchor_config_matches_the_prereg():
    """configs/eval/ch3_r4_fp_anchor.yaml is DERIVED: every pin and every FE3
    field must be byte-equal to the registered pre-reg's."""
    prereg = yaml.safe_load(Path(PREREG).read_text())
    fp_cfg = yaml.safe_load(Path(FP_PREREG).read_text())
    assert fp_cfg["checkpoints"] == prereg["checkpoints"]
    fe3, arm = prereg["anchor_arms"]["FE3"], fp_cfg["arms"]["FE3"]
    for key in ("kind", "dose", "battles", "seat_username", "fp_username",
                "evaluator", "comparator"):
        assert arm[key] == fe3[key], key
    assert arm["seat"] == fe3["seat"]
    assert arm["kind"] in ch3_fp_h2h.ARM_KINDS
    assert fp_cfg["fp"]["search_time_ms"] == fe3["search_time_ms"]
    assert fp_cfg["crash_forfeit"]["max_relaunches"] == grade_mod.MAX_RELAUNCHES
    assert fp_cfg["anchors"]["fs_e0_frozen"] == grade_mod.FP_FROZEN_COMPARATOR
    assert fp_cfg["anchors"]["fp_250_pinned_literal"] == grade_mod.FP_PINNED_THRESHOLD


# --------------------------------------------------------------------------
# F5 evaluator resolution, both drivers
# --------------------------------------------------------------------------


@pytest.mark.parametrize("mod,patch_target", [
    (ch3_fp_h2h, "_build_agent"),
    (anchors, "_load_peer"),
])
def test_loo_excludes_the_seat_lane_and_resolves_three(mod, patch_target,
                                                       monkeypatch):
    seen = []
    if patch_target == "_build_agent":
        monkeypatch.setattr(mod, patch_target,
                            lambda spec: seen.append(spec["path"]) or _Stub(spec["path"]))
    else:
        monkeypatch.setattr(mod, patch_target,
                            lambda prereg, lane: seen.append(lane) or _Stub(lane))
    agent0 = _Stub("s65")
    evaluator, prov = mod._resolve_evaluator(
        {"checkpoints": PINS}, "s65",
        {"kind": "loo", "pool": ["s62", "s63", "s64", "s65"]}, agent0,
    )
    assert prov["kind"] == "loo"
    assert prov["members"] == ["s62", "s63", "s64"]
    assert "s65" not in prov["members"]
    assert prov["member_sha256"] == ["aa", "bb", "cc"]
    assert len(evaluator["agents"]) == 3
    assert all(a is not agent0 for a in evaluator["agents"])
    assert "pool" not in evaluator
    assert len(seen) == 3


@pytest.mark.parametrize("mod,patch_target", [
    (ch3_fp_h2h, "_build_agent"),
    (anchors, "_load_peer"),
])
def test_loo_pool_of_wrong_size_is_f5_fail(mod, patch_target, monkeypatch):
    monkeypatch.setattr(mod, patch_target, lambda *a, **k: _Stub("x"))
    with pytest.raises(AssertionError, match="F5: loo pool resolved to"):
        mod._resolve_evaluator(
            {"checkpoints": PINS}, "s65",
            {"kind": "loo", "pool": ["s62", "s63", "s65"]}, _Stub("s65"),
        )


@pytest.mark.parametrize("mod,patch_target", [
    (ch3_fp_h2h, "_build_agent"),
    (anchors, "_load_peer"),
])
def test_loo_rejects_the_lanes_own_agent_by_identity(mod, patch_target,
                                                     monkeypatch):
    agent0 = _Stub("s65")
    monkeypatch.setattr(mod, patch_target, lambda *a, **k: agent0)
    with pytest.raises(AssertionError, match="own agent object"):
        mod._resolve_evaluator(
            {"checkpoints": PINS}, "s65",
            {"kind": "loo", "pool": ["s62", "s63", "s64", "s65"]}, agent0,
        )


@pytest.mark.parametrize("mod", [ch3_fp_h2h, anchors])
def test_no_evaluator_key_is_the_untouched_path(mod):
    assert mod._resolve_evaluator({}, "s65", None, _Stub("s65")) == (None, None)
    assert mod._resolve_evaluator({}, "s65", {}, _Stub("s65")) == (None, None)


# --------------------------------------------------------------------------
# per-arm output prefixes (CE0 / CE3 must not collide)
# --------------------------------------------------------------------------


def _chunk(path: Path, arm: str, wr: float, evaluator=None):
    rep = {
        "arm": arm, "kind": "search_h2h", "seat1": "s65", "seat2": "clone",
        "chunk": 0, "episodes": 100, "seed_start": 0,
        "eval/win_rate": wr, "wins_from_returns": wr, "ties_from_returns": 0.0,
        "mask_desyncs_delta": 0, "started_at": 1.0, "finished_at": 2.0,
        "search_dose": "M", "search/decisions": 500,
        "search/placeholder_skips": 54, "search/flips": 10,
        "search/searched_decisions": 446, "search/timeouts": 0,
        "search/ms_mean": 73.2, "search/leaves_mean": 353.0,
        "search/leaves_max": 900,
    }
    if evaluator:
        rep["evaluator"] = evaluator
    path.write_text(json.dumps(rep) + "\n")


def test_ce0_and_ce3_finals_do_not_collide(tmp_path):
    loo = {"kind": "loo", "members": ["s62", "s63", "s64"],
           "member_sha256": ["aa", "bb", "cc"]}
    _chunk(tmp_path / "ce0.chunk00.json", "CE0", 0.860)
    _chunk(tmp_path / "ce3.chunk00.json", "CE3", 0.895, evaluator=loo)
    anchors._merge(PREREG, "CE0", tmp_path, 1)
    anchors._merge(PREREG, "CE3", tmp_path, 1)
    ce0 = json.loads((tmp_path / "ce0.final.json").read_text())
    ce3 = json.loads((tmp_path / "ce3.final.json").read_text())
    assert ce0["eval/win_rate"] == 0.860 and ce3["eval/win_rate"] == 0.895
    assert "evaluator" not in ce0 and ce3["evaluator"] == loo
    assert ce0["prereg_sha256"] == ce3["prereg_sha256"]
    assert ce0["prereg"] == PREREG


def test_anchor_driver_refuses_the_fp_arm():
    prereg = yaml.safe_load(Path(PREREG).read_text())
    for name in ("CA", "CE0", "CE3"):
        assert anchors._arm_spec(prereg, name)["kind"] in ("greedy_h2h", "search_h2h")
    with pytest.raises(AssertionError, match="ch3_fp_h2h"):
        anchors._arm_spec(prereg, "FE3")


# --------------------------------------------------------------------------
# the grader + the runner
# --------------------------------------------------------------------------


def test_anchor_grade_selftest(capsys):
    grade_mod.selftest(PREREG)
    assert "ALL GREEN" in capsys.readouterr().out


def test_anchor_grade_selftest_via_cli():
    rc = subprocess.run(
        [sys.executable, str(REPO / "scripts/ch3_r4_anchor_grade.py"), "--selftest"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert rc.returncode == 0, rc.stderr
    assert "ALL GREEN" in rc.stdout


def test_composite_precedence_is_the_preregs():
    prereg = yaml.safe_load(Path(PREREG).read_text())
    assert prereg["composite_transfer_precedence"] == grade_mod.COMPOSITE_PRECEDENCE


def test_fp_runner_bash_syntax():
    rc = subprocess.run(["bash", "-n", str(REPO / "scripts/ch3_r4_fp_runner.sh")],
                        capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr


def test_fp_runner_is_bash32_safe():
    """No ${var,,} case-mangling, no associative arrays, no wait -n, no
    mapfile — macOS ships bash 3.2 and the wave/runner landmine is real."""
    src = Path(REPO / "scripts/ch3_r4_fp_runner.sh").read_text()
    code = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    for banned in (",,}", "declare -A", "wait -n", "mapfile", "readarray", "^^}"):
        assert banned not in code, banned
    # liveness is output-file PROGRESS; the crash cap is the VOID marker
    assert "TOO_MANY_CRASHES" in code
    assert "MAX_RELAUNCHES" in code
    assert "wc -c" in code and "Winner:" in code
    # no directory-existence liveness test anywhere in the loop
    assert "[ -d " not in code and "[[ -d " not in code

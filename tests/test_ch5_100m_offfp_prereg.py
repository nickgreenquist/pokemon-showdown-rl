"""Username + protocol guards for the 100M primary's runner-facing spec.

The R2 precedent (tests/test_ch5_r2_prereg.py): username collisions and
prefix relations have burned hours (poisoned pairs, misleading
TimeoutErrors), so every name ever issued is asserted pairwise distinct
and prefix-free before a wave may run. Protocol keys are pinned to the
RATIFIED pre-reg's frozen values (configs/showdown_sp_100m.yaml)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / "configs/eval/ch5_100m_offfp.yaml").read_text())


def _names(block):
    out = []
    for pairs in (block.get("pairs", {}), block.get("rerun_pairs", {})):
        for pair in pairs.values():
            out += [pair["seat"], pair["fp"]]
    return out


def _all_issued_names():
    names = _names(SPEC["usernames"])
    for other in ("configs/eval/ch5_r1_offsh.yaml", "configs/eval/ch5_r2_offsh.yaml"):
        doc = yaml.safe_load((ROOT / other).read_text())
        u = doc.get("usernames", {})
        names += _names(u)
        for pair in u.get("burned_pairs_r10", {}).values():
            if isinstance(pair, dict):
                names += [v for v in pair.values() if isinstance(v, str)]
    return names


def test_usernames_distinct_and_prefix_free():
    names = _all_issued_names()
    assert len(names) == len(set(names)), "duplicate username issued"
    for a in names:
        for b in names:
            if a != b:
                assert not b.startswith(a), f"{a!r} is a prefix of {b!r}"


def test_arms_match_ratified_protocol():
    for arm_name in ("T104", "T112", "T120"):
        arm = SPEC["arms"][arm_name]
        assert arm["kind"] == "greedy_seat"
        assert arm["battles"] == 3000
        assert arm["search_time_ms"] == 20
        assert arm["seat"] == f"s{arm_name[1:]}"


def test_checkpoints_are_the_crossing_rungs_on_disk():
    for lane, spec in SPEC["checkpoints"].items():
        p = ROOT / spec["path"]
        assert p.exists(), f"{lane}: {p} missing"
        assert spec["step"] >= 100_000_000
        assert p.name == f"ckpt_{spec['step']:09d}.pt"


def test_results_dir_matches_grader_input():
    assert SPEC["results_dir"] == "results/ch5_100m"

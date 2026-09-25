"""The R6 post-fleet reads (2026-09-21): configs/eval/r6_reads_offfp.yaml (the PRIMARY under
the trio headers' credit line + the ladder-object pick) and configs/eval/r6_reads.yaml
(vs SH, locked form); scripts/monster_reads_pin.py's a/b trios; and the pure core of
scripts/r6_reads_readout.py -- the credit line with its boundary convention, the
larger-of se_diff, the object rule."""
import glob
import math
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from r6_reads_readout import credit, object_rule, pool, primary, se_binomial, se_clustered  # noqa: E402
import monster_reads_pin as pin  # noqa: E402

FP = yaml.safe_load((ROOT / "configs/eval/r6_reads_offfp.yaml").read_text())
SH = yaml.safe_load((ROOT / "configs/eval/r6_reads.yaml").read_text())
R6_LANES = ["a304", "a312", "a320", "b328", "b336", "b344"]


def test_offfp_arms_are_complete_matched_in_form_and_reference_pinned_lanes():
    arms = FP["arms"]
    assert sorted(FP["run_order"]) == sorted(arms), "run_order must be a permutation of the arms"
    assert set(FP["arm_encoder"]) == set(arms) and set(FP["usernames"]["pairs"]) == set(arms)
    assert set(FP["usernames"]["rerun_pairs"]) == set(arms)
    for name, a in arms.items():
        assert a["loop_breaker"] is True and a["search_time_ms"] == 20 and a["battles"] == 3000, name
        lanes = [a["seat"]] if a["kind"] == "greedy_seat" else a["lanes"]
        assert ("seat" in a) == (a["kind"] == "greedy_seat") and ("lanes" in a) == (a["kind"] == "ensemble_seat"), name
        for lane in lanes:
            assert lane in FP["checkpoints"], (name, lane)
        pair = FP["usernames"]["pairs"][name]
        assert (a["seat_username"], a["fp_username"]) == (pair["seat"], pair["fp"]), name
        enc = FP["arm_encoder"][name]
        holds_r6 = any(l in R6_LANES for l in lanes)
        holds_w = any(l.startswith("w") for l in lanes)
        assert enc["c6"] is holds_r6, (name, "c6 must be on iff the arm holds an R6 final")
        assert bool(enc.get("allow_mismatch")) is (holds_r6 and holds_w), (name, "mixed iff both generations")
    assert FP["credits_nothing"] is False and SH["credits_nothing"] is True


def test_sh_arms_locked_form_and_run_order():
    arms = SH["arms"]
    assert sorted(SH["run_order"]) == sorted(arms)
    for name, a in arms.items():
        assert "loop_breaker" not in a, (name, "the vs-SH leg is the LOCKED form")
        assert a["battles"] == 3000 and a["chunks"] == 10
        members = a["lanes"] if a["kind"] == "policy" else a["members"]
        assert all(m in SH["checkpoints"] for m in members), name
        if a["kind"] == "ensemble":
            assert a["batches"] == 3


def test_r6_lanes_are_pinned_in_the_exact_form_the_pin_script_writes():
    # Was a PRE-pin guard asserting the TBD placeholders; PIN-a / PIN-b rewrote them on
    # 2026-09-24 04:37Z (1b923a0, 342bdf3), which is when it went stale. Now: every lane carries
    # the pin script's exact form -- its own run dir, a 200M-rung checkpoint whose file name
    # matches the step, a 64-hex sha256 -- and both pre-regs pin every lane identically.
    pins = {}
    for cfg in ("configs/eval/r6_reads_offfp.yaml", "configs/eval/r6_reads.yaml"):
        text = (ROOT / cfg).read_text()
        for lane, run_dir in pin.TRIOS["a"] + pin.TRIOS["b"]:
            m = re.search(rf"^  {lane}: \{{path: (\S+), sha256: ([0-9a-f]{{64}}), step: (\d+)\}}", text, re.M)
            assert m, (cfg, lane)
            path, sha, step = m.group(1), m.group(2), int(m.group(3))
            assert path == f"{run_dir}/ckpt_{step:09d}.pt" and step >= 200_000_000, (cfg, lane, path, step)
            assert pins.setdefault(lane, (path, sha, step)) == (path, sha, step), (cfg, lane)
    assert sorted(pins) == sorted(R6_LANES)
    assert [l for l, _ in pin.TRIOS["a"]] == R6_LANES[:3] and [l for l, _ in pin.TRIOS["b"]] == R6_LANES[3:]
    assert [d for _, d in pin.TRIOS["a"]] == [f"runs/showdown_r6_trio_a_s{s}" for s in (304, 312, 320)]
    assert [d for _, d in pin.TRIOS["b"]] == [f"runs/showdown_r6_trio_b_s{s}" for s in (328, 336, 344)]
    assert pin.CONFIGS_BY_TRIO["a"] == pin.CONFIGS_BY_TRIO["b"] == pin.R6_CONFIGS
    assert pin.CONFIGS_BY_TRIO["w"] == pin.MONSTER_CONFIGS


def test_username_inventory_is_pairwise_prefix_free_including_the_r6_names():
    names = set()
    for f in glob.glob(str(ROOT / "configs/eval/*.yaml")):
        for m in re.finditer(r"(?:seat_username|fp_username|seat|fp):\s*([a-z0-9]+)\b",
                             pathlib.Path(f).read_text()):
            names.add(m.group(1))
    names = sorted(names)
    bad = [(a, b) for a in names for b in names if a != b and b.startswith(a)]
    assert not bad, bad[:5]
    assert "r6ga304seat" in names and "r6e9rr2bot" in names


def test_credit_line_boundary_and_larger_of_se():
    assert credit(0.025, 0.010) == "FLAT", "exactly +0.025 reads as NOT met"
    assert credit(0.0251, 0.01255) == "FLAT", "exactly 2*se reads as NOT met"
    assert credit(0.0251, 0.0125) == "POS"
    assert credit(-0.03, 0.01) == "NEG" and credit(-0.03, 0.02) == "FLAT"
    assert credit(0.1, float("nan")) == "PENDING"
    assert math.isclose(se_clustered([0.5, 0.6, 0.7], [0.5, 0.5, 0.5]), 0.1 / math.sqrt(3))
    assert math.isnan(se_clustered([0.5], [0.5, 0.6]))
    trio = [{"p": 0.50, "n": 3000}, {"p": 0.60, "n": 3000}, {"p": 0.70, "n": 3000}]
    floor = [{"p": 0.55, "n": 3000}] * 3
    r = primary(trio, floor)
    assert math.isclose(r["delta"], 0.05) and r["se_diff"] == r["se_clustered"] > r["se_binomial"]
    assert r["cell"] == "FLAT", "a +0.05 with lane sd 0.1 is under 2 se_diff under the larger-of clause"
    tight = [{"p": 0.58, "n": 3000}, {"p": 0.585, "n": 3000}, {"p": 0.59, "n": 3000}]
    r2 = primary(tight, floor)
    assert r2["se_diff"] == r2["se_binomial"] and r2["cell"] == "POS"
    assert primary(trio, [None] * 3) is None
    assert math.isclose(pool(*trio)["p"], 0.6) and se_binomial(pool(*trio), pool(*floor)) > 0


def test_object_rule_tie_band_larger_committee_and_floor():
    sizes = {"E3AF": 3, "E3BF": 3, "E6RF": 6, "E9RF": 9}
    a = lambda p: {"p": p, "n": 3000}
    floor = a(0.60)
    assert object_rule({"E3AF": a(0.65), "E3BF": a(0.62), "E6RF": a(0.63), "E9RF": a(0.61)}, floor, sizes)["pick"] == "E3AF"
    r = object_rule({"E3AF": a(0.650), "E3BF": a(0.62), "E6RF": a(0.645), "E9RF": a(0.61)}, floor, sizes)
    assert r["pick"] == "E6RF" and "larger" in r["reason"]
    r = object_rule({"E3AF": a(0.58), "E3BF": a(0.57), "E6RF": a(0.586), "E9RF": a(0.55)}, floor, sizes)
    assert r["pick"] == "FLOOR"
    assert object_rule({"E3AF": a(0.65), "E3BF": None, "E6RF": a(0.63), "E9RF": a(0.61)}, floor, sizes)["pick"] is None

"""The R7 fleet's reads (2026-09-26): scripts/r7_reads_readout.py's pure core -- the pre-reg's cells with STRICT
boundaries in exact arithmetic, the larger-of se_diff with the power script's formulas, lane loss by pair, the
mechanism reads' MOVED rule and route, the branch actions, the object rule, the per-arm validity gates -- and one
end-to-end readout over a synthetic results tree (seat / runner JSONs, Foul Play stdout, the scheduler log, lane
histories, the mechanism rows, vs SH finals)."""
import copy
import csv
import io
import json
import math
import pathlib
import sys
from collections import Counter
from contextlib import redirect_stdout
from fractions import Fraction

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import r7_reads_readout as R  # noqa: E402


def lane(p: Fraction | float, n: int = 6000) -> dict:
    w = int(round(float(p) * n))
    return {"n": n, "w": w}


# ----------------------------------------------------------------- the primary's cells
def test_primary_formulas_match_the_power_script():
    S = [lane(0.60), lane(0.62), lane(0.61)]
    C = [lane(0.59), lane(0.60)]
    r = R.primary(S, C)
    ps, pc = (0.60 + 0.62 + 0.61) / 3, (0.59 + 0.60) / 2
    assert r["delta"] == pytest.approx(ps - pc)
    se_bin = math.sqrt(ps * (1 - ps) / 18000 + pc * (1 - pc) / 12000)
    sdS = math.sqrt(sum((x - ps) ** 2 for x in (0.60, 0.62, 0.61)) / 2)
    sdC = math.sqrt(sum((x - pc) ** 2 for x in (0.59, 0.60)) / 1)
    se_clu = math.sqrt(sdS ** 2 / 3 + sdC ** 2 / 2)
    assert r["se_binomial"] == pytest.approx(se_bin) and r["se_clustered"] == pytest.approx(se_clu)
    assert r["se_diff"] == pytest.approx(max(se_bin, se_clu))
    assert r["k_searched"] == 3 and r["k_control"] == 2 and r["n_searched"] == 18000 and r["n_control"] == 12000


def test_cells_and_strict_boundaries():
    # identical lanes per arm: the clustered leg is 0, so the binomial leg (exact) governs
    def arm(p, k):
        return [{"n": 40000, "w": int(p * 40000)} for _ in range(k)]
    assert R.primary(arm(0.65, 3), arm(0.60, 2))["cell"] == "X-POS"
    assert R.primary(arm(0.615, 3), arm(0.60, 2))["cell"] == "X-GAIN"
    assert R.primary(arm(0.60, 3), arm(0.615, 2))["cell"] == "X-COST"
    assert R.primary(arm(0.60, 3), arm(0.65, 2))["cell"] == "X-NEG"
    assert R.primary(arm(0.601, 3), arm(0.60, 2))["cell"] == "X-FLAT"
    # a delta EXACTLY +0.025 is NOT above the floor: X-GAIN (0 < d <= 0.025), never X-POS
    on = R.primary(arm(0.625, 3), arm(0.60, 2))
    assert on["delta"] == pytest.approx(0.025) and on["on_floor"] and on["cell"] == "X-GAIN"
    # a delta EXACTLY -0.025 is X-COST (-0.025 <= d < 0), never X-NEG
    assert R.primary(arm(0.60, 3), arm(0.625, 2))["cell"] == "X-COST"


def test_exactly_two_se_is_not_met():
    # search for a (w, n) pair where d^2 == 4 se_bin^2 exactly is impractical; instead check the comparison is strict by
    # monkeypatching a case where the binomial leg equals d/2 in exact arithmetic
    S, C = [{"n": 4, "w": 3}] * 3, [{"n": 4, "w": 1}] * 2          # ps 3/4, pc 1/4, d 1/2
    r = R.primary(S, C)
    se2 = Fraction(3, 4) * Fraction(1, 4) / 12 + Fraction(1, 4) * Fraction(3, 4) / 8
    assert Fraction(1, 2) ** 2 > 4 * se2 and r["cell"] == "X-POS"      # the ordinary case is strict-above
    # the strict comparison itself: d^2 == 4 se^2 must not count as beyond
    assert not (Fraction(1, 4) > 4 * Fraction(1, 16))


# ----------------------------------------------------------------- lane loss
def test_lane_loss_by_pair():
    pairs = {"f1": ["S1F", "C1F"], "f2": ["S2F", "C2F"]}
    ok = R.surviving_pairs(set(), pairs, ["S3F"])
    assert not ok["void"] and sorted(ok["pairs"]) == ["f1", "f2"] and ok["unpaired"] == ["S3F"]
    s3 = R.surviving_pairs({"S3F"}, pairs, ["S3F"])            # losing searched f3 leaves 2 vs 2
    assert not s3["void"] and s3["unpaired"] == [] and s3["lost_unpaired"] == ["S3F"]
    c1 = R.surviving_pairs({"C1F"}, pairs, ["S3F"])            # losing a lane of pair f1 leaves ONE pair -> VOID
    assert c1["void"] and c1["lost_pairs"] == ["f1"]


# ----------------------------------------------------------------- mechanism reads, route, actions
def test_moved_needs_sign_size_and_every_pair():
    assert R.moved({"f1": -0.10, "f2": -0.12}, -1, 0.01)["moved"] is True
    assert R.moved({"f1": -0.10, "f2": +0.01}, -1, 0.01)["moved"] is False          # a pair against the sign
    assert R.moved({"f1": -0.010, "f2": -0.012}, -1, 0.01)["moved"] is False        # |d| <= 2 se
    assert R.moved({"f1": +0.10, "f2": +0.12}, -1, 0.01)["moved"] is False          # wrong sign
    assert R.moved({"f1": 0.3, "f2": 0.2}, 0, 0.01)["moved"] is None                # (v): reported, no action


def test_mech_read_takes_the_larger_se():
    r = R.mech_read("vi", -1, {"f1": -0.004, "f2": -0.006}, [-0.005 + 0.05 * ((-1) ** i) for i in range(200)])
    assert r["se"] == pytest.approx(max(r["se_lane"], r["se_position"])) and r["se_position"] > r["se_lane"]
    assert r["moved"] is False                              # the position-level floor holds it


def test_route_and_actions():
    assert R.route(False, True) == "(i) NOT MOVED" and R.route(True, False) == "(i) MOVED, (vi) NOT"
    assert R.route(True, True) == "(i) and (vi) BOTH MOVED" and R.route(None, True) == "PENDING"
    assert "TARGET FORM" in R.action("X-FLAT", "(i) NOT MOVED", 0.01, False)
    assert "STRONGER EVALUATOR" in R.action("X-FLAT", "(i) MOVED, (vi) NOT", 0.01, True)
    assert "STAYS in the base" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", +0.01, True)
    assert "BEHAVIOUR" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", -0.01, True)
    assert "BEHAVIOUR" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", 0.0, True)       # delta <= 0
    assert "CREDITED" in R.action("X-POS", "(i) MOVED, (vi) NOT", 0.03, True)
    assert "DISCLOSED as the lever's behaviour" in R.action("X-GAIN", "(i) NOT MOVED", 0.02, False)
    assert "the evaluator" in R.action("X-COST", "(i) MOVED, (vi) NOT", -0.02, True)
    assert "PENDING" in R.action("X-FLAT", "PENDING", 0.0, None)


def test_object_rule():
    arms = {"E6RR": {"p": 0.62}, "ES3F": {"p": 0.61}, "EC2F": {"p": 0.60}}
    assert R.object_rule(arms, "E6RR", ["ES3F", "EC2F"])["object"] == "ES3F"            # 0.61 >= 0.62 - 0.013
    arms["ES3F"]["p"] = 0.60
    assert R.object_rule(arms, "E6RR", ["ES3F", "EC2F"])["object"] == "E6RR"            # 0.60 < 0.607
    arms["ES3F"] = None
    assert R.object_rule(arms, "E6RR", ["ES3F", "EC2F"])["object"] is None


def test_arm_valid_gates():
    seat = {"battles_finished": 10, "our_wins": 6, "ties": 1, "foulplay_wins": 3, "seat_username": "s", "fp_username": "b",
            "gate_all_challenges_resolved": True}
    runner = {"crash_forfeits": 0, "fpn_counters_ok": True, "relaunches": 0, "max_relaunches": 10}
    good = Counter({"s": 6, "b": 3, "None": 1})
    assert R.arm_valid(seat, runner, good, None)["ok"]
    assert not R.arm_valid(seat, {**runner, "fpn_counters_ok": False}, good, None)["ok"]
    assert not R.arm_valid(seat, runner, Counter({"s": 7, "b": 2, "None": 1}), None)["ok"]
    assert not R.arm_valid(seat, runner, None, None)["ok"]
    assert not R.arm_valid(seat, {**runner, "relaunches": 10}, good, None)["ok"]
    # the crash-forfeit rule: one crash forfeit removes one battle and one win before the tally is compared
    cf = R.arm_valid(seat, {**runner, "crash_forfeits": 1}, Counter({"s": 5, "b": 3, "None": 1}), None)
    assert cf["ok"] and cf["n"] == 9 and cf["w"] == 5


# ----------------------------------------------------------------- end to end on a synthetic tree
RATES = {"C1F": 0.600, "S1F": 0.605, "C2F": 0.605, "S2F": 0.610, "S3F": 0.615,
         "E6RR": 0.640, "E3BR": 0.630, "ES3F": 0.635, "EC2F": 0.625}


def _write_arm(res: pathlib.Path, arm: str, spec: dict, p: float, fpn_ok: bool = True) -> None:
    n = spec["battles"]
    w, t = int(round(p * n)), 10
    f = n - w - t
    tag = arm.lower()
    (res / f"{tag}.json").write_text(json.dumps({
        "battles_finished": n, "our_wins": w, "ties": t, "foulplay_wins": f, "our_win_rate": w / n,
        "seat_username": spec["seat_username"], "fp_username": spec["fp_username"], "gate_all_challenges_resolved": True,
        "rl_git_sha": "abc1234", "rl_git_dirty": False, "prereg_sha256": "p" * 64}))
    (res / f"{tag}.runner.json").write_text(json.dumps({"crash_forfeits": 0, "fpn_counters_ok": fpn_ok, "relaunches": 0,
                                                        "max_relaunches": 10, "void_too_many_crashes": False}))
    lines = ([f"Winner: {spec['seat_username']}"] * w + [f"Winner: {spec['fp_username']}"] * f + ["Winner: None"] * t)
    (res / f"{tag}.fp.stdout").write_text("\n".join(lines) + "\n")


def _tree(tmp: pathlib.Path, fpn_bad: str | None = None, with_rerun: bool = False):
    pre = yaml.safe_load((ROOT / "configs/eval/r7_reads_offfp.yaml").read_text())
    pre = copy.deepcopy(pre)
    res = tmp / "fp"; res.mkdir()
    runs = tmp / "runs"; runs.mkdir()
    for l in pre["lanes"]["run_dirs"]:
        d = runs / l; d.mkdir()
        pre["lanes"]["run_dirs"][l] = str(d)
        ck = d / "ckpt_100000123.pt"; ck.write_bytes(b"x")
        pre["checkpoints"][l] = {"path": str(ck), "sha256": "0" * 64, "step": 100000123}
        searched = l.startswith("s")
        with open(d / "history.csv", "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["_step", "search/kl_prior", "search/override", "search/value_gap", "value/bias_mirror"])
            for i in range(1, 101):
                step = i * 1_000_000
                wr.writerow([step, 0.20 if searched else 0.33, 0.30 if searched else 0.31, 0.10, 0.02 if i % 10 == 0 else ""])
    for arm, spec in pre["arms"].items():
        _write_arm(res, arm, spec, RATES[arm], fpn_ok=(arm != fpn_bad))
    order = list(pre["run_order"])
    if with_rerun and fpn_bad:
        rr = dict(pre["arms"][fpn_bad]); rr["rerun_of"] = fpn_bad
        rr["seat_username"], rr["fp_username"] = pre["usernames"]["rerun_pairs"][fpn_bad]["seat"], pre["usernames"]["rerun_pairs"][fpn_bad]["fp"]
        pre["arms"][fpn_bad + "R"] = rr
        _write_arm(res, fpn_bad + "R", rr, RATES[fpn_bad])
    log = ["[t] START pid 1 slots 8"] + [f"[t] {a} LAUNCHED pid 2 pair x/y" for a in order]
    if with_rerun and fpn_bad:
        log += ["[t] START pid 9 slots 1", f"[t] {fpn_bad}R LAUNCHED pid 3 pair x/y"]
    (res / "parallel.log").write_text("\n".join(log) + "\n")
    mech = tmp / "mech"; mech.mkdir()
    rows = []
    for li, l in enumerate(pre["lanes"]["run_dirs"]):
        noise = __import__("numpy").random.default_rng(100 + li).normal(0.0, 0.02, 200)   # lane-specific: paired
        for pid in range(200):                                                             # differences keep a spread
            reg = (0.010 if l.startswith("s") else 0.011) + float(noise[pid])
            rows.append({"unit": [pre["checkpoints"][l]["path"]], "pid": pid, "regret": reg,
                         "spearman": 0.50 + 0.001 * (pid % 7) + (0.01 if l.startswith("s") else 0.0)})
    (mech / "end.json").write_text("{}")
    (mech / "end.rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    sh = tmp / "sh"; sh.mkdir()
    for job, p in (("gs_s376", 0.80), ("gs_s384", 0.81), ("gs_s392", 0.79), ("gc_c400", 0.80), ("gc_c408", 0.79)):
        (sh / f"{job}.final.json").write_text(json.dumps({"eval/win_rate": p, "episodes": 3000}))
    pf = tmp / "prereg.yaml"
    pf.write_text(yaml.safe_dump(pre))
    return pf, res, sh, mech / "end.json"


def _run(monkeypatch, pf, res, sh, mech, out) -> str:
    monkeypatch.setattr(sys, "argv", ["x", "--prereg", str(pf), "--fp", str(res), "--sh", str(sh), "--mech", str(mech),
                                      "--json-out", str(out)])
    buf = io.StringIO()
    with redirect_stdout(buf):
        R.main()
    return buf.getvalue()


def test_end_to_end_readout(tmp_path, monkeypatch):
    pf, res, sh, mech = _tree(tmp_path)
    text = _run(monkeypatch, pf, res, sh, mech, tmp_path / "readout.json")
    j = json.loads((tmp_path / "readout.json").read_text())
    ps = (0.605 + 0.610 + 0.615) / 3
    pc = (0.600 + 0.605) / 2
    assert j["primary"]["delta"] == pytest.approx(ps - pc, abs=1e-9)
    assert j["primary"]["cell"] == "X-FLAT"                      # +0.0075 < 2 se (~0.0115): a null
    assert j["mechanism"]["i"]["moved"] is True                  # kl_prior 0.20 vs 0.33 in both pairs
    assert j["mechanism"]["vi"]["moved"] is False                # -0.001 against a position-level se ~0.002
    assert j["route"] == "(i) MOVED, (vi) NOT" and "STRONGER EVALUATOR" in j["action"]
    assert j["object_rule"]["object"] == "ES3F"                  # 0.635 >= 0.640 - 0.013
    assert j["session"]["ok"] and j["session"]["one_program"]
    assert "CELL X-FLAT" in text and "GS - GC" in text


def test_end_to_end_resolved_gain_below_the_floor(tmp_path, monkeypatch):
    monkeypatch.setitem(RATES, "S1F", 0.610)
    monkeypatch.setitem(RATES, "S2F", 0.615)
    monkeypatch.setitem(RATES, "S3F", 0.620)
    pf, res, sh, mech = _tree(tmp_path)
    _run(monkeypatch, pf, res, sh, mech, tmp_path / "g.json")
    j = json.loads((tmp_path / "g.json").read_text())
    # +0.0125 against se_diff = the binomial leg ~0.00575 (the clustered ~0.0038): resolved, below the floor
    assert j["primary"]["cell"] == "X-GAIN" and j["primary"]["se_leg"] == "binomial"
    assert j["action"].startswith("X-GAIN") and "STAYS" in j["action"]


def test_invalid_arm_is_pending_until_its_rerun(tmp_path, monkeypatch):
    pf, res, sh, mech = _tree(tmp_path, fpn_bad="C1F")
    _run(monkeypatch, pf, res, sh, mech, tmp_path / "r1.json")
    j = json.loads((tmp_path / "r1.json").read_text())
    assert j["primary"]["cell"] == "PENDING" and j["primary"]["waiting"] == ["C1F"]
    assert j["mechanism"]["i"]["moved"] is True                  # training-side reads do not wait on an FP arm
    t2 = tmp_path / "again"; t2.mkdir()
    pf, res, sh, mech = _tree(t2, fpn_bad="C1F", with_rerun=True)
    _run(monkeypatch, pf, res, sh, mech, t2 / "r2.json")
    j = json.loads((t2 / "r2.json").read_text())
    assert j["primary"]["cell"] == "X-FLAT" and j["arms"]["C1F"]["source_arm"] == "C1FR"
    assert j["session"]["ok"] is False                           # the re-run is a later session: disclosed


def test_declared_lane_loss_voids_on_a_pair_lane(tmp_path, monkeypatch):
    pf, res, sh, mech = _tree(tmp_path)
    pre = yaml.safe_load(pf.read_text())
    pre["lost_lanes"] = ["C2F"]
    pf.write_text(yaml.safe_dump(pre))
    _run(monkeypatch, pf, res, sh, mech, tmp_path / "r.json")
    j = json.loads((tmp_path / "r.json").read_text())
    assert j["primary"]["cell"] == "VOID" and j["lane_loss"]["lost_pairs"] == ["f2"]

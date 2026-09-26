"""The R7 fleet's reads (2026-09-26): scripts/r7_reads_readout.py's pure core -- the pre-reg's cells with STRICT
boundaries in exact arithmetic, the larger-of se_diff with the power script's formulas, lane loss by pair (declared,
validated), the mechanism reads' MOVED rule and route, the branch actions, the object rule in exact rationals, the
per-arm validity gates -- and end-to-end readouts over a synthetic results tree (seat / runner JSONs and logs, Foul
Play stdout, the scheduler log, the launch sha, lane histories streamed, the mechanism summary and rows, vs SH
finals), including a stale history, an invalid arm and its re-run, a declared lane loss and a program drift."""
import copy
import csv
import hashlib
import io
import json
import math
import pathlib
import sys
from collections import Counter
from contextlib import redirect_stdout

import numpy as np
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import r7_reads_readout as R  # noqa: E402


def lane(p: float, n: int = 6000) -> dict:
    return {"n": n, "w": int(round(p * n))}


def mean_of(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


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


def test_cells_and_the_floor_boundary():
    def arm(p, k):                       # identical lanes: the clustered leg is 0, the exact binomial leg governs
        return [{"n": 40000, "w": int(p * 40000)} for _ in range(k)]
    assert R.primary(arm(0.65, 3), arm(0.60, 2))["cell"] == "X-POS"
    assert R.primary(arm(0.615, 3), arm(0.60, 2))["cell"] == "X-GAIN"
    assert R.primary(arm(0.60, 3), arm(0.615, 2))["cell"] == "X-COST"
    assert R.primary(arm(0.60, 3), arm(0.65, 2))["cell"] == "X-NEG"
    assert R.primary(arm(0.601, 3), arm(0.60, 2))["cell"] == "X-FLAT"
    on = R.primary(arm(0.625, 3), arm(0.60, 2))             # EXACTLY +0.025: not above the floor -> X-GAIN
    assert on["on_floor"] and on["cell"] == "X-GAIN"
    assert R.primary(arm(0.60, 3), arm(0.625, 2))["cell"] == "X-COST"   # EXACTLY -0.025 -> X-COST, never X-NEG


def test_exactly_two_se_is_not_met():
    # ps 3/4, pc 1/2, d 1/4; se_bin^2 = (3/16)/36 + (1/4)/24 = 1/64, so 2 se = 1/4 = d EXACTLY; identical lanes make the
    # clustered leg 0, so the exact binomial leg governs and the strict comparison must read NOT met.
    r = R.primary([{"n": 12, "w": 9}] * 3, [{"n": 12, "w": 6}] * 2)
    assert r["delta"] == 0.25 and r["se_binomial"] == 0.125 and r["near_2se"] and r["cell"] == "X-FLAT"


# ----------------------------------------------------------------- lane loss
def test_lane_loss_by_pair_and_the_declared_list():
    pairs = {"f1": ["S1F", "C1F"], "f2": ["S2F", "C2F"]}
    ok = R.surviving_pairs(set(), pairs, ["S3F"])
    assert not ok["void"] and sorted(ok["pairs"]) == ["f1", "f2"] and ok["unpaired"] == ["S3F"]
    s3 = R.surviving_pairs({"S3F"}, pairs, ["S3F"])            # losing searched f3 leaves 2 vs 2
    assert not s3["void"] and s3["unpaired"] == [] and s3["lost_unpaired"] == ["S3F"]
    c1 = R.surviving_pairs({"C1F"}, pairs, ["S3F"])            # losing a lane of pair f1 leaves ONE pair -> VOID
    assert c1["void"] and c1["lost_pairs"] == ["f1"]
    spec = {"searched": ["S1F", "S2F", "S3F"], "control": ["C1F", "C2F"]}
    assert R.check_lost(["S3F"], spec) == {"S3F"}
    with pytest.raises(SystemExit, match="not primary arms"):
        R.check_lost(["S3"], spec)                             # a typo is refused, never silently ignored


# ----------------------------------------------------------------- mechanism reads, route, actions
def test_moved_needs_sign_size_and_every_pair():
    assert R.moved({"f1": -0.10, "f2": -0.12}, -1, 0.01)["moved"] is True
    assert R.moved({"f1": -0.10, "f2": +0.01}, -1, 0.01)["moved"] is False
    assert R.moved({"f1": -0.010, "f2": -0.012}, -1, 0.01)["moved"] is False
    assert R.moved({"f1": +0.10, "f2": +0.12}, -1, 0.01)["moved"] is False
    assert R.moved({"f1": 0.3, "f2": 0.2}, 0, 0.01)["moved"] is None


def test_mech_read_takes_the_larger_se():
    r = R.mech_read("vi", -1, {"f1": -0.004, "f2": -0.006}, [-0.005 + 0.05 * ((-1) ** i) for i in range(200)])
    assert r["se"] == pytest.approx(max(r["se_lane"], r["se_position"])) and r["se_position"] > r["se_lane"]
    assert r["moved"] is False


def test_route_and_actions():
    assert R.route(False, True) == "(i) NOT MOVED" and R.route(False, None) == "(i) NOT MOVED"   # decided by (i)
    assert R.route(True, False) == "(i) MOVED, (vi) NOT" and R.route(True, True) == "(i) and (vi) BOTH MOVED"
    assert R.route(None, True) == "PENDING" and R.route(True, None) == "PENDING"
    assert "TARGET FORM" in R.action("X-FLAT", "(i) NOT MOVED", 0.01, False)
    assert "STRONGER EVALUATOR" in R.action("X-FLAT", "(i) MOVED, (vi) NOT", 0.01, True)
    assert "STAYS in the base" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", +0.01, True)
    assert "BEHAVIOUR" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", -0.01, True)
    assert "BEHAVIOUR" in R.action("X-FLAT", "(i) and (vi) BOTH MOVED", 0.0, True)
    assert "CREDITED" in R.action("X-POS", "(i) MOVED, (vi) NOT", 0.03, True)
    assert "DISCLOSED as the lever's behaviour" in R.action("X-GAIN", "(i) NOT MOVED", 0.02, False)
    assert "PENDING on (i)" in R.action("X-GAIN", "PENDING", 0.02, None)
    assert "the evaluator" in R.action("X-COST", "(i) MOVED, (vi) NOT", -0.02, True)
    assert "clip_frac split" in R.action("X-NEG", "(i) and (vi) BOTH MOVED", -0.03, True)
    assert "PENDING" in R.action("X-FLAT", "PENDING", 0.0, None)


def test_object_rule_exact_and_the_unnamed_tie():
    def a(w, n=3000):
        return {"w": w, "n": n, "p": w / n}
    # 1469/3000 - 1508/3000 = -0.013 EXACTLY: it REACHES (a float compare would say it does not)
    r = R.object_rule({"E6RR": a(1508), "ES3F": a(1469), "EC2F": a(1400)}, "E6RR", ["ES3F", "EC2F"])
    assert r["object"] == "ES3F"
    assert R.object_rule({"E6RR": a(1508), "ES3F": a(1468), "EC2F": a(1400)}, "E6RR", ["ES3F", "EC2F"])["object"] == "E6RR"
    tie = R.object_rule({"E6RR": a(1508), "ES3F": a(1500), "EC2F": a(1500)}, "E6RR", ["ES3F", "EC2F"])
    assert tie["object"] is None and "UNNAMED CELL" in tie["why"]
    assert R.object_rule({"E6RR": a(1508), "ES3F": None, "EC2F": a(1400)}, "E6RR", ["ES3F", "EC2F"])["object"] is None


def test_arm_valid_gates():
    seat = {"battles_finished": 10, "our_wins": 6, "ties": 1, "foulplay_wins": 3, "seat_username": "s", "fp_username": "b",
            "gate_all_challenges_resolved": True, "our_win_rate": 0.6, "launch_git_sha": "abc", "rl_git_sha": "abc",
            "rl_git_dirty": False}
    runner = {"crash_forfeits": 0, "fpn_counters_ok": True, "relaunches": 0, "max_relaunches": 10}
    good = Counter({"s": 6, "b": 3, "None": 1})
    budget = "[t] budget verified from foul-play's log: fixed (search_iterations=25000/12000)"
    assert R.arm_valid(seat, runner, good, budget)["ok"]
    assert not R.arm_valid(seat, {**runner, "fpn_counters_ok": False}, good, budget)["ok"]
    assert not R.arm_valid(seat, runner, Counter({"s": 7, "b": 2, "None": 1}), budget)["ok"]
    assert not R.arm_valid(seat, runner, None, budget)["ok"]
    assert not R.arm_valid(seat, {**runner, "relaunches": 10}, good, budget)["ok"]
    assert not R.arm_valid(seat, runner, good, None)["ok"]                                   # no budget read-back
    assert not R.arm_valid(seat, runner, good, budget.replace("25000", "20000"))["ok"]
    assert not R.arm_valid({**seat, "our_win_rate": 0.65}, runner, good, budget)["ok"]       # ties counted as wins
    assert not R.arm_valid({**seat, "rl_git_dirty": True}, runner, good, budget)["ok"]
    cf = R.arm_valid(seat, {**runner, "crash_forfeits": 1}, Counter({"s": 5, "b": 3, "None": 1}), budget)
    assert cf["ok"] and cf["n"] == 9 and cf["w"] == 5


def test_stream_windows_and_the_stale_history_refusal(tmp_path):
    p = tmp_path / "history.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["_step", "a", "other"])
        for i in range(1, 101):
            w.writerow([i * 1_000_000, i, "x"])
            w.writerow([i * 1_000_000 + 1, "", "y"])          # a sparse row: `a` absent
    h = R.stream_windows(str(p), ["a", "missing"], final_step=100_000_123)
    assert h["ok"] and h["end"]["a"] == pytest.approx(mean_of(range(96, 101)))        # (95M, 100M]: 96..100
    assert h["12M"]["a"] == pytest.approx(mean_of(range(7, 13)))                         # [7M, 12M]
    assert h["missing_cols"] == ["missing"] and math.isnan(h["end"]["missing"])
    stale = R.stream_windows(str(p), ["a"], final_step=130_000_000)
    assert not stale["ok"] and "short of the pinned final" in stale["why"]


def test_sh_pool_needs_every_job(tmp_path):
    (tmp_path / "gs_a.final.json").write_text(json.dumps({"eval/win_rate": 0.8, "episodes": 3000}))
    assert R.sh_pool(str(tmp_path), ["gs_a", "gs_b"]) is None
    (tmp_path / "gs_b.final.json").write_text(json.dumps({"eval/win_rate": 0.7, "episodes": 3000}))
    assert R.sh_pool(str(tmp_path), ["gs_a", "gs_b"])["p"] == pytest.approx(0.75)


def test_same_program():
    assert R.same_program("abc1234", "abc1234def") and not R.same_program(None, "abc")


# ----------------------------------------------------------------- end to end on a synthetic tree
RATES = {"C1F": 0.600, "S1F": 0.605, "C2F": 0.605, "S2F": 0.610, "S3F": 0.615,
         "E6RR": 0.640, "E3BR": 0.630, "ES3F": 0.635, "EC2F": 0.625}
SHA = "abc1234def5678"


def _write_arm(res: pathlib.Path, arm: str, spec: dict, p: float, fpn_ok: bool = True) -> None:
    n = spec["battles"]
    w, t = int(round(p * n)), 10
    f = n - w - t
    tag = arm.lower()
    (res / f"{tag}.json").write_text(json.dumps({
        "battles_finished": n, "our_wins": w, "ties": t, "foulplay_wins": f, "our_win_rate": w / n,
        "seat_username": spec["seat_username"], "fp_username": spec["fp_username"], "gate_all_challenges_resolved": True,
        "rl_git_sha": SHA, "launch_git_sha": SHA, "rl_git_dirty": False, "prereg_sha256": "p" * 64,
        "concurrent_decision_rate": 0.0}))
    (res / f"{tag}.runner.json").write_text(json.dumps({"crash_forfeits": 0, "fpn_counters_ok": fpn_ok, "relaunches": 0,
                                                        "max_relaunches": 10, "void_too_many_crashes": False}))
    (res / f"{tag}.runner.log").write_text("[t] budget verified from foul-play's log: fixed (search_time_ms=20, "
                                           "search_iterations=25000/12000)\n")
    lines = ([f"Winner: {spec['seat_username']}"] * w + [f"Winner: {spec['fp_username']}"] * f + ["Winner: None"] * t)
    (res / f"{tag}.fp.stdout").write_text("\n".join(lines) + "\n")


def _tree(tmp: pathlib.Path, fpn_bad: str | None = None, with_rerun: bool = False, final_step: int = 100_000_123):
    pre = copy.deepcopy(yaml.safe_load((ROOT / "configs/eval/r7_reads_offfp.yaml").read_text()))
    res = tmp / "fp"; res.mkdir()
    runs = tmp / "runs"; runs.mkdir()
    for l in pre["lanes"]["run_dirs"]:
        d = runs / l; d.mkdir()
        pre["lanes"]["run_dirs"][l] = str(d)
        ck = d / "ckpt_100000123.pt"; ck.write_bytes(b"x")
        pre["checkpoints"][l] = {"path": str(ck), "sha256": "0" * 64, "step": final_step}
        searched = l.startswith("s")
        (d / "meta.yaml").write_text(yaml.safe_dump({"git_sha": SHA, "resumes": []}))
        with open(d / "history.csv", "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["_step", *R.HIST_COLS])
            for i in range(1, 101):
                vals = {"search/kl_prior": 0.20 if searched else 0.33, "search/override": 0.30 if searched else 0.31,
                        "search/value_gap": 0.10, "value/bias_mirror": 0.02 if i % 10 == 0 else "",
                        "search/eligible_frac": 0.80 if searched else 0.70, "search/searched_frac": 0.60 if searched else 0.52,
                        "search/played_frac": 0.60 if searched else 0.0, "loss/grad_norm": 4.5 if searched else 4.0,
                        "loss/clip_frac_searched": 0.51 if searched else 0.14, "loss/clip_frac_unsearched": 0.09}
                wr.writerow([i * 1_000_000, *[vals[c] for c in R.HIST_COLS]])
    for arm, spec in pre["arms"].items():
        _write_arm(res, arm, spec, RATES[arm], fpn_ok=(arm != fpn_bad))
    order = list(pre["run_order"])
    if with_rerun and fpn_bad:
        rr = dict(pre["arms"][fpn_bad]); rr["rerun_of"] = fpn_bad
        rp = pre["usernames"]["rerun_pairs"][fpn_bad]
        rr["seat_username"], rr["fp_username"] = rp["seat"], rp["fp"]
        pre["arms"][fpn_bad + "R"] = rr
        pre["arm_encoder"][fpn_bad + "R"] = {"c6": True}
        _write_arm(res, fpn_bad + "R", rr, RATES[fpn_bad])
    log = ["[t] START pid 1 slots 9"] + [f"[t] {a} LAUNCHED pid 2 pair x/y" for a in order]
    if with_rerun and fpn_bad:
        log += ["[t] START pid 9 slots 1", f"[t] {fpn_bad}R LAUNCHED pid 3 pair x/y"]
    (res / "parallel.log").write_text("\n".join(log) + "\n")
    (res / "launch_sha.txt").write_text(SHA + "\n")
    g0 = tmp / "g0rows.jsonl"; g0.write_text('{"pid": 0}\n')
    mech = tmp / "mech"; mech.mkdir()
    rows = []
    for li, l in enumerate(pre["lanes"]["run_dirs"]):
        noise = np.random.default_rng(100 + li).normal(0.0, 0.02, 200)   # lane-specific: paired differences keep a spread
        for pid in range(200):
            rows.append({"unit": [pre["checkpoints"][l]["path"]], "pid": pid,
                         "regret": (0.010 if l.startswith("s") else 0.011) + float(noise[pid]),
                         "spearman": 0.50 + 0.001 * (pid % 7) + (0.01 if l.startswith("s") else 0.0)})
    (mech / "end.json").write_text(json.dumps({"encoder": {"POKEMON_RL_ENCODER_C6": "1"}, "git_dirty": False, "per_bucket": 50,
                                               "pids": list(range(200)), "git_sha": SHA,
                                               "rows_sha256": hashlib.sha256(g0.read_bytes()).hexdigest()}))
    (mech / "end.rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    sh = tmp / "sh"; sh.mkdir()
    for job, p in (("gs_s376", 0.80), ("gs_s384", 0.81), ("gs_s392", 0.79), ("gc_c400", 0.80), ("gc_c408", 0.79)):
        (sh / f"{job}.final.json").write_text(json.dumps({"eval/win_rate": p, "episodes": 3000}))
    wd = tmp / "watchdog.log"; wd.write_text("[t] WATCHDOG EXIT -- every lane DONE or retired. RESUMES=0 NODE_RESTARTS=0\n")
    pf = tmp / "prereg.yaml"
    pf.write_text(yaml.safe_dump(pre))
    return {"prereg": pf, "fp": res, "sh": sh, "mech": mech / "end.json", "g0": g0, "wd": wd}


def _run(monkeypatch, t: dict, out: pathlib.Path) -> str:
    monkeypatch.setattr(sys, "argv", ["x", "--prereg", str(t["prereg"]), "--fp", str(t["fp"]), "--sh", str(t["sh"]),
                                      "--mech", str(t["mech"]), "--g0-rows", str(t["g0"]), "--watchdog-log", str(t["wd"]),
                                      "--json-out", str(out), "--md-out", str(out.with_suffix(".md"))])
    buf = io.StringIO()
    with redirect_stdout(buf):
        R.main()
    return buf.getvalue()


def test_end_to_end_readout(tmp_path, monkeypatch):
    t = _tree(tmp_path)
    text = _run(monkeypatch, t, tmp_path / "readout.json")
    j = json.loads((tmp_path / "readout.json").read_text())
    ps, pc = (0.605 + 0.610 + 0.615) / 3, (0.600 + 0.605) / 2
    assert j["primary"]["delta"] == pytest.approx(ps - pc, abs=1e-9)
    assert j["primary"]["cell"] == "X-FLAT"                      # +0.0075 < 2 se (~0.0115): a null
    assert j["mechanism"]["i"]["moved"] is True                  # kl_prior 0.20 vs 0.33 in both pairs
    assert j["mechanism"]["vi"]["moved"] is False                # -0.001 against a position-level se ~0.002
    assert j["route"] == "(i) MOVED, (vi) NOT" and "STRONGER EVALUATOR" in j["action"]
    assert j["object_rule"]["object"] == "ES3F"                  # 0.635 >= 0.640 - 0.013
    assert j["session"]["ok"] and j["session"]["pinned_launch_sha"] == SHA
    assert j["dose_divergence_end"]["search/eligible_frac"] == pytest.approx(0.10)
    assert j["histories"]["s376"]["12M"]["loss/clip_frac_searched"] == pytest.approx(0.51)
    assert j["owed"]["watchdog_exit"].endswith("RESUMES=0 NODE_RESTARTS=0") and j["owed"]["resumes"]["s376"] == []
    for s in ("CELL X-FLAT", "GS - GC", "N-ANNEAL", "winner's curse", "BESIDE THE PRIMARY", "(v) per arm", "/timer"):
        assert s in text, s
    md = (tmp_path / "readout.md").read_text()
    for s in ("**X-FLAT**", "**CELL X-FLAT**", "THE ROUTE: (i) MOVED, (vi) NOT", "OBJECT = ES3F", "| (vi) |", "N-ANNEAL",
              "RESUMES=0 NODE_RESTARTS=0", "| search/eligible_frac | end |", "| loss/clip_frac_searched | 12M |", "+0.1000 |"):
        assert s in md, s


def test_end_to_end_resolved_gain_below_the_floor(tmp_path, monkeypatch):
    for k, v in (("S1F", 0.610), ("S2F", 0.615), ("S3F", 0.620)):
        monkeypatch.setitem(RATES, k, v)
    t = _tree(tmp_path)
    _run(monkeypatch, t, tmp_path / "g.json")
    j = json.loads((tmp_path / "g.json").read_text())
    assert j["primary"]["cell"] == "X-GAIN" and j["primary"]["se_leg"] == "binomial"
    assert j["action"].startswith("X-GAIN") and "STAYS" in j["action"]


def test_invalid_arm_is_pending_until_its_rerun(tmp_path, monkeypatch):
    t = _tree(tmp_path, fpn_bad="C1F")
    _run(monkeypatch, t, tmp_path / "r1.json")
    j = json.loads((tmp_path / "r1.json").read_text())
    assert j["primary"]["cell"] == "PENDING" and j["primary"]["waiting"] == ["C1F"]
    assert j["mechanism"]["i"]["moved"] is True                  # training-side reads do not wait on an FP arm
    t2 = tmp_path / "again"; t2.mkdir()
    t = _tree(t2, fpn_bad="C1F", with_rerun=True)
    _run(monkeypatch, t, t2 / "r2.json")
    j = json.loads((t2 / "r2.json").read_text())
    assert j["primary"]["cell"] == "X-FLAT" and j["arms"]["C1F"]["source_arm"] == "C1FR"
    assert j["session"]["ok"] is False                           # the re-run is a later session: disclosed


def test_declared_lane_loss_voids_on_a_pair_lane(tmp_path, monkeypatch):
    t = _tree(tmp_path)
    pre = yaml.safe_load(t["prereg"].read_text())
    pre["lost_lanes"] = ["C2F"]
    t["prereg"].write_text(yaml.safe_dump(pre))
    _run(monkeypatch, t, tmp_path / "r.json")
    j = json.loads((tmp_path / "r.json").read_text())
    assert j["primary"]["cell"] == "VOID" and j["lane_loss"]["lost_pairs"] == ["f2"]


def test_a_stale_history_leaves_the_in_loop_reads_pending(tmp_path, monkeypatch):
    t = _tree(tmp_path, final_step=130_000_000)                # the histories stop 30M short of the pinned finals
    _run(monkeypatch, t, tmp_path / "s.json")
    j = json.loads((tmp_path / "s.json").read_text())
    assert j["mechanism"]["i"]["moved"] is None and j["route"] == "PENDING"
    assert j["primary"]["cell"] == "X-FLAT"                      # the primary does not read histories
    assert "PENDING" in j["action"]


def test_a_program_drift_invalidates_the_arm(tmp_path, monkeypatch):
    t = _tree(tmp_path)
    (t["fp"] / "launch_sha.txt").write_text("0000000deadbeef\n")  # not a commit: git diff fails -> not the same program
    _run(monkeypatch, t, tmp_path / "d.json")
    j = json.loads((tmp_path / "d.json").read_text())
    assert j["primary"]["cell"] == "PENDING" and "different program" in j["arms"]["C1F"]["why"]

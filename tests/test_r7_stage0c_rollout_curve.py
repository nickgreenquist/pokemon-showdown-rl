"""Engine-free tests for scripts/r7_stage0c_rollout_curve.py (R7 Stage 0c, written by the skeptic
reviewer of 2026-09-25 and reviewed before landing): every pure piece the verdict
rests on (the column/row rule, the root rule, the override-matched gate, the
per-world Qbar, the knee, the pre-stated branches, the summary's join), plus one
cross-check against the repo's own `scripts/rollout_q.py::regret_split`. No
pkmn_gen1, no torch. Run: python -m pytest -q test_stage0c_rollout_curve.py
(or `python test_stage0c_rollout_curve.py`)."""

from __future__ import annotations

import importlib.util
import json
import math
import os
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("stage0c", HERE.parent / "scripts" / "r7_stage0c_rollout_curve.py")
s0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s0)


def test_top_k_is_native_solves_stable_rule():
    prior = np.zeros(10)
    prior[[1, 3, 4, 7]] = [0.2, 0.3, 0.3, 0.2]
    # ties go to the lower action index (stable argsort on -prior), exactly native.solve's column order
    assert s0.top_k([1, 3, 4, 7], prior, 4) == [3, 4, 1, 7]
    assert s0.top_k([1, 3, 4, 7], prior, 2) == [3, 4]
    assert s0.top_k([1, 3], prior, 4) == [3, 1]
    # for our rows the first is np.argmax's choice (lowest index on ties)
    p = np.array([0.0, 0.4, 0.4, 0.2, 0, 0, 0, 0, 0, 0])
    assert s0.top_k([1, 2, 3], p, 3)[0] == int(np.argmax(p))


def test_root_candidate_soft_br_and_argmax():
    prior = np.array([0.7, 0.2, 0.1])
    q = np.array([0.0, 0.05, 0.30])
    tau = 0.05
    logits = np.log(prior) + q / tau
    j, m = s0.root_candidate(prior, q, "soft_br", tau, 0)
    assert j == int(np.argmax(logits)) == 2 and math.isclose(m, 0.30)
    # a small Q edge does not beat a large prior edge under the trust region
    j2, m2 = s0.root_candidate(prior, np.array([0.0, 0.05, 0.05]), "soft_br", tau, 0)
    assert j2 == 0 and m2 == 0.0
    # argmax is the pure best response
    j3, m3 = s0.root_candidate(prior, np.array([0.0, 0.05, 0.04]), "argmax", tau, 0)
    assert j3 == 1 and math.isclose(m3, 0.05)
    # under soft_br a candidate other than greedy (the prior's argmax) always has a positive margin
    rng = np.random.default_rng(0)
    for _ in range(200):
        pr = rng.dirichlet(np.ones(5))
        pr = pr[np.argsort(-pr)]          # greedy is index 0
        jq, mq = s0.root_candidate(pr, rng.normal(0, 0.3, 5), "soft_br", tau, 0)
        assert jq == 0 or mq > 0


def test_gate_for_target_hits_the_rate_and_reports_unreachable():
    moves = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], bool)
    margins = np.array([0.4, 0.3, 0.2, 0.1, 0, 0, 0, 0, 0, 0], float)
    g = s0.gate_for_target(moves, margins, 0.2)
    assert g["n_override"] == 2 and math.isclose(g["override"], 0.2) and g["gate"] == 0.3 and g["reachable"]
    g0 = s0.gate_for_target(moves, margins, 0.0)
    assert g0["n_override"] == 0
    gu = s0.gate_for_target(moves, margins, 0.5)            # only 4 of 10 move
    assert not gu["reachable"] and gu["n_override"] == 4 and math.isclose(gu["override"], 0.4)
    # the gate never reads an outcome: it is a function of (moves, margins) only
    assert set(s0.gate_for_target.__code__.co_varnames[: s0.gate_for_target.__code__.co_argcount]) == {"moves", "margins", "target"}


def test_world_qbar_full_and_subset_weights():
    o = np.array([[1, -1, 0], [0, 1, 1]], float)          # rows x cols_w
    cols = [0, 4, 7]
    p2 = np.zeros(10); p2[[0, 4, 7]] = [0.5, 0.3, 0.2]
    full = s0.world_qbar(o, cols, p2, cols)
    assert np.allclose(full, [0.5 - 0.3, 0.3 + 0.2])
    sub = s0.world_qbar(o, cols, p2, [0, 4])               # renormalised over the kept columns
    assert np.allclose(sub, [(0.5 - 0.3) / 0.8, 0.3 / 0.8])


def test_int8_roundtrip():
    a = np.array([[1, -1, 0], [0, 1, -1]])
    assert np.array_equal(s0.decode_i8(s0.encode_i8(a), a.shape), a.astype(float))


def test_knee_monotone_and_peaked():
    n = 400
    rng = np.random.default_rng(1)
    base = rng.normal(0, 0.05, n)
    # independent per-rung noise, so the PAIRED differences carry a real se (~0.0007)
    mono = {R: base + m + rng.normal(0, 0.01, n) for R, m in ((16, 0.00), (32, 0.01), (64, 0.02), (128, 0.0201))}
    k = s0.knee_of(mono)
    assert k["best"] == 128 and k["knee"] == 64
    peaked = {16: base + 0.00, 32: base + 0.03, 64: base + 0.01, 128: base - 0.01}
    kp = s0.knee_of(peaked)
    assert kp["best"] == 32 and kp["knee"] == 32


def _arrays(n, d_means, g_means, g3_means=None, sd=0.02, seed=2):
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, sd, n)
    d = {R: noise + d_means[R] for R in s0.RUNGS}
    g = {R: noise + g_means[R] for R in s0.RUNGS}
    g3 = {R: noise + (g3_means or g_means)[R] for R in s0.RUNGS}
    return d, g, g3


def test_verdict_branches():
    n = 500
    # NO VERDICT: too few positions / a rung missing
    d, g, g3 = _arrays(n, {R: 0.0 for R in s0.RUNGS}, {R: 0.0 for R in s0.RUNGS})
    assert s0.verdict(d, g, g3, 100)["branch"] == "NO VERDICT"
    assert s0.verdict({16: d[16]}, {16: g[16]}, {16: g3[16]}, n)["branch"] == "NO VERDICT"
    # KEEP LIGHT: the rollout operator is clearly below the critic at 128 and flat
    d, g, g3 = _arrays(n, {R: -0.02 for R in s0.RUNGS}, {R: 0.001 for R in s0.RUNGS})
    v = s0.verdict(d, g, g3, n)
    assert v["branch"] == "KEEP LIGHT" and not v["still_rising"] and "add_R512" not in v
    # STAGE 1: it pays; the curve is flat past 64, so the knee is the first rung within 1 se of the best
    d, g, g3 = _arrays(n, {16: 0.004, 32: 0.008, 64: 0.012, 128: 0.012},
                       {16: 0.006, 32: 0.010, 64: 0.014, 128: 0.014}, sd=0.01)
    v = s0.verdict(d, g, g3, n)
    assert v["branch"] == "STAGE 1" and v["knee"] == 64 and v["cells"] == "3x4" and not v["still_rising"]
    # ... and when the 3x4 subset loses the gain, H uses the full matrix
    d, g, g3 = _arrays(n, {16: 0.004, 32: 0.008, 64: 0.012, 128: 0.012},
                       {16: 0.006, 32: 0.010, 64: 0.014, 128: 0.014},
                       {16: 0.0, 32: 0.0, 64: 0.0, 128: 0.0}, sd=0.01)
    v = s0.verdict(d, g, g3, n)
    assert v["cells"] == "full"
    # ONE cells helper: the R = 512 follow-up's curve reads its cells exactly as the verdict does
    cells, gap = s0.cells_at(g, g3, v["knee"])
    assert cells == v["cells"] and gap == v["full_minus_3x4_at_knee"]
    assert s0.cells_at(g, g, 64)[0] == "3x4"
    # STILL RISING attaches ADD R = 512 to any branch
    d, g, g3 = _arrays(n, {16: 0.004, 32: 0.008, 64: 0.012, 128: 0.02},
                       {16: 0.006, 32: 0.010, 64: 0.014, 128: 0.022}, sd=0.01)
    v = s0.verdict(d, g, g3, n)
    assert v["branch"] == "STAGE 1" and v["still_rising"] and "add_R512" in v and v["knee"] == 128
    # UNRESOLVED: mean exactly 0 with a real spread -- neither pays nor sits below zero at 95%
    flat = np.tile([0.05, -0.05], n // 2)
    d = {R: flat.copy() for R in s0.RUNGS}
    v = s0.verdict(d, d, d, n)
    assert v["branch"] == "UNRESOLVED" and not v["still_rising"] and v["mde_win_rate"] > 0
    # KEEP LIGHT needs the curve FLAT: below zero at 128 but still rising is not a ceiling
    d, g, g3 = _arrays(n, {R: -0.02 for R in s0.RUNGS}, {16: 0.0, 32: 0.0, 64: 0.0, 128: 0.01}, sd=0.005)
    v = s0.verdict(d, g, g3, n)
    assert v["branch"] == "UNRESOLVED" and v["still_rising"] and "add_R512" in v


def _fake(n=40, seed=3):
    """G0-like rows, banked belief rows and this script's rows for rung 16, with known answers."""
    rng = np.random.default_rng(seed)
    g0, bel, mine = {}, {}, []
    for pid in range(n):
        rows = [0, 1, 2, 3]
        cols = [0, 1, 2]
        pi1 = np.zeros(10); pi1[rows] = [0.7, 0.15, 0.1, 0.05]
        pi2 = np.zeros(10); pi2[cols] = [0.5, 0.3, 0.2]
        qa = rng.normal(0, 0.3, (4, 3)); qb = qa + rng.normal(0, 0.05, (4, 3))
        g0[pid] = {"pid": pid, "rows": rows, "cols": cols, "a_greedy": 0, "pi1": pi1.tolist(), "pi2": pi2.tolist(),
                   "q_half_a": qa.tolist(), "q_half_b": qb.tolist(), "bucket": pid % 4, "instrument_version": "rollout_q/1"}
        moved = pid % 5 == 0
        tp = 1 if moved else 0
        bel[pid] = {"pid": pid, "a_greedy": 0, "t_pimc": tp, "margin_pimc": 0.02 if moved else 0.0,
                    "a_belief": tp, "version": "rollout_q_belief/2"}
        cand = int(rng.integers(0, 4))
        ent = {"worlds": 16, "rollouts": {"full": 16 * 12, "k4": 16 * 12, "3x4": 16 * 9}}
        for v in s0.VARIANTS:
            for rule in s0.RULES:
                ent[f"{v}/{rule}"] = {"cand": cand if v != "3x4" or cand < 3 else 0,
                                      "margin": float(rng.uniform(0.01, 0.5)) if cand else 0.0}
        mine.append({"version": s0.VERSION, "pid": pid, "bucket": pid % 4, "a_greedy": 0, "rungs": {"16": ent},
                     "critic": {}, "worlds_tried": 16, "worlds_built": 16, "worlds_refused": [], "resample_tries": 16,
                     "rollouts_run": 16 * 12, "lockstep_steps": 50, "seconds": 1.0, "qos": "background",
                     "launch_git_sha": "abc", "git_dirty": False, "engine_sha": "e"})
    return g0, bel, mine


def test_summarise_joins_and_matches_the_banked_operating_point():
    g0, bel, mine = _fake()
    s = s0.summarise(mine, g0, bel, tau=0.05)
    n = len(mine)
    target = np.mean([bel[p]["a_belief"] != 0 for p in range(n)])
    assert math.isclose(s["matched_rate"], target) and s["positions"] == n and s["rungs"] == [16]
    assert s["verdict"]["branch"] == "NO VERDICT"
    # a follow-up tag (NO VERDICT) still carries its curve's knee AND the cells rule at that knee
    assert s["curve"]["knee"]["knee"] == 16 and s["curve"]["cells_at_knee"] in ("3x4", "full")
    assert "full_minus_3x4_at_knee" in s["curve"]
    # the rollout primary at the matched rate, recomputed by hand: gate on its own margins, score on the oracle
    moves = np.array([m["rungs"]["16"]["full/soft_br"]["cand"] != 0 for m in mine])
    margins = np.array([m["rungs"]["16"]["full/soft_br"]["margin"] for m in mine])
    gate = s0.gate_for_target(moves, margins, target)
    gains = []
    for m, over in zip(mine, gate["overrides"]):
        o = s0.oracle_of(g0[m["pid"]])
        c = m["rungs"]["16"]["full/soft_br"]["cand"]
        gains.append((o["qbar"][o["row_of"][c]] - o["qbar"][o["ig"]]) / 2 if over else 0.0)
    got = s["operators"]["16/full/soft_br"]["matched"]
    assert got["n_override"] == gate["n_override"] and math.isclose(got["gain"]["mean"], float(np.mean(gains)))
    # the summary is JSON-serialisable after _json_safe (inf gates, nan se)
    json.dumps(s0._json_safe(s))
    assert "VERDICT" in s0.render_md(s)


def test_true_world_split_is_rollout_qs_regret_split():
    """With the argmax rule and every move overriding (an unreachable target), G0's
    true-world operator IS rollout_q.regret_split -- the repo's own function."""
    repo = pathlib.Path(os.environ.get("PSRL_REPO", s0.MAIN_CHECKOUT))
    if not (repo / "scripts" / "rollout_q.py").exists():
        import pytest
        pytest.skip("no checkout to cross-check against")
    sys.path.insert(0, str(repo / "scripts"))
    import rollout_q as rq                     # numpy-only at import
    rng = np.random.default_rng(4)
    rows_g0, want = [], []
    for pid in range(30):
        outcomes = rng.choice([-1.0, 0.0, 1.0], size=(4, 3, 16))
        pi1 = np.zeros(10); pi1[[0, 1, 2, 3]] = [0.4, 0.3, 0.2, 0.1]
        pi2 = np.zeros(10); pi2[[0, 1, 2]] = [0.5, 0.3, 0.2]
        half = np.zeros(16, bool); half[:8] = True
        q_col = pi2[[0, 1, 2]] / pi2[[0, 1, 2]].sum()
        want.append(rq.regret_split(outcomes, q_col, 0, half) / 2)
        rows_g0.append({"pid": pid, "rows": [0, 1, 2, 3], "cols": [0, 1, 2], "a_greedy": 0, "pi1": pi1.tolist(),
                        "pi2": pi2.tolist(), "q_half_a": rq.cell_means(outcomes, half).tolist(),
                        "q_half_b": rq.cell_means(outcomes, ~half).tolist()})
    tw = s0.true_world_rollout(rows_g0, "argmax", 0.05, 1.0)
    assert np.allclose(tw["per_position"], want)


def test_load_jsonl_refuses_a_mixed_version(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps({"version": s0.VERSION, "pid": 0}) + "\n" + json.dumps({"version": "other/1", "pid": 1}) + "\n")
    try:
        s0.load_jsonl(p, "version", s0.VERSION)
    except SystemExit as e:
        assert "REFUSED" in str(e)
    else:
        raise AssertionError("a mixed-version rows file must be refused")
    q = tmp_path / "ok.jsonl"
    q.write_text(json.dumps({"version": s0.VERSION, "pid": 0}) + "\n")
    assert [r["pid"] for r in s0.load_jsonl(q, "version", s0.VERSION)] == [0]


if __name__ == "__main__":
    import tempfile
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                    with tempfile.TemporaryDirectory() as d:
                        fn(pathlib.Path(d))
                else:
                    fn()
                print(f"PASS {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    sys.exit(1 if fails else 0)

"""CH5 R2 — the batch pre-registration's grade instrument (R0-e).

ONE file for wave gates AND the read (designer B O6: splitting them would
let a wave graded green feed an ungraded read). Deliberate DEPENDENT of
its two parents rather than a near-duplicate:

  * per-arm FP gates (G2 three-way, G3, G-DECLARED, G-TERMINAL-RACE,
    G-BUDGET, G-SEAT, G-SHA/G8, G-DESYNC, sentinel refusal) are IMPORTED
    from scripts/ch5_r1_grade.py — the gate semantics are a contract and
    a bug fix must land once, not thrice. R1 is CLOSED, so its grader is
    frozen in practice; the ratifying commit pins both.
  * the read (cells P1-P6, permutation, cell K, F1, vs-SH SN/X cells,
    sigma_seed WITH its mandatory disclosure line) and the R2-specific
    gates (attest, batch/pool arithmetic R0-f, D-A lr trace) live here.

--selftest runs with NO R2 battle data: it attests the banked control
finals from disk, reproduces the banked control's final lr bit-for-bit
with the D-A formula, exercises EVERY primary cell at synthetic cuts
(boundaries included), the k=2/k=1 descriptive path, the permutation's
fire/no-fire/tie cases, the vs-SH SN/X composition incl. X3, F1, and a
G2 case that must FAIL:
    python scripts/ch5_r2_grade.py --selftest
"""

import argparse
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PREREG_PATH = REPO / "configs/eval/ch5_r2_offsh.yaml"
TRAIN_CFG_PATH = REPO / "configs/showdown_sp_batch50m.yaml"
CONTROL_CFG_PATH = REPO / "configs/showdown_sp_stack50m_r2.yaml"

_spec = importlib.util.spec_from_file_location(
    "ch5_r1_grade", REPO / "scripts/ch5_r1_grade.py")
r1 = importlib.util.module_from_spec(_spec)
sys.modules["ch5_r1_grade"] = r1
_spec.loader.exec_module(r1)

# Frozen constants — every one is re-attested from disk by attest();
# a constant that does not reproduce is a FAIL, not a warning.
CTRL_OFFFP = {"s80": (0.3960, 1000), "s81": (0.3430, 1000), "s82": (0.2730, 1000)}
CTRL_VSSH = {"s80": 0.7423333333333333, "s81": 0.7346666666666667,
             "s82": 0.6296666666666667}
CTRL_MEAN = 0.33733333333333332
CTRL_SD = statistics.stdev([r for r, _ in CTRL_OFFFP.values()])   # 0.061704...
CTRL_SD_SH = statistics.stdev(CTRL_VSSH.values())                 # 0.062951...
CTRL_MEAN_SH = sum(CTRL_VSSH.values()) / 3
F1_THRESHOLD = 0.580222          # frozen struct50m vs-SH pooled
MAX_CTRL_LANE = 0.3960           # permutation threshold
FLOOR = 0.025
STEPS_PER_UPDATE = 30720         # D-A's one changed constant (was 1024)
EXPECTED_UPDATES = 1627
DA_RUNGS = {  # updates at rung -> expected lr, frac = 1-(u-1)*30720/50e6
    2_000_000: 65, 10_000_000: 325, 26_000_000: 846, 50_000_000: 1627}

SIGMA_DISCLOSURE = (
    "an F-test across two 3-lane groups has (2,2) degrees of freedom and "
    "critical value 19.0, so batch must cut sigma_seed ~4.4x before the "
    "comparison registers; A NULL IS NEVER READABLE AS 'BATCH DID NOT "
    "HELP VARIANCE'. Batch is a STRENGTH lever, not the instrument fix.")


def da_expected_lr(updates, base_lr=2.5e-4):
    frac = 1.0 - (updates - 1) * STEPS_PER_UPDATE / 50e6
    return base_lr * max(0.0, frac)


# ---------------------------------------------------------------------
def attest():
    """Re-derive both frozen control reads from disk; hard-stop on drift.
    R0-g's automated half."""
    out = {"pass": True, "checks": []}
    for lane, (rate, n) in CTRL_OFFFP.items():
        d = json.loads((REPO / f"results/ch5_r1_offsh/a{lane[1:]}.json").read_text())
        ok = (abs(d["our_win_rate"] - rate) < 5e-7
              and d["battles_finished"] == d["battles_requested"] == n)
        out["checks"].append({"file": f"a{lane[1:]}.json", "rate": d["our_win_rate"],
                              "n": d["battles_finished"], "pass": ok})
        out["pass"] &= ok
    for lane, rate in CTRL_VSSH.items():
        d = json.loads((REPO / f"results/d29r2/final_s{lane[1:]}.json").read_text())
        ok = abs(d["eval/win_rate"] - rate) < 5e-7 and d["episodes"] == 3000
        out["checks"].append({"file": f"final_s{lane[1:]}.json",
                              "rate": d["eval/win_rate"], "pass": ok})
        out["pass"] &= ok
    prereg = yaml.safe_load(PREREG_PATH.read_text())
    g = prereg["grading"]
    for lane, (rate, n) in CTRL_OFFFP.items():
        y = g["control_offfp"][lane]
        ok = abs(y["rate"] - rate) < 5e-7 and y["n"] == n
        out["checks"].append({"yaml": f"control_offfp.{lane}", "pass": ok})
        out["pass"] &= ok
    for name, want, got in (("mean", g["control_offfp"]["mean"], CTRL_MEAN),
                            ("sd", g["control_offfp"]["sd"], CTRL_SD),
                            ("mean_sh", g["control_vssh"]["mean"], CTRL_MEAN_SH),
                            ("sd_sh", g["control_vssh"]["sd"], CTRL_SD_SH)):
        ok = abs(want - got) < 5e-5
        out["checks"].append({"yaml_summary": name, "stored": want,
                              "exact": round(got, 7), "pass": ok})
        out["pass"] &= ok
    return out


def batch_pool_arithmetic(train_cfg_path=TRAIN_CFG_PATH, stamped_dirs=()):
    """R0-f, re-derived from config files, never transcribed."""
    t = yaml.safe_load(Path(train_cfg_path).read_text())
    c = yaml.safe_load(CONTROL_CFG_PATH.read_text())
    rs, ne = t["agent"]["rollout_steps"], t["num_envs"]
    mb = t["agent"]["minibatches"]
    batch = rs * ne
    updates = int(50e6) // batch
    grad = updates * t["agent"]["epochs"] * mb
    push = t["selfplay"]["push_every_updates"]
    c_batch = c["agent"]["rollout_steps"] * c["num_envs"]
    c_updates = int(50e6) // c_batch
    checks = {
        "batch_30720": batch == 30720,
        "minibatch_256_exact": batch % mb == 0 and batch // mb == 256,
        "updates_1627": updates == EXPECTED_UPDATES,
        "grad_steps_780960": grad == 780960,
        "grad_per_step_equal": (t["agent"]["epochs"] * mb) * c_batch
                               == (c["agent"]["epochs"] * c["agent"]["minibatches"]) * batch,
        "steps_per_push_153600": push * batch == 153600
                                 and c["selfplay"]["push_every_updates"] * c_batch == 153600,
        "pushes_325_both": updates // push == 325 and c_updates // c["selfplay"]["push_every_updates"] == 325,
        "anneal_guard": t["agent"]["lr_anneal_steps"] == t["total_steps"] == 50000000,
    }
    out = {"pass": all(checks.values()), **checks}
    for d in stamped_dirs:
        p = Path(d) / "config.yaml"
        if not p.exists():
            out[f"stamped_{Path(d).name}"] = "MISSING"
            out["pass"] = False
            continue
        s = yaml.safe_load(p.read_text())
        ok = (s["agent"]["rollout_steps"] == rs and s["agent"]["minibatches"] == mb
              and s["selfplay"]["push_every_updates"] == push
              and s["agent"]["gae_lambda"] == 0.95)
        out[f"stamped_{Path(d).name}"] = ok
        out["pass"] &= ok
    return out


def d_a_lr_trace(run_dir):
    """HARD, per lane, all three param groups, off the 2M/10M/26M/50M
    rungs. The only gate distinguishing 'the anneal ran' from 'the YAML
    said 50000000'."""
    import torch
    run_dir = Path(run_dir)
    out = {"lane": run_dir.name, "rungs": [], "pass": True}
    for step, updates in DA_RUNGS.items():
        p = (run_dir / "checkpoint.pt" if step == 50_000_000
             else run_dir / f"ckpt_{step:09d}.pt")
        if not p.exists():
            out["rungs"].append({"step": step, "file": p.name, "pass": None,
                                 "note": "MISSING -- D-A UNGRADED (not passed)"})
            out["pass"] = False
            continue
        d = torch.load(p, map_location="cpu", weights_only=False)
        u = d["agent"]["updates"]
        groups = d["agent"]["optimizer"]["param_groups"]
        sizes = [len(g["params"]) for g in groups]
        lrs = [g["lr"] for g in groups]
        want = da_expected_lr(u)
        ok = (sizes == [29, 26, 6]
              and all(math.isclose(lr, want, rel_tol=1e-9, abs_tol=1e-15) for lr in lrs))
        rung = {"step": step, "updates": u, "expected_updates_at_rung": updates,
                "lrs": lrs, "expected_lr": want, "group_sizes": sizes, "pass": ok}
        if u != updates:
            rung["note"] = ("updates differ from the no-resume expectation -- "
                            "legitimate after a resume (partial rollout discarded); "
                            "DISCLOSED, and the lr must still match ITS OWN updates")
        out["rungs"].append(rung)
        out["pass"] &= ok
    return out


# ---------------------------------------------------------------------
def primary_cell(delta, bar):
    """The six-cell partition. Half-open, exhaustive; boundary rules per
    the pre-reg Q2. Returns (cell, verdict-sentence)."""
    if delta >= bar:
        return "P1", "CREDIT -- the batch lever is credited at this dose."
    if delta >= FLOOR:
        return "P2", "letter-met POSITIVE, seed-fragile, NOT credited"
    if delta >= 0:
        return "P3", ("WITHIN, positive sign -- non-resolving; the scope guard "
                      "fires; quote the REALIZED bar")
    if delta > -FLOOR:
        return "P4", ("WITHIN, negative sign -- non-resolving; the scope guard "
                      "fires; quote the REALIZED bar")
    if delta > -bar:
        return "P5", "letter-met NEGATIVE, not credited"
    return "P6", ("NEGATIVE, credited in reverse -- record entropy/approx_kl/"
                  "clip_frac/lr trajectories beside it; L3 the named suspect")


def sn_cell(delta_sh, bar_sh):
    """vs-SH NEGATIVE-side letters (ADJ-2). Positive/within side bears no
    letter and returns None."""
    if delta_sh <= -bar_sh:
        return "SN-C", "vs-SH credited-negative"
    if delta_sh <= -FLOOR:
        return "SN-L", "letter-met NEGATIVE on the locked axis, not credited"
    return None, None


def x_cell(p, sn):
    if p == "P1" and sn == "SN-C":
        return "X3", ("NAMED CELL: both sentences recorded, neither suppressed; "
                      "whether the README row lands AT ALL goes to the "
                      "maintainer WITH the numbers.")
    if p == "P1" and sn == "SN-L":
        return "X2", ("credit stands; the locked-axis regression is named "
                      "beside every quote of the credit.")
    if p == "P1":
        return "X1", "credit stands; the vs-SH number and its bar reported beside it."
    return "X4", "the primary cell governs; vs-SH reported descriptively with its bar."


def grade_read(t_rates, t_ns, sh_rates=None, sh_n=3000):
    """The primary + composing conditions. t_rates: dict lane->rate on
    n_eff for SURVIVING lanes only (a VOIDed/failed lane is absent —
    removal MOVES k, it never cleans the data)."""
    k = len(t_rates)
    R = {"k_arm": k, "treatment": t_rates, "control": {l: r for l, (r, _) in CTRL_OFFFP.items()},
         "aggregator": "equal_weight_mean_of_lane_rates"}
    if k < 3:
        R["cell"] = "K"
        R["verdict"] = (
            "k_arm <= 2: the primary is DESCRIPTIVE ONLY; no cell fires; nothing "
            "is credited. Surviving lane rates reported individually at their own "
            "n_eff. At k=2 the seed sd has ONE degree of freedom; its 95% CI "
            "multipliers are 0.45x-31.9x.")
        return R
    xs = [t_rates[l] for l in sorted(t_rates)]
    mean_t = sum(xs) / k
    s_t = statistics.stdev(xs)
    delta = mean_t - CTRL_MEAN
    se_bin = math.sqrt(sum(x * (1 - x) / n for x, n in
                           zip(xs, (t_ns[l] for l in sorted(t_rates)))) / k ** 2
                       + sum(r * (1 - r) / n for r, n in CTRL_OFFFP.values()) / 9)
    se_clus = math.sqrt(s_t ** 2 / k + CTRL_SD ** 2 / 3)
    se_gov = max(se_bin, se_clus)
    bar = max(FLOOR, 2 * se_gov)
    cell, verdict = primary_cell(delta, bar)
    R.update({"mean_T": mean_t, "s_T": s_t, "delta": delta,
              "se_bin": se_bin, "se_clus": se_clus, "se_gov": se_gov,
              "governing": "clustered" if se_clus >= se_bin else "binomial",
              "bar": bar, "cell": cell, "verdict": verdict})
    R["recorded_never_governing"] = {
        "pooled_rate": sum(x * n for x, n in zip(xs, (t_ns[l] for l in sorted(t_rates))))
                       / sum(t_ns.values()),
        "best_lane": max(xs), "worst_lane": min(xs)}
    # sigma_seed descriptive -- the disclosure is IN THE SAME OBJECT and
    # the same print (designer B E1; the test asserts the pairing).
    xbar = mean_t
    R["sigma_seed_descriptive"] = {
        "s_T_raw": s_t, "ratio_vs_control": s_t / CTRL_SD,
        "sigma_hat_deconvolved_DESCRIPTIVE_ONLY":
            math.sqrt(max(0.0, s_t ** 2 - xbar * (1 - xbar) / 3000)),
        "F_vs_control": s_t ** 2 / CTRL_SD ** 2,
        "MANDATORY_DISCLOSURE": SIGMA_DISCLOSURE}
    # permutation secondary (letter-bearing, never credits)
    fires = all(x > MAX_CTRL_LANE for x in xs)
    tie = any(x == MAX_CTRL_LANE for x in xs)
    R["permutation"] = {"fires": fires and not tie, "tie_reads_non_separation": tie,
                        "min_p": 0.050, "credits": "never"}
    if cell == "P1" and not (fires and not tie):
        R["named_cell"] = ("credit line fires, permutation does not -- recorded as "
                           "CREDIT per the governing credit line, with the "
                           "non-separation stated wherever the permutation would "
                           "have been quoted")
    # vs-SH (ADJ-2): descriptive positive, letter-bearing negative + X
    if sh_rates is not None and len(sh_rates) == k:
        ys = [sh_rates[l] for l in sorted(sh_rates)]
        mean_sh = sum(ys) / k
        s_tsh = statistics.stdev(ys)
        delta_sh = mean_sh - CTRL_MEAN_SH
        se_bin_sh = math.sqrt(sum(y * (1 - y) / sh_n for y in ys) / k ** 2
                              + sum(r * (1 - r) / 3000 for r in CTRL_VSSH.values()) / 9)
        se_clus_sh = math.sqrt(s_tsh ** 2 / k + CTRL_SD_SH ** 2 / 3)
        bar_sh = max(FLOOR, 2 * max(se_bin_sh, se_clus_sh))
        sn, sn_verdict = sn_cell(delta_sh, bar_sh)
        xc, x_verdict = x_cell(cell, sn)
        R["vs_sh"] = {"mean_T": mean_sh, "delta": delta_sh, "s_T": s_tsh,
                      "bar": bar_sh, "positive_side": "DESCRIPTIVE (ADJ-2)",
                      "sn_cell": sn, "sn_verdict": sn_verdict,
                      "x_cell": xc, "x_verdict": x_verdict}
        R["F1_falsifier"] = {
            "fires": mean_sh < F1_THRESHOLD, "threshold": F1_THRESHOLD,
            "sentence": ("FALSIFIER-CLASS: the dose destroyed the credited "
                         "stack's entire 50M advantage; L3 the named suspect. "
                         "Composes with the cell; both sentences recorded.")
            if mean_sh < F1_THRESHOLD else None}
    return R


# ---------------------------------------------------------------------
def selftest():
    prereg = yaml.safe_load(PREREG_PATH.read_text())

    # (1) attest the frozen controls from disk AND the YAML.
    a = attest()
    assert a["pass"], f"attest failed: {a}"

    # (2) R0-f batch/pool arithmetic from the committed configs.
    b = batch_pool_arithmetic()
    assert b["pass"], f"batch arithmetic failed: {b}"

    # (3) D-A formula reproduces the BANKED CONTROL's final lr
    #     bit-for-bit with the control's own constant (1024).
    import torch
    d = torch.load(REPO / "runs/showdown_sp_stack50m_r2_s80/checkpoint.pt",
                   map_location="cpu", weights_only=False)
    u = d["agent"]["updates"]
    want = 2.5e-4 * (1 - (u - 1) * 1024 / 50e6)
    got = d["agent"]["optimizer"]["param_groups"][0]["lr"]
    assert got == want, (got, want)
    assert [len(g["params"]) for g in d["agent"]["optimizer"]["param_groups"]] == [29, 26, 6]
    # and the treatment's four pre-computed rungs reproduce
    for lr, u2 in ((2.401696e-4, 65), (2.002336e-4, 325),
                   (1.202080e-4, 846), (2.464000e-7, 1627)):
        assert math.isclose(da_expected_lr(u2), lr, rel_tol=1e-6), (u2, lr)

    # (4) every primary cell at synthetic cuts, boundaries included.
    #     bar at s_T ~ 0.005 is the floor-inert 0.0713-ish; use exact.
    ns = {"s66": 3000, "s75": 3000, "s83": 3000}
    def read(rates):
        return grade_read(dict(zip(("s66", "s75", "s83"), rates)), ns)
    r = read((0.45, 0.44, 0.46))
    assert r["cell"] == "P1" and r["governing"] == "clustered", r["cell"]
    assert r["permutation"]["fires"], "all lanes > 0.3960 must fire the permutation"
    r = read((0.45, 0.44, 0.36))          # credit w/ one lane <= 0.3960?
    if r["cell"] == "P1":
        assert "named_cell" in r, "P1 without permutation must emit the named cell"
    assert read((0.37, 0.365, 0.375))["cell"] == "P2"
    assert read((0.34, 0.345, 0.335))["cell"] == "P3"
    assert read((0.335, 0.33, 0.336))["cell"] == "P4"
    assert read((0.31, 0.305, 0.30))["cell"] == "P5"
    assert read((0.22, 0.215, 0.225))["cell"] == "P6"
    # exact boundaries: delta == +FLOOR -> P2; delta == 0 -> P3
    m = CTRL_MEAN + FLOOR
    assert read((m, m, m))["cell"] == "P2"
    assert read((CTRL_MEAN, CTRL_MEAN, CTRL_MEAN))["cell"] == "P3"
    # delta == +bar -> P1 (construct: equal lanes, s_T = 0, bar known)
    bar0 = max(FLOOR, 2 * math.sqrt(0 / 3 + CTRL_SD ** 2 / 3))
    rr = read((CTRL_MEAN + bar0,) * 3)
    assert rr["cell"] == "P1" and math.isclose(rr["delta"], rr["bar"]), rr["cell"]
    assert bar0 > FLOOR, "the floor must be INERT (bar > 0.025 at every s_T)"

    # (5) k=2 / k=1 -> cell K, descriptive only.
    assert grade_read({"s66": 0.5, "s75": 0.5}, ns)["cell"] == "K"
    assert grade_read({"s66": 0.5}, ns)["cell"] == "K"

    # (6) permutation tie reads NON-separation.
    r = read((0.45, 0.44, MAX_CTRL_LANE))
    assert r["permutation"]["tie_reads_non_separation"] is True
    assert r["permutation"]["fires"] is False

    # (7) sigma_seed and its disclosure are emitted TOGETHER.
    r = read((0.37, 0.36, 0.38))
    sd_block = r["sigma_seed_descriptive"]
    assert sd_block["MANDATORY_DISCLOSURE"] == SIGMA_DISCLOSURE
    assert "(2,2)" in SIGMA_DISCLOSURE and "19.0" in SIGMA_DISCLOSURE

    # (8) vs-SH SN/X cells incl. X3, and F1.
    sh = {"s66": 0.58, "s75": 0.57, "s83": 0.59}   # credited-negative + F1
    r = grade_read({"s66": 0.45, "s75": 0.46, "s83": 0.44}, ns, sh_rates=sh)
    assert r["cell"] == "P1" and r["vs_sh"]["sn_cell"] == "SN-C"
    assert r["vs_sh"]["x_cell"] == "X3", r["vs_sh"]
    assert r["F1_falsifier"]["fires"] is True
    sh2 = {"s66": 0.71, "s75": 0.70, "s83": 0.705}
    r = grade_read({"s66": 0.34, "s75": 0.335, "s83": 0.345}, ns, sh_rates=sh2)
    assert r["vs_sh"]["sn_cell"] is None and r["vs_sh"]["x_cell"] == "X4"
    assert r["F1_falsifier"]["fires"] is False

    # (9) a G2 case that must FAIL, through the imported R1 machinery.
    import tempfile
    lane = "s66"
    fake_cfg = {"checkpoints": {lane: {"path": "nonexistent", "sha256": "x"}},
                "grading": {"credit_floor": FLOOR, "tie_disclosure_band": 0.01},
                "fp": {"search_time_ms": 20},
                "arms": {"T": {"kind": "greedy_seat", "seat": lane, "battles": 10,
                               "search_time_ms": 20}}}
    fake_seat = {"battles_requested": 10, "battles_finished": 10,
                 "seat_lane": lane, "seat_lane_defaulted": False,
                 "seat_sha256": None, "gate_all_challenges_resolved": True,
                 "our_wins": 6, "foulplay_wins": 4, "ties": 0,
                 "seat_username": "u", "fp_username": "v",
                 "encoder_env": {"POKEMON_RL_ENCODER_V2": "1",
                                 "POKEMON_RL_ENCODER_IDS": "1"},
                 "process_obs_dim": 828, "declared_search_time_ms": 20}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "t.json").write_text(json.dumps(fake_seat))
        (p / "t.fp.stdout").write_text("Winner: u\n" * 5 + "Winner: v\n" * 4
                                       + "Winner: None\n")   # 5/4/1 != 6/4/0
        g2 = r1.grade_arm(fake_cfg, p, "T", "t")["gates"]["G2"]
        assert g2["pass"] is False, "a tally mismatch must FAIL G2"

    print("SELFTEST PASS")
    print(f"  attest: {sum(1 for c in a['checks'] if c['pass'])}/{len(a['checks'])} "
          "frozen-control checks reproduce from disk and YAML")
    print(f"  R0-f: batch 30720 = 120 x 256, updates {EXPECTED_UPDATES}, "
          "grad 780960, 153600 steps/push, 325 pushes both arms")
    print(f"  D-A: control final lr reproduces bit-for-bit ({got:.6e}); "
          "four treatment rungs reproduce")
    print("  cells: P1-P6 + boundaries + K(k<=2) + permutation tie + X3 + F1 "
          "all exercised; G2 mismatch FAILS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    selftest()
    if args.selftest:
        return

    prereg = yaml.safe_load(PREREG_PATH.read_text())
    out_dir = REPO / prereg["results_dir"]
    att = prereg.get("checkpoint_attestation", {})
    if att.get("status") != "ATTESTED":
        print(json.dumps({"refused": "checkpoint_attestation.status != ATTESTED -- "
                          "the wave may not have run against pinned checkpoints"}))
        return

    R = {"prereg": str(PREREG_PATH.relative_to(REPO)),
         "attest": attest(),
         "r0f": batch_pool_arithmetic(
             stamped_dirs=[REPO / f"runs/showdown_sp_batch50m_s{s}" for s in (66, 75, 83)]),
         "d_a": [d_a_lr_trace(REPO / f"runs/showdown_sp_batch50m_s{s}")
                 for s in (66, 75, 83)],
         "gates": {"G-SERIAL": r1.grade_serial(r1.parse_wave_log(out_dir / "wave.log"))},
         "arms": {}}
    prov = out_dir / "wave.provenance.json"
    R["gates"]["G8_wave_provenance"] = (json.loads(prov.read_text()) if prov.exists()
                                        else {"pass": None, "note": "no wave.provenance.json"})

    t_rates, t_ns = {}, {}
    for arm_name in ("T66", "T75", "T83"):
        tag = arm_name.lower()
        if not any((out_dir / f"{tag}{s}").exists() for s in
                   (".json", ".NO_PROGRESS", ".USERNAME_DEADLOCK")):
            continue
        g = r1.grade_arm(prereg, out_dir, arm_name, tag)
        R["arms"][arm_name] = g
        if not g.get("refused") and not g.get("void"):
            lane = prereg["arms"][arm_name]["seat"]
            t_rates[lane] = g["read"]["our_win_rate_on_n_eff"]
            t_ns[lane] = g["read"]["n_eff"]
    for arm_name in ("R4S66", "R4S75", "R4S83"):
        tag = arm_name.lower()
        if (out_dir / f"{tag}.json").exists():
            R["arms"][arm_name] = r1.grade_arm(prereg, out_dir, arm_name, tag)

    sh_rates = {}
    for s in (66, 75, 83):
        p = REPO / f"results/ch5_r2/final_s{s}.json"
        if p.exists():
            d = json.loads(p.read_text())
            assert d["episodes"] == 3000, f"vs-SH final s{s} not at the locked count"
            sh_rates[f"s{s}"] = d["eval/win_rate"]

    # THE PRIMARY VERDICT IS WRITTEN BEFORE ANY RIDER STATISTIC EXISTS
    # (R-Q4); riders are graded by their own tooling, later, never here.
    R["read"] = grade_read(t_rates, t_ns,
                           sh_rates=sh_rates if len(sh_rates) == len(t_rates) and t_rates else None)

    txt = json.dumps(R, indent=2, default=float)
    if args.out:
        Path(args.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()

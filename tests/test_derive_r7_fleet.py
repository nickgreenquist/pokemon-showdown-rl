"""R7 fleet derivation (`scripts/derive_r7_fleet.py`), engine-free, on a fake donor tree: every derived lane config
loads; a searched/control pair differs EXACTLY in the lever (dose matched by construction, checked); every pair
shares its donor; horizon = anneal = 100M at the chosen LR; the header carries the pre-reg (journey step, the exit
condition, the credit line verbatim, the gates, the branches, the power read from its JSON) with the C6 marker on line 2
(the launcher reads it there); the four bases take the right donors and levers; the five-wide fallback drops control
f3; nothing else in the base trio's body moves; seeds and tags collide with no existing config; the smokes run the
lane's schedule at their cadences; every LR candidate is below the donors' own lr; the LR rule reads the UNSEARCHED
approx_kl split, the control's entropy and the vs-SH shock on BOTH arms and picks the largest passing candidate; the
fleet stage refuses an lr the rule did not choose; every counter the gate names is written somewhere in rl/; the
T-op's dials are the signature's; a final that overshoots 200M is found; and a missing donor is refused."""

from __future__ import annotations

import ast
import csv
import glob
import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CREDIT = ("a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the "
          "pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at read time.")


def _mod():
    spec = importlib.util.spec_from_file_location("derive_r7_fleet", ROOT / "scripts/derive_r7_fleet.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _fake_power(tmp: pathlib.Path) -> pathlib.Path:
    table = []
    for width in ("3+3", "3+2"):
        for n in (3000, 6000):
            for share in (0.0, 0.5):
                for d in (-0.030, -0.020, 0.0, 0.020, 0.025, 0.030, 0.035, 0.040):
                    table.append({"width": width, "n": n, "donor_share": share, "delta": d,
                                  "X-POS": 0.111 if d == 0.030 else 0.5, "X-GAIN": 0.222, "se_diff_median": 0.0077})
    p = tmp / "power.json"
    p.write_text(json.dumps({"version": "r7_fleet_power/1", "pooled_sd": 0.0102, "binomial_sd": 0.0091, "df": 10,
                             "table": table}))
    return p


def _fake_runs(tmp: pathlib.Path) -> pathlib.Path:
    runs = tmp / "runs"
    for trio, seeds in (("a", (304, 312, 320)), ("b", (328, 336, 344))):
        for s in seeds:
            d = runs / f"showdown_r6_trio_{trio}_s{s}"
            d.mkdir(parents=True)
            (d / "ckpt_199500000.pt").write_bytes(b"not the final")
            (d / "ckpt_200000011.pt").write_bytes(f"final {trio}{s}".encode())
            (d / "theta0.pt").write_bytes(b"anchors")
    _fake_power(tmp)
    return runs


def _derive(tmp, *args, ok=True) -> tuple[pathlib.Path, str]:
    out = tmp / "configs"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/derive_r7_fleet.py"), "--runs", str(tmp / "runs"),
                        "--out", str(out), "--power", str(tmp / "power.json"), *args],
                       capture_output=True, text=True, cwd=ROOT)
    if ok:
        assert r.returncode == 0, r.stdout + r.stderr
        return out, r.stdout
    assert r.returncode != 0, r.stdout
    return out, r.stdout + r.stderr


RULED = ("--lr-ruled", "TEST: no smokes on a fake tree")


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def test_the_fleet_lanes_load_and_each_pair_differs_exactly_in_the_lever(tmp_path):
    from rl.common.config import load_config

    m = _mod()
    _fake_runs(tmp_path)
    out, launch = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS", *RULED)
    for f in (1, 2, 3):
        s, c = out / f"r7_fleet_searched_f{f}.yaml", out / f"r7_fleet_control_f{f}.yaml"
        for p in (s, c):
            cfg = load_config(p)
            assert cfg.total_steps == cfg.agent["lr_anneal_steps"] == 100_000_000
            assert cfg.agent["lr"] == 1e-4 and cfg.init_from.endswith(f"showdown_r6_trio_b_s{(328, 336, 344)[f - 1]}/ckpt_200000011.pt")
            lines = p.read_text().splitlines()
            assert lines[1] == "# ENCODER_C6: on"
            text = " ".join(l.lstrip("# ").strip() for l in lines if l.startswith("#"))
            assert CREDIT in text and 'journey_step: "14"' in text and "ACTION ON EACH BRANCH" in text
            assert "R0 SANITY GATES" in text and "Search-with-our-evaluator vs the same checkpoint greedy" in text
            # Every branch named, the lane-loss cell, the object rule, the power read from its JSON (0.11 is the
            # fake table's +0.030 cell), the dials and coefficients formatted from the module's own dicts.
            for cell in ("X-POS", "X-GAIN", "X-NEG", "X-COST", "X-FLAT", "LANE LOSS", "OBJECT RULE", "MECHANISM ROUTE"):
                assert cell in text, cell
            assert "0.50 / 0.11 / 0.50 / 0.50" in text and "r7_fleet_power/1" in text
            assert f"frac {m.SEARCH['frac']}" in text
            assert f"k {m.SEARCH['cols_k']} / S {m.SEARCH['chance_s']} / tau {m.SEARCH['tau']}" in text
            assert f"beta {m.LEVER['searched']['search_policy_coef']}" in text
            assert "C1, S1, C2, S2, C3, S3" in text and "ALLOW_SIX_WIDE_DISCLOSED" in text
            for name in m.GATE_COUNTERS["both"] + m.GATE_COUNTERS["searched_only"]:
                assert name in text, name
        a, b = _flat(yaml.safe_load(s.read_text())), _flat(yaml.safe_load(c.read_text()))
        diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        assert diff == {"seed", "run_name", "env_kwargs.seat_tag", "collector.search.play",
                        "agent.search_policy_coef", "agent.search_value_coef"}, diff
        assert a["collector.search.play"] is True and b["collector.search.play"] is False
        assert a["init_from"] == b["init_from"]
        # The config's run_name IS the launcher's run dir (<config basename>_s<seed>), never a second name.
        assert a["run_name"] == f"r7_fleet_searched_f{f}_s{a['seed']}" and b["run_name"] == f"r7_fleet_control_f{f}_s{b['seed']}"
    assert (out / "r7_fleet_smoke_searched.yaml").exists() and (out / "r7_fleet_smoke_control.yaml").exists()
    manifest = [l.split() for l in (out / "r7_fleet_lanes.txt").read_text().splitlines() if not l.startswith("#")]
    assert manifest == [[f"configs/r7_fleet_{arm}_f{f}.yaml", str(seed)] for arm in ("searched", "control")
                        for f, seed in enumerate(m.SEEDS[arm], start=1)]
    # The shakedown through its runner (never raw per-lane launcher lines), a STOP, then ONE fleet launch.
    assert "monster_fleet.sh" not in launch and launch.count("bash scripts/r7_smokes.sh shakedown") == 1
    assert launch.count("r7_fleet_launch.sh configs/r7_fleet_lanes.txt") == 1
    assert launch.index("r7_smokes.sh shakedown") < launch.index("STOP") < launch.index("r7_fleet_launch.sh")
    for cell in ("X-GAIN", "MECHANISM ROUTE", "r7_mechanism_reads.py", "BETA-0 COMPARATOR", "ALL FOUR IN THE R6 OBJECT'S POLICY FORM"):
        assert cell in " ".join(l.lstrip("# ").strip() for l in (out / "r7_fleet_searched_f1.yaml").read_text().splitlines()), cell


def test_the_smokes_run_the_lanes_schedule_at_their_cadences(tmp_path):
    m = _mod()
    _fake_runs(tmp_path)
    out, _ = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "5e-5", "--b0", "PASS", *RULED)
    # base b: 15360 x 8 = 122,880 steps an update; the first checkpoint.pt is SAVE_LATEST_EVERY_UPDATES updates in, and
    # the shakedown runs two updates past it (the wiring review's second pass: 400k never reached it at this base).
    assert m.steps_per_update("b") == 122_880 and m.save_latest_every() == 4 and m.smoke_steps("b") == 800_000
    assert m.steps_per_update("a") == 30_720 and m.smoke_steps("a") == m.SMOKE_MIN_STEPS == 400_000
    for arm in ("searched", "control"):
        s = yaml.safe_load((out / f"r7_fleet_smoke_{arm}.yaml").read_text())
        assert s["total_steps"] == 800_000 and s["agent"]["lr_anneal_steps"] == m.HORIZON
        assert s["eval_every"] == s["checkpoint_every"] == m.SMOKE_CADENCE
        assert s["collector"]["search"]["play"] is (arm == "searched")
        assert s["run_name"] == f"r7_fleet_smoke_{arm}_s{m.SMOKE_SEEDS[arm]}"
    out2, launch = _derive(tmp_path, "--base", "b", "--stage", "lr-smokes")
    names = sorted(p.name for p in out2.glob("r7_lr_smoke_*.yaml"))
    assert names == sorted(f"r7_lr_smoke_{arm}_{lr:g}.yaml" for lr in m.LR_CANDIDATES for arm in m.LR_ARMS)
    for lr in m.LR_CANDIDATES:
        for arm in m.LR_ARMS:
            s = yaml.safe_load((out2 / f"r7_lr_smoke_{arm}_{lr:g}.yaml").read_text())
            assert s["total_steps"] == m.LR_SMOKE_STEPS and s["agent"]["lr_anneal_steps"] == m.HORIZON
            assert s["agent"]["lr"] == lr and s["collector"]["search"]["play"] is (arm != "control")
            assert s["agent"]["search_policy_coef"] == (0.1 if arm == "searched" else 0.0)
            assert s["agent"]["search_value_coef"] == (0.0 if arm == "control" else 0.1)
            assert s["run_name"] == m.lr_smoke_dir(pathlib.Path("runs"), arm, lr).name
    assert "monster_fleet.sh" not in launch and launch.count("bash scripts/r7_smokes.sh lr b") == 1


def test_nothing_else_in_the_base_trios_body_moves(tmp_path):
    m = _mod()
    _fake_runs(tmp_path)
    out, _ = _derive(tmp_path, "--base", "a", "--stage", "fleet", "--lr", "5e-5", "--b0", "PASS", *RULED)
    trio = _flat(yaml.safe_load((ROOT / m.TRIO_A).read_text()))
    lane = _flat(yaml.safe_load((out / "r7_fleet_searched_f1.yaml").read_text()))
    moved = {k for k in set(trio) | set(lane) if trio.get(k) != lane.get(k)}
    assert moved == {"seed", "total_steps", "run_name", "init_from", "env_kwargs.seat_tag", "collector.process",
                     "collector.search.frac", "collector.search.top1_skip", "collector.search.cols_k",
                     "collector.search.chance_s", "collector.search.tau", "collector.search.play", "agent.lr",
                     "agent.lr_anneal_steps", "agent.search_targets", "agent.search_policy_coef",
                     "agent.search_value_head", "agent.search_value_coef", "agent.search_value_blend"}, moved


@pytest.mark.parametrize("base,trio,heads,batch", [("a", "a", True, 3840), ("b", "b", False, 15360),
                                                   ("ab", "a", True, 15360), ("w", "b", False, 3840)])
def test_each_base_takes_its_donors_and_its_levers(tmp_path, base, trio, heads, batch):
    m = _mod()
    _fake_runs(tmp_path)
    out, _ = _derive(tmp_path, "--base", base, "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS", *RULED)
    lane = _flat(yaml.safe_load((out / "r7_fleet_control_f2.yaml").read_text()))
    assert f"showdown_r6_trio_{trio}_s" in lane["init_from"]
    assert ("agent.trunk_kwargs.value_aux_out" in lane) == heads and ("collector.outcome_targets" in lane) == heads
    assert lane["agent.rollout_steps"] == batch
    assert ("aux_outcome/*" in (out / "r7_fleet_control_f2.yaml").read_text()) == heads
    # R-F1: a REDUCED lr -- every candidate below the donors' own starting lr, for every base.
    assert all(c < m.donor_lr(base) for c in m.LR_CANDIDATES)


def test_the_five_wide_fallback_drops_control_f3(tmp_path):
    _fake_runs(tmp_path)
    out, launch = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "FAIL", *RULED)
    assert not (out / "r7_fleet_control_f3.yaml").exists()
    assert sorted(p.name for p in out.glob("r7_fleet_*_f*.yaml")) == sorted(
        [f"r7_fleet_searched_f{f}.yaml" for f in (1, 2, 3)] + [f"r7_fleet_control_f{f}.yaml" for f in (1, 2)])
    assert len([l for l in (out / "r7_fleet_lanes.txt").read_text().splitlines() if not l.startswith("#")]) == 5
    assert "ALLOW_SIX_WIDE_DISCLOSED" not in launch
    assert "C1, S1, C2, S2, S3" in (out / "r7_fleet_searched_f1.yaml").read_text()


def test_seeds_and_tags_collide_with_no_existing_config():
    m = _mod()
    ours = set(m.SEEDS["searched"]) | set(m.SEEDS["control"]) | set(m.SMOKE_SEEDS.values())
    for arm in m.LR_ARMS:
        ours |= set(m.LR_SMOKE_SEEDS[arm])
    assert len(ours) == 6 + 2 + 9
    theirs, tags = set(), set()
    for p in glob.glob(str(ROOT / "configs/**/*.yaml"), recursive=True):
        if pathlib.Path(p).name.startswith(("r7_fleet", "r7_lr_smoke")):
            continue
        try:
            d = yaml.safe_load(pathlib.Path(p).read_text())
        except yaml.YAMLError:
            continue
        if isinstance(d, dict):
            theirs.add(d.get("seed"))
            tags.add(((d.get("env_kwargs") or {}).get("seat_tag")))
    assert not ours & theirs, ours & theirs
    assert not set(m.TAGS.values()) & tags
    assert len(set(m.TAGS.values())) == len(m.TAGS)


def _hist(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _smoke_rows(arm, kl, entropy, kl_update, kl_whole=0.20):
    """16 update rows. The searched/beta-0 arms' WHOLE-batch approx_kl is far past the bar on purpose (a searched row
    carries KL(pi'||pi_theta)): the rule reads their unsearched split, and the control's whole batch. kl_update wobbles
    +-0.01 so the not-inert margin has an se to read."""
    rows = []
    for i in range(16):
        r = {"loss/entropy": entropy, "search/kl_update": kl_update + (0.01 if i % 2 else -0.01)}
        if arm == "control":
            r["loss/approx_kl"] = kl
        else:
            r["loss/approx_kl"] = kl_whole
            r["loss/approx_kl_unsearched"] = kl
        rows.append(r)
    return rows


def _lr_tree(tmp_path, m, *, spec):
    """spec[lr][arm] = (kl, entropy, kl_update, vs_sh or None for beta0)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    runs = _fake_runs(tmp_path)
    _hist(runs / "showdown_r6_trio_b_s328/history.csv", [{"loss/entropy": 0.70} for _ in range(200)])
    sh = tmp_path / "sh"
    sh.mkdir()
    (sh / "donor_f1.json").write_text(json.dumps({"eval/win_rate": 0.88}))
    for lr in m.LR_CANDIDATES:
        for arm in m.LR_ARMS:
            kl, ent, kup, wr = spec[lr][arm]
            d = m.lr_smoke_dir(runs, arm, lr)
            _hist(d / "history.csv", _smoke_rows(arm, kl, ent, kup))
            if wr is not None:
                (sh / f"{d.name}.json").write_text(json.dumps({"eval/win_rate": wr}))
    return runs, sh


def test_the_lr_rule_gates_the_control_reads_the_searched_arm_and_contrasts_beta(tmp_path):
    m = _mod()
    c1, c2, c3 = m.LR_CANDIDATES  # descending: 1e-4, 5e-5, 2.5e-5
    S, C, B = (0.02, 0.50, 0.10, 0.87), (0.02, 0.69, 0.30, 0.87), (0.02, 0.60, 0.30, None)
    spec = {c1: {"searched": S, "control": (0.07, 0.69, 0.30, 0.87), "beta0": B},     # control's whole-batch kl too high
            c2: {"searched": S, "control": (0.02, 0.69, 0.30, 0.84), "beta0": B},     # control vs-SH shock (> 0.03 down)
            c3: {"searched": S, "control": C, "beta0": B}}
    runs, sh = _lr_tree(tmp_path / "a", m, spec=spec)
    verdict = tmp_path / "a" / "read_lr.json"
    assert m.read_lr(runs, "b", sh, verdict) == c3
    v = json.loads(verdict.read_text())
    assert v["chosen"] == c3 and not v["per_lr"][f"{c1:g}"]["gates"]["control_kl_ok"]
    assert not v["per_lr"][f"{c2:g}"]["gates"]["control_sh_ok"]
    # The searched arm's entropy (0.50, 29% off the donor's 0.70) is READ, never gated; the control's IS gated.
    spec[c3]["control"] = (0.02, 0.55, 0.30, 0.87)
    runs, sh = _lr_tree(tmp_path / "b", m, spec=spec)
    assert m.read_lr(runs, "b", sh, tmp_path / "b" / "v.json") is None
    # NOT-INERT is against the BETA-0 comparator, with a margin: a searched kl_update not clearly below beta-0's is a
    # ruling, never a default (0.29 vs 0.30 with an update-level se of ~0.0036 each: inside 2 se).
    spec[c3]["control"] = C
    spec[c3]["searched"] = (0.02, 0.50, 0.29, 0.87)
    runs, sh = _lr_tree(tmp_path / "c", m, spec=spec)
    assert m.read_lr(runs, "b", sh, tmp_path / "c" / "v.json") is None
    v = json.loads((tmp_path / "c" / "v.json").read_text())
    assert v["largest_passing"] == c3 and v["chosen"] is None and "NOT-INERT" in v["ruling_needed"]
    # A searched-only vs-SH drop past the tolerance at the chosen lr: a ruling.
    spec[c3]["searched"] = (0.02, 0.50, 0.10, 0.84)
    runs, sh = _lr_tree(tmp_path / "d", m, spec=spec)
    assert m.read_lr(runs, "b", sh, tmp_path / "d" / "v.json") is None
    assert "SEARCHED arm dropped" in json.loads((tmp_path / "d" / "v.json").read_text())["ruling_needed"]


def test_the_fleet_stage_takes_only_the_rules_lr(tmp_path):
    _fake_runs(tmp_path)
    verdict = tmp_path / "read_lr.json"
    verdict.write_text(json.dumps({"chosen": 5e-05}))
    _, err = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS",
                     "--lr-verdict", str(verdict), ok=False)
    assert "is not the rule's choice" in err
    out, _ = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "5e-05", "--b0", "PASS", "--lr-verdict", str(verdict))
    assert "the LR rule's choice" in (out / "r7_fleet_searched_f1.yaml").read_text()
    _, err = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "5e-05", "--b0", "PASS",
                     "--lr-verdict", str(tmp_path / "absent.json"), ok=False)
    assert "REFUSED" in err


def test_every_gate_counter_is_written_somewhere_in_rl():
    m = _mod()
    src = "\n".join(p.read_text() for p in (ROOT / "rl").rglob("*.py"))
    for group, names in m.GATE_COUNTERS.items():
        for name in names:
            # a prefix ("l2init/") matches its opening quote; a full name must appear CLOSED (so "search/override"
            # is not satisfied by "search/override_update" -- the wiring review's second pass)
            assert (f'"{name}' if name.endswith("/") else f'"{name}"') in src, (group, name)


def test_the_t_ops_dials_are_the_signatures():
    """Derived from rl/search/top.py's AST (engine-free): the fleet's SEARCH dict + `play` is exactly TOp's dial list."""
    tree = ast.parse((ROOT / "rl/search/top.py").read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TOp")
    init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
    dials = {a.arg for a in init.args.kwonlyargs} - {"seat", "seed"}
    assert set(_mod().SEARCH) | {"play"} == dials, dials


def test_a_final_that_overshoots_200m_is_found(tmp_path):
    m = _mod()
    runs = _fake_runs(tmp_path)
    d = runs / "showdown_r6_trio_b_s336"
    (d / "ckpt_200000011.pt").unlink()
    (d / "ckpt_200000163.pt").write_bytes(b"an overshooting final")
    assert m.donors("b", runs)[1]["path"].endswith("ckpt_200000163.pt")
    (d / "ckpt_1000000000.pt").write_bytes(b"a longer name, a larger step")
    assert m.donors("b", runs)[1]["path"].endswith("ckpt_1000000000.pt")


def test_a_missing_donor_is_refused(tmp_path):
    runs = _fake_runs(tmp_path)
    (runs / "showdown_r6_trio_b_s336/ckpt_200000011.pt").unlink()
    _, err = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS", *RULED, ok=False)
    assert "REFUSED" in err


def test_the_lr_evals_write_exactly_what_the_rule_reads(tmp_path):
    """--stage lr-evals prints one vs-SH command per checkpoint the rule compares (the donor f1's final and every
    smoke's highest-step checkpoint), each writing the JSON read_lr opens -- the two sides of one file name."""
    m = _mod()
    runs = _fake_runs(tmp_path)
    for lr in m.LR_CANDIDATES:
        for arm in ("searched", "control"):
            d = m.lr_smoke_dir(runs, arm, lr)
            d.mkdir(parents=True)
            (d / "ckpt_001966080.pt").write_bytes(b"a rung")
            (d / "ckpt_002088960.pt").write_bytes(b"the final")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/derive_r7_fleet.py"), "--runs", str(runs), "--base", "b",
                        "--stage", "lr-evals", "--sh-dir", str(tmp_path / "sh")], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    cmds = [l for l in r.stdout.splitlines() if l and not l.startswith("#")]
    assert len(cmds) == 1 + 2 * len(m.LR_CANDIDATES)
    assert "showdown_r6_trio_b_s328/ckpt_200000011.pt" in cmds[0] and cmds[0].endswith(str(tmp_path / "sh" / "donor_f1.json"))
    outs = {c.rsplit("--out ", 1)[1] for c in cmds[1:]}
    assert outs == {str(tmp_path / "sh" / f"{m.lr_smoke_dir(runs, a, lr).name}.json")
                    for lr in m.LR_CANDIDATES for a in ("searched", "control")}
    assert all("ckpt_002088960.pt" in c and f"--episodes {m.SH_N}" in c and "POKEMON_RL_ENCODER_C6=1" in c for c in cmds[1:])

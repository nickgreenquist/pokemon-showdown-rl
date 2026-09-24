"""R7 fleet derivation (`scripts/derive_r7_fleet.py`), engine-free, on a fake donor tree: every derived lane config
loads; a searched/control pair differs EXACTLY in the lever (dose matched by construction, checked); every pair
shares its donor; horizon = anneal = 100M at the chosen LR; the header carries the pre-reg (journey step, the exit
condition, the credit line verbatim, the gates, the branches) with the C6 marker on line 2 (the launcher reads it
there); the four bases take the right donors and levers; the five-wide fallback drops control f3; nothing else in
the base trio's body moves; seeds collide with no existing config; the LR rule picks the largest passing candidate;
and a missing donor is refused, never defaulted."""

from __future__ import annotations

import csv
import glob
import importlib.util
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


def _fake_runs(tmp: pathlib.Path) -> pathlib.Path:
    runs = tmp / "runs"
    for trio, seeds in (("a", (304, 312, 320)), ("b", (328, 336, 344))):
        for s in seeds:
            d = runs / f"showdown_r6_trio_{trio}_s{s}"
            d.mkdir(parents=True)
            (d / "ckpt_199500000.pt").write_bytes(b"not the final")
            (d / "ckpt_200000011.pt").write_bytes(f"final {trio}{s}".encode())
            (d / "theta0.pt").write_bytes(b"anchors")
    return runs


def _derive(tmp, *args) -> tuple[pathlib.Path, str]:
    out = tmp / "configs"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/derive_r7_fleet.py"), "--runs", str(tmp / "runs"),
                        "--out", str(out), *args], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    return out, r.stdout


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

    _fake_runs(tmp_path)
    out, launch = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS")
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
        a, b = _flat(yaml.safe_load(s.read_text())), _flat(yaml.safe_load(c.read_text()))
        diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
        assert diff == {"seed", "run_name", "env_kwargs.seat_tag", "collector.search.play",
                        "agent.search_policy_coef", "agent.search_value_coef"}, diff
        assert a["collector.search.play"] is True and b["collector.search.play"] is False
        assert a["init_from"] == b["init_from"]
    assert (out / "r7_fleet_smoke400k_searched.yaml").exists() and (out / "r7_fleet_smoke400k_control.yaml").exists()
    assert launch.count("monster_fleet.sh") == 8


def test_nothing_else_in_the_base_trios_body_moves(tmp_path):
    m = _mod()
    _fake_runs(tmp_path)
    out, _ = _derive(tmp_path, "--base", "a", "--stage", "fleet", "--lr", "5e-5", "--b0", "PASS")
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
    _fake_runs(tmp_path)
    out, _ = _derive(tmp_path, "--base", base, "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS")
    lane = _flat(yaml.safe_load((out / "r7_fleet_control_f2.yaml").read_text()))
    assert f"showdown_r6_trio_{trio}_s" in lane["init_from"]
    assert ("agent.trunk_kwargs.value_aux_out" in lane) == heads and ("collector.outcome_targets" in lane) == heads
    assert lane["agent.rollout_steps"] == batch


def test_the_five_wide_fallback_drops_control_f3(tmp_path):
    _fake_runs(tmp_path)
    out, launch = _derive(tmp_path, "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "FAIL")
    assert not (out / "r7_fleet_control_f3.yaml").exists()
    assert sorted(p.name for p in out.glob("r7_fleet_*_f*.yaml")) == sorted(
        [f"r7_fleet_searched_f{f}.yaml" for f in (1, 2, 3)] + [f"r7_fleet_control_f{f}.yaml" for f in (1, 2)])


def test_seeds_and_tags_collide_with_no_existing_config():
    m = _mod()
    ours = set(m.SEEDS["searched"]) | set(m.SEEDS["control"]) | set(m.SMOKE_SEEDS.values()) | set(m.LR_SMOKE.values())
    assert len(ours) == 6 + 2 + 3
    theirs, tags = set(), set()
    for p in glob.glob(str(ROOT / "configs/*.yaml")):
        if pathlib.Path(p).name.startswith("r7_fleet") or pathlib.Path(p).name.startswith("r7_lr_smoke"):
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


def test_the_lr_rule_picks_the_largest_passing_candidate(tmp_path):
    m = _mod()
    runs = _fake_runs(tmp_path)
    def hist(path, kl, ent):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["loss/approx_kl", "loss/entropy"])
            w.writeheader()
            for i in range(100):
                w.writerow({"loss/approx_kl": kl, "loss/entropy": ent})
    hist(runs / "showdown_r6_trio_b_s328/history.csv", 0.01, 0.70)
    hist(runs / "r7_lr_smoke_0.00025_s440/history.csv", 0.09, 0.70)     # kl too high
    hist(runs / "r7_lr_smoke_0.0001_s444/history.csv", 0.03, 0.60)      # entropy within 20%
    hist(runs / "r7_lr_smoke_5e-05_s448/history.csv", 0.02, 0.69)
    assert m.read_lr(runs, "b") == 1e-4


def test_a_missing_donor_is_refused(tmp_path):
    runs = _fake_runs(tmp_path)
    (runs / "showdown_r6_trio_b_s336/ckpt_200000011.pt").unlink()
    r = subprocess.run([sys.executable, str(ROOT / "scripts/derive_r7_fleet.py"), "--runs", str(runs), "--out",
                        str(tmp_path / "configs"), "--base", "b", "--stage", "fleet", "--lr", "1e-4", "--b0", "PASS"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr)

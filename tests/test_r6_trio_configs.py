"""The R6 fleet configs (2026-09-21): each is the W base
(configs/showdown_monster200m_w.yaml) plus EXACTLY the diffs its header states,
both carry the launcher's C6 marker, their seat_tags collide with no other
config's, the anneal equals the horizon, and trio A's three-key lever is set
together (the seam PPOAgent and rl/train.py enforce at construction/launch)."""
import glob
import pathlib

import yaml

from rl.common.config import load_config

ROOT = pathlib.Path(__file__).resolve().parents[1]
W = ROOT / "configs/showdown_monster200m_w.yaml"
A = ROOT / "configs/showdown_r6_trio_a.yaml"
B = ROOT / "configs/showdown_r6_trio_b.yaml"


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def _diff(a, b):
    fa, fb = _flat(a), _flat(b)
    return {k for k in fa.keys() | fb.keys() if fa.get(k, "<absent>") != fb.get(k, "<absent>")}


def test_both_load_as_configs_with_the_anneal_equal_to_the_horizon():
    for p in (A, B):
        cfg = load_config(p)
        assert cfg.total_steps == cfg.agent["lr_anneal_steps"] == 200_000_000, p.name
        assert cfg.collector["mode"] == "engine" and cfg.collector["k"] == 8


def test_trio_a_is_the_w_base_plus_exactly_its_stated_diffs():
    w, a = yaml.safe_load(W.read_text()), yaml.safe_load(A.read_text())
    assert _diff(w, a) == {
        "seed", "run_name", "env_kwargs.seat_tag",
        "collector.outcome_targets", "agent.aux_outcome_coef", "agent.trunk_kwargs.value_aux_out",
    }
    assert a["collector"]["outcome_targets"] is True
    assert a["agent"]["aux_outcome_coef"] == 0.1
    assert a["agent"]["trunk_kwargs"]["value_aux_out"] == 3
    assert a["seed"] == 304 and a["env_kwargs"]["seat_tag"] == "r6ta"


def test_trio_b_is_the_w_base_plus_exactly_its_stated_diffs():
    w, b = yaml.safe_load(W.read_text()), yaml.safe_load(B.read_text())
    assert _diff(w, b) == {
        "seed", "run_name", "env_kwargs.seat_tag",
        "agent.rollout_steps", "agent.epochs", "agent.lr",
    }
    assert b["agent"]["rollout_steps"] == 15360 and b["agent"]["epochs"] == 2
    assert b["agent"]["minibatches"] == 120 and b["agent"]["lr"] == 3.5e-4
    assert b["seed"] == 328 and b["env_kwargs"]["seat_tag"] == "r6tb"
    # the same dose keys the 12M screen ran, so the screen's verdict transfers
    s = yaml.safe_load((ROOT / "configs/showdown_r6_batch12m.yaml").read_text())
    for k in ("rollout_steps", "epochs", "minibatches", "lr"):
        assert b["agent"][k] == s["agent"][k], k


def test_c6_marker_is_on_the_trios_and_on_nothing_else_in_configs():
    marked = {pathlib.Path(p).name for p in glob.glob(str(ROOT / "configs/*.yaml"))
              if any(line.rstrip() == "# ENCODER_C6: on"
                     for line in pathlib.Path(p).read_text().splitlines())}
    assert marked == {A.name, B.name, A.name.replace('.yaml', '_smoke400k.yaml'),
                      B.name.replace('.yaml', '_smoke400k.yaml')}, marked


def test_seat_tags_and_seeds_collide_with_no_other_config():
    tags = {}
    for p in glob.glob(str(ROOT / "configs/*.yaml")):
        try:
            d = yaml.safe_load(pathlib.Path(p).read_text())
        except yaml.YAMLError:
            continue
        tag = ((d or {}).get("env_kwargs") or {}).get("seat_tag") if isinstance(d, dict) else None
        if tag:
            tags.setdefault(tag, []).append(pathlib.Path(p).name)
    # a trio's smoke shares its tag ON PURPOSE (it exercises the exact contract; its seed differs,
    # so the derived in-loop eval usernames differ); nothing else may carry the tag
    assert sorted(tags["r6ta"]) == sorted([A.name, A.name.replace(".yaml", "_smoke400k.yaml")]), tags.get("r6ta")
    assert sorted(tags["r6tb"]) == sorted([B.name, B.name.replace(".yaml", "_smoke400k.yaml")]), tags.get("r6tb")
    header_seeds = {304, 312, 320, 328, 336, 344}
    assert len(header_seeds) == 6 and yaml.safe_load(A.read_text())["seed"] in header_seeds


def test_smoke_configs_are_the_trios_with_exactly_the_six_smoke_keys_changed():
    for trio, seed in (("a", 904), ("b", 912)):
        base = yaml.safe_load((ROOT / f"configs/showdown_r6_trio_{trio}.yaml").read_text())
        smoke_path = ROOT / f"configs/showdown_r6_trio_{trio}_smoke400k.yaml"
        smoke = yaml.safe_load(smoke_path.read_text())
        assert _diff(base, smoke) == {
            "seed", "run_name", "total_steps", "eval_every", "checkpoint_every",
            "agent.lr_anneal_steps",
        }, trio
        assert smoke["total_steps"] == smoke["agent"]["lr_anneal_steps"] == 400_000
        assert smoke["seed"] == seed and smoke["run_name"] == f"r6_trio_{trio}_smoke_s{seed}"
        assert any(line.rstrip() == "# ENCODER_C6: on" for line in smoke_path.read_text().splitlines())
        load_config(smoke_path)

"""R7 shakedown configs (`configs/r7_shakedown_{searched,control}.yaml`): both load,
their anneal equals their horizon, the control is the searched lane with EXACTLY the two
coefficients zeroed (plus its own seed / run name / seat tag), both pass rl/train.py's
launch-time collector checks (the search seam, the T-op's signature-derived dials) and
build their agent (every dial refusal fires at construction, not after a rollout), and
their seeds and seat tags collide with no other config. The counter list a smoke must
see is derived from the objects, never typed."""

from __future__ import annotations

import glob
import inspect
import pathlib
from types import SimpleNamespace

import pytest
import yaml

from rl.common.config import Config, load_config

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEARCHED = ROOT / "configs/r7_shakedown_searched.yaml"
CONTROL = ROOT / "configs/r7_shakedown_control.yaml"


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def _raw(path):
    return yaml.safe_load(path.read_text())


def test_both_load_with_the_anneal_equal_to_the_horizon():
    for path in (SEARCHED, CONTROL):
        cfg = load_config(path)
        assert cfg.agent["lr_anneal_steps"] == cfg.total_steps == 400_000
        assert cfg.collector["process"] is True and cfg.agent["search_targets"] is True


def test_the_control_is_the_searched_lane_with_exactly_the_coefficients_zeroed():
    a, b = _flat(_raw(SEARCHED)), _flat(_raw(CONTROL))
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"seed", "run_name", "env_kwargs.seat_tag", "agent.search_policy_coef", "agent.search_value_coef"}, diff
    assert b["agent.search_policy_coef"] == 0.0 and b["agent.search_value_coef"] == 0.0
    assert a["agent.search_policy_coef"] > 0 and a["agent.search_value_coef"] > 0
    assert b["collector.search"] == a["collector.search"] if "collector.search" in a else True


def test_the_launch_checks_and_the_agent_construction_pass():
    from rl.envs.showdown import fake_spaces
    from rl.search.top import TOp
    from rl.train import _async_collector_mode, make_agent

    for path in (SEARCHED, CONTROL):
        cfg = load_config(path)
        assert set(cfg.collector["search"]) <= set(TOp.dials()), set(cfg.collector["search"]) - set(TOp.dials())
        assert _async_collector_mode(cfg, True) == "engine"
        obs_space, act_space = fake_spaces()
        agent = make_agent(cfg, SimpleNamespace(observation_space=obs_space, action_space=act_space))
        assert agent.search_targets and agent.antisymmetric_critic and agent.privileged_dim == 408
        assert (agent.search_value_head is not None)
        assert (agent.search_value_coef > 0) == (path == SEARCHED)


def test_the_counters_a_smoke_must_see_are_derived_not_typed():
    from rl.agents.ppo import PPOAgent
    from rl.search import native
    from rl.search.top import TOp

    dials = {n for n, p in inspect.signature(PPOAgent.__init__).parameters.items() if n.startswith("search_")}
    assert dials == {"search_targets", "search_policy_coef", "search_value_head", "search_value_coef", "search_value_blend"}
    for path in (SEARCHED, CONTROL):
        agent = _raw(path)["agent"]
        assert dials <= set(agent), dials - set(agent)
    assert set(TOp.dials()) == {"frac", "top1_skip", "cols_k", "chance_s", "tau", "play"}
    assert "search/kl_prior" in native.counter_names() and "search/root_rule_rm" in native.counter_names()


def test_seeds_and_seat_tags_collide_with_no_other_config():
    mine = {SEARCHED.name: _raw(SEARCHED), CONTROL.name: _raw(CONTROL)}
    seeds = {n: c["seed"] for n, c in mine.items()}
    tags = {n: c["env_kwargs"]["seat_tag"] for n, c in mine.items()}
    assert len(set(seeds.values())) == 2 and len(set(tags.values())) == 2
    for other in glob.glob(str(ROOT / "configs/*.yaml")):
        if pathlib.Path(other).name in mine:
            continue
        try:
            c = yaml.safe_load(pathlib.Path(other).read_text())
        except Exception:
            continue
        if not isinstance(c, dict):
            continue
        assert c.get("seed") not in seeds.values(), (other, c.get("seed"))
        tag = (c.get("env_kwargs") or {}).get("seat_tag")
        assert tag not in tags.values(), (other, tag)

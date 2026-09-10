"""The head-to-head speed A/B's fairness claims, checked rather than asserted.

`scripts/engine_ab_speed.py` claims fairness BY CONSTRUCTION: both arms are
generated from one base dict and only the collector block is edited. That claim
is worth exactly as much as a test, because the failure mode is silent — a
stray key difference does not raise, it just moves the number.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/engine_ab_speed.py"


@pytest.fixture(scope="module")
def ab():
    spec = importlib.util.spec_from_file_location("ab_speed", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def base(ab):
    return yaml.safe_load(ab.BASE_CONFIG.read_text())


def _cfg(ab, base, tmp, arm, rep=1, k=256, steps=1_000_000, seed=9301):
    return yaml.safe_load(ab.build_config(base, arm, steps, k, seed, tmp, rep).read_text())


def test_the_two_arms_differ_only_in_the_collector(ab, base, tmp_path):
    """The whole fairness argument in one assertion.

    `run_name` must differ (two run dirs) and `seat_tag` must differ (username
    collision, below). EVERYTHING else has to be byte-identical, because
    anything else that differs is a second treatment riding along with the
    collector swap and there is no way to attribute the ratio afterwards."""
    a = _cfg(ab, base, tmp_path, "node")
    b = _cfg(ab, base, tmp_path, "engine")
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert differing == {"collector", "env_kwargs", "run_name"}, (
        f"the arms differ in {sorted(differing)}; only the collector, the run "
        "name and the seat tag may differ or the ratio cannot be attributed")
    # and inside env_kwargs, ONLY the seat tag
    ka, kb = a["env_kwargs"], b["env_kwargs"]
    assert {k for k in set(ka) | set(kb) if ka.get(k) != kb.get(k)} == {"seat_tag"}


def test_seat_tags_are_distinct_across_arms_and_replicates(ab, base, tmp_path):
    """CLAUDE.md rule 2, in the shape it takes here.

    Alternation runs the two Node replicates back to back at the SAME seed. With
    no tag `seat_names` hands both the identical pair `as2s{seed}a/b`, and if
    replicate 1's seats have not released, replicate 2 dies with a misleading
    TimeoutError — after which that username pair is poisoned for HOURS and
    takes the rest of the A/B with it."""
    tags = [_cfg(ab, base, tmp_path, arm, rep)["env_kwargs"]["seat_tag"]
            for arm in ("node", "engine") for rep in (1, 2, 3, 4)]
    assert len(set(tags)) == len(tags), f"seat tags collide: {tags}"

    from rl.envs.showdown import seat_names
    names = [n for t in tags for n in seat_names(9301, t)]
    assert len(set(names)) == len(names), f"seat NAMES collide: {names}"


def test_evals_are_off_and_the_ladder_is_silent_in_both_arms(ab, base, tmp_path):
    """Both arms measure TRAINING throughput. The locked eval protocol runs on
    the Showdown server either way, so an eval would add the same constant to
    both arms and dilute the ratio while importing server variance."""
    for arm in ("node", "engine"):
        c = _cfg(ab, base, tmp_path, arm, steps=1_000_000)
        assert c["eval_every"] > c["total_steps"]
        assert c["checkpoint_every"] > c["total_steps"]
        assert c["eval_win_rate"] is False


@pytest.mark.parametrize("order,balanced", [
    ("ABBA", True), ("ABBAABBA", True),
    ("AB", False), ("ABAB", False), ("ABABAB", False),
])
def test_abba_cancels_linear_drift_and_abab_does_not(order, balanced):
    """The reason the default is ABBA and not the ABAB anyone reaches for first.

    A linear drift in the box (thermal, background creep) contributes in
    proportion to a run's POSITION in the sequence. It cancels out of the ratio
    exactly when both arms have the same mean position — which ABBA does (2.5
    and 2.5) and ABAB does not (2.0 against 3.0). Six runs cannot balance at
    all: three integers cannot average 3.5."""
    pos = {"A": [], "B": []}
    for i, c in enumerate(order, start=1):
        pos[c].append(i)
    mean_a = sum(pos["A"]) / len(pos["A"])
    mean_b = sum(pos["B"]) / len(pos["B"])
    assert (mean_a == mean_b) is balanced, (
        f"{order}: A mean {mean_a}, B mean {mean_b}")


def test_the_default_order_is_balanced(ab):
    """Whatever the default becomes, it has to be one of the balanced ones."""
    import argparse
    ap = argparse.ArgumentParser()
    src = SCRIPT.read_text()
    i = src.index('ap.add_argument("--order", default="') + len('ap.add_argument("--order", default="')
    default = src[i:src.index('"', i)]
    pos = {"A": [], "B": []}
    for n, c in enumerate(default, start=1):
        pos[c].append(n)
    assert sum(pos["A"]) / len(pos["A"]) == sum(pos["B"]) / len(pos["B"]), (
        f"default order {default!r} does not balance run position between arms")


def test_the_simulator_guard_is_present_and_reads_the_real_file(ab):
    """CLAUDE.md rule 5 is worth +81% on the Node path and the file that sets
    it is gitignored, so a re-clone silently resets it. Getting it wrong would
    inflate the reported speedup by that whole amount."""
    assert ab.simulator_workers() == 4

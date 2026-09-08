"""`configs/engine_smoke.yaml` — the first engine lane's config.

A SMOKE, not a pre-registration (the `gen4_smoke_heur.yaml` precedent), so this
file checks shape and safety, never a band or a read. Milliseconds: no engine,
no server, no agent.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from rl.common.config import load_config
from rl.envs.make import selfplay_env_kwargs
from rl.train import ENGINE_KEYS, _async_collector_mode

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "configs/engine_smoke.yaml"
TXT = PATH.read_text()
RAW = yaml.safe_load(TXT)

# Every window a pre-reg has reserved. A stamped run dir inside one of these
# turns the owning prereg test red — which is how a smoke breaks someone else's
# suite without touching their files.
RESERVED = (
    set(range(66, 74)) | set(range(75, 91))       # ch5 R2
    | set(range(104, 128))                        # 100M
    | set(range(200, 248))                        # gen4 wang50m + spares
)


def test_the_seed_is_outside_every_reserved_prereg_window():
    assert RAW["seed"] not in RESERVED, RAW["seed"]
    # The whole sub-env window, not just the base: make_vec_env seeds sub-env i
    # at seed + i, and the prereg guards reserve [seed, seed+7] for that reason.
    assert not (set(range(RAW["seed"], RAW["seed"] + RAW["num_envs"])) & RESERVED)


def test_it_survives_trains_actual_validation_order():
    """The order that mattered: `selfplay_env_kwargs` runs BEFORE
    `_async_collector_mode`, and enforces a strict selfplay key set. A config
    that passes the collector check in isolation can still be unlaunchable."""
    cfg = load_config(PATH)
    assert selfplay_env_kwargs(cfg, "opponent")["opponent"] == "self"
    selfplay_env_kwargs(cfg, "eval_opponent")
    if not pathlib.Path(cfg.collector["team_bank"]).exists():
        pytest.skip("team bank is gitignored; the rest of the chain is checked")
    assert _async_collector_mode(cfg, vectorized=True) == "engine"


def test_the_collector_block_uses_only_the_strict_key_set():
    assert set(RAW["collector"]) <= ENGINE_KEYS, set(RAW["collector"]) - ENGINE_KEYS
    assert RAW["collector"]["mode"] == "engine"
    assert RAW["collector"]["learner_seat"] in ("p1", "p2")


def test_the_d25_pair_is_set_together():
    """Refused at launch if it is not — and the 100M recipe this copies sets
    both."""
    assert bool(RAW["env_kwargs"]["opp_action"]) == bool(
        RAW["agent"]["aux_oppact_coef"]
    )


def test_the_agent_block_is_the_100m_width_not_a_toy():
    """A [64, 64] smoke would prove the seam and hide every batching question
    T-1 exists to answer, because the by-member opponent forwards are where the
    GEMV/GEMM anomaly lives."""
    hundred = yaml.safe_load((ROOT / "configs/showdown_sp_100m.yaml").read_text())
    for key in ("trunk", "trunk_kwargs", "hidden_sizes", "rollout_steps",
                "epochs", "minibatches", "gamma", "gae_lambda"):
        assert RAW["agent"][key] == hundred["agent"][key], key
    assert RAW["num_envs"] == hundred["num_envs"]
    # lr_anneal_steps == total_steps is the 100M header's own R0-b coupling.
    assert RAW["agent"]["lr_anneal_steps"] == RAW["total_steps"]


def test_the_header_says_what_it_is_and_is_not():
    for phrase in (
        "SMOKE, NOT A PRE-REGISTRATION",
        "journey_step: 7.5",
        "NOTHING FROM THE ENGINE COLLECTOR IS LICENSED",
        "IT STILL NEEDS A SERVER",
        "CLAUDE.md rule 2",
        "POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1",
    ):
        assert phrase in TXT, phrase
    # A smoke names no arm, no gate and no read. Guard against it quietly
    # growing into a pre-reg without the 2-Opus cycle.
    assert "credited" not in TXT and "PRIMARY read" not in TXT

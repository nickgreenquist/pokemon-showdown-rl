"""Launch-time validation of the Stage-2 collector block (the strict-keys
rule: a typo or an unsupported combination fails before any step runs)."""

import pytest

from rl.common.config import Config
from rl.train import _async_collector_mode


def _cfg(**over):
    base = dict(
        env_id="Showdown-v0",
        seed=0,
        total_steps=1000,
        eval_every=500,
        eval_episodes=10,
        run_name="t",
        collector={"mode": "async", "concurrency": 8},
    )
    base.update(over)
    return Config(**base)


def test_empty_block_is_the_sync_path():
    assert _async_collector_mode(_cfg(collector={}), vectorized=True) is False


def test_async_mode_accepted():
    assert _async_collector_mode(_cfg(), vectorized=True) is True


@pytest.mark.parametrize(
    "over, match",
    [
        (dict(collector={"mode": "async", "conc": 8}), "unknown collector key"),
        (dict(collector={"mode": "fast"}), "mode"),
        (dict(collector={"concurrency": 8}), "async-only"),
        (dict(collector={"mode": "async", "concurrency": 0}), "concurrency"),
        (dict(collector={"mode": "async", "concurrency": 128}), "concurrency"),
        (dict(env_id="Connect4-v0"), "Showdown-only"),
        (dict(normalize_obs=True), "normalizers"),
        (dict(env_kwargs={"opp_action": True, "hl_shaping": 1.0}), "opp_action"),
        (dict(agent={"privileged_dim": 7}), "privileged"),
    ],
)
def test_bad_blocks_fail_at_launch(over, match):
    with pytest.raises(ValueError, match=match):
        _async_collector_mode(_cfg(**over), vectorized=True)


def test_scalar_algorithms_are_refused():
    with pytest.raises(ValueError, match="vectorized"):
        _async_collector_mode(_cfg(), vectorized=False)


def test_async_mode_refuses_a_gen4_env_id():
    # The async collector's format is not threaded: it would train gen 1 under a
    # gen-4 fingerprint and die at the first eval (2026-09-05 review).
    with pytest.raises(ValueError, match="gen-1 only"):
        _async_collector_mode(_cfg(env_id="ShowdownGen4-v0"), vectorized=True)

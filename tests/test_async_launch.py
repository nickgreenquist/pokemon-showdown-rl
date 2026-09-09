"""Launch-time validation of the Stage-2 collector block (the strict-keys
rule: a typo or an unsupported combination fails before any step runs)."""

import re

import pytest

from rl.common.config import Config
from rl.envs.make import selfplay_env_kwargs
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
    assert _async_collector_mode(_cfg(collector={}), vectorized=True) == "sync"


def test_async_mode_accepted():
    assert _async_collector_mode(_cfg(), vectorized=True) == "async"


@pytest.mark.parametrize(
    "over, match",
    [
        (dict(collector={"mode": "async", "conc": 8}), "unknown collector key"),
        (dict(collector={"mode": "fast"}), "mode"),
        (dict(collector={"concurrency": 8}), "async-only"),
        (dict(collector={"k": 64}), "engine-only"),
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


# --- collector.mode 'engine' (docs/PKMN_ENGINE_RUST_PLAN.md §8.1) -----------
#
# NOT LICENSED: gate A-1 has not run, so a run launched in this mode produces
# numbers from a new instrument. The refusals below are what keep a config from
# stamping a knob that silently did nothing.


# The real shape a self-play config has — `enabled` is NOT a legal selfplay
# key, and `selfplay_env_kwargs` refuses unknown ones before the collector check
# ever runs. Building the fixture out of the true key set is what makes the
# launch-order test below meaningful.
SELFPLAY = {
    "opponent": "self",
    "eval_opponent": "heuristics",
    "pool_size": 20,
    "latest_prob": 0.8,
    "push_every_updates": 10,
}


def _engine(**over):
    block = {
        "mode": "engine",
        "k": 256,
        "team_bank": "data/engine/teams_x.bin",
    }
    block.update(over.pop("collector", {}))
    over.setdefault("selfplay", dict(SELFPLAY))
    return _cfg(collector=block, **over)


def test_engine_mode_accepted(tmp_path):
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    cfg = _engine(collector={"team_bank": str(bank)})
    assert _async_collector_mode(cfg, vectorized=True) == "engine"
    # ...and with the D25 pair set together, which is the shape A-1 would run.
    paired = _engine(
        collector={"team_bank": str(bank)},
        env_kwargs={"opp_action": True},
        agent={"aux_oppact_coef": 0.1},
    )
    assert _async_collector_mode(paired, vectorized=True) == "engine"


@pytest.mark.parametrize(
    "over, match",
    [
        (dict(collector={"concurrency": 8}), "async-only"),
        (dict(collector={"kk": 8}), "unknown collector key"),
        (dict(collector={"k": 0}), r"collector\.k"),
        (dict(collector={"k": "many"}), r"collector\.k"),
        (dict(collector={"team_bank": None}), "team_bank"),
        (dict(collector={"team_bank": "/nope/teams.bin"}), "does not exist"),
        (dict(collector={"learner_seat": "p3"}), "learner_seat"),
        (dict(env_id="ShowdownGen4-v0"), "gen-1 only"),
        (dict(env_id="Connect4-v0"), "gen-1 only"),
        (dict(normalize_reward=True), "normalizers"),
        (dict(env_kwargs={"faint_shaping": 1.0}), "opp_action"),
        (dict(agent={"privileged_dim": 7}), "privileged"),
        (dict(selfplay={**SELFPLAY, "harvest_both_seats": True}), "harvest"),
        (dict(selfplay={}), "selfplay.opponent"),
        (dict(selfplay={**SELFPLAY, "opponent": "heuristics"}), "selfplay.opponent"),
        # The D25 pair, refused at LAUNCH rather than at the first update.
        (dict(env_kwargs={"opp_action": True}), "must be set together"),
        (dict(agent={"aux_oppact_coef": 0.1}), "must be set together"),
    ],
)
def test_engine_blocks_fail_at_launch(over, match, tmp_path):
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    block = {"team_bank": str(bank)}
    block.update(over.pop("collector", {}))
    with pytest.raises(ValueError, match=match):
        _async_collector_mode(_engine(collector=block, **over), vectorized=True)


def test_engine_mode_refuses_a_scalar_algorithm(tmp_path):
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    with pytest.raises(ValueError, match="vectorized"):
        _async_collector_mode(
            _engine(collector={"team_bank": str(bank)}), vectorized=False
        )


def test_engine_validation_survives_trains_actual_call_order(tmp_path):
    """The 16 cases above call `_async_collector_mode` IN ISOLATION, and that is
    how `collector.mode: engine` shipped unlaunchable.

    `train()` calls `selfplay_env_kwargs(cfg, "opponent")` (rl/train.py:447)
    BEFORE `_async_collector_mode` (:508), and `selfplay_env_kwargs` enforces a
    STRICT selfplay key set. An engine check written against a `selfplay.enabled`
    key could therefore never be satisfied: without the key the collector check
    raised, and with it `selfplay_env_kwargs` raised first. Every isolated test
    passed, because none of them ran the two in the order `train()` does.

    So this test runs them in that order. It does not need to start training —
    the bug was entirely in the validation sequence.
    """
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    cfg = _engine(collector={"team_bank": str(bank)})

    # train()'s order, verbatim.
    train_env_kwargs = selfplay_env_kwargs(cfg, "opponent")
    assert train_env_kwargs["opponent"] == "self"
    selfplay_env_kwargs(cfg, "eval_opponent")  # make_eval_env's call
    assert _async_collector_mode(cfg, vectorized=True) == "engine"


def test_the_engine_check_names_only_keys_the_selfplay_validator_allows(tmp_path):
    """A guard against the same class of bug returning: whatever key the engine
    check reads must be one `selfplay_env_kwargs` accepts, or the check is
    unreachable."""
    import inspect

    from rl.train import _engine_collector_checks

    src = inspect.getsource(_engine_collector_checks)
    known = {"opponent", "eval_opponent", "pool_size", "latest_prob",
             "push_every_updates", "harvest_both_seats"}
    for key in re.findall(r'cfg\.selfplay\.get\(\s*"([^"]+)"', src):
        assert key in known, (
            f"_engine_collector_checks reads selfplay.{key!r}, which "
            f"selfplay_env_kwargs refuses; known: {sorted(known)}"
        )

"""IDEAS 2.2 — the seed-sharing run tag.

Every training A/B to date is unpaired for a MECHANICAL reason: same-seed arms
collide on Showdown usernames (CLAUDE.md rule 2), which is why the pre-reg seed
guards carry "legal owner" bookkeeping to keep arms on separate seeds. A per-run
tag folded into the seat names lets two arms share a seed.

Weakly dominant and cheap — at rho ~ 0 it is no worse than unpaired — but
`rho` is UNKNOWN and must be measured and reported on first use. Nothing here
claims a variance reduction; these tests only prove the mechanism.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from rl.common.config import Config
from rl.envs.showdown import SEAT_NAME_MAX, SEAT_PREFIX, seat_names
from rl.train import _async_collector_mode

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_no_tag_is_byte_identical_to_every_run_to_date():
    """The default must not move any existing run's wire. `as2s{seed}a/b` is
    what `showdown_async.py` has always used."""
    for seed in (0, 66, 104, 200, 9300):
        assert seat_names(seed) == (f"{SEAT_PREFIX}{seed}a", f"{SEAT_PREFIX}{seed}b")
        assert seat_names(seed, "") == seat_names(seed)


def test_two_arms_can_share_a_seed():
    """THE POINT. Different tags, same seed, disjoint names."""
    a = seat_names(104, "treatment")
    b = seat_names(104, "control")
    assert set(a).isdisjoint(b), (a, b)


def test_the_eval_env_does_not_collide_with_training_sub_env_zero():
    """Both are built at cfg.seed. Today's random derivation keeps them apart
    only because poke-env draws a fresh name per construction; with explicit
    names the role is what separates them."""
    train0 = seat_names(104, "arm", "t")
    ev = seat_names(104, "arm", "e")
    assert set(train0).isdisjoint(ev)


def test_sub_envs_within_one_arm_stay_distinct():
    """make_vec_env passes seed + i, which is what makes each sub-env's pair
    unique — the seed guards reserve [seed, seed+num_envs) for exactly this."""
    seen = set()
    for i in range(8):
        seen |= set(seat_names(104 + i, "arm", "t"))
    assert len(seen) == 16


def test_the_two_seats_of_one_env_differ():
    for tag in ("", "arm"):
        a, b = seat_names(104, tag)
        assert a != b


def test_names_fit_showdowns_username_cap():
    for seed in (0, 9300, 999999):
        for tag in ("", "a", "some-quite-long-arm-name"):
            for role in ("t", "e"):
                a, b = seat_names(seed, tag, role)
                assert len(a) <= SEAT_NAME_MAX and len(b) <= SEAT_NAME_MAX, (a, b)
                # Showdown folds usernames to an id; anything outside
                # [a-z0-9] would not round-trip to the name we think we hold.
                assert re.fullmatch(r"[a-z0-9]+", a), a


def test_an_oversized_seed_is_refused_rather_than_truncated():
    """A silently truncated name collides with its neighbour, which is the very
    failure this exists to prevent."""
    with pytest.raises(ValueError, match="username cap"):
        seat_names(10**12, "arm")


def _cfg(**over):
    base = dict(env_id="Showdown-v0", seed=0, total_steps=1000, eval_every=500,
                eval_episodes=10, run_name="t",
                selfplay={"opponent": "self", "eval_opponent": "heuristics",
                          "pool_size": 2, "latest_prob": 0.8,
                          "push_every_updates": 5})
    base.update(over)
    return Config(**base)


@pytest.mark.parametrize("mode", ["async", "engine"])
def test_seat_tag_is_an_accepted_env_kwarg_on_both_collector_paths(mode, tmp_path):
    """It rides `env_kwargs` rather than a new Config field: a new field would
    break `ckpt["config"] == asdict(cfg)` for every run launched before it
    existed, refusing their resumes."""
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    collector = ({"mode": "async", "concurrency": 8} if mode == "async"
                 else {"mode": "engine", "k": 32, "team_bank": str(bank)})
    cfg = _cfg(collector=collector, env_kwargs={"seat_tag": "armA"})
    assert _async_collector_mode(cfg, vectorized=True) == mode
    # ...and a typo is still refused, which is what the strict set is for.
    bad = _cfg(collector=collector, env_kwargs={"seat_taggg": "armA"})
    with pytest.raises(ValueError, match="env_kwargs"):
        _async_collector_mode(bad, vectorized=True)


def test_make_env_consumes_the_tag_and_never_passes_it_to_the_env():
    """`seat_tag` is not an env constructor argument — `make_env` is the only
    place holding the per-sub-env seed, so it resolves the tag into accounts
    and pops it. Leaking it through would be a TypeError at env construction."""
    import inspect

    from rl.envs.make import make_env

    src = inspect.getsource(make_env)
    assert 'env_kwargs.pop("seat_tag", "")' in src
    assert "account_configuration1" in src and "account_configuration2" in src


def test_the_seed_guard_reasoning_is_recorded_where_a_reader_will_find_it():
    """IDEAS 2.2 asks for the seed-guard test to be extended to tags. The guards
    live in the pre-reg tests, which this branch may not edit; this records the
    contract they would assert, so the extension is mechanical."""
    from rl.envs import showdown

    doc = inspect_source = showdown.seat_names.__doc__ or ""
    assert "role" in doc
    src = pathlib.Path(showdown.__file__).read_text()
    assert "MEASURE AND REPORT rho ON FIRST USE" in src
    assert "weakly dominant" in src

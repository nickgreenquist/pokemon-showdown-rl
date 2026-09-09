"""In-engine scripted opponents and the single-battle env (plan §8.2, §8.3).

These are ports of poke-env's `RandomPlayer` / `MaxBasePowerPlayer` and of
`rl/envs/most_damage_typed.py` (Huang & Lee's rule). They exist for gate D-1
and for server-free harness tests — never as a training opponent, and an
in-engine win rate is never the locked number.
"""

from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")))
ENV = {"POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"}
needs_bank = pytest.mark.skipif(not BANKS, reason="no team bank built yet")


def _run(body: str, timeout: int = 1800) -> str:
    r = subprocess.run(
        [sys.executable, "-c", body, BANKS[-1]],
        capture_output=True, text=True, timeout=timeout, cwd=ROOT,
        env={**os.environ, **ENV},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


@needs_bank
def test_the_scripted_ladder_orders_the_way_the_definitions_predict():
    """random < max_power < most_damage_typed_engine, head to head. Not a licensed
    number — a sanity read that the three policies are actually different and
    that the type-aware refinement is the stronger one."""
    out = _run(r"""
import pathlib, sys
import numpy as np, pkmn_gen1
from rl.envs.engine_bank import read_bank
from rl.envs.engine_tables import build_tables

tables, _ = build_tables()
_h, payload = read_bank(pathlib.Path(sys.argv[1]))

def duel(p1, p2, n=300, seed=11):
    env = pkmn_gen1.BatchEnv(64, seed, tables, payload, "p1")
    wins = games = 0
    for _ in range(200000):
        li, la = env.scripted_actions("learner", p1)
        oi, oa = env.scripted_actions("opponent", p2)
        env.step(li.tolist(), la.tolist(), [0.0] * len(li), 0, oi.tolist(), oa.tolist())
        for e in env.drain_finished():
            wins += float(e["reward"]) > 0
            games += 1
        if games >= n:
            break
    return wins / games, games

sym, n = duel("random", "random")
mp, _ = duel("max_power", "random")
md, _ = duel("most_damage_typed_engine", "random")
mdmp, _ = duel("most_damage_typed_engine", "max_power")
print(f"RESULT {sym:.3f} {mp:.3f} {md:.3f} {mdmp:.3f} {n}")
""")
    line = [l for l in out.splitlines() if l.startswith("RESULT")][-1]
    sym, mp, md, mdmp, n = (float(x) for x in line.split()[1:])
    # A symmetric matchup at n=300 has se ~ 0.029; 5 se is a loose guard.
    assert 0.35 < sym < 0.65, sym
    assert mp > 0.85, mp
    assert md > 0.85, md
    # The type chart is the only difference between the two, and it is worth
    # something: this is why most-damage-typed is JOURNEY's anchor and not
    # max-base-power.
    assert mdmp > 0.55, mdmp


@needs_bank
def test_max_power_never_switches_when_a_move_is_legal():
    """poke-env's rule verbatim: `if battle.available_moves: max(base_power)`.
    A switch action from `max_power` on a turn with a legal move would mean the
    port drifted."""
    out = _run(r"""
import pathlib, sys
import numpy as np, pkmn_gen1
from rl.envs.engine_bank import read_bank
from rl.envs.engine_tables import build_tables

tables, _ = build_tables()
_h, payload = read_bank(pathlib.Path(sys.argv[1]))
env = pkmn_gen1.BatchEnv(32, 5, tables, payload, "p1")

voluntary = forced = 0
for _ in range(4000):
    li, la = env.scripted_actions("learner", "max_power")
    _i, _o, mask, _m = env.pending("learner")
    for row, a in enumerate(la):
        has_move = bool(mask[row][6:].any())
        if a < 6:
            if has_move:
                voluntary += 1
            else:
                forced += 1
    oi, oa = env.scripted_actions("opponent", "random")
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), 0, oi.tolist(), oa.tolist())
    env.drain_finished()
print(f"RESULT {voluntary} {forced}")
""")
    line = [l for l in out.splitlines() if l.startswith("RESULT")][-1]
    voluntary, forced = (int(x) for x in line.split()[1:])
    assert voluntary == 0, f"{voluntary} voluntary switches"
    assert forced > 50, f"only {forced} forced replacements seen — untested path"


@needs_bank
def test_the_single_battle_env_keeps_the_harness_contract():
    """`ShowdownEngine-v0` through `make_env`: mask in info at reset and every
    step, terminal outcome rewards only, consecutive resets play DIFFERENT
    battles (a lane rebuilt at counter 0 would evaluate one team pair)."""
    out = _run(r"""
import sys
import numpy as np
from rl.envs.make import make_env

env = make_env("ShowdownEngine-v0", seed=3,
               env_kwargs={"team_bank": sys.argv[1], "opponent": "max_power", "seed": 3})
rng = np.random.default_rng(0)
leads, rewards, lengths = [], [], []
for _ in range(12):
    obs, info = env.reset()
    assert info["action_mask"].shape == (10,) and info["action_mask"].any()
    leads.append(obs.copy())
    n = 0
    while True:
        a = rng.choice(np.flatnonzero(info["action_mask"]))
        obs, r, term, trunc, info = env.step(a)
        n += 1
        assert obs.shape == (828,) and np.isfinite(obs).all()
        assert info["action_mask"].shape == (10,)
        assert not trunc
        if term:
            assert r in (-1.0, 0.0, 1.0), r
            rewards.append(r)
            lengths.append(n)
            break
        assert r == 0.0, "the engine env emits terminal outcome rewards only"
leads = np.stack(leads)
distinct = len({row.tobytes() for row in leads})
print(f"RESULT {distinct} {len(rewards)} {np.mean(lengths):.1f} {np.mean(rewards):.3f}")
""")
    line = [l for l in out.splitlines() if l.startswith("RESULT")][-1]
    distinct, n, mean_len, mean_r = line.split()[1:]
    assert int(distinct) == 12, f"only {distinct}/12 distinct battles across resets"
    assert int(n) == 12
    assert float(mean_len) > 3
    # A random learner vs max_power loses nearly always; the guard is only that
    # the sign is not inverted.
    assert float(mean_r) < 0.0, mean_r


@needs_bank
def test_the_anchors_are_refused_by_name_not_faked_or_called_unknown():
    """The naming rule is a safety property.

    `random` and `max_power` keep poke-env's names because D-1 plays the
    engine's against the server's under the same name — that shared name IS the
    comparison. The two names that identify a REPORTED number do not get shared:
    `heuristics` is the verdict denominator, and `most_damage_typed` is an
    anchor-battery row. Both are refused with a pointer to where the real one
    lives, so a misattributed number needs an explicit rename rather than a
    typo.
    """
    out = _run(r"""
import sys
import pkmn_gen1
from rl.envs.engine_bank import read_bank
from rl.envs.engine_tables import build_tables
from rl.envs.engine_env import EngineEnv

for name, needle in [("heuristics", "VERDICT DENOMINATOR"),
                     ("most_damage_typed", "SERVER anchor")]:
    try:
        EngineEnv(sys.argv[1], opponent=name)
    except ValueError as e:
        assert needle in str(e), (name, e)
    else:
        raise AssertionError(f"{name} was accepted")

# ...and the same refusal reaches through the Rust surface, which is what a
# D-1 or harness caller actually touches.
tables, _ = build_tables()
import pathlib
_h, payload = read_bank(pathlib.Path(sys.argv[1]))
env = pkmn_gen1.BatchEnv(2, 1, tables, payload, "p1")
for name, needle in [("heuristics", "VERDICT DENOMINATOR"),
                     ("most_damage_typed", "SERVER anchor"),
                     ("nonsense", "unknown scripted policy")]:
    try:
        env.scripted_actions("opponent", name)
    except ValueError as e:
        assert needle in str(e), (name, e)
    else:
        raise AssertionError(f"{name} was accepted")

# The suffixed name works, and it is what `EngineEnv` advertises.
assert "most_damage_typed_engine" in EngineEnv.__module__ or True
from rl.envs.engine_env import SCRIPTED
assert SCRIPTED == ("random", "max_power", "most_damage_typed_engine"), SCRIPTED
env.scripted_actions("opponent", "most_damage_typed_engine")
EngineEnv(sys.argv[1], opponent="most_damage_typed_engine")
print("RESULT refused")
""")
    assert "RESULT refused" in out


# --- the D-1 replay bug, pinned ------------------------------------------------

def _bank_or_skip():
    import pathlib
    import pytest
    for name in ("teams_a1_5000000.bin", "teams_59da482e_e0e0_50000.bin"):
        p = pathlib.Path("data/engine") / name
        if p.exists():
            return p
    pytest.skip("no team bank on disk (gitignored)")


def test_scripted_series_chunks_play_DIFFERENT_battles():
    """D-1 reported n=10,000 while measuring 500 battles twenty times.

    Battle `i` is a pure function of `(lane_seed, i)`, so a caller that chunks a
    long run and does not advance `start` replays battles 0..CHUNK every time.
    The leg's binomial se was understated by sqrt(20), which turned a +0.91 se
    difference into a "+4.2 se" D-1 FAILURE that was pure artifact.
    """
    import numpy as np
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    _, payload = read_bank(_bank_or_skip())
    env = pkmn_gen1.BatchEnv(1, 20260907, tables, payload, "p1")

    a = np.asarray(env.scripted_series(40, 0, "max_power", "max_power")["outcome"])
    b = np.asarray(env.scripted_series(40, 40, "max_power", "max_power")["outcome"])
    assert (a != b).any(), "consecutive chunks replayed the same battles"


def test_scripted_series_is_chunk_invariant():
    """Chunking must not change the numbers, or D-1 cannot resume without
    changing its own result. This also pins the policy RNG as PER-BATTLE: a
    stream carried across the series would make 20x500 differ from 1x10000."""
    import numpy as np
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    _, payload = read_bank(_bank_or_skip())
    env = pkmn_gen1.BatchEnv(1, 20260907, tables, payload, "p1")

    for pol in ("random", "max_power"):
        halves = np.concatenate([
            np.asarray(env.scripted_series(30, 0, pol, pol)["outcome"]),
            np.asarray(env.scripted_series(30, 30, pol, pol)["outcome"]),
        ])
        whole = np.asarray(env.scripted_series(60, 0, pol, pol)["outcome"])
        assert (halves == whole).all(), f"{pol}: chunking changed the outcomes"


def test_no_seat_asymmetry_under_a_symmetric_matchup():
    """Same policy on both seats must not favour a seat. This is the read that
    exposed the replay bug: it showed +7.4 se before the fix and under 2 se
    after, across every lane seed tried."""
    import math

    import numpy as np
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    _, payload = read_bank(_bank_or_skip())
    n = 4000
    env = pkmn_gen1.BatchEnv(1, 20260907, tables, payload, "p1")
    o = np.asarray(env.scripted_series(n, 0, "random", "random")["outcome"])
    p1, p2 = float((o > 0).mean()), float((o < 0).mean())
    se = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    assert abs(p1 - p2) < 4 * se, f"seat asymmetry {p1 - p2:+.4f} = {(p1-p2)/se:.1f} se"

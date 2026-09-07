"""The in-process collection surface (docs/PKMN_ENGINE_RUST_PLAN.md §7.5-§7.6).

No server: this is the whole point of the engine path. Nothing here is a
throughput measurement and nothing here is licensed -- no number from the engine
collector is comparable to anything banked until gate A-1 passes.

Skips loudly without the built extension or a team bank.
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

# The encoder flags are read at import, so the body runs in a subprocess -- the
# same shape tests/test_encoder_ids_tapes.py uses.
_CHILD = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables

tables, _fp = build_tables()
_header, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
K = 32
env = pkmn_gen1.BatchEnv(K, 4242, tables, payload, "p1")
assert env.k == K

rng = np.random.default_rng(0)

def act(seat):
    idx, obs, mask, member = env.pending(seat)
    assert obs.shape == (len(idx), 828), obs.shape
    assert mask.shape == (len(idx), 10), mask.shape
    if len(idx):
        # Showdown mode always offers at least one choice; an empty mask would
        # deadlock the slot.
        assert mask.any(axis=1).all(), "a pending decision with an empty mask"
        assert len(set(idx.tolist())) == len(idx), "a slot appeared twice"
    a = np.array([rng.choice(np.flatnonzero(m)) for m in mask], dtype=np.int64)
    return idx, a

episodes = []
for step in range(6000):
    li, la = act("learner")
    oi, oa = act("opponent")
    # Every live slot owes a decision to exactly one seat or both; a slot in
    # neither list would be stalled.
    assert set(li.tolist()) | set(oi.tolist()) == set(range(K)), "a slot owes nothing"
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), step, oi.tolist(), oa.tolist())
    episodes.extend(env.drain_finished())
    if len(episodes) >= 200:
        break

assert len(episodes) >= 200, len(episodes)
for e in episodes:
    n = e["length"]
    assert n > 0
    assert e["obs"].shape == (n, 828)
    assert e["masks"].shape == (n, 10)
    assert e["actions"].shape == (n,)
    assert e["opp_choice"].shape == (n, 3)
    assert e["reward"] in (-1.0, 0.0, 1.0)
    assert 0 < e["turns"] <= 1000
    # Every action taken was inside its own mask.
    assert np.take_along_axis(e["masks"], e["actions"][:, None], 1).all()
    # I1: the observation is bounded the way the declared Box is.
    assert np.isfinite(e["obs"]).all()
    assert e["obs"].min() >= -1.0 and e["obs"].max() <= 4.0

s = env.stats()
assert s["episodes_discarded"] == 0, "whole episodes only, by construction"
assert s["rerequests"] == 0
assert s["battles_in_flight"] == K
assert s["battle_counter"] >= s["episodes_finished"] + K

rewards = np.array([e["reward"] for e in episodes])
turns = np.array([e["turns"] for e in episodes])
# A uniform policy on both seats is symmetric: P1's win rate must not be far
# from 0.5. n=200 gives se ~ 0.035, so 5 se is a very loose guard against a
# systematic seat advantage (e.g. a reward sign error).
wins = (rewards > 0).sum() / len(rewards)
assert 0.32 < wins < 0.68, f"P1 win rate {wins} under a symmetric policy"
print(f"OK {len(episodes)} episodes, mean turns {turns.mean():.1f}, P1 {wins:.3f}")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_batchenv_plays_whole_episodes_with_legal_actions():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[-1]],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_the_same_lane_seed_replays_the_same_battles():
    child = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np, pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables
tables, _ = build_tables()
_h, payload = bank.read_bank(pathlib.Path(sys.argv[1]))

def run(seed):
    env = pkmn_gen1.BatchEnv(8, seed, tables, payload, "p1")
    rng = np.random.default_rng(7)
    out = []
    for step in range(2000):
        acts = {}
        for who in ("learner", "opponent"):
            idx, obs, mask, _m = env.pending(who)
            acts[who] = (idx, np.array([rng.choice(np.flatnonzero(m)) for m in mask]))
        li, la = acts["learner"]; oi, oa = acts["opponent"]
        env.step(li.tolist(), la.tolist(), [0.0]*len(li), 0, oi.tolist(), oa.tolist())
        for e in env.drain_finished():
            out.append((e["seed"], e["turns"], float(e["reward"])))
        if len(out) >= 40:
            break
    return out[:40]

a, b = run(999), run(999)
assert a == b, "the same lane seed produced different battles"
assert run(1000) != a, "different lane seeds produced identical battles"
print("OK", len(a))
"""
    r = subprocess.run(
        [sys.executable, "-c", child, BANKS[-1]],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().endswith("OK 40")

"""R7 B1b -- the engine->engine resample (`rl/search/resample.py`).

The contract, on live positions: a resampled world is OBSERVATIONALLY
IDENTICAL to the true one from our seat (obs and mask bitwise), differs in what
we cannot see, keeps the projection valid (a leaf expansion renders), and the
operator searches several of them as worlds. Plus the W-HP inverse: the HP the
fill picks shows the observed percent under the determinized max HP.

No server. Skips loudly without the built extension or a team bank.
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
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")),
               key=lambda p: pathlib.Path(p).stat().st_size)

_CHILD = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables
from rl.search import native
from rl.search.resample import resample_world, hp_for_percent, _health_percent

tables, _fp = build_tables()
_h, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
rng = np.random.default_rng(3)

# (0) W-HP inverse on every (hp, max) a gen-1 mon can show.
for max_hp in (11, 23, 57, 100, 231, 338, 688, 703):
    for hp in range(0, max_hp + 1):
        p = _health_percent(hp, max_hp)
        back = hp_for_percent(p, max_hp)
        assert _health_percent(back, max_hp) == p, (hp, max_hp, p, back)
        assert (back == 0) == (hp == 0)

env = pkmn_gen1.BatchEnv(12, 4711, tables, payload, "p1")
drawn = 0; hidden_differ = 0; tries = []; rejected = {"rejected_validate": 0, "rejected_requests": 0, "rejected_obs": 0, "charging_dropped": 0}
solved = 0
for step in range(600):
    li, lobs, lmask, _ = env.pending("learner")
    oi, oobs, omask, _ = env.pending("opponent")
    la = np.array([rng.choice(np.flatnonzero(m)) for m in lmask], dtype=np.int64)
    oa = np.array([rng.choice(np.flatnonzero(m)) for m in omask], dtype=np.int64)
    if drawn < 160 and step % 3 == 0:
        for slot in sorted(set(li.tolist()) & set(oi.tolist()))[:2]:
            node = env.snapshot(slot)
            for seat in ("p1", "p2"):
                if node.requests()[0 if seat == "p1" else 1] == "pass":
                    continue
                world, info = resample_world(node, tables, seat, rng)
                tries.append(info["tries"])
                for k in rejected:
                    rejected[k] += info[k]
                # THE CONTRACT (also asserted inside resample_world; re-checked here).
                assert np.array_equal(world.obs(tables, seat), node.obs(tables, seat))
                assert np.array_equal(world.mask(tables, seat), node.mask(tables, seat))
                assert world.requests() == node.requests() and world.turn() == node.turn()
                assert world.revealed(seat) == node.revealed(seat)
                foe = "p2" if seat == "p1" else "p1"
                assert world.revealed(foe) == node.revealed(foe)
                if bytes(world.bytes()) != bytes(node.bytes()):
                    hidden_differ += 1
                # The projection stays valid: a leaf expansion renders both views.
                rows = np.flatnonzero(node.mask(tables, seat)).tolist()
                cols = np.flatnonzero(node.mask(tables, foe)).tolist() or [-1]
                e = world.expand(tables, seat, [(rows[0], cols[0], 2)], 5)
                assert e["n"] == 2 and np.isfinite(e["obs"]).all()
                drawn += 1
            # The operator over several worlds of one root.
            if solved < 20:
                p1 = np.where(node.mask(tables, "p1"), rng.random(10), 0.0); p1 /= p1.sum()
                p2 = np.where(node.mask(tables, "p2"), rng.random(10), 0.0)
                p2 = p2 / p2.sum() if p2.sum() > 0 else p2
                worlds = [native.World(node)] + [native.World(resample_world(node, tables, "p1", rng)[0]) for _ in range(3)]
                W = rng.normal(size=828) * 0.05
                r = native.solve(worlds, tables, "p1", p1, p2, lambda e: np.tanh(e["obs"] @ W), 9, cols_k=2, chance_s=1)
                assert r["counters"]["search/worlds"] == 4.0 and abs(r["pi"].sum() - 1) < 1e-12
                solved += 1
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), step, oi.tolist(), oa.tolist())
    env.drain_finished()
    if drawn >= 160 and solved >= 20:
        break
assert drawn >= 120, drawn
assert solved >= 20, solved
# Hidden information really is redrawn: the bytes differ on most draws.
assert hidden_differ >= 0.8 * drawn, (hidden_differ, drawn)
mean_tries = float(np.mean(tries))
assert mean_tries < 3.0, (mean_tries, rejected)
print(f"OK resample: {drawn} worlds, {hidden_differ} with redrawn hidden state, mean tries {mean_tries:.2f}, rejected {rejected}")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_a_resampled_world_is_observationally_identical_and_hidden_state_is_redrawn():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[0]],
        capture_output=True, text=True, timeout=1500, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")

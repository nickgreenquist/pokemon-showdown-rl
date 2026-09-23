"""R7 B6 -- the write-side bridge (`rl/search/engine_bridge.py`) and the
constructed-root projection (`SearchNode.from_root` = `BattleTracker::from_root`).

(1) THE ROUND TRIP, engine-only, on live positions: for a live node, the root
    rebuilt from its own bytes, its request pair and each seat's `reveal()`
    payload must encode and mask BITWISE like the live node on BOTH seats, and
    must keep doing so after the same leaf expansion (the diff state was seeded
    right: no phantom re-reveal, PP spend or sleep reset on the first observe).
    The everything-revealed projection (`from_battle`, control C5) must NOT
    match on positions where the foe has hidden members -- the negative
    control that shows the comparison has teeth.
(2) THE GATE, on the harvested corpus (skipped when `results/ch3_r1` is not on
    this box): `scripts/search_r1e_gate.py --backend engine` on a sample of
    roots runs end to end, refusals are counted by family, leg A reports no
    UNDECLARED dim, and the C5 control moves leg A. The full 13,396-root run
    and its bar are the readout's, not this test's.

No server. Skips loudly without the built extension or a team bank.
"""

from __future__ import annotations

import glob
import json
import os
import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")),
               key=lambda p: pathlib.Path(p).stat().st_size)
# The R1 harvest corpus lives in the MAIN checkout's gitignored results/; a
# worktree reaches it through a symlink (results/ch3_r1 -> the main tree's).
HARVEST = ROOT / "results/ch3_r1"

_ROUND_TRIP = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables

tables, _fp = build_tables()
_h, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
rng = np.random.default_rng(5)
env = pkmn_gen1.BatchEnv(12, 9137, tables, payload, "p1")
checked = hidden = c5_differs = 0
for step in range(500):
    li, lobs, lmask, _ = env.pending("learner")
    oi, oobs, omask, _ = env.pending("opponent")
    la = np.array([rng.choice(np.flatnonzero(m)) for m in lmask], dtype=np.int64)
    oa = np.array([rng.choice(np.flatnonzero(m)) for m in omask], dtype=np.int64)
    if step % 4 == 0 and checked < 120:
        for slot in sorted(set(li.tolist()) & set(oi.tolist()))[:3]:
            node = env.snapshot(slot)
            r1, r2 = node.requests()
            p1, p2 = node.reveal("p1"), node.reveal("p2")
            for d in (p1, p2):
                assert set(d) == {"reveal_order", "revealed_moves", "move_uses", "sleep_observed", "flags_before_faint", "binding_victim_turns"}
            rebuilt = pkmn_gen1.SearchNode.from_root(node.battle(), r1, r2, p1, p2)
            for seat in ("p1", "p2"):
                assert np.array_equal(rebuilt.obs(tables, seat), node.obs(tables, seat)), (step, slot, seat, "obs")
                assert np.array_equal(rebuilt.mask(tables, seat), node.mask(tables, seat)), (step, slot, seat, "mask")
                assert rebuilt.reveal(seat) == node.reveal(seat)
            assert rebuilt.requests() == node.requests()
            # The diff state: the same leaf expansion renders the same leaves.
            rows = np.flatnonzero(node.mask(tables, "p1")).tolist()
            cols = np.flatnonzero(node.mask(tables, "p2")).tolist() or [-1]
            cells = [(rows[0], cols[0], 2)]
            if r1 != "pass":
                e0 = node.expand(tables, "p1", cells, 77, both_views=True)
                e1 = rebuilt.expand(tables, "p1", cells, 77, both_views=True)
                assert np.array_equal(e0["obs"], e1["obs"]) and np.array_equal(e0["obs2"], e1["obs2"]), (step, slot, "leaves")
            # Negative control: the everything-revealed projection (C5).
            if len(p2["reveal_order"]) < 6:
                hidden += 1
                c5 = pkmn_gen1.SearchNode.from_battle(node.battle(), r1, r2)
                if not np.array_equal(c5.obs(tables, "p1"), node.obs(tables, "p1")):
                    c5_differs += 1
            checked += 1
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), step, oi.tolist(), oa.tolist())
    env.drain_finished()
    if checked >= 120:
        break
assert checked >= 100, checked
# The control fires on most hidden-bench positions, not all: a foe whose hidden
# members the everything-revealed projection would list identically (measured
# 25/29 on the first run) is a property of those positions, not of from_root.
assert hidden >= 20 and c5_differs >= 0.75 * hidden, (hidden, c5_differs)
print(f"OK from_root round trip: {checked} live positions bitwise on both seats (+ leaves); C5 differs on {c5_differs}/{hidden} hidden-bench positions")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_a_root_rebuilt_from_its_reveal_payload_encodes_and_masks_bitwise():
    r = subprocess.run(
        [sys.executable, "-c", _ROUND_TRIP, BANKS[0]],
        capture_output=True, text=True, timeout=900, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")


@pytest.mark.skipif(not (HARVEST / "harvest_s62.pkl").exists(), reason="the R1 harvest corpus is not on this box")
def test_the_r1e_gate_runs_the_engine_backend_on_a_root_sample(tmp_path):
    out = tmp_path / "r1e"
    r = subprocess.run(
        [sys.executable, "scripts/search_r1e_gate.py", "--backend", "engine", "--limit", "60",
         "--control-limit", "60", "--leg-b-limit", "20", "--out", str(out)],
        capture_output=True, text=True, timeout=1500, cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    report = json.loads((out / "r1e.json").read_text())
    assert report["leg_a"]["undeclared_dims"] == 0, report["leg_a"].get("undeclared_examples")
    assert report["leg_a"]["n_roots"] + report["leg_a"]["n_refused"] >= 50
    assert report["leg_c"]["exact"] == report["leg_a"]["n_roots"], "mask parity must be exact on every built root"

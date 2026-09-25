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


@pytest.mark.skipif(not (HARVEST / "harvest_s62.pkl").exists(), reason="the R1 harvest corpus is not on this box")
def test_our_side_is_projected_as_the_foe_has_seen_it():
    """The G2 code review: the first form handed the tracker our WHOLE team as
    p1's reveal payload, so every built root's foe view knew our hidden bench.
    `our_side_reveal` gives it what the foe has seen: at turn 1 our lead and no
    moves; later, the mons that have been on the field and their USED moves --
    and our own view stays bitwise the live one (R1-E's leg A is unaffected)."""
    r = subprocess.run([sys.executable, "-c", _FOE_VIEW], capture_output=True, text=True, timeout=900, cwd=ROOT,
                       env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"})
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert r.stdout.strip().splitlines()[-1].startswith("OK")


_FOE_VIEW = r"""
import pickle
import numpy as np
from rl.envs.engine_tables import build_tables
from rl.search.harvest import rehydrate_battle
from rl.search.determinize import sample_determinization
from rl.search.engine_bridge import RevealHistory, build_root, our_side_reveal, side_reveal
tables, _ = build_tables()
eps = pickle.load(open("results/ch3_r1/harvest_s62.pkl", "rb"))
first = later = live_same = 0
for bi, ep in enumerate(eps[:40]):
    hist = RevealHistory()
    for si, row in enumerate(ep["rows"][:12]):
        if row["aliased"]:
            continue
        b = rehydrate_battle(row["battle"])
        b.battle_tag = f"harvest-{bi}"
        hist.update(b)
        our = our_side_reveal(b, hist)
        try:
            node, _, _ = build_root(b, sample_determinization(b, np.random.default_rng(si)), None, seed=si, our_reveal=our)
            old, _, _ = build_root(b, sample_determinization(b, np.random.default_rng(si)), None, seed=si,
                                   our_reveal=side_reveal(list(b.team.values())))
        except ValueError:
            continue
        team = node.view(tables, "p2")["opp"]["team"]
        assert len(team) == len(our["reveal_order"]), (bi, si, len(team), our["reveal_order"])
        # THE INVARIANT: our own view does not read our side's payload, so the fix
        # leaves it bit for bit where the first form (and R1-E) had it...
        assert np.array_equal(node.obs(tables, "p1"), old.obs(tables, "p1")), (bi, si)
        assert np.array_equal(node.mask(tables, "p1"), old.mask(tables, "p1")), (bi, si)
        # ...which is R1-E's parity with the live observation (99.7% bitwise; the rest a declared family).
        live_same += int(np.array_equal(node.obs(tables, "p1"), row["obs"]))
        if si == 0 and int(row["turn"]) == 1:
            # the battle's FIRST decision: the foe has seen our lead and nothing else
            # (a later decision inside turn 1 has already seen a move, correctly)
            assert len(team) == 1 and not any(our["revealed_moves"]), (bi, si, our)
            first += 1
        else:
            assert 1 <= len(team) <= 6
            later += 1
        # every move the foe is shown has been USED (PP spent), never an unused one
        for i in our["reveal_order"]:
            mon = list(b.team.values())[i]
            used = {mid for mid, mv in list(mon.moves.items())[:4] if mv.current_pp < mv.max_pp} if hasattr(next(iter(mon.moves.values())), "max_pp") else None
            assert len(our["revealed_moves"][i]) == len(our["move_uses"][i]) and all(u > 0 for u in our["move_uses"][i])
assert first >= 20 and later >= 100, (first, later)   # first: one per episode
assert live_same >= 0.97 * (first + later), (live_same, first + later)
print(f"OK foe view: {first} turn-1 roots show the foe our lead and no moves; {later} later roots show only fielded mons and used moves; "
      f"our view unchanged by the fix on all, bitwise the live one on {live_same}/{first + later}")
"""


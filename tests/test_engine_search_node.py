"""R7 B0 -- the batched leaf path, from Python (`engine/pkmn_gen1/src/search.rs`,
`pysearch.rs`; `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md` §3, §7).

The Rust side already proves the leaf is bit-for-bit the collector's own next
observation (`expand_reproduces_the_training_construction_bitwise`). This file
checks the SEAM: that what crosses PyO3 is that construction, in the shapes the
solver and the rollout instrument will consume, driven from a live `BatchEnv`.

No server, no throughput claim. Skips loudly without the built extension or a
team bank.
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
# The SMALLEST bank (see tests/test_engine_batchenv.py for why not the last).
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")),
               key=lambda p: pathlib.Path(p).stat().st_size)

# The encoder flags are read at import, so the body runs in a subprocess.
_CHILD = r"""
import pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables

tables, _fp = build_tables()
_header, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
K = 16
env = pkmn_gen1.BatchEnv(K, 777, tables, payload, "p1", privileged=True)
assert env.learner_seat == "p1"
rng = np.random.default_rng(0)

def act(seat):
    idx, obs, mask, _m = env.pending(seat)
    a = np.array([rng.choice(np.flatnonzero(m)) for m in mask], dtype=np.int64)
    return idx, obs, mask, a

compared = 0; terminals = 0; crn_checked = 0; rolled = 0
for step in range(400):
    li, lobs, lmask, la = act("learner")
    oi, oobs, omask, oa = act("opponent")
    if compared < 120 and len(li):
        # A slot where BOTH seats owe a decision: expand the played cell.
        both = sorted(set(li.tolist()) & set(oi.tolist()))
        for slot in both[:2]:
            node = env.snapshot(slot)
            assert not node.over()
            r1, r2 = node.requests()
            assert r1 != "pass" and r2 != "pass", (r1, r2)
            # The root's own view and mask are what pending() handed out.
            j = int(np.flatnonzero(li == slot)[0]); k = int(np.flatnonzero(oi == slot)[0])
            assert np.array_equal(node.obs(tables, "p1"), lobs[j]), "root obs != pending obs"
            assert np.array_equal(node.mask(tables, "p1"), lmask[j])
            assert np.array_equal(node.obs(tables, "p2"), oobs[k])
            assert np.array_equal(node.mask(tables, "p2"), omask[k])
            rows = np.flatnonzero(lmask[j]).tolist(); cols = np.flatnonzero(omask[k]).tolist()
            cells = [(r, c, 2) for r in rows for c in cols]
            e = node.expand(tables, "p1", cells, seed_base=0xB0 + step, both_views=True)
            n = e["n"]; assert n == 2 * len(cells)
            assert e["obs"].shape == (n, 828) and e["obs2"].shape == (n, 828)
            assert e["priv"].shape == (n, 408) and e["priv2"].shape == (n, 408)
            assert e["req_next"].shape == (n, 2) and e["terminal"].shape == (n,)
            assert e["cell"].tolist() == [i for i in range(len(cells)) for _ in range(2)]
            assert e["sample"].tolist() == [0, 1] * len(cells)
            # CRN-1 across rows: same col & sample -> same seed, whatever the row.
            seeds = e["seed"].reshape(len(rows), len(cols), 2)
            assert (seeds == seeds[0:1]).all(), "the chance seed depends on the row"
            assert len(set(seeds[0].ravel().tolist())) == len(cols) * 2, "cols/samples share a seed"
            crn_checked += 1
            live = e["terminal"] == 0
            if live.any():
                o = e["obs"][live]; o2 = e["obs2"][live]
                assert np.isfinite(o).all() and o.min() >= -1.0 and o.max() <= 4.0
                # D18's block is a slice of the OTHER seat's full encode: check the
                # slice rule from Python, independently of the Rust helper.
                GLOBAL, PRIV_OWN_END, ID_DIM = 6, 404, 20
                own = PRIV_OWN_END - GLOBAL; ido = 828 - ID_DIM
                want = np.concatenate([o2[:, GLOBAL:PRIV_OWN_END], o2[:, ido:ido + 6], o2[:, ido + 12:ido + 16]], 1)
                assert np.array_equal(e["priv"][live], want), "priv is not the foe's own-side slice"
                want2 = np.concatenate([o[:, GLOBAL:PRIV_OWN_END], o[:, ido:ido + 6], o[:, ido + 12:ido + 16]], 1)
                assert np.array_equal(e["priv2"][live], want2)
                # A live leaf where WE owe a decision carries a non-empty view.
                ours = live & (e["req_next"][:, 0] != 0)
                assert (np.abs(e["obs"][ours]).sum(1) > 0).all()
            dead = ~live
            if dead.any():
                assert (e["obs"][dead] == 0).all(), "a terminal leaf encodes nothing"
                assert set(e["terminal"][dead].tolist()) <= {1, -1, 2}
                terminals += int(dead.sum())
            # The played cell, under the SAME seed, is the env's next obs for
            # this slot -- the seam-level replay of the Rust parity test.
            played = cells.index((int(la[j]), int(oa[k]), 2))
            assert e["turn"][2 * played] >= node.turn()
            compared += 1
    if rolled < 2 and len(li) and step > 20:
        # The rollout leaf: expand one slot's full matrix into a LeafBatch and
        # play it out with random actions on BOTH seats through pending/step.
        slot = int(li[0])
        node = env.snapshot(slot)
        rows = np.flatnonzero(node.mask(tables, "p1")).tolist()
        cols = np.flatnonzero(node.mask(tables, "p2")).tolist() or [-1]
        lb = node.leaves(tables, "p1", [(r, c, 3) for r in rows for c in cols], seed_base=99 + step)
        assert lb.n == 3 * len(rows) * len(cols)
        guard = 0
        while lb.live() > 0:
            guard += 1; assert guard < 6000, "rollouts did not terminate"
            acts = {}
            for seat in ("p1", "p2"):
                idx, obs, mask = lb.pending(tables, seat)
                assert obs.shape == (len(idx), 828) and mask.shape == (len(idx), 10)
                if len(idx):
                    assert mask.any(1).all()
                acts[seat] = (idx.tolist(), [int(rng.choice(np.flatnonzero(m))) for m in mask])
            lb.step(tables, acts["p1"][0], acts["p1"][1], acts["p2"][0], acts["p2"][1])
        o1 = lb.outcome("p1"); o2 = lb.outcome("p2")
        assert set(o1.tolist()) <= {1, -1, 2} and lb.done().all()
        assert np.array_equal(o1, np.where(o2 == 2, 2, -o2)), "outcomes are not mirrored"
        assert (lb.turns() > node.turn()).all()
        assert lb.cell().shape == (lb.n,) and lb.sample().shape == (lb.n,)
        # A scripted rollout on a fresh batch also finishes.
        lb2 = node.leaves(tables, "p1", [(rows[0], cols[0], 4)], seed_base=5)
        guard = 0
        while lb2.scripted_step(tables, "random") > 0:
            guard += 1; assert guard < 6000
        assert (lb2.outcome("p1") != 0).all()
        rolled += 1
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), step, oi.tolist(), oa.tolist())
    env.drain_finished()
    if compared >= 120 and rolled >= 2:
        break

assert compared >= 60, compared
assert crn_checked >= 60, crn_checked
assert rolled >= 2, rolled
# from_battle / with_battle round-trip on a live root: same bytes, same views.
node = env.snapshot(0)
b = node.battle()
r1, r2 = node.requests()
same = node.with_battle(b, r1, r2)
assert np.array_equal(same.obs(tables, "p1"), node.obs(tables, "p1"))
assert np.array_equal(same.obs(tables, "p2"), node.obs(tables, "p2"))
fresh = pkmn_gen1.SearchNode.from_battle(b, r1, r2)
assert fresh.turn() == node.turn() and fresh.requests() == (r1, r2)
assert len(fresh.revealed("p2")) <= len(node.revealed("p2"))
# Illegal cells are refused by name, never handed to the engine.
bad = int(np.flatnonzero(~node.mask(tables, "p1"))[0]) if (~node.mask(tables, "p1")).any() else None
if bad is not None and r1 != "pass":
    try:
        node.expand(tables, "p1", [(bad, 6, 1)], 0)
    except ValueError as err:
        assert "not legal" in str(err) or "owes" in str(err), err
    else:
        raise AssertionError("an illegal row was accepted")
print(f"OK compared {compared} roots, {terminals} terminal leaves, {rolled} rollout batches")
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_search_node_expands_the_collectors_own_construction():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[0]],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")

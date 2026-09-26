"""DEEP SEARCH Step C's enabler -- `rl/search/tree_top.py::TreeOp`, the T-op's seams with
the native tree inside, OFFLINE: a fake env whose snapshots are hand-built roots, a
stub agent (a linear actor and critic), no collector and no team bank.

What must hold (the T-op's own contract, tests/test_top_collector.py, on this operator):
  * one record per learner decision, taken back in row order and asserted against the
    episode's length; searched rows carry a pi' that is a distribution on the mask and a
    finite v', unsearched rows zeros;
  * forced rows and confident rows (top-1 >= top1_skip) are never searched; the dose is
    the coin at `frac`;
  * PLAY: the played action is a support point of pi' and its log-prob is EXACTLY
    float32(log pi'(a)) from the stored float32 pi'; RECORD-ONLY leaves actions and
    log-probs untouched;
  * the rows a round searches go through ONE search_many call (tree/batch_rows > 1);
  * the dial list is the signature (an unknown key fails, `play` and `tree` are
    required, the tree's dials are validated); an antisymmetric or privileged critic is
    refused; `searcher_class` picks the TreeOp only for a block that carries `tree`.
Runs in a subprocess with both encoder env vars set; skips without the extension.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

_CHILD = r"""
import numpy as np
import torch
import pkmn_gen1
from rl.envs.engine_tables import build_tables
from rl.search.tree_top import TreeOp, searcher_class
from rl.search.top import TOp

torch.manual_seed(0)
tables, _ = build_tables()
def mon(species, moves, level=100):
    return pkmn_gen1.pokemon_record(species, level, moves, [15] * 5, [255] * 5)
P1 = [mon(128, [34, 63, 89, 59]), mon(113, [58, 85, 86, 135]), mon(143, [34, 115, 156, 89])]
P2 = [mon(121, [57, 94, 86, 105]), mon(103, [79, 94, 153, 72]), mon(65, [94, 69, 86, 105])]
b = pkmn_gen1.Battle(7, P1, P2)
_, r1, r2 = b.update("pass", ("pass", 0), "pass", ("pass", 0))
root = pkmn_gen1.SearchNode.from_battle(b, r1, r2)
lb = root.leaves(tables, "p1", [(6, 6, 3)], 5)
for _ in range(6):
    lb.scripted_step(tables, "random")
mid = lb.node(1)

class Agent:
    device = torch.device("cpu")
    antisymmetric_critic = False
    privileged_dim = 0
    def __init__(self):
        self.actor = torch.nn.Linear(828, 10)
        self.critic = torch.nn.Sequential(torch.nn.Linear(828, 1), torch.nn.Tanh())

class Env:
    def __init__(self, nodes):
        self.nodes = nodes
    def snapshot(self, slot):
        return self.nodes[slot]

agent = Agent()
nodes = {0: root, 1: mid, 2: root, 3: mid}
env = Env(nodes)
idx = np.array([0, 1, 2, 3])
obs = np.stack([np.asarray(nodes[s].obs(tables, "p1"), np.float32) for s in idx])
mask = np.stack([np.asarray(nodes[s].mask(tables, "p1"), bool) for s in idx])
act0 = np.array([int(np.flatnonzero(m)[0]) for m in mask])
lp0 = np.full(4, -1.5, np.float32)
TREE = {"sims": 120, "mode": "br_prior", "root_rule": "gumbel_mctx", "batch": 2}

# (1) RECORD-ONLY at frac 1: every row searched in ONE call, actions untouched, records aligned
op = TreeOp(agent, tables, seat="p1", seed=3, frac=1.0, top1_skip=1.0, play=False, tree=TREE)
a, lp = op.decide(env, idx, obs, mask, act0, lp0)
assert np.array_equal(a, act0) and np.array_equal(lp, lp0)
st = op.stats()
assert st["search/searched_frac"] == 1.0 and st["tree/batch_rows"] == 4.0, st
assert st["tree/sims"] >= 120 and st["tree/depth_mean"] > 1.0 and st["tree/errors"] == 0 and st["tree/fallback"] == 0, st
for s in idx:
    rec = op.take(int(s), 1)
    pi = rec["search_pi"][0]
    assert rec["search_mask"][0] and abs(pi.sum() - 1) < 1e-5 and (pi[~mask[s]] == 0).all() and np.isfinite(rec["search_v"][0])
try:
    op.take(0, 1); raise SystemExit("a slot with no records was taken")
except RuntimeError as err:
    assert "misaligned" in str(err)

# (2) PLAY: a support point of pi', log-prob exactly float32(log pi'(a)) of the STORED pi'
op = TreeOp(agent, tables, seat="p1", seed=4, frac=1.0, top1_skip=1.0, play=True, tree=TREE)
a, lp = op.decide(env, idx, obs, mask, act0, lp0)
for i, s in enumerate(idx):
    rec = op.take(int(s), 1)
    pi32 = rec["search_pi"][0]
    assert mask[i][a[i]] and pi32[a[i]] > 0
    assert lp[i] == np.float32(np.log(np.float64(pi32[a[i]]))), (lp[i], pi32[a[i]])
assert op.stats()["search/played_frac"] == 1.0

# (3) DOSE: frac 0 searches nothing; top1_skip excludes confident rows; a forced row is never searched
op = TreeOp(agent, tables, seat="p1", seed=5, frac=0.0, top1_skip=1.0, play=False, tree=TREE)
op.decide(env, idx, obs, mask, act0, lp0)
assert op.stats()["search/searched_frac"] == 0.0
op = TreeOp(agent, tables, seat="p1", seed=5, frac=1.0, top1_skip=1e-9, play=False, tree=TREE)
op.decide(env, idx, obs, mask, act0, lp0)
assert op.stats()["search/searched_frac"] == 0.0
forced = mask.copy(); forced[0] = False; forced[0, int(np.flatnonzero(mask[0])[0])] = True
op = TreeOp(agent, tables, seat="p1", seed=5, frac=1.0, top1_skip=1.0, play=False, tree=TREE)
op.decide(env, idx, obs, forced, act0, lp0)
assert not op.take(0, 1)["search_mask"][0] and op.take(1, 1)["search_mask"][0]

# (3b) A FALLBACK (every world failed): the tree's v is NaN, so the row is recorded UNSEARCHED and counted --
# never a NaN value target for the learner
import rl.search.tree_top as tt
real = tt.native_tree.search_many
def all_failed(specs, *a, **k):
    out = real(specs, *a, **k)
    for r in out:
        r["counters"]["tree/fallback"] = 1.0
        r["v"] = float("nan")
    return out
tt.native_tree.search_many = all_failed
try:
    op = TreeOp(agent, tables, seat="p1", seed=6, frac=1.0, top1_skip=1.0, play=True, tree=TREE)
    a, lp = op.decide(env, idx, obs, mask, act0, lp0)
finally:
    tt.native_tree.search_many = real
assert np.array_equal(a, act0) and np.array_equal(lp, lp0)
st = op.stats()
assert st["search/searched_frac"] == 0.0 and st["tree/fallback_frac"] == 1.0 and st["search/played_frac"] == 0.0, st
for s_ in idx:
    rec = op.take(int(s_), 1)
    assert not rec["search_mask"][0] and rec["search_v"][0] == 0.0 and (rec["search_pi"][0] == 0).all()

# (4) THE DIALS: the signature's; play and tree required; the tree's dials validated; unknown keys fail
assert sorted(TreeOp.dials()) == ["frac", "play", "top1_skip", "tree"]
for bad, msg in (({"frac": 0.5, "tree": TREE}, "missing required"), ({"play": False}, "missing required"),
                 ({"play": False, "tree": TREE, "cols_k": 4}, "unknown tree-op key"),
                 ({"play": False, "tree": {"sims": 10, "depth3": 1}}, "unknown native-tree dial")):
    try:
        TreeOp.check_dials(bad); raise SystemExit(f"{bad} accepted")
    except ValueError as err:
        assert msg in str(err), (bad, err)
class Anti(Agent):
    antisymmetric_critic = True
try:
    TreeOp(Anti(), tables, seat="p1", seed=1, play=False, tree=TREE); raise SystemExit("antisymmetric critic accepted")
except ValueError as err:
    assert "antisymmetric" in str(err)
assert searcher_class({"play": False, "tree": TREE}) is TreeOp
assert searcher_class({"play": False, "frac": 0.4, "cols_k": 4, "chance_s": 2, "tau": 0.05}) is TOp
try:
    searcher_class({"play": False, "cols_k": 4, "tree": TREE}); raise SystemExit("a mixed block accepted")
except ValueError as err:
    assert "unknown tree-op key" in str(err)
print("OK tree-op seams hold")
"""


def test_tree_op_seams():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True, text=True, timeout=900,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    assert r.stdout.strip().splitlines()[-1].startswith("OK")

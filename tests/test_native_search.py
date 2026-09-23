"""R7 B3 -- `rl/search/native.py::solve`, the native operator: goldens on fixed
roots, the invariants, and the derived dial list (runner brief §4; the
`tests/test_tree_decision_golden.py` pattern).

GOLDEN VALUES so "did my edit change the search?" is answerable in a second.
The roots are HAND-BUILT (no team bank): a 3-v-3 at turn 1 from
`pkmn_gen1.Battle` records, and a mid-battle root reached by playing one leaf
forward six scripted updates. The critic is a numpy stub (a fixed random
projection of both views, tanh'd) and the priors are seeded draws, so nothing
here depends on a checkpoint or on torch. The values are not meaningful in
themselves; what is meaningful is that they do not MOVE. A change is not
automatically a bug -- it means the operator now decides differently, and any
in-flight block comparing arms across it is comparing two algorithms.

Runs in a subprocess with both encoder env vars set (the tables are built
from poke-env at import). Skips loudly without the built extension.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

_CHILD = r"""
import json, math
import numpy as np
import pkmn_gen1
from rl.envs.engine_tables import build_tables
from rl.search import native
from rl.search.native import DIALS, World, counter_names, dials_from, seed_base, solve

def mon(species, moves, level=100):
    return pkmn_gen1.pokemon_record(species, level, moves, [15] * 5, [255] * 5)
# Tauros / Chansey / Snorlax vs Starmie / Exeggutor / Alakazam, gen-1 ids.
P1 = [mon(128, [34, 63, 89, 59]), mon(113, [58, 85, 86, 135]), mon(143, [34, 115, 156, 89])]
P2 = [mon(121, [57, 94, 86, 105]), mon(103, [79, 94, 153, 72]), mon(65, [94, 69, 86, 105])]
tables, _ = build_tables()
b = pkmn_gen1.Battle(7, P1, P2)
_, r1, r2 = b.update("pass", ("pass", 0), "pass", ("pass", 0))
root = pkmn_gen1.SearchNode.from_battle(b, r1, r2)
assert (root.turn(), root.requests()) == (1, ("move", "move"))
W = np.random.default_rng(0).normal(size=828) * 0.05
def stub(e):
    return np.tanh(e["obs"] @ W - e["obs2"] @ W)
def priors(node, seed):
    g = np.random.default_rng(seed)
    out = []
    for seat in ("p1", "p2"):
        m = np.asarray(node.mask(tables, seat), bool)
        p = np.where(m, g.random(10), 0.0)
        out.append(p / p.sum() if p.sum() > 0 else p)
    return out

GOLDEN = {
 "g0": {"action": 8, "policy_action": 8, "rows": [1, 2, 6, 7, 8, 9], "cols": [8, 6, 2],
        "pi": [0.0, 0.245656, 0.188533, 0.0, 0.0, 0.0, 0.021183, 0.039255, 0.304229, 0.201143],
        "q_row": [None, 0.096848, -0.354072, None, None, None, -0.395201, -0.38965, -0.330843, -0.322661],
        "counters": {"search/leaves": 36.0, "search/rows": 6.0, "search/cols": 3.0, "search/worlds": 1.0,
                     "search/override": 0.0, "search/kl_prior": 0.016464, "search/margin": 0.0,
                     "search/pi_top1": 0.304229, "search/prior_top1": 0.330292, "search/topk_mass": 0.577508,
                     "search/terminal_frac": 0.0, "search/pass_leaf_frac": 0.055556,
                     "search/v": -0.232183, "search/v_prior": -0.263801}},
 "g1": {"action": 1, "policy_action": 1, "rows": [1, 2, 6, 7, 8, 9], "cols": [7, 1, 6],
        "pi": [0.0, 0.316823, 0.054386, 0.0, 0.0, 0.0, 0.167539, 0.028326, 0.222772, 0.210155],
        "q_row": [None, -0.301379, -0.454022, None, None, None, -0.59341, -0.608542, -0.598819, -0.613596],
        "counters": {"search/leaves": 36.0, "search/rows": 6.0, "search/cols": 3.0, "search/worlds": 1.0,
                     "search/override": 0.0, "search/kl_prior": 0.009336, "search/margin": 0.0,
                     "search/pi_top1": 0.316823, "search/prior_top1": 0.257547, "search/topk_mass": 0.811663,
                     "search/terminal_frac": 0.0, "search/pass_leaf_frac": 0.138889,
                     "search/v": -0.499183, "search/v_prior": -0.517525}},
}

def run(node, key, **dials):
    p, q = priors(node, key)
    return solve([World(node)], tables, "p1", p, q, stub, key, **dials)

def check(r, g, label):
    assert r["action"] == g["action"] and r["policy_action"] == g["policy_action"], (label, r["action"], r["policy_action"])
    assert r["rows"] == g["rows"] and r["cols"] == g["cols"], (label, r["rows"], r["cols"])
    assert [round(float(x), 6) for x in r["pi"]] == g["pi"], (label, r["pi"])
    got_q = [None if np.isnan(x) else round(float(x), 6) for x in r["q_row"]]
    assert got_q == g["q_row"], (label, got_q)
    for k, v in g["counters"].items():
        assert round(r["counters"][k], 6) == v, (label, k, r["counters"][k], v)
    assert set(r["counters"]) == set(counter_names()), sorted(set(r["counters"]) ^ set(counter_names()))
    assert r["counters"]["search/ms"] > 0 and r["counters"]["search/rust_ms"] > 0

# (1) the goldens, on the turn-1 root and a mid-battle root.
r0 = run(root, 11); check(r0, GOLDEN["g0"], "g0")
lb = root.leaves(tables, "p1", [(6, 6, 3)], 5)
for _ in range(6):
    lb.scripted_step(tables, "random")
mid = lb.node(1)
assert (mid.turn(), mid.requests(), mid.over()) == (8, ("move", "move"), False), (mid.turn(), mid.requests())
r1_ = run(mid, 12); check(r1_, GOLDEN["g1"], "g1")

# (2) determinism: the same call twice is bitwise the same (CRN, no hidden rng).
r0b = run(root, 11)
assert np.array_equal(r0["pi"], r0b["pi"]) and np.array_equal(r0["q_cell"], r0b["q_cell"])
assert r0["counters"]["search/kl_prior"] == r0b["counters"]["search/kl_prior"]
# ...and a different decision key changes the chance draws, not the shape.
r0c = run(root, 13)
assert r0c["rows"] == r0["rows"]
# (3) pi' is a distribution on the mask, KL >= 0, and Qbar is the q-weighted row mean.
m = np.asarray(root.mask(tables, "p1"), bool)
assert abs(r0["pi"].sum() - 1) < 1e-12 and (r0["pi"][~m] == 0).all() and (r0["pi"][m] > 0).all()
assert r0["counters"]["search/kl_prior"] >= 0
assert np.allclose(r0["q_cell"] @ r0["q_col"], r0["q_row"][m])
assert abs(r0["v"] - float(r0["pi"][m] @ r0["q_row"][m])) < 1e-12
# (4) the temperature: tau -> inf recovers the prior; tau -> 0 plays argmax Qbar.
p, q = priors(root, 11)
hot = solve([World(root)], tables, "p1", p, q, stub, 11, tau=1e6)
assert hot["counters"]["search/kl_prior"] < 1e-9 and hot["action"] == hot["policy_action"]
cold = solve([World(root)], tables, "p1", p, q, stub, 11, tau=1e-4)
assert cold["action"] == int(np.nanargmax(cold["q_row"]))
# (5) columns: cols_k=1 is the foe's single most likely reply, full mass 1.0 when k covers all.
one = solve([World(root)], tables, "p1", p, q, stub, 11, cols_k=1)
assert one["cols"] == [int(np.argmax(q))] and one["counters"]["search/cols"] == 1.0
alls = solve([World(root)], tables, "p1", p, q, stub, 11, cols_k=10)
assert alls["counters"]["search/topk_mass"] == 1.0 and alls["counters"]["search/cols"] == float(np.count_nonzero(q))
# (6) chance: S samples per cell -> S x the leaves, same rows/cols.
s4 = solve([World(root)], tables, "p1", p, q, stub, 11, chance_s=4)
assert s4["counters"]["search/leaves"] == 2 * r0["counters"]["search/leaves"]
# (7) worlds: two copies of the root, distinct chance streams, weights honoured.
two = solve([World(root, 1.0), World(root, 3.0)], tables, "p1", p, q, stub, 11)
# The root_rule dial (amendment box 4 item 5): regret matching's average
# strategy over the SAME matrix -- a valid mix, flagged in the counters; the
# default ("soft_br") is the goldens above, bit for bit.
rm = solve([World(root)], tables, "p1", p, q, stub, 11, root_rule="regret_matching", rm_iters=500)
assert abs(rm["pi"].sum() - 1) < 1e-9 and (rm["pi"][~np.asarray(root.mask(tables, "p1"), bool)] == 0).all()
assert rm["counters"]["search/root_rule_rm"] == 1.0 and two["counters"]["search/root_rule_rm"] == 0.0
assert not np.array_equal(rm["pi"], solve([World(root)], tables, "p1", p, q, stub, 11)["pi"]) or rm["pi"].max() > 0.999
try:
    solve([World(root)], tables, "p1", p, q, stub, 11, root_rule="nope"); raise SystemExit("unknown root_rule accepted")
except ValueError as e:
    assert "root_rule" in str(e)
assert two["counters"]["search/worlds"] == 2.0 and two["counters"]["search/leaves"] == 72.0
# (8) the other seat: solving as p2 on the same root uses p2's mask and p1's prior as the foe's.
r2 = solve([World(root)], tables, "p2", q, p, stub, 11)
assert r2["rows"] == np.flatnonzero(np.asarray(root.mask(tables, "p2"), bool)).tolist()
# (9) refusals: an unmasked prior, a finished/absent decision, a bad dial, an unknown dial.
try:
    solve([World(root)], tables, "p1", np.full(10, 0.1), q, stub, 11); raise SystemExit("unmasked prior accepted")
except ValueError as e: assert "masked" in str(e)
try:
    solve([World(root)], tables, "p1", p, q, stub, 11, tau=0.0); raise SystemExit("tau 0 accepted")
except ValueError as e: assert "tau" in str(e)
try:
    solve([World(root)], tables, "p1", p, q, stub, 11, chance_s=200, max_leaves_per_call=100); raise SystemExit("cap ignored")
except ValueError as e: assert "max_leaves_per_call" in str(e)
try:
    dials_from({"depth2": {}}); raise SystemExit("unknown dial accepted")
except ValueError as e: assert "unknown native-search dial" in str(e)
# (10) the dial list is the signature's, and coerces by annotation.
assert DIALS == ("cols_k", "chance_s", "tau", "max_leaves_per_call", "root_rule", "rm_iters"), DIALS   # + the root_rule dial (box 4 item 5)
assert dials_from({"cols_k": "4", "tau": "0.5"}) == {"cols_k": 4, "tau": 0.5}
# (11) seed_base never aliases decision and world in a small sweep.
keys = {seed_base(d, w) for d in range(200) for w in range(8)}
assert len(keys) == 1600
print("OK native operator goldens hold")
"""


def test_native_operator_goldens_and_invariants():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True, text=True, timeout=900,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")

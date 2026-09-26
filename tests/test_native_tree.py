"""DEEP SEARCH Step A -- `rl/search/native_tree.py`, the tree on the native engine:
its depth-1 REDUCTION to `native.solve`, the tree's invariants, the known-answer
FIXTURES of gate (i-b), the derived dial list, and GOLDENS so "did my edit change
the search?" is answerable in a second.

`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step A. Every root is
HAND-BUILT (`pkmn_gen1.Battle` records or `BattleSpec`), and the evaluators are
numpy stubs, so nothing here depends on a checkpoint or on torch. The goldens are
KEYED to OBS_DIM 828 and the pinned engine sha: a different encoder or engine is a
different search, and the test says so rather than comparing across them.

Fixtures (gate i-b), each against the engine's own answer:
  * a KO visible only at depth >= 2: with a ZERO critic the one-ply Qbar is exactly
    0 on every row, and the tree at depth cap 4 finds the win;
  * Hyper Beam's recharge: the child's rows are the engine's single forced action;
  * a partial-trap lock: after Wrap the user's rows are the engine's one locked move;
  * a Pass node: under `pass_leaf="through"` no Pass state is ever valued by the
    critic, and under "critic" the Pass share equals `native.solve`'s;
  * a double-KO tie: Explosion into the foe's last mon ends 2 (tie) -> 0.0, so the
    root prefers it against a -0.5 critic and avoids it against a +0.5 one;
  * a 2x2 prediction game (matching pennies via an observation-lookup critic):
    br_prior's Qbar is exactly M @ q, the best response to the foe's PRIOR, and
    sm_rm's average strategies approach the (1/2, 1/2) equilibrium.

Runs in a subprocess with both encoder env vars set (the tables are built from
poke-env at import). Skips loudly without the built extension.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

_CHILD = r"""
import hashlib
import numpy as np
import pkmn_gen1
from rl.envs.engine_tables import build_tables
from rl.envs.showdown import OBS_DIM
from rl.search import native, native_tree
from rl.search.native import World
from rl.search.native_tree import DIALS, dials_from, search

assert OBS_DIM == 828, f"the goldens are keyed to OBS_DIM 828, not {OBS_DIM}: regenerate them"
ENGINE = pkmn_gen1.build_info()["engine_sha"]
assert ENGINE.startswith("9b88fd6c"), f"the goldens are keyed to engine 9b88fd6c, not {ENGINE[:12]}: regenerate them"
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
assert (mid.turn(), mid.requests()) == (8, ("move", "move"))
W = np.random.default_rng(0).normal(size=828) * 0.05
M = np.random.default_rng(1).normal(size=(828, 10)) * 0.05
def stub(e):
    return np.tanh(e["obs"] @ W)
def prior_fn(obs, mask):
    z = np.where(mask, np.tanh(obs @ M) * 3, -np.inf)
    p = np.exp(z - z.max(axis=1, keepdims=True)); p[~mask] = 0
    return p / p.sum(axis=1, keepdims=True)
def priors(node):
    out = []
    for seat in ("p1", "p2"):
        m = np.asarray(node.mask(tables, seat), bool)
        out.append(prior_fn(np.asarray(node.obs(tables, seat), np.float32)[None], m[None])[0] if m.any() else np.zeros(10))
    return out

# (1) THE REDUCTION: at depth cap 1 the tree IS native.solve, bit for bit.
for node, key in ((root, 11), (mid, 12)):
    p, q = priors(node)
    for ck, cs in ((4, 2), (3, 2), (10, 1), (2, 4)):
        ref = native.solve([World(node)], tables, "p1", p, q, stub, key, cols_k=ck, chance_s=cs, tau=0.05, both_views=False)
        got = search([World(node)], tables, "p1", p, q, stub, prior_fn, key, sims=len(ref["rows"]) * len(ref["cols"]) * cs,
                     root_rule="soft_br", depth_cap=1, cols_k=ck, chance_k=cs, tau=0.05, pass_leaf="critic")
        assert np.array_equal(ref["pi"], got["pi"]) and np.array_equal(ref["q_row"], got["q_row"], equal_nan=True), (key, ck, cs)
        assert ref["action"] == got["action"] and ref["policy_action"] == got["policy_action"]
        for k in ("search/leaves", "search/rows", "search/cols", "search/override", "search/kl_prior", "search/margin",
                  "search/topk_mass", "search/terminal_frac", "search/pass_leaf_frac", "search/v", "search/v_prior"):
            assert ref["counters"][k] == got["counters"][k], (key, ck, cs, k, ref["counters"][k], got["counters"][k])

# (2) the per-edge path renders exactly what expand() renders (the grid uses expand; below it, leaves + pending).
cells = [(a, c, 3) for a in np.flatnonzero(root.mask(tables, "p1"))[:3].tolist() for c in np.flatnonzero(root.mask(tables, "p2"))[:2].tolist()]
e = root.expand(tables, "p1", cells, 77, both_views=False)
lbx = root.leaves(tables, "p1", cells, 77)
idx, obs, _m = lbx.pending(tables, "p1")
live = (np.asarray(e["terminal"]) == 0) & (np.asarray(e["req_next"])[:, 0] != 0)
assert np.array_equal(np.asarray(idx), np.flatnonzero(live)) and np.array_equal(obs, e["obs"][live])

# (3) INVARIANTS on deep searches: every visit accounted, virtual loss drained, rows and
# columns are the ENGINE's masks at every expanded node, deterministic, any batch, any worlds.
def walk(x, seen, check_masks):
    if id(x) in seen or x.N is None:
        return
    seen.add(id(x))
    assert np.all(x.VL == 0) and abs(x.n - x.N.sum()) < 1e-9
    if check_masks and x.batch is not None:
        sn = x.sn or x.batch.lb.node(x.li)
        m1 = np.flatnonzero(sn.mask(tables, "p1")).tolist(); m2 = np.flatnonzero(sn.mask(tables, "p2")).tolist()
        assert x.rows == (m1 or [-1]), (x.rows, m1)
        assert set(x.cols) <= set(m2 or [-1]) and len(x.cols) == min(len(m2), cols_k) if m2 else x.cols == [-1]
    for (ri, ci), ed in x.edges.items():
        assert abs(sum(ed.n) - x.N[ri, ci]) < 1e-9 and all(v == 0 for v in ed.vl)
        for kid in ed.kids:
            if kid is not None:
                walk(kid, seen, check_masks)
p, q = priors(root)
cols_k = 4
for cfg in (dict(), dict(batch=8), dict(mode="legacy", root_grid=False, root_rule="legacy_gumbel", batch=4),
            dict(mode="sm_rm", root_grid=False, root_rule="rm_average", batch=2), dict(pass_leaf="critic", batch=16)):
    for nw in (1, 3):
        trees = []
        r = search([World(root)] * nw, tables, "p1", p, q, stub, prior_fn, 11, sims=900, _inspect=trees.append, **cfg)
        assert sum(t.root.N.sum() for t in trees) == r["counters"]["tree/sims"] == 900, (cfg, nw)
        seen = set()
        for t in trees:
            walk(t.root, seen, check_masks=(nw == 1))
        r2 = search([World(root)] * nw, tables, "p1", p, q, stub, prior_fn, 11, sims=900, **cfg)
        assert np.array_equal(r["pi"], r2["pi"]) and np.array_equal(r["q_row"], r2["q_row"], equal_nan=True), (cfg, nw)
        assert r["counters"]["tree/errors"] == 0 and r["counters"]["tree/fallback"] == 0
        assert r["counters"]["tree/depth_max"] >= 3, (cfg, r["counters"]["tree/depth_max"])

# (4) GOLDENS (600 simulations, the stub evaluators): a change means the search now decides differently.
GOLDEN = {
 "br": (dict(), 1, [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [None, -0.202683, -0.343773, None, None, None, -0.48887, -0.396242, -0.484438, -0.365525],
        {"search/leaves": 588.0, "tree/nodes": 582.0, "tree/merges": 147.0, "tree/pass_nodes": 4.0,
         "tree/depth_mean": 3.718333, "tree/depth_max": 8.0, "tree/capped_sims": 14.0, "search/kl_prior": 2.65323}),
 "legacy": (dict(mode="legacy", root_grid=False, root_rule="legacy_gumbel", cols_k=5), 9,
        [0.0, 0.402588, 0.136643, 0.0, 0.0, 0.0, 0.016222, 0.002381, 0.014653, 0.427513],
        [None, -0.45194, -0.46163, None, None, None, -0.556064, -0.57514, -0.553621, -0.521739],
        {"search/leaves": 599.0, "tree/nodes": 645.0, "tree/merges": 107.0, "tree/pass_nodes": 47.0,
         "tree/depth_mean": 3.008333, "tree/depth_max": 8.0, "tree/capped_sims": 2.0, "search/kl_prior": 0.618833}),
 "rm": (dict(mode="sm_rm", root_grid=False, root_rule="rm_average"), 1,
        [0.0, 0.423575, 0.078562, 0.0, 0.0, 0.0, 0.023677, 0.105558, 0.129703, 0.238924],
        [None, -0.333034, -0.385483, None, None, None, -0.486058, -0.450179, -0.463898, -0.452554],
        {"search/leaves": 601.0, "tree/nodes": 638.0, "tree/merges": 72.0, "tree/pass_nodes": 38.0,
         "tree/depth_mean": 2.583333, "tree/depth_max": 4.0, "tree/capped_sims": 0.0, "search/kl_prior": 0.77782}),
}
for name, (cfg, action, pi, q_row, cnt) in GOLDEN.items():
    r = search([World(root)], tables, "p1", p, q, stub, prior_fn, 11, sims=600, **cfg)
    assert r["action"] == action, (name, r["action"])
    assert [round(float(x), 6) for x in r["pi"]] == pi, (name, [round(float(x), 6) for x in r["pi"]])
    assert [None if np.isnan(x) else round(float(x), 6) for x in r["q_row"]] == q_row, (name, r["q_row"])
    for k, v in cnt.items():
        assert round(float(r["counters"][k]), 6) == v, (name, k, r["counters"][k], v)

# (4b) SEQUENTIAL HALVING at the root: rows eliminated in the same phase have EQUAL root visits, the
# finalists too, the survivors' visits only grow phase by phase, and it replays; it refuses a
# non-stationary root foe (legacy) and a root without the grid.
for nw, batch in ((1, 1), (3, 2)):
    trees = []
    r = search([World(root)] * nw, tables, "p1", p, q, stub, prior_fn, 11, sims=900 * nw, root_select="sequential_halving",
               batch=batch, _inspect=trees.append)
    n = r["n_row"][np.asarray(root.mask(tables, "p1"), bool)]
    groups = sorted(set(n.tolist()))
    assert r["counters"]["tree/sh_phases"] == 3.0 and r["counters"]["tree/sh_final"] == 2.0, r["counters"]
    assert len(groups) == 3 and sorted(n.tolist()).count(groups[-1]) == 2, n     # 6 rows: 3 out, 1 out, 2 finalists
    assert r["action"] in [int(a) for a, v in zip(np.flatnonzero(root.mask(tables, "p1")), n) if v == groups[-1]]
    assert all(np.all(t.root.VL == 0) for t in trees)
    r2 = search([World(root)] * nw, tables, "p1", p, q, stub, prior_fn, 11, sims=900 * nw, root_select="sequential_halving",
                batch=batch)
    assert r2["action"] == r["action"] and np.array_equal(r2["n_row"], r["n_row"]) and np.array_equal(r2["pi"], r["pi"])
for kw in (dict(mode="legacy", root_grid=False), dict(root_grid=False)):
    try:
        search([World(root)], tables, "p1", p, q, stub, prior_fn, 11, sims=50, root_select="sequential_halving", **kw)
        raise SystemExit(f"sequential_halving accepted {kw}")
    except ValueError as err:
        assert "sequential_halving" in str(err), err

# (4c) SEVERAL DECISIONS SEARCHED TOGETHER (search_many, the collector's case): every decision gets what it
# gets alone -- the same action, visits, depth and work, Q to float noise -- while the rounds share forwards.
from rl.search.native_tree import search_many
pm, qm = priors(mid)
specs = [([World(root)], p, q, 11), ([World(mid)], pm, qm, 12), ([World(root)] * 2, p, q, 13)]
for cfg in (dict(), dict(batch=4), dict(root_select="sequential_halving"), dict(mode="legacy", root_grid=False, root_rule="legacy_gumbel")):
    together = search_many(specs, tables, "p1", stub, prior_fn, sims=600, **cfg)
    for (ws, pp, qq, key), got in zip(specs, together):
        alone = search(ws, tables, "p1", pp, qq, stub, prior_fn, key, sims=600, **cfg)
        assert got["action"] == alone["action"] and np.array_equal(got["n_row"], alone["n_row"]), (cfg, key)
        assert np.allclose(got["q_row"], alone["q_row"], equal_nan=True, rtol=0, atol=1e-12), (cfg, key)
        for k in ("tree/sims", "search/leaves", "tree/nodes", "tree/merges", "tree/depth_mean", "tree/capped_sims"):
            assert got["counters"][k] == alone["counters"][k], (cfg, key, k, got["counters"][k], alone["counters"][k])
    assert sum(r["counters"]["tree/forwards_v"] for r in together) > max(r["counters"]["tree/forwards_v"] for r in together)
try:
    search_many(specs, tables, "p1", stub, prior_fn, sims=10, depth3=1); raise SystemExit("unknown dial accepted")
except ValueError as err:
    assert "unknown native-tree dial" in str(err)

# ---- (5) FIXTURES (gate i-b), on constructed roots
def ms(sp, moves, hp=None):
    return pkmn_gen1.MonSpec(sp, 100, [(m, pkmn_gen1.max_pp(m)) for m in moves], hp=hp)
def built(p1, p2, seed=3):
    bb, q1, q2 = pkmn_gen1.BattleSpec(1, seed, pkmn_gen1.SideSpec(p1, 0), pkmn_gen1.SideSpec(p2, 0)).build()
    return pkmn_gen1.SearchNode.from_battle(bb, q1, q2)
def uniform(node, seat):
    m = np.asarray(node.mask(tables, seat), bool)
    return np.where(m, 1.0 / max(m.sum(), 1), 0.0)
def prior_uniform(obs, mask):
    pu = mask.astype(np.float64)
    return pu / pu.sum(axis=1, keepdims=True)
def const(c):
    return lambda e: np.full(len(e["obs"]), float(c))
TAUROS, SNORLAX, CHANSEY, MAGIKARP, ARBOK, GENGAR = 128, 143, 113, 129, 24, 94
BODY_SLAM, SPLASH, GROWL, HYPER_BEAM, WRAP, EXPLOSION, TAIL_WHIP, LEER = 34, 150, 45, 63, 35, 153, 39, 43

# (5a) a KO visible only at depth >= 2: Tauros vs a Splash-only Snorlax at 55% HP.
ko = built([ms(TAUROS, [BODY_SLAM, SPLASH, GROWL])], [ms(SNORLAX, [SPLASH], hp=int(523 * 0.55))])
pk, qk = uniform(ko, "p1"), uniform(ko, "p2")
d1 = native.solve([World(ko)], tables, "p1", pk, qk, const(0.0), 5, cols_k=4, chance_s=8, tau=0.05, both_views=False)
assert np.all(d1["q_row"][d1["rows"]] == 0.0), d1["q_row"]
deep = search([World(ko)], tables, "p1", pk, qk, const(0.0), prior_uniform, 5, sims=3000, depth_cap=4, chance_k=4, root_rule="soft_br")
qd = deep["q_row"]
assert deep["action"] == 6 and qd[6] > 0.5 and qd[6] > qd[7] + 0.5 and qd[6] > qd[8] + 0.5, qd
shallow = search([World(ko)], tables, "p1", pk, qk, const(0.0), prior_uniform, 5, sims=3000, depth_cap=1, chance_k=4, root_rule="soft_br")
assert np.all(shallow["q_row"][shallow["rows"]] == 0.0), shallow["q_row"]

# (5b) Hyper Beam's recharge: the child after a non-KO Hyper Beam has ONE row, the engine's.
hb = built([ms(TAUROS, [HYPER_BEAM, BODY_SLAM])], [ms(CHANSEY, [SPLASH])])
trees = []
search([World(hb)], tables, "p1", uniform(hb, "p1"), uniform(hb, "p2"), const(0.0), prior_uniform, 5, sims=200, depth_cap=3,
       _inspect=trees.append)
rt = trees[0].root
kids = [k for (ri, ci), ed in rt.edges.items() if rt.rows[ri] == 6 for k in ed.kids if k is not None and k.N is not None]
assert kids and any(len(k.rows) == 1 for k in kids), [k.rows for k in kids]
walk(rt, set(), check_masks=True)

# (5c) a partial-trap lock: after Wrap, the user's rows are the engine's one locked move (Growl is gone).
wr = built([ms(ARBOK, [WRAP, GROWL])], [ms(SNORLAX, [SPLASH]), ms(CHANSEY, [SPLASH])])
trees = []
search([World(wr)], tables, "p1", uniform(wr, "p1"), uniform(wr, "p2"), const(0.0), prior_uniform, 5, sims=300, depth_cap=3,
       cols_k=10, _inspect=trees.append)
rt = trees[0].root
locked = [k for (ri, ci), ed in rt.edges.items() if rt.rows[ri] == 6 for k in ed.kids if k is not None and k.N is not None]
assert locked and any(k.rows == [6] for k in locked), [k.rows for k in locked]
cols_k = 10
walk(rt, set(), check_masks=True)
cols_k = 4

# (5d) a Pass node: Body Slam KOs a 10-HP Magikarp; the foe replaces it while we owe a Pass.
pn = built([ms(TAUROS, [BODY_SLAM, GROWL])], [ms(MAGIKARP, [SPLASH], hp=10), ms(SNORLAX, [SPLASH])])
pp_, qp_ = uniform(pn, "p1"), uniform(pn, "p2")
trees = []
thr = search([World(pn)], tables, "p1", pp_, qp_, stub, prior_uniform, 5, sims=300, depth_cap=3, cols_k=10, _inspect=trees.append)
assert thr["counters"]["search/pass_leaf_frac"] == 0.0 and thr["counters"]["tree/pass_nodes"] > 0
passes = [k for ed in trees[0].root.edges.values() for k in ed.kids if k is not None and k.term is None and not k.us_dec]
assert passes and all(k.v0 is None and k.rows == [-1] and k.n > 0 for k in passes)
grid = len(trees[0].root.rows) * len(trees[0].root.cols) * 2
crit = search([World(pn)], tables, "p1", pp_, qp_, stub, prior_uniform, 5, sims=grid, depth_cap=1, cols_k=10, pass_leaf="critic",
              root_rule="soft_br")
ref = native.solve([World(pn)], tables, "p1", pp_, qp_, stub, 5, cols_k=10, chance_s=2, tau=0.05, both_views=False)
assert crit["counters"]["search/pass_leaf_frac"] == ref["counters"]["search/pass_leaf_frac"] > 0
assert np.array_equal(crit["pi"], ref["pi"])

# (5e) a double-KO tie: Explosion into the foe's last mon -> outcome 2 -> 0.0.
dk = built([ms(GENGAR, [EXPLOSION, SPLASH])], [ms(MAGIKARP, [SPLASH], hp=5)])
e5 = dk.expand(tables, "p1", [(6, 6, 4)], 9, both_views=False)
assert list(e5["terminal"]) == [2, 2, 2, 2]
for c, want in ((-0.5, 6), (+0.5, 7)):
    r = search([World(dk)], tables, "p1", uniform(dk, "p1"), uniform(dk, "p2"), const(c), prior_uniform, 5, sims=200, depth_cap=2,
               root_rule="soft_br")
    assert r["q_row"][6] == 0.0 and r["action"] == want, (c, r["q_row"], r["action"])

# (5f) a 2x2 prediction game: matching pennies through an observation-lookup critic.
g = built([ms(TAUROS, [GROWL, TAIL_WHIP])], [ms(SNORLAX, [LEER, SPLASH])])
rows2 = np.flatnonzero(g.mask(tables, "p1")).tolist(); cols2 = np.flatnonzero(g.mask(tables, "p2")).tolist()
assert len(rows2) == 2 and len(cols2) == 2
table = {}
for i, a in enumerate(rows2):
    for j, c in enumerate(cols2):
        ex = g.expand(tables, "p1", [(a, c, 1)], native.seed_base(7, 0), both_views=False)
        table[hashlib.sha1(np.ascontiguousarray(ex["obs"][0]).tobytes()).hexdigest()] = 0.5 if i == j else -0.5
assert len(table) == 4
def lookup(e_):
    return np.array([table.get(hashlib.sha1(np.ascontiguousarray(o).tobytes()).hexdigest(), 0.0) for o in e_["obs"]])
qg = np.zeros(10); qg[cols2[0]] = 0.8; qg[cols2[1]] = 0.2
br = search([World(g)], tables, "p1", uniform(g, "p1"), qg, lookup, prior_uniform, 7, sims=4, depth_cap=1, chance_k=1,
            root_rule="soft_br", pass_leaf="critic")
assert np.allclose(br["q_row"][rows2], [0.3, -0.3], atol=1e-12) and br["action"] == rows2[0], br["q_row"]
trees = []
rm = search([World(g)], tables, "p1", uniform(g, "p1"), qg, lookup, prior_uniform, 7, sims=3000, depth_cap=1, chance_k=1,
            mode="sm_rm", root_grid=False, root_rule="rm_average", _inspect=trees.append)
foe_avg = trees[0].root.sm_foe / trees[0].root.sm_foe.sum()
assert np.all(np.abs(rm["pi"][rows2] - 0.5) < 0.05) and np.all(np.abs(foe_avg - 0.5) < 0.05), (rm["pi"][rows2], foe_avg)

# (6) the dial list is the signature's; unknown keys fail; values coerce by annotation; bad values refuse.
assert DIALS == ("sims", "mode", "root_rule", "root_select", "root_grid", "depth_cap", "cols_k", "chance_k", "pw_c",
                 "pw_alpha", "merge", "pass_leaf", "c_puct", "q_init", "opp_rule", "tau", "beta", "c_visit", "c_scale",
                 "gumbel_scale", "rm_gamma", "batch", "virtual_loss", "both_views", "deadline_ms"), DIALS
assert dials_from({"sims": "900", "tau": "0.5", "merge": False}) == {"sims": 900, "tau": 0.5, "merge": False}
for bad, msg in (({"depth2": 1}, "unknown native-tree dial"), ({"merge": "no"}, "must be a bool"), ({"sims": 1.5}, "integer")):
    try:
        dials_from(bad); raise SystemExit(f"{bad} accepted")
    except ValueError as err:
        assert msg in str(err), err
for kw, msg in ((dict(mode="duct"), "mode"), (dict(root_rule="rm_average"), "rm_average"), (dict(pass_leaf="x"), "pass_leaf"),
                (dict(tau=0.0), "tau"), (dict(chance_k=0), ">= 1")):
    try:
        search([World(root)], tables, "p1", p, q, stub, prior_fn, 11, sims=10, **kw); raise SystemExit(f"{kw} accepted")
    except ValueError as err:
        assert msg in str(err), (kw, err)
print("OK native tree reduction, invariants, fixtures and goldens hold")
"""


def test_native_tree_reduction_invariants_fixtures_and_goldens():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True, text=True, timeout=1800,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    assert r.stdout.strip().splitlines()[-1].startswith("OK")

"""DEEP SEARCH Step A -- the TREE on the native engine (`pkmn_gen1`).

`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step A. `rl/search/tree.py`
is the one search that has beaten greedy (RESULTS §35: +0.0319 at z 2.61 at 900
iterations x 2 worlds, mean simulation depth 3.76 turns), stranded on poke_engine;
`rl/search/native.py` is R7's ONE-PLY operator on this engine. This module is the
tree on this engine, built so that its depth-1 reduction IS `native.solve`
(gate i-a): depth becomes the only difference.

NODE MECHANICS (pinned by review 1; a tree that skips any of them never gets deep):
  * Actions for BOTH seats come from the engine's `mask()`. Our rows are every legal
    action; the foe's columns are the top `cols_k` by its prior (`native.solve`'s
    rule: stable, ties to the lower index).
  * CHANCE: each (row, col) edge owns `chance_k` REUSED children, child j seeded by
    the engine's `leaf_seed(node_seed, col, j)` -- never the row, so rows share
    chance draws at every depth (CRN). Visits go to the least-visited ACTIVE slot,
    the active count widening as ceil(pw_c * (n + 1) ** pw_alpha). Two slots whose
    positions are identical MERGE (the `save()` bytes with the RNG masked: the RNG
    is rewritten before every expansion), so a double switch costs one evaluation,
    not `chance_k`. A fresh child on every visit would cap the tree at depth 1.
  * PASS NODES (we owe a Pass while the foe replaces a fainted mon) are
    single-agent: the foe picks among its switch-ins by its prior. Under
    `pass_leaf="through"` (the default) they are never valued by our critic, which
    never trained on such a state (`native.solve` counts them as
    `search/pass_leaf_frac`). They add no LEVEL: `depth_cap` counts our decisions.
  * LEAVES: the critic on the acting seat's TRACKED view, rendered by the engine
    exactly as training renders it -- never tree.py's full reveal of a determinized
    foe team (the +0.0497 critic shift). Terminals are +1 / -1 / 0. The engine
    renders its own turn counter (tree.py fed turn+1 per transition: the L4 family).
  * ENGINE ERRORS abort that WORLD, counted by type; with no world left the prior's
    argmax is played, counted (`tree/fallback`). A fabricated value is never backed
    up (tree.py backed up 0.0).

THE ESTIMAND (`mode`), explicit:
  br_prior (default)  our PUCT over Qbar(a) = sum_b q(b) Qhat(a, b), with q the foe's
                      PRIOR over its top-k columns, renormalised over the columns row a
                      has visited. The foe's column is the one most under-visited
                      relative to q -- a deterministic stratification of the
                      expectation, not a sample. At depth cap 1 this is
                      `native.solve`'s estimand.
  legacy              tree.py's decoupled rule: both seats PUCT over their own marginal
                      statistics, the foe MINIMISING (`opp_rule="puct"`) or sampled
                      from its prior ("sample"). Kept for parity (Step B's
                      reproduction rung).
  sm_rm               regret matching for both seats at every node (SM-MCTS-RM). The
                      decoupled rule does not converge in simultaneous-move games
                      (Shafiei, via Lisy et al. 2013); this is the fallback estimand.

THE ROOT. `root_grid` first expands the whole one-ply matrix: every row x the top-k
columns x `chance_k` children, in one engine call and one critic batch. That is
`native.solve`'s own expansion, bit for bit; the remaining simulations deepen it.
The decision rule (`root_rule`):
  soft_br        `native.solve`'s P4 rule at `tau`.
  gumbel_mctx    completed Q (v_mix) with a visit-scaled sigma,
                 (c_visit + max N) * c_scale * q_hat, q_hat min-max over the rows
                 (Danihelka et al. 2022; mctx's defaults are 50 and 0.1).
  legacy_gumbel  tree.py's softmax(log prior + beta * q_norm).
  visits
  rm_average     sm_rm's average strategy.
There is no margin gate: gating is the caller's (the L-op's `margin_gate`, the
matched-override readouts).

UNITS. `sims` is TOTAL simulations over all worlds (iterations x worlds; §35 =
1,800). The grid's cells count as simulations. The work unit is `search/leaves`
(critic evaluations). Depth is logged in levels, engine updates and battle turns.

BATCHING. Trees run in LOCKSTEP over worlds, each round advancing `batch` descents
per tree under a virtual loss. Every leaf value and prior a round needs goes
through ONE `value_fn` call and ONE `prior_fn` call. Below the grid, `value_fn`
receives `{"obs": (n, OBS_DIM)}` only: a critic that reads more fails loudly.

Dials are the signature (`DIALS`), coerced by annotation (`dials_from`); an
unknown key is a hard failure (the typed-list landmine). The counters --
`search/*` where `native.solve` has the same quantity, `tree/*` otherwise -- are
returned for the caller to write to disk.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import time
import typing
from typing import Any, Callable, Sequence

import numpy as np

from rl.search.native import N_ACTIONS, World, seed_base

MODES = ("br_prior", "legacy", "sm_rm")
ROOT_RULES = ("gumbel_mctx", "soft_br", "legacy_gumbel", "visits", "rm_average")
PASS_LEAF = ("through", "critic")
OPP_RULES = ("puct", "sample")
Q_INITS = ("parent_v", "zero")
DEPTH_HIST = 24

# `SearchNode.save()`: a format byte, the 384 battle bytes (the RNG at 376..384,
# `engine/pkmn_gen1/src/layout.rs::B_RNG`), the result byte, the projection.
_RNG_LO, _RNG_HI = 1 + 376, 1 + 384
_M64 = (1 << 64) - 1

PriorFn = Callable[[np.ndarray, np.ndarray], np.ndarray]
"""(obs (n, OBS_DIM) float32, mask (n, 10) bool) -> probabilities (n, 10), zero off
the mask: the committee's `probs` (EnsembleAgent's rule)."""
ValueFn = Callable[[dict], np.ndarray]


class EngineError(RuntimeError):
    """An engine call failed inside one world's tree; that world is dropped."""


def _mix(x: int) -> int:
    x &= _M64
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & _M64
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & _M64
    return x ^ (x >> 31)


def child_seed(parent: int, col: int, slot: int) -> int:
    """A child's own seed, keyed like the engine's `leaf_seed` on the foe's column
    and the chance slot and NEVER on our row: siblings share chance draws below
    them too (CRN at every depth)."""
    key = ((int(col) + 2) << 32) | (int(slot) + 1)
    return _mix(int(parent) ^ _mix(key) ^ 0x6A09E667F3BCC909) & 0x7FFFFFFFFFFFFFFF


def position_digest(saved: bytes) -> bytes:
    """The merge key: a node's `save()` bytes with the RNG masked out."""
    b = bytes(saved)
    return hashlib.blake2b(b[:_RNG_LO] + b[_RNG_HI:], digest_size=16).digest()


def _eng(fn: Callable, *args, **kw):
    """One engine call; any failure out of it (a pyo3 PanicException is a
    BaseException) becomes an EngineError, which drops that world only."""
    try:
        return fn(*args, **kw)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as err:
        raise EngineError(f"{type(err).__name__}: {err}") from err


class _Batch:
    """One engine expansion's children (a `LeafBatch`), with each seat's rendered
    views fetched once, on demand, for the whole batch."""

    __slots__ = ("lb", "done", "out", "turns", "pend", "open")

    def __init__(self, lb: Any, us: str, n_open: int):
        self.lb = lb
        self.done = np.asarray(_eng(lb.done), dtype=bool)
        self.out = np.asarray(_eng(lb.outcome, us), dtype=np.int64)
        self.turns = np.asarray(_eng(lb.turns), dtype=np.int64)
        self.pend: dict[str, tuple] = {}
        self.open = n_open          # slots not yet materialised; the views are dropped at 0

    def pending(self, tables: Any, seat: str) -> tuple[dict, np.ndarray, np.ndarray]:
        p = self.pend.get(seat)
        if p is None:
            idx, obs, mask = _eng(self.lb.pending, tables, seat)
            p = ({int(i): k for k, i in enumerate(np.asarray(idx).tolist())},
                 np.asarray(obs), np.asarray(mask, dtype=bool))
            self.pend[seat] = p
        return p


class _Edge:
    __slots__ = ("batch", "key", "kids", "n", "vl", "base")

    def __init__(self, batch: _Batch, key: int, k: int, base: int = 0):
        self.batch = batch
        self.key = key                  # the column the chance seed is keyed on (-1: a Pass)
        self.kids: list = [None] * k
        self.n = [0.0] * k              # completed visits per slot
        self.vl = [0.0] * k             # pending (virtual) visits per slot
        self.base = base                # this edge's first leaf in `batch` (the grid shares one)


class _Node:
    __slots__ = ("sn", "batch", "li", "seed", "level", "upd", "turn", "term", "us_dec", "foe_dec",
                 "obs_us", "mask_us", "obs_foe", "mask_foe", "v0", "ready", "rows", "cols", "p", "q",
                 "topk_mass", "N", "W", "VL", "n", "w", "edges", "digest",
                 "rm_us", "rm_foe", "sm_us", "sm_foe")

    def __init__(self) -> None:
        self.sn = None
        self.batch = None
        self.li = 0
        self.seed = 0
        self.level = 0
        self.upd = 0
        self.turn = 0
        self.term: float | None = None
        self.us_dec = False
        self.foe_dec = False
        self.obs_us = self.mask_us = self.obs_foe = self.mask_foe = None
        self.v0: float | None = None
        self.ready = False
        self.rows: list[int] = []
        self.cols: list[int] = []
        self.p = self.q = None
        self.topk_mass = 1.0
        self.N = self.W = self.VL = None
        self.n = 0.0                    # completed simulations THROUGH this node
        self.w = 0.0
        self.edges: dict = {}
        self.digest: bytes | None = None
        self.rm_us = self.rm_foe = self.sm_us = self.sm_foe = None


class _Descent:
    __slots__ = ("path", "node", "need")

    def __init__(self, node: _Node, path: list | None = None):
        self.path: list = path or []
        self.node = node
        self.need: str | None = None


class _Tree:
    __slots__ = ("w", "weight", "root", "budget", "done", "active", "rng", "error", "grid_sims")

    def __init__(self, w: int, weight: float, root: _Node, budget: int, rng: np.random.Generator):
        self.w = w
        self.weight = weight
        self.root = root
        self.budget = budget
        self.done = 0
        self.active: list[_Descent] = []
        self.rng = rng
        self.error: str | None = None
        self.grid_sims = 0


def search(
    worlds: Sequence[World],
    tables: Any,
    seat: str,
    prior: np.ndarray,
    opp_prior: np.ndarray | None,
    value_fn: ValueFn,
    prior_fn: PriorFn,
    decision_key: int,
    *,
    sims: int = 1800,
    mode: str = "br_prior",
    root_rule: str = "gumbel_mctx",
    root_grid: bool = True,
    depth_cap: int = 8,
    cols_k: int = 4,
    chance_k: int = 2,
    pw_c: float = 1.0,
    pw_alpha: float = 1.0,
    merge: bool = True,
    pass_leaf: str = "through",
    c_puct: float = 1.5,
    q_init: str = "parent_v",
    opp_rule: str = "puct",
    tau: float = 0.05,
    beta: float = 4.0,
    c_visit: float = 50.0,
    c_scale: float = 0.1,
    rm_gamma: float = 0.1,
    batch: int = 1,
    virtual_loss: float = 1.0,
    both_views: bool = False,
    deadline_ms: float = 0.0,
    _inspect: Callable | None = None,
) -> dict[str, Any]:
    """The tree. Inputs are `native.solve`'s (`prior` / `opp_prior` are (10,)
    probabilities over OUR and the FOE's actions, masked to the engine's legal
    actions), plus `prior_fn` for every node below the root. `opp_prior` may be
    (10,) (every world), (len(worlds), 10), or None (the foe's prior is
    `prior_fn` on each world's foe view).

    Returns `pi` (10,) the improved policy, `q_row` (10,) the root's Q per action
    (NaN off the mask; NaN on a row no simulation reached), `n_row` (10,) the root's
    visits pooled over worlds, `v`, `v_prior`, `action`, `policy_action`, `rows`, `root`
    (each world's joint matrix: cols, q, N, W), `counters`, `per_world`.

    `_inspect` is not a dial: a diagnostic hook called with each world's finished
    tree (`_Tree`, root node at `.root`) before the decision (the fixtures walk it).
    """
    s = _Search(tables, seat, value_fn, prior_fn, locals())
    return s.run(worlds, prior, opp_prior, decision_key, _inspect)


class _Search:
    def __init__(self, tables: Any, seat: str, value_fn: ValueFn, prior_fn: PriorFn, dials: dict):
        for k in DIALS:
            setattr(self, k, dials[k])
        _check(self)
        self.tables = tables
        self.us = str(seat)
        self.foe = "p2" if self.us == "p1" else "p1"
        self.value_fn = value_fn
        self.prior_fn = prior_fn
        z = 0.0
        self.c = {k: z for k in ("evals", "evals_grid", "pass_evals", "prior_rows", "forwards_v", "forwards_p",
                                 "nodes", "edges", "merges", "pass_nodes", "terminal_sims", "capped_sims",
                                 "dup_waits", "sims", "depth_sum", "depth_max", "upd_sum", "upd_max",
                                 "turn_sum", "turn_max")}
        self.hist = [0] * DEPTH_HIST
        self.t_engine = self.t_value = self.t_prior = 0.0
        self.errors: dict[str, int] = {}

    # ---- nodes ------------------------------------------------------------------

    def _install(self, x: _Node, p_us: np.ndarray | None, p_foe: np.ndarray | None) -> None:
        """Priors -> rows, columns and statistics. The column rule is
        `native.solve`'s, expression for expression (the depth-1 reduction)."""
        if x.us_dec:
            rows = np.flatnonzero(x.mask_us)
            p = np.asarray(p_us, dtype=np.float64)[rows]
            tot = p.sum()
            x.rows = rows.tolist()
            x.p = p / tot if tot > 0 else np.full(len(rows), 1.0 / len(rows))
        else:
            x.rows, x.p = [-1], np.ones(1)
        if x.foe_dec:
            pf = np.asarray(p_foe, dtype=np.float64)
            legal = np.flatnonzero(x.mask_foe)
            order = legal[np.argsort(-pf[legal], kind="stable")]
            cols = order[: min(self.cols_k, len(order))]
            tot = pf[cols].sum()
            x.cols = cols.tolist()
            x.q = pf[cols] / tot if tot > 0 else np.full(len(cols), 1.0 / len(cols))
            lt = pf[legal].sum()
            x.topk_mass = float(tot / lt) if lt > 0 else 1.0
        else:
            x.cols, x.q, x.topk_mass = [-1], np.ones(1), 1.0
        nr, nc = len(x.rows), len(x.cols)
        x.N = np.zeros((nr, nc))
        x.W = np.zeros((nr, nc))
        x.VL = np.zeros((nr, nc))
        if self.mode == "sm_rm":
            x.rm_us, x.sm_us = np.zeros(nr), np.zeros(nr)
            x.rm_foe, x.sm_foe = np.zeros(nc), np.zeros(nc)
        x.ready = True
        x.obs_us = x.obs_foe = None
        if not x.us_dec:
            self.c["pass_nodes"] += 1

    def _child(self, parent: _Node, batch: _Batch, i: int, seed: int) -> _Node:
        nd = _Node()
        nd.batch, nd.li, nd.seed = batch, i, seed
        nd.level = parent.level + (1 if parent.us_dec else 0)
        nd.upd = parent.upd + 1
        nd.turn = int(batch.turns[i])
        if batch.done[i]:
            o = int(batch.out[i])
            nd.term = 0.0 if o == 2 else float(o)
            return nd
        t0 = time.perf_counter()
        pos, obs, mask = batch.pending(self.tables, self.us)
        k = pos.get(i)
        if k is not None:
            nd.us_dec, nd.obs_us, nd.mask_us = True, obs[k].copy(), mask[k].copy()
        pos2, obs2, mask2 = batch.pending(self.tables, self.foe)
        k2 = pos2.get(i)
        if k2 is not None:
            nd.foe_dec, nd.obs_foe, nd.mask_foe = True, obs2[k2].copy(), mask2[k2].copy()
        self.t_engine += time.perf_counter() - t0
        if not (nd.us_dec or nd.foe_dec):
            raise EngineError(f"leaf {i}: live, but neither seat owes a decision")
        return nd

    def _merge(self, e: _Edge, j: int, kid: _Node) -> _Node:
        """Slot j's canonical child: an identical position already under this edge
        (RNG masked) if there is one."""
        if kid.term is None and self.merge and len(e.kids) > 1:
            t0 = time.perf_counter()
            kid.sn = _eng(e.batch.lb.node, kid.li)
            kid.digest = position_digest(_eng(kid.sn.save))
            self.t_engine += time.perf_counter() - t0
            for other in e.kids:
                if other is not None and other.digest == kid.digest:
                    self.c["merges"] += 1
                    e.kids[j] = other
                    return other
        self.c["nodes"] += 1
        e.kids[j] = kid
        return kid

    def _edge(self, x: _Node, ri: int, ci: int) -> _Edge:
        k = self.chance_k
        if x.sn is None:
            x.sn = _eng(x.batch.lb.node, x.li)
        if x.us_dec:
            key = int(x.cols[ci])
            acting, cells = self.us, [(int(x.rows[ri]), key, k)]
        else:
            key = -1
            acting, cells = self.foe, [(int(x.cols[ci]), -1, k)]
        t0 = time.perf_counter()
        b = _Batch(_eng(x.sn.leaves, self.tables, acting, cells, x.seed), self.us, k)
        self.t_engine += time.perf_counter() - t0
        e = _Edge(b, key, k)
        x.edges[(ri, ci)] = e
        self.c["edges"] += 1
        return e

    def _kid(self, x: _Node, e: _Edge, j: int) -> _Node:
        kid = e.kids[j]
        if kid is None:
            kid = self._merge(e, j, self._child(x, e.batch, e.base + j, child_seed(x.seed, e.key, j)))
            e.batch.open -= 1
            if e.batch.open <= 0:
                e.batch.pend = {}
        return kid

    def _value(self, x: _Node) -> float:
        """A node's value estimate: its own evaluation and every simulation below it."""
        if x.v0 is not None:
            return (x.v0 + x.w) / (1.0 + x.n)
        return x.w / x.n if x.n > 0 else 0.0

    # ---- selection ----------------------------------------------------------------

    def _select(self, t: _Tree, x: _Node) -> tuple[int, int, Any]:
        nr, nc = x.N.shape
        if self.mode == "sm_rm":
            su = _rm_strategy(x.rm_us, self.rm_gamma)
            sf = _rm_strategy(x.rm_foe, self.rm_gamma)
            ri = int(t.rng.choice(nr, p=su)) if nr > 1 else 0
            ci = int(t.rng.choice(nc, p=sf)) if nc > 1 else 0
            return ri, ci, (su, sf)
        q0 = self._value(x) if self.q_init == "parent_v" else 0.0
        N = x.N + x.VL
        total = math.sqrt(float(N.sum()) + 1.0)
        if nr == 1:
            ri = 0
        else:
            if self.mode == "legacy":
                Na = N.sum(axis=1)
                Wa = x.W.sum(axis=1) - self.virtual_loss * x.VL.sum(axis=1)
                Q = np.where(Na > 0, Wa / np.where(Na > 0, Na, 1.0), q0)
            else:
                vis = N > 0
                Qab = (x.W - self.virtual_loss * x.VL) / np.where(vis, N, 1.0)
                qw = x.q * vis
                den = qw.sum(axis=1)
                Q = np.where(den > 0, (qw * Qab).sum(axis=1) / np.where(den > 0, den, 1.0), q0)
                Na = N.sum(axis=1)
            ri = int(np.argmax(Q + self.c_puct * x.p * total / (1.0 + Na)))
        if nc == 1:
            ci = 0
        elif self.mode == "br_prior":
            Nr = N[ri]
            ci = int(np.argmax(x.q - Nr / (1.0 + Nr.sum())))
        elif self.opp_rule == "sample":
            ci = int(t.rng.choice(nc, p=x.q))
        else:
            Nb = N.sum(axis=0)
            Wb = x.W.sum(axis=0) + self.virtual_loss * x.VL.sum(axis=0)
            Qb = np.where(Nb > 0, -Wb / np.where(Nb > 0, Nb, 1.0), -q0)
            ci = int(np.argmax(Qb + self.c_puct * x.q * total / (1.0 + Nb)))
        return ri, ci, None

    def _slot(self, e: _Edge) -> int:
        k = len(e.kids)
        if k == 1:
            return 0
        n_e = sum(e.n) + sum(e.vl)
        act = min(k, max(1, math.ceil(self.pw_c * (n_e + 1.0) ** self.pw_alpha)))
        best, bj = math.inf, 0
        for j in range(act):
            c = e.n[j] + e.vl[j]
            if c < best:
                best, bj = c, j
        return bj

    # ---- one descent ----------------------------------------------------------------

    def _advance(self, t: _Tree, d: _Descent) -> float | None:
        """Walk down until the simulation has a value (returned) or needs the
        network (`d.need` set, None returned)."""
        while True:
            x = d.node
            if x.term is not None:
                self.c["terminal_sims"] += 1
                return x.term
            through = (not x.us_dec) and self.pass_leaf == "through"
            if not x.ready:
                if not through and x.v0 is None:
                    d.need = "eval"
                    return None
                if not through and x.level >= self.depth_cap:
                    self.c["capped_sims"] += 1
                    return self._value(x)
                d.need = "prior"
                return None
            if not through and x.level >= self.depth_cap:
                self.c["capped_sims"] += 1
                return self._value(x)
            ri, ci, extra = self._select(t, x)
            e = x.edges.get((ri, ci)) or self._edge(x, ri, ci)
            j = self._slot(e)
            kid = self._kid(x, e, j)
            x.VL[ri, ci] += 1.0
            e.vl[j] += 1.0
            d.path.append((x, ri, ci, j, extra))
            d.node = kid

    def _backup(self, t: _Tree, d: _Descent, v: float) -> None:
        for x, ri, ci, j, extra in d.path:
            e = x.edges[(ri, ci)]
            x.VL[ri, ci] -= 1.0
            e.vl[j] -= 1.0
            x.N[ri, ci] += 1.0
            x.W[ri, ci] += v
            e.n[j] += 1.0
            x.n += 1.0
            x.w += v
            if extra is not None:
                su, sf = extra
                nr, nc = x.N.shape
                if nr > 1:
                    xt = np.zeros(nr)
                    xt[ri] = v / su[ri]
                    x.rm_us += xt - v
                    x.sm_us += su
                if nc > 1:
                    xt = np.zeros(nc)
                    xt[ci] = -v / sf[ci]
                    x.rm_foe += xt + v
                    x.sm_foe += sf
        t.done += 1
        self._depth(t, d.node)

    def _depth(self, t: _Tree, leaf: _Node) -> None:
        c = self.c
        c["sims"] += 1
        c["depth_sum"] += leaf.level
        c["depth_max"] = max(c["depth_max"], leaf.level)
        c["upd_sum"] += leaf.upd
        c["upd_max"] = max(c["upd_max"], leaf.upd)
        dt = leaf.turn - t.root.turn
        c["turn_sum"] += dt
        c["turn_max"] = max(c["turn_max"], dt)
        self.hist[min(leaf.level, DEPTH_HIST - 1)] += 1

    # ---- the network ----------------------------------------------------------------

    def _forward(self, eval_nodes: list[_Node], prior_nodes: list[_Node]) -> None:
        """ONE value_fn call for every new leaf, ONE prior_fn call for every node that
        needs priors (a new leaf below the cap, a grid child, a Pass node)."""
        if eval_nodes:
            obs = []
            for x in eval_nodes:
                if x.us_dec:
                    obs.append(x.obs_us)
                else:   # a Pass state, valued by the critic (pass_leaf="critic")
                    if x.sn is None:
                        x.sn = _eng(x.batch.lb.node, x.li)
                    obs.append(np.asarray(_eng(x.sn.obs, self.tables, self.us), dtype=np.float32))
                    self.c["pass_evals"] += 1
            t0 = time.perf_counter()
            v = np.asarray(self.value_fn({"obs": np.stack(obs)}), dtype=np.float64).reshape(len(obs))
            self.t_value += time.perf_counter() - t0
            self.c["evals"] += len(obs)
            self.c["forwards_v"] += 1
            for x, val in zip(eval_nodes, v.tolist()):
                x.v0 = float(val)
        need = [x for x in eval_nodes if x.level < self.depth_cap] + prior_nodes
        o, m, own = [], [], []
        for x in need:
            if x.us_dec:
                o.append(x.obs_us)
                m.append(x.mask_us)
                own.append((x, 0))
            if x.foe_dec:
                o.append(x.obs_foe)
                m.append(x.mask_foe)
                own.append((x, 1))
        probs = None
        if o:
            t0 = time.perf_counter()
            probs = np.asarray(self.prior_fn(np.stack(o), np.stack(m)), dtype=np.float64)
            self.t_prior += time.perf_counter() - t0
            self.c["prior_rows"] += len(o)
            self.c["forwards_p"] += 1
        got: dict[int, list] = {}
        for k, (x, side) in enumerate(own):
            got.setdefault(id(x), [x, None, None])[1 + side] = probs[k]
        for x in need:
            if not x.ready:
                g = got.get(id(x), [x, None, None])
                self._install(x, g[1], g[2])

    # ---- the grid ---------------------------------------------------------------------

    def _grid(self, t: _Tree) -> None:
        """The whole one-ply matrix, as `native.solve` builds it: the same cells, the
        same seed, the same render, ONE critic batch, terminals overwritten, cell sums
        accumulated in (cell, sample) order. Pass leaves under `through` get no critic
        value; their first simulation descends through them."""
        x = t.root
        k = self.chance_k
        cells = [(int(a), int(b), k) for a in x.rows for b in x.cols]
        t0 = time.perf_counter()
        e = _eng(x.sn.expand, self.tables, self.us, cells, x.seed, both_views=self.both_views)
        batch = _Batch(_eng(x.sn.leaves, self.tables, self.us, cells, x.seed), self.us, len(cells) * k)
        self.t_engine += time.perf_counter() - t0
        n = int(e["n"])
        t1 = time.perf_counter()
        v = np.asarray(self.value_fn(e), dtype=np.float64).reshape(n)
        self.t_value += time.perf_counter() - t1
        term = np.asarray(e["terminal"])
        live = term == 0
        v = np.where(live, v, np.where(term == 2, 0.0, term.astype(np.float64)))
        self.c["evals"] += n
        self.c["evals_grid"] += n
        self.c["forwards_v"] += 1
        if self.pass_leaf == "critic":   # under "through" their values are never used
            self.c["pass_evals"] += int((np.asarray(e["req_next"])[:, 0] == 0)[live].sum())
        nc = len(x.cols)
        for c, (_a, b, _k) in enumerate(cells):
            ri, ci = divmod(c, nc)
            edge = _Edge(batch, b, k, base=c * k)
            x.edges[(ri, ci)] = edge
            self.c["edges"] += 1
            for j in range(k):
                i = c * k + j
                kid = self._kid(x, edge, j)
                if kid.term is None and not kid.us_dec and self.pass_leaf == "through":
                    # the value comes from below: a simulation that starts here
                    x.VL[ri, ci] += 1.0
                    edge.vl[j] += 1.0
                    t.active.append(_Descent(kid, [(x, ri, ci, j, None)]))
                    continue
                val = float(v[i])
                if kid.term is None and kid.v0 is None:
                    kid.v0 = val
                elif kid.term is not None:
                    self.c["terminal_sims"] += 1
                x.N[ri, ci] += 1.0
                x.W[ri, ci] += val
                edge.n[j] += 1.0
                x.n += 1.0
                x.w += val
                t.done += 1
                t.grid_sims += 1
                self._depth(t, kid)
        t.budget = max(t.budget, len(cells) * k)

    # ---- the loop ---------------------------------------------------------------------

    def _fail(self, t: _Tree, err: BaseException) -> None:
        t.error = type(err).__name__
        key = f"{type(err.__cause__).__name__ if err.__cause__ else type(err).__name__}"
        self.errors[key] = self.errors.get(key, 0) + 1
        t.active = []

    def run(self, worlds: Sequence[World], prior: np.ndarray, opp_prior: np.ndarray | None,
            decision_key: int, inspect_fn: Callable | None = None) -> dict[str, Any]:
        t_start = time.perf_counter()
        if not worlds:
            raise ValueError("search() needs at least one world")
        prior = np.asarray(prior, dtype=np.float64).reshape(N_ACTIONS)
        root0 = worlds[0].node
        if root0.over():
            raise ValueError("search() on a finished battle")
        mask = np.asarray(root0.mask(self.tables, self.us), dtype=bool)
        if not mask.any():
            raise ValueError(f"{self.us} owes no decision at this root")
        if (prior[~mask] != 0).any() or not (prior[mask] > 0).any():
            raise ValueError("prior must be masked to the engine's legal actions (and not all zero on them)")
        rows = np.flatnonzero(mask).tolist()
        prior_m = prior[mask] / prior[mask].sum()
        policy_action = int(rows[int(np.argmax(prior_m))])
        opp = None if opp_prior is None else np.asarray(opp_prior, dtype=np.float64)
        if opp is not None and opp.ndim == 1:
            opp = np.broadcast_to(opp.reshape(1, N_ACTIONS), (len(worlds), N_ACTIONS))
        if opp is not None and opp.shape != (len(worlds), N_ACTIONS):
            raise ValueError(f"opp_prior has shape {opp.shape}; want (10,) or ({len(worlds)}, 10)")

        # ---- roots
        trees: list[_Tree] = []
        per = [self.sims // len(worlds) + (1 if i < self.sims % len(worlds) else 0) for i in range(len(worlds))]
        need_opp = []
        for w_i, world in enumerate(worlds):
            sn = world.node
            wm = np.asarray(sn.mask(self.tables, self.us), dtype=bool)
            if not np.array_equal(wm, mask):
                raise ValueError(f"world {w_i}: the acting seat's mask differs from world 0's -- "
                                 "a resampled world must keep our own side")
            r = _Node()
            r.sn, r.seed, r.turn = sn, seed_base(decision_key, w_i), int(sn.turn())
            r.us_dec, r.mask_us = True, mask
            fm = np.asarray(sn.mask(self.tables, self.foe), dtype=bool)
            r.foe_dec, r.mask_foe = bool(fm.any()), fm
            rng = np.random.default_rng([int(decision_key) & 0x7FFFFFFFFFFFFFFF, w_i])
            trees.append(_Tree(w_i, float(world.weight), r, per[w_i], rng))
            if r.foe_dec:
                if opp is None:
                    r.obs_foe = np.asarray(sn.obs(self.tables, self.foe), dtype=np.float32)
                    need_opp.append(r)
                else:
                    po = opp[w_i]
                    if (po[~fm] != 0).any() or not (po[fm] > 0).any():
                        raise ValueError(f"world {w_i}: opp_prior must be masked to the foe's legal actions")
        if need_opp:
            t0 = time.perf_counter()
            pr = self.prior_fn(np.stack([r.obs_foe for r in need_opp]), np.stack([r.mask_foe for r in need_opp]))
            self.t_prior += time.perf_counter() - t0
            self.c["prior_rows"] += len(need_opp)
            self.c["forwards_p"] += 1
            got = {id(r): np.asarray(pr[i], dtype=np.float64) for i, r in enumerate(need_opp)}
        for t in trees:
            r = t.root
            p_foe = None
            if r.foe_dec:
                p_foe = got[id(r)] if opp is None else opp[t.w]
            self._install(r, prior, p_foe)
        if not self.root_grid:
            # the root's own value: q_init and v_mix need it (tree.py evaluates the root too)
            obs = np.stack([np.asarray(t.root.sn.obs(self.tables, self.us), dtype=np.float32) for t in trees])
            t0 = time.perf_counter()
            v = np.asarray(self.value_fn({"obs": obs}), dtype=np.float64).reshape(len(trees))
            self.t_value += time.perf_counter() - t0
            self.c["evals"] += len(trees)
            self.c["forwards_v"] += 1
            for t, val in zip(trees, v.tolist()):
                t.root.v0 = float(val)
        else:
            for t in trees:
                try:
                    self._grid(t)
                except EngineError as err:
                    self._fail(t, err)

        # ---- simulations, in lockstep over worlds
        deadline = t_start + self.deadline_ms / 1e3 if self.deadline_ms > 0 else math.inf
        while True:
            stop_spawn = time.perf_counter() > deadline
            waits_e: dict[int, _Node] = {}
            waits_p: dict[int, _Node] = {}
            finished: list[tuple[_Tree, _Descent, float]] = []
            live_trees = 0
            for t in trees:
                if t.error:
                    continue
                if not stop_spawn:
                    while len(t.active) < self.batch and t.done + len(t.active) < t.budget:
                        t.active.append(_Descent(t.root))
                if not t.active:
                    continue
                live_trees += 1
                keep = []
                try:
                    for d in t.active:
                        d.need = None
                        val = self._advance(t, d)
                        if val is not None:
                            finished.append((t, d, val))
                        else:
                            bucket = waits_e if d.need == "eval" else waits_p
                            if id(d.node) in bucket:
                                self.c["dup_waits"] += 1
                            bucket[id(d.node)] = d.node
                            keep.append(d)
                except EngineError as err:
                    self._fail(t, err)
                    finished = [f for f in finished if f[0] is not t]
                    continue
                t.active = keep
            for t, d, val in finished:
                self._backup(t, d, val)
            if waits_e or waits_p:
                self._forward(list(waits_e.values()), [x for k, x in waits_p.items() if k not in waits_e])
                for t in trees:
                    if t.error:
                        continue
                    keep = []
                    for d in t.active:
                        if d.need == "eval":
                            self._backup(t, d, float(d.node.v0))
                        else:
                            keep.append(d)
                    t.active = keep
            if live_trees == 0 and not finished and not (waits_e or waits_p):
                break
        if inspect_fn is not None:
            for t in trees:
                inspect_fn(t)
        return self._decide(trees, rows, mask, prior_m, policy_action, t_start)

    # ---- the decision -----------------------------------------------------------------

    def _decide(self, trees: list[_Tree], rows: list[int], mask: np.ndarray, prior_m: np.ndarray,
                policy_action: int, t_start: float) -> dict[str, Any]:
        ok = [t for t in trees if not t.error]
        nr = len(rows)
        counters = self._counters(trees, ok)
        if not ok:
            counters.update({"tree/fallback": 1.0, "search/override": 0.0, "search/kl_prior": 0.0,
                             "search/margin": 0.0, "search/pi_top1": float(prior_m.max()),
                             "search/prior_top1": float(prior_m.max()), "search/v": float("nan"),
                             "search/v_prior": float("nan"), "tree/argmax_moved": 0.0, "tree/world_agree": float("nan")})
            counters["search/ms"] = (time.perf_counter() - t_start) * 1e3
            pi = np.zeros(N_ACTIONS)
            pi[mask] = prior_m
            return {"pi": pi, "q_row": np.full(N_ACTIONS, np.nan), "n_row": np.zeros(N_ACTIONS),
                    "v": float("nan"), "v_prior": float("nan"),
                    "action": policy_action, "policy_action": policy_action, "rows": rows, "root": [],
                    "counters": counters, "per_world": []}
        # per-world root estimates over OUR rows (the same rows in every world)
        per_q, per_n, per_marg, per_w = [], [], [], []
        for t in ok:
            r = t.root
            N, W = r.N, r.W
            vis = N > 0
            qhat = np.where(vis, W / np.where(vis, N, 1.0), 0.0)
            qbar = qhat @ r.q                     # `native.solve`'s arithmetic when every cell is visited
            full = vis.all(axis=1)
            if not full.all():
                qw = r.q * vis
                den = qw.sum(axis=1)
                part = np.where(den > 0, (qw * qhat).sum(axis=1) / np.where(den > 0, den, 1.0), np.nan)
                qbar = np.where(full, qbar, part)
            na = N.sum(axis=1)
            per_q.append(qbar)
            per_n.append(na)
            per_marg.append((W.sum(axis=1), na))
            per_w.append(t.weight)
        n_pool = np.sum(per_n, axis=0)
        if self.mode == "br_prior":
            if len(ok) == 1:
                q_root = per_q[0]
            else:
                qs = np.array(per_q)
                ws = np.array(per_w)[:, None] * np.isfinite(qs)
                den = ws.sum(axis=0)
                q_root = np.where(den > 0, (ws * np.nan_to_num(qs)).sum(axis=0) / np.where(den > 0, den, 1.0), np.nan)
        else:
            wsum = np.sum([m[0] for m in per_marg], axis=0)
            q_root = np.where(n_pool > 0, wsum / np.where(n_pool > 0, n_pool, 1.0), np.nan)
        vis = np.isfinite(q_root)
        v_root = float(np.mean([t.root.v0 if t.root.v0 is not None else self._value(t.root) for t in ok]))
        if vis.any():
            sum_n = float(n_pool[vis].sum())
            wq = float((prior_m[vis] * q_root[vis]).sum() / prior_m[vis].sum())
            v_mix = (v_root + sum_n * wq) / (1.0 + sum_n)
        else:
            v_mix = v_root
        q_done = np.where(vis, q_root, v_mix)      # completed Q (mctx): an unvisited row takes v_mix
        rule = self.root_rule
        if rule == "soft_br":
            logits = np.log(prior_m) + q_done / self.tau
            pi_m = np.exp(logits - logits.max())
            pi_m /= pi_m.sum()
        elif rule == "gumbel_mctx":
            lo, hi = q_done.min(), q_done.max()
            q_hat = (q_done - lo) / max(hi - lo, 1e-8)
            logits = np.log(prior_m) + (self.c_visit + float(n_pool.max())) * self.c_scale * q_hat
            pi_m = np.exp(logits - logits.max())
            pi_m /= pi_m.sum()
        elif rule == "legacy_gumbel":
            if vis.any():
                lo, hi = q_root[vis].min(), q_root[vis].max()
                qn = np.where(vis, (np.nan_to_num(q_root) - lo) / max(hi - lo, 1e-6), 0.0)
            else:
                qn = np.zeros(nr)
            z = np.log(prior_m) + self.beta * qn
            pi_m = np.exp(z - z.max())
            pi_m /= pi_m.sum()
        elif rule == "visits":
            pi_m = n_pool / n_pool.sum() if n_pool.sum() > 0 else prior_m.copy()
        else:   # rm_average
            s = np.sum([t.root.sm_us for t in ok], axis=0)
            pi_m = s / s.sum() if s.sum() > 0 else prior_m.copy()
        action = int(rows[int(np.argmax(pi_m))])
        ia = rows.index(action)
        ip = rows.index(policy_action)
        v_prime = float(pi_m @ q_done)
        v_prior = float(prior_m @ q_done)
        kl = float(np.sum(np.where(pi_m > 0, pi_m * (np.log(np.maximum(pi_m, 1e-300)) - np.log(prior_m)), 0.0)))
        # FUSION at the root: does each world's own best row agree with the pooled one?
        best = int(np.argmax(np.where(vis, q_root, -np.inf)))
        own = per_q if self.mode == "br_prior" else [np.where(n > 0, m / np.where(n > 0, n, 1.0), np.nan)
                                                     for m, n in per_marg]
        agree = [int(np.isfinite(q).any() and int(np.argmax(np.where(np.isfinite(q), q, -np.inf))) == best)
                 for q in own]
        counters.update({
            "tree/fallback": 0.0,
            "search/override": float(action != policy_action),
            "search/kl_prior": kl,
            "search/margin": float(q_done[ia] - q_done[ip]),
            "search/pi_top1": float(pi_m.max()),
            "search/prior_top1": float(prior_m.max()),
            "search/v": v_prime,
            "search/v_prior": v_prior,
            "tree/argmax_moved": float(int(np.argmax(pi_m)) != int(np.argmax(prior_m))),
            "tree/world_agree": float(np.mean(agree)),
            "tree/root_visits_top1": float(n_pool.max() / max(n_pool.sum(), 1.0)),
            "tree/v_mix": float(v_mix),
        })
        counters["search/ms"] = (time.perf_counter() - t_start) * 1e3
        pi = np.zeros(N_ACTIONS)
        pi[mask] = pi_m
        q_row = np.full(N_ACTIONS, np.nan)
        q_row[mask] = q_root
        n_row = np.zeros(N_ACTIONS)
        n_row[mask] = n_pool
        root = [{"world": t.w, "rows": rows, "cols": [int(c) for c in t.root.cols], "q": t.root.q.tolist(),
                 "N": t.root.N.tolist(), "W": t.root.W.tolist()} for t in ok]
        return {"pi": pi, "q_row": q_row, "n_row": n_row, "v": v_prime, "v_prior": v_prior, "action": action,
                "policy_action": policy_action, "rows": rows, "root": root, "counters": counters,
                "per_world": [q.tolist() for q in per_q]}

    def _counters(self, trees: list[_Tree], ok: list[_Tree]) -> dict[str, float]:
        c = self.c
        sims = max(c["sims"], 1.0)
        evals = max(c["evals"], 1.0)
        r0 = (ok or trees)[0].root
        out = {
            "search/leaves": c["evals"],
            "search/rows": float(len(r0.rows)),
            "search/cols": float(len(r0.cols)) if r0.cols != [-1] else 1.0,
            "search/worlds": float(len(ok)),
            "search/rust_ms": self.t_engine * 1e3,
            "search/topk_mass": float(np.mean([t.root.topk_mass for t in ok])) if ok else 1.0,
            "search/terminal_frac": c["terminal_sims"] / sims,
            "search/pass_leaf_frac": c["pass_evals"] / evals,
            "tree/sims": c["sims"],
            "tree/sims_grid": float(sum(t.grid_sims for t in trees)),
            "tree/evals_grid": c["evals_grid"],
            "tree/prior_rows": c["prior_rows"],
            "tree/forwards_v": c["forwards_v"],
            "tree/forwards_p": c["forwards_p"],
            "tree/nodes": c["nodes"],
            "tree/edges": c["edges"],
            "tree/merges": c["merges"],
            "tree/pass_nodes": c["pass_nodes"],
            "tree/terminal_sims": c["terminal_sims"],
            "tree/capped_sims": c["capped_sims"],
            "tree/dup_waits": c["dup_waits"],
            "tree/depth_mean": c["depth_sum"] / sims,
            "tree/depth_max": c["depth_max"],
            "tree/upd_mean": c["upd_sum"] / sims,
            "tree/upd_max": c["upd_max"],
            "tree/turns_mean": c["turn_sum"] / sims,
            "tree/turns_max": c["turn_max"],
            "tree/errors": float(sum(self.errors.values())),
            "tree/worlds_failed": float(len(trees) - len(ok)),
            "tree/ms_value": self.t_value * 1e3,
            "tree/ms_prior": self.t_prior * 1e3,
        }
        for i, h in enumerate(self.hist):
            out[f"tree/depth_hist/{i}"] = float(h)
        for k, v in self.errors.items():
            out[f"tree/error/{k}"] = float(v)
        return out


def _rm_strategy(r: np.ndarray, gamma: float) -> np.ndarray:
    pos = np.maximum(r, 0.0)
    s = pos.sum()
    sig = pos / s if s > 0 else np.full(r.shape[0], 1.0 / r.shape[0])
    return (1.0 - gamma) * sig + gamma / r.shape[0]


def _check(s: _Search) -> None:
    if s.sims < 1:
        raise ValueError(f"sims must be >= 1, got {s.sims}")
    if s.mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {s.mode!r}")
    if s.root_rule not in ROOT_RULES:
        raise ValueError(f"root_rule must be one of {ROOT_RULES}, got {s.root_rule!r}")
    if s.root_rule == "rm_average" and s.mode != "sm_rm":
        raise ValueError("root_rule rm_average needs mode sm_rm")
    if s.pass_leaf not in PASS_LEAF:
        raise ValueError(f"pass_leaf must be one of {PASS_LEAF}, got {s.pass_leaf!r}")
    if s.opp_rule not in OPP_RULES:
        raise ValueError(f"opp_rule must be one of {OPP_RULES}, got {s.opp_rule!r}")
    if s.q_init not in Q_INITS:
        raise ValueError(f"q_init must be one of {Q_INITS}, got {s.q_init!r}")
    if s.depth_cap < 1 or s.cols_k < 1 or s.chance_k < 1 or s.batch < 1:
        raise ValueError("depth_cap, cols_k, chance_k and batch must all be >= 1")
    if not (s.tau > 0 and math.isfinite(s.tau)):
        raise ValueError(f"tau must be a positive finite float, got {s.tau!r}")
    if not (0.0 <= s.rm_gamma <= 1.0):
        raise ValueError(f"rm_gamma must be in [0, 1], got {s.rm_gamma}")
    if s.pw_c <= 0 or s.pw_alpha < 0:
        raise ValueError("pw_c must be > 0 and pw_alpha >= 0")


# ---------------------------------------------------------------------------
# The dial list, derived -- never typed.
# ---------------------------------------------------------------------------

_FIXED = ("worlds", "tables", "seat", "prior", "opp_prior", "value_fn", "prior_fn", "decision_key")
DIALS = tuple(p for p in inspect.signature(search).parameters if p not in _FIXED and not p.startswith("_"))
"""Every keyword `search` accepts beyond its per-call inputs, read off the signature."""


def dials_from(spec: dict | None) -> dict[str, Any]:
    """A config's `tree:` block -> `search`'s keyword dials. Unknown keys are a HARD
    FAILURE; values are coerced to the signature's annotated type."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(DIALS))
    if unknown:
        raise ValueError(f"unknown native-tree dial(s) {unknown}; the dials are {list(DIALS)}")
    hints = typing.get_type_hints(search)
    out: dict[str, Any] = {}
    for k, v in spec.items():
        ann = hints.get(k)
        if ann is bool:
            if not isinstance(v, bool):
                raise ValueError(f"dial {k} must be a bool, got {v!r}")
            out[k] = v
        elif ann is int:
            if isinstance(v, bool) or int(v) != float(v):
                raise ValueError(f"dial {k} must be an integer, got {v!r}")
            out[k] = int(v)
        elif ann is float:
            out[k] = float(v)
        else:
            out[k] = v
    return out

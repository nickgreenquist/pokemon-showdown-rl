//! Python surface for the batched leaf path (R7 B0; `search.rs`).
//!
//! `SearchNode` is a root; `expand` renders leaves as numpy arrays with the GIL
//! released for the whole engine/tracker/encoder loop; `leaves` returns a
//! `LeafBatch` the rollout instrument (the I-op, `scripts/rollout_q.py`) drives
//! to termination with the policy on both seats. The solver, the critic and the
//! CRN decision key all live in Python (`rl/search/native.py`).

use numpy::{PyArray1, PyArray2};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::battle::{Battle, Player};
use crate::encoder::{OBS_DIM, PRIV_DIM};
use crate::env::N_ACTIONS;
use crate::observe::{ObservableState, SeatState};
use crate::pyencode::{Tables, rows2};
use crate::python::{PyBattle, player, request, request_to_py};
use crate::search::{Cell, LeafBatch as RustLeafBatch, Node, Render};
use crate::track::{BattleTracker, RootReveal};

fn reveal_from_py(d: &Bound<'_, PyDict>) -> PyResult<RootReveal> {
    let mut r = RootReveal::default();
    if let Some(v) = d.get_item("reveal_order")? {
        r.reveal_order = v.extract()?;
    }
    if let Some(v) = d.get_item("revealed_moves")? {
        let m: Vec<Vec<u8>> = v.extract()?;
        for (i, x) in m.into_iter().take(6).enumerate() {
            r.revealed_moves[i] = x;
        }
    }
    if let Some(v) = d.get_item("move_uses")? {
        let m: Vec<Vec<u8>> = v.extract()?;
        for (i, x) in m.into_iter().take(6).enumerate() {
            r.move_uses[i] = x;
        }
    }
    if let Some(v) = d.get_item("sleep_observed")? {
        let s: Vec<u8> = v.extract()?;
        for (i, x) in s.into_iter().take(6).enumerate() {
            r.sleep_observed[i] = x;
        }
    }
    if let Some(v) = d.get_item("flags_before_faint")? {
        let f: Vec<Vec<bool>> = v.extract()?;
        for (i, x) in f.into_iter().take(6).enumerate() {
            r.flags_before_faint[i] = (x.first().copied().unwrap_or(false), x.get(1).copied().unwrap_or(false));
        }
    }
    if let Some(v) = d.get_item("binding_victim_turns")? {
        r.binding_victim_turns = v.extract()?;
    }
    Ok(r)
}

fn reveal_to_py<'py>(py: Python<'py>, r: &RootReveal) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("reveal_order", r.reveal_order.clone())?;
    d.set_item("revealed_moves", r.revealed_moves.iter().map(|v| v.clone()).collect::<Vec<Vec<u8>>>())?;
    d.set_item("move_uses", r.move_uses.iter().map(|v| v.clone()).collect::<Vec<Vec<u8>>>())?;
    d.set_item("sleep_observed", r.sleep_observed.to_vec())?;
    d.set_item("flags_before_faint", r.flags_before_faint.iter().map(|&(a, b)| vec![a, b]).collect::<Vec<Vec<bool>>>())?;
    d.set_item("binding_victim_turns", r.binding_victim_turns)?;
    Ok(d)
}

#[pyclass(name = "SearchNode")]
pub struct SearchNode {
    pub(crate) inner: Node,
}

fn seat_to_py<'py>(py: Python<'py>, s: &SeatState) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    let team = pyo3::types::PyList::empty(py);
    for m in s.team.iter().filter(|m| m.present) {
        let md = PyDict::new(py);
        md.set_item("species", m.species)?;
        md.set_item("base_stats", m.base_stats.to_vec())?;
        md.set_item("type_1", m.type_1.map(|t| t as i64).unwrap_or(-1))?;
        md.set_item("type_2", m.type_2.map(|t| t as i64).unwrap_or(-1))?;
        md.set_item("hp", m.hp_fraction)?;
        md.set_item("fainted", m.fainted)?;
        md.set_item("is_active", m.is_active)?;
        md.set_item("status", m.status)?;
        md.set_item("level", m.level)?;
        team.append(md)?;
    }
    d.set_item("team", team)?;
    d.set_item("active_slot", s.active_slot)?;
    d.set_item("boosts", s.active.boosts.to_vec())?;
    d.set_item("volatiles", s.active.volatiles.to_vec())?;
    d.set_item("status_counter", s.active.status_counter)?;
    d.set_item("preparing", s.active.preparing)?;
    let moves = pyo3::types::PyList::empty(py);
    for mv in s.moves.iter().filter(|m| m.present) {
        let vd = PyDict::new(py);
        vd.set_item("id", mv.id)?;
        vd.set_item("prob", mv.prob)?;
        vd.set_item("pp", mv.pp)?;
        vd.set_item("max_pp", mv.max_pp)?;
        moves.append(vd)?;
    }
    d.set_item("moves", moves)?;
    Ok(d)
}

fn state_to_py<'py>(py: Python<'py>, st: &ObservableState) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("turn", st.turn)?;
    d.set_item("force_switch", st.force_switch)?;
    d.set_item("trapped", st.trapped)?;
    d.set_item("aliased", st.aliased)?;
    d.set_item("own", seat_to_py(py, &st.own)?)?;
    d.set_item("opp", seat_to_py(py, &st.opp)?)?;
    Ok(d)
}

#[allow(dead_code)]
fn _seat_name(p: Player) -> &'static str {
    match p {
        Player::P1 => "p1",
        Player::P2 => "p2",
    }
}

fn cells_from_py(cells: Vec<(i32, i32, u32)>) -> Vec<Cell> {
    cells
        .into_iter()
        .map(|(row, col, n_chance)| Cell { row, col, n_chance })
        .collect()
}

#[pymethods]
impl SearchNode {
    /// A root over `battle`'s bytes with a FRESH projection: only what those
    /// bytes show (the two actives and their live move slots) counts as
    /// revealed. For fixtures and constructed roots; a live position comes from
    /// `BatchEnv.snapshot`, a resampled world from `with_battle`.
    #[staticmethod]
    #[pyo3(signature = (battle, req_p1, req_p2))]
    fn from_battle(battle: &PyBattle, req_p1: &str, req_p2: &str) -> PyResult<Self> {
        Ok(SearchNode { inner: Node::fresh(Battle(battle.inner.0), request(req_p1)?, request(req_p2)?) })
    }

    /// A CONSTRUCTED root (R7 B6): bytes from `BattleSpec.build()`, the request
    /// pair, and each seat's `RootReveal` payload as a dict (`reveal_order`,
    /// `revealed_moves`, `move_uses`, `sleep_observed`, `flags_before_faint`,
    /// `binding_victim_turns`) -- the projection is `BattleTracker::from_root`,
    /// never `from_battle`'s everything-revealed one (control C5).
    #[staticmethod]
    #[pyo3(signature = (battle, req_p1, req_p2, p1, p2))]
    fn from_root(
        battle: &PyBattle,
        req_p1: &str,
        req_p2: &str,
        p1: &Bound<'_, PyDict>,
        p2: &Bound<'_, PyDict>,
    ) -> PyResult<Self> {
        let r1 = reveal_from_py(p1)?;
        let r2 = reveal_from_py(p2)?;
        let b = Battle(battle.inner.0);
        let tracker = BattleTracker::from_root(&b, &r1, &r2);
        Ok(SearchNode { inner: Node::constructed(b, tracker, request(req_p1)?, request(req_p2)?) })
    }

    /// One seat's projection history as the `RootReveal` dict `from_root`
    /// takes -- the round-trip oracle: `from_root(node.battle(), *reqs,
    /// node.reveal("p1"), node.reveal("p2"))` must encode and mask like `node`.
    fn reveal<'py>(&self, py: Python<'py>, seat: &str) -> PyResult<Bound<'py, PyDict>> {
        reveal_to_py(py, &self.inner.tracker.reveal_of(player(seat)?))
    }

    /// The same projection over different bytes -- a resampled world (build
    /// B1b: `BattleSpec.from_visible` + a hidden-slot fill -> `build()`).
    #[pyo3(signature = (battle, req_p1, req_p2))]
    fn with_battle(&self, battle: &PyBattle, req_p1: &str, req_p2: &str) -> PyResult<Self> {
        Ok(SearchNode {
            inner: self.inner.with_battle(Battle(battle.inner.0), request(req_p1)?, request(req_p2)?),
        })
    }

    fn bytes(&self) -> Vec<u8> {
        self.inner.battle.0.to_vec()
    }
    /// The whole position -- bytes, requests, projection -- as bytes; `load`
    /// restores it exactly (a G0 rows file keeps one per position).
    fn save(&self) -> Vec<u8> {
        self.inner.save()
    }
    #[staticmethod]
    fn load(b: Vec<u8>) -> PyResult<Self> {
        Ok(SearchNode { inner: Node::load(&b).map_err(PyValueError::new_err)? })
    }
    fn battle(&self) -> PyBattle {
        PyBattle { inner: Battle(self.inner.battle.0) }
    }
    fn turn(&self) -> u16 {
        self.inner.battle.turn()
    }
    fn seed(&self) -> u64 {
        self.inner.battle.seed()
    }
    fn over(&self) -> bool {
        self.inner.over()
    }
    /// `(req_p1, req_p2)` as `"pass"` / `"move"` / `"switch"`.
    fn requests(&self) -> (&'static str, &'static str) {
        (request_to_py(self.inner.result.p1), request_to_py(self.inner.result.p2))
    }
    /// Reveal order of `seat`'s party as its FOE sees it (party indices).
    fn revealed(&self, seat: &str) -> PyResult<Vec<u8>> {
        Ok(self.inner.tracker.side(player(seat)?).reveal_order().to_vec())
    }

    /// The OBSERVABLE state for `seat`, as the nested dict `Tables.encode`
    /// reads (`pyencode.rs::parse_state`): `turn`, `force_switch`, `trapped`,
    /// `aliased`, and `own` / `opp` seats with `team` (present mons only, in
    /// party order for `own` and REVEAL order for `opp`), `active_slot`,
    /// `boosts` (7, encoder order), `volatiles` (7), `status_counter`,
    /// `preparing`, `moves` (`id`, `prob`, `pp`, `max_pp`). This is the input
    /// the engine->engine resample (build B1b) reads; `Tables.encode(view) ==
    /// obs` bitwise, by construction.
    fn view<'py>(&self, py: Python<'py>, tables: &Tables, seat: &str) -> PyResult<Bound<'py, PyDict>> {
        let st = self.inner.state(player(seat)?, &tables.inner);
        state_to_py(py, &st)
    }

    /// What `seat`'s FOE has been shown of `seat`'s party, from the projection:
    /// one entry per revealed member in REVEAL order --
    /// `(party_index, revealed_move_ids, observed_uses, sleep_turns_observed)`.
    /// A resampled world keeps revealed members at their true party indices
    /// so this projection stays valid over the new bytes.
    fn revealed_moves(&self, seat: &str) -> PyResult<Vec<(u8, Vec<u8>, Vec<u8>, u8)>> {
        let tr = self.inner.tracker.side(player(seat)?);
        Ok(tr
            .reveal_order()
            .iter()
            .map(|&p| {
                let i = p as usize;
                (p, tr.revealed_moves(i).to_vec(), tr.move_uses(i).to_vec(), tr.sleep_observed(i))
            })
            .collect())
    }

    /// The ACTIVE slot's identity for `seat`: `(species, (type_1, type_2))`
    /// as the cartridge stores them -- under Transform the copied target,
    /// otherwise the party member's own. A client sees this (the `|-transform|`
    /// line), so a resample may carry it.
    fn active_identity(&self, seat: &str) -> PyResult<(u8, (u8, u8))> {
        let a = self.inner.battle.side(player(seat)?).active();
        Ok((a.species(), a.types()))
    }
    /// The active slot's LIVE move slots `(id, pp)` for `seat` -- our own are
    /// known exactly; the foe's are hidden except under Transform, where they
    /// are copies of OUR active's moves.
    fn active_moves(&self, seat: &str) -> PyResult<Vec<(u8, u8)>> {
        Ok(self.inner.battle.side(player(seat)?).active().moves().to_vec())
    }
    /// The active slot's current stats `(hp, atk, def, spe, spc)` for `seat`.
    /// Ours are known; the foe's are hidden except under Transform.
    fn active_stats(&self, seat: &str) -> PyResult<[u16; 5]> {
        let s = self.inner.battle.side(player(seat)?).active().stats();
        Ok([s.hp, s.atk, s.def, s.spe, s.spc])
    }
    /// Boosts `(atk, def, spe, spc, accuracy, evasion)` of `seat`'s active,
    /// the spec's order.
    fn active_boosts(&self, seat: &str) -> PyResult<(i8, i8, i8, i8, i8, i8)> {
        let b = self.inner.battle.side(player(seat)?).active().boosts();
        Ok((b.atk, b.def, b.spe, b.spc, b.accuracy, b.evasion))
    }

    /// poke-env's 10-way mask for `seat`; all-false when it owes a Pass.
    fn mask<'py>(&self, py: Python<'py>, tables: &Tables, seat: &str) -> PyResult<Bound<'py, PyArray1<bool>>> {
        let m = self.inner.mask(player(seat)?, &tables.inner);
        Ok(PyArray1::from_vec(py, m.to_vec()))
    }

    /// The 828-vector for `seat` at the root.
    fn obs<'py>(&self, py: Python<'py>, tables: &Tables, seat: &str) -> PyResult<Bound<'py, PyArray1<f32>>> {
        let v = self.inner.obs(player(seat)?, &tables.inner);
        Ok(PyArray1::from_vec(py, v))
    }

    /// Expand `cells` = `[(row, col, n_chance), ...]` for `seat` (`"p1"`/`"p2"`,
    /// the ACTING seat; `row` is its action, `col` its foe's, `-1` when the foe
    /// owes a Pass). The chance seed of each leaf is `leaf_seed(seed_base, col,
    /// sample)` -- **never the row** (CRN-1); fold the decision key and the
    /// determinization index into `seed_base`.
    ///
    /// Returns a dict of arrays, row-major over cells then samples:
    /// `obs f32[n, 828]` (the acting seat's view; zeros at a terminal),
    /// `obs2 f32[n, 828]` and `priv f32[n, 408]` / `priv2 f32[n, 408]` when
    /// `both_views` (the foe's own view and both seats' privileged blocks),
    /// `terminal i8[n]` (0 none, 1 win, -1 loss for the acting seat, 2 tie),
    /// `cell i32[n]`, `sample i32[n]`, `seed u64[n]`, `req_next i8[n, 2]`
    /// (`(acting, foe)`: 0 pass, 1 move, 2 switch), `turn u16[n]`.
    /// The GIL is released for the whole loop. Chunk at ~4,096 leaves.
    #[pyo3(signature = (tables, seat, cells, seed_base, both_views=true))]
    fn expand<'py>(
        &self,
        py: Python<'py>,
        tables: &Tables,
        seat: &str,
        cells: Vec<(i32, i32, u32)>,
        seed_base: u64,
        both_views: bool,
    ) -> PyResult<Bound<'py, PyDict>> {
        let seat = player(seat)?;
        let cells = cells_from_py(cells);
        let render = if both_views { Render::Both } else { Render::Seat };
        let (e, _) = py
            .detach(|| self.inner.expand(&tables.inner, seat, &cells, seed_base, render, false))
            .map_err(PyValueError::new_err)?;
        let n = e.n;
        if e.obs.len() != n * OBS_DIM || e.terminal.len() != n || e.req_next.len() != 2 * n {
            return Err(PyRuntimeError::new_err(format!(
                "expand: {n} leaves but {} obs / {} terminal / {} req_next values",
                e.obs.len(),
                e.terminal.len(),
                e.req_next.len()
            )));
        }
        let d = PyDict::new(py);
        d.set_item("n", n)?;
        d.set_item("obs", rows2(py, &e.obs, OBS_DIM, "expand obs")?)?;
        if both_views {
            d.set_item("obs2", rows2(py, &e.obs2, OBS_DIM, "expand obs2")?)?;
            d.set_item("priv", rows2(py, &e.priv1, PRIV_DIM, "expand priv")?)?;
            d.set_item("priv2", rows2(py, &e.priv2, PRIV_DIM, "expand priv2")?)?;
        } else {
            d.set_item("obs2", py.None())?;
            d.set_item("priv", py.None())?;
            d.set_item("priv2", py.None())?;
        }
        d.set_item("terminal", PyArray1::from_vec(py, e.terminal))?;
        d.set_item("cell", PyArray1::from_vec(py, e.cell))?;
        d.set_item("sample", PyArray1::from_vec(py, e.sample))?;
        d.set_item("seed", PyArray1::from_vec(py, e.seed))?;
        d.set_item("req_next", rows2(py, &e.req_next, 2, "expand req_next")?)?;
        d.set_item("turn", PyArray1::from_vec(py, e.turn))?;
        d.set_item("rust_ns", e.elapsed_ns)?;
        Ok(d)
    }

    /// The same expansion, kept as live positions for rollouts (nothing is
    /// encoded here; `LeafBatch.pending` encodes on demand).
    #[pyo3(signature = (tables, seat, cells, seed_base))]
    fn leaves(
        &self,
        py: Python<'_>,
        tables: &Tables,
        seat: &str,
        cells: Vec<(i32, i32, u32)>,
        seed_base: u64,
    ) -> PyResult<LeafBatch> {
        let seat = player(seat)?;
        let cells = cells_from_py(cells);
        let (e, nodes) = py
            .detach(|| self.inner.expand(&tables.inner, seat, &cells, seed_base, Render::None, true))
            .map_err(PyValueError::new_err)?;
        Ok(LeafBatch { inner: RustLeafBatch::new(nodes, e.cell, e.sample, seed_base) })
    }

    fn __repr__(&self) -> String {
        format!(
            "SearchNode(turn={}, requests=({}, {}), over={})",
            self.inner.battle.turn(),
            request_to_py(self.inner.result.p1),
            request_to_py(self.inner.result.p2),
            self.inner.over()
        )
    }
}

/// Leaf positions driven to termination from Python: the rollout leaf. Both
/// seats are `"p1"` / `"p2"` here (engine seats, not learner/opponent), because
/// a rollout has no learner -- the policy plays both sides.
#[pyclass(name = "LeafBatch")]
pub struct LeafBatch {
    inner: RustLeafBatch,
}

#[pymethods]
impl LeafBatch {
    #[getter]
    fn n(&self) -> usize {
        self.inner.len()
    }
    /// How many leaves are still being played.
    fn live(&self) -> usize {
        self.inner.live()
    }
    fn cell<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<i32>> {
        PyArray1::from_vec(py, self.inner.cell.clone())
    }
    fn sample<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<i32>> {
        PyArray1::from_vec(py, self.inner.sample.clone())
    }
    fn done<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<bool>> {
        PyArray1::from_vec(py, self.inner.done())
    }
    fn turns<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray1<u16>> {
        PyArray1::from_vec(py, self.inner.turns())
    }
    /// `i8[n]` from `seat`: 0 not over, 1 win, -1 loss, 2 tie.
    fn outcome<'py>(&self, py: Python<'py>, seat: &str) -> PyResult<Bound<'py, PyArray1<i8>>> {
        Ok(PyArray1::from_vec(py, self.inner.outcome(player(seat)?)))
    }

    /// Leaf `i` as a root of its own (bytes, projection, requests), for a
    /// deeper expansion or a fixture. A copy: the batch is not disturbed.
    fn node(&self, i: usize) -> PyResult<SearchNode> {
        let n = self
            .inner
            .nodes
            .get(i)
            .ok_or_else(|| PyValueError::new_err(format!("leaf {i} out of range 0..{}", self.inner.len())))?;
        Ok(SearchNode { inner: n.clone() })
    }

    /// `(idx int32[m], obs f32[m, 828], mask bool[m, 10])` for every live leaf
    /// where `seat` owes a decision.
    #[pyo3(signature = (tables, seat))]
    fn pending<'py>(
        &self,
        py: Python<'py>,
        tables: &Tables,
        seat: &str,
    ) -> PyResult<(Bound<'py, PyArray1<i32>>, Bound<'py, PyArray2<f32>>, Bound<'py, PyArray2<bool>>)> {
        let p = player(seat)?;
        let (idx, obs, mask) = py.detach(|| self.inner.pending(p, &tables.inner));
        let m = idx.len();
        if obs.len() != m * OBS_DIM || mask.len() != m * N_ACTIONS {
            return Err(PyRuntimeError::new_err(format!(
                "pending({seat}): {m} leaves but {} obs / {} mask values",
                obs.len(),
                mask.len()
            )));
        }
        Ok((
            PyArray1::from_vec(py, idx),
            rows2(py, &obs, OBS_DIM, "pending obs")?,
            rows2(py, &mask, N_ACTIONS, "pending mask")?,
        ))
    }

    /// One update on every live leaf. Every seat owing a decision must appear
    /// in its index list, or the call refuses.
    #[pyo3(signature = (tables, p1_idx, p1_actions, p2_idx, p2_actions))]
    fn step(
        &mut self,
        py: Python<'_>,
        tables: &Tables,
        p1_idx: Vec<i32>,
        p1_actions: Vec<usize>,
        p2_idx: Vec<i32>,
        p2_actions: Vec<usize>,
    ) -> PyResult<()> {
        py.detach(|| self.inner.step(&tables.inner, &p1_idx, &p1_actions, &p2_idx, &p2_actions))
            .map_err(PyRuntimeError::new_err)
    }

    /// Both seats play a scripted policy (`random` / `max_power` /
    /// `most_damage_typed_engine`) for one update on every live leaf; returns
    /// how many are still live. Tests and benches only.
    #[pyo3(signature = (tables, policy="random"))]
    fn scripted_step(&mut self, py: Python<'_>, tables: &Tables, policy: &str) -> PyResult<usize> {
        let p = crate::scripted::Scripted::parse(policy).map_err(PyValueError::new_err)?;
        py.detach(|| self.inner.scripted_step(&tables.inner, p))
            .map_err(PyRuntimeError::new_err)
    }

    fn __repr__(&self) -> String {
        format!("LeafBatch(n={}, live={})", self.inner.len(), self.inner.live())
    }
}

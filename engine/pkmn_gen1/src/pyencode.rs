//! The Python surface for the encoder: `Tables` (built once from poke-env) and
//! `Tables.encode(state)` for one decision (plan §7.4, §7.6).
//!
//! `ObservableState` arrives as a plain nested dict so gate P-1 can fill it from
//! a poke-env `Battle`. What the harness shares with the reference encoder is
//! the STATIC TABLES and nothing else -- plan §7.4 requires the tables to be
//! poke-env's; the per-decision rules (the aliasing test, the opponent slot
//! assignment, the set-prior conditioning) are implemented on this side and are
//! falsifiable, which `scripts/engine_p1_run.py --mutate` demonstrates. When
//! `env.rs` fills the same struct by diffing the engine's bytes, it will build
//! the Rust struct directly and never touch this path.

use numpy::{PyArray1, PyArrayMethods};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::encoder::{self, OBS_DIM};
use crate::observe::{ActiveView, MonView, MoveView, ObservableState, SeatState};
use crate::tables::{
    EFFECT_DIM, MoveEntry, N_BASE_STATS, N_BOOSTS, N_TYPES, N_VOLATILES, SpeciesEntry,
    SpeciesPrior, StaticTables,
};

fn type_index(v: i64, what: &str) -> PyResult<Option<u8>> {
    match v {
        // -1 is the encoder's "no one-hot slot for this type" (spec.type_index
        // returns None); it must NOT become a chart lookup.
        -1 => Ok(None),
        0..=14 => Ok(Some(v as u8)),
        _ => Err(PyValueError::new_err(format!(
            "{what}: type index {v} outside 0..{} (or -1 for none)",
            N_TYPES - 1
        ))),
    }
}

#[pyclass]
pub struct Tables {
    pub(crate) inner: StaticTables,
}

#[pymethods]
impl Tables {
    /// Built by `rl/envs/engine_tables.py` from poke-env -- the same source the
    /// Python encoder reads. Nothing here is derived from the engine's own data.
    #[new]
    #[pyo3(signature = (species_base_stats, species_types, moves, type_chart, prior, set_prior=true))]
    #[allow(clippy::type_complexity)]
    fn new(
        species_base_stats: Vec<[u16; N_BASE_STATS]>,
        species_types: Vec<(i64, i64)>,
        moves: Vec<(u16, f32, u16, i16, bool, bool, i64, bool, Vec<f32>)>,
        type_chart: Vec<Vec<f64>>,
        prior: Vec<(u8, Vec<u8>, Vec<Vec<u8>>)>,
        set_prior: bool,
    ) -> PyResult<Self> {
        if species_base_stats.len() != species_types.len() {
            return Err(PyValueError::new_err("species tables have different lengths"));
        }
        let species = species_base_stats
            .into_iter()
            .zip(species_types)
            .map(|(base_stats, (t1, t2))| {
                Ok(SpeciesEntry {
                    base_stats,
                    type_1: type_index(t1, "species type_1")?,
                    type_2: type_index(t2, "species type_2")?,
                })
            })
            .collect::<PyResult<Vec<_>>>()?;

        let moves = moves
            .into_iter()
            .map(
                |(base_power, accuracy, max_pp, priority, physical, status, ty, ohko, effect)| {
                    if effect.len() != EFFECT_DIM {
                        return Err(PyValueError::new_err(format!(
                            "effect block is {} floats, expected {EFFECT_DIM}",
                            effect.len()
                        )));
                    }
                    let mut e = [0.0f32; EFFECT_DIM];
                    e.copy_from_slice(&effect);
                    Ok(MoveEntry {
                        base_power,
                        accuracy,
                        max_pp,
                        priority,
                        physical,
                        status,
                        move_type: type_index(ty, "move type")?,
                        ohko,
                        effect: e,
                    })
                },
            )
            .collect::<PyResult<Vec<_>>>()?;

        if type_chart.len() != N_TYPES || type_chart.iter().any(|r| r.len() != N_TYPES) {
            return Err(PyValueError::new_err(format!(
                "type chart must be {N_TYPES}x{N_TYPES}"
            )));
        }
        let mut chart = [[1.0f64; N_TYPES]; N_TYPES];
        for (i, row) in type_chart.iter().enumerate() {
            chart[i].copy_from_slice(row);
        }

        if species.is_empty() || moves.is_empty() {
            return Err(PyValueError::new_err("species and move tables must be non-empty"));
        }

        let mut priors: Vec<Option<SpeciesPrior>> = (0..species.len()).map(|_| None).collect();
        for (sid, ids, draws) in prior {
            if sid as usize >= priors.len() {
                return Err(PyValueError::new_err(format!(
                    "prior for species {sid} outside the species table"
                )));
            }
            if draws.iter().any(|d| d.iter().any(|&j| j as usize >= ids.len())) {
                return Err(PyValueError::new_err(format!(
                    "prior for species {sid} indexes past its candidate list"
                )));
            }
            priors[sid as usize] = Some(SpeciesPrior::new(ids, &draws));
        }

        Ok(Tables {
            inner: StaticTables {
                species,
                moves,
                type_chart: chart,
                prior: priors,
                set_prior,
            },
        })
    }

    #[getter]
    fn obs_dim(&self) -> usize {
        OBS_DIM
    }

    #[getter]
    fn n_species(&self) -> usize {
        self.inner.species.len()
    }

    #[getter]
    fn n_moves(&self) -> usize {
        self.inner.moves.len()
    }

    #[getter]
    fn n_prior_species(&self) -> usize {
        self.inner.prior.iter().filter(|p| p.is_some()).count()
    }

    /// `conditional_move_probs(species, revealed)`, exposed so the P-1 harness
    /// can compare the Rust prior against the reference directly rather than
    /// only through the encoder.
    fn conditional_move_probs(&self, species: u8, revealed: Vec<u8>) -> Vec<(u8, f64)> {
        match self.inner.prior.get(species as usize).and_then(|p| p.as_ref()) {
            Some(p) => p.conditional(&revealed),
            None => Vec::new(),
        }
    }

    /// Encode one decision. `state` is the nested dict `observe.rs` documents.
    fn encode<'py>(&self, py: Python<'py>, state: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyArray1<f32>>> {
        let s = parse_state(state)?;
        let out = PyArray1::<f32>::zeros(py, OBS_DIM, false);
        // SAFETY: `out` was just created here and no Python code can hold a
        // second reference to it before this returns.
        let slice = unsafe { out.as_slice_mut()? };
        encoder::encode(slice, &self.inner, &s);
        Ok(out)
    }

    /// The type multiplier the encoder would use, exposed so the P-1 harness can
    /// isolate a chart disagreement from an encoder disagreement.
    fn multiplier(&self, attacker: u8, def_1: i64, def_2: i64) -> PyResult<f64> {
        Ok(self.inner.multiplier(
            attacker,
            type_index(def_1, "def_1")?,
            type_index(def_2, "def_2")?,
        ))
    }
}

fn get<'py>(d: &Bound<'py, PyAny>, key: &str) -> PyResult<Bound<'py, PyAny>> {
    d.get_item(key)
        .map_err(|_| PyValueError::new_err(format!("state is missing {key:?}")))
}

fn parse_mon(d: &Bound<'_, PyAny>) -> PyResult<MonView> {
    let species: u8 = get(d, "species")?.extract()?;
    let base: Vec<u16> = get(d, "base_stats")?.extract()?;
    if base.len() != N_BASE_STATS {
        return Err(PyValueError::new_err(format!(
            "{} base stats, expected {N_BASE_STATS}",
            base.len()
        )));
    }
    let mut base_stats = [0u16; N_BASE_STATS];
    base_stats.copy_from_slice(&base);
    Ok(MonView {
        present: true,
        species,
        base_stats,
        type_1: type_index(get(d, "type_1")?.extract()?, "mon type_1")?,
        type_2: type_index(get(d, "type_2")?.extract()?, "mon type_2")?,
        hp_fraction: get(d, "hp")?.extract()?,
        fainted: get(d, "fainted")?.extract()?,
        is_active: get(d, "is_active")?.extract()?,
        status: get(d, "status")?.extract::<Option<u8>>()?,
        level: get(d, "level")?.extract()?,
    })
}

fn parse_seat(d: &Bound<'_, PyAny>) -> PyResult<SeatState> {
    let mut seat = SeatState::default();
    let team = get(d, "team")?;
    let n = team.len()?;
    if n > 6 {
        return Err(PyValueError::new_err(format!("{n} team slots, max 6")));
    }
    for i in 0..n {
        seat.team[i] = parse_mon(&team.get_item(i)?)?;
    }
    seat.active_slot = get(d, "active_slot")?.extract::<Option<usize>>()?;
    if let Some(a) = seat.active_slot {
        if a >= n {
            return Err(PyValueError::new_err(format!("active_slot {a} >= {n} mons")));
        }
    }

    let boosts: Vec<i16> = get(d, "boosts")?.extract()?;
    if boosts.len() != N_BOOSTS {
        return Err(PyValueError::new_err(format!(
            "{} boosts, expected {N_BOOSTS}",
            boosts.len()
        )));
    }
    let vols: Vec<bool> = get(d, "volatiles")?.extract()?;
    if vols.len() != N_VOLATILES {
        return Err(PyValueError::new_err(format!(
            "{} volatiles, expected {N_VOLATILES}",
            vols.len()
        )));
    }
    let mut active = ActiveView {
        status_counter: get(d, "status_counter")?.extract()?,
        preparing: get(d, "preparing")?.extract()?,
        ..Default::default()
    };
    active.boosts.copy_from_slice(&boosts);
    active.volatiles.copy_from_slice(&vols);
    seat.active = active;

    let moves = get(d, "moves")?;
    let m = moves.len()?;
    if m > 4 {
        return Err(PyValueError::new_err(format!("{m} move slots, max 4")));
    }
    for i in 0..m {
        let mv = moves.get_item(i)?;
        seat.moves[i] = MoveView {
            id: get(&mv, "id")?.extract()?,
            prob: get(&mv, "prob")?.extract()?,
            pp: get(&mv, "pp")?.extract()?,
            max_pp: get(&mv, "max_pp")?.extract()?,
            present: true,
        };
    }
    Ok(seat)
}

fn parse_state(d: &Bound<'_, PyAny>) -> PyResult<ObservableState> {
    Ok(ObservableState {
        turn: get(d, "turn")?.extract()?,
        force_switch: get(d, "force_switch")?.extract()?,
        trapped: get(d, "trapped")?.extract()?,
        aliased: get(d, "aliased")?.extract()?,
        own: parse_seat(&get(d, "own")?)?,
        opp: parse_seat(&get(d, "opp")?)?,
    })
}

// ---------------------------------------------------------------------------
// BatchEnv: the Python-facing collection surface (plan §7.6).
// ---------------------------------------------------------------------------

use crate::battle::Player;
use crate::env::{BatchEnv as RustBatchEnv, N_ACTIONS, Seat, TeamBank};
use numpy::PyArray2;
use pyo3::exceptions::PyRuntimeError;
use pyo3::types::PyDict;

/// K engine battles driven together. NOT a licensed collector: no number from
/// this is comparable to anything banked until gate A-1 passes.
#[pyclass]
pub struct BatchEnv {
    inner: RustBatchEnv,
}

#[pymethods]
impl BatchEnv {
    /// `bank` is the packed payload of a `scripts/engine_team_bank.py` file
    /// (header stripped by the caller, which is where the sha256 is checked).
    #[new]
    #[pyo3(signature = (k, seed, tables, bank, learner_seat="p1", battle_counter=0))]
    fn new(
        k: usize,
        seed: u64,
        tables: &Tables,
        bank: Vec<u8>,
        learner_seat: &str,
        battle_counter: u64,
    ) -> PyResult<Self> {
        let learner = match learner_seat {
            "p1" => Player::P1,
            "p2" => Player::P2,
            s => return Err(PyValueError::new_err(format!("learner_seat {s:?} is not p1/p2"))),
        };
        let bank = TeamBank::new(bank).map_err(PyValueError::new_err)?;
        let inner = RustBatchEnv::new(k, seed, tables.inner.clone(), bank, learner, battle_counter)
            .map_err(PyValueError::new_err)?;
        Ok(BatchEnv { inner })
    }

    #[getter]
    fn k(&self) -> usize {
        self.inner.len()
    }
    #[getter]
    fn battle_counter(&self) -> u64 {
        self.inner.battle_counter()
    }
    /// Where the NEXT battle is drawn from. Setting it does not disturb the
    /// battles already in flight -- pass `battle_counter` to the constructor to
    /// start a resumed lane in the right place.
    #[setter]
    fn set_battle_counter(&mut self, n: u64) {
        self.inner.set_battle_counter(n);
    }

    /// Which pool member owns a slot, for the lifetime of its battle.
    fn set_member(&mut self, slot: usize, member: i32) {
        self.inner.set_member(slot, member);
    }

    /// `(idx int32[n], obs f32[n, 828], mask bool[n, 10], member int32[n])` for
    /// every slot where that seat owes a real decision. Slots owing a Pass are
    /// absent.
    #[pyo3(signature = (seat="learner"))]
    fn pending<'py>(
        &self,
        py: Python<'py>,
        seat: &str,
    ) -> PyResult<(
        Bound<'py, PyArray1<i32>>,
        Bound<'py, PyArray2<f32>>,
        Bound<'py, PyArray2<bool>>,
        Bound<'py, PyArray1<i32>>,
    )> {
        let seat = match seat {
            "learner" => Seat::Learner,
            "opponent" => Seat::Opponent,
            s => return Err(PyValueError::new_err(format!("seat {s:?} is not learner/opponent"))),
        };
        let (idx, obs, mask, member) = py.detach(|| self.inner.pending(seat));
        let n = idx.len();
        Ok((
            PyArray1::from_vec(py, idx),
            PyArray2::from_vec2(py, &obs.chunks(OBS_DIM).map(|c| c.to_vec()).collect::<Vec<_>>())
                .unwrap_or_else(|_| PyArray2::zeros(py, [n, OBS_DIM], false)),
            PyArray2::from_vec2(
                py,
                &mask.chunks(N_ACTIONS).map(|c| c.to_vec()).collect::<Vec<_>>(),
            )
            .unwrap_or_else(|_| PyArray2::zeros(py, [n, N_ACTIONS], false)),
            PyArray1::from_vec(py, member),
        ))
    }

    /// `(idx int32[n], actions int64[n])` — what a SCRIPTED policy would do at
    /// every slot where `seat` owes a decision. `policy` is one of `random`,
    /// `max_power`, `most_damage_typed_engine` (plan §8.2). For gate D-1 and
    /// for the single-battle gym env; NEVER a training opponent, and an
    /// in-engine `eval/win_rate` is never the locked number. The bare
    /// `most_damage_typed` and `heuristics` are refused by name — both identify
    /// a REPORTED number that lives on the server.
    #[pyo3(signature = (seat="opponent", policy="random"))]
    fn scripted_actions<'py>(
        &mut self,
        py: Python<'py>,
        seat: &str,
        policy: &str,
    ) -> PyResult<(Bound<'py, PyArray1<i32>>, Bound<'py, PyArray1<i64>>)> {
        let seat = match seat {
            "learner" => Seat::Learner,
            "opponent" => Seat::Opponent,
            s => return Err(PyValueError::new_err(format!("seat {s:?} is not learner/opponent"))),
        };
        let p = crate::scripted::Scripted::parse(policy).map_err(PyValueError::new_err)?;
        let (idx, actions) = py.detach(|| self.inner.scripted_actions(seat, p));
        Ok((
            PyArray1::from_vec(py, idx),
            PyArray1::from_vec(py, actions.into_iter().map(|a| a as i64).collect()),
        ))
    }

    /// Gate D-1's ENGINE LEG: `n` scripted-vs-scripted battles, engine only,
    /// returned as per-battle arrays (plan §9). The whole loop runs in Rust so
    /// a 10,000-battle leg costs no Python; the server leg
    /// (`scripts/engine_d1.py --leg server`) plays the same policies against
    /// the real simulator and the two distributions are compared.
    ///
    /// This is a MEASUREMENT. It must not run next to a training fleet.
    #[pyo3(signature = (n, p1="max_power", p2="max_power"))]
    fn scripted_series<'py>(
        &mut self,
        py: Python<'py>,
        n: u64,
        p1: &str,
        p2: &str,
    ) -> PyResult<Bound<'py, PyDict>> {
        let parse =
            |s: &str| crate::scripted::Scripted::parse(s).map_err(PyValueError::new_err);
        let (a, b) = (parse(p1)?, parse(p2)?);
        let rows = py
            .detach(|| self.inner.scripted_series(n, a, b))
            .map_err(PyRuntimeError::new_err)?;
        let d = PyDict::new(py);
        d.set_item("outcome", PyArray1::from_vec(py, rows.iter().map(|r| r.outcome as i8).collect()))?;
        d.set_item("turns", PyArray1::from_vec(py, rows.iter().map(|r| r.turns).collect()))?;
        d.set_item("faints_p1", PyArray1::from_vec(py, rows.iter().map(|r| r.faints_p1).collect()))?;
        d.set_item("faints_p2", PyArray1::from_vec(py, rows.iter().map(|r| r.faints_p2).collect()))?;
        d.set_item("any_sleep", PyArray1::from_vec(py, rows.iter().map(|r| r.any_sleep).collect()))?;
        d.set_item("any_freeze", PyArray1::from_vec(py, rows.iter().map(|r| r.any_freeze).collect()))?;
        Ok(d)
    }

    /// One batched step. Releases the GIL for the engine/encoder loop.
    #[pyo3(signature = (l_idx, l_actions, l_logp, version, o_idx, o_actions))]
    fn step(
        &mut self,
        py: Python<'_>,
        l_idx: Vec<i32>,
        l_actions: Vec<usize>,
        l_logp: Vec<f32>,
        version: i64,
        o_idx: Vec<i32>,
        o_actions: Vec<usize>,
    ) -> PyResult<()> {
        py.detach(|| {
            self.inner
                .step(&l_idx, &l_actions, &l_logp, version, &o_idx, &o_actions)
        })
        .map_err(PyRuntimeError::new_err)
    }

    /// Finished episodes since the last call, as dicts of numpy arrays.
    fn drain_finished<'py>(&mut self, py: Python<'py>) -> PyResult<Vec<Bound<'py, PyDict>>> {
        let eps = self.inner.drain_finished();
        let mut out = Vec::with_capacity(eps.len());
        for e in eps {
            let d = PyDict::new(py);
            let n = e.length;
            d.set_item(
                "obs",
                PyArray2::from_vec2(py, &e.obs.chunks(OBS_DIM).map(|c| c.to_vec()).collect::<Vec<_>>())
                    .unwrap_or_else(|_| PyArray2::zeros(py, [n, OBS_DIM], false)),
            )?;
            d.set_item(
                "masks",
                PyArray2::from_vec2(
                    py,
                    &e.masks.chunks(N_ACTIONS).map(|c| c.to_vec()).collect::<Vec<_>>(),
                )
                .unwrap_or_else(|_| PyArray2::zeros(py, [n, N_ACTIONS], false)),
            )?;
            d.set_item("actions", PyArray1::from_vec(py, e.actions))?;
            d.set_item("old_logp", PyArray1::from_vec(py, e.logp))?;
            d.set_item("version", PyArray1::from_vec(py, e.version))?;
            d.set_item(
                "opp_choice",
                PyArray2::from_vec2(
                    py,
                    &e.opp_choice.chunks(3).map(|c| c.to_vec()).collect::<Vec<_>>(),
                )
                .unwrap_or_else(|_| PyArray2::zeros(py, [n, 3], false)),
            )?;
            d.set_item("reward", e.reward)?;
            d.set_item("length", n)?;
            d.set_item("turns", e.turns)?;
            d.set_item("seed", e.seed)?;
            d.set_item("member", e.member)?;
            d.set_item("slot", e.slot)?;
            out.push(d);
        }
        Ok(out)
    }

    /// The counters the collector logs. Names deliberately mirror the async
    /// path's `collect/*` keys.
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = &self.inner.stats;
        let d = PyDict::new(py);
        d.set_item("episodes_finished", s.episodes_finished)?;
        d.set_item("episodes_discarded", 0u64)?;
        d.set_item("seam_requests", s.learner_decisions)?;
        d.set_item("opponent_requests", s.opponent_decisions)?;
        d.set_item("engine_updates", s.engine_updates)?;
        d.set_item("battles_started", s.battles_started)?;
        d.set_item("battles_in_flight", self.inner.len())?;
        d.set_item("rooms_tracked", self.inner.len())?;
        d.set_item("rerequests", 0u64)?;
        d.set_item("battle_counter", self.inner.battle_counter())?;
        Ok(d)
    }
}

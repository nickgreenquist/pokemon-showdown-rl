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
    inner: StaticTables,
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
        moves: Vec<(u16, f32, u16, i16, bool, bool, i64, Vec<f32>)>,
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
                |(base_power, accuracy, max_pp, priority, physical, status, ty, effect)| {
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

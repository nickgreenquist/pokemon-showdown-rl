//! The `pkmn_gen1` Python extension module (plan §7.6).
//!
//! At B-0 this exposes only `build_info()` / `verify()` and a thin `Battle`
//! handle used by the gate scripts. `BatchEnv`, `TeamBank` and the encoder land
//! with the later gates.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::battle::{Battle, Choice, Outcome, Player, Request};
use crate::ffi;
use crate::layout;

fn player(p: &str) -> PyResult<Player> {
    match p {
        "p1" | "P1" => Ok(Player::P1),
        "p2" | "P2" => Ok(Player::P2),
        _ => Err(PyValueError::new_err(format!("unknown player {p:?}"))),
    }
}

fn request(r: &str) -> PyResult<Request> {
    match r {
        "pass" => Ok(Request::Pass),
        "move" => Ok(Request::Move),
        "switch" => Ok(Request::Switch),
        _ => Err(PyValueError::new_err(format!("unknown request {r:?}"))),
    }
}

fn choice_from_py(c: (String, u8)) -> PyResult<Choice> {
    match c.0.as_str() {
        "pass" => Ok(Choice::Pass),
        "move" => Ok(Choice::Move(c.1)),
        "switch" => Ok(Choice::Switch(c.1)),
        k => Err(PyValueError::new_err(format!("unknown choice kind {k:?}"))),
    }
}

fn choice_to_py(c: Choice) -> (&'static str, u8) {
    match c {
        Choice::Pass => ("pass", 0),
        Choice::Move(d) => ("move", d),
        Choice::Switch(d) => ("switch", d),
    }
}

fn outcome_to_py(o: Outcome) -> &'static str {
    match o {
        Outcome::None => "none",
        Outcome::Win => "win",
        Outcome::Lose => "lose",
        Outcome::Tie => "tie",
        Outcome::Error => "error",
    }
}

fn request_to_py(r: Request) -> &'static str {
    match r {
        Request::Pass => "pass",
        Request::Move => "move",
        Request::Switch => "switch",
    }
}

/// What engine, built how, by which toolchain. Stamped into run metadata next to
/// `ENCODER_FINGERPRINT` so a run records exactly what produced its transitions.
#[pyfunction]
fn build_info(py: Python<'_>) -> PyResult<Py<PyDict>> {
    let (showdown, log, chance, calc) = ffi::options();
    let d = PyDict::new(py);
    d.set_item("engine_sha", ffi::ENGINE_SHA)?;
    d.set_item("engine_sha_pinned", ffi::ENGINE_SHA_PINNED)?;
    d.set_item("zig", ffi::ZIG_VERSION)?;
    d.set_item("battle_size", layout::BATTLE_SIZE)?;
    let (max_choices, choices_size) = ffi::choice_sizes();
    d.set_item("max_choices", max_choices)?;
    d.set_item("choices_size", choices_size)?;
    let opts = PyDict::new(py);
    opts.set_item("showdown", showdown)?;
    opts.set_item("log", log)?;
    opts.set_item("chance", chance)?;
    opts.set_item("calc", calc)?;
    d.set_item("options", &opts)?;
    d.set_item("crate_version", env!("CARGO_PKG_VERSION"))?;
    Ok(d.into())
}

/// Asserts the extension is the artifact the collector requires, and returns
/// `build_info()`. Call it at import time (the FG-5 habit from the chapter-3
/// search line: verify a source-built dependency EVERY time).
#[pyfunction]
fn verify(py: Python<'_>) -> PyResult<Py<PyDict>> {
    ffi::verify_options().map_err(PyRuntimeError::new_err)?;
    build_info(py)
}

/// A single engine battle. Thin by design: the batched collector surface
/// (`BatchEnv`) arrives with the later gates; this exists so the B-0/B-1 gate
/// scripts can drive the engine from Python.
#[pyclass(name = "Battle")]
struct PyBattle {
    inner: Battle,
}

#[pymethods]
impl PyBattle {
    /// `p1`/`p2` are lists of 24-byte `Pokemon` records (see `team.rs`).
    #[new]
    fn new(seed: u64, p1: Vec<Vec<u8>>, p2: Vec<Vec<u8>>) -> PyResult<Self> {
        let conv = |team: &Vec<Vec<u8>>| -> PyResult<Vec<[u8; layout::POKEMON_SIZE]>> {
            team.iter()
                .map(|m| {
                    <[u8; layout::POKEMON_SIZE]>::try_from(m.as_slice()).map_err(|_| {
                        PyValueError::new_err(format!(
                            "a Pokemon record is {} bytes, expected {}",
                            m.len(),
                            layout::POKEMON_SIZE
                        ))
                    })
                })
                .collect()
        };
        let (a, b) = (conv(&p1)?, conv(&p2)?);
        if a.is_empty() || a.len() > 6 || b.is_empty() || b.len() > 6 {
            return Err(PyValueError::new_err("each side needs 1..6 Pokemon"));
        }
        Ok(PyBattle {
            inner: Battle::new(seed, &a, &b),
        })
    }

    /// Wraps an existing 384-byte state (for replaying a failure).
    #[staticmethod]
    fn from_bytes(b: Vec<u8>) -> PyResult<Self> {
        let arr = <[u8; layout::BATTLE_SIZE]>::try_from(b.as_slice())
            .map_err(|_| PyValueError::new_err("battle state must be 384 bytes"))?;
        Ok(PyBattle {
            inner: Battle(arr),
        })
    }

    fn bytes(&self) -> Vec<u8> {
        self.inner.0.to_vec()
    }
    fn turn(&self) -> u16 {
        self.inner.turn()
    }
    fn seed(&self) -> u64 {
        self.inner.seed()
    }

    /// The legal choices for a seat under a request kind, as `(kind, data)`.
    fn choices(&self, p: &str, req: &str) -> PyResult<Vec<(&'static str, u8)>> {
        let cs = self.inner.choices(player(p)?, request(req)?);
        Ok(cs.iter().map(choice_to_py).collect())
    }

    /// Applies both choices. Returns `(outcome, p1_request, p2_request)`.
    /// Raises on an illegal choice rather than letting the engine hit UB.
    fn update(
        &mut self,
        req1: &str,
        c1: (String, u8),
        req2: &str,
        c2: (String, u8),
    ) -> PyResult<(&'static str, &'static str, &'static str)> {
        let r = self
            .inner
            .update(request(req1)?, choice_from_py(c1)?, request(req2)?, choice_from_py(c2)?)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
        if r.outcome == Outcome::Error {
            return Err(PyRuntimeError::new_err(format!(
                "engine returned Error, which showdown mode should make unreachable; {:?}",
                self.inner
            )));
        }
        Ok((
            outcome_to_py(r.outcome),
            request_to_py(r.p1),
            request_to_py(r.p2),
        ))
    }

    /// Party-order view of one side: `(species, level, hp, max_hp, status, types,
    /// [(move_id, pp)])` per stored slot.
    #[allow(clippy::type_complexity)]
    fn party(&self, p: &str) -> PyResult<Vec<(u8, u8, u16, u16, u8, (u8, u8), Vec<(u8, u8)>)>> {
        let side = self.inner.side(player(p)?);
        Ok((0..6)
            .map(|i| {
                let m = side.party(i);
                (
                    m.species(),
                    m.level(),
                    m.hp(),
                    m.stats().hp,
                    m.status().0,
                    m.types(),
                    m.moves().to_vec(),
                )
            })
            .collect())
    }

    fn order(&self, p: &str) -> PyResult<Vec<u8>> {
        Ok(self.inner.side(player(p)?).order().to_vec())
    }

    fn active_volatiles(&self, p: &str) -> PyResult<u64> {
        Ok(self.inner.side(player(p)?).active().volatiles().0)
    }

    fn __repr__(&self) -> String {
        format!("<pkmn_gen1.Battle turn={} seed={:#018x}>", self.turn(), self.seed())
    }
}

#[pymodule]
fn pkmn_gen1(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(build_info, m)?)?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    m.add_class::<PyBattle>()?;
    m.add("__engine_sha__", ffi::ENGINE_SHA)?;
    m.add("BATTLE_SIZE", layout::BATTLE_SIZE)?;
    Ok(())
}

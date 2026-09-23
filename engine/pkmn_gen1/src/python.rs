//! The `pkmn_gen1` Python extension module (plan §7.6).
//!
//! At B-0 this exposes only `build_info()` / `verify()` and a thin `Battle`
//! handle used by the gate scripts. `BatchEnv`, `TeamBank` and the encoder land
//! with the later gates.

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::battle::{Battle, Choice, Outcome, Player, Request};
use crate::data;
use crate::ffi;
use crate::layout;
use crate::smoke;
use crate::spec;
use crate::team::PokemonSet;

pub(crate) fn player(p: &str) -> PyResult<Player> {
    match p {
        "p1" | "P1" => Ok(Player::P1),
        "p2" | "P2" => Ok(Player::P2),
        _ => Err(PyValueError::new_err(format!("unknown player {p:?}"))),
    }
}

pub(crate) fn request(r: &str) -> PyResult<Request> {
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

pub(crate) fn request_to_py(r: Request) -> &'static str {
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

/// The engine's own species names, index 0 = "None" (its `Species` enum order).
#[pyfunction]
fn species_names() -> Vec<&'static str> {
    data::SPECIES_NAMES.to_vec()
}

/// The engine's own move names, index 0 = "None" (its `Move` enum order).
#[pyfunction]
fn move_names() -> Vec<&'static str> {
    data::MOVE_NAMES.to_vec()
}

/// The engine's 15 types in CARTRIDGE order (the encoder's one-hot is alphabetical).
#[pyfunction]
fn type_names() -> Vec<&'static str> {
    data::TYPE_NAMES.to_vec()
}

/// Max PP with 3 PP Ups for an engine move id.
#[pyfunction]
fn max_pp(move_id: u8) -> PyResult<u8> {
    if move_id == 0 || move_id > 165 {
        return Err(PyValueError::new_err(format!("move id {move_id} out of range")));
    }
    Ok(data::max_pp(move_id))
}

fn build_set(species: u8, level: u8, moves: Vec<u8>, ivs: [u8; 5], evs: [u8; 5]) -> PyResult<PokemonSet> {
    if species == 0 || species > 151 {
        return Err(PyValueError::new_err(format!("species {species} out of range")));
    }
    if level == 0 || level > 100 {
        return Err(PyValueError::new_err(format!("level {level} out of range")));
    }
    if moves.is_empty() || moves.len() > 4 {
        return Err(PyValueError::new_err("a Pokemon has 1..4 moves"));
    }
    let mut m = [0u8; 4];
    for (i, &mv) in moves.iter().enumerate() {
        if mv == 0 || mv > 165 {
            return Err(PyValueError::new_err(format!("move id {mv} out of range")));
        }
        m[i] = mv;
    }
    Ok(PokemonSet { species, level, moves: m, ivs, evs })
}

/// Gate P-4: the crate's §5.5 stats for a set, as `(hp, atk, def, spe, spc)`.
///
/// `ivs`/`evs` are in the ENGINE's stat order (hp, atk, def, spe, spc); PS's
/// `spa` and `spd` are the same number in gen 1 and both map to `spc`.
#[pyfunction]
fn set_stats(species: u8, level: u8, ivs: [u8; 5], evs: [u8; 5]) -> PyResult<[u16; 5]> {
    Ok(build_set(species, level, vec![1], ivs, evs)?.stats())
}

/// The 24-byte engine `Pokemon` record for a set (plan §6.4).
#[pyfunction]
fn pokemon_record(
    species: u8,
    level: u8,
    moves: Vec<u8>,
    ivs: [u8; 5],
    evs: [u8; 5],
) -> PyResult<Vec<u8>> {
    Ok(build_set(species, level, moves, ivs, evs)?.to_bytes().to_vec())
}

/// Gate B-1: `n` random-policy battles, engine-only. Releases the GIL.
///
/// Raises on anything the gate forbids -- an illegal choice, an `Error` outcome,
/// a battle past turn 1000, an empty choice list.
#[pyfunction]
#[pyo3(signature = (n, seed=0, block=true))]
fn smoke_random_battles(py: Python<'_>, n: u64, seed: u64, block: bool) -> PyResult<Py<PyDict>> {
    let stats = py
        .detach(|| smoke::random_battles(n, seed, block))
        .map_err(PyRuntimeError::new_err)?;
    let d = PyDict::new(py);
    d.set_item("battles", stats.battles)?;
    d.set_item("p1_wins", stats.p1_wins)?;
    d.set_item("p2_wins", stats.p2_wins)?;
    d.set_item("ties", stats.ties)?;
    d.set_item("long_ties", stats.long_ties)?;
    d.set_item("updates", stats.updates)?;
    d.set_item("decisions", stats.decisions)?;
    d.set_item("switch_requests", stats.switch_requests)?;
    d.set_item("forced_decisions", stats.forced_decisions)?;
    d.set_item("turns_total", stats.turns_total)?;
    d.set_item("max_turns", stats.max_turns)?;
    d.set_item("min_turns", stats.min_turns)?;
    d.set_item("mean_turns", stats.mean_turns())?;
    d.set_item("mean_updates", stats.mean_updates())?;
    d.set_item("tie_rate", stats.tie_rate())?;
    d.set_item("p1_win_rate", stats.p1_win_rate())?;
    Ok(d.into())
}

/// Gate P-2, engine leg: the §7.2 mapping table measured on real battles.
///
/// `teams` is a list of `(p1_records, p2_records)` pairs from the team bank;
/// battles cycle through them. Releases the GIL.
#[pyfunction]
#[pyo3(signature = (n, seed, teams))]
#[allow(clippy::type_complexity)]
fn mask_table_split(
    py: Python<'_>,
    n: u64,
    seed: u64,
    teams: Vec<(Vec<Vec<u8>>, Vec<Vec<u8>>)>,
) -> PyResult<Py<PyDict>> {
    let conv = |team: &Vec<Vec<u8>>| -> PyResult<Vec<[u8; layout::POKEMON_SIZE]>> {
        team.iter()
            .map(|m| {
                <[u8; layout::POKEMON_SIZE]>::try_from(m.as_slice())
                    .map_err(|_| PyValueError::new_err("a Pokemon record must be 24 bytes"))
            })
            .collect()
    };
    let pairs = teams
        .iter()
        .map(|(a, b)| Ok((conv(a)?, conv(b)?)))
        .collect::<PyResult<Vec<_>>>()?;
    let sp = py
        .detach(|| smoke::mask_table_split(n, seed, &pairs))
        .map_err(PyRuntimeError::new_err)?;
    let d = PyDict::new(py);
    for (k, v) in [
        ("decisions", sp.decisions),
        ("switch_requests", sp.switch_requests),
        ("recharging", sp.recharging),
        ("thrashing", sp.thrashing),
        ("charging", sp.charging),
        ("rage", sp.rage),
        ("forced", sp.forced),
        ("bide_user", sp.bide_user),
        ("binding_user", sp.binding_user),
        ("limited", sp.limited),
        ("binding_victim", sp.binding_victim),
        ("asleep", sp.asleep),
        ("frozen", sp.frozen),
        ("struggle", sp.struggle),
        ("forced_not_single_move1", sp.forced_not_single_move1),
        ("forced_offered_switch", sp.forced_offered_switch),
        ("limited_not_one_move", sp.limited_not_one_move),
        ("limited_missing_switches", sp.limited_missing_switches),
    ] {
        d.set_item(k, v)?;
    }
    Ok(d.into())
}

/// A single engine battle. Thin by design: the batched collector surface
/// (`BatchEnv`) arrives with the later gates; this exists so the B-0/B-1 gate
/// scripts can drive the engine from Python.
#[pyclass(name = "Battle")]
pub(crate) struct PyBattle {
    pub(crate) inner: Battle,
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

// =============================================================================
// The WRITE-SIDE BRIDGE's Python surface
// (`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §2).
//
// Deliberately thin and deliberately NOT ergonomic-by-defaulting: every field
// §2.4 classes **S** is either named here or carries a default that `spec.rs`
// documents with the engine line that forces it. Phase 2 builds on these names,
// so they are the design's names.
//
// What is NOT here: the poke-env -> spec mapping. The determinizer, the reveal
// order, the HP quantisation and the A-1a PP rule live in
// `rl/search/engine_bridge.py` and are graded by R1-E.
// =============================================================================

fn spec_err(e: spec::SpecError) -> PyErr {
    PyValueError::new_err(format!("W-VALIDATE: {e}"))
}

fn moves_from_py(m: &[(u8, u8)]) -> PyResult<[(u8, u8); 4]> {
    if m.is_empty() || m.len() > 4 {
        return Err(PyValueError::new_err("a Pokemon has 1..4 (move_id, pp) slots"));
    }
    for (i, &(id, _)) in m.iter().enumerate() {
        if id == 0 || id > 165 {
            return Err(PyValueError::new_err(format!("move id {id} out of range in slot {i}")));
        }
    }
    let mut out = [(0u8, 0u8); 4];
    out[..m.len()].copy_from_slice(m);
    Ok(out)
}

/// One party member as a client can know it. `stats=None` applies §2.3's
/// identity (`ivs=[30;5], evs=[255;5]`, the determinizer's max-DV model
/// bit-for-bit); `types=None` reads the engine's own table; `hp=None` is full
/// HP. Stats and types are settable because Transform separates identity from
/// stats and the PRODUCER has to say which apply (gate P-1's lesson).
#[pyclass(name = "MonSpec", from_py_object)]
#[derive(Clone)]
struct PyMonSpec {
    inner: spec::MonSpec,
}

#[pymethods]
impl PyMonSpec {
    #[new]
    #[pyo3(signature = (species, level, moves, hp=None, status=0, stats=None, types=None))]
    fn new(
        species: u8,
        level: u8,
        moves: Vec<(u8, u8)>,
        hp: Option<u16>,
        status: u8,
        stats: Option<[u16; 5]>,
        types: Option<(u8, u8)>,
    ) -> PyResult<Self> {
        if species == 0 || species > 151 {
            return Err(PyValueError::new_err(format!("species {species} out of range")));
        }
        let slots = moves_from_py(&moves)?;
        let ids: Vec<u8> = slots.iter().map(|m| m.0).take_while(|&m| m != 0).collect();
        let mut inner = spec::MonSpec::determinized(
            species,
            level,
            {
                let mut a = [(0u8, 0u8); 4];
                for (i, &id) in ids.iter().enumerate() {
                    a[i] = (id, 0);
                }
                a
            },
        );
        inner.moves = slots;
        if let Some(s) = stats {
            inner.stats = layout::Stats { hp: s[0], atk: s[1], def: s[2], spe: s[3], spc: s[4] };
        }
        if let Some(t) = types {
            inner.types = t;
        }
        inner.hp = hp.unwrap_or(inner.stats.hp);
        inner.status = layout::StatusByte(status);
        Ok(PyMonSpec { inner })
    }

    /// An empty party slot (`species == 0`).
    #[staticmethod]
    fn empty() -> PyMonSpec {
        PyMonSpec { inner: spec::MonSpec::EMPTY }
    }

    /// The max-HP stat, which is what W-HP quantises the opponent's percentage
    /// against. Exposed so the Python half can apply `bridge.py:220`'s rounding
    /// without reimplementing the stat model.
    #[getter]
    fn max_hp(&self) -> u16 {
        self.inner.max_hp()
    }

    fn __repr__(&self) -> String {
        format!(
            "<MonSpec species={} level={} hp={}/{} status={:#04x}>",
            self.inner.species, self.inner.level, self.inner.hp, self.inner.stats.hp, self.inner.status.0
        )
    }
}

/// Reads `VolatileSpec` out of a plain dict. **Unknown keys raise** — a typo
/// must not become a silent zero, which is the whole failure mode §2.4 warns
/// about for the S-class fields.
fn volatiles_from_py(d: &Bound<'_, PyDict>) -> PyResult<spec::VolatileSpec> {
    let mut v = spec::VolatileSpec::default();
    for (k, val) in d.iter() {
        let key: String = k.extract()?;
        match key.as_str() {
            // K, and the one that carries a slot rather than a flag.
            "charging" => v.charging = val.extract()?,
            "recharging" => v.recharging = val.extract()?,
            "reflect" => v.reflect = val.extract()?,
            "confusion" => v.confusion = val.extract()?,
            "confusion_turns" => v.confusion_turns = val.extract()?,
            "substitute" => v.substitute = val.extract()?,
            "substitute_hp" => v.substitute_hp = val.extract()?,
            "transform" => {
                v.transform = match val.extract::<Option<(String, u8)>>()? {
                    Some((who, slot)) => Some((player(&who)?, slot)),
                    None => None,
                }
            }
            "light_screen" => v.light_screen = val.extract()?,
            // V in gen1randombattle (§2.5), carried so the type is complete.
            "bide" => v.bide = val.extract()?,
            "thrashing" => v.thrashing = val.extract()?,
            "multi_hit" => v.multi_hit = val.extract()?,
            "flinch" => v.flinch = val.extract()?,
            "binding" => v.binding = val.extract()?,
            "invulnerable" => v.invulnerable = val.extract()?,
            "mist" => v.mist = val.extract()?,
            "focus_energy" => v.focus_energy = val.extract()?,
            "rage" => v.rage = val.extract()?,
            "leech_seed" => v.leech_seed = val.extract()?,
            "toxic" => v.toxic = val.extract()?,
            "attacks" => v.attacks = val.extract()?,
            "state" => v.state = val.extract()?,
            "disable_move" => v.disable_move = val.extract()?,
            "disable_duration" => v.disable_duration = val.extract()?,
            "toxic_turns" => v.toxic_turns = val.extract()?,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown volatile {other:?}; see VolatileSpec in engine/pkmn_gen1/src/spec.rs"
                )));
            }
        }
    }
    Ok(v)
}

/// One side, plus the two `B_LAST_MOVES` bytes that belong to this player.
///
/// `boosts` is `(atk, def, spe, spc, accuracy, evasion)` — gen 1 has ONE
/// Special, so poke-env's `spa` (== `spd`) goes into `spc`. `identity` and
/// `live_moves` are `None` for everything except Transform. `active_stats` is
/// §2.6's named-and-not-taken upgrade hook, and is REQUIRED under Transform.
#[pyclass(name = "SideSpec", from_py_object)]
#[derive(Clone)]
struct PySideSpec {
    inner: spec::SideSpec,
}

#[pymethods]
impl PySideSpec {
    #[new]
    #[pyo3(signature = (
        party,
        active_index,
        boosts=(0, 0, 0, 0, 0, 0),
        volatiles=None,
        identity=None,
        live_moves=None,
        active_stats=None,
        last_selected_move=spec::DEFAULT_LAST_SELECTED_MOVE,
        last_used_move=spec::DEFAULT_LAST_USED_MOVE,
        last_move_index=spec::DEFAULT_LAST_MOVE_INDEX,
        last_move_counterable=spec::DEFAULT_LAST_MOVE_COUNTERABLE,
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        party: Vec<PyMonSpec>,
        active_index: u8,
        boosts: (i8, i8, i8, i8, i8, i8),
        volatiles: Option<&Bound<'_, PyDict>>,
        identity: Option<(u8, (u8, u8))>,
        live_moves: Option<Vec<(u8, u8)>>,
        active_stats: Option<[u16; 5]>,
        last_selected_move: u8,
        last_used_move: u8,
        last_move_index: u8,
        last_move_counterable: bool,
    ) -> PyResult<Self> {
        if party.is_empty() || party.len() > 6 {
            return Err(PyValueError::new_err("a side has 1..6 party slots"));
        }
        let mut slots = [spec::MonSpec::EMPTY; 6];
        for (i, m) in party.iter().enumerate() {
            slots[i] = m.inner;
        }
        let mut inner = spec::SideSpec::new(slots, active_index);
        inner.active.boosts = layout::Boosts {
            atk: boosts.0,
            def: boosts.1,
            spe: boosts.2,
            spc: boosts.3,
            accuracy: boosts.4,
            evasion: boosts.5,
        };
        if let Some(d) = volatiles {
            inner.active.volatiles = volatiles_from_py(d)?;
        }
        inner.active.identity = identity;
        inner.active.live_moves = match live_moves {
            Some(m) => Some(moves_from_py(&m)?),
            None => None,
        };
        inner.active.stats = active_stats.map(|s| layout::Stats {
            hp: s[0],
            atk: s[1],
            def: s[2],
            spe: s[3],
            spc: s[4],
        });
        inner.last_selected_move = last_selected_move;
        inner.last_used_move = last_used_move;
        inner.last_move_index = last_move_index;
        inner.last_move_counterable = last_move_counterable;
        Ok(PySideSpec { inner })
    }

    fn __repr__(&self) -> String {
        format!(
            "<SideSpec n={} active={}>",
            self.inner.party_len(),
            self.inner.active_index
        )
    }
}

/// The battle header plus both sides. `build()` assembles the 384 bytes, runs
/// **W-VALIDATE**, and returns `(Battle, req_p1, req_p2)` — the request pair is
/// rule **W-REQ** and is NOT in the bytes (`battle.rs:96-138`).
///
/// `seed` has no default on purpose: it IS the chance dial (§1.2, CRN-1), and a
/// shared default would silently correlate every sample in a batch.
#[pyclass(name = "BattleSpec", skip_from_py_object)]
#[derive(Clone)]
struct PyBattleSpec {
    inner: spec::BattleSpec,
}

#[pymethods]
impl PyBattleSpec {
    #[new]
    #[pyo3(signature = (turn, seed, p1, p2, last_damage=spec::DEFAULT_LAST_DAMAGE))]
    fn new(turn: u16, seed: u64, p1: PySideSpec, p2: PySideSpec, last_damage: u16) -> PyBattleSpec {
        PyBattleSpec {
            inner: spec::BattleSpec { turn, last_damage, seed, p1: p1.inner, p2: p2.inner },
        }
    }

    /// Rule W-REQ, without building. Cheap, and it tells the caller whether it
    /// even owes a decision.
    fn requests(&self) -> (&'static str, &'static str) {
        let (a, b) = self.inner.requests();
        (request_to_py(a), request_to_py(b))
    }

    /// `(Battle, req_p1, req_p2)`. Raises `ValueError` naming the field on any
    /// W-VALIDATE violation — it never repairs and never panics.
    fn build(&self) -> PyResult<(PyBattle, &'static str, &'static str)> {
        let root = self.inner.build().map_err(spec_err)?;
        Ok((
            PyBattle { inner: root.battle },
            request_to_py(root.p1),
            request_to_py(root.p2),
        ))
    }

    /// Rebuilds a spec from a battle's own bytes using ONLY §2.4's K-class
    /// fields. This is the byte-identity guard's input and a debugging aid; it
    /// is NOT the poke-env bridge.
    #[staticmethod]
    fn from_visible(b: &PyBattle) -> PyBattleSpec {
        PyBattleSpec { inner: spec::BattleSpec::from_visible(&b.inner) }
    }

    /// One side, as a `SideSpec` copy.
    fn side(&self, seat: &str) -> PyResult<PySideSpec> {
        Ok(PySideSpec {
            inner: match player(seat)? {
                Player::P1 => self.inner.p1,
                Player::P2 => self.inner.p2,
            },
        })
    }

    /// The same spec with one side replaced -- the engine->engine resample
    /// (R7 B1b): our side stays `from_visible`'s, the foe's is a belief draw.
    fn with_side(&self, seat: &str, side: PySideSpec) -> PyResult<PyBattleSpec> {
        let mut inner = self.inner;
        match player(seat)? {
            Player::P1 => inner.p1 = side.inner,
            Player::P2 => inner.p2 = side.inner,
        }
        Ok(PyBattleSpec { inner })
    }

    #[getter]
    fn seed(&self) -> u64 {
        self.inner.seed
    }
    #[getter]
    fn turn(&self) -> u16 {
        self.inner.turn
    }
}

/// **W-VALIDATE** on 384 arbitrary bytes, because `Battle.from_bytes` accepts
/// anything (§2.4). Raises `ValueError` naming the field; returns `None` when
/// the state is one the engine may legally be handed.
#[pyfunction]
fn validate_battle(b: Vec<u8>, req1: &str, req2: &str) -> PyResult<()> {
    let arr = <[u8; layout::BATTLE_SIZE]>::try_from(b.as_slice())
        .map_err(|_| PyValueError::new_err("battle state must be 384 bytes"))?;
    spec::validate(&Battle(arr), request(req1)?, request(req2)?).map_err(spec_err)
}

#[pymodule]
fn pkmn_gen1(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(build_info, m)?)?;
    m.add_function(wrap_pyfunction!(verify, m)?)?;
    m.add_function(wrap_pyfunction!(smoke_random_battles, m)?)?;
    m.add_function(wrap_pyfunction!(mask_table_split, m)?)?;
    m.add_function(wrap_pyfunction!(species_names, m)?)?;
    m.add_function(wrap_pyfunction!(move_names, m)?)?;
    m.add_function(wrap_pyfunction!(type_names, m)?)?;
    m.add_function(wrap_pyfunction!(max_pp, m)?)?;
    m.add_function(wrap_pyfunction!(set_stats, m)?)?;
    m.add_function(wrap_pyfunction!(pokemon_record, m)?)?;
    m.add_function(wrap_pyfunction!(validate_battle, m)?)?;
    m.add_class::<PyBattle>()?;
    // The write-side bridge (ENGINE_SEARCH_DESIGN.md §2). Phase 2 builds on
    // these names.
    m.add_class::<PyMonSpec>()?;
    m.add_class::<PySideSpec>()?;
    m.add_class::<PyBattleSpec>()?;
    m.add_class::<crate::pyencode::Tables>()?;
    m.add_class::<crate::pyencode::BatchEnv>()?;
    // R7 B0: the batched leaf path (search.rs) and the rollout leaf.
    m.add_class::<crate::pysearch::SearchNode>()?;
    m.add_class::<crate::pysearch::LeafBatch>()?;
    m.add("N_ACTIONS", crate::env::N_ACTIONS)?;
    m.add("OBS_DIM", crate::encoder::OBS_DIM)?;
    m.add("PRIV_DIM", crate::encoder::PRIV_DIM)?;
    // C6 is IMPLEMENTED in this build (`Tables(..., c6=True)` re-semanticises the
    // fixed-damage slots). `rl/envs/engine_collector.py::_check_engine_c6` reads
    // this so a stale editable install cannot stamp c6=True over c6-off rows.
    m.add("ENCODER_C6", true)?;
    m.add("__engine_sha__", ffi::ENGINE_SHA)?;
    // Bump whenever the ObservableState dict schema changes. A stale editable
    // install is otherwise INVISIBLE: `cargo build` writes target/, but the
    // importable .so only changes on `pip install -e`, and an old parser that
    // ignores a new key degrades silently instead of raising. That cost a
    // debugging cycle at P-1 (a transformed Ditto kept its original types).
    m.add("__state_schema__", 2u32)?;
    m.add("BATTLE_SIZE", layout::BATTLE_SIZE)?;
    Ok(())
}

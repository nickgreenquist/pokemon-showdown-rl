//! Static game tables, handed in from Python (plan §7.4).
//!
//! The Rust encoder holds NO game data of its own. Everything it reads about
//! species, moves and type effectiveness comes from poke-env, through
//! `rl/envs/engine_tables.py`, because poke-env is the single source the Python
//! encoder reads and the observation must stay pinned to it. The engine's own
//! `data.rs` tables are for SIMULATION only; B-0 asserts the two agree.
//!
//! Bit-exactness rule, applied throughout `encoder.rs`: the Python encoder does
//! its arithmetic in Python floats (f64) and rounds once, on assignment into a
//! float32 array. Every derived value here is therefore computed in **f64** and
//! cast to f32 exactly once, at the store. Values Python stores verbatim
//! (accuracy, the effect block, prior probabilities) travel as data.

/// The number of types in the encoder's one-hot (gen 1: 15, ALPHABETICAL).
pub const N_TYPES: usize = 15;
/// Boost keys: accuracy, atk, def, evasion, spa, spd, spe.
pub const N_BOOSTS: usize = 7;
/// Volatiles: CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE,
/// PARTIALLY_TRAPPED, REFLECT, SUBSTITUTE.
pub const N_VOLATILES: usize = 7;
/// Statuses: BRN, FRZ, PAR, PSN, SLP, TOX (FNT excluded -- the fainted flag).
pub const N_STATUSES: usize = 6;
/// Base stats in the encoder's order: hp, atk, def, spa, spe (gen 1 mirrors spd).
pub const N_BASE_STATS: usize = 5;
/// The v2 per-move effect block.
pub const EFFECT_DIM: usize = 23;

#[derive(Clone, Debug)]
pub struct SpeciesEntry {
    /// hp, atk, def, spa, spe -- poke-env's `base_stats` in the spec's order.
    pub base_stats: [u16; N_BASE_STATS],
    /// ALPHABETICAL type indices. `type_2` is `None` for a mono-type species:
    /// poke-env's `damage_multiplier` takes ONE chart lookup when `type_2 is
    /// None`, so repeating the type here would square the multiplier.
    pub type_1: Option<u8>,
    pub type_2: Option<u8>,
}

#[derive(Clone, Debug)]
pub struct MoveEntry {
    pub base_power: u16,
    /// Stored verbatim (poke-env's `Move.accuracy`, already a fraction).
    pub accuracy: f32,
    pub max_pp: u16,
    pub priority: i16,
    pub physical: bool,
    pub status: bool,
    /// ALPHABETICAL type index; `None` for a type outside the gen's 15.
    pub move_type: Option<u8>,
    /// `rl.envs.showdown._effect_block(move_id)` verbatim, as f32.
    pub effect: [f32; EFFECT_DIM],
}

impl Default for MoveEntry {
    fn default() -> Self {
        MoveEntry {
            base_power: 0,
            accuracy: 0.0,
            max_pp: 0,
            priority: 0,
            physical: false,
            status: false,
            move_type: None,
            effect: [0.0; EFFECT_DIM],
        }
    }
}

#[derive(Clone, Debug)]
pub struct StaticTables {
    /// Indexed by species id; index 0 is the unknown/absent row.
    pub species: Vec<SpeciesEntry>,
    /// Indexed by move id; index 0 is the unknown/absent row.
    pub moves: Vec<MoveEntry>,
    /// `chart[defender_type][attacker_type]`, matching poke-env's
    /// `type_chart[type_1.name][self.name]`. f64: the Python multiplier is a
    /// product of two f64 chart entries before it is rounded to f32.
    pub type_chart: [[f64; N_TYPES]; N_TYPES],
}

impl StaticTables {
    pub fn species(&self, id: u8) -> &SpeciesEntry {
        self.species
            .get(id as usize)
            .unwrap_or(&self.species[0])
    }
    pub fn mov(&self, id: u8) -> &MoveEntry {
        self.moves.get(id as usize).unwrap_or(&self.moves[0])
    }

    /// poke-env's `PokemonType.damage_multiplier(type_1, type_2)`, exactly:
    /// one chart lookup for a mono-type defender, the product of two otherwise.
    pub fn multiplier(&self, attacker: u8, def_1: Option<u8>, def_2: Option<u8>) -> f64 {
        let a = attacker as usize;
        let Some(d1) = def_1 else { return 1.0 };
        let m = self.type_chart[d1 as usize][a];
        match def_2 {
            Some(d2) => m * self.type_chart[d2 as usize][a],
            None => m,
        }
    }
}

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
    /// Indexed by species id; `None` for a species with no randbats set
    /// (`randbats_prior.known_species()`), which fills no opponent slots.
    pub prior: Vec<Option<SpeciesPrior>>,
    /// `POKEMON_RL_NO_SET_PRIOR=1`: encode only REVEALED opponent moves.
    pub set_prior: bool,
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
    pub fn prior_for(&self, species: u8) -> Option<&SpeciesPrior> {
        if !self.set_prior {
            return None;
        }
        self.prior.get(species as usize).and_then(|p| p.as_ref())
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

/// The vendored gen-1 randbats SET PRIOR for one species (plan §7.4).
///
/// `rl/envs/randbats_prior.py` draws 4,000 sets per species from Showdown's own
/// `randomSet` procedure and answers "P(move in set | revealed subset)" by
/// rejection over those draws. The draws are DATA and travel from Python; the
/// conditioning, the ordering and the slot assignment are done HERE, because
/// they are per-decision rules the engine side must reproduce rather than
/// borrow (the P-1 harness previously imported them, which made them
/// unfalsifiable -- see docs/engine_port/NOTES.md).
#[derive(Clone, Debug)]
pub struct SpeciesPrior {
    /// Candidate move ids, in the reference's own order: `sorted()` over the
    /// move ID STRINGS. Rust cannot re-derive that from numeric ids, so the
    /// order is handed in and a stable sort by probability preserves it, which
    /// is exactly what Python's stable `sort(key=-p)` does.
    pub ids: Vec<u8>,
    pub n_samples: usize,
    /// One bitset per candidate: bit r is set iff draw r contained that move.
    cols: Vec<Vec<u64>>,
}

impl SpeciesPrior {
    /// `draws[r]` lists the indices into `ids` that draw `r` contained.
    pub fn new(ids: Vec<u8>, draws: &[Vec<u8>]) -> SpeciesPrior {
        let n = draws.len();
        let words = n.div_ceil(64);
        let mut cols = vec![vec![0u64; words]; ids.len()];
        for (r, d) in draws.iter().enumerate() {
            for &j in d {
                cols[j as usize][r / 64] |= 1u64 << (r % 64);
            }
        }
        SpeciesPrior {
            ids,
            n_samples: n,
            cols,
        }
    }

    fn index_of(&self, id: u8) -> Option<usize> {
        self.ids.iter().position(|&x| x == id)
    }

    /// `conditional_move_probs(species, revealed)`: P(move in set | revealed),
    /// for the moves NOT already revealed, highest probability first.
    ///
    /// Exactness: the mean of a 0/1 column over `k` kept rows is `count / k`,
    /// and both are integers below 2^53, so an f64 division reproduces numpy's
    /// `mat[keep].mean(axis=0)` bit for bit whatever order numpy summed in.
    pub fn conditional(&self, revealed: &[u8]) -> Vec<(u8, f64)> {
        let words = self.n_samples.div_ceil(64);
        let mut keep = vec![!0u64; words];
        // Mask off the bits past n_samples so popcount stays honest.
        if self.n_samples % 64 != 0 {
            keep[words - 1] = (1u64 << (self.n_samples % 64)) - 1;
        }
        for &mv in revealed {
            if let Some(j) = self.index_of(mv) {
                for w in 0..words {
                    keep[w] &= self.cols[j][w];
                }
            }
        }
        let mut kept: u32 = keep.iter().map(|w| w.count_ones()).sum();
        if kept == 0 {
            // Revealed moves inconsistent with every draw (pool drift, Mimic,
            // Transform): fall back to the unconditional marginals, exactly as
            // the reference does, rather than emitting nothing.
            keep.iter_mut().for_each(|w| *w = !0u64);
            if self.n_samples % 64 != 0 {
                keep[words - 1] = (1u64 << (self.n_samples % 64)) - 1;
            }
            kept = self.n_samples as u32;
        }
        let mut out: Vec<(u8, f64)> = Vec::with_capacity(self.ids.len());
        for (j, &id) in self.ids.iter().enumerate() {
            if revealed.contains(&id) {
                continue;
            }
            let c: u32 = (0..words)
                .map(|w| (keep[w] & self.cols[j][w]).count_ones())
                .sum();
            if c == 0 {
                continue; // `p > 0.0` in the reference
            }
            out.push((id, c as f64 / kept as f64));
        }
        // STABLE, so ties keep the candidate order -- the reference relies on
        // Python's stable sort for exactly this.
        out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Four draws over three candidates: A in 3, B in 2, C in 3; A and C in the
    /// same 2 draws that also hold B.
    fn prior() -> SpeciesPrior {
        // ids [10, 20, 30]; draws as index lists.
        SpeciesPrior::new(
            vec![10, 20, 30],
            &[vec![0, 2], vec![0, 1, 2], vec![0, 1], vec![2]],
        )
    }

    #[test]
    fn unconditional_marginals_are_exact_ratios() {
        let p = prior();
        let out = p.conditional(&[]);
        // A 3/4, C 3/4, B 2/4 -- ties keep the CANDIDATE order, as Python's
        // stable sort does.
        assert_eq!(out, vec![(10, 0.75), (30, 0.75), (20, 0.5)]);
    }

    #[test]
    fn conditioning_drops_the_revealed_move_and_rejects_rows() {
        let p = prior();
        // Revealing B keeps draws 1 and 2: A in both, C in one.
        let out = p.conditional(&[20]);
        assert_eq!(out, vec![(10, 1.0), (30, 0.5)]);
        // A move with zero conditional probability is omitted entirely.
        let out = p.conditional(&[10, 20]);
        assert_eq!(out, vec![(30, 0.5)]);
    }

    #[test]
    fn an_impossible_reveal_falls_back_to_the_unconditional_row() {
        let p = prior();
        // 99 is not a candidate at all: ignored, like the reference's `if mv in ids`.
        assert_eq!(p.conditional(&[99]), p.conditional(&[]));
    }

    #[test]
    fn a_reveal_consistent_with_no_draw_falls_back() {
        // B and C never co-occur, so conditioning on both keeps nothing and the
        // reference falls back to the unconditional marginals rather than
        // emitting an empty list.
        let p = SpeciesPrior::new(vec![10, 20, 30], &[vec![0, 1], vec![0, 2]]);
        let out = p.conditional(&[20, 30]);
        assert_eq!(out, vec![(10, 1.0)]);
    }
}

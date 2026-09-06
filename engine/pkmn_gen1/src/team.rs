//! Turning a Pokémon set into the engine's 24-byte `Pokemon` record (plan §5.5,
//! §6.4), and a random-team source for the B-1 smoke.
//!
//! Stats use **Showdown's** formula (`sim/battle.ts::statModify`), not the
//! engine's cartridge `Stats.calc`: the `|request|` JSON reports PS's numbers,
//! so PS's numbers are what P-4 checks us against and what the observation must
//! agree with. PS stores gen-1 DVs as even IVs and mirrors `spa` into `spd`; the
//! engine keeps one `spc`.

use crate::battle::splitmix64;
use crate::data;
use crate::layout::{self, POKEMON_SIZE};

/// Showdown's gen-1 stat calculation, integer-exact.
///
/// ```text
/// hp    = floor(floor(2*base + iv + floor(ev/4) + 100) * level / 100 + 10)
/// other = floor(floor(2*base + iv + floor(ev/4))       * level / 100 + 5)
/// ```
pub fn ps_stat(base: u16, iv: u16, ev: u16, level: u16, is_hp: bool) -> u16 {
    let core = 2 * base as u32 + iv as u32 + (ev as u32) / 4;
    if is_hp {
        ((core + 100) * level as u32 / 100 + 10) as u16
    } else {
        (core * level as u32 / 100 + 5) as u16
    }
}

/// One party member, as the team bank stores it.
///
/// `ivs`/`evs` are in the engine's stat order (hp, atk, def, spe, spc) -- PS's
/// `spa` and `spd` are the same number in gen 1, so one `spc` entry carries both.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PokemonSet {
    pub species: u8,
    pub level: u8,
    /// Move ids in PS's SHUFFLED slot order, 0-padded. The shuffle is per battle
    /// and is exactly why the encoder is slot-symmetric.
    pub moves: [u8; 4],
    pub ivs: [u8; 5],
    pub evs: [u8; 5],
}

impl PokemonSet {
    /// A gen-1 randbats default: level from the set, IVs 30, EVs 255.
    pub fn new(species: u8, level: u8, moves: [u8; 4]) -> PokemonSet {
        PokemonSet {
            species,
            level,
            moves,
            ivs: [30; 5],
            evs: [255; 5],
        }
    }

    pub fn stats(&self) -> [u16; 5] {
        let base = data::SPECIES_BASE_STATS[self.species as usize];
        std::array::from_fn(|i| {
            ps_stat(
                base[i],
                self.ivs[i] as u16,
                self.evs[i] as u16,
                self.level as u16,
                i == 0,
            )
        })
    }

    pub fn n_moves(&self) -> usize {
        self.moves.iter().take_while(|&&m| m != 0).count()
    }

    /// The engine's 24-byte `Pokemon` record: full HP, no status, types and base
    /// stats from the ENGINE's tables, every move at max PP.
    pub fn to_bytes(&self) -> [u8; POKEMON_SIZE] {
        assert!(
            self.species >= 1 && self.species <= 151,
            "species {} out of range",
            self.species
        );
        assert!(self.n_moves() > 0, "a Pokemon needs at least one move");
        let mut b = [0u8; POKEMON_SIZE];
        let stats = self.stats();
        for (i, s) in stats.iter().enumerate() {
            b[layout::P_STATS + 2 * i..layout::P_STATS + 2 * i + 2]
                .copy_from_slice(&s.to_le_bytes());
        }
        for (i, &m) in self.moves.iter().enumerate() {
            b[layout::P_MOVES + 2 * i] = m;
            b[layout::P_MOVES + 2 * i + 1] = if m == 0 { 0 } else { data::max_pp(m) };
        }
        b[layout::P_HP..layout::P_HP + 2].copy_from_slice(&stats[0].to_le_bytes());
        b[layout::P_STATUS] = 0;
        b[layout::P_SPECIES] = self.species;
        let (t1, t2) = data::SPECIES_TYPES[self.species as usize];
        b[layout::P_TYPES] = t1 | (t2 << 4);
        b[layout::P_LEVEL] = self.level;
        b
    }
}

/// Moves the engine's own random-battle helper excludes in showdown mode
/// (`helpers.zig::blocked`): "moves that contain bugs on Pokémon Showdown that
/// are unimplementable in the engine". Mimic(102), Metronome(118),
/// Mirror Move(119), Transform(144).
pub const BLOCKED_MOVES: [u8; 4] = [102, 118, 119, 144];

/// A deterministic random team, for the B-1 wrapper smoke ONLY.
///
/// This is NOT the randbats distribution -- real teams come from the
/// PS-generated bank at P-3. It exists so B-1 can exercise the wrapper before
/// the bank does, and it mirrors the engine's own fuzz configuration.
pub fn random_team(seed: u64, block: bool) -> Vec<PokemonSet> {
    let mut s = seed;
    let mut next = move || {
        s = splitmix64(s);
        s
    };
    let mut used: Vec<u8> = Vec::with_capacity(6);
    (0..6)
        .map(|_| {
            let species = loop {
                let c = (next() % 151) as u8 + 1;
                if !used.contains(&c) {
                    used.push(c);
                    break c;
                }
            };
            let mut moves = [0u8; 4];
            let mut have: Vec<u8> = Vec::with_capacity(4);
            for slot in 0..4 {
                let m = loop {
                    let c = (next() % 164) as u8 + 1; // 165 = Struggle, never in a moveset
                    if have.contains(&c) {
                        continue;
                    }
                    if block && BLOCKED_MOVES.contains(&c) {
                        continue;
                    }
                    break c;
                };
                have.push(m);
                moves[slot] = m;
            }
            PokemonSet::new(species, 100, moves)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ps_stat_reproduces_known_values() {
        // A level-100 randbats mon: IV 30, EV 255 -> 255/4 = 63.
        // Mewtwo (base 106 hp / 130 spe): hp = 2*106+30+63+100 = 405 -> 415.
        assert_eq!(ps_stat(106, 30, 255, 100, true), 415);
        // spe = 2*130+30+63 = 353 -> 358.
        assert_eq!(ps_stat(130, 30, 255, 100, false), 358);
        // Level scaling truncates: level 80 Mewtwo hp = 405*80/100 + 10 = 334.
        assert_eq!(ps_stat(106, 30, 255, 80, true), 334);
        assert_eq!(ps_stat(130, 30, 255, 80, false), 287);
        // Zero IVs/EVs, level 1: the floors bite.
        assert_eq!(ps_stat(100, 0, 0, 1, true), 13);
        assert_eq!(ps_stat(100, 0, 0, 1, false), 7);
    }

    #[test]
    fn set_to_bytes_round_trips_through_the_layout_views() {
        let set = PokemonSet::new(151, 80, [1, 2, 0, 0]); // Mew, Pound + Karate Chop
        let b = set.to_bytes();
        let v = layout::PokemonView(&b);
        assert_eq!(v.species(), 151);
        assert_eq!(v.level(), 80);
        assert_eq!(v.types(), (12, 12), "Mew is mono-Psychic; the type repeats");
        let stats = set.stats();
        assert_eq!(v.stats().hp, stats[0]);
        assert_eq!(v.stats().spc, stats[4]);
        assert_eq!(v.hp(), stats[0], "a fresh mon starts at full HP");
        assert_eq!(v.moves()[0], (1, data::max_pp(1)));
        assert_eq!(v.moves()[1], (2, data::max_pp(2)));
        assert_eq!(v.moves()[2], (0, 0), "an unused slot is empty, not 0-PP");
        assert!(v.status().healthy());
        assert!(!v.is_empty());
    }

    #[test]
    fn random_team_is_deterministic_and_well_formed() {
        let a = random_team(12345, true);
        assert_eq!(a, random_team(12345, true), "same seed, same team");
        assert_ne!(a, random_team(12346, true));
        assert_eq!(a.len(), 6);
        let mut species: Vec<u8> = a.iter().map(|m| m.species).collect();
        species.sort_unstable();
        species.dedup();
        assert_eq!(species.len(), 6, "no duplicate species");
        for m in &a {
            assert_eq!(m.n_moves(), 4);
            let mut ms = m.moves.to_vec();
            ms.sort_unstable();
            ms.dedup();
            assert_eq!(ms.len(), 4, "no duplicate moves");
            for &mv in &m.moves {
                assert!((1..=164).contains(&mv), "Struggle is never in a moveset");
                assert!(!BLOCKED_MOVES.contains(&mv));
            }
        }
        // Without blocking, the excluded four do appear.
        let many: Vec<u8> = (0..400u64)
            .flat_map(|s| random_team(s, false))
            .flat_map(|m| m.moves)
            .collect();
        assert!(BLOCKED_MOVES.iter().all(|b| many.contains(b)));
    }
}

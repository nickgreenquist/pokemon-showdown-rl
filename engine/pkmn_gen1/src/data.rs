//! The engine's OWN gen-1 tables, codegen'd by `build.rs` from the pinned
//! `vendor/pkmn-engine/src/data/data.json`.
//!
//! These are the numbers the engine SIMULATES with. The numbers the observation
//! is built from come from poke-env and are handed in from Python (plan §7.4);
//! B-0 asserts the two agree for all 151 species and 165 moves. Keeping them
//! separate is deliberate -- a silent divergence would mean the agent sees a
//! different game than it plays.

include!(concat!(env!("OUT_DIR"), "/engine_data.rs"));

/// Max PP with 3 PP Ups: PS's `calculatePP` (`pp * 8/5`, and gen <= 2 subtracts
/// the 3 PP Ups for 40-PP moves -> 61). Equal to the engine helper's
/// `min(pp / 5 * 8, 61)` for every gen 1 move -- asserted at B-0 against
/// poke-env's `Move.max_pp` for all 165.
pub fn max_pp(move_id: u8) -> u8 {
    let base = MOVE_BASE_PP[move_id as usize] as u16;
    (base / 5 * 8).min(61) as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tables_are_one_based_like_the_engine_enums() {
        assert_eq!(SPECIES_NAMES[0], "None");
        assert_eq!(SPECIES_NAMES[1], "Bulbasaur");
        assert_eq!(SPECIES_NAMES[151], "Mew");
        assert_eq!(MOVE_NAMES[0], "None");
        assert_eq!(MOVE_NAMES[1], "Pound");
        assert_eq!(MOVE_NAMES[165], "Struggle");
        assert_eq!(TYPE_NAMES[0], "Normal");
        assert_eq!(TYPE_NAMES[14], "Dragon");
    }

    #[test]
    fn base_stats_and_types_are_the_engines() {
        // Bulbasaur: 45/49/49/45/65, Grass(10)/Poison(3).
        assert_eq!(SPECIES_BASE_STATS[1], [45, 49, 49, 45, 65]);
        assert_eq!(SPECIES_TYPES[1], (10, 3));
        // Mew: 100 across, mono-Psychic(12) -> the type repeats.
        assert_eq!(SPECIES_BASE_STATS[151], [100, 100, 100, 100, 100]);
        assert_eq!(SPECIES_TYPES[151], (12, 12));
        // Mewtwo (150): 106/110/90/130/154.
        assert_eq!(SPECIES_BASE_STATS[150], [106, 110, 90, 130, 154]);
    }

    #[test]
    fn max_pp_matches_the_engine_helper() {
        for id in 1..=165u8 {
            let base = MOVE_BASE_PP[id as usize] as u16;
            assert!(base > 0, "{} has no base PP", MOVE_NAMES[id as usize]);
            assert_eq!(max_pp(id) as u16, (base / 5 * 8).min(61));
        }
        assert_eq!(max_pp(1), 56, "Pound: 35 base PP");
        // A 40-PP move caps at 61, not 64.
        let forty: Vec<u8> = (1..=165u8).filter(|&i| MOVE_BASE_PP[i as usize] == 40).collect();
        assert!(!forty.is_empty());
        for id in forty {
            assert_eq!(max_pp(id), 61, "{}", MOVE_NAMES[id as usize]);
        }
    }
}

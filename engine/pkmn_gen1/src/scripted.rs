//! In-engine scripted opponents (plan §8.2) — `random`, `max_power` and
//! `most_damage_typed`, ports of the poke-env players of the same names.
//!
//! They exist for two jobs and NEITHER is a training arm: gate D-1 plays the
//! same scripted policy on both seats against both the engine and the server
//! and compares the outcome distributions, and `rl/envs/engine_env.py` needs an
//! opponent that runs without a server. `SimpleHeuristicsPlayer` is deliberately
//! NOT here: it reads poke-env `Battle` objects, and a re-implementation would
//! be a different bot with the same name (plan §8.2). The SH anchor stays on
//! the server, always.
//!
//! Every policy reads the OBSERVABLE state, never the engine's 384 bytes. A
//! scripted opponent that cheated would make D-1 compare two different games,
//! and would make an in-engine eval number meaningless.
//!
//! Borrowed definitions, named per the standing obligation:
//!   * `random` / `max_power` — poke-env (MIT), `player/baselines.py`.
//!   * `most_damage_typed` — Huang & Lee's `MostDamageMovePlayer(type_aware=
//!     True)` via `rl/envs/most_damage_typed.py`, whose docstring carries the
//!     three disclosed deviations. Deviation (1) (Return at base power 102) is
//!     gen 4+ only and cannot apply here.

use crate::env::N_ACTIONS;
use crate::observe::ObservableState;
use crate::tables::StaticTables;

/// H&L's constant for the OHKO moves, which poke-env reports at base power 0.
const OHKO_SCORE: f64 = 120.0;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Scripted {
    Random,
    MaxPower,
    MostDamageTyped,
}

impl Scripted {
    pub fn parse(name: &str) -> Option<Scripted> {
        Some(match name {
            "random" => Scripted::Random,
            "max_power" => Scripted::MaxPower,
            "most_damage_typed" => Scripted::MostDamageTyped,
            _ => return None,
        })
    }

    pub fn name(self) -> &'static str {
        match self {
            Scripted::Random => "random",
            Scripted::MaxPower => "max_power",
            Scripted::MostDamageTyped => "most_damage_typed",
        }
    }

    /// The action this policy takes. `rng` is a splitmix64 state, advanced on
    /// every draw — the tie-break and uniform streams both come from it.
    pub fn act(
        self,
        st: &ObservableState,
        mask: &[bool; N_ACTIONS],
        t: &StaticTables,
        rng: &mut u64,
    ) -> usize {
        let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| mask[a]).collect();
        debug_assert!(!legal.is_empty(), "showdown mode always offers a choice");
        let moves: Vec<usize> = legal.iter().copied().filter(|&a| a >= 6).collect();
        let switches: Vec<usize> = legal.iter().copied().filter(|&a| a < 6).collect();

        match self {
            // `choose_random_singles_move` draws uniformly from
            // `available_moves + available_switches`, which is exactly the
            // mask's true entries (proved at gate P-2).
            Scripted::Random => pick(&legal, rng),

            // `MaxBasePowerPlayer.choose_singles_move`: a move whenever one is
            // legal -- it NEVER switches voluntarily -- else a random switch.
            // `max()` keeps the FIRST maximum, and `available_moves` is in
            // stored-slot order, so ties go to the lowest slot.
            Scripted::MaxPower => {
                if moves.is_empty() {
                    return pick(&switches, rng);
                }
                // Rust's `max_by_key` keeps the LAST maximum where Python's
                // `max` keeps the first, so the slot is part of the key:
                // highest base power, then lowest action index.
                *moves
                    .iter()
                    .max_by_key(|&&a| {
                        (t.mov(st.own.moves[a - 6].id).base_power, std::cmp::Reverse(a))
                    })
                    .expect("non-empty")
            }

            Scripted::MostDamageTyped => {
                if !moves.is_empty() {
                    let scored: Vec<f64> =
                        moves.iter().map(|&a| self.move_score(st, t, a - 6)).collect();
                    return pick(&tied_max(&moves, &scored), rng);
                }
                if switches.is_empty() {
                    return pick(&legal, rng);
                }
                let Some(foe) = st.opp.active() else {
                    return pick(&switches, rng);
                };
                // H&L's forced-switch criterion: minimise the sum, over the
                // opponent's types, of that type's effectiveness against the
                // candidate. Ties uniform.
                let scored: Vec<f64> = switches
                    .iter()
                    .map(|&a| {
                        let c = &st.own.team[a];
                        [foe.type_1, foe.type_2]
                            .into_iter()
                            .flatten()
                            .map(|ty| t.multiplier(ty, c.type_1, c.type_2))
                            .sum()
                    })
                    .collect();
                let neg: Vec<f64> = scored.iter().map(|s| -s).collect();
                pick(&tied_max(&switches, &neg), rng)
            }
        }
    }

    /// `most_damage_typed::move_score` — base power x effectiveness against the
    /// defender, OHKO moves at 120, and 0 for a move with no base power (every
    /// status move). The defender's types are the OBSERVED ones, which is what
    /// poke-env's `opponent_active_pokemon` carries.
    fn move_score(self, st: &ObservableState, t: &StaticTables, slot: usize) -> f64 {
        let entry = t.mov(st.own.moves[slot].id);
        if entry.ohko {
            return OHKO_SCORE;
        }
        let bp = entry.base_power as f64;
        if bp <= 0.0 {
            return 0.0;
        }
        let (Some(ty), Some(foe)) = (entry.move_type, st.opp.active()) else {
            return bp;
        };
        bp * t.multiplier(ty, foe.type_1, foe.type_2)
    }
}

/// Every action tied for the highest score. Exact float equality on purpose:
/// `most_damage_typed` compares `max(scored)` the same way, and both sides
/// compute the same product from the same f64 chart entries.
fn tied_max(actions: &[usize], scores: &[f64]) -> Vec<usize> {
    let best = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    actions
        .iter()
        .zip(scores)
        .filter(|(_, s)| **s == best)
        .map(|(a, _)| *a)
        .collect()
}

fn pick(from: &[usize], rng: &mut u64) -> usize {
    *rng = rng.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let draw = crate::battle::splitmix64(*rng);
    from[(draw >> 33) as usize % from.len()]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::observe::{MonView, MoveView};
    use crate::tables::{MoveEntry, N_TYPES, SpeciesEntry, StaticTables};

    /// Types are indices into an ALPHABETICAL gen-1 list; the chart below is
    /// synthetic, so only the arithmetic is under test, never gen 1's chart.
    fn tables() -> StaticTables {
        let mut chart = [[1.0f64; N_TYPES]; N_TYPES];
        chart[3][1] = 2.0; // attacker 1 is super effective on defender 3
        chart[3][2] = 0.5;
        chart[4][1] = 0.0;
        StaticTables {
            species: vec![SpeciesEntry { base_stats: [1; 5], type_1: None, type_2: None }; 4],
            moves: (0..8u16)
                .map(|i| MoveEntry {
                    base_power: [0, 40, 90, 90, 0, 120, 35, 0][i as usize],
                    move_type: Some([0, 1, 1, 2, 1, 0, 1, 1][i as usize]),
                    ohko: i == 7,
                    ..Default::default()
                })
                .collect(),
            type_chart: chart,
            prior: vec![None; 4],
            set_prior: true,
        }
    }

    fn state(own_moves: [u8; 4], foe_types: (Option<u8>, Option<u8>)) -> ObservableState {
        let mut st = ObservableState::default();
        for (i, id) in own_moves.into_iter().enumerate() {
            st.own.moves[i] = MoveView { id, present: id != 0, ..Default::default() };
        }
        st.own.active_slot = Some(0);
        for i in 0..6 {
            st.own.team[i] = MonView {
                present: true,
                species: 1,
                is_active: i == 0,
                // Bench types: slot 1 resists nothing, slot 2 is immune to
                // type 1, slot 3 takes 0.5x.
                type_1: Some(match i { 2 => 4, 3 => 3, _ => 0 }),
                type_2: None,
                ..Default::default()
            };
        }
        st.opp.active_slot = Some(0);
        st.opp.team[0] = MonView {
            present: true,
            species: 2,
            is_active: true,
            type_1: foe_types.0,
            type_2: foe_types.1,
            ..Default::default()
        };
        st
    }

    fn mask(actions: &[usize]) -> [bool; N_ACTIONS] {
        let mut m = [false; N_ACTIONS];
        for &a in actions {
            m[a] = true;
        }
        m
    }

    #[test]
    fn max_power_never_switches_and_breaks_ties_on_the_lowest_slot() {
        let t = tables();
        // Slots: 40, 90, 90, 0 base power. `max()` keeps the FIRST maximum,
        // which is poke-env's tie rule -- slot 1, not slot 2.
        let st = state([1, 2, 3, 4], (Some(3), None));
        let mut rng = 1;
        let m = mask(&[1, 2, 6, 7, 8, 9]);
        for _ in 0..20 {
            assert_eq!(Scripted::MaxPower.act(&st, &m, &t, &mut rng), 7);
        }
        // With no move legal it falls back to a random switch, never a Default.
        let sw = mask(&[1, 2, 3]);
        for _ in 0..50 {
            let a = Scripted::MaxPower.act(&st, &sw, &t, &mut rng);
            assert!((1..=3).contains(&a), "{a}");
        }
    }

    #[test]
    fn most_damage_typed_multiplies_base_power_by_effectiveness() {
        let t = tables();
        // Foe is type 3: type-1 moves x2, type-2 moves x0.5.
        // slot 0 = move 1 (bp 40, type 1) -> 80
        // slot 1 = move 2 (bp 90, type 1) -> 180   <- best
        // slot 2 = move 3 (bp 90, type 2) -> 45
        // slot 3 = move 5 (bp 120, type 0) -> 120
        let st = state([1, 2, 3, 5], (Some(3), None));
        let mut rng = 7;
        let m = mask(&[6, 7, 8, 9]);
        for _ in 0..20 {
            assert_eq!(Scripted::MostDamageTyped.act(&st, &m, &t, &mut rng), 7);
        }
        // Against a foe the type-1 moves cannot touch (x0), the neutral 120
        // wins -- the anchor's whole point is that it reads the chart.
        let st0 = state([1, 2, 3, 5], (Some(4), None));
        for _ in 0..20 {
            assert_eq!(Scripted::MostDamageTyped.act(&st0, &m, &t, &mut rng), 9);
        }
    }

    #[test]
    fn most_damage_typed_scores_an_ohko_move_at_the_constant() {
        let t = tables();
        // Move 7 is OHKO with base power 0: it must beat the 120-bp neutral
        // move only when the chart does not lift that one above 120.
        let st = state([7, 6, 0, 0], (Some(0), None));
        let mut rng = 3;
        let m = mask(&[6, 7]);
        for _ in 0..20 {
            assert_eq!(Scripted::MostDamageTyped.act(&st, &m, &t, &mut rng), 6);
        }
        // ...and loses to a 180 after the multiplier, which is H&L's rule and
        // not a special case for OHKO.
        let st2 = state([7, 2, 0, 0], (Some(3), None));
        for _ in 0..20 {
            assert_eq!(Scripted::MostDamageTyped.act(&st2, &m, &t, &mut rng), 7);
        }
    }

    #[test]
    fn a_forced_switch_picks_the_least_weak_bench_member() {
        let t = tables();
        // Foe is type 1. Bench types: slot 1 -> 0 (1.0x), slot 2 -> 4 (0.0x),
        // slot 3 -> 3 (2.0x). Lowest sum wins: slot 2.
        let st = state([1, 0, 0, 0], (Some(1), None));
        let mut rng = 11;
        let m = mask(&[1, 2, 3]);
        for _ in 0..20 {
            assert_eq!(Scripted::MostDamageTyped.act(&st, &m, &t, &mut rng), 2);
        }
    }

    #[test]
    fn random_covers_every_legal_action_and_nothing_else() {
        let t = tables();
        let st = state([1, 2, 3, 4], (Some(3), None));
        let legal = [0usize, 3, 6, 9];
        let m = mask(&legal);
        let mut rng = 5;
        let mut seen = [0usize; N_ACTIONS];
        for _ in 0..4000 {
            seen[Scripted::Random.act(&st, &m, &t, &mut rng)] += 1;
        }
        for a in 0..N_ACTIONS {
            if legal.contains(&a) {
                assert!(seen[a] > 700, "action {a} drawn {} times", seen[a]);
            } else {
                assert_eq!(seen[a], 0, "illegal action {a} was drawn");
            }
        }
    }
}

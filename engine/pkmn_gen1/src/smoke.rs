//! Gate B-1: the random-policy loop smoke (plan §9).
//!
//! Engine-only, no server, no encoder. It exercises exactly the contract the
//! wrapper is responsible for: drive the request state machine to the end of a
//! battle, never submit a choice the engine did not offer, and land on one of
//! the three showdown-mode terminal outcomes inside the 1000-turn bound.

use crate::battle::{Battle, BattleResult, Choice, Outcome, Player, Request, splitmix64};
use crate::team::{PokemonSet, random_team};

/// What B-1 records. Everything here is descriptive; the gate is the absence of
/// panics, `Error` outcomes and over-length battles.
#[derive(Clone, Debug, Default)]
pub struct SmokeStats {
    pub battles: u64,
    pub p1_wins: u64,
    pub p2_wins: u64,
    pub ties: u64,
    pub updates: u64,
    pub decisions: u64,
    /// Updates where at least one seat was replacing a fainted mon.
    pub switch_requests: u64,
    /// Decisions where the engine offered exactly one choice (forced / recharge /
    /// locked / no legal switch).
    pub forced_decisions: u64,
    pub turns_total: u64,
    pub max_turns: u16,
    pub min_turns: u16,
    /// Battles that ended on the 1000-turn / Endless Battle Clause tie.
    pub long_ties: u64,
}

impl SmokeStats {
    pub fn mean_turns(&self) -> f64 {
        if self.battles == 0 {
            0.0
        } else {
            self.turns_total as f64 / self.battles as f64
        }
    }
    pub fn tie_rate(&self) -> f64 {
        if self.battles == 0 {
            0.0
        } else {
            self.ties as f64 / self.battles as f64
        }
    }
    pub fn p1_win_rate(&self) -> f64 {
        if self.battles == 0 {
            0.0
        } else {
            self.p1_wins as f64 / self.battles as f64
        }
    }
    pub fn mean_updates(&self) -> f64 {
        if self.battles == 0 {
            0.0
        } else {
            self.updates as f64 / self.battles as f64
        }
    }
}

/// The showdown-mode turn ceiling: `mechanics.zig::endTurn` ties at 1000.
pub const MAX_TURNS: u16 = 1000;
/// A battle needs several updates per turn (mid-turn faint replacements), but
/// never unboundedly many. Generous, and a wedged wrapper trips it.
const MAX_UPDATES: u64 = 8 * MAX_TURNS as u64;

fn to_bytes(team: &[PokemonSet]) -> Vec<[u8; crate::layout::POKEMON_SIZE]> {
    team.iter().map(|m| m.to_bytes()).collect()
}

/// Plays one battle with a uniform-random policy on both seats.
/// Returns the result and the number of updates it took.
pub fn play_random(seed: u64, block: bool, stats: &mut SmokeStats) -> Result<(), String> {
    let p1 = to_bytes(&random_team(splitmix64(seed ^ 0xA1), block));
    let p2 = to_bytes(&random_team(splitmix64(seed ^ 0xB2), block));
    let mut battle = Battle::new(splitmix64(seed), &p1, &p2);

    let mut rng = seed;
    let mut next = move || {
        rng = splitmix64(rng);
        rng
    };

    // Turn 0: (Pass, Pass) switches both leads in.
    let mut r: BattleResult = battle
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .map_err(|e| e.to_string())?;
    let mut updates = 1u64;

    while !r.over() {
        if updates > MAX_UPDATES {
            return Err(format!(
                "battle seed {seed:#x} exceeded {MAX_UPDATES} updates at turn {} -- \
                 the wrapper is not driving the request state machine to an end",
                battle.turn()
            ));
        }
        if battle.turn() > MAX_TURNS {
            return Err(format!(
                "battle seed {seed:#x} passed turn {MAX_TURNS} without a terminal \
                 result; showdown mode must tie at {MAX_TURNS}"
            ));
        }
        let mut picked = [Choice::Pass; 2];
        for (i, p) in [Player::P1, Player::P2].iter().enumerate() {
            let req = r.request(*p);
            let cs = battle.choices(*p, req);
            if cs.is_empty() {
                return Err(format!(
                    "engine offered no choices to {p:?} under {req:?} at turn {}; \
                     showdown mode guarantees >= 1",
                    battle.turn()
                ));
            }
            if req != Request::Pass {
                stats.decisions += 1;
                if cs.len() == 1 {
                    stats.forced_decisions += 1;
                }
            }
            if req == Request::Switch {
                stats.switch_requests += 1;
            }
            picked[i] = cs.get((next() % cs.len() as u64) as usize);
        }
        r = battle
            .update(r.p1, picked[0], r.p2, picked[1])
            .map_err(|e| e.to_string())?;
        updates += 1;
    }

    let turns = battle.turn();
    stats.battles += 1;
    stats.updates += updates;
    stats.turns_total += turns as u64;
    stats.max_turns = stats.max_turns.max(turns);
    stats.min_turns = if stats.battles == 1 {
        turns
    } else {
        stats.min_turns.min(turns)
    };
    match r.outcome {
        Outcome::Win => stats.p1_wins += 1,
        Outcome::Lose => stats.p2_wins += 1,
        Outcome::Tie => {
            stats.ties += 1;
            if turns >= MAX_TURNS {
                stats.long_ties += 1;
            }
        }
        Outcome::None => return Err("loop exited with a non-terminal result".into()),
        Outcome::Error => {
            return Err(format!(
                "engine returned Error, unreachable in showdown mode; state: {battle:?}"
            ));
        }
    }
    Ok(())
}

/// B-1 proper: `n` independent random-policy battles from `seed`.
pub fn random_battles(n: u64, seed: u64, block: bool) -> Result<SmokeStats, String> {
    let mut stats = SmokeStats::default();
    for i in 0..n {
        play_random(splitmix64(seed.wrapping_add(i)), block, &mut stats)?;
    }
    Ok(stats)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_small_random_batch_completes_cleanly() {
        // The full 10,000-battle gate runs from scripts/engine_parity.py b1 in a
        // release build; this keeps `cargo test` fast while still covering the loop.
        let s = random_battles(200, 0xB1B1_0001, true).unwrap();
        assert_eq!(s.battles, 200);
        assert_eq!(s.p1_wins + s.p2_wins + s.ties, 200);
        assert!(s.max_turns <= MAX_TURNS);
        assert!(s.min_turns >= 1);
        assert!(s.decisions > 0 && s.updates > s.battles);
    }

    #[test]
    fn unblocked_movesets_also_complete() {
        // Mimic / Metronome / Mirror Move / Transform are what the engine's own
        // random helper excludes in showdown mode. Real randbats teams contain
        // Mimic and Transform, so the wrapper must survive them.
        let s = random_battles(200, 0xB1B1_0002, false).unwrap();
        assert_eq!(s.battles, 200);
        assert_eq!(s.p1_wins + s.p2_wins + s.ties, 200);
    }

    #[test]
    fn the_same_seed_replays_the_same_battle() {
        let a = random_battles(20, 42, true).unwrap();
        let b = random_battles(20, 42, true).unwrap();
        assert_eq!(a.p1_wins, b.p1_wins);
        assert_eq!(a.turns_total, b.turns_total);
        assert_eq!(a.updates, b.updates);
    }
}

//! Invariant I1, enforced rather than asserted (plan §7.1, §10 "Hidden-
//! information leak").
//!
//! The claim is that the observation is a function of what a Showdown client
//! could see, never of the engine's hidden state. A comment cannot enforce that
//! and a code review will not catch it a year from now, so this audit does it by
//! PERTURBATION: for every field of the 384-byte layout, flip it in a live
//! battle, re-derive the seat's 828-float observation from the SAME tracker, and
//! check the result against the field's declared visibility class.
//!
//!   HIDDEN  -> the observation must be bit-identical. A difference is a leak.
//!   VISIBLE -> the observation must differ. This is the positive control: it is
//!              what stops the audit passing because the harness is inert.
//!
//! The tracker is held fixed across a perturbation on purpose. Everything it
//! carries (reveal order, revealed moves, observed sleep turns) is derived from
//! HISTORY, so the question this asks is exactly the right one: does the encoder
//! read the hidden byte DIRECTLY?

use pkmn_gen1::battle::{Battle, Choice, Player, Request};
use pkmn_gen1::encoder::{OBS_DIM, encode};
use pkmn_gen1::layout::*;
use pkmn_gen1::tables::{
    MoveEntry, N_TYPES, SpeciesEntry, SpeciesPrior, StaticTables,
};
use pkmn_gen1::team::PokemonSet;
use pkmn_gen1::track::BattleTracker;
use std::collections::HashSet;

/// A synthetic but well-spread table. The audit is about which BYTES reach the
/// output, not about the table's own values, so anything injective will do --
/// but every species must differ from every other or a leak could hide behind
/// two species that encode identically.
fn tables() -> StaticTables {
    let species = (0..152u32)
        .map(|i| SpeciesEntry {
            base_stats: std::array::from_fn(|k| (10 + (i * 7 + k as u32 * 31) % 240) as u16),
            type_1: if i == 0 { None } else { Some((i % N_TYPES as u32) as u8) },
            type_2: if i == 0 || i % 3 == 0 {
                None
            } else {
                Some(((i / 2) % N_TYPES as u32) as u8)
            },
        })
        .collect();
    let moves = (0..166u32)
        .map(|i| MoveEntry {
            base_power: (i * 3 % 150) as u16,
            accuracy: 0.5 + (i % 5) as f32 / 10.0,
            max_pp: if i == 0 { 0 } else { 8 + (i % 7) as u16 * 8 },
            priority: (i % 3) as i16 - 1,
            physical: i % 2 == 0,
            status: i % 5 == 0,
            move_type: if i == 0 { None } else { Some((i % N_TYPES as u32) as u8) },
            effect: std::array::from_fn(|k| ((i as usize * 13 + k) % 17) as f32 / 17.0),
        })
        .collect();
    let mut type_chart = [[1.0f64; N_TYPES]; N_TYPES];
    for d in 0..N_TYPES {
        for a in 0..N_TYPES {
            type_chart[d][a] = [0.0, 0.5, 1.0, 2.0][(d * 7 + a * 3) % 4];
        }
    }
    // A LIVE prior on every species. With `prior: None` everywhere, the
    // opponent's prior-filled move slots -- 188 of the 828 columns -- are
    // structurally zero for the whole audit, and a leak into them could not
    // move anything.
    let prior = (0..152usize)
        .map(|i| {
            if i == 0 {
                return None;
            }
            let ids: Vec<u8> = (0..5).map(|k| (1 + (i * 7 + k * 29) % 165) as u8).collect();
            let mut ids2 = ids.clone();
            ids2.sort_unstable();
            ids2.dedup();
            // Draws with distinct marginals so the ordering is not a tie.
            let draws: Vec<Vec<u8>> = (0..40)
                .map(|r| (0..ids2.len() as u8).filter(|&j| (r + j as usize) % (2 + j as usize) == 0).collect())
                .collect();
            Some(SpeciesPrior::new(ids2, &draws))
        })
        .collect();
    StaticTables {
        species,
        moves,
        type_chart,
        prior,
        set_prior: true,
    }
}

fn team(base: u8) -> Vec<[u8; POKEMON_SIZE]> {
    (0..6)
        .map(|i| PokemonSet::new(base + i, 80 + i, [1 + i, 20 + i, 40 + i, 60 + i]).to_bytes())
        .collect()
}

/// Plays far enough in that both sides have switched, used moves and taken
/// damage -- so hidden counters hold non-trivial values -- but stops while each
/// side still has an UNREVEALED party member, because two cases depend on one
/// existing. Fixing a step count instead would make those cases silently vanish
/// the first time a battle happened to reveal a whole team.
fn played() -> (Battle, BattleTracker, Request, Request) {
    let (p1, p2) = (team(1), team(40));
    let mut b = Battle::new(0x5EED_1234_5678_9ABC, &p1, &p2);
    let mut tr = BattleTracker::default();
    let mut r = b
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    tr.observe(&b);
    let mut rng = 0x1234_5678u64;
    for step in 0..24 {
        if r.over() {
            break;
        }
        let mut pick = [Choice::Pass; 2];
        for (i, p) in [Player::P1, Player::P2].iter().enumerate() {
            let cs = b.choices(*p, r.request(*p));
            // Force an early switch on each side so more than one mon is revealed.
            let want_switch = step == 3;
            pick[i] = if want_switch {
                cs.iter()
                    .find(|c| matches!(c, Choice::Switch(_)))
                    .unwrap_or(cs.get(0))
            } else {
                rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                cs.get(((rng >> 33) as usize) % cs.len())
            };
        }
        r = b.update(r.p1, pick[0], r.p2, pick[1]).unwrap();
        tr.observe(&b);
        let spare = |p: Player| (0..6).filter(|&i| !tr.side(p).is_revealed(i)).count();
        if step >= 8 && (spare(Player::P1) < 2 || spare(Player::P2) < 2) {
            break;
        }
    }
    (b, tr, r.p1, r.p2)
}

fn obs(b: &Battle, tr: &BattleTracker, seat: Player, req: Request, t: &StaticTables) -> Vec<f32> {
    let mut v = vec![0.0f32; OBS_DIM];
    encode(&mut v, t, &tr.state_for(b, seat, req, t));
    v
}

fn differs(a: &[f32], c: &[f32]) -> bool {
    a.iter().zip(c).any(|(x, y)| x.to_bits() != y.to_bits())
}

/// `Battle` byte offsets for one side's active / stored records.
fn side_at(p: Player) -> usize {
    B_SIDES + p.index() * SIDE_SIZE
}
fn active_at(p: Player) -> usize {
    side_at(p) + S_ACTIVE
}
fn party_at(p: Player, i: usize) -> usize {
    side_at(p) + S_POKEMON + i * POKEMON_SIZE
}


fn set_volatile_field(b: &mut Battle, p: Player, off: u32, width: u32, value: u64) {
    let at = active_at(p) + A_VOLATILES;
    let mut w = [0u8; 8];
    w.copy_from_slice(&b.0[at..at + 8]);
    let mut v = u64::from_le_bytes(w);
    let mask = ((1u64 << width) - 1) << off;
    v = (v & !mask) | ((value << off) & mask);
    b.0[at..at + 8].copy_from_slice(&v.to_le_bytes());
}

fn flag(b: &mut Battle, p: Player, bit: u32, on: bool) {
    set_volatile_field(b, p, bit, 1, on as u64);
}

/// The first foe party slot the observer has NOT seen. `None` once all six are
/// revealed, in which case the unrevealed-mon cases have nothing to say.
fn unrevealed(tr: &BattleTracker, observer: Player) -> Option<usize> {
    (0..6).find(|&i| !tr.side(observer.foe()).is_revealed(i))
}

struct Case {
    name: &'static str,
    hidden: bool,
    /// Applied to BOTH sides of the comparison. A hidden COUNTER usually lives
    /// behind a visible FLAG (confusion turns behind the confusion bit, sleep
    /// turns behind the SLP bits, Bide damage behind the Bide bit), and mutating
    /// the counter alone is only a clean test once the flag is set in both
    /// states. Without this the audit reports the flag as a leak -- which is
    /// what it did on its first run -- or, worse, passes vacuously because the
    /// producer only reads the counter when the flag is on.
    prepare: fn(&mut Battle, Player, &BattleTracker),
    /// Applied to ONE side: the field under test.
    mutate: fn(&mut Battle, Player, &BattleTracker),
}

fn nop(_: &mut Battle, _: Player, _: &BattleTracker) {}

/// Every field of the layout, with the visibility class plan §7.1 assigns it.
/// `p` is the seat DOING the observing; each mutation targets whichever side
/// makes the field's class interesting.
fn cases() -> Vec<Case> {
    vec![
        // ---- battle header (7 of 7 fields) ---------------------------------
        Case { name: "turn", hidden: false, prepare: nop, mutate: |b, _, _| {
            // Small, and downward: `vec[0] = min(turn/50, 1)` saturates at turn
            // 50, so a large or upward nudge would silently stop being a control.
            let t = u16::from_le_bytes([b.0[B_TURN], b.0[B_TURN + 1]]);
            b.0[B_TURN..B_TURN + 2].copy_from_slice(&(t / 2 + 1).to_le_bytes());
        }},
        Case { name: "last_damage", hidden: true, prepare: nop, mutate: |b, _, _| {
            b.0[B_LAST_DAMAGE..B_LAST_DAMAGE + 2].copy_from_slice(&123u16.to_le_bytes());
        }},
        Case { name: "last_moves (all 4 showdown bytes)", hidden: true, prepare: nop, mutate: |b, _, _| {
            for k in 0..LAST_MOVES_WIDTH { b.0[B_LAST_MOVES + k] ^= 0x0F; }
        }},
        Case { name: "rng seed", hidden: true, prepare: nop, mutate: |b, _, _| {
            for k in 0..8 { b.0[B_RNG + k] ^= 0xA5; }
        }},

        // ---- Side: order, last_selected_move, last_used_move ---------------
        Case { name: "foe order[] back-row arrangement", hidden: true, prepare: nop, mutate: |b, p, _| {
            // A permutation of the BENCH only: slot 0 selects the active, so it
            // is left alone. The foe's live bench order is not visible.
            let at = side_at(p.foe()) + S_ORDER;
            b.0.swap(at + 3, at + 4);
        }},
        Case { name: "own last_selected_move", hidden: true, prepare: nop, mutate: |b, p, _| {
            b.0[side_at(p) + S_LAST_SELECTED_MOVE] ^= 0x3F;
        }},
        Case { name: "own last_used_move", hidden: true, prepare: nop, mutate: |b, p, _| {
            b.0[side_at(p) + S_LAST_USED_MOVE] ^= 0x3F;
        }},
        Case { name: "foe last_selected_move", hidden: true, prepare: nop, mutate: |b, p, _| {
            b.0[side_at(p.foe()) + S_LAST_SELECTED_MOVE] ^= 0x3F;
        }},
        Case { name: "foe last_used_move", hidden: true, prepare: nop, mutate: |b, p, _| {
            b.0[side_at(p.foe()) + S_LAST_USED_MOVE] ^= 0x3F;
        }},

        // ---- move IDs. The single most valuable hidden quantity in gen 1: an
        //      implementation that reads the foe's engine move slots while
        //      correctly forcing pp = max_pp leaks all four of its moves and no
        //      PP case can see it.
        Case { name: "foe LIVE move ids", hidden: true, prepare: nop, mutate: |b, p, _| {
            let at = active_at(p.foe()) + A_MOVES;
            for k in 0..4 { b.0[at + 2 * k] = 40 + k as u8; }
        }},
        Case { name: "foe STORED move ids", hidden: true, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i) + P_MOVES;
            for k in 0..4 { b.0[at + 2 * k] = 60 + k as u8; }
        }},
        Case { name: "own LIVE move ids", hidden: false, prepare: nop, mutate: |b, p, _| {
            let at = active_at(p) + A_MOVES;
            b.0[at] = if b.0[at] == 80 { 81 } else { 80 };
        }},

        // ---- PP ------------------------------------------------------------
        Case { name: "own live move PP", hidden: false,
            // Two guards: an aliased turn ZEROES the own-move blocks, and the
            // .max(1) idiom no-ops at 1 PP. Set a known value in both states and
            // move it, so the control cannot quietly go inert.
            prepare: |b, p, _| { b.0[active_at(p) + A_MOVES + 1] = 9; },
            mutate: |b, p, _| { b.0[active_at(p) + A_MOVES + 1] = 4; },
        },
        Case { name: "foe live move PP", hidden: true,
            prepare: |b, p, _| { b.0[active_at(p.foe()) + A_MOVES + 1] = 9; },
            mutate: |b, p, _| { b.0[active_at(p.foe()) + A_MOVES + 1] = 4; },
        },
        Case { name: "foe stored move PP", hidden: true,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_MOVES + 1] = 9;
            },
            mutate: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_MOVES + 1] = 4;
            },
        },

        // ---- computed stats. The encoder must read the species TABLE, never
        //      the engine's own stat block; the foe's real stats are hidden.
        Case { name: "foe active spe stat", hidden: true, prepare: nop, mutate: |b, p, _| {
            let at = active_at(p.foe()) + A_STATS + ST_SPE;
            b.0[at..at + 2].copy_from_slice(&399u16.to_le_bytes());
        }},
        Case { name: "foe stored atk stat", hidden: true, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i) + P_STATS + ST_ATK;
            b.0[at..at + 2].copy_from_slice(&377u16.to_le_bytes());
        }},
        Case { name: "own stored atk stat", hidden: true, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p).active_party_index();
            let at = party_at(p, i) + P_STATS + ST_ATK;
            b.0[at..at + 2].copy_from_slice(&366u16.to_le_bytes());
        }},

        // ---- HP -------------------------------------------------------------
        Case { name: "own active HP (exact)", hidden: false, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p).active_party_index();
            let at = party_at(p, i) + P_HP;
            let hp = u16::from_le_bytes([b.0[at], b.0[at + 1]]);
            b.0[at..at + 2].copy_from_slice(&(hp / 2).max(1).to_le_bytes());
        }},
        // A KNOWN pair rather than a search: at full HP no same-bucket
        // alternative exists, so a search-based version silently tests nothing
        // whenever the foe happens to be undamaged. 250/400 and 249/400 are both
        // ceil(62.5) = ceil(62.25) = 63%.
        Case { name: "foe exact HP INSIDE one percent bucket", hidden: true,
            prepare: |b, p, _| set_foe_hp(b, p, 250, 400),
            mutate: |b, p, _| set_foe_hp(b, p, 249, 400),
        },
        Case { name: "foe HP ACROSS a percent bucket", hidden: false, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i);
            let max = u16::from_le_bytes([b.0[at + P_STATS], b.0[at + P_STATS + 1]]);
            b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&(max / 3).max(1).to_le_bytes());
        }},
        // The foe's max HP is a HIDDEN byte whose QUOTIENT is visible, so the
        // honest pair of tests is: moving it alone changes the percentage
        // (visible), and moving hp and max TOGETHER so the percentage is
        // preserved must change nothing (hidden).
        Case { name: "foe max HP alone (changes the percentage)", hidden: false, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i);
            let max = u16::from_le_bytes([b.0[at + P_STATS], b.0[at + P_STATS + 1]]);
            let hp = u16::from_le_bytes([b.0[at + P_HP], b.0[at + P_HP + 1]]);
            if hp == 0 { return; }
            let mut alt = max;
            for cand in (hp.max(1)..1000).rev() {
                if pkmn_gen1::track::health_percent(hp, cand)
                    != pkmn_gen1::track::health_percent(hp, max)
                {
                    alt = cand;
                    break;
                }
            }
            b.0[at + P_STATS..at + P_STATS + 2].copy_from_slice(&alt.to_le_bytes());
        }},
        Case { name: "foe hp AND max scaled, percentage preserved", hidden: true,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i);
                b.0[at + P_STATS..at + P_STATS + 2].copy_from_slice(&400u16.to_le_bytes());
                b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&200u16.to_le_bytes());
            },
            mutate: |b, p, _| {
                // 100/200 is the same 50% as 200/400.
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i);
                b.0[at + P_STATS..at + P_STATS + 2].copy_from_slice(&200u16.to_le_bytes());
                b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&100u16.to_le_bytes());
            },
        },

        // ---- an UNREVEALED foe party member: nothing about it may show ------
        Case { name: "foe UNREVEALED member species/level/status", hidden: true, prepare: nop, mutate: |b, p, tr| {
            let Some(i) = unrevealed(tr, p) else { return };
            let at = party_at(p.foe(), i);
            b.0[at + P_SPECIES] = 99;
            b.0[at + P_LEVEL] = 55;
            b.0[at + P_STATUS] = 0b0100_0000;
        }},
        Case { name: "foe UNREVEALED member fainting", hidden: true, prepare: nop, mutate: |b, p, tr| {
            // `fainted_count` is a REVEALED-only count. An implementation that
            // walks all six party slots leaks the foe's true faint count.
            let Some(i) = unrevealed(tr, p) else { return };
            b.0[party_at(p.foe(), i) + P_HP..][..2].copy_from_slice(&0u16.to_le_bytes());
        }},

        // ---- a REVEALED foe's visible identity ------------------------------
        Case { name: "foe revealed species (stored)", hidden: false, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            b.0[party_at(p.foe(), i) + P_SPECIES] = 77;
        }},
        Case { name: "foe revealed level", hidden: false, prepare: nop, mutate: |b, p, _| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i) + P_LEVEL;
            b.0[at] = if b.0[at] == 61 { 62 } else { 61 };
        }},
        Case { name: "foe revealed status (PAR)", hidden: false,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0;
            },
            mutate: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0b0100_0000;
            },
        },
        Case { name: "foe active species (transform identity)", hidden: false, prepare: nop, mutate: |b, p, _| {
            b.0[active_at(p.foe()) + A_SPECIES] = 150;
        }},

        // ---- sleep: the remaining count is hidden, the SLP bit is not -------
        Case { name: "own sleep turns REMAINING", hidden: true,
            prepare: |b, p, _| {
                let i = b.side(p).active_party_index();
                let at = party_at(p, i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b101;
            },
            mutate: |b, p, _| {
                let i = b.side(p).active_party_index();
                let at = party_at(p, i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b010;
            },
        },
        Case { name: "foe sleep turns REMAINING", hidden: true,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b101;
            },
            mutate: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b010;
            },
        },
        Case { name: "foe EXT bit (self-inflicted sleep marker)", hidden: true,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0b0000_0011;
            },
            mutate: |b, p, _| {
                // Rest-sleep vs natural sleep: same SLP status to a client.
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0b1000_0011;
            },
        },

        // ---- volatile FLAGS that reach the observation ----------------------
        Case { name: "foe Substitute PRESENCE", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_SUBSTITUTE, true) },
        Case { name: "foe Reflect", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_REFLECT, true) },
        Case { name: "foe Leech Seed", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_LEECH_SEED, true) },
        Case { name: "foe Confusion", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_CONFUSION, true) },
        Case { name: "foe Focus Energy", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_FOCUS_ENERGY, true) },
        Case { name: "foe Recharging", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_RECHARGING, true) },
        Case { name: "foe Charging (preparing)", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_CHARGING, true) },
        // PARTIALLY_TRAPPED is the VICTIM's slot fed by the USER's bit, so both
        // sides' Binding reach the observation -- through OPPOSITE slots. This
        // is the trickiest read in track.rs and previously had no case at all.
        Case { name: "foe Binding -> our PARTIALLY_TRAPPED", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_BINDING, true) },
        Case { name: "own Binding -> foe's PARTIALLY_TRAPPED", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p, V_BINDING, true) },
        // Thrash/Rage reach the observation ONLY through our own `trapped`
        // flag, so the same bit is visible on our side and hidden on the foe's.
        Case { name: "own Thrashing (own trapped)", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p, V_THRASHING, true) },
        Case { name: "foe Thrashing (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_THRASHING, true) },
        Case { name: "own Rage (own trapped)", hidden: false, prepare: nop,
            mutate: |b, p, _| flag(b, p, V_RAGE, true) },
        Case { name: "foe Rage (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_RAGE, true) },

        // ---- volatile FLAGS with NO encoder slot: must stay out -------------
        Case { name: "foe Light Screen (no encoder slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_LIGHT_SCREEN, true) },
        Case { name: "foe Bide flag (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_BIDE, true) },
        Case { name: "foe Mist (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_MIST, true) },
        Case { name: "foe MultiHit (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_MULTI_HIT, true) },
        Case { name: "foe Flinch (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_FLINCH, true) },
        Case { name: "foe Invulnerable (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_INVULNERABLE, true) },
        Case { name: "foe Transform flag (no slot)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_TRANSFORM, true) },
        // The TOXIC VOLATILE is not the TOX status. track.rs reads the status
        // byte; switching it to this bit would be wrong (the volatile is lost on
        // switch, data.zig), so the bit itself must reach nothing.
        Case { name: "foe Toxic VOLATILE bit (not the TOX status)", hidden: true, prepare: nop,
            mutate: |b, p, _| flag(b, p.foe(), V_TOXIC, true) },

        // ---- packed volatile COUNTERS, each behind its gating flag ----------
        Case { name: "foe confusion turns", hidden: true,
            prepare: |b, p, _| {
                flag(b, p.foe(), V_CONFUSION, true);
                set_volatile_field(b, p.foe(), V_CONFUSION_TURNS, 3, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_CONFUSION_TURNS, 3, 4),
        },
        Case { name: "foe attacks-left counter", hidden: true,
            prepare: |b, p, _| {
                flag(b, p.foe(), V_THRASHING, true);
                set_volatile_field(b, p.foe(), V_ATTACKS, 3, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_ATTACKS, 3, 3),
        },
        Case { name: "foe Bide damage (state)", hidden: true,
            prepare: |b, p, _| {
                flag(b, p.foe(), V_BIDE, true);
                set_volatile_field(b, p.foe(), V_STATE, 16, 11);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_STATE, 16, 4321),
        },
        Case { name: "foe Substitute HP", hidden: true,
            prepare: |b, p, _| {
                flag(b, p.foe(), V_SUBSTITUTE, true);
                set_volatile_field(b, p.foe(), V_SUBSTITUTE_HP, 8, 20);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_SUBSTITUTE_HP, 8, 77),
        },
        Case { name: "foe Disable duration", hidden: true,
            prepare: |b, p, _| {
                set_volatile_field(b, p.foe(), V_DISABLE_MOVE, 3, 2);
                set_volatile_field(b, p.foe(), V_DISABLE_DURATION, 4, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_DISABLE_DURATION, 4, 5),
        },
        Case { name: "foe Disable slot", hidden: true,
            prepare: |b, p, _| {
                set_volatile_field(b, p.foe(), V_DISABLE_DURATION, 4, 4);
                set_volatile_field(b, p.foe(), V_DISABLE_MOVE, 3, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_DISABLE_MOVE, 3, 3),
        },
        Case { name: "foe Transform target id", hidden: true,
            prepare: |b, p, _| {
                flag(b, p.foe(), V_TRANSFORM, true);
                set_volatile_field(b, p.foe(), V_TRANSFORM_ID, 4, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_TRANSFORM_ID, 4, 4),
        },
        // The TOXIC COUNTER is visible -- one damage message per turn -- and is
        // poke-env's TOX status_counter.
        Case { name: "foe toxic counter", hidden: false,
            prepare: |b, p, _| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0b1000_1000; // TOX
                set_volatile_field(b, p.foe(), V_TOXIC_TURNS, 5, 1);
            },
            mutate: |b, p, _| set_volatile_field(b, p.foe(), V_TOXIC_TURNS, 5, 6),
        },

        // ---- boosts: every one of the six, not just atk ---------------------
        Case { name: "foe atk boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_ATK) },
        Case { name: "foe def boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_DEF) },
        Case { name: "foe spe boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_SPE) },
        Case { name: "foe spc boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_SPC) },
        Case { name: "foe accuracy boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_ACCURACY) },
        Case { name: "foe evasion boost", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p.foe(), BO_EVASION) },
        Case { name: "own spe boost (feeds the speed edge)", hidden: false, prepare: nop,
            mutate: |b, p, _| set_volatile_boost(b, p, BO_SPE) },
    ]
}

/// Sets the foe active's current and max HP.
fn set_foe_hp(b: &mut Battle, p: Player, hp: u16, max: u16) {
    let i = b.side(p.foe()).active_party_index();
    let at = party_at(p.foe(), i);
    b.0[at + P_STATS..at + P_STATS + 2].copy_from_slice(&max.to_le_bytes());
    b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&hp.to_le_bytes());
}

/// Writes +2 into one packed i4 boost field.
fn set_volatile_boost(b: &mut Battle, p: Player, off: u32) {
    let at = active_at(p) + A_BOOSTS;
    let mut w = [0u8; 4];
    w.copy_from_slice(&b.0[at..at + 4]);
    let mut v = u32::from_le_bytes(w);
    let mask = 0xFu32 << off;
    v = (v & !mask) | ((2u32 << off) & mask);
    b.0[at..at + 4].copy_from_slice(&v.to_le_bytes());
}

#[derive(Default)]
struct Report {
    leaks: Vec<String>,
    inert: Vec<String>,
    fired: HashSet<&'static str>,
    checked: usize,
}

/// The audit's engine. Separated from the case list so a deliberately
/// MISLABELLED list can be run through the identical code path -- otherwise
/// swapping the two classification arms leaves every test green (both buckets
/// are empty in a passing run, so an inverted classifier is invisible).
fn run(cases: &[Case], b: &Battle, tr: &BattleTracker, r1: Request, r2: Request, t: &StaticTables) -> Report {
    let mut rep = Report::default();
    for seat in [Player::P1, Player::P2] {
        let req = if seat == Player::P1 { r1 } else { r2 };
        for case in cases {
            let mut before = b.clone();
            (case.prepare)(&mut before, seat, tr);
            let mut m = before.clone();
            (case.mutate)(&mut m, seat, tr);
            if m.0 == before.0 {
                continue; // a no-op in this position; `fired` records the loss
            }
            rep.checked += 1;
            rep.fired.insert(case.name);
            let base = obs(&before, tr, seat, req, t);
            let after = obs(&m, tr, seat, req, t);
            match (case.hidden, differs(&base, &after)) {
                (true, true) => rep.leaks.push(format!("{seat:?}: {}", case.name)),
                (false, false) => rep.inert.push(format!("{seat:?}: {}", case.name)),
                _ => {}
            }
        }
    }
    rep
}

#[test]
fn no_hidden_field_reaches_the_observation() {
    let t = tables();
    let (b, tr, r1, r2) = played();
    for seat in [Player::P1, Player::P2] {
        assert!(
            unrevealed(&tr, seat).is_some(),
            "{seat:?} has seen the whole foe party, so the unrevealed-member \
             cases have nothing to test -- shorten played()"
        );
    }
    let all = cases();
    let rep = run(&all, &b, &tr, r1, r2, &t);

    eprintln!(
        "leak audit: {} cases, {} perturbations across both seats, {} leaks",
        all.len(),
        rep.checked,
        rep.leaks.len()
    );
    // EVERY case must have moved bytes at least once. Without this a case that
    // silently no-ops in the position played() reaches is dead coverage that
    // still looks present in the list.
    let never: Vec<&str> = all
        .iter()
        .map(|c| c.name)
        .filter(|n| !rep.fired.contains(n))
        .collect();
    assert!(
        never.is_empty(),
        "{} case(s) never perturbed anything, so they test nothing: {:#?}",
        never.len(),
        never
    );
    assert!(
        rep.leaks.is_empty(),
        "HIDDEN state reached the observation ({} leak(s)): {:#?}",
        rep.leaks.len(),
        rep.leaks
    );
    assert!(
        rep.inert.is_empty(),
        "VISIBLE state did NOT reach the observation ({} inert control(s)), so the \
         audit may be passing because the harness is dead: {:#?}",
        rep.inert.len(),
        rep.inert
    );
}

#[test]
fn the_classifier_reports_both_arms() {
    // A passing audit leaves both buckets empty, so an inverted or broken
    // classifier is invisible. Run the SAME `run()` over a deliberately
    // mislabelled list and require it to fill each bucket exactly once.
    let t = tables();
    let (b, tr, r1, r2) = played();
    let mislabelled = vec![
        // Genuinely hidden, declared VISIBLE -> must land in `inert`.
        Case { name: "rng seed, mislabelled VISIBLE", hidden: false, prepare: nop,
            mutate: |b, _, _| { for k in 0..8 { b.0[B_RNG + k] ^= 0xA5; } } },
        // Genuinely visible, declared HIDDEN -> must land in `leaks`.
        Case { name: "foe active species, mislabelled HIDDEN", hidden: true, prepare: nop,
            mutate: |b, p, _| { b.0[active_at(p.foe()) + A_SPECIES] = 150; } },
    ];
    let rep = run(&mislabelled, &b, &tr, r1, r2, &t);
    assert_eq!(rep.leaks.len(), 2, "one leak per seat expected: {:?}", rep.leaks);
    assert_eq!(rep.inert.len(), 2, "one inert control per seat expected: {:?}", rep.inert);
    assert!(rep.leaks.iter().all(|s| s.contains("mislabelled HIDDEN")));
    assert!(rep.inert.iter().all(|s| s.contains("mislabelled VISIBLE")));
}

#[test]
fn the_audit_detects_a_one_ulp_leak() {
    // `differs` compares raw bits, so it is 1-ulp sensitive by construction --
    // but "by construction" is an argument, not a test. Leak the foe's hidden
    // exact HP as the SMALLEST possible perturbation of a real lane and confirm
    // the same comparison notices.
    let t = tables();
    let (b, tr, r1, _) = played();
    let seat = Player::P1;
    let leaky = |bat: &Battle| -> Vec<f32> {
        let mut v = obs(bat, &tr, seat, r1, &t);
        let i = bat.side(seat.foe()).active_party_index();
        let hp = bat.side(seat.foe()).party(i).hp();
        // One ulp per HP point: far subtler than overwriting a lane outright.
        v[0] = f32::from_bits(v[0].to_bits() ^ (hp as u32 & 1));
        v
    };
    // 250/400 and 249/400 are the same 63% bucket and opposite parity, so the
    // leaked lane moves by exactly one ulp and nothing else changes.
    let mut before = b.clone();
    set_foe_hp(&mut before, seat, 250, 400);
    let mut m = before.clone();
    set_foe_hp(&mut m, seat, 249, 400);
    assert_eq!(
        pkmn_gen1::track::health_percent(250, 400),
        pkmn_gen1::track::health_percent(249, 400)
    );
    let b = before;
    assert!(
        differs(&leaky(&b), &leaky(&m)),
        "the comparison missed a ONE-ULP leak"
    );
    // And the real encoder does not move for the same perturbation.
    assert!(!differs(&obs(&b, &tr, seat, r1, &t), &obs(&m, &tr, seat, r1, &t)));
}

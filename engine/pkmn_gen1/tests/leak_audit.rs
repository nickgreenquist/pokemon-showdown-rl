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
    MoveEntry, N_TYPES, SpeciesEntry, StaticTables,
};
use pkmn_gen1::team::PokemonSet;
use pkmn_gen1::track::BattleTracker;

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
    StaticTables {
        species,
        moves,
        type_chart,
        prior: (0..152).map(|_| None).collect(),
        set_prior: true,
    }
}

fn team(base: u8) -> Vec<[u8; POKEMON_SIZE]> {
    (0..6)
        .map(|i| PokemonSet::new(base + i, 80 + i, [1 + i, 20 + i, 40 + i, 60 + i]).to_bytes())
        .collect()
}

/// Plays far enough in that both sides have switched, used moves, and taken
/// damage -- so that hidden counters actually hold non-trivial values.
fn played() -> (Battle, BattleTracker, Request, Request) {
    let (p1, p2) = (team(1), team(40));
    let mut b = Battle::new(0x5EED_1234_5678_9ABC, &p1, &p2);
    let mut tr = BattleTracker::default();
    let mut r = b
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    tr.observe(&b);
    let mut rng = 0x1234_5678u64;
    for step in 0..40 {
        if r.over() {
            break;
        }
        let mut pick = [Choice::Pass; 2];
        for (i, p) in [Player::P1, Player::P2].iter().enumerate() {
            let cs = b.choices(*p, r.request(*p));
            // Force an early switch on each side so more than one mon is revealed.
            let want_switch = step == 3 || step == 6;
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

struct Case {
    name: &'static str,
    hidden: bool,
    /// Applied to BOTH sides of the comparison. A hidden COUNTER usually lives
    /// behind a visible FLAG (confusion turns behind the confusion bit, sleep
    /// turns behind the SLP bits), and mutating the counter alone is only a
    /// clean test once the flag is already set in both states. Without this the
    /// audit reports the flag as a leak -- which is exactly what it did on the
    /// first run.
    prepare: fn(&mut Battle, Player),
    /// Applied to ONE side of the comparison: the field under test.
    mutate: fn(&mut Battle, Player),
}

fn nop(_: &mut Battle, _: Player) {}

/// Every field of the layout, with the visibility class plan §7.1 assigns it.
/// `p` is the seat DOING the observing; each mutation targets whichever side
/// makes the field's class interesting (the foe, for anything the foe hides).
fn cases() -> Vec<Case> {
    vec![
        // ---- battle header -------------------------------------------------
        Case { prepare: nop, name: "turn", hidden: false, mutate: |b, _| {
            let t = u16::from_le_bytes([b.0[B_TURN], b.0[B_TURN + 1]]);
            b.0[B_TURN..B_TURN + 2].copy_from_slice(&(t + 7).to_le_bytes());
        }},
        Case { prepare: nop, name: "last_damage", hidden: true, mutate: |b, _| {
            b.0[B_LAST_DAMAGE..B_LAST_DAMAGE + 2].copy_from_slice(&123u16.to_le_bytes());
        }},
        Case { prepare: nop, name: "last_moves (both seats)", hidden: true, mutate: |b, _| {
            for k in 0..LAST_MOVES_WIDTH { b.0[B_LAST_MOVES + k] ^= 0x0F; }
        }},
        Case { prepare: nop, name: "rng seed", hidden: true, mutate: |b, _| {
            for k in 0..8 { b.0[B_RNG + k] ^= 0xA5; }
        }},
        // ---- our own side: all of it is in the request ---------------------
        Case { prepare: nop, name: "own active HP (exact)", hidden: false, mutate: |b, p| {
            let i = b.side(p).active_party_index();
            let at = party_at(p, i) + P_HP;
            let hp = u16::from_le_bytes([b.0[at], b.0[at + 1]]);
            b.0[at..at + 2].copy_from_slice(&(hp.saturating_sub(1).max(1)).to_le_bytes());
        }},
        Case { prepare: nop, name: "own live move PP", hidden: false, mutate: |b, p| {
            let at = active_at(p) + A_MOVES + 1;
            b.0[at] = b.0[at].saturating_sub(1).max(1);
        }},
        Case { prepare: nop, name: "own last_selected_move", hidden: true, mutate: |b, p| {
            b.0[side_at(p) + S_LAST_SELECTED_MOVE] ^= 0x3F;
        }},
        Case { prepare: nop, name: "own last_used_move", hidden: true, mutate: |b, p| {
            b.0[side_at(p) + S_LAST_USED_MOVE] ^= 0x3F;
        }},
        // ---- the foe's hidden interior -------------------------------------
        Case { prepare: nop, name: "foe active PP", hidden: true, mutate: |b, p| {
            let at = active_at(p.foe()) + A_MOVES + 1;
            b.0[at] = b.0[at].saturating_sub(1).max(1);
        }},
        Case { prepare: nop, name: "foe stored move PP", hidden: true, mutate: |b, p| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i) + P_MOVES + 1;
            b.0[at] = b.0[at].saturating_sub(1).max(1);
        }},
        Case { prepare: nop, name: "foe exact HP INSIDE one percent bucket", hidden: true, mutate: |b, p| {
            // The seat learns ceil(100*hp/max) only, so a change that keeps the
            // bucket must be invisible. Pick the largest hp sharing the bucket.
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i);
            let max = u16::from_le_bytes([b.0[at + P_STATS], b.0[at + P_STATS + 1]]);
            let hp = u16::from_le_bytes([b.0[at + P_HP], b.0[at + P_HP + 1]]);
            if hp == 0 || max < 200 { return; }
            let want = pkmn_gen1::track::health_percent(hp, max);
            let mut alt = hp;
            for cand in 1..max {
                if cand != hp && pkmn_gen1::track::health_percent(cand, max) == want {
                    alt = cand;
                    break;
                }
            }
            b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&alt.to_le_bytes());
        }},
        Case { prepare: nop, name: "foe HP ACROSS a percent bucket", hidden: false, mutate: |b, p| {
            let i = b.side(p.foe()).active_party_index();
            let at = party_at(p.foe(), i);
            let max = u16::from_le_bytes([b.0[at + P_STATS], b.0[at + P_STATS + 1]]);
            b.0[at + P_HP..at + P_HP + 2].copy_from_slice(&(max / 3).max(1).to_le_bytes());
        }},
        Case { prepare: nop, name: "foe UNREVEALED party member", hidden: true, mutate: |b, p| {
            // The last slot in party order is the least likely to have appeared;
            // if it has been revealed the case is skipped by the runner.
            let at = party_at(p.foe(), 5);
            b.0[at + P_SPECIES] = 99;
            b.0[at + P_LEVEL] = 55;
            b.0[at + P_STATUS] = 0b0100_0000;
        }},
        // ---- volatile counters: the whole hidden-counter family ------------
        Case { name: "foe confusion turns", hidden: true,
            prepare: |b, p| {
                set_volatile_field(b, p.foe(), V_CONFUSION, 1, 1);
                set_volatile_field(b, p.foe(), V_CONFUSION_TURNS, 3, 1);
            },
            mutate: |b, p| set_volatile_field(b, p.foe(), V_CONFUSION_TURNS, 3, 4),
        },
        Case { prepare: nop, name: "foe attacks-left counter", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_ATTACKS, 3, 2);
        }},
        Case { prepare: nop, name: "foe Bide damage (state)", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_STATE, 16, 4321);
        }},
        Case { name: "foe Substitute HP", hidden: true,
            prepare: |b, p| {
                set_volatile_field(b, p.foe(), V_SUBSTITUTE, 1, 1);
                set_volatile_field(b, p.foe(), V_SUBSTITUTE_HP, 8, 20);
            },
            mutate: |b, p| set_volatile_field(b, p.foe(), V_SUBSTITUTE_HP, 8, 77),
        },
        Case { prepare: nop, name: "foe Disable duration", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_DISABLE_DURATION, 4, 5);
        }},
        Case { prepare: nop, name: "foe Disable slot", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_DISABLE_MOVE, 3, 3);
        }},
        Case { prepare: nop, name: "foe Transform target id", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_TRANSFORM_ID, 4, 4);
        }},
        // Asleep in BOTH states; only the hidden remaining count differs.
        Case { name: "own sleep turns REMAINING", hidden: true,
            prepare: |b, p| {
                let i = b.side(p).active_party_index();
                let at = party_at(p, i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b101;
            },
            mutate: |b, p| {
                let i = b.side(p).active_party_index();
                let at = party_at(p, i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b010;
            },
        },
        Case { name: "foe sleep turns REMAINING", hidden: true,
            prepare: |b, p| {
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b101;
            },
            mutate: |b, p| {
                let i = b.side(p.foe()).active_party_index();
                let at = party_at(p.foe(), i) + P_STATUS;
                b.0[at] = (b.0[at] & !0b111) | 0b010;
            },
        },
        // ---- volatile FLAGS a client can see -------------------------------
        Case { prepare: nop, name: "foe Substitute PRESENCE", hidden: false, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_SUBSTITUTE, 1, 1);
        }},
        Case { prepare: nop, name: "foe Reflect", hidden: false, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_REFLECT, 1, 1);
        }},
        Case { prepare: nop, name: "foe Leech Seed", hidden: false, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_LEECH_SEED, 1, 1);
        }},
        // Badly poisoned in BOTH; only the (VISIBLE) toxic counter differs.
        Case { name: "foe toxic counter", hidden: false,
            prepare: |b, p| {
                let i = b.side(p.foe()).active_party_index();
                b.0[party_at(p.foe(), i) + P_STATUS] = 0b1000_1000; // TOX
                set_volatile_field(b, p.foe(), V_TOXIC_TURNS, 5, 1);
            },
            mutate: |b, p| set_volatile_field(b, p.foe(), V_TOXIC_TURNS, 5, 6),
        },
        Case { prepare: nop, name: "foe boosts", hidden: false, mutate: |b, p| {
            let at = active_at(p.foe()) + A_BOOSTS;
            b.0[at] = b.0[at].wrapping_add(2);
        }},
        Case { prepare: nop, name: "foe active species", hidden: false, mutate: |b, p| {
            b.0[active_at(p.foe()) + A_SPECIES] = 150;
        }},
        // Light Screen has NO encoder slot (poke-env 0.15.0 cannot parse it), so
        // it must not reach the observation even though it is visible on PS.
        Case { prepare: nop, name: "foe Light Screen (no encoder slot)", hidden: true, mutate: |b, p| {
            set_volatile_field(b, p.foe(), V_LIGHT_SCREEN, 1, 1);
        }},
    ]
}

#[test]
fn no_hidden_field_reaches_the_observation() {
    let t = tables();
    let (b, tr, r1, r2) = played();
    let mut leaks = Vec::new();
    let mut inert = Vec::new();
    let mut checked = 0;

    for seat in [Player::P1, Player::P2] {
        let req = if seat == Player::P1 { r1 } else { r2 };
        for case in cases() {
            // The unrevealed-party case is only meaningful while that slot is
            // genuinely unrevealed.
            if case.name.contains("UNREVEALED")
                && tr.side(seat.foe()).is_revealed(5)
            {
                continue;
            }
            let mut before = b.clone();
            (case.prepare)(&mut before, seat);
            let mut m = before.clone();
            (case.mutate)(&mut m, seat);
            if m.0 == before.0 {
                continue; // the mutation was a no-op in this position
            }
            checked += 1;
            let base = obs(&before, &tr, seat, req, &t);
            let after = obs(&m, &tr, seat, req, &t);
            match (case.hidden, differs(&base, &after)) {
                (true, true) => leaks.push(format!("{:?}: {}", seat, case.name)),
                (false, false) => inert.push(format!("{:?}: {}", seat, case.name)),
                _ => {}
            }
        }
    }

    eprintln!("leak audit: {checked} perturbations across both seats, 0 leaks");
    assert!(checked >= 40, "only {checked} perturbations ran; the audit is thin");
    assert!(
        leaks.is_empty(),
        "HIDDEN state reached the observation ({} leak(s)): {:#?}",
        leaks.len(),
        leaks
    );
    assert!(
        inert.is_empty(),
        "VISIBLE state did NOT reach the observation ({} inert control(s)), so the \
         audit above may be passing because the harness is dead: {:#?}",
        inert.len(),
        inert
    );
}

#[test]
fn the_audit_can_actually_fail() {
    // A leak detector that cannot detect a leak is decoration. Encode the foe's
    // HIDDEN exact HP into a spare lane and confirm the same comparison catches
    // it -- this is the audit's own positive control.
    let t = tables();
    let (b, tr, r1, _) = played();
    let seat = Player::P1;
    let leak = |bat: &Battle| -> Vec<f32> {
        let mut v = obs(bat, &tr, seat, r1, &t);
        let i = bat.side(seat.foe()).active_party_index();
        v[0] = bat.side(seat.foe()).party(i).hp() as f32; // the leak
        v
    };
    let mut m = b.clone();
    let i = b.side(seat.foe()).active_party_index();
    let at = party_at(seat.foe(), i);
    let max = u16::from_le_bytes([m.0[at + P_STATS], m.0[at + P_STATS + 1]]);
    let hp = u16::from_le_bytes([m.0[at + P_HP], m.0[at + P_HP + 1]]);
    let mut alt = hp;
    for cand in 1..max {
        if cand != hp && pkmn_gen1::track::health_percent(cand, max) == pkmn_gen1::track::health_percent(hp, max) {
            alt = cand;
            break;
        }
    }
    assert_ne!(alt, hp, "no same-bucket alternative HP exists in this position");
    m.0[at + P_HP..at + P_HP + 2].copy_from_slice(&alt.to_le_bytes());
    assert!(
        differs(&leak(&b), &leak(&m)),
        "the audit's comparison failed to notice a deliberate leak"
    );
    // And the real encoder does NOT move for the same perturbation.
    assert!(!differs(&obs(&b, &tr, seat, r1, &t), &obs(&m, &tr, seat, r1, &t)));
}

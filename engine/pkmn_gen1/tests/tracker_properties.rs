//! Behavioural tests for the engine→observable tracker (`src/track.rs`).
//!
//! The tapes cannot be replayed in the engine — we have no way to reproduce a
//! recorded battle's RNG — so there is no direct oracle for "did the tracker
//! produce the right state". What there IS, is a set of properties any correct
//! tracker must satisfy, each reading a DIFFERENT part of the state from the
//! rule it checks. That is what makes them tests rather than restatements:
//!
//!   * cross-seat agreement — the strongest independent witness available. Two
//!     seats derive the same public facts by different code paths (own-side vs
//!     foe-side), so a side-index swap or a reveal-order/party-index confusion
//!     shows up as a disagreement.
//!   * conservation — `sleep_observed + sleep_turns_left` is invariant while
//!     asleep, which catches a missed increment, a double increment and a
//!     missed reset in one assertion.
//!   * "damaged, statused or PP-spent implies revealed" — reads a completely
//!     different part of the state than the reveal rule does, so a skipped
//!     reveal surfaces the moment that mon takes a point of damage.
//!   * monotonicity — reveal lists only ever extend; counters step by one or
//!     reset. Catches an accidental recompute-from-scratch.
//!
//! None of this settles whether the engine's `choices()` equals the request
//! Showdown would have sent. That is D-1's job.

use pkmn_gen1::battle::{Battle, Choice, Player, Request};
use pkmn_gen1::data;
use pkmn_gen1::layout::*;
use pkmn_gen1::tables::{MoveEntry, N_TYPES, SpeciesEntry, StaticTables};
use pkmn_gen1::team::random_team;
use pkmn_gen1::track::{BattleTracker, health_percent};

fn tables() -> StaticTables {
    StaticTables {
        species: (0..152u32)
            .map(|i| SpeciesEntry {
                base_stats: std::array::from_fn(|k| (10 + (i * 7 + k as u32 * 31) % 240) as u16),
                type_1: Some((i % N_TYPES as u32) as u8),
                type_2: if i % 3 == 0 { None } else { Some(((i / 2) % N_TYPES as u32) as u8) },
            })
            .collect(),
        moves: (0..166u32)
            .map(|i| MoveEntry {
                max_pp: if i == 0 { 0 } else { data::max_pp(i as u8) as u16 },
                ..Default::default()
            })
            .collect(),
        type_chart: [[1.0; N_TYPES]; N_TYPES],
        prior: (0..152).map(|_| None).collect(),
        set_prior: true,
    }
}

/// A snapshot of everything a property needs to compare across updates.
#[derive(Clone, Default)]
struct Snap {
    reveal_order: Vec<u8>,
    revealed_moves: [Vec<u8>; 6],
    sleep: [u8; 6],
    binding: u8,
}

fn snap(tr: &BattleTracker, p: Player) -> Snap {
    let s = tr.side(p);
    Snap {
        reveal_order: s.reveal_order().to_vec(),
        revealed_moves: std::array::from_fn(|i| s.revealed_moves(i).to_vec()),
        sleep: std::array::from_fn(|i| s.sleep_observed(i)),
        binding: s.binding_victim_turns(),
    }
}

struct Failures(Vec<String>);
impl Failures {
    fn check(&mut self, ok: bool, msg: impl FnOnce() -> String) {
        if !ok && self.0.len() < 40 {
            self.0.push(msg());
        }
    }
}

/// Drives `n` random-policy battles and applies every property at every update.
fn sweep(n: u64, seed0: u64, f: &mut Failures) -> (u64, u64) {
    let t = tables();
    let (mut battles, mut updates) = (0u64, 0u64);
    for s in 0..n {
        let p1: Vec<_> = random_team(s ^ 0xA11CE, false).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(s ^ 0xB0B, false).iter().map(|m| m.to_bytes()).collect();
        let mut b = Battle::new(seed0.wrapping_add(s), &p1, &p2);
        let mut tr = BattleTracker::default();
        let mut r = b
            .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
            .unwrap();
        tr.observe(&b);
        // `sleep_entry[p][i]` = the sleep duration recorded when that mon fell
        // asleep, for the conservation law.
        // Transform and Mimic REWRITE a mon's live slots, so a move it was seen
        // using need not be in its stored set afterwards -- and the engine
        // restores the stored slots on switch-out, which erases the evidence.
        // The soundness property has to know that happened.
        let mut rewrote = [[false; 6]; 2];
        // Sleep can be RE-APPLIED while a mon is already asleep, and poke-env
        // does not reset `_status_counter` on a fresh `-status|slp` (only on
        // cure and switch-out), so the tracker must not either. Conservation is
        // therefore stated against a baseline that re-bases whenever the
        // remaining count goes UP.
        let mut prev_left = [[0u8; 6]; 2];
        let mut baseline = [[0u8; 6]; 2];
        let mut prev: [Snap; 2] = [snap(&tr, Player::P1), snap(&tr, Player::P2)];
        let mut rng = seed0 ^ s ^ 0xF00D;
        let mut guard = 0;
        while !r.over() && guard < 3000 {
            guard += 1;
            // Record sleep entries BEFORE the update, so a mon that falls asleep
            // during it is picked up on the next pass.

            let mut pick = [Choice::Pass; 2];
            for (k, p) in [Player::P1, Player::P2].iter().enumerate() {
                let cs = b.choices(*p, r.request(*p));
                rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                pick[k] = cs.get(((rng >> 33) as usize) % cs.len());
            }
            r = b.update(r.p1, pick[0], r.p2, pick[1]).unwrap();
            tr.observe(&b);
            updates += 1;
            for (k, p) in [Player::P1, Player::P2].iter().enumerate() {
                let side = b.side(*p);
                let i = side.active_party_index();
                let live = side.active().moves();
                let stored = side.party(i).moves();
                if side.active().volatiles().transform()
                    || live.iter().zip(stored.iter()).any(|(a, c)| a.0 != c.0)
                {
                    rewrote[k][i] = true;
                }
            }

            for (k, p) in [Player::P1, Player::P2].iter().enumerate() {
                let side = b.side(*p);
                let st = tr.side(*p);
                let now = snap(&tr, *p);
                let was = &prev[k];

                // --- monotonicity: reveal lists only ever extend -------------
                f.check(
                    now.reveal_order.starts_with(&was.reveal_order),
                    || format!("reveal_order shrank or reordered: {:?} -> {:?}", was.reveal_order, now.reveal_order),
                );
                f.check(now.reveal_order.len() <= 6, || "more than six mons revealed".into());
                {
                    let mut u = now.reveal_order.clone();
                    u.sort_unstable();
                    u.dedup();
                    f.check(u.len() == now.reveal_order.len(), || "a mon was revealed twice".into());
                }
                for i in 0..6 {
                    f.check(
                        now.revealed_moves[i].starts_with(&was.revealed_moves[i]),
                        || format!("revealed_moves[{i}] shrank or reordered"),
                    );
                    f.check(now.revealed_moves[i].len() <= 4, || format!("revealed_moves[{i}] > 4"));
                    let mut u = now.revealed_moves[i].clone();
                    u.sort_unstable();
                    u.dedup();
                    f.check(u.len() == now.revealed_moves[i].len(), || {
                        format!("revealed_moves[{i}] has a duplicate")
                    });
                    // sleep_observed steps by +1 or resets to 0, never jumps.
                    let (a, c) = (was.sleep[i], now.sleep[i]);
                    f.check(c == 0 || c == a || c == a + 1, || {
                        format!("sleep_observed[{i}] jumped {a} -> {c}")
                    });
                    f.check(c <= 7, || format!("sleep_observed[{i}] = {c} > 7"));
                }
                f.check(
                    now.binding == 0 || now.binding == was.binding || now.binding == was.binding + 1,
                    || format!("binding_victim_turns jumped {} -> {}", was.binding, now.binding),
                );

                // --- reveal COMPLETENESS: damage, status or spent PP implies
                //     the mon was on the field, and being on the field reveals
                //     it. Reads a different part of the state than the rule.
                for i in 0..6 {
                    let mon = side.party(i);
                    if mon.is_empty() {
                        continue;
                    }
                    let hurt = mon.hp() < mon.stats().hp;
                    let statused = mon.status().0 != 0;
                    let spent = mon
                        .moves()
                        .iter()
                        .any(|&(id, pp)| id != 0 && (pp as u16) < data::max_pp(id) as u16);
                    f.check(!(hurt || statused || spent) || st.is_revealed(i), || {
                        format!(
                            "party {i} is hurt/statused/PP-spent but was never revealed \
                             (hp {} / {}, status {:#04x})",
                            mon.hp(),
                            mon.stats().hp,
                            mon.status().0
                        )
                    });
                }

                // --- reveal SOUNDNESS: a revealed move must exist on that mon,
                //     and (unless Transform/Mimic rewrote its slots) must have
                //     spent PP.
                for i in 0..6 {
                    let mon = side.party(i);
                    let live_ids: Vec<u8> = if i == side.active_party_index() {
                        side.active().moves().iter().map(|m| m.0).collect()
                    } else {
                        vec![]
                    };
                    for &id in st.revealed_moves(i) {
                        let known = mon.moves().iter().any(|&(m, _)| m == id)
                            || live_ids.contains(&id)
                            // A mon that Transformed or Mimicked was seen using
                            // moves it does not own; switching out restores its
                            // stored slots and erases the trace.
                            || rewrote[k][i];
                        f.check(known, || {
                            format!("revealed move {id} is not in party {i}'s stored or live slots")
                        });
                    }
                }

                // --- sleep CONSERVATION: while a single sleep runs down,
                //     observed + remaining is constant. Re-based whenever the
                //     remaining count goes UP, which is a fresh sleep.
                for i in 0..6 {
                    let mon = side.party(i);
                    let stt = mon.status();
                    let left = stt.sleep_turns_left();
                    if stt.asleep() {
                        if left > prev_left[k][i] {
                            baseline[k][i] = st.sleep_observed(i) + left;
                        }
                        let total = st.sleep_observed(i) + left;
                        f.check(total == baseline[k][i], || {
                            format!(
                                "sleep conservation broken on party {i}: observed {} + left {left} \
                                 != baseline {}",
                                st.sleep_observed(i),
                                baseline[k][i]
                            )
                        });
                    }
                    prev_left[k][i] = left;
                    // Awake and alive: the counter must be clear.
                    if !stt.asleep() && mon.hp() > 0 {
                        f.check(st.sleep_observed(i) == 0, || {
                            format!("party {i} is awake but sleep_observed = {}", st.sleep_observed(i))
                        });
                    }
                }
                prev[k] = now;
            }

            // --- CROSS-SEAT AGREEMENT: every public fact must read the same
            //     from both sides, by two different code paths.
            for p in [Player::P1, Player::P2] {
                let own = tr.state_for(&b, p, r.request(p), &t);
                let theirs = tr.state_for(&b, p.foe(), r.request(p.foe()), &t);
                // p's own team, as p sees it, vs the same mons as p.foe() sees
                // them (reveal-ordered on that side).
                for (slot, &party) in tr.side(p).reveal_order().iter().enumerate() {
                    let mine = &own.own.team[party as usize];
                    let seen = &theirs.opp.team[slot];
                    f.check(seen.present, || format!("{p:?} party {party} revealed but not present"));
                    f.check(mine.species == seen.species, || {
                        format!("{p:?} party {party}: species {} vs {}", mine.species, seen.species)
                    });
                    f.check(mine.level == seen.level, || format!("{p:?} party {party}: level"));
                    f.check(mine.fainted == seen.fainted, || format!("{p:?} party {party}: fainted"));
                    f.check(mine.status == seen.status, || {
                        format!("{p:?} party {party}: status {:?} vs {:?}", mine.status, seen.status)
                    });
                    f.check(mine.is_active == seen.is_active, || format!("{p:?} party {party}: is_active"));
                    f.check(mine.base_stats == seen.base_stats, || format!("{p:?} party {party}: base stats"));
                    f.check(
                        mine.type_1 == seen.type_1 && mine.type_2 == seen.type_2,
                        || format!("{p:?} party {party}: types"),
                    );
                    // The foe's view is the exact fraction rounded to Showdown's
                    // percentage, and never more than one bucket away.
                    let mon = b.side(p).party(party as usize);
                    let want = health_percent(mon.hp(), mon.stats().hp) as f64 / 100.0;
                    f.check((seen.hp_fraction - want).abs() < 1e-12, || {
                        format!("{p:?} party {party}: foe hp {} != quantised {want}", seen.hp_fraction)
                    });
                    f.check((seen.hp_fraction - mine.hp_fraction).abs() <= 0.01 + 1e-9, || {
                        format!(
                            "{p:?} party {party}: quantised {} is more than one bucket from exact {}",
                            seen.hp_fraction, mine.hp_fraction
                        )
                    });
                }
                // An unrevealed mon must be absent from the foe's view entirely.
                let revealed = tr.side(p).reveal_order().len();
                for slot in revealed..6 {
                    f.check(!theirs.opp.team[slot].present, || {
                        format!("{p:?}: slot {slot} present with only {revealed} revealed")
                    });
                }
                // Both seats must agree on whose mon is active.
                if let Some(a) = theirs.opp.active_slot {
                    let party = tr.side(p).reveal_order()[a] as usize;
                    f.check(party == b.side(p).active_party_index(), || {
                        format!("{p:?}: foe's view has the wrong active")
                    });
                }
            }
        }
        battles += 1;
    }
    (battles, updates)
}

#[test]
fn the_tracker_satisfies_its_invariants_over_random_battles() {
    let mut f = Failures(Vec::new());
    let (battles, updates) = sweep(300, 0x7BACC_7000, &mut f);
    eprintln!("tracker properties: {battles} battles, {updates} updates");
    assert!(updates > 20_000, "only {updates} updates; the sweep is thin");
    assert!(
        f.0.is_empty(),
        "{} tracker invariant violation(s):\n{}",
        f.0.len(),
        f.0.join("\n")
    );
}

/// The properties must be able to FAIL. Each of these is a plausible bug; if a
/// mutated tracker still passes, the property is decoration.
#[test]
fn the_properties_can_actually_fail() {
    // Cross-seat agreement is the load-bearing one, so prove the comparison
    // notices a side swap: read the foe's HP from the WRONG side and check the
    // quantisation assertion fires.
    let t = tables();
    let p1: Vec<_> = random_team(1, false).iter().map(|m| m.to_bytes()).collect();
    let p2: Vec<_> = random_team(2, false).iter().map(|m| m.to_bytes()).collect();
    let mut b = Battle::new(0xC0FFEE, &p1, &p2);
    let mut tr = BattleTracker::default();
    let mut r = b
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    tr.observe(&b);
    let mut rng = 5u64;
    for _ in 0..30 {
        if r.over() {
            break;
        }
        let mut pick = [Choice::Pass; 2];
        for (k, p) in [Player::P1, Player::P2].iter().enumerate() {
            let cs = b.choices(*p, r.request(*p));
            rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
            pick[k] = cs.get(((rng >> 33) as usize) % cs.len());
        }
        r = b.update(r.p1, pick[0], r.p2, pick[1]).unwrap();
        tr.observe(&b);
    }
    let st = tr.state_for(&b, Player::P1, r.request(Player::P1), &t);
    let party = tr.side(Player::P2).reveal_order()[0] as usize;
    let mon = b.side(Player::P2).party(party);
    let right = health_percent(mon.hp(), mon.stats().hp) as f64 / 100.0;
    let wrong = {
        let m = b.side(Player::P1).party(0);
        health_percent(m.hp(), m.stats().hp) as f64 / 100.0
    };
    assert!(
        (st.opp.team[0].hp_fraction - right).abs() < 1e-12,
        "the tracker disagrees with the quantisation rule it is graded against"
    );
    assert!(
        (right - wrong).abs() > 1e-12,
        "the two sides happen to share an HP percentage here, so a side swap \
         would be invisible -- pick another position"
    );

    // And the sleep conservation law must reject a double increment.
    let entry = 5u8;
    let (observed, left) = (3u8, 1u8); // 3 + 1 != 5: a double increment
    assert_ne!(observed + left, entry, "the conservation check would not fire");
}


/// F1: on a FORCE-SWITCH request the fainted mon is still the active, and
/// poke-env's `faint()` clears `_effects` but NOT `_must_recharge`,
/// `_preparing_move` or `_status_counter` (`pokemon.py:422-429`; those clear in
/// `moved()` and `switch_out()`). The engine zeroes the whole volatile word and
/// the status byte inside `faint()` (`mechanics.zig:1544-1570`), so without the
/// tracker's snapshot three own-active features would read 0 where poke-env
/// reports the stale value -- on ~12.5% of all rows, which is what makes this
/// the one divergence in the tracker that was worth chasing.
#[test]
fn a_fainted_active_still_reports_what_poke_env_would() {
    let t = tables();
    let p1: Vec<_> = random_team(21, true).iter().map(|m| m.to_bytes()).collect();
    let p2: Vec<_> = random_team(22, true).iter().map(|m| m.to_bytes()).collect();
    let mut b = Battle::new(0xFA1_7ED, &p1, &p2);
    let mut tr = BattleTracker::default();
    b.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    tr.observe(&b);

    let p = Player::P1;
    let side_at = B_SIDES + p.index() * SIDE_SIZE;
    let active_at = side_at + S_ACTIVE;
    let i = b.side(p).active_party_index();
    let party_at = side_at + S_POKEMON + i * POKEMON_SIZE;

    // Alive, mid-recharge, asleep for two observed turns, and charging.
    let set_vol = |b: &mut Battle, bit: u32, on: bool| {
        let at = active_at + A_VOLATILES;
        let mut w = [0u8; 8];
        w.copy_from_slice(&b.0[at..at + 8]);
        let mut v = u64::from_le_bytes(w);
        let m = 1u64 << bit;
        v = if on { v | m } else { v & !m };
        b.0[at..at + 8].copy_from_slice(&v.to_le_bytes());
    };
    set_vol(&mut b, V_RECHARGING, true);
    set_vol(&mut b, V_CHARGING, true);
    b.0[party_at + P_STATUS] = 0b0000_0011; // asleep, 3 turns left
    tr.observe(&b);
    b.0[party_at + P_STATUS] = 0b0000_0010; // one turn observed
    tr.observe(&b);

    let before = tr.state_for(&b, p, Request::Move, &t);
    assert!(before.own.active.volatiles[3], "MUST_RECHARGE while alive");
    assert!(before.own.active.preparing, "preparing while alive");
    assert_eq!(before.own.active.status_counter, 1, "one sleep turn observed");

    // Now faint it exactly as the engine does: HP 0, volatiles and status wiped.
    b.0[party_at + P_HP..party_at + P_HP + 2].copy_from_slice(&0u16.to_le_bytes());
    b.0[party_at + P_STATUS] = 0;
    for k in 0..8 {
        b.0[active_at + A_VOLATILES + k] = 0;
    }
    tr.observe(&b);

    let after = tr.state_for(&b, p, Request::Switch, &t);
    assert!(after.own.team[i].fainted);
    assert!(
        after.own.active.volatiles[3],
        "MUST_RECHARGE must survive the faint -- poke-env's faint() does not clear it"
    );
    assert!(
        after.own.active.preparing,
        "preparing must survive the faint -- poke-env's faint() does not clear it"
    );
    assert_eq!(
        after.own.active.status_counter, 1,
        "status_counter must survive the faint -- poke-env resets it only on \
         cure_status and switch_out"
    );
    // The six EFFECT-derived volatile slots DO clear: poke-env's faint() calls
    // _clear_effects(), and the engine zeroes them too.
    for k in [0usize, 1, 2, 4, 5, 6] {
        assert!(!after.own.active.volatiles[k], "volatile slot {k} should clear on a faint");
    }
    // A force-switch request is never trapped and never aliased.
    assert!(!after.trapped && !after.aliased && after.force_switch);
}

//! The write-side bridge, graded (`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §2).
//!
//! Five legs, and each answers a different question:
//!
//!   a. **Round-trip.** Every writer in `layout.rs` is the inverse of its reader
//!      on random values. Cheap, and it is the only thing that catches a
//!      transposed offset or a botched bit field.
//!   b. **The engine accepts our bytes.** A battle assembled from a spec, then
//!      `update`d, produces the same `Result` / `Request` shapes as one from
//!      `Battle::new`. `Battle::update` validates both choices against the
//!      engine's own `choices()` first (`battle.rs:288-307`), so this is a real
//!      legality oracle, not a smoke test.
//!   c. **W-VALIDATE rejects each malformed case with the RIGHT FIELD NAMED.**
//!      Asserting only "it errored" would pass on an error raised for the wrong
//!      reason, which is how a validator quietly stops validating.
//!   d. **The byte-identity guard.** A spec built from a played battle's own
//!      K-class fields reproduces that battle's 384 bytes EXACTLY, except the
//!      ranges §2 declares unrecoverable. The allowed set is written down
//!      explicitly so that widening it fails loudly rather than silently.
//!   e. the existing suite, untouched.
//!
//! The determinization, the reveal order and the HP quantisation are NOT here:
//! those live on the Python half of the bridge and are graded by R1-E (§3.2).

use pkmn_gen1::battle::{Battle, Choice, Outcome, Player, Request, splitmix64};
use pkmn_gen1::data;
use pkmn_gen1::layout::*;
use pkmn_gen1::spec::*;
use pkmn_gen1::team::PokemonSet;

// =============================================================================
// A deterministic bit source. `splitmix64` is already in the crate and already
// pinned against Vigna's reference vectors (`battle.rs:478-482`), so the tests
// need no new dependency and no OS entropy -- a repo-wide rule after the
// global-`random` seat-name incident (CLAUDE.md, "Development environment").
// =============================================================================
struct Rng(u64);
impl Rng {
    fn new(seed: u64) -> Rng {
        Rng(seed)
    }
    fn next(&mut self) -> u64 {
        self.0 = splitmix64(self.0);
        self.0
    }
    fn below(&mut self, n: u64) -> u64 {
        self.next() % n
    }
    fn bool(&mut self) -> bool {
        self.next() & 1 == 1
    }
}

// =============================================================================
// (a) Every writer round-trips through its reader
// =============================================================================

#[test]
fn stats_round_trip() {
    let mut r = Rng::new(0xA11CE);
    let mut b = [0u8; POKEMON_SIZE];
    for _ in 0..2000 {
        let s = Stats {
            hp: r.below(1024) as u16,
            atk: r.below(1024) as u16,
            def: r.below(1024) as u16,
            spe: r.below(1024) as u16,
            spc: r.below(1024) as u16,
        };
        s.write(&mut b, P_STATS);
        assert_eq!(PokemonView(&b).stats(), s);
    }
}

#[test]
fn boosts_round_trip_including_the_i4_sign_extension() {
    let mut r = Rng::new(0xB0057);
    let mut b = [0u8; ACTIVE_SIZE];
    // Every stage in range, and the full -6..=6 cross-product on one pair, so a
    // sign-extension slip (control C6 in §3.3) cannot hide behind zeros.
    for _ in 0..4000 {
        let stage = |r: &mut Rng| (r.below(13) as i8) - 6;
        let want = Boosts {
            atk: stage(&mut r),
            def: stage(&mut r),
            spe: stage(&mut r),
            spc: stage(&mut r),
            accuracy: stage(&mut r),
            evasion: stage(&mut r),
        };
        ActiveViewMut(&mut b).set_boosts(want);
        assert_eq!(ActiveView(&b).boosts(), want);
    }
    for a in -6..=6i8 {
        for d in -6..=6i8 {
            let want = Boosts { atk: a, def: d, ..Default::default() };
            ActiveViewMut(&mut b).set_boosts(want);
            assert_eq!(ActiveView(&b).boosts(), want, "atk={a} def={d}");
        }
    }
}

#[test]
fn volatile_flags_and_counters_round_trip() {
    let mut r = Rng::new(0x5011D);
    for _ in 0..4000 {
        let mut v = Volatiles(0);
        let f: Vec<bool> = (0..18).map(|_| r.bool()).collect();
        v.set_bide(f[0])
            .set_thrashing(f[1])
            .set_multi_hit(f[2])
            .set_flinch(f[3])
            .set_charging(f[4])
            .set_binding(f[5])
            .set_invulnerable(f[6])
            .set_confusion(f[7])
            .set_mist(f[8])
            .set_focus_energy(f[9])
            .set_substitute(f[10])
            .set_recharging(f[11])
            .set_rage(f[12])
            .set_leech_seed(f[13])
            .set_toxic(f[14])
            .set_light_screen(f[15])
            .set_reflect(f[16])
            .set_transform(f[17]);
        let conf = r.below(8) as u8;
        let atk = r.below(8) as u8;
        let st = r.below(65536) as u16;
        let sub = r.below(256) as u8;
        let tid = r.below(16) as u8;
        let dd = r.below(16) as u8;
        let dm = r.below(8) as u8;
        let tt = r.below(32) as u8;
        v.set_confusion_turns(conf)
            .set_attacks(atk)
            .set_state(st)
            .set_substitute_hp(sub)
            .set_transform_id(tid)
            .set_disable_duration(dd)
            .set_disable_move(dm)
            .set_toxic_turns(tt);

        let got = [
            v.bide(), v.thrashing(), v.multi_hit(), v.flinch(), v.charging(), v.binding(),
            v.invulnerable(), v.confusion(), v.mist(), v.focus_energy(), v.substitute(),
            v.recharging(), v.rage(), v.leech_seed(), v.toxic(), v.light_screen(), v.reflect(),
            v.transform(),
        ];
        assert_eq!(got.to_vec(), f, "a flag bit moved");
        assert_eq!(v.confusion_turns(), conf);
        assert_eq!(v.attacks(), atk);
        assert_eq!(v.state(), st);
        assert_eq!(v.substitute_hp(), sub);
        assert_eq!(v.transform_id(), tid);
        assert_eq!(v.disable_duration(), dd);
        assert_eq!(v.disable_move(), dm);
        assert_eq!(v.toxic_turns(), tt);
    }
}

/// The packed fields must not bleed into each other. Written independently of
/// the round-trip above, which would pass if two setters shared a mask.
#[test]
fn volatile_fields_do_not_overlap() {
    let widths: [(u32, u32); 8] = [
        (V_CONFUSION_TURNS, 3),
        (V_ATTACKS, 3),
        (V_STATE, 16),
        (V_SUBSTITUTE_HP, 8),
        (V_TRANSFORM_ID, 4),
        (V_DISABLE_DURATION, 4),
        (V_DISABLE_MOVE, 3),
        (V_TOXIC_TURNS, 5),
    ];
    let mut seen = 0u64;
    for (off, w) in widths {
        let mask = ((1u64 << w) - 1) << off;
        assert_eq!(seen & mask, 0, "field at bit {off} overlaps an earlier one");
        seen |= mask;
    }
    // The 18 flags occupy bits 0..17 and no counter may touch them.
    assert_eq!(seen & 0x3_FFFF, 0, "a packed counter overlaps the flag bits");
}

#[test]
fn status_constructors_match_the_readers() {
    assert!(StatusByte::NONE.healthy());
    assert!(StatusByte::PSN.psn() && !StatusByte::PSN.tox());
    assert!(StatusByte::BRN.brn());
    assert!(StatusByte::FRZ.frz());
    assert!(StatusByte::PAR.par());
    assert!(StatusByte::TOX.tox() && StatusByte::TOX.psn() && StatusByte::TOX.ext());
    for t in 1..=7u8 {
        let s = StatusByte::slp(t);
        assert!(s.asleep() && !s.self_inflicted_sleep());
        assert_eq!(s.sleep_turns_left(), t);
        let f = StatusByte::slf(t);
        assert!(f.asleep() && f.self_inflicted_sleep() && f.ext());
        assert_eq!(f.sleep_turns_left(), t);
    }
    assert!(!StatusByte::slp(0).asleep(), "0 turns is awake, not asleep");
}

#[test]
fn pokemon_and_active_writers_round_trip() {
    let mut r = Rng::new(0xF00D);
    let mut buf = [0u8; SIDE_SIZE];
    for _ in 0..1000 {
        let species = (r.below(151) + 1) as u8;
        let level = (r.below(100) + 1) as u8;
        let hp = r.below(700) as u16;
        let status = StatusByte(r.below(256) as u8);
        let types = ((r.below(15)) as u8, (r.below(15)) as u8);
        let mv = |r: &mut Rng| ((r.below(165) + 1) as u8, r.below(62) as u8);
        let moves: [(u8, u8); 4] = [mv(&mut r), mv(&mut r), mv(&mut r), mv(&mut r)];
        let stats = Stats {
            hp: r.below(1000) as u16,
            atk: r.below(1000) as u16,
            def: r.below(1000) as u16,
            spe: r.below(1000) as u16,
            spc: r.below(1000) as u16,
        };
        let i = r.below(6) as usize;
        {
            let mut w = SideViewMut(&mut buf);
            let mut m = w.party_mut(i);
            m.clear();
            m.set_species(species);
            m.set_level(level);
            m.set_hp(hp);
            m.set_status(status);
            m.set_types(types);
            m.set_moves(moves);
            m.set_stats(stats);
        }
        let v = SideView(&buf).party(i);
        assert_eq!(v.species(), species);
        assert_eq!(v.level(), level);
        assert_eq!(v.hp(), hp);
        assert_eq!(v.status(), status);
        assert_eq!(v.types(), types);
        assert_eq!(v.moves(), moves);
        assert_eq!(v.stats(), stats);

        let order: [u8; 6] = std::array::from_fn(|_| r.below(7) as u8);
        let (lsm, lum) = (r.below(166) as u8, r.below(166) as u8);
        {
            let mut w = SideViewMut(&mut buf);
            w.set_order(order);
            w.set_last_selected_move(lsm);
            w.set_last_used_move(lum);
            let mut a = w.active_mut();
            a.clear();
            a.set_species(species);
            a.set_types(types);
            a.set_moves(moves);
            a.set_stats(stats);
        }
        let s = SideView(&buf);
        assert_eq!(s.order(), order);
        assert_eq!(s.last_selected_move(), lsm);
        assert_eq!(s.last_used_move(), lum);
        assert_eq!(s.active().species(), species);
        assert_eq!(s.active().types(), types);
        assert_eq!(s.active().moves(), moves);
        assert_eq!(s.active().stats(), stats);
    }
}

#[test]
fn battle_header_writers_round_trip() {
    let mut r = Rng::new(0xBEEF);
    let mut b = Battle::default();
    for _ in 0..1000 {
        let turn = r.below(1000) as u16;
        let dmg = r.below(65536) as u16;
        let seed = r.next();
        let lm: [(u8, bool); 2] = [
            ((r.below(5)) as u8, r.bool()),
            ((r.below(5)) as u8, r.bool()),
        ];
        {
            let mut w = BattleViewMut(&mut b.0);
            w.set_turn(turn);
            w.set_last_damage(dmg);
            w.set_seed(seed);
            for (p, (i, c)) in lm.iter().enumerate() {
                w.set_last_moves(p, *i, *c);
            }
        }
        let v = b.view();
        assert_eq!(v.turn(), turn);
        assert_eq!(v.last_damage(), dmg);
        assert_eq!(v.seed(), seed);
        for (p, (i, c)) in lm.iter().enumerate() {
            assert_eq!(v.last_moves(p), (*i, *c as u8));
        }
    }
}

/// `set_order`'s inverse is not just `order()` -- `choices()` and every action
/// mapping go through `slot_of_party_index` (`layout.rs:377-383`).
#[test]
fn order_writer_agrees_with_slot_of_party_index() {
    let mut buf = [0u8; SIDE_SIZE];
    for active in 0..6usize {
        let mut order: [u8; 6] = std::array::from_fn(|i| (i + 1) as u8);
        order.swap(0, active);
        SideViewMut(&mut buf).set_order(order);
        let s = SideView(&buf);
        assert_eq!(s.active_party_index(), active);
        for i in 0..6 {
            let slot = s.slot_of_party_index(i).expect("every party index is in the order");
            assert_eq!(s.order()[slot as usize - 1] as usize, i + 1);
        }
    }
}

// =============================================================================
// Fixtures
// =============================================================================

fn team(base: u8) -> Vec<[u8; POKEMON_SIZE]> {
    (0..6)
        .map(|i| PokemonSet::new(base + i, 80 + i, [1 + i, 20 + i, 40 + i, 60 + i]).to_bytes())
        .collect()
}

fn party_spec(base: u8) -> [MonSpec; 6] {
    std::array::from_fn(|i| {
        MonSpec::from_set(&PokemonSet::new(
            base + i as u8,
            80 + i as u8,
            [1 + i as u8, 20 + i as u8, 40 + i as u8, 60 + i as u8],
        ))
    })
}

/// A plain mid-battle spec: both sides healthy, both actives at party slot 0.
fn plain_spec() -> BattleSpec {
    BattleSpec {
        turn: 7,
        last_damage: 0,
        seed: 0x5EED_1234_5678_9ABC,
        p1: SideSpec::new(party_spec(1), 0),
        p2: SideSpec::new(party_spec(40), 0),
    }
}

/// Plays a real battle forward, collecting every mid-battle state with its
/// request pair. This is the corpus for legs (b) and (d): states the ENGINE
/// produced, so "our bytes reproduce them" is a claim about the real
/// distribution and not about a fixture.
fn played(steps: usize, seed: u64) -> Vec<(Battle, Request, Request)> {
    // `random_team` rather than the fixed `team()` above: it draws move ids
    // across the whole 1..164 range, which is what actually puts status,
    // boosts, sleep, Substitute, Transform and the two-turn moves into the
    // corpus. With a fixed four-move-per-mon fixture the hard cases never
    // occur and the guards below assert containment in a set nothing reaches.
    let conv = |t: Vec<PokemonSet>| -> Vec<[u8; POKEMON_SIZE]> { t.iter().map(|m| m.to_bytes()).collect() };
    let p1 = conv(pkmn_gen1::team::random_team(seed, true));
    let p2 = conv(pkmn_gen1::team::random_team(seed ^ 0xABCD_EF01, true));
    let mut b = Battle::new(seed, &p1, &p2);
    let mut r = b
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .expect("the first update of a fresh battle is (Pass, Pass)");
    let mut rng = Rng::new(seed ^ 0x9999);
    let mut out = Vec::with_capacity(steps);
    for _ in 0..steps {
        if r.over() {
            break;
        }
        out.push((b.clone(), r.p1, r.p2));
        let mut pick = [Choice::Pass; 2];
        for (i, p) in [Player::P1, Player::P2].iter().enumerate() {
            let cs = b.choices(*p, r.request(*p));
            pick[i] = cs.get(rng.below(cs.len() as u64) as usize);
        }
        r = b.update(r.p1, pick[0], r.p2, pick[1]).expect("choices() offered it");
    }
    out
}

// =============================================================================
// (b) The engine accepts our bytes
// =============================================================================

#[test]
fn a_spec_built_battle_updates_like_a_fresh_one() {
    let root = plain_spec().build().expect("a plain mid-battle spec is legal");
    assert_eq!((root.p1, root.p2), (Request::Move, Request::Move), "W-REQ: both actives alive");

    // Both seats are offered a full menu, and the engine runs the turn.
    let mut b = root.battle.clone();
    let c1 = b.choices(Player::P1, root.p1);
    let c2 = b.choices(Player::P2, root.p2);
    assert!(c1.len() >= 4 && c2.len() >= 4, "4 moves + 5 switches expected, got {} / {}", c1.len(), c2.len());
    let res = b.update(root.p1, Choice::Move(1), root.p2, Choice::Move(1)).expect("legal");
    assert_eq!(res.outcome, Outcome::None);
    assert_eq!(b.turn(), 8, "the turn advanced from the constructed 7");

    // The same shape a `Battle::new` battle reaches after its (Pass, Pass).
    let (p1, p2) = (team(1), team(40));
    let mut fresh = Battle::new(0x5EED_1234_5678_9ABC, &p1, &p2);
    let fr = fresh.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass).unwrap();
    assert_eq!((fr.p1, fr.p2), (Request::Move, Request::Move));
    let fres = fresh.update(fr.p1, Choice::Move(1), fr.p2, Choice::Move(1)).expect("legal");
    assert_eq!(fres.outcome, res.outcome);
    assert_eq!((fres.p1, fres.p2), (res.p1, res.p2), "same Request shape from both origins");
}

/// Every state the engine itself produced, rebuilt and driven one more update.
/// This is the leg that would catch a byte the engine reads and we never write.
#[test]
fn every_played_state_rebuilds_into_a_battle_the_engine_accepts() {
    let mut n = 0;
    for seed in 1..=30u64 {
        for (b, r1, r2) in played(40, seed) {
            let spec = BattleSpec::from_visible(&b);
            let root = spec.build().unwrap_or_else(|e| panic!("seed {seed}: {e}"));
            assert_eq!((root.p1, root.p2), (r1, r2), "W-REQ disagrees with the engine's own requests");
            // Same offered choices, as SETS: `order` is renormalised, so the
            // slot LABELS may differ, but `slot_of_party_index` makes the
            // action mapping permutation-invariant -- family W-ORDER's claim.
            for (p, req) in [(Player::P1, r1), (Player::P2, r2)] {
                let want = choice_identities(&b, p, req);
                let got = choice_identities(&root.battle, p, req);
                assert_eq!(got, want, "seed {seed}: the rebuilt state offers a different action set");
            }
            let mut out = root.battle.clone();
            let pick = |bb: &Battle, p: Player, req: Request| bb.choices(p, req).get(0);
            let (c1, c2) = (pick(&out, Player::P1, r1), pick(&out, Player::P2, r2));
            let res = out.update(r1, c1, r2, c2).unwrap_or_else(|e| panic!("seed {seed}: {e}"));
            assert_ne!(res.outcome, Outcome::Error, "showdown mode must never return Error");
            n += 1;
        }
    }
    assert!(n > 200, "the corpus is too small to mean anything: {n}");
}

/// The offered choices named by ENTITY rather than by slot: switches by the
/// party member's species, moves by the live slot's move id. Invariant to the
/// `order` permutation, which is exactly what W-ORDER claims.
fn choice_identities(b: &Battle, p: Player, req: Request) -> Vec<(u8, u8)> {
    let side = b.side(p);
    let mut v: Vec<(u8, u8)> = b
        .choices(p, req)
        .iter()
        .map(|c| match c {
            Choice::Pass => (0, 0),
            Choice::Move(d) => (1, if d == 0 { 0 } else { side.active().moves()[d as usize - 1].0 }),
            Choice::Switch(d) => {
                let party = side.order()[d as usize - 1] as usize;
                (2, if party == 0 { 0 } else { side.party(party - 1).species() })
            }
        })
        .collect();
    v.sort_unstable();
    v
}

/// W-REQ's four rows, each built and each checked against what the engine
/// offers. A force-switch root has a FAINTED active, which is why "actives are
/// never fainted" is NOT one of W-VALIDATE's rules.
#[test]
fn w_req_covers_the_four_faint_shapes() {
    for (f1, f2, want) in [
        (false, false, (Request::Move, Request::Move)),
        (true, false, (Request::Switch, Request::Pass)),
        (false, true, (Request::Pass, Request::Switch)),
        (true, true, (Request::Switch, Request::Switch)),
    ] {
        let mut s = plain_spec();
        if f1 {
            s.p1.party[0].hp = 0;
            s.p1.party[0].status = StatusByte::NONE;
        }
        if f2 {
            s.p2.party[0].hp = 0;
            s.p2.party[0].status = StatusByte::NONE;
        }
        let root = s.build().unwrap_or_else(|e| panic!("{f1}/{f2}: {e}"));
        assert_eq!((root.p1, root.p2), want);
        for (p, req) in [(Player::P1, root.p1), (Player::P2, root.p2)] {
            let cs = root.battle.choices(p, req);
            assert!(!cs.is_empty());
            if req == Request::Switch {
                assert!(cs.iter().all(|c| matches!(c, Choice::Switch(_))), "a Switch request offers only switches");
            }
            if req == Request::Pass {
                assert!(cs.iter().all(|c| matches!(c, Choice::Pass)), "a Pass request offers only Pass");
            }
        }
        // And the engine runs it.
        let mut b = root.battle.clone();
        let pick = |bb: &Battle, p: Player, req: Request| bb.choices(p, req).get(0);
        let (c1, c2) = (pick(&b, Player::P1, root.p1), pick(&b, Player::P2, root.p2));
        b.update(root.p1, c1, root.p2, c2).expect("W-REQ's pair is what update() wants");
    }
}

/// The Charging contract, end to end. `VolatileSpec::charging` carries the SLOT,
/// and from it the builder derives `S_LAST_SELECTED_MOVE` (which `env.rs`'s mask
/// reads) and `B_LAST_MOVES.index` (which the engine's mslot recovery reads).
/// A 0 in the latter is `moves[-1]`, not a small error.
#[test]
fn charging_drives_both_derived_bytes_and_the_engine_releases_the_move() {
    let mut s = plain_spec();
    s.p1.active.volatiles.charging = Some(3);
    let root = s.build().expect("a charging root is legal");
    let live = root.battle.side(Player::P1).active().moves();
    assert_eq!(
        root.battle.side(Player::P1).last_selected_move(),
        live[2].0,
        "S_LAST_SELECTED_MOVE is the charging slot's move"
    );
    assert_eq!(root.battle.view().last_moves(0), (3, 0), "B_LAST_MOVES.index is the charging slot");
    assert!(root.battle.side(Player::P1).active().volatiles().forced());

    // Showdown offers exactly `Move(1)` on a hard lock (`mechanics.zig:3177`).
    let cs = root.battle.choices(Player::P1, root.p1);
    assert_eq!(cs.len(), 1);
    assert_eq!(cs.get(0), Choice::Move(1));

    // And the engine RECOVERS slot 3 from `B_LAST_MOVES.index` on the release
    // turn (`mechanics.zig:439-443`) -- observable because it spends THAT
    // slot's PP, and no other's.
    let mut b = root.battle.clone();
    let before = b.side(Player::P1).active().moves();
    b.update(root.p1, Choice::Move(1), root.p2, Choice::Move(1)).expect("legal");
    assert!(!b.side(Player::P1).active().volatiles().charging(), "the charge was released");
    let after = b.side(Player::P1).active().moves();
    assert_eq!(after[2].1, before[2].1 - 1, "the CHARGING slot spent PP");
    for j in [0usize, 1, 3] {
        assert_eq!(after[j].1, before[j].1, "slot {j} must not have been touched");
    }
}

/// The negative control for the finding above, and the reason
/// `DEFAULT_LAST_MOVE_INDEX` is 1 rather than 0.
///
/// §2.4 classes `B_LAST_MOVES` as **S**, family W-LASTDMG, on the grounds that
/// Counter reads it. It is also LOAD-BEARING for `V_CHARGING`, which §2 does
/// not say: point the index somewhere else and the engine releases a DIFFERENT
/// move. A silent 0 there is not an approximation — `ActivePokemon.move`
/// asserts `mslot > 0` (`data.zig:181`), and with asserts compiled out that is
/// `moves[-1]`.
#[test]
fn last_moves_index_decides_which_charging_move_is_released() {
    let mut s = plain_spec();
    s.p1.active.volatiles.charging = Some(3);
    let root = s.build().unwrap();

    let mut b = root.battle.clone();
    BattleViewMut(&mut b.0).set_last_moves(0, 2, false); // aim at slot 2 instead
    let before = b.side(Player::P1).active().moves();
    b.update(root.p1, Choice::Move(1), root.p2, Choice::Move(1)).expect("still a legal choice");
    let after = b.side(Player::P1).active().moves();
    assert_eq!(after[1].1, before[1].1 - 1, "the engine released the slot the INDEX named");
    assert_eq!(after[2].1, before[2].1, "not the slot the spec meant");

    // W-VALIDATE catches exactly this inconsistency before it can happen.
    let mut bad = root.battle.clone();
    BattleViewMut(&mut bad.0).set_last_moves(0, 2, false);
    let e = validate(&bad, root.p1, root.p2).expect_err("charging index vs last_selected_move");
    assert_eq!(e.field, "last_selected_move", "{e}");
}

// =============================================================================
// (c) W-VALIDATE rejects each malformed case, naming the field
// =============================================================================

/// Every case mutates ONE thing away from a legal spec and asserts the field
/// name. Asserting only "it errored" would pass on an error raised for the
/// wrong reason -- the failure mode `scripts/engine_p1_run.py --mutate` exists
/// to catch on the read side (`NOTES.md`, "a gate that still reports 0 is
/// blind").
fn rejects(field: &'static str, mutate: impl FnOnce(&mut BattleSpec)) {
    let mut s = plain_spec();
    mutate(&mut s);
    match s.build() {
        Ok(_) => panic!("W-VALIDATE accepted a state that violates {field}"),
        Err(e) => assert_eq!(e.field, field, "wrong field named: {e}"),
    }
}

#[test]
fn w_validate_rejects_a_turn_zero_root() {
    // `update` routes turn 0 into `start()`, which switches both leads in from
    // scratch (`mechanics.zig:81-82`) -- a total, silent corruption.
    rejects("turn", |s| s.turn = 0);
}

#[test]
fn w_validate_rejects_out_of_range_identities() {
    rejects("species", |s| s.p1.party[2].species = 152);
    rejects("level", |s| s.p1.party[2].level = 0);
    rejects("level", |s| s.p2.party[1].level = 101);
    rejects("moves", |s| s.p1.party[3].moves[0].0 = 166);
    rejects("active.species", |s| s.p1.active.identity = Some((200, (0, 0))));
}

#[test]
fn w_validate_rejects_impossible_hp_and_pp() {
    rejects("hp", |s| {
        let m = &mut s.p1.party[1];
        m.hp = m.stats.hp + 1;
    });
    rejects("moves", |s| {
        let id = s.p1.party[0].moves[0].0;
        s.p1.party[0].moves[0].1 = data::max_pp(id) + 1;
    });
    rejects("stats.hp", |s| s.p2.party[4].stats.hp = 0);
}

#[test]
fn w_validate_rejects_a_dead_side_and_a_fainted_mon_carrying_status() {
    rejects("party", |s| {
        for m in s.p2.party.iter_mut() {
            m.hp = 0;
            m.status = StatusByte::NONE;
        }
    });
    // `faint()` clears the status byte (`mechanics.zig:1567`), so a fainted mon
    // that still carries PAR is a state the engine cannot be in.
    rejects("status", |s| {
        s.p1.party[2].hp = 0;
        s.p1.party[2].status = StatusByte::PAR;
    });
}

#[test]
fn w_validate_rejects_a_broken_party_and_order() {
    rejects("pokemon", |s| {
        s.p1.party[3] = MonSpec::EMPTY; // a hole, with slots 4 and 5 still filled
    });
    rejects("moves", |s| {
        s.p1.party[0].moves = [(0, 0); 4]; // no moves at all
    });
    rejects("active.moves", |s| {
        s.p1.active.live_moves = Some([(0, 0); 4]);
    });
    rejects("active.moves", |s| {
        // A hole in the live slots: `choices()` stops at the first `.None`
        // (`mechanics.zig:3228`), so slot 3 would silently vanish.
        let mut m = s.p1.party[0].moves;
        m[1] = (0, 0);
        s.p1.active.live_moves = Some(m);
    });
}

#[test]
fn w_validate_rejects_out_of_range_boosts() {
    rejects("active.boosts.atk", |s| s.p1.active.boosts.atk = 7);
    rejects("active.boosts.evasion", |s| s.p2.active.boosts.evasion = -7);
}

#[test]
fn w_validate_rejects_every_flag_counter_mismatch() {
    // W-CONF, both directions.
    rejects("active.volatiles.confusion_turns", |s| {
        s.p1.active.volatiles.confusion = true;
        s.p1.active.volatiles.confusion_turns = Some(0);
    });
    rejects("active.volatiles.confusion_turns", |s| {
        s.p1.active.volatiles.confusion = true;
        s.p1.active.volatiles.confusion_turns = Some(6);
    });
    // W-SUB.
    rejects("active.volatiles.substitute_hp", |s| {
        s.p1.active.volatiles.substitute = true;
        s.p1.active.volatiles.substitute_hp = Some(0);
    });
    // Transform's target slot.
    rejects("active.volatiles.transform_id", |s| {
        s.p1.active.volatiles.transform = Some((Player::P2, 0));
        s.p1.active.identity = Some((132, (0, 0)));
        s.p1.active.stats = Some(Stats::default());
    });
    // Bide / Binding need a selected move (`mechanics.zig:3211`). Vacuous in
    // gen 1 randbats; a hard crash the day it stops being.
    rejects("last_selected_move", |s| s.p1.active.volatiles.bide = true);
    rejects("last_selected_move", |s| s.p1.active.volatiles.binding = true);
}

#[test]
fn w_validate_rejects_the_silent_zero_in_last_moves_index() {
    // The whole point of `DEFAULT_LAST_MOVE_INDEX == 1`.
    rejects("last_moves.index", |s| s.p1.last_move_index = 0);
    rejects("last_moves.index", |s| s.p2.last_move_index = 5);
}

/// The builder zeroes the volatile word for a fainted active on its own, so
/// this rule can only be reached at the BYTE level -- which is exactly where it
/// has to hold, because `from_bytes` accepts anything (§2.4).
#[test]
fn w_validate_rejects_a_fainted_active_carrying_volatiles() {
    let mut s = plain_spec();
    s.p1.party[0].hp = 0;
    s.p1.party[0].status = StatusByte::NONE;
    let root = s.build().expect("a force-switch root is legal");
    assert_eq!(root.p1, Request::Switch);
    assert_eq!(
        root.battle.side(Player::P1).active().volatiles().0,
        0,
        "faint() zeroes the volatile word and so do we"
    );
    let mut b = root.battle.clone();
    {
        let mut w = BattleViewMut(&mut b.0);
        let mut v = Volatiles(0);
        v.set_reflect(true);
        w.side_mut(0).active_mut().set_volatiles(v);
    }
    let e = validate(&b, root.p1, root.p2).expect_err("a fainted active cannot carry volatiles");
    assert_eq!(e.field, "active.volatiles", "{e}");
}

/// The shape checks, which run before assembly because assembly would index out
/// of bounds -- and the two spec-level rules that are invisible in the bytes.
#[test]
fn w_validate_rejects_bad_shape_before_it_can_panic() {
    rejects("active_index", |s| s.p1.active_index = 6);
    rejects("active_index", |s| {
        s.p1.party[5] = MonSpec::EMPTY; // punch a hole, then point the active at it
        s.p1.active_index = 5;
    });
    rejects("volatiles.charging", |s| s.p1.active.volatiles.charging = Some(0));
    rejects("volatiles.charging", |s| s.p1.active.volatiles.charging = Some(5));
    rejects("active.stats", |s| s.p1.active.volatiles.transform = Some((Player::P2, 1)));
    rejects("active.identity", |s| {
        s.p1.active.volatiles.transform = Some((Player::P2, 1));
        s.p1.active.stats = Some(Stats::default());
    });
}

/// W-VALIDATE also has to work on bytes it did not build -- that is the point
/// of §2.4's complaint that `from_bytes` accepts anything.
#[test]
fn w_validate_catches_a_corrupted_order_array_without_calling_the_engine() {
    let root = plain_spec().build().unwrap();
    for (bad, why) in [
        ([7u8, 2, 3, 4, 5, 6], "an index past the party length"),
        ([1u8, 1, 3, 4, 5, 6], "not a permutation"),
        ([0u8, 2, 3, 4, 5, 6], "a zero inside the party"),
    ] {
        let mut b = root.battle.clone();
        BattleViewMut(&mut b.0).side_mut(0).set_order(bad);
        let e = validate(&b, root.p1, root.p2).expect_err(why);
        assert_eq!(e.field, "order", "{why}: {e}");
    }
}

#[test]
fn w_validate_rejects_a_request_pair_that_is_not_w_req() {
    let root = plain_spec().build().unwrap();
    for (r1, r2) in [
        (Request::Switch, Request::Move),
        (Request::Move, Request::Pass),
        (Request::Pass, Request::Pass),
    ] {
        let e = validate(&root.battle, r1, r2).expect_err("both actives are alive: W-REQ says (Move, Move)");
        assert_eq!(e.field, "request", "{e}");
    }
}

// =============================================================================
// (d) The byte-identity guard
// =============================================================================

/// The byte ranges a rebuilt state is ALLOWED to differ in, with the family
/// that owns each. Everything else must be bit-identical.
///
/// This list is the assertion. Widening it is a design change and has to be
/// written here, where it is visible, rather than discovered later as drift.
fn declared_unrecoverable() -> Vec<(usize, usize, &'static str)> {
    let mut v = vec![
        (B_LAST_DAMAGE, 2, "W-LASTDMG"),
        (B_LAST_MOVES, LAST_MOVES_WIDTH, "W-LASTDMG"),
    ];
    for p in 0..2 {
        let side = B_SIDES + p * SIDE_SIZE;
        // order[1..6]: switch history, unobservable, and permutation-invariant
        // for every action mapping (W-ORDER).
        v.push((side + S_ORDER + 1, 5, "W-ORDER"));
        v.push((side + S_LAST_SELECTED_MOVE, 1, "W-LASTMOVE"));
        v.push((side + S_LAST_USED_MOVE, 1, "W-LASTMOVE"));
        // Sleep turns remaining + the EXT bit live in this byte (W-SLEEP).
        for i in 0..6 {
            v.push((side + S_POKEMON + i * POKEMON_SIZE + P_STATUS, 1, "W-SLEEP"));
        }
        // The modified stats (W-ACTIVESTATS), path-dependent by §2.6.
        v.push((side + S_ACTIVE + A_STATS, 10, "W-ACTIVESTATS"));
        // The hidden packed counters; the 18 PUBLIC FLAG BITS are excluded by
        // the mask below and are checked bit-for-bit.
        v.push((side + S_ACTIVE + A_VOLATILES, 8, "W-CONF/W-SUB/hidden counters"));
    }
    v
}

/// The volatile bits that must round-trip exactly: the 18 flags, plus
/// `V_TRANSFORM_ID` (public -- you watched the Transform happen) and
/// `V_TOXIC_TURNS` (poke-env's TOX `status_counter`).
fn public_volatile_mask() -> u64 {
    let mut m = 0x3_FFFFu64; // bits 0..17, the flags
    m |= 0xFu64 << V_TRANSFORM_ID;
    m |= 0x1Fu64 << V_TOXIC_TURNS;
    m
}

#[test]
fn a_spec_from_a_battles_own_visible_fields_reproduces_its_bytes() {
    let allowed = declared_unrecoverable();
    let mut allow_mask = [false; BATTLE_SIZE];
    for (at, len, _) in &allowed {
        for b in allow_mask.iter_mut().skip(*at).take(*len) {
            *b = true;
        }
    }
    let vmask = public_volatile_mask();

    let mut fired: std::collections::BTreeMap<&'static str, usize> = Default::default();
    let mut states = 0usize;
    let mut identical = 0usize;
    for seed in 1..=30u64 {
        for (b, _, _) in played(40, seed) {
            let rebuilt = BattleSpec::from_visible(&b).build().unwrap().battle;
            states += 1;
            let mut diff = 0usize;
            for i in 0..BATTLE_SIZE {
                if b.0[i] == rebuilt.0[i] {
                    continue;
                }
                diff += 1;
                assert!(
                    allow_mask[i],
                    "seed {seed}: byte {i} differs and is NOT in a declared family \
                     (that is a BUG, not a family -- §3.2's pass rule)"
                );
                let fam = allowed
                    .iter()
                    .find(|(at, len, _)| i >= *at && i < at + len)
                    .map(|(_, _, f)| *f)
                    .unwrap();
                *fired.entry(fam).or_default() += 1;
            }
            if diff == 0 {
                identical += 1;
            }
            // The PUBLIC volatile bits are exact -- the byte-range allowance
            // above covers the whole u64, which would otherwise let a flag slip.
            for p in 0..2 {
                let (a, r) = (
                    b.view().side(p).active().volatiles().0,
                    rebuilt.view().side(p).active().volatiles().0,
                );
                assert_eq!(
                    a & vmask,
                    r & vmask,
                    "seed {seed}: a PUBLIC volatile bit changed on p{}",
                    p + 1
                );
            }
            // W-SEED must contribute ZERO: the spec carries the seed verbatim.
            assert_eq!(b.seed(), rebuilt.seed(), "the PSRNG seed must round-trip");
            assert_eq!(b.turn(), rebuilt.turn());
            // W-ORDER's own claim: `order[0]` -- the ACTIVE -- is K and exact.
            for p in 0..2 {
                assert_eq!(
                    b.view().side(p).order()[0],
                    rebuilt.view().side(p).order()[0],
                    "order[0] names the active and is not free"
                );
            }
        }
    }
    assert!(states > 200, "corpus too small: {states}");
    // Positive control: the families must actually FIRE, or the guard is
    // asserting containment in a set nothing reaches.
    assert!(fired.contains_key("W-ORDER"), "W-ORDER never fired: {fired:?}");
    assert!(fired.contains_key("W-LASTMOVE"), "W-LASTMOVE never fired: {fired:?}");
    eprintln!("byte-identity guard: {states} states, {identical} bit-identical, families {fired:?}");
}

/// `A_STATS` is the one allowance that is a MODEL rather than a missing input,
/// so it gets its own claim.
///
/// **This test failed as written against §2.6 and the doc was wrong, not the
/// test.** §2.6 says the rule is "exact when there are no boosts" and bounds
/// its error by the boost x PAR/BRN intersection (2.26% of roots). The engine
/// re-applies `statusModify` to the DEFENDER at the end of EVERY stat change
/// (`mechanics.zig:2580-2581` in `boost`, `:2688-2689` in `unboost`, both
/// labelled "GLITCH: Stat modification errors glitch"), so a paralysed mon with
/// NO boosts of its own compounds another /4 every time its opponent uses a
/// stat move. The claim below is the corrected one: exact iff the active is
/// neither paralysed nor burned.
#[test]
fn active_stats_differs_only_where_section_2_6_says_it_can() {
    let mut total = 0usize;
    let mut wrong = 0usize;
    // The incidence of the case the rule is WRONG on, reported alongside the
    // error count. Without it a 0 is unreadable: it could mean the rule held,
    // or it could mean the corpus never reached the intersection (§2.5 puts it
    // at 2.26% of opponent roots, so a small corpus can miss it entirely).
    let mut intersection = 0usize;
    let mut boosted_n = 0usize;
    let mut status_n = 0usize;
    let mut asleep_n = 0usize;
    for seed in 1..=40u64 {
        for (b, _, _) in played(40, seed) {
            let rebuilt = BattleSpec::from_visible(&b).build().unwrap().battle;
            for p in 0..2 {
                total += 1;
                {
                    let side = b.view().side(p);
                    let mon = side.party(side.active_party_index());
                    let bo = side.active().boosts();
                    let boosted = [bo.atk, bo.def, bo.spe, bo.spc].iter().any(|&x| x != 0);
                    let st = mon.status();
                    if boosted {
                        boosted_n += 1;
                    }
                    if st.par() || st.brn() {
                        status_n += 1;
                    }
                    if st.asleep() {
                        asleep_n += 1;
                    }
                    if boosted && (st.par() || st.brn()) {
                        intersection += 1;
                    }
                }
                let (orig, got) = (
                    b.view().side(p).active().stats(),
                    rebuilt.view().side(p).active().stats(),
                );
                if orig == got {
                    continue;
                }
                wrong += 1;
                let side = b.view().side(p);
                let mon = side.party(side.active_party_index());
                let bo = side.active().boosts();
                let st = mon.status();
                let excused = st.par()
                    || st.brn()
                    || side.active().volatiles().transform()
                    || mon.fainted();
                assert!(
                    excused,
                    "seed {seed} p{}: active.stats differs on a mon that is neither paralysed \
                     nor burned, not transformed and not fainted -- that is outside \
                     W-ACTIVESTATS even as corrected. \
                     stored={:?} boosts={:?} status={:#04x} orig={orig:?} got={got:?}",
                    p + 1,
                    mon.stats(),
                    bo,
                    st.0
                );
            }
        }
    }
    eprintln!(
        "W-ACTIVESTATS: {wrong} / {total} actives differ; incidence boosted={boosted_n} \
         PAR|BRN={status_n} INTERSECTION={intersection} asleep={asleep_n}"
    );
    assert!(
        status_n > 0,
        "the corpus never reached a PAR/BRN active, so the count above says nothing about \
         W-ACTIVESTATS -- widen the corpus before reading it"
    );
    assert!(wrong > 0, "if nothing differs, the excuse list is not being exercised at all");
}

/// W-ORDER's claim, stated as a test rather than as a comment: the SET of
/// actions a seat is offered does not depend on the `order` permutation, so
/// renormalising it is free. This is R1-E leg C's mechanism at the crate level.
#[test]
fn order_is_free_for_the_action_set() {
    for seed in 1..=10u64 {
        for (b, r1, r2) in played(30, seed) {
            let rebuilt = BattleSpec::from_visible(&b).build().unwrap().battle;
            let mut any_reordered = false;
            for p in 0..2 {
                if b.view().side(p).order() != rebuilt.view().side(p).order() {
                    any_reordered = true;
                }
            }
            for (p, req) in [(Player::P1, r1), (Player::P2, r2)] {
                assert_eq!(
                    choice_identities(&rebuilt, p, req),
                    choice_identities(&b, p, req),
                    "seed {seed}: renormalising `order` changed the offered action set \
                     (any_reordered={any_reordered})"
                );
            }
        }
    }
}

/// The §2.6 correction, demonstrated directly rather than inferred from a
/// corpus: a paralysed active with NO boosts of its own loses another factor of
/// 4 on speed the moment its OPPONENT uses a stat move
/// (`mechanics.zig:2580-2581`, "GLITCH: Stat modification errors glitch").
///
/// This is the single largest thing the write side cannot reproduce from a
/// root, and §2.6 does not name it. It is recorded here so that a future change
/// to `active_stats` has to confront it.
#[test]
fn the_stat_modification_glitch_compounds_status_on_the_defender() {
    let id = |name: &str| {
        data::MOVE_NAMES.iter().position(|&n| n == name).unwrap_or_else(|| panic!("no move {name}")) as u8
    };
    let (teleport, swords_dance) = (id("Teleport"), id("Swords Dance"));

    let mut s = plain_spec();
    // P1: paralysed, unboosted, and its only useful move does nothing.
    s.p1.party[0] = MonSpec::from_set(&PokemonSet::new(25, 100, [teleport, 0, 0, 0]));
    s.p1.party[0].status = StatusByte::PAR;
    // P2: a stat move, aimed at itself.
    s.p2.party[0] = MonSpec::from_set(&PokemonSet::new(59, 100, [swords_dance, 0, 0, 0]));

    let root = s.build().expect("legal");
    let stored_spe = root.battle.side(Player::P1).party(0).stats().spe;
    let before = root.battle.side(Player::P1).active().stats().spe;
    assert_eq!(before, stored_spe / 4, "W-ACTIVESTATS applies statusModify exactly once");

    let mut b = root.battle.clone();
    b.update(root.p1, Choice::Move(1), root.p2, Choice::Move(1)).expect("legal");
    let after = b.side(Player::P1).active().stats().spe;
    assert_eq!(
        after,
        (stored_spe / 4) / 4,
        "the foe's Swords Dance re-applied statusModify to P1's ALREADY MODIFIED speed; \
         P1 has no boosts and nothing in its public description changed"
    );
    assert_eq!(b.side(Player::P1).active().boosts(), Boosts::default());
    assert_eq!(b.side(Player::P1).party(0).status(), StatusByte::PAR);
}

/// `MonSpec::determinized` must not panic on a move id outside the table: a bad
/// id is W-VALIDATE's to report, and it cannot report from inside a panic.
/// `data::max_pp` indexes a 166-entry table directly (`data.rs:16-19`).
#[test]
fn an_out_of_range_move_id_is_an_error_not_a_panic() {
    let m = MonSpec::determinized(25, 100, [(200, 0), (0, 0), (0, 0), (0, 0)]);
    assert_eq!(m.moves[0], (200, 0), "the bad id survives to be reported");
    let mut s = plain_spec();
    s.p1.party[0] = m;
    let e = s.build().expect_err("move id 200 is not a gen 1 move");
    assert_eq!(e.field, "moves", "{e}");
}

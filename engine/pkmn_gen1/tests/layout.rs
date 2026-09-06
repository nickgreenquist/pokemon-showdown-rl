//! B-0: every offset in `layout.rs` is pinned to the engine's own machine-readable
//! `src/data/layout.json`, plus the two SHOWDOWN-mode overrides that file does not
//! carry (`last_moves` 4 bytes wide, `rng` at 376) -- those are proved at RUNTIME
//! against the linked library, not read off a document.

use pkmn_gen1::battle::{Battle, Choice, Outcome, PsRng, Request};
use pkmn_gen1::layout::*;
use serde_json::Value;

fn layout_json() -> Value {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/vendor/pkmn-engine/src/data/layout.json"
    );
    let txt = std::fs::read_to_string(path).unwrap_or_else(|e| {
        panic!("cannot read {path}: {e} -- is the submodule checked out?")
    });
    let v: Value = serde_json::from_str(&txt).expect("layout.json is not valid JSON");
    v.as_array().expect("layout.json is an array, one entry per generation")[0].clone()
}

fn off(v: &Value, group: &str, field: &str) -> usize {
    v["offsets"][group][field]
        .as_u64()
        .unwrap_or_else(|| panic!("layout.json has no offsets.{group}.{field}")) as usize
}

fn size(v: &Value, name: &str) -> usize {
    v["sizes"][name]
        .as_u64()
        .unwrap_or_else(|| panic!("layout.json has no sizes.{name}")) as usize
}

#[test]
fn sizes_match_layout_json() {
    let v = layout_json();
    assert_eq!(BATTLE_SIZE, size(&v, "Battle"));
    assert_eq!(SIDE_SIZE, size(&v, "Side"));
    assert_eq!(POKEMON_SIZE, size(&v, "Pokemon"));
    assert_eq!(ACTIVE_SIZE, size(&v, "ActivePokemon"));
    assert_eq!(2 * SIDE_SIZE + 2 + 2 + LAST_MOVES_WIDTH + 8, BATTLE_SIZE);
    assert_eq!(6 * POKEMON_SIZE + ACTIVE_SIZE + 6 + 1 + 1, SIDE_SIZE);
}

#[test]
fn battle_offsets_match_layout_json() {
    let v = layout_json();
    assert_eq!(B_SIDES, off(&v, "Battle", "sides"));
    assert_eq!(B_TURN, off(&v, "Battle", "turn"));
    assert_eq!(B_LAST_DAMAGE, off(&v, "Battle", "last_damage"));
    assert_eq!(B_LAST_MOVES, off(&v, "Battle", "last_moves"));
    // SHOWDOWN OVERRIDE #1 and #2, together: layout.json documents the
    // non-showdown form, where last_moves is [2]u8 and the 9-byte seed starts at
    // 374. In showdown mode MoveDetails is packed u16, so last_moves is 4 bytes
    // and the u64 PSRNG seed sits at 376.
    assert_eq!(
        off(&v, "Battle", "rng"),
        374,
        "layout.json is expected to document the NON-showdown rng offset; if this \
         changed, re-derive both overrides from data.zig before trusting layout.rs"
    );
    assert_eq!(B_RNG, 376);
    assert_eq!(B_LAST_MOVES + LAST_MOVES_WIDTH, B_RNG);
}

#[test]
fn side_pokemon_active_offsets_match_layout_json() {
    let v = layout_json();
    assert_eq!(S_POKEMON, off(&v, "Side", "pokemon"));
    assert_eq!(S_ACTIVE, off(&v, "Side", "active"));
    assert_eq!(S_ORDER, off(&v, "Side", "order"));
    assert_eq!(S_LAST_SELECTED_MOVE, off(&v, "Side", "last_selected_move"));
    assert_eq!(S_LAST_USED_MOVE, off(&v, "Side", "last_used_move"));

    assert_eq!(P_STATS, off(&v, "Pokemon", "stats"));
    assert_eq!(P_MOVES, off(&v, "Pokemon", "moves"));
    assert_eq!(P_HP, off(&v, "Pokemon", "hp"));
    assert_eq!(P_STATUS, off(&v, "Pokemon", "status"));
    assert_eq!(P_SPECIES, off(&v, "Pokemon", "species"));
    assert_eq!(P_TYPES, off(&v, "Pokemon", "types"));
    assert_eq!(P_LEVEL, off(&v, "Pokemon", "level"));

    assert_eq!(A_STATS, off(&v, "ActivePokemon", "stats"));
    assert_eq!(A_SPECIES, off(&v, "ActivePokemon", "species"));
    assert_eq!(A_TYPES, off(&v, "ActivePokemon", "types"));
    assert_eq!(A_BOOSTS, off(&v, "ActivePokemon", "boosts"));
    assert_eq!(A_VOLATILES, off(&v, "ActivePokemon", "volatiles"));
    assert_eq!(A_MOVES, off(&v, "ActivePokemon", "moves"));
}

#[test]
fn stat_and_boost_field_offsets_match_layout_json() {
    let v = layout_json();
    assert_eq!(ST_HP, off(&v, "Stats", "hp"));
    assert_eq!(ST_ATK, off(&v, "Stats", "atk"));
    assert_eq!(ST_DEF, off(&v, "Stats", "def"));
    assert_eq!(ST_SPE, off(&v, "Stats", "spe"));
    assert_eq!(ST_SPC, off(&v, "Stats", "spc"));

    assert_eq!(BO_ATK as usize, off(&v, "Boosts", "atk"));
    assert_eq!(BO_DEF as usize, off(&v, "Boosts", "def"));
    assert_eq!(BO_SPE as usize, off(&v, "Boosts", "spe"));
    assert_eq!(BO_SPC as usize, off(&v, "Boosts", "spc"));
    assert_eq!(BO_ACCURACY as usize, off(&v, "Boosts", "accuracy"));
    assert_eq!(BO_EVASION as usize, off(&v, "Boosts", "evasion"));
}

#[test]
fn volatile_bit_offsets_match_layout_json() {
    let v = layout_json();
    for (name, ours) in [
        ("Bide", V_BIDE),
        ("Thrashing", V_THRASHING),
        ("MultiHit", V_MULTI_HIT),
        ("Flinch", V_FLINCH),
        ("Charging", V_CHARGING),
        ("Binding", V_BINDING),
        ("Invulnerable", V_INVULNERABLE),
        ("Confusion", V_CONFUSION),
        ("Mist", V_MIST),
        ("FocusEnergy", V_FOCUS_ENERGY),
        ("Substitute", V_SUBSTITUTE),
        ("Recharging", V_RECHARGING),
        ("Rage", V_RAGE),
        ("LeechSeed", V_LEECH_SEED),
        ("Toxic", V_TOXIC),
        ("LightScreen", V_LIGHT_SCREEN),
        ("Reflect", V_REFLECT),
        ("Transform", V_TRANSFORM),
        ("confusion", V_CONFUSION_TURNS),
        ("attacks", V_ATTACKS),
        ("state", V_STATE),
        ("substitute", V_SUBSTITUTE_HP),
        ("transform", V_TRANSFORM_ID),
        ("disable_duration", V_DISABLE_DURATION),
        ("disable_move", V_DISABLE_MOVE),
        ("toxic", V_TOXIC_TURNS),
    ] {
        assert_eq!(ours as usize, off(&v, "Volatiles", name), "Volatiles.{name}");
    }
}

// ---------------------------------------------------------------------------
// Runtime proofs against the linked library -- these do not trust any document.
// ---------------------------------------------------------------------------

/// A minimal 24-byte Pokemon record: enough for the engine to run a battle.
fn mon(species: u8, ty: (u8, u8), stats: [u16; 5], moves: &[(u8, u8)]) -> [u8; POKEMON_SIZE] {
    let mut b = [0u8; POKEMON_SIZE];
    for (i, s) in stats.iter().enumerate() {
        b[P_STATS + 2 * i..P_STATS + 2 * i + 2].copy_from_slice(&s.to_le_bytes());
    }
    for (i, (id, pp)) in moves.iter().enumerate() {
        b[P_MOVES + 2 * i] = *id;
        b[P_MOVES + 2 * i + 1] = *pp;
    }
    b[P_HP..P_HP + 2].copy_from_slice(&stats[0].to_le_bytes());
    b[P_SPECIES] = species;
    b[P_TYPES] = ty.0 | (ty.1 << 4);
    b[P_LEVEL] = 100;
    b
}

/// Six identical Tackle-only Normal-types: species 19 (Rattata), type Normal (0).
fn team() -> Vec<[u8; POKEMON_SIZE]> {
    (0..6)
        .map(|i| mon(19 + i, (0, 0), [200, 100, 100, 100, 100], &[(33, 56)]))
        .collect()
}

#[test]
fn rng_lives_at_376_and_is_the_psrng() {
    // If bytes 376..384 really hold the showdown PSRNG state, then after an
    // update those bytes must equal the initial seed advanced some number of
    // times through PS's Gen V/VI LCG. Nothing about that can be true by accident.
    let seed = 0x1234_5678_9ABC_DEF0u64;
    let (a, b) = (team(), team());
    let mut battle = Battle::new(seed, &a, &b);
    assert_eq!(battle.seed(), seed, "the seed we wrote reads back");

    let mut r = battle
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .expect("(Pass, Pass) switches both leads in");
    assert_eq!(r.outcome, Outcome::None);
    assert_eq!(battle.turn(), 1, "the first update starts turn 1");
    assert_eq!(
        battle.seed(),
        seed,
        "switching the leads in is deterministic -- no RNG is consumed on turn 0"
    );

    // Three attacking turns: accuracy, damage rolls and crits all draw.
    for _ in 0..3 {
        assert!(!r.over());
        r = battle
            .update(r.p1, Choice::Move(1), r.p2, Choice::Move(1))
            .expect("Tackle is offered to both sides");
    }
    let after = battle.seed();
    assert_ne!(after, seed, "attacking turns must consume randomness");
    let mut probe = PsRng::new(seed);
    let mut found = None;
    for n in 1..=4096 {
        probe.advance();
        if probe.seed() == after {
            found = Some(n);
            break;
        }
    }
    assert!(
        found.is_some(),
        "bytes 376..384 ({after:#018x}) are not a forward iterate of the PSRNG \
         seeded with {seed:#018x} -- the showdown rng offset is wrong"
    );
}

#[test]
fn a_fresh_battle_starts_with_order_1_to_6_and_zero_actives() {
    let (a, b) = (team(), team());
    let battle = Battle::new(0xDEAD_BEEF, &a, &b);
    for p in [pkmn_gen1::battle::Player::P1, pkmn_gen1::battle::Player::P2] {
        let s = battle.side(p);
        assert_eq!(s.order(), [1, 2, 3, 4, 5, 6]);
        assert_eq!(s.party_len(), 6);
        assert_eq!(s.active().species(), 0, "actives are zeroed before turn 1");
        assert_eq!(s.party(0).species(), 19);
        assert_eq!(s.party(0).hp(), 200);
        assert_eq!(s.party(0).stats().hp, 200);
        assert_eq!(s.party(0).moves()[0], (33, 56));
        assert_eq!(s.party(0).types(), (0, 0));
        assert_eq!(s.party(0).level(), 100);
        assert!(s.party(0).status().healthy());
    }
    assert_eq!(battle.turn(), 0, "turn is 0 before the first update");
}

#[test]
fn order_and_slot_are_inverses_after_a_switch() {
    let (a, b) = (team(), team());
    let mut battle = Battle::new(7, &a, &b);
    battle
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    let p1 = pkmn_gen1::battle::Player::P1;
    assert_eq!(battle.side(p1).active_party_index(), 0);
    assert_eq!(battle.side(p1).slot_of_party_index(0), Some(1));

    // Switch P1 to the party member sitting in slot 3.
    let target_party = battle.side(p1).order()[2] as usize - 1;
    battle
        .update(
            Request::Move,
            Choice::Switch(3),
            Request::Move,
            Choice::Move(1),
        )
        .unwrap();
    let s = battle.side(p1);
    assert_eq!(s.active_party_index(), target_party, "slot 1 now holds it");
    assert_eq!(s.slot_of_party_index(target_party), Some(1));
    let mut seen: Vec<u8> = s.order().to_vec();
    seen.sort_unstable();
    assert_eq!(seen, vec![1, 2, 3, 4, 5, 6], "order stays a permutation");
}

#[test]
fn choices_never_empty_in_showdown_mode() {
    let (a, b) = (team(), team());
    let mut battle = Battle::new(99, &a, &b);
    let mut r = battle
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    for _ in 0..200 {
        if r.over() {
            break;
        }
        let mut pick = [Choice::Pass; 2];
        for (i, p) in [pkmn_gen1::battle::Player::P1, pkmn_gen1::battle::Player::P2]
            .iter()
            .enumerate()
        {
            let req = r.request(*p);
            let cs = battle.choices(*p, req);
            assert!(!cs.is_empty(), "showdown mode always offers >= 1 choice");
            if req == Request::Pass {
                assert_eq!(cs.len(), 1);
                assert_eq!(cs.get(0), Choice::Pass);
            }
            pick[i] = cs.get(0);
        }
        r = battle
            .update(r.p1, pick[0], r.p2, pick[1])
            .expect("choices() output is legal by construction");
    }
}

#[test]
fn an_unoffered_choice_is_refused_not_passed_to_the_engine() {
    let (a, b) = (team(), team());
    let mut battle = Battle::new(5, &a, &b);
    battle
        .update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
        .unwrap();
    // Slot 4 has no move (these mons know one move), so Move(4) is not offered.
    let err = battle
        .update(Request::Move, Choice::Move(4), Request::Move, Choice::Move(1))
        .expect_err("passing an unoffered choice to the engine is UB");
    assert_eq!(err.choice, Choice::Move(4));
    assert!(!err.offered.contains(&Choice::Move(4)));
}

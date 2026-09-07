//! The 828-dim gen-1 encoder in Rust (plan §7.3).
//!
//! This is a REPRODUCTION of `rl/envs/showdown.py::embed_battle` under
//! `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1`, not a redesign: every
//! checkpoint the project has was trained against those exact 828 floats, and
//! "changing OBS_DIM invalidates every checkpoint" is a standing landmine.
//! Gate P-1 compares this output to the Python encoder BITWISE on replayed
//! tapes.
//!
//! ### The bit-exactness rule
//!
//! The Python encoder computes in Python floats (f64) and rounds exactly once,
//! when numpy stores into the float32 array. So does this: every derived value
//! is computed in f64 and cast with a single `as f32` at the store. Values
//! Python stores verbatim from a table (accuracy, the 23-float effect block,
//! prior probabilities) travel as data and are never recomputed here.

use crate::observe::{MonView, ObservableState, SeatState};
use crate::tables::{EFFECT_DIM, N_BASE_STATS, N_BOOSTS, N_TYPES, N_VOLATILES, StaticTables};

/// `_best_multiplier`: max over the ATTACKER's observed types of the multiplier
/// against the defender's observed types.
fn best_multiplier(t: &StaticTables, atk: &MonView, def: &MonView) -> f64 {
    let mut best = f64::NEG_INFINITY;
    for ty in [atk.type_1, atk.type_2].into_iter().flatten() {
        let m = t.multiplier(ty, def.type_1, def.type_2);
        if m > best {
            best = m;
        }
    }
    if best.is_finite() { best } else { 0.0 }
}

pub const GLOBAL_DIM: usize = 6;
pub const MON_STATUS_OFF: usize = 3;
pub const MON_LEVEL_OFF: usize = MON_STATUS_OFF + 6;
pub const MON_STATS_OFF: usize = MON_LEVEL_OFF + 1;
pub const MON_TYPES_OFF: usize = MON_STATS_OFF + N_BASE_STATS;
pub const MON_MATCHUP_OFF: usize = MON_TYPES_OFF + N_TYPES;
pub const MON_DIM_V1: usize = MON_MATCHUP_OFF + 2;
/// v2 appends the speed edge.
pub const MON_DIM: usize = MON_DIM_V1 + 1;

pub const ACTIVE_VOLATILES_OFF: usize = N_BOOSTS;
pub const ACTIVE_COUNTER_OFF: usize = N_BOOSTS + N_VOLATILES;
pub const ACTIVE_DIM: usize = ACTIVE_COUNTER_OFF + 2;

pub const MOVE_TYPE_OFF: usize = 8;
pub const MOVE_DIM_V1: usize = MOVE_TYPE_OFF + N_TYPES;
/// v2 appends the effect block.
pub const MOVE_DIM: usize = MOVE_DIM_V1 + EFFECT_DIM;

pub const ID_DIM: usize = 20;
pub const ID_SCALE: f64 = 256.0;

pub const OBS_DIM: usize = GLOBAL_DIM
    + 6 * MON_DIM
    + ACTIVE_DIM
    + 4 * MOVE_DIM
    + 6 * (MON_DIM + 1)
    + ACTIVE_DIM
    + 4 * MOVE_DIM
    + ID_DIM;

const _: () = assert!(MON_DIM == 33 && ACTIVE_DIM == 16 && MOVE_DIM == 46);
const _: () = assert!(OBS_DIM == 828);

/// `_spe_est`: base speed scaled by level, with the boost multiplier and
/// paralysis applied only for on-field mons. All f64, exactly as Python.
fn spe_est(mon: &MonView, boost_spe: i16, is_active: bool) -> f64 {
    let base = mon.base_stats[4] as f64;
    let mut s = base * mon.level as f64 / 100.0;
    if is_active {
        let b = boost_spe as f64;
        s *= if boost_spe >= 0 {
            (2.0 + b) / 2.0
        } else {
            2.0 / (2.0 - b)
        };
        // status index 2 == PAR
        if mon.status == Some(2) {
            s *= 0.25;
        }
    }
    s.max(1e-3)
}

/// `_speed_edge`: (a - d) / (a + d), positive when `mon` outspeeds the foe.
fn speed_edge(
    mon: &MonView,
    mon_boost_spe: i16,
    mon_is_active: bool,
    foe: &MonView,
    foe_boost_spe: i16,
) -> f64 {
    let a = spe_est(mon, mon_boost_spe, mon_is_active);
    let d = spe_est(foe, foe_boost_spe, true);
    (a - d) / (a + d)
}

#[allow(clippy::too_many_arguments)]
fn fill_mon(
    vec: &mut [f32],
    o: usize,
    t: &StaticTables,
    mon: &MonView,
    foe: Option<&MonView>,
    foe_boost_spe: i16,
    mon_boost_spe: i16,
    is_active: bool,
) {
    vec[o] = mon.hp_fraction as f32;
    vec[o + 1] = f32::from(mon.fainted);
    vec[o + 2] = f32::from(is_active);
    if let Some(s) = mon.status {
        vec[o + MON_STATUS_OFF + s as usize] = 1.0;
    }
    vec[o + MON_LEVEL_OFF] = (mon.level as f64 / 100.0) as f32;
    for i in 0..N_BASE_STATS {
        vec[o + MON_STATS_OFF + i] = (mon.base_stats[i] as f64 / 255.0) as f32;
    }
    for ty in [mon.type_1, mon.type_2].into_iter().flatten() {
        vec[o + MON_TYPES_OFF + ty as usize] = 1.0;
    }
    if let Some(foe) = foe {
        vec[o + MON_MATCHUP_OFF] = best_multiplier(t, mon, foe) as f32;
        vec[o + MON_MATCHUP_OFF + 1] = best_multiplier(t, foe, mon) as f32;
        vec[o + MON_MATCHUP_OFF + 2] =
            speed_edge(mon, mon_boost_spe, is_active, foe, foe_boost_spe) as f32;
    }
}

fn fill_active(vec: &mut [f32], o: usize, seat: &SeatState) {
    for i in 0..N_BOOSTS {
        vec[o + i] = (seat.active.boosts[i] as f64 / 6.0) as f32;
    }
    for i in 0..N_VOLATILES {
        vec[o + ACTIVE_VOLATILES_OFF + i] = f32::from(seat.active.volatiles[i]);
    }
    vec[o + ACTIVE_COUNTER_OFF] = (seat.active.status_counter as f64 / 16.0) as f32;
    vec[o + ACTIVE_COUNTER_OFF + 1] = f32::from(seat.active.preparing);
}

fn fill_move(
    vec: &mut [f32],
    o: usize,
    t: &StaticTables,
    mv: &crate::observe::MoveView,
    foe: Option<&MonView>,
) {
    let e = t.mov(mv.id);
    vec[o] = mv.prob as f32;
    vec[o + 1] = (e.base_power as f64 / 100.0) as f32;
    vec[o + 2] = e.accuracy;
    // Python: `move.current_pp / move.max_pp if move.max_pp else 0.0` -- the
    // MOVE's max_pp, not the table's. They differ after Transform, where
    // poke-env builds the copied Move with `from_transform=True`.
    vec[o + 3] = if mv.max_pp != 0 {
        (mv.pp as f64 / mv.max_pp as f64) as f32
    } else {
        0.0
    };
    if let Some(foe) = foe {
        if let Some(mt) = e.move_type {
            vec[o + 4] = t.multiplier(mt, foe.type_1, foe.type_2) as f32;
        }
    }
    vec[o + 5] = f32::from(e.physical);
    vec[o + 6] = f32::from(e.status);
    vec[o + 7] = (e.priority as f64 / 5.0) as f32;
    if let Some(mt) = e.move_type {
        vec[o + MOVE_TYPE_OFF + mt as usize] = 1.0;
    }
    vec[o + MOVE_DIM_V1..o + MOVE_DIM_V1 + EFFECT_DIM].copy_from_slice(&e.effect);
}

/// `_opponent_move_slots`: up to four (move, probability) pairs for the
/// opponent's active mon -- REVEALED moves first at p = 1.0 in reveal order,
/// then the likeliest unrevealed candidates from the set prior.
///
/// This rule lives here, not in the harness that feeds the encoder. It decides
/// 188 of the 828 columns (the opponent move blocks and their ids), and a
/// harness that imported it from the reference encoder could not falsify it --
/// which is exactly what an adversarial review of P-1 demonstrated by mutating
/// the shared function and watching the mismatch count stay at zero.
pub fn opponent_move_slots(t: &StaticTables, seat: &SeatState) -> [crate::observe::MoveView; 4] {
    let mut out = [crate::observe::MoveView::default(); 4];
    let mut n = 0usize;
    let mut revealed: Vec<u8> = Vec::with_capacity(4);
    for mv in seat.moves.iter() {
        if !mv.present || n >= 4 {
            break;
        }
        out[n] = *mv;
        revealed.push(mv.id);
        n += 1;
    }
    if n >= 4 || seat.active().is_none() {
        return out;
    }
    let Some(active) = seat.active() else { return out };
    let Some(prior) = t.prior_for(active.species) else { return out };
    for (id, p) in prior.conditional(&revealed) {
        if n >= 4 {
            break;
        }
        let max_pp = t.mov(id).max_pp;
        out[n] = crate::observe::MoveView {
            id,
            prob: p,
            // A prior fill is a freshly constructed Move: full PP, hence 1.0.
            pp: max_pp,
            max_pp,
            present: true,
        };
        n += 1;
    }
    out
}

/// `embed_battle`, in Rust. Writes `OBS_DIM` floats into `vec`.
pub fn encode(vec: &mut [f32], t: &StaticTables, s: &ObservableState) {
    assert_eq!(vec.len(), OBS_DIM);
    vec.fill(0.0);

    let ours = s.own.active();
    let theirs = s.opp.active();
    let own_spe = s.own.active.boosts[6];
    let opp_spe = s.opp.active.boosts[6];

    vec[0] = (s.turn as f64 / 50.0).min(1.0) as f32;
    vec[1] = (s.own.fainted_count() as f64 / 6.0) as f32;
    vec[2] = (s.opp.fainted_count() as f64 / 6.0) as f32;
    vec[3] = f32::from(s.force_switch);
    vec[4] = f32::from(s.trapped);
    vec[5] = f32::from(s.aliased);

    let mut o = GLOBAL_DIM;
    for i in 0..6 {
        let mon = &s.own.team[i];
        if !mon.present {
            continue;
        }
        fill_mon(
            vec,
            o + i * MON_DIM,
            t,
            mon,
            theirs,
            opp_spe,
            own_spe,
            s.own.active_slot == Some(i),
        );
    }
    o += 6 * MON_DIM;

    if ours.is_some() {
        fill_active(vec, o, &s.own);
        // ALIASING FIX (D13a): on a placeholder turn the four own-move blocks
        // stay zeroed -- the blocks describe the real moves, but move slot i no
        // longer means "take move i", and teaching that association is the bug
        // this zeroing exists to prevent. vec[5] states the cause.
        if !s.aliased {
            for i in 0..4 {
                let mv = &s.own.moves[i];
                if mv.present {
                    fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, t, mv, theirs);
                }
            }
        }
    }
    o += ACTIVE_DIM + 4 * MOVE_DIM;

    for i in 0..6 {
        let mon = &s.opp.team[i];
        if !mon.present {
            continue;
        }
        let base = o + i * (MON_DIM + 1);
        vec[base] = 1.0; // revealed
        fill_mon(
            vec,
            base + 1,
            t,
            mon,
            ours,
            own_spe,
            opp_spe,
            s.opp.active_slot == Some(i),
        );
    }
    o += 6 * (MON_DIM + 1);

    let opp_slots = opponent_move_slots(t, &s.opp);
    if theirs.is_some() {
        fill_active(vec, o, &s.opp);
        for (i, mv) in opp_slots.iter().enumerate() {
            if mv.present {
                fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, t, mv, ours);
            }
        }
    }

    // The 20-dim identity suffix, each value id/256 (exact in f32: 256 is a
    // power of two). Own move ids are zeroed on an aliased turn for the same
    // reason the blocks are.
    let idb = OBS_DIM - ID_DIM;
    for i in 0..6 {
        if s.own.team[i].present {
            vec[idb + i] = (s.own.team[i].species as f64 / ID_SCALE) as f32;
        }
        if s.opp.team[i].present {
            vec[idb + 6 + i] = (s.opp.team[i].species as f64 / ID_SCALE) as f32;
        }
    }
    if ours.is_some() && !s.aliased {
        for i in 0..4 {
            if s.own.moves[i].present {
                vec[idb + 12 + i] = (s.own.moves[i].id as f64 / ID_SCALE) as f32;
            }
        }
    }
    if theirs.is_some() {
        // The same slot assignment the blocks used: a slot and its id must
        // describe the same move.
        for (i, mv) in opp_slots.iter().enumerate() {
            if mv.present {
                vec[idb + 16 + i] = (mv.id as f64 / ID_SCALE) as f32;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn block_offsets_are_the_specs() {
        assert_eq!(GLOBAL_DIM, 6);
        assert_eq!(MON_STATUS_OFF, 3);
        assert_eq!(MON_LEVEL_OFF, 9);
        assert_eq!(MON_STATS_OFF, 10);
        assert_eq!(MON_TYPES_OFF, 15);
        assert_eq!(MON_MATCHUP_OFF, 30);
        assert_eq!(MON_DIM_V1, 32);
        assert_eq!(MON_DIM, 33);
        assert_eq!(ACTIVE_VOLATILES_OFF, 7);
        assert_eq!(ACTIVE_COUNTER_OFF, 14);
        assert_eq!(ACTIVE_DIM, 16);
        assert_eq!(MOVE_TYPE_OFF, 8);
        assert_eq!(MOVE_DIM_V1, 23);
        assert_eq!(MOVE_DIM, 46);
        assert_eq!(OBS_DIM, 828);
        // The block starts plan §7.3 names.
        assert_eq!(GLOBAL_DIM + 6 * MON_DIM, 204);
        assert_eq!(GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM, 220);
        assert_eq!(GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM, 404);
        assert_eq!(OBS_DIM - ID_DIM, 808);
    }

    #[test]
    fn mono_type_defenders_get_one_chart_lookup() {
        // poke-env returns chart[t1][atk] alone when type_2 is None. Repeating a
        // mono-type would square it -- 2x becomes 4x -- so this is load-bearing.
        let mut chart = [[1.0f64; N_TYPES]; N_TYPES];
        chart[3][7] = 2.0; // attacker 7 hits defender-type 3 for 2x
        let t = StaticTables {
            species: vec![],
            moves: vec![],
            type_chart: chart,
            prior: vec![],
            set_prior: true,
        };
        assert_eq!(t.multiplier(7, Some(3), None), 2.0);
        assert_eq!(t.multiplier(7, Some(3), Some(3)), 4.0);
    }
}

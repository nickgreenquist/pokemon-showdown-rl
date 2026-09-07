//! The engine→observable projection — invariant I1's producer (plan §7.1).
//!
//! `observe.rs` says WHAT a seat may know; this says HOW that is derived from the
//! engine's 384 bytes without ever reading a field the seat could not see. It is
//! the half of the port that gate P-1 deliberately does not test: P-1 compares
//! the two ENCODERS given identical observable state, so everything here — reveal
//! by diff, HP quantisation, observed sleep turns — is graded by D-1 and A-1.
//!
//! The tracker is diff-driven: `observe()` is called after every `update` and
//! compares the new state against what it recorded last time. `-Dlog` stays off;
//! nothing is parsed.
//!
//! ### What is deliberately NEVER read
//!
//! `status & 7` (sleep turns left), `volatiles.confusion_turns`, `.attacks`,
//! `.state` (Bide damage), `.substitute_hp`, `.disable_duration`,
//! `.transform_id`, the foe's `moves[].pp`, `last_damage`, `last_selected_move`,
//! and the RNG seed. `tests/leak_audit.rs` enforces that by listing every field
//! of the layout with its visibility class.

use crate::battle::{Battle, Player, Request};
use crate::layout::{PokemonView, StatusByte};
use crate::observe::{ActiveView as ObsActive, MonView, MoveView, ObservableState, SeatState};
use crate::tables::{N_BASE_STATS, StaticTables};

/// Showdown's `getHealth` under the HP Percentage Mod (`sim/pokemon.ts:2065`),
/// which gen-1 randbats runs: `ceil(100 * hp / maxhp)`, forced to 99 when that
/// rounds a non-full mon up to 100, and 0 when fainted.
///
/// This is the ONLY thing a seat learns about a foe's HP, so it is the only
/// thing the tracker stores.
pub fn health_percent(hp: u16, max_hp: u16) -> u8 {
    if hp == 0 || max_hp == 0 {
        return 0;
    }
    let pct = (100u32 * hp as u32).div_ceil(max_hp as u32) as u8;
    if pct >= 100 && hp < max_hp { 99 } else { pct.min(100) }
}

/// What one side has REVEALED, plus the counters a client would keep.
#[derive(Clone, Debug)]
pub struct SideTracker {
    /// Party indices this side has shown, in the order they first switched in.
    reveal_order: Vec<u8>,
    revealed: [bool; 6],
    /// Move ids this side has been SEEN to use, in usage order, per party index.
    revealed_moves: [Vec<u8>; 6],
    /// poke-env's `status_counter` for SLP: turns of sleep OBSERVED, never the
    /// engine's remaining count.
    sleep_observed: [u8; 6],
    prev_status: [u8; 6],
    prev_active_party: Option<usize>,
    prev_live_moves: [(u8, u8); 4],
    /// Turns this side has been held by a binding move (it is the VICTIM).
    binding_victim_turns: u8,
    started: bool,
}

impl Default for SideTracker {
    fn default() -> Self {
        SideTracker {
            reveal_order: Vec::with_capacity(6),
            revealed: [false; 6],
            revealed_moves: std::array::from_fn(|_| Vec::with_capacity(4)),
            sleep_observed: [0; 6],
            prev_status: [0; 6],
            prev_active_party: None,
            prev_live_moves: [(0, 0); 4],
            binding_victim_turns: 0,
            started: false,
        }
    }
}

impl SideTracker {
    pub fn reveal_order(&self) -> &[u8] {
        &self.reveal_order
    }
    pub fn is_revealed(&self, party: usize) -> bool {
        self.revealed[party]
    }
    pub fn revealed_moves(&self, party: usize) -> &[u8] {
        &self.revealed_moves[party]
    }
    pub fn sleep_observed(&self, party: usize) -> u8 {
        self.sleep_observed[party]
    }
    pub fn binding_victim_turns(&self) -> u8 {
        self.binding_victim_turns
    }

    fn reveal(&mut self, party: usize) {
        if !self.revealed[party] {
            self.revealed[party] = true;
            self.reveal_order.push(party as u8);
        }
    }
}

/// Both sides' projections, advanced together.
#[derive(Clone, Debug, Default)]
pub struct BattleTracker {
    sides: [SideTracker; 2],
}

impl BattleTracker {
    pub fn side(&self, p: Player) -> &SideTracker {
        &self.sides[p.index()]
    }

    /// Advance the projection. Call after EVERY `update`, including the first
    /// `(Pass, Pass)` — that is when the leads become visible.
    pub fn observe(&mut self, b: &Battle) {
        for p in [Player::P1, Player::P2] {
            let side = b.side(p);
            let foe = b.side(p.foe());
            let t = &mut self.sides[p.index()];
            let active_party = side.active_party_index();

            // (1) Reveal by diff: a party slot becomes visible when it takes
            //     over slot 1. `order[0]` is the only thing a client sees.
            let switched = t.prev_active_party != Some(active_party);
            if side.party(active_party).species() != 0 {
                t.reveal(active_party);
            }

            // (2) Move reveal by PP decrement, on the LIVE slots. Correct for
            //     `|cant|` turns (no PP spent, no reveal), for locked
            //     continuation turns (already revealed), for Struggle (no slot)
            //     and after Transform (copied moves reveal as they are used).
            //     Never inferred across a switch: the slots belong to a
            //     different mon.
            let live = side.active().moves();
            if t.started && !switched {
                for i in 0..4 {
                    let (id, pp) = live[i];
                    let (prev_id, prev_pp) = t.prev_live_moves[i];
                    if id != 0 && id == prev_id && pp < prev_pp {
                        let seen = &mut t.revealed_moves[active_party];
                        if !seen.contains(&id) && seen.len() < 4 {
                            seen.push(id);
                        }
                    }
                }
            }
            t.prev_live_moves = live;
            t.prev_active_party = Some(active_party);

            // (3) Observed sleep turns. The remaining count is HIDDEN; what a
            //     client sees is one `|cant|…|slp` per turn, so count the
            //     decrements and reset whenever sleep starts or ends.
            for i in 0..6 {
                let cur = side.party(i).status();
                let prev = StatusByte(t.prev_status[i]);
                if cur.asleep() && prev.asleep() {
                    if cur.sleep_turns_left() < prev.sleep_turns_left() {
                        t.sleep_observed[i] = t.sleep_observed[i].saturating_add(1);
                    }
                } else if cur.asleep() != prev.asleep() {
                    t.sleep_observed[i] = 0;
                }
                t.prev_status[i] = cur.0;
            }

            // (4) Binding: the flag sits on the USER, so this side is the victim
            //     iff the FOE's active carries it. Only ever used to decide
            //     whether Showdown would show the `[Fight]` placeholder.
            if foe.active().volatiles().binding() {
                t.binding_victim_turns = t.binding_victim_turns.saturating_add(1);
            } else {
                t.binding_victim_turns = 0;
            }

            t.started = true;
        }
    }

    /// Build the observation for `seat`, given the request kind it owes.
    pub fn state_for(
        &self,
        b: &Battle,
        seat: Player,
        req: Request,
        t: &StaticTables,
    ) -> ObservableState {
        let own = self.own_seat(b, seat, t);
        let opp = self.foe_seat(b, seat.foe(), t);
        let side = b.side(seat);
        let vol = side.active().volatiles();
        let stored = side.party(side.active_party_index());
        let status = stored.status();

        // `isForced` -- the engine's hard-lock set, which is exactly PS's
        // `trapped: true` (plan §7.2, confirmed at P-2 leg B).
        let forced = vol.recharging() || vol.rage() || vol.thrashing() || vol.charging();

        // Would Showdown re-base the move list onto a placeholder? PS's order of
        // precedence: `mustrecharge` -> `[Recharge]`; a lock -> the move itself
        // (NOT aliased); otherwise the gen-1 `[Fight]` placeholder for sleep,
        // freeze and the first turn as a binding victim; and `[Struggle]` when
        // nothing is selectable.
        let struggle_only = matches!(
            b.choices(seat, req).first_move(),
            Some(crate::battle::Choice::Move(0))
        );
        let aliased = if req != Request::Move {
            false
        } else if vol.recharging() {
            true
        } else if forced {
            false
        } else {
            status.asleep()
                || status.frz()
                || struggle_only
                || self.side(seat).binding_victim_turns() == 1
        };

        ObservableState {
            turn: b.turn(),
            force_switch: req == Request::Switch,
            trapped: forced && req == Request::Move,
            aliased,
            own,
            opp,
        }
    }

    /// Our own side: the `|request|` gives exact HP, status, stats and PP.
    fn own_seat(&self, b: &Battle, p: Player, t: &StaticTables) -> SeatState {
        let side = b.side(p);
        let tr = self.side(p);
        let active_party = side.active_party_index();
        let mut seat = SeatState::default();
        for i in 0..6 {
            let mon = side.party(i);
            if mon.is_empty() {
                continue;
            }
            let is_active = i == active_party;
            seat.team[i] = mon_view(
                &mon,
                t,
                is_active,
                // A transformed mon keeps its own name but wears the target's
                // stats and types; the engine puts the copy in `active.species`.
                if is_active { side.active().species() } else { mon.species() },
                exact_fraction(mon.hp(), mon.stats().hp),
                tr.sleep_observed(i),
            );
        }
        seat.active_slot = Some(active_party);
        seat.active = active_view(b, p, tr.sleep_observed(active_party));
        let live = side.active().moves();
        for i in 0..4 {
            let (id, pp) = live[i];
            if id == 0 {
                continue;
            }
            seat.moves[i] = MoveView {
                id,
                prob: 1.0,
                pp: pp as u16,
                max_pp: t.mov(id).max_pp,
                present: true,
            };
        }
        seat
    }

    /// The opponent: revealed mons only, HP quantised, PP never read.
    fn foe_seat(&self, b: &Battle, p: Player, t: &StaticTables) -> SeatState {
        let side = b.side(p);
        let tr = self.side(p);
        let active_party = side.active_party_index();
        let mut seat = SeatState::default();
        for (slot, &party) in tr.reveal_order().iter().take(6).enumerate() {
            let i = party as usize;
            let mon = side.party(i);
            let is_active = i == active_party;
            seat.team[slot] = mon_view(
                &mon,
                t,
                is_active,
                if is_active { side.active().species() } else { mon.species() },
                // The ONLY thing a seat learns about a foe's HP.
                health_percent(mon.hp(), mon.stats().hp) as f64 / 100.0,
                tr.sleep_observed(i),
            );
            if is_active {
                seat.active_slot = Some(slot);
            }
        }
        if seat.active_slot.is_some() {
            seat.active = active_view(b, p, tr.sleep_observed(active_party));
            // Revealed moves only, in usage order. The prior fills the rest --
            // in `encoder.rs`, from the table, never from the engine's slots.
            for (i, &id) in tr.revealed_moves(active_party).iter().take(4).enumerate() {
                let max_pp = t.mov(id).max_pp;
                seat.moves[i] = MoveView {
                    id,
                    prob: 1.0,
                    // A seat never sees a foe's PP, so the feature is always 1.0.
                    pp: max_pp,
                    max_pp,
                    present: true,
                };
            }
        }
        seat
    }
}

fn exact_fraction(hp: u16, max_hp: u16) -> f64 {
    if hp == 0 || max_hp == 0 {
        0.0
    } else {
        hp as f64 / max_hp as f64
    }
}

/// The six-status one-hot index poke-env uses: BRN, FRZ, PAR, PSN, SLP, TOX.
fn status_index(s: StatusByte) -> Option<u8> {
    if s.tox() {
        Some(5)
    } else if s.asleep() {
        Some(4)
    } else if s.frz() {
        Some(1)
    } else if s.par() {
        Some(2)
    } else if s.brn() {
        Some(0)
    } else if s.psn() {
        Some(3)
    } else {
        None
    }
}

fn mon_view(
    mon: &PokemonView<'_>,
    t: &StaticTables,
    is_active: bool,
    stats_species: u8,
    hp_fraction: f64,
    _sleep_observed: u8,
) -> MonView {
    let sp = t.species(stats_species);
    let mut base_stats = [0u16; N_BASE_STATS];
    base_stats.copy_from_slice(&sp.base_stats);
    MonView {
        present: true,
        species: mon.species(),
        base_stats,
        type_1: sp.type_1,
        type_2: sp.type_2,
        hp_fraction,
        fainted: mon.hp() == 0,
        is_active,
        status: status_index(mon.status()),
        level: mon.level(),
    }
}

fn active_view(b: &Battle, p: Player, sleep_observed: u8) -> ObsActive {
    let side = b.side(p);
    let a = side.active();
    let vol = a.volatiles();
    let boosts = a.boosts();
    let status = side.party(side.active_party_index()).status();
    // Gen 1 has ONE Special stat, and poke-env carries both spa and spd.
    let b7 = [
        boosts.accuracy as i16,
        boosts.atk as i16,
        boosts.def as i16,
        boosts.evasion as i16,
        boosts.spc as i16,
        boosts.spc as i16,
        boosts.spe as i16,
    ];
    // CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE, PARTIALLY_TRAPPED,
    // REFLECT, SUBSTITUTE. PARTIALLY_TRAPPED is the VICTIM's flag, so it reads
    // the FOE's Binding bit. Light Screen has no slot -- poke-env 0.15.0 cannot
    // parse it, so encoding it anywhere would be a divergence, not a fix.
    let vols = [
        vol.confusion(),
        vol.focus_energy(),
        vol.leech_seed(),
        vol.recharging(),
        b.side(p.foe()).active().volatiles().binding(),
        vol.reflect(),
        vol.substitute(),
    ];
    let st = status;
    ObsActive {
        boosts: b7,
        volatiles: vols,
        // SLP uses the OBSERVED count (the remaining count is hidden); TOX uses
        // the toxic counter, which is visible as one damage message per turn.
        status_counter: if st.asleep() {
            sleep_observed as u16
        } else if st.tox() {
            vol.toxic_turns() as u16
        } else {
            0
        },
        preparing: vol.charging(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_percent_is_showdowns_rule() {
        assert_eq!(health_percent(0, 300), 0, "fainted reads 0");
        assert_eq!(health_percent(300, 300), 100, "full reads 100");
        // ceil, not round: one HP off full is 99.67% -> ceil 100 -> forced to 99.
        assert_eq!(health_percent(299, 300), 99);
        assert_eq!(health_percent(1, 300), 1, "a sliver never reads 0");
        assert_eq!(health_percent(150, 300), 50);
        assert_eq!(health_percent(151, 300), 51, "50.33% ceils to 51");
        assert_eq!(health_percent(149, 300), 50, "49.67% ceils to 50");
        // Every non-zero HP must map into 1..=100, and only full HP to 100.
        for max in [1u16, 7, 100, 255, 703] {
            for hp in 1..=max {
                let p = health_percent(hp, max);
                assert!((1..=100).contains(&p), "hp {hp}/{max} -> {p}");
                assert_eq!(p == 100, hp == max, "hp {hp}/{max} -> {p}");
            }
        }
    }

    #[test]
    fn status_index_matches_the_encoders_one_hot() {
        assert_eq!(status_index(StatusByte(0)), None);
        assert_eq!(status_index(StatusByte(0b0001_0000)), Some(0), "BRN");
        assert_eq!(status_index(StatusByte(0b0010_0000)), Some(1), "FRZ");
        assert_eq!(status_index(StatusByte(0b0100_0000)), Some(2), "PAR");
        assert_eq!(status_index(StatusByte(0b0000_1000)), Some(3), "PSN");
        assert_eq!(status_index(StatusByte(0b0000_0011)), Some(4), "SLP, 3 turns left");
        assert_eq!(status_index(StatusByte(0b1000_1000)), Some(5), "TOX = PSN|EXT");
        // Self-inflicted sleep (Rest) is still SLP, not TOX.
        assert_eq!(status_index(StatusByte(0b1000_0010)), Some(4));
    }
}

//! `Gen1Env` / `BatchEnv`: K battles, two seats, no server (plan §7.5, §7.6).
//!
//! Nothing here is licensed. The collector is not comparable to any banked
//! number until gate A-1 passes, and A-1 has not run.
//!
//! The action space, the mask and the block orderings are poke-env's -- invariant
//! I2 -- so this file's job is to translate between the engine's `Choice` and
//! poke-env's 10-way index without inventing anything (plan §7.2, measured at
//! gate P-2):
//!
//!   * action `i` in 0..6 is the party member at ORIGINAL party index `i`, for
//!     the whole battle. It submits `Switch(slot_of_party_index(i))`, because
//!     the engine's switch data is a slot in the CURRENT order.
//!   * action `6+j` is stored move slot `j` -- except on an ALIASED turn, where
//!     Showdown replaces the move list with a single placeholder and only
//!     action 6 is legal.

use crate::battle::{Battle, BattleResult, Choice, IllegalChoice, Outcome, Player, Request};
use crate::encoder::{OBS_DIM, encode};
use crate::layout::POKEMON_SIZE;
use crate::observe::ObservableState;
use crate::scripted::Scripted;
use crate::tables::StaticTables;
use crate::team::PokemonSet;
use crate::track::BattleTracker;

pub const N_ACTIONS: usize = 10;
/// Struggle's gen-1 move num, which is also its engine id (B-0's name map).
const STRUGGLE_ID: i32 = 165;
/// A battle needs several updates per turn; 1000 turns is the showdown-mode
/// ceiling. Generous, and a wedged env trips it instead of hanging (F-03).
pub const MAX_UPDATES: u32 = 8000;

/// One decision owed by one seat.
#[derive(Clone, Debug)]
pub struct Pending {
    pub obs: Vec<f32>,
    pub mask: [bool; N_ACTIONS],
    pub request: Request,
}

/// A finished episode's rows, as the learner's dataset wants them.
#[derive(Clone, Debug, Default)]
pub struct Episode {
    pub obs: Vec<f32>,
    pub masks: Vec<bool>,
    pub actions: Vec<i32>,
    pub logp: Vec<f32>,
    pub version: Vec<i64>,
    /// D25 opponent-action labels: `(kind, id, flags)` per learner row.
    pub opp_choice: Vec<i32>,
    pub reward: f32,
    pub length: usize,
    pub turns: u16,
    pub seed: u64,
    pub member: i32,
    /// Which `BatchEnv` slot produced this episode. The slot has ALREADY been
    /// restarted by the time the caller sees this, so it names where to seat
    /// the next battle's opponent, not where this one still lives.
    pub slot: i32,
}

/// One battle: the engine, both seats' projections, and the learner's rows.
pub struct Gen1Env {
    battle: Battle,
    tracker: BattleTracker,
    result: BattleResult,
    learner: Player,
    seed: u64,
    updates: u32,
    member: i32,
    ep: Episode,
    done: bool,
}

/// Maps an action index to the engine choice it means, or `None` if illegal.
fn action_to_choice(b: &Battle, p: Player, req: Request, aliased: bool, action: usize) -> Option<Choice> {
    let offered = b.choices(p, req);
    if action < 6 {
        let slot = b.side(p).slot_of_party_index(action)?;
        let c = Choice::Switch(slot);
        return offered.contains(c).then_some(c);
    }
    if aliased {
        // Showdown re-based the list onto a single placeholder, so only action 6
        // exists and it means "whatever gen 1 forces". The engine's first Move
        // choice is that. This is the ONE place the submitted choice is not what
        // poke-env would have sent (plan §7.2, declared and negligible).
        return (action == 6).then(|| offered.first_move()).flatten();
    }
    // A HARD LOCK (Thrash / two-turn charge / Rage) offers exactly `Move(1)`,
    // but poke-env does NOT alias it: the locked move is a real member of the
    // mon's move dict, so `get_action_mask` yields `6 + its STORED SLOT`
    // (`singles_env.py:247-251`), not action 6. Plan §7.2 says exactly this
    // ("{6+slot(last_selected_move)}"); mapping it to 6 would put the legal
    // action in the wrong lane on every Sky Attack release turn.
    // `recharging` is in `forced()` too but cannot reach here: a recharge turn
    // is always aliased and left above.
    let side = b.side(p);
    if side.active().volatiles().forced() {
        let locked = side.last_selected_move();
        let slot = side
            .active()
            .moves()
            .iter()
            .position(|&(id, _)| id != 0 && id == locked);
        return match slot {
            // `Move(1)` is the engine's single forced option whatever the slot.
            Some(j) if action == 6 + j => offered.first_move(),
            Some(_) => None,
            // The locked move is not in the live slots (it cannot normally
            // happen); fall back to action 6 rather than offering nothing.
            None => (action == 6).then(|| offered.first_move()).flatten(),
        };
    }
    let c = Choice::Move((action - 6 + 1) as u8);
    offered.contains(c).then_some(c)
}

/// `rl/envs/showdown.py::_order_identity` for one seat's choice: `(kind, id)`,
/// kind 0 switch / 1 move / -1 none. It names the ENTITY, never the slot --
/// `_move_id(move)` and `_species_id(species)` -- and gen 1's engine numbering
/// IS that id space (B-0 proved species 1..151 and moves 1..165 identical to
/// poke-env's `num`), so no table lookup is needed.
///
/// poke-env names the entity in the REQUEST IT WAS SHOWN, not the move the
/// engine will run, so the placeholder turns take the placeholder's id:
///
///   * `Move(0)` is the engine's Struggle marker and Showdown displays
///     Struggle, whose num 165 is in range.
///   * an ALIASED turn is one Showdown re-based onto `Recharge` or `Fight`;
///     neither carries a gen-1 num, so `_move_id` gives 0 for both.
///   * a HARD LOCK is NOT aliased -- the request names the locked move, which is
///     `last_selected_move`. The engine writes `Move(1)` there as a "no slot was
///     offered" marker (`mechanics.zig:3178`, `@intFromBool(showdown)`), so
///     reading that 1 as a stored slot mislabels every lock outside slot 0.
///
/// Reading the DATA FIELD as the id -- the shape this function replaced -- is
/// silent: `canonicalise` matches the id against the row's own opponent-move id
/// suffix, so a slot index simply fails to match and the row lands in
/// OTHER_MOVE with no assertion to trip.
fn choice_identity(b: &Battle, p: Player, aliased: bool, c: Choice) -> (i32, i32) {
    let side = b.side(p);
    match c {
        Choice::Pass => (-1, -1),
        Choice::Move(0) => (1, STRUGGLE_ID),
        Choice::Move(_) if aliased => (1, 0),
        Choice::Move(_) if side.active().volatiles().forced() => {
            (1, side.last_selected_move() as i32)
        }
        Choice::Move(d) => (1, side.active().moves()[d as usize - 1].0 as i32),
        Choice::Switch(d) => {
            let party = side.order()[d as usize - 1] as usize;
            let id = if party == 0 { 0 } else { side.party(party - 1).species() as i32 };
            (0, id)
        }
    }
}

/// The 10-way mask, derived from the engine's own `choices()`.
fn mask_for(b: &Battle, p: Player, req: Request, aliased: bool) -> [bool; N_ACTIONS] {
    let mut m = [false; N_ACTIONS];
    for a in 0..N_ACTIONS {
        m[a] = action_to_choice(b, p, req, aliased, a).is_some();
    }
    m
}

impl Gen1Env {
    pub fn new(
        seed: u64,
        p1: &[[u8; POKEMON_SIZE]],
        p2: &[[u8; POKEMON_SIZE]],
        learner: Player,
        member: i32,
    ) -> Result<Gen1Env, IllegalChoice> {
        let mut battle = Battle::new(seed, p1, p2);
        let mut tracker = BattleTracker::default();
        // Turn 0: `(Pass, Pass)` switches both leads in and yields turn 1's
        // requests. The tracker sees the leads here.
        let result = battle.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)?;
        tracker.observe(&battle);
        Ok(Gen1Env {
            battle,
            tracker,
            result,
            learner,
            seed,
            updates: 1,
            member,
            ep: Episode {
                seed,
                member,
                ..Default::default()
            },
            done: false,
        })
    }

    pub fn done(&self) -> bool {
        self.done
    }
    pub fn member(&self) -> i32 {
        self.member
    }
    pub fn turn(&self) -> u16 {
        self.battle.turn()
    }

    pub(crate) fn state(&self, p: Player, t: &StaticTables) -> ObservableState {
        self.tracker
            .state_for(&self.battle, p, self.result.request(p), t)
    }

    /// The decision `p` owes right now, or `None` when it owes only a Pass.
    pub fn pending(&self, p: Player, t: &StaticTables) -> Option<Pending> {
        if self.done {
            return None;
        }
        let req = self.result.request(p);
        if req == Request::Pass {
            return None;
        }
        let st = self.state(p, t);
        let mut obs = vec![0.0f32; OBS_DIM];
        encode(&mut obs, t, &st);
        Some(Pending {
            obs,
            mask: mask_for(&self.battle, p, req, st.aliased),
            request: req,
        })
    }

    /// Applies one action per seat; either is `None` when that seat owes a Pass.
    ///
    /// It does NOT pump ahead on the caller's behalf. A mid-turn faint leaves
    /// the learner owing a Pass while the opponent replaces its mon, and the
    /// opponent's replacement is a real decision that belongs to the opponent
    /// POLICY -- picking one here would quietly install a "first legal choice"
    /// bot inside the env. The caller re-asks through `pending()` instead, which
    /// is also what keeps opponent inference batched (plan §7.6, §8.2).
    ///
    /// `logp`/`version` are the learner's; they are recorded, not used.
    #[allow(clippy::too_many_arguments)]
    pub fn step(
        &mut self,
        t: &StaticTables,
        learner_action: Option<usize>,
        logp: f32,
        version: i64,
        opp_action: Option<usize>,
    ) -> Result<(), String> {
        if self.done {
            return Err("step() on a finished battle".into());
        }
        let foe = self.learner.foe();
        let (lreq, freq) = (self.result.request(self.learner), self.result.request(foe));

        // The learner's row is recorded BEFORE the update, from the state the
        // action was chosen in.
        let mut lchoice = Choice::Pass;
        if lreq != Request::Pass {
            let a = learner_action.ok_or("the learner owes a decision but none was given")?;
            let st = self.state(self.learner, t);
            let mut obs = vec![0.0f32; OBS_DIM];
            encode(&mut obs, t, &st);
            let mask = mask_for(&self.battle, self.learner, lreq, st.aliased);
            lchoice = action_to_choice(&self.battle, self.learner, lreq, st.aliased, a)
                .ok_or_else(|| {
                    format!(
                        "action {a} is not legal here (mask {:?}); a masking bug must \
                         surface as an error, never as engine UB",
                        mask
                    )
                })?;
            self.ep.obs.extend_from_slice(&obs);
            self.ep.masks.extend(mask);
            self.ep.actions.push(a as i32);
            self.ep.logp.push(logp);
            self.ep.version.push(version);
            self.ep.length += 1;
        }

        let mut fchoice = Choice::Pass;
        if freq != Request::Pass {
            let a = opp_action.ok_or("the opponent owes a decision but none was given")?;
            let st = self.state(foe, t);
            fchoice = action_to_choice(&self.battle, foe, freq, st.aliased, a)
                .ok_or_else(|| format!("opponent action {a} is not legal here"))?;
        }

        // D25 labels come for free: both seats' choices are in hand. The
        // identity must be read BEFORE the update -- `choice_identity` reads the
        // move slots and party order the choice was made against.
        if lreq != Request::Pass {
            // A foe that owes nothing this step gets the SENTINEL, flags and
            // all. `_OPP_CHOICE_NONE` is `(-1, -1, 0)`: PRESENT must be 0, or
            // `canonicalise` reads a row where the opponent never decided as a
            // real decision, fails to match id -1 against any move slot, and
            // trains OTHER_MOVE on it. poke-env reaches the same sentinel via
            // `clear_choice` before every inner step (B2).
            let label = if freq == Request::Pass {
                [-1, -1, 0]
            } else {
                let faliased = self.state(foe, t).aliased;
                let (kind, id) = choice_identity(&self.battle, foe, faliased, fchoice);
                [kind, id, 1 | i32::from(faliased) << 1]
            };
            self.ep.opp_choice.extend_from_slice(&label);
        }

        let (c1, c2) = match self.learner {
            Player::P1 => (lchoice, fchoice),
            Player::P2 => (fchoice, lchoice),
        };
        self.advance(c1, c2)?;

        Ok(())
    }

    /// Applies both choices to the engine and refreshes the projection.
    pub fn advance(&mut self, c1: Choice, c2: Choice) -> Result<(), String> {
        let (r1, r2) = (self.result.p1, self.result.p2);
        self.result = self
            .battle
            .update(r1, c1, r2, c2)
            .map_err(|e| e.to_string())?;
        self.tracker.observe(&self.battle);
        self.updates += 1;
        if self.updates > MAX_UPDATES {
            return Err(format!(
                "battle seed {:#x} exceeded {MAX_UPDATES} updates at turn {}",
                self.seed,
                self.battle.turn()
            ));
        }
        match self.result.outcome {
            Outcome::None => {}
            Outcome::Error => {
                return Err(format!(
                    "engine returned Error, unreachable in showdown mode; state: {:?}",
                    self.battle
                ));
            }
            outcome => {
                // Terminal reward only, from the LEARNER's seat. Ties -- the
                // 1000-turn tie, Endless Battle Clause, a double KO -- score 0,
                // which is the async path's G4c rule.
                let from_p1 = match outcome {
                    Outcome::Win => 1.0,
                    Outcome::Lose => -1.0,
                    _ => 0.0,
                };
                self.ep.reward = if self.learner == Player::P1 { from_p1 } else { -from_p1 };
                self.ep.turns = self.battle.turn();
                self.done = true;
            }
        }
        Ok(())
    }

    pub fn take_episode(self) -> Episode {
        self.ep
    }

    pub fn request(&self, p: Player) -> Request {
        self.result.request(p)
    }

    /// The engine's true state. Only DIAGNOSTIC readers touch this -- gate
    /// D-1's per-battle summaries -- never the encoder, which sees the world
    /// exclusively through `state()`'s `ObservableState`.
    pub fn battle(&self) -> &Battle {
        &self.battle
    }

    /// From P1's seat, as the engine reports it.
    pub fn outcome(&self) -> Outcome {
        self.result.outcome
    }
}

/// The team bank's packed payload (`scripts/engine_team_bank.py`): pairs of two
/// six-mon teams, eight bytes per mon.
pub struct TeamBank {
    payload: Vec<u8>,
}

const BYTES_PER_MON: usize = 8;
const TEAM_BYTES: usize = BYTES_PER_MON * 6;
const PAIR_BYTES: usize = TEAM_BYTES * 2;

impl TeamBank {
    pub fn new(payload: Vec<u8>) -> Result<TeamBank, String> {
        if payload.is_empty() || payload.len() % PAIR_BYTES != 0 {
            return Err(format!(
                "team bank payload is {} bytes, not a multiple of {PAIR_BYTES}",
                payload.len()
            ));
        }
        Ok(TeamBank { payload })
    }

    pub fn pairs(&self) -> usize {
        self.payload.len() / PAIR_BYTES
    }

    fn mon(&self, at: usize) -> PokemonSet {
        let b = &self.payload[at..at + BYTES_PER_MON];
        let min_atk = b[6] & 1 != 0;
        PokemonSet {
            species: b[0],
            level: b[1],
            moves: [b[2], b[3], b[4], b[5]],
            ivs: [30, if min_atk { 2 } else { 30 }, 30, 30, 30],
            // Only floor(ev/4) enters the stat formula, so the packed quarter is
            // lossless (see the bank's own docstring).
            evs: [b[7].saturating_mul(4), if min_atk { 0 } else { 255 }, 255, 255, 255],
        }
    }

    /// The `i`-th pair, as engine records.
    pub fn pair(&self, i: usize) -> (Vec<[u8; POKEMON_SIZE]>, Vec<[u8; POKEMON_SIZE]>) {
        let base = (i % self.pairs()) * PAIR_BYTES;
        let team = |t: usize| {
            (0..6)
                .map(|j| self.mon(base + t * TEAM_BYTES + j * BYTES_PER_MON).to_bytes())
                .collect()
        };
        (team(0), team(1))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::team::random_team;

    fn tables_stub() -> StaticTables {
        StaticTables {
            species: (0..152)
                .map(|i| crate::tables::SpeciesEntry {
                    base_stats: [50 + (i % 100) as u16; 5],
                    type_1: Some((i % 15) as u8),
                    type_2: None,
                })
                .collect(),
            moves: (0..166)
                .map(|i| crate::tables::MoveEntry {
                    max_pp: 8 + (i % 7) as u16 * 8,
                    ..Default::default()
                })
                .collect(),
            type_chart: [[1.0; crate::tables::N_TYPES]; crate::tables::N_TYPES],
            prior: (0..152).map(|_| None).collect(),
            set_prior: true,
        }
    }

    /// Drives a battle end to end through the ACTION space, never through
    /// `Choice` -- so the mask, the action mapping and the pumping are all
    /// exercised together.
    #[test]
    fn a_battle_plays_out_through_the_action_space() {
        let t = tables_stub();
        for seed in 0..40u64 {
            let p1: Vec<_> = random_team(seed ^ 0xA, true).iter().map(|m| m.to_bytes()).collect();
            let p2: Vec<_> = random_team(seed ^ 0xB, true).iter().map(|m| m.to_bytes()).collect();
            let mut env = Gen1Env::new(seed, &p1, &p2, Player::P1, 3).unwrap();
            let mut rng = seed | 1;
            let mut guard = 0;
            while !env.done() {
                guard += 1;
                assert!(guard < 4000, "battle did not terminate");
                let pick = |env: &Gen1Env, p: Player, rng: &mut u64| -> Option<usize> {
                    let pd = env.pending(p, &t)?;
                    let legal: Vec<usize> =
                        (0..N_ACTIONS).filter(|&a| pd.mask[a]).collect();
                    assert!(!legal.is_empty(), "a pending decision with an empty mask");
                    *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    Some(legal[((*rng >> 33) as usize) % legal.len()])
                };
                let la = pick(&env, Player::P1, &mut rng);
                let oa = pick(&env, Player::P2, &mut rng);
                env.step(&t, la, 0.5, 7, oa).unwrap();
            }
            let ep = env.take_episode();
            assert!(ep.length > 0);
            assert_eq!(ep.obs.len(), ep.length * OBS_DIM);
            assert_eq!(ep.masks.len(), ep.length * N_ACTIONS);
            assert_eq!(ep.actions.len(), ep.length);
            assert_eq!(ep.opp_choice.len(), ep.length * 3);
            assert!([-1.0, 0.0, 1.0].contains(&ep.reward), "reward {}", ep.reward);
            assert!(ep.turns > 0 && ep.turns <= 1000);
            assert_eq!(ep.member, 3);
        }
    }

    #[test]
    fn the_mask_never_offers_a_switch_to_a_fainted_or_active_mon() {
        let t = tables_stub();
        let p1: Vec<_> = random_team(11, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(22, true).iter().map(|m| m.to_bytes()).collect();
        let mut env = Gen1Env::new(5, &p1, &p2, Player::P1, 0).unwrap();
        let mut rng = 99u64;
        let mut checked = 0;
        while !env.done() && checked < 400 {
            for p in [Player::P1, Player::P2] {
                if let Some(pd) = env.pending(p, &t) {
                    let side = env.battle.side(p);
                    let active = side.active_party_index();
                    for i in 0..6 {
                        if pd.mask[i] {
                            assert_ne!(i, active, "the active mon was offered as a switch");
                            assert!(side.party(i).hp() > 0, "a fainted mon was offered");
                        }
                    }
                    // A forced switch offers no move action.
                    if pd.request == Request::Switch {
                        assert!(pd.mask[6..].iter().all(|&m| !m));
                    }
                    checked += 1;
                }
            }
            let pick = |env: &Gen1Env, p: Player, rng: &mut u64| -> Option<usize> {
                let pd = env.pending(p, &t)?;
                let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| pd.mask[a]).collect();
                *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                Some(legal[((*rng >> 33) as usize) % legal.len()])
            };
            let la = pick(&env, Player::P1, &mut rng);
            let oa = pick(&env, Player::P2, &mut rng);
            env.step(&t, la, 0.0, 0, oa).unwrap();
        }
        assert!(checked > 50, "only {checked} masks inspected");
    }

    /// A HARD LOCK is not aliased, so poke-env keeps the locked move at its own
    /// stored slot: `get_action_mask` yields `6 + j`, not `6`
    /// (`singles_env.py:247-251`). The engine offers only `Move(1)` whatever the
    /// slot, so mapping it to action 6 would put the single legal action in the
    /// wrong lane on every two-turn-move release turn.
    #[test]
    fn a_hard_lock_keeps_the_locked_moves_own_action_index() {
        use crate::layout::*;
        let p1: Vec<_> = random_team(31, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(32, true).iter().map(|m| m.to_bytes()).collect();
        let mut b = Battle::new(0x10CC_0001, &p1, &p2);
        b.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
            .unwrap();

        let p = Player::P1;
        let side_at = B_SIDES + p.index() * SIDE_SIZE;
        let active_at = side_at + S_ACTIVE;
        for slot in 0..4usize {
            let mut m = b.clone();
            let locked = m.side(p).active().moves()[slot].0;
            if locked == 0 {
                continue;
            }
            // Charging: a hard lock whose move IS a real member of the moveset.
            let at = active_at + A_VOLATILES;
            let mut w = [0u8; 8];
            w.copy_from_slice(&m.0[at..at + 8]);
            let v = u64::from_le_bytes(w) | (1u64 << V_CHARGING);
            m.0[at..at + 8].copy_from_slice(&v.to_le_bytes());
            m.0[side_at + S_LAST_SELECTED_MOVE] = locked;

            let offered = m.choices(p, Request::Move);
            assert_eq!(offered.len(), 1, "a hard lock offers exactly one choice");
            assert_eq!(offered.get(0), Choice::Move(1));

            let mask = mask_for(&m, p, Request::Move, false);
            let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| mask[a]).collect();
            assert_eq!(
                legal,
                vec![6 + slot],
                "locked move in stored slot {slot} must be action {}",
                6 + slot
            );
            assert_eq!(
                action_to_choice(&m, p, Request::Move, false, 6 + slot),
                Some(Choice::Move(1)),
                "and it must still submit the engine's single forced option"
            );
        }
    }

    /// D25's label names the ENTITY. Under a hard lock the engine hands back
    /// `Move(1)` whatever the stored slot, so a label read off the choice's data
    /// field says "move 1" -- Pound -- on every locked turn.
    #[test]
    fn a_hard_locks_d25_label_names_the_locked_move_not_the_engines_marker() {
        use crate::layout::*;
        let p1: Vec<_> = random_team(31, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(32, true).iter().map(|m| m.to_bytes()).collect();
        let mut b = Battle::new(0x10CC_0001, &p1, &p2);
        b.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
            .unwrap();

        let p = Player::P1;
        let side_at = B_SIDES + p.index() * SIDE_SIZE;
        let mut checked = 0;
        for slot in 0..4usize {
            let mut m = b.clone();
            let locked = m.side(p).active().moves()[slot].0;
            if locked == 0 {
                continue;
            }
            let at = side_at + S_ACTIVE + A_VOLATILES;
            let mut w = [0u8; 8];
            w.copy_from_slice(&m.0[at..at + 8]);
            let v = u64::from_le_bytes(w) | (1u64 << V_CHARGING);
            m.0[at..at + 8].copy_from_slice(&v.to_le_bytes());
            m.0[side_at + S_LAST_SELECTED_MOVE] = locked;

            let offered = m.choices(p, Request::Move);
            assert_eq!(offered.get(0), Choice::Move(1));
            assert_eq!(
                choice_identity(&m, p, false, offered.get(0)),
                (1, locked as i32),
                "a lock in stored slot {slot} must be labelled with its own move id"
            );
            checked += 1;
        }
        assert!(checked >= 2, "only {checked} slots exercised");
    }

    /// The switch label names a SPECIES, and reaching it goes through the
    /// current-order indirection (`order[slot-1]` is a one-based party index) --
    /// the one place a slot could pass for an id undetected, since both live in
    /// 1..=6.
    #[test]
    fn a_switch_label_names_a_live_bench_members_species() {
        let p1: Vec<_> = random_team(41, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(42, true).iter().map(|m| m.to_bytes()).collect();
        let mut b = Battle::new(0x5117_0001, &p1, &p2);
        b.update(Request::Pass, Choice::Pass, Request::Pass, Choice::Pass)
            .unwrap();
        let p = Player::P1;
        let side = b.side(p);
        let active = side.active_party_index();
        let mut seen = 0;
        for c in b.choices(p, Request::Move).iter() {
            let Choice::Switch(d) = c else { continue };
            let (kind, id) = choice_identity(&b, p, false, c);
            assert_eq!(kind, 0);
            let party = side.order()[d as usize - 1] as usize - 1;
            assert_ne!(party, active, "the active is never a switch target");
            assert_eq!(id, side.party(party).species() as i32);
            assert!((1..=151).contains(&id), "species id {id} out of gen 1");
            seen += 1;
        }
        assert_eq!(seen, 5, "five bench members should be switchable at turn 1");
    }

    /// Over real play: every label names an entity the seat could actually have
    /// been shown, and the id distribution is NOT slot-shaped. The second half
    /// is what fails if the choice's data field is emitted as the id -- move
    /// slots are 1..=4 and order slots 1..=6, so a slot-shaped label set is
    /// indistinguishable from a legal one field by field.
    #[test]
    fn every_d25_label_names_an_entity_the_seat_was_offered() {
        let t = tables_stub();
        let mut ids_above_six = 0usize;
        let mut moves = 0usize;
        let mut switches = 0usize;
        let mut sentinels = 0usize;
        for battle in 0..60u64 {
            let p1: Vec<_> = random_team(1000 + battle, true).iter().map(|m| m.to_bytes()).collect();
            let p2: Vec<_> = random_team(2000 + battle, true).iter().map(|m| m.to_bytes()).collect();
            let mut env = Gen1Env::new(0xD25 ^ battle, &p1, &p2, Player::P1, 0).unwrap();
            let mut rng = 7 * battle + 1;
            while !env.done() {
                let pick = |env: &Gen1Env, p: Player, rng: &mut u64| -> Option<usize> {
                    let pd = env.pending(p, &t)?;
                    let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| pd.mask[a]).collect();
                    *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    Some(legal[((*rng >> 33) as usize) % legal.len()])
                };
                let la = pick(&env, Player::P1, &mut rng);
                let oa = pick(&env, Player::P2, &mut rng);

                // The foe's pre-update truth, which the label must be consistent
                // with -- read here because `step` advances the engine.
                let foe = Player::P2;
                let side = env.battle.side(foe);
                let live_moves: Vec<u8> = side
                    .active()
                    .moves()
                    .iter()
                    .filter(|&&(id, pp)| id != 0 && pp > 0)
                    .map(|&(id, _)| id)
                    .collect();
                let bench: Vec<u8> = (0..6)
                    .filter(|&i| i != side.active_party_index() && side.party(i).hp() > 0)
                    .map(|i| side.party(i).species())
                    .collect();
                let locked = side.last_selected_move();
                let n_before = env.ep.opp_choice.len();

                env.step(&t, la, 0.0, 0, oa).unwrap();

                if env.ep.opp_choice.len() == n_before {
                    continue;
                }
                let lbl = &env.ep.opp_choice[n_before..];
                let (kind, id, flags) = (lbl[0], lbl[1], lbl[2]);
                if id > 6 {
                    ids_above_six += 1;
                }
                match kind {
                    // The sentinel: a foe that owed no decision. Whole, or
                    // `canonicalise` treats it as a real one.
                    -1 => {
                        assert_eq!([kind, id, flags], [-1, -1, 0], "a partial sentinel");
                        sentinels += 1;
                    }
                    0 => {
                        assert_eq!(flags & 1, 1, "a real decision is PRESENT");
                        switches += 1;
                        assert!(
                            bench.contains(&(id as u8)),
                            "switch label {id} names no live bench member of {bench:?}"
                        );
                    }
                    1 => {
                        assert_eq!(flags & 1, 1, "a real decision is PRESENT");
                        moves += 1;
                        let ok = id == 0
                            || id == STRUGGLE_ID
                            || id == locked as i32
                            || live_moves.contains(&(id as u8));
                        assert!(
                            ok,
                            "move label {id} (flags {flags}) is neither a live move of \
                             {live_moves:?}, the locked move {locked}, nor a placeholder"
                        );
                    }
                    k => panic!("label kind {k}"),
                }
            }
        }
        assert!(moves > 500 && switches > 20, "{moves} moves / {switches} switches");
        // Wait turns exist (the reference measures 6.4% of raw steps), so a
        // run with none would mean the sentinel path is untested here.
        assert!(sentinels > 0, "no wait turn in {} steps", moves + switches);
        // Species run to 151 and moves to 165; slots stop at 6. Emitting the
        // choice's data field puts EVERY label in 1..=6.
        let n = moves + switches;
        assert!(
            ids_above_six * 2 > n,
            "only {ids_above_six} of {n} labels exceed 6 -- these look like slots"
        );
    }

    #[test]
    fn an_illegal_action_is_refused_not_passed_to_the_engine() {
        let t = tables_stub();
        let p1: Vec<_> = random_team(3, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(4, true).iter().map(|m| m.to_bytes()).collect();
        let mut env = Gen1Env::new(1, &p1, &p2, Player::P1, 0).unwrap();
        let pd = env.pending(Player::P1, &t).unwrap();
        let illegal = (0..N_ACTIONS).find(|&a| !pd.mask[a]).unwrap();
        let err = env.step(&t, Some(illegal), 0.0, 0, Some(6)).unwrap_err();
        assert!(err.contains("not legal"), "{err}");
    }

    #[test]
    fn the_learner_seat_flips_the_reward_not_the_game() {
        let t = tables_stub();
        let p1: Vec<_> = random_team(7, true).iter().map(|m| m.to_bytes()).collect();
        let p2: Vec<_> = random_team(8, true).iter().map(|m| m.to_bytes()).collect();
        let mut rewards = Vec::new();
        for learner in [Player::P1, Player::P2] {
            let mut env = Gen1Env::new(1234, &p1, &p2, learner, 0).unwrap();
            let mut rng = 42u64;
            while !env.done() {
                let act = |p: Player, rng: &mut u64| -> Option<usize> {
                    let pd = env.pending(p, &t)?;
                    let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| pd.mask[a]).collect();
                    *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                    Some(legal[((*rng >> 33) as usize) % legal.len()])
                };
                let (a1, a2) = (act(Player::P1, &mut rng), act(Player::P2, &mut rng));
                let (la, oa) = if learner == Player::P1 { (a1, a2) } else { (a2, a1) };
                env.step(&t, la, 0.0, 0, oa).unwrap();
            }
            rewards.push(env.take_episode().reward);
        }
        // Same seed, same teams, same RNG stream -- the same game, scored from
        // opposite seats.
        assert_eq!(rewards[0], -rewards[1], "seat flip must negate the reward");
    }
}

// ---------------------------------------------------------------------------
// BatchEnv: K battles driven together (plan §7.6).
// ---------------------------------------------------------------------------

/// Which seat a pending decision belongs to.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Seat {
    Learner,
    Opponent,
}

#[derive(Clone, Debug, Default)]
pub struct BatchStats {
    pub episodes_finished: u64,
    pub learner_decisions: u64,
    pub opponent_decisions: u64,
    pub engine_updates: u64,
    pub battles_started: u64,
}

pub struct BatchEnv {
    slots: Vec<Gen1Env>,
    tables: StaticTables,
    bank: TeamBank,
    lane_seed: u64,
    battle_counter: u64,
    learner: Player,
    finished: Vec<Episode>,
    /// The scripted opponents' draw stream (`scripted.rs`), seeded off the lane
    /// seed so an in-engine eval replays exactly.
    scripted_rng: u64,
    pub stats: BatchStats,
}

impl BatchEnv {
    /// `battle_counter` is where in the lane's battle sequence to START. It is
    /// a CONSTRUCTOR argument and not only a setter because the k battles in
    /// flight are drawn HERE: a resumed lane that set the counter afterwards
    /// would still replay its first k battles, teams and seeds included, before
    /// the counter had any effect.
    pub fn new(
        k: usize,
        lane_seed: u64,
        tables: StaticTables,
        bank: TeamBank,
        learner: Player,
        battle_counter: u64,
    ) -> Result<BatchEnv, String> {
        if k == 0 {
            return Err("BatchEnv needs at least one slot".into());
        }
        let mut env = BatchEnv {
            slots: Vec::with_capacity(k),
            tables,
            bank,
            lane_seed,
            battle_counter,
            learner,
            finished: Vec::new(),
            scripted_rng: lane_seed ^ 0x5343_5249_5054_4544,
            stats: BatchStats::default(),
        };
        for _ in 0..k {
            let b = env.fresh()?;
            env.slots.push(b);
        }
        Ok(env)
    }

    /// `battle_seed = splitmix64(lane_seed * PHI ^ battle_counter)`, with the
    /// team pair drawn at `splitmix64(battle_seed ^ 1)` (plan §7.5). The counter
    /// is exposed so a `--resume` can continue the same sequence.
    fn fresh(&mut self) -> Result<Gen1Env, String> {
        let n = self.battle_counter;
        self.battle_counter += 1;
        let seed = crate::battle::splitmix64(
            self.lane_seed
                .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                ^ n,
        );
        let pick = crate::battle::splitmix64(seed ^ 1) as usize;
        let (p1, p2) = self.bank.pair(pick % self.bank.pairs());
        self.stats.battles_started += 1;
        Gen1Env::new(seed, &p1, &p2, self.learner, -1).map_err(|e| e.to_string())
    }

    pub fn battle_counter(&self) -> u64 {
        self.battle_counter
    }
    pub fn set_battle_counter(&mut self, n: u64) {
        self.battle_counter = n;
    }
    pub fn len(&self) -> usize {
        self.slots.len()
    }
    pub fn is_empty(&self) -> bool {
        self.slots.is_empty()
    }
    pub fn tables(&self) -> &StaticTables {
        &self.tables
    }
    pub fn set_member(&mut self, slot: usize, member: i32) {
        if let Some(s) = self.slots.get_mut(slot) {
            s.member = member;
            s.ep.member = member;
        }
    }

    /// Every slot where `seat` owes a real decision, with its observation and
    /// mask. Slots owing only a Pass are absent, which is what makes a Pass turn
    /// cost the caller nothing.
    pub fn pending(&self, seat: Seat) -> (Vec<i32>, Vec<f32>, Vec<bool>, Vec<i32>) {
        let who = match seat {
            Seat::Learner => self.learner,
            Seat::Opponent => self.learner.foe(),
        };
        let mut idx = Vec::new();
        let mut obs = Vec::new();
        let mut mask = Vec::new();
        let mut member = Vec::new();
        for (i, s) in self.slots.iter().enumerate() {
            if let Some(p) = s.pending(who, &self.tables) {
                idx.push(i as i32);
                obs.extend_from_slice(&p.obs);
                mask.extend(p.mask);
                member.push(s.member());
            }
        }
        (idx, obs, mask, member)
    }

    /// One batched step. Every slot with a pending decision for either seat must
    /// appear in the corresponding index list.
    pub fn step(
        &mut self,
        l_idx: &[i32],
        l_actions: &[usize],
        l_logp: &[f32],
        version: i64,
        o_idx: &[i32],
        o_actions: &[usize],
    ) -> Result<(), String> {
        if l_idx.len() != l_actions.len() || l_idx.len() != l_logp.len() {
            return Err("learner idx/actions/logp lengths disagree".into());
        }
        if o_idx.len() != o_actions.len() {
            return Err("opponent idx/actions lengths disagree".into());
        }
        let k = self.slots.len();
        let mut la: Vec<Option<usize>> = vec![None; k];
        let mut lp: Vec<f32> = vec![0.0; k];
        let mut oa: Vec<Option<usize>> = vec![None; k];
        for (n, &i) in l_idx.iter().enumerate() {
            let i = i as usize;
            if i >= k {
                return Err(format!("learner slot {i} out of range"));
            }
            la[i] = Some(l_actions[n]);
            lp[i] = l_logp[n];
        }
        for (n, &i) in o_idx.iter().enumerate() {
            let i = i as usize;
            if i >= k {
                return Err(format!("opponent slot {i} out of range"));
            }
            oa[i] = Some(o_actions[n]);
        }

        for i in 0..k {
            let s = &mut self.slots[i];
            if s.done() {
                continue;
            }
            // Every seat owing a decision must have been given one: a silently
            // skipped slot would stall forever, which is the shape F-03 exists
            // to catch.
            let needs_l = s.request(self.learner) != Request::Pass;
            let needs_o = s.request(self.learner.foe()) != Request::Pass;
            if needs_l && la[i].is_none() {
                return Err(format!("slot {i}: the learner owes a decision, none given"));
            }
            if needs_o && oa[i].is_none() {
                return Err(format!("slot {i}: the opponent owes a decision, none given"));
            }
            if needs_l {
                self.stats.learner_decisions += 1;
            }
            if needs_o {
                self.stats.opponent_decisions += 1;
            }
            s.step(&self.tables, la[i], lp[i], version, oa[i])
                .map_err(|e| format!("slot {i}: {e}"))?;
            self.stats.engine_updates += 1;
        }

        // Restart finished slots immediately; whole episodes only, exactly as the
        // async path does.
        for i in 0..k {
            if self.slots[i].done() {
                let next = self.fresh()?;
                let done = std::mem::replace(&mut self.slots[i], next);
                let mut ep = done.take_episode();
                ep.slot = i as i32;
                self.finished.push(ep);
                self.stats.episodes_finished += 1;
            }
        }
        Ok(())
    }

    /// What a SCRIPTED policy would do at every slot where `seat` owes a
    /// decision (plan §8.2). For gate D-1 and for `rl/envs/engine_env.py`'s
    /// opponent — never for a training arm.
    ///
    /// The state is rebuilt here rather than taken from `pending()`, so the
    /// policy is a pure function of the same projection the encoder reads and
    /// cannot see anything the observation does not.
    pub fn scripted_actions(&mut self, seat: Seat, policy: Scripted) -> (Vec<i32>, Vec<usize>) {
        let who = match seat {
            Seat::Learner => self.learner,
            Seat::Opponent => self.learner.foe(),
        };
        let mut idx = Vec::new();
        let mut actions = Vec::new();
        for i in 0..self.slots.len() {
            let s = &self.slots[i];
            let Some(p) = s.pending(who, &self.tables) else { continue };
            let st = s.state(who, &self.tables);
            idx.push(i as i32);
            actions.push(policy.act(&st, &p.mask, &self.tables, &mut self.scripted_rng));
        }
        (idx, actions)
    }

    /// Gate D-1's engine leg (`scripted.rs::scripted_series`), sharing this
    /// lane's seed and team bank so a D-1 leg plays the same battles a
    /// collector lane at the same seed would.
    pub fn scripted_series(
        &self,
        n: u64,
        p1: Scripted,
        p2: Scripted,
    ) -> Result<Vec<crate::scripted::BattleSummary>, String> {
        crate::scripted::scripted_series(n, self.lane_seed, &self.tables, &self.bank, p1, p2)
    }

    pub fn drain_finished(&mut self) -> Vec<Episode> {
        std::mem::take(&mut self.finished)
    }
}

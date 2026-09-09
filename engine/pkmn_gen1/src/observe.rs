//! The OBSERVABLE state -- invariant I1 (plan §7.1).
//!
//! This struct is the whole interface between "what happened in the battle" and
//! "what the agent sees". It carries exactly what a Showdown client could know
//! from the protocol and the `|request|` JSON for one seat, and nothing else:
//! no sleep counter, no confusion turns, no Substitute HP, no opponent PP, no
//! `last_damage`, no RNG seed. `layout.rs` can read all of those; the encoder
//! never sees them because they never enter here.
//!
//! Two producers fill it, and that is the point:
//!   - gate P-1 fills it from a poke-env `Battle` replayed off a tape, so the
//!     Rust encoder can be compared bitwise against `embed_battle`; and
//!   - `env.rs` (later) fills it by diffing the engine's 384 bytes.
//! One struct, one encoder, so the two paths cannot drift.

/// One party member as this seat's client knows it.
#[derive(Clone, Copy, Debug, Default)]
pub struct MonView {
    /// False for a party slot this seat has not seen (opponent, unrevealed).
    pub present: bool,
    /// Dex number 1..151; 0 = unknown. This is the IDENTITY -- what the id
    /// suffix carries.
    pub species: u8,
    /// Base stats as this seat currently observes them, in the encoder's order
    /// (hp, atk, def, spa, spe). Carried EXPLICITLY rather than looked up from
    /// `species`, because Transform copies the target's stats and types while
    /// the mon keeps its own name -- poke-env swaps `base_stats`/`types` and
    /// leaves `_species` alone (`pokemon.py:625-636`), and the engine writes
    /// the copied species into `ActivePokemon.species` while `Pokemon.species`
    /// keeps the original. Making the producer state which stats apply removes
    /// a whole class of silent disagreement.
    pub base_stats: [u16; super::tables::N_BASE_STATS],
    /// ALPHABETICAL type indices as observed. `type_2` is `None` for a
    /// mono-type mon: poke-env's `damage_multiplier` takes ONE chart lookup in
    /// that case, so repeating the type would square the multiplier.
    pub type_1: Option<u8>,
    pub type_2: Option<u8>,
    /// Own side: `current_hp / max_hp` exactly. Opponent: `pct / 100`, since
    /// Showdown only ever reports the opponent's HP as a percentage.
    pub hp_fraction: f64,
    pub fainted: bool,
    pub is_active: bool,
    /// Index into (BRN, FRZ, PAR, PSN, SLP, TOX); `None` for healthy or FNT
    /// (poke-env's FNT has no encoder slot -- the fainted flag carries it).
    pub status: Option<u8>,
    pub level: u8,
}

/// The active mon's volatile state, as the protocol reveals it.
#[derive(Clone, Copy, Debug, Default)]
pub struct ActiveView {
    /// accuracy, atk, def, evasion, spa, spd, spe.
    pub boosts: [i16; super::tables::N_BOOSTS],
    /// CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE, PARTIALLY_TRAPPED,
    /// REFLECT, SUBSTITUTE. Light Screen has NO slot: poke-env 0.15.0 cannot
    /// parse it, so encoding it anywhere would be a divergence, not a fix.
    pub volatiles: [bool; super::tables::N_VOLATILES],
    /// poke-env's `status_counter`: observed sleep turns, or toxic turns.
    pub status_counter: u16,
    /// Charging a two-turn move.
    pub preparing: bool,
}

/// One move slot of the active mon.
#[derive(Clone, Copy, Debug, Default)]
pub struct MoveView {
    /// Gen-1 move number 1..165; 0 = empty slot.
    pub id: u8,
    /// 1.0 for our own moves and for revealed opponent moves; the set prior's
    /// P(move | revealed) for a prior-filled opponent slot.
    pub prob: f64,
    pub pp: u16,
    pub max_pp: u16,
    /// False for a slot that carries nothing (a 3-move set's fourth slot).
    pub present: bool,
}

/// Everything one seat knows about one side.
#[derive(Clone, Debug, Default)]
pub struct SeatState {
    /// Own side: party order (poke-env's `battle.team`, which is the order the
    /// FIRST `|request|` listed and therefore the order switch actions index).
    /// Opponent: REVEAL order, zero-padded.
    pub team: [MonView; 6],
    /// Index into `team` of the active mon, if any.
    pub active_slot: Option<usize>,
    pub active: ActiveView,
    /// Own side: the active's move slots in stored order. Opponent: revealed
    /// moves first, then prior fills.
    pub moves: [MoveView; 4],
}

impl SeatState {
    pub fn active(&self) -> Option<&MonView> {
        self.active_slot.map(|i| &self.team[i])
    }
    pub fn fainted_count(&self) -> usize {
        self.team.iter().filter(|m| m.present && m.fainted).count()
    }
}

/// A full decision-time observation for one seat.
#[derive(Clone, Debug, Default)]
pub struct ObservableState {
    pub turn: u16,
    pub force_switch: bool,
    pub trapped: bool,
    /// The only legal move-action is one of poke-env's SPECIAL_MOVES
    /// (fight / struggle / recharge), so move slot i stops meaning move i and
    /// the own-move blocks and own-move ids are ZEROED (plan §7.2).
    pub aliased: bool,
    pub own: SeatState,
    pub opp: SeatState,
}

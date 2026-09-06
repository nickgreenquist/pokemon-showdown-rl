//! Typed, read-only views over the engine's 384-byte `Battle` (plan §3.3, §5.4).
//!
//! Every offset here is pinned by `tests/layout.rs`, which parses the vendored
//! `src/data/layout.json` and asserts each constant, plus the two SHOWDOWN-mode
//! overrides that `layout.json` does not document: in showdown mode
//! `MoveDetails` is a `packed struct(u16)` so `last_moves` is 4 bytes wide, which
//! pushes the 8-byte PSRNG seed from 374 to 376
//! (`vendor/pkmn-engine/src/lib/gen1/data.zig:230`, `common/rng.zig:34`).
//!
//! Reading these fields is not the same as being ALLOWED to encode them: the
//! observation is a function of what poke-env could observe (invariant I1, plan
//! §7.1). `observe.rs` owns that projection; this module only decodes bytes.

// ---- Battle (384) --------------------------------------------------------
pub const BATTLE_SIZE: usize = 384;
pub const B_SIDES: usize = 0;
pub const B_TURN: usize = 368;
pub const B_LAST_DAMAGE: usize = 370;
pub const B_LAST_MOVES: usize = 372;
/// SHOWDOWN OVERRIDE: `layout.json` says 374 (the non-showdown 9-byte seed +
/// index form). In showdown mode this is a single u64 PSRNG seed at 376.
pub const B_RNG: usize = 376;
pub const LAST_MOVES_WIDTH: usize = 4;

// ---- Side (184) ----------------------------------------------------------
pub const SIDE_SIZE: usize = 184;
pub const S_POKEMON: usize = 0;
pub const S_ACTIVE: usize = 144;
pub const S_ORDER: usize = 176;
pub const S_LAST_SELECTED_MOVE: usize = 182;
pub const S_LAST_USED_MOVE: usize = 183;

// ---- Pokemon (24) --------------------------------------------------------
pub const POKEMON_SIZE: usize = 24;
pub const P_STATS: usize = 0;
pub const P_MOVES: usize = 10;
pub const P_HP: usize = 18;
pub const P_STATUS: usize = 20;
pub const P_SPECIES: usize = 21;
pub const P_TYPES: usize = 22;
pub const P_LEVEL: usize = 23;

// ---- ActivePokemon (32) --------------------------------------------------
pub const ACTIVE_SIZE: usize = 32;
pub const A_STATS: usize = 0;
pub const A_SPECIES: usize = 10;
pub const A_TYPES: usize = 11;
pub const A_BOOSTS: usize = 12;
pub const A_VOLATILES: usize = 16;
pub const A_MOVES: usize = 24;

// ---- Stats / Boosts field order -----------------------------------------
pub const ST_HP: usize = 0;
pub const ST_ATK: usize = 2;
pub const ST_DEF: usize = 4;
pub const ST_SPE: usize = 6;
pub const ST_SPC: usize = 8;

pub const BO_ATK: u32 = 0;
pub const BO_DEF: u32 = 4;
pub const BO_SPE: u32 = 8;
pub const BO_SPC: u32 = 12;
pub const BO_ACCURACY: u32 = 16;
pub const BO_EVASION: u32 = 20;

// ---- Volatiles (u64) bit offsets ----------------------------------------
pub const V_BIDE: u32 = 0;
pub const V_THRASHING: u32 = 1;
pub const V_MULTI_HIT: u32 = 2;
pub const V_FLINCH: u32 = 3;
pub const V_CHARGING: u32 = 4;
/// Set on the USER of Wrap/Bind/Clamp/Fire Spin, never on the victim.
pub const V_BINDING: u32 = 5;
pub const V_INVULNERABLE: u32 = 6;
pub const V_CONFUSION: u32 = 7;
pub const V_MIST: u32 = 8;
pub const V_FOCUS_ENERGY: u32 = 9;
pub const V_SUBSTITUTE: u32 = 10;
pub const V_RECHARGING: u32 = 11;
pub const V_RAGE: u32 = 12;
pub const V_LEECH_SEED: u32 = 13;
pub const V_TOXIC: u32 = 14;
pub const V_LIGHT_SCREEN: u32 = 15;
pub const V_REFLECT: u32 = 16;
pub const V_TRANSFORM: u32 = 17;
pub const V_CONFUSION_TURNS: u32 = 18; // u3
pub const V_ATTACKS: u32 = 21; // u3
pub const V_STATE: u32 = 24; // u16
pub const V_SUBSTITUTE_HP: u32 = 40; // u8
pub const V_TRANSFORM_ID: u32 = 48; // u4
pub const V_DISABLE_DURATION: u32 = 52; // u4
pub const V_DISABLE_MOVE: u32 = 56; // u3
pub const V_TOXIC_TURNS: u32 = 59; // u5

#[inline]
fn u16le(b: &[u8], at: usize) -> u16 {
    u16::from_le_bytes([b[at], b[at + 1]])
}

/// The five stats the engine stores, in its own order.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Stats {
    pub hp: u16,
    pub atk: u16,
    pub def: u16,
    pub spe: u16,
    pub spc: u16,
}

/// Six stat stages, sign-extended from the packed i4 fields.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Boosts {
    pub atk: i8,
    pub def: i8,
    pub spe: i8,
    pub spc: i8,
    pub accuracy: i8,
    pub evasion: i8,
}

/// The gen 1 status byte (`data.zig::Status`, cartridge encoding).
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct StatusByte(pub u8);

impl StatusByte {
    /// Sleep turns REMAINING. This is HIDDEN information on Showdown -- the
    /// tracker counts observed decrements instead (plan §7.1).
    pub fn sleep_turns_left(self) -> u8 {
        self.0 & 0b111
    }
    pub fn asleep(self) -> bool {
        self.sleep_turns_left() > 0
    }
    pub fn psn(self) -> bool {
        self.0 & (1 << 3) != 0
    }
    pub fn brn(self) -> bool {
        self.0 & (1 << 4) != 0
    }
    pub fn frz(self) -> bool {
        self.0 & (1 << 5) != 0
    }
    pub fn par(self) -> bool {
        self.0 & (1 << 6) != 0
    }
    /// The EXT bit: self-inflicted sleep (Rest, for Sleep Clause) or, with PSN,
    /// the badly-poisoned marker.
    pub fn ext(self) -> bool {
        self.0 & (1 << 7) != 0
    }
    /// `TOX = 0b1000_1000` -- EXT set together with PSN.
    pub fn tox(self) -> bool {
        self.psn() && self.ext()
    }
    /// Sleep that was self-inflicted (Rest): EXT set with a sleep duration.
    pub fn self_inflicted_sleep(self) -> bool {
        self.ext() && self.asleep()
    }
    pub fn healthy(self) -> bool {
        self.0 == 0
    }
}

/// The u64 volatiles word.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Volatiles(pub u64);

macro_rules! vflag {
    ($name:ident, $bit:expr) => {
        #[inline]
        pub fn $name(self) -> bool {
            self.0 & (1u64 << $bit) != 0
        }
    };
}

impl Volatiles {
    vflag!(bide, V_BIDE);
    vflag!(thrashing, V_THRASHING);
    vflag!(multi_hit, V_MULTI_HIT);
    vflag!(flinch, V_FLINCH);
    vflag!(charging, V_CHARGING);
    vflag!(binding, V_BINDING);
    vflag!(invulnerable, V_INVULNERABLE);
    vflag!(confusion, V_CONFUSION);
    vflag!(mist, V_MIST);
    vflag!(focus_energy, V_FOCUS_ENERGY);
    vflag!(substitute, V_SUBSTITUTE);
    vflag!(recharging, V_RECHARGING);
    vflag!(rage, V_RAGE);
    vflag!(leech_seed, V_LEECH_SEED);
    vflag!(toxic, V_TOXIC);
    vflag!(light_screen, V_LIGHT_SCREEN);
    vflag!(reflect, V_REFLECT);
    vflag!(transform, V_TRANSFORM);

    #[inline]
    fn field(self, off: u32, width: u32) -> u64 {
        (self.0 >> off) & ((1u64 << width) - 1)
    }
    /// Confusion turns remaining -- HIDDEN on Showdown; never encoded.
    pub fn confusion_turns(self) -> u8 {
        self.field(V_CONFUSION_TURNS, 3) as u8
    }
    /// Thrash/Bide/multi-hit attacks left -- HIDDEN; never encoded.
    pub fn attacks(self) -> u8 {
        self.field(V_ATTACKS, 3) as u8
    }
    /// Bide accumulated damage / overwritten accuracy -- HIDDEN.
    pub fn state(self) -> u16 {
        self.field(V_STATE, 16) as u16
    }
    /// Substitute HP -- HIDDEN (PS reveals only that a Substitute exists).
    pub fn substitute_hp(self) -> u8 {
        self.field(V_SUBSTITUTE_HP, 8) as u8
    }
    pub fn transform_id(self) -> u8 {
        self.field(V_TRANSFORM_ID, 4) as u8
    }
    /// Disable duration -- HIDDEN.
    pub fn disable_duration(self) -> u8 {
        self.field(V_DISABLE_DURATION, 4) as u8
    }
    /// One-based disabled move slot, 0 when nothing is disabled. Known to the
    /// OWNER (the request omits the move); hidden to the foe.
    pub fn disable_move(self) -> u8 {
        self.field(V_DISABLE_MOVE, 3) as u8
    }
    /// Turns of toxic damage taken so far -- VISIBLE (one `|-damage| [from] psn`
    /// per turn); this is poke-env's TOX `status_counter`.
    pub fn toxic_turns(self) -> u8 {
        self.field(V_TOXIC_TURNS, 5) as u8
    }
}

/// A stored party member, 24 bytes, in its ORIGINAL party order.
#[derive(Clone, Copy)]
pub struct PokemonView<'a>(pub &'a [u8]);

impl<'a> PokemonView<'a> {
    pub fn stats(&self) -> Stats {
        let b = self.0;
        Stats {
            hp: u16le(b, P_STATS + ST_HP),
            atk: u16le(b, P_STATS + ST_ATK),
            def: u16le(b, P_STATS + ST_DEF),
            spe: u16le(b, P_STATS + ST_SPE),
            spc: u16le(b, P_STATS + ST_SPC),
        }
    }
    /// The ORIGINAL stored move slots: `(move id, pp)`. Transform rewrites the
    /// ACTIVE slots, not these.
    pub fn moves(&self) -> [(u8, u8); 4] {
        let b = self.0;
        std::array::from_fn(|i| (b[P_MOVES + 2 * i], b[P_MOVES + 2 * i + 1]))
    }
    pub fn hp(&self) -> u16 {
        u16le(self.0, P_HP)
    }
    pub fn status(&self) -> StatusByte {
        StatusByte(self.0[P_STATUS])
    }
    pub fn species(&self) -> u8 {
        self.0[P_SPECIES]
    }
    /// `(type1, type2)` as engine `Type` values (cartridge order); type1 is the
    /// low nibble. A mono-type mon repeats its type.
    pub fn types(&self) -> (u8, u8) {
        let t = self.0[P_TYPES];
        (t & 0x0F, t >> 4)
    }
    pub fn level(&self) -> u8 {
        self.0[P_LEVEL]
    }
    /// True for an empty party slot (species None).
    pub fn is_empty(&self) -> bool {
        self.species() == 0
    }
    pub fn fainted(&self) -> bool {
        self.hp() == 0
    }
}

/// The active Pokémon's volatile state, 32 bytes.
#[derive(Clone, Copy)]
pub struct ActiveView<'a>(pub &'a [u8]);

impl<'a> ActiveView<'a> {
    /// MODIFIED stats (boosts already applied by the engine).
    pub fn stats(&self) -> Stats {
        let b = self.0;
        Stats {
            hp: u16le(b, A_STATS + ST_HP),
            atk: u16le(b, A_STATS + ST_ATK),
            def: u16le(b, A_STATS + ST_DEF),
            spe: u16le(b, A_STATS + ST_SPE),
            spc: u16le(b, A_STATS + ST_SPC),
        }
    }
    pub fn species(&self) -> u8 {
        self.0[A_SPECIES]
    }
    pub fn types(&self) -> (u8, u8) {
        let t = self.0[A_TYPES];
        (t & 0x0F, t >> 4)
    }
    pub fn boosts(&self) -> Boosts {
        let w = u32::from_le_bytes([
            self.0[A_BOOSTS],
            self.0[A_BOOSTS + 1],
            self.0[A_BOOSTS + 2],
            self.0[A_BOOSTS + 3],
        ]);
        let f = |off: u32| -> i8 {
            let n = ((w >> off) & 0xF) as u8;
            // sign-extend the i4
            if n & 0x8 != 0 { (n as i8) - 16 } else { n as i8 }
        };
        Boosts {
            atk: f(BO_ATK),
            def: f(BO_DEF),
            spe: f(BO_SPE),
            spc: f(BO_SPC),
            accuracy: f(BO_ACCURACY),
            evasion: f(BO_EVASION),
        }
    }
    pub fn volatiles(&self) -> Volatiles {
        let mut w = [0u8; 8];
        w.copy_from_slice(&self.0[A_VOLATILES..A_VOLATILES + 8]);
        Volatiles(u64::from_le_bytes(w))
    }
    /// The LIVE move slots: what the mon can actually select right now.
    /// Transform overwrites these with the copied moves at 5 PP.
    pub fn moves(&self) -> [(u8, u8); 4] {
        let b = self.0;
        std::array::from_fn(|i| (b[A_MOVES + 2 * i], b[A_MOVES + 2 * i + 1]))
    }
}

/// One player's side, 184 bytes.
#[derive(Clone, Copy)]
pub struct SideView<'a>(pub &'a [u8]);

impl<'a> SideView<'a> {
    /// Party member `i` (0..6) in ORIGINAL order -- the order poke-env's
    /// `battle.team` dict is filled in, hence the order actions 0..5 index
    /// (plan §7.2).
    pub fn party(&self, i: usize) -> PokemonView<'a> {
        debug_assert!(i < 6);
        PokemonView(&self.0[S_POKEMON + i * POKEMON_SIZE..S_POKEMON + (i + 1) * POKEMON_SIZE])
    }
    pub fn active(&self) -> ActiveView<'a> {
        ActiveView(&self.0[S_ACTIVE..S_ACTIVE + ACTIVE_SIZE])
    }
    /// `order[slot-1]` is the ONE-BASED party index currently in that slot;
    /// 0 marks an unused slot. Slot 1 is the active.
    pub fn order(&self) -> [u8; 6] {
        let mut o = [0u8; 6];
        o.copy_from_slice(&self.0[S_ORDER..S_ORDER + 6]);
        o
    }
    /// Zero-based party index of the active mon.
    pub fn active_party_index(&self) -> usize {
        (self.order()[0] as usize).saturating_sub(1)
    }
    /// The one-based CURRENT-ORDER slot holding party index `i`, for building a
    /// `Choice::Switch`. `None` if that party member is not in the order.
    pub fn slot_of_party_index(&self, i: usize) -> Option<u8> {
        let want = (i + 1) as u8;
        self.order()
            .iter()
            .position(|&p| p == want)
            .map(|s| (s + 1) as u8)
    }
    pub fn last_selected_move(&self) -> u8 {
        self.0[S_LAST_SELECTED_MOVE]
    }
    pub fn last_used_move(&self) -> u8 {
        self.0[S_LAST_USED_MOVE]
    }
    /// How many party slots hold a real Pokémon.
    pub fn party_len(&self) -> usize {
        (0..6).take_while(|&i| !self.party(i).is_empty()).count()
    }
}

/// Read-only view over the whole 384-byte battle.
#[derive(Clone, Copy)]
pub struct BattleView<'a>(pub &'a [u8]);

impl<'a> BattleView<'a> {
    pub fn side(&self, p: usize) -> SideView<'a> {
        debug_assert!(p < 2);
        SideView(&self.0[B_SIDES + p * SIDE_SIZE..B_SIDES + (p + 1) * SIDE_SIZE])
    }
    pub fn turn(&self) -> u16 {
        u16le(self.0, B_TURN)
    }
    /// HIDDEN: never encoded (plan §7.1).
    pub fn last_damage(&self) -> u16 {
        u16le(self.0, B_LAST_DAMAGE)
    }
    /// `(index, counterable)` for player `p`; showdown mode stores each as a
    /// full byte. HIDDEN: never encoded.
    pub fn last_moves(&self, p: usize) -> (u8, u8) {
        (self.0[B_LAST_MOVES + 2 * p], self.0[B_LAST_MOVES + 2 * p + 1])
    }
    /// The PSRNG seed. HIDDEN: never encoded; used only for reproducibility.
    pub fn seed(&self) -> u64 {
        let mut w = [0u8; 8];
        w.copy_from_slice(&self.0[B_RNG..B_RNG + 8]);
        u64::from_le_bytes(w)
    }
}

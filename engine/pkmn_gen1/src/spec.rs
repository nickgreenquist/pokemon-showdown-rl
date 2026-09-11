//! The WRITE-SIDE BRIDGE: a client-knowable description of a mid-battle state,
//! assembled into the engine's 384 bytes (`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §2).
//!
//! `layout.rs` decodes bytes and now also writes them; this module decides WHAT
//! to write. The distinction matters: §2's whole argument is about the
//! INFORMATION BOUNDARY, and a byte writer cannot enforce one.
//!
//! ### The classes, and why the defaults are spelled out
//!
//! §2.4 sorts every field of the layout into
//! **K** known exactly from the client's own view, **D** determinized,
//! **S** hidden even from the opponent's own client, **F** free (unobservable
//! and provably irrelevant) and **V** vacuous in `gen1randombattle` (§2.5's pool
//! census). Only K and D can be filled honestly; every S and F field needs a
//! stated rule, and **a silent zero is the failure mode** — three of them are
//! not merely inexact but ILLEGAL or undefined (`last_moves.index` under
//! Charging, `confusion_turns` under Confusion, `substitute` HP under
//! Substitute). Every default below is therefore a named constant with the
//! engine line that forces it.
//!
//! ### What this module is NOT
//!
//! It is not the poke-env → spec mapping. That is the Python half
//! (`rl/search/engine_bridge.py`, Phase 1's other block) and it is where the
//! determinizer, the HP quantisation and the reveal order live. This module
//! takes a spec as given and produces bytes the engine will accept, or an error
//! naming the field. It never repairs.

use crate::battle::{Battle, Player, Request};
use crate::data;
use crate::layout::{
    self, BattleViewMut, Boosts, SideViewMut, Stats, StatusByte, Volatiles,
};
use crate::team::PokemonSet;

// =============================================================================
// Errors -- W-VALIDATE's output. Copy, and it never allocates: the error path
// must be usable from the batched leaf loop (§4), which runs millions of times.
// =============================================================================

/// A named write-side invariant violation. **Never a panic and never a silent
/// repair** — §2.4's W-VALIDATE exists to "convert every write-side bug into a
/// loud error", which means the caller must be able to see WHICH field.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct SpecError {
    /// `Some(0)` / `Some(1)` for P1 / P2; `None` for a battle-level field.
    pub side: Option<u8>,
    /// Party slot, move slot or order slot — whichever `field` indexes.
    pub slot: Option<u8>,
    /// The offending field, named as `layout.rs` and §2.4 name it.
    pub field: &'static str,
    pub problem: &'static str,
    /// The value found, and the bound it broke. Both are informational; the
    /// test surface asserts on `field`.
    pub value: i64,
    pub limit: i64,
}

impl SpecError {
    #[inline]
    fn at(side: Option<u8>, slot: Option<u8>, field: &'static str, problem: &'static str, value: i64, limit: i64) -> SpecError {
        SpecError { side, slot, field, problem, value, limit }
    }
    #[inline]
    fn battle(field: &'static str, problem: &'static str, value: i64, limit: i64) -> SpecError {
        SpecError::at(None, None, field, problem, value, limit)
    }
    #[inline]
    fn side(p: usize, field: &'static str, problem: &'static str, value: i64, limit: i64) -> SpecError {
        SpecError::at(Some(p as u8), None, field, problem, value, limit)
    }
    #[inline]
    fn slot(p: usize, slot: usize, field: &'static str, problem: &'static str, value: i64, limit: i64) -> SpecError {
        SpecError::at(Some(p as u8), Some(slot as u8), field, problem, value, limit)
    }
}

impl std::fmt::Display for SpecError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self.side {
            Some(p) => write!(f, "p{}", p + 1)?,
            None => write!(f, "battle")?,
        }
        if let Some(s) = self.slot {
            write!(f, "[{s}]")?;
        }
        write!(f, ".{} = {}: {} (bound {})", self.field, self.value, self.problem, self.limit)
    }
}

impl std::error::Error for SpecError {}

// =============================================================================
// The named defaults. Each is an S- or F-class field with no client-visible
// value; each carries the rule §2.4 states and the engine line behind it.
// =============================================================================

/// **W-LASTDMG**, `B_LAST_DAMAGE`. §2.4: "0 when no damage is attributable".
/// Read by Counter, which 27 of 146 pool species carry — live, not vacuous.
pub const DEFAULT_LAST_DAMAGE: u16 = 0;

/// **W-LASTDMG**, `B_LAST_MOVES[p].index` — the one-based LIVE move slot.
/// **1, never 0.** `switchIn` writes 1 (`mechanics.zig:238`), and 0 is not a
/// small error: on the release turn of a two-turn move the engine RECOVERS the
/// slot from this byte (`mechanics.zig:439-443`) and hands it to
/// `ActivePokemon.move`, which asserts `mslot > 0` (`data.zig:179-184`). That
/// assert never fires here: `build.rs:220` pins `-Doptimize=ReleaseFast` in
/// EVERY profile, cargo debug included, so the read is an unconditional
/// `moves[-1]`. See `VolatileSpec::charging`.
pub const DEFAULT_LAST_MOVE_INDEX: u8 = 1;

/// **W-LASTDMG**, `B_LAST_MOVES[p].counterable`.
pub const DEFAULT_LAST_MOVE_COUNTERABLE: bool = false;

/// **W-LASTMOVE**, `S_LAST_SELECTED_MOVE`. 0 = `Move.None`, which is SAFE
/// everywhere the pool can reach: the only readers that cannot take a 0 are
/// Bide and Binding (`mechanics.zig:3211`), both of which §2.5 measures at 0
/// pool species, and Charging, which `VolatileSpec::charging` supplies instead.
pub const DEFAULT_LAST_SELECTED_MOVE: u8 = 0;

/// **W-LASTMOVE**, `S_LAST_USED_MOVE`. 0 is not merely a default — it is EXACT
/// after any switch or faint, both of which clear it for BOTH sides
/// (`mechanics.zig:240-241`, `:1564-1565`). It is a guess only mid-turn, where
/// Mirror Move (4 of 146 pool species) reads it.
pub const DEFAULT_LAST_USED_MOVE: u8 = 0;

/// **W-CONF**, `V_CONFUSION_TURNS`. §2.4's rule is "sample 1-4 per
/// determinization", and sampling is the CALLER's job — this exists so an
/// unsampled spec is a stated choice rather than an invalid state. It may not
/// be 0: `mechanics.zig:577` asserts `confusion > 0` whenever the flag is set,
/// and showdown-mode durations are drawn from `range(u3, 2, 6)`
/// (`mechanics.zig:3013`), so 1..=5 is the reachable band.
pub const DEFAULT_CONFUSION_TURNS: u8 = 2;

/// **W-DISABLE**, `V_DISABLE_DURATION`. A family §2.4 does not name, because it
/// classes Disable as **V** — correct for `gen1randombattle` (0 pool species,
/// §2.5) and NOT correct as a statement about the field. `disable_move` is
/// owner-visible (the `|request|` omits the move) and DROPPING IT CHANGES THE
/// LEGAL ACTION SET: `choices()` skips `disable_move == slot`
/// (`mechanics.zig:3231`), which is R1-E leg C's hard stop, not a residual.
/// The duration is genuinely hidden; showdown draws it from `range(u4, 1, 9)`
/// (`mechanics.zig:2997`), so 4 is the midpoint. It may not be 0 while
/// `disable_move` is set: `beforeMove` only clears the disable inside
/// `if (disable_duration > 0)` (`mechanics.zig:552-563`), so a 0 duration
/// disables the move FOREVER.
pub const DEFAULT_DISABLE_DURATION: u8 = 4;

/// **W-SLEEP**, the sleep duration in `P_STATUS` bits 0-2. What the client has
/// is `sleep_observed` (poke-env's `status_counter`), never the remaining
/// count; §2.4's rule is to sample from the gen-1 sleep distribution once per
/// determinization. 2 is the stated default for an unsampled spec. It may not
/// be 0 — `StatusByte::asleep()` IS `turns > 0`, so 0 means "awake".
pub const DEFAULT_SLEEP_TURNS_LEFT: u8 = 2;

/// The engine's own boost table (`mechanics.zig:34-48`), PORTED AS DATA rather
/// than re-derived, per §2.6. Indexed by `stage + 6`; `(numerator, denominator)`.
pub const BOOSTS: [(u32, u32); 13] = [
    (25, 100), // -6
    (28, 100), // -5
    (33, 100), // -4
    (40, 100), // -3
    (50, 100), // -2
    (66, 100), // -1
    (1, 1),    //  0
    (15, 10),  // +1
    (2, 1),    // +2
    (25, 10),  // +3
    (3, 1),    // +4
    (35, 10),  // +5
    (4, 1),    // +6
];

/// `mechanics.zig:52`.
pub const MAX_STAT_VALUE: u16 = 999;

/// `mechanics.zig::statusModify` (`:2698-2703`). PAR divides the ALREADY
/// MODIFIED speed; BRN the already modified attack.
#[inline]
pub fn status_modify(status: StatusByte, s: &mut Stats) {
    if status.par() {
        s.spe = (s.spe / 4).max(1);
    } else if status.brn() {
        s.atk = (s.atk / 2).max(1);
    }
}

/// Rule **W-ACTIVESTATS** (§2.6), the hardest field in the bridge.
///
/// `ActivePokemon.stats` holds the MODIFIED stats and is PATH-DEPENDENT:
/// a boost recomputes from the stored stats and does NOT re-apply the boosting
/// side's own status modifier (`mechanics.zig:2508-2510`, gen 1's "Agility
/// cures the paralysis speed drop" glitch), while paralysis and burn, when they
/// LAND, divide the already-modified stat (`:2229-2230, 2251-2252`). So
/// `(stored stats, stages, status)` does not determine `active.stats`:
/// Agility-then-Thunder-Wave gives `spe = stored·2/4`, Thunder-Wave-then-Agility
/// gives `spe = stored·2`, and the two states have IDENTICAL public
/// descriptions.
///
/// **CORRECTION TO §2.6, found by building against the engine rather than
/// reading it.** §2.6 says the rule "is exact when there are no boosts" and
/// bounds its error by the boost × PAR/BRN INTERSECTION, 2.26% of opponent
/// roots. That is **false**, and the true domain is wider:
///
/// `statusModify` is re-applied to the DEFENDER's already-modified active stats
/// at the end of **every** stat change, by BOTH sites — `boost` re-applies it
/// to `battle.foe(player)` (`mechanics.zig:2580-2581`) and `unboost` to its own
/// target (`:2688-2689`). The engine labels both "GLITCH: Stat modification
/// errors glitch". So a paralysed mon's `active.stats.spe` is divided by 4
/// AGAIN every time its opponent uses a stat move, with no boost of its own and
/// nothing visible in its public description. Measured here: stored spe 188,
/// no boosts, PAR → the engine holds 11 (188/4/4) where this rule gives 47.
///
/// The honest statement is therefore: **exact iff the active is neither
/// paralysed nor burned** (then `statusModify` is a no-op and the rule is
/// literally `switchIn`'s output plus boosts, `mechanics.zig:243-250`).
/// With PAR or BRN it is exact only if the active has no boosts of its own AND
/// no stat change has been applied to it since it switched in — which is
/// HISTORY, and unobservable from a root. The upper bound on incidence is
/// §2.5's "opp active PAR or BRN", **24.38%** of roots, not 2.26%.
///
/// It is also wrong under Transform, which copies the FOE's ACTIVE (already
/// modified) stats (`mechanics.zig:2450-2453`) — which is why
/// `ActiveSpec::stats` is REQUIRED when `VolatileSpec::transform` is set.
///
/// Blast radius: the encoder does not read `active.stats` (`_spe_est` derives
/// speed from base stats, level, stage and the PAR flag, `encoder.rs:101-118`),
/// so only the engine's turn order and damage see it.
#[inline]
pub fn active_stats(stored: Stats, boosts: Boosts, status: StatusByte) -> Stats {
    #[inline]
    fn boosted(v: u16, stage: i8) -> u16 {
        let (n, d) = BOOSTS[(stage + 6) as usize];
        ((v as u32 * n) / d).min(MAX_STAT_VALUE as u32) as u16
    }
    let mut s = Stats {
        // HP is never boosted and never status-modified; `switchIn` copies it
        // straight across with the rest of the struct.
        hp: stored.hp,
        atk: boosted(stored.atk, boosts.atk),
        def: boosted(stored.def, boosts.def),
        spe: boosted(stored.spe, boosts.spe),
        spc: boosted(stored.spc, boosts.spc),
    };
    status_modify(status, &mut s);
    s
}

// =============================================================================
// The spec
// =============================================================================

/// One party member as a client can know it (§2.4, `Pokemon`).
///
/// Stats and types are carried **EXPLICITLY, not looked up from the species**.
/// That is gate P-1's second hard-won lesson (`docs/engine_port/NOTES.md`,
/// "Base stats and types are carried EXPLICITLY"): Transform separates identity
/// from stats, and making the PRODUCER state which stats apply removes a whole
/// class of silent disagreement.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct MonSpec {
    /// Dex number 1..=151; **0 marks an EMPTY party slot**. B-0 proved engine
    /// species 1..151 ≡ poke-env `num` (`env.rs:129-130`).
    pub species: u8,
    pub level: u8,
    /// UNBOOSTED stats in the engine's order (hp, atk, def, spe, spc). `hp` is
    /// the MAX-HP STAT, not current HP. Gen 1 has ONE Special: poke-env's `spa`
    /// == `spd` and both map to `spc` (`team.rs:6-8`).
    /// Ours: `mon.stats` from the request. Theirs: §2.3's identity —
    /// `MonSpec::determinized`.
    pub stats: Stats,
    /// Engine cartridge type ids. A mono-type mon **repeats** its type, which
    /// is the engine's encoding and the opposite of `observe::MonView`, whose
    /// `type_2` is `None` (one chart lookup, not two).
    pub types: (u8, u8),
    /// CURRENT hp. Ours exact; theirs `round(hp_fraction × maxhp_det)` — family
    /// **W-HP**, whose rounding rule belongs to the Python half
    /// (`bridge.py:220`), because the inverse of Showdown's
    /// `ceil(100·hp/maxhp)` is an INTERVAL and the point estimate is a choice.
    pub hp: u16,
    /// The cartridge status byte. Class **K**, bits **S**: sleep turns remaining
    /// live in bits 0-2 and the EXT bit separates Rest-sleep from move-sleep —
    /// both hidden, both family **W-SLEEP**.
    pub status: StatusByte,
    /// STORED slots `(move id, pp)`, zero-padded. Ours: exact ids in
    /// `mon.moves` insertion order with exact `current_pp`. Theirs:
    /// determinized ids, `pp = max_pp − observed_uses` for revealed moves (the
    /// A-1a rule, `track.rs:50-57`) and `max_pp` for prior fills.
    pub moves: [(u8, u8); 4],
}

impl MonSpec {
    /// An empty party slot.
    pub const EMPTY: MonSpec = MonSpec {
        species: 0,
        level: 0,
        stats: Stats { hp: 0, atk: 0, def: 0, spe: 0, spc: 0 },
        types: (0, 0),
        hp: 0,
        status: StatusByte::NONE,
        moves: [(0, 0); 4],
    };

    /// A healthy, full-HP, max-PP member from a `PokemonSet` — byte-for-byte
    /// what `PokemonSet::to_bytes` produces (`team.rs:75-99`).
    pub fn from_set(set: &PokemonSet) -> MonSpec {
        let stats = set.stats();
        let stats = Stats { hp: stats[0], atk: stats[1], def: stats[2], spe: stats[3], spc: stats[4] };
        MonSpec {
            species: set.species,
            level: set.level,
            stats,
            types: data::SPECIES_TYPES[set.species as usize],
            hp: stats.hp,
            status: StatusByte::NONE,
            moves: std::array::from_fn(|i| {
                let m = set.moves[i];
                // `data::max_pp` indexes a 166-entry table, so an out-of-range
                // id must not reach it: W-VALIDATE is the thing that reports a
                // bad move id, and it cannot do that from inside a panic.
                (m, if m == 0 || m > 165 { 0 } else { data::max_pp(m) })
            }),
        }
    }

    /// The **D** case: §2.3's identity. `bridge.gen1_stat(base, level, hp, dv=15)`
    /// with `_EXP_TERM = 63` (`bridge.py:110-119`) and
    /// `team::ps_stat(base, iv=30, ev=255, level, is_hp)` compute the SAME
    /// INTEGER, so `PokemonSet { ivs: [30;5], evs: [255;5] }` reproduces the
    /// determinizer's max-DV model bit-for-bit — the single largest piece of
    /// reuse in the bridge, pinned by `stat_identity_*` below.
    ///
    /// Caveat, declared as family **W-STATS**: the team bank's `min_atk`
    /// variant (IV 2 / EV 0 on Attack for special-only sets, `env.rs:437-446`)
    /// is a randbats generator behaviour the determinizer does not model.
    pub fn determinized(species: u8, level: u8, moves: [(u8, u8); 4]) -> MonSpec {
        let ids = std::array::from_fn(|i| moves[i].0);
        let mut m = MonSpec::from_set(&PokemonSet::new(species, level, ids));
        m.moves = moves;
        m
    }

    #[inline]
    pub fn is_empty(&self) -> bool {
        self.species == 0
    }
    #[inline]
    pub fn fainted(&self) -> bool {
        self.hp == 0
    }
    /// The max-HP stat, which is what W-HP quantises against.
    #[inline]
    pub fn max_hp(&self) -> u16 {
        self.stats.hp
    }
}

/// The active's volatile word (§2.4, "Volatiles", `layout.rs:66-93`).
///
/// Every field carries its §2.4 class. The **V** ones are vacuous in
/// `gen1randombattle` by the §2.5 pool census and are carried anyway, so the
/// type is COMPLETE and gen 4+ does not have to reopen it — §2.4 already names
/// `V_BINDING` as "vacuous here; a live landmine for gen 4+".
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct VolatileSpec {
    // ---- K: the client watched these happen ---------------------------------
    /// `V_CHARGING`, and **the one-based LIVE move slot being charged**.
    ///
    /// Shaped differently from every other flag here, deliberately. A bare
    /// `bool` is not enough and a 0 slot is not a small error: on the release
    /// turn the engine discards the offered `Move(1)` and recovers the real
    /// slot from `B_LAST_MOVES[p].index` (`mechanics.zig:439-443`), and
    /// `env.rs:106-120` finds the ACTION-MASK LANE by looking
    /// `S_LAST_SELECTED_MOVE` up in the live slots. Both bytes are derived from
    /// this one field, so they cannot disagree. 8 pool species (Sky Attack);
    /// 0.31% of opponent roots, 0.03% of own (§2.5).
    pub charging: Option<u8>,
    /// `V_RECHARGING`. 5.77% opp / 1.48% own. `Volatiles::forced()` is exactly
    /// PS's `trapped: true` (`track.rs:310-312`).
    pub recharging: bool,
    /// `V_REFLECT`. 18 pool species; 1 of 13,702 roots.
    pub reflect: bool,
    /// `V_CONFUSION` flag — visible (`Effect.CONFUSION`); 0.74% of roots,
    /// 5 pool species (Confuse Ray).
    pub confusion: bool,
    /// `V_CONFUSION_TURNS` — **S**, hidden (`layout.rs:209-212`). Family
    /// **W-CONF**: `None` takes `DEFAULT_CONFUSION_TURNS`, and the caller
    /// SHOULD sample 1..=4 once per determinization so `n_det` averages over it.
    pub confusion_turns: Option<u8>,
    /// `V_SUBSTITUTE` flag — visible. 22 pool species carry Substitute but
    /// **0 of 13,702 harvest roots have one up**.
    pub substitute: bool,
    /// `V_SUBSTITUTE_HP` — **S**, hidden ("PS reveals only that a Substitute
    /// exists", `layout.rs:221-224`). Family **W-SUB**: `None` takes the value
    /// the engine creates it with, `floor(max_hp/4) + 1` (`mechanics.zig:2394,
    /// :2406`). It may not be 0 — 0 is how the engine spells "no Substitute"
    /// (`mechanics.zig:1331`).
    pub substitute_hp: Option<u8>,
    /// `V_TRANSFORM` + `V_TRANSFORM_ID` — **K**, "the transform target is
    /// public (you watched it happen)". `(target's player, ONE-BASED party
    /// index)`, packed as the engine's `ID` (`common/data.zig:30-45`).
    /// Setting this **requires** `ActiveSpec::identity` and `ActiveSpec::stats`,
    /// because Transform copies the foe's ACTIVE stats/species/types
    /// (`mechanics.zig:2450-2458`) and W-ACTIVESTATS cannot derive them.
    pub transform: Option<(Player, u8)>,
    // ---- NAMED UNMODELLABLE -------------------------------------------------
    /// `V_LIGHT_SCREEN` — family **W-LS**. poke-env 0.15 has no
    /// `Effect.LIGHT_SCREEN` (`observe.rs:54-56`), so it is unmodellable; it is
    /// also 0 pool species, so it is vacuous. The safest combination.
    pub light_screen: bool,
    // ---- V: vacuous in gen1randombattle (§2.5) ------------------------------
    /// 0 pool species. `track.rs:330-332` already records the semi-lock rows as
    /// unreachable here. Setting it REQUIRES a non-zero `last_selected_move`
    /// (`mechanics.zig:3211`).
    pub bide: bool,
    /// No Thrash / Petal Dance in the pool.
    pub thrashing: bool,
    /// Never observed at a decision point (intra-turn).
    pub multi_hit: bool,
    /// Cleared before the next request (intra-turn).
    pub flinch: bool,
    /// 0 pool species, and a **transposition hazard**: this bit sits on the
    /// USER of Wrap/Bind/Clamp/Fire Spin (`layout.rs:72-73`), while poke-env's
    /// `PARTIALLY_TRAPPED` sits on the VICTIM and `bridge.py:87-89` maps it onto
    /// the victim's own side. The engine bridge must write it on the **foe's**
    /// side. Also requires a non-zero `last_selected_move`.
    pub binding: bool,
    /// No Fly / Dig.
    pub invulnerable: bool,
    /// 0 pool species.
    pub mist: bool,
    /// 0 pool species.
    pub focus_energy: bool,
    /// 0 pool species.
    pub rage: bool,
    /// 0 pool species.
    pub leech_seed: bool,
    /// 0 pool species (Toxic). TOX is **V** throughout.
    pub toxic: bool,
    /// `V_ATTACKS` (u3) — hidden and vacuous (Thrash/Bide/multi-hit).
    pub attacks: u8,
    /// `V_STATE` (u16) — hidden and vacuous (Bide damage / overwritten accuracy).
    pub state: u16,
    /// `V_DISABLE_MOVE` (u3), the ONE-BASED live slot that is disabled, 0 for
    /// none. **Not vacuous as a mechanism**, only as a pool fact: it is
    /// owner-visible (the `|request|` omits the move) and `choices()` skips the
    /// slot (`mechanics.zig:3231`), so dropping it changes the LEGAL ACTION SET
    /// rather than a residual. Family **W-DISABLE**; 0 pool species in gen 1,
    /// live from gen 2 on.
    pub disable_move: u8,
    /// `V_DISABLE_DURATION` (u4) — **S**, hidden (`layout.rs:228-231`). `None`
    /// takes `DEFAULT_DISABLE_DURATION` when `disable_move` is set, and 0 when
    /// it is not. The two must agree, and W-VALIDATE says so.
    pub disable_duration: Option<u8>,
    /// `V_TOXIC_TURNS` (u5) — **VISIBLE** (it is poke-env's TOX
    /// `status_counter`, `layout.rs:237-241`) but vacuous: no Toxic in the pool.
    pub toxic_turns: u8,
}

impl VolatileSpec {
    /// Packs the spec into the engine's u64. `max_hp` is the active's max-HP
    /// stat and is used only for W-SUB's default.
    fn pack(&self, max_hp: u16) -> Volatiles {
        let mut v = Volatiles(0);
        v.set_bide(self.bide)
            .set_thrashing(self.thrashing)
            .set_multi_hit(self.multi_hit)
            .set_flinch(self.flinch)
            .set_charging(self.charging.is_some())
            .set_binding(self.binding)
            .set_invulnerable(self.invulnerable)
            .set_confusion(self.confusion)
            .set_mist(self.mist)
            .set_focus_energy(self.focus_energy)
            .set_substitute(self.substitute)
            .set_recharging(self.recharging)
            .set_rage(self.rage)
            .set_leech_seed(self.leech_seed)
            .set_toxic(self.toxic)
            .set_light_screen(self.light_screen)
            .set_reflect(self.reflect)
            .set_transform(self.transform.is_some())
            .set_attacks(self.attacks)
            .set_state(self.state)
            .set_disable_move(self.disable_move)
            .set_toxic_turns(self.toxic_turns);
        // W-DISABLE: the pair moves together or the move is disabled forever.
        v.set_disable_duration(if self.disable_move != 0 {
            self.disable_duration.unwrap_or(DEFAULT_DISABLE_DURATION)
        } else {
            0
        });
        // W-CONF. Explicit on BOTH branches: a stale counter behind a cleared
        // flag is as much a bug as a zero counter behind a set one, and
        // W-VALIDATE rejects both.
        v.set_confusion_turns(if self.confusion {
            self.confusion_turns.unwrap_or(DEFAULT_CONFUSION_TURNS)
        } else {
            0
        });
        // W-SUB: `floor(max_hp/4) + 1`, the value `mechanics.zig:2394-2406`
        // creates it with.
        v.set_substitute_hp(if self.substitute {
            self.substitute_hp.unwrap_or_else(|| ((max_hp / 4) + 1).min(255) as u8)
        } else {
            0
        });
        v.set_transform_id(match self.transform {
            Some((p, slot)) => (slot & 0b111) | ((p.index() as u8) << 3),
            None => 0,
        });
        v
    }
}

/// The 32-byte `ActivePokemon` (§2.4).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ActiveSpec {
    /// `A_BOOSTS` — **K**, from `mon.boosts`. Gen 1 has ONE Special, so
    /// `boosts["spa"]` (== `spd`) goes into `spc` — the mirror of
    /// `bridge.py:315-316`, which had to write it into TWO poke_engine slots.
    pub boosts: Boosts,
    pub volatiles: VolatileSpec,
    /// `A_SPECIES` / `A_TYPES` — **K**. `None` means "the stored record's",
    /// which is every non-Transform case. Under Transform the engine writes the
    /// COPIED species and types here while `Pokemon.species` keeps the original
    /// (`observe.rs:24-31`, `mechanics.zig:2456-2457`), so the PRODUCER supplies
    /// them.
    pub identity: Option<(u8, (u8, u8))>,
    /// `A_MOVES`, the LIVE slots — **K** ours / **D** theirs. `None` means "the
    /// stored slots". Transform overwrites all four at 5 PP
    /// (`mechanics.zig:2461-2463`).
    pub live_moves: Option<[(u8, u8); 4]>,
    /// `A_STATS` — **S**, the hardest field in the bridge. `None` applies rule
    /// **W-ACTIVESTATS** (`active_stats`). `Some` is §2.6's "upgrade path,
    /// named and not taken in Phase 1": the `|-boost|` / `|-status|` ORDER is
    /// observable and a LIVE agent could track it, so a caller that knows the
    /// exact value may state it. **Required under Transform.**
    pub stats: Option<Stats>,
}

/// One side (§2.4, `Side`), plus the two `B_LAST_MOVES` bytes that belong to
/// this player but live in the battle header.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SideSpec {
    /// The party in the order ACTIONS INDEX, zero-padded with `MonSpec::EMPTY`.
    ///
    /// §3.1's simplification, taken: put the opponent's revealed mons at
    /// `0..n_revealed` in REVEAL order and the determinized bench after. Then
    /// `reveal_order == [0, 1, …, n-1]` and `foe_seat`'s slot ordering
    /// (`track.rs:399-415`) is poke-env's by construction — safe because
    /// opponent actions are chosen by move id / species, and because
    /// `slot_of_party_index` handles the order indirection (`layout.rs:377-383`).
    pub party: [MonSpec; 6],
    /// ZERO-BASED party index of the active. `order[0]` is written as this + 1.
    /// **It may name a FAINTED mon**: that is exactly a force-switch root,
    /// 14.73% of the harvest (§2.5), and W-REQ turns it into `Request::Switch`.
    pub active_index: u8,
    pub active: ActiveSpec,
    /// `S_LAST_SELECTED_MOVE` — **S**, family **W-LASTMOVE**, default
    /// `DEFAULT_LAST_SELECTED_MOVE`. **Ignored when `volatiles.charging` is
    /// set**, which is the single source of truth for that case; see
    /// `VolatileSpec::charging`.
    pub last_selected_move: u8,
    /// `S_LAST_USED_MOVE` — **S**, family **W-LASTMOVE**, default
    /// `DEFAULT_LAST_USED_MOVE` (and EXACT after any switch or faint).
    pub last_used_move: u8,
    /// `B_LAST_MOVES[p].index` — default `DEFAULT_LAST_MOVE_INDEX` (**1**, not
    /// 0). **Ignored when `volatiles.charging` is set.**
    pub last_move_index: u8,
    /// `B_LAST_MOVES[p].counterable` — default
    /// `DEFAULT_LAST_MOVE_COUNTERABLE`; derivable from the last observed move's
    /// type and category (family W-LASTDMG).
    pub last_move_counterable: bool,
}

impl SideSpec {
    /// A side with the stated party and active, every S-class field at its
    /// documented default. Nothing here is a silent zero: see the constants.
    pub fn new(party: [MonSpec; 6], active_index: u8) -> SideSpec {
        SideSpec {
            party,
            active_index,
            active: ActiveSpec::default(),
            last_selected_move: DEFAULT_LAST_SELECTED_MOVE,
            last_used_move: DEFAULT_LAST_USED_MOVE,
            last_move_index: DEFAULT_LAST_MOVE_INDEX,
            last_move_counterable: DEFAULT_LAST_MOVE_COUNTERABLE,
        }
    }

    #[inline]
    pub fn party_len(&self) -> usize {
        self.party.iter().take_while(|m| !m.is_empty()).count()
    }
    #[inline]
    fn active_mon(&self) -> &MonSpec {
        &self.party[self.active_index as usize]
    }
    /// True on a force-switch root.
    #[inline]
    pub fn active_fainted(&self) -> bool {
        self.active_mon().fainted()
    }
    /// The LIVE move slots after `ActiveSpec::live_moves`' default is applied.
    #[inline]
    fn live_moves(&self) -> [(u8, u8); 4] {
        self.active.live_moves.unwrap_or(self.active_mon().moves)
    }
    /// `(S_LAST_SELECTED_MOVE, B_LAST_MOVES.index)`, with Charging as the single
    /// source of truth for both.
    #[inline]
    fn last_move_bytes(&self) -> (u8, u8) {
        match self.active.volatiles.charging {
            Some(slot) => (self.live_moves()[slot as usize - 1].0, slot),
            None => (self.last_selected_move, self.last_move_index),
        }
    }
}

/// The battle header (§2.4, `Battle`) plus both sides.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct BattleSpec {
    /// `B_TURN` — **K**, `battle.turn`. **Must be ≥ 1.** `update` routes turn 0
    /// into `start()`, which switches both leads in from scratch and discards
    /// the constructed actives (`mechanics.zig:81-82`, `:283-297`).
    pub turn: u16,
    /// `B_LAST_DAMAGE` — **S**, family **W-LASTDMG**.
    pub last_damage: u16,
    /// `B_RNG` — **S by design**. Not an approximation: this IS the chance dial,
    /// `splitmix64(decision_key ^ col ^ det ^ s)` under rule CRN-1 (§1.2).
    /// There is no default, because a shared default would silently correlate
    /// every sample in the batch.
    pub seed: u64,
    pub p1: SideSpec,
    pub p2: SideSpec,
}

/// A constructed root: the 384 bytes **and the request pair**, which is not in
/// them. `BattleResult` is returned by `update`, never stored
/// (`battle.rs:96-138`), so a constructed root has to carry it — rule **W-REQ**.
#[derive(Clone, Debug)]
pub struct Root {
    pub battle: Battle,
    pub p1: Request,
    pub p2: Request,
}

impl BattleSpec {
    /// Rule **W-REQ** (§2.4, "Not in the 384 bytes at all"):
    ///
    /// | our active | foe active | `(req_us, req_them)` |
    /// |---|---|---|
    /// | alive | alive | `(Move, Move)` |
    /// | fainted | alive | `(Switch, Pass)` |
    /// | alive | fainted | `(Pass, Switch)` |
    /// | fainted | fainted | `(Switch, Switch)` |
    ///
    /// It matches the engine's own mid-turn-faint shapes (`battle.rs:426-452`:
    /// `0x20`, `0x80`, `0xA0`) and `matrix.py:24-28`'s existing rule. It is also
    /// SELF-CHECKING: `Battle::update` validates both choices against
    /// `choices(p, req)` before calling the engine (`battle.rs:288-307`), so a
    /// wrong request surfaces as `IllegalChoice`, never as engine UB.
    pub fn requests(&self) -> (Request, Request) {
        requests_from(self.p1.active_fainted(), self.p2.active_fainted())
    }

    /// Assembles the 384 bytes, runs **W-VALIDATE**, and returns the root.
    /// On any violation it returns the error and no battle — it never repairs.
    pub fn build(&self) -> Result<Root, SpecError> {
        self.check_shape()?;
        let battle = self.assemble();
        let (p1, p2) = self.requests();
        validate(&battle, p1, p2)?;
        Ok(Root { battle, p1, p2 })
    }

    /// The few checks that must run BEFORE assembly, because assembly would
    /// otherwise index out of bounds, plus the two rules that exist only at the
    /// spec level and are invisible in the bytes.
    fn check_shape(&self) -> Result<(), SpecError> {
        for (p, side) in [&self.p1, &self.p2].into_iter().enumerate() {
            if side.active_index >= 6 {
                return Err(SpecError::side(p, "active_index", "not a party slot", side.active_index as i64, 5));
            }
            if side.party[side.active_index as usize].is_empty() {
                return Err(SpecError::side(p, "active_index", "names an empty party slot", side.active_index as i64, 5));
            }
            if let Some(slot) = side.active.volatiles.charging
                && !(1..=4).contains(&slot)
            {
                return Err(SpecError::side(p, "volatiles.charging", "not a one-based live move slot", slot as i64, 4));
            }
            // Range-checked HERE as well as in `validate`, because `assemble`
            // runs `active_stats`, which indexes the engine's 13-entry BOOSTS
            // table by `stage + 6`. Validating after assembly would mean
            // panicking before the error could be returned, and "it never
            // panics" is part of W-VALIDATE's contract.
            let bo = side.active.boosts;
            for (name, v) in [
                ("active.boosts.atk", bo.atk),
                ("active.boosts.def", bo.def),
                ("active.boosts.spe", bo.spe),
                ("active.boosts.spc", bo.spc),
                ("active.boosts.accuracy", bo.accuracy),
                ("active.boosts.evasion", bo.evasion),
            ] {
                if !(-6..=6).contains(&v) {
                    return Err(SpecError::side(p, name, "stat stage out of range", v as i64, 6));
                }
            }
            // Transform copies the foe's ACTIVE stats, species and types
            // (`mechanics.zig:2450-2458`); W-ACTIVESTATS cannot derive any of
            // them, so the producer must state them. Silently deriving would
            // put a Ditto's own stats behind a copied species.
            if side.active.volatiles.transform.is_some() {
                if side.active.stats.is_none() {
                    return Err(SpecError::side(p, "active.stats", "required under Transform: the engine copies the FOE's ACTIVE stats", 0, 0));
                }
                if side.active.identity.is_none() {
                    return Err(SpecError::side(p, "active.identity", "required under Transform: the engine copies the FOE's species and types", 0, 0));
                }
            }
        }
        Ok(())
    }

    /// Bytes only. Never called on an unchecked spec — `build` gates it.
    fn assemble(&self) -> Battle {
        let mut b = Battle::default();
        {
            let mut w = BattleViewMut(&mut b.0);
            w.set_turn(self.turn);
            w.set_last_damage(self.last_damage);
            w.set_seed(self.seed);
            for (p, side) in [&self.p1, &self.p2].into_iter().enumerate() {
                let (last_selected, last_index) = side.last_move_bytes();
                w.set_last_moves(p, last_index, side.last_move_counterable);
                side.assemble_into(&mut w.side_mut(p), last_selected);
            }
        }
        b
    }

    /// Rebuilds a spec from a battle's own bytes, reading **only** the fields
    /// §2.4 classes K (plus the seed, which the spec carries verbatim).
    ///
    /// This is the input to the byte-identity guard, and its value depends
    /// entirely on its discipline: every S-class field it reads is a field the
    /// guard then cannot catch. It reads exactly one thing that looks hidden —
    /// `S_LAST_SELECTED_MOVE`, and only under `V_CHARGING`, and only to recover
    /// WHICH live slot is charging. That is legitimate: poke-env retains the
    /// charging move's identity (`_preparing_move`), so the live bridge will do
    /// the same lookup.
    ///
    /// It is **not** the poke-env bridge. It cannot be: it reads engine bytes.
    pub fn from_visible(b: &Battle) -> BattleSpec {
        BattleSpec {
            turn: b.turn(),
            last_damage: DEFAULT_LAST_DAMAGE,
            seed: b.seed(),
            p1: side_from_visible(b, Player::P1),
            p2: side_from_visible(b, Player::P2),
        }
    }
}

impl SideSpec {
    fn assemble_into(&self, w: &mut SideViewMut<'_>, last_selected_move: u8) {
        let n = self.party_len();
        for i in 0..6 {
            let m = &self.party[i];
            let mut slot = w.party_mut(i);
            if m.is_empty() {
                slot.clear();
                continue;
            }
            slot.set_stats(m.stats);
            slot.set_moves(m.moves);
            slot.set_hp(m.hp);
            slot.set_status(m.status);
            slot.set_species(m.species);
            slot.set_types(m.types);
            slot.set_level(m.level);
        }
        // Family W-ORDER, declared FREE: write the identity with `order[0]`
        // swapped to the active, exactly as `switchIn` does
        // (`mechanics.zig:234-236`). The permutation carries switch history and
        // is unobservable, but `choices()` offers the same SET of live party
        // members whichever permutation it is, and every action maps through
        // `slot_of_party_index` (`layout.rs:377-383`, used at `env.rs:86`), so
        // the action mapping is permutation-invariant. `order_is_free_*` below
        // is the test that says so out loud.
        let mut order = [0u8; 6];
        for (i, o) in order.iter_mut().enumerate().take(n) {
            *o = (i + 1) as u8;
        }
        let a = self.active_index as usize;
        order.swap(0, a);
        w.set_order(order);
        w.set_last_selected_move(last_selected_move);
        w.set_last_used_move(self.last_used_move);

        let mon = self.active_mon();
        let (species, types) = self.active.identity.unwrap_or((mon.species, mon.types));
        let mut act = w.active_mut();
        act.clear();
        act.set_species(species);
        act.set_types(types);
        act.set_moves(self.live_moves());
        if self.active_fainted() {
            // `faint()` (`mechanics.zig:1562-1576`) zeroes the volatile word,
            // clears the stored status, and restores `active.stats.spe` from
            // the STORED speed (÷4 if the pre-faint status was PAR, "because
            // Pokémon Showdown decides double switching priority based on
            // speed"). atk/def/spc are left STALE at their pre-faint boosted
            // values and are not recoverable from any client view — declared
            // as an extension of family W-ACTIVESTATS.
            //
            // Nothing reads the stale three before they are overwritten: on a
            // force-switch root W-REQ offers only switches, and `switchIn` sets
            // `active.stats = incoming.stats` wholesale (`mechanics.zig:243`).
            // The one live reader is `turnOrder`'s `spe1 == spe2` on a double
            // switch (`mechanics.zig:291-300`), which is why spe is reproduced
            // exactly. The pre-faint PAR flag is itself unrecoverable (poke-env
            // reports FNT), so the default is "not paralysed"; it can only
            // change which of two SWITCHES resolves first, and gen 1 makes that
            // order unobservable.
            act.set_boosts(self.active.boosts);
            act.set_volatiles(Volatiles(0));
            let mut s = active_stats(mon.stats, self.active.boosts, StatusByte::NONE);
            s.spe = mon.stats.spe;
            act.set_stats(self.active.stats.unwrap_or(s));
        } else {
            act.set_boosts(self.active.boosts);
            act.set_volatiles(self.active.volatiles.pack(mon.max_hp()));
            act.set_stats(
                self.active
                    .stats
                    .unwrap_or_else(|| active_stats(mon.stats, self.active.boosts, mon.status)),
            );
        }
    }
}

#[inline]
fn requests_from(p1_fainted: bool, p2_fainted: bool) -> (Request, Request) {
    match (p1_fainted, p2_fainted) {
        (false, false) => (Request::Move, Request::Move),
        (true, false) => (Request::Switch, Request::Pass),
        (false, true) => (Request::Pass, Request::Switch),
        (true, true) => (Request::Switch, Request::Switch),
    }
}

/// Rule W-REQ read off assembled bytes, so `validate` can check a state it did
/// not build.
pub fn requests_for(b: &Battle) -> (Request, Request) {
    let f = |p: Player| {
        let s = b.side(p);
        let i = s.active_party_index();
        i < 6 && s.party(i).fainted()
    };
    requests_from(f(Player::P1), f(Player::P2))
}

/// Keeps the status bits a client can see and replaces the ones it cannot:
/// sleep turns REMAINING (bits 0-2) and, with them, the EXT bit that separates
/// Rest-sleep from move-sleep. Family **W-SLEEP**.
fn visible_status(s: StatusByte) -> StatusByte {
    if s.asleep() {
        StatusByte::slp(DEFAULT_SLEEP_TURNS_LEFT)
    } else {
        // PSN / BRN / FRZ / PAR, and EXT only as TOX's marker — all visible.
        StatusByte(s.0 & !0b111)
    }
}

fn side_from_visible(b: &Battle, p: Player) -> SideSpec {
    let s = b.side(p);
    let party: [MonSpec; 6] = std::array::from_fn(|i| {
        let m = s.party(i);
        if m.is_empty() {
            return MonSpec::EMPTY;
        }
        MonSpec {
            species: m.species(),
            level: m.level(),
            stats: m.stats(),
            types: m.types(),
            hp: m.hp(),
            status: visible_status(m.status()),
            moves: m.moves(),
        }
    });
    let act = s.active();
    let v = act.volatiles();
    let live = act.moves();
    let mut spec = SideSpec::new(party, s.active_party_index() as u8);
    // §2.4 classes `S_LAST_SELECTED_MOVE` as **S**, and the HARVEST cannot
    // supply it (`freeze_battle` carries `must_recharge` / `preparing` as
    // booleans only). But under a MOVE LOCK the client does know the identity —
    // it watched the move start — and both the engine and the mask REQUIRE it:
    // `choices()` asserts it under Bide/Binding (`mechanics.zig:3211`) and
    // `env.rs:106-120` finds the mask lane by looking it up in the live slots
    // for every member of `Volatiles::forced()`. So it is carried exactly under
    // a lock and defaulted otherwise. In `gen1randombattle` only Charging is
    // reachable (§2.5: 0 pool species for Bide, Thrash, Rage and the binding
    // moves), and Charging derives it from the slot instead.
    let locked = v.forced() || v.bide() || v.binding();
    spec.last_selected_move = if locked {
        s.last_selected_move()
    } else {
        DEFAULT_LAST_SELECTED_MOVE
    };
    spec.active = ActiveSpec {
        boosts: act.boosts(),
        volatiles: VolatileSpec {
            charging: v.charging().then(|| {
                // The charging move's IDENTITY is what poke-env retains
                // (`_preparing_move`); the slot is recovered by search, exactly
                // as the live bridge will. A miss is only reachable through
                // Metronome / Mirror Move, both in `team::BLOCKED_MOVES`, and
                // W-VALIDATE rejects the fallback loudly rather than writing a 0.
                let want = s.last_selected_move();
                live.iter()
                    .position(|&(id, _)| id != 0 && id == want)
                    .map_or(DEFAULT_LAST_MOVE_INDEX, |j| (j + 1) as u8)
            }),
            recharging: v.recharging(),
            reflect: v.reflect(),
            confusion: v.confusion(),
            confusion_turns: None, // W-CONF
            substitute: v.substitute(),
            substitute_hp: None, // W-SUB
            transform: v.transform().then(|| {
                let id = v.transform_id();
                let who = if id & 0b1000 == 0 { Player::P1 } else { Player::P2 };
                (who, id & 0b111)
            }),
            light_screen: v.light_screen(),
            bide: v.bide(),
            thrashing: v.thrashing(),
            multi_hit: v.multi_hit(),
            flinch: v.flinch(),
            binding: v.binding(),
            invulnerable: v.invulnerable(),
            mist: v.mist(),
            focus_energy: v.focus_energy(),
            rage: v.rage(),
            leech_seed: v.leech_seed(),
            toxic: v.toxic(),
            attacks: 0, // hidden, vacuous
            state: 0,   // hidden, vacuous
            // W-DISABLE: the SLOT is owner-visible and carried, because
            // dropping it would silently re-offer a move the request does not
            // list; the DURATION is hidden and defaulted.
            disable_move: v.disable_move(),
            disable_duration: None,
            toxic_turns: v.toxic_turns(),
        },
        identity: Some((act.species(), act.types())),
        live_moves: Some(live),
        // Transform is the one case where `active.stats` is recoverable: it is
        // the foe's active stats, which the client watched being copied.
        // `bridge._transform_stats_override` (`bridge.py:251-298`) is the
        // Python half of exactly this.
        stats: v.transform().then(|| act.stats()),
    };
    spec
}

// =============================================================================
// W-VALIDATE (§2.4)
// =============================================================================

/// **W-VALIDATE.** `from_bytes` accepts anything (`python.rs:289-297`); this is
/// what the write side must run before handing a state to `update`.
///
/// Checked in three layers, in this order and for this reason:
///  1. pure byte invariants (ranges, contiguity, the order permutation);
///  2. cross-field invariants (W-REQ, the volatile flag/counter pairs);
///  3. the ONE engine-backed check, `choices()` non-empty.
///
/// Layer 1 has to come first because `choices()` itself dereferences
/// `side.pokemon[order[slot-1] - 1]` (`mechanics.zig:3149-3153`): calling it on
/// a malformed order array is the very UB this function exists to prevent.
pub fn validate(b: &Battle, req1: Request, req2: Request) -> Result<(), SpecError> {
    // ---- battle level -------------------------------------------------------
    if b.turn() == 0 {
        return Err(SpecError::battle(
            "turn",
            "a constructed root needs turn >= 1; update() routes turn 0 into start()",
            0,
            1,
        ));
    }
    for p in 0..2usize {
        validate_side(b, p)?;
    }
    // ---- W-REQ --------------------------------------------------------------
    let want = requests_for(b);
    if (req1, req2) != want {
        return Err(SpecError::battle(
            "request",
            "the request pair does not match W-REQ for these actives",
            (req1 == want.0) as i64,
            (req2 == want.1) as i64,
        ));
    }
    // ---- the engine's own answer -------------------------------------------
    for (p, (player, req)) in [(Player::P1, req1), (Player::P2, req2)].into_iter().enumerate() {
        if b.choices(player, req).is_empty() {
            return Err(SpecError::side(p, "choices", "the engine offers this seat no legal choice", 0, 1));
        }
    }
    Ok(())
}

fn validate_side(b: &Battle, p: usize) -> Result<(), SpecError> {
    let s = b.view().side(p);

    // ---- the party ---------------------------------------------------------
    let mut n = 0usize;
    let mut any_live = false;
    let mut seen_empty = false;
    for i in 0..6 {
        let m = s.party(i);
        let at = layout::B_SIDES + p * layout::SIDE_SIZE + layout::S_POKEMON + i * layout::POKEMON_SIZE;
        let raw = &b.0[at..at + layout::POKEMON_SIZE];
        if m.is_empty() {
            seen_empty = true;
            if raw.iter().any(|&x| x != 0) {
                return Err(SpecError::slot(p, i, "pokemon", "an empty party slot must be all zero", 1, 0));
            }
            continue;
        }
        if seen_empty {
            return Err(SpecError::slot(p, i, "pokemon", "party slots must be contiguous from 0", i as i64, n as i64));
        }
        n += 1;
        if m.species() > 151 {
            return Err(SpecError::slot(p, i, "species", "not a gen 1 dex number", m.species() as i64, 151));
        }
        if m.level() == 0 || m.level() > 100 {
            return Err(SpecError::slot(p, i, "level", "out of range", m.level() as i64, 100));
        }
        let stats = m.stats();
        if stats.hp == 0 {
            return Err(SpecError::slot(p, i, "stats.hp", "max HP of 0 is not a Pokemon", 0, 1));
        }
        if m.hp() > stats.hp {
            return Err(SpecError::slot(p, i, "hp", "current HP exceeds max HP", m.hp() as i64, stats.hp as i64));
        }
        if m.hp() == 0 {
            // `faint()` clears the status byte of the mon that fainted
            // (`mechanics.zig:1567`), for Showdown's Sleep/Freeze Clause Mod.
            if m.status().0 != 0 {
                return Err(SpecError::slot(p, i, "status", "a fainted mon's status byte is cleared by faint()", m.status().0 as i64, 0));
            }
        } else {
            any_live = true;
        }
        // `PokemonSet::to_bytes` asserts it (`team.rs:81`) and
        // `ActivePokemon.move` asserts the slot it reaches is not `None`
        // (`data.zig:182`).
        if m.moves()[0].0 == 0 {
            return Err(SpecError::slot(p, i, "moves", "a Pokemon needs at least one move", 0, 1));
        }
        validate_move_slots(p, i, "moves", m.moves())?;
    }
    if n == 0 {
        return Err(SpecError::side(p, "party", "a side needs at least one Pokemon", 0, 1));
    }
    if !any_live {
        return Err(SpecError::side(p, "party", "a side with no live Pokemon has no decision to make", 0, 1));
    }

    // ---- the order array ---------------------------------------------------
    let order = s.order();
    let mut seen = [false; 7];
    for (slot, &id) in order.iter().enumerate() {
        if slot < n {
            if id == 0 || id as usize > n {
                return Err(SpecError::slot(p, slot, "order", "not a one-based index of a present party member", id as i64, n as i64));
            }
            if seen[id as usize] {
                return Err(SpecError::slot(p, slot, "order", "the order array is not a permutation", id as i64, n as i64));
            }
            seen[id as usize] = true;
        } else if id != 0 {
            return Err(SpecError::slot(p, slot, "order", "slots past the party length must be 0", id as i64, 0));
        }
    }

    // ---- the active --------------------------------------------------------
    let a = s.active();
    if a.species() == 0 || a.species() > 151 {
        return Err(SpecError::side(p, "active.species", "not a gen 1 dex number", a.species() as i64, 151));
    }
    let live = a.moves();
    if live[0].0 == 0 {
        return Err(SpecError::side(p, "active.moves", "the active needs at least one live move slot", 0, 1));
    }
    validate_move_slots(p, 6, "active.moves", live)?;
    let bo = a.boosts();
    for (name, v) in [
        ("active.boosts.atk", bo.atk),
        ("active.boosts.def", bo.def),
        ("active.boosts.spe", bo.spe),
        ("active.boosts.spc", bo.spc),
        ("active.boosts.accuracy", bo.accuracy),
        ("active.boosts.evasion", bo.evasion),
    ] {
        if !(-6..=6).contains(&v) {
            return Err(SpecError::side(p, name, "stat stage out of range", v as i64, 6));
        }
    }

    // ---- the volatile word -------------------------------------------------
    let v = a.volatiles();
    let active_fainted = s.party(s.active_party_index()).fainted();
    if active_fainted && v.0 != 0 {
        return Err(SpecError::side(p, "active.volatiles", "faint() zeroes the volatile word", v.0 as i64, 0));
    }
    // W-CONF. Both directions: a counter behind a cleared flag is as much a bug
    // as a zero counter behind a set one.
    if v.confusion() {
        if !(1..=5).contains(&v.confusion_turns()) {
            return Err(SpecError::side(p, "active.volatiles.confusion_turns", "V_CONFUSION needs 1..=5 turns left (mechanics.zig:577, :3013)", v.confusion_turns() as i64, 5));
        }
    } else if v.confusion_turns() != 0 {
        return Err(SpecError::side(p, "active.volatiles.confusion_turns", "a confusion counter behind a cleared V_CONFUSION", v.confusion_turns() as i64, 0));
    }
    // W-SUB. 0 is how the engine spells "no Substitute" (`mechanics.zig:1331`).
    if v.substitute() {
        if v.substitute_hp() == 0 {
            return Err(SpecError::side(p, "active.volatiles.substitute_hp", "V_SUBSTITUTE with 0 HP is how the engine spells no Substitute", 0, 1));
        }
    } else if v.substitute_hp() != 0 {
        return Err(SpecError::side(p, "active.volatiles.substitute_hp", "Substitute HP behind a cleared V_SUBSTITUTE", v.substitute_hp() as i64, 0));
    }
    if v.transform() {
        let slot = v.transform_id() & 0b111;
        if slot == 0 || slot > 6 {
            return Err(SpecError::side(p, "active.volatiles.transform_id", "not a one-based party slot (mechanics.zig:2694 does pokemon[id-1])", slot as i64, 6));
        }
    } else if v.transform_id() != 0 {
        return Err(SpecError::side(p, "active.volatiles.transform_id", "a transform target behind a cleared V_TRANSFORM", v.transform_id() as i64, 0));
    }
    // W-DISABLE. The slot decides which actions exist; the duration decides
    // whether the disable ever ends. They move together.
    if v.disable_move() != 0 {
        if v.disable_move() > 4 {
            return Err(SpecError::side(p, "active.volatiles.disable_move", "not a one-based live move slot", v.disable_move() as i64, 4));
        }
        if live[v.disable_move() as usize - 1].0 == 0 {
            return Err(SpecError::side(p, "active.volatiles.disable_move", "names an empty live move slot", v.disable_move() as i64, 4));
        }
        if !(1..=8).contains(&v.disable_duration()) {
            return Err(SpecError::side(p, "active.volatiles.disable_duration", "Disable needs 1..=8 turns left; 0 never clears (mechanics.zig:552-563, :2997)", v.disable_duration() as i64, 8));
        }
    } else if v.disable_duration() != 0 {
        return Err(SpecError::side(p, "active.volatiles.disable_duration", "a Disable duration with no disabled slot", v.disable_duration() as i64, 0));
    }
    // Bide and Binding assert a selected move when `choices()` builds the
    // limited list (`mechanics.zig:3211`). Vacuous in gen1randombattle, cheap
    // to check, and a hard crash if it ever stops being vacuous.
    if (v.bide() || v.binding()) && s.last_selected_move() == 0 {
        return Err(SpecError::side(p, "last_selected_move", "Bide / Binding require a selected move (mechanics.zig:3211)", 0, 1));
    }

    // ---- B_LAST_MOVES, and the Charging contract ---------------------------
    let (index, _counterable) = b.view().last_moves(p);
    if !(1..=4).contains(&index) {
        return Err(SpecError::side(p, "last_moves.index", "a one-based live move slot; switchIn writes 1 and 0 indexes moves[-1]", index as i64, 4));
    }
    if v.charging() {
        let id = live[index as usize - 1].0;
        if id == 0 {
            return Err(SpecError::side(p, "last_moves.index", "V_CHARGING points at an empty live move slot (mechanics.zig:439-443)", index as i64, 4));
        }
        if s.last_selected_move() != id {
            return Err(SpecError::side(p, "last_selected_move", "V_CHARGING: last_selected_move must be the charging slot's move, or env.rs:106-120 puts the mask in the wrong lane", s.last_selected_move() as i64, id as i64));
        }
    }
    Ok(())
}

fn validate_move_slots(p: usize, slot: usize, field: &'static str, m: [(u8, u8); 4]) -> Result<(), SpecError> {
    let mut empty = false;
    for (j, (id, pp)) in m.into_iter().enumerate() {
        if id == 0 {
            empty = true;
            if pp != 0 {
                return Err(SpecError::slot(p, slot, field, "an empty move slot must have 0 PP", pp as i64, 0));
            }
            continue;
        }
        if empty {
            return Err(SpecError::slot(p, slot, field, "move slots must be contiguous from 0", j as i64, 0));
        }
        if id > 165 {
            return Err(SpecError::slot(p, slot, field, "not a gen 1 move number", id as i64, 165));
        }
        let max = data::max_pp(id);
        if pp > max {
            return Err(SpecError::slot(p, slot, field, "PP exceeds the move's max PP", pp as i64, max as i64));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// §2.3, "verify this before anything else": the determinizer's max-DV stat
    /// model and `team::ps_stat` are the SAME INTEGER, so `PokemonSet` with
    /// `ivs: [30;5], evs: [255;5]` is a drop-in. `bridge.py:110-119` computes
    /// `floor((2*base + 30 + 63) * level/100) + 5` for non-HP and
    /// `floor(core*level/100) + level + 10` for HP, with `_EXP_TERM = 63`.
    #[test]
    fn stat_identity_matches_the_determinizers_max_dv_model() {
        for base in 1u16..=200 {
            for level in 1u16..=100 {
                let core = 2 * base as u32 + 30 + 63;
                let bridge_other = (core * level as u32 / 100 + 5) as u16;
                let bridge_hp = (core * level as u32 / 100 + level as u32 + 10) as u16;
                assert_eq!(
                    crate::team::ps_stat(base, 30, 255, level, false),
                    bridge_other,
                    "non-HP base={base} level={level}"
                );
                assert_eq!(
                    crate::team::ps_stat(base, 30, 255, level, true),
                    bridge_hp,
                    "HP base={base} level={level} -- 255/4 == 63 and the level term is integral"
                );
            }
        }
    }

    /// W-ACTIVESTATS is EXACT with no boosts: it is then literally `switchIn`'s
    /// output (`active.stats = incoming.stats`, then `statusModify`).
    #[test]
    fn active_stats_is_switch_in_when_unboosted() {
        let stored = Stats { hp: 300, atk: 200, def: 180, spe: 250, spc: 220 };
        assert_eq!(active_stats(stored, Boosts::default(), StatusByte::NONE), stored);
        let par = active_stats(stored, Boosts::default(), StatusByte::PAR);
        assert_eq!(par.spe, 250 / 4, "PAR divides speed by 4");
        assert_eq!(par.atk, 200);
        let brn = active_stats(stored, Boosts::default(), StatusByte::BRN);
        assert_eq!(brn.atk, 200 / 2, "BRN halves attack");
        assert_eq!(brn.spe, 250);
    }

    /// The engine's own table, exercised at both ends and at the 999 cap.
    #[test]
    fn active_stats_uses_the_engines_boost_table() {
        let stored = Stats { hp: 300, atk: 200, def: 180, spe: 250, spc: 220 };
        let mut b = Boosts::default();
        b.atk = 1;
        assert_eq!(active_stats(stored, b, StatusByte::NONE).atk, 200 * 15 / 10);
        b.atk = 6;
        assert_eq!(active_stats(stored, b, StatusByte::NONE).atk, 200 * 4);
        b.atk = -6;
        assert_eq!(active_stats(stored, b, StatusByte::NONE).atk, 200 * 25 / 100);
        // The cap: 300 * 4 = 1200 -> 999.
        let big = Stats { hp: 300, atk: 300, def: 180, spe: 250, spc: 220 };
        b.atk = 6;
        assert_eq!(active_stats(big, b, StatusByte::NONE).atk, MAX_STAT_VALUE);
    }

    /// §2.6's named ambiguity, stated as a test so it cannot be quietly
    /// "fixed": Agility-then-Thunder-Wave and Thunder-Wave-then-Agility have
    /// identical public descriptions and differ by 4x in the field that decides
    /// turn order. W-ACTIVESTATS produces the SECOND.
    #[test]
    fn w_activestats_is_the_declared_side_of_the_order_ambiguity() {
        let stored = Stats { hp: 300, atk: 200, def: 180, spe: 200, spc: 220 };
        let mut b = Boosts::default();
        b.spe = 2; // Agility
        let ours = active_stats(stored, b, StatusByte::PAR);
        // Thunder Wave THEN Agility: boost recomputes from the stored stat and
        // does not re-apply the status modifier -> 200 * 2 = 400.
        assert_eq!(ours.spe, 200 * 2 / 4, "we produce Agility-then-Thunder-Wave");
        assert_ne!(ours.spe, 200 * 2, "the other order is the 2.26%-of-roots error");
    }
}

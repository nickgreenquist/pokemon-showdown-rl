//! The safe `Battle` wrapper over `libpkmn-showdown` (plan §5.2, §5.3).
//!
//! The engine's contract, quoted from its README: "*Attempting to update the
//! battle with a choice not present in the options returned by `choices` is
//! undefined behavior and may corrupt state or cause the engine to crash*". Every
//! `update` here is therefore checked against the engine's own `choices()` before
//! the call -- a masking bug must surface as a Rust error, never as engine UB.

use crate::ffi;
use crate::layout::{self, BattleView, SideView};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Player {
    P1 = 0,
    P2 = 1,
}

impl Player {
    pub fn foe(self) -> Player {
        match self {
            Player::P1 => Player::P2,
            Player::P2 => Player::P1,
        }
    }
    pub fn index(self) -> usize {
        self as usize
    }
}

/// A player's choice. `Move(0)` is Struggle / the single forced option;
/// `Switch(s)` takes a one-based slot in CURRENT order (2..=6), not a party index.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Hash)]
pub enum Choice {
    Pass,
    Move(u8),
    Switch(u8),
}

impl Choice {
    /// `Choice{type:u2, data:u6}`, LSB-first (`common/data.zig`).
    pub fn raw(self) -> u8 {
        match self {
            Choice::Pass => 0,
            Choice::Move(d) => 1 | (d << 2),
            Choice::Switch(d) => 2 | (d << 2),
        }
    }
    pub fn from_raw(b: u8) -> Choice {
        match b & 0b11 {
            0 => Choice::Pass,
            1 => Choice::Move(b >> 2),
            2 => Choice::Switch(b >> 2),
            _ => unreachable!("choice kind 3 is not defined by the engine"),
        }
    }
}

/// The kind of decision a player owes on the next update.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Request {
    Pass,
    Move,
    Switch,
}

impl Request {
    fn raw(self) -> u8 {
        match self {
            Request::Pass => ffi::PKMN_CHOICE_PASS,
            Request::Move => ffi::PKMN_CHOICE_MOVE,
            Request::Switch => ffi::PKMN_CHOICE_SWITCH,
        }
    }
    fn from_raw(b: u8) -> Request {
        match b {
            0 => Request::Pass,
            1 => Request::Move,
            2 => Request::Switch,
            _ => unreachable!("request kind {b} is not defined by the engine"),
        }
    }
}

/// The battle outcome, always from **P1's** point of view.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Outcome {
    None,
    Win,
    Lose,
    Tie,
    Error,
}

/// `Result{type:u4, p1:u2, p2:u2}`. The all-move default is `0x50`.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct BattleResult {
    pub outcome: Outcome,
    pub p1: Request,
    pub p2: Request,
}

impl BattleResult {
    pub fn from_raw(b: u8) -> BattleResult {
        let outcome = match b & 0x0F {
            0 => Outcome::None,
            1 => Outcome::Win,
            2 => Outcome::Lose,
            3 => Outcome::Tie,
            4 => Outcome::Error,
            k => unreachable!("result kind {k} is not defined by the engine"),
        };
        BattleResult {
            outcome,
            p1: Request::from_raw((b >> 4) & 0b11),
            p2: Request::from_raw((b >> 6) & 0b11),
        }
    }
    pub fn raw(self) -> u8 {
        let k = match self.outcome {
            Outcome::None => 0u8,
            Outcome::Win => 1,
            Outcome::Lose => 2,
            Outcome::Tie => 3,
            Outcome::Error => 4,
        };
        k | (self.p1.raw() << 4) | (self.p2.raw() << 6)
    }
    pub fn over(self) -> bool {
        !matches!(self.outcome, Outcome::None)
    }
    pub fn request(self, p: Player) -> Request {
        match p {
            Player::P1 => self.p1,
            Player::P2 => self.p2,
        }
    }
}

/// The legal choices for one seat. Fixed capacity, never heap-allocates.
#[derive(Clone, Copy, Debug)]
pub struct Choices {
    buf: [u8; ffi::CHOICES_CAP],
    n: u8,
}

impl Choices {
    pub fn len(&self) -> usize {
        self.n as usize
    }
    pub fn is_empty(&self) -> bool {
        self.n == 0
    }
    pub fn get(&self, i: usize) -> Choice {
        Choice::from_raw(self.buf[i])
    }
    pub fn iter(&self) -> impl Iterator<Item = Choice> + '_ {
        (0..self.len()).map(move |i| self.get(i))
    }
    pub fn contains(&self, c: Choice) -> bool {
        let raw = c.raw();
        self.buf[..self.len()].contains(&raw)
    }
    /// The first `Move` choice the engine offers, which is what an "aliased"
    /// PS turn (`[Fight]` placeholder) resolves to (plan §7.2).
    pub fn first_move(&self) -> Option<Choice> {
        self.iter().find(|c| matches!(c, Choice::Move(_)))
    }
}

#[derive(Debug)]
pub struct IllegalChoice {
    pub player: Player,
    pub choice: Choice,
    pub request: Request,
    pub offered: Vec<Choice>,
}

impl std::fmt::Display for IllegalChoice {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "illegal choice {:?} for {:?} under request {:?}; engine offered {:?}",
            self.choice, self.player, self.request, self.offered
        )
    }
}

impl std::error::Error for IllegalChoice {}

/// The engine's 384-byte battle state. A plain byte array owned by Rust.
///
/// Aligned to 8 because the PSRNG seed at byte 376 is a u64 and the engine's
/// `Battle` is an `extern struct` with u16/u64 fields.
#[repr(C, align(8))]
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct Battle(pub [u8; layout::BATTLE_SIZE]);

// SAFETY: the library keeps no global mutable state -- `src/lib/bindings/c.zig`
// declares no `var` at file scope and every export operates solely on
// caller-provided pointers (confirmed at B-0). Distinct `Battle`s therefore do
// not alias any shared engine state.
unsafe impl Send for Battle {}

impl Default for Battle {
    fn default() -> Self {
        Battle([0u8; layout::BATTLE_SIZE])
    }
}

impl Battle {
    /// A fresh battle: parties in original order, `order[i] = i+1`, turn 0,
    /// actives zeroed, the u64 PSRNG seed at byte 376.
    ///
    /// This is the port of `helpers.zig::Battle.init` with one deliberate
    /// difference: the helper derives the battle seed from a parent PSRNG
    /// (`newSeed()`), while we write `seed` straight in. Any u64 is a valid
    /// PSRNG seed and the project's requirement is reproducibility from a
    /// documented derivation, not agreement with the helper (plan §3.5, §7.5).
    ///
    /// The first update of a fresh battle must be `(Pass, Pass)`: that is what
    /// switches both leads in and produces turn 1's requests.
    pub fn new(seed: u64, p1: &[[u8; layout::POKEMON_SIZE]], p2: &[[u8; layout::POKEMON_SIZE]]) -> Battle {
        let mut b = Battle::default();
        for (s, team) in [p1, p2].iter().enumerate() {
            assert!(!team.is_empty() && team.len() <= 6, "a side has 1..6 mons");
            let base = layout::B_SIDES + s * layout::SIDE_SIZE;
            for (i, mon) in team.iter().enumerate() {
                let at = base + layout::S_POKEMON + i * layout::POKEMON_SIZE;
                b.0[at..at + layout::POKEMON_SIZE].copy_from_slice(mon);
                b.0[base + layout::S_ORDER + i] = (i + 1) as u8;
            }
        }
        b.0[layout::B_RNG..layout::B_RNG + 8].copy_from_slice(&seed.to_le_bytes());
        b
    }

    pub fn view(&self) -> BattleView<'_> {
        BattleView(&self.0)
    }
    pub fn side(&self, p: Player) -> SideView<'_> {
        self.view().side(p.index())
    }
    pub fn turn(&self) -> u16 {
        self.view().turn()
    }
    pub fn seed(&self) -> u64 {
        self.view().seed()
    }
    pub fn as_bytes(&self) -> &[u8; layout::BATTLE_SIZE] {
        &self.0
    }
    /// The 384-byte memcpy the search line (JOURNEY 11.5) would consume.
    pub fn clone_into(&self, dst: &mut Battle) {
        dst.0.copy_from_slice(&self.0);
    }

    /// The legal choices for `p` given the request kind the previous update
    /// returned. In showdown mode this is never empty.
    pub fn choices(&self, p: Player, req: Request) -> Choices {
        let mut buf = [0u8; ffi::CHOICES_CAP];
        // SAFETY: `self.0` is a live 384-byte array we own; `buf` has
        // CHOICES_CAP >= the engine's CHOICES_SIZE (asserted in ffi's tests);
        // the engine writes at most `len` bytes and returns how many are valid.
        let n = unsafe {
            ffi::pkmn_gen1_battle_choices(
                self.0.as_ptr().cast(),
                p as ffi::pkmn_player,
                req.raw(),
                buf.as_mut_ptr(),
                buf.len(),
            )
        };
        debug_assert!(
            n as usize <= ffi::CHOICES_CAP,
            "engine returned {n} choices, cap is {}",
            ffi::CHOICES_CAP
        );
        Choices { buf, n }
    }

    pub fn is_legal(&self, p: Player, req: Request, c: Choice) -> bool {
        self.choices(p, req).contains(c)
    }

    /// Applies both choices simultaneously. Both are checked against the
    /// engine's own `choices()` first: passing an unoffered choice is UB.
    pub fn update(
        &mut self,
        req1: Request,
        c1: Choice,
        req2: Request,
        c2: Choice,
    ) -> Result<BattleResult, IllegalChoice> {
        for (p, req, c) in [(Player::P1, req1, c1), (Player::P2, req2, c2)] {
            let offered = self.choices(p, req);
            if !offered.contains(c) {
                return Err(IllegalChoice {
                    player: p,
                    choice: c,
                    request: req,
                    offered: offered.iter().collect(),
                });
            }
        }
        Ok(self.update_unchecked(c1, c2))
    }

    /// `update` without the legality check. Callers must have validated both
    /// choices against `choices()` for the CURRENT state.
    pub fn update_unchecked(&mut self, c1: Choice, c2: Choice) -> BattleResult {
        // SAFETY: the engine reads and writes only inside this 384-byte array,
        // which we own exclusively through `&mut self`; the null options pointer
        // is explicitly allowed by the C API; and both choices were offered by
        // `choices()` for this state, the engine's only stated precondition.
        let raw = unsafe {
            ffi::pkmn_gen1_battle_update(
                self.0.as_mut_ptr().cast(),
                c1.raw(),
                c2.raw(),
                std::ptr::null_mut(),
            )
        };
        BattleResult::from_raw(raw)
    }
}

impl std::fmt::Debug for Battle {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // Hex of the whole state: enough to replay a failure with the
        // `debug-log` build (plan §5.6).
        write!(f, "Battle(turn={}, bytes=", self.turn())?;
        for b in self.0.iter() {
            write!(f, "{b:02x}")?;
        }
        write!(f, ")")
    }
}

/// PS's Gen V/VI 64-bit LCG with 32-bit output, exposed for the layout proof
/// and for seed derivation (`common/rng.zig`).
pub struct PsRng(u64);

impl PsRng {
    pub fn new(seed: u64) -> PsRng {
        PsRng(seed)
    }
    pub fn seed(&self) -> u64 {
        self.0
    }
    pub fn next(&mut self) -> u32 {
        // SAFETY: `pkmn_psrng` is an 8-byte POD we own; init/next only touch it.
        unsafe {
            let mut r = ffi::pkmn_psrng {
                bytes: self.0.to_le_bytes(),
            };
            let out = ffi::pkmn_psrng_next(&mut r);
            self.0 = u64::from_le_bytes(r.bytes);
            out
        }
    }
    pub fn advance(&mut self) {
        let _ = self.next();
    }
}

/// `splitmix64`, the per-battle seed derivation (plan §7.5).
pub fn splitmix64(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = x;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn choice_bits_match_the_engines_unit_tests() {
        // `common/data.zig` pins these exact values.
        assert_eq!(Choice::Move(4).raw(), 0x11, "Move slot 4");
        assert_eq!(Choice::Switch(5).raw(), 0x16, "Switch slot 5");
        assert_eq!(Choice::Pass.raw(), 0x00, "the pass choice is always 0");
        for c in [
            Choice::Pass,
            Choice::Move(0),
            Choice::Move(4),
            Choice::Switch(2),
            Choice::Switch(6),
        ] {
            assert_eq!(Choice::from_raw(c.raw()), c);
        }
    }

    #[test]
    fn choice_bits_match_the_c_api() {
        for (kind, data) in [(0u8, 0u8), (1, 0), (1, 4), (2, 2), (2, 6)] {
            // SAFETY: pure function over two scalars.
            let raw = unsafe { ffi::pkmn_choice_init(kind, data) };
            let ours = match kind {
                0 => Choice::Pass,
                1 => Choice::Move(data),
                _ => Choice::Switch(data),
            };
            assert_eq!(ours.raw(), raw, "kind={kind} data={data}");
            // SAFETY: pure functions over one scalar.
            unsafe {
                assert_eq!(ffi::pkmn_choice_type(raw), kind);
                assert_eq!(ffi::pkmn_choice_data(raw), data);
            }
        }
    }

    #[test]
    fn result_bits_match_the_engines_unit_tests() {
        let r = BattleResult::from_raw(0x50);
        assert_eq!(r.outcome, Outcome::None);
        assert_eq!(r.p1, Request::Move);
        assert_eq!(r.p2, Request::Move);
        assert_eq!(r.raw(), 0x50, "both players choose a move");
        assert_eq!(BattleResult::from_raw(0).outcome, Outcome::None);
        assert_eq!(BattleResult::from_raw(0).p1, Request::Pass);
        // The three mid-turn faint shapes named in plan §3.4.
        assert_eq!(
            BattleResult::from_raw(0x20).raw(),
            BattleResult {
                outcome: Outcome::None,
                p1: Request::Switch,
                p2: Request::Pass
            }
            .raw()
        );
        assert_eq!(
            BattleResult {
                outcome: Outcome::None,
                p1: Request::Pass,
                p2: Request::Switch
            }
            .raw(),
            0x80
        );
        assert_eq!(
            BattleResult {
                outcome: Outcome::None,
                p1: Request::Switch,
                p2: Request::Switch
            }
            .raw(),
            0xA0
        );
    }

    #[test]
    fn result_bits_match_the_c_api() {
        for raw in 0u8..=255 {
            if raw & 0x0F > 4 || (raw >> 4) & 3 == 3 || (raw >> 6) & 3 == 3 {
                continue; // undefined encodings
            }
            // SAFETY: pure functions over one scalar.
            let (k, p1, p2) = unsafe {
                (
                    ffi::pkmn_result_type(raw),
                    ffi::pkmn_result_p1(raw),
                    ffi::pkmn_result_p2(raw),
                )
            };
            let r = BattleResult::from_raw(raw);
            assert_eq!(r.p1, Request::from_raw(p1), "raw={raw:#04x}");
            assert_eq!(r.p2, Request::from_raw(p2), "raw={raw:#04x}");
            assert_eq!(r.raw(), raw, "raw={raw:#04x}");
            assert_eq!(k, raw & 0x0F);
        }
    }

    #[test]
    fn splitmix64_is_the_reference_implementation() {
        // Vectors from the canonical splitmix64 (Vigna), state starting at 0.
        assert_eq!(splitmix64(0), 0xE220A8397B1DCDAF);
        assert_eq!(splitmix64(0x9E3779B97F4A7C15), 0x6E789E6AA1B965F4);
    }
}

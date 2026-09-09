//! Raw FFI layer over `libpkmn-showdown`. Only `battle.rs` may touch it.
//!
//! `ffi_generated.rs` is committed bindgen output (plan §4.4): regenerating it
//! needs libclang, and requiring that for every `pip install -e` is exactly the
//! kind of environment dependency this repo has paid for before. Regenerate with
//! `cargo build --features regen-bindings` when the engine pin moves.
#![allow(non_upper_case_globals, non_camel_case_types, non_snake_case, dead_code)]

include!("ffi_generated.rs");

/// The engine commit this artifact was built from (baked in by `build.rs`).
pub const ENGINE_SHA: &str = env!("PKMN_ENGINE_SHA");
/// The Zig version that compiled it.
pub const ZIG_VERSION: &str = env!("PKMN_ZIG_VERSION");
/// The pin this crate is written against (plan §1.1). `verify()` compares.
pub const ENGINE_SHA_PINNED: &str = "9b88fd6c5467f703c38951d5b2e8a660314d410b";

/// Gen 1 battle state size. Cross-checked against the header's constant below.
pub const BATTLE_SIZE: usize = 384;
/// Upper bound on `pkmn_gen1_battle_choices` output. Checked against
/// `PKMN_GEN1_CHOICES_SIZE` (a link-time `extern const`) at test time.
pub const CHOICES_CAP: usize = 16;

const _: () = assert!(BATTLE_SIZE == PKMN_GEN1_BATTLE_SIZE as usize);
const _: () = assert!(std::mem::size_of::<pkmn_gen1_battle>() == BATTLE_SIZE);

/// What the linked `.a` was actually built with.
pub fn options() -> (bool, bool, bool, bool) {
    // SAFETY: `PKMN_OPTIONS` is an `extern const` of four bools in the static
    // library; reading it is a plain load from read-only data.
    let o = unsafe { PKMN_OPTIONS };
    (o.showdown, o.log, o.chance, o.calc)
}

/// The engine's own reported choice-buffer sizes (link-time constants).
pub fn choice_sizes() -> (usize, usize) {
    // SAFETY: `extern const size_t` in the static library.
    unsafe { (PKMN_GEN1_MAX_CHOICES, PKMN_GEN1_CHOICES_SIZE) }
}

/// Fails unless the library was built exactly the way the collector requires.
///
/// `log` must be off for training: the collector derives everything from state
/// diffs (plan §7.1), and a log build changes `LOGS_SIZE` and makes
/// `PKMN_RESULT_ERROR` reachable.
pub fn verify_options() -> Result<(), String> {
    let (showdown, log, chance, calc) = options();
    let want_log = cfg!(feature = "debug-log");
    if !showdown {
        return Err("libpkmn was built without -Dshowdown; the collector's whole \
                    parity target is Showdown mode"
            .into());
    }
    if log != want_log {
        return Err(format!(
            "libpkmn -Dlog={log} but the crate was built with debug-log={want_log}"
        ));
    }
    if chance || calc {
        return Err(format!(
            "libpkmn built with -Dchance={chance} -Dcalc={calc}; the collector \
             requires both off (they belong to the search line, plan §10)"
        ));
    }
    if ENGINE_SHA != ENGINE_SHA_PINNED {
        return Err(format!(
            "engine commit {ENGINE_SHA} != pinned {ENGINE_SHA_PINNED}; moving the \
             pin re-runs gates B-0..P-2 (plan §10)"
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn built_the_way_the_collector_needs() {
        verify_options().unwrap();
        assert_eq!(options(), (true, cfg!(feature = "debug-log"), false, false));
    }

    #[test]
    fn choice_buffer_cap_covers_the_engine() {
        let (max, size) = choice_sizes();
        assert_eq!(max, 9, "MAX_CHOICES: move 1..4 + switch 2..6");
        assert!(
            CHOICES_CAP >= size,
            "CHOICES_CAP {CHOICES_CAP} < engine CHOICES_SIZE {size}"
        );
        assert_eq!(size, 16, "ReleaseFast rounds to the next power of two");
    }

    #[test]
    fn sizes_match_the_header() {
        assert_eq!(BATTLE_SIZE, 384);
        assert_eq!(PKMN_PSRNG_SIZE as usize, 8);
        assert_eq!(std::mem::size_of::<pkmn_psrng>(), 8);
    }
}

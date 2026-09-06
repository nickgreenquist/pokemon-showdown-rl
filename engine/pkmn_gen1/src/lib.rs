//! In-process Gen 1 collector for `pokemon-showdown-rl`.
//!
//! Borrowed: this crate is a thin safe wrapper over **pkmn/engine**
//! (<https://github.com/pkmn/engine>), MIT, © 2021-2024 pkmn contributors,
//! vendored at `vendor/pkmn-engine` and pinned to commit
//! `9b88fd6c5467f703c38951d5b2e8a660314d410b`. The engine is built in its
//! `-Dshowdown` mode, whose parity target is a patched Pokémon Showdown.
//!
//! Spec: `docs/PKMN_ENGINE_RUST_PLAN.md`. Nothing here is pre-registered; the
//! collector is not licensed until gate A-1 passes (plan §9).
#![cfg_attr(target_endian = "big", allow(unused))]
#[cfg(target_endian = "big")]
compile_error!("pkmn/engine stores its battle state in native endianness; \
                this crate decodes little-endian only");

pub mod battle;
pub mod data;
pub mod ffi;
pub mod layout;
pub mod smoke;
pub mod team;

mod python;

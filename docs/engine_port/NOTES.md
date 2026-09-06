# pkmn/engine collector port — working notes

Branch `pkmn-engine-port`, worktree
`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-engine`.
Spec: `docs/PKMN_ENGINE_RUST_PLAN.md`. Operating envelope:
`docs/engine_port_session_brief.md`. This file is the log the brief §5 asks for:
every gate with its exact numbers, the block budget against actual, and every
decision the plan did not already make.

**Nothing here is pre-registered.** The collector is not licensed until A-1, and
A-1, D-1 and T-1 are OUT OF SCOPE while the gen-4 fleet runs.

## Environment (session brief §1.1 overrides CLAUDE.md rule 1)

Own conda env `pkmn-engine-port` (`/opt/anaconda3/envs/pkmn-engine-port`, Python
3.13.15). The fleet's `pokemon-showdown-rl` env was never activated and never
installed into. Toolchain: `cargo`/`rustc` 1.97.1 (on the box),
`ziglang==0.16.0` + `maturin==1.15.0` (this env only). No Showdown server was
started and nothing connected to the running one.

Every build and test ran under `taskpolicy -b` at `-j2`.

## Block budget (brief §4)

Plan §12 estimates steps 1–7 (which is exactly this session's scope, B-0 → P-2)
at 10–12 evening blocks. Declared budget, by gate:

| gate | budget | actual |
|---|---|---|
| B-0 build | 2 | 1.0 |
| B-1 loop smoke | 1 | |
| P-4 stats | 1 | |
| P-3 teams | 1 | |
| P-1 encoder parity | **3** | |
| P-2 mask parity | **1** | |
| slack | 1 | |
| total | **10** | |

**P-1 + P-2 hard stop at 5 blocks combined.** On reaching it: stop and write up
what is blocking, with evidence, rather than grinding (brief §4).

A block is one evening's work. `2026-09-06 22:30Z–23:00Z` counts as 1.0 (B-0 ran
long on setup but short on debugging).

---

## Gate B-0 — build — **PASS** (2026-09-06)

| item | result |
|---|---|
| vendored engine | submodule at `9b88fd6c5467f703c38951d5b2e8a660314d410b`; upstream `HEAD` was verified to be exactly the pin at clone time |
| `zig build -Dshowdown=true -Dlog=false -Dchance=false -Dcalc=false -Doptimize=ReleaseFast -Dpic=true -Dstrip=true` | 25.6 s wall; `lib/libpkmn-showdown.a` 36,576 B; all 20 `pkmn_*` exports present |
| engine's own Zig suite at the pin (`zig build test -Dshowdown=true`) | **257 passed, 168 skipped (425 total)**, 16/16 build steps, 43.5 s |
| no global mutable state in the C bindings | `src/lib/bindings/c.zig`: zero file-scope `var`; every export takes caller pointers. This is the premise of `unsafe impl Send for Battle` |
| `pkmn_gen1.verify()` | `engine_sha` == pin, `zig` 0.16.0, `battle_size` 384, `max_choices` 9, `choices_size` 16, `PKMN_OPTIONS == {showdown: true, log: false, chance: false, calc: false}` |
| Rust tests | **18 passed** (`cargo test`): 8 unit + 10 integration |
| Python tests | **7 passed** (`pytest tests/test_engine_b0.py`) |

### What the Rust tests actually pin

- **Offsets** — all of `Battle` / `Side` / `Pokemon` / `ActivePokemon` / `Stats` /
  `Boosts` and all 26 `Volatiles` bit offsets are asserted against the vendored
  `src/data/layout.json`, not against this document.
- **The two showdown-mode overrides are proved at RUNTIME, not read off a doc.**
  `layout.json` documents the non-showdown form (`rng` at 374). In showdown mode
  `MoveDetails` is `packed struct(u16)` (`src/lib/gen1/data.zig:230`), so
  `last_moves` is 4 bytes and the u64 PSRNG seed sits at 376. The test writes a
  known seed at 376, plays three attacking turns, and shows the bytes at 376..384
  are a forward iterate of `PSRNG(seed)` — found within 4096 steps. Nothing about
  that can hold by accident.
- **Choice/Result bits** — `Move(4) = 0x11`, `Switch(5) = 0x16`, `Pass = 0x00`,
  the both-move default `Result = 0x50`, and the three mid-turn faint shapes
  `0x20 / 0x80 / 0xA0`. Checked BOTH against the engine's own unit-test values
  AND round-tripped through the C accessors (`pkmn_choice_init`,
  `pkmn_result_p1/p2`) over every defined encoding.
- **Structure** — a fresh battle has `order == [1..6]`, zeroed actives, turn 0;
  `order`/`slot_of_party_index` stay mutual inverses across a switch;
  `choices()` is never empty in showdown mode; an unoffered choice is refused by
  the wrapper instead of reaching the engine (which documents it as UB).

### What the Python tests pin

- **Name-map identity, both directions of the plan's claim.** All 151 engine
  species map onto poke-env's gen-1 dex `num` as the identity (engine enum
  `i` == `num`), and all 165 engine moves onto the gen-1 movedex `num`. Keys are
  normalised with poke-env's own `to_id_str`, not an ad-hoc rule.
- **Base stats and types agree** between the engine's `data.json` (what it
  SIMULATES with) and poke-env's dex (what the OBSERVATION is built from), for
  all 151, including `spa == spd == spc`.
- **Max PP agrees** for all 165: `min(base_pp // 5 * 8, 61)` == poke-env's
  `Move.max_pp`. Base PP agrees too.
- **Type order**: the engine's 15 types are cartridge order, confirmed against
  the list the encoder's alphabetical one-hot will have to permute.

### Fleet impact of B-0 (brief §2)

Lane rate is not in the wave log, so `scripts/engine_port_fleet_guard.sh`
computes dStep/dWall from the two newest checkpoints per lane (500k steps apart,
~40 min resolution) — a rate, which is what CLAUDE.md requires.

| window | s200 | s208 | s216 |
|---|---|---|---|
| before any build (22:45Z) | 203.4 | 190.2 | 201.3 |
| spanning every B-0 build (22:58Z) | 202.3 | 200.6 | 201.3 |

All ≥ 180 throughout; s208 rose. Peak concurrent load 5.3 of 14 cores; the
session's own footprint stayed under ~0.5 GB. No lane died, no `caffeinate` or
watcher was touched.

## Decisions the plan did not make (and corrections to it)

1. **`pyo3/extension-module` is maturin-only, not a crate default.** Plan §4.3
   lists `pyo3 = { version = "=0.29.2", features = ["extension-module"] }`. With
   that feature always on, the crate's own test binaries cannot link (no
   libpython) and **the entire B-0 Rust gate cannot run**. `[tool.maturin]
   features = ["pyo3/extension-module"]` already turns it on for the wheel, which
   is the only build that needs it. *Plan §4.3 is wrong as written; fixed on the
   branch.*
2. **`build.rs` emits an rpath to the interpreter's `LIBDIR`.** For the same
   reason: a conda `libpython3.13.dylib` is not on dyld's default search path, so
   `cargo test` aborts at load. Harmless for the maturin build, which never
   resolves it.
3. **`serde_json = "=1.0.151"` as a DEV-dependency**, so the layout test parses
   the engine's own `layout.json` instead of trusting a transcription. Dev-only:
   it is not linked into the extension.
4. **`zig build` gets `-j2` inside `build.rs`**, not just on the command line, so
   an installer cannot accidentally run it wide next to a fleet.
5. **`Battle::new` writes the u64 seed directly**, where `helpers.zig::Battle.init`
   derives it from a parent PSRNG via `newSeed()`. Any u64 is a valid PSRNG seed;
   the project needs reproducibility from a documented derivation (plan §7.5),
   not agreement with a Zig helper that is not exported to C anyway.
6. **`verify()` also checks the engine sha against the pin**, which plan §4.5
   describes in prose but does not list among the asserted fields.

## Owed, not done (cannot be done on this branch)

- **README provenance.** Repo rule: name anything borrowed in the README. The
  session brief §1.6 forbids editing `README.md` (it belongs to the gen-4
  readout). The pkmn/engine line (MIT, © 2021-2024 pkmn contributors, commit
  `9b88fd6c…`) is therefore **OWED and must land when this branch merges**.
  Provenance comments ARE in place in `Cargo.toml`, `src/lib.rs` and
  `.gitmodules`.
- `requirements-engine.txt`: written on this branch (plan §4.5), but its "install
  into `pokemon-showdown-rl`" wording is deliberately NOT followed here — this
  session installs into its own env per the brief.

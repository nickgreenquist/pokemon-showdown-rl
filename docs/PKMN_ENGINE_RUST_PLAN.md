# pkmn/engine → Rust → Python: an in-process Gen 1 collector

**STATUS: DESIGN ONLY.** Written 2026-09-04 on branch `pkmn-engine-plan` (a git
worktree off `main` at df3fe8f, opened while LADDER R4 was running on `main`).
No application source was written or modified; every code block below is a
sketch to be implemented, not a copy of anything in the tree. Nothing here is
pre-registered or ratified.

**Where it sits (JOURNEY):** infrastructure for the gen 1 lane — steps 8, 10, 11
and 11.5, and the constraint IDEAS_POST_100M §1 says orders everything (σ_seed
≈ 0.062 at k=3: more seeds per wall-clock is the lever). It is OFF the current
arc (step 2 running; step 3 gen 4 next) and **it does nothing for gen 4 or
gen 9: pkmn/engine implements RBY completely and GSC as a WIP; DPP is the
engine's "stage 2" and is not implemented at the pinned commit.** Implementing
this needs a maintainer ruling. Writing this document was maintainer-ordered
(2026-09-04: "wrap pkmn/engine via C bindings in Rust first").

Repo conventions this plan is written under: pin exact versions; name anything
borrowed (README + code comments); quote collection-only throughput with the
network width and never fold it into a full-loop claim (CLAUDE.md landmines);
changing `OBS_DIM` invalidates every checkpoint; the locked eval protocol is
vs `SimpleHeuristicsPlayer` on the Showdown server and is not touched here.

---

## 0. Verdict, in one screen

- **What it buys.** Collection stops being Node-bound. Today's collection path
  is ~1.5–1.85 ms of websocket/Node/poke-env latency per decision (THROUGHPUT_SPEC
  §1b); the engine plays a whole RBY battle in ~20 µs on one core (its own
  benchmark: 10,000 Challenge-Cup battles in 195 ms, docs/TESTING.md). The
  per-decision cost on the new path is the policy forward passes, batched across
  K in-flight battles, plus a few microseconds of Rust. Projection (§9, T-1
  measures it): collection-only ≥ 25k learner steps/s at K=256 at entity width,
  versus 1,218 decisions/s (K=8, collection-only, entity width) today.
- **What it does NOT buy — the honest ceiling.** The PPO update on the 100M
  recipe costs ~12.0 s per 30,720-step rollout (`scripts/ch5_mps_update_bench.py`;
  11.3 s logged live). At the realized 560 steps/s a rollout is ~55 s wall, so the
  update is already ~21% of it. With collection at ~1 s the full loop lands near
  **30,720 / 13 ≈ 2,350 steps/s per lane ≈ 4.2×**, and the learner becomes ~90%
  of wall time. Any "50×" number is collection-only and must be quoted that way.
- **The scientific lever is fleet width, not lane speed.** Engine lanes need no
  server, no accounts, no `/timer on`, no orphaned-room deadlock. They are
  bounded by cores (14) and RAM (~2.7 GB/lane at 3-wide; a solo lane was seen at
  5.87 GB — learner buffers, not the env). 8 lanes = 8 seeds per fleet-day
  instead of 3, which is the only thing that shrinks σ_seed.
- **New capability:** every battle is reproducible from a 64-bit seed (teams and
  rolls). Paired evaluation with common random numbers becomes possible
  (docs/research_reports Q1/Q2 §2.7); it is impossible on the server path.
- **What it costs.** A Rust crate + a PyO3 extension, a Zig toolchain, a
  re-implementation of the 828-dim encoder against an *observable-state
  tracker* that must reproduce poke-env's information boundary exactly, and an
  acceptance fleet before any number from it is comparable to anything banked.
  Rough effort: 12–16 evening blocks plus one fleet-day (§12).
- **The two invariants the whole plan rests on.** (I1) the observation is a
  function of what poke-env could observe from the protocol — never of the
  engine's hidden state (§7.1). (I2) the 10-way action space, the mask and the
  block/slot orderings are poke-env's, bit-for-bit where the information exists
  (§7.2). Both are gated by tape-replay parity tests before any training.

---

## 1. What was researched (sources and pins)

### 1.1 pkmn/engine (read from a shallow clone, not from memory)

| item | value |
|---|---|
| repository | https://github.com/pkmn/engine — MIT, "© 2021-2024 pkmn contributors" |
| commit read | `9b88fd6c5467f703c38951d5b2e8a660314d410b` (2026-09-02, "MAX_FRONTIER += 4") — **PIN THIS** |
| release state | **no GitHub releases exist**; README: "under heavy development … breaking changes … wait for v0.1". npm `@pkmn/engine` is `0.1.0-dev.207fa86a` (2026-08-05) |
| language / build | Zig; `build.zig.zon` says `minimum_zig_version = "0.16.0"`; README: "should work on Zig v0.16.0, though tracks Zig's master branch" |
| Zig 0.16.0 | released 2026-04-13 (ziglang.org/download); macOS aarch64 tarball provided; `pip install ziglang==0.16.0` exists on PyPI |
| generations | `src/lib/gen1` (RBY, complete, 466 KB of tests), `src/lib/gen2` (GSC, README is `TODO`). No gen3/gen4 directories. |
| C API | `src/include/pkmn.h` (about twenty small functions, seven opaque types, four compile-time flags) — the parts this plan uses are reproduced in §3.2 |
| layout docs | `src/lib/gen1/README.md` §Layout (byte/bit offsets), `src/data/layout.json` (machine-readable, **non-showdown layout** — see §3.3 for the two showdown-mode differences) |
| data dumps | `src/data/data.json`: gen 1 `types` (15, cartridge order), `species` (151, dex order, base stats + types), `moves` (165, index order, base PP) |
| helpers | `src/lib/gen1/helpers.zig` — Zig-only battle/side/pokemon constructors and the stat formula; **not exported to C** (the wrapper ports them, §5.5) |
| benchmark | docs/TESTING.md §Results: RBY, 10,000 battles: `libpkmn` 195 ms, `@pkmn/engine` (Node addon) 737 ms, patched PS `DirectBattle` 618 s (3167×). Challenge-Cup sets; randbats sets "2-3× faster in practice" |
| parity target | the engine's `-Dshowdown` mode matches a **patched** PS (three patches: no `speedSort` in gen 1/2 `eachEvent`/`fieldEvent`, host-ordered `insertChoice`, handler priorities that remove spurious speed-tie rolls). Its integration tests pin `@pkmn/sim 0.9.31` |
| known PS-mode bugs reproduced | `src/lib/gen1/README.md` §Bugs — Bide overflow, Counter, Leech Seed, Flinch across faints, Rage/Thrash accuracy, Hyper Beam PP, Roar/Whirlwind miss, Substitute 1/4 glitch, Sleep/Freeze/Desync/Endless Battle/Switch Priority clause mods |
| existing bindings | C++ `pasyg/wrapsire` (BSL-1.0), Python `AnnikaCodes/PyKMN` (MIT, cffi, pinned to an old engine commit `f55b950`, 6 stars). Neither is used here; PyKMN is a reference for the cffi shape only |

### 1.2 This repository (what "the existing Rust setup" actually is)

- **There is no Rust in the repo.** No `Cargo.toml`, no `.rs`. The toolchain
  exists on the box (`cargo 1.97.1`, `rustc 1.97.1`, `rustup` under
  `~/.cargo/bin`). `zig` and `maturin` are **not** installed. Node is v25.9.0.
- **The precedent for a Rust dependency** is the chapter-3 search line:
  `poke-engine==0.0.48` (pmariglia, MIT) is built from source by pip with
  `--config-settings="build-args=--features poke-engine/gen1 --no-default-features"`
  (`requirements-search.txt`, kept OUT of `pyproject.toml` by maintainer ruling
  2026-08-21 because PEP 621 cannot carry per-requirement build flags), and the
  build is verified every time by a discriminator (`scripts/ch3_fidelity_check.py
  --fg5`). This plan follows that pattern exactly (§4.5).
- **The environment stack.** `rl/envs/showdown.py` (1,366 lines) is a poke-env
  `SinglesEnv` + a Gym adapter over a local Node Showdown server (vendored at
  `showdown/`, PS 0.11.11 at commit `59da482e`, 2026-07-29, `simulator: 4`).
  `OBS_DIM = 828` with `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1` (the
  100M object); `N_ACTIONS = 10`. Per-generation tables live in
  `rl/envs/encoder_spec.py::GEN1`; the vendored set prior in
  `rl/envs/randbats_prior.py` (+ `rl/envs/data/gen1_randbats_sets.json`).
- **The collection loop the 100M recipe ran on** is the Stage-2 async collector
  (`rl/envs/showdown_async.py::AsyncCollector`, `rl/train.py::_async_loop`):
  K=8 concurrent battles on poke-env's `POKE_LOOP`, batch-1 inference through a
  gated seam, whole episodes only, `agent.update_episodes` with per-episode GAE
  (`rl/buffers/episode.py`). Opponents are `PoolPlayer` (snapshot pool of past
  selves, `rl/selfplay/pool.py`) or scripted poke-env players.
- **Throughput baselines** (quote with these labels): realized whole-lane
  dStep/dWall on the 100M fleet **562.8 / 558.2 / 557.5 steps/s** (RESULTS §18;
  never the `time/steps_per_sec` estimator, which overstates ~57% on async);
  `embed_battle` 133 µs/decision live (E3), 52.7–58.6 µs in isolation; MLP
  [512,512] forward 19.1 µs at B=1, 3.3 µs/sample at B=256 (THROUGHPUT_SPEC
  §1a); the entity trunk's per-sample cost at batch is **unmeasured** (T-1).
- **Tapes for parity tests exist:** `data/fp_tapes*/run_*.jsonl` are raw
  Showdown protocol + `|request|` JSON, replayable through poke-env
  (`tests/test_encoder_ids_tapes.py` shows the replay shape; ≥ 5,000 decisions).

### 1.3 Version pins this plan proposes

| component | pin | why this one |
|---|---|---|
| pkmn/engine | commit `9b88fd6c5467f703c38951d5b2e8a660314d410b` | the commit read; no release exists |
| Zig | `ziglang==0.16.0` (pip wheel) | the engine's stated minimum; a released version, not a nightly |
| Rust | `rust-version = "1.97"` (installed 1.97.1) | what is on the box |
| pyo3 | `=0.29.2` (crates.io max 2026-08-05) | current; supports 3.13 |
| numpy (rust crate) | `=0.29.0` (2026-06-13) | must match pyo3 0.29 |
| bindgen | `=0.72.1` (crates.io max, 2025-08-31) | latest stable; used only under a `regen-bindings` feature (§4.4) |
| maturin | `==1.15.0` (PyPI, released 2026-08-24) | current |
| Showdown for the team bank | the vendored `59da482e` | the same generator LG-5 pins for the ladder |

---

## 2. Architecture overview

```
TODAY (per learner decision, ~1.5-1.85 ms, Node-bound)

  learner Player ──websocket──▶ Node Showdown ◀──websocket── opponent Player
       │  parse protocol (poke-env)                             │ parse + encode
       │  embed_battle 133 us                                   │ pool member forward
       ▼                                                        ▼
  GatedSeam.request(obs, mask)  ── batch-1 torch forward ──▶ action_to_order
       │
       └── _EpisodeBuilder rows ──▶ AsyncCollector.poll() ──▶ EpisodeDataset ──▶ agent.update_episodes

PROPOSED (per batched step over K battles; no server, no sockets, no asyncio)

  ┌───────────────────────────── Rust crate `pkmn-gen1` (PyO3 module `pkmn_gen1`) ─────────────────────────────┐
  │  vendor/pkmn-engine  ──zig build -Dshowdown──▶  libpkmn-showdown.a  ──bindgen──▶  ffi::pkmn_gen1_battle_*   │
  │  battle.rs   safe Battle/Choice/Result + typed byte views (layout.json offsets, asserted)                    │
  │  team.rs     TeamBank (PS-generated sets) → engine Pokemon bytes (PS stat formula)                           │
  │  observe.rs  per-seat OBSERVABLE tracker: revealed mons/moves, elapsed sleep turns, HP% quantisation (I1)    │
  │  encoder.rs  828-dim obs from tracker + static tables handed in from Python (poke-env is the only source)    │
  │  env.rs      BatchEnv: K battles, request-kind state machine, mask (I2), Pass pumping, auto-restart          │
  └──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                 ▲ numpy views (obs [n,828] f32, mask [n,10] bool, idx)            │ finished episodes (dicts)
                 │                                                                 ▼
  rl/envs/engine_collector.py  EngineCollector  — same main-thread surface as AsyncCollector
       learner rows ─▶ agent.act_logp (ONE forward, batch n)         opponent rows ─▶ pool members, batched BY MEMBER
       ─▶ env.step(learner actions+logp+version, opponent actions)  ─▶ poll() → EpisodeDataset → update_episodes
  rl/train.py::_async_loop — unchanged cadences (eval, ckpt ladder, pool push, metric names); collector.mode: engine
```

What stays untouched: the learner (`rl/agents/ppo.py`), the episode dataset,
the snapshot pool and its retention rule, the locked eval protocol (server +
`SimpleHeuristicsPlayer`), every grader. What changes: where transitions come
from. What is deliberately NOT built: a gen 4 path (no engine), a Showdown
protocol emulator, a new encoder (the 828-dim layout is reproduced, not
redesigned — the OBS_DIM landmine).

Two seats, one process. Both seats are encoded by the same Rust encoder from
their own perspective (the pool members need seat-2 observations to move, as
`PoolPlayer` does today). Seat-2 rows are produced anyway, which is what makes
IDEAS_POST_100M 4.1 (both-seat harvest) free later — but harvesting them is a
separate pre-reg, not part of this build.

---

## 3. pkmn/engine facts the design rests on

Everything in this section was read from the pinned commit; file references
are to the engine tree. The implementer should re-read them at B-0 rather than
trust this summary if the pin ever moves.

### 3.1 Build system and flags (`build.zig`, `build.zig.zon`, `Makefile`)

```
zig build -Dshowdown=true -Dlog=false -Dchance=false -Dcalc=false \
          -Doptimize=ReleaseFast -Dpic=true -Dstrip=true --prefix <PREFIX>
```

| flag | default | effect | this plan |
|---|---|---|---|
| `-Dshowdown` | false | Pokémon Showdown compatibility mode: PS's Gen V/VI RNG, PS bugs, Sleep/Freeze/Desync clause mods, **Endless Battle Clause and the 1000-turn tie** (`options.mod = showdown`, `ebc` default true; `mechanics.zig::endTurn`). Output library is named `pkmn-showdown` instead of `pkmn` | **on** |
| `-Dlog` | false | binary protocol logging into a caller buffer each update (`PKMN_GEN1_LOGS_SIZE` = 256 bytes in ReleaseFast) | **off** for the collector (§7.1 uses state diffs); on for a debug build (§10) |
| `-Dchance` | false | tracks the probability of the chance events observed in an update (rational) | off; relevant to search (§10) |
| `-Dcalc` | false | lets the caller override RNG outcomes (damage roll, crit, hit, …) per update | off; relevant to search (§10) |
| `-Ddynamic` | false | build a shared library instead of static | off (static into the cdylib) |
| `-Dpic` | null | force position-independent code | **on** — the `.a` is linked into a Python extension `.so` |
| `-Dstrip` | null | strip symbols | on for release, off while debugging |
| `-Doptimize` | Debug | `ReleaseFast` for speed (`ReleaseSmall` changes `CHOICES_SIZE`/`LOGS_SIZE` to the non-power-of-two minimums) | `ReleaseFast` |

Artifacts under `<PREFIX>`: `lib/libpkmn-showdown.a` and `include/pkmn.h`
(installed by `build.zig`; the header is `src/include/pkmn.h`). `build.zig`
`@embedFile`s `package.json` for the version string, so the vendored checkout
must be the whole repository (submodule or full tarball), not `src/` alone.
The `Makefile`'s `zig-build` target shows the maintainers' own configuration:
`-Dlog -Dchance -Dcalc` with and without `-Dshowdown`, `-p build`.

### 3.2 The C API (`src/include/pkmn.h`, verbatim semantics)

```c
typedef struct { bool showdown; bool log; bool chance; bool calc; } pkmn_options;
extern const pkmn_options PKMN_OPTIONS;              // what the .a was built with — ASSERT at import
extern const size_t PKMN_GEN1_MAX_CHOICES;           // 9  (move 1..4, switch 2..6)
extern const size_t PKMN_GEN1_CHOICES_SIZE;          // 16 in ReleaseFast (next power of two)
extern const size_t PKMN_GEN1_MAX_LOGS, PKMN_GEN1_LOGS_SIZE;   // 180 / 256
#define PKMN_GEN1_BATTLE_SIZE 384
#define PKMN_GEN1_BATTLE_OPTIONS_SIZE 128
#define PKMN_PSRNG_SIZE 8

typedef uint8_t pkmn_choice;   // bits 0-1: kind (0 PASS, 1 MOVE, 2 SWITCH); bits 2-7: data
pkmn_choice pkmn_choice_init(pkmn_choice_kind type, uint8_t data);   // data <= 6
typedef uint8_t pkmn_result;   // bits 0-3: kind (0 NONE, 1 WIN, 2 LOSE, 3 TIE, 4 ERROR) from P1's view;
                               // bits 4-5: P1's next request kind; bits 6-7: P2's next request kind
pkmn_result_kind pkmn_result_type(pkmn_result); pkmn_choice_kind pkmn_result_p1(pkmn_result), pkmn_result_p2(pkmn_result);
bool pkmn_error(pkmn_result);  // only possible with -Dlog and an undersized buffer

typedef struct { uint8_t bytes[384]; } pkmn_gen1_battle;             // POD, native-endian, no init function in C
pkmn_result pkmn_gen1_battle_update(pkmn_gen1_battle *b, pkmn_choice c1, pkmn_choice c2, pkmn_gen1_battle_options *opts /* NULL ok */);
uint8_t     pkmn_gen1_battle_choices(const pkmn_gen1_battle *b, pkmn_player p, pkmn_choice_kind request, pkmn_choice out[], size_t len);

void     pkmn_psrng_init(pkmn_psrng *r, uint64_t seed);  uint32_t pkmn_psrng_next(pkmn_psrng *r);
```

Bit layouts (Zig `packed struct`s are LSB-first; `src/lib/common/data.zig` has
the unit tests that pin them): `Choice{type:u2, data:u6}` → `Move slot 4` =
`0x11`, `Switch slot 5` = `0x16`; `Result{type:u4, p1:u2, p2:u2}` → the
"both players choose a move" default is `0x50`. **The pass choice is always
`0`, and `PKMN_RESULT_NONE` is always `0`** (the C example relies on both).

Two contract lines from the README that shape the wrapper (§5.4):
"*Attempting to update the battle with a choice not present in the options
returned by `choices` is undefined behavior and may corrupt state or cause the
engine to crash*", and "*to freshly initialize a battle which is yet to start
the turn count and active Pokémon should be zeroed out*" — the first update of
a fresh battle is `update(PASS, PASS)`, which switches in both leads and
returns turn 1's requests.

### 3.3 Battle layout (384 bytes; `src/lib/gen1/README.md` §Layout, `src/data/layout.json`)

| bytes | field | notes |
|---|---|---|
| 0–184 | `sides[0]` (P1) | `Side`, 184 bytes |
| 184–368 | `sides[1]` (P2) | |
| 368–370 | `turn` u16 | native endian; 0 before the first update |
| 370–372 | `last_damage` u16 | |
| 372–376 | `last_moves` | **showdown mode: 4 bytes** (P1 last selected index, P1 counterable, P2 index, P2 counterable). `layout.json` documents the non-showdown 2-byte form |
| 376–384 | `rng` | **showdown mode: one u64 PSRNG seed at 376**. Non-showdown: 9 seed bytes + index at 374 |

`Side` (184): `pokemon[6]` × 24 at 0 (the party in ITS ORIGINAL ORDER),
`active` (32) at 144, `order[6]` u8 at 176 (one-based slot → `pokemon` index:
`order[i]` is the party index of the mon currently in slot i+1; slot 1 is the
active), `last_selected_move` at 182, `last_used_move` at 183.

`Pokemon` (24): `stats{hp,atk,def,spe,spc}` u16×5 at 0 (unmodified, computed),
`moves[4]{id u8, pp u8}` at 10, `hp` u16 at 18, `status` u8 at 20, `species`
u8 at 21, `types` u8 at 22 (two 4-bit fields, type1 low nibble), `level` u8
at 23.

`ActivePokemon` (32): `stats` (modified) at 0, `species` at 10, `types` at 11,
`boosts` u32 at 12 (i4 fields at bit offsets atk 0, def 4, spe 8, spc 12,
accuracy 16, evasion 20), `volatiles` u64 at 16, `moves[4]` at 24 (the LIVE
move slots and PP; Transform rewrites these).

`Volatiles` u64, bit offsets: Bide 0, Thrashing 1, MultiHit 2, Flinch 3,
Charging 4, **Binding 5 (set on the USER of Wrap/Bind/Clamp/Fire Spin)**,
Invulnerable 6, Confusion 7, Mist 8, FocusEnergy 9, Substitute 10, Recharging
11, Rage 12, LeechSeed 13, Toxic 14, LightScreen 15, Reflect 16, Transform 17;
then `confusion` u3 @18 (turns left), `attacks` u3 @21, `state` u16 @24 (Bide
damage / overwritten accuracy), `substitute` u8 @40 (sub HP), `transform` u4
@48, `disable_duration` u4 @52, `disable_move` u3 @56, `toxic` u5 @59 (turns
of toxic damage so far).

`status` byte (cartridge encoding, `data.zig::Status`): bits 0–2 sleep turns
REMAINING (asleep iff `status & 7 != 0`); bit 3 PSN; bit 4 BRN; bit 5 FRZ;
bit 6 PAR; bit 7 EXT = self-inflicted-sleep marker (Rest; needed for Sleep
Clause) or, together with PSN, the badly-poisoned marker (`TOX = 0x88`).

Enumerations: `Species` 0 = None, 1..151 in National Dex order (`Bulbasaur`
= 1 … `Mew` = 151); `Move` 0 = None, 1..165 in Gen 1 index order (`Pound` = 1
… `Struggle` = 165); `Type` u4 in cartridge order (Normal, Fighting, Flying,
Poison, Ground, Rock, Bug, Ghost, Fire, Water, Grass, Electric, Psychic, Ice,
Dragon). The encoder's ids (`_species_id` = dex num 1..151, `_move_id` = num
1..165) are therefore the engine's enum values by construction — **verified,
not assumed, by a test that maps every name in `src/data/data.json` through
poke-env's dex** (§9 B-0).

### 3.4 Update and request semantics (`src/lib/gen1/mechanics.zig::update/choices`)

- `update(c1, c2)` applies both players' choices *simultaneously* and returns
  the next request kind per player. One PS "turn" can take several updates: a
  faint mid-turn returns early with `(Switch, Pass)`, `(Pass, Switch)` or
  `(Switch, Switch)` (double KO, Explosion); after the replacement(s) switch in,
  the next update resumes. Turn 0 requires `(Pass, Pass)`.
- `choices(player, request)` in showdown mode:
  - `Pass` → `[PASS]` (the other side is choosing; nothing to decide).
  - `Switch` → every alive, non-active party slot as `SWITCH slot` (slots 2..6
    in *current order*), or `[PASS]` if none.
  - `Move` → if `isForced(active)` (**Recharging, Rage, Thrashing, Charging**)
    → exactly one choice, `MOVE data=1`, no switches (PS: hard lock,
    `trapped: true`). Otherwise: all alive non-active switch slots, then — if
    `limited` (**Bide or Binding on the user**) — the single locked move slot
    (or `MOVE 0` = Struggle when Bide has no PP / is disabled); else every move
    slot with `pp > 0` and not disabled; if none, `MOVE 0` (Struggle).
  - **Sleeping / frozen / Wrap-victim mons get the normal move list** in
    showdown mode; PS instead shows a single `Fight` placeholder (§7.2 maps it).
  - `choices` always returns ≥ 1 in showdown mode (the Transform + Mirror
    Move/Metronome + Disable softlock is cartridge-only).
- Result kinds are from **P1's** perspective. `Error` cannot happen in showdown
  mode except `turn >= 65535`, which the 1000-turn tie precludes.
- Terminal rules in showdown mode: last mon of a side faints → Win/Lose (both
  → Tie); `checkEBC` (Endless Battle Clause, no-progress detection) → Tie;
  `turn >= 1000` → Tie.

### 3.5 RNG (`src/lib/common/rng.zig`)

Showdown mode uses PS's Gen V/VI 64-bit LCG with 32-bit output (`PSRNG`),
seeded by a u64 written at byte 376; the engine's `helpers` derive one from a
parent PSRNG via `newSeed()`, but any u64 is a valid seed. Bounded draws use
PS's biased multiply-shift (`range`), which is why the engine can replay a
patched-PS battle exactly. For this project the seed only needs to be
*reproducible*: per battle, a `splitmix64` hash of the lane seed and the
battle counter (§7.5). Note the engine's `advance` option (default on) reproduces PS's
spurious RNG advances; leave it.

### 3.6 Performance envelope

10,000 Challenge-Cup RBY battles in 195 ms on one core of an AMD EPYC 7B12
(~20 µs per battle, ~0.3 µs per update at ~60 updates per battle); randbats
sets are "2-3× faster" than the benchmark's sets (docs/TESTING.md). Engine cost
is therefore negligible against a torch forward pass (19 µs at B=1 for the
[512,512] MLP alone). The Battle is a 384-byte POD: cloning is a `memcpy`,
which is the property the search line (JOURNEY 11.5) would want.

---

## 4. Prerequisites and build configuration

### 4.1 Toolchain

| need | how | pinned where |
|---|---|---|
| Zig 0.16.0 | `pip install ziglang==0.16.0` into `pokemon-showdown-rl` (the wheel ships the compiler; invoke as `python -m ziglang build …`). `PKMN_ZIG` env var overrides with a system binary for debugging | `pyproject.toml` optional group `engine` (see §4.5) |
| Rust ≥ 1.97 | already installed via rustup (`~/.cargo/bin`) | `rust-version` in `Cargo.toml` |
| maturin 1.15.0 | `pip install maturin==1.15.0` | same optional group |
| libclang | ONLY if regenerating bindings (`--features regen-bindings`); on macOS the Xcode Command Line Tools provide it (`LIBCLANG_PATH` if bindgen cannot find it). Normal builds use the committed `src/ffi_generated.rs` | — |
| Node 25 + built `showdown/dist` | only to generate the team bank (§6.2); `node pokemon-showdown start` builds `dist/` and it exists today | the vendored PS commit |

No `cc` crate: nothing C is compiled by cargo. Zig builds the static library;
Rust only links it. (`cc` would be needed only if a C shim were introduced, and
§5 shows none is.)

### 4.2 Crate layout (proposed; names follow the repo's `rl/envs/*` and `scripts/*` habits)

```
engine/pkmn_gen1/                 # NEW top-level dir; one crate, one Python extension
  Cargo.toml
  build.rs                        # zig build → link; bindgen only under `regen-bindings`
  pyproject.toml                  # maturin backend, pins
  vendor/pkmn-engine/             # git submodule at 9b88fd6c… (or a build-time tarball fetch verified by sha256)
  src/lib.rs                      # crate root; pub mod list; PyO3 module in python.rs
  src/ffi.rs                      # `include!("ffi_generated.rs")` + the few hand-checked consts (sizes) + PKMN_OPTIONS assert helper
  src/ffi_generated.rs            # COMMITTED bindgen output (regenerated on demand)
  src/battle.rs                   # Battle, Choice, Result, Player, Request; update/choices; clone; seed
  src/layout.rs                   # typed read-only views over the 384 bytes; offsets asserted against layout.json at test time
  src/team.rs                     # PokemonSet, TeamBank (load/sample), stat calc (PS formula), Pokemon/Side bytes
  src/observe.rs                  # per-seat observable tracker (revealed mons/moves, elapsed sleep turns, HP%), diff-driven
  src/tables.rs                   # StaticTables struct (species/moves/type-chart/prior) received from Python
  src/encoder.rs                  # the 828-dim encoder, block by block, reading tracker + tables only
  src/env.rs                      # Gen1Env (one battle, two seats) and BatchEnv (K battles): reset/step/pending/finished
  src/python.rs                   # PyO3 classes: BatchEnv, TeamBank, build_info(); numpy views
  tests/                          # Rust unit tests (layout, choice bits, stat vectors, mask derivation)
rl/envs/engine_tables.py          # builds StaticTables from poke-env (+ the repo's own _effect_block / conditional_move_probs)
rl/envs/engine_collector.py       # EngineCollector: the train.py seam (same surface as AsyncCollector)
rl/envs/engine_env.py             # thin single-battle gym.Env over BatchEnv(k=1) for evaluate()/tests
scripts/engine_team_bank.py       # Node oracle → data/engine/teams_<pscommit>_<seed>.bin (gitignored; script tracked)
scripts/engine_parity.py          # P-1..P-4 tape parity, D-1 dynamics smoke, T-1 throughput (each a subcommand)
requirements-engine.txt           # the exact install + verify commands (the poke-engine precedent)
tests/test_engine_*.py            # Python-side tests (see §9)
```

### 4.3 `Cargo.toml`

```toml
[package]
name = "pkmn-gen1"
version = "0.1.0"
edition = "2024"
rust-version = "1.97"
description = "Safe Rust + PyO3 wrapper over pkmn/engine's libpkmn-showdown (Gen 1) for pokemon-showdown-rl"
license = "MIT"           # the crate; pkmn/engine itself is MIT (vendor/pkmn-engine/LICENSE)

[lib]
name = "pkmn_gen1"
crate-type = ["cdylib", "rlib"]   # cdylib = the Python extension; rlib = Rust tests/benches

[dependencies]
pyo3  = { version = "=0.29.2", features = ["extension-module"] }
numpy = "=0.29.0"

[build-dependencies]
bindgen = { version = "=0.72.1", optional = true }

[features]
default = []
regen-bindings = ["dep:bindgen"]   # needs libclang; rewrites src/ffi_generated.rs
debug-log      = []                # builds the engine with -Dlog=true (§10 replay export); NOT for training

[profile.release]
lto = "fat"
codegen-units = 1
```

### 4.4 `build.rs` — compile the engine with Zig, link it, (re)generate bindings

```rust
use std::{env, path::PathBuf, process::Command};

fn zig_cmd() -> Vec<String> {
    // 1) PKMN_ZIG=/path/to/zig   2) the pinned pip wheel   3) `zig` on PATH
    if let Ok(z) = env::var("PKMN_ZIG") { return vec![z]; }
    let py = env::var("PYTHON").unwrap_or_else(|_| "python".into());
    if Command::new(&py).args(["-m", "ziglang", "version"]).output().map(|o| o.status.success()).unwrap_or(false) {
        return vec![py, "-m".into(), "ziglang".into()];
    }
    vec!["zig".into()]
}

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(env::var("OUT_DIR").unwrap());
    let vendor = manifest.join("vendor/pkmn-engine");
    let prefix = out.join("pkmn");
    let log = if cfg!(feature = "debug-log") { "true" } else { "false" };

    let zig = zig_cmd();
    let status = Command::new(&zig[0]).args(&zig[1..])
        .arg("build")
        .arg(format!("-Dlog={log}"))
        .args(["-Dshowdown=true", "-Dchance=false", "-Dcalc=false",
               "-Doptimize=ReleaseFast", "-Dpic=true", "-Dstrip=true"])
        .arg("--prefix").arg(&prefix)
        .arg("--cache-dir").arg(out.join("zig-cache"))            // keep the vendored tree pristine
        .arg("--global-cache-dir").arg(out.join("zig-global-cache"))
        .current_dir(&vendor)
        .status().expect("zig not runnable — see docs/PKMN_ENGINE_RUST_PLAN.md §4.1");
    assert!(status.success(), "zig build of pkmn/engine failed");

    println!("cargo:rustc-link-search=native={}", prefix.join("lib").display());
    println!("cargo:rustc-link-lib=static=pkmn-showdown");
    println!("cargo:rerun-if-changed=vendor/pkmn-engine/src");
    println!("cargo:rerun-if-changed=vendor/pkmn-engine/build.zig");
    println!("cargo:rerun-if-env-changed=PKMN_ZIG");

    #[cfg(feature = "regen-bindings")]
    {
        bindgen::Builder::default()
            .header(prefix.join("include/pkmn.h").to_string_lossy().into_owned())
            .allowlist_function("pkmn_.*")
            .allowlist_type("pkmn_.*")
            .allowlist_var("PKMN_.*")
            .prepend_enum_name(false)                // PKMN_CHOICE_MOVE, not pkmn_choice_kind_PKMN_CHOICE_MOVE
            .default_enum_style(bindgen::EnumVariation::Consts)   // the enums are packed u8 typedefs in C
            .layout_tests(true)                      // size/align asserts for pkmn_gen1_battle et al.
            .generate().expect("bindgen")
            .write_to_file(manifest.join("src/ffi_generated.rs")).expect("write bindings");
    }
}
```

Notes the implementer will hit:

- **Why commit the bindings.** `pkmn.h` is ~200 lines and changes rarely;
  requiring libclang for every `pip install -e` is the kind of environment
  dependency this repo has paid for before. The committed file plus bindgen's
  own `layout_tests` (compile-time `size_of` asserts) keeps it honest, and the
  `regen-bindings` feature regenerates it when the pin moves.
- `PKMN_OPAQUE(n)` becomes `#[repr(C)] struct pkmn_gen1_battle { bytes: [u8; 384] }`;
  `float64_t` becomes `f64`; the packed enums become `u8` consts under
  `EnumVariation::Consts`, which is why the wrapper (§5.2) defines its own
  `#[repr(u8)]` Rust enums and converts at the boundary.
- **Alignment.** The engine's `Battle` is an `extern struct` with u16/u64
  fields; give the Rust wrapper `#[repr(C, align(8))]` so a stack- or
  Vec-allocated battle is aligned for the u64 seed at 376.
- The static library may reference libc symbols (`memcpy`, `memset`); macOS
  links libSystem implicitly, Linux needs `cargo:rustc-link-lib=c` if the
  linker complains. `-Dpic=true` is required for the cdylib link on both.
- macOS deployment-target warnings (the engine's C example sets
  `-mmacosx-version-min`) are cosmetic.

### 4.5 Python packaging, install and verification (the `poke-engine` precedent)

`engine/pkmn_gen1/pyproject.toml`:

```toml
[build-system]
requires = ["maturin==1.15.0"]
build-backend = "maturin"

[project]
name = "pkmn-gen1"
version = "0.1.0"
requires-python = "==3.13.*"
dependencies = ["numpy==2.5.1"]

[tool.maturin]
module-name = "pkmn_gen1"
features = ["pyo3/extension-module"]
```

`requirements-engine.txt` (mirrors `requirements-search.txt`; OUTSIDE
`pyproject.toml` for the same reason — a source build with toolchain
prerequisites, not a wheel):

```
# Engine-collector extra dependency. Install with EXACTLY these commands,
# in the pokemon-showdown-rl conda env (never base):
#   pip install ziglang==0.16.0 maturin==1.15.0
#   git submodule update --init engine/pkmn_gen1/vendor/pkmn-engine
#   pip install --no-build-isolation -e engine/pkmn_gen1
# Verify EVERY time (the FG-5 habit): python -c "import pkmn_gen1; pkmn_gen1.verify()"
# prints and asserts: engine_sha == 9b88fd6c…, PKMN_OPTIONS == {showdown: true, log: false,
# chance: false, calc: false}, battle_size == 384, zig == 0.16.0.
```

`pkmn_gen1.build_info()` returns that dict (engine sha read from the submodule
at build time and baked in with `env!`; zig version captured by `build.rs`;
`PKMN_OPTIONS` read at import). `rl/train.py::_write_run_metadata` stamps it
next to `ENCODER_FINGERPRINT`, together with the team-bank sha256 and the
static-tables fingerprint (§7.4), so a run records exactly which engine and
which data produced its transitions.

README obligation ("name anything borrowed"): add pkmn/engine (MIT, pkmn
contributors, commit) to the *Notable external components* paragraph, and a
one-line provenance comment at the top of `engine/pkmn_gen1/src/lib.rs`,
`rl/envs/engine_tables.py` and `scripts/engine_team_bank.py`.

---

## 5. FFI and the safe wrapper (`src/battle.rs`, `src/layout.rs`, `src/team.rs`)

### 5.1 Raw layer (`src/ffi.rs`)

Only `battle.rs` touches `ffi::*`. Everything above it sees Rust types. The
raw layer adds three things to the generated file: `const BATTLE_SIZE: usize =
384` cross-checked against `PKMN_GEN1_BATTLE_SIZE`, a `verify_options()` that
reads `PKMN_OPTIONS` at runtime and returns an error unless `showdown && !log
&& !chance && !calc` (or `log` under `debug-log`), and `const CHOICES_CAP:
usize = 16` asserted `>= PKMN_GEN1_CHOICES_SIZE` at test time.

### 5.2 Types

```rust
#[derive(Clone, Copy, PartialEq, Eq, Debug)] #[repr(u8)]
pub enum Player { P1 = 0, P2 = 1 }
impl Player { pub fn foe(self) -> Player { match self { P1 => P2, P2 => P1 } } }

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Choice { Pass, Move(u8) /* 0 = Struggle/forced, 1..4 = slot */, Switch(u8) /* 2..6, CURRENT order */ }
impl Choice {
    pub fn raw(self) -> u8 { match self { Pass => 0, Move(d) => 1 | (d << 2), Switch(d) => 2 | (d << 2) } }
    pub fn from_raw(b: u8) -> Choice { match b & 3 { 0 => Pass, 1 => Move(b >> 2), 2 => Switch(b >> 2), _ => unreachable!() } }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)] pub enum Request { Pass, Move, Switch }
#[derive(Clone, Copy, PartialEq, Eq, Debug)] pub enum Outcome { None, Win, Lose, Tie, Error }   // from P1's view
#[derive(Clone, Copy, Debug)] pub struct Result { pub outcome: Outcome, pub p1: Request, pub p2: Request }
impl Result { pub fn from_raw(b: u8) -> Result { /* bits 0-3, 4-5, 6-7 */ } }

pub struct Choices { buf: [u8; 16], n: u8 }   // iterator over Choice; never heap-allocates

#[repr(C, align(8))]
#[derive(Clone)]
pub struct Battle(pub [u8; 384]);
```

### 5.3 The `Battle` API

```rust
impl Battle {
    /// Fresh battle: turn 0, actives zeroed, `order[i] = i+1`, u64 seed at byte 376 (showdown layout).
    pub fn new(seed: u64, p1: &[PokemonBytes], p2: &[PokemonBytes]) -> Battle;
    pub fn seed(&self) -> u64;                    // read-only after construction
    pub fn turn(&self) -> u16;
    pub fn side(&self, p: Player) -> SideView<'_>; // typed, read-only, offset-based (§5.4)

    /// Legal choices for `p` given the request kind the previous update returned.
    pub fn choices(&self, p: Player, req: Request) -> Choices;

    /// Applies both choices. `debug_assert!`s legality against `choices()`; the
    /// Python-facing env asserts ALWAYS (a violated contract is UB in the engine).
    pub fn update(&mut self, c1: Choice, c2: Choice) -> Result;

    pub fn clone_into(&self, dst: &mut Battle) { dst.0.copy_from_slice(&self.0) }   // search: memcpy
    pub fn as_bytes(&self) -> &[u8; 384];         // serialisation / hashing / debugging
}
```

`update` is the only `unsafe` block in the crate besides `choices`:

```rust
pub fn update(&mut self, c1: Choice, c2: Choice) -> Result {
    debug_assert!(self.is_legal(Player::P1, c1) && self.is_legal(Player::P2, c2));
    let raw = unsafe { ffi::pkmn_gen1_battle_update(self.0.as_mut_ptr().cast(), c1.raw(), c2.raw(), std::ptr::null_mut()) };
    Result::from_raw(raw)
}
```

Safety argument, in the words the reviewer will want: the battle is a plain
byte array owned by Rust; the C functions read/write only inside it; the only
precondition the engine imposes is choice legality, which the wrapper checks
against the engine's own `choices()` output; the library keeps no global
mutable state (Zig `export fn`s over `const` data — confirm at B-0 by grepping
`src/lib/bindings/c.zig` for `var`), so distinct `Battle`s may be updated from
different threads (`unsafe impl Send for Battle`; no `Sync` needed).

`Battle` implements `Clone` (384-byte copy) and `Hash`/`Eq` over the bytes — the
cheap state snapshot that the current server path cannot provide and that
JOURNEY 11.5's depth-2 search would consume.

### 5.4 Typed views (`src/layout.rs`)

Read-only accessors computed from the offsets in §3.3, written once as
constants and pinned by a test that parses `vendor/pkmn-engine/src/data/layout.json`
and asserts every constant (plus the two showdown-mode overrides: `last_moves`
width 4, `rng` at 376). Sketch:

```rust
pub struct SideView<'a>(&'a [u8]);          // 184 bytes
pub struct PokemonView<'a>(&'a [u8]);       // 24 bytes
pub struct ActiveView<'a>(&'a [u8]);        // 32 bytes

impl<'a> SideView<'a> {
    pub fn party(&self, i: usize) -> PokemonView<'a>   // ORIGINAL order, 0..6
    pub fn active(&self) -> ActiveView<'a>
    pub fn order(&self) -> [u8; 6]                     // order[slot-1] = party index + 1; 0 = empty slot
    pub fn active_party_index(&self) -> usize { self.order()[0] as usize - 1 }
    pub fn slot_of_party_index(&self, i: usize) -> Option<u8>   // inverse of order(): 1..6
    pub fn last_selected_move(&self) -> u8
    pub fn last_used_move(&self) -> u8
}
impl<'a> PokemonView<'a> {
    pub fn stats(&self) -> Stats { /* u16 LE at 0,2,4,6,8: hp atk def spe spc */ }
    pub fn moves(&self) -> [(u8, u8); 4]   // (move id, pp)
    pub fn hp(&self) -> u16                // current
    pub fn status(&self) -> StatusByte     // .asleep(), .sleep_turns_left(), .psn(), .brn(), .frz(), .par(), .tox(), .self_inflicted()
    pub fn species(&self) -> u8; pub fn types(&self) -> (u8, u8); pub fn level(&self) -> u8
}
impl<'a> ActiveView<'a> {
    pub fn stats(&self) -> Stats; pub fn species(&self) -> u8; pub fn types(&self) -> (u8, u8);
    pub fn boosts(&self) -> Boosts         // six i8 from the packed i4 fields (sign-extend)
    pub fn volatiles(&self) -> Volatiles   // u64 → bool flags + the small counters
    pub fn moves(&self) -> [(u8, u8); 4]   // LIVE slots (Transform-aware)
}
```

Every field is read from the byte slice with explicit little-endian decoding
(`u16::from_le_bytes`); the crate refuses to compile on big-endian targets
(`#[cfg(target_endian = "big")] compile_error!`), which matches the engine's
"native endianness" contract on the only hosts this project runs on.

### 5.5 Constructing battles (a port of `helpers.zig`, plus PS's stat rule)

The C API has no constructor. `Battle::new` writes the bytes the Zig helper
would: for each party slot, a `Pokemon` record; `order[i] = i+1`; everything
else zero; the seed at 376. A `PokemonBytes` is produced from a `PokemonSet`
(what the team bank stores):

```rust
pub struct PokemonSet { pub species: u8, pub level: u8, pub moves: [u8; 4] /* 0-padded, in PS's shuffled order */,
                        pub ivs: [u8; 5] /* hp atk def spa spe, even 0..30 as PS stores them */,
                        pub evs: [u8; 5] /* 0..255 */ }
```

Stats use **Showdown's** gen 1 formula (`sim/battle.ts::statModify`, which is
what the request's `stats` field reports and what the tapes let us verify):

```
hp    = floor( floor(2*base + iv + floor(ev/4) + 100) * level / 100 + 10 )
other = floor( floor(2*base + iv + floor(ev/4))       * level / 100 + 5  )
```

PS represents DVs as even IVs (`ivs &= 30`); `spd` mirrors `spa`; the engine
stores one `spc`. The engine's own `Stats.calc(base, dv, exp, level)` is the
same arithmetic in cartridge terms (`2*(base+dv) + min(255, ceil(sqrt(exp)))/4`),
so both agree for every randbats set — and P-4 (§9) checks our numbers against
`|request|` stats on the tapes rather than trusting either derivation.

Max PP: PS `calculatePP` with 3 PP Ups is `pp * 8/5`, minus 3 for 40-PP moves
(→ 61); the engine's helper uses `min(pp/5*8, 61)` — identical for every gen 1
move. Base PP comes from `src/data/data.json` (`moves`), which is the engine's
table and matches poke-env's `Move.max_pp` (assert once in the tables test).

Base stats and types for the `Pokemon` record come from the engine's own data
(`data.json` species), NOT from poke-env — the engine must simulate with its
own numbers. poke-env's tables are used only for the *observation* (§7.4); the
two sources are asserted equal at B-0 (gen 1 base stats are not in dispute).

### 5.6 Two wrapper-level guards worth their lines

- `is_legal(p, c)` is O(9) over the last `choices()` result cached per seat
  after each update; the Python env calls it unconditionally, so a masking bug
  surfaces as a Rust `Err`, never as engine UB (the current async path has the
  same "strict raise, count, die" stance: `CollectPlayer.choose_move`).
- `update` returning `Outcome::Error` is a hard error in showdown mode
  (§3.4) — raise, do not "recover", and include the battle bytes in the message
  so it can be replayed with the `debug-log` build.

---

## 6. Random Battle team generation

### 6.1 What Showdown does (`showdown/data/random-battles/gen1/teams.ts`, vendored `59da482e`)

- `randomTeam()`: sample species without replacement from the 146 entries of
  `data.json`; skip a second Ditto per BATTLE (`battleHasDitto` lives on the
  generator that produces both teams); at most 2 mons sharing a type; at most 2
  mons weak to each "spammable" type (Electric, Psychic, Water, Ice, Ground,
  Fire; weakness = not immune and effectiveness > 0); at most 1 level-100 mon;
  rejected-but-valid species refill the team if the pool runs dry; always 6.
- `randomSet(species)`: `comboMoves` all-or-none on a 50% flip; ONE
  `exclusiveMoves` pick; `essentialMoves` in order up to 4; fill from `moves`
  by `sampleNoReplace`; **the final move order is shuffled** (per-battle random
  slot permutation — the reason the encoder is slot-symmetric); `level` from
  `data.json` (default 80); EVs 255 everywhere; IVs 30 everywhere; if the set
  has `substitute`, lower `evs.hp` in steps of 4 while max HP is divisible by 4;
  if the set has no physical attacking move (and no Mimic/Transform):
  `evs.atk = 0`, `ivs.atk = 2` ("minimize confusion damage").
- The exact per-species marginals of this procedure are what
  `rl/envs/randbats_prior.py::_sample_set` already reproduces step for step
  (and `conditional_move_probs` conditions on).

### 6.2 Phase 1 (recommended): a bank generated by Showdown itself

Exactness by construction, zero porting risk: `showdown/dist/sim` is built and
exposes `Teams.generate('gen1randombattle', {seed})` (`sim/teams.ts:651`).
`scripts/engine_team_bank.py` runs a Node one-liner as a subprocess, streams N
teams as compact JSON lines, and writes `data/engine/teams_<pscommit>_<seed>_<N>.bin`:
48 bytes per team (6 × `PokemonSet` packed: species, level, 4 moves, atk-IV
flag, hp-EV/4) plus a header with the PS commit, generator seed, N and a
sha256. Sizes: 1M teams = 48 MB; a 100M-step lane plays ~3.1M battles × 2
teams, so a 2M-team bank is reused ~3× per lane — team draw is a nuisance term
already averaged over millions of battles, and the bank is resampled *with* a
per-battle seed, so no two lanes see the same pairing sequence.

Pairing rule at battle start: draw two teams; **re-draw the second if both
contain Ditto** (the one cross-team constraint the shared generator enforces).

The bank is gitignored (`data/` already is); the generator script, the PS
commit and the bank sha256 are tracked and stamped into run metadata.

### 6.3 Phase 2 (optional): a Rust port of the generator

Only worth it if the bank's reuse or its startup cost ever shows up in a
measurement. Validation if it is built: generate 200k teams both ways and
compare species marginals, per-species set marginals (against
`conditional_move_probs`), level histogram, and assert the four team-level
constraints are never violated; a χ² on species counts at n=200k has power to
see a 1% relative shift. PS's PRNG (sodium/ChaCha20 or the gen 5 LCG) is not
worth replicating; distributional equality is the bar.

### 6.4 From a set to engine bytes

`team.rs::PokemonBytes::from_set(set, &engine_species_table)`: stats by §5.5,
`hp = stats.hp`, `status = 0`, `types` from the engine table, `moves[i] = (id,
maxpp)`, `level`. No PP Ups bits are stored (gen 1 tracks PP as a full byte in
the engine). Species/move ids in the bank are the engine enum values, mapped
once from PS ids at bank-generation time (the name-map test in §9 B-0 covers
this direction too).

---

## 7. `Gen1Env`: observation, mask, step

### 7.1 Invariant I1 — the observable-state tracker (`src/observe.rs`)

poke-env builds its `Battle` from the protocol stream and the `|request|`
JSON. Some of what the engine holds is **hidden information** on Showdown, and
an observation that reads it would train a policy on a different game than the
one it is evaluated and laddered on. The tracker is the projection from engine
state to "what this seat's client would know", maintained per seat, updated by
diffing the 384 bytes before and after every update (`-Dlog` stays off).

| quantity | engine source | visible on PS to this seat? | tracker rule |
|---|---|---|---|
| own party (species, level, stats, moves, PP, HP exact, status) | `side.party(i)` | yes (`|request|`) | read from state |
| own active boosts, volatiles, live move slots/PP | `side.active()` | yes | read from state |
| opponent's active species, level, status, boosts, visible volatiles (Confusion, Substitute presence, Reflect, LightScreen, FocusEnergy, LeechSeed, Recharging, Charging, Bide, Thrashing, Toxic counter, Transform) | `foe.active()` | yes (protocol messages) | read from state, but ONLY for mons already revealed |
| opponent's HP | `foe.party(j).hp / stats.hp` | **percentage only** (`getHealth`: `ceil(100*hp/max)`, and 99 if that rounds a non-full mon to 100; `0 fnt` when fainted) | quantise with exactly that rule; `current_hp_fraction = pct/100` |
| opponent's PP | `foe.active().moves` | **no** (poke-env never decrements the opponent's PP) | never read; opponent PP feature = 1.0 |
| opponent's unrevealed party members | `foe.party(j)` | **no** until they switch in | `revealed: Vec<u8>` of party indices in reveal order; a slot is revealed when `foe.order()[0]` starts pointing at it (diff) |
| opponent's unrevealed moves | `foe.party(j).moves` | **no** until used | `revealed_moves[j]: Vec<u8>` in usage order; a move is revealed when its LIVE slot's PP decrements across an update (§7.1.1) |
| sleep turns REMAINING | `status & 7` | **no** (PS shows only `|cant|…|slp` events) | keep `sleep_turns_observed` per mon: +1 whenever the remaining count decrements across an update; reset to 0 when the status byte changes into or out of sleep. This is poke-env's `status_counter` for SLP |
| toxic turns so far | `volatiles.toxic` | yes (one `|-damage|…|[from] psn` per turn) | read from state (matches poke-env's TOX `status_counter`; confirm at P-1 against `pokemon.py:415/483`) |
| confusion turns remaining, Disable duration/slot, Bide damage, attacks left, Substitute HP, Transform target | volatile counters | **no** | never read (the encoder has no slot for any of them anyway) |
| `last_damage`, RNG seed, `last_selected_move` | battle header | no | never read |
| Wrap victim's "maybe still trapped" | — | PS shows the `Fight` placeholder only on the first trapped turn (`partiallytrapped.maybeLocked`); later turns show the normal list | `binding_turns_observed` per victim: +1 per update while `foe.active().volatiles.binding` holds; reset when it clears (§7.2) |

Own-side rows use exact values (the request gives them); opponent rows use
the quantised/revealed projection. Both seats run the same code with the
roles swapped, so the pool member's observation is built by the same rule.

#### 7.1.1 Reveal-by-diff, and the two families it cannot see

Move reveal by PP decrement is correct for `|cant|` turns (no PP spent, no
reveal), for locked continuation turns (already revealed), for Struggle (no
slot, no reveal) and after Transform (the copied moves live in the active's
slots with 5 PP and reveal as they are used). Two Showdown behaviours are
invisible to a diff and are declared **non-parity families**, counted at P-1
rather than emulated: (a) Metronome / Mirror Move — PS logs the called move
with `[from]`, and poke-env may add it to the user's known moves; (b) Struggle
— poke-env may add `struggle` to the opponent's move dict, occupying a
revealed slot. Both are rare in gen 1 randbats (Metronome appears in a handful
of sets; Struggle needs four exhausted moves). If P-1 shows either family
above its budget, the fallback is the `debug-log` build's protocol stream
(§10), decoded for `|move|` only.

### 7.2 Invariant I2 — the 10-way action space and the mask

poke-env's mapping (`singles_env.py:77-130, 233-280`), which every checkpoint
was trained against:

- **actions 0–5 = switch to `list(battle.team.values())[i]`.** The team dict is
  filled from the FIRST `|request|` in its `side.pokemon` order and never
  reordered (`abstract_battle.py:1279-1320` inserts unknown idents, Python dicts
  keep insertion order). That first order is the generated team order, i.e.
  the engine's **original party order `side.party(i)`** — not the live
  `order[]`. So action i ↔ party index i for the whole battle. To submit:
  `Choice::Switch(side.slot_of_party_index(i))`. Legal iff the engine's choice
  list contains that switch (alive, not active, switching allowed).
- **actions 6–9 = move `list(active.moves.values())[:4][j]`.** The per-mon
  move dict is filled from the request's move list in stored order and only
  grows (`pokemon.py:738`), so j ↔ stored slot j, and `[:4]` drops anything a
  Transform/Mimic appended later. Submit `Choice::Move(j+1)`.
- The mask is `get_action_mask`: switch actions from `available_switches`
  (empty when `trapped`), move actions whose id is in `available_moves`, plus
  the single-`SPECIAL_MOVES` alias rule.

The engine's `choices()` gives the same legality with different naming, and
the request JSON's quirks must be reproduced from state. The mapping table:

| situation (this seat) | engine `choices()` | PS request | mask (actions) | submit | `vec[3] force_switch` | `vec[4] trapped` | `vec[5] aliased` |
|---|---|---|---|---|---|---|---|
| normal move turn | switches + moves with PP, not disabled | full list | switches ∪ {6+j : Move(j+1) offered} | direct | 0 | 0 | 0 |
| forced switch after a faint (`Request::Switch`) | switches only | `forceSwitch` | switches | direct | 1 | 0 | 0 |
| other side replacing (`Request::Pass`) | `[PASS]` | `wait: true` | — (no learner row; env submits Pass) | Pass | — | — | — |
| Struggle (no PP anywhere) | switches + `Move(0)` | `[Struggle]` | switches ∪ {6} | `Move(0)` | 0 | 0 | 1 |
| Hyper Beam recharge (`Recharging`) | `Move(1)` only | `[Recharge]`, `trapped` (base `mustrecharge.onLockMove`, inherited by the gen 1 mod) | {6} | `Move(1)` | 0 | 1 | 1 |
| Thrash/Petal Dance (`Thrashing`), two-turn charge (`Charging`), Rage | `Move(1)` only (forced) | `[<the move>]`, `trapped` (`lockedmove`/`twoturnmove`/`rage` all carry `onLockMove` in the gen 1 mod) | {6+slot(last_selected_move)} — the id IS a real move, so poke-env does not alias | `Move(1)` | 0 | 1 | 0 |
| Wrap/Bind/Clamp/Fire Spin USER continuing (`Binding`), and Bide (user) | switches + the locked slot (`limited`) | `[<the move>]`, switching allowed (`partialtrappinglock` and gen 1 `bide` use `onSemiLockMove`, not `onLockMove`) | switches ∪ {6+slot} | direct | 0 | 0 | 0 |
| asleep / frozen | full list (engine accepts any) | `[Fight]` placeholder, switching allowed | switches ∪ {6} | the FIRST Move choice the engine lists | 0 | 0 | 1 |
| Wrap VICTIM, first trapped turn (`binding_turns_observed == 1`) | full list | `[Fight]` placeholder (`partiallytrapped` without `maybeLocked`) | switches ∪ {6} | first Move choice | 0 | 0 | 1 |
| Wrap VICTIM, later turns (`maybeLocked`) and the two `fakepartiallytrapped` turns after it ends | full list | full list | normal | direct | 0 | 0 | 0 |
| after Transform (Ditto) | live slots = copied moves | request lists copied moves; poke-env's `[:4]` still names the ORIGINAL dict entries | **non-parity family**: the engine env exposes the live slots (correct game); current poke-env behaviour is an accepted defect. Counted at P-2 | direct | 0 | 0 | 0 |

`trapped` = the request's `trapped: true` = a hard lock = exactly the engine's `isForced` set (Recharging, Thrashing, Charging, Rage); Bide and Wrap-user turns are semi-locks and allow switching in both PS and the engine.
The encoder's own measurement that `battle.trapped` is False on 1,262 of 1,273
recharge/partial-trap turns is consistent with this table if most of those
turns were Wrap victims; **P-2 must confirm the split before this table is
trusted.** The aliased flag `vec[5]` and the zeroed move blocks follow poke-env
exactly: on an aliased turn the four own-move blocks and the four own-move ids
are zero (`embed_battle` / `_fill_ids`).

The "first Move choice" rule for sleep/freeze/Wrap-victim turns is the one
place the submitted choice is not what poke-env would have sent (poke-env
sends `/choose move fight`, which PS resolves against the locked placeholder).
It matters only if the mon acts that turn after all — a Fire move thawing a
slower frozen mon — and the engine then uses the selected slot as PS does.
Declared, counted, negligible.

### 7.3 The 828-dim encoder in Rust (`src/encoder.rs`), block by block

Layout (from `rl/envs/showdown.py:128-145`, `encoder_spec.py::GEN1`):

```
[0..6)     GLOBAL   turn/50 capped | own fainted/6 | opp fainted (revealed)/6 | force_switch | trapped | aliased
[6..204)   OWN MONS 6 × 33, party order       hp | fainted | is_active | status one-hot(6) | level/100 | base stats/255 (hp atk def spa spe)
                                              | types one-hot(15, ALPHABETICAL) | best mult mon→foe | best mult foe→mon | speed edge
[204..220) OWN ACTIVE 16                      boosts/6 (accuracy atk def evasion spa spd spe; spa==spd==spc) | volatiles(7) | status_counter/16 | preparing
[220..404) OWN MOVES 4 × 46, stored order     known | bp/100 | accuracy | pp/maxpp | mult vs foe | physical | status | priority/5 | type one-hot(15) | effect(23)
[404..608) OPP MONS 6 × (1 + 33), reveal order  revealed flag then the same 33 (hp = pct/100)
[608..624) OPP ACTIVE 16
[624..808) OPP MOVES 4 × 46, revealed-then-prior order   known = 1.0 for revealed, P(move | revealed) for prior fills
[808..828) IDS  own species(6, party order) | opp species(6, reveal order) | own move ids(4, zero on aliased turns) | opp move ids(4, the slot's move) — each id/256
```

Rules that are easy to get subtly wrong, each pinned by a P-1 assertion:

- Types one-hot order is the encoder's **alphabetical** list (Bug, Dragon,
  Electric, Fighting, Fire, Flying, Ghost, Grass, Ground, Ice, Normal, Poison,
  Psychic, Rock, Water); the engine's `Type` is cartridge order — a 15-entry
  permutation lives in `tables.rs`.
- `volatiles(7)` = (CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE,
  PARTIALLY_TRAPPED, REFLECT, SUBSTITUTE). MUST_RECHARGE ← `Recharging`;
  **PARTIALLY_TRAPPED is the VICTIM's flag ← the FOE active's `Binding` bit**;
  LightScreen has no slot (poke-env 0.15.0 cannot parse it) and must not be
  encoded anywhere.
- `status_counter/16`: SLP → `sleep_turns_observed`; TOX → `volatiles.toxic`;
  everything else 0 (confirm the poke-env increment sites at P-1).
- `preparing` ← `Charging`. `fainted` ← `hp == 0`. `is_active` ← party index
  == `order[0]-1`.
- Matchups: `_best_multiplier` = max over the attacker's types of
  `damage_multiplier(defender type1, type2)` using **poke-env's gen 1 type
  chart** (which carries PS's gen 1 chart, including its quirks); the move
  block's multiplier uses the move's type the same way. Foe = the opponent's
  ACTIVE for own blocks and our active for opponent blocks; `None` foe (should
  not happen after turn 1) leaves the slots 0.
- Speed edge (v2): `(a-d)/(a+d)` with `_spe_est` = base speed × level/100,
  boosted and ×0.25 under PAR for on-field mons — base speed, not the actual
  stat, for both sides.
- Opponent move slots: revealed moves first at `known = 1.0` in usage order,
  then prior fills ordered by probability descending with a STABLE sort over
  the prior's alphabetical id order (`conditional_move_probs` sorts with
  `-p` and Python's stable sort; the slot assignment depends on it), until 4.
  Opponent `pp/maxpp` is 1.0. Opponent ids in `[824..828)` name whatever fills
  the slot, revealed or prior.
- Own move `known = 1.0` for real slots; unused 4th slot (3-move sets) stays
  all-zero. `pp/maxpp` from the live slot and the max-PP table.
- All floats are `f32` computed in the same order as the Python code (division
  by the same constants), so P-1 can demand bitwise equality rather than a
  tolerance.

### 7.4 Static tables from Python (`rl/envs/engine_tables.py` → `tables.rs`)

The Rust encoder holds no game data of its own. At construction Python hands
it dense arrays built from poke-env, so the encoder's semantics stay pinned to
the single source the Python encoder reads:

| table | shape | built from |
|---|---|---|
| `species` | (152, 5 base stats /255 + 2 alphabetical type idx) | `GenData.from_gen(1).pokedex` by dex `num` |
| `moves_static` | (166, 30) = bp/100, accuracy, max_pp, physical, status, priority/5, type idx, effect[23] | `poke_env.battle.move.Move(id, gen=1)` + `rl.envs.showdown._effect_block` (imported, not copied) |
| `type_chart` | (15, 15) alphabetical | `GenData.from_format("gen1randombattle").type_chart` through `PokemonType.damage_multiplier` |
| `engine_species_names` / `engine_move_names` | (152,), (166,) | `vendor/pkmn-engine/src/data/data.json` — asserted to map onto poke-env's dex/movedex nums as the identity |
| `prior` | sparse map (species, revealed-candidate bitmask) → probs over that species' candidate list | `randbats_prior.conditional_move_probs` evaluated for every reachable subset (subsets of the sampled sets), so the values are the very numbers the Python encoder emits; unreachable subsets fall back to the unconditional row exactly as the Python function does |

The whole bundle is hashed (sha256 of the concatenated arrays) into a
`tables_fingerprint` that is stamped into run metadata and cached under
`data/engine/tables_<fingerprint>.npz`. `POKEMON_RL_NO_SET_PRIOR=1` flips a
flag that skips prior fills, matching the Python ablation switch.

### 7.5 Reward, termination, seats, seeds (`src/env.rs`)

- Reward is terminal only: `+1/−1/0` for the learner seat from `Outcome`
  (flip sign for P2). Ties (EBC, 1000 turns, double KO) score 0 — the async
  path's G4c rule. `Outcome::Error` raises.
- Episodes never truncate; every finish is a decided game, so `terminated`
  is always the flag (bit-for-bit the `ShowdownEnv.step` remap).
- **Seat.** The learner is P1 in every battle today (the challenger is p1 on
  the server). Default `learner_seat: p1` for parity; `alternate`/`random`
  are knobs for a later pre-reg, not for A-1.
- **Seeds.** `battle_seed = splitmix64(lane_seed * 0x9E3779B97F4A7C15 ^ battle_counter)`;
  the team pair is drawn from the bank with `splitmix64(battle_seed ^ 1)`.
  `battle_counter` is persisted in the checkpoint payload so a `--resume`
  continues the same sequence (the async path loses in-flight battles on
  resume and so does this one).
- **Wait pumping.** `step()` applies the submitted choices, then keeps
  updating any battle whose learner request is `Pass` (only the opponent
  decides) — asking the opponent seat for its choice through the same batched
  path — until every live battle has a learner decision pending or has ended.
  Finished slots are restarted immediately with fresh teams and seed.

### 7.6 `BatchEnv` — the Python-facing surface (`src/python.rs`)

```python
import pkmn_gen1
pkmn_gen1.verify()                                   # PKMN_OPTIONS / sha / sizes (import-time in the collector)
env = pkmn_gen1.BatchEnv(k=256, seed=lane_seed, tables=tables, bank=bank,
                         learner_seat="p1", set_prior=True)
env.reset()
while True:
    L = env.pending("learner")     # idx int32[n], obs f32[n,828], mask bool[n,10]  (zero-copy numpy views into Rust buffers)
    O = env.pending("opponent")    # idx int32[m], obs f32[m,828], mask bool[m,10], member int32[m]
    a_l, logp = agent.act_logp(L.obs, L.mask)
    a_o = move_members(O)          # grouped by member (§8.2)
    env.step(L.idx, a_l, logp, version, O.idx, a_o)   # asserts legality; pumps Pass turns; restarts finished slots
    for ep in env.drain_finished(): dataset.append(ep)  # dict with obs/masks/actions/rewards/old_logp/version[/opp_choice]
```

Per-slot episode buffers live in Rust (rows appended at each learner
decision; `logp`/`version` copied in from `step`), so a finished episode
comes out as a handful of numpy arrays rather than thousands of Python
objects. `env.set_member(idx, member_id)` records which pool member owns a
slot for the lifetime of its battle (the collector calls it on restart, after
`pool.select`). `env.stats()` returns the counters the collector logs.

Thread safety with torch: `step()` runs on the calling thread; nothing is
async. It releases the GIL for the engine/encoder loop (`py.allow_threads`)
so a future rayon split across slots is a local change.

---

## 8. Integration into training

### 8.1 `EngineCollector` — the seam `rl/train.py` already has

`_async_loop` drives a collector through a small surface: `seam.version`,
`seam.requests`, `seam.inference_seconds`, `start(n_battles)`, `poll()`,
`check()`, `pause()`, `resume(version)`, `run_in_loop(fn, *args)`, `stats()`,
`close()`, plus the pool hooks (`report_outcome`, `seed_rng`,
`record_choices`/`take_choices`). `rl/envs/engine_collector.py::EngineCollector`
implements exactly that surface so the loop, its cadences (eval, checkpoint
ladder, pool push every `push_every_updates`), its metric names and
`extract_history` are untouched:

- `poll()` = run ONE batched step (§7.6) and return the finished episodes.
  It is the only place work happens; `pause()`/`resume()` are no-ops that
  keep the gate bookkeeping (nothing can be in flight between polls, so the
  "no decision straddles a weight change" invariant holds trivially).
- `run_in_loop(fn)` = `fn()` (there is no loop thread; pool pushes and stat
  reads are ordinary main-thread calls).
- `check()` keeps the F-03 spirit: raise if a slot has not finished within
  `max_updates_per_battle` (1000 turns × ~3 updates, generous) — the shape a
  wedged engine could produce — and re-raise any legality error.
- `stats()` emits the same `collect/*` keys with the same meanings
  (`seam_requests` = learner rows, `inference_seconds` = time inside
  `act_logp`, `episodes_finished`, `episodes_discarded` = 0 by construction,
  `battles_in_flight` = K, `rooms_tracked` = K, `rerequests` = 0) plus
  `collect/engine_updates` and `collect/opponent_inference_seconds`.

`train.py` changes: `_async_collector_mode` accepts `collector.mode: engine`
with its own strict key set (`k`, `team_bank`, `learner_seat`, `opp_action`)
and the same refusals (async-style episode batches only; no `privileged_dim`
until the block is emitted; `env_kwargs` limited to `opp_action`); `_async_loop`
takes the collector from a two-line factory. `time/steps_per_sec` keeps its
poll-cadence definition and `time/realized_steps_per_sec` (F-16) stays the
number that is quoted.

### 8.2 Opponents

- **Snapshot pool (the training opponent).** `SnapshotPool.select(rng)` picks
  a member per battle at slot restart (the per-episode rule), `pool.report`
  at finish — the same calls `PoolPlayer` makes. Members move through
  `AgentOpponent.move`-equivalent forwards on the member's own nets and its own
  `torch.Generator` (the existing determinism contract), but **batched by
  member**: group the opponent rows by member id, one forward per member per
  step. With `latest_prob 0.8` and 20 members at K=256 the latest member sees
  ~200 rows and the other 19 average ~3 — inside the batch-2..4 GEMV→GEMM
  anomaly THROUGHPUT_SPEC §1a measured (81 µs/sample at B=2 vs 19 at B=1). T-1
  measures whether that matters; the mitigation is K=512 or batch-1 servicing
  for tiny groups.
- **Scripted opponents.** `random` (uniform over the mask) and `max_power`
  (highest base power among legal moves, poke-env's `MaxBasePowerPlayer` rule)
  are trivial in Rust or numpy. `most-damage-typed` (JOURNEY's standing anchor,
  base power × type effectiveness, no switching) is equally trivial and is
  worth adding as an in-engine opponent since its definition is fixed by
  `docs/design_gen4/anchors_and_eval.md`. **`SimpleHeuristicsPlayer` is NOT
  ported**: it reads poke-env `Battle` objects, and an in-engine re-implementation
  would be a different bot with the same name — the anchor stays on the server.
- **`opp_action` labels (D25)** come for free: both seats' choices are in hand
  at every step, so `(kind, id, flags)` is emitted per learner row exactly as
  `PoolPlayer.take_choices` does today.

### 8.3 Evaluation

- The **locked protocol is unchanged**: final checkpoint, 3000 battles/seed ×
  3 seeds vs `SimpleHeuristicsPlayer` on the Showdown server, plus the anchor
  battery. The engine changes where training transitions come from, not what
  is measured. Every number produced by an engine-trained checkpoint is still
  read on the old instrument.
- **In-loop eval** (`eval_every 250000`, 100 episodes vs `heuristics`) uses
  the server today. For A-1 keep it exactly so (the server stays up for eval
  only; ~26 s per eval, trivial load) — nothing else moves. Afterwards the
  maintainer can choose F-06's budget cut or an in-engine proxy
  (`most-damage-typed`, descriptive only). Never let an in-engine `eval/win_rate`
  be read as the locked number.
- `rl/envs/engine_env.py` (single-battle `gym.Env` over `BatchEnv(k=1)`, in
  `info["action_mask"]` form) exists so `evaluate()` and the harness tests can
  run against in-engine scripted opponents without a server.

### 8.4 What the engine path makes cheap later (each is its OWN pre-reg)

Both-seat harvest (IDEAS 4.1: seat-2 rows are already encoded), the
privileged block D18 (seat 2's own-side block is a slice of an obs the env
already builds), paired evaluation with common random numbers (per-battle
seeds), and the depth-2 search question (a 384-byte clone; `-Dchance`/`-Dcalc`
builds for exact chance enumeration). None of these is in scope for A-1.

---

## 9. Verification and benchmarking plan (gates, in order)

Each gate names its instrument, its band and what a failure means. Nothing
downstream of a failed gate runs. All numbers are labelled COLLECTION-ONLY
or FULL-LOOP and carry the network width, per CLAUDE.md.

| gate | what | pass band | on failure |
|---|---|---|---|
| **B-0 build** | `pip install -e engine/pkmn_gen1` in the conda env; `pkmn_gen1.verify()`; the engine's own suite once at the pin (`zig build test -Dshowdown` in the vendor dir); Rust tests: `layout.json` offsets + the two showdown overrides, `Choice`/`Result` bit tests (`0x11`, `0x16`, `0x50`), name-map identity for 151 species and 165 moves between `data.json` and poke-env, engine vs poke-env base stats/types equal, max-PP table equal | all green | fix the build or move the pin; nothing else starts |
| **B-1 loop smoke** | 10,000 random-policy battles engine-only; every `update` legal by construction; outcomes in {Win, Lose, Tie}; never `Error`; turn ≤ 1000; mean turns and tie rate recorded | no panic, no `Error` | wrapper bug; stop |
| **P-4 stats** | for ≥ 1,000 own-side mons on the tapes, our §5.5 stats == the `|request|` `stats` (+ `maxhp`) | exact, 100% | formula/DV rule wrong; fix before P-1 |
| **P-3 teams** | bank header sha, PS commit == `59da482e`; per-team constraints (6 mons, ≤2 per type, ≤2 per spammable weakness, ≤1 level-100, ≤1 Ditto per pair) hold on 100k draws; species marginals vs `randbats_prior` set marginals agree (χ², n=100k) | constraints never violated | generator wiring bug |
| **P-1 encoder parity** | replay ≥ 5,000 tape decisions through poke-env (the `test_encoder_ids_tapes.py` harness); rebuild the engine-side observable state from the poke-env `Battle` (own side from the request, opponent from revealed info; the `shadow_battle.py` idea inverted); run the Rust encoder; compare 828 floats **bitwise** outside the declared families | 100% exact outside families; each family's count reported (Metronome/Mirror Move reveal, Struggle slot, Transform, Fire-thaw selection) with a budget of ≤ 1% of decisions in total | an undeclared mismatch is a bug, not a family; fix or declare with a why |
| **P-2 mask parity** | same replay: engine-derived mask == `get_action_mask` per decision; separately report the split of recharge / Wrap-victim / Wrap-user / locked turns and their `trapped` values against §7.2's table | 100% outside the Transform family | table wrong; fix |
| **D-1 dynamics smoke** | 10k battles engine vs 10k on the local server, both with the SAME scripted policy on both seats (`max_power` vs `max_power`, then `random` vs `random`); compare P1 win rate, tie rate, mean/percentile turns, faints per game, fraction of games with a sleep/freeze | P1 win-rate `|Δ| < 0.02` (se ≈ 0.007 at n=10k), tie-rate `|Δ| < 0.005`, mean turns `|Δ| < 5%` | a mechanic differs between the engine's patched-PS target and our PS `0.11.11`; localise with the `debug-log` build before any training |
| **T-1 throughput** | (a) engine-only battles/s, one core (expect ≥ 20k battles/s); (b) COLLECTION-ONLY learner steps/s at K ∈ {32, 64, 128, 256, 512}, entity trunk at the 100M `trunk_kwargs`, pool opponent batched by member, quoted with width and "collection-only"; (c) FULL-LOOP `time/realized_steps_per_sec` on a 12M config (`showdown_sp_struct12m`-shaped, engine mode) with the update share printed | (b) ≥ 25k steps/s at K=256; (c) ≥ 2,000 steps/s realized — the 4× claim, or the honest smaller number | if (c) < 1,500: profile; the learner or Python-side batching is the bound, and the doc's §0 numbers get corrected in place |
| **A-1 acceptance (pre-registered; the standing 2-Opus cycle, an irreversible artifact)** | 3 seeds × 12M on the engine collector vs the async-collector 12M acceptance fleet (pooled vs-SH 0.67211, seed sd 0.0122; itself +0.02322 above the sync basis 0.64889 — G9, `configs/showdown_sp_100m.yaml` N-COLL) under the locked eval protocol on the server; **primary** pooled vs-SH `|Δ| < 0.025` (G9's band; report the SIGNED delta forever after, as N-COLL does); secondary: off-FP@20 descriptive, entropy/ep-length curves overlaid; R0 gates: `collect/episodes_discarded == 0`, mask-legality errors == 0, no `Error` outcomes | inside the band with the signed delta disclosed | outside: diagnose parity (P-1/P-2 families, D-1), never tune; a NEGATIVE delta outside the band means the projection I1/I2 leaks or shifts the game and the collector is not licensed |

Only after A-1 does `collector.mode: engine` become a licensed non-lever that
future pre-regs may name; until then every number from it is a NEW INSTRUMENT
and is not comparable to any banked row. The A-1 header must restate the
credit line verbatim, name the across-lane aggregator (equal-weight mean of
per-seed finals), and say which side each band reads.

---

## 10. Edge cases and mitigations

| edge | risk | mitigation |
|---|---|---|
| **Engine is pre-release** ("heavy development, breaking changes", no releases) | API/layout churn on upgrade | pin the commit; `verify()` asserts sizes and `PKMN_OPTIONS`; the layout test parses the vendored `layout.json`; moving the pin re-runs B-0..P-2 |
| **Zig drift** (engine tracks master; minimum 0.16.0) | a newer engine commit may need a nightly Zig | pin both; if a future pin fails on 0.16.0, choose the newest engine commit that builds on it rather than an unpinned nightly |
| **Showdown drift** (engine targets patched PS at `@pkmn/sim 0.9.31`; our server is PS 0.11.11 `59da482e`) | a gen 1 mechanic could differ | D-1 bands; the engine's README §Bugs list is the reference for expected divergences; anything outside it is investigated with the `debug-log` build |
| **Hidden-information leak** (I1) | the in-engine game is easier than the real one; in-engine strength would not transfer to the server/ladder | the tracker never reads hidden fields (§7.1 table); P-1 is bitwise; an explicit leak audit lists every engine field with its visibility class |
| **Aliased turns** (sleep, freeze, first Wrap-victim turn, recharge, Struggle) | wrong mask or un-zeroed blocks teaches "slot-0 features ⇒ action 6" | §7.2 table; P-2 counts each kind |
| **Transform (Ditto), Mimic** | poke-env's `[:4]` dict semantics differ from the live slots | declared non-parity family; the engine env exposes the live slots (the correct game); counted at P-1/P-2 |
| **Metronome / Mirror Move reveal, Struggle slot** | diff-based reveal cannot see `[from]` calls | declared families with a 1% total budget; fallback = `debug-log` protocol decode for `|move|` |
| **Endless battles** | two Rest/Recover stallers | the engine implements EBC and the 1000-turn tie under `-Dshowdown`; `check()` also bounds updates per battle |
| **Two Dittos in one battle** | PS never generates it | re-draw the pairing (§6.2) |
| **`Outcome::Error`** | impossible in showdown mode | raise with the battle bytes attached |
| **Alignment / endianness** | u64 seed at 376, u16 fields | `#[repr(C, align(8))]`; explicit LE decoding; big-endian `compile_error!` |
| **libclang absent** | bindgen fails | bindings are committed; regeneration is a feature flag |
| **PIC / linking** | static `.a` into a cdylib | `-Dpic=true`; add `-lc` on Linux if needed |
| **Batch-2..4 opponent groups** | GEMV→GEMM anomaly (81 µs/sample at B=2) | measure at T-1; K=512 or batch-1 servicing for groups < 8 |
| **Resume** | in-flight battles lost, seeds repeat | whole-episode-only semantics (same as async); `battle_counter` persisted so the seed sequence continues |
| **Memory** | K=256 battles | 384 B + ~1 KB tracker each; obs buffers K×828×4 B ≈ 0.85 MB; negligible next to the learner |
| **RNG seeds and reproducibility** | a lane must be replayable | `splitmix64(lane_seed, battle_counter)` for the battle, `^1` for the team pair; both stamped per episode (`episode["seed"]`) so any battle can be re-run in isolation |
| **State cloning for search / MCTS** | JOURNEY 11.5 wants cheap clones with exact chance handling | `Battle: Clone` (memcpy); a second build with `-Dchance -Dcalc` (feature `search`, separate artifact/crate — one process cannot link both static libs under the same symbols) exposes `pkmn_gen1_battle_options` for chance probabilities and forced rolls; determinisation of the hidden opponent team stays `rl/search/determinize.py`'s job. Out of scope for the collector |
| **Learner always P1** | asymmetries ("host" ordering, speed-tie handling) baked into training | keep P1 for A-1 parity; `alternate`/`random` is a later pre-reg with its own read |
| **Concurrent lanes** | none of the server-era collisions (usernames, rooms, timers) exist | distinct `--seed`s still required for distinct battle streams; no server to share |

---

## 11. Open questions for the maintainer (decide before B-0)

1. **Ruling to implement, and when.** Off-arc for step 2/3; the natural slot is
   after the LADDER R4 readout, in parallel with the gen 4 design (which it
   does not help). A chapter number / script prefix (`ch6_`?) is needed.
2. **Team source:** the PS-generated bank (recommended, exact) vs a Rust port
   (only if the bank ever shows up in a measurement).
3. **In-loop eval for A-1:** keep the server for eval only (recommended) vs
   an in-engine proxy (descriptive only) vs F-06's budget cut.
4. **Learner seat:** P1-only (parity) vs alternating — a separate pre-reg
   either way; the knob exists from day one.
5. **Zig via the `ziglang` wheel** (pinned in the conda env) vs a system
   install; the wheel is recommended for the same reason `poke-engine` is
   built from source with a pinned command.
6. **Bindings committed vs generated at every build** — committed is
   recommended (no libclang requirement); the maintainer asked for bindgen,
   which is still the generator.
7. **Whether A-1 goes through the full 2-Opus design cycle** — it produces a
   licensed non-lever and a pre-reg, so by the standing rule it does.

---

## 12. Build sequence (ordered; each step ends green and committable)

| # | step | deliverable | est. |
|---|---|---|---|
| 1 | Toolchain + vendor: `ziglang`, `maturin`, submodule at the pin, `requirements-engine.txt` | `zig build` of the engine succeeds locally; engine test suite green at the pin | 1 evening |
| 2 | Crate skeleton: `build.rs`, committed bindings, `ffi.rs`, `verify()`, PyO3 `build_info` | `pip install -e` works; `pkmn_gen1.verify()` passes (B-0 first half) | 1 evening |
| 3 | `battle.rs` + `layout.rs` + tests (bits, offsets, name maps, base stats) | B-0 complete; B-1 random-policy loop runs 10k battles | 1–2 evenings |
| 4 | Team bank script + `team.rs` + stat calc | P-3, P-4 green | 1 evening |
| 5 | `tables.rs` + `rl/envs/engine_tables.py` (+ prior table) | tables fingerprint; identity/name tests | 1 evening |
| 6 | `observe.rs` + `encoder.rs` + `env.rs` (mask table §7.2, pumping, restarts) | `engine_env.py` plays a battle against `max_power` end to end | 3–4 evenings |
| 7 | `scripts/engine_parity.py` P-1 / P-2 on tapes; declare families with counts | P-1, P-2 green | 2 evenings (the grind) |
| 8 | `EngineCollector` + `train.py` factory + config validation + metadata stamping + tests mirroring `test_showdown_async.py` | a 12M engine-mode smoke runs; `extract_history` reads it | 2 evenings |
| 9 | D-1 dynamics smoke; T-1 (a)(b)(c) with the quoting rules | numbers in this doc's §0 replaced by measured ones | 1 evening + a few hours of box time (server up for D-1 only) |
| 10 | A-1 pre-reg (2-Opus cycle) → 3 × 12M fleet (< 2 h each at the projected rate: agent-side) → readout, SESSION_LOGS, STATUS, README row | the collector licensed or not | 1 evening design + 1 fleet-day |

Total: ~12–16 evening blocks plus one fleet-day. Steps 1–5 need no server;
steps 7–8 need the tapes; D-1 and A-1's evals need the local server up
(never during a ladder run — LG-7).

---

## Appendix A — byte-offset quick reference (showdown build)

```
Battle(384): sides[0]@0 sides[1]@184 turn:u16@368 last_damage:u16@370 last_moves[4]@372 rng:u64@376
Side(184):   pokemon[6]x24@0 active(32)@144 order[6]@176 last_selected_move@182 last_used_move@183
Pokemon(24): stats{hp,atk,def,spe,spc}:u16x5@0 moves[4]{id,pp}@10 hp:u16@18 status@20 species@21 types@22 level@23
Active(32):  stats@0 species@10 types@11 boosts:u32@12 volatiles:u64@16 moves[4]@24
Boosts bits: atk 0 def 4 spe 8 spc 12 accuracy 16 evasion 20 (i4 each)
Volatiles bits: Bide0 Thrashing1 MultiHit2 Flinch3 Charging4 Binding5 Invulnerable6 Confusion7 Mist8 FocusEnergy9
                Substitute10 Recharging11 Rage12 LeechSeed13 Toxic14 LightScreen15 Reflect16 Transform17
                confusion:u3@18 attacks:u3@21 state:u16@24 substitute:u8@40 transform:u4@48 disable_duration:u4@52 disable_move:u3@56 toxic:u5@59
Status byte: bits0-2 sleep left | 3 PSN | 4 BRN | 5 FRZ | 6 PAR | 7 EXT (self-sleep / with PSN = TOX)
Choice u8:   kind bits0-1 (0 pass,1 move,2 switch) | data bits2-7     Result u8: kind bits0-3 | p1 req bits4-5 | p2 req bits6-7
```

## Appendix B — source pointers

Engine (at the pin): `src/include/pkmn.h`; `src/lib/gen1/README.md` (§Layout,
§Bugs, §RNG); `src/lib/gen1/data.zig` (structs, `Status`, `Volatiles`,
`Stats.calc`); `src/lib/gen1/mechanics.zig` (`update` :53, `choices` :3139,
`isForced` :2706, `endTurn` :1640); `src/lib/gen1/helpers.zig`;
`src/lib/common/data.zig` (bit tests); `src/lib/common/rng.zig`;
`src/lib/common/options.zig` (`mod`, `ebc`); `src/data/{data,layout,protocol}.json`;
`build.zig`, `build.zig.zon`, `Makefile`; `docs/TESTING.md` (benchmark, patches);
`examples/c/example.c` (the canonical update loop).

Showdown (vendored `59da482e`): `sim/pokemon.ts` (`getHealth` :2065,
`getMoveRequestData` :1090-1130 incl. the gen 1 `Fight` placeholder :1105,
`calculatePP` in `sim/battle.ts` :2371, `statModify` :2351);
`data/mods/gen1/conditions.ts` (`partiallytrapped`, `mustrecharge` inherits
`onLockMove`, `lockedmove`); `data/random-battles/gen1/{teams.ts,data.json}`;
`sim/teams.ts` (`Teams.generate` :651).

This repo: `rl/envs/showdown.py` (layout :128-145, `_fill_*` :191-268,
`embed_battle` :269, `_fill_ids` :349, `_move_slots_aliased` :393,
`_effect_block` :502, `_spe_est`/`_speed_edge` :555, `_opponent_move_slots`
:582, `ShowdownEnv.step` wait pump :1289); `rl/envs/encoder_spec.py::GEN1`;
`rl/envs/randbats_prior.py`; `rl/envs/showdown_async.py` (the collector
surface); `rl/train.py::_async_collector_mode/_async_loop` :623-865;
`rl/buffers/episode.py`; `rl/selfplay/pool.py`; `rl/search/bridge.py` and
`shadow_battle.py` (the engine↔encoder mapping precedent); `requirements-search.txt`
(the Rust-dependency precedent); `docs/prior_work/THROUGHPUT_SPEC.md` (the measured
budget); `docs/landmines.md` §Throughput numbers; `RESULTS.md` §18 (realized
steps/s); `docs/IDEAS_POST_100M.md` §1 (why seeds are the lever).

poke-env 0.15.0 (installed): `environment/singles_env.py` (`action_to_order`
:77, `get_action_mask` :233); `battle/abstract_battle.py`
(`_update_team_from_request` :1279); `battle/battle.py` (`parse_request` :61,
`trapped`, `force_switch`, `available_switches`); `battle/pokemon.py`
(`update_from_request` :716, `status_counter` :1303 and its increment sites
:194/:415/:483).

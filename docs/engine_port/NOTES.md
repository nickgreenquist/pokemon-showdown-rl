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
| B-1 loop smoke | 1 | 0.4 |
| P-4 stats | 1 | 0.5 |
| P-3 teams | 1 | 0.6 |
| P-1 encoder parity | **3** | 1.2 |
| P-2 mask parity | **1** | 0.8 |
| adversarial review + acting on it | (slack) | 0.8 |
| total | **10** | **5.3** |

Well inside the box. The P-1/P-2 grind the brief warned about did not
materialise, and the reason is structural rather than luck: P-1 as the plan
specifies it compares the two encoders GIVEN IDENTICAL OBSERVABLE STATE, which
takes the whole reveal-by-diff problem out of scope (see the P-1 disclosure
below). What is left is arithmetic, and arithmetic either matches bitwise or
points straight at the line that differs.

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

---

## Gate B-1 — loop smoke — **PASS** (2026-09-06)

10,000 random-policy battles twice: once with the engine's own fuzz moveset
configuration (`helpers.zig::blocked` excludes Mimic / Metronome / Mirror Move /
Transform) and once with all 164 non-Struggle moves, because real randbats teams
carry Mimic and Transform.

| | blocked | all 164 |
|---|---|---|
| P1 wins / P2 wins / ties | 5079 / 4903 / 18 | 5018 / 4959 / 23 |
| of which 1000-turn or EBC ties | 0 | 0 |
| mean turns | 104.0 | 104.9 |
| min / max turns | 25 / 576 | 21 / 649 |
| mean updates per battle | 113.3 | 114.2 |
| learner decisions (forced) | 2,165,654 (108,674) | 2,182,939 (109,505) |

No `Error` outcome, no battle past turn 1000, no illegal choice, no empty choice
list, every outcome in `{Win, Lose, Tie}`. All 41 ties were double KOs.

Mean turns of ~104 is a random-policy artifact; with real bank teams (P-3's
round-trip leg) it is **60.3**, which is the right order for gen-1 randbats.

**The battles/s the script prints is NOT a T-1 number** and the script says so
in its own output. It includes team generation and the wrapper's per-update
legality check, it is a random policy with no encoder, and it was measured next
to three training lanes. T-1 is out of scope while the fleet runs.

### A build-time bug worth remembering

The first codegen of the engine's tables **alphabetised** them: `serde_json`'s
default `Map` is a `BTreeMap`, so `data.json`'s dex-ordered species came out with
Abra at index 1. Caught by a spot-check assertion, not by anything downstream.
Fixed with the `preserve_order` feature, and `build.rs` now pins the ends of both
tables (`Bulbasaur`..`Mew`, `Pound`..`Struggle`) so it cannot recur silently.

## Gate P-4 — stats — **PASS, exact** (2026-09-06)

Our §5.5 stats against the `|request|` `stats` + `maxhp` on the full tape corpus
(all 9 tapes, ~700 MB, 54 s):

A set reappears in every request of its battle, so the headline row below is a
REPEAT count: on the first tape, 7,200 stat rows are 240 distinct (room, mon) and
only **168 distinct (species, level, moveset)**. The distinct-arithmetic-instance
count over the whole corpus is smaller than 44,100 again and is not measured
here. Read the distinct row, not the first one.

| | |
|---|---|
| distinct (room, mon) sets | **44,100** |
| own-side mon checks (repeats included) | 1,304,243, mismatched **0** |
| checks with a max-HP reading | 996,569 |
| max-PP slots checked | **625,433**, mismatched **0** |
| skipped: transformed | 805 mons / 552 PP reads |
| skipped: fainted (no max HP) | 307,674 |

The arithmetic goes through the RUST code (`pkmn_gen1.set_stats` /
`pokemon_record`), not a Python re-implementation. Passing also required
reproducing the randbats IV/EV rules, since the request's numbers are not
reachable without them: IVs 30 / EVs 255, minus the Substitute HP-divisibility
walk and the "minimize confusion damage" `evs.atk = 0, ivs.atk = 2` rule
(`showdown/data/random-battles/gen1/teams.ts:271-292`).

### Two findings from P-4 that bear on everything downstream

1. **THE CATEGORY TRAP.** In gen 1-3 a move's category comes from its TYPE, not
   from the modern dex: PS rewrites it in `data/mods/gen3/scripts.ts:5-14`
   (Fire/Water/Grass/Ice/Electric/Dark/Psychic/Dragon → Special, everything else
   → Physical) and gen 1 inherits that. poke-env serves BOTH readings: the raw
   `GenData.from_gen(1).moves[id]` dict keeps the MODERN category (Hyper Beam
   Special, Razor Leaf Physical), while the `Move(id, gen=1)` CLASS applies the
   gen fix. Reading the raw dict made a Swords-Dance Tentacruel look like an
   all-special set and cost it 67 Attack. **The encoder uses the `Move` class, so
   it is correct** — and `engine_tables.py` uses it too, deliberately.
2. **TRANSFORM CHANGES WHAT A REQUEST MEANS.** `showdown/sim/pokemon.ts:1310-1330`
   copies `storedStats` from the target, and gives each copied slot
   `pp = min(5, base)` and, for gen < 5, `maxpp = calculatePP(move, ppUps=0)` —
   the BASE PP, with no PP Ups. So after Transform the request's `stats` stop
   describing the set and its `maxpp` stops being the PP-Upped max. Transformed
   mons are retired from both P-4 legs. (poke-env models this differently again —
   see the P-1 section.)

## Gate P-3 — teams — **PASS** (2026-09-06)

The bank is generated by Showdown itself at the pinned commit `59da482e`
(`dist/sim` only: no server started, no socket opened; `git status` in the
`showdown/` tree was clean before and after). 50,000 pairs in 99 s.

| | |
|---|---|
| pairs / teams / mons | 50,000 / **100,000** / 600,000 |
| per-team constraint violations | **0** |
| pairs containing a Ditto | 5,379 |
| pairs containing TWO Dittos | **0** |
| Ditto in team 1 / team 2 | 2,780 / 2,599 |
| distinct species drawn | 146 |
| species χ², even vs odd pairs (bank vs ITSELF) | 140.2 on dof 145, p = 0.60 |
| move marginals vs `randbats_prior` | 366 stochastic cells over 110 species; **max \|z\| 3.15** against a Bonferroni threshold of **3.81**; 0 cells over |
| deterministic cells agreeing exactly | 433 |
| round trip | 500 bank battles played through the engine, mean **60.3** turns |

Constraints checked per team: exactly 6 mons, Species Clause, ≤2 sharing a type,
≤2 weak to each of the six spammable attack types, ≤1 level-100, every species
present in `randbats_prior`, and the level equal to the prior's.

The move-marginal leg is the one with teeth: `rl/envs/randbats_prior.py` is a
Python re-implementation of `randomSet` that the ENCODER reads at inference time
(`_opponent_move_slots`), and this is the first time it has been checked against
what PS actually generates.

**Deviation from plan §9, stated plainly.** §9 asks for "species marginals vs
`randbats_prior` set marginals agree (χ², n=100k)". The species χ² that ran is
bank-even-pairs vs bank-odd-pairs — the bank against ITSELF, which can only
detect nonstationarity and could never catch a wrong generator. Species-vs-prior
is covered only by membership and level equality. The leg with real teeth is the
MOVE-marginal one, which is genuinely bank-vs-prior. A species-marginal test with
teeth would need a reference distribution the prior does not carry (it models
sets per species, not the species draw), so the gap is structural rather than an
oversight — but it is a gap.

**Statistics note.** No per-species χ² over move presence: the four slots of a
set are dependent (exactly four are drawn), so summing per-move 2×2 tables would
have the wrong degrees of freedom and a meaningless p-value. A two-sample z per
cell with a Bonferroni threshold says the same thing honestly. Likewise the
species self-consistency test splits by PAIR PARITY, not by team-within-pair —
the Ditto rule makes the second team of a pair a genuinely different distribution
(by design), so first-vs-second would flag a feature as a bug.

### PLAN CORRECTION — the bank's unit is a BATTLE, not a team

Plan §6.2 stores single teams and re-draws the second when both contain Ditto.
That is a **different distribution**. `battleHasDitto` is a field on the team
GENERATOR; PS creates exactly one generator per `Battle` and calls `getTeam()`
twice (`sim/battle.ts:3171-3177`); and the rule is enforced by SKIPPING Ditto
while picking the second team — it resamples ONE SLOT, not the whole team.
Reusing one generator across many teams would also silence Ditto after its first
appearance. So the bank stores PAIRS. The asymmetry is visible and in the
predicted direction: Ditto appears in 2,780 first teams and 2,599 second teams
(a difference of 2.5 se).

## Gate P-1 — encoder parity — **PASS, bitwise** (2026-09-06)

**100,000 tape decisions across 8 tapes. 828 floats each — 0 bitwise
mismatches.** Tables fingerprint `d2ba00c2ef52ba33`. 97 s.

Family EXPOSURE over the same 100,000 (counted on EVERY decision, not only on
mismatching ones, where a zero would be true by construction): **transform
1,117, Mirror Move 210, Struggle slot 0.** So the Transform family is present in
the corpus at ~1.1% and does not mismatch; the Mirror Move reveal family is
present at 0.2% but is a property of the engine→state path, which this gate does
not exercise (below).

"82,800,000 float comparisons" is the raw lane count and overstates the
independent content: 184 of the 828 floats per decision (8 move blocks × the
23-float v2 effect sub-block) are a verbatim copy of shared `_effect_block`
output, sanctioned by plan §7.4 but not an independent computation. Measured over
6,000 decisions, **81 of 828 columns are constant** across the whole corpus (79
constant-0 — the TOX status slot, the three dead volatile slots below, unused
effect and type one-hot lanes — and 2 constant-1); **747 carry variance**.

### What P-1 tests, and what it does NOT

The plan's P-1 replays tapes through poke-env, **rebuilds the engine-side
observable state from the resulting poke-env `Battle`**, runs the Rust encoder
and compares bitwise. So it answers exactly one question: *given identical
observable state, do the two encoders agree?*

**It therefore does not exercise the engine→state path at all**, and the two
families plan §7.1.1 declares — Mirror Move reveal, and the Struggle slot — live
entirely on that path. Their absence from this result is not evidence that they
are small; they are **untested until D-1/A-1**. Saying so is the point: the 0
above is a real and useful zero, but it is a zero about arithmetic and table
semantics, not about reveal-by-diff. The species→base-stats/types table is also
unexercised here, deliberately: the Transform design (below) has the PRODUCER
supply stats and types, so P-1 never reads the 152-row species table that the
real collector will.

### An adversarial review found this gate blind on 45% of its columns; it is fixed

The first version of this harness imported `_move_slots_aliased` and
`_opponent_move_slots` from `rl/envs/showdown.py`. Those are not tables — they
are per-decision RULES that `embed_battle` itself calls, and importing them meant
both sides computed them the same way, so a wrong rule was invisible. The review
proved it by mutation: corrupting either function in BOTH modules left the
mismatch count at **0/1500**, while between them they govern the `aliased` flag
(column 5), the own-move blocks `[220..404)` and ids `[820..824)`, and the
opponent-move blocks `[624..808)` and ids `[824..828)` — **377 of 828 columns**.

Both are now implemented on the engine side and the imports are gone:

- `aliased` is derived in the harness from the RAW `|request|` JSON (a single
  offered move whose id is one of poke-env's `SPECIAL_MOVES`);
- the opponent slot assignment, the set-prior conditioning and the ordering live
  in Rust (`tables.rs::SpeciesPrior`, `encoder.rs::opponent_move_slots`). Plan
  §7.4 called for a `prior` table and the first version did not have one; it now
  does. Only the 4,000 sampled sets per species travel from Python, as data.
  The Rust `conditional_move_probs` was checked against
  `randbats_prior.conditional_move_probs` for **all 146 species**, unconditioned
  and conditioned, with **0 disagreements** — exact, because the mean of a 0/1
  column over `k` kept rows is `count / k` with both integers below 2^53.

**A POSITIVE CONTROL now ships with the gate.** `scripts/engine_p1_run.py
--mutate {alias,opp_order,prior}` corrupts one rule in the REFERENCE encoder
only; a gate that still reports 0 is blind to that rule.

| control | mismatched / 6,000 |
|---|---|
| `none` (the gate as run) | **0** |
| `alias` — force `_move_slots_aliased` False | 167 |
| `opp_order` — reverse the opponent slot order | 5,983 |
| `prior` — flatten every prior probability to 0.5 | 6,000 |

The zero is now a zero those three mutations could have broken.

### How bitwise equality was achieved (the rule the code follows)

The Python encoder computes in Python floats (f64) and rounds exactly once, when
numpy stores into the float32 array. `encoder.rs` does the same: every derived
value is computed in f64 and cast with a single `as f32` at the store. Values
Python stores verbatim from a table — `accuracy`, the 23-float v2 effect block,
the set-prior probabilities — travel as data and are never recomputed
(`_effect_block` is IMPORTED by `engine_tables.py`, not reimplemented). Without
that rule a `(base as f32) / 255.0f32` would differ from Python by 1 ulp on some
entries and "bitwise" would have been unreachable.

### Three things the design had to get right, each of which was wrong first

1. **A mono-type defender takes ONE chart lookup.** poke-env's
   `damage_multiplier` returns `chart[type_1][atk]` alone when `type_2 is None`;
   repeating the type would square it (2× becomes 4×). `MonView.type_2` is
   therefore `Option<u8>` and the P-1 extractor emits `-1`, not a repeat.
2. **Base stats and types are carried EXPLICITLY, not looked up from the
   species.** Transform separates identity from stats: poke-env replaces
   `_temporary_base_stats` / `_temporary_types` and leaves `_species` alone
   (`pokemon.py:625-636`); the engine writes the copied species into
   `ActivePokemon.species` while `Pokemon.species` keeps the original. Making
   the PRODUCER state which stats apply removes a whole class of silent
   disagreement — and it removed the Transform family from P-1 outright.
3. **`pp/maxpp` uses the MOVE's `max_pp`, not the table's.** They part company
   after Transform, where poke-env builds the copied `Move` with
   `from_transform=True`.

### A trap that cost a debugging cycle, now guarded

`cargo build` refreshes `target/`, but the IMPORTABLE extension only changes on
`pip install --no-build-isolation -e engine/pkmn_gen1`. A stale editable install
is invisible: the old parser ignored the new state keys and silently used the
untransformed species, producing 61 "transform-family" mismatches that were
entirely an artifact of not reinstalling. `pkmn_gen1.__state_schema__` now exists
and the P-1 harness refuses to run against the wrong one.

### PLAN CORRECTION — poke-env's move dict IS transform-aware

Plan §7.2's Transform row says "poke-env's `[:4]` still names the ORIGINAL dict
entries" and declares a non-parity family on that basis. In poke-env 0.15.0 it is
false: `Pokemon.moves` returns `_moves.moves`, which resolves to the
`_transform_moves` set when transformed (`move.py:974-975`). poke-env and the
engine therefore agree on the live slots, and the family does not exist.

## Gate P-2 — mask parity — **PASS** (2026-09-06)

Three legs, because "engine-derived mask == `get_action_mask`" decomposes into
three separable claims and mixing them would hide which one broke.

### Leg A — mask parity, 100,000 tape decisions, **0 mismatches**

The mask is derived from the RAW `|request|` JSON — what Showdown itself sent,
which is what the engine's `-Dshowdown` mode is defined to reproduce — through
§7.2's table, and compared to poke-env's `get_action_mask` on the parsed
`Battle`. Two independent readings of the same protocol.

**This leg CONFIRMED plan §7.2's load-bearing ordering claim by first
falsifying the alternative.** Showdown's `side.pokemon` is the CURRENT order and
puts the active mon first, so it re-permutes on every switch; poke-env's
`battle.team` is filled from the FIRST request and never reordered. Indexing by
the live request order gave **3,744 mismatches in 6,000 decisions**; indexing by
the first-request order gives **0 in 100,000**.

Scope of that, precisely: what is measured is *poke-env's team order == the first
request's `side.pokemon` order*. §7.2's full claim is that this also equals the
engine's `side.party(i)`; the engine is not consulted by this leg, and that half
rests on `Battle::new` writing the parties in order (asserted in
`tests/layout.rs`) plus Showdown listing the generated team in that same order.

### Leg B — the §7.2 rows, read off the wire (100,000 decisions)

| row | n | request `trapped` | poke-env `trapped` |
|---|---|---|---|
| normal | 84,983 | 0 | 0 |
| force_switch | 12,626 | 0 | 0 |
| placeholder (`[Fight]`) | 1,648 | 0 | 0 |
| recharge (`[Recharge]`) | 540 | **540** | **540** |
| hard_lock (one real move + trapped) | 65 | **65** | **65** |
| one_move_set | 138 | 0 | 0 |
| semi_lock (Bide / Wrap user) | **0** | — | — |

**The two readings of `trapped` agree in every row.** These are two independent
per-row TOTALS, not a paired per-decision test, so in principle a compensating
swap inside a row would print identically; at n = 540 and n = 65 that is remote,
but the instrument is weaker than the sentence. That settles plan §7.2's
own open question ("the encoder's own measurement that `battle.trapped` is False
on 1,262 of 1,273 recharge/partial-trap turns … P-2 must confirm the split before
this table is trusted"): the split is exactly as §7.2 predicts, and the earlier
1,262/1,273 reading was of a category that pooled the `[Fight]` placeholder —
never trapped — with recharge, which always is.

Causes behind the locked rows, from poke-env's state: the placeholder is
**asleep 1,178 / frozen 469** and nothing else; every hard lock is a two-turn
charge (62, plus 3 also frozen); every recharge row is `must_recharge`.

`one_move_set` is a row plan §7.2 does not have: a mon whose SET has one move
(Ditto knows only Transform) produces a one-entry request that is
indistinguishable from a semi-lock unless the stored move list is consulted. All
138 are that; none is a lock.

### Leg C — the engine half of the table, 20,000 bank battles, 2,453,224 decisions

The tapes cannot test the engine's own `choices()` shape, so this leg plays the
BANK's teams in the engine and reads its volatiles directly.

| | |
|---|---|
| hard locks (`isForced`) | 29,057 — recharging 26,713, charging 2,344, thrashing 0, rage 0 |
| semi-locks (`limited` = Bide or Binding) | **0** |
| binding VICTIM turns | 0 |
| asleep / frozen turns | 155,303 / 31,324 |
| Struggle-only turns | 912 |
| **hard lock not a single `Move(1)`** | **0** — falsifiable, 29,057 opportunities |
| **hard lock offered a switch** | **0** — falsifiable, 29,057 opportunities |
| semi-lock not exactly one move | 0 — **VACUOUS here** (0 opportunities) |
| semi-lock dropped a switch | 0 — **VACUOUS here** (0 opportunities) |

Leg C also compares the engine's `choices()` against the engine's OWN volatile
bits, so it checks pkmn/engine's internal consistency plus our byte-offset
reading — not the engine against Showdown.

### Leg C′ — the falsification leg, 5,000 synthetic battles, 792,178 decisions

The two vacuous rows above are vacuous because the randbats pool has no binding
or Bide move (the finding below). So a second run uses hand-built teams carrying
all eight of the moves the format lacks, purely to give those assertions
something to be wrong about. This is a check on the ENGINE MAPPING, not a claim
about `gen1randombattle`.

| | |
|---|---|
| hard locks | 90,744 — thrashing 36,050, rage 54,694 |
| **semi-locks (`limited`)** | **54,381** — bide 12,939, binding 41,442 |
| binding VICTIM turns | 41,442 |
| hard lock not a single `Move(1)` / offered a switch | **0 / 0** |
| **semi-lock not exactly one move / dropped a switch** | **0 / 0** |

All four §7.2 shape assertions are now falsifiable and all four hold.

### The finding that simplifies §7.2: three of its rows are UNREACHABLE in this format

`rl/envs/data/gen1_randbats_sets.json` (a byte copy of Showdown's own gen-1
randbats pool) contains **no** Wrap, Bind, Clamp, Fire Spin, Thrash, Petal Dance,
Rage or Bide — zero species offer any of them. So in `gen1randombattle`:

- the **Wrap-user**, **Wrap-victim** and **Bide** rows of §7.2 cannot occur;
- `Effect.PARTIALLY_TRAPPED` can never be set, which makes the encoder's
  `PARTIALLY_TRAPPED` volatile slot **structurally dead in this format** — the
  same shape of defect the D13a `MUST_RECHARGE` fix addressed, though here the
  cause is the format's set pool, not a parser gap;
- `LEECH_SEED` and `FOCUS_ENERGY` are dead for the same reason (neither move is
  in the pool);
- `Metronome` is not in the pool either, so plan §7.1.1's "Metronome / Mirror
  Move" reveal family reduces to **Mirror Move alone** (4 species offer it).

The engine mapping still implements all of them — other gen-1 formats and the
search line need them, and leg C verifies the hard-lock shape directly — but the
randbats collector will never exercise them, and no A-1 number can be attributed
to them.

**Volatile-slot census** over 100,000 decisions (the seven encoder slots, per
active decision), reported with its caveat: these tapes are Foul Play (our seat)
versus a scripted opponent, so the own/opp asymmetries below are POLICY
asymmetries of the corpus, not properties of the format or of poke-env.

| slot | own | opp |
|---|---|---|
| CONFUSION | 0 | 1,684 |
| FOCUS_ENERGY | **0** | **0** |
| LEECH_SEED | **0** | **0** |
| MUST_RECHARGE | 1,646 | 6,860 |
| PARTIALLY_TRAPPED | **0** | **0** |
| REFLECT | 129 | 25 |
| SUBSTITUTE | 107 | 0 |

(Verified in the raw protocol: in `run_4106` only `p2a` is ever confused and only
`p1a` ever puts up a Substitute. The three bolded zeros are the format-level
finding above and do not depend on the corpus.)

---

## Fleet impact, whole session (brief §2)

`scripts/engine_port_fleet_guard.sh`, dStep/dWall between the two newest
checkpoints of each lane:

| window | s200 | s208 | s216 |
|---|---|---|---|
| before any build (22:45Z) | 203.4 | 190.2 | 201.3 |
| after B-0 (22:58Z) | 202.3 | 200.6 | 201.3 |
| after P-3 (23:24Z) | 202.3 | 200.6 | 194.4 |
| after P-2 (23:54Z) | 195.1 | 194.9 | 195.0 |
| after the review fixes (00:35Z) | 204.3 | 197.4 | 195.0 |

Never below **194.9**, and back to 204.3 / 197.4 / 195.0 at the end; the band's STOP line is 180 and its RECORD line is 180.
Every lane stayed `alive` in the wave log throughout, all three moved together in
the last window (which is not the shape single-core Python load produces), and no
build ran wider than `-j2` or outside `taskpolicy -b`. Peak observed box load 5.7
of 14 cores. Nothing owned by the fleet was started, stopped or written to; the
only main-tree access was read-only, by absolute path (`data/fp_tapes*`,
`showdown/`, `runs/*/ckpt_*.pt` mtimes, `logs/gen4_wang50m_wave.log`).

## Where this stops

**P-2 is the last gate in scope.** D-1 (dynamics smoke — needs a server), T-1
(throughput — needs an idle box) and A-1 (acceptance fleet) are out of scope while
the gen-4 fleet runs, per brief §3, and nothing here should be read as a
throughput or strength claim.

## The adversarial review (brief §4b)

One read-only reviewer was run at the end, with a single question: does the
parity harness compare what it claims to? It found the P-1 circularity above
(fixed, with a positive control now shipping), the vacuous semi-lock assertions
(fixed with leg C′), and five places where a NOTES sentence was stronger than its
instrument (all corrected in place: family exposure, the 82.8M lane count, the
paired-vs-aggregate `trapped` reading, P-4's repeat count, P-3's substituted
χ²). It confirmed independently that the comparison is genuinely bitwise
(`np.uint32` view, no tolerance anywhere in the path), that `mask_from_request`
touches no attribute of the parsed `Battle`, that there are no duplicate
`(room, rqid)` pairs in 184,221 decision events across the corpus, and that P-4
is not tautological. Its remaining open item — that P-2 never compares an
ENGINE-derived 10-way mask to anything, since leg C reads the engine but builds
no mask — stands as written: the bridge from engine `choices()` to the request PS
would send is argued from the engine's showdown-mode definition, not measured,
and cannot be measured without D-1.

## Owed / open when this branch merges

1. **README provenance for pkmn/engine** (MIT, © 2021-2024 pkmn contributors,
   commit `9b88fd6c…`) — the repo rule requires it; brief §1.6 forbids me to edit
   `README.md`. Code-level provenance IS in place (`Cargo.toml`, `src/lib.rs`,
   `.gitmodules`, `engine_tables.py`, `engine_team_bank.py`/`.js`).
2. `requirements-engine.txt` is NOT written: plan §4.5's version of it says
   "install into the `pokemon-showdown-rl` env", which is exactly what this
   session must not do. It should be written by whoever merges, against whatever
   env policy holds then.
3. The plan corrections above (§6.2 pairs, §7.2 Transform row, §7.2's three dead
   rows, §4.3's pyo3 feature) are recorded here rather than edited into
   `docs/PKMN_ENGINE_RUST_PLAN.md`, because that file is on `main`.
4. The D-1 band should be revisited with the P-2 finding in hand: with no
   binding, Bide, Thrash or Rage in the format, the mechanics D-1 can actually
   discriminate are a smaller set than plan §10 assumes.

---

# Beyond the gates (2026-09-07, maintainer-authorised)

The brief scoped six gates and said stop. The maintainer then asked for two
further pieces, both server-free and both untouched by the fleet. Neither is a
gate and neither licenses anything.

## The engine→observable tracker (`src/track.rs`) — plan §7.1's producer

This is the half of the port P-1 deliberately does not test. P-1 compares the two
ENCODERS given identical observable state; `track.rs` is what DERIVES that state
from the engine's 384 bytes, by diffing, with `-Dlog` off and nothing parsed.

Rules pinned against their sources rather than against the plan's summary:

- **HP quantisation.** Showdown's `getHealth` under the HP Percentage Mod
  (`sim/pokemon.ts:2065`, and the tapes confirm the rule is on) is
  `ceil(100*hp/maxhp)`, forced to 99 when that rounds a non-full mon up to 100,
  and 0 when fainted. A property test walks every `hp` in `1..max` for five
  values of `max` and asserts the result lands in `1..=100` and equals 100 only
  at full HP.
- **Transform.** The engine writes the copied species and types into
  `ActivePokemon` and the copied moves at **5 PP**
  (`mechanics.zig:2456-2461`) — which is `min(5, base)`, matching PS and
  poke-env. So the tracker reads stats and types from `active.species` for the
  active mon and from the stored record otherwise: the same identity/stats split
  `MonView` already carries, now with an engine-side producer.
- **Move reveal** is by PP decrement on the LIVE slots, and is never inferred
  across a switch (the slots belong to a different mon). **Sleep turns** are
  counted from observed decrements and reset on entry and exit, never read from
  `status & 7`. **PARTIALLY_TRAPPED** reads the FOE's `Binding` bit, because the
  flag sits on the user.

### The I1 leak audit (`tests/leak_audit.rs`) — enforced, not asserted

Plan §10 asks for "an explicit leak audit lists every engine field with its
visibility class". A list is a comment, and a comment does not survive a year of
edits, so the audit is mechanical: flip a field in a live battle, re-derive the
seat's 828 floats **from the same tracker**, and check the result against that
field's declared class.

- HIDDEN → the observation must be bit-identical. A difference is a leak.
- VISIBLE → the observation must differ. This is the positive control, and it is
  what stops the audit passing because the harness is inert.

Holding the tracker fixed is the point: everything it carries (reveal order,
revealed moves, observed sleep turns) comes from HISTORY, so what is being asked
is precisely "does the encoder read the hidden byte DIRECTLY?".

**Result: 68 cases, 136 perturbations across both seats (every case fires on
both), 0 leaks, 0 inert controls.**

The first version had 29 cases and 56 perturbations, and a second adversarial
review found it materially incomplete — roughly 28 of ~88 leaf fields, with four
holes that hid plausible leaks. All are now closed; the details are worth
keeping because they are the shape of hole a perturbation audit grows:

1. **No case perturbed a MOVE ID.** Only PP bytes moved. An implementation that
   built the foe's slots from the engine's move ids *while correctly forcing
   `pp = max_pp`* — the likelier half-right version — would leak all four of the
   opponent's moves, which is the single most valuable hidden quantity in gen 1,
   and every case stayed green. Now covered on the foe's live and stored slots,
   with our own live ids as the VISIBLE control.
2. **`Pokemon.stats` and `ActivePokemon.stats` were never perturbed** — ten u16
   fields. The encoder must read the species TABLE, not the engine's computed
   stats; reading the bytes that are right there is the easier mistake, and for
   the foe those stats are hidden. Now covered.
3. **14 of 18 volatile flag bits had no case**, including `Binding` — the
   trickiest read in `track.rs`, since PARTIALLY_TRAPPED is the victim's slot fed
   by the *user's* bit. All 18 are now covered, and Thrash/Rage are covered as a
   discriminating pair: VISIBLE on our own side (they set `trapped`) and HIDDEN
   on the foe's (no slot).
4. **`Side.order[]`, a revealed foe's species/level/status, and the unrevealed
   member's HP** were uncovered; the last would have hidden a `fainted_count`
   that walked all six party slots instead of the revealed ones.

Two structural weaknesses, also fixed:

- **Four hidden counters were tested with their gating flag OFF**, so a leak of
  the form `if vol.thrashing() { encode(attacks) }` passed vacuously. Every
  gated counter now sets its flag in `prepare`.
- **Six cases could silently no-op** and the `checked >= 40` assertion did not
  notice; 58 attempted vs 56 reported meant two unattributed drops. The audit now
  records which cases FIRED and asserts every one did. That assertion
  immediately earned itself twice: it caught `played()` revealing a whole foe
  party (so the unrevealed-member cases tested nothing) and the same-bucket HP
  case finding no alternative at full HP. Both are now set up deterministically
  rather than by search.

The classifier itself is now tested. A passing audit leaves both buckets empty,
so **swapping the two classification arms left every test green**. `run()` is
separated from the case list and a deliberately MISLABELLED pair — the RNG seed
declared VISIBLE, the foe's active species declared HIDDEN — is required to fill
each bucket exactly once.

The fixture gained a live set prior. With `prior: None` everywhere, the
opponent's prior-filled move slots — 188 of the 828 columns — were structurally
zero, so a leak into them could not have moved anything.

Covered as HIDDEN: the RNG seed, `last_damage`, `last_moves`, both sides'
`last_selected_move` / `last_used_move`, the foe's `order[]` bench arrangement,
the foe's live and stored move IDs, the foe's live and stored PP, the foe's and
our own computed stat block, the foe's exact HP *within* one percent bucket, HP
and max scaled together so the percentage is preserved, an unrevealed foe member
(identity and fainting), sleep turns remaining and the Rest/EXT marker, the eight
packed volatile counters each behind its flag, and the eight volatile flags with
no encoder slot (Light Screen, Bide, Mist, MultiHit, Flinch, Invulnerable,
Transform, and the Toxic VOLATILE as distinct from the TOX status).

Covered as VISIBLE: turn, our own exact HP, PP and live move ids, the foe's HP
*across* a bucket, its max HP alone, a revealed foe's species / level / status,
its active species, all six boosts plus our own spe boost, the toxic counter, and
the Substitute / Reflect / Leech Seed / Confusion / Focus Energy / Recharging /
Charging / Binding presence flags.

Light Screen is audited as **HIDDEN on purpose**: it is visible on Showdown but
has no encoder slot (poke-env 0.15.0 cannot parse it), so encoding it anywhere
would be a divergence, not a fix.

A second test proves the audit can fail, and now at the smallest scale that
matters: it leaks the foe's hidden exact HP as a **one-ulp** flip of a real lane
and confirms the same comparison catches it, while the real encoder does not move
for that perturbation. (`differs` compares raw bits, so ulp sensitivity was
always true by construction — but by construction is an argument, not a test.)

**The first run reported 8 leaks, all harness artifacts** — the mutations flipped
a visible FLAG alongside the hidden counter behind it (the confusion bit with
the confusion turns, the SLP bits with the sleep turns). Cases now carry a
`prepare` step applied to BOTH sides of the comparison, so a hidden counter is
tested with its flag already set in both. Worth recording: a perturbation audit
that does not separate "prepare" from "mutate" reports its own construction as a
leak.

## `Gen1Env` / `BatchEnv` (`src/env.rs`) — plan §7.5, §7.6

K battles, two seats, no server, no sockets, no asyncio. Reward is terminal only
and flips with the learner seat; ties (the 1000-turn tie, Endless Battle Clause,
a double KO) score 0, which is the async path's G4c rule. Finished slots restart
immediately with fresh teams and a fresh seed, so episodes are whole by
construction — `episodes_discarded` is 0 the same way.

Seeds follow §7.5: `battle_seed = splitmix64(lane_seed * PHI ^ battle_counter)`,
the team pair drawn at `splitmix64(battle_seed ^ 1)`, and `battle_counter` is
readable and settable so a `--resume` continues the same sequence.

**One design decision the plan did not make.** §7.6 says `step()` "pumps Pass
turns … asking the opponent seat for its choice". It does not. A mid-turn faint
leaves the learner owing a Pass while the opponent replaces its mon, and that
replacement is a real decision belonging to the opponent POLICY — choosing one
inside `step` would quietly install a "first legal choice" bot in the env and
would show up much later as an unexplained strength difference. Instead
`pending()` reports every seat that owes a decision and the caller re-asks, which
is also what keeps opponent inference batched by member (§8.2).

End-to-end smoke, K=64 against the P-3 bank, uniform policy on both seats:

| | |
|---|---|
| episodes | 300 |
| learner rows | 19,679 |
| P1 win / lose / tie | 144 / 155 / 1 |
| mean turns | **61.1** |
| actions outside their own mask | 0 |

Mean turns 61.1 against P-3's independently measured 60.3 on the same bank is the
sanity check that matters here.

**The wall time of that smoke is NOT a throughput number**: uniform policy, no
network forward pass, measured next to three training lanes. T-1 remains out of
scope.

Tests: `a_battle_plays_out_through_the_action_space` drives 40 battles end to end
through the 10-way ACTION space rather than through `Choice`, so the mask, the
action mapping and the Pass handling are exercised together; the mask is checked
never to offer the active or a fainted mon and never to offer a move on a forced
switch; an illegal action is refused with an error rather than reaching the
engine; and the **seat-flip test** plays one identical game from both seats and
asserts the rewards negate. On the Python side, `BatchEnv` is checked for whole
episodes, in-mask actions, observations inside the declared `Box(-1, 4)`, no
stalled slot, and lane-seed reproducibility.

## The tracker review, and the two divergences it found

A third adversarial reviewer was pointed at one question: is `track.rs` CORRECT,
and can that be proved offline? It confirmed the reveal rule, the sleep rule, the
`aliased` precedence, `trapped`/`force_switch`, and the foe-seat slot handling
against Showdown's and poke-env's sources — and found two real divergences plus
the fact that the tracker had **no behavioural tests at all**.

### F1 — a fainted active, on a force-switch row. Material; fixed.

The engine's `faint()` zeroes the whole volatile word and the status byte
(`mechanics.zig:1544-1570`). poke-env's `Pokemon.faint()` clears `_effects` but
**not** `_must_recharge`, `_preparing_move` or `_status_counter` — those clear in
`moved()` and `switch_out()` (`pokemon.py:422-429`, `:465`, `:604`). And on a
force-switch the fainted mon is **still the active**, so `_fill_active` runs on
it: the reviewer measured all 23,086 force-switch requests in the corpus and in
23,086/23,086 `side.pokemon[0]` is both `active: true` and `fnt`.

Force-switch rows are 23,086 of 184,221 decisions = **12.5% of all rows**, and of
66,968 faints the corpus has 2,377 while asleep, 2,953 with a recharge pending
and 270 while preparing — so roughly **1.4% of all rows** would have disagreed on
`vec[214]` (MUST_RECHARGE), `vec[218]` (status_counter) or `vec[219]`
(preparing). P-1 cannot see this by construction: it hands both encoders the same
`ObservableState`.

Fixed by snapshotting `(must_recharge, preparing)` per party index while the mon
is still alive, and by not resetting `sleep_observed` when the sleep ends because
the mon fainted. **Reproducing poke-env's staleness is the point** — I2 is
"bit-for-bit where the information exists", defects included, the same rule that
keeps Light Screen out of the encoder. `a_fainted_active_still_reports_what_poke_env_would`
pins it, including that the six EFFECT-derived volatile slots DO clear (both
sides clear those).

### F2 — a hard lock's action index. Fixed.

On a Thrash / two-turn charge / Rage turn the engine offers exactly `Move(1)` and
`env.rs` mapped it to **action 6**. poke-env does not alias a hard lock — the
locked move is a real member of the move dict — so `get_action_mask` yields
`6 + its stored slot` (`singles_env.py:247-251`). Plan §7.2 says exactly that
("{6+slot(last_selected_move)}") and the first implementation ignored it. If Sky
Attack is the mon's third move, poke-env's legal action is 8 and the port's was
6. Measured: ~100 hard locks in 161,135 move decisions, **0.06%** — small, but
wrong in the worst way, since the single legal action sat in the wrong lane.

This is the first concrete instance of the gap the previous review left open:
P-2 never compares an ENGINE-derived mask to anything. `a_hard_lock_keeps_the_locked_moves_own_action_index`
now covers it for all four stored slots.

### Three smaller ones, also fixed

- **A charge move was revealed one decision late.** `canMove` returns at the
  `.Charge` branch *before* `decrementPP` while still emitting `|move|`
  (`mechanics.zig:758`), so the PP diff sees nothing until the release turn.
  872 `-prepare` events in the corpus, 0.54% of turns; Sky Attack is the only
  charge move in the pool. Now revealed when the Charging bit goes false→true.
- **Transform and Mimic swallowed their own reveal**: both rewrite the slot id in
  the same update that spends its PP, so `id == prev_id` fails. Now revealed on
  the transform bit turning on, and on a live slot id changing.
  All three of these reveal paths read `last_selected_move` as the identity of a
  move the opponent just publicly saw used — the engine's proxy for the `|move|`
  line — and **only ever reveal a move the mon actually owns**, so a
  Metronome-called move cannot be fabricated into its moveset. (That last guard
  was added because the property tests caught it doing exactly that.)
- **`binding_victim_turns` counted UPDATES, not turns**, while §7.2's
  "first trapped turn" rule is in turns; and the `[Fight]` placeholder gate
  omitted SEMI-locks, which PS includes (`sim/pokemon.ts:1089-1108`). Both dead
  in `gen1randombattle` — no binding or Bide move is in the pool — but both
  matter for the search line, and both are cheap.

### F5 — the tracker had no behavioural tests. Now it has property tests.

The tapes cannot be replayed in the engine (no RNG), so there is no direct
oracle. `tests/tracker_properties.rs` instead asserts properties any correct
tracker must satisfy, each reading a DIFFERENT part of the state from the rule it
checks — **300 battles, 32,199 updates, no violations**:

- **cross-seat agreement**, the strongest independent witness available: every
  public fact must read the same from both seats, derived by different code paths
  (own-side vs foe-side). Species, level, fainted, status, is_active, base stats
  and types must agree; the foe's `hp_fraction` must equal the quantisation rule
  exactly and sit within one bucket of the exact fraction; an unrevealed mon must
  be absent from the foe's view entirely; both seats must agree on which mon is
  active. This is what would catch a side-index swap — and the PARTIALLY_TRAPPED
  read, which takes the FOE's Binding bit, is exposed to precisely it.
- **sleep conservation**: `sleep_observed + sleep_turns_left` is invariant while
  one sleep runs down, re-based when the remaining count goes up (a fresh sleep,
  which poke-env does not reset the counter for either). Catches a missed
  increment, a double increment and a missed reset in one assertion.
- **"damaged, statused or PP-spent implies revealed"** — a mon can only reach any
  of those while on the field, and being on the field reveals it. Reads a
  completely different part of the state than the reveal rule, so a skipped
  reveal surfaces the moment that mon takes a point of damage.
- **reveal soundness**: a revealed move must exist on that mon (relaxed for mons
  whose slots Transform or Mimic rewrote).
- **monotonicity**: reveal lists only extend, never reorder or shrink, never
  exceed the caps; counters step by one or reset to zero.

The properties are demonstrably able to fail — they fired three times during
development, twice on reveal soundness and once on sleep conservation. Two of
those were over-strong assertions of mine (a Transform-copied move need not be in
the stored set; sleep can be re-applied), and one was a real tracker bug (the
Metronome-called reveal). That is the pattern to expect from property tests, and
it is why they are worth more than the unit tests they replaced.

## Still open

D-1, T-1 and A-1 are unchanged: out of scope while the fleet runs. The
`EngineCollector` / `train.py` seam (plan §12 step 8) is not built.

Nothing above narrows the P-1 disclosure — the tracker now EXISTS and has
properties, but properties are not an oracle. What still cannot be settled
offline is whether the engine's `choices()` equals the request Showdown would
have sent; that bridge is argued from showdown-mode's definition, and F2 is the
first concrete instance of it producing a wrong number. **That is what D-1 is
for.**

Two documentation corrections fall out:

- **§7.1.1's declared "Struggle slot" family does not exist.**
  `Move.should_be_stored` returns False for poke-env's SPECIAL_MOVES
  (`move.py:151-161`), so poke-env 0.15.0 never puts `struggle` in a move dict.
  The budget line should drop it.
- The reveal families for `gen1randombattle` are, precisely: **Mirror Move
  (4 species), Mimic (5), Transform (1)** — Metronome is 0 species, so §7.1.1's
  "Metronome / Mirror Move" should read Mirror Move alone.

Not fixed, recorded: `state_for` builds the entire `ObservableState` for both
seats just to read `aliased`, and `mask_for` issues ten separate `choices()` FFI
calls per seat per step — roughly three full state builds and ~20 FFI calls per
decision. That is a T-1 concern and T-1 is out of scope.

## D25 opponent-action labels: two bugs in the `(kind, id, flags)` seam

Found by reading `rl/envs/showdown.py::_order_identity` against `src/env.rs`
while scoping the training seam; both were SILENT — `canonicalise` has no
assertion either one could trip.

1. **The id was the choice's DATA FIELD, not the entity.** `_order_identity`
   emits `_move_id(move)` / `_species_id(species)` — the encoder's own id space,
   1..165 and 1..151. `env.rs` emitted `Choice::Move(d)`/`Choice::Switch(d)`'s
   `d`, a slot in 1..=4 / 1..=6. `canonicalise` matches the id against the row's
   OWN opponent-move id suffix, so a slot index simply fails to match and the
   row lands in OTHER_MOVE. Measured: 76.6% of valid move rows canonicalise to a
   real slot after the fix, 0.0% under a control that reproduces the bug.

   Three sub-cases the naive "look the slot up" fix would still get wrong, all
   from `mechanics.zig::choices`:

   | engine | Showdown's request | `_move_id` |
   |---|---|---|
   | `Move(0)` (no selectable move, or Bide with none) | `Struggle` | 165 |
   | `Move(1)` under `isForced` | `Recharge` if recharging, else THE LOCKED MOVE | 0 / `last_selected_move` |
   | aliased turn (sleep / freeze / first turn bound) | `Fight` | 0 |

   `Move(1)` under a lock is `@intFromBool(showdown)` (`mechanics.zig:3178`), a
   "no slot was offered" marker — reading it as stored slot 1 mislabels every
   lock outside slot 0 as Pound. This is the same marker F2 got wrong on the
   action index; the two are independent reads of it.

2. **A foe that owed no decision was marked PRESENT.** `_OPP_CHOICE_NONE` is
   `(-1, -1, 0)` and poke-env reaches it via `clear_choice` before every inner
   step (B2). `env.rs` set `flags = 1 | aliased<<1` unconditionally, so a wait
   turn produced `(-1, -1, 1)`: `canonicalise` sees PRESENT, fails to match id
   -1 against any slot, falls through to OTHER_MOVE — which is ALWAYS legal —
   and trains on a decision that never happened. Measured 6.04% of learner rows
   are wait turns, against the reference's independently measured 6.4% of raw
   steps vs max_power.

Tests: `src/env.rs` gained three (a lock's label names its own move; a switch
label names a live bench member's SPECIES through the `order[]` indirection; and
a 60-battle property run asserting every label names something the seat was
offered, the sentinel is whole, and the id distribution is not slot-shaped).
All three FAIL on the pre-fix code with the right diagnostics. `tests/
test_engine_d25.py` runs the REAL `rl.networks.opp_action.canonicalise` over
25,669 engine rows:

| stat | engine | reference |
|---|---|---|
| `aux/illegal_label_frac` | 0.0000 | 0.0000 on all five tapes |
| `aux/aliased_frac` | 0.0981 | 0.040–0.103 across five tapes |
| `aux/label_present_frac` | 0.9396 | 6.4% wait turns measured vs max_power |
| `aux/frame_collision_frac` | 0.0000 | — |
| slotted share of valid move rows | 0.766 | — (control: 0.000) |

`aux/switch_frac` is 0.432 here against the tapes' 0.0719 and that is EXPECTED,
not a divergence: this run is uniform-random on both seats and 6 of the 10
actions are switches. It is not evidence either way.

## Step 8: the training seam (`collector.mode: engine`)

Built, unit-tested, NOT RUN as a training lane — the 12M smoke needs the server
(and the box). Nothing here is licensed; A-1 has not run.

| piece | where |
|---|---|
| `EngineCollector` | `rl/envs/engine_collector.py` — the `_async_loop` seam verbatim: `seam.version/requests/inference_seconds`, `start`, `poll`, `check`, `pause`, `resume`, `run_in_loop`, `stats`, `close` |
| episode adapter | `EngineCollector._episode` — Rust dict -> `EPISODE_KEYS`, with `rewards` zeros + terminal outcome (ties 0, G4c) |
| opponent loop | `SnapshotPool.select` per BATTLE at slot restart, `AgentOpponent.move_batch` grouped by member, `pool.report` at finish |
| launch validation | `rl/train.py::_engine_collector_checks`, strict key set `{mode, k, team_bank, learner_seat}` |
| metadata | `engine_metadata()` -> `meta["engine"]`: engine sha, PKMN_OPTIONS, zig, crate, bank sha256/pairs/PS commit, tables fingerprint |
| resume | `battle_counter` in `checkpoint.pt`'s `loop` entry |
| bank reader | moved to `rl/envs/engine_bank.py`; `scripts/engine_team_bank.py` re-exports it |

Three things the plan did not say, found by building it:

1. **`battle_counter` must be a CONSTRUCTOR argument, not just a setter.**
   `BatchEnv::new` draws the k battles in flight, so a resumed lane that set
   the counter afterwards still replayed the run's first k battles — same
   seeds, same teams, silently. Caught by
   `test_a_resumed_lane_does_not_replay_its_first_battles`, which failed 8/24
   before the fix. `_async_loop` now reads `resume_state` before constructing
   the collector.
2. **An episode must name its slot.** The opponent is drawn per BATTLE, so the
   collector has to seat a member on the slot that just restarted; `Episode`
   gained `slot`, set at restart.
3. **`AgentOpponent.move_batch`** is the batched-by-member act path. Its
   generator STREAM differs from B separate `move()` calls (one multinomial
   over (B, A) consumes the generator once), so an engine battle does not
   replay a server battle row for row — documented at the method. The contract
   that matters (a member draws from its OWN generator, never the global
   stream) is intact.

Also: `_async_collector_mode` now returns the MODE (`'sync'`/`'async'`/
`'engine'`) rather than a bool, and a key belonging to another mode is refused
by name ("collector.k is engine-only") rather than as an unknown key.

Tests: `tests/test_engine_collector.py` (3) drives the real `PPOAgent`, the
real `SnapshotPool` and the real `EpisodeDataset` end to end — 3,000 rows into
`update_episodes` with the D25 aux head on, weights move, `episodes_discarded`
0; a per-battle member draw credited exactly one game per finish; and the
resume property above. `tests/test_async_launch.py` gained 16 engine-mode
validation cases.

## In-engine scripted opponents + the single-battle env (plan §8.2, §8.3)

`src/scripted.rs` ports three poke-env players. They read the OBSERVABLE state
(`ObservableState`), never the engine's 384 bytes — a scripted opponent that
cheated would make D-1 compare two different games and make any in-engine eval
number meaningless.

| policy | rule ported from |
|---|---|
| `random` | `Player.choose_random_singles_move` — uniform over moves ∪ switches, which is exactly the mask's true entries (proved at P-2) |
| `max_power` | `MaxBasePowerPlayer.choose_singles_move` — a move whenever one is legal (NEVER a voluntary switch), else a random switch |
| `most_damage_typed` | `rl/envs/most_damage_typed.py` (Huang & Lee) — base power × effectiveness, OHKO at 120, ties uniform; forced switch minimises the summed weakness |

`SimpleHeuristicsPlayer` is NOT ported and the env REFUSES `opponent:
"heuristics"` by name. It reads poke-env `Battle` objects; an in-engine version
would be a different bot with the same name, and the locked protocol's
denominator would silently change.

**One porting bug the tests caught: Rust's `max_by_key` keeps the LAST maximum
where Python's `max` keeps the FIRST.** `max_power` therefore picked the
highest stored slot among tied base powers instead of the lowest —
`available_moves` is in stored-slot order, so poke-env's tie goes to the lowest
slot. Fixed by making the slot part of the key.

`MoveEntry` gained an `ohko` flag (poke-env reports base power 0 for Fissure /
Horn Drill / Guillotine, and H&L score them at 120). It is deliberately OUTSIDE
the tables fingerprint: the fingerprint pins what produced the OBSERVATIONS,
and `ohko` enters no encoder field.

`rl/envs/engine_env.py` (`ShowdownEngine-v0`) is a thin `BatchEnv(k=1)` wrapper
so `evaluate()` and harness tests run with no server. It pumps the opponent's
forced-replacement turns rather than returning them as learner rows with a
placeholder action — the sync path's wait-state absorption, and the one place
the env differs from the collector (which has other slots to work on instead of
waiting). Consecutive resets advance the battle counter, so an eval sees
different team pairs rather than one pair repeatedly.

Sanity ladder, 300 battles each (DESCRIPTIVE, not licensed, in-engine only):
random-vs-random 0.35–0.65 as a symmetry guard, max_power vs random > 0.85,
most_damage_typed_engine vs random > 0.85, and **most_damage_typed_engine vs
max_power > 0.55** — the type chart is the only difference between those two,
which is why JOURNEY's anchor is the typed one.

### The naming rule (a safety property, added after review)

`random` and `max_power` keep poke-env's names ON PURPOSE: D-1 plays the
engine's under that name against the server's under the same name, and "same
rule, two simulators" is exactly the comparison — a divergence there is what the
gate exists to FIND, and it is found, not hidden, by the shared name.

The in-engine typed bot is `most_damage_typed_engine`, and the bare
`most_damage_typed` is REFUSED by name. The reason is not tidiness:
`OPPONENT_PLAYERS["most_damage_typed"]` already means one specific thing
project-wide — the SERVER anchor, whose h2h at 500 battles is a REPORTED ROW in
the gen-1 and gen-4 anchor batteries (CLAUDE.md). There is no engine-vs-server
comparison for it to earn the shared name with, so sharing it buys nothing and
risks an in-engine number landing in a battery row. Such a number would be wrong
twice over: the port could have drifted, and the in-engine game has not passed
D-1.

`heuristics` / `simple_heuristics` are refused the same way and always will be.
SH is the VERDICT DENOMINATOR for every banked number in this project; a port
that differed anywhere would redefine it with no error surfacing anywhere. The
information for a gen-1 SH port is nearly all present (`ObservableState` carries
types, base stats, HP fractions, boosts and faint counts on both sides; only the
active's computed atk/spa, `move.expected_hits` and per-stat `move.boosts` are
missing, and the hazard/dynamax/tera branches are dead in gen 1) — feasibility
was never the objection. The one thing that would justify it is paired
evaluation with common random numbers (plan §8.4), and that needs its own
pre-reg AND its own parity gate: the ported SH's action against the real SH's,
decision for decision on tape states, the way P-2 gated the mask.

Both refusals name where the real one lives instead of saying "unknown policy",
so a misattributed number needs a deliberate rename rather than a typo. Pinned
by `scripted::tests::the_anchors_bare_name_is_refused_with_a_pointer_to_the_server_one`
and by `tests/test_engine_scripted.py::test_the_anchors_are_refused_by_name_not_faked_or_called_unknown`,
which checks both the Python and the Rust surface.

Evidence that this class of bug is real and not hypothetical: porting
`MaxBasePowerPlayer` — nine lines — shipped a tie-break divergence in this same
session, because Rust's `max_by_key` keeps the LAST maximum where Python's `max`
keeps the first. SH is roughly fifty times that surface.

## Gate harnesses written but NOT RUN: D-1 and T-1

Both are MEASUREMENTS and the box has a fleet on it, so both were written and
tested and neither was run. The point of writing them now is that when the box
frees they fire the same day instead of starting cold.

**`scripts/engine_d1.py`** — engine vs server dynamics. Three legs
(`--leg engine|server|compare`). The engine leg is complete and its plumbing is
verified; **the server leg is deliberately a `SystemExit` with the four
implementation steps and the two CLAUDE.md traps (`/timer on`, distinct
usernames) written into its docstring** — it needs a server, which this session
may not start. Bands restated verbatim in the file: P1 win rate |Δ| < 0.02, tie
rate |Δ| < 0.005, mean turns |Δ| < 5%.

The engine leg runs entirely in Rust (`scripted_series`), so a 10,000-battle leg
costs no Python, and it derives battle seeds and team pairs exactly as `BatchEnv`
does — a D-1 leg plays the battles a collector lane at the same seed would.

Two design points found while writing it:

* **The status scan must cover the WHOLE PARTY at every decision point AND once
  after the final update.** Checking only the active mon before each step misses
  a status applied on the killing turn, and misses a mon slept then switched
  out — while the server leg, reading `|-status|` off the log, misses neither.
  That asymmetry would have read as a phantom mechanic difference.
* **Both matchups are load-bearing.** Measured on 200 engine battles:
  `max_power` vs `max_power` gives sleep 0.000 / freeze 0.370 / 21.3 turns,
  `random` vs `random` gives sleep 0.765 / freeze 0.190 / 60.6 turns. max_power
  never selects a 0-base-power move, so it cannot exercise sleep at all; the
  random matchup is the only one that tests gen 1's sleep mechanic, which is the
  likeliest thing to differ between the engine's patched-PS target and PS
  0.11.11.

**`scripts/engine_t1.py`** — legs (a) engine-only battles/s, (b)
collection-only steps/s across K ∈ {32,64,128,256,512} at the 100M trunk with a
20-member pool, (c) full-loop `time/realized_steps_per_sec` read out of a run's
own `history.csv` (never re-derived, and never `time/steps_per_sec`, which is
the poll-cadence estimator). Bands 20k / 25k@K=256 / 2,000, with "if (c) <
1,500: PROFILE, and the plan's §0 numbers get corrected in place" in the file.

**Both refuse to start on a busy box** (`pgrep` for `rl.train` and
`node pokemon-showdown`); `--force` records `contended: true` rather than a
clean number. Verified: both refused today.

`tests/test_engine_gate_harnesses.py` (12) tests everything that would
otherwise only run on gate day — the guard, the summary shape, and each band
firing on its OWN read and not on its neighbours' (a gate that fails everything
at once localises nothing).

Also added: **`requirements-engine.txt`**. The engine deps stay OUT of
`pyproject.toml` on purpose — a sync or async run never imports `pkmn_gen1`, and
a checkout with no Rust/Zig toolchain must stay installable.

## Sweep, 2026-09-07: what the branch was still missing

### An engine lane is NOT server-free — plan §0 corrected

The plan's §0 says "engine lanes need no server, no accounts, no `/timer on`,
no orphaned-room deadlock". That is true of COLLECTION and **false of a LANE**.
`make_eval_env` builds a `Showdown-v0`, and `ShowdownEnv.__init__` constructs
`ShowdownSingles`, whose poke-env players connect at CONSTRUCTION — so every
engine lane holds two seats for its whole life, not just during an eval.

Three consequences that change how a fleet is planned, now written into the
plan:

* **CLAUDE.md rule 2 still applies to engine lanes.** Concurrent lanes need
  distinct `--seed`s or the seats collide on usernames and a lane dies with a
  misleading `TimeoutError`. "No server for collection" is not "no server".
* `/timer on` and the orphaned-room deadlock still apply to those seats.
* The server must be UP AT LAUNCH, not merely by the first eval.

The width argument survives and gets stronger — 8 lanes put 16 mostly-idle
seats on the server instead of 8 × K battling ones — but §0's sentence was not
one to plan a fleet on.

### The plan itself, corrected in place (brief §5)

Nine corrections, each marked with its date and the gate that found it, and
each STRIKING the wrong text rather than quietly rewriting it: §0 (above), §4.3
(`pyo3/extension-module` is maturin-only), §4.4 (rpath + `-j2` inside build.rs),
§4.5 (`requirements-engine.txt`, the stale-`.so` landmine), §6.2 (the bank's
unit is a battle), §7.1.1 (Metronome is not in the randbats pool, so the family
is Mirror Move alone), §7.2 (the Transform family does not exist; three rows
unreachable in this format), §7.5 (**wait-pumping REVERSED** — pumping installs
a first-legal-choice bot in place of the pool member; and `battle_counter` is a
constructor argument), §8.1 (the strict key set, the mode string, the
server-at-launch fact), §8.2 (the naming rule), §9 (the P-1/P-2 family rows).
Grep the plan for `IN PLACE` to find them all.

### Three robustness gaps closed

1. **`check()` had never been exercised.** Now tested both ways, and the test
   documents why the default bound is `Gen1Env`'s own per-battle ceiling: at
   K=1 the collector's "steps since a finish" and a battle's update count are
   the same quantity, so the two bounds coincide, which is the right
   coincidence.
2. **A pool member evicted mid-battle** was untested. It works, and for a
   reason worth stating: the collector holds the member OBJECT, not its push
   id, so `SnapshotPool.report`'s identity match silently credits nothing —
   holding the id would credit whichever member later occupied that list slot.
3. **The D25 pair is now refused at LAUNCH.** PPO refuses a mismatched
   `opp_action` / `aux_oppact_coef` pair, but only at the first update, a whole
   rollout in.

### One thing deliberately left as-is, documented rather than "fixed"

**A resume restarts the pool's member-selection stream.** F-18 restores the
global torch/numpy/random streams; `EngineCollector._rng` is private, so a
resumed lane re-draws members from the sequence's start. That MATCHES the env
path (its per-sub-env episode RNGs are re-created on resume too) and it is
harmless where `battle_counter` was not: member selection is iid 80/20 draws
from the same pool, so restarting changes WHICH member plays a given battle but
not the distribution. A restarted BATTLE sequence replays battles; a restarted
selection stream does not. Recorded at the field rather than silently differing
from the env path.

## The second sweep (one opus subagent + my own), 2026-09-07

The subagent's headline finding is the important one and it was MINE to make:

### `collector.mode: engine` was UNLAUNCHABLE. Fixed.

`_engine_collector_checks` required `cfg.selfplay["enabled"]`, and **`enabled`
is not a legal selfplay key**. `selfplay_env_kwargs` (`rl/envs/make.py:103-110`)
fixes the known set and raises on anything else, and `train()` calls it at
`:447` — BEFORE `_async_collector_mode` at `:508`. So without the key the engine
check raised, and with it `selfplay_env_kwargs` raised first. **No config could
satisfy both.**

Why sixteen validation cases missed it: every one of them called
`_async_collector_mode` **in isolation**, and the fixture did
`setdefault("selfplay", {"enabled": True})` — so the test suite ENCODED THE BUG
AS THE EXPECTED SHAPE. A validator tested apart from the order it runs in is
not tested.

Fixed by reading the predicate `train()` already uses (`selfplay.opponent ==
"self"`, the same one the D25 purity seam reads at `:458`) rather than by adding
a key to `make.py` — a new selfplay key would persist into `config.yaml` and
`ckpt["config"]`, and nine eval sites route through `selfplay_env_kwargs`. Two
new tests: one that runs the two validators **in `train()`'s order**, and one
that greps `_engine_collector_checks` for every `cfg.selfplay.get(...)` key it
reads and asserts each is one the validator accepts — so the class of bug cannot
return.

### The empty-poll sleep was a pure stall on this path, and it corrupted T-1(b)

`_async_loop` slept 20 ms after a poll that returned nothing. Correct for
`AsyncCollector` (its work happens on POKE_LOOP, so an empty poll means "nothing
has finished yet"); wrong here, because **every engine poll DOES a batched
step** — an empty poll is a step that finished no battle.

It bites hardest exactly where the plan wants a K chosen. At ~67 engine updates
per battle a poll finishes one with probability ~K/67:

| K | P(empty poll) | sleep per 30,720-step rollout |
|---|---|---|
| 256 | ~2% | 0.05 s |
| 128 | ~15% | 0.7 s |
| 64 | ~38% | **3.8 s** |
| 32 | ~62% | **12.1 s** |

against the plan's ~1 s projected collection. The default K=256 is fine, which
is why nothing would have caught it — but **T-1 leg (b) sweeps K ∈ {32…512} and
drives `poll()` bare**, so it would have published a clean K=32 number no lane
could reach: a measurement/production mismatch inside the gate itself.

Fixed with a collector-declared `idle_sleep` (0.0 here, 0.02 by default for the
async path), and leg (b) now records `empty_poll_fraction` per K and REFUSES to
publish if the collector declares a sleep the leg did not take.

### Five silent zero-fallbacks removed

`PyArray2::from_vec2(...).unwrap_or_else(|_| PyArray2::zeros(...))` at five
sites. `from_vec2` fails exactly when the flat buffer is not a whole number of
rows — the signature of an episode-buffer length bug — and the fallback handed
back an **all-zero observation of the correct declared shape** to train on, or
an **all-False mask** that sends every logit to the −1e8 sentinel. Replaced by
one `rows2` helper that errors, plus a row-count agreement check in `pending()`
so a caller can never zip one slot's obs with another's mask.

### Two guards added

* **Launch preflight.** `pkmn_gen1.verify()` now runs on the training path.
  `build_info()` only RECORDS what is loaded, including a stale extension; the
  stale-editable-install trap already cost a cycle at P-1 and nothing guarded a
  launch. (The encoder-width half is a BACKSTOP, not the primary guard —
  `EntityDeepSetsNet` already refuses at agent construction naming both flags,
  which is earlier and better. It covers `trunk: mlp`, where nothing compares
  the two widths. Recorded that way rather than claiming more.)
* **A resume re-verifies the engine block.** `ckpt["config"] == asdict(cfg)`
  catches a changed `team_bank` PATH but not a different bank at the same path
  (`read_bank` validates against the payload's own sha256, so a
  swapped-but-valid bank passes), a rebuilt extension at a different engine sha,
  or a tables fingerprint moved by a poke-env upgrade. All three silently change
  the game mid-run. Now refused, in the shape of `_ensure_theta0`.

### Recorded, not acted on

* **Three A-1 R0 gates cannot fail on this path.** `episodes_discarded`,
  `rerequests` are literal `0` and `battles_in_flight`/`rooms_tracked` are the
  constant k (`pyencode.rs`). They are live counters on the async path, which is
  why the gates were worth stating there. **The A-1 header must not restate
  gates that cannot fire** — drop them with a stated reason or replace them with
  something this path can violate (mask-legality errors and `Outcome::Error`
  both raise, so both qualify). This is pre-reg text, which is not agent work.
* **Any encoder change now costs two implementations plus a P-1 re-run.**
  `encoder.rs` hard-pins `OBS_DIM == 828` at compile time, so IDEAS 4.6, 2.7 and
  — importantly — **JOURNEY step 8's gen-4 encoder rewrite back-ported to gen 1,
  the very next step after 7.5** — must land in `rl/envs/showdown.py` AND
  `engine/pkmn_gen1/src/encoder.rs` AND `rl/envs/engine_tables.py`, with P-1
  re-run to re-establish bitwise parity. Plan §12's 12-16 block estimate does
  not include this recurring cost.
* **IDEAS 4.4 (H&L 5-term shaping) needs a different engine BUILD, not a knob.**
  `hl_shaping` sums Showdown PROTOCOL events, and the engine is built
  `-Dlog=false`. A `debug-log` feature exists but a protocol decoder does not,
  and a log build is a different artifact needing its own B-0. Nothing prices
  this. 4.4 is last-ranked and gated on 4.1/4.3/4.5 nulling, so: recorded, not
  built.
* **IDEAS 2.2 (the seed-sharing run tag) is still required.** The per-battle
  seed makes the BATTLE STREAM pairable, not the LAUNCH: two engine arms at the
  same `--seed` still collide on eval-env usernames. This is the same
  server-at-launch fact as above, and it means the pairing prize the 7.5 case
  rests on is gated on 2.2, which is Tier-0 instrument work needing no pre-reg.
* **Artifact compatibility: no gaps.** Independently swept — `eval_checkpoint.py`
  rebuilds from `ckpt["config"]` and never reads `cfg.collector`; `ladder.py`
  needs only the checkpoint, its sha and the encoder flags; `extract_history.py`
  takes a per-file key union so the two extra `collect/*` columns just appear;
  `meta.yaml` readers ignore the new `engine` block and
  `tests/test_run_capture.py` asserts a subset. Nothing outside `rl/train.py`
  reads `cfg.collector`.
* **In-loop eval costs less than the plan says.** Measured on
  `runs/showdown_sp_100m_s104/history.csv`: `time/eval_sec` mean **5.31 s** over
  400 evals, not plan §8.3's "~26 s". At the projected 2,350 steps/s and
  `eval_every 250000` that is ~4.8% of lane wall (up from ~1.2% today).

## 2026-09-08: the first engine config, and D-1's server leg

Written under a no-heavy-runs discipline — the 50M fleet was at ~48M with its
8 h eval chain due in ~2.5 h, and an eval is more sensitive to contention than
training. Rust unit tests (0.2 s) ran; the expensive Python suites (~2 min of
real PPO plus K engine battles each) were deferred. **What that means for this
entry is stated per item.**

### `configs/engine_smoke.yaml` — a SMOKE, not a pre-reg

Nothing on disk had `mode: engine`, so the first lane had to be invented at the
command line. This follows the `gen4_smoke_heur.yaml` precedent (a smoke needs
no ruling), names `journey_step: 7.5`, restates A-1's exit condition, and says
outright that it reads no band and produces no quotable number.

Three choices worth recording:

* **Seed 9300.** The 9xxx band is this repo's smoke band (9001/9002/9004/
  9100-9102) and 9300 is clear of every reserved pre-reg window — 66-90 (ch5
  R2), 104-127 (100M), 200-247 (gen4). A stamped run dir inside one of those
  turns the OWNING prereg's test red, which is how a smoke breaks someone
  else's suite without touching their files. The test checks the whole sub-env
  window `[seed, seed+num_envs)`, not just the base.
* **The 100M agent block verbatim.** A `[64, 64]` smoke would prove the seam
  and hide every batching question T-1 exists to answer — the by-member
  opponent forwards are where the GEMV/GEMM anomaly lives.
* **The header says it still needs a server**, with CLAUDE.md rule 2 restated,
  because "engine lanes need no server" is the sentence most likely to be
  remembered wrongly.

VERIFIED: the config loads and passes `selfplay_env_kwargs` → 
`_async_collector_mode` in `train()`'s real order. That is also the end-to-end
proof the unlaunchable bug is fixed — on a real config rather than a fixture.
NOT VERIFIED: it has never been launched (needs a server, and the box is busy).

### D-1's server leg — written, NEVER RUN

The plan's own band arithmetic settled a design question the earlier draft got
wrong. §9 says "se ~ 0.007 at n=10,000", which is the se of a **difference of
two independent proportions** (√(2×0.25/10000) = 0.00707) — so D-1 intends
INDEPENDENT draws, and the earlier docstring's scheme of feeding the bank's
pairs to the server through `gen1customgame` would have changed the FORMAT to
buy a pairing the gate never asked for. Both legs now play
`gen1randombattle` distributions from the same generator: the engine reads the
bank, which our Showdown at `59da482e` produced, and the server draws live from
that same checkout. The generator is common; only the simulator differs.

Disclosed, not fixed: the engine leg samples 10,000 battles from a 50,000-pair
bank so a few pairs recur (each with a fresh battle seed), while the server
draws fresh. Same distribution, different finite-sample structure, far below
the bands.

The subtle part is the sleep/freeze read, because an instrument asymmetry there
would look exactly like a mechanic difference. The engine leg scans every party
member at every decision point AND once after the final update; the server leg
now mixes a `_DynamicsProbe` into the registry player that scans both teams at
every `choose_move` and once when the battle finishes. Coverage matches despite
`opponent_team` holding only revealed mons — a mon can only be slept or frozen
while active, and an active mon is revealed. Outcomes go through the repo's own
`battle_outcome`, not a local reading of `battle.won`.

Ops, from CLAUDE.md's landmines: the poke-env ORIGINALS play (running our port
against itself would prove nothing), every seat sends `/timer on`, usernames
are explicit and distinct, and each chunk gets a FRESH SEAT PAIR so a resume
never reuses a killed arm's poisoned pair. Progress prints as s/battle.

**VERIFIED: none of the server path.** It has never touched a live server. The
row assembly, the outcome convention, the sleep-before-KO semantics and the
both-seats union ARE tested offline against stubs — that is where a silent
asymmetry against the engine leg would live. The connection, challenge loop and
chunk/resume path are unverified; `result["unverified"]` says so in the
artifact itself, and the first run is a bring-up, not the gate.

## IDEAS 2.2 — the seed-sharing run tag. BUILT.

IDEAS calls this "BUILD IT (few lines + a test)" and Tier-0 instrument work, so
it needs no pre-reg. It matters here because the port does NOT make paired
training seeds free: the per-battle seed pairs the BATTLE STREAM, not the
LAUNCH, and two engine arms at the same `--seed` still collided on eval-env
usernames (IDEAS §1's own note says the tag "matters only for concurrent
same-seed arms" — which is exactly the engine case).

`rl/envs/showdown.py::seat_names(seed, tag, role)`, used by both collectors.

Four design points:

1. **Off by default, byte-identical.** With no tag the names are
   `as2s{seed}a/b`, what the async collector has always used. No existing run's
   wire moves, so this cannot perturb a resume of anything already launched.
2. **It rides `env_kwargs`, not a new `Config` field.** A new field would break
   `ckpt["config"] == asdict(cfg)` for every run launched before it existed and
   REFUSE THEIR RESUMES — including the live fleet's lanes. `env_kwargs` is the
   existing per-run env-knob channel, and `seat_tag` is now in the strict
   accepted set on both the async and engine paths (a typo is still refused).
3. **`make_env` resolves it, not the env.** That is the only place holding the
   PER-SUB-ENV seed (`make_vec_env` passes `seed + i`), which is what makes each
   sub-env's pair distinct — and it is why the pre-reg guards reserve
   `[seed, seed+num_envs)` in the first place. The tag is popped there and never
   reaches the env constructor.
4. **A `role` separates train from eval.** Both are built at `cfg.seed`, so with
   explicit names the eval env would collide with training sub-env 0. Today's
   random derivation avoids that only because poke-env draws a fresh name per
   construction — an accident this replaces with a reason.

Refused rather than truncated: a seed large enough to push the name past
Showdown's 18-character cap raises, because a silently truncated name collides
with its neighbour — the exact failure the tag exists to prevent.

**No variance claim is made.** IDEAS is explicit that CH3 R4's paired-clustered
se of 0.0080 was same-checkpoint EVAL pairing, while training-seed pairing
cancels only what stays correlated through chaotic decorrelation, with rho
UNKNOWN. It is weakly dominant (rho ~ 0 means no worse than unpaired). **rho
must be measured and reported on first use** — recorded at the helper itself so
the obligation travels with the code.

Owed at merge: IDEAS 2.2 also asks that the pre-reg seed guards be extended to
tags. Those live in `tests/test_*_prereg.py`, which this branch may not edit;
`tests/test_seat_tag.py` records the contract they would assert so the extension
is mechanical.

## D18's privileged block: the EMITTER, built. The seam, deliberately not.

Plan §8.4 lists the privileged block as something the engine path makes cheap
later, and IDEAS ranks the arm (4.7) fourth. Mechanism is not an arm — the same
status 4.1 had when it was built for gen 4 — so the emitter is buildable now and
the arm still needs its own pre-reg.

**Built and verified:** `encoder.rs::privileged_block` (the same SLICE the
Python takes: own-side blocks, then 6 own species ids and 4 own move ids from
the id suffix, never the opponent's), and `Gen1Env`'s `privileged` flag, which
fills one block per learner row from a full encode of THE FOE'S SEAT, read
BEFORE the update so it describes the state the action was chosen in. The Rust
test rebuilds the expected block independently rather than re-running the
implementation, so slicing our own vector, or reading the foe after the update,
fails it. A second test pins that the block is empty when the flag is off.

Two guards against the drift that is actually coming — JOURNEY step 8's encoder
rewrite is the very NEXT step after 7.5, so both implementations are about to
move: `encoder.rs` asserts `PRIV_OWN_END == 404` and `PRIV_DIM == 408` at
COMPILE time, and a Python test asserts those constants equal
`rl/envs/showdown.py`'s. A shifted slice would otherwise reach the critic with
no error anywhere.

**Deliberately NOT built: the seam into PPO, and the lifted refusal.**
`_engine_collector_checks` still refuses `privileged_dim`, with a message that
now says the emitter exists and the seam does not. Half-wiring it would let
someone configure a wide critic that trains on zeros — the exact failure the
original refusal named.

**A plan claim that expires here.** Plan §12 waves through the block's cost —
a SECOND full 828 encode per learner row, half of it discarded — on the grounds
that "the collection loop is I/O-dominated". That is true of the server path and
false of this one, which is the whole point of the port. Hence the flag is
opt-in and off by default: off it costs nothing, and T-1 should price it before
an arm relies on it. Recorded rather than optimised, because optimising it means
a partial encode path and D18's design deliberately chose a SLICE over a new
fill path so the semantics cannot drift.

## The team bank A-1 must use, and how to rebuild it

The bank is gitignored, so a merge to `main` leaves it unreproducible unless
this is written down. **Every A-1 lane must use the same file**, because its
sha256 is what `meta["engine"]["team_bank_sha256"]` pins and what a resume
re-verifies.

| field | value |
|---|---|
| file | `data/engine/teams_59da482e_e0e0_50000.bin` (4,800,260 B, built 2026-09-06) |
| sha256 | `4f2b8737a3a5aba3989fd7fb140add7cb5e103a7e989c3d802974c10dd124ca2` |
| pairs | 50,000 (a pair = one BATTLE: two teams from one generator) |
| PS commit | `59da482eabc87245eb62313593e468e81ca537d9` — the ladder's own pin |
| generator seed prefix | `e0e0` |
| engine sha at build | `9b88fd6c5467f703c38951d5b2e8a660314d410b` |

Rebuild (needs the `showdown/` checkout at that commit; starts NO server):

    python scripts/engine_team_bank.py --pairs 50000 --out data/engine/

**Why 50,000, recorded because nobody had written it down.** A 100M-step lane
plays ~1.5M battles, so each pair recurs ~30 times — with a FRESH battle seed
every time, so the rolls differ even when the teams repeat. The pairs are a
correct iid sample from PS's own generator, so the recurrence adds no bias to
the team distribution; what it does is make the team draw slightly
lower-variance than a truly fresh draw per battle. Far below anything A-1's
bands read, and gate P-3 verified the marginals against
`rl/envs/randbats_prior.py` by χ² at n=100k. If a later run wants a fresh draw
per battle, the bank is cheap to regenerate larger — the constraint is disk
(96 B per pair), not correctness.

## 2026-09-09 — pre-launch smoke, and what it caught

The gen-4 chapter closed (`POST-FLEET DONE`, pooled vs-SH 0.8788, M-YES,
S5-MATCHED) and the maintainer released the box. Before committing the gate
chain I smoked the engine training loop, which was worth doing.

**The box was not literally free.** An idle Showdown server left from the gen-4
chapter (543 min cumulative CPU, ZERO delta over 10 s), a leftover idle shell
from that chapter's launcher, and `caffeinate`. The shell and `caffeinate` were
left alone. The server was restarted — deliberately, recorded in the pre-reg's
`launch_authorization` block, because the chapter that started it is closed and
D-1 wants a fresh instrument anyway.

**The stale server was breaking the eval path.** The first smoke threw
`websockets ConnectionClosedError: no close frame received or sent` on BOTH eval
seats ~43 s in. Collection was unaffected (the engine needs no server) and the
lane kept training, so this is a shape that would have quietly cost P-AUC its
48 rungs rather than killing a lane. On a FRESH server the same smoke ran with
**zero** connection errors and logged `eval/win_rate`. The chain restarts the
server before D-1 and before A-1, so it is covered by design — but the failure
mode is worth knowing: an eval-seat drop does not kill an engine lane.

**Measured, solo, single lane, engine collector, 100M recipe width:**
step 247,537 in ~180 s = **~1,375 steps/s**. Against the Node async fleet's
realized 574 steps/s/lane 3-wide, that is ~2.4x on a solo-vs-3-wide comparison,
which is NOT a like-for-like number and is not quotable as a speedup — T-1 (c)
and (d) exist to replace it. Recording it only as evidence the loop runs at a
plausible rate. It is well short of the plan's 4.2x projection.

**Resume works on the engine path:** `--resume` continued 247,537 -> 370,835
and crossed an eval boundary cleanly.

**Three defects the launch attempt found in my own runner**, all fixed before
launch: the RAM preflight assumed a 4096-byte page (this box reports 16384, so
it read 2 GB against a 6 GB floor and refused a box with ~10 GB free); the chain
was not actually detached, since it asked an operator to start and stop the
server between steps; and D-1's SERVER leg needs `--bank` (`engine_d1.py:410`),
which the runner did not pass — it would have died at step 2.

**Bank generation is much faster than NOTES had recorded:** 5,000 pairs in
2.44 s = **2,049 pairs/s**, so the 5,000,000-pair bank is ~41 min, not the
~2.75 h implied by the earlier "99 s per 50,000" (that figure was measured under
fleet contention). This is what made RW-6's 5M ruling cheap.

## P-1b — giving `track.rs` an oracle (designed 2026-09-09, not yet built)

**The problem, stated exactly.** P-1 rebuilds the engine-side observable state
*from poke-env's own `Battle`* and then compares encoders. So it answers only
"given identical observable state, do the two encoders agree?" — `track.rs`,
the engine→observable projection, is never exercised. Its own header says so
("the half of the port that gate P-1 deliberately does not test") and
`tests/tracker_properties.rs` says there is no direct oracle for it. That
projection decides roughly 400 of the 828 columns, it is symmetric in
self-play, it moves none of the D25 gates, and the repo has a measured sibling
defect — `recharge_fix`, an observation-semantics bug of exactly this class —
worth +0.0106, which is 42% of A-1's band. This is the single largest
unverified surface in the port.

A second, smaller circularity sits beside it: 184 of the 828 floats (8 move
blocks x the 23-float v2 effect sub-block) are a verbatim copy of shared
`_effect_block` output, because `engine_tables.py` IMPORTS `_effect_block`
rather than reimplementing it. That is sanctioned (plan §7.4 — values that
travel as data are never recomputed, which is what makes bitwise parity
reachable at all) but it means those columns carry no independent signal in
P-1. Fixing the projection oracle does not fix this one; only an independent
reimplementation would, and the cost/benefit there is poor.

**Why "drive track.rs from recorded protocol tapes" cannot be done literally.**
The tracker is DIFF-DRIVEN over the engine's own 384-byte structs
(`BattleTracker::observe(&mut self, b: &Battle)`), with `-Dlog` off and nothing
parsed. It has no protocol input to drive. And a recorded PS tape cannot be
replayed into the engine, because matching a real battle would require its RNG
stream and both players' choices.

**The design that does work — turn the direction around.** The engine has a
`-Dlog` build already wired as the `debug-log` cargo feature, and poke-env is
itself a PS-protocol parser. So:

  1. Run engine battles under `debug-log`, emitting PS protocol.
  2. Feed that protocol to a poke-env `Battle` — the REFERENCE observer, the
     same code the server path trusts in production.
  3. At every decision point, compare poke-env's `Battle`-derived observable
     state against `track.rs`'s diff-derived state for the SAME battle.

Both observers now watch one battle from the same information boundary, and
neither is derived from the other. That is a real oracle, and it exercises
precisely what P-1 skips: reveal order, revealed-move sets, HP quantisation,
observed sleep turns, binding/lock counters, faint flags.

**Why this is worth building even though A-1 is running.** A-1 cannot see a
projection defect below ~2.5 pp of win rate, and P-1b can see one at n=1 —
a single mismatched reveal is a hard failure. It is also offline, needs no
server, and is repeatable. If it finds nothing, A-1's blind spot shrinks from
"~400 unverified columns" to "~400 columns verified against poke-env on N
battles", which is the difference between a screened port and a trusted one.

**Cost and shape.** A `debug-log` build (the feature exists, unused), a small
Rust binary that plays K battles and writes protocol + a per-decision dump of
`ObservableState`, and a Python comparator reusing P-1's existing field
extractor against a poke-env `Battle` fed the same protocol. The declared
families carry over from P-1; anything else is a bug, not a family.
NOT STARTED — designed here so the next session can cost it honestly.

## 2026-09-09 (afternoon) — three incidents on the way to the first gate run

**The box slept all day.** The maintainer's `caffeinate` died, so the laptop
suspended repeatedly. Wall-clock elapsed is therefore meaningless for anything
measured today; CPU-time deltas are the only honest progress read, which is the
same instrument the stall landmine already demands. The current chain holds its
own `caffeinate -dims` (PreventSystemSleep asserted, confirmed in `pmset -g
log`), so it is insulated — but ANY future unattended run must assert sleep
prevention itself rather than inherit someone else's.

**Incident 1 — the 5,000,000-pair bank died at ~4 GB, and lied about why.**
`engine_team_bank.js` flushed every 2000 lines but ignored the return value of
`process.stdout.write`. Writing to a pipe returns false when the kernel buffer
is full; ignoring that queues the unwritten chunks on node's own heap. With a
JSON-parsing consumer the queue outran node's default old-space limit and node
died MID-WRITE. What the reader saw was `JSONDecodeError: Expecting value: line
1 column 928` — a TRUNCATED LINE, which reads like corrupt data rather than an
OOM. RSS was measured climbing 0.11 GB/min through 4.05 GB just before it went.
Fixed by awaiting `'drain'`. MEASURED after: RSS flat at 0.31 GB across 90 s of
continuous generation, and the output is byte-identical (sha256 `d2374a16…` on
a 5,000-pair run before and after), so this changed memory behaviour only. The
Python side now names the real cause on a partial line instead of surfacing a
decode error. Streaming the Python reader (fixed earlier the same day) was
necessary but not sufficient — BOTH ends had to stop buffering.

**Incident 2 — D-1's server leg hung silently, and its own docstring predicted
it.** The leg had never run. First contact: the script and the server both sat
at ZERO CPU indefinitely, no error, no timeout. Cause: the players were built
in a sync frame and then awaited from a fresh `asyncio.run` loop, so the
handshake touched primitives living on poke-env's background POKE_LOOP and
never completed — the trap `ch5_orphan_demo.py` already documents. Isolated by
running `anchor_h2h.py` against the same server, which finished 4 battles while
this leg hung. Everything poke-env touches is now built and awaited inside one
loop. A watchdog (`asyncio.wait_for`, 20 s/battle, ~13x the measured rate) was
added because the failure mode is SILENT and the chain runs unattended.

**Incident 3 — D-1 poisoned its own usernames.** The seat tag keyed on the
chunk index alone, so the SECOND matchup reused the FIRST matchup's usernames
while those players were still connected: `Expected d10b… to be logged in`. At
the real n=10,000 this would have fired only after the first matchup had
already spent 10,000 battles. The tag now carries the matchup index, and both
players are torn down after each chunk so a 20-chunk leg does not leak sockets.

**First numbers off the repaired legs (SANITY ONLY, not the gate).**
Engine, n=400: max_power 0.517/0.025 tie/21.4 turns, sleep 0.000; random
0.490/0.007/61.9, sleep 0.755. Server, n=6 (noise, quoted only to show the
harness runs): max_power 0.333/0.167/20.7, sleep 0.000; random 0.833/0.000/45.5,
sleep 0.833. The `sleep_fraction` agreeing at 0.000 on max_power across both
simulators is the first cross-simulator signal the port has ever produced.
Server rate 0.08 s/battle at concurrency 8, so D-1's 20,000 battles is ~30 min.

## 2026-09-09 (evening) — D-1's first FAIL was an artifact, and how it was caught

**The verdict.** D-1 came back FAIL: `max_power_vs_max_power` breached two of
three bands (p1 win rate delta +0.0208 against 0.02; tie rate +0.0060 against
0.005), while `random_vs_random` passed all three cleanly. Correctly, A-1 did
not launch.

**It was not a parity failure.** The engine leg was measuring 500 battles
twenty times. `scripted_series` derives battle `i` from `(lane_seed, i)` and
looped `for i in 0..n` on EVERY call; `engine_d1` chunks n=10,000 into 20 calls
of CHUNK=500, so it replayed battles 0..499 and reported n=10,000. Two
successive calls returned byte-identical outcomes AND turns — that was the
direct confirmation.

**The tell, and it is worth remembering.** Not the failing band — the SEAT
ASYMMETRY. Under `random_vs_random`, the same uniform policy sits on both
seats, so p1 − p2 must be ~0 by construction; there is no mechanism for a
difference. The engine gave +0.021, +0.061, +0.008, −0.010, +0.022 across five
lane seeds at a nominal n=20,000 — up to 12 se from zero, and violently
seed-dependent. Independent battles cannot behave like that, so the sample was
not what it claimed to be. **A symmetric matchup is a free self-test on any
battle generator, and it found this before any parity argument did.**
After the fix, the same five seeds: −0.0025, −0.0036, +0.0020, +0.0047,
+0.0091 — all inside 1.8 se.

**What it does to the numbers.** The engine leg's true binomial se is
sqrt(20)x what it reported: 0.0224, not 0.0050. The max_power p1-win delta of
+0.0208 is **+0.91 se_diff**, not the 4.2 se the reported se implied. Both
breaches were inside noise. `results/d1` was DELETED and the gate re-run, not
reinterpreted — a verdict computed on a broken sample is not evidence about
anything, in either direction.

**The fix, and a second bug inside it.** A battle-index `start` now threads
through `scripted.rs`, `env.rs` and the PyO3 binding (default 0, so single-shot
callers are unchanged). While fixing it, the policy RNG turned out to be a
STREAM carried across the series, which made the result depend on how the
caller chunked the run — 20x500 and 1x10,000 would play the same battles with
different policy draws, so D-1 could not resume without changing its own
answer. It is now derived per battle from the battle index. `2x30 == 1x60`
exactly, for both policies, and that invariant is pinned.

**Pinned by three tests** (`tests/test_engine_scripted.py`): chunks play
different battles; chunking is invariant; a symmetric matchup shows no seat
asymmetry. 59 Rust tests green.

**Scope check — this never touched training.** `scripted_series` is D-1-only.
The collector takes `battle_counter` as a CONSTRUCTOR argument precisely so
`BatchEnv` cannot replay battles across a resume, which is the same class of
bug caught earlier and already guarded. A-1's arm is unaffected.

## 2026-09-09 — GATE RESULTS: D-1 PASS, T-1 (a) and (b) BELOW BAND

### D-1 — PASS, on independent battles, n=10,000 per matchup per simulator

| matchup | metric | engine | server | delta | band |
|---|---|---|---|---|---|
| max_power | p1 win | 0.4947 | 0.4936 | **+0.0011** | 0.02 |
| max_power | tie | 0.0299 | 0.0272 | **+0.0027** | 0.005 |
| max_power | mean turns | 21.31 | 21.35 | **−0.0016** rel | 0.05 |
| random | p1 win | 0.4928 | 0.4920 | **+0.0008** | 0.02 |
| random | tie | 0.0070 | 0.0082 | **−0.0012** | 0.005 |
| random | mean turns | 61.03 | 61.02 | **+0.0001** rel | 0.05 |

Descriptive, and the more convincing half: sleep fraction 0.0002 / 0.0002 and
0.7520 / 0.7597; freeze 0.4347 / 0.4340 and 0.2148 / 0.2115; mean faints 5.08 /
5.08 and 4.96 / 4.97. The seat check agrees too — engine p1−p2 +0.0193 against
the server's +0.0144 on max_power, i.e. **both simulators show the same small
first-player advantage**, which is the right answer rather than zero.

This is the port's first evidence that it is playing the same GAME as
Showdown. It is not evidence about the encoder or the tracker (P-1 does not
test the projection; see the P-1b design above).

### T-1 (a) — 6,056 battles/s, band ≥ 20,000. BELOW BAND.

Engine-only, no encoder, no policy, no network, `contended: false`. But the
band and the measurement are not the same quantity: leg (a) plays
`random_vs_random`, whose mean battle is **61.1 turns**, and 6,056 battles/s at
61.1 turns is **~740,000 decisions/s** across both seats. A band stated in
BATTLES per second silently depends on which policy is played — max_power
battles are 21.3 turns, so the same engine would read ~3x higher on that
matchup and "pass". **The band is mis-specified, not merely missed**, and
plan §9 should restate it in DECISIONS per second. Recorded rather than
quietly re-run against the flattering matchup.

### T-1 (b) — 22,318 steps/s at K=256, band ≥ 25,000. BELOW BAND at 256; K=512 clears it.

| K | steps/s | empty polls | own inference | OPPONENT inference |
|---|---|---|---|---|
| 32 | 13,549 | 0.672 | 0.266 | **0.719** |
| 64 | 15,686 | 0.398 | 0.234 | **0.748** |
| 128 | 17,977 | 0.193 | 0.238 | **0.726** |
| 256 | 22,318 | 0.060 | 0.254 | **0.680** |
| 512 | 30,559 | 0.030 | 0.308 | **0.605** |

**The finding that matters is not the band — it is that the OPPONENT's forward
pass is 60–75% of collection at every K.** The learner's own inference is
~25%. This is exactly the batch-2..4 GEMV→GEMM anomaly T-1 (b) was written to
look for (`latest_prob 0.8` with 20 pool members leaves the latest member ~200
rows and the other 19 about three each), and it is now measured rather than
predicted. Any further collection speedup should attack opponent batching
FIRST; K alone is a weaker lever, and empty polls are already only 3% at 512.

**Consequence for A-1's K ruling (RW-1).** A-1 is written at k=8 to match the
banked arm's concurrency so the collector is the only delta. These numbers say
the engine's throughput case rests on LARGE K, so accepting the collector at
k=8 accepts it at a point nobody would train on. That is an argument for RW-1
branch (b) — declare K part of the treatment — and it is now backed by a
measurement instead of intuition. The ruling is still the maintainer's.

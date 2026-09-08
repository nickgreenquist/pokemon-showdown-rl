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
most_damage_typed vs random > 0.85, and **most_damage_typed vs max_power >
0.55** — the type chart is the only difference between those two, which is why
JOURNEY's anchor is the typed one.

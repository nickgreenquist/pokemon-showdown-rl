# foulplay_pokejax_audit.md — the foul-play / poke-engine / pokejax audit deferred as D3

> **design_gen4 status header (mandatory, verbatim structure).**
> Written 2026-09-04 on branch `gen4-build`, DOCS ONLY — nothing under `rl/`
> changed. **Arc position:** the target is JOURNEY step 3 (gen4 encoder +
> model). This design work is **maintainer-ruled PREPARATION running AHEAD of
> step 2 (gen1 ladder #3)**, done while the rated ladder run is live; it is not
> a pre-registration and it launches nothing.
> **Verification status per claim** — every claim below carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo
>   (`rl/`, `scripts/`, `configs/`, `tests/`, docs) or the vendored
>   `showdown/` data/sim: the game as we actually run it.
> - `[src]` **source-verified** — checked against an external primary source
>   on disk: the foul-play clone, the pokejax analyses, installed poke-env.
> - `[lit]` **literature-only** — a secondary write-up or the prior-work index,
>   not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running server or a Rust
>   build can confirm it; BARRED while the ladder run is live; the exact check
>   is stated beside the tag.
> **Sources read for this doc:** `/Users/nickgreenquist/Documents/Projects/foul-play`
> at `25c976f`, local gen1 patch applied (`git status --short`: `M fp/battle/
> inference.py fp/data/__init__.py fp/modes/base.py fp/search/main.py
> fp/websocket_client.py requirements.txt`, `A fp/tape.py`) — `fp/generations.py`,
> `fp/format_spec.py`, `fp/config.py`, `fp/main.py`, `fp/run_battle.py`,
> `fp/tape.py`, all of `fp/search/`, `fp/battle/{state,protocol}.py` in the
> ranges cited, `fp/battle/inference.py` (grep + patch hunk), `fp/data/sets/*`,
> `fp/data/mods/apply_mods.py` + the gen4/5/6 mod JSONs,
> `fp/modes/{base,random_battle}.py`, `Makefile`, `requirements.txt`, `tests/`
> (index + gen4 cases); `docs/prior_work/pokejax/*` (all four files);
> `docs/prior_work/README.md:258-320, 540-575`;
> `scripts/patches/foulplay_gen1_local.patch`, `scripts/ch3_r4_fp_runner.sh`,
> `scripts/ch3_fp_h2h.py`, `docs/landmines.md:118-135, 295-320`,
> `SESSION_LOGS.md:5500-5525, 9140-9160`, `showdown/config/formats.ts:4239-4244,
> 4260-4265`, `showdown/sim/battle.ts:1836-1848`,
> `showdown/data/random-battles/gen4/sets.json`.
> **NOT read:** poke-engine's Rust source or `Cargo.toml` (no checkout on disk;
> every `src/state.rs` claim is second-hand from `docs/landmines.md:305`), any FP
> stdout log from RS81/R4, `poke_env/*` (poke-env facts come from
> `pokeenv_gen4_survey.md` §3–4, not re-derived, per the brief).
> **Feeds / depends on:** discharges deferral **D3** (`open_questions.md` §7)
> and feeds Q37–Q39; consumes `anchors_and_eval.md` §3,
> `pokeenv_gen4_survey.md` §3–4, `mechanics_delta.md` §6/§12,
> `encoder_requirements.md` §9.
> **Reconcile at merge:** nothing here is designed against the `audit-fixes`
> F-08 EncoderSpec seam.

**Nothing here was measured, launched or evaluated. No server was started, no
battle played, no engine built, no checkpoint touched.**

---

## 1. Where the generation enters foul-play's search (Q1)

**Two entry points, both string-keyed off the format name** `[src]`.
`FormatSpec._parse_format_string` regexes `gen([1-9]0?)` out of the format
(`fp/format_spec.py:9, 49-64`), so `"gen4randombattle"` gives
`gen_number=4, battle_type=RANDOM_BATTLE`. Then (1) `Battle.gen` →
`GENERATIONS["gen4"] = GEN4` (`fp/battle/state.py:107-109`;
`fp/generations.py:97-102, 128, 138-143`), and (2) `apply_mods` →
`apply_gen_4_mods()` at process start (`fp/main.py:46`;
`fp/data/mods/apply_mods.py:99-102, 159-160`), walking the gen8→gen4 move and dex
mod JSONs plus Steel-resists-Dark/Ghost; the physical/special split is correctly
NOT undone (`:137-147` is called only from `apply_gen_3_mods`).

`GEN4 = replace(GEN5, has_team_preview=False, rest_turns_reset_on_switch=False,
taunt_duration_increments_end_of_turn=True)` (`fp/generations.py:97-102`), so the
effective row and its consumers are:

| field | GEN4 value | who reads it (`fp/…`) | effect in gen4 |
|---|---|---|---|
| `has_team_preview` | False | `modes/standard_battle.py:39,129`; `modes/random_battle.py:121,130`; `search/standard_battles.py:312` | randbats skips preview; **also disables the two "conjure a Zoroark" branches**, which is why Zoroark logic is inert in gen4 |
| `heavy_duty_boots_exists` | False | `battle/inference.py:662` | HDB never guessed |
| `choice_scarf_exists` | True | `battle/inference.py:357` | scarf stays a speed-range explanation |
| `megas_exist` | False | `battle/state.py:147` | `mega_evolve_possible()` False |
| `supports_reverse_damage_checking` | True | `battle/inference.py:562` | damage-roll set narrowing ON |
| `paralysis_speed_divisor` | 4 | `battle/inference.py:259,262` | correct for gen4 |
| `taunt_duration_increments_end_of_turn` | True | `battle/protocol.py:751` (skip on-move bump), `:2004-2014` (bump in `upkeep`) | gen3/4 taunt timing |
| `ability_weather_is_permanent` | True | `battle/protocol.py:1327-1332` | `[from] ability:` weather ⇒ `weather_turns_remaining = -1` |
| `pressure_revealed_on_switch_in` | True | `battle/protocol.py:403` | Pressure added to `impossible_abilities` on a silent switch-in |
| `rest_turns_reset_on_switch` | False | `battle/protocol.py:232-249` | sleep/rest counters SURVIVE a switch |
| `tracks_consecutive_sleep_talks` / `partial_trapping_mechanics` / `stat_modification_glitches` | all False | `battle/protocol.py:656,2123` / `:591,672,687,1949` / `:698` | every gen1/gen3-only path off |
| `regenerator_heals_on_switch_out` | **True** | `battle/protocol.py:291,369` | **WRONG for gen4 — see §1.2** |
| `randombattle_evs` / `max_ev` | (85,)×6 / 252 | `battle/helpers.py:35,39` | matches the vendored generator `[tree]` (`pokeenv_gen4_survey.md` §3.3) |
| `request_dict_ability` | `"baseAbility"` | `battle/state.py:437,506` | gen4 request key |
| `hidden_power_base_damage_string` | `"70"` | `battle/state.py:805,809`; `data/sets/base.py:426,437`; `search/standard_battles.py:133`; `data/sets/smogon.py:152` | `hiddenpowerice` → `hiddenpowerice70`; the key exists (`fp/data/moves.json` has 16 `*70` variants) `[src]` |
| `stat_calculation` / `max_pp` | MODERN / `int(pp*1.6)` | `battle/helpers.py:178`; `battle/state.py:817` | correct for gen4 |

`[src]` The **only gen4-specific data mods** are 33 move entries
(`fp/data/mods/gen4_move_mods.json`: base powers and accuracies — Toxic 85,
Disable 80, Wrap 85, Bind/Clamp 75, the pre-split multi-hit powers) and 5 Rotom
formes' types (`gen4_pokedex_mods.json`). `tests/test_generations.py:11-56` and
`tests/test_apply_mods.py:88-93` already assert the gen4 row and its mods; the
gen4 protocol cases are `tests/test_battle_modifiers.py:561-571` (sleep survives
a switch) and `:2225-2239` (ability weather permanent). **No gen4 test touches
`fp/search/`** — `tests/test_search_random_battles.py` and
`test_poke_engine_serialization.py` are gen9-only.

### 1.1 What a gen4 anchor needs beyond `make poke_engine GEN=gen4`

`[src]` The Makefile target rebuilds `poke-engine==0.0.48` with
`--features poke-engine/$(GEN) --no-default-features` (`Makefile:21-24`), version
grepped out of `requirements.txt`, whose pin line our patch owns (`:4-7`).
Beyond the rebuild:

1. `[tree]` **Fix the pin comment, not just the pin.** It says a gen9 engine
   running gen1 "NEVER crashes"; the index records the measured opposite — 2-5
   over 7 battles, dying in `pyo3_runtime.PanicException`
   (`docs/prior_work/README.md:288-296`). Stale, and it would teach the next
   reader to ignore a panic.
2. `[src]` **Network fetch of the set file** on first run (§4). Barred now.
3. `[src]` **Nothing else is gen-guarded on the Python side.** Our patch's
   gen1-only pieces are inert but not absent: `all_move_json["fight"]` is
   injected unconditionally at import (`fp/data/__init__.py:13-42`) — nothing
   references it, and `check_dictionaries_are_unmodified` snapshots *after* the
   injection (`fp/main.py:48-49`), so it does not trip; the placeholder branch
   fires only when the active's single move is named `fight`
   (`fp/modes/base.py:261-262`). Login, pool, tape writer, `BrokenProcessPool`
   retry, pre-truncation policy capture and the `switch ` guard all carry over.
4. `[tree]` **The harness hardcodes gen1.** `scripts/ch3_fp_h2h.py:48`
   `BATTLE_FORMAT = "gen1randombattle"` is a module constant, and `:105,442`
   import `OBS_DIM` from `rl.envs.showdown`; `scripts/ch3_r4_fp_runner.sh:41`
   parameterises `FORMAT` but exports the gen1 encoder env (`:58-59`).
5. `[live]` **Engine-vs-server divergences** (check: a 5-battle gen4 smoke with
   `--log-to-file`, post-ladder): the §3 items with no foul-play model, plus gen4
   Explosion/Self-Destruct halving the target's Defense —
   `gen4_move_mods.json` touches neither move, so that rule lives (or does not)
   entirely inside the Rust build. 40 of 464 vendored sets carry one `[tree]`.

### 1.2 A gen4 defect found while reading: stale hidden abilities

`[src]` `apply_pokedex_mods(4)` applies the gen8→gen4 dex mods, but **only gen5
(53 species) and gen6 (23) carry `abilities` rollbacks**; `gen4_pokedex_mods.json`
has none. Applied to the vendored gen4 pool, **219 of 295 species still hold a
Dream-World `"H"` ability slot** that does not exist in gen4 (probe over
`fp/data/pokedex.json` + the four mod files, read-only under the foul-play env).
Three sites read `pokedex[name]["abilities"].values()` and act on it:
`battle/protocol.py:359-378` (assign `ability="regenerator"` to an opponent whose
HP differs on switch-in — and `regenerator_heals_on_switch_out` **is True for
GEN4**, `fp/generations.py:60, 97-102`, so Slowbro/Tangrowth/Amoonguss can acquire
a gen5 ability that reaches the engine at
`fp/search/poke_engine_helpers.py:87` and heals 1/3 per switch-out in search,
`protocol.py:290-302`); `:883-892` (Sheer Force / Magic Guard suppress the Life
Orb elimination); `:1579-1584` (Unburden on item loss).
Detector `[live]`: `grep "setting its ability to regenerator"` and
`grep "Adding unburden volatile"` in a gen4 FP stdout; both should be empty.

---

## 2. The Struggle panic (`Invalid PokemonMoveIndex: 4`) (Q2)

**The Python site that can emit an out-of-range move index is exactly one**
`[src]` — `fp/search/poke_engine_helpers.py:117-126`:

```
elif battler.last_used_move.move:
    pkmn_moves = [m.name for m in battler.active.moves]
    for i, move in enumerate(pkmn_moves):
        if move == battler.last_used_move.move:
            last_used_move = "move:{}".format(i)
```

`i` is an unbounded `enumerate` over `battler.active.moves`. The 4-move
truncation that would bound it lives in a *different* function
(`:58-66`, `pokemon_to_poke_engine_pkmn`) that is called **later**, at `:167`,
and does not revisit `last_used_move`. So `len(active.moves) >= 5` with the last
used move in slot 4+ produces `"move:4"`, which the engine rejects. `[lit]` The
panic string and `src/state.rs:106` come from `docs/landmines.md:305`; the Rust
is **not read** (no checkout on disk).

**Both recorded root causes are contradicted by the source** `[src]`:

- `docs/landmines.md:305-306` ("both sides are out of PP and use Struggle —
  move index 4"). Struggle is **never added to any move list**:
  `fp/battle/protocol.py:766-768` returns before `add_move`. On the bot's own
  side the request carries a single `Struggle` entry, and
  `_initialize_user_active_from_request_json` **clears and rebuilds** the list
  (`fp/battle/state.py:357-368`), giving length 1, index 0.
- `SESSION_LOGS.md:5511-5514` ("most plausibly the synthetic `fight` placeholder
  stacking onto 4 tracked moves"). The corrected patch `.clear()`s the list and
  adds exactly one move (`fp/modes/base.py:276-277`), and that patch was in place
  by 2026-08-06, before the 2026-08-23 panic.

**Enumerated growth paths for `active.moves`, and their gen4 reachability**
`[src]`+`[tree]`. `Pokemon.add_move` appends with no cap (`state.py:754-758`) and
every caller de-duplicates through `get_move`, so the length equals the number of
*distinct* names attributed to the object:

| path | site | gen4 reachable? |
|---|---|---|
| ordinary `\|move\|` | `protocol.py:782-788` | yes, capped at the mon's real 4 |
| Sleep Talk's called move | `protocol.py:716-725` | yes (25 sets), but the called move is one of the same 4 |
| `\|cant\|…\|move: X\|` | `protocol.py:1912-1921` | yes (Taunt 13 sets), same 4 |
| Illusion/Zoroark move transfer | `protocol.py:1727-1729` | **no** — Zoroark is gen5+; no pool entry |
| Transform copies the target's list | `protocol.py:2238` | Ditto, **1 set** in the pool; copies our 4 |
| species-object rename / unknown forme | `protocol.py:343-345` | no in-battle forme change in the gen4 pool |
| set population | `search/helpers.py:44-46` | resets to the set's exactly-4 moves |

`[tree]` The vendored gen4 pool has **no** Mimic, Metronome, Assist, Copycat,
Me First, Nature Power, Disable, Baton Pass or Perish Song (probe over
`showdown/data/random-battles/gen4/sets.json`, 295 species / 464 sets), which
agrees with `pokeenv_gen4_survey.md` §3.8 ("no move in the pool can grow a mon's
move dict past four"). **So no source-reachable 5-move path was found in gen4 —
nor in gen1.** The hole is real and unbounded; what filled it in RS81 is
unresolved from source alone.

**Consequences for the gen4 anchor:**

1. `[src]`+`[tree]` The turn-cap Struggle story does not transfer — the risk it
   named is not the mechanism. gen4's higher stall exposure (no Endless Battle
   Clause, `showdown/config/formats.ts:4243` vs gen1's `['Standard']` at `:4264`;
   turn-1000 auto-tie, `showdown/sim/battle.ts:1836-1839`; Pressure 32 / Protect
   45 / Toxic 132 / Recover 37 of 464 sets) lengthens games but does not by itself
   reach a 5th move index.
2. `[src]` **A second, hotter call site exists in gen4.** `immune()` calls
   `poke_engine_get_damage_rolls` → `battle_to_poke_engine_state` on **every**
   `|-immune|` message (`protocol.py:1609-1611`), outside the search and outside
   the `BrokenProcessPool` retry. gen4 has far more immunities than gen1
   (Levitate, Flash Fire, Water/Volt Absorb, Wonder Guard, Dark/Ghost), so any
   serialisation defect fires much more often.
3. `[live]` **Pre-flight detector**, free and log-only: `grep -c "More than 4
   moves on pokemon"` in the gen4 smoke's FP stdout
   (`poke_engine_helpers.py:60-65`). Non-zero means the hole is live before any
   panic; zero over ~500 battles is the best evidence short of reading the Rust.
4. Suggested one-line hardening (not applied): clamp `i` at
   `poke_engine_helpers.py:124`, which cannot change behaviour on a well-formed
   list.

---

## 3. Hidden-state bookkeeping: foul-play vs poke-env 0.15.0 (Q3)

poke-env column is quoted from `pokeenv_gen4_survey.md` §3–4 (not re-derived).
"Copy" = what our gen4 wrapper should take, against
`encoder_requirements.md` §9 step 3.

| state item | foul-play (`fp/…`) `[src]` | poke-env 0.15.0 `[src]` via survey | what our wrapper should copy |
|---|---|---|---|
| item memory | `Pokemon.item` + `removed_item` + `knocked_off` + `impossible_items` (`battle/state.py:623-624,644,654`); set on `-item` (`protocol.py:1512-1560`), cleared with `removed_item` recorded on `-enditem` (`:1563-1588`); Knock Off flagged; `-activate item:` and Poltergeist sniffed (`:1021-1046`) | `item` is 3-valued, **no `original_item`**; Knock Off / consumed berry / itemless are indistinguishable after the fact (§3.1) | **`removed_item` + `knocked_off` + `impossible_items` verbatim.** This is the single largest gap poke-env leaves and foul-play's answer is small and self-contained |
| weather duration | `weather_turns_remaining` counted down on `[upkeep]`, set to 5 (or 8 with the matching rock), `-1` when `[from] ability:` and `ability_weather_is_permanent` (`protocol.py:1323-1368`); **plus** a recovery rule: if it did not end when expected, give 3 turns and **infer the rock item** on the opponent (`:1369-1405`) | `weather` is a per-turn stamp with no duration; `[from]`/`[of]` dropped, so permanent ability weather looks like 5 turns (§4) | duration counter, the permanent-weather branch, **and** the rock-inference rule (it is free item information) |
| weather source | `battle.weather_source = "opponent:<name>"` (`protocol.py:1320-1321`), used only by the recovery rule | absent | copy; needed for the above |
| sleep counter / Rest | `rest_turns=3` on `[from] move: Rest`, else `sleep_turns=0` (`protocol.py:970-976`); `+1` per `\|cant\|…\|slp` (`:1939-1945`); **`rest_turns==1` + a `cant` is a hard `exit(1)`** (`:1932-1938`); both zeroed on cure (`:1268-1276`) and on `cureteam` (`:1291-1294`); **not reset on switch in gen4** (`:232-249`, gated `rest_turns_reset_on_switch`) | `status_counter` counts SLEEP+TOXIC; **double-bumps on a Sleep-Talk turn**; **not reset by Rest on a toxiced mon** (§3.5 defects 1–2) | foul-play's split `rest_turns` vs `sleep_turns` is the better model — copy it, and it fixes both poke-env defects at once (a Rest sets `rest_turns` and zeroes nothing else) |
| Substitute HP | approximated: `max_hp/4` if never hit, `max_hp/10` if hit; `substitute_hit` set by `-activate Substitute [damage]` and cleared on `-start`/`-end` (`search/poke_engine_helpers.py:128-135`; `protocol.py:1010-1019, 1144-1157, 1208-1210`) | no Substitute HP anywhere (§3.6) | copy the **`substitute_hit` bit**; treat the 1/4-vs-1/10 numbers as foul-play's heuristic, not a rule |
| Choice lock | `choice_lock_moves` disables every non-last move when the item is a choice item and the last move was this mon's, exempting Hidden Power; `can_have_choice_item` falsified when two different moves are used or by `unlikely_to_have_choice_item` (`battle/state.py:300-317`; `protocol.py:797-822`) | not modelled | copy both halves: the lock and the **falsifier** (it is the belief update, and 21 Trick + 4 Switcheroo sets make it live in gen4) |
| Encore / Disable move | Encore duration incremented per move (`protocol.py:741-747`) and passed to the engine (`poke_engine_helpers.py:199`); **the encored/disabled MOVE NAME is never stored**, and `disable` has no duration field at all (`:196-203`) | same defect — the `-start` branch consumes only `event[3]`, the move name is dropped (§3.6) | **neither library has it; our wrapper must parse the move name off `-start` itself.** Disable is on 0 gen4 sets `[tree]`, Encore on 24 — so Encore is the one that matters |
| `-activate ability:` recovery | `activate()` writes the ability for any `-activate \|ability: X` (`protocol.py:1026-1029`), including Mummy's original-ability bookkeeping | poke-env records an `Effect`, **not** the ability (Forewarn, Hydration, Shed Skin, Sticky Hold, Suction Cups, Synchronize) (§3.2) | copy — a 4-line fix that recovers real ability information poke-env drops |
| Flash Fire persistence | not modelled either way; foul-play carries no Flash Fire volatile | poke-env **bug**: `moved()` ends it after one Fire move; Showdown persists until switch-out; 6 pool species (§3.6) | ours to fix; foul-play offers no pattern |
| ability set on switch-in | `impossible_abilities` accrues the 7 announce-on-switch abilities, with a weather-already-active exemption (`protocol.py:29-43, 402-463`) | `possible_abilities` from the dex; 161/295 pool species auto-known (§3.2) | copy `impossible_abilities` **but rebuild the ability universe from the gen4 set file, not the dex** — see §1.2 |
| trapped | `trapped = trapped or maybe_trapped` (`battle/state.py:391-397, 480-487`) — one conservative bit | `trapped` / `maybe_trapped` separate; no switches populated when trapped (§4) | keep them separate in the encoder; foul-play's collapse is a search convenience |
| PP | client-side per move, `-2` under Pressure with the opponent's ability already read (`protocol.py:781-788`) | tracked for both sides, `-2` via `_pressure_on`; `check_move_consistency` asserts exactness for gen4 (§3.8) | poke-env's is the better source; foul-play's is the same rule |

---

## 4. The set-data pin (Q4)

`[src]` `https://pkmn.github.io/randbats/data/full/{format}.json`
(`fp/data/sets/randbats.py:24-30`), cached at
`fp/data/pkmn_sets_cache/<format>.json` (`fp/data/sets/base.py:26-28`), fetched
once and cached forever — including **caching an empty dict on a non-200**
(`base.py:38-52`), which would silently produce a setless opponent model. The
cache today holds only `gen1randombattle.json` `[src]`.

**Schema — the two files are not the same object** `[src]`+`[tree]`:

| | pkmn.github.io "full" (what foul-play parses) | vendored `showdown/data/random-battles/gen4/sets.json` |
|---|---|---|
| shape | `{species: {"<level>,<item>,<ability>,<m1>,<m2>,<m3>,<m4>[,<tera>]": count}}` (`randbats.py:42-68`) | `{species: {level: int, sets: [{role, movepool[], abilities[], preferredTypes?}]}}` |
| unit | one **concrete 4-move set**, with an empirical frequency | one **role with a movepool of 5+ candidates** the generator samples from |
| item | in the key | **absent** — assigned by `teams.ts` rules |
| counts | yes (used as sampling weights, `search/random_battles.py:44-56`) | no |
| gen4 size | not read (no network) | 295 species, 464 sets, levels 67–100, 8 roles, `preferredTypes` on 85 sets |

`[src]` **Matching to revealed info:** `get_all_remaining_sets` keeps sets passing
`full_set_pkmn_can_have_set` with `match_ability/match_item/speed/level/tera` all
on, and falls back to all of them off if that empties (`randbats.py:95-124`).
The fallback is **not total**: `full_set_pkmn_can_have_set` always ANDs
`pkmn_moveset.makes_sense_on_pkmn(pkmn)` (`base.py:106-113`), which requires every
*observed* move to be in the set. So a mon whose observed moves are not a subset
of any set gets `[]`, `prepare_random_battles` skips populating it
(`search/random_battles.py:43, 51-52`), and its raw tracked belief goes to the
engine unmodified — the mechanism by which any bad move belief survives into §2's
serialisation. Item/ability checks honour `removed_item`, `impossible_items`,
`can_have_choice_item`, `impossible_abilities` (`base.py:365-385`); the speed
check allows only Choice Scarf as a hidden modifier (`:348-363`).

**What a diff between the two files must compare** (it cannot be a text diff):
(1) the species key sets — 295 vendored vs however many upstream, normalised
names; (2) per-species `level`; (3) for each species, whether every upstream
4-move key is a subset of some vendored `movepool` **and** whether every vendored
movepool is covered — a movepool of 5 legitimately yields 5 upstream keys;
(4) `abilities` as sets; (5) items, which are **only** in the upstream file, so
the vendored side of that column has to come from `teams.ts` rules, not
`sets.json`; (6) the generator version — the upstream file reflects *today's*
generator, our server is 59da482. Pin and hash the fetched JSON in the pre-reg
exactly as LG-5 pinned gen1, and record the fetch date.

---

## 5. pokejax turned into a gen4 bridge checklist (Q5)

`[src]` pokejax is a JAX gen4randombattle engine with its own PPO
(367M+ steps, 512 envs, γ=0.999, C51 value head over ±2.5), evaluated on a local
Showdown server through poke-env: **4W-16L over 20 battles, 0.20**
(`local_summary.json`), against ~0.50 vs its own internal heuristic. Its two
analyses attribute the gap to opponent strength first and *bridge* bugs second.
`[lit]` Its own numbers are self-reported at n=20 (±0.09 binomial) and are not a
rung; they are cited here only for the bug list.

Each item: what can go wrong, and the detector in a local battle log.

1. **Stale `available_moves` for 1–2 turns after a switch** — 15.9% of turns in
   their trace (`ANALYSIS_local_heuristic_winrate.md` §2; `ANALYSIS_winrate_gap.md`
   §3): wrong move features **and a wrong legal mask**. Detect: assert every id in
   `battle.available_moves` is in `battle.active_pokemon.moves`, and log the
   mismatch rate. Their own fallback (use `available_moves` anyway) is wrong.
2. **Empty `available_moves` on 33% of turns**, 7/69 with no switches either —
   fallback to action 0. Detect: count all-zero masks pre-masking; assert 0.
3. **`available_switches` still lists the now-active mon** (56 catches in 5
   games). Detect: assert the active slot is never set in the switch half.
4. **PP never decrements**, so `pp_frac ≡ 1.0`. `[src]`
   `pokeenv_gen4_survey.md` §3.8 says 0.15.0 **does** track PP both sides and
   asserts exactness for gen4 — so this is a pokejax-version artefact or a real
   regression. Detect: `sum(max_pp - current_pp)` over a battle; flat zero = bug.
5. **Sleep-turn off-by-one** (engine 0-indexed, poke-env 1-indexed). Detect: a
   parse-only replay of a recorded sleep sequence against `mechanics_delta.md`
   §6 — the same replay settles the survey's Sleep-Talk double-bump (§3.5).
6. **Perish Song never encoded** — they call it "regular" in gen4. `[tree]`
   **Wrong for our pool: `perishsong` is on 0 of 464 vendored gen4 sets.** Keep
   the check (free); spend no encoder slot.
7. **Heal Block / Grudge / Wonder Room in training, absent at inference.**
   Detect: assert the volatile→bit map is one shared object, not two literals —
   a bug class, and the one worth a unit test.
8. **Opponent stats fabricated with hardcoded 31 IV / 21 EV.** `[tree]` gen4
   randbats stats are exactly computable (`pokeenv_gen4_survey.md` §3.3), so this
   is a bug we simply must not write. Detect: check the estimator against an
   own-side mon's request stats.
9. **`nature_id` hardcoded neutral** — correct by construction in gen4 randbats;
   the lesson is to assert it rather than hardcode it.
10. **Value head "uncorrelated with outcome"** at n=5 — noise; recorded so
    nobody cites it.

---

## 6. Game length, rates and runner thresholds (Q6)

`[src]` foul-play has **no per-decision timeout**. The budget is
`search_time_ms` (default 100) × the number of sampled battles, chosen by
`RandomBattleMode.search_params` (`fp/modes/random_battle.py:64-90`):
`parallelism × 4` battles at `search_time_ms // 2` while ≤ 3 opponent mons are
revealed and the active has shown no move, else `parallelism × 2` battles at
full time; both multipliers halve when `battle.time_remaining <= 60`, which is
read off `|inactive|… sec this turn` (`protocol.py:95-108`). Workers are a
`ProcessPoolExecutor(max_workers=parallelism)` — persistent, via our patch
(`fp/search/main.py:87-98`), with `search_threads` threads inside each
(`:114-128`). `[tree]` Our gen1 anchor runs `--search-time-ms 20`,
`--search-parallelism 1`.

Two structural reasons gen4 per-decision wall-clock will exceed gen1's at the
same budget `[src]`: with **no team preview**,
`populate_randombattle_unrevealed_pkmn` synthesises the unrevealed 5 through a
rejection loop of up to 10 attempts each (`search/random_battles.py:78-109,
165-183`) on every sampled battle, every decision; and `deepcopy(battle)` runs
once per sampled battle over a 12-mon state. Game length also grows: no Endless
Battle Clause, only the turn-1000 auto-tie, and a stall-heavy pool (§2, item 1)
`[tree]`.

**Consequences for the runner** `[tree]` (`scripts/ch3_r4_fp_runner.sh`):
`POLL_SECS=10`, `STALL_POLLS=60` (a 600 s no-growth window),
`NO_PROGRESS_RELAUNCHES=3`, `MAX_RELAUNCHES=30`, `START_STAGGER=30`. The 600 s
window was sized against gen1 rates (FP@20 ≈ 1.2–1.5 s/battle,
`CLAUDE.md`), so a single gen4 battle can plausibly occupy a large fraction of
it. **Re-measure s/battle on the smoke and re-derive `STALL_POLLS` from it before
any n=250 arm** `[live]`; the four incident fixes carry over unchanged. Both
seats already request the timer — foul-play sends `/timer on` itself at battle
start (`fp/run_battle.py:28`) `[src]` and our seat sets
`start_timer_on_battle_start=True` (`scripts/ch3_fp_h2h.py:198`) `[tree]` — so
the orphaned-room deadlock's cause is covered on both sides in gen4 too.

---

## What this changes in the five docs

Concrete, cited; **not applied here.**

1. **`anchors_and_eval.md` §3, the Struggle risk bullet — replace the
   mechanism.** It says the panic is "hit when both sides are out of PP at the
   turn cap"; `fp/battle/protocol.py:766-768` shows Struggle is never added to a
   move list and `fp/battle/state.py:357-368` rebuilds the bot's list from the
   request. The hole is the unbounded index at
   `fp/search/poke_engine_helpers.py:117-126`, no 5-move path is reachable in the
   vendored gen4 pool, and the gen1 root cause is unresolved from source. Make
   the pre-flight check the `"More than 4 moves on pokemon"` grep (§2 item 3),
   not a forced-Struggle battle, and add the `|-immune|` call site
   (`protocol.py:1609`).
2. **`anchors_and_eval.md` §3, "Our patch".** Add: the `requirements.txt:4-6`
   comment ("a gen9 engine … NEVER crashes") contradicts the measured A/B
   (`docs/prior_work/README.md:288-296`) and must be corrected with the pin; and
   `scripts/ch3_fp_h2h.py:48` hardcodes `BATTLE_FORMAT = "gen1randombattle"`, so
   the h2h harness needs a format parameter, not just the runner's `FORMAT`.
3. **`anchors_and_eval.md` §3, the set-data paragraph.** Add the schema asymmetry
   (§4) — upstream is concrete counted 4-move sets, vendored is roles with
   movepools and **no items** — so "diff it against the vendored pool" means the
   six-way comparison in §4, with the item column coming from `teams.ts`. Add the
   silent failure mode: a non-200 caches `{}` permanently
   (`fp/data/sets/base.py:38-52`); the pre-reg must assert non-empty and hash it.
4. **`anchors_and_eval.md` §3, a new risk bullet — the stale-hidden-ability
   leak** (§1.2): `regenerator_heals_on_switch_out` is True for GEN4
   (`fp/generations.py:60, 97-102`) while 219/295 pool species keep a Dream-World
   `"H"` ability after `apply_gen_4_mods()`. Exactly the "biases the teacher down,
   silently" class the section already warns about, with a free log detector.
5. **`open_questions.md` §7 D3** — mark discharged by this note. **Q37** gains two
   pre-reg items: correct the pin comment, and assert the cached set file is
   non-empty and hashed. Q38/Q39 unaffected.
6. **`encoder_requirements.md` §9 step 3.** Four of the seven items now have a
   named implementation to copy rather than invent (§3): item memory
   (`removed_item`/`knocked_off`/`impossible_items`), weather start + `[from]
   ability` **plus the rock-inference rule**, the split `rest_turns`/`sleep_turns`
   model (which fixes both poke-env sleep defects at once), and
   `-activate ability:` recovery. Two remain ours alone: **the Encore/Disable
   move name, which neither library stores** (`poke_engine_helpers.py:196-203`;
   survey §3.6), and Flash Fire persistence. Substitute HP: copy the
   `substitute_hit` bit, not foul-play's 1/4-vs-1/10 numbers. Add Choice lock's
   **falsifier** (`protocol.py:797-822`), which the step does not list.
7. **`mechanics_delta.md` §12** — rules unchanged; optionally quantify the stall
   load (Protect 45 / Toxic 132 / Recover 37 / Pressure 32 of 464 sets), since the
   turn-cap discussion is otherwise qualitative.
8. **`pokeenv_gen4_survey.md` §3.8** — no change; its "no move in the pool can
   grow a mon's move dict past four" is independently confirmed here from
   `sets.json` (Mimic/Metronome/Assist/Copycat/Me First/Nature Power all 0,
   Transform 1). Cross-reference it: it is now load-bearing for §2.
9. **`docs/prior_work/README.md` (main tree, flag only — M3 class).** The pokejax
   entry repeats "Perish Song appears regularly in Gen4 random battles";
   `perishsong` is on **0 of 464** vendored gen4 sets. Its "PP never decrementing
   locally" is contradicted for 0.15.0 by `pokeenv_gen4_survey.md` §3.8 — record
   both sides.

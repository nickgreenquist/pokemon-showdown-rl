# poke-env 0.15.0 battle-state model for `gen4randombattle` — survey

**Agent:** pokeenv-battle-state (gen-4 design sweep, source family: installed poke-env + vendored Showdown data)
**Date:** 2026-09-04
**Note path:** `scratchpad/research/pokeenv_battle_state.md`

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP: `rl/`, `scripts/`, `configs/`, `tests/`, `docs/`) or the vendored Showdown `data/`/`sim/`, i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk: PE (installed poke-env) source, Wang's diffs/thesis, H&L text or MG code, PSPPO, FP, Metamon text.
- **literature-only** — from a secondary write-up, web page, memory, or the prior-work index without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm; BARRED until the ladder run (and any later fleet) completes. Each such finding names the exact post-ladder check.

## Sources read (path — what I actually opened)

Installed poke-env 0.15.0, `PE = /opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env`:

| File | Lines read |
|---|---|
| `PE/battle/abstract_battle.py` | 19–192 (MESSAGES_TO_IGNORE, `__slots__`, `__init__`), 330–470 (item/ability inference helpers, `_field_end`, `field_start`), 526–570 (`_finish_battle`, `is_grounded`), 570–800 (`parse_message` pt 1), 798–1000 (`-start` … `-item`), 1000–1196 (`-mega` … `NotImplementedError`), 1196–1226 (`_pressure_on`), 1224–1345 (`side_end`, `_side_start`, `_update_team_from_request`, `end_turn`), 1340–1811 (property outline via grep) |
| `PE/battle/battle.py` | 1–303 (whole file) |
| `PE/battle/pokemon.py` | 1–165 (`__slots__`, `__init__`), 165–200, 196–340 (`check_consistency`, `check_move_consistency`), 335–460, 457–620 (`moved`, `set_hp_status`, `start_effect`, `switch_in/out`), 620–760 (`transform`, `_update_from_pokedex`, `_update_from_details`, `update_from_request`), 791–860, 860–1010, 1016–1135, 1152–1310, 1310–1416 |
| `PE/battle/effect.py` | 1–60, 239–381 (parsers + classification properties), 615–683 (`_VOLATILE_STATUS_EFFECTS`), 683–780 (`_PROTECT_BREAKING`, `_TURN_COUNTER`, `_ENDS_ON_*`, `_ACTION_COUNTER`) |
| `PE/battle/move.py` | 17–165, 163–360, 360–560, 560–750; property outline via grep |
| `PE/battle/side_condition.py`, `weather.py`, `field.py`, `status.py`, `move_category.py`, `target.py`, `pokemon_type.py` | whole files |
| `PE/data/gen_data.py`, `PE/data/normalize.py` | whole files |
| `PE/stats.py` | whole file |
| `PE/calc/__init__.py` (3 lines), `PE/calc/damage_calc_gen1_2.py` 1–60 + gen-guard grep, `PE/calc/damage_calc_gen9.py` 31–120 + gen-guard grep | as noted |
| `PE/player/baselines.py` | 120–380 (`SimpleHeuristicsPlayer`) |
| `PE/player/player.py` | grep of message routing (lines 182–331) |
| `PE/environment/singles_env.py` | 55–140, 286–301 (`get_action_space_size`) |
| `PE/data/static/typechart/gen{1,4,5,6}typechart.json`, `pokedex/gen4pokedex.json`, `moves/gen{1,4}moves.json` | parsed programmatically (`nice -n 19` python, no network) |

Vendored Showdown 0.11.11 @59da482, `SD = /Users/nickgreenquist/.../pokemon-showdown-rl/showdown` (gitignored, un-snapshotted — read-only):
`SD/config/formats.ts` 4239–4265; `SD/data/random-battles/gen4/teams.ts` 1–30, 510–627, 627–745; `SD/data/random-battles/gen4/sets.json` (parsed); `SD/data/random-battles/gen5/teams.ts` 607–700; `SD/data/random-battles/gen9/teams.ts` 1445–1460; `SD/data/conditions.ts` 222–252, 500–690 (weather adds); `SD/data/abilities.ts` 1331–1371; `SD/data/mods/gen4/conditions.ts` 1–130; `SD/data/mods/gen4/moves.ts`, `items.ts`, `scripts.ts` (grep of `add('-…')`); `SD/data/mods/gen1/conditions.ts` 192–215; `SD/sim/` (grep of `add('…')` message names).

Repo snapshot, `SNAP = scratchpad/main_snapshot` (main@2738025): `SNAP/rl/envs/encoder_spec.py` 1–120 and the `GEN1 = EncoderSpec(...)` block 208–260.

Helper artefact written by me: `scratchpad/research/_effect_strings.txt` (185 literal effect strings greppable out of the vendored sim's `-start/-activate/-singleturn/-singlemove/-end` calls).

---

## 0. The one-paragraph shape of the answer

poke-env 0.15.0 has **no gen-4-specific code path at all**. There is one `Battle` class, one `parse_message`, one `Pokemon`, one `Move`; the generation enters only through (a) `GenData.from_gen(4)`'s three static JSON tables, (b) a handful of `self.gen <= 3` / `gen >= 5` / `gen in [1,2,3,7,8]` guards, and (c) whatever the server happens to send. That is *good news for gen 4* — gen 4 sits on the "modern" side of nearly every guard, so far fewer things are special-cased away than in gen 1 — and it is the reason almost every remaining risk is a **content** risk (an effect string that lands in `Effect.UNKNOWN`), not a **structural** one. The structural surprises are: the 18-key gen-4 type chart, the `num`-collision across formes, the absence of any opponent-stat estimator, the absence of any gen-4 damage calculator, and the fact that several state values poke-env exposes as `int` are *turn stamps*, not counters.

---

## 1. `Pokemon` fields and their gen-4 semantics

### 1.1 `item`

| Fact | Status | Citation |
|---|---|---|
| Three-valued: `"unknown_item"` (sentinel) → not yet known; `None` → known to hold nothing / just lost it; an id string → known. `GenData.UNKNOWN_ITEM = "unknown_item"`; a `Pokemon` is born holding it. | source-verified | `PE/data/gen_data.py:14`; `PE/battle/pokemon.py:114` `self._item: Optional[str] = GenData.from_gen(gen).UNKNOWN_ITEM` |
| Setter id-normalises: `item = to_id_str(item) if item is not None else None`. | source-verified | `PE/battle/pokemon.py:1110-1112` |
| **Own side:** overwritten every request from `request_pokemon["item"]` — Showdown sends `""` for no item, so our own mons' `_item` is `""` (falsy, but *not* `None`) when itemless. Any encoder must treat `""`, `None` and `"unknown_item"` as three distinct cases. | source-verified | `PE/battle/pokemon.py:731` `self._item = request_pokemon["item"]`; assertion `pkmn_request["item"] == (self.item or "")` at `pokemon.py:233-236` |
| **Opponent side:** revealed only by protocol events — `-item` (`abstract_battle.py:1148-1200`), `-enditem` (`:1135-1137`), `-damage`/`-heal` `[from] item:` sniffing (`:333-355`, `:370-387`), Trick (`:889-892`), Frisk (`:1150-1163`). | source-verified | as cited |
| **Trick / Switcheroo** are handled on the `-activate` event, and the follow-up `-item` messages that carry `[from] move: Trick` / `[from] move: Switcheroo` are explicitly `return`ed early so the swap is not double-applied. The swap is a raw `mon._item, mon2._item = mon2.item, mon.item`. | source-verified | `abstract_battle.py:889-892` and `:1193-1199` |
| **Knock Off** arrives as `-enditem|<victim>|<Item>|[from] move: Knock Off|[of] <source>`; poke-env's `end_item` just sets `self._item = None`. The *reason* the item left is discarded. | tree-verified (emission) + source-verified (handling) | `SD/data/mods/gen4/moves.ts:714`; `PE/battle/pokemon.py:405-410` |
| **Consumed berries** are indistinguishable from "no item" afterwards: `-enditem|…|Sitrus Berry` → `_item = None`, same as Knock Off and same as an opponent confirmed itemless. `_check_heal_message_for_item` deliberately refuses to re-assign anything containing `"berry"` or `"herb"` because Showdown emits the heal *after* consumption. | source-verified | `PE/battle/pokemon.py:405-410`; `abstract_battle.py:370-387` (the comment "don't assign an item that was just consumed") |
| `end_item("powerherb")` additionally clears `_preparing_move`/`_preparing_target`. Power Herb is gen-4-legal, so this path is live for us. | source-verified | `PE/battle/pokemon.py:405-410` |
| Gen-4 randbats item vocabulary is small: the literal item strings in gen 4's `getPriorityItem` plus the inherited gen-5 `getItem` union to **≈26 items** (Black Glasses, Black Sludge, Chesto Berry, Choice Band/Scarf/Specs, Custap Berry, Damp Rock, Expert Belt, Focus Sash, Leftovers, Life Orb, Light Ball, Light Clay, Lum Berry, Lustrous Orb, Quick Powder, Rocky Helmet, Silk Scarf, Sitrus Berry, Soul Dew, Stick, Thick Club, Toxic Orb, …). Exact enumeration belongs to the mechanics agent; the encoder should size an item embedding at ~32, not ~200. | tree-verified | `SD/data/random-battles/gen4/teams.ts:510-627`; `SD/data/random-battles/gen5/teams.ts:607-700` |

### 1.2 `ability` / `possible_abilities`

| Fact | Status | Citation |
|---|---|---|
| `possible_abilities` is set from the pokedex entry's `abilities` dict, id-normalised: `[to_id_str(a) for a in dex_entry["abilities"].values()]`. | source-verified | `PE/battle/pokemon.py:657-662` |
| **The single-ability auto-reveal.** `if len(self._possible_abilities) == 1 and self.gen >= 3: self._ability = self._possible_abilities[0]`. Gen 4 satisfies `gen >= 3`, so a one-ability species has its ability **known the instant it is seen**, opponent included. | source-verified | `PE/battle/pokemon.py:661-662` |
| **Quantified for our pool:** of the 295 species in gen-4 randbats, **161 have exactly one possible ability (auto-known) and 134 have two (genuinely hidden)**. 122 distinct abilities appear across the pool. Gen-4 `gen4pokedex.json` has **no `"H"` (hidden-ability) slot at all** — slot keys are only `"0"` (767 entries) and `"1"` (359) — so `possible_abilities` has length ≤ 2 in gen 4, never 3. | tree-verified (pool) + source-verified (dex) | `SD/data/random-battles/gen4/sets.json` cross-joined with `PE/data/static/pokedex/gen4pokedex.json` (parsed) |
| The `ability` **property** is a 3-level fallback: `temporary_ability` → `forme_change_ability` → `_ability`. The **setter** is stateful: writing when `_ability is None` sets the base ability; writing again writes `_temporary_ability`. `base_ability` returns `_forme_change_ability or _ability`. | source-verified | `PE/battle/pokemon.py:860-879`, `:912-918` |
| Reveal paths: `-ability` (`abstract_battle.py:766-797`), `move` with `[from] ability: X` (`:647-668`), `-damage`/`-heal` `[from] ability:` (`:356-368`, `:389-404`), `-immune|…|[from] ability: X` (`:1155-1162`), `-endability` (`:1131-1133`), Frisk on `-item` (`:1150-1163`), Skill Swap on `-activate` (`:829-864`). |
| **Trace** (Porygon2, Gardevoir in the pool) has a dedicated branch: on `-ability|<mon>|<Traced>|[from] ability: Trace|[of] …` it forces `_ability = "trace"` first (undoing a mis-ordered earlier write) and then sets the traced ability as `temporary_ability`. Result: `mon.ability` = the copied ability, `mon.base_ability` = `"trace"`. `switch_out` clears `temporary_ability`. | source-verified | `abstract_battle.py:777-793`; `PE/battle/pokemon.py:600-609` |
| **Ability-set weather does NOT reveal the ability.** The `-weather` branch reads only `event[2]`; `[from] ability: Sand Stream` and `[of] p1a: Tyranitar` are dropped on the floor. In practice this costs nothing for our pool — Tyranitar, Hippowdon, Abomasnow, Kyogre, Groudon are all single-ability and therefore already auto-known. | source-verified (PE) + tree-verified (emission, pool) | `abstract_battle.py:754-761`; `SD/data/conditions.ts:500,574,649,679` |
| **Abilities that leave no trace in poke-env state**: Truant (Slaking) arrives as `cant|<mon>|ability: Truant`, and the `cant` branch only calls `cant_move()` — no effect, no flag, so "Slaking is loafing this turn" is invisible. Pressure, Sturdy, Damp, Anticipation, Frisk, Speed Boost, Poison Heal, Magma Armor, Forecast do not map to `Effect` members. Slow Start (Regigigas) *does*: `-start|<mon>|ability: Slow Start` → `Effect.SLOW_START`, and it is turn-countable. Flash Fire → `Effect.FLASH_FIRE`. Illusion (`Effect.ILLUSION`) exists but **no gen-4 randbats species has Illusion** (Zoroark is gen 5). | source-verified (mapping) + tree-verified (pool) | `abstract_battle.py:742-744`; `PE/battle/effect.py` membership probe; pool join as above |

### 1.3 `stats` / `base_stats`

| Fact | Status | Citation |
|---|---|---|
| `_stats` is a 6-key dict `{hp, atk, def, spa, spd, spe}` initialised to all-`None`. **Gen 4 has a real, separate `spd`** — `base_stats` comes straight from the dex and carries all six. (Contrast gen 1, where the SNAP encoder drops `spd` as a mirror of `spa`.) | source-verified | `PE/battle/pokemon.py:121-128`, `:938-948`; `SNAP/rl/envs/encoder_spec.py:224` `base_stat_keys=("hp","atk","def","spa","spe")` |
| **Own side:** filled from `request_pokemon["stats"]` (5 keys — atk/def/spa/spd/spe), plus `hp` from the condition string when `store=True`. | source-verified | `PE/battle/pokemon.py:740-743`, `:534-556` |
| **Opponent side: `stats` stays all-`None` forever. poke-env contains no opponent-stat estimator.** `compute_raw_stats` exists (`PE/stats.py:70`) but its *only* caller is `_update_from_teambuilder` (`pokemon.py:780`), i.e. our own packed team. This is a hard requirement handed to the gen-4 encoder: we must compute opponent stats ourselves. | source-verified | `PE/stats.py`; grep for `compute_raw_stats` across `PE` returns exactly `stats.py`, `__init__.py`, `pokemon.py:14,780` |
| **Gen-4 randbats stats are exactly computable from `species` + `level`.** The generator hard-codes `evs = {85,85,85,85,85,85}` and `ivs = {31,…}` and specifies **no nature** (so Showdown's neutral default applies). Therefore for a non-HP stat: `stat = floor((2*base + floor(85/4) + 31) * level/100) + 5 = floor((2*base + 52) * level/100) + 5`, and `hp = floor((2*base + 52) * level/100) + level + 10`. Two documented deviations: `atk` EV→0 and IV→0 (or 31−28=3 with Hidden Power) when the set has no physical move; `spe` EV→0 and IV→0/3 when the set has Gyro Ball, Metal Burst or Trick Room; plus a Sitrus/Substitute/Belly-Drum HP-EV shave loop. | tree-verified | `SD/data/random-battles/gen4/teams.ts:648-649` (evs/ivs), `:696-707` (HP shave), `:711-719` (atk/spe zeroing), `:725-737` (returned set — **no `nature` key**) |
| Level is not fixed at 100: the gen-4 randbats level histogram over the 295-species pool spans **67…100** (34 distinct levels; mode ≈ 79/83/88). `level` is parsed out of `details` (`"Species, L84, M"`) and defaults to 100 when absent. | tree-verified (levels) + source-verified (parsing) | `SD/data/random-battles/gen4/sets.json` (parsed, `level` field per species); `PE/battle/pokemon.py:669-716` |
| `base_stats` returns `_temporary_base_stats` when Transform is active. | source-verified | `PE/battle/pokemon.py:938-948`, `:625-637` |

### 1.4 `boosts` — 7 keys, unchanged

`_boosts` is `{accuracy, atk, def, evasion, spa, spd, spe}`, clamped to ±6 in `boost()`; `set_boost` asserts `|amount| <= 6`. Gen 4 uses all seven (Double Team / Sand-Attack / Flash exist), same as gen 1. `clear_boosts`, `clear_negative_boosts`, `clear_positive_boosts`, `invert_boosts`, `copy_boosts`, `_swap_boosts` are all wired to protocol events (`-clearboost`, `-clearnegativeboost`, `-clearpositiveboost`, `-invertboost`, `-copyboost`, `-swapboost`). Baton Pass in gen 4 does **not** go through `copy_boosts` — boosts survive because Showdown re-emits them; but `switch_out` calls `clear_boosts()` unconditionally, so **poke-env zeroes the boosts of a Baton-Passing mon's replacement until the server re-sends `-boost` lines**. — *status:* source-verified for the code (`PE/battle/pokemon.py:182-188`, `:338-358`, `:524-528`, `:589-618`; `abstract_battle.py:899-919`); **needs-live-verification** for the claim about what Showdown actually re-emits after a gen-4 Baton Pass. *Post-ladder check:* run one `gen4randombattle` with a Baton Pass user, dump `battle._replay_data` around the `switch|…|[from] Baton Pass` line, and assert `battle.active_pokemon.boosts` matches the passer's at the moment after the switch.

### 1.5 `status` and `status_counter` — **an encoder CAN carry a sleep-turn feature**

| Fact | Status | Citation |
|---|---|---|
| `Status` is the same 7 members in every gen (`BRN FNT FRZ PAR PSN SLP TOX`). No new major status through gen 9. | source-verified | `PE/battle/status.py:12-18` |
| `status_counter` docstring: *"The pokemon's status turn count. Only counts TOXIC and SLEEP statuses."* | source-verified | `PE/battle/pokemon.py:1302-1308` |
| **Sleep** increments on two events: `cant_move()` (from `\|cant\|<mon>\|slp`) at `pokemon.py:194`, and `moved()` while `_status == SLP` at `pokemon.py:482-483` (i.e. a Sleep-Talk turn). It resets to 0 on `cure_status(status)` — which is what `-curestatus` fires on wake. | source-verified | `PE/battle/pokemon.py:189-195`, `:457-484`, `:359-364`; `abstract_battle.py:903-905` |
| **Gen-4 sleep is 1–4 move attempts.** The gen-4 mod sets `this.effectState.time = this.random(2, 6)` (→ 2..5) and decrements it *before* each move attempt, curing at ≤0. So `status_counter` ∈ {0,1,2,3} while asleep and the wake probability is a clean function of it: with `t = status_counter` attempts already spent, P(wake next attempt) = 1/(4−t). **A sleep-turn feature is therefore both well-defined and correctly tracked by pinned poke-env for gen 4.** (Early Bird — not in the pool as an ability worth noting — double-decrements.) | tree-verified | `SD/data/mods/gen4/conditions.ts:23-52` (`// 1-4 turns` / `this.random(2, 6)`) |
| **Toxic** increments once per turn in `end_turn()` (`pokemon.py:412-415`) and **resets to 0 on `switch_out`** (`:614-615`) — which is the correct gen-3+ rule (gen 1/2 differ). Note the counter counts *turns active while toxiced*, so it is off-by-the-turn-of-application by construction; the encoder should treat it as "n residual ticks already taken", which is what the damage fraction needs. | source-verified (PE) + literature-only (the gen-3+ reset rule itself) | `PE/battle/pokemon.py:412-415`, `:613-615` |
| **Known desync (small, real):** `status` is set in three places that do **not** reset `_status_counter` — the `status` setter (`pokemon.py:1298-1300`, driven by `-status`), and `set_hp_status` (`:534-541`, driven by `-damage`/`switch` hp strings). So a mon that carried a nonzero counter and then gains a *different* sleep/toxic status without an intervening `-curestatus` starts counting from the stale value. The realistic trigger in gen 4 is **Rest** on a toxiced mon: `-status\|<mon>\|slp\|[from] move: Rest` while `status_counter` is, say, 3 → the sleep clock reads 3 immediately, and poke-env would predict a wake that cannot happen. Rest is common in the gen-4 pool. | source-verified | as cited |
| Yawn is ended silently when the sleep it caused lands: `set_hp_status` checks `if self._status == Status.SLP and Effect.YAWN in self.effects: self.end_effect("yawn")`. | source-verified | `PE/battle/pokemon.py:543-545` |
| **Sleep Clause Mod is on** for `[Gen 4] Random Battle` (see §2.7), so at most one opponent mon is asleep at a time — a genuine policy fact and a reason the sleep feature is worth its slots. | tree-verified | `SD/config/formats.ts:4239-4244` |

### 1.6 `effects` — the `Effect` enum, and what gen 4 actually produces

**Size:** `Effect` has **224 members** (probed via `len(list(Effect))`). `effects` is `Dict[Effect, int]`. — source-verified, `PE/battle/effect.py`.

**Two different parsers, two different vocabularies.** `Effect.from_showdown_message` (used by `start_effect`/`end_effect`) strips `item: `/`move: `/`ability: `, uppercases, replaces spaces and hyphens with `_`, and falls back to `Effect.UNKNOWN` **with a `logging.warning`, not an exception** (`effect.py:243-271`). `Effect.from_data` (used by `Move.volatile_status`) strips separators entirely and looks up `_FROM_DATA` (`effect.py:274-297`). They do not agree on every string.

**Coverage of every volatile a gen-4 move can inflict.** I enumerated all `volatileStatus` / `self.volatileStatus` / `secondary.volatileStatus` values in `PE/data/static/moves/gen4moves.json` (486 moves) and ran each through `Effect.from_data`. **44 of 46 distinct values map to a real member; only `mudsport` and `watersport` fall to `Effect.UNKNOWN`** (poke-env models those as `Field.MUD_SPORT` / `Field.WATER_SPORT` instead — a genuine but tiny gen-4 gap, since in gen 4 they are user volatiles, not pseudo-weather). — source-verified, `PE/data/static/moves/gen4moves.json` + `PE/battle/effect.py:274-297`.

Explicit answers to the effects the task named:

| Requested effect | Member? | Turn-countable? | Notes / gen-4 protocol shape | Status |
|---|---|---|---|---|
| SUBSTITUTE | ✅ `SUBSTITUTE` | no | volatile-status set; presence bit only, **no substitute HP** anywhere in poke-env | source-verified |
| PROTECT | ✅ `PROTECT` | no | in `_ENDS_ON_TURN_EFFECTS` → cleared in `end_turn()` | source-verified |
| ENCORE | ✅ `ENCORE` | **yes** | `-start\|<mon>\|Encore` (no move name) → **which move is Encored is NOT stored** | source-verified + tree-verified (`SD/data/mods/gen4/moves.ts:412`) |
| TAUNT | ✅ `TAUNT` | **yes** | | source-verified |
| TORMENT | ✅ `TORMENT` | no | | source-verified |
| LEECH_SEED | ✅ `LEECH_SEED` | no | | source-verified |
| CONFUSION | ✅ `CONFUSION` | no | gen-4 mod emits `-activate\|<mon>\|confusion` on each self-hit; duration is hidden anyway | source-verified + tree-verified (`SD/data/mods/gen4/conditions.ts:73`) |
| CURSE | ✅ `CURSE` | no | | source-verified |
| PERISH_SONG | ❌ **no `PERISH_SONG` member** | no | but `PERISH0/1/2/3` exist and are what the server sends per-mon (`-start\|<mon>\|perish3`); the field-level `-fieldactivate\|move: Perish Song` is in `MESSAGES_TO_IGNORE`. The **countdown is readable from which of PERISH0..3 is present** — better than a counter. | source-verified |
| YAWN | ✅ `YAWN` | no | silently ended when sleep lands (§1.5) | source-verified |
| ATTRACT | ✅ `ATTRACT` | no | | source-verified |
| INGRAIN | ✅ `INGRAIN` | no | | source-verified |
| AQUA_RING | ✅ `AQUA_RING` | no | | source-verified |
| MAGNET_RISE | ✅ `MAGNET_RISE` | **yes** | also consulted by `is_grounded` | source-verified |
| TRAPPED / partial trap | `TRAPPED` exists but is **not** what gen 4 sends. `PARTIALLY_TRAPPED` exists but is only reachable via `from_data`. | the per-move members are | gen 4 emits `-activate\|<mon>\|move: <Wrap\|Bind\|Fire Spin\|Clamp\|Whirlpool\|Sand Tomb>\|[of] <source>` → `Effect.WRAP/BIND/FIRE_SPIN/CLAMP/WHIRLPOOL/SAND_TOMB`, **each of which is turn-countable**. Gen-4 duration is `this.random(3,7)` → 3–6 turns (6 with Grip Claw). An encoder must OR these six members into one "partially trapped" bit and read the count off whichever fired. | source-verified (mapping) + tree-verified (`SD/data/conditions.ts:229-232`, `SD/data/mods/gen4/conditions.ts:110-118`) |
| DISABLE | ✅ `DISABLE` | **yes** | gen 4 sends `-start\|<mon>\|Disable\|<Move Name>`; poke-env's `-start` branch consumes only `event[3]`, so **which move is disabled is lost** | source-verified + tree-verified (`SD/data/mods/gen4/moves.ts:319`) |
| EMBARGO | ✅ `EMBARGO` | **yes** | | source-verified |
| HEAL_BLOCK | ✅ `Effect.HEAL_BLOCK` | **yes** | note there is *also* a `Field.HEAL_BLOCK`; in gen 4 Heal Block is a per-mon volatile, so the `Effect` is the one that fires | source-verified |
| FOCUS_ENERGY | ✅ `FOCUS_ENERGY` | no | | source-verified |
| SLOW_START | ✅ `SLOW_START` | **yes** | `-start\|<mon>\|ability: Slow Start`; Regigigas only | source-verified |
| FLASH_FIRE | ✅ `FLASH_FIRE` | no | **poke-env drops it wrongly — see below** | source-verified |
| DESTINY_BOND | ✅ `DESTINY_BOND` | no | in `_ENDS_ON_MOVE_EFFECTS` | source-verified |
| MUST_RECHARGE | ✅ `MUST_RECHARGE` (a volatile-status member) | no | but the *live* signal is the separate boolean `must_recharge`, set by the `-mustrecharge` message | source-verified |
| LIGHT_SCREEN | ❌ **no `Effect.LIGHT_SCREEN`** | — | it is `SideCondition.LIGHT_SCREEN` in gen 2+, which is correct for gen 4 | source-verified |
| REFLECT | `Effect.REFLECT` exists (gen-1 legacy) **and** `SideCondition.REFLECT` exists | — | in gen 4 it arrives as `-sidestart`, so the **SideCondition** is the live one. The gen-1 `EncoderSpec` carries `Effect.REFLECT` in `volatiles`; a gen-4 spec must move it to the side block. | source-verified + tree-verified (`SNAP/rl/envs/encoder_spec.py:237-241`) |

**Bug found — Flash Fire is dropped early.** `Pokemon.moved()` contains `elif Effect.FLASH_FIRE in self.effects and move.base_power > 0 and move.type == PokemonType.FIRE and use: self.end_effect("Flash Fire")` (`PE/battle/pokemon.py:498-503`). In Showdown the `flashfire` volatile has **no** removal-on-use: it persists until switch-out (`onEnd(pokemon){ pokemon.removeVolatile('flashfire') }` on the ability, `[silent]` `-end` on the condition). So poke-env clears a 1.5× Fire boost that is still live. Six pool species carry Flash Fire (Ninetales, Arcanine, Rapidash, Flareon, Houndoom, Heatran). *Status:* source-verified (PE) + tree-verified (`SD/data/abilities.ts:1331-1367`). *Action for the encoder doc:* either patch downstream or accept the feature as noisy.

**Counter semantics.** Turn-countable effects are incremented in `Pokemon.end_turn()` (`pokemon.py:412-421`) — they count **up from 0**, they are not a remaining-turns countdown, and non-countable effects sit at 0 forever. The turn-counter set is 28 members (`effect.py:693-722`), of which gen-4-live are BIDE, BIND, CLAMP, DISABLE, DOOM_DESIRE, EMBARGO, ENCORE, FIRE_SPIN, FUTURE_SIGHT, GRAVITY, HEAL_BLOCK, MAGMA_STORM(gen5), MAGNET_RISE, SAND_TOMB, SLOW_START, TAUNT, UPROAR, WHIRLPOOL, WRAP. `_ACTION_COUNTER_EFFECTS` is only `{RAGE, STOCKPILE}` (`effect.py:777`).

**Dead classification helpers.** `Effect.ends_on_switch`, `.ends_on_move`, `.is_volatile_status`, `.is_from_ability`, `.is_from_item`, `.is_from_move` are **never called anywhere inside poke-env** (the only in-package reference is `ends_on_switch`'s own body at `effect.py:320`). `Pokemon.switch_out` clears *every* effect via `_clear_effects()` regardless of classification (`pokemon.py:342-344`, `:600`). They are there for downstream consumers — us. — source-verified, grep over `PE`.

**Effect-string coverage against the vendored sim.** Of the **185** literal effect strings greppable out of the vendored sim's `-start/-activate/-singleturn/-singlemove/-end` calls, **12 fall to `Effect.UNKNOWN`**: `ability:` (bare), `ability: Magma Armor`, `ability: Mega Sol`, `ability: Neutralizing Gas`, `ability: Persistent`, `healreplacement`, `item: Mystery Berry`, `move:` (bare), `move: Beat Up`, `move: Happy Hour`, `move: Shell Trap`, `quarkdrive`. **Only two of those are gen-4-legal: `move: Beat Up` and `ability: Magma Armor`** (Magcargo, Camerupt). *Caveat:* my grep captured only single-quoted three-argument literal forms, so this is a **lower bound** — template-literal and computed effect names were not captured. *Status:* tree-verified with the stated caveat; artefact at `scratchpad/research/_effect_strings.txt`.

### 1.7 `must_recharge`, `preparing`, `protect_counter`, `first_turn`, `revealed`

| Field | Semantics | Status | Citation |
|---|---|---|---|
| `must_recharge` | plain bool; set True by `-mustrecharge`, cleared at the top of `moved()` and by `switch_out`. Live in gen 4 (Hyper Beam, Giga Impact, Blast Burn, …: `self.volatileStatus == "mustrecharge"` on 7 gen-4 moves). | source-verified | `pokemon.py:1168-1178`, `:465`, `:604`; `abstract_battle.py:1009-1011` |
| `preparing` | `bool(_preparing_target) or bool(_preparing_move)`; set by `-prepare`, cleared on `moved()` / `switch_out` / Power Herb. Live in gen 4 (Fly, Dig, Dive, Bounce, Shadow Force, Solar Beam, Razor Wind, Sky Attack). `preparing_move` gives the actual `Move`. | source-verified | `pokemon.py:1222-1244`, `:505-513`; `abstract_battle.py:1012-1023` |
| `protect_counter` | incremented in `moved()` when `move.is_protect_counter and not failed`, zeroed otherwise; zeroed on `switch_out` and by any `breaks_protect` effect. `_PROTECT_COUNTER_MOVES` = `{protect, detect, endure, spikyshield, kingsshield, banefulbunker, burningbulwark, obstruct, maxguard, silktrap, wideguard, quickguard}` — for gen 4 that is **protect / detect / endure** only. | source-verified | `move.py:18-31`, `:438-445`; `pokemon.py:477-480`, `:565`, `:607` |
| `first_turn` | `_active_turns == 1`; `_active_turns` is bumped in `end_turn()` and zeroed on `switch_out`. This is the Fake Out feature (Fake Out is gen-3+, live in gen 4). | source-verified | `pokemon.py:1023-1029`, `:412-413`, `:603` |
| `revealed` | set True in `switch_in`. Never reset. The count of revealed opponent mons is the fog-of-war signal. | source-verified | `pokemon.py:583-587`, `:1254-1260` |

### 1.8 `moves` dict and PP

- `moves` is `Dict[str, Move]` behind a `MoveSet` that transparently swaps in Transform / Mimic move sets (`pokemon.py:1160-1166`, `:920-927`, `:1152-1158`). **source-verified.**
- **PP is tracked client-side for both sides.** `Move._current_pp` starts at `max_pp` and is decremented only by `Move.use()`, which is called from `Pokemon.moved()` on the `move` protocol event. `use(pressure=True)` decrements 2. `max_pp = entry["pp"] * 8 // 5` (PP Ups assumed maxed; the `gen < 3` cap at 61 and the `gen >= 5` transform clamp do not apply to gen 4). **source-verified**, `move.py:113-131`, `:470-482`; `pokemon.py:457-475`.
- **poke-env asserts its own gen-4 PP tracking is exact.** `check_move_consistency` runs `assert move_request["pp"] == move.current_pp` for every gen **except** `[1,2,3,7,8]` — the comment says early gens are excluded "because of unreliable Showdown event messages" and 7/8 for Z/Max untrackability. **Gen 4 is inside the checked set.** This only fires under `strict_battle_tracking=True`, but it is the maintainers' own statement that gen-4 PP tracking is trustworthy. **source-verified**, `pokemon.py:261-306`.
- Pressure doubling is applied via `AbstractBattle._pressure_on`, which requires the *target's* ability to already read `"pressure"`. Of the 22 Pressure species in the gen-4 randbats pool, **20 are single-ability and therefore auto-known from first sight**; only Absol and Aerodactyl are ambiguous. **source-verified (PE) + tree-verified (pool)**, `abstract_battle.py:1196-1222`.
- `Leppa Berry` restores 10 PP via a dedicated `-activate` branch (`abstract_battle.py:880-884`). Gen-4-legal but not in the randbats item pool.

### 1.9 `level`, `gender`, and the dynamax / tera guards

- `level` and `gender` are parsed out of `details` in `_update_from_details`; level defaults to 100 when the field is absent, gender defaults to `PokemonGender.NEUTRAL`. **source-verified**, `pokemon.py:669-716`.
- **All gimmick state is inert in gen 4, cleanly.** `can_mega_evolve` / `can_z_move` / `can_dynamax` / `can_tera` are reset to `False` at the top of every `parse_request` and only set from request keys `canMegaEvo` / `canZMove` / `canDynamax` / `canTerastallize`, none of which a gen-4 server sends. `is_dynamaxed` is `Effect.DYNAMAX in effects` → never. `is_terastallized` → `False`; `tera_type` → `None`. `stab_multiplier` therefore returns 1.5 (or 2.0 with Adaptability — gen-4-legal, e.g. Porygon-Z). **source-verified**, `battle.py:81-131`, `:192-222`; `pokemon.py:1086-1100`, `:1310-1333`.
- **Consequence for the action head:** `SinglesEnv.get_action_space_size(gen)` gives `num_gimmicks = 0` for every gen ≤ 5, so the gen-4 action space is **6 switches + 4 moves = 10**, byte-identical in shape to gen 1. **source-verified**, `PE/environment/singles_env.py:290-305`, `:76-140`.

---

## 2. `Battle` fields

### 2.1 `weather` — a turn *stamp*, refreshed every turn; no duration is recoverable

`_weather: Dict[Weather, int]`, and the `-weather` handler is:

```python
elif event[1] == "-weather":
    weather = event[2]
    if weather == "none":
        self._weather = {}
        return
    else:
        self._weather = {Weather.from_showdown_message(weather): self.turn}
```
(`abstract_battle.py:754-761`) — **source-verified.**

Showdown emits `-weather|<W>|[upkeep]` on **every** turn's residual phase (`SD/data/conditions.ts:507,539,585,621,656,681` — **tree-verified**), and poke-env does not look past `event[2]`, so the stored int is **"the turn on which weather was last seen", not "the turn weather started"**. `battle.turn - list(battle.weather.values())[0]` is therefore ~0–1 always and **carries no information about remaining weather turns**. An encoder that wants "turns of Sandstorm left" must count it itself off the start message, or do without.

The dict is also **replaced, not updated**, so it holds at most one weather — correct for gen 4. Gen-4-reachable members: `SANDSTORM`, `RAINDANCE`, `SUNNYDAY`, `HAIL`. (`SNOWSCAPE`/`SNOW` is gen 9; `PRIMORDIALSEA`/`DESOLATELAND`/`DELTASTREAM` gen 6.) `Weather.from_showdown_message` falls back to `Weather.UNKNOWN` with a warning, never raises. — source-verified, `PE/battle/weather.py:7-46`.

Permanent ability weather (Sand Stream, Drizzle, Drought, Snow Warning — Tyranitar, Hippowdon, Kyogre, Groudon, Abomasnow in the pool) appears as a normal `-weather|Sandstorm|[from] ability: Sand Stream|[of] p1a: Tyranitar`; poke-env stores the same single-entry dict and **discards the `[from]`/`[of]`** (§1.2). Whether gen-4 ability weather is infinite-duration or 5-turn is a mechanics question I did not verify — **needs-live-verification / hand off to `mechanics_delta.md`**. *Post-ladder check:* start one gen-4 battle with Tyranitar, log 10 turns of `_replay_data`, and confirm whether a `-weather|none` ever arrives without a replacement.

### 2.2 `fields` — `Field` enum, gen-4 members, turn stamps

`_fields: Dict[Field, int]`, written as `self._fields[field] = self.turn` in `field_start` (`abstract_battle.py:437-448`) — again a **start-turn stamp**, and here it genuinely *is* the start turn (there is no field upkeep message), so `battle.turn - fields[F]` is the elapsed count. `_field_end` pops (and `.pop(field)` will `KeyError` for anything but `NEUTRALIZING_GAS` if the field was never started). — source-verified.

`Field` has 15 members (`PE/battle/field.py:13-27`). **Gen-4-reachable: `TRICK_ROOM` and `GRAVITY`** (both `pseudoWeather` moves in `gen4moves.json`), plus `MUD_SPORT` / `WATER_SPORT` **which in gen 4 are per-mon volatiles, not fields** — this is the one place poke-env's model is generation-wrong for us, and it shows up as `Effect.UNKNOWN` on the volatile side (§1.6). Terrains (`ELECTRIC/GRASSY/MISTY/PSYCHIC_TERRAIN`), `MAGIC_ROOM`, `WONDER_ROOM`, `NEUTRALIZING_GAS`, `FAIRY_LOCK` are gen 5+/6+. `Field.from_showdown_message` degrades to `Field.UNKNOWN` with a warning. — source-verified + tree-verified (`gen4moves.json` `pseudoWeather` values: trickroom, gravity, mudsport, watersport).

### 2.3 `side_conditions` / `opponent_side_conditions` — layers vs turn stamps

```python
def _side_start(self, side, condition_str):
    conditions = self.side_conditions if side[:2] == self._player_role else self.opponent_side_conditions
    condition = SideCondition.from_showdown_message(condition_str)
    if condition in STACKABLE_CONDITIONS:
        conditions[condition] = conditions.get(condition, 0) + 1
    elif condition not in conditions:
        conditions[condition] = self.turn
```
(`abstract_battle.py:1238-1247`) — **source-verified.**

- `STACKABLE_CONDITIONS = {SPIKES: 3, TOXIC_SPIKES: 2}` (`PE/battle/side_condition.py:95`). For those two the value is a **layer count** (the dict's `3`/`2` are documentation, **not** an enforced cap in `_side_start` — the code just increments; the server won't overshoot).
- For **everything else the value is the turn the condition started**, and there is no upkeep refresh, so `battle.turn - side_conditions[REFLECT]` is elapsed turns. To get *remaining* turns you must know the duration yourself: gen-4 Reflect/Light Screen are **5 turns, or 8 with Light Clay** (Light Clay is in the gen-4 randbats item pool — `SD/data/random-battles/gen4/teams.ts`), Safeguard/Mist/Lucky Chant/Tailwind 5/5/5/3. Durations: **literature-only**, not re-checked in the vendored gen-4 mod.
- **`Stealth Rock` is one bit, not a count** — it is not in `STACKABLE_CONDITIONS`, so it stores a turn stamp. That is correct (SR does not stack) but means an encoder must special-case its slot: SPIKES ∈ {0,1,2,3}, TOXIC_SPIKES ∈ {0,1,2}, STEALTH_ROCK ∈ {absent, present}.
- All the gen-4 members exist in the enum: `STEALTH_ROCK`, `SPIKES`, `TOXIC_SPIKES`, `REFLECT`, `LIGHT_SCREEN`, `SAFEGUARD`, `MIST`, `TAILWIND`, `LUCKY_CHANT` (`PE/battle/side_condition.py:14-37`). `STICKY_WEB` is gen 6, `AURORA_VEIL` gen 7, the G-Max/pledge/guard members gen 8/5/5.
- `side_end` **pops silently** and `from_showdown_message` degrades to `UNKNOWN` with a warning — no crash path.
- `-swapsideconditions` (Court Change) swaps the two dicts wholesale; gen 8+, dead in gen 4.
- The nine gen-4 `sideCondition` values in `gen4moves.json` are reflect, lightscreen, safeguard, mist, luckychant, tailwind, spikes, toxicspikes, stealthrock — all nine resolve through `SideCondition.from_data`. — source-verified.

### 2.4 `turn`, `force_switch`, `trapped` / `maybe_trapped`

- `turn` is set from the `|turn|N` message via `end_turn(N)`, which also calls `Pokemon.end_turn()` on both actives (bumping `_active_turns`, the toxic counter, and every turn-countable effect). **source-verified**, `abstract_battle.py:1333-1338`.
- `force_switch` is `request.get("forceSwitch", [False])[0]` — a plain bool for singles. **source-verified**, `battle.py:90`, `:224-231`.
- `trapped` ← `active_request["trapped"]`; `maybe_trapped` ← `active_request["maybeTrapped"]`. Both reset to `False` at the top of each `parse_request`. **source-verified**, `battle.py:85-131`.
- **`maybe_trapped` is live in gen 4 and dead in gen 1.** Showdown sets `maybeTrapped` when the opponent *might* be a trapper; the gen-4 randbats pool contains **four** trapping-ability species — Dugtrio (Arena Trap), Wobbuffet (Shadow Tag), Magnezone and Probopass (Magnet Pull). This is a new, real decision-relevant bit for the gen-4 encoder. **tree-verified** (`SD/sim/side.ts:988-998`, `SD/sim/pokemon.ts:132-133`; pool join against `gen4pokedex.json`).
- When `trapped` is True, `parse_request` populates **no** `available_switches` at all (`battle.py:133-140`), so the action mask collapses to moves only.

### 2.5 Team preview — **a gen-4 randbats battle never gets one**

`[Gen 4] Random Battle` in the vendored server is:

```
name: "[Gen 4] Random Battle",
mod: 'gen4',
team: 'random',
bestOfDefault: true,
ruleset: ['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod'],
```
(`SD/config/formats.ts:4239-4244`) — **tree-verified.** There is **no `Team Preview` rule**, so no `|poke|`, no `|clearpoke|`, no `teamPreview` key in the request. Consequently `battle.teampreview` stays `False`, `teampreview_opponent_team` stays empty, `max_team_size` stays `None`, and `in_team_preview` never flips. (Team Preview enters at gen 5, and even then only for formats that opt in.) The encoder gets the same cold-open fog of war as gen 1. Two side effects worth noting: `HP Percentage Mod` means opponent HP arrives as `xx/100` (so `current_hp_fraction` is percent-granular for the opponent, exact for us), and `Sleep Clause Mod` bounds the opponent's asleep count at 1.

### 2.6 How the opponent's team is revealed and stored

`_opponent_team: Dict[str, Pokemon]` keyed by the `"p2: Nickname"` identifier, populated lazily by `AbstractBattle.get_pokemon` on the first `|switch|`/`|drag|` naming that mon (`abstract_battle.py:192-330`). With no team preview, the dict grows from 0 to at most 6 over the battle; `revealed` is True for every member of it by construction. `battle.opponent_team` is therefore *both* the reveal set and the identity set — there is no "6 unknown slots" scaffold, which is exactly the gen-1 situation and means the gen-1 encoder's "pad to 6 with an unknown embedding" trick carries over unchanged. **source-verified.** Note `SimpleHeuristicsPlayer` hard-codes `6 - len(fainted)` for the opponent's remaining count (`PE/player/baselines.py:280-282`), which is right for gen-4 randbats (always 6).

### 2.7 History / event log an encoder could use

- **`battle._replay_data` is populated unconditionally.** `parse_message` begins `self._replay_data.append(split_message[:])` regardless of `save_replays` (`abstract_battle.py:565-566`). So the **entire raw protocol log of the battle is in memory** and is the only place to recover: crits (`-crit`), misses (`-miss`), effectiveness (`-supereffective`/`-resisted`/`-immune`), failures (`-fail`, `-block`), hit counts (`-hitcount`), and the `[from]` provenance strings poke-env otherwise drops (the Encored/Disabled move name, the weather-setter's ability). All of those are in `MESSAGES_TO_IGNORE` (`abstract_battle.py:20-70`) and therefore absent from the object model. **source-verified.** This is an under-used seam and worth flagging to the encoder doc.
- Per-mon last move: `Pokemon.last_move` scans `moves.values()` for `_is_last_used`, which `moved()` maintains (`pokemon.py:1123-1132`, `:470-475`). Set on the mover, cleared on the others; all cleared on `switch_out`. There is **no history of the previous N moves** and **no "what the opponent did last turn" field** beyond this one flag.
- `battle.rules` accumulates `|rule|` lines — for gen-4 randbats it will read the four clauses above. **source-verified** (`abstract_battle.py:900-901`) + **tree-verified** (which rules).

---

## 3. Moves — `gen4moves.json` and the `Move` wrapper

**Size and shape.** `gen4moves.json` holds **486 entries** (vs 168 for gen 1 — a **2.9×** move vocabulary). `num` runs 1..467 with three synthetic negatives (`paleowave` −1, `shadowstrike` −2, `polarflare` −3); **483 entries fall in `[1, 467]`**, which confirms the `move_num_range=(1, 467)` figure the landed seam's docstring anticipates. Three entries are `isNonstandard: "CAP"`; 107 more carry an explicit `"isNonstandard": null`. — source-verified (`PE/data/static/moves/gen4moves.json`, parsed) + tree-verified against `SNAP/rl/envs/encoder_spec.py:67-68`.

| Property | Gen-4 semantics | Status | Citation |
|---|---|---|---|
| `category` | **`if self.gen <= 3 … return self._MOVE_CATEGORY_PER_TYPE_PRE_SPLIT[self.type]` — gen 4 is on the other side of the guard**, so `MoveCategory[entry["category"].upper()]` is read straight from the data, per move. Distribution over the 486: **192 Physical, 124 Special, 170 Status** (gen 1: 76/37/55). | source-verified | `PE/battle/move.py:209-215`, `:57-76` |
| `defensive_category` | reads `overrideDefensiveStat` (`def`→PHYSICAL, `spd`→SPECIAL) else falls back to `category`. Gen-4-relevant for Psyshock? — no, Psyshock is gen 5; in gen 4 this is effectively `category`. | source-verified | `move.py:262-278` |
| `base_power` | `entry.get("basePower", 0)`, overridden for Hidden Power when the raw id carries digits. | source-verified | `move.py:174-183`, `:100-111` |
| `accuracy` | `True` → `1.0`, else `/100`. | source-verified | `move.py:163-172` |
| `priority` | straight from data. **Gen 4's priority range is −7..+5** across 12 distinct values (`{-7:1, -6:2, -5:2, -4:2, -3:1, -1:1, 0:458, 1:11, 2:1, 3:3, 4:3, 5:1}`) versus gen 1's three values (`{-1:1, 0:166, 1:1}`). Priority is a real gen-4 feature (Trick Room −7, Roar/Whirlwind −6, Vital Throw −4, Sucker Punch/Extreme Speed/Fake Out/Protect at +1..+4, Helping Hand +5). | source-verified | `move.py:514-521`; both JSONs parsed |
| `pp` / `max_pp` | `max_pp = entry["pp"] * 8 // 5` (PP Ups maxed). See §1.8. | source-verified | `move.py:470-482` |
| `secondary` | normalises `secondary` (single dict → 1-element list) and `secondaries` (list). 105 gen-4 moves have `secondary`, 3 have `secondaries`. | source-verified | `move.py:578-589` |
| `boosts` | `entry.get("boosts")` — boosts inflicted on the **target**. 45 gen-4 moves. | source-verified | `move.py:184-190` |
| `self_boost` | `entry["selfBoost"]["boosts"]` or `entry["self"]["boosts"]`. | source-verified | `move.py:591-601` |
| `heal` | `entry["heal"][0]/[1]` — **the `if self.gen == 1: return 1/2` special case does not apply to gen 4**. 6 gen-4 moves have `heal`. | source-verified | `move.py:373-384` |
| `drain` | `entry["drain"][0]/[1]`. 6 gen-4 moves. | source-verified | `move.py:279-288` |
| `recoil` | `entry["recoil"][0]/[1]`, or `0.25` for `struggleRecoil`. 8 gen-4 moves + Struggle. | source-verified | `move.py:530-541` |
| `self_switch` | `entry.get("selfSwitch", False)` — **3 gen-4 moves** (U-turn, Baton Pass, and one other). | source-verified | `move.py:611-618` |
| `force_switch` | `entry.get("forceSwitch", False)` — **2 gen-4 moves** (Roar, Whirlwind). Circle Throw / Dragon Tail are gen 5. | source-verified | `move.py:357-364` |
| `volatile_status` | returns an **`Effect`**, via `Effect.from_data`, checking `volatileStatus`, then `secondary[].volatileStatus`, then `self.volatileStatus`. 51 gen-4 moves have a top-level `volatileStatus`. Coverage: 44/46 distinct values map (§1.6). | source-verified | `move.py:717-736` |
| `side_condition` | returns a **`SideCondition`** via `from_data`; 9 gen-4 moves, all mapping. | source-verified | `move.py:619-629` |
| `weather` | returns a **`Weather`** via `Weather[entry["weather"].upper()]` — **this one raises `KeyError`, it does not degrade**. 4 gen-4 moves (Sandstorm, Rain Dance, Sunny Day, Hail), all of which are `Weather` members. | source-verified | `move.py:737-745` |
| `status` | returns a **`Status`** via `Status[entry["status"].upper()]` — also a raising lookup. 14 gen-4 moves, all mapping to the 7 members. | source-verified | `move.py:654-663` |
| `flags` | `set(entry["flags"]) | (set(entry.keys()) & _MISC_FLAGS)` — a *union* of the data flags and 19 callback-key names. The docstring warns "This property is not well defined, and may be missing some information." Gen-4 flags that matter: `contact`, `protect`, `mirror`, `sound`, `punch`, `bite`(gen4? — via items), `snatch`, `reflectable`, `bypasssub`, `authentic`. | source-verified | `move.py:343-355`, `:35-55` |
| `target` | `Target.from_showdown_message(entry["target"])` — **this one `raise KeyError` on an unknown target** (`target.py:52-60`). Gen-4 distribution over 486: `normal` 335, `self` 69, `allAdjacentFoes` 25, `any` 17, `all` 10, `allAdjacent` 8, `allySide` 6, `randomNormal` 5, `foeSide` 3, `scripted` 3, `allyTeam` 2, `adjacentAlly`/`adjacentAllyOrSelf`/`adjacentFoe` 1 each. All 14 are `Target` members. | source-verified | `move.py:672-681`; `PE/battle/target.py:16-30` |
| `is_protect_move` / `is_protect_counter` / `is_side_protect_move` | membership in module-level sets; gen-4-live members are **protect, detect, endure** (counter) and **protect, detect, endure** (protect). | source-verified | `move.py:18-31`, `:438-460` |
| `breaks_protect` | `entry.get("breaksProtect", False)` — **2 gen-4 moves** (Feint; Shadow Force). | source-verified | `move.py:192-198` |
| `expected_hits` | For 2–5-hit moves it returns `(2+3)/3 + (4+5)/6 = 3.1667`, which is the **gen-5+** distribution (⅓,⅓,⅙,⅙). **Gen 4's distribution is ⅜,⅜,⅛,⅛ → E = 3.0.** So `expected_hits` is ~5.6% high for every gen-4 multi-hit move (17 have `multihit`), and it is used by `SimpleHeuristicsPlayer`'s move score. Triple Kick gets its own hard-coded `1 + 2·0.9 + 3·0.81`. | source-verified (PE) + literature-only (the gen-4 distribution itself; I did **not** locate the sampling code in the vendored `sim/`) | `move.py:321-342` |
| `crit_ratio` | `int(entry["critRatio"])` (19 gen-4 moves), or 6 if `willCrit`, else 0. Note gen-4 crit *stages* map differently from gen 5+ and the crit multiplier in gen 4 is **2.0** (gen 5+: 1.5) — an engineered damage feature must not borrow the gen-9 constant. Multiplier claim: **literature-only**. | source-verified (the property) | `move.py:218-229` |
| `sleep_usable` | `entry.get("sleepUsable", False)` — **exactly 2 gen-4 moves** (Sleep Talk, Snore). | source-verified | `move.py:630-637` |
| `thaws_target` | `entry.get("thawsTarget", False)` — **`thawsTarget` appears on ZERO gen-4 moves**, so this is constant `False` for us. (Thawing the *target* is gen 6+; gen-4 Flame Wheel/Sacred Fire thaw the *user*, expressed differently.) | source-verified | `move.py:693-700`; key-frequency scan of `gen4moves.json` |
| `damage` | `entry.get("damage", 0)`; 4 gen-4 moves (Seismic Toss/Night Shade style `"level"`, Sonic Boom 20, Dragon Rage 40). | source-verified | `move.py:238-246` |
| `n_hit`, `ignore_ability/defensive/evasion/immunity`, `steals_boosts`, `stalling_move`, `self_destruct`, `slot_condition`, `non_ghost_target`, `no_pp_boosts`, `use_target_offensive`, `pseudo_weather`, `terrain` | all thin `entry.get` wrappers; `terrain` is dead in gen 4, `pseudo_weather` is live (trickroom/gravity/mudsport/watersport). `nonGhostTarget` is on exactly 1 gen-4 move (Curse). | source-verified | `move.py:483-513`, `:522-529`, `:603-618`, `:638-653`, `:664-671`, `:682-692`, `:709-716` |

**SPECIAL_MOVES aliasing.** `SPECIAL_MOVES = {"struggle", "recharge", "fight"}` (`move.py:17`). `Move.should_be_stored` returns `False` for all three, so they never enter `Pokemon.moves` (`move.py:150-162`). `Move.entry` synthesises a stub `{"pp":1,"type":"normal","category":"Special","accuracy":1}` for `recharge` and `fight` — but **`struggle` is a real entry in `gen4moves.json`** (`basePower: 50`, Physical, `struggleRecoil: true`, `target: randomNormal`, `noPPBoosts`), so it resolves through the data path. **`"fight"` is a gen-1-only placeholder** and does not appear in `gen4moves.json`; the gen-4 spec can drop it from `special_move_ids`, and only `{"struggle","recharge"}` need to be handled. The consequence the landed seam already documents holds unchanged: when a `SPECIAL_MOVES` entry is the *only* legal move, `SinglesEnv.action_to_order` re-bases the move index onto `available_moves` rather than the mon's own move list. — source-verified, `move.py:17`, `:150-162`, `:301-320`; `PE/environment/singles_env.py:122-131`; `SNAP/rl/envs/encoder_spec.py:91-94`, `:244`.

**A gen-4 move type the gen-1 spec has no slot for: `???`.** Exactly one gen-4 move is `"type": "???"` — **Curse** — and `PokemonType.from_name("???")` returns `PokemonType.THREE_QUESTION_MARKS`, which `damage_multiplier` short-circuits to `1`. Gen-4 move types otherwise span the 17 real types (no Fairy). — source-verified, `gen4moves.json` parsed; `PE/battle/pokemon_type.py:37-38`, `:61-66`, `:81-83`.

---

## 4. The gen-4 type chart — **it has 18 keys, and Fairy is one of them**

`GenData.load_type_chart(gen)` reads `gen{gen}typechart.json`, builds an N×N dict from **every key in the file**, and asserts squareness. It performs **no `isNonstandard` filtering.** — source-verified, `PE/data/gen_data.py:73-109`.

`gen4typechart.json` has **18 keys**: bug, dark, dragon, electric, **fairy**, fighting, fire, flying, ghost, grass, ground, ice, normal, poison, psychic, rock, steel, water. The fairy entry carries `"isNonstandard": "Future"` — which `load_type_chart` ignores. **So `GenData.from_gen(4).type_chart` is an 18×18 dict with a live `"FAIRY"` row and column.** (The same is true of `gen1typechart.json`, so this is not new — but it means "gen 4 has 17 types" is a statement about the *game*, not about the object poke-env hands you.) — source-verified, both files parsed.

Multiplier semantics: the JSON stores `damageTaken` from the defender's perspective with the encoding `0 → 1×, 1 → 2×, 2 → 0.5×, 3 → 0×`, and `type_chart[DEFENDER][ATTACKER]` is the result; anything absent from a `damageTaken` block silently stays at the initialised `1.0`. `PokemonType.damage_multiplier(type_1, type_2, type_chart=…)` multiplies the two defending types and returns `1` outright if either side is `THREE_QUESTION_MARKS` or `STELLAR`. — source-verified, `gen_data.py:84-109`; `pokemon_type.py:43-70`.

Two consequences worth putting in `encoder_requirements.md`:

1. The **fairy row in `gen4typechart.json` is the modern (gen-6) defensive profile** — Dragon 0×, Dark/Fighting/Bug 0.5×, Poison/Steel 2× — but the fairy *column* is incomplete: several defending types' `damageTaken` blocks (Steel's, for one) have **no `Fairy` key at all**, so `type_chart["STEEL"]["FAIRY"]` defaults to `1.0` rather than the modern `2.0`. The chart is internally inconsistent on Fairy. This costs us **nothing** as long as we never construct a Fairy type or a Fairy move — and we cannot: no gen-4 move is Fairy-typed, and the only Fairy-typed entries in `gen4pokedex.json` are non-gen-4 formes (megas, CAP mons, Galar/Alola forms) none of which is in the 295-species randbats pool (Clefable is `["Normal"]` in the gen-4 dex, with abilities Cute Charm / Magic Guard). **But a gen-4 `EncoderSpec` that naively does `types=tuple(PokemonType)` or enumerates the chart's keys will silently allocate a Fairy slot that is always zero.** The spec must list the 17 explicitly, exactly as `GEN1` lists its 15.
2. `Pokemon.damage_multiplier` uses `type_1`/`type_2` and the raw chart only — it knows nothing about Levitate, Flash Fire, Wonder Guard, Thick Fat, or Iron Ball/Air Balloon/Gravity. Ability-based immunities are a **gen-4 encoder responsibility**; `AbstractBattle.is_grounded` is the only ability-aware helper and it covers Ground immunity alone (Gravity → grounded; Iron Ball → grounded; Levitate → not; **`ability is None and "levitate" in possible_abilities` → not grounded**, i.e. it optimistically assumes the hidden ability *is* Levitate; Air Balloon → not; Flying type → not; Magnet Rise → not). 23 pool species can have Levitate. — source-verified, `pokemon.py:842-858`; `abstract_battle.py:548-563`.

---

## 5. Damage-calc modules: **there is nothing for gen 4**

`PE/calc/` contains exactly two modules: `damage_calc_gen1_2.py` (492 lines) and `damage_calc_gen9.py` (1869 lines). `PE/calc/__init__.py` is three lines and exports **only** the gen-9 pair:

```python
from poke_env.calc.damage_calc_gen9 import calculate_base_power, calculate_damage
__all__ = ["calculate_damage", "calculate_base_power"]
```
— source-verified, `PE/calc/__init__.py:1-3`.

- `damage_calc_gen1_2.py` is explicitly ported from `smogon/damage-calc` `mechanics/gen12.ts` and branches on `battle.gen == 1` / `== 2` throughout (lines 86, 95, 138, 177–193, 278, 306, 318, 336, 426). It is **not exported** and is useless for gen 4.
- `damage_calc_gen9.py` has **no generation guard anywhere** — a grep for `gen ==` / `gen <=` / `gen >=` inside it returns nothing but a single `GenData.from_gen(battle.gen).pokedex[...]` lookup at line 1356. Its docstring says only "several edge cases are ignored and behaviour may deviate from the official damage calculator". Running it on a gen-4 battle would apply gen-9 mechanics wholesale: the wrong crit multiplier (1.5 vs gen 4's 2.0), gen-9 screen multipliers, gen-9 burn/Life Orb ordering, gen-9 ability and item effects (Punching Glove, Unseen Fist, Terablast, Photon Geyser are all referenced), and — via `Pokemon.damage_multiplier` — the 18-type chart. — source-verified, `calc/damage_calc_gen9.py:31-120` and gen-guard grep. Crit-multiplier delta: **literature-only.**
- **Both calculators hard-assert that every stat is a number** — `assert all(map(lambda x: isinstance(x,int) or isinstance(x,float), attacker.stats.values())), "attacker stats not defined"` and the same for the defender (`damage_calc_gen9.py:60-71`; `damage_calc_gen1_2.py:47-58`). Since opponent `stats` are permanently `None` (§1.3), **neither calculator can be called with an opponent on either side without us filling `stats` first**.

**Implication for an engineered damage feature.** Any "expected damage" input to a gen-4 encoder has to be ours: fill opponent `stats` from the §1.3 closed form, then either (a) write a small gen-4 damage function, or (b) reuse `foul-play`'s gen-4 calc if it has one (a question for the anchors agent — I did not open `FP`). Whichever we do, `poke_env.calc` is a false friend here in the same way `scripts/score_ladder.py` is on the ladder side.

---

## 6. Failure modes, TODOs, and where a gen-4 message would land in an unknown bucket

**Explicit TODO/FIXME/HACK markers in the whole `poke_env` package: none.** The only self-flagged gaps are four comments/docstrings: `pokemon.py:301-302` ("exclude early gens because of unreliable Showdown event messages… gen 7 and 8 because of Z-move and Max Move PP untrackability"), `pokemon.py:895` (`available_z_moves`: "Caution: this property is not properly tested yet"), `move.py:346` (`flags`: "not well defined, and may be missing some information"), `abstract_battle.py:1251` (`_swap`: logs "swap method in Battle is not implemented" — doubles-only). — source-verified, grep over `PE`.

**Hard failure paths** (these raise, they do not warn):

| Path | Trigger | Gen-4 risk | Status |
|---|---|---|---|
| `parse_message` final `else: raise NotImplementedError(event)` | any protocol message type not handled and not in `MESSAGES_TO_IGNORE` | **Low.** I diffed poke-env's 62 handled types + 51 ignored types against every `add('…')` message name greppable out of the vendored `sim/`, `data/mods/gen4/`, `data/{moves,abilities,items,conditions,scripts}.ts`. The only unmatched names are `-candynamax` (gen 8, never sent by a gen-4 battle), `bigerror` (intercepted by `Player._handle_battle_message` at `player.py:328-329` before it reaches `parse_message`), `win`/`tie` (routed to `battle.won_by`/`battle.tied` at `player.py:306-310`), and `showteam` — which is genuinely **not** handled and *would* raise, but is emitted only for Open Team Sheets, a gen-9 VGC feature. **No gen-4-reachable message type is unhandled.** | tree-verified (emission side) + source-verified (handling side) |
| `-item` with 6 fields and an unrecognised `[from]` cause: `raise ValueError(f"Unhandled item message: {event}")` | Gen-4-legal 6-field causes are Frisk, Thief, Covet — all three handled. Pickpocket/Magician are gen 5. | **Low but non-zero.** *Post-ladder check:* grep 200 gen-4 replay logs for `\|-item\|` lines with 4 pipe-separated payload fields and confirm the `[from]` cause is one of Frisk/Thief/Covet. | source-verified |
| `Move.entry`: `raise ValueError("Unknown move: %s")` | a move id absent from `gen4moves.json` | Only reachable via Metronome/Copycat/Assist/Mimic pulling something odd; the id-space is closed in gen 4. | source-verified |
| `Move.target`: `raise KeyError` from `Target.from_showdown_message` | all 14 gen-4 target strings are members | none | source-verified |
| `Move.weather` / `Move.status`: bare `Weather[...]` / `Status[...]` | all gen-4 values are members | none | source-verified |
| `_field_end`: `self._fields.pop(field)` without default (except NEUTRALIZING_GAS) | a `-fieldend` for a field never `-fieldstart`ed | shouldn't happen; a mid-battle reconnect could | source-verified |
| `PokemonType.from_name` KeyError | `gen4pokedex.json` contains one entry typed `"Bird"` (missingno-adjacent) with no `PokemonType` member | not in the randbats pool | source-verified |
| `check_consistency` / `check_move_consistency` assertions | only under `strict_battle_tracking=True`; the PP assertion **is enabled for gen 4** | if we turn strict tracking on for gen 4 and PP tracking drifts (Pressure on an unrevealed Absol/Aerodactyl), the battle dies. **needs-live-verification.** *Post-ladder check:* run 20 gen-4 self-play battles with `strict_battle_tracking=True` and count assertion failures. | source-verified |

**Soft (warning-only) unknown buckets** — these are where a gen-4 message *content* lands without crashing: `Effect.UNKNOWN` (`effect.py:265-271`), `SideCondition.UNKNOWN` (`side_condition.py:58-65` and `:84-91`), `Weather.UNKNOWN` (`weather.py:39-45`), `Field.UNKNOWN` (`field.py:51-58`). All four log through `logging.getLogger("poke-env")`. Measured gen-4 exposure (§1.6): 2 of 46 move volatiles (`mudsport`, `watersport`); 2 of 185 literal sim effect strings (`move: Beat Up`, `ability: Magma Armor`). **A cheap, high-value instrumentation step for the gen-4 bring-up is to install a `logging.Handler` on `"poke-env"` at WARNING and count `"Unexpected …"` lines over a few hundred battles.** — *status:* the measurement is **needs-live-verification**; *post-ladder check:* run 500 `gen4randombattle` self-play battles with a counting handler and report the histogram of unknown effect/side-condition/weather/field strings.

---

## 7. gen-1 encoder assumptions this breaks

Against `SNAP/rl/envs/encoder_spec.py` (main@2738025) — the seam is `GEN1` + `spec_for_format` refusing other gens.

1. **`types`: 15 → 17, and the spec must enumerate them.** `GEN1.types` is a hand-listed 15-tuple "Fixed here (not from `PokemonType`, which carries all 20 modern members) so the one-hot layout is stable" (`encoder_spec.py:210-218`). Gen 4 adds Dark and Steel. **Do not derive from the chart** — `GenData.from_gen(4).type_chart` has 18 keys including Fairy (§4). Also budget a 19th "move type" case for `???` (Curse). *tree-verified + source-verified.*
2. **`base_stat_keys`: 5 → 6.** `GEN1` drops `spd` because gen 1 mirrors it from `spa` (`encoder_spec.py:223-224`). Gen 4 has a real Special Defense. *tree-verified + source-verified.*
3. **`special_move_ids`: `{fight, struggle, recharge}` → `{struggle, recharge}`.** `"fight"` is a gen-1-only placeholder and is absent from `gen4moves.json`. *source-verified.*
4. **`species_num_range`: `(1,151)` → `(1,493)`, but `num` is no longer an injective species key.** Over the 295-species gen-4 randbats pool there are only **267 distinct `num` values**: Arceus's 17 formes all share 493, Rotom's 6 share 479, Deoxys's 4 share 386, Wormadam's 3 share 413, Giratina's 2 share 487, Shaymin's 2 share 492. Arceus-Ghost and Arceus-Water have *different types* and identical `num`. **The gen-4 spec must key species on the forme id string (poke-env's `Pokemon.species`, which is the forme id, e.g. `"arceusghost"`), not on `num`.** *tree-verified.*
5. **`move_num_range`: `(1,165)` → `(1,467)`**, and the move vocabulary triples (168 → 486 entries; 483 in range). *source-verified.*
6. **`volatiles` grows and one member must MOVE.** `GEN1.volatiles` is `(CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE, PARTIALLY_TRAPPED, REFLECT, SUBSTITUTE)` (`encoder_spec.py:237-243`). For gen 4: **`REFLECT` must move out of `volatiles` into the side-condition block** (in gen 2+ Reflect and Light Screen are 5-turn side conditions, and `LIGHT_SCREEN` has no `Effect` member at all — a hole the gen-1 spec's own comment already flags); **`PARTIALLY_TRAPPED` must be replaced by the six per-move members** `{BIND, WRAP, FIRE_SPIN, CLAMP, WHIRLPOOL, SAND_TOMB}` because that is what the gen-4 protocol emits (§1.6); and the new gen-4 members are at least `TAUNT, ENCORE, TORMENT, DISABLE, EMBARGO, HEAL_BLOCK, YAWN, ATTRACT, INGRAIN, AQUA_RING, MAGNET_RISE, PERISH0..3, CURSE, DESTINY_BOND, PROTECT, IMPRISON, NIGHTMARE, FORESIGHT, MIRACLE_EYE, POWER_TRICK, GASTRO_ACID, SLOW_START, FLASH_FIRE, FOCUS_ENERGY, LOCKED_MOVE, UPROAR, ROOST, BIDE, STOCKPILE, GRUDGE, SNATCH, MAGIC_COAT, CHARGE, DEFENSE_CURL, MINIMIZE, FUTURE_SIGHT, DOOM_DESIRE, TYPECHANGE, MIMIC, FLINCH, ENDURE, HELPING_HAND, FOLLOW_ME`. *tree-verified + source-verified.*
7. **Whole blocks that do not exist in gen 1 at all.** Items (~26-value vocabulary, three-valued unknown/none/known), abilities (122-value vocabulary over the pool, with the 161/134 known/hidden split), weather (4 members), fields (TRICK_ROOM, GRAVITY), and **two** side-condition blocks (ours and theirs) with 9 members each and mixed layer/turn-stamp semantics. Each is a MON_DIM or OBS_DIM change, i.e. **every existing checkpoint is invalidated** — the landmine the seam's docstring already names. *tree-verified.*
8. **Level is no longer 100.** Gen-1 randbats levels are also variable, but the gen-4 encoder now *needs* the level as a numeric feature because opponent stats are only computable from `(base, level)` (§1.3) — the level is not just a scaling nuisance, it is the input to the one stat estimator we will have. Range 67–100. *tree-verified.*
9. **`status_counter` semantics change (and the seam already anticipates this).** The docstring says "The status COUNTER semantics also move (gen-2 sleep/toxic counters)" (`encoder_spec.py:64-65`). Concretely for gen 4: sleep is 1–4 attempts and `status_counter` tracks them correctly (§1.5), so a sleep-turn feature is *newly worth having*; toxic resets on switch-out.
10. **Two new decision-relevant scalars that are dead in gen 1:** `maybe_trapped` (four trapping-ability species in the pool) and `protect_counter` (Protect/Detect/Endure exist in gen 1 too, but the gen-4 stall mechanic and Substitute+Protect stalling make it load-bearing). *tree-verified + source-verified.*
11. **The action head does NOT change.** `get_action_space_size(4)` = 6 + 4·(1+0) = **10**, identical to gen 1, which is what the seam's own note predicts (`encoder_spec.py:77-80`). One less thing. *source-verified.*
12. **The move-category rule that gen 1 "never assumed" is now live data.** The seam says "`_fill_move` reads poke-env's `move.category`, which is per-move in the gen-4 data already; only the gen-1 'category follows the type' rule stops holding, and the encoder never assumed it" (`encoder_spec.py:49-52`). **Confirmed correct**: `Move.category`'s pre-split branch is gated on `self.gen <= 3` and gen 4 falls through to the data (§3). *tree-verified + source-verified.*

---

## 8. Cross-references for the other docs

- → **`mechanics_delta.md`**: gen-4 sleep is `this.random(2,6)` decremented per move attempt (`SD/data/mods/gen4/conditions.ts:23-52`); gen-4 paralysis is a flat 1/4 with a ×0.25 speed drop (`:7-21`); partial trap is `this.random(3,7)` (`SD/data/mods/gen4/conditions.ts:110-118`); `[Gen 4] Random Battle` ruleset is `['Obtainable','Sleep Clause Mod','HP Percentage Mod','Cancel Mod']` with **no Team Preview** (`SD/config/formats.ts:4239-4244`). Open for you: gen-4 crit multiplier (2.0?) and whether ability weather is infinite in the gen-4 mod — I did not verify either.
- → **`encoder_requirements.md`**: §7 is the direct input. The two hard requirements poke-env does not meet are **opponent stat estimation** (§1.3, closed form supplied) and **any gen-4 damage function** (§5).
- → **`anchors_and_eval.md`**: `SimpleHeuristicsPlayer` (`PE/player/baselines.py:133-360`) has three defects that get *worse* in gen 4 than in gen 1. (a) **`ENTRY_HAZARDS` contains the typo `"stealhrock"`** (`baselines.py:134-139`), so SH cannot recognise Stealth Rock as a hazard-setting move — in a generation whose defining feature is Stealth Rock. (b) The setup-move branch tests `move.target == "self"` (`baselines.py:317`), comparing a `Target` **enum** against a **string**, which is always `False` — **the entire setup-move branch is dead code**. (c) `_stat_estimation` is `((2*base + 31) + 5) * boost` (`baselines.py:249-256`) — **no level term, no EVs**, so with gen-4 randbats levels spanning 67–100 the physical/special ratio it feeds into is systematically wrong. It also ignores items, abilities, weather, screens, priority, and status entirely, and its `expected_hits` is the gen-5 value (§3). *Expect SH to be a substantially weaker gen-4 opponent than a gen-4 player would guess.* All source-verified.
- → **`open_questions.md`**: items 1–4 in §9.
- → **`search_depreciation.md`**: `battle._replay_data` (§2.7) is the full protocol log, free, and is the only route to crit/miss/effectiveness signals — relevant if a search or an opponent model wants observation history.

---

## 9. Open questions for the maintainer

1. **Do we key species on `num` or on the forme id string?** `num` collides across 28 pool entries (Arceus ×17, Rotom ×6, Deoxys ×4, Wormadam ×3, Giratina ×2, Shaymin ×2), and Arceus's formes differ in **type**, which is the single most policy-relevant field. *Recommendation:* key on `Pokemon.species` (the forme id) with a 295-row embedding sized to the randbats pool plus an unknown row. *Losing argument:* `num` is a stable, dense, gen-independent integer that would let a gen-4 embedding be warm-started from gen-1 rows and would generalise to non-randbats formats; forme ids are format-specific and 17 Arceus rows will each see ~1/295 of the data.
2. **Do we fill `Pokemon.stats` for the opponent ourselves, mutating poke-env's objects, or keep a parallel table?** Mutating means `poke_env.calc` and any downstream helper "just works"; a parallel table keeps poke-env's own invariants (and `check_consistency`) clean. *Recommendation:* parallel table in the encoder, because the §1.3 closed form has two documented ambiguities (atk-zeroing, spe-zeroing) that we can only resolve *probabilistically* from the moves we have seen, and writing a guess into `mon.stats` would silently corrupt anything that later trusts it.
3. **Is a gen-4 damage feature in scope for the first gen-4 encoder, given that nothing off the shelf computes it?** *Recommendation:* no for v1 — ship type-effectiveness + base power + category + the stat ratio (what SH already approximates) and treat a real calc as a later lever, exactly as the gen-1 arc did. *Losing argument:* gen 4's damage is far more item/ability-modified than gen 1's, so a naive product-of-features may be a materially worse proxy there than it was here, and the lever may be worth more early.
4. **Do we run gen 4 with `strict_battle_tracking=True`?** It buys a hard PP/item/ability consistency check that poke-env's own authors consider valid for gen 4 — and it turns any tracking drift into a dead battle mid-fleet. *Recommendation:* on for a short bring-up fleet, off for production runs.
5. **Do we patch the Flash Fire drop (§1.6) and the missing Encored/Disabled move name (§1.6), or accept them?** Both are one-line reads off `_replay_data` if we want them; both are small.

---

## 10. Unread / unverified (explicitly)

- `PE/battle/double_battle.py`, `z_crystal.py`, `pokemon_gender.py` (beyond the enum), `PE/teambuilder/`, `PE/ps_client/`, `PE/environment/doubles_env.py`, `PE/player/*` other than `baselines.py` and the `player.py` message-routing grep.
- `PE/calc/damage_calc_gen9.py` lines 120–1869 and `damage_calc_gen1_2.py` lines 60–492 — I read the preambles and grepped the gen guards, nothing more.
- The **gen-4 crit multiplier (2.0)**, the **gen-4 2-to-5-hit distribution (⅜,⅜,⅛,⅛)**, the **gen-4 screen/Safeguard/Tailwind durations**, and the **gen-3+ toxic-reset-on-switch rule** are all stated here as **literature-only** — I did not locate the code for any of them in the vendored `sim/` or `data/mods/gen4/`.
- I did **not** open `FP` (foul-play), `PSPPO`, `MG` (metagrok), `PW/pokejax`, `prior_work/README.md`, or any of the four PDF text dumps. Nothing in this note is sourced from them, and the Metamon/Wang/H&L cross-checks belong to other agents.
- I did **not** start a server, construct a `Player`/`Env`/`PSClient`, run `pytest`, or touch `MAIN/runs`, `MAIN/logs`, `MAIN/results/ladder`, or the network. Every "how does gen 4 actually behave on the wire" claim is tagged **needs-live-verification** with its check.
- The effect-string coverage figure (12 UNKNOWN of 185) is a **lower bound**: my grep captured only single-quoted three-argument `this.add('-start'/'-activate'/…, x, 'literal')` forms and missed template-literal and computed effect names.
- The gen-4 randbats **item vocabulary (~26)** is assembled from two `getItem`/`getPriorityItem` bodies and is approximate; the mechanics agent should enumerate it properly.

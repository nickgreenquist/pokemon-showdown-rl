# gen1 → gen4 mechanics delta — what changes for an encoder and a policy

> **design_gen4 status header.** Written 2026-09-04 on branch `gen4-design` (landed on
> main the same day); **revised 2026-09-05 on branch `gen4-build`** after the local live
> checks (research/live/, 1,530 recorded seat-battles) and the critic pass
> (research/critic_pass.md) — corrections are applied inline with a `critic_pass.md`
> or `research/live/` citation, and each doc ends with a dated live-verification
> section.
> DOCS ONLY — nothing under `rl/` changed. **Arc position:** the target is
> JOURNEY step 3 (gen4 encoder + model). This design work is **maintainer-ruled
> PREPARATION running AHEAD of step 2 (gen1 ladder #3)**; it is not a
> pre-registration and it launches nothing. Method deviation, recorded: the
> brief's two-memo + adversarial-synthesis cycle was NOT run for this doc
> (maintainer ruling 2026-09-04, budget; the 2-Opus cycle is reserved for
> irreversible artifacts and this doc is free to rewrite). It is a single-writer
> synthesis of one research note per source family.
>
> **Verification status per claim** — every claim carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo
>   (main@2738025) or the vendored `showdown/` (pokemon-showdown 0.11.11 @
>   59da482, gitignored): the game as we actually run it.
> - `[src]` **source-verified** — checked against an external primary source
>   on disk (installed poke-env 0.15.0 under `poke_env/`).
> - `[lit]` **literature-only** — not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running server or battle can
>   confirm it; BARRED until the live ladder run and any later fleet complete;
>   the check is stated beside the tag.
>
> **Paths.** `showdown/...` = the vendored server tree; `poke_env/...` = the
> installed package; `rl/...` = this repo. Line numbers are from the files as
> read on 2026-09-04.
> **Sources read for this doc:** research note `showdown_gen4_mechanics.md`
> (every `showdown/` citation below was read there from the `.ts` sources and,
> for the merged move table, from `showdown/dist/data/**/moves.js`, spot-checked
> against the `.ts`), plus `showdown_gen4_pool.md` §1/§7 (format entry, EV/IV/HP
> rules), `showdown_gen4_abilities_items.md` §1–4 (ability/item universes and
> the reveal model), `pokeenv_battle_state.md` §4 (poke-env's type chart).
> **Feeds:** `encoder_requirements.md` (§15 is written to be lifted),
> `pokeenv_gen4_survey.md` (§11 reveal classes), `anchors_and_eval.md` (§12
> turn cap, §14 what SH cannot model), `open_questions.md` (§16).

## 0. The five deltas that change the encoder's shape

| # | delta | what it forces | status |
|---|---|---|---|
| 1 | **Move category is a per-move field.** The type→category rule lives in the gen3 mod (`showdown/data/mods/gen3/scripts.ts:4-14`) and does not apply to gen4; gen4 reads `category` off `showdown/data/moves.ts` via `Battle#getCategory` (`showdown/sim/battle.ts:2384-2386`). 97 gen4-legal moves would be mis-categorised by type (§3). | No new table — poke-env's `move.category` is already per-move. But **Special Defence must enter the mon block**: `rl/envs/encoder_spec.py:224` drops `spd` for gen1's single Special stat. That is a MON_DIM change and therefore an OBS_DIM change. | `[tree]` |
| 2 | **17 types.** Dark and Steel are live; Fairy is `isNonstandard: 'Future'` at gen4 (`showdown/data/mods/gen5/typechart.ts:93-96`). Four cells among the 15 shared types differ from gen1 (§4). | A 17-entry `types` tuple listed explicitly (poke-env's `gen4typechart.json` carries an 18th `fairy` key that `GenData` does not filter — §4). Matchup scalars recomputed off the gen4 chart. | `[tree]` `[src]` |
| 3 | **Items and abilities exist.** The randbats pool reaches 101 abilities and exactly 40 items (§11). ~51 of the 101 abilities are never announced; type-immunity abilities sit on 69 of 464 sets. | Two new per-mon blocks, plus a hidden-information model for silent abilities and un-revealed items. | `[tree]` |
| 4 | **Global state exists.** Four weathers (indefinite when ability-set), entry hazards (only Spikes and Toxic Spikes actually occur; Stealth Rock is on no set — §8), Trick Room (1 set). Reflect/Light Screen are side conditions from gen2, not per-mon volatiles. | New global blocks: weather one-hot + turns (with an "indefinite" value), per-side hazard layers, field flags. Move `Effect.REFLECT` out of `volatiles`. | `[tree]` |
| 5 | **Status and volatile semantics change, and the turn cap is live.** Sleep 1–4 turns and the mon acts on the wake turn; freeze thaws 20 %/turn; Toxic resets on switch; Substitute is a resource; Protect floors at 1/8; Roost rewrites the type list for a turn; U-turn/Pursuit/Sucker Punch are pool staples. gen4 randbats has **no Endless Battle Clause**, so turn 1000 auto-ties (§12). | Counter slots (sleep turns, toxic stage, protect count, lock turns, sub HP); a live type list; an explicit tie/turn-budget policy for training and eval. | `[tree]` |

## 1. How to verify anything here: the inherit chain

`[tree]` `showdown/data/mods/gen4/scripts.ts:2` is `inherit: 'gen5'`; gen5 → gen6 →
gen7 → gen8 → base (`gen8/scripts.ts` has no `inherit`). So **a gen4 battle runs base
`data/*.ts` overridden by gen8, then gen7, gen6, gen5, gen4 — in that order.**
Consequences that a grep of `mods/gen4/` alone gets wrong:

- `gen5/moves.ts` and `gen5/conditions.ts` are live in gen4: partial-trap chip
  divisor 16 (base is 8), the `stall` doubling counter, Hidden Power's
  variable-BP callback, Skull Bash 100 BP, Mean Look/Block `reflectable`.
- `gen6/conditions.ts:4-6` is live: burn residual is `baseMaxhp/8`, not base's /16.
- `gen5/typechart.ts:68-96` and `gen6/typechart.ts` are live: Steel resists Ghost
  and Dark; Fairy is `'Future'`.
- The gen1 mod sits at the other end (`gen1/scripts.ts:16` `inherit: 'gen2'` → gen3
  → gen4 → …), i.e. gen1 inherits **through** gen4; anything gen4 overrides and
  gen1 does not re-override is shared.

## 2. Damage, critical hits, STAB, accuracy

**Damage.** `[tree]` Base damage is computed once
(`showdown/sim/battle-actions.ts:1715-1718`,
`tr(tr(tr(tr(2*level/5+2)*basePower*attack)/defense)/50)`), then **gen4 replaces
`modifyDamage` wholesale** (`showdown/data/mods/gen4/scripts.ts:57-137`). Order in
gen4: burn halving for physical moves (:65-67, Guts-exempt) → `ModifyDamagePhase1`
(where Reflect/Light Screen hook, :70) → spread → weather → `+2` (:82) → crit ×2
(:84-87) → `ModifyDamagePhase2`, floor → the 16-roll randomiser 85–100 %
(`showdown/sim/battle.ts:2388-2391`) → STAB ×1.5 (:100-107) → type effectiveness
(:109-125) → `ModifyDamage` (Life Orb, Expert Belt, Tinted Lens; :130) → min 1
(:132-134). gen1 computes everything in its own `getDamage`
(`showdown/data/mods/gen1/scripts.ts:748-970`): screens double the defence stat
inline (:869-873), a crit doubles *level* and ignores boosts and screens (:878-884),
stats ≥ 256 roll over (:897-910), damage clamps to [0, 997] before `+2` (:925),
effectiveness is applied per target type (:932-947), and the random factor is
217–255/255 (:965-969), i.e. 39 rolls not 16.

**Critical hits.** `[tree]`

| | gen1 | gen4 |
|---|---|---|
| basis | base Speed of the species (`mods/gen1/scripts.ts:816-843`): ≈ baseSpe/512 (Tauros ≈ 21.5 %) | stage table `critMult = [0,16,8,4,3,2]`, `critRatio` default 1 → **1/16** (`showdown/sim/battle-actions.ts:1622-1644`; `showdown/sim/dex-moves.ts:486`) |
| high-crit move | ×4 → ≈ 4× base rate | `critRatio: 2` → **1/8** |
| Focus Energy | **halves** the rate (`mods/gen1/scripts.ts:821-823`; the modern handler is nulled in `mods/gen1/moves.ts`) | +2 stages → 1/4; with a high-crit move → 1/3 |
| multiplier | level doubled inside the formula (≈ 1.95× at L100) | ×2 (`mods/gen4/scripts.ts:86`) |
| ignores | attacker's and defender's boosts and screens | attacker's negative offensive boosts and defender's positive defensive boosts (`battle-actions.ts:1682-1691`), plus Reflect/Light Screen (`mods/gen4/moves.ts:1108`, `:731-748`) |
| suppressed by | — | Lucky Chant, Battle Armor / Shell Armor |

High-crit moves in the gen4 randbats pool `[tree]`: aeroblast, crabhammer, crosschop,
leafblade, nightslash, psychocut, shadowclaw, spacialrend, stoneedge (the full
gen4-legal list also has aircutter, attackorder, blazekick, crosspoison, karatechop,
poisontail, razorleaf, razorwind, skyattack, slash). Encoder consequence: in gen1
"fast mons crit" is a species fact the encoder gets from base Speed; in gen4 it is
a **move** fact — a per-move crit-stage bit is new and cheap.

**STAB.** `[tree]` 1.5× in both gens; gen4 applies it via `battle.modify` after the
random roll (`mods/gen4/scripts.ts:100-107`), gen1 as `damage += floor(damage/2)`
before effectiveness (`mods/gen1/scripts.ts:928-930`). Adaptability (one pool set)
hooks `ModifySTAB` for 2×.

**Accuracy and evasion.** `[tree]` gen4 overrides `hitStepAccuracy`
(`mods/gen4/scripts.ts:148-204`): accuracy is out of 100 (:195), **the gen1 1/256
guaranteed miss is gone** (`mods/gen1/scripts.ts:456-462`), accuracy and evasion
boosts are applied as **separate** multiplications from the table
`[1, 4/3, 5/3, 2, 7/3, 8/3, 3]` (:164-187) rather than gen5+'s single net boost,
and `ModifyAccuracy` runs after the boost math (:188). OHKO accuracy is
`30 + user.level − target.level`, bypassing all modifiers (:154-162) — moot, no OHKO
move is in the pool. Evasion is nonetheless a live axis: Sand Veil (6 sets) and Snow
Cloak (4 sets) hook `ModifyAccuracy`; no evasion *move* is in the pool, so the
`evasion` and `accuracy` boost slots (already in `boost_keys`) are near-dead.

## 3. Move category

`[tree]` gen4: `category` is a per-move field on `showdown/data/moves.ts`, read by
`Battle#getCategory` (`showdown/sim/battle.ts:2384`) and by `getDamage`
(`battle-actions.ts:1673-1675`: `isPhysical ? 'atk' : 'spa'`, `isPhysical ? 'def' :
'spd'`). gen1–3: an `init()` on the **gen3** mod rewrites every move's category from
its type (`showdown/data/mods/gen3/scripts.ts:4-14`, `specialTypes = [Fire, Water,
Grass, Ice, Electric, Dark, Psychic, Dragon]`).

Over the merged gen4 table (`num ≤ 467`, standard), **97 moves cannot be categorised
from their type** `[tree]`:

- Physical in gen4 but Special-by-type (48): aquajet, aquatail, assurance,
  avalanche, beatup, bite, blazekick, bulletseed, clamp, crabhammer, crunch, dive,
  dragonclaw, dragonrush, feintattack, firefang, firepunch, flamewheel, flareblitz,
  fling, iceball, icefang, icepunch, iceshard, iciclespear, knockoff, leafblade,
  needlearm, nightslash, outrage, payback, powerwhip, psychocut, punishment,
  pursuit, razorleaf, sacredfire, seedbomb, spark, suckerpunch, thief, thunderfang,
  thunderpunch, vinewhip, volttackle, waterfall, woodhammer, zenheadbutt.
- Special in gen4 but Physical-by-type (49): acid, aeroblast, aircutter, airslash,
  ancientpower, aurasphere, bugbuzz, chatter, doomdesire, earthpower, flashcannon,
  focusblast, gust, hiddenpower (all variants), hyperbeam, hypervoice, judgment,
  mirrorshot, mudbomb, mudshot, mudslap, nightshade, ominouswind, powergem,
  razorwind, shadowball, signalbeam, silverwind, sludge, sludgebomb, smog, snore,
  sonicboom, spitup, swift, triattack, trumpcard, uproar, vacuumwave, weatherball,
  wringout.

In the pool this covers e.g. suckerpunch (31 sets), pursuit (16), waterfall (28),
crunch (20), icepunch (19), nightslash (18), shadowball (34), focusblast (24),
earthpower (23), sludgebomb (18), airslash (14). The encoder's `physical` slot
already reads `move.category` (`rl/envs/showdown.py:258-259` `[tree]`), so the
docstring claim in `rl/envs/encoder_spec.py:48-52` ("NO new table") is right for
the move block. What it does not say: **the mon block has no SpD**
(`encoder_spec.py:224`), and a gen4 policy cannot evaluate a special attack without
it.

## 4. The type chart

`[tree]` Computed from `showdown/data/typechart.ts` plus the gen8→gen4 mod
overrides; `[src]` cross-checked cell by cell against
`poke_env/data/static/typechart/gen4typechart.json`, which agrees. Encoding:
`damageTaken[Attacker] ∈ {0 neutral, 1 super-effective, 2 resist, 3 immune}`
(`showdown/sim/dex.ts:283-289`).

**17 live types** in gen4 (bug, dark, dragon, electric, fighting, fire, flying, ghost,
grass, ground, ice, normal, poison, psychic, rock, steel, water) vs 15 in gen1
(`mods/gen1/typechart.ts:129-136` marks Dark and Steel `'Future'`).

Cells that differ between gen1 and gen4 among the 15 shared types:

| attacker → defender | gen1 | gen4 | gen1 file:line | gen4 file:line |
|---|---|---|---|---|
| Ghost → Psychic | 0× | **2×** | `mods/gen1/typechart.ts:110-127` | `data/typechart.ts` psychic row |
| Bug → Poison | 2× | **0.5×** | `mods/gen1/typechart.ts:89-108` | `data/typechart.ts` poison row |
| Poison → Bug | 2× | **1×** | `mods/gen1/typechart.ts:10-27` | `data/typechart.ts` bug row |
| Ice → Fire | 1× | **0.5×** | `mods/gen1/typechart.ts:29-46` | `data/typechart.ts` fire row |

The two new types: **Dark** is weak to Bug and Fighting, resists Dark and Ghost,
**immune to Psychic**; attacking, 2× vs Ghost and Psychic, 0.5× vs Dark, Fighting,
Steel. **Steel** is weak to Fighting, Fire, Ground; resists Bug, Dark, Dragon, Flying,
Ghost, Grass, Ice, Normal, Psychic, Rock, Steel; **immune to Poison**; attacking, 2×
vs Ice and Rock, 0.5× vs Electric, Fire, Steel, Water. The Ghost/Dark resistances
are gen2–5 only (`mods/gen5/typechart.ts:68-91`).

Non-type keys on the chart (read by `Pokemon#runStatusImmunity`) `[tree]`: Fire
`brn: 3`, Ice `hail: 3` and `frz: 3`, Ground/Rock/Steel `sandstorm: 3`, Poison/Steel
`psn: 3` and `tox: 3`. gen1 Fire types can be burned and Ice types frozen (those
keys are absent from the gen1 chart). gen4 Ghosts **can** be trapped (no `trapped:
3`; `mods/gen5/typechart.ts:24-45`) and gen4 Grass types **are** hit by powder moves
(no `powder: 3`; `:46-67`).

**Three poke-env traps** `[src]`: (1) `GenData.load_type_chart` builds the chart from
every key in the JSON with no `isNonstandard` filter (`poke_env/data/gen_data.py:
73-109`), so `GenData.from_gen(4).type_chart` is 18×18 with a live `FAIRY` row whose
column is internally inconsistent — a gen4 spec must list its 17 types explicitly,
exactly as `GEN1` lists its 15. (2) `gen4typechart.json` drops the lowercase
status/weather keys, so poke-env's chart alone cannot answer "is this mon immune to
sand chip". (3) `Pokemon.damage_multiplier` knows nothing about Levitate, Flash
Fire, Wonder Guard, Thick Fat (`poke_env/battle/pokemon.py:842-858`); ability-based
immunities are the encoder's responsibility.

## 5. Stats, levels, EVs/IVs/natures, Hidden Power

- **Special is split.** `[tree]` gen2+ has real SpA and SpD; `mods/gen1/pokedex.ts`
  mirrors `spd` from `spa`, which is why `encoder_spec.py:224` drops it. A gen4 mon
  block needs six base stats.
- **EVs/IVs/nature in gen4 randbats** `[tree]` (`showdown/data/random-battles/gen4/
  teams.ts:646-736`): EVs 85 in every stat (510 = the gen4 cap), IVs 31, **no nature
  field is emitted** (every mon is nature-neutral; no nature vocab is needed).
  Adjustments: `evs.atk = 0` on sets with no physical move (:709-713), `evs.spe = 0`
  on gyroball/metalburst/trickroom sets (:715-718), HP-parity loops for
  Sitrus/Substitute/Belly Drum (:697-707), `ivs.atk -= 28` or `ivs.spe -= 28` on
  those sets when Hidden Power is present.
- **Happiness is unset → 255**, so Return is 102 BP on all 39 of its users and the
  request names it `"Return 102"` `[tree]` (`showdown/sim/pokemon.ts:342`).
- **Levels 67–100** `[tree]` (modes 69 and 83, 19 species each; gen1's spread is
  narrower). Level stays a live feature.
- **Hidden Power** `[tree]`: gen4 uses the IV formula with variable BP (`showdown/sim/
  dex.ts:380-383`; `mods/gen5/moves.ts:382-390`), but the generator writes the
  type's canonical `HPivs` spread (`gen4/teams.ts:679-695`) and every spread gives
  **exactly BP 70**. Only 8 types occur (electric, fighting, fire, flying, grass,
  ground, ice, rock), all Special. Protocol shape: the switch request sends
  `hiddenpowerfire` (no power suffix at gen4, `showdown/sim/pokemon.ts:1172-1175`);
  the active request sends `move: "Hidden Power Fire 70"` with `id: "hiddenpower"`
  (`:996-998`; the id collapses via `placeholderFor`, `showdown/sim/dex-moves.ts:
  479`). The encoder's move id must therefore come from the request's typed id, not
  from the collapsed `id`.

## 6. Major status conditions

| | gen1 | gen4 |
|---|---|---|
| **Sleep** | 1–7 turns (`random(1,8)`, `mods/gen1/conditions.ts:53-86`); **never acts on the wake turn** (:19-30) | 2–5 rolled = **1–4 turns lost** (`random(2,6)`, `mods/gen4/conditions.ts:32`); **acts on the wake turn** (:44-47); Early Bird decrements twice (:40-42, 4 sets); Rest sets `time = 3` (2 turns asleep); the counter does **not** reset on switch in gen4: gen5's `onSwitchIn` reset (`mods/gen5/conditions.ts:2-7`) is not inherited, because gen4's `slp` entry is a full replacement without `inherit: true` and Showdown merges a child entry over its parent only when that flag is set (`showdown/sim/dex.ts:676-695`); foul-play's gen4 table models it the same way (`fp/generations.py`, `rest_turns_reset_on_switch=False`) — a correction of the research note, found while checking the Foul-Play leg; Sleep Talk'd multi-hit moves hit once (`battle-actions.ts:892`); Sleep Clause Mod is on |
| **Freeze** | permanent (`mods/gen1/conditions.ts:87-107`); Ice types can be frozen | 20 %/turn thaw (`mods/gen4/conditions.ts:87-98`); `defrost` moves (Flame Wheel, Sacred Fire, Flare Blitz) act and thaw; Ice immune; **no Freeze Clause** in gen4 randbats |
| **Paralysis** | 63/256 full-para; Speed ×0.25 as a destructive stat write (`mods/gen1/scripts.ts:665`) | 25 % (`mods/gen4/conditions.ts:16-20`); Speed via `chainModify(0.25)` (:9-14); Quick Feet exempt (1 set) |
| **Burn** | maxhp/16 per own-move plus a tick on switch-in; Attack halved destructively (`mods/gen1/conditions.ts:12-29`; `scripts.ts:664`) | maxhp/8 residual (`mods/gen6/conditions.ts:4-6`); physical **damage** halved at the top of `modifyDamage` (`mods/gen4/scripts.ts:65-67`), Guts-exempt; Fire types immune |
| **Poison / Toxic** | one shared `residualdmg` counter for psn/brn/tox that also multiplies Leech Seed (`mods/gen1/conditions.ts:20-23, 116-119`; `mods/gen1/moves.ts:450-457`) | psn maxhp/8; tox `stage` 0→15, `max(maxhp/16,1)*stage`, **resets to 0 on switch** (`data/conditions.ts` tox); Leech Seed flat 1/8; Poison/Steel immune; Toxic is on **132 of 464 sets** — the most common move in the pool |
| **Confusion** | 2–5 rolled (1–4 acting), 50 % self-hit, hand-rolled damage (`mods/gen1/conditions.ts:139-158`) | same duration; 50 % self-hit (`mods/gen4/conditions.ts:74-76`, gen7+ is 33 %); the self-hit runs through the normal 40-BP physical pipeline so **it can crit and respects boosts** (:77-83). No confusion move is in the pool, but Dynamic Punch (100 % secondary) and Outrage fatigue are |
| **Attract** | — | gender-gated 50 % immobilise (`data/moves.ts` attract); the move is not in the pool but Cute Charm is (7 sets), so the volatile can appear on contact |

All `[tree]`. Policy consequence: gen1's sleep dominance (long removal, no wake-turn
move) is gone, but the pool has darkvoid, lovelykiss, spore, hypnosis, sleeppowder,
and Grass types are no longer powder-immune, so sleep remains a primary axis.

## 7. Volatiles and multi-turn state

All `[tree]`; "gen4 file" is where the value comes from after the inherit chain.
"Pool" is set count in `showdown/data/random-battles/gen4/sets.json` (464 sets).

| mechanic | gen1 | gen4 | encoder should carry | pool |
|---|---|---|---|---|
| **Substitute** | HP `floor(maxhp/4)+1`, blocks a hardcoded list (`mods/gen1/moves.ts` substitute) | HP `floor(maxhp/4)`, fails at `hp <= maxhp/4`, blocks by the `bypasssub` flag (`mods/gen4/moves.ts:1280-1316`); the `substitutebroken` volatile (`mods/gen4/conditions.ts:99`) is cleared from every foe when a mon switches in (`mods/gen4/scripts.ts:49-53`; critic_pass.md W4) | **sub HP as a scalar**, not only a flag | 44; generator pairs it with Leech Seed and Focus Punch (`gen4/teams.ts:30-36`) |
| **Protect / Detect** | absent | priority **+3** (gen5+ is +4; `mods/gen4/moves.ts:293-296, 1026-1044`); success counter doubles from 2 (`mods/gen5/conditions.ts:24-46`) with `counterMax: 8` (`mods/gen4/conditions.ts:134-139`) → 100 %, 50 %, 25 %, 12.5 %, then **12.5 % forever** | consecutive-protect counter | 45 |
| **Encore** | — | **4–8 turns** (`mods/gen4/moves.ts:401-404`; base 3) | remaining turns + the encored move | 24 |
| **Taunt** | — | **3–5 turns** (`:1381-1383`; base 3) | remaining turns | 13 |
| **Leech Seed** | scaled by the toxic counter | flat 1/8 (`:723-730`) | flag (exists) | 10 |
| **Curse** | — | Ghost branch decided in `onModifyMove` (`:268-287`), type `???` | ghost-curse residual distinct from the boost form | 11 |
| **Yawn** | — | duration 2, sleeps on end (`:1524-1531`) | "will sleep next turn" flag | 4 |
| **Partial trapping** | victim's move is **skipped entirely** (`mods/gen1/conditions.ts:192-220`) | victim acts; 1/16 chip for 3–6 turns (`mods/gen5/conditions.ts:8-23`, `mods/gen4/conditions.ts:110-118`); traps; BPs 15–35 at 70–85 acc | trapped flag + chip | trapping moves absent from the pool; the volatile can still arrive via nothing in-pool — near-dead |
| **Outrage** (lockedmove) | — | 2–3 turns then confusion (`data/conditions.ts` lockedmove); Protect does **not** reset the counter (`mods/gen4/moves.ts:1032-1038`); 120 BP / 15 PP | lock flag + remaining turns | 13 (thrash/petaldance absent) |
| **Two-turn moves** | Dig/Fly banned in gen1 randbats | `charge` flag + `twoturnmove` volatile; gen4 evaluates invulnerability in its own `hitStepInvulnerabilityEvent` (`mods/gen4/scripts.ts:138-147`) | `preparing` slot exists | only Solar Beam (3); no Fly/Dig/Dive/Bounce/Shadow Force |
| **Recharge** | cancelled by a trap or sleep move (`mods/gen1/moves.ts:75-80, 937-941`) | plain `mustrecharge`, duration 2 (`data/conditions.ts:364-378`) | `mon.must_recharge` (exists) | Giga Impact 1; Hyper Beam 0 |
| **Destiny Bond** | — | `bypasssub` volatile | flag | 4 |
| **Roost** | — | one-turn volatile removing Flying from the type list (`data/moves.ts` roost, `onTypePriority: -1`); heals 1/2 | **read the live type list** — a species-derived one-hot desyncs for a turn | **45** (the most common non-attacking move) |
| **Wish** | — | slot condition, duration 2, heals **half the recipient's** max HP (`mods/gen4/moves.ts:1492-1507`) | pending-wish flag per slot | 19, paired with Protect |
| **U-turn** | — | `selfSwitch: true`, 70 BP; the switch resolves after the hit | the forced switch shows up as a request; not a state | **54** (6th most common move) |
| **Pursuit** | — | fires at a switching foe at 2× BP, cancelling the user's queued action (`mods/gen4/moves.ts:1049-1078`) | not observable; a policy fact | 16 |
| **Fake Out** | — | priority **+1** (gen5+ is +3; `:434-437`), first turn only | "just switched in" (activeTurns == 0) | 8 |
| **Sucker Punch** | — | +1, 80 BP; fails if the target is not queued to use a damaging move (`:1318-1326`) | — | **31** — a mind-game axis with no gen1 analogue |
| **Counter / Mirror Coat / Metal Burst** | gen1 Counter is desync-prone POV bookkeeping | −5 / −5 / 0; scripted targets (`data/moves.ts`) | — | 2 / 1 / 1 |
| **Trick / Switcheroo** | — | swap items; the generator gives Poison types Black Sludge instead of Leftovers for this reason (`gen4/teams.ts:669-673`) | **item identity per mon** | 21 / 4 |
| **Knock Off** | — | 20 BP, no boost (`mods/gen5/moves.ts:485-489`); makes the item unusable, gains nothing (`mods/gen4/moves.ts:706-718`) | item-knocked-off flag | 3 |
| **Rapid Spin** | — | 20 BP; clears hazards, Leech Seed, trapping **only if it connects** (`:1080-1098`) | — | 13 (vs 14 Spikes + 14 Toxic Spikes sets) |
| **Roar / Whirlwind** | priority 0, no `forceSwitch` | −6, `forceSwitch`; Roar is `sound` + `bypasssub` in gen4 (`:1143-1146`) | — | 7 / 6 |
| **Haze** | `target: 'self'` with gen1 quirks | `target: 'all'`, clears boosts and Focus Energy (`:600-609`) | — | 5 |
| **Explosion / Selfdestruct** | halves defence inside gen1's formula (`mods/gen1/scripts.ts:912-915`) | `battle-actions.ts:1711-1713`: defence halved for gen ≤ 4 → effectively double gen5+'s damage | — | **37** / 3 — a first-order threat |
| **Struggle** | recoil = half the damage dealt, Normal-typed (`mods/gen1/moves.ts` struggle) | **1/4 max HP** recoil (`mods/gen4/scripts.ts:205-220`); typeless (`mods/gen4/moves.ts:1270-1279`): no STAB, no effectiveness, hits Ghosts | — | always available |
| Encore-class extras absent from the pool | — | Disable (80 acc, 4–7 turns), Torment, Perish Song, Ingrain, Aqua Ring, Magnet Rise, Bide, Uproar (3–6 turns, 50 BP), Rollout/Ice Ball, Charge, Stockpile, Grudge, Embargo, Heal Block, Gastro Acid, Power Trick, Lock-On (Baton-Passable in gen4), Foresight/Odor Sleuth/Miracle Eye, Nightmare, Minimize (+1 evasion in gen4), Future Sight/Doom Desire, Baton Pass, Mean Look/Block/Spider Web (Ghosts not immune) | implemented, unreachable in this pool | 0 |

## 8. Entry hazards and side conditions

`[tree]` In gen1 Reflect/Light Screen/Mist are per-mon volatiles that die on switch
(`mods/gen1/scripts.ts:869-873` applies screens by doubling the defence stat). From
gen2 they are 5-turn **side conditions** — which is why a gen2+ spec must move
`Effect.REFLECT` out of `volatiles` into a side block (the landed seam's docstring
says exactly this, `rl/envs/encoder_spec.py:56-61`).

| side condition | gen4 semantics | file:line | in pool |
|---|---|---|---|
| Stealth Rock | on entry, `maxhp * 2^typeMod / 8` by Rock effectiveness → 1/32 … 1/2 | `mods/gen4/moves.ts:1257-1268` | **no set** (zero occurrences of `stealthrock` in `sets.json`; `HAZARDS` at `gen4/teams.ts:24-27` lists it but no movepool has it) |
| Spikes | 3 layers; 1/8, 1/6, 1/4; grounded only | `:1240-1252`, `data/moves.ts` spikes | 14 sets |
| Toxic Spikes | 2 layers; grounded only; psn / tox; grounded Poison types absorb it; Steel and Substitute-protected mons unaffected (the Substitute clause is gen4-specific) | `:1419-1439` | 14 sets |
| Reflect / Light Screen | 5 turns, 8 with Light Clay; halve physical / special damage unless crit or `infiltrates`; hook `ModifyDamagePhase1` | `:1103-1119`, `:731-748`; `data/items.ts:3440` | 0 |
| Safeguard / Mist / Tailwind (3 turns in gen4) / Lucky Chant | 5 / 5 / 3 / 5 turns | `:1151-1158`, `:920-927`, `:1357-1375`, `:756-765` | 0 |

Hazards fire on the `EntryHazard` event, which gen4's `runSwitch` raises before
`SwitchIn` (`mods/gen4/scripts.ts:18-21`).

## 9. Weather and fields

`[tree]` All four weathers are base conditions (`showdown/data/conditions.ts`
raindance / sunnyday / sandstorm / hail); gen4 only re-orders residuals
(`mods/gen4/conditions.ts:140-155`). Duration 5, 8 with the matching rock.
**Ability-set weather is indefinite in gen4**: each `onFieldStart` has `if
(effect?.effectType === 'Ability') { if (this.gen <= 5) this.effectState.duration =
0; }`. Drizzle (2 sets), Drought (2), Sand Stream (3), Snow Warning (1) are in the
pool; the only weather *moves* in the pool are Rain Dance (10) and Sunny Day (3), so
**sand and hail are always permanent when they occur**. Effects: rain ×1.5 Water /
×0.5 Fire, sun the mirror, sandstorm gives Rock types ×1.5 SpD, sand/hail chip
`baseMaxhp/16` with immunity read off the chart's lowercase keys
(`showdown/sim/battle.ts:2113`) — sand: Ground/Rock/Steel; hail: Ice; Magic Guard
exempt. Sand Veil (6) / Snow Cloak (4) are evasion in weather; Air Lock (3) / Cloud
Nine (1) suppress weather; Forecast (1) / Flower Gift (2) change form or stats.

**Trick Room** `[tree]`: priority −7, pseudo-weather, duration 5; gen4's
`getActionSpeed` override negates speed (`mods/gen4/scripts.ts:6-14`). One pool set,
but it inverts every speed comparison. **Gravity** exists (`data/moves.ts` gravity)
but is not in the pool.

Encoder consequence: a global weather block (5-way one-hot + turns remaining with a
distinguished "indefinite" value — 0 would collide with "just expired") and a
Trick Room flag + turns.

## 10. Turn order, priority, PP

`[tree]` Action order (`showdown/sim/battle-queue.ts:173-199`): `beforeTurnMove`
(Counter/Mirror Coat/Focus Punch/Pursuit register here) → `runSwitch` → **switch
103** → moves 200 → residual 300. **All switches resolve before all moves.** Within
a bracket, `comparePriority` sorts by order, priority, speed, subOrder
(`showdown/sim/battle.ts:404-411`); **speed ties are shuffled randomly**
(:437-458).

Every non-zero-priority gen4-legal move: +5 helpinghand; +4 endure, magiccoat,
snatch; **+3 detect, protect** (gen5+ is +4), followme; +2 feint; **+1 aquajet, bide,
bulletpunch, extremespeed (gen5+ is +2), fakeout (gen5+ is +3), iceshard,
machpunch, quickattack, shadowsneak, suckerpunch, vacuumwave**; −1 vitalthrow; −3
focuspunch; −4 avalanche, revenge; −5 counter, mirrorcoat; −6 roar, whirlwind; −7
trickroom. +1 moves sit on **95 of 464** pool sets (ten distinct: suckerpunch 31, extremespeed 16, quickattack 9, shadowsneak 9, aquajet 8, fakeout 8, bulletpunch 7, iceshard 7, machpunch 5, vacuumwave 1; critic_pass.md W5) against essentially one in gen1. **Note for the encoder:** `move.priority / 5.0` in the gen1
move block leaves the declared `Box(low=-1)` at gen4 (trickroom −1.4, roar −1.2) —
see `encoder_requirements.md`.

**PP and Pressure** `[tree]`: `Pokemon#deductPP` (`showdown/sim/pokemon.ts:894-906`)
deducts 1; Pressure makes it 2 and is on **32 sets** (second most common ability).
`mustpressure` moves (spikes, toxicspikes, stealthrock) charge Pressure even
untargeted. PP is a live resource in gen4 in a way it is not in gen1.

## 11. Abilities and items — the hooks, and what is observable

From `showdown_gen4_abilities_items.md` (all `[tree]` unless marked):

- **Universe.** 101 distinct abilities across 464 sets (`gen4/sets.json` `abilities`
  entries; every listed ability is reachable — `getAbility` only culls
  Chlorophyll/Leaf Guard without sun, Swift Swim without rain, Rock Head without
  recoil, Skill Link without a multi-hit, `gen4/teams.ts:452-509`). **Exactly 40
  items**: 17 species-forced (16 Arceus plates, Griseous Orb) and 23 by rule
  (`gen4/teams.ts:510-626`; gen4 overrides both `getItem` and `getPriorityItem`
  with no `super`, and gen5's `randomTeam` contains no item literal, so nothing
  leaks in). Notable absences: Flame Orb, Heat/Smooth/Icy Rock, Iron Ball, Macho
  Brace, Shed Shell, Quick Claw, King's Rock, Scope Lens, Shell Bell, Wise
  Glasses, Muscle Band, every pinch berry except Sitrus and Custap, every
  type-boost item except Black Glasses and Silk Scarf; gen5 items (Eviolite, Air
  Balloon, gems) by construction. Dialga has no Adamant Orb branch (Palkia has
  Lustrous Orb, `:596`).
- **Top abilities:** Levitate 40, Pressure 32, Multitype 23 (Arceus), Intimidate 20,
  Chlorophyll 16, Swift Swim 16, Water Absorb 13, Thick Fat 12, Torrent 12, Clear
  Body 11, Natural Cure 10, Own Tempo 10, Synchronize 9, Rock Head 9. Type-immunity
  abilities (Levitate, Water/Volt Absorb, Flash Fire, Dry Skin, Motor Drive, Wonder
  Guard) total 69 sets — a policy blind to abilities is systematically wrong
  about effectiveness.
- **gen4-specific ability semantics** worth carrying: Sturdy is OHKO-immunity only;
  Lightning Rod / Storm Drain are redirect-only, no immunity (`mods/gen4/
  abilities.ts:245-249, 447-451`; neither is in the pool); Knock Off cannot take an
  item; Intimidate whiffs through a Substitute; Life Orb takes no recoil into a
  Substitute; Simple reads stages doubled; Inner Focus / Own Tempo / Scrappy do
  not block Intimidate; Keen Eye does not ignore evasion; Custap Berry is a queue
  insert; Protect's floor is 1/8 (`mods/gen4/conditions.ts:135-141`).
- **Reveal model** (what the opponent can know):
  - announce via `-ability`: **only** Anticipation, Intimidate, Mold Breaker,
    Pressure (gen4 removes base's Air Lock / Cloud Nine / Sturdy announcements,
    `mods/gen4/abilities.ts:2-8, 37-43, 452-456`);
  - announce via `-immune … [from] ability:` when hit: Levitate, Flash Fire, Volt /
    Water Absorb, Motor Drive, Dry Skin, Wonder Guard, Soundproof, Insomnia, Vital
    Spirit, Immunity, Limber, Water Veil, Own Tempo, Sturdy (OHKO only), Leaf Guard
    (Yawn only);
  - announce via `-activate` (poke-env records an `Effect` but does **not** set
    `mon.ability`, `[src]` `poke_env/battle/abstract_battle.py:827-893`): Forewarn,
    Hydration, Shed Skin, Sticky Hold, Suction Cups, Synchronize;
  - announce indirectly (`-status`, `-damage [from] ability`, `-boost`, `-weather
    [from] ability`, `-curestatus`, `cant`): Static, Flame Body, Poison Point, Rough
    Skin, Aftermath, Trace, Download, Speed Boost, Truant, Slow Start, Natural
    Cure, Cute Charm, Clear Body-class, the weather setters — several with the
    cause dropped by poke-env (`cant` reason, `-curestatus` cause);
  - **never announced (~51 of 101):** Air Lock, Cloud Nine, Magic Guard, Chlorophyll,
    Swift Swim, Sand Veil, Snow Cloak, Thick Fat, Filter, Solid Rock, Technician,
    Tinted Lens, Iron Fist, Adaptability, Sniper, Super Luck, the pinch boosts,
    Guts, Quick Feet, Marvel Scale, Simple, Skill Link, Serene Grace, Shield Dust,
    Rock Head, Battle/Shell Armor, Huge/Pure Power, Poison Heal, Scrappy, Early
    Bird, Inner Focus, **Arena Trap, Shadow Tag, Magnet Pull**, Flower Gift,
    Multitype, Unburden, Liquid Ooze, and more. This is the largest new
    hidden-information surface gen4 adds; 278 of 295 pool species have a unique
    ability, so a species→ability prior collapses most of it.
  - items: Life Orb, Leftovers/Black Sludge, Toxic Orb, berries, Focus Sash, Custap
    self-reveal within a turn or two of relevance; the three Choice items, Expert
    Belt, Black Glasses, Silk Scarf, Light Clay, Damp Rock, Quick Powder and every
    species-locked item **never self-reveal**; 8 of the 40 are deducible from the
    species line alone. The live inference is "Choice / Life Orb / Leftovers /
    Expert Belt / Focus Sash?", and Choice is invisible until a move repeats or a
    Trick lands.
- Inert in singles: Plus, Minus (`mods/gen4/abilities.ts:270-280, 325-335`), Pickup,
  Run Away, and Gluttony given this pool's items. Flower Gift is **not** inert
  (`showdown/sim/battle.ts:1056` runs `onAlly*` for self).

## 12. Format rules: clauses, the turn cap, no team preview

`[tree]` `showdown/config/formats.ts:4238-4244`:

```
name: "[Gen 4] Random Battle", mod: 'gen4', team: 'random', bestOfDefault: true,
ruleset: ['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod'],
```

versus gen1's `ruleset: ['Standard']` (`:4260-4265`), which expands through
`mods/gen1/rulesets.ts:8-16` to Standard AG (Obtainable, Desync Clause Mod, HP
Percentage Mod, Cancel Mod, **Endless Battle Clause**) plus Sleep Clause Mod, Freeze
Clause Mod, Species Clause, Nickname Clause, OHKO Clause, Evasion Moves Clause, and
`banlist: ['Dig','Fly']`.

| clause | gen1 randbats | gen4 randbats |
|---|---|---|
| Sleep Clause Mod (`data/rulesets.ts:1378-1400`) | yes | yes |
| Freeze Clause Mod | yes | **no** |
| Species Clause | yes | no (uniqueness enforced inside the generator) |
| OHKO / Evasion clauses | yes | no (moot: no such move in the pool) |
| **Endless Battle Clause** | yes | **no** |
| HP Percentage Mod / Cancel Mod | yes | yes |
| **Team Preview** | no | **no** — the format does not use `Standard`, and `mods/gen4/rulesets.ts:2-7` strips Team Preview from gen4's `standardag` anyway |

**Turn cap** `[tree]` `showdown/sim/battle.ts:1833-1849`, independent of Endless
Battle Clause: warnings from turn 500, **auto-tie at turn > 1000**. With Protect's
1/8 floor, Toxic on 132 sets, Levitate on 40, Wish on 19, Leftovers, and no clause
to adjudicate stalling, gen4 randbats can genuinely reach the cap. Our gen1 episode
length priors (~26–32 decisions) and the tie handling in reward and eval must be
re-checked before any gen4 run (→ `anchors_and_eval.md`, `open_questions.md`).

`maxTeamSize = 6`, `maxMoveCount = 4`, singles, HP reported as percentages for the
opponent (same as gen1).

## 13. gen1 quirks that disappear in gen4

All `[tree]` unless marked.

| gen1 quirk | gen1 file | gen4 |
|---|---|---|
| 1/256 miss on every non-self move | `mods/gen1/scripts.ts:456-462` | gone |
| partial trapping skips the victim's turn | `mods/gen1/conditions.ts:198-202` | victim acts; 1/16 chip |
| Hyper Beam recharge cancelled by a trap/sleep move | `mods/gen1/moves.ts:75-80, 937-941`; `scripts.ts:648-658` | plain 2-turn recharge |
| Hyper Beam needs no recharge if the target faints | **not located in the vendored gen1 mod** — `[lit]`; check: a gen1 battle where Hyper Beam KOs and no `-mustrecharge` line follows `[live]` | n/a |
| Counter's cross-POV desync | `mods/gen1/moves.ts` counter | plain −5 |
| Substitute `floor(maxhp/4)+1` and a hardcoded block list | `mods/gen1/moves.ts` substitute | `floor(maxhp/4)`, `bypasssub` |
| burn/para stat-drop reset bug | `mods/gen1/scripts.ts:626-634, 649` | chain modifiers |
| stat rollover at 256 | `mods/gen1/scripts.ts:897-910` | gone |
| Wrap as a lock-out tool at 85 acc | `mods/gen1/moves.ts:930-943` | 15–35 BP chip |
| shared toxic counter multiplying Leech Seed | `mods/gen1/conditions.ts:20-23, 116-119`; `moves.ts:450-457` | separate `stage`, resets on switch |
| sleep 1–7, no wake-turn move | `mods/gen1/conditions.ts:53-86` | 1–4, acts on wake |
| permanent freeze | `mods/gen1/conditions.ts:87-107` | 20 % thaw |
| speed-based crits | `mods/gen1/scripts.ts:816-843` | 1/16 stage table |
| single Special stat | `mods/gen1/pokedex.ts` | SpA/SpD |
| Focus Energy halves crits | `mods/gen1/scripts.ts:821-823` | +2 stages |
| Fire can be burned, Ice frozen | absent `brn:3`/`frz:3` | both immune |
| Dig/Fly banned | `mods/gen1/rulesets.ts:15` | legal (and absent from the pool) |

## 14. What can actually occur — the pool bounds the mechanics

`[tree]` gen4's `randomSet` draws moves only from `set.movepool` in `sets.json`
(`gen4/teams.ts:636-641`), so the union of movepools plus Struggle is the complete
move universe: **295 species, 464 sets, 181 distinct moves, 101 abilities, 40
items, levels 67–100.** Top moves: toxic 132, earthquake 127, icebeam 81,
thunderbolt 57, stoneedge 57, uturn 54, surf 48, swordsdance 48, roost 45, protect
45, substitute 44, calmmind 44, psychic 44, fireblast 43, return 39, thunderwave 39,
explosion 37, recover 37, rest 35, shadowball 34, suckerpunch 31.

**Implemented but unreachable in this pool** (no move, and no ability path):
Stealth Rock, Baton Pass, Reflect, Light Screen, Safeguard, Mist, Tailwind, Lucky
Chant, Gravity, Perish Song, Disable, Torment, Embargo, Heal Block, Power Trick,
Gastro Acid, Lock-On, Foresight, Odor Sleuth, Miracle Eye, Nightmare, Ingrain, Aqua
Ring, Magnet Rise, Future Sight, Doom Desire, Endeavor, Flail, Reversal, Rollout,
Ice Ball, Thrash, Petal Dance, Uproar, Hyper Beam, Fly, Dig, Dive, Bounce, Shadow
Force, Feint, Avalanche, Revenge, Vital Throw, Icy Wind, Memento, all OHKO moves,
all evasion moves, Confuse Ray, Swagger, Attract, the Sandstorm and Hail moves.

Two cautions for the encoder: (a) this is the pool **as vendored at 59da482** — a
Showdown bump can add Stealth Rock to a set silently, so the pre-reg must pin the
commit and the encoder should keep the slot (→ §16 Q1); (b) an embedding table
sized to the 1..467 move `num` range is safe but ~62 % of its rows will never be
seen in randbats.

## 15. Consolidated delta table (for `encoder_requirements.md`)

| mechanic | gen1 (file:line) | gen4 (file:line) | encoder must carry | policy must reason about |
|---|---|---|---|---|
| move category | by type, `mods/gen3/scripts.ts:4-14` | per move, `sim/battle.ts:2384` | nothing new in the move block; **`spd` in the mon block** | 97 moves break the type heuristic |
| type chart | 15 types, `mods/gen1/typechart.ts` | 17, `data/typechart.ts` + `mods/gen5/typechart.ts:68-96` | 17-entry `types` tuple; recomputed matchup scalars; ability-aware immunity | Steel/Dark; Ghost→Psychic 2× |
| crit | speed-based, `mods/gen1/scripts.ts:816-843` | 1/16 table, `sim/battle-actions.ts:1622-1644` | per-move crit-stage bit; Focus Energy flag | high-crit moves as a threat class |
| damage order | `mods/gen1/scripts.ts:920-969` | `mods/gen4/scripts.ts:57-137` | — | burn halves before `+2`; crits bypass screens |
| accuracy | /256 + 1/256 miss | /100, separate acc/eva tables, `mods/gen4/scripts.ts:148-204` | acc/eva boost slots (present) | Sand Veil / Snow Cloak |
| sleep | 1–7, no wake move, `mods/gen1/conditions.ts:53-86` | 1–4, acts on wake, `mods/gen4/conditions.ts:22-53` | sleep-turn counter (the `status_counter` slot exists) | weaker sleep; Sleep Clause on |
| freeze | permanent | 20 %/turn, `mods/gen4/conditions.ts:87-98` | — | no Freeze Clause |
| paralysis | 63/256, destructive write | 25 %, `chainModify(0.25)` | — | Quick Feet |
| burn | maxhp/16, Atk halved destructively | maxhp/8; physical damage halved | — | Guts; Will-O-Wisp (21 sets) |
| toxic | shared counter | own `stage`, resets on switch | toxic stage counter | Toxic on 132 sets |
| Substitute | `floor(maxhp/4)+1` | `floor(maxhp/4)`, `bypasssub`, `mods/gen4/moves.ts:1280-1316` | **sub HP** | Sub+Protect, Sub+Leech Seed, Sub+Focus Punch |
| Protect | absent | +3, 1/8 floor | consecutive-protect counter | stall loops |
| hazards | absent | Spikes / Toxic Spikes, `mods/gen4/moves.ts:1240-1252, 1419-1439` | per-side layer counts (keep a Stealth Rock slot) | 28 hazard sets vs 13 Rapid Spin |
| screens | per-mon volatiles | side conditions, `mods/gen4/moves.ts:1103-1119` | move REFLECT to a side block | moot in this pool |
| weather | absent | 4 weathers, indefinite from abilities | one-hot + turns with "indefinite" | 8 weather-setter sets |
| Trick Room | absent | −7, `mods/gen4/scripts.ts:6-14` | field flag + turns | inverts speed |
| priority | Quick Attack | brackets −7..+5 | per-move priority (present; **Box range breaks**) | Sucker Punch 31, Extreme Speed 16, U-turn 54, Pursuit 16 |
| PP / Pressure | no abilities | Pressure = 2 PP | pp scalar (present) | 32 Pressure sets |
| Roost | absent | live type override, `data/moves.ts` roost | **read `mon.types`, not the species** | 45 sets |
| items / abilities | none | 40 / 101 | two new per-mon blocks + reveal state | Levitate 40, Trick 21, Choice lock |
| clauses | Standard incl. EBC | Sleep Clause only, `config/formats.ts:4243` | — | **turn-1000 auto-tie**, `sim/battle.ts:1836-1839` |

## 16. Maintainer rulings wanted (collected verbatim in `open_questions.md`)

1. **Stealth Rock is absent from every gen4 randbats set in the vendored build.**
   Recommendation: keep the side-block slot AND pin the Showdown commit in the gen4
   pre-reg. Losing argument: a slot that is always zero is dead weight and the pool
   should be taken as the spec.
2. **No Endless Battle Clause; turn-1000 auto-tie.** Ties are non-wins under the
   locked protocol. Recommendation: an explicit per-battle turn budget and tie
   rule in the gen4 pre-reg, and a check of the env's own turn cap. Losing
   argument: the cap is rare enough to disclose rather than design around.
3. **`spd` in `base_stat_keys` invalidates every checkpoint** (unavoidable). Clean
   break (new OBS_DIM, no gen1 loading) vs a padded layout that keeps gen1
   checkpoints loadable. Recommendation: clean break; JOURNEY's standing note says
   weights never transfer across generations.
4. **Roost's one-turn type override**: read the type one-hot from the live
   `mon.types` rather than the species (harmless in gen1 — nothing in the gen1 pool
   changes type — but it perturbs the tape-hash gate if applied to GEN1).
   Recommendation: gen4 spec only; leave GEN1's fill path untouched.
5. **Substitute HP as a scalar** (+1 float in the active block). Recommendation: yes.
   Losing argument: recoverable from message history the encoder does not carry.
6. **An "indefinite weather" sentinel** distinct from 0 turns. Recommendation: a
   separate flag.

## 17. Sources, verification, and what was not checked

- Every `showdown/` citation is `[tree]` from the research note's read of the `.ts`
  sources; the merged move table (categories, priorities, crit lists) came from the
  compiled `showdown/dist/data/**/moves.js` (mtime matches `data/`, spot-checked:
  gen4 thrash 90 BP / 20 PP, disable acc 80) — a number quoted only from that table
  should be re-grepped in the `.ts` before it enters a pre-reg.
- Not read: `mods/gen2/*`, `gen3/moves.ts`, gen4 `formats-data.ts` and learnsets,
  the gen4/base `rage` implementation, `SD/data/abilities.ts` beyond `pressure` and
  the ability/item bodies covered by the abilities note.
- `[live]` items in this doc: the gen1 Hyper-Beam-on-KO recharge rule (§13); the
  empirical (ability, item) frequency distribution of the generator (the item
  universe is a static reachability read of `getItem`/`getPriorityItem`, not a
  sampled one — check: run `RandomGen4Teams.randomTeam()` ~10⁵ times offline once
  the box is free); and every protocol-message claim in §11, which is read off the
  sim source, not a wire capture — check: one local gen4randombattle with
  `--no-security`, diffing `-ability` / `-activate` / `-enditem` / `-status` /
  `-weather` / `-sidestart` / `-singleturn` lines against §11.
- Literature cross-check (Bulbapedia / Smogon) was **not run** in this cycle (its
  agent was lost to the usage limit — `open_questions.md` deferral D4). Where the
  vendored sim is the authority this costs nothing; it would have caught
  sim-vs-cartridge divergences, which this doc does not claim to cover.

## 18. Live verification (2026-09-04/05, branch `gen4-build`)

Every claim below is `[tree]` against the tape summaries under
`docs/design_gen4/research/live/` (recorded by `scripts/gen4_smoke.py` on a
fresh local clone of the vendored server at 59da482e; 1,530 recorded
seat-battles over eight runs, both seats' views; the tapes themselves are
gitignored under `data/gen4_tapes/`) and against
`research/live/generator_sample_100k.json` (`scripts/gen4_sample_generator.js`,
100,000 generated teams, fixed seed). Counts are one seat's view per room.

- **§11 reveal model, corrected.** `-ability` announcements observed (300 + 200
  + 200 + 60 + 30 + 30 battles): Pressure 825, Intimidate 548, Mold Breaker 80,
  **Speed Boost 73, Download 49**, Anticipation 16 — six announcers, not four;
  the long tail (Levitate 8, Own Tempo 4, Swarm 3, ...) is Trace's copy line
  `-ability|X|<copied>|[from] ability: Trace|[of] Y` (7 fields). `-immune ...
  [from] ability:` Levitate / Water Absorb / Wonder Guard / Immunity / Dry Skin /
  Volt Absorb; `-activate ... ability:` Sticky Hold 14, Forewarn 8, Hydration 1;
  `-weather ... [from] ability:` all four setters with `[of]`; `-curestatus ...
  [from] ability: Natural Cure` 7 (the cause IS on the wire; poke-env drops it);
  `-status ... [from] ability:` Static / Flame Body / Poison Point / Synchronize;
  `-start|X|ability: Flash Fire` paired with `-end` on switch-out; `-start ...
  typechange ... [from] ability: Color Change` 17; `-start|ability: Slow Start` 29.
  (`t1_rnd_sh_300.summary.json` `from_causes`, `effects`; the `-ability` name
  histogram is in SESSION_LOGS 2026-09-05.)
- **§6 sleep.** Attempts lost before waking, from `cant|slp` counts between
  `-status|slp` and `-curestatus|slp` (111 wakes): {0: 8, 1: 4, 2: 90, 3: 2, 4: 7}.
  Rest (`time = 3`, two attempts) dominates; the eight zeros are Heal Bell /
  Natural Cure cures; the maximum is 4 — `random(2, 6)` as read from
  `mods/gen4/conditions.ts:32`. Sleep Clause never fired in 760 battles; three
  requests showed two own mons asleep (Rest + an inflicted sleep — §17 of
  `pokeenv_gen4_survey.md`).
- **§12 ties and the turn cap.** Ties 10 of 760 bot battles (SH-vs-SH 7/200,
  max-power-vs-SH 2/200, random-vs-SH 0/300) plus 1/30 in each most-damage-typed
  run — simultaneous KOs, never the turn-1000 cap: longest game 147 turns, per-
  matchup means 17.6–25.8, medians 16–23. The tie rule (Q33) is live at ~1–3 %.
- **§9 weather.** 4,195 of 4,350 weather-present decisions were under ability-set
  (indefinite) weather; a move weather ends with `-weather|none` (10 lines).
  Upkeep restamps every turn (`Sandstorm|upkeep` 431 vs 35 `[from] ability`
  set lines in 300 battles).
- **§8 hazards.** `-sidestart` Spikes 51 / Toxic Spikes 62 per 300 random-vs-SH
  battles; Toxic Spikes absorbed by a grounded Poison type (`-sideend|move: Toxic
  Spikes` 10); Rapid Spin `-sideend` 4; **Stealth Rock 0**, as the pool read says.
- **§7 volatiles.** Roost arrives as `-singleturn|move: Roost` (92): its type
  change lives inside the turn and is never visible at a decision point, so the
  live-type read matters for Color Change, not Roost (17 `-start|typechange`).
  Encore's `-start` names no move (42 lines, all 4 fields). Substitute's
  `-activate|Substitute|[damage]` carries no amount (12 lines) — sub HP is
  unobservable; hits are countable. `-fieldstart|move: Trick Room|[of]` 1.
- **§5 request shape.** The active list names `Return 102` and `Hidden Power
  <Type> 70` (`request_move_names_nonplain`: 916 / 2,122 in 300 battles);
  `side.pokemon[].moves` carries `return102` and `hiddenpowerfire`; poke-env's
  `Move.retrieve_id` collapses both to `return` / `hiddenpower` for the active
  list and keeps the typed Hidden Power id in `mon.moves`. Own `baseAbility` and
  `item` keys on every request (1,872/1,872); no gen-7 `ability` key.
- **§14 pool closure.** All 295 pool species appeared in requests, none outside
  the vocab; every request move id is a vocab row except the placeholder
  `recharge` (25) and `return102` (normalised). The generator's 600,000 sets:
  296 species ids (295 + `gastrodoneast`), 101 abilities, **39 of the 40 items**
  (Light Clay never — its rule needs Reflect and Light Screen, both absent from
  the pool), 181 moves, Stealth Rock 0, no nature field, every team 6 mons, one
  level per species, 17 species with more than one sampled ability, 145 with
  more than one sampled item; **1,743 distinct realised (moves, ability, item)
  triples** (median 4 per species, max 41 — Qwilfish), 13 singletons in 600,000
  draws.
- **Not checked live:** the gen-1 Hyper-Beam-on-KO rule (§13); the foul-play
  gen-4 engine build (needs authorisation, Q37).

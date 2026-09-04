# showdown_gen4_pool.md — the gen4 random-battle team pool, as vendored

**Agent:** gen4 pool characterization (staged docs-only design sweep for the GEN 4 chapter)
**Date:** 2026-09-04
**Scope:** what `gen4randombattle` actually generates on THIS machine's vendored
server, exact counts, and the encoder vocabulary that follows.

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP: `rl/`, `scripts/`,
  `configs/`, `tests/`, `docs/`) or the vendored `showdown/data`+`sim`, i.e. the game as we run it.
- **source-verified** — checked against an external primary source on disk (poke-env source,
  Wang, H&L/metagrok, ps-ppo, foul-play, Metamon text).
- **literature-only** — from a secondary write-up / web page / memory, primary not re-checked.
- **needs-live-verification** — only a running server or battle can confirm. BARRED until the
  live ladder run and any later fleet complete.

## Sources read (path — lines/pages)

Vendored Showdown (`SD = /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown`,
pokemon-showdown @ `59da482`, `git log --oneline -1` in SD):

| file | what I read |
|---|---|
| `SD/data/random-battles/gen4/sets.json` | whole file via `jq` (295 keys, 464 sets) |
| `SD/data/random-battles/gen4/teams.ts` | 1–771 (whole file, in four `sed` windows) |
| `SD/data/random-battles/gen5/teams.ts` | 1–54 (imports/consts/class), 845–987 (`randomTeam`) |
| `SD/data/random-battles/gen6/teams.ts`, `gen7/teams.ts`, `gen8/teams.ts` | lines 1–8 + class decl only (inheritance chain) |
| `SD/data/random-battles/gen9/teams.ts` | 151–191 (`RandomTeams` fields), 1414–1470 (`getLevel`, `getForme`), 1614–1660 (`getPokemonPool`) |
| `SD/data/random-battles/gen1/data.json`, `gen1/teams.ts` | whole data.json via `jq`; teams.ts 1–135, 190–320 |
| `SD/config/formats.ts` | 4238–4244 (gen4), 4232–4237 (gen5), 4259–4265 (gen1) |
| `SD/data/rulesets.ts` | 11–45 (`standardag`/`standard`), 160–200 (`obtainable`), 630–676 (`teampreview`), 1352–1404 (`hppercentagemod`, `cancelmod`, `sleepclausemod`) |
| `SD/data/mods/gen4/rulesets.ts` | 1–32 (whole file) |
| `SD/data/mods/gen1/rulesets.ts` | 1–16 |
| `SD/data/mods/gen4/formats-data.ts` | 1–30 + `grep -c randomBattleMoves` (0) + entry count (526) |
| `SD/data/abilities.ts` | 1372–1390 (`flowergift`), 1460–1492 (`forecast`) |
| `SD/data/conditions.ts` | 92–93 (Shaymin-Sky thaw-to-Land) |
| `SD/data/moves.ts` | 15009–15015 (`return` basePowerCallback) |
| `SD/sim/pokemon.ts` | 342–343 (happiness default), 536–555 (`getUpdatedDetails`), 990–1005 + 1310–1325 (Hidden Power request naming), 1159–1184 (`getSwitchRequestData`) |
| `SD/sim/side.ts` | 357–367 (`getRequestData`) |
| `SD/sim/dex-formats.ts` | 286–295 (`maxTeamSize`/`maxMoveCount`/`adjustLevel` defaults) |
| `SD/sim/dex-moves.ts` | 479 (Hidden Power `placeholderFor` id hack) |

poke-env 0.15.0 (`PE = /opt/anaconda3/envs/.../site-packages/poke_env`):

| file | what I read |
|---|---|
| `PE/data/static/pokedex/gen4pokedex.json` | via `jq` (counts, nums, cosmetic formes) |
| `PE/data/static/moves/gen4moves.json` | via `jq` (counts, nums, Hidden Power, zero-BP moves) |
| `PE/data/gen_data.py` | 35–71 (`load_pokedex` cosmetic-forme aliasing) |
| `PE/battle/move.py` | 17 (`SPECIAL_MOVES`), 34–115 (`__init__`, Hidden Power raw_id), 175–182 (`base_power`), 302–319 (`entry`), 561–576 (`retrieve_id`), 702–707 (`type`) |
| `PE/battle/pokemon.py` | 165–180 (`_add_move`), 457–475 (`moved`), 716–743 (`update_from_request`), 804–830 (`available_moves_from_request`) |
| `PE/battle/battle.py` | 119–120, 177–182 (available_moves wiring) |

Repo snapshot (`SNAP = .../scratchpad/main_snapshot`, main@2738025):

| file | what I read |
|---|---|
| `rl/envs/encoder_spec.py` | 1–286 (whole file) |
| `rl/envs/showdown.py` | 110–132 (`ID_SCALE`/`ID_DIM`), 177, 345–398 (`_fill_ids`, `_species_id`, `_move_id`), 832 |
| `rl/networks/entity_deepsets.py` | 48, 130–145, 169–196, 272–278 |
| `rl/envs/normalize.py` | grep only (lines 45, 94–104) |

Helper scripts (read before reusing their output, per the task's rule):

- `.../scratchpad/research/_gen4pool_probe.js` (read in full) → `_gen4pool_probe.out.json`.
  Loads `SD/dist/sim/dex`, `Dex.mod('gen4')`, and `SD/data/random-battles/gen4/sets.json`.
  Pure data; no Battle, no server, no network.
- `.../scratchpad/research/gen4dump.js` (read in full) → `_gen4_dexdump.json`. Same shape;
  I used only its `gen4.format` field (the resolved rule table).
- `.../scratchpad/research/_gen4_vocab.py` (written by me this session; run under
  `nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python`) → `_gen4_vocab.out.json`.
  Reads `poke_env.data.GenData.from_gen(4)` tables + `sets.json`. No Player/Env/PSClient,
  no network, no server.

**Not read** (out of my source family, flagged in "unread / unverified"): Wang / H&L / Metamon
PDFs, ps-ppo, foul-play, metagrok, `MAIN/results/`, WT.

---

## 1. The format entry and its rule table

**tree-verified.** `SD/config/formats.ts:4238-4244`, verbatim:

```
	{
		name: "[Gen 4] Random Battle",
		mod: 'gen4',
		team: 'random',
		bestOfDefault: true,
		ruleset: ['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod'],
	},
```

**tree-verified.** The RESOLVED rule table (from `_gen4_dexdump.json` `.gen4.format.ruleTableKeys`,
produced by `gen4dump.js` calling `dex4.formats.getRuleTable(fmt)`) is exactly:

```
obtainable, obtainablemoves, obtainableabilities, obtainableformes, evlimit,
obtainablemisc, -unreleased, -tag:unobtainable, -nonexistent,
sleepclausemod, hppercentagemod, cancelmod
```

Consequences, each **tree-verified**:

| rule | gen4 randbats | gen1 randbats | note |
|---|---|---|---|
| **Team Preview** | **ABSENT** | absent | The base `standardag` (`SD/data/rulesets.ts:11-17`) carries Team Preview, but gen4randombattle does not use `Standard` at all — it lists four rules directly. Separately, `SD/data/mods/gen4/rulesets.ts:2-7` strips Team Preview out of gen4's `standardag`. Both roads lead to no preview. |
| **Endless Battle Clause** | **ABSENT** | PRESENT | gen1 gets it via gen1-mod `standardag` (`SD/data/mods/gen1/rulesets.ts:2-7`). Gen 4 has no turn-limit clause at all in this format. |
| Sleep Clause Mod | present | present | `SD/data/rulesets.ts:1378-1402`: `onSetStatus` refuses `slp` if any other non-self-inflicted sleeper is alive on the target's side. |
| Freeze Clause Mod | absent | PRESENT (gen1 mod) | gen4 can have multiple frozen mons. |
| HP Percentage Mod | present | present | `reportPercentages = true` (`rulesets.ts:1352-1360`) — opponent HP arrives as a percentage, same as gen 1. |
| Cancel Mod | present | present | `supportCancel = true` (`rulesets.ts:1370-1377`). |
| Species Clause / OHKO Clause / Evasion clauses / Nickname Clause | ABSENT as rules | present (gen1 `Standard`) | Species-uniqueness is nonetheless enforced *inside the generator* (§4). OHKO moves (Fissure, Sheer Cold, Horn Drill, Guillotine) are not banned by rule — but none of them is in the pool (§3), so the practical effect is nil. |

gen1 for comparison, **tree-verified**: `SD/config/formats.ts:4260-4264` is `ruleset: ['Standard']`,
and gen1's `Standard` (`SD/data/mods/gen1/rulesets.ts:8-16`) =
`Standard AG` + `Sleep Clause Mod, Freeze Clause Mod, Species Clause, Nickname Clause, OHKO Clause,
Evasion Moves Clause`, with `banlist: ['Dig', 'Fly']`; gen1 `Standard AG` =
`Obtainable, Desync Clause Mod, HP Percentage Mod, Cancel Mod, Endless Battle Clause`.

**tree-verified.** `maxTeamSize = 6`, `maxMoveCount = 4`, `adjustLevel = null` — no value rules in the
format, so `SD/sim/dex-formats.ts:286-295` defaults apply (`|| 6`, `|| 4`, `|| null`).

**tree-verified.** `gameType: 'singles'`; `bestOfDefault: true` affects only ladder Bo3 offers, not
the single battle we drive.

---

## 2. Where the generator code lives, and the inheritance chain

**tree-verified.** `RandomGen4Teams extends RandomGen5Teams` (`gen4/teams.ts:43`), and the chain is
`gen4 → gen5 → gen6 → gen7 → gen8 → gen9::RandomTeams` (each file's line 1–8 imports; class
declarations at `gen5:53`, `gen6:64`, `gen7:90`, `gen8:74`, `gen9:151`).

Gen 4 **overrides**: `randomSets` (its own `sets.json`), `cullMovePool`, `randomMoveset`,
`shouldCullAbility`, `getAbility`, `getPriorityItem`, `getItem`, `randomSet`,
`getPokemonCompatibility`. It does **not** override `randomTeam` — so **gen5's `randomTeam`
(`gen5/teams.ts:845-983`) is the team-assembly loop**, and `getLevel` / `getForme` /
`getPokemonPool` come from the gen9 base `RandomTeams`.

**tree-verified.** `SD/data/mods/gen4/formats-data.ts` is **not** read by the generator: it contains
only `tier` (526 entries, sampled at lines 1–30; `grep -c randomBattleMoves` = 0), and `getLevel`
consults `species.tier` only when `this.gen === 2` (`gen9/teams.ts:1428-1442`). Gen 4 levels come
from `sets.json` (§5). It still matters indirectly — `Dex.species.get()` merges it, and the probe
confirms no pool species is `isNonstandard` and none has `gen > 4`.

---

## 3. Exact counts (all **tree-verified**; commands given verbatim)

All run from `SD/data/random-battles/gen4`.

| quantity | value | command |
|---|---|---|
| species keys in `sets.json` | **295** | `jq -r 'keys\|length' sets.json` |
| total sets | **464** | `jq -r '[.[].sets[]]\|length' sets.json` |
| distinct moves across all movepools | **181** | `jq -r '[.[].sets[].movepool[]]\|unique\|length' sets.json` |
| distinct abilities | **101** | `jq -r '[.[].sets[].abilities[]]\|unique\|length' sets.json` |
| distinct roles | **8** | `jq -r '[.[].sets[].role]\|unique\|length' sets.json` |
| distinct base species | **267** | `_gen4pool_probe.out.json .nBaseSpecies` |
| level range | **67 – 100** | `jq -r '[.[].level]\|min,max' sets.json` |
| mean level | **83.82** | `jq -r '[.[].level]\|add/length' sets.json` |

Top-level entry schema is exactly `{"level": int, "sets": [...]}`
(`jq -r '[.[]|keys[]]|unique'` → `["level","sets"]`); each set is exactly
`{role, movepool, abilities, preferredTypes?}`
(`jq -r '[.[].sets[]|keys[]]|unique'` → `["abilities","movepool","preferredTypes","role"]`).

### Sets per species

`jq -r '[.[].sets|length]|group_by(.)|map({k:.[0],n:length})[]' sets.json`

| sets | species |
|---|---|
| 1 | 145 |
| 2 | 131 |
| 3 | 19 |

The 19 three-set species: `blastoise wigglytuff poliwrath dewgong hypno snorlax feraligatr kingdra
swampert vigoroth spinda regirock regice rayquaza empoleon mismagius togekiss dusknoir heatran`.

### Roles (`role` is a first-class field on every set)

`jq -r '[.[].sets[].role]|group_by(.)|map({role:.[0],n:length})|sort_by(-.n)[]' sets.json`

| role | sets |
|---|---|
| Bulky Attacker | 81 |
| Bulky Support | 80 |
| Fast Attacker | 76 |
| Setup Sweeper | 65 |
| Staller | 53 |
| Bulky Setup | 47 |
| Wallbreaker | 44 |
| Fast Support | 18 |

Role is **not cosmetic**: it drives hazard-removal enforcement, recovery enforcement, setup
enforcement, the Staller move triple, Choice-item eligibility and the Life Orb / Expert Belt /
Leftovers default cascade (`gen4/teams.ts:290-448`, `:505-624`). Gen 1's data has no analogue.

### Movepool sizes — exact 4-move sets vs sampled pools

`jq -r '[.[].sets[].movepool|length]|group_by(.)|map({k:.[0],n:length})|sort_by(.k)[]' sets.json`

| movepool size | sets |
|---|---|
| 1 | 1 (Ditto: `["transform"]`) |
| 4 | 152 |
| 5 | 168 |
| 6 | 97 |
| 7 | 30 |
| 8 | 15 |
| 9 | 1 |

**153 sets (33%) are exact** (`length <= maxMoveCount`, taken whole — `gen4/teams.ts:493-501`);
**311 sets (67%) are sampled** under the constraint machinery in §6.

### Abilities per set

`jq -r '[.[].sets[].abilities|length]|group_by(.)...'` → **446 sets list one ability, 18 list two.**
The 18 two-ability sets, verbatim (`jq -r 'to_entries[]|.key as $k|.value.sets[]|select((.abilities|length)==2)'`):

```
tentacruel Clear Body/Liquid Ooze    dewgong Hydration/Thick Fat     cloyster Shell Armor/Skill Link
omastar Shell Armor/Swift Swim       kabutops Battle Armor/Swift Swim snorlax Immunity/Thick Fat
ariados Insomnia/Swarm               jumpluff Chlorophyll/Leaf Guard (x2)  qwilfish Poison Point/Swift Swim
kingdra Sniper/Swift Swim (x2)       porygon2 Download/Trace          shiftry Chlorophyll/Early Bird (x2)
pachirisu Pickup/Run Away (x2)       porygonz Adaptability/Download
```

**tree-verified.** No set in the pool lists an ability the species cannot legally have
(`_gen4pool_probe.out.json .abilityMismatch` is `[]`).

### `preferredTypes`

**85 of 464 sets** carry `preferredTypes`; the values seen are
`Bug, Dark, Electric, Fighting, Fire, Flying, Grass, Ground, Ice, Normal, Poison, Psychic, Rock`.
One is sampled per set (`gen4/teams.ts:641`) and it forces a STAB-shaped move of that type
(`:562-577`) and feeds `getMoveType`.

### Levels

`jq -r '[.[].level]|group_by(.)|map({lvl:.[0],n:length})|sort_by(.lvl)[]' sets.json`. Level is
**per species, not per set**, and present for all 295 (`select(.level==null)` → 0).

| L | n | | L | n | | L | n | | L | n |
|---|---|---|---|---|---|---|---|---|---|---|
|67|1| |76|7| |85|13| |94|3|
|68|3| |77|6| |86|16| |95|6|
|69|19| |78|12| |87|11| |96|4|
|70|7| |79|18| |88|18| |97|6|
|71|1| |80|15| |89|4| |98|3|
|72|2| |81|10| |90|12| |99|2|
|73|3| |82|12| |91|9| |100|13|
|74|2| |83|19| |92|10| | | |
|75|6| |84|17| |93|5| | | |

The 13 level-100 species: `farfetchd ditto ledian ariados delibird beautifly dustox delcatty spinda
luvdisc kricketune wormadam wormadamsandy`. `randomTeam` allows **at most one** of them per team
(`gen5/teams.ts:920-923`, "Limit one level 100 Pokemon", scaled by `limitFactor = round(maxTeamSize/6) = 1`).

### Gen-1 pool, for scale (**tree-verified**, `SD/data/random-battles/gen1/data.json`)

| | gen1 | gen4 | ratio |
|---|---|---|---|
| species keys | **146** | **295** | 2.02× |
| distinct moves in pool | **67** | **181** | 2.70× |
| distinct abilities | **0** (`ability: 'No Ability'`, `gen1/teams.ts:303`) | **101** | — |
| distinct items | **0** (`item: ''`, `gen1/teams.ts:305`) | **40** (§7) | — |
| level range / mean | 60–100 / **79.66** | 67–100 / **83.82** | — |
| entry schema | `{level, moves, essentialMoves?, exclusiveMoves?, comboMoves?}` | `{level, sets:[{role, movepool, abilities, preferredTypes?}]}` | — |
| roles | none | 8 | — |
| EVs / IVs | EVs 255 ×6, IVs 30 ×6 (`gen1/teams.ts:271-272`) | EVs 85 ×6, IVs 31 ×6 (§8) | — |

gen1 distinct-move command: `jq -r '[.[]|(.moves//[])[],(.exclusiveMoves//[])[],(.essentialMoves//[])[],(.comboMoves//[])[]]|unique|length' data.json` → 67.

---

## 4. Team-level constraints (`gen5/teams.ts::randomTeam`, lines 845–983) — **tree-verified**

Sampling is **by base species, then by forme**: `getPokemonPool` (`gen9/teams.ts:1614-1646`) buckets
the 295 keys under 267 base species and pushes each base species into `baseSpeciesPool`
`min(ceil(nFormes/3), 3)` times. Resulting pool length **271**
(`_gen4pool_probe.out.json .baseSpeciesPoolLen`). The multi-forme bases and their weights:

| base | formes in pool | weight |
|---|---|---|
| Arceus | 17 | 3 |
| Rotom | 6 | 2 |
| Deoxys | 4 | 2 |
| Wormadam | 3 | 1 |
| Giratina | 2 | 1 |
| Shaymin | 2 | 1 |

So Arceus is ~3/271 likely to be *drawn*, and then a uniform pick among its 17 formes.

Rejection filters, in order (`gen5/teams.ts:869-925`):

1. **Species Clause by base species** — `if (baseFormes[species.baseSpecies]) continue;` (line 872).
   One Arceus per team, one Rotom per team, etc.
2. **Zoroark not in the last slot** (line 875) — dead code in gen 4 (no Zoroark).
3. **Type cap: at most 2 of any type** (`typeCount[typeName] >= 2 * limitFactor`, lines 883-889).
4. **Weakness cap: at most 3 weak to any type; at most 1 double-weak to any type**
   (lines 891-908), using `dex.getEffectiveness(typeName, species) > 0` / `> 1`.
5. **Dry Skin counts as a Fire weakness** (lines 910-914).
6. **At most one level-100 mon** (lines 916-923).
7. **`getPokemonCompatibility`** — gen4's own override (`gen4/teams.ts:737-763`):
   `[['parasect','toxicroak'], 'groudon']` (Dry Skin + sun) and
   `['shedinja', ['tyranitar','hippowdon','abomasnow']]` (Shedinja + sand/hail).

Lead flag: `isLead = (pokemon.length === 0 && !ruleTable.has('pickedteamsize') && !ruleTable.has('teampreview'))`
(line 928) — **with no Team Preview in gen 4, slot 0 IS the lead and gets the lead-specific
Focus Sash branch** (`gen4/teams.ts:600-604`). Gen 5 randbats, by contrast, also has no Team Preview;
gen 6+ does.

`teamDetails` counters written after each accepted mon (lines 962-973), **tree-verified** verbatim keys:

```
hail        <- ability 'Snow Warning' or move 'hail'
rain        <- ability 'Drizzle'      or move 'raindance'
sand        <- ability 'Sand Stream'
sun         <- ability 'Drought'      or move 'sunnyday'
statusCure  <- move 'aromatherapy' or 'healbell'
spikes      <- COUNT of mons with 'spikes'
stealthRock <- move 'stealthrock'
toxicSpikes <- move 'toxicspikes'
rapidSpin   <- move 'rapidspin'
screens     <- move 'reflect' AND move 'lightscreen'
```

Failure mode: `throw new Error("Could not build a random team for ...")` if fewer than 6 assembled
(line 975) — not observed, but it is the only failure path.

### Which of those counters can actually fire in gen 4 — **tree-verified**, and surprising

`jq` over `sets.json` for each move id:

| move | species carrying it |
|---|---|
| `spikes` | 14 |
| `toxicspikes` | 14 |
| `rapidspin` | 13 |
| **`stealthrock`** | **0** |
| **`reflect`** | **0** |
| **`lightscreen`** | **0** |
| **`hail`** | **0** |
| `raindance` | 10 |
| `sunnyday` | 3 |
| `trickroom` | 1 |
| `explosion` | 37 |
| `selfdestruct` | 3 |
| `protect` | 45 |
| `substitute` | 44 |
| `rest` / `sleeptalk` | 35 / 25 |
| `uturn` | 54 |
| `pursuit` / `suckerpunch` | 16 / 31 |
| `trick` / `switcheroo` / `healingwish` | 21 / 4 / 4 |
| `aromatherapy` / `healbell` | 6 / 18 |

**There is NO Stealth Rock, NO Reflect, NO Light Screen and NO Hail anywhere in the gen4 randbats
pool.** The `teamDetails.screens` / `.stealthRock` / `.hail` branches, and the `MOVE_PAIRS` entry
`['lightscreen','reflect']`, are dead code in gen 4. This is worth saying out loud because gen-4 OU
lore is Stealth-Rock-shaped and an encoder designed from lore would budget for it: the hazard game
here is **Spikes + Toxic Spikes only**, cleared by Rapid Spin (13 users). Verified two independent
ways (`jq` over the parsed movepools, and `grep -c '"stealthrock"' sets.json` → 0).

Weather is set only by abilities: `Snow Warning` (abomasnow), `Drizzle` (kyogre), `Drought`
(groudon), `Sand Stream` (tyranitar, hippowdon), plus `Air Lock` (rayquaza) and `Cloud Nine`
(golduck) as suppressors — and by `raindance` (10) / `sunnyday` (3).

---

## 5. Level scaling — **tree-verified**

`getLevel` (`gen9/teams.ts:1420-1446`): `if (this.adjustLevel) return this.adjustLevel;` →
`if (!isDoubles && this.randomSets[species.id]["level"]) return ...` → gen-2 tier table → default 80.
For gen 4 the second line always fires (all 295 entries have `level`). `adjustLevel` is null.
So: **the level is a fixed per-species constant, 67–100, mean 83.82, and it is on the wire** —
`getUpdatedDetails` (`SD/sim/pokemon.ts:536-542`) appends `, L{level}` to `details` for every
level != 100. Same shape as gen 1 (which is 60–100, mean 79.66), so the encoder's existing
level slot carries over unchanged in KIND, only in range.

---

## 6. Move sampling: constraints, in the order they run — **tree-verified**

Module constants (`gen4/teams.ts:5-41`), quoted verbatim:

```js
const RECOVERY_MOVES = ['healorder','milkdrink','moonlight','morningsun','recover','roost','slackoff','softboiled','synthesis'];
const PHYSICAL_SETUP = ['bellydrum','bulkup','curse','dragondance','howl','meditate','screech','swordsdance'];
const SETUP = ['acidarmor','agility','bellydrum','bulkup','calmmind','curse','dragondance','growth','howl','irondefense',
               'meditate','nastyplot','raindance','rockpolish','sunnyday','swordsdance','tailglow'];
const NO_STAB = ['aquajet','bulletpunch','chatter','eruption','explosion','fakeout','focuspunch','futuresight','iceshard',
                 'icywind','knockoff','machpunch','pluck','pursuit','quickattack','rapidspin','reversal','selfdestruct',
                 'shadowsneak','skyattack','suckerpunch','uturn','vacuumwave','waterspout'];
const HAZARDS = ['spikes','stealthrock','toxicspikes'];
const MOVE_PAIRS = [['lightscreen','reflect'],['sleeptalk','rest'],['protect','wish'],
                    ['leechseed','substitute'],['focuspunch','substitute'],['raindance','rest']];
const PRIORITY_POKEMON = ['cacturne','dusknoir','honchkrow','mamoswine','scizor','shedinja','shiftry'];
```

`cullMovePool` (`:81-212`), in order:
1. **At most one Hidden Power, ever** — if any HP is already chosen, every `hiddenpower*` is popped
   from the pool (`:90-110`).
2. Early return if `moves.size + movePool.length <= maxMoveCount`.
3. If two slots are open and exactly one pool move is unpaired under `MOVE_PAIRS`, cull it.
4. If one slot is open, cull both halves of any complete `MOVE_PAIRS` pair.
5. **Team-based culls**, each returning early once the pool fits: `screens` → drop reflect/lightscreen;
   `rapidSpin` → drop rapidspin; `toxicSpikes` → drop toxicspikes; `spikes >= 2` → drop spikes;
   `statusCure` → drop aromatherapy/healbell.
6. **Incompatible pairs** (`:169-206`) — a long table including `[statusMoves, ['healingwish','switcheroo','trick']]`,
   `[SETUP,'uturn']`, `[SETUP, HAZARDS]`, `[SETUP,['pursuit','toxic']]`, `[PHYSICAL_SETUP, PHYSICAL_SETUP]`,
   `['rest','substitute']`, `['surf','hydropump']`, `['discharge','thunderbolt']`, `['payback','pursuit']`,
   plus named hardcodes for Manectric, Walrein, Smeargle, Seviper, Jirachi, Blaziken.
7. Unless `role === 'Staller'`, **at most one** of `['hypnosis','stunspore','thunderwave','toxic','willowisp','yawn']`.

`randomMoveset` (`:217-448`), in order: exact-pool shortcut → `species.requiredMove` → **Facade if
Guts** → **Seismic Toss / Spore / Volt Tackle forced if present** → Rapid Spin forced on
`Bulky Support` when the team lacks it → **STAB priority move** for `Bulky Attacker`/`Bulky Setup`
and every `PRIORITY_POKEMON` → per-type STAB enforcement driven by `moveEnforcementCheckers`
(`:51-79`; 15 type checkers with per-type conditions — e.g. Steel only fires for Metagross, Rock only
for `baseStats.atk >= 80`, Flying never for Aerodactyl) → preferred-type STAB → a STAB if none yet →
**one of Spikes/Toxic Spikes** (Toxic Spikes forced if the team already has Spikes) → recovery for
the four bulky/staller roles → Staller's `['protect','toxic','wish']` → a `SETUP` move for any
`*Setup*` role → a non-`NO_STAB` attack if the set has none → **a coverage move of a different type**
for `Fast Attacker`/`Setup Sweeper`/`Bulky Attacker`/`Wallbreaker` when only one damaging move exists
→ random fill, **pulling in the partner of any `MOVE_PAIRS` move drawn**.

Finally the four chosen moves are **shuffled** before the set is returned
(`gen4/teams.ts:719-721`: `this.prng.shuffle(shuffledMoves)`), so slot order carries no information.
Gen 1 does the same (`gen1/teams.ts:295-297`).

---

## 7. Ability, item, EV/IV/nature policy

### Ability choice — **tree-verified** (`gen4/teams.ts:450-505`)

```js
if (abilities.length <= 1) return abilities[0];
if (species.id === 'dewgong') return moves.has('raindance') ? 'Hydration' : 'Thick Fat';
if (species.id === 'cloyster' && counter.get('skilllink')) return 'Skill Link';
// else: filter by shouldCullAbility, sample uniformly from survivors;
// if all culled, prefer a weather ability; else sample uniformly from all.
```

`shouldCullAbility` (`:450-470`) culls only four: `Chlorophyll`/`Leaf Guard` without team sun,
`Swift Swim` without team rain, `Rock Head` without a recoil move, `Skill Link` without a
multi-hit move. Everything else survives. So for 446/464 sets the ability is deterministic; for
18 it is a coin flip conditioned on the team and the chosen moves.

### Items the generator can assign — **tree-verified**, exhaustive

I enumerated every capitalized quoted literal in `gen4/teams.ts`
(`grep -o "'[A-Z][A-Za-z]*\( [A-Za-z]*\)*'" teams.ts | sort -u`) and separated item names from
role / ability / stat / type names by checking each against the gen4 item table
(`_gen4pool_probe.out.json .items`). **Gen 4 fully overrides both `getPriorityItem` and `getItem`
and both terminate (`return 'Leftovers'`), so no gen5/gen6 item code runs.** The closed set is:

**A. `getPriorityItem` (`:505-552`), checked first, in this order:**

| item | condition (verbatim-ish) | gen4-legal? |
|---|---|---|
| `species.requiredItems` sample | any species with `requiredItems` — see D | yes |
| Soul Dew | `species.id === 'latias' \|\| 'latios'` | yes (gen 3; unbanned in gen4 randbats — +50% SpA/SpD) |
| Thick Club | `marowak` | yes (gen 2) |
| Light Ball | `pikachu` | yes (gen 2) |
| Focus Sash | `shedinja \|\| smeargle`; also `delibird && moves.has('counter')` | yes (gen 4) |
| Custap Berry | `wobbuffet` | yes (gen 4) |
| Choice Scarf / Quick Powder / Sitrus Berry | `ditto` → `this.sample([...])` | yes |
| Choice Scarf | `rampardos && role === 'Fast Attacker'`; also `moves.has('waterspout')` | yes |
| Life Orb | `honchkrow`; `ability === 'Magic Guard'`; `Speed Boost && yanmega` | yes |
| Leftovers | `shuckle`; `role === 'Staller'` | yes |
| Toxic Orb | `ability === 'Poison Heal' \|\| moves.has('facade')` | yes |
| Choice Scarf / Band / Specs | `healingwish\|switcheroo\|trick` in moves: Scarf if `60 <= spe <= 108 && role !== 'Wallbreaker' && !priority`, else Band if Physical > Special, else Specs | yes |
| Sitrus Berry | `moves.has('bellydrum')`; `ability === 'Unburden'` | yes |
| Light Clay | `moves.has('lightscreen') && moves.has('reflect')` | yes — **dead in gen4**, neither move is in the pool |
| Damp Rock / Chesto Berry | `moves.has('rest') && !sleeptalk && ability not in {Natural Cure, Shed Skin}` → Damp Rock if `raindance && Hydration`, else Chesto Berry | yes |

**B. `getItem` (`:554-624`), the fallthrough:**
Black Glasses (Pursuit+Sucker Punch+Dark counter), Choice Specs / Choice Scarf (4 special moves;
Scarf at 1/2 if `spa >= 90` and scarf-reqs), Choice Scarf (3 special + explosion/selfdestruct on a
Fast Attacker), Choice Specs (3 special + U-turn), Choice Band / Choice Scarf (4 physical, not
Jirachi, no fakeout/rapidspin), Silk Scarf (Normal-type with Fake Out), Lustrous Orb (`palkia`),
Stick (`farfetchd`), Lum Berry (Outrage + setup, no Sleep Talk), Leftovers (protect or substitute),
Focus Sash (`Fast Support` lead, `hp+def+spd < 255`, no recovery, hazards-or-setup, no recoil unless
Rock Head), Life Orb / Leftovers (`Fast Support` default), Expert Belt (`Fast Attacker`, no status
move, no Dragon/Normal/Poison counters and no `noExpertBeltMoves`), Life Orb
(Fast Attacker / Setup Sweeper / Wallbreaker without Rapid Spin), **Leftovers** (final default).

**C. `randomSet` post-hoc swap (`:668-671`):** `if (item === 'Leftovers' && types.has('Poison')) item = 'Black Sludge';`

**D. `species.requiredItems` reachable in this pool** (`_gen4pool_probe.out.json .requiredItems`) —
**17 items**: `Griseous Orb` (giratinaorigin) and the 16 typed Arceus plates:
`Insect, Dread, Draco, Zap, Fist, Flame, Sky, Spooky, Meadow, Earth, Icicle, Toxic, Mind, Stone,
Iron, Splash`. (Arceus-Normal — key `arceus` — has **no** requiredItems and therefore falls through
to the generic cascade like any other mon.)

**Total closed item universe: 23 named literals + Griseous Orb + 16 plates = 40 items** (plus
"no item" once Knock Off / a consumed Berry / Trick has taken it away). Every one is gen ≤ 4 with
`isNonstandard = null` in the gen4 mod (`_gen4pool_probe.out.json .items`): so **all 40 are
gen4-legal**; nothing the generator can produce is a later-gen item.

Two absences worth noting, both **tree-verified**: **Dialga never gets Adamant Orb** (there is no
`dialga` branch; Palkia's Lustrous Orb at `:596` has no Dialga twin), and **Light Clay is
unreachable** because Reflect and Light Screen are not in the pool.

Mid-battle item churn is real: `trick` (21 species) and `switcheroo` (4) **swap items between the
two active mons**, so an item can move from one side to the other; Knock Off (in `NO_STAB`, so it
appears but never as sole STAB) removes one; Berries and Focus Sash are consumed. The universe stays
40, because both teams come from the same generator.

### EVs / IVs / nature / happiness / gender / shiny — **tree-verified** (`gen4/teams.ts:646-736`)

```js
const evs = { hp: 85, atk: 85, def: 85, spa: 85, spd: 85, spe: 85 };
const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 };
```

- **EVs: 85 in every stat = 510 total, exactly the gen-4 cap.** Modified afterwards only by:
  the Sitrus/Substitute and Sitrus/Belly Drum HP-parity loops (`:697-707`, `evs.hp -= 4` until the
  computed HP satisfies `hp % 4 === 0` or `hp % 2 === 0`); `evs.atk = 0` when the set has no physical
  move, no Transform and no `forceofthefallenmod` (`:709-713`); `evs.spe = 0` when the set has
  `gyroball`, `metalburst` or `trickroom` (`:715-718`).
- **IVs: 31 everywhere**, then: Hidden Power's per-type `HPivs` overwritten in
  (`:687-695`); `ivs.atk = hasHiddenPower ? (ivs.atk || 31) - 28 : 0` on physical-less sets;
  `ivs.spe = hasHiddenPower ? (ivs.spe || 31) - 28 : 0` on gyroball/metalburst/trickroom sets.
- **NO NATURE FIELD IS EMITTED.** The returned set object (`:723-736`) has
  `{name, species, speciesId, gender, shiny, level, moves, ability, evs, ivs, item, role}` — no
  `nature`. `dex.natures.get('')` does not exist (`_gen4pool_probe.out.json .natureEmpty` =
  `[false, "", null, null]`), so **every gen4 randbats mon is nature-neutral.** No nature vocab is
  needed. (Gen 1 randbats likewise emits no nature; the Challenge Cup path hard-codes `'Serious'`.)
- **Happiness is not set**, so `SD/sim/pokemon.ts:342` gives 255 → `Return` is **102 BP** on every
  one of its **39** users, and the active request names the move `"Return 102"`.
- `gender: species.gender` — 92 of the 295 pool species carry a fixed gender/genderless marker;
  the rest are randomized by the sim and appear in `details`.
- `shiny: this.randomChance(1, 1024)` — appends `, shiny` to `details` about 0.1% of the time.

### The Hidden Power IV rule — **tree-verified** (`gen4/teams.ts:679-695`)

```js
let hasHiddenPower = false;
for (const move of moves) { if (move.startsWith('hiddenpower')) hasHiddenPower = true; }
if (hasHiddenPower) {
  let hpType;
  for (const move of moves) { if (move.startsWith('hiddenpower')) hpType = move.substr(11); }
  const HPivs = this.dex.types.get(hpType).HPivs;
  for (iv in HPivs) { ivs[iv] = HPivs[iv]!; }
}
```

The per-type IV spreads and the resulting Hidden Power, all at **power 70**
(`_gen4pool_probe.out.json .hpivs`, computed with `dex4.getHiddenPower`):

| HP type | HPivs (all others 31) | power | power after `atk -= 28` |
|---|---|---|---|
| Electric | spa 30 | 70 | 70 |
| Fighting | def/spa/spd/spe 30 | 70 | 70 |
| Fire | atk/spa/spe 30 | 70 | 70 |
| Flying | hp/atk/def/spa/spd 30 | 70 | 70 |
| Grass | atk/spa 30 | 70 | 70 |
| Ground | spa/spd 30 | 70 | 70 |
| Ice | atk/def 30 | 70 | 70 |
| Rock | def/spd/spe 30 | 70 | 70 |
| (Bug, Dragon, Ghost, Poison, Psychic, Steel, Water also defined; **Dark** is the all-31 default) | | 70 | 70 |

**Only 8 Hidden Power types actually appear in the gen4 randbats pool**
(`jq -r '[.[].sets[].movepool[]|select(startswith("hiddenpower"))]|unique[]'`):
`hiddenpowerelectric, hiddenpowerfighting, hiddenpowerfire, hiddenpowerflying, hiddenpowergrass,
hiddenpowerground, hiddenpowerice, hiddenpowerrock`. All are **power 70** and category **Special**
in the gen 4 mod, and the `-28` attack-IV tweak preserves both type and power.

**tree-verified.** Hidden Power's protocol shape in gen 4: the **switch request** sends
`hiddenpowerfire` (`SD/sim/pokemon.ts:1172-1175`:
`` return `${move}${toID(this.hpType)}${this.battle.gen < 6 ? '' : this.hpPower}` ``, so **no power
suffix at gen 4**); the **active move request** sends `move: "Hidden Power Fire 70"` with
`id: "hiddenpower"` (`:996-998`: `moveName = \`Hidden Power ${this.hpType}\`; if (gen < 6) moveName += \` ${this.hpPower}\``).
`SD/sim/dex-moves.ts:479` is why the id collapses: `if (data.placeholderFor) this.id = toID(data.placeholderFor);`.

---

## 8. What poke-env 0.15.0 does with this pool (the parts that set vocab)

**source-verified.** `PE/battle/move.py:561-576`, `Move.retrieve_id`, verbatim:

```python
move_name = to_id_str(move_name)
if move_name.startswith("return"):      return "return"
if move_name.startswith("frustration"): return "frustration"
if move_name.startswith("hiddenpower"): return "hiddenpower"
return move_name
```

**source-verified.** `PE/battle/pokemon.py:165-180` (`_add_move`) stores the Move under the
**collapsed** key (`base_moves["hiddenpower"]`) but constructs it with `raw_id`, and
`PE/battle/move.py:104-112` then *restores* the typed id:

```python
if move_id.startswith("hiddenpower") and raw_id is not None:
    base_power = "".join([c for c in raw_id if c.isdigit()])
    self._id = "".join([c for c in to_id_str(raw_id) if not c.isdigit()])
```

So `move.id == "hiddenpowerfire"`, `move.type == FIRE`, `move.base_power == 70` — **the encoder's
move block sees the right type and power.** The dict *key* stays `"hiddenpower"`, which is exactly
what `available_moves_from_request` (`PE/battle/pokemon.py:809-826`) needs, since the active request
sends `id: "hiddenpower"`.

**source-verified.** But `Move.entry` (`PE/battle/move.py:302-319`) looks up `self._id` in
`GenData.from_gen(4).moves` — and **all 17 `hiddenpower*` entries in
`PE/data/static/moves/gen4moves.json` carry `num: 237`**
(`jq -r 'to_entries[]|select(.key|startswith("hiddenpower"))|"\(.key) \(.value.num)"'`). Therefore
`_move_id` (`SNAP rl/envs/showdown.py:384-393`, `move.entry.get("num", 0)`) returns **237 for every
Hidden Power type** — a num-based move id cannot tell HP Fire from HP Ice.

**source-verified.** `Return` reaches poke-env as `return102` in the switch request; `retrieve_id`
strips it to `"return"`, and **the digit-stripping base-power override in `Move.__init__` applies
only to Hidden Power**, so `move.base_power` for Return is `entry["basePower"]` = **0**
(`jq -c '.return|{num,basePower}' gen4moves.json` → `{"num":216,"basePower":0}`), not 102.
Nine pool moves have `basePower: 0` in poke-env's gen4 table while dealing real damage:
`counter, grassknot, lowkick, metalburst, mirrorcoat, nightshade, return, seismictoss, superfang`.
`return` alone is on **39** species. (Gen 1 had the same *kind* of hole — `counter`, `nightshade`,
`seismictoss`, `superfang`, `dragonrage`, `sonicboom` — so this is a scale change, not a new class.)

**source-verified.** `PE/data/gen_data.py:52-63`: `load_pokedex` walks `cosmeticFormes` and
**rewrites each cosmetic-forme key to point at the base entry** before returning. In the raw
`gen4pokedex.json` exactly four keys lack a `num` field — `burmysandy, burmytrash, gastrodoneast,
shelloseast` — and this loader repairs all four. Confirmed at runtime:
`GenData.from_gen(4).pokedex["gastrodoneast"]["num"]` is **423** (`_gen4_vocab.out.json`). So
`_species_id("gastrodoneast", GEN4)` is safe. Worth recording as a trap poke-env happens to close,
not one we can rely on being closed for other formes.

**source-verified.** poke-env ships **no ability table and no item table** — `PE/data/static/`
contains only `learnset.json`, `natures.json`, `replay_template.html`, `moves/`, `pokedex/`,
`typechart/`. `mon.ability` and `mon.item` are bare id strings. **Any ability or item vocabulary must
be built and frozen by us**; there is no `num` to borrow the way species and moves have one.

**source-verified.** `SPECIAL_MOVES = {"struggle", "recharge", "fight"}` (`PE/battle/move.py:17`),
unchanged across generations — the gen1 spec's `special_move_ids` carries over verbatim.

---

## 9. VOCAB SIZES for a gen-4 encoder

### 9a. Species

| scheme | size | what it loses |
|---|---|---|
| **pool-local, entries** | **295** | nothing at team-generation time |
| **pool-local, incl. mid-battle formes** | **300** | nothing (see below) |
| **poke-env `num`** | **267 distinct** in 1..493, table must be sized **494** | collapses 28 formes onto 6 nums |
| gen-4 universe (gen4 mod, non-nonstandard) | **530 forme entries / 493 base species** | — |

**tree-verified / source-verified.** The 295 pool keys map onto only **267 distinct `num`s**
(`_gen4_vocab.out.json`), because `num` is per base species:

```
386 -> deoxys, deoxysattack, deoxysdefense, deoxysspeed          (4 -> 1)
413 -> wormadam, wormadamsandy, wormadamtrash                     (3 -> 1)
479 -> rotom, rotomfan, rotomfrost, rotomheat, rotommow, rotomwash (6 -> 1)
487 -> giratina, giratinaorigin                                   (2 -> 1)
492 -> shaymin, shayminsky                                        (2 -> 1)
493 -> arceus + 16 typed Arceus formes                           (17 -> 1)
```

That collapse is **not** cosmetic: Rotom-Wash (Water/Electric) and Rotom-Heat (Fire/Electric) share
one id; Deoxys-Attack (180/20/180/20/150 offensive shell) and Deoxys-Defense (50/160/... wall) share
one id; every Arceus plate shares one id. Types and base stats live in the mon block, so a network
can partly recover it — but the **species embedding row** cannot.

**Formes that can appear mid-battle beyond the 295 keys** (each **tree-verified**):

| forme | how it appears | in the pool? |
|---|---|---|
| **Gastrodon-East** | `getForme` samples `[name] + cosmeticFormes` (`gen9/teams.ts:1450`); `gastrodon` is the pool's only species with `cosmeticFormes` (`_gen4pool_probe.out.json .cosmetic`) | new species STRING, same num 423 |
| **Castform-Sunny / -Rainy / -Snowy** | `Forecast` (`SD/data/abilities.ts:1460-1486`) `formeChange`s on weather; Castform is in the pool with `Forecast` as its only ability | new strings, all num 351 |
| **Cherrim-Sunshine** | `Flower Gift` (`SD/data/abilities.ts:1372-1388`) in sun; Cherrim is in the pool with `Flower Gift` on both sets | new string, num 421 |
| Shaymin (from Shaymin-Sky) | `SD/data/conditions.ts:92-93` — freezing Shaymin-Sky reverts it to Shaymin | already a pool key |
| Ditto's transform target | `transform` copies the opposing active's species | always a pool key |

Rotom's appliance formes, Giratina-Origin, Wormadam's cloaks, Deoxys's formes and Arceus's plates are
all **fixed at team generation in gen 4** (`_gen4pool_probe.out.json .battleOnlyKeys` is `[]` for the
pool). So the wire-visible species universe is **295 + 1 + 3 + 1 = 300 strings**, over **267 `num`s**.

`details` on the wire is the full forme name plus level (`SD/sim/pokemon.ts:536-542`,
`name + (level === 100 ? '' : ', L' + level) + gender + shiny`) — nothing masks the forme, and with
no Team Preview the opponent's team is revealed one switch at a time.

### 9b. Moves — **pool IS the universe, plus Struggle**

**tree-verified.** Checked every move-calling move against the pool
(`jq -r --arg m "$m" '[to_entries[]|select(.value.sets[].movepool[]==$m)|.key]'`):

| move | in pool? |
|---|---|
| `metronome`, `assist`, `copycat`, `mimic`, `sketch`, `mefirst`, `mirrormove`, `naturepower`, `magiccoat`, `snatch` | **none** |
| `sleeptalk` | 25 species — but it can only call **the user's own** moves, which are pool moves |
| `transform` | **ditto only** — copies the opposing active's moves, which are pool moves |

So there is **no move-calling escape hatch in gen 4 randbats**. The move universe is closed:

| scheme | size | notes |
|---|---|---|
| **pool-local** | **181** | includes 8 typed Hidden Powers |
| **pool-local + Struggle** | **182** | `struggle` num 165; it is also one of poke-env's SPECIAL_MOVES |
| **+ poke-env's synthetic `recharge`/`fight`** | 184 slots if given rows | the gen1 spec routes these through `special_move_ids` instead |
| **poke-env `num`** | **174 distinct** in 1..465, table must be sized **468** | 8 HP types collapse to num 237 |
| gen-4 move universe (gen4 mod, non-nonstandard) | **483 entries / 467 real moves**, max num **467** | poke-env's gen4moves.json has 486 entries, 467 positive nums, and 3 CAP moves at nums −1/−2/−3 (`paleowave`, `shadowstrike`, `polarflare`) |

Category split of the 181 pool moves (`_gen4pool_probe.out.json .moveCats`):
**Physical 75, Special 52, Status 54** — the gen-4 physical/special split is per-move, exactly as the
landed spec's docstring already anticipates (`SNAP rl/envs/encoder_spec.py:52-56`).
Type split (`.moveTypes`): Normal 39, Fighting 18, Grass 16, Fire 13, Psychic 12, Dark 12, Flying 8,
Water 8, Ice 7, Bug 7, Electric 7, Rock 7, Dragon 6, Steel 6, Poison 5, Ghost 5, `???` 1
(the `???`-type move is `curse`, confirmed by filtering the 181 pool moves on `type == "???"` in poke-env's `gen4moves.json`).

### 9c. Abilities

| scheme | size |
|---|---|
| **pool-local** | **101** |
| gen-4 universe (gen4 mod, non-nonstandard) | **123**, max `num` **123** |

**tree-verified / source-verified.** 101 distinct ability names across the 464 sets. Gen 1 has
**zero** — this is an entirely new block. Because poke-env ships no ability table, the id must be a
frozen table of our own; **123 (or 101) fits comfortably under 255.**

### 9d. Items

| scheme | size |
|---|---|
| **generator-reachable (closed)** | **40**, + a "none" row = **41** |
| gen-4 universe (gen4 mod, non-nonstandard) | **210** |
| Showdown item `num` for the 40 | 112 (Griseous Orb) .. **313** (Iron Plate) — 4 plates exceed 255 |

**tree-verified.** 40 is exhaustive and closed (§7). **A pool-local item id (0..40) is the obvious
choice** — poke-env has no item table to borrow a `num` from anyway, and the Showdown item nums for
the plates run past 255.

### 9e. The `id/256` question — **tree-verified, and this is the load-bearing one**

`SNAP rl/envs/showdown.py:118-125`, verbatim:

```
# Values are emitted as id/256.0 in [0, 1): exact in float32
# (256 is a power of two), inside the declared Box(low=-1, high=4), and
# recovered as round(x*256) inside the tokenizer. Unknown/unrevealed -> 0.
ID_SCALE = 256.0
```

and `SNAP rl/networks/entity_deepsets.py:169-170`: `species_vocab: int = 152, move_vocab: int = 166`.

**Every vocab that exceeds 255, and what each id scheme costs:**

| vocab | pool-local size | > 255? | `num`-based size | > 255? | verdict |
|---|---|---|---|---|---|
| **species** | 295 (300 with mid-battle formes) | **YES** | 494 rows (267 used, max num 493) | **YES** | **no scheme fits under 255** |
| **moves** | 181 (182 with Struggle) | no | 468 rows (174 used, max num 467) | **YES** | pool-local fits; `num` does not |
| **abilities** | 101 | no | (poke-env has no table) | — | fits either way |
| **items** | 40 | no | Showdown nums to 313 | **YES** for 4 plates | pool-local fits |

Concretely: `493/256 = 1.92578125` and `467/256 = 1.82421875`. Both are still **exactly representable
in float32** (any integer over 2^8 is), both still sit inside the declared `Box(low=-1.0, high=4.0)`
(`SNAP rl/envs/showdown.py:177, 832`), and `(x * 256.0).round().long()` still recovers them exactly
(`entity_deepsets.py:138`). What actually breaks is (a) the documented `[0, 1)` invariant in the
docstring, and (b) the two embedding table sizes, which must go **152 → 494** and **166 → 468**
(or → 301 / 183 if we go pool-local). `ID_SCALE = 1024.0` would restore `[0, 1)` for every gen-4 id
in one line; so would keeping 256.0 and rewriting the docstring. This is an open question, §11.

The landed seam already names the right ranges: `SNAP rl/envs/encoder_spec.py:75-76`,
"*id ranges: species 1..493 and moves 1..467 at gen 4 (embedding table sizes in
rl/networks/entity_deepsets.py follow)*" — **confirmed correct against both the gen4 mod
(`universeSpeciesMaxNum` 493, `universeMovesMaxNum` 467) and poke-env's gen4 tables**
(pokedex max num 493, moves max num 467).

**The recommendation this pool argues for:** species should be **pool-local (300 rows)**, not
`num`-based — a `num` id destroys the Rotom/Deoxys/Arceus/Giratina/Shaymin distinctions, and a
pool-local table is 40% smaller besides. Moves can be either, but `num` costs the 8 Hidden Power
types their identity; **pool-local (182 rows)** keeps them and fits under 255. The cost of
pool-local is that the table is a frozen artifact tied to this vendored `sets.json` — if the
vendored Showdown is ever updated, unseen species/moves must map to row 0 exactly the way
out-of-range `num`s do today.

---

## 10. Gen-1 encoder assumptions this breaks

Each is **tree-verified** against `SNAP rl/envs/showdown.py` / `encoder_spec.py` and the vendored data.

1. **"Ids fit in a byte."** `ID_SCALE = 256.0` with the `[0, 1)` invariant holds for gen 1
   (151 species / 165 moves). At gen 4 **no species scheme fits**: 493 by `num`, 300 pool-local.
   Docstring + `entity_deepsets` vocab defaults both change.
2. **"Species identity = one id."** Gen 1 has no formes at all. Gen 4's pool ships 28 forme entries
   that share a base `num`, plus 5 more formes that only appear mid-battle. Any `num`-keyed species
   embedding silently merges Deoxys-Attack with Deoxys-Defense.
3. **"The pool has no items and no abilities."** Gen 1 emits `item: ''` and `ability: 'No Ability'`
   (`gen1/teams.ts:303-305`). Gen 4 gives every mon one of **40** items and one of **101** abilities,
   both wire-visible, both needing a NEW per-mon block — i.e. a `MON_DIM` change, i.e. an `OBS_DIM`
   change, i.e. the "changing OBS_DIM invalidates every checkpoint" landmine.
4. **"Items are static."** They are not: `trick` (21 species) and `switcheroo` (4) **swap items
   across the two sides mid-battle**, Knock Off removes one, Berries and Focus Sash are consumed.
   An item slot must be a live per-mon feature, not a team-generation constant.
5. **"Ability is static."** Mostly true in gen 4, but `Trace` (porygon2) copies the opponent's, and
   `Forecast` / `Flower Gift` change the mon's SPECIES mid-battle. poke-env models this as
   `Pokemon.temporary_ability` (`PE/battle/pokemon.py:719-725`) — a second ability slot may be needed.
6. **"A mon's type is fixed for the battle."** Castform (Forecast) becomes Fire/Water/Ice with the
   weather; Cherrim becomes... still Grass, but changes species string; **Color Change** is in the
   pool's ability list (kecleon). The type one-hot must be read from the live `mon.types`, never
   cached from the pokedex at reveal time.
7. **"Move base power is a constant from the dex."** Already partly false in gen 1, but gen 4 adds
   `return` (**39 species**, real BP 102, poke-env reports 0) plus `grassknot` / `lowkick`
   (weight-based) and `metalburst`. §8.
8. **"There is exactly one Hidden Power id per move."** New in gen 2+. Eight typed HPs in the pool,
   all sharing `num` 237 in poke-env's table; the typed identity survives only in `move.id` /
   `move.type`, not in `entry["num"]`.
9. **"Sleep Clause + Freeze Clause + Endless Battle Clause."** Gen 4 randbats has Sleep Clause Mod
   only. **No Freeze Clause** (multiple frozen mons are legal) and **no Endless Battle Clause** —
   episode-length assumptions and any turn-cap in the harness need re-checking against a format with
   no built-in endless guard.
10. **"Levels 60–100."** Gen 4 is 67–100 with a higher mean (83.82 vs 79.66) and a **hard cap of one
    level-100 mon per team**, which gen 1's generator also has but with only 2 candidates vs gen 4's 13.
11. **"Six switch actions + four move actions = 10."** Still true at gen 4 —
    `SinglesEnv.get_action_space_size(4)` is 10, gimmicks start at gen 6
    (`SNAP rl/envs/encoder_spec.py:79-83`). **This one does NOT break.**
12. **"The set prior is `rl/envs/randbats_prior.py`."** That file is gen-1 randbats data and
    `_opponent_move_slots` reads it directly (`encoder_spec.py:71-73`). A gen-4 prior must be built
    from **this** `sets.json`, and the gen-4 shape is different in kind: **role-conditioned pools
    with 33% exact sets and 67% sampled**, not gen 1's `moves`/`essentialMoves`/`exclusiveMoves`/
    `comboMoves`. Two-thirds of the pool needs a *sampling model*, not a lookup.

---

## 11. Open questions for the maintainer

1. **Pool-local ids or `num` ids?** My recommendation is **pool-local for species** (300 rows) and
   **pool-local for moves** (182 rows), because `num` merges the six Rotom appliances, the four
   Deoxys formes, the 17 Arceus plates, Giratina's two formes, Shaymin's two, Wormadam's three,
   and the eight Hidden Power types. The losing argument is real: `num` ids are *stable across a
   Showdown update* and *shared with gen 9* (a gen-9 chapter would reuse the same table), whereas a
   pool-local table is a frozen artifact keyed to this vendored `sets.json` and needs an explicit
   "unseen → row 0" rule and a regeneration script. If the plan is gen4 → gen9 with one embedding
   table, `num` wins on portability; if the plan is a per-chapter encoder, pool-local wins on
   information.
2. **`ID_SCALE`.** Keep 256.0 and rewrite the `[0, 1)` docstring (ids up to 1024 still round-trip
   inside `Box(high=4)`), or move to 512.0/1024.0 to restore the invariant? One line either way,
   but it is a bit-for-bit change to the gen-4 encoding and should be decided before any gen-4
   checkpoint exists.
3. **Do items and abilities get embeddings or one-hots?** 40 items and 101 abilities are small
   enough to one-hot per mon (141 extra dims × 12 mons = 1,692 — too much) or per ACTIVE mon only
   (141 × 2 = 282). An id-suffix + embedding costs 12 more id slots. This is an `OBS_DIM` decision
   and therefore a checkpoint-invalidating one; it should be pre-registered, not discovered.
4. **Is "no Stealth Rock in the gen4 randbats pool" a surprise worth confirming?** It is
   double-verified in the vendored data, and it materially changes what a gen-4 agent must learn
   (Spikes/Toxic Spikes/Rapid Spin, no Rocks). If the maintainer's mental model of gen-4 randbats
   includes Stealth Rock, that model is of a *different* (probably newer or older) `sets.json`
   than the one at `59da482`.
5. **No Endless Battle Clause.** Gen 4 randbats has no clause-level guard against an unending battle.
   With Leftovers/Black Sludge/Recover/Rest/Protect/Substitute all in the pool and no Rocks to break
   stall, do we want a harness-level turn cap for training, and if so does it become a disclosed
   deviation from the format?
6. **Does the `role` field enter the encoder or only the prior?** Gen 4's `sets.json` labels every set
   with one of 8 roles, and role determines items and move enforcement. A gen-4 opponent-modelling
   prior could predict role first and moves conditioned on it. That is a real modelling opportunity
   gen 1 did not have — but it is also a place to over-engineer.
7. **`Return`'s base power.** poke-env reports 0 for 39 of 295 species' signature attack. Do we patch
   it in our encoder (happiness is always 255 in randbats, so BP is always 102), or leave the slot
   at 0 and let the network learn "move id 216 means 102"? Patching is three lines and correct;
   not patching keeps us honest to poke-env's surface.

---

## 12. Cross-references for the other docs

- **`mechanics_delta.md`** — from this note: no Team Preview; **no Endless Battle Clause**;
  Sleep Clause Mod present, Freeze Clause absent; abilities are live (Trace, Forecast, Flower Gift,
  Color Change, Intimidate, Multitype, Wonder Guard all in the pool's 101); items are live and
  **transferable** (Trick/Switcheroo, 25 species); hazards are Spikes + Toxic Spikes only, cleared by
  Rapid Spin (13 users); weather is ability-driven (Snow Warning / Drizzle / Drought / Sand Stream)
  plus Rain Dance (10) / Sunny Day (3), with Air Lock (rayquaza) and Cloud Nine (golduck) as
  suppressors; Trick Room exists on exactly 1 species; Explosion on 37 and Self-Destruct on 3;
  Soul Dew is legal and always on Latias/Latios.
- **`pokeenv_gen4_survey.md`** — from this note: `Move.retrieve_id` collapses hiddenpower/return/
  frustration; `Move.__init__` restores the typed HP id from `raw_id` but NOT Return's base power;
  all 17 HP entries share `num` 237; nine pool moves report `basePower: 0`; `load_pokedex` repairs
  the four `num`-less cosmetic stubs; **poke-env ships no ability and no item table**;
  `SPECIAL_MOVES` unchanged; `SinglesEnv.get_action_space_size(4) == 10`.
- **`encoder_requirements.md`** — §9 (vocab sizes), §10 (broken assumptions), §11 (the two id
  decisions). The landed seam's stated ranges (species 1..493, moves 1..467) are correct.
- **`anchors_and_eval.md`** — the pool's shape bears on what a heuristic baseline can do: 67% of sets
  are sampled from a >4 pool, so a fixed-set opponent model is wrong two-thirds of the time; and the
  8-role labelling gives a natural stratification for eval reporting.
- **`open_questions.md`** — §11 items 1, 2, 3, 5 are maintainer rulings with real losing arguments.

---

## 13. Unread / unverified

- **needs-live-verification** — that a real `gen4randombattle` battle's `|switch|` line carries the
  full forme string (`Rotom-Wash, L84, M`) and that poke-env's `Pokemon.species` becomes
  `rotomwash`. I read `SD/sim/pokemon.ts:536-542` (`getUpdatedDetails` returns `this.species.name`)
  and poke-env's `_update_from_details`, but I did not observe a battle. The check, when the ladder
  run is done: start the local server, run one `gen4randombattle`, and grep the log for `|switch|`
  lines containing `Rotom-`, `Arceus-`, `Deoxys-`, `Gastrodon-East`, `Castform-Sunny`.
- **needs-live-verification** — the actual *frequency* of Gastrodon-East, Castform formes and
  Cherrim-Sunshine on the wire. `getForme` makes Gastrodon-East a 1/2 coin flip whenever Gastrodon
  is drawn; the Castform/Cherrim formes need weather to be up. The check: N=1000 generated teams via
  `Teams.generate('gen4randombattle')` (a pure generator call, no battle), tallying `set.species`.
- **needs-live-verification** — whether an obs-normalization wrapper (`SNAP rl/envs/normalize.py`,
  `normalize_obs` z-scores and clips at ±10σ) is ever applied to the id suffix, which would break the
  `round(x*256)` recovery. This is a gen-agnostic question about the existing gen-1 stack; I did not
  trace which wrappers wrap which runs.
- **not read** — Wang's thesis, Huang & Lee, Metamon, ps-ppo, foul-play, metagrok, `prior_work/README.md`.
  I stayed inside my source family (vendored Showdown + poke-env + the repo snapshot) as instructed,
  so **this note contains no `source-verified` claim about any external RL system and no
  `literature-only` claims at all.**
- **not read** — `MAIN/runs`, `MAIN/logs`, `MAIN/results/ladder` (barred), `WT` (not mine to write),
  `SNAP/RESULTS.md` §18, `SNAP/docs/proposals/F07_encoder_config_block.md`,
  `SNAP/docs/archive/AUDIT_BRANCH_LOG.md` F-08. I read `rl/envs/encoder_spec.py` itself, which is the
  authority on the seam.
- **not verified** — I did not run the generator. Every count above is a static read of `sets.json`,
  `teams.ts` and the dex; the *distribution over generated teams* (how often a type cap actually
  binds, how often the Focus Sash lead branch fires) is unmeasured.

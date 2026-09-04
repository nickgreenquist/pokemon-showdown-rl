# gen4randombattle: the ability and item universes, their gen-4 mechanics, and what an encoder must carry

**Agent:** showdown-gen4-abilities-items (research agent, gen-4 design sweep)
**Date:** 2026-09-04
**Scope:** only what can *actually appear* in `gen4randombattle` as the vendored generator builds it. Not "all gen-4 abilities/items".

## Status legend

- **tree-verified** — checked against a file in the repo tree (SNAP: `rl/`, `scripts/`, `configs/`, `tests/`, `docs/`) or the vendored Showdown `data/` / `sim/`, i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk (poke-env source, Wang, H&L, MG, PSPPO, FP, Metamon).
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work index without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm; BARRED until the ladder run and any later fleet complete. Each such item says exactly what the check would be.

## Sources read (path, lines)

Vendored Showdown 0.11.11 @ 59da482 at `SD = /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown` (gitignored, not in SNAP):

| File | What I read |
|---|---|
| `SD/data/random-battles/gen4/sets.json` | whole file, parsed (295 species, 464 sets) |
| `SD/data/random-battles/gen4/teams.ts` | 1–80, 450–771 in full; grep over the rest |
| `SD/data/random-battles/gen5/teams.ts` | method-definition list (53, 98, 240, 491, 518, 556, 607, 685, 815, 845); `randomTeam` 845–984 |
| `SD/data/abilities.ts` | per-ability blocks for all 101 pool abilities (line ranges in the table below); verbatim: `airlock` 90–109, `gluttony` 1608–1619, `innerfocus` 2143–2157, `keeneye` 2250–2267, `leafguard` 2281–2300, `magicguard` 2455–2466, `sturdy` 4665–4683 |
| `SD/data/mods/gen4/abilities.ts` | 1–563 (whole file) |
| `SD/data/items.ts` | per-item blocks for all 40 pool items; verbatim: `insectplate` 3026–3045, `sitrusberry` 5740–5761, `souldew` 5879–5897, `toxicorb` 6338–6352 |
| `SD/data/mods/gen4/items.ts` | override index (58 entries); verbatim 33–56, 73–101, 147–168, 174–183, 192–195, 242–264 |
| `SD/data/mods/gen5/abilities.ts` | 32–50 (`keeneye`) |
| `SD/data/mods/gen6/items.ts` | 166–181 (`souldew`) |
| `SD/data/mods/gen6/pokedex.ts` | 180–200, `arceuswater` block |
| `SD/data/mods/gen7/abilities.ts` | 30–86 (`innerfocus`, `oblivious`, `owntempo`, `scrappy`, `slowstart`) |
| `SD/data/mods/gen4/pokedex.ts` | whole file (28 lines) |
| `SD/data/mods/gen4/conditions.ts` | 118–145 |
| `SD/data/mods/gen4/moves.ts` | `knockoff` block |
| `SD/data/conditions.ts` | 324–360 (`choicelock`), `tox` block |
| `SD/data/pokedex.ts` | `requiredItem` / `requiredItems` grep; `arceus` 9106–9125, `giratinaorigin` block |
| `SD/data/text/abilities.ts`, `SD/data/text/items.ts` | per-entry `shortDesc` with `gen4:`/`gen5:`/`gen6:`/`gen7:` overrides |
| `SD/sim/pokemon.ts` | 2161, 2242–2270 (`runImmunity`, Levitate), `setStatus`, `eatItem`, `useItem` |
| `SD/sim/battle.ts` | 1005, 1056–1057 (`alliesAndSelf` → `onAlly*`) |
| `SD/sim/dex-species.ts` | 241–252, 316–317 (`requiredItems` derivation) |

poke-env 0.15.0 at `PE = /opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env`:
`PE/battle/abstract_battle.py` 330–390, 577, 742–960, 1160–1175; `PE/battle/pokemon.py` 20–140, 229–260, 405, 557–585, 655–665, 725–735, 861–880; `PE/battle/effect.py` `from_showdown_message` + membership checks.

Repo (SNAP, main@2738025): `rl/envs/encoder_spec.py` 1–120 (the landed F-08 seam; read for cross-reference only).

Derivation scripts I wrote and ran (scratchpad, read-only elsewhere):
`scratchpad/research/ab_item_parse.py` (block parser over `abilities.ts` / `items.ts` / `mods/gen4/*` / `text/*`), outputs `_ab_facts.txt` (496 lines), `_it_facts.txt` (220 lines), `_ab_names.json`, `_item_names.json`.
**I did not reuse `_gen4_dexdump.json` or `_gen4pool_probe.out.json`** — everything below is re-derived from the raw data files.

---

## 1. The ability universe

### 1.1 How abilities are picked (tree-verified)

`RandomGen4Teams.randomSet` reads the *set's* ability list, never the species dex entry:

```
gen4/teams.ts:652    const abilities = set.abilities!;
gen4/teams.ts:660    ability = this.getAbility(new Set(types), moves, abilities, counter, teamDetails, species);
```

`getAbility` (`gen4/teams.ts:475–509`) returns `abilities[0]` when the set lists one; otherwise it culls via `shouldCullAbility` and samples. `shouldCullAbility` (`gen4/teams.ts:452–474`) only ever culls four:

```
case 'Chlorophyll': case 'Leaf Guard':  return !teamDetails.sun;
case 'Swift Swim':                      return !teamDetails.rain;
case 'Rock Head':                       return !counter.get('recoil');
case 'Skill Link':                      return !counter.get('skilllink');
```

and if *everything* is culled it falls back to sampling the full list (`:507 return this.sample(abilities)`). So **every ability listed anywhere in `sets.json` is reachable**. — tree-verified.

Two hard-codes sit above the cull (`gen4/teams.ts:486–487`): Dewgong takes Hydration iff it rolled Rain Dance else Thick Fat; Cloyster takes Skill Link iff it has a Skill Link move.

### 1.2 The universe: 101 distinct abilities over 464 sets

Derived from `SD/data/random-battles/gen4/sets.json` by `scratchpad/research/ab_item_parse.py`'s companion counter (295 species, 464 sets, 18 sets list two abilities, none lists three). — tree-verified.

Counts are **sets**, then **species**. This is not a battle-frequency distribution (see §6 open question O-1).

| # sets | # species | Ability | gen-4 effect (file:line) | Encoder-relevant quantity | Reveal |
|---|---|---|---|---|---|
| 40 | 23 | **Levitate** | no handlers; immunity lives in `sim/pokemon.ts:2161` (`isGrounded → null`), message at `sim/pokemon.ts:2262-2263` | **type immunity (Ground)** | `-immune \|[from] ability: Levitate` on a Ground move |
| 32 | 21 | **Pressure** | `mods/gen4/abilities.ts:346-353` — `onDeductPP` returns 1; base `onStart` `-ability` **is inherited** (only `onDeductPP` overridden) | PP drain on foe | `-ability\|POKEMON\|Pressure` on switch-in |
| 23 | 17 | **Multitype** | `mods/gen4/abilities.ts:281-285` — `onTakeItem: false`, `onSetAbility: false` | plate is untakeable; type = plate | none (Arceus forme in `switch` details already says the type) |
| 20 | 13 | **Intimidate** | `mods/gen4/abilities.ts:211-234` — `-1 atk` to foes; **does nothing if the foe has a Substitute**, or if U-turn just broke it | **boost (foe atk −1)** | `-ability\|POKEMON\|Intimidate\|boost` |
| 16 | 9 | **Chlorophyll** | `abilities.ts:502-512` `onModifySpe` ×2 in sun | **speed ×2** | none |
| 16 | 11 | **Swift Swim** | `abilities.ts:4800-4810` `onModifySpe` ×2 in rain | **speed ×2** | none |
| 13 | 6 | **Water Absorb** | `abilities.ts:5355-5368` `onTryHit`; heal 1/4 | **type immunity + heal** | `-immune \|[from] ability: Water Absorb` (+ `-heal`) |
| 12 | 4 | **Torrent** | `mods/gen4/abilities.ts:502-513` — **basePower ×1.5**, not Atk/SpA ×1.5 | **damage ×1.5 at ≤1/3 HP** | none |
| 12 | 7 | **Thick Fat** | `mods/gen4/abilities.ts:491-501` — `onSourceBasePower` ×0.5 for Fire/Ice (base power, not attacker stat) | **damage taken ×0.5** | none |
| 11 | 5 | **Clear Body** | `abilities.ts:513-532` `onTryBoost` | blocks foe stat drops | `-fail\|…\|unboost` only when a drop is attempted |
| 10 | 5 | **Own Tempo** | `abilities.ts:3134-3159`, minus `onTryBoost` (removed at `mods/gen7/abilities.ts:70-72`) → **confusion immunity only; does NOT block Intimidate in gen 4** | status (confusion) immunity | `-immune\|…\|confusion\|[from] ability: Own Tempo`, `-activate` |
| 10 | 7 | **Natural Cure** | `mods/gen4/abilities.ts:286-298`; comment: *"Because statused/unstatused pokemon are shown after every switch in gen 3-4, Natural Cure's curing is always known to both players"* | status cleared on switch-out | `-curestatus\|…\|[from] ability: Natural Cure\|[silent]` — sent, but poke-env's `-curestatus` branch drops the cause |
| 9 | 5 | **Synchronize** | `mods/gen4/abilities.ts:469-479` — reflects brn/psn/par (not slp/frz), tox→psn, ignores Toxic Spikes | status onto attacker | `-activate\|…\|ability: Synchronize` (base message) |
| 9 | 6 | **Rock Head** | `abilities.ts:3896-3907` `onDamage` | recoil suppressed | none |
| 8 | 5 | **Flash Fire** | `mods/gen4/abilities.ts:111-135` — immune to Fire **unless frozen**; boost is `onModifyDamagePhase1` ×1.5, and the gen-4 `condition` drops base's `-start`/`-end` messages | **type immunity + damage ×1.5 flag** | `-immune \|[from] ability: Flash Fire`; **no `-start ability: Flash Fire` in gen 4** |
| 8 | 6 | **Inner Focus** | `abilities.ts:2143-2157` minus `onTryBoost` (`mods/gen7/abilities.ts:34-38`) → **flinch immunity only; does NOT block Intimidate in gen 4** | flinch immunity | none |
| 8 | 4 | **Serene Grace** | `mods/gen4/abilities.ts:373-383` — doubles every `secondary.chance`, **excludes Chatter** | **secondary-effect probability ×2** | none |
| 7 | 4 | **Overgrow** | `mods/gen4/abilities.ts:307-318` — basePower ×1.5 | **damage ×1.5 at ≤1/3 HP** | none |
| 7 | 6 | **Swarm** | `mods/gen4/abilities.ts:457-468` — basePower ×1.5 | **damage ×1.5 at ≤1/3 HP** | none |
| 7 | 5 | **Guts** | `abilities.ts:1760-1771` — Atk ×1.5 when statused, ignores burn halving | **attack ×1.5 conditioned on own status** | none |
| 7 | 5 | **Keen Eye** | `abilities.ts:2250-2267` minus `onModifyMove` (`mods/gen5/abilities.ts:32-35`) → **accuracy-drop protection only; no evasion-ignore in gen 4** | boost protection (accuracy) | `-fail\|…\|unboost\|accuracy` |
| 7 | 3 | **Cute Charm** | `mods/gen4/abilities.ts:65-74` — 30% attract on contact | contact punisher (gender-gated) | `-start\|…\|Attract` from the volatile |
| 7 | 5 | **Insomnia** | `abilities.ts:2158-2182` (gen4 override is `rating` only) | **status immunity (sleep)** | `-immune`/`-activate \|ability: Insomnia` |
| 6 | 4 | **Blaze** | `mods/gen4/abilities.ts:25-36` — basePower ×1.5 | **damage ×1.5 at ≤1/3 HP** | none |
| 6 | 3 | **Sand Veil** | `mods/gen4/abilities.ts:362-372` — `onModifyAccuracy` ×0.8 in sand; **the base `onImmunity` (sandstorm chip immunity) is inherited** | **accuracy ×0.8; sand chip immunity** | none |
| 6 | 4 | **Technician** | `abilities.ts:4908-4922`; gen-4 desc: *"moves of 60 power or less have 1.5x power, except Struggle"* | **damage ×1.5 on BP≤60** | none |
| 5 | 5 | **Static** | `mods/gen4/abilities.ts:422-431` — 30% par on contact | contact punisher | `-status\|…\|par` |
| 5 | 3 | **Vital Spirit** | `abilities.ts:5307-5331` (gen4 override is `rating` only) | **status immunity (sleep)** | `-immune`/`-activate` |
| 5 | 3 | **Hydration** | `mods/gen4/abilities.ts:197-206` — cures on the **weather event**, not residual | status cleared in rain | `-activate\|…\|ability: Hydration` |
| 5 | 3 | **Hyper Cutter** | `abilities.ts:1930-1944` `onTryBoost` (atk only) | boost protection (atk) | `-fail\|…\|unboost\|Attack` |
| 5 | 3 | **Battle Armor** | `abilities.ts:345-351` `onCriticalHit` | **crit denial** | none |
| 5 | 3 | **Sturdy** | `mods/gen4/abilities.ts:452-456` — `onDamage: undefined`. **gen-4 Sturdy = OHKO-move immunity ONLY**; no survive-at-1-HP | OHKO-move immunity | `-immune \|[from] ability: Sturdy` (only vs an OHKO move); **no `-ability\|…\|Sturdy`** |
| 4 | 2 | **Tangled Feet** | `mods/gen4/abilities.ts:480-490` — `onModifyAccuracy` ×0.5 while confused | **accuracy ×0.5 conditioned on own confusion** | none |
| 4 | 3 | **Early Bird** | `abilities.ts:1116-1122` (flags only; sleep counter halved in the sleep condition) | **sleep-turn counter ÷2** | none |
| 4 | 4 | **Anticipation** | `abilities.ts:174-195` `onStart` | information (foe has SE/OHKO move) | `-ability\|POKEMON\|Anticipation` |
| 4 | 3 | **Snow Cloak** | `mods/gen4/abilities.ts:399-409` — `onModifyAccuracy` ×0.8 in hail; base `onImmunity` (hail chip) inherited | **accuracy ×0.8; hail chip immunity** | none |
| 3 | 3 | **Poison Point** | `mods/gen4/abilities.ts:336-345` — 30% psn on contact | contact punisher | `-status\|…\|psn` |
| 3 | 2 | **Dry Skin** | `abilities.ts:1088-1115` — Water immunity + heal 1/4; **Fire damage ×1.25**; +1/8 in rain, −1/8 in sun | **type immunity, damage taken ×1.25, per-turn heal/chip** | `-immune \|[from] ability: Dry Skin` |
| 3 | 3 | **Tinted Lens** | `abilities.ts:5026-5037` `onModifyDamage` ×2 on NVE | **damage ×2 when NVE** | none |
| 3 | 2 | **Liquid Ooze** | `mods/gen4/abilities.ts:250-260` — drain/leechseed damages instead of heals; Dream Eater exempt in gen 4 | inverts drain sign | `-damage` on the drainer |
| 3 | 2 | **Shell Armor** | `abilities.ts:4212-4218` `onCriticalHit` | **crit denial** | none |
| 3 | 2 | **Mold Breaker** | `abilities.ts:2679-2690` | ignores foe abilities | `-ability\|POKEMON\|Mold Breaker` on switch-in |
| 3 | 2 | **Volt Absorb** | `abilities.ts:5332-5345` | **type immunity + heal 1/4** | `-immune \|[from] ability: Volt Absorb` |
| 3 | 2 | **Leaf Guard** | `mods/gen4/abilities.ts:235-244` — blocks status in sun **but Rest still works**; the override drops the `-immune` message | status immunity in sun | **silent for status**; only Yawn triggers the inherited `-immune \|[from] ability: Leaf Guard` |
| 3 | 2 | **Sniper** | `abilities.ts:4348-4359` `onModifyDamage` ×1.5 on crit | **crit damage ×1.5** | none |
| 3 | 2 | **Trace** | `mods/gen4/abilities.ts:514-525` — `onUpdate` copies a random foe's ability (`flags: {notrace:1}`) | copies foe ability | `-ability\|…\|X\|[from] ability: Trace` (poke-env has a dedicated branch, `abstract_battle.py:781-793`) |
| 3 | 2 | **Sand Stream** | `abilities.ts:3987-3995` `onStart` | **weather setter (sand)** | `-weather\|Sandstorm\|[from] ability: Sand Stream` |
| 3 | 2 | **Speed Boost** | `mods/gen4/abilities.ts:410-414` (residual ordering only) | **speed +1/turn** | `-boost\|…\|spe\|1` |
| 3 | 2 | **Solid Rock** | `abilities.ts:4404-4415` — SE damage ×3/4 | **damage taken ×0.75 when SE** | none |
| 3 | 1 | **Air Lock** | `mods/gen4/abilities.ts:2-8` — `onSwitchIn: undefined`; `suppressWeather` inherited | **suppresses all weather effects** | **NONE in gen 4** — base's `-ability\|…\|Air Lock` is removed |
| 3 | 2 | **Magnet Pull** | `abilities.ts:2506-2523`; gen-4 desc: *"Prevents opposing Steel-type Pokemon from choosing to switch out."* | **trapping (Steel)** | none directly; the foe's `|request|` shows `trapped: true` |
| 2 | 1 | **Magic Guard** | `abilities.ts:2455-2466` + `mods/gen4/abilities.ts:261-269` (also blocks Toxic-Spikes poison) | **all indirect damage = 0** | **NONE** — the `-activate` in the base body names the *attacking* ability, not Magic Guard |
| 2 | 2 | **Sticky Hold** | `mods/gen4/abilities.ts:438-446` | item cannot be taken (incl. Knock Off) | `-activate\|…\|ability: Sticky Hold` |
| 2 | 2 | **Limber** | `abilities.ts:2358-2376` | **status immunity (par)** | `-immune`/`-activate` |
| 2 | 1 | **Scrappy** | `abilities.ts:4069-4088` minus `onTryBoost` (`mods/gen7/abilities.ts:78-80`) | **Normal/Fighting hit Ghost** | none |
| 2 | 1 | **Forewarn** | `mods/gen4/abilities.ts:154-178` — names the foe's highest-BP move (OHKO=160, Counter/Metal Burst/Mirror Coat=120, statusless-BP-0=80) | **information: one foe move id** | `-activate\|POKEMON\|ability: Forewarn\|MOVE` |
| 2 | 2 | **Immunity** | `abilities.ts:2086-2104` | **status immunity (psn/tox)** | `-immune`/`-activate` |
| 2 | 1 | **Huge Power** | `abilities.ts:1876-1885` `onModifyAtk` ×2 | **attack ×2** | none |
| 2 | 2 | **Gluttony** | `abilities.ts:1608-1619` — sets `abilityState.gluttony`; only a 1/4-threshold berry reads it | **none in this pool** (see §3.4) | none |
| 2 | 2 | **Flame Body** | `mods/gen4/abilities.ts:101-110` — 30% brn on contact | contact punisher | `-status\|…\|brn` |
| 2 | 2 | **Download** | `mods/gen4/abilities.ts:75-91` — compares foes' **live** Def vs SpD, skips foes behind a Substitute | **boost +1 atk or +1 spa** | `-boost` |
| 2 | 1 | **Poison Heal** | `abilities.ts:3321-3333` `onDamage` | **+1/8 per turn while poisoned, no chip** | none (the absent `-damage` is the tell) |
| 2 | 1 | **Plus** | `mods/gen4/abilities.ts:325-335` — ally-only | **none in singles** | none |
| 2 | 1 | **Minus** | `mods/gen4/abilities.ts:270-280` — ally-only | **none in singles** | none |
| 2 | 1 | **Rough Skin** | `mods/gen4/abilities.ts:354-361` — 1/8 max HP on contact | contact chip | `-damage` on the attacker |
| 2 | 1 | **Water Veil** | `abilities.ts:5421-5439` | **status immunity (brn)** | `-immune`/`-activate` |
| 2 | 1 | **Marvel Scale** | `abilities.ts:2524-2535` `onModifyDef` ×1.5 when statused | **defense ×1.5 conditioned on own status** | none |
| 2 | 1 | **Super Luck** | `abilities.ts:4695-4703` `onModifyCritRatio` +1 | **crit stage +1** | none |
| 2 | 1 | **Drizzle** | `abilities.ts:1068-1077` | **weather setter (rain)** | `-weather\|RainDance\|[from] ability: Drizzle` |
| 2 | 1 | **Drought** | `abilities.ts:1078-1087` | **weather setter (sun)** | `-weather\|SunnyDay\|[from] ability: Drought` |
| 2 | 1 | **Simple** | `mods/gen4/abilities.ts:389-398` — gen-4 form is `onModifyBoost` (**stages are READ doubled**), not gen-5's doubled application | **effective boost stages ×2** | none |
| 2 | 1 | **Pickup** | `mods/gen4/abilities.ts:319-324` — `onResidual: undefined`; desc *"No competitive use."* | **none** | none |
| 2 | 1 | **Run Away** | `abilities.ts:3940-3945` — desc *"No competitive use."* | **none** | none |
| 2 | 1 | **Flower Gift** | `mods/gen4/abilities.ts:136-149` — `onAllyModifyAtk` / `onAllyModifySpD` ×1.5 in sun; `onAlly*` fires for self (`sim/battle.ts:1056 alliesAndSelf()`) | **attack ×1.5, sp.def ×1.5 in sun** | Cherrim's forme change is `onStart`/`onWeatherChange` (inherited) |
| 2 | 1 | **Bad Dreams** | `mods/gen4/abilities.ts:20-24` | **1/8 chip on sleeping foes** | `-damage\|…\|[from] ability: Bad Dreams` |
| 1 | 1 | **Compound Eyes** | `mods/gen4/abilities.ts:56-64` — ×1.3 accuracy | **accuracy ×1.3** | none |
| 1 | 1 | **Arena Trap** | `abilities.ts:196-214` | **trapping (non-airborne)** | none directly; foe `|request|` `trapped: true` |
| 1 | 1 | **Cloud Nine** | `mods/gen4/abilities.ts:37-43` — `onSwitchIn: undefined` | **suppresses weather** | **NONE in gen 4** |
| 1 | 1 | **No Guard** | `abilities.ts:2960-2975` | **accuracy = 100% both ways** | none |
| 1 | 1 | **Skill Link** | `abilities.ts:4287-4300` | **multi-hit = max hits** | none |
| 1 | 1 | **Iron Fist** | `abilities.ts:2226-2238` — punch moves ×1.2, Sucker Punch excluded | **damage ×1.2 on punch moves** | none |
| 1 | 1 | **Filter** | `abilities.ts:1273-1284` — SE damage ×3/4 | **damage taken ×0.75 when SE** | none |
| 1 | 1 | **Shadow Tag** | `abilities.ts:4146-4163`; gen-4 desc: *"Prevents foes from choosing to switch unless they also have this Ability."* | **trapping (all)** | foe `|request|` `trapped: true` |
| 1 | 1 | **Quick Feet** | `abilities.ts:3738-3748` — Spe ×1.5 when statused, ignores paralysis drop | **speed ×1.5 conditioned on own status** | none |
| 1 | 1 | **Shield Dust** | `abilities.ts:4219-4228` `onModifySecondaries` | **secondary-effect immunity** | none |
| 1 | 1 | **Truant** | `mods/gen4/abilities.ts:526-539` | **acts every other turn** | `cant\|POKEMON\|ability: Truant` |
| 1 | 1 | **Wonder Guard** | `mods/gen4/abilities.ts:544-558` — only SE moves connect; **Fire Fang always hits through it in gen 4** (explicit `hint`) | **type-effectiveness gate** | `-immune \|[from] ability: Wonder Guard` |
| 1 | 1 | **Soundproof** | `abilities.ts:4426-4442`; gen-4 desc: *"immune to sound-based moves, including Heal Bell"* | **move-flag immunity** | `-immune \|[from] ability: Soundproof` |
| 1 | 1 | **Pure Power** | `abilities.ts:3598-3607` `onModifyAtk` ×2 | **attack ×2** | none |
| 1 | 1 | **White Smoke** | `abilities.ts:5465-5484` `onTryBoost` | blocks foe stat drops | `-fail\|…\|unboost` |
| 1 | 1 | **Shed Skin** | `mods/gen4/abilities.ts:384-388` (residual order only) | **33%/turn status cure** | `-activate\|…\|ability: Shed Skin` |
| 1 | 1 | **Suction Cups** | `abilities.ts:4684-4694` | immune to phazing | `-activate\|…\|ability: Suction Cups` |
| 1 | 1 | **Forecast** | `mods/gen4/abilities.ts:150-153` (`flags: {notrace:1}` only) | **type changes with weather** | `-formechange` on Castform |
| 1 | 1 | **Color Change** | `mods/gen4/abilities.ts:44-55` — `onDamagingHit` (gen-4 timing) | **type changes to the hit's type** | `-start\|…\|typechange\|TYPE\|[from] ability: Color Change` |
| 1 | 1 | **Unburden** | `abilities.ts:5227-5249` | **speed ×2 after item loss** | `-start` of the `unburden` volatile |
| 1 | 1 | **Aftermath** | `abilities.ts:78-89` — 1/4 max HP to a contact KOer | contact punisher on KO | `-damage\|…\|[from] ability: Aftermath` |
| 1 | 1 | **Snow Warning** | `abilities.ts:4377-4385` | **weather setter (hail)** | `-weather\|Hail\|[from] ability: Snow Warning` |
| 1 | 1 | **Motor Drive** | `abilities.ts:2725-2738` | **type immunity (Electric) + speed +1** | `-immune \|[from] ability: Motor Drive` |
| 1 | 1 | **Adaptability** | `abilities.ts:43-56` `onModifySTAB` → 2.0 | **STAB 1.5 → 2.0** | none |
| 1 | 1 | **Steadfast** | `abilities.ts:4541-4549` `onFlinch` | **speed +1 on flinch** | `-boost` |
| 1 | 1 | **Slow Start** | `abilities.ts:4301-4336` + `mods/gen7/abilities.ts:82+` (`onModifyAtk` keys off the *data* category) | **attack ÷2 and speed ÷2 for 5 turns** | `-start\|…\|ability: Slow Start`, `-end` |

**Totals: 101 abilities, 464 set-slots.** Species holding a given ability are in `_ab_facts.txt` / the counter output; the notable singletons are Wonder Guard = Shedinja, Truant = Slaking, Slow Start = Regigigas, Shadow Tag = Wobbuffet, Arena Trap = Dugtrio, Air Lock = Rayquaza, Cloud Nine = Golduck, Magic Guard = Clefable, Poison Heal = Breloom, Adaptability = Porygon-Z, Pure Power = Medicham, Huge Power = Azumarill, Forewarn = Jynx, Bad Dreams = Darkrai, Multitype = the 17 Arceus formes. — tree-verified.

### 1.3 Abilities the task named that are NOT in the gen-4 randbats pool

**Lightning Rod, Storm Drain, Effect Spore, Frisk, Normalize, Klutz, Stall, Oblivious, Magma Armor, Unaware, Reckless, Rivalry, Hustle, Solar Power, Rain Dish, Ice Body, Anger Point, Heatproof.** None appears in any `abilities` entry of `gen4/sets.json`. — tree-verified.

Two of those are worth recording anyway because the task asked to verify the mod:

- **Lightning Rod** (`mods/gen4/abilities.ts:245-249`): `onTryHit: undefined, rating: 0`. **Confirmed: gen-4 Lightning Rod is redirect-only (a doubles mechanic), with no Electric immunity and no Sp. Atk boost — in singles it is completely inert.** Same for **Storm Drain** (`mods/gen4/abilities.ts:447-451`, identical shape). Neither is in the pool, so this is moot for our encoder, but it is the correct gen-4 semantics if anyone quotes them. — tree-verified.
- **Hustle** (`mods/gen4/abilities.ts:188-196`): the gen-4 override supplies only the ×0.8 physical-accuracy penalty; the ×1.5 Atk lives in the inherited base. Not in the pool.

---

## 2. The item universe

### 2.1 How items are picked (tree-verified)

`RandomGen4Teams` **overrides both** `getPriorityItem` (`gen4/teams.ts:510-553`) and `getItem` (`gen4/teams.ts:554-625`), and it calls `super` **nowhere** (`grep -n "super\." gen4/teams.ts` → no matches). It does *not* override `randomTeam`, but gen 5's `randomTeam` (`gen5/teams.ts:845-984`) contains **no item literal at all** — its `teamDetails` block (`gen5/teams.ts:967-977`) keys only off abilities and moves. So **no gen-5 item literal can leak into a gen-4 team**; the gen-4 universe is closed by gen-4's own two methods plus `species.requiredItems` plus one post-hoc swap. — tree-verified.

Assignment order in `randomSet` (`gen4/teams.ts:663-671`): `getPriorityItem` first; if it returns `undefined`, `getItem`; then

```
gen4/teams.ts:669   if (item === 'Leftovers' && types.has('Poison')) {
gen4/teams.ts:670       item = 'Black Sludge';
```

### 2.2 The universe: exactly 40 items

Every string literal in lines 510–626 was extracted mechanically (`sed -n '510,626p' teams.ts | grep -o "'[^']*'"`), then filtered to item names; `requiredItems` were resolved through the dex inherit chain.

**A. Species-forced (`gen4/teams.ts:521`, `this.sample(species.requiredItems)`) — 17 items**

The 16 typed Arceus formes present in `gen4/sets.json` (`arceus{bug,dark,dragon,electric,fighting,fire,flying,ghost,grass,ground,ice,poison,psychic,rock,steel,water}`; **no Arceus-Fairy — Fairy does not exist in gen 4**) each force one Plate. Base `pokedex.ts:9138-9395` lists `requiredItems: ["<X> Plate", "<X>ium Z"]`, but **`mods/gen6/pokedex.ts:187-...` overrides every typed Arceus to a single-element `requiredItems: ["<X> Plate"]`, and gen 4 inherits through gen 6 — so no Z-crystal can be rolled.** (`sim/dex-species.ts:316-317` derives `requiredItems` from `requiredItem` when the plural is absent.) — tree-verified.

Plates: **Insect, Dread, Draco, Zap, Fist, Flame, Sky, Spooky, Meadow, Earth, Icicle, Toxic, Mind, Stone, Iron, Splash** (16).
Plus **Griseous Orb** — Giratina-Origin. Base `pokedex.ts` says `requiredItem: "Griseous Core"` (the Gen-9/LA name); `mods/gen8/pokedex.ts:40` overrides it to `requiredItem: "Griseous Orb"` and gen 4 inherits. — tree-verified.

Note: **base Arceus (Normal) has no `requiredItems`** (`pokedex.ts:9106-9125` lists none) and therefore falls through to the ordinary item logic. — tree-verified.

**B. Assigned by rule — 23 items**

| Item | Condition (file:line) |
|---|---|
| **Soul Dew** | `species.id === 'latias' \|\| 'latios'` — `gen4/teams.ts:522` |
| **Thick Club** | `marowak` — `:523` |
| **Light Ball** | `pikachu` — `:524` |
| **Focus Sash** | `shedinja \|\| smeargle` (`:525`); `delibird` + Counter (`:526`); Fast-Support lead with `defensiveStatTotal < 255`, no recovery, hazards-or-setup, and (no recoil or Rock Head) (`:600-603`) |
| **Custap Berry** | `wobbuffet` — `:527` |
| **Quick Powder** | `ditto`, 1-in-3 (`this.sample(['Choice Scarf','Quick Powder','Sitrus Berry'])`) — `:528` |
| **Choice Scarf** | ditto 1/3 (`:528`); Rampardos Fast Attacker (`:529`); Trick/Switcheroo/Healing Wish + 60 ≤ base Spe ≤ 108, role ≠ Wallbreaker, no priority (`:534-542`); Water Spout (`:544`); 4 special moves + scarfReqs + baseSpA ≥ 90 + coin flip (`:577-581`); 3 special + Fast Attacker + Explosion/Self-Destruct (`:582-584`); 4 physical + scarfReqs + (baseAtk ≥ 100 or Pure/Huge Power) + coin flip (`:586-593`) |
| **Sitrus Berry** | ditto 1/3 (`:528`); Belly Drum (`:543`); Unburden (`:550`) |
| **Choice Band** | Trick-family, physical-leaning, not scarf-eligible (`:541`); 4 physical moves, not Jirachi, no Fake Out/Rapid Spin (`:586-593`) |
| **Choice Specs** | Trick-family, special-leaning (`:541`); 4 special moves without scarf (`:577-581`); 3 special + U-turn (`:585`) |
| **Life Orb** | Honchkrow (`:530`); Yanmega with Speed Boost (`:533`); Magic Guard (`:545`); Fast Support with ≥3 attacks and no Rapid Spin/U-turn (`:606-611`); Fast Attacker / Setup Sweeper / Wallbreaker without Rapid Spin (`:621-623`) |
| **Leftovers** | Shuckle (`:531`); role Staller (`:551`); Protect or Substitute (`:599`); Fast Support fallback (`:606-611`); final default (`:624`) |
| **Toxic Orb** | ability Poison Heal **or** the set has Facade — `:532` |
| **Light Clay** | Light Screen **and** Reflect — `:546` |
| **Damp Rock** | Rest (no Sleep Talk) + Rain Dance + Hydration — `:547-549` |
| **Chesto Berry** | Rest without Sleep Talk, ability ∉ {Natural Cure, Shed Skin} — `:547-549` |
| **Black Glasses** | Pursuit + Sucker Punch + Dark counter (with the priority-mon guard) — `:573-576` |
| **Silk Scarf** | Normal-type with Fake Out and a Normal attack — `:595` |
| **Lustrous Orb** | `palkia` — `:596` |
| **Stick** | `farfetchd` — `:597` |
| **Lum Berry** | Outrage + setup, no Sleep Talk — `:598` |
| **Expert Belt** | Fast Attacker, no status move, no Dragon/Normal/Poison attack, no `noStab` Dragon/Normal/Poison move — `:620` |
| **Black Sludge** | post-hoc: any Poison-type that landed on Leftovers — `:669-671` |

**Total: 16 plates + Griseous Orb + 23 = 40 items.** — tree-verified.

### 2.3 Items the task named that CANNOT appear

Not reachable from any branch of `gen4/teams.ts`:
**Flame Orb, Heat Rock, Smooth Rock, Icy Rock, Iron Ball, Macho Brace, Shed Shell, Wide Lens, Scope Lens, Metronome, Quick Claw, Big Root, Zoom Lens, King's Rock, Razor Fang, DeepSeaTooth, Shell Bell, Wise Glasses, Muscle Band, Adamant Orb, Leppa Berry, Salac/Petaya/Liechi/Starf and every other pinch berry except Sitrus and Custap, and every type-boost item except Black Glasses and Silk Scarf** (no Charcoal, Mystic Water, Magnet, Miracle Seed, NeverMeltIce, Spell Tag, Sharp Beak, Poison Barb, Soft Sand, Twisted Spoon, Metal Coat, Hard Stone, Dragon Fang, Black Belt, Silver Powder). — tree-verified.

**Adamant Orb is a notable asymmetry:** `gen4/teams.ts:596` hard-codes Palkia → Lustrous Orb, but there is **no corresponding Dialga branch**, even though Dialga is in the pool (`sets.json`, level 70, roles Bulky Attacker / Bulky Support). Dialga therefore takes an ordinary item (Leftovers / Life Orb / Choice). — tree-verified.

**gen-5-only items are excluded by construction, as the task asked me to state:** Eviolite, Air Balloon, and every type Gem are gen-5 introductions; they are absent from the gen-4 dex, absent from `gen4/teams.ts`, and unreachable because gen 4 overrides gen 5's `getItem`/`getPriorityItem` wholesale. — tree-verified.

### 2.4 Item mechanics in gen-4 terms, encoder quantity, and reveal

| Item | gen-4 effect (file:line) | Encoder quantity | Reveal mechanism |
|---|---|---|---|
| **16 type Plates** | base `items.ts` `onBasePower` ×1.2 for the matching type (`chainModify([4915,4096])`, e.g. `items.ts:3031-3035`); **`mods/gen4/items.ts:192-195` sets `onTakeItem: true`, so plates ARE removable in gen 4** — except on Arceus, whose Multitype (`mods/gen4/abilities.ts:281-285`) sets `onTakeItem: false` | **damage ×1.2 on one type; also SETS the holder's type** | **none needed** — the Arceus forme is in the `switch`/`detailschange` details line, so the plate is deducible with certainty |
| **Griseous Orb** | `mods/gen4/items.ts:174-183` — Ghost/Dragon ×1.2 for species num 487; `onTakeItem: false`, `onSetAbility: false` | **damage ×1.2 on two types** | none needed — Giratina-Origin's forme implies it |
| **Soul Dew** | **gen 4 uses the gen-6 form**: `mods/gen6/items.ts:166-181` — `onModifySpA` ×1.5 **and** `onModifySpD` ×1.5 for Latias/Latios (num 380/381). The base `items.ts:5885-5893` ×1.2-on-Psychic/Dragon form is gen-7+ and does NOT apply | **sp.atk ×1.5 and sp.def ×1.5** | none — deducible from species |
| **Thick Club** | `mods/gen4/items.ts:440-447` — Atk ×2 for Cubone/Marowak | **attack ×2** | none — deducible from species |
| **Light Ball** | `mods/gen4/items.ts:265-274` — **gen-4 form is `onBasePower` doubling the move's power** for Pikachu, not the gen-5+ Atk/SpA doubling (`onModifyAtk`/`onModifySpA` explicitly `undefined`) | **damage ×2** | none — deducible from species |
| **Lustrous Orb** | `mods/gen4/items.ts:291-298` — Water/Dragon ×1.2 for Palkia | **damage ×1.2 on two types** | none — deducible from species |
| **Stick** | `mods/gen4/items.ts:423-430` — crit ratio +2 for Farfetch'd | **crit stage +2** | none — deducible from species |
| **Quick Powder** | `items.ts:5002-5017` — Spe ×2 for an untransformed Ditto | **speed ×2** | none; and it is only 1 of 3 Ditto rolls, so it is **not** deducible from species |
| **Choice Band / Specs / Scarf** | Atk / SpA / Spe ×1.5 (base `items.ts:959-1029`). **gen-4 lock semantics differ:** `mods/gen4/items.ts:33-56` sets `onStart: undefined, onModifyMove: undefined` and adds `onAfterMove(pokemon) { pokemon.addVolatile('choicelock'); }`; `mods/gen4/conditions.ts:123-129` re-defines `choicelock.onStart` to read `pokemon.lastMove.id` instead of `this.activeMove`. **So in gen 4 the lock is applied AFTER a move resolves, off `lastMove` — a Choice user is free to pick anything on the turn it switches in** | **attack/sp.atk/speed ×1.5 + a "locked onto move i" flag** | **NO protocol message at all.** For our own side the lock is visible as `disabled: true` on the other three moves in `|request|` (`conditions.ts:350-357 onDisableMove`). For the opponent it is pure inference |
| **Life Orb** | `mods/gen4/items.ts:242-264` — `onBasePower` adds the `lifeorb` volatile **only if the target has no Substitute**; `onModifyDamagePhase2` returns `damage * 1.3`; the volatile's `onAfterMoveSecondarySelf` deals `baseMaxhp/10`. **gen-4 quirk: no recoil when the hit went into a Substitute** | **damage ×1.3, 10% self-chip** | `-damage\|POKEMON\|HP\|[from] item: Life Orb` — poke-env captures this (`abstract_battle.py:350-351`) |
| **Leftovers** | `items.ts:3334-3347` — heal 1/16 each turn; `mods/gen4/items.ts:233-237` only re-orders the residual | **+1/16 per turn** | `-heal\|POKEMON\|HP\|[from] item: Leftovers` — poke-env captures (`abstract_battle.py:375-378`). Revealed at the end of the first full turn |
| **Black Sludge** | `items.ts:538-555` — +1/16 for a Poison type; in this pool it is **only** assigned to Poison types, so it is always a heal | **+1/16 per turn** | `-heal … [from] item: Black Sludge` |
| **Focus Sash** | `mods/gen4/items.ts:147-168` — **gen-4 Sash is a volatile applied `onTryHit` at full HP** that survives *all hits of one attack*, consumed in `onAfterMoveSecondary`. Different from the gen-5+ `onDamage` form | **survive-at-1-HP flag while at full HP** | `-enditem\|POKEMON\|Focus Sash` (`sim/pokemon.ts useItem`) — revealed only on use |
| **Sitrus Berry** | `items.ts:5740-5761` — eats at ≤1/2 max HP, heals **1/4 max HP** (the gen-4 value; gen 3's flat 30 HP is not used) | **conditional +1/4 heal at ≤1/2 HP** | `-enditem\|POKEMON\|Sitrus Berry\|[eat]` then `-heal` |
| **Chesto Berry** | `items.ts:877-897` — cures sleep | **sleep insurance** | `-enditem … [eat]` |
| **Lum Berry** | `items.ts:3533-3556` — cures any non-volatile status or confusion | **status insurance** | `-enditem … [eat]` |
| **Custap Berry** | `mods/gen4/items.ts:73-101` — gen-4 form is a queue insertion at `action.priority + 0.1` when HP ≤ 1/4 (or ≤ 1/2 with Gluttony), not the modern `onFractionalPriority` | **acts first in bracket once, at ≤1/4 HP** | `-activate\|POKEMON\|item: Custap Berry\|[consumed]` |
| **Toxic Orb** | `items.ts:6338-6352` — end-of-turn `trySetStatus('tox')`; `mods/gen4/items.ts:448-452` re-orders only | **self-badly-poison on turn 1** | `-status\|POKEMON\|tox\|[from] item: Toxic Orb` (`conditions.ts` tox `onStart`). **poke-env's `-status` branch reads only `event[2:4]` and DROPS the cause** (`abstract_battle.py:895-897`) — the item is not recorded |
| **Light Clay** | `items.ts:3440-3449` — **no handlers**; the screens read it in their duration callback. 8 turns instead of 5 | **screen duration 8 vs 5** | none — inferable only by counting turns |
| **Damp Rock** | `items.ts:1261-1269` — no handlers; Rain Dance 8 turns instead of 5 | **rain duration 8 vs 5** | none — inferable only by counting turns |
| **Expert Belt** | `items.ts:1897-1910` `onModifyDamage` ×1.2 on SE hits | **damage ×1.2 when SE** | **none, ever** |
| **Black Glasses** | `items.ts:523-537` — Dark ×1.2 | **damage ×1.2 on Dark** | **none, ever** |
| **Silk Scarf** | `items.ts:5710-5724` — Normal ×1.2 | **damage ×1.2 on Normal** | **none, ever** |

Cross-cutting reveal mechanics:
- **Knock Off** (`mods/gen4/moves.ts` `knockoff`): gen-4 Knock Off has **no damage boost** and only makes the item *unusable* (`target.itemKnockedOff = true`; explicit `hint`: *"In Gens 3-4, Knock Off only makes the target's item unusable; it cannot obtain a new item."*). It emits `-enditem\|POKEMON\|Item\|[from] move: Knock Off\|[of] SOURCE`, which poke-env turns into `item = None` (`abstract_battle.py:934-936`, `pokemon.py:405`). **Sticky Hold blocks it in gen 4** (`mods/gen4/abilities.ts:438-446` explicitly names `knockoff`). — tree-verified.
- **Trick / Switcheroo**: `-activate\|POKEMON\|move: Trick\|[of] OTHER`; poke-env swaps `_item` on both mons (`abstract_battle.py:889-892`). This is the *only* way a Choice item is revealed by the protocol. — tree-verified/source-verified.
- **Frisk is not in the pool**, so the `-item … [from] ability: Frisk` path (which poke-env does handle, `abstract_battle.py:949-960`) never fires in gen4randombattle. — tree-verified.

---

## 3. Reveal model — what an encoder can and cannot know

### 3.1 Abilities that announce themselves (tree-verified)

**Announce via `-ability` (poke-env sets `mon.ability`, `abstract_battle.py:770-796`):** Anticipation, Intimidate, Mold Breaker, Pressure. Four, and they are the only four in gen 4 — **base's `-ability` announcements for Air Lock, Cloud Nine, and Sturdy are removed by the gen-4 mod** (`onSwitchIn: undefined` at `mods/gen4/abilities.ts:2-8` and `:37-43`; `onDamage: undefined` at `:452-456`).

**Announce via `-immune … [from] ability: X` (poke-env sets `mon.ability`, `abstract_battle.py:1162-1168`):** Levitate, Flash Fire, Volt Absorb, Water Absorb, Motor Drive, Dry Skin, Wonder Guard, Soundproof, Insomnia, Vital Spirit, Immunity, Limber, Water Veil, Own Tempo, Sturdy (OHKO moves only), Leaf Guard (**Yawn only** in gen 4 — the status path is silent).

**Announce via `-activate … ability: X` — poke-env records an `Effect`, but does NOT set `mon.ability`** (`abstract_battle.py:827-893`; the generic tail at `:893` calls `start_effect(effect)`): Forewarn, Hydration, Shed Skin, Sticky Hold, Suction Cups, Synchronize, plus the `-activate` half of Insomnia/Vital Spirit/Immunity/Limber/Water Veil/Own Tempo. `Effect` has members for all of these (`PE/battle/effect.py`); it has **no `MAGIC_GUARD` and no `TRUANT`**, but neither reaches `-activate` anyway, and unknown effects degrade to `Effect.UNKNOWN` with a logged warning, never a crash (`effect.py from_showdown_message`). — source-verified.

**Announce indirectly:** Static / Flame Body / Poison Point (a `-status` on the attacker after a contact move), Rough Skin / Aftermath / Bad Dreams (`-damage … [from] ability: X`), Trace (`-ability … [from] ability: Trace`, with a dedicated poke-env branch), Download / Speed Boost / Steadfast (`-boost`), Color Change / Forecast (`-start typechange` / `-formechange`), Truant (`cant\|…\|ability: Truant` — poke-env's `cant` branch at `:742-744` calls `cant_move()` and **drops the reason**), Slow Start (`-start ability: Slow Start`), Natural Cure (`-curestatus … [from] ability: Natural Cure [silent]` — cause dropped by poke-env), Cute Charm (the `attract` volatile), Clear Body / White Smoke / Hyper Cutter / Keen Eye (a `-fail … unboost` when a drop is attempted), the weather setters (`-weather … [from] ability: X`).

### 3.2 Abilities that are NEVER announced in gen 4 (tree-verified)

**Air Lock, Cloud Nine, Magic Guard, Chlorophyll, Swift Swim, Sand Veil, Snow Cloak, Tangled Feet, Compound Eyes, No Guard, Thick Fat, Filter, Solid Rock, Technician, Tinted Lens, Iron Fist, Adaptability, Sniper, Super Luck, Blaze, Torrent, Overgrow, Swarm, Guts, Quick Feet, Marvel Scale, Simple, Skill Link, Serene Grace, Shield Dust, Rock Head, Battle Armor, Shell Armor, Huge Power, Pure Power, Poison Heal, Scrappy, Early Bird, Inner Focus, Arena Trap, Shadow Tag, Magnet Pull, Flower Gift, Gluttony, Pickup, Run Away, Plus, Minus, Unburden, Multitype, Liquid Ooze.**

That is ~51 of 101 — **roughly half of all gen-4 abilities are silent**, and they include some of the highest-leverage ones (the trapping trio, Magic Guard, the weather-suppressors, every damage multiplier). This is the single largest new hidden-information surface gen 4 adds. — tree-verified.

### 3.3 Item reveal summary (tree-verified)

- **Always self-reveals within a turn or two of relevance:** Life Orb (`-damage`), Leftovers / Black Sludge (`-heal`), Toxic Orb (`-status`, cause dropped by poke-env), every berry (`-enditem [eat]`), Focus Sash (`-enditem`), Custap Berry (`-activate`).
- **Never self-reveals:** the three Choice items, Expert Belt, Black Glasses, Silk Scarf, Light Clay, Damp Rock, Quick Powder, and every species-locked item (plates, Griseous Orb, Soul Dew, Thick Club, Light Ball, Lustrous Orb, Stick).
- **Deducible with certainty from the species/forme line alone:** the 16 plates (Arceus formes), Griseous Orb (Giratina-Origin), Soul Dew (Latias/Latios), Thick Club (Marowak), Light Ball (Pikachu), Lustrous Orb (Palkia), Stick (Farfetch'd), and Leftovers-on-Shuckle. **8 of the 40 items carry zero information beyond the species.**
- **The interesting inference problem is exactly:** did that Pokémon bring a Choice item, Life Orb, Leftovers, Expert Belt, or Focus Sash? — and the first is invisible until it repeats a move or gets Tricked.

### 3.4 Interactions that are dead letters in this pool

- **Gluttony is a no-op.** `abilities.ts:1608-1619` only sets `abilityState.gluttony`; the only pool item that reads it is Custap Berry (`mods/gen4/items.ts:77`), and Custap is Wobbuffet-only (which has Shadow Tag). Sitrus already fires at ≤1/2 regardless (`items.ts:5748-5750`). Gluttony's two carriers are Linoone and Shuckle; Shuckle is hard-coded to Leftovers. — tree-verified.
- **Plus and Minus are inert in singles** — both gen-4 overrides loop `pokemon.allies()` for the partner ability (`mods/gen4/abilities.ts:270-280`, `:325-335`). — tree-verified.
- **Flower Gift is NOT inert in singles**: `onAlly*` handlers fire for the Pokémon itself (`sim/battle.ts:1056 for (const allyActive of target.alliesAndSelf())`), so Cherrim gets Atk ×1.5 and SpD ×1.5 in sun. — tree-verified.
- **Pickup and Run Away have no mechanical effect** (both carried only by Pachirisu; gen-4 Pickup has its residual explicitly removed).

---

## 4. Proposed feature-class taxonomy

The goal is a small multi-label class vector that sits **alongside** a raw ability-id embedding, so the network gets generalisation across the long tail (one Filter, one Iron Fist, one Skill Link) without waiting for those ids to be visited enough times.

**12 ability classes** (multi-label — an ability can carry several; e.g. Dry Skin is in 4):

| # | Class | Members in the pool (count) |
|---|---|---|
| A1 | **Type / move-class immunity** | Levitate, Flash Fire, Volt Absorb, Water Absorb, Motor Drive, Dry Skin, Wonder Guard, Soundproof (8) |
| A2 | **Offensive damage multiplier** | Adaptability, Technician, Tinted Lens, Iron Fist, Sniper, Super Luck, Huge Power, Pure Power, Guts, Blaze, Torrent, Overgrow, Swarm, Flower Gift, Skill Link, Serene Grace (16) |
| A3 | **Defensive damage multiplier / crit denial** | Thick Fat, Filter, Solid Rock, Marvel Scale, Battle Armor, Shell Armor, Dry Skin (Fire ×1.25, negative), Flower Gift (7) |
| A4 | **Speed modifier** | Chlorophyll, Swift Swim, Speed Boost, Quick Feet, Unburden, Slow Start, Steadfast, Motor Drive (8) |
| A5 | **Status immunity / self-cure** | Insomnia, Vital Spirit, Immunity, Limber, Water Veil, Own Tempo, Inner Focus, Shield Dust, Leaf Guard, Early Bird, Natural Cure, Shed Skin, Hydration, Magic Guard (Toxic Spikes), Synchronize (15) |
| A6 | **Stat-drop protection** | Clear Body, White Smoke, Hyper Cutter, Keen Eye (4) |
| A7 | **Weather setter** | Drizzle, Drought, Sand Stream, Snow Warning (4) |
| A8 | **Weather user / suppressor** | Chlorophyll, Swift Swim, Sand Veil, Snow Cloak, Leaf Guard, Dry Skin, Hydration, Flower Gift, Forecast, Air Lock, Cloud Nine (11) |
| A9 | **Trapping** | Arena Trap, Shadow Tag, Magnet Pull (3) |
| A10 | **Contact punisher** | Static, Flame Body, Poison Point, Rough Skin, Aftermath, Cute Charm (6) |
| A11 | **Per-turn recovery / chip** | Poison Heal, Magic Guard, Dry Skin, Bad Dreams, Liquid Ooze (5) |
| A12 | **Information / structural** | Trace, Anticipation, Forewarn, Download, Intimidate, Mold Breaker, Pressure, Truant, Sturdy, Multitype, Scrappy, Suction Cups, Sticky Hold, Color Change, Rock Head, Simple, No Guard, Compound Eyes, Hustle-shaped accuracy (Sand Veil, Snow Cloak, Tangled Feet) (~21) |

**Abilities with NO encoder-relevant effect in gen-4 singles — a raw id embedding is the only sensible carrier (4):** **Pickup, Run Away, Plus, Minus.** Gluttony is a fifth in practice (a no-op given this pool's item set, §3.4) but is mechanically live in the abstract, so I would keep it out of the "dead" list and let the id embedding learn that it does nothing.

**5 item classes** (an item gets exactly one primary class plus optional flags):

| # | Class | Members (count) |
|---|---|---|
| I1 | **Damage multiplier** | 16 plates, Griseous Orb, Lustrous Orb, Black Glasses, Silk Scarf, Expert Belt, Life Orb, Light Ball (23) |
| I2 | **Stat multiplier** | Choice Band, Choice Specs, Choice Scarf, Soul Dew, Thick Club, Quick Powder (6) |
| I3 | **Sustain / per-turn** | Leftovers, Black Sludge (2) |
| I4 | **One-shot consumable** | Sitrus Berry, Chesto Berry, Lum Berry, Custap Berry, Focus Sash (5) |
| I5 | **Field / duration / self-status** | Light Clay, Damp Rock, Toxic Orb, Stick (crit stage) (4) |

Plus two orthogonal boolean flags an encoder should carry per item: **`is_choice`** (locks move selection — Band/Specs/Scarf) and **`is_consumed`** (already spent, so the slot is empty).

**Items with no encoder-relevant effect: none.** All 40 modify a quantity. But **8 carry no *information*** (§3.3), so an encoder that already one-hots species gets nothing new from them; and **Light Clay and Damp Rock are unobservable** — their effect (8 vs 5 turns) is only visible as a discrepancy at turn 6, so their bit will be near-uninformative from the opponent's side.

---

## 5. gen-1 encoder assumptions this breaks

The seam doc (`rl/envs/encoder_spec.py:53-56`, main@2738025) already names the shape of the problem:

> `items and abilities: absent in gen 1, so there is no block for them. New per-mon fields are a MON_DIM change, i.e. an OBS_DIM change — every existing checkpoint is invalidated (landmine).`

What this note adds on top:

1. **"A Pokémon's identity is (species, moves, HP, status)" is now false.** Two identical Gengars differ by ability (Levitate is its only one, so not Gengar — but two identical Tentacruels differ by Clear Body vs Liquid Ooze, `sets.json`; two Kingdras by Sniper vs Swift Swim; two Porygon2s by Trace vs Download). **18 of 464 sets are ability-ambiguous even given the set.** The gen-1 encoder has no slot that can express this.
2. **"Type effectiveness is a pure function of (move type, defender types)" is false.** Levitate (40 set-slots, the most common ability in the format), Flash Fire, Volt Absorb, Water Absorb, Motor Drive, Dry Skin, Wonder Guard, and Soundproof all rewrite it, and **none of them is announced until it triggers**. Our gen-1 encoder carries a single scalar type-matchup slot (`EncoderSpec` docstring, `[+30] matchup`); in gen 4 that scalar is conditional on an unknown.
3. **"Speed order is a function of base stats, boosts, and paralysis" is false.** Choice Scarf ×1.5 (never announced), Chlorophyll/Swift Swim ×2 (never announced), Quick Feet ×1.5, Unburden ×2, Speed Boost +1/turn, Slow Start ÷2, Quick Powder ×2, Custap Berry's one-shot priority insert, and Stall's −0.1 fractional priority all move it. Speed inference becomes a first-class latent.
4. **"Damage is stat × BP × type × crit" is false** in a way that matters for the value head: fourteen ability multipliers and six item multipliers stack, and **gen 4 applies the pinch boosts (Blaze/Torrent/Overgrow/Swarm) and Thick Fat at the BASE POWER step, not the attack-stat step** (`mods/gen4/abilities.ts:25-36`, `:491-501`). Anything we port from a gen-5+ damage model gets the rounding wrong.
5. **"Switching out clears nothing but volatiles" is false**: Natural Cure clears status on switch (10 set-slots), and the gen-4 mod comment says the cure is *always* visible to both players.
6. **"You may always switch" is false**: Arena Trap, Shadow Tag, Magnet Pull. Our gen-1 action mask has never had to encode `trapped` from an *opponent ability*. (poke-env surfaces this as `battle.trapped`, driven by the `|request|`.)
7. **Weather becomes a global state with four ability setters, eleven ability consumers, and two suppressors** — and the suppressors (Air Lock, Cloud Nine) are silent in gen 4, so "is weather actually doing anything?" is itself hidden state.
8. **The `-activate` protocol class becomes load-bearing.** In gen 1 we never needed it for identity. In gen 4 it is how six abilities reveal themselves, and **poke-env does not write those into `pokemon.ability`** — only into `pokemon.effects`. Our encoder must read `effects` for ability identity, or we lose those reveals.
9. **Item slot needs three states, not two**: unknown / known-and-held / known-and-consumed. poke-env models this (`GenData.UNKNOWN_ITEM`, `end_item` → `None`), and the gen-1 encoder has no field for any of them.
10. **A choice-lock flag is a legal-action fact, not a feature.** For our own side it comes free (`disabled` in `|request|`, which poke-env already respects in `available_moves`); for the opponent it must be inferred, and the gen-4 lock timing (after the move, off `lastMove`) means the opponent is *unlocked* on the turn it switches in.

---

## 6. Open questions for the maintainer

- **O-1 — Do we need empirical ability/item frequencies, or is the reachability set enough?** The counts in §1.2 are *set-slot* counts, not battle frequencies; the true distribution depends on `getPokemonPool`, the type/weakness limits in `gen5/teams.ts:882-925`, and the level-100 cap. Getting real frequencies means running the team generator ~10⁵ times. **Recommendation: skip it for the encoder design** — the encoder needs the *universe* (which is exact and small), not the marginal. **Losing argument:** frequencies would tell us whether an id embedding is even trainable for the 40-odd singleton abilities, and would let us size a "rare ability" bucket instead of 101 rows.
- **O-2 — Ability as one 101-row embedding, or 12 class bits, or both?** **Recommendation: both** — 12 class bits (dense, always meaningful, generalises to the singletons) concatenated with a small id embedding. **Losing argument:** the class bits are hand-designed and therefore a place for our priors to be wrong; a pure id embedding at ~101 rows is not obviously too many given 100M-step budgets, and it can't encode a mistake we made in the taxonomy.
- **O-3 — How do we represent an *unknown* opponent ability?** Roughly half of gen-4 abilities never announce (§3.2), so for many opponent mons the ability is never observed at all. Options: (a) an `UNKNOWN` id row; (b) a prior distribution over the species' legal abilities from a gen-4 randbats prior file, analogous to `rl/envs/randbats_prior.py`; (c) both, with the prior collapsing to a one-hot on reveal. **Recommendation: (c).** `sets.json` gives us the exact legal ability list per species, and 277 of 295 species have a *single* ability across all their sets — so for 94% of the pool "unknown" is actually fully determined by the species. **Losing argument:** (c) is a second table to keep in sync with the vendored generator, and it silently goes wrong if the vendored Showdown is ever bumped.
- **O-4 — Do we carry Light Clay / Damp Rock at all?** Their only effect is a duration the protocol never states. **Recommendation: carry them in the item id space (they're in the universe) but expect zero signal.** **Losing argument:** two dead rows in a 40-row table is free; arguing about it costs more than it saves.
- **O-5 — Is the "silent half" of the ability space a reason to prefer a recurrent/history encoder over the current per-turn snapshot?** Gen 1's hidden information was essentially "which moves does the opponent have"; gen 4 adds "which ability, which item, and is it Choice-locked", all of which are inferred from *sequences* (it repeated a move; it took no sand damage; it outsped something it shouldn't). **Recommendation: flag it as a Chapter-6 architecture question, not a Chapter-5 encoder question** — the encoder's job is to expose the observations; the inference is the network's. **Losing argument:** if we're changing OBS_DIM anyway (which invalidates every checkpoint), this is the cheapest moment we will ever get to also change the temporal shape.
- **O-6 — Should the encoder read ability identity out of `pokemon.effects` to recover the six `-activate`-only abilities?** poke-env does not write them to `.ability` (§3.1). **Recommendation: yes, a small post-processing step in our env layer, not a poke-env patch** — we pin poke-env 0.15.0 and a fork is a maintenance tail. **Losing argument:** the mapping `Effect.SYNCHRONIZE → ability "synchronize"` is exactly the kind of hand table that rots; upstreaming it is the clean fix.

---

## 7. Cross-references for the other docs

- → **`mechanics_delta.md`**: the gen-4 basePower-vs-stat ordering for Blaze/Torrent/Overgrow/Swarm and Thick Fat (§1.2); gen-4 Sturdy = OHKO-only; gen-4 Knock Off has no damage boost and only disables the item; gen-4 Intimidate whiffs through a Substitute; Life Orb takes no recoil into a Substitute; gen-4 Simple reads stages doubled rather than doubling the application; Inner Focus / Own Tempo / Scrappy do NOT block Intimidate in gen 4; Keen Eye does not ignore evasion in gen 4; Custap Berry is a queue insert, not fractional priority; Stall is −0.1 fractional priority and gen-3/4 Protect's success chance floors at 1/8 (`mods/gen4/conditions.ts:135-141`).
- → **`pokeenv_gen4_survey.md`**: poke-env sets `.ability` from `-ability` and `-immune`, but **not** from `-activate`, `-curestatus`, or `cant`; it sets `.item` from `-item` (Frisk), `-enditem`, `-damage [from] item:`, `-heal [from] item:`, and `-activate move: Trick`, but **not** from `-status [from] item: Toxic Orb`. `Effect` lacks `MAGIC_GUARD` and `TRUANT` but degrades safely.
- → **`encoder_requirements.md`**: the exact vocabularies are **101 abilities** and **40 items**; the item slot needs three states; a `choice_locked` flag; 12 ability class bits + 5 item class bits + 2 item flags; 277/295 species have a unique ability so a species→ability prior collapses most of the uncertainty.
- → **`anchors_and_eval.md`**: `SimpleHeuristicsPlayer` in gen 4 will be reasoning about a board where ~half the abilities are hidden and Choice items are never announced; any "most-damage-typed" anchor needs a decision about whether it assumes the opponent's ability is unknown (Levitate at 40 set-slots will punish a naive damage calc badly).
- → **`open_questions.md`**: O-1 through O-6 above.

---

## 8. Unread / unverified

- **I did not run the team generator.** No frequency data, no sampled teams; §2.2 is a static reachability analysis of `getPriorityItem`/`getItem`, not an empirical distribution. — *needs-live-verification*: build the vendored TS and call `RandomGen4Teams.randomTeam()` ~10⁵ times, tallying `(ability, item)` pairs. Barred while the ladder run is live.
- **I did not confirm any of this against a live gen4randombattle log.** Every protocol-message claim is read off the sim source, not off a wire capture. — *needs-live-verification*: run one gen4randombattle against the local server with `--no-security` and diff the observed `-ability` / `-activate` / `-enditem` / `-status` lines against §3.
- **I did not read `SD/config/formats.ts`** to confirm `gen4randombattle` is registered and un-modified in the vendored copy, nor `SD/data/mods/gen4/formats-data.ts` for tier gating. The presence of Arceus/Kyogre/Groudon/Darkrai/Giratina in `sets.json` implies the format is Ubers-inclusive, but I did not verify that the *format* uses `gen4/teams.ts` rather than `gen4pt/`. — *needs-live-verification / one more read*.
- **I did not verify the `mods/gen4pt/` branch at all.** If `gen4randombattle` resolves to the `gen4pt` mod rather than `gen4`, some of the item/ability overrides above could differ. `mods/gen4pt/` exists in the mods listing; I read none of it.
- **`_gen4_dexdump.json` and `_gen4pool_probe.out.json`** (earlier agents' dumps) — I deliberately did **not** use them, so nothing here depends on `gen4dump.js` / `_gen4pool_probe.js` being correct.
- **Ability *ratings*** in the data files are Showdown's own competitive heuristics; I quote none of them as evidence.
- **Contact-move flags:** I asserted "contact punisher" from `move.flags['contact']` in each ability body but did **not** enumerate which gen-4 moves in the randbats movepool carry the contact flag. That enumeration belongs to the moves note, not this one.
- **PP/priority column of the task brief:** I found exactly one PP effect (Pressure) and two priority effects (Stall — not in the pool; Custap Berry) in this pool. I did not audit `mods/gen4/moves.ts` for move-side priority, which is out of my source family.
- **No `rl/` code was read beyond `encoder_spec.py:1-120`**, and nothing in the repo was modified.

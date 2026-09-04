# gen4 battle mechanics as implemented in the vendored Showdown

**Agent:** showdown-gen4-mechanics (gen4 design sweep, stage 1)
**Date:** 2026-09-04
**Scope:** gen1 → gen4 rules delta, restricted to what an encoder or a policy must
represent. Abilities and items are NAMED where they hook a mechanic and otherwise
left to the abilities/items agent. Sets/teams generation is left to the randbats
agent except where the move pool bounds what mechanics can actually occur.

## Status legend

- **tree-verified** — checked against a file in the repo tree (SNAP) or the
  vendored Showdown `data/` / `sim/` / `dist/`, i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk
  (installed poke-env source).
- **literature-only** — from memory or a secondary write-up, not re-checked.
- **needs-live-verification** — only a running server/battle can confirm; BARRED
  until the ladder run and any later fleet complete.

## Sources read (path — lines/ranges)

Vendored Showdown, `SD = /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown`
(pokemon-showdown 0.11.11 @ 59da482; `data/` and `dist/data/` both dated Jul 29 / Sep 4,
`dist` verified consistent with `data` on spot checks):

| file | lines read |
|---|---|
| `SD/data/mods/gen4/scripts.ts` | 1–222 (whole file) |
| `SD/data/mods/gen4/conditions.ts` | 1–175 (whole file) |
| `SD/data/mods/gen4/rulesets.ts` | 1–33 (whole file) |
| `SD/data/mods/gen4/pokedex.ts` | 1–27 (whole file) |
| `SD/data/mods/gen4/moves.ts` | move index (all top-level keys); bodies 36–48, 103–140, 268–335, 381–450, 524–545, 600–700, 706–800, 817–845, 892–930, 966–1100, 1103–1180, 1204–1280, 1280–1330, 1346–1420, 1419–1470, 1492–1560 |
| `SD/data/mods/gen4/abilities.ts` | top-level key index only |
| `SD/data/mods/gen4/items.ts` | top-level key index only |
| `SD/data/mods/gen5/scripts.ts` | 1–4 (whole file) |
| `SD/data/mods/gen5/conditions.ts` | 1–56 (whole file) |
| `SD/data/mods/gen5/moves.ts` | key index; bodies 76–92, 178–190, 254–262, 382–395, 485–502, 546–558, 758–800, 850–890 |
| `SD/data/mods/gen5/typechart.ts` | 1–97 (whole file) |
| `SD/data/mods/gen6/typechart.ts`, `gen6/conditions.ts`, `gen8/typechart.ts` | whole files |
| `SD/data/mods/gen3/scripts.ts` | 1–30 |
| `SD/data/mods/gen1/scripts.ts` | 340–350, 420, 426–470, 585–740, 748–985 |
| `SD/data/mods/gen1/conditions.ts` | 1–240 |
| `SD/data/mods/gen1/moves.ts` | 69–82, 400–460, 930–945; `substitute`, `struggle`, `counter`, `focusenergy` blocks |
| `SD/data/mods/gen1/typechart.ts` | 1–137 (whole file) |
| `SD/data/mods/gen1/rulesets.ts` | 1–60 |
| `SD/data/typechart.ts` | rows bug/dark/electric/fire/flying/ghost/grass/ice/normal/poison/psychic/steel |
| `SD/data/conditions.ts` | `slp`, `brn`, `psn`, `tox`, `confusion`, `stall`, `lockedmove`, `twoturnmove`, `mustrecharge`, `partiallytrapped`, `raindance`, `sunnyday`, `sandstorm`, `hail` blocks |
| `SD/data/moves.ts` | `reflect`, `spikes`, `toxicspikes`, `substitute`, `counter`, `yawn`, `roost`, `trickroom`, `gravity`, `rest`, `attract`, `focusenergy`, `safeguard`, `mist`, `luckychant`, `uproar`, `encore`, `taunt`, `disable`, `tailwind` blocks |
| `SD/data/rulesets.ts` | 19–27, 92–100, 788, 921–935, 957–980, 1060–1069, 1352–1400, 1451–1480 |
| `SD/data/items.ts` | 3440–3446 (`lightclay`) |
| `SD/sim/battle-actions.ts` | 690–750, 885–960, 1585–1830 |
| `SD/sim/battle.ts` | 404–476, 1830–1900, 2105–2125, 2380–2395 |
| `SD/sim/battle-queue.ts` | 165–200 |
| `SD/sim/pokemon.ts` | 560–630, 894–906, 1252–1274, 1620–1630, 1714–1726 |
| `SD/sim/dex.ts` | 260–300, 348–386 |
| `SD/sim/dex-moves.ts` | 223, 366, 486 |
| `SD/config/formats.ts` | 4082–4088, 4166–4172, 4213–4265, 4239–4244 |
| `SD/data/random-battles/gen4/teams.ts` | 1–60, 95–125, 627–700 |
| `SD/data/random-battles/gen4/sets.json` | parsed in full (counts only) |

Repo snapshot, `SNAP = .../scratchpad/main_snapshot` (main@2738025):
`SNAP/rl/envs/encoder_spec.py` 1–286 (whole file).

Installed poke-env 0.15.0, `PE = /opt/anaconda3/.../site-packages/poke_env`:
`PE/data/static/typechart/gen4typechart.json` (parsed), directory listings of
`PE/data/static/{typechart,moves}/`.

Helper scripts I wrote (scratch only, pure data parsing, `nice -n 19 node`):
- `.../research/tc_diff.js` — evaluates `SD/data/typechart.ts` + mod overrides and
  applies the inherit chain; produced the type-chart delta table below.
- `.../research/gen4_moves_merge.js` — same for moves, reading the **compiled**
  `SD/dist/data/**/moves.js` (the `.ts` sources carry in-body type annotations that
  `new Function` cannot eval; `dist` mtime Sep 4, spot-checked against the `.ts`,
  e.g. gen4 `thrash` basePower 90 / pp 20 in both).

I did **not** read: `SD/data/mods/gen2/*`, `gen3/moves.ts`, `SD/data/abilities.ts`
beyond `pressure`, `SD/data/items.ts` beyond `lightclay`, the gen4 learnsets, the
gen4 `formats-data.ts`, or any Wang/H&L/Metamon text (out of my source family).

---

## 0. The inherit chain — attribute each mechanic to the right file

**tree-verified.** `SD/data/mods/gen4/scripts.ts:2` is `inherit: 'gen5'`;
`gen5/scripts.ts:2` `inherit: 'gen6'`; `gen6:2` → gen7; `gen7:2` → gen8; `gen8/scripts.ts`
has no `inherit` (it is the last mod before base). So

> **a gen4 battle runs base `data/*.ts` overridden by gen8, then gen7, then gen6,
> then gen5, then gen4 — in that order.**

Practical consequences that bit me and will bite the downstream docs:

- **`gen5/moves.ts` and `gen5/conditions.ts` are live in gen4.** The partial-trapping
  chip divisor (16, not the base 8), the `stall` doubling counter, the Hidden Power
  variable-BP callback, the `charge`-flag move flag sets, `meanlook`/`block`
  `reflectable`, and `skullbash` 100 BP all come from gen5 and are *not* in
  `gen4/moves.ts`. Grepping only `mods/gen4/` gives a wrong answer.
- **`gen6/conditions.ts` is live in gen4**: burn residual is `baseMaxhp / 8`
  (`gen6/conditions.ts:4-6`), not the base `/16`.
- **`gen6/typechart.ts` and `gen5/typechart.ts` are live in gen4**: Steel resists
  Ghost and Dark (`gen5/typechart.ts:68-91`); Fairy is `isNonstandard: 'Future'`
  (`gen5/typechart.ts:93-96`).
- The gen1 mod sits at the *other* end (`gen1/scripts.ts:16` `inherit: 'gen2'`
  → gen3 → gen4 → …), i.e. gen1 inherits **through** gen4. Anything gen4 overrides
  and gen1 does not re-override is shared.
- **The physical/special-by-type rule lives in `gen3/scripts.ts`, not gen4.**
  `SD/data/mods/gen3/scripts.ts:4-14`:
  ```ts
  const specialTypes = ['Fire','Water','Grass','Ice','Electric','Dark','Psychic','Dragon'];
  ...
  newCategory = specialTypes.includes(this.data.Moves[i].type) ? 'Special' : 'Physical';
  ```
  It is an `init()` on the **gen3** mod, so it applies to gen3/2/1 and **not** to
  gen4. gen4 uses the per-move `category` field from base `data/moves.ts` via
  `Battle#getCategory` (`SD/sim/battle.ts:2384-2386`:
  `return this.dex.moves.get(move).category || 'Physical';`).

---

## 1. Damage formula and rounding

**tree-verified.** Base damage is computed once in base code
(`SD/sim/battle-actions.ts:1712-1717`):

```ts
// int(int(int(2 * L / 5 + 2) * A * P / D) / 50);
const baseDamage = tr(tr(tr(tr(2 * level / 5 + 2) * basePower * attack) / defense) / 50);
```

Then **gen4 replaces `modifyDamage` wholesale** (`SD/data/mods/gen4/scripts.ts:57-137`,
comment at :58 "DPP divides modifiers into several mathematically important stages").
The gen4 order is:

| step | gen4 (`mods/gen4/scripts.ts`) | base / gen5+ (`sim/battle-actions.ts:1724-1830`) |
|---|---|---|
| 1 | **burn halving** (physical, non-Guts), `modify(baseDamage, 0.5)` :65-67 | burn applied *late*, after type effectiveness, :1815-1820 |
| 2 | `ModifyDamagePhase1` — this is where **Reflect / Light Screen** hook :70 | screens hook the single `ModifyDamage` event |
| 3 | spread modifier :73-77 | same |
| 4 | `WeatherModifyDamage` :80 | same |
| 5 | `baseDamage += 2` :82 | **`+2` happens first**, :1731 |
| 6 | crit: `modify(baseDamage, move.critModifier \|\| 2)` :84-87 | `tr(baseDamage * (critModifier \|\| gen>=6 ? 1.5 : 2))` :1750-1752 |
| 7 | `ModifyDamagePhase2` then `Math.floor` :90 | — |
| 8 | randomizer :93 | randomizer :1755 |
| 9 | STAB ×1.5 :100-107 | STAB :1758-1793 |
| 10 | type effectiveness (`*=2` / `Math.floor(/2)` per stage) :109-125 | same :1795-1812 |
| 11 | `ModifyDamage` (Life Orb, Expert Belt, Tinted Lens, …) :130 | same :1823 |
| 12 | `if (!Math.floor(baseDamage)) return 1;` :132-134 | gen5-only min-1 at :1821 |

Randomizer (base, unchanged for gen4) `SD/sim/battle.ts:2388-2391`:
```ts
randomizer(baseDamage) { const tr = this.trunc; return tr(tr(baseDamage * (100 - this.random(16))) / 100); }
```
→ 16 equally likely rolls, 85 %…100 %.

**gen1** computes the whole thing in its own `getDamage`
(`SD/data/mods/gen1/scripts.ts:748-970`): screens are applied by **doubling the
defence stat inline** (:869-873), crit **doubles `level`** and ignores boosts *and*
screens (:878-884), stats ≥ 256 are divided by 4 and truncated to 8 bits (:897-910)
— the rollover bug — damage is clamped to `[0, 997]` before `+2` (:925), STAB is
`damage += Math.floor(damage/2)` (:929), effectiveness is applied **per target type
in sequence** with `*20/10` and `*5/10` (:932-947), and the random factor is
`damage * random(217,256) / 255` (:965-969), i.e. 39 rolls not 16.

**Encoder impact:** none of these constants belong in the observation, but a
value function trained on gen1 has internalised "crit ≈ 2× and ignores my
defence drops"; in gen4 the crit multiplier is still 2 (`critModifier || 2`) but the
level-doubling is gone, screens are a side condition that a crit *bypasses*
(`mods/gen4/moves.ts:1108` `if (!target.getMoveHitData(move).crit && !move.infiltrates)`),
and burn now halves *before* the `+2`.

---

## 2. Critical hits

| | gen1 | gen4 |
|---|---|---|
| basis | **base Speed of the species** | fixed stage table |
| formula | `critChance = floor(baseStats.spe / 2)`; ×2 capped 255; ÷2 for normal ratio; ×4 capped 255 for high-crit; then `randomChance(critChance, 256)` — `mods/gen1/scripts.ts:816-843` | `critRatio` clamped 0–5, `critMult = [0,16,8,4,3,2]`, `randomChance(1, critMult[critRatio])` — `sim/battle-actions.ts:1622-1644` |
| default rate | `floor(floor(baseSpe/2)*2/2)/256` ≈ baseSpe/512 (e.g. Tauros 110 → 55/256 ≈ 21.5 %) | `critRatio` defaults to **1** (`sim/dex-moves.ts:486` `this.critRatio = Number(data.critRatio) \|\| 1`) → `critMult[1] = 16` → **1/16 = 6.25 %** |
| high-crit move | `critRatio === 2` → ×4 → ≈ 4× base rate | `critRatio: 2` → `critMult[2] = 8` → **1/8** |
| Focus Energy | **HALVES** crit chance (`mods/gen1/scripts.ts:821-823`); `mods/gen1/moves.ts` explicitly kills the modern handler (`onModifyCritRatio: undefined`) | `+2` stages (`data/moves.ts` focusenergy condition `onModifyCritRatio(critRatio) { return critRatio + 2; }`) → ratio 3 → `critMult[3] = 4` → **1/4**; with a high-crit move → ratio 4 → **1/3** |
| multiplier | `level *= 2` inside the formula (≈ 1.95× at L100, less at low level) | ×2, via `battle.modify` (`mods/gen4/scripts.ts:86`) |
| what a crit ignores | attacker's *and* defender's boosts **and screens** (`mods/gen1/scripts.ts:875-895`) | attacker's **negative** offensive boosts and defender's **positive** defensive boosts only (`sim/battle-actions.ts:1682-1691`), plus Reflect/Light Screen (`mods/gen4/moves.ts:1108`, `:1164`) |
| suppressed by | — | Lucky Chant side condition (`data/moves.ts` luckychant `onCriticalHit: false`), Battle Armor / Shell Armor abilities |

**gen4 high-crit move list (tree-verified, from the merged gen4 table,
`num ≤ 467`, `gen4_moves_merge.js crit`):** aeroblast, aircutter, attackorder,
blazekick, crabhammer, crosschop, crosspoison, karatechop, leafblade, nightslash,
poisontail, psychocut, razorleaf, razorwind, shadowclaw, skyattack, slash,
spacialrend, stoneedge — all `critRatio: 2`. Of these, **crabhammer, crosschop,
leafblade, nightslash, psychocut, spacialrend, stoneedge, aeroblast, shadowclaw**
are in the gen4 randbats pool (§14).

**Encoder impact:** gen1's "fast mons crit a lot" is a *species* fact the encoder
gets for free from base Speed. In gen4 it is a *move* fact. A per-move crit-stage
feature (0/1) is new and cheap; a per-mon Focus Energy / Lucky Chant flag is new.

---

## 3. Move category (the physical/special split)

**tree-verified.** In gen4 `category` is a per-move field on base `data/moves.ts`
and is read by `Battle#getCategory` (`sim/battle.ts:2384`) and by `getDamage`
(`sim/battle-actions.ts:1673-1675`: `const isPhysical = move.category === 'Physical';
let attackStat = ... (isPhysical ? 'atk' : 'spa'); const defenseStat = ... (isPhysical ? 'def' : 'spd')`).

I computed, over the merged gen4 table restricted to `num ≤ 467` and
`!isNonstandard`, which moves the **gen1–3 by-type rule would get wrong**
(`gen4_moves_merge.js category`):

- **48 moves that are Physical in gen4 but would be Special by type:**
  aquajet, aquatail, assurance, avalanche, beatup, bite, blazekick, bulletseed,
  clamp, crabhammer, crunch, dive, dragonclaw, dragonrush, feintattack, firefang,
  firepunch, flamewheel, flareblitz, fling, iceball, icefang, icepunch, iceshard,
  iciclespear, knockoff, leafblade, needlearm, nightslash, outrage, payback,
  powerwhip, psychocut, punishment, pursuit, razorleaf, sacredfire, seedbomb,
  spark, suckerpunch, thief, thunderfang, thunderpunch, vinewhip, volttackle,
  waterfall, woodhammer, zenheadbutt.
- **49 moves that are Special in gen4 but would be Physical by type:**
  acid, aeroblast, aircutter, airslash, ancientpower, aurasphere, bugbuzz,
  chatter, doomdesire, earthpower, flashcannon, focusblast, gust, hiddenpower
  (+ the Bug/Fighting/Flying/Ghost/Ground/Poison/Rock/Steel variants), hyperbeam,
  hypervoice, judgment, mirrorshot, mudbomb, mudshot, mudslap, nightshade,
  ominouswind, powergem, razorwind, shadowball, signalbeam, silverwind, sludge,
  sludgebomb, smog, snore, sonicboom, spitup, swift, triattack, trumpcard,
  uproar, vacuumwave, weatherball, wringout.

**97 gen4-legal moves cannot be categorised from their type.** In the randbats pool
specifically this covers e.g. `suckerpunch` (31 sets), `pursuit` (16),
`extremespeed` (16), `waterfall` (28), `crunch` (20), `icepunch` (19),
`nightslash` (18), `shadowball` (34), `focusblast` (24), `earthpower` (23),
`sludgebomb` (18), `airslash` (14).

**Encoder impact:** `SNAP/rl/envs/encoder_spec.py:48-52` already anticipates this
and says "NO new table … only the gen-1 'category follows the type' rule stops
holding, and the encoder never assumed it." That is correct as far as the
`physical` slot in the move block goes. What it does **not** cover: the mon block's
`base_stat_keys` is `("hp","atk","def","spa","spe")` (`encoder_spec.py:224`) —
**Special Defence is genuinely absent**, and a gen4 policy cannot evaluate a
special attack without it. That is a MON_DIM change, i.e. an OBS_DIM change.

---

## 4. The type chart

**tree-verified** (computed by `tc_diff.js` from `SD/data/typechart.ts` +
`mods/{gen8,gen7,gen6,gen5,gen4}/typechart.ts` and, for gen1, + `mods/{gen3,gen2,gen1}`).
**Cross-checked source-verified** against `PE/data/static/typechart/gen4typechart.json`,
which agrees on every cell below.

Encoding: `damageTaken[Attacker] ∈ {0: neutral, 1: super-effective, 2: resist,
3: immune}` (`SD/sim/dex.ts:283-289`).

**17 live types in gen4** (bug, dark, dragon, electric, fighting, fire, flying,
ghost, grass, ground, ice, normal, poison, psychic, rock, steel, water) vs **15 in
gen1** (no dark, no steel: `mods/gen1/typechart.ts:129-136` mark both
`isNonstandard: 'Future'`). Fairy is `'Future'` at gen4 too
(`mods/gen5/typechart.ts:93-96`), so it must be excluded from a gen4 `types` tuple
even though `PokemonType` and poke-env's JSON both carry it.

**Every cell that differs between gen1 and gen4 among the 15 shared types:**

| attacker → defender | gen1 | gen4 | gen1 file:line | gen4 file:line |
|---|---|---|---|---|
| Ghost → Psychic | **0×** (immune) | **2×** | `mods/gen1/typechart.ts:110-127` (`Ghost: 3`) | `data/typechart.ts` psychic row (`Ghost: 1`) |
| Bug → Poison | **2×** | **0.5×** | `mods/gen1/typechart.ts:89-108` (`Bug: 1`) | `data/typechart.ts` poison row (`Bug: 2`) |
| Poison → Bug | **2×** | **1×** | `mods/gen1/typechart.ts:10-27` (`Poison: 1`) | `data/typechart.ts` bug row (`Poison: 0`) |
| Ice → Fire | **1×** | **0.5×** | `mods/gen1/typechart.ts:29-46` (`Ice: 0`) | `data/typechart.ts` fire row (`Ice: 2`) |

**The two new rows/columns (gen4, tree-verified):**

- **vs Dark:** weak to Bug 2×, Fighting 2×; resists Dark 0.5×, Ghost 0.5×;
  **immune to Psychic** (`data/typechart.ts` dark row `Psychic: 3`, kept by
  `mods/gen6/typechart.ts:2-24` which only drops the `prankster` key).
- **Dark attacking:** 2× vs Ghost and Psychic; 0.5× vs Dark, Fighting, **Steel**.
- **vs Steel:** weak to Fighting 2×, Fire 2×, Ground 2×; resists Bug, **Dark**,
  Dragon, Flying, **Ghost**, Grass, Ice, Normal, Psychic, Rock, Steel (all 0.5×);
  **immune to Poison**. The Ghost/Dark resistances are gen2–gen5-only and come
  from `mods/gen5/typechart.ts:68-91`; base (gen6+) drops them.
- **Steel attacking:** 2× vs Ice, Rock; 0.5× vs Electric, Fire, Steel, Water.

**Non-type keys on the gen4 chart (status/field immunities read through
`Pokemon#runStatusImmunity`):**

| type | gen4 | gen1 |
|---|---|---|
| fire | `brn: 3` (cannot be burned) | **absent** — gen1 Fire types *can* be burned |
| ice | `hail: 3`, `frz: 3` | **absent** — gen1 Ice types *can* be frozen |
| ground / rock / steel | `sandstorm: 3` | ground, rock only (no steel type) |
| poison / steel | `psn: 3`, `tox: 3` | poison only |
| ghost | **no `trapped: 3`** — gen4 Ghosts **can** be trapped by Mean Look / Shadow Tag / Arena Trap (base has `trapped: 3`; `mods/gen5/typechart.ts:24-45` drops it) | n/a |
| grass | **no `powder: 3`** — gen4 Grass types **are** hit by Sleep Powder / Spore / Stun Spore (base has `powder: 3`; `mods/gen5/typechart.ts:46-67` drops it) | n/a |

**Encoder impact:** `encoder_spec.py:212-218` hard-codes the 15 gen1 types in
alphabetical order as the one-hot layout; gen4 needs a 17-entry tuple. The
`mon_matchup_off` / `move_type_off` arithmetic is already derived from
`n_types` (`encoder_spec.py:159-190`), so the layout follows automatically — the
tuple is the only edit. The `off/def matchup` scalars (two per mon) must be
recomputed off the gen4 chart; poke-env's `gen4typechart.json` is the right source
and it is **source-verified present** in the pinned install.

---

## 5. STAB

**tree-verified.** gen4: `mods/gen4/scripts.ts:100-107` — `stab = 1.5` if
`move.forceSTAB || pokemon.hasType(type)`, applied via `battle.modify` after the
random roll and before type effectiveness; the `'???'` type never gets STAB.
gen1: `mods/gen1/scripts.ts:928-930` — `damage += Math.floor(damage / 2)`, applied
before type effectiveness. Numerically the same 1.5×; the rounding point differs.
Adaptability (2× STAB, one gen4 randbats set) hooks `ModifySTAB`
(`mods/gen4/scripts.ts:105`).

---

## 6. Accuracy and evasion

**tree-verified.** gen4 overrides `hitStepAccuracy` (`mods/gen4/scripts.ts:148-204`);
base is `sim/battle-actions.ts:690-750`.

| | gen1 | gen4 | base / gen5+ |
|---|---|---|---|
| denominator | **256** (`mods/gen1/scripts.ts:459`) | 100 (`mods/gen4/scripts.ts:195`) | 100 |
| guaranteed miss | **1/256 on every move that isn't self-targeted** — `mods/gen1/scripts.ts:456-462`, with the explicit hint "In Gen 1, moves with 100% accuracy can still miss 1/256 of the time." | **gone** | gone |
| boost table | `[25,28,33,40,50,66,100,150,200,250,300,350,400]/100`, indexed −6…+6 (`mods/gen1/scripts.ts:434`) | `[1, 4/3, 5/3, 2, 7/3, 8/3, 3]` (`mods/gen4/scripts.ts:164`) | same table but applied as a single net boost |
| how acc & eva combine | multiply by acc table, multiply by (inverted) eva table, `clampIntRange(accuracy, 1, 255)` (:445-450) | **separately**: `accuracy *= boostTable[accBoost]` then `accuracy /= boostTable[evaBoost]`, no intermediate truncation (:168-187) | **combined**: `boost = clamp(accBoost − evaBoost, −6, 6)` then one `trunc(accuracy * (3+boost)/3)` (`battle-actions.ts:714-727`) |
| `ModifyAccuracy` event | before the 1/256 roll | **after** the boost math (:188) | **before** the boost math (:712) |
| OHKO accuracy | n/a for our purposes | `30 + user.level − target.level`, immune if `user.level < target.level`, **bypasses all accuracy/evasion modifiers** (:154-162) | `30` (+level diff), plus gen7 Ice/Sheer Cold and type-immunity rules |

**Encoder impact:** the accuracy scalar in the move block already exists; the new
thing is that **evasion is a live axis in gen4** — Sand Veil (6 sets) and Snow
Cloak (4 sets) hook `ModifyAccuracy`, and Brightpowder / Lax Incense are gen4
items. The gen4 randbats **move** pool contains no evasion move
(no Double Team, no Minimize, no Acupressure — §14), so the `evasion` boost slot
will only ever be nonzero from Haze-style clears; the *accuracy* boost slot is
likewise dead. Both are already in `boost_keys` (`encoder_spec.py:222`).

---

## 7. Status conditions

### Sleep — the sharpest single-mechanic delta

| | gen1 | gen4 | base / gen5+ |
|---|---|---|---|
| roll | `this.random(1, 8)` → **1–7** (`mods/gen1/conditions.ts:53-86`, comment "1-7 turns") | `this.random(2, 6)` → **2–5** (`mods/gen4/conditions.ts:32`, comment "1-4 turns") | `this.random(2, 5)` → 2–4 (`data/conditions.ts` slp) |
| acts on the wake turn? | **NO.** `onBeforeMove` always `return false`; cure happens in `onAfterMoveSelf` (`mods/gen1/conditions.ts:19-30`) | **YES.** `if (pokemon.statusState.time <= 0) { pokemon.cureStatus(); return; }` — returning `undefined` lets the move run (`mods/gen4/conditions.ts:44-47`) | yes |
| effective turns lost | 1–7 | **1–4** | 1–3 |
| counter reset on switch | gen1 keeps `startTime`; `mods/gen5/conditions.ts:2-7` restores `time = startTime` **on switch-in** — this is a gen5 override and **applies to gen4**, so a gen4 sleeper that switches out re-rolls its clock back to full | n/a |
| `sleepUsable` | Sleep Talk / Snore run through `if (move.sleepUsable) return;` (`mods/gen4/conditions.ts:49-51`) | same | same |
| Sleep Talk multi-hit | — | **gen4-specific**: `if (hit > 1 && pokemon.status === 'slp' && (!isSleepUsable \|\| this.battle.gen === 4)) break;` (`sim/battle-actions.ts:892`) — a Sleep-Talked multi-hit move hits once | — |
| Rest | n/a in the gen1 pool sense | sets `statusState.time = 3` (`data/moves.ts` rest `onHit`), i.e. 2 turns asleep then act |
| Early Bird | — | `pokemon.statusState.time--` an extra time (`mods/gen4/conditions.ts:40-42`); 4 gen4 randbats sets |
| Sleep Clause Mod | in `Standard` (gen1 randbats) | **explicitly in the gen4 randbats ruleset** (`config/formats.ts:4243`) | |

**Policy impact:** gen1's "sleep is a 1–7-turn removal and you never move on the
wake turn" is why sleep moves dominate gen1 randbats. gen4's sleep is materially
weaker (1–4, and you act on wake), but the pool has **darkvoid, lovelykiss, spore,
hypnosis, sleeppowder** (§14) and **Grass types are no longer powder-immune**
(§4), so it is still a primary axis.

### Freeze

**gen1: permanent.** `mods/gen1/conditions.ts:87-107` — `onBeforeMove` always
`add('cant'); return false;` with no thaw roll; the only cure is
`onAfterMoveSecondary` when the move's secondary is `brn`. Ice types **can** be
frozen (no `frz: 3` in the gen1 ice row).

**gen4: 20 % thaw per turn.** `mods/gen4/conditions.ts:87-98`:
```ts
onBeforeMove(pokemon, target, move) {
    if (this.randomChance(1, 5)) { pokemon.cureStatus(); return; }
    if (move.flags['defrost']) return;
    this.add('cant', pokemon, 'frz'); return false;
}
```
Ice types are `frz: 3` immune. `defrost`-flagged moves (Flame Wheel, Sacred Fire,
Flare Blitz — the last two are in the gen4 pool) let the user act **and** thaw.
**Freeze Clause is NOT in the gen4 randbats ruleset** (`config/formats.ts:4243`),
whereas gen1 randbats gets it via `Standard` (`mods/gen1/rulesets.ts:13`).

### Paralysis

| | gen1 | gen4 |
|---|---|---|
| full-para rate | `randomChance(63, 256)` = **24.6 %** (`mods/gen1/conditions.ts:36`) | `randomChance(1, 4)` = **25 %** (`mods/gen4/conditions.ts:16-20`) |
| Speed | applied as a **destructive stat write** `modifyStat('spe', 0.25)` (`mods/gen1/scripts.ts:665`), which is why the **burn/para stat-drop reset bug** exists (see §13) | a clean `onModifySpe` chain modifier `chainModify(0.25)` (`mods/gen4/conditions.ts:9-14`); gen6+ changes it to `Math.floor(spe * 25/100)` after `finalModify` (`mods/gen6/conditions.ts:8-18`) — **gen4 uses the gen4 override, ×0.25** |
| exempt ability | — | Quick Feet (1 gen4 set) skips the Speed drop and the `randomChance` gate is Magic Guard-exempt (`mods/gen4/conditions.ts:16`) |
| also clears | Bide, twoturnmove, partialtrappinglock, lockedmove (`mods/gen1/conditions.ts:38-46`) | nothing |

### Burn

gen4 residual: `baseMaxhp / 8` (`mods/gen6/conditions.ts:4-6`, in gen4's inherit
chain), `onResidualOrder: 10, onResidualSubOrder: 6` (`mods/gen4/conditions.ts:2-6`).
Attack is **not** halved; instead **damage** is halved for physical moves at the
top of gen4's `modifyDamage` (`mods/gen4/scripts.ts:65-67`), Guts-exempt.

gen1: `floor(maxhp/16) * toxicCounter`, applied in `onAfterMoveSelf` (i.e. after
the burned mon's own move, not at end of turn), plus a second tick
`onAfterSwitchInSelf` (`mods/gen1/conditions.ts:12-29`). And the burn halves
**Attack destructively** (`mods/gen1/scripts.ts:664` `target.modifyStat!('atk', 0.5)`).

### Poison and Toxic

gen4 (base `data/conditions.ts`, sub-ordered by `mods/gen4/conditions.ts:55-64`):
- `psn`: `baseMaxhp / 8` at `onResidualOrder 10 / subOrder 6`.
- `tox`: `stage` starts 0, increments to a max of 15, damage
  `clampIntRange(baseMaxhp/16, 1) * stage`. **`onSwitchIn() { this.effectState.stage = 0; }`
  — the toxic counter RESETS on switch-out in gen4.**

gen1: there is no separate toxic counter object — the counter lives in a
`residualdmg` volatile and is **shared with psn and brn**
(`mods/gen1/conditions.ts:20-23, 116-119`, hint "In Gen 1, Toxic's counter is
retained after Rest and applies to PSN/BRN"), and **Leech Seed's damage is
multiplied by it** (`mods/gen1/moves.ts:450-457`, hint "In Gen 1, Leech Seed's
damage is affected by Toxic's counter"). That stacking is gone in gen4.

### Confusion

| | gen1 | gen4 | base |
|---|---|---|---|
| duration | `random(2, 6)` → 2–5 → **1–4 acting turns** (`mods/gen1/conditions.ts:139`) | `random(2, 6)` → **same** (base `data/conditions.ts` confusion, gen4 doesn't override the roll) | `random(2, 6)` |
| self-hit chance | `!randomChance(128, 256)` = **50 %** (`mods/gen1/conditions.ts:154`) | `if (this.randomChance(1, 2)) return;` = **50 %** (`mods/gen4/conditions.ts:74-76`) | `!randomChance(33, 100)` = **33 %** (gen7+) |
| self-hit damage | hand-rolled 40-BP physical using `getStat('atk')` vs `getStat('def', false)` (`mods/gen1/conditions.ts:155-158`) | `this.actions.getDamage(pokemon, pokemon, 40)` — a full 40-BP typeless **physical** hit through the normal pipeline, so **it can crit and it respects boosts** (`mods/gen4/conditions.ts:77-83`) | `getConfusionDamage` (no crit) |
| side effects | clears bide, twoturnmove, invulnerability, partialtrappinglock, lockedmove | none |

**No confusion move is in the gen4 randbats pool** (no Confuse Ray, Swagger,
Supersonic, Dynamic Punch *is* present with a 100 % confuse secondary — `dynamicpunch`
appears in the 181-move list). Outrage's fatigue confusion also applies. So the
CONFUSION volatile slot stays alive.

### Attract

`data/moves.ts` attract: `noCopy: true`, gender-gated
(`if (!(pokemon.gender === 'M' && source.gender === 'F') && ...) return false`),
50 % immobilise on `onBeforeMovePriority: 2`. **Not in the gen4 randbats move pool**;
**Cute Charm is** (7 sets), so the ATTRACT volatile can still appear on contact.

---

## 8. Volatiles and multi-turn state

Everything below is **tree-verified**. "gen4 file" is where gen4's value actually
comes from after the inherit chain.

| mechanic | gen1 | gen4 | encoder | policy |
|---|---|---|---|---|
| **Substitute** | HP `floor(maxhp/4) + 1` (`mods/gen1/moves.ts` substitute condition `onStart`); fails only if `hp < maxhp/4`; blocks a **hardcoded list** — psn/tox status, any stat-lowering move, confusion, `lockon`/`meanlook`/`mindreader`/`nightmare` — everything else passes through | HP `floor(maxhp/4)` (`data/moves.ts` substitute condition `onStart`); costs exactly `maxhp/4` and fails at `hp <= maxhp/4`; blocks by the **`bypasssub` move flag** (`mods/gen4/moves.ts:1280-1316`, `onTryPrimaryHit`); on break sets a `substitutebroken` volatile (`mods/gen4/scripts.ts:51`, `mods/gen4/conditions.ts:99-101`) cleared when the foe switches | sub-present flag exists (`Effect.SUBSTITUTE` in `encoder_spec.py:240`); **sub HP is not encoded and matters much more in gen4** | Sub + Leech Seed / Sub + Focus Punch are the two `MOVE_PAIRS` the gen4 generator enforces (`random-battles/gen4/teams.ts:30-36`) |
| **Protect / Detect** | not in gen1 | priority **3** (gen5+ is 4) — `mods/gen4/moves.ts:293-296` (detect), `:1026-1044` (protect); success counter `stall` from `mods/gen5/conditions.ts:24-46` (starts 2, **doubles**) with `counterMax: 8` from `mods/gen4/conditions.ts:134-139` ("In gen 3-4, the chance of protect succeeding does not fall below 1/8") → chain 100 %, 50 %, 25 %, 12.5 %, 12.5 %, … forever | needs a **consecutive-protect counter** slot | 45 randbats sets carry Protect; a 1/8 floor makes indefinite stalling viable in a way gen5+ does not |
| **Encore** | n/a | `durationCallback() { return this.random(4, 9); }` → **4–8 turns** (`mods/gen4/moves.ts:401-404`); base is a flat 3 | duration counter | 24 sets |
| **Taunt** | n/a | `this.random(3, 6)` → **3–5 turns** (`mods/gen4/moves.ts:1381-1383`); base is 3 | duration counter | 13 sets |
| **Disable** | gen1 has its own | accuracy **80** (base 100) and `this.random(4, 8)` → **4–7 turns** (`mods/gen4/moves.ts:299, 303-305`) | which move is disabled | not in the randbats pool |
| **Torment** | n/a | `bypasssub` (`mods/gen4/moves.ts:1411-1414`) | last-move-used | not in pool |
| **Leech Seed** | damage multiplied by the toxic counter (`mods/gen1/moves.ts:450-457`) | plain 1/8, `onResidualOrder 10 / subOrder 5` (`mods/gen4/moves.ts:723-730`) | already a slot (`encoder_spec.py:239`) | 10 sets |
| **Curse** | n/a | Ghost branch vs non-Ghost branch decided in `onModifyMove` (`mods/gen4/moves.ts:268-287`); type `"???"` so **no STAB, no effectiveness**; residual 10/8 | Ghost-curse residual is a distinct slot from the +Atk/+Def/−Spe boost | 11 sets |
| **Perish Song** | n/a | `onResidualOrder: 12` (`mods/gen4/moves.ts:1005-1011`) | 3-turn counter per side | **not in pool** |
| **Yawn** | n/a | duration 2, sleeps on `onEnd`; residual 10/19 (`mods/gen4/moves.ts:1524-1531`, base `data/moves.ts` yawn) | 1-turn "will fall asleep" flag | 4 sets |
| **Ingrain / Aqua Ring** | n/a | residual 10/1 and 10/2 (`mods/gen4/moves.ts:687-694`, `:36-44`); Ingrain also blocks switching and Magnet Rise | heal-per-turn flags | **neither in pool** |
| **Magnet Rise** | n/a | 5 turns; fails under Ingrain or Levitate; residual 10/16; `gravity: 1` flag (`mods/gen4/moves.ts:817-830`) | grounded/ungrounded is a real axis in gen4 | **not in pool** |
| **Partial trapping** (Wrap/Bind/Fire Spin/Clamp/Whirlpool/Sand Tomb/Magma Storm) | **skips the victim's move entirely** — `onBeforeMove` → `add('cant'); return false` (`mods/gen1/conditions.ts:192-220`); attacker locked 2–5 turns via `partialtrappinglock` `sample([2,2,2,3,3,3,4,5])` | victim **still acts**, takes `baseMaxhp / 16` per turn (`mods/gen5/conditions.ts:8-23`, divisor 16) for `this.random(3, 7)` = **3–6 turns**, 6 with Grip Claw (`mods/gen4/conditions.ts:110-118`), residual 10/9; also **traps** (`onTrapPokemon`) | trapped flag + chip | gen4 BPs are much lower: firespin/sandtomb/whirlpool 15 BP acc 70, wrap acc 85, clamp acc 75 (`mods/gen4/moves.ts:448-452, 1159-1163, 1483-1487, 1512-1515, 182-186`) |
| **Mean Look / Block / Spider Web** | n/a | `reflectable` (`mods/gen5/moves.ts:64-67, 546-549`); **Ghosts are NOT immune in gen4** (§4) | trapped flag | not in pool |
| **Bide** | gen1-native quirks | gen4 override keeps sleep/freeze cancelling it and deals `totalDamage * 2` as a priority-1 typeless physical hit (`mods/gen4/moves.ts:103-140`) | stored-damage counter | not in pool |
| **Uproar** | n/a | `this.random(3, 7)` = **3–6 turns**, 50 BP (base 3 turns, 90 BP) — `mods/gen4/moves.ts:1452-1464` | lock + "nobody can sleep" | not in pool |
| **Rollout / Ice Ball** | n/a | 30 BP, 90 acc, `basePowerCallback`, `failinstruct`/`noparentalbond` | 5-turn escalating BP counter | **neither in pool** |
| **Outrage / Thrash / Petal Dance** | n/a | `lockedmove` volatile: `trueDuration = this.random(2, 4)` → **2–3 turns** then `addVolatile('confusion')` (`data/conditions.ts` lockedmove); gen4 removes `onAfterMove` (`mods/gen4/conditions.ts:119-122`), and **Protect does not reset the counter** (`mods/gen4/moves.ts:1032-1038`, comment "Outrage counter is NOT reset"). gen4 BPs: outrage 120/pp15, thrash 90/pp20, petaldance 90/pp20 (base 120/120 pp10) | lock flag + remaining turns | **outrage is in the pool (13 sets)**; thrash/petaldance are not |
| **Two-turn moves** (Fly/Dig/Dive/Bounce/Shadow Force/Solar Beam/Skull Bash/Sky Attack/Razor Wind) | Dig/Fly are **banned by gen1 `Standard`** (`mods/gen1/rulesets.ts:15` `banlist: ['Dig','Fly']`) | all present; `charge` flag + `twoturnmove` volatile (`data/conditions.ts` twoturnmove, duration 2); semi-invulnerable ones set an `Invulnerability` handler that gen4 evaluates in its own `hitStepInvulnerabilityEvent` (`mods/gen4/scripts.ts:138-147`); Gravity cancels Fly/Bounce (`data/moves.ts` gravity `onFieldStart`); Skull Bash 100 BP (`mods/gen5/moves.ts:766-770`) | a **"charging / semi-invulnerable" flag with the pending move id** — `encoder_spec.py` has a `preparing` slot in the active block (`:171`) | **only Solar Beam (3 sets) is in the gen4 randbats pool**; no Fly/Dig/Dive/Bounce/Shadow Force |
| **Recharge** (Hyper Beam / Giga Impact) | gen1: recharge is skipped if the target faints, and a partial-trapping move or a sleep move **cancels** it (`mods/gen1/moves.ts:75-80, 937-941`; `mods/gen1/scripts.ts:648-658`) | plain `mustrecharge` volatile, duration 2, `onLockMove: 'recharge'` (`data/conditions.ts:364-378`) | already a slot via `mon.must_recharge` (`encoder_spec.py:232-236`) | Giga Impact appears on 1 set; Hyper Beam on none |
| **Charge** | n/a | volatile + `spd: 1` boost (`data/moves.ts` charge) | — | not in pool |
| **Stockpile / Spit Up / Swallow** | n/a | `mods/gen4/moves.ts:1328` swallow override | 0–3 stockpile counter | not in pool |
| **Destiny Bond** | n/a | `bypasssub`, volatile (`data/moves.ts` destinybond) | flag | 4 sets |
| **Grudge** | n/a | `bypasssub`, volatile | flag | not in pool |
| **Embargo / Heal Block / Gastro Acid / Power Trick / Lock-On** | n/a | residual 10/18, 10/17 (`mods/gen4/moves.ts:381-393`, `:624-637`); Heal Block in gen4 also blocks drain/Leech Seed/Wish (`:632-636`); Gastro Acid suppresses the ability; Power Trick swaps Atk/Def; Lock-On is `noCopy: false` in gen4, i.e. **Baton-Passable** (`mods/gen4/moves.ts:749-755`) | volatile flags | **none in pool** |
| **Foresight / Odor Sleuth / Miracle Eye** | n/a | all `bypasssub` in gen4 (`mods/gen4/moves.ts:524-527, 981-984, 898-901`); Foresight/Odor Sleuth share the `foresight` volatile | flag that changes the matchup scalar | not in pool |
| **Nightmare** | n/a | residual 10/7; auto-cleared when sleep ends (`mods/gen4/conditions.ts:34-36`) | flag | not in pool |
| **Minimize / Defense Curl** | n/a | gen4 Minimize is **+1 evasion** (base +2) and pp 20 (`mods/gen4/moves.ts:892-897`); Defense Curl flags Rollout/Ice Ball | — | not in pool |
| **Roost** | n/a | 1-turn volatile removing Flying from the type list via `onType` (`data/moves.ts` roost condition, `onTypePriority: -1`); heal 1/2 | **a per-turn type override on the active mon** — the encoder's type one-hot is read from the species, so Roost silently desyncs it | **45 randbats sets** — the single most common non-attacking move in the pool |
| **Wish** | n/a | slot condition, duration 2, `onResidualOrder: 7`, heals `target.baseMaxhp / 2` — **gen4 heals half the RECIPIENT's max HP**, not the wisher's (`mods/gen4/moves.ts:1492-1507`) | pending-wish flag per slot | 19 sets, paired with Protect (`teams.ts:33`) |
| **Future Sight / Doom Desire** | n/a | `futuremove` `onResidualOrder: 11` (`mods/gen4/conditions.ts:130-133`); gen4 stats: Future Sight 80 BP / 90 acc / pp 15, Doom Desire 120 BP / 85 acc (`mods/gen4/moves.ts:541-545, 331-...`) | delayed-hit countdown | **neither in pool** |
| **Baton Pass** | n/a | `selfSwitch: 'copyvolatile'`; `Pokemon#copyVolatileFrom` copies **boosts plus every volatile without `noCopy`** (`sim/pokemon.ts:1252-1274`). gen4 explicitly makes `trapped`, `trapper` and `lockon` **copyable** (`mods/gen4/conditions.ts:102-109`, `mods/gen4/moves.ts:749-755`) | — | **not in the pool** |
| **U-turn** | n/a | `selfSwitch: true`, 70 BP Bug physical, no priority — the switch happens after the hit, before the foe's move if U-turn was faster | pending-self-switch is invisible to the encoder but is an *action* the policy sees as a forced switch request | **54 sets — the 6th most common move in the pool** |
| **Pursuit on a switch** | n/a | gen4 rewrites `onFoeBeforeSwitchOut` (`mods/gen4/moves.ts:1049-1078`): the Pursuit user's queued action is cancelled and the move fires **at the switching mon at double BP**, blocked if the user is frz/slp/Truant or Encored into something else | "foe may Pursuit me" is not observable; it is a *policy* fact | 16 sets |
| **Fake Out** | n/a | priority **1** (`mods/gen4/moves.ts:434-437`; gen5+ is 3), 100 % flinch, first turn only | "this mon just switched in" (`activeTurns == 0`) | 8 sets |
| **Sucker Punch** | n/a | priority 1, 80 BP; gen4 `onTry` fails if the target is not queued to use a **damaging** move or is recharging (`mods/gen4/moves.ts:1318-1326`) | — | **31 sets** — a major mind-game axis with no gen1 analogue |
| **Counter / Mirror Coat / Metal Burst** | gen1 Counter is a **desync-prone** 2×-last-damage move over Normal/Fighting moves with `ignoreImmunity` (`mods/gen1/moves.ts` counter, 40+ lines of POV bookkeeping) | Counter priority **−5**, Physical, `target: 'scripted'`, doubles physical damage taken this turn; Mirror Coat the special mirror; Metal Burst priority 0, 1.5× (`data/moves.ts`) | — | counter 2, mirrorcoat 1, metalburst 1 set |
| **Endeavor** | n/a | gen4 `onTry` fails outright if `pokemon.hp >= target.hp` (`mods/gen4/moves.ts:421-428`) | — | not in pool |
| **Trick / Switcheroo** | n/a | swap items; the gen4 generator deliberately hands Poison types **Black Sludge instead of Leftovers** "For Trick / Switcheroo" (`random-battles/gen4/teams.ts:670-673`) | **item identity per mon** | trick 21, switcheroo 4 |
| **Knock Off** | n/a | **20 BP with no boost** (`mods/gen5/moves.ts:485-489` sets BP 20 and kills the gen6 `onBasePower`); gen4's `onAfterHit` only makes the item *unusable*, with the hint "In Gens 3-4, Knock Off only makes the target's item unusable; it cannot obtain a new item" (`mods/gen4/moves.ts:706-718`) | item-knocked-off flag | 3 sets |
| **Rapid Spin** | n/a | 20 BP; clears Leech Seed, spikes/toxicspikes/stealthrock/stickyweb, and partial trapping — but only `self.onHit`, i.e. **only if the move connects** (`mods/gen4/moves.ts:1080-1098`) | — | 13 sets, against 14 Spikes + 14 Toxic Spikes sets |
| **Roar / Whirlwind** | in gen1 both have `priority: 0` and **`forceSwitch` false** (they are no-ops on the last mon and behave differently) | priority **−6**, `forceSwitch: true`; **Roar is a `sound` move with `bypasssub` in gen4** (`mods/gen4/moves.ts:1143-1146`) — it hits through Substitute, which it does not from gen5 | — | roar 7, whirlwind 6 |
| **Haze** | gen1: `target: 'self'`, and gen1's Haze has extra status-clearing quirks | gen4: `target: 'all'`, clears every active mon's boosts **and Focus Energy** (`mods/gen4/moves.ts:600-609`) | — | 5 sets |
| **Explosion / Self-Destruct** | gen1 halves defence inside its own formula (`mods/gen1/scripts.ts:912-915`) | **`sim/battle-actions.ts:1706-1708`**: `if (this.battle.gen <= 4 && ['explosion','selfdestruct'].includes(move.id) && defenseStat === 'def') defense = clampIntRange(Math.floor(defense / 2), 1);` — BP is 250/200 in both gens, so the effective damage is **double** what gen5+ deals | — | explosion 37 sets, selfdestruct 3 — a first-order gen4 threat |
| **Struggle** | gen1: `pp: 10`, `recoil: [1, 2]` = **half the damage dealt**, and `onModifyMove: undefined` so it keeps its Normal type (`mods/gen1/moves.ts` struggle) | gen4: `struggleRecoil` → `clampIntRange(Math.floor(pokemon.baseMaxhp / 4), 1)` = **1/4 max HP** via `directDamage` (`mods/gen4/scripts.ts:205-220`), and `onModifyMove(move) { move.type = '???' }` (`mods/gen4/moves.ts:1270-1279`) so it is **typeless**: no STAB, no effectiveness, hits Ghosts | — | always available |
| **Hidden Power** | gen1 has its own gen2 formula | gen4 uses the gen3+ IV formula with **variable BP**: `power = tr(hpPowerX * 40 / 63) + 30` when `gen < 6` (`sim/dex.ts:380-383`), and `basePowerCallback(pokemon) { return pokemon.hpPower \|\| 70; }` (`mods/gen5/moves.ts:382-390`). The gen4 randbats generator writes the type's canonical `HPivs` spread (`random-battles/gen4/teams.ts:681-690`), and I computed that **all 16 spreads give exactly BP 70** — so in gen4 randbats Hidden Power is always **70 BP of the named type** | the move id already carries the type (`hiddenpowerice` etc.) in our own request JSON | 7 HP types are in the pool: ice 24, fighting 19, grass 17, fire 14, electric, flying, ground, rock |

---

## 9. Side conditions

**tree-verified.** In gen1, Reflect / Light Screen / Mist are **per-mon volatiles**
that die on switch-out (`gen4_moves_merge.js named` shows `vol: 'reflect'`,
`vol: 'lightscreen'`, `vol: 'mist'`, `target: 'self'` on the gen1 side; and gen1
applies Reflect/Light Screen by **doubling the defence stat inline** at
`mods/gen1/scripts.ts:869-873`). From gen2 they are **5-turn side conditions**.

| side condition | gen4 semantics | file:line |
|---|---|---|
| **Stealth Rock** | on entry, `damage(pokemon.maxhp * 2 ** typeMod / 8)` with `typeMod = clampIntRange(runEffectiveness(stealthrock), -6, 6)` → **1/32 … 1/2 max HP by Rock-type effectiveness**; fires on the `EntryHazard` event, not `SwitchIn` | `mods/gen4/moves.ts:1257-1268` |
| **Spikes** | 3 layers max (`data/moves.ts` spikes `onSideRestart`); `damageAmounts = [0,3,4,6]; damage(amount * maxhp / 24)` → **1/8, 1/6, 1/4**; **grounded only** | `mods/gen4/moves.ts:1240-1252`, base `data/moves.ts` spikes |
| **Toxic Spikes** | 2 layers max; **grounded only**; a grounded **Poison** type **absorbs the layer** and removes the hazard; **Steel** types and anything behind a **Substitute** are unaffected (the Substitute clause is gen4-specific); 1 layer → `psn`, 2 layers → `tox` | `mods/gen4/moves.ts:1419-1439` |
| **Reflect / Light Screen** | duration **5**, **8 with Light Clay** (base `data/moves.ts` reflect `durationCallback`); halve physical/special damage respectively **unless the hit is a crit or `infiltrates`**; in gen4 they hook `ModifyDamagePhase1`, i.e. **before the `+2` and before the crit multiplier**; side-residual order 1 and 2 | `mods/gen4/moves.ts:1103-1119`, `:731-748`; `data/items.ts:3440` |
| **Safeguard** | duration 5; blocks `onSetStatus` and `onTryAddVolatile`; side-residual order 4 | `mods/gen4/moves.ts:1151-1158`, base `data/moves.ts` safeguard |
| **Mist** | duration 5; blocks stat drops from the foe; side-residual order 3 | `mods/gen4/moves.ts:920-927` |
| **Tailwind** | duration **3** in gen4 (base is 4); `onModifySpe(spe) { return spe * 2; }`; side-residual order 5 | `mods/gen4/moves.ts:1357-1375` |
| **Lucky Chant** | duration 5; `onCriticalHit: false`; side-residual order 6 | `mods/gen4/moves.ts:756-765`, base `data/moves.ts` luckychant |

**Hazards fire on the `EntryHazard` event in gen4**, which gen4's `runSwitch`
raises *before* `SwitchIn` (`mods/gen4/scripts.ts:18-21`) and each hazard's base
`onSwitchIn` is explicitly killed (`onSwitchIn: undefined, // no inherit`). That
ordering matters for ability interactions on entry.

**Pool reality (§14):** of these, **only Spikes (14 sets) and Toxic Spikes
(14 sets)** occur in gen4 randbats. **Stealth Rock is absent from every set**
(verified: zero occurrences of the substring `stealthrock` in
`SD/data/random-battles/gen4/sets.json`, and `HAZARDS` at `teams.ts:24-27` lists it
but no movepool contains it). Reflect, Light Screen, Safeguard, Mist, Tailwind and
Lucky Chant are all absent too.

---

## 10. Weather

**tree-verified.** All four weathers are base conditions
(`data/conditions.ts` `raindance`, `sunnyday`, `sandstorm`, `hail`); gen4 only
re-orders them to `onFieldResidualOrder: 8` (`mods/gen4/conditions.ts:140-155`).

- **Duration:** `duration: 5`, `durationCallback` → **8** with the matching rock
  (Damp Rock / Heat Rock / Smooth Rock / Icy Rock).
- **Ability-set weather is INDEFINITE in gen4.** Each `onFieldStart` carries
  ```ts
  if (effect?.effectType === 'Ability') { if (this.gen <= 5) this.effectState.duration = 0; ... }
  ```
  (`data/conditions.ts` raindance :23-24, sunnyday, sandstorm :20-21, hail :12-13).
  `duration = 0` means never expires. Drizzle (2 sets), Drought (2), Sand Stream (3)
  and Snow Warning (1) are all in the gen4 randbats ability pool, so a
  **permanent weather is a realistic game state.**
- **Effects:** rain ×1.5 Water / ×0.5 Fire; sun the mirror; **sandstorm gives
  Rock types ×1.5 SpD** (`data/conditions.ts` sandstorm `onModifySpDPriority: 10`).
- **Chip:** sand and hail both `this.damage(target.baseMaxhp / 16)`.
- **Chip immunity** goes through `Pokemon#runStatusImmunity` at
  `sim/battle.ts:2113` (`if (effect.effectType === 'Weather' && !target.runStatusImmunity(effect.id))`),
  i.e. it reads the **typechart's lowercase keys**: sandstorm-immune = Ground,
  Rock, Steel; hail-immune = Ice. Magic Guard also exempts.
- **Sand Veil (6 sets) / Snow Cloak (4 sets)** are evasion abilities that hook
  `ModifyAccuracy` in the matching weather; **Air Lock (3) / Cloud Nine (1)**
  suppress weather effects (`Field#suppressingWeather`, checked at
  `sim/battle.ts:618, 891`); **Forecast (1)** and **Flower Gift (2)** change form/stats.
- **No weather move except Rain Dance (10) and Sunny Day (3) is in the pool** —
  no Sandstorm move, no Hail move; sand and hail come **only** from abilities and
  are therefore **always permanent** when they occur.

**Encoder impact:** gen1 has no weather at all. This is a new global block:
weather id (5-way one-hot: none/rain/sun/sand/hail) + turns remaining
(with "indefinite" as a distinguished value, not 0).

---

## 11. Fields (pseudo-weather)

- **Trick Room:** move priority **−7**, `pseudoWeather`, duration 5
  (`data/moves.ts` trickroom); gen4 sets `onFieldResidualOrder: 13`
  (`mods/gen4/moves.ts:1444-1451`). The inversion is implemented in the gen4
  `Pokemon#getActionSpeed` override (`mods/gen4/scripts.ts:6-14`):
  ```ts
  getActionSpeed() { let speed = this.getStat('spe', false, false);
      const trickRoomCheck = ... this.battle.field.getPseudoWeather('trickroom');
      if (trickRoomCheck) { speed = -speed; } return speed; }
  ```
  Note gen4's version **omits the Quick Claw branch** that gen3's has
  (`mods/gen3/scripts.ts:24-26`), i.e. gen4 Quick Claw is handled elsewhere.
  **1 randbats set.**
- **Gravity:** duration 5, `accuracy * 5/3`, grounds everyone, cancels
  Fly/Bounce/Sky Drop/Magnet Rise/Telekinesis on start, disables `gravity`-flagged
  moves; gen4 `onFieldResidualOrder: 9` (`mods/gen4/moves.ts:585-592`, base
  `data/moves.ts` gravity :11-55). **Not in the pool.**
- Mud Sport / Water Sport exist in gen4 as **volatiles**, not field effects
  (`mods/gen4/moves.ts:952-...`, `:1469-...`). Not in the pool.

---

## 12. Turn order, priority, PP

**Action order (base, `sim/battle-queue.ts:173-199`, tree-verified):**
`instaswitch` 3 → `beforeTurn` 4 / `beforeTurnMove` 5 (this is where **Counter /
Mirror Coat / Focus Punch / Pursuit** register) → `runSwitch` 101 → **`switch` 103**
→ `megaEvo` 104 → `shift` 200 → **moves 200 (default)** → `residual` 300.
**All switches resolve before all moves**, ordered among themselves by speed.

Within a bracket, `Battle#comparePriority` (`sim/battle.ts:404-411`) sorts by
`order`, then `priority`, then `speed`, then `subOrder`, then `effectOrder`.
**Speed ties are broken RANDOMLY**: `speedSort` collects the tied indices and calls
`this.prng.shuffle(list, sorted, sorted + nextIndexes.length)`
(`sim/battle.ts:437-458`).

**Every non-zero-priority gen4-legal move** (`num ≤ 467`, `!isNonstandard`,
merged table — `gen4_moves_merge.js priority`, tree-verified):

| priority | moves |
|---|---|
| +5 | helpinghand |
| +4 | endure, magiccoat, snatch |
| +3 | detect, followme, **protect** |
| +2 | feint |
| +1 | aquajet, bide, bulletpunch, **extremespeed**, **fakeout**, iceshard, machpunch, quickattack, shadowsneak, **suckerpunch**, vacuumwave |
| −1 | vitalthrow |
| −3 | focuspunch |
| −4 | avalanche, revenge |
| −5 | counter, mirrorcoat |
| −6 | roar, whirlwind |
| −7 | trickroom |

Two gen4-specific values worth flagging: **Extreme Speed is +1 in gen4** (it
becomes +2 at gen5 — base `data/moves.ts` has 2), so it **ties** with Fake Out,
Sucker Punch, Bullet Punch and friends and is resolved by Speed; and **Protect /
Detect are +3** (they become +4 at gen5).

gen1 has priority brackets too (Quick Attack +1 etc., unmodified by the gen1 mod),
so the *concept* is not new — but +1 priority moves are **77 of the 464 gen4
randbats sets** and there are eight distinct ones, against essentially one in gen1.

**PP and Pressure.** `Pokemon#deductPP` (`sim/pokemon.ts:894-906`) deducts 1 by
default; **Pressure** (`data/abilities.ts` pressure `onDeductPP` → return 1) makes
it 2. Pressure is on **32 gen4 randbats sets** — the second most common ability
after Levitate — so PP is a live resource in a way it is not in gen1 (gen1 has no
abilities at all). The move block already carries a `pp` scalar
(`encoder_spec.py:148`, "known/bp/acc/pp/matchup/physical/status/priority").
`mustpressure`-flagged moves (spikes, stealthrock, toxicspikes) charge Pressure
even though they don't target the Pressure holder (`mods/gen4/moves.ts:1242, 1259, 1421`).

---

## 13. Clauses, the turn cap, and the format definition

**tree-verified, and this is a real surprise.**

```
config/formats.ts:4239-4244
  name: "[Gen 4] Random Battle",
  mod: 'gen4',
  team: 'random',
  bestOfDefault: true,
  ruleset: ['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod'],
```

versus

```
config/formats.ts:4260-4265
  name: "[Gen 1] Random Battle",
  mod: 'gen1', team: 'random', bestOfDefault: true,
  ruleset: ['Standard'],
```

and gen1's `Standard` (`mods/gen1/rulesets.ts:8-16`) expands to
`Standard AG` (= Obtainable, **Desync Clause Mod**, HP Percentage Mod, Cancel Mod,
**Endless Battle Clause**) plus **Sleep Clause Mod, Freeze Clause Mod, Species
Clause, Nickname Clause, OHKO Clause, Evasion Moves Clause**, with
`banlist: ['Dig','Fly']`.

So, in the format we would actually run:

| clause | gen1 randbats | gen4 randbats |
|---|---|---|
| Sleep Clause Mod | **yes** | **yes** |
| Freeze Clause Mod | **yes** | **no** |
| Species Clause | yes | **no** |
| OHKO Clause | yes | **no** (moot: no OHKO move is in the pool — §14) |
| Evasion Moves Clause | yes | **no** (moot: no evasion move is in the pool) |
| **Endless Battle Clause** | **yes** | **no** |
| HP Percentage Mod | yes | yes |
| Cancel Mod | yes | yes |
| Desync Clause Mod | yes (gen1-only) | n/a |

**Turn cap.** `sim/battle.ts:1833-1849` — independent of Endless Battle Clause
(the comment at :1835 says so explicitly): nothing happens before turn 100;
at `turn > 1000` the battle **ties**; warnings fire every 100 turns from 500,
every 10 from 900, every turn from 990. Endless Battle Clause's
berry-cycling adjudication (:1851-1897) simply never runs in gen4 randbats.

**Sleep Clause Mod** (`data/rulesets.ts:1378-1400`) blocks `onSetStatus` for `slp`
if any of the target's team already has a foe-inflicted `slp` — this is the mod
that makes multi-sleep impossible and it **is** active in gen4.

**Policy impact:** with no Endless Battle Clause and no Species Clause, and with
Levitate/Wonder Guard/Magic Guard/Substitute+Protect all in the pool, gen4
randbats can genuinely reach turn 1000 and auto-tie. The gen1 episode-length
priors and the tie handling in our reward should be re-checked before a gen4 run.

---

## 14. What actually occurs: the gen4 randbats move and ability universe

**tree-verified** by parsing `SD/data/random-battles/gen4/sets.json` and reading
`SD/data/random-battles/gen4/teams.ts:44-45, 627-666`. gen4's `randomSet` draws its
`movePool` **only** from `set.movepool` in `sets.json`
(`teams.ts:636-641`), so the union of movepools is the complete move universe
(plus Struggle). Cross-ref: the randbats/sets agent should confirm this
independently; I am reporting it because it bounds the encoder hard.

- **295 species, 464 sets, 181 distinct moves, 101 distinct abilities.**
  Levels 67–100 (mode 69 and 83, 19 species each).
- **The 181 moves:** aerialace aeroblast agility airslash aquajet aquatail
  aromatherapy aurasphere bellydrum bite blizzard bodyslam bravebird brickbreak
  bugbite bugbuzz bulkup bulletpunch calmmind chatter closecombat counter
  crabhammer crosschop crunch curse darkpulse darkvoid destinybond discharge
  doubleedge dracometeor dragonclaw dragondance dragonpulse drillpeck
  dynamicpunch earthpower earthquake encore energyball eruption explosion
  extremespeed facade fakeout fireblast firefang firepunch flamethrower
  flareblitz flashcannon focusblast focuspunch gigaimpact glare grassknot
  gunkshot hammerarm haze headbutt headsmash healbell healingwish heatwave
  hiddenpower{electric,fighting,fire,flying,grass,ground,ice,rock} highjumpkick
  hydropump hypervoice hypnosis icebeam icefang icepunch iceshard ironhead
  irontail judgment knockoff lavaplume leafblade leafstorm leechseed lovelykiss
  lowkick machpunch megahorn metalburst meteormash milkdrink mirrorcoat moonlight
  morningsun nastyplot nightshade nightslash outrage overheat painsplit payback
  poisonjab powergem powerwhip protect psychic psychoboost psychocut pursuit
  quickattack raindance rapidspin recover refresh rest return roar rockblast
  rockpolish rockslide roost sacredfire seedbomb seedflare seismictoss
  selfdestruct shadowball shadowclaw shadowsneak signalbeam skyuppercut slackoff
  sleeppowder sleeptalk sludgebomb softboiled solarbeam spacialrend spikes spore
  stoneedge stunspore substitute suckerpunch sunnyday superfang superpower surf
  switcheroo swordsdance synthesis tailglow taunt thunder thunderbolt thunderfang
  thunderwave toxic toxicspikes transform triattack trick trickroom uturn
  vacuumwave volttackle waterfall waterspout weatherball whirlwind willowisp wish
  woodhammer xscissor yawn zenheadbutt.
- **Top of the distribution:** toxic 132, earthquake 127, icebeam 81, thunderbolt
  57, stoneedge 57, uturn 54, surf 48, swordsdance 48, roost 45, protect 45,
  substitute 44, calmmind 44, psychic 44, fireblast 43, return 39, thunderwave 39,
  explosion 37, recover 37, rest 35, shadowball 34, suckerpunch 31.
- **Mechanics that are implemented but CANNOT OCCUR** (no move in the pool, and
  no ability path I know of): Stealth Rock, Baton Pass, Reflect, Light Screen,
  Safeguard, Mist, Tailwind, Lucky Chant, Gravity, Perish Song, Disable, Torment,
  Embargo, Heal Block, Power Trick, Gastro Acid, Lock-On, Foresight, Odor Sleuth,
  Miracle Eye, Nightmare, Ingrain, Aqua Ring, Magnet Rise, Future Sight, Doom
  Desire, Endeavor, Flail, Reversal, Rollout, Ice Ball, Thrash, Petal Dance,
  Uproar, Hyper Beam, Fly, Dig, Dive, Bounce, Shadow Force, Feint, Avalanche,
  Revenge, Vital Throw, Icy Wind, Memento, all four OHKO moves, all evasion moves,
  Double Team, Minimize, Acupressure, Confuse Ray, Swagger, Attract, Sandstorm
  (move), Hail (move).
- **Top abilities:** Levitate 40, Pressure 32, Multitype 23 (Arceus formes),
  Intimidate 20, Chlorophyll 16, Swift Swim 16, Water Absorb 13, Thick Fat 12,
  Torrent 12, Clear Body 11, Natural Cure 10, Own Tempo 10, Synchronize 9,
  Rock Head 9. Weather setters: Drizzle 2, Drought 2, Sand Stream 3, Snow Warning 1.
  Type-immunity abilities (Levitate, Water/Volt Absorb, Flash Fire, Dry Skin,
  Motor Drive, Wonder Guard) total **≈ 68 sets** — a policy that cannot see the
  ability will be systematically wrong about effectiveness.

---

## 15. gen1 quirks that DISAPPEAR in gen4

All **tree-verified** against the gen1 mod unless marked otherwise.

| gen1 quirk | where it lives | gen4 |
|---|---|---|
| the **1/256 miss** on every non-self move | `mods/gen1/scripts.ts:456-462` | gone; accuracy is out of 100 (`mods/gen4/scripts.ts:195`) |
| partial trapping **skips the victim's turn entirely** | `mods/gen1/conditions.ts:198-202` | victim acts; 1/16 chip for 3–6 turns (`mods/gen5/conditions.ts:8-23`, `mods/gen4/conditions.ts:110-118`) |
| **Hyper Beam's recharge is cancelled** by a partial-trapping move (even on a miss) or a sleep move | `mods/gen1/moves.ts:75-80, 937-941`; `mods/gen1/scripts.ts:648-658` | gone; `mustrecharge` is a plain duration-2 volatile (`data/conditions.ts:364-378`) |
| Hyper Beam does **not** require a recharge if the target faints | *I could not locate this in the vendored gen1 mod* — see "unread / unverified" | n/a |
| **Counter** reads *last selected* vs *last used* move across POVs and desyncs | `mods/gen1/moves.ts` counter (40+ lines, with a `Desync Clause Mod` ruleset) | plain priority −5 double-the-physical-damage-taken (`data/moves.ts` counter) |
| **Bide** stores damage across sleep/freeze with gen1 timing | `mods/gen1/moves.ts:33-...` | still exists but the gen4 version is a clean priority-1 typeless 2× hit (`mods/gen4/moves.ts:103-140`); **not in the gen4 pool** |
| **Substitute** is `floor(maxhp/4)+1` HP and blocks by a hardcoded status list | `mods/gen1/moves.ts` substitute | `floor(maxhp/4)`, blocks by the `bypasssub` flag |
| the **burn/paralysis stat-drop reset bug** (a stat-changing move re-applies the ×0.5 Atk / ×0.25 Spe penalty on top of itself) | `mods/gen1/scripts.ts:626-634` and :649 comment "This does NOT revert the paralyse speed drop or the burn attack drop" | gone; both are chain modifiers (`mods/gen4/scripts.ts` burn at :65; `mods/gen4/conditions.ts:9-14` par) |
| stat **rollover at 256/1024** | `mods/gen1/scripts.ts:897-910` | gone |
| **Wrap** and friends as a lock-the-opponent-out tool at 85 acc | `mods/gen1/moves.ts:930-943` | 15–35 BP chip moves at 70–85 acc |
| **Toxic's counter is shared with psn/brn and multiplies Leech Seed** | `mods/gen1/conditions.ts:20-23, 116-119`; `mods/gen1/moves.ts:450-457` | `tox` has its own `stage`, resets on switch, and Leech Seed is a flat 1/8 |
| **sleep 1–7 turns with no move on the wake turn** | `mods/gen1/conditions.ts:53-86` | 1–4 turns, acts on the wake turn (`mods/gen4/conditions.ts:22-53`) |
| **freeze is permanent** | `mods/gen1/conditions.ts:87-107` | 20 % thaw/turn + `defrost` moves (`mods/gen4/conditions.ts:87-98`) |
| **speed-based crits** | `mods/gen1/scripts.ts:816-843` | stage table, 1/16 default (`sim/battle-actions.ts:1622-1644`) |
| **the single Special stat** | `mods/gen1/pokedex.ts` mirrors spd from spa; `SNAP/rl/envs/encoder_spec.py:224` drops `spd` for this reason | gen2+ splits SpA/SpD; **gen4 needs 6 base stats** |
| the **Focus Energy bug** (halves crit rate instead of raising it) | `mods/gen1/scripts.ts:821-823` and `mods/gen1/moves.ts` focusenergy `onModifyCritRatio: undefined` | +2 crit stages (`data/moves.ts` focusenergy) |
| Fire types can be **burned**, Ice types can be **frozen** | absence of `brn: 3` / `frz: 3` in `mods/gen1/typechart.ts` | both immune (`data/typechart.ts` fire, ice) |
| **Dig and Fly are banned** in gen1 randbats | `mods/gen1/rulesets.ts:15` | legal (and absent from the pool anyway) |

---

## 16. The delta table (condensed, for `mechanics_delta.md`)

| mechanic | gen1 (file:line) | gen4 (file:line) | encoder must carry | policy must reason about |
|---|---|---|---|---|
| move category | derived from type, `mods/gen3/scripts.ts:4-14` | per-move `category`, `sim/battle.ts:2384` | nothing new in the move block; **`spd` in the mon block** | 97 moves break the type→category heuristic |
| type chart | 15 types, `mods/gen1/typechart.ts` | 17 types, `data/typechart.ts` + `mods/gen5/typechart.ts:68-96` | 17-entry `types` tuple; recomputed matchup scalars | Steel/Dark resistances; Ghost→Psychic now 2× |
| crit | speed-based, `mods/gen1/scripts.ts:816-843` | 1/16 stage table, `sim/battle-actions.ts:1622-1644` | per-move crit stage (0/1); Focus Energy + Lucky Chant flags | high-crit moves as a real threat class |
| damage order | `mods/gen1/scripts.ts:920-969` | `mods/gen4/scripts.ts:57-137` | — | burn halves before `+2`; crit bypasses screens |
| accuracy | /256 + 1/256 miss, `mods/gen1/scripts.ts:434-462` | /100, separate acc & eva tables, `mods/gen4/scripts.ts:148-204` | acc/eva boost slots (already present) | Sand Veil / Snow Cloak / Brightpowder |
| sleep | 1–7, no wake-turn move, `mods/gen1/conditions.ts:53-86` | 1–4, acts on wake, `mods/gen4/conditions.ts:22-53` | sleep-turn counter (`active_counter_off` exists) | sleep is weaker; Sleep Clause still on |
| freeze | permanent, `mods/gen1/conditions.ts:87-107` | 20 %/turn, `mods/gen4/conditions.ts:87-98` | — | no Freeze Clause in gen4 randbats |
| paralysis | 63/256, destructive Spe write, `mods/gen1/conditions.ts:30-52` | 25 %, `chainModify(0.25)`, `mods/gen4/conditions.ts:7-21` | — | Quick Feet |
| burn | maxhp/16, halves Atk destructively, `mods/gen1/conditions.ts:12-29` | maxhp/8, halves physical damage, `mods/gen6/conditions.ts:4-6` + `mods/gen4/scripts.ts:65-67` | — | Guts, Will-O-Wisp (21 sets) |
| toxic | shared counter, multiplies Leech Seed, `mods/gen1/moves.ts:450-457` | own `stage`, resets on switch, `data/conditions.ts` tox | toxic stage counter | Toxic on **132** sets — the single most common move |
| Substitute | `floor(maxhp/4)+1`, hardcoded block list | `floor(maxhp/4)`, `bypasssub` flag, `mods/gen4/moves.ts:1280-1316` | **sub HP**, not just a flag | Sub+Protect, Sub+Leech Seed, Sub+Focus Punch |
| Protect | absent | +3, 1/8 floor, `mods/gen4/moves.ts:1026-1044` + `mods/gen4/conditions.ts:134-139` | consecutive-protect counter | 45 sets; stall loops are real |
| hazards | absent | Spikes 1/8–1/4, Toxic Spikes psn/tox, `mods/gen4/moves.ts:1240-1252, 1419-1439` | per-side layer counts | 28 hazard sets vs 13 Rapid Spin sets |
| screens | per-mon volatiles, `mods/gen1/scripts.ts:869-873` | 5/8-turn **side conditions**, `mods/gen4/moves.ts:1103-1119` | **move REFLECT out of `volatiles` into a side block** | moot in the pool (no screen sets) |
| weather | absent | 4 weathers, **indefinite from abilities**, `data/conditions.ts` + `mods/gen4/conditions.ts:140-155` | weather one-hot + turns (with "permanent") | 8 weather-setting ability sets |
| Trick Room | absent | −7 priority, `mods/gen4/scripts.ts:6-14` | field flag + turns | 1 set, but it inverts every speed comparison |
| priority | Quick Attack only | 11 distinct +1 moves + brackets to −7, `gen4_moves_merge.js priority` | per-move priority (already present) | Sucker Punch 31, Extreme Speed 16, U-turn 54, Pursuit 16 |
| PP / Pressure | no abilities | Pressure = 2 PP, `data/abilities.ts` pressure | pp scalar (present) | 32 Pressure sets |
| clauses | Standard: EBC + Freeze + Species + OHKO + Evasion, `mods/gen1/rulesets.ts:8-16` | only Sleep Clause Mod, `config/formats.ts:4243` | — | **no Endless Battle Clause**; turn-1000 auto-tie, `sim/battle.ts:1836-1839` |
| items / abilities | none | ~101 abilities, full item set | **two new per-mon blocks** | Levitate 40, Trick 21, Choice items |

---

## 17. gen1 encoder assumptions this breaks

Read against `SNAP/rl/envs/encoder_spec.py` (main@2738025). The docstring at
`:45-80` already lists most of these; below is what my reading of the sim
**confirms**, what it **adds**, and where I think the docstring is **wrong or
incomplete**.

**Confirmed by the sim:**
1. `types` must be 17, and **Fairy must be excluded explicitly** — poke-env's
   `gen4typechart.json` carries an 18th `fairy` key marked `isNonstandard: 'Future'`
   (source-verified), so building the tuple from `PokemonType` or from the JSON's
   keys silently gives 18.
2. `base_stat_keys` must gain `spd` (`:224` drops it deliberately for gen1's single
   Special stat). This is a MON_DIM change → OBS_DIM change → every checkpoint
   invalidated (the landmine in CLAUDE.md).
3. Items and abilities need new per-mon blocks (`:53-55`). The sim confirms these
   are not optional decoration: 68 randbats sets carry a **type-immunity** ability.
4. Weather and side conditions need new global blocks (`:56-61`), and the
   docstring's parenthetical about Reflect/Light Screen moving out of `volatiles`
   into a side block is **exactly right** — I verified the gen1 sim emits them as
   per-mon volatiles (`mods/gen1/scripts.ts:869-873`) and gen4 as
   `sideCondition`s (`mods/gen4/moves.ts:1103-1119`).
5. `statuses` stays the same six (`:62-63`) — correct, gen4 adds no major status.
6. Species range 1..493, move range 1..467 (`:67-68`) — consistent with Shadow
   Force being `num: 467` in the merged gen4 table (tree-verified) and Arceus
   being the last gen4 species.
7. `n_actions` stays 10 (`:76-80`) — `SinglesEnv.get_action_space_size(4)` with no
   gimmicks. Not re-verified against poke-env source in this pass.

**Added by my reading (not in the docstring):**
8. **`volatiles` is not just "grows"** — it must gain, at minimum, entries whose
   *state* is more than a bit:
   - **Substitute HP** (0–25 % of max), because Sub is a resource in gen4;
   - **the Protect/Detect consecutive counter** (`stall`), because the gen4 floor
     is 1/8 and a policy that cannot see the counter cannot value a 4th Protect;
   - **Encore / Taunt / Yawn / partial-trap remaining turns**, whose gen4 ranges
     (4–8, 3–5, 2, 3–6) are all wider than base;
   - **Roost**, which is a *one-turn type override* on the active mon and will
     silently desync the type one-hot on **45 of 464 randbats sets** unless the
     encoder reads the live type list rather than the species.
9. **Level must stay a live feature and its range changes**: gen4 randbats levels
   run 67–100 (tree-verified from `sets.json`), a wider spread than gen1's.
10. **The `active_counter_off` block (2 slots: status counter + preparing)** is too
    small. gen4 needs at least: sleep turns, toxic stage, confusion turns,
    protect counter, lockedmove turns, charging-move id. The `preparing` slot
    exists but there are **no** two-turn charge moves in the gen4 randbats pool
    except Solar Beam (3 sets), so it is nearly dead weight — the *counter* slots
    are where the budget should go.
11. **`special_move_ids`** (`:244` = `{"fight","struggle","recharge"}`) needs
    re-deriving: gen4's `SPECIAL_MOVES` set in poke-env is a different set
    (not checked in this pass — flagged for the poke-env survey agent).
12. **The randbats prior** (`:69-70`, `rl/envs/randbats_prior.py`) must be rebuilt
    from `SD/data/random-battles/gen4/sets.json`, whose shape is
    `{species: {level, sets: [{role, movepool, abilities, preferredTypes?}]}}`
    (tree-verified) — a **different schema** from gen1's `data.json`. The prior is
    also much stronger in gen4: 295 species × ≤ 3 sets, movepool + ability list per
    role, so an opponent-move-slot prior can condition on the revealed ability.
13. **The move universe is 181, not 467.** An embedding table sized 1..467 is
    correct for safety but ~62 % of its rows will never be seen in randbats.

---

## 18. Open questions for the maintainer

1. **Stealth Rock is absent from every gen4 randbats set in this vendored build.**
   Do we (a) take the vendored build as the spec and drop SR from the encoder's
   side block, (b) carry the slot anyway for robustness against a PS upgrade, or
   (c) pin the PS commit in the pre-reg so the pool is frozen? I recommend (b)+(c):
   the slot is one float and a PS bump is the kind of silent change that has cost
   us before.
2. **No Endless Battle Clause in gen4 randbats, and a turn-1000 auto-tie.**
   Our gen1 reward/eval treats ties as non-wins (locked protocol). Does the
   1000-turn cap need an explicit episode-truncation policy, and does the
   `max_turns` in our env config need to move? A gen4 stall war (Protect floor 1/8,
   Toxic on 132 sets, Levitate 40, Wish 19) can plausibly reach it.
3. **`spd` in `base_stat_keys` invalidates every checkpoint.** Confirmed
   unavoidable. Do we want the gen4 spec to be a clean break (new OBS_DIM, no
   attempt at gen1 transfer), or is there appetite for a padded layout that keeps
   gen1 checkpoints loadable?
4. **Roost's one-turn type override** — should the type one-hot be read from
   `mon.types` (live) rather than the species? That is a behavioural change to the
   gen1 encoder too (harmless there: nothing changes type in gen1 randbats except
   Conversion, which is not in the pool). Cheap, but it perturbs the tape hash gate.
5. **Substitute HP as a scalar vs a flag.** Adds one float to ACTIVE_DIM. Given
   Sub is on 44 sets and gen4 Subs break to specific damage numbers, I think it
   earns the slot; the losing argument is that the policy can infer it from the
   `|-activate|...|Substitute|[damage]` message history, which the encoder does not
   carry.
6. **Do we want an "indefinite weather" sentinel?** Ability-set weather never
   expires in gen4 (`this.gen <= 5` branch). Encoding turns-remaining as 0 for
   "permanent" collides with "just expired"; I'd use a separate flag.

---

## 19. Unread / unverified

- **"Hyper Beam does not require a recharge if the target faints" (gen1).** I
  searched `mods/gen1/scripts.ts` and `mods/gen1/moves.ts` and could **not**
  locate the code path. `mods/gen1/scripts.ts:712-714` gates self-effects on
  Substitute, not on fainting. **Status: literature-only, and I am not citing a
  file for it.** The check would be: run a gen1 battle where Hyper Beam KOs and
  confirm no `|-mustrecharge|` line — **needs-live-verification**, barred.
- **Rage** in gen4: I did not read the gen4/base `rage` implementation. Not in the
  gen4 randbats pool.
- **`SPECIAL_MOVES` for gen4 in poke-env**: not checked. Flagged for the
  poke-env survey agent; `encoder_spec.py:244` will need a gen4 value.
- **`SinglesEnv.get_action_space_size(4)`**: taken from the docstring
  (`encoder_spec.py:76-80`), not re-read from poke-env source in this pass.
- **Ability and item mechanics in depth**: deliberately out of scope. I named the
  hooks (Levitate/Wonder Guard/Magic Guard type & damage immunities, Pressure PP,
  Sand Veil/Snow Cloak evasion, Drizzle/Drought/Sand Stream/Snow Warning
  indefinite weather, Air Lock/Cloud Nine suppression, Guts/Quick Feet/Early Bird
  status interactions, Light Clay 8-turn screens, Grip Claw 6-turn trap, Choice
  items + `choicelock`, Life Orb/Expert Belt on the final `ModifyDamage`, Trick
  target items). The abilities/items agent owns the rest.
- **gen4 `formats-data.ts` and learnsets**: not read; legality of a move on a
  species is the randbats agent's problem since randbats draws from `sets.json`.
- **gen2 and gen3 mod files** beyond `gen3/scripts.ts:1-30`: not read. They are in
  gen1's inherit chain, not gen4's, so they only affect the gen1 column of the
  delta table where I cited gen1 files directly.
- **Whether `dist/` is byte-consistent with `data/` for every file I parsed.** I
  spot-checked `mods/gen4/moves.js` (thrash 90/20, disable acc 80) and the mtimes
  (both Sep 4). If a downstream doc quotes a number that came only from
  `gen4_moves_merge.js`, it should be re-grepped in the `.ts`.
- **poke-env's gen4 move JSON** (`PE/data/static/moves/gen4moves.json`): present on
  disk, not parsed. That is the poke-env survey agent's file; it is the one that
  determines what `move.category`, `move.priority` and `move.crit_ratio` our
  encoder will actually see.

---

## 20. Cross-references for the other docs

- **`pokeenv_gen4_survey.md`**: (a) `PE/data/static/typechart/gen4typechart.json`
  matches the vendored sim on every cell I checked, but it **drops the lowercase
  status/weather keys** (`sandstorm`, `hail`, `psn`, `frz`, `brn`), so poke-env's
  typechart alone cannot answer "is this mon immune to sand chip". (b) It carries
  an 18th `fairy` entry marked `'Future'`. (c) gen4 randbats will emit
  `|-sidestart|`/`|-sideend|` for Spikes and Toxic Spikes, `|-weather|` with
  `[from] ability:` and **no upkeep expiry** for ability weather, `|-fieldstart|`
  for Trick Room, and `|-singleturn| move: Roost` — check poke-env 0.15.0 parses
  each. (d) `Effect` members needed: SUBSTITUTE, LEECH_SEED, CONFUSION,
  TAUNT, ENCORE, YAWN, CURSE, PROTECT, DESTINY_BOND, PARTIALLY_TRAPPED,
  MUST_RECHARGE, ROOST, PERISH*, plus the `substitutebroken` gen4 volatile.
- **`encoder_requirements.md`**: §17 is written to be lifted directly. The three
  hard ones are `spd` (OBS_DIM break), the item/ability blocks, and Roost's live
  type override.
- **`anchors_and_eval.md`**: `SimpleHeuristicsPlayer` in gen4 will have to reason
  about items, abilities, hazards, Sucker Punch and U-turn — none of which it
  models. Expect it to be a much weaker anchor in gen4 than in gen1. Also: the
  **turn-1000 auto-tie with no Endless Battle Clause** means a gen4 eval protocol
  needs an explicit tie rule and a per-battle turn budget, and the `/timer on`
  landmine's 150 s/turn ladder path gets more expensive with longer games.
- **`open_questions.md`**: §18.
- **`search_depreciation.md`**: gen4's branching factor is materially larger than
  gen1's — 4 moves + 5 switches is the same, but the *state* a search must model
  now includes items, abilities, hazards, weather, screens, and a 1/8-floored
  Protect counter. Foul Play's gen4 support (if any) should be checked against
  this list.

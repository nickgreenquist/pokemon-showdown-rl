# critic_pass.md — the completeness-critic pass the gen4 design cycle could not afford (open_questions D6 / §8)

> **design_gen4 status header.** Written 2026-09-04 in the worktree
> `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-gen4` on branch
> `gen4-build` (at main's HEAD 62242bd), DOCS ONLY — nothing under `rl/`,
> `scripts/`, `configs/` or `tests/` changed, and no file outside
> `docs/design_gen4/research/` was written. **Arc position:** the target is
> JOURNEY step 3 (gen4 encoder + model). This is **maintainer-ruled PREPARATION
> running AHEAD of step 2 (gen1 ladder #3)**, written while a rated ladder run is
> live from the main tree; it is not a pre-registration and it launches nothing.
> **No server was started, no battle was played, no process was signalled, and
> nothing was installed.** Every command run was read-only under `nice -n 19`.
> **Verification status per claim** — every claim carries exactly one tag:
> - `[tree]` **tree-verified** — re-derived by me from a file in this worktree:
>   the FRESH `showdown/` clone at 59da482 (`.ts` sources, not `dist/`), `rl/`,
>   `tests/`, `docs/`.
> - `[src]` **source-verified** — re-derived by me from the installed poke-env
>   0.15.0 at
>   `/opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env/`.
> - `[lit]` **literature-only** — not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running gen4 server can
>   confirm it; the exact check is §4.
> **Sources read for this doc:** `DOC_CONVENTIONS.md`, `HEADER_TEMPLATE.md`,
> `research/README.md`, and all five docs in `docs/design_gen4/` in full; the
> vendored `showdown/` `.ts` sources; installed poke-env 0.15.0.
> **Feeds:** the orchestrator's revision of the five docs (§5 is the work list).
> **Reconcile at merge:** nothing here designs against an unlanded interface.

**Counts.** 131 citations checked: **111 verified**, **20 wrong or materially
drifted** (§1B). Zero fabricated citations were found — every path exists and
every cited construct is real; the defects are line drift, three substantive
misreadings, and five numbers that do not reproduce.

**One correction to the brief** `[tree]`: the fresh clone **does** carry
`showdown/dist/data/**/*.js` (built 6 min after the `.ts` mtimes). I ignored it
and re-derived every merged-table number from the `.ts` anyway, which is what
`mechanics_delta.md` §17 asked for.

---

## 1. Citation verdicts

### 1A. Verified (111)

`[tree]` **`showdown/` — merged tables re-derived from `.ts` (the §17
"dist-only" concern, now closed).** I parsed `data/moves.ts` and applied the
mod chain base → gen8 → gen7 → gen6 → gen5 → gen4 (confirmed by
`mods/gen{5,6,7}/scripts.ts:2` and `mods/gen8/scripts.ts` having no `inherit`,
plus `mods/gen4/scripts.ts:2` `inherit: 'gen5'`):

- **the 97-move category delta (`mechanics_delta` §3) reproduces EXACTLY** —
  48 Physical-but-Special-by-type and 49 Special-but-Physical-by-type (the
  second list counting each of the 9 mismatching `hiddenpower*` rows), total 97,
  and my name lists are identical to the doc's. `mods/gen3/scripts.ts:4-14`
  (`specialTypes` = Fire/Water/Grass/Ice/Electric/Dark/Psychic/Dragon) verified
  verbatim.
- **the priority census (§10) reproduces EXACTLY**: +5 helpinghand; +4 endure,
  magiccoat, snatch; +3 detect, followme, protect; +2 feint; +1 the eleven
  named; −1 vitalthrow; −3 focuspunch; −4 avalanche, revenge; −5 counter,
  mirrorcoat; −6 roar, whirlwind; −7 trickroom.
- **the high-crit list (§2) reproduces EXACTLY**: `critRatio: 2` over gen4-legal
  standard moves = 19, being the 9 in-pool + the 10 out-of-pool the doc names.

`[tree]` **`showdown/` — pinpoint citations verified at the cited line.**
`sim/battle.ts:1833-1849` and `:1836-1839` (turn≤100 skip, `turn > 1000` tie,
warnings from 500); `:2384-2386` `getCategory`; `:2388-2391` `randomizer`
(16 rolls, 85–100 %); `:2113` weather immunity via `runStatusImmunity`;
`:404-411` `comparePriority`; `:437-458` speed-tie `prng.shuffle`; `:1056`
`alliesAndSelf()` runs `onAlly*` for self. `sim/battle-actions.ts:1622-1644`
critMult `[0,16,8,4,3,2]` for gen≤5; `:1682-1691` crit ignores negative
offensive / positive defensive boosts; `:892` Sleep-Talk'd multi-hit breaks at
gen 4. `sim/battle-queue.ts:173-199` orders (beforeTurnMove 5, runSwitch 101,
switch 103, moves 200, residual 300). `sim/dex.ts:676-695` the inherit/merge
rule (shallow `{...parent, ...child}` **only** when `inherit` is set);
`:380-383` Hidden Power variable BP for gen<6. `sim/dex-moves.ts:479`
`placeholderFor`; `:486` `critRatio || 1`. `sim/pokemon.ts:342` happiness→255;
`:894-906` `deductPP`; `:996-998` `"Hidden Power Fire 70"`; `:1105-1112` the
gen1-only `Fight` placeholder; `:1126-1133` `maybeDisabled`/`maybeLocked`;
`:1143-1194` gimmick request keys + switch-request shape; `:1165-1183` five
`stats` keys + `baseAbility` + `item`; `:1186` live `ability` is gen>6.
`sim/side.ts:527-537` and `:984-1000` the trapped-switch rejection path.
`config/formats.ts:4238-4244` gen4 RB ruleset and `:4260-4265` gen1's
`['Standard']`. `data/rulesets.ts:1378-1400` Sleep Clause Mod; base
`standardag` (`:11-18`) carries Team Preview and `mods/gen4/rulesets.ts:2-7`
drops it; `mods/gen1/rulesets.ts:8-16` + `:15` banlist.

`[tree]` **gen4 mod files.** `mods/gen4/conditions.ts:22-53` slp (no
`inherit`), `:32` `random(2,6)`, `:40-42` Early Bird, `:44-47` wake-and-act;
`:16` para 25 %, `:9-14` `chainModify(0.25)`; `:74-76` confusion 50 % and
`:77-83` the 40-BP pipeline; `:87-98` freeze 20 %; `:134-139` `stall`
`counterMax: 8`. `mods/gen5/conditions.ts:2-7` the `onSwitchIn` sleep reset
gen4 does NOT inherit — **the headline "sleep does not reset on switch" claim is
CORRECT and its two citations are exact.** `mods/gen4/scripts.ts:2, 6-14
(getActionSpeed/Trick Room), 18-21 (EntryHazard before SwitchIn), 57-137
(modifyDamage), 65-67, 70, 82, 84-87, 100-107, 109-125, 130, 132-134, 138-147,
148-204, 154-162, 164-187, 188, 195, 205-220` (`struggleRecoil =
floor(baseMaxhp/4)` at :207). `mods/gen4/moves.ts:293-296` detect +3 and
`:1026-1044` **protect priority 3** at :1028; `:434-437` **fakeout priority 1**
at :436; `:401-404` Encore `random(4,9)`; `:1381-1383` Taunt `random(3,6)`;
`:1270-1279` Struggle `type = '???'`; `:1318-1326` Sucker Punch's Status-fail;
`:430-433` Extreme Speed +1; entry starts verified for spikes 1240,
stealthrock 1257, substitute 1280, toxicspikes 1419, reflect 1103,
lightscreen 731, knockoff 706, leechseed 723, roar 1143, haze 600,
rapidspin 1080, pursuit 1049, wish 1492, yawn 1524, curse 268.
`mods/gen4/abilities.ts:2-8`, `:37-43`, `:452-456` (airlock / cloudnine /
sturdy announcements nulled), `:245-249` + `:447-451` (Lightning Rod / Storm
Drain lose `onTryHit`), `:270-280` + `:325-335` (Minus/Plus), `:222` Intimidate.

`[tree]` **the ability-announce list is EXACTLY right.** I enumerated every
`this.add('-ability', …)` in `data/abilities.ts`: the gen4-legal self-announcers
are airlock (:93, in `onSwitchIn`), anticipation, cloudnine, intimidate,
moldbreaker, pressure, sturdy (:4675, in `onDamage`); gen4 nulls exactly
`onSwitchIn` for airlock/cloudnine and `onDamage` for sturdy, leaving
**Anticipation, Intimidate, Mold Breaker, Pressure**. Sturdy's OHKO branch
(`:4666-4671`) emits `-immune … [from] ability: Sturdy`, matching the doc's
second reveal class. `data/abilities.ts:196-203` Arena Trap
`onFoeMaybeTrapPokemon`, 2506 Magnet Pull, 4146 Shadow Tag, 1331 Flash Fire.

`[tree]` **type chart, re-derived with the correct shallow-replace semantics.**
gen4 live types = the 17 the encoder spec lists, alphabetical, exact; gen1 = 15
(`mods/gen1/typechart.ts:129-136` Dark/Steel `'Future'`). **All four cells
verified**: Ghost→Psychic 0×→2×, Bug→Poison 2×→0.5×, Poison→Bug 2×→1×,
Ice→Fire 1×→0.5×, with the gen1 rows at `:110-127, :89-108, :10-27, :29-46`.
Dark and Steel defensive/offensive descriptions verified cell by cell.
`mods/gen5/typechart.ts:24-45` (ghost, **no `trapped: 3`**), `:46-67` (grass,
**no `powder: 3`**), `:68-91` (steel resists Ghost/Dark), `:93-96` (fairy
`'Future'`) — all exact. Non-type keys Fire `brn`, Ice `hail`/`frz`,
Ground/Rock/Steel `sandstorm`, Poison/Steel `psn`/`tox` verified.

`[tree]` **the pool, re-derived with my own script over `sets.json` and
`teams.ts`.** **295 species / 464 sets / 181 distinct moves / 101 distinct
abilities / 8 roles / levels 67–100 with modes 69 and 83 at 19 species each —
all EXACT.** **267 distinct dex nums** (295 − 28 shared) and **34 species over
six shared nums** (Arceus 17→493, Rotom 6→479, Deoxys 4→386, Wormadam 3→413,
Giratina 2→487, Shaymin 2→492) — EXACT, and it confirms `research/README.md`
correction #2. **Stealth Rock on 0 sets** — EXACT. All 21 top-move counts
(toxic 132 … suckerpunch 31) and every one of ~60 other move counts I spot-tested
(pursuit 16, encore 24, taunt 13, wish 19, trick 21, knockoff 3, rapidspin 13,
explosion 37, selfdestruct 3, spikes 14, toxicspikes 14, raindance 10,
sunnyday 3, trickroom 1, willowisp 21, extremespeed 16, sleeptalk 25, rest 35,
solarbeam 3, gigaimpact 1, hyperbeam 0, plus every "unreachable" move at 0) —
**zero mismatches**. All 14 top-ability counts EXACT; Sand Veil 6, Snow Cloak 4,
Drizzle 2, Drought 2, Sand Stream 3, Snow Warning 1, Air Lock 3, Cloud Nine 1,
Forecast 1, Flower Gift 2, Early Bird 4, Quick Feet 1, Cute Charm 7,
Adaptability 1 — EXACT. `maybeTrapped` sources = 5 set entries — EXACT. Only
8 typed Hidden Powers occur (electric, fighting, fire, flying, grass, ground,
ice, rock) — EXACT, so the 182-move vocab (181 + Struggle, which is on no
movepool) is right.

`[tree]` **items: the 40 reproduces.** `teams.ts:521` `species.requiredItems`
covers exactly **17 pool species** — 16 Arceus formes and Giratina-Origin — and
the mod chain makes those single-valued and gen4-correct
(`mods/gen6/pokedex.ts:187+` gives each Arceus forme one plate, not the
plate-or-Z pair; `mods/gen8/pokedex.ts:38-41` sets Giratina-Origin's
`requiredItem: "Griseous Orb"`). The by-rule literals in
`getPriorityItem` (:510-552) and `getItem` (:554-625) are **22**, plus Black
Sludge from `randomSet:669-671` = **23**. 17 + 23 = **40 — EXACT**, and
"gen4 overrides both with no `super`" and "Dialga has no Adamant Orb branch
(Palkia has Lustrous Orb, :596)" are both right.

`[tree]` **EV/IV/level rules.** `teams.ts:648` EVs 85 ×6 (=510), `:649` IVs 31,
`:725-738` **no `nature` key emitted**, `:696-708` HP-parity for
Sitrus+Substitute / Belly Drum, `:711-713` `evs.atk = 0`, `:716-718`
`evs.spe = 0`, `ivs −28` on HP sets, `:682-693` canonical `HPivs`, `:636-641`
movepool-only draw. `sim/pokemon.ts:1172-1175` sends `hiddenpowerfire` with no
power suffix at gen<6 — exact. `data/moves.ts:14981` Rest `time = 3`;
`data/moves.ts:4970` Explosion BP 250 vs `mods/gen1/moves.ts:305` BP 170.

`[src]` **poke-env 0.15.0 (46 citations).** All verified at the cited line
unless noted in §1B: `singles_env.py:290-304` (`6 + 4*(gimmicks+1)`, 0 for
gen≤5), `:83-91`, `:109-112`, `:122-143` (re-base iff `len(avail)==1 and
avail[0] not in known_ids`), `:144`, `:182-185`, `:195-198` (`base_species`
match), `:232-288` (mask; `maybe_trapped` never read), `:233-240`.
`battle.py:130-131` parses `maybeTrapped`, `:242-248` exposes it, `:275-282`
`valid_orders` reads only `trapped`. `abstract_battle.py:726-741` — **the
Sleep-Talk double `moved()` is real**: the `elif` at :730-737 fires on the
Sleep Talk line and the `if` at :726-729 fires on the `overridden_move` line;
`pokemon.py:482-483` bumps SLP unconditionally in `moved()`, so the counter
advances by 2. Also `:742-744` (`cant` reason dropped), `:781-793` Trace,
`:827-894` `-activate` records an Effect not the ability, `:889-892` Trick swap,
`:437-448` `field_start` genuine stamp, `:548-563` `is_grounded` treats a
possible Levitate as Levitate, `:565-566` `_replay_data` unconditional,
`:1238-1247` layers-vs-stamp, `:1287-1319` team in request order, `:1162-1168`
`-immune [from] ability:` does set `.ability`. `pokemon.py:114` `unknown_item`
born state, `:189-195` `cant_move` bump, `:261-306` `check_move_consistency`
asserts exact PP for gen 4 (`gen not in [1,2,3,7,8]`), `:405-410` `end_item →
None`, `:412-415` toxic bump, `:477-480` protect counter, `:498-503`
**Flash Fire ended after one Fire move**, `:534-541` no counter reset on Rest,
`:607`/`:613-615` switch-out resets, `:657-662` **single-dex-ability auto-set at
gen≥3**, `:809-811` disabled dropped, `:842-858` `damage_multiplier` is
ability-blind, `:1108-1112` item setter (no `_orig_item` anywhere),
`:1160-1178`, `:1302-1308` "only TOXIC and SLEEP". `move.py:104-112` the
digit-strip override is **Hidden-Power-only** so `Return` BP is 0, `:123-130`
`use(pressure, overridden)`, `:209-215` by-type category gated `gen<=3`,
`:321-342` `expected_hits` = 3.1667, `:561-576` `retrieve_id` collapses
`return102 → return`, `:673-680` `Move.target` returns a `Target` enum.
`gen_data.py:14`, `:73-109` (no `isNonstandard` filter; non-type keys are
dropped by the `:88-89` skip), `:121-124` `int(format[3])`. `effect.py:243-271`
UNKNOWN fallback. `side_condition.py:95` `{SPIKES:3, TOXIC_SPIKES:2}`.
`env.py:175`, `:273/292/355/375` `max_concurrent_battles=1`, `:317-333` mask
wrap. `player.py:191`, `:230-231` `/timer on`, `:318-325` `_trying_again`,
`:705-709`. `utils.py:137-140` asserts **gen8**. `ps_client.py:328-332`
`/utm null`. `single_agent_wrapper.py:52-55`. Static data: `gen4moves.json`
486 entries, 192/124/170 P/S/Status, priority −7..+5 over 12 values,
`thawsTarget` on zero, Return BP 0, all 17 `hiddenpower*` at num 237;
`gen4typechart.json` **18 keys with `fairy`**; `gen4pokedex.json` no `"H"` slot.
`baselines.py:134-139` the `"stealhrock"` typo, `:147-163` `_estimate_matchup`,
`:249-256` `_stat_estimation` (**+1 scores 2.0 = the +2 value — confirms
open_questions Q43's direction**), `:286-303` hazard set/remove, `:322-340` the
move score, `:354` the unguarded switch branch.

`[tree]` **`rl/` line numbers have NOT shifted** between main@2738025 and this
worktree at 62242bd for everything I spot-checked: `encoder_spec.py:224`
`base_stat_keys=("hp","atk","def","spa","spe")`, `:267-276` refusal list (first
string at :268), `:149` `mon_status_off = 3`, `:208` `GEN1`, `:254`
`spec_for_format`; `showdown.py:61-64` `OPPONENT_PLAYERS`, `:234`
`status_counter / 16.0`, `:258-259` `move.category`, `:260` `priority / 5.0`,
`:288-295` the `spec is not GEN1` refusal; `tests/test_showdown_env.py:411`
asserts the registry key list; `JOURNEY.md:15-19`, `:68`, `:116`;
`IDEAS_POST_100M.md:114-115` ("12M per-lane search deltas +0.051/+0.104/+0.148");
`scripts/make_bc_dataset.py:11` "611-dim"; `docs/proposals/F07…§7` has exactly
**8** numbered rulings.

### 1B. Wrong or materially drifted (20)

| # | citation | doc § | status | correct reading |
|---|---|---|---|---|
| W1 | `showdown/data/mods/gen4/moves.ts:1164` (Light Screen ignores crits) | mechanics §2 | **wrong** `[tree]` | :1164 is `scaryface`. Light Screen's crit bypass is `:736`, entry `:731-748` — which mechanics §8's own table cites correctly. |
| W2 | `showdown/sim/battle-actions.ts:1706-1708` (Explosion halves Def for gen≤4) | mechanics §7 | **wrong** `[tree]` | The `gen <= 4 && ['explosion','selfdestruct']` halving is `:1711-1713`; :1706-1708 is the stat-modifier block. |
| W3 | `showdown/sim/battle-actions.ts:1712-1717` (base damage formula) | mechanics §2 | **wrong** `[tree]` | The formula line is `:1718`; the comment is `:1717`. Cite `:1715-1718`. |
| W4 | `showdown/data/mods/gen4/scripts.ts:51` "sets `substitutebroken` on break" | mechanics §7 | **wrong reading** `[tree]` | `:49-53` **removes** `substitutebroken` from every foe inside `runSwitch`, i.e. it is cleared when the opponent switches in. The volatile is declared at `mods/gen4/conditions.ts:99`. |
| W5 | "+1 moves sit on **77 of 464** pool sets (**eight** distinct ones)" | mechanics §10 | **does not reproduce** `[tree]` | **95 sets**, **ten** distinct: aquajet 8, bulletpunch 7, extremespeed 16, fakeout 8, iceshard 7, machpunch 5, quickattack 9, shadowsneak 9, suckerpunch 31, vacuumwave 1. |
| W6 | `poke_env/player/baselines.py:317` (dead `move.target == "self"`) | survey §7 **and** anchors §1 | **wrong line, right claim** `[src]` | The comparison is `:314`. It is genuinely dead: `Move.target` returns `Optional[Target]` (`move.py:673-680`). |
| W7 | `poke_env/battle/abstract_battle.py:1148-1200` (`-item` 6-field crash) | survey G12 | **wrong** `[src]` | `-enditem` is `:934`, `-item` is `:949`. `:1148-1200` is `replace`/`-immune`/`-terastallize` ending in `raise NotImplementedError` — a different failure mode from the claimed `ValueError`. |
| W8 | `poke_env/battle/abstract_battle.py:1193-1199` (item reveal) | survey §3.1 | **wrong** `[src]` | That is `parse_request` / `_pressure_on`. The item-reveal branches are `:934` and `:949`; the Trick branch `:889-892` is right. |
| W9 | "`status_counter ∈ {0..3}` … P(wake on the next attempt) = 1/(4 − counter)" | survey §3.5 | **wrong** `[tree]` | `time = random(2,6) ∈ {2,3,4,5}`, decremented once per attempt, wake when `<= 0`, so counter reaches **4**: `{0..4}`. P(wake next \| counter c) = **1/(5 − c)** for c ≥ 1 and **0** at c = 0 (a mon always loses at least one turn). |
| W10 | "Sleep Clause Mod is on … so at most one opponent mon is asleep at a time" | survey §3.5 | **wrong** `[tree]` | `data/rulesets.ts:1386-1398` returns early when `source.isAlly(target)` and skips ally-sourced sleepers, so **Rest is exempt**: a Rest user and an opponent-slept mon are simultaneously legal. Rest is on **35** sets. |
| W11 | "**Six** pool species carry Flash Fire" | survey §3.6, encoder §3.2 | **wrong** `[tree]` | **5 species** (flareon, heatran, houndoom, ninetales, rapidash) over 8 sets. |
| W12 | "**277** of 295 species have a unique set-listed ability" (→ "94 %") | mechanics §11, survey §3.2, encoder §3.5 | **off by one** `[tree]` | **278** of 295 (94.2 %). |
| W13 | "type-immunity abilities total **≈ 68** sets" | mechanics §0, §11 | **off by one** `[tree]` | **69** over the seven named (Levitate 40, Water Absorb 13, Flash Fire 8, Volt Absorb 3, Dry Skin 3, Motor Drive 1, Wonder Guard 1). |
| W14 | "**Two** poke-env traps" followed by three numbered items | mechanics §4 | **internal** `[tree]` | Say "three". |
| W15 | `mods/gen4/conditions.ts:135-141` (Protect 1/8 floor) | mechanics §11 | **drift** `[tree]` | The `stall` block is `:134-139`; :140-141 is `raindance`. mechanics §7 cites it correctly. |
| W16 | `poke_env/battle/abstract_battle.py:754-761` (`-weather` stamp) | survey §4, G2 | **off by one** `[src]` | The branch is `:755-761`; :754 is the `-boost` body. The claim itself is exact. |
| W17 | OBS_DIM "≈ **1,180**" | encoder §0 | **internal** `[tree]` | §4.7 computes **≈ 1,376** with §4's widths and **≈ 1,183** for the leaner sketch. 1,180 is neither. |
| W18 | volatiles "~**16** flags" | encoder §0 | **internal** `[tree]` | §3.2's table has **18** flag rows; §4.2 says "~17". |
| W19 | `SimpleHeuristicsPlayer` extent `:133-360` / `:133-368` | survey §7 / anchors §1 | **inconsistent, both short** `[src]` | The class runs `:133` to end-of-file (443); `choose_move` is at `:390`. |
| W20 | `git -C …/pokemon-showdown-rl-gen4design rebase main`; branch `gen4-design` | open_questions M1 + all five headers | **stale** `[tree]` | This worktree is `…/pokemon-showdown-rl-gen4` on branch **`gen4-build`**, already at main's HEAD (62242bd), so M1's rebase is a no-op at that path and the command's path does not exist. |

**Line drift too small to list individually** `[tree]`: `mechanics_delta` §5's
`teams.ts` ranges are each 1–3 lines off (`:709-713`→`:711-713`,
`:715-718`→`:716-718`, `:697-707`→`:696-708`, `:679-695`→`:682-693`); §2's
`battle-actions.ts:1673-1675` ends one line short of `defenseStat` (:1676);
survey §3.3's `pokemon.py:121-128` is `:123-130`. One partial: `sim/dex.ts:
283-289` shows the 1→super-effective / 2→resist mapping but **not** 3→immune
(the comment at :287 says immunity is handled elsewhere).

---

## 2. Cross-doc inconsistencies

1. **Light Screen's crit bypass** — mechanics §2 cites `moves.ts:1164`, §8's
   table cites `:731-748`. §8 is right (W1).
2. **Protect's stall block** — mechanics §7 `:134-139` vs §11 `:135-141`. §7 is
   right (W15).
3. **Flash Fire pool dose** — survey §3.6 and encoder §3.2 both say "6 species";
   the truth is 5 species / 8 sets (W11). Neither doc is right.
4. **Unique-ability count** — 277 in three docs; 278 is correct (W12). It also
   changes encoder §3.5's "94 %" only in the second decimal.
5. **SH class extent** — survey `:133-360`, anchors `:133-368` (W19).
6. **SH `ENTRY_HAZARDS` line** — survey `:134-139`, anchors `:134-141`. Survey is
   right; :140-141 is `ANTI_HAZARDS_MOVES`.
7. **OBS_DIM** — encoder §0 "≈ 1,180" vs §4.7 "≈ 1,376 / ≈ 1,183" (W17). Any
   quote of §0's number outside the doc will be wrong twice over.
8. **Volatile-flag count** — encoder §0 "~16", §4.2 "~17", §3.2 table 18 (W18).
9. **Item vocab rows** — encoder §0 says "items 40"; §3.4 says "40 + row 0
   unknown + a `none` row" (= 42 rows). open_questions M2 repeats "40". State
   the row count once.
10. **Branch name** — all five headers say `gen4-design`; the live worktree is
    `gen4-build` (W20). open_questions M1's path is a third variant.
11. **`maybe_trapped` ruling location** — survey §10.4 raises the *species key*
    (forme id vs `num`) as a poke-env ruling; open_questions files it as **Q9**
    under encoder rulings. Correct call, but §3's header claims to collect
    survey §10 and silently drops one of its nine.
12. **DOC_CONVENTIONS rule 10 says open_questions collects the other docs'
    ruling lines "verbatim (same wording, one place)". None of the 46 Q-items is
    verbatim** — all are recompressed, and some lose a live argument (e.g. Q26
    drops survey §10.1's "a fork is where Wang put 36 fixes and upstream has
    since absorbed most of them"). Either the convention or the practice should
    change; right now the doc set violates its own binding rule.
13. **Three adjudications never reach open_questions**: encoder §10 **A4**
    (unknown-ability prior + the `-activate`-only six), **A5** (ability-aware
    matchup scalars — 2 extra dims per mon and a mechanic baked into a feature),
    **A14** (`priority_scale = 7.0` vs widening the Box). Each has a stated
    losing argument, none is escalated by §11 or by open_questions §2. A5 and
    A14 change the vector; they should be Q-items.
14. **Q32** (the `Return` BP-102 override) is in open_questions §3 under
    "poke-env rulings (`pokeenv_gen4_survey.md` §10)", but survey §10 has no such
    item — it comes from G7 / encoder §3.6. Re-attribute it.
15. **Coverage is otherwise complete**: all 6 mechanics §16 items, all 9 survey
    §10 items, all 9 encoder §11 items and all 7 anchors §10 items map to a
    Q-number, and every Q-item's back-citation I checked (Q2→encoder §0/§6,
    Q5→anchors §6/A3, Q16→F-07 §7's exactly 8 rulings, Q18→mechanics §16 Q1,
    Q19→encoder §8, Q34→anchors A6, Q36→anchors §2 +
    `tests/test_showdown_env.py:411`, Q41→`IDEAS_POST_100M.md:114-115`,
    Q42→`JOURNEY.md:116`, Q43→survey §6, Q46→`make_bc_dataset.py:11`) resolves
    to a section that does say that.

---

## 3. Completeness gaps

**Reachable in the vendored pool** (counts are mine, `[tree]` from `sets.json`):

1. **Wish (19 sets) and Healing Wish (4) are SLOT conditions, and poke-env
   tracks no slot conditions at all** — `Move.slot_condition` exists
   (`move.py:639-644`) but `AbstractBattle` has no `slot_conditions` dict `[src]`.
   mechanics §7 asks for "a pending-wish flag per slot" without saying the data
   must be reconstructed from `_replay_data`; encoder §9 step 3's wrapper list
   omits it entirely. **Healing Wish appears in no doc** — not in the volatile
   table, not in §14's unreachable list, not in the encoder.
2. **Trick Room must invert the speed-edge feature.** encoder §4.1 carries a
   "v2 speed edge" and §3.3 a Trick Room flag, but no doc says the sign flips
   (`mods/gen4/scripts.ts:6-14` negates speed). One pool set; a sign error on
   every comparison while it is up.
3. **Opponent Choice-lock inference has no mechanism.** encoder §4.2 says
   "opponent inferred"; mechanics §11 says the three Choice items never
   self-reveal. The only signal is a repeated move (or a landed Trick, 21 sets).
   This belongs in encoder §9 step 3 beside item memory.
4. **Natural Cure (10 sets) silently cures on switch-out** and poke-env drops
   the `-curestatus` cause (survey §3.2) while `Pokemon.switch_out` does not
   clear `_status` `[src]`. No doc says the encoder must clear opponent status
   memory on such a switch.
5. **Gender and Attract.** Cute Charm (7 sets) infatuates on contact
   (mechanics §6), and Attract is gender-gated; the encoder has no gender
   feature although poke-env exposes `Pokemon.gender`.
6. **Un-removable items.** Multitype's `onTakeItem: false`
   (`mods/gen4/abilities.ts:283`) and Giratina-Origin's Griseous Orb make Trick
   (21) / Switcheroo (4) / Knock Off (3) fail into 40 of 464 sets. Only
   Multitype is mentioned, and not in that framing.
7. **gen4 Rotom formes.** `mods/gen4/pokedex.ts:7-26` restores all five
   appliance formes to **Electric/Ghost** but leaves gen5's boosted base stats
   (107/105/107/86 vs base Rotom's 77/95/77/91). So the forme key is
   load-bearing for **stats**, not types — the opposite of encoder A1's Arceus
   justification, and a Showdown-vs-cartridge divergence of exactly the class
   deferral D4 would have caught. Worth one sentence in encoder §3.4.
8. **Electric types are NOT paralysis-immune at gen 4** (gen5's electric row
   drops base's `par: 3`). mechanics §4's non-type-key list is correct by
   omission but never says so, and it does say the analogous gen1 facts.
9. **Sand's ×1.5 SpD for Rock and the sand/hail chip immunities have no encoder
   feature.** mechanics §9 states the rules; `GenData` cannot supply them
   (`gen_data.py:88-89` drops every lowercase key), so the spec needs its own
   table. encoder §3.3's weather block carries presence and duration only.
10. **The opponent stat estimator's `evs.spe = 0` branch fires on 2 sets, not a
    class** — gyroball is on **0** sets, metalburst 1, trickroom 1. Survey §3.3
    presents it as one of "two documented deviations"; the dose is worth stating.

**Unreachable in the pool** (correctly excluded, or named where they cannot
fire) `[tree]`: Stealth Rock 0 (already the subject of Q18); **Frisk 0, Thief 0,
Covet 0** — survey G12 names them as the gen4-legal `-item` causes, so that
crash path is reachable only through Trick/Switcheroo; **Defog 0** — half of
SH's `ANTI_HAZARDS_MOVES` is dead in gen4 (anchors §1 says "live (Rapid Spin)"
without noting the other key never fires); **Bide 0** though it is a real +1
move; **Gyro Ball 0**; **Natural Gift 0**; and the whole mechanics §14 list,
which I re-tested move by move and found to be at 0 sets without exception.

---

## 4. Live checklist (mechanical; one local gen4randombattle server)

| # | claim | doc § | the exact check |
|---|---|---|---|
| L1 | `maybe_trapped` rejection rate; the re-query does not loop | survey §1, G1, §8; Q27 | Over **N = 300** self-play gen4 battles, count decisions where `battle.maybe_trapped and not battle.trapped`, and `grep -c 'Unavailable choice' ` on the client log. Report both and the ratio. |
| L2 | Sleep Talk double bump | survey §3.5, G3; Q26 | Parse-only, **no server**: feed `\|move\|p1a: X\|Sleep Talk\|p2a: Y` then `\|move\|p1a: X\|Rest\|p1a: X\|[from]Sleep Talk` to `Battle.parse_message`; assert `mon.status_counter` rose by **1**, not 2. |
| L3 | sleep counter range and wake law (W9) | survey §3.5 | Over N = 200 battles, log `(status_counter, woke_this_turn)` at every own-side decision with `status == SLP`; assert max counter = **4** and the empirical wake rate at counter c matches **1/(5−c)**. |
| L4 | Sleep Clause vs Rest (W10) | survey §3.5 | `grep -c 'Sleep Clause Mod activated'` and, separately, count turns where two of one side's mons are `slp` at once. Expect the second to be > 0 on Rest sets. |
| L5 | force-switch request omits `active` | survey §2, §8 | Dump one U-turn-induced request JSON; assert `"active" not in request` and `request["forceSwitch"] == [True]`. |
| L6 | protocol reveal classes | mechanics §11, §17; survey §8 | Over N = 50 battles, `grep -oE '^\|-(ability\|activate\|immune\|enditem\|item\|status\|weather\|sidestart\|singleturn)\|[^\|]*\|[^\|]*'` the log; build the observed cause histogram and diff it against mechanics §11's four reveal classes. Assert `-ability` causes ⊆ {Anticipation, Intimidate, Mold Breaker, Pressure}. |
| L7 | `-weather` restamped every upkeep | survey §4, G2 | In one battle with sand up, assert a `\|-weather\|Sandstorm\|[upkeep]` line on **every** turn, and that `battle.turn - list(battle.weather.values())[0] <= 1` always. |
| L8 | ability weather is indefinite | mechanics §9; Q28 | Force a Tyranitar/Hippowdon lead; assert sand persists past turn 8 and that the setting line carries `[from] ability:` (which poke-env drops). |
| L9 | unknown-string histogram | survey §8 | Attach a `logging.Handler` to `"poke-env"` at WARNING over **N = 500** battles; report counts of `Effect`/`SideCondition`/`Weather`/`Field` UNKNOWN. Expect 0 for gen4 (`mudsport`/`watersport` are out of pool). |
| L10 | `strict_battle_tracking=True` survives gen 4 | survey §8; Q30 | 20 self-play battles with the flag; count `AssertionError` from `check_move_consistency` (`pokemon.py:296-306`). Suspect: PP under an unrevealed Pressure user. |
| L11 | `-item` 6-field causes (W7) | survey G12 | `grep -E '^\|-item\|' ` over N = 200 battle logs; report the field count and the `[from]` cause histogram. Expect only `move: Trick` / `move: Switcheroo`. |
| L12 | Flash Fire persistence | survey §3.6, G6 | One battle with a Flash Fire mon hit by two Fire moves; assert `Effect.FLASH_FIRE in mon.effects` after the **second**. |
| L13 | Substitute HP recoverable | encoder §3.2, §9 step 3 | `grep '\-activate.*Substitute'` and `\|-start\|.*Substitute`; confirm a `[damage]` payload exists to reconstruct sub HP, or record that it does not. |
| L14 | Encore / Disable move name in `_replay_data` | survey G5, encoder §3.2 | On one Encore turn, assert `event[4]` of the `-start` line names the locked move even though `mon.effects` drops it. |
| L15 | Wish / Healing Wish observability (§3 gap 1) | new | `grep -E '\|-(activate\|heal).*(Wish\|Healing Wish)'` over N = 50; confirm whether the slot and the pending turn are recoverable from the stream. |
| L16 | cosmetic-forme species keys | encoder §3.4 | Collect the set of `Pokemon.species` strings over N = 200 battles; assert it is a subset of the frozen 300-row vocab, and specifically check whether `gastrodoneast` / `castformsunny` ever appear. |
| L17 | move-id vocab closure | encoder §3.4 | Same run: collect every `move.id`; assert ⊆ the 182 (181 pool + `struggle`), and that Hidden Power arrives as the typed id. |
| L18 | tie rate and episode length | mechanics §12; anchors §5; Q33 | Over N = 300, report the turn-count distribution, the count of `turn > 1000` auto-ties, and mean decisions/episode against gen1's ~26–32. |
| L19 | s/battle reference for gen 4 | anchors §5.4 | From the same run, report s/battle for self-play and for vs-SH; this becomes the "progress is a rate" comparable the landmine requires. |
| L20 | mask-desync and aliasing rates at gen 4 | encoder §12 | Count `_recover_mask_desync` hits and `_move_slots_aliased` true-rate per 10k decisions; expect aliasing ≈ 0 (one Giga Impact set). |
| L21 | gen4 tape hash gate | encoder §8; Q19 | After L1–L20, collect six gen4 tapes (6,000 decisions) and land the `_HASH_CHILD`-shaped gate. **Nothing in the encoder is trustworthy until this exists.** |
| L22 | Foul Play gen4 smoke + Struggle panic | anchors §3 | `make poke_engine GEN=gen4`; assert `src/gen4/` module paths > 0; 5 battles vs SH at `--search-time-ms 20`; force a both-sides-out-of-PP turn and watch for `Invalid PokemonMoveIndex: 4`. |
| L23 | gen1 Hyper-Beam-on-KO recharge | mechanics §13, §17 | gen1 only, and lowest priority: one gen1 battle where Hyper Beam KOs; assert no `-mustrecharge` follows. |

---

## 5. The ten corrections worth making, in order

1. **`pokeenv_gen4_survey.md` §3.5** — replace "so `status_counter ∈ {0..3}`
   while asleep and P(wake on the next attempt) = 1/(4 − counter)" with
   "so `status_counter ∈ {0..4}` while asleep and P(wake on the next attempt)
   = 1/(5 − counter) for counter ≥ 1, and 0 at counter 0 (a sleeping mon always
   loses at least one turn)". This is the sleep feature's whole semantics and
   encoder §3.2's `/4` scale reads off it. (W9)
2. **`pokeenv_gen4_survey.md` §3.5, last line** — replace "Sleep Clause Mod is
   on for the format `[tree]`, so at most one opponent mon is asleep at a time"
   with "Sleep Clause Mod is on `[tree]`, but it exempts self-inflicted sleep
   (`showdown/data/rulesets.ts:1386-1398` returns early when
   `source.isAlly(target)`), so a Rest user (35 sets) and an opponent-slept mon
   can be asleep simultaneously". (W10)
3. **`mechanics_delta.md` §10** — replace "+1 moves sit on 77 of 464 pool sets
   (eight distinct ones)" with "+1 moves sit on **95 of 464** pool sets
   (**ten** distinct: suckerpunch 31, extremespeed 16, quickattack 9,
   shadowsneak 9, aquajet 8, fakeout 8, bulletpunch 7, iceshard 7, machpunch 5,
   vacuumwave 1)". (W5)
4. **`pokeenv_gen4_survey.md` §3.1 and G12** — replace
   `abstract_battle.py:1193-1199` and `abstract_battle.py:1148-1200` with
   `abstract_battle.py:934` (`-enditem`) and `:949` (`-item`), and change
   G12's "`ValueError`" to "`NotImplementedError` from the `:1187-1188`
   fallback"; add that Frisk, Thief and Covet are all on **0** pool sets, so the
   only live cause is Trick/Switcheroo. (W7, W8, §3 unreachable list)
5. **`mechanics_delta.md` §7** — the Substitute row: replace "sets
   `substitutebroken` on break (`mods/gen4/scripts.ts:51`)" with "the
   `substitutebroken` volatile (`mods/gen4/conditions.ts:99`) is **cleared from
   every foe when a mon switches in** (`mods/gen4/scripts.ts:49-53`)". (W4)
6. **`encoder_requirements.md` §0** — replace "OBS_DIM … ≈ **1,180**
   (illustrative, §4.7)" with "≈ **1,183–1,376** (illustrative; §4.7 gives both
   the full-width and the lean sketch)", and replace "~16 flags + 6 counters"
   with "**18** flags + 6 counters (§3.2)". Then make §4.2 say 18, not "~17".
   (W17, W18)
7. **`mechanics_delta.md` §2** — three citation fixes in one pass: Light Screen's
   crit bypass `:1164` → `:731-748` (the handler is `:736`); the base-damage
   formula `battle-actions.ts:1712-1717` → `:1715-1718`; and in §7 the Explosion
   defence halving `:1706-1708` → `:1711-1713`. Also change §4's "Two poke-env
   traps" to "Three". (W1, W2, W3, W14)
8. **All three docs carrying "277 of 295"** (mechanics §11, survey §3.2,
   encoder §3.5) → **278 of 295**; **"≈ 68 sets"** (mechanics §0 and §11) → **69
   sets**; **"Six pool species carry Flash Fire"** (survey §3.6, encoder §3.2) →
   **five species over eight sets**; and **`baselines.py:317`** → **`:314`** in
   survey §7 and anchors §1. (W6, W11, W12, W13)
9. **`encoder_requirements.md` §9 step 3** — add three wrapper-side items the
   list is missing, each `[live]` and each recoverable only from
   `_replay_data`: **Wish / Healing Wish slot state** (23 sets; poke-env tracks
   no slot conditions — `move.py:639-644` is the only mention), **opponent
   Choice-lock inference** (the item never self-reveals; the only signal is a
   repeated move or a landed Trick), and **Natural Cure status clearing on
   switch-out** (10 sets; `-curestatus`'s cause is dropped and
   `Pokemon.switch_out` leaves `_status` set). Add one line to §4.1/§4.4 that
   the speed-edge feature **inverts under Trick Room**. (§3 gaps 1–4)
10. **`open_questions.md`** — four record fixes: promote encoder §10 **A5**
    (ability-aware matchup scalars) and **A14** (`priority_scale = 7.0`) to
    Q-items, since both change the vector and neither is escalated anywhere;
    re-attribute **Q32** away from "survey §10" (it comes from G7 / encoder
    §3.6); fix **M1**'s path and branch — the worktree is
    `…/pokemon-showdown-rl-gen4` on **`gen4-build`**, already at main's HEAD, so
    the rebase is a no-op and all five headers' "branch `gen4-design`" is stale;
    and either restore DOC_CONVENTIONS rule 10's **verbatim** collection or amend
    the rule to say "faithfully restated", because no Q-item is verbatim today.
    (W20, §2 items 10–14)

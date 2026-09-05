# Wang's pokemon-showdown fork — `>getstate`/`>load`, the constrained set regeneration, and what our set prior can borrow

> **design_gen4 status header (mandatory, verbatim structure).**
> Written 2026-09-04 on branch `gen4-build`, DOCS ONLY — nothing under `rl/`
> changed. **Arc position:** the target is JOURNEY step 3 (gen4 encoder +
> model). This design work is **maintainer-ruled PREPARATION running AHEAD of
> step 2 (gen1 ladder #3)**, done while the maintainer-ordered, off-arc 100M
> fleet runs; it is not a pre-registration and it launches nothing.
> **Verification status per claim** — every claim below carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo
>   (`rl/`, `scripts/`, `configs/`, `tests/`, docs) or the vendored
>   `showdown/` data/sim: the game as we actually run it.
> - `[src]` **source-verified** — checked against an external primary source
>   on disk: installed poke-env 0.15.0, Wang's fork diffs / thesis PDF, the
>   H&L PDF / metagrok clone, ps-ppo, foul-play, the Metamon PDF.
> - `[lit]` **literature-only** — a secondary write-up, a web page, or the
>   prior-work index, not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running server or a battle
>   can confirm it; BARRED until the 100M fleet AND its frozen post-fleet eval
>   schedule complete; the exact check is stated beside the tag.
> **Sources read for this doc:** `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/docs/prior_work/wang_fork_diffs.md`
> §1 (lines 1–3407) in full, except the 47k-line upstream-sync churn inside commit
> `89bf869ba` (file lines 2171–3405), read by extracting its `+`/`-` lines and then
> reading the hunks touching the author's own code; §2 (poke-env) NOT read beyond its
> commit log at :3413–3450 — `wang_pokeenv_fork.md` owns it. Vendored
> `showdown/data/random-battles/gen4/{teams.ts,sets.json}` and `showdown/sim/state.ts`
> (pinned 59da482e). `docs/prior_work/README.md:10–13, 393–400, 460–500, 565–570`.
> `docs/design_gen4/research/wang_thesis.md:80–101, 528–594`. The thesis PDF was NOT
> re-read (per brief); claims sourced through that note are tagged `[lit]`.
> **Feeds / depends on:** discharges deferral **D1** (`open_questions.md` §7); feeds
> `encoder_requirements.md` §3.5, `open_questions.md` Q12, `anchors_and_eval.md` §6,
> `mechanics_delta.md` §16. Depends on `showdown_gen4_pool.md` for pool counts.
> **Reconcile at merge:** nothing here is designed against the `audit-fixes` F-08
> EncoderSpec seam; §5's prior is a data proposal, not an interface change.

Fork-diff citations are absolute lines in `wang_fork_diffs.md` (gitignored, main tree
only), written `fork:NNN`. Vendored paths are worktree-relative. Nothing here was
measured, launched or evaluated; no checkpoint was touched.

---

## 1. What the fork is

`[src]` Thirteen non-merge commits, 2023-12-26 → 2024-03-20, touching exactly six files
(`fork:15`): `data/mods/gen4/random-teams.ts`, `server/chat-commands/core.ts`,
`server/room-battle.ts`, `sim/battle-stream.ts`, `sim/battle.ts`, `sim/pokemon.ts`.
**No other file under `data/mods/gen4/`** — no `moves.ts`, `abilities.ts`, `items.ts`,
`scripts.ts`, no `sim/battle-actions.ts`, no type chart, no `formats-data`. The first
commit does not compile (`fork:134-135` is a bare `if` with no condition; `fork:78`
reads an unbound `isLead`, fixed at `fork:1172`), so read the fork as its cumulative
end state.

---

## 2. `>getstate` and `>load`: what crosses the wire

### 2.1 `>getstate`

| step | code | file:line |
|---|---|---|
| `/getstate` (alias `/save`), for the CALLER's own slot | `room.battle!.getState(player.slot)` | `fork:454-463` |
| room writes one stream line | `` stream.write(`>getstate ${target}`) `` | `fork:509-510` |
| stream dispatches | `this.battle!.emitState(message as SideID)` | `fork:661-665` |
| battle serialises and sends | `` send('sideupdate', `${sideid}\n\|state\|${JSON.stringify(this.toJSON())}`) `` | `fork:744-748` |

`[src]` `Battle.toJSON()` is upstream `State.serializeBattle` (`fork:737-738`).
`[tree]` In our vendored copy that serializer emits, for **both** sides: every Pokémon's
complete `PokemonSet` — species, the four real moves, item, ability, EVs, IVs, level,
gender (`showdown/sim/state.ts:212-222`, `state.set = pokemon.set`); every `moveSlot`
with live PP (`moveSlots` is not in the `POKEMON` skip set, `state.ts:46-49`); the live
RNG seed (`state.ts:68`); and the whole `log` (`state.ts:70-72`). **Nothing in the path
filters by side.** The payload is a complete perfect-information dump delivered to one
player's client.

### 2.2 `>load`

`[src]` Wire format `>load <sideid>|~|<sets JSON>|~|<state JSON>`. The chat side splits
the client's argument on `|-|` into `rest` and a `|~|`-joined rqid list
(`fork:525-547`), then writes the stream line **for the side that did NOT send the
load** (`fork:551-558`; comment verbatim "reroll the side that didn't send the load").
The stream handler (`fork:667-705`) then: parses `<sets JSON>` into `SetCriteria[]` —
only `species`, `moves`, `isLead` and optional `item`, `ability` survive
(`fork:675-689`, interface `fork:717-723`); restores `Battle.fromJSON(jsonState)` +
`restart(send)` **verbatim, true opponent team included** (`fork:694-696`); `undoChoice`
on both sides (`fork:699-701`); `resetRNG(null)`, so a rollout does not replay the true
future RNG stream (`fork:702`); **only then** `rerollTeam(sideid, checkpointSets)`
(`fork:703`); `makeRequest()` (`fork:704`).

`[src]` `rerollTeam` (`fork:757-814`) calls `randomTeamFromPartial(checkpointSets, 6)`
(`fork:767`); a slot whose `baseSpecies` was revealed keeps its Pokémon object and gets
`poke.replaceSet(newSet)` (HP, status, boosts, volatiles, position preserved), an
unrevealed slot is replaced by a fresh `Pokemon` (`fork:778-805`); `pokemonLeft` is
recounted from `fainted` flags (`fork:808-811`), so no fainted slot resurrects.

### 2.3 Privileged information

`[src]` **The interface leaks: the server hands the searching client the opponent's real
sets and nothing redacts them.** The determinization is applied inside the restored
battle, not to the payload. Whether his agent reads the opponent's true `set` fields
before re-serialising for `>load` is **not determinable here** — §2 of the diff
(poke-env) has no `getstate`/`load`/`|state|` handler (grepped `fork:3409-4213`: zero
hits), so the client half lives in his private agent repo, **not read**.

Three bounding observations `[src]`: the `SetCriteria` returned is strictly the revealed
subset (`fork:717-723`) — he would not need a rejection sampler if he were exploiting
the leak; between restore and reroll the search battle briefly holds the true team, and
only the named `sideid` is rerolled (the server-side `load` forces it to be the
opponent, `fork:551-558`, but a direct `>load` writer does not — a port must keep that
check); and the thesis's own account is rejection-sampled determinization `[lit]`
(`wang_thesis.md:564-573`). **Verdict: the interface leaks, the described algorithm does
not use the leak, the code that would settle it was not read.**

---

## 3. The constrained set regeneration

### 3.1 The constraint set, exactly

| constrained? | field | how | file:line |
|---|---|---|---|
| yes | species | fixes the species; popped from `baseSpeciesPool` | `fork:270-272` |
| yes | revealed moves | candidate sets pre-filtered to those whose `movepool` contains **every** revealed move; re-checked on the realised set | `fork:1160-1168`, `fork:99-102` |
| yes (weak) | Hidden Power | revealed as bare `hiddenpower`; a set qualifies if its movepool has any `hiddenpower*`, then a type is drawn from that set's HP entries | `fork:1402-1403`, `fork:1216-1237`, `fork:84-85` |
| yes | item | `toID` equality, only if revealed | `fork:89-92` |
| yes | ability | `toID` equality, only if revealed | `fork:94-97` |
| yes | lead flag | `isLead` passed to `getItem`/`cullMovePool` | `fork:722`, `fork:1183` |
| **no** | level | taken from the pool table, never constrained | `fork:182` |
| **no** | EVs / IVs / stats | regenerated by the standard rules (85s, 31s, HP-optimisation loop, confusion and Gyro Ball IV zeroing) | `fork:152-153`, `fork:205-236` |
| **no** | gender, shininess | re-rolled | `fork:239-242` |
| **no** | PP spent on an unrevealed move | new slots get full `basepp` | `fork:865-880` |
| **no** | "N of 4 slots already known" | no remaining-slot accounting beyond the movepool filter | — |

`[src]` Rejection sampling with a forced fallback (`fork:69-109`). `attempts` defaults
to 100; `randomTeamFromPartial` passes **500** (`fork:306-310`), later cut to **10**
(`fork:1610-1616`) — matching the thesis's "If after 10 attempts…" `[lit]`
(`wang_thesis.md:570-572`). On the last attempt `force=true`: ability and item are
written straight from the criteria, bypassing `getAbility`/`getItem` (`fork:1254`,
`fork:1268`), and the moveset switches from plain `randomMoveset` to
`randomConstrainedMoveset`, which seeds the move set with the revealed moves and runs
the full enforcement cascade around them (`fork:1581-1592`, `fork:911-1149`). If the
forced set still fails the post-check it throws (`fork:108`). **If no candidate set
matches at all, he re-allows every set** (`fork:1463-1470`, logging `NO SETS POSSIBLE
MATCHING MOVEPOOL`): the constrained prior silently degrades to the unconditional one.
We need the same escape hatch — out-of-pool reveals are real (Ditto's Transform copies
the opponent's moves; `transform` is in exactly 1 vendored set `[tree]`).

### 3.2 Four citable defects

1. `[src]` `new Set<string>(...criteria.moves)` (`fork:1213`) spreads the array into the
   constructor, building a set of the **characters** of the first move name; fixed at
   `fork:1420`. The 2023-12-26 snapshot is not a spec.
2. `[src]` `typeWeaknesses[typeName]++` on an uninitialised counter for the revealed half
   (`fork:300-305`) yields `NaN`, which the fill loop's `if (!typeWeaknesses[t])` guard
   (`fork:362-366`) resets to 0. **The "≤3 weak to any type" constraint is never enforced
   against the revealed Pokémon**, so his determinized teams are slightly more
   type-lopsided than real ones.
3. `[src]` `movePoolWithLockedMoves = set.movepool` aliased the shared table and `fastPop`
   mutated it (`fork:1209`, `fork:1234`); fixed by `Array.from` at `fork:1523-1528`.
4. `[src]` The `canSpinner` block (`fork:132-142`) forces the Spinner role whenever any
   Spinner set exists, and is the code that does not compile; removed at `fork:1189-1205`.
   **Moot for us — the vendored gen4 pool has no `Spinner` role** `[tree]` (§4).

### 3.3 The team-level constraints he does reproduce

`[src]` `randomTeamFromPartial` (`fork:253-432`, revised `fork:1278-1331`) rebuilds the
opponent to a full 6 under the standard randbats team rules: Species Clause on
`baseSpecies` (`fork:336`), ≤2 per tier (`fork:344`), ≤2 of any type (`fork:352-357`),
≤3 weak to any type (`fork:361-370`, but see defect 2), ≤1 of any type combination
(`fork:374`), Zoroark not last (`fork:339`). It **pre-populates `teamDetails` from the
revealed half** — hail/rain/sand/sun/spikes/stealthrock/toxicspikes/rapidspin/screens
(`fork:1282-1293`) — before generating anything.

`[src]` The sun/rain hack: `shouldCullAbility` culls Chlorophyll and Leaf Guard when
`!teamDetails.sun` and Swift Swim when `!teamDetails.rain`, so per-mon determinization
would systematically kill them. He forced both to 1 (`fork:1256-1265`), then replaced
that with independent marginals **P(sun)=0.054, P(rain)=0.120** (`fork:1605-1606`,
`fork:2004-2005`), commented as "roughly … the chance that a completely random team has
sun or rain". `[tree]` Our vendored `shouldCullAbility` has the same two weather branches
(`showdown/data/random-battles/gen4/teams.ts:452-472`, weather at `:461-464`), so **that
bias is ours too** — and his two numbers are reusable, though uncited in his code and
unverified here.

---

## 4. His generator vs our vendored pool — a correction to D1

`[src]` **His fork samples the same curated role-table architecture we vendor.**
`randomConstrainedSetInner` reads `this.randomSets[species.id]["sets"]` and uses
`set.role`, `set.movepool`, `set.preferredTypes`, then `cullMovePool` → `getAbility` →
`getPriorityItem` → `getItem` → the table `level` (`fork:128-182`, `fork:1160-1161`,
`fork:2100-2108`). `[tree]` The vendored `randomSet` has the same shape:
`randomSets = require('./sets.json')` (`teams.ts:45`), `randomSet` `:627-673`, sets
`:636`, `randomMoveset` `:655`, `getAbility` `:660`, `getPriorityItem`/`getItem`
`:663-666`, `getLevel` `:673`.

**This contradicts the premise in `open_questions.md` §7 D1, repeated at
`wang_thesis.md:580-593`.** Both positions, per DOC_CONVENTIONS 3:

- **The notes' position** `[lit]`: our pool is a curated ≤3-sets-per-species table, Wang
  measured "1 to 56 sets, mean ≈8, median 6" (thesis p. 15), so his sampler is a
  different object and a modern determinizer should *enumerate* the ≤3 sets.
- **This note's position** `[src]`+`[tree]`: the architecture is identical; the
  1–56/mean-8 figure counts **distinct realised sets over 2.6M generated teams**, not
  table rows. Rows expand — a 6-move movepool alone gives up to C(6,4)=15 movesets before
  ability and item branching. `[tree]` The vendored movepool-size histogram over 464 sets
  is {1:1, 4:152, 5:168, 6:97, 7:30, 8:15, 9:1}: only 152/464 (32.8%) are exact four-move
  sets, so two thirds of the pool is genuinely sampled and "enumerate the ≤3 candidates"
  under-counts the belief space by roughly an order of magnitude.

**What settles it:** counting distinct realised sets per species by sampling the vendored
generator (a cheap `nice -n 19 node` probe in the style of `probes/_gen4pool_sample.js`)
and comparing to thesis p. 15. **Not run here.** Until it is, "the belief space is ≤3 per
species" is **withdrawn, not replaced**.

`[tree]` Vendored pool facts recomputed this session with stdlib `json`: 295 species, 464
sets; per-set keys `role` (464), `movepool` (464), `abilities` (464), `preferredTypes`
(85); per-species keys `level`, `sets`; roles = Bulky Attacker 81, Bulky Support 80, Fast
Attacker 76, Setup Sweeper 65, Staller 53, Bulky Setup 47, Wallbreaker 44, Fast Support
18 (**no Spinner**); `abilities` length 1 in 446 sets, 2 in 18; levels 67–100.

**One divergence, and it favours us** `[src]`+`[tree]`: Wang's copied `randomSet` body
derives candidate abilities from the **dex** — `new Set(Object.values(species.abilities))`
minus `unreleasedHidden` (`fork:156-157`) — whereas the vendored pool carries a **per-set
`abilities` list** (`teams.ts:652`) and `getAbility` short-circuits with
`if (abilities.length <= 1) return abilities[0]` (`teams.ts:483`). With 446/464 sets
single-abilitied, our ability prior is a one-hot **given the set** for 96% of sets — a
sharper constraint than his.

---

## 5. What our set prior can and cannot borrow

| borrowable | from | our use |
|---|---|---|
| candidate-set filter: keep sets whose `movepool` ⊇ revealed moves | `fork:1160-1168` | the single most useful operation for a role-conditioned prior; a set-membership test on `sets.json`, no sampler port |
| Hidden Power relaxation (`hiddenpower` matches any `hiddenpower*`) | `fork:1402-1403` | required — the opponent view never carries an HP type |
| degrade-to-all-sets fallback on an empty candidate list | `fork:1463-1470` | required for Transform / out-of-pool reveals |
| `teamDetails` pre-population from the revealed half | `fork:1282-1293` | conditions the ability prior (weather) and the hazard-removal enforcement branch |
| P(sun)=0.054 / P(rain)=0.120 team-weather marginals | `fork:1605-1606` | the correction `teams.ts:461-464` needs; recompute on our pool before pre-registering |
| team constraints as *cross-mon* prior signal (species / tier / type / type-combo caps) | `fork:335-374` | a revealed species constrains the unrevealed five; per-species marginals in `encoder_requirements.md` §3.5 capture none of this |
| the five-field revealed-information vocabulary | `fork:717-723` | confirms our reveal model: level and stats are never inferable |

**Cannot borrow:** his **counts** (6-sets-per-species and the 1–56 range measure a 2023
dex snapshot's realised-set distribution, and his §2.2 game-tree numbers inherit it
`[lit]`); the **Spinner** logic (`fork:132-142`, `fork:981-986` — no such role `[tree]`);
his **ability candidate space** (`fork:156-157` vs `teams.ts:652`); the
`getAbility`/`cullMovePool`/`addMove` **signatures** (his still carry `isDoubles` and
`preferredType`/`role`/`movePool`, `fork:1786-1800`, `fork:2003-2008`, vs
`teams.ts:452-481` — a copy-paste port will not typecheck); any **item prior** (he
constrains items only by equality when revealed, so Q12's item rule table must still come
from `getItem`/`getPriorityItem`, `teams.ts:510-626`); and any claim that his sampler is
correct (§3.2).

---

## 6. Hallucinated-move disabling

`[src]` **What it is:** when `replaceSet` mints new move slots for a determinized opponent
(`fork:839-885`) they are created `disabled: false` (`fork:874-875`), but the Pokémon may
be mid-Choice-lock, mid-Encore or mid-Taunt, and those volatiles only disable slots at
slot-creation / `disableMove` time. The hallucinated moves would be **selectable in the
search copy when the rules say they are not.** The fix (`fork:1642-1668`) sets
`disabled`/`disabledSource` at mint time:

| case | condition | source label | file:line |
|---|---|---|---|
| Choice lock | `volatiles['choicelock'] && move.id !== volatiles['choicelock'].move` | the item's name | `fork:1644-1647` |
| Encore | `volatiles['encore'] && move.id != side.lastSelectedMove` | `'Encore'` | `fork:1748-1752` |
| Taunt | `volatiles['taunt'] && move.category === 'Status'` | `'Taunt'` | `fork:1754-1757` |

Both the Encore and Taunt conditions shipped **negated** (`fork:1648`, `fork:1653`) and
were corrected the same day (`fork:1747-1757`); comment verbatim at `fork:1649`:
"showdown doesn't normally use lastSelectedMove in this gen, so I get to hijack it for
hallucination".

**Does it change the rules his network trained under? No.** `[src]` `replaceSet` is called
only from `rerollTeam` (`fork:786`), called only from the `>load` handler (`fork:703`),
which fires only on an explicit `>load`. Nothing on the ordinary battle path touches it.
It is a **search-copy fidelity fix** and does not bear on the comparability of his 0.786
vs `SimpleHeuristicsPlayer` — a network-alone number `[lit]` (`wang_thesis.md:411-420`).

`[src]` **What it does NOT restore** (a checklist if we ever port it): Disable, Torment,
Imprison, Mimic-overwritten slots, and Transform — `fork:882` does
`this.moveSlots = this.baseMoveSlots.slice()` unconditionally. PP of already-revealed
moves is preserved (`fork:855-859` skips moves already in `this.moves`); hallucinated
moves get full `basepp` (`fork:865`).

---

## 7. Rules and server behaviour the fork changes — the comparability inventory

| # | change | file:line | rules change? |
|---|---|---|---|
| R1 | `/offertie` "please play until turn 100" guard **removed** | `fork:444-446` | **Yes, in-battle.** A tie can be agreed at any turn; both players must still opt in, and ties are non-wins under our locked protocol. The only change to what the server permits inside a battle. |
| R2 | battle end gutted to `timer.end(); logData = null; room.update()` — no ladder update, no `logBattle`, no `onBattleEnd`/`onBattleRanked`, no replay upload | `fork:574-630`; survives the merge at `fork:2736-2758` (`updateLadder` exists at `fork:2759`, never called) | No — bookkeeping. His local server never rated or logged; his published ladder numbers come from the **public** server, which has none of this fork. |
| R3 | `clearPlayers()` on end gated on usernames starting `train`/`eval` (later: drop the room from each user's game list) | `fork:566-570`, `fork:2021-2032`, `fork:2745-2748` | No — room-lifecycle hygiene, the same class as our ORPHANED-ROOM DEADLOCK / `/timer on` landmine (CLAUDE.md). Convergent evidence the leak is real; his fix is username-scoped, ours is the timer requester. |
| R4 | `choose()` too-late guard split into two branches with distinct error text | `fork:489-503` | No — semantically identical, message text only. |
| R5 | `consoleLog` no-op wrappers on five classes | `fork:56-59, 481-484, 649-652, 732-735, 827-830` | No. |
| R6 | new `>getstate`/`>load`, `Battle.emitState`, `Battle.rerollTeam`, `Pokemon.replaceSet`, `SetCriteria` | §2 | No — additive, inert unless invoked. |
| R7 | gen4 `random-teams.ts`: `randomConstrainedSet(Inner)`, `randomConstrainedMoveset`, `addMove`, `randomTeamFromPartial` | `fork:69-432, 911-1149, 1546-1569` | **No** — additive methods; the ordinary `randomSet`/`randomTeam` path is untouched, so the teams his agent trained and laddered on are stock. |

`[src]` **Not changed anywhere in the fork:** the damage formula, type chart, critical-hit
rules, accuracy, sleep/freeze mechanics, any clause (Sleep, Species, Evasion, Endless
Battle, OHKO), the turn cap, `forcetie`/`tiebreak`, and **the timer** — `RoomBattleTimer`
is touched only by upstream's own refactor inside the merge commit (`fork:2299-2379`). His
150 s/turn ladder clock `[lit]` (`wang_thesis.md:57-59`) is stock Showdown.

---

## 8. Other things an encoder / prior implementer wants

1. `[src]` **The revealed-information vocabulary is exactly five fields** (`fork:717-723`)
   — no stat estimates, no level inference, no remaining-move count. A second independent
   source for the reveal model in `encoder_requirements.md` §3.
2. `[src]` **`isLead` is a per-Pokémon constraint**, not a team property (`fork:722`,
   `fork:1183`), because `getItem`'s Focus Sash branch is lead-conditioned; our item prior
   needs the same flag.
3. `[src]` **Hidden Power is revealed without its type** and re-sampled from the chosen
   set's HP entries (`fork:1216-1237`) — his answer to the one-token-vs-16 encoder question
   is "one token in the observation, sampled in the prior".
4. `[src]` **PP is not part of the constraint set** (`fork:865`) — a "how much PP does the
   opponent have left" belief feature is ours to invent.
5. `[src]` **rqid bookkeeping on restore** (`fork:530-547`): he decrements the room's `rqid`
   by the number of active requests so reissued requests match what the client holds; a port
   that skips it desynchronises the client.
6. `[src]` **`resetRNG(null)` per load** (`fork:702`) means each determinized rollout
   re-randomises damage rolls too, so "one determinization per rollout" `[lit]`
   (`wang_thesis.md:564-573`) also means one RNG stream per rollout.
7. `[src]` Two upstream generator changes visible inside the merge (`fork:2058-2064` Shiftry
   added to `PRIORITY_POKEMON`; `fork:2067-2083` Rampardos Fast Attacker → Choice Scarf plus
   a `uturn` guard on the lead Focus Sash rule) confirm the gen4 pool kept churning after his
   fork. `[tree]` Ours is pinned at 59da482e; any constant borrowed from his fork is pinned
   to *his* snapshot.

---

## 9. What this changes in the five docs

Concrete and cited; **this note edits none of them.**

**`open_questions.md` §7 D1** — mark D1 **discharged** and replace its closing sentence
("the vendored pool is a curated table (≤ 3 sets per species), not the 2023 procedural
generator he sampled"), which is wrong on the architecture (§4): same generator family
(`fork:1160-1161`, `fork:2100-2108` vs `teams.ts:45,636`); what differs is the ability
source (dex vs per-set list) and the 2023-vs-59da482e table contents; and "≤3 sets" counts
table rows, not realised sets.

**`encoder_requirements.md` §3.5** — three additions and one correction. (a) **Add the
candidate-set filter** to the v1 prior: condition the role-conditioned marginals on the
`sets.json` rows whose `movepool` contains every revealed move, with the Hidden Power
relaxation and the empty-candidate fallback (`fork:1160-1168`, `fork:1402-1403`,
`fork:1463-1470`) — cheapest real improvement available, no sampler port. (b) **Add the
weather caveat**: the prior for Chlorophyll, Leaf Guard and Swift Swim is team-conditional
through `teamDetails.sun`/`rain` (`teams.ts:461-464`) and cannot be a per-species marginal;
`fork:1605-1606` is the shape of the fix. (c) **Correct the movepool split**: §3.5's
"roughly a third exact four-move, two thirds sampled from 5–6-move pools" — measured,
152/464 exact-4 (32.8%) holds, but 5–6-move is 265/464 (57.1%) and **46 sets have 7–9-move
pools** `[tree]`. (d) `abilities` is **per-set** (446/464 single, `teams.ts:652,483`); §3.5
attributes the one-hot collapse to species.

**`open_questions.md` Q12** — the recommendation (role-conditioned marginals plus an item
rule table) **survives and is strengthened**: Wang, with a full sampler in-process, still
reduced the problem to a movepool-membership filter plus rejection sampling, and his escape
hatch drops the constraint entirely. Its losing argument gains a datum: the realised-set
space per species is not ≤3 (§4), so "the marginals are NOT a heuristic" needs addition (a)
to stay true. **Add a refusal line:** this note declines to decide whether the cross-mon
team constraints (`fork:335-374`) belong in v1.

**`anchors_and_eval.md` §6** — add: nothing in Wang's Showdown fork changes gen4 battle
rules for training or evaluation (§7 R1–R7; only `/offertie`'s turn-100 gate is removed,
`fork:444-446`), so his 0.786 vs SH is not confounded by a modified simulator. The remaining
confound is the one already recorded — *which* SH `[lit]` (`wang_thesis.md:479-484`).

**`mechanics_delta.md` §16** — add R1 (`fork:444-446`) and R3 (`fork:2021-2032`) to the
disclosure list, R3 as independent corroboration of the orphaned-room bug class our
`/timer on` rule addresses.

**`research/README.md`** — add the row `wang_showdown_fork.md` | Wang's pokemon-showdown
fork, `wang_fork_diffs.md` §1 | `encoder_requirements.md` §3.5, `open_questions.md` Q12 /
§7 D1, `anchors_and_eval.md` §6; move D1 out of "Never produced"; and add to "Known errors
in the notes": `wang_thesis.md:580-593`'s "the generator he measured is not the generator we
would run" overstates the difference (§4).

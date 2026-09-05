# ps-ppo and Metamon observation design — the two comparators D2 deferred

> **design_gen4 status header.** Written 2026-09-04 on branch `gen4-build`, DOCS
> ONLY — nothing under `rl/` changed, nothing was launched, no checkpoint was
> touched, no server was started. **Arc position:** the target is JOURNEY step 3
> (gen4 encoder + model); this is **maintainer-ruled PREPARATION running AHEAD of
> step 2**, written while a rated ladder run is live from the main tree. Not a
> pre-registration.
> **Verification status per claim** — exactly one tag each: `[tree]` a file in
> this repo / the vendored `showdown/`; `[src]` an external primary on disk (the
> ps-ppo clone, the Metamon PDF, installed poke-env 0.15.0); `[lit]`
> `docs/prior_work/README.md` or another secondary, not re-checked; `[live]` needs
> a running server — **BARRED** until the ladder run and its frozen eval schedule
> complete. **This note contains no `[live]` claims.**
> **Sources read:** the ps-ppo clone at
> `/Users/nickgreenquist/Documents/Projects/ps-ppo` @ HEAD — `obs_pokemon.py`,
> `obs_moves.py`, `obs_abilities.py`, `obs_global.py`, `obs_transitions.py`,
> `obs_assembler.py`, `utils.py`, `config.py` in full; `vocab.json` /
> `type_schema.json` structurally; `ppo_core.py:415-560`; `worker.py:540-580` —
> cited as `ps-ppo/<file>:<line>`. The Metamon PDF
> (`docs/prior_work/grigsby2025_metamon.pdf` pp. 6-7, 21, 23, 25-28), cited as
> `Metamon p.N`. Also `docs/prior_work/README.md:320-356, 412-560` and
> `poke_env/battle/pokemon.py` (0.15.0). **The Wang and OURS columns come from
> `wang_thesis.md` §2.2/§2.3/§13 and `encoder_requirements.md` §3-§5 — his PDF was
> not re-opened.**
> **Feeds:** `open_questions.md` §7 D2 (discharged), Q11, Q13, Q29;
> `encoder_requirements.md` §5, which currently says these two were not read.
> **Reconcile at merge:** none — this note designs nothing.

## 0. What this note settles

D2 asked how the two largest pure-policy systems encode items, abilities and stat
belief. Both were read. Two headline corrections: **ps-ppo is the only one of the
four systems that builds an opponent-stat belief, and it is a range over ITEM AND
ABILITY, not over EVs/IVs — the phrase at `docs/prior_work/README.md:449-451`,
restated at `encoder_requirements.md:375`, is wrong** `[src]`. And **Metamon is a
weaker encoder comparator than its rating suggests**: only the opponent's ACTIVE
Pokemon, one volatile slot per mon, no durations, no PP, no possible-ability
belief `[src]` (`Metamon p.6`, `p.7 Fig 5`, `p.27 E.2`). Neither system reports an
ablation on any observation-design choice; the only evidence in either is two
Metamon nulls and one stated cost (§7).

## 1. ps-ppo — the vector `[src]`

Sizes computed by calling the repo's own metadata functions against its committed
`vocab.json` (read-only import of `obs_assembler.get_schema_metadata`; no server,
no model). `ps-ppo/obs_assembler.py:62-81`.

| block | shape | dims | offsets |
|---|---|---|---|
| `pokemon_body` | 12 × 351 | 4212 | 0-4212 |
| `pokemon_ids` (species, item) | 12 × 2 | 24 | 4212-4236 |
| `ability_ids` | 12 × 4 | 48 | 4236-4284 |
| `move_ids` | 12 × 4 | 48 | 4284-4332 |
| `move_scalars` | 12 × 340 (4 × 85) | 4080 | 4332-8412 |
| `global_scalars` | 41 | 41 | 8412-8453 |
| `transition_ids` | 10 | 10 | 8453-8463 |
| `transition_scalars` | 2 × 45 | 90 | 8463-8553 |
| `action_mask` | 14 | 14 | 8553-8567 |
| **total** | | **8567** | |

Per-mon body, 351 dims (`obs_pokemon.py:24-55`): `hp_int` 0 · `hp_abs_raw` 1-3 ·
`stats_int` 3-18 · `boosts_raw` 18-109 · `level_int` 109 · `weight_int` 110 ·
`height_int` 111 · `flags_raw` 112-124 · `mechanics_raw` 124-129 · `types_raw`
129-171 (2 × 21) · `effects_raw` 171-327 · `status_raw` 327-335 · `gender_raw`
335-339 · `pos_raw` 339-351. `hp_abs_raw` is **never read by the model** — the
`p_in` concatenation skips indices 1-2 (`ppo_core.py:532-543`). Per-move, 85 dims
(`obs_moves.py:31-59`), field by field in §2(8).
**Integers, not normalized floats:** `hp_int`/`level_int`/`acc_int`/`pp_int` → a
101-row `val_100` bank, the 15 `stats_int` + weight/height → an 800-row `stat`
bank, `pwr_int` + the global turn counter → a 251-row `power` bank; all three are
`nn.Embedding` initialized sinusoidally (`config.py:51-62`;
`ppo_core.py:326-328, 376-384, 519-546`). HP is therefore a **101-way
categorical**, not a scalar and not Wang's 7 bins.

## 2. ps-ppo — the eleven questions `[src]`

**(1) Items.** One embedding id per mon (`obs_pokemon.py:235`) plus one flag
(`mechanics_raw[0]`, `:280`). Three states are distinguishable, two by design.
**Unknown**: poke-env leaves `_item = "unknown_item"` (`pokemon.py:114`) and
`vocab.json` carries a dedicated `unknownitem` row (index 54 → id 55 after
`get_id`'s +1, `utils.py:88-106`), so an unrevealed item gets its own trainable
embedding. **Known**: its own id. **Consumed / knocked off**: `end_item` sets
`_item = None` (`pokemon.py:405-406`), `get_id` returns **0** (the pad/OOV id) and
the flag fires. That flag is mislabelled and inverted — its comment calls it fog
of war, but `1.0 if not mon.item else 0.0` is False for `"unknown_item"` and True
for `None`, so it is an **item-consumed** bit, not an item-unknown bit.
**No original-item memory**: 0.15.0 has none and ps-ppo adds none. The only trace
is a one-turn slot — `-enditem` / `-item` writes the id into `transition_ids[8|9]`
(`obs_transitions.py:372-374`), cleared next turn.

**(2) Abilities.** Four embedding ids per mon (`obs_abilities.py:21, 51-79`): slot
0 = the confirmed ability (`mon.ability`; `None` → id 0), slots 1-3 = the first
three entries of poke-env's `possible_abilities`, **always filled, for own mons
and for mons whose ability is already known**. Unknown is represented twice: id 0
in slot 0, and a bit at `mechanics_raw[1]` (`:281`) — this one is correct, because
`_ability` genuinely defaults to `None` (`pokemon.py:84`). There is **no
`unknownability` vocab row**; the pad id doubles as unknown. 271 abilities → a
272-row table (`obs_assembler.py:305`).

**(3) Opponent stats — the belief range.** `get_combat_bounds`
(`obs_pokemon.py:97-206`) returns `(min, est, max)` for atk/def/spa/spd/spe, 15
numbers per mon: `stat = int(((2*base + iv + ev//4) * level)/100) + 5` once per
bound, then `final = min(int(stat * mult), 799)` (799 = the stat-bank cap),
with `min_iv = est_iv = max_iv = 31` and `min_ev = est_ev = max_ev = 85` for gen9
randbats (`:104-105`), then: **atk** `min_iv, min_ev = 0, 0` unless a physical move
outside `{foulplay, bodypress, rapidspin}` is revealed, restoring 31/85
(`:110-119`); **spe** `min_iv, min_ev = 0, 0`, and a revealed Trick Room or Gyro
Ball sets `est = max = 0` (`:121-130`); **items** (`:151-200`) a *known* Choice
Scarf/Band/Specs, Thick Club, Light Ball, Assault Vest or Eviolite multiplies
**all three** by 1.5 while an *unknown* item multiplies **only max** by 1.5;
**abilities** a *confirmed* speed/atk/def doubler multiplies all three by 2.0,
otherwise any `possible_abilities` doubler multiplies **only max** by 2.0.
So the spread is a belief over **item and ability** plus an atk/spe investment
prior — **not** over EVs/IVs, which are pinned at the randbats constants. HP is
separate and a point estimate (`estimate_stat`, `:63-84`).
**The item half is dead in practice**: `item_unknown = not bool(item)` (`:144`) is
False for `"unknown_item"`, so the widening fires only when the item is *gone* —
the opposite of the intent. The ability half works.

**(4) Boosts.** **7 stats × 13-bin one-hot** = 91 dims per mon, stage + 6
(`obs_pokemon.py:257-263`), fed to the trunk raw (`ppo_core.py:541`). Accuracy and
evasion included.

**(5) Multi-turn state.** Thin and inconsistent. **Sleep / toxic**: ONE shared
9-bin one-hot over `mon.status_counter` clipped to `[0,8]` (`:275-276`) — poke-env
uses the same field for both statuses, so only the status one-hot disambiguates,
and toxic saturates (its ramp runs past 8). **Protect streak**: a **raw unscaled
integer** (`:283`). **Encore / taunt / lock durations: not carried** —
`mon.effects` is a `Dict[Effect, int]` whose int is poke-env's turn count, and
ps-ppo writes 1.0 into a 156-wide presence one-hot, **discarding the counter**
(`:306-313`). **Substitute HP**: not carried (one bit in that one-hot). Extras:
`4 - len(mon.moves)` as a "move slots still hidden" scalar (`:282`) and
`first_turn` (`:284`).

**(6) Weather / field / side conditions** (`obs_global.py`, 41 dims). Weather =
5-wide one-hot + a **10-bin two-hot duration** (`:18-29`) — but the duration reads
`getattr(battle, 'weather_duration', 0)` and **0.15.0's `Battle` has no such
attribute** (confirmed against `ps-ppo/type_schema.json`'s own dump of `Battle`
and by grep over the installed package), so the block is a constant `bin0 = 1.0`
whenever weather is up: **weather duration is dead code.** Fields = 5-wide
presence one-hot, no duration (`:31-41`). Side conditions = 9 wide × 2 sides at
`min(1.0, val/3.0)` — layers for Spikes, but poke-env stores a *turn stamp* for
screens, so a screen encodes as `turn/3` clipped at 1.0, i.e. presence after three
turns (`:43-58`). No "permanent" bin anywhere.

**(7) Hidden-information sentinels.** Index 0 is reserved across every embedding
table for pad / None / OOV (`utils.py:76-106`). An **unrevealed opponent mon is a
frozen zero row**: only the `pos_raw` slot one-hot is written before the
`mon is None` return (`obs_pokemon.py:223-231`), every id stays 0, and there is no
trainable "unknown mon" token. Per-field unknown symbols exist for **moves** (a
real `unknown` row in `move.id`, written for revealed mons with empty slots,
`obs_moves.py:120-122`) and **items**, but not for abilities or species.

**(8) Move features.** `base_power` raw int → the `power` bank; accuracy
normalized to 0-100; `current_pp` raw int; **13-bin priority one-hot**
(`obs_moves.py:21-22, 140-143`); type / category / target one-hots; **`stab_flag`**
= `move.type in [type_1, type_2]` (`:157-163`); `expected_hits`; `status` one-hot
+ `status_prob`, the secondary-effect chance (`:165-179`); `is_available`;
`owner_raw` / `slot_raw` positional identity so empty slots keep coordinates.
**No type-effectiveness term anywhere in the tree** `[src]` `[lit]`. Two fields do
not fire at HEAD: `self_boost_sum` tests `move.target in ("self","allAlly")`
(`:136`) against a `Target` **enum** (`type_schema.json`: `Move.target: "Target"`)
— always False; and the Tera-STAB expansion tests
`getattr(mon,'terastallized',False)` (`:159`) when 0.15.0's attribute is
`is_terastallized`, while `obs_pokemon.py:274` checks **both** spellings, so the
body's tera flag works and the move's does not. Base-type STAB is fine (enum vs
enum). Opponent move slots are in **reveal order** (`obs_moves.py:105`).

**(9) Temporal features.** A 100-dim last-turn block: 10 ids (both sides' move,
actor, target species, ability, item) plus 2 × 45 scalars — 38 event flags (moved
first, crit, super-effective, resisted, immune, failed, fainted, damaged, healed,
status set/cleared, item changed, volatile set/cleared, form changed, pivot
switch, eight `[from] ...` source flags) and 7 per-stat boost deltas scaled 1/6
(`obs_transitions.py:21-97, 210-374`). Above that a **64-turn KV cache and a
256-turn training sequence** (`config.py:68, 169`).

**(10) Vocab and OOV.** A static committed `vocab.json`, gen9-shaped, **not
regenerated per format**: species 572, abilities 271, moves 350, items 60, types
20, volatile effects 155, statuses 7, side conditions 8, weather 4, fields 4,
targets 11, categories 3, genders 3; tables sized `len+1`
(`obs_assembler.py:303-307`). OOV → id 0 **and** an increment of a global
`UNKNOWN_ENTITIES` counter for offline analysis (`utils.py:98-106`) — an OOV
telemetry channel we do not have.

**(11) Generation-conditional.** Nothing is; the encoder is gen9-only by table. A
gen4 port must replace the item/ability multiplier frozensets (`_SPD_BOOST_ITEMS`
= assaultvest/eviolite and `_DEF_DOUBLERS` = furcoat are gen5+/gen6+;
`_EXCLUDED_PHYSICAL` includes bodypress, gen8+) `obs_pokemon.py:89-95`; the
21-wide type block (Fairy, Stellar); the weather vocab (has `snowscape`, **lacks
`hail`** — a gen4 hail goes OOV to id 0 and writes nothing); the side-condition
vocab (**lacks gen4's Safeguard, Mist and Lucky Chant** — silently dropped); the
whole Tera apparatus; and the EV/IV constants. **But the stat closed form ports
cleanly**: IV 31 / EV 85 / no nature is *exactly* gen4 randbats' rule —
`stat = floor((2*base + 52) * level/100) + 5` (`pokeenv_gen4_survey.md` §3.3
`[src]` `[tree]`; **no nature field is emitted at gen4**,
`showdown_gen4_pool.md:518-533` `[tree]`) — and gen4's evidence rules are
*stronger* than gen9's, since `evs.atk = 0` on physical-less sets and
`evs.spe = 0` on Gyro Ball / Metal Burst / Trick Room sets are
generator-deterministic where ps-ppo must infer them from revealed moves.

**One layout-derived defect, recorded for §8(7)** `[src]`: HEAD's faint reward
reads `faint_internal_idx` = 125 (`obs_pokemon.py:43`, computed *after*
`flags_raw` advanced `curr` past its block) while the fainted flag is written at
112 + 1 = **113**, as `obs_assembler.py:302` says. Index 125 is
`mechanics_raw[1]`, the ability-unknown bit, so `worker.py:558-568` shapes reward
on ability-reveal transitions.

## 3. Metamon — the 87-token schema `[src]`

**87 word tokens plus 48 numerical features** (`Metamon p.6`, `p.7 Fig 5`,
`p.27 E.2`). The paper defers the numerics "to the open-source release", giving
only "base power and accuracy of moves and the health/stats/boosts of Pokemon"
(`p.27`). The token schema is fully readable from two worked examples — Figure 5
(`p.7`, Gen 3 UU) and Figure 23 (`p.26`, a **Gen 4 NU** replay) — and the slot
arithmetic closes exactly at 87:

| block | tokens | contents, verbatim from `p.26` Fig 23 |
|---|---|---|
| format | 1 | `<gen4nu>` |
| request type | 1 | `<anychoice>` |
| own active | 1 + 7 | `<player> piloswine lifeorb oblivious ground ice noeffect nostatus` = species, item, ability, type, type, effect, status |
| own moves | 4 × (1+3) = 16 | `<move> earthquake ground physical` = name, type, category |
| own bench | 5 × (1+8) = 45 | `<switch> haunter lifeorb levitate <moveset> shadowball sludgebomb substitute thunderbolt`; an unavailable slot is `<switch>` + **8 × `<blank>`** |
| opponent | 1 + 7 | `<opponent> electrode unknownitem unknownability electric notype noeffect nostatus` |
| conditions | 1 + 3 | `<conditions> noweather noconditions noconditions` (Fig 5: `... noconditions reflect`) |
| last moves | 2 + 2 | `<player_prev> earthquake <opp_prev> nomove` |
| **total** | **87** | |

87 is the paper's stated length (`p.7 Fig 5` caption); the per-block split is this
note's arithmetic and is the only split consistent with all three examples. The
two `<conditions>` slots after weather are unlabelled in the paper.
**Ordering is alphabetical.** Moves (`avalanche earthquake stealthrock stoneedge`;
`encore perishsong protect surf`) and bench slots (`haunter jynx magmortar
magneton politoed`) are alphabetical in every example, which is what `p.28 E.3`
states for the action correspondence. The **two type slots are also
alphabetical**, with `notype` as filler: `fire notype` (Magmortar), `notype water`
(Politoed), `notype psychic` (Hypno), `dark poison` (Skuntank), `rock water`
(Relicanth) — this last is the note's inference from six examples; the paper does
not state it for types.

## 4. Metamon — the eleven questions `[src]`

**(1) Items.** One word token; `unknownitem` is a real vocabulary token, used for
the opponent's active mon on every turn of `p.26` Fig 23. Own mons carry the true
item — the reconstruction pipeline infers unrevealed private state and backfills
it (`p.21 D`). **No consumed/knocked-off distinction and no original-item memory**
appear in the schema; recovery is left to memory over up to 200 turns
(`p.28 Table 3`).
**(2) Abilities.** One word token with an `unknownability` sentinel (`p.7 Fig 5`,
`p.26 Fig 23`). **No possible-ability list, no belief of any kind.** Vocabulary
size is not stated: "tokenizing the Pokemon vocabulary based on our dataset with
an `<unknown>` token for rare cases we may have missed" (`p.6`).
**(3) Opponent stats.** **No stat belief.** Stats appear only inside the 48
numerics, described in one line (`p.27 E.2`); whether *opponent* stats are present
at all is **not stated**, and no formula appears anywhere in the PDF. Not read,
because it is not there.
**(4) Boosts.** In the 48 numerics; **the form (scalar vs one-hot) is not stated**
(`p.27 E.2`).
**(5) Multi-turn state.** Effectively absent. Each Pokemon has **one** effect slot
(`noeffect` sentinel), so at most one volatile is representable, presence-only, no
duration. No sleep or toxic counter, protect streak, encore/taunt duration or
substitute HP appears in the 87 tokens, and the paper claims none in the numerics.
**PP is deliberately excluded**, with a stated reason and a stated cost: "we
ultimately exclude them from the observation space. We decided to protect against
sim2sim gaps... Our final policies are actually strong enough that PP stall losses
are their most noticeable flaw and the leading cause of invalid action selections"
(`p.27 E.2`). The bet is that a 200-turn causal transformer reconstructs the rest;
the supporting anecdote is Sleep Clause compliance (same page).
**(6) Weather / field / side conditions.** Three tokens: one weather slot
(`noweather`), two condition slots (`noconditions`). **Presence only, no
turns-left, no permanent flag** — and a hard capacity limit of one named condition
per side, so Spikes + Stealth Rock + Reflect cannot coexist in the observation.
**(7) Hidden-information sentinels.** Four kinds, all lexical: `<blank>` for an
unavailable bench slot (a fainted teammate becomes 8 blanks, `p.26` Fig 23 obs
#25); `unknownitem` / `unknownability`; `noeffect` / `nostatus` / `noweather` /
`noconditions` / `nomove` / `notype`; and a global `<unknown>` for OOV (`p.6`).
**The opponent's five non-active Pokemon are not represented at all** —
"observations only include the opponent's active Pokemon... relying entirely on
memory to infer the opponent's team" (`p.6`), justified as avoiding "distribution
shift over features of the opponent's full team as it is slowly revealed."
**(8) Move features.** Name, type, category as tokens; base power and accuracy in
the numerics (`p.27 E.2`). **No priority, no STAB flag, no expected hits, no
secondary-effect probability, no PP.**
**(9) Temporal features.** `<player_prev>` / `<opp_prev>` — the last move of each
side, `nomove` sentinel — plus the **previous action as a one-hot and the previous
reward** as policy inputs, the latter explicitly to "resolve some ambiguity over
the outcome of the previous turn (e.g., did the move hit and deal damage?)"
(`p.27 E.2`), plus max context 200 turns, 128 for Large (`p.28 Table 3`).
**(10) Vocab and OOV.** Dataset-derived, size unstated, with an `<unknown>` token
(`p.6`).
**(11) Generation-conditional.** The format is the first token (`<gen4nu>`,
`<gen3uu>`), so one model spans generations and tiers; the schema is otherwise
generation-agnostic by being coarse. The action space is **9** (4 moves + 5
switches, `p.28 E.3`) and **the mask is fed in as an observation feature**, not
applied to logits: "Invalid actions are also noted in the observation. If the
agent selects an invalid action, it is replaced by a random valid action"
(`p.28 E.3`).

## 5. Comparison table

Units: "dims" = observation dimensions. OURS = `encoder_requirements.md` §3-§4
PROPOSAL (nothing built, nothing measured).

| feature | ps-ppo `[src]` | Metamon `[src]` | Wang (`wang_thesis.md` §2.2/§2.3) | OURS (proposal) | evidence for the difference |
|---|---|---|---|---|---|
| opponent bench visible | yes, 6 slots (zero rows until revealed) | **no — active only** | yes, 6 slots + `unknown` flag | yes, 6 slots + `revealed` flag | Metamon states a reason (memory beats distribution shift, p.6); no ablation |
| item, unknown | dedicated `unknownitem` embedding row | dedicated `unknownitem` token | **unstated**; no per-field unknown symbol | 3-state (unknown/held/consumed) + 5 class bits + id | 3 of 4 converge on a dedicated unknown-item symbol; none reports evidence |
| item, consumed | id 0 + a bit (accidental, `obs_pokemon.py:280`) | not represented | not represented | explicit `is_consumed` bit | H&L's `prevItem` is the only prior art (`encoder_requirements.md` §5) |
| original-item memory | no (a one-turn transition slot only) | no | no | wrapper-tracked (survey G-list) | Wang's own fork adds `_orig_ability` but **not** `_orig_item` (survey §6) |
| ability, unknown | pad id 0 + a bit | dedicated `unknownability` token | unstated | 2-state (unknown/known) + 12 class bits + id | — |
| possible-ability belief | **yes**, 3 extra embedding slots | no | no | no (a set-prior slot instead, §3.5) | at gen4, 277/295 species have one set-listed ability, so the list collapses for 94% of the pool `[tree]` |
| opponent stats | **(min, est, max) × 5**, closed form + item/ability multipliers | not stated | **none** | closed form, parallel table (Q29) | ps-ppo is the only prior art; its EV/IV constants are gen9's, its structure is gen4-valid |
| HP | 101-way categorical (`val_100` bank) | in the 48 numerics, form unstated | **7 bins** (0 + 6 equal) | scalar | Wang footnotes his bins as "arbitrarily chosen" — the only stated rationale, and it is an admission |
| boosts | **7 × 13 one-hot** (91 dims) | in the numerics, form unstated | **7 × 13 one-hot** (91 dims) | 7 scalars | two of four use identical 13-bin one-hots; neither justifies it |
| sleep / toxic counters | one shared 9-bin one-hot, clipped at 8 | absent | **21-bin toxic + 11-bin sleep** | two scalars (/4, /16) | Wang states the Markov-restoration rationale (§2.1); nobody scalarizes but us (Q13) |
| encore / taunt / lock duration | **discarded** (presence one-hot only) | absent | 9- / 6-bin one-hots | scalars (/8) | — |
| protect streak | raw unscaled int | absent | 6-bin one-hot | scalar (/4) | — |
| substitute HP | no | no | no | **scalar, from `_replay_data`** (A10) | ours alone |
| weather | 5-hot + a **dead** 10-bin duration | 1 token, presence only | 4 × 9 one-hot **with a Permanent bin** | 4-hot + turns/8 + **indefinite bit** | Wang states the gen3-5 permanence rule; tree-verified in our sim |
| fields / terrain | presence one-hot | folded into `<conditions>` | Trick Room 7-bin duration | Trick Room + turns, Gravity | — |
| side conditions | 9 × 2, `min(1, val/3)` (screens degrade to presence) | **2 slots total, 1 per side** | per-side layer/duration one-hots (SR 2, Spikes 4, TSpikes 3, screens 10, Safeguard 7) | per-side 9 blocks, layers vs elapsed | Metamon's 2 slots cannot represent a gen4 hazard stack; ours and Wang's can |
| hidden rows | frozen zero row + slot one-hot | `<blank>` × 8 | `unknown` flag ("all other values are 0") | `revealed` flag prefix | all four use a frozen-zero convention |
| move: base power | raw int → 251-row bank | in numerics | **absent** | scalar /100 | Wang encodes no move properties beyond identity + PP |
| move: category | one-hot | token | **absent** | bit | gen4 makes this per-move, not per-type |
| move: priority | **13-bin one-hot** | absent | absent | scalar / 7 | ps-ppo alone bins it |
| move: STAB | **flag** (base types work; the tera branch is dead) | absent | absent | absent (we precompute effectiveness instead) | the index's standing argument: a flat MLP needs composed terms MORE `[lit]` |
| move: expected hits | scalar | absent | absent | in the effect block | — |
| move: secondary-status probability | **status one-hot + `status_prob`** | absent | absent | inflicted status one-hot + probability | ps-ppo and ours converge |
| move: PP | raw int → bank | **deliberately excluded** | ⌊∛pp⌋/4 | raw scalar | Metamon states the reason AND the cost (p.27) |
| type effectiveness | **none precomputed** | none | none | **precomputed both sides + ability-aware** | ours alone; the index calls this the exact inverse of ps-ppo `[lit]` |
| temporal | 100-dim last-turn block + 64-turn KV cache | last move ×2 + prev action + prev reward + 200-turn context | last-used move id per mon | **none in v1** (Q14 / A11) | we are the only single-snapshot design of the four |
| OOV | id 0 + a global counter | `<unknown>` token | unstated | row 0 | ps-ppo's OOV telemetry has no analogue in ours |
| action mask | **fed in as an observation feature** | fed in as an observation feature | `-inf` on logits | `-1e8` on logits (harness contract) | Metamon: test-time masking "predictably made little difference... though it may improve value estimation during training" (`p.23 D.1`) |
| total | 8,567 dims | 87 tokens + 48 numerics | 3,725 dims | ≈ 1,180-1,376 dims (illustrative) | — |

## 6. Where our proposal differs from all three

1. **Counters as scalars.** ps-ppo (partly), Metamon (not at all) and Wang (12
   duration one-hots) all avoid our form. Wang is the only one who argues for his
   (`wang_thesis.md` §2.1: Markov restoration for a **feed-forward** policy — our
   architecture class). **Q13's losing argument now has a second supporter and
   none against**: nobody in this literature encodes a duration as a scaled
   scalar, and nobody ablated it either.
2. **Precomputed type effectiveness.** None of the three computes it; we compute
   it on both sides and want it ability-aware. Our largest divergence —
   defensible (they use attention, we do not) but unmeasured here.
3. **Substitute HP as a scalar.** Nobody carries it.
4. **No temporal features.** All three carry at least a last-move token; two carry
   long context windows. We are the only single-snapshot design; Q14 defers this.
5. **A set prior over opponent moves.** None of the three has any belief feature
   (Wang explicitly: "there is no belief / set-prior feature", `wang_thesis.md`
   §2.3). ps-ppo's `possible_abilities` slots are the closest analogue, and at
   gen4 they would be near-constant for 94% of the pool.

Two places where we are **not** alone and should say so: the three-state item
representation (ps-ppo and Metamon both carry a dedicated unknown-item symbol) and
ability-as-embedding-id (all four).

## 7. Does any of them report evidence?

**No observation-design ablation exists in either system.** What does exist:

- **Metamon, two nulls** `[src]`: the `<unknown>`-token augmentation — "We do not
  find evidence that this strategy impacts performance" (`p.6` fn 3), a null on
  forcing the policy to recover masked observation tokens from memory; and
  post-paper invalid-action masking, "predictably made little difference when
  enforced only at test time — though it may improve value estimation during
  training" (`p.23 D.1`). Both stated without numbers; neither is an
  observation-content ablation.
- **Metamon, one stated reason with a stated cost** (`p.27 E.2`): PP excluded to
  avoid sim2sim gaps; PP stalls became "the leading cause of invalid action
  selections" — the closest thing to negative evidence about an encoder omission
  anywhere in the four systems, and it argues **for** carrying PP. A second
  stated reason carries no evidence at all (`p.6`, the opponent bench omitted to
  avoid distribution shift).
- **Wang**: one rationale (Markov restoration, §2.1) and one admission
  ("Arbitrarily chosen", the HP bins, §2.3). No ablation.
- **ps-ppo**: no rationale in any docstring or comment for any choice above, and
  no evaluation script against a fixed opponent ever existed
  (`docs/prior_work/README.md:486-489` `[lit]`); its only screen was
  "configurations that failed to imitate perfectly were discarded" `[lit]`, an
  architecture criterion, not an observation one.

Consequence: **the comparator columns are precedent, not evidence.** No row of §5
is a measured reason to prefer a form, and none of these choices has been credited
under this repo's credit line by anyone.

## 8. What this changes in the five docs

Concrete and cited; **this note edits none of them.**

1. **`encoder_requirements.md` §5, third bullet** (`:372-376`, "ps-ppo / Metamon:
   **not read this cycle**... deferral D2") — replace with the read. Two `[lit]`
   sentences need correcting: "its stats as (min, est, max) belief ranges" is
   right about the shape and **wrong about the variable** (the range is over
   *item and ability*; EVs/IVs are pinned at the randbats constants,
   `ps-ppo/obs_pokemon.py:104-105, 143-200`); and "boosts as 7×13 one-hots"
   upgrades to `[src]` (`:257-263`), with the addition that **Wang uses the
   identical 7 × 13 form** — two of four, not one.
2. **§3.2 (counters)** — add the third comparator: nobody in this literature
   scalarizes a duration; ps-ppo *discards* poke-env's per-effect counters
   (`obs_pokemon.py:306-313`) and clips its one shared status counter at 8, which
   saturates the toxic ramp (`:275-276`). Strengthens A7's losing side; belongs in
   Q13.
3. **§3.4 (items vocab)** — our "40 + row 0 unknown + a `none` row" is the same
   three-state design ps-ppo reaches (by accident) and the same unknown-item
   sentinel Metamon uses lexically. Record the convergence under Q11; it is the
   only place our proposal has independent support from both comparators.
4. **§4.1 (ability state: 2 bits)** — record what we decline: ps-ppo's 3-slot
   `possible_abilities` block (`obs_abilities.py:65-79`). At gen4, 277/295 pool
   species have a single set-listed ability (`encoder_requirements.md` §3.5
   `[tree]`), so the block would be near-constant for 94% of the pool — a stronger
   argument for our choice than the doc makes. Belongs beside Q11.
5. **`open_questions.md` §7 D2** — mark **discharged**, pointing here, and note
   that the "direct comparators for Q11 and Q29" turned out to be one comparator
   (ps-ppo) plus a system that carries neither feature (Metamon).
6. **`open_questions.md` Q29 (opponent stats)** — the recommendation (a parallel
   table, not mutating `Pokemon.stats`) is what the only prior art does
   (`obs_pokemon.py:97-206` computes and returns; it never writes back). Add that
   ps-ppo returns **(min, est, max)**, not a point estimate, and that its closed
   form is structurally identical to the survey's gen4 form
   (`pokeenv_gen4_survey.md` §3.3) because gen4 randbats is EV 85 / IV 31 /
   nature-neutral (`showdown_gen4_pool.md:518-533` `[tree]`). Whether we adopt the
   3-wide range or a point estimate is a **new sub-question** this note raises and
   does not decide.
7. **`open_questions.md` Q43 (prior-work index corrections owed)** — three more,
   all `[src]`: (a) the "belief range over hidden EVs/IVs" phrasing at
   `docs/prior_work/README.md:449-451`; (b) the tera-STAB defect is an
   *attribute-name* mismatch at `ps-ppo/obs_moves.py:159` (`terastallized` vs
   0.15.0's `is_terastallized`), **distinct** from the `Target`-enum defect at
   `:136` that kills `self_boost_sum`, and `obs_pokemon.py:274` checks both
   spellings so the body flag is fine; (c) HEAD's faint reward reads index 125
   (the ability-unknown bit) rather than 113 — a live off-by-12 the index's "fixed
   at `17e0955`" line (`:536-538`) does not cover.
8. **`anchors_and_eval.md`** — Metamon's PP omission and its stated cost
   (`Metamon p.27 E.2`) is the one piece of negative evidence in this literature
   about an encoder omission, and it supports keeping PP in the gen4 move block.
   Its masking sentence (`p.23 D.1`) sits beside our harness contract: both large
   systems feed the mask in as an observation feature; we mask logits. Neither is
   refuted.
9. **`pokeenv_gen4_survey.md` §4 / Q28 (weather duration)** — ps-ppo is a
   documented instance of the failure this gap causes: a 10-bin weather duration
   reading `battle.weather_duration`, which 0.15.0 does not have
   (`obs_global.py:25`), so the block is a constant. Cite it as precedent for
   wrapper-tracking the start turn rather than trusting an attribute.

`mechanics_delta.md` needs no change: neither system is a rules authority.

## 9. Not read

- ps-ppo's `learner.py`, `train.py`, `inference.py`, and `worker.py` outside
  `:540-580` and the event plumbing at `:211-320, 452-500`.
- ps-ppo's deleted `eval.py` / `eval_policy_improvement.py` (recoverable at
  `7fb522c^`) and the `1b13ae0` (Elo-screenshot) revision of the obs files.
  **Every ps-ppo line number here is HEAD**, and the index warns the laddered
  system is the `7fb522c`-era one `[lit]` (`docs/prior_work/README.md:527-531`).
- Metamon's code release: the 48 numerical features, the boost/stat encoding and
  the tokenizer vocabulary sizes are **not in the PDF** and are not read.
- The Wang column is `wang_thesis.md` §2.2/§2.3/§13 only; his PDF was not
  re-opened.

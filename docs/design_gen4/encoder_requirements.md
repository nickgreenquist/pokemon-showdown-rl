# encoder_requirements.md — the gen4 `EncoderSpec`, designed against the landed F-08 seam

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
> brief's two-memo (evidential-validity / build-ops) + adversarial-synthesis
> cycle was NOT run for this doc (maintainer ruling 2026-09-04, budget; the
> 2-Opus cycle is reserved for irreversible artifacts and this doc is free to
> rewrite). §10 records each design choice with its losing argument in the
> house style, as a single writer's adjudication.
>
> **Verification status per claim** — every claim carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo at
>   main@2738025 (the landed seam `rl/envs/encoder_spec.py`, `rl/envs/showdown.py`,
>   `tests/test_encoder_spec.py`, `rl/networks/*`) or the vendored `showdown/`.
> - `[src]` **source-verified** — installed poke-env 0.15.0, Wang's thesis
>   text, the H&L paper text / metagrok clone.
> - `[lit]` **literature-only** — the prior-work index or a secondary source.
> - `[live]` **needs-live-verification** — BARRED until the live ladder run
>   and any later fleet complete; the check is stated.
> Everything under "PROPOSAL" is a design recommendation, not a fact; it
> carries no tag and nothing of it exists in the tree.
>
> **The seam this is designed against is LANDED CODE:** `rl/envs/encoder_spec.py`
> (main@2738025, F-08, merged 2026-09-04) — a frozen `EncoderSpec` dataclass,
> `GEN1`, `spec_for_format` refusing every other generation with a work list.
> The brief's fallback ("if the seam isn't written yet, design the interface
> you need") no longer applies; where this doc asks for fields the dataclass
> does not have, they are marked **reconcile at merge**.
> **Sources read for this doc:** research notes `our_encoder_seam_inventory.md`
> (the seam and every gen1 assumption outside it, 54 rows), `showdown_gen4_pool.md`
> §9–11 (vocabularies), `showdown_gen4_abilities_items.md` §4–6, `wang_thesis.md`
> §2/§13 (Tables A.1/A.2), `huang_lee_metagrok.md` §2–3/§6, and the two
> preceding docs in this directory. `mechanics_delta.md` §15 and
> `pokeenv_gen4_survey.md` §3–6/§9 are consumed, not restated.
> **Feeds:** `open_questions.md` (§11), `anchors_and_eval.md` (§7 process model).
> **Reconcile at merge:** the F-07 `encoder:` config block
> (`docs/proposals/F07_encoder_config_block.md`) is unruled; §7 assumes its
> `spec:` key as the selector and says what changes if it is not adopted.

## 0. Summary

| axis | gen1 (`GEN1`, untouchable) | gen4 (this proposal) |
|---|---|---|
| action space | 10 | **10 — unchanged** (`SinglesEnv.get_action_space_size(4)`; the seam's refusal list does not name an action head at gen 4) `[tree]` `[src]` |
| block order | global \| own mons ×6 \| own active \| own moves ×4 \| opp mons ×6 (+revealed) \| opp active \| opp moves ×4 \| id suffix | **same order**, so the tokenizer's 21-token reshape (1 field + 12 mons + 8 moves) and the pointer head over 6 + 4 entities carry over |
| types | 15 | **17**, listed explicitly (poke-env's chart has 18 keys) |
| base stats | 5 (spd mirrored) | **6** |
| statuses / boosts | 6 / 7 | 6 / 7 — unchanged |
| volatiles | 7 flags + 1 counter + preparing | **18** flags + **6 counters** (sleep, toxic, protect, encore/taunt/lock, sub HP, perish) |
| items / abilities | none | **two new per-mon fields each**: id (embedding index) + class bits + reveal state |
| global | 6 scalars | 6 + weather (4 + turns + indefinite) + fields (2 + turns) + two side blocks (9 each, layers vs elapsed) + `maybe_trapped` |
| move block | 8 scalars + 15 types + v2 effect block (23) | 9 scalars (+crit stage) + 17 types + a gen4 effect block (~32 extractors) |
| set prior | gen1 `data.json` sampler | a gen4 `sets.json` role-conditioned prior (moves + ability + level); items by generator rule |
| ids | dex `num`, `/256`, vocab 152 / 166 | **forme-id strings, pool-local**: species 300, moves 182, abilities 101, items 40; `/256` kept |
| OBS_DIM (v2+ids) | 828 | ≈ **1,183–1,376** (illustrative; §4.7 gives the full-width and the lean sketch; the v0.1 build lands at **1,448** — §13) — every existing checkpoint invalidated, by design |

Three facts drive everything: **(1)** the seam already parameterizes 11 data fields and 12 derived offsets and refuses gen 4 with an eight-item list (§1); **(2)** the four gen4 additions that change the vector's width (SpD, items, abilities, global state) are unavoidable, so the gen4 encoder is a **clean break** with no gen1 checkpoint compatibility (§10 A12); **(3)** no gen4 tape can be collected until the ladder run ends, so the gen4 bit-identity gate — the seam's own safety instrument — cannot exist before then (§8).

## 1. The landed seam: what it gives, what it refuses

`[tree]` `rl/envs/encoder_spec.py` (main@2738025). The frozen dataclass carries
`gen, types, statuses, boost_keys, base_stat_keys, volatiles, special_move_ids,
species_num_range, move_num_range, n_switches, n_moves` and derives
`type_index, status_index, n_*`, `n_actions` (= `SinglesEnv.get_action_space_size`),
and the v1 intra-block offsets `mon_status_off=3 → mon_level_off → mon_stats_off →
mon_types_off → mon_matchup_off → mon_dim_v1`, `active_volatiles_off →
active_counter_off → active_dim`, `move_type_off=8 → move_dim_v1`
(`encoder_spec.py:83-190`). Every one of them is genuinely read off the `spec`
argument in `rl/envs/showdown.py` (`_fill_mon :200-213`, `_fill_active :225-233`,
`_fill_move :258-266`, `_fill_ids`, `_species_id :374-382`, `_move_id :384-390`,
`_move_slots_aliased :393-397`), proven by the `_GEN2_SKETCH` threading tests
(`tests/test_encoder_spec.py:371-455`).

**What it refuses**, verbatim (`encoder_spec.py:267-276`):

```
"a per-gen type table (17 types from gen 2, 18 from gen 6)",
"items and abilities blocks (absent in gen 1)",
"weather and side-condition blocks (terrain from gen 6)",
"the gen-2+ volatile set",
f"species and move `num` ranges for gen {gen}",
f"a set prior for the format ({battle_format!r}; randbats_prior.py is gen 1)",
"the v2 effect block off gen-1 Move data",
"per-spec block strides and OBS_DIM (showdown.py derives them from GEN1)",
```

plus, at gen 6+, an action-head line that does **not** fire at gen 4. The class
docstring (`:45-80`) adds the six-stat note, the Reflect/Light Screen relocation,
and the counter-semantics note. `embed_battle` refuses by identity
(`showdown.py:288-295`, `spec is not GEN1`), because the module strides are
derived from the singleton at import — that is the one structural change this
proposal needs (§4.8).

**The work list is accurate but incomplete.** The seam inventory found 54 gen1
assumptions outside the spec; the ones the docstring does not name and this
proposal must own `[tree]`: `priority / 5.0` leaves the declared `Box(low=-1)` at
gen 4 (Trick Room −7 → −1.4, Roar/Whirlwind −6 → −1.2); dex `num` is not injective
over gen4 formes (34 pool species share six numbers: Arceus ×17 → 493, Rotom ×6 →
479, Deoxys ×4 → 386, Wormadam ×3 → 413, Giratina ×2, Shaymin ×2); the type-chart
matchup scalars ignore abilities (`_best_multiplier`, `showdown.py:182-188`; poke-env's
`damage_multiplier` takes no ability); the tokenizer's vocab defaults 152 / 166
**clamp** out-of-range ids onto the last row rather than erroring
(`rl/networks/entity_deepsets.py:143-144, 167-168`); `status_counter / 16` conflates
sleep and toxic (`showdown.py:234`); `ENCODER_FINGERPRINT` records no generation
(`showdown.py:150-158`); `fake_spaces()` is called with no format at three sites
(`rl/train.py:104, 480`; `scripts/eval_checkpoint.py:81`) and `eval_checkpoint.py:103`
hardcodes gen1 for seat 2; `_move_slots_aliased` approximates poke-env's real
re-basing rule (`avail[0] not in known_ids`, not `SPECIAL_MOVES` membership;
`poke_env/environment/singles_env.py:122-127`); and the whole `rl/search/` line is gen1
(a rewrite, not a port — `search_depreciation.md`).

## 2. Hard constraints

1. **gen1 bit-identity.** `[tree]` The tape hash gate pins five encodings
   (`tests/test_encoder_spec.py:66-74`): bare 612 `e0217c10…`, v2 808 `273cd675…`,
   v2+ids 828 `0be192a8…`, bare+noprior 612 `8c2956c4…`, v2+ids+noprior 828
   `ac57b7f8…`, over six local tapes (6,000 decisions; skipped where `data/` is
   absent — a gen4 spec must be validated on the training box). "A changed hash is a
   changed encoding — fix the code, never the golden." Nothing in this proposal
   touches a `GEN1` value or a fill path when `spec is GEN1`.
2. **One process, one encoder.** `[tree]` The flags and strides are read at import
   (`scripts/eval_checkpoint.py:54-58`); the gen4 layout is not a prefix of gen1's,
   so the `PrefixSliceActor` shim (`rl/networks/mlp.py:10-33`) has no analogue. A
   gen1-vs-gen4 cross-play in one process is impossible; gen4 eval harnesses are
   separate processes. Two test files assert gen1 widths at import
   (`tests/test_encoder_ids_tapes.py:51`, `tests/test_encoder_v2.py:23`), so a
   process-global width change breaks collection, not a test (§8).
3. **Harness contracts** (CLAUDE.md): `info["action_mask"]` always emitted; masking
   through `rl/common/masking` with `-1e8`, never `-inf`, at eval too; the value head
   is never masked. Wang masks with `-inf` over ~486 dead logits `[src]`; H&L
   renormalise `[src]` — neither is copied.
4. **OBS_DIM landmine.** Any width change invalidates every checkpoint. Accepted for
   gen 4 (a new model); the cost lands only if the change is applied to the
   gen1 process, which it never is.
5. **No live verification now.** Every protocol-dependent claim below inherits
   `pokeenv_gen4_survey.md` §8's `[live]` checks; the gen4 tape gate waits (§8).

## 3. The GEN4 tables (values)

### 3.1 Fields that only get gen4 values (no dataclass change)

| field | GEN4 value | basis |
|---|---|---|
| `gen` | 4 | — |
| `types` | `(BUG, DARK, DRAGON, ELECTRIC, FIGHTING, FIRE, FLYING, GHOST, GRASS, GROUND, ICE, NORMAL, POISON, PSYCHIC, ROCK, STEEL, WATER)` — 17, alphabetical, **listed, never derived** | `[tree]` Fairy is `'Future'` at gen 4 (`showdown/data/mods/gen5/typechart.ts:93-96`); `[src]` `GenData.from_gen(4).type_chart` has 18 keys and its Fairy column is inconsistent (`poke_env/data/gen_data.py:73-109`); the fill helpers use `type_index.get`, so an unlisted type silently writes nothing — the `_GEN2_SKETCH` test class exists for this |
| `statuses` | unchanged six | `[src]` no new major status |
| `boost_keys` | unchanged seven | `spd` stops being redundant |
| `base_stat_keys` | `("hp","atk","def","spa","spd","spe")` | `[tree]` `mechanics_delta.md` §5 |
| `special_move_ids` | `frozenset({"struggle","recharge"})` | `[tree]` `fight` is a gen1-only wire placeholder (`showdown/sim/pokemon.ts:1105-1112`); `recharge` is near-extinct in the pool (one Giga Impact set) |
| `species_num_range` / `move_num_range` | `(1,493)` / `(1,467)` are correct **but not used** — replaced by vocabs (§3.4) | `[src]` max nums confirmed against `GenData.from_gen(4)` |
| `n_switches`, `n_moves` | 6 / 4 | unchanged |

The type chart source stays `GenData.from_format(battle_format).type_chart`
(already per-format at every production call site `[tree]`, `showdown.py:810, 1008`;
`rl/collect.py:78, 123`; `showdown_async.py:156`), read only through the 17 listed
types. Move category stays poke-env's per-move `move.category` (`showdown.py:258-259`
`[tree]`; `poke_env/battle/move.py:209-215` `[src]`) — no table, exactly as the
docstring says.

### 3.2 Volatiles and counters (the active block)

`[tree]` pool counts from `showdown/data/random-battles/gen4/sets.json` (464 sets);
`[src]` `Effect` membership from `poke_env/battle/effect.py`. PROPOSAL: a flag tuple
and a separate counter tuple, both spec fields.

| flag | poke-env source | in pool | note |
|---|---|---|---|
| SUBSTITUTE | `Effect.SUBSTITUTE` | 44 | plus a **sub-HP scalar** counter (§10 A10) |
| CONFUSION | `Effect.CONFUSION` | Dynamic Punch, Outrage fatigue | |
| LEECH_SEED | `Effect.LEECH_SEED` | 10 | |
| MUST_RECHARGE | the bool `mon.must_recharge` (D13a) | 1 | survives verbatim |
| PROTECT | `Effect.PROTECT` (this turn) | 45 | the consecutive count is `protect_counter` |
| ENCORE | `Effect.ENCORE` (turn-countable) | 24 | move name is dropped by poke-env → read from `_replay_data` (survey G5) |
| TAUNT | `Effect.TAUNT` (turn-countable) | 13 | |
| YAWN | `Effect.YAWN` | 4 | |
| CURSE | `Effect.CURSE` | 11 | ghost-curse residual only; the boost form is in `boosts` |
| DESTINY_BOND | `Effect.DESTINY_BOND` | 4 | |
| ATTRACT | `Effect.ATTRACT` | Cute Charm 7 | |
| FOCUS_ENERGY | `Effect.FOCUS_ENERGY` | 0 (Haze-relevant only) | cheap; keep for the crit model |
| LOCKED_MOVE | `Effect.LOCKED_MOVE` | Outrage 13 | |
| FLASH_FIRE | `Effect.FLASH_FIRE` | 5 species (8 sets) | poke-env clears it one use early (survey G6) — post-process |
| SLOW_START | `Effect.SLOW_START` (turn-countable) | Regigigas | |
| TRAPPED_BY_MOVE | OR of `BIND, WRAP, FIRE_SPIN, CLAMP, WHIRLPOOL, SAND_TOMB` | 0 | carried for robustness; one bit |
| PERISH | which of `PERISH0..3` is present → the counter below | 0 | |
| ROOST | `Effect.ROOST` | 45 | **the type one-hot reads `mon.types` live**, so Roost is carried by the types slot; the flag is optional |

Counters (each one scalar, scaled): **sleep attempts** (`status_counter` when SLP,
/4), **toxic stage** (`status_counter` when TOX, /16), **protect streak**
(`protect_counter`, /4), **lock/encore/taunt elapsed turns** (poke-env's turn-countable
effects count up from 0; /8), **Substitute HP** (tracked from the `-activate …
Substitute|[damage]` lines in `_replay_data`, /0.25 max HP; poke-env carries no sub
HP), **perish** (3 − index, /3). The gen1 slot `status_counter / 16` is replaced by
the first two — a semantics change the docstring already anticipates.

Absent from the pool and **not carried**: Disable, Torment, Embargo, Heal Block,
Ingrain, Aqua Ring, Magnet Rise, Nightmare, Uproar, Bide, Stockpile, Grudge,
Foresight / Miracle Eye, Power Trick, Gastro Acid, Lock-On, Rollout, Charge — all
implemented in the sim, unreachable from any set (`mechanics_delta.md` §14). A
Showdown bump that adds one of their moves to a set is a **pre-reg pin violation**,
not a silent feature change: unknown effects degrade to `Effect.UNKNOWN` and the
encoder writes nothing.

### 3.3 Global state: weather, fields, side conditions

| block | contents | source | note |
|---|---|---|---|
| weather | one-hot over `(RAINDANCE, SUNNYDAY, SANDSTORM, HAIL)` + `turns_elapsed/8` + **`indefinite`** bit | `battle.weather` gives presence only (its int is restamped every `[upkeep]`, survey §4); start turn and `[from] ability:` come from `_replay_data` | Wang's "Permanent" bin `[src]`; the sim sets `duration = 0` for ability weather at gen ≤ 5 `[tree]` |
| fields | `TRICK_ROOM` (+ turns elapsed /5), `GRAVITY` | `battle.fields` (genuine start stamp) | 1 Trick Room set; Gravity 0 |
| own side / opp side | `SPIKES` layers /3, `TOXIC_SPIKES` layers /2, `STEALTH_ROCK` 0/1, `REFLECT`, `LIGHT_SCREEN`, `SAFEGUARD`, `MIST`, `TAILWIND`, `LUCKY_CHANT` (elapsed turns /8) | `battle.side_conditions` / `opponent_side_conditions` (layers for the two stackables, turn stamps otherwise) | only Spikes and Toxic Spikes occur in the vendored pool; Stealth Rock kept as insurance (`mechanics_delta.md` §16 Q1) |
| scalars | `turn/turn_scale`, own faints, opp faints, `force_switch`, `trapped`, **`maybe_trapped`**, aliased | the gen1 six + one | `maybe_trapped` is live only at gen 4 (survey G1) |

Reflect and Light Screen **leave `volatiles`** (they are side conditions from gen 2;
`Effect.LIGHT_SCREEN` does not exist) — the docstring's instruction, executable
with no parser fork `[src]`.

### 3.4 Vocabularies and ids

PROPOSAL: format-scoped, forme-keyed vocab tuples replace the `num` ranges. `[tree]`
sizes from the vendored pool.

| vocab | rows | key | why not `num` |
|---|---|---|---|
| species | **300** + row 0 unknown (295 pool keys + Gastrodon-East + Castform-Sunny/Rainy/Snowy + Cherrim-Sunshine, the only mid-battle formes) | `Pokemon.species` (the forme id string) | 34 pool species share six nums; Arceus-Ghost and Arceus-Water would share a row |
| moves | **182** + row 0 (181 pool moves incl. eight typed Hidden Powers + Struggle) | `move.id` (poke-env restores the typed `hiddenpowerfire`) | all 17 Hidden Power entries share `num` 237 `[src]` |
| abilities | **101** + row 0 unknown | `mon.ability` id string, plus the `-activate`-only six recovered from `mon.effects` (`Effect.SYNCHRONIZE` etc.) | poke-env ships no ability table; the dex-derived `possible_abilities` universe is 122 strings but the generator assigns only the 101 |
| items | **40** + row 0 unknown + a `none` row | `mon.item` id string | poke-env ships no item table; Showdown item nums reach 313 |

`ID_SCALE = 256` **stays** `[tree]`: `id/256` is exact in float32 for every id ≤ 1025
and 300/256 = 1.17 sits inside the declared `Box(-1, 4)`; only the docstring's
`[0, 1)` claim changes (§10 A2). The tokenizer's `species_vocab` / `move_vocab`
defaults (152 / 166) must become required, spec-derived arguments, and construction
must **assert `vocab >= spec.max_id + 1`** instead of clamping. Both vocabs are
frozen artifacts of the vendored `sets.json` at 59da482: unseen strings map to
row 0 exactly as out-of-range nums do today, and the pre-reg pins the Showdown
commit (§10 A1).

### 3.5 The set prior

`[tree]` gen1's `rl/envs/randbats_prior.py` reproduces Showdown's gen1 `randomSet`
from a flat 146-species `data.json`. The gen4 file is a different schema —
`{species: {level, sets: [{role, movepool, abilities, preferredTypes?}]}}`, 295
species, 464 sets, 8 roles — drawn through `randomSet → cullMovePool → getAbility →
getItem` with `MOVE_PAIRS`, `NO_STAB`, hazard and setup counters
(`showdown/data/random-battles/gen4/teams.ts:627-741`); roughly a third of sets are
exact four-move sets and two thirds are sampled from 5–6-move pools; items are not in
the file at all (`getItem`, `:510-626`). PROPOSAL for v1: a **role-conditioned prior
over the union movepool** plus the set-listed ability list and level, harvested from
`sets.json` directly (no sampler port); items by a rule table transcribed from
`getItem`/`getPriorityItem` (40 items, conditions known). The prior fills the same
four probability-weighted opponent move slots `_opponent_move_slots` fills today
(`showdown.py:582-599`), plus one ability-prior slot and one item-prior slot per
opponent mon. 278 of 295 species have a single set-listed ability, so the ability
prior collapses to a one-hot for 94 % of the pool `[tree]`. A faithful port of the
sampler is §10 A6's losing side. `verify_against_showdown` gets the gen4 path.

### 3.6 The gen4 effect block (per move)

`[src]` poke-env's gen4 `Move` already exposes every field a gen4 effect block needs
(`side_condition`, `weather`, `force_switch`, `self_switch`, `slot_condition`,
`volatile_status`, `secondary`, `boosts`, `self_boost`, `heal`, `drain`, `recoil`,
`flags`, `crit_ratio`, `priority`, `breaks_protect`, `is_protect_move`); the
gen1 `_effect_block` builds `Move(id, gen=1)` (`showdown.py:478-480`) and indexes a
six-entry volatile table — both become spec-keyed (`spec.gen`, `spec.move_volatiles`).
PROPOSAL: `effect_features`, an ordered tuple of named extractors (`effect_dim =
len(...)`), for gen 4 ≈ 32: inflicted status one-hot (6) + probability; self-boost
sum, foe-boost sum; heal, drain, recoil fractions; crit-stage bit; multi-hit expected
hits (the gen4 3.0, not poke-env's 3.17 `[lit]`); self-destruct; recharge; charge;
inflicted-volatile one-hot over the §3.2 flags that moves cause; `side_condition`
one-hot (hazard / screen class); `weather`; `force_switch`; `self_switch`;
`contact`, `sound`, `bypasssub`, `punch` flags; protect-class; hazard-removal;
trapping. Plus two per-move overrides the data gets wrong: **Return = 102 BP**
(happiness is always 255 in randbats `[tree]`; poke-env reports 0) and the nine
BP-0 damaging moves (counter, grassknot, lowkick, metalburst, mirrorcoat,
nightshade, return, seismictoss, superfang) get a "variable damage" bit.

### 3.7 Scales

PROPOSAL: `priority_scale = 7.0` (GEN1 keeps 5.0 — bit-identical), `turn_scale`
(gen 4 games are longer; audit F-15), `status_counter` split as in §3.2, base stats
`/255` (unchanged; max is 255), level `/100` (unchanged; 67–100 in the pool), base
power `/100` (max 250 → 2.5, inside the Box).

## 4. Feature blocks and dims (PROPOSAL)

Block order and the 21-token tokenizer layout are preserved. Widths are illustrative
and become exact only when the extractor tuples are frozen.

### 4.1 Mon block (×12; own mons prepend a constant 1.0, opponent mons their `revealed` flag, as today)
hp, fainted, is-active (3) · status one-hot (6) · level (1) · base stats (6) ·
**live types** one-hot (17; from `mon.types`, so Roost / Forecast / Color Change are
carried) · off/def matchup from the chart (2) · **ability-aware off/def matchup**
(2; the chart multiplier folded with the known ability's immunity/resistance class,
0.5 for an unknown two-candidate ability that could be immune — §10 A5) ·
**item state** (unknown / held / consumed: 3) · item class bits (I1–I5: 5) ·
`is_choice`, `is_consumed` (2) · **ability state** (unknown / known: 2) · ability
class bits (A1–A12: 12) · v2 speed edge (1, from `mon.stats["spe"]` for own mons, the
closed-form estimate for the opponent — survey §3.3; the feature INVERTS under Trick Room, critic_pass.md §3). ≈ **62**.

### 4.2 Active extras (×2)
boosts (7) · volatile flags (§3.2, 18) · counters (6) · `first_turn` (1) ·
`preparing` (1) · `choice_locked` (own side from `disabled`; opponent inferred) (1).
≈ **33**. Built v0.1: **15** flags, not 18 — three §3.2 rows (Destiny Bond, a
Protect flag, Roost) are not flags in the layout (Protect rides its counter; Roost
is never visible at a decision) — so the active block is **31** (§13).

### 4.3 Move block (×8; own 4 in move-action order, opponent 4 prior-filled)
known, bp, acc, pp, matchup, physical, status, priority/7, **crit stage** (9) ·
type one-hot (17) · effect block (~32). ≈ **58**.

### 4.4 Global
turn, own faints, opp faints, force_switch, trapped, **maybe_trapped**, aliased (7) ·
weather (4 + 1 + 1) · Trick Room (1 + 1), Gravity (1) · own side (9 + counters ≈ 12)
· opp side (≈ 12). ≈ **40**.

### 4.5 Id suffix (ids on)
12 species + 8 moves + **12 items + 12 abilities** as `id/256` embedding indices
(≈ 44). `opp_action.py`'s three restated offsets (`_OPP_MOVE_ID_OFF=16`,
`_OPP_FAINT_IDX=2`, `_REVEALED/_FAINTED/_IS_ACTIVE = 0,2,3`, `rl/networks/opp_action.py:
66-77` `[tree]`) constrain the layout: hp/fainted/is-active stay first in the mon
block and the species+move ids stay first in the suffix; the new item/ability ids
are appended after them. These become spec ClassVars with a layout test (§8).

### 4.6 Privileged block
`privileged_block` (`showdown.py:462-464`) is the own-side slice plus the own id
tail; it re-derives from the spec offsets unchanged. The `+ 10` in
`entity_deepsets.py:212` is `PRIV_ID_DIM`, not the action count (the F-08 landing
record warns not to "fix" it `[tree]`).

### 4.7 Arithmetic
40 + 6·62 + 33 + 4·58 + 6·63 + 33 + 4·58 + 44 ≈ **1,376** at v2+ids with the widths
above; the seam inventory's leaner sketch (16 volatiles, no class bits) lands at
≈ 1,183. Either way ≥ 1.4× gen1's 828. **No number here is a commitment**; the
pre-reg header freezes the exact tuples.

### 4.8 What changes in `rl/envs/showdown.py`
`MON_DIM / ACTIVE_DIM / MOVE_DIM / OBS_DIM / EFFECT_DIM / GLOBAL_DIM` become
values of the **selected** spec (`spec.mon_dim(v2)`, `spec.obs_dim(v2, ids)`, …),
with the module names kept as aliases so every importer survives; `embed_battle`'s
`spec is not GEN1` refusal becomes "not a registered spec"; new fill helpers
`_fill_global`, `_fill_side`, `_fill_item_ability` thread the spec like the
existing ones; `_move_obj(move_id, gen=spec.gen)`; `_move_slots_aliased` mirrors
poke-env's condition exactly. `GEN1`'s results are bit-identical by construction and
the hash gate proves it.

## 5. What the three references contribute, and what we decline

- **Wang 2024** `[src]` (Tables A.1/A.2, 3,725-dim, index+float mixed): species /
  ability / item / move / last-move as **embedding indices** (vocabs 296 / 101 / 40 /
  199 — the same universe we count), every multi-turn effect as a **k+2 one-hot
  duration** (weather 4×9 with a "Permanent" bin, Trick Room 7, screens 2×10,
  Encore 9, Taunt 6, Magnet Rise 7, Slow Start 6, toxic 21, sleep 11, protect 6),
  HP in 7 bins, PP as ⌊∛pp⌋/4, boosts 7×13, a per-mon `unknown` flag and a
  battle-level `# unknown` count, **no** precomputed effectiveness / STAB / base
  power / category. Taken: the Permanent-weather bin, the per-side hazard layer
  one-hots, the explicit `first_turn` / `protect_counter` / `must_recharge` /
  `preparing` bits (we already have three of four), item and ability as indices.
  Declined (§10 A7, A8): duration one-hots (scalars instead), HP bins, PP cube-root.
  His partial-reveal representation is unstated (no per-field unknown symbol) — ours
  is explicit.
- **Huang & Lee / metagrok** `[src]` (gen7, 1,222 dims per mon): 128-d embeddings for
  species, base species, item, **prevItem**, ability, base ability, a 3-slot
  possible-ability belief (mean-pooled), moves summed, **lastmove on all 12 mons**,
  ppUsed, boosts /6, z-whitened stats, weather + `weatherTimeLeft` / `MinTimeLeft`,
  side conditions presence-only, **no status counters, no hazard layers, no turn**.
  Sentinel index 0 = hidden (frozen zero row), index 1 = unknown (trainable). Taken:
  `prevItem` (our `is_consumed` + the wrapper's item memory), the weather min/max
  belief (our elapsed + indefinite), the species/base-species split (our forme-keyed
  vocab), index-0-as-unknown (already ours). Declined: dropping counters (a regression
  gen 4 cannot afford), `lastmove` on every mon (a temporal feature; JOURNEY's
  Markovianity redesign is where it belongs — §10 A11).
- **ps-ppo / Metamon**: **not read this cycle** (its agent was lost to the usage
  limit; `open_questions.md` deferral D2). From the index only `[lit]`: ps-ppo's move
  token (STAB flag, expected hits, status + probability, 13-bin priority) is what our
  v2 effect block already adapted; its stats as (min, est, max) belief ranges and
  boosts as 7×13 one-hots are the two ideas worth reading when the deferral lifts.

## 6. What stays shared with gen1, what is new

**Shared (unchanged code paths):** the block order and 21-token reshape; `n_actions =
10`, the pointer head over 6 + 4, the mask width and `OPP_CHOICE_DIM`; the
per-format type chart threading; the per-move physical flag; the D13(a)
`must_recharge` bool; the mask-desync recovery mechanism (its gen1 rate calibration
is re-disclosed at gen 4); `battle_outcome`, `calc_reward`'s potential-based faint
shaping; `hl_event_sum`'s five tags (constants re-derived per format); `ID_SCALE`;
the six status one-hot; the seven boost keys; the `revealed` flag convention; the
own-side privileged block.

**New:** 17 types and the live-type read; SpD; items and abilities (ids + class bits +
reveal state); the weather / field / two side blocks; `maybe_trapped`; ~10 new
volatile flags and 5 new counters; a gen4 effect block; forme-keyed vocabs; a gen4
set prior with ability and item slots; `priority_scale`; a generation-stamped
fingerprint; per-spec strides.

**Rewritten, not ported:** the search line (`rl/search/*`) — every load-bearing
invariant is gen1 (poke-engine gen1 module, DVs/stat-exp, 39 damage rolls, the
Hyper-Beam-KO rule, gen1 volatile map) `[tree]`.

## 7. Selection, fingerprint, process model

- **Selection.** PROPOSAL (the seam inventory's option 3): the F-07 `encoder:` config
  block's `spec:` key selects (`docs/proposals/F07_encoder_config_block.md` §3.1/§5.3
  already plans `spec: gen1` as the only legal value "so F-08 adds VALUES, never
  fields" `[tree]`), and `spec_for_format(cfg.env_kwargs.battle_format)` stays as a
  cross-check that refuses on disagreement. If F-07 is not adopted, `spec_for_format`
  alone needs a lazy-init of the module strides (they are computed at import before
  any format is known) — workable, less safe.
- **Fingerprint.** `ENCODER_FINGERPRINT` gains `gen` and `spec` (F-07's
  `spec.fingerprint()`), and `test_every_hashed_combo_is_distinguishable` extends
  across generations (§8).
- **Sites to thread the format:** `fake_spaces()` at `rl/train.py:104, 480` and
  `scripts/eval_checkpoint.py:81`; `PoolPlayer(..., battle_format="gen1randombattle")`
  at `eval_checkpoint.py:103`; the collector defaults `rl/collect.py:75, 116`,
  `rl/envs/showdown_async.py:234`, `rl/search/agent.py:51` `[tree]`.
- **Process model.** gen4 training, eval and anchor batteries run in their own
  processes; the remaining `Discrete(10)` literals in analysis scripts and tests
  survive gen 4 and are a gen-9 item (the F-08 landing record's own list `[tree]`).

## 8. Test contract

**Keep green (gen1):** the five hash lines; `FINGERPRINTS` and
`test_fingerprint_records_the_semantics_the_hash_gate_pins`;
`test_bare_process_is_612_v1`; `test_module_constants_are_gen1_derived`;
`test_gen1_tables_are_the_literals_they_replaced` (layout `(3,9,10,15,30,32)`,
`(7,14,16)`, `(8,23)`); the five `_GEN2_SKETCH` threading tests;
`test_n_actions_is_poke_envs_and_gen9_widens`; `test_fake_spaces_shapes` `[tree]`.

**Rewrite (two):** `test_spec_for_format_registers_gen1_only` (`:227-239`, asserts
the gen-4 refusal) and `test_embed_battle_refuses_a_non_gen1_spec` (`:458-467`,
identity refusal → registry refusal). The two import-time width assertions
(`test_encoder_ids_tapes.py:51`, `test_encoder_v2.py:23`) must become
spec-conditional or the gen4 process cannot collect those files.

**Add (six):** a **gen4 tape hash gate** in the `_HASH_CHILD` shape — `[live]` the
tapes require a running server, so until post-ladder a gen4 encoder has **no
bit-identity pin at all**, the single largest schedule item hidden in the seam; a
gen4 spec-threading suite with a `_GEN5_SKETCH`-style probe for the new helpers; a
layout-invariant test for `opp_action.py`'s three offsets; a **bounds test** (every
emitted vector inside the declared Box — gen 4 fails it today on priority); an
injectivity test on the species vocab; cross-generation fingerprint
distinguishability.

## 9. Build order (sizes are estimates, nothing is scheduled)

1. Spec fields + derived strides + registry + selection + fingerprint; GEN1 bit-identity
   proven by the existing gate (small).
2. Vocab tables generated from the vendored pool by a script with the Showdown commit
   stamped (small); tokenizer assertions.
3. Wrapper-side state poke-env lacks — BUILT as `rl/envs/gen4/tracker.py` (§13): item memory / consumed, weather start + `[from] ability:` (indefinite), the Encore target (the sim never sends the move name; it is the target's last `|move|` line), Substitute HITS (no amount is sent, so sub HP is unobservable — A10 corrected), every `[from] ability:` reveal (Natural Cure, Static, Sand Stream, Rough Skin, Clear Body, ... — the `-activate` six included), the exact sleep-attempt count, Flash Fire persistence, Choice lock (a known Choice item + a move since switch-in; the OPPONENT's Choice item never self-reveals, so its lock is inferred only after a Trick — critic_pass.md §3), and Wish / Healing Wish pending per side (poke-env tracks no slot conditions; 23 sets). Each item is `[tree]` against research/live/ now that gen4 tapes exist.
4. New fill helpers and the gen4 effect block (medium).
5. Gen4 set prior from `sets.json` + item rule table (medium).
6. Post-ladder: collect gen4 tapes, land the hash gate, run the `[live]` checks in
   `pokeenv_gen4_survey.md` §8, then freeze the tuples in the gen4 pre-reg header.
   Tapes and live checks DONE 2026-09-05. **RULED 2026-09-05: freeze v0.1 AS BUILT
   (unreachable dims kept) → hash gate → entity trunk layout argument → the 50M
   Wang-recipe run (his Table A.3, mirror self-play, on our encoder)**
   (`open_questions.md` §0.5).

## 10. Adjudications (single-writer; recommendation, then the losing argument)

- **A1 Species key: forme-id string, pool-local (300).** Losing: dex `num` is stable
  across Showdown updates, dense, gen-independent, and lets a gen9 chapter reuse the
  table; forme ids are a frozen artifact needing an explicit unseen→0 rule. Flip if
  the plan is one embedding table gen4→gen9.
- **A2 `ID_SCALE` stays 256.** Losing: the `[0,1)` docstring invariant is broken;
  512 or 1024 restores it in one line, and gen 9's 1025 will force the change anyway.
- **A3 Items and abilities as embedding ids + class bits (12 + 5) + reveal state, not
  one-hots.** Losing: class bits are hand-designed priors that can be wrong; a pure
  id embedding cannot encode a taxonomy mistake, and 141 one-hot dims per active mon
  only is affordable.
- **A4 Unknown opponent ability = prior from `sets.json` collapsing to one-hot on
  reveal; the `-activate`-only six recovered from `effects`.** Losing: a second table
  to keep in sync with the vendored generator, and a hand map (`Effect.SYNCHRONIZE →
  "synchronize"`) that rots; upstreaming is the clean fix.
- **A5 Ability-aware matchup scalars beside the chart scalars.** Losing: it bakes a
  mechanic into a feature the network could learn from the class bits, and the
  two-candidate case has no honest single number.
- **A6 v1 set prior = role-conditioned marginals from `sets.json`, items by rule
  table; no sampler port.** Losing: gen1's whole standard was "the marginals are NOT
  a heuristic" (a faithful `randomSet` port); the item prior is only exact that way,
  and two thirds of gen4 sets are sampled from pools.
- **A7 Counters as scaled scalars, not Wang's k+2 one-hots.** Losing: one-hots are
  the Markov-restoring form he validated; scalars force the net to learn a threshold
  (a 4th Protect at 12.5 % vs a 3rd at 25 %) and cost nothing in dims that a
  1,300-dim vector cannot afford.
- **A8 HP scalar and raw PP, not Wang's bins / cube root.** Losing: he argues bins cut
  state space and that PP resolution matters most near zero; his footnote itself
  calls the HP bins arbitrary, and our gen1 arc never needed either.
- **A9 Live type list (`mon.types`) for gen 4 only; GEN1's fill path untouched.**
  Losing: applying it to gen 1 too is harmless in play (nothing in the gen1 pool
  changes type) and removes a per-spec branch; but it perturbs the hash gate.
- **A10 Substitute HP as a scalar (+1 dim).** Losing: recoverable from message
  history the encoder does not carry; a flag suffices at 44 sets.
- **A11 No temporal features (last move, move history) in the v1 gen4 spec.**
  Losing: an OBS_DIM change is the cheapest moment ever to add them; gen 4's hidden
  state (Choice lock, silent abilities) is inferred from sequences. Carried to
  JOURNEY's Markovianity redesign, where Wang's counters and H&L's `lastmove` both
  live.
- **A12 Clean break: a new OBS_DIM, no gen1-checkpoint loading, no padded layout.**
  Losing: a padded layout would let gen1 finals be evaluated in a gen4 process for
  comparison; JOURNEY's standing note says weights never transfer, and the
  one-process-one-encoder rule makes cross-play impossible anyway.
- **A13 `maybe_trapped`: encode a bit, keep the mask permissive, count rejections.**
  Losing: masking is the only choice that keeps the mask a true legality mask (the
  harness contract), and the retry lives in the same coroutine as the orphaned-room
  deadlock.
- **A14 `priority_scale` as a per-spec divisor (7.0), not a wider Box.** Losing:
  widening the Box is one line and gen-independent; but it touches every checkpoint's
  declared space.
- **A15 Selection by F-07's `spec:` key with `spec_for_format` as a cross-check.**
  Losing: F-07 is unruled and carries eight rulings of its own; `spec_for_format` alone
  is landed code.
- **A16 No damage-calc feature in v1.** Losing: gen4 damage is item/ability-modified
  far more than gen1's, so the product-of-features proxy may be materially worse; and
  nothing off the shelf computes it, so a later lever costs the same.
- **A17 The gen4 spec lands as its own module (`encoder_spec_gen4.py`) with the vocab
  tables as data files.** Losing: one file keeps the registry in one place; F-20
  already flags module size.

## 11. Maintainer rulings wanted (collected in `open_questions.md`)

A1, A2, A3, A6, A7, A11, A12, A15, A16 above, plus: whether Stealth Rock keeps a slot
(with the Showdown commit pinned); when gen4 tapes may be collected (the hash gate
gates everything); whether the vocab tables are tracked in git like
`rl/envs/data/gen1_randbats_sets.json` (F-21's precedent: tracked, borrowed, ruling
pending) or regenerated by script; and whether the 12 ability classes / 5 item
classes taxonomy is pre-registered as data or left to the implementer.

## 12. Sources, verification, deferrals

- Every `rl/`, `tests/`, `docs/` citation is main@2738025 via the seam inventory
  note, which read `encoder_spec.py`, `showdown.py`, `test_encoder_spec.py`,
  `entity_deepsets.py`, `opp_action.py`, `mlp.py`, `randbats_prior.py`, `make.py`
  in full and grepped `showdown_async.py`, `ppo.py`, `pool.py`, `matrix.py`,
  `agent.py` only.
- `[lit]`: the gen4 multi-hit distribution (3.0); everything attributed to ps-ppo or
  Metamon.
- `[live]`: the gen4 tapes and hash gate; every wrapper-side state item in §9 step 3;
  the aliasing and mask-desync rates at gen 4 (`_move_slots_aliased` true-rate;
  `mask_desync_total()` against steps); the empirical (ability, item) frequencies of
  the generator (the universe is exact, the marginal is not).
- Deferred, then DISCHARGED 2026-09-05 (`open_questions.md` D1–D3; the notes are
  under `research/`): ps-ppo / Metamon observation design, Wang's Showdown-fork set
  constraints as a second source for the prior, foul-play's gen4 calc as a
  damage-feature source. Still open: the literature cross-check (D4).

## 13. Build status — layout v0.1 (branch `gen4-build`, 2026-09-05)

What exists in code, `[tree]` at the branch head. Nothing here is frozen: the
tuples become a commitment only in a gen-4 pre-registration header (§4.7).

| piece | file | note |
|---|---|---|
| GEN4 spec + layout | `rl/envs/gen4/spec.py` | `EncoderSpec` filled for gen 4 (17 types listed, 6 stats, 13 single-Effect volatiles + 2 composite, `{struggle, recharge}`); `Gen4Layout` with every offset derived; **global 36 \| mon 61 \| active 31 \| move 71 (9 scalars + 17 types + 45 effect) \| ids 44 → OBS_DIM 1,448**; `priority_scale` 7, `turn_scale` 100, `ID_SCALE` 256 (A2, A14) |
| vocabularies | `rl/envs/gen4/vocab.py`, `data/gen4_vocab.json` | 300 species rows (295 + Gastrodon-East + Castform ×3 + Cherrim-Sunshine), 182 moves (typed Hidden Power), 101 abilities, 40 items; stamped with the Showdown commit and the `sets.json` sha256; `return102` canonicalised (§18 of `mechanics_delta.md`); **tracked in git** (Q20 — the F-21 precedent, ruling still owed) |
| class taxonomies | `rl/envs/gen4/classes.py` | 12 ability / 5 item classes as data-as-code with an import-time partition check against the vocab (Q21); the ability type-modifier table (A5) |
| set prior | `rl/envs/gen4/prior.py`, `data/gen4_set_samples.json` | **exact, not a marginal**: rejection over the 1,743 realised (moves, ability, item) triples the vendored generator emitted over 600,000 sets, conditioned on revealed moves / known ability / known item — a stronger form than A6's role-conditioned marginals AND than gen 1's port, because the samples come from whole teams (team weather, move pairs, item rules integrated). Monte-Carlo counts (~2,000 draws per species) — disclosed |
| tracker | `rl/envs/gen4/tracker.py` | §9 step 3, built and extended (weather set turn + indefinite, exact sleep attempts, item memory + consumed, Encore target, Substitute hits, Choice lock, Flash Fire, every `[from] ability:` reveal, Wish / Healing Wish per side; the Outrage / Thrash / Petal Dance lock — poke-env never attaches `Effect.LOCKED_MOVE`, review pass 2026-09-05) |
| encoder | `rl/envs/gen4/encoder.py` | `embed_battle_gen4`; the gen-1 block order; an opponent's UNTYPED Hidden Power (`hiddenpower`, what poke-env stores) resolved to the typed variant through the set prior — before the 2026-09-05 review fix it voided the prior for 5.6 % of opponent-mon reads; self stat drops read from Showdown's `self.boosts`; item / ability id + class bits + reveal state (expected class vectors under the prior when unknown); ability-aware matchups as EXPECTATIONS under the ability belief, capped at 4.0 (Dry Skin ×1.25 on a 4× hit reads 5.0 otherwise); closed-form opponent Speed (EV 85 / IV 31 / no nature), inverted under Trick Room; `privileged_block_gen4` (703 dims) |
| env | `rl/envs/gen4/env.py`, `rl/envs/make.py` | `Gen4ShowdownSingles`, `Gen4ShowdownEnv`, `Gen4PoolPlayer`; `ShowdownGen4-v0` registered; reward, timer, mask-desync recovery and the wait pump inherited from gen 1 unchanged |
| run metadata | `rl/train.py` | `ENCODER_FINGERPRINT_GEN4` (gen stamped) for `ShowdownGen4-*` env ids |
| tests | `tests/test_gen4_encoder.py` | 17 offline tests: layout arithmetic, tables, vocab/classes/prior, the effect block (incl. self drops), Hidden Power resolution, the tracker fed poke-env's own parser (the Sleep Talk counter and rampage-lock tests), the most-damage-typed rule and its seeding, `Gen4PoolPlayer` bookkeeping, a hand-built battle, and the tape replay gate (shape + bounds) on the COMMITTED fixture `tests/fixtures/gen4_tape_t0_2battles.jsonl.gz` (t0's first two battles, 13 KB) and on the local t0 tape when present |
| instruments | `rl/envs/gen4/tape.py`, `scripts/gen4_smoke.py`, `scripts/gen4_env_smoke.py`, `scripts/gen4_sample_generator.js`, `scripts/gen4_build_vocab.py` | tape record / replay / tallies; the live smokes; the generator sampler; the vocab builder |

**Reference replay (not a pinned gate):** every recorded tape (t0–t6, 1,650
seat-battles, **42,191 decisions**) through `embed_battle_gen4` → 0 NaN, every
value inside `Box(-1, 4)`, 0 poisoned battles, **193 µs/decision** (gen 1:
~133; 166 before the Hidden Power resolution and the rampage lock), sha256
`bbcf9f601c412a24ee7382fb654bb22c76e8ed39df0137a8b82ebbf77a4ff905` — sha256
over `vec.tobytes()` per decision in tape order, the gen-1 gate's rule
(`tests/test_encoder_spec.py`); re-recorded at the branch head after the
2026-09-05 review fixes (the pre-review record was `8acdc50a…`).
The gen-4 hash gate (§8, Q19) is buildable now — the tapes exist — and lands
the moment a pre-reg freezes the tuples; until then the reference hash is a
record, not a pin.

**Unreachable at the pinned pool (2026-09-05 review):** ~90 of the 1,448 dims
never left zero over 41,908 recorded decisions — Stealth Rock / Reflect / Light
Screen / Safeguard / Mist / Tailwind / Lucky Chant on both sides, Gravity, the
CURSE / FOCUS_ENERGY / trapped-by-move / perish flags and the perish counter, and
seven effect slots (drain, attract, partial trap, focus energy, screen, other
side condition, trap) × 8 move slots. Kept deliberately: they are the FORMAT's
mechanics and the pool moves with every Showdown commit (this one has zero
Stealth Rock sets; the format's history does not). **RULED 2026-09-05: KEPT in
the v0.1 freeze** — a relayout kills every checkpoint; relayout only on a measured defect;
`spec.py`'s layout docstring records the same list.

**Deviations from §3–4, each measured (`mechanics_delta.md` §18,
`pokeenv_gen4_survey.md` §12):** Substitute HP is unobservable → a hits
counter (A10); Encore's move is never sent → the last `|move|` line; Roost's
type change is never visible at a decision (the live-type read serves Color
Change); two slot dims for Wish; the effect block is 45 wide (the 32 sketch
folded side conditions into three classes and added trapping / variable
damage / item swap / team cure / defrost bits); `-ability` announcers are six
(Speed Boost and Download announce).

**Not built (next) — RULED ORDER 2026-09-05 (`open_questions.md` §0.5): (1) the
pre-reg header that freezes v0.1 as built (2-Opus review first), (2) the pinned
hash gate, (3) the entity trunk's layout argument, (4) the 50M Wang-recipe run —
his Table A.3 and mirror self-play on our encoder; our pool / league / batch
machinery held back as later levers (hand-over launch).** The items: the entity trunk's vocab arguments (`entity_deepsets.py`
must take `VOCAB.n_species / n_moves` and the two new id tables — today it
clamps at 152 / 166 and cannot serve gen 4); `scripts/eval_checkpoint.py` and
`rl/collect.py` / `showdown_async.py` format threading (the smoke ran the sync
path through `make_env`); F-07 selection; the pinned hash gate; the gen-4
pre-reg that freezes the layout. Q13 (counters as scalars) should be re-read
with `research/psppo_metamon_obs.md` §8 in hand: no comparator scalarises a
duration, and none ablated it.

# our_encoder_seam_inventory.md — the landed per-gen seam, and every gen-1 assumption still outside it

Agent: **encoder-seam inventory agent** (gen-4 design sweep, source family = OUR repo + installed poke-env)
Date: **2026-09-04**
Repo authority: `SNAP` = read-only snapshot of `main@2738025`. All repo paths below are
repo-relative and mean `main@2738025` unless stated. Everything in this note is
docs-only: no server was started, no battle was played, no file outside the scratchpad
was written, no process was signalled.

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP `rl/`, `scripts/`,
  `configs/`, `tests/`, `docs/`) or the vendored Showdown `data/`/`sim/`, i.e. the game
  as we actually run it.
- **source-verified** — checked against an external primary source on disk: the installed
  poke-env 0.15.0 source (`PE`), or another vendored clone.
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work
  index without re-checking the primary.
- **needs-live-verification** — only a running server or a real battle can confirm it.
  BARRED until the ladder run (and any later fleet) completes; each such item states the
  exact check.

## Sources actually read (path — what, and which lines)

Repo (SNAP, `main@2738025`):
- `rl/envs/encoder_spec.py` — read in FULL, 286 lines. Cited: docstring 1–19; class docstring
  34–81 (the gen-4 work list, 45–80); fields 83–105; derived props 108–202; `GEN1` 208–249;
  `_REGISTRY` 251; `spec_for_format` 254–286 (missing-list 267–276).
- `rl/envs/showdown.py` — read in FULL, 1366 lines, in five passes (1–200, 200–460, 460–760,
  760–1050, 1050–1366). Heavily cited below.
- `tests/test_encoder_spec.py` — read in FULL, 467 lines. Cited: docstring 1–27; `TAPES` 51–58;
  `ORACLE` 66–74; `_ENCODER_VARS` 76; `_HASH_CHILD` 78–174; `FINGERPRINTS` 192–199;
  tests 227–467.
- `rl/envs/randbats_prior.py` — read in FULL, 173 lines.
- `rl/envs/data/gen1_randbats_sets.json` — structure only, parsed with a 6-line throwaway
  script under `nice -n 19` (146 species; keys `level`, `moves`, `comboMoves`,
  `essentialMoves`, `exclusiveMoves`).
- `rl/networks/entity_deepsets.py` — read in FULL, 387 lines.
- `rl/networks/opp_action.py` — read in FULL, 341 lines.
- `rl/networks/mlp.py` — read in FULL, 73 lines.
- `rl/train.py` — grepped and read the encoder-relevant windows: 85–125, 170–195, 465–495.
- `scripts/eval_checkpoint.py` — read 50–115 (the cross-encoder shim and `_opponent_from_checkpoint`).
- `rl/envs/make.py` — read in FULL, 153 lines.
- `rl/envs/showdown_async.py` — grepped only (lines 75, 145–170, 234, 257); NOT read in full.
- `rl/collect.py` — read 70–90 and 110–140 (SeamPlayer / RecordingPlayer encode paths).
- `rl/search/{shadow_battle.py,bridge.py,determinize.py,harvest.py,expansion.py}` —
  grepped for gen-1 assumptions; `shadow_battle.py` 1–60 and `bridge.py` 1–115 read.
  `matrix.py`, `agent.py`, `ensemble.py` grepped only.
- `docs/archive/AUDIT_BRANCH_LOG.md` — F-08 section, lines 303–340, incl. its
  "Open questions for the maintainer" at 333–340.
- `docs/archive/AUDIT_ACTION_PLAN.md` — lines 73–75 (the finding table rows F-07/F-08),
  197–226 (F-07, F-08, F-11 in full), 250–262 (F-20), 275–277 (the ordering item).
- `docs/proposals/F07_encoder_config_block.md` — §3.1 (69–93), §3.2 head (94–100),
  §5 (209–242), §6 (243–256), §7 (257–278).
- Repo-wide greps over `rl/ scripts/ configs/ tests/` with `--include='*.py' --include='*.yaml'
  --include='*.sh'` for: `gen1randombattle` (138 hits), `Discrete(10)`, `from_gen(1)`/`gen=1`,
  `ID_SCALE`/`256.0`, `'fight'`, `type_chart`, `N_ACTIONS`, `POKEMON_RL_`.

Installed poke-env 0.15.0 (`PE = /opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env`):
- `environment/singles_env.py` — 110–135 (`action_to_order` re-basing), 233–288
  (`get_action_mask`), 291–304 (`get_action_space_size`).
- `battle/move.py:17` (`SPECIAL_MOVES`), 153/206/254 (its uses).
- `battle/pokemon.py` — slots 27–132; `status_counter` mutation sites 194, 362, 415, 483, 615;
  property list 861/939/1052/1103/1215/1255/1279.
- `battle/pokemon_type.py:43–68` (`damage_multiplier`).
- `battle/abstract_battle.py` — property lines 1409 (`fields`), 1516
  (`opponent_side_conditions`), 1652 (`side_conditions`), 1793 (`weather`).
- `data/static/typechart/gen1typechart.json`, `gen4typechart.json` — key sets and
  `isNonstandard` flags.
- `GenData.from_gen(4)` tables (pokedex/moves/type_chart) via a short offline script.

Vendored Showdown (`SD`, gitignored, poke-env-independent):
- `data/random-battles/gen4/sets.json` — 295 species; top keys `level`, `sets`; set keys
  `role`, `movepool`, `abilities`.
- `data/random-battles/gen4/teams.ts` — 771 lines; grepped for structure: `randomSets`
  require at :45, `cullMovePool` :84, `getAbility` :475, `getItem` :554, `randomSet` :627,
  `getLevel` call :673; item return strings in 520–626.
- `data/random-battles/gen1/{data.json,teams.ts}` — existence/size only (the vendored
  gen-1 pool the prior copies).
- `data/mods/gen4/conditions.ts:7–13` (paralysis speed).

NOT read (say so rather than imply coverage): `rl/agents/ppo.py`, `rl/buffers/*`,
`rl/selfplay/pool.py`, `rl/search/matrix.py` body, the Metamon/Wang/H&L texts (other
agents' family), `MAIN/results/design_ch5_100m/`, anything under `MAIN/runs`,
`MAIN/logs`, `MAIN/results/ladder` (barred).

---

# 1. What the landed seam ALREADY parameterizes

Every row is **tree-verified** against `rl/envs/encoder_spec.py` and the consuming line in
`rl/envs/showdown.py` (`main@2738025`).

| EncoderSpec member | Declared at | Read by (showdown.py) | Gen-4 status |
|---|---|---|---|
| `gen: int` | encoder_spec.py:83 | `_species_id` `GenData.from_gen(spec.gen).pokedex` :378; refusal message :290 | fill in `4` |
| `types: tuple[PokemonType, ...]` (ORDER IS LAYOUT) | :85 (GEN1 212–218) | `spec.type_index.get(t)` :209 (mon), :261 (move) | 17 members, see §4.1 |
| `statuses` (FNT excluded) | :87 (GEN1 219) | `spec.status_index.get(mon.status)` :200 | unchanged six |
| `boost_keys` | :88 (GEN1 222) | `for i, key in enumerate(spec.boost_keys)` :225 | same 7 poke-env keys; `spd` stops being redundant |
| `base_stat_keys` | :89 (GEN1 224) | `for i, key in enumerate(spec.base_stat_keys)` :205 | six (real Special Defense) |
| `volatiles: tuple[Effect, ...]` | :90 (GEN1 237–241) | `for i, effect in enumerate(spec.volatiles)` :228, incl. the D13(a) MUST_RECHARGE bool branch :229–230 | grows a lot; REFLECT must LEAVE (§4.3) |
| `special_move_ids: frozenset[str]` | :94 (GEN1 244) | `_move_slots_aliased` :397 | `{"struggle","recharge"}` — but the predicate itself is wrong for gen 4 (§3, row A11) |
| `species_num_range` | :98 (GEN1 247) | `_species_id` :380–381 | `(1, 493)` is NOT injective at gen 4 (§4.2) |
| `move_num_range` | :99 (GEN1 248) | `_move_id` :389–390 | `(1, 467)`, injective |
| `n_switches`, `n_moves` | :104–105 | naming only (layout arithmetic still uses literal 6/4) | unchanged |
| `type_index` (cached) | :108–110 | :209, :261 | derived |
| `status_index` (cached) | :112–114 | :200 | derived |
| `n_types / n_statuses / n_boosts / n_base_stats / n_volatiles` | :116–134 | via the offsets below | derived |
| `n_actions` = `SinglesEnv.get_action_space_size(gen)` | :136–140 | `N_ACTIONS = GEN1.n_actions` :96; `fake_spaces` :174 | **10 at gen 4** (source-verified, PE singles_env.py:291–304) |
| `mon_status_off` (ClassVar 3) | :149 | :202 | survives (hp/fainted/is-active) |
| `mon_level_off / mon_stats_off / mon_types_off / mon_matchup_off / mon_dim_v1` | :151–169 | :203, :204, :207, :213, and `MON_DIM` :136 | recompute automatically from the tables |
| `active_volatiles_off / active_counter_off / active_dim` | :172–182 | :227, :233, `ACTIVE_DIM` :137 | recompute automatically |
| `move_type_off` (ClassVar 8) / `move_dim_v1` | :186–190 | :263, :265, `MOVE_DIM` :138 | the 8 leading move scalars are *code*, not per-gen data |
| `__hash__` (cached, field-based) | :197–202 | `lru_cache` key of `_species_id` :373–378 | survives |

**Selection**: `spec_for_format(battle_format)` (encoder_spec.py:254–265) keys on
`GenData.from_format(fmt).gen` — the format string, not the config. Its only production
consumer today is `fake_spaces` (showdown.py:174: `n_actions = spec_for_format(battle_format).n_actions`).
Nothing else in `rl/` calls it. **tree-verified.**

## 2. What the seam explicitly REFUSES (the work list, verbatim)

Two refusals, both **tree-verified**.

**(a) The class docstring's gen-4 work list** — `rl/envs/encoder_spec.py:45–80`, quoted verbatim:

```
    WHAT A GEN-4 SPEC MUST ADD (the gen-4 blocker, plan F-08), beyond
    filling these fields for gen 4:
      - `types`: 17 (Dark and Steel since gen 2; Fairy makes 18 at gen 6).
        `PokemonType` already carries all of them.
      - per-move physical/special: NO new table. `_fill_move` reads
        poke-env's `move.category`, which is per-move in the gen-4 data
        already; only the gen-1 "category follows the type" rule stops
        holding, and the encoder never assumed it.
      - items and abilities: absent in gen 1, so there is no block for
        them. New per-mon fields are a MON_DIM change, i.e. an OBS_DIM
        change — every existing checkpoint is invalidated (landmine).
      - weather (gen 2+) and SIDE conditions (Spikes at gen 2; Stealth Rock
        and Toxic Spikes at gen 4; and note Reflect / Light Screen become
        5-turn SIDE conditions at GEN 2 — in gen 1 they are per-mon and die
        on switch-out, which is why `volatiles` carries REFLECT below, so a
        gen-2+ spec must MOVE them out of `volatiles` into the side block
        rather than inherit them): new global blocks. Terrain is gen 6.
      - `statuses` stays the same six (poke-env's `Status` minus FNT — no
        new major status through gen 9), but `volatiles` grows (Taunt,
        Encore, Yawn, Perish Song, Ingrain, ...): a new ACTIVE_DIM. The
        status COUNTER semantics also move (gen-2 sleep/toxic counters).
      - `base_stat_keys`: six — gen 2+ has a real Special Defense.
      - id ranges: species 1..493 and moves 1..467 at gen 4 (embedding
        table sizes in rl/networks/entity_deepsets.py follow).
      - a set prior for the format: `rl/envs/randbats_prior.py` is gen-1
        randbats data, and `_opponent_move_slots` reads it directly.
      - the v2 effect block: `_effect_block` / `_move_obj` build
        `Move(id, gen=1)` and index a gen-1 move-volatile table; both are
        outside this spec today.
      - the block STRIDES and OBS_DIM: `rl/envs/showdown.py` derives them
        at import from `GEN1` plus the process flags, which is why
        `embed_battle` refuses a non-GEN1 spec outright today.
      - (gen 6+) the action head: `n_actions` widens to 14/18/22/26 for the
        gimmick slots, and the pointer head scores exactly 6 + 4 entities.
        Gen 4 keeps 10 — poke-env's space is 6 + 4 * (1 + gimmicks) with
        gimmicks 0 through gen 5.
```

**(b) The runtime refusal** — `spec_for_format`'s `missing` list, `encoder_spec.py:267–276`,
verbatim:

```
    missing = [
        "a per-gen type table (17 types from gen 2, 18 from gen 6)",
        "items and abilities blocks (absent in gen 1)",
        "weather and side-condition blocks (terrain from gen 6)",
        "the gen-2+ volatile set",
        f"species and move `num` ranges for gen {gen}",
        f"a set prior for the format ({battle_format!r}; randbats_prior.py is gen 1)",
        "the v2 effect block off gen-1 Move data",
        "per-spec block strides and OBS_DIM (showdown.py derives them from GEN1)",
    ]
```

plus, only when `n_actions != GEN1.n_actions` (i.e. gen 6+), an action-head line
(:277–281). At gen 4 that clause does NOT fire — `spec_for_format("gen4randombattle")`
raises with the eight lines above and no action-head line. **tree-verified**; pinned by
`tests/test_encoder_spec.py:227–239`.

**(c) `embed_battle`'s identity refusal** — showdown.py:288–295: `if spec is not GEN1: raise
NotImplementedError(...)`. Note it is `is not`, not `!=`: even a field-equal
`dataclasses.replace(GEN1)` is refused, because the module strides were derived from the
singleton (tested at test_encoder_spec.py:461–467). **tree-verified.**

---

# 3. Every gen-1 assumption still OUTSIDE the spec

Columns: `file:line` | what it assumes | gen-4 status | proposed owner. Every row is
**tree-verified** at the cited line unless tagged otherwise. "PROPOSAL" marks my
recommendation, not a ruling.

## 3.1 Layout / strides / process flags

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A1 | `rl/envs/showdown.py:136–138` | `MON_DIM/ACTIVE_DIM/MOVE_DIM` are `GEN1.*` plus the two process flags, fixed at import | **breaks** — the widths are per-spec | move to spec properties `mon_dim/active_dim/move_dim` that take the v2 flags as arguments; module keeps GEN1 aliases |
| A2 | `showdown.py:145` (`OBS_DIM = ...`) | one process-global obs width, computed from GEN1 | **breaks** | `spec.obs_dim(v2, ids)`; the module global becomes the selected spec's value |
| A3 | `showdown.py:128` `GLOBAL_DIM = 6` | the global block is 6 scalars: turn, own faints, opp faints, force_switch, trapped, aliased (:299–309) | **needs a per-gen table** — gen 4 wants weather, both sides' side-conditions, Trick Room/Gravity, `maybe_trapped` | new `global_extras` spec field + a `_fill_global` helper |
| A4 | `showdown.py:129` `EFFECT_DIM = 23` | the v2 per-move effect block is 23 gen-1 features | **breaks** (see A8) | per-spec `effect_dim` / effect-block builder |
| A5 | `showdown.py:124–125` `ID_DIM=20`, `ID_SCALE=256.0` | 6+6 species and 4+4 move ids, each `id/256` | **survives numerically at gen 4** (§4.2), but `_species_id` is no longer injective | keep `ID_SCALE`; replace `species_num_range` with a per-spec vocab (§6) |
| A6 | `showdown.py:150–158` `ENCODER_FINGERPRINT` | five keys, no generation/spec identity | **breaks the audit trail** — a gen-1 and a gen-4 828-dim checkpoint would stamp the same fingerprint if the widths ever coincided | add `"spec": spec.name` / `"gen": spec.gen`; F-07 §5.3 already proposes `spec.fingerprint()` |
| A7 | `showdown.py:462–464` `PRIV_DIM` | privileged block = own-side slice of the GEN1 layout, ids tail = `6+4` | **derived, so it survives** once A1/A2 are per-spec; the literal `+ 10` in `entity_deepsets.py:212` is `PRIV_ID_DIM`, not the action count (the F-08 log flags this at AUDIT_BRANCH_LOG.md:336 so nobody "fixes" it into `N_ACTIONS`) | leave; re-derive from the spec |

## 3.2 The v2 effect block and its gen-1 move data

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A8 | `showdown.py:478–480` `_move_obj` → `Move(move_id, gen=1)` | every move object built for the effect block is gen-1 data | **breaks** — gen-4 BP/accuracy/category/secondaries differ, and 300+ gen-4 moves do not exist at gen 1 | `spec.gen` into a per-spec `_move_obj(move_id, gen)`; the `lru_cache` key gains the gen |
| A9 | `showdown.py:486` `_SEC_STATUS_STR` | six lowercase status strings, indices matching `_STATUS_INDEX` (the GEN1 alias) | survives as data, but is a module literal keyed to GEN1's status order | spec-derived (`{s.name.lower(): i for i, s in enumerate(spec.statuses)}`) |
| A10 | `showdown.py:490–498` `_MOVE_VOL_INDEX` / `_SEC_VOL_STR` | the only move-inflicted volatiles are CONFUSION, PARTIALLY_TRAPPED, SUBSTITUTE, REFLECT, LEECH_SEED, FLINCH | **breaks** — gen 4 adds Taunt, Encore, Yawn, Torment, Disable, Attract, Perish Song, Ingrain, Aqua Ring, Magnet Rise, Protect, Curse, Nightmare, Embargo, Heal Block, Foresight/Miracle Eye (all present as `Effect` members, source-verified) and moves REFLECT to the side block | a per-spec `move_volatiles` tuple + a per-spec effect-block builder |
| A11 | `showdown.py:502–553` `_effect_block` body | 23 slots covering gen-1 mechanics only; nothing for side conditions, weather, forced switch, self-switch, item removal, terrain | **breaks** — poke-env's gen-4 `Move` already exposes `side_condition`, `weather`, `force_switch`, `self_switch`, `slot_condition`, `flags` (source-verified, §4.4), so the *data* is there and only the block is missing | new per-spec effect-block builder keyed by gen; PROPOSAL: `spec.effect_features` as an ordered tuple of named extractors |
| A12 | `showdown.py:260` `vec[o+7] = move.priority / 5.0` | gen-1 priority ∈ [-1, +1], so `/5` stays inside `Box(low=-1)` | **BREAKS THE DECLARED OBSERVATION BOUNDS at gen 4** (§4.5) | `spec.priority_scale` (PROPOSAL: 7.0 at gen 4) or widen the Box |
| A13 | `showdown.py:251` `move.base_power / 100.0`, :252 `accuracy`, :253 `pp` | gen-1 magnitudes | survives — gen-4 randbats max BP is 250 → 2.5 < 4.0 (tree-verified against `SD data/random-battles/gen4/sets.json` movepools) | none |
| A14 | `showdown.py:258–259` `move.category == PHYSICAL / STATUS` | the flag is read off poke-env's per-move `category` | **survives verbatim** — confirmed at the line; gen-4 `Move("crunch", gen=4).category is PHYSICAL`, `Move("surf", gen=4).category is SPECIAL` (source-verified). The docstring's claim (encoder_spec.py:49–52) is accurate: no new table | none |

## 3.3 The set prior and `_opponent_move_slots`

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A15 | `rl/envs/randbats_prior.py:63` `_DATA = data/gen1_randbats_sets.json` | one process-global gen-1 pool file | **breaks** | per-format loader: `set_prior_for(format)` returning an object with `known_species()/conditional_move_probs()/species_level()` |
| A16 | `randbats_prior.py:83–105` `_sample_set` | Showdown's gen-1 `randomSet`: comboMoves all-or-none on a 50% flip, exactly one exclusiveMove, essentialMoves in order, then `sampleNoReplace` | **breaks completely** — gen-4 `sets.json` has no such keys. Its schema is `{level, sets: [{role, movepool, abilities}]}` (295 species; tree-verified), and `teams.ts` draws through `randomSet` (:627) → `cullMovePool` (:84) → `getAbility` (:475) → `getItem` (:554) with move-enforcement counters. A faithful gen-4 marginal is a much larger re-implementation | its own per-format sampler module; PROPOSAL: consider empirical marginals harvested from our own generated teams instead of re-implementing `teams.ts` (needs-live-verification to harvest) |
| A17 | `showdown.py:582–599` `_opponent_move_slots` | 4 move slots filled from revealed moves then gen-1 marginals; probability reinterprets the `known` flag at zero extra dims | the *shape* survives; the *source* does not (A15/A16). Also gen 4 adds **item and ability** to the unknown-set problem, which the 4 move slots cannot carry | keep the mechanism; add per-mon item/ability prior slots in the new mon block |
| A18 | `randbats_prior.py:145–147` `species_level` | randbats levels come from the pool file | survives with a gen-4 file — gen-4 levels run 67..100 (tree-verified from `sets.json`) vs gen 1's tighter band | same loader |
| A19 | `randbats_prior.py:150–172` `verify_against_showdown` | the live file is `showdown/data/random-battles/gen1/data.json` | **breaks** — the gen-4 file is `.../gen4/sets.json` (different name AND schema) | parameterize the path per format |

## 3.4 Ids, vocabularies and the networks

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A20 | `showdown.py:374–382` `_species_id` | `num` inside the spec range is a unique row index | **breaks silently at gen 4** — 33 of the 295 gen-4 randbats species share a dex `num` with another (Arceus's 17 formes all `num` 493; Rotom 6; Deoxys 4; Wormadam 3; Giratina 2; Shaymin 2). §4.2 | replace `species_num_range` with `species_vocab: tuple[str, ...]` (format-scoped) → index |
| A21 | `showdown.py:384–390` `_move_id` | move `num` in range is a unique row | survives — gen-4 move nums are injective (483 of 486 poke-env gen-4 move entries fall in 1..467; the 3 outside are synthetic, `num ≤ 0`) | widen the range or use a format-scoped move vocab |
| A22 | `rl/networks/entity_deepsets.py:167–168` `species_vocab: int = 152, move_vocab: int = 166` | gen-1 table sizes as DEFAULTS | **breaks** (silent clamp, not an error: `entity_deepsets.py:143–144` `.clamp(0, vocab-1)`) — every gen-4 id above 151 would clamp onto Mew | per-spec vocab sizes, passed by the config; PROPOSAL: assert `vocab >= spec.max_id + 1` at construction |
| A23 | `entity_deepsets.py:48–50` `_N_SPECIES_IDS=12`, `_N_MOVE_IDS=8` | the id suffix is 12+8 | survives at gen 4 (still 6+6 mons, 4+4 moves) | none |
| A24 | `entity_deepsets.py:136–138`, `:278` | `round(x*256)` recovers the id; hard-coded `256.0` in two places plus `opp_action.py:70` | survives (§4.2) | keep, but PROPOSAL: import `ID_SCALE` rather than restating it |
| A25 | `entity_deepsets.py:185–193` `from rl.envs.showdown import N_ACTIONS`, `out_dim not in (N_ACTIONS, 1)` | the process's single action count | survives at gen 4 (10) | none until gen 6 |
| A26 | `entity_deepsets.py:381–384` pointer head over `mons[:, :6]` ‖ `own_moves` (10 entities) | 6 switch + 4 move actions align with poke-env's mapping | survives at gen 4 | none until gen 6 |
| A27 | `rl/networks/opp_action.py:45–50` L6 = `{slot 0..3, OTHER_MOVE, SWITCH}` | the opponent has exactly 4 encoder move slots | survives structurally at gen 4, but the class prior shifts and the pre-registered constants (43.6/27.3/13.6/5.2/3.0/7.2%, `opp_action.py:38–42`) are gen-1 measurements | re-measure per format; the AUDIT_BRANCH_LOG F-08 note (:338) already says this head "will need its own pass at gen 6+" |
| A28 | `opp_action.py:66–77` `_OPP_MOVE_ID_OFF=16`, `_OPP_FAINT_IDX=2`, `_REVEALED/_FAINTED/_IS_ACTIVE = 0,2,3` | fixed offsets inside the id suffix and the mon block | survives *if* the gen-4 mon block keeps hp/fainted/is-active first and the id suffix keeps its shape; a new per-mon item/ability field must not be inserted before offset 3 | document as a layout invariant; PROPOSAL: expose these three as spec ClassVars |
| A29 | `opp_action.py:196–201` `switch_legal = 6 - opp_faints - active_alive >= 1` | teams are 6 | survives | none |

## 3.5 Aliasing, masks and the action space

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A30 | `showdown.py:393–397` `_move_slots_aliased` | "only one legal move and it is in `special_move_ids`" ⇒ slots are re-based | **partially breaks.** poke-env's actual re-basing condition (source-verified, `PE environment/singles_env.py:122–127`) is `len(avail_ids) == 1 and avail_ids[0] not in known_ids` — membership in `SPECIAL_MOVES` is NOT the test. At gen 1 the two coincide; at gen 4 the *false-positive* direction is what matters: a Choice-locked / Encored / Taunted / Outrage-locked mon has one available move that IS a known move, so poke-env does NOT re-base and our predicate correctly says False. But a gen-4 mon that reveals a move via Mimic/Copycat could present a single available move outside `known_ids` without being a `SPECIAL_MOVE` | PROPOSAL: change the predicate to mirror poke-env's condition exactly, and keep `special_move_ids` only as the gen-4 value `{"struggle","recharge"}`. Note `"fight"` is a gen-1 mod artifact and must be dropped |
| A31 | `showdown.py:96` `N_ACTIONS = GEN1.n_actions`, `showdown.py:162–178` `fake_spaces(battle_format="gen1randombattle")` | the default format is gen 1 | **survives but silently**: `rl/train.py:104` and `:480` and `scripts/eval_checkpoint.py:81` all call `fake_spaces()` with NO format, so a gen-4 run's faked spaces would be derived from the gen-1 default. The width is 10 either way, so nothing errors | PROPOSAL: make the format a required argument at those three sites, from `cfg.env_kwargs["battle_format"]` |
| A32 | `scripts/eval_checkpoint.py:103` `PoolPlayer(pool, battle_format="gen1randombattle")` | the cross-play seat-2 format is gen 1 | **breaks** for a gen-4 eval (wrong type chart, wrong action-mask gen) | thread the format from the config |
| A33 | remaining `Discrete(10)` literals: `scripts/ch3_eval.py:577`, `scripts/ch3_fidelity_check.py:896`, `scripts/ch3_r1_spike.py:50`, `scripts/foulplay_vs_sh.py:159`, `scripts/d22_weight_norms.py:141`, `scripts/d25_gates.py:648`, plus `scripts/showdown_throughput.py:88 N_ACTIONS = 10`; tests: `test_d25_placebo.py:232,271`, `test_zeroinfo.py:74`, `test_l2_init.py:342`, `test_showdown_env.py:98`, `test_frozen_opponent.py:80`, `test_eval_shim.py:113`, `test_opp_action.py:404,472,476`, `test_entity_deepsets.py:50,85,107,216` | the action space is 10 | survives at gen 4; breaks at gen 9 | the F-08 landing record already flags these as out of its scope (AUDIT_BRANCH_LOG.md:334) — leave until gen 9, but a gen-4 chapter should not add more |
| A34 | `showdown.py:675–740` mask-desync recovery (`_MASK_DESYNC_WINDOW=100_000`, `_MASK_DESYNC_CAP=3`) | the benign race rate is ~2.5e-9/step, measured at gen 1 | **needs-live-verification at gen 4** — the recovery mechanism is generation-agnostic (it is a poke-env threading race), but the calibration is a gen-1 measurement. Check: run a gen-4 collection lane and read `mask_desync_total()` against steps | keep the mechanism; re-state the rate as a gen-4 disclosure |

## 3.6 Per-mon and per-active features

| # | file:line | assumes | gen-4 status | proposed owner |
|---|---|---|---|---|
| A35 | `showdown.py:206` `mon.base_stats[key] / 255.0` | max base stat 255 | survives (gen-4 max base stat is 255, Blissey HP) | none |
| A36 | `showdown.py:203` `mon.level / 100.0` | levels ≤ 100 | survives (gen-4 randbats levels 67..100, tree-verified) | none |
| A37 | `showdown.py:213–215` `_best_multiplier` | the type chart alone gives the true effectiveness | **breaks at gen 4** — `PokemonType.damage_multiplier` (source-verified, `PE battle/pokemon_type.py:43–68`) is a pure chart lookup with no ability parameter, so Levitate, Flash Fire, Volt Absorb, Water Absorb, Wonder Guard, Thick Fat and Foresight/Odor Sleuth/Miracle Eye are all invisible. At gen 1 the chart WAS the truth | PROPOSAL: an ability-aware multiplier helper owned by the spec, or an explicit "ability may modify" flag next to the two matchup scalars |
| A38 | `showdown.py:234` `mon.status_counter / 16.0` | one counter, "/16 = the toxic cap" | **needs a per-gen decision.** poke-env's counter is a single int incremented for SLP at `cant_move`/`moved` and for TOX at `end_turn`, reset on cure and on switch-out for TOX (source-verified, `PE battle/pokemon.py:194, 362, 415, 483, 615`). At gen 4 the sleep counter is bounded differently and Toxic's counter resets on switch, so /16 is dimensionally wrong for the sleep half | `spec.status_counter_scale`, or split into two slots (sleep turns, toxic turns) |
| A39 | `showdown.py:235` `bool(mon.preparing)` | one bit for two-turn charging | survives; gen 4 adds Power Herb (bypasses charge, handled inside poke-env at `pokemon.py:408–410`) and Fly/Dig/Dive/Bounce semi-invulnerability, which the bit cannot distinguish | PROPOSAL: keep the bit; consider a "semi-invulnerable" companion bit in the gen-4 active block |
| A40 | `showdown.py:229–230` MUST_RECHARGE read from `mon.must_recharge`, not effect membership | the D13(a) fix | survives verbatim at gen 4 (Hyper Beam / Giga Impact / Blast Burn family) | none |
| A41 | `showdown.py:555–565` `_spe_est` | actual speed ≈ `base_spe * level / 100`, boost table, `×0.25` under PAR | **partly survives, partly breaks.** The `×0.25` paralysis factor is CORRECT at gen 4 (**tree-verified**, `SD data/mods/gen4/conditions.ts:7–13`, `onModifySpe → chainModify(0.25)` unless Quick Feet). What breaks: the gen-4 stat formula includes IVs/EVs/**nature** (±10%), and Choice Scarf (×1.5), Swift Swim/Chlorophyll/Quick Feet/Unburden (×2), Tailwind (×2) and **Trick Room** (order inversion) all move the true ordering | per-spec speed estimator; PROPOSAL: for our OWN mons use `mon.stats["spe"]` (present from the request, source-verified `PE battle/pokemon.py:1279`) instead of the base-stat proxy |
| A42 | `showdown.py:299` `min(battle.turn / 50.0, 1.0)` | 50-turn saturation | survives dimensionally; gen-4 games are longer (stall, Leftovers, hazards), so the feature saturates earlier in relative terms. Already logged as F-15 in the audit plan | PROPOSAL: per-spec turn scale |
| A43 | `showdown.py:302–303` `force_switch`, `trapped` | two bits describe switch legality | **incomplete at gen 4** — Shadow Tag / Arena Trap / Magnet Pull make trapping *inferred*, and poke-env exposes `battle.maybe_trapped` separately (source-verified, `PE battle/battle.py:242`) | add a `maybe_trapped` bit to the gen-4 global block |
| A44 | `showdown.py:917–922` `battle_outcome`, `:869–905` `calc_reward` | outcome/faint-potential are generation-agnostic | **survives** — reads only `battle.won/lost/finished` and fainted counts | none |
| A45 | `showdown.py:621–645` `hl_event_sum` / `_HL_WEIGHTS` | five protocol tags (`faint`, `-fail`, `-supereffective`, `-resisted`, `-immune`) with metagrok's constants; attribution by `entry[2].startswith(who)` | **survives mechanically** (the tags are protocol-level and gen-agnostic), but the CONSTANTS are Huang & Lee's gen-7-era numbers, and the `-immune` term becomes far more common at gen 4 (Levitate, Flash Fire, Volt Absorb, Wonder Guard, immunities on 17 types) | re-derive or re-disclose per format; the term stays exactly zero-sum either way |

## 3.7 Search line (`rl/search/`)

All **tree-verified**. The search line is a gen-1 artefact throughout; nothing in it is
behind the spec.

| # | file:line | assumes | gen-4 status |
|---|---|---|---|
| A46 | `rl/search/shadow_battle.py:47` `PEMove(move_id, gen=1)`; `:54` `GenData.from_gen(1).pokedex` | gen-1 move/dex data feeding `embed_battle` | **breaks** |
| A47 | `shadow_battle.py:15` "gen1 bench carries no volatiles"; `:163` "gen1: force_switch iff our active fainted" | gen-1 state model | **breaks** (gen 4: bench mons carry Perish Song/Leech Seed/Substitute across switches; Roar/Whirlwind/U-turn force switches without a faint) |
| A48 | `rl/search/bridge.py:65–93` `GEN1_ENGINE_VOLATILES`, `EFFECT_VOLATILE_MAP` pinned against poke-engine 0.0.48 `src/gen1/state.rs` | a gen-1 engine module | **breaks** — a gen-4 search needs poke-engine's gen-4 module and its own volatile enum |
| A49 | `bridge.py:110–115` `_EXP_TERM=63`, `_DV=15`, `gen1_stat` | the gen-1 stat formula with stat exp and DVs | **breaks** — gen 4 uses IV/EV/nature |
| A50 | `bridge.py:315–316` `special_defense_boost = spa` | gen 1's single Special | **breaks** |
| A51 | `bridge.py:324–327` `is_locked_turn` = `avail[0].id in ("fight","recharge")` | gen-1 placeholders (note: a SECOND, divergent copy of A30's predicate, and it omits `struggle`) | **breaks**; also a pre-existing duplication |
| A52 | `rl/search/determinize.py:92, 110–123` `GenData.from_gen(1)`, gen-1 type chart, `randbats_prior` directly | one gen-1 determinizer | **breaks** (gen 4 must determinize items and abilities too) |
| A53 | `rl/search/expansion.py:37` `_ROLLS = range(217, 256)`; `:12–13` KO-skip recharge | gen-1 damage rolls (39 values) and the gen-1 Hyper-Beam-KO rule | **breaks** — gen 4 uses 16 rolls (85..100) and Hyper Beam always recharges |
| A54 | `rl/search/harvest.py:51, 102` `must_recharge` in the harvested dict | fine as a field; the surrounding state model is gen-1 | survives as a field |

**Cross-reference for `search_depreciation.md`:** the search line is the single largest
gen-1 surface in the repo outside the encoder (≈1,300 LOC across bridge/determinize/
expansion/shadow_battle/matrix), and every one of its five load-bearing invariants (A46–A53)
is generation-specific. Porting it to gen 4 is not a parameterization; it is a rewrite
against a different poke-engine module.

## 3.8 Format literals that are not the spec's business

`gen1randombattle` appears 138 times across `rl/ scripts/ configs/ tests/`. The
production-path defaults are `rl/collect.py:75` and `:116`, `rl/search/agent.py:51`,
`rl/envs/showdown_async.py:234`, `rl/envs/showdown.py:163/790/1187`, and
`scripts/eval_checkpoint.py:103`. All are keyword defaults; a gen-4 config that sets
`env_kwargs.battle_format` overrides the env ones, but **not** `fake_spaces()`'s (A31) or
`eval_checkpoint`'s seat 2 (A32). **tree-verified.**

Positively: the type chart is ALREADY per-format at every call site —
`GenData.from_format(battle_format).type_chart` at `showdown.py:810` and `:1008`, `collect.py:78/123`,
`showdown_async.py:156`, `search/agent.py:85`. Only `search/determinize.py:110–120`
hardcodes gen 1. **tree-verified.**

---

# 4. The numeric checks the task asked for

## 4.1 The gen-4 type table is 17, and poke-env's chart has an 18th entry that is not gen 4

**source-verified.** `PE data/static/typechart/gen4typechart.json` has 18 keys, of which
`fairy` carries `"isNonstandard": "Future"` (verbatim from the file:
`{"damageTaken": {...}, "isNonstandard": "Future"}`). `gen1typechart.json` has the same 18
keys with `dark`, `fairy`, `steel` all `"Future"`. So the gen-4 `types` tuple is the 17
real types (the gen-1 15 + DARK + STEEL) and must be hand-written in the spec exactly as
`GEN1.types` is (encoder_spec.py:210–218 explains why: `PokemonType` carries all 20 modern
members, so the one-hot layout would otherwise drift). Note the fill helpers use
`type_index.get(...)`, so an unlisted type silently writes nothing — the `_GEN2_SKETCH`
test at `tests/test_encoder_spec.py:422–434` exists precisely to catch that class.

## 4.2 `ID_SCALE = 256` at gen 4: exact and in-bounds, but NOT injective

Computed offline (`nice -n 19 python`, no network, no poke-env objects beyond `GenData`):

- **Exactness**: `round(float(np.float32(i/256.0)) * 256) == i` for every `i` in `0..1025`
  → True. 256 is a power of two and 493 < 2²⁴, so `id/256` is exact in float32 and the
  tokenizer's `round(x*256)` (entity_deepsets.py:138) recovers it exactly. **source-verified.**
- **Bounds**: max value `493/256 = 1.92578125`, comfortably inside the declared
  `Box(low=-1.0, high=4.0)` (showdown.py:832). Moves: `467/256 = 1.82421875`. **Gen 4 is
  fine.** (Forward note, not gen-4 work: gen 9's `1025/256 = 4.00390625` is OUTSIDE the
  declared high, so `ID_SCALE` becomes a per-spec field at gen 9 regardless.)
- **Injectivity — the real break.** `GenData.from_gen(4).pokedex` has 829 entries whose
  `num` ranges −5014..493; 714 of them fall inside 1..493. Restricted to the 295 species
  in the gen-4 randbats pool (`SD data/random-battles/gen4/sets.json`), **6 dex numbers are
  shared by more than one pool species, covering 33 species**:

  | num | species sharing it |
  |---|---|
  | 386 | deoxys, deoxysattack, deoxysdefense, deoxysspeed |
  | 413 | wormadam, wormadamsandy, wormadamtrash |
  | 479 | rotom, rotomheat, rotomwash, rotomfrost, rotomfan, rotommow |
  | 487 | giratina, giratinaorigin |
  | 492 | shaymin, shayminsky |
  | 493 | arceus + 16 typed formes |

  These formes differ in **types and base stats** (Arceus-Ghost vs Arceus-Water share one
  embedding row under `_species_id`). At gen 1 the mapping was injective by construction.
  **tree-verified** (pool file) + **source-verified** (poke-env dex).

  Consequence for `opp_action.canonicalise`: the frame-collision drop
  (`opp_action.py:210–214`) is keyed on MOVE ids, which stay injective, so the aux head is
  not directly hurt — but the species embedding is. PROPOSAL: gen 4 uses a
  `species_vocab: tuple[str, ...]` (the pool's own species strings, 295 + 1 unknown), not
  a `num` range.

## 4.3 Reflect / Light Screen: poke-env has the side-condition members

**source-verified.** `SideCondition` in poke-env 0.15.0 has 24 members including
`REFLECT`, `LIGHT_SCREEN`, `SPIKES`, `TOXIC_SPIKES`, `STEALTH_ROCK`, `SAFEGUARD`, `MIST`,
`LUCKY_CHANT`, `TAILWIND` — i.e. every gen-4 side condition. `Weather` has
`RAINDANCE, SUNNYDAY, SANDSTORM, HAIL` (plus later-gen members). `Field` has `TRICK_ROOM`
and `GRAVITY` (both gen 4). `Battle` exposes `side_conditions` (:1652),
`opponent_side_conditions` (:1516), `weather` (:1793), `fields` (:1409), all as
`dict[Enum, int]` (turn/layer counters).

So the docstring's instruction (encoder_spec.py:56–61) — MOVE Reflect out of `volatiles`
into a side block — is executable with no parser fork. Contrast the gen-1 situation
recorded at encoder_spec.py:226–231: there is no `Effect.LIGHT_SCREEN` member (confirmed:
`LIGHT_SCREEN` is absent from the 224-member `Effect` enum), which is why gen 1 carries
only REFLECT per-mon.

## 4.4 The gen-4 effect block has all its data in poke-env already

**source-verified**, by constructing `Move(id, gen=4)` objects (data only, no player/env):

| move | category | priority | volatile_status | side_condition | weather | force_switch | self_switch |
|---|---|---|---|---|---|---|---|
| stealthrock | STATUS | 0 | — | STEALTH_ROCK | — | F | F |
| spikes / toxicspikes | STATUS | 0 | — | SPIKES / TOXIC_SPIKES | — | F | F |
| roar | STATUS | **−6** | — | — | — | **T** | F |
| uturn | PHYSICAL | 0 | — | — | — | F | **T** |
| protect | STATUS | +3 | PROTECT | — | — | F | F |
| taunt / encore | STATUS | 0 | TAUNT / ENCORE | — | — | F | F |
| sunnyday | STATUS | 0 | — | — | **SUNNYDAY** | F | F |
| trickroom | STATUS | **−7** | — | — | — | F | F |
| willowisp | STATUS | 0 | — | — | — | F | F (status=BRN) |
| swordsdance | STATUS | 0 | — | — | — | F | F (boosts atk +2) |

A gen-4 effect block therefore needs **no new data file** — only new extractor slots
(`side_condition`, `weather`, `force_switch`, `self_switch`, `slot_condition`, and a
handful of `flags` such as `contact`, `sound`, `bypasssub`, `reflectable`).

## 4.5 `priority / 5.0` leaves the declared observation Box at gen 4

**source-verified + tree-verified.** Over the 181 distinct moves in the gen-4 randbats
movepools (`SD data/random-battles/gen4/sets.json` × `GenData.from_gen(4).moves`), the
priority range is **−7 .. +3**:

- `trickroom` −7 → `−7/5 = −1.4`
- `roar`, `whirlwind` −6 → `−1.2`
- `counter`, `mirrorcoat` −5 → `−1.0`
- `protect` +3 → `+0.6`

The observation space is declared `Box(low=-1.0, high=4.0)` (showdown.py:832, mirrored by
`fake_spaces` :176–179). Trick Room and the phazing moves would emit values **below the
declared low**. Gen 1's range is −1..+1 (all gen-1 moves), so `/5` never mattered there.
This is a concrete, cheap gen-4 bug that a spec field fixes (`priority_scale = 7.0`), and
it is exactly the class of thing the seam was built to hold.

## 4.6 The gen-4 randbats vocabularies are small and enumerable

**tree-verified** from `SD data/random-battles/gen4/{sets.json,teams.ts}`:

- 295 species; 262 distinct dex numbers (§4.2).
- 181 distinct moves across all `movepool` arrays.
- **101 distinct abilities** across all `abilities` arrays.
- 8 roles: Bulky Attacker, Bulky Setup, Bulky Support, Fast Attacker, Fast Support,
  Setup Sweeper, Staller, Wallbreaker.
- **Items are NOT in `sets.json`.** They come from `teams.ts::getItem` (:554) and the
  priority-item branch above it. The literal returns in 520–626 are a closed set of roughly
  25 items (Black Glasses, Choice Band/Scarf/Specs, Expert Belt, Focus Sash, Leftovers,
  Life Orb, Lum Berry, Lustrous Orb, Silk Scarf, Stick, Custap Berry, Quick Powder, Sitrus
  Berry, Toxic Orb, Chesto Berry, Damp Rock, …). So an item embedding needs a vocab of
  ~30, not the full item table — but reproducing the item *prior* means reproducing
  `getItem`'s conditionals.

---

# 5. The exact test contract a gen-4 spec must keep green

All **tree-verified** from `tests/test_encoder_spec.py`.

## 5.1 What must not move (gen-1 bit-identity)

The tape hash gate, `test_gen1_encoding_hash_is_pinned[<id>]`, replays six local tapes
(6000 rqid-aligned decisions) in a subprocess per flag combo and sha256s every
`embed_battle` vector. The five pinned lines, verbatim from `ORACLE`
(test_encoder_spec.py:66–74):

| flag combo (test id) | expected line |
|---|---|
| `()` — `bare` | `OBS_DIM=612 decisions=6000 sha256=e0217c10dc8678af4fba93adbc5ef76f930e9f5c4b3533d669d22f06328b509d` |
| `("POKEMON_RL_ENCODER_V2",)` — `v2` | `OBS_DIM=808 decisions=6000 sha256=273cd675b190cb7e4ca2a1253430f92a0474649e96c1da588f805bc97908a13e` |
| `("POKEMON_RL_ENCODER_V2","POKEMON_RL_ENCODER_IDS")` — `v2+ids` | `OBS_DIM=828 decisions=6000 sha256=0be192a8711def10cff546a12271156e006c982f7a739d16161da34c4d961ef6` |
| `("POKEMON_RL_NO_SET_PRIOR",)` — `bare+noprior` | `OBS_DIM=612 decisions=6000 sha256=8c2956c4bde8eb89d30c17391b4a86e44aa8e81ea0dc38feaef2d016482eb769` |
| `("POKEMON_RL_ENCODER_V2","POKEMON_RL_ENCODER_IDS","POKEMON_RL_NO_SET_PRIOR")` | `OBS_DIM=828 decisions=6000 sha256=ac57b7f88a54e209229a38ae897e8570271566f3f6619de2414933bf6044daee` |

Env vars scrubbed in the child: `POKEMON_RL_ENCODER_V2`, `POKEMON_RL_ENCODER_IDS`,
`POKEMON_RL_NO_SET_PRIOR` (`_ENCODER_VARS`, :76; `_child_env` :201–209). Tapes:
`data/fp_tapes2/run_92564.jsonl`, `data/fp_tapes/run_90336.jsonl`,
`data/fp_tapes3/run_98827.jsonl`, `data/fp_tapes_all/run_{4106,4115,4121}.jsonl` (:51–58);
the gate SKIPS where they are absent, so **a gen-4 spec must be validated on the training
box, not on a machine without the tapes.** The goldens were captured on the pre-F-08
encoder at commit `d546228` (:62–65) — "A changed hash is a changed encoding — fix the
code, never the golden" (:16–17, the module docstring).

Companion pins:
- `FINGERPRINTS` (:192–199) — the exact `ENCODER_FINGERPRINT` dict per combo, plus
  `test_fingerprint_records_the_semantics_the_hash_gate_pins` (:308–312) and
  `test_every_hashed_combo_is_distinguishable` (:315–322).
- `test_bare_process_is_612_v1` (:299–301): a bare child prints `["612","32","23","0"]`.
- `test_module_constants_are_gen1_derived` (:253–269) and
  `test_gen1_tables_are_the_literals_they_replaced` (:271–297) — including the numeric
  layout `(3, 9, 10, 15, 30, 32)`, `(7, 14, 16)`, `(8, 23)`.
- Elsewhere: `tests/test_encoder_ids_tapes.py:51` asserts `OBS_DIM == 828 and ID_DIM == 20`
  **at module import**, and `tests/test_encoder_v2.py:23` asserts the 808 arithmetic at
  import. A gen-4 spec that changes the process-global `OBS_DIM` would collect-error these
  two files, not fail a test. That is a real hazard for the "one process, one encoder"
  design (§6.4).

## 5.2 What a gen-4 spec must NOT regress (the spec-threading pins)

`_GEN2_SKETCH` (:371–379) exists because the hash gate is structurally blind to a helper
that ignores its `spec` argument. Each of these must still pass, and each has a gen-4
analogue that should be added:

- `test_fill_mon_offsets_follow_the_spec_not_the_module` (:382–400)
- `test_fill_active_offsets_follow_the_spec_not_the_module` (:402–420)
- `test_fill_move_type_onehot_follows_the_spec_not_the_module` (:422–434; asserts
  `vec[8+dark] == vec[23] == 1.0`, `not vec[8:23].any()`, and physical/special = per-move)
- `test_id_lookups_follow_the_spec_not_the_module` (:436–447)
- `test_move_slots_aliased_reads_the_specs_special_moves` (:449–455)
- `test_spec_for_format_registers_gen1_only` (:227–239) — **this one must be REWRITTEN**:
  it currently asserts `pytest.raises(NotImplementedError, match=r"no EncoderSpec for gen 4")`.
  Registering GEN4 flips that assertion.
- `test_n_actions_is_poke_envs_and_gen9_widens` (:242–248) — unchanged at gen 4.
- `test_embed_battle_refuses_a_non_gen1_spec` (:458–467) — **must be rewritten**: the
  refusal becomes "not a REGISTERED spec" rather than "not GEN1".
- `test_fake_spaces_shapes` (:344–358) — the gen-9 refusal assertion survives.

## 5.3 Tests a gen-4 spec would need to ADD (PROPOSAL)

1. **A gen-4 tape hash gate.** Same `_HASH_CHILD` shape, new tapes collected from
   `gen4randombattle` (needs-live-verification: the tapes cannot be collected until a
   server may run). Until then a gen-4 encoder has NO bit-identity pin at all — this is
   the single biggest schedule item hidden in the seam.
2. **A gen-4 spec-threading suite** mirroring §5.2 with a `_GEN5_SKETCH`-style probe, so
   the same "helper reads the module literal" class is caught for whatever new helpers the
   gen-4 blocks add (`_fill_side`, `_fill_global`, item/ability fills).
3. **Layout-invariant tests** for the three offsets `opp_action.py` restates
   (`_OPP_MOVE_ID_OFF`, `_OPP_FAINT_IDX`, `_REVEALED/_FAINTED/_IS_ACTIVE`) against the gen-4
   spec — today nothing cross-checks them.
4. **A bounds test**: every emitted vector lies inside the declared Box. §4.5 shows gen 1
   never needed one and gen 4 fails without a `priority_scale`. Cheap, offline, and it
   would have caught the Trick Room case.
5. **An injectivity test** on the species vocab (§4.2): `len(set(ids)) == len(pool)`.
6. **A fingerprint-distinguishability test across GENERATIONS**, extending
   `test_every_hashed_combo_is_distinguishable` (:315–322): no two (gen, flags) pairs may
   stamp the same fingerprint.

---

# 6. PROPOSAL — a gen-4 EncoderSpec, written against the landed dataclass

**Everything in this section is a PROPOSAL to reconcile with the maintainer. None of it
exists in the tree.** It is grounded in the landed `EncoderSpec` (encoder_spec.py:32–202)
and cites the consuming site for every new field.

## 6.1 Fields that just get gen-4 values (no dataclass change)

```python
GEN4 = EncoderSpec(
    gen=4,
    types=(BUG, DARK, DRAGON, ELECTRIC, FIGHTING, FIRE, FLYING, GHOST, GRASS,
           GROUND, ICE, NORMAL, POISON, PSYCHIC, ROCK, STEEL, WATER),   # 17, alphabetical
    statuses=(BRN, FRZ, PAR, PSN, SLP, TOX),                            # unchanged
    boost_keys=("accuracy","atk","def","evasion","spa","spd","spe"),    # unchanged
    base_stat_keys=("hp","atk","def","spa","spd","spe"),                # six
    volatiles=(...),                                                     # see 6.2
    special_move_ids=frozenset({"struggle","recharge"}),                 # "fight" is gen-1 only
    ...
)
```

Consuming sites, unchanged: `showdown.py:200/202/203/205/207/209/213/225/227/228/233/261/263/397`.
Derived offsets recompute themselves (encoder_spec.py:151–190), which is the whole point of
the landed design and is already proven by `_GEN2_SKETCH`.

## 6.2 New fields (the dataclass grows)

| proposed field | type | why | consumed at |
|---|---|---|---|
| `name: str` (e.g. `"gen4"`) | str | fingerprint identity (A6) | `ENCODER_FINGERPRINT` showdown.py:150–158 |
| `side_conditions: tuple[SideCondition, ...]` | tuple | Spikes/Toxic Spikes/Stealth Rock/Reflect/Light Screen/Safeguard/Mist/Lucky Chant/Tailwind, per side, with layer counts | a NEW `_fill_side(vec, o, battle, side, spec)`; two blocks in the global region |
| `weathers: tuple[Weather, ...]` | tuple | Rain/Sun/Sand/Hail + turns left | NEW `_fill_global` |
| `fields: tuple[Field, ...]` | tuple | Trick Room, Gravity (gen 4); terrain is gen 6 | NEW `_fill_global` |
| `item_vocab: tuple[str, ...]` | tuple | ~30 randbats items (§4.6); one embedding row each | new per-mon slot; `_fill_mon` |
| `ability_vocab: tuple[str, ...]` | tuple | 101 randbats abilities (§4.6) | new per-mon slot; `_fill_mon` |
| `species_vocab: tuple[str, ...]` | tuple | REPLACES `species_num_range` — dex `num` is not injective at gen 4 (§4.2) | `_species_id` showdown.py:374–382 |
| `move_vocab: tuple[str, ...]` (or keep `move_num_range=(1,467)`) | tuple/range | move nums stay injective, so either works; a format-scoped vocab is 181 rows vs 468 | `_move_id` :384–390 |
| `priority_scale: float` | float | the Box violation, §4.5. Gen 1 → 5.0 (bit-identical), gen 4 → 7.0 | `_fill_move` :260 |
| `turn_scale: float` | float | A42 / audit F-15 | `embed_battle` :299 |
| `status_counter_scale: float` | float | A38 | `_fill_active` :234 |
| `move_volatiles: tuple[Effect, ...]` | tuple | replaces `_MOVE_VOL_INDEX` (A10) | effect-block builder |
| `effect_features: tuple[str, ...]` | tuple | ordered names of the per-move effect extractors; `effect_dim = len(...)`, replacing `EFFECT_DIM = 23` (A4/A11) | `_fill_move` :264–266 |
| `set_prior_path` / `set_prior_loader` | callable or path | A15–A19 | `_opponent_move_slots` :582–599 |
| `move_data_gen: int` | int (= `gen`) | `_move_obj` must build `Move(id, gen=spec.gen)` (A8) | showdown.py:478–480 |

New derived properties, mirroring the landed pattern:

```python
@cached_property
def n_side(self) -> int: return len(self.side_conditions)
@cached_property
def side_dim(self) -> int: return self.n_side          # + counters if we encode turns
@cached_property
def global_dim(self) -> int: return 6 + len(self.weathers) + len(self.fields) + 2*self.side_dim + 1  # +maybe_trapped
@cached_property
def effect_dim(self) -> int: return len(self.effect_features)
def mon_dim(self, v2: bool) -> int: ...      # v1 width + item/ability slots + v2 speed edge
def obs_dim(self, v2: bool, ids: bool) -> int: ...
def fingerprint(self, v2, ids, set_prior) -> dict: ...
```

`mon_dim` / `move_dim` / `obs_dim` becoming spec METHODS (taking the process flags) is the
change that lets `embed_battle` drop its `spec is not GEN1` refusal (showdown.py:288–295).
The module globals `MON_DIM/ACTIVE_DIM/MOVE_DIM/OBS_DIM` then become
`_ACTIVE_SPEC.mon_dim(_ENCODER_V2)` etc., preserving every importer's name.

## 6.3 Illustrative gen-4 arithmetic (PROPOSAL, not a commitment)

With 17 types, 6 base stats, 6 statuses, and (say) 16 volatiles, 9 side conditions per
side, 4 weathers, 2 fields, item+ability slots as two id scalars:

- mon v1 = 3 + 6 + 1 + 6 + 17 + 2 = **35**; +1 v2 speed edge = **36**
- active = 7 boosts + 16 volatiles + 2 = **25**
- move v1 = 8 + 17 = **25**; + effect block (say 30) = **55**
- global = 6 + 4 weather + 2 field + 2×9 side + 1 maybe_trapped = **31**
- id suffix (ids on) = 20 own/opp species+move ids, **+ 12 item ids + 12 ability ids** if
  items/abilities enter as embedding indices rather than one-hots → 44

⇒ `OBS_DIM ≈ 31 + 6·36 + 25 + 4·55 + 6·37 + 25 + 4·55 + 44 = 1,183` at v2+ids, vs gen 1's
828. **Every existing checkpoint is invalidated** — which is fine, since a gen-4 policy is
a new model, but it means the gen-4 chapter cannot share a process with gen-1 evaluation
(§6.4).

## 6.4 How the spec gets selected — `spec_for_format` vs the F-07 block

Three options; I recommend (2).

1. **`spec_for_format` alone** (today's seam). Cheap; but the encoder's layout is decided
   by the format string of whichever env is constructed first, and the module globals are
   computed at import BEFORE any format is known. This does not actually work for
   per-spec strides without a lazy-init dance.
2. **F-07's `encoder:` config block, with the `spec:` key doing the selection**
   (`docs/proposals/F07_encoder_config_block.md` §3.1, lines 71–77: `spec: gen1  # F-08
   seam (§5); gen1 is the only legal value until the gen-4 chapter opens`). The proposal
   explicitly plans for this: §5.3 (lines 232–236) says "the block's `spec` key SELECTS the
   spec; `v2`, `ids`, `set_prior` are gen-1 spec parameters. Under Option 2 the fingerprint
   becomes `spec.fingerprint()`, `OBS_DIM` becomes `spec.obs_dim` … The block should land
   with `spec: gen1` as its ONLY legal value, so F-08 adds VALUES, never fields." **The
   gen-4 chapter is precisely the moment that adds the value `gen4`.** §5.4 (lines 237–242)
   names the sequencing question and says JOURNEY step 3 is where the spec is needed.
   **tree-verified** (the proposal text), **unruled** (its §7 is a list of eight open rulings).
3. **Both**: config block decides, `spec_for_format` stays as a cross-check that the
   configured spec matches the configured format, refusing on disagreement. This is one
   assert and closes the "gen-4 config, gen-1 spec" failure mode.

**One-process-one-encoder consequence** (from `scripts/eval_checkpoint.py:54–58`: "One
process has one encoder config (the flags are read at import)"): a gen-1-vs-gen-4
cross-play is impossible in one process, and the `PrefixSliceActor` shim
(`rl/networks/mlp.py:10–33`) has no analogue across generations — the gen-4 layout is not a
prefix of gen 1's. Any gen-4 eval harness must be a separate process. **tree-verified.**

---

# 7. Gen-1 encoder assumptions this breaks

Consolidated, in rough order of how much work each is:

1. **Block strides and `OBS_DIM` are module-global GEN1 values** computed at import
   (showdown.py:136–145) — the reason `embed_battle` refuses any other spec (:288–295).
   Nothing else can move until this does.
2. **The v2 effect block is gen-1 data end to end** — `Move(id, gen=1)` (:478–480), a
   6-entry move-volatile table (:490–498), and 23 slots with no side-condition, weather,
   force-switch or self-switch feature (:502–553).
3. **The set prior is gen-1 randbats**, both the file (`randbats_prior.py:63`) and the
   sampler (`:83–105`), and the gen-4 pool has an incompatible schema and a far more
   complex generator (`SD .../gen4/teams.ts:627`).
4. **`_species_id` assumes dex `num` is a unique row** — false for 33 of 295 gen-4
   randbats species (§4.2).
5. **The tokenizer's vocab defaults are gen-1 sizes** and CLAMP rather than error
   (`entity_deepsets.py:167–168`, `:143–144`).
6. **`priority / 5.0` leaves the declared `Box(low=-1.0)`** at gen 4 (§4.5).
7. **`_best_multiplier` equates the type chart with true effectiveness** — abilities did
   not exist at gen 1 (showdown.py:182–188; `PE pokemon_type.py:43–68`).
8. **`_spe_est` is a gen-1 stat proxy**; the ×0.25 paralysis factor survives, natures/items/
   abilities/Trick Room do not (showdown.py:555–565; `SD data/mods/gen4/conditions.ts:7–13`).
9. **`status_counter / 16` conflates sleep and toxic** under gen-1 semantics
   (showdown.py:234; `PE pokemon.py:194/415/483/615`).
10. **The global block has no weather / side-condition / field / `maybe_trapped` slots**
    (showdown.py:299–309).
11. **`_move_slots_aliased` approximates poke-env's re-basing rule with a SPECIAL_MOVES
    membership test**, and carries the gen-1-only `"fight"` (showdown.py:393–397 vs
    `PE singles_env.py:122–127`).
12. **The whole search line** is gen-1 (A46–A54); `rl/search/bridge.py:324–327` even keeps a
    second, divergent copy of the aliasing predicate.
13. **`ENCODER_FINGERPRINT` records no generation** (showdown.py:150–158), so a gen-4
    checkpoint would be unattributable by exactly the mechanism the fingerprint exists to
    prevent.
14. **`fake_spaces()` is called with no format at three sites** (`train.py:104`, `:480`,
    `eval_checkpoint.py:81`) and `eval_checkpoint.py:103` hardcodes the gen-1 format for
    seat 2.
15. **Two test files assert gen-1 widths at import** (`test_encoder_ids_tapes.py:51`,
    `test_encoder_v2.py:23`), so a process-global width change breaks collection, not a test.

What **survives** and should be said out loud, because the seam earned it: the type-chart
threading (`GenData.from_format(...)` at every call site but one), the per-move
physical/special flag (A14), `n_actions` = 10, the pointer head's 6+4, `battle_outcome`,
`calc_reward`'s potential-based faint shaping, the mask-desync mechanism, the D13(a)
`must_recharge` bool, `ID_SCALE = 256`'s exactness and bounds, and every derived `*_off`
property (proven by `_GEN2_SKETCH`).

---

# 8. Open questions for the maintainer

1. **Selection mechanism.** F-07's `encoder:` block with a `spec:` key (its §5.3 already
   plans it), `spec_for_format` alone, or both with a cross-check? F-07's §7 lists eight
   unruled questions of its own and its §7.8 ties the block to the "after the 100M readout"
   shelf condition — the gen-4 chapter is the natural moment to rule the whole thing at once.
2. **Do items and abilities enter as embedding ids or as one-hots?** Ids are 2 scalars/mon
   (44-dim id suffix) and share the tokenizer's existing machinery; one-hots are
   ~130 dims/mon and blow up `MON_DIM`. Recommendation: ids.
3. **Does the gen-4 set prior re-implement `teams.ts::randomSet` (the gen-1 fidelity
   standard, `randbats_prior.py:24–39`), or harvest empirical marginals from generated
   teams?** The gen-1 module's whole claim is "the marginals are NOT a heuristic". Holding
   that standard at gen 4 means porting `randomSet` + `cullMovePool` + `getAbility` +
   `getItem` (~250 lines of TS) — and the item prior is *only* obtainable that way.
4. **Do we encode opponent ITEM and ABILITY priors at all in v1 of the gen-4 encoder, or
   ship "revealed only" first?** The gen-1 lesson (`randbats_prior.py:11–22`) says the
   discarded prior is an irreducible BC bias; the counter-argument is that a gen-4 encoder
   with no prior at all is still a complete, testable artefact and the prior is a clean
   second lever.
5. **Does the gen-4 chapter carry the search line forward at all?** §3.7 says porting it is
   a rewrite against a different poke-engine module. (Feeds `search_depreciation.md`.)
6. **`priority_scale`**: fix by a per-spec divisor (keeps gen 1 bit-identical at 5.0), or by
   widening the declared Box (touches every checkpoint's declared space)? Recommendation:
   per-spec divisor.
7. **Species vocab**: format-scoped (295 randbats species) or generation-scoped (all 714
   gen-4 dex entries with `num` in 1..493, keyed by species string)? Format-scoped is
   smaller and injective; generation-scoped survives a format change without a re-index.
8. **When may gen-4 tapes be collected?** The gen-4 hash gate cannot exist without them,
   and they need a running server (barred during the ladder run).
9. **Does the gen-4 spec land as a NEW module (`encoder_spec_gen4.py`) or as a second
   constant in `encoder_spec.py`?** The file is 286 lines today; a gen-4 spec with vocabs
   would add several hundred, and F-20 already flags module size.

---

# 9. Cross-references for the other docs

- → `mechanics_delta.md`: §4.1 (17 types, poke-env's `fairy: isNonstandard "Future"` at both
  gens), §4.3 (side conditions / weather / fields present in poke-env), §4.5 (gen-4 priority
  range −7..+3 in the randbats pool), A37 (abilities break type effectiveness), A41 (gen-4
  paralysis is ×0.25 unless Quick Feet, `SD data/mods/gen4/conditions.ts:7–13`), A38 (status
  counters), A43 (`maybe_trapped` / trapping abilities).
- → `pokeenv_gen4_survey.md`: `get_action_space_size(4) == 10` (`PE singles_env.py:291–304`);
  `get_action_mask` is already gen-keyed (`:286`); the re-basing rule is `avail[0] not in
  known_ids`, NOT `SPECIAL_MOVES` (`:122–127`); `SideCondition`/`Weather`/`Field` member
  lists; `Move(gen=4)` exposes `side_condition`/`weather`/`force_switch`/`self_switch`;
  `Pokemon.item`/`ability`/`possible_abilities`/`stats` exist (`PE pokemon.py:1103/861/1215/1279`).
- → `encoder_requirements.md`: §6 in its entirety, §5 (the test contract it must keep and
  add), §3 (the assumption table it must close out row by row).
- → `anchors_and_eval.md`: `eval_checkpoint.py:103` hardcodes `gen1randombattle` for seat 2
  and `fake_spaces()` takes the gen-1 default at three sites (A31/A32) — any gen-4 anchor
  battery trips over these first; and the one-process-one-encoder rule (§6.4) means gen-1
  and gen-4 evals cannot share a process.
- → `open_questions.md`: §8, all nine, plus F-07's own §7 list (eight rulings) which the
  gen-4 chapter forces.
- → `search_depreciation.md`: §3.7 (A46–A54).

---

# 10. Unread / unverified

- **`rl/envs/showdown_async.py` was grepped, not read in full** (471 lines). I cite only
  lines 156/170/234 and have not audited its battle lifecycle for gen-4 assumptions.
- **`rl/search/matrix.py` (269 lines) and `rl/search/agent.py` (166 lines)** were grepped
  only; `matrix.py:226` calls `embed_battle(shadow_battle(...))`, so it inherits every
  encoder assumption, but I did not read its body.
- **`rl/agents/ppo.py`, `rl/buffers/*`, `rl/selfplay/pool.py`** — not read. If any of them
  restates an obs offset, I did not find it (the greps for `828/808/612` list `ppo.py`,
  `pool.py` and `mlp.py` as hits, and I read only `mlp.py`'s hits).
- **`docs/proposals/F07_encoder_config_block.md` §§1–4 and §3.2's two options** were read
  only in part (I read §3.1, the head of §3.2, §5, §6, §7). The Option-1/Option-2 mechanics
  for binding a config to import-time globals are relevant to §6.4 and I summarize them
  only from §5.
- **`RESULTS.md` §18 (the 100M readout, cell P3)** — located at line 1143 but not read;
  no claim here depends on it.
- **The gen-4 `teams.ts` sampler was structurally surveyed, not read line by line.** I cite
  function locations (`randomSet` :627, `cullMovePool` :84, `getAbility` :475, `getItem` :554)
  and the item return strings in 520–626. Whether a faithful gen-4 move marginal is
  tractable is an open question, not a finding.
- **needs-live-verification, all barred until the ladder run and any later fleet finish:**
  (a) that `gen4randombattle` actually reaches poke-env with the volatile/side-condition
  set assumed here — check: parse one gen-4 battle log and dump
  `battle.side_conditions | opponent_side_conditions | weather | fields` and every
  `mon.effects` key seen; (b) the gen-4 aliasing rate (`_move_slots_aliased` true-rate) and
  whether any non-`SPECIAL_MOVES` single-available-move turn occurs — check: count over a
  few thousand gen-4 decisions; (c) the gen-4 mask-desync rate against A34's gen-1
  calibration; (d) the gen-4 tapes needed for a hash gate (§5.3 item 1); (e) `SimpleHeuristicsPlayer`'s
  gen-4 competence (owned by `anchors_and_eval.md`, not by me).
- **literature-only, flagged as such:** nothing in this note rests on a secondary source.
  I did not consult `prior_work/README.md`, the Wang/H&L/Metamon texts, or any web page —
  every claim above is tied to a file on this disk.

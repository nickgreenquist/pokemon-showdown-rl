# Huang & Lee 2019 / metagrok as an encoder and anchor reference for gen 4

Agent: `huang_lee_metagrok` (gen-4 design sweep, source family: H&L paper + metagrok clone)
Date: 2026-09-04
Note path: `/private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/b1478b5b-c556-4e2e-9100-b0db7e234069/scratchpad/research/huang_lee_metagrok.md`

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (`SNAP` = main@2738025 snapshot: `rl/`, `scripts/`, `configs/`, `tests/`, `docs/`) or the vendored Showdown `data/`/`sim/`, i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk: the metagrok clone, the H&L paper text, poke-env source, PSPPO, FP, Wang, Metamon.
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work index without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm; BARRED until the ladder run and any later fleet complete.

## Sources actually read (path + range)

| Source | What I read |
|---|---|
| `prior_work/README.md` | lines 121, 240, 346, 422, 560–706 (the full `huang_lee_2019_selfplay_pokemon.pdf` entry incl. the 2026-08-26 per-update addendum, the 2026-08-28 deep-read addendum, and the "REFUTED, for the third time" block) |
| `prior_work/HUANG_LEE_DEEP_READ.md` | all 104 lines |
| `scratchpad/research/_huanglee_paged.txt` (converted from `prior_work/huang_lee_2019_selfplay_pokemon.pdf`) | p1 L1–62, p2 L63–130 (Table I, §III.A/B, Algorithm 1), p3 L131–279 (Fig. 1, Table II, §IV.A/B, footnotes 3–4), p4 L280–357 (Tables III/IV, §V, §VI, references) |
| metagrok clone `/Users/nickgreenquist/Documents/Projects/metagrok` | `expts/01.json` (whole); `metagrok/pkmn/models/v3_capacity.py` (whole); `metagrok/pkmn/models/v2_repro.py` lines 1–461 (whole); `metagrok/pkmn/dex.py` (whole); `metagrok/pkmn/formulae.py` (whole); `metagrok/pkmn/reward_shaper.py` (whole); `metagrok/pkmn/actions.py` (whole); `metagrok/pkmn/parser.py` (whole); `metagrok/pkmn/engine/baselines.py` (whole); `metagrok/pkmn/engine/player.py` (whole); `metagrok/pkmn/engine/navigation.py` (whole); `metagrok/pkmn/engine/core.py` lines 1–220; `metagrok/exe/simulate_worker.py` lines 1–80; `metagrok/exe/smogon_eval.py` lines 1–155; `metagrok/exe/head2head.py` lines 1–90; `metagrok/methods/ppo.py` (whole); `metagrok/methods/updater.py` (grepped lines 36–51, 86, 127–258); `metagrok/methods/learner.py` (grepped); `metagrok/integrated_rl.py` lines 315–340 + grep for `epsilon`/`num_matches`; `metagrok/torch_utils/masked_softmax.py` lines 1–60; `metagrok/formats.py` (whole); `metagrok/utils.py` line 37–39 (`to_id`); `js/engine.js`, `js/predef.js`; `dex/*.json` key counts via `jq` |
| `SNAP/rl/envs/encoder_spec.py` | lines 1–250 (module docstring, `EncoderSpec`, the gen-4 work list, `GEN1`, `spec_for_format`) |
| `SNAP/rl/envs/showdown.py` | lines 105–150 (dims), 600–690 (`hl_event_sum`), grep of block/offset names |
| `SD/data/random-battles/gen4/sets.json` | first two entries via `jq` (shape only) |

Two derived artefacts I produced in scratch (arithmetic only, no network, `nice -n 19`): a vocab-size recomputation from `metagrok/dex/*.json` replaying `dex.py::CategoricalFeature.__init__`, and a parameter-count reconstruction of `v2_repro.Policy(embed_size=128, pkmn_size=256)`. Both are reported inline below with their inputs.

---

## 1. The headline correction: **Table I is not the network they shipped**

**tree-of-record correction, source-verified.** The prior-work index and `HUANG_LEE_DEEP_READ.md` both quote Table I's dims (`species 1023`, `status 28`, `volatiles 23`, `stats 6`, `boosts 6`, `types 18`). Four of those six do **not** match the committed config that reproduces the paper's parameter count.

The paper states the network "contains 1,327,618 parameters in total" (`_huanglee_paged.txt` p2 L63–64). `expts/01.json` selects `metagrok.pkmn.models.v3_capacity.QuadCapacity` (`expts/01.json:2`), which is `v2_repro.Policy(embed_size = 128, pkmn_size = 256)` (`metagrok/pkmn/models/v3_capacity.py:9-10`). Replaying `v2_repro.Policy.__init__` (`metagrok/pkmn/models/v2_repro.py:36-86`) with the vocab sizes that `dex.py::CategoricalFeature` actually builds gives **exactly 1,327,618** — no slack. The reconstruction:

```
embeddings   species 1049x128 + abilities 238x128 + items 368x128 + moves 731x128 = 305,408
pkmn_affine  1222x256 + 256   = 313,088     (total_poke_size = 9*128 embeds + 70 numeric)
group_affine 256x256 + 256    =  65,792
policy_fc1   1445x256 + 256   = 370,176     (decision_size = shared 1061 + 256 + 128)
policy_mega/zmove/ultra 3x(1x256, no bias) =    768
policy_fc2   256x1 + 1        =     257
value_fc1    1061x256 + 256   = 271,872
value_fc2    256x1 + 1        =     257
                       TOTAL  = 1,327,618   == paper
```

So the **real** sizes are `species 1049`, `types 20`, `status 8`, `volatiles 22`, `sideConditions 11`, `weather 13`, `stats 5`, `boosts 7`. Table I's `1023 / 28 / 23 / 6 / 6 / 18` are stale or approximate. Vocab sizes are `len(json keys) + {2 sentinels}` de-duplicated (`metagrok/pkmn/dex.py:100-116`, `_key_to_extras` at `dex.py:18-29`); measured key counts from the clone's `dex/`: Movedex 729, Pokedex 1047, Abilities 236, Items 366, TypeChart 18, BattleVolatiles 20, BattleSideConditionsNew 9, BattleWeathers 12 (which already contains `+none`), BattleStatuses 28 raw but **filtered to `effectType == 'Status'` → 6** at `dex.py:63-65`.

Three of Table I's numbers do survive and are worth keeping: **moves 731** (729 + `+hidden` + `+unknown`), **abilities 238**, **items 368**.

**Where "status 28" came from — source-verified.** `dex/BattleStatuses.json` has exactly 28 top-level keys, and they are a grab-bag, not 28 status conditions: `arceus brn choicelock confusion deltastream desolateland flinch frz futuremove gem hail healreplacement lockedmove mustrecharge par partiallytrapped primordialsea psn raindance sandstorm silvally slp stall sunnyday tox trapped trapper twoturnmove`. The paper's "status indicator 28" is the size of the Showdown *client* `BattleStatuses` table at the time, not a claim about 28 statuses. The shipping code filters it to the six real statuses (`brn par slp frz psn tox`) plus `+none`/`+unknown` = 8. **Do not cite "H&L used a 28-dim status" as evidence for a wide gen-4 status block.** The genuinely wide block is `volatiles`.

**Where "volatiles 23" came from — source-verified.** `dex/BattleVolatiles.json` has 20 keys → 22 with sentinels, which is what `v2_repro.py:272` selects. `dex/BattleVolatilesNew.json` has 21 keys → 23, matching Table I; `BattleVolatilesNewV3.json` has 22 → 24. So Table I's 23 is a *different, adjacent* volatile table (`BattleVolatilesNew`, which adds `safeguard`), and the reproducing config uses the 22-wide one. Either way the count is ~20–22 volatile flags, and the `BattleVolatiles` list is worth reading verbatim because it is the design target: `airballoon autotomize confusion disable encore flashfire formechange itemremoved leechseed magnetrise perish1 perish2 perish3 slowstart smackdown substitute taunt transform typechange yawn`.

---

## 2. The full observation, as the code actually builds it

**source-verified**, `metagrok/pkmn/models/v2_repro.py:438-458` (`_default_poke_features`, marked `# DO NOT CHANGE THE ORDERING HERE`), with sizes resolved above. Per-Pokémon input vector = **1222 dims** at the paper's capacity; concatenated in *alphabetical* feature-name order (`v2_repro.py:220`, `ms = [v for k, v in sorted(out.items())]`).

| Feature | Dim (QuadCapacity) | Encoding | Source line |
|---|---|---|---|
| `abilities` (= "Possible Ability 1/2/3") | 128 | up to 3 ability ids, `pad(3)`, embedded, **mean-pooled** (`v2_repro.py:183`) | `v2_repro.py:439` |
| `ability` | 128 | current ability id → embedding | `:440` |
| `baseAbility` | 128 | pre-change ability id → embedding | `:441` |
| `baseSpecies` | 128 | species id → embedding (forme-invariant) | `:442` |
| `species` | 128 | species id → embedding (current forme) | `:453` |
| `item` | 128 | item id → embedding | `:447` |
| `prevItem` | 128 | consumed / removed item id → embedding | `:452` |
| `moves` | 128 | first 4 entries of `moveTrack`, `pad(4)`, embedded, **summed** (`v2_repro.py:218`) | `:450` |
| `lastmove` | 128 | one move id → embedding | `:448` |
| `boosts` | **7** | `accuracy, atk, def, evasion, spa, spd, spe`, each `/6.` | `:443`, `Boosts` at `:277` |
| `stats` | **5** | `atk, def, spa, spd, spe`, z-whitened over the gen7-randbats species stat table then `/3.` (`whiten_stats`, `:287-288`) | `:454`, `Stats` at `:276` |
| `hp` | 1 | `hp / MaxHp`, `MaxHp` = max HP over the gen7rb stat table | `:444`, `:283` |
| `maxhp` | 1 | z-whitened (`whiten_hp`, `:290-291`) | `:449` |
| `ppUsed` | 4 | per revealed move, raw use count (`div(1.)` = identity) | `:451` |
| `isActive` | 1 | 0/1 | `:445` |
| `isFainted` | 1 | 0/1 | `:446` |
| `status` | **8** | n-hot over `{brn,frz,par,psn,slp,tox,+none,+unknown}` | `:455` |
| `types` | **20** | n-hot, `pad(2)` first (so a mono-type mon lights `+hidden` too) | `:456` |
| `volatiles` | **22** | n-hot over the 20 client volatiles + `+none`/`+unknown` | `:457` |

Per side (`v2_repro.py:229-261`): each of 6 mon slots → `pkmn_affine` (1222→256, ReLU) → `group_affine` (256→256, ReLU) → **max-pool over the 6** (`:248`); the **active** slot's 256-d vector is pulled out by index and zeroed when there is no active (`:250-258`); plus `sideConditions` n-hot **11**. Side representation = `[active 256 ‖ maxpool 256 ‖ sideConditions 11]` = 523.

Global (`v2_repro.py:293-302`): `weather` n-hot **13**, `weatherTimeLeft` 1, `weatherMinTimeLeft` 1.

Trunk = `[player 523 ‖ opponent 523 ‖ weather 13 ‖ wMinTimeLeft 1 ‖ wTimeLeft 1]` = **1061** (`shared_size`, `v2_repro.py:46-50`).

Value head: `1061 → 256 (ReLU) → 1` (`:85-86`, `:107-111`). **The value head sees only the trunk — no per-action input, no mask.** Same convention as ours (`CLAUDE.md`: "the value head is never masked").

Policy head (`v2_repro.py:113-134`, the shared pointer scorer): for each of the 22 actions, score = `MLP([trunk 1061 ‖ switch-target pkmn 256 ‖ move 128])` → `Linear(1445→256)` + a learned per-gimmick bias → ReLU → `Linear(256→1)`. Move actions get the active's move embedding and a zero pkmn slot; switch actions get the target's pkmn embedding and a zero move slot (`:119-126`). Weights shared across all 22 — the paper's "the parameters for computing p ... are shared among all n actions" (p2 L129-130).

**Masking is renormalisation, not a sentinel — source-verified.** `masked_softmax.py:21-25` computes `max(xs + log(mask))`, `exp(xs-max)*mask`, then divides by the masked sum; illegal actions get exactly 0 probability and a zeroed log-prob. Paper p2 L116-122: "we take a mask s ∈ {0,1}^n as part of the input, and renormalize probabilities". **Our repo does the opposite by convention** — `rl/common/masking` with a finite `-1e8` sentinel, "never `-inf`" (`CLAUDE.md`). Not a defect either way; note it if a gen-4 pointer head is written.

### Where the state comes from: the real Showdown client, in-process

**source-verified.** `js/engine.js` instantiates the Showdown **client** `Battle` object and feeds it the protocol stream (`battle.add(changes); battle.fastForwardTo(-1)`), and `metagrok/pkmn/engine/core.py:24-27` runs that JS inside `py_mini_racer`. So every belief feature (`moveTrack`, `prevItem`, `volatiles`, `sideConditions`, `abilities`, `weatherTimeLeft`) is whatever a human's browser would know — no server-side peeking. This is architecturally different from poke-env (which parses the same stream in Python) but informationally equivalent.

Post-processing that matters (`core.py:60-197`):

- **Opponent stats are estimated, not observed** (`core.py:181-187`): `F.estimate_stats(baseStats, level)` with `EV = 510/6 = 85` and `IV = 15` (`formulae.py:9-21`). HP is converted from the percentage the client sees to absolute: `hp_pct = hp/maxhp; maxhp = stats['hp']; hp = stats['hp']*hp_pct`. **source-verified caveat:** gen-7 randbats actually rolls 31 IVs, not 15 — their estimator is systematically low on every stat. A gen-4 encoder should take the level *and* the IV/EV spread from the actual `random-battles/gen4` generator rather than copy this constant.
- **"Possible Ability 1/2/3" is a dex lookup, not a learned belief** (`core.py:196`, `val['abilities'] = {k: to_id(v) for k, v in val['abilities'].items()}` — the client's pokedex ability slots `{0, 1, H}`). It is the *species'* legal ability set, padded to 3 and averaged. Structurally the same idea as our randbats set prior, but strictly weaker: no conditioning on the observed set.
- **Illusion/Zoroark is handled by species-clause dedup** (`core.py:65-77`), and `_pad_pokes` carries a `# TODO: Fix this for zoroarks` (`v2_repro.py:460`). Irrelevant to gen 4 (Zoroark is gen 5).
- The player's own side is overwritten from the `|request|` payload (`core.py:79-127`), and the active mon's `moveTrack` is **reordered to request order** (`core.py:126-127`, `_reorder_movetrack`) so that move-slot *i* in the action space is move *i* in the observation. This is exactly the "move slot means the mon's move i" invariant our `special_move_ids` handling protects in gen 1.

### Unrevealed opponent slots

**source-verified.** `_pad_pokes = pad(6, default_poke(), 'head')` (`v2_repro.py:461`) pads the opponent's revealed list up to 6 with `default_poke()` (`v2_repro.py:410-432`): `species/baseSpecies/item/prevItem/ability/baseAbility/lastmove = CONST_HIDDEN`, `stats = MeanStats`, `hp = maxhp = MeanHp`, `status = CONST_NONE`, `types = []`, `moveTrack = []`, `volatiles = {}`, `abilities = {}`.

The sentinel resolution is a design detail worth stealing: `keys.sort()` puts `'+hidden'` at index **0** and `'+unknown'` at index **1** of every embedded vocabulary (verified by replaying `CategoricalFeature.__init__` over the clone's `dex/*.json`), and every embedding is declared `padding_idx = 0` (`v2_repro.py:53-56`). **So "hidden/unrevealed" is the frozen zero vector, and it is the same index that an absent slot resolves to** (`to_index` returns 0 for a falsy name, `dex.py:118-119`). Embeddings additionally carry `max_norm = 1.`. For n-hot features the index-0 sentinel is `'+none'` instead.

### What is Markov-restoring — and the three holes

Restoring (all **source-verified**, `v2_repro.py:438-458`, `:293-302`):

- `lastmove` **on all 12 Pokémon**, not just the actives — restores Choice lock, Encore/Disable target, locked-move (Outrage/Petal Dance) and two-turn context.
- `ppUsed` (4 per mon) — restores PP depletion, so Struggle, PP-stall and Choice-item pressure are visible.
- `prevItem` — restores a consumed berry / Knocked-Off item.
- `weatherTimeLeft` and `weatherMinTimeLeft` (2 scalars) — restores weather duration, including the "5 or 8 turns depending on an unseen item" ambiguity that the client tracks as a min/max pair.
- `boosts` including `accuracy`/`evasion`.
- `species` vs `baseSpecies`, `ability` vs `baseAbility` — restores forme changes and ability overwrites.

Holes (**source-verified**, by absence):

1. **No status counters.** `default_poke()` builds `statusData = dict(sleepTurns=0., toxicTurns=0.)` (`v2_repro.py:406-412, 428`) but **no `PokeFeature` reads it** — sleep turns and the Toxic counter never reach the network. For gen 4 that is a much larger hole than for gen 7: badly-poisoned damage is `n/16` and Rest/sleep-talk lines turn on the sleep counter. Our gen-1 encoder already carries a `status_counter` slot (`SNAP/rl/envs/showdown.py:136-137`, `ACTIVE_DIM = boosts + volatiles + status_counter + preparing`), so we are *ahead* of H&L here — keep it.
2. **No hazard layer counts.** `sideConditions` is a presence-only n-hot (`v2_repro.py:315`), so Spikes 1/2/3 and Toxic Spikes 1/2 collapse to one bit each. Gen 4 is the generation where this first bites hard (Stealth Rock + Spikes + Toxic Spikes all legal, Rapid Spin the only removal).
3. **No side-condition durations, no turn counter.** Reflect/Light Screen/Tailwind/Safeguard turn counters are absent; so is the battle turn number.

Also absent by design: **no precomputed type chart, no move base power / accuracy / category / priority features**. Moves are *pure* embeddings. This is the index's "Zero precomputed type chart" claim, and it is **source-verified** here: the only place a type chart appears in metagrok is the scripted baseline (`engine/baselines.py:16-40`), never the policy.

---

## 3. gen4 applicability of their feature set

| Feature | gen 4? | Note |
|---|---|---|
| species / move / item / ability embeddings | **yes** | gen 4 has items and abilities; gen 1 has neither, so these are *new blocks* for us either way. Vocabularies shrink: gen-4 dex is 493 species / 467 moves (`SNAP/rl/envs/encoder_spec.py:66-68`, tree-verified as our own recorded ranges). |
| "Possible Ability 1/2/3" | **yes, and improvable** | gen-4 randbats `sets.json` carries an explicit `abilities` list **per role** (`SD/data/random-battles/gen4/sets.json`, e.g. `venusaur → sets[i].abilities = ["Overgrow"]` — source-verified shape only). Conditioning on the *set* prior beats H&L's species-wide list. Cross-ref: the `encoder_requirements.md` and randbats-prior agents. |
| `lastmove`, `ppUsed`, `prevItem`, `boosts`, `status`, `types`, `hp/maxhp`, `isActive`, `isFainted` | **yes** | all gen-agnostic. |
| `volatiles` (their 20) | **partly** | gen-4-valid from their list: `confusion disable encore leechseed magnetrise perish1/2/3 slowstart substitute taunt transform typechange yawn autotomize?* flashfire itemremoved formechange`. `airballoon` is a gen-5 item; `smackdown` and `autotomize` are gen-5 moves. Missing for gen 4 and needed: Trick Room (a *field* effect), Gravity, Aqua Ring, Ingrain, Embargo, Heal Block, Torment, Attract, Foresight/Odor Sleuth, Miracle Eye, Lock-On, Roost's typeloss, Stockpile counters, Aqua/Focus Energy. **literature-only on the exact gen-4 volatile roster — hand the roster question to the `mechanics_delta.md` agent; I checked only which of H&L's 20 are gen ≥ 5.** |
| `sideConditions` (their 9: `auroraveil lightscreen reflect safeguard spikes stealthrock stickyweb tailwind toxicspikes`) | **partly** | `auroraveil` gen 7, `stickyweb` gen 6 — drop both. gen 4 adds **Lucky Chant** and **Mist** as side conditions (literature-only; the mechanics agent should confirm against `SD/data/mods/gen4/`). Reflect/Light Screen are 5-turn *side* conditions from gen 2 — our gen-1 spec deliberately keeps `Effect.REFLECT` in `volatiles` and its docstring already flags the move (`SNAP/rl/envs/encoder_spec.py:229-241`, tree-verified). |
| `weather` (their 13) | **partly** | drop the four gen-6 terrains (`electricterrain grassyterrain mistyterrain psychicterrain`) and the three gen-6 primal weathers (`primordialsea desolateland deltastream`). gen 4 keeps `sunnyday raindance sandstorm hail` + `+none`; gen 4 has **no terrain**. Their `pseudo` key is the client's catch-all. |
| `weatherTimeLeft` / `weatherMinTimeLeft` | **yes, and more load-bearing than in gen 7** | gen 4 has Damp Rock / Heat Rock / Smooth Rock / Icy Rock (8 vs 5 turns) but no weather-extending abilities, so the min/max pair is exactly the right belief shape. |
| `species` vs `baseSpecies` (forme split) | **yes** | not for megas (gen 6) but for Giratina-Origin, Shaymin-Sky, Rotom appliance formes, Deoxys formes, Castform, Cherrim, Arceus plates. **Keep the split.** |
| mega / Z-move / ultra action rows + `policy_mega/zmove/ultra` biases | **NO — gen 7 only** | `actions.GEN7SINGLES` (`metagrok/pkmn/actions.py:13-19`) is 4 moves + 6 switches + 4 mega + 4 zmove + 4 ultra = **22**. gen 4 has **no** gimmick: the action space is 4 + 6 = **10**, which is what our `EncoderSpec.n_actions` already computes (`SinglesEnv.get_action_space_size(gen)`, "10 through gen 5", `SNAP/rl/envs/encoder_spec.py:137-140`, tree-verified). Delete all three bias vectors and all 12 gimmick rows. |
| team preview | **NO for randbats** | `parser.team_preview_actions_singles` exists and `EnginePkmnPlayer.action` shuffles a random team order when `teamPreview` fires (`engine/player.py:51-58`) — gen4randombattle has no team preview, same as gen1. |

---

## 4. The max-damage-typed bot, at verbatim precision

**Paper definition** (`_huanglee_paged.txt` p3 L261-266), verbatim:

> "• most-damage - The agent selects the highest damage move each turn. This aligns with beginner level play.
> • most-damage-typed - Similar to most-damage, except that the agent has knowledge of Pokémon type weaknesses and resistances."

**Actual algorithm — source-verified**, `metagrok/pkmn/engine/baselines.py:48-152`. `MostDamageMovePlayerTypeAware()` is `MostDamageMovePlayer(type_aware = True)` (`:152`).

Score for a legal move action (`baselines.py:128-142`):

```python
def compute_power(move_key, opponent = None):
  movedex_entry = Movedex.get(move_key)
  if not movedex_entry: return 0.
  move_type = movedex_entry.get('type') or ''
  power = movedex_entry.get('basePower', 0.)
  if movedex_entry.get('ohko'): power = 120.
  multiplier = 1.
  if move_type and opponent:
    multiplier = compute_multiplier(move_type, opponent['types'])
  return power * multiplier
```

i.e. **`basePower × type-effectiveness against the defender's types`, and nothing else**. Explicitly absent: **STAB, accuracy, physical/special category, attacker Atk/SpA, defender Def/SpD, boosts, items, abilities, expected number of hits, priority, status-move value, HP/KO reasoning, weather.** OHKO moves are scored as base power 120. `compute_multiplier` (`:144-150`) multiplies over both defender types, reading the *client* `BattleTypeChart` `damageTaken` codes remapped `0→1×, 1→2×, 2→0.5×, 3→0×` (`:16-37`).

Selection (`baselines.py:102-114`), verbatim:

```python
    if move_candidates:
      random.shuffle(move_candidates)
      move_candidates.sort(key = self._move_sort_key, reverse = True)
      selected = move_candidates[0][-1]
    else:
      random.shuffle(switch_candidates)
      switch_candidates.sort(key = self._switch_sort_key)
      selected = switch_candidates[0][-1]
```

Consequences, all source-verified:

- **It never switches voluntarily.** A switch is chosen only when the legal-action mask offers no move at all — a forced switch after a faint, or a fully-disabled/no-PP active. Ties among equal-power moves are broken uniformly at random (shuffle, then stable descending sort).
- **Status moves score 0**, so it uses them only when every legal move has zero effective power (e.g. everything is immune) — then it picks one at random.
- **A 0× matchup does not make it switch**; it will happily keep clicking a move scored 0 if that is still the max.
- On a **forced** switch it picks the mon minimising `weakness = Σ_{t ∈ opponent_active.types} effectiveness(t → my types)` (`:96-100`, `:125-126`) — a crude "resists the opponent's *types*" heuristic (not their moves), sorted ascending.
- The non-typed `most-damage` variant is the same code with `opp_active = None` (`:85-86`), i.e. pure base power.

**The result — source-verified** (`_huanglee_paged.txt` p3 L251-258, Table II, "1000 gen7randombattle matches between RL-rb and each of the other agents", p3 L277-278):

| Opponent | Wins | Losses |
|---|---|---|
| random | 995 | 5 |
| most-damage | 929 | 71 |
| **most-damage-typed** | **829** | **171** |
| pmariglia | 612 | 388 |

Wins + losses = 1000 in every row, so **ties are folded into non-wins** — the same convention as our locked eval protocol. Confirmed in code: `head2head.py:60-63` increments `wins[j]` only on `'winner'` and asserts the alternative is `'loser'` or `'tie'`.

**What the index says about the bot table not transferring — literature-of-record, quoted from `prior_work/README.md`:**

> "Their bot table does NOT transfer: 0.829 is vs a max-damage-typed bot far weaker than SH, and their 0.612 is vs the 2019 ancestor of foul-play, pre-Rust."

and, from the 2026-08-28 addendum:

> "their strongest scripted baseline (most-damage-typed, 0.829) is far weaker than SH — the bot-table non-transfer above now cuts BOTH ways: it removes 'we are behind H&L' as a framing, and most-damage-typed is trivial to implement if that comparison ever needs to be measured rather than argued."

`HUANG_LEE_DEEP_READ.md` adds the reasoned (not measured) comparison: `SimpleHeuristicsPlayer` "switches on a composed matchup score, uses setup moves, and scores expected damage with STAB, accuracy, expected hits, and a boost-adjusted stat ratio", with the explicit caveat "most-damage-typed is not in our anchor battery, so this is a reasoned comparison of bot strength, not a measured one."

**My reading for the gen-4 anchor design (source-verified premises, my inference):** the code above settles the strength question qualitatively. A bot that never switches, ignores STAB and accuracy, and ignores both sides' stats is strictly below `MaxBasePowerPlayer`-plus-type-awareness and far below SH. Implementing it for gen 4 is ~40 lines against poke-env's `Move.base_power`, `Move.type`, and a **gen-4 type chart** (`GenData.from_gen(4).type_chart`; poke-env ships `data/static/typechart/gen4*.json` — I did not open it, cross-ref the `pokeenv_gen4_survey.md` agent). Two gen-4 traps for anyone porting `compute_multiplier` verbatim: **the gen-4 chart has no Fairy, and Steel resists Ghost and Dark** (both removed in gen 6). Copying metagrok's `dex/BattleTypeChart.json` would silently use gen-7 effectiveness.

---

## 5. Recipe facts for a gen-4 pre-reg

All **source-verified** unless marked.

- **Both seats are harvested.** `simulate_worker.py:46-52` writes p1 and p2 trajectories from every battle; `integrated_rl.py:328-330` filters to one seat *only if* the experiment sets `player`, which `expts/01.json` does not. Paper Algorithm 1 (p2 L75-84) is explicit: "update the neural network parameters using the **2m** self-play matches as training data". So **one update consumes 7,680 matches = 15,360 episodes.**
- **m = 7680 is arbitrary, by the authors' own words** (p2 L102-105), verbatim: *"For the number of matches played per iteration, we picked m = 7680 (a completely arbitrary choice)."* The index's ruling stands: cite H&L as an **existence proof** that enormous batches work in pure self-play randbats, never as a target; any batch pre-reg carries the gradient-noise argument as its rationale.
- **Scale and cost** (p2 L104-111): 500 iterations × 7,680 = **3,840,000 self-play matches**, "trained using Google Cloud Platform over the course of 6 days and cost approximately $91 USD".
- **Hyperparameters — from `expts/01.json` only; the paper publishes none.** Verbatim:
  ```json
  "num_iters": 500,
  "simulate_args": {"num_matches": 7680},
  "updater_args": {"vbatch_size": 8192, "clip_param": 0.1,
                   "weight_decay": 2e-6, "opt_lr": 2e-4, "num_epochs": 6},
  "updater_buffer_length_iters": 1,
  "reward_args": {"gamma": 0.95, "lam": 0.9, "shaping": {...}}
  ```
- **No entropy bonus, no grad clip.** `updater.py:37` `self._entropy_coef = kwargs.get('entropy_coef')` → `None`, and `ppo.py:50-51` only adds an entropy term `if self._entropy_coef is not None`. `updater.py:46` `max_grad_norm = kwargs.get('max_grad_norm')` → `None`, and `updater.py:178-179` clips only when it is set. Neither key is in `expts/01.json`. **The paper's §III.B text says PPO "combines expected reward, accuracy of state-value prediction, and a bonus for high entropy policies" (p2 L104-108) — that is generic PPO prose, and the config overrides it.** (This is the index's standing "paper text never overrides the config" ruling.)
- `value_coef` defaults to `1.` (`updater.py:38`); value loss is the clipped/`max` form (`ppo.py:45-48`). `updater_buffer_length_iters: 1` = no cross-iteration replay; `num_epochs: 6` reuses each transition 6× within the update.
- **Training play is sampled, ε = 0, true mirror self-play.** `simulate_worker.py:23-25` sets `p2_policy = p1_policy` unless `--p2-policy-tag`; `expts/01.json` sets neither `epsilon` nor `p2` (`integrated_rl.py:83-88` only passes them if present); `EnginePkmnPlayer.action` samples with `np.random.choice(..., p=probs)` unless `play_best_move` (`engine/player.py:66-69`). Paper Algorithm 1: "Sample from π to select the action to take at each turn."
- **The 5-term zero-sum shaping, verbatim from `expts/01.json`:** `faint -0.0125`, `fail -0.005`, `supereffective -0.0025`, `resisted 0.0025`, `immune 0.005`, with `new_style: true, zero_sum: true`.
  **The attribution rule is what makes the signs make sense** (`reward_shaper.py:79-97`): `mentions()` returns `+1` if the protocol line's third field names *your* side and `-1` otherwise, then `reward += delta * v`. Showdown's `|-supereffective|`, `|-resisted|`, `|-immune|` and `|-fail|` all name the **target/failing** Pokémon. So `supereffective: -0.0025` means "−0.0025 when *we* are hit super-effectively, +0.0025 when *they* are" — which is precisely the paper's "+0.0025 whenever the player's Pokémon makes a super effective move" (p2 L92-95). The config and the paper agree; the negative sign is a target-indexing artefact, not a contradiction. **Our own `hl_event_sum` reproduces all five weights and this attribution rule exactly** (`SNAP/rl/envs/showdown.py:619-643`, tree-verified), including the deliberate `|-fail|` quirk documented at `:612-618`.
  Faint contribution caps at 6 × 0.0125 = 0.075 per side against a ±1 terminal.
- **Coupling caution, from the index and re-confirmed here:** `gamma 0.95` + `lam 0.9` + the dense 5-term shaping arrived together; we run `gamma 1.0` sparse. Do not lift one without the other in a gen-4 arm.
- **Their batches are exactly return-balanced per battle** (one winner + one loser trajectory from the same game) — a structural property our one-seat-vs-pool batches do not have.

### The ladder protocol

**source-verified**, p3 L256-264, verbatim:

> "Every 100 training iterations, we would evaluate it by having it play 300 matches on the gen7randombattle ladder on the Pokémon Showdown server, and used its Glicko-1 rating at the end of matchmaking as an indicator of skill. At the end of 500 training iterations, RL-rb attains a 1677 Glicko-1 rating, which roughly corresponds to a 72% chance of defeating an opponent selected uniformly at random from the ladder."

So the 1677 is the **fifth point of a trajectory** (iterations 100/200/300/400/500 × 300 matches each), not a single endpoint read. The 72% is that Glicko pushed through Showdown's GXE formula, not an independent measurement (index: "verified: 71.94%") — quoting both is quoting one number twice.

Footnote 4 (p3 L277-279), verbatim, and directly supportive of our GXE/Glicko-over-Elo choice:

> "Pokémon Showdown exposes an Elo rating for competitors, but we do not use that because their Elo rating is not a true Elo system. [10] contains a discussion of rating systems for Pokémon Showdown servers."

**New this pass (the deep-read listed the account question as unresolved by the paper — the *script* has a default):** `smogon_eval.py:55` is `username = args.username or utils.random_name()`, so **the released ladder tool defaults to a fresh random account per evaluation** and only reuses one if `--username` is passed. Other defaults: `--num-matches 1000` (they ran 300), `--max-concurrent 4`, `--wait-time-before-move 3.0`, `--host sim.smogon.com --port 80`, and `--play-best-move` is an **off-by-default flag** (`smogon_eval.py:143-149`) — so unless they passed it, the 1677 was earned by a **sampled** policy, making it a lower bound on the greedy policy's rating. The final rating is scraped from `https://pokemonshowdown.com/user/<username>.json` (`smogon_eval.py:32-33`) — the same profile-JSON route our own ladder landmine records as the one that works for unlisted accounts. `conf.timer = True` (`smogon_eval.py:92`) — they also request the timer, matching our `start_timer_on_battle_start` rule.

### Negative results

- **Trick Room was never learned — source-verified**, Table III (p4 L280-291). Row = the team RL-rb pilots, column = pmariglia's team:

  | RL-rb team \ pmariglia team | OF | PS | TR |
  |---|---|---|---|
  | OF | 0.435 | 0.21 | 0.87 |
  | PS | 0.82 | 0.24 | 0.8 |
  | **TR** | **0.145** | **0.12** | 0.635 |

  200 matches per cell. The randbats-trained policy piloting the Trick Room team wins 0.145 / 0.12 against the two non-mirror opponents. §V-B-1 (p4 L334-342): "many of the agent's losses can be attributed either to an inability to properly utilize the team's core strategy or an unfavorable edge case to a conventional strategy." **Read: pure randbats self-play does not discover multi-turn setup.** Directly relevant to gen 4, where Trick Room, Rain Dance/Swords Dance sweeps, Baton Pass chains and hazard-stacking are all multi-turn plans that randbats sets do contain.
- **Fine-tuning collapsed general play — source-verified**, §V-B-2 and §V-C (p4 L344-352, L280-288). 50 further iterations × 7,680 = 384,000 matches on the fixed 3-team metagame produced RL-meta, whose 3team win rates rise sharply (Table IV: 0.555–0.99 vs pmariglia). Then, verbatim: *"In a head-to-head matchup of RL-rb and RL-meta in the generalized format (gen7randombattle), RL-meta only wins 77/500 matches."* = **0.154**. A 10%-of-training specialisation run destroyed randbats ability. Relevant to any gen-4 plan that proposes warm-starting from a gen-1 checkpoint or fine-tuning a general policy onto a sub-distribution.
- §VI's own framing (p4 L292-300) is the optimistic read of the same fact: "the agent must be retrained for each. This is a minor issue, as training the agent is inexpensive and can be bootstrapped using a previously trained model as a baseline." **§V-C is the evidence against that sentence.**

---

## 6. gen1 encoder assumptions this breaks

Our gen-1 encoder is a flat `OBS_DIM = 828` vector (v2 + ids) laid out as `global 6 | our 6 mon blocks | our active extras | our 4 move blocks | opp 6 mon blocks each with a revealed flag | opp active extras | opp 4 move blocks | 20-dim id suffix` (`SNAP/rl/envs/showdown.py:128-146`, tree-verified). H&L's design breaks the following assumptions, all of which the landed `EncoderSpec` seam already *names* as gen-4 blockers (`SNAP/rl/envs/encoder_spec.py:44-84`):

1. **"A Pokémon has no item and no ability."** Gen 1 has neither, so there is no block for them. H&L spend **4 of their 9 embeddings** (`item`, `prevItem`, `ability`, `baseAbility`, plus the 3-slot `abilities` belief) on exactly this. In gen 4 these are first-class and partly hidden — this is the single largest structural addition.
2. **"A Pokémon's identity is base stats + types + an id scalar."** Our species identity enters only through base stats, types, and the `id/256.0` suffix (`showdown.py:110-125`). H&L's 128-d learned embedding over 1049 species is the alternative, and it is what makes their DeepSets trunk work without a type chart. Gen 4's 493 species make a real embedding table cheap. Cross-ref `encoder_requirements.md`.
3. **"There is no weather and there are no side conditions."** Our `GLOBAL_DIM = 6` has no weather block, and `Effect.REFLECT` sits in the *per-mon* `volatiles` tuple because gen 1 makes it a per-mon effect that dies on switch-out (`encoder_spec.py:229-241`). H&L carry `weather (13) + weatherTimeLeft + weatherMinTimeLeft` globally and `sideConditions (11)` **per side**. Gen 4 needs both, and Reflect/Light Screen must *move out* of `volatiles` into the new side block.
4. **"7 volatile flags is enough."** Ours is 7 (`CONFUSION, FOCUS_ENERGY, LEECH_SEED, MUST_RECHARGE, PARTIALLY_TRAPPED, REFLECT, SUBSTITUTE`). Theirs is 20–22 and still misses gen-4 staples (Trick Room, Gravity, Ingrain, Embargo, Heal Block, Torment, Attract). Expect the gen-4 `ACTIVE_DIM` to roughly triple.
5. **"Move slot *i* is the mon's move *i*, and the action space is 10."** Both survive gen 4 unchanged (`n_actions` = 10 through gen 5), and H&L's 22-wide `GEN7SINGLES` is the thing to *not* copy. Their `_reorder_movetrack` shows they had to enforce the same slot invariant we protect with `special_move_ids`.
6. **"One Special stat; 5 base-stat keys."** Ours drops `spd` (`base_stat_keys=("hp","atk","def","spa","spe")`). H&L carry `atk def spa spd spe` (5, HP separately) — gen 2+ needs the real split, so the gen-4 spec's `base_stat_keys` is 6.
7. **"Status has no counter worth more than one slot."** We already carry a `status_counter` and H&L carry none — this is one place where **copying H&L would be a regression**. Gen 4's Toxic counter and sleep counter both matter; keep and widen ours.
8. **"Sentinel = zero row."** We map unknown/unrevealed to id `0` (`showdown.py:118-125`, "Unknown/unrevealed -> 0"), which is exactly H&L's `padding_idx = 0` + `'+hidden'` collision. Independent convergence; worth stating in the gen-4 spec as a deliberate choice rather than an accident. Note their subtlety: `'+unknown'` at index 1 is a *distinct, trainable* row for "we know this exists but not what it is", which we do not currently have.
9. **"Masking uses a finite `-1e8` sentinel."** H&L renormalise instead. Not a break, but the gen-4 pointer head (if we build one) should say which it uses; ours is a harness contract (`CLAUDE.md`).
10. **"Opponent stats can be read."** Ours reads what poke-env exposes; H&L *estimate* opponent stats from base stats + level with fixed EV/IV (`core.py:181-187`). Gen-4 randbats levels vary per species (`sets.json` carries a per-species `level`), so whichever route we take must be stated explicitly in the spec.

---

## 7. Open questions for the maintainer

1. **Is most-damage-typed worth adding to the gen-4 anchor battery?** The 2026-08-28 addendum says it is "trivial to implement if that comparison ever needs to be measured rather than argued". For gen 4 the argument to add it is stronger than it was for gen 1: it is the only anchor that lets us place a gen-4 number on H&L's published axis at all, since SH's gen-4 strength is unknown and Foul Play's gen-4 support is a separate question. The losing argument: it is a fourth anchor in a battery the maintainer has already capped at three, it is descriptive-only, and a bot that never voluntarily switches will be beaten so badly that the number carries no gradient.
2. **Does the gen-4 chapter adopt a curve-shaped ladder read (H&L's 5 × 300) or a single endpoint?** H&L's protocol is published support for the curve; our own landmine says one vs-SH rung at n=3000 is worth ±0.02 and that curves are the right unit. Losing argument: five ladder points cost five accounts' worth of human-facing games and the ladder run is the scarcest resource we have.
3. **Do we build a species/move/item/ability embedding trunk for gen 4, or extend the flat encoder?** H&L is the existence proof for the embedding + DeepSets + shared pointer-head route at 1.33M params and $91. Losing argument: our whole ladder, all our checkpoints and the entire eval harness are built on a flat `Box(OBS_DIM,)`, and `rl/networks/entity_deepsets.py` already exists as the compromise — a gen-4 architecture change on top of a gen-4 encoder change confounds the chapter's first result.
4. **Do we copy the 5-term shaping into gen 4?** We already have `hl_event_sum` and a gen-1 arm that read null at the 12M instrument. Gen 4 has far more `-supereffective`/`-immune`/`-resisted` traffic (18 types, abilities like Levitate/Flash Fire/Volt Absorb generating `-immune`), so the signal density is genuinely different. Losing argument: it is coupled to `gamma 0.95`, and re-opening a settled null is off-arc.
5. **Status counters and hazard-layer counts: do they go in the v1 gen-4 spec or wait?** They are H&L's clearest holes and gen 4's clearest needs, but each is an `OBS_DIM` change and therefore a one-way door for checkpoints.

## 8. Unread / unverified

- **The PDF figures themselves.** I read Fig. 1 only through the extracted text layer (`_huanglee_paged.txt` p3 L131-248), which is a scrambled column dump. Two of its labels conflict with the code and I resolved both in favour of the code: Fig. 1 labels the per-Pokémon move-embedding pool "Average", but `v2_repro.py:218` is `out['moves'] = moves.sum(1)` (a **sum**); the "Possible Ability" pool is genuinely a mean (`v2_repro.py:183`). I did not open the PDF to confirm the figure text.
- **poke-env's gen-4 type chart / move data.** Not opened — the `pokeenv_gen4_survey.md` agent's family. My "no Fairy, Steel resists Ghost/Dark in gen 4" note is **literature-only**.
- **The exact gen-4 volatile and side-condition rosters.** I checked only which of H&L's entries are gen ≥ 5. The authoritative list must come from `SD/data/mods/gen4/` — the `mechanics_delta.md` agent's job. My gen-4 additions (Lucky Chant, Mist, Trick Room, Gravity, Ingrain, Embargo, Heal Block, Torment, Attract) are **literature-only**.
- **`metagrok/pkmn/transforms.py`, `battlelogs.py`, `datasets.py`, `misc/count_categoricals.py`, `models/v4_speedup.py`, `expts/XX-test.json`, the released checkpoint.** Not read; nothing in my task depended on them, and none is cited above.
- **Anything requiring a live server.** No comparison of most-damage-typed against `SimpleHeuristicsPlayer` was measured — the deep-read's "0.829 vs a weaker bot, 0.718 vs a stronger one" remains a **reasoned** comparison. The check that would settle it (**needs-live-verification**, BARRED): implement `MaxDamageTypedPlayer` for gen 4 against poke-env's gen-4 type chart, then run it head-to-head against `SimpleHeuristicsPlayer` for n ≥ 1000 in `gen4randombattle` on the local server, ties as non-wins, and report SH's win rate. That single number tells us where H&L's 0.829 axis sits relative to ours.
- **The gen-4 `teams.ts` item-assignment logic.** I confirmed only that `sets.json` carries per-role `abilities` and a per-species `level`; item selection lives in `teams.ts`, which I did not read.

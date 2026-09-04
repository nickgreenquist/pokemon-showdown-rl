# poke-env 0.15.0 for gen4randombattle — what the pinned library supports, and where it is wrong

> **design_gen4 status header.** Written 2026-09-04 on branch `gen4-design`,
> DOCS ONLY — nothing under `rl/` changed. **Arc position:** the target is
> JOURNEY step 3 (gen4 encoder + model). This design work is **maintainer-ruled
> PREPARATION running AHEAD of step 2 (gen1 ladder #3)**; it is not a
> pre-registration and it launches nothing. Method deviation, recorded: the
> brief's two-memo + adversarial-synthesis cycle was NOT run (maintainer ruling
> 2026-09-04, budget); this is a single-writer synthesis of three research notes
> (poke-env battle-state survey, poke-env env/action/player survey, Wang's
> poke-env fork diffed against 0.15.0), reconciled where they disagree.
>
> **Verification status per claim** — every claim carries exactly one tag:
> - `[tree]` **tree-verified** — checked against a file in this repo
>   (main@2738025) or the vendored `showdown/` (0.11.11 @ 59da482).
> - `[src]` **source-verified** — checked against the installed poke-env 0.15.0
>   source (`poke_env/...`, `/opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env`)
>   or Wang's fork diffs (`prior_work/wang_fork_diffs.md`, gitignored).
> - `[lit]` **literature-only** — not re-checked against a primary here.
> - `[live]` **needs-live-verification** — only a running server or battle can
>   confirm it; BARRED until the live ladder run and any later fleet complete;
>   the check is stated beside the tag. **No server was started, no Player /
>   Env / PSClient was constructed, and no battle was played for this doc.**
>
> **Sources read for this doc:** research notes `pokeenv_battle_state.md`,
> `pokeenv_env_layer.md`, `wang_pokeenv_fork.md`, and `showdown_gen4_pool.md`
> §8; each cites `poke_env/<file>:<line>` from the installed package.
> **Feeds:** `encoder_requirements.md` (§3–6 are its input),
> `anchors_and_eval.md` (§7), `open_questions.md` (§10).
> **Depends on:** `mechanics_delta.md` for the rules themselves; this doc is
> about what the library exposes and gets wrong, not about the game.

## 0. The shape of the answer

`[src]` poke-env 0.15.0 has **no gen-4-specific code path**. One `Battle`, one
`parse_message`, one `Pokemon`, one `Move`; the generation enters only through
`GenData.from_gen(4)`'s three static JSON tables, a handful of `gen <= 3` /
`gen >= 5` guards, and whatever the server sends. Gen 4 sits on the "modern" side
of nearly every guard, so far fewer things are special-cased away than in gen 1.
The action space is **identical to gen 1** (`Discrete(10)`). The consequences:

| what works out of the box | what does not | severity for a gen4 encoder |
|---|---|---|
| action space 10, same index layout, same mask code, same wrapper hooks, no team preview, team-less format path, `/timer on` knob | `maybe_trapped` is parsed and then **ignored** by the mask (ability trapping is gen4-live) | medium: rejected choices and re-picks; a mask/legality mismatch |
| items and abilities arrive for our own six mons in every request (`item`, `baseAbility`); opponent items/abilities are revealed by protocol events into `mon.item` / `mon.ability` | no `original_item`: a consumed berry, a Knocked-Off item and "confirmed itemless" all collapse to `None`; **ability-set weather is indistinguishable from move weather and its turn stamp is refreshed every turn** | high: two hidden-information features an encoder must track itself |
| `status_counter` tracks sleep attempts and toxic stage; toxic resets on switch | the sleep counter **bumps twice on a Sleep Talk turn**; Rest on a toxiced mon inherits a stale counter | medium: 25 Sleep Talk + 35 Rest sets in the pool |
| every gen4 volatile a move can inflict maps to an `Effect` member except Mud/Water Sport; every gen4 side condition, weather and field maps | Encore's and Disable's **move name is dropped**; Flash Fire is **cleared one use early**; Perish Song is four members (`PERISH0..3`), partial trapping is six per-move members | low–medium: a few post-processing rules |
| `gen4moves.json` (486 moves, per-move category, priority −7..+5), `gen4pokedex.json`, `gen4typechart.json` ship and are gen-4 data | the chart has **18 keys (Fairy included)**; `num` is not injective over formes; `Return`'s base power reads **0**; all Hidden Power variants share `num` 237; **no ability table, no item table, no opponent stat estimator, no gen4 damage calculator** | high: the spec must enumerate its own vocabularies and compute opponent stats itself |

## 1. Action space and mask

- **Size 10.** `[src]` `SinglesEnv.get_action_space_size(gen)` returns
  `6 + 4 * (1 + gimmicks)` with gimmicks 0 for every gen ≤ 5
  (`poke_env/environment/singles_env.py:290-304`; probed `[10,10,10,10,10,14,18,22,26]`
  for gens 1–9). The env derives gen from the format string
  (`GenData.from_format` is `int(format[3])`, `poke_env/data/gen_data.py:121-124`).
  `[tree]` The landed seam already knows: `rl/envs/encoder_spec.py:277-281` appends
  an action-head item to its refusal list only if `n_actions != GEN1.n_actions`, and
  for gen 4 that is `10 != 10`. **The gen4 encoder work is a feature problem, not
  an action-space problem.**
- **Index layout.** `[src]` `0..5` switch to `list(battle.team.values())[action]`;
  `6..9` use move `mvs[(action-6) % 4]`; `10..25` are the gimmick slots and
  unreachable in gen 4; `-1`/`-2` (forfeit / default) cross the seam only from
  `order_to_action` (`singles_env.py:83-91, 109-112, 182-185`).
- **Switch slot order.** `[src]` `battle.team` is filled in request order
  (`poke_env/battle/abstract_battle.py:1287-1319`), and the server emits
  `side.pokemon` in slot order, so switch index i is the server's team slot i,
  fixed at the first request; with no team preview slot 0 is the lead — identical
  to gen 1. `order_to_action` matches on `base_species` (`singles_env.py:195-198`);
  two mons sharing a base species would collide, which randbats' species
  uniqueness prevents.
- **Move index and re-basing.** `[src]` `singles_env.py:122-143`: move action `6+j`
  means the mon's own move slot j unless there is exactly one legal move **and it is
  not one of the known four** — then `mvs` re-bases onto `available_moves`. In gen 4
  only `struggle` and `recharge` inhabit that case (`fight` is gen-1-only — §1.5).
  Choice lock, Encore, Taunt, Torment and the locking moves leave the single legal
  move inside the known four, so no aliasing occurs. `action_to_order` raises
  `ValueError` on a mask-illegal order (`:144`); our tree's `_recover_mask_desync`
  (`rl/envs/showdown.py:849-867` `[tree]`) intercepts it and carries over unchanged.
- **Mask construction.** `[src]` `singles_env.py:232-288`: `switch_space` gated on
  `not battle.trapped`; `move_space` from the known four filtered by
  `available_moves`; a lone `SPECIAL_MOVES` entry (Struggle, recharge) maps to index
  6; the gimmick lists are empty because `can_mega_evolve / can_z_move /
  can_dynamax / can_tera` are set only from request keys a gen4 server never sends
  (`poke_env/battle/battle.py:122-129`; `showdown/sim/pokemon.ts:1143-1194` `[tree]`).
  Disabled moves (PP 0, Taunt, Encore, Choice lock, Disable) are dropped from
  `available_moves` by the request's `disabled: true` (`poke_env/battle/pokemon.py:
  809-811`). Under `battle._wait` the mask marks index 0 legal while `valid_orders`
  is `[DefaultBattleOrder()]` — a pre-existing quirk `_recover_mask_desync` already
  covers.
- **The gen4-only hazard: `maybe_trapped` is parsed and ignored.** `[src]`
  `Battle.parse_request` reads `maybeTrapped` (`battle.py:130-131`) and exposes
  `battle.maybe_trapped` (`:242-248`), but nothing in singles consumes it: the mask,
  `valid_orders` (`battle.py:275-282`) and `SimpleHeuristicsPlayer` read only
  `trapped`. `[tree]` `maybeTrapped` is set by Arena Trap, Magnet Pull, Shadow Tag
  (`showdown/data/abilities.ts:196-203, 2506-2512, 4146-4152`), abilities gen 1 does
  not have; the pool carries Dugtrio (Arena Trap), Wobbuffet (Shadow Tag), Magnezone
  and Probopass (Magnet Pull) — 5 set entries. A switch chosen against a hidden
  trapper is rejected with `|error|[Unavailable choice]` and a corrected request
  (`showdown/sim/side.ts:984-1000, 527-537`); poke-env sets `_trying_again` and
  re-queries the policy on the same mask (`poke_env/player/player.py:318-325`;
  `poke_env/environment/env.py:432-446`), so the agent can re-pick the same
  illegal switch. Wang's fork guarded both SH and the random helper on this
  (`prior_work/wang_fork_diffs.md:3824-3830, 3941-3949`); 0.15.0 has neither.
  `[live]` the actual rejection rate in gen4randombattle: count
  `battle.maybe_trapped and not battle.trapped` at decision time and
  `[Unavailable choice]` lines over a few hundred self-play games. `maybeDisabled`
  / `maybeLocked` are likewise emitted (`showdown/sim/pokemon.ts:1126-1133`) and
  parsed nowhere; Imprison is their only gen4 source and is not in the pool.

## 2. Battle lifecycle, request, wrapper

- **No team preview.** `[tree]` `showdown/config/formats.ts:4239-4244` lists no Team
  Preview rule; `battle.teampreview` stays `False`, the `teampreview` branches in
  `player.py:341-345` and `single_agent_wrapper.py:52-55` (which would raise
  `NotImplementedError`) never fire. Same cold-open fog of war as gen 1.
- **Team-less format.** `[src]` `get_next_team()` returns `None`, `set_team(None)`
  sends `/utm null` before each challenge or search (`player.py:705-709`;
  `poke_env/ps_client/ps_client.py:328-332`); the open-team-sheet machinery is
  gated on `"vgc"` and inert.
- **The two knobs the landmines depend on are generation-independent.** `[src]`
  `start_timer_on_battle_start` defaults `False` in `PokeEnv`, `SinglesEnv` and
  `Player` (`env.py:175`, `singles_env.py:39`, `player.py:66`) and sends `/timer on`
  at `player.py:230-231`; `[tree]` our tree forces it `True`
  (`rl/envs/showdown.py:1194`, `rl/envs/showdown_async.py:262-272`). Wang's fork
  added timers and then reverted them — not precedent for dropping ours.
  `max_concurrent_battles=1` is a literal at `env.py:273, 292, 355, 375`, exactly as
  `rl/envs/showdown.py:1207-1208` records; only `showdown_async.py:258` widens it.
- **What a gen4 request populates.** `[src]`+`[tree]` `Battle.parse_request`
  (`battle.py:61-140`) is gen-agnostic; the server fills, for our own six mons,
  `stats` (5 keys), **`baseAbility` (the real ability; gen 1 sends `""`)** and
  **`item` (the real item; gen 1 sends `""`)** (`showdown/sim/pokemon.ts:1165-1183`).
  The live `ability` key is gen 7+ (`:1186`), so a mid-battle ability change
  (Trace) is visible only through `|-ability|` messages. `forceSwitch` is parsed as
  `[False][0]` (`battle.py:90`, Wang's fix #20 upstreamed). `[live]` that a gen4
  force-switch request omits the `active` key (the mechanism by which
  `move_space` empties): confirm on one captured request.
- **Wrapper hooks.** `[src]` `PokeEnv.__setattr__` wraps the obs into
  `Dict({"observation", "action_mask": Box((10,))})` (`env.py:317-333`); `step`
  emits obs + mask, `calc_reward`, `calc_term_trunc` (`env.py:400-467, 772-788`),
  all generation-blind. `SingleAgentWrapper.step` runs the opponent's
  `choose_move` synchronously inside our step and converts it with
  `order_to_action` (`single_agent_wrapper.py:22-84`) — the hook D25's
  opponent-action label rides (`rl/envs/showdown.py:400-420` `[tree]`), unchanged.
- **`evaluate_player` is unusable** — it hard-asserts gen 8
  (`poke_env/player/utils.py:137-140`); `cross_evaluate` is fine. `[src]`

## 3. The battle-state model, field by field

### 3.1 `Pokemon.item` `[src]`
Three-valued: `"unknown_item"` (born state, `poke_env/data/gen_data.py:14`;
`pokemon.py:114`), `None` (known to hold nothing **or just lost it**), or an id.
Own side: overwritten each request; Showdown sends `""` for no item, so an
itemless own mon reads `""` — three falsy-but-distinct cases. Opponent side:
revealed by `-item`, `-enditem`, `-damage`/`-heal [from] item:` sniffing, Trick
(`abstract_battle.py:889-892, 1193-1199`), Frisk. **Knock Off, a consumed berry
and a confirmed-itemless opponent are indistinguishable afterwards** (all
`end_item` → `None`, `pokemon.py:405-410`); `_check_heal_message_for_item`
deliberately refuses to assign anything containing "berry"/"herb" after the fact.
There is no `original_item` anywhere (Wang's fork #18 `_orig_item` — ABSENT). An
encoder wanting "it had a Sitrus / it was Choice-locked before Trick" must track
that from the message stream itself.

### 3.2 `ability` / `possible_abilities` `[src]`+`[tree]`
`possible_abilities` comes from the dex entry (`pokemon.py:657-662`), and
**if the species has exactly one dex ability and gen ≥ 3, `ability` is set at
first sight — opponent included** (`:661-662`). Over the 295 pool species: **161
have one dex ability (auto-known), 134 have two**; `gen4pokedex.json` has no `"H"`
slot, so never three. **Two vocabularies, both real:** the dex-derived
`possible_abilities` strings over the pool number **122**, while the abilities the
generator can actually assign number **101** (`showdown/data/random-battles/gen4/
sets.json`), and **277 of 295 species have a unique set-listed ability** — so a
set prior collapses far more ability uncertainty than poke-env's dex list does.
Reveal paths: `-ability`, `move … [from] ability:`, `-damage`/`-heal [from]
ability:`, `-immune … [from] ability:`, `-endability`, Frisk, Skill Swap; Trace has
a dedicated branch (`abstract_battle.py:777-793`) that keeps `base_ability =
"trace"` and sets the copied one as `temporary_ability` (Wang's fix #17 —
UPSTREAMED, richer). **Not revealed into `.ability`:** `-activate … ability: X`
(poke-env records an `Effect`, not the ability: Forewarn, Hydration, Shed Skin,
Sticky Hold, Suction Cups, Synchronize), `-weather … [from] ability:` (the
`[from]`/`[of]` are dropped, `abstract_battle.py:754-761`), `cant|…|ability:
Truant` (reason dropped, `:742-744`), `-curestatus … [from] ability: Natural
Cure` (cause dropped). In practice the weather setters in the pool are all
single-ability species and therefore already auto-known.

### 3.3 `stats` / `base_stats` `[src]`+`[tree]`
Six keys with a real `spd` (`pokemon.py:121-128, 938-948`). Own side filled from
the request. **Opponent side: `stats` stays `None` forever — poke-env has no
opponent stat estimator** (`compute_raw_stats` in `poke_env/stats.py` is called
only from the teambuilder path). But gen4 randbats stats are exactly computable:
EVs 85 everywhere, IVs 31, no nature (`showdown/data/random-battles/gen4/teams.ts:
648-649, 725-737`), so `stat = floor((2*base + 52) * level/100) + 5` and
`hp = floor((2*base + 52) * level/100) + level + 10`, with two documented
deviations (`evs.atk = 0`/`ivs.atk` 0 or 3 on physical-less sets; `evs.spe = 0`
on Gyro Ball / Metal Burst / Trick Room sets; `:711-719`) and the HP-parity shave
(`:696-707`). Level is parsed from `details` (default 100; `pokemon.py:669-716`)
and spans 67–100 in the pool, so **level is the input to the one stat estimator
we will have**.

### 3.4 `boosts` `[src]`
Seven keys, clamped ±6, wired to every `-boost`-family message
(`pokemon.py:182-188, 338-358, 524-528`). `switch_out` clears boosts
unconditionally; `[live]` whether the server re-emits boosts after a Baton Pass —
moot in this pool (Baton Pass is on no set).

### 3.5 `status` / `status_counter` — usable, with two known defects
`[src]` Seven `Status` members in every gen. `status_counter` "only counts TOXIC
and SLEEP" (`pokemon.py:1302-1308`): sleep bumps on `cant_move()` (from
`|cant|<mon>|slp`, `:189-195`) and on `moved()` while asleep (`:482-483`); it
resets on `cure_status`. Toxic bumps once per turn in `end_turn()` (`:412-415`)
and **resets on `switch_out`** (`:613-615`), the correct gen-3+ rule. `[tree]`
gen4 sleep is `random(2,6)` decremented per move attempt
(`showdown/data/mods/gen4/conditions.ts:23-52`), so `status_counter ∈ {0..3}`
while asleep and P(wake on the next attempt) = 1/(4 − counter): **a sleep-turn
feature is well-defined in gen 4.** Two defects, reconciled across the notes:
1. **Sleep Talk double-bump.** `[src]` Showdown emits two `|move|` lines for a
   Sleep Talk turn; `abstract_battle.py:726-741` calls `moved()` for both (the
   preemptive Sleep Talk line and the `overridden_move` line), and neither call
   suppresses the SLP bump, so the counter advances by 2 per Sleep Talk turn.
   Wang's fork moved the bump to avoid exactly this (#10) — ABSENT in 0.15.0. One
   research note read the counter as "correctly tracked"; it did not consider the
   double `moved()` call, so the fork-comparison reading stands, subject to `[live]`
   a parse-only replay of a recorded two-line Sleep Talk sequence through
   `Battle.parse_message` (a unit test, but it constructs battle objects, which
   this session is barred from). 25 sets carry Sleep Talk, 35 carry Rest.
2. **Stale counter on Rest.** `[src]` the `status` setter and `set_hp_status`
   (`pokemon.py:1298-1300, 534-541`) do not reset `_status_counter`, so Rest on a
   toxiced mon starts its sleep clock at the toxic stage.

Sleep Clause Mod is on for the format `[tree]`, so at most one opponent mon is
asleep at a time.

### 3.6 `effects` — coverage of the `Effect` enum `[src]`
224 members; `Effect.from_showdown_message` falls back to `Effect.UNKNOWN` with a
warning, never an exception (`poke_env/battle/effect.py:243-271`). Every
`volatileStatus` a gen4 move can inflict maps except `mudsport` / `watersport`
(44 of 46). Of 185 literal effect strings greppable out of the vendored sim, 12
land in `UNKNOWN`, only two gen4-legal (`move: Beat Up`, `ability: Magma Armor`),
a lower bound (single-quoted literal forms only). Specifics an encoder must know:

| effect | member | notes |
|---|---|---|
| SUBSTITUTE | yes | presence only; **no Substitute HP anywhere in poke-env** |
| PROTECT | yes | cleared in `end_turn()`; the consecutive counter is `protect_counter` (§3.7) |
| ENCORE / DISABLE | yes, turn-countable | the **move name is dropped** (`-start` branch consumes only `event[3]`) |
| TAUNT / EMBARGO / HEAL_BLOCK / MAGNET_RISE / SLOW_START | yes, turn-countable | counters count **up from 0**, not down |
| CONFUSION / CURSE / YAWN / ATTRACT / LEECH_SEED / INGRAIN / AQUA_RING / DESTINY_BOND / FOCUS_ENERGY | yes | Yawn is ended silently when the sleep lands |
| Perish Song | no `PERISH_SONG`; `PERISH0..3` | the countdown is readable from which member is present |
| partial trapping | `PARTIALLY_TRAPPED` only via `from_data`; gen4 sends `-activate … move: Wrap/Bind/Fire Spin/Clamp/Whirlpool/Sand Tomb` → six per-move members, each turn-countable | OR them into one bit; none of these moves is in the pool |
| FLASH_FIRE | yes | **bug:** `moved()` ends it after one Fire move (`pokemon.py:498-503`); in Showdown it persists until switch-out (`showdown/data/abilities.ts:1331-1367` `[tree]`). Six pool species carry Flash Fire |
| MUST_RECHARGE | yes, but the live signal is the bool `must_recharge` | see §3.7 |
| LIGHT_SCREEN / REFLECT | no `Effect.LIGHT_SCREEN`; `Effect.REFLECT` is the gen1 legacy | in gen 4 both arrive as `-sidestart` → `SideCondition`; the gen1 spec's `Effect.REFLECT` slot must move to the side block |

`Pokemon.switch_out` clears every effect regardless of classification; the
`ends_on_switch`/`is_volatile_status` helpers are never called inside poke-env —
they exist for us.

### 3.7 `must_recharge`, `preparing`, `protect_counter`, `first_turn`, `revealed` `[src]`
`must_recharge` is a bool set by `-mustrecharge`, cleared in `moved()` and
`switch_out` (`pokemon.py:1168-1178`); `preparing` is set by `-prepare`
(`preparing_move` gives the move; only Solar Beam is in the pool);
`protect_counter` increments on a successful protect/detect/endure and zeroes
otherwise, on switch-out, and on any `breaks_protect` effect (`:477-480, 565,
607`); `first_turn` is `_active_turns == 1` (the Fake Out feature); `revealed` is
set on `switch_in` and never reset.

### 3.8 `moves` and PP `[src]`
`moves` is a `MoveSet` that swaps in Transform / Mimic sets in place
(`pokemon.py:1160-1166`). **PP is tracked client-side for both sides**: `max_pp =
entry["pp"] * 8 // 5`, decremented by `Move.use()` from `moved()`, 2 under Pressure
via `_pressure_on` (which needs the target's ability to already read
`"pressure"`; 20 of the 22 Pressure species are single-ability and auto-known).
Wang's double-deduction fix (#2) is upstreamed by a cleaner mechanism
(`abstract_battle.py:735-737`; `move.py:123-130`). poke-env's own
`check_move_consistency` asserts exact PP for gen 4 under
`strict_battle_tracking=True` (`pokemon.py:261-306`) — the maintainers' statement
that gen4 PP tracking is trustworthy. `[tree]` no move in the pool can grow a
mon's move dict past four (no Assist / Me First / Metronome / Copycat / Mimic;
Sleep Talk is handled; the one Ditto set uses Transform, handled structurally), so
**the gen4 mask-desync surface from called moves is empty as vendored**.

## 4. Battle-level fields

- **`weather` is a turn stamp refreshed every turn.** `[src]` `-weather` stores
  `{Weather: self.turn}` and reads only `event[2]` (`abstract_battle.py:754-761`);
  `[tree]` Showdown emits `-weather|X|[upkeep]` every residual phase
  (`showdown/data/conditions.ts:507, 539, 585, 621, 656, 681`), so `turn − stamp` is
  always 0–1 and **carries no duration information**, and `[from] ability:` is
  dropped so permanent ability weather looks like a 5-turn move. Wang's fork
  handled both (`prior_work/wang_fork_diffs.md:3563-3573`, #9) — ABSENT in 0.15.0.
  Members reachable in gen 4: SANDSTORM, RAINDANCE, SUNNYDAY, HAIL.
- **`fields`** `[src]` stores the genuine start turn (`abstract_battle.py:437-448`);
  gen4-reachable: TRICK_ROOM, GRAVITY. Mud/Water Sport are per-mon volatiles in
  gen 4 but modelled as fields — the one generation-wrong spot (and not in the pool).
- **`side_conditions` / `opponent_side_conditions`** `[src]`
  (`abstract_battle.py:1238-1247`): SPIKES and TOXIC_SPIKES are **layer counts**
  (`STACKABLE_CONDITIONS`, `side_condition.py:95`); everything else, including
  STEALTH_ROCK, is a **turn stamp**, so remaining turns need the duration from
  `mechanics_delta.md` §8. All nine gen4 side conditions map; `side_end` pops
  silently.
- **`turn`, `force_switch`, `trapped` / `maybe_trapped`** `[src]` `battle.py:85-140,
  224-248`; when `trapped` is true no `available_switches` are populated.
- **Opponent team** `[src]` grows lazily from `|switch|`/`|drag|`
  (`abstract_battle.py:192-330`); with no preview it is both the reveal set and
  the identity set — the gen1 "pad to 6 unknown" convention carries over.
  Opponent HP arrives as `x/100` (HP Percentage Mod).
- **`_replay_data` is populated unconditionally** `[src]`
  (`abstract_battle.py:565-566`): the entire raw protocol log is in memory and is
  the only route to `-crit`, `-miss`, `-supereffective`/`-resisted`/`-immune`,
  `-fail`, `-hitcount`, and every `[from]` string poke-env drops (Encored move,
  weather setter). `Pokemon.last_move` is a single flag; there is no move history.

## 5. Static data and calculators

- **`gen4moves.json`** `[src]`: 486 entries (gen 1: 168), `num` 1..467 plus three
  synthetic negatives; **category is per move** (`Move.category`'s by-type branch is
  gated `gen <= 3`, `poke_env/battle/move.py:209-215`): 192 Physical / 124 Special
  / 170 Status. `priority` spans −7..+5 over 12 values. `expected_hits` uses the
  gen5+ 2–5-hit distribution (3.1667; gen 4's is 3.0 `[lit]`). `thawsTarget` is on
  zero gen4 moves. Curse is type `???` → `THREE_QUESTION_MARKS`, multiplier 1.
  `Move.target`, `.weather`, `.status` are raising lookups; all gen4 values are
  members. **`Return`'s base power is 0** (the digit-stripping override applies
  only to Hidden Power, `move.py:104-112, 561-576`); nine pool moves have BP 0
  while dealing damage (counter, grassknot, lowkick, metalburst, mirrorcoat,
  nightshade, return, seismictoss, superfang); Return is on 39 species.
  **All 17 `hiddenpower*` entries share `num` 237**, so a `num`-keyed move id
  cannot separate HP Fire from HP Ice, although `move.id` keeps the typed id and
  `move.type`/`base_power` (70) are right; the dict key is the collapsed
  `"hiddenpower"`.
- **`gen4pokedex.json`** `[src]`+`[tree]`: no hidden-ability slot; cosmetic formes
  (`burmysandy`, `gastrodoneast`, …) are repaired by `load_pokedex`; **`num` is not
  injective over formes** — 295 pool species map to 267 distinct nums (Arceus ×17
  → 493, Rotom ×6, Deoxys ×4, Wormadam ×3, Giratina ×2, Shaymin ×2), and Arceus
  formes differ in type. Key species on `Pokemon.species` (the forme id).
- **`gen4typechart.json`** `[src]`: **18 keys including `fairy`**
  (`isNonstandard: 'Future'`, unfiltered by `load_type_chart`,
  `gen_data.py:73-109`); the Fairy column is internally inconsistent. Harmless as
  long as the spec lists its 17 types explicitly. `damage_multiplier` knows nothing
  about abilities; `is_grounded` is the only ability-aware helper and it treats a
  hidden possible Levitate as Levitate (`abstract_battle.py:548-563`).
- **No ability table, no item table** `[src]`: `poke_env/data/static/` holds only
  moves/pokedex/typechart/learnset/natures. `mon.ability` and `mon.item` are bare
  id strings; **our spec must build and freeze both vocabularies** (101 abilities,
  40 items from the pool — `mechanics_delta.md` §11).
- **No gen4 damage calculator** `[src]`: `poke_env/calc/` exports only the gen-9
  pair; `damage_calc_gen1_2.py` branches on gen 1/2 throughout;
  `damage_calc_gen9.py` has no gen guard and would apply gen-9 crit (1.5× vs gen
  4's 2×), screens, ordering and the 18-type chart; both assert numeric stats on
  both sides, which the opponent never has (§3.3).

## 6. Consolidated gaps and bugs for gen 4

| # | gap | where | effect on a gen4 run | fix class | status |
|---|---|---|---|---|---|
| G1 | `maybe_trapped` ignored by mask and baselines | `singles_env.py:233-240`; `battle.py:275-282`; `baselines.py:354` | rejected switches, re-picks, possible retry loop | encode a bit; leave the mask permissive; count rejections | `[src]` `[live]` rate |
| G2 | weather stamp refreshed every `[upkeep]`; ability weather not distinguished | `abstract_battle.py:754-761` | no duration feature; permanent sand reads as fresh | track start turn and `[from] ability` from `_replay_data` in our wrapper | `[src]` `[tree]` |
| G3 | sleep counter double-bumps on Sleep Talk | `abstract_battle.py:726-741`; `pokemon.py:482-483` | 2× sleep clock on Rest/Sleep Talk sets | suppress the bump on the `overridden_move` call | `[src]`, `[live]` parse test |
| G4 | no `original_item`; consumed / knocked-off / none collapse | `pokemon.py:405-410, 1108-1112` | item inference thrown away on use | wrapper-side item memory + `is_consumed` flag | `[src]` |
| G5 | Encore / Disable move name dropped | `abstract_battle.py` `-start` branch | cannot see which move is locked | read from `_replay_data` | `[src]` |
| G6 | Flash Fire cleared after one use | `pokemon.py:498-503` | Fire boost feature wrong after first use (6 species) | post-process | `[src]` `[tree]` |
| G7 | `Return` BP 0; nine BP-0 damaging moves | `move.py:104-112` | a 102-BP STAB move reads as powerless on 39 species | per-move override table | `[src]` |
| G8 | Hidden Power `num` 237 for all types | `gen4moves.json` | num-keyed ids alias 8 pool variants | key move ids on the typed `move.id` string | `[src]` |
| G9 | `num` not injective over formes | `gen4pokedex.json` | Arceus formes share an embedding row | key species on the forme id | `[src]` `[tree]` |
| G10 | 18-key chart with Fairy | `gen_data.py:73-109` | a derived type tuple silently gains a dead slot | enumerate 17 types | `[src]` |
| G11 | no opponent stats, no ability/item tables, no gen4 damage calc | §5 | encoder must supply them | closed-form stats; frozen vocabs; own damage proxy | `[src]` `[tree]` |
| G12 | `-item` 6-field `ValueError` on an unknown `[from]` cause | `abstract_battle.py:1148-1200` | crash path; gen4-legal causes (Frisk, Thief, Covet) are handled | none expected | `[src]` `[live]` grep of logs |
| G13 | `expected_hits` is the gen5+ distribution | `move.py:321-342` | SH's move score ~5.6 % high on 17 multi-hit moves | none (SH is the anchor as shipped) | `[src]` `[lit]` |
| G14 | `base_format` `@@@` custom-rule strings never match | `player.py:191` | only if a modded format is ever used (e.g. determinized search) | wrapper | `[src]` |
| G15 | no `/offertie` (`TieBattleOrder`) | whole package | stall wars end only at the turn cap or the timer | design question | `[src]` |

**Wang's poke-env fork vs 0.15.0, tallied** `[src]` (30 distinct changes over 36
commits): 15 UPSTREAMED (Max PP, Sleep Talk PP double-deduction, Curse `???`,
`opp_remaining_mons`, timers, gymnasium, request ordering by redesign,
`inactiveoff`, Trace base ability, `[from]lockedmove` trimming, `forceSwitch`
list, `_ACTION_COUNTER_EFFECTS`, `sentchoice`, websocket URL, `uhtml`); 1 PARTIAL
(`_orig_ability` yes, `_orig_item` no); 9 ABSENT, of which **four are gen4-live
and gen1-dead** (G2, G3, G1 ×2 for SH and the random helper) and five are
lower-stakes (`base_format`, `TieBattleOrder`, `Move._revealed`, a switch-dedup
that 0.15.0 makes unnecessary by design, a stricter `-weather` else-branch); 5
N/A. The index's line "encoder-relevant ones upstreamed by 0.15.0"
(`prior_work/README.md`) is therefore amended: four encoder-relevant fixes are
**not** upstreamed. The SB3 fork is instrumentation only — Wang's PPO is stock
SB3 PPO (`prior_work/wang_fork_diffs.md:3993-4213`).

## 7. `SimpleHeuristicsPlayer` in gen 4 (summary; the anchor question is `anchors_and_eval.md`)

`[src]` `poke_env/player/baselines.py:133-360`. Defects that get worse in gen 4:
(a) `ENTRY_HAZARDS` contains the typo `"stealhrock"` (`:134-139`), so SH never
recognises Stealth Rock — moot in this pool, where no set has it; (b) the
setup-move branch tests `move.target == "self"`, a `Target` enum against a
string, always `False` — **dead in every generation** (`:317`); (c)
`_stat_estimation` is `((2*base + 31) + 5) * boost` with no level and no EVs
(`:249-256`), and it double-counts a +1 boost; (d) `expected_hits` is gen5+
(G13); (e) Return scores 0 (G7) and Explosion scores at BP 250 with no
self-KO penalty; (f) no `maybe_trapped` guard (G1). SH is blind to items,
abilities, weather, hazard chip, priority and every status move; in gen 1 four of
those six do not exist, in gen 4 all six do. The hazard-setting branch is inert
in gen 1 and partially live in gen 4 (Spikes, Toxic Spikes); hazard removal
(Rapid Spin) is live. **Mechanism argument only — nothing is measured here.**

## 8. What needs live verification (all barred until post-ladder)

| check | how |
|---|---|
| `maybe_trapped` rejection rate and whether the re-query loops | a few hundred gen4 self-play games with counters on the flag and on `[Unavailable choice]` |
| Sleep Talk double-bump | replay a recorded two-line Sleep Talk sequence through `Battle.parse_message`; assert +1 |
| force-switch request omits `active` | one captured gen4 request |
| unknown-string histogram | a `logging.Handler` on `"poke-env"` at WARNING over ~500 battles: `Effect`/`SideCondition`/`Weather`/`Field` UNKNOWN counts |
| `strict_battle_tracking=True` survives gen 4 | 20 self-play battles; count assertion failures (PP under an unrevealed Pressure Absol/Aerodactyl is the suspect) |
| every protocol claim in §3–4 | one local gen4randombattle with `--no-security`, diffing observed `-ability`/`-activate`/`-enditem`/`-status`/`-weather`/`-sidestart`/`-singleturn` lines against the tables here and in `mechanics_delta.md` §11 |
| `-item` 6-field causes | grep gen4 logs for 4-payload `|-item|` lines |

## 9. gen1 encoder assumptions this breaks (input to `encoder_requirements.md`)

`[src]`+`[tree]` against `rl/envs/encoder_spec.py` (main@2738025): `types` 15 → 17,
enumerated, never derived from the chart; `base_stat_keys` gains `spd`;
`special_move_ids` should be `{struggle, recharge}` (`fight` is gen-1-only,
`showdown/sim/pokemon.ts:1105-1112`; `recharge` is near-extinct in the pool — one
Giga Impact set — so `_move_slots_aliased` will essentially never fire);
`species_num_range` (1,151) → (1,493) but keyed on the forme id; `move_num_range`
(1,165) → (1,467) with Hidden Power keyed on `move.id`; `volatiles` grows and
`REFLECT` moves to a side block, `PARTIALLY_TRAPPED` becomes six per-move members;
new blocks for items (three-state + consumed), abilities (known / two-candidate /
prior), weather (presence + our own start turn), fields, two side-condition
blocks (layers vs stamps); level as a live numeric input; `status_counter`
semantics change; `maybe_trapped` and `protect_counter` become decision-relevant;
the action head does **not** change; `move.category` is now live data.

## 10. Maintainer rulings wanted (collected in `open_questions.md`)

1. **Patch poke-env, or wrap it?** The four gen4-live ABSENTs (G1–G4) and the
   smaller G5–G7 can all be handled by a subclass/wrapper inside `rl/envs/`
   reading `_replay_data`, keeping the exact pin in `pyproject.toml`.
   Recommendation: wrap, never fork. Losing argument: a fork is where Wang put
   36 fixes and upstream has since absorbed most of them; a vendored patch set
   is the documented precedent for foul-play.
2. **`maybe_trapped`: mask, encode, or neither.** Recommendation: encode a bit,
   keep the mask permissive, count rejections as a disclosed metric. Losing
   argument: masking is the only option that keeps the mask a true legality
   mask, which is the harness contract; the retry loop lives in the same
   coroutine as the orphaned-room deadlock.
3. **Weather duration:** presence-only, wrapper-tracked start turn, or a patched
   `-weather` branch. Recommendation: wrapper-tracked start turn + an
   "indefinite" flag from `[from] ability`.
4. **Species key:** forme id (295-row, pool-sized) vs dex `num` (dense, gen-
   independent, warm-startable). Recommendation: forme id; Arceus formes differ
   in type.
5. **Opponent stats:** parallel table in the encoder vs mutating
   `Pokemon.stats`. Recommendation: parallel table (the closed form has two
   set-dependent ambiguities that should stay probabilistic).
6. **A gen4 damage feature in v1?** Recommendation: no — type effectiveness ×
   base power × category × the stat ratio, as SH approximates; a real calc is a
   later lever. Losing argument: gen4 damage is far more item/ability-modified
   than gen1's, so the proxy may be materially worse.
7. **`strict_battle_tracking=True`** for a short bring-up fleet only.
8. **`/offertie`** for gen4 collection: worth adding, and does a tie corrupt the
   reward (ties are non-wins)?
9. **Patch SH for gen 4?** Recommendation: no; disclose its defects wherever a
   gen4 vs-SH number is quoted (→ `anchors_and_eval.md`).

## 11. Sources and what was not read

- Not read: `poke_env/battle/double_battle.py`, `z_crystal.py`,
  `poke_env/teambuilder/*`, `poke_env/environment/doubles_env.py`,
  `poke_env/concurrency.py`, `ps_client/{account,server}_configuration.py`
  (beyond the URL), `damage_calc_gen9.py` beyond its preamble and gen-guard grep.
- `[lit]` in this doc: the gen4 2–5-hit distribution (3/8, 3/8, 1/8, 1/8) behind
  G13; the gen4 crit multiplier as quoted for the gen9 calculator comparison
  (`mechanics_delta.md` §2 verifies it as 2× from the sim).
- The ps-ppo / Metamon observation-design comparison and the literature
  cross-check were not produced this cycle (`open_questions.md` deferrals
  D2, D4); nothing here depends on them.

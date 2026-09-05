# poke-env 0.15.0 env / action / player layer for `gen4randombattle`

**Agent:** pokeenv-env-layer surveyor (gen-4 design sweep, stage: research)
**Date:** 2026-09-04
**Scope:** the pinned poke-env environment/action/player layer, read against gen 4. Where a
claim needed the game as we actually run it, it is checked against the vendored Showdown
0.11.11 sim, not against memory.

## Status legend (every finding carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP `main@2738025`: `rl/`,
  `scripts/`, `configs/`, `tests/`, `docs/`) or the vendored `showdown/` `data/` / `sim/`,
  i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk (installed
  poke-env 0.15.0 source, ps-ppo clone, prior-work index).
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work
  index without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm it; BARRED until
  the live ladder run and any later fleet complete. Each such item names the exact check.

## Sources read (path — lines)

Installed poke-env 0.15.0 at
`PE = /opt/anaconda3/envs/pokemon-showdown-rl/lib/python3.13/site-packages/poke_env`:

| file | lines read |
|---|---|
| `PE/environment/singles_env.py` | 1–304 (whole file) |
| `PE/environment/env.py` | 1–815 (whole file) |
| `PE/environment/single_agent_wrapper.py` | 1–100 (whole file) |
| `PE/player/player.py` | 40–80, 120–360, 440–500, 500–600, 596–758 |
| `PE/player/battle_order.py` | 1–110 (whole file) |
| `PE/player/baselines.py` | 1–443 (whole file, as instructed) |
| `PE/player/utils.py` | 1–177 (whole file) |
| `PE/ps_client/ps_client.py` | 116–135, 300–340 (+ full grep index) |
| `PE/data/gen_data.py` | 1–124 (whole file) |
| `PE/battle/battle.py` | 55–180, 272–303 |
| `PE/battle/abstract_battle.py` | 582–680, 1279–1320, 1673–1700 (+ grep index) |
| `PE/battle/pokemon.py` | 165–180, 716–760, 804–900, 1159–1175 |
| `PE/battle/move.py` | 1–70, 80–140, 205–216, 290–320, 322–341, 343–384, 484–504, 561–586, 665–712, 953–1013 |
| `PE/battle/target.py` | 1–60 (whole file) |
| `PE/battle/pokemon_type.py` | 43–83 |
| `PE/battle/side_condition.py` | grep index (lines 24–35, 95, 108–119) |
| `PE/data/static/{moves,pokedex,typechart}/gen*.json` | directory listing + programmatic probes |

Vendored Showdown 0.11.11 at
`SD = /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown`:
`sim/pokemon.ts` 350–365, 960–1050, 1100–1150, 1159–1194, 1310–1325;
`sim/side.ts` 470–520, 527–537, 555–610, 975–1005;
`config/formats.ts` 4239–4275;
`data/abilities.ts` 192–206, 2502–2516, 4142–4156;
`data/random-battles/gen4/sets.json` (parsed, 295 species) and
`data/random-battles/gen4/teams.ts` 14–30, 140–160, 270–280, 340–360;
`data/random-battles/gen1/data.json` (parsed, 146 species).

Repo snapshot `SNAP = .../scratchpad/main_snapshot` (`main@2738025`):
`rl/envs/encoder_spec.py` 1–60, 80–150, 255–290; `rl/envs/showdown.py` 238–290, 385–420,
840–880, 1195–1240; `rl/envs/showdown_async.py` (grep index only);
`docs/prior_work/README.md` 480–505; `/Users/nickgreenquist/Documents/Projects/ps-ppo/worker.py` 40–80.

Programmatic probes (all offline, `nice -n 19`, no player/env constructed, no network):
`GenData` / `Move` / `SinglesEnv.get_action_space_size` reads, and `json` parses of the two
random-battle set files. No server was contacted; port 8000 untouched.

---

## 1. The action space for gen 4

### 1.1 Size is 10, and the derivation is a plain gen switch

**tree-verified / source-verified.** `SinglesEnv.get_action_space_size(4) == 10`.
`PE/environment/singles_env.py:290-304`:

```python
    @staticmethod
    def get_action_space_size(gen: int) -> int:
        num_switches = 6
        num_moves = 4
        if gen == 6:
            num_gimmicks = 1
        elif gen == 7:
            num_gimmicks = 2
        elif gen == 8:
            num_gimmicks = 3
        elif gen == 9:
            num_gimmicks = 4
        else:
            num_gimmicks = 0
        return num_switches + num_moves * (num_gimmicks + 1)
```

Probed directly: `[SinglesEnv.get_action_space_size(g) for g in range(1,10)]` →
`[10, 10, 10, 10, 10, 14, 18, 22, 26]`. Gen 4 falls in the `else` branch (0 gimmicks), so it
gets **exactly the gen-1 action space**: `Discrete(10)`.

The env wires this from the format string, not from a constructor argument
(`singles_env.py:70-74`):

```python
        gen = GenData.from_format(battle_format).gen
        self.action_spaces: dict[str, Space[Any]] = {
            agent: Discrete(SinglesEnv.get_action_space_size(gen))
            for agent in self.possible_agents
        }
```

and `GenData.from_format` is `gen = int(format[3])` (`PE/data/gen_data.py:121-124`), so
`"gen4randombattle"` → gen 4.

**Cross-reference for `encoder_requirements.md`:** the LANDED seam already knows this.
`SNAP/rl/envs/encoder_spec.py:277-281` only appends "an action head for N actions" to its
refusal list `if n_actions != GEN1.n_actions` — for gen 4 that comparison is `10 != 10`, so
**the gen-4 blocker list does NOT include the action head**. The pointer head, the mask
width, `OPP_CHOICE_DIM`, and the 6/4 layout arithmetic all carry over unchanged. The gen-4
encoder work is a *feature* problem, not an action-space problem.

### 1.2 Exact index layout

**source-verified.** From the docstring at `singles_env.py:83-91` and the code beneath it:

| index | meaning (gen 4) |
|---|---|
| `-2` | `DefaultBattleOrder()` → `/choose default` |
| `-1` | `ForfeitBattleOrder()` → `/forfeit` |
| `0..5` | switch to `list(battle.team.values())[action]` |
| `6..9` | use move `mvs[(action - 6) % 4]` |
| `10..13` | move + mega — **unreachable in gen 4** (outside `Discrete(10)`) |
| `14..17` | move + z-move — unreachable |
| `18..21` | move + dynamax — unreachable |
| `22..25` | move + terastallize — unreachable |

Note the *negative* codes are not in the `Discrete(10)` space; they are produced by
`order_to_action` (lines 182–185) and consumed by `action_to_order` (lines 109–112), i.e.
they cross the seam only for default/forfeit, never as a policy output.

### 1.3 Switch slot ordering

**source-verified.** `singles_env.py:113-114`:

```python
            elif action < 6:
                order = Player.create_order(list(battle.team.values())[action])
```

`battle.team` is a `Dict[str, Pokemon]` keyed by request ident (`"p1: Nickname"`), populated
in insertion order by `AbstractBattle._update_team_from_request` iterating `side["pokemon"]`
(`PE/battle/abstract_battle.py:1287-1319`). The server emits `side.pokemon` in slot order, so
**switch index i == the server's team slot i**, fixed at the first `|request|` and stable for
the battle. Gen 4 randbats has no team preview (§2.1), so slot 0 is always the lead. This is
identical to gen 1; the encoder's team-block ordering assumption survives verbatim.

The inverse (`order_to_action`, `singles_env.py:195-198`) matches on **base species**, not on
ident:

```python
                if isinstance(order.order, Pokemon):
                    action = [p.base_species for p in battle.team.values()].index(
                        order.order.base_species
                    )
```

**Risk, low:** two mons on one team sharing a `base_species` (e.g. two Rotom formes, two
Deoxys formes) would collide and the index would silently point at the first. Gen 4 randbats
is species-clause-bound so this cannot arise there; it is a caveat only if we ever run gen-4
non-random formats. Not a gen-4 blocker.

### 1.4 Move index and the `mvs` re-basing rule

**source-verified.** `singles_env.py:122-143` (and mirrored at 201–209 in `order_to_action`):

```python
                avail_ids = [m.id for m in battle.available_moves]
                known_moves = list(battle.active_pokemon.moves.values())[:4]
                known_ids = [m.id for m in known_moves]
                mvs = (
                    battle.available_moves
                    if len(avail_ids) == 1 and avail_ids[0] not in known_ids
                    else known_moves
                )
```

So **move action `6+j` normally means "the mon's own move slot j"**, and only re-bases onto
`available_moves` when there is exactly one legal move *and it is not one of the mon's known
four*. In gen 4 the only inhabitants of that re-basing case are `struggle` and `recharge`
(see §4.2 — `fight` is gen-1-only). Choice-lock, Encore, Taunt, Disable, Torment and the
locking moves (Outrage / Petal Dance / Thrash / Rollout / Uproar) all leave the single legal
move *inside* the known four, so no aliasing occurs and the slot index stays honest.

Then, for gen 4, the gimmick flags are all provably `False`:

```python
                order = Player.create_order(
                    mvs[(action - 6) % 4],
                    mega=10 <= action.item() < 14,
                    z_move=14 <= action.item() < 18,
                    dynamax=18 <= action.item() < 22,
                    terastallize=22 <= action.item() < 26,
                )
```

because `action <= 9`. And in `order_to_action` (`singles_env.py:210-220`) `gimmick = 0`, so
`action = 6 + move_index`. The round trip is the identity for gen 4.

Strictness: `action_to_order` line 144 cross-checks the produced order against
`battle.valid_orders` and raises `ValueError` if absent; `strict=False` degrades to
`Player.choose_random_singles_move` (lines 151–157). Our repo intercepts that raise with
`_recover_mask_desync` (`SNAP/rl/envs/showdown.py:849-867`) — that interception carries over
to gen 4 unchanged and is *more* load-bearing there (see §1.6).

### 1.5 How the action mask is built

**source-verified.** `singles_env.py:232-288`, verbatim for the parts that matter in gen 4:

```python
    @staticmethod
    def get_action_mask(battle: Battle) -> list[int]:
        switch_space = [
            i
            for i, pokemon in enumerate(battle.team.values())
            if not battle.trapped
            and pokemon.base_species
            in [p.base_species for p in battle.available_switches]
        ]
        if battle._wait:
            actions = [0]
        elif battle.active_pokemon is None:
            actions = switch_space
        else:
            known_moves = list(battle.active_pokemon.moves.values())[:4]
            move_space = [
                i + 6
                for i, move in enumerate(known_moves)
                if move.id in [m.id for m in battle.available_moves]
            ]
            if (
                not move_space
                and len(battle.available_moves) == 1
                and battle.available_moves[0].id not in SPECIAL_MOVES
            ):
                move_space = [6]
            ...
            if (
                not move_space
                and len(battle.available_moves) == 1
                and battle.available_moves[0].id in SPECIAL_MOVES
            ):
                move_space = [6]
            actions = (
                switch_space + move_space + mega_space + zmove_space
                + dynamax_space + tera_space
            )
        action_mask = [
            int(i in actions)
            for i in range(SinglesEnv.get_action_space_size(battle.gen))
        ]
        return action_mask
```

For gen 4 the four gimmick lists are empty: `battle.can_mega_evolve` / `can_z_move` /
`can_dynamax` / `can_tera` are set only from `canMegaEvo` / `canZMove` / `canDynamax` /
`canTerastallize` in the request (`PE/battle/battle.py:122-129`), and the gen-4 sim never
emits any of them (`SD/sim/pokemon.ts:1143-1194` gates mega/Z on `!lockedMove` and gen-9 tera
on `battle.gen === 9`). So the mask is exactly `switch_space + move_space`, width 10.

How each situation shows up:

| condition | mask effect | status |
|---|---|---|
| **disabled move** (PP 0, Disable, Taunt, Torment, Encore, Imprison, Choice lock) | server marks `disabled: true` in `request.active[0].moves[]`; `Pokemon.available_moves_from_request` filters it out (`PE/battle/pokemon.py:809-811`); the slot's index drops out of `move_space` | source-verified + tree-verified (`SD/sim/pokemon.ts:1022-1045`) |
| **`force_switch`** | on a switch request PS omits the `"active"` key, so `Battle.parse_request` never populates `_available_moves` (`PE/battle/battle.py:110-121`), `move_space` is empty, `actions == switch_space` | source-verified; the `"active"`-omission half is **needs-live-verification** (see §5) |
| **`trapped`** | `battle.trapped` truthy ⇒ `switch_space` is `[]` *and* `available_switches` is `[]` (`PE/battle/battle.py:133-140`), so only moves remain | source-verified |
| **`must_recharge`** | server sends a single `{move: "Recharge", id: "recharge"}` (`SD/sim/pokemon.ts:973-978`); `recharge ∈ SPECIAL_MOVES`, is never stored on the mon (`Move.should_be_stored` returns False for `SPECIAL_MOVES`, `PE/battle/move.py:83-85`), so `move_space` is empty and the second guard sets `move_space = [6]`; `action_to_order` then re-bases onto `available_moves` and `SingleBattleOrder.message` special-cases it to `/choose move 1` (`PE/player/battle_order.py:48-49`) | source-verified + tree-verified |
| **Struggle** | same path: `{move: "Struggle", id: "struggle"}` when `getMoves()` returns empty (`SD/sim/pokemon.ts:1109-1112`); mask index 6, message `/choose move struggle` | source-verified + tree-verified |
| **`battle._wait`** | `actions = [0]` — index 0 is marked legal *even though it is a switch index*, while `valid_orders` returns `[DefaultBattleOrder()]` (`PE/battle/battle.py:277-278`). Converting action 0 under wait therefore fails the strict check. Not gen-specific; our `_recover_mask_desync` covers it | source-verified |

### 1.6 The one gen-4-only mask hazard: `maybeTrapped` is parsed and then ignored

**source-verified + tree-verified. This is the single most important action-layer delta.**

`Battle.parse_request` reads `maybeTrapped` (`PE/battle/battle.py:130-131`) and exposes it as
`battle.maybe_trapped` (lines 242–248) — but a grep of the whole installed package shows
**nothing consumes it in singles**: `get_action_mask` reads only `battle.trapped`,
`valid_orders` reads only `battle.trapped`, and `SimpleHeuristicsPlayer` reads neither. The
only consumers are `DoubleBattle` bookkeeping.

`maybeTrapped` is set by exactly three abilities — Arena Trap, Magnet Pull, Shadow Tag
(`SD/data/abilities.ts:196/203`, `2506/2512`, `4146/4152`, each `onFoeMaybeTrapPokemon`) —
**none of which exists in gen 1**, where there are no abilities at all. In gen 4 they do.

The consequence is wire-visible. `SD/sim/side.ts:984-1000`:

```ts
		if (this.requestState === 'move') {
			if (pokemon.trapped) {
				return this.emitChoiceError(`Can't switch: The active Pokémon is trapped`, { pokemon, update: req => {
					let updated = false;
					if (req.maybeTrapped) { delete req.maybeTrapped; updated = true; }
					if (!req.trapped)     { req.trapped = true;     updated = true; }
					return updated;
				} });
			} else if (pokemon.maybeTrapped) {
				this.choice.cantUndo = true;
			}
		}
```

and `emitChoiceError` (`SD/sim/side.ts:527-537`) sends
`|error|[Unavailable choice] ...` **and re-emits the corrected request** when it updated
anything. poke-env's handler treats `[Unavailable choice]` by setting `_trying_again` and
waiting for the new request (`PE/player/player.py:318-325`).

So in gen 4, a mask that advertises a switch against an unrevealed Arena Trap / Shadow Tag /
Magnet Pull will occasionally trigger a rejected choice, an extra `|request|`, and a re-pick.
This never happens in gen 1. **Whether it happens at material rates in `gen4randombattle`
depends on whether the pool actually carries those abilities** — Dugtrio / Magneton /
Magnezone / Wobbuffet are the classic carriers; confirming their presence and ability rolls
belongs to the pool survey, and I flag it there rather than asserting it here.

**needs-live-verification (post-ladder):** run a few hundred `gen4randombattle` self-play
games with a counter on `battle.maybe_trapped and not battle.trapped` at decision time, and a
counter on `|error|[Unavailable choice]` lines in the seat logs. If the rate is non-trivial,
the gen-4 mask should be `switch_space = [] if (battle.trapped or battle.maybe_trapped)` —
which is *conservative but lossy* (it forbids legal switches) — or, better, left as-is with
`_recover_mask_desync` doing the work and the event counted as a disclosed metric.

`maybeDisabled` and `maybeLocked` are emitted by the sim (`SD/sim/pokemon.ts:1126-1133`) and
**parsed nowhere in poke-env** (grep across the package: zero hits). In gen 4 the only source
of `maybeDisabled` is Imprison; low prevalence, but it means poke-env can advertise a move
the server may reject with `[Unavailable choice]` too.

---

## 2. Battle start, request parsing, wrapper hooks, and the two knobs

### 2.1 Gen 4 random battle has no team preview

**tree-verified.** `SD/config/formats.ts:4239-4244`:

```ts
		name: "[Gen 4] Random Battle",
		mod: 'gen4',
		team: 'random',
		bestOfDefault: true,
		ruleset: ['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod'],
```

No `Team Preview` in the ruleset. (Gen 1's entry is `ruleset: ['Standard']`,
`formats.ts:4260-4264`.) So `request["teamPreview"]` is never true, `battle.teampreview` stays
`False` (`PE/battle/battle.py:94-99`), and:

- `Player._handle_battle_request`'s `elif battle.teampreview:` branch (`player.py:341-345`) is
  dead — every request goes straight to `choose_move`.
- `SingleAgentWrapper.step`'s `raise NotImplementedError("Teampreview is only supported for
  VGC formats in SingleAgentWrapper.")` (`single_agent_wrapper.py:52-55`) **cannot fire**.
- `_EnvPlayer._teampreview` / `random_teampreview` are never called.

This is the same shape as gen 1. **Nothing in the wrapper or env needs a team-preview
change for gen 4.** (Cross-reference for `open_questions.md`: if the chapter ever moves to
gen 4 OU or another team-preview format, `SingleAgentWrapper` refuses outright and would need
work; `choose_on_teampreview` only ever does anything for VGC doubles.)

### 2.2 The team-less format path

**source-verified.** `Player.get_next_team()` returns `None` when `self._team` is `None`
(`player.py:705-709`), and `PSClient.set_team(None)` sends `/utm null`
(`ps_client.py:328-332`) before every `/challenge` (line 130) or `/search` (line 305). For
`gen4randombattle` we never pass `team=`, so the handshake is identical to gen 1. The
`accept_open_team_sheet` machinery is gated on `"vgc" in self.format`
(`player.py:233-241`) and is inert.

### 2.3 Battle creation, `/timer on`, and `max_concurrent_battles`

**source-verified.** `Player._create_battle` (`player.py:182-243`) builds a `Battle` with
`gen = GenData.from_format(self._format).gen` (line 198) — 4 for us — then:

```python
                await self._battle_count_queue.put(None)
                ...
                if self._start_timer_on_battle_start:
                    await self.ps_client.send_message("/timer on", battle.battle_tag)
```

(lines 221, 230–231). This is the landmine's mechanism, and it is **generation-independent**:
the knob defaults to `False` in all three places that carry it —
`PokeEnv.__init__` (`env.py:175`), `SinglesEnv.__init__` (`singles_env.py:39`), and
`Player.__init__` (`player.py:66`) — and is forwarded to both seats verbatim
(`env.py:277`, `env.py:296`, and again in `__setstate__` at `env.py:359`/`379`). Our tree sets
it `True` at `SNAP/rl/envs/showdown.py:1194` (default arg) and
`SNAP/rl/envs/showdown_async.py:262`, with a hard guard forbidding overrides at
`showdown_async.py:270-272`. **Nothing about gen 4 changes this; the rule carries over
verbatim, and the landmine's `/timer on` requirement is unchanged.**

The `max_concurrent_battles=1` **literals** in `PokeEnv` are at `env.py:273` and `env.py:292`
(construction) and `env.py:355` and `env.py:375` (`__setstate__`) — four sites, exactly as
`SNAP/rl/envs/showdown.py:1207-1208` records. `Player`'s own default is `1`
(`player.py:62`); it becomes the maxsize of `_battle_count_queue`
(`player.py:134-136`), which is what blocks forever on an orphaned room. Gen 4 does not
change any of this, and `showdown_async.py:258` remains the only place we widen it.

### 2.4 Request parsing

**source-verified.** `Battle.parse_request` (`PE/battle/battle.py:61-140`) is fully
gen-agnostic in structure. What it reads, and what gen 4 actually populates:

| request key | gen 1 | gen 4 | note |
|---|---|---|---|
| `wait` | yes | yes | → `battle._wait` |
| `forceSwitch[0]` | yes | yes | line 90 |
| `teamPreview` | no | no | §2.1 |
| `active[0].trapped` | yes (partial trap) | yes (+ Mean Look, Block, Ingrain, ability trapping) | line 113 |
| `active[0].maybeTrapped` | never from abilities | **yes** (Arena Trap / Magnet Pull / Shadow Tag) | line 130; **ignored downstream**, §1.6 |
| `active[0].canMegaEvo/canZMove/canDynamax/canTerastallize` | no | no | lines 122–129, all stay `False` |
| `side.pokemon[].stats` | yes | yes | `SD/sim/pokemon.ts:1165-1171`, always emitted |
| `side.pokemon[].baseAbility` | `""` | **real ability** | `SD/sim/pokemon.ts:1182` |
| `side.pokemon[].ability` (live) | no | **no** — `if (this.battle.gen > 6)` (`SD/sim/pokemon.ts:1186`) | so gen 4 exposes only `baseAbility`; `Pokemon.update_from_request` (`PE/battle/pokemon.py:719-725`) sets `ability` from it and never sets `temporary_ability` |
| `side.pokemon[].item` | `""` | **real item** | `SD/sim/pokemon.ts:1183` |
| `side.pokemon[].reviving` / `commanding` / `teraType` | no | no | gen-9-gated at `SD/sim/pokemon.ts:1187-1193` |

**Gen-4 consequence:** the request *does* hand us our own items and abilities for all six
mons. That is new information the gen-1 encoder has no block for — see §6.

### 2.5 Wrapper obs / reward hooks

**source-verified.** `PokeEnv.__setattr__` (`env.py:317-333`) wraps whatever `observation_spaces`
we assign into `spaces.Dict({"observation": raw, "action_mask": Box(0,1,(flatdim(action_space),), int64)})`.
For gen 4 that `Box` is shape `(10,)` — same as gen 1. `PokeEnv.step` (`env.py:400-467`) emits
per-agent `{"observation": self.embed_battle(b), "action_mask": np.array(self.get_action_mask(b))}`
(lines 447–456), `calc_reward` per agent (457–460), and `calc_term_trunc` (461–464).
`calc_term_trunc` (`env.py:772-788`) marks `terminated` when exactly one side is wiped and
`truncated` otherwise — using `battle.team_size` (`PE/battle/abstract_battle.py:1676-1686`),
which for gen 4 randbats is 6 with no preview. `reward_computing_helper` (`env.py:678-760`)
is generation-blind: HP fractions, fainted counts, `status is not None`, and win/loss.
Nothing here needs a gen-4 change.

`SingleAgentWrapper.step` (`single_agent_wrapper.py:22-84`) handles the opponent seat: on
`battle2.wait` it converts `DefaultBattleOrder()` (lines 35–42), otherwise it calls
`self.opponent.choose_move(self.env.battle2)` **synchronously, inside our step**, and converts
the order with `order_to_action` (43–51). This is the hook D25's opponent-action label rides
(`SNAP/rl/envs/showdown.py:400-420`), and it is unchanged for gen 4 — with the one caveat
that in gen 4 `order_to_action` must survive an opponent that emits an order the mask did not
advertise (§1.6). Our `order_to_action` override (`SNAP/rl/envs/showdown.py:856-867`) already
handles this by construction.

---

## 3. `SimpleHeuristicsPlayer`, end to end

Read in full at `PE/player/baselines.py:133-368` (plus `PseudoBattle` 105–131 and the doubles
tail 370–443, both irrelevant to singles). Constants at lines 134–145.

### 3.1 The `ENTRY_HAZARDS` dict has a typo, and it matters differently per gen

**source-verified.** `baselines.py:134-141`:

```python
    ENTRY_HAZARDS = {
        "spikes": SideCondition.SPIKES,
        "stealhrock": SideCondition.STEALTH_ROCK,
        "stickyweb": SideCondition.STICKY_WEB,
        "toxicspikes": SideCondition.TOXIC_SPIKES,
    }

    ANTI_HAZARDS_MOVES = {"rapidspin", "defog"}
```

`"stealhrock"` is a **typo** — the real Showdown move id is `stealthrock`. Probed against
`PE/data/static/moves/gen4moves.json`: `stealthrock` is present
(`{'target': 'foeSide', 'category': 'Status', 'basePower': 0}`), `stealhrock` is absent. The
dict is keyed by `move.id` and looked up as `move.id in ENTRY_HAZARDS` (line 291), so **SH can
never set Stealth Rock in any generation.** ps-ppo did not patch this (only `_stat_estimation`
is monkey-patched, `/Users/nickgreenquist/Documents/Projects/ps-ppo/worker.py:76`), so every
published SH number in the literature is a number for a bot that cannot set SR.

Usage, `baselines.py:286-303`:

```python
            for move in battle.available_moves:
                if (
                    n_opp_remaining_mons >= 3
                    and move.id in SimpleHeuristicsPlayer.ENTRY_HAZARDS
                    and SimpleHeuristicsPlayer.ENTRY_HAZARDS[move.id]
                    not in battle.opponent_side_conditions
                ):
                    return Player.create_order(move), 0
                elif (
                    battle.side_conditions
                    and move.id in SimpleHeuristicsPlayer.ANTI_HAZARDS_MOVES
                    and n_remaining_mons >= 2
                ):
                    return Player.create_order(move), 0
```

Note the removal branch's first condition is bare `battle.side_conditions` — **any** side
condition on our own side, including our own Reflect / Light Screen / Safeguard / Lucky Chant
/ Tailwind (all present in `PE/battle/side_condition.py:24-35` and all gen-2+). So in gen 4,
SH will spend a turn on Rapid Spin because it has its own Reflect up. Inert in gen 1, where
Reflect and Light Screen are per-mon volatiles rather than side conditions (recorded in
`SNAP/rl/envs/encoder_spec.py:57-60`).

**Pool grounding (tree-verified, cross-family — cite the parse, not memory).** Parsed
`SD/data/random-battles/gen4/sets.json` (295 species) with a short offline script counting
movepool ids across all `sets[].movepool`:

| move | occurrences in gen-4 randbats movepools |
|---|---|
| `spikes` | 14 |
| `toxicspikes` | 14 |
| `stealthrock` | **0** |
| `rapidspin` | 13 |
| `defog` | **0** |
| `stickyweb` | not a gen-4 move at all (absent from `gen4moves.json`) |

`grep -c stealthrock sets.json` → 0. `SD/data/random-battles/gen4/teams.ts:25-27` still
declares `const HAZARDS = ['spikes', 'stealthrock', 'toxicspikes'];`, and the hazard-selection
code at `teams.ts:351` filters to `['spikes', 'toxicspikes']` only. So **as vendored, the
gen-4 randbats pool does not run Stealth Rock at all**, which makes SH's `stealhrock` typo
doubly moot for this format — but it also means the format is much less hazard-dominated than
gen 4 OU intuition suggests. Flagged for `mechanics_delta.md` and `encoder_requirements.md`;
a future randbats-generator bump could reintroduce SR, so a `STEALTH_ROCK` slot in the side
block is cheap insurance rather than dead weight.

**Verdict:** the hazard-set branch is **100% inert in gen 1** (none of the four moves exists
in `gen1moves.json` — probed: all four MISSING) and **partially live in gen 4** (Spikes and
Toxic Spikes, ~28 of 295 species). The hazard-removal branch is **inert in gen 1** (no
`rapidspin`, no `defog` in gen1 data) and **live in gen 4** via Rapid Spin only.

### 3.2 `_estimate_matchup` — the type-chart core

**source-verified.** `baselines.py:147-163`:

```python
    @staticmethod
    def _estimate_matchup(mon: Pokemon, opponent: Pokemon):
        score = max([opponent.damage_multiplier(t) for t in mon.types if t is not None])
        score -= max([mon.damage_multiplier(t) for t in opponent.types if t is not None])
        if mon.base_stats["spe"] > opponent.base_stats["spe"]:
            score += SimpleHeuristicsPlayer.SPEED_TIER_COEFICIENT      # 0.1
        elif opponent.base_stats["spe"] > mon.base_stats["spe"]:
            score -= SimpleHeuristicsPlayer.SPEED_TIER_COEFICIENT
        score += mon.current_hp_fraction * SimpleHeuristicsPlayer.HP_FRACTION_COEFICIENT   # 0.4
        score -= opponent.current_hp_fraction * SimpleHeuristicsPlayer.HP_FRACTION_COEFICIENT
        return score
```

The chart is reached through `Pokemon.damage_multiplier`
(`PE/battle/pokemon.py:842-858`), which uses **`GenData.from_gen(self.gen)`** — the
*Pokemon's* gen, not `battle.gen`. (The task brief's "type chart via `GenData.from_gen(battle.gen)`"
is true only of `_should_terastallize`, `baselines.py:210`, which is inert in gen 4.) The
Pokemon's gen comes from `Battle(gen=…)` at `PE/player/player.py:198-214`, so it is 4 for us.

The chart itself is gen-correct: probed `GenData.from_gen(4).type_chart` vs gen 6 —
Steel takes Ghost `0.5` and Dark `0.5` in gen 4 vs `1` in gen 6 (the gen-6 Steel nerf), and
gen 1's Psychic takes Ghost `0` vs gen 4's `2` (the gen-1 Ghost/Psychic bug is faithfully
encoded). All nine chart files carry **18 type keys** including Fairy
(`GenData.load_type_chart`, `PE/data/gen_data.py:73-109`), so the *table* is 18-wide in every
generation — only the values differ. That is a layout note for the encoder spec: our
`EncoderSpec.types` tuple, not poke-env's chart, defines the one-hot width, and gen 4 needs
**17 real types** (Fairy arrives gen 6).

**What `_estimate_matchup` ignores, and how that lands per gen:**

| ignored | gen 1 cost | gen 4 cost |
|---|---|---|
| **abilities** (`damage_multiplier` is pure type chart — no Levitate, Wonder Guard, Flash Fire, Water/Volt Absorb, Motor Drive, Dry Skin, Thick Fat, Heatproof, Filter/Solid Rock) | **zero — gen 1 has no abilities** | **large** — Levitate alone turns a "4× Ground" read into a 0× read on a large slice of the pool |
| **items** (`Pokemon.item` is never read anywhere in `baselines.py`) | zero — gen 1 has no items | large — Choice Scarf inverts the speed-tier term, Choice Band/Specs/Life Orb invert the damage ratio, Leftovers/Sash change the HP term |
| **actual speed** (uses `base_stats["spe"]`, not `stats["spe"]`, not boosts, not paralysis, not Trick Room, not Chlorophyll/Swift Swim/Sand Rush) | moderate (para, Agility) | larger (adds Scarf, weather speed abilities, Trick Room) |
| **entry-hazard damage on the incoming mon** (the switch chooser at `baselines.py:354-366` maximises `_estimate_matchup` with no hazard term) | zero — no hazards in gen 1 | moderate — Spikes/T-Spikes exist (28/295 species set them) |
| **weather** (`battle.weather` never read) | zero — no weather in gen 1 | moderate — gen 4 randbats has Sand/Rain/Sun/Hail sets |

This table is the mechanical backing for JOURNEY's argument that **SH's strength drifts across
generations**: SH is a *type-chart-plus-base-stats* bot, and gen 1 is a game that is almost
entirely type chart plus base stats. Gen 4 is not.

### 3.3 `_should_switch_out`

**source-verified.** `baselines.py:219-247`. Fires only if some available switch scores
`_estimate_matchup > 0`, and then only on one of four "good reasons":
`boosts["def"] <= -3`, `boosts["spd"] <= -3`, `boosts["atk"] <= -3 and stats["atk"] >= stats["spa"]`,
`boosts["spa"] <= -3 and stats["atk"] <= stats["spa"]`, or
`_estimate_matchup(active, opponent) < -2` (`SWITCH_OUT_MATCHUP_THRESHOLD`, line 145).

`active.stats[...]` is the real request-supplied stat block
(`PE/battle/pokemon.py:741-743` ← `SD/sim/pokemon.ts:1165-1171`), so this comparison is sound
in both gens. Note the `-3` boost thresholds: in gen 4, Intimidate (a switch-in −1 Atk) and
repeated drops make these reachable more often than in gen 1, but the dominant trigger is the
`< -2` matchup threshold, which is the type-chart term above.

When `battle.available_switches` is empty (trapped, or last mon) the list comprehension is
empty and the function returns `False` — so SH never tries an illegal switch.

### 3.4 `_stat_estimation` — the +1-boost bug, stated exactly

**source-verified.** `baselines.py:249-256`:

```python
    @staticmethod
    def _stat_estimation(mon: Pokemon, stat: str):
        # Stats boosts value
        if mon.boosts[stat] > 1:
            boost = (2 + mon.boosts[stat]) / 2
        else:
            boost = 2 / (2 - mon.boosts[stat])
        return ((2 * mon.base_stats[stat] + 31) + 5) * boost
```

The guard should be `>= 1`, not `> 1`. Exact effect, evaluated:

| boost | poke-env's multiplier | correct multiplier |
|---|---|---|
| `+2` | `(2+2)/2 = 2.0` | 2.0 ✓ |
| **`+1`** | `2/(2-1) = **2.0**` | **1.5** ✗ |
| `0` | `2/2 = 1.0` | 1.0 ✓ |
| `-1` | `2/3 ≈ 0.667` | 0.667 ✓ |

So **a +1 boost is valued exactly as if it were +2** — a 33% over-estimate of the boosted
stat, on both the numerator (our attack) and the denominator (their defence).

**Correction to the prior-work index (source-verified).** `docs/prior_work/README.md:499` records
"the poke-env `_stat_estimation` +1-boost bug patched at `worker.py:76`", which is accurate.
But ps-ppo's own in-code comment
(`/Users/nickgreenquist/Documents/Projects/ps-ppo/worker.py:52`) says
*"Original bug checked `> 1` which made +1 act like +0, and +2 act like +2"* — **that
characterisation is wrong**: with `> 1`, +1 takes the `else` branch and yields `2.0`, i.e. +1
acts like **+2**, not like +0. The patch itself (`worker.py:53-57`) is correct; only the
comment is not. Worth a one-line correction in `docs/prior_work/README.md` when it is next touched.

Note also the formula body: `((2 * base + 31) + 5) * boost` is a level-100 / 0-EV / neutral-
nature stat with no level term at all. Random battles set levels per tier —
**gen 4 pool levels span 67–100** (parsed from `SD/data/random-battles/gen4/sets.json`), and
gen 1's span is comparable. So the ratio `atk_est / def_est` silently ignores every level
difference in both gens; in gen 4 it additionally ignores per-set EV spreads, natures, and
items. Gen-4-relative: worse, but not catastrophically so, because both numerator and
denominator share the flaw.

**Gen-4 salience of the +1 bug specifically.** Parsed from the gen-4 movepools: `swordsdance`
48, `calmmind` 44, `suckerpunch` 31 (not a boost, listed for scale), `nastyplot` 20,
`dragondance` 13, `curse` 11, `rockpolish` 11, `agility` 4. Single-stage boosters
(Dragon Dance, Calm Mind, Curse, Bulk Up) are common in gen 4, so the +1-mis-valuation is hit
frequently — *from the opponent's side*, since SH itself can never set up (§3.5).

### 3.5 The setup branch is DEAD — in every generation

**source-verified. This is the answer to "the index calls SH's setup branch 'dead': find out why".**

`baselines.py:305-320`:

```python
            # Setup moves
            if (
                active.current_hp_fraction == 1
                and SimpleHeuristicsPlayer._estimate_matchup(active, opponent) > 0
            ):
                for move in battle.available_moves:
                    if (
                        move.boosts
                        and sum(move.boosts.values()) >= 2
                        and move.target == "self"
                        and min([active.boosts[s] for s, v in move.boosts.items() if v > 0]) < 6
                    ):
                        return Player.create_order(move), 0
```

`Move.target` returns an `Optional[Target]` — a plain `enum.Enum`, **not** a `str` enum
(`PE/battle/move.py:672-680` returning `Target.from_showdown_message(...)`;
`PE/battle/target.py:11-33`, `class Target(Enum)` with no `str` mixin). Therefore
`move.target == "self"` is **always `False`**.

Probed directly:

```
swordsdance target repr: <Target.SELF: 15>   eq self -> False   boosts {'atk': 2}
```

So the entire setup branch is unreachable, in gen 1 and in gen 4 alike. **SH never uses a
setup move.** (Its sibling `MaxBasePowerPlayer` never does either, by construction.) Two
consequences worth carrying downstream:

1. For `anchors_and_eval.md`: SH's "setup" behaviour is not a behaviour, it is a bug. Any
   claim that "SH sets up when ahead" is false and should not appear in our docs.
2. This is a gen-*neutral* defect, so it does **not** contribute to SH drift — but it means
   SH leaves a large amount of gen-4 value on the table (48 Swords Dance / 44 Calm Mind
   movepools), so a *fixed* SH would be a materially different opponent in gen 4 than in gen 1.
   Do not silently fix it: it would break comparability with every published SH number
   (including ps-ppo's, which patched only `_stat_estimation`). This belongs in
   `open_questions.md` as a maintainer ruling.

### 3.6 Dynamax and Terastallize guards — inert in gen 4

**source-verified.** `_should_dynamax` (`baselines.py:165-187`) opens with
`if battle.can_dynamax:` and `_should_terastallize` (189–217) opens with
`if (not battle.can_tera or not active or not opp_active or active.tera_type is None): return False`.
Both flags are set only from `canDynamax` / `canTerastallize` in the request
(`PE/battle/battle.py:126-129`), which the gen-4 sim never emits (§1.5). Both are therefore
**inert in gen 4**, exactly as in gen 1, and the two calls at `baselines.py:344-349` reduce to
`Player.create_order(move, dynamax=False, terastallize=False)`.

Mega and Z: SH does not have branches for them at all — it never passes `mega=` or `z_move=`.
So SH never megas even in gen 6/7. Not a gen-4 issue, noted for completeness.

### 3.7 The move-scoring formula

**source-verified.** `baselines.py:322-340`:

```python
            move, score = max(
                [
                    (
                        m,
                        m.base_power
                        * (1.5 if m.type in active.types else 1)
                        * (
                            physical_ratio
                            if m.category == MoveCategory.PHYSICAL
                            else special_ratio
                        )
                        * m.accuracy
                        * m.expected_hits
                        * opponent.damage_multiplier(m),
                    )
                    for m in battle.available_moves
                ],
                key=lambda x: x[1],
            )
```

with `physical_ratio` / `special_ratio` from `_stat_estimation` at lines 268–273.

**It reads `move.category`; it does not infer from type.** But `Move.category` itself
infers from type below gen 4 (`PE/battle/move.py:209-216`):

```python
    @property
    def category(self) -> MoveCategory:
        if self.gen <= 3 and self.entry["category"].upper() in {"PHYSICAL", "SPECIAL"}:
            return self._MOVE_CATEGORY_PER_TYPE_PRE_SPLIT[self.type]
        return MoveCategory[self.entry["category"].upper()]
```

So `m.category == MoveCategory.PHYSICAL` is *the type rule* in gen 1–3 and *the real
per-move category* from gen 4 on. Probed: gen-4 `crunch` → PHYSICAL, gen-4 `shadowball` →
SPECIAL, i.e. the physical/special split is honoured. **This is the one place SH gets
strictly better in gen 4**, and it is also the reason
`SNAP/rl/envs/encoder_spec.py:49-52` can say the gen-4 encoder needs "NO new table" for
physical/special.

Three further properties of the formula:

- **`m.expected_hits`** (`PE/battle/move.py:322-341`) returns `(2 + 3) / 3 + (4 + 5) / 6 =
  3.1667` for every 2–5-hit move, in every generation. The true expected value for gen 1–4
  (3/8, 3/8, 1/8, 1/8) is **3.0**; 3.1667 is the gen-5+ distribution. Probed: gen-4
  `bulletseed` / `iciclespear` / `rockblast` / `bonerush` / `armthrust` all → 3.1667. A ~5.6%
  over-rating, present in both gens (gen 1 Pin Missile etc. hit it too), so gen-neutral.
- **`m.accuracy`** is `entry["accuracy"] / 100` with `True → 1.0`
  (`PE/battle/move.py:164-174`). Gen-4-accurate: probed Will-O-Wisp `0.75` (gen 9: `0.85`),
  Thunder Wave `1.0` (gen 9: `0.9`), Flamethrower BP `95` (gen 9: `90`), Rapid Spin BP `20`
  (gen 9: `50`). The `gen4moves.json` table is genuinely gen-4 data, not filtered gen-9 data.
- **Status moves score 0** (`base_power == 0`), so SH essentially always attacks unless a
  hazard branch fires. It never uses Toxic, Will-O-Wisp, Thunder Wave, Sleep Powder, Trick,
  Substitute, Protect, Roost, Wish. Gen-4 movepool counts for those: `substitute` 44,
  `protect` 45, `roost` 45, `trick` 21, `wish` 19. This is a *huge* slice of gen-4 randbats
  behaviour that SH ignores — and in gen 1 the equivalent slice (sleep moves, Recover,
  Reflect) is smaller and less decisive.

### 3.8 Two poke-env data quirks that bite SH (and our encoder) in gen 4 only

**(a) `return` is scored as base power 0.** `Move.retrieve_id` (`PE/battle/move.py:561-576`)
collapses `return102` → `"return"`, and the `_base_power_override` escape hatch in
`Move.__init__` (`PE/battle/move.py:104-112`) fires **only** for ids starting with
`hiddenpower`:

```python
        if move_id.startswith("hiddenpower") and raw_id is not None:
            base_power = "".join([c for c in raw_id if c.isdigit()])
            self._id = "".join([c for c in to_id_str(raw_id) if not c.isdigit()])
            if base_power:
                try:
                    self._base_power_override = int(base_power)
                except ValueError:
                    pass
```

The gen-4 sim sends the side-data move id as `return102` (`SD/sim/pokemon.ts:1176-1179`) and
the active-request name as `"Return 102"` with `id: "return"` (`SD/sim/pokemon.ts:999-1001`,
`1038-1045`). poke-env keeps neither number: probed `Move("return", gen=4).base_power == 0`.

Return appears in **39 of 295** gen-4 randbats movepools (13%). So:
- **SH scores Return as 0** and will never choose it over any attacking move.
- **`MaxBasePowerPlayer` scores Return as 0** — a 102-BP STAB move is invisible to the
  most-damage anchor. Directly relevant to `anchors_and_eval.md`.
- **Our encoder would emit `0.0` for that move's base-power feature**:
  `SNAP/rl/envs/showdown.py:251` is `vec[o + 1] = move.base_power / 100.0`. A gen-4
  `EncoderSpec` should either special-case `return`/`frustration` or read the request name.
  `frustration` is 0 occurrences in the gen-4 pool, so `return` alone is the fix.

**(b) Hidden Power *is* handled correctly, by a different path.** The side data sends the
typed id `hiddenpowerice` (`SD/sim/pokemon.ts:1172-1175`, with `gen < 6 ? '' : this.hpPower`
so gen 4 gets no BP suffix), while the active request sends `id: "hiddenpower"`
(`SD/sim/pokemon.ts:996-998`, `1040`). poke-env stitches this:
`_add_move("hiddenpowerice")` → `retrieve_id` → key `"hiddenpower"`, but `Move.__init__`'s
digit-strip branch resets `_id` back to `"hiddenpowerice"`
(`PE/battle/move.py:104-106`); then `available_moves_from_request`'s `hiddenpower` fallback
(`PE/battle/pokemon.py:820-826`) resolves the request's `hiddenpower` to that same object.
So `known_moves` and `available_moves` agree on `.id == "hiddenpowerice"`, the mask lines up,
and `/choose move hiddenpowerice` is normalised back by the server
(`SD/sim/side.ts:588-590`). Probed: `gen4moves.json["hiddenpowerice"]` is `basePower 70`,
`type Ice`. **97 of the gen-4 movepool entries are `hiddenpower*` across 8 types.** No action
needed, but the encoder must know that the *dict key* is `hiddenpower` while `move.id` is
`hiddenpowerice` — anything keyed off `active.moves` keys will see the wrong id.

### 3.9 `MaxBasePowerPlayer` and `RandomPlayer`

**source-verified.** `baselines.py:29-41`:

```python
class MaxBasePowerPlayer(Player):
    @staticmethod
    def choose_singles_move(battle: AbstractBattle):
        if battle.available_moves:
            best_move = max(battle.available_moves, key=lambda move: move.base_power)
            return Player.create_order(best_move)
        return Player.choose_random_move(battle)
```

It **never switches voluntarily** — only on force-switch, where `available_moves` is empty and
it falls to a uniform random switch. Gen-4 consequences for the "most-damage-typed" anchor:

- It ignores type effectiveness entirely (no `damage_multiplier` term), unlike the gen-4
  intuition of a "max damage" bot. It is a max-*base-power* bot.
- **Explosion**: gen-4 base power **250** (gen 1: 170); Self-Destruct **200** (gen 1: 130).
  Explosion is in **37** and Self-Destruct in **3** of 295 gen-4 movepools. So a
  MaxBasePower anchor in gen 4 will detonate essentially on sight, and so will SH (its
  formula is monotone in base power). This makes both baselines *much* weaker in gen 4 than
  their gen-1 counterparts on exactly the mons that carry Explosion. **This is a first-class
  finding for `anchors_and_eval.md`** and is the strongest single argument that a gen-4
  "most-damage-typed" anchor must be written by us rather than borrowed.
- Return (BP 0, §3.8a) and Hidden Power (BP 70 typed, fine) round out the data quirks.

`RandomPlayer` (`baselines.py:24-26`) → `Player.choose_random_move` →
`Player.choose_random_singles_move` (`player.py:474-480`) → uniform over
`battle.valid_orders`. In gen 4 `valid_orders` (`PE/battle/battle.py:274-303`) contains only
switches and plain moves (all four gimmick blocks are gated on the `can_*` flags), so the
gen-4 random player is distributionally the same object as the gen-1 one.

`PE/player/utils.py:16-20` fixes the evaluation ratings
`{RandomPlayer: 1, MaxBasePowerPlayer: 7.665994, SimpleHeuristicsPlayer: 128.757145}`, and
`evaluate_player` **hard-asserts `player.format == "gen8randombattle"`**
(`utils.py:137-140`). These numbers are gen-8 calibrations and are **not usable for gen 4**;
the assert makes that explicit. `cross_evaluate` (`utils.py:31-46`) is format-agnostic and
usable.

### 3.10 Verdict: which SH branches are inert in gen 1 and live in gen 4

| SH branch | gen 1 | gen 4 | why |
|---|---|---|---|
| hazard **setup** (`ENTRY_HAZARDS`) | **INERT** — none of the 4 moves exists in `gen1moves.json` | **PARTIALLY LIVE** — Spikes (14 pools) + Toxic Spikes (14); SR blocked by the `stealhrock` typo *and* absent from the pool; Sticky Web is gen-6+ | §3.1 |
| hazard **removal** (`rapidspin`, `defog`) | **INERT** — neither move exists in gen 1; `battle.side_conditions` is empty (gen-1 screens are volatiles) | **LIVE** — Rapid Spin in 13 pools; misfires on our own screens because the guard is bare `battle.side_conditions` | §3.1 |
| **setup moves** | **DEAD** (`move.target == "self"` is always False) | **DEAD** — same bug | §3.5 |
| `_should_dynamax` | INERT | INERT | §3.6 |
| `_should_terastallize` | INERT | INERT | §3.6 |
| `_should_switch_out` | LIVE | LIVE, but its `_estimate_matchup` input degrades (abilities/items/weather) | §3.2, §3.3 |
| move scoring physical/special split | type-derived (correct for gen 1 by definition) | **per-move (a genuine improvement)** | §3.7 |
| `_stat_estimation` +1 bug | LIVE, low dose (few boosters) | LIVE, **higher dose** (SD 48 / CM 44 / NP 20 / DD 13 / Curse 11 pools) | §3.4 |
| Explosion over-selection | LIVE at BP 170 | LIVE at **BP 250**, 37 pools | §3.9 |
| `return` scored 0 | n/a (no Return in gen 1) | **LIVE**, 39 pools | §3.8a |

**Is SH *relatively weaker* in gen 4? Yes, and the mechanism is enumerable.** SH is blind to
items, abilities, weather, hazard chip on switch-in, priority, and every status move. In gen 1
four of those six do not exist, so the blindness costs almost nothing; in gen 4 all six exist
and three of them (items, abilities, status) are load-bearing at the top of the format. Add
the gen-4-only data quirks (Return→0, Explosion at 250) and the direction is unambiguous.
The only counterweight is the physical/special split making the damage ratio genuinely
per-move (§3.7), which is a real but small gain.

**What this does *not* license.** I have not measured anything. "SH is weaker in gen 4" is a
mechanism argument, not a win-rate claim, and it says nothing about how strong SH is *relative
to a gen-4 agent we train*. Quantifying it is `anchors_and_eval.md`'s job and is
**needs-live-verification**: the check is an SH-vs-`MaxBasePowerPlayer` and
SH-vs-`RandomPlayer` cross-evaluation in `gen4randombattle` at the locked protocol
(3000 battles/seed, 3 seeds, ties as non-wins), compared against the same triangle run in
`gen1randombattle`. Both are barred until the ladder run and any subsequent fleet complete.

---

## 4. Other gen-specific things in this layer

### 4.1 `SPECIAL_MOVES` — three ids, one of which is gen-1-only

**source-verified + tree-verified.** `PE/battle/move.py:17`:

```python
SPECIAL_MOVES: Set[str] = {"struggle", "recharge", "fight"}
```

`Move.should_be_stored` returns `False` for all three (`move.py:83-85`), so they never land in
`Pokemon.moves` — which is precisely what makes `avail_ids[0] not in known_ids` the aliasing
trigger (§1.4). `Move.entry` synthesises a stub for `recharge` and `fight`
(`move.py:316-317`): `{"pp": 1, "type": "normal", "category": "Special", "accuracy": 1}`.
Probed: both come out as BP 0, type Normal, category SPECIAL, accuracy `0.01`
(`accuracy: 1` divided by 100 at `move.py:100-103` — a poke-env quirk, harmless since BP is 0).
`struggle` is a real data entry in both gens: BP 50, Normal, PHYSICAL, `randomNormal`.

**`fight` is gen-1-only.** `SD/sim/pokemon.ts:1105-1112`:

```ts
		if (this.battle.gen === 1 && !lockedMove && (['frz', 'slp'].includes(this.status) ||
			(this.volatiles['partiallytrapped'] && !this.maybeLocked))) {
			moves = [{ move: 'Fight', id: 'fight' as ID }];
			lockedMove = 'fight' as ID;
		} else if (!moves.length) {
			moves = [{ move: 'Struggle', id: 'struggle' as ID, target: 'randomNormal', disabled: false }];
			lockedMove = 'struggle' as ID;
		}
```

So in gen 4 a frozen or sleeping mon simply gets its normal four moves listed, and the
`fight` placeholder never appears on the wire. **Gen-4 `SPECIAL_MOVES` is effectively
`{struggle, recharge}`.**

**And `recharge` is nearly extinct in gen-4 randbats.** Movepool counts parsed from
`SD/data/random-battles/gen4/sets.json`: `gigaimpact` 1, `hyperbeam` 0, `blastburn` /
`hydrocannon` / `frenzyplant` / `roaroftime` / `rockwrecker` all 0. Compare gen 1:
`grep -o hyperbeam SD/data/random-battles/gen1/data.json | wc -l` → **55** occurrences across
146 species. So the whole `SPECIAL_MOVES` aliasing path — which our encoder guards with
`_move_slots_aliased` (`SNAP/rl/envs/showdown.py:393-397`) — is **common in gen 1 and close to
vestigial in gen 4** (Struggle plus one Giga Impact set).

**Cross-reference for `encoder_requirements.md`:** the gen-4 `EncoderSpec.special_move_ids`
should be `frozenset({"struggle", "recharge"})`, not the gen-1 three. Keeping `fight` in it
would be harmless (it simply never matches) but would be a false statement about gen 4.

### 4.2 Struggle / recharge round trip

**source-verified.** `SingleBattleOrder.message` (`PE/player/battle_order.py:45-67`):

```python
        if isinstance(self.order, Move):
            if self.order.id == "recharge":
                return "/choose move 1"
            message = f"/choose move {self.order.id}"
```

so recharge is sent positionally and Struggle by id (`/choose move struggle`), which the
server parses at `SD/sim/side.ts:584-596`. Both work in gen 4 exactly as in gen 1.

### 4.3 Called moves and move-set growth: the gen-4 desync surface is empty

**source-verified + tree-verified.** `AbstractBattle`'s `|move|` handler
(`PE/battle/abstract_battle.py:582-673`) sets `reveal = False` for Copycat, Metronome, Nature
Power, Round, Magic Bounce, Magic Coat, Mirror Move and Dancer, but **not** for Assist or Me
First — those fall into the `else` warning branch (lines 637–645) and the called move *is*
added, growing `Pokemon.moves` past four and truncating under
`list(active.moves.values())[:4]`. That would desync the mask from the true slot order.

Parsed `SD/data/random-battles/gen4/sets.json`: `assist` 0, `mefirst` 0, `metronome` 0,
`copycat` 0, `mimic` 0, `naturepower` 0, `mirrormove` 0, `magiccoat` 0. `sleeptalk` **25**
(handled explicitly — `abstract_battle.py:616-626` normalises `[from] Sleep Talk` and lets the
reveal through, which is correct because Sleep Talk calls one of the mon's own moves).
`transform` **1** — Ditto, `{"level": 100, "sets": [{"role": "Fast Support", "movepool":
["transform"], "abilities": ["Limber"]}]}`.

poke-env 0.15.0 handles both Transform and Mimic structurally via `MoveSet`
(`PE/battle/move.py:953-1013`): `_transform_moves` swaps the whole resolved set,
`_mimic_move` substitutes **in place** at the `mimic` key so the four slots keep their
positions. Both are reset on switch-out (`PE/battle/pokemon.py:610-611`) and on
`_update_from_details` (427–428).

**Verdict:** the gen-4 randbats pool contains no move that can grow a mon's move dict past
four, and the one Transform user is handled by dedicated machinery. The gen-4 mask desync
surface from called moves is **empty as vendored**. (It is not empty for gen-4 OU or for a
future randbats generator revision.)

### 4.4 `battle.gen` plumbing

**source-verified.** `Player._create_battle` sets `gen = GenData.from_format(self._format).gen`
and passes it to `Battle(...)` (`PE/player/player.py:198-214`); every `Pokemon` and `Move` then
carries that gen and looks its data up through `GenData.from_gen`. `GenData` is a per-gen
singleton with `__deepcopy__` returning `self` (`PE/data/gen_data.py:16-31, 115-119`), so the
gen-4 tables are loaded once per process. `from_format` is `int(format[3])` with the comment
`# Update when Gen 10 comes` (line 123) — fine for us.

`get_action_mask` uses `battle.gen` for the mask width
(`singles_env.py:286`), so it is self-consistent with the `Discrete` built from the format
string.

### 4.5 Gen-4 format-level differences visible from this layer

**tree-verified.** `SD/config/formats.ts:4239-4244` vs `4260-4264`:
gen 4 randbats runs `['Obtainable', 'Sleep Clause Mod', 'HP Percentage Mod', 'Cancel Mod']`;
gen 1 runs `['Standard']`. Notably gen 4 has **no Freeze Clause and no Evasion clause** where
gen 1's `Standard` (gen-1 mod ruleset) does carry Freeze Clause. That is a
`mechanics_delta.md` item, not an env-layer one, but it is visible from here and I record it
so the mechanics agent can confirm against `SD/data/mods/gen1/rulesets.ts` and
`SD/data/mods/gen4/rulesets.ts`, which I did **not** read.

---

## 5. Gen-1 encoder assumptions this breaks

Ordered by how much work each implies. Cross-referenced to
`SNAP/rl/envs/encoder_spec.py` (the landed seam) and `SNAP/rl/envs/showdown.py`.

1. **`special_move_ids` must lose `fight`.** `encoder_spec.py:91-94` documents
   `SPECIAL_MOVES` as the re-basing trigger; in gen 4 the set is `{struggle, recharge}` and
   `recharge` is near-extinct in the pool (§4.1). `_move_slots_aliased`
   (`showdown.py:393-397`) will essentially never fire in gen 4. **tree-verified.**
2. **`move.base_power` is 0 for `return`** (39/295 gen-4 movepools), so
   `showdown.py:251` (`vec[o+1] = move.base_power / 100.0`) silently zeroes a common,
   102-BP STAB move. A gen-4 spec needs an explicit `return`/`frustration` base-power
   override or must read the request move name. **source-verified + tree-verified.** No gen-1
   analogue (Return does not exist in gen 1).
3. **The move dict key and `move.id` diverge for Hidden Power** (key `hiddenpower`,
   `move.id` `hiddenpowerice`), and 97 gen-4 movepool entries are Hidden Power. Anything the
   encoder keys off `active.moves.keys()` (rather than `move.id`) reads the wrong id in gen 4.
   **source-verified + tree-verified.** In gen 1 Hidden Power does not exist, so this path is
   entirely new.
4. **Types: 17, not 15** — and poke-env's *chart* is 18-wide in every gen (Fairy included),
   so the spec's `types` tuple is what defines the one-hot, per
   `encoder_spec.py:39-43`. Gen 4 needs Dark and Steel added and Fairy excluded.
   **source-verified.** Already on the seam's blocker list (`encoder_spec.py:268`).
5. **The action head does NOT change.** `get_action_space_size(4) == 10 == GEN1.n_actions`,
   so `encoder_spec.py:277-281` will not append an action-head item to its refusal list.
   The pointer head, the mask width, and the switch/move slot arithmetic all carry over.
   **tree-verified.** This *reduces* the gen-4 blocker list by one item relative to what the
   seam's docstring implies for a generic new gen.
6. **`move.category` stops being a function of type** (`PE/battle/move.py:214-215`), which
   `encoder_spec.py:49-52` already anticipates — no new table, but the gen-1 invariant
   "category ≡ type" no longer holds and any code that assumed it (there is none in the
   encoder, per that comment) would break. **source-verified.**
7. **New per-mon fields exist in the request: `item` and `baseAbility`**
   (`SD/sim/pokemon.ts:1182-1183`), both empty in gen 1. Adding them is a `MON_DIM` change,
   i.e. an `OBS_DIM` change, i.e. every checkpoint invalidated (the standing landmine).
   Already on the seam's list (`encoder_spec.py:269`). Note gen 4 gets `baseAbility` only —
   the live `ability` field is gen-7+ (`SD/sim/pokemon.ts:1186`), so an ability changed
   mid-battle (Trace, Skill Swap) is not in the request and must be tracked from
   `|-ability|` messages. **tree-verified.**
8. **Side conditions are real in gen 4** (Spikes 14, Toxic Spikes 14 in the pool; Reflect /
   Light Screen / Safeguard / Lucky Chant / Tailwind all `SideCondition`s from gen 2), where
   gen 1's Reflect/Light Screen are per-mon volatiles carried in `EncoderSpec.volatiles`
   (`encoder_spec.py:57-60`). They must move out of the volatile block into a side block.
   **Stealth Rock is absent from the vendored gen-4 pool** (§3.1), so an SR slot is insurance
   rather than a requirement. **tree-verified.**
9. **`maybe_trapped` becomes a real, unmodelled state** (§1.6). Gen 1 has no ability
   trapping; gen 4 does, and poke-env exposes the flag but neither masks on it nor encodes it.
   A gen-4 spec should consider a `maybe_trapped` observation bit even if the mask is left
   alone. **source-verified + tree-verified.**
10. **The `randbats_prior.py` set prior is gen-1-only** (`encoder_spec.py:273`), and the
    gen-4 pool has a different *shape*: 295 species with 1–2 `sets` each, each a
    5–6-move `movepool` from which 4 are drawn, plus per-set `abilities` and a per-species
    `level` (67–100). The gen-1 file is `data.json` with a flat `moves` list per species and
    146 species. A gen-4 prior is a rewrite, not a port. **tree-verified**, cross-referenced
    to the pool survey.

---

## 6. Cross-references for the other downstream docs

- **`mechanics_delta.md`:** `fight` is gen-1-only (`SD/sim/pokemon.ts:1105-1108`); the
  physical/special split lands at gen 4 (`PE/battle/move.py:214-215`); Explosion 170→250 and
  Self-Destruct 130→200; Steel resists Ghost/Dark in gen 4 but not gen 6; gen-1 Psychic is
  immune to Ghost, gen 4 takes 2×; the gen-4 randbats ruleset drops Freeze Clause
  (`SD/config/formats.ts:4239-4244`); ability trapping (Arena Trap / Magnet Pull / Shadow Tag)
  arrives.
- **`pokeenv_gen4_survey.md`:** `gen4moves.json` / `gen4pokedex.json` / `gen4typechart.json`
  all ship with poke-env 0.15.0 and are genuinely gen-4 data (probed: Flamethrower 95, Rapid
  Spin 20, Will-O-Wisp 75%, Thunder Wave 100%). `evaluate_player` hard-asserts gen 8
  (`PE/player/utils.py:137-140`) and is unusable; `cross_evaluate` is fine.
- **`anchors_and_eval.md`:** SH's setup branch is dead in all gens (§3.5); SH cannot set
  Stealth Rock in any gen (§3.1); `MaxBasePowerPlayer` is a max-*base-power* bot that ignores
  type effectiveness and will detonate Explosion at BP 250 (§3.9); Return is invisible to both
  (BP 0, §3.8a); poke-env's `_EVALUATION_RATINGS` are gen-8 calibrations.
- **`encoder_requirements.md`:** the ten items in §5 above.
- **`open_questions.md`:** whether to patch SH for gen 4 (setup branch, `stealhrock`,
  `_stat_estimation`) and thereby break comparability with every published SH number,
  including ps-ppo's partially-patched one; and whether the gen-4 mask should mask out
  switches under `maybe_trapped`.

---

## 7. Open questions for the maintainer

1. **Do we patch `SimpleHeuristicsPlayer` for gen 4?** Three defects are now documented and
   independent: the dead setup branch (`move.target == "self"`, §3.5), the `stealhrock` typo
   (§3.1, moot for this pool), and the `_stat_estimation` +1 bug (§3.4). Patching makes SH a
   *better* and more gen-4-representative opponent; not patching keeps the anchor comparable
   with gen 1 and with the literature. My recommendation: **do not patch**, and instead
   disclose the three defects wherever a gen-4 SH number is quoted, exactly as we disclose
   FP@20's two caveats. *The losing argument:* a bot that cannot set up, cannot set Stealth
   Rock, and mis-prices every +1 boost is a straw opponent in gen 4 in a way it is not in gen
   1, so a gen-4 SH win rate is not the same instrument as a gen-1 SH win rate and calling
   both "vs-SH" invites exactly the cross-generation projection the ladder landmine forbids.
2. **Is the gen-1 vs-SH bar transferable at all?** Given §3.10, "X% vs SH" almost certainly
   does not mean the same thing in gen 4. Does the chapter want a re-anchored bar (e.g. SH's
   own triangle vs Random / MaxBasePower measured in gen 4 first), or a fresh instrument?
3. **`maybe_trapped`: mask, encode, or neither?** Masking is conservative but forbids legal
   switches; encoding costs a dimension; neither leaves `_recover_mask_desync` to absorb the
   rejections. Recommendation: **encode a bit, do not mask**, and count the
   `[Unavailable choice]` rate as a disclosed metric. *The losing argument:* every rejected
   choice is an extra request round-trip in the single message-handling coroutine, which is
   the same coroutine the orphaned-room deadlock lives in; if the rate is non-trivial it is a
   throughput and a liveness question, not just an accuracy one.
4. **The vendored gen-4 randbats pool has no Stealth Rock.** That is surprising enough that it
   should be an explicit, disclosed premise of the chapter rather than a quiet assumption —
   and it means a Showdown re-clone or version bump could change the format under us. Do we
   pin `showdown/` to `59da482` for the whole gen-4 chapter?
5. **`return`'s base power.** Fix in the encoder (override 102), or leave it at 0 and accept
   that 13% of movepools carry a move the agent sees as powerless? Recommendation: **override**
   — it is three lines and the alternative is a known-wrong feature. *The losing argument:*
   Return's real BP is happiness-dependent and the randbats generator's value is not
   guaranteed to be 102 forever; hardcoding it embeds a fact we have not verified in the
   generator.

---

## 8. Unread / unverified

Stated plainly so nothing here is mistaken for checked:

- **I did not read** `PE/environment/doubles_env.py`, `PE/teambuilder/*`, `PE/calc/*`,
  `PE/concurrency.py`, or `PE/ps_client/{account_configuration,server_configuration}.py`.
- **I did not read** `SD/data/mods/gen4/{abilities,items,moves,conditions,scripts}.ts` beyond
  the three `onFoeMaybeTrapPokemon` hits in the shared `data/abilities.ts`. Every claim about
  gen-4 *mechanics* (as opposed to gen-4 *data as poke-env sees it*) is therefore either
  tree-verified against `sim/` or explicitly handed to `mechanics_delta.md`.
- **I did not read** `SD/data/mods/gen4/rulesets.ts` or `SD/data/mods/gen1/rulesets.ts`, so
  the Freeze Clause remark in §4.5 is a `formats.ts`-level observation only.
- **I did not read** `SD/data/random-battles/gen4/teams.ts` in full — only lines 14–30 and the
  hazard/rapid-spin regions found by grep. Set-construction details (how 4 moves are drawn
  from a 5–6 move pool, ability rolls, item assignment, level tiers) belong to the pool
  survey and I have not verified them.
- **I did not verify** that Dugtrio / Magnezone / Magneton / Wobbuffet are in the gen-4
  randbats pool with trapping abilities, so §1.6's prevalence claim is deliberately unquantified.
- **Not verified live, and barred until after the ladder run:** that a gen-4 force-switch
  request truly omits the `"active"` key (§1.5); the actual `maybe_trapped` and
  `[Unavailable choice]` rates (§1.6); that no gen-4 randbats battle ever produces a
  `Pokemon.moves` dict longer than four (§4.3); and every quantitative statement about SH's
  gen-4 strength (§3.10).
- **Nothing in this note is literature-only.** Every finding is tied to a file I opened or a
  value I probed offline. Where I could not check something, it is in this section rather than
  in the body.
- **No claim here rests on a running server.** The local Showdown server was not started, port
  8000 was not touched, no `Player`/`Env`/`PSClient` was constructed, and no process was
  signalled. Only `GenData` / `Move` / `SinglesEnv.get_action_space_size` static reads and
  two `json.load` calls were executed, all under `nice -n 19`.

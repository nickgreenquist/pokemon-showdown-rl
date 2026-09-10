# ENGINE-NATIVE SEARCH — DESIGN

**Status:** DESIGN, not a pre-reg. Nothing here credits anything. Every arm named
below needs its own config header naming its `journey_step` and restating that
step's exit condition verbatim before it launches (CLAUDE.md, "Conventions").

**Written:** 2026-09-10, after A-1 graded A1-PASS (`STATUS.md:21-25`), after S1
fired (`docs/search_relook/S1_S2_SCREENS.md:167-168`) and `det_blind` was built
(`docs/search_relook/DET_BLIND.md:14-20`), while S3B / F3B112 / S3M / S3L / A1E
are still running.

**Journey position.** This design serves **JOURNEY 11.5** (`JOURNEY.md:122-137`)
and **JOURNEY 14** (`JOURNEY.md:149-196`). It is downstream of **JOURNEY 7.5**,
whose exit is the A-1 re-run (`STATUS.md:25`); JOURNEY 14 names 7.5 as its
precondition in as many words (`JOURNEY.md:186-189`: "Real search needs to copy
a state and roll it forward thousands of times… pkmn/engine's 384-byte state
makes it ordinary. **Keep a state-copy/rollout surface in the collector even
before anything uses it.**"). This document is the specification of that
surface.

**One correction carried throughout.** `docs/PKMN_ENGINE_RUST_PLAN.md:1212-1218`
lists "`-Dchance`/`-Dcalc` builds for exact chance enumeration" as the depth-2
asset, and `JOURNEY.md:131` repeats it. That is **backwards** and
`STATUS.md:50-51` already records the correction: *"The asset is the 384-byte
clone + Rust encode, not the chance builds (plan §8.4 backwards)."* The pinned
build is `-Dchance=false -Dcalc=false` (`engine/pkmn_gen1/build.rs:218-219`), and
`ffi.rs:59-64` **refuses** a chance/calc build outright ("the collector requires
both off"). What `-Dchance` actually buys is the probability of the transition
that *happened*, and `-Dcalc` re-runs one update with chosen overrides
(`engine/pkmn_gen1/vendor/pkmn-engine/docs/TESTING.md:14-17`) — the enumeration
loop over the override space is the **caller's**, not the engine's. So the
engine's update is a **sample**, and every design decision below follows from
that.

---

## 1. Goal, and the two forms it must support

### 1.0 The one-sentence goal

Give the search a transition function that costs ~5.7 µs per leaf instead of
~212 µs, without changing what the agent is allowed to know, so that (a) the
existing depth-1 form becomes cheap enough to run at a real per-turn budget and
(b) depth-2 becomes buildable at all.

### 1.1 Form A — engine-native depth-1, a like-for-like replacement

**Definition.** Identical to `rl/search/matrix.py::solve_decision` with
`leaf_encoding="det_blind"` in every respect except the simulator: the
determinization is the same RSD draw, the rows are the same legal actions, the
columns are the same L6 classes weighted by the same oppact posterior `q`
(`matrix.py:184-186`), the leaf evaluator is the same critic, the tie-breaks are
the same (D3/D4, `matrix.py:33-37`). Only `generate_instructions` +
`apply_instructions` + `shadow_battle` + `embed_battle` is replaced by
`Battle::clone_into` + `Battle::update` + `BattleTracker::observe` +
`encoder::encode`.

**Why "like-for-like" is the whole point.** It is the only form that can be
*gated by parity*. A decision-level agreement test against the poke_engine path
on the harvest is a real oracle; nothing else in this line has one. Form A is
therefore both the deliverable and the gate on the write-side bridge.

**What it answers.**
- **JOURNEY 14, precondition** (`JOURNEY.md:186-189`): the state-copy/rollout
  surface exists, and a checkpoint can be searched at a real budget rather than
  at 20 ms. JOURNEY 14 item 1 (`:166-170`) is precisely "the ladder gives ~150 s
  per turn and every point on the depreciation curve is depth-1 at 20 ms —
  0.013% of the budget."
- It does **not** answer JOURNEY 11.5. Depth-1 faster is not depth-2.

**What it does NOT change.** The determinizer's error (`DET_BLIND.md:304-309`:
"The determinizer's error is untouched by this build; only the encoder's is"),
the RSD prior, the oppact head, the credit line.

### 1.2 Form B — depth-2 with sampled chance

**Definition.** §5 gives it precisely. The root is Form A's matrix; each cell's
value becomes the value of a depth-1 solve at the child rather than the value of
a leaf; chance at both plies is a **sample average** over `S` engine seeds.

**What sampling does to the BR solve.** This is the load-bearing change and it
must not be glossed.

Today, one `(row, col, det)` cell is filled by
`generate_instructions(state, a, b)` → branches with explicit probabilities →
top-`top_branches` retained (6 at every dose, `matrix.py:79-83`) →
renormalised → each branch's leaf valued → weighted sum
(`matrix.py:218-222, 256, 267-269`), with the 2-point KO-roll expansion adding
exact roll mass on top (`rl/search/expansion.py:100-102, 156-164`). The estimate
is **exact over the retained mass and biased by the discarded tail**; the
retained mass is already recorded per decision
(`matrix.py:222, 287` → `search/retained_mass_mean`).

On the engine, the same cell is filled by `S` independent
`clone + seed + update` calls. The estimate is **unbiased over the FULL chance
distribution and noisy at σ_cell/√S**. That is not "the same thing, cheaper" —
it is a different estimator with the opposite error profile.

The decision-relevant quantity is not σ_cell but the sd of the **margin**
(top1 − top2 of `row_ev`), because a chance component common to every row of a
determinization cancels exactly in the argmax — the same argument
`S1_S2_SCREENS.md:318-329` makes about the encoding artefact. Two consequences:

- **CRN-1 (common random numbers), a binding rule.** The chance seed is a pure
  function of `(decision key, col, det, sample index)` and **never** of the row.
  Every row of a `(col, det, s)` triple is rolled forward from the same PSRNG
  seed. This is the standard variance reducer for a simultaneous-move matrix over
  shared randomness. It is a *heuristic*, not an identity — the engine consumes
  rolls in an order that depends on both actions, so identical seeds do not
  guarantee identical shared events — and it must be measured, not assumed.
- **P0 calibration, and it gates everything downstream.** Before Phase 3 commits
  to a dose, measure `sd(top1 − top2)` across independent chance-seed families at
  fixed determinizations, for `S ∈ {1, 2, 4, 8, 16, 32}`, with and without CRN,
  on ~200 harvest roots. Choose the smallest `S` with
  `sd(margin) ≤ 0.2 × median(margin)`. The median Dose-M margin is **0.02773**
  (`S1_S2_SCREENS.md:166`), so the target is `sd(margin) ≤ 0.0055`.

**When to prefer which simulator.**

| | poke_engine (exact enumeration) | pkmn/engine (sampled) |
|---|---|---|
| per-leaf cost | ~212 µs all-in at dose M, of which ~116 µs is `shadow_battle`+`embed_battle` (session scoping) | 5.7 µs/row batched, engine + tracker + encoder (session scoping) |
| chance model | exact over retained mass; biased by the truncated tail | unbiased over the full distribution; noisy at 1/√S |
| branch count per cell | `top_branches` = 6, deterministic | `S`, chosen |
| depth 2 | 6² = 36 branch pairs per (row, col, row′, col′) — combinatorially dead | the only option |
| probabilities | free, from `generate_instructions` | not available; the sample frequency *is* the probability |

**Recommendation.** For **depth 1**, at a *matched leaf count*, poke_engine's
estimator is strictly better — 6 leaves buy the exact retained-mass EV, where 6
samples buy `se ≈ σ_cell/2.4`. The engine wins on depth-1 only through wall
clock: at ~37× the throughput per leaf it can buy ~37× the samples, and √37 ≈ 6×
less noise. Whether that beats the truncation bias is **exactly what P0
measures**, and the answer is not obvious in advance. For **depth 2**, exact
enumeration is not on the table at any budget, so the engine is the only
simulator and sampling is the only chance model.

**What Form B answers.** JOURNEY 11.5, and only that. Its exit condition, quoted
verbatim in `configs/eval/search_s3_100m.yaml:8-12` and `JOURNEY.md:133`:

> **Exit condition: one comparison, then the chapter closes.** Depth-2 credits
> over depth-1 iff the pooled delta clears the standing credit line. Report
> decisions/sec for both arms — a gain that costs 5× is a different finding than
> the same gain at 1.5×.

`JOURNEY.md:137`: "No depth-3. If depth-2 is ambiguous, that is the answer." The
session's own scoping agrees for a second reason: depth-3 is 75.4² ≈ 5,700× a
depth-1 tree, i.e. ~13 s/decision even at 5.7 µs/leaf. **Depth-3 is dead
everywhere and this design does not consider it.**

### 1.3 The one invariant that governs both forms

**L-BOUNDARY.** A leaf's 828-dim actor observation keeps the **root's**
information boundary. A leaf's optional 408-dim privileged block carries the
**full determinized** opponent side. These are two different information sets in
one input, exactly as at training time, and they must never be mixed.

This resolves an apparent contradiction that is worth stating plainly, because
it will otherwise be raised at review: `det_blind` exists to *hide* the
determinizer's invented bench from the critic (`DET_BLIND.md:29-40`), and the
privileged block's entire content *is* the opponent's bench
(`encoder.rs:56-65`). They do not conflict, because they feed **different heads
with different training-time input contracts**:

- The ordinary critic was trained on live 828 vectors, where an unrevealed
  opponent mon is zeros behind a zero `revealed` flag. Handing it a determinized
  bench is out-of-distribution — that is S1, measured at +0.0497 mean / 0.1254 sd
  against a 0.0277 margin (`S1_S2_SCREENS.md:165-170`).
- A privileged evaluator head is trained on `(obs_828, priv_408)` where **every**
  training row's 408-block is a fully populated opponent side
  (`env.rs:295-302`). Handing it a *zeroed* block would be the
  out-of-distribution move; handing it a determinized one is in-distribution, and
  the only residual shift is prior-vs-truth, which is the proposal's own R4
  (`docs/proposals/privileged_critic_engine_route.md:482-490`, "a named secondary
  read, not an assumption").

On the engine this falls out of the tracker for free: the boundaried half comes
from `BattleTracker::foe_seat` (`track.rs:394-438`, revealed mons only, HP
quantised, PP from observed uses) and the full-information half from
`BattleTracker::own_seat` (`track.rs:352-391`, exact HP, exact status, exact PP,
all six slots). **det_blind stops being an option and becomes a property of the
tracker.**

---

## 2. The write-side bridge

### 2.1 The gap

`layout.rs` is entirely read-only: `BattleView`, `SideView`, `PokemonView`,
`ActiveView` all wrap `&[u8]` (`layout.rs:246, 294, 351, 398`). The only
constructors are `Battle::new` — which builds a **fresh** battle (parties in
original order, `order[i] = i+1`, turn 0, **actives zeroed**, and whose first
update must be `(Pass, Pass)`; `battle.rs:211-236`) — and
`PyBattle::from_bytes`, which wraps 384 arbitrary bytes with **no validation**
(`python.rs:289-297`).

There is no way to construct a mid-battle `Battle` from a public view. That is
the write side, and it does not exist. **Not found:** any writer, any
`PokemonViewMut`/`ActiveViewMut`, any builder.

### 2.2 Inputs

- `battle1` — poke-env's seat-1 view, or a harvest snapshot
  (`rl/search/harvest.py:57-77`; both expose the same surface, `agent.py:5-6`).
- One determinization — `rl/search/determinize.py:153-210`'s output: per opponent
  species `{moves, level, base_stats, dvs, live, provenance}` plus the sampled
  unrevealed bench.

### 2.3 The stat model transfers EXACTLY — verify this before anything else

`bridge.gen1_stat(base, level, hp, dv=15)` with `_EXP_TERM = 63`
(`bridge.py:110-119`) and `team::ps_stat(base, iv=30, ev=255, level, is_hp)`
(`team.rs:20-27`) compute the same integer:

```
bridge, non-HP: floor((2*base + 30 + 63) * level/100) + 5
team,   non-HP: floor((2*base + 30 + 255/4) * level/100) + 5      # 255/4 = 63
bridge, HP:     floor(core*level/100) + level + 10
team,   HP:     floor((core + 100)*level/100) + 10                # == the above, level integral
```

So `PokemonSet { ivs: [30;5], evs: [255;5] }.to_bytes()` (`team.rs:46-54, 75-99`)
reproduces the determinizer's max-DV model bit-for-bit
(`determinize.py:44-56`: max DV, evidence-based — 94.85% of 7,500 realized server
stats are exactly the max-DV formula). **This is the single largest piece of
reuse available and it should be pinned by a test on day one.** Caveat: the team
bank's `min_atk` variant (`env.rs:437, 442-446`, IV 2 / EV 0 on Attack for
special-only sets) is a randbats generator behaviour the determinizer does not
model — declared, family **W-STATS**.

### 2.4 Field-by-field over `layout.rs`

Legend: **K** = known exactly from `battle1`; **D** = determinized;
**S** = sampled (hidden even to the opponent's own client, or hidden to us and
not carried by the determinizer); **F** = free (unobservable and provably
irrelevant); **V** = vacuous in `gen1randombattle` (pool census, §2.5).

#### `Battle` (384 bytes)

| offset | field | class | source / rule |
|---|---|---|---|
| 368 `B_TURN` u16 | turn | **K** | `battle.turn` (`harvest.py:61`). Encoder reads `turn/50` capped (`encoder.rs:263`). |
| 370 `B_LAST_DAMAGE` u16 | last damage dealt | **S** | Read by Counter — **27 of 146 pool species carry Counter** (§2.5), so this is live, not vacuous. Family **W-LASTDMG**. Rule: reconstruct from the HP delta of the mon last damaged — exact on our side, `%·maxhp_det` on theirs; 0 when no damage is attributable. `layout.rs:408-411` marks it HIDDEN *for encoding*; that is about the observation, not about the transition, and the two are different questions. |
| 372 `B_LAST_MOVES` 4×u8 | `(index, counterable)` per player | **S** | `layout.rs:412-416`. `index` is a slot index, not a move id (the engine writes 1 on switch-in, `mechanics.zig:238`); `counterable` is derivable from the last observed move's type/category. Same family **W-LASTDMG**. |
| 376 `B_RNG` u64 | PSRNG seed | **S by design** | Not an approximation — this **is** the chance dial. `splitmix64(decision_key ^ col ^ det ^ s)` per CRN-1 (`battle.rs:368-374`, `PsRng` at `:342-365`). |

#### `Side` (184 bytes) × 2

| offset | field | class | source / rule |
|---|---|---|---|
| 0..144 `S_POKEMON` | six 24-byte records | see below | |
| 144..176 `S_ACTIVE` | `ActivePokemon` | see below | |
| 176 `S_ORDER` 6×u8 | `order[slot-1]` = one-based party index | **K** for slot 0, **F** for 1..5 | `order[0]` = active party index + 1 (`layout.rs:364-374`). The rest carries switch history and is unobservable — but **every action maps through `slot_of_party_index`** (`layout.rs:377-383`, used at `env.rs:86`), so the permutation is action-mapping invariant. Write the identity with `order[0]` swapped to the active, exactly as `switchIn` does (`mechanics.zig:234-236`). Family **W-ORDER**, declared free. |
| 182 `S_LAST_SELECTED_MOVE` u8 | last move selected | **S** | Read for the hard-lock action mapping (`env.rs:106-120`), for `choice_identity` (`env.rs:154-156`), for Mirror Move (4 pool species) and for releasing a charge turn. **`freeze_battle` does not carry it** (`harvest.py:57-77` — `must_recharge`/`preparing` are booleans only), so the harvest-replay gate must declare it; the **live** path can fill it from poke-env's own `_preparing_move`. Incidence bound: `preparing` is 0.31% (opp) / 0.03% (own) of harvest roots (§2.5). Family **W-LASTMOVE**. |
| 183 `S_LAST_USED_MOVE` u8 | last move used | **S** | Same family. Cleared on switch-in for *both* sides (`mechanics.zig:240-241`), which is a cheap correctness win: after any switch it is provably 0. |

#### `Pokemon` (24 bytes) × 6

| offset | field | class | source / rule |
|---|---|---|---|
| 0 `P_STATS` 5×u16 (hp, atk, def, spe, spc) | unboosted stats | **K** ours / **D** theirs | Ours: `mon.stats` from the request (`harvest.py:44`). Theirs: §2.3's identity — `PokemonSet{ivs:[30;5], evs:[255;5]}`. Note gen 1 has ONE Special: poke-env's `spa` == `spd` and the engine has one `spc` (`team.rs:6-8`). |
| 10 `P_MOVES` 4×(u8 id, u8 pp) | stored slots | **K** ours / **D** theirs | Ours: exact ids in `mon.moves` insertion order (which is what `our_action_str` indexes, `matrix.py:95-100`) and exact `current_pp`. Theirs: determinized ids; PP = `max_pp − observed_uses` for revealed moves — **exactly the A-1a rule** (`track.rs:50-57`, `:424-430`; the defect it fixed was hard-coding 1.0, SMD 0.94 on dims 627/673/719, `STATUS.md:22-24`) — and `max_pp` for prior fills, matching `bridge._default_pp` (`bridge.py:135-146`). |
| 18 `P_HP` u16 | current HP | **K** ours / **D+grain** theirs | Ours exact. Theirs: `round(hp_fraction × maxhp_det)`, reusing `bridge.py:220` verbatim. The inverse of Showdown's `ceil(100·hp/maxhp)` rule (`track.rs:28-38`) is an **interval** of width ≈ maxhp/100, so the point estimate is a choice. Family **W-HP**; already priced at 0.558 dims/root residual (`DET_BLIND.md:280`), where quantising was *deliberately not done* so S1's residual prices it honestly. |
| 20 `P_STATUS` u8 | cartridge status byte | **K** for the class, **S** for the bits | The 6-status map is `bridge.py:105-108` / `track.rs:450-465`. But **sleep turns REMAINING live in bits 0-2** (`layout.rs:127-131`) and are hidden; what we have is `sleep_observed` (poke-env's `status_counter`). And the **EXT bit** (`layout.rs:146-150`) separates Rest-sleep from move-sleep, which poke-env conflates (`S1_S2_SCREENS.md:110`, family `sleep_rest_counter`). Family **W-SLEEP**: sample turns-left from the gen-1 sleep distribution conditioned on `sleep_observed`, once **per determinization** so `n_det` averages over it. Incidence: opponent SLP at 7.00% of roots, own 0.35%; observed-count histogram in §2.5. TOX is **V** (0 pool species). |
| 21 `P_SPECIES` u8 | dex number | **K**/**D** | B-0 proved engine species 1..151 ≡ poke-env `num` (`env.rs:129-130`). |
| 22 `P_TYPES` u8 (two nibbles, cartridge order) | types | **K** | From the engine's own table (`team.rs:95-96`). |
| 23 `P_LEVEL` u8 | level | **K**/**D** | Revealed: `mon.level`. Unrevealed: `randbats_prior.species_level` (`determinize.py:205`). |

#### `ActivePokemon` (32 bytes)

| offset | field | class | source / rule |
|---|---|---|---|
| 0 `A_STATS` 5×u16 | **MODIFIED** stats — boosts already applied (`layout.rs:296-298`) | **S — the hardest field in the bridge** | See §2.6. |
| 10 `A_SPECIES`, 11 `A_TYPES` | the active's identity | **K** | Equal to the stored record except under Transform, where the engine writes the copied species into `ActivePokemon.species` while `Pokemon.species` keeps the original (`observe.rs:24-31`). Reuse `bridge._transform_stats_override` / `_our_transform_stats_override` (`bridge.py:251-298`), which match a transformed Ditto by base-stat equality. Ditto is 1 of 146 pool species; the residual is 0.375 dims/root over 32/1600 roots (`DET_BLIND.md:281`). |
| 12 `A_BOOSTS` u32, six packed i4 | stat stages | **K** | `mon.boosts` (`harvest.py:49`). Order `atk, def, spe, spc, accuracy, evasion` (`layout.rs:59-64`) with sign extension at `layout.rs:322-326`. Gen 1 has ONE Special, so write `boosts["spa"]` (== `spd`) into `BO_SPC` — the mirror of `bridge.py:315-316`, which had to write it into *two* poke_engine slots. |
| 16 `A_VOLATILES` u64 | 18 flags + 6 packed counters | mixed | See the volatile table below. |
| 24 `A_MOVES` 4×(id, pp) | the LIVE slots | **K** ours / **D** theirs | Transform overwrites all four at 5 PP (`layout.rs:341-344`, `mechanics.zig:2461`). |

**Volatiles**, bit by bit (`layout.rs:66-93`):

| bit | flag | class | note |
|---|---|---|---|
| 0 `V_BIDE` | **V** | 0 pool species. `track.rs:330-332` already records the semi-lock rows as unreachable in `gen1randombattle`. |
| 1 `V_THRASHING` | **V** | no Thrash / Petal Dance in the pool. |
| 2 `V_MULTI_HIT` | **V/intra-turn** | never observed at a decision point. |
| 3 `V_FLINCH` | **V/intra-turn** | cleared before the next request. |
| 4 `V_CHARGING` | **K** | poke-env `preparing`; 8 pool species (Sky Attack). Its *identity* is `W-LASTMOVE`. |
| 5 `V_BINDING` | **V**, and a **transposition hazard** | 0 pool species. But note the semantics: the bit sits on the **USER** (`layout.rs:71-73`), while poke-env's `PARTIALLY_TRAPPED` sits on the **victim** and `bridge.py:87-89` maps it onto the victim's own side in poke_engine. The engine bridge must write it on the **foe's** side. Vacuous here; a live landmine for gen 4+. |
| 6 `V_INVULNERABLE` | **V** | no Fly / Dig. |
| 7 `V_CONFUSION` | **K** flag / **S** turns | flag from `Effect.CONFUSION` (0.74% of roots); `V_CONFUSION_TURNS` (bit 18, u3) is hidden (`layout.rs:209-212`). Family **W-CONF**: sample 1-4 per determinization. 5 pool species (Confuse Ray). |
| 8 `V_MIST`, 9 `V_FOCUS_ENERGY`, 12 `V_RAGE`, 13 `V_LEECH_SEED`, 14 `V_TOXIC` | **V** | 0 pool species each. |
| 10 `V_SUBSTITUTE` | **K** flag / **S** HP | `V_SUBSTITUTE_HP` (bit 40, u8) is hidden — "PS reveals only that a Substitute exists" (`layout.rs:221-224`). 22 pool species carry Substitute, but **0 of 13,702 harvest roots have one up**. Family **W-SUB**: set to `floor(maxhp/4)+1`, the value it is created with, and declare. |
| 11 `V_RECHARGING` | **K** | `must_recharge`; 5.77% opp / 1.48% own. Note `Volatiles::forced()` (`layout.rs:200-203`) is exactly PS's `trapped: true` (`track.rs:310-312`). |
| 15 `V_LIGHT_SCREEN` | **NAMED UNMODELLABLE** | poke-env 0.15 has no `Effect.LIGHT_SCREEN` (`bridge.py:16-19`, `observe.rs:54-56`). 0 pool species, so vacuous *and* unmodellable — the safest combination. Family **W-LS**. |
| 16 `V_REFLECT` | **K** | 18 pool species; 1 of 13,702 roots. |
| 17 `V_TRANSFORM` + bit 48 `V_TRANSFORM_ID` | **K** | The transform target is public (you watched it happen). |
| 21 `V_ATTACKS` (u3), 24 `V_STATE` (u16, Bide damage / overwritten accuracy) | **V** | both hidden (`layout.rs:213-220`) and both vacuous here. |
| 52 `V_DISABLE_DURATION`, 56 `V_DISABLE_MOVE` | **V** | 0 pool species carry Disable. |
| 59 `V_TOXIC_TURNS` (u5) | **VISIBLE**, **V** | `layout.rs:237-241` — it is poke-env's TOX `status_counter`. No Toxic in the pool. |

#### Not in the 384 bytes at all: the request pair

`BattleResult` is returned by `update`, not stored (`battle.rs:96-138`;
`Gen1Env` keeps it in a separate field, `env.rs:72`). A constructed root must
therefore carry `(Request, Request)` alongside its bytes. Rule **W-REQ**,
derived from poke-env:

| our active | foe active | `(req_us, req_them)` |
|---|---|---|
| alive | alive | `(Move, Move)` |
| fainted | alive | `(Switch, Pass)` |
| alive | fainted | `(Pass, Switch)` — we owe nothing; the search is never called |
| fainted | fainted | `(Switch, Switch)` |

This matches the engine's own mid-turn-faint shapes (`battle.rs:426-452`:
`0x20`, `0x80`, `0xA0`) and matches `matrix.py:24-28`'s existing rule ("On our
force_switch decisions the opponent does not act simultaneously: single 'none'
column"). It is also **self-checking**: `Battle::update` validates both choices
against `choices(p, req)` before calling the engine (`battle.rs:288-307`), so a
wrong request surfaces as an `IllegalChoice` error, never as engine UB. That is
the property `battle.rs:1-8` exists to guarantee, and the write side inherits it
for free.

#### W-VALIDATE

`from_bytes` accepts anything (`python.rs:289-297`). The write side must
validate before handing a state to `update`: both sides have ≥1 unfainted mon;
`order[0]` names a live mon; `choices()` is non-empty for both seats under
`W-REQ`; every stored move id ∈ 1..165; every species ∈ 1..151;
`hp ≤ stats.hp`. Cheap, and it converts every write-side bug into a loud error.

### 2.5 Census — measured, not assumed

**Pool census** (`rl/envs/data/gen1_randbats_sets.json`, 146 species; counts are
species carrying the move across `moves`/`essentialMoves`/`exclusiveMoves`/
`comboMoves`):

- **live:** hyperbeam 55, doubleedge 39, thunderwave 35, agility 34,
  swordsdance 29, **counter 27**, rest 25, explosion 22, substitute 22,
  reflect 18, sleeppowder 15, amnesia 11, hypnosis 9, sing 8, skyattack 8,
  recover 6, confuseray 5, mimic 5, sandattack 4, **mirrormove 4**, spore 2,
  glare 2, selfdestruct 2, softboiled 2, transform 1, lovelykiss 1,
  highjumpkick 1.
- **zero, hence vacuous:** metronome, bide, disable, rage, thrash, petaldance,
  wrap, bind, clamp, firespin, haze, lightscreen, toxic, leechseed,
  focusenergy, mist, dig, fly, solarbeam, razorwind, supersonic, psybeam,
  confusion, dizzypunch, growl, screech, stringshot.

**Harvest census** (`results/ch3_r1/harvest_s6{2,3,4,5}.pkl`, 500 episodes,
**13,702 rows**, of which 306 aliased → **13,396 non-aliased**, which is exactly
the corpus size the S1/det_blind docs use, `S1_S2_SCREENS.md:98`,
`DET_BLIND.md:64`):

| quantity | count | % of 13,702 |
|---|---:|---:|
| aliased | 306 | 2.23 |
| force_switch | 2,018 | 14.73 |
| trapped | 80 | 0.58 |
| opp active PAR or BRN | 3,340 | 24.38 |
| opp active any non-zero stat stage | 546 | 3.98 |
| **opp active (PAR\|BRN) AND a stage — W-ACTIVESTATS** | **310** | **2.26** |
| own active PAR or BRN | 797 | 5.82 |
| own active any non-zero stat stage | 1,158 | 8.45 |
| **own active (PAR\|BRN) AND a stage — W-ACTIVESTATS** | **148** | **1.08** |
| opp active asleep | 959 | 7.00 |
| own active asleep | 48 | 0.35 |
| opp active must_recharge | 790 | 5.77 |
| own active must_recharge | 203 | 1.48 |
| opp active preparing | 43 | 0.31 |
| own active preparing | 4 | 0.03 |
| opp active confused | 102 | 0.74 |
| own or opp active with Substitute | **0** | 0.00 |
| own active Reflect | 1 | 0.01 |

Opponent sleep `status_counter` histogram: 0→215, 1→321, 2→230, 3→130, 4→51,
5→11, 6→1.

Opponent active's **revealed move count**: 0 moves at 25.1% of roots, 1 at 59.5%,
2 at 13.6%, 3 at 0.4%, 4 at 1.4%. **Three quarters of the opponent's move slots
at a typical root are prior fills, not observations** — which is why the
information boundary is worth this much care.

Mean legal actions at a non-aliased root: **6.601** (median 7, max 9), over
13,396 roots. The session's own scoping quotes 6.67 on the 100M lanes; both are
consistent and the difference is corpus.

### 2.6 W-ACTIVESTATS — the hardest field, stated honestly

`ActivePokemon.stats` holds the **modified** stats and is **path-dependent**.
Three facts from the vendored engine:

1. `switchIn` sets `active.stats = incoming.stats` (`mechanics.zig:243`) then
   applies `statusModify` (`mechanics.zig:250`).
2. A boost recomputes from `unmodifiedStats` — the **stored** stats — and does
   **not** re-apply the boosting side's own status modifier
   (`mechanics.zig:2508-2510, 2528-2529, 2545-2546, 2565-2566`). This is gen 1's
   famous "Agility cures the paralysis speed drop" glitch, faithfully modelled.
   The engine's own comment at the end of `boost` labels it: *"GLITCH: Stat
   modification errors glitch"* (`mechanics.zig:2580-2581`).
3. Paralysis and burn, when they *land*, divide the **already-modified** active
   stat (`mechanics.zig:2229-2230, 2251-2252, 1862`), while a cure recomputes
   from the stored stat and thereby **discards** any boost
   (`mechanics.zig:1572-1575`).

Consequence: `(stored stats, boost stages, status)` does **not** determine
`active.stats`. Agility-then-Thunder-Wave gives `spe = stored·2/4`;
Thunder-Wave-then-Agility gives `spe = stored·2`. Both states have **identical
public descriptions** and differ by 4× in the field that decides turn order.

This is not a regression against the current line — `bridge.py:308-320` hands
poke_engine stages and status separately and lets it apply its own model, which
has the same ambiguity — but the engine makes it visible, so it must be declared.

**Rule W-ACTIVESTATS (proposed):** `active.stats.X = min(999, floor(stored.X ·
num/den))` using the engine's own `BOOSTS` table (`mechanics.zig:34-48`, ported
as data, not re-derived), then `statusModify` (PAR → `max(spe/4, 1)`, BRN →
`max(atk/2, 1)`; `mechanics.zig:2698-2703`). This is **exact** when there are no
boosts (it is then literally `switchIn`'s output) and **exact** when there is no
PAR/BRN. It is wrong only on the intersection, measured at **2.26% of roots
(opponent) and 1.08% (own)**.

**Upgrade path, named and not taken in Phase 1:** the ordering *is* observable —
the client saw `|-boost|` and `|-status|` in order — poke-env simply does not
retain it. A live agent could track it in its own bookkeeping. The harvest
cannot, so R1-E would have to declare it either way. Recommend: declare in
Phase 1, revisit only if the P0 sensitivity read says turn order flips matter.

One mitigation that limits the blast radius: the **encoder** does not read
`active.stats`. `_spe_est` derives speed from base stats, level, the boost stage
and the PAR flag (`encoder.rs:101-118`), so the observation is unaffected. Only
the engine's turn order and damage see it.

---

## 3. Tracker init — `SideTracker::from_root`, and gate **R1-E**

### 3.1 What must be initialised

`BattleTracker` is `#[derive(Default)]` over two private `SideTracker`s
(`track.rs:164-168`), and every `SideTracker` field is private with no setter
(`track.rs:41-84`). **Not found:** any constructor other than `Default`. So this
is new API.

Two groups of fields, and both matter:

**(a) Observable history — filled from `battle1`:**

| field | line | our side | opponent side |
|---|---|---|---|
| `reveal_order` / `revealed` | `track.rs:44-46` | needed only by the foe's own observation (the privileged path) | **the operative one.** poke-env's `opponent_team` is insertion-ordered by reveal (`shadow_battle.py:141-152` depends on exactly this; `harvest.py:59, 65-66` preserves it) |
| `revealed_moves` | `:48` | ours are all "revealed" trivially | `mon.moves` keys in order, mapped to engine ids |
| `move_uses` | `:50-58` | — | `max_pp − mon.moves[mid].current_pp`, the A-1a rule |
| `sleep_observed` | `:59-61` | `status_counter` when SLP | `status_counter` when SLP |
| `flags_before_faint` | `:71-80` | `(must_recharge, preparing)` | `(must_recharge, preparing)` |
| `binding_victim_turns` / `binding_last_turn` | `:65-69` | 0 (vacuous, §2.5) | 0 |

**(b) Diff state — seeded from the CONSTRUCTED battle, not from history:**
`prev_status[6]`, `prev_active_party`, `prev_live_moves[4]`, `prev_charging`,
`prev_transform`, `started` (`track.rs:62-64, 81-83`). If these are left at
`Default`, the first `observe()` after the root will spuriously re-reveal, count
a phantom PP spend, or reset a sleep counter. Seeding them is mechanical:
snapshot the constructed bytes and set `started = true`.

**Proposed API.**

```rust
// track.rs
pub struct RootReveal {                 // one per side, filled from battle1
    pub reveal_order:   Vec<u8>,        // party indices, first-switch-in order
    pub revealed_moves: [Vec<u8>; 6],   // engine move ids, usage order
    pub move_uses:      [Vec<u8>; 6],   // observed PP spends, aligned
    pub sleep_observed: [u8; 6],
    pub flags_before_faint: [(bool, bool); 6],
    pub binding_victim_turns: u8,
}
impl BattleTracker {
    pub fn from_root(b: &Battle, p1: &RootReveal, p2: &RootReveal) -> BattleTracker;
}
```

**A simplification worth taking.** We choose the constructed party order, so put
the opponent's revealed mons at party indices `0..n_revealed` in reveal order and
the determinized bench after. Then `reveal_order == [0, 1, …, n-1]` and
`foe_seat`'s `seat.team[slot]` ordering (`track.rs:399-415`) is poke-env's by
construction. Safe because opponent actions are chosen by move id / species, and
because `slot_of_party_index` handles the order indirection (`layout.rs:377-383`).

### 3.2 Gate **R1-E** (Root Init, Engine)

**Claim under test.** Encoding a constructed root through the Rust encoder
reproduces the LIVE root observation bitwise outside the declared families.

**Corpus.**
- **Leg A oracle:** the **13,396 non-aliased roots** in
  `results/ch3_r1/harvest_s6{2,3,4,5}.pkl`, comparing against `row["obs"]` — the
  vector the policy actually acted on, and already known to survive
  freeze/rehydrate bit-identically (`scripts/ch3_harvest.py:152-155`).
- **Plus a fresh 100M-lane harvest.** The R1 harvest is a D26/12M-era object; the
  state distribution the search will actually see is the 100M lanes'
  (`configs/eval/search_s3_100m.yaml:126-129`). Same recorder, same assert,
  ≥ 3,000 roots per lane × 3 lanes. **This is not optional**: a write-side bridge
  graded only on 12M-era states is graded on the wrong distribution.

**Pass rule.** Every differing dim must fall in a **declared family**, and an
undeclared dim is a **BUG, not a family** — the rule
`scripts/engine_p1_run.py:127-129` already enforces. Report, per family, dims per
root and max |Δ|, in the shape `DET_BLIND.md:41-66` already established.

**Proposed bar**, calibrated against the det_blind residual (0.945 dims/root,
47.5% of roots bit-identical, `DET_BLIND.md:274-275`):

- total ≤ **1.5 dims/root** and ≥ **40%** of roots bit-identical;
- **W-HP** ≤ 0.60 dims/root, max |Δ| ≤ 0.01 (matching `DET_BLIND.md:280`'s
  0.558 / 0.0023);
- **W-STATS**, **W-SLEEP**, **W-CONF**, **W-SUB**, **W-LASTDMG**,
  **W-LASTMOVE**, **W-ACTIVESTATS**, **W-LS**, transformed-Ditto: enumerated with
  dims and incidence;
- **W-ORDER**, **W-SEED**: must contribute **zero** dims. If they do not, the
  claim that they are free is false.

**Leg B — the foe seat (the privileged block).** There is no harvested foe
observation, so there is no external oracle. The check is the **cross-seat
agreement** property `tracker_properties.rs:9-12` already uses ("Two seats derive
the same public facts by different code paths… a side-index swap or a
reveal-order/party-index confusion shows up as a disagreement"), plus the value
test the privileged proposal owes anyway
(`docs/proposals/privileged_critic_engine_route.md:215-230`,
`test_engine_privileged_block_is_the_python_block`). Disclose it as an
internal-consistency check, never as parity.

**Leg C — mask parity, and it is the cheapest strong gate here.** The obs
comparison cannot see `order`, the `forced()` set, PP>0, or fainted-ness. Compare
`mask_for(constructed, us, req, aliased)` (`env.rs:167-173`, derived from the
engine's own `choices()`) against the harvested `row["mask"]`.
**Target: 100% exact on all 13,396 non-aliased roots**, with aliased roots the
declared exception (`env.rs:90-95`). This is an *external* oracle for the half of
the state the observation does not expose, and it costs one comparison.

### 3.3 Positive controls — mutations that MUST break it

Modelled on `scripts/engine_p1_run.py:151-160` (`--mutate`, whose whole purpose
is that "a gate that still reports 0 mismatches is blind") and on
`DET_BLIND.md:157-160`'s `test_as_is_root_fails_the_same_parity_check` ("without
that control the parity test measures nothing").

| id | mutation | must move |
|---|---|---|
| **C1** | swap two entries of the opponent's `reveal_order` | the opp mon blocks `[404..608)` and the id suffix `[814..820)` |
| **C2** | zero `move_uses` (i.e. re-introduce the A-1a defect exactly) | dims **627 / 673 / 719** (the pp slots), SMD ≈ 0.94 (`STATUS.md:22-24`) |
| **C3** | `sleep_observed` off by one | `status_counter` at `[622]` |
| **C4** | drop `flags_before_faint` | the recharging / preparing dims on the **2,018 force-switch roots** |
| **C5** | **the as-is control** — initialise with every opponent party slot revealed | ≈ **35.9 dims/root** (`DET_BLIND.md:61`), reproducing S1's artefact. The strongest control: it proves R1-E measures the *boundary*, not the plumbing |
| **C6** | flip the sign of a negative boost (break the i4 sign extension at `layout.rs:322-326`) | the boost block at `[204..211)` / `[608..615)` |
| **C7** | write HP with `floor` instead of `round` | must move **inside** W-HP and still be caught by W-HP's max-\|Δ\| bound — a control that lands in a family and is still bounded |

A control that does **not** break the gate is a finding about the gate, and it is
reported as one.

---

## 4. The batched leaf path

### 4.1 The entry point

**Not found** today: any way to encode arbitrary `Battle` bytes as seat X.
`Tables::encode` takes an `ObservableState` **dict** (`pyencode.rs:169-178`);
`Gen1Env::pending` encodes from a live env (`env.rs:224-240`). Neither serves a
search.

Proposed, on `BatchEnv`'s pattern (GIL released, ragged output refused,
`pyencode.rs:302-328, 403-421`):

```
SearchNode(root_bytes: bytes,
           req: (str, str),
           tracker: RootTracker,          # opaque handle from from_root()
           tables: Tables,
           seat: str)                     # the acting seat

SearchNode.expand(
    cells: list[(row_action: int, col_action: int, det: int, n_chance: int)],
    seed_base: int,                       # CRN-1: no row in the key
    privileged: bool,
) -> (obs        f32[N, 828],
      priv       f32[N, 408] | None,
      terminal   i8[N],                   # 0 none, +1 win, -1 loss, 2 tie
      weight     f32[N],                  # 1/n_chance within a cell
      cell       i32[N],                  # index back into `cells`
      req_next   i8[N, 2],
      child      bytes | None)            # only when depth-2 needs to recurse
```

Per row, Rust does: `clone_into` (384-byte memcpy, `battle.rs:253-256`) → write
the CRN seed at `B_RNG` → `update` (validated, `battle.rs:288-307`) →
`tracker.observe` (`track.rs:177-293`) → `state_for(seat, req)`
(`track.rs:296-349`) → `encode` (`encoder.rs:254-364`); and, when `privileged`,
additionally `state_for(foe, req)` → `encode` → `privileged_block`
(`encoder.rs:77-85`) — **exactly the training-time construction at
`env.rs:295-302`**, so train and search semantics cannot drift.

`det_blind` is not a parameter here. The tracker's `foe_seat` path
(`track.rs:394-438`) applies the boundary; the tracker's `own_seat` path
(`track.rs:352-391`) supplies the full-information half. **det_blind by
construction** (invariant L-BOUNDARY, §1.3).

**The 408-block's foe half.** The privileged block is defined as a slice of a
full 828 encode of the **opponent seat's own view** (`encoder.rs:56-85`,
`PRIV_OWN_END == 404`, `PRIV_DIM == 408`, pinned at compile time
`encoder.rs:74-75`). Under determinization the constructed `Battle` contains a
**complete** opponent team, so `state_for(foe, …)` runs the foe's `own_seat`
path and returns exactly the observable state the foe's own client would have:
exact HP (`track.rs:370`), exact status, exact PP (`track.rs:376-389`), all six
party slots. Encode 828, slice 408. **Disclosure owed** (proposal R4,
`privileged_critic_engine_route.md:482-495`): at training time that block is the
TRUE seat-2 state; at search time it is the RSD-sampled one, and the sampled
bench is systematically *fresher* — max PP, full HP, no status. Averaged over
`n_det`, never eliminated.

Python then runs **one** critic forward over the whole `(N, 828)` (or
`(N, 1236)` = `cat([obs, priv])`, the shape `ppo.py:1030-1042` already builds)
and the BR solve in numpy, unchanged from `matrix.py:265-275`.

**Threading.** Single-threaded Rust; torch keeps its own threads for the critic.
The Rust leaf path is ~0.2 s of a ~0.35 s depth-2 decision — not worth a new
crate dependency (the crate today has three: pyo3, numpy, serde_json;
`engine/pkmn_gen1/Cargo.toml:21-37`).

### 4.2 Cost model

Constants. Engine + tracker + encoder, batched: **5.7 µs/row**. Rust encoder
alone: **0.70 µs/row**. `clone + update` from Python: **0.243 µs**. Critic
forward: **1.1–1.5 µs/leaf at 4 threads**. Today's poke_engine stack:
**212 µs/leaf all-in at dose M**, of which **116 µs is
`shadow_battle` + `embed_battle`**. *(All measured this session's scoping;
**not found** in any committed file — quote them as session measurements. The
committed anchors are `STATUS.md:50` — "~0.17 s/decision PROJECTED on
pkmn/engine; today's stack 5 s" — and `S1_S2_SCREENS.md:154`, clean-box 65-68 ms
at M / 253-269 ms at L.)*

**Depth-1, dose M**, at the measured 350.7725 leaves/decision
(`DET_BLIND.md:118-119, 251`):

| term | today | engine |
|---|---:|---:|
| transition + leaf encode | 350.8 × 116 µs = 40.7 ms | 350.8 × 5.7 µs = **2.0 ms** |
| critic | included in the 212 µs | 350.8 × 1.2 µs = **0.4 ms** |
| everything else | balance of 350.8 × 212 µs = 74.4 ms | one PyO3 call + numpy BR ≈ **1-2 ms** |
| **total** | **~74 ms** (clean-box measured 65-68 ms) | **~4 ms** |

That is ~**17× at matched leaf count**. But matched leaf count is **not matched
decision quality** — see §1.2. If P0 finds that `S ≈ 30` samples per cell are
needed to bring `sd(margin)` under `0.2 × median(margin)`, the honest depth-1
number is ~3,300 leaves → ~19 ms engine + ~4 ms critic ≈ **25 ms**, i.e.
**~2.6-3×**, not 17×. **State the 3× until P0 says otherwise.** This is the
argument for keeping poke_engine at depth 1 and is the first thing a reviewer
will ask.

**Depth-2.** The session's scoping puts the naive blowup at **75.4×** depth-1's
leaves (rows 6.67 × cols 4.19 × 2.7 retained branches), i.e.
350.8 × 75.4 ≈ **26,450 leaves/decision**:

| term | value |
|---|---:|
| engine + tracker + encoder | 26,450 × 5.7 µs = **151 ms** |
| critic | 26,450 × 1.2 µs = **32 ms** |
| oppact head at children (~351 child nodes, batched) | < **1 ms** |
| Python / numpy | **5-10 ms** |
| **total** | **~0.19 s/decision** |

Consistent with `STATUS.md:50`'s ~0.17 s projection, and **26× under the ≤ 5 s
cap** — which is precisely the headroom that buys chance samples. With
`S = S' = 16` the same tree costs roughly **1.4 s**, still inside the cap. On
today's stack the same tree is 26,450 × 212 µs = **5.6 s**, over the cap by
itself, before any second encode.

**Memory.** 828 floats × 4 B = **3.31 KB/leaf**. 26,450 leaves = **87.6 MB** if
materialised, **130.8 MB** with the 408-block. **The path must stream.** Chunk at
4,096 rows (13.6 MB obs, +6.7 MB priv = 20.3 MB), one critic forward per chunk,
accumulate `ev_cell` incrementally exactly as `matrix.py:266-269` does. This is a
real constraint, not a footnote: the R2 landmine about resource gates being
calibrated at a fleet width (`CLAUDE.md`, Landmines) applies — a 131 MB
per-decision spike inside a seven-wide eval fleet is a different object than the
same spike alone, and at `S = S' = 16` the unchunked figure would be ~1 GB.

**The privileged evaluator's marginal cost** is one extra `state_for` + `encode`
per leaf ≈ **+0.7 µs encode plus tracker work**; budget **1.5× the base leaf
cost** until T-2 measures it. On today's stack the same thing was
5 s → 7.75 s and **breached the cap**
(`privileged_critic_engine_route.md:568-578`, R3 at `:684-689`, "the search seam
should wait for the Rust leaf encoder"). **This design is what unblocks it.**

---

## 5. The depth-2 solve

### 5.1 Definition

Let `I` be the root information set; `d = 1..D` the RSD determinizations
(shared across every cell, MF-13, `matrix.py:34-37`); `A` our legal rows;
`C` the realised L6 columns with weights `q̃` (the oppact posterior renormalised
over realised classes, `matrix.py:184-186`; `OTHER_MOVE` is never simulated and
its mass is recorded, `matrix.py:11-14`).

For each `(a, c, d)` and chance sample `s = 1..S`, the child is
`x(a,c,d,s) = update(state(d), a, c; seed(decision, c, d, s))` — **no `a` in the
seed** (CRN-1).

```
V2(a,c,d,s) = terminal(x)                       if x is terminal      # matrix.py:117-130, ±1 / 0
            = max_{a' ∈ A'(x)}  Σ_{c'} q̃'(c'|x) · (1/S') Σ_{s'} v(leaf(a',c',d,s'))   otherwise

EV(a,c)     = (1/D) Σ_d (1/S) Σ_s V2(a,c,d,s)          # matrix.py:269's mean over dets
row_ev(a)   = Σ_c q̃(c) · EV(a,c)                       # matrix.py:270
choice      = argmax row_ev, ties → policy prior → lowest index    # matrix.py:271-275, D3/D4
```

**`q̃'` at the child** is the oppact head run on **our** observation at `x` —
which the tracker already produces at the leaf, at the root's information
boundary. One extra forward per **child node**, not per leaf — and under the
75.4x framing a child node is exactly a depth-1 leaf, so that is **~351**
forwards per decision, batched, sub-millisecond. Purity is intact: our own head, our own
observation, no seat-2 read.

**The determinization does not resample at the child.** `d` is a sample from the
root belief and a rollout does not get a new world. Stated so nobody "improves"
it later; re-sampling inside a rollout would double-count the prior.

### 5.2 The operator, and its known optimism

`max` at both plies is **best response to a fixed opponent model**, not a Nash
solve. That is already what depth-1 does (`matrix.py:270-275`). Applied
recursively it inherits a bias that **grows with depth**: at the second ply we
implicitly get to see the opponent's mixture before choosing, which
over-estimates our value. That is a second optimism on top of the one the design
already declares (uniform switch targets, `matrix.py:13-19`, "systematically
OPTIMISTIC about our staying in").

**Alternative worth pre-registering as a secondary arm:** child value = the Nash
value of the child's own 7x5 matrix. ~351 tiny matrix games per decision; a
fictitious-play or small LP solve is single-digit milliseconds total, i.e.
affordable. **Recommendation:** default to BR-vs-`q̃'` (it keeps the root
operator matched, so Form B is a strict extension of Form A), and register
Nash-at-child as one pre-declared secondary. Do not decide it after seeing the
numbers.

### 5.3 Caps, pruning, and the pre-pass

**Caps.** Extend the frozen-dose pattern (`matrix.py:69-83`):

```
Dose2(n_det, root_k, n_chance_root, child_k, n_chance_child, node_cap)
```

`node_cap` keeps the **RAISE** semantics — `SearchWatchdogError`,
never a silent fallback to the policy (`matrix.py:65-67, 240-245`,
DO-NOT-BUILD #16). A depth-2 watchdog that quietly degrades to depth-1 would
make the JOURNEY 11.5 comparison meaningless.

**Top-k at the root: use a depth-1 pre-pass, not the policy prior.** A full
depth-1 solve costs ~4 ms on the engine (§4.2) — 2% of the depth-2 budget — and
ranks rows far better than the prior. Take the top-`root_k` rows by depth-1
`row_ev`, expand only those to depth 2. Three benefits:

1. Better pruning than a prior-based cut.
2. **The depth-1 answer comes out for free as the paired control**, so JOURNEY
   11.5's comparison is paired at the *decision* level on the same
   determinizations, the same `q`, the same battle — the tightest possible
   design for that read.
3. The retained-mass question becomes measurable rather than assumed: report the
   fraction of decisions where the depth-2 winner was outside the depth-1
   top-`root_k`, offline on the harvest, at `root_k ∈ {3, 4, 6, all}`. Publish
   that curve before choosing `root_k`; it is a **measurement**, not a
   calibration knob.

`child_k` prunes the child's rows the same way, by the child's own policy prior
(a second pre-pass at every child is not affordable).

### 5.4 What "decisions/sec" reporting the exit condition needs

JOURNEY 11.5 requires decisions/sec for **both** arms. Two landmines govern how:

- **Contention invalidates it.** `S1_S2_SCREENS.md:152-159`: "Timing is CONTENDED
  and descriptive, never a budget number… 430.3 ms/decision at M against R3's
  clean-box 65-68 ms — 6.3-6.6× inflated by contention."
  `DET_BLIND.md:182-185` repeats it. So the JOURNEY 11.5 timing leg **must** run
  on an idle box, one process, fleet down, and the box state must be disclosed
  in the readout.
- **A window that straddles startup invents records** (`CLAUDE.md`, Landmines).
  Use a conforming window.

**Protocol:** the two arms interleaved **ABBA** in one session, as the A/B
speedup measurement did (`docs/engine_port/SPEEDUP.md`); report
`search/ms_mean`, `search/ms_p50`, `search/ms_p99`, `search/leaves_mean`
(the counters `scripts/ch3_eval.py:170-173` already emits) plus decisions/sec and
the torch thread count. **Leaves must be reported alongside**, because leaves is
the contention-insensitive quantity (`DET_BLIND.md:184-185`) and it is what makes
a timing number auditable later.

---

## 6. Purity and disclosures

### 6.1 Purity

Everything in both forms is **our own heads plus the engine as a transition
function**. Specifically:

- Policy (actor), critic, oppact head — all from one checkpoint.
  `SearchAgent.__init__` hard-asserts the oppact head
  (`rl/search/agent.py:83-85`; note `STATUS.md:40` and
  `privileged_critic_engine_route.md:604` both still cite the pre-`det_blind`
  line `:68`, which is now docstring prose).
- The determinization is RSD over the **vendored public generator statistics**
  (`determinize.py:1-32`; `randbats_prior` is a byte copy of
  `showdown/data/random-battles/gen1/data.json`, `randbats_prior.py:38-44`).
  Nothing is fitted or trained (`determinize.py:6-8`).
- FG-4 stays armed: `battle_to_state` asserts RSD provenance on every opponent
  spec (`bridge.py:366-372`), and the engine write side must carry the identical
  assert. `scripts/ch3_eval.py`'s `_Battle2Sentinel` raises `PurityIncident` when
  `battle2` is read from any `rl/search` frame — keep it, and name it in the
  pre-reg so nobody takes the shortcut
  (`privileged_critic_engine_route.md:556-566`).
- **Foul Play appears only as an opponent in evals.** Never as a teacher, never
  as a leaf evaluator, never as a determinizer. JOURNEY 14 is explicit that FP
  distillation is the LAST rung, a charter change, needing its own ruling
  (`JOURNEY.md:180-184`).

### 6.2 What a searched ladder object carries

| component | required? | source |
|---|---|---|
| actor (policy) | yes | the checkpoint |
| critic | yes | the checkpoint |
| oppact head (`aux_head`) | **yes — the search cannot run without it** | `agent.py:83-85` |
| privileged evaluator head | optional | design B, `privileged_critic_engine_route.md:517-526` |
| RSD determinizer + vendored set statistics | yes | `determinize.py`, `randbats_prior` |
| the engine build fingerprint | yes | `pkmn_gen1.build_info()` (`python.rs:72-91`) — engine sha, zig version, `{showdown, log, chance, calc}` |

**Dependency status, checked against the tree at the time of writing.** The
`TypeError` in `rl/agents/ppo.py` that refused `aux_oppact_coef` together with
`privileged_dim` — the pair a searched privileged object needs — **has already
been lifted**, in the **uncommitted working tree**, on 2026-09-10. The code now
carries the reasoning in place of the guard (`rl/agents/ppo.py:478-503`): "NO
privileged_dim REFUSAL HERE. There was one until 2026-09-10; it protected
nothing structural and it was ARM-SCOPED, not an invariant… The two levers touch
DISJOINT tensors… ONE RESIDUE, DISCLOSED RATHER THAN FIXED: privileged_dim
changes the ACTOR'S INITIAL WEIGHTS at a fixed seed… Disclose, do not reorder."

In the same uncommitted tree, **design B exists**: `priv_eval_coef` /
`priv_eval_max_grad_norm` build a separate `EntityDeepSetsNet` value head
(`rl/agents/ppo.py:323-324, 537-559, 641-664, 765`), with a smoke config at
`configs/engine_a1_priveval_smoke.yaml`. Two things follow that this design must
carry:

- **B rides on top of A structurally, not instead of it.** `priv_eval_coef`
  requires `privileged_dim > 0` (`ppo.py:539-543`), and `privileged_dim` both
  emits the block *and* widens the ordinary critic. The smoke config says so in
  its own header: "a lane running this file is design A + design B, NOT a
  narrow-critic control plus an evaluator head." **The A-vs-B ruling is
  therefore still owed** — B as built does not avoid D18's advantage-channel
  hazard, because A is underneath it.
- Nothing above is committed. Re-check `git status` before citing any of it in a
  pre-reg.

### 6.3 The per-decision budget

**Proposed cap: ≤ 5 s/decision** for a searched ladder object
(`STATUS.md:43-44`, still listed as a ruling owed). Two constraints on it:

- The ladder's tight path is **150 s/turn**, not the 300 s a challenge gets
  (`CLAUDE.md`, Landmines). At ~27 searchable decisions per battle
  (`S1_S2_SCREENS.md:249-255` measures **26.79**), 5 s/decision is well inside a
  per-turn budget but the cap is per **decision**, and a force-switch plus a move
  in one turn is two decisions.
- JOURNEY 14 item 1 is that the budget is **unspent**: depth-1 at 20 ms is
  0.013% of 150 s, while FP@500 beats us on 0.33%
  (`JOURNEY.md:166-170`). Depth-2 at ~0.2 s is 0.13% — still an order of
  magnitude under FP@500's share. That is a finding in itself and should be
  reported with the first depth-2 number.

### 6.4 Disclosures that travel with every number from this line

1. **Chance is SAMPLED, not enumerated.** The pinned build is
   `-Dchance=false -Dcalc=false` (`build.rs:218-219`) and `ffi.rs:59-64` refuses
   anything else. Name `S` (samples per cell) and whether CRN-1 was on in every
   quote. `PKMN_ENGINE_RUST_PLAN.md:1212-1218` and `JOURNEY.md:131` say the
   opposite and are corrected by `STATUS.md:50-51`.
2. **HP grain.** The opponent's HP is inverted from a percentage; the true value
   lies in an interval of width ≈ maxhp/100. Family W-HP, 0.558 dims/root at the
   root (`DET_BLIND.md:280`).
3. **The determinization prior.** RSD from the public generator statistics; the
   determinizer's own error is untouched by any of this
   (`DET_BLIND.md:304-309`).
4. **W-ACTIVESTATS.** `ActivePokemon.stats` is path-dependent in the engine and
   the public view cannot recover the path; the declared rule is wrong on
   2.26% (opp) / 1.08% (own) of roots (§2.6).
5. **The privileged block at a search leaf is the DETERMINIZED opponent, not the
   true one** — a distribution shift against training, averaged over `n_det`,
   never eliminated (`privileged_critic_engine_route.md:482-495`).
6. **Depth-2's BR-vs-`q̃'` operator is optimistically biased and the bias grows
   with depth** (§5.2), on top of the already-declared switch-in optimism
   (`matrix.py:13-19`).
7. **Every FP number carries its two standing disclosures forever** — weakly
   powered equivalence test, point estimate flatters us — and names its budget
   (`CLAUDE.md`, Anchor battery).
8. **Timing numbers name the box state.** Contended timings are descriptive only
   (`S1_S2_SCREENS.md:152-159`).

---

## 7. Build plan, with a time-box

Effort is in **evening blocks** (the maintainer's session unit). The overall
time-box follows the precedent already set for JOURNEY 7.5: *parity time-boxed,
keep-the-server branch pre-decided.*

### Phase 0 — calibration and de-risking. **1 block.**

No new production code. Four offline measurements, all read-only, all from the
harvest:

- **σ-margin calibration** (§1.2): `sd(top1 − top2)` vs `S ∈ {1,2,4,8,16,32}`,
  with and without CRN-1, ~200 roots. *(Needs a minimal engine rollout, so
  strictly it follows a spike of Phase 1's write side — run it on a stubbed
  subset: no-status, no-boost, no-transform roots, where the write side is
  provably exact and W-ACTIVESTATS cannot contaminate the read.)*
- **Top-k retained mass** (§5.3) at `root_k ∈ {3,4,6,all}` using the existing
  poke_engine depth-1 solve.
- **W-ACTIVESTATS incidence** — **done** (§2.5: 2.26% / 1.08%).
- **`last_selected_move` availability in poke-env 0.15** — does the live
  `Pokemon` expose the preparing/last move by identity? If yes, W-LASTMOVE is
  harvest-only and shrinks.

**Stop rule.** If σ-margin at `S = 32` with CRN-1 still exceeds
`0.5 × median(margin)`, sampled chance cannot resolve a decision at any
affordable dose and **Form B does not get built**. Form A proceeds regardless
(it does not need sampling to beat exact enumeration — it needs the write side).

### Phase 1 — write-side bridge + tracker init + gate R1-E. **3-4 blocks.**

Mutable layout writers, the `battle1 + det → 384 bytes` builder, `W-VALIDATE`,
`RootReveal` / `BattleTracker::from_root`, R1-E legs A/B/C, controls C1-C7, a
fresh 100M-lane harvest.

**Time-box: 4 blocks.** **Pre-decided failure branch:** if R1-E has not passed
its bar at 4 blocks, do **not** extend and do **not** loosen the families
silently. Drop to the **reduced-fidelity root**: accept W-ACTIVESTATS and
W-LASTDMG as unmodelled defaults, widen the declared families to match, and
re-grade the whole line on **decision-level agreement with the poke_engine path**
(Phase 2's target) instead of bitwise obs parity. That is a weaker claim, it must
be stated as one, and it must be stated *before* the numbers.

**Stop rule.** R1-E leg C (mask parity) below 99.5% is a **hard stop**: it means
the constructed state does not offer the actions the real one offered, and every
downstream number is about a different game.

### Phase 2 — batched leaf path + Form A + like-for-like parity. **2-3 blocks.**

`SearchNode.expand`, the chunked streaming path, the Python wiring in
`solve_decision`, and the parity read:

**Target: decision-level agreement between engine-depth-1 and
`det_blind`-on-poke_engine on the 13,396 harvest roots.** Both arms share
determinizations (same `decision_rng`), so the only difference is the simulator.
Propose **≥ 90% argmax agreement**, with every disagreement's margin reported —
the shape `DET_BLIND.md:234-255` used for the 11.4% flip analysis, where flips
concentrated on close calls (mean margin 0.0121 at a flip vs 0.0560 at a
non-flip). Below 85%, the simulators disagree about the *game*, not about noise,
and Phase 3 does not start until that is explained.

Then the timing leg: ABBA, clean box, decisions/sec + leaves (§5.4).

### Phase 3 — depth-2 + the budget-ladder harness. **2-3 blocks.**

The recursive solve, `Dose2` with a raising watchdog, the depth-1 pre-pass and
its free paired control, `q̃'` at children, the budget ladder
(a `configs/eval/fp_budget_ladder.yaml`-shaped sweep over per-decision budget:
20 ms / 200 ms / 1 s / 5 s), and the JOURNEY 11.5 readout.

**Stop rule.** JOURNEY 11.5 is explicit: one comparison, then the chapter closes;
credits at acceptable cost → MCTS in gen 9; doesn't credit → the MCTS question
closes permanently (`JOURNEY.md:133-137`). **No depth-3 under any branch.**

### Total: **8-11 blocks.**

### The reordering rule for tonight's screens

**Where the read lands:** `docs/search_relook/S3_READOUT.md`, machine-written by
`scripts/search_s3_readout.py`. At the time of writing every cell — P-M, P-B,
P-BA, P-E — is **PENDING**, correctly refusing to read on partial data (S3M
23/30 chunks, S3B 6/30, A1E 0/30). The partial per-lane rates printed there are
running pooled rates and are **never** cell inputs; do not use them to pick a
branch below. Take the branch from the readout's cells when they fill.

**S3B (the online `det_blind` arm) reading FLAT or NEG does NOT stop the write-
side bridge, but it reorders Phase 3 behind the evaluator.** `DET_BLIND.md:376-383`
pre-states exactly this: a null on `delta_B` "says the encoding artefact was
**not** the binding defect — the search is limited by the EVALUATOR itself, not
by what the evaluator is being shown… It would NOT license depth."

So, pre-decided:

| S3B / F3B112 read | consequence for this design |
|---|---|
| **POS** | Form A is the direct beneficiary; build Phases 1-2 and go straight to Phase 3. |
| **FLAT** | Phases 0-2 unchanged. **Phase 3 waits behind the privileged evaluator** (design B), which Phase 2's cost model makes affordable for the first time. |
| **NEG** | Phases 0-2 unchanged — the write-side bridge is JOURNEY 14's precondition and JOURNEY 7.5's own deliverable regardless of what depth-1 scores. **Phase 3 is deferred until an evaluator arm has credited**, and the JOURNEY 11.5 comparison runs on the *evaluator-improved* object, not on the current one. |

The asymmetry is deliberate: the write-side bridge is a **capability** JOURNEY
14 names as a precondition (`JOURNEY.md:186-189`), so no depth-1 result retires
it. Depth-2 is a **hypothesis**, and a null on the evaluator's input routes
straight to the evaluator.

---

## 8. Open questions for the maintainer

**Q1. Does the write-side bridge ship inside JOURNEY 7.5, or after its exit?**
7.5 closes on the A-1 re-run (`STATUS.md:25`), and JOURNEY 14 asks for the
state-copy surface "in the collector even before anything uses it"
(`JOURNEY.md:189`). **Recommendation: after 7.5 exits, as its own item.** 7.5's
gates are about the collector's fidelity; adding a write side mid-gate widens the
object A-1 graded. But keep it as the *first* thing after, because it is
JOURNEY 14's stated precondition and because Phase 1 is the long pole.

**Q2. Design A or design B — and note that as built today it is A+B, not B.**
Owed already (`privileged_critic_engine_route.md:762-767`, `STATUS.md:42`), and
the working tree's `priv_eval_coef` requires `privileged_dim > 0`
(`ppo.py:539-543`), so a design-B lane is a design-A lane with a head on top.
**Recommendation: B, and separate it from A** — i.e. add the ability to emit the
408-block and train the evaluator head **without** widening the ordinary critic.
Two reasons, one of which this design adds to the record:

- Under L-BOUNDARY (§1.3), the leaf's two halves carry *different* information
  sets. Only a **separate** head can be trained on a contract where the
  408-block is always fully populated, which is what makes feeding it a
  determinized team in-distribution.
- A widened ordinary critic is also the head producing advantages — exactly the
  channel D18's falsifier fires on ("EV rose on EVERY lane… while win rate
  stayed flat"; `privileged_critic_engine_route.md:674-682`). Shipping A+B means
  the monster's arm B carries that hazard *and* the evaluator, and a null
  cannot be attributed to either.

If separating them is more than a small change, the fallback is to run A+B and
**pre-register the confound as unresolvable in that arm** rather than to let it
pass unnamed.

**Q3. But B as written does not satisfy JOURNEY 14 item 2.** JOURNEY 14
(`:171-174`) asks for "a critic trained AS AN EVALUATOR… Search needs accurate
values on HYPOTHETICAL states it has never played… nothing in this project has
ever trained for the second one." Design B trains its head "on the same returns"
(`privileged_critic_engine_route.md:519-521`) — same on-policy value objective,
wider input. **The gap between "privileged input" and "trained as an evaluator"
is unclosed in both documents.** *Recommendation:* name the gap in the monster
pre-reg, ship B as-is (it is the cheap, safe half), and register the actual
evaluator objective — value regression on **off-policy / search-visited** states
— as a separate, later entry. Do not let B's name imply it closed item 2.

**Q4. The `ppo.py` guard — ALREADY LIFTED, uncommitted; confirm the disclosure
rides with it.** As of the working tree at the time of writing, the refusal is
gone and the actor-init residue is disclosed in place (`ppo.py:478-503`). Nothing
is asked of the maintainer here except: **the R1 disclosure must appear in the
monster's pre-reg header, not only in a code comment.** `privileged_dim` moves
the RNG stream and changes the actor's *initial weights* at a fixed seed (actor
param sum 334.851 → 410.510, count unchanged at 626,059;
`tests/test_entity_trunk_gen4.py:194-199`), so two arms differing in
`privileged_dim` are **not paired at initialisation even at the same seed** —
which is exactly the pairing IDEAS 2.2 assumes. Do not "fix" it by reordering
construction: that breaks `_GEN1_PIN` for every existing recipe
(`privileged_critic_engine_route.md:664-673`, restated at `ppo.py:498-503`).

**Q5. Does a determinization-sourced privileged block satisfy SF-13?**
`scripts/ch3_eval.py:331-333` asserts the eval env emits no `info["privileged"]`.
An RSD-sourced block uses no hidden state, so it does not violate SF-13's spirit,
but the assert is literal. **Recommendation: rule explicitly, keep the
`_Battle2Sentinel` armed, and name the ruling in the pre-reg** — a quiet edit
here is exactly the shape of a retraction-grade incident.

**Q6. What is the per-decision cap for a searched ladder object?**
**Recommendation: ≤ 5 s**, as already proposed (`STATUS.md:43-44`). Depth-2 lands
near 0.2 s, so the cap is not binding — which means it costs nothing to set it
now and it prevents a later arm from quietly buying its result with compute.

**Q7. `root_k` for depth-2 pruning — chosen, or measured?**
**Recommendation: measured, and published before the arm runs** (§5.3). The
retained-mass curve is a cheap offline read on the harvest; choosing `root_k`
after seeing win rates would be exactly the unnamed-cell failure the D25/D25-P
pre-reg rules exist to prevent (`CLAUDE.md`, Conventions).

**Q8. BR-vs-`q̃'` or Nash at the child?** **Recommendation: BR by default**
(matches the root operator, so Form B strictly extends Form A), **Nash as one
pre-declared secondary**, decided before the numbers. The optimism it fixes is
real and grows with depth (§5.2), but changing both the depth and the operator in
one arm makes the JOURNEY 11.5 comparison uninterpretable.

**Q9. Is the fresh 100M-lane harvest for R1-E worth its cost?**
It is ~9,000 roots across three lanes on a live server. **Recommendation: yes,
and it is not optional** — the R1 harvest is a 12M-era object, the search will
run on the 100M object, and the entire S3 relook exists because "search@M on a
100M lane was NEVER measured" (`configs/eval/search_s3_100m.yaml:18-20`). Making
that mistake twice in the same chapter would be avoidable.

**Q10. Do we build the exact-enumeration crate at all?** It is the second crate
the prompt's framing implies: an enumeration loop over gen 1's 39 damage rolls ×
crit × hit × secondary × speed tie, driven through `-Dcalc` overrides.
**Recommendation: NO, and pre-decide it now.** It is a second engine build that
`verify()` currently rejects (`ffi.rs:59-64`), it re-runs gates B-0..P-2 by the
crate's own rule (`ffi.rs:65-70`), and its only advantage over `S = 32` sampling
with CRN-1 is at depth 1 — where poke_engine already enumerates for free. If P0
says sampling cannot resolve a decision, the answer is that depth-2 is not
buildable, not that we should build a second engine.

---

## Appendix A — declared families, at a glance

| id | field(s) | class | measured incidence / residual |
|---|---|---|---|
| **W-HP** | opponent `P_HP` | grain | 0.558 dims/root, max \|Δ\| 0.0023 (`DET_BLIND.md:280`) |
| **W-STATS** | opponent `P_STATS` | determinized | max-DV model exact on 94.85% of realized stats (`determinize.py:48-51`); `min_atk` variant unmodelled |
| **W-ACTIVESTATS** | `A_STATS` | path-dependent | wrong on 2.26% (opp) / 1.08% (own) of 13,702 roots |
| **W-SLEEP** | `P_STATUS` bits 0-2, EXT | sampled per det | 7.00% opp / 0.35% own asleep |
| **W-CONF** | `V_CONFUSION_TURNS` | sampled per det | 0.74% of roots |
| **W-SUB** | `V_SUBSTITUTE_HP` | defaulted | 0 of 13,702 roots |
| **W-LASTDMG** | `B_LAST_DAMAGE`, `B_LAST_MOVES` | reconstructed | 27/146 pool species carry Counter |
| **W-LASTMOVE** | `S_LAST_SELECTED_MOVE`, `S_LAST_USED_MOVE` | sampled/defaulted | 0.31% opp / 0.03% own preparing; 4/146 species Mirror Move |
| **W-ORDER** | `S_ORDER[1..6]` | free | must contribute **0** dims |
| **W-SEED** | `B_RNG` | the chance dial | must contribute **0** dims |
| **W-LS** | `V_LIGHT_SCREEN` | NAMED UNMODELLABLE | 0 pool species |
| **W-REQ** | the request pair | derived | self-checking via `Battle::update`'s legality check |
| **W-DET** | the determinization itself | inherited, unchanged | `DET_BLIND.md:304-309` |

## Appendix B — files this design would touch

**New:** mutable layout writers (`engine/pkmn_gen1/src/layout.rs` or a new
`build.rs`-adjacent module), `RootReveal` + `BattleTracker::from_root`
(`track.rs`), `SearchNode` (a new `search.rs` + `pyencode.rs` surface), the
Python write-side bridge (`rl/search/engine_bridge.py`), the depth-2 solve
(`rl/search/matrix2.py`), gate scripts (`scripts/engine_r1e.py`).

**Modified:** `rl/search/matrix.py` (a simulator dial next to `leaf_view`),
`rl/search/agent.py` (a `simulator` dial next to `leaf_encoding`),
`scripts/ch3_eval.py` (arm keys + report fields, on the `search_leaf_encoding`
precedent at `DET_BLIND.md:130`).

**Unchanged and must stay so:** `rl/envs/showdown.py` (the encoder — changing
`OBS_DIM` invalidates every checkpoint), `engine/pkmn_gen1/src/encoder.rs`,
`rl/search/determinize.py`, `rl/search/expansion.py` (it is a poke_engine-side
correction and has no engine analogue — the engine's sampled update already
draws the roll).

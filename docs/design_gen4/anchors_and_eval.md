# anchors_and_eval.md — what the gen1 anchor battery becomes in gen4

> **design_gen4 status header.** Written 2026-09-04 on branch `gen4-design` (landed on
> main the same day); **revised 2026-09-05 on branch `gen4-build`** after the local live
> checks (research/live/, 1,530 recorded seat-battles) and the critic pass
> (research/critic_pass.md) — corrections are applied inline with a `critic_pass.md`
> or `research/live/` citation, and each doc ends with a dated live-verification
> section.
> DOCS ONLY — nothing under `rl/` changed. **Arc position:** the target is
> JOURNEY step 3 (gen4 encoder + model), and this doc also serves steps 5
> (offline evals vs Wang) and 6 (one gen4 ladder run). This design work is
> **maintainer-ruled PREPARATION running AHEAD of step 2 (gen1 ladder #3)**,
> written while ladder R4 is live; it is not a pre-registration and it launches
> nothing. Method deviation, recorded: no two-memo synthesis cycle (maintainer
> ruling 2026-09-04, budget); single-writer synthesis with adjudications in §9.
>
> **Verification status per claim** — every claim carries exactly one tag:
> - `[tree]` **tree-verified** — this repo at main@2738025 (CLAUDE.md, RESULTS.md,
>   SESSION_LOGS.md, `configs/eval/*`, `rl/`, `scripts/`) or the vendored `showdown/`.
> - `[src]` **source-verified** — installed poke-env 0.15.0; the foul-play clone
>   at `/Users/nickgreenquist/Documents/Projects/foul-play` and its conda env;
>   Wang's thesis text; the H&L paper text and metagrok clone.
> - `[lit]` **literature-only** — the prior-work index or a secondary source.
> - `[live]` **needs-live-verification** — BARRED until the live ladder run and
>   any later fleet complete; the check is stated.
> Nothing here was measured. **No gen4 number of ours exists.**
>
> **Sources read for this doc:** research notes `project_record.md` §1.9, §2–4
> (the anchor convention verbatim, the FP protocol, the search data set, the
> most-damage-typed record), `pokeenv_env_layer.md` §3 (SimpleHeuristicsPlayer
> end to end), `huang_lee_metagrok.md` §4–5, `wang_thesis.md` §1, §7–8, §11; my
> own read of the foul-play clone (`fp/generations.py`, `fp/data/sets/randbats.py`,
> `fp/format_spec.py`, `requirements.txt`, `Makefile`) and of the poke-engine
> binary installed in the `foul-play` conda env.
> **Depends on:** `mechanics_delta.md` §12 (turn cap, clauses), §11 (what SH
> cannot see); `pokeenv_gen4_survey.md` §7 (SH defects), G1/G7/G13.
> **Feeds:** `open_questions.md` (§10), `search_depreciation.md` (§5.4).

## 0. Summary — the battery's shape survives, every leg is re-derived

`[tree]` The standing convention (CLAUDE.md, 2026-08-23 ruling, MU-2 amendment
2026-08-26): every headline-grade result reports **vs-SH at the locked protocol**
(final checkpoint, 3000 battles/seed, 3 seeds pooled, ties as non-wins,
deterministic policy) **plus two descriptive anchors** — BC-clone h2h (500) and
Foul Play h2h at `--search-time-ms 20` with its two standing disclosures — before a
README row lands; anchors are descriptive, never verdict inputs; match the policy
form to the rating you compare against; ladder always means ladder + Foul Play at
pinned settings; vs-SH and off-FP numbers are never ladder numbers.

| leg | gen1 object | gen4 status | what changes |
|---|---|---|---|
| **vs-SH, locked protocol** | stock poke-env 0.15.0 `SimpleHeuristicsPlayer` | **keeps its place, as a weaker and different instrument** (§1) | same stock bot (comparability with Wang's 0.786 depends on it); the disclosure list grows; no gen1 bar or σ_seed is inherited |
| **BC-clone h2h 500** | Foul-Play clone at OBS_DIM 808 (`runs/bc_fp_v2r_soft_180k_s0`) | **must be rebuilt** — gen4 obs, gen4 teacher, gen4 tapes | blocked on a gen4 Foul Play and on tapes; `[live]` |
| **Foul Play h2h @20** | foul-play + our gen1 patch, poke-engine 0.0.48 gen1 build | **BUILT 2026-09-05 (§12): the `foul-play-gen4` env (poke-engine 0.0.48, `--features poke-engine/gen4`, functionally pinned as gen 4), the set file pinned by sha, the eval-bot path run end to end vs a gen-4 checkpoint** | the FP@20 licence rests on a gen1-specific flatness finding; the budget ladder still has to be re-run against a REAL gen-4 agent |
| **most-damage-typed** (JOURNEY's pre-step-3 add) | not built; `MaxBasePowerPlayer` is the weaker sibling in the registry | **spec below** (§2); one afternoon; registry + test edit | the cross-generation denominator; descriptive only |
| **ladder (step 6, one run)** | R1/R3/R4 on gen1randombattle | one run, exit = the run; 150 s/turn timer path | pin FP budget, engine commit, n, greedy-vs-searched first (JOURNEY's pairing rule) |

## 1. What SimpleHeuristicsPlayer is worth in gen4

**The mechanism, enumerated** `[src]` (`poke_env/player/baselines.py:133-368`, read in
full): SH scores moves as `base_power × STAB 1.5 × (physical or special stat ratio)
× accuracy × expected_hits × type multiplier` (`:322-340`), switches out on a
type-chart-plus-base-speed-plus-HP matchup score (`:147-163, 219-247`), sets
Spikes/Toxic Spikes when three or more opposing mons remain and spins when it has
any side condition of its own (`:286-303`). It is blind to **items, abilities,
weather, hazard chip on the incoming mon, priority, and every status move** (status
moves score 0). In gen 1 four of those six do not exist; in gen 4 all six do.

| branch | gen1 | gen4 | source |
|---|---|---|---|
| hazard setting | inert (no such move exists) | partially live: Spikes + Toxic Spikes (14 + 14 sets); Stealth Rock never — the dict key is the typo `"stealhrock"` (`:134-141`), and SR is on no vendored set anyway | `[src]` `[tree]` |
| hazard removal | inert | live (Rapid Spin, 13 sets); misfires on its own screens (the guard is bare `battle.side_conditions`) | `[src]` |
| setup moves | **dead** — `move.target == "self"` compares an enum to a string, always False (`:314`) | dead | `[src]` |
| `_stat_estimation` +1 bug | live, low dose | live, higher dose: Swords Dance 48, Calm Mind 44, Nasty Plot 20, Dragon Dance 13, Curse 11 sets — a +1 boost is valued as +2 (`:249-256`); no level or EV term either | `[src]` `[tree]` |
| physical/special ratio | type-derived (correct by definition in gen1) | per-move — SH's one genuine improvement in gen4 | `[src]` |
| `expected_hits` | gen5+ value 3.17 (true 3.0) | same | `[src]` `[lit]` |
| Return | n/a | scored 0 BP on 39 species (poke-env reports 0; survey G7) | `[src]` `[tree]` |
| Explosion / Self-Destruct | BP 170 / 130 | BP **250 / 200** with no self-KO penalty: the score is monotone in base power, so SH (and MaxBasePower) detonate on sight on the 37 + 3 sets that carry them | `[src]` `[tree]` |
| `maybe_trapped` | dead | ignored: SH tries switches that Arena Trap / Shadow Tag / Magnet Pull reject (Wang's fork guarded this; 0.15.0 does not) | `[src]` |
| dynamax / tera guards | inert | inert | `[src]` |

**Verdict:** SH is a type-chart-plus-base-stats bot, and gen 1 is almost entirely a
type-chart-plus-base-stats game; gen 4 is not. JOURNEY's argument that "an
SH-denominated number partly measures SH getting stronger as we move up the arc"
`[tree]` (JOURNEY.md:17) is correct in direction for the hazard branches, but the
net effect of everything above is that **SH is relatively weaker in gen4** than in
gen1 against any agent that reads items, abilities and status. This is a mechanism
argument; it licenses no win-rate claim.

**External calibration** `[src]` `[lit]`: Wang's Table 4.1 has SH beating Random
.992 and losing to his network .786 and to his searched agent .908; his text calls
SH "equivalent in skill to a beginner Pokémon player" and notes the in-training
win rate "never surpassed 90%". Metamon's ladder row for SH is Gen4**OU** 21–36
(36.8 % raw, 31.6 % GXE) — an OU tier with team building, not randbats; the randbats
rows (gen7RB 39.7 %, gen9RB 41.2 % GXE) are the ones that apply to our family, and
**no gen4RB SH ladder number exists anywhere** (`docs/prior_work/README.md`). SH's
gen4RB strength against humans is unmeasured.

**Three SimpleHeuristicsPlayers are now in play** `[src]` `[tree]`: stock 0.15.0
(ours, and Wang's validation harness as far as the thesis says), Wang's fork's SH
(patched four times: Curse `???` type, `opp_remaining_mons`, `maybe_trapped` ×2 —
`docs/prior_work/wang_fork_diffs.md`), and ps-ppo's (`_stat_estimation` patched). Wang's
0.786 is comparable to a stock-SH number **only if the number he reports was
measured against stock SH, which the thesis does not state** (`wang_thesis.md` §7.2).

**Recommendation (adjudicated in §9 A1): do not patch SH.** Keep the stock bot so
gen4 numbers stay comparable with the gen1 ledger and with Wang; disclose the
defects above wherever a gen4 vs-SH number is quoted, exactly as FP@20's two
disclosures travel. The protocol itself (3 × 3000, deterministic, ties non-wins)
carries over unchanged. **What does not carry:** the gen1 σ_seed (≈ 0.062) and
every bar derived from it — gen4's noise floor is unmeasured `[live]` (the check is
the first gen4 fleet's finals), and the ±0.02 single-rung landmine is presumably
worse with longer games, not better.

## 2. The most-damage-typed anchor — specification

> **STATUS 2026-09-05: BUILT** as specified below (`rl/envs/most_damage_typed.py`,
> registry key `most_damage_typed`, `tests/test_most_damage_typed.py`,
> `scripts/anchor_h2h.py`). Gen-1 placement, bot-vs-bot, n = 300 each, sanity only:
> 0.983 vs random, 0.777 vs MaxBasePower, 0.330 vs SimpleHeuristics. It joins the
> battery only on the maintainer's say-so (§9 A2); no README row.

**Why** `[tree]`: JOURNEY's pre-step-3 item ("the only anchor whose own strength
doesn't drift across generations … the right denominator for a gen1 → gen4 → gen9
comparison", JOURNEY.md:15-19; IDEAS_POST_100M §2.6). Record status: **no pre-reg,
config, script or ruling exists** — six grep hits, all proposal or citation
(`project_record.md` §4.1).

**The definition, at the precision H&L's code gives it** `[src]`
(`metagrok/pkmn/engine/baselines.py:48-152`, `MostDamageMovePlayer(type_aware=True)`):
score every legal move as `basePower × effectiveness(move type → defender's types)`,
OHKO moves as 120, **nothing else** — no STAB, accuracy, category, stats, boosts,
items, abilities, multi-hit, priority, status value, KO reasoning; pick the max, ties
broken uniformly at random; **never switch voluntarily**; on a forced switch pick the
bench mon minimising the sum of the opponent's *types'* effectiveness against it.
Their result vs the trained agent: 829–171 of 1000 gen7RB games, ties as non-wins
(the same convention as ours). The index's caveat stands `[tree]`: this bot is "far
weaker than SH", and the number does not transfer across formats.

**Our specification (PROPOSAL):**

| element | choice | reason |
|---|---|---|
| name | `most_damage_typed`, fourth key in `OPPONENT_PLAYERS` (`rl/envs/showdown.py:61-64`) beside `random`, `max_power`, `heuristics` | reachable from every collector and eval path that takes an opponent spec |
| move score | `base_power × opponent.damage_multiplier(move)`; STAB **excluded**; status moves 0; ties uniform random | H&L's definition verbatim — the point is a fixed, published denominator, not a good bot |
| base power source | poke-env's `move.base_power` **with the Return override (102)** and with Hidden Power's typed id | without the override the bot cannot see a 102-BP STAB move on 39 species; the override is a deviation from H&L and is disclosed |
| type chart | `GenData.from_format(battle_format).type_chart` through the spec's listed types (17 at gen 4) | a chart copied from metagrok's `dex/` is gen7 (Fairy present, Steel loses its Ghost/Dark resistances) — a silent error |
| switching | never voluntary; forced switch = H&L's least-weak-by-types rule | keeps "no generation-dependent logic" honest |
| abilities / items | ignored | by definition; note that in gen 4 this bot will fire Earthquake into Levitate |
| Explosion | scored at raw BP (250) like every move | H&L's definition; disclosed as the bot's largest gen4 weakness |
| determinism | seeded RNG for tie-breaks | eval reproducibility |
| tests | `tests/test_showdown_env.py:411` asserts the exact registry key list and must be edited; add a scoring test against a fixed battle fixture | `[tree]` |

**"No generation-dependent code" is true of the algorithm, not of the code** `[src]`:
any poke-env implementation reads a per-generation chart and, from gen 4, a per-move
category (irrelevant here) — the invariance claim is that the *rule* is the same
product in every generation. Say it that way.

**What it is worth:** a descriptive fourth leg, never a verdict input; its sole
purpose is a denominator that means the same thing in gen1, gen4 and gen9, and a
one-time cross-format placement against H&L's 0.829 (confounded, as JOURNEY says).
It joins the battery only if the maintainer says so (§9 A2); the 2026-08-23 ruling
named three legs.

## 3. A Foul-Play equivalent for gen4

**foul-play supports gen4 as a first-class generation** `[src]`
(`/Users/nickgreenquist/Documents/Projects/foul-play/fp/generations.py:23-135`): a
`GenerationMechanics` table with `GEN4 = replace(GEN5, has_team_preview=False,
rest_turns_reset_on_switch=False, taunt_duration_increments_end_of_turn=True)`,
inheriting from GEN5 `ability_weather_is_permanent=True`, `hidden_power_base_damage_
string="70"`, from GEN6 `paralysis_speed_divisor=4`, `request_dict_ability="baseAbility"`,
with `choice_scarf_exists`, `supports_reverse_damage_checking`, modern stat
calculation and PP; `GENERATIONS["gen4"]` is selected from the format string
(`fp/format_spec.py`). Gen1 sits at the far end of the same table
(`partial_trapping_mechanics`, `stat_modification_glitches`). So the Python side is
not the blocker.

**The engine is** `[src]`: the poke-engine installed in the `foul-play` conda env is
the **gen1 build** — module-path strings in
`site-packages/poke_engine/poke_engine.cpython-311-darwin.so`: `src/gen1/` 7,
`src/gen4/` 0, `src/gen2..5/` 0, `src/gen9/` 0, `"used for spc"` 1 (the index's own
discriminator). `requirements.txt` pins
`poke-engine==0.0.48 --config-settings="build-args=--features poke-engine/gen1
--no-default-features"` (our patch), and the `Makefile`'s `poke_engine` target rebuilds
with `--features poke-engine/$(GEN)` for any `GEN`. The index records `gen1..gen9` as
real Cargo features with `default = []` `[lit]` (verified there against `Cargo.toml`,
not re-verified here; no Rust checkout is on disk). **A gen4 anchor is therefore
`make poke_engine GEN=gen4` in the foul-play env** (Rust toolchain; the gen1 build took
~9 s), plus the module-path check `src/gen4/ > 0`.

**Set data is fetched, not cached — now PINNED** `[tree]` (`fp/data/sets/randbats.py:24-31`; `research/live/fp_gen4_set_pin.json`): `gen4randombattle.json` fetched 2026-09-05 (sha256 `f742b0d9…`, 125,866 bytes) and pre-placed in `fp/data/pkmn_sets_cache/` so the bot never fetches (a non-200 caches `{}` permanently, `fp/data/sets/base.py:38-52`). Its schema is `{species: {"level,item,ability,m1..m4": count}}` — counted 4-move sets, not the vendored roles-plus-movepools — so the LG-5-style check is a six-way comparison, done: the same 295 species; every item, ability and move inside our 40 / 101 / 182 vocab; 1,736 of its 1,743 distinct set keys are realised by OUR generator sample and 5 of ours are absent upstream (weighted overlap 1.000 — the two files describe the same realised set space, 600,000 counted sets each); **40 species differ by ±1–2 levels** (upstream was generated at a nearby Showdown commit) — the one divergence between Foul Play's opponent model and our server, disclosed in every gen-4 FP quote. Stealth Rock is on no set in either.

**Our patch** `[tree]` (`scripts/patches/foulplay_gen1_local.patch`): the gen1
`Fight` placeholder handling (`fp/data/__init__.py`, `fp/modes/base.py`) is gen1-only
and inert in gen4; the local `--no-security` login, the persistent process pool, the
tape writer, the switch guard and the engine pin carry over (the pin changes to gen4).

**Risks to verify** (`[live]` when written; §12 records what the 2026-09-05 build settled): - a 5-battle gen4 smoke vs SH at `--search-time-ms 20` — DONE, 5-0 for FP, no panic (§12), then the FP-h2h G1–G5 gates (with a real agent);
- **the Struggle panic** (`Invalid PokemonMoveIndex: 4`): the "both sides out of PP" mechanism recorded here and in `landmines.md` does not survive the source — Struggle is never added to a move list and the bot's list is rebuilt from the request; the hole is an unbounded `move:{i}` index in the engine bridge (`fp/search/poke_engine_helpers.py:117-126`, `research/foulplay_pokejax_audit.md` §2), no 5-move path is reachable in the vendored gen4 pool, and the gen-1 trigger stays unresolved. The pre-flight is `grep "More than 4 moves on pokemon"` over the FP log (0 hits in the 2026-09-05 runs, §12);
- game length: the FP-runner rate references (FP@20 ≈ 1.2–1.5 s/battle, FP@100 ≈ 6–7 s)
  are gen1 numbers and every stall-watch threshold derived from them must be
  re-measured; the four incident fixes in `scripts/ch3_r4_fp_runner.sh` carry over
  unchanged;
- one modelling divergence surfaced while reading: foul-play's gen4 table says the
  sleep counter does **not** reset on switch, and the vendored gen4 `slp` block is a
  full replacement without `inherit: true` — see `mechanics_delta.md` §6 for the
  resolution; any such divergence between the engine's model and the server's rules
  biases the teacher down, silently, exactly as a wrong-generation build does.

**The FP@20 licence does not carry by itself** `[tree]`: MU-2 made FP@20 the standing
anchor because the budget ladder found FP **flat in budget** (FP@20 0.312 / FP@100
0.388 / FP@500 0.332, n=250, every gap ~1–2 se), and the recorded explanation is
"gen1's small trees (20 ms already searches deep enough)"
(`SESSION_LOGS.md:5702-5717`). Gen4 trees are not small. The two-rung ladder
(`configs/eval/fp_budget_ladder.yaml`, 20 ms and 500 ms, n ≥ 250) must be re-run
against the gen4 build before a gen4 budget is pinned; until then any gen4 FP number
names its budget and carries the two disclosures, as every FP number does.

**Wang's MCTS is not an anchor candidate** `[src]` `[tree]`: it is test-time search
over his own network with 20 workers and 10 s/decision, needs `>getstate`/`>load`
stream commands that the vendored 0.11.11 does not have (serialization is upstream,
the commands are not), and its determinizer reject-samples a 2023 procedural
generator that no longer exists — the vendored gen4 pool is a curated table of ≤ 3
sets per species. Foul Play is the reproducible incumbent in gen4 as in gen1.

## 4. The BC-clone leg

`[tree]` The current clone is a Foul-Play clone at OBS_DIM 808 (six FP tapes, 7,200
battles / 180,440 decisions, MLP 512/512, soft targets; 0.5490 / 0.5777 vs SH), not
portable to a gen4 encoder or a gen4 teacher. A gen4 clone needs: a working gen4
Foul Play (§3), gen4 tapes through the gen4 encoder, and the banked recipe re-run.
`scripts/make_bc_dataset.py` still documents 611-dim obs and defaults to SH as the
expert — a stale docstring to fix when it is next touched. Purity: the clone is an
anchor, never training input (CHAPTER5 §6). Order of work: encoder → gen4 FP → tapes
→ clone; the clone lands last and is `[live]` throughout.

## 5. Protocol adjustments the gen4 rules force

1. **Ties and the turn cap.** Ties are non-wins (locked protocol). gen4 randbats has
   no Endless Battle Clause; the sim auto-ties at turn > 1000 with Protect's 1/8
   floor, Toxic on 132 sets, Levitate on 40, Wish on 19 and Leftovers in play. The
   gen4 pre-reg needs an explicit tie rule (count, disclose the rate, and a
   per-battle turn budget for the collector) — `mechanics_delta.md` §16 Q2.
2. **Timer.** Every seat sends `/timer on` (wire-visible, binding); challenge battles
   get 300 s/turn, ladder games 150 s (the same 150 s Wang's search budget was set
   by `[src]`). Longer gen4 games change the cost per battle, not the rule.
3. **Sleep Clause Mod is on; Freeze Clause is not** — multi-freeze is legal.
4. **Rates.** No s/battle reference exists for gen4; the "progress is a rate" landmine
   needs a gen4 comparable before any long arm is trusted `[live]`.
5. **Process isolation.** A gen4 eval process cannot host a gen1 encoder
   (`encoder_requirements.md` §2); `scripts/eval_checkpoint.py:103` and the three
   `fake_spaces()` sites must take the gen4 format.
6. **The credit line and the five pre-reg rules apply verbatim** to any gen4 lever;
   no gen1 bar, σ_seed, or "50M was enough" argument is inherited (the IDEAS §1
   re-rank under SS-CLIMB is itself still owed `[tree]`).

## 6. The Wang comparison (JOURNEY step 5)

`[src]` Table 4.1: network alone **0.786** vs SH; Figure 4.1 digitized: **0.575 at 6M**,
0.786 at 30M, endpoint **≈ 0.836**, peak **≈ 0.849 near 120M** (150M steps, 4 days).
The two are unreconciled from the text (not 3v3 vs 6v6 — that was only the
hyperparameter surrogate; not ties; not the 100M LR accident; plausibly a different
action-selection mode or a different SH between the validation harness and the
post-hoc table). His laddered agent is the **searched** one: rank 8, 1693 Elo, 1756 ± 28
Glicko-1, 79.5 % GXE — a **peak**, 200-game average ≈ 1615, one account. His ladder
row in the prior-work field table quotes that peak against our stopping-rule
endpoints; footnote it wherever the table is reused.

**Recommendation (§9 A3): pin 0.786 as the step-5 exit bar and quote ≈ 0.836 as the
stretch**, with "matched" defined as the pooled 3 × 3000 locked-protocol final whose
lower 2·se_gov bound reaches 0.786 (se_gov the larger of binomial and seed-clustered,
as the credit line says). Disclosures that travel with the comparison: stock SH with
the +1-boost bug on both sides (comparable iff Wang's harness was stock — unstated);
SB3's PPO **implementation** (his 13 hyperparameters are Bayesian-tuned on a 3v3
surrogate, not SB3 defaults — JOURNEY's "with its defaults" is wrong `[src]`); his
encoder (3,725-dim, identity actions) and batch shape (≈ 40k steps/update); and that
our exit bar is his weaker number.

## 7. The gen4 ladder (JOURNEY step 6)

One run; exit condition = the run; not a like-for-like comparison with Wang (his is
searched). Before it: pin FP budget, engine + poke-engine commit, n, and
greedy-vs-searched (JOURNEY's pairing rule); the ladder seat stays at
`max_concurrent_battles` 2 (rated, matchmade); `scripts/ladder.py` under its own
pre-reg; the profile JSON, not the leaderboard, is the read; never project between
boards. The gen4RB board's thickness and admission cutoff are unmeasured
`[live]` — one unauthenticated pull of the gen4randombattle ladder JSON before the
run (barred now, and never for the live gen1 account).

## 8. Search's gen4 anchor role — a pointer

The searched endpoint of the gen1 depreciation curve does not exist (no searched
arm of any 100M lane; `project_record.md` §3.7 `[tree]`), and the gen1 search line
is a rewrite for gen4 (`encoder_requirements.md` §6). Nothing in this doc assumes a
gen4 search object; if one ever exists, "match the policy form" applies and the
ladder-object question is decided before the run (JOURNEY step 11). Detail:
`search_depreciation.md` if written; otherwise `open_questions.md` D5.

## 9. Adjudications (single-writer; recommendation, then the losing argument)

- **A1 Do not patch SH for gen4.** Losing: a bot that cannot set up, cannot set
  Stealth Rock, mis-prices every +1 boost and walks into ability traps is a straw
  opponent in gen4 in a way it is not in gen1, so "vs-SH" is not the same instrument
  and calling both by one name invites exactly the cross-generation projection the
  ladder landmine forbids; a patched SH would be a *better* gen4 anchor. Patching
  breaks comparability with every published SH number, including Wang's.
- **A2 most-damage-typed is built as a fourth, descriptive leg — not a replacement.**
  Losing: the 2026-08-23 ruling capped the battery at three legs; a never-switching
  bot will be beaten so badly the number carries no gradient; it is one more n=500
  run per readout.
- **A3 Pin 0.786 as the exit bar, 0.836 as the stretch.** Losing: "roughly 85 %" is the
  number Wang headlines and the one a reader remembers; matching 0.786 and claiming
  parity reads as matching the weaker of his two numbers.
- **A4 Foul Play (gen4 build) is the FP leg; Wang's MCTS is not an alternative.**
  Losing: FP's gen4 opponent model is upstream's set data, not our pool; Wang's
  determinizer is exact against the server's generator. The vendored curated pool
  makes Wang's sampler moot and the pinning discipline closes FP's gap.
- **A5 Re-run the FP budget ladder before pinning a gen4 budget; quote FP@20 until
  then with the standing disclosures.** Losing: 5.1× cost was the whole reason for
  MU-2, and a 500 ms rung in gen4 games may cost hours per 250 battles.
- **A6 Keep the locked protocol's n and form; inherit no bar.** Losing: 3 × 3000 was
  sized for gen1's ~30-decision battles and gen1's σ_seed; gen4's longer games make
  each battle dearer and the seed noise is unknown, so the first gen4 fleet should
  size n from its own R0 read.

## 10. Maintainer rulings wanted (collected in `open_questions.md`)

1. Patch SH for gen4, or disclose (A1)?
2. Does most-damage-typed join the battery (A2), and is it built before step 3 as
   JOURNEY schedules it?
3. The step-5 target: 0.786 vs ≈ 0.836, and the numeric definition of "matched" (A3).
4. Authorise the gen4 Foul Play build (`make poke_engine GEN=gen4` in the foul-play
   env, a network fetch of the gen4 set file, its pin and diff) when the box is free.
5. The gen4 tie / turn-cap rule for collection and eval.
6. Whether the BC-clone leg waits for a gen4 Foul Play or is dropped for the chapter's
   first readout.
7. The gen4 chapter's written exit condition (JOURNEY.md:68 — still unwritten).

## 11. Sources, verification, deferrals

- `[live]` items: everything in §3 "Risks to verify"; the gen4 noise floor; s/battle
  references; the gen4RB board pull; the clone pipeline.
- `[lit]` items: poke-engine's Cargo feature list (index-verified, not re-read here);
  Metamon's SH rows; the gen4 multi-hit distribution behind SH's `expected_hits`.
- Not read: the foul-play search core (`fp/search/*`) beyond the file listing, its
  tests, the pkmn.github.io data format beyond `randbats.py`'s parser; Wang's
  Showdown-fork determinizer in the diff (only its thesis description and the index).
- Deferred (`open_questions.md` D3): a full foul-play/pokejax audit was the lost
  agent's task; the facts above are the cheap subset I could verify directly.

## 12. Live verification and what was built (2026-09-04/05, branch `gen4-build`)

- **§2 most-damage-typed is BUILT** — built independently on BOTH branches on 2026-09-05 (main: `rl/envs/most_damage_typed.py`, the §2 status box above; this branch: a twin under `rl/envs/players.py`, since REMOVED — the branch converged on main's module, same rule); the gen-4 placements below were recorded with the twin —
  registered as `most_damage_typed` in `OPPONENT_PLAYERS` (H&L's rule verbatim,
  the Return override and the typed Hidden Power id disclosed in its docstring;
  it is generation-agnostic by rule and reads the per-format type chart).
  Battery admission is still Q36's ruling. `[tree]` live, 30 battles each,
  descriptive and far below any protocol n: gen4 vs random **29-1-0**, gen4 vs
  SH **14-15-1**, gen1 vs max-power **24-5-1**
  (`research/live/t5_mdt_rnd`, `t6_mdt_sh`, `t7_mdt_mbp_gen1`). SH vs SH in gen4
  was 93-100-7 over 200 (`t2_sh_sh_200`).
- **§5 ties** are live at 1–3.5 % between bots (simultaneous KOs, never the turn
  cap; longest game 147 turns) — the gen4 pre-reg's tie rule (Q33) has a measured
  base rate to disclose against.
- **§3 the FP gen4 build — DONE 2026-09-05 (Q37 authorised that morning; recipe: `scripts/setup_foulplay_gen4.sh`).** A SECOND conda env `foul-play-gen4` (the gen-1 build in `foul-play` stays untouched — one env per engine build), poke-engine 0.0.48 compiled with `--features poke-engine/gen4 --no-default-features` (maturin log), sharing the patched foul-play clone read-only. `[tree]` The binary is functionally gen 4: `calculate_damage` gives Ghost→Steel and Dark→Steel ×0.50 (the gen 2–5 chart), Explosion / Double-Edge 4.14 (gen ≤ 4 halves the target's Defense; gen 5+ would read 2.08), crit ×2.01 at 6.2 % (the 1/16 stage table); the gen-1 build on the same probes reads 3.33 and 21.6 % speed-based crits. Module tree `src/genx/` (the gen-1 build carries `src/gen1/`). **Smoke** (`scripts/gen4_fp_smoke.py`, `research/live/fp0_sh_5.summary.json`): FP@20 vs SH 5-0, 2.5 s/battle, 0 panics / tracebacks / `More than 4 moves`, sets loaded from the pinned cache, 0 poke-env warnings on our seat. **Eval-bot path** (`scripts/gen4_fp_h2h.py`, `h2h0_smokeckpt_20.summary.json`): FP@20 vs OUR gen-4 checkpoint (the learner-smoke checkpoint, untrained) through `Gen4PoolPlayer` — 20 battles, 0-20 as expected, 1.35 s/battle, 0 mask desyncs, one `[Unavailable choice]` (a sampled switch into a hidden trapper — the G1 rate). **Rates**: FP@20 ≈ 1.2–2.5 s/battle, FP@500 26.6 s/battle over n=250 (both seats on one box; the ≈ 60 s first estimate from the opening dozen battles is superseded); **FP@20 vs stock SH, n = 250: Foul Play 226-24-0 (0.904), 1.18 s/battle, 0 panics, 7 `[Unavailable choice]` on the SH seat, longest game 58 turns** (`research/live/fp1_sh_250_t20.summary.json`; descriptive — a bot-vs-bot rate, not a protocol number and never a ladder number; the two standing disclosures travel with it as with every FP@20 number — the equivalence test is weakly powered and the point estimate flatters us — plus the gen-4 caveat that FP's opponent model drifts ±1–2 levels on 40 species); **the FP@500 twin, n = 250: Foul Play 228-22-0 (0.912), 26.6 s/battle, wall 6,657 s, FP exit 0, 0 panics / tracebacks / `More than 4 moves`, 0 poke-env warnings, 2 `[Unavailable choice]` on the SH seat, sets from the pinned cache on all 250 loads, turns mean 21.8 / median 20 / max 117** (`research/live/fp2_sh_250_t500.summary.json`; the same disclosures travel with it, budget named). FP@20 0.904 vs FP@500 0.912 against SH is flat in budget within noise (se ≈ 0.018 each) — as in gen 1, and here a ceiling of the SH seat as much as of the search; the budget ladder that matters is against a REAL agent (Q38). FP's log carries thousands of gen-9 bookkeeping lines (`neutralizinggas` / `boosterenergy` / `airballoon` marked impossible) — noise, not a defect. **Regenerator (D3's teacher defect) is not live in randbats**: FP samples whole opponent sets from the pinned set file, whose 101 abilities are the pool's; `grep -ci regenerator` over every FP log is 0. `research/foulplay_pokejax_audit.md`
  (deferral D3, now read) replaces the Struggle-panic mechanism in §3: the hole
  is an unbounded `move:{i}` index in the engine bridge, no 5-move path exists in
  the vendored gen4 pool, and the cheap pre-flight is a grep for `"More than 4
  moves on pokemon"`; it also finds a gen4-specific teacher defect (Regenerator
  healing on switch-out is enabled for GEN4 while 219 / 295 pool species keep a
  Dream-World hidden ability after the gen-4 mods) and that the upstream set file
  and the vendored pool are different schemas (counted 4-move sets with items vs
  roles with movepools and no items), so the LG-5-style pin is a six-way
  comparison, not a diff. Both go into Q37's pre-reg items.
- **The learner loop closes end to end** (`configs/gen4_smoke_heur.yaml`, 16
  updates of 512 steps, 4 envs, [64, 64], vs SH): rollout → PPO update → eval →
  checkpoint → `meta.yaml` with the gen-4 fingerprint (`rl/train.py` stamps
  `ENCODER_FINGERPRINT_GEN4` for `ShowdownGen4-*` env ids). Its eval win rate is
  0/10 at 8,192 steps, which measures nothing and is quoted nowhere.
- **§6 Wang's comparability:** `research/wang_showdown_fork.md` (deferral D1, now
  read) finds nothing in his Showdown fork that changes gen4 battle rules for
  training or evaluation (only the `/offertie` turn-100 gate is removed), so the
  0.786 is not confounded by a modified simulator; the open confound stays "which
  SH" (`[lit]`).

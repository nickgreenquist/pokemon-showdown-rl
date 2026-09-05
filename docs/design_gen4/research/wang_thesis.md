# Wang 2024 — full read (gen4randombattle PPO + test-time MCTS)

**Agent:** wang-thesis research agent (gen4 design sweep, stage 1)
**Date:** 2026-09-04
**Note name:** `wang_thesis.md`

## Status legend (every finding below carries exactly one)

- **tree-verified** — checked against a file in the repo tree (SNAP `rl/`, `scripts/`, `configs/`,
  `tests/`, `docs/`) or the vendored Showdown `data/`/`sim/`, i.e. the game as we actually run it.
- **source-verified** — checked against an external primary source on disk: poke-env 0.15.0 source,
  Wang's thesis text or fork diffs, H&L text / metagrok, ps-ppo, foul-play, Metamon text.
- **literature-only** — from a secondary write-up, a web page, memory, or the prior-work index
  without re-checking the primary.
- **needs-live-verification** — only a running server or battle can confirm; BARRED until the ladder
  run and any later fleet complete. The check is stated explicitly.

## Sources read (path + line/page ranges)

| Source | What I read |
|---|---|
| `scratchpad/research/_wang_thesis_paged.txt` (pdftotext of `docs/prior_work/wang2024_mit_thesis_randbats_rl.pdf`) | **the whole file, 1,440 lines = thesis pp. 1–47.** Line→page map: lines 1–199 = pp. 1–12 (front matter/TOC), 200–400 = pp. 13–17 (ch. 1), 400–604 = pp. 18–22 (ch. 2), 605–827 = pp. 23–28 (ch. 3), 828–1025 = pp. 29–35 (ch. 4), 1026–1193 = pp. 36–39 (ch. 5), 1194–1337 = pp. 40–43 (Appendix A + Tables A.1/A.2/A.3), 1338–1440 = pp. 44–46 (references). |
| `scratchpad/research/_wang_fig41_crop-29.png` | Figure 4.1 (thesis p. 29), viewed, then **digitized** — see "Figure 4.1 digitization" below. Helper scripts written by me this session: `scratchpad/research/_fig41_probe.py` and `_fig41_read.py`, operating on `_fig41.bmp` (a `sips -s format bmp` conversion of the PNG). |
| `docs/prior_work/README.md` | lines 110–135 (ladder-comparison table), 385–500 (Sources: Wang / VGC-Bench / Metamon / ps-ppo entries), 555–640 (`wang_fork_diffs.md` entry, H&L entry). |
| `docs/prior_work/wang_fork_diffs.md` | lines 1–35 (header + PS commit log), 3409–3460 (poke-env commit log + start of cumulative diff), 3560–3590 and 3676–3700 (weather / `Move.reveal` / `_base_ability` hunks), 3930–3992 (Player `maybe_trapped`, `base_format`, server-URL hunks), 3993–4030 (SB3 commit log + first hunks); grepped the whole file for `getstate`/`>load`/`randomConstrainedSet`/`maxpp`/`maybe_trapped`. |
| poke-env 0.15.0 (`PE`) | `battle/abstract_battle.py:752–772`, `grep` for `from_showdown_message(weather)` and `maybe_trapped` across the package, `player/baselines.py` `available_switches` sites. |
| Vendored Showdown (`SD`, PS 0.11.11 @59da482) | `data/conditions.ts:640–700` (sandstorm/hail weather conditions), `grep '-weather'` over `data/conditions.ts`, `data/mods/gen4/conditions.ts:146–160`, `data/random-battles/gen4/teams.ts:1–45,636`, `data/random-battles/gen4/sets.json` (counted with a 3-line stdlib-json script), `sim/battle-stream.ts` (case list), `sim/battle.ts:318–323`. |
| SNAP `main@2738025` | `JOURNEY.md` lines 36–62 (steps 3–5) and 118; `grep -n -i wang JOURNEY.md docs/IDEAS_POST_100M.md`. |

**Not read / out of scope for this note:** the thesis PDF's figure pages 26 (Fig 3.1, LR schedule),
31 (Fig 4.2, losses), 32 (Fig 4.3, Elo progression), 33–34 (Figs 4.4/4.5, game logs) — I read their
captions and surrounding prose in the text dump but did not open the page images; the prose carries
every number I cite. I did not open Wang's code (no repo beyond `wang_fork_diffs.md` is on disk —
the thesis links only a *replay* repo).

---

## 1. Format and environment

**(source-verified)** Format is `gen4randombattles`, 6v6 singles, teams drawn from "a pool of 296
Pokémon available in Gen 4 and equipped with a procedurally generated set (moves, item, and ability)"
(p. 13, §1.1.1). Rationale, verbatim (p. 13): "Gen 4 has most of the intricacies of Pokémon
mechanics… Earlier generations have noticeable flaws… Gen 1 has no real counters to strong
Psychic-type Pokémon; Gen 2 lacks abilities…; and Gen 3 designates attacks as physical/special based
on type". And (p. 14): "Generation 4 excludes mechanics from later generations such as
mega-evolving and Terastallization which essentially double the action space of the game until they
are used." Metagame character (p. 14): "gen4randombattles tends to favor 'stalling' tactics, using a
combination of entry hazards, status moves, and healing moves/items".

**(source-verified)** The POMDP, verbatim (p. 23, §3): `s ∈ S ⊂ [0,1]^3725`;
`a ∈ A = {0,1,…,494}`; `r ∈ {−1,0,1}`.

**(source-verified)** Time control, verbatim (p. 24): "In gen4randombattles, a timer is kept for each
player starting at 150 seconds, which gets replenished by 10 seconds for every decision made. If a
player's timer reaches 0, they instantly lose the game. Thus, the agent was allowed 10 seconds of
thinking time per move, which constrained the number of possible futures that could be explored
during MCTS." **Cross-ref for `anchors_and_eval.md` / `search_depreciation.md`:** this is the same
150 s/turn ladder budget our own timer landmine records (CLAUDE.md, "The LADDER is the tight path
(150 s/turn, not the 300 s a challenge gets)") — Wang's search budget is set by exactly that clock.

**(source-verified)** The **3v3 surrogate is for hyperparameter optimization only**, not for
training or evaluation. Verbatim (p. 41, §A.0.3): "Hyperparameters were tuned via Bayesian
optimization on a surrogate task: 3v3 battles where each team is given only 3 Pokémon instead of 6.
Because training just one model takes so long for full 6v6 games, we tuned hyperparameters in the
3v3 case, where battles are half as long. This subgame retained some complexity, but vastly
shortened the amount of time to see significant differences in hyperparameter performance." No
Bayesian-optimization details are given: no search space, no trial count, no budget per trial, no
objective definition. **This rules out "3v3 vs 6v6" as an explanation of the Table 4.1 / Figure 4.1
gap** (both headline numbers are 6v6).

**(source-verified, thesis is silent)** **The thesis never mentions a Showdown fork, poke-env
patches, or Stable-Baselines3.** Grepping the full text for `fork`, `bug`, `poke-env`, `poke_env`,
`stable.baselines`, `sb3` returns nothing but reference [22] (poke-env, cited only as the source of
`SimpleHeuristicsPlayer`) and reference [6] (Pokémon Showdown). The only repo he links is
`https://github.com/quadraticmuffin/pkmn-thesis-replays` (p. 35), which holds replay HTML. **The
whole infrastructure layer is undocumented in the thesis** and exists only in
`docs/prior_work/wang_fork_diffs.md`.

**(source-verified, from the fork diffs, not the thesis)** What the forks actually contain
(`wang_fork_diffs.md:1–35`): `pokemon-showdown` 13 non-merge commits touching
`data/mods/gen4/random-teams.ts`, `server/chat-commands/core.ts`, `server/room-battle.ts`,
`sim/battle-stream.ts`, `sim/battle.ts`, `sim/pokemon.ts`; `poke-env` 36 commits; `stable-baselines3`
8 commits. The Showdown work splits cleanly:
- **Search-time:** `randomConstrainedSet` / `randomConstrainedMoveset` in the gen4 random-teams
  generator (commits `eb75dbaf1`, `550e3786b`, `87edac55a`, `8b2bb8e08`, `09883ae5a`,
  `8d43265ae`/`13d8c26a1` "disabling hallucinated moves when encore or taunt is active"), plus the
  `>getstate` / `>load` stream commands added in `sim/battle-stream.ts` and
  `server/chat-commands/core.ts` (`wang_fork_diffs.md:454–455, 510, 555–556, 661`).
- **Training-time:** `24a5e8ce4 "HACKY: clear players from room if username starts with train or
  eval"` and `81dd69cde "don't console.log DEINIT lol"` — a *server* hack that only makes sense if
  the forked server was also the training server. So: **the fork was used at both train and test
  time, but only the determinization half is search-specific.**

**(tree-verified) Serialization is upstream; the stream commands are not.** Our vendored PS 0.11.11
has `Battle.toJSON()` and `Battle.fromJSON()` (`showdown/sim/battle.ts:318–323`) and a
`deserialized` flag (`:75, :113, :215, :1904, :1969`), but `sim/battle-stream.ts`'s command switch
has no `getstate`/`load` case (cases present: `start, player, p1..p4, forcewin, forcetie, forcelose,
reseed, tiebreak, chat-inputlogonly, chat, eval, editbattle, requestlog, requestexport, requestteam,
show-openteamsheets, version`). Re-adding Wang's two commands is a small, well-scoped port if we
ever do search. This corroborates the prior-work index's line "(`>getstate`/`>load` stream commands
+ constrained team regen (the MCTS determinization — serialization itself is upstream Showdown)"
(`docs/prior_work/README.md:567–569`).

---

## 2. Observation design (Tables A.1 / A.2, pp. 40–42)

**(source-verified)** Total observation length **3725**, a single flat vector (p. 40, §A.0.1: "The
input to the neural network is a single vector of length 3725"). The arithmetic checks out exactly:
Table A.1's non-Pokémon block sums to **125** and the Pokémon block is **12 × 300 = 3600**;
125 + 3600 = 3725. Table A.2 sums to exactly **300**. (I summed both tables by hand; both close.)

### 2.1 The Markov-restoration principle (the transferable idea)

Verbatim (p. 23, §3): "Naively, Pokémon battles break the Markov assumption… some moves like Light
Screen and Rain Dance create conditions in the battle which last multiple turns. We account for this
by encoding the durations of multi-turn effects into the state. For example, since Light Screen
lasts a maximum of 8 turns, we associate with it a one-hot vector of size 10 in the state (each
dimension represents a number of turns between 0 and 8 inclusive, plus an extra dimension for No
Light Screen). With this modification, we restore the Markov assumption."

And the general rule (p. 40, §A.0.1): "Multi-turn effects with maximum duration k are generally
encoded using a k + 1-length onehot vector, with the extra dimension for when the effect is not
present." **Note the arithmetic does not quite match his own example** — Light Screen with max
duration k = 8 gets length **10**, not k+1 = 9, because he encodes 0..8 inclusive (9 values) *plus*
"not present". Read the rule as **k + 2** where k is the max duration, or as "one bin per attainable
counter value including 0, plus an absent bin". This matters when we size ours.

### 2.2 Table A.1 — battle-level features (p. 41), verbatim

| feature | length | domain | notes |
|---|---|---|---|
| sun | 9 | {0,1} | onehot: # turns, or Permanent |
| rain | 9 | {0,1} | onehot: # turns, or Permanent |
| hail | 9 | {0,1} | onehot: # turns, or Permanent |
| sandstorm | 9 | {0,1} | onehot: # turns, or Permanent |
| no weather | 1 | {0,1} | |
| trick room | 7 | {0,1} | onehot: # turns, or No Trick Room |
| force switch | 2 | {0,1} | e.g. used the move U-turn, fainted |
| # unknown | 7 | {0,1} | |
| stealth rock | 2·2 | {0,1} | onehot for each side |
| spikes | 2·4 | {0,1} | onehot for each side: # layers, or none |
| toxic spikes | 2·3 | {0,1} | onehot for each side: # layers, or none |
| reflect | 2·10 | {0,1} | onehot for each side: # turns, or none |
| light screen | 2·10 | {0,1} | onehot for each side: # turns, or none |
| safeguard | 2·7 | {0,1} | onehot for each side: # turns, or none |
| Pokémon | 12·300 | mixed | see Table A.2 |

**(source-verified)** The **weather "Permanent" bin** is explained on p. 40: "Weather, when summoned
by moves, can last 5 or 8 turns (or until overridden by a different weather), depending on the item
held by the move's user. On the other hand, weather caused by abilities (as opposed to moves) is
permanent until a different weather is imposed. **This permanence only occurs in Generations 3-5.**
Thus we add an extra onehot bin for each weather condition which signifies 'permanent' imposition of
that type of weather."

**(tree-verified) This is correct in our vendored simulator, and it is a gen4-only branch.**
`showdown/data/conditions.ts:646–652` (sandstorm) and `:674–681` (hail), verbatim:

```ts
onFieldStart(field, source, effect) {
    if (effect?.effectType === 'Ability') {
        if (this.gen <= 5) this.effectState.duration = 0;
        this.add('-weather', 'Sandstorm', '[from] ability: ' + effect.name, `[of] ${source}`);
    } else {
        this.add('-weather', 'Sandstorm');
    }
},
```

`duration = 0` means "no expiry". The 5-vs-8 turn move duration is also there
(`durationCallback` returning 8 with the appropriate rock item, else 5). **`# unknown` (length 7)** is
almost certainly the count of not-yet-revealed opponent Pokémon (0..6 = 7 bins); the thesis does not
say so explicitly — inference, flagged.

### 2.3 Table A.2 — per-Pokémon features, 12 slots × 300 dims (p. 42), verbatim

| feature | length | domain | notes |
|---|---|---|---|
| species | 1 | {0,1,…,295} | |
| ability | 1 | {0,1,…,100} | |
| item | 1 | {0,1,…,39} | |
| move | 4 | {0,1,…,198} | |
| ⌊∛(move PP)⌋/4 | 4 | {0, ¼, ½, ¾} | see State Binning |
| last used move | 1 | {0,1,…,198} | |
| type(s) | 18 | {0,1} | can have 1 or 2 types |
| current hp fraction | 7 | {0,1} | onehot; see State Binning |
| accuracy boost | 13 | {0,1} | onehot from -6 to +6 |
| atk boost | 13 | {0,1} | |
| ⋯ boost | 5·13 | {0,1} | def, evasion, spa, spd, spe |
| volatile effects | 2·38 | {0,1} | length-2 onehots for OFF or ON |
| encore | 9 | {0,1} | onehot: # turns or none |
| taunt | 6 | {0,1} | onehot: # turns or none |
| magnet rise | 7 | {0,1} | onehot: # turns or none |
| slow start | 6 | {0,1} | onehot: # turns or none |
| gender | 3 | {0,1} | onehot: male, female, neutral |
| status | 7 | {0,1} | onehot: all non-volatile statuses + FNT |
| toxic counter | 21 | {0,1} | onehot: # turns |
| sleep counter | 11 | {0,1} | onehot: # turns |
| log₁₀(weight) | 5 | {0,1} | onehot after rounding |
| log₁₀(height) | 4 | {0,1} | onehot after rounding |
| first turn | 2 | {0,1} | |
| protect counter | 6 | {0,1} | how many Protects in a row, max 5 |
| must recharge | 2 | {0,1} | due to Giga Impact |
| preparing | 2 | {0,1} | due to moves like Bounce |
| active | 2 | {0,1} | |
| is opponent | 2 | {0,1} | |
| unknown | 1 | {0,1} | If this is 1, all other values are 0. |

**(source-verified)** Binning rules, verbatim (p. 40, "State Binning"): "we divide a Pokémon's HP
into 1 special state for 0 HP and 6 equally-sized bins, regardless of its total HP, such that having,
e.g., 10% and 12% HP are treated as the same state. We also bin a move's PP… using the formula
⌊x^{1/3}⌋ (chosen because resolution matters more when a move has fewer uses left; inspired by
Deepmind's AlphaStar, which plays Starcraft II [27]), which gives a total of four bins since 64 is
the highest possible PP." Footnote 1 on the HP bins, verbatim: "Arbitrarily chosen to significantly
cut down on state space. Future work would explore more fine-grained bins, perhaps 16 bins since
that is the smallest increment of both healing from the popular item Leftovers and damage from being
poisoned by Toxic." So **HP = 7 bins = {0 HP} ∪ 6 equal bins**, confirming the Table A.2 row.

**(source-verified) Small internal inconsistency in the PP encoding.** Table A.2's stated domain
is {0, ¼, ½, ¾}, i.e. ⌊∛x⌋ ∈ {0,1,2,3} divided by 4 — but ⌊∛64⌋ = 4 → 1.0, which is outside the
stated domain. Either the cap is 63 PP in practice or the domain row is imprecise. Immaterial to us
except that we should decide the divisor deliberately.

**(source-verified) Species / ability / item / move / last-used-move are INDICES, not one-hots**
(domains {0..295}, {0..100}, {0..39}, {0..198}), consumed by `nn.Embedding` (p. 41, §A.0.2). This
contradicts the chapter-3 claim `s ∈ S ⊂ [0,1]^3725` (p. 23) — the observation is a *mixed*
index/float vector, and 8 of its 3725 slots per Pokémon (96 overall) are categorical ids outside
[0,1]. Cosmetic in the thesis; load-bearing for us, because an `EncoderSpec` that declares a
`[0,1]^N` box would be wrong for this design.

**(source-verified) Implied vocabulary sizes:** 296 species, 101 abilities, 40 items, 199 moves.
The move vocabulary (199) equals the action-space move block (199), so moves are indexed in one
shared identity space across observation and action.

**(source-verified) Unrevealed opponent information is handled by exactly two mechanisms**: the
battle-level `# unknown` count (7) and the per-Pokémon `unknown` flag ("If this is 1, all other
values are 0"). **There is no per-field unknown token.** The thesis never says how a *partially*
revealed opponent Pokémon is encoded — species known but item/ability/2 moves unknown is the
overwhelmingly common case, and Table A.2 offers no "unknown item" or "unknown move" symbol. Either
index 0 doubles as a null in each vocabulary (plausible, unstated) or partial knowledge is lost.
**Open question; unverified — no code on disk to check.**

**(source-verified) There is no belief / set-prior feature.** Nothing in Tables A.1/A.2 carries
randbats set frequencies, damage-roll ranges, stat estimates, type effectiveness, STAB, base power,
or move category. Every derived quantity our gen1 encoder precomputes is absent; the network sees
raw identities plus embeddings. (Contrast ps-ppo's `obs_pokemon.py` `stats_int` = 5 stats ×
(min, est, max), per `docs/prior_work/README.md:472–474` — literature-only, I did not re-read ps-ppo.)

**(source-verified) Slot semantics.** 12 slots × 300, each carrying its own `active` (2) and
`is opponent` (2) flags — so slot order is presumably [our 6 | their 6] with redundant flags, and
the acknowledgments credit Kairo Morton with "ideas on how to deal with symmetries in the state
representation" (p. 5). The thesis never states whether slots are sorted, fixed at team order, or
canonicalized. **Unverified.**

---

## 3. Action space and masking

**(source-verified) Identity-based, not positional.** Verbatim (p. 23): "a ∈ A = {0, 1, . . . , 494}:
The first 199 actions correspond to moves, while the latter 295 actions correspond to switching to
another Pokémon. On any given turn, up to 9 actions are valid (up to 4 moves and up to 5 possible
switches); the rest get masked out (see subsection 3.1.3)."

**(source-verified) The thesis is internally inconsistent about the size, three ways:**
`{0,…,494}` is **495** actions; `199 + 295` = **494**; and p. 27 refers to "a length-496
distribution over actions". Most likely reading: 199 move ids + 296 switch targets (one per species,
matching the 296-species pool) = 495 = |{0,…,494}|, and "295" on p. 23 is a typo. **The prior-work
index's "494-way identity space" (`docs/prior_work/README.md:490–493`) is the sum of the two stated
components; it is defensible but the thesis's own set notation says 495.** Quote it as "≈495-way,
identity-based (thesis internally inconsistent: 494 / 495 / 496)".

**(source-verified) Masking.** Verbatim (p. 25, §3.1.3): "Drawing from previous work [16][23], we
mask out all invalid actions by setting their corresponding output logits to `-float("inf")` before
the final softmax layer. We use the action masks while collecting trajectories, then save them to be
applied once again during gradient updates, in particular when calculating the probability that the
updated policy would have chosen the saved actions."
**Cross-ref to our harness contract:** same two-place masking discipline we enforce
(`CLAUDE.md`: "Action masking is a harness contract… masking applies at eval too"), but he uses a
true `-inf` where our contract mandates the finite `-1e8` sentinel. With ~486 of 495 logits masked
every turn, `-inf` is the risky choice, not the safe one.

---

## 4. Reward

**(source-verified)** Verbatim (p. 23): "r ∈ {−1, 0, 1}: The reward is 1 on a turn where the agent
wins (causes all opposing Pokémon to faint), -1 on a loss, and 0 on any other turn (including ties)."
**Terminal-only, zero-sum, ties scored 0. No shaping of any kind** — no faint bonus (contrast H&L's
5-term shaping, `docs/prior_work/README.md`), no HP-delta term. With γ = 0.9999 over ~25-turn / ~50-step
episodes this is effectively undiscounted (0.9999^50 ≈ 0.995).

---

## 5. Hyperparameters — Table A.3 verbatim (p. 43)

| parameter | value | description (verbatim) |
|---|---|---|
| `learning_rate` | 10⁻⁴·²³ | annealing rate not tuned; see subsection 3.1.4 |
| `n_epochs` | 7 | # gradient descent passes over a given batch of data |
| `gamma` | 0.9999 | discount factor |
| `gae_lambda` | 0.754 | trades off between bias (λ = 0) and variance (λ = 1)[19]. |
| `clip_range` | 0.0829 | smaller value will clip the prob. ratio more aggressively |
| `clip_range_vf` | 0.0184 | |
| `entropy_coef` | 0.0588 | weight of entropy term in loss |
| `value_coef` | 0.4375 | weight of value function loss |
| `max_grad_norm` | 0.5430 | limit to norm of gradient update |
| `n_steps` | 78 · 512 | # steps experience to collect to train; 78 is # workers |
| `batch_size` | 1024 | |
| `features_dim` | 896 | |
| `hidden_dim` | 256 | |

Corroborating numbers elsewhere in the text: p. 30 states "the weights c₁ = 0.4375, c₂ = 0.0588 are
tuned hyperparameters" — matching `value_coef` and `entropy_coef`. 10⁻⁴·²³ = **5.888 × 10⁻⁵**.

**LR schedule, verbatim (p. 25, §3.1.4):**

> The learning rate was annealed (lowered) smoothly, according to the formula
> ℓ(x) = 10⁻⁴·²³ / (8x + 1)^{1.5}
> where x denotes the training progress as a floating point number from 0 to 1.

So ℓ(0) = 5.888e−5 and ℓ(1) = 5.888e−5 / 9^1.5 = 5.888e−5 / 27 = **2.181e−6** — a 27× decay.

**The LR-anneal ablation, verbatim (p. 25):** "Learning rate annealing had a massive impact on
performance of the neural network. With a constant learning rate, the validation winrate was stuck
at around 55%, compared to 80% after annealing the learning rate. The learning rate decay constants
8 and 1.5 were chosen after a few manual runs, rather than tuned with other hyperparameters; future
work might more properly tune them, given the empirical importance of learning rate annealing to the
neural network's strength."

**(source-verified) Caveats on that ablation, which the index's "constant 0.55 → annealed 0.80" line
does not carry:** it is **n = 1 vs n = 1**, no seeds, no error bars, no statement of the constant
LR's value, no statement of the step budget of the constant-LR run, and it is a comparison of
*validation curves* (200 games/point) not of a locked eval protocol. It is still the only controlled
LR-annealing datapoint in this literature — but it would not clear our own credit line as a *result*;
it clears as a *prior*. The 0.80 figure also matches the Figure 4.1 curve at ~40M, not its 150M
endpoint (see §7).

**(source-verified) Figure 3.1's caption records a training accident**, verbatim (p. 26): "A mistake
was made while resuming training at 100M steps which caused the learning rate to suddenly dip, then
continue slowly decreasing. We do not believe this had any noticeable impact on the final agent's
strength." (My digitization of Fig 4.1 agrees: 0.837 at 100M, 0.849 at 120M, 0.836 at 140M — no
visible discontinuity.)

### 5.1 Steps per update, and the "half-full buffers" ambiguity

**(source-verified)** `n_steps = 78 · 512 = **39,936** steps per update` (78 workers × 512 steps per
worker). But §3.1.5 (p. 25) describes an *asynchronous* collector, verbatim: "Training proceeded with
39 games (78 workers) being played in parallel. A separate rollout buffer was kept for each worker,
and environments were not required to act in lockstep with each other. **Once at least half of the
rollout buffers were full**, returns and advantages were computed, followed by 7 epochs of gradient
descent over the batched data." So the *effective* batch per update is somewhere between ~20k and
39,936 steps and the thesis never pins it. Treat 39,936 as an upper bound.

Derived, at face value: 150M / 39,936 ≈ **3,756 updates**; 39,936 / 1024 ≈ 39 minibatches × 7 epochs
= **273 gradient steps per update**; at ~25 steps per seat-episode, **≈1,597 seat-episodes ≈ 799
battles per update**. **Cross-ref:** this reproduces the "~1,600" in `docs/prior_work/README.md`'s
episodes-per-update discussion (H&L 15,360 ≫ Wang ~1,600 ≈ ps-ppo ~1,500 ≫ ours ~34).

---

## 6. Training scale, SB3, seeds

**(source-verified)** Verbatim (p. 24, §3.1): "The neural network was trained for **150M steps
(approximately 3 million battles, since the average battle lasted 25 steps and experience was
collected from the perspective of both players) over 4 days** via PPO, with rollout trajectories
collected via self-play. In each game played during training, both players used the most recent
iteration of the policy, and both players recorded the trajectory for learning. In other words, each
game played produced two games for the algorithm to learn from."
**So: pure mirror self-play, latest-vs-latest, both seats harvested, no opponent pool, no league, no
BC init, no curriculum.** (This is the same seat-accounting shape as H&L; per-battle both-seat
harvesting means his "150M steps" is a learner-consumed number, ≈75M per-seat env decisions.)

**(source-verified) Hardware**, verbatim (p. 24, §3.1.1): "The neural network was trained using a
single NVIDIA A6000 48G GPU and 80 CPU workers with at most 1G of RAM used by each." (Table A.3 says
78 workers; p. 24 says 80 CPU workers — the extra two are presumably the driver/aggregator.)

**(source-verified) Architecture** (p. 41, §A.0.2), verbatim: "A feature extractor, which converts
indices (for species, abilities, items, moves) into tensors via learned `nn.Embedding` layers, and
projects to a length 896-vector for each Pokémon as well as for the overall battle, for a total
output length of 13 · 896. • A 3-layer MLP with hidden dimension 256 and ReLU activations. • An
actor head, composed of a 2-layer MLP followed by projection to a distribution over the action space.
• A critic head, composed of a 2-layer MLP followed by projection to a scalar estimate of the state
value." Note **13 × 896 = 11,648** features into a 256-wide 3-layer trunk — a >45× width collapse at
the first layer; parameter count is never reported.

**(source-verified, from the forks) SB3.** The thesis never names Stable-Baselines3, but
(i) `wang_fork_diffs.md:3993–4008` shows an 8-commit `stable-baselines3` fork whose entire content is
logging/timing instrumentation (`record fps for rollout only`, `track rollout, train, callback time
separately`, `add csv logging`, `train_fps should * n_envs`, `pass monitor_wrapper kwarg`), and
(ii) Table A.3's parameter names are literally SB3's `PPO` kwargs (`n_steps`, `batch_size`,
`n_epochs`, `gamma`, `gae_lambda`, `clip_range`, `clip_range_vf`, `max_grad_norm`, and
`features_dim`/`net_arch`-style policy kwargs). **JOURNEY step 5's "he ran SB3" is correct but must
be sourced to the fork, not to the thesis.**

**(source-verified) Seeds and error bars: NONE, anywhere.** One training run. Table 4.1 reports no n
and no interval; Table 4.2 reports raw W–L; §4.3 reports a single 200-game ladder run. Figure 4.1 is
a single run's validation curve (smoothed line + raw band). The word "seed" does not appear in the
thesis.

**(source-verified, inference) Table 4.1's n is probably 1000.** All ten entries are 3-decimal
(.809, .908, .996, .191, .786, .088, .206, .992, .004, .007); .809 is not a multiple of 1/500 or
1/250, and .004 = 4/1000 — n = 1000 fits every cell. **Inference, not a stated number.** At n = 1000
the binomial se is 0.013.

---

## 7. Results

### 7.1 Table 4.1 (p. 30) verbatim — "Winrates Versus Reference Bots"

| | MCTS + NN | NN | Heuristic | Random |
|---|---|---|---|---|
| **MCTS + NN** | — | .809 | .908 | .996 |
| **NN** | .191 | — | **.786** | 1. |
| **Heuristic** | .088 | .206 | — | .992 |
| **Random** | .004 | 0. | .007 | — |

Caption note, verbatim: "Some head-to-head winrates don't add up to 1, because of ties."

**Search is worth +12.2 points vs SH** (.908 with MCTS vs .786 without) and **+.809/-.191 head to
head vs its own network**, with an explicit inflation caveat, verbatim (p. 32): "Note that we believe
the winrate of the full agent with MCTS vs NN to be somewhat 'inflated'. Recall that during MCTS, we
assume our opponent plays according to the NN policy, and search for the best response. Then,
because in essence the MCTS always knows exactly what the NN will do, its winrate when playing
against NN is higher than when playing against humans of equivalent strength to NN."
**Cross-ref for `search_depreciation.md`:** the honest search-gain estimate against a *non-self*
opponent is the SH column (+12.2 pts, .786 → .908), not the .809 self-play column.

Also useful as anchor calibration: **SimpleHeuristicsPlayer beats Random .992** and **Random beats SH
.007** in gen4 (ties account for the residual).

### 7.2 Figure 4.1 (p. 29) — the validation curve, and the unreconciled 0.786 vs ~0.85

Prose, verbatim (p. 29, §4.1): "By our validation metric, the neural network made most of its
progress within the first 40M steps (1 day) of training, quickly reaching 80% winrate against
SimpleHeuristicsPlayer. After 150M total steps (4 days) of training, we reach slightly more than
that, roughly 85%."

Validation protocol, verbatim (p. 24, §3.1.2): "During training, the neural network was validated
every 20,000 steps. The sole validation metric was the agent's winrate over 200 games against
SimpleHeuristicsPlayer [22], an open-source bot which takes into account hazards and setup moves,
while also switching out of bad matchups, **equivalent in skill to a beginner Pokémon player**. This
proved to be a useful metric, especially early on in experimentation, since SimpleHeuristicsPlayer
is weak enough that any amount of useful learning is reflected in winrate against it, but strong
enough not to get completely dominated throughout the training process (**the winrate never
surpassed 90%**)."

**Figure 4.1 digitization (source-verified; my own measurement, scripts named above).** I converted
the page crop to BMP with `sips`, located the axis gridlines by pixel run-length (x: 0 → px 270.5,
20M → px 428.0; y: 0.8 → px 200, 0.6 → px 323), and took the centroid of dark-curve pixels per
column. Reading the **smoothed** line:

| steps | 1M | 2M | 3M | 4M | 5M | **6M** | 7M | 8M | 10M | 12M | 15M | 20M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| winrate | .180 | .298 | .414 | .497 | .539 | **.575** | .612 | .636 | .682 | .707 | .737 | .759 |

| steps | 30M | 40M | 50M | 60M | 80M | 100M | 120M | 140M | 148M |
|---|---|---|---|---|---|---|---|---|---|
| winrate | .786 | .797 | .814 | .821 | .837 | .837 | **.849** | .835 | .836 |

**This exactly reproduces the prior-work index's "~0.575 at 6M steps"** (`docs/prior_work/README.md:396`)
— that number is a Figure 4.1 digitization, and it is right. Two further facts fall out:
- The curve's **endpoint is ≈0.836, its peak ≈0.849 near 120M**. The prose's "roughly 85%" is the
  peak, not the endpoint; the honest Fig-4.1 final number is **~0.836**.
- **0.786 — the Table 4.1 number — is exactly the Fig 4.1 curve at 30M steps.** Suggestive, but the
  thesis never says Table 4.1 used an early checkpoint, and §4.2 explicitly evaluates "the full
  agent (MCTS + NN)" and "NN: The neural network policy playing on its own" as final artifacts.

**Reconciliation attempt — what the text supports and what it does not (source-verified):**
- **NOT 3v3 vs 6v6.** §A.0.3 says 3v3 was used only for Bayesian HPO.
- **NOT ties.** NN-vs-Heuristic .786 and Heuristic-vs-NN .206 sum to .992, so ties are ~0.8% — an
  order of magnitude too small to close a 5-point gap.
- **NOT the 100M LR accident.** The digitized curve shows no drop there; 140M reads .835.
- **Probably not sampling noise.** At the inferred n = 1000, se = 0.013, so .786 vs .836 is ~3.8 se.
  At n = 200 (the validation n) se = 0.028 and it would be ~1.8 se — but Fig 4.1's *smoothed* line
  averages many 200-game points, so the comparison is against a low-variance estimate.
- **Candidates the thesis leaves open, in my order of plausibility:** (1) a different action-selection
  mode — Fig 4.1 validation may sample from π while Table 4.1 is greedy, or vice versa; the thesis
  states neither for either number, and it never uses the words "deterministic"/"greedy" about
  evaluation. (2) A different SH configuration or a different (possibly patched) poke-env between the
  in-training validation harness and the post-hoc evaluation harness — his poke-env fork *does* patch
  `SimpleHeuristicsPlayer` twice (`1799235 Ignore Curse "???" type in HeuristicPlayer`, `e806b20
  opp_remaining_mons bug in HeuristicsPlayer`, `11fb65b/547674a SimpleHeuristicPlayer should respect
  maybe_trapped`), so *which* SH each number was measured against is genuinely underdetermined.
  (3) Table 4.1 used an earlier checkpoint.
- **Verdict: the gap remains unreconciled from the text.** The prior-work index's flag stands. For
  JOURNEY step 5's "pin the target before starting" ruling, my recommendation is in §11.

**(source-verified) Arithmetic tension in the validation cadence, worth flagging.** Taken literally,
"validated every 20,000 steps… over 200 games" across 150M steps means 7,500 validations × 200 games
= **1.5M validation battles against 3M training battles** — a 50% eval tax, which is implausible. The
consistent reading is that "20,000 steps" is *per worker* (78 × 20,000 ≈ 1.56M global steps → ~96
validations ≈ 19,200 battles). The thesis does not disambiguate. **Relevant to us because our own
eval cadence is a live cost question.**

### 7.3 Ladder (p. 32, §4.3) — exact numbers

Verbatim: "After 200 games played on the Pokémon Showdown ladder with the username `ihtfp_abra`, the
agent displays an average performance around **1615 Elo**¹, peaking at **rank 8 (1693 Elo, 1756 ± 28
Glicko-1, 79.5% GXE)**. This is the best known rank achieved by any non-human agent in
gen4randombattles." Footnote 1, verbatim: "average taken after game 100, to exclude the period where
it was climbing".

**The laddered agent is the FULL agent, MCTS included** — the abstract (p. 3) says "We demonstrate an
agent which employs a Monte Carlo Tree Search informed by a actor-critic network trained using
Proximal Policy Optimization… The agent peaked at rank 8 (1693 Elo)", and §4.2 defines "the full
agent (MCTS + NN)". **Confirms JOURNEY.md:63** ("His rank 8 / 1693 Elo / 79.5% GXE is the searched
agent"). Note also that **1756 ± 28 is a *peak*, not an endpoint**, n = 200, one account, one run —
the same shape of number as our own R1/R3 ladder rows, so it is comparable in kind, but the prior-work
index's ladder table row "Wang 2024 | Gen4RB | 1756 | 79.5%" is quoting a peak against our
stopping-rule endpoints. Worth a footnote wherever that table is reused.

### 7.4 Expert evaluation (Table 4.2, p. 33) — verbatim

| Username | Credentials | W-L vs. bot |
|---|---|---|
| WhatColorIsThis? | rank 6, gen4randombattles | 2-1 |
| arolakiv | top 50, gen7randombattles | 3-1 |
| Star Thunderbolt | rank 1, gen8randombattles | 4-11 |

Expert long-run self-estimates against the bot: "maybe 50 or 60" / "50" / "in theory slightly over
50" (p. 34). Star Thunderbolt: the bot is "very good but not elite" (p. 35). Behavioural praise
(p. 33): "good in preserving what it needed to win; but when its in a bad position it gets pretty
predictable" and "having stuff saved in the back". Two case studies: a bad switch (Kecleon →
Venomoth into a Rampardos, p. 33 — "around 37.4% of Rampardos have the move Superpower"), attributed
to the opponent model, and a "bait-and-switch for marginal gain" double-switch praised as
near-mixed-strategy play (p. 34).

---

## 8. MCTS at test time (§2.3, §3.2, pp. 20–28)

**(source-verified) Not AlphaZero.** Verbatim (p. 23): "our approach diverges from that of AlphaZero
in that MCTS is not used to train the neural network. Instead, the neural network is trained via PPO,
then **MCTS is used purely at inference time as a policy improvement operator**. This was done
because simulating the environment is very slow, compared to a game like chess; generating gameplay
using MCTS would not likely lead to enough samples for a neural network to converge, given the
computational constraints of the present work."

**Tree policy, verbatim (p. 21):** `a_t = argmax_a (Q[s_t,a] + α · U(s_t,a))` with
`U(s,a) = P[s,a]^β · √(M[s]) / (N[s,a] + 1)`, "and hyperparameters α, β ∈ [0,1] dictate how much to
value exploration and how much to trust the neural network policy, respectively". Footnote 3: "The
tree policy used is similar to that used in AlphaZero [21], except that α is a constant instead of a
function of M[s] and β is introduced." **α and β are never given numeric values anywhere in the
thesis** — a genuine reproducibility hole.

**Backup, verbatim (p. 21):** rollouts stop at a terminal node (v = +1/−1/0 for win/loss/tie) **or at
a leaf** (v = V_θ(s_T), the critic). Updates: `Q ← (N·Q + v)/(N+1)`, `N ← N+1`, `M ← M+1`. Root
choice, verbatim (p. 22): "we choose the action with the greatest visit count from the root node:
a* = max_a N(s₀,a)… It is intuitive to choose the action with the largest Q value instead, but
less-visited actions may have higher variance in their Q estimates."

**Budget, verbatim (p. 27, §3.2.3):** "By parallelizing search and controlling tree size, we usually
achieve a number of rollouts **R between 1000 and 2000 within 10 seconds**, depending on the length
of each rollout and size of the game tree being tracked." Parallelism: "MCTS is performed with **20
workers**… After finishing **10 rollouts**, a worker sends the 'tree'… to the master process, which
aggregates the results into a master copy." The prior dictionary P is deliberately not shipped
between processes: "it is computationally very cheap to recompute the neural network probabilities;
**the speed of each rollout is bottlenecked by the environment stepping, not GPU inference**." Tree
size control uses `F[s]`, the total fainted count (monotone non-decreasing), to prune every state
with `F[s'] < f₁`; "the number of nodes stored at any given time varies between **2,000 and
15,000**" (p. 28).

**Determinization, verbatim (p. 26–27, §3.2.2):** "We address this by **sampling one possibility for
all unknown opponent information at the start of each MCTS trajectory**. This is possible because we
have access to the exact procedure by which Pokémon Showdown generates randombattles teams. For
unknown Pokémon, the server generates a new Pokémon and its set, and adds it to the opponent team.
For known Pokémon, the server attempts to generate a valid set consistent with the known traits of
the Pokémon. It does this through **rejection sampling**: generating random sets until one satisfies
the constraints formed by known traits. It can be difficult to sample a valid set, because some sets
are modified based on traits of the Pokémon's team… **If after 10 attempts we do not generate any
valid sets, we 'force' the known information to be in the set, randomly filling in unknown
information with no regard for compatibility.**" (One determinization per *rollout*, not per search —
so expectation over hidden info is taken across the 1000–2000 rollouts.)

**Opponent model, verbatim (p. 26, §3.2.1):** "During MCTS, we model the opponent's decisions using
the trained neural network policy. This has the benefit of simplicity, but weakens the agent's
performance against players who play differently from the neural network."

**(tree-verified) The determinization premise has changed under us.** Wang's rejection sampler is
expensive because 2023-era gen4 randbats generated sets procedurally from movepools. Our vendored
PS 0.11.11 gen4 is a **curated set table**: `showdown/data/random-battles/gen4/teams.ts:44–45`
reads `override randomSets … = require('./sets.json')`, and that file holds **295 species / 464 total
sets, min 1, max 3, median 2, mean 1.57 sets per species** (counted with stdlib `json` under
`nice -n 19`). Compare Wang p. 15, verbatim: "6 possible sets for each Pokémon species… This figure
was obtained empirically by generating 2.6 million teams (15.7 million sets) using Pokémon Showdown's
team generator. The number of sets for a given Pokémon **ranges from 1 to 56**, distributed close to
exponentially with **an average around 8**, but we conservatively take the median 6". **The generator
he measured is not the generator we would run.** Consequences: (i) his game-tree lower bound
(6.175·10³⁴ starting states, 1.365·10⁸⁸ total, p. 15) does not transfer; (ii) a modern determinizer
should **enumerate** the ≤3 candidate sets per species and weight them, not reject-sample; (iii) the
opponent-set belief state is far smaller and far more learnable than in 2023 — which strengthens the
case for a belief/set-prior feature in the encoder and weakens the case for search.
**Cross-ref: `mechanics_delta.md`, `encoder_requirements.md`, `search_depreciation.md`.**

---

## 9. Negative results

**(source-verified) §5.1.3 "Recursive Learning" is a single negative result, and it is BOTH of the
two things our docs list separately.** Verbatim (p. 37): "Imagine that you have trained 6 actor-critic
networks (π₁,v₁),…,(π₆,v₆), where (π_k,v_k) specializes in Pokémon battles with teams containing k
Pokémon… Whenever a game devolves into the 1v1 case, say at time t, one can simply use v₁(t) as an
estimate of the return from that point on, saving time by truncating each episode and training
(π₂,v₂) only on timesteps where some team still has 2 Pokémon… **We attempted such a setup, but saw
no significant improvements over simply training a 6v6 from scratch, in either training efficiency or
strength of the trained agent.**" Two hypothesized causes are given: out-of-distribution states in
the smaller sub-game (his Pikachu-poisoned-by-a-fainted-Muk example), and "π₄ might not actually be
all that different from π₃ except for the size of their state spaces; strategies involving more than
3 Pokémon are seldom employed".

**This is NOT an opponent-pool curriculum, and the thesis contains no curriculum experiment of any
kind.** The index's "Curriculum negative result (§5.1.3)" (`docs/prior_work/README.md:399`) and JOURNEY's
"Wang tried a bootstrapping variant and reported no significant improvement (§5.1.3)"
(`JOURNEY.md:118`) are **the same experiment described two different ways** — a hierarchical /
value-bootstrapping transfer scheme across team sizes. Neither wording is wrong, but reading them as
two independent negative results would double-count one n = 1 anecdote. It also carries **no numbers
at all** — no win rates, no curves, no seeds. Treat as an anecdote, not a measurement.

**Other negatives / caveats recorded in the thesis:**
- Constant LR plateaued at ~55% vs ~80% annealed (§3.1.4, p. 25) — see §5.
- MCTS-vs-NN .809 is "inflated" because the searcher's opponent model *is* the opponent (p. 32).
- The opponent model causes concrete misplays against humans who play off-policy (p. 33–34).
- "the winrate never surpassed 90%" against SH (p. 25) — the SH anchor saturates.
- Figure 4.2 (p. 30–31): total loss *rose* throughout training; explained as entropy loss rising as
  the policy sharpens plus policy loss rising as advantages shrink. Worth remembering the next time
  one of our loss curves rises.

---

## 10. What the thesis says about poke-env state-tracking bugs: **nothing**

**(source-verified)** The thesis never mentions a poke-env bug, patch, or fork. `poke-env` appears
once, as reference [22] (p. 45), cited only as the provenance of `SimpleHeuristicsPlayer`. Everything
we know about his 36 fixes comes from `docs/prior_work/wang_fork_diffs.md:3411–3450`.

**(source-verified) The gen4-relevant fixes in his poke-env fork**, commit-log verbatim:
`2b407c3 gen 4 moves Max PP` · `aa8acaf Fix Sleep Talk PP subtracted twice per use` ·
`1799235 Ignore Curse "???" type in HeuristicPlayer` · `e806b20 opp_remaining_mons bug in
HeuristicsPlayer` · `0ed9928 Weather caused by abilities lasts indefinitely in gen4` ·
`35d43ec sleep counter should only increment once on sleep talk` · `1b00e90 fix move revealed by
sleeptalk not getting PP used` · `0e01065 fix sleep talk PP usage` · `8db0846 fix handling battle
requests too early when forceSwitch` · `b4ad51e parse base ability Trace` · `7f8da8a _orig_ability,
_orig_item` · `3cc6cd6 prepare moves deducting PP twice` · `48b63f5 trim [from]lockedmove from
messages` · `4bcf47c base ability` · `558b0ab fix _force_switch was parsed as list` ·
`f3eac47 fix _TURN_COUNTER_EFFECTS -> _ACTION_COUNTER_EFFECTS for is_action_countable` ·
`11fb65b/547674a SimpleHeuristicPlayer should respect maybe_trapped` · `d69b7fc make RandomPlayer
respect maybe_trapped` · `471cffb add ._revealed for Move`.

**Two spot-checks against our pinned poke-env 0.15.0 (source-verified), because they land directly on
Table A.1 features:**

1. **Ability-set weather permanence did NOT survive upstreaming.** Wang's patch
   (`wang_fork_diffs.md:3568–3578`) branches on the message tail:
   ```python
   elif split_message[3].split(' ')[0] == '[from]':
       self._weather = {Weather.from_showdown_message(weather): -1}   # permanent
   elif split_message[3] == '[upkeep]':
       return                                                          # do NOT restamp the turn
   ```
   Our 0.15.0 has neither branch — `poke_env/battle/abstract_battle.py:755–761` is, verbatim:
   ```python
   elif event[1] == "-weather":
       weather = event[2]
       if weather == "none":
           self._weather = {}
           return
       else:
           self._weather = {Weather.from_showdown_message(weather): self.turn}
   ```
   **(tree-verified) Showdown emits `|-weather|<W>|[upkeep]` every residual turn**
   (`showdown/data/conditions.ts:507, 539, 585, 621, 656, 681` for rain/primordialsea/sun/
   desolateland/sandstorm/hail) **and `|-weather|<W>|[from] ability: …` on ability-set weather**
   (`:500, 535, 574, 613, 649, 679`). Therefore **in poke-env 0.15.0 `battle.weather[W]` is restamped
   to the current turn every single turn, so "turns of weather active" derived from it is always 0,
   and permanent (ability) weather is indistinguishable from move weather.** Both of Wang's weather
   features (`# turns` and `Permanent`) are unimplementable on stock 0.15.0. This is the single most
   concrete gen4 encoder blocker I found. **Cross-ref: `pokeenv_gen4_survey.md`,
   `encoder_requirements.md`.** *(needs-live-verification for the end-to-end claim: replay a gen4
   battle with a Tyranitar/Hippowdon and assert `battle.weather` values across turns — barred until
   the ladder run completes.)*
2. **`maybe_trapped` exists in 0.15.0** (`battle/battle.py:29,85,131,242–248`;
   `battle/abstract_battle.py:91,1482`; `battle/double_battle.py:45,143,247,529–535`), so that half of
   his fork is upstream. Whether `SimpleHeuristicsPlayer` *respects* it in 0.15.0 I did not verify
   line-by-line — `player/baselines.py` uses `battle.available_switches` at `:226,:277,:354–355`
   without a visible `maybe_trapped` guard, which suggests his SH patch did **not** survive. Flagged
   as **unverified**; it matters because it changes what our gen4 SH anchor actually is.

**JOURNEY.md:40's list is accurate** ("Max PP, Sleep Talk double-decrementing, weather-from-abilities
persistence, sleep counters, Trace base-ability parsing, maybe_trapped, _force_switch as a list") —
every item appears verbatim in the commit log. Its instruction ("Diff it against our pinned 0.15.0
and check which survived upstreaming") is the right one and is **not yet done**; I did 2 of ~19.

---

## 11. The discrepancy the task asked me to resolve

**Claim under test (from the session brief): "Wang: gamma = 1.0 / lambda = 0.95 at 128k steps/update".**

**(source-verified) That is wrong on all three numbers, and the first two belong to a different
paper.** Table A.3 (p. 43) says **`gamma 0.9999`**, **`gae_lambda 0.754`**, **`n_steps 78 · 512 =
39,936`**. γ = 1.0 / λ = 0.95 is **VGC-Bench's** recipe, recorded in our own index as such:
`docs/prior_work/README.md:406–409`, verbatim — "Their recipe (Table 7): gamma 1.0, lambda 0.95, ~3k
steps/update — **OUR gamma/lambda, not Wang/ps-ppo's 0.75**". No quantity anywhere in the thesis is
128k; the nearest is 39,936 steps per update (upper bound; §5.1 above explains the "half the buffers"
ambiguity). I could not find any source for "128k".

| document | claim about Wang | verdict |
|---|---|---|
| session brief | γ 1.0, λ 0.95, 128k steps/update | **WRONG** — γ/λ are VGC-Bench's (index line 406–409); 128k is unsourced. Thesis: γ 0.9999, λ 0.754, 39,936 steps/update (Table A.3, p. 43). |
| `JOURNEY.md:47` (step 4) | γ 0.9999, λ 0.754, 7 epochs, clip 0.0829, value clip 0.0184, ent 0.0588, vf 0.4375, grad-norm 0.543, n_steps 78×512, batch 1024, hidden 256, features 896, LR 10^-4.23/(8x+1)^1.5 | **CORRECT, every value, verbatim against Table A.3 + §3.1.4.** |
| `docs/IDEAS_POST_100M.md:180` | "ps-ppo 0.75 and Wang 0.754 sit against VGC-Bench at γ1.0/λ0.95" | **CORRECT** for Wang's λ. |
| `docs/prior_work/README.md:396` | "~0.575 at 6M steps" | **CORRECT** — reproduced by my Figure 4.1 digitization (0.575 at 6M). |
| `docs/prior_work/README.md:395–396` | "Pure network 0.786 vs SimpleHeuristics (Table 4.1; Fig 4.1 says ~0.85 — unreconciled)" | **CORRECT and still unreconciled**; refine "~0.85" to "peak 0.849 at ~120M, endpoint ~0.836". |
| `docs/prior_work/README.md:490–493` | "Wang's 494-way identity space" | **Substantively correct** (identity-based, ~500-way) but the thesis says `A = {0,…,494}` = 495 and once "length-496"; quote with the inconsistency. |
| `docs/prior_work/README.md:399` + `JOURNEY.md:118` | "Curriculum negative result (§5.1.3)" / "bootstrapping variant… no significant improvement (§5.1.3)" | **Both refer to the SAME single experiment** (hierarchical team-size transfer). Do not count as two. |
| `docs/prior_work/README.md:123` (ladder table) | "Wang 2024 · Gen4RB · 1756 · 79.5%" | **Correct numbers, but they are a PEAK** (rank-8 moment), not an endpoint; his 200-game average was ~1615 Elo. |
| `JOURNEY.md:53` | "he ran Stable-Baselines3 with its defaults" | **Half-right.** SB3 is source-verified from the fork, not the thesis — but "with its defaults" is wrong: Table A.3's 13 values are Bayesian-tuned, not SB3 defaults (SB3 PPO defaults are lr 3e-4, n_epochs 10, γ 0.99, λ 0.95, clip 0.2, ent 0.0, vf 0.5, grad-norm 0.5). The honest disclosure is "he ran SB3's PPO *implementation*", which is the real confound. |

---

## 12. Required table — every hyperparameter JOURNEY step 4 proposes to copy

| JOURNEY step 4 proposes | thesis value and location | agrees? |
|---|---|---|
| γ 0.9999 | `gamma 0.9999`, Table A.3, p. 43 | ✅ exact |
| λ 0.754 | `gae_lambda 0.754`, Table A.3, p. 43 | ✅ exact |
| 7 epochs | `n_epochs 7`, Table A.3, p. 43 (also §3.1.5, p. 25: "7 epochs of gradient descent") | ✅ exact |
| clip 0.0829 | `clip_range 0.0829`, Table A.3, p. 43 | ✅ exact |
| value clip 0.0184 | `clip_range_vf 0.0184`, Table A.3, p. 43 | ✅ exact |
| ent 0.0588 | `entropy_coef 0.0588`, Table A.3, p. 43; corroborated as `c₂ = 0.0588` on p. 30 | ✅ exact |
| vf 0.4375 | `value_coef 0.4375`, Table A.3, p. 43; corroborated as `c₁ = 0.4375` on p. 30 | ✅ exact |
| grad-norm 0.543 | `max_grad_norm 0.5430`, Table A.3, p. 43 | ✅ exact |
| n_steps 78×512 | `n_steps 78 · 512`, Table A.3, p. 43 ("78 is # workers") | ✅ exact — **but** §3.1.5 (p. 25) fires the update "once at least half of the rollout buffers were full", so 39,936 is an upper bound on the real per-update batch. Copying it needs a ruling on which we mean. |
| batch 1024 | `batch_size 1024`, Table A.3, p. 43 | ✅ exact (minibatch; ≈39 minibatches × 7 epochs = 273 grad steps/update) |
| hidden 256 | `hidden_dim 256`, Table A.3, p. 43; §A.0.2 "A 3-layer MLP with hidden dimension 256 and ReLU activations" | ✅ exact |
| features 896 | `features_dim 896`, Table A.3, p. 43; §A.0.2 "projects to a length 896-vector for each Pokémon as well as for the overall battle, for a total output length of 13 · 896" | ✅ exact — **but note it means 13×896 = 11,648 into a 256-wide trunk.** Copying "896" without the 13× fan-in copies the wrong thing. |
| LR 10^-4.23/(8x+1)^1.5 | §3.1.4, p. 25, verbatim; `learning_rate 10⁻⁴·²³`, Table A.3 | ✅ exact. ℓ(0)=5.888e−5 → ℓ(1)=2.181e−6 (27× decay). "The learning rate decay constants 8 and 1.5 were chosen after a few manual runs, rather than tuned" (p. 25). |
| *(not in JOURNEY)* MCTS α, β | §2.3 p. 21 — **never given numerically** | ⚠️ unreproducible if we ever do search |
| *(not in JOURNEY)* Bayesian-opt search space / trial count | §A.0.3 p. 41 — **not given** | ⚠️ his tuning is not reproducible; the 13 values are a point, not a recipe |

**One caution the table cannot carry:** every value above was tuned by Bayesian optimization **on the
3v3 surrogate** (§A.0.3), against **his** encoder (3725-d flat, identity actions, index embeddings),
**his** batch shape (~40k steps/update, ~1,600 seat-episodes), and **SB3's PPO implementation**. λ =
0.754 with γ = 0.9999 and 273 grad steps per 40k-step batch is a coupled operating point. Copying
γ/λ into our ~1k-step/34-episode updates is not the same experiment — JOURNEY step 4's instinct is
right (better than a from-scratch guess) but the batch-shape term should travel with it or be
explicitly held out.

---

## 13. gen1 encoder assumptions this breaks

Our gen1 encoder is 828-d with a frozen `EncoderSpec` seam (`rl/envs/encoder_spec.py`, main@2738025
— referenced from the brief; I did **not** open it this session, so every statement below is about
*documented gen1 assumptions*, not about that file's contents, and is flagged accordingly).

1. **"No items, no abilities" (gen1 truth) → 40 item ids + 101 ability ids per Pokémon in Wang's
   design** (Table A.2). These are the two largest new categorical vocabularies, and both are
   *partially hidden* opponent information — they need an unknown symbol our gen1 spec never needed.
   **(source-verified)**
2. **"Weather is not a thing" → four weathers × (turn counter + a Permanent bin) + a no-weather bit,
   37 dims of battle-level state** (Table A.1), and the Permanent branch is a **gen 3–5-only** rule
   (`showdown/data/conditions.ts`: `if (this.gen <= 5) this.effectState.duration = 0`) that will
   *not* carry to a future gen9 chapter. **(tree-verified)**
3. **"No entry hazards" → 6 hazard features (stealth rock 2, spikes 4 layers, toxic spikes 3), per
   side.** Stealth Rock's damage is type-dependent, so a hazard bit interacts with the type chart in
   a way no gen1 feature does. **(source-verified for the encoding; hazard mechanics not re-verified
   here)**
4. **"Screens are Reflect/Light Screen with a simple counter" → 10-wide duration one-hots per side
   per screen, plus Safeguard, plus Trick Room** (Table A.1) — and Trick Room *inverts the speed
   order*, which our gen1 policy has never had to represent. **(source-verified)**
5. **Duration counters everywhere.** Wang carries **12 distinct multi-turn counters** (4 weathers,
   trick room, reflect×2, light screen×2, safeguard×2, encore, taunt, magnet rise, slow start, toxic,
   sleep, protect-in-a-row). Gen1 needed a small handful. This is the single largest structural
   growth in the state, and it exists specifically to restore Markovianity (p. 23) for a
   **feed-forward** policy — the same reason our own encoder is feed-forward. **(source-verified)**
6. **Physical/special is per-move in gen4, not per-type.** Not in Wang (he encodes no move
   properties at all beyond identity + PP), but it is the assumption most silently baked into a gen1
   encoder's damage reasoning. **(literature-only from `JOURNEY.md:37`; not re-verified against
   `SD/data/mods/gen4` this session — flagged for `mechanics_delta.md`.)**
7. **Team/species pool size.** Gen1 randbats draws from a much smaller species pool; gen4 is
   **295 species / 464 sets** in our vendored generator (tree-verified, counted). An identity
   embedding table is now unavoidable if we go Wang's route; a one-hot species field is not.
8. **The opponent-set belief is tractable in gen4.** ≤3 sets per species (tree-verified) means the
   "what set is that?" posterior is a small categorical — cheap to featurize, unlike gen1's
   movepool-style uncertainty. Our gen1 D19 finding ("the genuine belief residual is 0.024–0.034
   nats", `docs/prior_work/README.md:110–113`, literature-only here) does **not** transfer: the gen4
   belief object is a different shape.
9. **`-inf` masking.** Wang masks with `-float("inf")` (p. 25) over ~486 dead logits out of ~495; our
   contract mandates `-1e8`. If we ever copy his action space, the sentinel choice becomes
   numerically load-bearing in a way it never was at gen1's 9 actions. **(source-verified vs
   CLAUDE.md convention)**
10. **Observation dtype.** Wang's vector is *mixed* (index ints + [0,1] floats), not a float box
    (p. 23 vs Table A.2). A gen4 `EncoderSpec` copied from his design cannot declare a single
    `Box(0,1,(N,))`. **(source-verified)**

---

## 14. Open questions for the maintainer

1. **Which Wang number is the gen4 step-5 target — 0.786 or ~0.836?** JOURNEY step 5 says to pin it
   in writing before starting. My recommendation: **pin 0.786 (Table 4.1) as the exit bar and quote
   ~0.836 (Fig 4.1 endpoint, digitized) as the stretch**, because Table 4.1 is the only number
   measured under a stated head-to-head protocol, and because our own locked protocol (final
   checkpoint, deterministic policy, 3000×N battles, ties as non-wins) is much closer in kind to a
   post-hoc table than to an in-training validation curve. **Losing argument:** Fig 4.1 is the
   number *he* headlines in prose ("roughly 85%"), the number the LR ablation is quoted against
   (0.55 → 0.80), and the one a reader who skims chapter 4 will remember — matching 0.786 and
   claiming parity could read as matching the weaker of his two numbers.
2. **Do we copy his action space at all?** Our whole ladder history is positional (14-way ps-ppo,
   9-way Metamon, ours). Wang's ~495-way identity space is the outlier **and his headline needed
   MCTS** (`docs/prior_work/README.md:490–493`). His *pure-network* 0.786 is the identity space's
   unaided score. Recommendation: **stay positional**; treat the identity space as a rejected
   alternative with a named reason.
3. **Do we adopt his batch shape along with his γ/λ?** λ = 0.754 was tuned at ~1,600 seat-episodes
   per update; ours is ~34. Either copy both or hold λ out of the copy.
4. **Is the 3v3 HPO surrogate worth building?** JOURNEY step 4 says "consider" it. It is the only
   affordable path to tuning we have ever had, and Wang's is the existence proof that the transfer
   works — but he publishes **no evidence** that the 3v3 optimum transfers to 6v6 (no 6v6 control, no
   trial counts). It is a cost-saving *hypothesis*, not a validated method.
5. **Which SH is the gen4 anchor?** Wang's numbers are against a **patched** `SimpleHeuristicsPlayer`
   (his fork patches it 4 times: Curse "???" type, `opp_remaining_mons`, `maybe_trapped` ×2). Ours
   would be against stock 0.15.0. Same comparability caveat we already carry for ps-ppo
   (`docs/prior_work/README.md`: "their SH numbers are vs a PATCHED bot"). Decide whether to patch, and
   disclose either way.
6. **Does the weather bug get fixed in the encoder or in a poke-env patch?** If `battle.weather` is
   restamped every turn (§10), the choices are: parse the raw message stream ourselves in the env
   wrapper, or vendor a patch. The former keeps the pinned dependency clean.
7. **How often do we validate?** Wang validated every 20k steps × 200 games, which taken literally is
   a 50% eval tax (§7.2). Our gen4 run needs an explicit cadence decision that does not depend on
   reading his ambiguous sentence.
8. **Does search stay depreciated?** Wang's own honest search gain is **+12.2 points vs SH**
   (.786 → .908) at 1000–2000 rollouts and 10 s/decision — a large gain, and his rank-8 ladder result
   is the searched agent. Against that: the modern curated `sets.json` makes determinization
   *cheaper* (≤3 sets/species, enumerable), which cuts the other way. This is `search_depreciation.md`'s
   central tension and I am flagging it rather than resolving it.

---

## 15. Unread / unverified

- **Figure page images not opened:** `_wang_p26-26.png` (Fig 3.1, LR schedule), `_wang_p29-29.png`
  (full p. 29), `_wang_p31-31.png` / `_wang_p31-32.png` (Fig 4.2 losses, Fig 4.3 Elo). Only
  `_wang_fig41_crop-29.png` was viewed and digitized. Anything about the *shape* of the loss curves
  or the Elo trajectory beyond the prose is unverified.
- **My Figure 4.1 digitization is my own measurement, ±~0.01** from gridline localization and line
  thickness; it tracks the smoothed line, not the raw 200-game points (whose band is visibly ±0.03).
- **Table 4.1's n = 1000 is an inference** from the 3-decimal precision, not a stated number.
- **`# unknown` (7) = count of unrevealed opponent Pokémon** is an inference; the thesis says nothing.
- **How partially-revealed opponent Pokémon are encoded** is genuinely not in the thesis (§2.3).
- **MCTS α and β have no published values.**
- **The Bayesian-optimization setup** (search space, trials, budget, objective) is not published.
- **Slot ordering / symmetry handling** in the 12 × 300 block is not published.
- **Whether Table 4.1 and Figure 4.1 used sampled or greedy action selection** is not published — the
  most plausible remaining explanation of the 0.786/0.836 gap, and unresolvable from the document.
- **Whether `SimpleHeuristicsPlayer` in poke-env 0.15.0 respects `maybe_trapped`** — I saw
  `available_switches` used in `player/baselines.py:226,277,354` without an obvious guard but did not
  read the full class. **Unverified; check before quoting any gen4 SH anchor.**
- **17 of Wang's ~19 gen4-relevant poke-env fixes** are unchecked against 0.15.0 (I checked weather
  and `maybe_trapped`'s existence only). JOURNEY.md:40's diff task remains open.
- **Wang's own code is not on disk** — only fork diffs and replays. Every claim about his
  implementation beyond the thesis text and those diffs is unavailable, not merely unread.
- **needs-live-verification (BARRED until the ladder run and any later fleet complete):**
  (a) that poke-env 0.15.0's `battle.weather` really does read as 0 turns-active across a live gen4
  battle with permanent (ability) weather — the check is a single `gen4randombattle` replay/battle
  with a Sand Stream user, asserting `battle.weather` values across ≥3 consecutive turns;
  (b) that `gen4randombattle` runs at all on our pinned poke-env + vendored server, and what
  `SimpleHeuristicsPlayer` scores against `RandomPlayer` there (Wang: .992) — the check is a small
  headless SH-vs-Random match set once the server may be started again;
  (c) the real s/battle for gen4 vs our gen1 FP@20 ≈ 1.2–1.5 s baseline, needed before any budget
  claim.

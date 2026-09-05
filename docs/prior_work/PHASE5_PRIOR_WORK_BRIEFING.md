# Advisory: Two prior-work findings for Phase 5

## What this is, and how much to trust it

Advisory input from a separate chat session with **no repo access**. I have not seen PLAN.md's current text, the campaign results, or the code. You have all of it. Everything here is a claim to verify and a decision to make, not a change to apply.

Provenance, stated plainly because it varies by source:

- **Source A (Wang thesis)** — read in full, PDF uploaded by the user. High confidence on specifics.
- **Source B (`Nebraskinator/ps-ppo`)** — **NOT read directly.** GitHub blocks automated access from my tooling, so everything below about it comes from a search-result snippet of the repo README. The numbers are that author's own claims about their own work, and one of them is their characterization of someone else's. **Read the actual repo before acting on any of it.** Flagged as the single largest uncertainty in this document.

---

## Finding 1 — the pure-policy calibration (the headline)

This is the item most likely to change how Phase 5 results are read.

**Wang's famous number includes search.** The 1693 Elo / rank 8 result on `gen4randombattles` is the PPO-trained network *plus* MCTS at inference. Wang reports the network alone at 0.786 winrate vs `SimpleHeuristicsPlayer`, and the full agent at 0.908 — search bought roughly 12 points and the ladder rank.

**Source B claims to have replicated Wang's MLP and hyperparameters without MCTS, and reports it plateauing around 1100 Elo.** If that holds, it prices the configuration this project is actually building: a pure neural policy, single forward pass, no search.

**The same source claims their own attention-based architecture reached >85% winrate vs `SimpleHeuristicsPlayer` and >1900 Elo on the Gen 9 random battle ladder, as a pure policy with no MCTS, no expectimax, and no external damage calculator.** They attribute the gap to architecture — attention internalizing the game tree into weights rather than searching it.

Why this matters here: the project's headline metric is winrate vs `SimpleHeuristicsPlayer`, and there is now an external datapoint suggesting that in a very similar setting, with search removed, **architecture was the binding constraint** and attention was the lever that moved it. That bears directly on the encoder-ceiling question Phase 5 currently holds as a named-optional BC diagnostic.

**Caveats that could defeat all of this:** Source B is Gen 9, Wang is Gen 4, this project is Gen 1 — mechanics, action-space size, and metagame all differ. Elo across formats and eras is not directly comparable. And a self-reported replication of someone else's work is the weakest evidence class in this document.

---

## Finding 2 — transferable specifics from Wang

Higher confidence; read from the thesis directly.

### Highest value-per-minute item: learning-rate annealing

Wang describes this as having a large impact: a constant learning rate left validation winrate stuck around 55%, while annealing reached roughly 80%. The schedule was `lr(x) = 10^-4.23 / (8x + 1)^1.5` with `x` as training progress in [0,1]. The constants 8 and 1.5 were chosen by hand rather than tuned, so they may not be optimal.

**If the Showdown runs currently use a flat LR, this is worth checking before the next campaign config locks.**

### Methodology worth stealing: tune on a surrogate task

Wang tuned hyperparameters via Bayesian optimization on **3v3 battles rather than 6v6** — roughly half the episode length, most of the strategic complexity, far cheaper per trial. Given this project is throughput-bound and has treated tuning as largely unaffordable, this is a direct workaround, and Gen 1 randbats supports the same reduction.

### Published hyperparameters (gen4randombattles)

| Parameter | Value |
|---|---|
| learning_rate | 10^-4.23, annealed |
| gamma | 0.9999 |
| gae_lambda | 0.754 |
| n_epochs | 7 |
| clip_range | 0.0829 |
| clip_range_vf | 0.0184 |
| entropy_coef | 0.0588 |
| value_coef | 0.4375 |
| max_grad_norm | 0.5430 |
| n_steps | 78 × 512 |
| batch_size | 1024 |
| hidden_dim | 256 (3-layer MLP, ReLU) |
| features_dim | 896 per Pokémon |

Note `gae_lambda` 0.754 — considerably lower than the 0.95 this repo settled on in Phase 4, and paired with a near-1 discount. Different game, but it is a tuned value for this domain specifically.

### Design decisions that touch open questions here

- **Reward: sparse terminal only.** +1 win, −1 loss, 0 on every other turn including ties. No shaping anywhere in the strongest published agent for its format. Relevant to the KO-shaping fork.
- **No recurrence.** Markov was restored by explicitly one-hot encoding the *durations* of multi-turn effects (e.g. Light Screen as a 10-dim one-hot over remaining turns). Recurrence is listed as future work, not a prerequisite for rank 8.
- **Env stepping, not GPU inference, was the rollout bottleneck** — stated directly, by someone training on an A6000. Independent support for the CPU-first hardware decision recorded on 2026-07-28.
- **Action masking:** logits set to −inf before softmax; masks saved at collection and **reapplied during gradient updates** when recomputing action probabilities. Matches the contract this repo already landed. (Note: this repo deliberately uses a finite sentinel instead of −inf to avoid NaN entropy — that divergence is intentional and should stay.)
- **Parallelization:** not lockstep. Per-worker rollout buffers; the update fires once at least half the buffers are full. Two stated reasons — variance in env step speed dampens the speedup, and turns are not strictly alternating (sometimes simultaneous, sometimes one player acts twice), so treating the two players as independent lockstep environments produces a **race condition**. Worth checking against the collection-loop design before it's written.
- **Both players' trajectories collected** from each battle — one game yields two for learning.
- **State binning** as deliberate state-space reduction: HP into 6 equal bins plus a zero state; PP via `floor(pp^(1/3))`, giving four bins.
- **Action space design differs from this repo's.** Wang used 494 global actions — 199 indexed by move identity, 295 by switch-to-species — masked to the ≤9 legal each turn. This repo uses 9 positional slots. Wang's learns move identity directly and may generalize better across random team draws; this repo's is far denser and simpler. Not a defect, but it is a fork that was taken implicitly and is worth being aware of.

### Scale calibration

Wang trained 150M steps over 4 days on one A6000 plus 80 CPU workers, 39 parallel games, ~3M battles. Most of the gain arrived within the first 40M steps (~1 day), reaching roughly 0.80 vs `SimpleHeuristicsPlayer`; the remaining 110M steps added about 5 points.

The current campaign is 6M steps. That is roughly 15% of Wang's first-day milestone, on far less hardware. Useful context for interpreting the finals rather than a target.

### The follow-on lever, priced

Wang's MCTS was used purely at inference as a policy improvement operator, explicitly **not** for generating training data — env simulation was judged too slow to produce enough samples. Hidden information was handled by sampling the opponent's unknown team at the start of each search trajectory using Showdown's own team generator with rejection sampling against known constraints. Opponent decisions inside the search were modelled with the trained policy, which the thesis identifies as a weakness against opponents that play differently.

---

## Concrete asks

In priority order. Push back on any of them.

1. **Read `Nebraskinator/ps-ppo` directly and verify or refute Finding 1.** Everything I have on it is a search snippet. If the pure-policy-without-search ≈ 1100 Elo claim holds up, and the attention architecture claim holds up, it is the most decision-relevant external evidence available for this phase.
2. **If Finding 1 holds, decide whether it changes the encoder-ceiling plan.** Phase 5 currently carries a BC diagnostic as named-optional to separate "encoder is the ceiling" from "training is the ceiling." External evidence pointing at architecture may raise its priority, or may substitute for part of it.
3. **Check whether the Showdown runs anneal the learning rate.** Cheapest item on this list, largest reported single-lever effect in the thesis.
4. **Decide whether the 3v3 surrogate-task tuning trick is worth adopting** for hyperparameter work that has so far been unaffordable.
5. **Compare the collection-loop design against Wang's non-lockstep note**, specifically the race condition around collecting both players when turns aren't strictly alternating.
6. **Record whichever of these are accepted or rejected in PLAN.md**, with reasons — the value is in the decision being explicit, not in it going a particular way.

---

## Sources

- Jett Wang, *Winning at Pokémon Random Battles Using Reinforcement Learning*, MIT MEng thesis, February 2024. PDF uploaded by the user; also at `https://dspace.mit.edu/handle/1721.1/153888`. Replays only (no training code) at `github.com/quadraticmuffin/pkmn-thesis-replays`; no code repository is referenced in the thesis.
- `github.com/Nebraskinator/ps-ppo` — **unverified, snippet only.**
- Prior anchors already in PLAN.md for comparison: Huang & Lee (2019) self-play PPO without search, ~1677 Glicko-1 on Gen 7 random battles; Metamon (offline RL with transformers).

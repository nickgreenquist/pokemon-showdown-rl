# Huang & Lee (2019) — deep read, corrections, and ranked findings

Source: *A Self-Play Policy Optimization Approach to Battling Pokémon*, Dan Huang & Scott Lee, IEEE CoG 2019. Read in full from `ieee-cog.org/2019/papers/paper_175.pdf` (also at `yuzeh.com/assets/CoG-2019-Pkmn.pdf`). Code: `github.com/yuzeh/metagrok` (MIT).

**No blog posts or other writeups exist.** The author's site hosts only the PDF; his GitHub has no writeup. Two sources total: this paper and that repo.

Written from a chat session with **no repo access**. Claims about this project's own numbers come from pasted status reports and may be stale — verify before acting.

---

## Ranked by what it changes

### 1. The baseline comparison is far more favorable than assumed

Table II, 1000 matches per pairing:

| Opponent | RL-rb win rate |
|---|---|
| random | 0.995 |
| most-damage | 0.929 |
| **most-damage-typed** | **0.829** |
| pmariglia (2019 tree search) | 0.612 |

Their strongest scripted baseline is **most-damage-typed** — highest-damage move with type awareness, nothing else.

`SimpleHeuristicsPlayer` is meaningfully stronger: it switches on a composed matchup score, uses setup moves, and scores expected damage with STAB, accuracy, expected hits, and a boost-adjusted stat ratio.

**So H&L scored 0.829 against a weaker bot than ours; we score 0.718 against a stronger one.** Those may be near-equivalent, or we may be ahead. The ~104 Glicko gap is then plausibly about ladder populations — gen7 randbats in 2019 vs gen1 randbats in 2026 — rather than policy quality.

This is free, and it undercuts the "we are behind H&L" framing that supplies urgency to the batch plan.

**Caveat:** most-damage-typed is not in our anchor battery, so this is a reasoned comparison of bot strength, not a measured one. If it matters to a claim, implement most-damage-typed and measure it directly — it is a trivial bot.

### 2. m = 7680 was arbitrary — the authors say so

> "For the number of matches played per iteration, we picked m = 7680 (a completely arbitrary choice)."

The batch plan currently treats this as a target to close ~30× toward. It is untuned and carries no evidence of optimality. The gradient-noise argument for larger batches stands on its own; the argument-from-H&L does not. Demote it in the pre-reg rationale.

### 3. The paper publishes **zero** PPO hyperparameters

No γ, no λ, no learning rate, no epochs, no minibatch count, no entropy coefficient, no ablations. Four pages.

So "H&L's γ = 0.95" did not come from this paper. It is either from metagrok's configs or it is our replication's own choice — and if the latter, "H&L's shaping is coupled to their γ" is an inference about a value they never published.

**This makes reading `metagrok/expts/*.json` the only route to ground truth on their recipe.** Higher priority than before, not lower.

### 4. Their ladder protocol, and their explicit rejection of Elo

They laddered **300 matches, five times** — every 100 training iterations — not once at the end. That is closer to a scaling curve than an endpoint read, and it is the shape our R-series is converging on independently.

A footnote worth citing verbatim:

> "Pokémon Showdown exposes an Elo rating for competitors, but we do not use that because their Elo rating is not a true Elo system."

They cite Antar's Smogon ratings resource. That is published support for our Glicko/GXE-over-Elo choice.

The paper does not say whether the five evaluations used one account or fresh ones — so it does not settle our A/B account question.

### 5. Their shaping is tiny and asymmetric — our replication was a different function

−0.0125 per friendly faint, +0.0025 per super-effective move. **No term for opponent faints.** It is not zero-sum, and the faint contribution caps near 0.075 against a ±1 terminal — roughly 8× smaller than ps-ppo's ±0.1 per faint.

Our arm was "γ0.95, 5-term zero-sum," which is a materially different reward function.

Combined with the fact that our shaping read was **+0.0135 against a bar of 0.072** — five times inside the noise floor — "our own shaping arm read null" should carry no weight in any argument. It is an unmeasurable, exactly like the scale read, and it has not been reclassified as such.

### 6. Catastrophic forgetting — Section V

They fine-tuned RL-rb for 50 more iterations (384,000 matches) on a fixed 3-team metagame. It improved sharply there (0.555–0.99 vs pmariglia, up from 0.12–0.87). Then:

> "In a head-to-head matchup of RL-rb and RL-meta in the generalized format, RL-meta only wins 77/500 matches."

**0.154.** A short specialization run destroyed general randbats ability. These policies fit the team distribution hard rather than learning transferable skill.

Relevant to: the lane-diversity/ensembling story, anything involving continued training from a checkpoint, and the general question of what a gen1randombattle policy is actually learning.

### 7. Encoder gaps

Table I, per-Pokémon features: species (1023-way), item (368), ability (238), moveset (4×731), **lastmove (731-way categorical)**, stats (6), boosts (6), hp, maxhp, **ppUsed (4)**, active, fainted, **status (28)**, types (18), **volatiles (23)**.

Two design details from Figure 1 worth noting:

- **Ability embeddings for "Possible Ability 1/2/3"** — an explicit belief-state mechanism over unrevealed opponent abilities. Structurally the same idea as our randbats set prior, arrived at independently.
- Move embeddings are **averaged** into the Pokémon token before the team max-pool; the active Pokémon's four move embeddings are separately concatenated into the policy head.

Gen 1 has fewer statuses and volatiles, so the raw gap overstates it — but our 6-dim status and 7 volatile flags are thin against 28 and 23.

---

## Confirmed, unchanged from prior notes

500 iterations × 7,680 matches = **3,840,000 self-play matches**; both seats collected ("using the 2m self-play matches as training data"); **6 days on GCP, ~$91 USD**; **1,327,618 parameters**; 128-dim entity embeddings per categorical; max-pool over the team; "the parameters for computing p ... are shared among all n actions" (the pointer head); sampling from π during training; masking by **renormalization** rather than a logit sentinel; no recurrence (LSTM listed as future work).

Also: they note training can be "bootstrapped using a previously trained model as a baseline" — though §6 shows what that costs in generality.

---

## What to do with this

1. **Reweight the H&L gap.** The Glicko comparison and the bot-baseline comparison point in different directions, and the bot comparison is the one measured under controlled conditions. Consider implementing most-damage-typed as an anchor to make it measurable rather than argued.
2. **Read `metagrok/expts/*.json`** before any retrain that cites H&L's recipe. The paper cannot support those claims.
3. **Reclassify the shaping arm** from null to unmeasurable, and note it tested a different reward function than H&L's.
4. **Drop "close the 450× gap to H&L" as a rationale** for the batch lever; keep the noise-floor argument, which does not depend on them.

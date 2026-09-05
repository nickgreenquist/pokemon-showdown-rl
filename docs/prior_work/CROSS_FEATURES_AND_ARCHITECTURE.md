# Cross Features and Architecture — Implementation Spec

*Companion to `LLM_IN_RL_REPORT.md`. That document covers optional LLM-assisted techniques and concludes they are deferred. **This document is the primary path.** Nothing here involves an LLM.*

## Provenance

Written from a chat session with **no repo access**. Feature formulas below are stated from Gen 1 mechanics and from reading `SimpleHeuristicsPlayer`'s logic as described in earlier sessions — **verify every formula against `baselines.py` and the Gen 1 damage formula before implementing.** Where this contradicts the runner's own audit, the audit wins.

---

## 1. The diagnosis, in one paragraph

The observation vector supplies the *ingredients* of every important quantity but almost none of the *products*. `SimpleHeuristicsPlayer` computes expected damage as `base_power × STAB × (atk/def ratio) × accuracy × expected_hits × type_multiplier` — a degree-5 product with a division inside it. The current network is a **flat MLP over a concatenated 611-dim vector**, and flat MLPs are known to be inefficient at representing even degree-2 feature crosses. This is the well-documented motivation for Wide & Deep, DeepFM, and DCN in the ranking literature: the deep tower alone does not learn crosses efficiently, so explicit crossing machinery is added alongside it.

So "our features nearly contain SH's inputs, therefore our policy class contains SH" is weaker than it sounds. Containment in principle is not reachability in practice when the target function is a product of distant inputs. The agent plateauing at ~0.443 while a BC clone of SH lands at ~0.453 is consistent with exactly this.

**Two independent fixes, and they compose:**
1. **Hand-compute the products** (this document, §2–3). Zero samples required, near-zero inference cost.
2. **Add crossing machinery** to the architecture (§4). Catches the crosses you didn't name, at the cost of samples and inference time.

Do both. They are not alternatives.

---

## 2. Per-move-slot features

Four move slots, aligned to actions 6..9. Current `MOVE_DIM = 23`.

| # | Feature | Formula | Notes |
|---|---|---|---|
| M1 | `stab` | `1.5 if move.type in user.types else 1.0` | **The canonical missing cross.** Requires matching the move's type one-hot against the *user's* type block at a distant offset — a multiplicative comparison across blocks. |
| M2 | `expected_damage_frac` | see §2.1 | Composed. The single highest-value feature here. |
| M3 | `is_probable_ko` | `expected_damage_frac >= opponent.current_hp_frac` | Cheap, large strategic payoff. Consider a soft version (margin) rather than a hard flag. |
| M4 | `expected_hits` | `move.expected_hits` | Double Kick currently reads as base power 30. |
| M5 | `self_boost_sum` | `sum(move.boosts.values())` gated on `move.target in ("self",)` | SH's setup rule, same gate. Swords Dance / Amnesia / Agility currently collapse to "status move, bp 0". |
| M6 | `status_prob` | secondary-effect chance × status one-hot | Blizzard's 10% freeze. **Gen 1 freeze is permanent** (no natural thaw; only a Fire-type hit or Haze), so this is arguably the highest-leverage Gen 1 semantic in the game. |
| M7 | `accuracy_weighted_power` | `base_power × accuracy` | Trivial, but removes one more product from the net's burden. |

Already present and keep: base power, accuracy, PP, category, priority, type one-hot, type multiplier vs. opposing active.

### 2.1 Expected damage

Shape (verify the exact Gen 1 constants):

```
level_term   = (2 * level / 5) + 2
ratio        = boosted_stat(user, atk_stat) / boosted_stat(opponent, def_stat)
raw          = (level_term * base_power * ratio / 50) + 2
damage       = raw * stab * type_multiplier
expected     = damage * accuracy * expected_hits / opponent.max_hp
```

Three Gen 1 specifics that will silently corrupt this if missed:

- **Category is determined by the move's TYPE, not the move.** Physical: Normal, Fighting, Flying, Ground, Rock, Bug, Ghost, Poison. Special: Fire, Water, Grass, Electric, Psychic, Ice, Dragon. The physical/special split by move arrives in Gen 4.
- **Special is a single combined stat** used for both attacking and defending. There is no SpA/SpD split until Gen 2.
- **Boost stages need the piecewise transform**, not the raw stage. Roughly `(2+b)/2` for `b > 0` and `2/(2-b)` for `b < 0`. Feeding raw stage integers leaves the net to learn a piecewise nonlinearity *and* a division.

**Format bonus worth exploiting:** in `gen1randombattle` the spreads are standardized by species. Once the opponent's species is revealed, its stats are **known**, not estimated. So expected damage against a revealed opponent is exactly computable — you do not need the belief-range machinery that later generations require. This is a real advantage of the format choice and it is currently unused.

---

## 3. Per-Pokémon-slot features

Six team slots aligned to actions 0..5. These matter more than the move features, because **the composed matchup score is the single statistic that drives every switch decision `SimpleHeuristicsPlayer` makes** — and it is absent from the observation.

| # | Feature | Formula | Notes |
|---|---|---|---|
| P1 | `matchup_score` | see below | The switch statistic. Compute per bench mon against the opponent's **active**. |
| P2 | `speed_sign` | `+1 / 0 / -1` on base speed vs. opponent active | A cross-block comparison. In Gen 1 this also proxies crit rate — **crit chance is keyed to base Speed**, so fast Pokémon crit constantly. |
| P3 | `hp_diff` | `mon.hp_frac - opponent_active.hp_frac` | A cross-block difference. |
| P4 | `best_type_mult_out` | `max(opp.damage_multiplier(t) for t in mon.types)` | Already present at `[+30]`. |
| P5 | `best_type_mult_in` | `max(mon.damage_multiplier(t) for t in opp.types)` | Already present at `[+31]`. |

SH's composed score (verify coefficients against source):

```
matchup = best_type_mult_out
        - best_type_mult_in
        + SPEED_COEF * speed_sign          # ~0.1
        + HP_COEF * hp_diff                # ~0.4
```

Keep P2–P5 alongside P1. The composed score gives you SH's floor by construction; the raw components leave room to learn better coefficients than SH's hand-tuned ones.

### 3.1 Global features

- `n_alive_self`, `n_alive_opp` — check whether already present.
- `n_revealed_opp` — how much of the opponent's team is known. A proxy for information state.

### 3.2 The known gap this does *not* close

All type-effectiveness features above are computed against the opponent's **types**, not their **revealed moves**. The defensive switch question — *"does their revealed Blizzard hit the Pokémon I'd switch to?"* — needs per-bench-mon × revealed-move multipliers. STAB dominance in Gen 1 makes the type proxy decent, and this was already documented as a priced follow-up. Leave it out of the first pass; revisit if the composed-matchup arm underdelivers.

**Total added:** roughly `4 moves × 7 + 6 mons × 3 + 3 global ≈ 49` dims on 611. Small, and every one replaces a product the net currently has to discover.

---

## 4. Architecture ladder

Ordered by cost. Each rung is independently shippable and composes with the next.

### Rung 0 — hand-composed features (§2–3)
~1 evening. Zero inference cost. Zero samples required. Do this first regardless of everything below.

### Rung 1 — pointer / shared-slot scoring head
**Highest benefit-to-inference-cost ratio on this list, and neither Wang nor ps-ppo has it.**

Today the trunk flattens everything and a linear head projects to 10 logits. Nothing structurally connects slot *j*'s features to logit *j* — the net learns that correspondence ten separate times and cannot share what it learns about slot 0 with slot 3.

A pointer head scores each slot with a **shared** function of that slot's features:

```
logit_j = f_shared(slot_features_j, global_context)
```

Correspondence becomes architectural, and every slot's data trains the same scorer. Cheap: one small MLP applied 10 times instead of one wide linear layer. **Careful with the two action classes** — moves (4 slots) and switches (6 slots) have different feature shapes, so either use two shared scorers or project both into a common slot representation.

### Rung 2 — explicit crossing: two-tower dot product or DCN cross layers
Familiar machinery from the ranking world, and the direct test of the crossing hypothesis.

- **Two-tower**: encode `(move ⊕ user)` and `(opponent)` separately, dot them. STAB and type effectiveness are both bilinear in type one-hots, so a dot product represents them natively.
- **DCN cross layers**: `x_{l+1} = x_0 ⊙ (W x_l) + b + x_l`, two or three layers before the trunk. Gives explicit degree-(l+1) polynomial interactions over the whole vector without naming any of them.

~1 day. Small fraction of a transformer's inference cost. This is the cheap architectural arm, and it isolates crossing cleanly.

### Rung 3 — entity attention over Pokémon tokens
Attention is `query · key` — a bilinear form, i.e. a data-dependent cross with learned routing. ps-ppo's evidence is real: they precompute **no** type effectiveness at all (raw types both sides) and reached >1900 Elo pure-policy at 250M steps.

Two things it does **not** give you free:

- **Move-level granularity.** ps-ppo's tokens are per-Pokémon (12 of them); the four moves are fused into the Pokémon token by a subnet *before* attention. So the specific cross of *this move's type* × *that Pokémon's types* is bottlenecked before attention sees it. Move-level tokens would fix that, and nobody has built them.
- **Ratios.** Attention gives products, not divisions. The `boosted_atk / boosted_def` term stays hand-computed regardless.

Also note Gen 1 shrinks the prize: ps-ppo's Pokémon token fuses species, item, four ability slots, Tera, weather and hazards — none of which exist in Gen 1. A meaningful share of what their attention relates does not exist in your format.

Cost: a phase, plus a real inference-cost hit (14.5M params, 15 tokens, d=512, 3 layers).

---

## 5. Experimental design

Features and architecture are **orthogonal axes**. With the compute constraint lifted, run the factorial rather than a sequence:

|  | MLP trunk | Cross trunk (Rung 2 or 3) |
|---|---|---|
| **Current encoder** | control — the existing 0.443 | isolates architecture |
| **Rich encoder** (§2–3) | isolates features | interaction |

The interaction cell is the interesting one: hand-computed crosses may make learned crossing **redundant** (they overlap) or **compounding** (they free capacity for higher-order structure). Either result is a genuine finding and neither is visible from sequential arms.

**Sequencing constraint that is not about compute:** adding features changes `OBS_DIM`, which breaks every existing checkpoint. Freeze the rich encoder before launching architecture arms, or the arms differ on two axes at once. Evaluate all outstanding finals *before* the encoder change lands.

### Pre-registration sketch

State before running:

- **Primary metric:** win rate vs. `SimpleHeuristicsPlayer`, ≥1000 battles, ≥3 seeds, sampled (not greedy — simultaneous-move play needs a stochastic policy).
- **Control:** the existing matched-recipe run at 0.443.
- **Rich-encoder arm success:** e.g. ≥0.04 absolute improvement, seed-averaged, with the SE reported.
- **Clone-diagnostic caveat:** evaluate the BC clone **both greedy and sampled**. A stochastic clone of a deterministic teacher scores below 0.5 in a mirror match by construction, so part of the 0.453 gap may be policy entropy rather than missing features. If greedy ≈ 0.50 while sampled ≈ 0.45, the feature story is unsupported and this whole plan needs rethinking before the architecture arms run.
- **Note what the clone test can and cannot validate:** BC on SH data can only reward features SH itself uses. STAB, `expected_hits`, `self_boost_sum` and the matchup score are testable this way. `status_prob`, freeze permanence, partial trapping and speed-keyed crits are **not** — SH is blind to them too. Those are justified on theory and validated only by RL. Do not read a passing clone test as "encoder solved"; it clears the lower bar of *reaching* SH, not *exceeding* it.

---

## 6. Hardware, now that the constraint is lifted

The right rental is **coupled to the architecture arm**, because the loop is ~95% collect and inference-bound with the update at only ~5%.

- **MLP or DCN arms → rent CPUs.** More parallel envs and more Showdown server processes. A GPU barely helps: batch-1 inference on a small net is often *slower* on GPU than CPU due to kernel-launch overhead, and the 5% update is the only part a GPU accelerates.
- **Attention arm → rent a GPU**, and batch inference across concurrent envs. At transformer scale the net is finally large enough that GPU batching wins. ps-ppo's own recipe was ~250M steps in ~2 days on a single RTX 3090.

Two things worth buying with the freed budget regardless of arm: **multi-seed on everything** (the variance discipline this project already applies elsewhere), and **Wang's 3v3 surrogate-task hyperparameter search** — half-length episodes, most of the strategic complexity, previously unaffordable.

---

## 7. Suggested order

1. Evaluate all outstanding finals (checkpoints break next step).
2. Implement §2–3 hand features. Screen with the BC clone, greedy **and** sampled.
3. Add the Rung 1 pointer head — cheap, uncontested, no evidence against it.
4. Launch the 2×2 with Rung 2 (DCN / two-tower) as the cross trunk.
5. Rung 3 attention **only** if the 2×2 says crossing is the binding constraint and the inference-cost measurement says the throughput is affordable.

The separately-tracked highest-value lever remains **BC initialization from the ~109k human `gen1randombattle` replays** — VGC-Bench reports +25–30 points at matched budget, which is larger than anything in this document. It is orthogonal to everything here and belongs in its own chapter.

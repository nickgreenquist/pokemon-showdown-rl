# Distillation objectives for the Foul-Play BC chapter — verified survey + in-repo measurements

Provenance: researched 2026-08-07 by a session subagent (Metamon PDF deep-read + published-
literature sweep), with three read-only measurements over this repo's own tapes. Curated and
committed by the session; the measurements were run against `data/fp_all_v2/*.npz` (180,440
rows) and `data/fp_tranche/run_4106.jsonl` (9,938 decisions with full policy+Q).

## Verdict

**Plain soft-target cross-entropy against the teacher's search policy stays the objective for
the ~900k-row fit. Every weighted/filtered/offline-RL variant is measurably a no-op or a
variance injector ON THIS DATA.** The two supported add-ons are early stopping (measured
overfit: train KL ~0.185 vs val 0.738 at 180k rows, 20 epochs — the val peak at epoch 7
scored 0.569 vs the final epoch's 0.558) and a small DAgger round, gated on a cheap
covariate-shift diagnostic.

## The in-repo measurement that kills the weighted variants

Teacher advantage of the taken action, reconstructed from the tapes' per-action values
(A = 2·Q(a_taken) − 2·Σ p(a)Q(a), ±1 scale):

    mean +0.0308  sd 0.0381  p05 +0.0008  p95 +0.0701  frac A>0 = 0.971

- Metamon's binary filter `1[A>0]` would keep **97.1%** of our rows; their gain came from
  keeping only 15–45% of mixed-quality human data. We have nothing to throw away.
- At Metamon's own β=0.5, `exp(βA)` spans [1.000, 1.036] — numerically inert.
- Q-augmented targets (Gumbel-style): argmax(policy)==argmax(Q) on 92.5% of decisions,
  Kendall τ = 0.957 — the visit shares already encode the Q ordering (the "N_sim=50 regime"
  where Grill et al.'s target change buys nothing).

## Key external evidence (all verified against the papers)

- **ExIt (Anthony et al., NeurIPS 2017): soft-vs-hard at IDENTICAL agreement (47.0 vs 47.7%)
  gave the soft-target net +50 ± 13 Elo.** Directly explains our own soft-vs-hard tie on
  agreement (0.4215 vs 0.4212): agreement cannot discriminate; strength can. Soft is right.
- Policy Distillation (Rusu, ICLR 2016): KL > NLL > MSE on both tables.
- Searchless chess (Ruoss et al., 2402.04494): BC-of-oracle-move is the WORST of their three
  targets; value-aware targets win — but their gains route through richer targets, and our
  soft policy already carries the teacher's value ordering (τ 0.957).
- Metamon: offline RL beat BC by +11 GXE in Gen1OU — but ALL RL variants tie with each other,
  the gain is attributed to filtering bad demonstrators (keep-rate 15–45%), and their
  winners-only arm was tried and abandoned. Does not transfer to a 0.83-vs-SH teacher.
- Kumar et al. (ICLR 2022): on expert data, BC matches offline RL at the information-theoretic
  bound; filtering DEGRADES sample complexity.
- AlphaStar Unplugged Table 2: winners-only was the WORST configuration (51% vs 84%);
  train-on-everything-then-fine-tune-on-quality was the best (89%). Outcome filtering: no.
- AlphaGo Zero's +600 Elo from the value head is measured WITH search at deploy; the paper
  records a small policy-accuracy COST. We deploy argmax without search: keep actor and critic
  disjoint (our `--value-coef` critic training adds exactly zero actor gradient — it is a
  warm-start artifact, not an objective change).
- DAgger (Ross et al., 2011): +44% at matched label budget when learner errors move the state
  distribution (Mario), +1.9% when they don't (OCR). Pokémon is the former regime. Cost here:
  ~100k on-policy relabels ≈ 2.2 h at 3-wide (measured 0.237 s/decision). Gate first: tape
  ~5k decisions with the CLONE driving the seat while Foul Play labels; a large agreement gap
  vs held-out FP-trajectory rows ⇒ shift binds ⇒ run one round and FINE-TUNE (AlphaStar
  staging), don't retrain on the union.

## Explicitly not recommended

Advantage/binary/outcome weighting, one-step offline RL (we HAVE the teacher's Q — fitting a
critic to estimate it only adds error), Q-augmented targets, hard targets, shared actor-critic
trunk. One speculative arm if ever wanted: temperature on the teacher target (unablated
anywhere in the literature; would cost win-rate evals to test, agreement cannot discriminate
it).

## Recipe changes adopted for the 900k fit

1. Early stopping / fewer epochs so final == best (kills the best-checkpoint selection caveat).
2. `--value-coef 0.5` ON (critic pre-training for the warm start; zero actor coupling).
3. Loss unchanged: `−Σ_a p_teacher(a) · log softmax(masked_logits)_a`.
4. Optional secondary arm at 900k only: width sweep + weight decay (capacity binds for BC —
   Metamon Fig. 24/26; our 682k-param actor already overfits 161k rows).

# Pokémon RL Capstone — External Research Brief

*Dated snapshot, 2026-08-10 — written to hand a research assistant full project context
in one page. Not a living doc; STATUS.md and DESIGN.md are the source of truth.*

## What this project is

An RL agent for **Pokémon Showdown Gen 1 random battles** (`gen1randombattle`),
battle-phase only, playing via poke-env against a local Showdown server. Solo project,
evening-blocks cadence, CPU-only laptop (the loop is ~95% environment collection,
~350–390 env-steps/s per training lane, 3 parallel lanes).

## The core direction — and the maintainer's explicit preference: novelty over strength

The goal is a **pure from-scratch self-play agent**, because it has never been
demonstrated in Gen 1: no BC warm-start, no teacher data, no scripted opponents in
training, no human replays. Weights must be a function only of random init + self-play
experience + the environment. **It is trivial to copy proven published results and
spend money to match them — that is not interesting.** The nearest existence proof is
Huang & Lee 2019 (gen7 randbats, pure mirror self-play, ~2–3×10⁸ decisions); nothing
exists for gen1. Hand-designed observation encoders are fine (everyone hand-designs
obs/action/reward); scripted and distilled agents are allowed as **eval anchors only**.

## Stack

PPO (on-policy, 4 epochs), 10 discrete actions (6 switches + 4 moves) with action
masking, ~828-dim hand-written observation (entity features + species/move ID suffix),
and — the key recent finding — an **entity architecture**: per-Pokémon/per-move
embeddings and subnets, DeepSets max-pool over teams, and a shared per-action scoring
head (pointer-style), ~0.62M actor params.

## Results so far

Benchmark: poke-env's SimpleHeuristicsPlayer ("SH"). Protocol: final checkpoint,
deterministic policy, ties count as losses, 3 seeds × 3000 battles pooled.

| result | vs SH |
|---|---|
| SH-vs-SH mirror (parity point; SH is weak — ~40% GXE in human-ladder terms) | 0.489 |
| Best SH-*trained* PPO (old era) | 0.4607 |
| BC clone of SH | 0.4657 |
| Search-based engine (Foul Play, patched) | ~0.83 |
| Pure self-play 12M, flat MLP — the plateau | 0.3996 |
| + H&L reward shaping (γ0.95, 5-term zero-sum) — NULL | 0.4131 (n.s.) |
| **+ entity architecture at matched params — CREDIT** | **0.5509 ± 0.005** |

The entity-architecture result (+0.151, z≈+20) showed **the flat readout was the
binder** — not the input features, not the reward. It cleared the pre-registered
"past SH" success milestone, guarded by head-to-heads vs non-SH anchors (beats the
search engine's BC clone 0.657 head-to-head; the engine's edge over us shrank 0.876 →
0.824) — the gain is general, not SH-specific. **First pure self-play agent past the
scripted benchmark in gen1, per our literature index.** The published field starts at
72% GXE, so this is a *local* first, not SOTA — stated plainly on purpose.

Currently finishing: a 50M-step scale run (4.2× budget, same recipe). In-training
curves suggest it reads out near **~0.55 — likely a scale NULL at this range**: more
steps alone isn't paying under this recipe.

## What's queued next (all training-side, purity-compatible)

1. **Privileged/asymmetric critic** — critic sees the opponent's true hidden team
   during self-play training; actor doesn't (AlphaStar precedent; Baisero & Amato,
   AAMAS 2022, prove the actor-obs ‖ privileged form unbiased for bootstrapping). We
   believe this is unattempted in Pokémon RL but have NOT verified.
2. **Auxiliary opponent-team prediction head** (belief-state learning; ground truth is
   free in self-play).
3. Hygiene levers: KL early stopping, entropy-coefficient scheduling, PFSP-style
   win-rate-prioritized opponent sampling.
4. Later: richer belief/history observation features (gen1 turn counters,
   revealed-move tracking, last-turn events).

## Constraints that make research suggestions useful or useless here

- On-policy PPO self-play, sparse terminal ±1 reward at γ=1.0.
- Strict one-lever-per-experiment pre-registration discipline (bundled changes cannot
  be attributed; every experiment has a pre-registered credit line).
- The observation encoder is frozen mid-chapter — semantics changes invalidate all
  checkpoints and comparators, so they batch into rare re-baselines.
- CPU inference-bound loop: anything raising per-step inference cost (recurrence, big
  attention stacks) is heavily penalized.
- Off-policy / high-replay-ratio techniques generally do not transfer.

## What we most want from research

- **Prior-art verification, adversarially**: has *anyone* done an asymmetric/
  privileged critic in Pokémon RL? Pure self-play in gen1 at any scale? We need
  searches that try to REFUTE our novelty claims, not confirm them.
- Evidence-graded techniques that fit the constraints above — especially ones
  exploiting properties unique to self-play (both seats controlled, hidden state
  known at training time).

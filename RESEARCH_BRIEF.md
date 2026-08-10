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

## Technical detail (for cross-checking against literature)

### Environment
poke-env 0.15.0 (our pinned build; its setup branch is dead upstream) against a local
Node Showdown server. `gen1randombattle`: random teams and sets, 151 species / 165
moves, **no team preview** (at turn 1 the opponent's entire team is hidden), no items/
abilities in gen1. Episodes average ~25–35 decisions. Simultaneous-move game with
substantial outcome RNG (crits keyed to base Speed, damage rolls, sleep/freeze turns).

### Action space
`Discrete(10)`: actions 0–5 = switch to team slot i (poke-env team order), actions
6–9 = use move slot j of the active Pokémon. Legal-action mask supplied by the env
every step; masking applied outside the network with a finite −1e8 sentinel (never
−inf), at eval too; the value head is never masked. Slot alignment is load-bearing:
obs block i corresponds to action i. Gen1 quirk we handle explicitly: on "placeholder"
turns (recharge, locked moves, Struggle) Showdown re-bases the move list to a single
action; our encoder zeroes the move blocks and sets a global aliased-turn flag rather
than mislabeling slot semantics.

### Observation (hand-written, 828 dims, all values hand-normalized to ~[0,1])
- **Global (6)**: turn/50 (capped), own fainted/6, opponent fainted/6, force-switch
  flag, trapped flag, aliased-turn flag.
- **Own 6 Pokémon blocks (33 each)**: HP fraction, fainted, is-active, status one-hot
  (6), level/100, base stats (5, /255), type one-hots (15), best type multiplier of
  mon's types vs current foe, foe's vs mon, speed-edge scalar vs foe.
- **Own active extras (16)**: 7 boosts (/6), 7 volatile flags (confusion, focus
  energy, leech seed, must-recharge, partial-trap, reflect, substitute), a shared
  sleep/toxic turn counter (/16), a "preparing" flag (two-turn moves).
- **Own active's 4 move blocks (46 each)**: known flag, base power/100, accuracy, PP
  fraction, type multiplier vs foe, physical/status category, priority/5, move-type
  one-hot (15), and a 23-dim hand-built move-effect block.
- **Opponent: 6 blocks of (33+1)** — same mon features plus a revealed flag, in
  reveal order, zero-padded for unrevealed mons; opponent active extras (16); and the
  opponent active's 4 move blocks where the "known" dim is **P(mon has this move)
  from a vendored randbats set prior** — an unrevealed-but-likely move is encoded as
  a probability-weighted block instead of zeros. This is the belief-state mechanism.
- **ID suffix (20)**: 12 species ids + 8 move ids (id/256), recovered to embedding
  indices inside the network.

**What each side knows**: our full team always; the opponent's bench only as revealed;
opponent active's moves via revealed + set prior. The critic currently sees exactly
what the actor sees — that is what the queued privileged-critic experiment changes.

### Model (the credited "entity" trunk, ~0.62M actor params)
A tokenizer reshapes the flat obs into 21 tokens (1 field, 12 mons, 8 moves). Species
embedding table 152×64, move table 166×64. Shared per-mon subnet: [mon token 50 ‖
species emb 64] → 2 layers → 128; shared per-move subnet likewise → 128. **DeepSets
max-pool** over our 6 mon vectors and separately over theirs. Context = concat(field
projection, own pool, opp pool, own active, opp active) = 640 → MLP [384,384].
**Policy head is a pointer-style shared scorer**: logit_i = scorer(context ‖
entity_i) + slot bias, where entity_i is the mon token for switch actions and the
move token for move actions — ONE shared 2-layer scorer (512→256→1) across all 10
actions. That sharing is the hypothesis that credited: what the net learns about
"switching into X" transfers across slots. Value head: separate [384,384] stack over
the same pooled features (no shared trunk with the actor — deliberate deviation from
Huang & Lee, who share). No attention anywhere — an entity-attention trunk measured
34.6× the MLP train step on CPU and was rejected on throughput.

### Training recipe
PPO: clip 0.2, lr 2.5e-4 constant (no anneal), γ=1.0, GAE λ=0.95, rollout 128 steps ×
8 envs = 1024 steps/update, 4 epochs, 4 minibatches, entropy coef 0.01, value coef
0.5, grad-norm clip 0.5, single torch thread. Reward: terminal ±1 only, ties 0.
Self-play: opponent pool of 20 past checkpoints, push every 150 updates, 80% latest /
20% pool sampling, span-preserving eviction. (Both published pure-self-play successes
used no pool — pure mirror; our pool is a recorded deviation.)

### Eval protocol (locked; what every headline number means)
Final checkpoint, deterministic argmax, ties count as non-wins, 3 seeds × 3000
battles pooled vs SimpleHeuristicsPlayer; win rate comes from env-supplied outcome,
never the return sign. In-training curve: n=100 eval every 250k steps (noisy, shape
only — never a headline). Head-to-heads: both orientations, 500/pair, pooled —
deterministic-vs-sampling seat asymmetry is large (measured up to 0.800/0.514) so one
orientation alone is never read. Eval anchors: SH, a BC clone of SH, a BC clone of the
Foul Play search engine (protocol-graded 0.5490 final / 0.5777 val-peak), the Foul
Play engine itself, and a max-base-power bot. Milestone claims require the non-SH
anchors to move (guards against benchmark-specific exploits).

### Known encoder gaps (audited, deliberately deferred — useful cross-check targets)
Light Screen is unparseable in our poke-env version (maps to a generic unknown
effect); the partial-trap volatile flag never fires (gen1 protocol path); sleep/toxic
counters are a shared scalar, not one-hots; no Substitute remaining-HP; no
Bide/Rage/Transform/Mimic/Mist flags; no last-turn history features (who moved first,
crits, effectiveness — designed but deferred); no summed-team-HP aggregates; PP is a
continuous fraction (not binned). We audit poke-env field population before trusting
any field — two "present" features were measured structurally dead this way.

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

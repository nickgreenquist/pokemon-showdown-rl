# JOURNEY.md

The multi-generation arc, end to end. Written 2026-08-28.

**Not a spec.** Chapter documents, config headers, and STATUS.md remain authoritative for anything currently in flight. This is the shape of the thing, so no session has to reconstruct why we are where we are.

**The story in one line:** gen1 is the novelty (pure self play non published), gen4 is the validation (published results to compare against), gen9 is the relevance (most users play this).

Each generation answers a different question. Gen1 asks *has anyone done this* — no, and pure self-play there is unclaimed ground. Gen4 asks *does the method actually work* — Wang published a pure-self-play PPO result on `gen4randombattle` with hyperparameters attached, so it is the one generation where our levers can be measured against an external reference instead of only against our own noise floor. Gen9 asks *does anyone care* — it is where Foul Play, ps-ppo, PokéChamp and VGC-Bench all stand, so a number there gets read by people who have never heard of gen1 randbats.

---

## Before step 3 — one cheap add

Implement `most-damage-typed` as a standing anchor. Highest-damage move with type awareness, nothing else. One afternoon. We already have MaxBasePowerPlayer (no type awareness); this is the stronger sibling.

Why it earns its place: it is the only anchor whose own strength doesn't drift across generations. SimpleHeuristicsPlayer has hazard branches that are inert in gen1 and live from gen4 on, so an SH-denominated number partly measures SH getting stronger as we move up the arc. Most-damage-typed has no generation-dependent code. That makes it the right denominator for a gen1 → gen4 → gen9 comparison.

Secondary: H&L reported 0.829 against this bot in gen7. That's a cross-generation comparison and carries a confound (a pure damage bot is relatively weaker in gen7, where more mechanics exist for a good player to exploit), but it holds the opponent fixed, which no ladder comparison can.

---

## The journey

### 1. Gen1 retrain (batch lever). One retrain. The batch change is the lever; everything else stays fixed.

Scope guard: if the offline read lands inside the 0.072 bar, that's information about the instrument, not the lever — and it is not a reason to queue another gen1 lever. Ladder anyway, then go to step 3. The trap is the retrain after this one.

### 2. Gen1 ladder #3 — record. Happens regardless of what step 1's offline read says.

This is the capture of where the object stands on the format the novelty claim lives on, before the encoder rewrite. Exit condition: the run itself — not a rating, not top-500.

Top-500 admission is an Elo threshold set by other people's activity on a thin format. It is not a measurement of the agent, and chasing it can absorb weeks that belong to step 3. The novelty claim is already banked by the local benchmarks; the ladder is legibility, not proof. A mediocre run here does not mean the story failed.

### 3. Fable ultracode → gen4 encoder + model
Full encoder rewrite: items, abilities, weather, hazards, SpA/SpD split. Note gen4 is where physical/special becomes a per-move field rather than type-determined — that branch changes here and does not carry back.

Mine Wang's forks first. quadraticmuffin/poke-env is ~36 gen4 state-tracking fixes found the expensive way — Max PP, Sleep Talk double-decrementing, weather-from-abilities persistence, sleep counters, Trace base-ability parsing, maybe_trapped, _force_switch as a list. Diff it against our pinned 0.15.0 and check which survived upstreaming. A silently wrong observation field looks exactly like a training problem. His pokemon-showdown fork is MCTS infrastructure (>getstate/>load, constrained team regen) and is not needed unless we do search.

Steal his observation design where it fits (Tables A.1/A.2): multi-turn effect durations as one-hot counters to restore Markovianity, HP binned, PP as floor(pp^(1/3)). Our encoder is ours, but these are solved problems.

### 4. Gen4 train — start from Wang's published recipe
Use his hyperparameters as the starting config, not a from-scratch guess (Table A.3): γ 0.9999, λ 0.754, 7 epochs, clip 0.0829, value clip 0.0184, ent 0.0588, vf 0.4375, grad-norm 0.543, n_steps 78×512, batch 1024, hidden 256, features 896. Plus his LR schedule 10^-4.23/(8x+1)^1.5 — the only controlled annealing ablation in this literature.

This is a config, not a teacher — it stays inside the purity lane. He ran SB3, so any residual gap partly measures SB3's implementation against ours. State it in step 5 rather than let a reader find it.

Consider the 3v3 surrogate for tuning. He ran Bayesian optimization on 3v3 battles — half the episode length, most of the complexity, far cheaper per trial. That's how hyperparameter search becomes affordable, and we have never been able to afford it.

### 5. Gen4 offline evals vs Wang
**Exit condition: "close enough" to his offline numbers.**

**Pin the target before starting.** His Table 4.1 says 0.786 vs `SimpleHeuristicsPlayer`; his Figure 4.1 reads closer to 0.85. Our own prior-work index flags this as unreconciled. Choose which one we are matching, in writing, and define what "matched" means numerically — deciding afterward is how a comparison becomes a rationalization.

**Disclose the confound:** he ran Stable-Baselines3 with its defaults. Any gap partly measures SB3's tuned recipe against our from-scratch PPO, not only architecture and scale. Legible, but say it rather than let a reader find it.

This step is the real gen4 deliverable.

### 6. Gen4 ladder — one run
**Exit condition: the run.**

Lower value than it looks, and worth knowing why before spending on it: Wang's headline ladder result *includes MCTS at inference*. Ours will not. So this is not a like-for-like comparison — it is a data point for the complexity curve and a sanity check that the gen4 agent works against humans. Do not let it become a second gen4 chapter.

### 7. Record results
Gen4 chapter closes. **Give gen4 a written exit condition when the chapter is opened**, or it becomes where the project lives. It is a borrowed instrument, not a home.

### 8. Back to gen1 — retrain with any special sauce
Recipe findings are generation-agnostic: rollout size, minibatch structure, λ and γ, LR schedule, privileged critic, auxiliary heads, opponent-pool composition, entropy scheduling. None of those are gen4 facts. Port them home.

**Pre-register the gen1 re-test as part of the gen4 chapter, before running it.** Anything tuned against episode length may not survive the trip — λ especially, since its effect scales as λ^(T−t), and that is a different regime at T≈25 than at T≈100.

**A null here is a finding, not a failure:** a lever that helps in gen4 but not gen1 is evidence it is episode-length- or complexity-sensitive. That is a claim only a multi-generation study can make, and it is more interesting than either number alone. But it only reads that way if the test was pre-registered.

### 9. Check whether offline evals moved
The honest checkpoint. Did the borrowed recipe actually transfer?

### 10. Massive gen1 train
The big one, with a recipe validated somewhere the instrument works.

### 11. Final gen1 ladder
The number the story ends on.

### 12. Wrap the story
Novelty (gen1), validation (gen4), and the transfer result. Three points on a complexity curve, and a recipe developed where it could be seen and tested where it couldn't.

### 13. OPTIONAL — gen9 via ultracode, and live there
Where the comparators are. Terastallization genuinely expands the action space rather than adding fields, so it is a capability test and not just a bigger encoder. Thick ladder means cheaper, less time-of-day-dependent evaluation. Poke-engine's best-vetted generation, so the Foul Play anchor improves too.

If we only ever get two generations, make them gen1 and gen9 — trade the clean transfer claim for relevance.

---

## Standing notes

- **The binding constraint is not time.** It is that gen1 measurements are currently uninterpretable at k=3 with σ_seed ≈ 0.062 against a 0.072 bar. Every sequencing decision above follows from that.
- **Weights never transfer between generations** — only recipe. Wang tried a bootstrapping variant and reported no significant improvement (§5.1.3); H&L's specialized agent won 77/500 against its own predecessor after a short fine-tune. Mechanics differ too much and the observation space changes anyway.
- **Gen 5+ introduces team preview**, which *removes* the hidden-team problem. Gens 1–4 keep it. Worth stating in any writeup that gen1 is harder than gen9 on partial observability even as gen9 is harder on mechanics.

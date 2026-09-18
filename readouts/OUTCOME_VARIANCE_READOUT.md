# The luck ceiling — how much of a gen-1 battle is decided by chance rather than by play?

`scripts/outcome_variance.py`, run 2026-09-18 on the R5 committee.
`results/outcome_variance/variance.json` (+ `variance.json.rows.jsonl`, one row
per position). Hacking run, **credits nothing**. RESULTS §27. IDEAS **2.11**.

## Why it was run first

RESULTS §21 measured `explained_variance` pinned at ~0.59 while 2.67× critic
width and 126× first-layer rank bought **zero** of it. §22/§23/§24/§26 then
measured that search buys nothing at depth with either evaluator and does not
beat greedy with any of four constructions. **Both results have the same
untested explanation, and nobody had checked it: the format may simply be
mostly luck.** If so, the critic is done, no leaf evaluator can be much better,
and every remaining lever belongs on the POLICY — which would re-rank the whole
of `docs/IDEAS_POST_100M.md`, and in particular would make **4.9 (expert
iteration)** a bad place to spend a fleet. It costs minutes; 4.9 costs days.

## What is measured, and against whose information

Each position is held at **OUR OBSERVATION** — the right conditioning set,
because that is the function whose EV we are trying to explain. Then both
irreducible sources are varied: **4 determinizations** consistent with that
observation (the same RSD sampler the search uses) × **8 rollouts** each, under
the **same deterministic committee on both seats**. Everything that differs
afterwards is noise the critic could not have known: engine chance (crits,
freeze, full paralysis, sleep turns, damage rolls, speed ties) and hidden
information (the opponent's unrevealed team and moves).

The critic's own EV is computed **on the same positions and the same rollouts**.

## The result — 707 positions, 22,358 rollouts

| quantity | value |
|---|---|
| mean outcome | **−0.0006** |
| σ² within an observation (irreducible) | 0.6366 |
| σ² between observations (what play controls) | 0.3627 |
| **EV ceiling for ANY critic reading our observation** | **0.3630** |
| our critic's EV on these same positions | **0.2176** |
| **headroom** | **+0.1454** |

**Roughly 64% of the outcome variance at a mid-battle position is irreducible.**
Of the 36% that is knowable, our critic captures **60%** of it.

**THE SANITY CHECK THAT MATTERS: the mean outcome is −0.0006 over 22,358
rollouts.** The rollout is self-play with the same policy on both seats, so it
*must* come out even; `_swap` building the opponent's view of the position is
the one hand-written piece that could have broken silently, and this is the
measurement that says it did not.

## By turn — the pooled number is a statement about the turn mix

| turns | positions | EV ceiling | our critic | critic / ceiling |
|---|---|---|---|---|
| 2–8 | 173 | 0.1586 | 0.0393 | **25%** |
| 9–15 | 157 | 0.2049 | 0.0445 | **22%** |
| 16–22 | 187 | 0.4870 | 0.3319 | 68% |
| 23+ | 190 | 0.5564 | 0.4053 | 73% |

**Both things rise with the turn, and they do not rise together.** Late in a
battle the position is genuinely more predictable (ceiling 0.56) *and* the
critic captures most of what is there (73%). **Early, the ceiling is low AND the
critic captures a quarter of it** — so the largest *proportional* gap is in the
opening, which is also where a battle is most winnable by better play.

## The verdict, stated as a gate

**THE GATE OPENS. The critic is NOT at the format's ceiling.** The kill branch
for 4.9 was "EV_ceiling ≈ our critic's EV", and it does not fire: there is
**+0.145 of explainable variance unclaimed**, about 40% of what is knowable.
Expert iteration, a better evaluator, and search that acts on one are all still
live on this evidence.

**Where it points:** the early game. A critic that is at 73% of the ceiling at
turn 23 and 25% at turn 5 is not short of capacity — it is short of signal about
positions whose outcome is still open, which is exactly the regime search visits
and exactly what training on search-visited states would address.

## What may NOT be said with these numbers

- **NEVER set the training `explained_variance` (~0.59) against this ceiling.**
  That number is computed over PPO's whole batch — every timestep of many
  episodes, including near-terminal states where the outcome is already decided
  — while every position here is mid-battle. They are different state
  distributions, and comparing them is the unmatched comparison that turned a
  −0.0007 null into a −0.053 "result" on 2026-09-17. **The matched pair is
  `critic_ev_here` 0.2176 against `ev_ceiling_unbiased` 0.3630.**
- **The naive ratio (0.3818) is biased UP and is reported only for comparison.**
  `var_between` is the variance of position MEANS, each from ~32 rollouts, so it
  carries their sampling noise; the one-way random-effects decomposition
  (0.3630) is the number to read. The bias runs toward *more* headroom, i.e.
  toward spending a fleet.
- This is a property of **the format measured through our own encoder and
  policy**, not a claim about the ladder and not a win rate. A different encoder
  sees a different observation and has a different ceiling.
- The stop turn is drawn uniformly from [2, 36), so a late position exists only
  in a battle that lasted that long. That is **not** a bias for the per-turn rows
  (the population at turn *t* is the battles that reached turn *t*) but it does
  weight the POOLED number toward longer games.

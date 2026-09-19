# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED). The post-ladder SEARCH chapter is CLOSED, and closed by a CORRECTION PASS
**Nothing is running. Tree clean, suite green 1219 / 0 failed / 87 skipped.** Eight blocks
ran 09-18/19 (§25–§32); **three Opus review passes then went back over every claim and
changed sixteen of them, retracted one section in full, and found three numbers I had
invented while writing the corrections themselves.** Read §30.1's retraction box and the
§27.1 CV box before quoting anything from this week.

## THE FIVE RESULTS WORTH CARRYING FORWARD
**§30 — GREEDY BEATS EVERY SEARCH ARM, and it is a COST, not another null.** n=1000×7 off
FP@20 on the R5 committee with an in-session anchor: **GC greedy 0.6050** is the top of the
block. Ungated depth-1 **−0.052 at 2.4 se**; depth-2 **−0.076 / −0.098 at 3.4–4.4 se**.
**The block validated itself** — D1O and DUM are the SAME config on two username pairs and
read **0.5510 / 0.5530, |d| 0.0020**, so the within-session floor is a tenth of one
cross-session rung. **"Monotone in the change rate" was published and is FALSE** (0.584 at
6.4% rises to 0.587 at 9.1%); the defensible claim is the level ordering.
**§30/8.5 — the committee does NOT know WHERE to search, but SEARCHING LESS BEAT SEARCHING
MORE.** Gated on committee disagreement vs a **COIN at a matched rate: +0.0030 at 0.14 se,
selection is a null.** Gated (40%) vs ungated (93%), both replicates pooled per side:
**+0.0335 at 2.14 se**, clearing both halves of the credit line. Post-hoc pooling, credits
nothing — but the dose intuition is backwards.
**§27 + §27.1 — THE LUCK CEILING, and the critic's real deficit.** 707 positions / 22,358
rollouts: **~64% of a mid-battle outcome is IRREDUCIBLE**; ceiling **0.3630**, critic
**0.2176**. **THE GATE OPENS — the critic is NOT done.** Out-of-sample isotonic buys
**+0.0096, only ~7% of the gap: 93% is RANKING** (corrected from 12/88 — the published CV
split at the OUTCOME level while the predictor is constant within a POSITION, so every
held-out outcome had its own position in training). Worst in
the **OPENING** (r² 0.287 at turns 2–8 vs 0.727 at 23+). **Never set the training EV 0.59
against this ceiling** — a different state distribution.
**§31 — THE CRITIC IS NOT ANTISYMMETRIC: +0.059 to whichever side it is pointed at,
z 14.7**, 5× larger in the opening. **Mechanism identified:** that is its training
distribution's own mean return — league play fits it against *older, weaker* checkpoints
(+0.036 whole-run) while eval is a mirror where the truth is 0. **A TRAIN/EVAL
DISTRIBUTION SHIFT. IDEAS 4.1's claim on this evidence is WITHDRAWN** (p1/p2 are
symmetric); 4.1 keeps its sample-efficiency argument.
**§28 + §29 — two facts about our own policy form.** §28: **103 of 104 turn-cap battles
enumerated** — 100 are switch loops, **94 (91.3%)** with the opponent immobilised on ≥80%
of turns while our seat oscillates. **The mechanism is the locked protocol's own
DETERMINISM**: argmax in a state that stopped changing repeats forever; training SAMPLES.
§29: **the annealed tail trades EV for WIN RATE in 9 lanes of 9** — EV
−0.060/−0.088/−0.005, win rate +0.059/+0.062/+0.033. **DO NOT FLOOR THE LR. Third
independent measurement that EV IS NOT THE OBJECTIVE** (§21 width, §27.1 ranking, §29).

## WHAT THE REVIEW PASSES CHANGED — **read before citing anything from this week**
**Five review passes. ~25 claims changed, ONE SECTION RETRACTED, and several of the errors
were INSIDE the corrections.** The full table is in `HANDOFF.md`; the four that change what
you may cite:
- **§30.1 RETRACTED IN FULL.** It relaxed the "never difference across sessions" landmine
  on a G-test whose power at 0.02 is **0.13** (it claimed "G≈12, p≈0.02" without computing
  it). Heterogeneity sits **between days** (G 2.760 of 3.139 on 2 df). **THE LANDMINE
  STANDS**, on the honest ground that 0.02 is UNRESOLVED. Pooled greedy **0.5818 (n=6500)**
  keeps. The retraction did NOT reach `docs/landmines.md` for a day — it does now.
- **§27.1: 12%/88% → 7%/93%** (the CV split at the OUTCOME level while the predictor is
  constant within a POSITION). **"Affine beats isotonic" is WITHDRAWN — a SEED-0 artifact**:
  over 40 CV seeds +0.00055 ± 0.00128, affine ahead 24/40, the margin *half of isotonic's
  own seed-to-seed sd*. **One CV fold draw is one rung.**
- **§28's "every stall" rested on SIX battles** → 91.3%. **§31's "the sampler is exonerated"
  INVERTS its own probe** (V(s) and V(swap(s)) share a determinization, so it carries zero
  information about the sampler). **§32 withdrew the "90.9% of root visits" caveat** quoted
  all week: one smoke decision; measured `pi_top1` **0.417** vs the prior's 0.885.
- **THE CORRECTIONS THEMSELVES NEEDED CORRECTING SIX TIMES** — a KL lifted from a GOLDEN
  TEST FIXTURE, an uncomputed median G *inside the paragraph charging that a number was
  never computed*, a test asserting a SOURCE STRING (so it survived commenting the code
  out), and a denominator wrong at six sites. **Both lessons are in `docs/landmines.md` and
  CLAUDE.md** — STATUS is rewritten in place and cannot hold them.
- **NINE defect-class fixes, all ONE shape — a dial or counter that runs and reports
  nothing, or the wrong thing.** Structural repair: `ch3_eval` DERIVES its forwarded dials
  from `SearchAgent`'s signature and **hard-fails on an unknown pre-reg key**.

## Next actions
1. **R6 PREP PLAN WRITTEN — `docs/proposals/R6_PREP_PLAN_2026-09-19.md` (NOT ratified; six rulings inside).** The R5
   loss autopsy (IDEAS 2.15) reads the format as luck-dominated and our style at parity, so R6 = the W + C6 base, trio A 4.11, trio B 4.12; no width, no 300M; transformer and expert iteration gated for R7.
2. **The search chapter is closed for now: §30 is a measured COST, not a null.** The next
   search idea must argue against the override regression (−0.48 win rate per unit override
   fraction, r −0.875, leave-one-out stable), not merely propose another vehicle.
3. **The live lever is the CRITIC, and §27/§27.1/§31 say what is wrong with it**: 93% of
   the gap is RANKING, worst in the opening, and the train/eval shift is measured at +0.059.
   `docs/IDEAS_POST_100M.md` Round 4 is re-ranked around that. **4.9 (expert iteration) is
   the top §4 item and its 2.11 gate has OPENED.**
4. **SIX RULINGS OWED:** the LOOP BREAKER (§28 — it changes the policy form); R6's SPLIT
   SCHEDULE (CLEANUP L1); the next fleet's shape; whether 4.9 gets a fleet; whether **2.13's
   recalibration is ON BY DEFAULT** (§32.1 — it changes the object); whether **8.6's
   mis-specified criterion earns a RE-RUN** (§32). **The LR-anneal floor now has its
   evidence (§29): DO NOT floor it.**
5. **`scripts/action_gap.py` — the one instrument that could CLOSE the search axis** (the
   prize: P(top-1 worse than top-2) × E|ΔQ|, no evaluator, no search). **Written, UNRUN,
   and INVALID — two defects that both SHRINK the gap** (CLEANUP L9), i.e. bias it toward
   the ceiling it would license. Fixing it is contained and high value.

## Watch items
- **A SMALL-RUN NULL IS NOT EVIDENCE ABOUT A LEVER** (CLAUDE.md rule 6). §30's selection
  null is quoted as *"+0.003 at 0.022 se"*, never as a kill: it does not exclude a
  credit-sized effect. **§30's ungated arms ARE a kill-shaped result** because they measure
  a COST at 2.4–4.4 se, which is the distinction rule 6 turns on.
- **SEEDS DO NOT PAIR BATTLES**; replicates are the instrument. **Never difference across
  sessions without an in-block anchor** (§30.1 retraction).
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS ONLY** (2026-09-17) — hacking needs
  none, and the anti-self-deception rules do not relax: **counters to disk, matched
  comparisons, same-session anchors.** All three were violated at least once this week and
  each violation was caught only by a second pass.

# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED). The post-ladder SEARCH chapter is CLOSED, and closed by a CORRECTION PASS
**RUNNING: the exit-gate queue (IDEAS 4.9's gate; `configs/eval/exit_gate_r5.yaml`, `scripts/exit_gate_queue.sh`) — GAP DONE (§33), XSM DONE, XGR (the greedy control) DONE 09-21 00:35Z at **0.5866 (n=3200, ties 2)**, **XTG9 (tree@900) RUNNING since 00:36Z at ~24.3 s/battle, 2,091/3,200 at 14:43Z → QUEUE DONE ≈ 22:10Z = 18:10 EDT 09-21**, then `results/exit_gate_r5/READOUT.txt`. CHECK: `tail -3 logs/exit_gate_r5/queue.log` and `grep -c Winner results/exit_gate_r5/xtg9.fp.stdout` (stalled = the count stops for ~10 min or the search seat's CPU time does not advance in 15 s; a watch with both instruments is armed this session); a dead FP arm poisons its username pair for hours — add a fresh prefix-free pair to the config before relaunching with GO present. NOTHING starts on the box before QUEUE DONE. THEN the launch-night runbook (SESSION_LOGS 2026-09-21 cont. 2 + cont. 3): BOTH 12M screens (GO keys 204/212 and the fallback keys 220/228, `configs/showdown_r6_batch12m{,_fallback}.yaml`) → `scripts/r6_smokes.sh` beside them → `scripts/exit_gate_readout.py` → `scripts/r6_batch12m_read.py` on each → the launch blocks. RULED: the maintainer launches both trios TOGETHER (morning if late), the agent launches nothing 24 h+; OPEN RULING: trio B in the FALLBACK form regardless of the screen (recommended yes; cont. 3 has the 8×-fewer-steps arithmetic and RESULTS §17's shape). Two pre-launch Opus reviews fixed five confirmed defects (cont. 3): the aux gradient now sits AFTER the shared clip, trio B's league cadence is env-step-matched, the reads queue's guards work during and after the fleet, a resume stamps its sha.** Eight blocks
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
were INSIDE the corrections.** The full table is in SESSION_LOGS 2026-09-19 and 2026-09-19 (cont.); the four that change what
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
1. **R6 PREP — DONE 09-20/21: the action gap banked (§33), 4.11's heads + loss BUILT (unsmoked), the C6 RUST
   PORT LANDED (P-1 zero mismatches, flag on: ruling 2 met, C6 rides R6), the R6 trio configs DRAFTED with the launcher's C6 export, and R7's ARCHITECTURE GATE READ: the attention screen DOES NOT CLEAR (§34: +0.0179 at 6.52×, flat reveal profile = generic capacity; no R7 attention trio).** NEXT, after QUEUE DONE: the 4.12 screen, the 400k smokes (`scripts/r6_smokes.sh` → `scripts/r6_smoke_check.py`, every expectation derived), the exit-gate readout (`scripts/exit_gate_readout.py`, computed from disk), the screen read (`scripts/r6_batch12m_read.py`), the fleet (maintainer launches); the post-fleet reads are BUILT (`scripts/r6_reads_queue.sh`, `configs/eval/r6_reads*.yaml`); then the split-schedule ladder (DRAFT `docs/proposals/ladder_r6.draft.yaml`, M-R6-1..7 owed).
2. **The search chapter is closed for now: §30 is a measured COST, not a null.** The next
   search idea must argue against the override regression (−0.48 win rate per unit override
   fraction, r −0.875, leave-one-out stable), not merely propose another vehicle.
3. **The live lever is the CRITIC, and §27/§27.1/§31 say what is wrong with it**: 93% of
   the gap is RANKING, worst in the opening, and the train/eval shift is measured at +0.059.
   `docs/IDEAS_POST_100M.md` Round 4 is re-ranked around that. **4.9 (expert iteration) is
   the top §4 item and its 2.11 gate has OPENED.**
4. **THE SIX R6 RULINGS ARE TAKEN (maintainer, 2026-09-20, "agree with all"):** loop breaker ON
   for the ladder object; C6 in R6 only if the Rust port lands first; fleet = W base, trio A
   outcome heads, trio B batch/epochs; R6 ladder under the split schedule; 2.13 stays OFF; the
   two R7 gates run now (the exit-gate queue was relaunched 09-20). Also: 4.9's fleet waits on
   that gate; 8.6's re-run is subsumed by it. **The LR-anneal floor: DO NOT floor it (§29).**
5. **THE ACTION GAP IS MEASURED (RESULTS §33, `readouts/ACTION_GAP_R5_READOUT.md`): a perfect
   top-2 swap is worth 0.032 naive [0.022, 0.043] / 0.024 deconvolved of win rate per decision —
   AT the credit floor, NEITHER a mechanism kill NOR a licence.** Noise alone would print 0.029;
   true gaps have sd ≈ 0.16 outcome units, ordered right ~59% of the time. The exit gate decides 4.9.

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

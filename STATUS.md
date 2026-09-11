# STATUS
## JOURNEY POSITION — step 7.5 (engine port) **EXITED 2026-09-10**; next is gen-1 step 8/10
**GEN-4 CHAPTER CLOSED (2026-09-09):** step 3 MET (M-YES), step 5 MET (S5-MATCHED), step 6
BANKED NOT RUN, step 7 is RESULTS §19. vs SH 3×3000 greedy **0.8788**, band on the
seed-clustered 0.00452, **CREDITS NOTHING**. LADDER R4: GXE 65.2 / Glicko 1618 ± 25 / Elo
1354, n=200. **From here it is all gen 1.**

## JOURNEY 7.5 — the engine port, EXITED (full account docs/engine_port/NOTES.md)
- **A-1 PASSED TWICE** (maintainer ratified RW-1..9, RW-10 no). Engine arm at the 12M rung,
  n=12,000/seed vs the banked async 0.67211: pre-fix pooled 0.67067 (−0.00144), **FIXED
  (bd3d06a) 0.66775, −0.00436, A1-PASS**, −0.59 se on the seed-clustered 0.00736.
  **−0.00436 travels forever.** P-AUC −0.00298 INSIDE.
- **A-1a EARNED ITS PLACE:** 10× separation on dims 627/673/719 — the foe's revealed-move
  **PP fraction**; `track.rs` hard-coded `pp = max_pp`. **P-1 structurally could not see it.**

## SEARCH IS CRACKED — the defect was the SELECTOR, not the evaluator
**D5 margin gate: play search's action only if it beats the POLICY's argmax by > delta.**
Absent = exact no-op (golden digest); delta=inf is exactly greedy. s112, n=3000/arm, vs SH:

| delta | 0 | 0.02 | 0.05 | **0.10** | 0.15 | 0.20 | inf (greedy) |
|---|---|---|---|---|---|---|---|
| win rate | 0.74767 | 0.78200 | 0.80867 | **0.82400** | 0.81400 | 0.81000 | 0.78233 |
| override rate | 0.71 | 0.445 | 0.232 | **0.085** | 0.040 | 0.021 | 0 |

- **HUMP FIRED AND THE PEAK IS NOW BRACKETED** — it falls off on BOTH sides. Interior max
  at delta 0.10, **+0.04167 over greedy on the same checkpoint, ZERO training.**
- **delta WAS SELECTED ON s112, so s112's +0.0417 is IN-SAMPLE and optimistic.** The honest
  read is out of sample: **s104 0.80900 vs greedy 0.78933 = +0.01967**; s120 pending (9/10).
  Quote the out-of-sample pooled number, never s112's, and say which is which.
- Cost **77.6 ms/decision** at the peak — 0.05% of the ladder's 150 s/turn.
- S3's earlier NEG cells (P-M −0.0681, P-B −0.0088, P-BA −0.0769) were all **D4** objects.
- **S1 fired and its fix did not pay** (leaf bias +0.0497, sd 0.125 vs margins 0.028;
  det_blind collapses it offline and moved win rate by nothing). Encoding was not the defect.
- **WANG OVERTURNED "the evaluator is the answer"**: +12 pts vs SH on the **UNMODIFIED PPO
  critic**; what differs is SELECTION (prior inside PUCT, decide by MAX VISIT COUNT not max Q).

## LANDMINE — **every search number before 2026-09-11 measures a BROKEN selector**
Grep `PRE-D5`. **LADDER R3 is a D4 object.** Such a number may NOT be used to argue that
search, depth or dose does not pay. Re-measure under D5 or do not cite it.

## Engine-native search — P0 and R1-E both read out 2026-09-10
- **P0 STOP RULE PASSES — depth-2 is NOT killed.** sd(margin | S=32, CRN-1) **0.00835** vs
  the 0.5×median bar **0.01640** (ratio 0.509); passes on the median too. **CRN-1 is worth
  exactly 2× the samples at S=32, measured.** Pre-register **S=16** for depth-2, not 52.
- **Depth-1's honest speedup is ~4×** at S=32 (not 17×, not 3×) — **quote it with the dose.**
  **65% of per-child cost is Python marshalling that Phase 2 deletes**, so no engine ceiling
  can be read off today's loop. Restriction cost said loudly: only 45.3% of roots survive.
- **R1-E gate built and run** (13,396 roots, poke_engine stand-in): **leg A FAILS on exactly
  ONE undeclared dim** (F5, a mon that faints asleep keeps `status_counter`); leg B PASS
  (disclosed internal-only); **leg C PASS 99.686%** vs a 99.5% hard stop; **controls 8/8**.
- **Rust write side landed** (+739 lines, 0 deleted, 94 cargo tests). It corrected the design
  in three places: `B_LAST_MOVES.index` is load-bearing for V_CHARGING and 0 is an
  unconditional OOB read (charging roots must be REFUSED); **W-ACTIVESTATS is wrong on
  ≤24.38% of roots, not 2.26%**; W-VALIDATE's `order[0]` rule would reject 14.73% of the
  harvest. Amendments applied to R1-E BEFORE readout with provenance and
  `post_dates_first_numbers: true`; the pre-bar artifact is preserved and **every number is
  identical leg by leg** — leg A fails under BOTH bars, on the same dim.
- **Editable reinstall still OWED** (`pip install --no-build-isolation -e engine/pkmn_gen1`)
  — MUST NOT run while `engine_pe_s66` is alive. The Python surface is UNEXERCISED until it does.

## The monster (JOURNEY 10) — reviewed; THREE THINGS CHANGED, maintainer decisions owed
1. **ARM B IS BITWISE ARM A — PROVEN, not argued.** runs/engine_pe_s66 vs engine_a1b_s66 at
   10.5M: **21 identical checkpoint rungs, 223 shared tensors / 3,428,015 elements, 0
   differing, sha 104a9339eb6a2260.** The head takes a separate `autograd.grad` and rewinds
   the RNG. **So B must RIDE arm A's lanes, not cost three of its own** — 3 of 9 lanes were
   buying duplicate checkpoints. Cost of the rider is wall only (~+56% params, update-side).
2. **ARM B'S TARGET WAS WRONG AND IS FIXED (b147f48).** The head regressed the GAE(0.95)
   target, which at gamma 1 with terminal-only reward is **~53% the ORDINARY critic's own
   output (~82% at turn 1)** — the network it exists to beat. It survived because its only
   learning test ran at lambda 1.0, where the GAE target already IS the MC return: **the
   tested path was not the production path.** Now regresses the outcome on BOTH drivers.
   New verdict metric `priv_eval/ev_mc_advantage`; the old EV is a DIAGNOSTIC, never a verdict.
3. **ARM C IS CONTESTED BY BOTH REVIEWS.** It is D18's exact lever at lambda 0.95, but the
   vacatur named the **lambda=1.0 pure-baseline** variant as the live hypothesis; and its
   variance channel has **30× less headroom** at a 30,720-step update than at D18's 1,024.
   Its falsifier also conditions on an "uncollapsed critic" that has **never exceeded 25/384
   on any lane at any dose** — as written the falsifier cannot fire and the arm returns no cell.
- **Both reviews also flag: no search seam exists** (`grep priv_eval_value rl/search/` = 0),
  so neither B nor C can be read through search today; and **k=3 × n=3000 gives
  P(credit | +0.025) = 0.45** — a coin flip at its own bar.

## Next actions
0. **GOAL (maintainer, 2026-09-11): not "clear top 500" but "AS HIGH AS POSSIBLE".** R4 hit
   Elo 1354 vs a 1358.999 cutoff — missed by 5. Targets: H&L 1677 / ps-ppo 1725 / **Wang
   1756** (the in-charter one). Metamon's 1761 used HUMAN REPLAYS — out of bounds.
1. **DECISIONS OWED BEFORE LAUNCH** (all four in the handoff): fold B into A's lanes and
   spend the freed 3 on seeds?; keep, re-specify or drop C?; primary axis off-FP@20 vs the
   saturated vs-SH (at p 0.789 credit needs ≥ 0.81367)?; read each arm at ITS OWN delta peak.
2. **Free, measured, and NOT in the design:** the 3-seed inference ensemble (+0.036, credited
   at B1) composed with the D5 gate (+0.042). Structurally orthogonal, zero training cost.
3. **Chores owed:** `engine_a1_grade.py` must run `extract_history.py` before the AUC leg;
   8 corrections to the Wang row in `prior_work/README.md`; the engine editable reinstall.

## Watch items
- **SUITE GREEN** 995 (port env); 143 across ppo/privileged/episode/harvest after b147f48.
  **No single env runs engine + analysis** (CLEANUP E1).
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200.
- Post-fix between-seed sd 0.01938 → 0.00368 is **DESCRIPTIVE ONLY**; re-check on the fleet.

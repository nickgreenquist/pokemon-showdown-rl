# STATUS
## JOURNEY POSITION — step 7.5 (engine port) **EXITED 2026-09-10**; next is gen-1 step 8/10
**GEN-4 CLOSED (RESULTS §19):** steps 3/5 MET, vs SH 0.8788, CREDITS NOTHING. **LADDER R4:
GXE 65.2 / Glicko 1618 ± 25 / Elo 1354, n=200. From here it is all gen 1.**

## JOURNEY 7.5 — the engine port, EXITED (full account docs/engine_port/NOTES.md)
- **A-1 PASSED TWICE.** 12M rung, n=12,000/seed vs banked async 0.67211: **FIXED 0.66775,
  −0.00436, A1-PASS**; **−0.00436 travels forever.** **A-1a EARNED ITS PLACE** — 10×
  separation on the foe's revealed-move PP dims; **P-1 structurally could not see it.**
## **ENS3 CREDITS (+0.0349) — the strongest FREE object we have**
First run of the log-prob ensemble on the 100M finals. **ENS3 0.82356 (n=9000) vs fresh greedy
A0 0.78867 (n=9000) = +0.03489, se_diff 0.005888, 5.93 se → CREDIT** (meets the +0.025 floor
AND 2·se_diff). Batches 0.82667 / 0.81467 / 0.82933; flip rate ~0.108 so the wrapper is live;
0 desyncs. **It beats the gated search's IN-SAMPLE peak (0.82400) at GREEDY SPEED.** Two
disclosures travel: the **clustered se is UNAVAILABLE by construction** (three lanes = ONE
committee, so the batch spread is EVAL noise and the binomial governs — anti-conservative),
and it licenses **"ensembling THESE three checkpoints at 100M", NEVER "ensembling helps"** —
LADDER R1's own limitation, repeated deliberately. A README row WAITS on the anchor battery.

## SEARCH: the defect WAS the SELECTOR — fixed, positive out of sample, NOT yet credit-grade
**D5 margin gate: play search's action only if it beats the POLICY's argmax by > delta.**
Absent = exact no-op (golden digest); delta=inf is exactly greedy. s112, n=3000/arm, vs SH:

| delta | 0 | 0.02 | 0.05 | **0.10** | 0.15 | 0.20 | inf (greedy) |
|---|---|---|---|---|---|---|---|
| win rate | 0.74767 | 0.78200 | 0.80867 | **0.82400** | 0.81400 | 0.81000 | 0.78233 |
| override rate | 0.71 | 0.445 | 0.232 | **0.085** | 0.040 | 0.021 | 0 |

- **HUMP FIRED AND THE PEAK IS BRACKETED** — it falls off on BOTH sides; interior max at
  delta 0.10. But **delta WAS SELECTED ON s112, so that +0.04167 is IN-SAMPLE.**
- **THE HONEST READ IS OUT OF SAMPLE AND IT IS +0.016, NOT +0.042.** Both held-out lanes at
  delta 0.10, n=3000 each: **s104 0.80900 vs 0.78933 = +0.01967**, **s120 0.80667 vs
  0.79433 = +0.01233**. **Pooled n=6000: +0.01600 = 2.19 se_diff (binomial 0.00730; the
  2-lane clustered se is smaller, so binomial governs under larger-of).**
  **CREDIT LINE: MEETS 2*se_diff, MISSES the +0.025 floor -> NOT CREDITED.**
  Selection shrank the effect by 2.6x. **Never quote s112's +0.0417 as the gate's effect.**
- So: the selector WAS the defect and fixing it moved search from **-0.0681 to +0.016**,
  which is real, free and reproducible on 2/2 held-out lanes — and still **below the bar**.
  delta 0.10 is also only known to be the peak ON s112; the per-lane curves are unmeasured.
- **OFF FOUL PLAY THE GATE TRANSFERS — pre-decided branch FIRED.** BLM (gated@M, delta 0.10,
  s112) vs FP@20, n=1000: **0.525** against a **0.47** bar. Same lane/checkpoint: banked greedy
  0.50167 (n=3000), UNGATED search 0.39600. **The SELECTOR ALONE bought +0.129 off-FP** —
  −0.106-vs-greedy → **+0.023** (1.28 se, NOT significant; TRANSFERS = not SH-facing, NOT
  that it beats greedy). Stage 2 (BLL) auto-launched. Both FP@20 disclosures travel.
- 77.6 ms/decision at the peak. S3's NEG cells were all **D4**. S1's fix did not pay.

## LANDMINE — **every search number before 2026-09-11 measures a BROKEN selector**
Grep `PRE-D5`. **LADDER R3 is a D4 object.** Such a number may NOT be used to argue that
search, depth or dose does not pay. Re-measure under D5 or do not cite it.

## Engine-native search — P0 and R1-E read out 2026-09-10
- **P0 STOP RULE PASSES — depth-2 is NOT killed.** sd(margin | S=32, CRN-1) **0.00835** vs the
  0.5×median bar **0.01640** (ratio 0.509). **CRN-1 = 2× the samples, measured.** Depth-2
  pre-registers **S=16**, not 52. **Depth-1's honest speedup is ~4×** at S=32 (not 17×) —
  quote WITH the dose; 65% of per-child cost is Python marshalling Phase 2 deletes.
- **R1-E built and run** (13,396 roots): **leg A FAILS on exactly ONE undeclared dim** (F5);
  leg B PASS (internal-only); **leg C PASS 99.686%** vs a 99.5% stop; **controls 8/8**.
- **Rust write side landed** (+739/0, 94 tests), correcting the design three times:
  `B_LAST_MOVES.index` is load-bearing for V_CHARGING and 0 is an unconditional OOB read;
  **W-ACTIVESTATS wrong on ≤24.38% of roots, not 2.26%**; `order[0]` would reject 14.73%.
  Amendments reached R1-E BEFORE readout with provenance; **leg A fails under BOTH bars.**
- **Editable reinstall DONE 2026-09-11**, Python write surface EXERCISED: a built root
  validates, 200 engine-produced states all pass W-VALIDATE, all-zero bytes rejected by name.

## The monster (JOURNEY 10) — reviewed; THREE THINGS CHANGED, maintainer decisions owed
1. **ARM B IS BITWISE ARM A — PROVEN AT THE FULL 12M HORIZON.** The design-B smoke finished:
   engine_pe_s66 vs engine_a1b_s66 at ckpt_012000017 (same step, **24 identical rungs**),
   **223 shared tensors / 3,428,015 elements, 0 differing, sha f156f232462e635b**; the head
   is present (26 tensors, 642,305 params) and touches nothing. **So B must RIDE arm A's
   lanes** — 3 of 9 lanes bought duplicate checkpoints. Rider cost is wall only.
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
- **No search seam exists** (`grep priv_eval_value rl/search/` = 0) so neither B nor C can be
  read through search today; and **k=3 × n=3000 gives P(credit | +0.025) = 0.45.**

## Next actions
0. **GOAL: "AS HIGH AS POSSIBLE", not "clear top 500".** R4 hit Elo 1354 vs a 1358.999
   cutoff. Targets: H&L 1677 / ps-ppo 1725 / **Wang 1756** (Metamon's 1761 used REPLAYS).
1. **DECISIONS OWED BEFORE LAUNCH** (all four in the handoff): fold B into A's lanes and
   spend the freed 3 on seeds?; keep, re-specify or drop C?; primary axis off-FP@20 vs the
   saturated vs-SH (at p 0.789 credit needs ≥ 0.81367)?; read each arm at ITS OWN delta peak.
2. **Free, measured, NOT in the design:** the 3-seed inference ensemble (+0.036, credited at
   B1) composed with the D5 gate (+0.016 OOS) — orthogonal (ensemble moves the prior and leaf
   value, the gate the selector), zero training cost. **Both reviews named it independently.**
3. **Chores owed:** `engine_a1_grade.py` must run `extract_history.py` before the AUC leg;
   8 corrections to the Wang row in `prior_work/README.md`; the engine editable reinstall.

## Watch items
- **SUITE GREEN** 995 (port env) + 143 ppo/priv/episode/harvest; no env runs both (E1).
- **ONE RUNG IS WORTH ±0.02** — three redraws of one checkpoint spread 0.0200, larger than
  the gate's entire out-of-sample effect. Read curves, never one rung.

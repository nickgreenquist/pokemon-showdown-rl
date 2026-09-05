# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 2 of 13 DONE (`JOURNEY.md`: gen1→gen4→gen9)
Step 1 DONE AND CREDITED (batch, RESULTS §17). Step 2 (gen1 ladder #3)
DISCHARGED 2026-09-05 by LADDER R4 — the run itself was the exit condition.
**NEXT IS STEP 3 (gen4 encoder + model), after JOURNEY's "two cheap adds".**

## Where things stand (2026-09-05, early morning) — LADDER R4 COMPLETE, VALID
- **LADDER R4 — COMPLETE AND READ OUT** (readouts/LADDER_R4_READOUT.md;
  RESULTS §16.5; README section). Object: 100M final s112, GREEDY, on R1's
  account REUSED and warm-started (M6). **PRIMARY READ: GXE 65.2%,
  Glicko-1 1618 ± 25, Elo 1354, n=200 this run.** Profile record is the
  CUMULATIVE 199-201 over 400 (R1's 200 + R4's 200); this run's
  runner-logged subset 104-96 = 0.520; reconciled exactly, 0 unlogged.
  Not listed at stop (cutoff 1359.7, 5.7 under). **Listed on the top-500
  for 42/200 battles, 13 excursions, peak 1431 ≈ rank 350 (screenshots
  owed to readouts/ladder_r4_evidence/); 18-24 while listed — reached the
  line, did not hold it.** Licensed cell [1300,1400): 0.423 (n=52, se
  0.069); refs R1 0.319 / R3 0.444, never subtracted. Rule met at rd 25.0;
  attempt 1, 0 relaunches, 0 kills; VOID (a)-(g) clear; NO courtesy note
  (M10). **No cross-run delta is an effect; Elo(R4)-Elo(R1) and "on track
  for top-500" are barred by name.**
- **Record propagation (obligation viii):** 104-96 is quoted ONLY as the
  runner-logged subset, 199-201 ONLY as the cumulative profile record;
  tests/test_ladder_docs.py greps README/STATUS/RESULTS and fails otherwise.
- **E2 exemption LIFTED** (ckpt_100000008.pt was frozen until this readout):
  rung deletion is fully permitted (keep completion + 12M rungs; your call).
- 100M (C1) GRADED P3: off-FP@20 0.49844 vs 0.47456 (+0.02389 < 0.025, NOT
  credited); vs-SH 0.79589; SS-CLIMB. RESULTS §18.
- Audit branch MERGED AND CLOSED (docs/archive/AUDIT_BRANCH_LOG.md). The
  maintainer's other session landed docs/design_gen4/ (encoder requirements,
  anchors, mechanics delta, open_questions with 46 rulings owed, research
  notes), IDEAS_POST_100M round 2, and moved CLEANUP / IDEAS_POST_100M /
  prior_work / research_reports under docs/. CHAPTER5 is archived.

## Next actions — **MAINTAINER, in order**
1. **Read the R4 readout and RESULTS §16.5; rule on anything to change.**
   Nothing is pushed. Bare suite green at this commit.
2. **JOURNEY step 3 (gen4)** — first its "two cheap adds" (the
   most-damage-typed anchor; the search-depreciation check over existing
   12M/50M checkpoints, no training), then the gen4 encoder/model per
   docs/design_gen4/. Each needs its own pre-reg; the 46 open_questions
   rulings come first.
3. Audit rulings owed (AUDIT_BRANCH_LOG §Open questions): F-21, F-04
   routing, F-06/F-07, F-05 cadence, F-03 900 s. Standing rulings (3):
   CLAUDE.md MPS wording; pool.py:88; stall-kill crash_forfeit read rule.
4. Housekeeping: local Showdown server is STOPPED (restart before any local
   eval/test); rung deletion per E2 above.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** — pool 3 seeds; read SHAPE, never rungs.
- **RESUME SPLITS HISTORY** (0 resumes in the 100M fleet; rule stands).
- vs-SH/off-FP are NEVER ladder numbers; FP@20 quotes carry budget + the
  two standing disclosures, forever. Three (off-FP@20, ladder) k=1 pairs
  now exist; fitting or narrating a mapping through them is barred by name.
- **RECONCILE (unchanged):** LADDER R3 STATUS 106-94 (n=200) vs readout
  106-102 (208). foul-play Struggle PANIC open (died once in R4S66).
- Ladder account parked at 199-201 / Elo 1354 (2026-09-05); any future run is a NEW pre-reg.

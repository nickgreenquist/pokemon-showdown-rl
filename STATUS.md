# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
**Step 1 DONE AND CREDITED 2026-08-31.** NEXT IS STEP 2 (ladder), then step 3
(gen4). **Standing maintainer order (2026-08-31, supersedes CHAPTER5 §7
ruling 4): a 100M run, as fast as possible — speedups FIRST, then the run.**
The 100M run is OFF-ARC under that explicit ruling (≈ step 10 pulled forward).

## Where things stand (2026-09-01) — STAGE 2 ACCEPTED; 100M FLEET RUNNING
- **STAGE 2 (async collector) BUILT, LANDED, AND ACCEPTED. G9 PASS** (null
  holds: pooled 0.67211 vs basis 0.64889, signed Δ +0.02322 — 93% of the
  band, positive; rides every future credit sentence). **G8 CREDITED**
  (median sps 901.2/907.6/901.3 vs basis 444, all ≫ 620).
- **HONEST SPEEDUP (realized-vs-realized): 1.53× at fleet width** (574 vs
  375.4 steps/s/lane) · **1.49× solo end-to-end** (bench: collect 45.83→
  28.26 s, update 11.00→9.78 s). 100M = **48.4 h/lane** (was ~74 h).
  NEW LANDMINE-CLASS DISCLOSURE: sps overstates realized ~57% on async
  (18.3% on sync) — wall clocks are realized-only, never the sps estimator.
- **R4S66 COMPLETE, CLEAN (timer fix's first real workload — held):**
  search@20 on batch-lane s66 off-FP **0.38067** vs the lane's greedy
  0.4740 → **search@20 HURTS the batch recipe (~10 se)**. One relaunch =
  foul-play died (seat_frozen_at_kill 0 — §5.3 question not triggered).
- **100M PRE-REG: full 2-Opus cycle done** (brief → memos → synthesis →
  draft → 2 reviews → 12 MUST-FIX + 27 SHOULD-FIX ALL applied → acceptance
  fills complete). `configs/showdown_sp_100m.yaml` **RATIFIED 2026-09-01**; sync
  fallback + grader (selftested) + one-diff tests committed. Review 2
  caught the wave's rung-literal bug BEFORE launch — cycle paid twice.

## Next actions — **MAINTAINER, in order**
1. **100M FLEET RUNNING** (ratified and launched 2026-09-01 ~10:58Z; seeds
   104/112/120). Monitored per HANDOFF; all gates in band at ~24M; realized
   538–563 steps/s → FLEET DONE ETA ~2026-09-03 14:40Z (Thu), then frozen
   eval schedule → grade → record. Peeking bar HOLDS (no evals till done).
   Audit A1 landed (5 design docs tracked in place); A2–A5: CLEANUP.md.
2. **Ladder-object ruling now has R4S66's number**: search@20 hurts the
   batch lane — greedy batch-lane object leads on today's evidence.
3. Standing HANDOFF §5 rulings (4): MPS wording; pool.py:88 fix; stall-kill
   crash_forfeit read rule; RESULTS timer line (pre-drafted in the 100M
   header, discharges with its headline number).

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** — pool 3 seeds; read SHAPE, never rungs.
- **Async fleet health was spotless** (lag exactly ≤1, 0 discards in 1.17M
  episodes, 0 stalls) — but CPU-delta remains the only stall instrument.
- **Gate re-bases forced by the fleet's own values** (R0-7, D-C labelled
  bands): the provisional band would have false-killed s83 — never carry a
  first-250k band onto a full run, and never a sync band onto async unproven.
- **RESUME SPLITS HISTORY** (none occurred this fleet; rule stands).
- **RECONCILE (unchanged):** LADDER R3 STATUS 106-94 (n=200) vs readout
  106-102 (208). foul-play Struggle PANIC open (it died once in R4S66).

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 3 of 13 IN PROGRESS (`JOURNEY.md`: gen1→gen4→gen9)
Step 1 DONE AND CREDITED (batch, RESULTS §17). Step 2 (gen1 ladder #3)
DISCHARGED 2026-09-05 by LADDER R4. **Step 3 (gen4 encoder + model):
GROUNDWORK MERGED 2026-09-05 (branch gen4-build, 17 commits) — encoder
layout v0.1, env, eval bots; NO gen-4 model trained beyond a smoke; step 3
still has no written exit condition (JOURNEY.md:68).**

## Where things stand (2026-09-05, midday)
- **LADDER R4 — COMPLETE AND READ OUT** (readouts/LADDER_R4_READOUT.md;
  RESULTS §16.5; README). GXE 65.2%, Glicko-1 1618 ± 25, Elo 1354, n=200;
  cumulative profile 199-201 over 400; runner subset 104-96. Listed on the
  top-500 for 42/200 battles (peak 1431), not listed at stop (5.7 under).
  **No cross-run delta is an effect; Elo(R4)-Elo(R1) and "on track for
  top-500" are barred by name.** Screenshots owed to readouts/ladder_r4_evidence/.
- **GEN 4 GROUNDWORK (rl/envs/gen4/, docs/design_gen4/):** the five design
  docs verified against 1,650 recorded seat-battles on a local gen4 server
  (replayable tapes, rl/envs/gen4/tape.py); encoder v0.1, OBS_DIM 1,448
  (36 | 61×12 | 31×2 | 71×8 | 44), an EXACT set prior (the vendored
  generator's 600,000 realised sets), forme-keyed vocabs 300/182/101/40,
  12+5 ability/item classes, a per-battle tracker for what poke-env drops
  (weather duration, sleep attempts, items, Encore, Substitute, Choice lock,
  Flash Fire, Wish, the Outrage lock); `ShowdownGen4-v0`; learner smoke
  closes (16 updates, no number). Replay of 42,191 decisions: 0 NaN, in-Box;
  17 offline tests + a committed tape fixture; two Opus reviews folded in
  (SESSION_LOGS 09-05 midday); tapes / FP logs / smoke ckpt under gitignored data/, runs/.
- **Foul Play gen 4 eval bot UP** (Q37): conda env `foul-play-gen4`, pinned
  set file (sha in docs/design_gen4/research/live/fp_gen4_set_pin.json; 40
  species drift ±1–2 levels — disclosed with every quote). vs SH n=250:
  FP@20 226-24-0, FP@500 228-22-0, clean logs. Descriptive only, budget named.
- most-damage-typed anchor BUILT (gen 1 sanity 0.983/0.777/0.330 vs
  random/MBP/SH, n=300) — joins the battery only on your say-so. Search-
  depreciation check ASSEMBLED (docs/proposals/). 100M (C1) graded P3 (RESULTS §18).

## Next actions — **MAINTAINER, in order**
1. **Read the R4 readout / RESULTS §16.5 and the gen-4 review entry; rule on
   anything to change.** Nothing is pushed. Suite: 794 passed, 4 failed =
   gitignored artifacts absent locally (results/ch4_r1_offsh, runs/ rungs).
2. **Gen-4 build items needing a ruling before they run** (encoder_requirements
   §13): the entity trunk's layout argument (rl/networks/entity_deepsets.py is
   gen-1-bound); the pinned gen-4 hash gate + the pre-reg that FREEZES layout
   v0.1 (and decides the ~90 dims unreachable at this pool); the FP budget
   ladder against a REAL gen-4 agent (Q38); step 3's exit condition. The 46
   design rulings are indexed in docs/design_gen4/open_questions.md.
3. Rulings owed, yours: search-depreciation rule; audit F-21, F-04 routing,
   F-06/F-07, F-05 cadence, F-03 900 s; stall-kill crash_forfeit READ rule.
4. Housekeeping: Showdown server UP (pid 50440, port 8000); rung deletion per E2; the gen4-build worktree can go when done.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (pool 3 seeds; read SHAPE); **RESUME SPLITS HISTORY**.
- vs-SH/off-FP are NEVER ladder numbers; FP@<ms> quotes carry budget + the two
  standing disclosures, forever (gen 4 adds the level-drift caveat). Three
  (off-FP@20, ladder) k=1 pairs exist; fitting a mapping through them is barred.
- foul-play Struggle PANIC: symptom chain + `/timer on` rule stand; the MECHANISM
  was corrected 2026-09-05 (landmines.md); 0 hits in 525 gen-4 FP battles.
- Ladder account parked at 199-201 / Elo 1354 (2026-09-05); any future run is a NEW pre-reg.
- Every gen-4 number so far is a smoke or bot-vs-bot placement; none is a claim.

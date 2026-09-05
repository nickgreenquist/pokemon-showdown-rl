# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 3 of 13 IN PROGRESS (`JOURNEY.md`: gen1→gen4→gen9)
Steps 1–2 DONE (batch credited, RESULTS §17; LADDER R4 discharged step 2).
**Step 3 (gen4 encoder + model): groundwork MERGED 2026-09-05; exit condition
RULED 2026-09-05 (JOURNEY step 3): a PURE self-play gen4 agent on the frozen
layout v0.1 scores ≥ 0.60 vs SH under the locked protocol (pooled 3×3000),
three descriptive anchors reported. No gen4 model trained beyond a smoke.**

## Where things stand (2026-09-05, midday)
- **LADDER R4 — COMPLETE AND READ OUT** (readouts/LADDER_R4_READOUT.md;
  RESULTS §16.5; README). GXE 65.2%, Glicko-1 1618 ± 25, Elo 1354, n=200;
  cumulative profile 199-201 over 400; on the top-500 for 42/200 battles (peak
  1431), not listed at stop. **No cross-run delta is an effect; Elo(R4)-Elo(R1)
  and "on track for top-500" are barred by name.** Screenshots owed to
  readouts/ladder_r4_evidence/. 100M (C1) graded P3 (RESULTS §18).
- **GEN 4 GROUNDWORK (rl/envs/gen4/, docs/design_gen4/):** design docs verified
  against 1,650 recorded seat-battles (replayable tapes); encoder v0.1, OBS_DIM
  1,448 (36 | 61×12 | 31×2 | 71×8 | 44), EXACT set prior (600,000 realised sets),
  vocabs 300/182/101/40, 12+5 classes, tracker for what poke-env drops;
  `ShowdownGen4-v0`; learner smoke closes. Replay of 42,191 decisions: 0 NaN,
  in-Box, sha bbcf9f60…; 17 offline tests + committed fixture; two Opus reviews
  folded in. Tapes / FP logs / smoke ckpt: gitignored data/, runs/ (also in
  ../pokemon-showdown-rl-gen4).
- **Foul Play gen4 eval bot UP** (env `foul-play-gen4`, pinned set file; 40 species
  drift ±1–2 levels, disclosed). vs SH n=250: FP@20 226-24-0, FP@500 228-22-0. Descriptive.
- most-damage-typed anchor BUILT (gen1 sanity 0.983/0.777/0.330, n=300) and
  RULED INTO THE BATTERY (gen4 on). Search-depreciation check ASSEMBLED
  (docs/proposals/), rule awaiting ratification.

## Next actions — THE RULED GEN-4 ORDER (maintainer 2026-09-05; verbatim: SESSION_LOGS midday, open_questions.md §0.5)
1. **Pre-reg header that FREEZES layout v0.1 as built, unreachable dims KEPT.**
   Draft `configs/gen4_sp50m.yaml` from `configs/showdown_sp_batch50m.yaml`
   (journey_step 3, exit condition verbatim, credit line verbatim, arms, R0
   gates, anchors) — pre-reg-grade: 2-Opus design review BEFORE it is committed.
2. **Pinned gen4 hash gate** (mechanical: fixture + local tapes, mirror
   tests/test_encoder_spec.py; reference sha bbcf9f60… in encoder_requirements §13).
3. **Entity trunk layout argument** — `rl/networks/entity_deepsets.py` takes a
   layout object + item/ability id embeddings; gen1 bit-identity tests guard it.
4. **50M pure self-play run** on the frozen layout (the header from item 1);
   > 5 h → HAND-OVER launch (rule 4); nothing larger until it reads out.
5. **FP budget (Q38):** two-rung ladder (20/500 ms, n ≥ 250) ONCE against the
   item-4 checkpoint, then pin; quote both budgets meanwhile.
6. Rulings still yours: search-depreciation rule; audit F-21, F-04 routing,
   F-06/F-07, F-05 cadence, F-03 900 s; stall-kill crash_forfeit READ rule; the
   remaining design Q-items (open_questions.md; most ride the item-1 header).
7. Housekeeping: Showdown server UP (pid 50440, 8000); rung deletion per E2;
   the gen4-build worktree can go when done. Nothing is pushed.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (pool 3 seeds; read SHAPE); **RESUME SPLITS HISTORY**.
- vs-SH/off-FP are NEVER ladder numbers; FP quotes carry budget + the two
  standing disclosures, forever (gen4 adds the level-drift caveat). Fitting a
  mapping through the three (off-FP@20, ladder) k=1 pairs is barred by name.
- foul-play Struggle PANIC: symptom chain + `/timer on` rule stand; mechanism
  corrected 2026-09-05 (landmines.md); 0 hits in 525 gen4 FP battles.
- Ladder account parked at 199-201 / Elo 1354; any future run is a NEW pre-reg.
- Every gen4 number so far is a smoke or bot-vs-bot placement; none is a claim.

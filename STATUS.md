# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 3 of 13 IN PROGRESS (`JOURNEY.md`: gen1→gen4→gen9)
Steps 1–2 DONE (batch credited, RESULTS §17; LADDER R4 discharged step 2).
**Step 3 (gen4 encoder + model): groundwork MERGED and REVIEWED 2026-09-05.
FIRST RUN = WANG'S RECIPE on our encoder (step 4, ruled); step-3 milestone =
it learns (≥ 0.60 vs SH, locked protocol); the CHAPTER's exit is step 5:
pooled 3×3000 vs-SH ≥ 0.756, ONE-SIDED (0.786 − 1 se of his n=200; ruled
2026-09-05 evening, Option A). No gen4 model trained yet.**

## Where things stand (2026-09-05, evening)
- **LADDER R4 — COMPLETE AND READ OUT** (readouts/LADDER_R4_READOUT.md;
  RESULTS §16.5; README). GXE 65.2%, Glicko-1 1618 ± 25, Elo 1354, n=200;
  cumulative profile 199-201 over 400; on the top-500 for 42/200 battles (peak
  1431), not listed at stop. **No cross-run delta is an effect; Elo(R4)-Elo(R1)
  and "on track for top-500" are barred by name.** Screenshots owed to
  readouts/ladder_r4_evidence/. 100M (C1) graded P3 (RESULTS §18).
- **GEN 4 GROUNDWORK (rl/envs/gen4/, docs/design_gen4/):** encoder v0.1, OBS_DIM
  1,448 (36 | 6×61 + 6×62 | 31×2 | 71×8 | 44), EXACT set prior (600,000 realised
  sets), vocabs 300/182/101/40, tracker, `ShowdownGen4-v0`; 42,191-decision
  replay 0 NaN in-Box, **sha b72dcbc7…** (scripts/gen4_reference_replay.py);
  25 tests + fixture. **POST-MERGE REVIEW DONE (3 Opus reviewers, 2026-09-05
  evening): 1 BLOCKER + 4 MAJORS in the encoder FIXED on main** — ability holder
  via `[of]` (false immunities), Hidden Power variant probability, stat-Curse,
  Castform/Cherrim formes in the prior, Wish/multi-hit; ops hardened (tapes
  stream to disk, FP process-group reaping, progress lines, setup-script
  flags + .so check); async collector REFUSES gen4 env ids. §13 has the list.
- **Foul Play gen4 eval bot UP** (env `foul-play-gen4`, pinned set file; 40 species
  drift ±1–2 levels). vs SH n=250: FP@20 226-24-0, FP@500 228-22-0 — bot-vs-bot,
  descriptive; every FP@20 quote carries the two standing disclosures.
- most-damage-typed anchor BUILT (gen1 sanity 0.983/0.777/0.330, n=300), IN THE
  BATTERY from gen 4 on. Search-depreciation check ASSEMBLED (docs/proposals/), unratified.

## Next actions — THE RULED GEN-4 ORDER (maintainer 2026-09-05; open_questions.md §0.5)
1. **Pre-reg header for the WANG-RECIPE run (it also FREEZES layout v0.1 as
   built, unreachable dims KEPT):** `configs/gen4_wang50m.yaml` — his Table A.3
   + LR schedule, mirror self-play latest-vs-latest, both seats, NO pool; step-5
   target 0.786, matched = pooled 3×3000 ≥ 0.756 one-sided; SB3 + scale (50M vs
   ≈75M) disclosures; the failure branch names DOSE; R0 gates; anchors.
   2-Opus design review BEFORE commit.
2. **Pinned gen4 hash gate** (mechanical: fixture + local tapes, mirror
   tests/test_encoder_spec.py; reference sha b72dcbc7… in encoder_requirements §13).
3. **Entity trunk layout argument** — `rl/networks/entity_deepsets.py` takes a
   layout object + item/ability id embeddings; gen1 bit-identity tests guard it.
4. **The 50M Wang-recipe run** (item 1's header); > 5 h → HAND-OVER launch;
   nothing larger until it reads out. AFTER it: our gen1 machinery as LEVERS
   (pool / league first, then batch config, privileged critic), each its own pre-reg.
5. **FP budget (Q38):** two-rung ladder (20/500 ms, n ≥ 250) ONCE against the
   item-4 checkpoint, then pin; quote both budgets meanwhile.
6. Rulings still yours: the BC-clone leg for the first gen4 readout (JOURNEY's
   milestone lists MDT + FP@20 + FP@500; CLAUDE.md's battery names BC-clone —
   anchors §10 item 6); search-depreciation rule; audit F-21/F-04/F-06/F-07/
   F-05/F-03; stall-kill crash_forfeit READ rule; remaining Q-items.
7. Housekeeping: Showdown server UP (pid 50440); rung deletion per E2; the
   gen4-build + pkmn-plan worktrees can go when done. Not pushed since 69c5fbe.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (pool 3 seeds; read SHAPE); **RESUME SPLITS HISTORY**.
- vs-SH/off-FP are NEVER ladder numbers; FP quotes carry budget + the two standing
  disclosures (gen4 adds level drift). No (proxy, ladder) mapping — barred by name.
- foul-play Struggle PANIC: `/timer on` rule stands; 0 hits in 527 gen4 FP battles.
- `mix:` opponents are deliberately NOT reseeded by ShowdownEnv.reset (historical
  configs); a most_damage_typed env opponent now IS (no committed config uses one).
- Every gen4 number so far is a smoke or bot-vs-bot placement; none is a claim.

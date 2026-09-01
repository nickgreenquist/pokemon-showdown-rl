# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever (R2) — DONE AND CREDITED 2026-08-31.**
NEXT IS STEP 2 (ladder), then step 3 (gen4). **Standing maintainer order
(2026-08-31, supersedes CHAPTER5 §7 ruling 4): a 100M run, as fast as
possible — speedups FIRST, then the run.** Stage 1+2 serve that order.

## Where things stand (2026-09-01, overnight session)
Cell **P1** credited (R2): off-FP@20 greedy delta **+0.13722** vs bar 0.07181;
vs-SH 0.78644. Attestation 3a31755. Prior results: RESULTS §15/§16; LADDER R1
GXE 59.6%, R3 60.3% standalone. Ladders credit nothing.

## This session (2026-09-01) — STAGE 2 BUILT AND LANDED; fleet queued
- **STAGE 2 (async collector) BUILT, GREEN, SMOKE-VERIFIED LIVE** (ca37aa7 →
  e6630f3): episode buffer + per-episode GAE, old_logp AT ACT TIME, factored
  `_optimize`, per-tag member maps (G6a), (turn,idx) label join, collector on
  the MEASURED E4b shape (one pair, K=8, batch-1 on POKE_LOOP — spec's drain
  seam deliberately not built; disclosed). Suite 643 passed / 17 skipped.
  Smokes: G5 lag p99=1, clip_frac 0.04-0.09, aux hard gates 0/0, 0 discards;
  SIGKILL + `--resume` verified. One real bug found+fixed: trailing 1-row
  minibatch NaN (15719d9).
- **G9 RE-BASED: pooled basis 0.64889** (s66 .62900/.s75 .65700/s83 .66067,
  n=3000 locked, seed sd 0.0173). 0.3890 retired. **G8 RE-BASED: control's
  own 3-wide median 444 steps/s** → credited ≥620 / short 500-620 / stop <500.
- **QUEUED DETACHED: `scripts/ch5_g9_wave.sh`** — waits for R4S66's box, runs
  the solo on/off bench, then 3 async lanes (seeds 66/75/83, killed at the
  12M rung), then locked evals + pooled G9 + per-lane G8 into
  `logs/ch5_g9_wave.log`. Pre-reg: `configs/showdown_sp_batch50m_async.yaml`.
- **R4S66 ran clean beside the build** (timer fix's first real workload):
  934/3000 at 02:28Z, orphans steady at 1, ~3.1 s/battle. Grade on finish.

## Next actions
1. Read `logs/ch5_g9_wave.log`: bench Δ vs runs/ch5_stage1_after; G8 medians;
   G9 pooled vs 0.64889 (|Δ|<0.025 = PASS). FAIL → no 100M on async; bisect
   per the pre-reg header.
2. Grade R4S66 (`scripts/ch5_r2_grade.py`); check `seat_frozen_at_kill`.
3. 100M pre-reg (credit-seeking, full 2-Opus cycle, HANDOFF §2 requirements;
   launch is the maintainer's). Draft may exist by morning — check
   SESSION_LOGS tail.
4. Maintainer rulings owed: HANDOFF §5 (4 items, unchanged).

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02, NOT ±0.008** — pool 3 seeds; read SHAPE.
- **LANE STALLS**: CPU-time deltas remain the only instrument; the wave
  auto-resumes at 3 consecutive zero-deltas (bounded, 3 retries).
- **RESUME SPLITS HISTORY**: any auto-resumed async lane's G8 median needs
  the merge protocol before quoting; `extract_history` hard-fails on splits.
- **foul-play PANICs on Struggle** — unchanged. **RECONCILE** (unchanged):
  LADDER R3 STATUS 106-94 (n=200) vs readout 106-102 (208).
- Async path refuses privileged/shaping/normalizers loudly — sync path is
  bit-identical for every existing config (empty `collector:` block).

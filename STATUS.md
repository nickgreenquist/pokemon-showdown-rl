# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever (R2) — DONE AND CREDITED 2026-08-31.**
NEXT IS STEP 2 (ladder), then step 3 (gen4). SCOPE GUARD: a read inside the
bar informs the INSTRUMENT; it does not licence another gen1 lever.

## Where things stand (2026-08-31) — **R2 COMPLETE, GRADED, CREDITED.**
Cell **P1**: off-FP@20 greedy delta **+0.13722** vs bar **0.07181** (se_gov
0.03591 clustered, the larger-of). Treatment 0.4740/0.4827/0.4670 (mean
0.47456, s_T 0.00785) vs control 0.3960/0.3430/0.2730 (0.33733, sd 0.0617).
Secondary vs-SH mean **0.78644** vs 0.70222 → delta +0.08422 vs bar 0.07316 →
**X1, credit stands**; F1 does not fire. All gates green; attestation
**3a31755**. **Pre-stated ~6.5% to credit (E1); it credited — treat the
surprise with MORE scrutiny.** Detail: SESSION_LOGS 08-31.

## Prior results (detail RESULTS §15/§16)
12M 0.71825 · ensemble 0.74633 · search@M 0.79283 · **LADDER R1 (ensemble) GXE
59.6%** · **LADDER R3 (search@M, s80) GXE 60.3% — STANDALONE, no R1-vs-R3 delta
(D5)**, both n=200. Ties=loss. **Ladders credit nothing; vs-SH/off-FP are
NEVER ladder numbers.**

## Next actions — RULING 2026-08-31: 2a/2b are **IN-ARC** step-1 work
(choosing the object to ladder R3 with), NOT off-arc gen1 levers.
1. **RUNNING: R4S66 rerun** on the flipped pair (956b909, licensed edit ii;
   a-pair burned). ~19:50 EDT. NOTHING runs beside it — stolen CPU inflates
   FP's budget = wave-scoped VOID.
2. **QUEUED, start when the wave clears** (rationale: SESSION_LOGS 08-31).
   **(a) SCALE SHAPE:** D29r2's R-B FLAT tested the OLD recipe; the BATCH
   recipe's scaling is **UNMEASURED**. E3 kept all 69 rungs/lane — eval
   20/30/40/50M of one R2 lane vs SH, read whether the curve still climbs.
   Minutes, not 70 h. DESCRIPTIVE, no bar, no credit. **(b) MPS BENCHMARK:**
   "MPS is flaky here" is **NEVER MEASURED** — no log entry, benchmark, or
   landmine narrative. Measure `time/update_sec` at REAL width/batch (never
   `showdown_throughput.py`); collection is Node-bound and cannot benefit.
3. **THEN step 2 (ladder).** Candidates pre-named in R2 Q7; R3 chooses under
   its OWN pre-reg, incumbent-wins-ties — **R2's primary DOES NOT SELECT the
   ladder object.** Best greedy object now: s75 (off-FP 0.4827).
4. Riders R3c/R1i/R1ii NOT RUN — need `scripts/ch5_r2_crossplay.py`, unbuilt;
   this also BLOCKS the README row (anchor battery's BC-clone half). RESULTS
   §17 + §15 row landed; CHAPTER5.md archivable; residue `CLEANUP.md`.

## Watch items
- **NEW, reproducible: LANES STALL** (s66 @68.9%, s75 @94.3%) — process ALIVE,
  **zero CPU**, stale logs, RSS bleeding out. Liveness does NOT catch it;
  **sample CPU-time deltas**. Losses 190,776/170,680 steps (NOT ≤30,720 —
  `checkpoint.pt` lags the last logged step by >1 update).
- **RESUME SPLITS HISTORY:** two wandb runs, OVERLAPPING steps;
  `extract_history.py <run_dir>` HARD-FAILS on s66/s75 — use
  `history_merged.csv`. Verdict path never reads history.
- **D-E BREACH DISCLOSED:** resumed s75 alone peaked **5.87 GB** vs a 4.5 GB
  STOP line calibrated 3-wide. Ruled continue (box 85% free, swap FELL).
- **D-D passed but LOW:** 0.8584/0.8422/0.8607 — over the 0.75 floor, BELOW
  the pre-stated 0.90–0.96, far below control's ~0.971.
- **s_T 0.0078 vs 0.0617 is NOT a variance result** — (2,2) df, crit 19.0.
- **foul-play PANICs** → tie-crash wedge; a killed pair stays poisoned for
  hours — re-run LAST on the rerun pair.
- **RECONCILE:** LADDER R3 record — STATUS said 106-94 (n=200), committed readout says 106-102 (208).

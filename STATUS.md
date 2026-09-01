# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever (R2) — DONE AND CREDITED 2026-08-31.**
NEXT IS STEP 2 (ladder), then step 3 (gen4). SCOPE GUARD: a read inside the
bar informs the INSTRUMENT; it does not licence another gen1 lever.

## Where things stand (2026-08-31) — **R2 COMPLETE, GRADED, CREDITED.**
Cell **P1**: off-FP@20 greedy delta **+0.13722** vs bar **0.07181** (se_gov
0.03591 clustered, the larger-of); treatment 0.47456 (s_T 0.00785) vs control
0.33733 (sd 0.0617). Secondary vs-SH 0.78644 vs 0.70222 → **X1, credit
stands**. Gates green; attestation **3a31755**. Detail: SESSION_LOGS 08-31.

## Prior results (detail RESULTS §15/§16)
12M 0.71825 · ensemble 0.74633 · search@M 0.79283 · **LADDER R1 GXE 59.6%**,
**R3 (search@M, s80) GXE 60.3% — STANDALONE, no R1-vs-R3 delta (D5)**, n=200,
ties=loss. **Ladders credit nothing; vs-SH/off-FP are NEVER ladder numbers.**

## Closed this session (HANDOFF items 1–4, all four done)
1. **THE ORPHANED-ROOM DEADLOCK IS FIXED** (`9a0e54d`) — maintainer ruled *ship
   everywhere, disclose*. `start_timer_on_battle_start=True` on every connecting
   seat + h2h `max_concurrent_battles` 2→8; ladder stays at 2 (rated). Verified
   LIVE: an orphan **RESOLVED in 300.0 s returning its slot** vs **open at the
   420 s cap holding 1/1** before. Runner also fixed (`fc3066d`).
2. **SCALE-SHAPE (descriptive, s83 only, 10 rungs × n=3000):** .6657 (5M) →
   .7647 (50M); 5M→45M **+0.105**, **40M→50M +0.0010 (0.1 se)** — plateau vs
   noise is unsettleable at one seed; see the noise floor below.
3. **MPS MEASURED:** it **CRASHES** (`rl/selfplay/pool.py:88`, CPU generator vs
   MPS probs — every self-play lane). Priced on the learner anyway: cpu@1
   12.002s · mps 10.449s (1.15×) · cpu@6 14.195s (0.85×) → **~2.5% end to end**;
   numerics agree (argmax 512/512, `-1e8` sentinel intact).

## Next actions — **`HANDOFF.md` IS NON-EMPTY. READ IT.**
**GOAL (maintainer, 2026-08-31): a 100M run, as fast as possible. Build the
speedups FIRST, then run it.** CHAPTER5 §7 ruling 4 is SUPERSEDED — say so in
the 100M header. MPS is dead (measured; crashes; ~2.5%). Do not relitigate.
- **RUNNING NOW: R4S66**, launched 01:40:48Z from clean `ce4c38e`, 3.21
  s/battle measured, ETA ~04:00-04:30Z. First real workload for the timer fix.
- **STAGE 1 SHIPPED (`ce4c38e`): +8.1% end to end**, collect 50.547 -> 45.827.
  72 h -> 66.2 h at 100M.
- **STAGE 2 (async collector) is the job.** Honest gain on the CURRENT recipe
  is **~1.55x**, not the spec's 2.6x — the batch lever tripled the update
  share (5.2% -> 19.4%). **Re-base G8 and G9 BEFORE writing code**; G9's
  control side is already on disk (all three lanes' clean 12M rungs).
- RULINGS OWED (4) and the 100M pre-reg's requirements: HANDOFF §5 and §2.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02, NOT ±0.008** — three re-draws of ONE 50M
  checkpoint gave 0.76467/0.78467/0.78333. Read SHAPE, never rung vs neighbour.
- **LANE STALLS** (s66 @68.9%, s75 @94.3%): root cause fixed, but **CPU-time
  deltas remain the only instrument** — `pgrep` never catches this shape. The
  LADDER is the timer's tight path (150 s/turn, not a challenge's 300).
- **RESUME SPLITS HISTORY:** `extract_history.py` HARD-FAILS on s66/s75 — use
  `history_merged.csv`. **D-D passed but LOW** (0.8584/0.8422/0.8607), and
  **s_T 0.0078 vs 0.0617 is NOT a variance result**.
- **foul-play PANICs on Struggle** — open whether the FP anchor runs at n=3000
  for SEARCH seats; the timer bounds it, it is not a cure. **RECONCILE:** LADDER
  R3 — STATUS said 106-94 (n=200), readout says 106-102 (208).

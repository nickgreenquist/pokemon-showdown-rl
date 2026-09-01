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

## Next actions — **`HANDOFF.md` is EMPTY; no handoff pending.**
- **RULINGS OWED (3):** (a) CLAUDE.md's MPS wording — proposal: keep CPU-only,
  replace "flaky" with the measured reason (**not edited; yours**); (b) fix
  `pool.py:88` at all, given the 2.5% prize?; (c) may a stall-kill that
  forfeited no battle keep counting as a `crash_forfeit` (a READ-RULE question
  against a frozen pre-reg)?
- **RESULTS disclosure line OWED** with the next headline number — the wire
  differs from every pre-2026-08-31 arm's. **R4S66 re-run now unblocked**
  (~2.4 h, `ARMS="R4S66" bash scripts/ch5_r2_wave.sh`): optional, routes nothing.
- **`ch5_r2_crossplay.py` STILL UNBUILT** — blocks riders R3c/R1i/R1ii and the
  README row. A 100M run stays credit-seeking: own pre-reg, 2-Opus cycle.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02, NOT ±0.008** — three re-draws of the SAME
  50M checkpoint gave 0.76467 / 0.78467 / 0.78333 (spread 0.0200 vs binomial
  se 0.0077). Read curve SHAPE, never one rung against its neighbour.
- **LANE STALLS** (s66 @68.9%, s75 @94.3%): root cause fixed, but **CPU-time
  deltas remain the only instrument** — `pgrep` never catches this shape. The
  LADDER is the timer's tight path (150 s/turn, not a challenge's 300).
- **RESUME SPLITS HISTORY:** `extract_history.py` HARD-FAILS on s66/s75 — use
  `history_merged.csv`. **D-D passed but LOW** (0.8584/0.8422/0.8607: over the
  0.75 floor, under the pre-stated 0.90–0.96), and **s_T 0.0078 vs 0.0617 is
  NOT a variance result**.
- **foul-play PANICs on Struggle** — open whether the FP anchor runs at n=3000
  for SEARCH seats; the timer bounds it, it is not a cure. **RECONCILE:** LADDER
  R3 — STATUS said 106-94 (n=200), readout says 106-102 (208).

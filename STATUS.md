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

## Next actions — SEE `HANDOFF.md` (non-empty; fresh session, Opus/high).
RULING: items 2/3 are **IN-ARC** step-1 work (choosing the ladder object).
1. **R4S66 FAILED TWICE, NOT GRADED.** Attempt 2 (flipped pair) aborted
   `.NO_PROGRESS` rc=4 at 1,536/3,000. Root cause found — the ORPHANED-ROOM
   DEADLOCK (`docs/landmines.md`), very likely the SAME bug as the s66/s75
   training stalls. Verdict re-graded WITH both sentinels: **unchanged, P1.**
2. **THE TIMER FIX, first and highest value.**
   `start_timer_on_battle_start=True` — the only fix available to the training
   env (`max_concurrent_battles=1` is a hardcoded literal there). **RULING
   OWED: it is a WIRE-VISIBLE protocol change**; comparability vs banked arms
   is the maintainer's call. Then R4S66 re-run is optional (routes nothing).
3. **SCALE-SHAPE READ** on **s83's rungs only** (s66/s75 have resume seams).
   Descriptive; STOP at "read the curve". A 100M run is credit-seeking and
   needs its OWN pre-reg via the 2-Opus cycle — not a session task.
4. **MPS BENCHMARK** — never measured anywhere. Report and PROPOSE only; the
   maintainer rules on the CLAUDE.md:71 change.
5. Riders R3c/R1i/R1ii NOT RUN — need `scripts/ch5_r2_crossplay.py`, unbuilt;
   also BLOCKS the README row. RESULTS §17 + §15 row landed.

## Watch items
- **LANES STALL** (s66 @68.9%, s75 @94.3%) — process ALIVE, **zero CPU**,
  stale logs. `pgrep` NEVER catches it; **sample CPU-time deltas**. Losses
  190,776/170,680 steps (NOT ≤30,720 — `checkpoint.pt` lags by >1 update).
  **ROOT CAUSE: the ORPHANED-ROOM DEADLOCK** (`docs/landmines.md`) — turn-1000
  auto-tie → Struggle → foul-play panic → a room that never resolves (no
  `/timer on`) → poke-env's queue fills → next battle blocks forever. Killed
  R4S66 twice AND is very likely the training stall. Probabilistic, not
  deterministic: s83 hit turn 1000 **482×** (most of any lane) and never hung.
- **RESUME SPLITS HISTORY:** `extract_history.py <run_dir>` HARD-FAILS on
  s66/s75 (two overlapping wandb runs) — use `history_merged.csv`.
- **D-E BREACH DISCLOSED:** resumed s75 alone peaked **5.87 GB** vs a 4.5 GB
  STOP calibrated 3-wide. Ruled continue (box 85% free, swap FELL).
- **D-D passed but LOW:** 0.8584/0.8422/0.8607 — over the 0.75 floor, BELOW the pre-stated 0.90–0.96.
- **s_T 0.0078 vs 0.0617 is NOT a variance result** — (2,2) df, crit 19.0.
- **foul-play PANICs on Struggle** — open question whether the FP anchor is runnable at all for search seats.
- **RECONCILE:** LADDER R3 — STATUS said 106-94 (n=200), readout says 106-102 (208).

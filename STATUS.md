# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-27 — **CH5 R1 IS COMPLETE: 9 arms, ZERO VOIDS,
G2 exact on every one. R1 PRODUCED AN R3 DEPLOYMENT CANDIDATE WITH ZERO
TRAINING.** One job still running: `RS80`, the mandatory fresh re-score.
**HANDOFF.md IS NON-EMPTY — read it first.**) **Pure from-scratch self-play;
THE NOVELTY IS THE LANE.** CH3 + CH4-R1 CLOSED.

## Results | D26 12M **0.71825** vs SH · R0 ensemble 0.74633 · R2 search@M
0.79283 · **LADDER R1: GXE 59.6%, Glicko-1 1573+/-27, Elo 1292, n=200** ·
**R1 off FP@20 — greedy s80/s81/s82 0.3960/0.3430/0.2730 · search@M
0.4470/0.4470/0.4210 · C0(L2) 0.3893 · CE3 0.3623 · CE7 0.3827.**
Ties=loss; locked = final ckpt. **R1 CREDITS NOTHING; headlines UNTOUCHED.**

## R1's three answers, graded by the pre-reg's own rules
- **R1-A PRIMARY: s82's collapse REPRODUCES off-FP.** +0.0965 vs bar 0.0369
  = **5.2 se**. A genuinely bad seed, not an SH artifact.
- **R1-A FLEET: WITHIN x NON-RESOLVING.** −0.0113 vs a REALIZED BAR of
  **0.0717** (s_50 off-FP 0.0617 ~ its vs-SH 0.0629, so clustered governs).
  **The O-4 cliff predicted this before any datum.** Action taken verbatim:
  stop buying battles; buy LANES or drop the scale question. **"flat" BARRED.**
- **R1-B: SEARCH HELPS.** within-lane mean **+0.1010**, bar 0.0561, 3.6 se.
  **Helps MOST on the WORST lane** (s82 +0.148 vs s80 +0.051). **CEILING:
  licenses search as an R3 DEPLOYMENT CANDIDATE ONLY; does NOT reverse MU-8
  (z=−2.80); never set beside the 12M cell.**
- **R1-C: NOT DELIVERED.** E3 0.3623 BELOW C0; E7 0.3827 WITHIN. L2 holds as
  ensemble incumbent. The pre-registered soft-AND mechanism explains it.
- **C0 = the repo's FIRST complete (proxy, ladder) pair.**

## Next actions — **PLAN RATIFIED 2026-08-27; R3 THEN R2, BOTH HAPPEN**
1. **FINISH `RS80`** (search@M on s80, n=3000). The 0.4470 is a SELECTION
   score and **MAY NOT BE PUBLISHED** (Q6). Grade with
   `python scripts/ch5_r1_grade.py`. See HANDOFF.md §1.
2. **R3 — LADDER #2 NOW**, ~200 battles, one night, **FRESH ACCOUNT** (reusing
   `nickgen1rbrlbot` contaminates the rating with L2's history). Readout must
   say top-500 needs Elo 1357 vs our implied true ~1232: **R3 MEASURES, it is
   not an attempt on the list.**
3. **R2 — RETRAIN IS COMMITTED, NOT OPTIONAL.** Batch lever (~1,000
   episodes/update, 3 lanes, banked fleet as free control, ~37 h). **Ruling
   owed:** the branch table routes to C2 (more seeds, first-class); batch is
   §3b A4 and cannot displace a C-item without your call. HANDOFF.md §5.
4. `CLEANUP.md` rulings. **main is UNPUSHED — ask before pushing.**

## Watch items
- **NEVER re-run a killed arm IMMEDIATELY** — its Showdown room stays poisoned
  for hours (`KeyError: 'battle\n'`). Restart the server to clear rooms fast.
- **DO NOT edit the pre-reg, `ch3_r4_fp_runner.sh` or `ch3_fp_h2h.py` while a
  wave runs** — runner and seat are invoked FRESH PER ARM.
- **r7/r8 amended a RATIFIED pre-reg** (dose M; the RS80 arm), disclosed in its
  banner. `prereg_sha256` differs across arms: `80245bbd` -> r7 -> r8.
- **SEARCH PLAYS 32-47% LONGER BATTLES** (36.8-40.3 turns vs 25-28). That is
  why only search arms hit the turn-1000 auto-tie, and it is a style/cost fact
  for the readout.
- **"NOT LISTED" NEVER MEANT "NO RATING"** — the profile carries GXE/Glicko for
  any rated account. `L2.battles.jsonl.rating` is PRE-BATTLE; final Elo 1292.
- **TOP-500 IS ~125 ELO AWAY, NOT 65** — we score 0.340 vs the 1300-1400 band.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED** (3 copies via
  `scripts/backup_ladder.sh`). **FP stdout IS G2's second tally.**

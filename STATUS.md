# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
Step 1 DONE AND CREDITED. The 2026-08-31 off-arc order (100M run) is
**DISCHARGED** — run done, graded, readout committed 2026-09-04.
**NEXT IS STEP 2 (ladder) — every cell of the 100M table routes there.**

## Where things stand (2026-09-04) — 100M GRADED: P3, NON-RESOLVING
- **100M (C1) COMPLETE AND GRADED — CELL P3.** Primary off-FP@20 greedy
  pooled **0.49844** vs control 0.47456: **delta +0.02389 vs floor 0.025**
  (se_gov clustered 0.00774; NOT credited; A-COLL void). vs-SH secondary
  pooled **0.79589** (+0.00944, SN-N descriptive). BC-clone 0.9233.
  **S-SHAPE: SS-CLIMB** — still climbing at 100M (+0.029, 4.6× threshold;
  sub-100M rungs are on the 100M anneal — never compare to finished runs).
  Fleet ops spotless: 0 stalls/resumes, 562.8/558.2/557.5 steps/s realized,
  D-A 12/12, R0-f all bands. Full account: RESULTS.md §18; README row
  landed (full anchor battery). N-TIMER RESULTS line DISCHARGED.
- **E2 rung retention DISCHARGED** — S-SHAPE/S-ANNEAL/D-A recorded and
  committed; deleting the ~600 treatment + 300 control rungs is now
  permitted (keep completion + 12M rungs; maintainer call).
- **`audit-fixes` MERGED 2026-09-04 (ff, main @ bd8484d, 46 commits).**
  Landed F-01/02/03/04/05/08/09/10/13/14/16/18/19 + branch-discovered F-21
  (encoder set prior was untracked) and F-22; F-04 pre-reg, F-06, F-07 are
  PROPOSALS under docs/proposals/ (unruled). Suite in main 785 passed /
  17 skipped (live tests incl.). Record: docs/archive/AUDIT_BRANCH_LOG.md
  (CLOSED). `gen4-design` (docs only) still awaits review/merge.

## Next actions — **MAINTAINER, in order**
1. **Merge gen4-design docs** (maintainer's own task); fold its log into
   SESSION_LOGS at merge. Audit rulings now owed (AUDIT_BRANCH_LOG §Open
   questions): F-21 keep the borrowed set prior tracked?; F-04 fold/drop/
   neither + routing; F-06/F-07 options; F-05 cadence (4 updates); F-03 900 s.
2. **LADDER R4 — RATIFIED 2026-09-04, LAUNCH HELD until gen4-design lands**
   (maintainer-ordered). Object: 100M final s112, GREEDY, account
   nickgen1rbrlbot REUSED (M6, maintainer-ruled — multi-account rules).
   Pre-launch acts when unheld, in order: send the courtesy note (≥24 h
   ahead; drafted at readouts/LADDER_R4_COURTESY_NOTE.md), update .env
   (bot1 username AND password), LG-2 parked-profile capture, LG-4..7
   gates, then launch (~90 s at the terminal; agent babysits). Plan
   12-16 h overnight. Pre-reg: configs/eval/ladder_r4.yaml.
3. Standing rulings (3 left): CLAUDE.md:71 MPS wording; pool.py:88 fix;
   stall-kill crash_forfeit read rule. IDEAS_POST_100M re-rank per its
   §1 (SS-CLIMB: "more steps" competes; extensions need a new pre-reg).

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** — pool 3 seeds; read SHAPE, never rungs.
- **RESUME SPLITS HISTORY** (0 resumes this fleet; rule stands).
- vs-SH/off-FP are NEVER ladder numbers; FP@20 quotes carry budget + the
  two standing disclosures, forever.
- **RECONCILE (unchanged):** LADDER R3 STATUS 106-94 (n=200) vs readout
  106-102 (208). foul-play Struggle PANIC open (died once in R4S66).
- Showdown server pid 68702 is ~2.5 days old; restart before the next
  training run (R0-j-class hygiene), not urgent for evals.

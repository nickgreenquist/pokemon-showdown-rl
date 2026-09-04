# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`: gen1→gen4→gen9)
Step 1 DONE AND CREDITED. The 2026-08-31 off-arc order (100M run) is
**DISCHARGED** — run done, graded, readout committed 2026-09-04.
**NEXT IS STEP 2 (ladder) — every cell of the 100M table routes there.**

## Where things stand (2026-09-04 evening) — LADDER R4 HOLD LIFTED
- **100M (C1) COMPLETE AND GRADED — CELL P3.** Primary off-FP@20 greedy
  pooled **0.49844** vs control 0.47456: **delta +0.02389 vs floor 0.025**
  (se_gov clustered 0.00774; NOT credited; A-COLL void). vs-SH secondary
  pooled **0.79589** (+0.00944, SN-N descriptive). BC-clone 0.9233.
  **S-SHAPE: SS-CLIMB** — still climbing at 100M (+0.029, 4.6× threshold;
  sub-100M rungs are on the 100M anneal — never compare to finished runs).
  Full account: RESULTS.md §18; README row landed (full anchor battery).
- **E2 rung retention DISCHARGED** — deleting the ~600 treatment + 300
  control rungs is permitted (keep completion + 12M rungs; maintainer call).
- **`audit-fixes` MERGED AND CLOSED** (ff, 46 commits; record:
  docs/archive/AUDIT_BRANCH_LOG.md). Re-verified 2026-09-04 evening on main
  @3d8fd19: bare suite **785 passed / 17 skipped**, tree clean, main ==
  origin/main, branch + worktree gone. F-04 pre-reg / F-06 / F-07 are
  PROPOSALS under docs/proposals/ (unruled).
- **`gen4-design` PAUSED (maintainer, 2026-09-04 evening) — NOT a ladder
  blocker.** As found: ZERO commits of its own, worktree `docs/design_gen4`
  EMPTY, base 58 commits behind main — rebase onto main when resumed.

## Next actions — **MAINTAINER, in order**
1. **LADDER R4 — RATIFIED; HOLD LIFTED 2026-09-04 evening** (maintainer:
   gen4-design paused, not a blocker). Object: 100M final s112, GREEDY,
   account nickgen1rbrlbot REUSED (M6). **LG-2 PRE-CHECK PASSED
   2026-09-04:** profile == R1 banked end state (Elo 1292.25, GXE 59.6,
   Glicko-1 1573.04, rd 26.57, 95-105 = n 200; zero games since
   2026-08-26). **LG-1 courtesy note WAIVED (M10, maintainer, 2026-09-04
   evening: not a tournament, not a high-traffic room) — start whenever.**
   Maintainer act: update .env (PS_USERNAME AND PS_PASSWORD — currently
   bot2). Then
   agent-side: official LG-2 capture into the readout dir, LG-4, LG-5
   (set-pool re-check within 24 h), LG-6 smoke on a FRESHLY restarted local
   server (finalize VOID (e) threshold), LG-7 (server STOPPED, tree clean),
   then LG-9 launch (~90 s at the terminal; agent babysits 12-16 h).
   Pre-reg: configs/eval/ladder_r4.yaml — read it IN FULL before LG-6.
2. Audit rulings owed (AUDIT_BRANCH_LOG §Open questions): F-21 keep the
   borrowed set prior tracked?; F-04 fold/drop/neither + routing; F-06/F-07
   options; F-05 cadence (4 updates); F-03 900 s. None gate the ladder.
3. Standing rulings (3 left): CLAUDE.md:71 MPS wording; pool.py:88 fix;
   stall-kill crash_forfeit read rule. IDEAS_POST_100M re-rank per its
   §1 (SS-CLIMB: "more steps" competes; extensions need a new pre-reg).
   gen4-design resume: maintainer's call, off the ladder critical path.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** — pool 3 seeds; read SHAPE, never rungs.
- **RESUME SPLITS HISTORY** (0 resumes this fleet; rule stands).
- vs-SH/off-FP are NEVER ladder numbers; FP@20 quotes carry budget + the
  two standing disclosures, forever.
- **RECONCILE (unchanged):** LADDER R3 STATUS 106-94 (n=200) vs readout
  106-102 (208). foul-play Struggle PANIC open (died once in R4S66).
- Showdown server pid 68702 is 3+ days old; LG-6 restarts it fresh and
  LG-7 stops it before launch. Nothing else heavy is on the box.

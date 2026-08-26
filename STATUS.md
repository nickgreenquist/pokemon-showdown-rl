# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **CH5 R1 PRE-REG IS r6. EVERY BLOCKER IS
CLOSED; IT NEEDS THE MAINTAINER'S RATIFICATION, THEN IT LAUNCHES.** All five
build items BUILT, nine arms ENUMERATED, both escalations RULED. Suite
**590 / 17** (was 573). Grader `--selftest` green off banked CH4 artifacts.
Nothing launched; tree clean.) **Pure from-scratch self-play; THE NOVELTY IS
THE LANE.** CH3 + CH4-R1 CLOSED. LADDER R1 complete at n=200 (PS Elo 1311,
0.475, 141 opponents, NEVER LISTED so **NO GXE EXISTS — quote the Elo**).

## Results | D26 12M HEADLINE **0.71825** vs SH · R0 ensemble 0.74633 · D29r2
50M 0.70222 · **R2 search@M 0.79283** (B1 CREDIT, SH-facing) · **LADDER R1
n=200 DESCRIPTIVE, PS Elo 1311, NO GXE** · off-FP@20 (12M lanes only)
0.342/0.355/0.356/0.342, fleet 0.34867 n=12,000. Ties=loss; locked = final ckpt.

## Next actions
1. **RATIFY `configs/eval/ch5_r1_offsh.yaml` (r6), then launch.** Run
   `bash scripts/ch5_preflight.sh && bash scripts/ch5_r1_wave.sh`. Serial
   k=1, **7.53 h** of battles, agent-side (0 maintainer terminal hours).
   Order C0, A80-82, B80-82, CE3, CE7. **C0 alone (1.33 h) is already a
   complete standalone result** — the repo's FIRST (proxy, ladder) pair.
2. **STILL OPEN FOR YOU: A-BR-1** (buy a 4th 50M lane, ~12.5 h? designer A
   says NO — let WITHIN/WEAK route to C2, which buys the lane as the LEVER)
   and **A-BR-5** (CHAPTER5 §1 motivation 2 still says ONE (proxy, ladder)
   pair; there are ZERO — an edit to a ratified doc, so it is your call).
3. **THEN the training lever from CHAPTER5 §5.** Maintainer's six stay
   first-class (§3); §3b additions COMPETE. Encoder fork LAST. **R1 may
   produce the R3 model on its own** — if CE7 or search-on-50M beats L2
   off-FP, no retraining is needed.
4. `CLEANUP.md` still needs rulings. **12 commits UNPUSHED — ask first.**

## What r6 changed that you should know
- **The TOST is UNREACHABLE at n=1000 at ANY sigma_seed** (needs s_50 <=
  0.01324; the per-lane binomial sd ALONE is 0.01507). So **"flat" is BARRED
  on every branch** — from arithmetic, not taste. Ruled: keep n, bar the word.
- **The cliff had a SECOND COPY in prose, still at n=1500** after the key was
  recomputed — the "each fix landed in one place" failure again. Now a
  pointer. The missing n-INDEPENDENT row (s_50 = 0.0206) is restored.
- Four more figures were stated as LIVE and wrong: 6.3 se (5.9), ~750 (552),
  "correct is 0.0142/7.8 se" (0.0185/5.9), and one winner's-curse number for
  candidates scored at two different n (+0.0101 / +0.0175 / +0.0235).
- **RULED: R1-C funds BOTH rosters, E7 last** (the cut is only reversible in
  the wrong direction). **CHAPTER5 §3 C1 RETRO-RATIFIED** at 0.0735.
- **RULED (assistant, flagged): at k <= 2 the fleet-mean read is DESCRIPTIVE
  ONLY** — at 1 df the sd's CI multipliers span 0.45x-31.9x, a factor of 72.

## Watch items
- **"SCALE IS FLAT" WAS NEVER ESTABLISHED, ON EITHER AXIS.** 50M vs SH is
  0.7423/0.7347/**0.6297**; the delta is **0.44 se** against a 0.0735 bar.
  The heterogeneity IS licensable: **F = 31.7 on (2,3) df, p = 0.0096.**
- **TWO GATES ARE OPEN AND NAMED, not assumed: G1** (no per-arm 5-battle
  smoke is budgeted) and **G-SEARCH** (nothing catches a search arm
  degrading to greedy on ~1/3 of the budget — a DISCLOSED gap).
- **ATTENTION: the 34.6x was vs the FLAT MLP**, not production;
  attention-vs-`entity_deepsets` was NEVER measured. **Temporal context** is
  the sharper gap. CAPACITY was ruled; STRUCTURE was not.
- **WE ARE IN THE STYLE TABLE.** Sum-|delta| from humans: US 0.095, SH 0.095,
  clone 0.124. Gross move errors us 0.6% vs humans 2.7%. **Style is NOT the
  gap**; only the VOLUNTARY switch cut differs (6.9/10.7) — ours are REACTIVE.
- **THE CRITIC IS FINE, NOT SH-SPECIFIC**: AUC 0.704 -> 0.891 by material.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED**; 3 copies via
  `scripts/backup_ladder.sh`. `results/` is single-copy — FP stdout IS G2's
  second tally and may not be deleted before the grader runs.

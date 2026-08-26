# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.
## Where things stand (2026-08-26 — **CH5 R1 PRE-REG IS r6. EVERY BLOCKER
CLOSED; IT NEEDS YOUR RATIFICATION, THEN IT LAUNCHES.** Five build items
BUILT, nine arms ENUMERATED, both escalations RULED. Suite **590 / 17** (was
573); grader `--selftest` green off banked CH4 artifacts. Nothing launched.)
**Pure from-scratch self-play; THE NOVELTY IS THE LANE.** CH3 + CH4-R1
CLOSED. LADDER R1 done at n=200: PS Elo 1311, 0.475, **NEVER LISTED so NO
GXE EXISTS — quote the Elo, never project one.**
## Results | D26 12M HEADLINE **0.71825** vs SH · R0 ensemble 0.74633 · D29r2
50M 0.70222 · **R2 search@M 0.79283** (B1 CREDIT, SH-facing) · **LADDER R1
n=200 DESCRIPTIVE, Elo 1311, NO GXE** · off-FP@20 (12M only) fleet **0.34867**
n=12,000. Ties=loss; locked = final ckpt.
## Next actions
1. **RATIFY `configs/eval/ch5_r1_offsh.yaml` (r6), then launch:**
   `bash scripts/ch5_preflight.sh && bash scripts/ch5_r1_wave.sh` — serial
   k=1, **7.53 h**, agent-side (0 maintainer terminal hours), order C0,
   A80-82, B80-82, CE3, CE7. **C0 alone (1.33 h) is already a complete
   standalone result** — the repo's FIRST (proxy, ladder) pair.
2. **OPEN FOR YOU: A-BR-1** (buy a 4th 50M lane? designer A says NO — let
   WITHIN/WEAK route to C2, which buys the lane as the LEVER); **A-BR-5**
   (CHAPTER5 §1 still says ONE (proxy, ladder) pair; there are ZERO); and
   **whether EPISODES/UPDATE becomes a 7th CHAPTER5 §3 lever** — verified
   2026-08-26 off H&L's committed config: their update eats **15,360
   episodes to our ~34 (~450x)**, and our recorded "100-300" target was
   calibrated against Wang/ps-ppo, which `prior_work` says are the WRONG
   comparable. A config change, not compute. UNTESTED; see prior_work.
3. **THEN the training lever from CHAPTER5 §5.** Your six stay first-class
   (§3); §3b additions COMPETE; encoder fork LAST. **R1 may produce the R3
   model itself** — if CE7 or search-on-50M beats L2 off-FP, no retraining.
4. `CLEANUP.md` still needs rulings. **MAIN IS UNPUSHED — ask before pushing.**

## What r6 changed
- **The TOST is UNREACHABLE at n=1000 at ANY sigma_seed** (needs s_50 <=
  0.01324; the per-lane binomial sd ALONE is 0.01507), so **"flat" is BARRED
  on every branch** — arithmetic, not taste. RULED: keep n, bar the word.
- **The cliff had a SECOND COPY in prose, still at n=1500** after the key was
  recomputed. Now a pointer; the missing row (s_50 = 0.0206) is restored.
- **RULED: R1-C funds BOTH rosters, E7 last** (the cut is only reversible in
  the wrong direction). **CHAPTER5 §3 C1 RETRO-RATIFIED** at 0.0735. **And
  at k <= 2 the fleet-mean read is DESCRIPTIVE ONLY** (assistant's call,
  flagged) — at 1 df the sd's CI multipliers span 0.45x-31.9x, a factor of 72.

## Watch items
- **"SCALE IS FLAT" WAS NEVER ESTABLISHED, ON EITHER AXIS.** 50M vs SH is
  0.7423/0.7347/**0.6297**; the delta is **0.44 se** against a 0.0735 bar.
  The heterogeneity IS licensable: **F = 31.7 on (2,3) df, p = 0.0096.**
- **TWO GATES OPEN AND NAMED, not assumed: G1** (no per-arm 5-battle smoke is
  budgeted) and **G-SEARCH** (nothing catches a search arm degrading to greedy
  on ~1/3 of the budget — a DISCLOSED gap).
- **ATTENTION: the 34.6x was vs the FLAT MLP**, not production; attention-vs-
  `entity_deepsets` was NEVER measured. CAPACITY was ruled, STRUCTURE was not;
  **temporal context** is the sharper gap.
- **STYLE IS NOT THE GAP**: sum-|delta| from humans US 0.095 / SH 0.095 /
  clone 0.124, gross move errors us 0.6% vs humans 2.7%; only the VOLUNTARY
  switch cut differs (6.9/10.7), ours REACTIVE. Critic fine too (AUC 0.891).
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED** (3 copies via
  `scripts/backup_ladder.sh`). `results/` is single-copy and **FP stdout IS
  G2's second tally** — never delete it before the grader runs.

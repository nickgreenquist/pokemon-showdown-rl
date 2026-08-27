# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-27 — **R1-A IS READ OUT. THE PRIMARY READ
FIRED: s82's COLLAPSE REPRODUCES OFF-FP AT 5.2 se. The fleet read is
WITHIN x NON-RESOLVING at a realized bar of 0.0717 — the cell the O-4 cliff
declared unreachable BEFORE any datum.** CE3 also landed. **Five arms are
re-running now** (C0, B80/81/82 after the r7 `dose` fix, CE7), watchdog live.)
**Pure from-scratch self-play; THE NOVELTY IS THE LANE.** CH3 + CH4-R1 CLOSED.

## Results | D26 12M HEADLINE **0.71825** vs SH · R0 ensemble 0.74633 · **R2
search@M 0.79283** · **LADDER R1: GXE 59.6%, Glicko-1 1573+/-27, Elo 1292,
0.475, n=200, not listed** · **R1-A off FP@20: s80 0.3960 · s81 0.3430 ·
s82 0.2730, fleet 0.33733** vs the banked 12M fleet 0.34867 (n=12,000) ·
**CE3 (50M ensemble) 0.3623, n=3000.** Ties=loss; locked = final ckpt.

## R1-A, graded by the pre-reg's own rules
- **PRIMARY — REPRODUCES.** mean{s80,s81} − s82 = **+0.0965** vs a bar of
  0.0369, one-sided positive = **5.2 se**. vs-SH the same contrast was
  +0.10883, so the collapse carries off-FP at 89% of its vs-SH size.
  **s82 is a genuinely bad seed, not an SH artifact.**
- **FLEET — WITHIN x NON-RESOLVING.** delta **−0.0113**; s_50(off-FP)
  **0.0617** ≈ its vs-SH 0.0629, so the CLUSTERED term governs and the bar
  is **0.0717**. That is 0.32 se. **The cliff predicted this**: its 0.0650
  row said bar 0.0755 and "ABOVE is UNREACHABLE".
- **PRE-REGISTERED ACTION, both reads route here: stop buying battles. Buy
  LANES, or drop the scale question.** "flat" is BARRED; quote 0.0717 always.

## Next actions
0. **DO NOT EDIT `configs/eval/ch5_r1_offsh.yaml`, `ch3_r4_fp_runner.sh` or
   `ch3_fp_h2h.py` WHILE THE WAVE RUNS** — runner and seat are invoked FRESH
   PER ARM. Docs and `ch5_r1_grade.py` are safe.
1. **WAVE RUNNING** (detached, PPID 1) — C0, B80/81/82, CE7. ~5.3 h.
   `tail results/ch5_r1_offsh/watchdog.log` for rates and ALERT lines.
   Grade with `python scripts/ch5_r1_grade.py` before quoting anything.
2. **THEN R1-C** needs C0 to compare CE3/CE7 against. **R1-B** is a
   WITHIN-LANE contrast, so the seed heterogeneity does NOT touch it and its
   bar stays floor-governed at 0.025 — the most informative arm outstanding.
3. **OPEN FOR YOU: A-BR-1** (buy a 4th 50M lane? R1-A's answer is now
   evidence FOR it — "buy LANES" is the pre-registered action) and
   **A-BR-5** (CHAPTER5 §1 says ONE (proxy, ladder) pair; there are ZERO).
4. `CLEANUP.md` rulings. **main is UNPUSHED — ask before pushing.**

## Watch items
- **r7 AMENDED A FROZEN PRE-REG AFTER DATA WAS SEEN**, disclosed in its
  banner: the B arms gained `dose: M`. `prereg_sha256` is `80245bbd` for
  A80/A81/A82/CE3 and `afa4ef12` after. Nothing else moved; R1-A is unaffected.
- **"NOT LISTED" NEVER MEANT "NO RATING"** — the leaderboard JSON holds only
  listed accounts; the PROFILE carries GXE/Glicko for any rated one. And
  `L2.battles.jsonl.rating` is PRE-BATTLE: "Elo 1311" was second-to-last.
- **TOP-500 IS ~125 ELO AWAY, NOT 65.** We score 0.340 against the 1300-1400
  band rank 500 lives in; implied true rating ~1232. A model gap, not a
  battles gap.
- **TWO GATES OPEN: G1** (per-arm smoke unbudgeted — it just caught the `dose`
  bug) and **G-SEARCH**. **ATTENTION's 34.6x was vs the FLAT MLP**, not
  production; **temporal context** is the sharper structural gap.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED** (3 copies via
  `scripts/backup_ladder.sh`). `results/` is single-copy and **FP stdout IS
  G2's second tally** — never delete it before the grader runs.

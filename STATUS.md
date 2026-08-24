# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-24 afternoon — **T-GATE T-PASS, DECISIVE:
search@M beats its own greedy self in MIRROR play by mean +0.1515 (3x the
+0.05 bar), 4/4 lanes, zero excluded — the expert-iteration family is
ALIVE and ch3_r5b (offline actor-ExIt credit test) is ELIGIBLE pending
maintainer rulings. Same day: R4 ensemble-critic B3 FLAT (+0.0224 <
0.025, not credited); oracle diag (BARRED) showed true-team info HURTS
search; standing diagnosis corrected — D26 critic srank99 49/51/35/52 of
384, D22's "7-11" is STALE (regen-L2/capacity levers dead). Chapter
mechanism story: the value function limits search, but the ACTOR path
(distill search play into the policy) has the headroom (+0.069 vs SH,
+0.15 mirror).**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** R2 search@M
B1 CREDIT 0.79283 BEST, quoted only WITH its SH-facing caveat. R4 B3 FLAT.
resume-from-checkpoint BUILT (`--resume RUN_DIR`).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing, P2×2)** | **0.79283** |
| CH3 R4 ensemble-critic — B3 FLAT, uncredited (A1S fresh 0.78958) | 0.81200* |
| T-GATE (mirror, n=1000/lane): TM 0.478-0.540, TS 0.637-0.685, mean m +0.1515 | T-PASS |
| s65 anchors: clone greedy/search 0.894/0.860 · FP@100 greedy/search 0.388/0.368 | — |

## Next actions
1. **MAINTAINER RULINGS for ch3_r5b** (the offline actor expert-iteration
   credit test; draft results/design_critic/ch3_r5b_exit_draft.yaml, 7
   open brackets): RULE-1 purity of engine-derived targets entering
   weights — THREE options (CLEAN / NOT-CLEAN / CLEAN-for-search-deployed-
   only; option 3 kills r5b's greedy read, revives design A's successor);
   RULE-1b SH-state prohibition reading; U-B1 clone n=1000; U-B2 4×3000.
   On CLEAN + ratification: ~9 h agent build (recorder/distiller/gates/
   grader), ~2.7 h collection, ~1 h fit, 16-min greedy read. Zero seeds.
2. R5 design cycle artifacts: results/design_critic/ (2 memos, synthesis,
   2 reviews, revision r2, changelog, power sim) — all backed up.
3. Open: E2(σ=0.2) maintainer-buyable; U9 T2b contamination flag; FP h2h
   at stock budget is the readiness anchor.

## Watch items
- **Never quote 0.81200 as a best (B3, uncredited). Never quote T-GATE
  numbers as vs-SH strength — they are MIRROR-regime margins.**
- Oracle-diag numbers BARRED from README/STATUS/headlines (log-only).
- Critic srank "7-11 of 384" is STALE (D22/D25-era); D26 measures
  49/51/35/52 — scope any quote to its era (the D19-pointer landmine).
- Paired se governed R4; unpaired governed the T-GATE; expect sd(d_i)
  0.016-0.033 in evaluator/mirror reads for power planning.
- Named-file reads only; bash 3.2 (no ${var,,}); FP crash-forfeit rule +
  auto-relaunch runner BUILT (scripts/ch3_r4_fp_runner.sh).
- README ± binomial except ‡; never read throughput off time/steps_per_sec.
- results/ dirs are the ONLY copies; ch3_r4, ch3_r3_oracle, ch3_r5a,
  design_ch3_r4, design_critic all mirrored to
  ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67, 75/76, 83/84,
  93/94 all HELD (nothing this cycle burned any). vs-SH ~40% GXE.

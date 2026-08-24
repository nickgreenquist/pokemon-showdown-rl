# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **R5b RAN TO ITS PRE-REGISTERED STOP:
collection clean (12k battles, 494,603 rows, every run-time gate green),
fits complete, but D-2 (a1 >= a0 + 0.20) FAILS on 2 of 4 lanes — s63
-0.085, s64 -0.006 — so B-10 is NOT green: NO battles, NO stamp, NO
cell; the frozen headline is untouched. All four lanes chose tau=hard
(the agreement-maximizing member -> no grid tau passes where the chosen
one fails). Durable color: D-8 |v_LOO-v_own| = 0.047-0.072 at scale —
design A's ~0.06 CONFIRMED, the 0.45 synthetic reading is ~7x off.
AWAITING MAINTAINER RULING: accept the STOP as the arm's outcome, or
commission a re-registration on the D-2 margin's form.**)
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
1. **RULE ON THE R5b STOP** (see 2026-08-25 SESSION_LOGS entry): (a)
   accept — the ExIt arm records "did not clear its own convergence
   gate on 2/4 lanes; no vs-SH read taken"; or (b) commission a D-2
   re-registration (absolute +0.20 margin vs measured a0 heterogeneity
   0.333-0.472 and ~150-battle GATE-split noise; s64 missed by 0.006).
   Distilled checkpoints exist (runs/exit_*, D-5-clean) but are
   unstamped and unread; nothing else is licensed to run.
2. Unpushed: commits past e3bca48 (morning auth only) — ask before push.
3. Open: E2(σ=0.2) maintainer-buyable; U9 T2b contamination flag; FP h2h
   at stock budget is the readiness anchor; R4 follow-ups unproposed.
## Watch items
- **Never quote 0.81200 as a best (B3, uncredited). Never quote T-GATE
  numbers as vs-SH strength — they are MIRROR-regime margins.**
- Oracle-diag numbers BARRED from README/STATUS/headlines (log-only).
- Critic srank "7-11 of 384" is STALE (D22/D25-era); D26 measures
  49/51/35/52 — scope any quote to its era (the D19-pointer landmine).
- Paired se governed R4; unpaired governed the T-GATE; expect sd(d_i)
  0.016-0.033 in evaluator/mirror reads for power planning.
- Named-file reads only; bash 3.2 (no ${var,,}); FP crash-forfeit rule +
  auto-relaunch runner BUILT (scripts/ch3_r4_fp_runner.sh). Encoder env
  vars must NOT be exported to the whole suite — canonical B-3 run is bare.
- README ± binomial except ‡; never read throughput off time/steps_per_sec.
- results/ dirs are the ONLY copies; ch3_r4, ch3_r3_oracle, ch3_r5a,
  design_ch3_r4, design_critic all mirrored to
  ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67, 75/76, 83/84,
  93/94 all HELD (nothing this cycle burned any). vs-SH ~40% GXE.

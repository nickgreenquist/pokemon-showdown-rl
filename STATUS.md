# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **R5b READ OUT: B5 + KILL. Compiling
search into the weights makes the agent WORSE vs SH: delta -0.0545 (bar
0.0442, paired-clustered governs), 4/4 lanes negative. THE ACTOR
EXPERT-ITERATION LINE IS CLOSED for this chapter; search@M stands as an
inference-time lever that does not compile into weights. Ran under
Amendment A1 (D-2 capture-fraction form, win-rate-blind, disclosed on
every branch; headline was capped regardless). Mechanism: C7 materialized
— distilled switch rates ~double; the T-GATE's +0.15 mirror margin is
real IN PLAY but hard-label BC transfers the bias with the signal.
Durable rider: |v_LOO-v_own| 0.047-0.072 at 500k real points (A's ~0.06
confirmed). Headline 0.71825 and R2 0.79283 UNTOUCHED.**)
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
| R5b ExIt distill (Amendment A1): X1 0.6526 vs X0 0.7071, 4/4 neg | **B5+KILL** |
| s65 anchors: clone greedy/search 0.894/0.860 · FP@100 greedy/search 0.388/0.368 | — |

## Next actions
1. R5b is CLOSED (B5+KILL, README row landed). Legal next moves: design
   A's critic-value family (needs its own pre-reg; NOT closed by this
   KILL); R4 follow-ups (all-4 / single-foreign-critic / U8 k=4->8);
   E2(σ=0.2) upgrade; U9 T2b contamination flag; FP h2h at stock budget
   remains the readiness anchor. Chapter story: search@M's value is
   REAL and INFERENCE-ONLY — polish/ladder-readiness path goes through
   the search-deployed agent, maintainer's call.
2. Unpushed: commits past e3bca48 (morning auth only) — ask before push.
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

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-24 overnight — **R4 READ OUT: B3 FLAT. The
LOO 3-critic ensemble evaluator inside search@M scored +0.0224 vs the 0.025
floor — ALL FOUR lanes positive, zero F-gates, KILL not fired, headline
UNCHANGED. Fresh same-session A1S 0.78958 (offset −0.0033 from R2's
0.79283 — era held); A1E pooled 0.81200 DESCRIPTIVE, uncredited, never a
best. Paired se GOVERNED for the first time (sd(d_i) 0.0160 — real lane
heterogeneity: +0.0457 s62 vs +0.0093 s65). Screen's +0.036 not excluded;
df=3 CI does not exclude 0. B3 was pre-named the modal outcome at this
effect size. Anchors not run (iff-B1/B2, as ruled). Full pre-reg cycle:
2-Opus design + 2 reviews + 4 ratification rulings, all landmines held.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** R2 search@M
B1 CREDIT 0.79283 NEW BEST, quoted only WITH its README caveat (SH-facing per
P2×2). R4 ensemble-critic B3 FLAT (+0.0224 < 0.025): NOT credited.
resume-from-checkpoint BUILT (`--resume RUN_DIR`).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing, P2×2)** | **0.79283** |
| CH3 R4 ensemble-critic — B3 FLAT, uncredited (A1S fresh 0.78958) | 0.81200* |
| s65 anchors: clone greedy/search 0.894/0.860 · FP@100 greedy/search 0.388/0.368 | — |
| FP budget ladder (greedy s65, n=250): @20 0.312 · @100 0.388 · @500 0.332 | — |

## Next actions
1. **Maintainer morning read**: R4 B3 readout (SESSION_LOGS 08-24 entry;
   results/ch3_r4/r4_readout.json). Decisions open, none urgent: all-4 /
   single-foreign-critic / larger-n (U8 k=4→8, the only power lever) all
   stay OPEN (KILL did not fire) but need fresh pre-regs + appetite.
2. Oracle-team diag (BARRED binary, ~35 min) — running/ran overnight per
   delegation; outputs BARRED from README/STATUS, log entry only.
3. Open items: E2(σ=0.2) upgrade maintainer-buyable; U9 flag (T2b seg2
   cross-session contamination — "saturates at M" is soft); readiness
   anchor = FP h2h at stock budget.

## Watch items
- **Never quote 0.81200 as a headline/best — B3, uncredited, descriptive.**
  Headline stays 0.79283 WITH its SH-facing caveat.
- Paired-clustered se governed R4 (first time): lane heterogeneity is real;
  future evaluator tests should expect sd(d_i) ~ 0.016 in power calcs.
- Never quote per-arm numbers from unsorted multi-file greps — read named
  files. macOS bash 3.2: no `${var,,}` in runners.
- FP numbers are "FP + our patches"; poke-engine gen1 5th-move panic is
  rare but real — crash-forfeit read rule + auto-relaunch runner (BUILT,
  scripts/ch3_r4_fp_runner.sh).
- E-cell numbers are SCREEN GRADE (±0.028), color never verdicts;
  oracle-diag outputs BARRED from README/STATUS/headlines.
- heal-aware 0.9237 SECONDARY; FG-2p 0.6278 OUT-OF-SCOPE; README ±
  binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies; ch3_r4 + design_ch3_r4 backed up to
  `../pokemon-showdown-rl-d25-backup-20260815/` (re-mirror after readout).
  Seeds 66/67, 75/76, 83/84, 93/94 held. vs-SH 0.72-0.81 is ~40% GXE.

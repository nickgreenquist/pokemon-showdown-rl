# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-22 — **FG-2 GAP FULLY ATTRIBUTED: turn-order
diagnostic run (scripts/ch3_turnorder_diag.py, reruns in 23 s); two repairs
landed (our-side transformed Ditto bridged; heal-aware band) — primary
0.9074 -> 0.9092, heal-aware SECONDARY 0.9237, bar 0.98; measured repair
CEILING ~0.95 -> the FG-2 ROUTE RULING is now the blocking item, options +
recommendation (b) in the 08-22 'later' log entry**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** CH3 ratified
(depth-1 only). R0: ensemble-of-4 B1 CREDIT 0.74633 ("THESE four checkpoints");
K0-1 PASS 0.780 -> V-leaf allowed; flip anchor 0.103. R1 reads: spike 73.2
ms/decision post-expansion, successor-ranking AUC 0.816, oppact sh_accuracy
0.42-0.48 vs 0.436 marginal (named confound), FG-1/4/5/6/7 PASS, FG-2k residual
0.0075. Engine landmines pinned by tests (full-name statuses; readback UPPERCASES
volatiles; from_string drops volatiles; sleep-success branch still self-KOs).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| R2 12M 0.5509 · R3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (+0.0998, p 1/126) | **0.71825** |
| D29r2 50M — R-A CREDIT (named cell) / R-B FLAT · 5-lane desc 0.7181 | 0.70222 |
| D28 zero-info control — A1 (p 1/252), NOT SEALED (late dose collapse) | 0.52240 |
| CH3 R0 ensemble-of-4 — B1 CREDIT (+0.036, THESE four ckpts only) | 0.74633 |

## Next actions
1. **FG-2 ROUTE RULING (maintainer)** — repairs measured to their ceiling
   (~0.95 < 0.98): gap attribution = truncation 1.51pt (top_b is §3 law —
   design change), net_heal 1.42 (SECONDARY built, 0.9237), turn_order
   0.37, ditto-residual 0.39, chip 0.26, sleep-interrupt 0.14
   (engine-internal), rest observability/boundary. Options (a) re-scope
   band, (b) accept + named strata, R2 carries verdict, (c) A-sidecar,
   (d) stop. REC: (b). Full memo: 08-22 'later' log entry.
2. ~~R2 driver~~ DONE (search arms + SF-13 sentinel; FIRST LIVE search
   run green: 3/4 at Dose M, ms 83.7 vs spike 73.2, +14% < ±25% band).
   After the ruling: R2 executable pre-reg YAML (transcribe design §4 R2;
   maintainer process), then R2-1/R2-2 gate re-runs at launch sha.
3. Push: 9 local commits — say the word.
4. Standing: §13/250M futility ruling (rec RETIRE); resume-from-checkpoint
   (24h bar); D7(a) ladder ruling only if R2 lands B1.

## Watch items
- **Spike flip rate vs recorded greedy = 0.51 (post-expansion)** — descriptive
  only; R2 adjudicates whether flips WIN. Quote it nowhere as a strength claim.
- heal-aware 0.9237 is SECONDARY (never governing until ruled); FG-2p 0.6278
  placeholder stratum OUT-OF-SCOPE per pre-reg; FG-6 budget FROZEN.
- D28's A1 quoted WITH "not sealed"; D29r2 R-A is a NAMED CELL; README ± are
  binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies (ch3_r1 incl. harvest+battery+diag backed
  up to `../pokemon-showdown-rl-d25-backup-20260815/`). Seeds 66/67, 75/76,
  83/84, 93/94 held — ch3 burns none. vs-SH 0.72 is still ~40% GXE.

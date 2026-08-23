# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-23 — **R2 B1 CREDIT: SEARCH WINS, NEW BEST
0.7928 (+0.0693 over the same checkpoints greedy, bar 0.025, ALL 4 lanes
positive, worst +0.0497, zero F-gates). FG-2 ruled (b) accepted 0.9092 +
named strata; pre-reg REGISTERED + graded (r2_readout.json). B1 fires:
SH-exploitation falsifier + foul-play h2h + R3 LAUNCH — next session**)
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
| **CH3 R2 depth-1 search@M — B1 CREDIT (+0.0693, 4/4 lanes, NEW BEST)** | **0.79283** |

## Next actions
1. **B1 follow-ups (pre-registered, in order)**: (a) SH-exploitation
   falsifier — two-orientation h2h vs the BC clone (D26 H4 machinery,
   ~20 min); (b) h2h vs Foul Play (purity-legal anchor, 0.8307* vs SH);
   (c) **R3 mechanism grid** (design §4 R3, non-crediting; E1-E4 dials);
   (d) D7(a) ladder contradiction -> maintainer ruling (named, not acted).
2. R2 artifacts: results/ch3_r2/ (80 chunks + r2_readout.json) — back up
   to the d25-backup dir with the next results sync.
3. Push: 4 local commits since the last push — ask first (standing rule).
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

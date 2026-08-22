# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-21 evening — **D28 READ OUT: A1, NOT SEALED — the
zero-info control fails to reproduce D25 at perm 1/252; the dose caveat is
DOWNGRADED, not closed**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** 50M answered
(D29r2): R-A CREDIT (stack transfers, 0.70222, named cell) / R-B FLAT (scale adds
nothing; 5-lane descriptive 0.71813 = the 12M number). **D28 (zero-info dose
control, s70-74): pooled 0.52240 — A1** (+0.09607 vs D25, bar 0.05732, perm 1/252,
strict separation) **x S-b** (-0.022, null band) at dose SHORT/ERRATIC — **SEAL
BLOCKED** (Delta_2 < 0; r_late 0.12: per-bin q collapsed 0.12/0.68/0.01 in bins
9-11 because median g 0.979 — the head LEARNED the task and a learned task stops
dosing). **Structural finding for any successor: a control easy enough to dose is
easy enough to learn; D27 died of trunk collapse, D28's task died of convergence.**
Every readout cell was pre-named; zero adjudications owed. RESULTS §9-12 = the
account. **NEVER "belief state"**; D18 NULL; D27/D30 dead.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| R2 12M 0.5509 · R3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (+0.0998, p 1/126) | **0.71825** |
| D29r2 50M — R-A CREDIT (named cell) / R-B FLAT · 5-lane desc 0.7181 | 0.70222 |
| **D28 zero-info control — A1 (p 1/252), NOT SEALED (late dose collapse)** | **0.52240** |

## Next actions
1. **Maintainer: RATIFY (or amend) the chapter-3 SEARCH design** —
   `results/design_ch3/ch3_search_design_r2.md` (self-contained; full 2-Opus
   round done 08-21: 2 designs + synthesis + 2 reviews, 27 MFs all folded).
   **Five rulings in its §10** (poke-engine admissibility rec ALLOW; install
   deviation; determinization disclosure; K0-2 ownership; D7(a) ladder).
   Nothing runs until ratified; R0 is one evening, ~0.02 ld, zero training.
2. Push: origin current through e03f331; tonight's ch3 session-log commit is
   local (say the word).
3. Standing: §13/250M futility ruling (rec RETIRE, on record);
   resume-from-checkpoint (the 24h bar) — design on request.

## Watch items
- **D28's A1 is quoted WITH "not sealed"** — the pre-registered sentence; the
  caveat is downgraded ("tested once, strongest separation, dose SHORT with late
  collapse"), never "closed"/"refuted". The per-bin q table travels with it.
- **The D29r2 R-A credit is a NAMED CELL** (no strict separation) — sentence
  travels with every quote; STACK not lever.
- **README ± are BINOMIAL except the ‡ row; clustered se governs verdicts.**
- **Never read throughput off `time/steps_per_sec`**; Δstep/Δwall off ckpt mtimes.
- **`results/d25 d25p d19_closeout c4_transfer design_ch2 d26 d29 d29r2 d28
  struct12m/50m finals` are the ONLY copies**, backed up at
  `../pokemon-showdown-rl-d25-backup-20260815/`.
- Ledger: ch-2 realised ~11 ld total (D29r 4.2 + D29r2 4.6 + D28 2.2). Seeds:
  70-74 burned, 75/76 held, 80-92 burned/held per 08-19. vs-SH 0.72 is still
  ~40% GXE — nothing here is "nearly solved".

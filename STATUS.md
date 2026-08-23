# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-23 overnight — **FALSIFIER FIRES (P2): the R2
search increment is SH-FACING on the anchors available — s65 search@M vs the
BC clone 0.8600 vs greedy 0.8940 (delta −0.034 ± 0.041, transfer > +0.008
excluded ~95%) while the same config gains +0.081 vs SH. Headline 0.79283
KEEPS its number, OWES the caveat — WORDING AWAITS MAINTAINER RULING, README
untouched. D26 greedy itself PASSES the anchor (clone trail 0.657 → 0.719 →
0.795, moves with vs-SH; also discharges D26's never-run H4 re-fire)**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** CH3 ratified
(depth-1 only). R2 B1 CREDIT 0.79283 (+0.0693, 4/4 lanes, zero F-gates); R0
ensemble B1 0.74633; falsifier P2 per configs/eval/ch3_r2_falsifier.yaml
(pre-registered, graded; secondary: placeholder_skip_rate 10.8% vs clone,
DOUBLE the 4.4–5.8% vs-SH band — named mechanism candidate; flip 62.4% in-band).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| R2 12M 0.5509 · R3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (+0.0998, p 1/126) | **0.71825** |
| D29r2 50M — R-A CREDIT (named cell) / R-B FLAT · 5-lane desc 0.7181 | 0.70222 |
| CH3 R0 ensemble-of-4 — B1 CREDIT (+0.036, THESE four ckpts only) | 0.74633 |
| **CH3 R2 search@M — B1 CREDIT, NEW BEST; P2 caveat pending ruling** | **0.79283** |
| falsifier (s65 vs BC clone): greedy 0.894 / search@M 0.860 / G pooled 0.795 | — |

## Next actions
1. **Maintainer ruling owed: P2 caveat wording** (draft in the 08-23 log
   entry) before any README change. R3 still launches (B1, independent).
2. B1 follow-ups remaining: (b) h2h vs Foul Play (purity-legal anchor,
   0.8307* vs SH) — IN PROGRESS overnight; (c) R3 mechanism grid
   (design §4 R3, non-crediting, E1-E4 dials) — transcription in progress;
   (d) D7(a) ladder contradiction memo -> morning ruling (named, not acted).
3. Back up results/ch3_r2/ + results/ch3_r2_falsifier/ to the d25-backup dir.
4. Push: local commits since last push — ask first (standing rule).
5. Standing: §13/250M futility ruling (rec RETIRE); resume-from-checkpoint
   (24h bar).

## Watch items
- **P2 does NOT retract the R2 credit** — the credit line's sentence stands;
  what changed is its scope claim (SH-facing until an anchor says otherwise).
  Never quote 0.79283 without the caveat once the wording is ruled.
- Spike flip rate 0.51 and falsifier flip 62.4% are descriptive only.
- heal-aware 0.9237 SECONDARY; FG-2p 0.6278 OUT-OF-SCOPE; FG-6 budget FROZEN.
- D28's A1 quoted WITH "not sealed" (0.52240); D29r2 R-A is a NAMED CELL;
  README ± binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies (ch3_r1 backed up to
  `../pokemon-showdown-rl-d25-backup-20260815/`; ch3_r2 + falsifier owed).
  Seeds 66/67, 75/76, 83/84, 93/94 held — ch3 burns none. vs-SH 0.72 is
  still ~40% GXE.

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-23 overnight — **BOTH off-SH anchors say the R2
search increment is SH-FACING: BC-clone falsifier P2 (s65 search@M 0.860 vs
greedy 0.894, transfer > +0.008 excluded ~95%) AND Foul Play h2h P2 (0.368 vs
0.388, n=250/arm) while the same config gains +0.081 vs SH. Headline 0.79283
KEEPS its number, OWES the caveat — WORDING AWAITS MAINTAINER RULING, README
untouched. D26 GREEDY itself transfers everywhere: clone trail 0.657→0.719→
0.795, FP -against trail 0.124→0.172→0.388. R3 DOSE AXIS READ OUT: T2b,
SATURATES AT M — seg1 (S→M) +0.020 resolved above the +0.0125 band, seg2
(M→L) +0.0025 unresolved; zero F-gates; non-crediting. RULINGS EXECUTED**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** CH3 ratified
(depth-1 only). R2 B1 CREDIT 0.79283 (+0.0693, 4/4 lanes, zero F-gates).
Named mechanism candidate for R3: placeholder_skip_rate scales with opponent
distance from SH (4.4-5.8% SH / 10.8% clone / 17.9% FP). D26's own H4 re-fire
debt (owed at >=0.6435, never run at its readout) discharged tonight: PASSES.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| R2 12M 0.5509 · R3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (+0.0998, p 1/126) | **0.71825** |
| D29r2 50M R-A · D28 A1 "not sealed" 0.52240 · R0 ensemble 0.74633 | 0.70222 |
| **CH3 R2 search@M — B1 CREDIT, NEW BEST; P2 caveat in README per (c)** | **0.79283** |
| s65 vs BC clone: greedy 0.894 / search@M 0.860 / G pooled 0.795 | — |
| s65 vs Foul Play (n=250/arm): greedy 0.388 / search@M 0.368 | — |

## Next actions
1. **RULINGS EXECUTED 2026-08-23**: P2 caveat (c) in README (+2 anchor rows);
   D7(a) ladder = DEFERRED-UNTIL-READY (ready = models exhausted vs SH+FP
   anchors; CLAUDE.md landmine reworded); DESIGN §13 RETIRED with named
   re-triggers (ladder-ready polish run / logs still climbing). Pushed.
2. Pipeline (auto): FP budget ladder (@20/@500) → E-cell screens (E2 σ
   ladder / E3 LOO / oppact ablation, configs/eval/ch3_r3_ecells.yaml).
   MC-leaf/λ-blend blocked on a State→obs reverse bridge — options with
   maintainer (async). Oracle diag binary built, not yet run (BARRED).
3. resume-from-checkpoint BUILT 2026-08-23 (`--resume RUN_DIR`) — closed.
4. Push: several local commits since 087e3dc — maintainer said push after;
   will push with the evening readouts.

## Watch items
- **P2 does NOT retract the R2 credit** — but never quote 0.79283 without
  its README caveat (SH-facing, s65-lane scope).
- FP numbers are "Foul Play + our patches" (always quoted so); FS attempt-1
  hit a poke-engine panic (Invalid PokemonMoveIndex: 4, gen1 5th-move state)
  — rerun was clean; crash-forfeit read rule pre-stated in the log.
- All falsifier/FP-h2h deltas are s65-lane-only; flip rates descriptive only.
- heal-aware 0.9237 SECONDARY; FG-2p 0.6278 OUT-OF-SCOPE; FG-6 budget FROZEN;
  README ± binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies; ch3_r1/r2 + falsifier + fp_h2h backed
  up to `../pokemon-showdown-rl-d25-backup-20260815/`; ch3_r3 owed after
  readout. Seeds 66/67, 75/76, 83/84, 93/94 held — ch3 burns none.
  vs-SH 0.72 is still ~40% GXE.

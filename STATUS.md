# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-23 evening — **CH3 R3 COMPLETE: the mechanism
verdict is VALUE-LIMITED. Dose axis T2b (seg1 S→M +0.020 resolved above the
+0.0125 band; seg2 M→L +0.0025 unresolved — saturates at M). E-cell screens:
E3 LOO-ensemble evaluator +0.036 OVER E0 (0.847/0.810 vs 0.793/0.792);
evaluator noise collapses the gain monotonically (σ0.4 → ~0.45); oppact head
INFERENCE-INERT vs SH (its D25 training credit untouched). FP budget ladder:
NO gradient (0.312/0.388/0.332 at 20/100/500 ms) — budget is not a readiness
dial. Earlier same day: BOTH off-SH anchors fired P2 (search increment
SH-facing); three rulings executed (caveat (c) in README, ladder
deferred-until-ready, §13 RETIRED). All pre-registered, all backed up.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** R2 search@M
B1 CREDIT 0.79283 NEW BEST, quoted only WITH its README caveat (SH-facing per
P2×2; s65-lane transfer tests). resume-from-checkpoint BUILT (`--resume RUN_DIR`).
Skip-rate trail (mechanism color): 4.4-5.8% SH / 10.8% clone / 17.9% FP.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, NEW BEST (caveat: SH-facing, P2×2)** | **0.79283** |
| s65 anchors: clone greedy/search 0.894/0.860 · FP@100 greedy/search 0.388/0.368 | — |
| R3 screens (1000/lane): E3 LOO 0.847/0.810 · OPA 0.802/0.777 · σ0.4 0.480/0.412 | — |
| FP budget ladder (greedy s65, n=250): @20 0.312 · @100 0.388 · @500 0.332 | — |

## Next actions
1. **R4-family candidate for maintainer**: depth-1 search@M with an
   ENSEMBLE-CRITIC evaluator (pure, zero training; E3's +0.036 directional
   at the credited dose). Needs fresh pre-reg + ratification (MF-7) + the
   anchor battery (P2 makes off-SH transfer THE question for it).
2. Open R3 remainders: MC-leaf/λ-blend blocked on a State→obs reverse
   bridge (options owed to maintainer, async); oracle-team diag built,
   unrun (BARRED binary, scripts/ch3_oracle_diag.py, 1 lane × 1000);
   E2(σ=0.2) upgrade at 4×3000 stays maintainer-buyable.
3. Readiness anchor simplifies: FP h2h at stock budget (no ladder staircase).
4. Pushed through the evening readouts (maintainer-authorized "push after").

## Watch items
- Never quote 0.79283 without its README caveat. Never quote per-arm numbers
  from unsorted multi-file greps — read named files (twice bitten 08-23).
- FP numbers are "Foul Play + our patches"; poke-engine gen1 5th-move panic
  (`Invalid PokemonMoveIndex: 4`) is rare but real — FP-side runners
  auto-relaunch with the crash-forfeit read rule pre-stated in the log.
- macOS runs bash 3.2: no `${var,,}` in runner scripts (cost one arm 08-23).
- E-cell numbers are SCREEN GRADE (±0.028) — directional color, never
  verdicts; oracle-diag outputs are BARRED from README/STATUS/headlines.
- heal-aware 0.9237 SECONDARY; FG-2p 0.6278 OUT-OF-SCOPE; FG-6 budget FROZEN;
  README ± binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies; ch3_r1/r2/r3 + ecells + falsifier +
  fp_h2h + fp_budget_ladder all backed up to
  `../pokemon-showdown-rl-d25-backup-20260815/`. Seeds 66/67, 75/76,
  83/84, 93/94 held — ch3 burns none. vs-SH 0.72 is still ~40% GXE.

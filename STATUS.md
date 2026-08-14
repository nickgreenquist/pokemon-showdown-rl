# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-14 — D25 RUNNING at coef 0.1, 5 lanes s52-56)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (seed sd 0.0756); D18 NULL; D23
regen-L2 "letter-met, seed-fragile, NOT credited"; the 50M CARRY IS REJECTED (bar
≥0.6675, above the best lane ever, 0.6593). **D25 (opponent ACTION prediction) BUILT**
(~230 lines, 26 tests, suite **319 green**); gates R0-12b/R0-13(a)/(b) PASS; smoke set
coef 0.1 — frozen in config §15B/§15C + SESSION_LOGS 2026-08-13/14; R0-10's
largest-passing-arm rule was DEVIATED FROM, disclosed (§15C).

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |
| **LADDER** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M | **NOT claimed** |

## Next actions, in order (maintainer decisions at the top)
0. **D25 RUNNING — verified 11:10 EDT by battle PROGRESS: 3.68-3.72M steps, wall
   312-327 steps/s** (R0-8: ≥30-min WALL window, never logged `steps_per_sec`; record
   <255, STOP <210), `winrate_anchor` 0.969-0.979 (R1 ≥0.75 at 4M met; <3 of 5 clearing
   STOPS the arm → F5 NEGATIVE, no re-tune), entropy 0.35-0.47 (K6: median <0.15 ×5
   before 6M → stop lane), `aux/illegal_label_frac` 0. Finals **~18:30 EDT**; `screen`
   d25_s52…s56; a dead lane relaunches on a FRESH seed (47-48 held), never same seat.
1. **YOUR CALL: the shuffled-label placebo arm, +2.35 lane-days** (chapter → ~18.2/20) —
   "an explicit opponent model helps" vs "an aux loss helps". Needed before the READOUT.
2. **R0-14 GRADER WRITTEN + VERIFIED** (`scripts/d25_grade.py`, 20 tests incl. known-p
   cases per grid; suite **339 green**). Attestation-first (R0-15): reproduces the five
   frozen comparator finals from disk, 0.54452/0.03558, §5 atoms, both tape shas — PASS.
   At readout: put finals in `results/d25/final_s{52..56}.json`, atoms in
   `treatment_atoms.json` {"L6":{...},"c12":{...}}, dormancy CSV; then run it.
3. **M4 CLONE RE-SCORE at 5×3000 BEFORE the finals land** — the obligations fire on the
   NUMBER (pooled ≥0.558), not on a verdict; a FLAT result can trigger them.
4. At the finals: locked eval — final ckpt, deterministic, ties as non-wins, vs SH,
   **3000 battles/seed × 5 seeds pooled**, BOTH encoder env vars at every eval.
5. Also owed: **C10** — do §0 tapes include forced post-faint replacements? settle
   pre-readout. **g NEVER COMPUTED** for R0-10(a) (proxied via `aux/loss`) — close or
   say "proxied". **R0-16** dormancy control s50/s51, 12M, tau 0.025 (S1 letter only).
6. **LEDGER: chase 13.54 + this rung's 2.35 = 15.9/20**; re-measure, never increment.

## Watch items
- **`grad_clip_frac` ~0.99 mid-run is NORMAL, NOT a VOID trigger** — the clause's 0.90
  is a WHOLE-RUN mean; controls sit 0.9847-0.9878 at matched steps (D25 0.9843-0.9886).
  Compare at MATCHED STEPS or every lane voids, controls included.
- **results/d25/ IS THE ONLY COPY of the sha256-frozen tapes** (gitignored) — losing it
  voids the mechanism co-primary. `scripts/d25_gates.py verify` attests them.
- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 47-48 held for a D25
  lane lost before R1; **52-56 = D25**; 57+ free.
- **Quote the RANGE, not the best variant** (MDE 0.0105-0.0301; non-fire <~0.017 nats
  UNINFORMATIVE). MAX null to ESTABLISH, MEDIAN to RETIRE. LEARNED bar **0.3286**. L6
  class order `{slot0..3, OTHER_MOVE=4, SWITCH=5}`. Realised under pool labels
  **0.4485** (~46%). **Verify launches by battle PROGRESS** (`setsid` absent on macOS;
  wandb offline — a stale history.csv is not a stalled lane).

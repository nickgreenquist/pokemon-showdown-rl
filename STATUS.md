# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D25 BUILT and GATED; smoke is next; 0 lanes)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (seed sd 0.0756); D18 NULL; D23
regen-L2 "letter-met, seed-fragile, NOT credited"; the 50M CARRY IS REJECTED (bar
≥0.6675, above the best lane ever, 0.6593). **D25 (opponent ACTION prediction) is now
BUILT** (~230 lines, 26 tests, suite **319 green**) **and its zero-lane gates are RUN:
R0-12b, R0-13(a), R0-13(b) PASS. R0-10b fired; amendment A1 was REFUSED on review and
A2 measures the ratio LIVE in the smoke instead.**

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |
| **LADDER** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M | **NOT claimed** |

## Next actions, in order (maintainer decisions at the top)
0. **RUN THE R0-10 SMOKE, then launch 52-56.** Four arms shipped as
   `configs/showdown_sp_actpred_smoke_c{005,010,025,050}.yaml`, seed 99, **ONE AT A
   TIME** (they collide on Showdown usernames), ~4 min each; read with
   `scripts/d25_gates.py smoke`. **R0-10b's A1 amendment was REFUSED by both reviews**
   — the fitted-head construction is not determinate (a reviewer reproduced it and got
   1.74/1.46/1.24 vs A1's 2.50/3.41/4.19) and A1's headline was a Jensen-inflated
   mean-of-ratios whose "head-draw spread" was the DENOMINATOR (13.6× across advantage
   draws with the actor FIXED). **A2, PROPOSED: neither offline proxy gates the rung** —
   both measure ‖W_last‖ × residual over a random advantage vector — so the ratio is
   measured LIVE (`aux/trunk_norm` / `aux/policy_trunk_norm`, ratio-of-means). **Reads
   0.177 at coef 0.1 over 8k steps, in band.** No pre-registered number changes; the rule
   selects **0.1, already in the config**. Record: `results/d25/d25_amendment_r010b.md`.
   If you prefer R0-10b's strict reading it stands and the rung does not launch.
1. **YOUR CALL before launch: the shuffled-label placebo arm, +2.35 lane-days** (chapter
   → ~18.2/20) — "an explicit opponent model helps" vs "an aux loss helps".
3. **LEDGER: chase = 13.54, headroom ~6.5**; re-measure, never increment. **§13
   DEFECT:** it conditions 250M on a credited 50M lever and none exists → restate.
## Gate results, frozen into the config's §15B (zero-lane, `scripts/d25_gates.py`)
- **R0-12b PASS** — nulls +0.0009 / +0.0021 / -0.0046 / -0.0146 against a real ctx of
  +0.0150; closest null 7× below. Header claim corrected: the PCA nulls are NOT "worse
  than nothing" in L6 on s36. **R0-13(a) PASS** — window 1.1505 → **0.9783 (85%)**,
  matching the 86% prior; and realised does NOT hold constant under pool labels
  (**0.544 → 0.4485**), so the honest headline is **~46% of the knowable, not ~50%**.
- **R0-13(b) — the LEARNED bar MOVES to 0.3286** (L6 mean g 0.4108) from 0.371, an 11.4%
  loosening; §6's WEAK band becomes [0.10, 0.3286). The grader reproduces §5's frozen
  atoms to 4.7e-05 before any gate runs.
- **BUILD FIX from running the real launch path:** SWITCH legality assumed the opponent's
  active is ALIVE, so forced post-faint replacements were called illegal and dropped at
  0.12% of live decisions — enough to HARD-FAIL R0-5(d) at read time. No frozen tape
  carries such a row, so no offline gate could have caught it. Fixed; now 0.0000.

## Watch items
- **results/d25/ IS THE ONLY COPY of the sha256-frozen reference tapes** (gitignored,
  rescued from a job scratch dir) — losing it voids the mechanism co-primary.
- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 = the smoke; 47-48
  held for a D25 lane lost before R1; **52-56 = D25**; 57+ free.
- **Quote the RANGE, not the best variant.** **MAX null to ESTABLISH, MEDIAN to RETIRE.**
  `ctx` is max-pooled ⇒ heads and estimators must be scorer-shaped. BOTH env vars, always.

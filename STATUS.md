# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D25 BUILT and GATED; R0-10b fires; 0 lanes)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (seed sd 0.0756); D18 NULL; D23
regen-L2 "letter-met, seed-fragile, NOT credited"; the 50M CARRY IS REJECTED (bar
≥0.6675, above the best lane ever, 0.6593). **D25 (opponent ACTION prediction) is now
BUILT** (~230 lines, 25 tests, suite **318 green**) **and its zero-lane gates are RUN:
R0-12b, R0-13(a), R0-13(b) PASS; R0-10b FIRES NO-LAUNCH and needs your call.**

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |
| **LADDER** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M | **NOT claimed** |

## Next actions, in order (maintainer decisions at the top)
0. **YOUR CALL, AND IT BLOCKS LAUNCH — R0-10b.** On the built head the aux/policy
   trunk-gradient raw ratio is **0.037-0.074 / 0.020-0.047 / 0.006-0.059** at
   600k/6M/12M (5 head draws), so the whole pre-stated grid {0.05, 0.1, 0.25, 0.5} lands
   at 0.0015-0.029 against the band's 0.05 floor → **grid EMPTY, stated action "the rung
   does not launch"**. The policy column reproduces D19-B's within ~1.5× so the proxy is
   right; D25's aux gradient is 4×/33×/36× SMALLER than D19's — the opposite of what the
   header expected from B6a's wider path. **AND THE BAND FAILS ITS OWN SOURCE:** on
   D19-B's table at D19-B's own recommended 0.1 it rejects 2 of 3 gated stages.
   Arithmetic only, not a proposal: the band wants coef ∈ **[1.7, 26]**. Amending the
   grid, band or `aux_head_gain` is a ratified pre-reg change → 2 designers + 2 reviews.
1. **YOUR CALL, also before launch: the shuffled-label placebo arm, +2.35 lane-days**
   (chapter → ~18.2/20) — "an explicit opponent model helps" vs "an aux loss helps".
2. **THEN the R0-10 coefficient smoke** (four arms, seed 99, **ONE AT A TIME** — they
   collide on Showdown usernames), unspecifiable until 0 is settled; ~20 min in your
   terminal, then launch 52-56.
3. **LEDGER: chase = 13.54 lane-days, headroom ~6.5**; re-measure, never increment.
   **§13 DEFECT:** it conditions 250M on "a credited lever at 50M" and none exists →
   restate or waive. CLAUDE.md says 1000 battles/seed, DESIGN §8 says 3000 — fix.

## Gate results, frozen into the config's §15B (zero-lane, `scripts/d25_gates.py`)
- **R0-12b PASS** — nulls +0.0009 / +0.0021 / -0.0046 / -0.0146 against a real ctx of
  +0.0150; closest null 7× below. Header claim corrected: the PCA nulls are NOT "worse
  than nothing" in L6 on s36, they are slightly positive. Verdict untouched.
- **R0-13(a) PASS** — window 1.1505 → **0.9783 (85%)**, matching the 86% prior; and
  realised does NOT hold constant under pool labels: **0.544 → 0.4485**, so the honest
  headline is **~46% of the knowable, not ~50%**.
- **R0-13(b) — the LEARNED bar MOVES to 0.3286** (L6 mean g 0.4108) from 0.371, an 11.4%
  loosening; §6's WEAK band becomes [0.10, 0.3286). The grader reproduces §5's frozen
  atoms to 4.7e-05 before any gate runs.

## Watch items
- **results/d25/ IS THE ONLY COPY of the sha256-frozen reference tapes** (gitignored;
  rescued from a job scratch dir). Losing it voids the mechanism co-primary.
- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable; 47-48
  held for a D25 lane lost before R1; **52-56 = D25**; 57+ free.
- **Quote the RANGE, not the best measured variant.** **MAX null to ESTABLISH, MEDIAN to
  RETIRE.** Letters at n=3 quantize to {0, 0.21, 0.79, 1}. `ctx` is max-pooled ⇒ heads and
  estimators must be scorer-shaped. BOTH encoder env vars, always.

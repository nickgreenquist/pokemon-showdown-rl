# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D25 RATIFIED at r2 and BUILT; 0 lanes)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT credited"**; Rung-2
12M seed sd ≈0.036. **THE 50M CARRY IS REJECTED** (2 designers + 2 reviews + 2 opposed
advocates, 0 lanes) — no branch changes a decision, and the 50M credit bar is **≥0.6675
unconditionally**, above the best lane ever (0.6593). The **GEOMETRIC-NULL STUDY**
(results/d24_null/) re-grades D23: **critic de-collapse SURVIVES; the actor read is
INCONCLUSIVE, not refuted** ("2 of 3 below geometry" used the max null).

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **D25 (opponent ACTION prediction) RATIFIED at r2 on L6 and BUILT, NOT LAUNCHED** —
   `configs/showdown_sp_actpred12m.yaml` is the SPEC and now also RUNS (§15 BUILD
   RECORD). Premise **0.544 nats realised (L6, 5 lanes, 8 splits) of a ~1.0-nat
   pool-corrected window**. Letter Δ_ref-ctx on the FROZEN s36@12M reference, level
   12/252 = 0.0476, **MDE(80%) 0.0105–0.0301, power at +0.010 = 0.27–0.76** (the RANGE,
   never the best cell); a non-fire below ~0.017 nats is uninformative. Seeds **52–56**,
   ~2.35 lane-days → 15.9/20. Build: ~230 lines, 24 tests, suite **317 green**; both
   verify-at-build numbers HOLD; **R0-2/2b/2c, R0-3, R0-5(a-d), R0-7, R0-9 DISCHARGED**.
1. **NEXT UNIT — the gate scripts, all zero-lane, all BLOCKING:** (a) **R0-13**'s L6
   LEARNED bar (0.371 is anchored on 12-class `g_frozen-probe` values and its 0.80
   multiplier is unsourced) plus the pool correction on the REAL `_evict_index`
   schedule; (b) **R0-12b**'s four capacity nulls on the s36 tape at max_iter 2000 with
   the asserted ||g||<1e-3; then **R0-10b** offline and the **R0-10** coefficient smoke
   (four arms, seed 99, ONE AT A TIME — they collide on Showdown usernames otherwise).
2. **YOUR CALL, needed BEFORE launch: the shuffled-label placebo arm, +2.35 lane-days**
   (chapter → ~18.2/20) — "an explicit opponent model helps" vs "an aux loss helps".
   Currently NAMED-NOT-RUN; the header scopes the claim accordingly.
3. **LEDGER AUDITED — recorded ~17 was ~3.5 HIGH.** 392.8 lane-hours, 67.9 pre-chase →
   **chase = 13.54, headroom ~6.5**; re-measure, never increment. **§13 DEFECT:** it
   conditions 250M on "a credited lever at 50M", and none exists → restate or waive.
   CLAUDE.md's locked eval says 1000 battles/seed, DESIGN §8 says 3000 — fix.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable; 47-48
  held for a D25 lane lost before R1; **52-56 = D25**; 57+ free.
- **Quote the RANGE, not the best measured variant** — the 08-13 systematic error. Rank
  reads: **MAX null to ESTABLISH, MEDIAN null to RETIRE**; srank float64 + Gram fallback;
  `--tag` every pass. Letters at n=3 quantize to {0, 0.21, 0.79, 1} — calibrate first.
- `ctx` is max-pooled and logits are `scorer([ctx‖entity])`, so a linear ctx probe cannot
  decode even the actor's OWN action ⇒ heads and estimators must be scorer-shaped.
- Entity ckpts need BOTH env vars. Eval auto-tie crash can kill a lane; relaunch on a
  FRESH seed (s49→s51). Artifacts results/d23/, d24_design/, d24_null/ are gitignored.

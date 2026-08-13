# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — carry rejected, D19's premise failed; 0 lanes spent today)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT credited"** (BOUND,
gap-shrink realized, srank letter not met, falsifier NOT fired); Rung-2 12M seed sd
≈0.036. **THE 50M CARRY IS REJECTED** (2 designers + 2 reviews + 2 opposed advocates,
0 lanes, results/d24_design/) — no branch changes a decision, and the 50M win-rate
credit bar is **≥0.6675 unconditionally**, above the best lane ever (0.6593).
Zero-lane work landed (detail in the 08-13 log): rank tooling repaired (`srank99=1` was
a float32 NaN sentinel; one record cell fixed; D23's destroyed control pass regenerated
and it MATCHES what was logged), and the **GEOMETRIC-NULL STUDY** (results/d24_null/)
re-grades D23 at matched distance — **critic de-collapse SURVIVES (1.35/2.21/1.64×),
actor rise does NOT** — showing a raw 50M rank contrast is geometry and **dormancy is
the null-robust statistic**.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **MAINTAINER CALL — D19's PREMISE FAILED at zero lanes; authorized but NOT built.**
   Two designers, independent data (1800 tape-recovered teams; 4000 generator teams),
   both measured gen1-randbats teams as independent near-uniform draws: learnable
   structure **0.074 nats of ~4.94** (0.064 of it mere exclusion), belief content
   **0.000 at one revealed mon**. A team-prediction head cannot form a belief state
   here. Options: (i) drop D19, record the format finding; (ii) **RE-TARGET to opponent
   ACTION prediction** — in a simultaneous-move game that is the belief that bears on
   the decision, free ground truth, same plumbing and budget, own cycle; (iii) close
   the chapter. **I recommend (ii).**
1. **LEDGER AUDITED — recorded ~17 was ~3.5 HIGH.** 392.8 lane-hours, 67.9 pre-chase →
   **chase = 13.54, headroom ~6.5**; drift was estimate-rounding, not lost runs. Any
   5-lane 12M rung = 2.24 → 15.8/20. Re-measure, never increment.
2. **§13 DEFECT:** conditions 250M on "a credited lever at 50M"; none exists under
   today's line → restate or waive. CLAUDE.md's locked-eval line says 1000
   battles/seed, DESIGN §8 says 3000 — fix.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free**. Rank reads: MARGIN over the matched-distance null; `--tag` them.
- Entity ckpts need BOTH env vars. Eval auto-tie crash (~1-in-10⁴) can kill a lane;
  same-seed relaunch hits zombies — use a FRESH seed (s49→s51, log 08-12).
- Aux head: 384→152 breaches ACTOR_PARAM_CEILING (own it on the agent); clip aux grads
  SEPARATELY (`grad_clip_frac` 0.90 ⇒ coupled = covert LR cut). Letters at n=3 quantize
  to {0, 0.21, 0.79, 1} — calibrate every level, never eyeball.
- Artifacts results/d23/, d24_design/, d24_null/ (gitignored). Suite 293 green (R0-3
  golden needs its own pytest run). Process: 2 Opus designers + 2 reviews per pre-reg.

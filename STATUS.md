# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D23 read out; the 50M carry designed, NO-GO as scoped)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT credited"** (BOUND,
gap-shrink realized, srank letter not met, falsifier NOT fired).
Rung-2 12M seed sd ≈0.036. **THE 50M CARRY IS REJECTED (2 designers + 2 reviews + 2
opposed advocates, 0 lanes, results/d24_design/)** — no branch changes a decision. The
zero-lane work then LANDED: (1) `srank99=1` was a float32 NaN sentinel — tooling now
float64 + Gram fallback + hard fail + no-clobber; record re-derived (1 cell fixed, s36
critic@6M 1→19; D23's destroyed control pass regenerated, MATCHES the logged 11/17/16);
(2) **GEOMETRIC-NULL STUDY** (results/d24_null/): at matched distance D23's **critic
de-collapse SURVIVES** (1.35/2.21/1.64×) but its **actor rise does NOT** (1.26/0.94/
0.63× — 2 of 3 lanes at or below pure geometry); at 50M the null alone gives critic
srank 14-164 vs control 7-10, so a raw rank contrast there is geometry; (3) **dormancy
is null-robust** (0.76→0.74) and is where the 50M pathology lives; (4) **50M win-rate
credit bar ≥0.6675 unconditionally**, above the best lane ever (s35 0.6593).

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| Self-play 12M control 0.3996 · Rung 1 SIGNAL NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 | 0.5509 ± 0.0052 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic 12M — NULL, falsifier-killed | 0.5364 ± 0.0066 |
| D23 regen-L2 12M — letter-met, NOT credited (s44 0.6463!) | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **MAINTAINER CALL — D19 or close.** The 50M carry is rejected on merit by all six
   agents (no branch changes a decision). **D19 AT 5 LANES = 2.24 lane-days measured**
   (D18's identical fleet shape) → chapter **15.8/20**, inside D17, no renegotiation.
   Credit needs 5 lanes: bar 0.5898 at s_T=0.036 vs D23's realized 0.5897 — it credits
   iff it beats D23 slightly, and the credit region is entirely above M4 (0.558). Needs
   its OWN authorization: the 08-13 overage was purchase-specific to the carry, now
   dead. If it runs: 2-Opus pre-reg first, dormancy-primary with a CALIBRATED letter.
1. **LEDGER AUDITED 08-13 — the recorded ~17 was ~3.5 HIGH.** Measured over all run
   dirs: 392.8 lane-hours, 67.9 pre-chase → **chase = 13.54, headroom ~6.5.** Drift was
   estimate-rounding, not lost runs. Future accounting: re-measure, never increment.
2. **§13 DEFECT:** it conditions 250M on "a credited lever at 50M"; none exists under
   today's line (Rung 3 stands era-graded) → restate or waive. Also CLAUDE.md's
   locked-eval line says 1000 battles/seed, DESIGN §8 says 3000 — fix.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free** (D19 would take 52-56). Rank reads: state as a MARGIN over the
  matched-distance null, never a raw contrast; `--tag` every rank pass.
- Entity ckpts need BOTH env vars. Eval auto-tie crash (~1-in-10⁴) can kill a lane;
  same-seed relaunch hits zombies — use a FRESH seed (s49→s51, log 08-12).
- Artifacts results/d23/, d24_design/, d24_null/ (gitignored). Suite 293 green (R0-3
  golden needs its own pytest process). Process: 2 Opus designers + 2 reviews per pre-reg.

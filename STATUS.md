# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D23 read out; the 50M carry designed, NO-GO as scoped)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT credited"** (BOUND,
gap-shrink realized, srank letter not met, falsifier NOT fired).
Rung-2 12M seed sd ≈0.036 → 12M win-rate primaries un-creditable. **CARRY DESIGN CYCLE
(2 designers + 2 reviews, 0 lanes, results/d24_design/): NO-GO AS SCOPED** — every
reachable verdict ends at the same action. Its findings, and the zero-lane work that
then LANDED (08-13): (1) `srank99=1` was a float32 NaN sentinel — tooling now float64
+ Gram fallback + hard fail + no-clobber; record re-derived (1 cell fixed, s36
critic@6M 1→19; D23's destroyed control pass regenerated, MATCHES the logged 11/17/16);
(2) **GEOMETRIC-NULL STUDY DONE** (results/d24_null/): at matched distance D23's
**critic de-collapse SURVIVES**
(1.35/2.21/1.64×) but its **actor rise does NOT** (1.26/0.94/0.63× — 2 of 3 lanes at or
below pure geometry); at 50M the null alone gives critic srank 14-164 vs control 7-10,
so a raw rank contrast there is geometry; (3) **dormancy is null-robust** (0.76→0.74)
and is where the 50M pathology lives; (4) **50M win-rate credit bar ≥0.6675
unconditionally**, above the best lane ever (s35 0.6593).

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

0. **(a) ZERO-LANE WORK IS DONE (08-13)** — tooling hardened, record re-derived, null
   study published (results/d24_null/SUMMARY.md). **RE-DECIDE THE CARRY** knowing rank
   letters must be margins over the matched-distance null and dormancy is the
   null-robust primary: (b) carry on the B-merged spine — cost UNRESOLVED, 4.4 vs 5.6
   lane-days, not the accepted "5.0"; (c) D19 at 12M ~1.5 lane-days, the only
   reachable credit; (d) close at ~17/20.
1. **§13 DEFECT:** it conditions 250M on "a credited lever at 50M"; under today's line
   none exists (Rung 3 stands era-graded) → restate or waive. Also: CLAUDE.md's
   locked-eval line says 1000 battles/seed, DESIGN §8 says 3000 — fix.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free** (a carry takes 52/53/54, 47-48 for crash replacement).
- Rank reads: state as a MARGIN over the matched-distance geometric null, never a raw
  treatment-vs-control contrast. `--tag` every rank pass (clobber guard).
- Entity ckpts need BOTH env vars. Eval auto-tie crash (~1-in-10⁴) can kill a lane
  (s49 at 7.2M → s51); same-seed relaunch hits zombies — use a FRESH seed (log 08-12).
- Artifacts results/d23/, d24_design/, d24_null/ (gitignored). Suite 293 green (R0-3
  golden needs its own pytest process — 1-ULP flake). Design process (08-12, standing):
  2 Opus designers + 2 Opus reviews per pre-reg.

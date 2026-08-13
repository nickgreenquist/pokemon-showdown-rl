# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D23 read out; the 50M carry designed, NO-GO as scoped)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (era-graded, seed sd 0.0756); D18
priv-critic NULL, falsifier-killed; D23 regen-L2 **"letter-met, seed-fragile, NOT
credited"** (BOUND, gap-shrink realized, srank letter not met, falsifier NOT fired).
Rung-2 12M seed sd is really ≈0.036 → 12M win-rate primaries are un-creditable at
advisory scale. **CARRY DESIGN CYCLE (2 Opus designers + 2 reviews, 0 lanes, docs in
results/d24_design/): NO-GO AS SCOPED** — every reachable verdict ends at the same next
action. Four zero-cost findings, two touching recorded results: (1) **`srank99=1` is a
float32 NaN sentinel**, one corrupt cell on disk (d22 effective_rank.csv, s36 critic@6M
reads 1, true 19); (2) **GEOMETRIC NULL** — pulling a control back toward its own init
reproduces ~50% of D23's srank de-collapse with NO training (D23's actor margin 1.21×)
→ every rank read needs a matched-distance null clause; (3) **dormancy is null-robust**
and is where the 50M pathology lives, while critic srank SATURATES 12M→50M; (4) **50M
win-rate credit bar ≥0.6675 unconditionally** — above the best lane ever, s35's 0.6593.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| Self-play 12M control (v2/808, flat MLP) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M (entity DeepSets ptr) — CREDIT | 0.5509 ± 0.0052 |
| Rung 2 comparator refresh (5 seeds, 2026-08-13) | 0.5445, sd 0.0356 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic 12M — NULL, falsifier-killed | 0.5364 ± 0.0066 |
| D23 regen-L2 12M — letter-met, NOT credited (s44 0.6463!) | 0.5897 ± 0.0066 |
| BC-of-FP clone graded final / val-peak = M4 bar | 0.5490 / 0.5777 ± 0.0090 |
| SH mirror parity 0.489 · FP engine 0.812-against* | clone h2h 0.643 pooled |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4: letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **MAINTAINER CALL — the carry is NO-GO as scoped** (chosen 08-13, before the
   un-creditability arithmetic existed). (a) ZERO-LANE first: fix the NaN sentinel +
   d22 CSV clobber, re-derive affected rank cells, publish the geometric-null study —
   free, and it decides whether any 50M rank read is meaningful; (b) run the carry on
   the B-merged spine (dormancy PRIMARY, rank ABOVE-NULL, relative capability floor,
   seeds 52/53/54) — cost UNRESOLVED, 4.4 vs 5.6 lane-days (3- vs 5-wide), not the
   accepted "5.0"; (c) D19 at 12M ~1.5 lane-days, the only place credit is still
   reachable; (d) close the chapter at ~17/20. **I recommend (a), then re-decide.**
1. **ROADMAP DEFECT:** DESIGN §13 conditions 250M on "a credited lever at 50M"; under
   today's larger-of line none exists (Rung 3's verdict stands as era-graded) and the
   carry cannot make one. §13(1) needs restating or an explicit waiver.
2. Fix CLAUDE.md's locked-eval line: it says 1000 battles/seed, DESIGN §8 says 3000.
3. Post-chase bundle: comparator-spread + geometric-null + D23 mechanism story.

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free** (a carry would take 52/53/54, 47-48 for crash replacement).
- **Quote no srank number until the float64 + NaN-hard-fail lands**; and
  `d22_dormant_rank.py` clobbers its own CSVs (it destroyed D23's control rank pass).
- Entity ckpts need BOTH env vars; D23 ckpts eval fine on the plain path.
- Eval auto-tie crash (~1-in-10⁴ evals) can kill a lane (s49 at 7.2M → s51); same-seed
  relaunch hits zombie battles — relaunch on a FRESH seed (log 08-12).
- Artifacts results/d23/ + results/d24_design/ (gitignored). Suite 293 green (R0-3
  golden needs its own pytest process — 1-ULP flake, logged).
- Design process (standing, 08-12): 2 Opus designers + 2 Opus reviews per pre-reg.

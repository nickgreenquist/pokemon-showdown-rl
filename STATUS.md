# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 — **D25-P READ OUT: BRANCH B1 UPGRADE**)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **D25 CREDITED 0.6185; ladder COMPLETE (M1-M4); and
the placebo arm has now WIDENED THE CLAIM.** Licensed sentence: *an explicit
opponent-action model helps* — with C3(b) self-model, C4 representational-only, and the
P3 dose caveat attached in the same breath. **NEVER "belief state".** The shuffled-label
placebo lands dead on the comparator (0.5415 vs 0.54452) while treatment reaches 0.6185.
50M CLOSED; D18 NULL; D23 not-credited.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo (shuffled labels) — FLAT on comparator, delta -0.0030** | **0.5415** |
| R-1 treatment vs placebo **+0.0770** vs 2·se 0.03471 — **CREDITS** | Δ +0.0770 |

## The D25-P grid (all reads in; `results/d25p/grade_placebo.txt`, `r4_manipulation.txt`)
- **R-1 CREDITS** +0.0770 (clustered se governs). **R-2 FLAT** -0.0030.
- **R-3(a) NOT FIRED** p=0.948 — placebo atoms +0.0071 BELOW controls' +0.0150; fraction
  -0.185 vs bar 0.333, so **the license does NOT narrow**. Rider: a silent (a) does not
  clear specificity below §5's MDE 0.0105-0.0301. **R-3(b) FIRED p=1/252.**
- **R-4 SHUFFLE CONFIRMED** (median g_P -0.0118, 0/5 rising, 4/5 TRAINED-TO-FLOOR) →
  **B7 does not fire.** **B6 does not fire** (R1 5/5).
- **R-5(a) NOT FIRED** p=0.778 (placebo MORE dormant than controls) → de-dormancy tracks
  the information. **R-5(b) FIRED p=1/252.**

## Next actions, in order
1. **MAINTAINER CALL — R-4 aggregator wording.** Median reads SHUFFLE CONFIRMED; the
   worst lane (s61, |g_P| 0.0226) reads RESIDUAL under max-governs. **The branch is
   identical either way** (both far below the 0.10 LEAK line); only the letter's wording
   moves. R-4 fixes the bands but never names the aggregator; §6's median was inherited.
2. **R-6 NOT RUN** (recorded-no-letters, optional, nothing depends on it): h2h
   placebo-vs-treatment, S3-P entropy vs band 0.212-0.284, S5-P/S7-P, dose curves.
3. **Push** — nothing pushed; commits sit on `main` (ask first). Next lever: DESIGN.md
   is the roadmap; §11 (search) is PROPOSED, not ratified.

## Watch items
- **THE DOSE CAVEAT IS PART OF THE CLAIM, not a footnote.** Placebo `aux/trunk_norm`
  ran at 3-31% of the frozen band, 12/12 bins DOSE-CAVEATED (bin 0 0.0137-0.0173 →
  bin 11 0.0011-0.0022 vs band 0.079-0.098). So R-2's flatness does NOT refute "a
  generic aux gradient of matched size would help" — untested, not eliminated.
- s61's NLL_head sits in the header's UNNAMED cell (A1+0.02, A1+0.05] — disclosed as
  NEAR-FLOOR, never folded into a neighbour.
- **R-5 needs `--s1-control results/d23/dormant_d25_control.csv`** for n_C=5; the
  default CSV has s26/s27/s28 only and the grader rightly refuses to grade at n_C=3.
- **Three DIFFERENT ctx metrics — do not conflate:** R-5 reads tau025; srank99 collapses
  on the placebo (s58 218→14) while dormancy stays high; "live ctx units" is a third.
- **Never read R0-8 off `time/steps_per_sec`** (mean 361 vs wall 312) — Δstep/Δruntime.
- **In-loop `eval/win_rate` (n=100) does NOT preview a locked number** — it said 0.576,
  the locked answer was 0.5415. Per-lane noise does not average out at 5 lanes.
- **`results/d25/` + `results/d25p/` are the ONLY copies** of the frozen tapes and grade
  artifacts; both now in `../pokemon-showdown-rl-d25-backup-20260815/` (verified).
- **LEDGER 17.91/20 chase lane-days** (re-measured 2026-08-16 across 78 lanes; D25-P
  cost 2.17). Re-measure, never increment.
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 47-48 held; 52-56 = D25;
  **57-61 = D25-P (SPENT)**; 62-63 never needed; 64+ free.

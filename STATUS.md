# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-14 evening — **D25 PRIMARY: CREDIT, pooled 0.6185**)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **D25 (opponent ACTION prediction, coef 0.1, 5
lanes s52-56) ran 12M clean and its finals CREDIT: pooled 0.6185, delta +0.0739 over
the frozen 0.54453, operative bar 0.58273 cleared by +0.036 under the larger-of
clause — the first credited lever since Rung 3, on a NON-advisory-scale effect.**
Claim scope is pre-registered: without the shuffled-label placebo (§12, YOUR call)
the claim is "an aux opponent-action loss helps", NOT "an opponent model helps".
50M chapter CLOSED; D18 NULL; D23 not-credited; the 50M CARRY REJECTED.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756) | 0.5802 ± 0.0052 |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited 0.5897 | — |
| **D25 oppact-aux 12M — CREDIT (bar 0.58273; s53 record 0.6573)** | **0.6185** |
| **D25 mech co-primary: LETTER at MIN p = 1/252, both label spaces** | Δ +0.0426 |
| BC-of-FP v2r clone at 5×3000: final 0.5503 / val-peak 0.5837 — both < D25 | — |
| **LADDER** M1/M2/M3 CLAIMED · **M4: BOTH obligations clear — bless it?** | 0.6185 |

## Next actions, in order (maintainer decisions at the top)
0. **ALL FOUR LETTER-BEARING READS LANDED FULL-SUCCESS (2026-08-14 night): PRIMARY
   CREDIT + co-primary B p=1/252 (both spaces) + §6 LEARNED (median g 0.7055, 2.1×
   bar, 5/5, trajectory rising) + S1 p=1/252. Falsifier does NOT fire. R0-16 done
   (controls s50 0.4896 / s51 0.4115). Transcripts/artifacts under results/d25/.**
1. **D25-P placebo: RATIFIED, BUILT, ALL GATES GREEN — LAUNCH-READY** (header
   RATIFIED 2026-08-15, P11 = 5-and-no-more; suite 354; R0-P2 dispositions in the
   log). Seeds 57-61, recipe = D25's; readout via `d25_grade.py --placebo`. **M4:
   bless?**
2. **M4 (ii) DISCHARGED (2026-08-15): s55 beats the clone 0.7190 pooled over
   orientations (0.854 det / 0.584 sampling, z +15.4)** — the anchor MOVED with the
   vs-SH number (Rung 2: 0.657 at 0.5509 → D25: 0.719 at 0.6073), so the jump is not
   SH-specific. **M4 is one formal blessing from claimed.**
3. **§6 manipulation check + S1/R0-16 — OWED, need per-lane tapes:** collect oppact
   tapes + obs (s52-56) and obs for s50/s51 (fleet is DOWN, safe); then g vs bar
   0.3286 (A1/A3 re-derived per lane, per-member oracle for the >1.0 hard fail) and
   dormancy CSVs → grader's S1 letter. **g for R0-10(a) stays "proxied" unless closed.**
4. **C10 SETTLED (2026-08-14): tapes exclude forced replacements BY CONSTRUCTION**
   (collector pairs non-forced-on-both-sides; 0 of 53,848 rows across 7 tapes); live
   loss included the double-faint ones at ~0.12%. Disclose at readout.
5. **LEDGER: chase 13.54 + this rung's 2.35 = 15.9/20**; re-measure, never increment.
6. R0-14/R0-15 DISCHARGED: `scripts/d25_grade.py` (20 tests, suite 339 green),
   attestation green vs frozen inputs (`results/d25/grade_primary.txt`).

## Watch items
- **Treatment live ctx units ~247 vs controls 111-170 on the same tape** — the lever
  de-dormantifies the trunk; record JOINTLY with the §5 letter, don't over-read (the
  control-side specificity r is -0.453, wrong sign to manufacture a positive).
- **`grad_clip_frac` ~0.99 mid-run is NORMAL** — the VOID clause's 0.90 is a WHOLE-RUN
  mean; compare at MATCHED STEPS or every lane voids, controls included.
- **results/d25/ IS THE ONLY COPY of the sha256-frozen tapes AND now the finals/grade
  artifacts** — losing it voids the mechanism co-primary.
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 47-48 held; **52-56 =
  D25 (SPENT)**; 57+ free. **The 808-vs-828 seam: v2/808 ckpts (the clone) eval in the
  808 process (V2=1, IDS unset); 828 ckpts need BOTH env vars — a mixed chain dies at
  load, measured tonight.** Quote the RANGE; MAX null to ESTABLISH, MEDIAN to RETIRE.

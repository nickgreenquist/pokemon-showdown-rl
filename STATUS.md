# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-14 — D25 LAUNCHED at coef 0.1, 5 lanes s52-56)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (seed sd 0.0756); D18 NULL; D23
regen-L2 "letter-met, seed-fragile, NOT credited"; the 50M CARRY IS REJECTED (bar
≥0.6675, above the best lane ever, 0.6593). **D25 (opponent ACTION prediction) is now
BUILT** (~230 lines, 26 tests, suite **319 green**) **and its zero-lane gates are RUN:
R0-12b, R0-13(a), R0-13(b) PASS; R0-10b's A1 amendment was REFUSED on review and the
ratio is measured LIVE instead; R0-10's four smoke arms ran and set coef 0.1.**

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)
| result | win rate |
|---|---|
| Rung 2 STRUCTURE 12M — CREDIT · 5-seed refresh 0.5445 (sd 0.0356) | 0.5509 |
| **Rung 3 50M finals — CREDIT (era-graded, seed sd 0.0756)** | **0.5802 ± 0.0052** |
| D18 priv-critic NULL 0.5364 · D23 regen-L2 not-credited | 0.5897 ± 0.0066 |
| BC-of-FP clone final / val-peak = M4 bar · SH mirror 0.489 | 0.5490 / 0.5777 |
| **LADDER** M1/M2/**M3 CLAIMED at 12M** · M4 letter-met at 50M | **NOT claimed** |

## Next actions, in order (maintainer decisions at the top)
0. **D25 IS RUNNING — 5 lanes, seeds 52-56, coef 0.1, ETA ~10.2 h from 2026-08-14 ~00:10.**
   Each lane is a DETACHED `screen` session: `screen -r d25_s52` (…s56), `ctrl-a d` to
   detach, `screen -ls` to list. Launch verified by battle PROGRESS (148k-185k steps,
   3.8k-4.9k episodes at first check), 314-325 steps/s wall 5-wide, R0-1 stamps correct
   on all five (`git_dirty: false`, `l6`, actor+aux 675,538). WATCH: R0-8 battle
   PROGRESS per lane (never "run dir exists"), R1 `selfplay/winrate_anchor` ≥0.75 by 4M
   (arm STOPS and records F5 NEGATIVE if <3 of 5 clear), K6 entropy, the VOID clause on
   `loss/grad_norm`/`grad_clip_frac`, and `aux/illegal_label_frac` == 0.
   **R0-10's rule was DEVIATED FROM, disclosed:** it says take the LARGEST passing arm
   (0.5), but condition (a) is flat across a 10× range (`aux/loss` 1.5312-1.5574, and g
   itself was NOT computed — proxied only) and condition (b) is NON-MONOTONE against the
   matched-step control band (0.05 in, 0.1 out, 0.25 in, 0.5 in), i.e. noise. What IS
   monotone: injection fraction and `aux/grad_clip_frac` (0.102 at coef 0.5 — the clip
   binds, so the declared coefficient stops being the effective one). 0.1 sits in
   D19-B's targeted 3-12% injection band and never clips. Full record: config §15C.
1. **YOUR CALL before launch: the shuffled-label placebo arm, +2.35 lane-days** (chapter
   → ~18.2/20) — "an explicit opponent model helps" vs "an aux loss helps".
3. **LEDGER: chase 13.54 + this rung's 2.35 = 15.9/20**; re-measure, never increment.
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
- **results/d25/ IS THE ONLY COPY of the sha256-frozen tapes** (gitignored, rescued from
  a job scratch dir) — losing it voids the mechanism co-primary.
- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 = the smoke; 47-48
  held for a D25 lane lost before R1; **52-56 = D25**; 57+ free.
- **Quote the RANGE, not the best variant.** **MAX null to ESTABLISH, MEDIAN to RETIRE.**
  `ctx` is max-pooled ⇒ estimators must be scorer-shaped. BOTH env vars, always. **Verify
  a launch by battle PROGRESS, never by what the launcher printed** (`setsid` is absent on
  macOS and printed five plausible pids for five dead lanes).

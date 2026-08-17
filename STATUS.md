# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 night — **D26 RUNNING: 4 lanes s62-65 since 21:05, ~08:00 finish**)
**Pure from-scratch self-play in gen1randombattle is the chase. The NOVELTY IS THE LANE,
not the levers** — proven technique inside it is fine (DESIGN §5:390); expert-data
bootstrapping is what's excluded. **D25 CREDITED 0.6185; placebo dead flat (0.5415), so
the INFORMATION did it; M1-M4 all claimed; C4 transfer FIRED, C4 discharged.** C3(b) and
the dose caveat remain; **NEVER "belief state"**. 50M CLOSED; D18 NULL (audit 08-16:
impl clean, null upheld); D23 not-credited; D19 KILLED (cap-mask correction stands).
`RESULTS.md` = the account. **Chapter-2 proposal DRAFTED: `DESIGN2.md` r1 (PROPOSED,
NOT ratified) — 2 Opus designs + 2 Opus reviews, 26 must-fixes folded in; process docs
in `results/design_ch2/` (only copies).**

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo — FLAT** Δ -0.0030; R-1 T-vs-P Δ **+0.0770** CREDITS | **0.5415** |

## Next actions
1. **D26 readout ~08:00 2026-08-17**: grade with the committed grader per the header's
   Q6; the headline moves ONLY on B1 (credit); the modal outcome is FLAT and a FLAT
   licenses nothing (interval would not exclude the lever's own +0.0277). Required
   delta +0.025..+0.053; P(CREDIT) 0.23-0.39 typical, 0.60-0.75 if s_T lands low.
   Verify lanes by battle PROGRESS, never run-dir existence.
2. **D26 throughput note**: indicative 4-wide fleet median ~311.8 steps/s (ckpt mtimes,
   200k-600k) vs the D-D band 320-350 — re-read at the gate's own ≥30-min warm window
   after 1M; **thresholds remain 275/230 until that compliant read** (DESIGN2 §8).
3. **DESIGN2.md decision points (its §7)**: the tranche (full chapter ≈9.0 ld takes the
   ledger to ≈28.6 vs the 20 cap — a new tranche is the ask); re-open the closed 50M
   line + the §13(1) ruling; D30's S-A vs S-B legality channel; D29-vs-D30 order.
   Stage-0 zero-lane work is free (DESIGN2 §6); the two small code patches are HELD
   until the D26 fleet finishes.
4. **D27 IS DEAD** (zero lanes; mechanism `RESULTS.md` §5) — never re-propose a
   rescaled shuffled-label placebo. **D18 audited post-hoc 2026-08-16: zero defects,
   null upheld, do not revisit** (SESSION_LOGS 2026-08-16 audit entry).
5. **Maintainer:** DESIGN §8 D7(a) defers the ladder eval "until M2/M3" (now satisfied)
   while CLAUDE.md forbids it. Two ratified docs contradict; one must move.

## Watch items
- **THE DOSE CAVEAT stands** ("untested, AND this control cannot test it") — DESIGN2's
  D28 is the designed closure; its unified dose gates are the load-bearing part, and
  what a D28 null does NOT close is pre-written in DESIGN2 §1.
- **README error bars are BINOMIAL; the seed-clustered se governs**, 2.66x larger.
- **Never read throughput off `time/steps_per_sec`** (measured 14.5% overstatement);
  use Δstep/Δwall. In-loop `eval/win_rate` (n=100) does not preview a locked number
  (0.576 vs 0.5415).
- **`results/d25/ d25p/ d19_closeout/ c4_transfer/ design_ch2/` are the ONLY copies**;
  the first four are backed up at `../pokemon-showdown-rl-d25-backup-20260815/`;
  `design_ch2/` is NOT yet backed up.
- **No DESIGN §11**; LEDGER 17.91/20 → ~19.7 after D26. Seeds: 62-65 = D26, 66/67
  held, 68+ free (DESIGN2 §5 plan: 70-74 / 80-84 / 90-92, spaced, held pairs). vs-SH
  0.6185 is still ~40% GXE — nothing here is "nearly solved".

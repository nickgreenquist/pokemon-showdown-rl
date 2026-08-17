# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-17 AM — **D26 READ OUT: B1 CREDIT 0.71825. NEW HEADLINE.**)
**Pure from-scratch self-play in gen1randombattle is the chase. The NOVELTY IS THE LANE,
not the levers** (DESIGN §5:390); expert data excluded. **Recipe now: entity arch +
oppact aux head + LR anneal = 0.3996 -> 0.5509 -> 0.6185 -> 0.71825** (D26: 4x3000,
delta +0.0998 vs frozen D25, floor bar governs at s_T 0.0112, perm p 1/126, D-A LR
trace 12/12, K6/R1/R0-4 clean; RESULTS.md §9). **+0.0998 is 3.6x the estimate — WHY is
OPEN** (6M-transfer underestimate? anneal x aux interaction?), recorded not narrated.
D25's dose caveat + C3(b) remain; **NEVER "belief state"**. 50M CLOSED; D18 NULL (impl
audit clean); D23 not-credited; D19 KILLED. `RESULTS.md` = the account. **Chapter-2:
`DESIGN2.md` r2 (PROPOSED). Stage-0: D30 KILLED (Z3-3: soft labels = 0.2-1.8% of head
signal); Z1-1 VOID as screen (D28 dose in-run only, 6M abort 0.35 calibrated). D28's
caveat logic unaffected by D26; its 0.6185-era narrative is stale against 0.71825.**

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo — FLAT** Δ -0.0030; R-1 T-vs-P Δ **+0.0770** CREDITS | **0.5415** |
| **D26 +LR anneal 12M — B1 CREDIT 08-17** (bar 0.64344; s62-65, 4x3000) | **0.71825** |

## Next actions
1. **Maintainer: review the D26 credit, then push.** Grade transcript + finals:
   `results/d26/` (only copy, backed up); grader `scripts/d26_grade.py` (R0-I owed it —
   the handoff's "committed grader" did NOT exist; written at readout BEFORE any final
   was read). Suite re-run before push is cheap and owed (new script only).
2. **DESIGN2.md §7 decisions, now against 0.71825**: (a) authorise D28 (2.16 ld, a new
   tranche — ledger ~19.7/20 is spent); its frozen-comparator caveat logic is
   unaffected by D26. (b) The 50M/§13(1) ruling; note any 50M carry is now a question
   about the FULL credited stack (DESIGN2 §2's pre-stated anneal-off rule needs a
   maintainer revisit given B1). D30 is DEAD (Z3-3). The two held code patches
   (delivered-dose logging; train.py anneal guard) may now land — fleet is done.
3. **D27 IS DEAD; never re-propose a rescaled shuffled placebo. D18 audited 08-16:
   zero defects, null upheld, do not revisit.** (SESSION_LOGS entries.)
4. **Maintainer:** DESIGN §8 D7(a) defers the ladder eval "until M2/M3" (satisfied)
   while CLAUDE.md forbids it. Two ratified docs contradict; one must move — and at
   0.71825 the "what does this convert to" question is getting harder to defer.

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

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-19 overnight — **D29r READ OUT: PRIMARY VOID by lane loss;
headline stays D26 0.71825**)
**Pure from-scratch self-play in gen1randombattle is the chase; THE NOVELTY IS THE LANE,
not the levers** (DESIGN §5:390); expert data excluded. **Recipe: entity arch + oppact
aux head + LR anneal = 0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26, 12M, CREDITED).**
**D29r (stack at 50M, seeds 90-92): s90 DIED at 35.0M** (poke-env strict ValueError,
mask/valid-orders listener race, ~turn-1000 stall battle) → lane-failure rule →
**2 survivors → PRIMARY VOID, R-A AND R-B UNREAD** (`scripts/d29_grade.py`, attest
PASS). Surviving finals, individual, NEVER pooled: **s91 0.73267, s92 0.75133** —
both above 0.71825, recorded as observations, not credits. Diagnostics: D-A 16/16,
D-C/D-D PASS, R0-4 exact, mask_desyncs 0; K6 unreadable (3-lane median, one dead);
aux/loss prediction missed GOOD (predicted >0.81 plateau; fell to 0.645/0.574).
**Mask-desync hardening LANDED** (2-Opus reviewed, commit 9ac445d): the s90 crash
class can no longer kill a run; residuals (assert window, hangs, RESUME) recorded in
results/design_ch2/mask_desync_fix_memo.md. **NEVER "belief state"**; D18 NULL; D27
dead; D30 KILLED (Z3-3); Z1-1 void as screen. `RESULTS.md` §9-10 = the account.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** · placebo FLAT 0.5415 | **0.6185** |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (4×3000, +0.0998, p 1/126) | **0.71825** |
| D29r stack 50M — **PRIMARY VOID** (s90 died 35M); s91/s92 individual | 0.7327 / 0.7513 |

## Next actions
1. **Maintainer: review the D29r VOID record + the mask-desync hardening, then push.**
   Artifacts: `results/d29/` (only copy, backed up); grade transcript in SESSION_LOGS
   2026-08-19; hardening memo + 2 reviews in `results/design_ch2/maskfix_*`.
2. **Maintainer decision — what buys the 50M answer:** (a) fresh pre-registered
   3-lane re-run of the stack at 50M (new tranche ~4.5 ld; seeds per DESIGN2 §5,
   never seat 90; now protected by the desync fix), or (b) straight to **D28**
   (zero-info control, ~2.2 ld, queued; build specified in DESIGN2 §1 +
   results/design_ch2/ memos). The two individual 0.73+/0.75+ finals are evidence the
   stack scales, but nothing credits without 3 surviving lanes.
3. **Resume-from-checkpoint is the OPEN resilience item** (maintainer bar: never lose
   24+ h again; the cap/recovery landed, resume is what would have saved s90's 35M).
4. **Maintainer:** DESIGN §8 D7(a) vs CLAUDE.md ladder-eval contradiction stands; at
   0.71825+ the GXE question presses harder still.

## Watch items
- **THE DOSE CAVEAT stands** (D28 is the designed closure; what a D28 null does NOT
  close is pre-written in DESIGN2 §1). D26's 3.6x-estimate anneal surprise still OPEN.
- **README error bars are BINOMIAL; the seed-clustered se governs** (2.66x larger).
- **Never read throughput off `time/steps_per_sec`** (14.5% overstatement measured);
  Δstep/Δwall from ckpt mtimes only.
- **`results/d25/ d25p/ d19_closeout/ c4_transfer/ design_ch2/ d26/ d29/
  struct50m_finals/` are the ONLY copies**; all backed up at
  `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11**; ledger: ch-1 ~19.7/20 spent; D29r tranche ~4.2 ld realised.
  Seeds: 90-92 burned (90 died; never relaunch on a dead seat), 93/94 held, DESIGN2
  §5 plan 70-86. vs-SH 0.75 is still ~40% GXE — nothing here is "nearly solved".

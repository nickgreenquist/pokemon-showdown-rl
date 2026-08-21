# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-20 night — **D29r2 READ OUT: R-A CREDIT, R-B FLAT; the
50M question is ANSWERED; headline stays D26 0.71825**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers** (DESIGN §5:390); expert data excluded. **Recipe: entity arch + oppact aux +
LR anneal = 0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).**
**D29r2 (50M re-run, s80-82, zero incidents): pooled 0.70222** — **R-A CREDIT** vs
struct50m 0.58022 (+0.12200 over bar 0.11361; NAMED CELL — lanes do not fully
separate, s82 0.6297, perm 2/20; sentence attaches to every quote) · **R-B FLAT** vs
D26 (-0.016; 4.17x compute adds NOTHING on top — decision-grade §13 futility input).
**5-lane descriptive (pre-declared): 0.71813 ± 0.02236 over both 50M fleets** — the
recipe sits at ~0.72 at 12M and 50M alike. D29r itself: VOID (s90 died 35M);
s91 0.73267 / s92 0.75133 individual. Crash class FIXED (9ac445d, mask_desyncs 0
across 9000 final battles). aux/loss pool-hardening prediction 0-for-5 — retired.
**NEVER "belief state"**; D18 NULL; D27/D30 dead. `RESULTS.md` §9-11 = the account.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (4x3000, +0.0998, p 1/126) | **0.71825** |
| D29r 50M — VOID (s90 died); s91/s92 individual | 0.7327 / 0.7513 |
| **D29r2 50M re-run — R-A CREDIT (named cell) / R-B FLAT** (s80-82) | **0.70222** |
| All five 50M lanes, descriptive only (pre-declared 08-19) | 0.7181 ± 0.0224 |

## Next actions
1. **Maintainer: the §13(1) ruling is now LOAD-BEARING.** R-A gives the "credited
   at 50M" candidate (as a STACK — the wording ruling decides if it counts) while
   R-B FLAT argues the 250M line buys nothing at this recipe. Both recorded,
   RESULTS §11. Decide: pursue §13/250M, or accept saturation and pivot.
2. **D28 (zero-info dose control, ~2.2 ld) is the queued next arm** — build spec in
   DESIGN2 §1 + results/design_ch2/ memos; seeds 70-74 (75/76 held). Closes D25's
   dose caveat regardless of the §13 decision. Say go and I prep the config+grader.
3. **Maintainer: review + push** (readout commit local; prior 11 pushed 08-19).
4. Standing: DESIGN §8 D7(a) vs CLAUDE.md ladder-eval contradiction; resume-from-
   checkpoint (the 24h-loss bar, run-loss-tolerance memory) — design on request.

## Watch items
- **The R-A credit is a NAMED CELL** — never quote it without the non-separation
  sentence; the two-lever attribution disclaimer stands (STACK, not lever).
- **THE DOSE CAVEAT stands** (D28 is the designed closure; what a null does NOT
  close is pre-written in DESIGN2 §1). D26's 3.6x anneal surprise still OPEN.
- **README ± are BINOMIAL except the ‡ row; the seed-clustered se governs verdicts.**
- **Never read throughput off `time/steps_per_sec`** (14.5% overstatement); use
  Δstep/Δwall off ckpt mtimes.
- **`results/d25 d25p d19_closeout c4_transfer design_ch2 d26 d29 d29r2
  struct50m_finals` are the ONLY copies**, all backed up at
  `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11 in DESIGN.md** (RESULTS §11 exists and is fine). Ledger: ch-1
  ~19.7/20; D29r+D29r2 tranches ~8.8 ld realised. Seeds: 80-92 burned/held per
  SESSION_LOGS 08-19; 70-74 reserved for D28. vs-SH ~0.72 is still ~40% GXE —
  nothing here is "nearly solved".

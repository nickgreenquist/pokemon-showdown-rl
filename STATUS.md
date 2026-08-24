# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25/26 — **FP-GAP DESIGN CYCLE (option C) ran
end-to-end: 2 Opus memos -> synthesis -> 2 adversarial reviews -> revised
pre-reg. CH4 R1 "off-SH instrument" is DRAFT r2 at
configs/eval/ch4_r1_offsh_instrument.yaml, COMMITTED, AWAITING RATIFICATION +
brackets MU-1..MU-11b (results/design_fp_gap/ch4_synthesis.md §7.3). Nothing
launched. Key cycle findings: memo B's Bradley-Terry fit says the h2h board is
transitive to ±0.03 EXCEPT the clone (we over-beat it +0.11 pooled) and FP's
take off D26 is BELOW prediction — "FP exploits D26" excluded ~95% on banked
data; D22 read 5 already refuted the exploitability pathology (BR 0.4765,
never parity); the P2 rider is TOO WEAK as banked (non-transfer is z~-2.9 on
FP, -6.0 on clone vs BT-commensurate transfer; supersede pending MU-8); the
brief's "oppact head fixes the switch column" is NOT implementable (C7 is the
bench TARGET, matrix.py:103-114). CH3 remains CLOSED; R5b B5+KILL stands.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
Recipe: entity arch + oppact aux + LR anneal = 0.71825 (D26 12M, CREDITED
HEADLINE). R2 search@M B1 CREDIT 0.79283 BEST (SH-facing caveat). Search is
REAL and INFERENCE-ONLY (T-GATE +0.1515 mirror; distilling it = B5+KILL).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing, P2×2)** | **0.79283** |
| R5b ExIt distill: B5+KILL (delta -0.0545, 4/4 neg); actor ExIt CLOSED | — |
| s65 anchors: clone greedy/search 0.894/0.860 · FP@100 greedy/search 0.388/0.368 | — |
| FP budget ladder (no gradient): FP@20 0.312 · FP@100 0.388 · FP@500 0.332 | — |

## Next actions
1. **Maintainer: ratify (or amend) CH4 R1 DRAFT r2 + rule the brackets.**
   Headline brackets: MU-1 off-SH credit line (conditional on s_T; depends on
   MU-9 two-vs-three-term); MU-3 confirm agent-side eval-wave precedent
   (~10.3 h battles serial, 0 terminal); MU-4 pre-commit the no-anomaly
   action (a/b/c) BEFORE readout; MU-10 Ch-3 sentence on R2 (A: untouched,
   B: correct); MU-11 tau-DIV dispute; MU-11b optional X-PROBE (3.6 h).
2. On ratification: BI-1..BI-8 build, then waves V -> A -> B -> C per the
   wave plan. Lever designs banked: A's EXPL (design_input_A.md §2/§7B),
   B's tau-DIV/POOL-SPAN (design_input_B.md §2). Ladder stays DEFERRED.
3. Commits after 60d73fc remain unpushed — ask before pushing.
## Watch items
- **Never quote 0.81200 as a best (B3). Never quote T-GATE numbers as vs-SH
  strength.** Oracle-diag numbers BARRED (log-only).
- CH4 R1 is NON-CREDITING; anchors stay descriptive; no anchor number is a
  "best". FP numbers always "FP + our patches" with budget named.
- The banked P2-rider sentence ("FP anchor carried ~no information") is
  PENDING SUPERSESSION (MU-8) — do not re-quote it without the BT re-grade.
- R5b D-9 switch rates 0.143-0.197 include force-switch rows (~+0.09
  definitional) — recompute (BI-8) before using as a style baseline.
- Paired se governed R4; unpaired governed T-GATE; sd(d_i) 0.016-0.033.
- Named-file reads only; bash 3.2; encoder env vars NOT exported to the
  whole suite; F-U compares FULL quoted usernames.
- results/ dirs are the ONLY copies; design_fp_gap (8 files) + earlier
  cycles mirrored to ../pokemon-showdown-rl-d25-backup-20260815/. Seeds
  66/67, 75/76, 83/84, 93/94 all HELD (CH4 R1 burns none). vs-SH ~40% GXE.

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **CH4 R1 RATIFIED (by delegation),
AMENDED RESULT-BLIND (A1), AND HALF-EXECUTED. 5 of 14 arms banked; the
remaining 9 (~7.0 h) are HANDED TO THE MAINTAINER'S TERMINAL — one
resume-safe command, below. Already settled and NOT dependent on the
remaining battles: SH-side era pin PASS (in-session 0.71508 vs banked
0.71825); the FRESH FP@20 HUB H1 = 0.82133 (n=3000); G6b style
equivalence PASS (FP@20 plays like FP@100); NO P-CELL FIRES and none is
close; E-b says our low-switch style is a POLICY property; and E-c
resolved AGAINST the style story — our own search seat already switches
MORE than FP (0.189 vs 0.137-0.146) and the h2h got WORSE (0.388 ->
0.368). The tape half of VERDICT-A points at NO MECHANISM; the BT half
(rho) needs the four L arms.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
D26 12M = 0.71825 (CREDITED HEADLINE). R2 search@M = 0.79283 (B1 CREDIT,
SH-facing caveat). Search is REAL and INFERENCE-ONLY (R5b B5+KILL). CH3 CLOSED.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing, P2×2)** | **0.79283** |
| R5b ExIt distill: B5+KILL (delta -0.0545, 4/4 neg); actor ExIt CLOSED | — |
| CH4 R1 V-arms in-session vs SH (era pin PASS) | 0.71508 |
| CH4 R1 H1 — FP@20 vs SH, the fresh hub (n=3000) | 0.82133‡ |
| s65 anchors: clone 0.894/0.860 · FP@100 0.388/0.368 · ladder 0.312/0.388/0.332 | — |
‡ FP's take, not ours. Never quote an anchor number as a "best".

## Next actions
1. **RUN THE REMAINING WAVE** (maintainer's terminal; resume-safe —
   re-invoke freely, completed arms are skipped):
   `caffeinate -is bash /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/scripts/ch4_r1_wave.sh`
   Needs the Showdown server up on :8000. Order: H2, L62-L65, C1, C1b,
   S1, E1. ~7.0 h at H1's measured 1.20 s/battle; the four L arms
   (~4.0 h) alone carry s_T and rho.
2. Then: `python scripts/ch4_r1_grade.py` -> results/ch4_r1_offsh/
   r1_readout.json (emits VERDICT-I + VERDICT-A + the original r2
   partition). Then readout, README Chapter-4 note, mirror.
3. `pytest tests/` is OWED — deferred while battles ran (CPU contention
   would starve FP's time-budgeted search and bias the arms).
4. Commits after 60d73fc remain unpushed — ask before pushing.
## Watch items
- **CH4 R1 is NON-CREDITING on every branch.** Amendment A1 (result-blind,
  structure-only) travels with every quote: VERDICT-I (instrument) and
  VERDICT-A (anomaly) are orthogonal and both are always reported.
- Never quote 0.81200 as a best (B3); never quote T-GATE numbers as vs-SH
  strength. Oracle-diag numbers BARRED (log-only).
- The banked P2-rider sentence is PENDING SUPERSESSION (MU-8 ruled
  SUPERSEDE; the grader emits it) — do not re-quote the old form.
- R5b D-9 switch rates 0.143-0.197 include force-switch rows; the true
  policy rate is 0.060-0.097 (BI-8, results/ch4_r1_offsh/sp_baseline.json).
- Archaeology is SCREEN-GRADE: it may SELECT among pre-named levers only.
- Named-file reads only; bash 3.2; encoder env vars NOT exported to the
  whole suite; F-U compares FULL quoted usernames.
- results/ dirs are the ONLY copies; design_fp_gap + ch4_r1_offsh JSONs
  mirrored to ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67,
  75/76, 83/84, 93/94 all HELD (CH4 R1 burns none). vs-SH ~40% GXE.

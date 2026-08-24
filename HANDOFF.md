# Handoff — 2026-08-25 (session close, maintainer-requested)

Written at the maintainer's explicit instruction ("after you close up
this session, handoff md so I can clear context and fresh context starts
back up with C"). Box idle, server healthy on :8000, tree clean and
committable, everything mirrored to
`../pokemon-showdown-rl-d25-backup-20260815/`. Pushed through `60d73fc`
this morning (maintainer-authorized); the session-close commits AFTER
60d73fc are UNPUSHED — ask before pushing them.

READ STATUS.md, then the three 2026-08-25 SESSION_LOGS entries (STOP →
amendment+readout → closure). Headline of the block: **CH3 IS CLOSED.
R5b read out B5 + KILL — compiling search into the weights made every
lane WORSE vs SH (delta −0.0545, 4/4 negative); the actor
expert-iteration family is closed; search@M stands as a REAL,
INFERENCE-ONLY lever (0.793 vs SH with the SH-facing caveat; T-GATE
mirror margin +0.1515). README carries a "Chapter 3, closed" narrative
section and the full additive row with every disclosure (Amendment A1,
C7 switch-bias materialized, F-P 0.78–0.80 pairing disclosure).**

THE NEXT SESSION STARTS OPTION C — the FOUL-PLAY-GAP DESIGN CYCLE
(ruled "a then c, skip b"):
- Question: why does the agent lose off-anchor (FP h2h 0.388 greedy,
  0.368 search@M) and what lever moves off-SH strength?
- Process: the standing 2-Opus design discipline (two independent design
  agents → synthesis → two adversarial reviews → revision → maintainer
  rulings) BEFORE anything runs. Nothing launches without a ratified
  pre-reg.
- Evidence to seed the design agents (all banked, pointers in the
  2026-08-25 entries): search increments are SH-FACING (R2 P2
  falsifier); C7 switch-column bias now measured AT THE POLICY LEVEL
  (distilled switch rates ~doubled and tracked the losses); FP budget
  ladder NO-GRADIENT; U9 T2b contamination flag still open; D-8 settled
  |v_LOO−v_own| ≈ 0.05–0.07 (critic disagreement small); critic NOT
  rank-collapsed (srank99 ~47/384). Oracle-diag numbers stay BARRED
  (log-only).
- SKIPPED (shelved, not killed): design A's critic-value family
  (design_input_A.md, complete and priced) and the R4 follow-ups.
- Ladder stays DEFERRED until models are exhausted vs SH + FP anchors
  (2026-08-23 ruling).

FRESH LANDMINES/FACTS from this block (all logged): the encoder env vars
must NOT be exported to the whole test suite (8 default-encoder tests
fail by design; canonical B-3 run is bare `pytest tests/`); the runner's
F-U check must compare FULL quoted usernames (the shared 'ShowdownSing'
prefix false-fires a token-based check — fixed in ch3_r5b_run.sh);
usernames are per-process entropy (no set_seed in any eval path), so
same-cfg paired lanes do not collide; the r5a readout exists under BOTH
names (r5a_readout.json and the pre-registered t_gate_readout.json,
byte-copies); Amendment A1 lives at the bottom of
configs/eval/ch3_r5b_exit.yaml — any future quote of R5b carries its
disclosure obligation verbatim; the 30 s wave stagger yields F-P overlap
just under 0.80 on ~6-min jobs (pre-launch either shrink the stagger or
accept the disclosure).

R5b artifacts if ever needed: dataset results/ch3_r5b/collect (494,603
rows, 58M), distilled+placebo checkpoints runs/exit_* (D-5-clean,
stamped), readout results/ch3_r5b/r5b_readout.json, era pin
results/ch3_r5b_era_pin. All mirrored.

Fold this back to the empty stub on pickup.

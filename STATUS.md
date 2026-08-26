# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **LADDER R1 COMPLETE AT n=200; the
pre-registered PRIMARY read is UNMEASURED.** 95-105 (0.475); PS Elo 1000 ->
**1311** (peak 1348) vs a top-500 cutoff of 1357; 141 opponents; 12.07 h.
**NEVER LISTED, so GXE/Glicko DO NOT EXIST — quote the Elo, never project
one.** Gates green; obligations -> `LADDER_R1_READOUT.md`.)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
R2 search@M is a B1 CREDIT but SH-facing/INFERENCE-ONLY. CH3+CH4-R1 CLOSED.

## Results | D26 12M HEADLINE **0.71825** vs SH · R0 ensemble 0.74633 · D29r2
50M 0.70222 · **R2 search@M 0.79283** (B1 CREDIT, SH-facing) · **LADDER R1
n=200 DESCRIPTIVE, PS Elo 1311, 0.475, NO GXE** · off-FP@20 (12M lanes only)
0.342/0.355/0.356/0.342. Ties=loss; locked = final ckpt.

## Next actions (2026-08-26 evening — REORDERED after the maintainer
challenged "scale is flat"; the challenge held, see that day's log)
1. **MEASURE BEFORE TRAINING. Three ZERO-TRAINING reads, all gated on the same
   off-SH seat (item 2):** (a) **D29r2's 50M lanes s80/81/82 vs FP@20** — "50M
   is FLAT" is vs-SH ONLY and no 50M stack lane was EVER measured off-SH;
   (b) **search@M on the 50M checkpoints** — inference-only, ran only on
   `recipe12m_s62..s65`; "it failed because the net wasn't saturated" is untested
   and free to test; (c) **a wider ensemble** — 4 lanes now, 6 more idle.
2. **BUILD THE OFF-SH SEAT — the gate on all of item 1.** (a) `ch3_fp_h2h.py`'s
   `ARM_KINDS` has no `ensemble` and asserts on it; (b)
   `eval_checkpoint._opponent_from_checkpoint` seats a PoolPlayer that SAMPLES =
   the A1 bias — use `SeatPlayer`. **Yardstick: FP@20 PRIMARY, vs-SH a guard.**
3. **THEN pick the training lever, with item 1 in hand.** Candidates, none
   ratified: more seeds (the 0.630-0.742 spread makes seed count a real lever);
   longer runs; H&L `hl_shaping: 1.0` + `gamma: 0.95` on the entity trunk (never
   tested there, but POST-HOC, ~1 in 4); attention / temporal context; the
   encoder fork LAST (it invalidates every checkpoint).
## Watch items
- **"SCALE IS FLAT" IS A vs-SH-ONLY CLAIM — DO NOT QUOTE IT UNQUALIFIED.**
  D29r2 50M vs SH: 0.7423 / 0.7347 / **0.6297** -> pooled 0.70222, i.e. **2 of
  3 lanes BEAT the 12M pooled 0.71825**; one lane drags the mean. **The one 50M
  arm ever measured off-FP went the OTHER WAY**: struct12M 0.176 off FP@100,
  struct50M **0.188** (n=250 each, +0.012, se_diff 0.035 — n.s., sign positive)
  while the same step read +0.029 vs SH and CREDITED. **No D29r2 lane has ANY
  off-SH number.**
- **ATTENTION: the 34.6x was measured against the FLAT [512,512] MLP**, no
  longer production; attention-vs-`entity_deepsets` has NEVER been measured
  (minutes to do). The 08-25 review ruled on CAPACITY, not structure, and named
  **temporal context** (we are single-snapshot Markov) the SHARPER gap.
- **WE ARE IN THE STYLE TABLE (`scripts/replay_audit/our_style.py`).** Sum-
  |delta| from the human field: **US 0.095, SH 0.095**, clone 0.124. **Gross
  move errors: us 0.6% vs humans 2.7%** (1.88 vs 7.20% given a known better
  move) — nothing for a blunder mask to filter; style is NOT the gap. TOTAL
  switch rate is at PARITY (27.2/28.6); only the VOLUNTARY cut differs
  (6.9/10.7) — ours are REACTIVE.
- **ENCODER DEFECT HAS A PARTIAL ROUTE-AROUND:** `move_emb` is a learned
  `nn.Embedding(166, 64)` in every move token, so "cannot route around
  `basePower == 1`" is too strong — misleading, not unrepresentable, ~1% of
  decisions. NOT DONE; invalidates every checkpoint, so it goes LAST.
- **THE CRITIC IS FINE, NOT SH-SPECIFIC** (n=300/opp): AUC 0.704 -> 0.891 by
  material, BETTER vs the FP clone. NOT a value-shape problem.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED**; 3 copies via
  `scripts/backup_ladder.sh`. **13 commits UNPUSHED — ask first.**

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **LADDER R1 COMPLETE AT n=200; the
pre-registered PRIMARY read is UNMEASURED.** 95-105 (0.475); PS Elo 1000 ->
**1311** (peak 1348) vs a top-500 cutoff of 1357; 141 opponents; 12.07 h.
**NEVER LISTED, so GXE/Glicko DO NOT EXIST — quote the Elo, never project
one.** Gates green; obligations -> `LADDER_R1_READOUT.md`.) **Pure
from-scratch self-play; THE NOVELTY IS THE LANE.** CH3+CH4-R1 CLOSED.

## Results | D26 12M HEADLINE **0.71825** vs SH · R0 ensemble 0.74633 · D29r2
50M 0.70222 · **R2 search@M 0.79283** (B1 CREDIT, SH-facing) · **LADDER R1
n=200 DESCRIPTIVE, PS Elo 1311, 0.475, NO GXE** · off-FP@20 (12M lanes only)
0.342/0.355/0.356/0.342. Ties=loss; locked = final ckpt.

## Next actions — **`CHAPTER5.md` IS THE CHAPTER DOC. SHAPE RATIFIED
2026-08-26; **50M IS THE HARD CEILING** (no 100M/120M/250M). Pre-regs NOT
written and they owe the 2-Opus cycle. Summary:
1. **MEASURE BEFORE TRAINING. Three ZERO-TRAINING reads, gated on the off-SH
   seat (item 2):** (a) **D29r2's 50M lanes s80/81/82 vs FP@20** — "50M is
   FLAT" is vs-SH ONLY and no 50M lane was EVER measured off-SH; **if it reads
   positive the better model is ALREADY ON DISK and R2 training is optional;**
   (b) **search@M on the 50M checkpoints** — inference-only, ran only on
   `recipe12m_s62..s65`, so "it failed from under-training" is free to test;
   (c) **a wider ensemble** — 4 lanes now, 6 idle.
2. **OFF-SH SEAT: BUILT AND GATED 2026-08-26.** `ensemble_seat` is in
   `ARM_KINDS`; `scripts/ch5_seat_equiv.py` proves **0 disagreements over 2000
   states** vs `ladder.py`'s path, so an L2 off-SH number rates the object
   that laddered. **Network smoke NOT run** (needs server + FP build).
3. **THEN pick the training lever from CHAPTER5 §5's branch table.** The
   maintainer's six stay first-class (§3 provenance table); assistant additions
   (§3b) COMPETE, never displace. Encoder fork LAST — it invalidates every ckpt.
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
- **THE CRITIC IS FINE, NOT SH-SPECIFIC**: AUC 0.704 -> 0.891 by material,
  BETTER vs the FP clone (n=300/opp). NOT a value-shape problem.
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED**; 3 copies via
  `scripts/backup_ladder.sh`. **5 commits UNPUSHED (this session only;
  origin/main = 3bdb2a3, so the handoff's "13" is STALE). Ask before push.**

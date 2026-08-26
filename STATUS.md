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
1. **MEASURE BEFORE TRAINING, zero training. C0 = L2 off FP@20 RUNS FIRST**
   (both designers, independently: **L2 has NO FP number at any budget**, so
   the repo holds ZERO (proxy, ladder) pairs — CHAPTER5 §1 claimed one).
   Then the 50M lanes off FP@20, search@M on 50M, a wider ensemble.
   **"50M is FLAT" is not a weak claim, it is NOT A CLAIM — 0.44 se against a
   0.0735 bar** (50M vs-SH sigma_seed 0.0624 = 8.2x the 12M 0.0076).
2. **SEAT: BUILT, GATED, SMOKED.** `ch5_seat_equiv.py` 0 disagreements/2000
   states vs `ladder.py`; real FP@20 runs 0 desyncs, 0 relaunches, **G2
   exact**. **PRICED by calibration: ensemble 1.60 s/b, search 2.68 (my n=20
   3.51 and a designer's 4.55 model were BOTH high) -> R1 ~6.9 h.**
3. **R1 PRE-REG `configs/eval/ch5_r1_offsh.yaml` IS r2 AND NOT LAUNCHABLE.**
   2 designers + 2 reviews; **10 blockers, 5 fixed, 5 OPEN** (its
   BLOCKERS-OPEN block: Q5 has no action column; Q5 grades 1 of 3 reads;
   k<3 unnamed; ABOVE may be unreachable; dropped gates undispositioned).
4. **THEN the training lever from CHAPTER5 §5.** Maintainer's six stay
   first-class (§3); assistant additions (§3b) COMPETE. Encoder fork LAST.
## Watch items
- **"SCALE IS FLAT" WAS NEVER ESTABLISHED, ON EITHER AXIS.** 50M vs SH is
  0.7423/0.7347/**0.6297** — **2 of 3 lanes BEAT the 12M pooled 0.71825** and
  one drags the mean; the delta is 0.44 se. **The one 50M arm ever measured
  off-FP went the OTHER WAY** (struct12M 0.176 -> struct50M 0.188 @FP100,
  n=250, n.s.). **No D29r2 lane has ANY off-SH number.**
- **ATTENTION: the 34.6x was vs the FLAT [512,512] MLP**, no longer
  production; attention-vs-`entity_deepsets` has NEVER been measured. The 08-25
  review ruled on CAPACITY, not structure, and named **temporal context** the
  sharper gap.
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

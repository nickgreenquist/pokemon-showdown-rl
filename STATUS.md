# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **LADDER R1 COMPLETE AT n=200; the
pre-registered PRIMARY read is UNMEASURED.** 95-105 (0.475); played-only
91/196 (0.464); PS Elo 1000 -> **1311** (peak 1348) vs a top-500 cutoff of
1357; 141 opponents; 12.07 h. **NEVER LISTED, so GXE/Glicko DO NOT EXIST —
quote the Elo, never project one.** Gates green: 200/200 tallies, 0
decision_errors, 0 mask_desyncs; obligations -> `LADDER_R1_READOUT.md`.)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
R2 search@M is a B1 CREDIT but SH-facing/INFERENCE-ONLY. CH3+CH4-R1 CLOSED.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE · R0 ensemble 0.74633 · D29r2 50M 0.70222 | **0.71825** |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing)** | **0.79283** |
| **LADDER R1 n=200 — DESCRIPTIVE, PS Elo 1311, NO GXE** | **0.475** |

## Next actions (assistant-decided 2026-08-26; DEVIATES from the 08-26 morning
plan — the encoder fork is DEFERRED to round 2, reasons in that day's log)
1. **ONE pre-reg = YARDSTICK CHANGE + THE H&L SIGNAL CARRY-FORWARD.** Needs
   the 2-Opus-plus-reviews process; NOT yet written.
   - **Lever: `hl_shaping: 1.0` + `gamma: 0.95` on `showdown_sp_recipe12m.yaml`
     verbatim otherwise, 4 lanes x 12M** (~9.8 h/lane, one overnight), seeds
     from the HELD set 66/67/75/76/83/84/93/94. Zero new code: `hl_shaping` is
     a live env kwarg and DESIGN §4 Rung 1 already specifies its R0
     antisymmetry gate. **Encoder-neutral -> invalidates no checkpoint.**
     Rung 1 nulled (+0.0135 n.s.) but ONLY on `trunk: mlp`; EVERY entity-trunk
     run on disk is gamma 1.0 / no shaping, and DESIGN pre-registered the
     carry-forward result-blind.
   - **Yardstick: FP@20 PRIMARY credit line, vs-SH a non-regression guard.**
     Two real blockers: (a) `ch3_fp_h2h.py`'s `ARM_KINDS` has no `ensemble`
     and asserts on it; (b) `eval_checkpoint._opponent_from_checkpoint` seats a
     PoolPlayer that SAMPLES = the A1 bias — use `SeatPlayer`. Grade L2 AND the
     new arm in the same window, or round 2 has no baseline.
2. **Round 2: the encoder fork** (fixed-damage `basePower == 1`), graded on
   the FP@20 baselines round 1 establishes.
3. **NOT: more scale** (50M FLAT), **not attention/capacity** (08-25 review:
   88% of a same-family 72%-GXE agent), **not a blunder filter** (dead, below),
   **not a 2nd ladder arm to DISCRIMINATE proxies** (~4x n=200 for ~30-50 Elo).
## Watch items
- **WE ARE IN THE STYLE TABLE (`scripts/replay_audit/our_style.py`, new).**
  Sum-|delta| from the human field: **US 0.095, SH 0.095**, clone 0.124 — as
  human-like as the closest anchor already. **Gross move errors: us 0.6% vs
  humans 2.7%** (1.88 vs 7.20% given a known better move; exposure near-equal)
  — nothing for a blunder mask to filter. Biggest gap left: status 18.0/23.0.
- **"We under-switch" IS RECONCILED: TOTAL switch rate is at PARITY (27.2 vs
  28.6); only the VOLUNTARY cut differs (6.9 vs 10.7) — ours are REACTIVE.**
- **THE ENCODER DEFECT HAS A PARTIAL ROUTE-AROUND:** `move_emb` is a learned
  `nn.Embedding(166, 64)` in every move token, so the sweep's "cannot route
  around `basePower == 1`" is too strong — misleading, not unrepresentable, and
  ~1% of decisions. Fix in round 2, ONE fork. Force-switch defect: INERT.
- **THE CRITIC IS FINE, NOT SH-SPECIFIC** (n=300/opp): AUC 0.704 (6 mons) ->
  0.891 (1 mon), BETTER vs the FP clone. (n=40 gave 0.964 — do not.)
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED.** 3 copies via
  `scripts/backup_ladder.sh`; numbers survive in tracked `LADDER_R1_READOUT.md`.
  `score_ladder.py` is a FALSE FRIEND; `REPLAY_AUDIT.md` is n=39, SUPERSEDED.
  **13 commits UNPUSHED — ask before pushing.**

# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-26 — **LADDER R1 COMPLETE AT n=200; THE PRIMARY
READ IS UNMEASURED.** 95-105 (0.475); played-only 91/196 (0.464); PS Elo 1000
-> **1311** (peak 1348) vs a top-500 cutoff of 1357; 141 opponents; 12.07 h.
**NEVER LISTED, so GXE/Glicko DO NOT EXIST — quote the Elo, never project a
GXE.** `stopped_by_rule: false` is CORRECT (the rule also needs listing).
Gates green: 200/200 tallies, 0 decision_errors, 0 mask_desyncs, 6.74 ms.
**All 3 readout obligations discharged -> `LADDER_R1_READOUT.md` (tracked);**
obligation (ii) resolved AGAINST memorisation — rematch opponents are ~113
Elo stronger (1311 vs 1198), the confound the pre-reg named in advance.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
D26 12M = 0.71825 (CREDITED HEADLINE). R2 search@M = 0.79283 (B1 CREDIT,
SH-facing, INFERENCE-ONLY). CH3/CH4-R1 CLOSED. Suite 538 / 17 skipped.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing)** | **0.79283** |
| **LADDER R1 n=200 — DESCRIPTIVE, PS Elo 1311, NO GXE** | **0.475** |
‡ FP's take, not ours. Never quote an anchor as a "best".

## Next actions (maintainer-decided 2026-08-26)
1. **L2 OFF-SH IS THE OUTSTANDING EVAL.** The arm that just played 200 ladder
   games has NEVER been measured off-SH — the pre-reg's own table says
   `unmeasured` vs both the BC clone and Foul Play. ~3 h. **Check first that
   `ensemble` is in `ch3_fp_h2h.py`'s ARM_KINDS** (it asserts on unknown kinds;
   a 3 h run would die on it). "Evaluate all finals" is otherwise near-empty:
   132 ckpts on disk, only 13 sha-pinned, essentially all already graded.
2. **ONE pre-reg covering BOTH the encoder fork and the yardstick change** —
   split them and the first result is ungradeable and the second has no
   baseline. 2-Opus-agents-plus-review per standing process. **Yardstick:
   FP@20 becomes the PRIMARY credit line, vs-SH a non-regression guard.** CH4
   R1 already paid for this (off-SH seed sd 0.0077 < vs-SH 0.0112 = "off-SH
   credit line AFFORDABLE", never spent); FP@20 at 1.20 s/battle makes a full
   3000x3 arm ~3 h. **Encoder: fixed-damage moves are the one defect to fix.**
3. **Retrain 12M on the new encoder, graded on the new protocol. NOT longer:**
   D29r2 at 50M read 0.70222, R-B FLAT vs 12M — the one lever with direct
   evidence against it.
## Watch items
- **LADDER DATA IS UNREPEATABLE AND GITIGNORED.** 3 copies via
  `scripts/backup_ladder.sh` (live / d25-backup mirror / ~/pokemon-showdown-rl-
  ladder-archive; exits non-zero if the mirror drifts). The NUMBERS survive
  separately in tracked `LADDER_R1_READOUT.md` + `ladder_readout.py`.
- **ENCODER DEFECT, ACT ON IT:** fixed-damage moves have `basePower == 1` in
  poke-env gen-1, so Seismic Toss encodes as 1/80th of a Thunderbolt. Measured
  cost: **Super Fang 0/59 for us vs 36% for humans**; Seismic Toss 0.141 vs
  0.289 (z=-3.39). Changing OBS_DIM invalidates every checkpoint — one fork.
- **ENCODER DEFECT, INERT:** `bool([])` is False, so `_move_slots_aliased`
  says "not aliased" on force-switch turns and 4 move blocks describe the
  FAINTED mon at `known=1.0` (42/42). Zeroing them flips **0/42** choices and
  fixing it moves checkpoints off-distribution. Not a win.
- **THE CRITIC IS FINE** — AUC 0.773 (6 mons) -> 0.964 (1 mon), tracks progress
  not own-HP. Heal loops / endgame collapse are NOT value-shape and the gamma
  lever has no support. Caveat: measured vs SH-like play only.
- `REPLAY_AUDIT.md` is n=39, SUPERSEDED by the n~175 sweep in SESSION_LOGS.
  `score_ladder.py` is a FALSE FRIEND; real: `ladder{,_readout,_classify}.py`.

# STATUS
## JOURNEY POSITION — step 7.5 (the engine port) **EXITED 2026-09-10**; next is gen-1 step 8/10
**THE GEN-4 CHAPTER IS CLOSED (2026-09-09):** step 3 MET (M-YES), step 5's exit MET
(S5-MATCHED), step 6's ladder BANKED NOT RUN, step 7 is RESULTS §19. Steps 1–2 banked
(LADDER R4: GXE 65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200). **From here it is all gen 1.**

## The gen-4 result (2026-09-09; RESULTS §19, readouts/GEN4_WANG50M_READOUT.md)
- **vs SH, locked protocol, 3×3000, greedy: pooled 0.8788.** Band reads the seed-clustered
  0.00452, not the binomial 0.00344. **ONE RUNG IS WORTH ±0.02.** **M-YES**, **S5-MATCHED**,
  **CREDITS NOTHING** — "matched" carries D-DOSE (2/3), D-IMPL, D-NET, D-ACT, D-ENC, D-COLL,
  D-SH, D-TIE. Anchors (descriptive): MDT 0.902 · FP@20 0.293 (budget named; weakly powered;
  flatters us) · FP@500 0.264 · clone(FP@20) 0.985. Every gate PASS ×3.

## JOURNEY 7.5 — the engine port, EXITED (full account docs/engine_port/NOTES.md)
- **A-1 IS THE EXIT AND IT PASSED TWICE.** Maintainer ratified RW-1..9, RW-10 no, verdict
  authorized (verbatim in the sidecar). Engine arm at the 12M rung, n=12,000/seed, vs the
  banked async arm 0.67211:

  | build | s66 | s75 | s83 | pooled | signed delta | cell |
  |---|---|---|---|---|---|---|
  | pre-fix | 0.66400 | 0.69250 | 0.65550 | 0.67067 | −0.00144 | A1-PASS |
  | **FIXED (bd3d06a)** | 0.66675 | 0.67183 | 0.66467 | **0.66775** | **−0.00436** | **A1-PASS** |

  Band ±0.025; the fixed read is −0.59 se on the seed-clustered 0.00736. P-AUC −0.00298
  INSIDE (secondary, RW-8). **−0.00436 travels forever** as N-COLL's does.
- **A-1a (RW-9) EARNED ITS PLACE.** Frozen-policy rows: actions, masks, old_logp, lengths
  and outcomes all inside the A/A reseeding spread — and **10× separation** on dims
  627/673/719, the foe's revealed-move **PP fraction**. poke-env decrements a foe's
  `current_pp` per observed `|move|`; `track.rs` hard-coded `pp = max_pp`. **P-1
  structurally could not see it** (it fills the observable state FROM poke-env). Fixed by
  counting observed spends; `cargo test` 44/44; P-1 re-run 100,000 decisions 0 mismatches;
  A-1a on the fixed build separates NOTHING.
- **SPEED.** A/B **4.035x** (k=256 vs concurrency 8, ABBA) is the COLLECTOR's; **k alone is
  1.30x at matched width**; fleet k=256 w=6 = 2.06x. Profile INVERTED (update 25% → 65% of
  wall), so further collector work is capped at 1.54x. A lane is a SEED.
- **K-1 (k=256) PARKED, reviewed ×2.** The monster runs at **k=8**: k buys ~5 fleet-hours
  against 13.3% of every update's rows one version stale, concentrated on OPENING play (22%
  of turns 1–5 vs 7% of turns 25+), into an already-saturated clip. Its MDE (0.032–0.038)
  is WIDER than its own accept band.

## The search relook — GRADED, and the diagnosis moved (docs/search_relook/)
- **S3, on the 100M finals, vs SH, locked protocol, 3×3000/arm** (credits nothing):

  | read | delta | cell |
  |---|---|---|
  | **P-M** search@M − FRESH greedy (0.78867) | **−0.0681** | **NEG, 3/3 lanes** |
  | **P-B** det_blind − as-is | **−0.0088** | **NEG** |
  | **P-BA** det_blind search − greedy | **−0.0769** | **NEG** |
  | P-E LOO-ensemble evaluator − search@M | PARTIAL ~+0.012 | pending |

  Off FP@20, s112, n=1000 (budget named; both standing disclosures): as-is **0.3960**,
  det_blind **0.4054**, banked greedy **0.50167**. Dose L (partial) reads BELOW dose M.
- **S1 FIRED and the fix did not pay.** The leaf encoder showed the critic a *revealed*
  determinized bench it never trained on: bias **+0.0497**, sd 0.125, against decision
  margins of **0.028** (4.5×). `det_blind` collapses it offline (sd 0.008) and moved the
  win rate by **nothing**. The ENCODING was not the binding defect.
- **WANG OVERTURNS "the evaluator is the answer"** (`prior_work/WANG_SEARCH_DEEP_READ.md`,
  154 citations). His MCTS gained **+12 pts** vs SH on the **UNMODIFIED PPO critic**. What
  differs is SELECTION: his prior sits INSIDE the PUCT rule and he decides by **MAX VISIT
  COUNT, not max Q**, explicitly for variance. **Ours hard-argmaxes and overrides the
  policy on 72.8% of decisions** while losing 6.8 points. He DECLINES our S1 operation by
  name (§5.2.2); his budget is **160× our wall clock**, 250–500× our determinizations.
- **RUNNING: D5, the margin gate** (9034d7e, registered before launch). Play the search's
  action only if it beats the POLICY's argmax by > delta; absent = exact no-op (golden
  digest, 13,775 real leaves); delta=inf is exactly greedy. Arms S3G02/05/10 on **s112,
  where BOTH endpoints are measured** (0.74767 at delta 0, 0.78233 at inf). **Only a HUMP
  is interesting.** MONOTONE routes to **H3, the opponent model / switch-target law**: the
  search moves ~8.5 pts of mass attack→switch, concentrated in the high-margin tail the
  gate keeps (0.600 above margin 0.2) — Wang's own documented failure (p.33–34).
- **The ladder object stays GREEDY** until an evaluator or selector arm changes it.

## Next actions
1. **Monster (JOURNEY 10), ruled:** 100M × 2 arms × 3 seeds at **k=8**, w=6 (~22 h;
   fallback 250M × 3). **A** = R4 recipe, oppact head ON (`rl/search/agent.py:68` asserts
   it — a checkpoint without it can NEVER be searched). **B** = A + the **privileged
   EVALUATOR head** (design B, BUILT 7d8650e: a SEPARATE full-information value head;
   `privileged_dim` keeps D18's meaning so a B lane does not silently carry A;
   bit-identical off; engine parity 1,807 blocks bitwise). Pre-reg after P-E and P-G.
   **Maintainer launches (>5 h).**
2. **12M design-B smoke** queued behind the margin arms (`scripts/engine_pe_smoke.sh`); a
   BITWISE actor/critic comparison against engine_a1b_s66 is its inertness read.
3. **Rulings owed:** **11.5 before 11** (the ladder object cannot be chosen blind); a
   per-decision cap for a searched ladder object (proposed ≤ 5 s); whether to build
   engine-native search at all (`ENGINE_SEARCH_DESIGN.md`: 8–11 blocks; P0 gates depth-2).
4. **Chores owed:** `engine_a1_grade.py` must run `extract_history.py` before the AUC leg;
   **8 corrections to the Wang row** in `prior_work/README.md` (1756/79.5% is his PEAK at
   rank 8, post-game-100 average 1615, against our FINAL Elo rows; his network alone was
   NEVER laddered; Table 4.1 carries no n; his SimpleHeuristics is PATCHED, ours stock).
   Free wins staged: the scorer `ctx` factorization (CLEANUP E2), an mmap'd team bank.

## Watch items
- **SUITE GREEN** 995 (port env, seam in); 102 across the search files. **No single env runs engine + analysis** (CLEANUP E1).
- **Post-fix between-seed sd 0.01938 → 0.00368 — DESCRIPTIVE ONLY.** k=3 cannot separate
  that from three lucky draws. Re-check on the monster fleet.
- **Depth-2 does NOT exist.** ~0.17 s/decision PROJECTED on the engine vs 5 s today. The
  asset is the 384-byte clone + Rust encoder, **NOT** the `-Dchance`/`-Dcalc` builds —
  plan §8.4 has that backwards (the pinned build SAMPLES chance).
- A `ch3_eval` job can die on `assert not self.battle2.finished`; it resumes at the chunk
  boundary. **vs-SH is NEVER a ladder number.** Resumes SPLIT wandb history. A pgrep guard
  anchors on `bin/python`. Never edit a script an instance is executing.

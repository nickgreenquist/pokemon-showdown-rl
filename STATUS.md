# STATUS
## JOURNEY POSITION — step 7.5 (the engine port), IN FLIGHT and P0; steps 1–7 DONE
**THE GEN-4 CHAPTER IS CLOSED (2026-09-09):** step 3 MET (M-YES), step 5's exit MET
(S5-MATCHED), step 6's ladder BANKED NOT RUN, step 7 is RESULTS §19. Steps 1–2 banked
(LADDER R4: GXE 65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200).
**Everything from here is gen 1.**

## The gen-4 result (2026-09-09; RESULTS §19, readouts/GEN4_WANG50M_READOUT.md)
- **vs SH, locked protocol, 3×3000, greedy: pooled 0.8788.** Band reads the
  seed-clustered 0.00452, not the binomial 0.00344; +0.1228 over the floor = 27.2×.
  **ONE RUNG IS WORTH ±0.02.** **M-YES** and **S5-MATCHED**; **CREDITS NOTHING** —
  "matched" carries D-DOSE (2/3), D-IMPL, D-NET, D-ACT, D-ENC, D-COLL, D-SH, D-TIE.
- **Anchors** (descriptive, never verdict inputs): MDT 0.902 · FP@20 0.293 (budget named;
  weakly powered; flatters us) · FP@500 0.264 · clone(FP@20) 0.985. Every gate PASS ×3.

## JOURNEY 7.5 — the engine port (2026-09-10; full account docs/engine_port/NOTES.md)
- **A/B SPEEDUP 4.035x** (width 1, k=256 vs concurrency 8; ABBA, sd 0.0086); **2.984x
  matched** (collector alone); **3.553x at width 3**. The Node path is ~85% batch-1
  forwards, so much of this is INFERENCE BATCHING — quote the PIPELINE's, never the
  engine's. 2.62x cross-day is RETIRED.
- **PROFILE INVERTED:** update 25.0% of wall on Node -> **65.1% on engine**; further
  collector work capped at **1.54x**. Account: docs/engine_port/SPEEDUP.md.
- **MAX-OUT:** today k=8 w=3 = 4,861 steps/s fleet; **k=256 w=6 = 9,994 = 2.06x** on
  11.3 GB of 24; best per-lane k=256 w=1 = 3,035 = 1.87x. **A lane is a SEED — width buys
  seeds/hour, never a shorter run.** 100M×3 seeds: 13.2 h at k=256 vs 48 h on Node.
- **Learner levers are COMPLEMENTS:** threads and minibatches each NEGATIVE alone, **1.51x
  crossed**; `torch.compile` dead. Scorer factorization REVERTED (bit-exact pin). See CLEANUP
  E1-E3 for the three open rulings.
- **A-1: NO VERDICT, by instruction.** Descriptive per-seed at n=12,000: s66 0.6640,
  s75 0.6925, s83 0.6555. `ratified_decisions` empty; RW-1..RW-10 all owed.

## Next actions
0. **SEARCH RELOOK (critical, maintainer 2026-09-10).** On record: VALUE-LIMITED, not
   dose-limited — depth-1 over the PPO critic went NEGATIVE at 50M off FP (0.474 → 0.381),
   16x n_det bought +0.0225 vs SH at 12M (last 4x: +0.0025), FP@500 ≈ FP@20 against us
   (gen 1: 0.312/0.388/0.332 at 20/100/500 ms). The monster train MUST keep the oppact head
   (`rl/search/agent.py:68` asserts it) AND pick its EVALUATOR lever before launch (seed
   ensemble / privileged critic / outcome-trained evaluator). **S3 RUNNING** (agent-side,
   detached, `scripts/search_s3_status.sh`): search@M/L + LOO-ensemble vs FRESH greedy on the
   100M finals vs SH locked, + search@M off FP@20 (`configs/eval/search_s3_100m*.yaml`).
   Fresh greedy landed: s104 0.7893 / s112 0.7823 / s120 0.7943 (banked pooled 0.7959).
1. **Rule on RW-1..RW-10** (`configs/engine_a1.prereg.yaml`) + `verdict_authorized` — A-1
   reads engine 0.6707 vs banked 0.6721 (Δ −0.0014, band ±0.025) and cannot be graded until
   ruled; nothing 100M+ runs on the engine before 7.5 exits (one collector for steps 8–11).
2. **k=256 screen** (3 × 12M, ~1.7 h, paired with A-1's own k=8 lanes) — pre-reg in draft.
   The 4.035x is at an UNTESTED LEARNING config (12.6% of an update is off-policy rows).
3. **Monster pre-reg (JOURNEY 10):** rec 100M × 2 arms × 3 seeds (R4 recipe vs + evaluator
   lever; ~17 h at k=256 w=6) over 250M × 1 arm (35–43 h, dose only — the ladder resolves
   ±70 Elo and R1→R4 spans 45). Maintainer launches (>5 h). Rulings owed: shape, k, JOURNEY
   11.5-before-11, a per-decision cap for a searched ladder object (proposed ≤ 5 s).
4. FREE wins still staged (scorer `ctx` factorization, CLEANUP E2; mmap'd team bank).

## Watch items
- **SUITE GREEN** 939 / 19 skipped + 9 live-server (port env); no single env runs it all
  (CLEANUP E1). The live-server "flake" was an ORDERING BUG — fixed in `tests/conftest.py`.
- **Depth-2 does NOT exist.** Today's stack: 5 s/decision (55% is a Python leaf encoder the
  Rust encoder does 166x faster); pkmn/engine ~0.17 s PROJECTED. The asset is the 384-byte
  clone + Rust encode, NOT the chance builds (plan §8.4 has it backwards).
- **vs-SH is NEVER a ladder number**; resumes SPLIT wandb history (`merge_history.py`); a
  pgrep guard anchors on `bin/python`; never edit a bash script an instance is executing.

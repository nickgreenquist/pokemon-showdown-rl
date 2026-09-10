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
- **A/B SPEEDUP 4.035x** (k=256 vs concurrency 8; ABBA) is the COLLECTOR's; **k alone is
  1.30x at matched width** (max-out); fleet k=256 w=6 = 2.06x. Profile inverted: update 65%
  of wall on the engine. Account: docs/engine_port/SPEEDUP.md.
- **A-1 GRADED A1-PASS** (maintainer ratified RW-1..9, RW-10 no, verdict authorized):
  engine 0.67067 vs banked 0.67211, **signed delta −0.00144** (pre-reg basis); same-era
  re-read at n=12,000 **+0.0016**. **A-1a (RW-9) CAUGHT a boundary defect** — foe move PP
  hard-coded 1.0 where poke-env decrements per observed use (dims 627/673/719, SMD 0.94);
  FIXED in the tracker (bd3d06a), P-1 still bitwise, A-1a re-run on the fixed build shows
  NOTHING separated. **7.5 closes on A-1 re-run on the fixed build (~2.4 h, ASKED).**
- **K-1 (k=256 screen) is PARKED, reviewed x2** (`configs/engine_k256*.yaml`): the monster
  should run at k=8 — k buys 5 fleet-hours and the screen cannot resolve a 2-point cost.

## Next actions
0. **SEARCH RELOOK — the day's finding.** Depth-1 search as it existed HURTS the 100M object:
   off FP@20 s112 **0.396 vs greedy 0.502** (n=1000); vs SH at 4/10 chunks search@M trails
   fresh greedy by 5–10 points on all three lanes. **S1 fired (4.5x):** the leaf encoding
   revealed the determinized bench to a critic that never saw it (bias +0.050, sd 0.125 vs
   margins 0.028). **`det_blind` built** (f6e7226; byte-identical default): offline the
   artefact collapses (sd 0.008, bias +0.0002) and 11.4% of dose-M decisions flip.
   **S3B (det_blind, 3 lanes vs SH) + F3B112 (off FP@20) RUNNING**; reads pre-stated in
   `configs/eval/search_s3_100m*.yaml` (P-B) and docs/search_relook/DET_BLIND.md §6.
   S3M/S3L/A1E (LOO-ensemble evaluator) also running. `scripts/search_s3_status.sh`.
1. **Monster pre-reg (JOURNEY 10), rec:** 100M × 2 arms × 3 seeds at **k=8**, w=6 (~22 h):
   R4 recipe (oppact head ON — `rl/search/agent.py:68` asserts it) vs + a separate
   PRIVILEGED EVALUATOR HEAD (design B, docs/proposals/privileged_critic_engine_route.md;
   2 blocks; the ppo.py:478 guard protects nothing structurally). Rulings owed: 100M×2
   vs 250M×1; design A/B; JOURNEY 11.5 before 11; per-decision cap for a searched ladder
   object (proposed ≤ 5 s). Maintainer launches (>5 h).
2. Free wins still staged (scorer `ctx` factorization, CLEANUP E2; mmap'd team bank).

## Watch items
- **SUITE GREEN** in the main env (965 passed with det_blind); engine tests 87 in the port
  env — no single env runs both (CLEANUP E1). Live-server "flake" fixed in `tests/conftest.py`.
- Depth-2 does NOT exist; ~0.17 s/decision PROJECTED on pkmn/engine; today's stack 5 s. The
  asset is the 384-byte clone + Rust encode, not the chance builds (plan §8.4 backwards).
- **vs-SH is NEVER a ladder number**; resumes SPLIT wandb history (`merge_history.py`); a
  pgrep guard anchors on `bin/python`; never edit a bash script an instance is executing.

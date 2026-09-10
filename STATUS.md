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
  NOTHING separated. **7.5's EXIT IS MET: A-1 on the FIXED build is A1-PASS, delta -0.00436.**
- **K-1 (k=256 screen) is PARKED, reviewed x2** (`configs/engine_k256*.yaml`): the monster
  should run at k=8 — k buys 5 fleet-hours and the screen cannot resolve a 2-point cost.

## Next actions
0. **SEARCH RELOOK — the selector, not (only) the evaluator.** S3 GRADED: **P-M
   (search@M - greedy) -0.0681 NEG 3/3**; **P-B (det_blind - as-is) -0.0088 NEG** — S1's
   encoding artefact was real, is fixed, was NOT binding. **But Wang's MCTS gained +12
   pts on the UNMODIFIED PPO critic** (`WANG_SEARCH_DEEP_READ.md`), so a bad critic does
   not explain our sign either. His prior sits INSIDE the selection rule; he decides by
   VISIT COUNT for variance; **ours overrides the policy on 72.8% of decisions** —
   maximization bias. **RUNNING: the margin gate D5** (S3G02/05/10 on s112, registered
   9034d7e; endpoints both measured, 0.74767 and 0.78233). Only a HUMP is interesting;
   MONOTONE routes to **H3, the opponent model / switch-target law** (8.5 pts of mass
   moves attack->switch, concentrated in the high-margin tail the gate keeps — Wang's
   own documented failure). A1E partial ~0.732 buys ~1 pt where the gap is 7.
   **Ladder object stays GREEDY until this moves.**
1. **Monster (JOURNEY 10), ruled:** 100M x 2 arms x 3 seeds at **k=8**, w=6 (~22 h;
   fallback 250M x 3). A = R4 recipe (oppact head ON); B = **+ privileged EVALUATOR
   head** (design B, BUILT 7d8650e, bit-identical off; 12M smoke queued behind the
   margin arms). Pre-reg after P-E and P-G land. Maintainer launches (>5 h).
2. Owed: 11.5 before 11; a per-decision cap for a searched ladder object (<= 5 s);
   whether to build engine-native search at all (`ENGINE_SEARCH_DESIGN.md`, 8-11 blocks);
   `engine_a1_grade.py` must run `extract_history.py` before the AUC leg; 8 corrections
   owed to the Wang row in `prior_work/README.md` (1756 is his PEAK vs our FINAL Elo).

## Watch items
- **SUITE GREEN** 995 in the port env; 102 across the search files after D5.
- **A-1a caught a defect P-1 could not see** (foe move PP hard-coded 1.0). Fixed bd3d06a.
  **Post-fix between-seed sd 0.01938 -> 0.00368 — DESCRIPTIVE ONLY**; k=3 cannot separate
  that from chance; re-check on the monster fleet.
- **K-1 (k=256) PARKED, reviewed x2** — k alone is 1.30x at matched width.
- Depth-2 does NOT exist; the asset is the 384-byte clone + Rust encode, NOT the chance
  builds. A `ch3_eval` job can die on `assert not self.battle2.finished`; it resumes.
- **vs-SH is NEVER a ladder number**; resumes SPLIT wandb history; pgrep on `bin/python`;
  never edit a bash script an instance is executing.

# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED); 11.5 READ; **the post-ladder week ended with the GATE, not depth, as the instrument**
**§24 (2026-09-18, `readouts/GATE_R5_READOUT.md`) REVERSES §23 and is the sharpest search finding we have.**
§22/§23 both read null on depth at a ~6.5% override rate, where search changes ~2 decisions of a 30-turn
battle — a mechanical bound on how much any leaf value can matter. Hold depth, OPEN the gate to 16–19%:
our critic **−0.006 (0.38 se)**, Foul Play's hand-tuned heuristic **−0.088 (5.59 se)**. The evaluator
difference is −0.020 (1.56 se) tight and **−0.102 (5.62 se)** open. **OUR CRITIC IS THE ROBUST EVALUATOR**
— the off-distribution story is falsified in the OPPOSITE direction to the one assumed. **DEPTH-2 IS THE
DEFECT and the cause is OUR code:** −0.0007 tight, **−0.047 at 2.57 se** open; `_look_further` maxed over
our replies with the opponent PINNED, and rows with more escape hatches inflate most.
**WHAT DOES NOT CHANGE: search still loses to GREEDY.** Three greedy draws 0.5747 / 0.5720 / 0.5827 →
**pooled 0.5765 (n=4500)**; best searched arm 0.5627. **THE BAR IS GREEDY, not the depth-1 search.**
## **NEW 2026-09-18 — the R5 committee BEATS FP@500: 0.5600 (n=500, 0 ties), +2.70 se above even**
Same session W020 0.5500; **25× budget buys Foul Play +0.010 at 0.32 se**. The 100M committee LOST this at
0.472. FP@500 is an INSTRUMENT, not a rung; all four FP disclosures travel. **RESULTS §25,
`readouts/FP500_R5_READOUT.md`.**
**JOURNEY 11.5's premise "FP beats us at 500 ms" is retracted for THIS object.**
## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2, ~103 clear)**
Committee of the 200M W finals (w104/w112/w120), greedy, 2026-09-16: **128–72**, rd 25.0, attempt 1, no
relaunch/resume, 0 decision errors, 0 mask desyncs, account reconciles 327–273/600 with ZERO unlogged games.
146/200 battles at or above the STOP cutoff; 93–53 listed vs 35–19 below (indistinguishable). DISCLOSURES:
warm-started account (400 prior games — GXE/Glicko/Elo are ACCOUNT properties); STANDALONE DESCRIPTIVE;
**no R1/R3/R4/R5 delta is an effect**; barred list binding. Pool (CLEANUP L1): 102 opponents, 63.5% repeats,
both adaptation tests null. `readouts/LADDER_R5_READOUT.md`, §20. **Anchors COMPLETE: BC-clone 0.9640.**
**GEN-4 CLOSED (§19): vs SH 0.8788, CREDITS NOTHING; LADDER R4 Elo 1354. From here it is all gen 1. JOURNEY
7.5 engine port EXITED, A-1 PASSED TWICE** (−0.00436 travels forever); k=8 idle w3 1620, w6 1282 steps/s/lane.

## **THE TREE (§26, `readouts/TREE_R5_READOUT.md`) — DONE 14:08Z: nothing clears greedy, but the RULE matters**
A real decoupled-UCT tree, our policy as PUCT prior, our critic at leaves, n=1000/arm off FP@20:

| arm | rule | acted on | changed/battle | win rate | vs greedy |
|---|---|---|---|---|---|
| **TG** | gumbel | 11.44% | 3.6 | **0.6040** | **+0.0210 at 0.96 se** |
| TV | visits (FP's rule) | 3.65% | 1.1 | 0.5970 | +0.0140 at 0.64 se |
| TQ | q + margin (the MATRIX selector's shape) | 9.34% | 2.9 | 0.5600 | −0.0230 at 1.04 se |
| **TGR** | GREEDY, this block | — | — | **0.5830** | the bar |

**NOTHING CLEARS THE CREDIT LINE** (≥ +0.025 AND ≥ 2·se_diff). **And nothing is BELOW greedy either —
that is new:** every matrix arm ever measured was level or under. Block calibrated (TGR − pooled greedy
+0.0065 at 0.38 se). **THE FINDING: the DECIDE RULE orders these arms, not the action rate.** TQ acts
BETWEEN TV and TG and reads LOWEST; TG − TQ = **+0.0440 at 2.00 se**. Every earlier search result was
explicable by how often search was believed (§22); this ordering runs AGAINST that confound. The worst
rule is `q + margin` — **the shape every banked matrix number uses. TG's +0.021 is UNRESOLVED, not a
null**: se_diff 0.0220 at n=1000, and resolving it at 2 se needs n≈4,375/arm (the +0.025 floor, ≈3,087).
**Every arm is `iters: 100`, so nothing here speaks to the BUDGET** — and 90.9% of root visits land on
one action at a small budget, which is what TV's 1.1 changed decisions/battle is.

## BUILT 2026-09-18, ALL UNRUN — details in `docs/IDEAS_POST_100M.md` Round 4
- **2.10 `depth2.opp_k`** (11 tests): default 1 = the old pinned-opponent max, BIT-IDENTICAL; >1 gives the
  opponent answers and backs up max-of-min (= minimax at plies=1). **TWO MORE DEFECTS fell out of the
  tests:** an unexpandable leaf was re-embedded at `turn+1+plies` and RE-SCORED (**every depth-2 arm before
  today carries it**, CLEANUP L4), and a SWITCH column produced ZERO grandchildren.
- **8.5 the disagreement gate** (`SearchAgent(disagree=…)`, 17 tests): search only where the committee is
  split. `votes` is free; `margin` works for one agent; **`random` is the CONTROL** that separates "spend it
  HERE" from "spend it CONCENTRATED". Threshold 0 = search all, above every score = exactly greedy.
- **2.11 the luck ceiling** (`scripts/outcome_variance.py`) is now RESUME-SAFE and rate-readable (rule 4).
- **4.9 EXPERT ITERATION is the maintainer's TOP §4 item** (2026-09-18); design in
  `docs/proposals/EXPERT_ITERATION.md`, gated on 2.11, with a falsifier that is free: measure
  KL(π′‖prior) on banked arms — if the expert IS the student the lever dies without a fleet.

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; CREDITED for the RECIPE (§21)
Six lanes k=8: **W trio = L2 + 1024 critic** (104/112/120, 46.3 h); **L2LAM = L2 + MC targets** (128/136/144).
- **Off FP@20, same session, n=3000/arm:** E3WF **0.5987** > E6MF 0.5763 ≈ E9F 0.5760 > E3HF 0.5570 > E3LF
  0.4960. Singles n=9000: W 0.5417, 100M 0.4952, L2LAM 0.4481. **LADDER OBJECT = E3WF** (+0.0417 at 3.27 se).
  **vs SH:** GW 0.8217 vs 100M A0 0.7887 = **+0.033 at 5.6 se**; E3W 0.8386 (+0.015 over the 100M ENS3 at
  2.01 se — **NOT credited; recipe gain and committee gain SUBSTITUTE**). **ENS3 of the 100M finals CREDITS**
  (+0.0349 vs SH at 5.93 se) and is the R5 FLOOR, at greedy speed.
- **Mechanism (§21):** critic first-layer srank99 **632/1024 vs 5/384** — width is LIVE, ceiling branch did
  NOT fire. But **EV DID NOT MOVE** (0.5881 vs 0.5919): **do not size the next fleet on EV.**

## SEARCH LANDMINES (narratives in `docs/landmines.md`)
D5 gate out of sample **+0.016 at 2.19 se — MISSES the floor**; never quote s112's +0.0417. **EVERY search
number before 2026-09-11 measures a BROKEN selector** (grep `PRE-D5`; LADDER R3 is a D4 object). **MCTS IS
NOT CLOSED** (§22's scope limit, ruling owed; §24 adds a reason and §26 a second — the matrix vehicle had a
known-optimistic backup, and its `q + margin` selector is the WORST of three decide rules inside a tree).

## Next actions
1. **RUN 2.11 (the luck ceiling) FIRST** — it gates 4.9 and every evaluator item, costs ~45 min, and is
   detached + resume-safe. If `EV_ceiling ≈ 0.6` the critic is DONE and every remaining lever is on the
   POLICY, which re-ranks everything below.
2. **Then `scripts/backup_gate_queue.sh`** (~8 h, overnight, 12 arms + an in-session greedy anchor and an
   in-session replicate): 2.10's `opp_k` minimax backup vs the old one vs depth-1, all at an OPEN gate and
   matched on override rate; and 8.5's disagreement gate against a COIN at the same rate and against a
   uniform arm at matched compute. Config/pin/queue/readout all committed and tested offline.
3. **NEW, from §26 — the TREE BUDGET on the gumbel rule** (IDEAS 8.6): `iters` 100/300/900. Resolving
   TG's +0.021 at the SMALLEST budget would spend ten hours on the weakest version of the arm.
4. **RULINGS OWED:** R6's SPLIT SCHEDULE (CLEANUP L1 — needs its own stopping rule); the LR-anneal floor
   ([RWL-4]; W's EV FALLS through the annealed tail 0.675→0.596, so the tail is not inert); the next fleet's
   shape; **whether a null on the MATRIX vehicle may close MCTS**; and whether 4.9 (expert iteration) gets a
   fleet — it needs a pre-reg and a mechanism co-primary that is NOT explained variance.

## Watch items
- **SUITE GREEN 1151 passed / 0 failed / 87 skipped** (2026-09-18, full `pytest tests/` with the server up,
  encoder flags UNSET — the documented invocation; **+61 tests today**). Engine 115 + 94 cargo. **SIX
  defect-class fixes this week, all one shape — a dial or a field that runs and reports nothing, or reports
  the wrong thing.** Each now has a test that reads the source.
- **SESSION OFFSET ~0.02 ON BOTH FP INSTRUMENTS** — never difference across sessions without a same-session
  anchor. **ONE RUNG IS WORTH ±0.02** (three redraws of one checkpoint spread 0.0200): read curves, not rungs.
- **SEEDS DO NOT PAIR BATTLES** (`docs/landmines.md`): agreement on shared seeds is at the independence level
  (0.66–0.73); every "matched seed-for-seed, McNemar se" phrase was UNPAIRED. Replicates are the instrument.
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS ONLY** (maintainer, 2026-09-17). Hacking needs none; the
  anti-self-deception rules do not relax — counters to disk, matched comparisons, same-session anchors.

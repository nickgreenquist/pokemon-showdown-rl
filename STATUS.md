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
0.472. FP@500 is an INSTRUMENT, not a rung; both FP@20 disclosures travel; `configs/eval/fp500_r5.yaml`.
**JOURNEY 11.5's premise "FP beats us at 500 ms" is retracted for THIS object.**
## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2, ~103 clear)**
Committee of the 200M W finals (w104/w112/w120), greedy, 2026-09-16: **128–72 (0.640)**, rd 25.0, attempt 1,
NO relaunch/resume, mean decision 5.40 ms, 0 decision errors, 0 mask desyncs, account reconciles 327–273/600
with ZERO unlogged games. 146/200 battles entered at or above the STOP cutoff, 9 excursions, peak 1541;
93–53 listed vs 35–19 below (indistinguishable). DISCLOSURES: warm-started account (400 prior games — GXE/
Glicko/Elo are ACCOUNT properties); STANDALONE DESCRIPTIVE; **no R1/R3/R4/R5 delta is an effect**; barred
list binding. Pool (CLEANUP L1): 102 opponents, 63.5% repeats; both adaptation tests null.
`readouts/LADDER_R5_READOUT.md`, §20. **Anchor battery COMPLETE: BC-clone 0.9640 (n=500).**
**GEN-4 CLOSED (§19): vs SH 0.8788, CREDITS NOTHING. LADDER R4: Elo 1354, n=200. From here it is all gen 1.**
**JOURNEY 7.5 engine port EXITED; A-1 PASSED TWICE** (−0.00436 travels forever). k=8 idle: w3 1620, w6 1282 steps/s/lane.

## RUNNING NOW — `scripts/tree_r5_queue.sh` (our critic inside a REAL tree, off FP@20)
Launched 10:45Z, ETA ~14:40Z. Arms n=1000 each: **TV** visits (FP's/AlphaZero's rule), **TG** gumbel,
**TQ** q at margin 0.20 (flip 0.0888 vs D1's 0.0682 target), **TGR** greedy anchor. Decoupled UCT, our
policy as PUCT prior, our critic at leaves, batch-16 leaf-parallel under virtual loss.
**THE BAR IS GREEDY 0.5765.** If it clears, step 2 is scaling the budget for a 500 ms h2h vs FP@500.
Monitor `logs/tree_r5/queue.log`; readout `scripts/tree_r5_readout.py`. Caveat measured 2026-09-11:
**90.9% of root visits land on ONE action** at a small budget, so visit share is nearly the prior.

## BUILT TODAY, ALL UNRUN — the three cheapest items the post-ladder reads point at
- **IDEAS 2.10 — `depth2.opp_k`** (`rl/search/matrix.py`, 11 tests). Default 1 = the old pinned-opponent
  max, BIT-IDENTICAL; >1 gives the opponent answers and backs up max-of-min (exactly minimax at plies=1).
  **A SECOND DEFECT fell out of the tests:** an unexpandable leaf was re-embedded at `turn+1+plies` and
  re-scored, so TURNING DEPTH ON moved values it never looked past. **Every depth-2 arm before today carries
  it.** Third hole closed: a SWITCH column produced ZERO grandchildren (illegal repeat → silent `continue`).
- **IDEAS 8.5 — the disagreement gate** (`SearchAgent(disagree=…)`, 14 tests): search only where the
  committee is split. `votes` is free (the members' log-probs are already computed); `margin` works for a
  single agent. Threshold 0.0 = search everything, above every score = exactly greedy. Gate skips fold into
  the `skips` denominator or a healthy gated arm reads VOID.
- **IDEAS 2.11 — the luck ceiling** (`scripts/outcome_variance.py`) is now RESUME-SAFE and rate-readable
  (rule 4): one position at a time, row appended as measured. **RUN IT BEFORE ANY FLEET — it BOUNDS
  everything.** If EV_ceiling ≈ 0.6 the critic is DONE and every remaining lever is on the POLICY.
- `docs/IDEAS_POST_100M.md` **Round 4**: §3 width/capacity ANSWERED (both halves), §8.1/§8.2 amended,
  **4.9 EXPERT ITERATION added as the TOP §4 item** (maintainer, 2026-09-18), 2.10 / 2.11 / 2.12 / 8.5 new.

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; CREDITED for the RECIPE (§21)
Six lanes k=8: **W trio = L2 + 1024 critic** (104/112/120, 46.3 h); **L2LAM = L2 + MC targets** (128/136/144).
- **Off FP@20, same session, n=3000/arm:** E3WF **0.5987** > E6MF 0.5763 ≈ E9F 0.5760 > E3HF 0.5570 > E3LF
  0.4960. Singles n=9000: W 0.5417, 100M 0.4952, L2LAM 0.4481. **LADDER OBJECT = E3WF** (+0.0417 at 3.27 se).
- **vs SH:** GW 0.8217 vs 100M A0 0.7887 = **+0.033 at 5.6 se**; E3W 0.8386 (+0.015 over the 100M ENS3 at
  2.01 se — **NOT credited; recipe gain and committee gain SUBSTITUTE**).
- **Mechanism (§21):** critic first-layer srank99 **632/1024 vs 5/384** — width is LIVE, ceiling branch did
  NOT fire. But **EV DID NOT MOVE** (0.5881 vs 0.5919): **do not size the next fleet on EV.**
- **ENS3 of the 100M finals CREDITS** (+0.0349 vs SH at 5.93 se) and is the R5 FLOOR, at greedy speed.

## SEARCH LANDMINES
D5 gate out of sample **+0.016 at 2.19 se — MISSES the floor**; never quote s112's +0.0417. Off FP@20 the
SELECTOR alone bought +0.129 — search has only ever paid as a **rarely-fired VETO**, and §22/§24 say why.
**EVERY search number before 2026-09-11 measures a BROKEN selector** (grep `PRE-D5`; LADDER R3 is a D4 object).
**MCTS IS NOT CLOSED** (§22's pre-reg scope limit; ruling owed) — and §24 adds a reason: the matrix vehicle
had a known-optimistic backup until today.

## Next actions
1. **Tree readout → RESULTS §25** when the queue lands, then this file.
2. **Run 2.11 (luck ceiling) BEFORE anything else** — it gates 4.9 and every evaluator item. Hours, no
   server, no FP; detached + resume-safe now.
3. **Then the two built-and-unrun arms, both at an OPEN gate and matched on override rate:** 2.10's
   `opp_k` depth-2 vs depth-1, and 8.5's disagreement gate (threshold swept for realized search_rate first,
   exactly as the margin was swept for override rate).
4. **RULINGS OWED:** R6's SPLIT SCHEDULE (CLEANUP L1 — needs its own stopping rule); the LR-anneal floor
   ([RWL-4]; W's EV FALLS through the annealed tail 0.675→0.596, so the tail is not inert); the next fleet's
   shape; **whether a null on the MATRIX vehicle may close MCTS**; and whether 4.9 (expert iteration) gets a
   fleet — it needs a pre-reg and a mechanism co-primary that is NOT explained variance.

## Watch items
- **SUITE GREEN 1110 passed / 0 failed, 87 skipped, 9 deselected** (2026-09-18, encoder flags UNSET;
  `-k "not live_server"` because the tree queue owns the Showdown server — re-run the 9 live tests when it
  lands). **+29 tests today.** Engine 115 + 94 cargo. **FIVE defect-class fixes this week, all one shape — a
  dial that runs and reports nothing.** Each now has a test that reads the source.
- **SESSION OFFSET ~0.02 ON BOTH FP INSTRUMENTS** — never difference across sessions without a same-session
  anchor. **ONE RUNG IS WORTH ±0.02** (three redraws of one checkpoint spread 0.0200): read curves, not rungs.
- **SEEDS DO NOT PAIR BATTLES** (`docs/landmines.md`): agreement on shared seeds is at the independence level
  (0.66–0.73); every "matched seed-for-seed, McNemar se" phrase was UNPAIRED. Replicates are the instrument.
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS ONLY** (maintainer, 2026-09-17). Hacking needs none; the
  anti-self-deception rules do not relax — counters to disk, matched comparisons, same-session anchors.

# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED). The post-ladder week is a SEARCH chapter that closed with a BUG
**§28 — THE TURN-CAP STALL IS A SWITCH LOOP, and in 91% of cases a THROWN-AWAY WIN.** **103 of the 104
capped battles enumerated** (the claim first rested on six — corrected same day): **100 are switch loops**
(~900–990 switches, ~100% alternating between two slots) and **94 (91.3%) have the opponent immobilised on
≥80% of turns**, usually one Pokémon **FROZEN SOLID**, while our seat oscillates instead of attacking it.
Turn cap → tie → **NON-WIN**. **With and without search** — the two largest concentrations are greedy seats
(15 and 19 of 3000). **THE MECHANISM IS THE LOCKED PROTOCOL'S OWN DETERMINISM:** argmax in a state that
stopped changing repeats forever; training SAMPLES, so it never happens there. `rl/common/loop_breaker.py`
BUILT (13 tests, provably invisible on non-looping battles), **WIRED NOWHERE — it changes the policy form, so
it needs a RULING.** Ladder risk latent (R5 max 121 turns, 0 ties). Tie rate 0.0014, worst arm 0.0110.
**§29 — THE ANNEALED TAIL TRADES EV FOR WIN RATE, 9 LANES OF 9.** Last quarter vs the one before, across W /
L2LAM / the 100M baseline: **EV −0.060 / −0.088 / −0.005** and value loss UP, while **in-loop eval win rate
+0.059 / +0.062 / +0.033** (across-lane sd 0.003–0.006). **Every lane agrees in sign. DO NOT FLOOR THE LR** —
the tail is where 3–6 points of win rate are made. It does NOT isolate the anneal from the steps (a
constant-LR arm has never run). **THIRD independent measurement that EV IS NOT THE OBJECTIVE:** §21 (width
bought zero EV while the win rate moved), §27.1 (88% of the gap is ranking), §29 (EV moves the OTHER WAY).
**§27 + §27.1 — THE LUCK CEILING, and what the critic gets wrong.** 707 positions / 22,358 self-play rollouts:
**~64% of a mid-battle outcome is IRREDUCIBLE**; ceiling **0.3630**, our critic **0.2176**. **THE GATE OPENS —
the critic is NOT done.** Out-of-sample isotonic recalibration buys **+0.0195, only 12% of the gap: 88% is
RANKING.** The critic is **optimistic about its own seat by +0.0416 (z 2.74)** where self-play makes the truth
exactly 0 — **first direct evidence for IDEAS 4.1 (both-seat harvest)**; the collector runs `learner_seat: p1`.
Both failures are **worst in the OPENING** (r² 0.287 at turns 2–8 vs 0.727 at 23+). **NEVER set the training
EV 0.59 against this ceiling** — a different state distribution.
**§26 + §26.1 — a real tree does not beat greedy, but the DECIDE RULE orders the arms.** n=1000/arm off FP@20
vs an in-block greedy anchor **0.5830**: **TG** gumbel **0.6040** [acts 11.4%] **+0.0210 at 0.96 se**; **TV**
visits 0.5970 [3.7%] +0.0140; **TQ** q+margin 0.5600 [9.3%] −0.0230. Nothing clears the credit line; **nothing
is BELOW greedy either, which is new.** TQ acts BETWEEN the others and reads LOWEST (TG−TQ **+0.0440 at 2.00
se**) — the ordering runs AGAINST the override-rate confound, and the worst rule is `q + margin`, **the shape
every banked matrix number uses.** TG's +0.021 is **UNRESOLVED** (n≈4,375/arm); all arms `iters: 100`.
**§26.1: all 5 matrix arms sit below their own anchor; the only arms above one are trees (2 of 3), Fisher
p 0.107** — the VEHICLE separates, the dose does not.
**§25 — the R5 committee BEATS FP@500: 0.5600 (n=500, 0 ties), +2.70 se.** Same-session W020 0.5500, so 25×
budget buys Foul Play +0.010 at 0.32 se for 24.4× the wall clock; the 100M committee lost at 0.472. **Retracts IDEAS §8.1's
premise that FP beats us at 500 ms.** FP@500 is an INSTRUMENT, not a rung.
**§24 — the GATE was the instrument.** Opening it costs our critic 0.006 and Foul Play's heuristic 0.088; the
evaluator gap is −0.020 tight and **−0.102 (5.62 se) open. OUR CRITIC IS THE ROBUST EVALUATOR.** **Depth-2 is
the defect** (−0.047 at 2.57 se open) and the cause was in our code. **§22 — depth-2 at a MATCHED override
rate is −0.0007**; at the naive delta the same arm reads −0.053, so every earlier depth number was an artifact.
**The realized override rate DRIFTS across sessions at fixed δ** (0.1933 → 0.1703): match to the CONTROL and run it FIRST (CLEANUP L6).

## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2)**
Committee of the 200M W finals, greedy, 2026-09-16: **128–72**, rd 25.0, attempt 1, no relaunch/resume, 0
decision errors, 0 mask desyncs, account reconciles 327–273/600 with ZERO unlogged games; 146/200 at or
above the STOP cutoff; 93–53 listed vs 35–19 below. DISCLOSURES: warm-started account (400 prior games —
GXE/Glicko/Elo are ACCOUNT properties); STANDALONE DESCRIPTIVE; **no R1/R3/R4/R5 delta is an effect**;
barred list binding. Pool (CLEANUP L1): 102 opponents, 63.5% repeats, both adaptation tests null. §20.
**Anchors COMPLETE: BC-clone 0.9640. GEN-4 CLOSED (§19): 0.8788 vs SH, credits nothing; R4 Elo 1354.** **JOURNEY 7.5 engine port EXITED, A-1 PASSED TWICE.**

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; CREDITED for the RECIPE (§21)
Six lanes k=8: **W = L2 + 1024 critic** (104/112/120); **L2LAM = L2 + MC targets** (128/136/144). Off FP@20
same session n=3000: E3WF **0.5987** > E6MF 0.5763 ≈ E9F 0.5760 > E3HF 0.5570 > E3LF 0.4960 → **LADDER
OBJECT = E3WF** (+0.0417, 3.27 se). vs SH: GW **0.8217** vs 100M A0 0.7887 = **+0.033 at 5.6 se**; E3W
0.8386 (+0.015 at 2.01 se — **NOT credited; recipe and committee gains SUBSTITUTE**); the 100M ENS3
CREDITS (+0.0349 at 5.93 se) and is the R5 FLOOR. **Mechanism: srank99 632/1024 vs 5/384** (width is LIVE)
but **EV DID NOT MOVE** (0.5881 vs 0.5919): **do not size the next fleet on EV.**

## RUNNING — `scripts/backup_gate_queue.sh` (ETA ~04:15Z). **2.10 HALF IS IN AND THE FIX FAILED**
At a MATCHED override rate (0.1862 vs 0.1703): **B2R minimax 0.5070 vs D1O depth-1 0.5510 = −0.0440 at 1.97
se.** The dial fired (`minimax_drop` 0.057, large against δ 0.08) and made it WORSE. B2O 0.5290 at 0.1322 is
MISMATCHED (a design error, disclosed in the config — B2O's δ was hardcoded from §22 rather than swept), so
B2R−B2O says nothing. **NOT SUPPORTED: "the optimism is WHY depth-2 hurts".** Does NOT close depth, the tree
or MCTS. **Next hypothesis, specific — PESSIMISM TWICE:** `col_w = q` already models the opponent
probabilistically, so a MIN on top is worst-case over an expectation, and that undervalues exactly the
high-variance (aggressive) lines. The untried third option is an EXPECTATION over the opponent's reply under
its own policy — a few lines in `matrix.py`.
**Phase S pinned clean:** δ0.08→0.1974 vs a 0.193 target (|d| 0.0044); the gate's realized rate 0.437 → DRV's
coin at 0.563. Remaining: **DGV** committee-gated / **DRV** coin at the same rate / **DUM** uniform (8.5, all
dose M, so the only difference is WHICH decisions were searched) and **GC** the greedy anchor.

## BUILT 2026-09-18, UNRUN — details in `docs/IDEAS_POST_100M.md` Round 4
- **2.10 `depth2.opp_k`** (12 tests) — **RUN, see above.** Two more defects fell out of writing it: an
  unexpandable leaf was RE-SCORED at a shifted turn (**every depth-2 arm before today carries it**, CLEANUP
  L4), and a SWITCH column produced ZERO grandchildren.
- **8.5 the disagreement gate** (17 tests) with a **`random` CONTROL**. **2.13 recalibrate the leaf value**
  (10 tests) — free, **+0.0195 measured**, and **NOT inert: a monotone map cannot reorder leaves at one node
  but DOES reorder `row_ev`'s expectation over them (3.5% of row pairs flip), and the D5 gate is a threshold
  on that scale, so δ must be re-swept with it.**
- **4.9 EXPERT ITERATION, the TOP §4 item**; design `docs/proposals/EXPERT_ITERATION.md`. Its 2.11 gate has
  OPENED and its FREE falsifier is measured on every tree decision now: `tree/kl_pi_prior`, `tree/pi_top1`,
  `tree/argmax_moved` (UNGATED, unlike `search/overrode`).
- **8.6 the tree BUDGET SCREEN** (`configs/eval/tree_budget_r5.yaml`) — gumbel at iters 100/300/900 plus
  visits at 900, n=40, ~30 min, reading the MECHANISM: phase R fires only if KL rises ≥1.5× and
  argmax_moved by ≥5 points, so the expensive rungs may never run.

## Next actions
1. **Read out `backup_gate_r5`** → RESULTS §30 (§29 is the anneal tail), then this file.
2. **Run the 8.6 budget SCREEN (~30 min)** — it decides whether the expensive tree rungs ever run. Then wire
   **2.13 (recalibration)** into `matrix.py`, re-sweep δ, read it off FP@20. **2.12** likewise free, untried.
3. **RULINGS OWED:** the LOOP BREAKER (§28 — it changes the policy form); R6's SPLIT SCHEDULE (CLEANUP L1);
   the next fleet's shape; whether a MATRIX null may close MCTS; whether 4.9 gets a fleet. **The LR-anneal
   floor now has its evidence (§29): DO NOT floor it** — the tail is where 3–6 points of win rate are made.

## Watch items
- **SUITE GREEN 1187 / 0 failed / 87 skipped** (2026-09-18; **+98 tests today**). **SEVEN defect-class fixes
  this week, all one shape — a dial or a field that runs and reports nothing, or reports the wrong thing.**
  `launch_git_sha` was read AFTER the battles for its whole life; nothing noticed because nothing read it.
- **SESSION OFFSET ~0.02 ON BOTH FP INSTRUMENTS**, and **ONE RUNG IS WORTH ±0.02**: never difference across
  sessions without an anchor. **§28 adds a second reason** cross-block win rates are barred — the tie-rate
  spread is 0.011 and points the same way, against the weaker arm.
- **SEEDS DO NOT PAIR BATTLES**; replicates are the instrument. **PRE-REG IS FOR LADDER RUNS AND HEADLINE
  CLAIMS ONLY** (2026-09-17) — hacking needs none, and the anti-self-deception rules do not relax: counters
  to disk, matched comparisons, same-session anchors.

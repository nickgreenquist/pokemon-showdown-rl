# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED). The post-ladder week is a SEARCH chapter, and it closed with a BUG
**Everything below is RESULTS §20–§28, each with a readout. Nothing since §21 credits anything.**
**§28 (2026-09-18) — EVERY TURN-CAP STALL IS ONE BUG, and it is a thrown-away win.** The opponent is down
to one Pokémon **FROZEN SOLID** (gen-1 freeze is permanent), the state stops changing, and our seat
**oscillates between exactly two Pokémon for ~950 turns — 100% strictly alternating** — instead of
attacking a helpless target. Turn cap → tie → **NON-WIN**. Measured six times, three blocks, two objects,
**with and without search** (a plain greedy seat does it 15× in 3000). **THE MECHANISM IS THE LOCKED
PROTOCOL'S OWN DETERMINISM:** argmax in a state that stopped changing repeats forever; training SAMPLES so
it never happens there. `rl/common/loop_breaker.py` BUILT (13 tests, provably invisible on non-looping
battles) and **WIRED NOWHERE — it changes the policy form, so it needs a RULING.** Ladder risk is latent
(R5 max 121 turns, 0 ties). Overall tie rate 0.0014, worst arm 0.0110; 51% of ties are cap stalls.
**§27 + §27.1 — THE LUCK CEILING, and what the critic actually gets wrong.** 707 positions / 22,358
self-play rollouts: **~64% of a mid-battle outcome is IRREDUCIBLE**; ceiling **0.3630**, our critic
**0.2176**. **THE GATE OPENS — the critic is NOT done.** An out-of-sample isotonic recalibration (the best
any rescaling can do) buys **+0.0195, only 12% of the gap: 88% is RANKING.** The critic is **optimistic
about its own seat by +0.0416 (z 2.74)** where self-play makes the truth exactly 0 — **first direct
evidence for IDEAS 4.1 (both-seat harvest)**; the collector runs `learner_seat: p1`. Both failures are
**worst in the OPENING** (r² 0.287 at turns 2–8 vs 0.727 at 23+), the regime search visits.
**NEVER set the training EV 0.59 against this ceiling** — different state distribution.
**§26 + §26.1 — a real tree does not beat greedy, but the DECIDE RULE is what orders the arms.**
n=1000/arm off FP@20 vs an in-block greedy anchor **0.5830**: **TG** gumbel **0.6040** [acts 11.4%]
**+0.0210 at 0.96 se**; **TV** visits 0.5970 [3.7%] +0.0140; **TQ** q+margin 0.5600 [9.3%] −0.0230.
Nothing clears the credit line; **nothing is BELOW greedy either, which is new.** TQ acts BETWEEN the
others and reads LOWEST (TG−TQ **+0.0440 at 2.00 se**), so the ordering runs AGAINST the override-rate
confound. **Worst rule is `q + margin` — the shape every banked matrix number uses.** TG's +0.021 is
**UNRESOLVED** (n≈4,375/arm to resolve at 2 se). All arms `iters: 100` → nothing speaks to the BUDGET.
**Across every block (§26.1): all 5 matrix arms are below their own anchor, the only arms above one are
trees (2 of 3), Fisher p 0.107** — the VEHICLE separates, the dose does not.
**§25 — the R5 committee BEATS FP@500: 0.5600 (n=500, 0 ties), +2.70 se.** Same-session W020 0.5500, so
25× budget buys Foul Play +0.010 at 0.32 se for 24.4× the wall clock; the 100M committee lost at 0.472.
**Retracts IDEAS §8.1's premise that FP beats us at 500 ms.** FP@500 is an INSTRUMENT, not a rung.
**§24 — the GATE was the instrument.** Opening it costs our critic 0.006 and Foul Play's heuristic 0.088;
the evaluator gap is −0.020 tight and **−0.102 (5.62 se) open. OUR CRITIC IS THE ROBUST EVALUATOR** — the
off-distribution story is falsified in the OPPOSITE direction. **Depth-2 is the defect** (−0.047 at 2.57 se
open) and the cause was in our code. **§22 — depth-2 at a MATCHED override rate is −0.0007**; the same arm
at the naive delta reads −0.053, so every earlier depth number was an override-rate artifact.

## **LADDER R5 — GXE 73.9 / Glicko-1 1697 ± 25 / Elo 1457, n=200, LISTED (cutoff 1354.2)**
Committee of the 200M W finals (w104/w112/w120), greedy, 2026-09-16: **128–72**, rd 25.0, attempt 1, no
relaunch/resume, 0 decision errors, 0 mask desyncs, account reconciles 327–273/600 with ZERO unlogged
games. 146/200 battles at or above the STOP cutoff; 93–53 listed vs 35–19 below (indistinguishable).
DISCLOSURES: warm-started account (400 prior games — GXE/Glicko/Elo are ACCOUNT properties); STANDALONE
DESCRIPTIVE; **no R1/R3/R4/R5 delta is an effect**; barred list binding. Pool (CLEANUP L1): 102 opponents,
63.5% repeats, both adaptation tests null. §20, `readouts/LADDER_R5_READOUT.md`. **Anchors COMPLETE:
BC-clone 0.9640.** **GEN-4 CLOSED (§19): 0.8788 vs SH, credits nothing; R4 Elo 1354. From here all gen 1.**
**JOURNEY 7.5 engine port EXITED, A-1 PASSED TWICE** (−0.00436 travels); k=8 idle w3 1620, w6 1282 st/s.

## THE MONSTER (JOURNEY 10) — DONE 2026-09-15, ZERO RESUMES; CREDITED for the RECIPE (§21)
Six lanes k=8: **W = L2 + 1024 critic** (104/112/120, 46.3 h); **L2LAM = L2 + MC targets** (128/136/144).
- **Off FP@20, same session, n=3000/arm:** E3WF **0.5987** > E6MF 0.5763 ≈ E9F 0.5760 > E3HF 0.5570 > E3LF
  0.4960. Singles n=9000: W 0.5417, 100M 0.4952, L2LAM 0.4481. **LADDER OBJECT = E3WF** (+0.0417, 3.27 se).
  **vs SH:** GW 0.8217 vs 100M A0 0.7887 = **+0.033 at 5.6 se**; E3W 0.8386 (+0.015 at 2.01 se over the
  100M ENS3 — **NOT credited; recipe gain and committee gain SUBSTITUTE**). **ENS3 of the 100M finals
  CREDITS** (+0.0349 vs SH at 5.93 se) and is the R5 FLOOR, at greedy speed.
- **Mechanism (§21):** critic first-layer srank99 **632/1024 vs 5/384** (width is LIVE, ceiling branch did
  NOT fire) but **EV DID NOT MOVE** (0.5881 vs 0.5919): **do not size the next fleet on EV.**

## RUNNING — `scripts/backup_gate_queue.sh` (phase R from 17:06Z, ~9 h; ETA ~02:00Z)
**PHASE S CLEAN AND PINNED.** B2 sweep δ0.03→0.370, δ0.05→0.240, **δ0.08→0.1974 against a 0.193 target
(|d| 0.0044)**; the gate's realized rate is **0.437**, so DRV's coin is pinned at 1−0.437 = **0.563**. The
pin reads override rates and never a win rate, and REFUSES above |d|>0.05 rather than handing phase R an
unmatched comparison. Phase R, n=1000 each: **D1O** depth-1 open gate / **B2O** depth-2 OLD backup /
**B2R** depth-2 `opp_k` minimax (δ 0.08) — 2.10; **DGV** committee-gated / **DRV** coin at the same rate /
**DUM** uniform — 8.5, **all three dose M** so the only difference is WHICH decisions were searched; **GC**
greedy anchor. D1O and DUM are the same configuration on two pairs — the block's realized noise floor.
**The dose-L design was corrected mid-block:** the smoke measured the gate at 45%, not the 25% the compute
matching assumed, which would have made DGV cost ~1.8× DUM and confounded it with COMPUTE.

## BUILT 2026-09-18, UNRUN — details in `docs/IDEAS_POST_100M.md` Round 4
- **2.10 `depth2.opp_k`** (12 tests): default 1 = the old pinned max, BIT-IDENTICAL. **Two more defects fell
  out of the tests:** an unexpandable leaf was re-embedded at `turn+1+plies` and RE-SCORED (**every depth-2
  arm before today carries it**, CLEANUP L4), and a SWITCH column produced ZERO grandchildren.
- **8.5 the disagreement gate** (17 tests) with a **`random` CONTROL** separating "spend it HERE" from
  "spend it CONCENTRATED". **2.13 recalibrate the leaf value** — free, +0.0195 measured, and NOT inert
  (row_ev averages leaf values; the D5 gate is a threshold on that scale, so re-sweep δ with it).
- **4.9 EXPERT ITERATION, the maintainer's TOP §4 item**; design `docs/proposals/EXPERT_ITERATION.md`. Its
  2.11 gate has OPENED. Its FREE falsifier is now measured on every tree decision:
  `tree/kl_pi_prior`, `tree/pi_top1`, `tree/argmax_moved` (UNGATED, unlike `search/overrode`).
- **8.6 the tree BUDGET** on the gumbel rule — `iters` 100/300/900, the direct follow-up to §26.

## Next actions
1. **Read out `backup_gate_r5` when it lands** → RESULTS §29, then this file.
2. **8.6, the tree budget ladder** — resolving TG's +0.021 at the SMALLEST budget would spend ten hours on
   the weakest version of the arm; ladder `iters` first and report KL(π′‖prior) at every rung.
3. **2.13 (recalibration) is free and unrun**; 2.12 (weight averaging) likewise.
4. **RULINGS OWED:** the LOOP BREAKER (§28 — it changes the policy form); R6's SPLIT SCHEDULE (CLEANUP L1);
   the LR-anneal floor ([RWL-4]; W's EV FALLS through the annealed tail 0.675→0.596); the next fleet's
   shape; **whether a null on the MATRIX vehicle may close MCTS**; and whether 4.9 gets a fleet.

## Watch items
- **SUITE GREEN 1173 / 0 failed / 87 skipped** (2026-09-18; +84 tests today). Engine 115 + 94 cargo.
  **SEVEN defect-class fixes this week, all one shape — a dial or a field that runs and reports nothing, or
  reports the wrong thing.** `launch_git_sha` was read AFTER the battles for its whole life, so every arm
  ever run stamped its COMPLETION state under the launch name; nothing noticed because nothing read it.
- **SESSION OFFSET ~0.02 ON BOTH FP INSTRUMENTS**, and **ONE RUNG IS WORTH ±0.02**: never difference across
  sessions without an anchor; read curves, not rungs. **§28 adds a second reason** cross-block win rates are
  barred — the tie rate spread is 0.011 and points the same way, against the weaker arm.
- **SEEDS DO NOT PAIR BATTLES** (`docs/landmines.md`): every "matched seed-for-seed, McNemar se" phrase was
  UNPAIRED. Replicates are the instrument.
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS ONLY** (maintainer, 2026-09-17); hacking needs none, and
  the anti-self-deception rules do not relax — counters to disk, matched comparisons, same-session anchors.

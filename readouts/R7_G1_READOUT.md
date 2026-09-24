# R7 G1 — the operator in the engine mirror, and how much of it is seeing the hidden state

Written 2026-09-24T02:28:11+00:00 by `scripts/r7_g1_readout.py` (branch `r7-native-search` at `a35ff9b`). **Every number below is re-derived from the rows files at generation time; nothing is typed.** Rule 6: G1 is a mechanism read on the operator, never a win-rate A/B against the credit line (G2 is that, off FP@20).

## Provenance

- G1 rows: `results/r7_g1/g1.rows.jsonl` — sha256 `6f9d86e5d243ee36…`, version `g1_engine_mirror/1`, **15,000 battles** (lop_p1 5,000, lop_p2 5,000, greedy_greedy 5,000); the summary JSON agrees with the rows: **True**. One process, launched 2026-09-23T19:34:54Z (`logs/r7_g1/g1.log`), QoS `background` — niced beside the R6 fleet, so every ms figure here is an efficiency-core timing, not a cost (the B0 bench is the cost).
- Program: the worktree at `9a3e4ae` with B6's second form in progress; the extension it loaded was rebuilt at 2026-09-23T19:33:53Z (`logs/r7_g0/maturin_b6.log`), a minute before launch, from engine sources unchanged through `a35ff9b` (`git diff 9a3e4ae..a35ff9b -- engine/`: empty). The /1 harness predates the launch-SHA stamp (fixed in /2). **The operator G1 ran is the sweep's, bit for bit, across that rebuild:** the belief read's true-world arm takes the sweep's decision keys and reproduces the sweep's cell exactly on the rebuilt extension (override 0.100, regret +0.00404 win-rate: identical = **True**); the sweep was written 2026-09-23T16:30:07Z, before it.
- Committee: `showdown_monster200m_w_s104/ckpt_200000000.pt` (sha `a502af3af5b8`), `showdown_monster200m_w_s112/ckpt_200000012.pt` (sha `add6e89a3fe7`), `showdown_monster200m_w_s120/ckpt_200000003.pt` (sha `33108eadc38c`); bank `teams_a1_5000000.bin`; tables `d2ba00c2ef52`; dials k 4, S 2, τ 0.05, margin gate 0.01 critic units (the sweep's cell, amendment box 4 item 3); 64 battles in flight; seed 20260924.
- The plan's G1 (§6), verbatim: > **G1 — engine self-play, the fast in-block test of the operator.** L-op (true world, B=1, depth-1) vs greedy, both from the same checkpoint, engine mirror matches, n=5,000 per arm, seat-swapped; anchor = greedy vs greedy = 0.5 by symmetry, which is a free instrument check. Override rate reported; the statistical gate (`Q̄(a') − Q̄(a_greedy) ≥ 2·se`) is the matching device. No Showdown, no FP, hours not days.

## The read — win rate from the L-op's seat, ties as half

| arm | seat | battles | win rate ± se | ties | override (of all decisions) | decisions / battle | overrides / battle | battles with ≥ 1 override | mean length ± se |
|---|---|--:|---|--:|--:|--:|--:|--:|---|
| lop_p1 | p1 | 5,000 | 0.5530 ± 0.0070 | 16 | 0.097 | 35.0 | 3.38 | 0.933 | 35.01 ± 0.17 |
| lop_p2 | p2 | 5,000 | 0.5479 ± 0.0070 | 7 | 0.096 | 35.0 | 3.37 | 0.927 | 35.02 ± 0.17 |
| greedy_greedy | p1 (learner) | 5,000 | 0.5080 ± 0.0071 | 12 | 0.000 | 35.5 | 0.00 | 0.000 | 35.53 ± 0.27 |
| **L-op pooled** | both | 10,000 | **0.5504 ± 0.0050** | 23 | 0.096 | 35.0 | 3.38 | 0.930 | 35.02 ± 0.12 |

- **THE READ: the gated L-op beats its own greedy policy by +0.0504 ± 0.0050 win-rate over the seat-balanced symmetric line (10.1 se), at an override rate of 0.096 of all decisions** (3.38 overrides a battle).
- The instrument check: greedy vs greedy (learner in p1) reads 0.5080 ± 0.0071, +1.13 se from 0.5 — passes, and bounds the p1 seat's own advantage.
- Seat-matched against the measured anchor: lop_p1 − anchor = +0.0450 ± 0.0100; lop_p2 − (1 − anchor) = +0.0559 ± 0.0100; their mean, +0.0505, is exactly pooled − 0.5 (the anchor cancels in a seat-balanced pair). The harness's own line, pooled − anchor = +0.0424 ± 0.0086, subtracts a p1-seat anchor from a seat-balanced number: conservative, reported, not the read.
- No seat interaction: lop_p1 − lop_p2 = +0.0051 ± 0.0099. Ties as losses (the locked protocol's convention) move the pooled rate to 0.5493.

## What G1 licenses — and the two advantages G2 will not have

- **It licenses:** the operator is not broken, and the sweep's dials transfer to live play (override 0.096 of every decision in the mirror against 0.100 of G0's positions — a different mix: G0's are turn-stratified simultaneous turns from SAMPLED play, G1's are every decision of GREEDY play, forced ones included). Nothing blocks G2 or the fleet on G1's account.
- **It does not license** any FP@20, vs-SH or ladder number. G1 is the operator's best case twice over: **(1) it searches the TRUE world** — the foe's hidden members, sets and HP are in the leaves; **(2) its foe prior is the committee on the foe's TRUE view, and the foe IS that committee** — the opponent model is exact up to the foe playing its argmax where the L-op models the top-4 mix (that mismatch runs against the L-op). (1) is measured below and in G1b; (2) only G2 can measure.

## The correction: P3's licence at the dials the operator runs (the belief read)

**What amendment box 4 item 4 read.** `scripts/rollout_q_fusion.py` (`rollout_q_fusion/1`) fixes its dials in code — `dials = dict(cols_k=args.critic_cols_k, chance_s=args.critic_chance, tau=1.0)` — and `post_g0.sh` ran it with the defaults (k 3, S 2), no gate: **τ 1.0, where the operator's own true-world action moved 0.006 of G0's 500 positions.** A flip rate of 0.010 between worlds was close to mechanical for an operator that barely moves, and each resampled world carried the foe's TRUE-view prior, re-masked. "P3's licence is INTACT" was a read of the wrong operator.

**The re-read** (`scripts/rollout_q_belief.py`, `rollout_q_belief/2`, git `d8e0ef5`, QoS background): G0's 500 positions × B = 8 resampled worlds at the working dials ({'cols_k': 4, 'chance_s': 2, 'tau': 0.05}, gate 0.01), each world's foe prior recomputed by the committee from that world's foe view; every action scored on G0's own rollout oracle at the true world; worlds refused 0.

| arm | what it is | override | gain ± se, win-rate per decision | gain \| override |
|---|---|--:|---|---|
| true | G1's L-op: the true world, the foe's true-view prior, gated | 0.100 (50) | +0.0040 ± 0.0015 | +0.0404 ± 0.0137 |
| belief | the same L-op on resampled worlds (PIMC), gated — G2's operator | 0.080 (40) | +0.0028 ± 0.0013 | +0.0351 ± 0.0154 |
| t_true | the T-op target's argmax, true world | 0.102 (51) | +0.0040 ± 0.0015 | +0.0394 ± 0.0135 |
| t_avg | argmax of the world-averaged targets — a student's fixed point under true-world targets | 0.084 (42) | +0.0024 ± 0.0013 | +0.0284 ± 0.0147 |
| t_pimc | argmax of the PIMC target — what a B ≥ 2 T-op would teach | 0.082 (41) | +0.0027 ± 0.0013 | +0.0327 ± 0.0152 |

- **The choice depends on the hidden world ~9× more than the fusion pass said:** per-world argmax flips 0.088 ± 0.009 (the fusion pass: 0.010); the belief L-op makes the true L-op's move on 0.54 of the 50 positions where the true L-op overrides; the gated actions differ on 0.066 ± 0.011 of positions; the T-op's target moves TV 0.078 ± 0.006 between the true world and the world average.
- **The value it keeps:** the belief L-op gains +0.0028 ± 0.0013 per decision against the true L-op's +0.0040 ± 0.0015; **the peek, +0.0012 ± 0.0011, is NOT resolved on 500 positions** (the per-decision gains rest on ~50 overrides). G1b measures it at the battle level.
- **The student:** a student trained on true-world targets converges to the world-averaged target (t_avg, +0.0024 ± 0.0013); PIMC targets would teach t_pimc (+0.0027 ± 0.0013). **Fusion cost +0.0003 ± 0.0003 per decision (upper95 +0.0008).**
- **B = 4** (the same first four worlds): belief gain +0.0015 ± 0.0011, peek +0.0025 ± 0.0012, fusion cost -0.0011 ± 0.0006; world_flip 0.090, TV 0.081. The world-dependence reads are stable across B; the belief L-op's gain is not (fewer worlds, a noisier average), and the fusion cost changes sign — it is noise around zero at this n. B = 8 is G1b's.
- **The v′ target** (outcome units, ±1): its peek-optimism, value_fusion_gap = mean_b v′_wb − v′_pimc = +0.0078 ± 0.0008 (positive in every turn bucket: 2-8 +0.0071, 9-15 +0.0074, 16-22 +0.0085, 23-+ +0.0081), is small beside the evaluator's own: the committee critic reads +0.0336 ± 0.0151 above the rollout root value on the same positions, and the root max at τ 0.05 adds +0.0191 ± 0.0054 over the one-step lookahead under the prior. The value target's bias is the evaluator's, not the peek's.

**The plan's rule (§10), verbatim:** > - **The fusion read after B6** shows the true-world action's regret against the belief-averaged action above the credit floor: P3's D19 licence is spent for this object, and the T-op must search B ≥ 2 sampled worlds at training time (cost ×B).

**Read against it: the licence HOLDS at the working dials, now on the right measurement.** Fusion cost upper95 +0.0008 per decision; even summed over the T-op's ~14 searched decisions of a battle it is +0.012, below the +0.025 floor. **The T-op stays B = 1.** What changes is the reading of G1: its operator's choices lean on the hidden world far more than the fusion pass said, so **G1's +0.0504 is an UPPER bound on G2's operator in the same mirror**, and the share the ladder keeps is G1b's to measure.

## G1b — the belief arms in the mirror, paired

| arm | seat | battles | win rate ± se | override | overrides / battle | mean length |
|---|---|--:|---|--:|--:|--:|
| lop_p1 | p1 | 2,500 | 0.5464 ± 0.0100 | 0.097 | 3.43 | 35.40 |
| lop_p2 | p2 | 2,500 | 0.5590 ± 0.0099 | 0.098 | 3.46 | 35.33 |
| greedy_greedy | p1 | 2,500 | 0.5108 ± 0.0100 | 0.000 | 0.00 | 35.43 |
| lop_belief_p1 | p1 | 2,500 | 0.5516 ± 0.0099 | 0.074 | 2.60 | 34.99 |
| lop_belief_p2 | p2 | 2,500 | 0.5590 ± 0.0099 | 0.072 | 2.53 | 35.31 |


- **The belief L-op vs its own greedy, pooled: 0.5553 ± 0.0070 — +0.0553 over the symmetric line (7.9 se), override 0.073.**
- **Belief minus true, PAIRED on 4,993 battles (the same battle seed: the same teams and chance seed, whose draws part once the two arms' actions do): +0.0022 ± 0.0079** (identical outcome on 0.688 of pairs).
- **Read:** the peek's price over a battle is -0.0022 win-rate (belief minus true +0.0022, 95% CI [-0.0132, +0.0176]) -- WITHIN NOISE OF ZERO: the belief operator keeps the true-world operator's gain in this mirror, so the per-decision world dependence the belief read found (box 5) does not reach the battle level, and G1's true-world gain is not a bound G2's operator measurably falls short of here. The mirror is G1's (both seats the R5 committee, greedy but for the L-op); the live test of the belief operator against a different opponent is G2, off FP@20, after the fleet.
- The re-run true-world arms: 0.5527 ± 0.0070 on 5,000 battles.
- **/1 reproduction** (the re-run's rows against /1's, in order, on outcome, length, decisions and overrides): lop_p1 2,500/2,500 identical; lop_p2 2,500/2,500 identical; greedy_greedy 2,500/2,500 identical.
- **The program:** launched 2026-09-23T21:53:45Z at the branch's `e486482` (its HEAD at the guard's start line); the lazily imported modules (rl/search/resample.py, rl/envs/randbats_prior.py) are byte-identical at `e486482` and HEAD, and the rest loaded at launch — one program throughout. The /2 JSON's `launch_git_sha` reads `068ccaf` because /2 stamped it at WRITE time (a harness defect, fixed after this run: the launch sha is now taken before any arm).

## Secondary reads

- Per override: the pooled gain over 3.38 overrides a battle is +0.0149 win-rate per override, against the sweep's +0.0404 conditional on an override at the same cell. The two are scored against different foes and continuations (G0's oracle: both seats SAMPLED; the mirror: both GREEDY), so the sweep's number ranks dials and does not predict a match; the gap is not chased.
- Battle length: L-op battles run 35.02 ± 0.12 turns against 35.53 ± 0.27 greedy-vs-greedy (-0.51).
- Rate (niced, E-cores; not a cost): 57–96 battles/min on the L-op arms at k 64, 15.0 ms per searched decision (median over progress lines).

## Branch

G1 carries no kill clause; it reads the operator as WORKING in its best case. Added by this read: **G1b** (above) prices the peek at the battle level, in the same mirror, before G2 spends a quiet-box block; the T-op stays B = 1 (the licence holds on the right measurement). Where the next steps stand (amendment box 6, rulings of 2026-09-24): **G2** (the L-op's ladder path with belief samples through B6's bridge, whose gate R1-E passed; n = 3,000 per arm off FP@20, the credit line verbatim) is RATIFIED (`configs/eval/r7_g2.yaml` r2) and runs AFTER the R7 fleet, only its two-battle smoke before it; **G3** reads on the fleet's own lanes; and the **evaluator trained on rollout labels** is an own-lap campaign after the fleet — fine-tuning the critic on G0's 500 positions fit them and transferred nothing out of fold (box 5 item 7), so G0-scale data is too small, while the critic's own optimism still dominates the v′ target and the root-rule read named the evaluator the binding constraint (amendment box 4 items 1 and 5).

# R7 G2 — the belief-sampled L-op vs the same committee greedy, off FP@N 25k/12k: **DOES NOT CLEAR**

**Pre-reg:** `configs/eval/r7_g2.yaml`, ratified r2 (2026-09-24), AMENDED r3 before any R-phase battle (2026-09-25:
off FP@N 25k/12k beside the R7 fleet by the maintainer's ruling, voted unanimous; the leaves band re-derived from
G2DOSE by the maintainer's "30-battle measurement first"; plan AMENDMENT BOX 9). **Run:** both arms concurrently in
one `scripts/fp_arms_parallel.py` session, G2G launched first (14:00:47Z) and G2L 16 s later, ended 16:20:36Z and
16:37:53Z, beside the R7 fleet. **Launch commit `c34f49c`, and both arms FINISHED on it too**
(finish_git_sha == launch_git_sha on both: every session held its commits, so the block spans no commit).
**Computed from disk** by `scripts/r7_g2_readout.py` (`results/r7_g2/readout.json`, `readout.md`); every number below
is that script's output or a field of the arms' JSONs.

## The read (the script's output, verbatim)

| arm | win rate (n_eff) | n_eff | crash forfeits | ties | override | lop/leaves_mean | seat ms p50 / p99 | decisions/s |
|---|---|---|---|---|---|---|---|---|
| G2G (committee greedy) | 0.5934 | 3200 | 0 | 4 | — | — | 1.4 / 3.9 | 653.8 |
| G2L (L-op, B 8 x k 4 x S 2) | 0.5947 | 3200 | 0 | 0 | 0.06300924438058869 | 393.69393822660777 | 49.6 / 137.0 | 18.4 |

delta (G2L - G2G, off FP@N 25k/12k): **+0.0013**; se_diff (unpaired binomial, 3200 vs 3200): 0.0123; z +0.10; 2*se_diff 0.0246. Crash forfeits G2L - G2G: +0.

R0 gates:
- `G_FPN_COUNTERS` -- **PASS**: {"G2G": {"fpn_counters_ok": true, "why": [], "iters_exact_rate": 1.0, "budget_line": "[2026-09-25T14:01:27Z] budget verified from foul-play's log: fixed (search_time_ms=20, search_iterations=25000/12000)", "budget_25k_12k": true}, "G2L": {"fpn_counters_ok": true, "why": [], "iters_exact_rate": 1.0, "budget_line": "[2026-09-25T14:01:43Z] budget verified from foul-play's log: fixed (search_time_ms=20, search_iterations=25000/12000)", "budget_25k_12k": true}}
- `G_CONTROL_FIRST` -- **PASS**: {"g2g_line": "[2026-09-25T14:00:47Z] G2G LAUNCHED runner pid 6548 (budget 25000; c6 off)", "g2l_line": "[2026-09-25T14:01:03Z] G2L LAUNCHED runner pid 6607 (budget 25000; c6 off)", "one_scheduler_session": true}
- `G_SAME_PROGRAM` -- **PASS**: {"rl_package": ["/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/rl", "/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/rl"], "rl_git_sha": ["c34f49c910709fd95506c59ef46bd894fb0a6d30", "c34f49c910709fd95506c59ef46bd894fb0a6d30"], "rl_git_dirty": [false, false], "launch_git_sha": ["c34f49c910709fd95506c59ef46bd894fb0a6d30", "c34f49c910709fd95506c59ef46bd894fb0a6d30"]}
- `G_RUNNER` -- **PASS**: {"G2G": {"relaunches": 0, "max_relaunches": 30, "void_too_many_crashes": false, "all_challenges_resolved": true, "tally_agrees": true, "mask_desyncs": 0}, "G2L": {"relaunches": 0, "max_relaunches": 30, "void_too_many_crashes": false, "all_challenges_resolved": true, "tally_agrees": true, "mask_desyncs": 0}}
- `G_OPERATOR_RAN` -- **PASS**: {"searched_frac": {"value": 0.9569635329035673, "rule": ">= 0.5", "ok": true}, "worlds_built_rate": {"value": 0.9849208588300532, "rule": ">= 0.9", "ok": true}, "no_world_rate": {"value": 0.014651114429929864, "rule": "<= 0.1", "ok": true}, "mask_mismatch_rate": {"value": 0.0, "rule": "<= 0.001", "ok": true}, "errors_per_world": {"value": 0.0, "rule": "<= 0.001", "ok": true}, "override_rate": {"value": 0.06300924438058869, "rule": "in (0.02, 0.2)", "ok": true}, "leaves_mean": {"value": 393.69393822660777, "rule": "in (276.1, 460.3)", "ok": true}, "error_types": {}, "refused": {"W-ACTIVESTATS": 12400.0}}
- `G_SESSION` -- **PASS**: {"prereg_sha256": ["1cd222a93bf75ce6b299b5dfe83b93c1842ee5c361c10161c44e02a51d42008a", "1cd222a93bf75ce6b299b5dfe83b93c1842ee5c361c10161c44e02a51d42008a"], "note": "the delta is G2L - G2G only; no banked number enters"}
- `G_TIES` -- **PASS**: {"ties": {"G2G": 4, "G2L": 0}}
- `G_CONCURRENCY` -- **PASS**: {"concurrent_decision_rate": {"G2G": 0.0, "G2L": 0.0}, "max_concurrent_live_battles_DISCLOSED": {"G2G": 1, "G2L": 1}}
- `G_MATCHED_GREEDY` -- **PASS**: {"summary": "7 passed in 10.81s", "launch_sha_in_log": true}

G2G_SANITY (DISCLOSURE ONLY, never a gate; two instruments): G2G 0.5934 off FP@N 25k/12k (the R5 W committee's FIRST FP@N number) beside §35's XGR 0.5866 off FP@20 (n 3200). Never differenced; no pass/fail at the calibration's level CI95 [-0.026, +0.011].

**DOES NOT CLEAR** -- neither clears nor negative -> the ladder stays greedy; the training side proceeds anyway (plan §6: G0 said the prize exists and the evaluator is what the fleet trains). NOT the real-budget null, and at this power a non-clear is LIKELY even if the operator works (the POWER block): the next L-op arm raises the budget (B >= 16 worlds; rollout leaves on close calls) before anything is concluded about search at the ladder.

Disclosures: FP@N 25k/12k with its calibration (two seats vs FP@20, NON-REJECTION, offset CI95 [-0.026, +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054): G2's primary is a gap, so this is a verdict off FP@N, never a translated FP@20 result. The equivalence test is weakly powered, and the point estimate flatters us. Measured beside the R7 fleet: the seat ms and decisions/s are load-inflated, and the per-decision budget is the leaves. Every seat sends /timer on.

## In one paragraph

The committee searched by the L-op won **0.5947** (1903/3200) against
Foul Play at FP@N 25k/12k; the same committee greedy won **0.5934** (1899/3200).
Delta **+0.0013**, se_diff 0.0123, z +0.10, CI95 [-0.0228, +0.0253]. Every R0 gate
PASSES, so the read is valid and the pre-registered branch is **DOES NOT CLEAR**: the ladder stays greedy and the
training side proceeds. The one-sided upper95 is +0.0214: at THIS operator and THIS budget (~394
leaves a searched decision, overriding greedy on 6.3% of decisions), a credit-sized effect
off FP@N is not what happened. It says nothing about search at a larger budget or with another evaluator (CLAUDE.md
rule 6; the pre-reg: "NOT the real-budget null"). The pre-reg's POWER block had called a non-clear likely even if the
operator works (power ~0.50 at a true +0.025).

## The per-turn budget (quoted with every number)

B 8 worlds × k 4 × S 2 at depth 1. Realized: `lop/leaves_mean` **393.7** a searched decision
(the budget); searched 101241 of 105794 decisions (3003 forced);
overrides 6666 (override rate 0.0630; argmax moved on
0.0672 of searched decisions; margin mean 0.0076). Seat ms p50/p99:
G2L 49.6/137.0, G2G 1.4/3.9;
seat decisions/s G2L 18.4, G2G 653.8 -- LOAD-INFLATED, measured beside
the fleet, so the leaves are the budget to quote. Mean turns 28.96 / 29.11.

## Disclosures

- **FP@N 25k/12k and its calibration:** two seats vs FP@20, NON-REJECTION, offset CI95 [-0.026, +0.011], gap-change
  CI95 [-0.042, +0.033], MDE 0.054. G2's primary is a gap, so this is a verdict off FP@N, never a translated FP@20
  result; never differenced across instruments. The equivalence test is weakly powered, and the point estimate flatters us.
- **G2G 0.5934 is the R5 W committee's FIRST FP@N number.** §35's XGR 0.5866 is FP@20; they are printed
  side by side (G2G_SANITY, a disclosure only) and never differenced.
- **The leaves band mattered.** The realized 393.7 is inside r3's [276.1, 460.3], re-derived BEFORE
  the R phase from G2DOSE (368.19; the maintainer's "30-battle measurement first"), and BELOW
  r2's ratified [400, 700], which came from build smokes not on disk. **Under r2's band this pair would have VOIDED.**
  The two live smokes had read 360.7 and 371.6; the leaf count is fixed per position, so its mean follows the live
  battles' position mix, never load or the instrument.
- **Refused worlds:** 12400 worlds refused by the bridge (family W-ACTIVESTATS);
  worlds built 0.9849, no-world decisions 0.0147 (they play the control's action:
  dilution, not bias); mask mismatches 0.0, errors 0.0.
- Crash forfeits 0 and 0; relaunches 0 and 0; ties 4 (G2G) and 0 (G2L), non-wins;
  mask desyncs 0; Foul Play's own tallies agree with both seat JSONs on n_eff exactly. Every seat sends /timer on.
- **Two corrections to the pre-reg's header, found this week:** its "~0.2 s a decision" predates the smoke (~25 ms idle;
  54.5 ms mean here under load); and "the ladder allows ~150 s a turn" overstates the clock, which is a 150 s
  bank refilling +10 s a turn and charged in 5-s ticks (`showdown/server/room-battle.ts`), so ~10 s a turn is sustained.

## What comes next

The pre-reg's does-not-clear branch: "the next L-op arm raises the budget (B >= 16 worlds; rollout leaves on close
calls) before anything is concluded about search at the ladder". Two Opus reviews of the inference budget (2026-09-25)
put the room on the LEAF-EVALUATOR axis: G0's best critic-leaf operator captures +0.0040 ± 0.0014 of the +0.0236 ± 0.0028
per-decision rollout ceiling (`readouts/R7_G0_READOUT.md`). The maintainer approved measuring that first at the decision
level (rollouts vs critic leaves on G0's 500 banked roots, matched override), then a battle-level read of a rollout
operator at the knee after R7's reads. JOURNEY 14's exit condition ("at a REAL budget") stays owed.

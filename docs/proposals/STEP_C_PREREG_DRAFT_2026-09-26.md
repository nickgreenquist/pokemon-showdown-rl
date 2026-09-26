# STEP C — DEEP SEARCH IN TRAINING: the pre-reg, DRAFT (2026-09-26)

**Status: DRAFT r3, not ratified. Its four rulings (§0) were DECIDED on 2026-09-26 by the three agent sessions**, as
the maintainer asked ("Ask the other two sessions for their opinion. You decide among the 3 of you and then go for
review"). The record, with every condition written in, is §8. Two Opus reviews come next.

It builds on `docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step C and adds the 09-26 reads that set its dose,
its form and its mechanism. The standing ruling holds throughout: *"I do NOT want you to kill search in train if 1-ply
doesn't work"* (CLAUDE.md rule 6). Nothing below decides WHETHER Step C runs; the reads set its FORM and DOSE.

**journey_step: "14"**, whose exit condition reads verbatim: "one comparison at a REAL budget, on the strongest gen-1
object we have. Search-with-our-evaluator vs the same checkpoint greedy, pooled under the standing credit line, with
decisions/sec reported for both arms and the per-turn budget named in every quote." Step C is not that comparison
(Step B is). Like R7, it trains the objects such a comparison uses and credits ONE training lever.

## 0. The four rulings, DECIDED (2026-09-26, the three sessions)

### D1 — THE BUDGET: +100M steps per lane in <= 4 days of the box, 3 + 2 lanes

- Sunday's quiet-box width bench measures a lane's steps/s with the TreeOp at the dose. `frac`, the searched
  fraction, is lowered to fit BEFORE the dose is ever touched.
- **`frac`'s FLOOR** (r6-runner; fp-speedup) is the larger of 0.25 (KataGo's playout-cap p) and the level where the
  KL term stays not-inert. The beta* smoke ladder and the not-inert check run AT THE FLEET'S `frac`, not only at the
  smokes'.
- **The pre-stated action:** if +100M in <= 4 days needs `frac` below the floor, run fewer steps, or the maintainer
  rules on more days or fewer lanes. Never a thinner lever that can read null for dose reasons.
- The width bench NEVER overlaps fp-speedup's FP@500 calibration reference (REF500 VOIDs above 5% contaminated
  minutes).

### D2 — THE LEVER'S FORM: the tree's soft_br POLICY TARGET at B = 1, TreeStrap stacked beside it on an EVALUATOR head; `play: false`; v' into the evaluator head

- **THE FORM IS soft_br, not completed-Q** (fp-speedup's finding, reproduced on the instrument). A student of B = 1
  targets converges to their mean over the hidden world, its FIXED POINT. On that learnable objective (§1):
  - the soft_br target (tau 0.05) keeps **+0.0019 ± 0.0010 (z 1.91) over R7's one-ply target**;
  - completed-Q keeps ~0: +0.0003 ± 0.0014 at the true-world sigma, and +0.0008 even with sigma chosen on the fixed
    point, which is -0.0011 ± 0.0004 (z -2.95) against soft_br's fixed point.
  - Completed-Q's true-world +0.0044 (z 2.76) is almost all PEEK: true minus fixed point +0.0041 ± 0.0016.
  - Completed-Q is the form ONLY under a joint belief tree, where the two tie (+0.0005 ± 0.0017).
  - Whichever form, its dials are chosen on the FIXED POINT's expected improvement, never the true world's.
- **The learnable number is at the floor.** +0.0019 is z 1.91, suggestive rather than resolved. Times ~14 searched
  decisions a battle, it puts the B = 1 policy channel's ceiling at ~+0.027 a battle: AT the +0.025 floor, and
  optimistic (full distillation, additive per-decision gains). The joint 8-world target's is ~+0.043. These are
  planning numbers, never a kill (rule 6), and the strongest case for stacking TreeStrap.
- **TREESTRAP, on an EVALUATOR head** (fp-speedup's alternative to a critic-side lever):
  - The labels train a SEPARATE evaluator head (R7's v' aux head, extended; at the warm start it is initialised from
    the critic where the donor's aux head is untrained), and the TreeOp reads THAT head at its leaves.
  - The GAE critic stays PPO's baseline, untouched by the labels. The lever is then actor-neutral on the advantage
    path by construction (D18's falsifier).
  - Each label is (the node's obs from OUR information set in the true world, the NON-OPTIMISTIC backup E_{a~pi'}
    E_{b~prior} Q at the node): v''s own form, NEVER a max over our moves with the foe fixed. That max is G1's +0.019
    of optimism and the `_look_further` landmine. Nodes with N >= N_min are labelled.
  - At B = 1 the peek sits in the labels too (true-world backed-up values). The evaluator can only learn their mean
    over worlds, the posterior mean, which is the right target for an observation-measurable evaluator.
  - Counters: labels a decision; the labelled nodes' depth histogram; the label-vs-head gap; the evaluator head's
    loss.
  - **A pre-smoke LABEL-QUALITY READ** on the E-cores (fp-speedup): at nodes with N >= 16 on G0's roots, the label vs
    the raw critic vs a rollout value of the node. It sets N_min and shows whether the labels carry signal. If they
    carry none, TreeStrap goes to its own lap.
  - **FALLBACK, if the evaluator head's build is not green:** the labels train the GAE critic, with the ON-POLICY
    CRITIC STOP CONDITION below as the named counter and action.
- **ON-POLICY CRITIC COUNTERS, a STOP CONDITION** (r6-runner; a critic-side effect is not actor-neutral in PPO): the
  GAE critic's value loss and explained variance on the rows each lane actually played, searched vs control, every
  update. A searched-arm EV that falls away from its pair's goes to the maintainer mid-fleet, never a silent
  continuation.
- **IF TREESTRAP IS NOT GREEN AT LAUNCH** (r6-runner): the maintainer rules between launching the policy target alone,
  with TreeStrap on its own lap, and holding the fleet. It is named now so it is not improvised.

### D3 — THE CONTROL: mechanical from R7's verdict (§6), with the X-POS / X-GAIN case STATED

- Under X-POS / X-GAIN, R7's credited recipe is `play: true`, `frac` 0.75, search_policy_coef 0.1
  (`configs/r7_fleet_searched_f1.yaml`).
- **C = that credited recipe UNCHANGED** (fp-speedup's preference). **S = the same base with the one-ply T-op
  REPLACED** by the deep TreeOp at 256, `play: false`, the soft_br target, TreeStrap and the evaluator head.
- The lever is named as the WHOLE difference: {depth, `play` true -> false, the evaluator head + TreeStrap}. The
  target form is soft_br tau 0.05 on both sides, so the form is not part of the difference.
- The mechanism reads and the clip-split / grad-norm counters attribute within it (§5). r2's "isolates DEPTH" was not
  true as written, and is withdrawn.
- Otherwise C is R7's base (no T-op) and S = the base + the lever. The finals R7's verdict names are warm starts,
  paired by final.

### D4 — WORLDS PER SEARCH: B = 1 at 256 simulations, with the soft_br target; the fusion read at depth disclosed as UNRESOLVED

- **The B = 2 switch, a rule stated before its read** (r6-runner; fp-speedup):
  - B = 2 runs over BELIEF worlds only. A true world inside a B >= 2 tree brings the peek back.
  - Each world is searched at the depth floor, ~2x B = 1's cost.
  - B = 2 replaces B = 1 iff its student fixed point beats B = 1's soft_br fixed point, paired, at z >= 2, AT EQUAL
    TOTAL COST (B = 2's `frac` halved), AND the halved `frac` stays above the floor.
  - The fixed-point read runs on the E-cores (G0, decision level); the cost is measured on the quiet box.
- Why B = 1 now: it is the cheapest, and it carries the only learnable number measured at 256. The joint target has
  headroom (+0.0031 over one ply, z 2.72) at 8x the work.

## 0.5 POWER (r6-runner; `results/native_tree/stepc_power.json`, scripts/r7_fleet_power.py's model)

At 3 + 2 and n 6000 per lane the median se_diff is 0.0062 (pooled-binomial 0.0059). So 2 * se_diff is ~0.012 and the
+0.025 SIZE FLOOR binds; it stops binding only if the two-control-lane clustered se exceeds ~0.0125.

P(X-POS) at a true:
- +0.019: 0.20 (X-GAIN 0.50);
- +0.027 (B = 1's optimistic ceiling): 0.60 (X-GAIN 0.32);
- +0.043 (the joint target's ceiling): 0.99.

Said plainly: at B = 1, a non-clear is LIKELY unless the optimistic ceiling is reached in full.

## 1. The evidence (every number traced; `results/native_tree/*.summary.*` and `stepc_a.stepc.*`, SESSION_LOGS 2026-09-26)

- **Gate (i-c)** (`oracle_c`): at 1,800 simulations the belief tree is +0.0020 over the one-ply critic L-op at the
  matched override (z 1.37, its best rule). br_prior is the estimand: legacy -0.0041 at z -2.78 and sm_rm -0.0055 at z
  -3.55 against it.
- **Tier 1** (`tier1_a`): FLAT from 1,800 to 28,800 simulations. Depth over equal-work breadth is ~+0.002 at every
  rung and never grows. The evaluator binds, not depth.
- **Tier 1b** (`tier1b_a`): in the TRAINING setting (true world, B = 1), the tree's gated ARGMAX ties the one-ply T-op
  at 256 / 1,024 / 1,800 simulations (matched at 0.100; every |d| < 1 se). The depth floor (mean >= 2.5 turns) is met
  at 256: 2.89 turns, 228 leaves, ~4.5x the one-ply's ~51.
- **Step C's E-core inputs** (`stepc_a`; expected improvement, EI, over greedy on G0's oracle, win rate per decision,
  of the full target distribution):

| target | true world (with the peek) | STUDENT'S FIXED POINT (learnable) |
|---|---|---|
| R7's one-ply T-op (soft_br tau 0.05) | -0.0001 ± 0.0013 | (the reference) |
| deep soft_br (tau 0.05) | +0.0031 ± 0.0014 | **+0.0018 ± 0.0011; over one ply +0.0019 ± 0.0010 (z 1.91)** |
| deep completed-Q, sigma chosen on the true world | +0.0043 ± 0.0020 (held out) | +0.0002 ± 0.0016; over one ply +0.0003 (z 0.22) |
| deep completed-Q, sigma chosen on the fixed point | -- | +0.0008 ± 0.0011 (held out); vs soft_br's fixed point -0.0011 ± 0.0004 (z -2.95) |
| joint B = 8 tree (no peek; 8x the work) | soft_br +0.0030; completed-Q +0.0035 (tie: +0.0005 ± 0.0017) | the same (a joint target has no peek) |

  - FUSION AT DEPTH: +0.00058 ± 0.00106 per decision. x14 a battle: 95% [-0.021, +0.037] vs the 0.025 floor:
    UNRESOLVED.
- **R7's counters** (the searched lane f1 over its last 5M steps; the record-only control's matched baseline): PPO
  clips 51.2% of searched rows vs 15.9% on the same selection in the record-only twin, ~3.2x at one ply. So **play:
  false** is Step C's design.
- **Stage 0c:** rollout leaves beat critic leaves at one ply (+0.0027 at z 2.02 at R 128, still rising to 512). The
  evaluator axis is where search has shown room, which is TreeStrap's reason to exist.

## 2. The lever (arm S): the collector's TreeOp

`rl/search/tree_top.py::TreeOp` is built and tested on `deep-search-step-a`; `searcher_class(spec)` picks it for a
block that carries `tree`. Its dials are derived from its signature, and unknown keys fail.
- **Dose:** 256 TOTAL simulations on the TRUE world (B = 1, D4); br_prior, the root grid, depth cap 8, cols_k 4,
  chance_k 2. The learner's own actor serves as prior, and the EVALUATOR HEAD (D2) as the leaf. TreeOp refuses an
  antisymmetric or privileged critic.
- **Which rows:** eligible rows as R7's (> 1 legal action, pi_theta top-1 < 0.97), searched on a coin at `frac`
  (D1).
- **Behaviour:** `play: false`. The lane plays pi_theta, so its data stay on-policy.
- **Policy target:** the tree's soft_br pi' at tau 0.05 (D2), trained as beta * KL(pi' || pi_theta) on searched rows.
  beta warms up 0 -> beta* over ~5M steps. beta* comes from a 2M smoke ladder at the fleet's `frac` under R7's
  not-inert rule.
- **Value target:** v' = E_{a~pi'} E_{b~prior} Q(a,b) into the evaluator head, NEVER the root max (G1: +0.019 of max
  optimism).
- **TreeStrap:** as D2 states it: evaluator head, non-optimistic labels, our information set, N >= N_min from the
  label-quality read.
- **The control (arm C):** D3. A searched/control pair differs EXACTLY in {seed, run_name, seat_tag, the search block,
  the coefficients, `play`}, and a test pins that.

## 3. R0 gates (before launch; each with its action on a FAIL)

1. **THE LABEL-QUALITY READ** (E-cores, before the smokes). No signal -> TreeStrap to its own lap (D2).
2. **THE WIDTH BENCH** (quiet box, nice 0, never overlapping REF500): `native_tree_gates.py bench`'s training rungs
   plus a collector-throughput bench with weights lag <= 1. It gives each lane's steps/s at the dose and `frac`. Under
   D1's floor -> D1's pre-stated action; never a smaller dose.
3. **THE DEPTH FLOOR** in the bench: `tree/turns_mean` >= 2.5 at 256 simulations. FAIL -> 512, re-bench.
4. **THE SMOKES** (400k, searched + control, warm from one final): every counter on every update row (search/*,
   tree/*, the TreeStrap and evaluator-head counters, fallback_frac, batch_rows, the on-policy critic counters); the
   KL term not inert AT THE FLEET'S `frac`; a resume mid-smoke reproduces. FAIL -> no fleet.
5. **THE LR RULE** (a third anneal, disclosed), as R7's.
6. **DISK:** +~6 GB a lane (CLAUDE.md's disk rule).

## 4. The fleet

- 3 + 2 (or 3 + 3 by the width bench, as R7's R-F2). Fewer lanes weaken the seed-clustered se.
- **Steps:** +100M; `frac` fits the 4 days, subject to D1's floor.
- Warm from the finals R7's verdict names, paired by final.

## 5. The reads (the same instruments as R7's, so no read is differenced across instruments)

- **PRIMARY:** off FP@N 25k/12k, greedy, loop breaker off, n 6000 per lane, one scheduler session in a pinned
  control-first order. 30k battles, ~2.4-2.6 h at 8 slots on fp-speedup's ROI numbers.
  - delta = the equal-weight mean of the searched finals minus that of the control finals. se_diff = the LARGER of the
    pooled-binomial and the seed-clustered se_diff.
  - CREDIT LINE, verbatim (CLAUDE.md): "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff
    is the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed
    finals at read time." STRICT at both boundaries.
  - Cells X-POS / X-GAIN / X-COST / X-NEG / X-FLAT with R7's actions (`scripts/r7_reads_readout.py` generalises).
  - **An arm whose runner JSON has `fpn_counters_ok` false is INVALID**: it re-runs LAST on its rerun pair and is
    never pooled.
  - **Every quote names "FP@N 25k/12k" with its calibration** (two seats vs FP@20, NON-REJECTION, offset CI95 [-0.026,
    +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054) and the two disclosures: the equivalence test is weakly
    powered, and the point estimate flatters us.
- **MECHANISM READS**, searched minus control, paired by donor, with R7's MOVED rule:
  - (i) KL(pi' || pi_theta), LOWER: the manipulation check.
  - (iii) the evaluator head's AND the critic's Spearman on G0, HIGHER.
  - (vi) the greedy's split-sample regret on G0, LOWER.
  - (vii) NEW: the evaluator head's error on TREE states against their rollout values (TreeStrap's own target), LOWER.
  - (viii) NEW: the EI of the searched arm's pi' at its FIXED POINT on G0's oracle (stepc_a's instrument), HIGHER.
  - The BEHAVIOUR channel: the clip_frac split and loss/grad_norm per arm. They attribute D3's `play` difference.
  - STOP CONDITION (D2): the on-policy critic's value loss and EV on played rows, searched vs control.
- **Secondary:** vs SH (locked); the object rule, as R7's.

## 6. R7's outcome -> Step C's design (r2's mapping, corrected by D3; never whether it runs)

- **X-POS / X-GAIN:** C = R7's credited recipe unchanged; S replaces its one-ply T-op with the lever. The difference is
  the whole lever (D3).
- **X-FLAT, (i) not moved:** the target form is the suspect, so beta is a ladder, and CE is sooner.
- **X-FLAT, (i) moved and (vi) not:** the value channel is the suspect. TreeStrap on the evaluator head is ON, as D2
  already has it.
- **Moved with delta <= 0, or X-COST / X-NEG:** `play: false` is mandatory, as it already is here.
- **VOID:** R7's control recipe on the R6 trio B donors.

## 7. What changes the plan, and what does not

- **Changes it:**
  - the fusion read at depth (UNRESOLVED; a resolved SPENT forces B >= 2 at x B the cost);
  - the B = 2 fixed-point read under D4's rule;
  - the width bench (`frac` and steps under D1's floor);
  - the label-quality read (TreeStrap in or on its own lap).
- **Read, 09-26 (stepc_a + fp-speedup's fixed-point read):** the policy-target channel measures ONLY in soft_br form at
  B = 1, and only at z 1.91. Completed-Q's learnable part is ~0.
- **Does not change it:** a null or a cost at any one budget (rule 6); R7's verdict (it sets the control and the
  suspect channel, never whether this runs).

## 8. The three-session decision (2026-09-26)

- **r7-runner** proposed D1-D4 (r1: completed-Q, B = 1, +100M in <= 4 days, the control from R7's verdict).
- **r6-runner AGREED on all four**, with conditions now in §0 and §0.5:
  - the learnable number as the policy channel's;
  - the ~+0.027 ceiling at the floor, and the power block;
  - `frac`'s floor at the fleet's `frac`;
  - TreeStrap's non-optimistic backup from our information set;
  - the on-policy critic stop condition;
  - the not-green branch;
  - the B = 2 rule.
  Its draft fixes are applied.
- **fp-speedup: D1 AGREE** (+ the 0.25 floor with its action; never overlapping REF500); **D2 AGREE on the structure,
  DISAGREE with completed-Q at B = 1.** Its offline fixed-point read, reproduced exactly on the instrument (branch
  `074f593`), shows completed-Q's learnable part ~0. It asked that dials be chosen on the fixed point, and that
  TreeStrap be put on an evaluator head or given a named counter. **D3 AGREE**, with the X-POS control stated
  (adopted: C = the credited recipe unchanged). **D4 AGREE**, with the soft_br form; the B = 2 rule is at equal cost,
  over belief worlds only, at the depth floor. It also supplied §5's FP validity and disclosure lines and the sizing.
- **The decision:** D1, D3 and D4 carry three of three. D2's STRUCTURE carries three of three. D2's FORM (soft_br at B
  = 1) carries two of three (r7-runner + fp-speedup) on the fixed-point evidence. It is also the form r6-runner's own
  learnable-number condition cites. r6-runner is informed and may object before the Opus reviews close.
- The maintainer's rulings remain open only where a condition sends a case back to him: D1's floor, D2's not-green
  branch, and a mid-fleet stop.

# STEP C — DEEP SEARCH IN TRAINING: the pre-reg, DRAFT (2026-09-26)

**Status: DRAFT r2, not ratified.** Its four rulings (§0) were DECIDED on 2026-09-26 by the three agent sessions, as
the maintainer asked ("Ask the other two sessions for their opinion. You decide among the 3 of you and then go for
review"). r7-runner proposed and r6-runner agreed on all four, with conditions that are now written in; fp-speedup's
vote is recorded in §8. Two Opus reviews come next. It builds on
`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step C and adds the 09-26 reads that set its dose and its
mechanism. The standing ruling holds throughout: *"I do NOT want you to kill search in train if 1-ply doesn't work"*
(CLAUDE.md rule 6). Nothing below decides WHETHER Step C runs; the reads set its FORM and DOSE.

**journey_step: "14"**, whose exit condition reads verbatim: "one comparison at a REAL budget, on the strongest gen-1
object we have. Search-with-our-evaluator vs the same checkpoint greedy, pooled under the standing credit line, with
decisions/sec reported for both arms and the per-turn budget named in every quote." Step C is not that comparison
(Step B is); like R7, it trains the objects such a comparison uses and credits ONE training lever.

## 0. The four rulings, DECIDED (2026-09-26, the three sessions; conditions from r6-runner written in)

- **D1 — THE BUDGET: +100M steps per lane in <= 4 days of the box, 3 + 2 lanes.** Sunday's quiet-box width bench
  measures a lane's steps/s with the TreeOp at the dose. `frac` (the searched fraction) is lowered to fit BEFORE the
  dose is touched.
  - A FLOOR ON `frac` (r6-runner): the beta* smoke ladder and the not-inert check run AT THE FLEET'S `frac`, not only at
    the smokes'. If the budget would push `frac` below the level where the KL term stays not-inert, it goes back to the
    maintainer (more days, or fewer lanes). A diluted lever is never launched.
- **D2 — THE LEVER'S FORM: (c), the completed-Q POLICY TARGET as the channel that measured, TreeStrap stacked beside
  it as a counted dial; `play: false`; v' into R7's aux head.**
  - THE LEARNABLE NUMBER (r6-runner). A student of B = 1 targets converges to their average over the hidden world. Its
    fixed point keeps **+0.0019 ± 0.0010 (z 1.91)** of expected improvement over R7's one-ply target, and that is the
    policy channel's number. The true-world target's +0.0044 ± 0.0016 (z 2.76) INCLUDES THE PEEK, which no student can
    learn.
  - Times ~14 searched decisions a battle, the B = 1 policy channel's ceiling is ~+0.027 a battle: AT the +0.025
    floor, and optimistic (full distillation, additive per-decision gains). The joint 8-world target's is ~+0.043.
    Planning numbers, never a kill (rule 6). This is the strongest case for stacking TreeStrap.
  - TREESTRAP LABELS use the SAME non-optimistic backup as v': E_{a~pi'} E_{b~prior} Q at the node. NEVER a max over
    our moves with the foe fixed; that is G1's +0.019 of max optimism and the `_look_further` landmine, and the
    label-vs-critic-gap counter would then read optimism as learning. Each internal node's obs is rendered from OUR
    information set in the true world (the tracked view), so the regression's fixed point is the posterior mean.
  - ON-POLICY CRITIC COUNTERS, a STOP CONDITION (a critic-side lever is not actor-neutral in PPO, CLAUDE.md
    conventions): value loss and explained variance on the rows each lane actually played, searched vs control,
    watched beside labels/decision and the labelled nodes' depth histogram.
  - IF TREESTRAP IS NOT GREEN AT LAUNCH (it is not built yet; the TreeOp is): the maintainer rules between launching
    the policy target alone (TreeStrap to its own lap) and holding the fleet. This branch is named now so it is not
    improvised.
- **D3 — THE CONTROL.** Whatever base R7's verdict names (§6), warm from its finals and paired by final. It follows
  mechanically from Sunday's readout.
- **D4 — WORLDS PER SEARCH: B = 1 at 256 simulations**, the fusion read at depth disclosed as UNRESOLVED.
  - B = 2 at EQUAL TOTAL simulations is benched beside it on Sunday's quiet box, under a rule stated now (r6-runner),
    so the bench is a read, not a debate: **B = 2 replaces B = 1 iff its student fixed point beats B = 1's, paired, at
    z >= 2, AND the width bench fits it above `frac`'s floor.**
  - Why: B = 1's learnable ceiling sits at the credit floor, and the joint target has headroom.

## 0.5 POWER (r6-runner; `results/native_tree/stepc_power.json`, scripts/r7_fleet_power.py's model)

At 3 + 2 and n 6000 per lane the median se_diff is 0.0062 (pooled-binomial 0.0059), so 2 * se_diff is ~0.012 and the
+0.025 SIZE FLOOR binds. It stops binding only if the two-control-lane clustered se exceeds ~0.0125. P(X-POS) at a
true:
- +0.019: 0.20 (X-GAIN 0.50);
- +0.027 (B = 1's optimistic ceiling): 0.60 (X-GAIN 0.32);
- +0.043 (the joint target's ceiling): 0.99.
Said plainly: at B = 1, a non-clear is LIKELY unless the ceiling is reached in full.

## 1. The evidence (every number traced; `results/native_tree/*.summary.*`, SESSION_LOGS 2026-09-26)

- **Gate (i-c)** (`oracle_c`): at 1,800 simulations the belief tree is +0.0020 over the one-ply critic L-op at the
  matched override (z 1.37, its best rule). br_prior is the estimand (legacy -0.0041 at z -2.78, sm_rm -0.0055 at z
  -3.55 against it).
- **Tier 1** (`tier1_a`): FLAT from 1,800 to 28,800 simulations. Depth over equal-work breadth is ~+0.002 at every
  rung and never grows. The evaluator binds, not depth.
- **Tier 1b** (`tier1b_a`): the TRAINING setting (true world, B = 1) ties the one-ply T-op at 256 / 1,024 / 1,800
  simulations (matched at 0.100; every |d| < 1 se). The depth floor (mean >= 2.5 turns) is met at 256 (2.89 turns, 228
  leaves, ~4.5x the one-ply's ~51).
- **Step C's E-core inputs** (`stepc_a`, `results/native_tree/stepc_a.stepc.md`, SESSION_LOGS 12:15Z). Expected
  improvement over greedy on G0's oracle, win rate per decision:
  - R7's one-ply T-op target: -0.0001 ± 0.0013.
  - The deep soft_br target: +0.0031.
  - The completed-Q target: +0.0043, held out.
  - Paired, completed-Q minus one-ply: +0.0044 ± 0.0016 (z 2.76).
  - The B = 1 student's fixed point: +0.0019 over one ply (z 1.91).
  - The joint B = 8 target: +0.0031 (z 2.72, at 8x the work).
  - FUSION AT DEPTH: +0.00058 ± 0.00106 per decision. x14 a battle: 95% [-0.021, +0.037] vs the 0.025 floor, so
    UNRESOLVED.
  - SIGMA: a ridge at c_scale 0.1; c_visit 100-200 best, and the MCTX default is within ~10%.
- **R7's counters** (the searched lane f1 over its last 5M steps; the record-only control's matched baseline): PPO
  clips 51.2% of searched rows vs 15.9% on the same selection in the record-only twin (~3.2x at one ply), so
  **play: false** is Step C's design.
- **Stage 0c**: rollout leaves beat critic leaves at one ply (+0.0027 at z 2.02 at R 128, still rising to 512). The
  evaluator axis is where search has shown room.

## 2. The lever (arm S): the collector's TreeOp

`rl/search/tree_top.py::TreeOp` (built and tested on `deep-search-step-a`; `searcher_class(spec)` picks it for a
block that carries `tree`). Its dials are derived from its signature, and unknown keys fail.
- **Dose:** 256 TOTAL simulations on the TRUE world (B = 1 by D4; the fusion read at depth is UNRESOLVED and
  disclosed; B = 2 is benched beside it); br_prior, the root grid, depth cap 8, cols_k 4, chance_k 2. The
  learner's OWN actor and critic serve as prior and leaf (TreeOp refuses an antisymmetric or privileged critic).
- **Which rows:** eligible rows as R7's (> 1 legal action, pi_theta top-1 < 0.97), searched on a coin at `frac` (a
  benched fraction; KataGo's playout-cap randomization). `frac` comes from D1 and the width bench (§4).
- **Behaviour:** `play: false` (§1). The lane plays pi_theta, so its data stay on-policy.
- **Policy target:** the completed-Q pi' at sigma c_visit 100, c_scale 0.1 (stepc_a's split-sample choice; the ridge
  is flat to within ~10% across c_visit 25-200), trained as beta * KL(pi' || pi_theta) on
  searched rows. beta warms up 0 -> beta* over ~5M steps; beta* comes from a 2M smoke ladder under R7's not-inert
  rule.
- **Value target:** v' = E_{a~pi'} E_{b~prior} Q(a,b) into R7's aux head, NEVER the root max (G1: +0.019 of max
  optimism).
- **TreeStrap (D2):** the tree's internal nodes with N >= 16 each contribute (obs of that node, its backed-up value)
  to the critic's loss at a counted weight. The value is the NON-OPTIMISTIC backup, E_{a~pi'} E_{b~prior} Q at the
  node (v''s own form, never a max over our moves), and the obs comes from OUR information set in the true world. These are the hypothetical states JOURNEY 14 names. Counters:
  labels/decision, the depth histogram of the labelled nodes, and the label-vs-critic gap.
- **The control (arm C):** §6's mapping of R7's verdict. Identical dose rules, `tree` absent (or the T-op, if R7
  credits), every other key equal. A searched/control pair differs EXACTLY in {seed, run_name, seat_tag, the search
  block, the coefficients}, and a test pins that.

## 3. R0 gates (before launch; each with its action on a FAIL)

1. **THE WIDTH BENCH** (quiet box, nice 0; `native_tree_gates.py bench`'s training rungs plus a collector-throughput
   bench with weights lag <= 1). It gives each lane's steps/s at the dose and `frac`. FAIL (under D1's floor) -> lower
   `frac`, never the dose.
2. **THE DEPTH FLOOR** in the bench: `tree/turns_mean` >= 2.5 at 256 simulations. FAIL -> raise to 512, re-bench.
3. **THE SMOKES** (400k, searched + control, warm from one final): every counter on every update row (search/*,
   tree/*, the TreeStrap counters, fallback_frac, batch_rows); the searched arm's KL term not inert AT THE FLEET'S
   `frac` (D1's floor); a resume mid-smoke reproduces. FAIL -> no fleet.
4. **THE LR RULE** (a third anneal, disclosed), as R7's.
5. **DISK:** +~6 GB a lane (CLAUDE.md's disk rule).

## 4. The fleet

- 3 + 2 or 3 + 3 by the width bench, as R7's R-F2 did. Fewer lanes weaken the seed-clustered se (r2: keep 3 + 2).
- **Steps:** D1 / (lane steps/s). At R7's one-ply cost the lanes run ~620-850 steps/s. The TreeOp at 256 is ~4.5x the
  one-ply's leaves, so expect lower [the bench]. The budget buys fewer steps or a lower `frac`, never a smaller dose.
- Warm from the finals R7's verdict names, paired by final.

## 5. The reads (the same instruments as R7's, so no read is differenced across instruments)

- **PRIMARY:** off FP@N 25k/12k, greedy, loop breaker off, n 6000 per lane, one scheduler session in a pinned
  control-first order. delta = the equal-weight mean of the searched finals minus that of the control finals.
  se_diff = the LARGER of the pooled-binomial and the seed-clustered se_diff. CREDIT LINE, verbatim (CLAUDE.md): "a
  lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is the LARGER of the pooled-binomial
  se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals at read time." STRICT at both
  boundaries. Cells X-POS / X-GAIN / X-COST / X-NEG / X-FLAT with R7's actions (`scripts/r7_reads_readout.py`
  generalises).
- **MECHANISM READS**, searched minus control, paired by donor, with R7's MOVED rule:
  - (i) KL(pi' || pi_theta), LOWER: the manipulation check.
  - (iii) the critic's Spearman on G0, HIGHER: the evaluator.
  - (vi) the greedy's split-sample regret on G0, LOWER.
  - (vii) NEW: the critic's error on TREE states against their rollout values (TreeStrap's own target): LOWER.
  - (viii) NEW: the expected improvement of the searched arm's pi' on G0's oracle (stepc_a's instrument).
  - STOP CONDITION (D2): the on-policy critic's value loss and explained variance on the rows each lane played,
    searched vs control, every update. A searched-arm EV that falls away from its pair's is the maintainer's call
    mid-fleet, never a silent continuation.
- **Secondary:** vs SH (locked); the object rule, as R7's.

## 6. R7's outcome -> Step C's design (r2's mapping, restated; never whether it runs)

- **X-POS / X-GAIN:** the control keeps the one-ply T-op, so Step C isolates DEPTH + TreeStrap over one ply.
- **X-FLAT, (i) not moved:** the target form is the suspect, so beta is a ladder, and CE is sooner.
- **X-FLAT, (i) moved and (vi) not:** the value channel is the suspect, so TreeStrap is ON (D2's recommendation
  either way).
- **Moved with delta <= 0, or X-COST / X-NEG:** `play: false` is mandatory, as it already is here.
- **VOID:** R7's control recipe on the R6 trio B donors.

## 7. What changes the plan, and what does not

- **Changes it:** the fusion read at depth. It read UNRESOLVED; D4 rules, and a resolved SPENT would force B >= 2
  worlds at x B the cost.
- **Changes it:** the width bench. It sets `frac` and the steps.
- **Read (stepc_a): the target-form channel measures** (+0.0044 over the one-ply target at z 2.76). The policy
  target is the lever's primary channel, TreeStrap the stacked value channel.
- **Does not change it:** a null or a cost at any one budget (rule 6); R7's verdict (it sets the control and the
  suspect channel, never whether this runs).

## 8. The three-session decision (2026-09-26)

- **r7-runner** proposed D1-D4 as in r1.
- **r6-runner AGREED on all four**, with conditions that are now in §0 and §0.5:
  - the learnable +0.0019 as the policy channel's number;
  - the ~+0.027 ceiling at the floor, and the power block;
  - `frac`'s floor at the fleet's `frac`;
  - TreeStrap's non-optimistic backup from our information set;
  - on-policy critic counters as a stop condition;
  - the not-green-at-launch branch;
  - the B = 2 bench's pre-stated rule.
  Its draft fixes (four rulings, not three; §0 in D1-D4 order; a POWER block) are applied.
- **fp-speedup:** [PENDING at r2's writing].
- Two of three decide a point, so D1-D4 stand as decided. The maintainer's rulings remain open only where a condition
  sends a case back to him (D1's `frac` floor, D2's not-green branch).

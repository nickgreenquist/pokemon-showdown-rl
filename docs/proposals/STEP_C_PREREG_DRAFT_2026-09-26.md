# STEP C — DEEP SEARCH IN TRAINING: the pre-reg, DRAFT (2026-09-26)

**Status: DRAFT, not ratified.** For the maintainer's three rulings (§0) and then two Opus reviews. It builds on
`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step C and adds the 09-26 reads that set its dose and its
mechanism. The standing ruling holds throughout: *"I do NOT want you to kill search in train if 1-ply doesn't work"*
(CLAUDE.md rule 6). Nothing below decides WHETHER Step C runs; the reads set its FORM and DOSE.

**journey_step: "14"**, whose exit condition reads verbatim: "one comparison at a REAL budget, on the strongest gen-1
object we have. Search-with-our-evaluator vs the same checkpoint greedy, pooled under the standing credit line, with
decisions/sec reported for both arms and the per-turn budget named in every quote." Step C is not that comparison
(Step B is); like R7, it trains the objects such a comparison uses and credits ONE training lever.

## 0. The maintainer's rulings this draft needs

- **D1 — THE BUDGET.** How many days of the box, or how many steps, the fleet may take. Sunday's quiet-box width bench
  measures a lane's steps/s with the TreeOp at the dose. The budget then sets the searched fraction and the steps (§4).
- **D2 — THE LEVER'S FORM, given 09-26's reads (§1).** Three options:
  - (a) As r2 wrote it: the deep tree's policy target (completed-Q pi') plus v'.
  - (b) Aimed at the EVALUATOR: the tree's INTERNAL-NODE value labels (TreeStrap) as the primary new channel. This is
    JOURNEY 14's own thesis: "this chapter's target is the VALUE FUNCTION, not the depth"; "a critic trained AS AN
    EVALUATOR ... on HYPOTHETICAL states it has never played".
  - (c) Both in one lever, as r2's "the value channel on" branch reads.
  - **Recommendation: (c) with TreeStrap ON, for two reasons.** First, 09-26 measured that deeper search does not
    change the root's choice under this critic, so a policy-target-only lever tests the channel least likely to move.
    Second, stacking the value channel is what the kitchen-sink ruling licenses: a built, counted addition inside
    the same objective.
- **D3 — THE CONTROL.** It is whatever base R7's verdict names (§6), warm from its finals and paired by final. It
  follows mechanically from Sunday's readout; it is listed so the ruling is visible.

## 1. The evidence (every number traced; `results/native_tree/*.summary.*`, SESSION_LOGS 2026-09-26)

- **Gate (i-c)** (`oracle_c`): at 1,800 simulations the belief tree is +0.0020 over the one-ply critic L-op at the
  matched override (z 1.37, its best rule). br_prior is the estimand (legacy -0.0041 at z -2.78, sm_rm -0.0055 at z
  -3.55 against it).
- **Tier 1** (`tier1_a`): FLAT from 1,800 to 28,800 simulations. Depth over equal-work breadth is ~+0.002 at every
  rung and never grows. The evaluator binds, not depth.
- **Tier 1b** (`tier1b_a`): the TRAINING setting (true world, B = 1) ties the one-ply T-op at 256 / 1,024 / 1,800
  simulations (matched at 0.100; every |d| < 1 se). The depth floor (mean >= 2.5 turns) is met at 256 (2.89 turns, 228
  leaves, ~4.5x the one-ply's ~51).
- **Step C's E-core inputs** (`stepc_a`, [PENDING -- running 09-26 11:28Z]): the FUSION READ AT DEPTH (the B = 1
  licence, §10's rule); SIGMA for the completed-Q target, chosen split-sample; the TARGET'S FORM, i.e. the expected
  improvement of the deep completed-Q target vs the one-ply T-op's own target vs the prior.
- **R7's counters** (the searched lane f1 over its last 5M steps; the record-only control's matched baseline): PPO
  clips 51.2% of searched rows vs 15.9% on the same selection in the record-only twin (~3.2x at one ply), so
  **play: false** is Step C's design.
- **Stage 0c**: rollout leaves beat critic leaves at one ply (+0.0027 at z 2.02 at R 128, still rising to 512). The
  evaluator axis is where search has shown room.

## 2. The lever (arm S): the collector's TreeOp

`rl/search/tree_top.py::TreeOp` (built and tested on `deep-search-step-a`; `searcher_class(spec)` picks it for a
block that carries `tree`). Its dials are derived from its signature, and unknown keys fail.
- **Dose:** 256 TOTAL simulations on the TRUE world (B = 1, iff the fusion read at depth holds [PENDING stepc_a];
  else B >= 2 worlds, with the cost multiplied); br_prior, the root grid, depth cap 8, cols_k 4, chance_k 2. The
  learner's OWN actor and critic serve as prior and leaf (TreeOp refuses an antisymmetric or privileged critic).
- **Which rows:** eligible rows as R7's (> 1 legal action, pi_theta top-1 < 0.97), searched on a coin at `frac` (a
  benched fraction; KataGo's playout-cap randomization). `frac` comes from D1 and the width bench (§4).
- **Behaviour:** `play: false` (§1). The lane plays pi_theta, so its data stay on-policy.
- **Policy target:** the completed-Q pi' at sigma = [PENDING stepc_a], trained as beta * KL(pi' || pi_theta) on
  searched rows. beta warms up 0 -> beta* over ~5M steps; beta* comes from a 2M smoke ladder under R7's not-inert
  rule.
- **Value target:** v' = E_{a~pi'} E_{b~prior} Q(a,b) into R7's aux head, NEVER the root max (G1: +0.019 of max
  optimism).
- **TreeStrap (D2):** the tree's internal nodes with N >= 16 each contribute (obs of that node, its backed-up value)
  to the critic's loss at a counted weight. These are the hypothetical states JOURNEY 14 names. Counters:
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
   tree/*, the TreeStrap counters, fallback_frac, batch_rows); the searched arm's KL term not inert; a resume
   mid-smoke reproduces. FAIL -> no fleet.
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
- **Secondary:** vs SH (locked); the object rule, as R7's.

## 6. R7's outcome -> Step C's design (r2's mapping, restated; never whether it runs)

- **X-POS / X-GAIN:** the control keeps the one-ply T-op, so Step C isolates DEPTH + TreeStrap over one ply.
- **X-FLAT, (i) not moved:** the target form is the suspect, so beta is a ladder, and CE is sooner.
- **X-FLAT, (i) moved and (vi) not:** the value channel is the suspect, so TreeStrap is ON (D2's recommendation
  either way).
- **Moved with delta <= 0, or X-COST / X-NEG:** `play: false` is mandatory, as it already is here.
- **VOID:** R7's control recipe on the R6 trio B donors.

## 7. What changes the plan, and what does not

- **Changes it:** the fusion read at depth. If it spends B = 1's licence, the dose becomes B >= 2 worlds at x B the
  cost.
- **Changes it:** the width bench. It sets `frac` and the steps.
- **Changes it:** stepc_a's target-form read. If the deep completed-Q target shows no expected improvement over the
  one-ply T-op's, TreeStrap carries the lever and D2's (b) is the honest name.
- **Does not change it:** a null or a cost at any one budget (rule 6); R7's verdict (it sets the control and the
  suspect channel, never whether this runs).

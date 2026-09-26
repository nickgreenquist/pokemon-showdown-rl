# STEP C — DEEP SEARCH IN TRAINING: the pre-reg, DRAFT (2026-09-26)

**Status: DRAFT r4 (+ the deep-key value read, 13:55Z; + the level rule, 14:35Z), not ratified.**
- The three agent sessions (r7-runner, r6-runner, fp-speedup) agreed on r4's direction, as the maintainer asked ("You
  decide among the 3 of you and then go for review").
- Both Opus reviews of r3 are folded in. Every finding has a disposition in §9.
- **D1 (the budget) and D4 (worlds per search) are HELD** for the speed work: the maintainer's DeepResearch report
  (`docs/SearchOptimizationsIdeas.md`, pending) and the quiet-box bench.
- Next: a verification pass by both reviewers, held until the DeepResearch report lands and D1 / D4 are folded in (one
  pass covers all of it; the reviewers' first try died on the usage limit, 13:58Z).

The standing ruling holds throughout: *"I do NOT want you to kill search in train if 1-ply doesn't work"* (CLAUDE.md
rule 6). Nothing below decides WHETHER Step C runs; the evidence sets its FORM, DOSE and the reads that decide the next
lap.

**journey_step: "14"**, whose exit condition reads verbatim: "one comparison at a REAL budget, on the strongest gen-1
object we have. Search-with-our-evaluator vs the same checkpoint greedy, pooled under the standing credit line, with
decisions/sec reported for both arms and the per-turn budget named in every quote." Step C is not that comparison
(Step B is). It trains the objects such a comparison uses, and it credits ONE training lever: the bundle {depth, the
evaluator + TreeStrap} (D3).

## 0. What Step C tests (the corrected evidence, §2)

All of the following are measured at the decision level on G0's 500 roots, with the R5 committee as the net.

- **BETWEEN positions, depth measured.** At the learnable fixed point (the mean over 8 belief worlds, no peek), the deep
  tree's prior-weighted root value tracks the rollout oracle better than the raw critic:
  - centred squared error -0.0133 ± 0.0056 (z -2.38) vs the critic;
  - -0.015 .. -0.017 (z -2.9 .. -3.7) vs R7's exact one-ply fixed point, across 3 one-ply keys;
  - across 3 DEEP keys it holds on every key: -0.0133 / -0.0165 / -0.0127 vs the critic (z -2.38 / -3.34 / -2.49),
    and z -2.8 .. -4.2 vs the one-ply FP on all 9 key pairs. Averaged over its keys the deep FP is -0.0184 vs the
    critic (z -3.90) and -0.0184 vs the one-ply FP averaged over its keys (z -4.95), which equals the critic
    (+0.0000, z 0.01).
  - **The deep backup is MORE OPTIMISTIC in level.** The deep FP sits +0.046 .. +0.050 above the rollout; the critic
    sits +0.034 (deep minus critic +0.0147 ± 0.0060); the one-ply FP matches the critic. Centred error removes a
    level, but a TreeStrap label keeps it, so the MC grounding term anchors the level.
    - It is measured on the PUCT-mean (visit-weighted) backups, the only form the stored rows carry. The recursive
      prior-weighted labels (D2(ii)) should cut it at the source, and G1's signed gap on BOTH forms confirms it
      (fp-speedup).
    - The anchor sees PLAYED states only, while labels cover HYPOTHETICAL ones, so a state-dependent bias would
      survive it. G1 splits the signed gap by node depth and turn bucket (fp-speedup).
    - The optimism can feed itself: the tree reads the evaluator at its leaves, so high labels lift the evaluator,
      which lifts the next backups. So the level has a MEASURED threshold and a staged action, not a read-only watch
      (r6-runner): tau_lvl from G2, G7's clause, stop condition S2.
- **WITHIN a position, depth ties one ply.** On the ranking of our root rows against the oracle (fp-speedup: Pearson /
  Spearman paired, every |z| < 1.2 per key), the policy target's learnable EI edge is ~+0.0008, not resolved, and the
  argmax ties.
- **So the VALUE channel is where depth measured, and the policy target is the pathway.** An improving evaluator
  reaches the actor only through the tree's within-position choices. That link, the compounding bet, is UNMEASURED.
  - Its first test is offline and runs before the fleet (G2, §3).
  - Its decisive test is the per-checkpoint fixed-point EI read (M2, §5).
- **Expectation for the primary: X-FLAT is the likely cell.** Off FP@N, the decision-to-battle conversion is G2's
  ~0.46, not the engine mirror's ~14 (§5 POWER). So the offline mechanism reads are pre-registered as decision-bearing
  for the next lap's design (D5).

## 1. The rulings (the three sessions, 2026-09-26)

### D1 — THE BUDGET: HELD for the speed work, with its rules pre-stated

- **Target:** +100M steps per lane in <= 4 days of the box, 3 + 2 lanes. C's steps are matched to S's.
- **The break-even cost per searched decision** (reviewer B #10): 100M in 4 days is 289 steps/s a lane. With eligible
  decisions ~0.71 and the one-ply T-op at ~1.6 ms a searched decision (R7's lanes), `frac` 0.25 needs c_tree <= ~20 ms,
  ~12x the one-ply.
  - The stored E-core timings put the 256-simulation tree at ~20.5x the one-ply's time (680 vs 33 ms, the committee on
    E-cores). The width bench (G3) measures c_tree on the fleet's own net.
- **`frac`'s FLOOR** is the larger of 0.25 (KataGo's playout-cap p) and the level where the KL term stays not-inert.
  The beta ladder and the not-inert check run AT THE FLEET'S `frac`.
- **If c_tree > break-even, in this order:**
  1. The speed levers: the merged critic + prior forward; lazy priors, verified bitwise at batch 8; cross-tree batching
     with more environments per collector; search OFF the collector's critical path (Reanalyze-style workers, which
     can use the E-cores); a distilled leaf net.
  2. Then more days or fewer lanes (the maintainer).
  3. Never a smaller dose, and never a `frac` below the floor.
- **The minimum steps** below which the fleet waits rather than launches: 50M a lane. That is a dose-limited null
  otherwise, which rule 6 would forbid reading anyway.
- The width bench NEVER overlaps fp-speedup's FP@500 calibration reference (REF500 VOIDs above 5% contaminated
  minutes).

### D2 — THE LEVER (agreed 3/3)

- **THE TREE.** The dials are pinned to the evidence: stepc_a's stamped `dials["tr_256"]` = {sims 256, mode br_prior,
  root_grid, depth_cap 8, cols_k 4, chance_k 2, root_rule soft_br, tau 0.05, batch 8}, pass_leaf "through", lazy_priors
  off (or on only after a bitwise check at batch 8).
  - B = 1 on the TRUE world (D4).
  - The generator writes the full block, and a test asserts it equals the stamped dials.
  - TreeOp's own defaults (completed-Q, batch 1, `frac` 0.4) are never relied on, and its docstring's completed-Q line
    is fixed (reviewer A #6).
- **THE POLICY TARGET: the tree's soft_br pi' at tau 0.05**, trained as beta * KL(pi' || pi_theta) on searched rows;
  beta warms up 0 -> beta* (G6).
  - DISCLOSED (r6-runner): tau 0.05 was INHERITED from G0's belief dials, never tuned on these roots, while
    completed-Q's sigma was selected split-sample. So completed-Q's z -2.95 deficit against soft_br at the fixed point
    is conservative.
  - A policy-entropy counter on searched rows, searched vs control.
- **THE EVALUATOR, a SEPARATE network on design B's isolation pattern** (`rl/agents/ppo.py` ~592-640;
  `_priv_eval_gradient` ~1365; reviewers A #1, B #4).
  - Its own EntityDeepSetsNet on the OBSERVATION only. No privileged block: the TreeOp refuses a privileged leaf.
  - Warm-started as a copy of the donor's critic in every cell.
  - It feeds NOTHING but the tree's leaves. Advantages, the policy gradient, `loss/value` and `loss/explained_variance`
    keep reading the critic.
  - Its gradient is a separate autograd over its own parameters, called after the shared clip is read, so it cannot
    move `loss/grad_norm`.
  - Tests: the critic's updates are bit-identical with the evaluator on and off (tests/test_priv_eval_head.py's
    pattern); the collector child's evaluator equals the learner's at every weights version; the TreeOp's leaf equals
    the donor critic at step 0.
  - R7's v' aux head (a linear head on the critic's context whose gradient reaches the critic trunk; reviewer A #1) is
    NOT used by S, and "actor-neutral by construction" is claimed only for this separate net.
- **THE EVALUATOR'S LOSS:**
  - (1) GROUNDING (r6-runner, fp-speedup): design B's Monte-Carlo-return MSE (lambda 1) on the rows each lane played,
    at a counted coefficient. Labels alone bootstrap off the evaluator's own leaves (tree/terminal_sims is ~0 at 256),
    and a flat value is nearly self-consistent.
  - (2) TREESTRAP labels at a counted weight w_ts (set by G2), on internal nodes with N >= N_min (set by G1):
    - The obs comes from OUR information set in the true world (the tracked view).
    - The label is the RECURSIVE prior-weighted backup over the finished tree (fp-speedup): at every node our side is
      weighted by the prior and the foe's side by its model's q. Unexpanded rows take the evaluator's value (v_mix).
      No choice anywhere below depends on the peek, so the posterior mean is the prior's value from our information
      set, which is the oracle's own estimand.
    - Excluded: Pass nodes (valued through), terminals (their outcome), unvisited rows.
  - v' (the root soft-best-response value) is NEVER a label (reviewer B #3: v' - v_prior is +0.0293 at 256, only +0.0070
    of it real, with clairvoyance +0.0208 at z 6.2).
- **THE STOP CONDITIONS:** §4.

### D3 — THE CONTROL (agreed 3/3)

- **C = R7's one-ply T-op at `play: false`, at S's `frac` and beta*** (beta* shared from S's ladder, disclosed),
  every other key equal.
- **S - C = {depth, the evaluator + TreeStrap}**, with the behaviour channel MATCHED (reviewer B #5). r3's "C = the
  credited recipe unchanged" is withdrawn: a lever this small needs the clean contrast more than the credited base.
- C is a new configuration, so it gets its own smoke and its own not-inert check (G7).
- **Adoption** (fp-speedup): where R7 does not credit the T-op, C carries an uncredited one-ply target. A positive S - C
  then credits the bundle OVER THAT C, never "S beats the base". Adoption goes through the object rule (§5) or a
  disclosed secondary.
- If R7 credits `play: true` (X-POS), the base's deviation is disclosed.
- The donors follow §6's table.

### D4 — WORLDS PER SEARCH: HELD, B = 1 by default, with the switch rule pre-stated

- B = 2 runs over BELIEF worlds only (a true world inside a B >= 2 tree brings the peek back), each world at the depth
  floor.
- B = 2 replaces B = 1 iff all of these hold:
  - its student fixed point's EI beats B = 1's, paired on G0's roots, at z >= 2;
  - each form's tau is chosen split-sample (fp-speedup: reviewer B's tau 0.01 for the joint target was picked on the
    same roots);
  - the width bench fits it at EQUAL TOTAL COST (B = 2's `frac` halved) above `frac`'s floor.
- ITS POWER, stated before the read (reviewer B #8): at 500 roots, even the joint B = 8 target's EI gap over the B = 1
  fixed point is +0.0012 ± 0.0007 at tau 0.05 (z 1.82). At a split-chosen tau it is +0.0030 ± 0.0012 (z 2.60),
  to be re-derived under the split rule. So the rule is likely unreachable at this n, and a non-switch is not evidence
  against B = 2 (rule 6).

### D5 — THE DECISION-BEARING MECHANISM READS (agreed 3/3): §5

## 2. The evidence (every number traced to `results/native_tree/*`, SESSION_LOGS 2026-09-26)

Caveats on everything below (reviewers B #6, #7, #9, #12, #13, #20):
- Decision level on G0's 500 roots, 125 per turn bucket.
- The R5 committee (c6-off) as prior and leaf; the fleet uses its own c6-on learner.
- The root foe prior is the oracle's own column weighting (pi2). Under a uniform or worst-case foe the target reads
  shrink toward 0, so the planning numbers are re-reported under a foe-robust weighting.
- The resampled worlds are measurably NOT exchangeable with the true world (TV gap +0.0165 at z 2.9), so the fixed
  point is a biased stand-in, sign unknown.
- 230 of 500 roots are ineligible (top-1 >= 0.97 or one legal row).
- The one-ply target headline sat mostly in the turn 16-22 bucket.
- The banked one-ply reference used by i-c, tier 1 and tier 1b was the dial sweep's MAXIMUM cell (+0.0040 vs its band
  mean +0.0028), which biases those reads against the tree.

| read | what it measured | the number | file |
|---|---|---|---|
| gate (i-c) | belief tree at 1,800 vs the one-ply critic L-op, matched 0.080 | soft_br +0.0006 (z 0.47); gumbel_mctx +0.0020 (z 1.37); estimand vs br_prior under gumbel_mctx: legacy -0.0041 (z -2.78), sm_rm -0.0055 (z -3.55); under soft_br -0.0016 / -0.0019 | oracle_c.summary.md |
| tier 1 | the belief tree 1,800 -> 28,800 | FLAT: steps -0.0004 ± 0.0004 / +0.0002 ± 0.0007 (soft_br) | tier1_a.summary.md |
| tier 1b | the true world at 256 / 1,024 / 1,800 vs the banked one-ply (the sweep's max cell) at 0.100 | ties; every |d| < 1 se under soft_br and gumbel_mctx (legacy_gumbel z -1.28 / -1.47 / -1.29) | tier1b_a.summary.md |
| stepc_a target form | EI, true world vs fixed point, soft_br vs completed-Q | completed-Q's learnable part ~0 (+0.0002); soft_br's fixed point +0.0018; completed-Q minus soft_br at the fixed point -0.0011 ± 0.0004 (z -2.95); the joint target: tie between forms | stepc_a.stepc.md |
| stepc2_a like-for-like | R7's EXACT one-ply (pass_leaf critic), 3 keys, the same 8 worlds | fixed-point EI deep minus one-ply +0.0013 / +0.0003 / +0.0006; argmax tie; the one-ply's EI swings +0.0000..+0.0016 with the chance key | stepc2_a.stepc2.md |
| value channel (peek) | prior-weighted root value vs G0's v_root_rollout, centred squared error | deep TRUE -0.0344 (z -4.98) vs the critic; deep FIXED POINT -0.0133 (z -2.38) vs the critic, -0.015..-0.017 (z -2.9..-3.7) vs the one-ply FP; joint -0.0180 (z -3.64); the one-ply FP = the critic (+0.0021); ~60% of the true edge is peek | SESSION_LOGS; recompute from the stored rows |
| value channel (deep keys) | the same, deep side under keys 1 and 2 | holds on every key: vs the critic -0.0133 / -0.0165 / -0.0127 (z -2.38 / -3.34 / -2.49); vs the one-ply FP z -2.8..-4.2 on all 9 key pairs; 3-key averages -0.0184 vs the critic (z -3.90) and vs the one-ply FP average (z -4.95), which equals the critic (z 0.01); LEVEL: the deep FP +0.0147 ± 0.0060 above the critic's +0.034 optimism | value_channel_keys.json (stepc3_a) |
| within-position (fp-speedup) | ranking our root rows vs the oracle | deep ties one-ply (|z| < 1.2 per key); among N >= 16 rows +0.11..+0.14 (z ~1.2-1.5) | fp-speedup's offline scripts |
| fusion at depth | argmax form, t_pimc - t_avg | +0.00058 ± 0.00106 a decision; UNRESOLVED | stepc_a.stepc.md |
| R7's clip split | R7's searched f1 vs the record-only control f1, last 5M steps (to 29.5M vs to 34.0M: windows NOT matched) | 51.2% vs 15.9% of searched rows (wandb; to be banked with its windows) | DEEP_SEARCH_PATH r2 note |

## 3. The builds and the R0 gates, in order

**THE ORDER** (reviewer A #16). The merge is never before the R7 reads queue is done: the fleet and the queue import
main's working tree, and the branch edits `rl/train.py`, `rl/envs/engine_collector_proc.py`, `scripts/ch3_fp_h2h.py`
and `scripts/ch3_eval.py`.
1. The R7 fleet DONE.
2. The R7 reads queue DONE.
3. Merge `deep-search-step-a`, then the suite at the merge commit (G8).
4. The builds.
5. The quiet-box benches (never during REF500).
6. The E-core reads (G1, G2, the B = 2 read).
7. The LR rule, then the beta ladder.
8. The shakedown.
9. Launch.

**THE BUILDS.** Each has named counters in a DERIVED `GATE_COUNTERS` table, with a grep test over rl/ (R7's pattern).
- **B1 — the evaluator network.** As D2: design B's isolation, obs only, the warm copy, its three tests.
  - Counters: `loss/evaluator_mc`, `loss/evaluator_ts`, `evaluator/label_gap_signed`, `evaluator/drift_signed`.
    `evaluator/drift_signed` is the evaluator minus the played-row MC return, signed, per update, with its
    battle-clustered se. S2 and G7 read it.
  - The grounding weight and w_ts are RESUME-TIME OVERRIDES, stamped in meta.yaml with their from_step, for S2's
    staged action (a test pins that a resume without the override reproduces the run's value).
- **B2 — the TreeStrap label export.** The tree exports (node obs, recursive prior-weighted value) for N >= N_min
  through a side channel from the collector child to the learner. TreeOp's `take()` is one record per row today
  (`rl/search/tree_top.py` ~212-225), and native_tree returns root statistics only.
  - Counters: `treestrap/labels_per_decision`, `treestrap/depth_hist/*`, `treestrap/label_minus_head_signed`,
    `treestrap/excluded/{pass,terminal,unvisited}`.
- **B3 — the TreeOp reads the evaluator.** Its value_fn is switched from `native.critic_value_fn(agent)`; the dials are
  pinned by test (D2); the docstring is fixed.
- **B4 — the beta warm-up in `ppo.py`** (`search/beta_effective`).
- **B5 — the OFFLINE c6-on mechanism instrument** (the `scripts/r7_mechanism_reads.py` precedent). It runs M1-M4 (§5)
  on G0's roots per checkpoint, with the SAME TreeOp dials on every final and the leaf named (S's evaluator or C's
  critic).
- **B6 — the TreeOp collector bench on the fleet's net:** c6-on, fleet width, weights lag <= 1.
  `native_tree_gates.py bench` runs the committee c6-off (reviewer A #14) and is not this bench.
- **B7 — the generator, the config-diff test and a Step C readout** derived from the header (R7's pattern:
  `scripts/derive_r7_fleet.py`, `tests/test_derive_r7_fleet.py`, `scripts/r7_reads_readout.py`).

**THE R0 GATES** (each with its FAIL action):
- **G1 — THE LABEL-QUALITY READ** (E-cores; the donor final, c6-on, as the net; R = 32 rollouts per labelled node,
  played from OUR information set by observation-based policies, never the tree; >= 2,000 labelled nodes from G0's
  roots; both label forms, node-level and recursive). Per node:
  - the paired |label - rollout| minus |donor critic - rollout|, centred;
  - the SIGNED mean gap, label - rollout (the optimism), per label form, split by labelled-node depth and by G0's
    turn bucket (fp-speedup: the played-row anchor cannot see a bias on hypothetical states, so G1 is its only
    instrument before the fleet). A depth trend in the recursive form at 2 se caps the labels at the deepest depth
    without one, disclosed;
  - the WITHIN-position measure (fp-speedup): the ranking of a labelled node's children against their rollout values.
  - PASS: the centred paired error is below 0 at 2 se. N_min is the smallest N at which it passes. FAIL -> the
    not-green table.
- **G2 — THE OFFLINE FIRST-LINK TEST** (r6-runner). Train the evaluator on TreeStrap labels plus MC grounding from ONE
  fixed donor, for a few hours on idle cores. Then, on HELD-OUT G0 roots:
  - (a) the evaluator's centred error vs the rollout value;
  - (b) the tree's fixed-point pi' EI with that evaluator at the leaves vs the donor critic at the leaves.
  - It sets FORM only (w_ts, N_min, the grounding weight). (a) improved at 2 se -> TreeStrap on. (b) is the compounding
    link's first measurement: reported, never a gate (rule 6).
  - **THE LEVEL THRESHOLD tau_lvl** (r6-runner). `evaluator/drift_signed` on HELD-OUT played rows, at G2's start (the
    warm copy) and at its end.
    - The grounding weight is the smallest rung of w_mc / w_ts in {0.5, 1, 2, 4} at which that start-to-end change is
      NOT significant at 2 se. The threshold is never taken at a weight whose own offline loop already drifts.
    - A rung COUNTS only if (r6-runner) both hold; otherwise G2 runs longer before any rung is picked. This stops a
      noisy or short G2 from passing on noise and then inflating tau_lvl through its se:
      - PRECISION: 2 se <= 0.0073, half the measured label optimism (+0.0147 deep FP minus the critic;
        `value_channel_keys.json` "level").
      - PLATEAU: the change over G2's last third is not significant at 2 se. The fleet's evaluator trains far longer
        than G2's, so the bound comes from an equilibrium, never a transient.
    - tau_lvl = |the change| + 2 se, at that rung. It is S2's and G7's threshold, so it is measured, never typed.
    - No rung passes -> the not-green table's TreeStrap row (MC grounding only; the maintainer rules).
- **G3 — THE WIDTH BENCH (B6)** -> c_tree, against D1's break-even and D1's order.
- **G4 — THE DEPTH FLOOR:** `tree/turns_mean` >= 2.5 in the smokes, on the fleet's net. FAIL -> 512, re-bench. It is
  also watched in-fleet (§4).
- **G5 — THE LR RULE.** R7's candidate clause fails here (R7's finals started at 2.5e-05; reviewer A #9). So the
  candidates are {2.5e-05, 1.25e-05}, each 2M, control-first. The bars are R7's control bars (approx_kl <= 0.06 on
  every update, the entropy band, vs SH within 0.03), read on C, since both arms are `play: false`. The largest passing
  lr wins; none passing -> the maintainer.
- **G6 — THE BETA LADDER** (after G5). The candidates are {0.03, 0.1, 0.3}: S at each, plus a beta-0 comparator, all
  AT THE FLEET'S `frac`, 2M each, with the warm-up compressed to 1M (disclosed).
  - Not-inert (R7's rule): the last half's `search/kl_update` below the beta-0 comparator's by > 2 * sqrt(se_S^2 +
    se_0^2).
  - beta* is the largest candidate that passes C-matched KL and entropy bars and is not inert. If none is not-inert at
    the floor `frac`, it goes back to D1's action.
- **G7 — THE SHAKEDOWN** (reviewer A #2): S and C each >= 800k steps (6.5 updates at base b), eval and checkpoint every
  100k.
  - Kill the searched smoke after its first `checkpoint.pt` and resume it; the resume reproduces.
  - Every GATE_COUNTER on every update row, and C's own not-inert check.
  - THE LEVEL (r6-runner): S's `evaluator/drift_signed` change from its first 100k steps to its last exceeds tau_lvl at
    2 se -> FAIL -> the grounding weight x2 and re-smoke before any fleet.
  - FAIL -> no fleet.
- **G8 — THE SUITE at the launch commit**, after the merge. Every lane stamps the same clean sha.
- **G9 — DISK:** free space >= 2x the projection (~6 GB a lane plus ~7.5 GB of Foul Play stdout for 30k battles) and
  >= 50 GB; else STOP (CLAUDE.md).

**THE NOT-GREEN TABLE** (one table replacing r3's overlapping routes; reviewer A #8):

| evaluator build (B1) | TreeStrap build (B2) + G1 | action |
|---|---|---|
| green | green | launch as specified |
| green | not green, or G1 FAIL | the maintainer rules: the policy target + the evaluator trained on MC grounding only (TreeStrap to its own lap), or hold |
| not green | any | HOLD (the maintainer); never labels into the GAE critic silently |

## 4. The fleet

- **3 + 2 lanes** (3 + 3 only if the width bench passes six-wide), +100M (D1 held), warm from §6's donors.
- The theta0 anchors are the donor's; the pool restarts at the donor.
- The LR is re-armed: a third anneal. The N-ANNEAL disclosure travels on every number (~400M total over three anneals).
- **LAUNCH:** over 5 h, so the maintainer launches unless a permission is recorded (CLAUDE.md rule 4; R7's
  agent-side permission is R7's, not this fleet's).
- **MONITORS:**
  - A per-arm throughput alert at 0.6x the median of the lane's OWN arm (S and C run different operators; reviewer A
    #10).
  - The CPU-delta stall check; RESUMES= / NODE_RESTARTS= from one watchdog; every from_step; the /timer line.
- **STOP CONDITIONS** (each read over the last 5M steps at every monitor pass; two consecutive trips go to the
  maintainer mid-fleet, never a silent continuation):
  - S1, THE CRITIC: S's on-policy explained variance on played rows below its pair's by > 0.05 (r6-runner; reviewers
    A #15, B #15).
  - S2, THE EVALUATOR'S LEVEL (r6-runner; replaces r4's typed 0.05). The instrument is the change in
    `evaluator/drift_signed` since the lane's first 1M steps, over the last 5M steps. It is watched at every monitor
    pass; its action fires only at the 25M marks.
    - The trigger is TIERED to the action's cost (r6-runner). tau_lvl already carries G2's 2 se, and a stricter test
      would trip late on a self-reinforcing loop.
      - FIRST TRIP (mild, reversible in effect): the POINT estimate of the change exceeds tau_lvl AND grew since the
        previous mark -> the grounding weight x2 from the next update (B1's resume-time override; disclosed with its
        from_step).
      - A LATER TRIP: the change exceeds tau_lvl at 2 se AND grew since the previous mark -> TreeStrap labels OFF for
        the rest of the lap (w_ts 0; the evaluator continues on MC grounding; the policy target alone, disclosed).
        TreeStrap goes to its own lap.
    - ONE RECIPE (r6-runner): a trip on ANY S lane applies its action to ALL S lanes at the same 25M mark, disclosed.
      Otherwise the primary's equal-weight mean of S finals would average different recipes, and a credit would not
      name one lever. C has no TreeStrap and is unaffected.
    - S2 never waits for a second consecutive trip to act, and never continues silently.
  - S3, THE DEPTH FLOOR: `tree/turns_mean` < 2.5.

## 5. The reads

**PRIMARY:** off FP@N 25k/12k, greedy, loop breaker off, n 6000 per lane, one scheduler session in a pinned
control-first order. That is 30k battles, ~2.4-2.6 h at 8 slots (fp-speedup).
- delta = the equal-weight mean of the searched finals minus that of the control finals (the aggregator).
- se_diff = the LARGER of the pooled-binomial and the seed-clustered se_diff.
- CREDIT LINE, verbatim (CLAUDE.md): "a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, where se_diff is
  the LARGER of the pooled-binomial se_diff and the seed-clustered se_diff, the latter computed from the per-seed finals
  at read time." STRICT at both boundaries.
- **VALIDITY:** an arm whose runner JSON has `fpn_counters_ok` false is INVALID. It re-runs LAST on its rerun pair and
  is never pooled.
- **Every quote** names "FP@N 25k/12k" with its calibration (two seats vs FP@20, NON-REJECTION, offset CI95 [-0.026,
  +0.011], gap-change CI95 [-0.042, +0.033], MDE 0.054) and the two disclosures: the equivalence test is weakly powered,
  and the point estimate flatters us.
- **LANE LOSS:** a lane that fails a gate or cannot reach its steps is dropped with its pair. Under 3 + 2, losing a lane
  of pair f1 or f2 -> PRIMARY VOID; losing S's f3 -> 2 vs 2.
- **DOSE IS NOT MATCHED by design:** S and C search differently. Both arms' `search/searched_frac`, `eligible_frac`,
  `tree/sims` and `search/leaves` are reported at 12M and at the end, beside the primary. The config-key diff is
  enumerated and pinned by a test (B7).

**STEP C's OWN BRANCH ACTIONS** (strict boundaries, no unnamed cells, the word "kill" absent):
- **X-POS** (delta > +0.025 AND > 2 se):
  - The bundle {depth, evaluator + TreeStrap} is credited over C, in the warm-start regime.
  - The lever stays in the next base.
  - S's evaluator becomes Step B's leaf candidate at inference.
- **X-GAIN** (0 < delta <= +0.025 AND > 2 se): a resolved gain below the floor, NOT credited; the lever stays in the
  base.
- **X-COST** (-0.025 <= delta < 0 AND |delta| > 2 se) and **X-NEG** (delta < -0.025 AND |delta| > 2 se):
  - The lever leaves the base (X-NEG is credited negative).
  - Its own lap goes to the channel the mechanism reads name: the evaluator (M1 moved with drift, S2) or the policy
    pathway (M2).
- **X-FLAT** (everything else): a null that closes nothing (rule 6), routed on M1 and M2 below. Never "search does not
  work".

**POWER** (reviewer B #2, A #13; `results/native_tree/stepc_power.json`, via `scripts/r7_fleet_power.py`'s simulate; the
lane sd comes from FP@20 trio reads, so it is APPROXIMATE under FP@N; the generating call is to be committed):
- In the engine mirror's units (the ~14x conversion), the ceilings are +0.027 (B = 1) and +0.043 (joint), with P(X-POS)
  0.60 and 0.99.
- Off FP@N, the only paired calibration is G2's: 0.46x, CI roughly [-8x, +9x]. At that conversion the planning ceiling
  is ~+0.001 a battle and P(X-POS) is ~0.
- **The likely primary cell is X-FLAT, so M1 and M2 carry the next lap's design.**

**THE DECISION-BEARING MECHANISM READS** (D5; B5's instrument; offline on G0's roots, c6-on, the SAME TreeOp dials on
every final, paired by donor, every 25M checkpoint and at the finals; r6-runner's trajectory condition):
- **M1 — THE EVALUATOR.** S's evaluator vs C's critic: centred error against the rollout value, paired by position;
  also the signed level bias.
  - Threshold: S better at 2 se at the finals -> "the evaluator improved".
  - Consequence: S's evaluator is Step B's leaf candidate.
- **M2 — THE TARGET'S FIXED-POINT EI**, the DECISIVE read of the compounding bet. The tree with S's evaluator vs C's
  one-ply T-op with C's critic, both averaged over the same 8 belief worlds, 3 chance keys; plus the argmax, matched on
  the override.
  - Threshold: S's EI above C's at 2 se at the finals -> "the policy pathway moved". The trajectory over checkpoints is
    the compounding test itself.
- **M3 — WITHIN-POSITION RANKING** (fp-speedup): Spearman of the root Q against the oracle's qbar, S vs C. Reported.
- **M4 — READ (i)**, the manipulation check: KL(pi' || pi_theta) with the same dials on each final. Reported.
- **X-FLAT ROUTING:**
  - M1 and M2 both moved -> the lever stays; the next lap is SCALE (dose, `frac`, B).
  - M1 moved, M2 not -> the evaluator improved but did not reach the policy. The next lap puts the evaluator into
    inference (Step B) and makes the target form the suspect.
  - M1 not moved -> the value channel did not move at this dose. TreeStrap's form (labels, w_ts, N_min) is the next
    lap's suspect.

**SECONDARY:** vs SH (locked form). The object rule: the incumbent is R7's object as its readout names it; the fleet's
committees are ENS-S and ENS-C; the tolerance is 0.013. The anchor battery comes before any README row.

**OWED AT READOUT:** RESUMES= and NODE_RESTARTS=, every from_step, the donors' sha256, the /timer line.

## 6. R7's verdict -> Step C's arms (one table, keyed on R7's action; reviewer A #4)

| R7's action | C | S | donors (every lane's path and sha are pinned by the generator) |
|---|---|---|---|
| the lever STAYS (X-POS; X-GAIN; X-FLAT with both (i) and (vi) moved and delta > 0) | R7's T-op at play: false, at S's frac and beta* | C + the bundle | R7's SEARCHED finals, paired by donor (f1, f2, f3), for both arms |
| the lever LEAVES (X-COST; X-NEG; X-FLAT's other routes) | the same C | the same S | R7's CONTROL finals for f1 and f2. Under 3 + 2 there is NO f3 control final, so Step C runs 2 + 2, unless the maintainer rules a third donor (R6 trio B's b344, with an N-ANNEAL disclosure) |
| VOID | R7's control recipe | the same S | the R6 trio B donors |

Every row: theta0 anchors, pool restart, the LR re-arm and the N-ANNEAL disclosure, as §4.

## 7. What changes the plan, and what does not

- **Changes it:**
  - the speed work and the width bench (D1: `frac`, steps and the order of its levers);
  - the B = 2 read (D4's rule);
  - G1 and G2 (TreeStrap in, or on its own lap; w_ts, N_min, the grounding weight and tau_lvl);
  - ~~the deep-key value read (stepc3_a)~~ DONE 2026-09-26: the fixed-point value edge holds on all three deep keys
    (§2), so the value channel's rationale stands.
- **Does not change it:** a null or a cost at any one budget (rule 6); R7's verdict (it sets C's donors, never whether
  this runs).
- **GENERATION (JOURNEY 15):** B = 1's licence, tau 0.05, `frac`'s floor and the dose are GEN-1 MEASUREMENTS. The
  algorithm is generation-agnostic, and a new generation re-measures them. The TreeOp sits behind the engine interface
  (SearchNode / LeafBatch), so a new generation supplies its engine and encoder, nothing else.

## 8. The three-session record (2026-09-26)

- **r1 -> r3:** D1-D4 as first decided; fp-speedup's completed-Q finding moved D2's form to soft_br.
- **r4:** the reviews and the like-for-like read overturned r3's D2 rationale (SESSION_LOGS 12:20Z and 13:10Z). The
  sessions re-decided as follows:
  - **r6-runner AGREED:**
    - D2(i)-(iii), with the peek and key checks on the value evidence (both done: the peek check, and the deep-key
      check, which holds on every key);
    - the grounding term and the drift stop;
    - D3, with C's own smoke and the shared beta* disclosed;
    - D5, with the 25M trajectory and G2's offline first-link test;
    - D1 and D4 held.
  - **fp-speedup AGREED:**
    - D2(i), scoped as BETWEEN-position evidence (within a root deep ties one ply), with the within-position measure;
    - D2(ii), the RECURSIVE prior-weighted labels, both forms in G1 with the signed gap;
    - D2(iii), design B's isolation without the privileged input, and the MC-return grounding;
    - D3, with the adoption sentence;
    - D5, with thresholds and consequences, argmax matched on the override;
    - D1 and D4 held, with the joint tau chosen split-sample.
- **After r4 (13:55Z, the deep-key value read):**
  - r6-runner asked for a harder rule than "read it" on the level optimism, because the optimism feeds itself through
    the leaves. Adopted: tau_lvl measured in G2, G7's smoke clause, and S2's staged action (the grounding weight x2,
    then TreeStrap off for the lap).
  - Added by r7-runner: the grounding-weight rung rule, so tau_lvl is never taken at a weight that already drifts
    offline; the resume-time override that S2's action needs (B1).
  - r6-runner amended all three: a rung counts only above a PRECISION floor and after a PLATEAU; the trigger is TIERED
    (the mild action on the point estimate, TreeStrap off at 2 se); ONE RECIPE across the S lanes. All adopted, and
    fp-speedup's G1 split is agreed by r6-runner.
  - fp-speedup: the +0.0147 is on the PUCT-mean backups (the recursive form should cut it, confirmed in G1), and a
    state-dependent bias survives a played-row anchor. G1's signed gap is split by depth and turn bucket, with the
    depth-cap action.

## 9. The review record: every finding's disposition (reviewer A = completeness, B = the skeptic; r3)

| finding | disposition |
|---|---|
| A1 / B4 the aux head moves the critic trunk | FIXED: a separate design-B evaluator net, its tests, "by construction" claimed only for it (D2, B1) |
| A2 the 400k smoke is 3.3 updates with no resume | FIXED: G7 (>= 800k, kill + resume); not-inert moved to G6 |
| A3 read (i) not computable against either control | FIXED: B5's offline instrument, the same dials on every final (M4) |
| A4 unnamed / misassigned branch cells | FIXED: §6's table; 2 + 2 under "lever leaves", with the named third-donor ruling |
| A5 the whole difference understated | FIXED: D3 (the bundle); frac and beta matched by construction; dose not matched, reported (§5); the config diff test-pinned (B7) |
| A6 the tree block not pinned; TreeOp's defaults | FIXED: D2's pinned dials plus the test; the docstring fix (B3) |
| A7 the machinery unbuilt; no named counters | FIXED: B1-B7 with the derived GATE_COUNTERS and a grep test |
| A8 the label-quality read has no rule; overlapping routes | FIXED: G1's statistic, net, R, n and pass line; one not-green table |
| A9 the beta and LR rules only by reference | FIXED: G5 and G6 written in full, with the order |
| A10 missing house elements | FIXED: lane loss, the suite gate, RESUMES / from_step / timer, the per-arm throughput alert, OWED, the anchors, launch ownership, the object rule, disk (§3-§5) |
| A11 no Step C branch actions | FIXED: §5's own actions |
| A12 / B8 the fusion trigger vs D4's rule | FIXED: D4's EI-form rule is the only switch; the argmax-form fusion read is retired for Step C (play: false; the target enters only through the fixed point) |
| A13 / B2 x14 unjustified off FP@N | FIXED: §5 POWER reports both conversions; X-FLAT likely; M1 and M2 decide |
| A14 / B10 the bench measures the wrong object; no projection | FIXED: B6 on the fleet's net; D1's break-even and its lever order |
| A15 / B15 the stop condition has no band | FIXED: §4's S1-S3 |
| A16 no schedule; the merge hazard | FIXED: §3's order |
| A17 untraced and mis-framed numbers | FIXED: §2's table with file and frame |
| A18 rule names on numbers | FIXED: §2 |
| A19 R7's clip counters untraced; windows unmatched | DISCLOSED in §2; the extraction is to be banked with its windows before ratification |
| A20 / B7 transfer and foe caveats | FIXED: §2's caveats; foe-robust re-reporting |
| A21 the B = 2 read has no instrument or power | FIXED: D4 (instrument = G0-root fixed-point EI per form; power stated) |
| A22 wording | FIXED ("kept recipe"; no "the form only under a tie") |
| A23 JOURNEY 15's per-generation dials | ADDED: B = 1's licence, tau and the frac floor are gen-1 measurements; the TreeOp sits behind the engine interface |
| B1 the one-ply reference not like-for-like | FIXED: stepc2_a (R7's exact operator, 3 keys, the same 8 worlds); SECOND CORRECTION logged; D2's rationale rewritten |
| B3 v' labels optimistic | FIXED: recursive prior-weighted labels; v' never a label; signed gaps (G1, S2) |
| B5 D3's play confound | FIXED: C at play: false at S's frac and beta* |
| B6 EI vs a greedy PPO student; eligible roots | ADDED: G2 (realised distillation on held-out roots); planning numbers on eligible roots at the argmax level alongside EI |
| B9 the resampler is not the posterior | DISCLOSED (§2); M2 reads the trained student's own fixed point, which needs no resampler stand-in for the student |
| B11 the warm-start leaf is not the tree S launches with | FIXED: G2 runs the donor's net as the leaf; B5 names the leaf per final |
| B12-B14, B16 | DISCLOSED in §2 (bucket concentration; what is held out; the label gate's pass line is G1; power-model approximations) |

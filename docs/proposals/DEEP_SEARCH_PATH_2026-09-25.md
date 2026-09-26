# DEEP SEARCH — port the tree, scale it at inference, put it in training (proposal r2, 2026-09-25)

JOURNEY step 14 (the strength chapter; its exit condition asks for "one comparison at a REAL budget"). r1 (`ea9bb97`)
was written the day G2 read DOES NOT CLEAR. **r2 folds in two Opus reviews** (engine port and algorithm; research
strategy and training); the record of what each changed is in §6. It is a PROPOSAL: Step C's fleet gets its own
pre-reg.

## 0. The maintainer's words, verbatim (2026-09-25)

- "how much search budget to use? 10s avg per turn is the max budget ... just want to make sure we aren't leaving room
  on the table at inference."
- "I can't believe we don't have the search tree ported or even have a plan to do deep search in training."
- **"I do NOT want you to kill search in train if 1-ply doesn't work."** This is binding (CLAUDE.md rule 6): R7's
  one-ply verdict sets Step C's DESIGN, never WHETHER Step C runs.

## 1. Where we are (every fact traced)

- **The one search that has beaten greedy is a DEEP tree, and it has never been run bigger.**
  - `rl/search/tree.py`: decoupled UCT with our committee prior and the oppact L6 posterior for the foe, sampled
    chance branches, critic leaves, and the "gumbel" decision rule.
  - §35's XTG9: 900 iterations x 2 worlds = **1,800 total simulations** (`configs/eval/exit_gate_r5.yaml`), **1,547
    evaluations a decision, mean simulation depth 3.76 turns, max 7.38** (`results/exit_gate_r5/xtg9.json`), ~771 ms.
    It beat the same committee greedy off FP@20 by **+0.0319 at z 2.61** (RESULTS §35).
  - Its argmax moved on 4.0% of decisions at 100 iterations and 15.9% at 900 (§32, n=40, descriptive).
  - It lives on `poke_engine` (Foul Play's engine) through Python.
- **The depth-2 history, corrected by review 2 and verified.** r1 said §30's depth-2 costs came from a pinned-opponent
  backup and an unexpanded-leaf artifact. That is WRONG.
  - B2R, the honest MINIMAX backup, ran after the L4 fix and read **-0.0980 at 4.43 se** at a matched override rate
    (0.1862 against the control's 0.1703).
  - §30's reading: "the VEHICLE separates them" -- the depth-2 one-ply-MATRIX vehicle was a measured cost with either
    backup, while the TREE vehicle (visit-based decoupled UCT, gumbel decision) read positive. §30 itself: it "does not
    close depth, the tree or MCTS".
- **R7's searches are ONE PLY, on the native engine.**
  - The training T-op: TRUE world, every legal row x the foe's top-4 x 2 chance samples, one turn, critic leaves.
    ~51.1 leaves a decision (`readouts/R7_B0_BENCH.md`), ~1.8 ms, on 75% of decisions, skipping prior top-1 >= 0.97.
    Its pi' is a 0.1-weight policy target and its values a 0.1-weight value target.
  - G2's L-op: 8 belief worlds, did not clear (+0.0013 at z +0.10, `readouts/R7_G2_READOUT.md`).
  - Stage 0c (running): rollouts vs the critic as the leaf evaluator at one ply.

## 2. The path

### Step A — PORT the tree to the native engine (start now; a new module, in a worktree and a fresh env)

**Where the work happens.** A branch in a worktree, with a FRESH env for any Rust work. The R7 fleet runs from main in
`pkmn-engine-port`, and its spawned collector lazily imports `rl.search.top`; Stage 0c runs in `pkmn-engine-r7`. Step A
adds NEW modules only (review 1).

**Units.** TOTAL simulations (iterations x worlds): §35 = 1,800. Log depth both in engine updates and in battle turns.

**`rl/search/native_tree.py`** (~700 lines of Python on `pkmn_gen1`'s current API; review 1 checked it):
- **Node mechanics** (pin these, or the tree never gets deep):
  - Actions for BOTH seats come from `mask()`.
  - Pass nodes are single-agent and never valued by our critic.
  - Chance: K REUSED children per edge, seeded `leaf_seed(node_seed, b, j)`. A fresh `leaves()` child on every visit
    caps the tree at depth 1. Visit the least-visited first, widen progressively, and MERGE identical outcomes (on the
    `save()` digest) so a double switch does not cost K identical evaluations.
  - The engine gives sampled chance only (no branch probabilities); CRN via `leaf_seed`.
- **The estimand, explicit.** Keep joint (a,b) statistics plus per-side statistics, in three modes:
  - `legacy`: tree.py's decoupled rule, for parity only.
  - `br_prior` (DEFAULT): our PUCT, with the foe sampled from its prior. That is `native.solve`'s own estimand, so
    depth becomes the only difference from R7's operators.
  - `sm_rm`: regret matching at every simultaneous node.
- **The foe prior:** the committee on `obs("p2")`. Oppact L6 is a parity dial, mapped by move ID, with unmapped mass
  counted.
- **Leaves:** the committee's mean critic on `obs("p1")`, rendered from the acting seat's TRACKED view, never a full
  reveal of the determinized foe team. Terminals are +-1/0. Rollout or lambda-mixed leaves are a dial (Stage 0c).
  - On an engine error, play greedy and COUNT it; never back up a fabricated value.
- **Root:** `legacy` reproduces tree.py. `gumbel_mctx` uses completed Q (v_mix) and a visit-scaled sigma; sequential
  halving is allowed only against a stationary root foe. Save the root joint matrix.
- **Engineering:** batch across worlds first, then within a tree (virtual loss cut depth at batch 16). Anytime search,
  iteration-bounded for arms. Dials derived from the signature; unknown keys fail.
- **Do NOT copy these tree.py defects** (review 1):
  - poke_engine legality skips the recharge turn and partial trapping (`bridge.py`).
  - Our side gets moves during the foe's forced switch.
  - The foe can switch only to bench[0].
  - The renormalised top-2 chance truncation drops the third outcome.
  - Det-leaked encodings (a +0.0497 critic shift, `shadow_battle.py`).
  - 0.0 backed up on engine failure.
  - turn+1 fed to the encoder per transition (the L4 family).
  - L6 class j mapped to engine slot j.
- **Rust additions** (fresh env): `SearchNode.outcome` (~10 lines), a multi-parent `expand_nodes` (~200 lines,
  GIL-free), `LeafBatch.from_nodes` (~50 lines). A Rust tree (~1,000-1,500 lines) is Step C's enabler.
- **Counters to disk:**
  - Tree shape: depth histogram, nodes, evaluations, batch duplicates, chance children and merges, Pass / terminal /
    capped / error shares.
  - Root: visits per side, per-world agreement, and a FUSION counter (our argmax disagreement across worlds at equal
    `obs("p1")` digests).
  - Policy: prior top-1, visit pi' and played pi', argmax_moved, a non-None `search/override_rate`.
  - Cost and fallbacks: time split, fallbacks by cause.
  - Stamps: sha, `build_info()`, OBS_DIM, member sha256s.

**GATES** (replacing r1's tree.py-parity gate, which cannot attribute a disagreement across five intended differences):
- (i-a) At depth cap 1 (`br_prior`, top-k columns, chance_s children) the tree REPRODUCES `native.solve`'s Qbar and pi'
  on G0's 500 roots: bitwise at matched batch, else to 1e-6.
- (i-b) Known-answer fixtures: a KO visible only at depth 2-3, Hyper Beam recharge, a partial-trap lock, a Pass node, a
  double-KO tie, and a 2x2 prediction game.
- (i-c) G0's true-world oracle: the tree at 1,800 simulations against the one-ply critic L-op at matched override,
  paired, per mode (Stage 0c's scorer).
- (i-d) DESCRIPTIVE: agreement with tree.py on shared snapshots, beside each tree's own seed-to-seed agreement.
- (ii) A quiet-box P-core bench on 200 turn-stratified G0 roots at nice 0, per rung:
  - sims/s, p50/p99, time split, batch fill, depth histogram vs batch, memory;
  - 1/2/5/10 workers plus a shared-inference process;
  - output: hours per 3,200-battle arm.
- (iii) A two-battle FP smoke whose arm JSON carries every counter.
- A golden test keyed by OBS_DIM and engine sha; determinism at a fixed batch and 1 torch thread.
- Later, the Rust tree equals the Python tree bitwise under a stub evaluator.
- **Strength parity is Step B's first rung:** `legacy` at 1,800 against a same-session greedy control. Missing §35's
  clear triggers diagnosis via (i-c)/(i-d), never a kill.

### Step B — the INFERENCE BUDGET CURVE (reaching the ruled cap)

- **Work = leaf evaluations per searched decision;** a rollout counts at its benched forward-equivalent. Rungs go x4
  from XTG9's ~1,550 up to the CAP = 10 s x 10 P-cores x gate (ii)'s measured rate. At ~15k evaluations/s/core that is
  ~0.7-1.5M evaluations. r1's "~50,000 simulations" stopped 15-30x short.
- **Tier 1 — decision level, on G0's 500 roots** (fixed work, E-cores, runnable beside the fleet):
  - the chosen action and pi' are scored on the oracle, paired across rungs;
  - a depth-cap-1 twin at equal work;
  - sigma set here.
- **Tier 2 — the engine mirror** (G1's harness): rungs up to ~25k, n 2,000-5,000, seat-swapped. This gives the curve's
  shape at battle level; it is inflated, since the foe model is exact there.
- **Tier 3 — FP@N 25k/12k, control first:**
  - (a) Reproduction on the R5 W committee at 1,800 total simulations, n 3,200, with the opp_rule pair {puct, sample}.
    The §35 tree ran the minimizing default.
  - (b) The knee on the strongest object, n 3,200.
  - (c) The cap at n 250, DESCRIPTIVE: ~20 h of the whole box. A credit-line read at the cap (n 3,200) is ~11 days of
    the box -- **the maintainer's call**.
  - FP@500's visits-matched FP@N is a second opponent, not a known-harder one (strength not tested).
- **Knee rule, simulated before tier 3:** the knee is the first rung past which x4 more work adds < 10% of the
  reproduction rung's gain on tiers 1-2. "Within 1 se of the best" cannot separate rungs at +-0.012 an arm, and it
  carries a winner's curse.
- **Overrides:** under a fixed rule, override rises with budget (§32: 4.0% -> 15.9%), so rungs cannot be
  override-matched. Report gain per override, plus ONE matched contrast: the tree vs one-ply at the knee's override.
- **Stage 0c:** if it reads STAGE 1, its rollout operator joins every tier on the same work axis. Tier 1 cannot
  adjudicate (its rollouts share the oracle's continuation); tiers 2-3 can.
- **The ladder operator** is the knee, unless tier 3 reads the cap above it. Design to the ruled 10 s average: 0 on
  forced moves, a cheap check on prior top-1 >= 0.97, a reserve, and a greedy fallback. The clock's 5-s ticks make
  under ~15 s/turn bank-neutral, which is headroom, not budget.

### Step C — DEEP SEARCH IN TRAINING: the lap after R7, REGARDLESS of R7's one-ply verdict

- **Deep by construction** (review 2). 16-64 simulations do not even cover depth one here (~6.7 rows x 4-5 replies x
  chance; the T-op already enumerates that layer in ~51 leaves).
  - The DOSE is a DEPTH FLOOR: mean simulation depth >= 2.5 turns, read from the tree's own counter in the bench. That
    is ~256-1,024 simulations (depth grows ~+0.5 ply per e-fold of simulations: 3.05 -> 3.40 for 400 -> 800).
  - B = 1, on a coin-selected, benched fraction of decisions (KataGo's playout-cap randomization). Batch leaves across
    the collector's 8 in-flight trees.
- **A collector-side TreeOp** (the T-op's seams; dials derived from its signature). Rust-tree speed is its enabler.
- **The true world vs the peek:**
  - B = 1 in training only if a fusion read AT DEPTH on G0's 500 roots passes plan §10's rule. Strategy fusion is a
    per-tree bias: more worlds cut variance, not fusion, and the true world is the fully fused case.
  - Leaves render the acting seat's tracked view.
  - B = 1 is a per-generation dial (JOURNEY 15).
- **Policy target:** completed-Q pi', not visit counts, with sigma set on G0's roots by the split-sample oracle's
  expected improvement. beta*KL stays an auxiliary term with a 0 -> beta* warm-up over ~5M steps; beta* is picked by a
  2M smoke ladder under R7's not-inert rule. Making CE the primary loss is the NEXT lap, and only if mechanism reads (i)
  and (vi) both move.
- **Behaviour:** `play: false` by default. At tree@900's KL(pi' || prior) of 1.669 (§35), PPO's ratio sits far outside
  the clip. Play pi' only if a 400k smoke shows `clip_frac_searched` within 2x of the unsearched rows.
  - CORRECTED 2026-09-26: r2 set this against "the T-op's ~0.16", a figure typed without a source. R7's own training
    counters say otherwise: searched lane f1, over its last 5M steps to 29.5M, reads KL(pi' || prior) **0.330**, and
    PPO clips **51.2%** of searched rows against **8.9%** of unsearched ones (5.7x). Source: the lane's wandb history
    (`runs/r7_fleet_searched_f1_s376`, via `scripts/extract_history.py`).
  - THE RULE'S BASELINE IS WRONG, per the record-only control. Control lane f1 runs the same one-ply search
    record-only (searched 53%, played 0%). Over its last 5M steps to 34.0M, its searched rows ALREADY clip **15.9%**
    against **6.2%** unsearched: 2.6x, with nothing played. That is a selection effect: searched rows are the
    uncertain decisions, where the policy moves most per update. So "within 2x of the unsearched rows" fails even a
    lane that never plays.
  - The rule becomes: searched rows in the playing smoke against the SAME selection in a record-only twin. On R7's
    lanes (different lanes, descriptive) that is 51.2% vs 15.9%, about 3.2x at one ply.
  - Playing a deep tree's pi', which moves further from the prior, can only be worse, so `play: false` is Step C's
    design, not a precaution. R7's pre-registered mechanism reads say what this means for R7 itself.
- **Value:** v' = E_{a~pi'} E_{b~prior} Q(a,b) into R7's aux head, NEVER the root max (G1 measured +0.019 of max
  optimism on top of the critic's). TreeStrap internal-node labels (N >= 16) are a counted dial.
- **Fleet:**
  - The control is whatever base R7's verdict names, warm-started from its finals and paired by final. Re-run the LR
    rule (a third anneal, disclosed).
  - Width comes from a MEAN collector-throughput bench with weights lag <= 1, not p99.
  - Keep 3 + 2: fewer lanes weaken the seed-clustered se.
  - Disk: +~6 GB a lane (CLAUDE.md's disk rule).
- **R7's outcome -> Step C's design,** never whether it runs:
  - X-POS / X-GAIN: the control keeps the T-op, so C isolates depth.
  - (i) not moved: the target form (a beta ladder; CE sooner).
  - (i) moved, (vi) not: the value channel on (TreeStrap plus Stage 0c's leaf).
  - Moved with delta <= 0, or X-COST / X-NEG on that route: `play: false` is mandatory.
  - VOID: R7's control recipe on the R6 trio B donors.

## 3. What changes the plan, and what does not

- **Stops nothing:** a null of any operator at any one budget (rule 6); G2's null; a null OR a cost of R7's one-ply
  training search (the ruling).
- **Redirects, never kills:** a measured COST of the tree at the reproduction rung. Diagnose it first: the
  simultaneous-move estimand (switch modes), the leaf evaluator, the foe prior (opp_rule), fusion at depth.

## 4. Risks named up front

- **Decoupled UCT does not converge** in simultaneous-move games (Shafiei, via Lisy et al. 2013; the prior-work index).
  `br_prior` is the default estimand, and `sm_rm` at EVERY node is the fallback, not an RM root over DUCT internals.
- **Strategy fusion** grows with depth over determinized worlds. More worlds cut variance, not fusion, and the true
  world in training is FULL fusion, so it is gated by the fusion read at depth.
- **The critic is queried off-distribution at depth.** ExIt / TreeStrap on the tree's own states is the known fix;
  rollout leaves (Stage 0c) are the other lever. The critic's gap is 93% ranking (§27.1): tier 1's depth twin at
  equal work measures whether depth buys anything, which sets the dose, never whether Step C runs.
- **NN leaf cost dominates.** Review 1's estimates, which the bench decides: tree.py ~2.3k sims/s; Python on native
  ~3-5k; a Rust tree ~5-7k; a distilled leaf net ~20-40k per P-core. Levers in order: distilled leaf net, Rust tree,
  batching across worlds, outcome merges with no critic at Pass nodes, a fused committee forward. Root-parallelism
  scales sublinearly on this CPU.
- **Tuning transfers badly across budgets:** dials are re-set per rung, never carried.
- **The port loses §35's gain:** the defects above change the object. Gate (i-c) and the reproduction rung catch it.

## 5. Sequencing on one 10-P-core laptop (instruments never contaminated)

- **Now -> the fleet's end (~Sunday):**
  - Build Step A in its worktree and fresh env.
  - Gates (i-a)/(i-b), tier 1 (up to ~100k), the fusion read and sigma all run on the E-cores at background QoS once
    Stage 0c frees them: fixed work, never timed.
  - Hold Step B's FP@N seats, since at 25k+ evaluations a decision they take P-cores from R7.
  - R7's own counters (kl_prior, the clip split, child_idle) can be read today, for free.
- **At the fleet's end:** a few quiet-box minutes for gate (ii) and Step C's width bench, tier 1's cap rung, then R7's
  reads, and fp-speedup's FP@500 calibration window.
- **After R7's reads:** Step C's pre-reg, its smokes, then its fleet. Tiers 2-3 run beside it, since fixed work costs
  time, never strength. The cap rung goes last, on a quiet box.

## 6. Review record (2026-09-25, two Opus reviewers, read-only)

- **Review 1 (engine port and algorithm):**
  - Feasible now in Python on `pkmn_gen1`'s API.
  - Pinned the node mechanics (reused chance children, Pass nodes, masks for both seats, total-simulation units) and
    the explicit estimand (legacy / br_prior / sm_rm).
  - Listed tree.py's defects not to copy.
  - Replaced the parity gate with a bitwise depth-1 reduction plus fixtures plus oracle decision quality.
  - Named the fleet-env hazard; gave performance estimates and levers.
- **Review 2 (strategy and training):**
  - Made Step C deep by construction (a depth floor, ~256-1,024 simulations, playout-cap randomization).
  - Gave Step B three tiers and a cap in leaf evaluations, and replaced the knee rule.
  - Set completed-Q with sigma from G0, the beta warm-up, `play: false` by default, and the value estimand.
  - Added the fusion-at-depth gate, the R7-outcome -> design table, sequencing and the disk note.
  - **Caught r1's wrong depth-2 history** (§1).

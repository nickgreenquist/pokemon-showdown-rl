# DEEP SEARCH — port the tree, scale it at inference, put it in training (proposal, 2026-09-25)

JOURNEY step 14 (the strength chapter; its exit condition asks for "one comparison at a REAL budget"). DRAFT, written
the day G2 read DOES NOT CLEAR. It is under two Opus reviews, and their findings get folded in below.

## 0. The maintainer's words, verbatim (2026-09-25)

- "how much search budget to use? 10s avg per turn is the max budget ... just want to make sure we aren't leaving room
  on the table at inference."
- "I can't believe we don't have the search tree ported or even have a plan to do deep search in training."
- **"I do NOT want you to kill search in train if 1-ply doesn't work."** This is binding: R7's 1-ply verdict informs the
  DESIGN of the training-search lap below and never WHETHER it runs. CLAUDE.md carries it.

## 1. Where we are (every fact traced)

- **The one search that has beaten greedy is a DEEP tree, and it has never been run bigger.**
  - `rl/search/tree.py`: decoupled UCT over 2 determinized worlds. Our side's prior is the committee's masked policy;
    theirs is the oppact head's L6 posterior. Chance branches are sampled per visit, the committee's critic sits at
    the leaves, and the decision is the "gumbel" rule, pi' = softmax(logits + beta * q_norm).
  - At 900 iterations (~771 ms/decision) it beat the same committee greedy off FP@20 by **+0.0319 at z 2.61**, n 3200
    each (RESULTS.md §35).
  - At 400 iterations it reached a mean simulation depth of **3.05 turns, max 6.58** (692 network evaluations, 280
    ms/decision; `docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md`).
  - Its argmax moved on 4.0% of decisions at 100 iterations and 15.9% at 900 (§32, n=40, descriptive): still moving
    with budget. No config runs it above 900.
- **It lives on the WRONG ENGINE for scale.** It is built on `poke_engine` (Foul Play's engine) through Python
  (`rl/search/bridge.py`, `generate_instructions`). At ~0.8 s a decision it cannot run inside training, and large
  offline reads with it are slow.
- **R7's searches are ONE PLY, on the native engine.**
  - The training T-op sees the TRUE world: every legal row of ours x the foe's top-4 replies by the committee prior x 2
    chance samples, then ONE turn simulated and the critic at the leaf. Soft best response at tau 0.05. About 51 leaves
    a decision (`readouts/R7_B0_BENCH.md`), ~1.8 ms, on 75% of decisions, skipping prior top-1 >= 0.97. Its pi' is a
    0.1-weight policy target and its values a 0.1-weight value target (`configs/r7_fleet_searched_*.yaml`).
  - G2's L-op is the same one ply over 8 belief worlds. It did not clear: +0.0013 at z +0.10
    (`readouts/R7_G2_READOUT.md`).
- **The native engine already exposes a tree's building blocks:** `pkmn_gen1.SearchNode.expand` (children),
  `leaves` / `LeafBatch` (batched stepping and rollouts), `obs`, `mask`, `view`, `save` / `load`, `from_root`. Engine
  parity with Showdown is measured (the port's P-1: zero mismatches).
- **Stage 0c** (running, `scripts/r7_stage0c_rollout_curve.py`) measures whether ROLLOUTS beat the critic as the leaf
  evaluator at one ply. Its answer feeds the tree's leaf choice.

## 2. The path

### Step A — PORT the tree to the native engine (starts now; engineering, no box contention beyond tests)
- `rl/search/native_tree.py`: `tree.py`'s algorithm on native `SearchNode` states.
  - Decoupled selection per side: PUCT with our prior and the oppact posterior.
  - Sampled chance and a depth cap.
  - The Gumbel decision rule at the root (sequential halving as an option).
  - Batched critic evaluation across in-flight simulations (virtual loss).
- Worlds: sampled beliefs from B6's bridge for live play; the TRUE world in training.
- Counters to disk: depth reached, nodes, evaluations, chance branches, visits per side.
- GATES before any arm:
  - (i) Decision parity with `tree.py` on a fixed position set at equal iterations: agreement of the root decision and
    of visit shares, within a pre-stated tolerance. Not bitwise, since the engines and RNG differ.
  - (ii) A P-core speed bench on a quiet box: simulations/s and decision latency at 64 / 256 / 900 / 3,600 / 14,400
    iterations, one world and root-parallel.
  - (iii) A two-battle smoke through the FP harness.

### Step B — the INFERENCE BUDGET CURVE (after R7's reads; the approved plan, widened)
- **Rungs in WORK units:** the native tree at 900 -> 3,600 -> 14,400 -> ~50,000 simulations, root-parallel over worlds
  on the 10 P-cores. Beside it, the one-ply rollout operator at Stage 0c's knee, if Stage 0c says STAGE 1.
- **Opponents:**
  - FP@N 25k/12k, run K-wide at fixed work.
  - The visits-matched FP@N of FP@500, for a stronger opponent (fp-speedup's calibration).
- **Protocol:** same-session greedy control launched first; overrides matched where comparable; a pre-stated knee rule
  (the smallest rung whose gain is within 1 se of the best's).
- **The ladder operator** is the rung at the knee, converted to seconds by the bench and capped by the clock: ~10 s/turn
  sustained, 5-s ticks, so under ~15 s/turn is bank-neutral. Its time management spends 0 on forced moves and a cheap
  check on prior top-1 >= 0.97, keeps a reserve, and falls back to greedy.

### Step C — DEEP SEARCH IN TRAINING: a lap after R7, REGARDLESS of R7's 1-ply verdict (the ruling)
- **The operator:** the native tree at a small simulation budget in the collector, on the TRUE world. Gumbel MuZero's
  regime: its policy improvement holds with as few as 16-64 simulations when Q is right.
  - Selective, as the T-op is: contested decisions only.
  - Policy targets are Gumbel's completed-Q pi'. Value targets come from the search, the target weight is set by
    pre-reg, and a control arm runs beside it.
- **The budget is set by throughput:** a B0-style bench at the fleet's width (the T-op's 3.6 ms p99 line was a
  throughput line, not a law) decides lanes x simulations. Fewer, deeper-searching lanes are an option.
- **What R7's 1-ply verdict changes:** the dose (simulations, target weight, how selective), the leaf evaluator, and
  whether the fleet warm-starts from R7's searched or control lanes. NEVER whether this lap runs.

## 3. What changes the plan, and what does not

- **Does NOT stop anything:** a null of any operator at any one budget (CLAUDE.md rule 6); G2's null; a null OR a cost
  of R7's 1-ply training search (the ruling).
- **Redirects, never kills:** a measured COST of the deep tree at matched override on the budget curve. Diagnose it
  (the simultaneous-move backup, the leaf evaluator, the opponent prior, strategy fusion at depth) before the next
  rung. §30's depth-2 costs came from a pinned-opponent backup and an unexpanded-leaf artifact (CLAUDE.md landmines),
  not from depth.

## 4. Risks named up front

- **Decoupled UCT** is not guaranteed to converge to equilibrium in simultaneous-move games. Visit-share decisions plus
  the Gumbel rule are the practical fix; a regret-matching root is the fallback.
- **Strategy fusion** grows with depth over determinized worlds. More worlds and the true world in training bound it;
  the live gain from the peek was measured small at one ply (G1b).
- **The critic is queried off-distribution at depth.** Expert iteration on the tree's own states is the known fix
  (TreeStrap / ExIt); rollout or hybrid leaves are the other lever (Stage 0c).
- **NN leaf cost dominates** (~15k leaves/s per core at one ply in G2): batching, a distilled small leaf net, and
  native inference are the speed levers.
- **Tuning transfers badly across budgets** (the Foul Play exploration constant that inverted between 100 ms and ladder
  play): dials are re-set per rung, never carried.

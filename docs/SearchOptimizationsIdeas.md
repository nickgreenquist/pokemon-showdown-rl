# Search optimizations: the catalogue

2026-09-26. Every optimization of SEARCH that the literature and this repo offer, for (a) search inside TRAINING
(learner targets and collector throughput) and (b) search at INFERENCE (~10 s a turn on one laptop). It covers SPEED
(more search per second) and EFFICIENCY (more learning signal or decision quality per unit of search). Each idea
carries its status here, its expected gain on this box and why, its build cost, its risks and collisions with
CLAUDE.md and `docs/landmines.md`, and the counter that would measure it.

This is a research catalogue. Nothing in it credits a lever, and no entry is a pre-registration.

**JOURNEY position.** It serves step 14, the strength chapter ("search over OUR OWN value function"), open since
2026-09-22 with R7 running and Step C's pre-reg in draft. Every lever is written to sit behind the rules-and-encoder
interface that step 15 requires; a lever that works only because of a gen-1 fact is flagged as such. Nothing here
touches step 16's human data.

**What was read.** `main` at `df1222c` and the branch `deep-search-step-a` at `f60e58d`, where the deep tree lives.
CLAUDE.md, STATUS.md, JOURNEY.md, `docs/landmines.md`, `docs/prior_work/README.md` (first, as it asks), the three
proposals the brief names, `docs/IDEAS_POST_100M.md`, `docs/CLEANUP.md`, RESULTS §20-§35, the readouts, SESSION_LOGS
from 2026-09-22 on, and the search code on both refs. Outside: 59 papers read as PDF text, 58 of them from the Kaggle
arXiv mirror on Google Cloud Storage and the AlphaZero preprint from DeepMind's own bucket; and code read at pinned
commits (mctx, KataGo, lc0 and its wiki, Leela Zero, ELF, Polygames, MiniZero, EfficientZero and V2, LightZero, muzero-general, OpenSpiel, alpha-zero-general, ReBeL, DeepStack-Leduc,
poke-engine, Foul Play, PokéChamp, poke-env, WU-UCT, the PyTorch 2.13 sources, ONNX Runtime, coremltools, Stockfish's
NNUE docs, `corsix/amx`, `tzakharko/m4-sme-exploration`). This sandbox blocks arxiv.org, openreview, nature.com,
science.org, PMLR, NeurIPS, IEEE, ACM and Springer, so conference-only papers (Frank & Basin 1998, Long et al. 2010,
Cowling et al. 2012, Heinrich & Silver 2015, Chaslot et al. 2008, TreeStrap 2009, the Gumbel and Stochastic MuZero
papers) are cited through secondary sources or marked unverified.

**Legend.**
- [V]: read in the primary source, the paper's PDF or the code or docs at a named commit.
- [V2]: read in a secondary source that restates the primary; the secondary is named.
- [U]: unverified: an abstract or search snippet, a recollection, or the task brief.
- [R]: a fact of this repo, cited by file:line, commit or SESSION_LOGS entry.
- [D]: derived here by arithmetic from cited facts; an estimate, not a measurement.
- MEASURED and CLAIMED are said in words, with the hardware a result needed.

**The answer in one paragraph.** On this box a search's cost is network CALLS plus network ROWS; the engine is about 1
µs a leaf. A call costs a fixed ~0.14-0.2 ms when idle plus ~6.5 µs (actor) to ~12 µs (critic) a row, and fleet-width
contention roughly doubles it. The first training-side finding is a correction: every Step C input was measured with the
tree's batch at 8, while the TreeOp's default is 1, which is a different search at ~8× the rounds (§1.2). The largest
training-side lever is structural: under `play: false` no engine step needs the search result, so a lane can defer its
searches and run them in wide lockstep, in the child or on the learner's idle core. That cuts the fixed term 30-100× and
fits Step C inside its throughput floor. Hours-level cuts stack on it: remove duplicate forwards, land the bit-identical
trace, and turn on lazy priors once rounds are cheap. At inference and on reads, a fused committee with batched worlds
cuts a one-ply seat's time by about a third, skipping confident decisions saves ~40%, and sequential halving plus that
skip take Stage 1's rollout arm from ~1,800 to ~580 P-core-hours; reaching the approved 30-200 needs a cheaper rollout
policy too. Spread over the ladder seat's 10 cores, the rollout evaluator fits the clock. On quality,
the measurements say the evaluator binds, not depth, so the budget belongs on the evaluator: rollouts, label campaigns,
TreeStrap and reanalysis.

**CORRECTIONS (2026-09-26 ~16:10Z, r7-runner, MEASURED on this box; they win over the [D] numbers below where they
conflict).**
1. **C1 is already in the draft.** Step C DRAFT r4 (`09f01eb`, §1 "THE TREE") pins stepc_a's stamped `tr_256` dials,
   batch 8 included, and says the TreeOp's own defaults (batch 1) are never relied on. This catalogue read r3 at
   `df1222c`. No pre-reg edit is owed.
2. **§1.2's two-term model does not hold for stock `nn.Linear` here, and the cause is the kernel, not contention.**
   `nn.Linear` calls Accelerate's sgemm with the weight transposed as a view, and that path is slow at 2-16 rows. A
   1024x1024 layer costs ~590 us at 2-12 rows, against ~20 us at 1 row (gemv) and ~45-60 us for the same product on a
   contiguous W.T. That holds on a P-core beside the fleet AND on the E-cores (~1,300 vs ~160 us), whose matrix unit
   the fleet does not touch (F2/Q2).
   - On the fleet net (R6 trio B b328, c6-on), in situ under the fleet's load: the critic costs 0.33 ms at 1 row and
     1.24-1.64 ms at 2-32 rows; the policy prior 0.49 ms at 1 row, 0.83-1.06 at 2-32 (`results/native_tree/
     cost_model_r3_b328_stock.json`).
   - So §1.6's "batching independent work into one call is nearly free at <= 8 rows" is false for the stock layer:
     1 -> 2 rows is ~4x on the critic.
   - `rl/common/fast_linear.py` (branch `deep-search-step-a` `ca662a3`; opt-in, no-grad forwards only) runs the product
     on a cached contiguous W.T. It is bitwise at 128 rows and within ~3e-7 at 8, the size of stock's own
     batch-to-batch difference.
3. **Q1 is answered without a quiet box, and §1.3's Step C costs are 3-8x low.** The work-unit cost model
   (`rl/search/cost_model.py`, `scripts/native_tree_gates.py calibrate`; branch `61c64d2` + `9f9d1f4`) prices a
   search from its deterministic counters. Its calibration runs under any load, with the load tagged.
   - Held-out median error 2.3-3.2% on four calibrations: G0's committee and the fleet net, each with stock and fast
     Linear, all under the R7 fleet's load (load1 ~11).
   - Step C's lever (stepc_a's tr_256 dials) on the fleet net, per searched decision (`results/native_tree/
     stepc_cost_scenarios.json`, `scripts/native_tree_cost_scenarios.py`):

   | design | stock | fast Linear |
   |---|---|---|
   | in-line, 1 decision a call (Step C's floor) | 108 ms | 70 ms |
   | in-line, 3 a call (R7's frac) | 61 ms | 50 ms |
   | deferred lockstep (D1), 16-64 a call | 42 ms | 39 ms |
   | D1 + lazy priors, 64 a call | 36 ms | 33 ms |
   | in-line at batch 1 (the TreeOp's default) | 246 ms | 210 ms |

   - §1.3 left out PYTHON: ~17-21 ms a decision plus ~7 ms of engine. That is about half of D1's cost, and lockstep
     width does not amortize it.
   - So D1 is worth ~2.6x over in-line, not 30-100x, and the Python cuts (F6, F7) rank right after D1, not at #22.
4. **Q0: the collector child binds in every R7 lane** (offline wandb histories, no resumes; `results/r7_q0/`, re-derive
   with `scripts/extract_history.py`).
   - `collect/child_idle_frac` median is 0.000 on 5/5 lanes, over the whole run and the last 10M steps.
   - Per update (~122,900 steps) the learner updates for 90-119 s, then waits `time/collect_sec` 39-67 s for the
     child.
   - `search/seconds` is 135-150 s of the searched child's 162-185 s a rollout, and 103-106 of 129-133 s on the
     record-only controls. Greedy collection is the other ~25-36 s.
   - Eligibility reads 0.81 (searched) and 0.68 (controls), not ~54%. `search/searched_frac` is 0.61 / 0.51 at
     `frac` 0.75.
   - So D1 needs BOTH cores. At Step C's floor (`frac` 0.25, ~21-25k searched decisions a rollout) and >= 289 steps/s
     (<= 425 s a rollout), the child has ~395 s spare and the learner ~306 s after R7's update. Together that is
     ~700 s, or ~28-33 ms a searched decision; either core alone gives ~12-19 ms. D1 + lazy + fast (~33 ms) sits at
     that edge before Step C's evaluator training lengthens the update. Fitting with margin needs the Python cut, or a
     longer run than 4 days (the maintainer's call).

## 0. Ranked summary

Ranked by expected gain on this box per unit of build cost. T = training, I = inference, B = both. "§" is the entry
in §2. Gains are derived from §1's cost model unless a measurement is cited.

| # | idea (§) | T/I/B | status here | expected gain on this box, and why | build cost | risk |
|---|---|---|---|---|---|---|
| 1 | Pin Step C's per-tree `batch` to 8, the measured object, and read batch and in-flight penalty at equal rounds (C1) | T | NEW finding: Step C's dose omits `batch`; the TreeOp default is 1 | Avoids running an unmeasured search at ~8× the rounds: ~17 ms a searched decision at batch 8 against ~88 ms at batch 1, idle [D] | one line and an oracle read | none; it is a correction |
| 2 | Defer the searches under `play: false` and run them in wide lockstep, in the child or on the learner's idle core (D1) | T | NEW | The fixed-call term falls 30-100×; a searched decision costs its rows, ~5-6 ms idle, inside the floor's ~19 ms [D] | 1-2 days | only under `play: false`; a tolerance check against in-line |
| 3 | Remove duplicate and avoidable forwards: eligibility, batch-1 foe priors, per-row critic calls, per-tree grids, forced-node priors (A2) | B | NEW | ~1.4× on the T-op's searched share; fewer calls a poll in the TreeOp [D] | hours | not bitwise; R7's lanes import this code |
| 4 | Land the traced forward on every search path (A1) | B | PLANNED (CLEANUP E3); measured on the actor only | 1.6× on batch-1 calls, 1.1-1.25× at 8-64 rows; ~1.15-1.2× a decision [R, D] | an afternoon plus a guard | low: bit-identical |
| 5 | Lazy priors on, once rounds are wide (A6) | B | BUILT, off | ~40% fewer rows, ~1.3-1.5× under D1 [D]; may lose inside `poll()`, where extra rounds cost | done; a quality read | a different search at batch > 1 |
| 6 | Skip confident decisions in the inference operators (A13) | I | NEW; BUILT in the T-op | ~40-46% of a searched seat's time on reads; π_θ top-1 ≥ 0.97 on 46% of G0 positions [R, D] | an hour plus an offline read | the override rate moves |
| 7 | Fuse the committee and batch the one-ply L-op's worlds (A4, A5) | I | A4 PLANNED (DEEP_SEARCH_PATH §4); A5 NEW | One-ply seat from 51 member forwards to ~3 calls, idle 25.8 → ~17-18 ms, ~1.45×; the ~1,080 critic rows remain; tree L-op 6 → 2 calls a round [D] | 1-1.5 days | not bitwise; re-anchor reads |
| 8 | The rollout cost stack: sequential halving, skip, fused or distilled rollout policy, control variates, truncation (A14) | I | SH measured offline; skip PLANNED; rest NEW | Stage 1's arm from ~1,800 to ~580 P-core-hours with the two planned levers [D]; the approved plan budgeted 30-200, which needs a cheaper rollout policy too | hours to days | every item but the variance tricks changes the estimator |
| 9 | Root parallelism over worlds for the ladder seat, spent on rollouts (C4) | I | NEW | ~8× search per wall second; the rollout evaluator at the knee goes from ~60 s a decision to ~6 s on 10 cores, ~3.5 s with SH [D] | a day | ladder only; needs time management |
| 10 | Reanalysis: re-search stored positions with the newest weights for the KL and evaluator terms (D2) | T | NEW | More learning signal per search; batches as wide as the sample | a day after D1 | a critic-side stream; keep the on-policy stop condition |
| 11 | Evaluator label campaign and TreeStrap, with a rented GPU for the offline search (D5, D6, C8) | T | D5, D6 PLANNED (Step C D2; R7 box 5 item 7); C8 NEW | The evaluator is the measured binding constraint, and this is its lever | days | the peek in true-world labels; version pins |
| 12 | Early stopping: one survivor under SH, a KLD-gain or smart-pruning stopper (B7) | B | NEW (`deadline_ms` BUILT, unused) | V-MCTS spent ~half the simulations for 71% vs 75% on 9×9 Go [V]; here the saving is the decided share of decisions | ~20 lines and a read | the override rate moves |
| 13 | A virtual mean or in-flight counts instead of the virtual loss (C5) | B | NEW | Lets C1 raise the per-tree batch with less distortion: 68% vs 29.5% against 512 sequential evaluations in Batch MCTS [V] | hours plus Q4 | a new search to read |
| 14 | A value cache on observation digests, and common chance across worlds (A7) | B | NEW | Exact row savings; the hit rate is unknown (Q6) | an hour plus a read | A7b raises chance variance in Q̄ |
| 15 | Probe the shared matrix unit (F2) | B | NEW | Decides how many searched lanes or seats a box holds, and whether a NEON leaf pays | an hour | none |
| 16 | Gate the critic's dead `move_net` branch (A3) | B | PLANNED (IDEAS 2.9) | A few percent of every critic call, bitwise | an hour | none |
| 17 | Measure PIMC-friendliness: disambiguation, leaf correlation, bias (E2) | B | NEW | An instrument for Step C's unresolved fusion read at depth | hours | none |
| 18 | Mix the foe model toward an equilibrium at foe nodes (E5) | B | NEW | G0 reads the foe model as first-order: `opp_model_gap` +0.059, best reply outside top-4 on 25% [R] | hours plus a read | the ladder's humans are a different population |
| 19 | A distilled leaf network, or an NNUE-style incremental one (A10) | B | PLANNED (DEEP_SEARCH_PATH §4); incremental NEW | Cheap rows off the shared matrix unit, only if it keeps the committee's ranking | days to a week | the evaluator binds |
| 20 | One trunk for policy and value (A8) | B | PLANNED as its own lap | Halves calls a round, ~1.3-1.6× on a tree decision [D] | an architecture lap | not actor-neutral in PPO |
| 21 | One tree over our information sets (E3) | I | NEW | Bounded by the fusion cost at depth; MAPLE gained +291 Elo in Phantom Go but lost to PIMC with random worlds [V] | a week | world selection is part of the method |
| 22 | A Rust tree, a Python-free evaluator, less PyO3 traffic (F5, F6, F7) | B | F6 PLANNED; F5, F7 NEW | At most the Python share of a decision, which is unmeasured | a week or more | extension reinstalls mid-block |
| 23 | Exact or stratified chance (B5) | B | PLANNED (Rust plan) | Lower variance per leaf at equal leaves; size unknown (Q8) | multi-day Rust | a second engine artifact |
| 24 | Weight worlds by the foe's observed actions (E4) | I | NEW | Small in gen 1 by D19's residual; read offline first | hours | a gen-1 fact, so behind the interface |
| 25 | Raise the collector's `k` for lockstep width (C2) | T | conditionally PLANNED (R7 plan box 6) | ~4× on the fixed term at k 32 [D]; D1 gets the width without staleness | a config and a read | 12.6% off-policy rows at k 256 |
| 26 | A shared inference process (C3) | I | PLANNED as a question | Only for C4's pool or a Neural Engine server | a day | one process fails for many seats |
| 27 | Second-order dials: surprise weighting (D7), short-horizon heads (D8), budget schedules (D11), adaptive foe columns (B10), variance-scaled cPUCT (B12), disagreement-weighted backups (B13) | B | NEW | Unknown or second-order while the evaluator binds | hours each | each moves the override rate or the objective |
| 28 | Recorded so they are not re-proposed: forced playouts and target pruning (B3), root noise (B4), graph search (B6), row sampling (B9), tree reuse (B15), calibration (B16), compile or export (A9), int8 or fp16 (A11), weight averaging (A15), the Neural Engine (F3), MPS (F4), preallocated buffers (F8), pipelining (C6), thread overlap (C9), ReBeL-class solving (E6), mixed root play (E7), Smooth UCT (E8), clip exclusion (D9) | B | mixed | moot, low, or waiting on a measurement named in the entry | none now | as each entry says |
| 29 | Built, measured or settled, kept in §2 for their status and cites: skipped evaluations (A12), the SH root (B1), the target's form (B2), budget gating dials (B8), the estimand (B11), depth and dose (B14), lanes against cores (C7), playout-cap randomization (D3), value targets (D4), the β warm-up and cross-entropy lap (D10), PIMC world count (E1), other Pokémon agents (E9), threads (F1), QoS rules (F9) | B | BUILT, PLANNED or reference | nothing new to gain; each entry says what would reopen it | none | none |

**Measured as strength levers under this critic; open as cost levers.** Depth past ~1,800 simulations (tier 1 flat), the
training tree's root choice against the one-ply T-op (tier 1b tie), decoupled UCT and regret matching as the estimand
(both below `br_prior` at 1,800), completed-Q as a one-world target (learnable part ~0), belief breadth at one ply (B32
against B8 flat), and root sequential halving at 1,800 (no change). These are decision-level reads, not battle A/Bs, and
they reopen whenever the evaluator changes (CLAUDE.md rule 6).

## 1. The search stack today, and what it costs

Read at `main` = `df1222c` and branch `deep-search-step-a` = `f60e58d` (2026-09-26). `results/` is gitignored, so every
number is cited from the committed file that carries it. A number that lives only in a gitignored file or in the task
brief is marked [U].

### 1.1 The operators

| operator | file | what it does | worlds | leaves a decision | network calls a decision | measured cost |
|---|---|---|---|---|---|---|
| one-ply `native.solve` | `main:rl/search/native.py:88-268` | Every legal row × the foe's top-`cols_k` columns × `chance_s` samples. One Rust `expand` per world (`:196`), one `value_fn` per world (`:199`), soft best response to the foe's prior at `tau` (`:214`). Dials derived from the signature (`:286`). | 1 or B | ~51 at k 4 / S 2 | 1 critic call per world | see the next two rows |
| T-op (training, R7) | `main:rl/search/top.py:52-221` | Inside the collector's `poll`. Eligible = more than one legal row and π_θ top-1 < 0.97, then a coin at `frac` (`:147-150`). One `solve` per searched row, in sequence (`:154-186`). | 1, the true world | 51.1 (`readouts/R7_B0_BENCH.md:24-30`) | per searched row: 1 batch-1 foe-prior actor call (`top.py:160-163`) + 1 critic call on ~51 rows; per poll: 1 extra actor call for eligibility (`top.py:147`) | six-wide mean 1.76-2.15 ms, fleet p99 7.46 ms; critic forward mean 1.61-1.96 ms, p99 4.4-7.1 ms; engine + tracker ≤ 0.048 ms (`readouts/R7_B0_BENCH.md:22-32`) |
| L-op (inference, G2) | `main:rl/search/lop.py:88-229` | B worlds, each a Python determinization + `build_root` (`:151-154`), a foe prior from the committee (`:159`), a `solve` (`:160`), in sequence. PIMC mean of Q over worlds (`:184`), margin gate (`:191`). | 8 | 393.7 (`readouts/R7_G2_READOUT.md`) | 17 committee calls = 51 member forwards, all sequential (derived from `lop.py:135`, `:151-170`; `ensemble.py:69-83` takes one observation per call) | seat p50 49.6 / p99 137.0 ms beside the fleet, load-inflated (`readouts/R7_G2_READOUT.md`); 25.8 ms a decision on the idle box, 360.7 leaves (SESSION_LOGS 2026-09-25 07:28Z) |
| old tree | `main:rl/search/tree.py` | Decoupled UCT on Foul Play's `poke_engine`, committee prior, oppact foe prior, sampled chance branches, batch-16 virtual-loss descents | n_det 2 | 1,550 at iters 900 (`readouts/TREE_BUDGET_R5_READOUT.md`) | one combined `eval_fn` per 16 descents per world | 771 ms a decision at iters 900 (XTG9; `readouts/EXIT_GATE_R5_READOUT.md`); the one search that beat greedy in battles, +0.0319 at z 2.61, PRE-FP@N (RESULTS §35) |
| native tree | `deep-search-step-a:rl/search/native_tree.py` | PUCT over the foe-prior-weighted joint matrix (`br_prior`), a root grid equal to `native.solve`'s batch (`:669-723`), `chance_k` reused chance children with merges on the RNG-masked `save()` digest (`:426-441`), Pass nodes descended through, virtual-loss batches, `search_many` lockstep across worlds and decisions (`:782-900`), sequential halving (`:819-831`), five root rules | 1 or 8 | 228 at 256 sims (1 world); 1,617 at 1,800 (8 worlds); 17,459 at 28,800 (SESSION_LOGS 2026-09-26 09:45Z, 10:30Z) | 2 per ROUND (one value, one prior) plus one value call per tree for its root grid; see §1.2 | E-core, background-QoS seconds only: 4.4 s per 1,800-sim search at batch 4 (SESSION_LOGS 2026-09-26 05:15Z); 1.6 s a decision in the 2-battle smoke beside the fleet (2026-09-25 23:45Z). The P-core bench (gate ii) is built and has not run. |
| TreeOp | `deep-search-step-a:rl/search/tree_top.py:66-247` | The T-op's seams with one `search_many` over every searched row of a poll (`:160-181`); refuses an antisymmetric or privileged critic (`:83-85`) | 1 | as the tree | 2 per round, shared by the poll's searched rows | unbenched |
| tree L-op | `deep-search-step-a:rl/search/tree_lop.py:56-214` | The L-op with the native tree over its worlds (`:143-144`); prior stacks 3 member actors per call (`:80-92`), value 3 member critics (`:94-98`) | 8 | 1,539 (smoke) | 6 member forwards a round | 1.6 s a decision (smoke) |
| rollout L-op (Stage 0c) | `main:scripts/r7_stage0c_rollout_curve.py`, `scripts/rollout_q.py` | The whole row × column matrix played to the end once per belief world by the committee on both seats, lockstep over `LeafBatch.step` | R | 6,610 rollouts at R 128; 26,522 at the knee R 512 | one committee policy step per lockstep step | 64 rollouts/s per process on contended E-cores; ~60 s a decision per P-core; ~1,800 P-core-hours per 3,200-battle arm (SESSION_LOGS 2026-09-26 03:45Z) |

### 1.2 The cost model this document uses

**The engine is not the cost.** `SearchNode.expand` releases the GIL and batches
(`main:engine/pkmn_gen1/src/pysearch.rs:286-345`). B0 measured engine + tracker at ≤ 0.048 ms for a 51-leaf decision,
about 1 µs a leaf (`readouts/R7_B0_BENCH.md:30`).

**A forward costs a fixed part plus a per-row part.** The only curve on this box is the actor's act path, one thread,
idle (`docs/engine_port/NOTES.md:2169-2204`). The trace is bit-identical at every batch and was never landed
(`docs/CLEANUP.md:206-216`, item E3).

| rows | eager µs | `torch.jit.trace` µs | trace speedup |
|---|---|---|---|
| 1 | 135.7 | 84.9 | 1.60× |
| 4 | 196.2 | 150.3 | 1.31× |
| 8 | 249.6 | 201.4 | 1.24× |
| 64 | 611.3 | 563.1 | 1.09× |
| 256 | 2,356.4 | 2,105.0 | 1.12× |

The same note reads the collection model as "a forward at ~230 us almost regardless of row count, i.e. ~4.6 us per
tensor op" (`NOTES.md:2173-2175`), the same order as PyTorch's own ≈ 5 µs per op ([V, MEASURED, hardware not stated]
https://github.com/pytorch/pytorch/issues/41383). The table itself says rows are not free. One row costs ~0.14 ms; from
8 to 64 rows the curve is ~0.2 ms plus ~6.5 µs a row, and above 64 it climbs ~9 µs a row. The critic has never been
timed on its own curve. Three repo facts pin it:

| fact | source | what it gives |
|---|---|---|
| W critic 1,807,489 params vs actor 626,059; about 2.49M vs 1.61M MACs a row | `scripts/r7_b0_bench.py:79-80`; MACs derived from `rl/networks/entity_deepsets.py` layer shapes | the critic's per-row term is about 1.5× the actor's [D] |
| one-ply L-op idle at 25.8 ms a decision: 24 critic calls of ~45 rows and 27 actor calls of 1 row | SESSION_LOGS 2026-09-25 07:28Z; call count from `lop.py:151-170` | consistent with a critic call ≈ 0.2 ms + ~12 µs a row when idle, if determinization and Python take ~4 ms [D] |
| B0's 51-row critic call at 1.61-1.96 ms, six-wide with a learner-load process a lane | `readouts/R7_B0_BENCH.md:22-32` | fleet-width contention roughly doubles a call [D] |

A fourth fact bounds the whole box. A bare `torch.mm` at the scorer's production shape reached 1,421 GFLOP/s on one
thread and 2,211 on two, then plateaued at 4 and 6 (`NOTES.md:2207-2225`). Apple's matrix unit is one shared block per
CPU cluster, and a single thread can saturate it ([V] `tzakharko/m4-sme-exploration` `reports/01-sme-overview.md#L44`;
[V] Remke & Breuer, "Hello SME", arXiv:2409.18779 §III-F). If that plateau is the box's matrix units, every process on
the box shares roughly 2.2 TFLOP/s of fp32 GEMM. Whether the fleet's small GEMMs contend on it is open (§4 Q2).

**The native tree's round structure** is what turns this into a cost per decision (`native_tree.py:782-900`,
`:617-666`, `:547-575`):
- A descent walks down until it creates ONE new node, then waits. Each round issues one `value_fn` call over every new
  node of every live tree, then one `prior_fn` call over every node that needs priors (both seats' views, so up to two
  rows a node).
- A round carries at most `batch` descents per tree. `batch` defaults to 1 (`native_tree.py:305`).
- The root grid is one extra value call per tree, not batched across trees or worlds (`:684`, `:814-818`).
- Rounds per tree ≈ 1 + (sims − grid leaves) / batch. At 256 sims on one world the grid is ~51 leaves, so about 200
  rounds at batch 1, about 50 at batch 4, and about 26 at batch 8 [D].

The branch's commit `3443923` reports "~8.6 rows a forward" for a lone one-world tree in the bench's forced dry run.
That matches batch 8, where 228 leaves over ~27 value calls gives ~8.4. The brief's "~56 sequential calls (28 critic +
28 prior)" at 256 sims is the same configuration. It is not in any committed file [U].

**Every Step C input was measured at batch 8.** The training arms `tr_256`, `tr_1024` and `fw_256_*` all derive from
`br_true`, which sets `batch=8` (`deep-search-step-a:scripts/native_tree_gates.py:207-208`, `:229-245`). Step C's stated
dose omits `batch` (`docs/proposals/STEP_C_PREREG_DRAFT_2026-09-26.md` §2), and the TreeOp passes its `tree` block to
the tree's defaults (`tree_top.py:93`). A Step C config that omits `batch` runs batch 1: a different search from the one
measured, at about 8× the rounds. This is the typed-dial landmine's shape (`docs/landmines.md:55-85`): a dial silently
at its default. §2 C1 carries the fix.

**Calls and rows per searched decision at today's dials, derived from the code:**

| operator | sequential calls a decision | rows a decision | where the time goes |
|---|---|---|---|
| T-op, one-ply | ~2.4 (critic, batch-1 foe prior, a share of the eligibility call) | ~51 critic + 1 actor | the critic's per-row term at 51 rows, and contention |
| one-ply L-op, 8 worlds | 51 member forwards | ~1,080 critic rows (3 members × 360) + 27 actor rows | per-row term (≈13 ms of the idle 25.8 ms) [D] |
| TreeOp at 256 sims, batch 8, alone | ~54 (27 value + 27 prior) | ~228 value + up to ~456 prior | the fixed term (~54 × 0.2 ms ≈ 11 ms), then the rows (~6 ms) [D] |
| TreeOp at 256 sims, batch 1, alone | ~400 | the same rows | the fixed term, ~80 ms [D] |
| tree L-op at 1,800 sims, 8 worlds, batch 4 | ~56 rounds × 6 member forwards + 8 grids × 3 | ~1,617 × 3 value + ~3,000 × 3 prior | rows [D] |

**What the brief said that the repo does not carry.**

| brief | repo |
|---|---|
| deep tree time split ~86% network / ~10% Python / ~3% Rust | in no committed file [U]. The instrument exists: the bench's `split` and the `tree/ms_value`, `tree/ms_prior` counters (`native_tree_gates.py:1035-1054`). Gate (ii) has not run. |
| "a committee forward costs about the same from 8 to 64 rows" | a code comment and commit messages (`native_tree_gates.py:195`, `a0f6dd9`, `3443923`), written from E-core runs. The same commit measured batch 1 → 4 (8 → 32 rows a call, 4× fewer calls) as 2.46× faster, not 4×. The actor table above reads 2.4× from 8 to 64 rows. |
| ~620-850 env steps/s per lane | in no committed file [U]. The monitor's anchors are an estimate of 650 and smoke rates of ~830 three-wide and ~1,000 two-wide (`scripts/r7_fleet_monitor.sh:5-7`). Launch-to-ETA implies ~570-590 steps/s over 100M (SESSION_LOGS 2026-09-25 11:02Z) [D]. |
| 5 lanes, 8 environments a lane, a two-core collector | correct: 3 searched + 2 control lanes (B0 failed six-wide), `num_envs 8`, `collector.k 8`, `collector.process true` (`configs/r7_fleet_searched_f1.yaml:228-247`) |
| lazy priors skip ~62% of prior rows, off by default | correct (`edc274f`; `native_tree.py:307`, `:638`) |

### 1.3 The training loop the search sits in

- **Lanes.** Each lane is a learner process plus a child collector process on a second core. Weights ship once per
  update and the child runs at most one rollout ahead (`main:rl/envs/engine_collector_proc.py:1-38`). The fleet is 3
  searched + 2 control lanes on the 10 P-cores (`readouts/R7_B0_BENCH.md`).
- **The search is on the collector's critical path.** `EngineCollector.poll` runs one batched policy forward over the
  learner rows, then `searcher.decide`, then `env.step` (`main:rl/envs/engine_collector.py:319-336`). Every engine step
  of the lane's 8 battles waits for every searched decision of that poll.
- **Targets.** Searched rows carry `search_pi` and `search_v` (`top.py:190-203`). The learner adds β·KL(π′ ‖ π_θ) on
  searched rows and a v′ auxiliary head on the critic's context, with a GAE blend dial at 0
  (`main:rl/agents/ppo.py:368-372`, `:885-899`, `:1923-1974`).
- **Throughput.** Greedy engine collection runs 1,282 steps/s a lane six-wide at k 8 (`docs/engine_port/SPEEDUP.md`).
  R7's plan priced the T-op at ~1.8 ms against ~0.15 ms greedy and put a 40%-searched lane at 1.75T of a greedy lane's
  wall (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:719-733`).
- **What R7's counters say about searching inside PPO.** On searched lane f1, PPO clips 51.2% of searched rows against
  15.9% on the same selection record-only, and KL(π′ ‖ prior) reads 0.330
  (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:157-171`, from gitignored wandb histories). Step C therefore uses
  `play: false` (`STEP_C_PREREG_DRAFT_2026-09-26.md` §0 D2).
- **Step C's budget.** +100M a lane in ≤ 4 days is ≥ 289 steps/s a lane (`STEP_C_PREREG_DRAFT_2026-09-26.md:18-28`), so
  the child may spend at most ~3.46 ms per learner step. R7's lanes run ~1.7 ms a step all-in, of which the T-op is
  ~0.8 ms at 40% searched [D; whether R7's child or learner binds is §4 Q0]. That leaves ~2.6 ms a step for the tree.
  At the draft's floor (`frac` 0.25 of the ~54% eligible, ~13.5% of decisions, ~1 searched decision per poll of 8 rows)
  a searched decision may cost ~19 ms. At R7's `frac` 0.75 (~40% of decisions, ~3 per poll) it may cost ~6.4 ms [D].

**Step C's cost per searched decision, derived.** Two-term model, idle: critic 0.2 ms + 12 µs a row, actor 0.2 ms +
6.5 µs a row, 256 sims, ~27 rounds at batch 8 and ~206 at batch 1. The last column doubles everything for fleet-width
contention, as B0 suggests.

| per-tree batch | searched decisions sharing each round | fixed part | row part | total, idle | total at ×2 |
|---|---|---|---|---|---|
| 1 (the TreeOp default) | ~1 (floor) | ~82 ms | ~6 ms | ~88 ms | ~175 ms |
| 8 (what Step C measured) | ~1 (floor) | ~11 ms | ~6 ms | ~17 ms | ~34 ms |
| 8 | ~3 (R7's `frac`) | ~3.6 ms | ~6 ms | ~10 ms | ~19 ms |
| 8, lazy priors on | ~3 | ~3.6 ms, plus extra rounds | ~4 ms | ~8 ms | ~16 ms |
| any, deferred wide lockstep (§2 D1) | ~100 | < 1 ms | ~4-6 ms | ~5-6 ms | ~10-12 ms |

Read against the budgets: at the floor (19 ms, ~1 decision a round) batch 8 fits only on an idle box.
At R7's `frac` (6.4 ms) nothing that runs inside `poll()` fits. Deferred wide lockstep fits the floor with room, and
approaches R7's `frac` only once rows get cheaper too. Python bookkeeping is not in this table, and no measurement
separates it yet. The conclusion does not hang on the exact constants: at the batch Step C measured, the fixed per-call
term and the row term are the same size. The levers that pay first cut CALLS (lockstep width, per-tree batch, duplicate
calls); the next ones cut ROWS (lazy priors, skipped foe views, a cheaper leaf).

### 1.4 The inference budget and the evaluation budget

- **The ladder clock.** A 150 s bank refills 10 s a turn in 5-s ticks, so ~10 s a turn is sustained and under ~15 s a
  turn is bank-neutral (Showdown's `room-battle.ts`, vendored and gitignored, as verified in
  `docs/prior_work/README.md`, "Foul Play ON THE LADDER"; SESSION_LOGS 2026-09-25). The ladder object today plays greedy
  at 5.40 ms a decision (RESULTS §20). Foul Play's author spends ~7 s a decision on the ladder
  (`docs/prior_work/README.md`).
- **Evaluation arms are the box's real search budget.** A 3,200-battle FP@N arm is about 93k decisions. At G2's ~50 ms a
  decision that is ~1.3 h of seat time; the tree L-op at ~1.6 s is ~41 h; the rollout L-op at the knee is ~1,800
  P-core-hours [D from §1.1]. Fourteen arms ran 8-wide in 3.3 h, and FP iterations per ms fall to 0.81× at 8 arms
  (`readouts/FP_PARALLEL_ROI_READOUT.md`). A cheaper searched seat buys reads long before it buys ladder strength.
- **The box.** M4 Pro, 10 P + 4 E cores, 24 GB (`readouts/R7_B0_BENCH.md:54`;
  `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:711-715`). Background QoS lands work on the E-cores
  at ~6.8× a decision (`docs/landmines.md:687-742`). `torch_threads 1` is the fleet setting; 6 threads read 0.85× of 1
  on 256-row minibatches (`docs/landmines.md:334-386`). MPS measured 1.15× on the learner and ~2.5% end to end (same).
  Torch is pinned at 2.13.0 (`pyproject.toml:15`).

### 1.5 What the branch has built, gated and left pending

- **Built and pinned by tests:** the native tree (`3910250`); the depth-1 reduction bitwise to `native.solve` on 500/500
  G0 roots (gate i-a, `3bd7d4d`); the tree L-op and FP seat kind (`07a19a4`); sequential halving (`0d4de52`); the fusion
  counter at depth (`a10792a`); batch-4 descents in the oracle arms (`a0f6dd9`); the P-core bench (`2128ae4`, dry run
  only); `search_many` (`3443923`); the TreeOp wired into `rl/train.py` and the child collector (`e3e1644`); lazy
  priors, off (`edc274f`); the NaN-safe fallback (`b0137ab`); the bitwise regression diff (`0d6de00`); the tier 1, tier
  1b, stepc and stepc2 arm sets (`8c0726f` → `f60e58d`).
- **Read, on the E-cores:** gate i-c, tier 1, tier 1b and stepc (SESSION_LOGS 2026-09-26).
- **Pending:** the stepc2 one-ply reference (`f60e58d`); gate (ii), the quiet-box P-core bench, which every cost number
  here that is not from B0 or an E-core run waits on; gate (i-d); Step B tiers 2-3; Step C's width bench, label-quality
  read, B = 2 read and smokes.
- **Not built anywhere:** the Rust additions DEEP_SEARCH_PATH names (`SearchNode.outcome`, `expand_nodes`,
  `LeafBatch.from_nodes`, a Rust tree); the shared-inference process; any forward-cost work; any search off the
  collector's critical path; TreeStrap; the evaluator head; time management for the ladder.
- **The branch is 15 commits behind main.** Main carries the Step C draft and the corrected `play: false` rationale.
  This document cites main for docs and the branch for the tree.

### 1.6 Two facts that set everything below

1. **The unit of cost is a network CALL plus a per-row term, never the engine.** Batching independent work into one call
   is nearly free at ≤ 8 rows and cheap to ~64. Removing rows pays once calls are amortised.
2. **The evaluator binds, not depth.** Tier 1 read flat from 1,800 to 28,800 simulations at the decision level. Tier
   1b's training setting tied the one-ply T-op at 256, 1,024 and 1,800. Rollout leaves beat critic leaves at one ply
   (+0.0027 ± 0.0013, z 2.02 at R 128, still rising at R 512). The deep soft_br TARGET keeps +0.0019 ± 0.0010 (z 1.91)
   over one ply at its learnable fixed point (SESSION_LOGS 2026-09-25 21:45Z, 2026-09-26 03:45Z, 09:45Z, 10:30Z;
   `STEP_C_PREREG_DRAFT_2026-09-26.md` §1). These are decision-level reads under THIS critic, not battle A/Bs. They move
   the budget toward the evaluator; they do not retire depth, which reopens whenever the evaluator changes (CLAUDE.md
   rule 6; `docs/landmines.md:743-780`).

## 2. The catalogue

Each entry gives: **What** it is · **Sources** with status tags · **Status here** (BUILT with file:line and default,
PLANNED with doc and section, or NEW) · **Gain here** and why · **Cost** to build · **Risks** and collisions with
CLAUDE.md or `docs/landmines.md` · the **Counter** that would measure it. Gains are derived from §1.2's two-term model
unless a measurement is cited, and derived numbers carry [D].

Two collisions apply to every speed lever that touches code the fleet imports, so they are stated once here:
- **A running block imports the working tree.** The fleet's env installs this repo editable from main, so an edit to
  `rl/search/top.py`, `rl/envs/engine_collector.py` or `rl/networks/` changes what R7's lanes run at their next resume
  (CLAUDE.md "A RUNNING BLOCK IMPORTS THE WORKING TREE"; `docs/landmines.md:899-951`). Land such a lever after R7's
  lanes finish, or behind a default-off dial whose default path is byte-identical.
- **Batch size changes the numbers.** "A GEMM may pick a different kernel for a different batch size"
  (`rl/networks/entity_deepsets.py:661-664`; `rl/agents/ppo.py:1266-1270`). Any lever that changes how rows are grouped
  into calls moves the bitwise goldens and gates. Only the trace (A1), the dead-branch gate (A3) and reusing already
  computed logits (A2 i) are bitwise.

### 2(a) Network-evaluation cost

**A1. Land the traced forward on every search path.**
- **What.** `torch.jit.trace` the actor and critic modules the search calls: the T-op's critic and foe prior, the
  TreeOp's two callables, each committee member in the L-ops. Re-trace after every weight load.
- **Sources.** [R] measured on this box: bit-identical at every batch, 1.60× at 1 row, 1.24× at 8, 1.09× at 64
  (`docs/engine_port/NOTES.md:2169-2204`). [V] TorchScript is deprecated in favour of `torch.export` in torch 2.13
  (https://github.com/pytorch/pytorch/blob/v2.13.0/docs/source/notes/cpu_threading_torchscript_inference.md, L6). [V,
  MEASURED on a Raspberry Pi] `torch.jit.script` took a quantized MobileNetV2 from ~20 to ~30 fps by cutting Python
  overhead (https://github.com/pytorch/tutorials/blob/65e2e1a/intermediate_source/realtime_rpi.rst, L213).
- **Status here.** Measured on the actor's act path, NOT LANDED. PLANNED as `docs/CLEANUP.md:206-216` (E3), which wants
  "a guard (periodic eager-vs-traced assertion) or a maintainer ruling". Never measured on the critic or the committee.
- **Gain here.** 1.6× on the batch-1 calls (the T-op's foe prior, the L-op's 27 committee prior forwards a decision) and
  ~1.1-1.25× on 8-64-row calls. About 1.15-1.2× on a tree decision at batch 8 and on the one-ply L-op [D]. It is
  bit-identical, so no read needs re-anchoring.
- **Cost.** An afternoon plus the guard.
- **Risks.** The trace freezes control flow at trace time, so trace each configuration the search uses (`both_views`,
  antisymmetric critic). Use `trace`, not `trace` + `freeze`: `freeze` inlines weights as constants and the learner's
  weights change every update (`NOTES.md:2191-2197`).
- **Counter.** `search/ms`, `tree/ms_value`, `tree/ms_prior` per call; a count of guard checks and failures.

**A2. Remove the duplicate and avoidable forwards.**
- **What.** Five call sites found by reading, none measured:
  1. The T-op re-runs the actor over the rows the collector just scored (`rl/search/top.py:147` after
     `rl/envs/engine_collector.py:321`; same in `tree_top.py:154`). Return the logits from the collector's forward.
  2. The T-op scores each searched row's foe prior at batch 1 (`top.py:160-163`). One call per poll instead; the TreeOp
     already does this (`tree_top.py:166-174`).
  3. The T-op solves a poll's searched rows one by one, one critic call each (`top.py:154-186`). One call per poll.
  4. The native tree's root grid makes one value call per tree (`native_tree.py:684`, `:814-818`) and expands the same
     cells twice, once through `expand` and once through `leaves` (`:678-679`). Batch the grids of a `search_many` call.
  5. A node whose seat has exactly one legal action still gets a prior row (`_forward`, `native_tree.py:643-654`). Skip
     the row and install a one-hot prior.
- **Sources.** [R] the code lines above; the repo inventory's read of the stack.
- **Status here.** NEW. Item 2 is BUILT in the TreeOp only.
- **Gain here.** On the T-op, a poll with ~3 searched rows falls from ~7 calls to 2. That is ~1.4× on the searched share
  when idle [D]. On the TreeOp, items 1, 4 and 5 save one call a poll plus a few grid calls and rows. Item 5's share
  depends on how often a Pass or forced node gets primed, which `tree/prior_rows` can split once counted.
- **Cost.** Hours.
- **Risks.** Items 2-4 regroup rows and are not bitwise. Item 1 is bitwise only if the exact logits are reused. Both
  collisions at the top of §2 apply: R7's lanes import this code.
- **Counter.** A new `search/forwards` per poll; `search/ms`.

**A3. Gate the critic's dead `move_net` branch.**
- **What.** `_context` always runs `move_net` over our four moves (`rl/networks/entity_deepsets.py:597-601`). The critic
  returns `head(ctx)` and never reads them (`:670-676`). Every critic leaf of every search pays for it.
- **Sources.** [R] IDEAS 2.9 priced it at 1.46% of the update, bit-identical (`docs/IDEAS_POST_100M.md:387-396`).
- **Status here.** PLANNED (IDEAS 2.9, "not done").
- **Gain here.** A few percent of each critic call: four dispatched ops at ~4.6 µs each plus a small per-row GEMM [D].
- **Cost.** An hour and a bitwise test.
- **Risks.** None to numerics if the critic's output stays bitwise, which the test pins.
- **Counter.** `tree/ms_value` per row.

**A4. Fuse the committee into one batched forward.**
- **What.** Stack the K members' weights and run one `bmm` per layer instead of K forwards
  (`torch.func.stack_module_state` + `vmap`, or a hand-written batched trunk). Today every committee call runs its three
  members in sequence (`rl/search/ensemble.py:69-83`; `rl/search/lop.py:119-123`; `tree_lop.py:80-98`).
- **Sources.** [V code; speedup CLAIMED, no number printed] the PyTorch model-ensembling tutorial
  (https://github.com/pytorch/tutorials/blob/65e2e1a/intermediate_source/ensembling.py, L93-L142, L168).
- **Status here.** PLANNED: DEEP_SEARCH_PATH §4 names "a fused committee forward", last of its levers
  (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:203-206`). Not built.
- **Gain here.** Inference only; the training searches use one critic. The one-ply L-op drops from 51 member forwards to
  17 calls, and its idle 25.8 ms to ~20 ms. Most of what remains is ~1,080 critic rows a decision, ~13 ms, which fusion
  does not touch [D]. The tree L-op drops from six calls a round to two.
- **Cost.** Half a day plus a tolerance test.
- **Risks.** `bmm` sums in a different order from three `mm`s, so the committee's argmax can flip on near-ties.
  Re-anchor every read across the change.
- **Counter.** A new `lop/forwards`; `lop/ms_mean`.

**A5. Batch the one-ply L-op's worlds.**
- **What.** Concatenate the 8 worlds' leaf batches into one committee value call and the 8 foe views into one prior
  call. The L-op runs its worlds one after another (`rl/search/lop.py:151-170`), and `native.solve` loops one forward
  per world even when handed several (`native.py:190-211`).
- **Sources.** [V code] mctx runs a batch of independent searches in lockstep (https://github.com/google-deepmind/mctx,
  README L8-L11). [V code] EfficientZero advances a batch of roots in lockstep with one `recurrent_inference` a step
  (https://github.com/YeWR/EfficientZero/blob/468bb03/core/mcts.py, L13-L105). [R] the native tree already does it
  (`search_many`, `native_tree.py:782-900`).
- **Status here.** NEW for `native.solve` and the L-op; BUILT in the tree.
- **Gain here.** With A4, ~3 calls a decision and ~17-18 ms idle instead of 25.8 ms, about 1.45× [D]. What remains is
  rows, plus the Python determinization and `build_root` per world, whose share is unmeasured. Cutting rows needs A7 or
  A13.
- **Cost.** A day. Keep the per-world π′ identity check (`lop.py:174-175`) on the per-world path.
- **Risks.** Not bitwise, so it lands behind a dial with a tolerance test.
- **Counter.** `lop/forwards`, `lop/ms_mean`, and a new `lop/ms_build` for the determinization share.

**A6. Lazy priors.**
- **What.** Prime a node's prior only when a simulation selects at it. About 38% of primed nodes are ever selected at
  600-7,200 sims, so ~62% of prior rows, ~40% of all rows, are never needed (commit `edc274f`).
- **Sources.** [R] the branch. [V code] KataGo and lc0 get policy and value from one call per node, so the trade does
  not arise there; mctx's `recurrent_fn` returns both.
- **Status here.** BUILT, OFF (`native_tree.py:307`, `:637-641`). Identical to eager at batch 1 on one world, pinned on
  three modes (`deep-search-step-a:tests/test_native_tree.py:202-209`).
- **Gain here.** It removes ~40% of rows and adds rounds: a descent that reaches a selected, unprimed node waits one
  round. Inside `poll()` at a lockstep width of 1-3 the extra rounds can cancel the saving. Under deferred wide lockstep
  (D1) rounds are cheap and it is worth ~1.3-1.5× [D]. The bench's configs never set it
  (`native_tree_gates.py:900-910`); add lazy twins.
- **Cost.** Done; a bench config and a quality read.
- **Risks.** At batch > 1 the lazy search is not the eager one, so Step C's measured object changes. Read its decision
  quality on G0 at 256 sims and batch 8 before turning it on.
- **Counter.** `tree/prior_rows`, `tree/forwards_p`, `tree/dup_waits`.

**A7. A value cache keyed on the observation bytes, and common random numbers across belief worlds.**
- **What.** A per-decision dict from the leaf's observation digest to its value, checked before `value_fn`. The critic
  reads only the acting seat's observation, and the tree already hashes it for the fusion counter
  (`native_tree.py:415-416`). Its twin, A7b: key chance on (decision, column, sample) and not on the world. Today each
  world gets its own chance seed (`lop.py:160`; `native.seed_base` mixes the world, `native.py:60-69`), so two worlds
  whose hidden information does not touch a line still roll differently and render different observations.
- **Sources.** [V doc] KataGo caches `2**nnCacheSizePowerOfTwo` evaluations at ~1.5 KB each, keyed on a hash of what the
  net sees (https://github.com/lightvector/KataGo/blob/7c42e21/cpp/configs/gtp_example.cfg, L368-L378). [V wiki,
  MEASURED, chess on GPU] lc0's 1M-node trees hold 10-69% unique positions, which sets its cache hit rate
  (https://github.com/LeelaChessZero/lc0/wiki/Transposition-tests). [V code] alpha-zero-general keys every node dict on
  the board string (https://github.com/suragnair/alpha-zero-general/blob/f1a78e0/MCTS.py, L20-L26). [V code] OpenSpiel's
  AlphaZero evaluator keys an LRU cache on the observation and mask bytes, and one forward serves both the value and the
  prior request (https://github.com/google-deepmind/open_spiel, `open_spiel/python/algorithms/alpha_zero/evaluator.py`
  at `4840189`). The same evaluator refuses simultaneous-move games, so its code is not reusable here.
- **Status here.** NEW. No evaluation cache exists anywhere; the tree's merge is per edge only (repo inventory B.2).
- **Gain here.** It removes rows, not calls, unless a whole round hits. The hit rate is unknown and cheap to measure
  offline: distinct observation digests per decision over the oracle trees. Within one world transpositions are rare
  (continuous HP, simultaneous moves). Across worlds they can be common near the root, and A7b is what makes them hit.
- **Cost.** An hour for the cache; a dial and a read for A7b.
- **Risks.** A7b trades cache hits for chance variance: the PIMC mean then averages S chance draws, not 8·S. A cached
  value was computed in a different batch, so it is equal to the uncached one only up to batch-size float noise.
- **Counter.** `tree/cache_hits`, `tree/cache_rows_saved`; offline, the distinct-digest ratio per decision.

**A8. One trunk for policy and value.**
- **What.** A shared actor-critic trunk with two heads: one call a round instead of two, and the duplicated trunk stage
  computed once. That stage is 66.7% of the [384, 384] critic's MACs a row (`docs/IDEAS_POST_100M.md:1553-1565`).
- **Sources.** [V paper] AlphaGo Zero's single dual-headed network; MuZero, KataGo and lc0 all use one network for both
  (lit dossier part 1 §1-§3).
- **Status here.** PLANNED as its own lap (IDEAS §5 `:1553-1565`; JOURNEY 14 lists "a shared actor-critic trunk" among
  the items that get their own lap, `JOURNEY.md:203-204`).
- **Gain here.** Halves the calls a round and removes about a third of a W-critic row's MACs where both heads are
  needed, ~1.3-1.6× on a tree decision [D].
- **Cost.** An architecture lap: new checkpoints, and the actor's `ACTOR_PARAM_CEILING` assert
  (`entity_deepsets.py:55-61`).
- **Risks.** A critic-side change is not actor-neutral in PPO (CLAUDE.md's stacking convention; D18's falsifier).
- **Counter.** `tree/forwards_v + tree/forwards_p`; the critic's Spearman on G0.

**A9. Compile or export the forward.**
- **What.** `torch.compile` with the CPU inductor backend, `torch.export` + AOTInductor, ONNX Runtime, a Core ML model
  on the CPU, or Apple's BNNS Graph.
- **Sources.**
  - [R] `torch.compile` read 0.82× on the UPDATE (`docs/engine_port/NOTES.md:2171`; SESSION_LOGS:11246). It was never
    tried on a search forward.
  - [V code] `mode="reduce-overhead"` only reduces overhead for CUDA graphs
    (https://github.com/pytorch/pytorch/blob/v2.13.0/torch/__init__.py, L2670-L2676). Inductor on macOS needs an OpenMP
    runtime (`torch/_inductor/cpp_builder.py`, L1478-L1521). Its `cpp_wrapper` and `freezing` options target per-call
    overhead (`torch/_inductor/config.py`, L196, L1561). No published CPU small-MLP speedup was found [U].
  - [V doc] AOTInductor packages a C++ runner loadable from Python or C++
    (https://github.com/pytorch/tutorials/blob/65e2e1a/recipes_source/torch_export_aoti_python.py).
  - [V code] ONNX Runtime's CPU kernels have fp16 compiled out on Apple ARM64
    (https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/core/mlas/inc/mlas.h, L106-L119). No evidence that
    its fp32 GEMM uses Apple's matrix unit, which PyTorch's Accelerate path does [U].
  - [V code] lc0's CPU backend on macOS also calls Accelerate's BLAS (lc0 `meson_options.txt` at `1227b4c`), so the
    chess engines' CPU path offers no kernel that PyTorch lacks here.
  - [V, Apple's CLAIM] BNNS Graph runs single-threaded with no allocation during execute and is "on average, at least
    2x faster than previous BNNS primitives" (https://developer.apple.com/videos/play/wwdc2024/10211/).
- **Status here.** NEW for search.
- **Gain here.** Unknown. The trace (A1) already removes Python dispatch; what is left is kernel launch cost and
  small-GEMM efficiency. ONNX Runtime may lose the matrix unit that Accelerate gives PyTorch. AOTInductor and BNNS Graph
  matter most for a Rust tree with no Python in the loop (F6).
- **Cost.** A day per backend for a microbench (§4 Q3).
- **Risks.** None is bitwise with today's forward. Each adds a dependency to pin exactly (`pyproject.toml`). Each
  process pays a warm-up.
- **Counter.** µs a call at 1, 8, 64 and 256 rows against the traced eager forward.

**A10. A distilled leaf network, and an incremental evaluator.**
- **What.** A small critic trained only for leaf use, to reproduce the committee's value or rollout labels on
  search-visited states. Its extreme form is NNUE's: a wide sparse first layer updated incrementally between parent and
  child, and an int8 tail.
- **Sources.**
  - [R] DEEP_SEARCH_PATH §4 lists "a distilled leaf net ~20-40k per P-core" first among the speed levers, as an estimate
    (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:203-206`).
  - [V paper, MEASURED on Atari] a student 4× smaller than DQN beat it, and one 15× smaller matched it (Rusu et al.
    2016, https://arxiv.org/abs/1511.06295 §4.3).
  - [V paper, MEASURED on Hex] tree-policy targets beat chosen-action targets by +50 ± 13 Elo, and DAgger added +120
    (Anthony et al. 2017, https://arxiv.org/abs/1705.08439 p.6).
  - [V doc, a CLAIMED target] NNUE aims at "million(s) of evaluations per second per thread" on CPU without batching
    (https://github.com/official-stockfish/nnue-pytorch/blob/aa2fff2/docs/nnue.md, L167). Stockfish's Apple Silicon
    build uses NEON dot-product instructions (Stockfish `src/Makefile`, L397-L403).
- **Status here.** PLANNED (DEEP_SEARCH_PATH §4). The incremental form is NEW.
- **Gain here.** Rows get cheap, and a NEON int8 leaf runs per core instead of on the shared matrix unit (§1.2). But the
  evaluator binds (§1.6): a leaf that ranks worse loses more than it saves. The committee critic's Spearman on G0's
  cells is +0.476 (`readouts/R7_G0_READOUT.md`), and a distilled leaf has to match it before it is used.
- **Cost.** A supervised job, days; CLAUDE.md allows a rented GPU for it. The incremental form is a week or more, and an
  input change is two encoder ports plus a parity gate (`docs/landmines.md:1103-1134`).
- **Risks.** Evaluator quality. JOURNEY 16's purity line: train on our own positions and labels only.
- **Counter.** Held-out Spearman against the committee on G0 by turn bucket; µs a row.

**A11. Reduced precision.**
- **What.** int8 dynamic quantization of the Linear layers, or fp16/bf16.
- **Sources.** [V paper, MEASURED on base M4] the matrix unit runs int8 at 2× fp32 and fp16/bf16 at the same rate as
  fp32 (Remke & Breuer, https://arxiv.org/abs/2409.18779 Table I). [V code] the torch 2.13 macOS wheel is built with
  `USE_QNNPACK=OFF` (https://github.com/pytorch/pytorch/blob/v2.13.0/.ci/wheel/build_wheel.sh, L182), and
  `torch.ao.quantization` is deprecated for torchao
  (https://github.com/pytorch/pytorch/blob/v2.13.0/docs/source/quantization.md, L10-L20). [V paper, MEASURED] int8
  and fp16 policies lost 2-5% of episode reward on Atari and Gym (QuaRL, https://arxiv.org/abs/1910.01055 §3).
- **Status here.** NEW.
- **Gain here.** fp16 and bf16 buy nothing on this hardware. int8 could halve the GEMM part if some kernel reaches the
  matrix unit's int8 path, which is unverified for PyTorch on this wheel. The critic ranks siblings whose values differ
  by ~0.01-0.05 (RESULTS §33), the worst place for quantization noise. Low.
- **Cost.** A day to find out whether any int8 path exists here.
- **Risks.** Ranking error; a new dependency.
- **Counter.** Argmax agreement and override rate on G0 roots; µs a call.

**A12. Skip evaluations the value cannot use.**
- **Status here.** BUILT and on. Pass nodes are descended through and never critic-valued (`pass_leaf="through"`,
  `native_tree.py:295`). Terminals are overwritten with the outcome. `both_views=False` stops the one-view critic's
  searches rendering the foe's view (`native.py:103`, `:126-133`; `top.py:82-86`). A capped simulation returns the
  node's value (`native_tree.py:555-567`). A2's item 5 is the one gap left.

**A13. Skip confident decisions in the inference operators.**
- **What.** Give the L-ops the T-op's rule: search only when π top-1 < 0.97. Today both L-ops search every decision with
  more than one legal action (`lop.py:138-140`; `tree_lop.py:112-114`). G2 searched 101,241 of 105,794 decisions
  (`readouts/R7_G2_READOUT.md`).
- **Sources.** [R] the T-op's rule (`top.py:61`, `:148`). [V code] KataGo's self-play reduces visits when the game is
  decided (`reduceVisits`, `selfplay8mainb18.cfg`) and lc0 stops a search whose best move can no longer change (lc0
  `src/search/classic/params.cc`, smart pruning); lit dossier part 1 §10-§11.
- **Status here.** NEW for the L-ops; BUILT in the T-op. DEEP_SEARCH_PATH's ladder operator names "a cheap check on
  prior top-1 >= 0.97" (`:135-137`), unbuilt.
- **Gain here.** π_θ top-1 ≥ 0.97 on 46% of G0's positions (`readouts/R7_G0_READOUT.md:46`), so ~40-46% of a searched
  seat's time on reads [D]. The quality cost can be read offline on G0 before any arm: how often search would have
  overridden on those positions, and for how much.
- **Cost.** An hour, plus the offline read.
- **Risks.** The override rate moves, so every comparison is matched on it (CLAUDE.md "MATCH ON THE OVERRIDE RATE";
  `docs/landmines.md:840-872`).
- **Counter.** A new `lop/skipped_confident`; the override rate beside every win rate.

**A14. Cheaper rollout leaves: the Stage 1 cost stack.**
- **What.** The rollout L-op at the knee costs ~26,500 rollouts a decision and ~1,800 P-core-hours an arm, "far past the
  approved plan's 30-200 core-hours for its read" (SESSION_LOGS:14183-14209). The levers, cheapest first:
  1. Sequential halving over rows, spending rollouts only on contenders. Offline it matched the full 512-world choice on
     100/100 roots at 0.59× the rollouts, "~2x, not 10x" (SESSION_LOGS:14252-14253; `scripts/r7_stage0c_sh_offline.py`).
  2. The confident skip (A13), which the approved plan names beside it.
  3. The fused committee (A4) on the rollout policy, which runs three member forwards every lockstep step. A step
     scores all live rollouts of the grouped worlds in one call per seat (`scripts/r7_stage0c_rollout_curve.py:599-647`),
     so calls are wide early and narrow in the tail, where fusion's saving lives.
  4. A distilled rollout policy (A10's policy half): one small forward a step instead of three W actors.
  5. Truncated rollouts with a critic bootstrap after k turns (TD(k) or λ-mixed leaves). DEEP_SEARCH_PATH Step A lists
     "rollout or lambda-mixed leaves" as a dial.
  6. A control variate: estimate Q = V_critic + E[R − V_critic] per cell. The variance falls by the factor 1 − ρ², where
     ρ is the rollout-critic correlation, at zero extra rollouts [D].
  7. Antithetic or stratified chance seeds across a cell's rollouts [D].
- **Sources.** [R] Stage 0c and its offline SH read. [V2 via `docs/prior_work/WANG_SEARCH_DEEP_READ.md`] Wang's gen-4
  MCTS used critic leaves with fresh determinization per rollout at 1,000-2,000 rollouts a decision.
- **Status here.** Item 1 measured offline, operator PLANNED as Stage 1's (SESSION_LOGS:14205-14207). Item 2 PLANNED
  (same). Item 5 PLANNED as a dial (DEEP_SEARCH_PATH Step A), unbuilt. Items 3, 4, 6 and 7 NEW.
- **Gain here.** Items 1 and 2 compound to 0.59 × 0.54 ≈ 0.32, or ~580 P-core-hours an arm, still above the approved
  30-200 [D]. Item 3's size depends on the tail's share of lockstep steps, which the stored step counts give. Item 4 is
  the next large factor, since the policy's rows dominate a rollout step; it changes the rollout policy, so it is an
  estimator change. Item 6 is free and its size depends on ρ, which Stage 0c's stored rows can give offline. Item 5's quality cost falls where the
  critic is weakest: the rollouts' edge sits in the late game (turn 23+: d +0.0081 ± 0.0051), and a truncated rollout in
  the opening falls back to the critic's worst region (r² 0.287 at turns 2-8, RESULTS §27.1). Read it offline before
  counting its saving.
- **Cost.** Hours each for 2, 6 and 7; a day for 3; item 4 is a supervised job.
- **Risks.** Every item except 6 and 7 changes the estimator, so re-read the decision-level curve at the matched
  override before an FP arm.
- **Counter.** Rollouts a decision, steps a rollout, and the Stage 0c gain at the matched rate.

**A15. Average the committee's weights into one network.**
- **What.** IDEAS 2.12 proposes weight-space averaging of "a lane's last rungs": "Zero training cost, zero inference
  cost — unlike 4.8, which pays one forward per member" (`docs/IDEAS_POST_100M.md:514`).
- **Status here.** PLANNED as an idea, "never tried".
- **Gain here.** It would cut every committee leaf's rows 3×. But IDEAS 2.12 averages one lane's consecutive rungs,
  while the committee is three seeds' 200M finals (`runs/showdown_monster200m_w_s104`, `_s112`, `_s120`;
  `configs/eval/exit_gate_r5.yaml:22-24`). Networks trained from different seeds need their neurons aligned before
  their weights can be averaged ([U, not read here] Ainsworth et al., "Git Re-Basin", https://arxiv.org/abs/2209.04836).
  So this replaces the committee only if one averaged lane matches the committee's measured gain (+0.0349 vs SH,
  IDEAS 4.8).
- **Counter.** The locked vs-SH protocol against the committee; µs a leaf.

### 2(b) Tree-algorithm and budget efficiency

**B1. The root's spending rule: sequential halving instead of PUCT.**
- **What.** The 2-battle smoke moved off greedy on 0 of 57 decisions, and its session log reads the root statistics as
  the cause: "a PUCT root compares the row it searched most -- the prior's -- at depth against rows left at one ply, and
  deeper search raises a row's Q" (SESSION_LOGS:14167-14172). Sequential halving gives every surviving row equal root
  visits per phase and halves on g + logits + σ(q̂) pooled over worlds.
- **Sources.** [V code] mctx's sequential-halving, policy and Q-transform modules at commit 88f9205
  (https://github.com/google-deepmind/mctx, `mctx/_src/`). The Gumbel paper itself was unreachable here, so its
  per-budget results are [U] (https://openreview.net/forum?id=bERaNdoegnO). [V paper, MEASURED on 4× GTX 1080 Ti]
  MiniZero trained Gumbel AlphaZero at 2 and 16 simulations against PUCT at 200 on 8×8 Othello at equal wall-clock: n =
  2 matched n = 200, and n = 16 was slightly worse (Wu et al., https://arxiv.org/abs/2310.11305 §IV-C). [V paper]
  LightZero: Gumbel MuZero does "notably better" than MuZero when simulations are limited
  (https://arxiv.org/abs/2310.08348 App. B.2.3).
- **Status here.** BUILT, `root_select` dial, default `"puct"` (`native_tree.py:287`, `:819-831`, `:980-1015`;
  `0d4de52`). MEASURED at 1,800 sims: SH − PUCT −0.0001 ± 0.0004 at the matched override (SESSION_LOGS 2026-09-26
  05:15Z).
- **Gain here.** None on decision quality at 1,800. Its value is at small budgets and as the vehicle for rollout
  leaves on contending rows (A14 item 1), where each phase is one batched call.
- **Cost.** Done.
- **Risks.** The root's guarantee holds against the foe model used to average Q, not as an equilibrium.
- **Counter.** `tree/sh_phases`, the root's top-1 visit share.

**B2. The policy target's form.**
- **What.** AlphaZero trains on visit counts. Gumbel MuZero trains on softmax(logits + σ(completed q̂)) over every
  action. This project's default is the soft best response π′ ∝ π·exp(Q̄/τ) (`native.py:214-219`;
  `native_tree.py:1047-1050`).
- **Sources.** [V code] mctx's completed-Q transform, `maxvisit_init` 50 and `value_scale` 0.1 by default. [V code]
  MiniZero's defaults use c_scale 1.0 citing the Gumbel paper (https://github.com/rlglab/minizero at `394b2e4`,
  `minizero/config/configuration.cpp`), so the scale depends on how Q is normalised. [V doc] KataGo's author on Grill et al.'s regularised-policy target: it "can sometimes
  put a large policy weight on a move with relatively few visits if its Q appears good enough"
  (https://github.com/lightvector/KataGo/blob/7c42e21/docs/GraphSearch.md, footnote 3). [V paper, MEASURED on Atari with
  4-8 V100s] Grill et al.'s regularised target helped most at 5 simulations, and MuZero caught up at ≥ 24 simulations
  for ≤ 18 actions (https://arxiv.org/abs/2007.12509 p.7). A 256-sim tree over ≤ 9 rows sits at ~28 simulations a row,
  past that crossover. [V paper, MEASURED on Hex] soft tree-policy targets beat chosen-action targets by +50 ± 13 Elo at
  equal prediction error (ExIt, https://arxiv.org/abs/1705.08439 p.6).
- **Status here.** BUILT: five root rules. MEASURED 2026-09-26: the deep soft_br target's fixed point keeps +0.0019 ±
  0.0010 (z 1.91) over one ply. Completed-Q's learnable part at one world is ~0 (+0.0002); its true-world +0.0044 was
  almost all peek. σ sits on a ridge at c_scale 0.1 (`STEP_C_PREREG_DRAFT_2026-09-26.md` §0 D2, §1;
  SESSION_LOGS:14355-14369).
- **Gain here.** Settled for Step C: soft_br at τ 0.05.
- **Risks.** Choose a target's dials on the student's fixed point, never on the true world (SESSION_LOGS:14355-14369).
- **Counter.** `search/kl_prior`, `search/pi_top1`; the fixed-point instrument (`native_tree_gates.py --arm-set stepc`).

**B3. Forced playouts and policy-target pruning.**
- **What.** KataGo forces each root child to at least √(2·P(c)·ΣN) playouts, then subtracts those forced playouts from
  the policy target unless the child earned them, and prunes children left with one playout.
- **Sources.** [V paper] Wu, arXiv:1902.10565 §3.2 p.5. Removing them cost a 1.25× training-time factor in the paper's
  ablation (Table 2, p.14; 2-day runs, V100s). [V code] `rootDesiredPerChildVisitsCoeff = 2` in KataGo's self-play
  config.
- **Status here.** NEW, and moot. The root grid evaluates every row × top-k column × chance sample before any descent
  (`native_tree.py:669-723`), the targets are Q-based, and root noise is off (B4).
- **Gain here.** None unless a visit-count target or root noise is turned on.

**B4. Root exploration noise.**
- **What.** Dirichlet noise on the root prior (AlphaZero), shaped Dirichlet noise (KataGo), or Gumbel noise on the
  logits (Gumbel MuZero).
- **Sources.** [V code] KataGo `rootDirichletNoiseTotalConcentration = 10.83`, weight 0.25, and its author's note that
  shaped noise "has *not* been validated as a measurable improvement"
  (https://github.com/lightvector/KataGo/blob/7c42e21/docs/KataGoMethods.md). [V code] mctx's docstring: evaluation "on
  perfect-information games can use gumbel_scale=0.0".
- **Status here.** BUILT as `gumbel_scale`, default 0, used only under sequential halving (`native_tree.py:303`), and as
  `root_dirichlet` in the old tree (default 0).
- **Gain here.** For training targets only, and only if the grid proves too narrow. Read `tree/argmax_moved` and the
  fixed-point value before setting it. Never at inference.

**B5. Chance handling: sampled children, exact enumeration, stratified rolls.**
- **What.** The tree samples `chance_k` = 2 reused children per edge seeded by the engine's `leaf_seed`, so rows share
  draws at every depth, widens progressively, and merges identical positions on the RNG-masked `save()` digest
  (`native_tree.py:426-441`, `:532-543`). The alternative is to enumerate chance outcomes with probabilities.
- **Sources.** [V code] poke-engine pre-enumerates every chance outcome with its probability and samples one child per
  visit; in gen 1 it uses average damage, branches on a crit only when average damage does not KO, and fixes 2-5-hit
  moves at 3 hits (lit dossier part 2 §8.3; https://github.com/pmariglia/poke-engine at `bcf1382`). [U, not on the
  arXiv mirror] Stochastic MuZero learns chance codes because it has no simulator. [R] pkmn/engine offers `-Dchance`
  and `-Dcalc` in a separate build, "relevant to search" (`docs/PKMN_ENGINE_RUST_PLAN.md:214-215`, `:1269`).
- **Status here.** Sampling with reuse and merges BUILT. Exact enumeration PLANNED in the Rust plan and unbuilt; the
  extension is built with both flags off (`engine/pkmn_gen1/build.rs:218-219`). Stratified rolls NEW.
- **Gain here.** Lower variance per leaf at the same leaf count. The one-ply matrix's noise was the D5 story
  (`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §4.2). Size unknown (§4 Q7).
- **Cost.** Multi-day Rust: a second engine artifact, since "one process cannot link both static libs"
  (`PKMN_ENGINE_RUST_PLAN.md:1269`).
- **Risks.** Gen 1 has 39 damage rolls, so full enumeration explodes; stratify the roll within each crit and hit branch.
  Reinstalling the extension mid-block changes running jobs (`docs/landmines.md:899-951`).
- **Counter.** Per-cell value variance at fixed leaves; the oracle runs already store the cell values.

**B6. Transpositions and graph search.**
- **What.** Merge identical states across edges, not only within one edge, and back up on the resulting graph.
- **Sources.** [V paper, MEASURED, CrazyAra on GPU] Monte-Carlo Graph Search: 30-70% less memory, ≈ +110 Elo in
  crazyhouse from the graph alone, ≈ +69 in chess combined (Czech et al., https://arxiv.org/abs/2012.11045 p.5, p.9).
  [V doc] KataGo's sound formulation separates edge visits from child visits
  (https://github.com/lightvector/KataGo/blob/7c42e21/docs/GraphSearch.md).
- **Status here.** NEW. Merges are per edge (`native_tree.py:426-441`); the fixture golden shows 147 merges among 582
  nodes (`deep-search-step-a:tests/test_native_tree.py:135-140`).
- **Gain here.** Probably small. Chess transposes through move order; a simultaneous stochastic game with continuous HP
  rarely reaches the same state by two joint actions. A7's value cache takes most of the network saving without changing
  the tree's shape.
- **Counter.** Count cross-edge digest collisions offline on the oracle trees before building anything.

**B7. Stop a search early when the answer cannot change.**
- **What.** lc0's smart pruning stops when the remaining playouts cannot close the gap between the best and second-best
  root moves. Its KLD-gain stopper stops when the root visit distribution stops moving per new node. Under sequential
  halving the rule is trivial: a decision is done when one row survives.
- **Sources.** [V code] lc0 `SmartPruningStopper` and `KldGainStopper`
  (https://github.com/LeelaChessZero/lc0/blob/1227b4c/src/search/classic/stoppers/stoppers.cc). [V doc] lc0 wiki: KLD
  gain "allows selfplay to spend more time when the Policy prediction was bad, and less time on obvious moves. First
  used in T50." [V paper, MEASURED] V-MCTS stops at the root when the visit distribution after k simulations is within
  0.1 (L1) of the one after k/2, with no network call. On 9×9 Go it spent 76 simulations for a 71% ± 4.7 win rate
  against GnuGo, where full MCTS spent 150 for 75% ± 3.0 (Ye et al., https://arxiv.org/abs/2210.12628 Table 1, §4.3).
- **Status here.** NEW as a stopping rule. `deadline_ms` exists as a wall bound, unused by every arm
  (`native_tree.py:309`, `:834-851`).
- **Gain here.** A direct cut in collector time for Step C and in seat time on reads. Tier 1's flat curve says the
  average decision stops improving early; a per-decision stopper spends where the root is still moving.
- **Cost.** About 20 lines and a quality read on G0.
- **Risks.** At a simultaneous root the "visit distribution" is our side's pooled visits under `br_prior`. A stopper
  changes the override rate, so match on it.
- **Counter.** Realised sims against budgeted, per decision; the oracle gain at the matched rate.

**B8. Spend the budget where the decision is close.**
- **What.** A second search phase only when the first phase's top-two margin is under a threshold, or searches gated by
  committee disagreement.
- **Sources.** [R] IDEAS 8.5: gating by committee disagreement read as a null against a coin at a matched rate (+0.0030
  at 0.14 se), while concentrating the budget beat spreading it (+0.0335 at 2.14 se, post hoc)
  (`docs/IDEAS_POST_100M.md:1730-1793`). [V code] KataGo's `reduceVisits` cuts visits once a game is decided.
- **Status here.** Dials BUILT (`top1_skip`, `frac`, `disagree=` in `rl/search/agent.py`). An adaptive two-phase budget
  is NEW.
- **Gain here.** Mostly seat and collector time; A13 is the cheap first form.
- **Counter.** The override rate beside every read.

**B9. Search only the prior's top rows (Sampled MuZero).**
- **What.** Search K rows sampled from the prior and correct PUCT for the sampling.
- **Sources.** [V paper] Sampled MuZero: K = 50 samples "closely approaching" full search in Go, one seed per experiment
  (Hubert et al., https://arxiv.org/abs/2104.06303 §6.1).
- **Status here.** NEW; the grid covers every legal row. Stage 0c measured the 3×4 cells against the full matrix for
  rollout leaves: full − 3×4 = +0.0022 ± 0.0012 (z 1.85), so the full matrix was kept (SESSION_LOGS 2026-09-26 03:45Z).
- **Gain here.** The grid is ~51 of 228 leaves at 256 sims. Skip: the measurement argues against it, and sequential
  halving already reallocates.

**B10. Choose the foe's columns by prior mass.**
- **What.** `cols_k` = 4 covers the foe's oracle-best reply on 75% of positions (`opp_best_outside_top4` 0.250,
  `readouts/R7_G0_READOUT.md`). Choose k per node to cover a fixed share of the foe's prior mass.
- **Status here.** Fixed k BUILT; adaptive NEW. `search/topk_mass` already records the covered mass.
- **Gain here.** Decision quality on the quarter of positions whose best reply is outside the top four, at a leaf cost
  the mass rule bounds. Readable offline on G0, whose oracle has every column.
- **Counter.** `search/topk_mass`, columns a node.

**B11. The estimand at a simultaneous node.**
- **What.** Best response to the foe's prior (`br_prior`), decoupled UCT (`legacy`), or regret matching at every node
  (`sm_rm`).
- **Sources.**
  - [V paper] Lisý et al.: Hannan-consistent selection converges to an approximate Nash equilibrium through the average
    strategy, while UCB selection does not converge even in a one-stage game (https://arxiv.org/abs/1310.8613; already
    in `docs/prior_work/README.md`).
  - [V paper, MEASURED] Albatross compared AlphaZero adaptations for simultaneous games: regret matching and SM-OOS were
    worst in stochastic two-player Battlesnake, and fixed-depth search with logit-equilibrium backups best overall
    (Mahlau et al., https://arxiv.org/abs/2402.03136 App. C, 5 seeds).
  - [V paper] Simultaneous AlphaZero: warm-starting per-node regret matching from learned regrets cut the local Nash gap
    from 0.251 to 0.150; cold-started RM at few iterations per node is the weak configuration (Becker & Sunberg,
    https://arxiv.org/abs/2512.12486).
  - [U, abstract only] Tak, Lanctot & Winands 2014 over nine games: "Decoupled UCT performs best despite its theoretical
    shortcomings".
- **Status here.** BUILT (three modes) and MEASURED at 1,800 sims: legacy − br −0.0041 (z −2.78), rm − br −0.0055
  (z −3.55) (SESSION_LOGS 2026-09-26 05:15Z). At the oracle level RM halves greedy's exploitability, but at the critic
  level every root rule is within noise (`readouts/R7_G0_READOUT.md`).
- **Gain here.** Keep `br_prior`. The literature agrees that cold RM at a few hundred visits per node is weak.
  Warm-started RM or a logit-equilibrium backup are the forms worth a read once the evaluator improves (E5).
- **Counter.** The root-rule read on G0 (`scripts/rollout_q_root_rules.py`).

**B12. FPU, exploration constant, variance-scaled exploration.**
- **What.** Unvisited children take the parent's value (`q_init: "parent_v"`); `c_puct` is 1.5
  (`native_tree.py:296-297`). KataGo scales cPUCT per node by the square root of the observed utility variance.
- **Sources.** [V doc] KataGo's dynamic variance-scaled cPUCT plus uncertainty-weighted playouts: "about 75 Elo stronger
  than the preceding release, and about 50 Elo stronger ... if the cPUCT for the preceding release is optimally tuned"
  (https://github.com/lightvector/KataGo/blob/7c42e21/docs/KataGoMethods.md). These are play-time settings, off in its
  self-play config (`cpp/program/setup.cpp`).
- **Status here.** BUILT dials, untuned beyond defaults. Variance scaling NEW.
- **Gain here.** Second-order while the evaluator binds. Sweep once on G0 inside the bench, and never carry dials across
  budgets ("Tuning transfers badly across budgets", DEEP_SEARCH_PATH §4).

**B13. Down-weight backups where the committee disagrees.**
- **What.** KataGo weights each playout by the inverse of the net's predicted error. The committee's member spread is a
  free stand-in: weight ∝ 1/(u0 + Var_members(leaf)), capped.
- **Sources.** [V code] KataGo defaults `uncertaintyCoeff` to 0.25 and `uncertaintyMaxWeight` to 8.0 for play
  (https://github.com/lightvector/KataGo/blob/7c42e21/cpp/program/setup.cpp, L592, L598).
- **Status here.** NEW. The committee's members are computed separately today, so their spread is available at no call
  cost in the L-ops (A4 keeps it).
- **Gain here.** Speculative. Member disagreement is epistemic spread, not the trained error head KataGo uses. Inference
  only; the training trees use one critic.
- **Counter.** The oracle gain at the matched rate, with and without the weighting.

**B14. Depth cap and dose.**
- **Sources.** [V paper, MEASURED over MuZero ablations] Hamrick et al.: "Dtree does not make much of a difference in
  most environments. Even in Sokoban and Go, we can recover reasonable performance using Dtree = 2". Search for training
  targets and data lifted median normalised strength from 46.7% to 90.3%, adding search at evaluation took it to 100%,
  and "Search at evaluation time only provides a small boost in most environments" (https://arxiv.org/abs/2011.04021
  p.5-7). [V paper] MuZero on Atari plateaued near 100 simulations, "suggesting that,
  by the end of training, the raw policy has learned to internalise the benefits of search"
  (https://arxiv.org/abs/1911.08265 p.6).
- **Status here.** BUILT (`depth_cap` 8, counting our decisions). MEASURED: the training tree reaches the 2.5-turn floor
  at 256 sims (tier 1b), and nothing past ~1,800 improves the root under this critic (tier 1).
- **Gain here.** A cost lever now. Depth is a question to reopen whenever the evaluator changes, never a closed one
  (§1.6).

**B15. Keep the tree between turns.**
- **What.** Re-root at the realised joint action and chance outcome.
- **Sources.** [V doc] lc0 re-roots at the played move and erases the rest (lc0 wiki, "Technical Explanation"). [V code]
  ELF's `treeAdvance()` does the same. [V2 via the project's deep read] Wang persisted his tree across decisions.
- **Status here.** NEW. Every operator builds fresh roots (`native_tree.py:733-780`).
- **Gain here.** Small. The realised state must match one of `chance_k` = 2 sampled children under the foe's actual
  column, and the belief worlds are resampled each turn. A7's cache keeps what is reusable (values) without re-rooting.
- **Counter.** How often the realised next state's digest is already in the tree (offline, from the smoke's trees).

**B16. Calibrate the leaf value.**
- **What.** A monotone map on the critic's output before it enters the tree.
- **Sources.** [R] Isotonic recalibration buys +0.0096, ~7% of the gap to the luck ceiling; 93% of the gap is ranking
  (RESULTS §27.1; IDEAS 2.13 `docs/IDEAS_POST_100M.md:575`).
- **Status here.** Measured, not applied to search.
- **Gain here.** A monotone map cannot change a ranking, so it cannot change a one-ply argmax. It can change deep
  backups that mix values of different depth and the soft target's temperature. Small.
- **Counter.** The fixed-point value of the soft target with and without the map.

### 2(c) Parallelism and batching across trees, games and worlds

**C1. Pin Step C's per-tree batch to what was measured, and price its quality cost.**
- **What.** `batch` sets how many descents a tree runs per round under a virtual loss (`native_tree.py:305-306`). Every
  Step C input ran at batch 8 (`br_true`, `native_tree_gates.py:207-208`), the TreeOp default is 1, and Step C's
  stated dose omits it (§1.2). Batch 1 → 8 cuts rounds ~8×; it also changes the search.
- **Sources.**
  - [V paper, MEASURED, Go MobileNet; throughput on an RTX 2080 Ti] Cazenave's Batch MCTS separates the two ways to
    compare (https://arxiv.org/abs/2104.04278 Tables III, VII, VIII). At matched EVALUATIONS batching loses: 8 batches ×
    32 under a virtual loss won 13-21% against sequential PUCT at 64 evaluations, 24-31% with a "virtual mean". At
    matched ROUNDS it wins: 32 batches × 32 with the virtual mean won 95-97% against 64 sequential evaluations and 68%
    against 512, at about 1/13 of the wall-clock; swapping in a virtual loss dropped the 68% to 29.5%.
  - [V paper, MEASURED on GPU] ELF OpenGo's virtual-loss constant sweep: 0.1 → 22%, 1.0 → 50%, 2.0 → 32% against the
    default 1.0 (Tian et al., https://arxiv.org/abs/1902.04522 §5.2 Table 1). [V doc] Its maintainer: batching 8-16
    rollouts "substantially improves GPU efficiency ... at the price of weakening the strength of the bot. We suggest
    using batchsize=4 when total number of rollouts are 800 or 1600" (https://github.com/pytorch/ELF/issues/25).
  - [V code] lc0 allows one collision per batch until the tree holds 28 nodes, and self-play sets
    `max-collision-visits 1` (https://github.com/LeelaChessZero/lc0/blob/1227b4c/src/search/classic/params.cc, L576;
    `src/selfplay/tournament.cc`). [V doc, MEASURED, chess on GPU] "1024 batchsize never wins" (lc0 wiki,
    Batchsize---Node-Collisions-Testing).
  - [V code, an "ad-hoc formula"] KataGo charges ~7 Elo per extra search thread at 800 visits and ~2 at 5,000
    (https://github.com/lightvector/KataGo/blob/7c42e21/cpp/program/playutils.cpp, L873-L899).
- **Status here.** BUILT dial. MEASURED once: batch 1 → 4 took an oracle root from 102.5 s to 41.6 s on the E-cores at
  "unchanged depth" (br 2.82 → 2.78 levels; commit `a0f6dd9`). The quality cost of batch 8 against batch 1 at 256 sims
  has never been read. The old tree's batch 16 cut depth from 2.70 to 2.15 levels at equal iterations
  (`docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md:159-166`).
- **Gain here.** Pinning batch 8 keeps Step C on its measured object and is worth ~5-8× on the fixed-cost term against
  the default (§1.3's table). The literature splits by what is held fixed. Per simulation, within-tree batching hurts,
  most at small budgets (ELF, lc0, Cazenave at matched evaluations). Per sequential round, which is what this box pays
  for, it wins once there are ~32 rounds and the in-flight penalty is a virtual mean (C5). So the read that fixes Step
  C's batch compares the fixed-point value at equal ROUNDS, not only at equal sims: batch 1, 4 and 8, with a virtual
  loss and with a virtual mean, on G0's roots.
- **Cost.** One line in the pre-reg and an oracle read (the arm set exists; add `tr_256` at batch 1 and 4).
- **Risks.** The measured +0.0019 fixed-point gain belongs to batch 8; a different batch needs its own read.
- **Counter.** `tree/dup_waits` (collisions), `tree/depth_mean` and `tree/turns_mean` against batch, the fixed-point
  value at the matched rate.

**C2. Put more decisions into each lockstep round.**
- **What.** The TreeOp runs one `search_many` over a poll's searched rows, so they share every round's two forwards
  (`tree_top.py:160-181`). With `k` = 8 battles a lane a poll owes ≤ 8 learner rows, so a round carries ~1 decision at
  Step C's floor and ~3 at R7's `frac`. Widening it: raise `k`, or defer the searches (D1).
- **Sources.** [V code] mctx, EfficientZero and LightZero run many independent searches in lockstep, one network call a
  simulation step (§2(a) A5). [V paper] LightZero: "the naive vectorized environment scheme shows no obvious gain in
  tree search methods because each environment needs a unique search tree"; batch the inference across trees instead
  (https://arxiv.org/abs/2310.08348 p.28). [V doc, https://github.com/pytorch/ELF/issues/25] ELF's self-play ran "32
  concurrent games ... Each concurrent game runs its own MCTS without any batching", average batch ~90. [V doc,
  MEASURED on a GTX 1080 Ti] Leela Zero's batch 8 raised a small 64×5 net's evaluations 2.6× but a 192×15 net's only 22%
  (https://github.com/leela-zero/leela-zero/issues/1601): small networks gain most from wider calls, and this project's
  are small. [V doc] Polygames batches inference across games and caps threads per tree near 8, where "overheads
  between threads lead to decreasing returns" (https://github.com/facebookincubator/Polygames, README). [V code] KataGo's
  main self-play config runs one search thread per game over 800 concurrent games, batching up to 192 rows a network
  call (`numSearchThreads 1`, `numGameThreads 800`, `nnMaxBatchSize 192`;
  https://github.com/lightvector/KataGo/blob/7c42e21/cpp/configs/training/selfplay8mainb18.cfg).
- **Status here.** The mechanism is BUILT (`search_many`, `3443923`). Raising `k` is conditionally PLANNED: "collector
  k > 8 (k 256: 1.87× a lane, 12.6% off-policy rows) — NOT planned ... if B0 shows the collector child is the critical
  path, a mechanism-level acceptance read (off-policy rows, clip fraction, approx_kl at k 32/64 vs 8) rides the
  shakedown" (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:391-394`).
- **Gain here.** At `k` 32 a poll carries ~4× the decisions, so the fixed term per searched decision falls ~4× [D]. It
  does not touch the row term, and every searched decision still sits on the critical path. D1 gets the same width with
  no staleness and no `k` change.
- **Cost.** A config change plus the named acceptance read.
- **Risks.** Staleness: 12.6% off-policy rows at k 256. Memory per slot.
- **Counter.** `tree/batch_rows`, `collect/child_idle_frac`, `loss/clip_frac_{searched,unsearched}`,
  `collect/policy_version_lag_max`.

**C3. A shared inference process across search processes.**
- **What.** Several search processes send leaf batches to one process that runs one forward over all of them.
- **Sources.** [V code] WU-UCT's master process and worker processes over pipes (https://github.com/liuanji/WU-UCT). [V
  doc] Ray Serve's batching defaults, `max_batch_size=10` and a 10 ms wait, show the fill-versus-latency trade
  (https://github.com/ray-project/ray/blob/master/doc/source/serve/advanced-guides/dyn-req-batch.md, L37-L38). [V doc,
  MEASURED on an x86 i5 under Linux] ipc-bench round trips at 100 bytes: pipes ≈ 6.2 µs, Unix sockets ≈ 7.7 µs, shared
  memory ≈ 0.2 µs (https://github.com/goldsborough/ipc-bench/blob/589146a/README.md, L10-L24). Apple numbers [U].
- **Status here.** PLANNED as a question: the P-core bench's "1/2/5/10 workers plus a shared-inference process"
  (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:99-103`); the process is "Not built"
  (`deep-search-step-a:scripts/native_tree_gates.py:52-53`).
- **Gain here.** Inference only. Training lanes each hold their own learner weights, so a box-wide server would serve
  five different networks and merge nothing. Across FP seats it pays only if seats' rounds coincide and each seat has
  other work while waiting. Its real use is feeding the ladder seat's root-parallel workers (C4) and the matrix unit
  larger GEMMs (§1.2).
- **Cost.** A day: shared-memory tensors and a request queue. Python pickling over a `multiprocessing.Queue` adds tens
  of µs a request [U].
- **Risks.** One process now fails for many seats, while the FP runner's crash and cleanup rules are written per arm
  (`docs/landmines.md:230-273`).
- **Counter.** Rows per server call, queue wait per request.

**C4. Root parallelism over belief worlds for the ladder seat.**
- **What.** One ladder decision has 10 P-cores and ~10 s. Today a searched seat uses one core. Run the 8 worlds as 8
  processes, each its own tree and network copy, and pool root statistics with `_root_q`'s rule
  (`native_tree.py:904-938`).
- **Sources.** [V2 via Mirsoleimani et al., https://arxiv.org/abs/1605.04447] Chaslot et al. 2008 reported root
  parallelization's "perfect playout speedup for up to 16 threads". [V2 via the MCTS survey,
  https://arxiv.org/abs/2103.04931 §8.6] with ISMCTS, root parallelization was "the most efficient approach" (Sephton et
  al. 2014). [V code] Foul Play runs its ladder search root-parallel over sampled worlds and averages visit shares
  (lit dossier part 2 §8.5; https://github.com/pmariglia/foul-play at `6c467c0`). [R] its author spends ~7 s a decision
  on the ladder (`docs/prior_work/README.md`, "Foul Play ON THE LADDER"). [V2 via Mirsoleimani et al.,
  https://arxiv.org/abs/1409.4297 and https://arxiv.org/abs/1605.04447] Lock-free shared trees (Enzenberger & Müller
  2010) beat root parallelism in Go, where playouts are cheap: Soejima et al.'s 4-8 lock-free threads outperformed root
  parallelism on 64 distributed cores. A shared tree needs threads on one tree, which the GIL rules out in Python; it
  becomes an option only with a Rust tree (F6).
- **Status here.** NEW. The L-ops run in one process; `scripts/fp_arms_parallel.py` parallelises arms, not worlds.
- **Gain here.** ~8× the search per wall second at the ladder. Tier 1 says more simulations buy nothing under this
  critic, so spend the cores on the evaluator instead: the rollout L-op at the knee is ~60 s a decision on one P-core,
  so ~6 s on 10 cores, and ~3.5 s with sequential halving (A14) [D]. That puts the one leaf evaluator measured to beat
  the critic inside the ladder clock.
- **Cost.** A day: a pool of seat workers holding the committee, with `SearchNode.save()` bytes crossing the pipe.
- **Risks.** Only the ladder object benefits. A searched ladder seat also needs time management and a greedy fallback,
  neither built (`docs/landmines.md` ladder clock; DEEP_SEARCH_PATH `:135-137`).
- **Counter.** Wall ms a decision, worlds completed within budget, bank seconds left per turn.

**C5. Replace the virtual loss with in-flight counts or a virtual mean.**
- **What.** WU-UCT keeps O(s), the simulations started and not finished, and widens only the exploration term:
  V(s′) + β·√(2·log(N(s)+O(s)) / (N(s′)+O(s′))). No value is faked. Cazenave's "virtual mean" adds visits at the node's
  current mean instead of a loss.
- **Sources.** [V paper, MEASURED, Xeon + RTX 2080 Ti] WU-UCT was best among parallel MCTS variants in 12 of 15 Atari
  games at 16 workers and 128 simulations (Liu et al., https://arxiv.org/abs/1810.11755 Eq. 4, Table 1). [V paper]
  Cazenave's virtual mean beat the virtual loss at every batch shape tested, and was the difference between 68% and
  29.5% against sequential search at 512 evaluations (C1). [V paper] ExIt's rule for asynchronous batching: search a set
  of positions larger than twice the batch and switch whenever one awaits an evaluation, because "suboptimal moves are
  made in the tree where prior information has not yet been calculated" (Anthony et al.,
  https://arxiv.org/abs/1705.08439 App. B).
- **Status here.** NEW. The native tree applies `virtual_loss` to both W and N on our and the foe's arms
  (`native_tree.py:499-529`).
- **Gain here.** It would let C1 raise the per-tree batch with less distortion, which is exactly Step C's small-budget
  regime.
- **Cost.** Hours: a dial beside `virtual_loss`, derived from the signature.
- **Risks.** A new search; read it on G0 at the matched rate.
- **Counter.** As C1.

**C6. Pipeline tree bookkeeping against inference.**
- **What.** Split the collector's trees into two groups: while group A's forward runs, group B walks its trees and steps
  its engine, then swap.
- **Sources.** [V paper] LightZero's collector does this: "divides these modules into several groups ... data collector
  alternate between different groups" (https://arxiv.org/abs/2310.08348 p.28-29).
- **Status here.** NEW.
- **Gain here.** Bounded by the Python and engine share of a round, which no measurement separates yet (§4 Q1). On one
  core it needs the forward to release the GIL and run on another thread; PyTorch does release it inside ops. Probably
  worth less than D1.
- **Cost.** A day.
- **Counter.** Wall per round against the sum of its parts.

**C7. Lanes against cores per lane.**
- **What.** Five two-core lanes fill the ten P-cores. A searched lane could take a third core for a search worker at the
  price of a lane.
- **Status here.** Step C D1 defers width to the width bench and keeps 3 + 2
  (`STEP_C_PREREG_DRAFT_2026-09-26.md:18-28`); a lane past the tenth P-core spills onto the E-cores
  (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:124-140`).
- **Gain here.** None until D1 and C2 are measured. The credit line's power depends on lanes (P(X-POS) 0.60 at +0.027,
  `STEP_C_PREREG_DRAFT_2026-09-26.md:92-102`), so width is the last thing to spend.
- **Counter.** `collect/child_idle_frac`; learner idle time per update.

**C8. Rent a GPU for offline search: reanalysis and label campaigns.**
- **What.** Search banked positions (G0's rows, or a lane's stored episodes) offline, thousands of trees in lockstep,
  one batched forward a step over thousands of rows. The engine stays on CPU cores.
- **Sources.** [V code] EfficientZero's reanalysis runs batched MCTS on GPU workers fed by CPU context workers
  (https://github.com/YeWR/EfficientZero/blob/468bb03/core/reanalyze_worker.py). [V paper, MEASURED on 1 A100 + 30 CPU
  cores] ReZero's backward-view reanalysis ran 2-4× less wall-clock per 100k steps than a reanalyse-everything MuZero
  (https://arxiv.org/abs/2404.16364 Table 1). CLAUDE.md allows a GPU "for supervised/offline arms if worth renting".
- **Status here.** NEW.
- **Gain here.** It makes D2 (reanalysis) and D6 (evaluator label campaigns at thousands of positions) affordable
  without the box. The network cost per leaf collapses on a GPU at thousands of rows, and the job becomes engine-bound
  at ~5.7 µs a row (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:707-717`, a session measurement).
- **Cost.** A day of glue; the engine builds on Linux.
- **Risks.** Pinned torch and engine versions must match the box. Purity holds: our positions, our network.
- **Counter.** Labels per hour; the label-quality read (`STEP_C_PREREG_DRAFT_2026-09-26.md` §0 D2).

**C9. Overlap the engine with the network on threads.**
- **What.** `expand` releases the GIL, so a thread could expand the next round's leaves while a forward runs.
- **Status here.** NEW.
- **Gain here.** Bounded by the engine's share, ~1 µs a leaf (§1.2). Not worth a thread; recorded so it is not
  re-proposed.

### 2(d) Training-loop integration

**D1. Under `play: false`, defer the searches and run them in wide lockstep.**
- **What.** Under `play: false` the lane plays π_θ, so no engine step needs the search result. Today the TreeOp still
  runs inside `poll()` between the policy forward and `env.step` (`rl/envs/engine_collector.py:326-341`), and each
  round carries only that poll's ~1-3 searched decisions. Instead:
  1. At each poll, record the coin winners: slot, row, the `SearchNode` snapshot (its `save()` bytes are a few hundred
     bytes plus the tracker), the prior and the foe prior. Step the engine at greedy speed.
  2. Before the rollout ships, run one `search_many` over the pending decisions in rounds of a few hundred decisions,
     and fill `search_pi` and `search_v`. The weights are the ones that collected the rollout, so the target's lag is
     zero.
  3. Variant: ship the pending snapshots with the rollout and let the LEARNER run the searches at the start of its
     update, on its own core. The learner's process idles while the child collects (CLAUDE.md's stalled-lane landmine
     describes exactly that idle parent), so if the child binds, this moves search onto idle time.
- **Sources.** [V code] EfficientZero, LightZero and MiniZero all search many independent roots in lockstep, one
  batched network call a simulation step (§2(a) A5; https://github.com/rlglab/minizero README: "the self-play worker
  runs the selection for each MCTS to collect a batch of leaf nodes and then evaluates them through batch GPU
  inferencing"). [V paper] LightZero's grouped collector (C6).
- **Status here.** NEW. The plans price the tree inside the two-core lane (R7 plan §5;
  `STEP_C_PREREG_DRAFT_2026-09-26.md` D1: "frac is lowered ... before the dose is ever touched").
- **Gain here.** The fixed per-call term, half or more of a searched decision at Step C's measured batch, falls ~30-100×
  once a round carries ~100 decisions. A searched decision then costs its rows, ~5-6 ms idle and ~10-12 ms at fleet
  contention, which fits the floor's ~19 ms with room [D, §1.3]. The learner-side variant adds the learner's idle core
  to the search budget. Step C's ≥ 289 steps/s floor then stops depending on `frac` being cut to fit, which is the
  constraint D1 of the pre-reg names as binding.
- **Cost.** One to two days: the pending queue, the fill step, the `take()` alignment (a record per decision, searched
  or not, `tree_top.py:212-225`), a resume path, counters.
- **Risks.** Does not apply under `play: true`, where the played action needs the search. Rounds of hundreds of trees
  hold hundreds of trees in memory; chunk them. The learner-side variant lengthens the update, so wall = max(update +
  search, collect); Q0 says which side binds. It is the same search object as in-line, so no new quality read is needed,
  only a within-tolerance check against the in-line TreeOp on the same snapshots.
- **Counter.** `search/pending_max`, `search/deferred_ms`, rows per round, and `collect/child_idle_frac` against
  learner idle time.

**D2. Reanalysis: re-search stored positions with the newest weights.**
- **What.** Keep the last N rollouts' searched snapshots. Each update, re-search a sample with the current weights and
  feed the fresh π′ and v′ to the KL term and the evaluator head as an extra minibatch stream. PPO's surrogate stays
  on-policy; only the auxiliary terms read the replay.
- **Sources.**
  - [V paper] MuZero Reanalyze uses a fresh-search policy target "for 80% of updates", with a target network for n-step
    values (Schrittwieser et al., https://arxiv.org/abs/1911.08265 App. H).
  - [V paper] MuZero Unplugged holds compute constant and varies the reanalyse fraction: median human-normalised Atari
    score 1,331.7% at 50% reanalyse on 2,000M frames, 1,006.4% at 95% on 200M, 126.6% at 99.5% on 20M
    (https://arxiv.org/abs/2104.06294 Table 1).
  - [V paper] EfficientZero reanalyses 99% of policy targets and 100% of value targets
    (https://arxiv.org/abs/2111.00210 App. A.4).
  - [V paper, MEASURED on 1 A100] ReZero's backward-view reanalysis skips re-searching the taken action's subtree and
    ran 2-4× less wall-clock per 100k steps (https://arxiv.org/abs/2404.16364 Table 1).
  - [V code] muzero-general's reanalyse refreshes values only and re-runs no search
    (https://github.com/werner-duvaud/muzero-general/blob/0825bd5/replay_buffer.py).
- **Status here.** NEW. "Reanalys" has zero hits in the repo (repo inventory G.1).
- **Gain here.** More learning signal per search: one searched position is re-labelled as the student improves, which
  is the compounding the plan bets on. Its batches are as wide as the sample, so the fixed-call term is negligible.
- **Cost.** D1 first; then a snapshot buffer and a second loss stream, a day.
- **Risks.** The replay's states come from older policies; the targets are fresh. Keep the on-policy critic stop
  condition (`STEP_C_PREREG_DRAFT_2026-09-26.md` §0 D2). A second loss stream is a critic-side change and gets its
  counter watched (CLAUDE.md stacking convention).
- **Counter.** `reanalyze/positions_per_update`, `reanalyze/age_updates`, `search/kl_update` split by age.

**D3. Playout-cap randomization.**
- **What.** KataGo runs a full search on a random share p of moves and a cheap one on the rest, and records policy
  targets only from full searches.
- **Sources.** [V paper] p = 0.25 with (N, n) = (600, 100) rising to (1000, 200) after two days; removing it cost a
  1.37× training-time factor (Wu, https://arxiv.org/abs/1902.10565 §3.1, Table 2; ~27 V100s). [V code] the current
  config: `cheapSearchProb 0.75`, `cheapSearchTargetWeight 0.0`
  (https://github.com/lightvector/KataGo/blob/7c42e21/cpp/configs/training/selfplay8mainb18.cfg).
- **Status here.** BUILT as the `frac` coin on eligible rows (`top.py:148-150`; `tree_top.py:156`, whose docstring calls
  it "KataGo's playout-cap randomisation"). Step C's floor is `frac` ≥ max(0.25, not inert)
  (`STEP_C_PREREG_DRAFT_2026-09-26.md:22-26`).
- **Gain here.** KataGo's reason, more value samples per unit of compute, is already met: the value target is GAE over
  every row. What remains is the rate, which D1 makes cheap. Nothing to build.
- **Counter.** `search/searched_frac`, `search/eligible_frac`.

**D4. Value targets from the tree.**
- **What.** v′ = E_{a~π′} E_{b~prior} Q(a,b) into an auxiliary head, never the root max; an n-step bootstrap that uses
  v′ at searched rows; a mix of TD targets for fresh data and search values for old data.
- **Sources.** [V paper] MuZero Unplugged: at 99.5% reanalyse, a 5-step TD target toward a target network beat direct
  regression on the search value, 126.6% against 115.3% median (https://arxiv.org/abs/2104.06294 Table 8). [V paper]
  EfficientZero V2's mixed target, TD for recent samples and the search value for old ones, beat both a multi-step TD
  target and GAE on two of three Atari games (https://arxiv.org/abs/2403.00564 App. J.2). [V paper] EfficientZero
  shortens the bootstrap horizon as a sample ages (https://arxiv.org/abs/2111.00210 Eq. 12).
- **Status here.** v′ and its head BUILT (`native.py:236`; `native_tree.py:1081`; `rl/agents/ppo.py:885-899`). The GAE
  blend dial BUILT at 0, promoted only after `search/value_gap` reads. The n-step blend and the mixed rule NEW.
- **Gain here.** Target quality for the evaluator head, which is where the room is (§1.6). The mixed rule matters only
  with D2's replay.
- **Risks.** Never a max over our moves with the foe fixed: that max is G1's +0.019 of optimism
  (`docs/landmines.md:873-898`; `STEP_C_PREREG_DRAFT_2026-09-26.md:49-51`).
- **Counter.** `search/value_gap`, `search/value_gap_critic`, the head's loss and its Spearman on G0.

**D5. TreeStrap labels on a separate evaluator head.**
- **What.** Train the leaf evaluator on the tree's internal nodes, not only its root.
- **Sources.** [U, paper unreachable here] Veness et al. 2009, TreeStrap
  (https://proceedings.neurips.cc/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf). [V paper] Student of
  Games trains its value network on values from solved sub-searches (Schmid et al., https://arxiv.org/abs/2112.03178).
- **Status here.** PLANNED: Step C D2 puts TreeStrap on a separate evaluator head the TreeOp reads, with non-optimistic
  labels from our information set, N ≥ N_min, after a label-quality read (`STEP_C_PREREG_DRAFT_2026-09-26.md:30-66`).
  Not built on the branch.
- **Gain here.** Many labels per searched decision at no extra search. The risk is self-bootstrapping: the labels are
  made of the same evaluator's leaf values. The label-quality read is the right gate.
- **Counter.** The evaluator head's out-of-fold Spearman on G0 against rollout means.

**D6. An evaluator label campaign.**
- **What.** Fine-tune the leaf evaluator on rollout labels over thousands of positions.
- **Status here.** PLANNED as its own lap. R7's plan measured that 500 positions transfer nothing (out-of-fold Spearman
  +0.486 → +0.490; "positions, not rollouts, are what the fit lacks") and named the fix: "a CAMPAIGN — thousands of
  positions at ~16 rollouts per cell" (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:306-324`; IDEAS 8.2).
- **Gain here.** The one axis measured to have room (rollouts beat the critic). C8 makes it cheap.
- **Risks.** True-world labels carry the peek; the right target is the posterior mean
  (`STEP_C_PREREG_DRAFT_2026-09-26.md` §0 D2).
- **Counter.** Out-of-fold Spearman by turn bucket.

**D7. Policy-surprise weighting.**
- **What.** Up-weight training rows whose search target differs most from the net's prior.
- **Sources.** [V code] KataGo `policySurpriseDataWeight 0.5`: half the weight uniform, half ∝ KL(target ‖ prior), with
  no importance correction. [V doc] "one of the larger improvements in KataGo's training between its g170 run and
  earlier runs" (https://github.com/lightvector/KataGo/blob/7c42e21/docs/KataGoMethods.md, no number).
- **Status here.** NEW; a dial on the KL term (`ppo.py:1923-1974`), derived from the signature.
- **Gain here.** Unknown. Searched rows already concentrate on uncertain positions, so this compounds a selection bias
  R7's clip counters flagged.
- **Counter.** The weighted KL's effective sample size; `search/kl_update`.

**D8. Short-horizon value heads.**
- **What.** Heads predicting the value k turns ahead, as auxiliary targets.
- **Sources.** [V doc] KataGo's short-term value and score heads at ~6, 16 and 50 turns give "lower-variance feedback"
  (https://github.com/lightvector/KataGo/blob/7c42e21/docs/KataGoMethods.md). [V paper] KataGo's auxiliary policy target
  is the opponent's next move, weighted 0.15 (https://arxiv.org/abs/1902.10565 §3.4); this project's opponent-action
  head (D25) is the credited analogue.
- **Status here.** The opponent-action head BUILT and credited. Short-horizon heads NEW.
- **Gain here.** It speaks to the critic's measured opening blindness (r² 0.287 at turns 2-8 against 0.727 at 23+,
  RESULTS §27.1; IDEAS 4.10). An objective change, so its own lap under the stacking convention.
- **Counter.** Per-bucket Spearman on G0.

**D9. Keep played-π′ rows out of PPO's clipped surrogate.**
- **What.** Under `play: true` a searched row's behaviour is π′, and PPO clips 51.2% of them against 15.9% record-only
  on the same selection (§1.3). Train those rows only through the KL term.
- **Status here.** NEW dial. R7 stores float32 log π′(a) so the ratio is exact (`top.py:173-181`).
- **Gain here.** Moot under `play: false`, Step C's design. It matters only if a played lane runs again.
- **Counter.** `loss/clip_frac_searched`, gradient norm per arm.

**D10. Cross-entropy to π′ as the primary policy loss, and the β warm-up.**
- **Status here.** PLANNED as the lap after Step C, conditional on mechanism reads (i) and (vi) moving (DEEP_SEARCH_PATH
  Step C "Policy target"). β warms from 0 to β* over ~5M steps with a 2M smoke ladder
  (`STEP_C_PREREG_DRAFT_2026-09-26.md` §2). Recorded for completeness.

**D11. Grow the search budget over training.**
- **What.** Raise simulations per searched decision as the net improves.
- **Sources.** [V paper] KataGo raised (N, n) from (600, 100) to (1000, 200) after two days. [V paper, MEASURED on
  4× 1080 Ti] MiniZero's progressive simulation beat fixed budgets by the end of training on board games but trailed
  before 54,000 steps, and lost on Atari (359.97% against 395.87% mean) (https://arxiv.org/abs/2310.11305 §IV-F).
- **Status here.** NEW.
- **Gain here.** Unknown and mixed in the literature. A dose schedule at the same objective can stack by the convention,
  but only with its own counter. Low priority behind D1 and D2.
- **Counter.** `search/sims_mean` over training beside the fixed-point instrument at matched steps.

### 2(e) Imperfect information and simultaneous moves

**E1. PIMC over belief worlds: how many, and how to fuse them.**
- **What.** Sample B worlds of the foe's hidden team, search each, and fuse at the root. The L-op averages Q over worlds
  and takes a soft best response (`lop.py:184`). Foul Play averages each world's root visit share and samples among
  moves within 75% of the best (lit dossier part 2 §8.5; https://github.com/pmariglia/foul-play at `6c467c0`,
  `fp/search/main.py` L16-L44).
- **Sources.** [V2 via MAPLE, https://arxiv.org/abs/2605.24139 p.3] AlphaZe** fuses its per-world trees by average
  POLICY, because per-world values "may be biased toward favorable determinizations". [V code] Foul Play gives the early
  game more worlds at half the time each (`fp/modes/random_battle.py` L77-L84).
- **Status here.** BUILT: B = 8 in both L-ops. MEASURED: at B = 4 the belief L-op's gain halves, so ladder worlds are
  B ≥ 8 (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:279-280`); critic breadth B32 − B8 read −0.0010 ± 0.0006
  (SESSION_LOGS 2026-09-25 21:45Z). Policy fusion at the root is NEW as an inference rule; the fusion reads already
  compute its target form (`t_avg`, `native_tree_gates.py:229-245`).
- **Gain here.** Small at one ply, where the measured fusion cost is +0.0003 ± 0.0003 a decision
  (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:269-281`).
  Foul Play's early-game rule costs nothing to read offline: more worlds while the foe's bench is unrevealed.
- **Counter.** `lop/worlds_built`, argmax flips across worlds.

**E2. Measure whether gen-1 random battles are PIMC-friendly.**
- **What.** Long et al. predict PIMC's loss to an equilibrium player from three game properties: leaf correlation,
  bias, and disambiguation. A 2026 paper measured all three by self-play with its own policy network and reported the
  search gain beside them.
- **Sources.** [V2 via Rubin 2026 and a third-party issue; the AAAI paper was unreachable] Long et al. 2010
  (https://ojs.aaai.org/index.php/AAAI/article/view/7562): PIMC does worst when leaf correlation is low. [V paper,
  MEASURED on an A10G at a 185 ms budget] Rubin measured all three in Legends of Code and Magic, found search worth
  +24.6 points, and found worlds saturating near 32 (https://arxiv.org/abs/2609.06816 §IV-E, §V-A).
- **Status here.** NEW. The fusion counters are BUILT (`native_tree.py:956-978`), and the fusion read at depth is
  UNRESOLVED: +0.00058 ± 0.00106 a decision, 95% [−0.021, +0.037] a battle against a 0.025 floor
  (`STEP_C_PREREG_DRAFT_2026-09-26.md:125-126`).
- **Gain here.** A cheap, direct instrument for the question Step C cannot yet answer: whether per-world trees fuse
  strategies at depth. Disambiguation is log2 of the number of generator-consistent foe teams by turn, from the
  project's own determinizer. Leaf correlation is how often two belief worlds, played out by the committee from the same
  state, produce the same winner, by turn and by unrevealed-mon count. Bias is P(p1 wins) of those pairs.
- **Cost.** A batch job on the engine; hours.
- **Counter.** The three curves by turn bucket, beside the fusion counter's `tree/fusion_disagree`.

**E3. One tree over our information sets instead of one tree per world.**
- **What.** Information Set MCTS keeps one tree whose nodes are our information sets and samples a world per
  iteration. MAPLE's neural form samples k worlds once, pushes every selected path through all k, evaluates the k leaf
  rows in one batched call, and averages policy and value.
- **Sources.** [V2 via arXiv:1807.06813 and arXiv:2103.04931] Cowling, Powley & Whitehouse 2012 define SO-, POM- and
  MO-ISMCTS with availability counts. [U, abstract] ISMCTS beat determinized UCT in two of three games, including one
  with simultaneous moves. [V paper, MEASURED] MAPLE with k = 5: Phantom Go Elo 1,063 (PIMC) → 1,354; Dark Hex 1,130
  (PIMC) → 1,266 with learned world selection, but 1,076 with random worlds, WORSE than PIMC
  (https://arxiv.org/abs/2605.24139 p.5-6). [V2 via pkmn.ai's catalogue] Ihara et al. 2018: ISMCTS beat determinized
  MCTS at fixed iterations in gen-6 Pokémon.
- **Status here.** NEW. The node's `view` digest of our observation already exists (`native_tree.py:415-416`).
- **Gain here.** Bounded by the fusion cost at depth (E2), and it deepens one tree instead of eight shallow ones. The
  simultaneous-move catch MAPLE does not face: the foe knows its team, so foe decisions must stay world-specific
  (MO-ISMCTS), and the foe's legal set differs across worlds, so shared foe arms need availability counts.
- **Cost.** A week.
- **Risks.** MAPLE's Dark Hex row: with random worlds it lost to PIMC. World selection is part of the method.
- **Counter.** `tree/fusion_disagree`; the fixed-point value against per-world trees at equal rows.

**E4. Weight the belief worlds by the foe's observed actions.**
- **What.** PIMC's second pathology, non-locality: the foe's earlier choices carry information about its hidden team.
  Weight each sampled world by the likelihood of the foe's observed actions under the foe prior in that world.
- **Sources.** [V2 via arXiv:1911.07960 §2] Frank & Basin 1998's non-locality. [U, the NeurIPS copy was unreachable]
  POMCP reweights belief particles after each real observation (Silver & Veness 2010,
  https://papers.nips.cc/paper/4031-monte-carlo-planning-in-large-pomdps).
- **Status here.** NEW. `World.weight` exists and the tree pools by it (`native.py:79`, `:206-207`;
  `native_tree.py:925`), but the L-op averages its worlds equally (`lop.py:184`).
- **Gain here.** The generator's team-structure residual is small in gen 1, 0.024-0.034 nats (D19,
  `docs/IDEAS_POST_100M.md:859-868`); the peek measured at one ply was nothing per battle (G1b's belief − true +0.0022 ±
  0.0079). What the belief does not model is action-based inference, such as a foe's switch revealing a counter. Read
  it offline on G0 first. By JOURNEY 15 it is written behind the generation interface, since the residual is a gen-1
  fact.
- **Counter.** The effective sample size of the weights; the oracle gain on G0 with and without them.

**E5. The foe model inside the tree.**
- **What.** `br_prior` best-responds to the foe prior. The alternatives mix the prior with an equilibrium strategy
  (restricted Nash response), or best-respond smoothly to a foe of estimated rationality.
- **Sources.** [V2 via Ponsen et al., https://arxiv.org/abs/1401.4591 §4.1] Restricted Nash Response: with probability
  p the foe must play the model; p = 1 is a pure best response, p = 0 the equilibrium. [V paper] Albatross's smooth best
  response to an estimated-rationality foe (https://arxiv.org/abs/2402.03136 §4). [V paper, MEASURED, VGC with open
  team sheets] PokaiTrainer's opponent shortlist contained the realised joint action on 64% of turns
  (https://arxiv.org/abs/2608.29197 p.9).
- **Status here.** `br_prior` BUILT and measured best of three at 1,800 sims (B11). The foe prior is the actor on the
  foe's view; the opponent-action head feeds only the old tree and is a "parity dial" in the port
  (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:63-64`). RNR mixing and a smooth best response NEW.
- **Gain here.** G0 measured the root's opponent model as first-order: `opp_model_gap` +0.059, and the foe's
  oracle-best reply lies outside the top four columns on 25% of positions (`readouts/R7_G0_READOUT.md`). A p < 1 mixture
  hedges a prior that puts ~0 on the foe's best reply, which is the single failure Wang's thesis reports
  (`docs/prior_work/WANG_SEARCH_DEEP_READ.md`). Readable offline on G0.
- **Risks.** Against humans on the ladder the foe prior is a self-play model of a different population.
- **Counter.** `opp_model_gap` and the oracle gain on G0 by p.

**E6. Leaf values conditioned on a belief (DeepStack, ReBeL, Student of Games).**
- **What.** Solve a depth-limited subgame at the public belief state, with a value network that takes the belief as
  input.
- **Sources.** [V paper, MEASURED on one GTX 1080] DeepStack thinks a median 2.3 s, mean 3.0 s per action
  (https://arxiv.org/abs/1701.01724 Table 7). [V paper] ReBeL's own limitation: its network input "grows linearly with
  the number of infostates in a public state", "intractable in games such as Recon Chess"
  (https://arxiv.org/abs/2007.13544 p.9); its compute is stated two ways, up to 128 machines × 8 GPUs in the text and 90
  DGX-1 in the appendix. [V paper] Student of Games' re-solving step costs O(kT²) network calls for T iterations under
  imperfect information (https://arxiv.org/abs/2112.03178 p.18).
- **Status here.** NEW, and deliberately not proposed: R7's plan lists CFR/ReBeL under "deliberately not proposed"
  (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:885-898`).
- **Gain here.** Out of reach. The foe's infostates per public state are the consistent teams, ~10^9 or more early in
  a battle. What transfers is already here or in D2 and D5: batch every leaf of a solver iteration into one call (the
  root grid does), and train values on search-visited states rather than random ones.

**E7. Mixed root decisions at inference.**
- **What.** Play a sample from π′ restricted to near-best rows instead of the argmax, as Foul Play does (E1).
- **Sources.** [V code] Foul Play's rule, E1. [R] The deterministic-policy loop: battles stall to the 1,000-turn cap,
  and a tie is a non-win (`docs/landmines.md:952-1013`; IDEAS 2.14 is the breaker).
- **Status here.** π′ BUILT; the L-ops play the argmax behind a margin gate (`lop.py:191`). Sampling at inference NEW.
- **Gain here.** Against a fixed opponent such as the SH or FP instruments, a mixed root costs expected value. On the
  ladder it resists exploitation and breaks loops. A ladder-object question, not an instrument question.
- **Counter.** Loop-cap ties per 1,000 battles; the override rate.

**E8. Smooth UCT.**
- **What.** At each node, pick either the UCB action or a sample from the node's average strategy, mixing with a
  decaying probability, as fictitious play does.
- **Sources.** [U, abstract] Heinrich & Silver 2015: Smooth UCT approached a Nash equilibrium in Kuhn and Leduc poker
  where UCT diverged. [V paper] Student of Games: "its convergence properties are not known"
  (https://arxiv.org/abs/2112.03178 p.8).
- **Status here.** NEW. It sits between `legacy` (decoupled UCT) and `sm_rm`, both measured below `br_prior`.
- **Gain here.** Low while `br_prior` leads.

**E9. What the Pokémon search agents do.**
- **Foul Play** [V code, lit dossier part 2 §8]. Decoupled UCB1 per side at c = √2; a hand-written leaf through a
  sigmoid; chance enumerated with probabilities and one child sampled per visit; in gen 1, average damage with a crit
  branch only when average damage does not KO. Each iteration costs ~0.8 µs, derived from the FP@N 25k/12k calibration
  against FP@20's 20 ms [D]. Its strength comes from very many cheap evaluations; this project has few, expensive,
  better ones. Unrevealed foe species are drawn uniformly, a cruder prior than the project's generator posterior.
- **Athena** [V paper, https://arxiv.org/abs/2212.13338 §4.1]. A 2-turn simultaneous lookahead with a payoff matrix per
  node, forward pruning of dominated actions by static rules, and a distributed transposition table on 4 single-socket
  servers; peak rank 33 in gen-7 random battles.
- **PokéChamp** [V paper and code, https://arxiv.org/abs/2503.04094 p.14]. Depth-2 minimax with an LLM leaf; about a
  third of its ladder games were lost on the clock, and its 1,300-1,500 Elo is a projection that removes them. The clock
  capped it, not the algorithm.
- **Wang 2024** [V2 via `docs/prior_work/WANG_SEARCH_DEEP_READ.md`]. 1,000-2,000 rollouts a decision on 20 workers at
  10 s a move, a fresh determinization per rollout, critic leaves, the opponent sampled from the same network, the tree
  kept across decisions. No ablation of any search dial; only MCTS+NN was laddered.
- **PokaiTrainer** [V paper, https://arxiv.org/abs/2608.29197]. Student of Games for VGC doubles: a Rust engine
  enumerating each joint action's weighted outcomes, a median 0.08 ms a turn against Showdown's 2.0 ms; median 2.7 s a
  decision on the ladder. "Budget alone saturates: ... depth grows only logarithmically in budget, and the extra spend
  buys width the value network cannot use" (p.8), the same shape as this project's tier 1. "Every search agent beats its
  own policy head" (p.8). Its value network "prices early-game positions optimistically" (p.8), the defect this
  project's critic shows in the opening. It is initialised by behaviour cloning on 122,804 human replays and plays open
  team sheets, so it is evidence about search, not about a pure self-play lane or closed-sheet hidden information. Its
  per-lever nulls sit inside its own stated ±4-6 pp resolution (App. E.3), so they are not evidence against any lever
  (CLAUDE.md rule 6).
- **Others.** A Showdown AI competition in gen-7 random battles found a one-turn lookahead beat minimax and BFS under
  simulation cost; PokeML solved the one-turn joint matrix with `lrsnash` and sampled from it; shallow-red tried DUCT,
  Exp3, regret matching, OOS and MC-CFR before settling on Deep MC-CFR [V2 via https://github.com/pkmn/ai
  `static/projects.yml`].

### 2(f) Runtime and hardware

**F1. Threads per search process.**
- **What.** Every search path runs one torch thread (`rl/common/config.py:34-38`; the child sets it,
  `rl/envs/engine_collector_proc.py:88`). Whether one thread is right for 50-400-row leaf calls has never been measured.
- **Sources.** [R] The threads knob reaches Accelerate's sgemm: a bare `torch.mm` at the scorer's shape ran 1.56× at 2
  threads and plateaued after (`docs/engine_port/NOTES.md:2207-2225`). Six threads read 0.85× of one on the 256-row
  update (`docs/landmines.md:372-375`). [V doc, MEASURED on a Raspberry Pi] fewer threads traded best-case latency for
  fewer latency spikes (https://github.com/pytorch/tutorials/blob/65e2e1a/intermediate_source/realtime_rpi.rst,
  L325-L340).
- **Status here.** Fixed at 1; NEW as a measurement.
- **Gain here.** At most 1.56× on a single process's GEMMs, and likely nothing at fleet width, where every core is
  taken and the matrix units are shared (F2). Worth one bench row, not a design change.
- **Counter.** Gate (ii)'s ms at 1 and 2 threads, alone and beside a loaded fleet.

**F2. The shared matrix unit and fleet-wide contention.**
- **What.** `nn.Linear` on this wheel runs through Accelerate on Apple's matrix unit, of which there is one per CPU
  cluster, saturated by a single thread.
- **Sources.** [V code] The torch 2.13 macOS wheel is built `USE_MKLDNN=OFF`
  (https://github.com/pytorch/pytorch/blob/v2.13.0/.ci/wheel/build_wheel.sh, L181) and resolves BLAS to Accelerate
  (`cmake/Modules/FindBLAS.cmake`, L123-L133). [V doc] "There is one such block per CPU cluster"
  (https://github.com/tzakharko/m4-sme-exploration/blob/089ceeb/reports/01-sme-overview.md, L44). [V paper, MEASURED on
  base M4] FP32 outer products at ~2 TFLOPS on one P-core thread, flat from 1 to 4 P threads, with a fifth thread on the
  E cluster lifting it to 2.34 (https://arxiv.org/abs/2409.18779 §III-F). [V paper] an M4 Pro Mac mini's 12 cores share
  "two SME units" (LOOPS, https://arxiv.org/abs/2511.08158 §4.1); the 14-core part's layout was not found [U]. [R] This
  box's bare GEMM plateaus at ~2.2 TFLOP/s from two threads up (§1.2).
- **Status here.** NEW as a question; nothing measures it.
- **Gain here.** It changes what "more processes" buys. If the fleet's GEMMs contend on one or two matrix units, then
  B0's "structural" six-wide tail and the ~2× contention factor are this effect, and a searched lane's cost rises with
  the number of searched lanes. The levers that answer it are fewer, larger GEMMs (C2, D1, A4, A5) and leaves that leave
  the matrix unit: a NEON int8 leaf runs per core (A10).
- **Cost.** An hour for the probe.
- **Counter.** §4 Q2: N concurrent single-thread GEMM loops at leaf shapes, N = 1..10, P-cores only, total throughput
  against N.

**F3. Core ML and the Neural Engine.**
- **Sources.** [V paper, MEASURED on M1] The Neural Engine costs ≈ 0.19-0.23 ms of dispatch per call, submissions
  serialize one in flight, and batching to 512 samples cut per-sample cost from ≈ 196 µs to ≈ 1.5 µs; "The CPU is the
  better choice for the trivial cases" (Bryngelson, https://arxiv.org/abs/2606.22283 §2.3-§2.4, §9.4, §11.4). [V paper,
  MEASURED on M1] Through the public Core ML path the floor is ≈ 0.54 ms per inference (Shahir,
  https://arxiv.org/abs/2608.22110). [V doc] The Neural Engine computes in fp16
  (https://github.com/apple/coremltools/blob/db4dd46/docs-guides/source/typed-execution.md, L48).
  [V PR text, MEASURED on an M3 Max with a large convnet] KataGo's Metal backend feeds GPU and Neural Engine server
  threads from a batching server (https://github.com/lightvector/KataGo/pull/1148).
- **Status here.** NEW; zero hits in the repo.
- **Gain here.** None per call: a 0.2-0.5 ms floor that serializes across processes is worse than the CPU's fixed cost.
  It could pay only behind a shared server that pools hundreds of rows per call (C3), and only if fp16 keeps the
  critic's ranking.
- **Counter.** µs per row at 512 rows through Core ML against the traced CPU forward; argmax agreement on G0.

**F4. MPS or a GPU for search leaves.**
- **What.** CLAUDE.md keeps the RL loop on the CPU by measurement: MPS read 1.15× on the learner and ~2.5% end to end
  (`docs/landmines.md:334-386`). The "GPU / MPS inference — CUT, unconditionally" line was priced for the collection
  act path at 3.7 µs a decision (`docs/prior_work/THROUGHPUT_SPEC.md:191-192`), on the old flat MLP.
- **Status here.** Measured for the learner and the act path only; never priced for search leaves, where the network
  dominates. IDEAS 2.8 says the kill's premise "expires with the collector port" (`docs/IDEAS_POST_100M.md:359-386`).
- **Gain here.** Unknown. A fused committee call carries ~1,000 rows at the one-ply L-op and several thousand in the
  tree L-op, the regime where accelerators start to pay. The ANE monograph's point applies to both accelerators: below
  their dispatch floor the CPU wins (F3).
- **Risks.** Collides with CLAUDE.md's CPU-only rule for the RL loop; an inference seat is not the RL loop, so a seat
  experiment needs no ruling, while a training use would.
- **Counter.** µs per call at 64, 512 and 2,048 rows on MPS against the traced CPU forward.

**F5. A Python-free evaluator for a Rust tree.**
- **What.** Call the leaf network from Rust without the interpreter: AOTInductor's C++ runner, or Apple's BNNS Graph
  (single-threaded, no allocation during execute).
- **Sources.** [V doc] AOTInductor, §2(a) A9. [V, Apple's CLAIM] BNNS Graph, WWDC24 session 10211 and WWDC25 session 276
  (https://developer.apple.com/videos/play/wwdc2025/276/).
- **Status here.** NEW. It matters only with F6.
- **Gain here.** It removes the whole Python dispatch term, which the trace (A1) only shrinks.
- **Cost.** Days, after F6.

**F6. A Rust tree.**
- **What.** Move tree bookkeeping into the engine crate: multi-parent `expand_nodes` without the GIL,
  `LeafBatch.from_nodes`, `SearchNode.outcome`, then the tree itself.
- **Sources.** [R] DEEP_SEARCH_PATH names these: "`SearchNode.outcome` (~10 lines), a multi-parent `expand_nodes`
  (~200 lines, GIL-free), `LeafBatch.from_nodes` (~50 lines). A Rust tree (~1,000-1,500 lines) is Step C's enabler"
  (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md:81-82`), with review 1's unmeasured estimates of ~3-5k sims/s for
  Python on native against ~5-7k for a Rust tree (`:203-206`). [V code] EfficientZero and LightZero keep batched
  traversal in C++ and only tensors in Python (§2(a) A5).
- **Status here.** PLANNED; nothing built (no engine diff on the branch).
- **Gain here.** At most the Python share of a searched decision, which no measurement separates yet (the brief's ~10%
  is [U]). It also removes the per-edge PyO3 traffic (F7). Rank it after the call-count levers: with the network in
  Python, the network's share is untouched.
- **Cost.** A week or more.
- **Risks.** The later gate "the Rust tree equals the Python tree bitwise under a stub evaluator" (`:106`) is the right
  one. Reinstalling the extension mid-block changes running jobs (`docs/landmines.md:899-951`).
- **Counter.** Gate (ii)'s time split, before and after.

**F7. Per-edge Python and PyO3 traffic in the native tree.**
- **What.** Each new edge makes a `leaves()` call, reads `done`, `outcome` and `turns`, makes two `pending` calls that
  render BOTH seats' views even when one seat decides, clones a node and saves a digest per new child
  (`native_tree.py:162-177`, `:400-441`, `:454`).
- **Status here.** NEW; found by reading (repo inventory B.3 items 7 and 11).
- **Gain here.** Bounded by the Python and engine share. Rendering only the deciding seat's view halves one encode per
  child; batching `leaves()` across a round's edges is F6's `expand_nodes`.
- **Cost.** Hours for the render; F6 for the rest.
- **Counter.** `tree/ms_engine` and gate (ii)'s Python share.

**F8. Preallocated leaf buffers.**
- **What.** `Expanded` allocates fresh vectors per call (`engine/pkmn_gen1/src/search.rs:301-314`) and the row copy
  happens twice (`engine/pkmn_gen1/src/pyencode.rs:321-343`).
- **Status here.** PLANNED in R7's cost section ("preallocated leaf buffers",
  `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:726-727`; asked for in
  `docs/proposals/SEARCH_IN_TRAINING_CHAPTER_2026-09-22.md:876-879`), not done.
- **Gain here.** Small: engine plus tracker is ≤ 0.048 ms a decision (B0). It matters for allocator churn at high
  searched rates, not for speed.

**F9. Quality-of-service and core placement.**
- **What.** Background QoS moves a process onto the E-cores at ~6.8× a decision; plain `nice` does not
  (`docs/landmines.md:687-742`).
- **Sources.** [V doc, a TRAP] NumKong's benchmark guide recommends `taskpolicy -b` "to avoid efficiency cores"
  (https://github.com/ashvardanian/NumKong/blob/main/bench/README.md), the opposite of what this box measured.
- **Status here.** BUILT refusals: the two-core collector and the fleet launchers refuse background QoS, and the P-core
  bench refuses a niced or busy box (`native_tree_gates.py:915-934`).
- **Gain here.** A rule, not a lever. Any new search worker (D1's learner-side variant, C3's server, C4's pool)
  inherits it. Untimed batch jobs such as the oracle reads may use the E-cores on purpose, as the branch's reads did.

## 3. What the literature does that we should NOT copy, and why

1. **Visit-count targets and visit-count play at this budget.** AlphaZero trains on N^(1/τ) after 800 simulations on a
   sharp value network. Here the old tree at 100-900 iterations moved the argmax on only 4-16% of decisions
   (`readouts/TREE_BUDGET_R5_READOUT.md`), and a 256-simulation visit histogram over ~9 rows is coarse. The Q-based
   targets use every evaluated row, and the fixed-point read chose soft_br (B2). Keep `visits` as a parity dial.
2. **A learned model and learned chance codes (MuZero, Stochastic MuZero).** The simulator is exact and forks by
   copying a 384-byte `Battle`. R7's plan lists MuZero under "deliberately not proposed" because "the simulator is exact
   and forkable" (`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md:885-898`). Reanalyze's architecture transfers
   (D1, D2); its dynamics network does not.
3. **Public-belief-state solving (ReBeL, DeepStack, full Student of Games).** Its value network's input grows with the
   number of infostates in a public state, which ReBeL names as its own limit (E6). Here the hidden information is a
   draw from a public pool whose team-structure residual is small in gen 1 (D19), and the observation critic already
   averages over it.
4. **Decoupled UCT with a pure argmax at the root.** UCB selection does not converge at a simultaneous node (Lisý et al.
   2013, already in `docs/prior_work/README.md`), and it measured −0.0041 (z −2.78) against best response to the prior
   here. `tree.py`'s rule stays a parity mode.
5. **Regret matching at every node at a few hundred visits per node.** Convergent in principle; measured −0.0055 (z
   −3.55) at 1,800 simulations here, and Albatross found the same ordering in stochastic two-player Battlesnake (B11).
   Simultaneous AlphaZero's fix is warm-starting, not more cold iterations.
6. **The search root's value, or any max over our rows, as a value target.** The root max carries +0.019 of optimism
   here (G1) and `_look_further`'s row max was a measured cost (`docs/landmines.md:873-898`). v′ is the expectation
   under π′ and the foe prior. MuZero Unplugged also found a 5-step TD target beat direct regression on the search value
   (D4).
7. **Forced playouts, root Dirichlet noise and policy-target pruning as a package.** They exist to make a visit-count
   target explore. With the root grid, Q-based targets and sequential halving they are moot (B3, B4).
8. **Large per-tree virtual-loss batches, and GPU engines' batch sizes.** lc0 allows one collision per batch until a
   tree has 28 nodes, and its self-play caps collision visits at 1; ELF recommends batch 4 at 800-1,600 rollouts (C1).
   Those numbers are per PLAYOUT on GPUs whose cost per row is tiny. On this box the unit is the CALL, and the one paper that compares at
   equal rounds found batching wins with a virtual mean and loses with a virtual loss (Cazenave, C1). Copy the
   principle, not the batch size: batch across trees first (C2, D1), then within a tree with a virtual mean (C5).
9. **Tree reuse between moves as a first-order lever.** In Go and chess the played child is deterministic. Here the
   realised chance outcome and the resampled hidden world make an exact match rare (B15). The value cache (A7) is the
   form that transfers.
10. **Fleets of accelerators.** AlphaZero generated self-play on 5,000 first-generation TPUs and trained on 16
    second-generation TPUs ([V paper] the DeepMind-hosted preprint,
    https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphazero-shedding-new-light-on-chess-shogi-and-go/alphazero_preprint.pdf);
    MuZero used 1,000 TPUs for board-game self-play (https://arxiv.org/abs/1911.08265 App. G); ELF used 2,000 GPUs
    (https://arxiv.org/abs/1902.04522 p.1). What transfers from them is what KataGo showed on ~27 V100s: target
    efficiency and backend engineering, not "more games".
11. **Wall-clock search budgets in instruments.** Foul Play's wall-clock budgets lose iterations under load (0.81× per
    core at 8 arms, `readouts/FP_PARALLEL_ROI_READOUT.md`), and CLAUDE.md retired them for FP@N. Our operators stay
    iteration-bounded in reads (`deadline_ms` = 0); only the ladder seat gets a wall budget.
12. **Other bots' depth as a target.** Wang's ~200 worker-seconds a decision went into 1,000-2,000 shallow determinized
    rollouts bottlenecked by Node (`docs/prior_work/WANG_SEARCH_DEEP_READ.md`). Foul Play's depth claims are its
    author's, unmeasured (E9). Tier 1 says simulations past ~1,800 buy nothing under this critic. What transfers from
    both is spending on the evaluator: rollouts and worlds.
13. **Other projects' per-lever nulls as evidence.** PokaiTrainer's per-lever nulls sit inside its own ±4-6 pp
    resolution, and it started from behaviour cloning on human replays with open team sheets (E9). Wang ran no search
    ablation. None of these bears on a lever here (CLAUDE.md rule 6).
14. **Background QoS "to avoid efficiency cores".** NumKong's benchmark guide recommends `taskpolicy -b`; on this box it
    does the opposite and costs ~6.8× a decision (F9).
15. **The Neural Engine as a per-leaf path.** KataGo's Apple backend uses it as a throughput co-processor behind a
    batching server for convnets; per call it costs 0.2-0.5 ms and serializes (F3).

## 4. Open questions only a measurement on this box can answer

Every item is an analysis job under CLAUDE.md rule 4: run it detached, resume-safe, with progress readable as a rate.
The timed ones (Q1-Q3, Q5, Q13) run at nice 0 on a quiet box after R7's lanes finish, never under background QoS.
Check free disk before any launch (CLAUDE.md). The offline ones (Q0, Q4, Q6-Q12) read banked rows or run untimed and can
use the E-cores.

| # | question | the measurement | decides |
|---|---|---|---|
| Q0 | In R7's two-core lanes, which side binds, and what does the T-op really cost at width 5? | Free and available now: from each lane's offline wandb history, per update, `time/collect_sec`, `time/update_sec`, `search/seconds` and `collect/child_idle_frac`, merged across resumes per the landmine. | D1's variant (in the child or on the learner); §1.3's budget arithmetic |
| Q1 | What are the two terms of a forward, per network, on a P-core? | Gate (ii) as built (`native_tree_gates.py bench`, `2128ae4`), plus a sweep of the W critic and the actor at 1, 8, 32, 64, 128, 512 rows, eager and traced, alone and beside a loaded fleet; the bench's value/prior/engine/Python split. | every [D] in this document; A1's size on the critic; F6's ceiling |
| Q2 | Do concurrent processes contend on the matrix units? | N concurrent single-thread GEMM loops at the critic's value-stack shapes (51-512 rows × 640 → 1024, and 1024 → 1024), N = 1..10, P-cores only; total GFLOP/s against N. Then the same with the real critic forward. | F2; how many searched lanes or seats a box holds; whether A10's NEON leaf is worth building |
| Q3 | What does a compiled or exported forward buy over the trace? | The Q1 sweep through `torch.compile` (inductor CPU, `cpp_wrapper` and `freezing` on), `torch.export` + AOTInductor, ONNX Runtime CPU, Core ML on CPU and on ALL units, and MPS; max \|Δvalue\| against eager and argmax agreement on G0. | A9, F3, F4, F5 |
| Q4 | What batch and in-flight penalty should Step C run? | On G0's roots at 256 sims on the true world: batch 1, 4 and 8, with a virtual loss and with a virtual mean; the fixed-point value at equal SIMS and at equal ROUNDS, at the matched override rate. The arm sets exist (`--arm-set stepc`); add the batch and penalty variants. | C1, C5, Step C's dose line |
| Q5 | Does deferred wide lockstep match the in-line TreeOp and hit the throughput floor? | The same snapshots searched in-line and deferred (targets equal within tolerance), then a 400k smoke of each at Step C's dose: env steps/s, rows per round, `collect/child_idle_frac`, learner idle time. | D1; whether Step C's `frac` floor binds |
| Q6 | How often would a value cache hit, and what does common chance across worlds cost? | Re-run 200 G0 roots with a counting cache: distinct observation digests per decision within a world, across the 8 worlds, and across two consecutive turns. Repeat with chance keyed off the world (A7b), and read the change in Q̄'s variance and the oracle value. | A7, A7b, E3's cost case |
| Q7 | What does skipping confident decisions cost a searched seat? | On G0: the oracle gain of each L-op with and without `top1_skip` 0.97 at the matched override rate; the realised skip share on G2's live rows. | A13 for every future read arm; A14 item 2 |
| Q8 | How much variance does exact or stratified chance remove? | With a `-Dchance`/`-Dcalc` build: per-cell value variance and the oracle gain at equal leaves, stratified crit/hit branches against `chance_k` = 2 samples. | B5 |
| Q9 | What do truncation and control variates do to the rollout leaf? | From Stage 0c's stored rows: the rollout-critic correlation per cell, by turn bucket (the variance cut is its square). A new arm with rollouts cut at 4, 8 and 16 turns and bootstrapped by the critic, at the matched rate. | A14 items 5-7; Stage 1's cost |
| Q10 | Do action-likelihood world weights help? | On G1b's rows, which already hold per-world foe priors: likelihood-weighted PIMC against uniform on the true-world oracle; the weights' effective sample size. | E4 |
| Q11 | Is gen-1 random battles PIMC-friendly, turn by turn? | E2's protocol: disambiguation (log2 consistent foe teams), leaf correlation (winner agreement of two belief worlds played out by the committee) and bias, by turn bucket and unrevealed-mon count. | E2, E3, and a prior for Step C's unresolved fusion read |
| Q12 | Does the foe model's mixing pay? | On G0: the oracle gain with foe nodes at p·prior + (1 − p)·RM for p ∈ {1, 0.9, 0.75, 0.5}, at the matched rate. | E5 |
| Q13 | What does root parallelism over worlds cost on the seat? | 8 worlds on 8 processes against one process at equal total work on 200 G0 roots: ms a decision, and agreement of the pooled root with the single-process one; then the same with the rollout L-op under sequential halving. | C4, and the ladder object's evaluator |

## Appendix. Sources

Each external source once, with how it was read. [V] papers were read as PDF text; arXiv PDFs came from the Kaggle
arXiv mirror (`https://storage.googleapis.com/arxiv-dataset/arxiv/arxiv/pdf/<yymm>/<id>v<N>.pdf`) because arxiv.org
is blocked here, and the version read is named. Code and docs were read at the commit given.

**The AlphaZero family and its engineering**

| source | URL | read | used in |
|---|---|---|---|
| AlphaGo Zero, Silver et al. 2017 | https://www.nature.com/articles/nature24270 | [V] a copy of the published PDF | A8 |
| AlphaZero, Silver et al. 2018, the preprint with supplementary tables | https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphazero-shedding-new-light-on-chess-shogi-and-go/alphazero_preprint.pdf | [V] | §3 item 10 |
| MuZero, Schrittwieser et al. 2020 | https://arxiv.org/abs/1911.08265 | [V] v2 | B14, D2, §3 |
| MuZero Unplugged / Reanalyse, Schrittwieser et al. 2021 | https://arxiv.org/abs/2104.06294 | [V] v1 | D2, D4 |
| Sampled MuZero, Hubert et al. 2021 | https://arxiv.org/abs/2104.06303 | [V] v1 | B9 |
| Gumbel MuZero, Danihelka et al. 2022 | https://openreview.net/forum?id=bERaNdoegnO | [U] unreachable; its reference code, mctx, read instead | B1, B2 |
| Stochastic MuZero, Antonoglou et al. 2022 | https://openreview.net/forum?id=X6D9bAHhBQ1 | [U] unreachable | B5 |
| Student of Games, Schmid et al. 2023 | https://arxiv.org/abs/2112.03178 | [V] v2 | D5, E6, E8 |
| mctx | https://github.com/google-deepmind/mctx | [V] code at `88f9205` | A5, B1, B2, B4 |
| KataGo, Wu 2019 | https://arxiv.org/abs/1902.10565 | [V] v5; hardware ~27 V100s | B3, D3, D8, D11 |
| KataGo repository and docs | https://github.com/lightvector/KataGo | [V] code and docs at `7c42e21` | A7, A13, B2, B3, B4, B6, B8, B12, B13, C1, C2, D3, D7, D8, F3 |
| Leela Chess Zero and its wiki | https://github.com/LeelaChessZero/lc0 | [V] code at `1227b4c`; wiki at `39ebcef` | A7, A9, A13, B7, B15, C1 |
| Leela Zero, batching issue | https://github.com/leela-zero/leela-zero/issues/1601 | [V] GTX 1080 Ti | C2 |
| ELF OpenGo, Tian et al. 2019 | https://arxiv.org/abs/1902.04522 | [V] v5; 2,000 GPUs | C1, §3 |
| ELF batch-size issue | https://github.com/pytorch/ELF/issues/25 | [V] maintainer's answers | C1, C2 |
| Polygames | https://github.com/facebookincubator/Polygames | [V] README | C2 |
| MiniZero, Wu et al. 2024 | https://arxiv.org/abs/2310.11305 | [V] v3; 4× GTX 1080 Ti | B1, B2, D11 |
| EfficientZero, Ye et al. 2021 | https://arxiv.org/abs/2111.00210 ; https://github.com/YeWR/EfficientZero | [V] v2; code at `468bb03` | A5, C8, D2, D4 |
| EfficientZero V2, Wang et al. 2024 | https://arxiv.org/abs/2403.00564 | [V] v2; 8× RTX 3090 | D4 |
| LightZero, Niu et al. 2023 | https://arxiv.org/abs/2310.08348 | [V] v1; 1 A100 + 24 cores | B1, C2, C6 |
| ReZero | https://arxiv.org/abs/2404.16364 | [V] v5; 1 A100 + 30 cores | C8, D2 |
| muzero-general | https://github.com/werner-duvaud/muzero-general | [V] code at `0825bd5` | D2 |
| OpenSpiel AlphaZero | https://github.com/google-deepmind/open_spiel | [V] code at `4840189` | A7 |
| alpha-zero-general | https://github.com/suragnair/alpha-zero-general | [V] code at `f1a78e0` | A7 |
| MCTS as regularized policy optimization, Grill et al. 2020 | https://arxiv.org/abs/2007.12509 | [V] v1; 4-8 V100s | B2 |
| On the role of planning, Hamrick et al. 2021 | https://arxiv.org/abs/2011.04021 | [V] v2 | B14 |
| V-MCTS, Ye et al. 2022 | https://arxiv.org/abs/2210.12628 | [V] v1 | B7 |
| Expert Iteration, Anthony et al. 2017 | https://arxiv.org/abs/1705.08439 | [V] v4 | A10, B2, C5 |
| Policy distillation, Rusu et al. 2016 | https://arxiv.org/abs/1511.06295 | [V] v2 | A10 |
| TreeStrap, Veness et al. 2009 | https://proceedings.neurips.cc/paper/2009/file/389bc7bb1e1c2a5e7e147703232a88f6-Paper.pdf | [U] unreachable, not on the mirror | D5 |

**Parallel search, caches and graphs**

| source | URL | read | used in |
|---|---|---|---|
| Batch Monte Carlo Tree Search, Cazenave 2021 | https://arxiv.org/abs/2104.04278 | [V] v1; RTX 2080 Ti | C1, C5, §3 |
| WU-UCT, Liu et al. 2020 | https://arxiv.org/abs/1810.11755 ; https://github.com/liuanji/WU-UCT | [V] v5; Xeon + RTX 2080 Ti | C3, C5 |
| Parallel MCTS, Chaslot et al. 2008; lock-free trees, Enzenberger & Müller 2010 | via Mirsoleimani et al., https://arxiv.org/abs/1605.04447 and https://arxiv.org/abs/1409.4297 | [V2] | C4 |
| MCTS survey, Świechowski et al. | https://arxiv.org/abs/2103.04931 | [V] v4, for Sephton et al. 2014 and ISMCTS | C4, E3 |
| Monte-Carlo Graph Search, Czech et al. 2020 | https://arxiv.org/abs/2012.11045 | [V] v1 | B6 |
| Ray Serve dynamic batching | https://github.com/ray-project/ray/blob/master/doc/source/serve/advanced-guides/dyn-req-batch.md | [V] doc | C3 |
| ipc-bench | https://github.com/goldsborough/ipc-bench | [V] README at `589146a`; x86 Linux | C3 |

**Imperfect information and simultaneous moves**

| source | URL | read | used in |
|---|---|---|---|
| Frank & Basin 1998, strategy fusion and non-locality | via Cazenave & Ventos, https://arxiv.org/abs/1911.07960 | [V2] | E4 |
| Long et al. 2010, when PIMC works | https://ojs.aaai.org/index.php/AAAI/article/view/7562 | [V2] via Rubin 2026; numbers [U] | E2 |
| Unsound search in LoCM, Rubin 2026 | https://arxiv.org/abs/2609.06816 | [V] v1; A10G | E2 |
| ISMCTS, Cowling et al. 2012 | via https://arxiv.org/abs/1807.06813 and the survey above | [V2]; results [U] | E3 |
| MAPLE, Li et al. 2026 | https://arxiv.org/abs/2605.24139 | [V] v1 | E1, E3 |
| Smooth UCT, Heinrich & Silver 2015 | https://www.ijcai.org/Proceedings/15/Papers/084.pdf | [U] abstract | E8 |
| SM-MCTS convergence, Lisý et al. 2013 | https://arxiv.org/abs/1310.8613 | [V] v2; already in `docs/prior_work/README.md` | B11, §3 |
| Albatross, Mahlau et al. 2024 | https://arxiv.org/abs/2402.03136 | [V] v2 | B11, E5 |
| Simultaneous AlphaZero, Becker & Sunberg | https://arxiv.org/abs/2512.12486 | [V] v2 | B11 |
| Restricted Nash Response | via Ponsen et al., https://arxiv.org/abs/1401.4591 | [V2] | E5 |
| POMCP, Silver & Veness 2010 | https://papers.nips.cc/paper/4031-monte-carlo-planning-in-large-pomdps | [U] | E4 |
| DeepStack, Moravčík et al. 2017 | https://arxiv.org/abs/1701.01724 | [V] v3; one GTX 1080 | E6 |
| ReBeL, Brown et al. 2020 | https://arxiv.org/abs/2007.13544 ; https://github.com/facebookresearch/rebel | [V] v2; code at `7960a42` | E6 |

**Pokémon agents**

| source | URL | read | used in |
|---|---|---|---|
| Foul Play | https://github.com/pmariglia/foul-play | [V] code at `6c467c0` and the project pin `25c976f` | C4, E1, E9 |
| poke-engine | https://github.com/pmariglia/poke-engine | [V] code at `bcf1382` (v0.0.48) and `f4e224c` | B5, E9 |
| PokéChamp, Karten et al. 2025 | https://arxiv.org/abs/2503.04094 ; https://github.com/sethkarten/pokechamp | [V] v1; code at `0f84c46` | E9 |
| Athena, Sarantinos | https://arxiv.org/abs/2212.13338 | [V] v2 | E9 |
| PokaiTrainer, Yu 2026 | https://arxiv.org/abs/2608.29197 | [V] v1; 10 shared L40S, ladder on an RTX 4090 | E5, E9, §3 |
| Wang 2024, MIT MEng thesis | https://dspace.mit.edu/handle/1721.1/153888 | [V2] via `docs/prior_work/WANG_SEARCH_DEEP_READ.md` | A14, B15, E5, E9 |
| pkmn.ai project catalogue | https://github.com/pkmn/ai | [V2] `static/projects.yml` | E3, E9 |

**Runtime and hardware**

| source | URL | read | used in |
|---|---|---|---|
| PyTorch 2.13.0 sources (wheel flags, BLAS, inductor, quantization) | https://github.com/pytorch/pytorch/tree/v2.13.0 | [V] | A1, A9, A11, F2 |
| PyTorch tutorials (ensembling, real-time inference, AOTInductor) | https://github.com/pytorch/tutorials/tree/65e2e1a | [V] | A1, A4, A9, F1 |
| PyTorch per-op overhead issue | https://github.com/pytorch/pytorch/issues/41383 | [V]; hardware not stated | §1.2 |
| Hello SME, Remke & Breuer 2024 | https://arxiv.org/abs/2409.18779 | [V] v1; base M4 | A11, F2 |
| M4 SME exploration | https://github.com/tzakharko/m4-sme-exploration | [V] reports at `089ceeb` | §1.2, F2 |
| LOOPS | https://arxiv.org/abs/2511.08158 | [V] v2; M4 Pro | F2 |
| Apple Neural Engine monograph, Bryngelson | https://arxiv.org/abs/2606.22283 | [V] v1; M1 | F3 |
| Core ML path latency, Shahir | https://arxiv.org/abs/2608.22110 | [V] v1; M1 | F3 |
| KataGo Metal backend PR | https://github.com/lightvector/KataGo/pull/1148 | [V] PR text; M3 Max | F3 |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | [V] docs and `mlas.h` | A9 |
| coremltools docs | https://github.com/apple/coremltools/tree/db4dd46 | [V] | F3 |
| BNNS Graph, WWDC24 and WWDC25 | https://developer.apple.com/videos/play/wwdc2024/10211/ ; https://developer.apple.com/videos/play/wwdc2025/276/ | [V] Apple's claims | A9, F5 |
| NNUE docs | https://github.com/official-stockfish/nnue-pytorch/blob/aa2fff2/docs/nnue.md | [V] | A10 |
| QuaRL, Krishnan et al. | https://arxiv.org/abs/1910.01055 | [V] v6 | A11 |
| NumKong benchmark guide | https://github.com/ashvardanian/NumKong/blob/main/bench/README.md | [V], cited as a trap | F9, §3 |
| Git Re-Basin, Ainsworth et al. | https://arxiv.org/abs/2209.04836 | [U] not read | A15 |

**Repo sources, most cited.** `readouts/R7_B0_BENCH.md`, `readouts/R7_G0_READOUT.md`, `readouts/R7_G2_READOUT.md`,
`docs/engine_port/NOTES.md:2169-2225`, `docs/proposals/STEP_C_PREREG_DRAFT_2026-09-26.md`,
`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md`, `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`,
`docs/IDEAS_POST_100M.md`, `docs/CLEANUP.md`, and SESSION_LOGS 2026-09-25 07:28Z to 2026-09-26 10:30Z on main. The
branch's commits are named where used; its reads' raw results live in the gitignored `results/native_tree/`.

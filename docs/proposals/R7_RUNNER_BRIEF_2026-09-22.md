# R7 runner brief — for the box session that takes the native-search chapter from here

**Written 2026-09-22 by the cloud session that authored the R7 plan, at the maintainer's
request.** The plan itself is `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`
(RATIFIED, six rulings; frozen at amendment box 3 until G0 reads). This brief is the
operational layer: what to do first on the maintainer's box, in what order, under which
constraints. It adds no new claims. On conflict, the plan wins, then `CLAUDE.md`.

## 0. Read order, then a health check

1. `CLAUDE.md` (binding), `HANDOFF.md` (the R6 handoff — still live, still yours to
   respect), `STATUS.md`.
2. The plan, in full, including the three amendment boxes at the top. Then
   `docs/proposals/SEARCH_IN_TRAINING_CHAPTER_2026-09-22.md` (SUPERSEDED; its REPLY BOX 2
   holds the B0 bench spec, the B5 test designs and the G3 sign-off conditions verbatim).
3. `docs/search_relook/ENGINE_SEARCH_DESIGN.md` §4 (the batched leaf path and cost model)
   and §2–§3 only when B6 starts.
4. Health: `git status` clean; no OTHER live Claude process in this tree
   (`ps -axo pid,etime,command | grep -i claude`); the exit-gate queue's state
   (`tail -5 logs/exit_gate_r5/queue.log`); `showdown/config/config.js` `simulator: 4`.

## 1. Two constraints that decide HOW you work

- **A RUNNING BLOCK IMPORTS THE WORKING TREE** (`CLAUDE.md` landmines). The exit-gate
  queue launches each arm as a fresh process from the main checkout. **Never edit `rl/`,
  `scripts/` or `engine/` in that checkout while any queue or fleet is running.** Work in
  a git worktree (`docs/engine_port_session_brief.md` §1.1 is the precedent), merge to
  `main` only between blocks, and stamp `launch_git_sha` on everything you run.
- **The engine extension lives in the `pkmn-engine-port` conda env only** (rule 1).
  **CORRECTED 2026-09-22 by the box session — this brief inherited rule 1's inversion,
  fixed in `CLAUDE.md` and `docs/engine_port_session_brief.md` at commit 0f406bb: the env
  THE LIVE LANES RESUME INTO IS `pkmn-engine-port`, NOT `pokemon-showdown-rl`.**
  `scripts/monster_fleet.sh` line 43 defaults `PY` there and `scripts/train_watchdog.sh`
  inherits it for every resume, because `engine` collection needs `pkmn_gen1`, which only
  that env has. **So B0 MUST NOT be built or installed into `pkmn-engine-port` while an
  R6 lane is live.** Already-running lanes hold their mapped `.so` and are safe, but a
  lane the watchdog RESUMES imports whatever is on disk — a rebuilt or half-built
  extension means a resumed lane runs a different engine than it launched with, at best a
  provenance break across the fleet and at worst an import death after 50 h of training.
  B0 therefore waits for the R6 fleet to finish, or is built in a FRESH env of its own
  (`pkmn-engine-port2`) whose extension no live lane can reach. Python-side work (B1, B2,
  B5) that does not touch the extension runs in `pokemon-showdown-rl`; tests that need
  both run per CLEANUP.

## 2. Sequencing against what is already running or ratified

| what | state | your obligation |
|---|---|---|
| Exit-gate queue (XGR → XTG9 → READOUT) | running or done; see `HANDOFF.md` §1 | bank the readouts per `HANDOFF.md` §3 item 1 when they land; **its verdict is scoped to the tree-on-PPO-critic operator (ruling 2) and does not decide R7** |
| R6 prep (`HANDOFF.md` §3 items 2–7) | ratified, in order | unchanged; the 4.12 screen and the R6 fleet run as written; **no R7 job beside an FP arm**, and R7 engine-only jobs run niced beside the R6 fleet only if their CPU share is disclosed |
| R7 builds B0–B3 | not started | start now, in the worktree, between the queue's blocks |
| G0 | not started | after B0–B2; agent-side (eval/analysis: detached, resume-safe, rate-readable — rule 4) |
| B4–B6, G1–G4, the fleet | gated on G0 | the fleet is > 5 h → the maintainer launches |

## 3. Pending ruling — ask in your first message, default if unanswered

**Ruling 7, fleet width:** 5 lanes × 2 cores on the ten performance cores (recommended),
or 6 lanes with a pre-registered disclosure that one runs degraded on the efficiency
cores (`docs/landmines.md:614-626`, 6.8×). **Default to 5** until the maintainer says 6.

## 4. The first four builds, with their acceptance

**B0 — the batched leaf path** (`engine/pkmn_gen1`, Rust, `pkmn-engine-port` env; design
§4.1's `SearchNode.expand`): clone → CRN seed at `B_RNG` keyed on `(decision, col, world,
sample)`, never the row → `update` → tracker observe → encode BOTH seats' observations
(the antisymmetric second view is on by default) → chunked at 4,096 rows, GIL released.
**Acceptance = the bench that replaces §5's constants**, per the imported REPLY BOX 2's
spec: run at fleet width (five- and six-wide, never solo), `torch_threads: 1`, both views
on, p99 not mean, the four components separated (engine+tracker, encode, critic forward,
PyO3+numpy glue), pass condition pre-stated at 2× the plan's table (≤ 3.6 ms per 40-leaf
decision at p99). Commit the bench output as `readouts/R7_B0_BENCH.md`. **If it fails
2×, stop and report: the T-op is a lane, not a fleet, and the plan's §5 must be rewritten
before B4.**

**B1 — `scripts/rollout_q.py`** (the I-op instrument, G0's engine): positions sampled
from R5-final self-play on the engine, stratified by turn bucket; full row × column
matrix; 256 rollouts per cell **split 128/128** with CRN across rows; both seats
stochastic. Columns per the plan's §6 as amended: `regret_depth1_ceiling` (split-sample,
with the permuted-split zero-gap null), `regret_critic_depth1`, `spearman` for the
observation critic AND the privileged critic AND `root_q_depth1`, `opp_model_gap`,
`opp_best_outside_topk[k]` for k ∈ {2,3,4}, `fusion_flip` / `fusion_bound` (needs B1b).
Resume-safe rows file; a VERSION MARKER in the JSON (the skip-guard landmine); every
threshold on the WIN-RATE scale, printed with its scale. **B1b:** the engine→engine
resample — `pkmn_gen1.BattleSpec::from_visible(b)` (`engine/pkmn_gen1/src/spec.rs:756`)
plus the determinizer's hidden-slot fill ported from `rl/search/determinize.py` onto the
spec → `build()`. Not the poke-env bridge; that is B6 and it waits.

**B2 — the antisymmetric critic:** `V := ½(f(obs₁) − f(obs₂))` in
`rl/networks/entity_deepsets.py`, both views supplied by the engine collector (and by
B0 at leaves); the privileged 408-block stays an option behind its existing kwarg
(`:348-353`). Tests: `V(swap(s)) == −V(s)` BITWISE; a checkpoint without the second
view still loads; actor param count unchanged (`ACTOR_PARAM_CEILING` untouched).

**B3 — `rl/search/native.py::solve`** (the operator): rows = our legal actions, columns
= the opponent's top-k legal actions by `π_opp` (k from G0's `opp_best_outside_topk`
read, never typed), chance S samples, leaves through B0, root = `π'(a) ∝ π_θ(a) ·
exp(Q̄(a)/τ)` with `Q̄` under the opponent's prior policy (the value estimand, amendment
2 item 3); returns `π'`, `Q̄`, `v'`, counters. **Dial list derived from the signature;
unknown keys hard-fail. Golden test on fixed roots** (`tests/test_tree_decision_golden.py`
is the pattern). Counters to disk before any dial gets an arm.

Then **G0** as the plan's §6 specifies, agent-side, detached, resume-safe, rate against
the ~2–4 core-hour estimate. Readout `readouts/R7_G0_READOUT.md` with every number
traced to its rows file, the zero-gap null beside the estimate, and the branch taken
stated in the plan's words.

## 5. What you do not do

- No search on the R6 ladder object and no R7 number beside a pure-lane number without
  saying so (JOURNEY 14's bar).
- No 12M win-rate A/B anywhere in this chapter (rule 6); G3 reads mechanism only.
- No edits to `HANDOFF.md`'s R6 content except to fold in what lands; no rewrite of any
  amendment box (append a dated box 4 if something must change).
- No `taskpolicy` on anything whose timing will be quoted (`docs/landmines.md:614-626`).
- Commit small and often; **push only when the maintainer says push**, except for the
  end-of-block push the maintainer's launch instruction already authorises.

# R7 — the native-search chapter: turn the engine into supervision (written 2026-09-22)

**Status: RATIFIED — all six §9 rulings taken by the maintainer 2026-09-22 ("agree with all"). A plan, not a pre-reg.** Nothing here credits anything.
Every arm that becomes a headline number or a ladder object gets its own config header
under the standing rules before it runs. Numbers are traced in place; session-scoped
measurements that never reached a committed file are marked as such.

**Journey position.** This is **JOURNEY 14** (the strength chapter: *"search over OUR OWN
value function"*, `JOURNEY.md:149-196`) opened early, plus **IDEAS 4.9** (expert iteration)
on a different operator than the one its gate is testing. JOURNEY 14 is written as
"after the story is wrapped". The maintainer's ask of 2026-09-22 — *keep pushing to the
top, no human data, anything else on the table, no incremental gains* — is the ruling
that opens it; §9 lists that ruling explicitly. **R6 is not touched** (§8).

**The maintainer's brief, restated.** Top ~200 today (R5: GXE 73.9, Glicko 1697 ± 25,
`readouts/LADDER_R5_READOUT.md`). The next bracket is the board's p90: **GXE 82.3,
Glicko 1794** (gen1RB top-500 list pulled 2026-08-25, `docs/prior_work/README.md`; best
93.5 / 2022, list median 75.0 / 1712). So the target is roughly **+8 GXE / +100 Glicko**,
on a 14-core laptop, CPU only, pure self-play.

> ### AMENDMENT BOX — 2026-09-22, folded from the teammate's `SEARCH_IN_TRAINING_CHAPTER_2026-09-22.md`
> (branch `claude/search-in-training-proposal`, commit `757c4f0`). Recorded as an amendment, not
> a rewrite, so the original text stays auditable. Six items adopted; two rejected with reasons.
> 1. **Behaviour log-prob from `π'`, pinned by a test.** §4 item 1 plays the sampled `π'` action
>    and stores `log π'(a)`. A ratio computed against `π_θ`'s log-prob on those rows is a SILENT
>    corruption: `approx_kl` and `clip_frac` will not flag it. Test: a searched batch with `π' ≠
>    π_θ` must produce ratio 1.0 at the first epoch.
> 2. **The search value starts as an AUXILIARY head, not a GAE blend.** Searching ~40% of
>    decisions and blending `v'` only there puts an offset across the searched/unsearched
>    boundary that GAE straddles on most transitions. Our `v'` is a one-step Bellman backup of the
>    same critic, so the offset should be small — but that is a prediction, and `search/value_gap`
>    is the measurement. §4 item 3 is amended: auxiliary head first (the 4.11 pattern, `forward`
>    unchanged, GAE untouched); the blend is a later dial, promoted only after `value_gap` reads.
> 3. **The value estimand is named.** The target `v'` is the expectation under the OPPONENT'S
>    PRIOR POLICY (columns weighted by `π_opp`), which is §27's oracle estimand (the committee
>    rolled out on both seats). The mixed-strategy root (P4) decides the ACTION only. A minimax
>    root value (the tree's `puct` default) is a different, pessimistic estimand and is never the
>    critic's target.
> 4. **Two samplers.** The policy target may use a contested-state selector; the value target
>    uses a COIN, because a biased sampler biases the critic's training distribution — the defect
>    §31 measured. Both rates are dials to disk.
> 5. **Stage 0B is adopted and runs first, free:** across banked finals with FP@20 / vs-SH
>    numbers, regress strength on the turn-2–8 r² bucket. If it does not correlate, that bucket
>    is uninterpretable as a mechanism co-primary — for G3/G4 here AND for R6 trio A, which is
>    already ratified on it. Owed to R6 regardless of this chapter.
> 6. **The purity clause needs a TEXT amendment.** RESULTS §1 defines a pure run by three
>    sources (init, self-play experience, the environment). Search inside training adds the
>    engine's forward model and the generator prior. Ruling 4 covers the spirit; the enforceable
>    clause is edited before any R7 number lands, and the amendment says what it admits (the
>    game's own rules and the format's own generator) and what it still excludes (any external
>    policy, tape or evaluator).
>
> **Rejected, with reasons.** (a) The L6 column-abstraction concern about an equilibrium solve
> does not apply: our columns are the opponent's actual legal actions in the determinized world,
> top-k by `π_opp`, so the ≤9×k solve is over the real game. (b) Its cost model (tens of server
> hours per 10⁴ labelled states, 766.6 ms/decision) prices the poke_engine Python tree; the
> native operator is ~1 ms/decision with no server (§5), so its Stages A–B are not adopted as
> written. Its Stage 0A (root value vs oracle r²) is subsumed by G0, which measures the same
> quantity against a 256-rollout oracle on the engine.

---

## 0. The bet in one paragraph

Every lever this project has pulled feeds the network **one outcome bit per ~30
decisions, 64% of it noise** (RESULTS §27: irreducible 0.6366). Dose is flat
(+0.001 on the committee 50M→100M, plan §1), width buys zero explained variance
(§21), and the format's own arithmetic caps the label rate at **5.6 bits per parameter
against AlphaZero's ~610** (`docs/research_reports/MODEL_SCALE_2026-09-12.md:238-240`).
AlphaZero closed that gap with one device: **search over an exact simulator turns
compute into supervision** — a full improved distribution and a backed-up value per
position instead of one noisy outcome per game. This repo now owns that simulator:
`pkmn/engine` clones a battle in a 384-byte memcpy and steps a leaf in **5.7 µs**
including the training encoder (`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §4.2).
Nothing in the training loop uses it for anything but collection. **The plan is to
build ONE search operator on that engine and use it in three places: at the ladder
(the unspent 150 s/turn), inside training (expert iteration), and as the instrument
that measures both.** The evaluator at its leaves is the **privileged critic**, which
is the right object for determinized search and has never been used as one.

## 1. Why the search chapter read as a cost, and why that does not bind here

RESULTS §30 is a real, measured cost: greedy 0.6050 tops every search arm, depth-1
−0.052 at 2.4 se, and the deficit grows with the override rate (−0.48 per unit,
r −0.875). Read what was measured:

1. **The leaf evaluator was PPO's baseline, not an evaluator.** It is trained on the
   states the actor visits, against single-outcome GAE targets, and it adds **+0.059
   to whichever seat it looks at** (§31: its league's mean return). It has never been
   trained on a counterfactual successor state, which is the only kind of state a
   search asks it about. Its ranking r² is **0.2176 against a 0.3630 ceiling** for an
   observation-only reader, and worst in the opening (0.287 at turns 2–8, §27.1).
2. **The leaves were rendered through a different path than training.** Every search
   arm runs on `poke_engine` + the Python encoder, while the W lanes trained on
   `pkmn_gen1` + the Rust encoder. The `col_views` vs `view=None` rendering difference
   alone **flips 10.76% of argmaxes** (§26.1). A critic read off-distribution at every
   leaf is a different critic.
3. **The budgets were tiny and the vehicle was Python.** Depth-1 at 81.7 ms, the tree at
   900 iterations at 766.6 ms per decision (RESULTS :1880, :2706-2711), against a
   ladder that allows ~150 s. The action-gap instrument that is supposed to bound the
   prize ran **24 rollouts per position** and carries per-position noise of 0.204 on a
   mean gap of 0.181 (`HANDOFF.md` §1) — it cannot resolve the thing it bounds.
4. **Depth-2 had a specific optimism defect** (`_look_further`, fixed 2026-09-18) and
   every pre-fix number carries it.

None of those four is a property of search; each is a property of the objects it was
tried with. The only operator-level fact that survives is the one this plan is built
around: **the search's value is exactly the leaf evaluator's ranking quality, so the
evaluator is the object.**

**The running exit gate (XTG9, tree@900 vs greedy) does not decide this plan.** It
measures the Python tree over the observation-only PPO critic at inference. Its verdict
rule closes 4.9 "on this object"; §9 asks the maintainer to scope that closure to the
tree-on-PPO-critic operator, because the operator below differs in evaluator, simulator,
root rule and cost by an order of magnitude each, and its own kill is §6's G0.

## 2. Four principles the operator is built on

**P1 — Expand the first ply exactly; that is where arithmetic lives.** Whether Body
Slam + Hyper Beam KOs Chansey from 78%, who moves first at a speed tie, what a crit
does — a 626k-parameter feed-forward net approximates these; the engine computes them.
Foul Play's entire strength is exact expansion over a crude evaluator, and it scores
0.904 vs SH in gen 4 where our 50M policy scores 0.879 (`JOURNEY.md` §14). Our
committee beats FP@500 at 0.5600 (`readouts/FP500_R5_READOUT.md`) — a better evaluator
under a cruder expansion. The combination has never been run on a consistent evaluator.

**P2 — The privileged critic is the right evaluator for determinized leaves.** A
determinized leaf is a COMPLETE state: the sampled world has an opponent team, movesets,
exact HP. An observation-only critic throws that away and then has to marginalise over
a bench it could read. The D18 privileged form already exists in the net
(`rl/networks/entity_deepsets.py:340-352`, the 408-block appended to the obs) and the
engine constructs the block at training time (`env.rs:295-302`); the design's leaf path
renders it for search leaves at ~1.5× the base leaf cost (ENGINE_SEARCH_DESIGN §4.1).
D18's −0.0145 at 12M measured it as a **baseline**, was vacated as dose-limited, and
never asked it to be an evaluator. Two properties come with it:
- **Antisymmetry by construction.** `V(s) := ½ (f(state as seat 1) − f(state as seat 2))`.
  Both views are renderable from a complete state, so §31's +0.059 vanishes as an
  identity, not as a regulariser.
- **Hidden information is nature's, not the opponent's.** D19 measured the set pool at
  0.024–0.034 nats of residual belief, 88–90% of it a deterministic cap mask
  (`docs/prior_work/README.md`). Perfect-information Monte Carlo over sampled worlds is
  the right approximation for nature-drawn hidden state; the strategy-fusion error at
  depth 1 is second order.

**P3 — At training time the true world IS a posterior sample.** In self-play the
opponent's team is drawn by the generator; conditioned on everything the acting seat
has observed, the true hidden state is distributed exactly as the posterior. So a
search over the true world, averaged over episodes, teaches the student
`E_world~posterior[π_search(obs, world)]` — the same object a belief-sampled search
computes at inference, at one determinization instead of B. **No belief sampler is
needed to train**; it is needed only at the ladder, and `rl/search/determinize.py` +
`pkmn_gen1.BattleSpec` already exist for that.

**P4 — The root of a simultaneous-move game is a matrix game, not an argmax.** The
locked protocol's deterministic argmax is what §28 measured looping and what a 1400+
human can read. The operator returns a **regularised mixed strategy at the root**:
`π'(a) ∝ π_θ(a) · exp(Q̄(a)/τ)` with `Q̄(a) = Σ_b q(b) Q(a,b)` over the opponent's
policy-weighted replies (Gumbel-MuZero's improved policy; a full zero-sum LP over the
≤9×k matrix is the alternative and costs nothing at this size). The prior term is the
trust region that CH3 R5's hard-argmax distillation (−0.0545, RESULTS :696, PRE-D5) did
not have.

## 3. The object: ONE operator, three uses

`rl/search/native.py::solve(root_bytes, seat, prior, worlds, cols_k, chance_S, depth, tau)`
on `pkmn_gen1`, batched (`SearchNode.expand` as specified in ENGINE_SEARCH_DESIGN §4.1;
CRN-1 seeds keyed on `(decision, col, world, sample)`, never the row). Returns `π'`,
`Q̄`, the root value `v'`, and the counters (`search/override`, `search/kl_prior`,
`search/margin`, `search/leaves`, `search/ms`) — **counters to disk before any dial gets
an arm; the dial list is derived from the function's signature and unknown keys hard-fail**
(the typed-list landmine).

| use | worlds | leaves/decision | evaluator | budget | who consumes `π'` |
|---|---|---|---|---|---|
| **T-op** (training, in the engine collector) | 1 = the true state (P3) | ~6.7 rows × 3 cols × 2 chance ≈ **40** | privileged critic, current weights | ~1–1.5 ms | behaviour policy samples from `π'`; learner gets `π'`, `v'` |
| **L-op** (ladder / evals) | B = 8 sampled | 6.7 × 4 × 8 × 8 ≈ **1,700** at depth 1; ×~75 at depth 2 | privileged critic on each world, averaged | 30 ms depth-1, ~2.5 s depth-2 | the played mixed action; greedy is the disclosed fallback |
| **I-op** (instruments) | 1 = true | full matrix × **256 rollouts per cell** under the stochastic π, both seats | none — the rollouts ARE the value | ~2–4 s/position | §6's G0 |

The rollout leaf (I-op) deserves its own line: it is the backgammon "rollout" — the
gold-standard evaluator in a dice-dominated game because the luck averages out and
there is no critic to be wrong. It is too slow to train on and too slow for the ladder
at full dose, but it is exactly the oracle that says whether the critic ranks successors
and how much decision quality the greedy policy leaves on the table. At the ladder it is
also a cheap cross-check on close calls (a few hundred rollouts inside the 150 s).

## 4. The learner: PPO plus search targets (expert iteration, affordable form)

Keep `PPOAgent`, the snapshot pool, the anneal, the W recipe. Add, on searched rows:

1. **Behaviour = `π'`.** The collector samples the played action from `π'` and stores
   `log π'(a)` as the behaviour log-prob; PPO's ratio handles the one-update staleness
   exactly as it does today for the pool.
2. **Policy loss toward `π'`:** `β · KL(π' ‖ π_θ)` masked through `rl/common/masking`,
   logged as `loss/search_policy` from the update. Soft target, never the argmax
   (`docs/prior_work/DISTILLATION_OBJECTIVES.md`: soft vs hard is +50 Elo at equal agreement).
3. **Value target:** `v'` (the root's expectation under the opponent's prior policy —
   amendment 3) trained through an AUXILIARY critic head first (amendment 2), logged as
   `loss/search_value`, with `search/value_gap = |v' − GAE|` as the read; the GAE blend
   `V_target = (1−w)·GAE + w·v'` is a later dial, promoted only after `value_gap` reads.
4. **The critic is privileged and antisymmetric (P2)** — it is the same network the T-op
   evaluates leaves with, so the loop is self-consistent: successors the critic overrates
   get played, visited and corrected. Underrated ones are the exploration problem, which
   the prior term and entropy own.
5. **The 4.11 outcome heads ride on the same critic** (built data path; the heads are
   R6 trio A's build) — no conflict, one more target.

**Which decisions get searched.** Two samplers (amendment 4): the value target's rows are
a coin; the policy target's rows may be contested-state selected. Not forced moves (one legal row), not decisions where
`π_θ` top-1 ≥ 0.97 — measure the fraction on the R5 finals first (§32: mean
`pi_top1` 0.885, so a large share is confident). Pre-decide the fraction as a DOSE and
match it across arms; a pre-stated fallback is "search where the policy's top-2 margin
is below the median", which is IDEAS 8.5's selector with a measurable rate.

## 5. Cost, on this box, traced

Constants: engine + tracker + Rust encoder **5.7 µs/row** batched; critic forward
**1.1–1.5 µs/leaf at 4 threads** (both session measurements in ENGINE_SEARCH_DESIGN
§4.2, **not in any committed result file** — this plan budgets **10 µs/leaf
single-threaded** until B0's bench pins it); collection **34.9% of wall** at k=8 with
the Rust side ≤ 8.7% of that; **1,282 sps/lane** six-wide (`docs/engine_port/SPEEDUP.md`);
greedy collection ≈ **0.15 ms/decision** in its phase; box **M4 Pro 14 cores / 24 GB**,
per-lane RSS **1.825 GB**, the mmap'd team bank returns **2.7 GB** at width 6
(`configs/showdown_monster200m_w.yaml:686-712`).

| | per decision | vs greedy collection |
|---|---:|---:|
| T-op, 40 leaves | 0.23 ms engine + 0.4 ms critic + ~0.5 ms glue ≈ **1.2 ms** | **~8×** |
| T-op on 40% of decisions | mean **0.6 ms** | **~4×** |

Synchronous, one core per lane: wall = 0.65T (update) + 4 × 0.35T = **2.05T**, i.e.
~2× slower per step. **The fix is structural and cheap: give each lane a second core
for an asynchronous collector.** Six lanes use twelve of fourteen cores instead of six;
memory is 6 × (1.825 + ~0.6) ≈ 14.6 GB, inside the 24 GB with the mmap unlock in hand.
Then wall = max(0.65T, 1.4T) = **1.4T** at 40% searched, and with R6 trio B's epochs-2
update the learner is no longer the bottleneck at all. **A 100M ExIt lane ≈ 30 h; a
60M lane ≈ 18 h.** The fleet comparison is therefore **matched on WALL-CLOCK, not steps**
(pre-stated): 6 × ~60–100M searched steps against the R6 finals as the control. The
sample-efficiency claim is the bet, and matching on wall is the honest way to test it.

L-op at the ladder: ~30 ms depth-1, ~2.5 s depth-2 at S=8, both under 2% of the 150 s
tight-path budget; the design's ≤ 5 s cap holds, chunked at 4,096 rows (§4.2).

## 6. Gates and instruments, in order, each with its branch pre-stated

**Stage 0B (amendment 5), before G0 and free:** regress banked finals' FP@20 / vs-SH
strength on their turn-2–8 r² bucket. No correlation → that bucket is dropped as a mechanism
co-primary here and flagged to R6 trio A.

**G0 — the rollout-Q instrument (I-op), the one measurement that decides everything.**
500 positions sampled from R5-final self-play on the engine (stratified by turn bucket),
the full row × column matrix, **256 rollouts per cell** (se ≈ 0.03 per cell), both seats
stochastic. Reads, all in one file, all in-block:
- `regret_greedy` = `max_a Q̄(a) − Q̄(a_greedy)`: **how much the played action leaves on
  the table**, by turn bucket, with the winner's-curse correction the action-gap script
  already carries. This is the prize, at 10× the resolution of the 24-rollout run.
- `spearman(critic, rollout-Q)` per position, for the observation critic AND the
  privileged critic on the true world: **can the critic be a leaf?** And
  `regret_critic_depth1` = the regret of argmax over critic-valued leaves — the T-op's
  quality before any training.
- The R5 W finals' committee as the policy; ~2–4 core-hours; runs niced beside the R6
  fleet or after it.
**Branches.** `regret_greedy` averaged over decisions below **0.005** (the effect of
fixing every decision could not clear the credit line even if compounded): a **measured
mechanism ceiling on depth-1 search over this policy** — the chapter closes on P1 and
the training-side build is not started. Above it: the prize is real and G1 follows.
`spearman` of the privileged critic below the observation critic's: P2 is wrong for this
critic and B2 trains the evaluator on rollout labels first (the G0 rows are the dataset).

**G1 — engine self-play, the fast in-block test of the operator.** L-op (true world,
B=1, depth-1) vs greedy, both from the same checkpoint, engine mirror matches, n=5,000
per arm, seat-swapped; anchor = greedy vs greedy = 0.5 by symmetry, which is a free
instrument check. Override rate reported; the statistical gate (`Q̄(a') − Q̄(a_greedy)
≥ 2·se`) is the matching device. No Showdown, no FP, hours not days.

**G2 — the JOURNEY 14 exit condition.** L-op with belief samples vs greedy, off FP@20,
n=3,000 per arm, in-session anchor (the R5 greedy committee re-drawn), the standing
credit line verbatim (pooled delta ≥ +0.025 AND ≥ 2·se_diff, se_diff the larger of
binomial and seed-clustered), decisions/sec and the per-turn budget in every quote,
both FP@20 disclosures. **Clears → the R6 ladder pre-reg gets an addendum offering the
L-op as the object under a disclosed policy form.** Does not clear → the ladder stays
greedy and the training side proceeds anyway, because G0 said the prize exists and the
evaluator is what G3 trains.

**G3 — the ExIt mechanism smoke, 12M, two lanes, never a win rate.** `search/kl_prior`
falling over training (the student absorbing the expert), `search/override` at a fixed
gate falling, privileged-critic Spearman on a held-out G0 set rising, `value_gap`
falling, EV NOT used for sizing (§21 bars it). All three moving → the fleet.

**G4 — the fleet readout.** vs-SH locked protocol; FP@20 and FP@500; the BC-clone leg;
the committee rule; the mechanism co-primaries above; then the R7 ladder under the split
schedule. A greedy read of the ExIt finals AND an L-op read, both, because the fleet's
claim is about the network and the ladder's object may be either.

## 7. The builds, in evening blocks (the maintainer's unit)

| # | build | blocks | precondition |
|---|---|---|---|
| B0 | `SearchNode.expand` batched leaf path in `engine/pkmn_gen1` (design §4.1, GIL released, chunked), the privileged leaf render, the critic-per-leaf bench that replaces the session number in §5 | 2–3 | none; `pkmn-engine-port` env only (rule 1) |
| B1 | `scripts/rollout_q.py` — the I-op instrument, resume-safe rows file, version marker in the JSON (the skip-guard landmine) | 1 | B0 |
| B2 | privileged antisymmetric critic: `V = ½(f(view1) − f(view2))` in `EntityDeepSetsNet`, both views from the engine collector, a test that asserts antisymmetry to 1e-6 by construction, checkpoints without it still load | 1–2 | none |
| B3 | `rl/search/native.py::solve` (the operator), counters, signature-derived dial list, golden test on fixed roots (the `test_tree_decision_golden` pattern) | 2 | B0 |
| B4 | asynchronous two-core lane: collector process, shared-memory rollout buffer, staleness counter `time/collector_lag_updates`, watchdog resume | 2–3 | none; the R6 fleet is the throughput control |
| B5 | learner seams: behaviour log-prob from `π'`, `loss/search_policy`, `loss/search_value`, `w`/`β`/`τ` dials, the loud seam when searched rows arrive without the dials or vice versa (the `opp_choice` precedent) | 1–2 | B2, B3 |
| B6 | the write-side bridge for the ladder: `rl/search/engine_bridge.py` + `BattleTracker.from_root` + gate R1-E (design §2–§3) | 3–4, **time-boxed at 4 with the design's reduced-fidelity fallback pre-decided** | needed only for G2 and the ladder; G0/G1/G3 do not wait on it |

Total **12–17 blocks** with B6 the only one that can balloon, and it is fenced by its own
design. B0–B3 are what G0 needs; that is the first thing to run, and it is the one that
can still kill the plan cheaply.

## 8. How this sits with R6 and the queue

- **R6 runs as ratified.** Its finals are the control for G4 and the warm start for the
  ExIt fleet (a warm start off a finished checkpoint is barred for PPO's anneal, not for
  a different learner; disclosed either way). Its trio A (4.11) and trio B (4.12) are both
  inputs here: the outcome heads ride the privileged critic, epochs-2 is what makes the
  async lane learner-idle.
- **The exit-gate queue finishes.** Its verdict is banked as written for the tree-on-PPO-
  critic operator. §9 asks that its closure not extend to this operator.
- **The attention BC screen** is orthogonal and stays R7's architecture gate. If it
  clears, the ExIt fleet's actor trunk is decided by it, not here.
- **Job ownership** (rule 4): every gate is eval/analysis, detached, resume-safe and
  rate-readable, so it runs agent-side at any length; the ExIt fleet is over 5 h and the
  maintainer launches it.
- **No heavy job beside an FP arm.** G0 and G1 are engine-only and can run niced beside
  the R6 fleet; G2 waits for an idle box.

## 9. Rulings — **ALL SIX TAKEN AS RECOMMENDED, maintainer 2026-09-22 ("agree with all")**; #5 is conditional on G2 clearing, #6 lands the mmap'd team bank first

1. **Open JOURNEY 14 now**, before step 12's wrap, as the R7 chapter. (The plan assumes yes.)
2. **Scope the exit gate's closure** to the tree-on-PPO-critic operator; the native
   operator's kill is G0's ceiling, stated in §6.
3. **The privileged critic as the evaluator** (P2) — inside the charter: it reads the
   engine's own state, no external data. D18's null is vacated and was a baseline test.
4. **A search-backed value target** (`v'`) inside the charter's spirit — the ExIt sketch's
   open question 3; it is our own network's backup.
5. **The ladder object may be a mixed-strategy searched policy** (P4), disclosed as a
   policy form, if G2 clears. The greedy committee stays the pure-lane number beside it.
6. **Two cores per lane** for the R7 fleet (B4), with the memory arithmetic in §5.

## 10. What would kill it, named before anything runs

- **G0's ceiling** (`regret_greedy` < 0.005): depth-1 over this policy has nothing to
  find; P1 is wrong for this format at this strength. Close the chapter, keep B0–B1 as
  instruments.
- **The privileged critic ranks successors no better than the observation critic** on
  G0's rows: the evaluator's deficit is fit, not information. Then B2 trains on rollout
  labels (pure self-play; the G0 rows) before any T-op, and the plan slows by a fleet.
- **`search/kl_prior` does not fall in G3**: the student cannot absorb the expert, which
  is a capacity or a target-form problem (the ACTOR_PARAM_CEILING is a K2 artifact and
  the attention screen is the lift). Not a kill of the operator; a kill of the 626k actor
  as its student.
- **The async lane's staleness exceeds one update** on this box: fall back to synchronous
  at 20% searched and match on wall; the fleet shrinks, the read does not change.
- **A small-run null on G3's win rate is not evidence** (rule 6) and G3 does not read one.

## 11. What this plan deliberately does not propose

- **A learned model (MuZero).** The simulator is exact and forkable; a learned one adds
  error and buys nothing.
- **CFR / ReBeL-class belief solving.** Hidden information here is nature's, shallow and
  measured small (D19); the matrix-game root captures the mixing that matters.
- **More dose, more width, a third recipe trio.** Three independent measurements say the
  target, not the capacity, is the bottleneck (§21, §27.1, §29).
- **League redesign / exploiters.** The board is transitive (14 arms, ~30k battles) and
  the maintainer declined to re-derive it (2026-09-06).
- **The transformer as THE lever.** It is a student-capacity question and has its own
  gate; the operator above is what would give a bigger student something to learn.
- **Foul Play distillation or any human replay.** Excluded by charter; everything above
  is search over our own policy and our own value function on the format's own generator.

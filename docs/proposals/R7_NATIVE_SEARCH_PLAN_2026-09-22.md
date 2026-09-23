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

> ### AMENDMENT BOX 2 — 2026-09-22, reply to the teammate's REPLY BOX (branch
> `claude/search-in-training-proposal`, commit `dd224a4`). Four findings against this plan,
> each verified here against source before being taken; one is against the ratified kill branch.
> 1. **G0's kill branch could not fire as written — TAKEN, and it is a finding against a
>    ratified plan.** `regret_greedy = max_a Q̄(a) − Q̄(a_greedy)` is a max over ~6.7 noisy rows,
>    upward-biased by construction (a winner's curse). `scripts/action_gap.py:218-225` says so in
>    its own comment: *"with zero true gap everywhere, pure noise still yields a 'ceiling' of
>    ~0.04"* at 24 rollouts. Re-derived at G0's budget: row-mean se ≈ 0.029 on the ±1 scale over
>    3–4 columns × 256 rollouts, times E[max of ~6.7 standard normals] ≈ 1.27, gives a zero-gap
>    floor of **≈ 0.037 outcome / ≈ 0.018 win-rate**; the teammate's √(24/256) scaling gives
>    ≈ 0.012. Either is 2–4× ABOVE the 0.005 kill. **Fix, all three adopted:** (a) **split-sample**
>    — choose the argmax on 128 rollouts, evaluate it on the other 128 (unbiased; √2 on the se,
>    which is the right trade because the kill needs bias gone, not variance); the same fix on
>    `regret_critic_depth1`; (b) **CRN-1 across rows** (chance seed keyed on `(col, sample)`,
>    never the row), which shrinks the row-to-row noise the max feeds on — the script records
>    `corr_12` for exactly this reason; (c) **a measured zero-gap null** at the G0 budget
>    (permute the split), printed beside the estimate, and the kill fires only when the upper
>    95% bound of mean split-sample regret is below the threshold. **Scale named: 0.005 is a
>    WIN-RATE number** (half an outcome point, `action_gap.py:275`). §6 and §10 edited in place.
> 2. **P3 holds as sampling and fails as search — TAKEN, made conditional on D19.** Searching
>    the true world yields `π'(·|o,w)`, the policy of an agent who knows `w`; averaging
>    knowledge-assuming best responses is strategy fusion (two worlds, A wins in w₁ and loses in
>    w₂, B the mirror, C neutral: the averaged target is ½A + ½B with zero mass on C, the
>    o-optimal action). Depth 1 does not prevent it. The value target `E_w[V_search(o,w)]`
>    upper-bounds `V*(o)` for any o-measurable policy — an optimism concentrated in
>    high-uncertainty positions, invisible in a win rate. **The bias scales with the value of
>    knowing `w`, which D19 measured at 0.024–0.034 nats of residual belief, 88–90% of the
>    structure a deterministic cap mask.** So P3 is defensible in gen-1 randbats BECAUSE of that
>    measurement, and **does not transfer to gen 4, gen 9 or any OU format** without re-measuring
>    it. Reads added: `search/value_gap` by turn bucket (the opening is where the optimism would
>    show), and a **fusion read after B6** — the true-world action's regret against the
>    belief-averaged action over B sampled worlds, on G0's positions.
> 3. **P2 makes P3 worse — TAKEN; the privileged critic is DEMOTED from principle to arm.** An
>    observation-only leaf already averages over the posterior, confining fusion to the expanded
>    ply; a privileged leaf re-introduces the knowledge assumption at every leaf. And IDEAS 4.7's
>    vacatur *"does NOT touch: the information leg"* — the entire hidden team was worth ~+0.045
>    EV. **First arm: the observation critic at the leaves. Privileged critic: an arm, decided by
>    G0's `spearman` columns on the same rows.** What survives of P2 without privilege: the
>    **antisymmetric construction still works on the observation critic** — in a determinized
>    world both seats' OBSERVATIONS are renderable (each blind to the other's hidden bench through
>    the tracker's foe path), so `V := ½(f(obs₁) − f(obs₂))` cancels §31's seat-constant bias as
>    an identity with no privileged input. B2 builds that form. Line reference corrected:
>    `entity_deepsets.py:348-353`.
> 4. **Stage 0A is one more column, not subsumed — TAKEN.** `spearman(root_q_depth1, rollout-Q)`
>    beside the critic's raw value on the same rows: is the backed-up root value a better
>    ESTIMATOR than the critic's own output? That decides whether a root-value target is live
>    independently of whether the search chooses better. Zero extra cost.
> 5. **Top-k column optimism — TAKEN as a recorded read.** If the opponent's best reply is
>    outside the searched top-k, the row is overestimated — the same sign as 2.10's
>    `_look_further` optimism. G0 records the fraction of decisions where the oracle's best reply
>    falls outside top-k for k ∈ {2,3,4,all}; the T-op's k is set from that read, not typed.
> 6. **§26.1 quote softened** — the 10.76% flip is a named suspect for §30's cost, not a measured
>    explanation; §1 item 2 now says so.
>
> **Ownership (maintainer, 2026-09-22): ONE runner.** The B5 seams, the B0 bench, Stage 0B
> and every other build item are this plan's author's. The teammate's proposal is imported
> as `SEARCH_IN_TRAINING_CHAPTER_2026-09-22.md` (SUPERSEDED) so its test designs and bench
> spec stay in the tree; that branch and session are closed.

> ### AMENDMENT BOX 3 — 2026-09-22, reply to the teammate's REPLY BOX 2 (`eed70ed`). Six
> tasks answered; five findings taken, two points of disagreement recorded, one ruling asked.
> **This closes the review thread: the plan is frozen at this box until G0 reads. The
> teammate's branch is closed; all build items are the R7 author's (maintainer, 2026-09-22).**
> 1. **CORE TOPOLOGY — TAKEN, and it is the finding that matters.** `docs/landmines.md:614-626`:
>    this box is **10 performance + 4 efficiency cores**, and search work on the E-cores read
>    **549.8 ms/decision against 81.1** (6.8×). §5's twelve threads for six lanes do not fit on
>    ten P-cores; the spill lands on E-cores, and under a WALL-MATCHED comparison a lane whose
>    collector runs there does not finish late — it trains FEWER STEPS in the same wall, so the
>    fleet becomes heterogeneous in dose and the arm is CONFOUNDED, not delayed. Changes: §5
>    carries the topology; B4 gets a QoS clause (normal QoS everywhere, `taskpolicy` barred in
>    the fleet path, the launcher asserts it); **fleet width is restated as 5 lanes × 2 cores on
>    the 10 P-cores** — 6-wide only under a pre-registered disclosure that one lane runs
>    degraded. **RULING ASKED (§9 item 7): 5-wide honest, or 6-wide disclosed.** Also taken: the
>    "1.1–1.5 µs/leaf at 4 threads" figure is STRUCK (`landmines.md:328`: `torch_threads: 6`
>    is 0.85× of 1 on 256-row minibatches; a 40-row leaf batch is narrower still) — 10 µs
>    single-threaded is the only planning number; the antisymmetric second view (amendment 2,
>    item 3) doubles encodes and forwards per leaf, so the T-op is **≈1.8 ms, not 1.2**; §5's
>    table is corrected and every wall figure re-derived from it. B0's bench spec is the
>    teammate's: fleet width (five- and six-wide, never solo), `torch_threads: 1`, both views on,
>    p99 not mean, the four cost components separated, pass condition pre-stated at 2× the table.
> 2. **`regret_greedy` RENAMED to what it is — TAKEN.** It is the **depth-1 policy-improvement
>    ceiling under a PERFECT evaluator** (Q̄ rolls out to termination under the committee, so no
>    depth-1 evaluator beats it), and it bounds the FIRST ExIt iteration, not the compounding.
>    Now `regret_depth1_ceiling` in §6. **§0 is amended accordingly:** every independent bound
>    this repo owns (0.0317 top-two, §27's 64% irreducible, §24/§30/2.10 on depth-2) says the
>    inference-side prize is small, so **the monumental claim rests on COMPOUNDING through the
>    student — the training effect — and the plan now measures it** (item 4 below).
>    **Disagreement recorded:** the proposed `max_a min_b Q̄(a,b)` vs `max_a E_b[Q̄(a,b)]` read
>    is not a depth-2 separator; both are depth-1 quantities that differ in the OPPONENT MODEL
>    (minimax vs best-response-to-π). It is taken as `opp_model_gap` — it says whether the
>    matrix-game root matters — but a true depth-2 ceiling needs rollouts from re-searched
>    children and is NOT free; it stays unmeasured before the fleet and the plan says so.
> 3. **B5 tests — TAKEN as written in the teammate's REPLY BOX 2 (imported, superseded file):** the ratio identity
>    asserted BITWISE at epoch 0 / minibatch 0 on a fixture that asserts its own preconditions
>    and goes RED under "play π′ with π_θ's logp"; the aux-head golden on the advantage and
>    return ARRAYS across head-absent / coef-0 / coef>0; `value/bias_mirror` (pred − realized
>    on latest-snapshot rows, truth ≈ 0 by symmetry) as the counter §31 lacked;
>    `V(swap(s)) == −V(s)` bitwise as the antisymmetry property test. G3's six conditions and
>    the split branch (kl/override move, held-out Spearman does not → policy coefficient only)
>    are adopted as G3's sign-off, with the coef-0 control lane mandatory.
> 4. **COMPOUNDING gets an instrument — added here, not in the teammate's reply.** G3 runs the
>    G0 instrument on the STUDENT'S greedy play at matched steps for the searched lane and the
>    coef-0 control: `regret_depth1_ceiling(student_greedy)` must FALL FASTER on the searched
>    lane. That is compounding measured as the student's own ceiling shrinking, and it is the
>    read the monumental claim now rests on. Rule 6 applies: a 12M null on it is not a kill;
>    the pre-stated branch is "no separation at 12M → the fleet still runs, the NEXT fleet does
>    not repeat it".
> 5. **B4 — TAKEN:** `collect/weights_lag_updates` to disk with a bound of one update;
>    preallocated leaf buffers (~500 searched decisions/s/lane would otherwise churn hundreds of
>    MB/s); a second torch runtime per lane added to the memory arithmetic; and seed discipline
>    moves INTO the collector process, which is exactly where rule 2's username-collision
>    landmine lives — the launcher derives collector seeds from the lane seed and asserts
>    distinctness across the fleet.
> 6. **FUSION BOUND WITHOUT B6 — TAKEN, with a correction on the mechanism.** The read —
>    `fusion_flip = P(argmax π′(o,w₀) ≠ argmax π′(o,w₁))` and `fusion_bound = E[1{flip} ·
>    (Q̄(a_avg) − Q̄(a(w₀)))]` over G0's positions with 2–4 resampled worlds — is adopted as a
>    G0 column. **But it does not run on `rl/search/determinize.py::sample_determinization`,
>    which takes a poke-env `Battle`;** G0's positions are engine states. The resample is
>    `pkmn_gen1.BattleSpec::from_visible(b)` (`engine/pkmn_gen1/src/spec.rs:756`, exists) plus
>    the determinizer's hidden-slot fill ported onto the spec → `build()`. That is an
>    engine→engine resample, a fraction of B6's poke-env→engine fidelity work; it is **B1b**,
>    and B6 becomes conditional on the fusion bound instead of a prerequisite for knowing
>    whether it is needed.
> 7. **Stage 0B — DEMOTED, the teammate's own correction.** `scripts/critic_calibration.py`
>    reads one rows file from one object; per-final r² needs a §27-scale rollout campaign each
>    (~2–4 core-hours, live server, × 6–9 finals), and the regression's n is single digits
>    against ±0.02–0.03 strength noise: underpowered by construction. Amendment 1 item 5 is
>    corrected: 0B is a NECESSARY-CONDITION check with its n stated (strongest final must beat
>    weakest on the bucket; the converse licenses nothing), not a gate. No readout exists
>    because no run happened.

---

> ### AMENDMENT BOX 4 — 2026-09-23, **G0 HAS READ** (`readouts/R7_G0_READOUT.md`, rows sha `fa50141ead6c`,
> 500 positions, every number below re-derived from the rows file by `scripts/r7_g0_readout.py`) **and the
> maintainer's kitchen-sink ruling is folded in.** The plan unfreezes at this box.
> 1. **THE KILL DOES NOT FIRE.** Split-sample `regret_depth1_ceiling` pooled **+0.0236 ± 0.0028 win-rate, upper95
>    +0.0292** against the 0.005 threshold; by turn bucket +0.030 / +0.025 / +0.021 / +0.018 (turns 2–8 … 23+). The
>    measured zero-gap null is −0.0003 ± 0.0009. **The prize is real and G1 follows** — launched 19:35Z
>    (`scripts/g1_engine_mirror.py`, n = 5,000 per arm, seat-swapped, greedy-vs-greedy anchor, niced beside the
>    fleet, a guard kills it at fleet end). Leaf critic for the first arm: the OBSERVATION critic (`spearman_critic`
>    +0.476 ± 0.011; privileged PENDING, no trained checkpoint). Estimator: the searched root v′ ranks the rollout
>    root value no better than the critic's raw value (+0.843 vs +0.849), so **B2 trains the evaluator on rollout
>    labels first — the G0 rows are the dataset** (§6's own branch). `opp_model_gap` +0.059: the root's opponent model
>    is first-order (item 6).
> 2. **INSTRUMENT CORRECTION, owed as `rollout_q/2`:** `scripts/rollout_q.py::permuted_null` re-halves the SAME
>    samples — a re-split REPLICATE of the estimate (+0.0246 ± 0.0028 beside +0.0236), not the zero-gap null §6
>    named. The readout computes the real one (the scoring half's row labels permuted relative to the selecting
>    half; expectation 0) and the kill clause is read against it. The bump lands after this chapter's rows are done
>    with (a version bump refuses the rows).
> 3. **THE T-OP'S DIALS ARE SET FROM THE READ, NOT TYPED** (amendment 3 item 5): the dial sweep
>    (`scripts/rollout_q_top_sweep.py`, 300 cells × 500 positions, scored on the rollouts already paid for) reads
>    POSITIVE at every cell — the critic-leaf operator's overrides beat greedy under the oracle everywhere (worst cell
>    +0.0004) — and captures the most ceiling at **k 4, S 2, τ 0.05, margin gate 0.01: override 10.0%, +0.0040 ±
>    0.0015 win-rate unconditional (+0.040 conditional on an override), 17% of the ceiling**; k 2, S 8, τ 0.05 ties it
>    at 9.2%. At the plan's typed dials (k 3, S 2, τ 1) the operator overrides 0.6% of decisions and measures nothing.
>    The dose read: π_θ top-1 ≥ 0.97 on 46% of positions, so the eligible pool is ~54%; the T-op's `frac` is set
>    to search ~40% of decisions (`frac` ≈ 0.75 of eligible rows), matched across arms.
> 4. **[CORRECTED IN BOX 5: this pass ran at τ 1.0 / k 3 / no gate, where the operator barely moves, with the foe's TRUE-view
>    prior in every resampled world; re-read at the working dials the licence still holds, on the right measurement.]**
>    **FUSION: P3's licence is INTACT.** `fusion_flip` 0.010 ± 0.004 and `fusion_bound` −0.0000 ± 0.0001 win-rate
>    (upper95 +0.0002) against the +0.025 floor over 4 resampled worlds per position (B1b). The T-op searches B = 1,
>    the true world, as planned.
> 5. **THE SIMULTANEOUS-MOVE NOTE, read and measured** (`docs/prior_work/README.md` "SIMULTANEOUS-MOVE SEARCH";
>    `rl/search/root_rules.py`, `scripts/rollout_q_root_rules.py`). At the ORACLE level, split-sample, the policy's
>    greedy row is exploitable by **−0.052 win-rate** against a best reply; the pure best response to the foe's
>    prior (the depth-1 ceiling's rule) gains +0.025 under the prior and is MORE exploitable (−0.061); **regret
>    matching's average strategy keeps greedy's value under the prior and halves the exploitability (−0.028)**. At
>    the CRITIC level (k 4, S 2) every root rule is within noise of greedy: **the root rule cannot repair values that
>    are wrong, and this critic ranks successors at Spearman 0.48 — the evaluator is the binding constraint, not the
>    rule.** Change to the plan: `native.solve` gains a `root_rule` dial (soft best response, the current P4 rule, or
>    regret matching's average strategy) for the T-op target and the L-op's played mix, read in G3's counters once
>    the evaluator moves; the ExIt-target question is Becker & Sunberg 2025's, and it is deferred to that read.
> 6. **RULING (maintainer, 2026-09-23, verbatim in JOURNEY step 14): "make R7 the kitchen sync."** The ExIt fleet's
>    base is the STACKED recipe — W + C6 + whichever of R6 trio A (outcome heads) / trio B (×4 batch, fallback form)
>    reads non-negative on the 09-25 read + the antisymmetric privileged critic (B2) + anything stackable that is
>    built and smoked — with **searched vs coef-0 control arms on that base** keeping attribution for the one lever
>    with a measured prize. Ruling 7 stands at 5 lanes: proposed 3 searched + 2 control, wall-matched. **G3 is not a
>    separate lap:** a 400k inert-check smoke through the launcher, then the fleet, with G3's six mechanism conditions
>    read at 12M ON the fleet's own lanes (rule 6: no separation at 12M stops nothing). Own-lap items after the fleet:
>    trunk / architecture replacements (attention read: does not clear), the shared trunk, feature crosses, temporal
>    context, objective changes, the seat-2 harvest (needs a seat-2 block build). JOURNEY steps 15–16 order the rest.
> 7. **BUILT since box 3, all on `r7-native-search` (pushed):** B0–B3, B1b (resample + fusion), **B5** (the learner
>    seams, signature-derived dials, `value/bias_mirror`), **B4** (the two-core lane: the child-process collector,
>    weights shipped per update, backpressure, `collect/weights_lag_updates` ≤ 1; the T-op inside it, playing π′ and
>    recording log π′(a); the loop runs and resumes it; the launcher's QoS clause), **B6 first form** (the write-side
>    bridge: `BattleTracker::from_root`, `rl/search/engine_bridge.py`, gate R1-E's engine backend; the round trip is
>    bitwise on live positions; the gate's full run is owed), the G1 harness, the readout generator, the dial sweep,
>    the root-rule read. **Still owed before the fleet:** `rollout_q/2`; the `root_rule` dial; the fleet and smoke
>    configs (after the 09-25 read fixes the base); B6's R1-E run and the L-op's ladder path (G2 needs the idle box);
>    the merge of the branch into main (Friday, the idle box); the B0 bench at normal QoS (Friday).
> 8. **PENDING, named:** `spearman_privileged` (no trained privileged critic yet); the depth-2 ceiling (unmeasured before
>    the fleet by amendment 3 item 2); the G1 read (tonight); the critic-level root-rule read after the evaluator is
>    retrained. CPU share disclosed in the readout: the six R6 lanes ran 1.11–1.24× their 3-rung pre-G0 baseline during
>    G0's 94 rungs (a wall cost on step-matched lanes, not a measurement).

---

> ### AMENDMENT BOX 5 — 2026-09-23, **G1 HAS READ** (`readouts/R7_G1_READOUT.md`, every number re-derived from the rows by
> `scripts/r7_g1_readout.py`) **and P3's licence is RE-READ at the dials the operator actually runs.**
> 1. **G1: THE OPERATOR WORKS, IN ITS BEST CASE.** The gated L-op (true world, B = 1, depth 1; k 4 / S 2 / τ 0.05 / margin
>    gate 0.01) beats its own greedy committee in the engine mirror by **+0.0504 ± 0.0050 win-rate** pooled over both seats
>    (0.5504, n 10,000, 10.1 se) at **override 0.096** of all decisions (3.38 a battle). The anchor reads 0.5080 ± 0.0071
>    (+1.13 se from 0.5: the instrument check passes); no seat interaction (+0.0051 ± 0.0099). The harness's pooled − anchor
>    (+0.0424 ± 0.0086) subtracts a p1-seat anchor from a seat-balanced number — conservative, reported, not the read. G1
>    carries no kill clause; nothing blocks G2 or the fleet on its account. Its program is pinned: the belief read's
>    true-world arm reproduces the sweep's cell bit for bit across the B6 extension rebuild, and G1b's re-runs reproduce G1's
>    rows in order.
> 2. **CORRECTION TO BOX 4 ITEM 4.** `scripts/rollout_q_fusion.py` hard-codes τ 1.0 and ran at k 3 / S 2 with no gate — where
>    the operator's own true-world action moved 0.006 of G0's positions — and it carried the foe's TRUE-view prior into every
>    resampled world, holding the most direct channel of hidden information at the truth. "INTACT" read an operator that
>    barely moves. **Re-read** (`scripts/rollout_q_belief.py`, 500 positions × B = 8, each world's foe prior recomputed from
>    that world's foe view): the choice depends on the hidden world **~9× more** (per-world argmax flips 0.088 ± 0.009; the
>    belief L-op makes the true L-op's move on 54% of its overrides; the T-op's target moves TV 0.078). The value: the
>    belief L-op gains +0.0028 ± 0.0013 per decision against the true L-op's +0.0040 ± 0.0015 — **the peek, +0.0012 ±
>    0.0011, is NOT resolved**. The student: the fusion cost (the PIMC target over the world-averaged target a student of
>    true-world targets converges to) is **+0.0003 ± 0.0003 per decision, upper95 +0.0008** — +0.012 even summed over the
>    T-op's ~14 searched decisions of a battle, **below §10's credit floor: the licence HOLDS, now on the right measurement,
>    and the T-op stays B = 1.** At B = 4 the belief L-op's gain halves and the fusion cost changes sign (noise at this n), so
>    ladder-side worlds are B ≥ 8. The v′ target's peek-optimism (+0.0078 ± 0.0008 outcome units) is small beside the
>    critic's own optimism against the rollout root value (+0.034 ± 0.015) and the root max's (+0.019 ± 0.005).
> 3. **WHAT CHANGES: G1's +0.050 is an UPPER bound on G2's operator in the same mirror** — G1 saw (a) the true world and (b)
>    the foe's exact prior (the foe IS the committee). **G1b** prices (a) at the battle level: `scripts/g1_engine_mirror.py`
>    /2's belief arms (B = 8, per-world foe priors, PIMC, the same gate) PAIRED on battle seed with re-runs of G1's true-world
>    arms, n 2,500 per arm, launched 21:53Z niced beside the fleet, guard-killed at fleet end, resumable on the idle box.
>    (b) stays G2's to measure. G2's build now has its operator: the belief arm's PIMC loop is the ladder L-op's, fed by
>    B6's bridge instead of the engine resample.
> 4. **Order unchanged, one reason sharpened:** the evaluator trained on rollout labels (G0's rows) stays first before the
>    fleet — the critic's own optimism, not the peek, dominates both the L-op's value error and the v′ target.

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
that measures both.** **Where the monumental claim sits, stated after amendment 3:** every
independent bound this repo owns says the inference-side prize of one exact ply is small, so
the +8 GXE bet is on COMPOUNDING — the student absorbing a search-improved target every
update, which G3 measures as the student's own depth-1 ceiling shrinking faster than a
control's. The evaluator at its leaves is an **antisymmetric critic** read on
both seats' views of the determinized leaf; whether it also reads privileged information is
an ARM that G0 decides (amendment box 2, item 3).

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
   alone **flips 10.76% of argmaxes** (§26.1, which calls it a suspect that "may be" the
   largest unnamed difference — a named suspect, not a measured explanation of §30). A
   critic read off-distribution at every leaf is a different critic.
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

**P2 — The critic at a determinized leaf is antisymmetric by construction; privilege is an
arm, not a principle (amendment box 2, item 3).** A
determinized leaf is a COMPLETE state: the sampled world has an opponent team, movesets,
exact HP. An observation-only critic throws that away and then has to marginalise over
a bench it could read. The D18 privileged form already exists in the net
(`rl/networks/entity_deepsets.py:348-353`, the 408-block appended to the obs) and the
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
**10 µs/leaf single-threaded** (the design's "1.1–1.5 µs at 4 threads" is STRUCK per
amendment 3 — `landmines.md:328` measures threads as slower than one on this box; both
constants are session measurements **not in any committed result file** until B0's bench,
run at fleet width, pins them); **box topology: 10 performance + 4 efficiency cores
(`landmines.md:614-626`), so at most TEN busy threads run at full speed;** collection **34.9% of wall** at k=8 with
the Rust side ≤ 8.7% of that; **1,282 sps/lane** six-wide (`docs/engine_port/SPEEDUP.md`);
greedy collection ≈ **0.15 ms/decision** in its phase; box **M4 Pro 14 cores / 24 GB**,
per-lane RSS **1.825 GB**, the mmap'd team bank returns **2.7 GB** at width 6
(`configs/showdown_monster200m_w.yaml:686-712`).

| | per decision | vs greedy collection |
|---|---:|---:|
| T-op, 40 leaves, both views (antisymmetry) | 0.46 ms engine/encode + 0.8 ms critic + ~0.5 ms glue ≈ **1.8 ms** | **~12×** |
| T-op on 40% of decisions | mean **0.7 ms** | **~5×** |
| T-op on 30% of decisions | mean **0.55 ms** | **~3.7×** |

Synchronous, one core per lane: wall = 0.65T (update) + 5 × 0.35T = **2.4T** at 40%
searched. **The fix is structural: give each lane a second core for an asynchronous
collector — and the box has TEN performance cores, so that is FIVE lanes, not six**
(amendment 3, item 1; a sixth lane's threads spill to the efficiency cores at ~6.8× and,
under a wall-matched comparison, train fewer steps — a confound, not a delay). Memory at
width 5: 5 × (1.825 + ~0.6 collector + ~0.3 second torch runtime + preallocated leaf
buffers) ≈ 14 GB of 24, with the mmap unlock in hand. Then wall = max(0.65T, 1.75T) =
**1.75T** at 40% searched, or **1.3T** at 30%, and with R6 trio B's epochs-2 update the
learner is never the bottleneck. **A 100M ExIt lane ≈ 38 h at 40% searched, ≈ 28 h at
30%; a 60M lane ≈ 23 / 17 h.** All of it re-derived from the 1.8 ms row; B0's bench
replaces that row before any of these numbers enters a pre-reg. The fleet comparison is
**matched on WALL-CLOCK, not steps** (pre-stated), with each lane's realised step count
DISCLOSED beside its readout: 5 × ~60–100M searched steps against the R6 finals as the
control. The sample-efficiency claim is the bet, and matching on wall is the honest way
to test it. QoS: normal everywhere, `taskpolicy` barred in the fleet path, asserted by
the launcher (`landmines.md:614-626`).

L-op at the ladder: ~30 ms depth-1, ~2.5 s depth-2 at S=8, both under 2% of the 150 s
tight-path budget; the design's ≤ 5 s cap holds, chunked at 4,096 rows (§4.2).

## 6. Gates and instruments, in order, each with its branch pre-stated

**Stage 0B (amendment 5), before G0 and free:** regress banked finals' FP@20 / vs-SH
strength on their turn-2–8 r² bucket. No correlation → that bucket is dropped as a mechanism
co-primary here and flagged to R6 trio A.

**G0 — the rollout-Q instrument (I-op), the one measurement that decides everything.**
500 positions sampled from R5-final self-play on the engine (stratified by turn bucket),
the full row × column matrix, **256 rollouts per cell, split 128/128** (se ≈ 0.05 per
cell on the ±1 outcome scale, ≈ 0.025 win-rate; CRN-1 seeds across rows), both seats
stochastic. **All thresholds below are on the WIN-RATE scale.** Reads, all in one file,
all in-block:
- `regret_depth1_ceiling` (formerly `regret_greedy`; amendment 3, item 2) =
  `Q̄_B(a*_A) − Q̄_B(a_greedy)` where `a*_A` is the argmax on the first 128 rollouts and `Q̄_B`
  is the mean on the other 128 — **split-sample, unbiased** (amendment box 2, item 1); by
  turn bucket; a **measured zero-gap null** (permuted split) printed beside it. **This is the
  depth-1 improvement ceiling under a PERFECT evaluator and it bounds the FIRST ExIt
  iteration, not the compounding.**
- `opp_model_gap` = `max_a E_b[Q̄(a,b)] − max_a min_b Q̄(a,b)` on the same cells: whether the
  root's opponent model (best response to π vs minimax) matters. NOT a depth-2 read; the
  depth-2 ceiling stays unmeasured before the fleet.
- `fusion_flip` and `fusion_bound` over 2–4 resampled worlds per position via
  `BattleSpec::from_visible` + the determinizer's fill (B1b; amendment 3, item 6).
- `spearman(critic, rollout-Q)` per position for the observation critic AND the privileged
  critic on the true world: **can the critic be a leaf, and which one?** And
  `regret_critic_depth1` = the split-sample regret of argmax over critic-valued leaves —
  the T-op's quality before any training.
- `spearman(root_q_depth1, rollout-Q)` beside the critic's raw value on the same rows —
  the ESTIMATOR question (amendment box 2, item 4).
- `opp_best_outside_topk[k]` for k ∈ {2,3,4}: the fraction of decisions where the oracle's
  best opponent reply is outside the policy's top-k (amendment box 2, item 5).
- The R5 W finals' committee as the policy; ~2–4 core-hours; runs niced beside the R6
  fleet or after it.
**Branches.** The **upper 95% bound** of mean split-sample `regret_depth1_ceiling` below **0.005
win-rate** (the effect of fixing every decision could not clear the credit line even if
compounded): a **measured mechanism ceiling on depth-1 search over this policy** — the
chapter closes on P1 and the training-side build is not started. Above it: the prize is
real and G1 follows. `spearman` picks the first arm's leaf critic (observation by default;
privileged only if it ranks better on the same rows); neither ranking above the critic's
own raw-value `spearman` on the root: B2 trains the evaluator on rollout labels first (the
G0 rows are the dataset).

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

**G3 — the ExIt mechanism smoke, 12M, searched lane + coef-0 CONTROL lane, never a win
rate.** The teammate's six sign-off conditions (amendment 3, item 3): `search/kl_prior`
falling (the student absorbing the expert), `search/override` at a fixed gate falling,
leaf-critic Spearman on a held-out G0 set rising RELATIVE TO THE CONTROL, `value_gap`
falling, `value/bias_mirror` ≈ 0, and **the compounding read (amendment 3, item 4):
`regret_depth1_ceiling(student_greedy)` at matched steps falls faster on the searched
lane than on the control.** EV NOT used for sizing (§21 bars it). Split branch: kl and
override move but the held-out Spearman does not → launch with the policy coefficient
only. A 12M null on the compounding read is not a kill (rule 6): the fleet runs, the
next fleet does not repeat it.

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
7. **FLEET WIDTH (amendment 3, item 1): 5 lanes × 2 cores on the ten performance cores,
   or 6 lanes with a pre-registered disclosure that one runs degraded on the efficiency
   cores.** Recommended: 5. — *RULING PENDING.*

## 10. What would kill it, named before anything runs

- **G0's ceiling** (upper 95% bound of split-sample `regret_depth1_ceiling` < 0.005 win-rate, with
  the measured zero-gap null below it): depth-1 over this policy has nothing to find; P1 is
  wrong for this format at this strength. Close the chapter, keep B0–B1 as instruments.
- **The fusion read after B6** shows the true-world action's regret against the
  belief-averaged action above the credit floor: P3's D19 licence is spent for this object,
  and the T-op must search B ≥ 2 sampled worlds at training time (cost ×B).
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

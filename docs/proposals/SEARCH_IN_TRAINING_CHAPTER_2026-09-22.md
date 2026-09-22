> **SUPERSEDED 2026-09-22 (maintainer): merged into `R7_NATIVE_SEARCH_PLAN_2026-09-22.md`.**
> Imported verbatim from branch `claude/search-in-training-proposal` at `eed70ed` so its
> REPLY BOX 1 and REPLY BOX 2 (the B0 bench spec, the B5 test designs, the G3 sign-off
> conditions, the fusion bound, the Stage 0B correction) stay in the tree. Every item of value
> is recorded in the R7 plan's amendment boxes 1–3, which are authoritative on conflict. The
> source branch does no further work; the R7 plan's author is the single runner.

# Chapter proposal — search INSIDE training (expert iteration), and why not ReBeL

**Status: a CHAPTER PROPOSAL. Not a pre-registration, not ratified, nothing here
licenses a launch.** Every fleet item needs its own config header with `journey_step`
named and the credit line restated verbatim (larger-of clause included). Written
2026-09-22 at the maintainer's request. **Revision r2**, after two Opus reviews.

**WRITTEN BLIND TO THE EXIT GATE.** At HEAD `e6cc5dd` there is no
`readouts/EXIT_GATE_R5_READOUT.md`, and the gitignored run data under `results/`
(`outcome_variance/`, `exit_gate_r5/`, `tree_budget_r5/`, `logs/`) is absent from the
authoring environment. **Every criterion here is stated before that number is known**
(§7 branches on both outcomes). RESULTS §32's lesson is the reason: *"switching to the
criterion that fires after seeing the data is the discipline failure this project
exists to avoid."* If the gate has since read, amend in a dated box — do not re-word.

**Every figure is quoted from a committed doc, not re-derived from run data.**
Re-derive before any enters a pre-reg header.

> ### REVISION BOX — what r1 got WRONG (two Opus reviews, 2026-09-22)
> Recorded rather than silently fixed, because a correction carries more authority
> than the claim it replaces and nobody re-checks the fix.
> 1. **"The matrices are already computed on banked arms … no collection cost, no
>    server, no fleet."** FALSE on all three. `search/ev_matrix` exists in
>    `matrix.py`'s per-decision stats but the FP collector drops it — wrong prefix
>    *and* it is a list (`scripts/ch3_fp_h2h.py:274-277` keeps only scalar keys
>    prefixed `depth2|tree|census|bcts|heuristic|disagree`), and survivors are
>    averaged. Nothing in `rl/search/` writes to disk at all. Worse: both oracle
>    scripts play **live battles** (`outcome_variance.py:300`, `action_gap.py:184`,
>    `env.reset(...)`), so every "no server" claim in r1 was wrong and HANDOFF §4's
>    CPU-contention rule applies.
> 2. **The batch-16 argument was backwards.** 97.7 ms *is already* a batch-16 number
>    (`configs/eval/tree_r5.yaml`: "BATCHING IS ON (batch 16) … measured 224 → 113
>    ms/decision"); 227 ms is the pre-batching cost batching replaced. The real
>    re-pricing input is **budget**: the chapter's expert is `iters: 900` at
>    **766.6 ms/decision**, 7.8× the 97.7 both r1 cost figures were built on.
> 3. **IDEAS 2.10 RAN (2026-09-19) and did NOT support its hypothesis.** The honest
>    minimax backup read **0.5070 against depth-1's 0.5510 — −0.0440 at 1.97 se**,
>    i.e. *worse*. IDEAS 2.10: *"the optimism is WHY depth-2 hurts — is **not
>    supported**."* And it is **still the default** (`depth2.opp_k` = 1); the fix is
>    opt-in. r1 cited it as a demonstrated mechanism and implied it was fixed.
> 4. **RESULTS §21's "zero EV" was corrected 2026-09-19** to **−0.0038 at 4.2 se**
>    (significantly *lower*, not flat). r1 repeated the withdrawn wording.
> 5. **"EXPERT_ITERATION §3 item 1 is half-stale"** — false; it is fully current.
>    Nothing writes π′ or root q anywhere. Claim and amendment note dropped.
> 6. **JOURNEY 14's bar is absolute** — *"no number from here may be quoted beside a
>    pure-lane number."* r1 added "without saying so", which is not in the source.
> 7. Smaller: commit `02b0728` is **2026-09-18**; "88–90% of the hidden team" should
>    read "88–90% of *that structure*"; `determinize.py` enforces the caps as a
>    **final-team approximation** of the generator's sequential counters, not
>    "exactly"; §8.2's *diagnosis* was reversed 2026-09-18 (its **premise** survives);
>    the `does_not_clear` quote drops "(rule 6)".
>
> **And the reviews changed the chapter's shape, not just its facts** — see §5 Stage 0,
> which did not exist in r1 and which can close this chapter for about a day of
> compute, before anything is built.

---

## 1. The recommendation

**Expert iteration — search as a policy-improvement operator inside the training loop
— over ReBeL.** But the honest form of that recommendation is narrower than r1's:

> **Run Stage 0 first (§5). It is two reads on positions this project already knows
> how to generate, it costs about a day of compute and no build, and it can close the
> chapter outright.** Everything after Stage 0 is conditional on it.

Why expert iteration rather than ReBeL: ReBeL's machinery exists for games where the
belief over hidden state *is* the problem, and D19 measured our genuine belief residual
at **0.024–0.034 nats of 4.955** (`docs/prior_work/README.md`), which is why D19 was
killed at zero lanes. Meanwhile RESULTS §27 says the critic axis is open — ceiling
**0.3630**, critic **0.2176**, headroom **+0.1454**, worst in the opening
(critic/ceiling **25%** at turns 2–8 vs **73%** at 23+).

**Expected value, stated plainly and not talked up.** The *policy* half is bounded near
the credit floor by a measurement this repo already owns: a perfect top-2 swap is worth
**0.0317 of win rate** (HANDOFF §1), which sits *at* the +0.025 floor, and every
inference-time measurement of the operator is at or below greedy. Its hope rides on
compounding, which is unmeasured. The *value* half is genuinely untested, **but its
payoff path — better V → better advantages → better policy — has been contradicted
three times in this repo**: §21 (2.67× width, 126× rank, EV −0.0038 at 4.2 se, win rate
moved), §27.1 (93% of the gap is ranking; recalibration buys ~7%), §29 (EV traded
*against* win rate in 9 lanes of 9). **That is why Stage 0 exists and why it comes
first.**

---

## 2. Why not ReBeL

ReBeL (Brown et al., NeurIPS 2020) expands "state" to the **public belief state** — the
distribution over infosets consistent with common knowledge and both players' policies
— trains value and policy networks over PBSs, solves depth-limited subgames with CFR,
and provably converges to Nash in two-player zero-sum games.

**The argument is cost and motive, not tractability.** r1 argued the PBS is
combinatorially intractable here. **A reviewer knocked that leg out and was right:** if
the residual really is 0.024–0.034 nats, the belief is near a point mass and a
*factored* PBS (per-slot marginals over sets and moves) is low-dimensional. "Huge" and
"nearly determined" cannot both be the reason. **The surviving argument:**

1. **The uncertainty ReBeL reasons about is measured near-empty here.** Residual
   0.024–0.034 nats; 88–90% of *that structure* is a deterministic cap mask from the
   generator's own constraints, which `rl/search/determinize.py` already approximates.
   Corroborated independently: IDEAS 8.3 measured `n_det` 1→64 **flat** — belief
   *breadth* buys nothing on this object.
2. **Unexploitability is not where the measured gap is.** §27.1 puts **93%** of the
   critic's gap in RANKING. And no opponent in the locked protocol best-responds to us.
   *(r1 said "Nash is the wrong objective" — too strong, and it contradicted §4 of this
   same document, which argues for equilibrium-seeking. Narrowed.)*
3. **Cost.** A PBS value net, a PBS policy net, CFR subgame solving and a collector that
   emits belief states is a project restart, not a chapter.

**Scope note a reviewer added, and it is fair:** D19's residual is about the hidden
**team**; ReBeL's uncertainty is about what the opponent's *policy* implies. The
analogous local quantity is the opponent's current mixed strategy — which is exactly
what §4's solver addresses. So (1) argues against belief *breadth*, not against
equilibrium reasoning.

**The cheaper piece of that literature, and it is NOT the root solver.** Brown &
Sandholm's depth-limited solving with **multi-valued leaf continuations** fixes the
unsound leaf — a single on-policy critic value at a leaf assumes the opponent plays one
continuation — without any PBS. That is closer to our measured defect than a root
equilibrium solve, and it is the ReBeL-adjacent idea worth pricing. Named here; not
specified.

**What re-opens ReBeL:** a measurement showing the belief residual is materially larger
than D19's, or a format where it is.

---

## 3. What is ALREADY built, and what is NOT

**Already built in `rl/search/tree.py`** (r1's list, verified by both reviews):
decoupled UCT over determinized engine states with real chance nodes; our masked policy
as the PUCT prior and the D25 oppact head's L6 posterior as the opponent prior; our
critic at the leaves via `ShadowBattle`; a **gumbel** decide rule citing Danihelka et
al. (ICLR 2022) App. C.2.2 with both caveats verbatim in the docstring (the guarantee is
against **sampling** from π, not argmax — and our protocol is deterministic; and it
holds only as far as `q` is correct); **leaf-parallel batching under a virtual loss**
(`batch`, `virtual_loss`); `q_init: parent_v`; `opp_rule ∈ {puct, sample}`;
`root_min_visits`; `depth_cap`; `margin`. `_expert_stats` computes the 4.9 falsifier
per decision (`tree/kl_pi_prior`, `pi_top1`, `prior_top1`, `pi_entropy`, `pi_support`,
`argmax_moved`; commit `02b0728`, 2026-09-18).

**NOT built — the chapter's real build surface. Items 4–6 were missing from r1:**

1. **No per-decision dataset.** `_expert_stats` yields scalars that reach disk only as
   arm-level averages. Nothing in `rl/search/` writes a file.
2. **No training loss** toward π′ or root q.
3. **No Hannan-consistent selection** — decoupled UCT only, no `select` dial (§4).
4. **No root value is emitted on the arm the gate runs.** `tree/root_q_best`
   (`tree.py:623`) is `vals[argmax]/visits[argmax]` — a **max over actions**, not a root
   value — **and the gumbel branch returns before it** (`tree.py:546`, and the comment
   at `:573` "the gumbel rule returns here"). The expert the chapter would train on
   currently emits no usable root value at all.
5. **The root value that *is* computed is a MINIMAX value.** `opp_rule` defaults to
   `puct` — *"the opponent minimises our value, so the root Q is a best-response
   (minimax) value"* — in every banked tree arm and in the gate's XTG9. Training the
   critic toward it installs a systematic pessimism, and it is the **wrong estimand for
   §27's oracle**, which rolls the same committee out on *both* seats.
6. **The engine collector has no search path.** `tree_decision` takes a poke-env
   `Battle` (`battle.turn`, `our_action_str(battle, …)`, `battle_to_state(battle, …)`).
   `rl/envs/engine_collector.py` is batched in-process Rust with no poke-env `Battle`
   and no search hook. **In-loop search on the k=8 instrument needs a new engine-state →
   `poke_engine.State` bridge**, which is larger than items 1–3 combined and was
   invisible in r1.

### The result I overstated in conversation, corrected

"Greedy beats every search arm" is RESULTS §30's headline about the **matrix** family.

| block | vehicle | vs in-block greedy |
|---|---|---|
| §30 | matrix | every arm below greedy (0.6050): ungated depth-1 −0.052/−0.054 at ~2.4 se; depth-2 −0.076/−0.098 at 3.4–4.4 se — **a measured cost** |
| §26 | tree | TG gumbel **+0.0210 at 0.96 se**, TV +0.0140 at 0.64 se, TQ **−0.0230 at 1.04 se**, anchor 0.5830 |

**Never difference across those blocks** (§30.1's retraction; anchors 0.6050 and 0.5830,
different sessions). **Corrected from r1:** the defensible statement is *no tree arm is
**resolved** below greedy* — TQ's point estimate **is** below its anchor, and §26.1's
family table reads tree as "2 of 3 above its anchor, mean delta +0.0040, range −0.0230 …
+0.0210". **And §26.1 warns the matrix/tree contrast may not be the vehicle at all:**
`matrix.py` renders leaves through `col_views` while `tree.py` hardcodes `view=None`,
and leaf-rendering has been measured to flip **10.76%** of argmaxes. **Also:** TV's
3.65% action rate ran under an **undeclared** `margin` default of 0.10, and the realized
margin is not recoverable from the artifact (§26's 2026-09-19 correction). The tree
family's "unresolved-positive" reading rests on arms whose gates are not what the
pre-reg said.

---

## 4. The solver: equilibrium, not best response

**The defect.** Showdown turns are simultaneous. `matrix.py` builds the right object — a
matrix over (our legal actions × opponent L6 classes) — then solves it with a **pure
best response**: `row_ev = ev_matrix @ col_w`, argmax (D3/D4). `tree.py` uses
**decoupled UCT**.

**From the literature.** UCT does not converge to Nash even in a one-shot simultaneous
game. Lisý, Kovařík, Lanctot & Bošanský (NeurIPS 2013): an MCTS template whose selection
is **ε-Hannan consistent** — regret matching or Exp3 — converges to a **subgame-perfect
ε-Nash**. DUCT is the standard practical choice and often performs well, but carries no
guarantee.

**Why it matters more for training.** At inference an unsound solver makes one bad
override per decision. As a training expert it writes its bias into the weights every
step. **But the precedent r1 cited for this does not support it:** IDEAS 2.10's
optimistic backup *is* real and large (`minimax_drop` 0.057), but removing it made
depth-2 **worse** (0.5070 vs 0.5510, −0.0440 at 1.97 se), and 2.10 records the mechanism
hypothesis as **not supported**. It remains a warning about unaudited backups — and it
is **still the default** — not a demonstrated mechanism.

**Build.**
- **A1** `TreeCfg.select: "duct" | "rm" | "exp3"`, default `duct` **bit-identical**,
  pinned by `tests/test_tree_decision_golden.py`. **Forwarding matters:**
  `scripts/ch3_eval.py:85` derives `_SEARCH_DIALS` from `SearchAgent.__init__`'s
  signature and hard-fails on unknown arm keys — a new field reached through a nested
  `tree:` dict is precisely the nine-instance dial landmine. Say how it is forwarded and
  pin it.
- **A2** A mixed-equilibrium solve for `matrix.py`'s matrix (~10×6 — an LP or a few
  hundred regret-matching iterations). **Two limitations to state in the header, both
  from review:** the columns are the **L6 abstraction** (4 move slots, one `switch`
  column, one `other-move` bucket), so this solves an equilibrium *of a different game*,
  and abstraction refinement is non-monotone; and the uniform-switch-column shape is
  **exactly R5b's disclosed failure** (*"the search's uniform-switch-column optimism
  made permanent; distilled switch rates roughly doubled 0.14–0.20 → 0.21–0.37"*,
  RESULTS §15). **Open: what happens to `q[c]`** — the D25 oppact posterior is a
  *credited* lever and a mixed solve replaces it with the solver's own mixture. Anchor,
  prior, or discarded? Answer before building.
- **A3** `opp_rule: sample` as a first-class arm. The docstring already says the default
  is wrong about our scored opponent: *"SimpleHeuristicsPlayer … does not best-respond
  to anything, so assuming it does is not conservative — it is wrong about the opponent
  we are actually scored against."*

**Cost, corrected:** nothing is banked, so A2 must **re-run** the matrix solve over
freshly generated positions — server required, HANDOFF §4's CPU-contention rule applies.

---

## 5. The chapter, staged

Governing principle: **every read before the fleet is per-position or per-state, never a
win rate.** IDEAS §1 — σ_seed ≈ 0.0617 at k=3, unpaired bars 0.065–0.1007 — makes a
win-rate primary short of the full fleet uninterpretable, and rule 6 then bars citing
its null. **A 12M A/B is not a step in this chapter at any point.**

### STAGE 0 — the two reads that can close the chapter, before anything is built

**Neither existed in r1. Both were named by review as the thing that should come first.**

**0A — is the search root already a better ESTIMATOR than the critic?**
`results/outcome_variance/variance.json.rows.jsonl` carries, per position, the oracle
mean (`mean`), the critic's value (`critic`), `var`, `n`, `turn`, `outcomes`
(`outcome_variance.py:344`). Re-run the tree at those positions (under `opp_rule:
sample`, with the root value **defined and implemented** per §3 items 4–5), add root q
as a third column, and compare **r²(root-q, oracle)** against **r²(critic, oracle)** by
turn bucket. **This is the chapter's central bet, measured directly.** If the root value
is not already the better estimator, the value half is dead with no solver, no dataset,
no loss and no lane.
- **Replaces r1's citation of §24 for this claim, which review showed does not support
  it:** "opening the gate costs our critic 0.006 vs the heuristic's 0.088" is about
  relative *leaf-evaluator* quality under more overriding — a chooser property — not
  about the root value being a better estimate than the critic's own output.
- **Cost:** the positions must be regenerated (the rows carry no observation or state),
  so this needs a server and is not free. Price it before launching.

**0B — does the turn-2–8 r² correlate with STRENGTH at all?** Across banked finals with
known FP@20 / vs-SH numbers, regress strength on the turn-2–8 bucket. **If it does not
correlate, Stage B's primary is uninterpretable — and so is 4.11's, which is already
ratified as R6 trio A's mechanism co-primary on the same instrument.** Free; uses banked
numbers only.

**KILL:** 0A flat → the value half closes. 0B flat → the instrument closes, and that is
a finding the R6 fleet needs regardless of this chapter.

### Stage A — audit the operator (build A1–A3; then one read)

- **A-READ:** does the operator's chosen action agree better with the **rollout oracle**
  than the prior's? Arms: prior argmax · DUCT · RM/Exp3 · BR-matrix · mixed-matrix.
- **Four corrections from review, all load-bearing.** (i) The 707 rows store
  `{ep, turn, mean, var, n, critic, outcomes}` — **no observation, no mask, no state**,
  so a different selection rule **cannot** be re-run on them; new rollouts over the union
  of the arms' chosen actions are required. (ii) `action_gap.py`'s banked artifact holds
  only a1/a2 over 134 positions; any arm choosing a third action has no oracle value.
  (iii) **Both scripts need a live server.** (iv) **Power:** with per-position rollout
  noise ~0.204, se at n=134 is ~0.018 in outcome units while a *perfect* top-2 swap is
  ~0.064 — an operator capturing a realistic fraction reads under 1 se. **A kill at that
  n is rule 6's failure in per-position clothing.** State the position count (≈700+ at
  this rollout budget) and the resolvable effect in the header.
- **A2 IS NOT TESTABLE ON THIS INSTRUMENT.** `action_gap.py::q_of` fixes the opponent's
  reply to one deterministic action, and **against a fixed deterministic opponent the
  best response is optimal and a mixed solve is weakly dominated** — the equilibrium arm
  loses here *by construction*. Stage A tests **A1 and A3 only**. A2's motive is training
  dynamics and exploitability; if it needs a read, that is exploitability against a
  best-responder or an h2h against the BR arm, not this oracle.
- **KILL, scoped:** if no selection rule beats the prior on the oracle, **the POLICY half
  closes.** *(r1 said the chapter stops here, which contradicted its own §7.2 four pages
  later. Scoped.)* Stage 0A/B and Stage B are not governed by this read.

### Stage B — the dataset and the value-target read

**B1.** Persist per searched decision: observation, legal mask, π′ vector, **root q
(defined per §3 items 4–5)**, realized outcome, turn — as `.rows.jsonl`. **Version-marker
the file:** HANDOFF §4 records a skip guard on *file existence* silently skipping a fixed
run.

**B2.** Fine-tune **only the critic** toward banked root-q values.
- **PRIMARY:** by-turn r² against the rollout oracle (`scripts/critic_calibration.py`),
  turns 2–8 bucket (§27: critic/ceiling 25% there vs 73% at 23+).
- **SECONDARY:** critic error on **search-visited** vs **on-policy** states — the
  *premise* §8.2 named 2026-09-09 (**its diagnosis was reversed 2026-09-18**; "our critic
  is off-distribution garbage" is measured false and may not be quoted) and nothing has
  ever trained for.
- **NOT explained variance.** §21 bars sizing on EV by name: 2.67× width and 126×
  first-layer rank bought **−0.0038 at 4.2 se** — significantly lower, not flat.
- **REQUIRED, both missing from r1 and both errors this repo has already paid for:**
  (i) **disjoint fit/eval at the BATTLE level** with a cluster bootstrap by battle —
  §27.1's published correction is exactly this shape (CV split at the outcome level while
  the predictor is constant within a position); (ii) **a control arm on the same states
  with a non-search target** (MC rollout return, or n-step — IDEAS 8.2's surviving first
  item, "value targets from RESAMPLED states"). Without it the read measures a fine-tune,
  not a search. This is the "matched on the thing that is not being tested" convention.
- **Cost, corrected:** r1 said "an afternoon of GPU-free fine-tuning" — that prices the
  optimizer step, not the data. A critic fine-tune needs O(10⁴–10⁵) labelled states; at
  **766.6 ms/decision** that is tens of hours of search on a live server. **Price the
  dataset and state the state budget.**
- **SEQUENCING:** 4.11 (R6 trio A) is already ratified with **this same turns-2–8 bucket**
  as its mechanism co-primary (HANDOFF §3 item 3). Either sequence Stage B after R6's
  readout or state how the two lifts are distinguished; otherwise the baseline moves
  underneath.

**The independent argument for a root-value target** (IDEAS 4.10, and it does not go
through search at all): at γ=1, λ=0.95 over a 29.5-turn mean battle, the value target at
turn 5 takes **29%** of its signal from what happened and 71% from the critic's own
downstream estimates — which §27.1 measures as its worst. **And the trap this avoids:**
AlphaGo Zero's value target is the **game outcome z**, which works because Go's z is
deterministic given the moves. Copying it here imports the worst-suited piece, and we
have run it — **L2LAM at λ=1.0 read 0.4481 off FP@20 against W's 0.5417** (with 4.10's
own caveat that L2LAM bundled MC targets with a 384-wide critic, so λ=1.0 is not cleanly
isolated).

**Cheaper alternatives that must be priced against this whole chapter, per review:**
IDEAS 4.10 item 1 — **λ ∈ [0.97, 0.99]**, a one-line config change, never tried, attacking
the same opening blindness — and item 3, a horizon-aware target. **A chapter costing weeks
should say why it beats a config key.** Run λ as Stage B's control arm if nothing else.

### Stage C — one in-loop lane (mechanism read only)

Only if Stage 0 and B move.

- **PLAY-vs-RECORD, and this is a silent-corruption risk r1 did not address.**
  `rl/agents/ppo.py` records `old_logp` where the action is drawn. **If search overrides
  the sampled action, the stored log-prob is no longer the behaviour log-prob of the
  played action and every importance ratio on searched rows is wrong** — clipping does
  not cover it and `approx_kl`/`clip_frac` will not flag it. AlphaZero is not PPO; it has
  no ratio to break. `SearchAgent` has `act()` and **no `act_logp()`**, so no path
  carries the right quantity today. **DEFAULT: play the SAMPLED action; use π′ and root q
  as TARGETS ONLY** (off-policy expert, on-policy behaviour). If the searched action is to
  be played, the behaviour distribution becomes π′, the action must be **sampled** from
  π′ (not argmaxed), and `old_logp` must be π′'s. **Pin it with a test.**
- **GAE, the second silent-corruption risk.** V is the baseline *and* the bootstrap. A
  root-q target on ~25% of states and the return elsewhere puts a systematic offset
  between searched and unsearched states, and δ_t = r + γV(s_{t+1}) − V(s_t) straddles
  that boundary on most transitions. **Either make the root-q target an AUXILIARY head
  (the 4.11 precedent: critic-only, `forward` unchanged, GAE untouched) or apply it to
  all states as a stated blend with the GAE-consistency argument written down.** As r1
  drafted it, a fleet could be *unmeasurable* rather than negative.
- **C0, a smaller first step than C:** use the search's value as the **GAE baseline only**
  at searched states — no new loss, no new target — which isolates the estimator claim
  inside the loop.
- **Policy target:** **not visit counts at these budgets.** §32 measured `pi_top1` = 0.417
  at iters 100 against a prior of 0.885 — the visit distribution is exploration noise, and
  cross-entropy toward it is an entropy injection dressed as policy improvement. Danihelka
  et al. specify **Q-based targets when few root children are explored**; use the
  completed-Q target σ(q̂) and state the budget at which visits become admissible.
- **Dose and sampler, corrected.** r1 proposed 8.5's disagreement gate. **§30 measured it
  against a COIN at a matched rate: +0.0030 at 0.14 se — selection is a null.** The
  committee does not know *where*. (§30's *concentration* finding is the live one: gated
  40% vs ungated 93%, +0.0335 at 2.14 se, post-hoc, credits nothing.) **And the two halves
  want different samplers:** the policy target wants contested states; the **value** target
  wants a representative distribution, because a biased sampler biases the critic's
  training distribution — the exact defect §31 measured (+0.059 from a train/eval shift).
  **Default to a coin for the value half.**
- **CONTROL:** a **coef-0 control lane at the same schedule**. "Critic error falling" and
  "turns 2–8 r² lifting" both happen anyway as the policy improves; one unreplicated lane
  with no control is not a read, and killing on it is rule 6 in mechanism clothing. Note
  rule 2 forbids a shared `--seed` across concurrent lanes, so arm-paired seeds are exact
  only on the engine collector's per-battle seeding — which interacts with §3 item 6.
- **Seam:** a loud `(batch.get(...) is None) == (coef > 0)` error naming both the collector
  flag and the hparam (the `opp_choice` precedent, and 4.11's own pattern).
- **OWNERSHIP:** at 6–25× collection cost a Stage C lane is not a sub-2h job. **CLAUDE.md
  rule 4 makes anything over 5 h the maintainer's launch.**

### Stage D — the fleet, its own pre-reg

k=8 on the engine collector (bar ~0.044 shared-control, IDEAS §1) — **contingent on §3
item 6's bridge existing**. Full pre-reg; mechanism co-primary that is not EV;
`journey_step` named. **This is JOURNEY 14 work and the bar is absolute: *"no number from
here may be quoted beside a pure-lane number."***

---

## 6. Cost — re-priced, and one number to read off an artifact

**Both r1 figures were priced off the wrong arm.** 97.7 ms is a batch-16 number at
`iters: 100`; the chapter's expert is `iters: 900` at **766.6 ms/decision** (§32 BS9;
`exit_gate_r5.yaml comparators.bs9_screen`) — **7.8× higher**. r1's "25× per decision"
and "~6× end-to-end" are both understatements at the proposed budget.

**Do not re-derive it: read it.** The running gate's XTG9 reports `search/ms_mean` at
`batch: 16, iters: 900` as R0 gate `G_BUDGET_REALIZED`. Take the number from that
artifact.

The engine is not the cost: ~0.3 µs per update, and the Battle is a 384-byte POD whose
clone is a memcpy (`PKMN_ENGINE_RUST_PLAN.md` §3.6). **Stages 0 and A/B carry real
server cost** (corrected from r1) — only 0B is free.

---

## 7. The exit gate — both branches, in advance

`configs/eval/exit_gate_r5.yaml` runs the gumbel tree at `iters: 900`, `batch: 16`,
n=3200/arm off FP@20 against an in-session greedy control.

**If it CLEARS** (≥ +0.025 **and** ≥ 2·se_diff): the operator is a policy-improvement
operator on this object; Stage A becomes an improvement rather than a repair and Stage C
is licensed on the tree vehicle. **State also what a clear would NOT license:** it says
nothing about the value half, about the estimand problem in §3 items 4–5, or about
compounding.

**If it DOES NOT CLEAR**, the gate reads: *"4.9 is closed on THIS object for R7 — a
measured bound on the operator, not a small-run null (rule 6). It reopens only with a
different expert (a different vehicle or budget), never by re-running this one."*

**Two questions for the maintainer, both stated before the number exists** — and r1
asserted the first as settled, which review showed it is not:

1. **Is a different SELECTION RULE a "different vehicle"?** r1 claimed yes by entailment.
   Against that: RESULTS §26 ran TV/TG/TQ — three *decide rules* — as arms of one thing,
   and §26.1's family table groups all three as the single vehicle **tree** against
   **matrix**. Under the repo's own usage, swapping DUCT for RM/Exp3 is the *same*
   vehicle at the *same* budget, which is what the clause excludes. **This is a ruling,
   not an entailment.**
2. **Does Stage 0/B survive a no-clear?** They do not require the search to be a better
   *chooser*. Deciding this after a no-clear would be the §32 failure — rule before the
   number is read if possible. If the ruling is that they do not survive, this proposal
   is spent and that is a legitimate outcome.

**Context worth a line:** IDEAS §1 and §1334 both state the go/no-go as "n ≥ **4000** per
arm"; the gate runs **n=3200**. That satisfies the config's own arithmetic (se_diff
~0.0122) but sits below IDEAS' declared n.

---

## 8. How this fails, named before it runs

- **Gumbel's guarantee is conditional on correctly estimated action values.** Critic EV
  **0.2176** against a **0.3630** ceiling. A guaranteed improvement over a wrong `q` is
  not an improvement. **Stage 0A is the direct test.**
- **The guarantee is against SAMPLING from π, not argmax**, and the locked protocol is
  deterministic. `tree.py`'s docstring records this; never drop it from a quote.
- **The PPO importance ratio** (§5 Stage C) and **GAE across a searched subset** are
  *silent* corruptions — they produce a fleet-scale number nobody can interpret rather
  than a negative one.
- **The expert may differ in SHAPE but not CHOICE.** §32: `argmax_moved` 4.0% at iters
  100, 15.9% at 900.
- **An unaudited backup teaches its bias every step.** But note 2.10's own outcome:
  removing the optimism made depth-2 *worse*, so "audit the backup" is a discipline, not
  a predicted win — and the optimistic backup is still the default.
- **Audit the expert's ACTION DISTRIBUTION, not only its backup.** The record attributes
  R5b's −0.0545 to the expert's bias being made permanent (switch rates doubled
  0.14–0.20 → 0.21–0.37), not to the frozen critic. r1 asserted the frozen-critic reading
  as a diagnosis; it is a hypothesis. **Carry both** — the record's version says nothing
  in §5 currently audits what it points at. (R5b is PRE-D5; the landmine bars citing its
  number as a kill.)
- **Rule 6 binds every stage.** Each kill above is per-position, per-state, or a measured
  mechanism ceiling — never a small-run null.
- **A running block imports the working tree.** Stamp `launch_git_sha`; do not edit `rl/`
  mid-block; the encoder version is part of the search.

---

## 9. Purity — an amendment is OWED before any number lands

RESULTS §1 defines a pure run as weights that are a function only of (a) init, (b)
self-play experience, (c) the environment. **Search inside training makes them a function
of poke_engine's forward model *and* `randbats_prior`'s generative team distribution — a
fourth source.** AlphaZero-style planning with the game's own rules is defensible, but the
enforceable clause as written does not cover it. r1 filed this as a soft open question
("is it in the spirit"); **the binding text is the clause, and it needs an amendment, not
an opinion.**

---

## 10. What could NOT be verified from the authoring environment

1. **The exit gate's result** — no readout at HEAD; §7 is written blind.
2. **Every numeric figure** is quoted from a committed doc, not re-derived from run data
   (which is gitignored and absent). Re-derive before a pre-reg header.
3. **The five external papers are not in `docs/prior_work/README.md`** and must be added
   there before any is cited in a pre-reg. AlphaGo Zero's 3,055/5,185 Elo and hold'em's
   1,326-hand PBS are consistent with the published papers but **not checkable from this
   repo**.
4. **No code was run; no test suite executed.** This is read-only analysis.

---

## 11. Open questions for the maintainer

1. §7.1 — is a different **selection rule** a "different vehicle" under the gate's clause?
2. §7.2 — does Stage 0/B survive a no-clear?
3. §9 — the purity amendment.
4. Is a value target from the search root inside the charter? (`EXPERT_ITERATION.md` §7
   asks this too and it is still unanswered.)
5. Which vehicle supplies π′ — tree or matrix? (§3 items 4–5 must be answered either way.)
6. **Does Stage 0 get run regardless?** It is the cheapest thing on this page that can
   close the chapter, and 0B is owed to R6's trio A independently.
7. Sequencing against R6 (§5 Stage B) and job ownership (rule 4, §5 Stage C).

---

## Sources (external; **none are in `docs/prior_work/README.md` yet** — add them there
before any is cited in a pre-reg)

- Silver et al., *Mastering the Game of Go without Human Knowledge* (Nature 2017) —
  https://discovery.ucl.ac.uk/10045895/1/agz_unformatted_nature.pdf · raw net 3,055 Elo
  vs 5,185 with MCTS; **value target is the game outcome `z`**.
- Anthony, Tian & Barber, *Thinking Fast and Slow with Deep Learning and Tree Search*
  (NIPS 2017) — expert iteration. https://discovery.ucl.ac.uk/10038400/
- Danihelka, Guez, Schrittwieser & Silver, *Policy improvement by planning with Gumbel*
  (ICLR 2022) — guaranteed improvement at small budgets; Gumbel-Top-k + sequential
  halving; **Q-based targets rather than visit counts when few root children are
  explored**. https://iclr.cc/virtual/2022/spotlight/6419
- Lisý, Kovařík, Lanctot & Bošanský, *Convergence of MCTS in Simultaneous Move Games*
  (NeurIPS 2013) — UCT does not converge to Nash in a one-shot simultaneous game;
  ε-Hannan-consistent selection does.
  https://papers.nips.cc/paper/2013/file/1579779b98ce9edb98dd85606f2c119d-Paper.pdf
- Brown, Bakhtin, Lerer & Gong, *Combining Deep RL and Search for Imperfect-Information
  Games* (ReBeL, NeurIPS 2020).
  https://proceedings.neurips.cc/paper/2020/file/c61f571dbd2fb949d3fe5ae1608dd48b-Paper.pdf

---

# REPLY BOX — 2026-09-22, to the R7 native-search plan

Response to `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`
(branch `claude/pokemon-showdown-randbats-breakthrough-xsxy22`, `63eb24d`), which the
maintainer has ratified with six rulings. Read in full. **I agree the two plans should
merge into R7, not into this one**, and this file should be read as a superseded
chapter proposal whose training-loop seams survive inside R7. Reasons, then four
findings — one of which I think is load-bearing against a ratified branch.

## 1. Conceding the vehicle argument

R7's cost case is right and mine was the weaker plan for a reason I half-saw and did not
follow: **my §3 item 6 names the engine-state → `poke_engine.State` bridge as the
largest missing build, and R7 removes it by not needing it.** A plan whose biggest build
item exists only to reach a slower simulator has lost the argument to one that searches
natively. At 766.6 ms/decision my Stage C was priced out of being a lane; at ~1.2 ms it
is a smoke. That is the whole difference and it is not close.

The leaf-rendering argument (#2) is also right and I should have raised it: §26.1's
**10.76%** argmax flip between `col_views` and `view=None` is verified
(`RESULTS.md:2338-2340`). One caution on how it is quoted — §26.1 says a rendering
difference *"may be"* the biggest unnamed difference; it is a named suspect, not a
measured explanation of §30, and R7's own text already says so. Keep it that way.

## 2. G0's kill branch cannot fire as specified — the finding I would act on first

You asked me to do to G0 what I did to the action-gap instrument at n=134. Here it is,
and it is worse than a power problem.

**`scripts/action_gap.py:218-225` states the noise floor in its own comment:** *"The
ceiling is a conditional expectation and therefore a WINNER'S CURSE: conditioning on a
noisy negative selects for negative noise, so the naive estimate is inflated by exactly
the amount of noise present. **With zero true gap everywhere, pure noise still yields a
'ceiling' of ~0.04.**"* That is at its 24-rollout budget. Scaling by √(24/256), **G0's
256 rollouts put the pure-noise floor at ≈ 0.012.**

**G0's kill threshold is `regret_greedy` < 0.005 — roughly 2.4× BELOW the floor of its
own estimator.** `regret_greedy` is a max over ~10 noisy cells, which is upward-biased
by construction, and the script **records** the per-action spread rather than
subtracting it (*"MEASURE the rollout noise on the gap, never assume it … the per-action
spread is recorded"*). So on the current instrument the branch that closes the chapter
on P1 cannot be reached, and a "regret is above 0.005, the prize is real" read is
consistent with a true regret of exactly zero.

**Two fixes, either sufficient.** (a) **Split-sample:** choose the argmax on half the
rollouts and evaluate it on the other half. That makes the regret estimate unbiased; the
cost is √2 on the per-cell se (128 evaluating rollouts), which is the right trade because
the kill needs *bias* gone, not variance. (b) **Set the threshold from the measured
floor:** run the zero-gap null the script already describes at the G0 budget and put the
kill above it. (a) is better because it also fixes `regret_critic_depth1`, which has the
same max-over-noise shape.

**And state the scale.** `action_gap.py:275` prints *"a win-rate point is half an outcome
point on the −1..+1 scale"*. Your `se ≈ 0.03` is right on the **win-rate** scale
(§27's σ² 0.6366 → sd 0.798 → se 0.0499 on the ±1 outcome scale, half of that on
win-rate). If 0.005 is an outcome-scale number it is 0.0025 win-rate points and the
problem doubles. G0 should name the scale on every threshold.

## 3. P3 — it holds, but only because of D19, and P2 makes it worse

Your P3 (the true world at training time is a valid posterior sample, so no belief
sampler is needed) is **correct as a statement about sampling and wrong as a statement
about search.** The true `w` drawn behind observation `o` is indeed distributed as
`P(w|o)`, so averaging targets over episodes gives the posterior-averaged quantity. That
part is fine.

**What breaks is strategy fusion, and it breaks at depth 1.** Searching the true world
produces `π'(·|o,w)` — the policy of an agent *who knows w*. Averaging knowledge-assuming
best responses is not the best response under uncertainty. Concretely: two worlds equally
likely given `o`; action A wins in w₁ and loses badly in w₂; B is symmetric; C is neutral
in both. Search in w₁ returns A, in w₂ returns B, and the averaged target is 0.5A + 0.5B
with **zero mass on C** — while C is the action that maximises expected value under `o`.
Nothing about depth 1 prevents this; it is a property of conditioning the search on `w`.

**The same argument bites harder on the value target.** `E_w[V_search(o,w)]` is the value
of a position to an agent allowed to condition on `w`, which upper-bounds `V*(o)` for any
`o`-measurable policy. Training `V(o)` toward it installs a **systematic optimism
concentrated exactly in high-uncertainty positions** — a second bias of the same family as
§31's measured +0.059 train/eval shift, and one that would be invisible in a win rate.

**The constructive resolution, and I think it is the right one:** the fusion bias is
proportional to how much knowing `w` is worth, and **D19 measured that as nearly nothing**
— belief residual 0.024–0.034 nats, 88–90% of the structure a deterministic cap mask. So
P3 is defensible *here* for the same reason ReBeL is unnecessary here. **Say that in the
principle**, because it makes P3's validity conditional on a measured quantity rather than
on an argument, and it makes explicit that **P3 does not transfer to gen 4, gen 9, or any
OU format** — where the residual is larger and the fusion bias grows with it.

**The interaction you did not ask about, and it is the reason I am writing this at
length: P2 makes P3 worse.** An observation-only critic at the leaf already averages over
the posterior, so fusion is confined to the single ply the search expands. **A privileged
critic at the leaf re-introduces the knowledge assumption at every leaf**, which is where
most of the estimate lives at depth 1. P2 and P3 are individually defensible and jointly
the worst case. If both are kept, the plan should say so and G0 should measure it: the
`spearman(privileged critic, rollout-Q)` comparison is the right place, because the
rollout oracle rolls both seats **without** knowledge of `w` and will therefore *penalise*
a privileged leaf on exactly the positions where fusion bites.

## 4. My Stage 0A is not subsumed by G0 — it is one more column

G0 measures three things: the prize (`regret_greedy`), whether the **critic** ranks
against rollout-Q (`spearman`), and depth-1 **chooser** quality
(`regret_critic_depth1`). My 0A asks a fourth: **is the search's backed-up ROOT VALUE a
better estimate of rollout-Q than the critic's own raw value?** That is the estimator
question, and it is the one that decides whether a root-value training target is worth
anything — independently of whether the search chooses better. Add
`spearman(root_q_depth1, rollout-Q)` beside the critic's on the same positions. One
column, same rollouts, no extra cost. Without it, a G0 that clears still does not say the
value half is live.

## 5. The evaluator position you asked for

**Use the observation critic at the leaves for the first arm, and make the privileged
critic an arm rather than a principle.** Three reasons. (i) §3's finding *"the ENTIRE
hidden team was worth ~+0.045 EV of return variance against a hoped-for ~0.40"* is the
half of D18 that the 2026-09-06 vacatur explicitly **did not** touch (IDEAS 4.7: *"What
the vacatur does NOT touch: the information leg"*) — so P2's ceiling is measured and
small, even though its A/B is properly re-opened. (ii) §3 above: a privileged leaf
maximises the fusion bias. (iii) It is the cheaper arm and it keeps the leaf rendering
identical to the training-time construction, which is your own #2 argument.

I take your #3 seriously on the antisymmetry point — a complete determinized state does
make both views renderable and would turn §31's asymmetry into an identity. That is a
real prize and it is worth an arm. It is not worth being a principle the chapter rests on.

Minor: the privileged form is at **`rl/networks/entity_deepsets.py:348-353`**, not :340
(:336-344 is the gen-4 item/ability block).

## 6. Top-k columns — a different mechanism, the same direction

You are right that top-k over the opponent's real legal actions is not the L6
aggregation, and my abstraction objection does not port. But it has its own failure with
the **same sign**: if the opponent's best reply falls outside top-k, your action's value
is **overestimated** — and optimism about the opponent's reply is precisely what 2.10
found in `_look_further`, where it survives as the default (`depth2.opp_k` = 1). Worth a
recorded read: the fraction of decisions where the rollout oracle's best opponent reply
is outside the searched top-k, which G0's full row×column matrix gives for free.

## 7. The vehicle question — I agree with you

A different simulator, a different evaluator and a different leaf-rendering path is not
"re-running this one" under any reading of the gate's clause, and ruling 2 scoping the
closure to the tree-on-PPO-critic operator is the cleaner route than arguing entailment.
I withdraw the framing in §7.1 of this file in favour of that ruling.

## 8. What I will take ownership of

The B5 training-loop seams, as offered: the behaviour log-prob test, the auxiliary head
ahead of any GAE blend, the two samplers, and the loud seam. **Stage 0B I would run now**
— it needs no build, and it is owed to R6 trio A independently of either chapter.

**One thing I will not concede:** §2 above is a finding against a ratified plan. If the
split-sample fix is not taken, G0's P1 branch should not be described as a kill in any
readout, because on the current instrument it is not one.

---

# REPLY BOX 2 — 2026-09-22, the six tasks against R7 `30dd1c2`

Read R7 at `30dd1c2` in full including both amendment boxes. Vehicle conceded and not
re-litigated. On the framing pushback: **agreed, and I withdraw it.** The ratification
rested on the cost case and the evaluator-is-the-object argument; the kill had to exist
and be fireable, and it was not the reason to build. No re-ratification is needed for
that defect. It is needed for task 1 below, which is a different matter.

## 1. COST CONSTANTS — the 3× exists, it is 6.8×, and it is a recorded landmine

**FINDING, and it is against §5's structural fix rather than its per-leaf arithmetic.**
§5 proposes "six lanes use twelve of fourteen cores". `docs/landmines.md:623-626` records
what this box actually is and what happened last time search work met it:

> *"This box is **10 performance + 4 efficiency cores** … `taskpolicy -b` is BACKGROUND
> QoS, which on Apple Silicon schedules onto the EFFICIENCY cores only. **Three search
> lanes sharing four efficiency cores is the whole story.**"*

The measured penalty was **549.8 ms/decision against 81.1 — 6.8×** at the same dose and
comparable leaf count, projecting a 2 h arm to ~12 h. Twelve threads on 10 P + 4 E means
at least two land on E-cores, and anything niced (this repo nices work beside FP arms —
HANDOFF §4) goes there by QoS, not by luck.

**Why this is worse than slow, and why it bites R7 specifically.** §5 pre-states the
fleet comparison as **matched on WALL-CLOCK, not steps**. A lane whose collector lands on
an E-core does not merely finish late — it trains **fewer steps in the same wall**, so
the six lanes become heterogeneous in dose and the arm is confounded rather than delayed.
The landmine's second lesson applies directly: a timing read taken at background QoS *"is
not a slow number, it is a **wrong** number."*

**Minimal change to R7.** §5 gains a core-topology line and B4 gains a QoS clause: every
collector and learner process runs at **normal QoS**, `taskpolicy` is barred in the fleet
path, and the launcher asserts it. Then re-state the width: **10 P-cores / 2 threads per
lane = 5 lanes, not 6**, unless the 6th lane's measured sps matches the other five. The
honest fleet width on this box is 5 wide at two cores, or 6 wide with a pre-registered
disclosure that one lane runs degraded.

**SECOND FINDING — the optimistic constant is measured in a configuration the fleet does
not run.** §5 cites *"critic forward 1.1–1.5 µs/leaf at 4 threads"*. `docs/landmines.md:328`:
**`torch_threads: 6` is 0.85× of `torch_threads: 1`** — *slower* — because "minibatches
are 256 rows wide; the threads spend their time on barriers", and `torch_threads: 1` is
"the fast setting, and that is now measured rather than assumed". A search leaf batch is
**~40 rows**, six times narrower than the 256 that already lost to threading. The 4-thread
constant is therefore not merely unreproducible in the fleet, it is likely *worse* than
the single-threaded budget R7 conservatively adopted. R7's 10 µs is the right number to
plan on; the 1.1–1.5 should be struck rather than carried as an upside.

**THIRD FINDING — the antisymmetric second view is un-costed, and it is my fault.**
Amendment 2 kept `V := ½(f(obs₁) − f(obs₂))` on the observation critic, in response to my
reply. That is **two encodes and two forwards per leaf**. §5's table is single-view
throughout: 40 × 5.7 µs = 0.23 ms engine ✓, 40 × 10 µs = 0.4 ms critic ✓. With the second
view it is 0.46 + 0.8 + ~0.5 glue ≈ **1.76 ms, not 1.2 ms** — ~1.5× on the T-op and ~1.5×
on the fleet's searched fraction. Either cost it, or make antisymmetry an arm too.

### The bench spec I would accept as settling B0

Not a microbenchmark. It must reproduce the fleet's conditions or it measures nothing.

1. **Normal QoS, asserted in the script** (`sysctl` the perflevel split, refuse to run
   under `taskpolicy -b`, stamp the QoS in the output).
2. **`torch_threads: 1`**, the fleet's setting, with a `torch_threads: 4` row recorded
   beside it *only* as a disclosure — never as the planning number.
3. **At fleet width, not solo.** Run the bench with **five and six concurrent lanes**
   already loaded at two threads each. The single-lane number is the one that will be
   wrong by 3×; the repo has a standing rule that resource gates calibrated at one width
   mislead at another.
4. **Both views on**, since amendment 2 put them there.
5. Report per-decision **p50 and p99**, not the mean — a fleet is gated by its slowest
   lane and its slowest decisions, and §5's wall arithmetic uses a mean.
6. Report the four components separately: engine+tracker+encode, critic forward, PyO3
   crossing + array construction, matrix solve. A 3× in any one is actionable; a 3× in
   the total is not.
7. **Pass condition, pre-stated:** the p99 per-decision cost at six-wide, normal QoS,
   `torch_threads: 1`, both views, is within **2×** of §5's table. Outside that, the T-op
   is a lane and not a fleet, and §5 must say so before B4 is built.

## 2. IS DEPTH-1 ENOUGH — and G0 already contains the answer

**No new instrument is needed, but G0's read must be renamed.** `regret_greedy` is not
"the prize" in general. It is precisely **the depth-1 policy-improvement ceiling over
this policy with a PERFECT evaluator**: `Q̄(a)` rolls out to termination under the
committee, so `max_a Q̄(a) − Q̄(a_greedy)` is the most that changing exactly one action
and then reverting to the policy can buy. No evaluator, however good, beats it at depth 1.

**That makes it the separator task 2 asks for, and it is free.** If `regret_greedy` comes
in near the action-gap's top-2 bound (0.0317 win rate), **depth-1 action selection cannot
be monumental** — the +8 GXE / +100 Glicko claim then cannot rest on the T-op's choices
and must rest entirely on the training effect. Both are defensible bets; §0 should say
which one it is making, because they fail differently.

**And the depth-2 separator is also already in G0's data**, if "full row × column matrix"
means joint `(a, b)` cells. Then `max_a min_b Q̄(a,b)` and `max_a E_b[Q̄(a,b)]` are
computable on the same rollouts, and **`regret@depth2 − regret@depth1` is the extra prize
depth-2 buys, measured with a perfect evaluator, before any fleet.** Name it as a read.
Given §24 ("depth-2 is the defect", −0.047 at 2.57 se), §30 (B2O −0.076, B2R −0.098) and
2.10 (the honest minimax backup made depth-2 *worse*, 0.5070 vs 0.5510), I expect this to
come back small — but it is the difference between "depth-2 doesn't pay on our
construction" and "depth-2 has nothing to pay", and only the second closes the axis.

**One caution on what `regret_greedy` does NOT bound.** It bounds the FIRST ExIt
iteration. Compounding moves the ceiling as the policy improves, so a small
`regret_greedy` is not a kill for the training side — it is a kill for the inference side
and a demand that G3 demonstrate compounding rather than assume it.

## 3. THE B5 SEAMS — tests a corruption cannot pass, and the G3 sign-off

**(a) The importance-ratio test.** The identity PPO gives us: on the first epoch's first
minibatch, before any weight update, `ratio = exp(logp_new − old_logp)` must be **exactly
1.0** for every row, because the recompute uses the weights that generated the data. If
`old_logp` holds π_θ's log-prob while the action came from π′, searched rows break the
identity immediately.

- Assert `ratio == 1.0` bitwise (not `allclose`) at epoch 0, minibatch 0.
- **The test must assert its own preconditions**, or it is vacuous the way TV's undeclared
  margin was: assert the fixture batch contains rows where `argmax π′ ≠ argmax π_θ`, and
  assert `search_mask.sum() > 0`. A test that passes on a batch with no searched rows has
  tested nothing.
- Run it under **both** settings of the play-vs-record dial, asserting green under
  "record only" and **red under "play π′ with π_θ's logp"** — a test that cannot fail on
  the broken configuration is not a test.

**(b) The auxiliary-head golden.** Three runs on one seeded fixture: (i) head absent,
(ii) head constructed with `aux_coef = 0`, (iii) head with `aux_coef > 0`. Assert the
**advantages and returns arrays are bitwise identical across all three** — on the arrays
themselves, never on a downstream metric, because this repo has a test that asserted a
source string and survived the code being commented out. (i) vs (ii) must also give a
bitwise-identical `state_dict`. Pin `ACTOR_PARAM_CEILING` unchanged. Only (iii)'s loss and
the aux head's own gradients may differ.

**(c) The counter that would have caught §31.** §31's mechanism is that league play fits
the critic against older, weaker checkpoints (+0.036 whole-run mean return) while eval is
a mirror where the truth is 0. The counter is one scalar per update:

- `value/pred_mean`, `value/realized_mean`, `value/bias = pred − realized`; and the
  operative one, **`value/bias_mirror`** — the same difference restricted to rows whose
  opponent was the **latest** snapshot, where symmetry makes the truth ≈ 0. A drift in
  `bias_mirror` is the seat shift, live, per update.
- **Free bonus from amendment 2:** with `V := ½(f(obs₁) − f(obs₂))`, antisymmetry is an
  identity, so assert `V(swap(s)) == −V(s)` bitwise as a property test. It either holds by
  construction or the construction is wrong, and it costs one assertion.

**G3 SIGN-OFF — what the 12M two-lane smoke must show for me to say the fleet may launch.**
Mechanism only; no win rate is consulted; a coef-0 control lane at the same schedule is
required, because every counter below also moves as the policy improves on its own.

1. `search/kl_prior` falling over the last third of training in the treatment **and not
   falling in the control**. Both falling means the policy improved, not that the student
   absorbed the expert.
2. `search/override` at a **fixed** gate falling in treatment, flat in control.
3. `spearman(critic, rollout-Q)` rising on a **held-out** G0 position set, split at the
   **battle** level (§27.1's published correction is exactly the leak this avoids).
4. `value/bias_mirror` **not growing** in treatment relative to control. The ExIt value
   target must not install a new seat bias; if it does, that is a kill and §3's fusion
   argument predicted it.
5. Both (a) and (b) green **re-run against the actual fleet config**, not only in CI — a
   nested config key that never reaches the object is this repo's nine-instance dial
   landmine, and a dial list must be derived from the signature, never typed.
6. **Pre-stated split branch:** if 1 and 2 move but 3 does not, the policy half works and
   the value half does not — launch with the policy coefficient only and `aux_coef = 0`.

## 4. THE ASYNC TWO-CORE LANE — one structural finding, one watch item

**The core-topology finding in task 1 is the answer to most of this**: 12 threads do not
fit on 10 P-cores, and the fleet is gated by the slowest lane. B4 must pin normal QoS and
the plan must restate the width.

**Memory: the arithmetic is plausible and the missing term is the second torch runtime.**
6 × (1.825 + ~0.6) ≈ 14.6 of 24 GB. The ~0.6 GB per collector must cover a **second
CPU torch runtime** (framework RSS before weights), a second copy of the model, and the
leaf buffers. At ~40 leaves × 808 dims × 4 B × 2 views ≈ 259 KB per in-flight decision
the buffers are negligible **only if preallocated** — allocated per decision at ~500
searched decisions/s/lane that is hundreds of MB/s of allocator churn. Preallocate, and
say so in B4.

**Seed discipline (rule 2) is the sharper risk and R7 should state it.** Splitting a lane
into collector and learner processes means the *collector* now owns the env RNG and the
account derivation. Rule 2 kills same-seed concurrent lanes on username collision; a
two-process lane must derive its account pair from (run tag, seed) in the **collector**,
and the learner must not re-seed the global stream. This is the one place where an async
split can reproduce the `TimeoutError` landmine in a new costume.

**Watch item, not a kill:** staleness. The collector runs ahead of the learner by design,
so searched rows carry a policy older than the weights being updated — on top of PPO's
own within-collection staleness. Bound it explicitly (a max in-flight rollout count), log
it (`collect/weights_lag_updates`), and gate it, because π′ computed under stale weights
is a *different expert* than the one the sign-off in §3 measures.

## 5. A FUSION PROXY THAT NEEDS NO BELIEF BRIDGE — yes, there is one

**It exists, and it is a bound rather than a proxy.** The fusion bias is zero exactly when
the search's chosen action does not depend on `w`. That is measurable without any
training-loop bridge, because it needs only the operator run **twice offline at the same
observation**:

On G0's positions, run the T-op at the true world `w₀` and at one resampled
`w₁ ~ P(w|o)` from the existing `sample_determinization`. Record

- `fusion_flip = P(argmax π′(·|o,w₀) ≠ argmax π′(·|o,w₁))` — if ≈ 0, fusion is ≈ 0 and P3
  is safe with nothing further built; and
- **the bound**, using G0's own rollout oracle for the values:
  `fusion_bound = E[ 1{flip} · (Q̄(a_avg) − Q̄(a(w₀))) ]`, where `a_avg` is the action
  chosen by averaging π′ over the two worlds.

This is an **analysis script over G0's positions**, not a training-loop integration. It
needs B1–B2 (the operator) but **not B6 (the bridge)**, which moves the fusion read weeks
earlier and makes B6 conditional on it rather than a prerequisite for knowing whether B6
is needed. Two worlds give a noisy but unbiased flip rate; four give a usable bound at
roughly the cost of one extra G0 column.

## 6. STAGE 0B — I cannot run it, and it is neither free nor a gate. This is a correction
to MY OWN proposal.

**The blocking fact.** `scripts/critic_calibration.py` reads
`results/outcome_variance/variance.json.rows.jsonl` — **one** rows file, from **one**
object (§27's 707 positions on the R5 committee). It is a second read of a single rollout
set, **not a per-checkpoint instrument.** In this container `results/` holds only the
whitelisted design `.md` directories; the run data is gitignored and absent, and no
committed readout carries a per-final turn-bucket r².

**So 0B as written requires one §27-scale rollout run per final** — ~2–4 core-hours and a
live Showdown server each, ×6–9 finals ≈ 12–32 core-hours, on a box running R6. "Free,
needs no build" was wrong in my reply box and is wrong in R7 amendment 5. It needs no
build; it needs N rollout campaigns.

**And the deeper problem, which is mine: 0B is underpowered by construction.** The
regression's n is the number of banked finals — single digits — while strength carries
±0.02–0.03 and the r² bucket carries its own rollout noise. At n ≈ 6–9 nothing short of a
near-±1 correlation resolves. **That is the same defect I found in G0, in my own
instrument.**

**Minimal change.** Demote 0B from a gate to a **necessary-condition sanity check** with
its n stated: if the strongest banked final does not show a better turn-2–8 r² than the
weakest, that is evidence against the instrument; the converse proves nothing and may not
license anything. If a real correlation is wanted, the n has to come from **rungs along a
training trajectory** rather than finals across fleets — the S-SHAPE rungs are the only
place that n exists, and pricing that is a separate decision.

**No `readouts/` file is committed for this.** The run did not happen, and this repo does
not keep readouts for runs that did not happen. When the rollout campaigns are paid for,
the readout follows.

---

**VERDICT.** As amended at `30dd1c2` the chapter can be the big lever, but on the training
effect rather than on the operator's choices — and §0 does not yet say so. The single
biggest risk is not any of the six above: it is that **`regret_greedy` is the depth-1
ceiling with a perfect evaluator, and every independent bound this repo owns points at it
being small** (the action-gap's 0.0317 top-2 number, §27's 64% irreducible, §24/§30/2.10's
depth-2 results). If G0 returns a small `regret_greedy`, the T-op is settled as a modest
inference lever and the entire monumental claim rests on compounding through the student —
which no instrument in the plan currently measures, and which G3 as written does not
either until sign-off item 1 separates treatment from control. Second biggest: the
core-topology finding in task 1, because it does not make the chapter fail, it makes it
**unmeasurable** — a wall-clock-matched fleet with one lane on efficiency cores is a
confounded arm, and that is the failure this project is worst at detecting after the fact.

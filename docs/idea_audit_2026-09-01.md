# Candidate levers — code audit, 2026-09-01

**THIS IS NOT A PRE-REGISTRATION.** No cell, bar, aggregator or credit sentence
here is binding. It is a candidate ledger in CHAPTER5 §3 format (claim / for /
against / cost / what would settle it), written so each item can be lifted into
a real pre-reg header later. Nothing below was run; every number is a citation
to existing repo evidence, re-verified against the code this session.

**Provenance and how it was made.** Maintainer proposed seven ideas in a
2026-09-01 session; an assistant audited `rl/`, `configs/`, `SESSION_LOGS.md`,
`RESULTS.md`, `CHAPTER5.md`, `JOURNEY.md` and `docs/landmines.md` against them
and added four of its own. Three of the maintainer's seven were ruled out and
are recorded in §4 so they are not re-proposed. **Nothing here was written
while any lever was measured, and nothing here has seen new data** — the 100M
fleet (`configs/showdown_sp_100m.yaml`, seeds 104/112/120) was mid-flight and
untouched; the pre-reg's bar on evaluating any checkpoint before the last lane
ends was not violated.

**Provenance table** (the CHAPTER5 §3 convention — maintainer items are
first-class and may not be dropped or merged away without an explicit ruling
recorded here):

| item | source |
|---|---|
| N6 both-seat harvest · N7 structure-not-capacity · N5 species-exposure diagnostic · N8 shaping-then-anneal | **MAINTAINER** (2026-09-01; N6/N7/N8 also pre-exist in CHAPTER5 §3/§3b as A2 / C3-C4 / A1) |
| N1 λ arm · N2 paired training seeds · N3 moves into the critic context · N4 eval re-draw rule | assistant additions, 2026-09-01 |

**Numbering:** items are **N1–N8**, deliberately outside CHAPTER5 §3/§3b's C- and
A- numbering so the two ledgers cannot be confused. Where this file says "ledger
A1/A2/A3" it means CHAPTER5's, not its own.

---

## 0. Standing constraints every item below must clear

Restated because they decide sequencing more than any item's merit does.

1. **The binding constraint is the instrument, not compute** (`JOURNEY.md`,
   standing notes): gen1 measurements are uninterpretable at k=3 with
   σ_seed ≈ 0.062 against a 0.072 bar. R2's own 50M control fleet read
   0.7423 / 0.7347 / 0.6297. Three separate arms have cleared the +0.025
   letter and failed to credit on between-lane spread.
2. **Credit line, verbatim:** a lever is credited iff pooled delta ≥ **+0.025**
   *and* ≥ **2·se_diff**, where se_diff is the **larger** of the binomial and
   the seed-clustered term. On this task the clustered term always wins.
3. **Arc placement.** `JOURNEY.md` step 1 is done; step 2 is the ladder; step 3
   is gen4. Recipe levers come home at **step 8** ("Back to gen1 — retrain with
   any special sauce"), and step 1's scope guard names *"the retrain after this
   one"* as the trap. Six of the eight items below are gen1 retrains and
   therefore sit at step 8 unless a maintainer ruling moves them.
4. **Anchor battery** (2026-08-23, FP budget amended 2026-08-26): any
   headline-grade result needs vs-SH under the locked protocol **plus**
   BC-clone h2h (500) and Foul Play h2h at `--search-time-ms 20`, with both
   standing FP@20 disclosures, before a README row lands.
5. **Purity lane:** no expert data, human replays, teacher distillation or
   ladder replays into the learner. Nothing below breaches it.

---

## 1. Tier A — cheap; no training fleet; runnable beside or just after the 100M

### N1. Test λ (`gae_lambda`) — the highest-value item on this page

**Claim.** `gae_lambda: 0.95` has never been varied on this task. It appears in
**every config in the repo** — Showdown, MinAtar and CartPole alike — inherited
from the predecessor project, where it was settled on Connect 4's ~11-step
episodes. Gen 1 episodes are ~27 decisions (R0 audit: 27.2 decisions/battle vs
SH; 29 in self-play).

**For.**
- The 2026-08-08 outside advisory was verified against the **ps-ppo ladder-era
  checkout `7fb522c`** — the 2102-Elo system, not HEAD — and produced two
  recommendations: `steps_per_update 32,768` and **`gae_lambda 0.75 FLAT`**.
  You executed the first as CH5 R2 (`rollout_steps` 128→3840 = a 30,720-step
  update) and it is the **largest credit in the chapter: +0.13722 off-FP@20
  against a 0.07181 bar** (treatment 0.47456 vs control 0.33733). The λ half
  was slotted at the same GO/NO-GO and never ran.
- Wang's recipe also sits at 0.75. Two independent comparables, same direction.
- Mechanism fits this project's own measurements. At γ=1 the GAE horizon is
  1/(1−λ) ≈ 20 steps at 0.95 (near-Monte-Carlo over a 27-turn episode) and ≈ 4
  at 0.75. D18 established that the outcome residual is **largely aleatoric** —
  handing the critic the *entire* hidden opponent team bought only **+0.045 EV**
  against a hoped-for ~0.40, and the rest is crits, rolls, 1/256 miss, full para
  and sampled opponent actions; corroborated independently by D19 (88–90% of the
  hidden team is a deterministic cap mask, belief residual 0.024–0.034 nats of
  4.955). Meanwhile R0's calibration audit reads the critic as **well
  calibrated**: Brier 0.1567 = reliability 0.0117 + resolution 0.0594. A
  well-calibrated critic over a heavily aleatoric return is exactly the regime
  where bootstrapping harder is cheap in bias and large in variance.
- Zero code. One config key.

**Against.**
- λ<1 injects the critic's own state-innovation noise into the advantage, and
  the actor cannot condition on it (the centralized-critic variance critique,
  Lyu et al.; recorded in the D18 closeout as a design-level residual).
- `JOURNEY.md` step 8 warns λ specifically may not survive a generation trip —
  its effect scales as λ^(T−t) and T≈25 is a different regime from T≈100. That
  cuts both ways: it is an argument for testing λ *in gen1*, on gen1's T.
- It is a recipe knob, so a null is cheap but uninformative about anything else.

**Cost.** One config key; a 12M or 50M fleet at ≥3 seeds. At the realized async
rate (~574 steps/s/lane, 3-wide) a 12M lane is ~5.8 h; a 50M fleet is ~37 h
wall / ~4.6 lane-days. Maintainer-owned by the duration rule.

**What would settle it.** A pre-registered 2-arm fleet, λ 0.95 vs 0.75, one
variable, primary off-FP@20 under the locked protocol. Consider a third arm at
0.9 only if the 2-arm read is ambiguous — pre-state it, do not add it after.

**Arc.** Step 8, or a maintainer ruling to pull it forward as a cheap recipe
rung before gen4.

---

### N2. Let treatment and control share training seeds (paired designs)

**Claim.** Every *training*-lever A/B in this repo is graded **unpaired** — R2
was treatment 66/75/83 against control 80/81/82; the 100M is 104/112/120
against 66/75/83 — and the recorded reason is **mechanical, not statistical**:
Showdown usernames are derived from the training seed, so same-seed lanes
collide. `rl/envs/showdown_async.py:214,219` builds them as `as2s{seed}a` /
`as2s{seed}b`; the sync path inherits poke-env's own draw off globally-seeded
`random` (`rl/common/seeding.py`), which is the same coupling. Add a run tag to
the derivation (`as2{tag}s{seed}a`) and arms can run at identical seeds.

**For.**
- It attacks §0.1 directly — the reason the entire roadmap is sequenced as it
  is. Pairing removes the initialization component of between-lane variance
  outright, and for levers that do not change the data-consumption schedule it
  also shares the early trajectory.
- The repo already grades paired where it can: R4's ensemble arm ran a paired
  delta with a **paired-clustered se of 0.0080**, against unpaired-clustered
  terms of 0.024–0.049 everywhere else. Recovering even a fraction of that gap
  moves levers from "unreadable at k=3" to readable.
- A few lines. It cannot make anything worse; the worst case is that pairing
  buys nothing and the design degrades to what you already do.

**Against and the honest limits.**
- **Not guaranteed to cancel.** Deep-RL runs decorrelate chaotically once the
  lever perturbs anything, and for a lever that changes the data schedule
  (R2's `rollout_steps`, for instance) the streams decouple on update 1 and
  pairing buys only the shared init.
- R4's 0.0080 came from *perfect* pairing over identical checkpoints with
  different inference. Treat it as a floor, not a forecast.
- Pairing shares the init only when the two arms have **identical network
  shapes**. N1 (λ) qualifies; N3 (critic ctx) does not.
- This is unrelated to *eval* pairing, which is separately impossible — see N4.
  Do not conflate them.
- The username landmine is written about **concurrent** lanes; arms that run at
  different times can already share seeds. The change matters for concurrent
  fleets, which is how fleets actually run here.

**Cost.** A few lines in `showdown_async.py` plus an explicit
`AccountConfiguration` on the sync path, and a regression test that two arms at
the same `--seed` get distinct account pairs. Then one pre-reg amendment to say
the governing se is paired-clustered and how it is computed.

**What would settle it.** Ship the username change, then run any two-arm fleet
at matched seeds and report both the paired and unpaired clustered se beside
each other, once. That single number tells you whether every future A/B in this
project gets cheaper.

**Arc.** Infrastructure — no arc slot needed, and it should land **before** any
step-8 lever so those levers are readable when they run.

---

### N3. Put move information into the critic's context

**Claim.** The value function currently sees **no move information from either
side**. `rl/networks/entity_deepsets.py:345-349` computes `own_moves`, and
`ctx_parts` at `:353-359` is built from field + own-team max-pool + opp-team
max-pool + own active + opp active — `own_moves` never enters it, and the
opponent's prior-filled move tokens (`tok["moves"][:, 4:]`) are never even
computed. For `is_policy=False` the head reads `ctx` alone, so the critic gets
no PP, no disabled moves, no revealed opponent moves. It also pays the
`move_net` FLOPs and discards the result.

**For.**
- This is **already on record as a defect** and was never fixed. D18's closeout
  lists it as design-level residual (2), naming the same lines, and says
  verbatim that it is *"the first thing to fix if critic-side work is ever
  revisited."* Critic-side work has not been revisited since.
- It is the same direction as N1: a better-informed critic is what makes lower
  λ cheap, so N1 and N3 are complements rather than competitors.
- Encoder-neutral. `OBS_DIM` does not move, so tapes and every encoder-keyed
  baseline survive (the C6 problem does not apply).

**Against.**
- Partially routed around already: bench mons carry no moveset but do carry
  `species_emb`, and gen1 randbats movesets are stereotyped per species, so the
  critic has a species-level proxy for "what moves does this thing have."
- It changes `ctx_in`, so existing checkpoints will not load into the new trunk.
  That is expected for a training lever but it does break shape-paired seeds
  (see N2's limits) and it means the arm needs its own control.
- D18's own finding caps the prize: the critic's *information* ceiling is small
  (+0.045 EV from the entire hidden team). Moves are inside the observation
  already, so this is a representation fix, not new information — expect a
  smaller effect than "the critic can't see moves" sounds like.

**Cost.** One concat plus the `ctx_in` arithmetic, an init-hazard check, and a
regression test that the actor path is bit-identical. Then it needs a fleet like
any trunk change.

**What would settle it.** Cheapest first: a **critic-only offline read** — fit
both value heads on an existing frozen tape and compare held-out EV and Brier.
If EV does not move on a tape, do not buy a fleet. The d22 tooling and the R0
calibration battery already produce both numbers.

**Arc.** Step 8 for the fleet; the offline read is free and can happen now.

---

### N4. Re-measure (or retire) the "one vs-SH rung is worth ±0.02" rule

**Claim.** `docs/landmines.md` records that three independent n=3000 passes over
the same 50M checkpoint scored **0.76467 / 0.78467 / 0.78333**, calls the
**range** of 0.0200 *"2.6× the binomial se of 0.0077"*, and concludes the eval
instrument is overdispersed. **That comparison is between two different
statistics.** The expected range of three draws is 1.693σ = 0.0130 with its own
sd of 0.888σ = 0.0068, so an observed range of 0.0200 is about **+1.0σ** —
ordinary. On the matching statistic the sample sd is **0.0112 = 1.45×** the
binomial se, on **2 degrees of freedom** (χ² = 4.22, p ≈ 0.12). The data do not
establish overdispersion.

**For acting on it.**
- There is no mechanism for it either, by the repo's own theory: P3's
  interpretation guard states that a mixture of Bernoullis has the same block
  variance as a plain Bernoulli at the pooled p, which is exactly why team luck
  was said not to widen an eval-mean se. The landmine contradicts that guard.
- It is not free to be wrong in this direction. If the true eval se is 0.0077
  and the rule says 0.02, every power calculation over-buys battles by ~6.7×,
  and variance that belongs to **training seeds** — the term §0.1 says is
  actually binding — gets parked in "the instrument," where it cannot be
  diagnosed.

**Against.**
- 2 df is 2 df in both directions: this does not *prove* the eval is
  binomial-clean either. The correct posture is "unmeasured," not "retired."
- **The practical guidance survives regardless.** A single rung really can sit
  1 se = 0.008 off, and a 0.02 spike between neighbouring rungs really is within
  ordinary sampling. "Read a curve's SHAPE, never one rung against its
  neighbour" stays true whichever way the sd lands.

**Cost.** ~15 minutes of eval time. `scripts/ch5_scale_shape_report.py` already
prints the re-draw check; run **8 passes instead of 3** on one checkpoint and
report the sd with usable df.

**What would settle it.** The 8-pass sd, and then either a corrected landmine
entry or a confirmed one with real df behind it.

**Sub-idea, unverified — paired eval.** `rl/common/evaluation.py:9-17` records
that eval pairing "buys nothing on Showdown" because the **server** rolls teams
and damage and the env never seeds it. That is a statement about the current
wiring, not a law: `showdown/` is a vendored, gitignored, re-clonable tree you
already modify (`simulator: 4`) and already patch (`scripts/patches/
foulplay_gen1_local.patch`). If a fixed battle seed can be pushed through the
challenge path, two checkpoints could face **identical teams and identical
damage rolls**, which is a genuinely paired eval and a large cut in eval se.
**I did not verify that Showdown's challenge path accepts a seed** — worth
about 30 minutes of checking before anyone budgets on it.

**Arc.** Instrument work; no arc slot. Do it before the post-100M S-SHAPE read
is interpreted, since that read is exactly a rung-vs-rung curve.

---

### N5. Species-exposure diagnostic (maintainer's "rarer Pokémon did worse")

**Claim.** The observation is worth one regression, not a training change.

**For.**
- P3 already priced this (`scripts/p3_team_luck.py`, 2026-08-03): the observable
  draw explains **CV R² = 0.0375** of per-battle outcome variance on n=3000 over
  146 species, against a permutation null at 95th pct 0.0015 (p < 0.005). Real
  but modest, and a lower bound.
- The coefficients are face-valid on **strength**, not rarity: own Electabuzz
  +0.098, Mewtwo +0.072, Abra/Alakazam ≈ +0.07 win-probability; Tangela,
  Parasect, Grimer ≈ −0.07. So "worse with rare mons" and "worse with weak mons"
  are confounded, and P3 never separated them.
- The discriminator is cheap and already built: re-run the same ridge
  linear-probability procedure on existing eval tapes with **species draw
  frequency added as a covariate**, same folds, same permutation null.

**Against — and this is why it is a diagnostic and not a lever.**
- **Exposure cannot plausibly bind at scale.** 100M steps ≈ 3.3M episodes × 6
  own slots over 146 species ≈ ~135k appearances per species per lane.
- The observation is very likely an eval-n artifact: at n=3000 a given species
  appears on our team in ~120 battles, so a per-species win rate carries a
  binomial se of ~0.045 — more than enough to manufacture the pattern.
- **There is no lever even if it is real.** `gen1randombattle` teams are rolled
  by the server; there is no team-control seam anywhere in `rl/`, and forcing
  composition means leaving the format, which invalidates every comparison and
  anchor the project owns.

**Cost.** ~20 minutes on an existing script, no training, no server.

**What would settle it.** The re-run with the frequency covariate. If frequency
carries no coefficient once strength is in the model, close the question in
`CLEANUP.md` so it is not re-raised.

**Arc.** Diagnostic; no arc slot.

---

## 2. Tier B — training levers; JOURNEY step 8 unless ruled otherwise

### N6. Both-seat harvest (ledger item A2, licensed 2026-08-26, never built)

**Claim.** The learner buffers seat 1 only. `ShowdownEnv` is
`SingleAgentWrapper(ShowdownSingles, opponent)` with `discard_seat2_obs=True`
(`rl/envs/showdown.py:1208, 1216-1217`), so the opponent seat's trajectory is
thrown away. In the async collector both seats are already first-class
`Player`s and the opponent already encodes its own observation to move
(`rl/envs/showdown_async.py:212-222`), so the encode is paid and discarded.

**For.**
- **~2× episodes per update at identical simulation cost**, and that exact
  quantity is this project's largest credited lever (R2: +0.13722 off-FP@20).
  The ledger calls A2 "the first free 2× of this same quantity."
- **Return-balanced batches.** Every battle contributes one +1 and one −1, which
  removes batch-level outcome noise by construction. H&L's per-battle batches
  have this property; ours do not. It matters here because gen 1 is luck-heavy
  and the reward is terminal-only at γ=1.
- The second seat is already a proven source of free signal in this repo: D25's
  auxiliary opponent-action head harvests seat 2's *labels* and credited
  **+0.074 pooled over 5 seeds** (0.6185 vs a 0.583 bar).

**Against and the design problem the code exposes.**
- The opponent seat is a **frozen `SnapshotPool` member**, not the learner:
  `latest_prob 0.8` on the newest push with `push_every_updates: 5`, and 0.2
  uniform over up to 20 historical members (`rl/selfplay/pool.py:185-191`).
  Harvesting it naively feeds PPO rows whose behaviour policy is not the
  learner's. The 2026-08-08 advisory rejected the "free 2×" framing for exactly
  this reason and filed it as a throughput lever needing behavioural-logp
  storage.
- **The fix is known and small:** store the acting snapshot's own log-prob as
  the behaviour logp so the importance ratio is correct by construction, and
  harvest only rows where the drawn member is the **latest** snapshot (≈80% of
  episodes, ≤5 updates stale — comparable to the staleness PPO already tolerates
  across its 4 epochs). Drop the historical 20%, where the ratio would clip to
  zero gradient anyway.
- **It is not a clean 2× of the R2 quantity.** The two seats' outcomes are
  perfectly anticorrelated, so effective sample size for outcome-driven gradient
  is less than 2×. That is the same fact that makes it a variance win, and it
  means dose-matching against R2 needs stating up front.
- Real collection wiring: the rollout buffer must accept two interleaved
  streams with independent episode boundaries and per-seat GAE.
- 50M-flat says more data alone does not move the number — so the case rests on
  the **variance/balance** property, not on volume. Say so in the header.

**Cost.** Build in `rl/collect.py` + `showdown_async.py` + the buffer; then a
fleet. Not free, but bounded, and no encoder change.

**What would settle it.** A pre-registered 2-arm fleet at matched total env
steps (so the lever is episodes-per-update and batch composition, not
simulation), primary off-FP@20. Pair it with N2's matched seeds if the shapes
allow.

**Arc.** Step 8. Best companion to N1 — both attack the same variance axis, so
run them as separate arms, never bundled.

---

### N7. Structure, not capacity (maintainer's "bigger architecture / CNN")

**Claim.** Capacity is ruled out; the open question is structure. The 2026-08-26
ruling stands: *"hold until R1-A. Capacity is ruled; structure is not."*

**Against more capacity, and it is the one candidate the ledger argues against
directly.**
- The biggest credited win came at **reduced** parameters — Rung 2's entity
  trunk moved 0.3996 → 0.5509 (**+0.1513, z +20.5**) at 626,059 params under the
  681,994 MLP ceiling.
- H&L reached 72% GXE at 1.33M params against our ~1.17M.
- **The capacity you have is idle.** `ctx_net.1` dormant fraction climbs
  27% → 84–88% (s35/s36), scorer 54–74%; ctx feature srank99 collapses from
  ~250 to 33–54 of 384 in the actor and to **7–11 of 384** in the critic. Adding
  width to a net whose effective rank has collapsed buys capacity it is not
  using.
- The privileged-critic arm read −0.0145 while its EV rose on every lane — more
  critic, not more usable policy.

**Against a CNN specifically.** No spatial structure exists to exploit.
`rl/networks/conv.py` is MinAtar's 10×10 binary-plane net and says so. A team is
a set; the current DeepSets-over-entity-tokens trunk with a shared per-action
scorer is already the right inductive bias, and it is the thing that credited.

**The structural gaps that are actually named and unbuilt**, in the order I
would rank them:
1. **Temporal context (ledger A3).** We are single-snapshot Markov; ps-ppo uses
   64–256 turns, Metamon 200. The 2026-08-25 architecture review named this a
   *sharper* gap than attention. Spec exists at
   `prior_work/HISTORY_FEATURES_DESIGN.md`. Concrete in gen1: sleep/freeze turn
   counters, PP tracking, cross-turn set inference. **Changes `OBS_DIM`, so it
   invalidates every checkpoint** and inherits C6's sequencing — evaluate every
   outstanding final first.
2. **Explicit crossing — DCN or two-tower (ledger rung 2).** The cheap middle
   rung nobody built. Motivation is measured, not aesthetic: SH's expected
   damage is `base_power × STAB × (atk/def) × accuracy × hits × type_mult`, a
   degree-5 product with a division inside it, and flat trunks are poor at
   crosses. ~1 day, small inference cost, isolates crossing cleanly.
3. **Attention — re-benchmark before arguing about it.** The 34.6× train-step
   kill was measured against the **flat MLP**, which has not been production
   since Rung 2. Attention-vs-`entity_deepsets` has never been measured at all.
   The re-benchmark is minutes and either reopens the lever or closes it on a
   live ratio instead of a stale one. Spec at `prior_work/ARCH_SCREEN_SPEC.md`,
   including its pre-registered throughput gate (>2.5× RL throughput loss with
   <+0.02 agreement gain kills RL adoption regardless of the screen's primary).

**Also worth naming here, because it is the one *measured* encoder defect:**
C6 fixed-damage moves. `seismictoss / superfang / nightshade / dragonrage /
sonicboom` carry `basePower == 1`, so `_fill_move` writes 0.01 where Thunderbolt
gets 0.95. Super Fang 0/59 for us against 36% for humans; Seismic Toss 0.141
vs 0.289 (z = −3.39). Partially routed around by `move_emb`, touches ~1% of
decisions, and **invalidates every checkpoint** — which is why it is sequenced
**last**, after the baselines everything else is graded against.

**Arc.** Step 8, and item 1 additionally gated on the checkpoint-invalidation
sequencing.

---

### N8. H&L shaping on the entity trunk, optionally annealed to the clean objective

**Claim.** This is ledger item A1, plus the maintainer's 2026-09-01 refinement
(anneal the shaping off so the final objective is undistorted). It is the only
reward-signal branch still open, and it is open for a specific reason: the
2026-08-26 archaeology verified against `runs/*/config.yaml` that `hl_shaping`
is non-zero in **exactly three runs on disk** — `showdown_sp_signal12m_s23/24/25`
— and **all three are `trunk: mlp`**. Every entity-trunk run, including D26 and
both 50M arms, is γ1.0 with `hl_shaping` absent.

**For.**
- The mechanism argument is the repo's own, and it is good: *"shaping pays
  per-event credit, and the flat MLP could not express 'this action targets this
  entity' — the very thing Rung 2 added. A per-action credit signal is newly
  USABLE by the architecture that nulled it."*
- The 12M null (+0.0135, n.s.) is a null on a **bundle** (γ 1.0→0.95 *and*
  5-term shaping), at 12M, on a superseded trunk. Weak evidence.
- Annealing the shaping to zero before the end of training answers the standing
  objection to non-potential shaping — permanent distortion of the optimum —
  because the final objective is clean.
- Cost is one overnight, zero code (`hl_shaping` is a live env kwarg with its
  antisymmetry gate specified; `gamma` is a config key), and **no checkpoint
  invalidation**.

**Against, and the case got weaker since it was written, not stronger.**
- The in-house corroboration for the shaping story was **"noise-dominated
  updates"** — ~34–38 episodes per update against Wang's ~1,600 and ps-ppo's
  ~1,500. R2 has since taken 30,720 steps/update ÷ ~28 decisions ≈ **~1,100
  episodes/update** and credited +0.137. The variance half of the shaping case
  has largely been bought already, by a lever that worked.
- What survives is the within-episode credit-assignment half, which batching
  genuinely does not provide — but its ceiling is measured and small (D18's
  +0.045 EV from the whole hidden team; R0's reliability 0.0117). Dense reward
  does not reduce aleatoric noise, it moves reward earlier.
- **Four of the five H&L terms reward behaviour we already beat the human field
  at**: gross move errors 0.6% for us vs 2.7% for the field, and 1.88% vs 7.20%
  conditioned on a known better move existing. Only the faint term (weight
  −0.0125, the largest) targets a measured deficit — and the faint term in H&L's
  **non-cancelled** form is the trade-down risk from §4.3, just ~12× weaker than
  the `faint_shaping: 0.1` version the docstring warns about (±1.075 span vs
  ±1.6).
- It is a **bundle** against the one-lever rule (shaping + γ). A null is
  unattributable between the two, and so is a credit. State that up front.
- Its own author priced it at **~1 in 4** to clear +0.025, and picked it on cost
  rather than likelihood. That number was set before R2 landed and should
  probably come down.
- **Annealing only has content on a distorting term.** Arm B's potential-based
  shaping was *inert* (see §4.1), so annealing an inert term to zero anneals
  nothing. The anneal refinement therefore attaches to this item and only this
  item.

**Cost.** One overnight ×3–4 lanes; zero code.

**What would settle it.** A pre-registered arm on the current entity recipe:
`hl_shaping: 1.0` + `gamma: 0.95`, optionally with a declared anneal schedule to
`hl_shaping: 0` — but if the anneal is included it is a *third* bundled lever
and the header must say so and give up on attribution entirely, or run it as a
second arm.

**Arc.** Step 8. Lowest-ranked of the four Tier-B items on this page.

---

## 3. Suggested order

Nothing here should displace the 100M fleet's frozen post-fleet eval schedule
(`HANDOFF.md` §2) or JOURNEY step 2 (the ladder).

1. **N4** (8 re-draws, ~15 min) — before the S-SHAPE curve is interpreted.
2. **N5** (~20 min) — closes a maintainer observation cheaply either way.
3. **N2** (a few lines + a test) — lands before any Tier-B lever so those levers
   are readable when they run.
4. **N3 offline read** (free, on an existing tape) — decides whether N3 buys a
   fleet at all.
5. **N1** (λ) — first Tier-B fleet. Zero code, strongest prior.
6. **N6** (both-seat) — first Tier-B *build*. Natural companion to N1; never
   bundled with it.
7. **N7** — structure work, sequenced against checkpoint invalidation; do the
   attention re-benchmark early since it is minutes.
8. **N8** — last, and re-price it against R2's result before spending an
   overnight.

---

## 4. Ruled out — do not re-propose

Recorded in `CLEANUP.md` style so these are not re-run in another costume.

### 4.1 More rewards of the KO / status / HP-differential kind — dead by algebra

This is Arm B, already built, run and **CLOSED 2026-08-06** (`faint_shaping`,
`rl/envs/showdown.py:844-880`). Pooled 0.4303 vs control 0.4308, **Δ −0.0004**,
se_diff 0.0074, z = −0.06; the one-sided 90% upper bound was +0.0090, which does
not reach the credit line.

The null is **mechanical, not empirical**, so no recipe change touches it. With
`r' = r + γΦ(s') − Φ(s)` the shifted optimal value is `V' = V − Φ`, so
`δ' = δ` identically — every TD error unchanged, every GAE advantage unchanged,
the policy gradient unchanged. And Φ is not merely representable but *exactly*
present: `Φ = 0.6·(obs[2] − obs[1])` (`rl/envs/showdown.py:278-279`, verified
2026-09-01). Status one-hots and HP fractions are in the mon blocks too, so
status- and damage-differential potentials are the same family.

The only remaining channel is second-order — whether denser reward reduces
estimator variance while the critic is still wrong — and that channel is
**largest when the critic is worst**. It was tested on the flat MLP at the
0.3996 plateau, the weakest critic in the project's history, and came back empty
to three decimals: late-window value loss +0.0013, `approx_kl` identical to four
decimals (0.0008 both arms), `clip_frac` +0.0002, entropy +0.0017, over
**639,409 episodes**. A better trunk absorbs Φ more exactly, not less — so a
better recipe makes this *deader*, not livelier.

**The standing rule, verbatim:** *a potential-based shaping term whose potential
is an (approximately) linear function of features the encoder already emits is
predictably inert.* Any future shaping proposal must state its potential and
show it is NOT already representable from the observation. Do not raise the
coefficient; the coefficient is not why it did nothing.

### 4.2 Chaining runs off checkpoints instead of training fresh

Two separate readings, and both fail for different reasons.

*As "do fewer, bigger runs"* — that is already the standing order and the thing
currently executing (the 100M fleet). Nothing to decide.

*As "warm-start each new experiment from the last lineage"* — no:
- It costs attributability. Matched controls from identical init are what make a
  delta a delta; a shared donor confounds every arm with the donor.
- **`lr_anneal_steps` is coupled to `total_steps`** (R0-b,
  `configs/showdown_sp_100m.yaml:573`), so a finished lane ends at LR≈0.
  Resuming means either continuing at LR≈0, where nothing learns, or re-heating
  — and re-heating **is** N-ANNEAL, the alternative explanation the 100M pre-reg
  already names as leading on a positive read ("the anneal, not the data"). The
  idea silently instantiates the confound the running experiment exists to
  guard against.
- Plasticity is measured here and it is bad: dormant 27% → 84–88%, critic ctx
  srank99 7–11 of 384. A collapsed representation is a poor place to start more
  training. The regenerative L2-toward-init arm was built for exactly this and
  read +0.045 without crediting.
- A warm-start lineage locks `OBS_DIM`, and both C6 and temporal context
  (N7's item 1) invalidate checkpoints by construction.

The legitimate home for "massive train from a validated recipe" is
`JOURNEY.md` step 10.

### 4.3 A survivor bonus — remaining Pokémon added to the win reward

Harmful, and it is the precise failure mode the terminal cancellation was
designed out to prevent. Without the cancellation the effective outcome signal
spans **±1.6 and a clean-sweeping 48%-win policy outscores a trading 50%-win
one** (`rl/envs/showdown.py:742`). The objective stops being "win" and becomes
"win prettily," which in gen1 is concretely wrong — sacrificing a mon to absorb
a sleep, scout a set, or preserve a sweeper is routine correct play. Secondary
cost: value targets leave ±1, inflating the value loss ~2.5× against
`value_coef: 0.5`. Arm B's falsifier confirms there is no upside hiding here —
the loss-conditioned faint differential moved +0.017 mons, and
`eval/loss_faint_lead_frac` was **0.000 in both arms**: in not one losing battle
out of ~5,100 did either policy lead on faints. Our losses are decisive, not
close.

---

## 5. What this audit did NOT verify

Stated so nobody inherits a claim I did not check.

1. **Whether Showdown's challenge path accepts a battle PRNG seed** (N4's paired
   -eval sub-idea). Unverified; ~30 minutes to check in the vendored tree.
2. **Whether there is a *statistical* reason arms use distinct seeds** beyond
   the username collision (N2). I found only the mechanical one; if a design
   reason exists somewhere I did not read, N2 is void.
3. **Parameter counts were not recomputed.** The conda env
   `pokemon-showdown-rl` does not exist in the remote container this was written
   in, so `torch` was unavailable. The 626,059 / 681,994 / ~1.17M / 1.33M
   figures are quoted from `RESULTS.md` §3 and CHAPTER5 §3, not re-derived.
4. **The gen1 randbats species-frequency distribution was not inspected.**
   `rl/envs/data/gen1_randbats_sets.json` is under the gitignored `data/` tree
   and absent from the container, so N5's "roughly uniform draw" premise rests
   on the 146-species pool size and per-species set counts described in
   `rl/envs/randbats_prior.py`, not on a counted distribution. **N5's regression
   should count it rather than assume it.**
5. **No run artifacts were read.** `runs/` does not exist in this container, so
   nothing here reflects live fleet state, and no checkpoint was evaluated —
   the pre-reg's bar held.

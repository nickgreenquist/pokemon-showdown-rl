# SELF-PLAY RECIPE AUDIT — the 200M monster, 2026-09-12 launch

Audit of `configs/showdown_monster200m.yaml` against what strong self-play
systems do. **[V]** = I opened the primary text; **[R]** = secondary. CLAUDE.md
rule 6 binds: no 12M/50M A/B null is cited as evidence about a lever; where I
cite our own runs it is a MECHANISM MEASUREMENT, never an A/B verdict. Nothing
here is ratified and nothing authorises a launch.

**Relation to the two sibling reports** (read after drafting, reconciled here).
`MODEL_SCALE_2026-09-12.md` already proposes ARM L2, LayerNorm in
`ctx_net`/value stack, `gae_lambda: 1.0` and fewer epochs; I reached #2 and #3
independently and they should be read as corroboration, not a second proposal.
**I do not recommend width** — that is its lever, not mine. What is new here is
#1, the anneal floor, and it *contradicts* that report's line 314, which treats
the full-horizon anneal as protective; §1 measures the opposite. The consequence
matters for its own arm: **L2's decay is proportional to the group lr, so a
to-zero anneal disables ARM L2 in the tail.** `PLASTICITY_PROBE_2026-09-12.md`
gates #2/#3 and its results were still pending when I finished; its
"REPRESENTATION DEGENERATE BUT TRAINABLE" branch argues for my #3 specifically.

## TL;DR — 10 lines

1. The recipe is field-correct on nearly every axis: value clipping off,
   separate actor/critic, per-minibatch advantage norm, λ=0.95, the 80/20
   span-thinned pool, no PopArt/symlog. §3 says leave all of them.
2. **The problem is the schedule, not the hyperparameters: the last ~15% of
   every lane does nothing.** At 98.5M on both 100M finals, `approx_kl` 8.6e-7,
   `clip_frac` 0.0, `grad_clip_frac` 1.0. Dead compute, about to be doubled.
3. **#1 (free): floor the LR anneal** — `lr_anneal_steps: 240000000` against
   `total_steps: 200000000`. +17% lr-integral, all of it late. One launcher
   line; needs a ruling against JOURNEY 10's verbatim clause.
4. **#2: `l2_init_decay: 0.02` on half the fleet** — built, 14 tests,
   resume-guarded, config already written, −3.2% throughput, and it targets
   exactly the measured pathology (norm growth, srank collapse, EV decay).
5. **#3: LayerNorm in `ctx_net` + value stack** — the one place the trunk lacks
   it, and where the collapse was measured. ~10 lines, RNG-neutral. Fleet only
   if a 400k smoke lands tomorrow; else next fleet.
6. **Six identical arm-A lanes is the weakest allocation for a ladder object**
   — our own read prices the last step-doubling at +0.001 vs SH on the
   committee. Recommend 3 × A + 3 × A+L2, all six with the floor.
7. **#1 next fleet, highest ceiling: an R-NaD/MMD KL-to-reference magnet.**
   DeepNash reached top-3 human Stratego on pure self-play, no search, no pool,
   with exactly this term; `bc_kl_coef` is ~80% of the plumbing already.
8. **#2 next fleet: KataGo-style auxiliary outcome decomposition** (survivors,
   terminal HP diff) — their ownership+score targets were worth 1.65×.
9. Do NOT run λ=0.75, arm B, arm C, PFSP, obs-norm, or a bigger entropy bonus.
10. Ladder object: ENS6 of the six finals, greedy. No new play-time machinery
    this week; the BC-clone anchor leg is still PENDING.

## 1. What our own run measures (the spine of everything below)

From `runs/showdown_sp_100m_s{104,112}/history.csv` — a diagnostic series over
~3,250 updates, not an A/B. s112 reproduces every row.

| step | entropy | approx_kl | clip_frac | expl_var | grad_norm | grad_clip_frac |
|---|---|---|---|---|---|---|
| 0.03M | 1.796 | 0.0052 | 0.040 | −0.330 | 1.61 | 0.91 |
| 12.3M | 0.704 | 0.0430 | 0.225 | 0.665 | 1.70 | 1.00 |
| 49.3M | 0.541 | 0.0280 | 0.162 | 0.625 | 3.04 | 1.00 |
| 86.2M | 0.396 | 0.0082 | 0.073 | 0.582 | 3.65 | 1.00 |
| 99.99M | 0.314 | **8.6e-7** | **0.000** | 0.609 | 4.41 | 1.00 |

- **The tail is dead.** `approx_kl` falls five orders of magnitude, `clip_frac`
  hits exactly 0. Under linear-to-zero the last 10% of the horizon carries 1%
  of the lr-integral; 200M under a 200M anneal reproduces this at 2× the cost.
- **`max_grad_norm: 0.5` is the optimizer, not a safety valve.**
  `grad_clip_frac` is 1.0 from update ~1 on, against a norm growing 1.6 → 4.4.
  Every step is renormalised. Adam absorbs much of a *constant* rescale, so I am
  not claiming an 8× effective-lr loss — but `lr: 2.5e-4` is not the step size
  and nothing logs what is.
- **The critic gets worse after 12M.** EV peaks 0.665 at 12M, settles 0.58–0.61
  — the component D22 measured as idle (dormant 27→84–88%, critic ctx srank99
  7–11/384). Norm growth + rank collapse + EV decay is the textbook
  plasticity-loss signature [V].
- **Entropy never floors on its own** — still falling at 0.31 nats when the
  anneal freezes it. The plateau is the schedule, not convergence.
- **The engine port inverted the cost structure.** I computed update share on
  the Node 100M run at 24.6% of (collect+update); on the engine route collect is
  34.9% of wall, so the **update is now ~65%**. Update-side levers are now the
  expensive ones.

## 2. Ranked recommendations

### #1 — Floor the LR anneal. FREE. THIS FLEET, all six lanes.

**Mechanism:** linear-to-zero spends the tail at a step size that provably moves
nothing. A floor at 0.167·lr0 raises the lr-integral 0.500 → 0.583 (+17%), all
of it in the second half where the policy is most refined; a rate strictly below
the run's own midpoint cannot destabilise a run that was stable at its midpoint.
**Evidence:** nobody at scale anneals to zero. OpenAI Five LR `5e-5 → 5e-6`,
entropy `0.01 → 0.001` [V, Table 2, 1912.06680]; Andrychowicz — linear decay
"may slightly improve performance but is of secondary importance" [V, 2006.05990];
Engstrom — Adam LR annealing helps [V, 2005.12729]; Wang's schedule, already
implemented here as `lr_schedule: power`, floors at `lr0/27` and ran a full
gen-4 fleet to completion [V, `configs/gen4_wang50m.yaml:653`].
**Cost:** zero learner code. `rl/train.py:433` already PERMITS
`lr_anneal_steps >= total_steps` and names that shape legitimate in its own
comment; the only blocker is `scripts/monster_fleet.sh:91`, which asserts
equality — one line, relax to `>=`.
**Risk:** lowest here. No new code path, no new tensor, no divergence mode. The
one behavioural change is a final checkpoint drawn from a still-moving policy;
at 0.167·lr0 with renormalised gradients the motion is small and the committee
averages 3–6 of them.
**Ruling needed:** JOURNEY 10 says verbatim `lr_anneal_steps == total_steps`.
The anneal trap that clause defends against is `anneal < horizon`;
`anneal > horizon` is the opposite error direction, and train.py's guard agrees.

### #2 — `l2_init_decay: 0.02` on half the fleet. THIS FLEET, 3 of 6 lanes.

**Mechanism:** decoupled per-step decay toward θ₀ stops parameters the recent
loss is insensitive to from drifting, bounding parameter-norm growth and
preserving rank — both measured pathologies (§1). Decaying toward θ₀ rather than
toward 0 is what avoids the rank collapse plain L2 causes.
**Evidence:** Kumar et al. — `L_train + λ‖θ−θ₀‖²`, "a single value λ=0.01
achieves the best performance across problems", beating plain L2 (which causes
"weight rank collapse" and "mutually frozen weights") and matching or beating
Continual Backprop on 4/5 problems [V, 2308.11958]; Lyle recommends **layer norm
together with L2** as the combination that addresses multiple mechanisms at once
[V, 2402.18762]. Our D23 mechanism leg — critic srank99 31/53/36 vs control
11/17/16, norm bound held — is a measurement, cited as such; I cite no win-rate
reading from it in either direction (rule 6).
**Cost:** ZERO build. `configs/showdown_monster200m_l2.yaml` exists with one
diff; θ₀ capture, `theta0.pt`, the resume digest guard (`rl/train.py:238-260`)
and 14 tests are in. −3.2% → 44.7 h, inside the window.
**Risk:** LOW, with one interaction worth knowing:
`alpha = -group["lr"] * l2_init_decay` (`ppo.py:913`) — **the regulariser is
proportional to the group lr, so annealing to exactly zero switches the
plasticity fix off precisely when plasticity is worst.** #1 and #2 are
complements; run L2 only with the floor.

### #3 — LayerNorm in `ctx_net` and the value stack. SMOKE-GATED.

**Mechanism:** the trunk has LayerNorm only at the terminal of each entity
subnet (`entity_deepsets.py:268-274`). `ctx_net` [384,384], the scorer [256] and
the value stack [384,384] are bare Linear+ReLU — and the ctx/value stacks are
exactly where D22 measured srank 7–11/384. LN holds preactivation distributions
in range and smooths the landscape, the mechanism Lyle identifies as causal.
**Evidence:** Lyle 2023 — normalization layers "provide the greatest
improvements to plasticity", and adding LN to DQN "robustly improves performance
across the benchmark, without any additional hyperparameter tuning", while
parameter-perturbation methods "see less benefit" [V, 2303.01486]; BRO — LN
after each dense layer is "essential to unlocking scaling" of the critic [V,
2405.16158]; ps-ppo, the 2102-Elo Showdown system whose subnet shape we already
borrow, uses LN in `_build_subnet` [V, our provenance note, `:16`].
**Cost:** ~10 lines behind a `trunk_kwargs.ctx_layernorm` flag defaulting false.
**`nn.LayerNorm` consumes no RNG** (ones_/zeros_ init; `init_head` touches only
Linear/Embedding), so the flag is an exact no-op when off and the goldens are
untouched. Forward cost is small but update-side.
**Risk:** MODERATE only because unsmoked — LN itself has no divergence mode. It
does make those lanes non-comparable to the 100M control.
**Where:** this fleet **only if** a 400k smoke through the launcher is clean
tomorrow; else the first arm of the next fleet. Do not stack with L2 in one arm
— one lever per arm, factorial hazard.

### #4 — Spend the fleet on levers, not on six control lanes. THIS FLEET.

**Mechanism:** the ladder object is picked descriptively from committee reads
and does not need the horizon verdict. The horizon is our weakest measured axis
— STATUS prices the 50M→100M doubling at **+0.001 vs SH on the committee**
(+0.024 off-FP, not credited) against a credited +0.035 for ensembling. Six
lanes re-measuring a weak axis while two built levers sit unused is the wrong
trade for "a super awesome policy to ladder with next week".
**Evidence:** internal (STATUS ENSEMBLE SCALING), plus — near the top of the
strength axis the cyclic dimension shrinks and gains are transitive, so
coverage-style width buys less than strength [V, 2004.09468].
**Cost/risk:** zero build; the price, stated honestly, is that "more steps"
becomes a descriptive read. [RWL-7] already contemplates this shape.
**Recommended:** 3 lanes plain A + 3 lanes A+L2, all six with the #1 floor,
seeds 104/112/120/128/136/144. Ladder object = ENS6 mixed, or ENS3 of whichever
trio reads better off FP@20.

### #5 — Ladder object: ENS6, greedy, and finish the anchor battery.

**Mechanism:** the committee is our only credited free lever (+0.0349 at 5.93 se);
six equal-strength members beat three-plus-weaker mixes, and the measured 1→6
curve 0.789 → 0.844 is a lower bound because members 4–6 were 50M objects. Greedy
is the form every number was measured on.
**Evidence:** internal, plus — humans on ladder make "safe Pokémon switches" and
play "multi-turn strategy", and agents fail on "rare team compositions" rather
than on a failure to mix [V, Metamon 2504.04395: Gen1OU rank #31, GXE 79.9,
Glicko 1761±35, **using human replays** — a target line, not a method we may
copy]. That is fixed by coverage (our 5M-pair team bank), not by play-time
stochasticity; and our object is argmax, so training entropy never reaches play.
**Cost/risk:** zero — it is the existing plan. Two asks: run
`configs/eval/ens_width*.yaml` on the six real finals before choosing, and land
the **BC-clone h2h (500)** leg, still PENDING and blocking the README row.

## 3. Confirmed correct — do not change

- **Value-function clipping OFF.** Engstrom: "no evidence that the value
  function loss clipping helps"; Andrychowicz: it "even hurts performance" [V,
  2005.12729; 2006.05990].
- **Separate actor/critic nets** — "Use separate value and policy networks" [V,
  2006.05990]. Ignore the SB3 shared-trunk row for now.
- **Per-minibatch advantage normalisation** (`ppo.py:1739`) — "not to affect
  performance much" [V, 2006.05990]. Optional hygiene: `minibatch_tail: drop`
  already exists if you want F-04's ~0.8% tiny self-normalised slices gone.
- **`gae_lambda` — do NOT go to 0.75; λ=1.0 is a different question and stays
  open.** GAE's own claim: "λ<1 introduces bias only when the value function is
  inaccurate" [V, 1506.02438]. Ours *is* the diagnosed weak component (EV
  0.58–0.61, falling), so *lowering* λ routes credit through the worst part of
  the net: at γ=1, terminal-only ±1, ep len ~31, λ=0.75 leaves actions >8 turns
  from the end almost no direct outcome signal (0.75¹⁰ ≈ 0.06), and IDEAS 4.2's
  own correction (ii) notes every λ<0.95 system in the field pairs it with dense
  reward. **Raising** λ to 1.0 (pure MC, zero critic bias) points the same way my
  diagnosis does and is `MODEL_SCALE` §E's lever; I do not contest it.
- **The pool: 20 / latest_prob 0.8 / push_every 5.** I expected to recommend
  widening it and was wrong: `pool.py` does **span-preserving thinning**, not a
  recency deque — retained push ids stay ~uniform over [0, latest] with a
  protected step-0 anchor, so the pool spans the whole run, not a 3M-step
  window. That is exactly Bansal's δ=0, whose ablation says latest-only "leads
  to imbalance in training" [V, 1710.03748]; 80/20 is OpenAI Five's split [V].
- **No PFSP / exploiters.** The board is transitive (BT fit ±0.03 across 14 arms)
  and the exploitability probe found a representation ceiling, not an
  exploitability one; spinning-top geometry agrees cycles shrink near the top [V,
  2004.09468]. Population value in the field (FTW's P=30 [V, 1807.01281]) is
  about stabilising learning, which the span-thinned pool already buys.
- **No PopArt / symlog.** Both address large or drifting regression-target scale
  (Lyle's cause #3); our targets are bounded in [−1,1], mean ≈0, `loss/value`
  ≈0.23. Nothing to rescale — explicitly unnecessary.
- **No observation normalisation** — `rl/train.py:414-421` refuses it under
  self-play (the opponent lives in a sub-env and would see raw obs). LN is the
  substitute; that is #3.
- **No KL early stop — but a correction is owed.** IDEAS §3 says our measured KL
  "would never fire", citing gen-4 (`p50 0.00086, max 0.00228`). **On gen 1 the
  100M finals reach `approx_kl` 0.043 at `clip_frac` 0.225 by 12M** — a 1.5·0.03
  trigger would fire mid-run. Still should not be added (it would fire where PPO
  does its useful work), but that sentence is generation-specific.
- **k=8; arms B and C dropped** — I agree with both pre-launch reviews: B is
  bitwise A plus a head whose only consumer is search, and search is a null on
  both axes; C puts the privileged block into the advantage channel where D18's
  falsifier fired, at λ=0.95 where the vacatur named λ=1.0.
- **`entropy_coef: 0.01` constant.** Unusual at 200M, but leave it: OpenAI Five
  annealed *down* [V], which we get free as entropy decays, and entropy bonuses
  are "highly sensitive to coefficients ... large coefficients lead to entropy
  explosion" [V, 2505.22617]. The principled version of "stop the policy
  over-committing" is §4.1.

## 4. Next fleet — ranked

**4.1 R-NaD / MMD KL-to-reference magnet — the highest ceiling here.**
Unregularised self-play dynamics in imperfect-information zero-sum games cycle
rather than converge; adding `−η log(π(a)/π_reg(a))` to the learner's reward
(equivalently a KL toward a reference) contracts them to a regularised fixed
point, and iterating `π_reg ← π*` converges to Nash [V, 2206.15378]. DeepNash
reached **84% over 50 ranked matches and top-3 all-time on Gravon with no search
and no opponent pool** — the closest published analogue to our lane that exists.
Magnetic Mirror Descent is the same idea in policy-gradient form and
"substantially outperforms" NFSP and PPO on approximate exploitability [V,
2206.05825]. **Cost is unusually low here:** `bc_kl_coef` already computes
forward KL to a frozen anchor actor per minibatch over the masked categorical,
and the anchor is checkpointed (`ppo.py:1906`) and restored on load (`:1989`) —
resume-safe already. Missing: installing the anchor at step 0 on a *fresh* run
(`_install_bc_anchor` is called only from `begin_warm_start()`) and re-anchoring
every N updates. ~30 lines plus a key, a metric and a test. Two real prices: an
extra actor forward per minibatch (update-side, estimate +6–10% wall,
unmeasured) and an uncalibrated η. **Not for a 43 h unattended fleet on 36 h
notice.** Smoke at 400k, sweep η ∈ {0.01, 0.03, 0.1} at 12M reading MECHANISM
(entropy floor, `approx_kl` tail, exploitability probe) not win rate, then give
it three lanes.

**4.2 KataGo-style auxiliary outcome decomposition.** KataGo's rationale is
ours: decompose the noisy binary outcome into "finer variables" to regularise.
Measured — ownership+score targets 1.65× speedup, auxiliary opponent-reply
policy 1.30×, ~9.1× combined [V, 1902.10565]. **We already have the 1.30×
analogue:** `aux_oppact_coef: 0.1` *is* KataGo's auxiliary policy target. The
1.65× analogue we lack is terminal-quantity regression — how many of our mons
survive, terminal HP differential, turns-to-end. All self-play-legal (labels are
our own episode outcomes; the purity constraint is untouched) and all derivable
from the episode's terminal observation, so the Rust side may not need to change.
~a day for head + labels + tests. Best sample-efficiency lever available.

**4.3 `max_grad_norm`.** Clipping fires on 100% of minibatches against a norm
reaching 4.4; raising it to ~2.0 changes the optimizer's character — a lever, not
a fix, and the wrong thing to try unattended. Free first step: log the pre-clip
norm distribution and the realised scale factor, which nothing does today.

**4.4 History / recurrence.** Metamon's transformer "relied entirely on long-term
memory to infer the opponent's team" [V]. Our D19 closeout says 88–90% of gen-1
randbats team structure is a deterministic cap mask over what is already
revealed, so the *belief* half is largely priced in — but the *behavioural* half
(does this opponent switch out of bad matchups? stall?) is not, and it is exactly
what differs between self-play and humans. Changing `OBS_DIM` invalidates every
checkpoint (landmine). Gen-4 chapter work.

**4.5 Epochs / minibatches.** 4 epochs × 120 minibatches = 480 Adam steps per
30,720-row update at minibatch 256; OpenAI Five ran sample reuse ≈1.0–1.1 at a
983,040-sample batch [V], and our mid-run `clip_frac` 0.225 vs `clip_eps` 0.2
says the surrogate is saturated on ~22% of rows. Worth one screen; larger
minibatches would also be faster on CPU at `torch_threads: 1`.

## 5. Disclosures

- §1 is two lanes of one recipe on the **Node** collector; the fleet runs the
  **engine** route (A-1 signed delta −0.00436, which travels). The *shapes* —
  anneal tail, clip saturation, EV decay — belong to the optimizer and the
  schedule, not the collector, but values may shift.
- The 24.6% update share is the Node path's, computed here; 34.9%-collect is the
  engine path's banked figure, not re-measured.
- "+6–10% wall" for a KL anchor forward and "~10 lines" for LayerNorm are
  estimates. No external result here is an A/B in gen-1 randbats — every "at
  scale" citation is a different game, mechanism evidence not transfer.
- #1 and #4 need maintainer rulings (JOURNEY 10's anneal clause; arm
  allocation); #3 needs a smoke. Rule-3 housekeeping:
  `scripts/plasticity_probe.py` is untracked and will stamp `git_dirty`.

## 6. Sources opened

[V], all `https://arxiv.org/abs/<id>`: 1912.06680 OpenAI Five · 2006.05990 What
Matters in On-Policy RL · 2005.12729 Implementation Matters · 1902.10565 KataGo ·
2206.15378 DeepNash/R-NaD · 2206.05825 Magnetic Mirror Descent · 2308.11958 L2
Init · 2303.01486 Understanding Plasticity · 2402.18762 Disentangling Plasticity
Loss · 2302.12902 Dormant Neurons · 2205.07802 Primacy Bias · 2405.16158 BRO ·
1710.03748 Emergent Complexity · 1807.01281 Capture the Flag · 2004.09468
Spinning Top · 1506.02438 GAE · 2504.04395 Metamon · 2505.22617 Entropy Mechanism
of RL. Plus `iclr-blog-track.github.io/2022/03/25/ppo-implementation-details/`.

[R] AlphaStar (Nature 2019) — paywalled, not opened; its league/PFSP, its
KL-to-supervised term (unavailable to us under the purity constraint) and its
opponent-observation value function are quoted from this repo's verified record
(`docs/IDEAS_POST_100M.md` §3, verified 2026-09-04), not the source. Also [R]:
the Hanabi CTDE/aux and CFR/ReBeL poker lines, not opened — R-NaD and MMD carry
the same argument in the form we would actually use.

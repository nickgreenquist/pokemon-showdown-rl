# Capacity-loss / plasticity probe (2026-09-12)

Commissioned by `docs/research_reports/MODEL_SCALE_2026-09-12.md` §E(3): *"Do
this first, tonight — it is free and it can change the launch."* The maintainer
decides in ~30 h whether to widen the critic (**ARM W**, `value_sizes:
[1024,1024]` + `l2_init_decay: 0.02`) on a 3–4 day, 6-lane, 200M fleet. This
probe is one input to that decision.

**Marks.** `[V]` verified this session (paper text fetched verbatim / artifact
read / measurement run here). `[R]` secondary — taken from
`MODEL_SCALE_2026-09-12.md`, which marked it `[V]` there.

**Rule 6 does not bite here.** Nothing below is a win-rate A/B at any dose. This
is a mechanism measurement on banked checkpoints — the same class as D23's
mechanism leg, which the scale report cites for exactly that reason.

**Script:** `scripts/plasticity_probe.py` (its module docstring is the
authoritative protocol; this section restates it).
**Data:** `results/plasticity_probe/probe.json` (gitignored).

---

## 1. Why this probe exists

`MODEL_SCALE` §D'-3 reads our D22 instruments — critic `srank99(ctx)` **7–10 of
384** at 50M against the actor's 33–54, and heavy dormancy — and then says the
literature will not let them carry the weight:

- Lyle 2303.01486 §5.2 falsifies feature rank *and* sparsity as causal
  plasticity indicators `[R]`.
- Lyle 2204.09560 **Corollary 1**, verbatim `[V]`: *"Then if Rπ=0, the feature
  representation converges to the zero vector for every state, independent of
  whether the learning rate α is scaled as 1/M or the linear weight
  initialization variance scales as 1/M."* Terminal-only ±1 reward at γ=1 is
  the sparse-reward limit that corollary describes.

So a collapsed srank is consistent with two different worlds, and they imply
opposite fleet decisions:

| world | what it means | what it argues for |
|---|---|---|
| **(i) plasticity loss** | the current parameters can no longer be optimised | width **+** L2-toward-init — i.e. ARM W |
| **(ii) representation artefact** | a healthy learner's response to sparse reward; the net would still fit anything asked of it | width unlikely to pay; the levers are `gae_lambda: 1.0` / denser targets |

The corpus's own instrument for separating them is **Lyle et al. 2022
(arXiv 2204.09560), Clare Lyle, Mark Rowland, Will Dabney, "Understanding and
Preventing Capacity Loss in Reinforcement Learning"** — *target-fitting
capacity*, **Definition 1**, fetched verbatim this session `[V]`:

> Let P_X ∈ 𝒫(X) be some distribution over inputs X and P_ℱ a distribution over
> a family of real-valued functions ℱ with domain X. Let 𝒩=(g_θ, θ₀) represent
> the pairing of a neural network architecture with some initial parameters θ₀,
> and 𝒪 correspond to an optimization algorithm for supervised learning. We
> measure the target-fitting capacity of 𝒩 under the optimizer 𝒪 to fit the
> data-generating distribution 𝒟=(P_X, P_ℱ) as follows:
> 𝒞(𝒩,𝒪,𝒟) = E_{f∼P_ℱ}[ E_{x∼P_X}[ (g_{θ'}(x) − f(x))² ] ] where
> θ' = 𝒪(θ₀, P_X, f).

The paper's own empirical read loads agent checkpoints at various training
timepoints, draws random target functions from newly-initialised networks,
samples states from the replay buffer, and measures MSE after **50,000**
gradient steps of regression `[R]` (a paraphrase returned by the fetch, not a
verbatim quote). Its abstract, verbatim `[V]`, also names the remedy family:
InFeR, *"regressing a subspace of features towards its value at
initialization"* — which is the same family as ARM W's `l2_init_decay`, and is
why the scale report pairs width **with** L2 rather than shipping width alone.

---

## 2. Protocol — frozen before the run

### 2.1 Inputs

`results/d22/obs_s{35,36,37}.npz` — seat-1 observations and action masks at
every decision of 200 self-play mirror battles per D22 lane
(`scripts/d22_collect_obs.py`). Pooled: **19,218 rows × 828**. One fixed
shuffle (seed 20260912), **80/20** split → 15,374 train / 3,844 held-out.

*Disclosure:* these obs were collected from `showdown_sp_struct50m_s{35,36,37}`
final checkpoints, not from the checkpoints being probed. Def 1 needs
"inputs from our own domain" (P_X), and one shared input set is what makes
checkpoints comparable to each other; it is not each checkpoint's own on-policy
measure. Measured side-effect of the choice: re-running the D22 rank instrument
on the s35 checkpoint gives `srank99(ctx)` actor **33** / critic **10** on its
OWN obs and **32 / 10** on this pooled held-out set `[V]` — the input set moves
the number by ≤1.

### 2.2 Targets (drawn once; identical for every parameter set)

| family | net | target | loss |
|---|---|---|---|
| `randnet` | critic | output of a **fresh** `EntityDeepSetsNet` critic (seed 9001), standardised with the train split's mean/std | MSE |
| `randnet2` | critic | same, independent draw (seed 9003) — the second Monte-Carlo sample of `f ∼ P_ℱ` | MSE |
| `iid` | critic | one i.i.d. **N(0,1)** scalar per row (seed 4242) — pure memorisation | MSE |
| `randpol` | actor | logits of a **fresh** actor (seed 9002), standardised over legal entries, masked-softmaxed | forward **KL(target ‖ student)** over legal actions |

`randnet` is Lyle's own target family. `iid` is the memorisation control: its
held-out leg is ~1.0 by construction and is reported only to prove that.

The actor's standardisation is not cosmetic. The shipped init rescales the
actor's final layer by gain 0.01 and zeroes every bias, so a fresh actor's raw
logits have std ≈0.003 and the raw target distribution is the uniform one to
three decimals — nothing to fit. Because the biases are zero the logits are
exactly `gain · (W·f)`, so standardising cancels the gain: the target is the
same object at 0.01 and at 1.0. Standardised it has mean entropy ≈1.53 nats
against ≈1.75 for uniform-over-legal, mean max-prob ≈0.39.

### 2.3 Conditions

- **FULL** — every parameter trainable. Def 1 proper. *Freeze nothing.*
- **HEAD-ONLY** — trunk frozen, final linear only. Critic: `head` (384→1).
  Actor: `scorer[-1]` (256→1) plus `slot_bias` (10) — the whole readout that
  sits on the per-action features. Starts from the checkpoint's **own** head
  weights: Def 1 asks what the current parameters can do. Implemented by
  caching the frozen net's input to that final layer (captured with a forward
  pre-hook, not by re-deriving the forward) and training the layer on the
  cache — identical function, negligible cost.
- **Controls** — two **fresh inits** of the same architecture (seeds
  20260912 / 20260913, built exactly as `PPOAgent` builds them: actor
  `init_head(0.01)`, critic `init_head(1.0)`), plus the **earliest rungs**
  available (`engine_a1_s66` @500k and @1M).

### 2.4 Parameter sets

All seven checkpoints were confirmed to carry byte-identical `trunk_kwargs`
(`entity_dim 128`, `ctx_sizes [384,384]`, `scorer_sizes [256]`,
`value_sizes [384,384]`, `embed_dim 64`, vocab 152/166) `[V]`; the script
asserts this and SKIPS any that differ rather than rebuilding at another shape.
None were skipped.

| name | path |
|---|---|
| `100M_final` | `runs/showdown_sp_100m_s112/ckpt_100000008.pt` |
| `100M_rung12M` | `runs/showdown_sp_100m_s112/ckpt_012000023.pt` |
| `50M_s66/s75/s83` | `runs/showdown_sp_batch50m_s{66,75,83}/ckpt_050000000.pt` |
| `early_500k` | `runs/engine_a1_s66/ckpt_000500006.pt` |
| `early_1M` | `runs/engine_a1_s66/ckpt_001000017.pt` |
| `fresh_a`, `fresh_b` | fresh inits, seeds 20260912 / 20260913 |

Nets are built by `scripts/d22_dormant_rank.py::build`, i.e.
`EntityDeepSetsNet(828, 10|1, **trunk_kwargs)` + that checkpoint's own
`agent[part]` state dict — identical in effect to
`scripts/ch3_eval.py::_load_member_spaces` (`make_agent` → `PPOAgent` builds
the two nets with exactly these arguments), without needing spaces or an
optimiser. Every FULL run gets a **fresh copy** of the parameters, so no run
inherits what another moved.

### 2.5 Budget — identical for every condition

Adam, batch **256**, **6,000 steps** (= 100 epochs of the train split), at
**both lr 2.5e-4** (the runs' own lr) **and lr 1e-3**. Batch order is a fixed
stream per (part, family, lr), **shared across parameter sets**, so every
between-checkpoint comparison is paired. Loss reported at **0 / 25 / 50 / 100%**
of budget, on the **full** train split and the **full** held-out split.

*Calibration* (dry run, 2026-09-12, `[V]`): a fresh-init FULL critic goes
**1.051 → 0.062** held-out MSE on `randnet` by step 2000 (17×, flat from
~1500); a fresh-init FULL actor **0.226 → 0.0047** held-out KL by step 1000.
The budget had to reach clearly sub-initial loss on the fresh init; 6,000 is 3×
past the point where that is already true, so the 100% mark reads asymptotic
fit and the 25% / 50% marks read optimisation **speed**.

**Two deviations from Lyle, disclosed with every number.**

1. Lyle's read uses **50,000** steps; ours is **6,000** — what fits one CPU
   process in the window while two Foul Play wall-clock evaluations hold the
   box. A shorter budget is a *strictly harder* test of trainability, so a
   "no capacity loss" verdict from it is conservative; a "capacity lost"
   verdict would need the longer budget before it could be called asymptotic.
2. Def 1 is an **expectation** over target draws; we take one draw per family
   (plus `randnet2` as a second critic draw at the run's lr). Pairing the same
   draws across every parameter set removes the draw from the between-checkpoint
   comparison, which is the comparison the probe exists for.

**Disclosure that travels with every actor number:** a trained actor is a sharp
policy, so its step-0 forward KL to a near-uniform random target is an order of
magnitude above a fresh init's (~10 vs ~0.2 nats). Def 1 asks exactly "what can
a fixed budget do from *here*", so that distance is part of the measurement and
not a bug — but the raw final loss must be read next to the step-0 loss and the
fraction-of-initial-remaining, both of which the output carries. The critic legs
have no such asymmetry.

### 2.6 Instrument alongside: effective rank

For each parameter set, `srank99` (smallest k holding 99% of the singular mass)
and the participation ratio of the penultimate features on the **held-out** obs,
**float64**, via `scripts/d22_dormant_rank.py::srank99` — the same hardened
function that backs `results/d22/effective_rank_float64.csv`, including its
Gram/`eigvalsh` fallback and its refusal to record a number it could not
compute. Two feature sets per net: `ctx` (the `ctx_net` output, 384-d —
directly comparable to the D22 CSV) and `head_in` (the actual input to the
trained final layer; for the critic that *is* ctx, for the actor the 256-d
scorer penultimate over all B×10 action pairs).

**Instrument validated before the run** `[V]`: this code path reproduces the
D22 CSV exactly on `showdown_sp_struct50m_s35` @50M — actor `srank99(ctx)` 33,
critic 10, against the CSV's 33 and 10.

### 2.7 Environment

`/opt/anaconda3/envs/pokemon-showdown-rl/bin/python`,
`POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1` (828-d id-suffix encoder,
asserted at start), `torch.set_num_threads(1)`, one process, no Showdown
server, no battles, on a 14-core box whose other load is the running FP queue.

---

## 3. The read — stated before the run

Let **R = (final held-out loss of the trained checkpoint) / (mean final
held-out loss of the two fresh inits)**, on the **critic `randnet` FULL**
condition, at the **better of the two lrs per parameter set** (lr is a nuisance
parameter, not a finding). The branch must hold consistently across the four
trained finals (`100M_final`, `50M_s66/s75/s83`); if the 100M and the 50M trio
disagree, both are reported and **no branch fires**.

| branch | fires when | what it argues for the fleet |
|---|---|---|
| **TRAINABLE** | R ≤ **1.10** | The srank/dormancy numbers are a *representation* artefact of sparse reward (Lyle Cor. 1), not a trainability pathology. **Width is unlikely to pay.** Run Option B unchanged; the live levers are `gae_lambda: 1.0` (Kumar's MC control) and denser auxiliary targets — `MODEL_SCALE` §E(6). Adding the D22 instruments + pre-activation norm as a mechanism cell (§E(5)) is the cheap way to keep the width question measurable. |
| **PLASTICITY LOST** | R ≥ **1.50** (i.e. ≥50% worse than fresh) | A real optimisation pathology. **ARM W is the right pair** — width **plus** L2-toward-init, which is Lyle's own InFeR family `[V]`. Launch 3 × L2 + 3 × ARM W as §E(2) drafts it. |
| **REPRESENTATION DEGENERATE BUT TRAINABLE** | FULL R ≤ 1.10 **and** HEAD-ONLY R ≥ 1.50 | The parameters move fine; the *features* the frozen trunk hands its head are poor. Width adds capacity to a trunk that is not using the 384 it has — a **weak** case for ARM W, a stronger one for changing the TARGET (λ=1.0, dense aux) and for LayerNorm inside `ctx_net` / the value stack (BRO's essential component). |
| **EQUIVOCAL** | 1.10 < R < 1.50 | Report the number; credit neither branch. The probe has not moved the decision, and the fleet call rests on the scale report's other lines. |

Secondary reads, descriptive, no branch attached: the `iid` memorisation leg
(train loss only), the `randpol` actor leg, the early rungs (`early_500k`,
`early_1M`, `100M_rung12M`) as the training-time trajectory Lyle's Figure-1
shape would show, and the srank table.

### 3.1 What this probe cannot answer

- **It cannot say whether 1024 would help.** It measures whether the *current*
  384-wide critic is broken as an optimisation object, not whether a wider one
  would learn a better value function. No width is varied here.
- **Fitting random targets is not the RL objective.** A net can have full
  target-fitting capacity and still be signal-limited, which is `MODEL_SCALE`
  §D'-2's separate claim (5.6 label-bits per parameter, high aleatoric noise, a
  critic EV plateau at 0.59). "TRAINABLE" removes one explanation for the
  plateau; it does not explain the plateau.
- **6,000 steps, one target draw per family, one optimisation run per cell.**
  There is no seed-level error bar on any single cell; the protection is that
  every cell shares its target draw and batch-order stream with every other
  parameter set, so the *differences* are paired even though the levels carry
  the draw.
- **It says nothing about `l2_init_decay` on its own.** InFeR-family
  regularisation is Lyle's remedy for capacity loss; if capacity is not lost,
  this probe is silent on whether L2-toward-init helps for other reasons (D23
  already moved critic srank with it — a separate measurement).

---

## 4. Results

Run 2026-09-12 03:16–03:58Z, one process, one thread, **2,470 s** wall
(≈41 min CPU), started after `ENS3FR DONE` cleared the 20 ms Foul Play queue.
No checkpoint was skipped. Raw: `results/plasticity_probe/probe.json`.
All numbers `[V]`.

### 4.1 PRIMARY — critic, random-network targets, FULL (Def 1 proper)

Held-out MSE against a unit-variance target (held-out target variance 1.029).
Every parameter set starts from essentially the same loss (~1.32), so this leg
has **no travel-distance confound**. `R` = best-lr final ÷ mean of the two
fresh inits at that lr.

| param set | step 0 | 1500 (25%) | 3000 (50%) | 6000 (100%) | 6000 @ lr 1e-3 | best | **R** |
|---|---|---|---|---|---|---|---|
| `100M_final` | 1.319 | 0.1946 | 0.1588 | 0.1280 | 0.1024 | 0.1024 | **1.89** |
| `50M_s66` | 1.325 | 0.1897 | 0.1438 | 0.1201 | 0.0920 | 0.0920 | **1.70** |
| `50M_s75` | 1.321 | 0.1902 | 0.1485 | 0.1291 | 0.0919 | 0.0919 | **1.69** |
| `50M_s83` | 1.341 | 0.1821 | 0.1451 | 0.1178 | 0.0924 | 0.0924 | **1.70** |
| `100M_rung12M` | 1.415 | 0.1796 | 0.1456 | 0.1324 | 0.0915 | 0.0915 | **1.69** |
| `early_1M` | 1.442 | 0.0998 | 0.0956 | 0.0870 | 0.0645 | 0.0645 | **1.19** |
| `early_500k` | 1.374 | 0.0836 | 0.0791 | 0.0720 | 0.0565 | 0.0565 | **1.04** |
| `fresh_a` | 1.305 | 0.0695 | 0.0572 | 0.0554 | 0.0564 | 0.0554 | **1.02** |
| `fresh_b` | 5.995 | 0.0736 | 0.0555 | 0.0533 | 0.0520 | 0.0520 | **0.96** |

Same ordering on the **second target draw** (`randnet2`, lr 2.5e-4 only, so not
best-of-lr): `100M_final` **2.11**, `50M` trio **2.11 / 2.12 / 2.19**, `12M`
**2.28**, `early_1M` 1.61, `early_500k` 1.35, fresh 0.95 / 1.05. The ordering is
also identical at each lr taken alone (at lr 2.5e-4 the 100M ratio is 2.36).

The **memorisation** leg (`iid` N(0,1), **train** loss — held-out is meaningless
by construction and comes out at 1.0–1.7 for everything, which is the control
working): `100M_final` 0.730, `12M` 0.669, `50M` trio 0.539 / 0.557 / 0.626,
against fresh **0.127 / 0.138** and `early_500k` **0.127** — **R 3.6–5.5**. A
trained net is far worse at memorising arbitrary labels than a fresh one; an
early rung is indistinguishable from fresh.

### 4.2 HEAD-ONLY — what the frozen trunk's features can support

Held-out MSE of the best linear readout of the frozen penultimate features.

| param set | 6000-step best | closed-form least squares | held-out **R²** |
|---|---|---|---|
| `100M_final` | 1.007 | 0.9988 | **0.029** |
| `50M_s66` | 1.006 | 0.9806 | **0.047** |
| `50M_s75` | 0.997 | 0.9689 | **0.058** |
| `50M_s83` | 1.015 | 1.0003 | **0.028** |
| `100M_rung12M` | 0.996 | 0.9713 | **0.056** |
| `early_1M` | 0.891 | 0.8896 | **0.135** |
| `early_500k` | 0.796 | 0.7815 | **0.240** |
| `fresh_a` | 0.302 | 0.2973 | **0.711** |
| `fresh_b` | 0.269 | 0.2551 | **0.752** |

This is the run's largest single effect, and it is **not** an optimisation
artefact: a closed-form ridge solve (λ=1e-6, float64) on the same cached
features lands within 0.01–0.03 of what 6,000 Adam steps found, on all nine
parameter sets `[V]` (`scripts/plasticity_probe.py --linear-probe` →
`results/plasticity_probe/linear_probe_check.json`). **The trained critics'
384-d context features linearly explain 3–6% of a fresh random critic's output;
a fresh init's explain 71–75%.** R_HEAD is 3.49–3.55 for every trained final.

### 4.3 Actor — read with the step-0 disclosure

| param set | step 0 KL | 6000 best | frac of initial left | **R** |
|---|---|---|---|---|
| `100M_final` | 9.135 | 0.0147 | 0.0016 | **3.43** |
| `50M_s66/s75/s83` | 9.10 / 9.46 / 9.26 | 0.0114 each | 0.0013 | **2.65 / 2.66 / 2.66** |
| `100M_rung12M` | 8.481 | 0.0112 | 0.0013 | **2.60** |
| `early_1M` | 1.821 | 0.0064 | 0.0035 | **1.49** |
| `early_500k` | 0.704 | 0.0053 | 0.0076 | **1.24** |
| `fresh_a / fresh_b` | 0.210 / 0.211 | 0.0042 / 0.0044 | 0.020 | **0.99 / 1.01** |

The raw R is 2.6–3.4, but a trained actor starts **43×** further from the
target than a fresh init and closes **99.84–99.87%** of that gap against the
fresh init's 98%. The actor leg is directionally consistent with the critic's and is
**not** the clean measurement; the critic leg is.

*Care with "the actor degrades far less"* (STATUS.md, commit `834b265`). It is
right on the two legs that are read-comparable — the actor's frozen features
still support a fit (HEAD-ONLY closes 98.3% of its initial KL where the
critic's frozen features close ~0%) and its `srank99(ctx)` is 369–370/384
against the critic's 48–139. It is **not** right on the raw FULL ratio, where
the actor's 2.6–3.4 is numerically worse than the critic's 1.69–1.89 purely
because of the step-0 distance. Quote the srank and head-only legs for that
claim, not R.

### 4.4 Effective rank — and a correction to `MODEL_SCALE` §D'-3

srank99 / 384 on the held-out obs, float64, same function as the D22 CSV.

| param set | critic srank99(ctx) | critic PR | actor srank99(ctx) | actor PR |
|---|---|---|---|---|
| `100M_final` | **48** | 1.03 | 370 | 8.62 |
| `50M_s66` | 139 | 1.31 | 370 | 10.35 |
| `50M_s75` | 94 | 1.25 | 370 | 9.15 |
| `50M_s83` | 102 | 1.52 | 369 | 9.01 |
| `100M_rung12M` | 241 | 2.34 | 367 | 10.46 |
| `early_1M` | 323 | 3.34 | 359 | 6.97 |
| `early_500k` | 322 | 2.94 | 343 | 4.63 |
| `fresh_a / fresh_b` | 297 / 305 | 1.29 / 1.33 | 289 / 313 | 1.31 / 1.42 |

**`MODEL_SCALE` §E(2)(a) argues for ARM W partly on "our critic sits at srank99
7–10/384 against the actor's 33–54". Those numbers belong to the D22
`showdown_sp_struct50m_s{35,36,37}` lanes, not to the lineage the fleet builds
on.** On `showdown_sp_100m_s112` and the `showdown_sp_batch50m` trio the critic
measures **48–139/384** and the actor is at **essentially full rank, 369–370/384
— above a fresh init's 289–313.** The instrument is not at fault: this same code
path reproduces the D22 CSV exactly on `struct50m_s35` (actor 33, critic 10) and
the pooled-vs-own-obs difference is ≤1 `[V]`. The actor/critic **ordering**
survives everywhere; the **severity** does not transfer between run families.

Note also that rank and trainability do not track each other cleanly *across*
runs: `100M_final` has the lowest critic srank (48) and the worst R (1.89), but
the 50M trio spans 94–139 at a flat R of 1.69–1.70. They do track *within* a
training trajectory (500k: 322 / R 1.04 → 12M: 241 / R 1.69 → 100M: 48 / R
1.89). This is Lyle 2303.01486 §5.2's point restated by our own data: rank is
correlated with, but not a substitute for, a trainability measurement.

### 4.5 The trajectory

R (critic, FULL, best-lr) against training step, the shape Lyle's capacity-loss
figures show:

```
  500k   1.04   ←  indistinguishable from a fresh init
    1M   1.19
   12M   1.69
   50M   1.70  1.69  1.70   (three independent seeds)
  100M   1.89
```

**Capacity loss is essentially complete by 12M.** 12M → 100M, an 8× increase in
experience, adds 0.20 to a ratio that moved 0.65 over the first 12M.

---

## 5. Verdict

### The branch that fired: **PLASTICITY LOST**

Pre-stated threshold: R ≥ 1.50 on the critic `randnet` FULL condition, at the
better lr, consistently across the four trained finals. Measured **1.89 / 1.70 /
1.69 / 1.70** — fires, at both lrs taken separately, on both target draws, and
corroborated by the memorisation leg at R 3.6–5.5.

*Reconciling two numbers for one result:* STATUS.md and
`configs/showdown_monster200m.yaml` (commit `834b265`, written off this
probe's JSON) quote **2.3×** for the 100M critic. That is the ratio at the
run's own lr, 2.5e-4 (0.128 ÷ 0.0544 = 2.36). The **1.89** above is the
pre-registered statistic — best-of-lr, which is more conservative because the
trained checkpoints benefit more from lr 1e-3 than the fresh inits do. Both are
this table; the branch fires either way, and 1.89 is the one the pre-reg binds. The
REPRESENTATION-DEGENERATE-BUT-TRAINABLE branch required FULL R ≤ 1.10 and does
**not** fire: HEAD-ONLY is indeed catastrophic (R 3.5, R² 0.03), but FULL is
impaired too, so this is not a pure representation artefact of sparse reward.

**Per §3's table this is the branch that argues for ARM W — width *plus*
L2-toward-init.** Three qualifications travel with that, and none of them is
optional:

1. **The loss is real but moderate in absolute terms.** The trained critic
   still explains **90%** of a random target's variance under this budget
   (0.102 MSE on variance 1.029) where a fresh init explains **94.7%** (0.054).
   This is not a net that has stopped learning; it is a net that has lost about
   half of its residual headroom.
2. **The probe is direct evidence for the REGULARISER half of ARM W and only
   indirect evidence for the WIDTH half.** Lyle's own remedy for exactly this
   measurement is InFeR — *"regressing a subspace of features towards its value
   at initialization"* `[V]` — which is `l2_init_decay`'s family, not width.
   Width enters through Lyle 2402.18762 (*"Across depths, increasing width is
   beneficial"*) and Sokar's width-invariance of dormancy `[R]`, neither of
   which is a capacity-loss-under-width measurement. **Nothing here says
   `value_sizes: [1024,1024]` recovers the lost capacity.**
3. **Capacity loss saturates by 12M**, so ARM W would have to earn its keep by
   *resisting or recovering* capacity, not by delaying an onset that the 200M
   lane will reach in its first 6% of steps either way.

And one correction that cuts the other way: **§4.4 retires "critic srank99
7–10/384" as evidence for the fleet's own lineage.** The batch50m/100M critics
are at 48–139/384 and their actors at full rank. `MODEL_SCALE` §E(2)(a) should
be read with that substitution; the actor/critic *ordering* it relies on
survives, the severity does not.

### The single sentence

> Under an identical 6,000-step budget the 100M and 50M critics fit fresh random
> targets **1.7–1.9× worse** than a fresh init of the same architecture, and
> their frozen features support **no** linear fit of one (R² 0.03 vs 0.71) — the
> pre-registered **PLASTICITY LOST** branch fires, which is the branch that
> argues for ARM W, with the caveat that the probe directly supports the
> `l2_init_decay` half and only indirectly the width half.

### What follows for the ~30 h decision

- **Launching 3 × L2 + 3 × ARM W is consistent with this probe.** It is not
  *required* by it: the measured pathology is an optimisation one, and the
  instrument that would tell you width fixes it does not exist in the
  literature or here.
- **If only one thing changes, make it the regulariser, not the width.**
  `l2_init_decay` is on both arms of §E(2) already, so the L2 trio alone
  already tests the intervention this probe points at — and §E(5)'s fallback
  (Option B unchanged + the D22 instruments and the pre-activation norm as a
  named mechanism cell) remains a defensible read of tonight's result.
- **The mechanism co-primary in §E(4) should add this probe as a rung.** Re-run
  `scripts/plasticity_probe.py` on the W-arm and L2-arm finals: R against a
  fresh init of *each arm's own architecture* is the direct test of whether
  width bought back capacity — the measurement nobody in this literature has
  made, and it costs 41 min of CPU.
- **`gae_lambda: 1.0` is not dismissed by this result.** Kumar's bootstrapping
  mechanism predicts exactly the collapse in §4.2; the probe cannot distinguish
  "sparse reward" from "bootstrapping" as its cause, and §E(6) still ranks that
  lever above width for the fleet after this one.

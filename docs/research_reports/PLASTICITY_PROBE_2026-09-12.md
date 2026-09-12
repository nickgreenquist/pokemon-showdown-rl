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

*(filled in after the run — see §5 for the verdict)*

## 5. Verdict

*(pending)*

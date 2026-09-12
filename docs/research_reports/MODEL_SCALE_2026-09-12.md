# Model scale — are we too small? (2026-09-12)

Asked 2026-09-11: *"check our model param size to see if we have enough params to
actually learn something deep? … and since we have time to train 250M or more due to
our optimizations: have the agent see if more params will help."*

**Marks.** `[V]` verified this session (instantiated the net / read the repo artifact /
read the paper body). `[D]` derived by arithmetic from `[V]` numbers. `[R]` secondary
only. **Rule 6:** no 12M/50M win-rate A/B is cited as evidence, kill or caveat.
`IDEAS_POST_100M.md` §3 filed width as MECHANISM-BOUNDED-**BUT-CONTINGENT** and says
re-opening on a changed premise "is not re-proposing" — so it is open.

## TL;DR

1. **Gen-1 actor is 626,059, not 674,763** (that is the *gen-4* actor). Trained object
   = actor 626,059 + critic 494,849 + aux 49,479 = **1,170,387** `[V]`.
2. **A 200M lane is 1.75e16 FLOP; the 6-lane fleet ≈1.05e17 — ~25 min of one A100.**
3. **RL scaling laws at our actual compute say we are NOT undersized.** Hilton's fitted
   frontiers give compute-optimal N = **42k–186k** on three Procgen arms and Dota; only
   the MNIST calibration says 11M. His line: optimal RL model size is *"consistently
   smaller than for generative modeling, in some cases by multiple orders of magnitude."*
4. **The board-game self-play family says the opposite** — Neumann & Gros: **≈350 Elo
   per 10× params**, and published AlphaZero-class systems were undersized *"by up to
   two orders of magnitude."* Our *problem* is that family; our *compute* is Procgen's.
5. **I was wrong that bigger nets lose plasticity faster.** Sokar: dormancy is
   **width-invariant**; Lyle: *"increasing width is beneficial"*; Nikishin: injection
   gains *decrease* with net size. **Depth** is the hazard, not width.
6. **Three independent sources say widen the CRITIC, not the actor** — Andrychowicz
   (on-policy, 250k agents): *"use a wide value MLP… tune the policy width (it might
   need to be narrower)"*; BRO; SimBa's grid (critic 64→1024: **303→722**; actor
   64→1024 at fixed critic: **690→706→706→686→648**).
7. **Our data agrees:** critic ctx srank99 **7–10/384** at 50M vs the actor's 33–54;
   critic EV plateaus at **0.59** by mid-run and never improves `[V]`. Moalla — the one
   paper measuring *our* metric *in PPO* — finds exactly this ordering under sparse reward.
8. **But both our instruments are weak evidence, and the literature says so.** Lyle
   §5.2 falsifies feature rank *and* dormancy as causal indicators; Lyle Cor. 1 predicts
   collapse as the *sparse-reward limit*; Kumar shows it is a **bootstrapping** pathology
   MC targets remove — and λ=0.95 makes ~53% of our value target the critic's own output.
9. **Width has never been varied here: 125 run configs, all `entity_dim 128 /
   ctx_sizes [384,384]`** `[V]`, and `ACTOR_PARAM_CEILING 681_994` fails construction
   for any wider *actor* (it does not gate the critic).
10. **Recommendation.** (a) Run the **capacity-loss probe tonight** — frozen-checkpoint
    refit, CPU-only, no training run, ~1 h: it separates "too small" from "won't train"
    before launch. (b) Fleet: **3 × L2 + 3 × ARM W**, ARM W = `value_sizes: [1024,1024]`
    + `l2_init_decay: 0.02` → critic 494,849 → **1,807,489**, trained 2.12×, **54.4 h**
    (base 44.7 h), free at greedy inference, needs no ceiling ruling. Replaces arm C.
    Expected win-rate gain **modest and unresolvable at k=3** — the product is the
    measurement.

## A. OUR SIZE — by instantiation

From `configs/showdown_monster200m.yaml`'s `agent` block at the gen-1 layout
(`POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1`; obs 828, priv 408, 10 actions),
`torch.set_num_threads(1)`. All `[V]`.

| module | actor (out 10) | critic (out 1) | actor MAC/fwd |
|---|---:|---:|---:|
| `ctx_net` 640→384→384 | 393,984 (62.9%) | 393,984 (79.6%) | 393,216 |
| `scorer` 512→256→1 ×10 pairs / `head` | 131,585 (21.0%) | 385 | 1,313,280 (59%) |
| `mon_net` 114→128→128 ×12 | 31,488 | 31,488 | 371,712 |
| `move_net` 110→128→128 ×4 | 30,976 | 30,976 *(dead)* | 121,856 |
| `field_net` 6→128→128 | 17,664 | 17,664 | 17,152 |
| `move_emb` + `species_emb` | 20,352 (1.7%) | 20,352 | (gather) |
| **total** | **626,059** | **494,849** | **2,217,216** |

Aux oppact head **49,479**; critic forward 904,320 MAC; arm C's privileged critic
642,305. **`actor 674,763 / critic 543,553` is the GEN-4 pair**
(`runs/gen4_wang50m_s200/meta.yaml`, obs 1,448, three embeddings per mon token).

**FLOPs.** Epoch loop = 9,120,896 MAC/row (actor 3× fwd; critic 3× fwd minus the dead
`move_net` backward) = **18.24 MFLOP/row** over 1,120,908 actor+critic params, against
6·N = 6.7 MFLOP for a dense net that size: **we do 2.7× the arithmetic per parameter**
(one subnet over 16 tokens, one scorer over 10 pairs). Per env step, **87.5 MFLOP =
74.8 FLOP/param/interaction** `[D]`, vs Hilton's measured 24.2 for a dense MLP-PPO and
2,136 for a Procgen CNN. One actor forward ≈20 µs — **inference is never the constraint.**

**The gate.** `rl/networks/entity_deepsets.py:60/391` asserts `ACTOR_PARAM_CEILING =
681_994` for the gen-1 layout, so any wider **actor** dies at construction; three tests
pin it. Purpose is R0-2/K2 — keep the *structure* rung from testing capacity. **It does
not gate the critic**, so §E's arm clears it with no ruling and no test edit.

## B'. SELF-PLAY RL AT SCALE

All `[V]` from the primary paper unless marked; params marked `[D]` derived via 18·b·c²
(calibrated against lc0's published T78 = 194.5M).

| system | params | samples | compute | samples/param `[D]` |
|---|---:|---:|---|---:|
| **ours, 200M lane** | **1.17M** | 2.0e8 steps | 1.75e16 FLOP, 43 h CPU | **171** |
| Huang & Lee 2019 (our comparable) | 1.33M | 2.3e8 decisions | 6 d, ~$91 | 173 |
| KataGo main run | 1.0M→**23.6M** | 241M samples / 4.2M games | ~1.4 GPU-yr | 10 |
| AlphaGo Zero 20b / 40b | 24.0M / 47.6M | 1.43e9 / 6.35e9 positions | 3 d / 40 d | 60 / 133 |
| AlphaZero (chess) | ~23.5M | 2.87e9 pos / 44M games | 5,000 TPU, 9 h | 122 |
| OpenAI Five | **159M** | 180 days | **770 PF-days** | — |
| AlphaStar | **139M** (55M at inference) | 971k replays + league | 12 × 32 TPUv3 × 44 d | — |
| DeepNash (Stratego, 1e535 tree) | **NEVER STATED** | 7.21M learner steps | 1,024 TPU nodes | — |
| DeepStack / ReBeL (>1e160 pts) | 3.5M / 18M | 11M / 4.5e9 examples | 175 core-yr / 720 V100 | — |
| **Pluribus (6p NLHE, >1e160)** | **zero nets** | — | **12,400 core-h ≈ $144** | — |
| Hanabi ACHA | ~1.05M | **2e10** steps | ~100 CPU-yr | 19,000 |

**Hilton, Tang & Schulman 2023** — the only law that scaled PPO/PPG. Compute-optimal
`N ∝ C^(1/(1+α_N/α_E))`, exponent **0.40–0.65 (Procgen), ≈0.76 (Dota)** vs Chinchilla's
0.50; *"the optimal model size for RL for a given compute budget is consistently smaller
than for generative modeling, in some cases by multiple orders of magnitude."* They
scaled PPO/PPG width **1/64× to 8× with no plasticity intervention** and got clean power
laws with **no saturation** — the best on-policy width evidence in existence. **At our
C = 1.75e16 FLOP = 2.03e-4 PF-days** `[D]` their own fitted frontiers give optimal N =
**168k** (StarPilot-hard), **176k** (CoinRun-hard), **186k** (FruitBot-hard), **42k**
(Dota 1v1), **11.3M** (MNIST h=32) — four of five *below* our actor. Their own warning
is why this is not a verdict: coefficients are not portable (*"2,000 times longer on
Dota 2 than on MNIST"*), only exponents are. **Exponent-only: 10× more env steps
justifies a 2.5×–6.3× larger net.**

**Hilton §5.2, the environment-cost clause — the strongest pro-bigger argument for our
setup, and it is weaker than it looks.** With `N_e` = env cost per interaction in
param-equivalents: *"it is only efficient to take N ≪ N_e when C is very small… it is
usually inefficient to use a model that is much cheaper to run than the environment."*
**Our N_e ≈ 560k–630k** `[D]`: collection is 34.87% of wall against the update's 65.13%,
so the environment's wall converts to ≈42.1 MFLOP/env-step at the update's efficiency,
divided by our 67–75 FLOP/param/interaction. Our trained object is 1.17M ≈ **1.9–2.1
N_e** — we are already *past* the "much cheaper than the environment" regime. The clause
gives a discount on further width, not a mandate; our cost model's `0.35 + 0.65·r` **is**
that discount, measured.

**Neumann & Gros 2022 (AlphaZero on Connect Four / Pentago) — our family.** α_N =
**0.88**, α_C = 0.55, `N_opt ∝ C^0.63`. **≈350 Elo per 10× params** at unbounded
compute; *"previously published state-of-the-art game-playing models are significantly
smaller than their optimal size"* — for AGZ/AZ *"by up to two orders of magnitude."*
**Counterweight, App. B:** at **fixed inference compute** the fit falls to 240
Elo/decade and *"the trend breaks for large models… larger agents break off at different
points which depend on the amount of compute given."* Branching 7 vs 288 changed neither
exponent. **Jones 2021 (Hex):** 500 Elo/decade of compute; *"perfect play on a 9×9 board
can be achieved by a fully-connected residual net with two layers of 512 neurons… 500k
parameters"* — our 626k actor is in that class. **Tuyls 2023 (NetHack IL):**
N_opt ∝ C^**0.61**. The 0.5–0.65 band is robust across IL and RL.

**What these systems did instead of scaling.** KataGo grows the net only *"when its
average loss caught up to the smaller size"* — bigger is strictly worse early; Elo at a
1,600-visit cap runs b6c96 −1276 / b10c128 −850 / b15c192 −329 / b20c256 +76 (confounded
with training time), and its exchange rate is *"each doubling of speed may be worth
somewhere around 150–250 Elo"*. Its measured **9.1× speedup came entirely from auxiliary
targets and architecture**, not size. **lc0's BT2 at 82M beats T78 at 194.5M by +123
Elo.** AGZ's 20b-vs-40b head-to-head gap **is not published**. OpenAI Five's only
measured law is **batch size**, sub-linear, and its 43.4M → 156.7M jump has **no
attributed skill delta**. **No large self-play system in this survey ran a clean
model-size ablation.**

**Showdown context, one paragraph.** Against the only comparable — Huang & Lee, pure
self-play, randbats, attention-free, no search, Glicko 1677 — we are at **parity**:
their 1,327,618 includes **305,408 of gen-7 vocabulary embeddings** (1049 species / 731
moves / items / abilities) gen 1 does not have, so dense params are ≈1.02M theirs vs
≈1.13M ours `[V]`. ps-ppo (14.5M) and Metamon (15M/50M/200M) are 12–170× larger and all
human/expert-data-fit; Metamon's own verdict is that size ordering is *"clearer for BC
than it is for RL"*, a relabelled 15M beat their 200M, and PokéAgent's Table 1 has
**57M out-ranking 200M** on gen-1 GXE `[V]`.

## C. COST ON OUR BOX — a model, not a measurement

**Measured** `[V]`: `maxout.json` — width 6 **1,282.3** steps/s/lane, width 3
**1,620.5** (k=8, idle, evals off); `update_share.json` — **update 0.6513 / collect
0.3487** of wall; Rust ≤8.7% of collection. Baseline **200M = 43.3 h/lane at width 6**.
**Model:** `hours = 43.3 × (0.3487 + 0.6513·r_upd)` (lower) to
`43.3 × (0.030 + 0.3184·r_act + 0.6513·r_upd)` (upper); `r` are exact MAC ratios from
`nn.Linear` hooks. Truth sits near the lower bound — collection's MAC load (≈4.4
MMAC/env-step) is ~12% of the epoch loop's (~38), so collection wall is Rust simulation
and marshalling. **Rows include L2's measured −3.2%.** "Mixed" = this arm as 3 of 6 lanes
beside 3 base+L2 lanes that finish at 44.7 h and hand the box back to 3-wide.
**Critic-only widths cost nothing at collection, so their bracket collapses.**

| variant | actor P | critic P | trained P | ×par | r_upd | mixed fleet |
|---|---:|---:|---:|---:|---:|---:|
| **BASE** | 626,059 | 494,849 | 1,170,387 | 1.00 | 1.00 | **44.7 h** |
| **V768** `value_sizes [768,768]` | 626,059 | 1,184,129 | 1,859,667 | 1.59 | 1.22 | **49.8** |
| **V1024** `value_sizes [1024,1024]` | 626,059 | **1,807,489** | 2,483,027 | 2.12 | 1.42 | **54.4** |
| V1536 `value_sizes [1536,1536]` | 626,059 | 3,447,425 | 4,122,963 | 3.52 | 1.95 | 66.5 |
| A-CTX768 (actor ctx only) | 1,413,259 | 494,849 | 1,994,451 | 1.70 | 1.54 | 57.0–65.5 |
| ENT256 (both nets) | 1,083,019 | 919,041 | 2,063,955 | 1.76 | 1.95 | 66.5–74.9 |
| BOTH-CTX768 | 1,413,259 | 1,184,129 | 2,683,731 | 2.29 | 1.76 | 62.1–70.6 |
| W2 (uniform ~2×) | 2,431,755 | 1,907,201 | 4,437,715 | 3.79 | 3.87 | 120–160 |
| W4 (uniform ~4×) | 9,582,091 | 7,484,417 | 17,263,827 | 14.75 | 15.21 | 459–664 |
| *arm C (privileged critic)* | 626,059 | 642,305 | 1,317,843 | 1.13 | 1.15 | ~47 |

A uniform 2× does not fit (120–160 h against a 72–96 h window). **Critic width is ~3×
cheaper per parameter than actor width** — no 10-way scorer, and it never runs at
collection. V1024 buys **2.12× the trained object for +9.7 h.**

**Memory is not a constraint.** Params+grad+Adam(m,v) = 16 B/param: **18.7 MB/lane**
BASE, **39.7 MB** at V1024, against **1.825 GB/lane** measured at width 6. Rollout
buffers (30,720 × 828 × 4 B ≈ 102 MB, twice) and 256-row activations are
width-insensitive. The 6-wide budget and 9-wide refusal are unchanged.
**And widening does not change `OBS_DIM`** `[V]` — the "changing OBS_DIM invalidates
every checkpoint" landmine does not apply; cross-play works and mixed-width committees
work, because `eval_checkpoint.py` builds each member via `make_agent(cfg, …)` from its
own run's config. No eval or search path hardcodes a width.

## D'. FIRST PRINCIPLES

### D'-1. What function does this problem need?

From the vendored generator (`showdown/data/random-battles/gen1/data.json`, `[V]`):
**146 species**, level fixed per species, median **5 distinct 4-move sets/species**,
mean **2.42 bits** of set entropy; team draw **33.5 bits/side**. Crude perfect-info
state: teams 67 + sets 29 + HP 80 + status 34 + stages 30 + active 5 + volatiles ~10 ≈
**254 bits ≈ 1e77 states** `[D]` — above chess, far below Go (1e360) and Stratego
(1e535). Raw state count is the wrong axis; **factorisation** is:

- **Go/chess need non-local computation** (life-and-death, ladders, ko) — hence 20–60
  residual blocks. **Gen-1 randbats factorises:** 12 near-independent Pokémon, a type
  chart, a speed order, no items, no abilities, no hazards. Our DeepSets trunk *is* that
  factorisation, and H&L chose it independently. No known gen-1 concept demands a tower.
- **The hidden information is shallow and non-adversarial** — the opponent's team comes
  from a *public, enumerable* generator, so belief is a posterior over a known prior,
  not over an adversary's chosen private state; our own measurement puts the **residual
  at 0.024–0.034 nats** (88–90% of the apparent entropy is a deterministic cap mask)
  `[V]`. The machinery DeepStack/ReBeL/Pluribus exist for, we do not need — and they
  solved 1e160-decision-point games with 3.5M params, 18M, and *zero*.
- **What is hard is simultaneous-move mixing and noise.** From the vendored gen-1 engine
  `[V]`: crit = `floor(baseSpeed/2)/256` (**25–27%** for a base-130/140 speedster;
  `critRatio 2` moves clamp to 255/256); damage `random(217,256)/255`, a **15%-wide
  roll**; paralysis `randomChance(63,256)` = **24.6%/turn**; a "100%" move misses 1/256;
  confusion self-hit 50%; freeze permanent. Neither is a capacity problem. **Our own
  series confirm it** `[V]` (`runs/showdown_sp_100m_s112/history.csv`): critic **EV 0.39
  → ~0.60 then flat for the whole second half** (last-50 median 0.592); policy **entropy
  1.79 → 0.31 nats** against a ~2.2 ceiling, with `clip_frac` 0.22–0.23 vs `clip_eps`
  0.2 and `approx_kl` 0.042 — a nearly pure policy in a simultaneous-move game is
  exploitable by construction. Objective and regularisation, not capacity.

### D'-2. Data budget — data-limited or capacity-limited?

One 200M lane, from measured constants (L̄=30.7; 30,720-step update; 4 epochs; 120
minibatches → 256 rows, 480 grad steps/update; 6,510 updates → 3.12M grad steps):
env steps **2.00e8**, episodes 6.51e6, sample-passes 8.00e8, trained params 1.17e6 →
**171 env steps per parameter**; training **1.75e16 FLOP/lane**, **1.05e17** for the
fleet ≈ **25 min of one A100**; terminal-outcome label bits 6.5e6 → **5.6 bits/param**;
aux oppact dense labels (log₂6/step) 5.2e8 → **442 bits/param**.

**Samples-per-parameter does not discriminate** — the field spans KataGo 10, AGZ-20b 60,
AlphaZero 122, us 171, Hanabi ACHA 19,000 `[D]`. **Label bits per parameter does.**
AlphaZero's MCTS hands every position a full visit-count policy target plus a
search-refined value — at ~5 bits/position, ≈**610 bits/param** `[D]` against our **5.6**
from game outcomes. **We are ~100× poorer in outcome information per parameter than a
search-based self-play system at a comparable samples/param ratio.** That is the real
gap to the field, and parameters do not close it. Our *densest* signal is already an
auxiliary head (442 bits/param, D25) — the axis KataGo's 9.1× actually came from.

**Against compute the two families disagree by 100×:** Hilton's RL frontiers at our C
say 42k–186k (three of four *below* us); Neumann & Gros say AlphaZero-class systems were
undersized by up to 100×. Our *problem* is board-game self-play; our *compute* is
Procgen-scale. **Honest verdict: 626k is not obviously undersized, and not obviously
right-sized either.**

### D'-3. What our instruments say — and what they are worth

`results/d22/effective_rank_float64.csv`, seeds 35/36/37, D24 float64 fix, all `[V]`:

| step | actor srank99(ctx)/384 | critic srank99(ctx)/384 |
|---|---|---|
| 500k | 243 / 254 / 208 | 252 / 242 / 259 |
| 12M | 85 / 5 / 74 | 8 / 14 / 11 |
| 50M | 33 / 46 / 54 | **10 / 7 / 9** |

Dormancy at 50M (τ=0.025): actor `ctx_net` 0.839 / 0.763 / **0.388**; actor `scorer`
0.684 / 0.543 / 0.738; critic `ctx_net` 0.383 / 0.422 / 0.539; actor `mon_net`
0.250/0.195/0.164; critic `mon_net` 0.055/0.078/0.047. srank99(mon)/128 at 50M: actor
72/67/68, critic 83–84. Five corrections the literature forces:

1. **Width does not cause it.** Sokar §5.3 (2× and 4× DQN width): *"the percentage of
   dormant neurons is similar across the varying widths"*, flagged as a surprise. Lyle
   2402.18762 Fig D.4, the only direct width-vs-plasticity ablation in the corpus:
   *"Across depths, increasing width is beneficial."* Nikishin: injection gains
   *"monotonically decrease with the size of the neural network."* **Depth without
   tuning is the hazard; width is not.** My prior was wrong.
2. **Both statistics have been explicitly falsified as causal indicators.** Lyle
   2303.01486 §5.2, 128 DQN agents, names weight norm, weight rank, **feature rank** and
   **sparsity**: *"for each of four quantities, there exists a learning problem where the
   quantity positively correlates with plasticity, and one in which it exhibits a
   negative correlation."* Fig 3 names our axis: *"feature rank and sparsity depend on
   the reward structure of the environment."*
3. **Our reward structure is the predicted limit.** Lyle 2204.09560 **Cor. 1**: under
   sparse rewards *"the feature representation converges to the zero vector for every
   state."* Terminal-only ±1 at γ=1 is that case.
4. **The named cause is bootstrapping, and we have a free dial.** Kumar 2010.14498's
   control: *"by removing bootstrapped updates and instead regressing directly to
   Monte-Carlo estimates of the value, the effective rank does not collapse"* — it is
   *"a pathological interaction between bootstrapping and gradient-based optimization."*
   At λ=0.95 over ~31 decisions, **~53% of our value target is the critic's own output**
   `[V]`. `gae_lambda: 1.0` is a zero-compute one-key intervention aimed at exactly
   this. (Our 7–10/384 is *more extreme* than anything Kumar reports: 20–100 of 512.)
5. **Moalla 2405.00662 measures our metric in our algorithm** — same srank99, PPO,
   δ=0.01; rank decline in 5/6 ALE and 7/8 MuJoCo tasks, always preceded by
   pre-activation-norm growth; **more epochs per rollout (4→6→8) accelerates it** (we run
   4). Its ordering matches ours: normally *"this collapse is not driven by the value
   network, whose rank is still high"*, but *"sparse rewards deteriorate the rank of the
   value network, and… when shared in an actor-critic architecture they, in turn,
   deteriorate the policy."* **Our actor and critic share nothing — protective, and why
   our actor is the healthier half.** And: **no width sweep exists** against PPO rank
   collapse, anywhere.

**So our instruments establish that something changes over training; they do not
establish "too small", and the literature says they cannot.** The corpus's own
trainability instrument is **Lyle 2204.09560 Def 1**: freeze a checkpoint, fit fresh
random targets drawn from our own rollout buffer under a fixed budget, compare the 50M
checkpoint against the 500k one. **CPU-only, no training run.**

### D'-4. Does a bigger net help *more* at 200M than at 12M, in our regime?

**Directionally yes** — N_opt rises with C in every law here, so 16.7× the compute
justifies a **3.1×–8.6×** larger net *if we were optimal at 12M*. We never were: the
size was set by the K2 structure-rung ceiling, not a budget. **Four regime facts price
it down:** (i) label bits, not samples, are scarce (5.6 bits/param) and laws fitted on
dense targets overstate this; (ii) high aleatoric noise — extra capacity cannot fit
noise, and critic EV has been flat since mid-run; (iii) on-policy PPO at a saturated
clip (`clip_frac` 0.22–0.23 vs 0.2, `approx_kl` 0.042) — a larger net at the same
lr/clip moves further per update, partly protected by the full-horizon anneal but a
named risk; (iv) CPU, at `0.35 + 0.65·r` of wall, plus KataGo's 150–250-Elo tax on a 2×
inference slowdown — which is precisely why a **critic-only** widening is the cheap one.
**One prices it up:** Andrychowicz's 250k-agent on-policy sweep — *"for the value
function there seems to be no downside in using wider networks."*

## E. RECOMMENDATION

**(1) Is 626,059 small for this problem?** *Not against the comparable, not against our
compute; yes against the field's headline systems.* Dense-capacity parity with Huang &
Lee (1.13M vs 1.02M, their extra mass being gen-7 vocabulary); at or above
compute-optimal on three of four RL-frontier calibrations at our actual C; in the class
of Jones's perfect-9×9-Hex net. Against ps-ppo / Metamon / AlphaStar we are 12–170×
small — and every one is human/expert-data-fit or has ~1e5× our compute. The strongest
counter is Neumann & Gros: in *this exact family*, published systems were undersized by
up to 100×, worth ≈350 Elo per decade of params. **The hunch is defensible; it is not
supported by the calibration that fits our compute, and it is contradicted by the
closest comparable.**

**(2) Would I add a wider arm to a fleet launching in ~36 h? Yes — one, on the critic.**

> **ARM W:** `agent.trunk_kwargs.value_sizes: [1024, 1024]` (leave `ctx_sizes`,
> `entity_dim`, `scorer_sizes` untouched) **+ `agent.l2_init_decay: 0.02`**.
> Critic **494,849 → 1,807,489** (3.65×, width 384 → 1024); trained object → **2,483,027**
> (2.12×). **3 lanes, 200M, 54.4 h** in a mixed 6-lane fleet — 9.7 h over the base+L2
> trio, deep inside the 72–96 h window.

**Launch 3 × ARM L2** (`showdown_monster200m_l2.yaml`, unchanged) **+ 3 × ARM W.** Not
arm C. **(a)** The critic is where all three evidence lines converge: the actor/critic
asymmetry is unanimous with one on-policy leg (Andrychowicz, BRO, SimBa's grid), our
critic sits at srank99 7–10/384 against the actor's 33–54, and Moalla says sparse reward
is exactly the regime where the value net collapses first. **(b)** It is the cheapest
capacity in the net (2.12× for +9.7 h) and **free at greedy inference**, so KataGo's
speed tax misses the ladder object (disclosure: a *searched* object pays — critic leaf
evals become ~2.45× slower). **(c)** It clears `ACTOR_PARAM_CEILING` with no ruling and
no test edit, unlike every actor-side width. **(d)** Both arms carry L2, so width is read
at matched regularisation; L2 is the on-policy-validated regenerative regulariser
(Juliani & Ash, α 1e-4…1e-2; ours 0.02 is in band), built with 14 tests, and D23's
mechanism leg already moved this exact instrument (critic srank99 31/53/36 vs control
11/17/16 — a mechanism measurement, not a win-rate A/B). **(e)** Arm C is the weakest
candidate and both pre-launch reviews say so (D18's lever at λ 0.95 where the vacatur
named λ 1.0; ~30× less variance headroom at a 30,720-step update; a falsifier
conditioned on an "uncollapsed critic" never observed) — and it widens the critic's
*input* where arm W widens its *capacity*, on the axis never tested. **(f)** No dose is
given up, and two 3-committees plus the 6-member read survive.

**Expected value, plainly: modest.** The compute-frontier calibration argues we are not
undersized; the board-game family argues we are; a 3-seed win-rate primary cannot
resolve the difference. **The product is a measurement nobody in this literature has
made** — no width sweep against PPO rank collapse exists, and none of
AGZ/AZ/OpenAI Five/AlphaStar/DeepNash/FTW ran a clean size ablation.

**(3) Do this first, tonight — it is free and it can change the launch.** The
**capacity-loss probe** (Lyle 2204.09560 Def 1 / Moalla's): load the banked 100M final
and a 500k rung, freeze each, fit fresh random targets drawn from our own rollout buffer
under a fixed optimisation budget (L2 on outputs for the critic, forward KL for the
actor), compare final losses. **CPU-only, no server, no training run, ~1 h.** If the
100M checkpoint still fits random targets as well as the 500k one, the srank number is a
*representation* artifact of sparse reward (Lyle Cor. 1), width is unlikely to pay, and
Option B should run unchanged. If it fits them markedly worse, there is a real
optimisation pathology and ARM W + L2 is the right pair.

**(4) The read — mechanism co-primary, in the header before launch.** k=3 unpaired bars
run 0.065–0.10 and the k=8 shared-control bar is ~0.044, so a win-rate primary returns
"unresolved" by construction. **PRIMARY (mechanism), W vs L2 at matched rungs:**
(i) `srank99(ctx)` **as a fraction of width** — 1024 vs 384 — for the critic, with the
unchanged-width actor as the control; (ii) dormant fraction at τ=0.025 **and τ=0.1**
(Sokar rejected 0.025 as too tight); (iii) **pre-activation norm** of the critic's
penultimate layer — Moalla's leading indicator, and the one instrument we do not log;
(iv) `loss/explained_variance` (does the 0.59 plateau move?); (v) `loss/entropy`.
**Pre-stated branches:** *srank99/width holds or rises* → width is live, size the next
fleet on the curve; *srank99 stays pinned near 7–10 absolute at 2.67× width* →
**MEASURED CEILING**, capacity is confirmed idle, §3's entry goes contingent → final,
and "kill" is earned, which no win-rate A/B at any dose can earn; *EV plateau and norm
trace move but win rate does not* → representational, and the bottleneck is signal
(D'-2). **SECONDARY, descriptive:** off FP@20 per [RWL-3], greedy, n=3000/lane vs the
same-session re-drawn 100M finals; vs SH at the locked protocol; both FP@20 disclosures
travel. **Owed at readout:** RESUMES / NODE_RESTARTS, each resume's `from_step`, the
`/timer` disclosure, and the gen-1 anchor battery (BC-clone h2h PENDING).

**(5) If the maintainer would rather not touch the arms 36 h out** — run [RWL-7] Option
B as drafted and **add the D22 instruments plus the pre-activation norm as a named
mechanism cell on the L2 arm**. IDEAS 4.3, verbatim: the L2 read *"decides whether §3's
width kill stays factual."* Free, bar-independent, and it makes the next fleet's width
decision a measurement. Cost: one fleet cycle of delay.

**(6) Ranked above width for the fleet after this one** — all cheap, all aimed at
measured pathologies rather than capacity: **`gae_lambda: 1.0`** (Kumar's MC control:
zero compute, targets the named cause of rank collapse, and it is what IDEAS 4.7's
vacatur actually named); **LayerNorm inside `ctx_net` and the value stack** (BRO's
essential component — our entity subnets already have a terminal LayerNorm, these stacks
do not; near-free, and Juliani & Ash's best on-policy combination is soft shrink+perturb
*with* LayerNorm); **fewer epochs per rollout** (Moalla's measured dose; ps-ppo runs 2
where we run 4); and **more dense auxiliary targets** (D'-2 — the axis KataGo's 9.1×
came from). Each needs its own pre-reg; none is a Saturday edit.

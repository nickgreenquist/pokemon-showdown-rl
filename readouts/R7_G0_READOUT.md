# R7 G0 — the rollout-Q instrument (I-op) readout

Written 2026-09-23T19:36:05+00:00 by `scripts/r7_g0_readout.py`. **Every number below is re-derived from the rows file at generation time**; nothing is typed.

## Provenance

- rows: `pokemon-showdown-rl/results/r7_g0/rollout_q.rows.jsonl` — sha256 `fa50141ead6c9184…`, **500 positions**, instrument `rollout_q/1`, rows written by `scripts/rollout_q.py` at git ['bd30afe'], qos ['background'], c6 [False], tables ['d2ba00c2ef52'].
- dose per row: `rollouts_per_cell` [256] split half/half, the FULL row × column matrix; 15.6 core-hours of rollouts; mean 111 policy steps per position.
- committee: `ckpt_200000000.pt` (step 200000000, sha `a502af3af5b8`), `ckpt_200000012.pt` (step 200000012, sha `add6e89a3fe7`), `ckpt_200000003.pt` (step 200000003, sha `33108eadc38c`); bank `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/data/engine/teams_a1_5000000.bin`; summary JSON written 2026-09-23T16:14:10.635392+00:00.
- plan: `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md` §6; the kill rule and the branch are quoted verbatim below. Rule 6: nothing here is a win-rate A/B.

## The kill read — split-sample `regret_depth1_ceiling`, WIN-RATE scale (outcome / 2)

> the UPPER 95% bound of the mean split-sample regret_depth1_ceiling (WIN-RATE scale) below 0.005, with the measured zero-gap null below it -- plan §6

| bucket (turns) | positions | ceiling mean ± se | upper95 | zero-gap null (mean ± se, expect 0) | re-split replicate (mean ± se) | opp_model_gap |
|---|---:|---|---:|---|---|---|
| **pooled** | 500 | +0.0236 ± 0.0028 | +0.0292 | -0.0003 ± 0.0009 | +0.0246 ± 0.0028 | +0.0594 ± 0.0029 |
| **2-8** | 125 | +0.0301 ± 0.0060 | +0.0419 | -0.0005 ± 0.0016 | +0.0287 ± 0.0058 | +0.0675 ± 0.0043 |
| **9-15** | 125 | +0.0254 ± 0.0061 | +0.0374 | -0.0017 ± 0.0017 | +0.0282 ± 0.0060 | +0.0627 ± 0.0054 |
| **16-22** | 125 | +0.0214 ± 0.0059 | +0.0329 | +0.0005 ± 0.0021 | +0.0248 ± 0.0058 | +0.0614 ± 0.0068 |
| **23-+** | 125 | +0.0176 ± 0.0045 | +0.0265 | +0.0005 ± 0.0018 | +0.0166 ± 0.0045 | +0.0459 ± 0.0060 |

Outcome scale (±1), pooled: ceiling +0.0472 ± 0.0057; zero-gap null -0.0006 ± 0.0018; re-split replicate +0.0492 ± 0.0056. Provenance check: the ceiling re-derived from the stored halves (`q_half_a`, `q_half_b`, `pi2`, `cols`, `a_greedy`) matches the stored column to 0.0e+00.

**On the two nulls.** The instrument's `regret_depth1_ceiling_null` column (`scripts/rollout_q.py::permuted_null`) re-halves the SAME samples and recomputes the split-sample statistic: that is a second, independent draw of the same unbiased estimator, with the SAME expectation as the estimate — a re-split REPLICATE, not the zero-gap null its docstring claims (it reads identical to the estimate on positions where every halving picks the same row). It is reported here as the replication check it actually is. The **zero-gap null** the plan's kill clause names is computed above from the stored halves: the same statistic with the scoring half's row labels permuted relative to the selecting half, so the chosen row carries no information — expectation exactly 0, and its spread is the noise floor. The instrument is corrected in its next version (`rollout_q/2`) after this chapter closes; the rows file is not touched.

**KILL READ (the plan's clause, both halves):** upper95 **+0.0292** vs threshold 0.005 win-rate; zero-gap null **-0.0003 ± 0.0009** (below the threshold at its own 95% bound) → the rule **does not fire**. (The rows' own `kill_read.fires`, which used the re-split column, reads does not fire — same verdict here, different null.)

## The other reads (plan §6, amendment box 2)

| read | pooled | by bucket |
|---|---|---|
| spearman(critic, rollout-Q) over cells | +0.476 ± 0.011 | 2-8: +0.474, 9-15: +0.486, 16-22: +0.494, 23-+: +0.445 |
| spearman(root Q̄ depth-1, rollout-Q) over rows | +0.357 ± 0.021 | 2-8: +0.356, 9-15: +0.334, 16-22: +0.388, 23-+: +0.349 |
| opp_best_outside_top2 (fraction of positions) | 0.534 | 2-8: 0.536, 9-15: 0.496, 16-22: 0.520, 23-+: 0.584 |
| opp_best_outside_top3 (fraction of positions) | 0.388 | 2-8: 0.392, 9-15: 0.360, 16-22: 0.360, 23-+: 0.440 |
| opp_best_outside_top4 (fraction of positions) | 0.250 | 2-8: 0.264, 9-15: 0.248, 16-22: 0.208, 23-+: 0.280 |
| root estimator vs rollout V (across positions) | critic +0.849, search v′ +0.843 | — |

## The T-op read — `regret_critic_depth1` BESIDE its override rate (the landmine: match on the override rate, not the delta)

- T-op at the rows' dials (cols_k 3, chance_s 2, τ 1, critic = the committee's observation critic): **override rate 0.006** (3/500 positions), mean `search/kl_prior` 0.0007, mean margin +0.0011 (outcome), 42 leaves and 13.2 ms per decision (niced, beside the fleet — not a timing number).
- `regret_critic_depth1`, unconditional: +0.0003 ± 0.0002 win-rate — **zero by construction on every non-overridden position**, so this row alone says nothing about the operator.
- `regret_critic_depth1` CONDITIONAL on an override (3 positions): +0.0454 ± 0.0305 win-rate (the split-sample regret of the T-op's action vs greedy where they differ; positive = the override was better under the rollout oracle).
- Amendment-4 dose read on these positions: π_θ top-1 ≥ 0.97 on **0.460** of positions (mean top-1 0.859; §32's R5 read was 0.885 per decision), forced (one legal row) 0.020. Positions here are sampled per turn bucket, not per decision, so this is not a decision-weighted rate.

## The T-op dial sweep — the same critic at every (k, S, τ, gate), read at MATCHED override rates

`top_sweep.json` (`scripts/rollout_q_top_sweep.py`): 500 positions × 300 cells; regret = rollout Q̄(a′) − Q̄(greedy) on the 256-sample means, WIN-RATE; 'ceiling captured' = the cell's summed regret over the split-sample ceiling's. Cells with < 10 overrides are omitted.

| override band | k | S | τ | gate | override | n | regret uncond ± se | regret cond | ceiling captured | kl_prior |
|---|--:|--:|--:|--:|--:|--:|---|--:|--:|--:|
| 0.00–0.03 | 4 | 8 | 0.1 | 0.1 | 0.024 | 12 | +0.0022 ± 0.0011 | +0.0928 | 0.094 | 0.0337 |
| 0.00–0.03 | 9 | 8 | 0.1 | 0.1 | 0.024 | 12 | +0.0020 ± 0.0009 | +0.0832 | 0.085 | 0.0319 |
| 0.03–0.06 | 9 | 2 | 0.25 | 0.05 | 0.032 | 16 | +0.0030 ± 0.0011 | +0.0933 | 0.126 | 0.0125 |
| 0.03–0.06 | 9 | 2 | 0.25 | 0.0 | 0.040 | 20 | +0.0027 ± 0.0011 | +0.0684 | 0.116 | 0.0125 |
| 0.06–0.10 | 2 | 8 | 0.05 | 0.01 | 0.092 | 46 | +0.0040 ± 0.0014 | +0.0435 | 0.170 | 0.1032 |
| 0.06–0.10 | 2 | 8 | 0.05 | 0.0 | 0.096 | 48 | +0.0040 ± 0.0014 | +0.0415 | 0.169 | 0.1032 |
| 0.10–0.15 | 4 | 2 | 0.05 | 0.01 | 0.100 | 50 | +0.0040 ± 0.0015 | +0.0404 | 0.171 | 0.1645 |
| 0.10–0.15 | 4 | 2 | 0.05 | 0.0 | 0.102 | 51 | +0.0040 ± 0.0015 | +0.0394 | 0.170 | 0.1645 |

No cell reads negative: the worst is k 9 S 2 τ 0.1 gate 0.05 at +0.0004 ± 0.0011 (override 0.050). The operator's overrides are better than greedy under the oracle at every dial; the grid's largest override rate is 0.122 (τ ≥ 0.05).

## Root rules on the same matrix — level oracle, split-sample (`root_rules_oracle_split.json`, `scripts/rollout_q_root_rules.py`)

Every rule turns the SAME payoff matrix into a row distribution; scored on the rollout oracle under the foe's prior and against the foe's BEST REPLY (exploitability). Split-sample: chosen on one half of the rollouts, scored on the other. WIN-RATE units; Δ against greedy.

| rule | τ | under prior ± se | Δ | vs best reply ± se | Δ | override (mass) |
|---|--:|---|--:|---|--:|--:|
| greedy |  | +0.0011 ± 0.0142 | +0.0000 | -0.0523 ± 0.0142 | +0.0000 | 0.000 |
| pure_br |  | +0.0248 ± 0.0144 | +0.0236 | -0.0610 ± 0.0142 | -0.0086 | 0.697 |
| soft_br | 1.0 | +0.0015 ± 0.0142 | +0.0004 | -0.0471 ± 0.0142 | +0.0052 | 0.141 |
| soft_br | 0.5 | +0.0023 ± 0.0142 | +0.0012 | -0.0468 ± 0.0142 | +0.0056 | 0.142 |
| soft_br | 0.25 | +0.0037 ± 0.0142 | +0.0026 | -0.0462 ± 0.0142 | +0.0062 | 0.145 |
| soft_br | 0.1 | +0.0067 ± 0.0143 | +0.0056 | -0.0452 ± 0.0142 | +0.0071 | 0.164 |
| regret_matching |  | +0.0032 ± 0.0142 | +0.0021 | -0.0279 ± 0.0142 | +0.0244 | 0.652 |
| maximin |  | +0.0079 ± 0.0143 | +0.0067 | -0.0408 ± 0.0142 | +0.0115 | 0.652 |

## Root rules on the same matrix — level critic, in-sample (`root_rules_critic_k4s2.json`, `scripts/rollout_q_root_rules.py`)

Every rule turns the SAME payoff matrix into a row distribution; scored on the rollout oracle under the foe's prior and against the foe's BEST REPLY (exploitability). Split-sample: chosen on one half of the rollouts, scored on the other. WIN-RATE units; Δ against greedy.

| rule | τ | under prior ± se | Δ | vs best reply ± se | Δ | override (mass) |
|---|--:|---|--:|---|--:|--:|
| greedy |  | +0.0010 ± 0.0142 | +0.0000 | -0.0337 ± 0.0142 | +0.0000 | 0.000 |
| pure_br |  | +0.0002 ± 0.0143 | -0.0009 | -0.0444 ± 0.0141 | -0.0107 | 0.546 |
| soft_br | 1.0 | +0.0008 ± 0.0142 | -0.0002 | -0.0314 ± 0.0142 | +0.0022 | 0.139 |
| soft_br | 0.5 | +0.0011 ± 0.0142 | +0.0001 | -0.0314 ± 0.0142 | +0.0023 | 0.138 |
| soft_br | 0.25 | +0.0015 ± 0.0142 | +0.0005 | -0.0312 ± 0.0142 | +0.0024 | 0.138 |
| soft_br | 0.1 | +0.0025 ± 0.0142 | +0.0015 | -0.0312 ± 0.0142 | +0.0024 | 0.145 |
| regret_matching |  | -0.0053 ± 0.0143 | -0.0063 | -0.0366 ± 0.0142 | -0.0030 | 0.557 |
| maximin |  | -0.0037 ± 0.0143 | -0.0048 | -0.0385 ± 0.0142 | -0.0048 | 0.524 |

## Fusion (P3's licence): `fusion_flip` / `fusion_bound` over resampled worlds

- 500 positions × 4 resampled worlds (`scripts/rollout_q_fusion.py`, B1b): flip 0.010 ± 0.004; bound **-0.0000 ± 0.0001 win-rate** (upper95 +0.0002) against the credit floor +0.025 (plan §10: above it P3's licence is spent and the T-op searches B ≥ 2 worlds).

## PENDING columns, named

- `spearman_privileged`: PENDING on every row — ['no privileged critic is trained for this committee']. The observation critic is the leaf by default (plan §6); the privileged antisymmetric critic (B2) exists as a network but no trained checkpoint of it exists yet.
- A true depth-2 ceiling: unmeasured before the fleet, by the plan's own words (amendment box 3, item 2).

## CPU-share disclosure — G0 ran niced beside the R6 fleet (plan §8)

Window 2026-09-23T00:38+00:00 → 2026-09-23T16:15+00:00 UTC; baseline 2026-09-23T00:12+00:00 → 2026-09-23T00:33+00:00 UTC; rates are `logs/r6_fleet/monitor.log`'s per-rung `rate=` readings (steps/s). Step-matched lanes: a wall cost, not a measurement.

| lane | baseline mean (n) | during G0 mean (n) | during / baseline | during min |
|---|---:|---:|---:|---:|
| showdown_r6_trio_a_s304 | 867 (3) | 1072 (94) | 1.237 | 794 |
| showdown_r6_trio_a_s312 | 969 (3) | 1125 (94) | 1.161 | 846 |
| showdown_r6_trio_a_s320 | 945 (3) | 1046 (94) | 1.107 | 810 |
| showdown_r6_trio_b_s328 | 1145 (3) | 1314 (94) | 1.147 | 1068 |
| showdown_r6_trio_b_s336 | 1138 (3) | 1356 (94) | 1.191 | 1098 |
| showdown_r6_trio_b_s344 | 1124 (3) | 1262 (94) | 1.123 | 984 |

## The branch, in the plan's words (§6)

> **Branches.** The **upper 95% bound** of mean split-sample `regret_depth1_ceiling` below **0.005 win-rate** (the effect of fixing every decision could not clear the credit line even if compounded): a **measured mechanism ceiling on depth-1 search over this policy** — the chapter closes on P1 and the training-side build is not started. Above it: the prize is real and G1 follows. `spearman` picks the first arm's leaf critic (observation by default; privileged only if it ranks better on the same rows); neither ranking above the critic's own raw-value `spearman` on the root: B2 trains the evaluator on rollout labels first (the G0 rows are the dataset).

Read against this file's numbers: the kill rule **does not fire** — the prize is real and G1 follows (engine mirror matches, L-op vs greedy, n = 5,000 per arm, seat-swapped). Leaf critic for the first arm: observation (`spearman_critic` +0.476; privileged PENDING). Estimator: the searched root v′ ranks the rollout root value no better than the critic's raw value (+0.843 vs +0.849).

Rule 6 applies to everything above: these are mechanism reads on 500 positions under the rollout oracle, never a win-rate A/B, and no small-run null is cited.

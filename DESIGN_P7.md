# P7 — BC warm start, staged unfreeze, and shaping: a TRAINING-SIDE package

**Status: PROPOSED, not ratified. Written 2026-08-04 for review.**
Lifecycle: reviewed → revised → the ratified version folds into `PLAN.md` as a Phase-5 scope
block and each arm's pre-registration moves into its config header (the `showdown_r512_lra.yaml`
pattern); this file is then deleted. Nothing here is decided.

Self-contained on purpose — a reviewer should need no other file and no prior conversation.

---

## 1. Where the project is

From-scratch deep RL in PyTorch (no RL libraries, by hard rule). Capstone: Pokémon Showdown
Gen 1 random battles, battle phase only, via poke-env against a local Showdown server. Agent is
PPO with a `[512,512]` MLP over a 611-dim hand-written observation, 10 discrete actions
(6 switch slots + 4 move slots), terminal-only ±1 reward at `gamma = 1.0`.

Benchmark opponent throughout: poke-env's `SimpleHeuristicsPlayer` ("SH"). Locked protocol for
headline numbers: final checkpoint, 1000 battles/seed, 3 seeds pooled, ties count as non-wins.

Numbers that matter here, all measured in-repo:

| result | value | note |
|---|---|---|
| RL best, 6M, flat lr (P5) | 0.3923 ± 0.0089 | r512 recipe |
| RL best, 6M, + LR anneal (P5b) | **0.4433 ± 0.0091** | credited lever, +0.051 |
| RL, 12M, pre-P5 recipe | 0.417 ± 0.009 | `rollout_steps: 128`, not a valid control |
| **BC clone of SH (P4)** | **0.453–0.465** | supervised, same encoder + trunk |
| clone val free-agreement (P4) | 0.9017 / 0.8987 / 0.9047 | 40k battery, 3 seeds |

A run in flight (P6, flat-vs-annealed at 12M on r512) will add two more rows around 01:50 on
2026-08-05. **P7 should not be ratified before P6 reads**, since a 12M result changes the budget
premise underneath it.

## 2. The finding this package is built on

**P4 (2026-08-02) established that the plateau is TRAINING-SIDE, and exonerated the encoder.**
A supervised clone through the *exact* capstone encoder and trunk reaches 0.453–0.465 vs SH —
above every RL result. So a better policy is representable and learnable on this stack; PPO is
not reaching it.

P4 also bucketed the clone's residual disagreements with SH:
- multi-hit exposure (`expected_hits`, a real encoder gap) — **2.1% of disagreements, immaterial**
- all-status agreement — **1.000**
- weakest buckets, forced-switch 0.866 and voluntary-switch-label 0.556 — **boundary sharpness on
  the analytically-covered matchup argmax, i.e. generalization, not missing information**

**Consequence for P7: encoder work and architecture work are NOT the lever.** An earlier draft of
this design proposed enriching the move features first; P4's bucket analysis refutes that framing
and the proposal was dropped. See §7 for the one narrow encoder question that survives.

The complementary caveat P4 itself states, and which P7 must respect: *nothing in P4 shows PPO can
reach that policy under terminal-only reward.* P7 is precisely an attempt to make it reach it.

## 3. External evidence

- **VGC-Bench** (Angliss et al. 2025, arXiv 2506.10326): scratch transformer PPO at 5M steps
  = 0.48 vs SH; BC-initialized variants 0.62–0.78. **+25–30 points at matched budget** — the
  best-evidenced remaining lever anywhere. *Caveat, and it is not small:* VGC-Bench is doubles/VGC
  with a joint action space and team building in scope, and it evaluates against a
  doubles-modified SH. The relative BC-vs-scratch effect transfers across settings far better than
  the absolute win rate does, but this is not the apples-to-apples anchor the project's docs have
  called it.
- **ps-ppo** (Nebraskinator, Gen 9 randbats; full source at
  `/Users/nickgreenquist/Documents/Projects/ps-ppo`, read 2026-08-04): the strongest pure neural
  policy documented. **Confounded, no ablations** — BC-from-SH init + transformer trunk + faint
  shaping + distributional value + 250M states, all at once. Its ">85% vs SH" figure **must not be
  used**: no script in 49 commits ever evaluated against SH. Its ladder Elo is real.
- **Wang** (MIT MEng 2024, gen4randombattles): network alone 0.786 vs SH, but the headline result
  needed MCTS. Source of the LR-anneal ablation this repo already replicated as P5b.

## 4. What P7 proposes

Three training-side changes, aimed where P4 says the bottleneck is. `PLAN.md` already directs that
these be designed "as a pre-registered stack, not one lever at a time," so the arms below share a
recipe and are added cumulatively rather than crossed.

Base recipe for every arm: `showdown_r512_lra.yaml` — `[512,512]`, `rollout_steps: 512`,
`num_envs: 8`, `epochs: 4`, `minibatches: 4`, `lr: 2.5e-4` with linear anneal to 0 over the
budget, `gamma: 1.0`, 6M steps, 3 seeds, `opponent: heuristics`.
**Control for every arm: P5b's pooled 0.4433 ± 0.0091** — same recipe, same budget, same protocol.
Cost per arm: ~2.9 h at 3-wide.

### P7a — BC warm start with a staged unfreeze

Initialize PPO from the P4 clone (`runs/bc_p4_512_40k_s{0,1,2}`), then train in two phases:

1. **Critic-only warmup.** Freeze the backbone and policy head; train the value head alone for a
   short fixed prefix. **This is the load-bearing detail.** P4's clone was trained with *no value
   labels* — "the critic rides along untrained." A naive PPO start would compute advantages from a
   random value function and destroy the cloned policy within the first updates, which would look
   exactly like "BC init doesn't help" while actually measuring a broken handoff.
2. **PPO with a reduced backbone LR**, to keep the cloned representation from being overwritten
   early.

Both steps are lifted from ps-ppo's `LearnerConfig.__post_init__` — `warmup: (backbone 0.0,
actor 0.0, critic 1.0)` then `ppo: (backbone 0.5, actor 1.0, critic 2.0)`. Two honesty notes:
those multipliers are **dead code at HEAD in their repo** (the default mode string doesn't match
the dict key, so `.get(..., (1.0,1.0,1.0))` returns neutral), and they were never ablated. The
*mechanism* is sound and standard; the specific constants are not evidence.

### P7b — faint-based reward shaping

±0.1 per faint alongside the ±1 terminal, symmetric, as ps-ppo uses (`faint_self: -0.1`,
`faint_opp: +0.1`, confirmed in their `config.py`). Rationale: terminal-only ±1 at `gamma = 1.0`
over ~27-step episodes is an extremely sparse signal, and P4 localized the failure to signal /
distribution / optimization. Known trap, from their commit log: an off-by-one in faint attribution
(`17e0955 fixed off-by-one in faint reward calculation`).

### P7c — distributional value head

51-bin categorical value over a bounded support, replacing the scalar head. Independent of the
above and of Pokémon entirely — so it must be validated on **CartPole and MinAtar through the
existing harness first**, where known-good baselines exist, before touching Showdown. This is the
one item that is genuinely a from-scratch deep-RL chapter rather than a capstone tweak.

## 5. Pre-registered reads

Credit line, consistent with P5 and P5b: **delta ≥ +0.025 AND ≥ 2·se_diff** on pooled 3-seed
finals (1000 battles/seed, ties as non-wins) against the P5b control 0.4433.

- **R0 gates, every arm:** late entropy in [0.2, 1.0] (a frozen value is expected under anneal);
  ties ≤ 4%; steps/s within ~25% of the lane baseline for the concurrency used.
- **P7a PRIMARY:** pooled BC-warm-started finals vs 0.4433. VGC-Bench predicts a large effect; a
  null at this budget is itself informative and would be the first evidence that the BC-init
  result does not transfer from doubles/VGC to Gen 1 singles.
- **P7a MECHANISM (recorded, not gated):** win rate at step 0 (should be ≈ the clone's 0.453 if
  the handoff is clean — **if it is far below, the warm start is broken and the PRIMARY is
  uninterpretable**); the 0–500k trajectory, to see whether PPO destroys the init and re-climbs.
- **P7b PRIMARY:** vs the P7a result, one variable. **Comparability warning:** shaping changes the
  objective, so `rollout/episode_return` becomes incomparable to every prior run. Only
  `eval/win_rate` under the locked protocol stays comparable, and the shaped reward must not leak
  into the eval path.
- **P7c:** spine-first. Gate on CartPole/MinAtar parity with the existing baselines before any
  Showdown arm is run.

## 6. Blockers and risks

1. **`rl/train.py:134` refuses `init_from` together with `lr_anneal_steps`.** The guard is
   deliberate: `load_state_dict` restores the agent's update count, so the anneal fraction clamps
   to 0 and the entire run trains at lr ≈ 0 — silently, with no crash and no obviously wrong
   metric. P7a needs both the credited anneal and the init. **This must be resolved as a design
   decision, not bypassed:** the natural fix is that a warm start is a *fresh* run and should reset
   the update counter, but the guard's comment says "no warm-start config anneals, so refuse the
   combination instead of inventing resume semantics." P7 is the config that changes that premise.
2. **The clone's untrained critic** — see P7a step 1. If the warmup phase is skipped or too short,
   the experiment measures a broken handoff rather than the lever.
3. **P4's data constraint.** P4 found the clone still data-limited at 40k battles (per-doubling
   agreement gain +0.021, ratio 0.78, extrapolating to a ~0.97 ceiling) and its one pre-authorized
   doubling is spent. A better clone may be available for the cost of more data — which would raise
   the warm-start floor and is arguably a cheaper first move than any of P7a–c.
4. **Budget premise.** P6 may show 12M materially beats 6M, in which case every arm here should be
   specified at 12M and the control re-derived. Do not ratify before P6 reads.
5. **Stacking vs isolating.** `PLAN.md` directs a stack. The cost is attribution: if P7a+b+c
   together clear the line, we will not know which carried it — the exact failure mode that makes
   ps-ppo uncitable. The arms above are cumulative-but-separately-read to mitigate this, at
   ~2.9 h per arm.
6. **Stop rule.** Ratified 2026-08-02: the 0.5 bar is not chased under this recipe class, and
   training probes need their own pre-registration. P7 is a mechanism package under that rule.
   Amendment condition: the README gains a measured sentence only if a PRIMARY credits.

## 7. Explicitly NOT proposed

- **Encoder enrichment** (STAB flag, `expected_hits`, `self_boost_sum`, `status_prob`) — P4's
  bucket analysis prices the known residue at 2.1% and attributes the weak buckets to
  generalization, not information. *The one question that survives:* P4's audit never priced
  **STAB** specifically, and our encoder omits it while precomputing the harder cross-entity type
  multiplier — ps-ppo encodes STAB explicitly. It is a 4-dim change. Proposed only as a possible
  cheap arm *after* P7a, never as the headline, and note it changes `OBS_DIM` and therefore
  invalidates every existing checkpoint (see §8).
- **Transformer / entity-tokenized trunk** — capacity is not the measured constraint, and on CPU
  it would cost throughput in a loop that is already 95% collect (measured 2026-08-04), where
  inference sits inside collect.
- **JEPA, KV-cache history, move-ID embeddings** — undisclosed and unablated in the only source
  that uses them; the author's public description of the history path contradicts his own code.
- **Wholesale hyperparameter adoption** from ps-ppo (`gamma` 0.999, `clip` 0.1, `epochs` 2, …) —
  each is a separate variable, not a package.

## 8. Operational notes

- **Any `OBS_DIM` change invalidates every existing checkpoint.** All outstanding finals — P6's
  included — must be evaluated *before* such a change lands, or they can only be scored by checking
  out an older commit.
- **Concurrent lanes must carry distinct `--seed` values, including across arms.** Global `random`
  is seeded from `cfg.seed` and poke-env derives player usernames from it, so same-seed concurrent
  lanes collide on Showdown usernames; the loser dies at first `reset` with the misleading
  `TimeoutError: Agent is not challenging`. This killed an entire arm of P6 on 2026-08-04.
- Launchers must stagger starts and assert **battle progress**, not run-dir existence — the run
  directory is written before the first `reset`, so `-d` is true for a lane that never trains.

## 9. Questions for reviewers

1. Does P7a's staged unfreeze adequately address the untrained critic, or does the value head need
   supervised pre-training on returns from the BC dataset before PPO at all?
2. Is the P5b control (0.4433, flat 6M annealed) the right control for a warm-started run, given
   the warm start begins near 0.453? Should the control instead be "the clone, frozen" — i.e. is
   the honest question "does PPO improve on the clone" rather than "does BC init beat scratch"?
3. §6.3: is *more BC data* the cheaper first move than any P7 arm, given the clone is still
   data-limited and the warm-start floor scales with clone quality?
4. Does faint shaping (P7b) risk teaching trade-down behaviour that terminal-only reward correctly
   avoids — and is potential-based shaping worth the extra machinery to preserve policy invariance?
5. Is stacking (§6.5) the right call, or does the attribution cost outweigh the wall-clock saving
   at ~2.9 h per arm?
6. Is anything in §7 wrongly excluded — in particular, is the STAB omission larger than P4's
   bucket analysis implies, given that analysis never isolated it?

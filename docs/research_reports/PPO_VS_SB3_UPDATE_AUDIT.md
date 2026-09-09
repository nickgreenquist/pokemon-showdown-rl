# Our PPO vs Stable-Baselines3 — UPDATE-PATH audit

**Provenance.** Produced 2026-09-08 by a read-only Opus subagent audit at the
maintainer's request ("look at the stablebaseline code, and our code, and
specifically look for optimizations in the library"), then corrected once in
place: revision 1 read `obs_dim` from `runs/gen4_smoke_heur_s1` (a `head -1`
selecting the SMOKE run alphabetically) and so used 612 where this fleet's
width is 1,448. Revision 2's layout derivation is closed three ways against
`runs/gen4_wang50m_s200/meta.yaml` — `obs_dim` 1,448, `priv_dim` 703, and the
stamped `params: actor 674763 / critic 543553` reproduced to the unit from the
derived first-layer widths.

**Spot-checked in the main session before filing:** the SB3 clone's
`version.txt` (2.0.0), `git diff --stat v2.0.0 HEAD` (40 insertions / 12
deletions, 5 files), `target_kl: Optional[float] = None` in
`stable_baselines3/ppo/ppo.py:96`, `loss/approx_kl` p50 0.00086 / max 0.00228
over 1,761 updates, the two `params:` values above, and that 612 belongs to the
smoke run. **Not re-derived by hand:** the per-row MAC counts and byte figures.

**Verdict: NEITHER — do not migrate.** The audit's own "exact vs assumed"
section at the end governs any number quoted from it. Nothing here is a
measurement of wall time; the one measurement it asks for
(`scripts/ch5_mps_update_bench.py --arms cpu1` under `torch.profiler`) needs an
idle box and had not been run when this was filed.

---

# SB3 PPO vs ours — UPDATE-PATH audit (read-only)

*Audited 2026-09-08. **Revision 2** corrects an observation-width error; see
"Correction record" at the end for what changed and what it did not.*

## VERDICT: **NEITHER** (unchanged by the correction)

SB3's PPO contains exactly **one** update-path optimization our implementation
lacks (`target_kl` early epoch termination), it is **off by default in SB3 too**,
and our own gen-4 history says it would **never fire**: `loss/approx_kl` over all
1,761 logged updates of `runs/gen4_wang50m_s200` has mean **0.00103**, p99
**0.00218**, max **0.00228**. SB3's trigger is `approx_kl > 1.5 * target_kl`; at
any target_kl a sane person would set (0.01–0.03) that comparison is never true,
so all 7 epochs always run. Every other item on the shopping list we either
already do, or do *better* than SB3, or SB3 lacks as well.

The one thing SB3's design would nudge us toward is not code we would inherit —
it is `share_features_extractor`
(`stable-baselines3/stable_baselines3/common/policies.py:693`), i.e. a shared
actor/critic trunk. We have deliberately ruled that out
(`rl/networks/entity_deepsets.py:44-47`: "the value variant is a fully separate
stack … no shared trunk (repo contract, ppo.py — H&L DO share; deliberate
deviation, recorded)"). That is a pre-reg-shaped architecture decision, not a
migration.

## Provenance of the SB3 clone (read first, as asked)

- `/Users/nickgreenquist/Documents/Projects/stable-baselines3`
- HEAD `c981d9f842e32ef57fc781c6bcd6b7ec073f9f38`, "merge origina/v2.0.0",
  Jett Wang, 2023-09-04. `origin = quadraticmuffin/stable-baselines3`,
  `upstream = DLR-RM/stable-baselines3`. `version.txt` = **2.0.0**.
- `git diff v2.0.0 HEAD` touches five files, **40 insertions / 12 deletions**:
  `base_class.py`, `callbacks.py`, `on_policy_algorithm.py`, `utils.py`,
  `ppo/ppo.py`. **`common/buffers.py` is untouched.**
- **The fork's PPO/rollout-buffer path is algorithmically identical to upstream
  v2.0.0.** Every change is instrumentation or logging:
  `ppo.py:182` `start_time = time.time_ns()`; `ppo.py:284-305`
  `time/train_time`, `time/batches_per_sec`, `time/train_fps`,
  `train/batch_size`, plus a `logger.dump()` inside `train()`;
  `on_policy_algorithm.py:150-151,225-232` rollout/callback timers and
  `time/fps` → `time/rollout_fps`; `utils.py:208` adds a `csv` log format;
  one commented-out per-step timing probe. **No optimization, no masking, no
  buffer change.** There is nothing in this fork to inherit that upstream
  does not already have.
- Staleness relative to current upstream: the local repo carries tags up to
  `v2.9.0`, so the fork is ~9 minor versions behind. I did not diff v2.0.0
  against v2.9.0 — I cannot tell you from this code what landed since, and I
  am not going to guess. What I *can* say is that nothing in the v2.0.0
  `train()` loop is the kind of code that later releases rewrote for speed:
  it is the same 40-line loop CleanRL ships.
- **`sb3-contrib` (MaskablePPO) is NOT cloned anywhere** under
  `/Users/nickgreenquist/Documents/Projects/` (checked by `find -iname
  '*contrib*'` and by listing the directory). SB3 is also **not installed** in
  the `pokemon-showdown-rl` conda env (`site-packages` has `torch 2.13.0` and
  no `stable_baselines3`).

## The recipe the numbers are about

`configs/gen4_wang50m.yaml`: `num_envs 8` × `rollout_steps 2496` = 19,968
seat-1 rows, plus `harvest_both_seats: true` ≈ 19,968 seat-2 rows → batch
≈ **39,936**; `minibatches 39` → mbs **1,024**; `epochs 7` → **273 grad steps
per update**; `torch_threads: 1` (applied at `rl/train.py:379`);
`value_clip_eps 0.0184` (so the value-clip branch is live);
`trunk: entity_deepsets`; **`obs_dim` = 1,448**, `priv_dim` = 703 (unused —
`privileged_dim` is 0 on this recipe), 10 actions. Gen 4 runs the **sync**
path: `rl/train.py:668-675` refuses `collector.mode: async` for
`ShowdownGen4-v0`, so `agent.update()` (`rl/agents/ppo.py:966`) is the entry,
not `update_episodes()`.

Width provenance, stated because revision 1 got it wrong:
`grep obs_dim runs/gen4_wang50m_s200/meta.yaml` → `obs_dim: 1448` under
`layout: v0.1`, and `configs/gen4_wang50m.prereg.yaml:57-58` freezes
`obs_dim 1448` / `priv_dim 703`. Revision 1 cited **612**, and attributed it to
that same file, which was wrong on both counts: 612 is the value in
**`runs/gen4_smoke_heur_s1/meta.yaml:16`** — a different run. The mechanism was
a shell mistake, not a misread: I ran `for d in $(ls -d runs/gen4* | head -1)`,
and alphabetical order puts `gen4_smoke_heur_s1` ahead of `gen4_wang50m_s200`,
so `head -1` selected the SMOKE run. (`configs/gen4_smoke_heur.yaml` is
`ShowdownGen4-v0` and is labelled a SMOKE, not a pre-reg, in CLAUDE.md; its
narrower width is consistent with a bring-up layout, but I did not chase down
which layout produced 612 because nothing in this audit depends on it.)

## Layout dims: now EXACT, and verified against a stamped invariant

Every width below is computed from constants read in `rl/envs/gen4/spec.py`,
then **checked three ways**. This matters because revision 1's per-row
arithmetic rested on inferred widths; revision 2's does not.

Read directly (`rl/envs/gen4/spec.py:97-160`): `n_global_scalars 7`,
`len(weathers) 4`, `n_weather_extras 2`, `len(fields) 2`, `n_field_extras 1`,
`len(side_conditions) 9`, `n_slot_extras 1`, `n_mon_leading 3`,
`n_base_stats 6`, `n_matchup 2`, `n_matchup_ability 2`, `n_item_state 3`,
`n_item_classes 5`, `n_item_extras 1`, `n_ability_state 2`,
`n_ability_classes 12`, `n_mon_extras 1`, `len(composite_volatiles) 2`,
`n_counters 6`, `n_active_extras 3`, `n_move_scalars 9`, `effect_dim 45`,
`n_id_species 12`, `n_id_moves 8`, `n_id_items 12`, `n_id_abilities 12`;
`len(GEN4_TYPES) = 17` (listed explicitly at `:41-49`);
`len(GEN4_VOLATILES) = 13` (counted from the tuple at `:51-70`).

| dim | value | status |
|---|---|---|
| `global_dim` | **36** | exact from read constants |
| `mon_dim` | **61** | exact (see note on `n_statuses`) |
| `active_dim` | **31** | exact (see note on `n_boosts`) |
| `move_dim` | **71** | exact: 9 + 17 + 45, no unknowns |
| `id_dim` | **44** | exact: 12 + 8 + 12 + 12 |
| `mon_token_dim` | **93** | exact: 1 + 61 + 31 |

Two values live on `EncoderSpec` rather than in this file and I did **not** read
them: `n_statuses` and `n_boosts`. `n_boosts = 7` is asserted by the spec's own
comment (`boost_keys=GEN1.boost_keys,  # the same seven keys`); `n_statuses = 6`
then falls out of the arithmetic. Three independent checks close **exactly** on
those values, which is why I am calling the table exact rather than inferred:

1. `obs_dim`: 36 + 6(61) + 31 + 4(71) + 6(62) + 31 + 4(71) + 44 = **1,448** ✓
   (matches `meta.yaml` and the pre-reg freeze)
2. `priv_dim`: 6(61) + 31 + 4(71) + 22 = **703** ✓ (matches the pre-reg freeze)
3. **Parameter counts.** Those widths are exactly what the trunk's first Linear
   layers consume, so the parameter total is a sharp test of them. Derived from
   the table: **actor 674,763**, **critic 543,553**. Stamped in
   `runs/gen4_wang50m_s200/meta.yaml:19-21`: `actor: 674763`, `critic: 543553`.
   **Unit-exact agreement on both nets.** Nothing about a wrong width survives
   that test.

Derived layer inputs (all exact): `mon_net` in = 93 + 3×64 = **285**;
`move_net` in = 71 + 64 = **135**; `field_net` in = **36**; `ctx_in` =
5 × 128 = **640**; scorer in = 384 + 128 = **512**.

## Finding 1 (the decision) — `target_kl`: real mechanism, zero value here

*Width-independent: `approx_kl` is dimensionless. Unchanged from revision 1.*

- **SB3:** `stable_baselines3/ppo/ppo.py:261-270` computes
  `approx_kl_div = mean((exp(log_ratio) - 1) - log_ratio)` per minibatch and at
  `:266` sets `continue_training = False` + `break`s the minibatch loop when
  `approx_kl_div > 1.5 * self.target_kl`; `:280-281` then breaks the epoch loop.
  Note the break is placed **before** `zero_grad/backward/step` (`:272-277`), so
  the triggering minibatch's gradient work is also skipped.
- **Ours:** we compute the identical estimator —
  `rl/agents/ppo.py:151` `approx_kl = ((ratio - 1.0) - logratio).mean()` — and
  only log it (`ppo.py:1430`). No early stop exists.
- **Mechanism:** skips whole epochs of forward+backward+step. Upper bound 6/7 =
  86% of the epoch loop, which is ~96% of the update.
- **Portable without migrating:** yes, ~8 lines. It is a `break` on a number we
  already have.
- **But it buys nothing on this recipe.** Measured from
  `runs/gen4_wang50m_s200/history_merged.csv` (column 19, `loss/approx_kl`,
  n=1,761): min 0.000446, p10 0.000522, **p50 0.000855**, p90 0.00190,
  p99 0.00218, **max 0.00228**. `loss/clip_frac` p50 = 0.065, max 0.175 — the
  policy barely moves inside an update. SB3's own default is `target_kl=None`;
  the values people set are 0.01–0.03. **Nothing in that range fires.**
  - *Caveat, stated rather than hidden:* our logged `loss/approx_kl` is the
    **mean over all 273 minibatches** of the update (`ppo.py:1449` divides by
    `grad_steps`), while SB3 tests the **per-minibatch** value. Epoch-1
    minibatches sit near 0 by construction (ratio ≡ 1), so the last epoch's
    minibatches are higher than the mean — plausibly 2–3×. Even at 3× the
    all-time max that is 0.0068, still under 1.5 × 0.01. To resolve it exactly
    you would have to log per-minibatch max, which nothing does today.
  - Wang's own recipe (which this config reproduces) evidently did not set
    `target_kl` either, or his SB3 runs would show truncated epochs.

## Finding 2 — three places we are already **better** than SB3

These matter because they are the items the question anticipated finding in
SB3's favour. They are the other way round.

1. **Buffer → tensor conversion happens once, not per minibatch.**
   SB3: `common/buffers.py:480-493` `_get_samples` fancy-indexes six *numpy*
   arrays and passes each through `to_torch` (`buffers.py:124-136`), which is
   `th.tensor(array, device=...)` — `copy=True` by default, i.e. **a fresh
   numpy→torch copy of the observation minibatch on every one of the 273 steps**.
   Ours: `rl/agents/ppo.py:1012-1017` converts the whole buffer once with
   `torch.as_tensor(..., dtype=torch.float32)` (zero-copy — `buf.obs` is already
   float32, `rl/buffers/rollout.py:40`), then indexes the torch tensor.
   At 39,936 × 1,448 float32 the buffer is **231 MB**
   (39,936 × 1,448 × 4 = 231,309,312 B), which SB3 would re-materialize in
   1,024-row slices 273 times per update. We do not.
2. **Vectorized GAE, and better than SB3's on the episode path.**
   SB3: `buffers.py:398-407`, a Python loop of `buffer_size` iterations (2,496
   here) of `n_envs`-wide numpy ops. Ours (`rl/buffers/rollout.py:157-160`) is
   the same shape for the sync path — a wash — but the async/episode path
   (`rl/buffers/episode.py:139-194`) already carries the F-10 fix: a
   `(Lmax, E)` right-aligned padded layout so the loop runs `Lmax` (hundreds)
   times of `E`-wide ops instead of B (~30k) times of 1-element ops, pinned
   bit-identical to the reference reduction. SB3 has no equivalent.
3. **`explained_variance` allocates nothing.**
   SB3: `common/utils.py:63-65` does `np.var(y_true - y_pred)` — a full-batch
   temporary every update. Ours (`ppo.py:1231-1240`) exploits
   `flat_targets = advantages + values`, so the residual **is** `flat_advantages`
   and no second pass or temporary exists. Also guards the degenerate case to
   0.0 instead of SB3's `np.nan` (which would poison a logger history).

Two more that are a wash, listed so they are not re-raised:
`optimizer.zero_grad()` (`ppo.py:1371`) — torch 2.13's default **is**
`set_to_none=True` (`torch/optim/optimizer.py:1024`), so we already get it and
so does SB3; and per-minibatch schedule recomputation — neither of us does it
(SB3 evaluates `clip_range` once per `train()` at `ppo.py:188`; our `clip_eps`
is a constant and the LR anneal is written once per `_optimize` at
`ppo.py:1266-1284`).

## Findings 3–7 — inefficiencies in **our** update path (SB3 has no cure either)

**Ranked by expected saving.** All are portable without migrating; four of the
five are bit-identical. *Revision 2 reordered this list — see the correction
record. Percentages are shares of the 3,131.7 GMAC-per-update denominator
derived in the magnitude section.*

### 3 (was 5). `old_logp` is recomputed with a full actor forward — **1.59%**
- `ppo.py:1054`: `old_logp = self._logp_entropy(flat_obs, flat_actions,
  flat_masks)[0]` under `no_grad` — a forward of the actor (2,496,512 MAC/row)
  over all 19,968 seat-1 rows = **49.85 GMAC**, to reproduce a number collection
  already computed. The docstring at `:1046-1051` defends *correctness* (exact,
  ratio ≡ 1), not cost.
- SB3 stores `log_prob` at collection time (`buffers.py:448`) and never
  recomputes. The harvest path here already records it at act time
  (`rl/selfplay/harvest.py:25-27`), and `PPOAgent.act_logp` (`ppo.py:810`)
  already exists — so the machinery is present; only `_vector_loop` still calls
  the plain `act()`.
- **Bit-identical for seat 1** (the learner is the actor, and with
  `push_every_updates: 1` nothing intervenes). Needs the collector change plus
  a bit-identity test; the docstring's argument survives, because storing gives
  the same number the recompute produces.
- **Already implemented on the async path** (`update_episodes`, `ppo.py:1130-1133`)
  — so this finding is scoped to the sync path: gen 4, and gen 1's 50M runs.

### 4 (was 3). The critic computes `move_net` and throws it away — **1.46%**
- `rl/networks/entity_deepsets.py:517-521` runs
  `own_moves = self.move_net(cat([tok["moves"][:, :4], move_emb(...)]))`
  **unconditionally**. `own_moves` is consumed only at `:543`, inside the
  branch the critic never reaches — `:535-538` is
  `if not self.is_policy: return self.head(ctx)`.
- Cost, exact: 4 tokens × (135×128 + 128×128) = 4 × 33,664 = **134,656 MAC/row**
  on a critic forward of **1,183,616 MAC/row** — **11.4% of every critic
  forward.** The critic forwards 339,456 rows per update (279,552 in the epoch
  loop + 3 preamble passes × 19,968), so the waste is 339,456 × 134,656 =
  **45.71 GMAC**.
- Forward only: autograd never traverses it, so no backward is wasted, but the
  graph nodes and the embedding gather + `cat` allocations are.
- Also: `EntityTokenizer.forward` builds `tok["moves"]` as a `(B, 8, 71)`
  concat (`entity_deepsets.py:226`) of which slots 4:8 are consumed by **nothing**
  in the trunk (the module docstring at `:41-44` says so; `_aux_features` at
  `:485-489` is the only reader and runs only under `return_features=True`,
  i.e. only when the D25 aux lever is on — it is off in gen 4). So both nets pay
  a half-wasted concat per forward.
- Fix: gate the `move_net` call on `self.is_policy` (keep the parameters — they
  are in every checkpoint and in `self.critic_params`; they simply keep receiving
  no gradient, which is already true today). **Bit-identical to the loss.**

### 5 (was 4). `flat_critic_obs` is duplicated, then gathered twice per minibatch — **0.5–1.7%**
- `ppo.py:1044`: with `privileged_dim == 0` (gen 4's case),
  `flat_critic_obs, flat_critic_next_obs = flat_obs, flat_next_obs` — a correct
  alias, explicitly documented as "no copy".
- `ppo.py:1099-1100` then destroys the alias:
  `flat_obs = torch.cat([flat_obs, h_obs])` **and**
  `flat_critic_obs = torch.cat([flat_critic_obs, h_obs])` — two independent
  concatenations with identical contents. **231 MB** of duplicate allocation +
  copy per update (39,936 × 1,448 × 4).
- `ppo.py:1329` gathers `flat_obs[idx]`; `ppo.py:1335` gathers
  `flat_critic_obs[idx]` — the **same rows of the same values**, 273 times per
  update. Each gather is 1,024 × 1,448 × 4 B = **5.93 MB**, so
  273 × 5.93 = **1.62 GB** of redundant gather traffic per update.
- Total redundant memory traffic ≈ (1.62 GB read + 1.62 GB written) +
  (0.23 GB read + 0.23 GB written) ≈ **3.70 GB per update**. At 8–25 GB/s
  effective single-thread bandwidth that is 0.15–0.46 s of 27.7 s =
  **0.5–1.7%**. Rows are 5,792 contiguous bytes each, so the gather streams
  rather than random-accesses — the high end of that band is the likelier one,
  but **the bandwidth is assumed, not measured**, which is why this sits below
  finding 4 despite a higher upper bound.
- Fix: `flat_critic_obs = flat_obs` after the harvest concat when
  `privileged_dim == 0`, and reuse the single gathered tensor. **Bit-identical.**
- SB3 does not have this shape: `_get_samples` gathers observations once.

### 6. The second critic pass for `next_values` is avoidable — **0.75%**
- `ppo.py:1052-1053` runs the critic twice over 19,968 rows each: once on
  `flat_critic_obs`, once on `flat_critic_next_obs`. The second is
  19,968 × 1,183,616 = **23.63 GMAC**.
- With autoreset disabled and per-row `next_obs`
  (`rl/buffers/rollout.py:8-14`), for a non-terminal row `next_obs[t]` **is**
  `obs[t+1]` of the same env, so `next_values[t] = values[t+1]`; at a terminal
  row `compute_gae` multiplies `next_values` by `(1 - terminated) = 0`
  (`rollout.py:158`) and discards it. So a shift of `values` plus one forward
  over the last row's N=8 rows replaces a forward over 19,968.
- This is structurally what SB3 gets for free from its (T,N) layout, and what
  our own async path already gets (`episode.py:14-19`).
- Bit-identical for Showdown (`ShowdownEnv.step` forces every decided finish
  terminal; truncations never surface), but the generic path needs a truncation
  guard, so it is a small correctness surface for a small win. Lowest priority
  of the four bit-identical items.

### 7. Adam runs the **single-tensor Python loop** on CPU — unbounded
- `ppo.py:648`: `torch.optim.Adam(groups, eps=1e-5)` — no `foreach`, no `fused`.
- In torch 2.13, `adam.py:937-945` calls `_default_to_fused_or_foreach(...,
  use_fused=False)`, so **fused is never auto-selected**, and
  `torch/utils/_foreach_utils.py:8-10`
  `_get_foreach_kernels_supported_devices() == ["cuda", "xpu", "mtia",
  privateuse1]` — **"cpu" is absent**, so `foreach` is not auto-selected either.
  On CPU we therefore get the per-parameter Python loop.
  `_get_fused_kernels_supported_devices()` (`_foreach_utils.py:13-24`) **does**
  include `"cpu"`, so `fused=True` is a legal explicit override; `foreach=True`
  is too (`_device_has_foreach_support`, `_foreach_utils.py:50-54`, adds "cpu").
- Scale: **59 parameter tensors** (actor 31, critic 28) × 273 steps ≈ **16,100
  per-tensor Adam invocations per update**, over **1,218,316 parameters**
  (674,763 + 543,553, stamped) × ~10 element-wise passes ≈ **3.3 G element-ops
  per update**.
- SB3 has the identical gap: `common/policies.py:71,439` default
  `optimizer_class = th.optim.Adam` with no `foreach`/`fused`.
- **NOT bit-identical** (different fma/reduction order), so it needs a pre-reg
  or a fresh-run boundary. I **cannot size this without measurement** — see
  the magnitude section.

### Micro, listed for completeness, not worth a commit on its own
- `_logp_entropy` (`ppo.py:850-855`) computes `masked_logits` **twice** —
  once inside `Categorical(logits=masked_logits(...))` and again inside
  `masked_entropy(logits, masks)` → `rl/common/masking.py:43`. Each call does a
  `torch.full_like` alloc + `torch.where` + a normalization over (1024, 10), and
  `masking.py:35`'s `assert bool(mask.any(dim=-1).all())` runs twice per
  minibatch (a reduction plus a host readback). Deriving `log_prob` and entropy
  from one `log_softmax` removes half of it. Tensors are 10-wide (action count,
  not obs width — unaffected by the correction); the saving is kernel-launch
  count, not FLOPs. SB3 shares one distribution object
  (`policies.py:699-702`) and does not pay this — but it is <0.5% here.
- Seven `float(x.item())` per grad step (`ppo.py:1427-1433`) plus
  `grad_norm.item()` twice ≈ 1,900 scalar readbacks per update. On CPU these are
  direct reads, ~ms total. Non-issue.
- `nn.utils.clip_grad_norm_` (`ppo.py:1396`) **already** uses foreach on CPU
  (`_has_foreach_support` includes "cpu"). Nothing to do.

## The item that dwarfs all of the above (and is not an SB3 question)

**Actor and critic are two independent full DeepSets encoders.** `ppo.py:513-515`
builds `self.actor = build(n_actions)` and `self.critic = build(1)` as separate
`EntityDeepSetsNet`s. The entity-encoding stage they duplicate —
`species_emb`/`move_emb`/`item_emb`/`ability_emb` + `mon_net` + `move_net` +
`field_net` — is **790,016 of the critic's 1,183,616 MAC/row (66.7%)**. Sharing
it removes, per row, `(mon_net + field_net) × 3` (fwd+bwd) plus `move_net`'s
wasted forward = 1,966,080 + 134,656 = **2,100,736 of 10,771,072 MAC/row**, i.e.
**19.5% of the epoch loop**; adding the preamble critic passes, **≈20% of
`update_sec`**. That is ~4× everything in findings 3–6 combined.

It is not free: `rl/networks/entity_deepsets.py:44-47` records the separate-stack
choice as a deliberate deviation from Hu & Liu (who share), the module docstring
premises the `value_coef` note on it (`ppo.py:486-487`), it invalidates every
checkpoint, and it changes every number — so it needs a pre-reg, not a
refactor. SB3's `share_features_extractor` (`policies.py:693-698`) is exactly
this pattern, which is the only sense in which SB3 is "ahead" here: it makes the
sharing cheap to express. It does not make the decision for us, and adopting the
decision does not require adopting SB3.

## What we would LOSE by migrating

*Width-independent; unchanged from revision 1.*

1. **Action masking — the whole harness contract.** SB3's PPO has none:
   `ppo.py:212` calls `policy.evaluate_actions(obs, actions)` with no mask
   parameter anywhere in the path. Masking needs `sb3-contrib`'s `MaskablePPO`,
   which **is not cloned here** and is not installed — a new pinned dependency.
   Our contract (`rl/common/masking.py:8-22`) is specific and load-bearing:
   finite `-1e8` sentinel (never `-inf`, because `Categorical.entropy()`'s
   `0 * -inf = NaN` flows silently into the loss), a `where`-guarded
   `masked_entropy` so illegal positions contribute an exact 0, the value head
   never masked, masking applied at eval too, no `mask is None` branches
   anywhere in algorithm code, and `masked_logits` provably bitwise-inert under
   an all-True mask. I **cannot verify** which of these sb3-contrib's
   `MaskableCategoricalDistribution` satisfies, because the package is not on
   this machine — that verification would have to happen before, not after, a
   migration decision.
2. **The both-seat harvest.** `rl/selfplay/harvest.py` (130 lines) +
   `ppo.py:1077-1111`: seat-2 rows carry the **pool member's own** log-prob
   recorded at act time and a `version` id, so the importance ratio corrects the
   member's lag and `harvest/version_lag_max` measures it. SB3's `RolloutBuffer`
   is a fixed `(buffer_size, n_envs)` array whose `get()` asserts `self.full`
   (`buffers.py:454`); a **variable-size union** of lockstep seat-1 rows plus a
   variable number of seat-2 episode rows does not fit it. You would subclass
   `RolloutBuffer` and override `get`, `_get_samples` and
   `compute_returns_and_advantage` — i.e. rewrite the exact three functions the
   migration was supposed to inherit.
3. **Per-episode GAE.** `rl/buffers/episode.py:139-194`, bit-identity-pinned
   against `_episode_gae_reference` with `np.array_equal` **and** a bitwise view.
   SB3's `compute_returns_and_advantage` is (T,N)-only. Gen 1's async path is
   built on this, and the Rust port is expected to make the async shape the
   normal one.
4. **The league pool.** `rl/selfplay/pool.py` (308 lines) + `opponents.py` (136)
   + `push_every_updates` / `latest_prob` / `pool_size`. SB3 has no self-play
   concept; this lives in our loop, so the code survives, but it has to be
   re-plumbed against SB3's `learn()` + callback control flow instead of the
   loop we own. Memory says league play stays on, so this is not optional.
5. **Resume / `meta.yaml` / history convention.** `--resume RUN_DIR`,
   `from_step` read out of `meta.yaml` (`runs/gen4_wang50m_s200/meta.yaml`
   already carries a `resumes:` list with `from_step: 5750784`), the
   "`updates_done` one short per resume" and "`checkpoint.pt` lags the last
   logged step" landmines, `scripts/extract_history.py`, `merge_history.py`,
   `runs/*/history*.csv`. SB3's `save`/`load` is a zip with
   `reset_num_timesteps`; every one of these tools reads *our* format, and the
   run-loss tolerance rule (never lose 24 h to one error) rides on it.
6. **The locked metric names — zero overlap.** Ours (CLAUDE.md, binding):
   `rollout/episode_return`, `rollout/episode_length`, `eval/return_mean`,
   `eval/return_std`, `eval/win_rate`, `time/steps_per_sec`,
   `time/collect_sec`, `time/update_sec`, `time/eval_sec`, `loss/*`,
   `selfplay/*`, `harvest/*`. SB3 logs `train/entropy_loss`,
   `train/policy_gradient_loss`, `train/value_loss`, `train/approx_kl`,
   `train/clip_fraction`, `train/explained_variance`, `rollout/ep_rew_mean`,
   `rollout/ep_len_mean`, `time/fps` (this fork renames it `time/rollout_fps`,
   `on_policy_algorithm.py:285`). **Not one name matches.** Every pre-reg
   header, every gate, every readout and `RESULTS.md` cross-reference reads the
   ours-side names, so a migration ships a rename shim on day one and lives with
   it forever.
7. **Diagnostics and levers that exist only in ours and are pre-reg inputs.**
   `loss/grad_clip_frac` and `loss/grad_norm` (the "rare safety net vs permanent
   lr divisor" read, `ppo.py:1389-1396`), `loss/adv_std` (`:1245` — the only
   place a shaping term's effect on advantage magnitude is visible),
   `loss/minibatch_rows_min|dropped` (F-04, `:1440-1445`), the entire
   `aux/*` apparatus (`_aux_gradient` at `:857-914` with its decoupled clip and
   the delivered-trunk-norm arithmetic that D25/D25-P/D28 depend on),
   `l2_init_metrics`, `loss/bc_kl`, the staged unfreeze
   (`critic_warmup_updates` / `actor_lr_scale`, `:1247-1256`), `minibatch_tail`
   (`:221-279`), and Wang's `power` LR schedule (`:1266-1284`). SB3's
   `get_schedule_fn` (`utils.py:80-95`) accepts a callable so the schedule is
   implementable — but it is ours to write either way, and every item above is
   a hook into a *hand-written* loop.
8. **The audit trail itself.** Five separate audits are encoded in `ppo.py` as
   asserts and loud seams: the privileged/opp_choice mismatch seams
   (`:981-998`), the 1-row-minibatch NaN caught live by smoke3 (`:1302-1319`),
   the `retain_graph` decision that avoids a +25% second actor forward
   (`:1372-1376`), the aux-clip ordering that keeps `loss/grad_norm` numerically
   identical to every control curve, the third-param-group ordering that
   prevents silent Adam-moment corruption on resume (`:620-634`). None of that
   transfers, and every one of them cost a session to find.
9. **One point *for* migrating, for honesty.** `JOURNEY.md:60-62` discloses that
   Wang ran SB3 with its defaults, so "any residual gap partly measures SB3's
   implementation against ours." Migrating would delete that confound from step
   5. It would also break comparability with every gen-1 result, and step 5 is a
   reproduction check that credits nothing — so the confound is cheaper to
   disclose than to eliminate.

## Magnitude estimate

### Per-row arithmetic — **all exact** (see the verification above)

`_subnet(in, w)` = `Linear(in,w) → ReLU → Linear(w,w) → LayerNorm(w)`, so
MACs = `in*w + w*w`. `entity_dim` 128, `embed_dim` 64, `ctx_sizes [384,384]`,
`value_sizes [384,384]`, `scorer_sizes [256]`, 10 actions. Embedding lookups are
gathers, not MACs, and are excluded on both sides.

| stage | actor | critic |
|---|---|---|
| `mon_net`, 12 tokens: 12 × (285·128 + 128·128) | 634,368 | 634,368 |
| `move_net`, 4 own-move tokens: 4 × (135·128 + 128·128) | 134,656 | 134,656 **(dead)** |
| `field_net`, 1 token: 36·128 + 128·128 | 20,992 | 20,992 |
| `ctx_net`: 640·384 + 384·384 | 393,216 | 393,216 |
| head — scorer 10 × (512·256 + 256) / `Linear(384,1)` | 1,313,280 | 384 |
| **per-row forward** | **2,496,512** | **1,183,616** |

Per row through the epoch loop (backward ≈ 2× forward; the critic's dead
`move_net` gets no backward, so 1× not 3× on that term):
actor 7,489,536 + critic (3,550,848 − 269,312) = **10,771,072 MAC/row**.

| block | rows | GMAC |
|---|---|---|
| epoch loop (7 × 39,936) | 279,552 | **3,011.0** |
| preamble `values` (critic) | 19,968 | 23.6 |
| preamble `next_values` (critic) | 19,968 | 23.6 |
| preamble `old_logp` (actor) | 19,968 | 49.9 |
| preamble harvest `values` (critic) | 19,968 | 23.6 |
| **total per update** | | **3,131.7 GMAC ≈ 6.26 TFLOP** |

The preamble is **3.9%** of the update; the epoch loop is **96.1%**. This is why
every large win has to come out of the 273 grad steps, not the setup.

### Implied throughput, and why it decides finding 7

6.263 TFLOP / 27.7 s = **≈226 GFLOP/s on one torch thread**. That is high but
not impossible here: `libtorch_cpu.dylib` links
`/System/Library/Frameworks/Accelerate.framework` (checked with `otool -L`), and
every hot shape is a clean sgemm (the scorer is (10,240 × 512) × (512 × 256)),
so Apple's AMX-backed BLAS can plausibly deliver it. **If that reading is right,
the update is already BLAS-bound and there is essentially no dispatch/Python fat
to cut — the only wins are the ones that do less arithmetic, and finding 7 is
worth close to nothing.** If instead the real efficiency is 2–3× lower (i.e. the
measured 27.7 s contains substantial non-BLAS time my MAC count cannot see),
finding 7 is worth more than the band below.

The MAC count itself is now exact, so the *only* remaining uncertainty in this
figure is the backward ≈ 2× forward convention and whatever non-GEMM work
(LayerNorm, ReLU, gathers, autograd bookkeeping) the count omits — both of which
push the true efficiency **down**, i.e. 226 GFLOP/s is an upper bound on the
BLAS-bound reading. **I have not measured it and will not guess further.**

### Bounded, bit-identical, portable-without-migrating

| finding | mechanism | saving |
|---|---|---|
| 3 | store `old_logp` instead of recomputing (49.9 GMAC) | **1.59%** |
| 4 | dead `move_net` in the critic (45.7 GMAC) | **1.46%** |
| 5 | duplicate critic-obs copy + double gather (3.70 GB traffic) | **0.5–1.7%** |
| 6 | shift `values` instead of a second critic pass (23.6 GMAC) | **0.75%** |
| micro | single `masked_logits` / one `log_softmax` | <0.5% |
| **total** | | **≈4.3–6.0% of `update_sec`** |

That is **1.2–1.7 s of gen 4's 27.7 s** per update. Post-Rust-port, with the
update at (say) 60–80% of wall time, it is **≈3–5% of total training wall
clock**. Real, cheap, worth doing on their own merits — and **not a reason to
migrate anything**, since SB3 fixes none of them.

**Gen-1 scoping (corrected in revision 2).** I did *not* re-derive gen-1's
per-row MACs, and the earlier "≈0.5–0.7 s of gen 1's 13.0 s" is withdrawn as
unsupported. Two things are worth knowing instead:
- Gen-1 `obs_dim` is **828** (`runs/showdown_sp_100m_s120/meta.yaml:10`,
  encoder v2 + ids), so finding 5's byte figures scale by 828/1448 = 0.57.
- The gen-1 **100M** runs are `collector.mode: async`
  (`configs/showdown_sp_100m.yaml:543-544`), i.e. `update_episodes`
  (`ppo.py:1123-1190`), which **already** records `old_logp` at act time and
  **already** uses one critic pass. **Findings 3 and 6 do not apply there** —
  only 4, 5 and the micro do. The gen-1 **50M** runs are sync
  (`showdown_sp_batch50m.yaml`; the async variant is a separate file whose
  header calls the collector block "THE ONLY DELTA"), so all four apply there.
  Anyone quoting a gen-1 number from this audit must say which path they mean.

### Not bounded
- **Finding 7 (fused/foreach Adam):** the element-op count (3.3 G/update over
  1,218,316 stamped parameters) is exact, but converting it to seconds requires
  knowing whether the update is BLAS-bound. **Needs measurement.** Also not
  bit-identical.
- **Finding 1 (`target_kl`):** bounded at **~0%** on the current recipe by our
  own history, as measured above. Not "unknown" — measured, and zero.
- **Shared actor/critic trunk:** ≈20% of `update_sec`, but it is an
  architecture change requiring a pre-reg and invalidating every checkpoint, so
  it does not belong in the same table.

## Cheapest future measurement (when the box is free)

`scripts/ch5_mps_update_bench.py` already exists and already does exactly this:
it replays a fixed tape of real-shaped transitions through `agent.update()`
one env step at a time, so the number is commensurable with the logged
`time/update_sec` — and its docstring records that the `cpu` arm **was validated
against the real logged `time/update_sec`** of a matching training run. Point it
at the gen-4 config with a single arm:

    python scripts/ch5_mps_update_bench.py --config <gen4 bench cfg> --arms cpu1 --repeats 3

Cost: one live env for obs collection plus a few minutes of one core. Wrap
`torch.profiler.profile(activities=[CPU], record_shapes=True)` around one update
inside it and the same run answers all three open questions at once:
(a) is the update BLAS-bound at ~226 GFLOP/s — which decides whether finding 7
is worth anything; (b) the true actor/critic/backward/optimizer/gather split —
which turns findings 3–6 from arithmetic into measurements; (c) the
per-minibatch `approx_kl` max, which closes the one caveat on finding 1.
No new script, no new dependency, and nothing that has to touch a training run.

---

## Correction record (revision 1 → revision 2)

**The error.** Revision 1 used `obs_dim = 612` and attributed it to
`runs/gen4_wang50m_s200/meta.yaml`. The correct width is **1,448**
(`meta.yaml:15`; frozen in `configs/gen4_wang50m.prereg.yaml:57-58` alongside
`priv_dim 703`). 612 is `runs/gen4_smoke_heur_s1/meta.yaml:16` — a **different
run**, selected by a shell mistake: `ls -d runs/gen4* | head -1` sorts
alphabetically and returns the smoke run, not `s200`.

**Does the verdict change?** **No.** Finding 1 — the whole basis of the
NEITHER verdict — is a comparison of dimensionless KL values against a
dimensionless threshold and is untouched by observation width. So is every item
in "what we would lose". The verdict was never width-sensitive.

**Does any rank change?** **Yes, one swap, and it is worth reading.** Revision 1
listed the bit-identical wins as 3-4-5-6 = (dead `move_net`, duplicate gather,
store `old_logp`, drop `next_values`); revision 2 lists them as
(store `old_logp` 1.59%, dead `move_net` 1.46%, duplicate gather 0.5–1.7%,
drop `next_values` 0.75%). Two causes, only one of them the width bug:
- Revision 1's ordering was already wrong on its own numbers — it labelled the
  list "ranked by expected saving" while placing the 1.6% item third. That was
  my error, independent of the width.
- The dead-`move_net` figure genuinely grew, 1.0% → 1.46%, for two reasons: the
  correct `move_dim` (71, not the ~20 I had inferred) raises `move_net`'s share
  of a critic forward from ~9.9% to **11.4%**, and revision 1 counted only the
  epoch loop where the critic also forwards 59,904 preamble rows.
`flat_critic_obs` (finding 5) also grew — 0.5–1.0% → 0.5–1.7% — because its
memory traffic scales linearly with width (2.37×). Its band now overlaps
findings 3 and 4; I have kept it third because its saving rests on an **assumed
memory bandwidth** while 3 and 4 are arithmetic.

**Every number that moved.**

| quantity | rev 1 (obs 612) | rev 2 (obs 1,448) |
|---|---|---|
| `obs_dim` | 612 (wrong run) | **1,448** |
| `mon_dim` / `active_dim` / `move_dim` / `global_dim` | ~26 / ~28 / ~20 / 36 (inferred) | **61 / 31 / 71 / 36** (exact) |
| `mon_net` in / `move_net` in | ~222 / ~84 | **285 / 135** |
| actor MAC/row | ~2.41M | **2,496,512** |
| critic MAC/row | ~1.10M | **1,183,616** |
| dead `move_net` share of critic fwd | ~8–10% | **11.4%** |
| epoch-loop GMAC/update | 2,876 | **3,011.0** |
| preamble GMAC/update | 111 | **120.8** |
| total GMAC/update (denominator) | 2,987 / 2,943 (inconsistent) | **3,131.7** |
| TFLOP/update | 5.97 | **6.26** |
| implied single-thread throughput | ~215 GFLOP/s | **~226 GFLOP/s** |
| buffer size (finding 2.1) | ~98 MB | **231 MB** |
| duplicate concat (finding 5) | ~98 MB | **231 MB** |
| per-minibatch gather (finding 5) | 2.5 MB | **5.93 MB** |
| redundant gather traffic/update | ~685 MB | **1.62 GB** |
| finding "store `old_logp`" | 1.6% | **1.59%** |
| finding "dead `move_net`" | ~1.0% | **1.46%** |
| finding "duplicate gather" | 0.5–1.0% | **0.5–1.7%** |
| finding "drop `next_values`" | 0.7% | **0.75%** |
| combined bit-identical | ≈4–5% | **≈4.3–6.0%** |
| shared-trunk share | ≈20% | **≈20%** (19.5% of the epoch loop) |
| duplicated encoder stage | ~705k of ~1.10M | **790,016 of 1,183,616 (66.7%)** |
| total parameters | ~1.2M (estimated) | **1,218,316** (stamped, and independently re-derived to the unit) |
| gen-1 saving | "0.5–0.7 s of 13.0 s" | **withdrawn**; replaced by the async-scoping note |

**Numbers that did NOT move, and why.** `loss/approx_kl` and `loss/clip_frac`
statistics (dimensionless); the 273 grad steps / 1,024 mbs / 39,936 batch
(config, not width); `ctx_net` 393,216 and scorer 1,313,280 MAC/row (their input
widths are `5 × entity_dim` and `ctx + entity_dim`, both fixed by
`trunk_kwargs`, not by `obs_dim` — which is why the actor total moved only 3.5%
despite the width more than doubling); the 59 parameter tensors; the scorer's
(10,240 × 512) × (512 × 256) GEMM shape; the micro items (10-wide action
tensors); every entry in "what we would lose"; the SB3 clone's provenance and
diff.

**Exact vs still-inferred, for the citing session.**
- **Exact and independently verified:** all six layout dims, all per-row MAC
  figures, all GMAC totals, all byte figures, the parameter counts, the 273
  grad steps, and the `approx_kl` / `clip_frac` percentiles. The layout dims are
  confirmed by three independent closures — `obs_dim` 1,448, `priv_dim` 703, and
  a unit-exact match to the **stamped** `params: actor 674763 / critic 543553`.
- **Read but not directly verified:** `n_statuses = 6` and `n_boosts = 7` live on
  `EncoderSpec` in `rl/envs/encoder_spec.py`, which I did not open. `n_boosts`
  is asserted by the spec's own comment; `n_statuses` falls out of the
  arithmetic. Both are pinned by the three closures above, so an error in either
  would have to be compensated exactly by an error in the other *and* still
  reproduce two parameter counts — which is why I am willing to call them exact.
- **Still a modelling assumption, not a measurement:** backward ≈ 2× forward;
  non-GEMM work (LayerNorm, ReLU, gathers, autograd bookkeeping) excluded from
  the MAC count; 8–25 GB/s effective single-thread memory bandwidth for
  finding 5; ~10 element-wise passes per Adam step for finding 7. The first two
  bias the 226 GFLOP/s figure **downward** (i.e. it is an upper bound on the
  BLAS-bound reading). **None of the four has been measured, and the report does
  not claim otherwise.**

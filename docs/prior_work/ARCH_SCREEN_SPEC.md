# Architecture screen — implementable spec (entity attention vs MLP, BC-decided)

Provenance: designed 2026-08-07 by a session subagent from the ACTUAL encoder layout
(offsets verified numerically), the ps-ppo LADDER-ERA checkout (`7fb522c` — the system that
scored 2102 Elo, not HEAD), and a working prototype BENCHMARKED on this machine. Supersedes
`CROSS_FEATURES_AND_ARCHITECTURE.md` wherever they disagree (23 discrepancies audited; the
largest: several rung-0 features already shipped in encoder v2; its M5 formula contains the
ps-ppo Target-enum bug; its ps-ppo sizing describes HEAD, which never laddered; its "GPU
barely helps" claim inverts for this trunk). This is the screen DESIGN §11 names as a free
by-product of option (C); it needs no new D-number.

## Design (the part to implement)

- **Tokenization inside the network** — a reshape layer over the existing flat v2 obs (807);
  no encoder change, no OBS_DIM change, no tape re-embed. 21 tokens: 1 field `[0:5]`,
  12 mons (50-d: mon block ⊕ active-extras gated by that mon's own is_active bit; own mons
  prepend a constant 1.0 so both sides share one input projection), 8 move tokens (46-d, own
  4 + opponent's prior-filled 4 — the defensive-switch cross nothing else expresses).
  Additive learned embeddings: side(2) + mon_slot(6) + move_slot(4) + field(1) — REQUIRED
  (attention is permutation-equivariant; the MLP gets slot identity free from its weight
  columns). All slices derived from `rl.envs.showdown` constants, asserted at construction.
- **Trunk**: d_model 128, 2 layers, 4 heads, ff 4.0, pre-LN, GELU; per-type 2-layer input
  subnets with terminal LayerNorm (ps-ppo's `_build_subnet` shape). Matches the ladder-era
  ps-ppo DEPTH (2 layers) at 1/8 width — sized so the actor lands at ~496k params, BELOW the
  MLP's 681k, so the screen is not confounded by capacity.
- **Policy head: pointer.** ctx = mean over tokens; logits_i = shared scorer(concat(token of
  action i, ctx)) + 10-dim slot bias. Switch action i ↔ own-mon token 1+i; move action 6+j ↔
  own-move token 13+j (the exact poke-env alignment the encoder already relies on). Masking
  unchanged, outside the head. Value head: flat pooled (field ⊕ mon-pool ⊕ move-pool), never
  masked, separate stack (repo contract; do NOT share the trunk).
- **Integration**: new `rl/networks/entity_attention.py`; `trunk:/trunk_kwargs:` keys on
  PPOAgent (default "mlp", bit-identical); a `build` branch; INIT HAZARD — do not run
  `_orthogonal_init` over the attention net (it would hit MHA out_proj and skip in_proj);
  use an `init_head(gain)` method with Xavier + std-0.02 embeddings (ps-ppo's recipe) and
  rescale only the final scorer. train_bc gains `--trunk/--d-model/--n-layers/--n-heads/
  --threads`; run-name must differ per trunk. Everything else round-trips untouched
  (eval_checkpoint rebuilds via cfg.agent). Regression test: trunk="mlp" bit-identical params.

## Measured cost (prototype, this machine)

Params: attn actor ~496k vs MLP 681k (0.73×). FLOPs 13.6×; measured train step **34.6×**
(4.9 ms → 170 ms at batch 512, 1 thread); `--threads 8` recovers 2.35× on attention vs 1.45×
on MLP. BC fits: 180k rows ~18 min @1t (~9 @8t); 900k ~90 min (~45). RL projection: update
becomes ~55-60% of the loop (vs MLP's ~5%) → ~205-220 steps/s/lane vs ~570. **Pre-registered
throughput gate: >2.5× RL throughput loss with <+0.02 agreement gain kills the RL adoption
regardless of the screen's primary read.** (This inverts CROSS_FEATURES' hardware note: for
this trunk the UPDATE, not inference/collection, is the bottleneck — a GPU-for-update is the
relevant mitigation, a maintainer decision.)

## Pre-registration sketch (goes into configs/bc_arch_screen.yaml at launch)

Arms at 180k rows, 3 matched fit seeds (0/1/2), everything else fixed (soft targets, split,
epochs-with-early-stop, lr 1e-3, v2 encoder, value-coef 0):
  A control: --trunk mlp --hidden 512 512
  B: --trunk attention --d-model 128 --n-layers 2 --n-heads 4
One pre-declared capacity rung (d_model 192) runs ONLY at 900k and only if B credits or is
ambiguous at 180k. PRIMARY: held-out val_kl AND agreement_free, pooled over seeds, paired —
cluster bootstrap by battle (1,000 resamples), 95% CI. CREDIT: Δagreement_free ≥ +0.02 AND CI
excludes 0 AND Δval_kl ≤ −0.02 (both metrics must move). AMBIGUOUS ⇒ hold for the 900k read
(the data-starved-transformer crossing is pre-stated, not re-arguable). SECONDARY (mechanism):
agree_reveal buckets — a gain concentrated in the 4-6-revealed band is evidence for entity
attention specifically; flat gain = generic capacity. fitted_entropy must not undercut the
teacher's. TERTIARY, not a read: probe vs-SH continuity eval.

Caveat carried from the doc it supersedes: BC agreement rewards only structure the TEACHER
uses; the screen chooses a trunk, it does not predict an RL outcome.

## Free follow-up (excluded from the primary comparison to avoid the 2×2 confound)

STAB and per-bench-mon × opp-move multipliers are zero-parameter dot products computable
inside the reshape layer (mon and move type one-hots share `_TYPE_INDEX`). Pre-declared as
the immediate follow-up arm on whichever trunk wins.

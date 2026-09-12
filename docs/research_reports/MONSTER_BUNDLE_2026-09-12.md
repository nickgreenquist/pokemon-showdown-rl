# MONSTER BUNDLE — what else is worth bundling before the 200M fleet and the ladder

Asked 2026-09-11: *"other items in ideas.md worth doing and verifying before monster train
and ladder … very open to implementing more things and bundling in this monster chapter …
the goal is always how high on the ladder can we go, no human data (in training)."*

**Marks.** `[V]` opened the source this session (file:line, instantiated the net, read the
CSV). `[R]` secondary — a sibling report or a paper I did not open. **CLAUDE.md rule 6
binds:** no 12M/50M A/B null is cited as evidence, kill, or caveat. Sibling reports read and
integrated, not duplicated: `MODEL_SCALE_2026-09-12.md` (arm W) and
`SELFPLAY_RECIPE_2026-09-12.md` (the LR floor). **Nothing here is ratified.**

## TL;DR — 10 lines

1. **Three free config keys are worth more than anything buildable by noon:** the LR-anneal
   floor (recipe report #1), `l2_init_decay: 0.02`, and `gae_lambda: 1.0`. Total build cost:
   one launcher line and two config files.
2. **`gae_lambda: 1.0` is the lever neither sibling report proposed for THIS fleet and I
   think it belongs on three lanes.** It is the only zero-compute intervention aimed at the
   *named cause* of our measured critic collapse, and the recipe report's own GAE citation
   argues for it once you read it in our direction (§A1).
3. **Arm W (`value_sizes: [1024,1024]`) is correct and cheap.** Verified by instantiation:
   critic 494,849 → **1,807,489**, actor untouched at 626,059, `ACTOR_PARAM_CEILING`
   untouched, `OBS_DIM` untouched `[V]`. ~+9 h on three lanes.
4. **RECOMMENDED FLEET: all six lanes L2 + LR floor; three lanes + W, three lanes + λ=1.0.**
   Two critic-directed levers, one per trio, maximum committee diversity, clean attribution,
   ≈53–55 h `[R]`. **It is also the only shape that survives every branch of the capacity-loss
   probe** (`PLASTICITY_PROBE_2026-09-12.md`, written and unrun): two of its four pre-stated
   branches name `gae_lambda: 1.0` as the live lever and width as unlikely to pay; one names
   W. Splitting the trios buys both without waiting on the probe.
5. **Both-seat harvest on the engine route is NOT a night's work** — it needs a second
   per-battle episode buffer in `env.rs`, a batched opponent log-prob, an extension rebuild
   that moves the sha `pkmn_gen1.verify()` pins, and it is double-blocked by the mandatory
   D25 aux head `[V]`. Days, plus a re-gate. NO.
6. **IDEAS §2.2 (the seed-sharing run tag) is BUILT and shipping** — `env_kwargs.seat_tag`
   is it `[V, rl/envs/make.py:36-47]`. IDEAS still lists it NOT STARTED. Arms *can* share
   seeds now; I recommend against it here (diversity is what the committee monetises).
7. **Nothing that touches `OBS_DIM` or the encoder may enter this fleet** — C6 (4.6),
   temporal context, cross-features. They break the 100M finals as committee members, and
   the 100M ENS3 is the floor the whole chapter is graded against.
8. **The best remaining ladder lever costs zero training: weight-space averaging of each
   lane's last few rungs.** In neither sibling report, in no IDEAS row. It is the exact
   antidote to the one risk the LR floor introduces.
9. **The config header's DISK/eval arithmetic is 100M×9-shaped and is now ~2× off** — 400
   rungs/lane not 200, ~800 in-loop evals/lane not 400 `[V]`. Re-do it before launch; it
   still fits (≈72 GB of 146 GB free) but nobody has checked at the ratified shape.
10. **Two rulings are owed tonight, not tomorrow:** the LR floor against JOURNEY 10's
    verbatim `lr_anneal_steps == total_steps` clause, and the arm allocation.

---

## A. THE TABLE — every candidate, blunt

Columns: mechanism · **L** = expected ladder value · build cost by noon · verification before
launch · **R** = unattended-run risk · verdict.

### A1. Free config keys (no code, already wired and tested)

| lever | mechanism | L | build | verify | R | verdict |
|---|---|---|---|---|---|---|
| **LR-anneal floor** `lr_anneal_steps: 240000000` @ `total_steps: 200000000` | linear-to-zero spends the tail at a step size that provably moves nothing — `approx_kl` 8.6e-7 and `clip_frac` **exactly 0** at 99.99M `[R, recipe §1]`; my own read of s112 has `approx_kl` 0.0279 mid-run → 0.0002 last-50 `[V]`. +16.7% lr-integral, all of it late `[V, arithmetic]` | **H** — the single biggest free change on the table; also re-arms L2, whose decay is `−lr·l2_init_decay` so a zero lr switches the plasticity fix off exactly when plasticity is worst `[V, ppo.py:913]` | 1 line: `monster_fleet.sh:85` asserts `CFG_ANNEAL == STEPS`; `rl/train.py:433` already **permits** `>= total_steps` and names that shape legitimate `[V]` | smoke: launcher accepts it; `meta.yaml` records 240M | **L** — no new code path, no new tensor, no divergence mode. Day-2 shape: none. Real cost is a *final* drawn from a still-moving policy — pair with A4's rung averaging | **BUNDLE NOW** (needs a ruling) |
| **`agent.l2_init_decay: 0.02`** | decoupled per-step decay toward θ₀; bounds norm growth, preserves rank | **M** | zero — `_l2.yaml` and `_w.yaml` already carry it | `l2init/*` keys present and rising; θ₀ hash guard on resume `[V, train.py:238-260]` | **L** — resume-guarded by a sha over the anchors `[V, ppo.py:theta0_hash]`; −3.2% throughput | **BUNDLE NOW**, all six |
| **`trunk_kwargs.value_sizes: [1024,1024]` (arm W)** | critic capacity where every evidence line converges; critic ctx srank99 7–10/384 vs actor 33–54 `[R, scale §D'-3]` | **M** — honestly modest; the product is a measurement nobody has made | zero — `_w.yaml` exists | instantiated `[V]`: critic 1,807,489, actor 626,059 unchanged, ceiling clears, `OBS_DIM` unchanged so mixed-width committees load (`eval_checkpoint.py` builds each member from its own config `[V:73,95]`) | **L** — +2.12× trained object is +21 MB/lane of Adam state against 1.825 GB/lane measured `[V, maxout.json]` | **BUNDLE NOW**, 3 lanes |
| **`agent.gae_lambda: 1.0`** | at γ=1 and terminal-only ±1, λ=1 makes the value target *exactly* ±1 — zero bootstrapping. Kumar's named control for rank collapse; at λ=0.95 ~53% of our target is the critic's own output `[R, scale §D'-3.4]` | **M–H** — see §A1-note | zero — one key | `loss/adv_std` must rise materially vs the λ=0.95 trio at matched step (predicted ~0.48 → ~0.60–0.65 `[V, s112 history + EV 0.59]`) | **L** — λ is a plain multiplier in the audited scan, no division, no special case `[V, buffers/episode.py]`; targets bounded in [−1,1] so it **cannot** NaN. Risk is "worse", never "dead" | **BUNDLE NOW**, 3 lanes |
| `gae_lambda: 0.75` (IDEAS 4.2) | — | **L** | — | — | — | **NO** — recipe report §3 is right and IDEAS 4.2's own correction (ii) agrees |
| `value_clip_eps` (SB3/Wang form, wired) | clamps the critic step | **L** | zero | — | L | **NO** — "no evidence it helps", "even hurts" `[R, recipe §3]` |
| `lr_schedule: power` (Wang's, wired + tested) | floors at lr0/27 | **M** | zero | — | L | **NO for this fleet** — it is a *second* way to get the floor and it changes the whole shape; the 240M-linear floor is one number and one line. Keep power in reserve |
| `epochs: 2` (Moalla's dose; ps-ppo runs 2) | fewer optimizer passes per datum; less rank collapse | **M** | zero | — | M | **NEXT FLEET** — but see the arithmetic: `43.3 × (0.3487 + 0.6513·r)` puts epochs-2 at **29.2 h** and epochs-2 **+ W1024** at **35.1 h**, i.e. *faster than today's base* `[V, cost model arithmetic]`. It is the lever that pays for width twice over, and it is a dose change with no local read. Screen it, do not bundle it |
| `minibatches` 120 → 60 | fewer, bigger, less noisy grad steps; better BLAS use at `torch_threads: 1` | **L–M** | zero | bench | M | **NEXT FLEET** — bench first, it is a throughput *and* a variance change |
| `entropy_coef` raise or schedule | keep the policy from over-committing | **L** | schedule = code | — | M | **NO** — the deployed object is argmax, so training entropy never reaches play; and bonuses are "highly sensitive … large coefficients lead to entropy explosion" `[R, recipe §3]` |
| `total_steps: 250000000` | dose, the only measured monotone axis | **L** | zero | — | M | **NO** — 6×250M ≈ 54 h base / ~66 h with W, eating the resume slack; the last doubling bought +0.001 vs SH **on the committee** `[R, STATUS]` |
| `collector.k`, `pool_size`, `latest_prob` | — | — | — | — | — | **NO** — standing rulings |
| seeds shared across arms (IDEAS 2.2) | `seat_tag` already makes eval seat names tag-derived `[V, showdown.py:968-985]`, and the engine draws teams from `f(lane_seed, battle_counter)`, so same-seed arms would face the **same team sequence** — real training-seed pairing, free | **L** here | zero | — | L | **NO for this fleet** — pairing buys a cleaner A/B (ρ unknown, P3 bounds team-luck at R² 0.0375) and *costs committee diversity*, which is the thing the ladder object monetises. Keep distinct seeds. **But IDEAS is stale: 2.2 is BUILT** |

**A1-note, why λ=1.0 and not "leave it at 0.95".** The recipe report quotes GAE's own claim —
*"λ<1 introduces bias only when the value function is inaccurate"* `[R, 1506.02438]` — to
argue against λ=0.75. Read it in our direction: **our value function is the diagnosed
inaccurate component** (EV mid 0.603, last-50 **0.592** `[V]`), so λ=0.95 is already paying a
nameable bias, levied on our weakest part. Three things make λ=1.0 the moderate move, not the
wild one: episodes are ~31 decisions `[V]`, so the effective horizon goes 20 → ~31, not
20 → ∞; the variance rise is computable (adv_std 0.48 → ~0.64, 1.33× not 10×); and the
resulting critic is a pure win-probability regressor — the object IDEAS §8.2 says we have
never trained and the leaf evaluator any future searched ladder object needs. **Honest
counter:** every comparable system runs λ<1 (VGC-Bench 0.95, H&L 0.9, ps-ppo 0.75) and none
runs 1.0. That is why it goes on three lanes, not six.

### A2. Code changes — priced against a noon deadline

| lever | mechanism | L | build | verify | R | verdict |
|---|---|---|---|---|---|---|
| **LayerNorm in `ctx_net` + value stack** (scale §E6; recipe #3) | the two stacks that lack it are exactly where srank collapsed | **M** | ~10–15 lines behind a `trunk_kwargs` flag; RNG-neutral even when on `[V, entity_deepsets.py:300-390]` | 400k smoke | **M** (unsmoked, not divergent) | **NEXT FLEET.** One interaction neither report names: `_ln_free_blocks` excludes any block containing an LN, so turning it on **silently deletes `l2init/anchor_dist_ctx_net` and changes what the `_actor_lnfree` aggregate sums** `[V, ppo.py:199-211]` — it degrades the instrument of the lever it ships beside. Fix that, then run it as its own arm |
| critic blocks in `l2init/*` | W's mechanism lives in the critic; the per-block metric is **actor-only** `[V, ppo.py:_capture_theta0]` | **L** (observability) | ~45 min incl. two test edits (`test_l2_init.py:116,387` pin exact key sets `[V]`) | unit test | **L** — `torch.no_grad()` at eval boundaries, θ₀ hash unchanged | **OPTIONAL** if the smoke is clean and there is time |
| **dense auxiliary targets** (survivors, terminal-HP diff, turns-to-end) | KataGo's ownership+score was worth 1.65× `[R, recipe 4.2]`; we are ~100× poorer in label-bits/param than a search-based self-play system `[R, scale §D'-2]` | **H over a chapter** | ~a day. Labels are derivable Python-side from each episode's terminal obs row (HP/fainted are in the mon block `[V, encoder_spec.py:142]`) — **no Rust change** | smoke | **M** | **NEXT FLEET** — highest-ceiling buildable item, far too big for 34 h |
| **R-NaD / MMD KL-to-reference magnet** `[R, recipe 4.1]` | contracts self-play dynamics to a regularised fixed point | **H** | ~30 lines on `bc_kl_coef` + an extra actor forward/minibatch (+6–10% wall, unmeasured) | smoke + η sweep | **M–H** (uncalibrated η) | **NEXT FLEET.** Strong idea; an uncalibrated regulariser is exactly what you do not leave running four days |
| `target_kl` epoch early-stop | SB3's one update-path optimisation we lack | **L** | ~10 lines | — | M | **NO** — but a **correction is owed to IDEAS §3**: "our measured KL would never fire" is a *gen-4* number. Gen-1 s112 reads `approx_kl` **max 0.113, mid-run median 0.0279** `[V]`. Do not quote that sentence for gen 1 |
| `max_grad_norm` 0.5 → ~2.0 | `grad_clip_frac` is **1.0 from update ~1** `[R, recipe §1]`; my read: grad_norm 0.86 → 2.12 → 3.74 `[V]`. The clip *is* the optimizer | **M** | zero (a key) | — | **H** — changes the optimizer's character with no read | **NO.** Free first step next fleet: log the pre-clip norm distribution; nothing does today |
| **both-seat harvest on the engine route** (IDEAS 4.1) | ~2× episodes/update at zero extra simulation | **H if free** | **NOT a night's work** | — | H | **NO.** `train.py:857` refuses it by name `[V]`; `env.rs:303-307` appends episode rows only in the *learner* branch `[V]`, so seat 2 needs a second per-battle buffer and drain shape in a 1,223-line file; `_opponent_actions` calls `move_batch`, which returns actions with **no log-prob** `[V, pool.py:130]`; the rebuild moves the sha `pkmn_gen1.verify()` pins against A-1; and `attach_harvest` refuses outright while the D25 aux head is on `[V, ppo.py:862-864]`, which this pre-reg makes MANDATORY. Days, plus a re-gate |
| IDEAS 2.9 update micro-wins | 4.3–6.0% of `update_sec`; two of four do not apply on the episode path | **L** | an afternoon + tests | — | M | **NO.** ~50 min saved over 43 h, bought by editing the hot path the night before launch |
| IDEAS 2.8 GPU/MPS for the update | the kill's premise has genuinely expired: update is now **~65% of wall**, not ~25% `[V, update_share.json 0.6513]` | **M next chapter** | bench + a CLAUDE.md change + a ruling | — | H | **NEXT FLEET** — say it loudly: the ~2.5% that killed it was measured while collection dominated |
| IDEAS 2.3 critic own-move routing | the critic's ctx carries no own-move detail and pays `move_net` FLOPs it discards `[V, entity_deepsets.py:517-521]` | **M** | the offline read alone needs ~50k collected decisions = box time we do not have | — | — | **NEXT FLEET** — a *critic* lever; same chapter as W and λ |
| IDEAS 2.1 / 2.4 · 2.7 zero-init surgery | instrument hygiene · a tool for an encoder change we are deliberately not making | **L** | box time · ~a day | — | — | **NEXT** / **NO** |
| IDEAS 4.6 **C6** fixed-damage fix | a real, measured encoder defect | — | half a day + a fleet | — | — | **NO, categorically** — both shapes change semantics or `OBS_DIM` and destroy the 100M finals as committee members |
| IDEAS §5: attention · cross-features/DCN · temporal context · shared trunk · width | architecture | — | days | — | — | **NO.** Attention is maintainer-deferred to JOURNEY 11.6; temporal context and cross-features change `OBS_DIM` or need an offline screen on an FP-derived dataset; the shared trunk is a strength risk sold as a speedup |
| IDEAS 4.4 H&L 5-term shaping | dense reward | **L** | zero code | — | M | **NO** — ranked LAST, gated on 4.1/4.3/4.5 nulling, and 4 of 5 terms reward play we already dominate on |

### A3. Ladder-object only — zero training, run them AFTER the fleet, before the ladder

| item | mechanism | L | cost | verdict |
|---|---|---|---|---|
| **committee over the 6 new finals + the 3 100M finals** | the only **credited** free lever we own: +0.0349 at 5.93 se; the 1→6 member curve runs 0.789 → 0.844 `[R, STATUS]` | **H** | zero, it is the plan | **DO** — measure ENS3-of-each-trio, ENS6-mixed and ENS9 before choosing |
| **weight-space averaging of each lane's last k rungs** ("model soup" / Polyak tail) | the code's own comment says the final policy "is an arbitrary sample of an oscillating training trajectory" `[V, train.py:1239-1241]`; under a floored anneal the last rungs sit close together, so averaging them is nearly free variance reduction — **the exact antidote to the one risk the LR floor introduces** | **M–H** | ~30 lines eval-side, zero training, evaluated like any member | **DO — in neither sibling report and in no IDEAS row.** Average within a lane, ensemble across lanes |
| member weighting / temperature on the committee's log-prob mean | free dial over an already-credited object | **L–M** | ~10 lines | **DO** if time — weight members by their own off-FP read |
| IDEAS **8.1** the unspent inference budget | we play greedy; the ladder allows ~150 s/turn and every search number we own is depth-1 at **20 ms = 0.013%** of it | **M** | box time post-fleet | **DO, post-fleet.** The depth null is licensed only as "no evidence at these budgets and this δ"; a δ sweep for deeper backups is the cheap first step |
| IDEAS 8.2 critic-as-evaluator · 8.3 belief-sampled search | the leaf evaluator is the bottleneck · the imperfect-information leg | **H / M** | a chapter | **NEXT** — λ=1.0 is a down-payment on 8.2 |
| IDEAS 8.4 FP distillation | — | — | — | **NO — charter.** Excluded by the purity constraint |

---

## B. CONCRETE BUNDLES

All three keep: `collector.mode engine`, `k: 8`, `opp_action: true` + `aux_oppact_coef: 0.1`,
the 20/0.8/5 pool, `total_steps: 200000000`, six lanes, seeds **104 112 120 / 128 136 144**.

### BUNDLE 1 — "two critics, one schedule fix" — **RECOMMENDED**

Diffs **on all six lanes**, against `configs/showdown_monster200m.yaml`:

```yaml
agent:
  l2_init_decay: 0.02            # NEW key
  lr_anneal_steps: 240000000     # was 200000000; total_steps stays 200000000
```

Trio W — `configs/showdown_monster200m_w.yaml` (exists; add the anneal line):

```yaml
agent:
  trunk_kwargs:
    value_sizes: [1024, 1024]    # was [384, 384]
env_kwargs: { seat_tag: m10w }
```

Trio G — new `configs/showdown_monster200m_lg.yaml`:

```yaml
agent:
  gae_lambda: 1.0                # was 0.95
env_kwargs: { seat_tag: m10g }
```

One launcher line, because `monster_fleet.sh:85` asserts equality where `rl/train.py:433`
asserts only `>=` `[V]`:

```bash
if [ "$CFG_STEPS" != "$STEPS" ] || [ "$CFG_ANNEAL" -lt "$STEPS" ]; then
```

Two commands, W first (it is the long pole):

```
bash scripts/monster_fleet.sh configs/showdown_monster200m_w.yaml  200000000 104 112 120
bash scripts/monster_fleet.sh configs/showdown_monster200m_lg.yaml 200000000 128 136 144
```

**Rationale.** Every lever in the chapter now points at the same organ. D22's srank, the EV
plateau at 0.59 `[V]`, IDEAS 8.2 and both sibling reports independently say **the critic is
the bottleneck**, and this fleet attacks it three ways: plasticity (L2, plus the floor that
keeps L2 alive in the tail), capacity (W), and the bootstrapping Kumar names as the cause
(λ=1.0). The two *hypotheses* sit on separate trios, so attribution is clean; the two trios
train genuinely different critics, which is the best possible input to a log-prob committee;
and neither trio spends three lanes re-measuring the horizon, our weakest axis. **It is also
probe-proof:** `PLASTICITY_PROBE`'s pre-stated branches send TRAINABLE and
REPRESENTATION-DEGENERATE to λ=1.0 + denser targets and PLASTICITY-LOST to W — this split
buys whichever fires, and the probe (unrun, ~1 h CPU-only) can still re-weight the trios
before launch rather than block them.

**Hours at six lanes:** ≈**53–55 h** `[R, scale §C]` — the G trio finishes ≈44.7 h and hands
the box back to 3-wide; the W trio lands ≈53–55 h. Against a 72–96 h window that leaves
~20 h of slack for resumes.

### BUNDLE 2 — "no ruling needed"

Identical to BUNDLE 1 with `lr_anneal_steps: 200000000` on both files and the launcher
untouched. Take this if the LR-floor ruling does not land tonight. Costs the +17%
lr-integral and leaves L2's decay switched off through the tail.

### BUNDLE 3 — "three arms, two seeds" (offered, argued against)

2 × (L2+floor) + 2 × (+W) + 2 × (+λ1.0). Buys a plain-recipe control at 200M and full
attribution. **Do not run it:** per-arm committees fall to k=2, and the measured member curve
puts ENS2 at 0.817 against ENS3's 0.827 `[R, STATUS]` — you would pay a ladder point for an
attribution the maintainer has explicitly said he does not want to buy by the week.

### The 400k smoke — what it must show (both configs, through the launcher)

Set `eval_every: 50000` in the two derived smoke configs, or 400k yields a single eval
sample. **Know the trap:** `derive_monster_config.py` moves the anneal with the horizon, so a
400k smoke anneals over 400k and its late curves reflect lr≈0 — read the first ~200k, and
compare the two trios only at matched steps.

- **S-1** launcher preflight all green: `pkmn_gen1` importable, tree clean, seeds distinct,
  `simulator ≥ 4`, Node up, bank present, no existing run dir.
- **S-2** `meta.yaml` → `params.actor` **626,059** both trios; `params.critic` **494,849** (G)
  / **1,807,489** (W). Instantiated and confirmed `[V]`.
- **S-3** `l2init/*` present, > 0, rising over ≥3 evals — proves L2 live. Expect **actor
  blocks only**; the decay covers the critic but the per-block view does not `[V]`.
- **S-4** λ manipulation: `loss/adv_std` on the G trio materially above the W trio at matched
  step. If they match, λ did not take.
- **S-5** rate: G lanes ≥ ~1200 steps/s/lane 6-wide; W lanes ≈ **1000** (1282.3 / 1.274).
  **If W < ~900, the cost model is wrong** → drop to `[768,768]` (≈49.8 h `[R]`) or drop W.
- **S-6** fleet peak RSS ≤ ~12 GB (base 10.95 GB at 6-wide `[V, maxout.json]`).
- **S-7** no NaN/inf in any `loss/*`; `explained_variance` finite and rising; `loss/entropy`
  falling from ~1.8 and still > 1.0 at 400k.
- **S-8** **the resume test, and it is the one that matters.** Kill one lane; confirm the
  watchdog resumes it *with the engine interpreter* (its default `PY` is the
  `pokemon-showdown-rl` env, which has no `pkmn_gen1` `[V, train_watchdog.sh:47]` — it is
  correct only because `monster_fleet.sh` exports `PY` into it), that the θ₀ hash guard
  passes, that the wide critic reloads, and that `from_step` in `meta.yaml` is sane.
- **S-9** bytes written per lane per 100k steps → extrapolate (§D-3).
- **S-10** if the floor is in: the launcher accepts anneal 240M > steps 200M and the config
  records it.

### Fallback if a bundle underperforms

Pre-stated, so it is not a post-hoc choice: **the ladder object is the committee of whichever
lanes read better off FP@20** (greedy, n=3000/lane, same-session re-draw, both FP@20
disclosures travelling). Read ENS3-of-W, ENS3-of-G, ENS6-mixed and ENS9-with-the-100M-finals;
take the best. **The floor is the 100M ENS3** (0.82356 vs SH; 0.557 off FP@20 `[R, STATUS]`)
— if no trio's committee beats it off FP, the ladder object is unchanged and the fleet's
product is the mechanism measurement plus six more candidate members.

---

## C. WHAT NOT TO BUNDLE, AND WHY

- **Arms B and C.** Three reviews now agree. B is bitwise A plus a head whose only consumer
  is search, and search is a null on both axes; C puts the privileged block in the advantage
  channel at λ=0.95 where the vacatur named λ=1.0, with a falsifier that cannot fire.
- **Anything touching `OBS_DIM` or the encoder** — C6, temporal context, cross-features. They
  make the 100M finals unusable as committee members, which forfeits the floor.
- **Both-seat harvest.** Engine-route Rust work plus a parity re-gate, double-blocked by the
  mandatory aux head. §A2 has the file:line evidence.
- **λ=0.75, bigger entropy, obs-norm, PopArt/symlog, value clipping, PFSP/exploiters, pool
  ablation, shared trunk.** Recipe report §3 settles these on the field's evidence; I have
  nothing to add and will not re-derive them.
- **`max_grad_norm` and `epochs`.** Both are real findings and both change the optimizer's
  character. Neither is a thing to change 34 h before four unattended days.
- **IDEAS 2.9 micro-optimisations.** ~50 min saved over 43 h, bought by editing the update's
  hot path the night before launch.
- **Seed pairing across arms.** Available for free and I still say no: it trades committee
  diversity, which is the credited lever, for an A/B precision the maintainer has said he
  does not want to pay a week for.
- **250M.** Eats the resume slack for a doubling the committee prices at +0.001 vs SH.

---

## D. VERIFICATION CHECKLIST — in order

### D-1. Rulings owed tonight (maintainer only)

1. **The LR floor** against JOURNEY 10's verbatim `lr_anneal_steps == total_steps`. Note the
   clause defends against `anneal < horizon`; this is the opposite direction, and
   `rl/train.py:433` already permits it by name `[V]`.
2. **The arm allocation** — ratify by editing the `[RWL]` block and committing (rule 3).

### D-2. Agent, tonight, in this order

3. **Commit or delete every untracked file** — `scripts/plasticity_probe.py`,
   `PLASTICITY_PROBE_2026-09-12.md`, this report `[V, git status]`. **The launcher refuses a
   dirty tree** — a hard launch blocker, not hygiene.
4. Write the two arm configs + the one-line launcher relaxation. Derive the two 400k smokes
   and hand-set `eval_every: 50000` in them.
5. **Re-do the DISK and eval arithmetic for the ratified shape.** The header's block is
   100M×9-shaped `[V, config:741-747]`: at 200M×6 it is **400 rungs/lane, not 200**, and
   ~**800 in-loop evals/lane, not 400**. My estimate: ≈33 GB of rungs (A-shape) rising to
   ≈51 GB with a W trio, +~21 GB wandb/history → **≈72 GB against 146 GB free** `[V, df]`.
   It fits; nobody has checked it at this shape, and there is **no retention policy** —
   `save_checkpoint` writes and never deletes.
6. **Run the 400k smoke, S-1…S-10, including the kill/resume test (S-8).**
7. Cheap, in this order if the box is free: (a) **run the capacity-loss probe** —
   `scripts/plasticity_probe.py` and its protocol are written and **unrun** (§4/§5 of
   `PLASTICITY_PROBE_2026-09-12.md` say "pending") `[V]`; ~1 h CPU-only, and its branches
   re-weight the trios; (b) a 10-minute **`torch_threads` bench at width 6**, which is
   **unmeasured** — every cell in `maxout.json` is `threads: 1` `[V]`. If 2 threads pays
   anything, it funds W outright.
8. Pre-write the readout's owed disclosures ([RWL-6]): `RESUMES=`, `NODE_RESTARTS=`, each
   resume's `from_step`, the `/timer` line, the anchor battery with **BC-clone h2h still
   PENDING**.

### D-3. Human, with a password or a GUI, before leaving

9. `sudo pmset -c sleep 0 disksleep 0`.
10. System Settings → Software Update → **"Install macOS updates" OFF** (it was ON on
    2026-09-11) — an idle box can reboot itself mid-fleet and nothing relaunches the lanes.
11. Lid **OPEN**; quit VS Code and Chrome (six lanes are ~11 GB of 24).
12. Free: the GitHub branch-protection click on `main` (IDEAS §6) — server-side, touches
    nothing on this box.

### D-4. Post-fleet, before the ladder (zero training)

13. Committee reads: ENS3-of-W, ENS3-of-G, ENS6-mixed, ENS9-with-the-100M-finals, off FP@20.
14. **Rung weight-averaging** (§A3) on the best trio — the free antidote to the floored
    anneal's noisier final.
15. The mechanism co-primary: srank99 **as a fraction of width** (1024 vs 384) with the
    unchanged-width actor as control, dormancy at τ=0.025 **and** τ=0.1, the critic's
    pre-activation norm, the EV plateau, entropy `[R, scale §E(4)]` — plus the same reads on
    the λ trio, where a bootstrapping fix should move srank at **unchanged** width. Those two
    together separate "capacity was scarce" from "bootstrapping was the pathology", and that
    separation is the fleet's real product.
16. IDEAS 8.1: re-run the search-depreciation curve at 0.5 / 5 / 50 s with a **recalibrated
    δ**, on an idle box, before spending any ladder exposure.

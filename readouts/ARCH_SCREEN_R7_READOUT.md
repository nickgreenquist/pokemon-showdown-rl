# R7 ARCHITECTURE SCREEN — entity ATTENTION vs the entity DEEPSETS trunk

**JOURNEY step 11.6.** Decided offline on Foul Play behavioural cloning, by the rule in
`configs/bc_arch_screen.yaml`, which was committed **before the first fit ran**.

> **VERDICT: THE SCREEN DOES NOT CLEAR.** Δagreement_free **+0.0179** (95% CI
> [+0.0143, +0.0214]) misses the pre-stated **+0.02** bar, and the throughput ratio
> against today's trunk is **6.52×**, over the pre-stated **3.0×** ceiling. The interval
> excludes 0, so the gain is real; it is smaller than the bar and it costs 6.5× the
> update step. **Recommendation: do not spend a §11.6 fleet arm on this trunk as
> specified.** The mechanism read says the gain is generic, not entity-attention-shaped.

Every number below is re-derived from `results/arch_screen/` by
`scripts/arch_screen_readout.py`. Its verbatim output is in §8 and the machine-readable
form is `results/arch_screen/readout.json`; **cite those, not this prose.**

---

## 1. Provenance

**Branch** `worktree-agent-ae28c38b2c31010fc`, off `e6cc5dd`.

| commit | what |
|---|---|
| `85201da` | `rl/networks/entity_attention.py` — the trunk |
| `96ac5e0` | `rl/agents/ppo.py` — the `trunk == "attention"` branch |
| `33e9425` | `scripts/train_bc.py` — `--trunk`, and per-row held-out predictions |
| `878059b`, `1095d3a`, `eb932e8` | `tests/test_entity_attention.py` |
| **`958f24f`** | **the pre-reg** (`configs/bc_arch_screen.yaml`) — precedes every fit |
| `81ab324` | `scripts/arch_screen_bench.py`, `scripts/arch_screen_fits.sh` |
| `0ac8306`, `1596bf8`, `4f9dff2`, `a8fd22e` | `scripts/arch_screen_readout.py` |
| `d009660` | `tests/test_arch_screen_readout.py` — gates on the bootstrap itself |

All six fits ran with the working tree at `81ab324`+`0ac8306`, which differ from `85201da`
only in files no fit imports — **so all six arms are the same program**, the
running-block-imports-the-working-tree landmine. `rl/` was untouched after `96ac5e0`.
The bench's own `git_sha` stamp is `a8fd22e` (`results/arch_screen/throughput.json`).

### Dataset — built for this screen

No 828-dim BC dataset existed (`data/fp_all_v2r` is 808-dim, `data/fp_all_v2` 807), so
the six gen-1 Foul Play tape runs in `data/fp_tapes_all/` were re-embedded through the
CURRENT encoder into
`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/data/fp_all_v2i/`.

| shard | rows | md5 |
|---|---:|---|
| `v2i_run_13185.npz` | 50,269 | `856814a96724c581706a9831743db358` |
| `v2i_run_13353.npz` | 50,148 | `2ca51d6c983d6b0bc2c54e1fa4371170` |
| `v2i_run_13445.npz` | 50,179 | `7dd3fcf4e8e8d3c7d174e58f7f5d87db` |
| `v2i_run_4106.npz` | 10,148 | `537ac0602edac8f128d4904dffc2b5cb` |
| `v2i_run_4115.npz` | 9,699 | `761a7602771a7b442e4fea33d86897ce` |
| `v2i_run_4121.npz` | 9,997 | `75301312d2e8d2f1fd7a82f29b4a9b65` |
| **total** | **180,440** over **7,200 battles** | |

`obs_dim` 828, `gen` 1, `expert` foulplay, fingerprint `{obs_dim: 828, encoder: v2,
set_prior: true, recharge_fix: true, ids: true, c6: false}`. **All six
`tape_to_dataset.py` gates PASS** — G1 7,200/7,200 terminal; G2 label identity
180,440/180,440 round-tripped through the DEPLOYMENT conversion (0 outside mask, 0
mismatches); G3 rqid alignment 100%; G4 outcome agrees 7,200/7,200; G5 3,050 placeholder
turns (0.42/battle); G6 zero `|error|` frames and zero replay exceptions.
Log: `results/arch_screen/dataset_build_v2i.log`.

### Commands

```
env PYTHONPATH=<worktree> POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 nice -n 19 \
  python scripts/tape_to_dataset.py --tapes <main>/data/fp_tapes_all \
  --out <main>/data/fp_all_v2i/v2i
```

```
bash scripts/arch_screen_fits.sh          # the six fits, sequential and niced
```

which runs, for `--seed` 0/1/2:

```
nice -n 19 python scripts/train_bc.py --data <main>/data/fp_all_v2i/v2i --target soft \
  --max-rows 180000 --epochs 20 --batch-size 512 --lr 1e-3 \
  --run-name arch_screen_entity_s<N> --trunk entity_deepsets --seed <N>

nice -n 19 python scripts/train_bc.py --data <main>/data/fp_all_v2i/v2i --target soft \
  --max-rows 180000 --epochs 20 --batch-size 512 --lr 1e-3 \
  --run-name arch_screen_attn_s<N> --trunk attention \
  --d-model 128 --n-layers 2 --n-heads 4 --seed <N>
```

Those hyperparameters are the banked 180k clone's, matched from
`runs/bc_fp_v2r_soft_180k_s0/bc_metrics.json` (soft targets, 20 epochs, batch 512,
lr 1e-3, val_frac 0.1).

```
nice -n 19 python scripts/arch_screen_bench.py --out <main>/results/arch_screen/throughput.json
python scripts/arch_screen_readout.py --results <main>/results/arch_screen \
  --json-out <main>/results/arch_screen/readout.json
```

Wall clock, from the runner's own stamps in `results/arch_screen/` and the block log:
entity fits **2m04s / 2m00s / 2m05s** (00:10:30→00:12:34, 00:28:39→00:30:39,
00:46:42→00:48:47), attention fits **16m05s / 16m03s / 15m52s** (00:12:34→00:28:39,
00:30:39→00:46:42, 00:48:47→01:04:39). The pre-stated abort threshold was 2× the spec's
~18 min estimate for an attention fit; no fit came close.

---

## 2. The pre-stated rule, verbatim from `configs/bc_arch_screen.yaml`

> QUANTITY: Δagreement_free = mean over seeds s ∈ {0,1,2} of (agreement_free(B_s) −
> agreement_free(A_s)), each arm read AT ITS OWN BEST EPOCH, best = max val
> agreement_free over the 20 epochs, exactly as train_bc selects `best_checkpoint.pt`.
> `agreement_free` is agreement over MULTI-CHOICE held-out rows only; single-legal-action
> rows are free for any policy and are excluded (train_bc's own rule).
>
> ACROSS-LANE AGGREGATOR, NAMED: the unweighted MEAN of the three per-seed PAIRED
> differences. Not a pooled-rows difference — the three seeds hold out different battles,
> so pooling rows across seeds would mix a split effect into the arm effect.
>
> INTERVAL: CLUSTER BOOTSTRAP BY BATTLE, 1,000 resamples, seeded. One replicate = for
> each seed s, resample s's held-out BATTLES with replacement to the same battle count,
> recompute agreement_free for A_s and B_s over the resampled rows (SAME battles for both
> arms — the pairing is the point), difference them, then average the three. 95% CI = the
> [2.5, 97.5] percentiles of the 1,000 replicate means.
>
> BAND DIRECTION, STATED: the CI is on B − A. POSITIVE means the attention arm agrees
> with the teacher MORE OFTEN. For Δval_kl (reported the same way) NEGATIVE means
> attention is better — it is a forward KL(teacher ‖ student) and lower is closer.
>
> THROUGHPUT: median TRAIN-STEP wall time — forward + backward + optimizer step, batch
> 512, torch.set_num_threads(1), ≥30 timed steps after 5 warmup, on this box, niced,
> nothing else of ours running. … THE GATE READS attention / entity_deepsets — the ratio
> against TODAY's trunk.
>
> **CREDIT LINE — THE SCREEN CLEARS IFF ALL THREE HOLD:**
> **(i) Δagreement_free ≥ +0.02 (ii) its 95% cluster-bootstrap CI excludes 0**
> **(iii) throughput loss ≤ 3x, i.e. median_step(attention) / median_step(entity_deepsets) ≤ 3.0**

The repo's standing credit line, restated in the header as CLAUDE.md requires: *"a lever
is credited iff pooled delta ≥ +0.025 and ≥ 2·se_diff"*, with `se_diff` the larger of the
binomial and the seed-clustered estimate. That line governs a lever credited on **vs-SH
win rate** under the locked eval protocol; **nothing here is a win-rate number.** The
+0.02 / CI-excludes-0 bar is ARCH_SCREEN_SPEC's own and gates only "is a §11.6 fleet arm
worth its pre-reg".

**Arms.** A = `--trunk entity_deepsets`, actor **626,059** params, the W base's
`trunk_kwargs`. B = `--trunk attention --d-model 128 --n-layers 2 --n-heads 4`, actor
**564,875** params. **Capacity is not the variable and arm B is the SMALLER net:**
564,875 < 626,059 < 681,994 (`ACTOR_PARAM_CEILING`, the flat MLP's count). The arms share
`EntityTokenizer`, the 152/166 vocabularies, `embed_dim` 64, the pointer alignment and the
masking path. **The only difference is the mixer:** a permutation-invariant max pool
versus two pre-LN self-attention blocks.

---

## 3. Per-seed, per-arm

Each arm at its own best epoch. `n_free` = multi-choice held-out rows (the ones a clone
can get wrong); `n` = all held-out rows. Source: `results/arch_screen/readout.json`.

| arm | seed | best ep | agreement_free | val_kl | fitted ent | teacher ent | r 0–1 | r 2–3 | r 4–6 | n_free | n | actor params |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| entity_deepsets | 0 | 18 | 0.6812 | 0.5007 | 1.2977 | 1.1287 | 0.6993 | 0.6918 | 0.6678 | 17,887 | 18,201 | 626,059 |
| attention | 0 | 12 | **0.7031** | 0.4777 | 1.2932 | 1.1287 | 0.7262 | 0.7133 | 0.6886 | 17,887 | 18,201 | 564,875 |
| entity_deepsets | 1 | 20 | 0.6799 | 0.5105 | 1.2692 | 1.1261 | 0.7226 | 0.6809 | 0.6658 | 17,811 | 18,146 | 626,059 |
| attention | 1 | 20 | **0.6919** | 0.5079 | 1.2244 | 1.1261 | 0.7336 | 0.6918 | 0.6789 | 17,811 | 18,146 | 564,875 |
| entity_deepsets | 2 | 20 | 0.6813 | 0.5091 | 1.2505 | 1.1191 | 0.7156 | 0.6913 | 0.6642 | 17,369 | 17,681 | 626,059 |
| attention | 2 | 20 | **0.7012** | 0.5025 | 1.1905 | 1.1191 | 0.7433 | 0.7097 | 0.6827 | 17,369 | 17,681 | 564,875 |

**Pairing verified, not assumed.** The readout asserts element-wise that the two arms hold
out identical `battle_ids`, identical `free` masks and identical labels at each seed, and
refuses to print a delta otherwise — 718 battles per seed, 18,201 / 18,146 / 17,681 rows.
An unmatched comparison is how a −0.0007 null became a −0.053 "result" here on 2026-09-17.

**Reference point, not a control:** the banked 808-dim MLP clone
`runs/bc_fp_v2r_soft_180k_s0` reached best agreement_free **0.5175** at epoch 9. Different
encoder width, different trunk, one seed — it says the fits are working, and it is
differenced against nothing.

---

## 4. Primary read — the paired delta

| quantity | mean over seeds | 95% CI (cluster bootstrap by battle, 1,000 resamples) | per-seed | direction |
|---|---:|---|---|---|
| **Δagreement_free** | **+0.0179** | **[+0.0143, +0.0214]** | +0.0220, +0.0120, +0.0199 | positive favours attention |
| Δval_kl | −0.0107 | [−0.0133, −0.0081] | −0.0230, −0.0026, −0.0066 | negative favours attention |

The interval excludes 0 on both metrics: **attention fits this teacher better, and the
effect is not noise.** It is also smaller than the +0.02 bar that was written down before
the fits, and the seed spread (+0.012 to +0.022) is wide relative to the bar — seed 1
alone would have read +0.012.

**Best-epoch selection is not inflating it.** Five of six fits peak at or near epoch 20,
so the readout's automatic "under-trained" note fires. Reading the curves instead of the
note: the last-5-epoch spreads are 0.0030–0.0079, i.e. every fit is on a near-plateau, and
the delta computed from the **epochs 16–20 MEANS** — which is immune to picking the max of
a noisy tail — is **+0.0182** (per seed +0.0219, +0.0122, +0.0206), against +0.0179 from
the best epochs. The two estimators agree to 0.0003.

**The 20-epoch budget, if anything, flatters arm B.** From epochs 11–15 to 16–20, arm A
gains +0.0047 on average and arm B +0.0022. Arm A still has the larger tail slope at this
budget, so **+0.018 should be read as an upper bound on the asymptotic gap at 180k rows.**
Extrapolating the two tails to a crossing is not supported by three seeds of a decelerating
curve and is not done here.

---

## 5. Throughput

One actor train step — forward, masked soft CE, backward, Adam step — batch 512,
`torch.set_num_threads(1)`, median of 30 timed steps after 5 warmup.
Source: `results/arch_screen/throughput.json`.

| net | actor step | critic step | actor params |
|---|---:|---:|---:|
| attention (d128, 2L, 4H) | **139.49 ms** | 137.56 ms | 564,875 |
| entity_deepsets (today's trunk) | **21.40 ms** | 12.34 ms | 626,059 |
| mlp [512,512] (the retired comparator) | 4.76 ms | 4.56 ms | 692,234 |

| ratio | value | what it is |
|---|---:|---|
| **attention / entity_deepsets (actor)** | **6.52×** | **THE GATE.** Ceiling was 3.0× |
| attention / entity_deepsets (actor+critic) | 8.21× | not the gate; an RL projection's input |
| attention / mlp (actor) | 29.31× | the 2026-08-07 kill quoted **34.6×** on this exact pairing |
| entity_deepsets / mlp (actor) | 4.50× | why the old number could not be reused |

**This answers the open question JOURNEY §11.6 names.** It records that "the 34.6× was
measured against the flat MLP, so the honest ratio against today's trunk is simply
unknown." It is **6.52×**. The 29.31× we measure against the MLP reproduces the historical
34.6× closely enough to trust the instrument, and it factorises exactly:
29.31 ≈ 4.50 (entity trunk vs MLP) × 6.52 (attention vs entity trunk). The part of the old
headline that was the entity trunk's own cost is already being paid by every lane we run,
so it is not attention's to pay against today's baseline.

**A second replicate, taken before the fit block** with the same script and settings
(`results/arch_screen/throughput_replicate1_prefits.json`, 00:09:32Z) gives **5.96×**
against the post-block run's 6.52× (01:05:18Z) — a 9% spread across the session, both far
above the ceiling. The verdict on (iii) does not turn on which replicate is used.

### 5b. The RL-loop projection — ARITHMETIC, NOT A MEASUREMENT

An RL update trains both heads: entity 21.40 + 12.34 = 33.73 ms, attention 139.49 + 137.56
= 277.04 ms, a **8.21×** both-heads ratio. JOURNEY §11.6 records that the engine port moved
the update from 25% to **~65% of wall**. Taking that as given, a lane paying 8.21× on 65%
of its wall and 1× on the rest would run at **5.69×** the wall per step — **17.6%** of the
steps in the same time.

**That sentence is arithmetic on a number measured elsewhere, not a measurement made
here.** No attention lane exists, the collector is unchanged, and batching or threading
choices inside a real update could move it either way. It is written down because a future
§11.6 pre-reg has to start from something, and an explicit chain with its input named is
auditable in a way a remembered "about 6×" is not. **Do not quote 5.69× or 17.6% as a
measured throughput number.**

---

## 6. Secondary — mechanism. Never a verdict input.

**The pre-stated mechanism test fails for attention.** The config states: *"A gain
CONCENTRATED in the 4-6 band is evidence for entity attention specifically … A FLAT gain
across all three is generic capacity and should be reported as such."*

| opponent mons revealed | Δ (B − A) | per-seed | n per seed |
|---|---:|---|---|
| 0–1 | **+0.0218** | +0.0269, +0.0110, +0.0277 | 2,644 / 2,729 / 2,637 |
| 2–3 | +0.0169 | +0.0215, +0.0109, +0.0184 | 6,508 / 6,343 / 5,976 |
| 4–6 | +0.0175 | +0.0208, +0.0132, +0.0185 | 8,735 / 8,739 / 8,756 |

The gain is flat, and if anything **largest where the least is revealed** — the opposite of
the predicted signature. Read as pre-stated: **this is generic capacity or a better
optimisation surface, not evidence that cross-entity attention is doing the work.** That
matters more than the size of the delta: the argument for this trunk was that attention
lets a token read another token before the pool, and the band where there is most to read
is the band with the smallest gain. (The three buckets partition `reveal` with no unnamed
cell. In practice `reveal` never falls below 1 in held-out rows — the opponent's active mon
is always revealed — so the "0–1" bucket is entirely reveal = 1.)

**Entropy: no collapse in either arm.** Fitted entropy averages 1.2724 (A) and 1.2360 (B)
against the teacher's 1.1247 — both ABOVE the teacher's, which is what soft targets are
for. Attention sits closer to the teacher, i.e. it is the slightly sharper fit.

**Sample efficiency, descriptive.** At seed 0 the attention arm reaches 0.6239 after ONE
epoch, where arm A needs nine (0.6646 at epoch 9), and it passes arm A's twenty-epoch
plateau by epoch 4. Whatever the asymptotic gap, the two arms get there very differently.
**This says nothing about RL** — a supervised fit against a fixed teacher and an on-policy
learner with a terminal-only reward are different optimisation problems.

---

## 7. Verdict, by the rule

| gate | value | result |
|---|---|---|
| (i) Δagreement_free ≥ +0.02 | +0.0179 | **FAIL** |
| (ii) 95% CI excludes 0 | [+0.0143, +0.0214] | PASS |
| (iii) attention / entity_deepsets ≤ 3.0× | 6.52× | **FAIL** |
| **⇒ THE SCREEN DOES NOT CLEAR** | | |

ARCH_SCREEN_SPEC's stricter both-metrics variant (which also required Δval_kl ≤ −0.02)
would **also not clear**: Δval_kl is −0.0107, CI [−0.0133, −0.0081].

**What follows, by the actions pre-stated in the config:**

- **(iii) is a MEASURED MECHANISM CEILING** and is the one result here that may be cited
  against adoption. Quote it as *"6.5× the entity trunk's actor train step, 1-thread CPU
  microbenchmark at batch 512"* — never as "attention is 34.6×", and never without the
  comparator.
- **(i) failing is NOT a kill.** It may not appear in a ranking, an opinion, or a "why we
  dropped X" — not even as a hedge (CLAUDE.md rule 6). It is one 180k-row supervised fit
  against a search teacher; it cannot resolve an advisory-scale effect, and it does not
  measure the objective the fleet optimises.
- **Recommendation: do not spend a §11.6 fleet arm on this trunk as specified.** The case
  would have to be rebuilt, not re-argued, and the three things that would rebuild it are
  (a) a cheaper attention variant — the cost here is two full 21-token blocks on CPU, and
  d_model, depth and sequence length are all untried dials; (b) a GPU-for-update, which
  §11.6 already names as the relevant mitigation and which is a maintainer decision; or
  (c) a mechanism read that actually points at cross-entity structure, which this one does
  not. **None of that is settled by this screen, and this screen must not be quoted as
  settling it.**

---

## 8. The readout, verbatim

Reproduce with
`python scripts/arch_screen_readout.py --results results/arch_screen --json-out results/arch_screen/readout.json`.
Saved at `results/arch_screen/readout_stdout.txt`.

```
RULE (pre-registered, configs/bc_arch_screen.yaml):
  CLEARS iff (i) delta agreement_free >= +0.02, (ii) its 95% cluster-bootstrap-by-battle CI excludes 0, and (iii) median train-step attention / entity_deepsets <= 3.0x.

PER-SEED, PER-ARM (each arm at its OWN best epoch; n = held-out rows)
arm              seed  ep  agree_free   val_kl  fit_ent  tch_ent    r0-1    r2-3    r4-6  n_free       n   params
entity_deepsets     0  18      0.6812   0.5007   1.2977   1.1287  0.6993  0.6918  0.6678   17887   18201  626,059
attention           0  12      0.7031   0.4777   1.2932   1.1287  0.7262  0.7133  0.6886   17887   18201  564,875
entity_deepsets     1  20      0.6799   0.5105   1.2692   1.1261  0.7226  0.6809  0.6658   17811   18146  626,059
attention           1  20      0.6919   0.5079   1.2244   1.1261  0.7336  0.6918  0.6789   17811   18146  564,875
entity_deepsets     2  20      0.6813   0.5091   1.2505   1.1191  0.7156  0.6913  0.6642   17369   17681  626,059
attention           2  20      0.7012   0.5025   1.1905   1.1191  0.7433  0.7097  0.6827   17369   17681  564,875

pairing verified: identical held-out rows per seed (battles [718, 718, 718], rows [18201, 18146, 17681])

PAIRED DELTA (B attention - A entity_deepsets), mean over seeds [0, 1, 2]; CI = cluster bootstrap by battle, 1000 resamples
  dagreement_free  +0.0179   95% CI [+0.0143, +0.0214]   per-seed [0.022, 0.012, 0.0199]   (positive favours attention)
  dval_kl          -0.0107   95% CI [-0.0133, -0.0081]   per-seed [-0.023, -0.0026, -0.0066]   (negative favours attention)

SECONDARY (MECHANISM, NEVER A VERDICT INPUT) — delta by how many opponent mons are revealed
  reveal 0-1: d +0.0218   per-seed [0.0269, 0.011, 0.0277]   n [2644, 2729, 2637]
  reveal 2-3: d +0.0169   per-seed [0.0215, 0.0109, 0.0184]   n [6508, 6343, 5976]
  reveal 4-6: d +0.0175   per-seed [0.0208, 0.0132, 0.0185]   n [8735, 8739, 8756]
  entity_deepsets  fitted_entropy 1.2724 vs teacher 1.1247 (ABOVE the teacher's)
  attention        fitted_entropy 1.2360 vs teacher 1.1247 (ABOVE the teacher's)
  NOTE: at least one arm's best epoch is the LAST (20) — that arm was still improving and is UNDER-TRAINED at this budget. A caveat on the null, not on the arm.

THROUGHPUT (one actor train step, batch 512, threads 1, median of 30 after 5 warmup)
  attention        policy   139.49 ms   value   137.56 ms   params   564,875
  entity_deepsets  policy    21.40 ms   value    12.34 ms   params   626,059
  mlp_512x512      policy     4.76 ms   value     4.56 ms   params   692,234
  GATE ratio attention / entity_deepsets = 6.52x (pre-registered ceiling 3.0x)
  historical comparator attention / mlp_512x512 = 29.31x (the 2026-08-07 kill quoted 34.6x on this pairing)
  both-heads (actor + critic) attention / entity_deepsets = 8.21x — NOT the gate; the input an RL projection would use

VERDICT
  (i)   delta agreement_free +0.0179 >= +0.02      : FAIL
  (ii)  95% CI [+0.0143, +0.0214] excludes 0        : PASS
  (iii) throughput ratio 6.52x <= 3.0x          : FAIL
  => THE SCREEN DOES NOT CLEAR
  (ARCH_SCREEN_SPEC's stricter both-metrics variant, which also required d val_kl <= -0.02: d -0.0107 CI [-0.0133, -0.0081] -> would NOT clear)
  (iii) is a MEASURED MECHANISM CEILING and is the one result here that may be cited against adoption. A failure of (i)/(ii) is NOT a kill and may not appear in a ranking or an opinion (CLAUDE.md rule 6).
```

The readout's automatic "UNDER-TRAINED" note is conservative and §4 reads the curves
instead: both arms are on a near-plateau, and the epochs-16–20-mean estimator reproduces
the best-epoch delta to 0.0003.

---

## 9. What may NOT be said about any number here

1. **BC agreement is not win rate and predicts no RL outcome.** The screen chooses a
   trunk; it does not forecast what that trunk does under PPO with a terminal-only reward.
   Representable under supervision does not imply reachable by PPO. **No number here may
   be converted into, compared with, or used to project a vs-SH win rate or a ladder
   rating in either direction.**
2. **Agreement rewards only structure THE TEACHER uses.** Foul Play is a search bot with a
   set prior. An architecture that sees something Foul Play does not use scores zero here
   and could still be right; one that reproduces a Foul Play artefact scores well and is
   not thereby better. A clone number is never style evidence.
3. **Purity.** These are Foul Play tapes. **No weights fitted here may ever enter a
   learner** — the pure self-play lane excludes expert-data bootstrapping. ONLY THE
   ARCHITECTURE CHOICE TRANSFERS. Every checkpoint this screen wrote lives under the
   worktree's gitignored `runs/` and is throwaway by construction; none was evaluated
   against SimpleHeuristicsPlayer, Foul Play or anything else, and none should be.
   `results/arch_screen/` contains no `.pt` file.
4. **The throughput number is a 1-thread CPU microbenchmark** of one net's train step at
   batch 512. Not an RL update, not a lane's steps/s, not a wall-clock projection. Quote
   it with that scope and with the comparator named — which is the entire lesson of the
   2026-08-07 kill.
5. **The +0.0179 is not a null and the failure of (i) is not a kill.** The CI excludes
   zero: attention really does fit this teacher better. What failed is a pre-stated bar,
   at one dose, on one objective.
6. **This screen does not answer JOURNEY §11.6.** That step's win-rate question is a
   §4-class fleet arm needing its own pre-reg with mechanism co-primary. The timing trap
   §11.6 records still holds: architecture expires at a run's launch, so the decision has
   to be made BEFORE a run starts.

---

## 10. Disclosures

- **DEVIATION FROM THE PRE-REG.** The config's throughput clause says *"on this box,
  niced, nothing else of ours running"*. That was not met: the exit-gate queue's Foul Play
  evaluation arm (`xggrbot` vs `xggrseat`, gen1randombattle, `--search-time-ms 20`,
  `--run-count 3200`, and afterwards its tree arm) was live throughout and could not be
  paused. **What was met:** no fit of this screen ran during either bench, everything ran
  `nice -n 19` single-threaded on a 14-core box at load ≈ 3–4, and all three nets were
  timed back-to-back inside one process under identical conditions — so the RATIO the gate
  reads is matched even where the absolute milliseconds are inflated. The two replicates
  (5.96× pre-block, 6.52× post-block) bound the contention effect empirically.
- **The fits ran beside that same FP arm.** Never touched, never paused; every fit
  `nice -n 19`, single-threaded, **one at a time, never two concurrently**.
- **`value_sizes` deviates from the W base** ([384,384] rather than W's [1024,1024]).
  Stated in the config header and in `scripts/train_bc.py`. Inert here: the critic is
  untrained at `--value-coef 0`.
- **One deviation from ARCH_SCREEN_SPEC's sketch:** the spec also required Δval_kl ≤ −0.02
  ("both metrics must move"). This screen gates on agreement_free alone and reports Δval_kl
  with its own CI beside it — including, in §7, that the stricter variant would also not
  have cleared. Nothing is hidden by the choice.
- **The spec was written for the 807-dim v2 obs**; today's trunk runs at OBS_DIM 828
  (v2 + the 20-float id tail). Token widths therefore differ from the spec's text (field 6
  not 5, mon token 50, move token 46), and `EntityTokenizer` — shared with arm A, not a
  re-derived offset table — is what slices them.
- **Test suite at the close:** 1,209 passed, 111 skipped, 9 deselected (`live_server`),
  **6 failed** — `test_ch5_100m_offfp_prereg`, `test_ch5_r2_prereg` (×2), `test_ladder`,
  `test_priveval_smoke_config`, `test_tie_and_stall_audit`. All six read `data/`, `runs/`
  or `results/`, which are gitignored and exist only in the main tree; **all six pass at
  HEAD in the main checkout.** They are worktree artefacts, not regressions.
- **New gates this screen added:** `tests/test_entity_attention.py` (param count pinned at
  564,875, shapes at 828, pointer alignment plus a token-mixing check, the two-faced init
  hazard, the `Config → make_agent → state_dict` round trip **and** the
  `eval_checkpoint`-path rebuild, and that the default MLP path of PPOAgent and train_bc is
  byte-identical) and `tests/test_arch_screen_readout.py` (the bootstrap clusters by
  battle, keeps the pairing, counts a twice-drawn battle twice, averages rather than pools
  the three seeds; `_load`'s cross-check raises in both directions; and the readout's
  restated rule constants still match the committed pre-reg).

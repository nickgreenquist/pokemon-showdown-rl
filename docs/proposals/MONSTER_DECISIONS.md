# The monster: four decisions, with the evidence each turns on

Written 2026-09-11 (night) after two independent design reviews of the three
arms, the design-B smoke finishing, and the margin gate's out-of-sample read
landing. **Nothing here is ratified.** The pre-reg
(`configs/showdown_monster100m.prereg.yaml`) writes every branch out and
refuses to pick a default: an unanswered decision is `M-UNRATIFIED` and the
fleet does not launch.

Read this with `STATUS.md`. The short version: **two of the three arms are not
what they were believed to be when the three-arm shape was ruled**, and the
axis the fleet was going to be graded on is one its own predecessor
pre-registered as a near-certain null.

---

## D1 — Does arm B ride arm A's lanes? **Recommend: YES.**

**This is not a judgement call; it is arithmetic.** The design-B smoke ran to
its 12M target and its checkpoints were compared against its priv-off twin at
the same seed:

| | |
|---|---|
| shared checkpoint rungs, identical filenames | **24** |
| final rung | `ckpt_012000017.pt`, same step on both |
| shared tensors / elements | **223 / 3,428,015** |
| **bitwise different** | **0** |
| sha256 of the shared blob | `f156f232462e635b` on both sides |

The head takes a separate `autograd.grad` over its own parameters after the
clip is read, and its construction rewinds the global RNG, so the actor, the
critic, the aux head and every minibatch permutation are identical. Arm B *is*
arm A, plus a rider that feeds nothing.

So three of the nine planned lanes were buying **duplicate checkpoints**. Turn
`priv_eval_coef` on in arm A's own three lanes and you get both arms. The only
cost is wall (the head is a second wide value net, ~+56% trainable params, all
update-side).

**If you say no**, you spend ~11–13 h of fleet reproducing checkpoints you
already have, and the A-vs-B greedy contrast you get is not "null by design" —
it is the same number, to the bit.

**What the freed lanes should buy:** seeds. The governing band is
seed-clustered, and three lanes make exactly one ensemble committee — which is
the precise limitation LADDER R1's object carried. Six seeds give two disjoint
committees and a real σ_seed, which every future bar depends on and which is
currently uncertain over a factor of ten (0.006 to 0.0617).

---

## D2 — Arm C: keep, re-specify, or drop? **Recommend: re-specify or drop.**

Both reviews contested it independently. The substance:

- It is **D18's exact lever** — `privileged_dim: 408` at `gae_lambda: 0.95` —
  but the vacatur that revived it named the **λ=1.0 pure-baseline** variant as
  the live hypothesis, on the grounds that the untested channel is variance
  reduction, not information.
- That channel has **~30× less headroom here than where it died**: D18's
  update was 1,024 steps, the monster's is 30,720. A variance-reducing
  baseline has less to do at a larger batch, not more. The pre-reg must argue
  this explicitly or it has not stated a mechanism.
- Its falsifier conditions on an **"uncollapsed critic"** — a quantity that
  has never exceeded 25/384 on any lane at any dose. As written the falsifier
  cannot fire and the arm returns no cell, which is the unnamed-cell failure
  the five pre-reg rules forbid. The drafted pre-reg already rebuilt this as an
  exhaustive 3×2 partition with srank demoted from gate to reported axis.
- It is **not init-paired with A** (privileged_dim re-rolls the actor at a
  fixed seed: param sum 442.300 → 375.635 at identical param count), so the
  A-vs-C contrast cannot share a se with A-vs-B and neither may use a paired one.
- **It has never run on this route at all.** `privileged_dim` has never run on
  the engine route, and `privileged_dim + aux_oppact_coef` has never run
  anywhere (D18 predates D25). PRE-2 makes a live smoke a hard precondition.

Per the 2026-09-06 ruling, **"kill" is barred for this arm** — a small-run null
closes nothing, only a measured ceiling kills. So the honest outcomes are
"null" and "credited negative", and the pre-reg says so.

**You ruled "11-15 extra hours is worth it. add it", and that ruling stands
until you change it** — this is the argument you asked for when you asked how
it could hurt, not a refusal to run it.

---

## D3 — Primary axis: vs-SH, or off-FP@20? **Recommend: promote off-FP@20.**

**vs-SH at p≈0.789 is saturated, and R4's own pre-reg said so before this
fleet existed** (`configs/showdown_sp_100m.yaml:141-145`, `:205-213`): at a
matched logit gain of 0.10, P(credit) is **0.488 off-FP against 0.067 vs-SH**.
Reproduced: +0.025 absolute costs +0.1571 logit at 0.789 against +0.1001 at
0.498 — **1.57×**.

The fresh comparator is 0.78867, so credit needs **≥ 0.81367** — above every
number this project's *training* runs have produced on that axis, and Foul
Play's own anchor is 0.8307. The axis is also measurably flat: doubling 50M →
100M moved vs-SH **+0.0094** while moving off-FP@20 **+0.02389**.

**If you keep vs-SH as primary**, the header must print `P(credit) ≈ 0.07 at a
+0.10-logit lever` verbatim, so the fleet's likely null is pre-registered as
expected rather than discovered afterwards.

---

## D4 — Read each arm at its own δ, not at arm A's. **Recommend: yes.**

The margin gate's δ is a function of evaluator noise: a lower-variance
evaluator should want a *smaller* δ. The repo already wrote this down for the
compute axis (`configs/eval/search_budget_ladder.yaml`: "DELTA IS HELD FIXED
ACROSS RUNGS … **This biases AGAINST the expensive rungs**"). Across evaluator
arms it binds harder, and **the bias runs against the treatment**.

It matters because the δ curve is steep exactly where it is read — and because
selection on δ is worth more than the effect itself:

| δ | 0 | 0.02 | 0.05 | **0.10** | 0.15 | 0.20 | inf |
|---|---|---|---|---|---|---|---|
| s112 win rate | 0.74767 | 0.78200 | 0.80867 | **0.82400** | 0.81400 | 0.81000 | 0.78233 |

**s112's +0.0417 is in-sample — δ was chosen there.** Out of sample it is
**+0.01600** (s104 +0.01967, s120 +0.01233, pooled n=6000, 2.19 se_diff):
**meets 2·se_diff, misses the +0.025 floor, NOT CREDITED.** Selection shrank
the effect 2.6×. A fixed-δ read across arms is not a valid evaluator
comparison and should not be registered as one.

---

## What is running tonight that bears on this

- **EG10** — the LOO ensemble evaluator *with* the working gate, three lanes,
  n=3000. A1E's +0.0163 was a D4 number and is `PRE-D5` by our own landmine, so
  the evaluator axis is **unanswered, not answered no** — and it is arm B's
  premise. If a strictly better evaluator buys nothing once the selector works,
  that is worth knowing before 45 h of fleet.
- **ENS3** — the 3-seed log-prob ensemble on the 100M finals, n=9000. The only
  free-compute dial this project has ever credited (+0.036, B1), LADDER R1's
  actual object, and never once run at 100M.
- **BLM** — the pre-decided Foul Play transfer branch for the gate.

## Cost, corrected

STATUS's "~40 h, +11–15 h" presumed nine-wide. **Nine-wide is refused on
memory** (16.4 GB measured non-growing against 11–13 GB idle headroom on 24
GB, before the Node path's 1.39× growth). Measured: wave 1 at w6 (25.3 h) plus
wave 2 at w3 (20.0 h) = **~45.3 h**. Waves are cut **by seed, never by arm** —
a wave cut by arm confounds arm with box.

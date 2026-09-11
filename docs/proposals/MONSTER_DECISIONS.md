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

- **EG10 — DONE. A better evaluator adds nothing AT DEPTH-1, DOSE M, delta 0.10.**
  LOO ensemble evaluator + the SAME gate vs the gated-plain arm, 3x3000 each:
  **0.81278 vs 0.81322 = −0.00044, se_diff 0.00812** (0.05 se — a flat null;
  the cell prints NEG only via the 2-of-3 direction rule). Dose matched.
  **This is the cheapest possible test of arm B's premise and it came back
  null for ~2 h of box instead of 45 h of fleet.** It does NOT kill a
  PRIVILEGED evaluator — that carries information a LOO ensemble of our own
  critics does not — but it removes the reason to *buy* one at dedicated lanes,
  and D1 already makes arm B free. Combined, the honest position is: let the
  head ride arm A's lanes as a rider, read it offline, and spend nothing on it.
- **ENS3 — DONE, AND IT CREDITS.** 0.82356 (n=9000) vs fresh greedy 0.78867,
  **+0.03489 at 5.93 se**, meeting both the floor and 2*se_diff. It beats the
  gated search's IN-SAMPLE peak at greedy speed. **This changes the ladder-object
  question**: the object to beat is no longer single-seed greedy, it is the
  ensemble. Disclosures travel — clustered se UNAVAILABLE (one committee), and
  it licenses "ensembling THESE three checkpoints", never "ensembling helps".
- **BLM — DONE, branch FIRED: TRANSFERS.** 0.525 vs FP@20 (n=1000) against a
  0.47 bar, with banked greedy 0.50167 and UNGATED search 0.39600 on the same
  lane. **The selector alone bought +0.129 off-FP.** The gate is not an
  SH-facing artifact. (The +0.023 over greedy is 1.28 se — not significant; the
  branch tested SH-facing-ness, not superiority.) Stage 2 auto-launched.

## Cost, corrected

STATUS's "~40 h, +11–15 h" presumed nine-wide. **Nine-wide is refused on
memory** (16.4 GB measured non-growing against 11–13 GB idle headroom on 24
GB, before the Node path's 1.39× growth). Measured: wave 1 at w6 (25.3 h) plus
wave 2 at w3 (20.0 h) = **~45.3 h**. Waves are cut **by seed, never by arm** —
a wave cut by arm confounds arm with box.

---

## The next experiment, now buildable

`rl/search/ensemble_search.py` (committed tonight, tested, **not wired**) lets a
`SearchAgent` take an ensemble as its **prior and leaf value**, which was
previously impossible — `EnsembleAgent` exposes none of the three surfaces
`SearchAgent` consumes, which is why `ch3_eval.py` could build an ensemble OR a
search but never both.

That composition is the top untested lever on the evidence:

| lever | measured | cost |
|---|---|---|
| ensemble as PRIOR (ENS3) | **+0.038** on batch 1 of 3 | greedy speed |
| D5 margin gate (out of sample) | +0.016 | 77.6 ms/decision |
| gate, off Foul Play | **+0.129 vs ungated**, TRANSFERS | same |

They are structurally orthogonal — the ensemble moves the prior and the leaf
value, the gate moves the selector — and **neither has ever been measured in
the presence of the other.** Wiring is three lines in `ch3_eval.py`, held back
only because the EG10 verdict arm's queue relaunches on failure and a resumed
arm must not run different code than its finished chunks.

**It is deliberately NOT pre-registered yet.** ENS3 and EG10 are still running,
and a pre-reg written tonight would be written by someone who has seen one
batch of ENS3 and none of EG10. The honest sequence is: read those two out,
then register the composition against whichever object wins.


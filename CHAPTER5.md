# CHAPTER 5 — from "one ladder number" to "a better model on the ladder"

**STATUS — REWRITTEN 2026-08-28. The shape is still RATIFIED (maintainer,
2026-08-26 — §7 carries the rulings verbatim), but the rest of the old
status block is wrong and is quoted below rather than deleted.**

- **R1's pre-registration EXISTS and had the 2-Opus cycle**:
  `configs/eval/ch5_r1_offsh.yaml`, designed 2026-08-26 (2 Opus designers,
  candidate set not conclusion), now at amendment **r10**; amendment r9
  ran the full cycle again (two design memos, two independent reviews).
- **R1 LAUNCHED, RAN AND IS CLOSED**: ten graded arms, **zero voids**, G2
  exact on every one. Publishable number: search@M on s80 off Foul
  Play@20, **0.4390** at n=3000.
- **CHAPTER R3 — ladder run #2 — RAN, AHEAD OF R2**: 2026-08-28, n=200,
  **GXE 60.3%, Glicko-1 1579 ± 25, Elo 1232**, on search@M over the 50M
  lane s80. See `readouts/LADDER_R3_READOUT.md` and `configs/eval/ladder_r3.yaml`.
- **Still true: NOTHING HAS BEEN TRAINED IN THIS CHAPTER.** R1 was
  eval-only against existing checkpoints and R3 was a ladder run; **R2 is
  the training round and its pre-registration is not written.** That, not
  R1's, is what still owes the next design cycle.

> SUPERSEDED TEXT, kept so the error is visible rather than silently
> overwritten: *"The IMPLEMENTING PRE-REGISTRATIONS ARE NOT WRITTEN and
> still owe the 2-Opus cycle (§8). Nothing launched, nothing trained."*

Written 2026-08-26 after the maintainer challenged this session's "scale
is flat / nothing here reaches the cutoff" framing and the challenge held
on every count checked.

**HARD CEILING, ruled 2026-08-26: 50M IS THE LARGEST RUN IN THIS CHAPTER.**
No 100M, no 120M, no 250M. See §7.4 for the reasoning, which also makes
the old §7.3 moot.

**WHAT THIS FILE IS:** the chapter decision document, in the role
`DESIGN2.md` played for Chapter 2 — and, deliberately, **the evidence
brief that the standing 2-Opus-designers-plus-reviews cycle should
consume.** It is NOT the output of that cycle. Its candidate ranking is
one assistant's, formed in one session, and the sequencing in §4 is
exactly the kind of call the two-designer process exists to attack. Read
§8 before treating any of it as settled.

**WHAT THIS FILE IS NOT:** `DESIGN.md` is HISTORICAL/SPENT and must not be
extended as a roadmap (CLAUDE.md, Docs). `DESIGN2.md` is Chapter 2 and is
spent. This file supersedes neither; it starts a new chapter. Per the
repo's lifecycle, each pre-registration below migrates into its config
header and **this file is deleted once fully migrated.**

---

## §1 — The end goal, stated once

**LADDER RUN #2, with a model that is actually better than L2.** Every
scripted opponent in this project is a proxy for that. Chapter 5 exists to
turn the six candidate levers below into one deployable model and put it
back on the real board.

Two things make R2 worth more than a repeat of R1:

1. **It is the first strength claim this project can make against humans.**
   R1 established the harness and a level (final Elo 1292, GXE 59.6%,
   Glicko-1 1573 +/- 27; the long-quoted 1311 was the PRE-BATTLE rating of
   the last game). R2 is the delta.
2. **It creates the FIRST (proxy score, ladder rating) pair — not the
   second.** CORRECTED 2026-08-26 by designer A, verified: **L2 has no Foul
   Play number at ANY budget** (`ladder_r1.yaml` line 42 says `unmeasured`
   against both off-SH anchors). The one policy with a ladder rating has no
   proxy score, so the repo holds **ZERO complete pairs**, not one. This
   raises R1-C from "nice to have" to the arm that makes the pairing
   possible at all.

   > **OVERTAKEN BY EVENTS, 2026-08-28 — the "ZERO complete pairs" count is
   > no longer true, and R1 is what closed it.** Arm C0 measured L2 itself
   > off Foul Play@20 at n=3000: **0.3893**. That plus R1's ladder read
   > makes **(0.3893 off FP@20, GXE 59.6%) a complete pair** — the first.
   > Chapter R3 then made a second: its object, search@M on s80, scores
   > **0.4390** off FP@20 at n=3000 (arm RS80) and read **GXE 60.3%** on
   > the board. **So the repo holds TWO complete pairs, not zero.** The
   > paragraph above is kept because it is the reasoning that made R1-C
   > look load-bearing, and because C0 — not R1-C — is what actually
   > delivered the pairing.
   >
   > **What does NOT follow from two pairs:** the two are on different
   > objects, different accounts and different opponent pools, and ruling
   > D5 (`configs/eval/ladder_r3.yaml`) bars presenting any arithmetic
   > difference between R1's and R3's ladder numbers as a quantity, in
   > either direction. Two pairs are two points, not a slope.

**Honest limit, pre-stated:** one pair does not validate a proxy, and two
barely begin to. It gives the first datapoint that could *falsify* one. Do
not oversell it in the readout. *(That limit is now live rather than
hypothetical — the two pairs exist and the sentence applies to them.)*

---

## §2 — Where we actually are, on BOTH axes

*Off-FP and ladder cells UPDATED 2026-08-28 — CH5 R1 and chapter R3 filled
four of the cells this table wrote as `unmeasured` / `—`, and added a row
for R3's actual object. Every new value below is measured, not projected;
the cells still blank are still genuinely unmeasured.*

| | vs SH | off FP | ladder |
|---|---|---|---|
| D26 12M greedy (s62-65) | **0.71825** | **0.34867** @20, n=12,000 | — |
| D26 12M, 4-lane ensemble (L2) | 0.74633 | ~~unmeasured~~ **0.3893** @20, n=3000 (R1 arm C0) | **GXE 59.6%**, Glicko-1 1573+/-27, Elo 1292, 0.475, n=200 |
| D26 12M + search@M (L3) | 0.79283 | 0.368 @100, **n=250** | — (never laddered; the ladder ran search on the **50M** lane, next row but one) |
| D29r2 stack @ 50M (s80/81/82), **greedy** | 0.70222 | ~~unmeasured~~ **0.3960 / 0.3430 / 0.2730** @20, n=1000 each (R1 arms A80/A81/A82) | — |
| D29r2 s80 + search@M — **chapter R3's object** | unmeasured (no vs-SH at the locked protocol for search on any 50M lane) | **0.4390** @20, n=3000 (arm RS80) | **GXE 60.3%**, Glicko-1 1579+/-25, Elo 1232, 106-94, n=200 |
| struct 12M (earlier era) | 0.5509 | 0.176 @100, n=250 | — |
| struct 50M (earlier era) | 0.5802 | 0.188 @100, n=250 | — |

**Two rules travel with the two ladder cells.** They are DESCRIPTIVE — a
ladder run credits no lever here — and **no arithmetic difference between
them may be presented as a quantity, in either direction** (ruling D5,
`configs/eval/ladder_r3.yaml`): different objects, different accounts,
different opponent pools. R3's object also carries **one of three anchors
(FP@20 only)**.

**Three things this table says that the project has been quoting wrong.**

1. ~~**"Scale is flat" is a vs-SH-only claim.** No D29r2 lane has any
   off-SH number.~~ **ANSWERED 2026-08-28 by R1-A, and the sentence above
   is only history now.** All three D29r2 lanes were measured off FP@20 at
   n=1000 each — **0.3960 / 0.3430 / 0.2730** — against the 12M greedy
   comparator's 0.34867. **R1-A read WITHIN × NON-RESOLVING** (§5's
   post-hoc block): 50M is not materially above or below 12M off-FP, and
   the fleet's seed spread is what makes the read non-resolving rather
   than any point estimate. The pre-R1 evidence, kept for provenance: the
   one 50M arm then measured off-FP read **+0.012** over its 12M sibling
   (n=250 each, se_diff 0.035 — n.s., positive sign) while the same step
   read +0.029 vs SH and CREDITED.
2. **"Flat" is also a variance statement.** D29r2's lanes are 0.74233 /
   0.73467 / **0.62967**. Two of three 50M lanes BEAT the 12M pooled
   headline of 0.71825; one lane 0.10 low drags the mean. The pre-declared
   5-lane read says it in terms: "one lane in five landing ~0.10 low."
3. **"Search is worse off-SH" rests on n=250 per side.** fg 97/250 =
   0.388 vs fs 92/250 = 0.368: delta **-0.020, se_diff 0.043** — 0.46 se,
   inside noise. The stronger half of that case is the clone (-0.034 +/-
   0.021) and MU-8's pooled z = -2.80, NOT the FP cell. Quote it that way.

**And the numbers are not budget-commensurable.** 0.388 (greedy, FP@100,
n=250, one lane) vs 0.34867 (greedy, FP@20, n=12,000, four lanes) differ
in the direction FP@20's licence does NOT predict — FP@20 is the
*marginally weaker* opponent. The reconciliation is n: the 0.388 is a
small single-lane read. **Nothing in Chapter 5 may compare across FP
budgets without naming both.**

---

## §3 — The six candidates

**PROVENANCE, and it is load-bearing (maintainer, 2026-08-26: "you can try
things you thought up. just dont lose track of what i proposed").**

| | source | status |
|---|---|---|
| C1 longer run · C2 seeds/ensemble · C3 larger arch · C4 attention · C5 search-on-better-net · C6 encoder fix | **MAINTAINER** | **first-class. None may be dropped, deferred or merged away without an explicit maintainer ruling recorded here.** |
| H&L shaping (§7.5) · both-seat harvest (§3b) · temporal context (§3b) · **episodes/update (§3b A4)** | assistant | additions, licensed 2026-08-26. They COMPETE with the six; they never displace one. |

Raised by the maintainer 2026-08-26. Each gets: the claim, what supports
it, what argues against, cost, and what would settle it.

### C1 — Longer run, and enough eval to prove "stalled"
**CAPPED AT 50M by the 2026-08-26 ruling (§7.4), and the two 50M fleets we
need are already trained — so C1's first move is a MEASUREMENT, not a run.**
- **For:** the flat verdict is one arm on one opponent at one era (§2.1).
  H&L's comparable ran ~19x our 12M in learner-consumed terms.
- **Against:** the 2026-08-23 big-run ruling reserves 120/250M for polish or
  a visibly climbing log. **NOT against: "D29r2 pooled -0.016 vs SH".
  CORRECTED 2026-08-26 (designer A, verified independently) — that is not a
  weak claim, it is NOT A CLAIM.** The 50M lanes read 0.7423/0.7347/0.6297,
  giving sigma_seed = **0.0624**, 8.2x the 12M family's 0.0076. Clustered
  se_diff is then 0.0362 and the delta is **0.44 se** against a 2-se bar of
  0.0735 (r1 said 0.0724, from sigma_seed; the Q5-consistent value uses the TOTAL sd). The one lane at 0.6297 inflates the variance so far that nothing
  at this k is resolvable. **"Scale is flat" was never established even on
  its own axis** — a stronger correction than this file's earlier
  "it is a vs-SH-only claim".
- **Cost:** zero, if R1-A answers it — s80/81/82 exist. A *new* 50M fleet
  is ~37.4 h wall / ~4.6 lane-days. Past 50M: out of chapter.
- **Settles it:** R1-A first. **A longer run should not be bought before
  the 50M checkpoints we already own are measured off-SH.**

### C2 — More seeds; wider ensemble
- **For:** strongest of the six on existing evidence. The 0.630-0.742
  spread means seed count is a real lever on the MAX, not just the mean.
  Six trained checkpoints (3x D29r2 50M, 3x struct50m) sit idle while the
  ensemble uses four.
- **Against:** ensembling is inference cost per decision; the ladder does
  not care (we use 6.74 ms of an effectively unlimited budget).
- **Cost:** wider ensemble = **zero training**. More seeds = ~9.8 h/lane.
- **Note that makes it legitimate:** selecting the best lane to DEPLOY is
  not post-hoc selection on a credit claim. The repo's anti-post-hoc rules
  govern credit; which checkpoint we ship is a deployment decision.

### C3 — Larger architecture
- **For:** completeness; untested at this recipe.
- **Against:** the only candidate the ledger argues against directly —
  privileged critic -0.0145, ~88% of D26 critic rank idle, the biggest
  credited win (+0.1513) came at *reduced* params, and H&L reached 72% GXE
  at 1.33M to our 1.17M.
- **Cost:** build + full retrain.
- **Settles it:** hold until R1-A. Capacity is ruled; **structure is not.**

### C4 — Attention / transformer, graded off-SH this time
- **For:** never trained. The 34.6x kill was a CPU train step **against the
  flat [512,512] MLP**, which has not been production since Rung 2 —
  attention-vs-`entity_deepsets` has NEVER been measured, and that is
  minutes of work.
- **Against:** the 2026-08-25 architecture review named **temporal
  context** the sharper structural gap (we are single-snapshot Markov;
  ps-ppo 64-256 turns, Metamon 200) plus an untried two-tower/DCN middle
  rung. If a structure budget exists, those may outrank attention.
- **Cost:** re-benchmark = minutes. Build + train = a chapter of its own.
- **Settles it:** run the benchmark now; it is free and it either reopens
  the lever or closes it properly instead of on a stale ratio.

### C5 — Search, on a better-trained network
- **For:** cheapest of the six. Search is INFERENCE-ONLY, has only ever run
  on `recipe12m_s62..s65`, and the 50M checkpoints are on disk. The
  hypothesis "search failed because the leaf evaluator was not saturated"
  is coherent and has never been tested. And its off-FP evidence is n=250
  per side (§2.3).
- **Against:** MU-8's pooled transfer test is z = -2.80; battles run ~40%
  longer (38.5 vs 27.6 mean turns), which costs ladder games per hour.
- **Cost:** zero training. Battle time only.

### C6 — Fixed-damage encoder fix
- **For:** real and measured. `seismictoss / superfang / nightshade /
  dragonrage / sonicboom` get `basePower == 1`, so `_fill_move` writes 0.01
  where Thunderbolt gets 0.95. Super Fang 0/59 for us vs 36% for humans;
  Seismic Toss 0.141 vs 0.289 (z = -3.39).
- **Against:** `move_emb` is a learned `nn.Embedding(166, 64)` in every
  move token, so the block is *misleading*, not unrepresentable — a partial
  route-around. Touches ~1% of decisions.
- **Cost:** fork + full retrain, and **it invalidates every checkpoint.**
- **Sequencing:** LAST. Doing it earlier destroys the baselines everything
  else is graded against.

### §3b — Assistant additions (licensed 2026-08-26, SUBORDINATE to the six)

These compete for R2's slot in §5's second row. None displaces a C-item.

- **A1 — H&L dense zero-sum shaping** (`hl_shaping: 1.0` + `gamma: 0.95`).
  Never tested on the entity trunk: `hl_shaping` is non-zero in exactly
  three runs on disk, all `trunk: mlp`, and every entity-trunk run is gamma
  1.0 / no shaping. It nulled on the flat MLP (+0.0135 n.s.). POST-HOC —
  DESIGN's result-blind carry-forward was to SCALE, not to a new trunk at
  12M. Cost: one overnight, zero code, no checkpoint invalidation. ~1 in 4.
- **A2 — both-seat harvest.** We buffer agent1's transitions only; the
  opponent seat is a `PoolPlayer` whose trajectory is discarded. H&L
  consume both, and their per-battle batches are RETURN-BALANCED by
  construction (one winner + one loser), which removes batch-level outcome
  noise. **That is a variance property, not a data-volume one, so
  50M-flat does not speak to it** — and gen 1 is unusually luck-heavy
  (freeze, para, crits, 1/256). Needs real collection wiring.
- **A4 — EPISODES PER UPDATE (batch size). LICENSED 2026-08-26 by the
  maintainer, on the same footing as A1-A3: it COMPETES for R2's slot and
  displaces no C-item.** Verified off H&L's committed run config in our own
  metagrok clone (`expts/01.json`: `num_iters 500`, `num_matches 7680`,
  both seats harvested), so **one H&L update consumes 15,360 episodes
  against our ~34** — rollout 128 x 8 envs = 1024 steps at ~30
  decisions/episode. **~450x, with the regimes INVERTED**: 500 enormous
  updates against our ~48.8k tiny ones at 50M.
  **WHY IT IS NOT THE ~40x ALREADY LOGGED (2026-08-08).** That figure, and
  the **"~30 -> 100-300 episodes/update" target** it produced, were
  calibrated against **Wang (~1,600) and ps-ppo (~1,500)** — and
  `prior_work/README.md` argues at length that those are NOT our comparable
  because both use human data. **H&L is**: the only pure-self-play randbats
  success on record, our exact lane. **Against the right reference the
  recorded target is 50-150x too low.**
  **THE DOSE IS BOUNDED BY THE 50M CEILING, AND THAT IS THE USEFUL PART.**
  H&L bought their batch with 3.84M matches; we are capped at 50M steps. At
  ~30 decisions/episode, copying their 15,360 leaves **109 updates**, and
  PPO from random init will not learn in 109. **~1,000 episodes/update is
  the reachable dose: ~1,630 updates, still 3x more updates than H&L used
  at all (500), and ~30x of the gap closed.** Mechanically `rollout_steps
  128 -> ~3840` at `num_envs 8`; nearly free in wall-clock (same collection,
  FEWER optimizer passes), ~100 MB more buffer, `minibatches: 4` held so
  minibatches land at ~7,680 — near H&L's own `vbatch_size 8192`.
  **COST: the control is already trained.** s80/81/82 are a banked 3-seed
  50M fleet on the current recipe, so only the treatment fleet is bought:
  ~37.4 h wall as 3 concurrent lanes (~4.6 lane-days). Held seeds 66/67,
  75/76, 83/84, 93/94 are available and MUST be distinct across lanes.
  **AGAINST, and it is not small: at fixed total steps this trades update
  COUNT for update QUALITY, and nothing in this repo has measured which
  side binds.** It is UNTESTED here — a candidate, not a finding. H&L's
  `gamma 0.95` + dense shaping + return-balanced both-seat batches are
  COUPLED; copying batch size alone is the clean test, copying the recipe
  piecemeal is not. **A2 (both-seat harvest) is the first free 2x** of this
  same quantity at identical simulation cost, which makes A2+A4 natural
  companions and A2 the obvious dose-matched placebo.
  **SEQUENCING, RULED 2026-08-26: R1 FIRST, AND NOT CONCURRENTLY.** Two
  reasons, neither of them discipline. (i) R1's wave is serial k=1 because
  FP is TIME-BUDGETED — a training lane stealing CPU inflates FP's
  effective thinking budget and flatters our numbers; that is a
  wave-scoped VOID. (ii) **R1-A PRICES R2**: whether one new 50M lane is
  readable depends on the fleet's OFF-FP seed spread, which R1-A measures.
  The 12M fleet's sigma_seed is 0.0076 vs SH but 0 off-FP; if the 50M fleet
  tightens the same way R2 is 1 lane, and if it looks like its vs-SH 0.0624
  it is 3.
- **A3 — temporal context.** We are single-snapshot Markov; ps-ppo uses
  64-256 turns, Metamon 200. Named by the 2026-08-25 architecture review as
  a SHARPER structural gap than attention. Spec exists at
  `prior_work/HISTORY_FEATURES_DESIGN.md` (unread this session). Changes
  OBS_DIM, so it inherits C6's invalidation problem and its sequencing.

---

## §4 — Proposed shape: R1 (free) -> R2 (train) -> R3 (ladder)

### R1 — the instrument, and three reads that cost NO training
One build unlocks all three. **This is the gate on the whole chapter.**

**BUILD (the off-SH seat).** Two independent blockers, both verified:
(a) `ch3_fp_h2h.py`'s `ARM_KINDS = (greedy_seat, search_seat, sampled_seat,
fp_vs_clone)` asserts on anything else, and L2 is `kind: ensemble` from
`ladder.py`'s separate `POLICY_KINDS` namespace — there is no ensemble seat
in the FP path at all. (b) `eval_checkpoint._opponent_from_checkpoint`
seats the opponent in a **PoolPlayer that SAMPLES** by contract, which
reproduces the A1 bias (~26 points of implied rating). `SeatPlayer` is the
deterministic one and is the right home.

**READS.** All vs FP@20, both disclosures travelling per CLAUDE.md.
- **R1-A — the 50M lanes s80/81/82 off-SH.** Comparator: the 12M lanes'
  0.34867 (n=12,000). ~1 h/arm at 1.20 s/battle x 3000. **This is the read
  that adjudicates C1 and C3.**
- **R1-B — search@M on the 50M checkpoints.** Adjudicates C5. **PRICED
  2026-08-26 (it was UNPRICED here, which is why the smoke went first).**
- **R1-C — a wider / cross-era ensemble.** Adjudicates C2's free half.
  Requires the ensemble seat from BUILD, so it is the seat's own smoke.

**R1 COST LEDGER — MEASURED 2026-08-26, not projected.** The seat was
smoked against real Foul Play at `--search-time-ms 20` through the hardened
runner (`ch3_r4_fp_runner.sh`), 0 relaunches, 0 crash-forfeits, 0
mask-desyncs, and **G2 satisfied on every run** (the seat's tally and Foul
Play's own `Winner:` lines agree exactly).

| seat | measured s/battle vs FP@20 | 3000 battles | x3 lanes |
|---|---|---|---|
| ensemble | **1.60** (marginal, startup stripped: (55.6-15.7)/(30-5)) | 1.33 h | **4.0 h** |
| search@M | **3.51** (n=20, startup NOT stripped -> slight over-estimate) | 2.92 h | **8.8 h** |

Reference points, CORRECTED 2026-08-26 (designer A, verified): CLAUDE.md's
1.20 s/battle is not what the banked arms actually cost — `l62..l65` realized
**1.44 / 1.53 / 1.51 / 1.46**. So the ensemble's 1.60 is only ~**7%** over a
realized greedy arm, not 33%. Search costs 73.6 ms/decision over 727/794
searched decisions and runs longer battles (35.6 vs 28.3 turns) — that is
its 2.2x.

**EXECUTION CONSTRAINT the ledger must respect:** the comparator arms ran
**strictly serial, k=1** (`results/ch4_r1_offsh/wave.log`: "WAVE START
serial k=1"). Running R1's arms concurrently is an execution difference the
comparator does not have; the pre-reg must either match it or pre-state why
concurrency is safe. These hour figures assume serial.

**CORRECTION TO §7.4's OWN BUDGET LINE.** It said R1 was "~4-6 h of
agent-side battles". At full power (3000 x 3 lanes on A and B, one arm on
C) R1 is **~14 h** — the estimate was low by ~2.5x, on the same axis CH4
R1's review caught a cost ledger wrong by 45%. **R1-B is the expensive
arm and the pre-reg must decide explicitly whether it runs at fewer lanes,
fewer battles, or full power** — and say which, rather than discovering
it mid-run.

**R1 is eval-only and credits no lever** — same footing as CH4 R1.

**R1 CAN ALREADY PRODUCE THE R3 MODEL.** R1-B and R1-C are deployment
candidates, not just diagnostics. If either beats L2 off-SH, ladder run #2
can launch **without retraining anything.** That is the single most
important structural fact about this chapter and it should survive any
redesign of it.

### R2 — one training arm, chosen by R1's branch table (§5)

### R3 — ladder run #2 — **EXECUTED 2026-08-28, ahead of R2**
Primary named in advance, one arm, its own pre-reg
(`configs/eval/ladder_r3.yaml`). **Do not pick the better of two ladder
numbers after the fact.** Result: **GXE 60.3%, Glicko-1 1579 ± 25, Elo
1232, 106-94 at n=200**, on search@M over the 50M lane s80
(`readouts/LADDER_R3_READOUT.md`).

> **RETRACTED 2026-08-28 — the "open question for the design cycle" below
> rested on a false premise, and the false premise is the interesting
> part.** It read: *"R1's stopping rule (`rd <= 40 AND n >= 200`) never
> fired because we were never listed — R3 needs a rule that can actually
> fire."*
>
> **R1's rule was SATISFIED**, at **rd 27, n 200**. Both readouts now
> record it that way. `stopped_by_rule: false` in
> `results/ladder/L2.report.json` is a **TOOLING ARTIFACT**: the runner
> read `rd` off the top-500 leaderboard JSON, which contains only listed
> accounts, so on an unlisted account it could not read `rd` at all and
> reported the rule as un-fired. The **user profile** carries GXE, Glicko
> and `rd` for any rated account, and always did. Fixed 2026-08-27; same
> root cause as the retracted "GXE is unmeasurable for unlisted accounts"
> claim (`readouts/LADDER_R1_READOUT.md` correction block).
>
> R3 needed no new rule. It ran under `rd <= 40 AND n >= 200` and the rule
> **fired on its own at rd 25.4, n 200** — the supervisor saw the exit and
> stopped.
>
> **What survives from the retracted paragraph, and it survives in a
> stronger form:** "n=200 cannot resolve a ~30-50 Elo difference between
> arms" was right, and ruling **D5** now goes further — **no arithmetic
> difference between R1's and R3's ladder numbers may be presented as a
> quantity, in either direction**, at any n, because the two runs differ in
> object, account and opponent pool. R3 is standalone descriptive.

---

## §5 — R2 branch table, pre-committed result-blind

Written 2026-08-26 before any R1 datum exists. Comparator throughout is
the 12M greedy 0.34867 off FP@20 (n=12,000).

**THE SIMPLIFICATION THAT FALLS OUT OF THE 50M CEILING:** if R1-A is
positive, **the better model is ALREADY ON DISK.** D29r2's s80/81/82 are
trained. A positive R1-A does not buy a longer run — it buys a *deployment
decision*, and R2 training becomes OPTIONAL rather than the point.

| R1-A reads | interpretation | action |
|---|---|---|
| 50M **materially above** 12M | scale is alive AND the model exists | **R3 uses the 50M lanes** (greedy or ensembled). R2 training is OPTIONAL — spend it on C2/C4 or skip it. **Anything past 50M is OUT OF CHAPTER** and needs its own pre-reg under the 2026-08-23 conditions |
| 50M **within noise** of 12M | scale genuinely flat on both axes | **C2** (more seeds) unless R1-C already delivered; then a structure lever, C4's benchmark deciding attention vs temporal context |
| 50M **materially below** 12M | scale actively hurts this recipe | **C2** — more 12M seeds + widest ensemble. Cheapest path to a better R3 model, and C1/C3 are closed for the chapter |

Independent of A:
- **R1-B positive off-FP** -> search returns as an R3 DEPLOYMENT lever
  (inference-only; it changes no training decision).
- **R1-C beats L2 off-FP** -> the R3 model is an ensemble regardless of
  what R2 does.
- **C6 (encoder fork) runs after R2 and before nothing** — it is the last
  training change of the chapter, for the checkpoint-invalidation reason.

**Unnamed cells are a known failure mode of this repo's pre-regs (R-4's
silent gap at (A1+0.02, A1+0.05]). "Materially" above MUST be given a
number in the ratified header, on the FP@20 scale, with the aggregator
named (median vs worst-lane changed a verdict once).**

> ### SUPERSEDED IN PART — 2026-08-28. READ THIS BEFORE ACTING ON THE TABLE.
>
> R1-A read **WITHIN x NON-RESOLVING**, so the table above routes to **C2
> (more seeds)**. **THAT ROUTING IS DEAD AS A ROUTE TO A CREDITED RESULT,
> and the reason is arithmetic that was not done when the table was
> written.** The realized R1-A bar is `2 * sigma_seed / sqrt(k)` — 0.0717 at
> sigma_seed 0.0617, k=3. Reaching the credit line's own **+0.025 floor**
> therefore needs **k >= 24 lanes**. k=6 buys 0.051, k=12 buys 0.036.
> **No realistic k reaches the threshold this project has committed to**, so
> buying seeds cannot credit a lever in the +0.02-0.05 band no matter how
> many are bought.
>
> Two consequences, both live:
> 1. **The only variance term that can still move is `sigma_seed` itself.**
>    **THIS DOES NOT MAKE BATCH THE INSTRUMENT FIX, AND AN EARLIER DRAFT OF
>    THIS NOTE SAID IT DID — CORRECTED 2026-08-28 03:10Z.** The argument
>    establishes that `sigma_seed` is the only remaining TARGET, not that we
>    can DETECT hitting it: comparing `sigma_seed` across two 3-lane groups is
>    an **F-test on (2,2) df, critical value 19.0**, so batch would have to cut
>    it **4.4x (0.0617 -> ~0.014)** before the comparison registers anything.
>    That is the same 2-df wall as k~24. **Batch is a STRENGTH lever** — bar
>    **0.1007** at k=3 (CORRECTED by r9, 2026-08-28: R2's control is
>    s80/81/82, so BOTH sides carry the clustered term — 2*sqrt(2*0.0617^2/3);
>    the 0.0717 was R1-A's bar against the near-zero-sd 12M fleet and
>    understates R2's by sqrt(2); s_batch halved gives 0.0797), plausibly
>    cleared by an 8x batch increase — and it is R2,
>    gated only by the s81/s82 rescore that fixes the policy form. Its
>    `sigma_seed` read is a DESCRIPTIVE SECONDARY carrying that disclosure, so
>    a null is never readable as "batch did not help variance".
> 2. **C2 is rehabilitated the moment the deliverable is a SCALING CURVE
>    rather than a credited win rate**, because resolving 12M vs 50M vs 250M
>    does not need +0.025 resolution and lanes shrink the error bar on every
>    point regardless of what causes sigma_seed. **That scoping call is now
>    the first decision of the next phase** — it is a POLICY change (it makes
>    120M/250M runs first-class, against the 2026-08-23 ruling limiting them
>    to ladder-ready polish or climbing logs), and it dissolves the owed
>    C2-vs-batch ruling rather than answering it.
>
> Also live and not in the table: **search may EQUALISE the lanes** (off
> FP@20 the search-minus-greedy gain is monotone in lane weakness, 3/3, and
> collapses a 0.123 spread to 0.026). If it holds, levers become measurable
> at k=3 with no new lanes — at the cost of a scope change, because the same
> mechanism that buys the variance masks value-head improvements. **2 df,
> p ~ 0.06, hypothesis not finding.** Full derivation, the case against it,
> and the revised 0-6 ordering: SESSION_LOGS 2026-08-28 (02:30Z).

---

## §6 — Explicitly out of scope, with reasons

- **A blunder / dominated-action filter at inference.** Measured dead
  2026-08-26: we make gross move errors at 0.6% vs the human field's 2.7%
  (1.88% vs 7.20% conditioned on having a known better move). Nothing to
  filter.
- **A second ladder arm run to DISCRIMINATE proxies.** Right idea, wrong
  power: R1's own trajectory swung 1063-1348 within one run, so n=200/arm
  cannot resolve ~30-50 Elo. Needs ~4x the n.
- **Compiling search into the weights.** KILLED by R5b (B5, 4/4 lanes
  non-positive).
- **Expert data, human replays, teacher distillation, ladder replays as
  training data.** The lane's purity constraint. Unchanged.

---

## §7 — Maintainer rulings, 2026-08-26 (all five closed)

1. **SHAPE RATIFIED** — R1 -> R2 -> R3 as written. ("ratify")
2. **R2's lever comes from §5's branch table**, not named in advance.
   ("sure")
3. **MOOT — dissolved by ruling 4, not decided.** It asked whether a
   positive R1-A could re-open the 2026-08-23 ruling that reserves
   120/250M runs for "polishing a ladder-ready model" or "a live run whose
   training logs are still clearly climbing." With 50M as the chapter
   ceiling, no run in Chapter 5 is large enough for that ruling to bind.
   It stays in force, untouched, and nothing here re-opens it.
4. **50M IS THE CEILING. 120-250M is overkill and is not proposed.**
   ("days at 100M is too much. we can start with a 50M run.") The reason
   is specific, not budgetary squeamishness: **we already own two 50M
   fleets (struct50m, D29r2) and have never measured either off-SH.**
   Extending a scaling curve whose existing points are unmeasured on the
   axis that decides things is backwards. Measure what is on disk first.
   Scale, for calibration only: 12M lane 9.8 h; 50M x3 lanes was 37.4 h
   wall / 4.6 lane-days; 250M x3 would be ~a week of the box — against
   H&L's comparable diet of roughly 230M in our currency, so the number is
   not absurd in principle, just unaffordable and unmotivated now.
   > *Note appended 2026-08-28, ruling text above left VERBATIM and
   > unaltered: its premise "we already own two 50M fleets and have never
   > measured either off-SH" was true when ruled and is now half-spent —
   > R1-A measured all three D29r2 lanes off FP@20 (0.3960 / 0.3430 /
   > 0.2730, n=1000 each). "Measure what is on disk first" was followed.
   > The ceiling itself is untouched and still binds.*
5. **Assistant additions are LICENSED but SUBORDINATE.** ("you can try
   things you thought up. just dont lose track of what i proposed") The
   provenance table in §3 is the enforcement: the maintainer's six are
   first-class and may not be dropped without an explicit ruling; H&L
   shaping (`hl_shaping: 1.0` + `gamma: 0.95`, never tested on the entity
   trunk, POST-HOC, its own author at ~1 in 4) competes in §5's second
   row and never leads.

~~**Still open, and the only thing blocking R1:** the pre-registrations that
implement this shape are not written, and they owe the 2-Opus cycle (§8).~~

**UNBLOCKED AND SUPERSEDED, 2026-08-28.** R1's pre-registration was written
(`configs/eval/ch5_r1_offsh.yaml`), had the 2-Opus cycle on 2026-08-26 (two
designers given the candidate set, not the ranking) and again at amendment
r9, and now stands at **r10**. **R1 ran and is CLOSED — ten graded arms,
zero voids, G2 exact on every one.** Chapter R3, the ladder run, has also
executed (n=200, GXE 60.3%). **What is still open is R2's pre-registration**
— the training round, and the only round in this chapter that trains
anything. It is what owes the next 2-Opus cycle; §8's disclosure below now
attaches to R2, not to R1.

---

## §8 — Process note, and a disclosure

**The standing process (maintainer, 2026-08-12) is 2 Opus designers plus
reviews for any pre-registration, lever design, protocol change or roadmap
choice. THIS FILE HAS NOT HAD IT.** It is one assistant's synthesis from
one session. Two specific things it should be attacked on:

1. **§3's ranking and §4's sequencing are the assistant's**, formed after
   proposing — and then retracting — a different round-1 lever the same
   session. Give the designers the candidate set, NOT this ranking, or the
   cycle ratifies a conclusion instead of testing it. That exact failure
   ("the synthesis hid the dispute") is on the record from the FP-gap
   cycle.
2. **§5's branch table is the load-bearing part** and is the part most
   likely to contain an unnamed cell.

**Disclosure:** the assistant's "none of these gets us the 46 Elo to the
top-500 cutoff" (same session) is WITHDRAWN. It generalised from a single
vs-SH arm and from style metrics that measure blunder rate rather than
strength.

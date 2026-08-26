# CHAPTER 5 — from "one ladder number" to "a better model on the ladder"

**STATUS: PROPOSED, NOT RATIFIED. Nothing launched, nothing trained, no
tranche authorised.** Written 2026-08-26 after the maintainer challenged
this session's "scale is flat / nothing here reaches the cutoff" framing
and the challenge held on every count checked.

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
   R1 established the harness and a level (Elo 1311). R2 is the delta.
2. **It creates the second (proxy score, ladder rating) pair.** With n=1 no
   proxy in this repo is validated against the only ground truth we have.
   With n=2 the question "does FP@20 predict ladder rating" becomes
   answerable at all. Recorded as motivation 2026-08-26; still true.

**Honest limit, pre-stated:** n=2 does not validate a proxy either. It
gives the first datapoint that could *falsify* one. Do not oversell it in
the readout.

---

## §2 — Where we actually are, on BOTH axes

| | vs SH | off FP | ladder |
|---|---|---|---|
| D26 12M greedy (s62-65) | **0.71825** | **0.34867** @20, n=12,000 | — |
| D26 12M, 4-lane ensemble (L2) | 0.74633 | **unmeasured** | **Elo 1311**, 0.475, n=200 |
| D26 12M + search@M (L3) | 0.79283 | 0.368 @100, **n=250** | — |
| D29r2 stack @ 50M (s80/81/82) | 0.70222 | **unmeasured** | — |
| struct 12M (earlier era) | 0.5509 | 0.176 @100, n=250 | — |
| struct 50M (earlier era) | 0.5802 | 0.188 @100, n=250 | — |

**Three things this table says that the project has been quoting wrong.**

1. **"Scale is flat" is a vs-SH-only claim.** No D29r2 lane has any off-SH
   number. The one 50M arm ever measured off-FP read **+0.012** over its
   12M sibling (n=250 each, se_diff 0.035 — n.s., but the sign is
   positive) while the same step read +0.029 vs SH and CREDITED.
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

Raised by the maintainer 2026-08-26. Each gets: the claim, what supports
it, what argues against, cost, and what would settle it.

### C1 — Longer run (100M+), and enough eval to prove "stalled"
- **For:** the flat verdict is one arm on one opponent at one era (§2.1).
  H&L's comparable ran ~19x our 12M in learner-consumed terms.
- **Against:** D29r2 pooled -0.016 vs SH is real as far as it goes; the
  2026-08-23 big-run ruling reserves 120/250M for polish or a visibly
  climbing log.
- **Cost:** 50M x 3 lanes was ~37.4 h wall / ~4.6 lane-days. 100M is
  roughly double.
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
- **R1-B — search@M on the 50M checkpoints.** Adjudicates C5. **Cost
  UNKNOWN: the search seat's s/battle against FP has never been measured.
  Smoke it and read s/battle against a completed FP@20 arm before
  projecting any ETA** (the S1 deadlock landmine: a wall-clock ETA is not
  progress).
- **R1-C — a wider / cross-era ensemble.** Adjudicates C2's free half.
  Requires the ensemble seat from BUILD, so it is the seat's own smoke.

**R1 is eval-only and credits no lever** — same footing as CH4 R1.

**R1 CAN ALREADY PRODUCE THE R3 MODEL.** R1-B and R1-C are deployment
candidates, not just diagnostics. If either beats L2 off-SH, ladder run #2
can launch **without retraining anything.** That is the single most
important structural fact about this chapter and it should survive any
redesign of it.

### R2 — one training arm, chosen by R1's branch table (§5)

### R3 — ladder run #2
Primary named in advance, one arm, its own pre-reg. **Do not pick the
better of two ladder numbers after the fact.** Open question for the
design cycle: R1's stopping rule (`rd <= 40 AND n >= 200`) never fired
because we were never listed — R3 needs a rule that can actually fire, and
n=200 cannot resolve a ~30-50 Elo difference between arms.

---

## §5 — R2 branch table, pre-committed result-blind

Written 2026-08-26 before any R1 datum exists. Comparator throughout is
the 12M greedy 0.34867 off FP@20 (n=12,000).

| R1-A reads | interpretation | R2 |
|---|---|---|
| 50M **materially above** 12M | scale is alive; the flat verdict was an SH artifact | **C1** — longer run. Re-opening the 120/250M policy is the MAINTAINER'S call; this cell only supplies the evidence the 2026-08-23 ruling asked for |
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

## §7 — Open decisions for the maintainer

1. **Ratify the shape** (R1 -> R2 -> R3) or reorder it.
2. **The R2 lever is NOT chosen here** — §5 chooses it from R1's result.
   Confirm that is acceptable, or name it now instead.
3. **C1 re-opens the 2026-08-23 big-run ruling** on one branch. That
   ruling is yours; §5 only supplies evidence to it.
4. **Budget.** R1 is ~1 evening of build + ~4-6 h of agent-side battles
   (R1-B unpriced until smoked). R2 is one overnight at 12M or several
   days at 100M. R3 is ~12-20 h of unattended laddering.
5. **H&L shaping** (`hl_shaping: 1.0` + `gamma: 0.95` on the entity trunk)
   is a live R2 candidate not listed in the six: never tested on this
   architecture — every entity-trunk run on disk is gamma 1.0 / no shaping
   — but its 12M-vs-scale framing makes it POST-HOC, and its own author
   puts it at ~1 in 4. It should compete in §5's second row, not lead.

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

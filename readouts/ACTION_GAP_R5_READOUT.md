# The action gap — how much is there for a top-2 swap to win?

`scripts/action_gap.py --battles 150 --rollouts 24`, the CLEANUP L9 FIXED version (top-2
ranked ONCE from the live observation and mask; `top1_is_played` self-check), run
2026-09-20 22:58–23:03Z under `scripts/exit_gate_queue.sh` at `39da8f8` on the R5
committee (the three W finals: s104 `ckpt_200000000`, s112 `ckpt_200000012`, s120
`ckpt_200000003`). `results/outcome_variance/action_gap.json` + `action_gap.rows.jsonl`
(134 rows); the companion reads from `scripts/action_gap_readout.py` →
`action_gap.rows.jsonl.readout.json`. Log `logs/exit_gate_r5/action_gap.log`. Hacking
run, **credits nothing**. RESULTS §33. IDEAS 2.15 / 8.1 / 8.2. CLEANUP L9 (closed).

## Why it was run

Four search constructions read null or negative on this object — the one-ply matrix
(§22), Foul Play's evaluator inside it (§23), an honest second ply (§30) and a decoupled
tree (§26) — and §30 measured greedy ABOVE every search arm at 2.4–4.4 se. CLAUDE.md
rule 6 says a null kills nothing; only a MEASURED MECHANISM CEILING does. This is the
ceiling: search can only improve on the policy by swapping its argmax for a better legal
action, so the prize of a gated search (argmax → runner-up, the form §24/§30 measure at
6–19% override) is

    P(top-1 worse than top-2) × E[Q(top-2) − Q(top-1) | worse]

and both factors are measurable by rollout with no evaluator and no search.

## What is measured, and against whose information

Each position is a decision the committee actually faced, held at OUR observation, at a
stop turn drawn uniformly from [2, 36). `top2_live` ranks the committee's masked
log-probabilities over the LEGAL actions once per position. Then, for each of 2
determinizations consistent with the observation, 24 rollouts per action under the SAME
deterministic committee on both seats (§27's instrument), so Q(a) is the true expected
outcome of playing `a` here and continuing as the committee would. The pre-L9 version
re-derived the pair per determinization from a privileged shadow battle; both defects
SHRANK the gap, i.e. biased the number toward the kill it would license.

**Validity gate: the top-1 equals the action the committee actually played in 134/134
positions (`top1_is_played_frac` 1.000).** 16 of the 150 battles produced no row (a
forced move or a finished battle at the stop turn); each row is a distinct battle.

## The result — 134 positions, 2 × 24 rollouts per action

| quantity | value |
|---|---|
| E[Q(top-1)] | +0.0237 |
| E[Q(top-2)] | −0.0145 |
| **E[gap]** | **+0.0383** (se 0.0197) |
| E\|gap\| | 0.1649 |
| top-1 worse / tie / better | 0.351 / 0.119 / 0.530 |
| E[−gap \| top-1 worse] | 0.1805 |
| **naive ceiling on a top-2 swap** (win-rate units = outcome / 2) | **0.0317**, bootstrap 95% [0.0220, 0.0426] |

## The winner's curse — the script said so before it ran, and here is the size of it

The ceiling is a conditional expectation over NOISY per-position gaps: conditioning on a
measured negative selects for negative noise, so noise alone prints a positive
"ceiling". The run summary's printed noise (0.204) assumes unit outcome variance; the
RECORDED per-action variances (~0.5 over 48 outcomes) give a per-row se on the gap of
0.148 independent / 0.146 paired (the pairing removes the shared-world component the two
actions' determinizations have in common). Everything below is from
`scripts/action_gap_readout.py` over the rows file.

| read | value |
|---|---|
| **noise-only ceiling** — every true gap zero, the recorded noise, same n | **0.0290** [0.0216, 0.0371] |
| measured variance of the gaps vs mean noise variance | 0.0521 vs 0.0254 |
| Gaussian deconvolution: true-gap sd τ | 0.164 |
| … P(true gap < 0) | 0.41 |
| **… deconvolved ceiling** E[max(0, −G)] / 2 | **0.0241** |
| gaps resolved at 2 se: negative / positive | 7 / 14 (3.0 expected per side by chance) |

**Read it as three facts.** (i) The naive point value is what pure noise would also
produce, so by itself it distinguishes nothing. (ii) The gaps are NOT pure noise: their
variance is twice the noise variance, so real top-1-vs-top-2 differences exist with sd
≈ 0.16 outcome units (8 win-rate points), and the mean gap is positive at 1.9 se — the
policy orders the pair right more often than not (P(true gap > 0) ≈ 0.59). (iii) The
prize under the true distribution is ≈ 0.024 per swap. **Both the naive and the
deconvolved readings sit at the credit floor (0.025).**

## By turn — descriptive, n ≈ 30 per bucket

| turns | n | mean gap | top-1 worse | naive ceiling |
|---|---|---|---|---|
| 2–8 | 36 | +0.034 | 0.389 | 0.0349 |
| 9–15 | 31 | +0.011 | 0.419 | 0.0404 |
| 16–22 | 28 | +0.015 | 0.429 | 0.0415 |
| 23+ | 39 | +0.080 | 0.205 | 0.0147 |

The prize is mid-game; late the policy's top-1 is worse in only a fifth of positions.
Consistent with §27's profile (the critic is at 25% of its ceiling at turns 2–8 and 73%
at 23+) without being the same quantity.

## The verdict, stated as the gate it was built to be

**NEITHER A MECHANISM KILL NOR A LICENCE.**

- **Not a kill.** Rule 6's one permitted kill needs the ceiling BELOW the effects the
  search blocks chase (+0.02..0.05). It is 0.032 [0.022, 0.043] naive and 0.024
  deconvolved — at the floor, with the interval reaching 0.043. And the scope is ONE swap
  at ONE decision: a gated search at §30's override rates intervenes 2–6 times in a
  ~30-decision battle, so to first order its oracle bound is a small multiple of the
  per-swap number (advantages do not add exactly — the outcome is bounded — so the
  multiple is loose, but it is not below the floor). The search axis is not closed here.
- **Not a licence.** The prize is the ORACLE's: it is realised only by an evaluator that
  ranks a1 against a2 better than the policy head that put them in that order, on
  differences of ~0.16 outcome units, in a regime where the critic's r² against the
  rollout oracle is 0.29 (turns 2–8, §27). §30 measured, in one session, that every
  construction we have realises a NEGATIVE share of it.
- **What decides IDEAS 4.9** is the exit gate now running (`configs/eval/exit_gate_r5.yaml`:
  the gumbel tree at 900 iterations vs the greedy committee, n=3200 each, control first).

## What may NOT be said with these numbers

- "Search cannot pay on this object" — the ceiling does not sit below the chased effects.
- "The prize is 0.03 per battle" — it is per SWAP; how many swaps a search makes is its
  own dial, and §30 measured more swaps to cost win rate under OUR evaluators.
- "The policy is wrong 35% of the time" — that is the naive fraction with noise in it;
  the deconvolved 41% is a model read, and the resolved count is 7 confident errors in
  134 against 3 expected by chance.
- The deconvolution assumes Gaussian true gaps and takes the noise from 2 × 24 rollouts
  per action, where the two determinizations' shared-world component is only partly
  removed by the pairing. It is a companion read. **The headline is the naive ceiling
  with its bootstrap interval**, and the direction of every known bias is stated: L9's
  two defects shrank the gap (fixed); the winner's curse inflates the naive ceiling
  (quantified above).
- This is a property of the R5 committee through our encoder, at greedy inference,
  against itself. It is not a ladder number and not a win rate.

## Disclosures

- The run shared the box with nothing: it was the queue's first phase, before the XGR
  control arm launched. `scripts/action_gap_readout.py` (134 rows of numpy, seconds,
  `nice -n 19`) ran beside the XGR arm.
- A pre-fix `action_gap.json` (336 positions, no self-check field) had made the queue's
  existence-based skip guard skip this run on 2026-09-19; those artifacts are quarantined
  in `results/outcome_variance/invalid_pre_L9/` and the guard now checks the fixed
  version's marker (`39da8f8`).

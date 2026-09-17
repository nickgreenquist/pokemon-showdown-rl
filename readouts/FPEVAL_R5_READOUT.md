# Foul Play's own evaluator, inside our search — off FP@20, R5 committee

Committed provenance (`results/` is gitignored). Config
`configs/eval/fpeval_r5.yaml`, evaluator `rl/search/fp_eval.py` (a port of
poke-engine 0.0.48's `src/gen1/evaluate.rs`, verified by 29 hand-computed tests),
readout `scripts/fpeval_r5_readout.py`. **Hacking run, not a pre-reg** (maintainer
2026-09-17: *"pre-reg is for ladder runs. For hacking and trying ideas, keep going
by yourself"*). Both FP@20 disclosures travel with every number: the equivalence
test is weakly powered and the point estimate flatters us.

## The question, and the answer

The depth null of JOURNEY 11.5 (RESULTS §22) had one standing explanation: our
critic was fit by PPO **only to states our own policy reaches**, and a search
deliberately visits the lines the policy does not play, so it degrades exactly
where a tree needs it. Foul Play's heuristic has the opposite property — it is the
**same function everywhere**, scored as a **difference from the root** so constant
bias cancels — and Foul Play converts compute into strength where we do not.

So we swapped **only the leaf evaluator** into our own search, keeping the dose,
the opponent model, the object and the selector shape, and re-asked the question.

**The hypothesis does not survive. Depth buys nothing with a static evaluator
either.**

| leaf evaluator | depth 1 | depth 2 | the depth step |
|---|---|---|---|
| **our critic** (1.8M params, 200M steps) | **0.5687** | **0.5680** | **−0.0007** (0.05 se) |
| **Foul Play's heuristic** (202 lines, 30 constants) | **0.5487** | **0.5400** | **−0.0087** (0.67 se) |
| evaluator difference | −0.0200 (1.56 se) | −0.0280 (2.18 se) | |

All four arms are n=3000 and **matched on override rate: 6.82 / 6.20 / 6.54 /
6.07 %**. Greedy, the same object with no search at all, reads **0.5747** and
**0.5720** on two independent n=1500 draws.

## Why the numbers are comparable

**The session anchor says the two measurement blocks are calibrated.** GA (greedy,
this block) 0.5720 against G0 (greedy, the depth block) 0.5747 = **−0.0027 at 0.15
se**. This mattered: the same frozen committee moved −0.024 between 09-15 and
09-17, and without an anchor a −0.020 evaluator difference could have been entirely
drift. It is not.

**The override rates are matched to within 0.3 points**, by a rule that reads
`search/override_rate` and never a win rate. This is not optional here: the
heuristic's leaf values spread wider than our critic's, so at the SAME δ it
overrides 2.5× as often, and yesterday an unmatched override rate turned a −0.0007
null into a −0.053 "significant" result. Achieving the match needed two grid points
added mid-sweep (δ 0.20 and 0.31) because the original grid straddled the target
without landing inside it — a refinement of the matching, not of the result.

**The vehicle fired**: `heuristic/fired_rate` 1.000 on every arm, ~348 leaves
scored per decision. The first smoke ran the vehicle and reported **no counter at
all** (two prefix filters, the new vehicle added to neither), which is the
2026-09-11 VOID shape for the fourth time this week; a test now reads both filters
out of the source and fails unless they agree.

## The one clearly attractive result is the cost

| | depth 1 | depth 2 |
|---|---|---|
| our critic | 81.7 ms | 267.3 ms |
| **their heuristic** | **30.5 ms** | **81.2 ms** |

**Their evaluator at depth 2 costs what our critic costs at depth 1.** With this
vehicle the encoder never runs — it exists only to feed a critic nobody is asking —
and that is most of our per-decision cost. **Caveat, stated rather than buried:
this is implementation-bound, not intrinsic. Our critic values ~890 leaves in ONE
batched forward while the port loops in Python over engine states, so the wall-clock
comparison flatters the heuristic at depth 1 and the network at depth 2, and
neither is what Foul Play's own Rust costs.** The evaluator comparison at equal
dose is the part that transfers; the timings are about our implementation.

## What this rules out, and what it leaves

**Ruled out:** "depth does not pay *because* our critic is off-distribution." The
property that story turns on — no training distribution to fall off — is exactly
what the heuristic has, and the extra ply still bought nothing (−0.0087 at 0.67 se).

**Also visible:** their heuristic is *worse* than our critic at both depths, and
worse than plain greedy (−0.023 and −0.032 against the same-session anchor). Foul
Play's evaluator wins for Foul Play because it is cheap and search-stable, not
because it judges gen-1 positions better than a critic trained on them.

**What is left, and it is now the live hypothesis: the GATE, not the evaluator and
not the depth.** At a ~6.5% override rate the search changes the played action on
roughly 2 decisions of a 30-turn battle, which bounds how much any leaf-value
improvement can move a win rate. We already know our critic **collapses** when
allowed to speak more often — depth-2 at 16.3% override reads 0.5160 against
0.5687 at 6.8%. The untested cell is whether a *static* evaluator collapses the same
way. If it does not, the evaluator difference shows up on the axis where it can
actually matter; if it does, the ceiling is the search construction itself.

## Sweep (override rate and cost only; n=60, win-rate se 0.065 — not read)

| δ | depth-1 override | ms | depth-2 override | ms |
|---|---|---|---|---|
| 0.15 | 0.1130 | 30.6 | — | |
| **0.20** | **0.0620** | 32.5 | — | |
| 0.25 | 0.0401 | 31.8 | 0.1119 | 89.1 |
| **0.31** | — | | **0.0682** | 87.2 |
| 0.40 | 0.0094 | 30.9 | 0.0347 | 86.3 |
| 0.60 | 0.0041 | 32.0 | 0.0059 | 84.8 |
| 0.90 | — | | 0.0010 | 86.3 |

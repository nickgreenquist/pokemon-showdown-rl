# The GATE, not the evaluator and not the depth — off FP@20, R5 committee

Committed provenance. Config `configs/eval/gate_r5.yaml`, readout
`scripts/gate_r5_readout.py`. Hacking run, 2026-09-17/18. Both FP@20 disclosures
travel with every number: the equivalence test is weakly powered and the point
estimate flatters us.

## Why this ran

§22 and §23 both came back null on depth, with our critic and with Foul Play's
heuristic. But at the ~6.5% override rate those arms used, the search changes
the played action on **about two decisions of a thirty-turn battle** — which
mechanically bounds how much any leaf-value change can move a win rate. The one
thing already measured to move it was opening the gate: our critic at depth 2
went 0.5687 → 0.5160 as its override rate went 6.8% → 16.3%.

So: hold depth, open the gate to that same rate for **both** evaluators, and see
whose values survive being acted on.

## The result

| | tight gate | open gate | opening costs |
|---|---|---|---|
| **our critic, depth 1** | 0.5687 [6.8%] | **0.5627** [19.3%] | **−0.0060** (0.38 se) |
| our critic, depth 2 | 0.5680 [6.2%] | 0.5160 [16.3%] | −0.0520 (3.30 se) |
| **FP heuristic, depth 1** | 0.5487 [6.5%] | **0.4607** [16.7%] | **−0.0880** (5.59 se) |
| FP heuristic, depth 2 | 0.5400 [6.1%] | — | not measured |

n=1500 on the open-gate arms, n=3000 on the tight-gate ones. Override rates in
brackets, matched by a rule that reads `search/override_rate` and never a win
rate.

**The evaluator difference, by gate:**

| | theirs − ours, depth 1 |
|---|---|
| tight gate | −0.0200 (1.56 se) |
| **open gate** | **−0.1020 (5.62 se)** |

## What it means

**1. OUR CRITIC IS THE ROBUST ONE, and this reverses the standing story.** The
expectation was that our critic — fit by PPO only to states our own policy
reaches — would be the fragile evaluator on search-visited lines, and that a
static heuristic with no training distribution would survive being acted on.
The opposite is measured: **tripling how often search overrides the policy on
our critic's judgement costs 0.006; doing the same on Foul Play's heuristic
costs 0.088 at 5.6 se.**

**2. §23's evaluator comparison was made in the one regime where it could not
show.** At a tight gate the difference reads −0.020 at 1.56 se and looks like a
wash. At an open gate it is −0.102 at 5.62 se. §23's sentence "their heuristic
is no better than our critic" is true and nearly powerless; the correct
statement is that **our critic is decisively better once the search is allowed
to act on it.**

**3. DEPTH-2 IS WHAT DEGRADES OUR VALUES, and the mechanism is in our own code.**
Opening the gate is free at depth 1 (−0.006) and costs 5 points at depth 2
(−0.052 at 3.30 se); the two depths are indistinguishable at a tight gate
(−0.0007) and **−0.047 apart at 2.57 se when the gate is open**. So §22's "depth
is a null" holds only in the regime where depth barely gets to speak.

`rl/search/matrix.py::_look_further` takes **a max over our replies with no min
over the opponent's**, and its own docstring justifies that by asserting the
optimism "biases every row the same way, and the root decision is an argmax over
rows". **That assumption is what fails.** Rows differ in how many replies they
have and how good the best one is, so the bias is *not* uniform — it inflates
exactly the rows with the most escape hatches, which are the rows search then
overrides into. At a tight gate almost none of those inflated rows clear the
margin; at an open gate they do.

**4. AND SEARCH STILL DOES NOT BEAT GREEDY.** The best searched arm here, our
critic at depth 1 with an open gate, reads 0.5627 against a greedy committee at
~0.572. Every search configuration measured on this object is level with or
below simply playing the policy's argmax. **A better evaluator did not change
that, and neither did more depth.**

## The greedy anchor, three independent draws

| draw | block | n | win rate |
|---|---|---|---|
| G0 | depth2_r5 (09-17) | 1500 | 0.5747 |
| GA | fpeval_r5 (09-17) | 1500 | 0.5720 |
| GB | gate_r5 (09-18) | 1500 | 0.5827 |

Spread 0.0107, each with binomial se 0.0128 — **the blocks are calibrated**, so
every comparison above is within-session in effect and none of it is drift.
Pooled, the greedy committee sits at **0.5765 (n=4500)**.

**Against that, the best searched arm on this object is 0.5627** (our critic,
depth 1, open gate) — **−0.020 against its own block's anchor at 1.29 se**, and
every other search configuration is further below. Search on the R5 committee is
level with or worse than simply playing the policy's argmax, at every depth,
with either evaluator, at either gate setting.

## What this does NOT say

- It says nothing about MCTS. `rl/search/tree.py` — decoupled UCT, our policy as
  the PUCT prior, our critic at the leaves — is a different algorithm, and it
  could not even run off Foul Play until 2026-09-17.
- It says nothing about whether the depth-2 defect is fixable. A proper min over
  the opponent's replies is the obvious repair and has not been tried.
- "Our critic is better than Foul Play's evaluator" is scoped to **leaf values
  inside our one-ply construction**. It does not follow that it wins inside a
  deep tree, where leaves sit much further off-policy.

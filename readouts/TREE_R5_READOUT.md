# TREE R5 — our critic inside a real tree, off Foul Play @20

Generated from `results/tree_r5/*.json` under `configs/eval/tree_r5.yaml`.
Hacking run, 2026-09-18. **CREDITS NOTHING.** RESULTS §26.
Regenerate the machine part with `python scripts/tree_r5_readout.py`.

## The question

Every search number this project has is the **matrix family**: one ply, an
expectation over the opponent's column, decided by a hard argmax (pre-D5) or a
margin gate. `rl/search/tree.py` is a different algorithm — **decoupled UCT, our
policy as the PUCT prior, our critic at the leaves, batch-16 leaf-parallel
descents under a virtual loss** — and it had never been run against a real
opponent. §22 declined to close MCTS on a matrix null for exactly this reason.

**THE BAR IS GREEDY**, not the depth-1 matrix: three earlier greedy draws on this
object pooled to 0.5765 (n=4500), and every search configuration measured before
today was level with or below it.

## The result — n=1000 per arm, off FP@20, R5 committee

| arm | decide rule | acted on | changed/battle | win rate | vs greedy |
|---|---|---|---|---|---|
| **TG** | **gumbel** (Danihelka et al., ICLR 2022) | 11.44% | 3.6 | **0.6040** | **+0.0210 at 0.96 se** |
| TV | visits (Foul Play's and AlphaZero's rule) | 3.65% | 1.1 | 0.5970 | +0.0140 at 0.64 se |
| TQ | q + margin 0.20 (the matrix selector's shape) | 9.34% | 2.9 | 0.5600 | −0.0230 at 1.04 se |
| **TGR** | **GREEDY, this block — the bar** | — | — | **0.5830** | — |

**NOTHING CLEARS GREEDY.** The credit line needs ≥ +0.025 **and** ≥ 2·se_diff;
TG's +0.0210 at 0.96 se misses both. **But nothing is below it either, for the
first time:** every matrix arm ever measured was level with or under greedy, and
two of these three sit above.

**THE BLOCK IS CALIBRATED.** TGR − the three-block pooled greedy = **+0.0065 at
0.38 se**, so this session is not an outlier and the anchor is doing its job.

## What IS established: the DECIDE RULE matters, and it is not the action rate

TQ acts **between** TV and TG — 9.34% against 3.65% and 11.44% — and reads
**lowest of the three**. TG − TQ is **+0.0440 at 2.00 se**. So the ordering is
not explained by how often the search overrules the policy, which is the
confound that has explained every previous depth result (§22). **The rule that
turns a finished tree into an action is doing the work**, and the worst of the
three is `q + margin` — *the shape of the banked matrix selector*.

That is a mechanism statement about our own tooling, and it is the most useful
thing in this block.

## What is NOT established, stated plainly

- **TG's +0.021 is UNRESOLVED, not a null.** se_diff at n=1000/arm is 0.0220, so
  an advisory-scale effect (+0.02–0.05) lands squarely in the recording band.
  **Resolving +0.0210 at 2 se needs n≈4,375 per arm; clearing the +0.025 floor at
  2 se needs n≈3,087.** Both are one overnight block.
- **Cross-arm deltas among TV/TG/TQ are confounded** by action rate as well as
  rule. Only arm-vs-TGR is clean here. TG − TQ is quoted above *because* it runs
  against the confound rather than with it (the arm that acts LESS reads BETTER
  is not explicable by "it acted more").
- **Nothing here says anything about the budget.** Every arm is `iters: 100`.
  The 90.9% visit-concentration caveat measured 2026-09-11 says a small budget
  cannot overrule a sharp prior, and TV's 1.1 changed decisions per battle is
  that caveat showing up in a win rate.

## Provenance and disclosures

- All four arms: **1000/1000 battles finished**, `gate_all_challenges_resolved`,
  **0 mask desyncs**. Ties: 1 each for TV/TG/TQ, 0 for TGR (ties are non-wins).
- **DISCLOSURE, not a void:** TGR reports `max_concurrent_live_battles: 2` where
  the search arms report 1, on **109 concurrent decisions of ~29,500 (0.4%)**.
  Concurrency divides Foul Play's time-boxed budget, so it can only have
  *flattered the anchor* — i.e. it biases against the search arms, which is the
  conservative direction for the claim being made.
- **Cost:** 92.7–97.7 ms per decision against greedy's ~0; 3.3 s/battle against
  1.95. The tree costs ~1.7× the wall clock of greedy for this result.
- **Code provenance:** the block spans three commits, and **`rl/` is IDENTICAL
  across them** — the arms ran the same searcher and the spanning commits were
  docs, tests and tooling. Separately verified by hand: a decision fixture run
  against the pre-block tree (`git archive`) gives bit-identical actions, stats
  and counters on all three decide rules; only wall-clock differs, and the arms
  are iteration-bounded. `tests/test_tree_decision_golden.py` now pins this.
- **Both FP@20 disclosures travel**, and the budget is named: this is 20 ms.
- TV and TG carry a **FINISH-time** `launch_git_sha` (the field was mis-named
  until 2026-09-18; `docs/CLEANUP.md` L5).

## What it argues for next

The pre-reg's step 2 was "if it clears greedy, scale the budget and put it
against FP@500". **It did not clear, so step 2 does not fire as written.** What
the result argues for instead, in order:

1. **The BUDGET, on the gumbel rule.** `iters: 100` is the regime where the
   prior dominates; the mechanism claim is that more iterations move `π′` away
   from the prior. A ladder (iters 100 / 300 / 900) measures whether the +0.021
   grows, and it is the cheapest thing that could turn an unresolved delta into
   a resolved one. **Resolving +0.021 at the SMALLEST budget would be spending
   ten hours on the weakest version of the arm.**
2. **Retire `q + margin` as the tree's decide rule.** It is the worst of three
   at 2.00 se and it is the shape every banked matrix number uses.
3. **This does not close MCTS and it does not open it.** It is one budget, one
   object, one session.

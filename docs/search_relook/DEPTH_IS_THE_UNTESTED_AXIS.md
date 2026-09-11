# Every search result we have is DEPTH-1. The plan gets depth the expensive way.

Raised by the maintainer 2026-09-11, after the budget ladder's off-FP legs came
back flat: *"when I say deep or xl search I meant more like FP: go wide AND
deep... depth=1 for all our trials is probably a massive issue and giving us
wrong conclusions."*

That is correct, and this note records why, because the mistake is structural
rather than a wording slip.

## 1. Our dose dials only buy WIDTH

`rl/search/matrix.py` DOSES: S/M/L/XL vary `n_det` (1 → 64) and `leaf_cap`
(324 → 20,736). **Every one of them is one ply.** "Dose XL" is 64
determinizations of a depth-1 matrix — the widest possible version of the
shallowest possible search, and close to the OPPOSITE of what Foul Play does.

So these results say breadth saturates at one ply, and nothing else:

| read | result |
|---|---|
| dose M → L, gated, off-FP | **−0.014 at −0.63 se** (4× the leaves) |
| better leaf evaluator (EG10) | **−0.00044 at 0.05 se** |
| gated depth-1 vs greedy, vs-SH, OOS | +0.016 (under the floor) |

**None of them is evidence about depth.** Phrases like "search doesn't pay"
were written from this table and are barred — see `docs/landmines.md`.

## 2. What the opponents actually do — MEASURED, not assumed

From Foul Play's own stdout over 33,620 decisions tonight
(`docs/prior_work/README.md`, the 2026-09-11 section):

* **FP@20**: determinizes the unknown team, holds a **~40 ms TOTAL** budget,
  splits it (`2 battles at 20ms` / `4 battles at 10ms`), runs **MCTS** on each,
  and decides by **visit percentage**. Logs no depth — an MCTS tree has none.
* **Wang**: MCTS, 20 workers × 10 s = **200 worker-seconds**. His depth is
  **NOT STATED** in the thesis (`WANG_SEARCH_DEEP_READ.md` — any "his search was
  deep" claim must be argued from node counts, never quoted as a depth).
* **Us**: **77.6 ms/decision**, ~347 leaves, **depth 1**.

**We already spend ~2× FP@20's entire budget and put all of it into breadth.**
Depth-1 is not a compute limitation here; it is a structural choice.

## 3. The plan buys depth the expensive way, and defers the cheap way behind it

`ENGINE_SEARCH_DESIGN.md` Phase 3 is *"the recursive solve, `Dose2` with a
raising watchdog"* — **EXHAUSTIVE** depth-2, which costs ~leaves². That cost is
the entire justification for the 8-11 block engine port (212 µs/leaf → 5.7
µs/leaf). **MCTS does not pay leaves²; it pays iterations**, which is how FP
gets a tree out of 40 ms using the SAME `poke_engine` our bridge already builds
States for — and which already ships
`monte_carlo_tree_search(state, duration_ms, iterations, threads)`.

**THE TRAP.** `JOURNEY.md` 11.5: *"Credits at acceptable cost → build MCTS in
gen9. Doesn't credit → the MCTS question closes permanently."* So a null on
EXHAUSTIVE depth-2 — a different algorithm, with a different cost curve, very
likely read on the saturated vs-SH axis at a delta tuned for depth-1 — would
retire MCTS **having never tested it**. That is the PRE-D5 failure shape: a null
from the wrong configuration closing a question permanently.

## 4. What this changes — MAINTAINER RULING OWED

Not for an agent to decide; `JOURNEY.md` is the maintainer's doc.

1. **Decouple the stop rule.** A null on exhaustive depth-2 must NOT close
   MCTS. They are different algorithms; the arc currently conflates them.
2. **Consider MCTS as the FIRST depth vehicle, not the reward for the second.**
   Two variants, and they are not the same experiment:
   * **(a) reference**: `poke_engine`'s own MCTS on our determinized roots —
     nearly free to measure, but it is FP, with no learned policy in the loop.
     Useful only as an upper/reference marker.
   * **(b) the actual target**: our policy as the PRIOR and our critic at the
     LEAVES inside an MCTS — Wang's architecture, on our self-play object. This
     is the "FP-like on top of our own policy" the maintainer asked for. It
     needs the bridge (have it), a tree, and batched leaf evaluation; it does
     NOT obviously need the 8-11 block port, because selectivity replaces speed.
3. **Price (b) honestly before committing.** The open question is per-decision
   cost with our critic in the loop: P0 measured ~110 µs of Python marshalling +
   critic per child, so ~1,000 visits is ~110 ms unbatched — the same order as
   the 77.6 ms we already spend, and far inside the ladder's 150 s/turn. That
   estimate is an EXTRAPOLATION from P0's per-child numbers and has not been
   measured on a tree.

**Until (b) is measured, "search does not pay for this project" is an
unsupported claim, and no depth-1 null may be cited for it.**

---

## What got built, 2026-09-11 (hacking phase — probes, not pre-regs)

### The depth-2 probe was VOID, and its number must not be quoted

`D2` (n=300, s112) printed 0.8400 and it means nothing. `_leaf_our_moves`
indexed `side.pokemon` with `side.active_index`, which pyo3 returns as a
STRING; the `TypeError` landed in a bare `except Exception: return []`, so the
extra ply produced **zero grandchildren on all 1572 searched decisions**. The
arm was S3G10 re-rolled on fresh seeds. Fixed, along with a second bug in the
same function (a terminal grandchild was valued 0.0 instead of its own ±1).

The reason it was invisible is worth more than the bug: `solve_decision` DID
emit `depth2/grandchildren`, and `_SearchEvalAdapter` dropped it, because that
adapter forwards a whitelist of keys. **"The extra ply changed nothing" and
"the extra ply never fired" printed the same win rate.** Any future dial gets
a counter that reaches disk before it gets an arm.

### `rl/search/tree.py` — the thing that was actually missing

Decoupled UCT over determinized engine states. Our masked policy is the PUCT
prior on our side; the oppact head's L6 posterior is the prior on theirs;
chance nodes are real (`generate_instructions`' branch distribution, sampled
per visit); **our critic values the leaves.**

Neither existing probe is this:

| | leaf evaluator | depth |
|---|---|---|
| `matrix.py` (every banked search number) | our critic | **1** |
| `mcts_probe.py` (MP20/MP20T/MP200) | poke_engine's heuristic | real |
| `tree.py` | **our critic** | **real** |

Measured, not argued — mean simulation depth **3.05**, max **6.58**, at 400
iterations × 2 determinizations, 692 network evaluations, **280 ms/decision**.
For scale: the depth-1 matrix at dose M is 78 ms, FP@20's ENTIRE budget is
~40 ms, and the ladder allows 150 s per turn.

### Two decision rules, because the rule mattered more than the tree

`decide: visits` is AlphaZero's and FP's. On the first smoke a sharp policy
prior put **90.9%** of root visits on one action, so at this budget visit
share is very nearly the prior and the tree can barely speak. FP gets away
with it because FP has no policy net to be overruled by.

`decide: q` scores each root action by its backed-up mean value and plays it
only if it beats the policy's own action by a margin. That is the SAME SHAPE
as the banked depth-1 selector (`row_ev` + `margin_delta`), on the same ±1
critic scale — so `S3G10` at δ 0.10 and `TREEQ` at δ 0.10 differ in DEPTH and
in nothing else. That is the comparison this axis has been missing.

The gate calibration lesson is already paid for: the same MCTS tree at
margin 0.10 (30.0% override) read 0.7900 and at 0.35 (10.9%) read 0.8400.

### Batching, so depth is affordable

The network was 55% of a decision (126 of 227 ms over 276 batch-1 forwards).
Leaf-parallel descents under a virtual loss now share one forward: **224 ms →
113 ms at batch 16**, network 125 → 25 ms. The cost is depth per iteration
(16 descents commit before any is expanded: mean depth 2.70 → 2.15 at equal
iterations), which more iterations buy back. The bottleneck is now the
pure-Python encoder — 99 of SWA's 280 ms — and `embed_battle` is NOT to be
touched, because every checkpoint was trained against it byte-for-byte.

---

## The baseline these probes have to be read against (2026-09-11, corrected)

**A 300-seed arm may not be compared to a 3000-seed pooled mean.** Every probe
arm here runs seeds 100–399. So does `S3G10`'s chunk00 — and that chunk reads
**0.8000**, while `S3G10`'s pooled n=3000 number is **0.82400**. Reading the
probes against 0.824 silently charged each of them 0.024 of seed-block offset.

On this block the ordering is not even the usual one:

| seeds 100–399, n=300 | win rate |
|---|---|
| `A0` greedy | **0.8367** |
| `S3G10` depth-1 gated | 0.8000 |
| `S3M` depth-1 ungated | 0.7500 |

Greedy *beats* the gated search on these 300 seeds. That is the landmine
about a single rung being worth ±0.02 rather than the binomial ±0.008, showing
up exactly where it was predicted to.

Matched seed-for-seed, with McNemar's se over the battles where the two arms
actually disagreed:

| arm | n | win | vs depth-1 | |
|---|---|---|---|---|
| `TREEQ` deep tree, minimax opponent, δ 0.10, **27.2%** override | 300 | 0.6800 | **−0.1200** | **−3.3 se** |
| `TREEQ25` same tree, δ 0.25, 9.7% override | 300 | 0.7900 | −0.0100 | −0.3 se |
| `D2B` banked matrix + 1 selective ply, 16.9% override | 300 | 0.7900 | −0.0100 | −0.3 se |
| `MP200` poke_engine MCTS @200 ms, 31.5% override | 300 | 0.8200 | +0.0200 | +0.6 se |

**One thing separates at this n, and it is not depth: letting the deep tree's
minimax Q override the policy 27% of the time costs 0.12.** Tightening the
same tree's gate to 9.7% recovers all of it. Depth itself is neither shown to
help nor shown to hurt at these doses — n=300 buys ±0.03 and the interesting
deltas are smaller than that.

Which is why the next arms are the ones that separate the mechanisms rather
than pile on n: `TSAMP1` (depth 1, opponent SAMPLED from q) against `S3G10`
isolates the tree's Monte-Carlo root estimate from the matrix's exact one, and
`TSAMP` against `TSAMP1` then isolates depth with that controlled. `D3` and
`D2W` push the one family that keeps everything the banked object already
gets right.

---

## The depth census, and what it does to the question (2026-09-11)

`poke_engine`'s own `iterative_deepening_expectiminimax`, run on OUR
determinized states at three budgets, 218 live decisions:

| budget | depth reached |
|---|---|
| 20 ms | **2.44** |
| 200 ms | 3.08 |
| 2000 ms | 3.56 |

**100× the compute buys 1.1 plies.** The curve is that flat because branching
is ~9 our-actions × ~5 opponent-actions × chance branches per ply, so depth is
logarithmic in budget. Our own tree's sweep says the same thing from the other
side: 400 → 800 iterations moved mean simulation depth 3.05 → 3.40.

Two consequences, and they change what the open question is.

**1. Foul Play at its anchor budget is searching at roughly depth 2.4–2.6.**
Its whole measured budget is ~40 ms (2 determinizations × 20 ms). So "Foul
Play is strong because it searches deep" is not supportable, and neither is any
story that explains our gap by depth we cannot afford. Our tree reaches a MEAN
simulation depth of 3.15 and a max near 7 — **we already search deeper than
Foul Play does at the budget we anchor against.**

**2. The question is no longer "can we get depth".** We get it, and it costs
us. At n=900, matched seed-for-seed against the depth-1 gated baseline
(0.8189), with McNemar's se over the battles where the two arms disagreed:

| arm | depth | n | win | vs depth-1 |
|---|---|---|---|---|
| `TSAMP1` tree, opponent sampled from q | **1** | 900 | 0.8144 | −0.0044 (−0.2 se) |
| `TSAMP` same tree, same selector, uncapped | 3.15 | 900 | 0.7900 | −0.0289 (−1.6 se) |
| `D2B` banked matrix + 1 selective ply | 2 | 900 | 0.7800 | −0.0389 (−2.1 se) |
| `D2W` same, our_k 3 → 4 | 2 | 900 | 0.7778 | −0.0411 (−2.2 se) |
| `D3` banked matrix + 2 selective plies | 3 | 900 | 0.7244 | −0.0944 (−4.6 se) |
| `TREEQ` tree, MINIMAX opponent, 27% override | 3.71 | 300 | 0.6800 | −0.1200 (−3.3 se) |

`TSAMP1` is the control that makes the rest readable: the NEW tree, capped to
one ply, reproduces the banked depth-1 matrix (−0.2 se). The implementation is
not the problem. What is left is a **monotone dose-response in depth, going
the wrong way, in two independent implementations** — −0.004 → −0.029 in the
tree, −0.039 → −0.094 on the matrix.

### The hypothesis this now points at

Same depth, different evaluator. `poke_engine`'s hand-written heuristic works
at depth 2.4; our critic does not work at depth 3. A static evaluator has no
training distribution to fall off — it is the same function everywhere in the
tree. Our critic was fit by PPO **only to states our own policy reaches**, and
search deliberately visits the lines the policy does not play. The deeper it
goes, the further off that distribution it is asked to judge.

The supporting evidence was already on the table and was being read as a
selector story: **the gate is load-bearing at depth 1 too.** Ungated depth-1
is 0.74767, BELOW greedy's 0.78233; gated at δ 0.10 it is 0.82400. Even at one
ply the critic's own argmax is worse than the policy's preference. Search has
only ever paid here as a rarely-fired veto. Depth does not fix that; it gives
a bad argmax more room to act.

Not yet established, and deliberately left open: whether a critic trained on
search-visited states would change the sign. That is the AlphaZero / expert
iteration answer and it is the reason the deep-research briefs went out.

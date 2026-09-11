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

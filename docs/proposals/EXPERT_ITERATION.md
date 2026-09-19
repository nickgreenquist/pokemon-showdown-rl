# Expert iteration — the design, written 2026-09-18

**Status: a DESIGN SKETCH, not a pre-reg and not ratified.** It exists because
the maintainer ranked IDEAS **4.9** the top item of §4 on 2026-09-18 and a fleet
item needs something rulable before it needs a header. **It is gated on IDEAS
2.11** (the luck ceiling), which is hours of work and decides whether this is
the right fleet at all. Nothing here runs until that reads.

---

## 1. What it is, in one paragraph

Search at state `s` produces an improved policy — the root visit distribution
`π' = N/ΣN` — and an improved value, the root's backed-up `q`. Train the network
toward BOTH: cross-entropy from the policy head to `π'`, and the value head
toward the search-backed target instead of (or blended with) the raw return. The
improved network makes the next search better, and the loop compounds. This is
AlphaZero's actual mechanism and Anthony et al.'s "expert iteration"; **it is not
"MCTS bolted on at inference", which is the only thing this project has ever
measured.** The expert is OUR OWN SEARCH, so it is inside the pure-self-play
charter — nothing external enters the learner.

## 2. Why this lever and not another — the evidence, not the vibe

**Two defects are measured, and this is the only proposal that attacks both.**

**(a) The critic is never trained on the states search visits.** PPO's value loss
fits a baseline on the state distribution OUR OWN POLICY reaches. Search
deliberately visits the lines the policy does not play. §8.2 has said this since
2026-09-09 and nothing has ever trained for the second objective. RESULTS §24
sharpens it in our favour: opening the gate costs our critic **0.006 (0.38 se)**
where it costs Foul Play's hand-tuned heuristic **0.088 (5.59 se)** — our critic
is the ROBUST evaluator, so the material is good. It has simply never been asked
the search's question.

**(b) The policy is never trained toward the search's improved distribution, and
the search cannot express an improvement without that.** Measured 2026-09-11 and
recorded in `configs/eval/tree_r5.yaml:36` and **WITHDRAWN 2026-09-19 (RESULTS
§32): π′_top1 at iters 100 measures 0.417, not 0.909 — the sharp thing is the
PRIOR (0.885). The point survives in a better form: the tree's argmax differs
from the policy's on 4.0% of decisions at iters 100 and 15.9% at iters 900.**
The original claim was: at a small budget **90.9% of root
visits land on ONE action**, because the prior is sharp and nothing ever moves
it. First live confirmation, 2026-09-18: the TV arm (decide=visits, iters 100)
changed the played action on **3.65% of decisions — 1.1 decisions per battle**.
A tree whose visit distribution is nearly its own prior is nearly the greedy
policy, which is exactly what every "search is a null" result has been measuring.

**And the thing that makes it a TRAINING lever rather than another dose.**
§22/§23/§24 all measured inference-time search on a FROZEN network: a one-shot
override on 6–19% of decisions, bounded mechanically by how often it fires.
Expert iteration changes what the network IS, so the search's value compounds
over a fleet instead of being spent once per decision. Its failure mode (a bad
expert teaching a bad target) is different IN KIND from "the override did not
pay", which is why the depth nulls do not speak to it.

## 3. What has to be built, cheapest first

1. **PERSIST `π'` AND THE ROOT VALUE.** `rl/search/tree.py` already computes root
   visits and q; nothing writes them anywhere. This is the free half and it is
   worth doing even if the rest is never ratified — it makes every existing
   search arm a dataset and lets us ask offline how far `π'` is from the prior
   before spending a fleet on closing that gap.
2. **A POLICY LOSS TOWARD `π'`** on searched states: `-Σ π' log π_θ`, masked
   through `rl/common/masking` like everything else, with its own coefficient
   and its own `loss/*` metric (locked names: it is logged from PPO's update,
   never from env or pool code).
3. **A VALUE TARGET FROM THE SEARCH ROOT** rather than the raw return — or a
   blend, which is the honest first arm because the raw return is what the
   current 0.59 EV is fit to.
4. **THE DOSE, which is what decides the price.** Searching every decision is
   ~100× a greedy step (97.7 ms vs ~1 ms measured on the R5 committee), so the
   only affordable shape is **search a SAMPLED FRACTION of decisions and train on
   those**. IDEAS **8.5**'s disagreement gate is the natural selector and is
   already built — search where the committee is split, train on those states.

## 4. The three ways this fails, named before it runs

- **The luck ceiling (2.11).** If `EV_ceiling ≈ 0.6`, the critic is already at
  the format's ceiling, a better expert has nothing to teach, and this is the
  wrong fleet. **This is why 2.11 runs first: hours against days.**
- **The expert is not better than the student.** If `π'` is ~the prior, the
  cross-entropy term is a no-op with extra compute. (~~the 90.9% reading~~ —
  **WITHDRAWN 2026-09-19, §32. The falsifier below has since RUN, at `iters:
  100` over 1,107 searched decisions: `KL(π′ ‖ prior)` = 5.70 nats, `pi_top1`
  0.417 vs the prior's 0.885 — π′ is NOT ~the prior, so this gate is OPEN. Read
  the KL with its companion: π′ at this budget is DIFFUSE rather than
  confidently opposed, and `argmax_moved` is only 4.0% (15.9% at 900), so the
  expert differs from the student mostly in SHAPE, not yet in CHOICE.**) **The
  falsifier is cheap and comes free with step 1: measure KL(`π'` ‖ prior) and the
  fraction of decisions where argmax `π'` ≠ argmax prior, on banked arms, BEFORE
  the fleet.** If that KL is ~0 at an affordable budget, the lever is dead
  without a fleet and the right follow-up is the tree BUDGET, not the loss.
- **The expert is optimistic.** IDEAS 2.10 measured the matrix vehicle's backup
  inflating exactly the rows search overrides into. **A tree with a broken backup
  would teach the bug.** Whatever vehicle supplies `π'` must have its backup
  audited first; `opp_k` exists for that reason on the matrix side, and
  `tests/test_tree_decision_golden.py` pins the tree's.

## 5. What a pre-reg would have to carry

- **A mechanism co-primary that is NOT explained variance.** RESULTS §21 bars
  sizing on EV by name: 2.67× width and 126× first-layer rank bought ZERO EV
  while the win rate moved. Candidate mechanism reads: KL(`π'` ‖ prior) rising
  over training (the expert pulling away from the student), critic error on
  SEARCH-VISITED states falling relative to on-policy states (the defect this
  targets, measured directly), and the override rate at a FIXED gate rising.
- **The credit line restated verbatim**, including the larger-of clause.
- **The dose stated and matched**: an arm that searches 25% of decisions has less
  fresh experience per wall-clock hour than the control, and a comparison that
  does not hold total steps fixed measures the dose.
- **`journey_step` named** — this is JOURNEY 14 work, and no number from it may
  be quoted beside a pure-lane number without saying so.

## 6. Cost, roughly

Collection is ~200 steps/s/lane on the engine collector at k=8. A searched
decision at the TV budget is 97.7 ms, so searching 25% of decisions multiplies
collection cost by ~25×, which is not affordable at 200M. **The realistic first
arm is much smaller than a fleet**: one lane, a short horizon, and the read is
the MECHANISM (does `π'` move, does critic error on search-visited states fall),
not a win rate. A win-rate arm only makes sense after the mechanism moves.

## 7. Open questions for the maintainer

1. Does 4.9 get a fleet at all, and does it wait for 2.11? (This file assumes
   yes and yes.)
2. Which vehicle supplies `π'` — `rl/search/tree.py` (a real tree, the right
   shape, and the one with a pinned backup) or the matrix family (cheaper, one
   ply, and its backup was wrong until 2026-09-18)?
3. Is a value target from the search root inside the charter's spirit? It is our
   own network's backup, so this file assumes yes, but it is the first time a
   target here has come from anywhere but the environment's return.

# Handoff — the post-ladder week, 2026-09-18/19

**Written 2026-09-19 at an explicit stopping point.** Nothing is running. Tree is
clean, suite is green (**1219 passed / 0 failed / 87 skipped**), 13 commits today,
45 since 09-18. On pickup: fold anything durable into STATUS/SESSION_LOGS and
restore the empty stub.

**Read in this order:** this file → `STATUS.md` → the RESULTS sections it names.
Do not quote a number from this week without reading its correction box first.

---

## What this week was

LADDER R5 landed on 09-16 (**GXE 73.9 / Glicko 1697 ± 25 / Elo 1457, LISTED**).
The week after it was a **search chapter**: eight blocks asking whether anything
we can do at inference time beats playing the committee greedily, plus two
diagnostic blocks asking what is actually wrong with the critic.

**The answer on search is no, and it is now a measured cost rather than another
null.** The answer on the critic is that it has a real, identified, un-fixed
deficit — which is the live thread.

The last third of the week was a **correction pass**: three Opus review agents
over every claim. **Sixteen changed. One section was retracted in full. Three of
the wrong numbers were ones I had written INTO the corrections.**

---

## The five results worth carrying forward

1. **§30 — greedy beats every search arm, at 2.4–4.4 se.** In-session anchor
   **GC 0.6050** tops a seven-arm n=1000 block off FP@20. The block validated
   itself: D1O and DUM are the same config on two username pairs and read
   **0.5510 / 0.5530**, so the within-session floor is **0.0020** — a tenth of
   one cross-session rung. This is the first search result that measures a COST
   rather than failing to measure a gain, which is what makes it citable under
   CLAUDE.md rule 6.

2. **§30 / IDEAS 8.5 — selection is a null, but SEARCHING LESS BEAT SEARCHING
   MORE.** Committee-disagreement gating vs a coin at a rate matched to three
   decimals: **+0.0030 at 0.14 se.** Gated (40% of decisions) vs ungated (93%),
   pooling both replicates per side: **+0.0335 at 2.14 se.** Post-hoc pooling and
   the block credits nothing — but the dose intuition is backwards, and that is
   the most interesting unexplained thing on the board.

3. **§27 / §27.1 — the luck ceiling, and the critic's real deficit.** ~64% of a
   mid-battle outcome is irreducible; ceiling **0.3630** against our critic's
   **0.2176**, so **the gate opens — the critic is not done.** Of the gap,
   **~93% is RANKING** and only ~7% is calibration (corrected from 88/12 — the
   original CV leaked). Worst in the **opening** (r² 0.287 at turns 2–8 vs 0.727
   at 23+). **This is the live lever.**

4. **§31 — the critic adds +0.059 to whichever side it is pointed at, z 14.7**,
   5× more in the opening. The mechanism is identified and it is not a bug: that
   is its training distribution's own mean return, because **league play fits it
   against a pool of older, weaker checkpoints** (+0.036 whole-run, +0.087 late)
   while evaluation is a mirror where the truth is 0. **A train/eval distribution
   shift.**

5. **§29 — the annealed LR tail trades EV for win rate in 9 lanes of 9.** EV goes
   DOWN and value loss UP while in-loop win rate goes **+0.059 / +0.062 / +0.033**.
   **Do not floor the LR.** Together with §21 (width bought zero EV) and §27.1
   (93% ranking), that is the third independent measurement that **EV is not the
   objective.**

---

## What the review pass changed — read this before citing anything

| what | was | is |
|---|---|---|
| **§30.1** | "no session offset; the landmine is retired" | **RETRACTED IN FULL.** The test's power at 0.02 is **0.13**, not the "G≈12, p≈0.02" it claimed without computing. **The landmine stands.** |
| **§27.1 split** | calibration 12% / ranking 88% | **7% / 93%** — the CV split at the outcome level while the predictor is constant within a position |
| **§28** | "every turn-cap stall is…" | **91.3%** — the claim had rested on six battles; 103 of 104 are now enumerated |
| **§31** | "the determinization sampler is exonerated" | **withdrawn** — the probe holds the sampler fixed by construction, so it carries zero information about it |
| **§32 / the "90.9%" caveat** | quoted all week as a property of the regime | **one smoke decision.** Measured: `pi_top1` **0.417** vs the prior's 0.885, KL **5.70 nats** — π′ is far FLATTER than the prior |
| **IDEAS 4.1** | "has its measured defect at last" | **attribution withdrawn** — p1/p2 are symmetric, so it is not a seat effect. 4.1 keeps its sample-efficiency argument at zero build cost |

**The week's actual lesson.** I wrote three numbers into correction boxes that
were not measurements — one of them a value lifted from a **golden test fixture**.
They were caught only by re-deriving every figure from `results/`. *A number typed
from memory into a correction is exactly as unsafe as the number it corrects.*

---

## The code that changed, and why it matters more than the numbers

**Eight defects this week, all one shape: a dial or a counter that runs and reports
nothing, or reports the wrong thing.** The structural repair is in:

- **`scripts/ch3_eval.py`** forwarded a **hardcoded** list of `SearchAgent` dials.
  `disagree` and `calibration` were added to the object afterwards, so a pre-reg
  declaring either would have been accepted, the key **silently dropped**, and the
  arm run as an unmodified control **while its readout claimed the dial** — with
  nothing to catch it, because the dial's counters simply stay zero, which reads as
  "the dial did nothing". Now derived from `inspect.signature`, with an unknown
  pre-reg key a **hard failure**. Verified against all 31 banked pre-regs.
- **`rl/common/value_calibration.py`** ramped through every isotonic STEP, throwing
  away **27% of the fitted gain** — while its docstring claimed it could not drift
  from the analysis script. It had.
- **`rl/search/tree.py`** now emits `tree/gate_off`, so "acts 0%, the tree agreed"
  can never be confused with "acts 0%, the tree was never allowed to act".

---

## Where to pick up

**Nothing is blocked and nothing is mid-flight.** Three threads, in order:

1. **THE CRITIC IS THE LEVER.** §27/§27.1/§31 say precisely what is wrong: 93% of
   the gap is ranking, concentrated in the opening, plus a measured +0.059
   train/eval shift. **4.9 (expert iteration) is the top §4 item and its 2.11 gate
   has OPENED.** `docs/proposals/EXPERT_ITERATION.md` is written and its free
   falsifier has now run: KL 5.70 nats at `iters: 100`, `pi_top1` 0.417 — π′ is
   **not** the prior, so the "expert is no better than the student" objection is
   answered. What remains unanswered is that `argmax_moved` is only **4.0%** at 100
   iters (15.9% at 900): the expert differs in SHAPE long before it differs in
   CHOICE, and a distillation target that never changes the action is a no-op.
2. **SEARCH IS CLOSED FOR NOW, AND IT OWES A BAR.** Any next search idea has to
   argue against the override regression (**−0.48 win rate per unit override
   fraction**, r −0.875, leave-one-out stable, intercept reproducing the measured
   anchor to 0.006), not merely propose another vehicle. Note carefully what this
   does **not** close: `tree.py` is a different algorithm from the matrix, a true
   per-ply minimax is untried, and the 40%-beats-93% result says targeting may pay
   even where dose does not.
3. **FOUR RULINGS ARE OWED** (all in STATUS): the **loop breaker** (§28 — built,
   13 tests, wired nowhere, because it changes the policy form); **R6's split
   schedule**; the next fleet's shape; and whether 4.9 gets a fleet. **The LR-anneal
   floor no longer needs one — §29 answers it: do not floor it.**

## What is safe to trust, and what needs care

- **Trust:** every number in `readouts/`, every R5 ladder figure, the suite, and
  every correction box (each is now traced to a file in `results/`).
- **Care:** anything this week quoted WITHOUT its correction box — the six rows in
  the table above are all still findable in older docs and in `docs/archive/`.
- **Binding again:** never difference across sessions without an in-block anchor.
  §30.1 tried to lift that and has been retracted.

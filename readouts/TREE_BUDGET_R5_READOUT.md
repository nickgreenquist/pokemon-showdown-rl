# TREE_BUDGET_R5 — readout

**Block:** `configs/eval/tree_budget_r5.yaml` · **run:** 2026-09-19 ·
**data:** `results/tree_budget_r5/` · **status:** hacking screen, credits nothing

**Object:** the R5 committee (log-pooled `w104`/`w112`/`w120`). **Instrument:**
Foul Play h2h at `--search-time-ms 20`, seat `w112`. **n = 40 per rung, so NO WIN
RATE HERE IS A READ** (se 0.079). This block was designed to read a MECHANISM.

---

## The pre-registered rule, and that it did not fire

`configs/eval/tree_budget_r5.yaml` fixed the criterion BEFORE the block ran:
phase R proceeds only if **KL(π′‖prior) rises ≥1.5×** *and* **`argmax_moved`
rises ≥5 points** between `iters: 100` and `iters: 900`.

| arm | rule | iters | evals/dec | `prior_top1` | **`pi_top1`** | **`argmax_moved`** | **KL(π′‖prior)** | π′ entropy | win (n=40) |
|---|---|---|---|---|---|---|---|---|---|
| BS1 | gumbel | 100 |   181 | 0.885 | **0.417** | **4.0%**  | **5.70** | 1.68 | 0.625 |
| BS3 | gumbel | 300 |   535 | 0.890 | 0.670 | 9.0%  | 2.77 | 1.10 | 0.650 |
| BS9 | gumbel | 900 | 1,550 | 0.884 | **0.773** | **15.9%** | **1.67** | 0.71 | 0.725 |
| BSV | visits | 900 | 1,525 | 0.882 | 0.754 | 17.5% | 1.82 | 0.76 | 0.600 |

> **THE RULE DOES NOT FIRE, and it is recorded as not firing.** `argmax_moved`
> rose **+11.9 points** (criterion: ≥5) — but **KL went the OTHER WAY, to 0.29×**
> (criterion: ≥1.5×). One of two criteria met. **Phase R does not run.**

## The criterion was MIS-SPECIFIED, and that is the block's real finding

The rule assumed KL(π′‖prior) measures *conviction* — that a tree given more
iterations would move FURTHER from the prior. **It measures DISPERSION, and at a
small budget it is inflated by the opposite of conviction.**

At `iters: 100` the tree spends ~181 evaluations over ~7 legal actions. π′ comes
out **DIFFUSE** — `pi_top1` **0.417**, entropy **1.68**, support **7.06** — against
a prior that is sharp at **0.885**. A flat π′ against a sharp prior is a *large*
KL. As iterations rise the tree CONCENTRATES (`pi_top1` 0.417 → 0.670 → 0.773,
entropy 1.68 → 0.71, support 7.06 → 4.27) and moves TOWARD the prior's shape, so
KL falls. **KL was the wrong instrument; `argmax_moved` was the right one**, and
it moved monotonically and in the predicted direction at every rung.

**A corrected rule needs a re-run, and whether to spend it is a maintainer
ruling.** On the corrected reading (`argmax_moved` alone) the rule WOULD have
fired.

## What this withdraws — the "90.9%" caveat, quoted project-wide all week

The proposal behind this block asserted: *"our prior is sharp enough that 90.9%
of root visits land on one action at a small budget."* It was quoted in seven
files as a property of the regime.

> **It was ONE smoke decision.** Measured here over **1,107 searched decisions**
> at that same `iters: 100`: **`pi_top1` = 0.417**, not 0.909. **π′ is far
> FLATTER than the prior, not concentrated on it** — the opposite of the claim.
> The prior does NOT dominate at 100 iterations.

**Consequences, both ways.** It REMOVES the premise that the budget is a lever
("more iterations will unlock a bigger effect" has lost its mechanism — and the
screen confirms the rule did not fire). It OPENS **IDEAS 4.9**'s gate: expert
iteration's standing objection was *"if π′ ≈ the prior, the cross-entropy term
is a no-op." π′ is not the prior.* What 4.9 still has to answer is that
`argmax_moved` is only **4.0%** at 100 iters — **the expert differs from the
student in SHAPE long before it differs in CHOICE**, and a distillation target
that rarely changes the action is close to a no-op regardless of its KL.

## Cost, for the record

| iters | evals/decision | relative cost |
|---|---|---|
| 100 | 181 | 1.0× |
| 300 | 535 | 3.0× |
| 900 | 1,550 | **8.6×** |

**8.6× the compute buys 4× the `argmax_moved`.** Read against §30 — which
measured, in one session, that the arms changing MORE decisions read WORSE — a
bigger tree buys more of the thing that block measured to cost win rate. That is
not proof the tree behaves like the matrix (§26.1: the only arms ever above
their own anchor were trees), but it is the economics the next tree proposal has
to answer.

## Provenance and disclosures

* **`tree/*` counters reached no disk on the preceding block** (`tree_r5`) — the
  third occurrence of the writer-not-collector defect, fixed before this block
  ran, which is why these columns exist here and are absent from `tree_r5`'s
  JSONs. `readouts/TREE_R5_READOUT.md` carries that disclosure.
* **`tree/transition_failures` = 0.0 on all four arms** — the engine reproduced
  every transition the tree asked for.
* **Ties: 0 on all four arms.** 40/40 battles finished per arm.
* **n = 40 per rung.** The win-rate column is printed for completeness and is
  **not a read** — se 0.079, and the four values span 0.125.
* BSV shares BS9's budget so the `decide` rule is the only difference between
  them; `visits` reads 0.600 against gumbel's 0.725, which at this n says
  nothing on its own but points the same way as §26's TG > TV ordering.

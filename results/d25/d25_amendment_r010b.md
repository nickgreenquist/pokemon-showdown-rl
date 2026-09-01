# R0-10b — AMENDMENT A1 **REFUSED**, superseded by A2

**A1 (the fitted-head construction) was drafted, sent to two independent Opus
reviews, and REFUSED on their evidence. A2 below is what replaces it, and it is
PROPOSED — awaiting the maintainer. Nothing in
`configs/showdown_sp_actpred12m.yaml` has been changed.** 2026-08-13, zero lanes.

Reviewer 1 (evidential validity): **REFUSE.**
Reviewer 2 (decision and risk): **RATIFY WITH CHANGES** → coefficient 0.1.

## What A1 claimed, and what the reviews did to it

A1 argued that R0-10b's fresh-head measurement is an initialisation artefact
(`aux_head_gain = 0.01` scaling the scorer's final layer, hence the gradient
into ctx), that a FITTED head gives raw ratios 2.50/3.41/4.19, and that the
pre-stated grid therefore filters to {0.05, 0.1, 0.25} rather than being empty.

**Three of A1's load-bearing claims did not survive.**

1. **THE FITTED CONSTRUCTION IS NOT DETERMINATE.** Reviewer 1 re-ran A1's own
   recipe — matching held-out CE, so it *is* the same construction — and got
   1.74/1.46/1.24 where A1 got 2.50/3.41/4.19. Under Reviewer 1's numbers coef
   0.5 is IN BAND at every stage and the sweep would start at 0.5, not 0.25.
   A gate whose output moves across the entire pre-stated grid under undisclosed
   fit hyperparameters (optimiser, lr, patience, split seed) is not a gate.

2. **A1's HEADLINE WAS STATISTICALLY WRONG, IN ITS OWN FAVOUR.** A1 reported
   "2.31–6.56 across three head draws" at 12M as head-draw spread. It is not.
   Re-measured with the actor held FIXED at 12M and only the random z-scored
   advantage vector varying, **‖g_trunk policy‖ spans 0.236–3.196 over 20 draws,
   a 13.6× swing**. A1 varied the advantage seed *with* the head seed and then
   took a **mean-of-ratios**, which is Jensen-inflated 1.3–1.5× against
   ratio-of-means. A1 also dropped from the executed gate's 5 draws to 3 while
   the spread widened — fewer draws, narrower range, in the flattering
   direction, on the one quantity the launch turns on.

3. **A1's DEFENCE #2 RUNS THE WRONG WAY, and both reviewers caught it
   independently.** "The correction retro-fixes D19-B's self-contradiction" is
   asserted, never measured, and the stated mechanism predicts the opposite
   sign: D19-B's table is fresh-head at the *same* gain 0.01, so a symmetric
   correction scales its ratios UP too and its recommended 0.1 fails the band
   out the TOP. The fresh→fitted factor is common-mode and CANCELS, so it cannot
   explain why D25's fresh aux gradient is 4×/33×/36× below D19's. **Struck.**
   Defence #3 ("the correction REMOVES a coefficient") falls with finding 1 —
   0.5's removal was an artefact of A1's fit recipe.

**And the mechanism, while real, does not license the conclusion.** Reviewer 1
verified it directly: scaling the head's final layer by 100 raises ‖g_trunk aux‖
by 66.7×/87.4×/77.8×, so "~100×" is the right order. But at that scale a
*random* head sits within 1.5–2.2× of the *fitted* head. **Both constructions
measure ‖W_last(t)‖ × residual, not the lever's coupling** — which is A1's own
critique of the fresh-head number, turned on A1.

## A2 — PROPOSED

**R0-10b is neither passed nor overridden. It is SUPERSEDED by a live
measurement during R0-10's smoke, which is already owed and already budgeted.**

1. **Strike the fitted-head construction as a gate.** It is not determinate, and
   it measures the same weight-scale quantity it accuses the fresh-head number
   of measuring. A1's defences #2 and #3 are struck outright.
2. **Neither offline proxy gates the rung.** The numerator moves ~66× over
   training with the head's last-layer norm; the denominator is the norm of an
   arbitrary z-scored advantage vector and swings 13.6× with the actor frozen.
   That is not a criterion, in either construction — which is also why the band
   rejects D19-B's own recommendation.
3. **Measure it live instead**, on the co-trained head against the moving trunk
   with the run's own real advantages. Shipped: `aux/trunk_norm` and
   `aux/policy_trunk_norm`, both PRE-clip, logged per rollout, with the ratio
   taken as a RATIO OF MEANS at read time. A pure diagnostic — it reads `.grad`
   and changes no update. **Reference already measured: 0.177 at coef 0.1 over
   the first 8k steps, inside the band [0.05, 1.5].**
4. **The R0-10 smoke runs the pre-stated grid** (configs shipped for all four
   arms) and its read gains one line: the live ratio and its trajectory. The
   coefficient is chosen by R0-10's own unmodified rule.
5. **NO pre-registered number changes.** Not the grid, not the band, not
   `aux_head_gain`, not `aux_oppact_coef`. On the evidence so far the rule
   selects **0.1 — the value the ratified config already carries.**

## Reviewer 2's findings that A2 adopts on their own merits

- **Calibrate on injection fraction.** `coef × ratio` IS the aux trunk gradient
  as a fraction of the policy's. D19-B recommended a coefficient it believed
  bought 3–12%. Nothing in this repo has recommended an auxiliary loss that
  pushes the shared trunk as hard as the policy does — which is what 0.25 would
  do under A1's own numbers (62–105%).
- **Risk is asymmetric and the head's learning is nearly coefficient-free.**
  `aux_params` are their own Adam group fed only by the aux term, so Adam's
  per-parameter normalisation makes *whether the task trains* roughly
  coefficient-invariant. The coefficient buys little g and all of the F5 risk.
  Too large → R1 arm-level stop at 4M, F5 NEGATIVE recorded, **no re-tune, no
  relaunch**, and an epitaph naming a coefficient chosen by an amended gate.
  Too small → FLAT with a LEARNED manipulation check, the interpretable null
  this rung exists to buy.
- **Clip interaction, now visible.** `aux_max_grad_norm` 0.5 vs `max_grad_norm`
  0.5: at the top of the grid the aux clip binds and the band would be
  regulating a pre-clip quantity that no longer describes what reaches the
  trunk. `aux/grad_clip_frac` is logged and is added to the launch watch reads.
- **Condition (a) may not bind.** A head on frozen 600k features reaches
  held-out CE ~0.68 against A1 ≈ 1.50 / A3 ≈ 0.25, i.e. g ≈ 0.65 against a
  0.3286 bar. If g ≥ 0.25-and-rising passes at every coefficient, the smoke's
  real yield is the live ratio, R0-8 throughput, and the finiteness reads — say
  so at readout rather than discovering it there.
- **Budget arithmetic verified:** 5 × 11.0 h = 2.29 → 2.35 all-in ✓;
  13.54 + 2.35 = 15.89 → "15.9 of 20" ✓; headroom ~6.5 ✓; with the placebo
  ~18.2 ✓. The smoke arms (~0.015 lane-days) are unledgered and immaterial.

## What A2 does NOT resolve

Reviewer 1's answer to "is fresh-head defensible on its own terms?" is **yes**:
the first updates are when the trunk is most plastic and least protected, and
`aux_head_gain = 0.01` was chosen in that frame. A2 does not refute that reading
— it declines to let either offline reading decide, and buys a live one for
~20 minutes. **If the maintainer prefers the strict reading, R0-10b stands and
the rung does not launch; that is a legitimate call and A2 is not an argument
against it.**

Reviewer 1's separate finding that D25's fresh aux gradient is 4×/33×/36× below
D19's at identical gain — a head-architecture difference (2-layer scorer over 6
classes vs a wide linear species head), not a frame difference — is untouched by
A2 and is recorded as the actual open finding.

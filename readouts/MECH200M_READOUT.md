# mech200m — [RWL-3]'s MECHANISM CO-PRIMARY, read out

Committed provenance for the mechanism half of the monster fleet's PRIMARY.
`results/` is gitignored, so this file and `scripts/mech200m_readout.py` are
the only record that survives losing `results/mech200m/`. Regenerate with:

```
python scripts/mech200m_history.py
bash scripts/mech200m_queue.sh          # needs the local Showdown server up
python scripts/mech200m_readout.py
```

Read plan, registered BEFORE any number below existed: `configs/eval/mech200m.yaml`
(commit 12aaa18). Branches restated verbatim from `configs/showdown_monster200m.yaml`
[RWL-3]. **This read credits nothing by itself; it decides whether the already-banked
off-FP@20 and vs-SH numbers MAY be credited.**

## The verdict in five lines

1. **Branch 1 FIRES: width is LIVE, not idle.** In the first layer of the critic's
   value stack the wide critic holds **srank99 632 of 1024 (0.617)** where the two
   384-wide critics hold **27 of 384 (0.069)** and **5 of 384 (0.013)**. The delta is
   8x the across-lane spread and both obs protocols agree in sign.
2. **Branch 2 does NOT fire.** The ceiling branch required srank99 "pinned near ~48
   absolute at 2.67x width". It is 632. There is no measured ceiling here, and under
   CLAUDE.md rule 6 nothing else is allowed to kill the lever.
3. **Branch 3's condition is INVERTED.** It required EV to move while the win rate
   did not. **EV did not move** (W 0.5881 vs the 100M lanes' 0.5919 — the 0.59 plateau
   is exactly where it was) **and the win rate did** (+0.033 vs SH, +0.046 off FP@20).
4. **The manipulation check passes**: L2LAM's `loss/adv_std` is **1.83x** W's, so
   lambda 1.0 took and the L2LAM arm is a valid comparison.
5. **So the credit is LICENSED — for the RECIPE, not for width as a separable lever.**
   No contrast isolates width: W vs 100M bundles width + L2 + horizon; W vs L2LAM
   bundles width + the value target. Width is the only factor common to both, and it
   is measured to be used — that is what licenses the recipe-level credit, and it is
   the whole of what the mechanism shows.

## M1 — critic ctx srank99 as a FRACTION OF WIDTH (the PRIMARY)

At the finals, on the SHARED pooled obs (the cross-arm read; the per-lane pass agrees
in sign at both layers):

| arm | critic width | ctx_net.1 (first) | fraction | ctx_net.3 (output) | fraction |
|---|---|---|---|---|---|
| **W** (L2 + 1024 critic, 200M) | 1024 | **632** (707/573/616) | **0.617** | **24** (18/32/22) | **0.023** |
| L2LAM (L2 + MC targets, 200M) | 384 | 26.7 (33/22/25) | 0.069 | 161.7 (174/138/173) | 0.421 |
| 100M baseline (no L2, 100M) | 384 | 5.0 (4/4/7) | 0.013 | 93.7 (103/64/114) | 0.244 |

**THE TWO ARMS COLLAPSE AT OPPOSITE ENDS OF THE STACK, and that is the finding.** The
384-wide critics destroy their representation in the FIRST layer — the 100M baseline
keeps **five** significant directions out of 384 — and partially re-expand afterwards.
The 1024-wide critic keeps 632 directions through the first layer and compresses at
the output instead. A critic emits one scalar, so a low-rank OUTPUT layer is expected
and is not a pathology; a rank-5 FIRST layer is the pathology, and width is what
prevents it. Note L2LAM has L2-toward-init and the 100M baseline does not, and BOTH
collapse: **L2 does not prevent the first-layer collapse; width does.**

*A measurement trap, recorded because it reversed this verdict once.* The probe's
`srank99_ctx` is the hook on `net.ctx_net`, i.e. the stack's OUTPUT layer, while its
dormant table carried `ctx_net.1`, the FIRST layer — because the skip rule read
`".3" in name`, meaning "the LayerNorm slot", and on every checkpoint this repo has
trained `ctx_net.3` is the second ReLU. The first version of this readout therefore
compared the wide critic's output rank against the narrow critics' first-layer
dormancy and called it a ceiling. `scripts/d22_dormant_rank.py` now skips by module
TYPE and `--layer-ranks` records the whole stack.

## M2 — dormant fraction (the same fact, seen twice)

| arm | ctx_net.1 tau .025 | ctx_net.3 tau .025 |
|---|---|---|
| **W** | **0.359** | 0.973 |
| L2LAM | 0.969 | 0.188 |
| 100M | 0.987 | 0.333 |

## M3 — explained variance: THE 0.59 PLATEAU DID NOT MOVE

Tail (last 5% of updates): **W 0.5881** (across-lane sd 0.0006), 100M baseline
**0.5919** (sd 0.0014), L2LAM 0.2024 — the L2LAM column is NOT evidence about the
critic and is printed only because [RWL-3] names it (lambda 1.0 targets carry the
outcome noise; the pre-reg says so verbatim). W vs the 100M lanes IS like-for-like:
both are TD targets at gae_lambda < 1.

At matched rungs the wide critic DOES fit better mid-run and then gives it back:

| trio mean EV | 500k | 12M | 50M | 100M | 150M | 200M |
|---|---|---|---|---|---|---|
| W | 0.491 | 0.688 | 0.671 | 0.675 | 0.647 | 0.596 |
| 100M baseline | 0.532 | 0.634 | 0.609 | 0.592 | — | — |
| L2LAM | -0.042 | 0.158 | 0.231 | 0.233 | 0.140 | 0.250 |

**This is the most decision-relevant line in the read: 2.67x the critic width and
126x the first-layer rank buy ZERO explained variance at the horizon.** Whatever the
wide critic is worth, it is not "the critic fits the returns better", and the next
fleet must not be sized on EV.

## M4 — adv_std: the L2LAM manipulation check PASSES

W **0.4855**, 100M baseline 0.4825, L2LAM **0.8882** = **1.83x** W. [RWL-3]'s gate
was "must sit materially higher on L2LAM or lambda did not take". It took.

## M5 — l2init anchor distances (ACTOR-side only)

| anchor | W | L2LAM | delta |
|---|---|---|---|
| actor_lnfree | 31.615 | 31.456 | +0.159 |
| ctx_net | 26.755 | 27.012 | -0.257 |
| move_emb | 3.027 | 3.216 | -0.189 |
| scorer | 16.039 | 15.227 | +0.811 |
| slot_bias | 0.071 | 0.088 | -0.017 |
| species_emb | 4.157 | 4.194 | -0.037 |

L2 bit essentially equally hard on the two arms' actors (the one visible gap is the
scorer, +5% on W). **KNOWN GAP, stated in the plan before the read: every logged
anchor is ACTOR-side, there is no critic anchor metric and no logged critic
pre-activation norm, so M5 cannot speak about the critic at all.**

## M7 — the credit line, both halves, computed from the per-lane finals

| contrast | delta | se_binom | se_seed-clustered | larger | verdict |
|---|---|---|---|---|---|
| off FP@20, W singles vs the 100M re-draw | **+0.0464** | 0.0074 | 0.0097 | 0.0097 (4.79 se) | **MEETS THE CREDIT LINE** |
| off FP@20, W singles vs L2LAM singles | **+0.0936** | 0.0074 | 0.0088 | 0.0088 (10.61 se) | **MEETS IT** |
| vs SH, GW vs the banked 100M greedy A0 | **+0.0330** | 0.0059 | 0.0035 | 0.0059 (5.59 se) | **MEETS IT** |
| vs SH, GW vs GL | **+0.0439** | 0.0060 | 0.0036 | 0.0060 (7.37 se) | **MEETS IT** |
| vs SH, E3W (the ladder object) vs the 100M ENS3 floor | +0.0150 | 0.0056 | 0.0075 | 0.0075 (2.01 se) | **DOES NOT** (misses the floor) |

The seed-clustered half is the binding one on both off-FP rows — as the larger-of
clause exists to ensure.

**The last row is not a footnote.** At the COMMITTEE level the 200M recipe does not
clear the floor over the 100M committee: +0.015 at 2.01 se, failing the +0.025 floor.
The recipe gain and the committee gain substantially SUBSTITUTE for each other rather
than adding — which is a direct input to the next fleet's shape, and it is why the
ladder object's advantage over what we already had is smaller than the singles
comparison suggests.

## What this licenses, exactly

- **LICENSED:** "the W recipe (regenerative L2-toward-init + a 1024-wide critic) at
  200M beats the 100M baseline by +0.033 vs SH and +0.046 off FP@20, both clearing
  the credit line on the larger of the two se_diffs, and the mechanism read confirms
  the added critic capacity is USED rather than idle."
- **NOT LICENSED:** "the wide critic is worth +0.033" (no contrast isolates width);
  "a wider critic fits the value function better" (measured FALSE — EV is flat at
  0.59); "ensembling the 200M finals beats the 100M committee" (the E3W row misses
  the floor); any claim that the L2LAM/MC-target arm was mis-run (the manipulation
  check passes, so it is a fair comparison that simply lost).
- **RULE 6:** nothing here kills anything. The ceiling branch did not fire, and an
  unresolved or flat mechanism is never a kill.

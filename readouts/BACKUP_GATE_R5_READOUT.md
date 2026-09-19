# BACKUP_GATE_R5 — readout

**Block:** `configs/eval/backup_gate_r5.yaml` · **run:** 2026-09-18/19 ·
**data:** `results/backup_gate_r5/` · **status:** hacking run, `credits_nothing: true`

**Object:** the R5 committee (log-pooled `w104` / `w112` / `w120`, the 200M
W-recipe finals — the LADDER R5 object). **Instrument:** Foul Play head-to-head
at `--search-time-ms 20`, seat `w112`. **n = 1000 battles per phase-R arm.**

---

## The one-line result

**Every arm that searched read BELOW the greedy committee.** The in-session
greedy anchor **GC = 0.6050** is the highest number in the block. The ungated
depth-1 arms sit below it at ~2.4 se and the depth-2 arms at 3.4–4.4 se; the
gated arms sit between and are separated from neither.

> **NOT MONOTONE, and RESULTS §30 corrects an earlier claim here that it was.**
> Ordering the arms by how often they change the played action, **0.584 at 6.4%
> RISES to 0.587 at 9.1%**, and `B2O`'s 0.529 at 12.5% sits below `DUM`'s 0.553
> at 15.3%. Such a list also **mixes vehicles** — GC searches nothing, DGV/DRV
> are gated, DUM/D1O/B2O/B2R ungated — which is the frame §26.1 retired ("the
> VEHICLE separates them, and the override rate does not"). **This block does
> not establish a monotone relation with the change rate.** What it establishes
> is the level ordering above.

| arm  | what it is                              | searched | overrides / ALL decisions | **win rate** |
|------|-----------------------------------------|---------:|--------------------------:|-------------:|
| GC   | greedy committee, **the anchor**        |     0.0% |                    0.0000 |   **0.6050** |
| DGV  | disagreement-gated, dose M              |    40.2% |                    0.0846 |   **0.5870** |
| DRV  | **coin** at DGV's realized rate, dose M |    40.5% |                    0.0596 |   **0.5840** |
| DUM  | ungated, dose M, every decision         |    93.4% |                    0.1525 |   **0.5530** |
| D1O  | ungated, dose M — **DUM's replicate**   |    93.3% |                    0.1590 |   **0.5510** |
| B2O  | depth 2, OLD backup, δ 0.12             |    94.3% |                    0.1247 |   **0.5290** |
| B2R  | depth 2, **minimax fix**, δ 0.08        |    94.2% |                    0.1753 |   **0.5070** |

Ties are non-wins (0–2 per arm). All seven arms: 1000/1000 battles finished,
0 mask desyncs.

---

## R0 — the block's own noise floor, and why the rest is readable

The pre-reg ran **D1O and DUM as the SAME CONFIGURATION on two username pairs**
and pinned in advance: *"If D1O and DUM differ by more than 0.02, the block's
own noise floor is larger than the effects it is looking for."*

> **D1O 0.5510 vs DUM 0.5530 — |Δ| = 0.0020. GATE PASSES, with room to spare.**

That is the most important number here. One rung of this instrument is worth
±0.02 across sessions (three re-draws of one checkpoint spread 0.0200), and this
block's *within*-session replicate lands at a tenth of that. Every delta below
is read against a measured floor rather than an assumed one.

**SIX OF SEVEN R0 GATES PASS. `G_OVERRIDE_MATCHED` FAILS** — it requires ≤0.03
for B2R *and* B2O, and **B2O misses by 0.0382**; the block's own readout prints
`AT LEAST ONE R0 GATE FAILED` as its last line, and the B2O design error below
is the same fact stated twice. The six that pass: `opp_replies` 2.00/1.00,
`minimax_drop` **0.0566**/0.0000 (the new backup genuinely fired, large against
δ 0.08), both search rates matched to 0.0004, the cap not binding at 1865
grandchildren against 6000, and the replicate above.

---

## Half one — IDEAS 2.10: does an HONEST depth-2 backup pay?

**It does not. It made depth-2 WORSE.**

    B2R (minimax fix)  0.5070   override 0.1862
    D1O (depth 1)      0.5510   override 0.1703      <- matched within 0.016
    B2R - D1O  =  -0.0440   se 0.0223   1.97 se

The matched comparison is **B2R − D1O** (see the pre-reg's mid-block design-error
disclosure: B2O's δ was hardcoded rather than swept, so **B2R − B2O is the
MISMATCHED one**). The fix fired, moved values by 0.057 on a δ-0.08 scale, and
cost 4.4 points.

> **NOT SUPPORTED: "the leaf optimism is WHY depth-2 hurts."** §24's story was
> that `_look_further` maxed over our replies with the opponent pinned, so rows
> with more escape hatches inflated and the root overrode into them. Giving the
> opponent answers and backing up max-of-min does not recover the loss — it
> deepens it.

**B2R − B2O = −0.0220 at 0.98 se is UNINTERPRETABLE and is not read**, per the
pre-reg's own asymmetry rule written before the numbers existed: B2R acts ~41%
more often than B2O on an axis where acting more is known to hurt, so
`B2R > B2O` would have been a strong result and `B2R < B2O` says nothing.

**This does NOT close depth.** It closes *this vehicle's* depth-2 at this
budget. `rl/search/tree.py` is a different algorithm, and a true minimax at
every ply is untried.

---

## Half two — IDEAS 8.5: does the committee know WHERE to spend the budget?

**No. A coin does just as well, and both beat spending everywhere.**

    DGV (committee-gated, 40.2%)   0.5870
    DRV (coin at the same rate)    0.5840
    DGV - DRV  =  +0.0030   se 0.0220   0.14 se

The two arms are matched on everything the block could match: same object, same
dose M, same `margin_delta` 0.05, same ~40% searched fraction (DRV's threshold
0.563 was pinned **arithmetically** from DGV's measured 0.437, not screened).
The only difference is *which* decisions were searched — and it is worth
**+0.003**.

**Concentration is a different question from selection, and it reads
differently.** Pooling both gated arms against both ungated replicates (the
symmetric choice): **+0.0335 at 2.14 se**, which clears both halves of the
credit line. **The pooling is post-hoc on both sides and this block credits
nothing** — but "searching 40% of decisions beat searching 93%" is the live
result here, and it is the opposite of the dose intuition. (RESULTS §30 first
published this as "+0.0325 at 1.69 se, misses the 2·se bar"; that figure pooled
two gated arms against only ONE of the two identical ungated arms, and is
corrected there.)

**What the SELECTION null does and does not say.** At n=1000/arm the se on this delta is
0.0220, so an effect at the credit line (0.025) sits ~1.1 se from the point
estimate: **this does not EXCLUDE a credit-sized selection effect, and it is not
quoted as a kill.** What it does say is that the point estimate is +0.003 rather
than +0.03, and that `votes ≥ 1/3` on a three-member committee is not the signal
that would have shown up here if one were sitting in plain sight. The natural
follow-ups are a *different* signal (margin, entropy, critic disagreement — 8.5
lists them) and a bigger dose on the selected decisions, not more n on this cut.

---

## The graded picture — a TREND, explicitly not a monotone law

Pooling the arms by how much of the game they handed to the search:

| searched fraction | arms        |     n | win rate |
|------------------:|-------------|------:|---------:|
|                0% | GC          |  1000 |   0.6050 |
|               40% | DGV + DRV   |  2000 |   0.5855 |
|               93% | DUM + D1O   |  2000 |   0.5520 |

    0%  -  40%  =  +0.0195   se 0.0190   1.03 se
    40% -  93%  =  +0.0335   se 0.0157   2.14 se
    0%  -  93%  =  +0.0530   se 0.0190   2.78 se   <- the ENDS separate

Regressing win rate on **overrides as a fraction of ALL decisions** — the
quantity that says how much of the policy was actually replaced — across all
seven arms:

    win = 0.6113 - 0.4807 * override_fraction      pearson r = -0.875

* **Each 1% of decisions handed to the search costs ≈ 0.48 points of win rate.**
* The fit survives leave-one-out: dropping any single arm leaves the slope in
  −0.40…−0.56 and r in −0.82…−0.91, so no one arm is carrying it.
* **The intercept, 0.6113, lands within 0.006 of the measured greedy anchor
  0.6050** — a check the fit never got to use.

**How to read it, and how not to.** This is a **descriptive** relationship over
seven arms that differ in more than one way. `override_fraction` is not
separable from `searched_fraction` here — an arm that searches more overrides
more by construction — and the three-rung pooling **mixes vehicles**, so it
inherits §26.1's objection in full. **The fit is a trend with r = −0.875 and
two inversions in the raw ordering, not a law**; the 0%–40% step is itself only
1.03 se. It is not a credited effect and it is not a mechanism ceiling.

What it is worth: the ends separate at 2.78 se, the fit survives leave-one-out,
and its intercept reproduces the measured anchor to 0.006. Read alongside §21
(width bought zero EV), §26 (no tree arm beat greedy) and §30 (greedy beat
every search arm), it is the first *graded* version of a result this project has
so far only seen as a sequence of binary nulls. **The value is as a target for
the next search idea to argue against**, not as a number to cite.

---

## Provenance and disclosures

* **Session offset, visible and expected.** GC 0.6050 sits +0.0285 above the
  banked three-draw greedy pool (0.5765, n=4500, different sessions). That is
  the ~0.02 instrument offset this project measures repeatedly, and it is
  exactly why the block bought an in-session anchor. **No number here is
  differenced against a banked cross-session arm.**
* **CONTAMINATION, DUM, 2026-09-19 01:56–01:59Z — MEASURED, and it went the
  OTHER WAY.** A second chain started 23 s after DUM launched and ran beside it
  ~2.8 min before being killed. **35 of 1000 battles** ran inside the window at
  5.5 s/battle against DUM's clean 3.0. The *prediction* was that contention
  weakens a **time-boxed** opponent and so flatters DUM. **The measurement
  refutes the prediction:** those 35 battles read **0.4571** against the
  remaining 965 at **0.5565** — 1.2 se in the direction OPPOSITE to the one
  predicted, i.e. **the contamination is not visible above noise.** Reported
  this way because the pre-reg promised a measurement rather than an argument.
  Both guard holes are fixed in `scripts/night_queue2.sh` (frozen-mktemp names
  now matched; six consecutive clear checks, longer than the 30 s inter-arm
  sleep).
* **`concurrent_decision_rate` in these JSONs is computed on a BAD DENOMINATOR**
  (`_decision_index`, which the placeholder path does not advance) — DRV's
  1.15625 is a rate above 1, which is how it was caught. Fixed 2026-09-19 in
  `scripts/ch3_fp_h2h.py`; **the win rates and override counts are unaffected**,
  and `max_concurrent_live_battles` (2 for B2O and DRV, 1 elsewhere) is the
  field that was actually load-bearing.
* **B2O's δ was hardcoded, not swept** — a design error found mid-block after
  B2O ran, disclosed in the config and **deliberately not re-pinned**, because a
  selection rule re-run after an outcome is visible stops being a selection rule.
* Phase-S win rates (B2A/B2B/B2C/GV, n=60) are **rate-pinning cells, not
  reads**; se at n=60 is 0.065.
* The smoke (SMK, n=2) ran on a throwaway username pair because neither `opp_k`
  nor `disagree` had crossed the Foul Play seat path before.

## Barred, by name

"Search does not work" (this is one vehicle, one dose, one budget, one
opponent); "the committee's disagreement signal is dead" (the point estimate is
+0.003 at 0.022 se — that is not exclusion); "depth is closed" (`tree.py` is a
different algorithm and a true per-ply minimax is untried); any cross-session
difference taken against a banked arm; and reading the override regression as a
credited effect.

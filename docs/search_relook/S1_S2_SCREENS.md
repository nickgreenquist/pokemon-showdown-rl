# Search relook — screens S1 and S2

Two offline screens on the existing chapter-3 search line. Together they
decide whether the relook's next build is **(a) the leaf encoder** or
**(b) depth**. Nothing here is letter-bearing: both are screens, not rungs,
and neither is a verdict input for any headline number.

- Script: `scripts/search_s1_s2_screens.py`
- Sample: the four D26 lanes pinned in `configs/eval/ch3_rung2.yaml`
  (`s62..s65`, 12M checkpoints, sha256-pinned), 200 non-aliased harvested
  decisions per lane strided with `np.linspace` over the lane's non-aliased
  pool exactly as `scripts/ch3_r1_spike.py` does = **800 decisions**.
- Data: `results/ch3_r1/harvest_<lane>.pkl` — the PUBLIC harvest only, never
  `harvest_priv_*` (FG-4).
- Offline: no server, no battles, no websocket. One process, torch threads 2.
- Output: `results/search_s1_s2/s1.json`, `results/search_s1_s2/s2.json`.

---

## 1. The read rules — PRE-REGISTERED, written before the numbers

These two paragraphs were written into the script docstring and into this
file before `search_s1_s2_screens.py` was run. Section 3 read `PENDING`, with
no numbers of any kind in it, at the moment the run launched. Nothing in
sections 1 and 2 changed after the numbers landed except the verification note
in §2, which records checks that were themselves run before the launch.

### S1 — leaf-encoding bias vs decision margin

> **S1 FIRES if the pooled sd of Delta (across decisions and
> determinizations) >= the median row_ev margin — the encoding artefact is
> then as large as the decision itself and the leaf encoder is the first fix,
> before any depth work.**

Also reported, declared in advance, none of them the firing condition:

- the fraction of decisions with `|mean Delta| > margin`;
- the **mean signed Delta** — is the artefact a consistent bias (does a
  determinized, fully-revealed opponent bench read *stronger* or *weaker* to
  the critic than the live unknown bench?);
- the sd of `row_ev` across legal rows, as a second scale for the decision;
- everything above, per lane.

### S2 — budget headroom by flip rate

> **S2 IS ONE-DIRECTIONAL.** R3 measured flip rate RISING with evaluator
> noise while wins FELL (flips are not wins), so a high flip rate proves
> nothing; but a LOW one bounds headroom: **if L flips < 5% of M's
> decisions, then at ~38 decisions/battle a 4x budget touches < 2 decisions
> per battle and cannot plausibly move win rate past the 0.025 credit line.**

`38 decisions/battle` is the pre-stated constant and is the conservative
direction: a *larger* decisions/battle makes "< 2 decisions touched" *harder*
to satisfy, so the bound cannot be flattered by it. The harvest-measured
searchable-decisions-per-battle is computed alongside and reported as a
secondary read.

Also reported, declared in advance: flip rates M-vs-recorded-greedy and
L-vs-recorded-greedy; and, among the L-vs-M flips, the mean and median Dose-M
`row_ev` margin — were the flips close calls? Everything per lane and pooled.

---

## 2. What is actually measured, and the honest attribution

### S1 construction

For each decision:

1. `v_root = critic(row["obs"])` — the **LIVE** encoding of the root, the
   same 828-d vector the policy acted on during the harvest.
2. `rng = decision_rng(cfg.seed, episode, battle.turn, step)`, then four
   sequential `sample_determinization(battle, rng)` draws. Because
   `matrix.solve_decision` builds its determinizations the same way from the
   same key, **these are byte-identically the four determinizations Dose M
   uses on that decision** — not an independent redraw. Verified offline before
   the run on 8 probed decisions by injecting a recording `det_fn` into a
   `SearchAgent`: S1's four dets equal M's four, and L's first four equal M's
   four, in every case. (One rehydrated `Battle` object serves S1, M and L —
   also verified: two `act` calls on one object and a third on a fresh one
   return the same action on 8/8, so `act` does not mutate the battle.)
3. For each det: `state = battle_to_state(battle, det, BridgeCounters())`
   (the **ROOT** State, no instruction branch applied), then
   `v_det = critic(embed_battle(shadow_battle(state, turn=battle.turn), type_chart))`.
   This is FG-6's construction verbatim
   (`scripts/ch3_fidelity_check.py::fg6_encoder_parity`), and it is a leaf's
   encoding in every respect except (i) the turn dim carries the root turn
   rather than `turn + 1` and (ii) no `apply_instructions` has run. Those are
   the only two substitutions; nothing else about the encode path differs
   from what a leaf gets.
4. `Delta = v_det - v_root`, four per decision.
5. The decision's own scale: a normal `SearchAgent(agent, DOSES["M"]).act(...)`
   on the same decision, `margin = top1 - top2` over `stats["search/row_ev"]`.

**Attribution — which non-parity families this Delta carries.** The root
encoding is not "the live encoding plus the bench reveal". It carries every
family `shadow_battle`'s docstring declares plus the ones FG-6 measured, and
Delta prices all of them jointly. FG-6's measured per-dim counts over 13,396
roots (`results/ch3_r1/fg_battery.json`), in dims-differing per root:

| family | count | per root | max abs dim diff | what it is |
| --- | ---: | ---: | ---: | --- |
| `det_unrevealed_bench` | 453,544 | 33.86 | 4.0 | the determinized opponent bench is encoded as REVEALED; the live obs encodes it as unknown |
| `slot_known_prob` | 12,246 | 0.91 | 0.789 | det shows p=1.0 where battle1 shows the prior's p |
| `pp` | 12,189 | 0.91 | 1.0 | poke-env never decrements the opponent's PP; the engine defaults it |
| `opp_hp_grain` | 7,888 | 0.59 | 0.0025 | engine exact HP vs battle1's /100 public fraction |
| `transform_ditto` | 4,177 | 0.31 | 3.5 | copied stats unrepresentable from the static dex |
| `preparing` | 47 | 0.004 | 1.0 | FLY/DIG modelled as volatiles we do not map back |
| `root_trapped` | 3 | 0.0002 | 1.0 | gen-1 partial-trap flag |
| `sleep_rest_counter` | 1 | 0.0001 | 0.0625 | engine splits sleep/Rest, poke-env conflates |

Plus one family that is structurally invisible here: **lightscreen is
unobservable from `battle1`** (poke-env 0.15 has no `Effect.LIGHT_SCREEN`), so
it is a named unmodellable, not a diff.

`det_unrevealed_bench` dominates by ~37x the next family, so Delta is
overwhelmingly the **bench-reveal artefact** — but it is not *only* that, and
the number below is reported as the joint figure, not as a bench-only figure.

### S2 construction

Same 800 decisions, two `SearchAgent` instances over the same loaded agent
with the same `checkpoint_seed=cfg.seed`, Dose M (`n_det=4`, node cap 1500)
and Dose L (`n_det=16`, no node cap). Both key the same `decision_rng`, and
determinizations are drawn sequentially from it, so **L's first four dets are
M's four dets** — L is a strict superset of M's determinization sample, which
is the right comparison for a budget screen (it isolates *more samples*, not
*different samples*).

Watchdog trips at M and placeholder skips are counted and excluded from the
flip statistics; they are reported, not hidden.

---

## 3. The numbers

Run 2026-09-10 11:23-11:52 EDT, one process, `taskpolicy -b`, torch threads 2,
800 decisions (200/lane), wall **28.7 min**. `results/search_s1_s2/{s1,s2}.json`
(under `results/`, which is gitignored — this file is the committed provenance).
Disclosure: after the run the script was tidied cosmetically — one import
hoisted to module scope and a one-line wrapper inlined. No logic, constant or
output changed; re-smoked at `--per-lane 2` to confirm.

**Zero watchdog trips at M, zero at L, zero placeholder skips, zero
determinization errors — 800/800 decisions searched at both doses.** S1's
margin is undefined on **19** decisions that had exactly one legal action
(forced replacement with one live mon); those are dropped from S1's pooled
read, leaving **781** decisions / **3,124** Delta samples. They are kept in
S2, where a flip is still defined (both doses must pick the one legal action,
so they contribute non-flips).

**Timing is CONTENDED and descriptive, never a budget number.** The box was
running the seven-wide `search_s3_100m` eval fleet throughout. Measured here:
**430.3 ms/decision at M, 1698.7 ms at L** against R3's clean-box 65-68 ms and
253-269 ms — 6.3-6.6x inflated by contention. The *search itself* is
unaffected and that is checkable: **leaves/decision at M = 350.8**, against the
R1-0 spike's frozen baseline of **353.1** (0.6% off, well inside F3's +/-25%
band), and L/M = **4.00x** in leaves, exactly the n_det ratio. The screens
measure decisions, not wall.

### S1 — pooled (781 decisions, 3,124 Deltas)

| quantity | value |
| --- | ---: |
| **pooled sd(Delta)** | **0.12544** |
| **median row_ev margin (Dose M)** | **0.02773** |
| ratio sd(Delta) / median margin | **4.52** |
| **S1 FIRES** | **YES** |
| fraction of decisions with \|mean Delta\| > margin | **0.612** |
| **mean signed Delta** | **+0.04974** (se by decision 0.00304 = **+16.3 se**) |
| median signed Delta | +0.02931 |
| fraction of Deltas > 0 | 0.661 |
| mean \|mean Delta\| | 0.07079 |
| median \|mean Delta\| | 0.04946 |
| mean within-decision sd(Delta) over the 4 dets | 0.08569 |
| between-decision sd of mean Delta | 0.08507 |
| mean row_ev margin | 0.05142 |
| mean sd(row_ev) across legal rows | 0.08882 |
| median sd(row_ev) across legal rows | 0.07620 |
| mean v_root | +0.2421 |

Delta percentiles: p1 -0.2722, p5 -0.1410, p25 -0.0106, p50 +0.0293,
p75 +0.1171, p95 +0.2815, p99 +0.3812.
Margin percentiles: p5 0.00040, p25 0.00860, p50 0.02773, p75 0.06487,
p95 0.17953.

Two further measured facts, both declared as "everything per lane / secondary"
and neither the firing condition:

- **corr(|mean Delta|, margin) = +0.024.** The artefact is essentially
  uncorrelated with how hard the decision is. It is not concentrated on the
  easy calls where it would be harmless.
- **70.6% of decisions have their within-decision sd(Delta) alone larger than
  their own margin** — i.e. the spread the artefact shows *across the four
  determinizations of one decision* already exceeds the gap the solver is
  resolving, before any between-decision variation is counted.

### S1 — per lane

| lane | sd(Delta) | median margin | ratio | fires | mean signed Delta | frac \|mean D\|>margin | frac D>0 | mean v_root | n |
| --- | ---: | ---: | ---: | :-: | ---: | ---: | ---: | ---: | ---: |
| s62 | 0.11898 | 0.02563 | 4.64 | **YES** | +0.05623 | 0.648 | 0.676 | +0.2607 | 196 |
| s63 | 0.13157 | 0.03038 | 4.33 | **YES** | +0.05170 | 0.574 | 0.645 | +0.1974 | 195 |
| s64 | 0.11564 | 0.02817 | 4.11 | **YES** | +0.04713 | 0.615 | 0.688 | +0.2312 | 192 |
| s65 | 0.13420 | 0.02668 | 5.03 | **YES** | +0.04391 | 0.611 | 0.636 | +0.2783 | 198 |

**All four lanes fire independently, all four ratios in 4.1-5.0, all four mean
signed Deltas positive at +0.044 to +0.056.** The screen is not carried by one
lane and the bias is not a one-lane artefact.

### S2 — pooled (800 decisions)

| quantity | value |
| --- | ---: |
| **flip rate L vs M** | **0.0675** (54/800) |
| **S2 low-flip bound holds (rate < 0.05)** | **NO** |
| decisions touched/battle @ 38 (pre-stated) | **2.57** |
| decisions touched/battle @ 26.79 (measured) | 1.81 |
| flip rate M vs recorded greedy | 0.4888 |
| flip rate L vs recorded greedy | 0.4938 |
| **mean Dose-M margin at the L-vs-M flips** | **0.01006** |
| median Dose-M margin at the L-vs-M flips | 0.00470 |
| mean Dose-M margin at non-flips | 0.05449 |
| median Dose-M margin at non-flips | 0.03038 |
| mean \|mean Delta\| at the L-vs-M flips | 0.08594 |
| mean \|mean Delta\| at non-flips | 0.06966 |
| ms/decision M (contended) | 430.3 |
| ms/decision L (contended) | 1698.7 |
| leaves/decision M | 350.8 |
| leaves/decision L | 1402.9 |

### S2 — per lane

| lane | flip L vs M | n | flip M vs greedy | flip L vs greedy | mean margin at flips | mean margin at non-flips |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| s62 | 0.0550 | 11/200 | 0.4750 | 0.4750 | 0.01855 | 0.05140 |
| s63 | 0.0700 | 14/200 | 0.4800 | 0.4900 | 0.00836 | 0.06344 |
| s64 | 0.0850 | 17/200 | 0.4950 | 0.5100 | 0.00671 | 0.04955 |
| s65 | 0.0600 | 12/200 | 0.5050 | 0.5000 | 0.00903 | 0.05352 |

**Every lane is above the 5% threshold** (0.055-0.085), so the bound fails on
every lane, not just pooled.

The M-vs-recorded-greedy flip rate of 0.489 sits next to the R1-0 spike's 0.51
on 200 decisions of the same harvest — consistent, and a check that this is the
same instrument.

The harvest-measured searchable-decisions-per-battle is **26.79** (per lane
27.55 / 25.94 / 27.58 / 26.09; 3,444 / 3,243 / 3,448 / 3,261 non-aliased rows
over 125 episodes each), not 38. **The pre-stated 38 is what the bound is read
against**, and the trigger is the 5% flip-rate threshold, which is not met.
Note the arithmetic *would* land under 2 decisions/battle at the measured 26.79
(1.81) — but the rule as registered gates on the flip rate, and 6.75% is not
below 5%. The screen does not get to claim the bound on a constant swapped in
after the fact.

### Prior live evidence these screens sit beside

Not part of either read rule; recorded so the verdict is not read in a vacuum.
Both are on these same four 12M lanes, vs SH, locked protocol, 3000/lane.

- **R3 seg2, dose M -> dose L (the exact 4x this screen proxies):** pooled
  **+0.0025**, se_clustered 0.0055, CI **[-0.0086, +0.0136]**, bar 0.0125 —
  NOT met, landing cell T2b (`results/ch3_r3/r3_readout.json`). Per lane
  -0.0037 / +0.0190 / -0.0043 / -0.0010. The live 4x was already measured and
  bought essentially nothing.
- **R4, swapping the LEAF EVALUATOR (leave-one-out critic ensemble) at the
  same dose M:** pooled **+0.02242**, se_gov 0.00798 (paired-clustered),
  cell **B3 FLAT** — just under the +0.025 credit line
  (`results/ch3_r4/r4_readout.json`). Per lane +0.0457 / +0.0173 / +0.0173 /
  +0.0093.
- **R3 E-cells, the evidence behind S2's one-directional rule** (n=1000, lanes
  s63/s65): as evaluator noise rises E2A -> E2B -> E2C, win rate falls
  0.732/0.729 -> 0.636/0.635 -> 0.480/0.412 while **flip rate rises**
  0.561/0.585 -> 0.597/0.613 -> 0.649/0.662. Flips are not wins.

An evaluator change bought ~9x what a 4x budget bought, on the same object,
under the same protocol. S1 says the evaluator's *input* is corrupted by
0.125 sd / +0.050 mean at a decision scale of 0.028.

---

## 4. Verdict

1. **S1 FIRED, on the pre-registered rule, on all four lanes.** Pooled
   sd(Delta) = **0.1254** against a median Dose-M margin of **0.0277** — ratio
   **4.5x**; 61% of decisions are moved by more than their own top1-top2 gap,
   and the artefact is uncorrelated with margin (r = +0.02), so it is not
   confined to decisions that were easy anyway.
2. The artefact is a **bias, not noise**: mean signed Delta **+0.0497**
   (+16.3 se, 66% of Deltas positive, all four lanes +0.044..+0.056). A
   determinized root reads systematically **better for us** than the live root
   — every leaf is valued against an optimistically shifted baseline, which is
   the same direction as the design's already-declared switch-in optimism.
3. **S2's bound does NOT hold**: L flips **6.75%** of M's decisions (5.5-8.5%
   per lane), above the 5% threshold, so the screen is **silent by
   construction** — it neither licenses depth nor rules it out, and a 6.75%
   flip rate is not evidence *for* depth (R3: flips rose with noise while wins
   fell). What it does show is that the flips are **close calls**: mean Dose-M
   margin 0.0101 at a flip vs 0.0545 at a non-flip (5.4x), and 0.0101 is
   **one fifth** of the encoding bias S1 measured — 4x the budget is
   re-deciding decisions that sit well inside the encoder's own error.
4. **Next build is (a) the leaf encoder.** S1 fired; S2 returned nothing; and
   the live record agrees with that ordering — R3 already measured the M->L 4x
   at **+0.0025 [-0.0086, +0.0136]** while R4's evaluator swap at the same dose
   measured **+0.0224**, ~9x more, on the same four lanes.
5. **Cost asymmetry seals the order.** L costs 4.00x M's leaves (1402.9 vs
   350.8) for a 6.75% touch rate on the cheapest decisions in the set; a leaf
   encoder fix costs nothing at search time. Build the encoder, re-measure S1,
   and only then put depth back on the table.

### Not claimed

- **Neither screen is a win-rate measurement.** S1 prices the encoding artefact
  in value units; it does not show that removing it wins battles. Whether a
  leaf-encoder fix crosses +0.025 still needs a pre-registered rung with
  battles.
- **S1 measures the artefact at the root, not the residual after row-wise
  cancellation.** Inside one decision every row shares the same four
  determinizations, so any component of the artefact common to all rows of a
  determinization cancels exactly in the `top1 - top2` the solver reads. What
  survives is the part that varies **across rows** — across the different
  successor states each action leads to — and this screen does not decompose
  that. It cannot: the counterfactual "what the critic would say about this
  *leaf* under the live encoding" **does not exist**, because the live encoding
  is only defined on states the server actually produced. The root is the one
  state where both encodings exist, which is exactly why the artefact is priced
  there. Read S1 as the magnitude of the input corruption, not as a bound on
  the decision error it induces.
- **Delta is the joint figure over every non-parity family** in the table in
  §2, not a bench-only figure — though `det_unrevealed_bench` outweighs the
  next family ~37:1 in dims touched.
- **The measured 6.75% flip rate is not a claim that depth is dead.** S2 was
  registered as one-directional; a failed low-flip bound is silence. The
  argument against depth-first in line 4 rests on R3's live M->L measurement
  and R4's evaluator delta, which are letter-graded rungs, not on this screen.
- **Timing here is contended** (seven-wide eval fleet on the box) and is not a
  budget number for any dose.

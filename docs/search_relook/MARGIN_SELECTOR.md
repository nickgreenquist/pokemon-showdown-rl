# The margin-gated selector — a confidence threshold on depth-1 search

Built 2026-09-10, acting on `docs/prior_work/WANG_SEARCH_DEEP_READ.md` §2 and
its hypothesis **H2** ("the highest-value cheap test"). The finding it acts on:
our depth-1 search costs **6.8 points** against greedy on the 100M finals
(S3M **0.72056** vs A0 **0.78867** vs `SimpleHeuristicsPlayer`, 3×3000 each,
`S3_READOUT.md`), while Wang's MCTS on a comparable-strength network **gained
12 points** using the *unmodified PPO critic* as its leaf evaluator. "Our
critic is bad" does not by itself explain the sign.

`margin_delta` is an **option**, not a replacement. With it off — the default,
and what every banked search arm ran — `solve_decision` is byte-for-byte
unchanged; §4 pins that against a golden computed before the edit, in a
detached worktree at `c48dd677a640`.

**Nothing here is a win-rate measurement.** §6 is the pre-stated read for the
live screen that would be one, and §7 names the Wang difference this build
does *not* test, so a null here cannot be read as closing the budget axis.

---

## 1. The mechanism

Two structural differences sit inside Wang's **action selection** (deep-read
§2, thesis p.21–22). Neither is a bigger tree; both are ways of *not trusting
a noisy value estimate*.

**(i) The policy prior sits INSIDE the selection rule.** His tree policy is

> a_t = argmax_a ( Q[s_t, a] + α · U(s_t, a) ),  where
> U(s, a) = P[s, a]^β · √(M[s]) / (N[s, a] + 1)   — (p.21)

with `P[s,a] = π_θ(a | s)` and β ∈ [0,1] an exponent that "dictates … how much
to trust the neural network policy" (p.21). An action the policy dislikes must
*earn* its visits against `P[s,a]^β`.

**(ii) He decides by MAX VISIT COUNT, not max Q, and says why.**

> "a\* = max_{a∈A} N(s_0, a) … It is intuitive to choose the action with the
> largest Q value instead, but **less-visited actions may have higher variance
> in their Q estimates**." (p.22)

That is a *robust* selector: an action whose Q looks best on a handful of noisy
leaf evaluations cannot win unless the tree policy also chose to spend visits
on it.

**Ours has neither.** `rl/search/matrix.py` clause **D3** uses the policy prior
only as a tie-break — *after* the matrix score — and clause **D4** is a hard
argmax over `row_ev`. And `row_ev` is not a mean over ~1000 samples: dose M
spreads **277.4 leaves** over ≤9 rows × ≤6 opponent columns × 4
determinizations, i.e. single-digit leaves per cell. A hard argmax over
single-digit-sample means is the textbook maximization-bias / optimizer's-curse
regime.

**The smoking gun is in our own readout.** S3M **overrides the policy's own
argmax on 72.8% of decisions** (`search/flip_rate` 0.7277, 471,072 searched
decisions) and lands 6.8 points below the policy it overrode. Overriding a
0.789-strength policy three times in four, on a one-ply value estimate built
from single-digit-sample cells, is a mechanism for losing points that requires
no defect in the critic at all.

**What this build is.** The cheapest retraining-free analogue of Wang's
variance aversion: not his prior-in-the-tree-policy (we have no tree) and not
his visit counts (we have no visits), but the same *effect* — make the search
clear a confidence bar before it is allowed to override the policy.

---

## 2. The design

Let, at one decision:

- **`a_pi`** = the policy's own argmax over LEGAL actions — `argmax_{a legal}
  π_θ(a|s)` under the identical mask. This is exactly the action the greedy
  agent plays (`PPOAgent.act(deterministic=True)` argmaxes the same masked
  logits; softmax is monotone), and exactly what `matrix.py` already recorded
  as `search/policy_argmax` and what `agent.py`'s placeholder-skip path already
  returns.
- **`a_s`** = D4's argmax of `row_ev` (with D3's tie-breaks: score → prior →
  lowest index).

The rule, clause **D5**:

```
play a_s   iff   row_ev[a_s] - row_ev[a_pi] > delta
play a_pi  otherwise
```

Both sides of the comparison are on the same `row_ev` scale — expected outcome
in [−1, +1], the critic's own units — so `delta` is a value margin, not a
percentile.

**The endpoints are the two arms we have already measured.**

| `margin_delta` | selector | the arm it reproduces | measured on s112 |
| --- | --- | --- | ---: |
| absent (`None`) | D4 hard argmax, byte-identical | **S3M** | **0.74767** |
| `0.0` | D4 with exact ties conceded to the policy | S3M (see §3) | 0.74767 |
| `inf` | never overrides → the greedy policy | **A0** | **0.78233** |

So the live screen is not measuring two new endpoints: it is measuring whether
anything in between beats **both** of them.

**Semantic notes, each a place this could have gone wrong.**

- `None` is the *exact* no-op: nothing is computed and **no new stats key
  appears**, which is what makes the golden digest in §4 possible. A float
  delta is always the new rule, including `0.0`.
- The comparison is **strict `>`**. At `delta=0.0` an exact tie is therefore
  conceded to the policy — a real semantic difference from D4, which breaks
  ties by prior then index. §3 shows it is unreachable, and measures rather
  than assumes it.
- `delta=inf` with strict `>` can never fire, so it is *exactly* greedy. A test
  asserts this on 20 real harvested decisions across all four D26 lanes,
  against the independently computed `legal[argmax(prior[legal])]`.
- The gate can only ever move the search **back towards the policy**. It cannot
  invent an action D4 did not already pick, so the arms form a **nested
  family** — the overrides kept at a larger δ are a strict subset of those kept
  at a smaller one — and `override_rate(δ)` is therefore non-increasing in δ by
  construction (tested). The family interpolates the two arms' *behaviour*
  between S3M and A0. Whether it interpolates their *win rates* monotonically
  is the whole open question, and §6's cells are written on exactly that.
- Placeholder turns (locked: sleep/freeze/partial-trap/recharge) never reach
  the solver; they already return the policy argmax and are already excluded
  from the flip-rate denominator. The gate changes nothing there.

### Plumbing

Copied from how `leaf_encoding: det_blind` is threaded, site for site.

| site | change |
| --- | --- |
| `rl/search/matrix.py` | `solve_decision(..., margin_delta=None)`; D5 in the module docstring; `policy_argmax` hoisted (same value, same key); four `search/*` keys emitted **only** when the gate is on |
| `rl/search/agent.py` | `SearchAgent(..., margin_delta=None)`, validated (`None`, or a float ≥ 0.0, `inf` allowed, NaN rejected); `self.margin_delta`; `search/overrides` counter |
| `scripts/ch3_eval.py` | a `kind: search` arm may declare `margin_delta`; every chunk JSON and the merged final carry `search_margin_delta` (null when off), `search/overrides` and `search/override_rate` |
| `scripts/ch3_fp_h2h.py` | same for `kind: search_seat`; same three report fields |
| `scripts/search_margin_curve.py` | the offline curve (§5) |
| `tests/test_search_margin_selector.py` | 16 tests: the golden, the gate semantics over the delta grid, both endpoints, the plumbing |

**Per-decision stats, emitted only with the gate on:** `search/margin_delta`,
`search/search_argmax` (`a_s`), `search/margin` (`row_ev[a_s] −
row_ev[a_pi]`), `search/overrode` (bool). `search/chosen` is always the action
actually **played**.

**Why they are conditional.** The byte-identity contract is over
`solve_decision`'s *full* output, stats included; an unconditional key would
break it. Nothing is lost: with the gate off, both quantities are already
exactly derivable from `search/row_ev` and `search/policy_argmax`, which every
banked search arm recorded.

**`search/override_rate` is null when the gate is off**, not 0.0 — with no gate
there was never an override decision to take, and a 0.0 would read as "the
search never overrode the policy", which is the opposite of the truth (0.7277).
With the gate **on** it equals `search/flip_rate` by construction (both are
"played ≠ policy argmax"); the pair is kept separate so the two are
cross-checkable from disk and so a later selector cannot silently alias them.
`_merge` reads both new keys with `.get(default)`, so chunks written before
today — including every chunk the live S3 fleet is writing right now — merge
unchanged (tested).

---

## 3. Why `delta = 0.0` is not a third behaviour

D3 breaks a `row_ev` tie by **prior descending, then lowest index**. Suppose
`row_ev[a_s] == row_ev[a_pi]` with `a_s ≠ a_pi`. Then `prior[a_s] ≥
prior[a_pi]` (a_s won the tie-break) and `prior[a_pi] ≥ prior[a_s]` (a_pi is
the prior argmax), so the priors are equal too, and the index tie-break picks
the same lowest index in both rules — i.e. `a_s == a_pi`, contradiction. **The
conceded tie is unreachable**, so `delta=0.0` plays D4's action.

This is an argument, so it is also a test:
`test_delta_zero_reproduces_the_d4_argmax` runs 20 real harvested decisions
across all four lanes, asserts the actions agree, and separately counts
decisions where a conceded tie occurred. **0/20.** The distinction is kept in
the code anyway, because it is what makes `delta=inf` exactly greedy.

---

## 4. The byte-identity proof

Same instrument as DET_BLIND §3: a **golden sha256 over `solve_decision`'s full
output** — action plus every stat, `search/ev_matrix` included — under a fixed
cosine-projection critic, so a change to any leaf's encoding or to any EV
arithmetic moves the digest.

Computed **in a detached `git worktree` at `c48dd677a640`, i.e. before the
edit**, then reproduced by the post-edit working tree. Widened past DET_BLIND's
fixture to **all four D26 lanes × 10 strided non-aliased harvested decisions at
dose M**, plus the synthetic two-a-side fixture at dose S.

| fixture | leaves | digest | pre → post |
| --- | ---: | --- | :-: |
| synthetic, dose S | 99 | `892407da14fb…` | **identical** |
| s62 × 10, dose M | 3,707 | `f2b85990a1e0…` | **identical** |
| s63 × 10, dose M | 2,796 | `03249e4b0dc9…` | **identical** |
| s64 × 10, dose M | 3,540 | `b48c0b4189a5…` | **identical** |
| s65 × 10, dose M | 3,732 | `35b0af03081a…` | **identical** |
| **all 40 decisions** | **13,775** | `a3a847c7b782…` | **identical** |

The whole JSON — every digest, every action list, the leaf counts — diffs
empty between the pre-edit worktree run and the post-edit tree run.

*(`main` moved to `539b857` while this was being built — the parallel
engine-port session's A-1 readout. `git diff c48dd677a640..539b857 -- rl/
scripts/ tests/` is **empty**, so the golden's base commit is still exactly
"the search path before this edit".)*

**Two of these digests were already pinned in the repo before either edit.**
`tests/test_search_det_blind.py`'s `GOLDEN[("v2", True)]` is
`("892407da14fb…", "f2b85990a1e0…")`, computed at `899fdd9^{tree}` — before
*det_blind*. My pre-edit worktree run reproduces both exactly, at the same
3,707 leaves, so the golden is anchored to a pin that predates both changes
rather than to a number I minted this session. All 15 det_blind tests still
pass unchanged after the D5 edit.

---

## 5. The offline curve

`scripts/search_margin_curve.py`. Replays real harvested decisions through dose
M, records the two numbers the gate compares (`row_ev[a_s]`, `row_ev[a_pi]`),
and reports the **override rate** each delta would produce.

**Its only job is to choose which deltas a live screen should spend battles
on.** A delta whose override rate is ~0 cannot change anything — that arm *is*
the greedy policy. A delta whose override rate is ~0.73 is just today's search
— that arm *is* S3M. Only the strictly-between deltas are worth battles.

> **OVERRIDE RATE IS NOT WIN RATE.** R3 measured flip rate **rising** with
> evaluator noise while wins **fell** (0.732 → 0.480 as σ rose, flips 0.561 →
> 0.649). DET_BLIND §4 measured an 11.4% argmax footprint whose live delta then
> came back **−0.0088, NEG**. A footprint is a size, never a sign. Nothing in
> this section is evidence that any delta wins; only §6's screen can say that.

**Sample.** Deliberately the same one S1/S2 took: the four D26 12M lanes
(`results/ch3_r1/harvest_s6{2,3,4,5}.pkl`), 200 strided non-aliased decisions
per lane by `np.linspace`, public harvest only (never `harvest_priv_*` — FG-4).
Both leaf encodings run on every decision from the **same `decision_rng` key**,
so they draw the identical four determinizations and expand the identical
branches — verified live: `leaves_equal = true` on every decision.

**A plumbing check runs inside the job**: on the first 5 decisions of every
checkpoint lane the real `SearchAgent(margin_delta=d)` path is run at δ ∈
{0.02, 0.1} and its action must equal the post-hoc prediction from the recorded
margin. The curve and the flag are then the same object.

### 5a. There is no 100M harvest, and building one is NOT POSSIBLE OFFLINE

`rl/search/harvest.py` freezes `battle1` off a **live** battle:
`scripts/ch3_harvest.py` plays real games against `SimpleHeuristicsPlayer`
through the Showdown server. A harvest of the 100M finals needs a server and
real battles. It is not available offline and was not invented.

What *is* cheap and honest is a **cross-object replay**: the three 100M finals'
policy+critic+oppact heads run over the *same 12M-lane harvested states*. The
observation encoding is checkpoint-independent (828-d, encoder v2+ids), so this
is a legitimate measurement of **the 100M evaluator's margin distribution** —
on states a 12M policy generated while playing SH, not states the 100M policy
would generate. **That is a declared distribution shift**, it is stamped into
the JSON's provenance, and the object is read as a SHAPE, never as a number.
It is reported because the live screen runs on s112@100M and the 12M object's
margin scale need not transfer.

### 5b. THE CURVE — the four D26 12M lanes, own checkpoint on own states

Run 2026-09-10 17:06–17:18 EDT, one process, `taskpolicy -b`, torch threads 2,
**800 decisions** (200/lane over s62–s65, the same `np.linspace` stride over
the same public harvest S1/S2 took), `results/search_margin/margin_curve_d26_12m.json`.
Wall 11.7 min. Zero watchdog trips, zero placeholder skips. **Plumbing check:
PASS, 40/40 probes** at δ ∈ {0.02, 0.1}.

| delta | override rate, as-is | override rate, det_blind |
| ---: | ---: | ---: |
| **0** *(= D4, today's search)* | 0.4888 (391) | 0.4975 (398) |
| **0.005** | 0.4412 (353) | 0.4500 (360) |
| **0.01** | 0.4025 (322) | 0.4163 (333) |
| **0.02** | 0.3475 (278) | 0.3513 (281) |
| **0.03** | 0.2900 (232) | 0.2825 (226) |
| **0.05** | 0.2000 (160) | 0.1988 (159) |
| **0.075** | 0.1375 (110) | 0.1475 (118) |
| **0.1** | 0.0963 (77) | 0.1037 (83) |
| **0.15** | 0.0525 (42) | 0.0512 (41) |
| **0.2** | 0.0338 (27) | 0.0338 (27) |
| **inf** *(= the greedy policy)* | 0.0000 (0) | 0.0000 (0) |

| quantity | as-is | det_blind |
| --- | ---: | ---: |
| flip rate at δ=0 (`a_s ≠ a_pi`) | 0.4888 | 0.4975 |
| mean margin where `a_s ≠ a_pi` | 0.0657 | 0.0651 |
| median margin where `a_s ≠ a_pi` | 0.0379 | 0.0353 |
| mean `row_ev[a_s]` | 0.3373 | 0.2920 |
| mean `row_ev[a_pi]` | 0.3052 | 0.2596 |
| mean sd(row_ev) across legal rows | 0.0867 | 0.0833 |
| leaves/decision | **350.77** | **350.77** |
| ms/decision (CONTENDED, descriptive) | 443.1 | 402.7 |
| `a_pi` == recorded greedy action | **1.0000** | **1.0000** |
| decisions with 1 legal action | 19 | 19 |
| watchdog trips / placeholder skips | 0 / 0 | 0 / 0 |

Margin percentiles **conditional on the search and the policy disagreeing** —
this is the distribution the delta grid slices:

| pct | 1 | 5 | 10 | 25 | 50 | 75 | 90 | 95 | 99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| as-is | 0.0001 | 0.0018 | 0.0054 | 0.0157 | **0.0379** | 0.0848 | 0.1674 | 0.2234 | 0.4124 |
| det_blind | 0.0001 | 0.0021 | 0.0052 | 0.0159 | **0.0353** | 0.0864 | 0.1561 | 0.2201 | 0.3993 |

Per lane, override rate (as-is / det_blind):

| delta | s62 | s63 | s64 | s65 |
| ---: | ---: | ---: | ---: | ---: |
| **0** | 0.475 / 0.465 | 0.480 / 0.495 | 0.495 / 0.520 | 0.505 / 0.510 |
| **0.02** | 0.285 / 0.320 | 0.340 / 0.335 | 0.370 / 0.400 | 0.395 / 0.350 |
| **0.05** | 0.165 / 0.175 | 0.185 / 0.185 | 0.245 / 0.240 | 0.205 / 0.195 |
| **0.1** | 0.090 / 0.110 | 0.120 / 0.100 | 0.085 / 0.105 | 0.090 / 0.100 |
| **0.2** | 0.035 / 0.040 | 0.050 / 0.045 | 0.025 / 0.030 | 0.025 / 0.020 |

**Four independent cross-checks that this harness is measuring what it says.**
`a_pi` equals the harvest's recorded greedy action on **800/800** decisions —
`a_pi` really is the checkpoint's own argmax. Leaves/decision is **350.7725 on
both encoders**, reproducing DET_BLIND §4's figure to four decimals. Cross-
encoder `a_s` agreement is **0.8862**, i.e. an 11.38% disagreement, reproducing
DET_BLIND §4's **0.11375** argmax-flip rate. And the 19 dropped one-legal-action
decisions are the same 19 S1 dropped.

### 5c. THE CURVE — the three 100M finals on 12M-lane states (declared shift)

Run 2026-09-10 17:18–17:27 EDT, same conditions, **600 decisions** (200 per
100M lane, split 50 per state lane over s62–s65),
`results/search_margin/margin_curve_finals_100m.json`. Wall 9.0 min. Zero
watchdog trips, zero placeholder skips. **Plumbing check: PASS, 30/30 probes.**

| delta | override rate, as-is | override rate, det_blind |
| ---: | ---: | ---: |
| **0** *(= D4, today's search)* | 0.4617 (277) | 0.4433 (266) |
| **0.005** | 0.4033 (242) | 0.3833 (230) |
| **0.01** | 0.3733 (224) | 0.3567 (214) |
| **0.02** | 0.3200 (192) | 0.3033 (182) |
| **0.03** | 0.2700 (162) | 0.2583 (155) |
| **0.05** | 0.1833 (110) | 0.1983 (119) |
| **0.075** | 0.1333 (80) | 0.1350 (81) |
| **0.1** | 0.0850 (51) | 0.1000 (60) |
| **0.15** | 0.0483 (29) | 0.0417 (25) |
| **0.2** | 0.0250 (15) | 0.0250 (15) |
| **inf** *(= the greedy policy)* | 0.0000 (0) | 0.0000 (0) |

| quantity | as-is | det_blind |
| --- | ---: | ---: |
| flip rate at δ=0 | 0.4617 | 0.4433 |
| mean / median margin where `a_s ≠ a_pi` | 0.0619 / 0.0357 | 0.0637 / 0.0416 |
| mean `row_ev[a_s]` / `row_ev[a_pi]` | 0.3090 / 0.2804 | 0.2918 / 0.2636 |
| mean sd(row_ev) across legal rows | 0.0762 | 0.0778 |
| leaves/decision | **353.21** | **353.21** |
| `a_pi` == recorded greedy action | **0.6000** | **0.6000** |
| cross-encoder `a_s` agreement | **0.8967** | — |

**Per lane** (as-is / det_blind), s112 being the lane the screen will run on:

| delta | s104 | **s112** | s120 |
| ---: | ---: | ---: | ---: |
| **0** | 0.445 / 0.415 | **0.450** / 0.455 | 0.490 / 0.460 |
| **0.005** | 0.380 / 0.355 | **0.375** / 0.370 | 0.455 / 0.425 |
| **0.01** | 0.350 / 0.330 | **0.325** / 0.345 | 0.445 / 0.395 |
| **0.02** | 0.295 / 0.270 | **0.285** / 0.305 | 0.380 / 0.335 |
| **0.03** | 0.230 / 0.240 | **0.255** / 0.250 | 0.325 / 0.285 |
| **0.05** | 0.135 / 0.175 | **0.200** / 0.200 | 0.215 / 0.220 |
| **0.075** | 0.100 / 0.120 | **0.125** / 0.115 | 0.175 / 0.170 |
| **0.1** | 0.070 / 0.095 | **0.070** / 0.085 | 0.115 / 0.120 |
| **0.15** | 0.045 / 0.035 | **0.045** / 0.040 | 0.055 / 0.050 |
| **0.2** | 0.025 / 0.025 | **0.015** / 0.020 | 0.035 / 0.030 |

`a_pi` == the recorded greedy action on only **60%** of decisions here, which
is the shift made visible: the 100M policy disagrees with the 12M policy that
generated these states on 40% of them. That is the number to hold in mind when
reading the next section — this object's *level* is not transferable.

### 5d. Reading it, and the deltas the live screen should buy

**There is a usable middle.** The margin distribution conditional on
disagreement is heavy-tailed and decays slowly: median 0.036–0.038, p75 ≈
0.085, p90 ≈ 0.15–0.17. So the delta grid genuinely partitions the
disagreements — δ=0.02 keeps ~63% of them, δ=0.05 ~44%, δ=0.1 ~16%, δ=0.2
~3%. A margin gate is not a knob that snaps from "all" to "none"; the whole
range is reachable.

**Both encoders give the same curve.** as-is and det_blind agree to within
~0.02 in override rate at every delta on both objects, at identical leaf
counts. **det_blind is therefore not a reason to choose different deltas.**
The screen should run the **as-is** encoding, because that is what keeps the
δ=0 endpoint paired with a *measured* number (S3M s112 = 0.74767); a det_blind
screen would need its own δ=0 endpoint, and P-B already read **NEG (−0.0088)**.

**LEVEL DISCLOSURE — the offline override rate does not reproduce the live
one.** At δ=0 this replay reads **0.4617** on the 100M finals, while the live
S3M arm measured **`search/flip_rate` 0.7277** over 471,072 decisions. Same
selector, same dose, same checkpoints — different STATES (12M-policy-vs-SH
here, 100M-policy-vs-SH live) and a strided 600-decision sample against half a
million. **So the offline column is not a prediction of the live override
rate.** What is more likely to transfer is the *conditional* decay
`P(margin > δ | a_s ≠ a_pi)`, since that is a property of the margin
distribution rather than of how often the two policies disagree.

**PROJECTION — labelled as such, not a measurement.** Rescaling s112's
conditional decay by the live δ=0 anchor of 0.7277, i.e. **assuming only the
disagreement rate shifts and the shape of the margin distribution does not**:

| δ | offline s112 | `P(m>δ \| dis)` | **projected live override rate** | overrides/battle¹ |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 0.4500 | 1.000 | **0.7277** *(measured)* | 19.5 |
| 0.005 | 0.3750 | 0.833 | 0.606 | 16.2 |
| 0.01 | 0.3250 | 0.722 | 0.526 | 14.1 |
| **0.02** | 0.2850 | 0.633 | **0.461** | 12.3 |
| 0.03 | 0.2550 | 0.567 | 0.412 | 11.0 |
| **0.05** | 0.2000 | 0.444 | **0.323** | 8.7 |
| 0.075 | 0.1250 | 0.278 | 0.202 | 5.4 |
| **0.1** | 0.0700 | 0.156 | **0.113** | 3.0 |
| 0.15 | 0.0450 | 0.100 | 0.073 | 2.0 |
| 0.2 | 0.0150 | 0.033 | 0.024 | 0.7 |

¹ at the harvest-measured **26.79 searchable decisions/battle** (not S1/S2's
pre-stated 38, which was deliberately conservative for a different bound).

**WHICH DELTAS HAVE POWER — the argument that picks them.** Every gated arm
plays `a_pi` except on the kept overrides, so write its win rate as
`A0 + r(δ)·v̄(δ)`, where `r` is the override rate and `v̄` the mean win-rate
value of a kept override. The δ=0 endpoints pin `v̄(0)`: `0.74767 = 0.78233 +
0.7277·v̄(0)` ⟹ **`v̄(0) = −0.0477`**. For an arm to clear the routing bar of
+0.025 above A0 it needs `r(δ)·v̄(δ) ≥ 0.025`:

| δ | projected r | **`v̄` required for a +0.025 hump** | linear-null win rate² |
| ---: | ---: | ---: | ---: |
| **0.02** | 0.461 | **+0.054** | 0.760 |
| 0.03 | 0.412 | +0.061 | 0.763 |
| **0.05** | 0.323 | **+0.077** | 0.767 |
| 0.075 | 0.202 | +0.124 | 0.773 |
| **0.1** | 0.113 | **+0.221** | 0.777 |
| 0.15 | 0.073 | +0.343 | 0.779 |
| 0.2 | 0.024 | **+1.03** *(impossible)* | 0.781 |

² what the arm reads if `v̄(δ) = v̄(0)`, i.e. if the gate filters nothing but
volume. Note that from δ=0.1 upward the linear null already sits within one
redraw spread (±0.02) of A0: **those arms cannot distinguish themselves from
greedy in either direction, so they carry almost no information about a hump.**

**RECOMMENDED: δ ∈ {0.02, 0.05, 0.10}, one lane (s112), 3000 battles each,
as-is encoding.** Rationale, in one line each:

- **0.02** — keeps ~63% of the disagreements; the *most powerful* arm, because
  it has the largest `r` and therefore the lowest `v̄` bar (+0.054). If any
  confidence threshold helps at all, this arm should already sit clearly above
  S3M's 0.74767.
- **0.05** — the mid point, ~44% of disagreements kept, `v̄` bar +0.077. This
  is where the shape between the two endpoints becomes readable rather than a
  two-point line.
- **0.10** — the **Wang-shaped** arm: the policy plays unless the search is
  loudly confident (~3 overrides per battle). Its linear null is 0.777, so a
  reading materially above A0 *here* would be a strong hump signal precisely
  because the arm has so little room to move. It also pins the right-hand
  approach to A0, which the MONOTONE cell needs.

Three arms is the minimum that makes a SHAPE readable at ±0.02 per rung; a
fourth at **δ=0.03** is the cheapest densification if the maintainer wants it.
**Advise against δ ≥ 0.15** (projected `r` ≤ 0.073 — indistinguishable from A0)
and **against δ ≤ 0.01** (projected `r` ≥ 0.53, linear null 0.757 —
indistinguishable from S3M). Both ends buy a battle budget to re-measure
something already measured.

### 5e. What made me doubt the mechanism

**The margin is not zero-mean noise. It carries a one-sided, margin-GROWING
shift toward switching out.** A margin gate is the textbook fix for
maximization bias when the estimator's error is symmetric noise; it is *not* a
fix when the error is a systematic bias, because filtering on |margin| keeps
exactly the decisions where a one-sided bias is largest.

Computed post-hoc from the same JSONs (poke-env's mapping: index 0–5 = switch,
6–9 = the active's move slot). Among decisions where the search disagrees with
the policy, on the **100M finals**, as-is:

| margin band | n | policy switches → search attacks | policy attacks → **search switches** |
| --- | ---: | ---: | ---: |
| (0, 0.01] | 53 | 0.000 | 0.264 |
| (0.01, 0.02] | 32 | 0.000 | 0.281 |
| (0.02, 0.05] | 82 | 0.049 | 0.146 |
| (0.05, 0.1] | 59 | 0.186 | 0.220 |
| (0.1, 0.2] | 36 | 0.111 | **0.389** |
| **(0.2, ∞)** | 15 | 0.067 | **0.600** |
| all | 277 | 0.072 | 0.256 |

Base rates: `a_pi` is an attack on **79.5%** of these decisions, `a_s` on
**71.0%** — the search moves ~8.5 points of mass from attacking to switching,
and **the skew is strongest exactly in the high-margin tail the gate keeps**
(0.600 at margin > 0.2; det_blind reads 0.733 in the same band). The 12M object
shows the same one-sided pattern (0.238 overall, 0.370 in the top band, against
0.033 the other way).

Why that is a specific worry and not a generic one: the search's opponent model
drops `OTHER_MOVE` and renormalizes over the determinized active's four move
slots plus a **uniform** bench draw, and `rl/search/matrix.py`'s own docstring
names the consequence. At depth 1 a switch is valued **one turn after it
happens**, before any punishment lands. Wang's single documented search failure
is exactly this shape: with Kecleon against Rampardos his search switched into
an instant KO because its opponent model "was not aware of the potential for
the switched-in Venomoth to get instantly knocked out" (p.33–34). If our
high-margin overrides are disproportionately switches into an under-modelled
reply, then the confident subset is the *contaminated* subset and the hump does
not exist — the curve would be monotone for a reason that has nothing to do
with the selector.

This is descriptive and it is not a verdict: it does not show switching is
wrong, only that the override is one-sided and that the one-sidedness grows
with the very quantity the gate filters on. It is the single strongest reason
to expect MONOTONE, and it is worth naming *before* the screen so a monotone
result is not read as a surprise. It also names the follow-up if MONOTONE
lands: the opponent model / switch-target law (deep-read **H3**), not the
selector.

---

## 6. Pre-stated read for the LIVE screen

Written before the screen runs. **This is the read, not the pre-reg**: the arm
needs its own config header naming its `journey_step` and restating that step's
exit condition verbatim, per CLAUDE.md, before it launches.

**Object.** `s112` @ 100M, sha256-pinned in `configs/eval/search_s3_100m.yaml`
(`runs/showdown_sp_100m_s112/ckpt_100000008.pt`, sha `2ec16fbf85a9…`).
**ONE LANE FIRST.**

**Arms.** `S3G<delta>` = S3M with `margin_delta: <delta>`, at the three deltas
§5d selects. Everything else identical to S3M: dose M (n_det 4, top_branches 6,
leaf_cap 1296), **as-is** leaf encoding (§5d: both encoders give the same
curve, and as-is is what keeps the δ=0 endpoint paired with a measured number),
same driver, same chunking, same battle2 sentinel on chunk 0.

```yaml
S3G002: {kind: search, lanes: [s112], dose: M, battles: 3000, chunks: 10, margin_delta: 0.02}
S3G005: {kind: search, lanes: [s112], dose: M, battles: 3000, chunks: 10, margin_delta: 0.05}
S3G010: {kind: search, lanes: [s112], dose: M, battles: 3000, chunks: 10, margin_delta: 0.10}
```

**Protocol.** vs `SimpleHeuristicsPlayer`, locked protocol, deterministic seat,
ties as non-wins, **3000 battles**, 10 chunks, `ch3_eval.py`.

**Comparators — both already MEASURED on this exact lane, this session, at this
exact protocol.** No new endpoint arms are needed and none should be run:

| endpoint | arm | `margin_delta` | measured |
| --- | --- | --- | ---: |
| the search | **S3M s112** | `0.0` (≡ absent) | **0.74767** (10/10 chunks, n=3000) |
| the policy | **A0 s112** | `inf` | **0.78233** (10/10 chunks, n=3000) |

**THE INTERESTING OUTCOME IS A HUMP.** Some intermediate delta beating
**0.78233**. That would say the value signal is real but only above a
confidence threshold, and that our loss was a *selector* defect — H2 — fixable
with no retraining and no extra compute. (Beating 0.78233 *at all* is the
HINT cell below; beating it by the credit line's floor is HUMP. The split
exists because one rung is worth ±0.02 and a one-lane arm cannot credit.)

**A MONOTONE CURVE from 0.748 to 0.782 means the value signal adds nothing at
any confidence threshold, and search over this critic is dead regardless of the
selector.** Every intermediate delta is a mixture of the same two policies; if
the mixture is monotone in the mixing weight, the search half contributes
nothing but loss, at every level of confidence we can ask it for. That is a
much stronger statement than "search@M loses": it closes the *selector* axis
for this evaluator.

**The statistic.** `delta_G(δ) = p(S3G δ, s112) − p(A0, s112) = p(S3G δ) −
0.78233`, and the reported summary is `best_delta_G = max over the SCREENED
deltas of delta_G(δ)`. Named before the run because it is a **maximum over k
arms and is therefore upward-biased** — which is exactly why the routing bar
below is the credit line's own floor rather than "beats A0", and why a HUMP
promotes to a re-read out of sample rather than to a claim. **The band is on
`delta_G`, and HUMP needs its LOWER edge above the line.**

**Cells — a complete partition on (`best_delta_G`, monotonicity in δ). No cell
is unnamed and none of them credits anything.**

- **HUMP** iff `best_delta_G ≥ +0.025` → the selector is the defect. Promote
  that δ to all three lanes (s104/s112/s120, 3×3000) under its own pre-reg,
  with the δ **declared as a selection made on s112 and re-read out of
  sample**. Only that three-lane arm can meet the credit line.
- **HINT** iff `0 < best_delta_G < +0.025` → it beats A0 but by less than one
  redraw of the same checkpoint (±0.02). Route: run the SAME δ on s104 and
  s120 (3×3000) before any claim, statement, or further delta search. Nothing
  else changes and no sentence is licensed from the hint alone.
- **MONOTONE** iff `best_delta_G ≤ 0` **and** `delta_G(δ)` is non-decreasing
  across the screened deltas → the value signal adds nothing at any confidence
  threshold: the **selector axis is closed for this evaluator at this budget**.
  The relook's remaining burden is the **evaluator** (A1E / IDEAS 8.2) and
  **depth** (`ENGINE_SEARCH_DESIGN.md`); §7's budget axis is untouched.
- **NON-MONOTONE NULL** iff `best_delta_G ≤ 0` and the sequence is not
  non-decreasing → no route. Report the shape and stop; do not add lanes or
  deltas to chase a sub-zero wiggle at ±0.02 per rung.

**This is a SCREEN. It CREDITS NOTHING.** Credit line, restated **verbatim**
from CLAUDE.md: *"a lever is credited iff pooled delta ≥ +0.025 **and** ≥
2·se_diff"*, with the **larger-of** clause — se_diff is the LARGER of the
pooled-binomial se_diff and the seed-clustered se_diff, the latter computed
from the per-seed finals at read time. One lane cannot produce a seed-clustered
se_diff, so a one-lane screen is **structurally incapable of crediting
anything**; it selects a delta for a three-lane arm that could.

**ONE RUNG IS WORTH ±0.02**, not the binomial ±0.008 — three n=3000 redraws of
ONE checkpoint spread 0.0200 (2026-08-31). The gap being probed, A0 − S3M on
s112, is **0.0347**: less than two redraw spreads. Read the SHAPE across the
screened deltas; never one cell against its neighbour. Screening ≥3 deltas is
what makes a shape readable at all, and it is why the recommendation in §5d
names more than one.

**Secondary reads, declared in advance, none of them a firing condition:**

- `search/override_rate` per arm, against §5d's **projected** live rates
  (0.461 / 0.323 / 0.113 at δ = 0.02 / 0.05 / 0.10). The live realized rate on
  100M-policy states versus the offline rate on 12M-policy states is the direct
  test of §5c's declared distribution shift, and the first arm to report will
  re-calibrate the projection for the rest;
- `search/flip_rate` per arm (must equal `override_rate` exactly with the gate
  on — a mismatch is a defect, not a finding);
- `search/ms_mean`, `leaves_mean` — the gate is predicted **cost-neutral**
  (identical determinizations, identical branches, identical leaves; only the
  final comparison differs). A leaves delta would mean the option changed the
  search tree, which it must not;
- `search/placeholder_skip_rate`, `mask_desyncs == 0` as usual.

**Dose is NOT matched** between A0 and any gated arm — the generic-compute
confound survives exactly as in R2/S3, and is disclosed rather than controlled.
It IS matched among all the gated arms and S3M, which is what makes the shape
across deltas readable.

---

## 7. What this build does NOT test — the budget axis

**A null here does not close the budget axis.** The selector is one of the two
structural differences in the deep-read; the other is untouched by this build
and is much larger (§4 of the deep-read, and H1, which the deep-read ranks
**above** H2):

| quantity | Wang | ours (dose M) | ratio |
| --- | ---: | ---: | ---: |
| wall clock per decision | 10 s | 62.3 ms | **~160×** |
| CPU-seconds per decision | ~200 worker-s (20 workers) | ~0.062 s | **~3,200×** |
| determinizations per decision | 1,000–2,000 | 4 | **250–500×** |
| rollouts / leaves per decision | 1,000–2,000 rollouts | 277.4 leaves | ~4–7× |
| depth | multi-ply, unstated | **1** | — |
| tree persistence | **statistics accumulate across the ~25 decisions of a game**, pruned only by fainted count (p.28) | none — every decision starts empty | — |

**We have never run search at a budget within two orders of magnitude of his.**
Dose L (n_det 16, leaf_cap 5184) is 244.6 ms / 1,083 leaves — still ~40× short
in wall clock and ~60× short in determinizations.

Three further Wang differences this build also does not touch, listed so no
one reads them into the result: his opponent model is the *same network's*
policy (ours is a 6-class oppact head with `SWITCH` collapsed to a uniform
bench draw, a **named directional bias** — H3); his critic is queried on
exactly the π_θ-vs-π_θ distribution it was trained on (H5); and his generation
is gen 4, a stalling metagame where a multi-turn tree has more to find than one
ply does in gen 1 (H4).

**What a MONOTONE result would license, precisely:** *the selector axis is
closed for this evaluator at this budget* — no confidence threshold rescues a
depth-1, 4-determinization search over this critic. It would license nothing
about depth ≥ 2 (which does not exist in `rl/search/`), nothing about
n_det ≥ 1000, and nothing about a persistent tree.

---

## 8. Files

| file | what |
| --- | --- |
| `rl/search/matrix.py` | D5, the gate |
| `rl/search/agent.py` | the `margin_delta` dial + `search/overrides` |
| `scripts/ch3_eval.py` | pre-reg key, chunk/final provenance, `override_rate` |
| `scripts/ch3_fp_h2h.py` | same for the Foul-Play seat |
| `scripts/search_margin_curve.py` | the offline curve |
| `tests/test_search_margin_selector.py` | the golden + the semantics + the plumbing |
| `results/search_margin/margin_curve_d26_12m.json` | §5b (gitignored) |
| `results/search_margin/margin_curve_finals_100m.json` | §5c (gitignored) |

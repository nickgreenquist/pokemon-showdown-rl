# DESIGN2 — Chapter 2 proposal: seal D25, then extend it

**STATUS: DRAFT r1, PROPOSED 2026-08-16 (night). NOT RATIFIED. Nothing launched; no
tranche authorised.** Ratification and the budget are the maintainer's. This file is the
decision document; full designs and reviews live in `results/design_ch2/` —
`ch2_design_A.md` (information-and-verdict lens), `ch2_design_B.md` (build-and-cost
lens), `ch2_review_1.md` (evidential validity), `ch2_review_2.md` (buildability) — two
independent Opus designers plus two independent Opus reviewers per the standing process
(maintainer 2026-08-12). `results/` is gitignored: those files are the only copies.
**r1 incorporates all 26 review MUST-FIXes; r0's versions of the affected claims are
superseded.** Review 1 verified every bar-arithmetic spot-check to <0.001.

**Process disclosures.** (1) The designers' brief misdescribed D25's cadence (that was
D18's); Designer B caught it; Designer A was not contaminated. (2) The memos conflicted
on the D28 task and on sequencing; resolved below with reasons. (3) The trunk-fraction
"discrepancy" (RESULTS §5's 0.51–0.62 vs recomputed 0.619–0.676) is per Review 2 a
window difference — late-window (bin 11) vs full-run mean — to be confirmed per-lane
and stated with its convention in any header. (4) Designer A independently re-derived a
finding already banked on 2026-08-13 (`SESSION_LOGS.md:2916-2940`, the rejected 50M
carry): **the 50M win-rate channel is arithmetically un-creditable** — STATUS's "50M
CLOSED". D29 below therefore asks to RE-OPEN a closed line, not to act on a new finding.

**The credit line, verbatim, restated in every arm's header exactly as follows: a lever
is credited iff pooled delta ≥ +0.025 AND ≥ 2·se_diff, where se_diff is the LARGER of
the pooled-binomial se_diff and the seed-clustered se_diff (computed from the per-seed
finals at read time).** Across-lane aggregator, per arm: D28, D29, D30 win-rate reads
all use the EQUAL-WEIGHT MEAN of per-seed finals; mechanism reads (g, ctx atoms) use
the MEDIAN across lanes, as D25 did. Both named here so no read invents its own.

## 0. What this chapter is, and what it costs

Chapter 1 ends at ~19.7/20 lane-days when D26 reads out. **The full chapter-2 tranche
(≈8.9–9.0 ld at realised pricing) takes the ledger to ≈28.6 against the standing 20
lane-day cap — this chapter cannot run inside the existing authorisation; the ask is a
new tranche.** (Ledger denomination — realised wall-clock 0.432 ld per 12M lane vs the
budgeted 0.470 — is OWED a ruling; both totals quoted where they differ.)

| arm | what it buys | lanes | lane-days (realised pricing) |
|---|---|---|---|
| **D28** — zero-information structured aux control, 12M | closes D25's dose caveat (STATUS: "untested, AND this control cannot test it") | 5 (4 acceptable, but the frozen power table only transfers at 5v5) | **2.16** (1.78) |
| **D29** — D25 recipe at 50M, anneal-off | the scale question; requires re-opening the closed 50M line and a §13 ruling | 3 | **4.45–4.57** |
| **D30** — soft-label aux, 12M | the direct extension of the credited lever | 5 (3-lane mechanism-only variant ≈ 1.30) | **2.16** |
| zero-lane gates, calibrations, finals | — | — | ~0.10 |

## 1. D28 — the zero-information control (the chapter's core purchase)

**Purpose.** D25's credit carries one open caveat: "a generic auxiliary gradient of
matched size would have helped too" — untested, because a shuffled-label head cannot be
dosed (D25-P measured the trunk-fraction collapse 0.44–0.54 → 0.05–0.09; that
measurement is what killed D27 at zero lanes). D28 is the dosable version.

**Task (r1, corrected per both reviews).** A temperature-sampled draw from a fixed
random linear readout of the raw obs blocks the head's entities are built from, with
**one shared readout vector across the four opponent-move slots** (`s_j = ⟨w_move,
block_j⟩`, j=0..3) — the head's scorer is shared across classes with only a scalar
`slot_bias` per slot, so independent per-slot vectors would be ~75% unrepresentable and
collapse into the bias (Review 2 MF-1). Separate `w_global` (OTHER_MOVE's stand-in) and
`w_bench` (SWITCH's). Disclosed: classes 0–3/5 are trunk-connected through the entity
path; class 4 only through ctx (its entity is the constant null token). **Free numbers:
τ AND the per-class score standardisation** (raw block scales differ 46/6/34-dim), both
frozen offline by Z1-2 targeting D25's measured label marginal and oracle entropy
(0.250 nats), with a stated primary criterion and tie-break. Two dedicated RNGs, both
named in the header: W from a module-constant seed (identical task across lanes, never
serialised — the θ₀ precedent), the label draw from a per-lane generator (the
`_shuffle_gen` precedent; the default stream carries poke-env usernames). Rows: D25's
`valid` filter reused, so trained rows match (~0.80–0.82 labelled_frac). Honest scope
(Review 2): the label reads *opponent move/mon blocks*, so this is zero
opponent-**action** information — the trunk is still pushed to encode opponent
*features* — and every licensed sentence says so.

**What a null closes, stated now (Review 1's sentence, adopted verbatim):** a null
licenses *"an auxiliary gradient of D25's delivered size, through D25's head and entity
path, on a task with zero opponent-action information and no decision-relevant
structure, does not reproduce D25's gain."* It does NOT license "no generic auxiliary
gradient of matched size would have helped" — the strongest task-relevant generic
candidate (own-action) is architecturally unfittable by this head (D25's B6 probe
corroborates: linear/frozen/greedy, gain −0.061 — corroboration, not proof) and is not
run. This is the header's single most important sentence.

**Dose gates (r1, unified — one scalar, one band system).** The single dose scalar is
the **delivered ratio** `aux/trunk_norm_delivered ÷ aux/policy_trunk_norm` (the
caveat's actual quantity; D25 measured 0.094–0.108 as run means). A's
INSUFFICIENT/SHORT/MATCHED/OVER partition is defined ON this scalar (bands re-derived
from D25's per-bin `dose_bins.json` values at header time, convention stated on the
same line — Review 2 showed r0's flat [0.50, 0.75] per-bin band fails D25 itself).
Trunk-fraction is a separate LATE-WINDOW gate on A's [0.45, 0.70] (bracketing the
recorded bin-11 0.51–0.62), plus clip-neutrality ≤ 0.01. Precedence: the delivered
ratio decides the dose cell; trunk-fraction and clip gates decide VOID. The
INSUFFICIENT-cell rule (A's table governs): a NULL licenses nothing; a POSITIVE is
a-fortiori informative. Requires the 6-line delivered-dose instrumentation patch
(verified correct against `_aux_gradient` by Review 2; lands with its test-arity fix,
AFTER the D26 fleet finishes).

**Verdict machinery (A §1.3–1.7 as amended by Review 1).** Dual comparator: R-1
PRIMARY = frozen D25 (0.618467, sd 0.023575, n=5) minus control, one-sided upper; R-2
letter-bearing secondary = control minus frozen Rung-2 comparator (0.54452, sd 0.03558,
n=5), one-sided upper. **Sealing = R-1 fires AND the R-2 point estimate ≥ 0** (the
operationalised form; r0's "not S-c" cell form would have sealed under a control that
hurt by 0.030). Three pre-written A1 sentences keyed to (dose cell × S-a/S-b): MATCHED
+ S-b → "refuted"; SHORT + any → the shortfall caveat attached to every use; any + S-a
→ "both contribute", never "refuted". Branch table A1–A5 + S-a/b/c + three VOIDs,
partition-complete (verified), retraction obligations enumerated, D30 cancelled on
retraction. Power quoted WITH the P(band) columns from the frozen table (the modal
non-null outcome at wide spread is the A2 recording band, 0.28–0.35).

**Manipulation check (r1, restated for the adopted task):** g = (A1 − NLL_head)/(A1 −
A3) where A3 is the τ-set synthetic sampler's own entropy — *exactly computable*, not
estimated. The LEARNED bar via the 0.80× construction on the synthetic probe, derived
at zero lanes. (A's own-action A3 = H(π) and its self-distillation confound C-A2 are
struck with the task they described.)

**Zero-lane gates before ratification:** Z1-1 is a **screen, not a kill gate**, until
calibrated — the repo already measured offline fitted-head ratios to be dominated by
head weight scale (13.6× spread; `ppo.py:554-561`) — so Z1-1 runs the identical offline
procedure on D25's real task and D25-P's shuffled task first, maps proxy→live against
their banked live answers, and only then reads the synthetic task (on BOTH r0
candidates too, one extra fit, converting the designer conflict into a measurement).
Z1-2 (τ + standardisation), Z1-3 (target invariant under `opp_choice` permutation;
`valid`'s dependence on the opponent's presence stated separately), Z1-4 (bit-identity
of actor/critic state_dicts at fixed seed), the D25-P per-bin trajectory recompute
(calibrates the 6M abort), Z1-5 smoke (server, post-D26).

## 2. D29 — D25 at 50M (re-opening a closed line; needs the §13 ruling first)

**Standing (r1).** The 2026-08-13 carry cycle already established, to the digit, that
the 50M win-rate channel cannot credit: floor bar 0.66754 at zero treatment spread —
above the best single lane ever measured (s35's 0.65933) and above D25's entire 12M
effect reproduced perfectly — because the banked comparator (0.580222, sd 0.075617,
n=3) contributes 2·sd/√3 = 0.0873 alone. That cycle also already escalated the §13
question. Designer A re-derived all of it independently (Review 1 verified both). The
s37 outlier has a **recorded diagnosis** and it makes the spread MORE real, not less:
a sustained actor-side gradient pathology from ~20M (pre-clip median 1088, clip pinned
1.0 from ~25M, eval 0.616→0.490), reproduced in D18's s41 — a recurring regime
property, not a recoverable artefact (r0's "open zero-lane item" is withdrawn).

**What D29 differs in from the rejected carry:** the treatment is the credited D25
recipe (not bare struct), the PRIMARY is distribution-free, and the mechanism
secondaries are the purchase. PRIMARY: exact 3v3 permutation on per-seed finals —
fires iff min(treatment) > 0.65933 (complete separation), p = 1/20; **ties at the
boundary read as non-separation, pre-stated.** The credit line runs as a letter-bearing
secondary with the bar table printed and the expected miss pre-narrated; **the cell
"credit line fires, permutation does not" is named** (possible at low treatment spread,
e.g. 0.68/0.68/0.65) and reads: seed-fragile-favourable, no separation claim, licensed
sentence pre-written (Review 1 MF-9). Scale secondary: D25@50M vs D25@12M (bar 0.643 at
floor) — answers "does 4.17× compute add on top of the credited recipe", explicitly
cannot discharge §13. Mechanism secondaries: §6 g and §5 ctx atoms at 50M, with the
falsifier floor **recomputed against the 50M pool mixture** (the pre-registered pool
prediction — retained members span ~2.6M-step gaps, E[KL(member‖mixture)] proxy 0.176
nats — mechanically depresses g, so D25's 12M bar 0.371 is non-comparable and would
fire falsely; Review 1 MF-11). The `aux/loss`-rises prediction gets a ceiling at header
time so it is violable.

**Pre-stated rules.** (1) **Anneal-off on every D26 branch** (one-lever vs the banked
comparator; horizon-matched anneal is an unvalidated fifth transfer; an override is
priced at +3 comparator lanes). (2) Cadence **250k/100/500k unconditionally** — the
struct50m comparator's own cadence, making the treatment one-lever against it; the
one-diff gate runs in BOTH directions (vs D25: five keys; vs struct50m: exactly the
aux keys) (Review 2 MF-7; r0's Z2-6-conditioned fallback was inverted). Z2-6 (eval RNG
neutrality) is demoted to a recorded diagnostic and split: torch-stream half offline,
poke-env half post-D26 — it is NOT server-free (Review 2 MF-11). (3) **The anneal
trap guard lives in `rl/train.py` config validation** (PPOAgent never sees
`total_steps`), interval form — raise iff `0 < lr_anneal_steps < total_steps` — which
still catches the 12M-under-50M trap (38M steps silently at lr 0) while permitting
D26's ratified schedule-prefix smoke config that the r0 set-membership form would have
rejected (Review 2 MF-6). (4) Grader: `d25_grade.py` at 3v3 **silently returns NOT
GRADED** (not a crash); the (n_T, n_C)-keyed fix adds (3,3): (1, 20). (5) Seeds 90–92
(93/94 held) — B's example block's 73–75 is superseded.

**§13, stated correctly (Review 1 MF-2):** §13 is itself PROPOSED/unratified, and its
precondition is threefold — (1) a credited lever at 50M, (2) E1–E4 measured, (3) the
lane-count/cap/rent question answered. D29 bears only on (1). The maintainer's options
on (1): (i) buy +2 comparator lanes (2.95 ld; even then credit needs the full 12M
effect at low spread); (ii) amend to the distribution-free criterion (3v3 complete
separation, p = 1/20) — **Designer A's recommendation** (B did not address it); (iii)
leave closed and retire the 250M line.

## 3. D30 — soft-label aux (premise measured, and it is thin)

**The lever.** Train the D25 head with soft-CE against the opponent snapshot's full
masked action distribution mapped into L6 (the distribution is computed and discarded
today in `pool.py::AgentOpponent.move`; seam widens 3→12 floats; canonicalisation
agent-side per B4; wait-pump rule unchanged; ~145 lines + 12 tests).

**Measured premise (B §4.5, zero lanes, validated against D25's R0-5(c)):** the
opponent's L6 distribution is nearly deterministic — mean max-class mass 0.87–0.90,
36–46% of rows one-hot within 0.01; extra content per row = H(p) = 0.25–0.32 nats;
mechanism is gradient-variance reduction only. **Blocking zero-lane premise test
Z3-3** (fit the head offline hard vs soft; soft must beat hard on held-out hard-label
CE by a pre-stated margin) can kill the arm before any header is ratified.

**The legality confound (B §4.6):** the masked distribution's exact zeros leak the
opponent's true legality — which D25's B11 deliberately withheld — at a measured
0.19–0.20 nats/row, comparable to the whole shape channel. **Designer B's
recommendation** (A did not analyse this): S-A faithful, leak disclosed and the lever
renamed honestly ("the opponent's full decision distribution, including its
legality"), S-B pre-registered as the follow-up; Z3-4 attributes the channels offline.
Maintainer's call.

**Bar and power (A §3.2, verified):** vs frozen D25, bar 0.643–0.667; at the
designer-estimated Δ = +0.030 (naive-linear in g, labelled as such), P(credit)
0.26–0.59 at 5 lanes — comparable to D26's ratified 0.23–0.39. Branch table G1–G7 is
adopted IN FULL (r0 dropped G6/G7): G6 = mechanism falsifier (g ≤ 0.7055 refutes the
premise regardless of win rate); G7 = dose out of band, caveated on the side missed.
Dose: same delivered-ratio scalar as D28; soft-CE's gradient is expected smaller at
coef 0.1 — if the dose band cannot be met, the header pre-decides matched-dose-with-
disclosed-coefficient over matched-coefficient. Fallback: 3-lane mechanism-only
variant (≈1.30 ld), win rate recorded non-letter-bearing.

**Build corrections register (Review 2, binding on the header):** NaN guard in
`canonicalise_soft` (`dist * allow`, clamped sum, `torch.where(valid, …)`) — the r0
sketch NaNs on sentinel rows; the live oracle-identity gate |CE(y|p) − H(p)| < 0.02
accumulates **per 1M-step bin** (per-rollout n≈205 gives se 0.04–0.06 and would kill
healthy lanes); `soft_mass_on_illegal` is a counted-drop with a tape-calibrated
threshold, not a hard crash; the collision rule (n>1 → drop, counted) is written into
the code, not just prose; the dtype/width change's blast radius is six named sites
including D26's ratified R0-B test fixture; **the seam widening lands only after D28
launches** so D28's "identical harness to D25" claim survives at its launch sha.

## 4. Cross-arm decision rules

- D28 retraction branches (A3/A4/A5) **cancel D30**; D29 is unaffected (licensed
  sentence pre-written both ways).
- D28 letter-met-only (A2) drops D30 to the mechanism-only variant.
- **(r1, replacing r0's rule that broke D29's one-diff gate):** if D30 credits before
  D29 runs, whether D29 carries soft labels becomes a maintainer decision requiring a
  fresh one-diff plan and comparator statement — the default remains hard-label,
  five-key, anneal-off.
- D26's readout gates nothing in this chapter, on any branch.

## 5. Sequencing

D28 first (unanimous). The D29-vs-D30 order is decided by evidence that costs nothing:
Z3-3 (can kill D30) and the §13 ruling (decides D29's worth) both land during D28's
build. If Z3-3 kills D30 the question dissolves; if the §13 ruling is (iii), D29 drops
to last or never; if both survive, the maintainer picks (A argued verdict-bearing arms
first; B argued downstream-consequence first — both memos carry the arguments).

**Seeds** (spaced): D28 70–74 (75/76 held), D30 80–84 (85/86 held), D29 90–92 (93/94
held). Never relaunch a dead lane on its own seat. Arms never share a fleet: 12M arms
5-wide alone (~11 h wall), D29 3-wide alone (~37 h; co-scheduling costs +1.0 ld,
measured). No width penalty was detectable 4→5 wide (uncontrolled comparison — stated
as such).

## 6. Staged authorisation (the ask)

- **Stage 0 — free, CPU-only, starts now** (server untouched while D26 runs): Z1-1
  calibrated as amended, Z1-2/3/4, Z3-1..Z3-5 (incl. blocking Z3-3), the torch half of
  Z2-6, the D25-P per-bin trajectory recompute, the trunk-fraction and ledger
  denomination reconciliations, the grader (n_T, n_C) fix. **Held until the D26 fleet
  finishes (~07:15): the two code patches** (delivered-dose logging + its test-arity
  fix; the train.py anneal guard) and the poke-env half of Z2-6 — technically safe
  earlier, but the clean-tree landmine and a possible lane relaunch argue for waiting.
- **Stage 1 — D28 at 5 lanes, 2.16 ld**, conditional on the calibrated Z1-1 screen and
  a ratified header.
- **Stage 2 — D29 (4.45–4.57 ld) and/or D30 (2.16 ld)** per §5. Full tranche:
  **≈8.9–9.0 ld realised (≈9.3 budgeted-rate), ledger ≈28.6 vs the standing 20 cap.**
  Minimum defensible chapter: Stage 0 + Stage 1 ≈ 2.3 ld.

## 7. Maintainer decision points

1. **The tranche** — Stage 0+1 now, or the full chapter, or neither; and which
   denomination the ledger charges.
2. **Re-open the closed 50M line?** If yes: the §13(1) options — (i) +2 comparator
   lanes / (ii) the distribution-free criterion (Designer A's recommendation) / (iii)
   retire the 250M line. §13's other two preconditions stand regardless.
3. **D30's legality channel** — S-A faithful-with-disclosure (Designer B's
   recommendation) vs S-B one-lever.
4. **D29-vs-D30 order** if both survive Stage 0.
5. Standing and unchanged: the DESIGN §8 D7(a) vs CLAUDE.md ladder-eval contradiction.

## 8. Side finding from this session (relay only)

D26's fleet median measured ~311.8 steps/s at 4-wide over 200k→600k **by checkpoint
mtimes — an indicative reading, not the gate's ≥30-min warm window after 1M**. The
pre-stated band is 320–350, so the D-D re-derivation clause MAY fire at the compliant
read; **until that read exists the ratified thresholds remain 275/230 and no derived
numbers are published here** (Review 1 MF-13). The indicative budget projection lands
the ledger at ~19.7, under the 19.9 breach trigger.

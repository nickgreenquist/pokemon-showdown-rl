# Handoff — written 2026-08-16 midday. **NOTHING IS RUNNING. Next unit: D19's pre-reg.**

Read this, then STATUS.md. D25 + D25-P are fully read out, committed AND PUSHED
(`main` clean at `1a73e34`, suite 370 green, fleet down, server still up on :8000).
Nothing is owed on D25 except optional R-6. This file is only about what comes next.

Session model: run this at **Opus 5 / max** for the pre-reg (maintainer is setting it).

## The sequence: (1) D19 pre-reg → (2) ~200-line build → (3) 5 lanes → (4) readout

## 1. D19 — the pre-registration is the unit of work

**D19 = AUXILIARY OPPONENT-TEAM PREDICTION.** CE head over species for the opponent's
UNREVEALED slots, ground truth free from self-play's second seat. `DESIGN.md:658` is the
queue entry — read it first; §12 is RATIFIED so D19 is binding, just unread. Its D18
contingency is resolved (D18 did not credit, so the re-scope clause does not bite) and
its plumbing dependency is satisfied (D18 built the CTDE path; D25 built the aux-head
path). Prior art named there: arXiv 1907.09597, DouZero+ hidden-hand prediction.

**Why it is the right lever:** D25 just proved the mechanism at +0.0770 with three
converging separations. D19 points identical machinery at the thing gen1 randbats
actually hides (5 of 6 mons at turn 1) — and it is the lever that could earn the
**"belief state"** claim we deliberately refused for D25. Highest novelty value, which
is the chase.

### THE BUDGET DECISION — settle this before writing anything else
**The ledger is 17.91 of 20 chase lane-days** (re-measured 2026-08-16, 78 lanes). A
5-lane 12M arm costs ~2.17. **5 lanes puts the chase at 20.08/20 — over.** Options, all
the maintainer's call: 3 lanes (19.21/20, but n=3 guts the seed-clustered credit line
and the exact-permutation levels are enumerated at n=5), 5 lanes and raise/retire the
budget, or bank D19 and stop the chase at D25. **Do not design a 5-lane arm without
naming this.** It is the first question of the session, not a footnote.

### The primary-read decision
DESIGN's D19 note says a 12M win-rate PRIMARY is "effectively un-creditable at
advisory-scale effects" (fresh 5-seed comparator put Rung-2 12M seed sd at ~0.036) and
that D19 must therefore be mechanism-primary in D23's shape. **D25 partly falsified
that**: it credited on win rate at 12M under the clustered rule at +0.0739, because the
effect was NOT advisory-scale. So win-rate-primary is back on the table IF you expect a
D25-sized effect. Argue it explicitly in the header rather than inheriting either
default. Frozen comparator: **0.54452, sd 0.03558, 5 seeds** (never re-score).

### Write the header against `configs/showdown_sp_actpred12m_placebo.yaml`
That is the best-specified pre-reg in the repo — use it as the template, and carry these
FIVE lessons the D25/D25-P cycle actually taught (each cost real adjudication time):
1. **Name the across-lane aggregator.** R-4 fixed its bands and never said median vs
   max. It mattered: median read CONFIRMED, worst lane read RESIDUAL. Same branch either
   way that time — next time it might not be.
2. **Leave no unnamed cells.** R-4's view-2 partition had a silent gap at
   (A1+0.02, A1+0.05]; s61 landed in it. Partition-complete or it will bite.
3. **Decide up front whether dose is matched, and how you'd know.** D25-P's placebo ran
   at 3-31% of the frozen trunk band, so the a-fortiori branch was unreachable and
   "generic aux gradient helps" survives untested. **A matched-dose control is the
   obvious improvement for D19** — D19's gradient flows into the ACTOR trunk, so this
   matters more, not less.
4. **Restate the credit line VERBATIM incl. the larger-of (binomial vs seed-clustered)
   se_diff clause.** Omitting it forced a maintainer adjudication once already.
5. **Sign-dependence.** A two-sided |x| band is right for VOID screening and wrong for
   the residual cell — leakage is a positive-g phenomenon. Say which side each band
   reads.

### Process the maintainer mandates
**2 Opus agents + reviews for pre-regs / lever designs.** Do not skip it, and do not
spawn agents without the maintainer asking — raise it and let them trigger it.

## 2. The build (~200 lines, after ratification)
Mirror D25's: aux head + coefficient on `rl/agents/ppo.py` (see the `aux_head` /
`retain_graph` block ~line 1055 and the `aux/*` metric convention). Purity-clean, no obs
change — **the encoder stays frozen at v2/808+ids=828; changing OBS_DIM invalidates every
checkpoint.** R0 gates in the header, unit tests before launch, suite green before
anything runs. Reusable and already parametrised: `d25_grade.py`, `d25_atoms.py`
(`--lanes/--run-prefix/--out`), `d25p_manipulation.py` (`--run-prefix`),
`d22_collect_obs.py`, `d22_dormant_rank.py`, `results/d25/scripts/collect_oppact.py`.

## 3. The lanes
Distinct `--seed` per lane. **62+ are free** (62/63 were held for a D25-P relaunch that
never happened; 57-61 SPENT). Commit docs BEFORE launching, launch from a clean tree,
stagger starts, verify each lane by battle PROGRESS. Expect ~10.4 h for 12M 5-wide at
~310 steps/s wall. Runs go in the MAINTAINER's terminal; evals are fine in-session
(the D25-P locked set took 10 min for 5x3000).

## Do NOT rediscover (measured this cycle)
- **`time/steps_per_sec` is NOT throughput** — mean 361 vs a true wall of 312, emitted
  17,166x against 627 updates. Read Δstep/Δruntime for any wall gate.
- **In-loop `eval/win_rate` (n=100) does not preview a locked number** — it said 0.576,
  the locked answer was 0.5415. Per-lane noise does not average out at 5 lanes.
- **Three different ctx metrics** — tau025 dormancy, srank99 effective rank, live ctx
  units. They move independently; do not conflate them.
- Trunk ratio = `aux/trunk_norm` ÷ `aux/policy_trunk_norm`, **ratio of means** (a
  mean-of-ratios is Jensen-inflated 1.3-1.5x; I inverted it once).
- Per-lane analysis loops: bind data eagerly. A late-binding closure silently reported
  one lane's numbers as all five, and the tell was values identical to 4 decimals.
- `d25_grade.py --placebo` needs `--s1-control results/d23/dormant_d25_control.csv` for
  n_C=5; at n_C=3 it correctly refuses to grade.
- `results/d25/` + `results/d25p/` are the ONLY copies of the frozen tapes and every
  grade artifact; both are backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- vs-SH 0.6185 is still ~40% GXE territory. Nothing here is "nearly solved."

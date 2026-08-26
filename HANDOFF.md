# Handoff — written 2026-08-26 evening, for a fresh-context session

**Nothing is in flight. Tree is clean. Suite green (573 passed, 17 skipped).**
Fold this into STATUS.md / SESSION_LOGS.md on pickup and restore the empty stub.

## Read order

1. `STATUS.md` — authoritative, 60-line cap.
2. **`CHAPTER5.md`** — the current chapter. Shape RATIFIED 2026-08-26; **50M
   is a hard ceiling**; §3 has the maintainer's six candidate levers (they are
   FIRST-CLASS and may not be dropped without a ruling), §3b the assistant's
   subordinate additions, §5 the branch table.
3. **`configs/eval/ch5_r1_offsh.yaml`** — the R1 pre-registration, **draft r5,
   NOT RATIFIED, NOT LAUNCHABLE.** Most of its content is in YAML comments;
   the `grading:` block is AUTHORITATIVE and machine-checked by
   `tests/test_ch5_prereg.py`.
4. The 2026-08-26 SESSION_LOGS entries (`grep -n '^- 20' SESSION_LOGS.md | tail -12`).
5. **Do NOT read `DESIGN.md` for "what next"** — HISTORICAL/SPENT banner.

## What Chapter 5 is, in one paragraph

The end goal is **ladder run #2 against humans with a better model**. R1 is
three ZERO-TRAINING reads on checkpoints already on disk (C0 = L2 off FP@20,
the 50M lanes off FP@20, search on 50M, a wider ensemble), gated on an off-SH
seat that is **built, gated and smoked**. R2 is one training arm chosen by §5's
branch table. R3 is the ladder. **R1 may produce the R3 model on its own** —
if the wider ensemble or search-on-50M beats L2 off-SH, no retraining is needed.

## The state of the R1 pre-reg, honestly

It has been through: 2 design memos -> synthesis -> 2 reviews -> a completeness
sweep -> 3 disposition agents. **Every round found real defects in the
assistant's synthesis, several of them arithmetic.** The most recent found a
**sign inversion in the primary read's own grading rule** and a bar that
breached the file's own `max(floor, 2*se)` — the second time that same rule
broke, and the test of the day passed it both times. The test is now an
equality check. **Treat this file as load-bearing and verify its numbers rather
than trusting them.**

## What still BLOCKS launch

1. **~70 open items were dispositioned but NOT all applied.** The three
   disposition memos carry **paste-ready text** for everything adopted:
   `design_ch5/{disp_A,disp_B,disp_RV}.md` in
   `../pokemon-showdown-rl-d25-backup-20260815/`. r5 applied the
   highest-consequence ones only. **Working through the rest is the next
   mechanical task** and needs no new judgement.
2. **Five build items with no code yet** (designer B): a wave script (so
   `G-SERIAL` names an artifact — it is currently ungradeable), a grader with
   `--selftest` (nothing in the tree applies a CH5 gate to an arm JSON), a
   NO_PROGRESS abort in `ch3_r4_fp_runner.sh` (~10 lines, paste-ready in
   disp_B), the `OUT == results_dir` rule, and the username scheme — **which
   must be written BEFORE the six arms are added, because that is the next
   mechanical edit anyone makes.**
3. **Arms A1-A3 / B1-B3 and the R1-C compositions are deliberately not
   enumerated.** They wait on item 2 and on the maintainer calls below.

## TWO MAINTAINER DECISIONS ARE OWED

- **`grading.r1c_scope_escalation`** — R1-C declares two rosters (E3, E7) and
  budgets one. Honest cost is ~5.3 h more, or cut the candidate list, or defer
  R1-C to R2. Options are in the key.
- **`grading.chapter5_s3c1_edit`** — this session edited a RATIFIED document
  (`CHAPTER5.md` §3 C1) on designer A's finding. A had reserved that call to
  the maintainer. The edit is a factual correction and stands, but is flagged
  `AWAITING_RETRO_RATIFICATION`.

## Numbers you will want, all measured this session

- **Costs vs FP@20, marginal, startup stripped:** ensemble **1.60** s/battle,
  search@M **2.68**. Realized greedy on the banked arms: **1.44-1.53** (NOT
  CLAUDE.md's 1.20). R1 total ~**7.5 h**, serial k=1 mandatory.
- **Comparator:** 12M greedy **0.34867** off FP@20, n=12,000, 4 lanes.
- **Variance decomposition:** 12M off-FP sigma_seed **0**; 12M vs-SH 0.0076;
  **50M vs-SH 0.0624 (8.2x)**. Hence "50M is flat vs SH" is **0.44 se against
  a 0.0735 bar — not a weak claim, NOT A CLAIM.**
- **n does not bind the fleet-mean bar past 552 battles/lane.** s_50 binds.
- 50M pins (verified 828-d, entity_deepsets, ids-on, load through the seat):
  s80 `8b6546e2...`, s81 `47849ba0...`, s82 `c7cd5d8d...`.

## Landmines added this session

- `ch3_r4_fp_runner.sh:39` defaults `SEARCH_TIME_MS` to **100** — an arm
  omitting `search_time_ms` silently runs FP@100. The seat's own
  `declared_search_time_ms` CANNOT catch it (it copies the same YAML); assert
  FP's own `Sampling N battles at M ms each` lines, where `N*M == 2*declared`.
- `ch3_fp_h2h.py` `seat` defaults to **s65**, and where s65 is pinned the sha
  assert PASSES. The seat now stamps `seat_lane_defaulted`; gate on it.
- **`results/` is gitignored and single-copy.** FP's stdout IS the G2 second
  tally. This session's calibration logs lived only in an agent scratch dir
  before being rescued to `results/ch5_r1_offsh/` and mirrored.

## Open, unchanged

- 9 commits UNPUSHED — **ask before pushing.**
- `CLEANUP.md` still needs rulings.
- Seeds 66/67, 75/76, 83/84, 93/94 remain HELD.

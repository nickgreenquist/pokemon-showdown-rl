# Handoff — CH5 R1 COMPLETE, re-score running. Written 2026-08-27 ~22:35Z

**R1 is done: 9 arms, zero voids, G2 exact on every one.** One job is still
running (`RS80`, the mandatory fresh re-score). Two maintainer decisions open.

## 1. Is the re-score finished?

    tail -3 results/ch5_r1_offsh/wave.log
    tail -3 results/ch5_r1_offsh/watchdog.log

`RS80` = search@M on s80, n=3000, launched 22:28Z, ETA ~2.3 h (~00:50Z).
**If `WAVE COMPLETE` and `rs80.json` exists:**

    python scripts/ch5_r1_grade.py --out results/ch5_r1_offsh/grade.json

**If it died:** sweep, then relaunch. Never re-run a killed arm IMMEDIATELY —
its Showdown room stays poisoned for hours (CLAUDE.md landmine a3); either
wait, or restart the server (`kill` the `pokemon-showdown start` pid and
relaunch from `showdown/`), which clears all rooms in seconds.

    pkill -9 -f 'run.py .*--ps-username ch5'; pkill -9 -f 'foul-play/bin/python -c from multiprocessing'
    ARMS="RS80" nohup bash scripts/ch5_r1_wave.sh > results/ch5_r1_offsh/wave.driver.log 2>&1 &

## 2. What RS80 is for, and the rule that makes it mandatory

The R1-B search object scored **0.4470 at n=1000**. That is a SELECTION score
and **may not be published**. Q6: "Whatever is chosen for a ladder run is
RE-SCORED fresh before any number is published." RS80's number is the
publishable one. s80 was picked by the pre-registered ORTHOGONAL rule (highest
banked vs-SH, 0.74233) because B80 and B81 tied exactly at 0.4470 — breaking
the tie on the off-FP score would be selection on the read's own metric.

## 3. R1's answers (all in SESSION_LOGS 2026-08-27 evening)

- **R1-A PRIMARY: s82's collapse REPRODUCES off-FP, +0.0965 vs bar 0.0369,
  5.2 se.** A genuinely bad seed, not an SH artifact.
- **R1-A FLEET: WITHIN x NON-RESOLVING.** −0.0113 vs a realized bar of
  **0.0717**. The O-4 cliff predicted this before any datum. Action taken
  verbatim: stop buying battles; buy LANES or drop the scale question.
  **"flat" is BARRED; the realized 0.0717 travels with any sentence.**
- **R1-B: search HELPS.** Within-lane mean **+0.1010**, bar 0.0561, 3.6 se.
  Helps MOST on the worst lane (s82 +0.148 vs s80 +0.051). **CEILING: licenses
  search as an R3 DEPLOYMENT CANDIDATE and nothing else; does NOT reverse
  MU-8 (z = −2.80); never set beside the 12M cell.**
- **R1-C: NOT DELIVERED.** E3 0.3623 BELOW C0 0.3893; E7 0.3827 WITHIN.
  L2 remains the ensemble incumbent. The pre-registered soft-AND mechanism
  explains it and IS licensed to be used.
- **C0 = the repo's first complete (proxy, ladder) pair**: 0.3893 off FP@20
  at n=3000, alongside GXE 59.6% / Glicko-1 1573±27 / Elo 1292 at n=200.

## 4. MAINTAINER RULED 2026-08-27 — R3 NOW, THEN A RETRAIN THAT IS NOT OPTIONAL

Verbatim: *"assuming ladder is one night to get ~200 games, let's do it.
BUT - i definitely want a retrain. that will not be optional. i only am
saying we do ladder again now, then train next. breaking 500 is one goal,
not the end goal (top500)"*

**SEQUENCE IS FIXED: R3 (ladder #2) -> R2 (retrain). Both happen.**

- **R3 NEXT, as soon as RS80 lands.** Ladder the re-scored search object,
  ~200 rated battles, one night, per `configs/eval/ladder_r1.yaml`'s protocol
  (run with `scripts/ladder.py`; `scripts/score_ladder.py` is a Connect-4-era false
  friend). Use a FRESH account/username — do not reuse `nickgen1rbrlbot`, or
  the new rating is contaminated by the old object's history.
  **SET EXPECTATIONS IN THE READOUT: top-500 needs Elo 1357 and we sit at an
  implied true ~1232 (we score 0.340 against the 1300-1400 band). Search
  buying +0.058 off Foul Play will NOT close ~125 Elo.** R3 MEASURES the
  improvement; it is not an attempt on the list. **Breaking top-500 is A
  goal, not the end goal** — the maintainer said so explicitly.
- **R2 RETRAIN IS COMMITTED, NOT CONDITIONAL.** It follows R3 regardless of
  what R3 reads. Do not re-litigate whether to train.
- **A-BR-1 (4th 50M lane, ~12.5 h)** — RECOMMEND **NO** standalone; it folds
  into R2's seed count. Still the maintainer's call.
- **A-BR-5**: CHAPTER5 §1 says ONE (proxy, ladder) pair. C0 now makes that
  exactly one, so the sentence may finally be TRUE — re-read before editing.

## 5. THE R2 LEVER — batch size, and the one thing that needs ruling

Maintainer asked whether the retrain uses the batch lever. **Assistant
recommends YES**, and R1 strengthened the case from "H&L did it" to evidence
from our own fleet:

- H&L consume **15,360 episodes per update**; we consume **~34** (rollout 128
  x 8 envs = 1024 steps at ~30 decisions/episode). ~450x, regimes inverted.
- **R1-A measured sigma_seed = 0.0617 across the 50M fleet, one lane 0.10
  below its siblings. Noise-dominated updates are the textbook cause of
  exactly that.** So the pathology A4 targets is one we have now MEASURED,
  not one we imported.

**THE RULING THAT IS OWED, and it is a real conflict:** R1-A routed to
WITHIN x NON-RESOLVING, whose pre-registered action is *"stop buying battles,
and either buy LANES or drop the scale question for the chapter."* Buying
lanes is **C2**, a FIRST-CLASS maintainer lever. Batch is **A4**, an
assistant §3b addition that COMPETES but may not displace a C-item without an
explicit ruling. More seeds treats the symptom; bigger batches treat the
cause.

**RECOMMENDED SHAPE:** take the branch table's SECOND option — explicitly
DROP the scale question for the chapter (permitted verbatim) — and spend R2
on batch: **3 new 50M lanes at ~1,000 episodes/update, with the banked
s80/s81/s82 as a FREE control.** ~37.4 h wall / ~4.6 lane-days; the control
costs nothing. It is a clean one-lever test AND incidentally delivers the
three extra lanes C2 wanted.

**BOUNDS AND CONFOUNDS, so neither is discovered late:**
- At the 50M ceiling the dose is bounded. Copying H&L's 15,360 leaves **109
  updates** and PPO will not learn in 109. **~1,000 episodes/update is the
  reachable dose**: ~1,630 updates, still 3x more than H&L used at all (500),
  closing ~30x of the ~450x gap. Mechanically `rollout_steps 128 -> ~3840` at
  `num_envs 8`; keep `minibatches: 4` (lands ~7,680, near H&L's vbatch 8192).
- **CHANGE BATCH ALONE.** H&L's `gamma 0.95` + dense shaping + return-balanced
  both-seat batches are COUPLED; our own shaping arm read NULL. Copying the
  recipe piecemeal is not the test.
- **UNTESTED:** at fixed total steps this trades update COUNT for update
  QUALITY and nothing here has measured which side binds.
- Seeds 66/67, 75/76, 83/84, 93/94 are HELD and available; lanes MUST use
  distinct seeds or they collide on Showdown usernames.
- Full detail: `CHAPTER5.md` §3b A4, and `prior_work/README.md`'s H&L entry.

## 6. Amendments to a RATIFIED pre-reg, all disclosed in its banner

r7 added `dose: M` to the B arms (they were unlaunchable without it).
r8 added the `RS80` re-score arm. Both are transcriptions of values the file
already pre-registered in prose, not new choices. **`prereg_sha256` differs
across arms: `80245bbd` (A80/A81/A82/CE3) → r7 → r8.** Nothing else moved.

## 7. THE RATIFIED FOUR-STEP PLAN (maintainer, 2026-08-27)

1. **Ladder now** with what we have (R3, the re-scored search object).
2. **Retrain on BATCH — not scale.** 50M stays the chapter ceiling.
3. **Check offline results, then perhaps ladder that.** NOT optional extras:
   a headline-grade result owes the **ANCHOR BATTERY** before any README row —
   vs-SH (locked protocol, 3000/seed, the credit line) PLUS BC-clone h2h PLUS
   Foul Play h2h, anchors descriptive and never verdict inputs. And **FP@20 is
   an INSTRUMENT, not a rung**: a fleet that beats FP@20 next faces **FP@100**
   on `configs/eval/fp_budget_ladder.yaml`, then FP@500.
4. **Then scale — TWO FLAGS, both raised 2026-08-27 and neither resolved.**
   - **(a) IT LEAVES CHAPTER 5.** 50M is the RATIFIED hard ceiling (§7.4).
     Going past it opens a new chapter and needs an explicit ruling; it is not
     a next step inside the current plan.
   - **(b) THE REASON IT MAKES SENSE IS STRONGER THAN "batch worked, stack
     scale on it" — AND IT COMES WITH A PRE-COMMITTED SUCCESS CRITERION.**
     R1-A did NOT find that scale fails; it found the scale question is
     **currently UNANSWERABLE**: effect 0.011 against a bar of **0.0717**,
     because sigma_seed = 0.0617 at k=3. More battles cannot fix that — the
     clustered term contains no n. **So if batch shrinks sigma_seed, the scale
     question becomes measurable FOR THE FIRST TIME, which makes batch a
     PREREQUISITE for a meaningful scale test rather than a gain to compound.**
     **CHECK THIS BEFORE BUYING SCALE: compute sigma_seed across the
     batch-trained fleet and compare against 0.0617. If it did not shrink,
     scale is STILL unmeasurable at k=3 and you would be buying an answer you
     cannot read.** Decide this in advance, not at readout — the D25-P lesson.

## 8. Do NOT, while anything runs

Edit `configs/eval/ch5_r1_offsh.yaml`, `scripts/ch3_r4_fp_runner.sh` or
`scripts/ch3_fp_h2h.py` — runner and seat are invoked FRESH PER ARM.
Docs and `scripts/ch5_r1_grade.py` are safe.

## 9. Open, unchanged

`CLEANUP.md` needs rulings. **main is UNPUSHED — ask before pushing.**

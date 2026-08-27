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

## 4. TWO DECISIONS OPEN (assistant recommendations, maintainer's call)

- **A-BR-1 — buy a 4th 50M lane (~12.5 h)?** RECOMMEND **NO** standalone:
  R1-B showed search lifts the bad lane most, so seed quality matters less
  once search is on. Let it fold into R2's "more seeds" lever instead.
- **R3 now vs R2 first?** RECOMMEND **R3 now** on the re-scored search object.
  It is materially better than L2 with zero training, and the ladder is the
  only thing that answers "are we actually better". Caveat: top-500 is ~125
  Elo away and this will not close it — R3 measures, it does not crack the list.
- **A-BR-5 still open**: CHAPTER5 §1 says ONE (proxy, ladder) pair; C0 now
  makes that exactly one, so the sentence may finally be correct — re-read it.

## 5. Amendments made to a RATIFIED pre-reg, all disclosed in its banner

r7 added `dose: M` to the B arms (they were unlaunchable without it).
r8 added the `RS80` re-score arm. Both are transcriptions of values the file
already pre-registered in prose, not new choices. **`prereg_sha256` differs
across arms: `80245bbd` (A80/A81/A82/CE3) → r7 → r8.** Nothing else moved.

## 6. Do NOT, while anything runs

Edit `configs/eval/ch5_r1_offsh.yaml`, `scripts/ch3_r4_fp_runner.sh` or
`scripts/ch3_fp_h2h.py` — runner and seat are invoked FRESH PER ARM.
Docs and `ch5_r1_grade.py` are safe.

## 7. Open, unchanged

`CLEANUP.md` needs rulings. **main is UNPUSHED — ask before pushing.**

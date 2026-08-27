# Handoff — CH5 R1 wave running overnight, written 2026-08-27 ~01:40Z

**The wave is LIVE and detached (PPID 1). It survives the agent session
ending. It does NOT survive the Mac sleeping.**

## If you are reading this in the morning: three commands

1. **Is it still going, and how far?**

       tail -20 results/ch5_r1_offsh/wave.log

2. **If `WAVE COMPLETE` is the last line — C0 IS STILL OWED A RE-RUN.**
   C0 ops-failed early (see below) and the wave skipped it. Re-invoking the
   wave picks it up automatically; every finished arm is skipped.

       nohup bash scripts/ch5_r1_wave.sh > results/ch5_r1_offsh/wave.driver.log 2>&1 &

3. **If it died mid-arm** (no wave process, no `WAVE COMPLETE`): same command.
   Arms are individually resumable; a partial arm re-runs WHOLE, so you lose
   at most the arm that was in flight. Before relaunching, sweep any orphans:

       pkill -9 -f 'run.py .*--ps-username ch5'; pkill -9 -f 'foul-play/bin/python -c from multiprocessing'

## State at hand-off

| arm | status |
|---|---|
| C0 | **OPS FAILURE, owed a re-run** — runs last, disclosed deviation from `wave_plan.order` |
| A80 | **COMPLETE, all gates pass, not void.** 0.3960 off FP@20, n_eff 1000 |
| A81 | running |
| A82, B80/81/82, CE3, CE7 | queued |

**ETA ~7.1 h from 01:40Z (so ~08:45Z), including the C0 re-run.** Disk is
fine: ~4 GB of `fp.stdout` against 173 GB free.

## Do NOT, while the wave runs

- Edit `configs/eval/ch5_r1_offsh.yaml`, `scripts/ch3_r4_fp_runner.sh` or
  `scripts/ch3_fp_h2h.py`. **The runner and seat are invoked FRESH PER ARM**,
  so an edit changes the instrument mid-experiment and no gate catches it.
  Docs and `ch5_r1_grade.py` are safe (the grader is not invoked by the wave).

## Grading — before ANY number is quoted

    python scripts/ch5_r1_grade.py

It self-tests against banked CH4 artifacts first, refuses to grade an arm
carrying an ops-failure sentinel, and re-derives every bar from n.

## What is owed to you, unchanged

- **A-BR-1** — buy a 4th 50M lane? (designer A says NO)
- **A-BR-5** — CHAPTER5 §1 still says ONE (proxy, ladder) pair; there are ZERO
- `CLEANUP.md` rulings; **main is unpushed — ask before pushing**

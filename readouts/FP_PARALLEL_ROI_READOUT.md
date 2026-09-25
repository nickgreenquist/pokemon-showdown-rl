# FP-parallel ROI, Phase 1 — how much faster could the reads queue's Foul Play phase run with k arms at once?

**STATUS: READ 2026-09-25T01:42Z.**
- **The ROI.** This week's 14-arm FP phase (R6 reads queue, k=1, FP@20) took **19.73 h**. With a fixed-iteration Foul Play (FP@N, N = 25,000 / 12,000) it projects to **3.27 h at k=8** and **4.65 h at k=6**. That is ~6× faster, ~16.5 h saved per reads queue. Waves end with their slowest arm, so read it as ≈3.3–3.6 h.
- **Saturation.** Nothing saturates up to k=8: 8.37 of 10 P-cores busy, E-cores idle, the Node server at 0.20 cores, ≥12.9 GB free.
- **The one cost.** Per-core speed: Foul Play's iterations/ms fall to **0.81× by k=8**.
  - That fall is why FP@20 cannot go parallel: at k≥4 it searches 16–19% less per move.
  - It is also why FP@N's own searches slow there. The 3.27 h already includes that. On the same R5 anchor, FP@N reads 3.22 h where the raw FP@20 curve would say 2.87 h.
- **Provenance.** Every number here is printed by `scripts/fp_parallel_probe_read.py` into `results/fp_parallel_probe/read_final.txt` and `roi.json`, except where a line names another file.
- **Scope.** This credits nothing: it is an ops measurement, and FP@20 was a load generator. No win rate from it is quoted anywhere.
- **PHASE 2 (the FP@N patch plus its FP@N-vs-FP@20 calibration) WAITS FOR THE MAINTAINER'S GO.**

JOURNEY: off-arc eval ops, assigned by the maintainer (2026-09-24). It serves every future off-FP read, starting with R7's.

Branch `fp-parallel-probe`, commit `e6a425a`, clean. Worktree `../pokemon-showdown-rl-fpprobe`. The main checkout was never touched.

## What ran

- **Arms.** k = 1, 2, 4, 6, 8 identical arms ran at once, 150 battles each, on the one `:8000` server. k=8 ran only because k=6 projected to 8.45 ≤ 10 cores (`driver.log`).
- **The seat.** The **E3WR object**: ENS3 of the three W finals, c6 off, loop breaker on. That is R6's committee floor arm.
- **Foul Play.** Production FP with one **logging-only** patch, running from a separate copy (`../foul-play-fpprobe`). It uses scripts/ch3_r4_fp_runner.sh's exact command line: `--search-time-ms 20 --search-parallelism 1`, the reads queue's env exports, and one username pair per arm.
- **Window.** Each k is read in its **steady window**: from the poll at which every arm is past its first battle, to the poll at which the first arm finished. No startup, and no arm running alone. The windows were 231–243 s.
- **Gate.** A quiet-box gate (the reads queue's two nets) passed before every k.
- **Slot.** The slot was agreed with r6-runner and r7-runner: right after R6's `QUEUE DONE` (01:07:53Z), 01:08:30–01:42:32Z.
- **Driver.** `scripts/fp_parallel_probe.py`, launched by `scripts/fp_parallel_probe_after_queue.sh`.

## Throughput scaling (FP@20, steady windows)

| k | window | battles | turns | agg battles/h | turn speedup | per-arm turn rate | FP iters/ms p50 vs k1 (2×20 ms) | cores tracked | cores/arm | Node cores | P busy mean / p95 | E busy | min free GB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 241 s | 149 | 4,366 | 2,226 | 1.000 | 1.000 | 1.000 | 1.031 | 1.031 | 0.029 | 1.126 / 1.284 | 0.170 | 15.64 |
| 2 | 231 s | 292 | 8,355 | 4,547 | 1.994 | 0.997 | 0.948 | 2.069 | 1.034 | 0.048 | 2.116 / 2.156 | 0.126 | 14.96 |
| 4 | 238 s | 581 | 16,543 | 8,794 | 3.838 | 0.960 | 0.838 | 4.155 | 1.039 | 0.095 | 4.203 / 4.263 | 0.130 | 14.76 |
| 6 | 238 s | 875 | 24,654 | 13,212 | 5.706 | 0.951 | 0.829 | 6.220 | 1.037 | 0.139 | 6.285 / 6.350 | 0.171 | 13.92 |
| 8 | 243 s | 1,152 | 33,580 | 17,066 | 7.626 | 0.953 | 0.807 | 8.268 | 1.034 | 0.198 | 8.367 / 8.466 | 0.248 | 12.94 |

- **Speedups are per TURN.** 150-battle blocks carry ~3% (1 sd) battle-length noise, and a k's effect is on the speed of play, not on battle length. Turns per battle in the windows were 28.2–29.3.
- **Integrity held in every k.** All arms 150/150, 0 errors, 0 seat relaunches, every challenge resolved (G3).
- **Strictly serial per seat.** `max_concurrent_live_battles` was 1 and `concurrent_decisions` 0 on every arm.
- **Turns cross-check.** The seat's per-battle turns equal Foul Play's `|turn|` count on every arm.
- **No window CONTAMINATED.** Foreign load inside the windows was 0.10–0.21 cores (WindowServer, sysmond, Activity Monitor, the other sessions' CLIs).

## Per-process CPU, per arm (mean over the k arms)

| k | FP search worker | FP main | our seat | Showdown (all processes, whole server) |
|---|---|---|---|---|
| 1 | 0.882 | 0.091 | 0.029 | 0.029 |
| 8 | 0.875 | 0.101 | 0.033 | 0.198 (0.025 per arm) |

An arm is one core, and ~85% of that core is Foul Play's single search worker (`--search-parallelism 1` runs the 2 or 4 sampled searches back to back on it). The seat, even a 3-member committee, costs 0.03 cores, so the seat kind cannot move this curve. At k=8 the whole server runs 0.042 cores in sockets, 0.098 in its four simulators and 0.052 in the main process.

## Where it saturates: nowhere up to k=8

- **P-cores.** 8.37 of 10 busy (p95 8.47), and **no poll reached 90%** P-core saturation. k × cores-per-arm stayed inside the 10 P-cores at every k (8.27 tracked at k=8).
- **E-cores.** 0.13–0.25 cores busy, the idle level. Nothing spilled onto them.
- **The single Node server.** 0.20 cores at k=8. It is not a bottleneck.
- **Memory.** ≥12.94 GB available and swap flat at 1.0 GB. At k=8, 8 seats peak at 3,969 MB RSS, 8 FP workers at 1,487 MB and 8 FP mains at 454 MB.
- **Projected ceiling.** 10 P-cores ÷ 1.034 cores/arm ≈ **9.7 arms** before spill.
- **What degrades before that is per-core speed.** Foul Play's median iterations/ms falls to 0.948× at k=2, 0.838× at k=4, 0.829× at k=6 and 0.807× at k=8. The 4×10 ms branch falls the same way: 1,085 → 1,034 → 937 → 924 → 904.
  - The E-cores stayed idle, so this is not spill.
  - The cause is not measured (no `powermetrics` without sudo). It is consistent with the P-clusters' clock falling as more cores are active, and/or with shared-cache contention.
  - FP@20's clock-bound search hides it from throughput (the per-arm turn rate is still 0.95). It does **not** hide it from strength: the median 20 ms search reaches **21,000 visits at k=8 against 25,000 at k=1**.

## The ROI: 14 arms × 3,000 battles

- **The scheduler model.** 14 equal arms run on k slots in waves. Phase hours = Σ over waves of 3,000 × s/battle(k_wave).
- **The rate model.** s/battle(k) = anchor s/battle(1) ÷ that k's per-arm turn rate.
- **FP@N rows.** Every window search is re-timed at N ÷ the iterations/ms it actually got at that k. Forced moves are unchanged. That assumes everything else runs as observed.

| basis | k=1 | k=2 | k=4 | k=6 | k=8 |
|---|---|---|---|---|---|
| FP@20 curve (R5 phase-B anchor 1.64 s/battle) — *not a valid parallel instrument, see above* | 19.13 h | 9.60 | 5.64 | 4.24 | 2.87 |
| **FP@N**, R5 phase-B anchor (1.64 s/battle) | 18.83 h | 9.77 | 6.10 | 4.58 | 3.22 |
| **FP@N**, R6 same-week anchor (1.666 s/battle) | 19.13 h | 9.93 | 6.20 | 4.65 | **3.27** |

- **Waves.** k=4 runs [4,4,4,2], k=6 runs [6,6,2] and k=8 runs [8,6].
  - k=7 would run two full waves [7,7]. It is unmeasured, and between k=6 and k=8's per-arm rates, so it projects to the same ≈3.3 h with one arm fewer per wave.
- **FP@N per-arm turn rate** relative to FP@20 at k=1: **1.016** (k1), **0.979** (k2), **0.871** (k4), **0.858** (k6), **0.841** (k8). At k=1 it is slightly faster: N at the median takes 0.983× FP@20's mean search time.
- **Today's k=1 anchors.**
  - R6 this week: phase wall **19.73 h**, **19.44 h** of seat time over 14 arms, mean 1.666 s/battle (`logs/r6_reads/queue.log`, `results/r6_reads_offfp/*.json`).
  - R5's 14 arms: 19.89 h (`results/monster_reads_offfp/*.json`).
  - This probe's own k=1: 1.617 s/battle in-window. R6's E3WR, the same seat object at NI 5, ran at **1.57**. The probe reproduces production within ~3%.
- **Two optimisms, stated.**
  - A wave ends with its slowest arm. R6's arms spread 1.56–1.82 s/battle, so up to ≈+9% per wave (1.82 against the 1.666 mean). A slot scheduler that starts the next arm as soon as any finishes recovers most of it.
  - The projection keeps the seat/server/FP-main time as observed under FP@20.

## Side check: Foul Play's iterations per search at 20 ms (k=1, quiet box; Phase 2's calibration input)

Every search's `total_visits` and duration were logged in FP's PARENT. The worker's own `Iterations` line runs in a spawned pool process whose logging is never configured, so it never reaches the log.

| branch (`fp/modes/random_battle.py`) | searches | forced (1,000 visits, <2 ms) | visits p5 / p25 / **p50** / p75 / p95 / max | mean | search ms p50 (p5–p95) | iters/ms p50 (p5–p95) |
|---|---|---|---|---|---|---|
| early game: 4 sampled × 10 ms | 1,916 | 1.25% | 10k / 11k / **12k** / 13k / 14k / 16k | 12,256 | 11.31 (10.86–11.84) | 1,084 (907–1,260) |
| otherwise: 2 sampled × 20 ms | 9,140 | 4.38% | 20k / 23k / **25k** / 27k / 73k / 349k | 32,616 | 22.20 (20.83–23.01) | 1,106 (880–3,533) |

- **The time-pressure branches** (2 × 10 ms, 1 × 20 ms at ≤60 s on the clock) **never fired: 0 searches**.
- **Per decision.** Search wall p50 is 45.0 ms (2×20) / 46.2 ms (4×10), and FP's own prep p50 is 2.3 / 3.5 ms.
- **Every visit count is a multiple of 1,000 (100% of 11,056 searches), and the source says why.**
  - poke-engine v0.0.48's `run_mcts_loop` (`src/mcts.rs`) runs `for _ in 0..1000 { mcts_iteration(..) }` and only then checks `start_time.elapsed() >= max_time` (or `times_visited >= n` under `iterations=N`). So a 20 ms budget overshoots by up to one chunk (median search 22.2 ms), and **an explicit N also stops on a whole 1,000**.
  - Forced moves are the binding's doing: `poke-engine-py/src/lib.rs` `mcts()` sets `iterations = 100` when our side has ≤1 option. That produces one chunk, under FP@20 and FP@N alike.
- **Calibration candidates.**
  - The median, **N = 25,000 / 12,000**, gives 0.983× / 0.988× FP@20's mean search time.
  - The N that equalises mean time is 25,445 / 12,143, which run as 26,000 / 13,000 in whole chunks.
  - **The 20 ms distribution is right-skewed** (mean 32.6k, p95 73k, max 349k). States with cheap iterations get up to ~3× the median at p95 and 14× at the max under FP@20, and a fixed N gives them the median. **FP@N is therefore not FP@20 state by state at matched mean time.** Whether it is as STRONG is exactly Phase 2's same-session FP@N-vs-FP@20 test.

## If Phase 2 gets a go: what it needs, measured here

1. **The patch.** One keyword: `monte_carlo_tree_search(state, duration_ms, iterations=N)` at production `fp/search/main.py:82`, with N per branch.
2. **A concurrency-safe runner.** `ch3_r4_fp_runner.sh`'s `kill_fp` does a GLOBAL `pkill -9 -f "foul-play/bin/python -c from multiprocessing"`. That is safe only at k=1: any crash-relaunch would kill every other arm's search worker. Kill by process group instead, as `scripts/fp_parallel_probe.py` does, where every child runs in its own session.
3. **Per-arm username pairs.** The pre-regs already carry them. Hold gates belong at slot boundaries.
4. **Priority.** zsh's `BG_NICE` (on by default) runs every `cmd &` launch at **nice +5**. The R6 reads queue, the trio-A lanes and the Showdown server all ran at NI 5 / PRI 31.
   - Plain nice keeps the P-cores: those lanes ran at full speed. It is `taskpolicy -b` (PRI 4) that lands work on cpu0–3.
   - CLAUDE.md's landmine line lumps the two together. r6-runner is raising the wording, and its readout discloses NI 5.

## Disclosures

- **Not a read.** FP@20 was a load generator. Its per-k weakening IS a finding (above), but no win rate is quoted.
- **The seat is one object**, the E3WR committee. 9 of R6's 14 arms are greedy singles. The seat costs 0.03 cores/arm either way, and R6's 14 arms, all seat kinds, ran 1.56–1.82 s/battle.
- **Priority is mixed.** The probe's arms ran at **nice 0** (the maintainer's rule; the driver refuses otherwise), against the Showdown server at **nice 5**. Production runs everything at 5. The P-cores never saturated (max 8.47 of 10 busy), so priority had nothing to arbitrate.
- **Power source changed mid-sequence.** k=1 and k=2 ran on battery (energy mode automatic, `powermode 0`); k=4, 6 and 8 ran on AC (plugged in between k=2 and k=4; `summary.json` provenance).
  - If battery had lowered k=1's clocks, the k≥4 ratios would read optimistic. The per-core rate kept falling on AC, so any such effect is smaller than the decline measured here. It was not measured directly: a same-power k=1 re-run (~6 min) would bound it.
- **The FP copy.** Production = upstream `25c976f` + `scripts/patches/foulplay_gen1_local.patch` (sha256 `8234a15d…`, equal to the live checkout's diff). On top of that, `scripts/patches/foulplay_probe_visits.patch` (sha256 `ea4eb1a3…`) is logging and timing only. `diff -rq` against production differs in `fp/search/main.py` alone.
- **Code.** The seat imported this worktree's `rl` (`PYTHONPATH`; the env's editable install points at main). Main moved during the week (`16e1a28` at run time); the probe used none of it.
- **The maintainer's box.** Light Chrome use during the run is inside the 0.10–0.21 foreign cores above.

## Provenance

- `configs/eval/fp_parallel_probe.yaml` (sha256 `8eb93e4a…`; arms block generated; usernames prefix-free against every `configs/eval` name in main, the R7 worktree and here).
- `scripts/fp_parallel_probe.py` (driver), `scripts/fp_parallel_probe_read.py` (every number), `scripts/fp_parallel_probe_after_queue.sh` (launcher).
- Results (gitignored, on disk in the worktree): `results/fp_parallel_probe/k{1,2,4,6,8}/{summary.json, timeline.jsonl, visits.jsonl, *.fp.stdout, *.seat.stdout}`, the seat JSONs `results/fp_parallel_probe/k*a*.json`, `roi.json`, `read_final.txt`, `driver.log`, `STATUS.log`.
- **Harness history.**
  - Three smokes (1, 1 and 2 arms × 3 battles, each approved by both runners).
  - An Opus review found nine defects, all fixed in `e6a425a` before the slot. Among them: the k=8 headroom check under-counted CPU, the ROI was scaled per battle, a failed k ended the whole sequence, and the chain itself had been niced by BG_NICE.

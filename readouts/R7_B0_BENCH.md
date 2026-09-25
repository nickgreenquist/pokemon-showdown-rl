# R7 B0 — the T-op's per-decision cost at fleet width

**First run: FAIL, NOT VERDICT-BEARING** — the window was not quiet; a quiet-box re-run is the verdict (maintainer,
2026-09-25; see Consequence). Six-wide fleet p99 **7.531 ms** vs the line **3.6 ms** (2 × plan §5's 1.8 ms). Under
FAIL, box 6's R-F2 (`scripts/derive_r7_fleet.py --b0 FAIL`) makes the fleet 3 + 2.

Every number here is from `results/r7_b0_bench/2026-09-25T020423Z.json` (sha256 `dee47c5f1431…`), written by
`scripts/r7_b0_bench.py --widths 5 6`, launched 2026-09-25 02:04:23Z at `fb3364e` on a clean tree (the merge
`9d6a1f8` plus docs). The QoS stamp reads normal and the process ran at nice 0 (checked with `ps`).

## Configuration

These are the bench's pre-stated items (its docstring, from REPLY BOX 2 §1):

- Normal QoS, `torch_threads 1`.
- Five and then six concurrent lanes, each paired with a learner-load process (forward and backward on 256-row
  minibatches).
- The fleet's one-view critic, 1,807,489 params (asserted).
- `--cols 4`, `--chance 2`, k 8.
- 2,000 timed decisions per lane after 200 warmup decisions.

The box has 10 performance and 4 efficiency cores (14 logical, stamped). The engine is `9b88fd6c` (the pinned
sha), zig 0.16.0, 384-byte battle, `bank_zero_copy` true (the mmap'd bank).

Disclosed:

- **Encoder flags.** The encoder ran with V2/IDS **and C6 on**, the fleet's form; the bench's spec does not name C6.
- **Team bank.** The bank was the bench's default, the smallest under `data/engine`
  (`teams_59da482e_e0e0_50000.bin`); timing does not depend on the bank.
- **Position source.** Positions come from scripted-random engine self-play, not the trained policy's
  distribution, so leaves per decision (51.1) are reported beside every number.

## Result

| width | fleet p99 (slowest lane) | lane p50, max | lane mean total | leaves / decision | wall |
|---|---|---|---|---|---|
| 5 | 6.191 ms (lane 4) | 1.527 ms | 1.639–1.728 ms | 51.1 | 7.5 s |
| **6** | **7.531 ms (lane 2)** | 1.767 ms | 1.783–2.096 ms | 51.1 | 8.4 s |

**Per component at six-wide**, across lanes:

- **Critic forward:** mean 1.62–1.91 ms, p50 1.52–1.60 ms, p99 4.91–7.11 ms.
- **Engine and tracker (Rust):** mean ≤ 0.049 ms, p99 ≤ 0.155 ms.
- **PyO3 glue:** mean ≤ 0.061 ms, p99 ≤ 0.287 ms.
- **Root solve:** mean ≤ 0.077 ms, p99 ≤ 0.208 ms.

## Reading

**The budget holds on average and fails on the tail.**

- **Mean cost.** The mean decision costs 1.64–1.73 ms five-wide and 1.78–2.10 ms six-wide, which is at the plan's
  1.8 ms table.
- **The tail.** The p99 is 3–4× the p50, and all of that excess is the critic forward.
- **The tail is uniform.** It shows in every one of the 11 lanes at both widths (critic p99 4.9–7.1 ms), so it is
  structural, not one lane's hiccup.
- **Likely cause.** Six-wide with learner load is 12 busy threads on 10 performance cores. Five-wide is 10 threads
  plus the bench's parent and the OS.

**The window was not perfectly quiet.** The peer sessions' own logs record:

- fp-speedup ran two single-core python processes, each under a second, at 02:04:21Z. That was 2 s before the
  launch stamp, inside startup and warmup, not the timed decisions.
- r6-runner made millisecond reads.
- In r6-runner's `ps` at 02:04:08Z, Terminal was at ~20% of a core and three agent CLIs at 5–12% each.

Nothing was sustained, and the uniform tail argues against those bursts.

## Consequence

The consequence is pre-stated (box 6 R-F2; the generator's `--b0` flag): **FAIL → 3 + 2**. That means five lanes
in the order C1, S1, C2, S2, S3, which is also 10 threads on the 10 performance cores.

Power at the ruled n 6000 (`results/r7_fleet/power.json`):

| layout | P(X-POS) at +0.025 | +0.030 | +0.035 | +0.040 |
|---|---|---|---|---|
| 3 + 2 | 0.49 | 0.75 | 0.91 | 0.98 |
| 3 + 3 | 0.50 | 0.78 | 0.94 | 0.99 |

**THIS READ IS SUPERSEDED BY A QUIET-BOX RE-RUN** (maintainer, 2026-09-25 ~02:10Z: "better to rerun the test
later once box is truly empty"). The window above was not quiet, and a p99 bench is the instrument background load
corrupts. The rule is stated now, before the re-run exists:

- The re-run uses the same command and configuration.
- It runs right after fp-speedup's calibration, with all three agent sessions idle for its ~1-minute window.
- It is THE verdict whichever way it reads, and `--b0` takes its reading.
- This run stays here, disclosed and not verdict-bearing.

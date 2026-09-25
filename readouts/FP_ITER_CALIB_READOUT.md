# FP@N calibration — is a fixed-iteration Foul Play (25,000 / 12,000) the same opponent as FP@20?

**STATUS: READ 2026-09-25T03:50Z.**
- **Verdict: NO DETECTABLE DIFFERENCE.** Our seat (the greedy W final s104, loop breaker on) scored **0.5440 against FP@20** (n 3000, k=1, quiet box) and **0.5385 against FP@N** (n 2999, 8 parallel slices).
  - **delta −0.0055, se 0.0144, z −0.38, 95% CI [−0.034, +0.023].** The se is the slice-clustered one, the larger of the two.
  - This is the pre-stated rule's "candidate replacement" branch: **FP@N at 25k/12k may replace FP@20 as the off-FP instrument — the MAINTAINER RULES.**
  - What this does NOT show: a gap under ~2 se (~0.029) is not excluded. This is a failure to find a difference, not an equivalence proof.
- **G2 is exact on all 9 arms**, after the pre-registered crash-forfeit correction.
- **Instrument checks.** FP@N ran exactly N on 100% of its non-forced searches. The FP@20 control, in the same session, again bought medians of exactly 25,000 / 12,000 iterations. No foreign load was logged in either phase.
- **Speed.** FP@N ran 8-wide at **0.80×** FP@20's single-arm turn rate. That includes ~4% of per-slice startup, so ≈0.83 in steady state, consistent with Phase 1's 0.841 projection.
- **Provenance.** Every number here is printed by `scripts/fp_iter_calib_read.py` (`results/fp_iter_calib/read.json`). The rule and arms were registered in `configs/eval/fp_iter_calib.yaml` before any battle.

JOURNEY: off-arc eval ops. The maintainer said "Go" at 2026-09-25 02:00Z and prioritised this over R7. It serves every off-FP read, starting with R7's. Phase 1 (the ROI) is `readouts/FP_PARALLEL_ROI_READOUT.md`.

Branch `fp-parallel-probe`, launch commit `73f27c0` (clean; every seat stamps `rl_git_dirty: false`). Worktree `../pokemon-showdown-rl-fpprobe`. Production Foul Play and the main checkout were not touched.

## The rule, verbatim from the config (written before any battle)

- delta = WR(vs FP@N) − WR(vs FP@20), n 3000 vs 3000, unpaired binomial se_diff ~0.0128.
- |delta| < 2 se_diff → no detectable difference at this power (a gap under ~0.026 is NOT excluded; this is not an equivalence proof) → FP@N at 25k/12k is a candidate replacement for FP@20; the MAINTAINER rules.
- delta ≥ +2 se_diff → FP@N is WEAKER than FP@20 (we beat it more): raise N and re-run.
- delta ≤ −2 se_diff → FP@N is STRONGER: lower N and re-run.

The rule named the binomial se. The read uses the LARGER of the binomial (0.0129) and the FP@N side's slice-clustered se (0.0144), per the house convention. Both give the same branch.

## What ran

| arm | opponent | when (Z) | n_eff | wins | WR | ties | crash forfeits | G2 |
|---|---|---|---|---|---|---|---|---|
| CAL20 | FP@20 (wall-clock), k=1, quiet-box gate | 02:11:30–03:31:00 | 3000 | 1632 | **0.5440** | 2 | 0 | exact |
| CALN1..8 | FP@N 25,000 / 12,000, 8 slices × 375 at k=8 | 03:31:02–03:50:08 | 2999 | 1615 | **0.5385** | 2 | 1 (CALN8) | exact after the correction |

- **Slice win rates:** 0.547 / 0.552 / 0.565 / 0.528 / 0.480 / 0.576 / 0.509 / 0.551. That spread is the slice-clustered se's witness.
- **Same opponent code.** Both opponents are the same Foul Play copy (`../foul-play-fpprobe` = production + `scripts/patches/foulplay_fpn_calib.patch`). They differ only by `--search-iterations 25000 --search-iterations-early 12000`.
- **The budget is verified, not assumed.** The runner takes it from the arm, never from the environment, and verified it ONCE from Foul Play's own log: CAL20 `time`, every CALN `fixed`. The seat JSONs stamp `declared_search_iterations` 25000 / None.
- **Control first** (CLEANUP L6): CAL20's JSON predates every CALN JSON.
- **The one crash.** CALN8's Foul Play panicked at 03:35:35Z (`Invalid PokemonMoveIndex: 4`, poke-engine `src/state.rs:106`), the known crash class. The runner relaunched it and the in-flight battle forfeits TO US and is EXCLUDED, per the R4 rule verbatim: n_eff = seat-finished − crash forfeits, and wins are reduced by the same count.
  - G2 raw agrees on 8 of 9 arms. CALN8's seat counts 207 wins against Foul Play's 206, which is exactly its one crash forfeit (the designed asymmetry). Corrected, 206 = 206.
  - The relaunch cost ~4 min of dead time while the orphaned room timed out (the seat's `max_concurrent_live_battles` reads 2 on CALN8 alone).
- **Clean box.** No CONTAMINATION line in either phase: the scheduler samples foreign load every 60 s, at the gate's 0.5-core threshold. CAL20 launched on a clear quiet-box gate.
- **Battle length is unchanged:** mean turns 29.21 (FP@20) vs 29.04 (FP@N).

## What each opponent actually ran

| | branch | searches | forced | visits p5 / p50 / p95 | exactly N | search ms p50 (mean) |
|---|---|---|---|---|---|---|
| FP@20 (CAL20) | 2 × 20 ms | 180,048 | 4.32% | 20,000 / **25,000** / 83,000 | — | 22.08 (22.02) |
| FP@20 (CAL20) | 4 × 10 ms | 39,260 | 0.93% | 10,000 / **12,000** / 14,000 | — | 11.28 (11.29) |
| FP@N (CALN) | 2 × 25,000 it | 179,036 | 4.39% | 25,000 / 25,000 / 25,000 | **100%** | 27.47 (26.34) |
| FP@N (CALN) | 4 × 12,000 it | 38,948 | 0.96% | 12,000 / 12,000 / 12,000 | **100%** | 13.03 (13.15) |

- **The same-session control reproduces Phase 1's calibration input exactly.** Medians are 25,000 / 12,000, and the right-skewed tail reaches p95 83k on the 20 ms branch.
- **Forced moves are a property of the positions, not the budget:** 4.3% vs 4.4%. poke-engine's binding runs one 1,000-iteration chunk when our side has ≤1 option, under either budget.
- **FP@N's searches took 1.24× FP@20's time at 8 arms** (27.47 vs 22.08 ms). That matches Phase 1's per-core rate at k=8 (0.807×). This is the time the fixed budget costs, and the strength it keeps.

## Speed: does the Phase 1 ROI hold?

- **Measured.** FP@N 8-wide ran at **0.797×** FP@20's single-arm turn rate over the 7 slices without a relaunch (0.764× with CALN8's dead time).
  - Each slice's wall clock includes the runner's 30 s seat-to-FP stagger plus FP startup once: ~4% of a 375-battle slice, ~0.5% of a 3,000-battle arm.
  - Steady state is therefore ≈0.83×, consistent with Phase 1's projected **0.841**.
- **The ROI stands.** The 14-arm FP phase projects to **≈3.3–3.6 h at 8 slots** against **19.73 h** this week (Phase 1 readout, R6 anchor). The occasional crash relaunch adds its few minutes of dead time to one arm, as it always has.

## For the maintainer's ruling

1. **Adopt FP@N (25,000 / 12,000) as the off-FP instrument in place of FP@20?**
   - **Yes:** every future off-FP read runs 7–8 arms at once.
   - **Beside other work:** a fixed iteration budget is the same opponent at any box load. Load costs it time, never strength. So FP@N reads no longer need an empty box, and can run beside training (slower, still valid). The quiet-box rule stays for any FP@<ms> arm, and the scheduler enforces it.
   - **Banked FP@20 numbers stay FP@20 numbers.** Reads already never difference across sessions (each re-draws its comparator in-session), so nothing banked changes meaning.
   - **The two FP disclosures travel unchanged, with the budget named:** the equivalence test is weakly powered, and the point estimate flatters us. FP@N is calibrated to FP@20's median search, not to a stronger opponent.
2. **Or tighten the bound first.** This read cannot exclude a gap under ~0.029. Another 3000 vs 3000 would bring the se to ~0.010.
   - The FP@N half is cheap (~20 min at 8 slots, any box).
   - The FP@20 half costs ~80 min of EMPTY box. That would be coordinated with r7-runner, whose ~3 h of LR smokes were released at ~03:55Z.

## If adopted: the integration (no empty box needed, ~1 h)

1. **Production Foul Play:** apply the FP@N flag (plus the per-search logging) to `../foul-play`, and regenerate `scripts/patches/foulplay_gen1_local.patch`, the G8 provenance input every FP number stamps.
2. **Merge `fp-parallel-probe` into main.**
   - `scripts/ch3_r4_fp_runner.sh` changes in four ways:
     - Foul Play runs in its own process group and is killed as one group. The box-wide worker `pkill` is gone.
     - A SIGTERM trap cleans up the runner's own arm.
     - The budget comes from the pre-reg, and is verified from Foul Play's log.
     - An unpatched FPDIR is refused.
   - This is strictly safer for today's k=1 queues too.
   - Also merged: the seat's budget stamps and `scripts/fp_arms_parallel.py`, the slot scheduler. It forces 1 slot plus the full quiet-box gate for any wall-clock arm, samples foreign load, and refuses to run niced.
3. **R7's reads pre-reg:** its off-FP arms declare `search_iterations: 25000, search_iterations_early: 12000`. Its queue calls `fp_arms_parallel.py --slots 7` (14 arms = two full waves) instead of the serial loop.

## Disclosures

- **One seat object** (the greedy W final s104, c6 off, loop breaker on): a calibration of the opponent, not of our policy. **n = 3000 per side**, as the brief set it.
- **Load differs between sides:** FP@N ran 8-wide, FP@20 alone. That is the form each will be used in, and the point of the fixed budget. FP@N's strength cannot depend on load by construction: exactly N iterations on 100% of non-forced searches, and Showdown's timers never came near.
- **Priority.** Every arm ran at nice 0 (the scheduler refuses otherwise), against the Showdown server at nice 5, as in Phase 1.
- **The box.** r6-runner's instrument and r7-runner's B0 bench ran BEFORE the calibration. My own dev work overlapped B0's first run at 02:04Z, which the maintainer has since declared not verdict-bearing. Nothing else ran during either phase: the gate passed, and no CONTAMINATION line was logged.
- **Code.** Seats import this worktree's `rl` (`PYTHONPATH`), merged with main at `fb3364e`. The FP copy's diff against production is exactly `fp/config.py` + `fp/search/main.py` = `scripts/patches/foulplay_fpn_calib.patch`, verified by re-applying it.

## Provenance

- `configs/eval/fp_iter_calib.yaml` (arms generated; usernames prefix-free against every `configs/eval` name).
- `scripts/fp_iter_calib_chain.sh` (control first, then the wave), `scripts/fp_arms_parallel.py`, `scripts/ch3_r4_fp_runner.sh`, `scripts/fp_iter_calib_read.py`.
- Results (gitignored, on disk in the worktree): `results/fp_iter_calib/{cal20,caln1..8}.{json,runner.json,runner.log,fp.stdout,seat.stdout}`, `parallel.log`, `parallel_summary.json`, `STATUS.log`, `read.json`.

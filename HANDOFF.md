# Handoff — R7 runner, 2026-09-24 23:55Z (the maintainer asked: context 73%, handoff + clear)

Resume as the single R7 runner (JOURNEY 14; CLAUDE.md binding). Read STATUS first, then the plan's **AMENDMENT BOX 7**
(`docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`): Friday's order and the four maintainer items, with numbers.
Worktree `../pokemon-showdown-rl-r7`, branch `r7-native-search` tip `779d9e8`, env `pkmn-engine-r7`. NOTHING PUSHED
(branch since `a35ff9b`, main since `67f3d30`) — ask before pushing.

## State at 23:55Z Thu 09-24
- **R6:** all six lanes DONE. The reads queue pinned both trios at 04:37Z (PIN-a, PIN-b) and is in its FP phase: 13 of
  14 off-FP arms done, E9RF running since 22:59Z (~1.4 h), then the vs-SH jobs (~1 h) and r6-runner's readout.
  **QUIET BOX: run NOTHING — no tests, builds or evals — until the R6 readout lands.** Docs-only commits on main are
  fine, each written and committed in one step.
- **The a7 session** (`pokemon-showdown-rl-a7`) holds a ~45 min FP throughput probe right after the queue's QUEUE DONE
  line (its waiter, pid 64328, starts it). The box is yours when
  `../pokemon-showdown-rl-fpprobe/results/fp_parallel_probe/STATUS` reads DONE / FAILED / HELD_OUT / SKIPPED_*; it
  also messages. It never starts after Fri 02:20Z and never runs a k that ends after 03:00Z.
- **R7 runs nothing.** G1b is READ (box 5 item 8: the peek is worth nothing measurable at the battle level). The fleet
  pre-reg r3 is final pending the maintainer (box 7), after two Opus reviews, two verification passes and two focused
  passes.

## First actions (Friday, box 7's order)
1. Read r6-runner's R6 readout: it names the base (a / b / ab / w) by trio A's and trio B's own pre-stated branches.
2. Wait for the a7 STATUS file to release the box.
3. Merge `r7-native-search` into main (`git merge-tree` was clean at 02:31Z; re-check). Reinstall the merged extension
   into `pkmn-engine-r7` AND `pkmn-engine-port` (maturin with CONDA_PREFIX set; no job alive in either env). Then the
   suite: `test_engine_bank_mmap.py` and `test_r7_mechanism_reads.py` PASS (not skip), `test_lop.py` none skipped,
   `test_derive_r7_fleet.py`. Commit only on pytest's own return code, never through `| tail`.
4. B0 bench `--widths 5 6` at nice 0. zsh's BG_NICE puts any `cmd &` at +5: launch via the tool's background runner or
   `bash -c 'nohup ... &'`, and check `ps -o nice=`.
5. `derive_r7_fleet.py --base <base> --stage lr-smokes` (power.json already sits in main's `results/r7_fleet/`),
   commit, then `bash -c 'nohup bash scripts/r7_smokes.sh lr <base> > logs/r7_smokes/lr.nohup 2>&1 &'`: three triples
   (searched / control / beta-0), seven vs-SH evals, then the rule -> `results/r7_lr/read_lr.json`.
6. `--stage fleet --lr <chosen> --b0 <verdict>`, commit, then `scripts/r7_smokes.sh shakedown`: both smokes must PASS
   `r7_smoke_check.py`.
7. G2's two-battle smoke.
8. The maintainer ratifies box 7's four items and launches in the foreground (over 5 h, so theirs):
   `ALLOW_SIX_WIDE_DISCLOSED=1 bash scripts/r7_fleet_launch.sh configs/r7_fleet_lanes.txt` (5 lanes, without the
   flag, if B0 fails six-wide).

## Owed to the maintainer (box 7)
X-FLAT's routing (a research-direction call); n 3000 vs 6000 per lane; beta·KL inside the shared clip (kept);
Friday grows by ~3 h.

## Watch
- The worktree has no `runs/` or `results/`: run derive and the checks from main after the merge (or pass absolute
  `--runs` / `--power`).
- The engine env's full suite: 1,183 passed. Its failures are documented classes (SESSION_LOGS 09-24 02:45Z); don't
  chase them as new.
- CLEANUP L10: audit every results-JSON sha stamp (write-time vs launch).
- Memory `r7-runner-setup` carries the state, BG_NICE, and the (spent) pin-window rule.

# Handoff — R6 launch night, written 2026-09-22 00:50Z at the maintainer's request (before a context compact)

**Read in this order:** this file → `STATUS.md` (RUNNING line) → `SESSION_LOGS.md` entries dated 2026-09-21
(cont. 3 onward) and 2026-09-22 → the trio headers (`configs/showdown_r6_trio_a.yaml`,
`configs/showdown_r6_trio_b_fallback.yaml`). **Do not re-derive anything below; execute it.**

## 0. Rulings tonight (all recorded; verbatim quotes in the trio A header and SESSION_LOGS)

- The AGENT launches the fleet and monitors it (a one-off rule-4 authorization). If overnight throughput is
  much slower than the W fleet's, the maintainer pings in the morning, the agent KILLS the lanes, and the
  maintainer relaunches from their own terminal.
- Ladder R6 is CONDITIONAL on offline gains (M-R6-10 in `docs/proposals/ladder_r6.draft.yaml`): run it only
  if an R6 committee beats the same-session re-drawn R5 committee off FP@20 by ≥ ~+0.05 (threshold to
  confirm); otherwise the R6 finals are R7's base and R7 ladders.
- No box prep (pmset etc.) is ever handed over; the launcher's caffeinate is the fix.

## 1. What is running (check first)

- **TRIO A** (W + C6 + outcome heads): `runs/showdown_r6_trio_a_s{304,312,320}`, launched 00:36–00:41Z from
  `bfe8493` (all three stamped clean, c6 true, head 3,075); watchdog pid 44675, caffeinate 44679. ~50 h.
- **The fallback-keys 12M screen**: `runs/showdown_r6_batch12m_fallback_s{220,228}` (c6-off, seeds 220/228),
  ~8.85M at 00:30Z, DONE ≈ 01:20Z. Its read decides trio B (§2).
- **The fleet monitor**: `scripts/r6_fleet_monitor.sh` → `logs/r6_fleet/monitor.log` every 10 min (per-lane
  rate from the two newest 500k rungs vs the W fleet's 1,254 steps/s per lane six-wide; ALERT below 0.6× after
  a lane's first hour; RSS, watchdog verdicts, RESUMED/ALERT counts, memory, Node). `tail -12` it.
- **Armed session watches** (harness tasks; each wakes the agent with a task-notification):
  `bd9tpoym4` = all four screen lanes DONE (the two GO lanes are already DONE; it fires when the fallback pair
  finishes) → run §2. `bllni2hy3` = the reads-queue auto-arm: starts `scripts/r6_reads_queue.sh` (nohup) once
  ≥3 fleet lanes are stable 15 min → prints READS QUEUE ARMED; nothing to do but note it. `bzpggmelk` = the
  fleet wake loop: fires on any `ALERT` line in `monitor.log` or ALL LANES DONE → investigate (§4).
- DONE and banked today: the exit gate CLEARS (RESULTS §35; XTG9 0.6184 vs XGR 0.5866, +0.0319 at z 2.61 →
  IDEAS 4.9 gets R7's first trio); the GO-keys screen read FALLBACK (policy travel 21× less; `results/
  r6_batch12m/read.json`); all three 400k smokes PASS (`results/r6_smokes/`); five review defects fixed.

## 2. THE NEXT STEP: the fallback screen's read → trio B (agent; every command from the repo root)

1. When `bd9tpoym4` fires (or `grep -c "batch12m_fallback_s2.. DONE at step" runs/train_watchdog.log` = 2):
   ```
   /opt/anaconda3/envs/pokemon-showdown-rl/bin/python scripts/r6_batch12m_read.py --screen runs/showdown_r6_batch12m_fallback_s220 runs/showdown_r6_batch12m_fallback_s228 --json-out results/r6_batch12m/read_fallback.json
   ```
   (The partial history.csv files were deleted after an early 4M look, so it re-extracts; ~2 min.)
2. Record it: `python /private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/4570ee72-6701-4009-9d8a-f451912a38a4/scratchpad/record_fallback_read.py`
   (writes both branches: PASS → trio B headers say RATIFIED/LAUNCHED; FAIL → HELD). If the scratchpad is
   gone, edit the "(iii) the maintainer ratifies..." line in `configs/showdown_r6_trio_b.yaml` and
   `configs/showdown_r6_trio_b_fallback.yaml` by hand with the read's numbers from the JSON. Then STATUS's
   RUNNING line + a SESSION_LOGS entry; `git commit`; tree MUST be clean.
3. **If the read PASSES** (verdict GO under the identical rule: kl band, entropy within 0.15 of W's 0.70, EV
   within 0.05 of W's 0.69): launch trio B in the fallback form, then TOUCH NOTHING in the tree until the
   launcher prints `DONE.` (~6 min; a commit during the stagger stamps a lane dirty — `docs/landmines.md`):
   ```
   nohup env TAG=showdown_r6_trio_b bash scripts/monster_fleet.sh configs/showdown_r6_trio_b_fallback.yaml 200000000 328 336 344 > logs/r6_fleet/launch_trio_b.log 2>&1 &
   ```
   Then verify every lane's `meta.yaml` (`git_sha` = the launch commit, `git_dirty` false, `encoder.c6` true,
   params critic 1,807,489 with NO head) and that `runs/showdown_r6_trio_b_s{328,336,344}` exist (the TAG).
   Log it; commit.
4. **If the read FAILS:** do NOT launch trio B. Trio A runs alone. Write the options for the maintainer's
   morning in the log: (a) launch the fallback form anyway with the disclosure (its EV/entropy gaps were
   closing at 4M: entropy 0.86 vs 0.73, EV 0.60 vs 0.68); (b) launch trio B as "W + C6 only" (no batch
   change) — which gives the design its missing C6 comparison; (c) hold trio B.
5. Both screens' lanes are then finished; their watchdogs exit on their own.

## 3. Overnight: monitoring only (no tree edits needed)

- `tail -12 logs/r6_fleet/monitor.log` — one line per lane per 10 min. Expected per-lane rate six-wide: near
  the W fleet's 1,254 steps/s (p10 1,012). Trio B's fallback form has 4× longer updates per 122,880 steps but
  the same cost per env step. ALERT lines: SLOW (< 0.6×), WATCHDOG (a resume/stall), NO PROCESS.
- The watchdogs resume dead/stalled lanes themselves (`runs/train_watchdog.log`); a resume is a DISCLOSURE
  (RESUMES= at readout; `meta.yaml resumes[]` carries from_step + git_sha). Node is kept alive by them.
- Memory: ~2.3–2.4 GB per lane; six-wide ≈ 15 GB of 24 (monitor's `free=` counts free+inactive+speculative).
- Morning report to the maintainer: one table — per lane: steps, rate vs 1,254, resumes, RSS; plus the box
  line. If much slower: the maintainer pings → kill the lanes (watchdogs FIRST: `pkill -f
  'train_watchdog.sh runs/showdown_r6_trio'`, then `kill -TERM -<pgid>` per lane, pgid = pid) and they relaunch.

## 4. Landmines learned tonight (also in `docs/landmines.md` / the log)

- A clean tree must hold for the WHOLE stagger window of a launch, not just at preflight.
- `pgrep -f` / `pkill -f` on a pattern that appears in your own command line matches YOURSELF: anchor
  (`^bash .*/script\.`), never a bare substring; five zombie loops and one killed watch came from this.
- zsh aborts a `&&` chain on a failed glob ("no matches found") — run such lines under `bash -c`.
- macOS `/bin/bash` is 3.2: no associative arrays.
- A watch's terminal-pattern grep must read only NEW lines, or an old "DONE" line re-fires it.

## 5. Numbers to carry (each traced)

Exit gate: XTG9 0.6184 / XGR 0.5866, +0.0319, se 0.0122, z 2.61, 771 ms/decision, change rate 0.110
(`results/exit_gate_r5/readout.json`). GO screen: entropy 0.48 vs 0.70, EV 0.49 vs 0.69, kl_sum 0.72 vs 15.4
(`results/r6_batch12m/read.json`). Smokes: `results/r6_smokes/{a,b,bf}.json` (A: aux EV 0.42/0.38/0.26 at
400k, resume from 123,088; peak RSS 2.35/2.40/1.75 GB). W reference rate: 1,254 steps/s per lane six-wide.

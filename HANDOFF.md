# Handoff — babysit the 100M fleet, then run the frozen eval schedule, grade, record
Written 2026-09-01 ~11:30Z, maintainer-ordered. Read `STATUS.md` first, then this.

**A 2-DAY JOB IS RUNNING RIGHT NOW — §0.** Your work splits cleanly:
(1) light monitoring until ~Wed 2026-09-03 ~11:00Z; (2) on FLEET DONE, the
frozen post-fleet eval schedule; (3) grade; (4) record everywhere. The
GOVERNING DOCUMENT for all of it is `configs/showdown_sp_100m.yaml` —
**RATIFIED 2026-09-01** ("commit, push, ratify"), every cell/bar/disclosure
frozen. Read its header in full before doing anything. The freeze rule is in
effect: no cell, bar, n, aggregator, sidedness, comparator or barred-sentence
list moves, ever.

## 0. RUNNING NOW

    nohup caffeinate -dims bash scripts/ch5_100m_wave.sh   # log: logs/ch5_100m_wave.log

- 3 lanes, seeds 104/112/120, launched fresh 10:58-10:59:50Z (pids at launch
  69144/69525/69635 — reread from `ps`, never trust these), run names
  `showdown_sp_100m_s{104,112,120}`. total_steps 1e8; each lane EXITS ITSELF
  at its 100M crossing rung (`ckpt_1000*.pt` — async rungs are named at the
  crossing step, never grid literals; same for every rung you'll touch).
- Preflight passed on the record: fresh server pid 68702 (age 176 s,
  simulator: 4 verified), disk 171 GiB, reclaimable mem 19 GB.
- The wave babysits: CPU-delta stall watch (3 consecutive zero-deltas →
  kill + `--resume`, 3 retries/lane), progress lines every ~5 min. An RSS/box
  sampler (D-E's read) appends to `logs/ch5_100m_rss.log` every 5 min.
- **Expected rate: ~574 steps/s/lane realized** (the acceptance fleet's own
  3-wide number) → one 500k rung every ~14.5 min per lane → **~48.4 h/lane,
  done ~2026-09-03 11:00Z**. Rungs are the progress read:
  `ls -t runs/showdown_sp_100m_s104/ | head -3`.
- **The stall signature: ALIVE, ZERO CPU, stale log. `pgrep` never catches
  it.** `ps -o time= -p <pid>` twice, 15 s apart. The wave auto-recovers;
  you only act if a lane is DEAD AND OUT OF RETRIES in the wave log — then
  the LANE-FAILURE RULE (pre-reg): `--resume runs/<dir>`, real from_step
  from meta.yaml, fleet does NOT wait, k<=2 → cell K.
- **DO NOT edit `scripts/ch5_100m_wave.sh` while it runs** (bash reads
  scripts incrementally; editing a live script corrupts the instance). After
  FLEET DONE, one deferred fix: its header's launch line should gain
  `< /dev/null` (zsh job control suspended the maintainer's launch because
  nohup leaves stdin on the tty; this relaunch detached it — SESSION_LOGS).

## 1. MONITORING RULES (the pre-reg's, not suggestions)

- **BARRED OUTRIGHT: any checkpoint evaluation — any n, any opponent, any
  lane — until the last lane ends.** This is the biggest trap for an eager
  monitor. It corrupts the throughput record, inflates a time-budgeted FP
  opponent later, and peeks the verdict axis. The R0/D gates diagnose a sick
  lane without an eval; that is what they are for.
- BARRED: extending past 100M, any config/lr change, lane replacement
  outside the ordered-spare protocol (spares 128/136/144, REPLACEMENT only,
  pre-D-D only).
- In-loop `eval/win_rate` (n=100) is visible and NOT ACTIONABLE.
- Periodic health reads (every few hours is plenty; all from
  `scripts/extract_history.py <run_dir>` → history.csv, which works on a
  live run): K6 entropy (STOP a lane only if 3-lane median < 0.15 twice
  consecutively BEFORE 50M), T2 clip_frac (median >= 0.90 x3 → STOP AND
  REPORT), T3 approx_kl (>= 0.5 x3, or ANY non-finite loss/*), D-G lag_p99
  (>= 2 x3 consecutive → STOP that lane), D-H discards (>1% disclose, >5%
  STOP), D-C aux gates (illegal/collision must be exactly 0 — STOP that
  lane otherwise). The acceptance fleet ran all of these spotless; a breach
  is news, not noise. Full table with numbers: the pre-reg header.
- First 200k steps are already past R0's window by the time you read this;
  the fleet launched clean.

## 2. ON "FLEET DONE" — the FROZEN eval schedule, in this exact order

All agent-side (detached, resume-safe, rate-readable). Costs and rates are
pre-registered; outputs go where `scripts/ch5_100m_grade.py` reads them
(`results/ch5_100m/`). NOTHING was allowed to run early.

1. **vs-SH finals** (~6 min): for each seed,
   `eval_checkpoint.py runs/showdown_sp_100m_sN/ckpt_1000*.pt --episodes
   3000 --out results/ch5_100m/final_sN.json` with
   POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1. ~120 s each
   (ch5_g9_basis.sh is the pattern, incl. resume-safety).
2. **THE PRIMARY — off-FP@20 greedy, 3x3000, serial k=1** (~3.9 h at
   1.53-1.55 s/battle): adapt the R2 greedy-arm pattern
   (`scripts/ch5_r2_wave.sh` / `ch3_fp_h2h.py` — deterministic seat, FRESH
   username pair per arm, `--search-time-ms 20`, no co-scheduling; output
   t104/t112/t120.json into results/ch5_100m/, ch3_fp_h2h format). All four
   FP-runner incident fixes stay (CLAUDE.md landmine): kill search workers
   first, poisoned pairs re-run LAST on fresh pairs, no forfeit at clean
   boundaries, G2 = two tallies agreeing.
3. **S-SHAPE** (2.0 h): rungs nearest >= 5M..100M step 5M x 3 lanes,
   n=3000 vs-SH. Descriptive; "flat"/"plateau" BARRED; the anneal sentence
   is MANDATORY on every quote (pre-reg wording).
4. **S-ANNEAL** (1.0 h): the SYNC control's own 5M..50M rungs
   (runs/showdown_sp_batch50m_s{66,75,83}/ckpt_0*.pt), n=3000 — overlay.
5. **BC-clone h2h 500/lane** (rate unmeasured — measure at n=20 first).
   Must land before any README row.
6. **A-COLL, IFF the primary lands P1** (7.75 h): 6 arms off-FP@20 at the
   12M rungs — async fleet `runs/showdown_sp_batch50m_async_s*/ckpt_0120*
   .pt` vs sync fleet `runs/showdown_sp_batch50m_s*/ckpt_012000000.pt`,
   matched seeds, n=3000, serial. Write `results/ch5_100m/acoll.json` as
   `{"async_12m": <pooled>, "sync_12m": <pooled>}`.

## 3. GRADE AND RECORD

- `python scripts/ch5_100m_grade.py` (attest runs first and hard-stops on
  control drift; `--selftest` if in doubt). Cells P1..P6/K, SN/X
  composition, F1, A-COLL, sigma disclosure — all in the grader, all
  transcribed from the ratified header.
- **Every credit sentence carries: G9's signed delta +0.02322, the A-COLL
  number (at P1), N-ANNEAL as the named leading alternative, the FP@20
  budget + its two standing disclosures.** vs-SH/off-FP are NEVER ladder
  numbers; wall clocks are REALIZED dStep/dWall only (sps overstates ~57%
  on async — never mix estimators).
- Record: SESSION_LOGS entry + STATUS rewrite (same commit); **RESULTS.md
  gets the headline number AND discharges the owed N-TIMER line (it is
  pre-drafted in the pre-reg header — copy it beside the number)**; the
  README row only after the full anchor battery (steps 1/2/5 above).
  Rung retention: all ~200 rungs x 3 lanes + the sync control's 300 stay
  on disk until S-SHAPE, S-ANNEAL and D-A are recorded and committed (E2).
- D-A anneal check at grade time: exact form via history basis (pre-reg
  wording); expect a resume-free run's extract_history to just work — a
  resumed lane needs the merge protocol FIRST (landmine: hard-fail).

## 4. Standing maintainer items (unchanged, escalate not answer)

1. CLAUDE.md:71 MPS wording (proposal on the table). 2. Fix
   rl/selfplay/pool.py:88 at all (~2.5% prize)? 3. Stall-kill
   crash_forfeit read rule (R4S66 did NOT trigger it — seat_frozen 0).
4. NEW, with R4S66's number: the ladder-object question — **search@20
   HURTS the batch lane (0.38067 vs greedy 0.4740, ~10 se)**, so greedy
   batch-lane leads on today's evidence; the 100M final supersedes both
   as the candidate when it lands. JOURNEY step 2 (ladder) is next on
   every branch.

## 5. Context you'd otherwise have to dig for

- STAGE 2 acceptance: G9 PASS (+0.02322 signed), G8 CREDITED (901/908/901
  median-sps vs 444). Speedup realized: 1.53x fleet-width, 1.49x solo.
  All in SESSION_LOGS 2026-09-01 (two entries) + the acceptance header
  `configs/showdown_sp_batch50m_async.yaml`.
- The 2-Opus cycle artifacts live in `results/design_ch5_100m/` (gitignored,
  on disk): brief, mem_A/B, synthesis (6 adjudications), review_1/2.
- Suite: 648 passed / 17 skipped, bare `pytest tests/` (8 encoder-default
  tests fail BY DESIGN under forced V2/IDS env vars — R0-k names the bare
  invocation; only test_anneal_aux_group runs env-var'd, 9/1).
- Everything through the wave launch is pushed (origin/main = 2a21b9a +
  this handoff commit). Rules that cost hours: conda env
  `pokemon-showdown-rl` never base; distinct seeds everywhere; commit docs
  before launching; launch from a clean tree; `showdown/config/config.js`
  simulator: 4 (gitignored — re-set after any re-clone).

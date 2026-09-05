# docs/CLEANUP.md — the single cleanup ledger

Reconciled 2026-08-29 from the two prior lists (this file's 2026-08-25
audit + `REPO_CLEANUP.md`'s 2026-08-28 sweep, now deleted) during the
maintainer-ordered pre-R2 cleanup session. Execution detail and every
verification note from that session: SESSION_LOGS.md 2026-08-29. The five
maintainer rulings that session ran on (elo.py, the MinAtar/continuous
spine, killed-lever strip, the two disk deletions, §D restructure +
CLAUDE.md diet) are recorded there too.

**The fact that governs this file:** `results/`, `runs/` and `data/` are ALL
gitignored with zero tracked files, so a closed rung's grader script is the
*only committed provenance* for its number. **"Nothing greps it" is not
evidence a script is dead** — two deletion proposals were retracted on
exactly that (see do-not-relitigate below).

## Still open

- **B3 — the encode/mask/convert trio is duplicated 8× with divergent
  desync policy** (strict-raise in `rl/collect.py`, counted-recover in
  `showdown.py`/`ch3_fp_h2h.py`, default-move in `ladder.py` — the ladder
  half feeds the shared counter since 2026-08-25). Proposed: one
  `decide(battle, type_chart, act_fn, *, on_desync)` helper with the policy
  explicit. DEFERRED 2026-08-29: an 8-site refactor of live eval/collection
  paths directly before R2 is the wrong moment; revisit after R2 lands.
- **CHAPTER5.md migration — DISCHARGED 2026-09-04.** §3/§6/§7 survived
  verbatim into R2's pre-reg header (`configs/showdown_sp_batch50m.yaml`,
  ratified and run 2026-08-31); §1/§2/§4/§5/§8 were superseded already; §7
  ruling 4 superseded by the 100M header. File archived to
  `docs/archive/CHAPTER5.md` (body verbatim under a 13-line banner: `:N` cites
  resolve at N+13).
- **B9 — poke-env sporadically drops `battle.rating`** (race in the
  `|player|` parse; found live at n=5). ACCEPTED, not fixed: the readouts
  read the replays, which are authoritative, and the primary read is
  server-computed. Optionally patch `ladder.py` before R4 — never
  mid-measurement. Join replays to JSONL on the NUMERIC battle id (tags can
  carry a secret `-<token>` suffix that breaks `rsplit("-")`).
- **`runs/*/history.csv` compression (2.16 GB)** — decided AGAINST
  2026-08-29: the CSVs are only-copies read by exact name from five frozen
  grader/instrument scripts (incl. the pre-registered `d22_trajectories.py`);
  editing all of them to save 2 GB against 172 GB free is a bad trade.
  Revisit only if disk actually gets tight.
- **`SESSION_LOGS_PREDECESSOR.md` location** — stays at root for now (§D
  allowed archiving it); moving it means a link pass over the 24 repointed
  PLAN.md citations plus CLAUDE.md's read protocol. Do it only with a reason.

## Decisions and deviations recorded 2026-08-29 (executed cleanup)

- **Unlabelled predecessor figure — CLOSED 2026-08-29**: maintainer gave
  blanket approval ("update what you think is best"); a dated caveat now
  sits beside the embed in the otherwise-frozen file. (The PNG itself
  STAYS — see do-not-relitigate.)
- **Kept against the A4 strip list, on verification:** `TensorBoardLogger`
  (+ tensorboard pin) — "no test covers it" was FALSE, ~15 test files use it
  as the offline logger backend; `kernel_size` — PPO plumbs it and
  `test_ppo.py` pins its param counts as the pre-registered probe. Stripped
  as ruled: `fixed_mix`, `pfsp_power`, `dueling`; also `rl/selfplay/elo.py`
  (+test), the MinAtar dep/registration/test, the continuous-PPO track,
  `scripts/record.py` (+pillow pin).
- **selfplay.\* config keys are strict now** (B2): unknown keys fail in
  `selfplay_env_kwargs`; the removed levers double as the regression pin.
- **Six fp-tape symlink targets stay UNCOMPRESSED** (~600 MB):
  `data/fp_tapes_all/` symlinks into `fp_tranche*/`, and the pre-registered
  R0-5 gate (`tests/test_encoder_ids_tapes.py`) reads them — gzipping them
  silently skipped the gate. The rest of the tranches and all 13
  `ch4_r1_offsh` FP stdout tapes are gzipped in place, with gzip-aware
  readers (`ch4_r1_grade._fp_log`, `tape_to_dataset.iter_events`,
  `ch5_r1_grade.open_maybe_gz` already had it).
- **Vendored provenance modules** (B1): `gate_r012.py`, `rev1_check.py`,
  `analyze_oppact.py`, `z1_1.py` are byte-identical tracked copies in
  `scripts/`; the gitignored originals remain the executed artifacts.
- **d29_grade / d29r2_grade stay as deliberate near-duplicates** (B8), each
  header pointing at the other; a bug fix lands in BOTH.

## Do not re-litigate

- **`scripts/score_ladder.py`** — warning header added 2026-08-28; NOT
  deleted (deletion is a maintainer call). The dangerous invocation is
  `--opponents random` ALONE, which prints a full page of plausible numbers
  and exits 0.
- **The predecessor PNG** (embedded at `SESSION_LOGS_PREDECESSOR.md:1403`):
  its deletion was proposed and RETRACTED 2026-08-28 — it is a rendered
  embed in a frozen doc and `SESSION_LOGS.md:408` already RULED it stays.
- **Five "orphan" scripts, all with references** (retracted 2026-08-28):
  `ch3_r1_spike.py` (backs live config constants), `d22_trajectories.py`
  (only implementation of a pre-registered statistic),
  `probe_type_multiplier.py` (cited by its claimed successor),
  `make_bc_dataset.py`, `p3_team_luck.py` (instruments behind a live anchor
  and a banked decomposition).
- `configs/eval/ladder_r1.yaml` is genuinely result-blind — leave it (the
  ladder_r3.yaml:967-969 corrected-bands-beside-superseded pattern is the
  model for such fixes). The 0.0717→0.1007 r9 corrections are in place. All
  four `ch3_r4_fp_runner.sh` landmine fixes are in place.
  `ladder_supervise.sh` + `ladder_watchdog.sh` + `ch5_watchdog.sh` are three
  distinct live tools. `configs/showdown_sp_actpred12m.yaml.c4prereg` is a
  deliberate unlaunchable pre-reg record, invisible to `*.yaml` globs.
- **`play_vs_agent.py` stays** — flagged dead by the 2026-08-25 audit, then
  immediately became the way to play the ladder policy by hand (`--arm`).
- The 2026-08-25 same-day fixes and the 2026-08-28/29 executed items are
  recorded in SESSION_LOGS (2026-08-25, -28, -29 entries); do not re-audit
  them from scratch — spot-check against those entries instead.

## 2026-09-01 read-only audit (backlog pointer)

Source: `~/Downloads/20260826_114242.md` (produced env-less — tree reads
only, never test results; counts at d82f7fe). **A1 EXECUTED 2026-09-01,
maintainer-ruled**: the five `results/` design docs cited by tracked code
are tracked in place via docs/prior_work-style whitelist. **SHELVED until the
100M readout is recorded:** A2 (encoder env-var default flip → assert
`OBS_DIM==828`/fingerprint instead; pure default flip only), A3
(`normalize.py` spine residue + `_scalar_loop` — "ask, not delete"), A4
(`update()`'s variadic tuple; lands with A3), A5 (eight dangling
`REPO_CLEANUP.md` citations + `scripts/README.md` stale headline). Its
do-not-relitigate finds (no scripts/ helper dedupe, no scripts/ subdirs, no
config-header prose dedupe, B3 deferral re-confirmed) match this file.

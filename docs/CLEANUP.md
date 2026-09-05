# docs/CLEANUP.md — the single cleanup ledger

Reconciled 2026-08-29 from the two prior lists (this file's 2026-08-25
audit + `REPO_CLEANUP.md`'s 2026-08-28 sweep, now deleted) during the
maintainer-ordered pre-R2 cleanup session. Execution detail and every
verification note from that session: SESSION_LOGS.md 2026-08-29. The five
maintainer rulings that session ran on (elo.py, the MinAtar/continuous
spine, killed-lever strip, the two disk deletions, §D restructure +
CLAUDE.md diet) are recorded there too.

**Status pass 2026-09-04** (the day this file moved to `docs/`): every open
item below was re-checked against the tree. Nothing new was executed — each
entry now carries the evidence that it is undone and WHY. **Cite entries BY
LABEL (B3, B9, A2…), never by line** — this pass shifted every line, so
`configs/eval/ladder_r4.yaml:483`'s `docs/CLEANUP.md:29-34` pointer (already
drifted by 3 at ratification) resolves by its **B9** label instead.

**The fact that governs this file:** `results/`, `runs/` and `data/` are ALL
gitignored, so a closed rung's grader script is the *only committed
provenance* for its number. (`runs/` and `data/` still hold zero tracked
files; A1 whitelisted 11 design DOCS under `results/` on 2026-09-01 — no
data, so the fact is unchanged in substance.) **"Nothing greps it" is not
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
  **NOT DONE — the R2 condition fired, and it is re-blocked for the same
  reason (2026-09-04).** R2 ran 2026-08-31 and the 100M grading landed
  2026-09-04, so the deferral has expired; but `scripts/ladder.py:531` is one
  of the sites and LADDER R4 is MID-MEASUREMENT, which is the same wrong
  moment restated. Verified unimplemented: `git grep 'def decide' -- rl
  scripts` returns nothing, and the trio still lives in `rl/collect.py`,
  `rl/envs/showdown.py`, `rl/envs/showdown_async.py`, `scripts/ladder.py`,
  `scripts/ch3_fp_h2h.py`, `scripts/showdown_throughput.py`,
  `scripts/tape_to_dataset.py`. Next window: after the R4 readout.
- **B9 — poke-env sporadically drops `battle.rating`** (race in the
  `|player|` parse; found live at n=5). ACCEPTED, not fixed: the readouts
  read the replays, which are authoritative, and the primary read is
  server-computed. Join replays to JSONL on the NUMERIC battle id (tags can
  carry a secret `-<token>` suffix that breaks `rsplit("-")`).
  **"Optionally patch `ladder.py` before R4" is SPENT — RULED AGAINST
  2026-09-04** (`configs/eval/ladder_r4.yaml` ratified_decisions **M9**, from
  review_2 F12): carry R3's rating-loss disclosure verbatim, read
  trajectories from replays, no live-path patch days before a rated run. R4
  launched unpatched. Next decision point: before R5.
- **`runs/*/history.csv` compression (2.16 GB)** — decided AGAINST
  2026-08-29: the CSVs are only-copies read by exact name from five frozen
  grader/instrument scripts (incl. the pre-registered `d22_trajectories.py`);
  editing all of them to save 2 GB against 172 GB free is a bad trade.
  Revisit only if disk actually gets tight. **Re-checked 2026-09-04: 156 GB
  free, `runs/` is 26 GB across 109 `history.csv`. Not tight — decision
  stands.**
- **`SESSION_LOGS_PREDECESSOR.md` location** — stays at root for now (§D
  allowed archiving it); moving it means a link pass over the 24 repointed
  PLAN.md citations plus CLAUDE.md's read protocol. Do it only with a reason.
  **Re-checked 2026-09-04: still at root, and the link cost is smaller than
  written** — the file now carries 7 `PLAN.md` mentions, all pointing at the
  PREDECESSOR repo's plan, which does not exist here
  (`.claude/agents/doc-archaeologist.md:12`); they already dangle, and a move
  neither breaks nor fixes them. Still no reason, so still no move.

## Closed since the 2026-08-29 reconcile

- **CHAPTER5.md migration — DISCHARGED 2026-09-04.** §3/§6/§7 survived
  verbatim into R2's pre-reg header (`configs/showdown_sp_batch50m.yaml`,
  ratified and run 2026-08-31); §1/§2/§4/§5/§8 were superseded already; §7
  ruling 4 superseded by the 100M header. File archived to
  `docs/archive/CHAPTER5.md` (body verbatim under a 13-line banner: `:N` cites
  resolve at N+13).

## Decisions and deviations recorded 2026-08-29 (executed cleanup)

Spot-checked against the tree 2026-09-04, all still true: `rl/selfplay/elo.py`
and `scripts/record.py` are gone; `fixed_mix` / `pfsp_power` / `dueling`
survive only as removal comments (`rl/envs/make.py:109`,
`rl/selfplay/pool.py:136`, `rl/networks/conv.py:10`); `TensorBoardLogger` and
`kernel_size` are still carried, as ruled.

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

Re-verified 2026-09-04: every file named below still exists, and
`scripts/score_ladder.py`'s FALSE FRIEND header is in place.

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

## 2026-09-01 read-only audit — SHELF LIFTED 2026-09-04, all four UNDONE

Source: `~/Downloads/20260826_114242.md` (produced env-less — tree reads
only, never test results; counts at d82f7fe). **A1 EXECUTED 2026-09-01,
maintainer-ruled**: the five `results/` design docs cited by tracked code are
tracked in place via a docs/prior_work-style whitelist (11 tracked files
under `results/` today, after the R4 design set landed).

A2-A5 were **SHELVED until the 100M readout is recorded**. That readout
landed 2026-09-04 (RESULTS.md §18), so **the shelf condition has FIRED**.
Re-checked against the tree the same day: none of the four is done, and each
is blocked on something nameable — a ruling (A2), an unasked question (A3),
its sibling (A4), or the live R4 run (A5).

- **A2 — encoder env-var default flip → assert `OBS_DIM == 828`/fingerprint
  instead (pure default flip only). NOT DONE, and now entangled.** The
  2026-09-02 audit picked the same risk up as F-07 and proposed the larger
  `encoder:` config block; that proposal is written but **UNRULED**
  (`docs/proposals/F07_encoder_config_block.md`), and the ordering — block
  before A2, A2 before block, or A2 subsumed by the block's schema default —
  is an open maintainer question in `docs/archive/AUDIT_BRANCH_LOG.md`
  §Open questions. **Do not execute A2 until that is ruled.** It also touches
  the encoder, so the `OBS_DIM` landmine binds: evaluate outstanding finals
  first, and R4's `ckpt_100000008.pt` is frozen until its readout.
- **A3 — `normalize.py` spine residue + `_scalar_loop` ("ask, not delete").
  NOT DONE; the ask has not been put.** `_scalar_loop` is live at
  `rl/train.py:868`, reached from `:616` for any run that is neither async
  nor vectorized; `rl/envs/normalize.py` is imported by `rl/agents/ppo.py`,
  `rl/train.py`, `tests/test_normalize.py` and eight `scripts/` (incl.
  `eval_checkpoint.py`). Neither is orphaned, so this is a scope question for
  the maintainer, not a sweep — which is what "ask, not delete" meant.
- **A4 — `update()`'s variadic positional tuple (lands with A3). NOT DONE.**
  `rl/agents/ppo.py:923-928` still unpacks 8 positional elements plus up to 3
  optional ones behind a hand-written arity check. The audit's fix (a
  `Transition` dataclass, `docs/archive/AUDIT_ACTION_PLAN.md:254`) would touch
  ~10 call sites across `rl/train.py` and the tests. Blocked on A3 by its own
  "lands with A3" clause.
- **A5 — dangling `REPO_CLEANUP.md` citations + `scripts/README.md` stale
  headline. NOT DONE; the cheapest of the four, and the only one whose
  blocker is timing rather than a ruling.** Nine live citations to the
  deleted file remain (eight at audit time; `mem_B.md` joined when A1 tracked
  it): `docs/landmines.md:7`, `scripts/README.md:105`,
  `scripts/ch5_watchdog.sh:22`, `scripts/eval_checkpoint.py:5`,
  `scripts/ladder_classify.py:85`, `scripts/ladder_move_audit.py:28`,
  `scripts/ladder_readout.py:103`, `scripts/ladder_supervise.sh:4`,
  `results/design_ladder_r4/mem_B.md:211`. Each cites a NUMBERED
  REPO_CLEANUP item, so repointing means naming the item, not swapping the
  filename — those items now live in SESSION_LOGS.md 2026-08-29.
  `scripts/README.md` is stale three ways: its governing fact still asserts
  `git ls-files results | wc -l` → 0 (now 11, post-A1); its count says 94
  `.py`/`.sh` files (now 115); and its `ladder_supervise.sh` paragraph
  (`:100-106`) describes the hardcoded-`ladder_r3.yaml` bug as LIVE when the
  very item it cites fixed it 2026-08-29 (`scripts/ladder_supervise.sh:4` —
  the pre-reg is a required argument). **Four of those files are R4's live
  tooling: do this pass after the R4 readout, not during it.**

Its do-not-relitigate finds (no scripts/ helper dedupe, no scripts/ subdirs,
no config-header prose dedupe, B3 deferral re-confirmed) match this file.

## When this file may be archived

**Not yet (asked and answered 2026-09-04).** It is the only home for two
things that are still load-bearing: the eight open entries above (four under
"Still open", A2-A5 here), each with a named blocker, and
the do-not-relitigate record that stops the next sweep from re-proposing the
two deletions already retracted. Archive it when "Still open" and the A2-A5
block are both empty — and fold the do-not-relitigate record into
`docs/landmines.md` at that point rather than letting it go quiet under
`docs/archive/`, which nothing reads unless the maintainer names the file.

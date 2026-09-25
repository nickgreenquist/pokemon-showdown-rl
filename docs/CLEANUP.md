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

- **L2 — THE LADDER READOUT'S "STATUS OF THE PRIMARY READ" BLOCK IS A LIVE PULL
  AND DRIFTS ON EVERY REGENERATION** (opened 2026-09-16, R5 audit).
  `scripts/ladder_readout.py` calls `ladder_snapshot()` at readout time, so the
  admission cutoff, `listed`, and the profile it prints are "as of whenever you
  ran it", inside a file headed "final readout". Measured: R4's committed file
  says cutoff **1358.999** while its own `R4G.report.json` `ladder_after` says
  **1359.680**, and R5 re-renders today at **1354.395** against the **1354.173**
  it stopped at. **Mitigated, not fixed:** the at-stop value from `--report` now
  prints beside the live one and is labelled as the one every downstream quote
  uses, and a failed network pull falls back to the report instead of killing
  the render. **The ruling owed is whether the report should simply BE the
  source** — which would change what a regenerated R1/R3/R4 readout says, and
  the repo's published R4 cutoff (1358.999, quoted in README and the R5
  pre-reg header) is one of the numbers that would move. Escalate before
  changing; a published number is a maintainer call.

- **L3 — `scripts/plasticity_probe.py` CAN ONLY SEE ONE ARCHITECTURE** (opened
  2026-09-16). It asserts `REF_TRUNK_KWARGS` with `value_sizes [384, 384]` and
  compares parameter sets of ONE architecture against fresh inits of that same
  architecture, so the 1024-wide critic finals cannot enter it without a second
  arch family (its own fresh inits and `ORDER_SEEDS`). This is the instrument
  that would separate "the parameters can still be optimised" (Lyle Def-1
  plasticity) from "the representation is a sparse-reward artefact" — i.e. it
  is the follow-up the mechanism read (RESULTS §21) leaves open, since that read
  shows the wide critic's capacity is USED but buys no explained variance.
  Not blocking anything today; named so the next person does not rediscover the
  assert mid-read.

- **L4 — EVERY DEPTH-2 ARM BEFORE 2026-09-18 CARRIES AN UNEXPANDED-LEAF
  ARTIFACT** (opened 2026-09-18, found while building IDEAS 2.10's fix).
  `matrix.py::_look_further` used to RE-SCORE a leaf it could not expand: the
  state was re-embedded at `turn + 1 + plies` and passed to the critic again, so
  merely TURNING DEPTH ON moved the value of leaves the lookahead never looked
  past — by whatever the encoder does with a shifted turn count. Fixed (the leaf
  keeps the value it has; `depth2/leaves_unexpanded` counts them), and the fix
  is NOT retro-fitted to the banked arms. **Consequence for reading the record:**
  D2M / D2N / §22's and §24's depth-2 numbers include it. It is small in
  expectation — the same state, one turn index apart — but it is not zero, and it
  is one more reason a depth number from the matrix vehicle must be re-measured
  rather than re-quoted. Nothing to do; recorded so it is not rediscovered.

- **L5 — A RUNNING BLOCK IMPORTS THE WORKING TREE, AND NOTHING ENFORCES THAT**
  (opened 2026-09-18). The tree block launched at 10:45Z and this session then
  edited `agent.py`, `matrix.py`, `ensemble_search.py` and `ch3_fp_h2h.py` —
  files EVERY arm imports, with TV finished and TG/TQ/TGR not yet launched. Each
  arm is a fresh process, so the later arms ran newer code than the earlier one.
  **This time it was provably harmless** (`tests/test_tree_decision_golden.py`
  now pins the decision, and the pre-edit tree out of `git archive` gave
  bit-identical actions, stats and counters on all three decide rules; only
  wall-clock differed, and the arms are iteration-bounded). The queue script
  freezes ITSELF (`mktemp` + re-exec) precisely because of this hazard and does
  nothing about the Python. **THE STAMP ALREADY EXISTED, NOTHING READ IT, AND IT
  MEANT THE WRONG THING:** every arm's JSON has carried `launch_git_sha` since
  CH4 R1's G8 provenance block — but it was read AFTER the battles, so it
  recorded the tree state when the arm FINISHED, under a name that says
  otherwise, while SESSION_LOGS records the opposite belief in prose ("the seat
  stamps `launch_git_sha` per arm at ITS start"). Caught 2026-09-18 when TV —
  launched 10:45Z — came back stamped with a commit made at 11:40Z. **Fixed:**
  the sha is read before the first battle and `finish_git_sha` is kept beside
  it, so an arm that spans a commit MID-ARM is visible too. **Arms written
  before that fix carry a finish-time value under the launch name**, and both
  readouts label them rather than comparing them against a real launch sha.
  **A provenance field nothing reads is a field nobody notices is wrong.** **Half-closed 2026-09-18:** both live
  readouts now print each arm's sha and say plainly when a block spans more than
  one, so a reader is told rather than having to think of the question.
  **Still open:** whether a spanning block should be REFUSED rather than
  disclosed, and the heavier option of running a block out of a `git archive`
  snapshot. Refusal is the maintainer's call — it would have voided today's tree
  block, which was proved harmless.

- **L6 — A MATCHED BLOCK SHOULD RUN ITS CONTROL FIRST** (opened 2026-09-18).
  Matching on the realized override rate is the standing rule (§22), and
  2026-09-18 measured that **the realized rate itself drifts across sessions at a
  fixed delta**: the same configuration read **0.1933** on 09-17 (CN1) and
  **0.1703** on 09-18 (D1O), 0.023 apart, the same order as the win-rate offset.
  `backup_gate_r5` therefore matched its treatment to a BANKED target, because
  the control had not run yet, and landed 0.027 from the control in front of it —
  inside the ±0.03 gate and closer to the edge than intended. **The fix costs an
  ordering and nothing else: put the control at the head of phase R and pin the
  treatment to ITS realized rate.** Not applied to the running block, because
  re-pinning after a win rate is visible turns a selection rule into a choice.
  Fold this into the next matched block's queue script.
  **AND SWEEP EVERY ARM YOU INTEND TO MATCH** (added the same evening, from the
  same block): `backup_gate_r5` swept B2R's delta but HARDCODED B2O's at 0.12,
  the value §22's D2N used in a different session. B2O realized **0.1322** here
  against D1O's 0.1703 and B2R's ~0.197, so **the comparison the config declares
  as the fix (B2R − B2O) is the mismatched one** and the one it calls secondary
  (B2R − D1O, |d| 0.027) is the matched one. Not re-pinned — B2O's win rate was
  visible by then, and a selection rule re-run after an outcome stops being one.
  Disclosed in the config, in the readout, and here. The rule is one line: **a
  matched block sweeps every arm it matches, against an in-session control.**
- **L10 — A HARNESS STAMPED ITS "LAUNCH" SHA AT WRITE TIME** (opened 2026-09-24).
  `scripts/g1_engine_mirror.py` /2 ran `git rev-parse HEAD` after its arms
  finished and saved it as `launch_git_sha`; G1b ran 4.5 h while 31 commits
  landed on its branch, so its JSON names `068ccaf` for a program launched at
  `e486482`. The G1 readout now derives the launch commit from the guard's start
  line and checks the lazily imported modules byte-identical there; `2d9b180`
  fixed the harness, and the same shape in the new `scripts/r7_mechanism_reads.py`
  before it ever ran. L5's companion: a running block imports the tree at launch,
  so the sha that describes it must be read at launch. **AUDITED AND FIXED
  2026-09-25** (merged in `9d6a1f8`): a read-only pass over every file under
  `scripts/` and `rl/` that stamps a sha or a dirty flag (47 files match
  `launch_git_sha|git_sha|rev-parse`) found two LIVE write-time stamps, both now
  read at launch with a behavioural test -- `scripts/ch3_fp_h2h.py`'s `rl_git_sha`
  / `rl_git_dirty` (G2's "which rl" fields, read inside `run()` after the battles;
  `3050292`) and `scripts/search_r1e_gate.py`'s `provenance()` (after legs A/B/C
  and the controls; the write-time value kept as `written_git_sha`; `c7efc87`).
  Two gaps of another shape, closed for what R7 runs next: `scripts/eval_checkpoint.py`
  stamped NO sha (the LR smokes' vs-SH gate evals run through it; it stamps
  `launch_git_sha` / `launch_git_dirty` / `rl_package` now, `e384e3d`), and
  `scripts/r7_smoke_check.py`'s S_RESUME never compared a resume's sha with the
  launch's (`same_program_as_launch`, `3a58e79`). Every other live stamp is read
  at launch (rl/train.py, fresh and per resume; rollout_q / _belief / _evaluator;
  r7_b0_bench; r7_mechanism_reads; g1_engine_mirror) or is a readout's own HEAD.
  **LEFT, disclosed:** the spent ch3_r*/ch5 graders and probes stamp inline at
  write time; `scripts/ch3_eval.py` and `scripts/action_gap.py` stamp nothing;
  `scripts/rollout_q.py` has no dirty flag; rl/train.py's resume stamp omits
  `cwd=` (harmless: the watchdog cds to the repo). L5's shape, not L10's: a child
  process imports the tree AFTER the stamp (train.py's spawn `ProcCollector`,
  r7_b0_bench's per-width children, ch3_fp_h2h's lazy `rl.search`) -- the
  stagger-window rule covers it.

- **L1 — THE LADDER'S OPPONENT POOL IS SMALL AND ONE SESSION SAMPLES ONE SLICE
  OF IT** (opened 2026-09-16, from the maintainer's observation mid-R5). R5 at
  n=156 had played **78 distinct opponents, with five of them supplying 62 games
  (40%)** and 64% of all battles against someone already faced. Consequences, both
  real: 200 battles buy fewer than 200 independent draws (Glicko treats them as
  independent), and a repeat opponent can adapt to the bot across games. The
  adaptation is NOT visible yet in R5 — repeat opponents' first halves vs second
  halves 0.625 → 0.657 (+0.03, 0.27 se), first meetings vs rematches 0.603 →
  0.684 (+0.08, 1.06 se), both in OUR favour and neither significant — so this is
  a design item, not a finding. **Proposal for the next ladder pre-reg (R6):
  replace "ONE CONTINUOUS RUN" with a pre-registered SPLIT SCHEDULE** — e.g. four
  sessions of ~50 at different hours and on different days — with its own stopping
  rule (rd grows between sessions; the current rule reads rd at the stop of one
  continuous run), an explicit calendar-drift disclosure, and the repeat-opponent
  census above computed in the readout. **Not applied to R5**: changing the
  schedule mid-run is an unregistered deviation, and R5 was 40 games from its
  floor when this came up. **RULED 2026-09-20: R6 ladders under the split schedule**
  (four sessions, different hours and days, its own stopping rule) — the R6 pre-reg
  carries it.

- **E1 — NO SINGLE ENV RUNS THE TEST SUITE** (opened 2026-09-10). The port env
  `pkmn-engine-port` has the `pkmn_gen1` extension and now the analysis deps;
  `pokemon-showdown-rl` has the analysis deps but NOT the extension, so its run
  skips the seven `importorskip`-guarded engine modules. Both are green on what
  they can see, neither covers everything. Needs a ruling: install the extension
  into `pokemon-showdown-rl`, or make the port env the suite env. Blocked on the
  maintainer because CLAUDE.md rule 1 forbids installing into that env
  unilaterally. (`pandas` was the same class of bug and is fixed — it was
  undeclared and only ever arrived as a transitive dep, failing four gen-4 gate
  tests in any env built from `pyproject.toml` alone. `scipy` and `seaborn`
  were reported as the same problem and are NOT: scipy appears once, in a
  comment saying it is deliberately not used, and seaborn is absent entirely.)

- **E2 — the scorer `ctx` factorization is blocked by a bit-exact pin**
  (opened 2026-09-10). `entity_deepsets.py` scores 10 actions over
  `[ctx || entity_i]` where `ctx` is identical in all ten slots, so the
  384-wide half runs ten times per row instead of once. Factoring it is
  ~26% of the epoch loop and ~1.97x on that layer's forward, verified
  equivalent to 2.98e-07 (`scripts/engine_scorer_equiv.py`,
  `tests/test_entity_scorer_factorization.py`, both retained). But
  `tests/test_entity_trunk_gen4.py::_GEN1_PIN` asserts `lo == lo_w` on the
  actor's summed logits — EXACT equality, with the comment "the forwards are
  exact". 3e-07 is not bit-identical. Regenerating a deliberate golden to pass
  one's own change is backwards, so this needs a maintainer ruling on whether
  the pin may be re-baselined. APPLIED AND REVERTED 2026-09-10.
  **CLOSED 2026-09-24 — RULED YES (the maintainer, R-E2) and LANDED** on
  `r7-native-search` at `38f7736` with `_GEN1_PIN` re-baselined IN THE SAME
  COMMIT (only the actor's summed logits moved: 0.13518786523491144 →
  0.13518785871565342 at priv 0, 0.18378696037689224 → 0.18378695903811604 at
  priv 408; the identity test is the bridge). The sweep for other bitwise
  goldens found none that move (every golden-bearing file with the encoder
  flags set: 109 passed, 0 skipped; both envs' full suites fail only where the
  unmodified branch fails identically, plus two load flakes that pass on
  rerun). Reaches main at the Friday merge, so the R7 fleet runs it from its
  first step in both arms.

- **E3 — the act path traces bit-identically and is not yet adopted**
  (opened 2026-09-10). `torch.jit.trace` on the actor gives 1.60x at B=1 and
  1.31x at B=4 — the range the act path actually runs at — and is BIT-IDENTICAL
  at every batch size tested, so unlike E2 it needs no pre-reg. ~1.09x on the
  full loop, free. Use `trace`, NOT `trace`+`freeze`: they are within noise, so
  freeze buys nothing while being documented to inline parameters as constants.
  NOT LANDED, deliberately: it changes the learner's collection path, tonight's
  A/B numbers were measured against the untraced path, and a traced module that
  ever stopped tracking a weight update would be silently wrong — the exact
  failure class the recorded-`old_logp` design exists to prevent. Wants a guard
  (periodic eager-vs-traced assertion) or a maintainer ruling before it lands.

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

**Label warning:** the `A<n>` below are the **2026-08-25** audit's numbering
and do NOT mean the 2026-09-01 `A1-A5` in the last section. Here A4 is the
strip list and A5 was the disk pass — which is why commit 0634937 ("Disk
hygiene (CLEANUP A5)") names something entirely different from today's A5.

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
- **Our PPO vs a library (Stable-Baselines3) — AUDITED 2026-09-08, verdict
  NEITHER.** Do not re-propose a migration:
  `docs/research_reports/PPO_VS_SB3_UPDATE_AUDIT.md`, indexed in IDEAS §3. The
  one update-path optimization we lack (`target_kl`) is off by default in SB3
  too and never fires at our measured KL (p50 0.00086 / max 0.00228 vs a
  1.5·target_kl trigger); the local SB3 clone is Wang's v2.0.0 fork whose entire
  diff from the tag is timers and logging with `common/buffers.py` untouched;
  `sb3-contrib` (MaskablePPO) is not cloned, so SB3 cannot even satisfy the
  action-masking contract. Migration would re-plumb masking, the both-seat
  harvest, per-episode GAE, the pool, the resume toolchain and every locked
  metric name. **Only the migration is closed** — the PORTABLE wins are live as
  IDEAS **2.9** (4.3–6.0% of `update_sec`, bit-identical) and the §5 shared-trunk
  pre-reg (19.5% of the epoch loop); both are worth most after JOURNEY 7.5.
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

## L7 — a typed dial list dropped two dials (2026-09-19, FIXED)

`scripts/ch3_eval.py` forwarded a HARDCODED list of `SearchAgent` dials.
`disagree` and `calibration`, added to the object afterwards, would have been
accepted in a pre-reg, silently dropped, and the arm run as an unmodified
CONTROL while its readout claimed the dial. **Fixed:** the set is derived from
`inspect.signature`, and an unrecognised arm key is a hard failure
(`tests/test_dial_forwarding.py`; verified against all banked pre-regs).

**AUDIT OWED, not yet done:** no banked arm is known to have declared either
dial — `disagree` and `calibration` were only ever run through
`scripts/ch3_fp_h2h.py`, which forwards them correctly. **But that was not
verified arm-by-arm**, only reasoned from which harness each block used. Before
citing any `kind: search` arm from `configs/eval/` as a dial test, confirm from
its config that the dial it claims is one the harness of that era forwarded.

## L8 — the isotonic thinner ramped through every step (2026-09-19, FIXED)

`rl/common/value_calibration.py` kept only the FIRST x of each PAVA level set,
so `np.interp` drew a RAMP across ground the fit holds FLAT and then STEPS.
Measured on the 22,358-pair fit: **27% of the fitted gain thrown away**
(in-sample EV +0.0213 full vs +0.0155 as deployed), max |deployed − true| 0.158.
Its docstring claimed the estimator was shared with
`scripts/critic_calibration.py` "so the number reported there and the transform
applied here cannot drift apart". They had.

**CONSEQUENCE FOR BANKED NUMBERS:** every 2.13 figure measured before this date
was measured on the DEPLOYED (ramped) object, including
`results/outcome_variance/calib_action_diff.json`'s **5.41% action-change rate**
and the **3.5% row-pair flip rate** quoted in RESULTS §27.1 and
`tests/test_value_calibration.py`. Those are LOWER BOUNDS on the fixed object.
**Re-run `scripts/calibration_action_diff.py` before any 2.13 arm.**

## L9 — `scripts/action_gap.py` is INVALID for its headline claim (2026-09-19, FIXED the same evening)

**FIXED 2026-09-19 (evening).** `top2_live` computes (a1, a2) ONCE per position from the
LIVE observation and action mask — the tensors the committee acts on — and holds the pair
fixed across determinizations, so no shadow battle and no privileged view enter the
ranking; every row records `top1_is_played` (a1 vs the action the committee actually
played) and the summary prints it as a self-check that must sit at ~100%.
`tests/test_action_gap_top2.py` pins the contract (3 tests). Still UNRUN at the time of the
fix; the first run is queued behind the wavg_r5 read (`scripts/exit_gate_queue.sh`).

**RUN 2026-09-20 (22:58–23:03Z, under the queue at `39da8f8`), VALID — `top1_is_played_frac`
1.000 over 134 positions.** Naive per-swap ceiling **0.0317** [0.0220, 0.0426]; noise alone
prints 0.0290; deconvolved 0.0241 — AT the credit floor, **neither a mechanism kill nor a
licence** (RESULTS §33; `readouts/ACTION_GAP_R5_READOUT.md`; `scripts/action_gap_readout.py`
for the companion reads). The queue's existence-based skip guard had first skipped the run on
the pre-fix artifacts (now in `results/outcome_variance/invalid_pre_L9/`); since `39da8f8` it
checks the fixed version's marker. **This item is CLOSED.** The original entry follows.


The script's docstring calls it *"a ceiling, not a null, and the first thing in
this project licensed to close the axis"* — the search axis. **It is not valid
for that, and both defects bias it toward the conclusion it would license.**

1. **The top-2 is re-derived per determinization** (`top2(shadow_battle(st, turn))`
   inside `for st in states`). The real policy commits to one argmax at the ROOT;
   search swaps THAT. Per-determinization pairs measure a smaller quantity.
2. **The policy is read from a privileged observation** — `shadow_battle(...)` is
   called with `view=None`, so the opponent's full determinized team is encoded
   where the live agent sees zero padding.

`cda517d` fixed a third defect (noise diagnostics measuring ~zero by
construction) and did not touch these. **Fix:** compute `(a1, a2)` once from the
root's live observation and hold it fixed; pass `view=public_view(root_battle)`.

**UNRUN and uncited** — no number from it appears in RESULTS, STATUS or any
readout, which is the only reason this is a cleanup item rather than a
retraction. **Do not run it and quote the number until both are fixed.**

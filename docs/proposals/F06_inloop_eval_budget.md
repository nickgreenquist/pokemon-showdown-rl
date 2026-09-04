# F-06 proposal — the in-loop eval budget

**DRAFT, UNRULED.** Written 2026-09-02 on `audit/DOCS` @ 5d3c6b7 (main @
60c1225, the tree the 100M fleet runs on). Nothing in this file is landed
behaviour; nothing here touches the running fleet or its ratified pre-reg
(`configs/showdown_sp_100m.yaml`, FREEZE RULE `:288-290`). Source finding:
`docs/archive/AUDIT_ACTION_PLAN.md` §3 F-06 (with F-05) and §5 item 3.

Tags used below: **RULED** = a maintainer ruling or ratified pre-reg text;
**MEASURED** = a number read from the tree/logs, with its source;
**PROPOSED** = this draft's suggestion, which needs a ruling.

## 1. What the in-loop eval is today (code, not opinion)

1. Async loop (the path every 100M lane runs): `rl/train.py:635-650`. On
   every `cfg.eval_every` crossing (`next_eval`, `:534`) the loop `pause()`s
   the collector (`:637`), runs `evaluate(agent, eval_env, cfg.eval_episodes,
   win_rate=cfg.eval_win_rate)` (`:639-641`) — deterministic policy vs the
   `selfplay.eval_opponent` anchor (`heuristics`,
   `configs/showdown_sp_100m.yaml:550`) on a dedicated env built once at
   `:338` through `make_eval_env` — logs `time/eval_sec` (`:642`), writes
   `best_checkpoint.pt` when `eval/return_mean` improves (`:646-648`), calls
   `save_latest()` (`:649`; the resume pair `checkpoint.pt` + `pool.pt`,
   `:552-558`), then `resume()`s (`:650`). The sync path runs the same block
   without pause/resume (no async collector to pause): `:914-937` (`if step
   >= next_eval:` at `:914`), with the latest-checkpoint save
   (`checkpoint.pt` + `pool.pt`) written inline at `:928-937`; the
   best-checkpoint save is `:927`. Those two writes stay distinguished
   throughout this file — `:927` is the noise-max artifact §3 item 2 argues
   against, `:928-937` is the resume pair F-05 moves onto its own cadence.
2. Config: `eval_every: 250000`, `eval_episodes: 100`
   (`configs/showdown_sp_100m.yaml:535-536`), `eval_win_rate: true` (`:542`).
   1e8 / 250k = 400 evals per lane.
3. Metric names are locked (CLAUDE.md): `eval/return_mean`,
   `eval/return_std`, `eval/win_rate`, `time/eval_sec`. `eval/win_rate` is
   the env-supplied outcome (`rl/common/evaluation.py:141-150`), never the
   return sign (`docs/landmines.md:46-53`).

## 2. What it costs (MEASURED where a source exists; the range is wide on purpose)

1. Per eval — two reads, they disagree, and NEITHER comes from the 100M lanes:
   - the pre-reg's own budget line, "400 evals ~ 0.58 h/lane"
     (`showdown_sp_100m.yaml:535`) = ~5.2 s/eval = 1.2% of the realized
     48.4 h/lane (`:513`);
   - the acceptance fleet's fleet-max `time/eval_sec` 26.18 s (s66;
     `showdown_sp_100m.yaml:110`) = 6.0% if every eval ran at the max.
   Collection between evals at the realized 574 steps/s is 250k / 574 =
   ~435 s, so the pause is 1-6% of each cycle: 0.6-2.9 h of a 48 h lane.
   The audit plan quotes the prize as **1-6%** (plan §3 F-06, re-verified
   note); the 100M lanes' own `time/eval_sec` was NOT read here, for two
   reasons and NEITHER is a fleet rule: the lane logs carry no eval timings,
   and `extract_history.py` is barred to THIS workstream by the
   audit-worktree protocol ("no reads of `runs/` or `logs/`, no
   `extract_history.py`", `docs/archive/AUDIT_BRANCH_LOG.md:21-23`; plan header). The
   fleet's own monitoring rules say the opposite — HANDOFF §1 prescribes
   periodic health reads "all from `scripts/extract_history.py <run_dir>` →
   history.csv, which works on a live run" (`HANDOFF.md:53-55`). See §8 for
   the read that settles it.
2. Timer exposure: the eval+checkpoint block is the longest collector
   pause; during it K=8 battles sit mid-turn against the 300 s/turn
   challenge budget (~11x margin at 26 s; `showdown_sp_100m.yaml:109-112`;
   N-TIMER is disclosed-not-celled, ruling E4). The ladder is tighter
   (150 s/turn, CLAUDE.md). This is a per-pause LENGTH exposure; the eval
   COUNT only multiplies the wall-clock cost.
3. Resume-loss window: because `save_latest()` rides the eval block
   (`:649`), `eval_every` IS the resume granularity — a kill costs up to
   ~250k steps (~7 min at 574 steps/s; R2 measured 170,680-190,776 steps
   lost per resume, `docs/landmines.md:256-266`).

## 3. What it buys (every consumer, read in the tree)

1. `eval/win_rate` at n=100 (se ~0.040 at p~0.8; the pre-reg's own figure,
   `:301`). RULED (pre-reg peeking section `:292-305`; HANDOFF §1):
   "logged, visible, and NOT ACTIONABLE"; "no mid-run curve appears in the
   readout except through S-SHAPE at n=3000". Its only gate use is R0-6,
   "eval/win_rate present, in (0,1)" (`:398-399`) — existence plus a sanity
   band, read once, early. The grader `scripts/ch5_100m_grade.py` reads
   `eval/win_rate` ONLY from n=3000 `eval_checkpoint.py` finals JSON —
   `results/ch5_r2/final_s*.json` (the banked R2 control attest,
   `:246-250`) and `results/ch5_100m/final_s{seed}.json` (treatment,
   `:373-376`; `base = REPO / args.dir`, default `results/ch5_100m`,
   `:355,363`); never from history, never the in-loop value.
2. `best_checkpoint.pt`: the argmax over 400 draws of `eval/return_mean`
   at n=100 (returns are +-1/0, so se ~0.08 per draw) — a noise-max.
   `scripts/eval_checkpoint.py:11-13` documents the selection bias;
   `scripts/score_ladder.py:50` refuses to score it; the frozen schedule
   reads the 100M crossing rung `ckpt_1000*.pt` — `HANDOFF.md:72` (§2 item
   1) is the whole of the source for the 100M object. No 100M script
   references it (`grep best_checkpoint scripts/ch5_100m_*` is empty).
   A DIFFERENT fleet's pin says the same thing about a different object: the
   R2 read-side pre-reg (`configs/eval/ch5_r2_offsh.yaml`, header line 2:
   "CH5 R2 — THE READ HALF OF THE BATCH PRE-REGISTRATION (JOURNEY step 1)")
   pins the 50M SYNC CONTROL's evaluated object in its
   `checkpoint_attestation` — `rule: final_checkpoint_pt_at_step_50000000`,
   i.e. `runs/showdown_sp_batch50m_s<N>/checkpoint.pt`, "the file the
   training loop writes on exit at step == 50,000,000; NOT
   best_checkpoint.pt, NOT any `ckpt_*.pt` rung (matches the control's own
   pin)" (`:498-501`). Quote that pin for the control only, and in full: its
   second clause excludes exactly the class of object the 100M schedule DOES
   read (a `ckpt_*.pt` crossing rung), so it is evidence that
   `best_checkpoint.pt` is refused project-wide, never evidence about the
   100M rung. Seven earlier training pre-reg headers disclaim it in their own
   words (`configs/showdown_sp6m.yaml:62`, `showdown_warmrl_v2.yaml:35`,
   `showdown_sp_l2init12m.yaml:239`, plus `scratch12m`, `sp_actpred12m`,
   `sp_priv12m`, `sp_recipe12m`; `grep -rli 'best.checkpoint\|best_ckpt'
   configs/` = 8 files, the eighth being `ch5_r2_offsh.yaml` above).
3. The `save_latest()` cadence (F-05) — the one load-bearing consumer, and
   load-bearing by placement, not by design.
4. A shape read during the run (health reads, HANDOFF §1). At se 0.04 the
   curve cannot resolve anything two neighbouring 250k rungs differ by; it
   is a coarse liveness signal. S-SHAPE (n=3000 every 5M, `:239-262`) is
   the shape that is reported.

## 4. Coupling with F-05 (described, NOT landed)

1. Plan §5 item 3 orders F-05 BEFORE F-06: fold `pool.state_dict()` into
   `checkpoint.pt`'s `extras`, one rename, a `stamp: step` asserted on
   resume, and `save_latest()` on its own cadence. The plan's example cadence
   is "every 4 updates, ~2 min at 574 steps/s"; the arithmetic gives 3.6 min,
   not 2 — one update is `rollout_steps` 3840 x `num_envs` 8 = 30,720 env
   steps (`configs/showdown_sp_100m.yaml:537, 576`; `rl/train.py:520`), so
   4 updates = 122,880 steps = **214 s ≈ 3.6 min** at 574 steps/s (2 updates
   would be ~1.8 min). Whoever quotes the run-loss window under F-05 must
   quote 3.6 min for a 4-update cadence, or pick 2 updates if ~2 min was the
   intent. [MEASURED: the config lines and `train.py:520`; the plan's "~2
   min" is a slip and is corrected here, not in the plan.]
2. STATUS at this draft: F-05 is being implemented in a sibling worktree on
   the `audit-fixes` branch family. At this draft's base (every audit branch
   at 5d3c6b7) no F-05 commit exists; nothing in this file may be read as
   "save_latest is decoupled". If F-05 does not land, option A in §5 is a
   REGRESSION on the run-loss bar (a 1M eval cadence = a 1M-step, ~29 min
   resume window) and only B is safe.
3. Once F-05 lands, `eval_every` stops being the resume granularity and the
   in-loop eval is free to move.

## 5. The proposal (PROPOSED; for the NEXT pre-reg, never the running one)

Sized against §2. "Prize" = share of the in-loop eval wall-clock removed.

- **A.** `eval_every: 1000000`, `eval_episodes: 100`. 100 evals/lane; se per
  reading unchanged (0.04); prize 75% (~0.4-2.2 h/lane); timer exposure
  COUNT /4, per-pause LENGTH unchanged; R0-6's first reading moves from
  250k to 1M. Config-only. REQUIRES F-05 first (§4).
- **B.** `eval_every: 250000`, `eval_episodes: 50`. 400 evals/lane; se
  0.057-0.071; prize 50%; per-pause length halved (the timer-relevant
  number); R0-6 and the resume window unchanged. Config-only; does NOT
  require F-05.
- **C.** Both (1M x 50): prize 87.5%; 100 readings/lane at se ~0.06 — enough
  for R0-6 and a liveness curve; not enough for anything that was ever
  allowed to be read from it, which is the point.
- **D.** `best_checkpoint.pt` on Showdown runs: **(i)** stop writing it when
  `cfg.env_id.startswith("Showdown")` (the `_write_run_metadata` idiom,
  `rl/train.py:142`); **(ii)** rename it `best_inloop_eval.pt` everywhere
  so the bias is in the filename; **(iii)** keep. (i)/(ii) are code
  changes. Spine-env tests assert the file exists (`tests/test_harness.py:79`,
  `tests/test_ppo.py:321`, `tests/test_run_capture.py:62,120`,
  `tests/test_normalize.py:231`) — all CartPole/Pendulum, untouched by (i),
  touched by (ii). The `loop.best_eval` bookkeeping
  (`rl/common/checkpoint.py:25-28`, `tests/test_resume.py:93-103`) stays
  under every option.

Recommendation (PROPOSED): **C + D(i)**. The per-reading precision was never
allowed to be read, so shrinking it costs nothing; wall clock and timer
exposure are real.

## 6. What must be preserved (the contract the next header restates)

1. R0-6 semantics: `eval/win_rate` must EXIST and be in (0,1) inside its
   window. R0's per-lane window is "FIRST 200K STEPS" (`:381`), yet R0-6 is
   already read at the first eval (250k) and its band is quoted over "the
   control's first 1M" (`:398-399`). At a 1M cadence the first reading
   lands AT 1M. The next header must state R0-6's window explicitly
   (PROPOSED wording: "the first reading, wherever the cadence places it").
2. Locked metric names; `eval_win_rate` stays ON in the Showdown config
   (`configs/showdown_sp_100m.yaml:542`; the `Config` field itself defaults
   to `False`, `rl/common/config.py:48`, and that default does not move);
   the `eval/win_rate` provenance rule (env-supplied outcome).
3. The frozen post-fleet read (`eval_checkpoint.py` at n=3000 on the
   crossing rung) — untouched; the in-loop eval never fed it.
4. Pre-reg one-diff discipline: `tests/test_100m_prereg.py:61` pins
   `eval_every == 250_000` for the RATIFIED file ("S3: untouched,
   undiscussed"). The next pre-reg is a NEW file whose one-diff test names
   `eval_every`/`eval_episodes` among the permitted diffs;
   `configs/showdown_sp_100m.yaml` is never edited.
5. Spine behaviour bit-identical: `Config` defaults do not move; only
   Showdown configs opt into the new cadence; D(i) is keyed on `env_id`.
6. Disclosure: the eval cadence is not a training lever (deterministic
   policy, no learner RNG consumed, separate env) but it changes the pause
   pattern and the realized rate D-B reads — the next header names it a
   NON-LEVER WIRE CHANGE (the F-04 idiom, plan §5 item 4) and quotes
   realized dStep/dWall, never `time/steps_per_sec`.

## 7. The decision the maintainer must make

1. A, B, C, or none — and for A/C, confirm "F-05 lands first" or accept the
   wider resume window explicitly.
2. D(i) stop, D(ii) rename, or D(iii) keep `best_checkpoint.pt` on Showdown.
3. Whether the change rides the next pre-reg header as a non-lever wire
   change (recommended) or needs its own pre-reg.
4. R0-6's window wording under the chosen cadence (§6 item 1).

## 8. Post-fleet evidence that sharpens the 1-6% range (MEASURED, to be produced)

1. After FLEET DONE and after the frozen schedule's PRIMARY — the ordering is
   NOT a bar on the extractor (HANDOFF §1 has it running on a LIVE run,
   `HANDOFF.md:53-55`; `runs/` is gitignored, `.gitignore:35`, the default
   output is `<run_dir>/history.csv` and `-o` redirects it,
   `scripts/extract_history.py:63, 68`). The reasons are that the numbers
   need FINISHED lanes (the 400-row per-lane total and the realized
   dStep/dWall) and that the off-FP@20 primary is time-budgeted and runs with
   "no co-scheduling" (HANDOFF §2 item 2), so nothing else should take CPU
   beside it. The read: `scripts/extract_history.py
   runs/showdown_sp_100m_s{104,112,120}` → `history.csv`; sum
   `time/eval_sec` per lane (expect 400 rows) over the REALIZED wall clock
   (dStep/dWall from rung mtimes). That ratio replaces "1-6%". A resumed
   lane needs the merge protocol first (`docs/landmines.md:268-283`; none
   had been resumed at the 2026-09-02 19:32Z read, plan header). Whoever
   schedules this is NOT this audit worktree, which may not run the
   extractor at all (`docs/archive/AUDIT_BRANCH_LOG.md:21-23`).
2. Distribution, not mean: the max and p99 of `time/eval_sec` are the
   timer-exposure numbers; compare against the acceptance max 26.18 s.
3. In-loop `eval/win_rate` (400 points/lane) against the S-SHAPE n=3000
   rungs: the residual sd of the n=100 curve around the n=3000 curve is
   what n=100 adds beyond shape (expected: its own se, i.e. nothing).
4. `time/collect_sec` on the rollout after each eval vs steady state: any
   post-pause recovery (paused battles finishing late) is an eval cost
   §2 does not count.

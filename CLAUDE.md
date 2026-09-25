# CLAUDE.md

Guide for Claude Code sessions on this repo. Rules here are binding and carry
one-clause whys; the full incident narratives live in `docs/landmines.md` —
read a section there before touching the thing it covers.

**Session start:** read `HANDOFF.md` if non-empty, then `STATUS.md` — the only
mandatory read. Everything else on demand per "Docs". **STATUS's `JOURNEY
POSITION` line is the arc: name the JOURNEY step any new work serves, or say
why it is off-arc — off-arc work needs a maintainer ruling.**

## If you read nothing else

Violating any of these costs hours, and each already has.

1. **Activate the `pokemon-showdown-rl` conda env.** Never `base`, never shared
   with `deep-rl-from-scratch` — both ship a top-level `rl` package and the
   loser imports silently from the wrong tree. **But the FLEET's env is
   `pkmn-engine-port`, NOT this one** (corrected 2026-09-22):
   `scripts/monster_fleet.sh` line 43 defaults `PY` there and
   `scripts/train_watchdog.sh` inherits it for every resume, because `engine`
   collection needs `pkmn_gen1`, which only that env has. This env is the one
   for analysis, evals and the reads queues. **Exception while a fleet is
   running: a session following `docs/engine_port_session_brief.md` creates a
   FRESH env of its own per that brief's §1.1 and must never install into
   `pkmn-engine-port` — the live lanes resume into it and a half-resolved
   dependency kills them at import — nor into this one.**
2. **Concurrent lanes need distinct `--seed`s, including across arms** —
   same-seed lanes collide on Showdown usernames (poke-env derives them from
   globally-seeded `random`) and die with a misleading `TimeoutError`.
3. **Commit docs before launching runs; launch from a clean tree.** One
   untracked `.md` stamps `git_dirty` on every run.
4. **Job ownership is by DURATION × KIND** (maintainer, 2026-08-26).
   **Training:** under 2 h run it yourself; 2–5 h ask first; over 5 h hand it
   over. **Eval/analysis:** any length may run agent-side *if it is safe* —
   (i) DETACHED from the agent's process tree (`nohup` / detached screen),
   (ii) RESUME-SAFE so a death costs one unit of work, (iii) progress readable
   as a RATE against a comparable completed arm. Meet all three and length is
   not the issue; miss any and hand it over regardless of length. (The binding
   risk is JOB LIFETIME, not throughput — agent-side runs are near-native;
   `docs/landmines.md` has the correction record.)
5. **`showdown/config/config.js` must set `simulator: 4`** (line ~111) — +81%
   collection throughput, and the file is gitignored, so re-set it after any
   re-clone.
6. **A SMALL-RUN NULL IS NOT EVIDENCE ABOUT A LEVER. Never cite one — not as
   a kill, not as a caveat, not in an opinion.** A 12M (or 50M, 3–5 seed)
   A/B cannot resolve an advisory-scale effect, so its null says nothing
   about the lever at 100M+; only a MEASURED MECHANISM CEILING kills (the
   maintainer's ruling, 2026-09-06, restated with anger 2026-09-11 after the
   fourth session quoted D18's 12M null as gospel). When the maintainer asks
   "what do you think of X", answer from mechanism, the literature at scale,
   and the format's properties — never from D18 / D23 / any sub-scale number.
   `docs/landmines.md` "Small-run nulls".

## What this project is

An RL agent playing **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`), battle phase only — no team building. Plays via
[poke-env](https://github.com/hsahovic/poke-env) against a local Node.js
Showdown server (vendored at `showdown/`, gitignored).

Capstone of the predecessor project `deep-rl-from-scratch`, spun out. That
project's "no RL libraries, everything from scratch" charter is complete,
banked there, and **retired here in full — including for the learner**. The
goal here is the strongest agent we can build; external libraries, replay
datasets, pretrained teachers, a GPU, a different learner are all in scope
when they win on merit. (But the PURE SELF-PLAY LANE is the novelty —
expert-data bootstrapping into the learner is excluded **until JOURNEY step 16**.)

**The arc is three acts (JOURNEY steps 14–16, maintainer 2026-09-23).** (1) Max out the
no-human-data lane, truly: every idea goes in first (R7's kitchen sink, then the own-lap
items). (2) The generality claim: the ALGORITHM is generation-agnostic and never tuned per
generation; a new generation costs its rules (the engine) and its state encoder, nothing
else, read on the same protocol — so every lever is written behind that interface, and a
lever that only works because of a gen-1 fact is a finding about gen 1, not part of the
system. (3) The TRUE FINAL step: human data in ANY form (replays, tapes, distillation,
offline RL, pretraining), only after (1) and (2), with the pure-lane finals and ladder runs
FROZEN before the first human row so the writeup can say what self-play alone reached.

Standing obligations: **pin exact versions** in `pyproject.toml`; **name
anything borrowed** in the README and in code comments; **keep secrets out of
committed files** (local paths are fine — relaxed 2026-08-05).

## Development environment

- **Env:** `conda activate pokemon-showdown-rl`
  (`/opt/anaconda3/envs/pokemon-showdown-rl`, Python 3.13), or call its
  `bin/python` / `bin/pytest` directly. One env per repo — rule 1.
- **Install:** `pip install -e ".[dev]"`. Dependency changes go through
  `pyproject.toml` with exact pins — no ad-hoc installs. Recreate with
  `conda create -y -n pokemon-showdown-rl python=3.13` + the editable install,
  then run the full suite to verify.
- **Showdown server** (required for anything touching the env):
  `cd showdown && node pokemon-showdown start --no-security`.
- **Train:** `python -m rl.train --config configs/<run>.yaml --seed N
  --run-name <name>` (resume: `--resume RUN_DIR`).
- **Metrics:** W&B defaults to offline; `scripts/extract_history.py <run_dir>`
  writes `history.csv`.
- **CPU only** for the RL loop. MPS was MEASURED 2026-09-01: it crashed on a
  one-site CPU-generator defect (`pool.py`, fixed 2026-09-05) and the prize
  behind it is ~2.5% — not worth an unvalidated backend. A GPU is permitted
  for supervised/offline arms if worth renting.
- **Gen 4 (JOURNEY step 3; groundwork merged 2026-09-05):** env
  `ShowdownGen4-v0` (`rl/envs/gen4/`; `configs/gen4_smoke_heur.yaml` is a
  SMOKE, not a pre-reg); Foul Play's gen-4 engine build lives in conda env
  `foul-play-gen4` (`scripts/setup_foulplay_gen4.sh`) — the gen-1 `foul-play`
  env stays untouched, one env per engine build. Design: `docs/design_gen4/`.
- **Tests:** `pytest tests/` from the repo root, in an env that has BOTH
  `pkmn_gen1` and the analysis deps — no env has both today (see CLEANUP).
  **The old "known flake" is FIXED (2026-09-10) and was never a flake:**
  poke-env derives seat usernames from the GLOBAL `random`, which `set_seed()`
  has already pinned by the time the live tests run, so the whole suite asked
  for identical names every time while a single file got OS entropy. That is
  the "fails in the suite, passes alone" signature. `tests/conftest.py` unpins
  it and bounds each `live_server` test at 300 s, because poke-env raises
  `nametaken` on a daemon loop and parks the main thread on an UNTIMED queue
  get — so a collision used to hang the suite forever at zero CPU rather than
  fail. All 9 live tests now pass in 4.5 s with a server up.

## Docs

- `STATUS.md` — **always read at session start.** Current state, last verdict
  with numbers, next actions, watch items. Hard cap 100 lines (raised from
  60 by the maintainer, 2026-09-10: "this is ridiculous how short it is" —
  the 60-line cap was forcing real findings out of the doc); rewritten in
  place; update it in the same commit that appends a session-log entry. On
  conflict, the newest session-log entry wins — say so and fix STATUS.md.
- `HANDOFF.md` — read only if non-empty (mid-handoff). Fold anything durable
  into STATUS/SESSION_LOGS, then restore the empty stub. Written only when the
  maintainer explicitly asks.
- `docs/IDEAS_POST_100M.md` — the live lever list, re-ranked after the 100M
  read; every entry needs its own pre-reg before it runs. (The Chapter 5
  brief is ARCHIVED at `docs/archive/CHAPTER5.md`, 2026-09-04; its §3/§6/§7
  live verbatim in `configs/showdown_sp_batch50m.yaml`.)
- `JOURNEY.md` — the maintainer's high-level goals, chapter by chapter
  (gen1 → gen4 → gen9); the only doc that says WHERE A WORK ITEM SITS. Read
  once per session at most: STATUS carries the current step. NOT a pre-reg —
  intent, not claims; no gates, figures not authoritative.
- `RESULTS.md` — **the account**: the claim, the evidence, what failed, every
  disclosure. Addenda accrue as chapters close; §16 is the ladder.
- `SESSION_LOGS.md` — dated entries; append as work lands. Index with
  `grep -n '^- 20' SESSION_LOGS.md`, then Read the chosen entry by
  offset/limit — never a broad keyword grep.
- `SESSION_LOGS_PREDECESSOR.md` — 36 capstone-era entries, frozen;
  SESSION_LOGS.md wins on conflict. Same read protocol.
- `readouts/` — committed ladder provenance (one file per run); the data
  behind them is gitignored.
- `docs/prior_work/README.md` — verified index of external material. **Read
  before citing any external result** — several widely-repeated claims about
  these systems do not survive contact with their code, and the index records
  which. Also points at a full local clone of `ps-ppo` (sibling directory) for
  encoder / action-space / reward / PPO-hyperparameter questions.
- `docs/CLEANUP.md` — the single cleanup ledger (audit backlog +
  do-not-relitigate record).
- `docs/` — everything else written down: `prior_work/`,
  `research_reports/`, `proposals/`, `design_gen4/`.
- `docs/archive/` — **history, never "what next"; nothing under it is read
  unless the maintainer names the file.** Spent roadmaps (DESIGN, DESIGN2)
  and frozen audits live there; their known traps are recorded in
  `docs/landmines.md`.
- `docs/landmines.md` — the full incident narratives behind every rule below.

## Landmines — one line each; the story and the fix live in `docs/landmines.md`

- Concurrent lanes: distinct `--seed`s (rule 2).
- Launcher liveness checks battle PROGRESS, not artifacts; lanes can SIGSEGV
  at startup before any log line — stagger and verify individually.
- **A lane can STALL MID-RUN with the process ALIVE and ZERO CPU** — every
  `pgrep` check passes forever (twice in R2, ~10 h apart, at 68.9% and
  94.3%). Confirm in 15 s with CPU-time deltas (`ps -o time=` twice), not by
  waiting on step counts — **summed over the lane's whole process TREE** (a
  `collector.process` lane's parent idles while its child collects; the
  parent alone read a healthy R7 smoke as stalled, 2026-09-25); recover with
  `--resume runs/<dir>` -- AFTER ~6.5 min (a resume onto the dead process's open Showdown room dies at
  its next eval; the watchdog waits `ROOM_REAP`). **Root cause
  found and FIXED 2026-08-31 — the ORPHANED-ROOM DEADLOCK; the CPU-delta
  check stays the instrument, because nothing else catches this shape.**
- **Every connecting seat sends `/timer on`** (`start_timer_on_battle_start`;
  2026-08-31, maintainer-ruled, WIRE-VISIBLE) — without a timer requester
  Showdown NEVER ends an abandoned room, the queue slot never returns and the
  lane wedges forever. Do not remove it. Verified live by
  `scripts/ch5_timer_smoke.py` and `scripts/ch5_orphan_demo.py`; a RESULTS
  disclosure line is OWED with the next headline number. The LADDER is the
  tight path (a 150 s bank refilling +10 s/turn, 150 s max for one turn — so
  ~10 s/turn sustained — not the 300 s a challenge gets).
- **A resume SPLITS the wandb history** into two offline runs with
  OVERLAPPING steps: `extract_history.py <run_dir>` then HARD-FAILS, and
  merging means pre-resume rows `_step < from_step` + the whole post-resume
  run. `checkpoint.pt` lags the last logged step by MUCH more than one update
  (R2 lost 190,776 and 170,680 steps) — read the real `from_step` from
  `meta.yaml`, and expect `updates_done` one short per resume.
- **CHECK FREE DISK BEFORE ANY FLEET OR READS LAUNCH, and ALERT the maintainer
  if it is near full** (2026-09-25: the data volume sat at 98%, 12.9 GB free, in
  the middle of the R7 fleet). Every lane keeps every checkpoint (~30 MB each
  500k steps, ~6 GB a 100M lane), and FP@N arms write ~0.25 GB of Foul Play
  stdout per 1,000 battles, so a full disk would have crashed all five lanes at
  a checkpoint write. Before launching: `df -h /System/Volumes/Data` and project
  the run's writes. If free space is under 2x that projection or under ~50 GB,
  STOP and alert the maintainer; re-check it on every monitor pass. Cleanup that
  loses nothing needed: gzip COMPLETED arms' `*.fp.stdout`, and prune a FINISHED
  run's intermediate checkpoints, keeping its final, `checkpoint.pt`,
  `best_checkpoint.pt`, `theta0.pt`, metadata and every checkpoint a tracked file
  names (`docs/landmines.md`).
- **Resource gates are calibrated at a FLEET WIDTH**: R2's D-E (STOP > 4.5 GB)
  came from 2.68 GB/lane 3-wide, and a lane running ALONE legitimately hit
  5.87 GB with the box 85% free — disclose, don't kill. Likewise a throughput
  window that straddles startup invents records; use the conforming window.
- A wall-clock ETA is not progress — check s/battle against a comparable
  completed arm (FP@20 ≈ 1.2–1.5 s, FP@100 ≈ 6–7 s); 10× off means stalled.
  An FP@N arm compares against a completed FP@N arm at the same slot count:
  its per-arm s/battle grows with load by design.
- **A TYPED DIAL LIST SILENTLY DROPS DIALS** — nine instances in one week of the
  same shape (a dial or counter that runs and reports nothing); the dial's counters
  stay ZERO, which reads as a RESULT rather than an error. Derive the list from the
  object's signature and hard-fail on unknown pre-reg keys.
- **A NUMBER TYPED FROM MEMORY INTO A CORRECTION IS AS UNSAFE AS THE ONE IT
  CORRECTS** — a correction carries more authority because nobody re-checks the fix.
  Re-derive every figure from `results/` and cite the file inside the box.
- **MATCH ON THE OVERRIDE RATE, NOT THE DELTA** — an unmatched gate turned a
  −0.0007 null into a −0.053 "result" on the same checkpoints and the same
  depth (2026-09-17). And a TREE arm reports `search/override_rate: None` (the
  field is gated on the matrix's `margin_delta`); the quantity is
  `search/flips / (decisions − skips)`. Taking the None at face value blocked a
  pin for four hours. **The gate is the instrument, not a nuisance parameter:**
  at ~6.5% override the search changes ~2 decisions of a 30-turn battle, which
  BOUNDS any leaf-value effect (RESULTS §24).
- **A RUNNING BLOCK IMPORTS THE WORKING TREE.** Each arm is a fresh process, so
  editing `rl/` mid-block makes the later arms a different program. Every arm
  stamps `launch_git_sha` and both live readouts now say when a block spans
  commits; `tests/test_tree_decision_golden.py` answers "did my edit change the
  search?" in a second. The encoder version is part of the search — the same
  fixture picks a different action at OBS_DIM 612 than at 828. **The installed
  extension is part of the working tree too:** `maturin develop` installs into
  `$CONDA_PREFIX` (base in a non-activated shell — set it explicitly), and a
  reinstall while any job in that env is still to start makes that job a
  different program (2026-09-23; `docs/landmines.md`). **A worktree pins nothing
  without `PYTHONPATH=<worktree>`:** the envs install the repo editable from
  main, so `import rl` resolves to main from any directory (2026-09-25).
- **`taskpolicy -b` (background QoS, PRI 4) SENDS A PROCESS TO THE FOUR EFFICIENCY CORES
  at ~6.8× per decision; plain `nice` (+5, measured) does NOT** (`docs/landmines.md`, both
  entries). zsh's `BG_NICE` puts every agent `cmd &` at nice +5 / PRI 31, which keeps the
  P-cores: the NI-5 R6 lanes ran 1,100–1,500 steps/s, nowhere near the E-cores' 6.8×
  penalty, while the PRI-4 G1b jobs lit exactly cpu0-3 (2026-09-24). Never put a training
  lane under background QoS: the two-core collector (`collector.process`) and
  `monster_fleet.sh` refuse background QoS, and `r7_fleet_launch.sh`, `r7_smokes.sh` and
  `fp_arms_parallel.py` refuse any niced shell. Timed instruments run at nice 0 — never
  nice or taskpolicy anything you time, because under contention priority decides who
  waits. Launch through `bash -c 'nohup … &'` and check `ps -o nice=,pri=`.
- **`_look_further` WAS OPTIMISTIC and its docstring said that was fine** — a
  max over our replies with the opponent pinned inflates the rows with the most
  escape hatches, which are the rows search overrides into. Fixed 2026-09-18
  behind `depth2.opp_k` (default 1 = the old backup, bit-identical); **every
  depth-2 arm before that date also carries an unexpanded-leaf re-scoring
  artifact** (`docs/CLEANUP.md` L4).
- **EVERY SEARCH NUMBER BEFORE 2026-09-11 MEASURES A BROKEN SELECTOR** (D4's hard
  argmax overrode a 0.789 policy on 72.8% of decisions; D5's margin gate turns
  -0.035 into +0.042 on the same critic). Grep `PRE-D5`. Such a number may NOT
  be used to argue search, depth or dose does not pay — re-measure under D5.
  **LADDER R3 is a D4 object.**
- Changing `OBS_DIM` invalidates every checkpoint — evaluate outstanding
  finals first.
- **One vs-SH rung at n=3000 is worth ±0.02, not the binomial ±0.008** — three
  re-draws of ONE checkpoint spread 0.0200 (2026-08-31). Read a curve's SHAPE
  over tens of millions of steps; never one rung against its neighbour.
- `eval/win_rate` is env-supplied outcome, never return-sign;
  `wins_from_returns` exists only as the cross-check and the two must agree.
- **vs-SH numbers are NOT ladder numbers** — never project in either
  direction; the ~40% GXE conversion is RETIRED. LADDER R1: GXE 59.6%,
  Glicko-1 1573 ± 27, final Elo 1292, n=200 (the profile carries GXE/Glicko
  for ANY rated account — the leaderboard JSON only for listed ones; and
  JSONL `rating` is PRE-battle). Ladder runs: `scripts/ladder.py` under each
  run's own pre-reg (`ladder_r3.yaml` is the template that can actually
  fire); `scripts/score_ladder.py` is a Connect-4-era false friend.
- **Foul-Play runner ops:** all four incident fixes live in
  `scripts/ch3_r4_fp_runner.sh` — do not reintroduce (subshell-pid orphans;
  kill search-worker children FIRST; a killed arm's username pair is poisoned
  for hours, re-run it LAST or on a fresh pair; no forfeit at a clean
  boundary; G2 is two tallies agreeing, never a subtraction). **Since
  2026-09-25 foul-play runs in its OWN process group and dies as one group
  kill — never reintroduce a box-wide `pkill` of foul-play workers**, which
  killed every other arm's search the moment two arms shared a box. **One
  crash can orphan TWO rooms** (CALN8), so the n_eff rule can under-count;
  `scripts/fp_arm_counters.py` catches it.
- Shell loops run under `bash`, not zsh; anything handed to the maintainer
  runs in THEIR zsh.
- `scripts/showdown_throughput.py` numbers are collection-only (~7×
  overstatement) at `[64,64]` — quote with width and scope.

## Conventions (they earned their place)

- **STACK WHAT CANNOT BE THE SOLE SUSPECT; LAP WHAT MUST BE ISOLATED** (maintainer,
  2026-09-23, *"make R7 the kitchen sink"*; the one-lever-per-week cadence is over). A
  lever rides in a fleet's base only if it is a FIX, a DOSE at the same objective, or a
  BUILT-AND-SMOKED addition with its own mechanism counter on disk; trunk/architecture
  replacements and objective changes get their own lap against that base. A critic-side
  lever is NOT actor-neutral in PPO (the critic sets the advantages — D18's own falsifier),
  so it stacks only with its counter watched. The cadence changed; the anti-self-deception
  machinery below did not.
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS, NOT FOR HACKING** (maintainer,
  2026-09-17, verbatim: *"pre-reg is for ladder runs. For hacking and trying ideas,
  keep going by yourself"*). An offline arm that explores an idea needs no pre-reg,
  no ratification and no waiting: build it, run it, report it. What does NOT relax
  is the anti-self-deception machinery, because that is about not fooling ourselves
  rather than about ceremony — **counters must reach disk before a dial gets an arm,
  and a harness's DIAL LIST MUST BE DERIVED FROM THE OBJECT'S SIGNATURE, NEVER
  TYPED (a typed list silently drops a dial added later, and the arm then runs as a
  CONTROL while its readout claims the dial — `docs/landmines.md`);
  a comparison must be matched on the thing that is not being tested (2026-09-17: an
  unmatched override rate turned a −0.0007 null into a −0.053 "significant" result);
  and a cross-session number needs a same-session anchor (~0.02 on both FP
  instruments)**. Anything that becomes a headline number, a README row or a ladder
  run gets the full treatment below, written BEFORE it runs.
- **Pre-register every LADDER RUN and every headline-grade experiment** in the config header before launching —
  pattern: `configs/showdown_r512_lra.yaml`. **Every header names its
  `journey_step` and restates that step's exit condition verbatim.** Arms, R0
  sanity gates, PRIMARY read with explicit credit line, secondary reads,
  action on each branch.
- **Credit line:** a lever is credited iff pooled delta ≥ +0.025 **and**
  ≥ 2·se_diff. **The header must restate this verbatim, including the
  larger-of (binomial vs seed-clustered) se_diff clause.**
- **Five pre-reg rules the D25/D25-P cycle paid for** (each cost a maintainer
  ruling — SESSION_LOGS 2026-08-11 onward): name the across-lane aggregator;
  leave no unnamed cells in a partition; decide up front whether dose is
  matched and how you'd know; restate the credit line verbatim; say which side
  each band reads.
- **Locked eval protocol:** final checkpoint, **3000 battles/seed**, 3 seeds
  pooled, ties as non-wins, deterministic policy, vs `SimpleHeuristicsPlayer`.
  Every arm from D23 on has pooled **5×3000** — a disclosed DEVIATION
  (conservative, 5 ≥ 3); say so when quoting it.
- **Anchor battery** (2026-08-23; FP budget amended 2026-08-26 per MU-2; per-gen
  list ruled 2026-09-05): every headline-grade result reports vs-SH (locked
  protocol, the ONLY verdict input) **plus every descriptive leg for its
  generation** before its README row lands. **Gen 1:** BC-clone h2h (500),
  Foul Play h2h at FP@N 25k/12k (FP@20 RETIRED 2026-09-25). **Gen 4:** most-damage-typed h2h (500), Foul Play h2h at
  BOTH 20 and 500 ms until Q38 pins one (written before FP@20's retirement;
  25k/12k is calibrated only on gen 1's engine, so gen 4's FP leg is re-ruled
  when that chapter reopens), BC-clone h2h (500; a gen-4 clone of
  FP@20 tapes — built alongside the first gen-4 run, ready by its readout). A
  leg that does not exist yet is reported as PENDING and the README row WAITS
  for it — legs are never dropped to make a readout land. Random / MaxBasePower
  may print as sanity rows; they are not legs. Anchors are descriptive,
  **never verdict inputs**.
  - **Match the policy form to the rating you compare against** — a clone
    number is never style evidence.
  - **Gen-1 FP instrument is FP@N 25k/12k since 2026-09-25** (unanimous: the
    maintainer, r6-runner, r7-runner). Each arm declares `search_iterations:
    25000, search_iterations_early: 12000` and runs K-wide through
    `scripts/fp_arms_parallel.py`, beside other work if need be, because a
    fixed budget loses time under load, never strength.
    `readouts/FP_ITER_CALIB_READOUT.md`, `readouts/FP_PARALLEL_ROI_READOUT.md`.
    - **Its calibration travels with every FP@N number:** two seats vs FP@20,
      NON-REJECTION, offset CI95 [−0.026, +0.011], gap-change CI95 [−0.042,
      +0.033], MDE 0.054.
    - **Never difference across instruments.** A read re-draws its comparator
      on FP@N in-session. Never set an FP@20 number, or a threshold defined on
      FP@20, against an FP@N delta without saying so. Name "FP@N 25k/12k" in
      every quote beside the two disclosures below.
    - **An arm whose runner JSON has `fpn_counters_ok: false` is INVALID.**
      The counters require realized iterations == N on 100% of non-forced
      searches, and timer+forfeit losses ≤ crash forfeits.
    - **FP@20 IS RETIRED** (maintainer 2026-09-25: "No one should run outdated
      F@20 anymore"; unanimous with r6-runner, fp-speedup, r7-runner). No new
      FP@20 arm by anyone: the runner (exit 7) and `fp_arms_parallel.py` refuse
      a gen-1 arm with `search_time_ms: 20` and no `search_iterations`
      (`6936b2f`, `tests/test_fp_runner_guards.py`), and R7's G2 moved to FP@N
      (r3). Banked FP@20 numbers stay citable as history, never differenced
      against FP@N. **EVERY wall-clock budget is retired with it** (FP@100/500
      too; maintainer, same day: "We should never run a FP@500 or 100 again
      serially ... I don't want to ever again wait hours for FP runs unless
      calibrating a new N."). A bigger budget runs only as its own
      CALIBRATED FP@N, K-wide (FP@500's is visits-matched, strength not tested,
      ruled). The runner and the scheduler refuse EVERY gen-1 arm without
      `search_iterations` (`fbe36a1`), except an arm declaring
      `calibration_reference_for`: the wall-clock reference inside calibrating a
      new N, the one serial quiet-box FP left — wall-clock FP loses iterations
      under load (FP@20 measured −16 to −19% of iterations/ms at 4–8 arms even
      on P-cores).
  - FP@20 (the wall-clock anchor until its retirement on 2026-09-25) was `--search-time-ms 20`.
    **Two disclosures travel with every FP number, forever:** the equivalence
    test is weakly powered, and the point estimate flatters us. **Name the
    budget in every quote.** FP@N is an instrument, not a rung — the readiness gradient is the FP budget
    ladder (`configs/eval/fp_budget_ladder.yaml`; its wall-clock rungs are retired, each
    re-expressed as a calibrated FP@N before it runs again). **Gen 4's budget is UNPINNED
    until that ladder runs against the first trained gen-4 checkpoint (ruled
    2026-09-05); quote 20 and 500 ms both meanwhile.**
- **Locked metric names:** `rollout/episode_return`, `rollout/episode_length`,
  `eval/return_mean`, `eval/return_std`, `eval/win_rate`,
  `time/steps_per_sec`, `time/collect_sec`, `time/update_sec`,
  `time/eval_sec`, plus `loss/*`, `selfplay/*` and (2026-09-05, the
  both-seat harvest) `harvest/*` — logged from PPO's update, never from
  env or pool code.
- **Action masking is a harness contract.** Discrete envs always emit
  `info["action_mask"]`; algorithms mask through `rl/common/masking` with a
  finite `-1e8` sentinel, never `-inf`; no `mask is None` branches; the value
  head is never masked; masking applies at eval too.
- Small, single-purpose commits; end every session green and committable.

## Working with the maintainer

- Deep ML/DL fluency (production PyTorch) — don't explain tensors or PyTorch
  basics. RL specifically is newer; explaining RL concepts and algorithm
  design choices is welcome.
- Direct tone; skip superlatives and filler; push back when warranted.
- **Answer length: lead with the verdict in one or two sentences and stop,
  unless more would change what the maintainer does next.** No headers, no
  bolded label on every paragraph, no restating the question. Disclosure and
  caveat norms govern DOCS AND COMMITS, not chat. Sessions are short evening
  blocks — optimize for incremental, resumable progress.
- **Handed-over commands: one command per fenced block, never multi-line.**
  No inline `#` comments. State-changing steps (`kill`, `rm`) are separate
  blocks run one at a time; runs meant to execute together are ONE
  `&&`-chained line. Wrap every block in `<command>` / `</command>` sentinel
  lines OUTSIDE the fence.
- **Git:** commit your own work directly, without asking, in small
  single-purpose commits. Committing to `main` is normal flow. **Pushing is
  different: never commit+push in one command, and always ask before
  pushing.**

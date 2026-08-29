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
   loser imports silently from the wrong tree.
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
expert-data bootstrapping into the learner is excluded.)

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
- **CPU only** for the RL loop; MPS is flaky here. A GPU is permitted for
  supervised/offline arms if worth renting.
- **Tests:** `pytest tests/` from the repo root. Known flake (documented
  in-file): `test_full_episode_contract_against_live_server` fails only when
  the whole suite runs with a server up; passes alone.

## Docs

- `STATUS.md` — **always read at session start.** Current state, last verdict
  with numbers, next actions, watch items. Hard cap 60 lines; rewritten in
  place; update it in the same commit that appends a session-log entry. On
  conflict, the newest session-log entry wins — say so and fix STATUS.md.
- `HANDOFF.md` — read only if non-empty (mid-handoff). Fold anything durable
  into STATUS/SESSION_LOGS, then restore the empty stub. Written only when the
  maintainer explicitly asks.
- `CHAPTER5.md` — the current chapter brief. **The SHAPE is RATIFIED
  (2026-08-26, §7); R1 is CLOSED and R3 laddered; R2 (batch, JOURNEY step 1)
  is the next arc work.** Its §3/§6/§7 must migrate into R2's pre-reg header
  before the file can be archived — never before.
- `JOURNEY.md` — the maintainer's high-level goals, chapter by chapter
  (gen1 → gen4 → gen9); the only doc that says WHERE A WORK ITEM SITS. Read
  once per session at most: STATUS carries the current step. NOT a pre-reg —
  intent, not claims; no gates, figures not authoritative.
- `SESSION_LOGS.md` — dated entries; append as work lands. Index with
  `grep -n '^- 20' SESSION_LOGS.md`, then Read the chosen entry by
  offset/limit — never a broad keyword grep.
- `SESSION_LOGS_PREDECESSOR.md` — 36 capstone-era entries, frozen;
  SESSION_LOGS.md wins on conflict. Same read protocol.
- `readouts/` — committed ladder provenance (one file per run); the data
  behind them is gitignored.
- `prior_work/README.md` — verified index of external material. **Read before
  citing any external result** — several widely-repeated claims about these
  systems do not survive contact with their code, and the index records which.
  Also points at a full local clone of `ps-ppo` (sibling directory) for
  encoder / action-space / reward / PPO-hyperparameter questions.
- `CLEANUP.md` — the single cleanup ledger (audit backlog + do-not-relitigate
  record).
- `docs/archive/` — **history, never "what next"; nothing under it is read
  unless the maintainer names the file.** Spent roadmaps (DESIGN, DESIGN2)
  and frozen audits live there; their known traps are recorded in
  `docs/landmines.md`.
- `docs/landmines.md` — the full incident narratives behind every rule below.

## Landmines — one line each; the story and the fix live in `docs/landmines.md`

- Concurrent lanes: distinct `--seed`s (rule 2).
- Launcher liveness checks battle PROGRESS, not artifacts; lanes can SIGSEGV
  at startup before any log line — stagger and verify individually.
- A wall-clock ETA is not progress — check s/battle against a comparable
  completed arm (FP@20 ≈ 1.2–1.5 s, FP@100 ≈ 6–7 s); 10× off means stalled.
- Changing `OBS_DIM` invalidates every checkpoint — evaluate outstanding
  finals first.
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
  boundary; G2 is two tallies agreeing, never a subtraction).
- Shell loops run under `bash`, not zsh; anything handed to the maintainer
  runs in THEIR zsh.
- `scripts/showdown_throughput.py` numbers are collection-only (~7×
  overstatement) at `[64,64]` — quote with width and scope.

## Conventions (they earned their place)

- **Pre-register every experiment** in the config header before launching —
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
- **Anchor battery** (2026-08-23; FP budget amended 2026-08-26 per MU-2):
  every headline-grade result reports vs-SH (locked protocol) **plus** two
  descriptive anchors — BC-clone h2h (500) and Foul Play h2h — before its
  README row lands. Anchors are descriptive, **never verdict inputs**.
  - **Match the policy form to the rating you compare against** — a clone
    number is never style evidence.
  - FP anchor at `--search-time-ms 20`. **Two disclosures travel with every
    FP@20 number, forever:** the equivalence test is weakly powered, and the
    point estimate flatters us. **Name the budget in every quote.** FP@20 is
    an instrument, not a rung — the readiness gradient is the FP budget
    ladder (`configs/eval/fp_budget_ladder.yaml`).
- **Locked metric names:** `rollout/episode_return`, `rollout/episode_length`,
  `eval/return_mean`, `eval/return_std`, `eval/win_rate`,
  `time/steps_per_sec`, `time/collect_sec`, `time/update_sec`,
  `time/eval_sec`, plus `loss/*` and `selfplay/*`.
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

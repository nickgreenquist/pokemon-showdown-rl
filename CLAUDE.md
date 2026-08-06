# CLAUDE.md

Guide for Claude Code sessions on this repo. At session start read `HANDOFF.md` if non-empty, then `STATUS.md` — the only mandatory read; everything else on demand per "Docs" below.

## What this project is

An RL agent that plays **Pokémon Showdown Gen 1 random battles** (`gen1randombattle`), battle phase only — no team building. It plays via [poke-env](https://github.com/hsahovic/poke-env) against a local Node.js Showdown server (vendored at `showdown/`, gitignored).

This is the capstone of the predecessor project `deep-rl-from-scratch`, spun out into its own repo. That project's "no RL libraries, everything from scratch" charter is complete, banked there, and **retired here in full — including for the learner**. The goal here is the strongest agent we can build; external libraries, replay datasets, pretrained teachers, a GPU, a different learner are all in scope when they win on merit. Standing obligations:

- **Pin exact versions** in `pyproject.toml`.
- **Be honest about provenance** — anything borrowed gets named, in the README and in code comments.
- **Keep secrets out of committed files.** The stricter no-personal-details / may-go-public rule was relaxed 2026-08-05 — local paths and the like are fine.

## Development environment

- **Always run in the `pokemon-showdown-rl` conda env** (`/opt/anaconda3/envs/pokemon-showdown-rl`, Python 3.13): `conda activate pokemon-showdown-rl`, or call `/opt/anaconda3/envs/pokemon-showdown-rl/bin/python` / `.../bin/pytest` directly. Never `base`, and **never share an env with `deep-rl-from-scratch`** — both repos ship a top-level package named `rl`; in a shared env the first `.pth` alphabetically wins and the loser imports silently from the wrong tree (measured, in both repos). One env per repo.
- Recreate from scratch if needed: `conda create -y -n pokemon-showdown-rl python=3.13`, then `pip install -e ".[dev]"` in it. Verified 2026-08-05: fresh env runs the offline suite green (288 passed).
- The repo installs editable: `pip install -e ".[dev]"`. Dependency changes go through `pyproject.toml` with exact pins — no ad-hoc `pip install`, no `conda install`.
- **Showdown server** (required for anything touching the env): `cd showdown && node pokemon-showdown start --no-security`. The server config `showdown/config/config.js` is gitignored — `simulator: 4` (line ~111) must be set; it is worth +81% collection throughput. If `showdown/` is ever re-cloned, re-set it.
- **Train**: `python -m rl.train --config configs/<run>.yaml --seed N --run-name <name>`
- **Metrics**: W&B defaults to offline; `scripts/extract_history.py <run_dir>` writes `history.csv`.
- **CPU only** for the RL loop; MPS is flaky for this workload. A GPU is permitted for supervised/offline arms if worth renting.
- Tests: `pytest tests/` from the repo root. Known flake: `test_full_episode_contract_against_live_server` fails only when the whole suite runs with a server up; passes alone.

## Docs

Session start: read `HANDOFF.md` only if non-empty (mid-handoff — fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub; written only when the maintainer explicitly asks for a handoff), then `STATUS.md` — the only mandatory read.

- `STATUS.md` — always read at session start. Current state, last verdict with numbers, next actions, watch items. Rewritten in place (never appended), hard cap 60 lines; update it in the same commit that appends a session-log entry. On conflict, the newest session-log entry wins — say so and fix STATUS.md.
- `DESIGN.md` — **the roadmap.** Self-contained (written for external reviewers, needs no other file); read it for any substantive "what next" question rather than restating it elsewhere. Status: **r6 RATIFIED 2026-08-05** (D1–D7 binding) — implement it. Sections added AFTER ratification carry their own status line and are PROPOSED until the maintainer ratifies them; §11 (search) is one. Lifecycle: each pre-registration migrates into its config header, and the file is deleted once fully migrated.
- `SESSION_LOGS.md` — dated entries (findings, decisions, run records); append as work lands. Index with `grep -n '^- 20' SESSION_LOGS.md`, then Read the chosen entry by offset/limit — never a broad keyword grep.
- `SESSION_LOGS_PREDECESSOR.md` — the 36 capstone-era entries recovered from the predecessor repo (P3/P4/P5-era detail, milestones; plus its Phase-5 README/PLAN sections as appendices). Historical and frozen; SESSION_LOGS.md wins on conflict. Same read protocol.
- `prior_work/README.md` — verified index of external material. Read it before citing any external result; several widely-repeated claims about these systems do not survive contact with their code, and the index records which. It also points at a full local clone of the strongest comparable agent (`ps-ppo`, sibling directory) — read that source directly for encoder/action-space/reward/PPO-hyperparameter questions.

## Landmines — each of these already cost real time; do not rediscover them

- **Concurrent training lanes MUST use distinct `--seed` values, including across arms.** `rl/common/seeding.py` seeds global `random`, poke-env derives usernames from it; same-seed lanes collide on Showdown usernames and the loser dies with the misleading `TimeoutError: Agent is not challenging` at first `reset`.
- **Launcher liveness must check battle PROGRESS, not artifacts.** Run dirs (`config.yaml`, `meta.yaml`, `wandb/`) are written before the first `reset`; "directory exists" is true for a lane that never trained.
- A lane can die at startup with SIGSEGV in torch lazy static init, before any log line or run dir. Stagger lane starts; verify every lane individually.
- **Shell loops run under `bash`, not zsh** — unquoted `$VAR` does not word-split in zsh. Also zsh: `echo ===` is a glob error; inline `#` comments do not parse interactively.
- **Changing `OBS_DIM` invalidates every existing checkpoint.** Evaluate all outstanding finals before any encoder change lands.
- **`eval/win_rate` comes from env-supplied `info["outcome"] ∈ {-1,0,+1}`, never the sign of the return** — a reward-sign inversion would report 100% and pass its own detector (measured). `scripts/score_ladder.py` is the correct path; `scripts/eval_checkpoint.py` returns raw returns only.
- **Commit docs BEFORE launching runs; launch from a clean tree.** Launches stamp `git_dirty`; one untracked `.md` flips it (measured: dirtied 8 of 9 runs once). Never edit the tree — even untracked files — while the maintainer may be launching.
- `scripts/showdown_throughput.py` measures server-side decisions/s only — collection-only numbers overstate full-loop gains ~7×, and it hardcodes `[64,64]` where production is `[512,512]`. Anything quoted from it must carry its network width.

## Conventions (they earned their place)

- **Pre-register every experiment** in the config header before launching — pattern: `configs/showdown_r512_lra.yaml`. Arms, R0 sanity gates, PRIMARY read with explicit credit line, secondary reads, action on each branch.
- **Credit line:** a lever is credited iff pooled delta ≥ +0.025 **and** ≥ 2·se_diff.
- **Locked eval protocol:** final checkpoint, 1000 battles/seed, 3 seeds pooled, ties as non-wins, deterministic policy, vs `SimpleHeuristicsPlayer`.
- **Locked metric names:** `rollout/episode_return`, `rollout/episode_length`, `eval/return_mean`, `eval/return_std`, `eval/win_rate`, `time/steps_per_sec`, `time/collect_sec`, `time/update_sec`, `time/eval_sec`, plus `loss/*` and `selfplay/*`.
- **Action masking is a harness contract.** Discrete envs always emit `info["action_mask"]`; algorithms mask through `rl/common/masking` with a finite `-1e8` sentinel, never `-inf`; no `mask is None` branches; the value head is never masked; masking applies at eval too.
- Small, single-purpose commits; end every session green and committable.

## Working with the maintainer

- Deep ML/DL fluency (production PyTorch background) — don't explain tensors, gradients, PyTorch basics. RL specifically is newer — explaining RL concepts and algorithm design choices is welcome.
- Direct tone; skip superlatives and filler; push back when warranted. Sessions are short evening blocks — optimize for incremental, resumable progress.
- **Runs longer than ~5 minutes go in the maintainer's terminal, not through Claude** (agent-launched training measured ~10× slower). Hand over the exact command, then read logs/checkpoints from disk. Short smokes and pytest stay in-session.
- **Handed-over commands: one command per fenced block, never multi-line.** No inline `#` comments. State-changing steps (`kill`, `rm`) are separate blocks run one at a time; runs meant to execute together are ONE `&&`-chained line. Wrap every handed-over block in `<command>` / `</command>` sentinel lines OUTSIDE the fence.
- **Git:** commit your own work — `git add` + `git commit` directly, without asking, in small single-purpose commits as the work lands. Committing to `main` is this repo's normal flow; do not branch for it. **Pushing is different: never commit+push in one command, and always ask before pushing.**

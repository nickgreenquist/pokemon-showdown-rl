# AUDIT_BRANCH_LOG.md — the `audit-fixes` branch, worked while the 100M fleet ran

Branch started 2026-09-02 ~20:40Z from `main` @ 60c1225 in the isolated worktree
`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit`, under the
maintainer's `AUDIT_WORKTREE_PROMPT.md`. Work order: `docs/AUDIT_ACTION_PLAN.md` §5.
This log is folded into SESSION_LOGS at merge time; SESSION_LOGS / STATUS / HANDOFF
were not touched by this branch.

## Hard bars observed (the fleet's, restated so the record is auditable)

- Main tree never edited, checked out, or committed on; every change lives on
  `audit-fixes` (and short-lived per-finding branches merged into it).
- No `pip install` into the `pokemon-showdown-rl` env — the editable install must
  keep pointing at the main tree. Dependency changes, if any, are proposed in
  `pyproject.toml` only.
- No Showdown server contact, no battles, no process signalled, no checkpoint
  evaluation, no training run, no throughput benchmark, no reads of `runs/` or
  `logs/`, no `extract_history.py`.
- Tests: targeted single-file runs only, `nice -n 19`, never `pytest -n`, never the
  full suite. **Full-suite verification is DEFERRED to post-fleet** (see the
  deferred list at the end).

## Setup record

- `git worktree add ../pokemon-showdown-rl-audit -b audit-fixes` → main tree left at
  60c1225, `git status` clean before and after.
- Import isolation verified from the worktree root:
  `python -c "import rl; print(rl.__file__)"` →
  `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit/rl/__init__.py`.
  `sys.meta_path` order is `PathFinder` then `_EditableFinder`, so cwd shadows the
  editable install; `PYTHONPATH=<worktree>` is added anyway as belt and braces.
- **Server guard.** The six server tests are gated by `skipif(not _server_up())`,
  which makes them RUN whenever a server is up — i.e. exactly now. Two layers:
  1. commit 940def6 registers a `live_server` marker (pyproject
     `[tool.pytest.ini_options]`) and tags the six tests, so `-m "not live_server"`
     deselects the class;
  2. a session-local pytest plugin (`noserver_plugin.py`, scratchpad, not in the
     repo) monkeypatches `socket.socket.connect`/`connect_ex` to refuse port 8000
     with `ConnectionRefusedError`. `_server_up()` therefore returns False (the
     gated tests skip as in a bare run) and any UNGATED connector fails loudly
     instead of logging into the live server.
- **The one test invocation used on this branch** (wrapper `audit_pytest.sh`,
  scratchpad; refuses the main tree, `-n`, and the bare suite; re-checks import
  isolation each call). Expanded:

      cd <worktree> && PYTHONPATH=<worktree>:<scratchpad> PYTHONDONTWRITEBYTECODE=1 \
        OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 \
        /opt/anaconda3/envs/pokemon-showdown-rl/bin/python -m pytest -q \
        -p no:cacheprovider -p noserver_plugin -m "not live_server" tests/<file>.py

- `data/` (tapes, gitignored) exists only in the main tree. Where a tape gate had to
  run (F-08 bit-identity), a transient `data -> <main tree>/data` symlink was placed
  in the working worktree for READ access only and removed afterwards; it shows as
  `?? data` while present and never entered a commit.

## Baseline (pre-change, this branch @ 940def6, one file at a time, nice'd)

25 in-scope files, sequential, ~50 s total. All green except four, every one
explained by the worktree itself rather than by the code:

| file | result @ 940def6 | cause |
|---|---|---|
| test_showdown_env | 5 failed, 49 passed, 3 deselected | `FileNotFoundError: rl/envs/data/gen1_randbats_sets.json` → **F-21** |
| test_collect | 4 failed, 3 passed, 2 deselected | same |
| test_ch3_matrix | 6 failed, 5 passed | same |
| test_entity_deepsets | 1 failed (`test_r03_mlp_trunk_bit_identical_to_pre_seam_goldens`) | wrapper had `OMP_NUM_THREADS=1`; the golden's `.double().sum()` over ~700k params is reduction-order dependent and was captured at this box's default 10 threads → **F-22**; passes at default threads |

Everything else: test_selfplay_pool 20, test_resume 5, test_frozen_opponent 2,
test_selfplay_harness 31, test_pool_pertag 6, test_ppo 25, test_ppo_episodes 6,
test_masking 11, test_l2_init 14, test_zeroinfo 3 (+9 skipped), test_episode_buffer 6,
test_rollout 7, test_encoder_v2 2, test_encoder_ids_tapes skipped (no `data/`),
test_hl_shaping_tapes skipped (no `data/`), test_mask_desync 8, test_privileged_block 4
(+1 deselected), test_run_capture 4, test_eval_shim 3, test_loop_timers 1,
test_opp_action 19 — all passed.

### Branch-discovered findings (not in the action plan)

- **F-21 [Medium, reproducibility] — the encoder's set prior was never tracked.**
  `rl/envs/randbats_prior.py` hard-requires `rl/envs/data/gen1_randbats_sets.json`
  and its docstring says the copy "lives here to keep the offline encoder
  reproducible", but `.gitignore`'s `data/` rule matched `rl/envs/data/` too. The
  file existed only in the maintainer's working tree; a fresh clone or worktree
  fails 20+ tests and cannot encode a battle. **Landed on this branch** (commit
  `F-21:` whitelists dir + file; 25 KB, sha256 `85fc2743…5380f` matches the
  docstring). **Maintainer ruling wanted at merge:** the `prior_work/` rule is
  "track iff the content is ours"; this is borrowed (Showdown, MIT) but a hard
  runtime dependency — the alternative is a setup-script copy from the pinned
  `showdown/` checkout. Tracking is the reversible default chosen here.
- **F-22 [Low, test fragility] — R0-3 goldens are thread-count dependent.**
  `tests/test_entity_deepsets.py::test_r03_mlp_trunk_bit_identical_to_pre_seam_goldens`
  asserts exact equality of `torch.cat(params).double().sum()` (captured at 10
  threads); under `OMP_NUM_THREADS=1` the sum differs in the last digit
  (`-23.334520053290372` vs golden `-23.33452005329038`). The forward-pass goldens
  may share the sensitivity. Proposed ride-along: keep the exact-equality intent but
  compare the two parameter sums with `abs_tol=1e-9` (a real init change moves them
  by O(1)), and note the thread dependence in the docstring. **Landed** (commit
  `F-22:`; measured: only `csum` moves between 1 and 10 threads — `asum`, the logits
  sum and the three value goldens are identical, so those stay exact). Verified:
  `audit_pytest.sh tests/test_entity_deepsets.py` → 5 passed at default threads AND
  under `OMP_NUM_THREADS=1`.

## Findings — one section per landed finding

(filled in as work lands: what changed, commits, exact test invocations and
results, tests deferred to post-fleet, open questions for the maintainer)

## Deferred to post-fleet (not run on this branch)

- The full suite (`pytest tests/`, bare, no encoder env vars) — rule 6.
- Every `live_server` test, including the new async pause/resume live test.
- Any `profile_collect.py` / throughput number (F-11 is not attempted for this
  reason).

## Open questions for the maintainer

(collected here; each also appears in its finding's section)

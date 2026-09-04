> **ARCHIVED 2026-09-04 — WORK ORDER, CLOSED.** The maintainer's brief that
> governed the `audit-fixes` worktree while the 100M fleet ran (2026-09-02 →
> 09-04). Kept as provenance for the hard bars recorded in
> `AUDIT_BRANCH_LOG.md`. Nothing below is a current instruction; the setup
> paths no longer exist.

ultracode. You are working the codebase audit in an ISOLATED WORKTREE while a
maintainer-ratified 100M training fleet runs on this box for the next ~18h.
Another Claude session is babysitting that fleet — you are NOT. Your job is
engineering on a branch; nothing you do may perturb the run.

## THE RUNNING FLEET — READ FIRST, THESE ARE HARD BARS

Three `python -m rl.train` lanes (seeds 104/112/120), a supervisor
(`bash scripts/ch5_100m_wave.sh`), `caffeinate`, a `node pokemon-showdown`
server on localhost:8000, and an RSS sampler are live. The run is governed by
a frozen pre-registration (`configs/showdown_sp_100m.yaml` header). Rules:

1. NEVER touch the main tree at
   /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl — no edits,
   no `git checkout`, no commits, no doc updates there. The fleet's
   auto-resume relaunches rl.train FROM THAT TREE; changing it can silently
   contaminate a resumed lane. You work ONLY in the worktree you create.
2. NEVER run `pip install` into the `pokemon-showdown-rl` conda env — no
   `pip install -e .` from the worktree. The env's editable install points at
   the main tree and must keep pointing there (a resume imports through it).
   Dependency changes: propose in pyproject.toml on the branch, don't install.
3. NEVER touch the Showdown server or port 8000: no live-server tests
   (deselect `test_full_episode_contract_against_live_server` and anything
   marked as needing a server), no battles, no server restarts, no killing
   any `node` process.
4. NEVER kill, restart, renice, or signal any existing process: rl.train
   lanes, ch5_100m_wave.sh, caffeinate, node, samplers, tails. No broad
   `pkill`/`killall` ever.
5. NO checkpoint evaluation of ANY kind — any n, any opponent, any
   checkpoint, including old fleets' — until the fleet ends (pre-reg peeking
   bar). No training runs, no throughput benchmarks.
6. CPU/memory politeness: the 3 lanes own the box and the run's throughput
   record is being accumulated. Run only targeted single-file pytest, always
   under `nice -n 19`, never the full suite, never `pytest -n`. Full-suite
   verification is deferred to post-fleet; say so in your log rather than
   running it.
7. Do not read or write `runs/`, `logs/`, or run `scripts/extract_history.py`
   against live run dirs (the babysitter session owns those reads).
8. Git: commit freely ON YOUR BRANCH in the worktree. NEVER push, NEVER
   merge to main, NEVER commit on main. Merging happens only after the 100M
   readout is recorded, gated on the bit-identity pins.

## SETUP

    cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
    git worktree add ../pokemon-showdown-rl-audit -b audit-fixes
    cd ../pokemon-showdown-rl-audit
    cp ~/Downloads/AUDIT_ACTION_PLAN.md docs/AUDIT_ACTION_PLAN.md

First commit: the plan doc (it's currently unversioned provenance for ~20
verified findings). Then verify import isolation before ANY test run:
`python -c "import rl; print(rl.__file__)"` from the worktree root MUST print
the worktree path (cwd shadows the editable install); if it prints the main
tree, fix resolution (PYTHONPATH=. ) before proceeding — a test importing the
main tree would be testing the wrong code AND touching the live tree's
bytecode caches. Use the `pokemon-showdown-rl` conda env's python directly
(/opt/anaconda3/envs/pokemon-showdown-rl/bin/python), never base.

Read in the worktree: CLAUDE.md (binding), docs/AUDIT_ACTION_PLAN.md (your
work order), docs/landmines.md sections for anything you touch. STATUS.md/
HANDOFF.md are context only — the fleet is the other session's job.

## THE WORK — docs/AUDIT_ACTION_PLAN.md §5 order

1. F-01: AgentOpponent snapshots only the nets (~4 GB/lane prize); add the
   size regression test.
2. F-02+F-03+F-09: async collector testability — injectable players, unit
   tests for episode bookkeeping, in-loop liveness timeout that turns a
   silent stall into a resumable crash, `len(self._ended)` fix. The live
   pause/resume test that needs a real server: WRITE it, mark it
   server-required, leave it deselected.
3. F-05: pool state into checkpoint.pt extras (one atomic payload), own save
   cadence, stamp+assert the pair on resume. Keep backward compat with
   existing run dirs (fallback to pool.pt) — the live fleet's dirs must
   remain resumable by OLD code.
4. F-04: minibatch trailing-slice policy (drop/fold below mbs//2) + test on
   async-shaped sizes. Numerics move → implement behind the plan's
   non-lever-wire-change framing and draft its pre-reg paragraph for the
   maintainer; it must not become default behavior without that ruling.
5. F-08: the EncoderSpec per-gen seam (the gen-4 blocker). Gen-1 828-dim
   encoding stays BIT-IDENTICAL — regression-test against stored tapes
   before/after. Do not change OBS_DIM. The format-derived action space can
   ride along (gen-9 need).
6. Ride-alongs as time permits: F-10 (vectorized GAE with equality pin),
   F-13, F-14, F-16, F-18, F-19 counter, F-20 refactors LAST (they conflict
   with everything else — do them after the findings land, or skip).

DRAFT-ONLY (maintainer rulings needed, do not land as behavior changes):
F-06 (in-loop eval budget — next-prereg proposal), F-07's config-block form
(exceeds the ruled CLEANUP A2 pure-default-flip). Write these as proposal
docs on the branch.

## QUALITY BARS

- Small single-purpose commits, one finding per commit where possible, each
  naming its finding id (F-NN).
- Every behavior-adjacent change keeps the existing R0-3b bit-identity tests
  and masking/PPO invariant tests green (targeted runs, nice'd).
- Keep a branch log at docs/AUDIT_BRANCH_LOG.md: per finding — what changed,
  tests run (exact invocations), tests deferred to post-fleet, open
  questions for the maintainer. This gets folded into SESSION_LOGS at merge
  time; do not touch SESSION_LOGS/STATUS/HANDOFF themselves.
- Pin exact versions for any proposed dependency; name anything borrowed.
- End state: worktree clean, branch committed, log current. Do not push.

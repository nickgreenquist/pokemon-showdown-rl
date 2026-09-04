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
        nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python -m pytest -q \
        -p no:cacheprovider -p noserver_plugin -m "not live_server" tests/<file>.py

  Torch threads are deliberately left at the box default (10): the wrapper first
  pinned `OMP_NUM_THREADS=1`, which is what exposed F-22 (below), and the repo's
  goldens were captured at default threading. The wrapper also holds a
  machine-wide semaphore (at most 3 concurrent pytest processes, `mkdir`-atomic
  slots in the scratchpad) so any number of agents cannot stack test load on the
  fleet's box; callers wait for a slot.

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

Branch @ `59efa21` = 42 commits over `main`@60c1225; every per-finding branch
was rebased onto `audit-fixes` and fast-forwarded (linear history, no merge commits).
The plan's F-11 (encoder vectorization; needs a profile number), F-12 (per-episode W&B
volume), F-15 (turn feature; an OBS_DIM change), F-17 (MPS generator; standing ruling)
and F-20 (module splits) were NOT attempted — F-20 by the plan's own "do them last or
skip", the others because each needs a measurement or a ruling this branch could not take.

### F-01 — pool snapshots hold only the nets

Commits (newest first):
- `d546228` F-01: AgentOpponent snapshots only the nets (drops the ~205 MB rollout buffer + Adam moments per member)

**What changed** (implementer's account, abridged): AgentOpponent.__init__ no longer deep-copies the whole PPOAgent. It now does one copy.deepcopy over the (actor, critic) pair and stores them with agent.device in a tiny __slots__ holder class `_MemberNets` (rl/selfplay/pool.py), preserving the `.agent.actor / .agent.critic / .agent.device` surface; __slots__ closes the surface so a buffer/optimizer cannot ride along again. No PPOAgent.__deepcopy__ was defined. SnapshotPool.load_state_dict keeps the `AgentOpponent(agent_factory(), ...)` contract (factory agent is transient; only its nets are copied) and its docstring says so. Module docstring's stale "~2/3 of the ~1 MB per snapshot ... accepted waste" sentence replaced with the batch-recipe arithmetic (2 x 3840 x 8 x 828 x 4 B = 203.5 MB buffer + ~9.4 MB Adam moments per member, ~4.1 GB/lane at pool_size 20 on sync and on every async --resume; a member now costs ~4.5 MB of weights, matchi…

Tests run through the wrapper (last result per file):
- `tests/test_frozen_opponent.py` → 2 passed in 2.41s
- `tests/test_pool_pertag.py` → 6 passed in 0.64s
- `tests/test_resume.py` → 5 passed in 1.61s
- `tests/test_selfplay_harness.py` → 31 passed in 2.46s
- `tests/test_selfplay_pool.py` → 21 passed in 1.57s (re-run after the final docstring-only edit: 21 passed in 1.21s)

Bit-identity claims: move() output on a seeded generator is unchanged: verified by a one-off script (nice -n 19, worktree PYTHONPATH) that reconstructed the pre-fix path (copy.deepcopy(agent) + identical freeze/move bodies) and compared 300 draws for generator seeds 0, 5, 11 on th… ¶ Pool state_dict format unchanged: top-level keys remain exactly {pool_size, latest_prob, pushes, push_ids, stats, members}; per-member keys remain exactly {actor, critic, generator} (asserted in the one-off script); torch.save/torch.load(weights_only=False) ro… ¶ Learner untouched: the fix only changes what the MEMBER holds; the learner's actor/critic/buffer/optimizer are read, never written (test_snapshot_shares_no_storage_with_the_learner and test_push_freezes_the_snapshot_and_leaves_the_learner_trainable pass unchan… ¶ Module sharing preserved: one deepcopy call over the (actor, critic) tuple keeps any module shared between the two nets shared in the copy, as the whole-agent deepcopy's memo did (ppo.py:377 confirms they share none today, so this is defensive only).

Open questions for the maintainer:
- docs/landmines.md cites `rl/selfplay/pool.py:88` for the torch.multinomial generator/MPS defect; that line is now pool.py:123 (the module docstring grew). I did not edit docs; the citation should be refreshed when the docs are next touched (AUDIT_ACTION_PLAN §3 F-01 cites pool.py:74/134/237-238, now…
- The holder is a tiny __slots__ class `_MemberNets` rather than types.SimpleNamespace (both were permitted): __slots__ makes 'a member keeps only its nets' enforceable (the new test pins that member.agent.buffer = ... raises). If the maintainer prefers SimpleNamespace for zero surface area, the swap…
- rl/networks/mlp.py:22 still says PrefixSliceActor 'composes with AgentOpponent's deepcopy/freeze' — still true (the actor, wrapped or not, is what gets deep-copied), so left alone.
- The step-0 push in rl/train.py:429 still happens before _async_loop sets agent.buffer = None; with this fix that ordering no longer matters for memory, so no train.py change was made.

### F-02 / F-03 / F-09 / F-19 — async collector: testability, liveness, stats race, re-request counter

Commits (newest first):
- `b00a16f` F-02: review fixes — the settle test gets a handshake so it stops being vacuous
- `c78c0f9` F-02: review fixes — settle the last finish callback before the live test's final poll
- `98009e7` F-02: review fixes — the gated-progress test now discriminates, F-09 gets a pin, the live test loses two races
- `98aaa02` F-02: live pause/resume contract test (server-required, deselected)
- `f8ca6f7` F-19: count `[Invalid choice]` re-requests as collect/rerequests
- `b4aba9b` F-03: in-loop liveness budget turns a silent stall into a resumable crash
- `f1cf9b3` F-02: offline construction seam + unit tests for the async collector
- `4f089f5` F-09: stats() reads len(self._ended) instead of iterating the deque

**What changed** (implementer's account, abridged): All five reviewer issues addressed; every fix is in tests/test_showdown_async.py and rl/envs/showdown_async.py is byte-identical to f490b7c (production semantics were judged correct).\n\n(1) test_a_gated_request_does_not_count_as_progress rewritten so it actually discriminates. The reviewer was right that the frozen clock made construction, pause(), resume() and the completing request all stamp 1000.0, so `_last_progress >= resumed_at` held wherever _mark_progress() sat. The clock now moves at two distinct instants: it advances 100 s BEFORE the coroutine is scheduled (an entry-time mark then stamps 1100 against a parked expectation of 1000), and the gate is opened DIRECTLY via POKE_LOOP.call_soon_threadsafe(seam.gate.set) at 1200 rather than via resume() — resume() marks progress itself, so bypassing it leaves the completion as the only remaining writer and a deleted mark leaves 1000. re…

**Review-fix rounds:** One reviewer issue this round (round-1 issue (1), half-closed), and I applied the reviewer's own suggested fix — the diagnosis holds exactly as written.\n\nThe race: in the live contract test, `ended()` = episodes_finished + episodes_discarded, and `_finish` bumps `episodes_finished` (/Users/nickgreenquist/Documents/Pr… ¶ One reviewer issue this round, and the reviewer is right in every detail — I reproduced their measurement independently before applying their suggested fix, then applied it as written. The defect: test_pause_returns_only_once_in_flight_decisions_have_settled (tests/test_showdown_async.py) was the branch's headline OFFL…

Tests run through the wrapper (last result per file):
- `MUTATION 1 (F-09 pin): stats() reverted to len([t for t, _ in self._ended]), then <wrapper> tests/test_showdown_async.py -k stats` → 1 failed, 1 passed, 30 deselected — test_stats_never_iterates_the_ended_deque FAILED with…
- `MUTATION 2 (_mark_progress moved above the gate wait in CollectPlayer.choose_move), then <wrapper> tests/test_showdown_async.py -k 'gated or completed_request'` → 1 failed, 1 passed, 30 deselected — test_a_gated_request_does_not_count_as_progress FAILED…
- `MUTATION 3 (_mark_progress deleted from choose_move), then <wrapper> tests/test_showdown_async.py -k 'gated or completed_request'` → 2 failed, 30 deselected — test_a_gated_request_does_not_count_as_progress FAILED at 'the m…
- `OFFLINE DISCRIMINATION HARNESS (not a suite test, not committed): cd worktree && PYTHONPATH=worktree nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python /private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/98e8306c-cd54-4f08-82e5-f3472f1a2b0e/scratchpad/settle_discrimination.py` → pristine + handshake: PASS 6/6, all trials settled/requests/rows/calls = (4,4,4,4). mutant…
- `OFFLINE RACE DEMO (not a suite test, not committed): nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python <scratchpad>/settle_race_sim.py, from cwd=the worktree with PYTHONPATH=the worktree` → WITHOUT settle wait [(False, False)] x5 -> ASSERTION WOULD FAIL; WITH settle wait [(True,…
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && <wrapper> tests/test_async_launch.py` → 12 passed in 0.43s
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && <wrapper> tests/test_pool_pertag.py` → 6 passed in 0.48s
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && <wrapper> tests/test_showdown_env.py` → 54 passed, 3 deselected in 0.73s
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && for i in 1 2 3 4 5; do <wrapper> tests/test_showdown_async.py -q -k pause; done` → 2 passed, 5 times out of 5
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && for i in 1 2 3; do <wrapper> tests/test_showdown_async.py; done` → 31 passed, 1 deselected in 0.97s / 0.98s / 0.97s
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F02 && nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python -m py_compile tests/test_showdown_async.py` → COMPILE_OK
- `tests/test_async_launch.py` → 12 passed in 0.40s
- `tests/test_pool_pertag.py` → 6 passed in 0.43s
- `tests/test_showdown_async.py` → 31 passed, 1 deselected in 0.97s (run again after the final comment edit: 31 passed, 1 des…
- `tests/test_showdown_env.py` → 54 passed, 3 deselected in 0.70s

Bit-identity claims: rl/envs/showdown_async.py is unchanged by this commit. Verified two ways: (a) md5 -q before the mutation experiments and after the final restore are both ffbb8ef32da58d74f3d230dfc9256261; (b) `git diff f490b7c..HEAD -- rl/ configs/ scripts/` outputs 0 lines. ¶ No production code at all changed: `git diff --stat f490b7c..HEAD` lists only tests/test_showdown_async.py (78 insertions, 13 deletions). ¶ No default moved. _LIVENESS_S is still 900.0, _ROOM_GRACE_S 300.0, _BUILDER_MAX_AGE_S 3600.0, AsyncCollector(liveness_s=_LIVENESS_S) — all still pinned by the untouched test_liveness_budget_default_and_override, which passes. ¶ The masking contract and locked metric names are untouched: the new test asserts only the existing collect/rooms_tracked key, and test_stats_keys_and_values (unchanged) still pins the exact seven-key collect/* dict.

Open questions for the maintainer:
- The reviewer's own suggested_fix for the gated-progress test would NOT have worked, and should not be re-applied. Quoted claim: 'After scheduling the coroutine and confirming it is parked (the TimeoutError), advance the clock while parked — e.g. `t0 = col._last_progress; clock(100.0); assert col._la…
- I went one step past issue (4)'s scope: with wait_until now tolerating a clean drive end, the final `wait_until(lambda: ended() == 4, 300, ...)` no longer passes check=False, so a real stream death in that 300 s window fails with its own cause instead of a timeout. This is a behaviour change to a te…
- Whether test_async_pause_resume_live_contract should be run at all before FLEET DONE is a maintainer call — it logs in as as2s990001a/b and plays four rated-free battles against SimpleHeuristicsPlayer on the same server the fleet is using. My bars forbade it; it is the only unexercised code in this…
- The reviewer's suggested_fix was right and applied verbatim in substance; the only correction is bookkeeping. Quoted claim: "`_finish` increments `episodes_finished` (showdown_async.py:337) BEFORE `self._finished.append(episode)` (:338), `self._ended.append(...)` (:342), `self._prune()` (:343)". In…
- Round-1's two live-test fixes and this one are all unexercised for the same reason, and they now stack: three separate concurrency changes to test_async_pause_resume_live_contract have been reviewed by reading and (this one) by an offline ordering demo, but never run against a server. Recommend the…
- Still open from round 1 and unchanged by this commit: the final wait now keeps check() ON (round-1 issue (4) went one line past its minimal scope). If a reviewer prefers the minimal patch there, dropping check for that wait restores the old semantics without touching either race fix. My view is that…

### F-04 — opt-in minibatch tail policy (default `keep`, bit-identical) + draft pre-reg

Commits (newest first):
- `59efa21` F-04: review fixes — fold gate covers the 2-row floor at narrow widths; default path pinned end-to-end at the 100M shape
- `25c3dd3` F-04: review fixes — vendor the pre-F-04 baseline so the bit-identity pin cannot silently stop pinning
- `65e7c82` F-04: review fixes — a real bit-identity pin, the production shape, an operationally pinned T arm
- `3cf8ffa` F-04: draft pre-reg paragraph for the minibatch tail policy (proposal, unruled)
- `62d967b` F-04: opt-in minibatch tail policy (keep|drop|fold); default keep is bit-identical

**What changed** (implementer's account, abridged): Implemented F-04 as an OPT-IN wire change. rl/agents/ppo.py: new module-level `MINIBATCH_TAILS = ("keep","drop","fold")` and pure helper `_minibatch_slices(batch_size, minibatch_size, tail) -> (slices, min_rows)`; new `PPOAgent(..., minibatch_tail: str = "keep")` kwarg (appended last in the signature), validated at construction with ValueError, stored as `self.minibatch_tail`; `_optimize`'s epoch loop now iterates the plan's (start, stop) slices with a per-policy row floor (`keep`: floor 2 = today's `< 2` skip; `drop`: floor max(2, mbs//2); `fold`: a tail under mbs//2 merged into the previous slice, floor 2). Two update-level diagnostics `loss/minibatch_rows_min` and `loss/minibatch_rows_dropped` (rows dropped per epoch) are returned ONLY when minibatch_tail != "keep", following the l2_init_decay/bc_kl_coef "default adds no metric key" precedent (tests/test_ppo.py:189, test_l2_init.py:11…

**Review-fix rounds:** All three reviewer issues fixed in one commit (43e0d38); the prior agent's uncommitted partial fix was read critically, kept where it was right, and replaced where it was not. (1) TAUTOLOGY (should_fix) — the reviewer was right: the old test compared PPOAgent() against PPOAgent(minibatch_tail="keep"), both the new loop… ¶ The single round-2 issue is fixed in commit 58bb269. The reviewer was right and the diagnosis was exact: `_pre_f04_ppo()` resolved the abbreviated sha `5d3c6b7` out of the object store and mapped every git failure to `pytest.skip`, so a squash-merge/rebase (object gc'd), an abbreviation that stopped being unique, or a…

Tests run through the wrapper (last result per file):
- `PROBE (five loss/fake modes must FAIL, not skip): <scratchpad>/f04r2/probe_negatives.py and <scratchpad>/f04r2/probe_worstcase.py, same interpreter/PYTHONPATH/nice` → M1 fixture absent -> Failed (pytest.fail); M2 fixture edited by one char -> AssertionError…
- `PROBE (gc'd-commit future, not a shipped state): PYTHONPATH=<worktree> nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python <scratchpad>/f04r2/probe_gcd.py — imports tests.test_ppo_episodes, sets _PRE_F04_COMMIT to 40 zeros, clears the lru_cache, then calls the baseline test and the pin at all five tails` → source loaded without git: 72448 chars / baseline test: PASS / pin ran at every tail with…
- `tests/test_async_launch.py` → 12 passed in 0.59s
- `tests/test_async_launch.py -rs` → 12 passed in 0.41s
- `tests/test_l2_init.py` → 14 passed in 3.02s
- `tests/test_l2_init.py -rs` → 14 passed in 1.66s
- `tests/test_masking.py` → 11 passed in 1.19s
- `tests/test_masking.py -rs` → 11 passed in 0.79s
- `tests/test_ppo.py` → 25 passed, 1 warning in 1.72s
- `tests/test_ppo.py -rs` → 25 passed, 1 warning in 0.91s
- `tests/test_ppo_episodes.py` → 29 passed in 1.66s
- `tests/test_ppo_episodes.py -q -k 'pre_f04_agent or default_is_keep' -x` → each mutation FAILED the new pin: M1 (keep floor 2->3) -> ...pre_f04_agent[2] at line 306;…
- `tests/test_ppo_episodes.py -rs` → 43 passed in 1.49s
- `tests/test_zeroinfo.py` → 3 passed, 9 skipped in 2.40s
- `tests/test_zeroinfo.py -rs` → 3 passed, 9 skipped in 1.50s

Bit-identity claims: Default (minibatch_tail absent) == 'keep' == pre-F-04 behaviour, bit-for-bit, on both the async and vector paths. HOW VERIFIED: (a) by construction — `_minibatch_slices(..., 'keep')` returns [(start, min(start+mbs, B)) for start in range(0, B, mbs)] with floor… ¶ Default emits NO new metric key: `loss/minibatch_rows_min` and `loss/minibatch_rows_dropped` appear only when minibatch_tail != 'keep'. VERIFIED by the unchanged `set(metrics) == {...}` assertions in test_ppo.py:189, test_l2_init.py:115/386 and test_ppo_episod… ¶ Constructor RNG/ordering untouched: the new validation is pure Python placed after `self.max_grad_norm`, before any net is built, so actor/critic init and every dedicated generator derivation are unchanged (the identity test's construction-from-seed equality c… ¶ rl/ is byte-for-byte unchanged by this commit. VERIFIED: `git diff --stat 650a8e6 HEAD -- rl/` is empty; `git show --stat HEAD` lists only tests/test_ppo_episodes.py and docs/proposals/F04_minibatch_tail_prereg.md.

Open questions for the maintainer:
- Ruling 1: adopt `fold`, `drop`, or neither? The draft proposes `fold` (keeps every row per epoch); default remains `keep` until ruled.
- Ruling 2: routing — disclose-and-adopt with no fleet (as N-TIMER was handled), ride-along on the next acceptance-shaped fleet, or a standalone 3x12M fleet (~17.4 lane-hours, >5 h/lane so maintainer-launched)? The audit recommends 1 or 2.
- Ruling 3: if a fleet runs — seeds 66/75/83 as a THIRD legal owner (needs a one-line amendment to tests/test_ch5_r2_prereg.py::test_seeds_are_window_disjoint_and_unused) for a paired read against the banked G9 acceptance finals, or fresh seeds 152/160/168 with pairing lost and disclosed? I could not…
- Ruling 4: add a `loss/grad_steps` diagnostic under the same non-default gating so the dose paragraph's 'how we would know' is logged rather than derived?
- The draft's journey_step is NOT ASSIGNED (off-arc); JOURNEY steps 8 and 10 are quoted as candidate homes and the chosen step's exit condition must be restated verbatim on ratification.
- Design choice to confirm: I placed the diagnostics under `loss/` (locked namespace, per the brief) and gated them off on the default to honour the repo's 'default adds no metric key' precedent; if the maintainer would rather see `loss/minibatch_rows_min` on every run (including `keep`) that is a one…

### F-05 / F-18 / F-13 / F-16 — one atomic resume payload, RNG state, provenance keys, realized sps

Commits (newest first):
- `e44db32` F-05: review fixes — the legacy fixture now builds the shape that is actually on disk
- `9f4209b` F-18: review fixes — pin the restore's CALL SITE at loop entry, not just its payload
- `c11da91` F-16: log time/realized_steps_per_sec at every update boundary, both loops
- `eb1da7b` F-13: stamp git_dirty_tracked and untracked_files beside git_dirty
- `6ba5da3` F-18: checkpoint the three global RNG streams, restore them on resume
- `373ec07` F-05: one atomic resume payload (pool inside checkpoint.pt, stamped) on its own 4-update cadence

**What changed** (implementer's account, abridged): F-05 was already committed on the branch (61f2441, not mine). I audited it line by line against the brief and it meets (a)-(d) as written, so it got NO review-fix commit: extras carry {"loop", "pool":{step,state}} in one write-then-rename; the async pool read stays fenced through collector.run_in_loop with the load-bearing reason spelled out in both the closure and the shared helper's docstring; no site writes pool.pt any more (grep-verified across .py/.sh/.yaml — nothing outside docs and tests references it, and no script depends on its existence); the loader prefers ckpt["pool"], asserts the step stamp, falls back to pool.pt with the exact disclosure text, else reseeds with the old text, and records pool_source in the meta stamp; the stamp is built before _restore_pool so a refused pair leaves meta.yaml untouched; SAVE_LATEST_EVERY_UPDATES = 4 is a module constant (no Config field — th…

**Review-fix rounds:** Round 2 addressed both should_fix issues; both were correct as written, so both were fixed rather than disputed, and each fix was then MUTATION-VERIFIED to be a real pin. No production code changed in round 2 — `git diff --name-only 4412a5f..HEAD` is `tests/test_resume.py` alone, and rl/train.py's sha256 is byte-identi…

Tests run through the wrapper (last result per file):
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-TRAIN && PYTHONPATH=<worktree> nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python - (heredoc): np.random.seed(0); st=get_state(); 5000 draws; compare st[1] to its pre-draw copy` → np.random.get_state() returns a COPY: True
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-TRAIN && PYTHONPATH=<worktree> nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python - (heredoc, ~10 lines): set_seed(99); baseline draws; set_seed(99); 50 x rl.train._rng_state(); draws again` → torch stream unmoved by _rng_state: True / numpy stream unmoved: True / python stream unmo…
- `tests/test_async_launch.py` → 12 passed in 0.39s
- `tests/test_l2_init.py` → 14 passed in 1.63s
- `tests/test_loop_timers.py` → 2 passed in 1.62s
- `tests/test_resume.py` → 11 passed in 1.40s
- `tests/test_resume.py  [MUTATION A: _restore_rng hoisted above _restore_pool, removed from its own block]` → 1 failed, 10 passed in 1.53s — FAILED test_resume_restores_the_rng_state: AssertionError:…
- `tests/test_resume.py  [MUTATION B: torch.rand(1) between _ensure_theta0 and make_logger]` → 1 failed, 10 passed in 1.60s — FAILED test_legacy_pool_pt_run_dir_resumes_with_disclosure:…
- `tests/test_run_capture.py` → 5 passed in 1.33s
- `tests/test_selfplay_harness.py` → 31 passed in 1.57s

Bit-identity claims: FRESH (non-resume) run numerics unchanged by F-18. The only new code on that path is extras["rng"] = _rng_state(), i.e. torch.get_rng_state() / np.random.get_state() / random.getstate(). VERIFIED by probe: set_seed(99), 50 consecutive _rng_state() calls, then… ¶ FRESH run numerics unchanged by F-16. VERIFIED by reading `git diff` for the commit: the only additions are one time.perf_counter() read per update boundary, two new locals, and one additive key in an existing logger.log dict on each loop. The `sps = (step - l… ¶ FRESH run numerics unchanged by F-13. The addition is one extra `git status --porcelain --untracked-files=no` subprocess plus two additive meta.yaml keys, all inside _write_run_metadata, which runs before the loop and touches no RNG. git_dirty is still bool(`g… ¶ LEGACY resume (the live 100M fleet's format: checkpoint.pt with no pool key beside pool.pt) resumes exactly as before F-05, streams included. F-05 moved the pool rebuild earlier in train(), but VERIFIED by reading the two functions it moved across — _ensure_th…

Open questions for the maintainer:
- F-05's torn-stamp refusal is an `assert`, so it vanishes under `python -O`. Consistent with the two resume asserts already there (config drift, vectorized-only), so I left it — flagging in case the audit wants the pool/checkpoint pair check raised as a ValueError instead.
- F-05 write volume: with the pool inside checkpoint.pt the payload is ~104 MB at the batch recipe (13.8 MB learner + ~90 MB pool, per the plan's own figures), now written every 4 updates (~3.6 min at 574 steps/s) instead of every 250k steps (~7 min) — roughly 2x the write traffic, ~0.5 MB/s. Fine on…
- F-05/F-06 interaction, documented in code but worth a ruling: with the eval-block save gone, best_eval reaches the payload only at the next boundary save, so a kill inside that window resumes with a best_eval up to one eval stale and best_checkpoint.pt may be rewritten once by a lower draw. Descript…
- F-18 residual scope, named in _rng_state's docstring and NOT fixed: PPO's _shuffle_gen / _synth_gen are re-derived from torch.initial_seed() at construction, so their consumed draws replay on a resume (both levers are off in every frozen config), and gymnasium reseeds each sub-env from cfg.seed at e…
- time/realized_steps_per_sec is a new time/* key. CLAUDE.md's locked metric list names time/steps_per_sec, collect_sec, update_sec, eval_sec explicitly; I did not edit CLAUDE.md (bar 6), so someone needs to add the new key to that list — and decide whether extract_history.py / the graders should read…
- docs/AUDIT_BRANCH_LOG.md has no entry for these three commits (bar 6 forbids editing it). F-05's entry may also be missing — 61f2441 predates my session.

### F-08 — EncoderSpec per-gen seam, gen-1 hash-pinned bit-identical; format-derived action space

Commits (newest first):
- `6007c1a` F-08: review fixes — pin the five other spec-threaded helpers and the whole ENCODER_FINGERPRINT
- `61ed5eb` F-08: review fixes — Reflect/Light Screen are gen-2 side conditions, terrain is gen 6
- `4024230` F-08: derive the faked Showdown spaces from the format (Discrete(10) sites)
- `f616498` F-08: EncoderSpec — per-gen encoder tables behind a format-selected seam; gen-1 bit-identical (hash-pinned on tapes)

**What changed** (implementer's account, abridged): RESUMED the draft, which was already structurally right and already bit-identical on the three oracle combos; I reviewed it against the brief, made four substantive corrections, added one test, and split it into two commits. WHAT THE DRAFT HAD RIGHT (kept): rl/envs/encoder_spec.py's frozen EncoderSpec with every per-gen table plus the derived *_off/*_dim_v1 layout properties and n_actions via SinglesEnv.get_action_space_size; GEN1 carrying today's tables in today's order; spec_for_format keyed on GenData.from_format(fmt).gen with a NotImplementedError that names the missing pieces; the gen-4 work list in the class docstring (incl. "per-move physical/special is already poke-env's move.category"); the spec threaded through _fill_mon/_fill_active/_fill_move/embed_battle/_fill_ids/_species_id/_move_id/_move_slots_aliased; every module-level name kept at GEN1's identical values; N_ACTIONS; fa…

**Review-fix rounds:** All three review issues ADDRESSED (none disputed), in two new commits on top of the round-1 pair. 41d1c96 = the seam's contract text; a4c88ec = the two coverage gaps. No production code path changed in round 2: rl/ saw comments plus one refusal-message string, everything else is tests — the three oracle hashes still ma…

Tests run through the wrapper (last result per file):
- `<wrapper> tests/test_async_launch.py` → 12 passed in 0.40s
- `<wrapper> tests/test_ch3_bridge.py` → 18 passed in 0.97s
- `<wrapper> tests/test_collect.py` → 7 passed, 2 deselected in 0.46s
- `<wrapper> tests/test_encoder_ids_tapes.py` → 1 passed in 2.25s
- `<wrapper> tests/test_encoder_v2.py` → 2 passed in 1.11s
- `<wrapper> tests/test_entity_deepsets.py` → 5 passed in 1.72s
- `<wrapper> tests/test_eval_shim.py` → 3 passed in 2.45s
- `<wrapper> tests/test_frozen_opponent.py` → 2 passed in 1.35s
- `<wrapper> tests/test_mask_desync.py` → 8 passed in 0.42s
- `<wrapper> tests/test_opp_action.py` → 19 passed in 2.16s
- `<wrapper> tests/test_privileged_block.py` → 4 passed, 1 deselected in 0.95s
- `<wrapper> tests/test_run_capture.py` → 4 passed in 1.31s
- `<wrapper> tests/test_showdown_env.py` → 54 passed, 3 deselected in 0.69s
- `tests/test_encoder_spec.py` → 23 passed in 13.09s

Bit-identity claims: ENCODING, 5 FLAG COMBINATIONS, base d546228 vs HEAD 13962ea — identical. Method: the brief's scratchpad script (6 tapes, 6000 rqid-aligned decisions, sha256 over every embed_battle(...).tobytes()), run from cwd=worktree with PYTHONPATH=worktree under nice -n 1… ¶ I DID NOT TRUST THE ORACLE BLIND — I re-derived it. `git show d546228:rl/envs/showdown.py` into a scratch package tree (a copy of rl/ with encoder_spec.py deleted), imported via PYTHONPATH with sys.path[0] = the scratchpad (verified: rl.envs.showdown.__file__… ¶ FOURTH FLAG, NOT IN THE BRIEF'S ORACLE. POKEMON_RL_NO_SET_PRIOR changes obs SEMANTICS at constant OBS_DIM, so 'bit-identical at every flag combination' needed it. Captured base vs HEAD both ways: bare+NO_SET_PRIOR 612/8c2956c4bde8eb89d30c17391b4a86e44aa8e81ea0… ¶ MODULE CONSTANTS. Dumped every module-level non-callable name of rl.envs.showdown with its repr (plus the sorted callable/class list) for base and HEAD at three flag combos and diffed. The ONLY differences: the five intended new names (EncoderSpec, GEN1, spec_…

Open questions for the maintainer:
- The three sites the finding names are converted, but `gym.spaces.Discrete(10)` literals remain in analysis/eval scripts NOT listed in F-08 (scripts/ch3_eval.py:577, scripts/ch3_fidelity_check.py:896, scripts/ch3_r1_spike.py:50, scripts/foulplay_vs_sh.py:159, scripts/d22_weight_norms.py:141, scripts/…
- rl/networks/entity_deepsets.py's privileged-critic check has a literal `+ 10` in its expected width — that 10 is PRIV_ID_DIM (the id block), NOT the action count. I left it; flagging it so a future reader does not 'fix' it into N_ACTIONS.
- rl/networks/opp_action.py's L6 head over 4 move slots (named in the finding's Location line) is untouched: it is a per-move-slot head, not an action-space size, and nothing in the brief asked for it. It will need its own pass at gen 6+ where 4 move slots stop meaning 4 move actions.
- Constructing an EntityDeepSetsNet now imports rl.envs.showdown for N_ACTIONS. Its own tokenizer already did this one line later, so there is no new dependency in practice — but if a future refactor makes the tokenizer torch-only, this import becomes the trunk's only poke_env dependency.
- F-07 (encoder flags into Config) is adjacent and untouched, as the plan's re-verification requires its own maintainer ruling; the new seam does not change that, and spec_for_format deliberately says nothing about the v2/ids flags (they are process-level, not per-gen).
- The `fake_spaces` parameter is named `battle_format` (poke-env's own kwarg name), not the brief's shorthand `fmt`; it also takes an `obs_dim` override the brief did not specify, which is what eval_checkpoint's cross-encoder shim needs. Say the word if you want either renamed.

### F-10 / F-14 — vectorized per-episode GAE; matrix.py exception guard

Commits (newest first):
- `c0a83dc` F-10: review fixes — give the F-14 tests power, pin F-10's one behaviour change
- `5934e07` F-10: review fixes — matrix.py guard keeps catching poke-engine panics, re-raises interrupts only
- `59dbafb` F-14: matrix.py catches Exception, not BaseException
- `e9bae05` F-10: vectorized per-episode GAE (scan over Lmax, not B) with an equality pin against the (T,N) kernel

**What changed** (implementer's account, abridged): F-10: rl/buffers/episode.py episode_gae now lays the flat batch out as (Lmax, E) — one RIGHT-aligned column per episode (terminal row on the last scan row), zero padding above short episodes, gathered back in flat order — and calls the UNCHANGED (T, N) compute_gae kernel over it, so the kernel's Python reverse loop runs Lmax times (longest episode) instead of B (~30k) with E-wide ops. Signature episode_gae(rewards, values, lengths, gamma, lam) -> (B,) and float32 dtype preserved; the per-row terminated/next_values construction was factored into a shared private helper _episode_boundaries; the old (B,1) column reduction is kept verbatim in math as _episode_gae_reference (training never calls it; ppo.py untouched). No dependency added. New test test_episode_gae_is_bit_identical_to_the_column_reduction pins np.array_equal AND a bitwise int32 view against the reference on: one episode of len…

**Review-fix rounds:** Both should_fix items (correctness + compliance lenses) concern the same defect and were accepted: 1a2e62e's `except Exception` in rl/search/matrix.py solve_decision no longer caught poke-engine Rust panics. Verified in this env under nice with the worktree PYTHONPATH: `poke_engine.State.from_string("garbage")` raises… ¶ All three should_fix issues addressed in one commit (ca00928); no production code touched. (1) The panic test was vacuous, as the reviewer showed: I reproduced it — on _two_mon_battle() real dmg, a None stub and the panicking stub all give action 1 / leaves 99 / expanded 0 / identical row_ev. It now runs on a new _stra…

Tests run through the wrapper (last result per file):
- `cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-audit-F10 && PYTHONPATH=<worktree> PYTHONDONTWRITEBYTECODE=1 nice -n 19 /opt/anaconda3/envs/pokemon-showdown-rl/bin/python -c '<one-off: 900 episodes, lengths 5..60 plus one of 1200, data-path rewards, random float32 values; episode_gae vs _episode_gae_reference under the three (gamma, lam) pairs; compare .view(np.int32)>'` → B = 30700 E = 900 Lmax = 1200 bit_identical = True
- `tests/test_ch3_bridge.py` → 18 passed in 0.95s
- `tests/test_ch3_matrix.py` → 14 passed in 0.72s
- `tests/test_ch3_matrix.py -k interrupt` → 1 failed, 1 passed, 12 deselected — FAILED ...propagates[SystemExit]: DID NOT RAISE System…
- `tests/test_ch3_matrix.py -k panic` → before the expand_leaf value pin: 1 passed (mutant SURVIVED). After adding the pin: 1 fail…
- `tests/test_ch3_matrix.py -q` → 13 passed
- `tests/test_episode_buffer.py` → 1 failed, 7 passed — only test_episode_gae_does_not_leak_a_nonfinite_value_across_a_bounda…
- `tests/test_episode_buffer.py -q` → 7 passed
- `tests/test_ppo_episodes.py` → 6 passed in 0.68s
- `tests/test_ppo_episodes.py -q` → 6 passed
- `tests/test_rollout.py` → 7 passed in 0.03s
- `tests/test_rollout.py -q` → 7 passed

Bit-identity claims: episode_gae (new (Lmax, E) layout) returns the same float32 bits as the old (B, 1) column reduction for every finite input. Verified: (a) new test asserts np.array_equal AND np.array_equal(got.view(np.int32), want.view(np.int32)) on 5 length patterns x 2 rewar… ¶ compute_gae in rl/buffers/rollout.py is byte-for-byte unchanged (git diff touches only episode.py, matrix.py and the two test files); the sync (T, N) path is unaffected by construction. ¶ Documented NON-identity (only under already-broken inputs): if the critic emitted a NaN/inf value, the old (B, 1) form leaked it backward across an episode boundary via 0.0 * carry (NaN); the column-per-episode layout cannot. Finite inputs — the only ones a he… ¶ F-14 changes behaviour ONLY for BaseException subclasses that are not Exception (KeyboardInterrupt, SystemExit, GeneratorExit): they now propagate instead of yielding dmg = None. Every Exception the guard existed for is handled exactly as before; test_ch3_matr…

Open questions for the maintainer:
- _episode_gae_reference lives in rl/buffers/episode.py (the plan allowed either that or an inline test copy). It is ~15 lines of never-called production-module code kept purely as the pin target; if the maintainer prefers the module free of it, the reference can move into tests/test_episode_buffer.py…
- Padded transient memory: the (Lmax, E) layout allocates 6 float32 arrays of Lmax x E; a batch with one turn-1000-class auto-tie (Lmax ~1,200-2,000) at E ~1,000 is ~30-50 MB transient per update (vs ~100 MB for the batch's own obs). Acceptable in my read, but flagging since the box runs with ~0 free…
- The plan's 0.1-0.3 s/update (1-3% of time/update_sec) F-10 saving is unmeasured on this branch (benchmarks barred while the fleet runs); worth a single before/after profile_collect-style number post-fleet before it is quoted anywhere.
- docs/AUDIT_ACTION_PLAN.md:227 (the F-14 `Fix:` sentence) was edited to the two-clause prescription. The plan is not on the bar-6 forbidden list and the task said 'fix code/tests/docs', but if the orchestrator owns that file, drop the one-line hunk from 5a8990c's doc change — code and test stand on t…
- The correctness reviewer noted generate_instructions on the same (state, a_str, b_str) at rl/search/matrix.py:195 is unguarded, so a panic there already kills the decision today. Pre-existing and pre-branch behaviour, out of this finding's scope, deliberately not changed — flagging so nobody reads t…
- The reviewers asked to amend 1a2e62e's message; bar 5 forbids amend, so the false 'covers every engine fault' claim remains in 1a2e62e's history and is contradicted by 5a8990c's message. If the branch is later squashed for merge, prefer 5a8990c's wording.

### F-06 / F-07 — proposal documents (draft, unruled)

Commits (newest first):
- `ed9d536` F-07: review fixes — physical/special is not one of the :81-168 gen-1 tables
- `56f5dfb` F-06: review fixes — sync-path save citation, split the R2 control pin from the 100M rung
- `f720a0c` F-07: review fixes — correct the import graph in §3.2 Option 1, EncoderSpec grep note
- `a69424c` F-06: review fixes — F-05 cadence arithmetic, extract_history attribution, two citation tightenings
- `f8f21cc` F-06: review fixes — grader read path, disclaimer count, one-diff test mechanism
- `e0645f4` F-07: proposal — encoder config block (draft, unruled)
- `cbf04bc` F-06: proposal — in-loop eval budget (draft, unruled)

**What changed** (implementer's account, abridged): Two draft proposal documents written under docs/proposals/ (new directory), both explicitly DRAFT/UNRULED with RULED / MEASURED / PROPOSED tags and file:line citations re-verified in the worktree at 5d3c6b7. No code, no tests, no config touched. F06_inloop_eval_budget.md (183 lines): (1) today's mechanism at rl/train.py:635-650 (pause at :637, evaluate :639-641, time/eval_sec :642, best_checkpoint.pt on eval/return_mean :646-648, save_latest :649, resume :650; sync twin :915-927; config :535-536/:542/:550); (2) cost with both disagreeing sources — pre-reg's 0.58 h/lane (~5.2 s/eval, 1.2%, :535) vs acceptance fleet-max time/eval_sec 26.18 s (:110, 6.0%) — quoted as 1-6%, 0.6-2.9 h of a 48.4 h lane, plus the timer-exposure (per-pause LENGTH) and resume-window (eval_every IS the resume granularity) costs; (3) consumers: eval/win_rate ruled 'visible, NOT ACTIONABLE' (:292-305), R0-6 existenc…

**Review-fix rounds:** Round-1 fix for the F-06/F-07 DRAFT proposal docs. All three reviewer should_fix items were independently re-verified against the tree and confirmed correct, so all three were applied (no pushback). (1) F06 §3 item 1: the grader's control attest at scripts/ch5_100m_grade.py:246-250 reads the banked R2 finals results/ch… ¶ All three round-1 issues were real and are fixed; I also re-read every file:line citation and every number in both docs against the tree and found two further imprecisions in F-06 and one in F-07, which I fixed in the same commits. ISSUE 1 (F-06 §4 item 1, was line 96-97) — CONFIRMED, fixed. One update = rollout_steps… ¶ All three round-2 issues were real; all three are fixed. No reviewer claim was disputed. ISSUE 1 (F-06 §1 item 1, sync-path citation) — CONFIRMED in the tree. rl/train.py:913 is blank; the sync eval block opens `if step >= next_eval:` at :914. :927 is `save_checkpoint(out_dir / "best_checkpoint.pt", agent, step, cfg, n…

Tests run through the wrapper (last result per file):


Bit-identity claims: Behaviour is bit-identical by construction: the diff 5d3c6b7..HEAD adds only docs/proposals/F06_inloop_eval_budget.md and docs/proposals/F07_encoder_config_block.md — verified with `git -C <worktree> show --stat --format=%h 5d3c6b7..HEAD` (183 and 255 insertio… ¶ Both documents state in their header and body that nothing in them is landed; F-05 decoupling and F-08 EncoderSpec are described as in-progress/planned, verified by `git branch -a` + `git log audit-fixes` (every audit branch at 5d3c6b7) and `grep -rn EncoderSp… ¶ No runtime behaviour touched: the commit changes only docs/proposals/F06_inloop_eval_budget.md and docs/proposals/F07_encoder_config_block.md. No code, config, test, or checkpoint format is altered; the running 100M fleet and configs/showdown_sp_100m.yaml are… ¶ No behaviour can have changed: `git diff --stat 4fbbb05..HEAD` is exactly `docs/proposals/F06_inloop_eval_budget.md | 48 ++-` and `docs/proposals/F07_encoder_config_block.md | 21 +-`, 52 insertions / 17 deletions, both files documentation-only. No file under r…

Open questions for the maintainer:
- F-06: which cadence/n option (A: 1M x 100, B: 250k x 50, C: 1M x 50, or none) for the NEXT pre-reg; A/C require confirming 'F-05 lands first' or accepting a ~1M-step (~29 min) resume window.
- F-06: best_checkpoint.pt on Showdown runs — stop writing it (keyed on env_id; spine tests untouched), rename it (touches tests/test_harness.py:79, test_ppo.py:321, test_run_capture.py:62,120, test_normalize.py:231), or keep it.
- F-06: does the cadence change ride the next pre-reg header as a NON-LEVER WIRE CHANGE (recommended) or need its own pre-reg; and the explicit R0-6 window wording — today R0's per-lane window is 200k (:381) while R0-6's first reading is at 250k and its band is quoted over the first 1M (:398-399).
- F-07: is an `encoder:` config block wanted at all given A2 is ruled and shelved, or does A2-as-ruled suffice for gen 1 with the block deferred to the gen-4 chapter alongside F-08.
- F-07: ordering — block before A2, A2 before block, or A2 subsumed by the block's schema default.
- F-07: Option 1 (config-sets-flags now; needs eval_checkpoint.py:46's top-level import deferred) vs Option 2 only (wait for EncoderSpec, do it once).

## Verification record

- **Review protocol actually applied.** Each branch was implemented by one agent and
  reviewed by independent agents under distinct lenses (correctness / compliance /
  test adequacy; citations for the docs), with fix rounds re-verified. Three separate
  usage-limit cut-offs (2026-09-02/03/04) killed agents mid-flight; every kill was
  recovered from the on-disk worktree state. **The LAST re-verification round did not
  complete for F-02, F-04, F-08, F-05-cluster and F-06/F-07** — their final fix
  commits were verified by the orchestrator only through the test runs below and a
  read of the final diffs where the blast radius is highest (F-05 resume format,
  F-03 liveness, F-04 default path). The maintainer's merge-time review should weight
  those five accordingly.
- **Full suite on the merged branch @ 59efa21** (post-fleet, box idle, guard active so
  the 7 `live_server` tests are deselected, default torch threads, `nice -n 19`):
  **747 passed, 30 skipped, 7 deselected, 3 failed in 28.5 s.** The three failures
  read gitignored on-disk artifacts that exist only in the maintainer's main tree —
  `results/ch5_r1_offsh/a80.json` (`test_ch5_r2_prereg::test_frozen_controls_attest_from_disk`),
  the same attest inside `test_the_grader_selftest_passes`, and
  `results/ch4_r1_offsh/r1_readout.json` (`test_ladder::TestProvenanceLinks`). None
  touches code this branch changed; they will pass in main (the same worktree-only
  class as F-21's baseline failures).
- **Baseline on the branch point** (25 in-scope files, above): all green once F-21/F-22
  were in place. Gains on this branch: +~100 tests (async collector, encoder spec, tail
  policy, resume format, GAE pin, provenance keys).
- **R0-3b / bit-identity pins that stayed green:** `test_entity_deepsets` (R0-3 goldens,
  now thread-safe), `test_l2_init` (R0-3 exact no-op), `test_zeroinfo` (Z1-4),
  `test_selfplay_pool` (distribution bit-identical after the learner moves),
  `test_ppo_episodes` (default `keep` == pre-F-04 loop end-to-end at the 100M shape),
  `test_encoder_spec` (three-combo + two extra encoding hashes on 6000 tape decisions;
  ENCODER_FINGERPRINT pinned), `test_encoder_ids_tapes` (R0-5, EXECUTED here via the
  tape symlink: 1 passed in 2.2 s).
- Pre-change encoding oracle used by F-08 (captured at `d546228`, six tapes, 6000
  rqid-aligned decisions, sha256 over `embed_battle(...).tobytes()`):
  `612:e0217c10dc8678af4fba93adbc5ef76f930e9f5c4b3533d669d22f06328b509d`,
  `808:273cd675b190cb7e4ca2a1253430f92a0474649e96c1da588f805bc97908a13e`,
  `828:0be192a8711def10cff546a12271156e006c982f7a739d16161da34c4d961ef6`.

## Merge notes for the maintainer

1. `main` moved 60c1225 → 9fdf1fa while this branch was worked (100M eval runners,
   readout, STATUS). The delta is new files plus 8 lines in `tests/test_100m_prereg.py`;
   no `rl/` file changed, so `git rebase main` from `audit-fixes` should be clean.
2. Then the bare suite IN MAIN (`pytest tests/`, no encoder env vars, server up so the
   `live_server` tests run — including the NEW `test_async_pause_resume_live_contract`,
   which has never executed) and the R0-3b pins.
3. **Behaviour changes to know about at merge:** (a) F-05 — new run dirs write the pool
   INSIDE `checkpoint.pt` every 4 updates and no longer write `pool.pt`; old dirs still
   resume (legacy fallback prints a disclosure and stamps `pool_source`); (b) F-03 — a
   collector with no decision and no finish for 900 s while un-paused now DIES with a
   traceback (the wave supervisor's resume branch is the intended catcher); (c) F-13 —
   `meta.yaml` gains `git_dirty_tracked` + `untracked_files` (old `git_dirty` unchanged);
   (d) F-16 — `time/realized_steps_per_sec` is logged at update boundaries; (e) F-19 —
   `collect/rerequests` in the collector stats; (f) F-08 — no encoding change (hash-pinned),
   `Discrete(10)` is now derived from the format. Everything else is default-off
   (F-04 `minibatch_tail: keep`) or internal (F-01, F-09, F-10, F-14, F-21, F-22).
4. `docs/landmines.md` line citations into `rl/selfplay/pool.py` (`:88`) and the plan's
   pool.py/showdown.py line numbers have shifted; refresh when those docs are next touched.

## Deferred to post-fleet (status at branch end)

- The full suite was RUN post-fleet on the branch (above). Still deferred to the
  maintainer's main-tree run: the 7 `live_server` tests, and the 3 artifact-reading
  tests that need `results/` and `runs/`.
- Any `profile_collect.py` / throughput number (F-10's speedup and F-11 are unmeasured;
  benchmarks were barred while the fleet ran and were not run afterwards).

## Open questions for the maintainer (consolidated)

- F-21: keep the set prior tracked (borrowed content, hard runtime dependency) or move
  to a setup-script copy from the pinned `showdown/` checkout?
- F-04: adopt `fold`, `drop`, or neither — and how to route the pre-reg
  (`docs/proposals/F04_minibatch_tail_prereg.md`). Default stays `keep` until ruled.
- F-06 / F-07: the option choices listed inside each proposal doc.
- F-05: is `SAVE_LATEST_EVERY_UPDATES = 4` (≈123k steps, ≈3.6 min at 574 steps/s,
  ~104 MB write inside the paused window) the cadence you want, or 2?
- F-03: is 900 s the liveness budget you want on lanes launched by hand (the wave's
  CPU-delta watch stays the outer layer)?
- Per-finding questions are listed under each finding above.

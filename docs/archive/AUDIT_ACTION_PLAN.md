> **CLOSED 2026-09-04.** Executed on the `audit-fixes` branch and merged into
> `main` (fast-forward) at bd8484d. What landed, what was skipped and what is
> still owed: `docs/archive/AUDIT_BRANCH_LOG.md`; the open rulings are in
> STATUS.md. History only — do not work from it. One edit was made during
> execution: the F-14 "Fix" sentence in §4 (PyO3 panics are BaseException).

# AUDIT_ACTION_PLAN.md - read-only audit of pokemon-showdown-rl

Audit date: 2026-09-02 (fleet at ~57.5M steps/lane at the original read; seeds 104/112/120).
**Re-verified 2026-09-02 ~19:35Z against `main` @ 60c1225 (still clean, still the tree the fleet
runs on): every finding's location and claim was re-read in the code, the installed poke-env
0.15.0 source, the configs and the live logs - read-only, no test run, no process touched, no
`extract_history.py` (it writes into the run dir). Corrections are marked `[re-verified: ...]`
inline, the fleet block below is the fresh read, and section 6 is the record of what was
confirmed, what was corrected and what could not be re-checked without running something.**
Tree audited: `main` @ 60c1225, clean. Mode: strictly read-only. No repo file was created or
modified, no git command that alters state was run, no test suite was executed (a live fleet
shares this box and the Showdown server), no process was touched. This file lives outside the
repo tree on purpose: CLAUDE.md rule 3 - one untracked `.md` stamps `git_dirty` on the next
`--resume`.

Verification sources: every file under `rl/` read in full (8,968 LOC); poke-env 0.15.0 source in
the conda env (`singles_env.py`, `player.py`, `env.py`, `single_agent_wrapper.py`, `move.py`);
the ratified `configs/showdown_sp_100m.yaml`; `scripts/ch5_100m_wave.sh`, `eval_checkpoint.py`,
`ladder.py`, `ch3_fp_h2h.py` (seat policy only); the test inventory (631 `def test_` functions
in 52 files; 665 collected items with parametrization - 648 passed / 17 skipped on the
2026-09-01 bare run recorded in `HANDOFF.md`); live logs
(`logs/ch5_100m_wave.log`, `logs/ch5_100m_rss.log`) and `ps`/`vm_stat`. One 1/10-scale memory
probe was run in the scratch directory (numpy only, ~40 MB, no repo import side effects).

---

**Fleet at re-verification (2026-09-02 19:22-19:32Z, all read-only; rates are rung-mtime
dStep/dWall, i.e. REALIZED - never `time/steps_per_sec`):**

| Lane | Latest rung (mtime) | Lifetime realized | Last 3 rungs | ETA 100M at the lifetime rate |
|---|---|---|---|---|
| s104 | `ckpt_066000019.pt` 19:32:34Z | 563 steps/s | 577 steps/s | ~2026-09-03 12:20Z |
| s112 | `ckpt_065000009.pt` 19:27:25Z | 556 steps/s | 560 steps/s | ~2026-09-03 12:55Z |
| s120 | `ckpt_064500010.pt` 19:22:35Z | 553 steps/s | 583 steps/s | ~2026-09-03 13:15Z |

FLEET DONE ~ 2026-09-03 12:20-13:15Z (s120 last) - earlier than STATUS's 14:40Z. Wave log: all
three lanes alive with advancing CPU time, no stall, no retry consumed. RSS
(`logs/ch5_100m_rss.log`, 1,568 samples): launch 2.0-2.3 GB/lane, PEAK 3.29 / 3.19 / 3.12 GB
(s104 / s112 / s120) - under the pre-reg's D-E line (RECORD any lane > 3.5 GB; record-only, no
per-lane threshold at any width) with 6% headroom, not the pre-reg header's "~30%" (`showdown_sp_100m.yaml:452`); current 0.7-1.3 GB
only because the box is compressing (73 MB free, 5.6 GB inactive, ~4 GB cumulative swapouts,
server 1.48 GB). No action: D-E is record-only and the box-level STOP (free+inactive < 2 GiB with
swapouts rising) is not near. `checkpoint.pt` (13.8 MB), `pool.pt` (90.1 MB) and
`best_checkpoint.pt` are being rewritten at the 250k eval cadence exactly as F-05/F-06 describe.
Nothing in this block changes the verdict or the plan.

---

## 1. Executive summary

**Verdict: the PPO core, the action-masking contract and the async collection path are correct.
No defect was found that corrupts the learning signal of the running 100M fleet, and nothing in
this report warrants touching it.** The three gate families the pre-reg relies on (recorded
old_logp under async collection, stored-and-reapplied masks, per-episode GAE with terminal
bootstrap 0) are implemented as described and are covered by tests.

The material findings are about memory, robustness and coverage, all post-fleet:

| # | Severity | Category | One line |
|---|---|---|---|
| F-01 | **High** | Performance | `SnapshotPool.push` deep-copies the whole `PPOAgent`, including the ~205 MB `RolloutBuffer` and the Adam moments. Sync path: ~4.1 GB of dead memory per lane at pool_size 20 (this is the 5.87 GB solo-lane "D-E landmine"). Async path: ~0.2 GB in the anchor member today, but **every `--resume` rebuilds all 20 members through the same copy and adds ~4.1 GB RSS to that lane**. |
| F-02 | **High** | Architecture / tests | `rl/envs/showdown_async.py` (the production collector) has zero unit tests; no test or script references `AsyncCollector`, `GatedSeam` or `CollectPlayer`. Its only coverage is the live acceptance fleet. |
| F-03 | Medium | Architecture | A wedged battle stream is invisible in-process: `_async_loop` sleeps on an empty `poll()` forever and `check()` only catches a *dead* drive. The external CPU-delta watch is the sole detector. |
| F-04 | Medium | PPO core | Async path: after the `< 2 rows` skip, trailing minibatch slices of 2..119 rows still take a full Adam step with advantages z-scored over that slice alone. |
| F-05 | Medium | Architecture | `checkpoint.pt` and `pool.pt` are written as two separate atomic renames, only at eval boundaries; a kill between them leaves a silently mismatched resume pair, and the resume-loss window (up to ~250k steps) is coupled to the eval cadence. |
| F-06 | Medium | Performance / method | In-loop eval (100 battles every 250k steps) costs 1-6% of wall-clock (range re-verified, see F-06) and feeds only a non-actionable metric and a noise-max `best_checkpoint.pt`. |
| F-07 | Medium | Reproducibility | Observation layout is decided by process env vars (`POKEMON_RL_ENCODER_V2/IDS/NO_SET_PRIOR`), not by the config; already shelved as CLEANUP A2. |
| F-08 | Medium | Architecture | `Discrete(10)` and gen-1 constants hard-coded in three places. [re-verified] poke-env's space is 10 for gens 1-5 and 14/18/22/26 for gens 6/7/8/9, so the action space SURVIVES the gen-4 chapter and breaks at gen 9; the encoder's gen-1 tables are the gen-4 blocker. |
| F-09..F-20 | Low / Refactor | see section 4 | stats() deque race, Python-loop GAE, scalar encoder, per-episode W&B volume, git_dirty vs untracked, `except BaseException`, turn feature saturation, sps estimator, MPS generator, RNG state, file size / layering. |

No Critical findings. Health by area:

| Area | Status |
|---|---|
| Action masking (sampling, log-prob, entropy, eval, stored per row) | Sound, tested |
| PPO loss terms, GAE, detaching, numerical guards | Sound, tested |
| Async collector correctness (old_logp at act time, version lag, label join, pause/resume invariant) | Sound by construction; **untested at unit level** (F-02) |
| Observation / partial observability | No hidden-information leak into the actor's obs; opponent side is revealed-only plus a public set prior |
| Turn / request synchronization | Sound; the sync path's listener race is documented, counted and capped; the async path has no such race (single synchronous segment) |
| Throughput | Measured, not assumed (1.53x realized at fleet width); remaining waste is memory (F-01) and eval overhead (F-06) |
| Reproducibility | Provenance stamped (sha, dirty flag, versions, encoder fingerprint, param counts); seeds cover random/numpy/torch; Showdown is server-rolled by design |
| Tests | 631 test functions (665 collected); strong on masking, GAE, pool, resume; gap is the async collector (F-02) and gradient-isolation assertions |

---

## 2. Verified sound (do not re-audit)

Each item names the code that was read and what it was checked against.

**Showdown domain logic**
- Mask source of truth is poke-env's `SinglesEnv.get_action_mask` (`singles_env.py:233-288`): switches are excluded wholesale when `battle.trapped`, moves are legal iff present in the server's `available_moves` (disabled / 0-PP moves never appear), a wait request yields the one-legal placeholder `[0]`, and the gen-1 placeholder turns (`fight` / `struggle` / `recharge`, poke-env `SPECIAL_MOVES`) collapse to action 6. Gen 1 has no mega/Z/dynamax/tera, so the space is exactly 6 switches + 4 moves = 10 (`get_action_space_size`, verified; `tests/test_showdown_env.py::test_gen1_action_space_is_10`).
- The encoder mirrors poke-env's action mapping bit-for-bit: team blocks in `list(battle.team.values())` order, move blocks in `list(active.moves.values())[:4]` order (`rl/envs/showdown.py:289-307`), which is exactly what `action_to_order` indexes (`singles_env.py:114,123-130`). On aliased placeholder turns the move blocks and their id suffix are zeroed and `vec[5]` says why (`showdown.py:282-287, 294-307, 343-345`), so "slot-0 features => action 6" is never taught on a turn where action 6 does not mean move 0.
- Mimic and Transform: poke-env 0.15.0 resolves both through `MoveSet` overlays (`poke_env/battle/move.py:953-1001`: `MoveSet`, `_transform_moves`, `mimic_move`, the `moves` property), so `moves` keeps the 4-slot alignment for our own mon. Verified in source; not a finding.
- Partial observability: the actor's obs reads only public fields for the opponent (`current_hp_fraction`, `level`, `base_stats`, revealed `moves`, `boosts`, `status`, `status_counter`, `effects`); actual opponent stats are never read (`_spe_est` uses base stats). Unrevealed mons are zero blocks behind a revealed flag; unrevealed moves are filled from the vendored randbats set prior as *probabilities* in the "known" slot (`showdown.py:234-258, 557-574`), which is public information. The privileged critic block (D18) is critic-only and off in the 100M config. `battle.opponent_team` only ever contains revealed mons (no team preview in gen1randombattle).
- Reward / outcome: terminal-only +-1/0 from `battle.won` / `battle.lost` (`showdown.py:844-853, 892-898`), never from the return sign; forfeits and timer losses are decided games and are remapped `truncated -> terminated` so GAE never stacks a bootstrap on a finished game (`showdown.py:1329-1337`). `eval/win_rate` reads the env-supplied outcome and raises if any episode lacks one (`rl/common/evaluation.py:141-150`).
- Turn synchronization, sync path: `ShowdownEnv.step` asserts `agent1_to_move` (a discarded action would be a phantom row), pumps wait states inside the step and accumulates their reward (`showdown.py:1274, 1299-1304`); `SingleAgentWrapper.step` never calls the opponent on its own wait (`single_agent_wrapper.py:36-42`). The mask-desync race between poke-env's listener thread and the main thread's conversion is intercepted at the conversion site, counted, capped at 3 per 100k steps, and fatal on a second hit in one battle (`showdown.py:623-711, 824-842`).
- Turn synchronization, async path: poke-env only calls `choose_move` on a real decision request (`player.py:_handle_battle_request` returns early on `battle._wait`), and `CollectPlayer.choose_move` runs encode -> mask -> policy -> record -> convert in one synchronous segment with no `await` that can yield while the gate is open (`showdown_async.py:142-173`; `GatedSeam.request` only awaits when the gate is clear). The listener race therefore cannot occur on this path, and `convert_errors` is correctly treated as a hard fault. The `(turn, nth-decision)` label join reproduces the sync semantics (first decisions pair; forced replacements pair only when both seats replaced; unmatched keys resolve to the sentinel and are dropped from the aux loss by `canonicalise`).
- Pool swap boundaries: member per *battle* (`PoolPlayer._by_tag`, `showdown.py:1063-1072`), pushes only at update boundaries fenced through `run_in_loop` (`rl/train.py:623-625`), members frozen at push (`pool.py:131-139`), outcome credited to the member that played (`showdown_async.py:252-253`).

**PPO / PyTorch**
- Masking before every softmax: collection `act` (`ppo.py:675-680`), `act_logp` (`701-704`), the update-start recompute (`929-931`), every epoch's forward (`1139-1142`), eval argmax (`677-678`), the BC anchor (`1163-1171`), the pool opponent (`pool.py:86-87`) and the aux head (`opp_action.py:338`). Finite `-1e8` sentinel; `masked_entropy` where-guards illegal positions to an exact 0 (`masking.py:39-45`); the critic is never masked. `tests/test_masking.py` pins illegal probability == 0.0, first-epoch ratio == 1 under masking, and end-to-end legality.
- The stored mask is what makes the ratio right: `RolloutBuffer.masks` per row (`rollout.py:61-64`), `EpisodeDataset` requires `masks` on every episode (`episode.py:35-42`).
- `old_logp` under async collection is recorded at act time (`ppo.py:685-705`, `showdown_async.py:157-167`), never recomputed (`ppo.py:1001-1003`); the sync path recomputes at update start where that is exact (`ppo.py:920-931`). `tests/test_ppo_episodes.py::test_act_logp_samples_inside_mask_and_matches_recompute` pins the two constructions against each other.
- GAE: `compute_gae` implements delta_t = r + gamma V(s') (1 - term) - V(s), chain cut on any done, bootstrap kept on truncation (`rollout.py:154-161`); `episode_gae` reduces the flat episode batch to the same kernel with terminal bootstrap 0 and next_values = V shifted (`episode.py:97-130`). Tested against hand references, across-episode isolation, and against the (T, N) form on aligned columns.
- Clipped surrogate, approx_kl, clip_frac (`ppo.py:125-153`); value MSE on GAE-consistent targets; entropy subtracted with coefficient (`1146-1150`); one `clip_grad_norm_` over the actor+critic union with the aux gradient clipped to its own budget and added after the PPO clip is read (`1201-1215`, `732-789`).
- No graph leakage: `values`, `next_values`, `old_logp`, the anchor log-probs, the L2-init decay, explained variance and adv_std are all under `torch.no_grad()`; advantages and targets enter as detached tensors; diagnostics are `.item()`ed. `AgentOpponent.freeze` drops `requires_grad`, and pool members share no storage with the learner (`tests/test_selfplay_pool.py::test_snapshot_shares_no_storage_with_the_learner`).
- Numerical guards present where needed: `mb_adv.std() + 1e-8` (`1135`), explained-variance degenerate-batch guard (`1071-1075`), `aux_cross_entropy` weight clamp (`opp_action.py:341`), `_spe_est` floor (`showdown.py:540`), PP division guard (`246`), `RunningMeanStd` EPS inside the sqrt (unused on Showdown). No `-inf` anywhere in the masking path.
- Learning-rate anneal reads the checkpointed counters (`ppo.py:1101-1112`), the optimizer graft on load keeps the config's lr and tolerates the pre-split single-group checkpoints (`1295-1321`), the aux group is appended third so loaded moments land on the right tensors (`510-525`).

**Throughput (measured by the repo, confirmed by reading the code paths)**
- The E1-E4b measurements behind the async design hold up: batch-1 servicing inline on `POKE_LOOP`, `torch_threads: 1` (measured faster than 6 on this box), no lockstep barrier, one critic pass per update instead of two, `next_obs` array gone on the async path. Realized 574 steps/s/lane at fleet width = 1.53x the sync control; the fleet is currently realizing ~558 steps/s/lane (57.5M steps in 28.6 h).

**Reproducibility**
- `set_seed` covers `random`, NumPy and torch; pool member draws use a per-sub-env `default_rng(seed)` and per-member `torch.Generator`s; account names are derived (`as2s{seed}a/b`) on the async path; `meta.yaml` stamps sha, dirty flag, package versions, the encoder fingerprint and exact parameter counts. Showdown itself is unseeded by design and every doc says so.

---

## 3. Detailed findings - High and Medium

### F-01 [High] [Performance / memory] Pool snapshots deep-copy the rollout buffer and optimizer moments

**Location.** `rl/selfplay/pool.py:74` (`self.agent = copy.deepcopy(agent)`), called from `push` (`:134`) and from `load_state_dict` (`:237-238`, `AgentOpponent(agent_factory(), ...)`). The step-0 push in `rl/train.py:429` happens *before* `_async_loop` sets `agent.buffer = None` (`rl/train.py:519`). `PPOAgent` defines no `__deepcopy__` (`grep` over `rl/`: none), so `copy.deepcopy(agent)` copies `agent.buffer` (a `RolloutBuffer(3840, 8, (828,))`: `obs` + `next_obs` = 2 x 101.7 MB, ~205 MB total) and `agent.optimizer` (two Adam moments per parameter, ~9 MB).

**Measured.** Scratch probe at 1/10 scale (`RolloutBuffer(384, 8, (828,), n_actions=10, opp_choice_dim=3)`, 20.5 MB): allocation via `np.zeros` costs 0.1 MB RSS (calloc pages are lazy), `copy.deepcopy` costs +38.9 MB RSS (the copy is written, the source is faulted in). Scaled: **~205 MB resident per member copy**.

**Impact.**
- Sync control fleet (`showdown_sp_batch50m.yaml`, same 30,720-row buffer, pool_size 20): ~4.1 GB of dead, zero-or-stale-rollout pages per lane. This is the mechanism behind the D-E landmine: 2.68 GB/lane 3-wide (macOS compresses idle zero pages under pressure) vs 5.87 GB when a lane ran alone with no pressure.
- Async lanes today: the anchor member (never evicted) carries ~205 MB of zero-filled buffer plus ~9.4 MB of moments (`meta.yaml`: 626,059 + 494,849 + 49,479 = 1,170,387 params x 2 moments x 4 B); the 19 later members carry buffer=None but still ~9.4 MB of moments each. Roughly 0.4 GB of a lane's RSS is waste (launch 2.0-2.3 GB, peak 3.1-3.3 GB, currently 0.7-1.3 GB under box-level compression - see the fleet block). `pool.pt` is 90.1 MB (weights only: `state_dict` at `pool.py:197-219` saves actor, critic and generator state per member), so the on-disk state is fine. [re-verified] The module docstring (`pool.py:14-17`) still describes the deepcopy's waste as "~2/3 of the ~1 MB per snapshot ... accepted waste, per the locked spec" - a Connect-4-era figure; at the batch recipe a snapshot is ~215 MB, 200x the accepted number, so the fix should correct that sentence too.
- **Any `--resume` of an async lane rebuilds all 20 members through `make_agent` + deepcopy: +~4.1 GB RSS on that lane** (24 GB box, three lanes plus the server, historical swapouts already at ~4 GB). The D-E "RECORD > 3.5 GB" line will trip on a resumed lane for a non-reason.

**Fix (post-fleet, trivial, keeps every existing test).** Snapshot the nets, not the agent:
```python
# rl/selfplay/pool.py
from types import SimpleNamespace

class AgentOpponent(Opponent):
    def __init__(self, agent, seed: int = 0):
        # A member needs the two nets and the device - never the rollout
        # buffer (~205 MB at the batch recipe) or the Adam moments.
        self.agent = SimpleNamespace(
            actor=copy.deepcopy(agent.actor),
            critic=copy.deepcopy(agent.critic),
            device=agent.device,
        )
        self.generator = torch.Generator().manual_seed(seed)
```
`move`, `freeze`, `state_dict`, `load_state_dict` and the tests only touch `member.agent.actor/critic/device` [re-verified by grep, not by running: `tests/test_selfplay_pool.py:62-176`, `tests/test_frozen_opponent.py:90` and `tests/test_selfplay_harness.py:514` read `.agent.actor` / `.agent.critic` only; the `self.agent.act(...)` at `test_selfplay_harness.py:336` belongs to a test-local opponent class holding its own agent, not to a pool member]. Add a regression test: `len(pickle.dumps(member.agent)) < 20 MB` (or assert `not hasattr(member.agent, "buffer")`). Optionally also drop the optimizer from `state_dict` riders. Do not fix by defining `PPOAgent.__deepcopy__`: it would change semantics for every other deepcopy caller (`_install_bc_anchor` copies the actor only, fine, but future callers would inherit surprising behaviour).

**Operational note for the running fleet (no action).** Resumes still work. If one becomes necessary, resume one lane at a time and expect that lane's RSS to jump by ~4 GB of highly compressible zero pages; the box-level STOP (free+inactive < 2 GiB and swapouts rising) remains the only gate that should act.

### F-02 [High] [Architecture / test coverage] The production collector has no unit tests

**Location.** `rl/envs/showdown_async.py` (364 LOC). `grep -l "showdown_async\|AsyncCollector\|GatedSeam\|CollectPlayer" tests/*.py scripts/*` returns nothing. `tests/test_async_launch.py` covers only the config block, `tests/test_ppo_episodes.py` covers `update_episodes`, `tests/test_episode_buffer.py` covers the dataset.

**Problem.** The invariants the pre-reg's gates rest on are asserted only by having run the acceptance fleet: the pause/resume fence ("no decision is between the gate and its row append when `pause()` returns", `:322-330`), the discard rule (`:257-258`), `_prune`'s grace window and orphan aging (`:281-293`), `check()`'s dead-stream detection (`:312-320`), `stats()`, and the `(turn, idx)` label join (`:161-163` with `showdown.py:1097-1110`). A regression in any of these would surface only as a live-run gate breach after hours.

**Fix.** (1) Make the two `Player`s injectable (a `_make_players` seam or `players=` kwarg) so the bookkeeping can be driven with duck-typed battles and `start_listening=False`; unit-test `_finish` (kept / discarded / tie reward 0 / label join incl. forced replacements), `_prune` (grace window, orphan aging), `check()` (raises on convert errors and on a finished drive), `stats()`. (2) One live test in the `test_full_episode_contract_against_live_server` style: K=4 battles vs `SimpleHeuristicsPlayer`, call `pause()` from the main thread while decisions are in flight, assert `seam.requests` does not advance until `resume()`, assert every episode row's `version` is <= the version at its own finish. (3) Assert the gate invariant directly: after `pause()` returns, mutate a weight and check no row recorded between pause and resume used the new weight (record the actor's parameter hash in the seam during the test).

### F-03 [Medium] [Architecture / robustness] Silent stall is undetectable in-process

**Location.** `rl/train.py:563-568` (`while step < total_steps: check(); episodes = poll(); if not episodes: sleep(0.02); continue`) and `showdown_async.py:312-320` (`check()`).

**Problem.** The landmine record's stall shape (alive, zero CPU, sockets open) is exactly what this loop produces when the battle stream wedges: `_drive` is still running (`battle_against` is a live coroutine parked on `_battle_count_queue.put`), `poll()` is empty, and the process idles at zero CPU forever. `check()` cannot see it. The timer fix removed the known cause, and the wave's 15 s CPU-delta probe is the detector, but a lane launched by hand (or the sync fallback) has nothing.

**Fix.** Add an in-loop liveness budget: remember `last_progress = time.monotonic()` whenever `poll()` returns episodes or `seam.requests` advances; if the gate is open and `time.monotonic() - last_progress > LIVENESS_S` (900 s is > 30x the longest legitimate gap at 574 steps/s), raise `RuntimeError("collector: no decision for 900 s with N battles in flight")`. The process dies with a traceback, the wave's dead-lane branch resumes it [re-verified: `scripts/ch5_100m_wave.sh:103-117`, 3 retries per lane], and the failure is attributable in the lane log instead of only in the wave log. Keep the CPU-delta watch as the outer layer.

### F-04 [Medium] [PPO core] Trailing minibatch slices of 2..119 rows get a full optimizer step

**Location.** `rl/agents/ppo.py:1114-1135`. `minibatch_size = batch_size // self.minibatches` with `minibatches: 120` (`configs/showdown_sp_100m.yaml:578`), so each slice is 256 + floor(eps/120) rows and `range(0, batch_size, minibatch_size)` leaves a final slice of `batch_size mod minibatch_size` = eps mod 120 rows (0..119) on the async path (whole-episode overshoot makes `batch_size` = 30,720 + eps; the pre-reg header `:86-89` discloses exactly this). Only `< 2` rows are skipped (`:1122-1131`; pinned by `tests/test_ppo_episodes.py::test_trailing_one_row_minibatch_is_skipped_not_nan`).

**Problem.** A slice of, say, 3 rows is z-scored against its own mean/std (`:1135`) and then takes a full Adam step at the same lr as a 256-row minibatch. Adam's normalization means the *magnitude* of the step is comparable to a real minibatch, but its direction is a 3-sample estimate. Expected frequency: one such step per epoch per update, i.e. ~0.8% of gradient steps, with slice size uniform on 2..119. Not a correctness bug, and the pre-reg discloses the "trailing partial slice"; it is a small, avoidable variance source that is easy to test.

**Fix (pre-register as a non-lever wire change; numerics move slightly).** Either drop the tail (`for start in range(0, n_full * mbs, mbs)`; `perm` is fresh per epoch so different rows are dropped each epoch, expected loss 0.2% of rows per epoch), or fold it into the last slice when it is smaller than `mbs // 2`. Add a test that every executed minibatch has `>= mbs // 2` rows on an async-shaped batch (30,721 .. 30,839 rows).

### F-05 [Medium] [Architecture / resume] Resume state is two files, written only at eval boundaries

**Location.** `rl/train.py:552-558` (`save_latest`: `checkpoint.pt` then `pool.pt`, two separate atomic renames), called at `:649` (eval block) and `:653` (end); the same pattern at `:928-937` on the sync path. The wave script resumes with `kill -9` (`scripts/ch5_100m_wave.sh:131-135`, stall branch).

**Problem.** (a) A SIGKILL between the two renames leaves `checkpoint.pt` at step S and `pool.pt` at step S - 250k: the resumed run silently continues with an older pool (up to ~8 updates / 2 pushes behind, wrong `pushes` counter, generator states one eval behind). Nothing checks the pair. (b) `save_latest` rides the eval cadence, so the resume-loss window is ~250k steps (the landmine record measured 170k-190k lost per resume), and any future change to `eval_every` silently changes resume granularity.

**Fix.** Put the pool inside the checkpoint payload: `save_checkpoint(..., extras={"loop": {...}, "pool": collector.run_in_loop(pool.state_dict)})` - one file, one rename, one atomic pair; the loader reads `ckpt.get("pool")` and falls back to `pool.pt` for pre-existing run dirs. Then call `save_latest()` on its own cadence (e.g. every 4 updates, ~2 min at 574 steps/s) independent of eval. Add a `stamp: step` to the pool state and assert it equals `ckpt["step"]` on resume.

### F-06 [Medium] [Performance / method] In-loop eval buys nothing the verdict path reads

**Location.** `rl/train.py:635-650` (eval every 250k steps, 100 battles, `best_checkpoint.pt` on `eval/return_mean`); `configs/showdown_sp_100m.yaml` (`eval_every 250000`, `eval_episodes 100`).

**Problem.** Per lane: 400 evals x ~10-26 s (the original read of `time/eval_sec`, max 26.18 s) against ~435 s of collection per 250k steps = 2-6% of wall-clock (~1-2 h of a 48 h lane), during which K=8 battles sit paused against the 300 s challenge timer (`pause()` precedes `evaluate()` at `rl/train.py:637-641`). [re-verified: the pre-reg's own budget line (`showdown_sp_100m.yaml:535`) says "400 evals ~ 0.58 h/lane" (~5 s/eval, 1.2%); the lane logs carry no eval timings and `extract_history.py` writes into the run dir, so the per-eval figure was NOT re-read here - quote the prize as 1-6%, not 2-6%, until history.csv is extracted after FLEET DONE.] Consumers: `eval/win_rate` (pre-reg: visible, not actionable; R0-6 only needs it to exist), `best_checkpoint.pt` (max over 400 draws at se ~0.05, a noise-max that `eval_checkpoint.py`'s own docstring warns about and no grader reads [re-verified: `scripts/eval_checkpoint.py:11`; `scripts/ch5_100m_grade.py` never references it]), and the `save_latest` cadence (F-05).

**Fix (next pre-reg, not this run).** Decouple `save_latest` (F-05), then either lengthen the cadence (1M steps keeps R0-6 and the shape read) or cut `eval_episodes` to 50; stop writing `best_checkpoint.pt` on Showdown runs, or rename it to make the selection bias explicit. Expected gain: 2-5% wall-clock per lane and shorter timer exposure.

### F-07 [Medium] [Reproducibility] Encoder layout is process-environment state

**Location.** `rl/envs/showdown.py:139, 152, 554` (`_ENCODER_V2`, `_ENCODER_IDS`, `_NO_SET_PRIOR` read from `os.environ` at import), `OBS_DIM` at `:168`; consumers `rl/networks/entity_deepsets.py:57-105` (the tokenizer asserts the layout against `OBS_DIM` at construction), `scripts/eval_checkpoint.py::_load_showdown_agent` (`:51-92`, shim + refusal), `scripts/ch5_100m_wave.sh:29-30` (exports the flags).

**Problem.** The observation semantics of a checkpoint are not in the config that trains or evaluates it. The entity trunk fails loudly on a mismatch (good); an MLP-trunk checkpoint fails on a shape mismatch (good); `NO_SET_PRIOR` changes semantics at *constant* `OBS_DIM` and only the `meta.yaml` fingerprint records it - a forgotten export on an eval box produces a plausible wrong number for the MLP + set-prior case. Already shelved as CLEANUP A2 ("flip the default, assert `OBS_DIM == 828`"); recorded here so the shelf item carries the risk statement.

**Fix.** Move the three flags into `Config` (an `encoder:` block), stamp them into every checkpoint payload, and make `make_agent` / the eval loaders compare the checkpoint's fingerprint against the process's and refuse on mismatch. The env vars can remain as a deprecated override that must equal the config. [re-verified: `CLEANUP.md:107-108` shelves A2 as a PURE default flip ("encoder env-var default flip -> assert `OBS_DIM==828`/fingerprint instead; pure default flip only") until the 100M readout is recorded. The `encoder:` config block is a larger change than the ruled A2 - carry it as a separate proposal that needs its own maintainer ruling; do not fold it into A2.]

### F-08 [Medium] [Architecture] Action-space size and gen-1 constants are hard-coded ahead of the gen-4/gen-9 chapters

**Location.** `rl/train.py:91-94` and `:325-330` (`Discrete(10)` for the faked spaces), `scripts/eval_checkpoint.py:85` (same), `rl/envs/showdown.py:81-168` (15 types, 7 boosts, `GEN1_TYPES`, gen-1 volatiles), `rl/networks/entity_deepsets.py:180-181` (`out_dim not in (10, 1)`), `rl/networks/opp_action.py` (L6 over 4 move slots).

**Problem.** [re-verified - the original overstated this] poke-env's `get_action_space_size` (`singles_env.py:291-304`) is 6 switches + 4 moves x (1 + gimmicks) with gimmicks 0 for gens 1-5 and 1/2/3/4 for gens 6/7/8/9: 10 through gen 5, then 14/18/22/26. The hard-coded 10 therefore SURVIVES the gen-4 chapter (JOURNEY step 3) and breaks only at gen 9 (26). What does not survive gen 4 is the encoder: 15 gen-1 types (gen 2 adds Dark and Steel -> 17; gen 6 adds Fairy -> 18), the physical/special-by-type rule (gen 4 splits it per move), and no items, abilities, weather or gen-2+ status/volatile set. Every hard-coded 10 is still a silent shape bug at gen 9, and the encoder's per-gen tables need a seam before gen 4.

**Fix.** Derive the faked spaces from `SinglesEnv.get_action_space_size(GenData.from_format(fmt).gen)`; move gen-specific tables behind an `EncoderSpec` chosen by format; keep gen 1 bit-identical (regression-test the 828-dim encoding on the stored tapes). Order: the `EncoderSpec` seam is the gen-4 blocker; the action-space derivation can land with it but is not needed until gen 9.

---

## 4. Detailed findings - Low and Refactor

### F-09 [Low] [Architecture / concurrency] `AsyncCollector.stats()` iterates a deque the loop thread appends to
`showdown_async.py:343-345`: `len([t for t, _ in self._ended])` runs on the main thread while `_finish` (loop thread) may `append`. CPython raises `RuntimeError: deque mutated during iteration` if that interleaves. The window is microseconds and finishes during a pause cluster at its start, so the realized risk is very low, but the expression is also pointless work. Fix: `len(self._ended)` (atomic under the GIL), or read all stats via `run_in_loop` like the pool stats already are.

### F-10 [Low] [Performance] GAE runs a Python loop over ~30k rows on the async path
`episode.py:97-130` reduces to `compute_gae` over a `(B, 1)` column; `rollout.py:157-160` then iterates B ~30,720 times with 1-element NumPy ops (~0.1-0.3 s per update, 1-3% of `time/update_sec`). Fix: scipy is not a declared dependency (`pyproject.toml`), so no `lfilter`; pad the episodes to (E, Lmax) and run the existing reverse scan over Lmax (~2,000, the longest episode) instead of over B, or a per-episode NumPy reverse-cumulative form. Keep the (T, N) kernel as the reference and pin equality in `test_episode_buffer.py`.

### F-11 [Low] [Performance] The encoder is scalar Python and recomputes the opponent slots twice
`showdown.py:194-258` writes ~800 elements one at a time, twice per step (learner seat, pool seat); under `POKEMON_RL_ENCODER_IDS=1` `_opponent_move_slots` is called in the block fill (`:320`) and again in `_fill_ids` (`:347`). Measured cost ~133 us/decision (E3), i.e. a few percent of collection. Fix: pass the slot list from `embed_battle` into `_fill_ids`; precompute the static per-species and per-move blocks (`_fill_mon` base stats/types, `_fill_move` bp/acc/category/type/effect) as cached NumPy rows and assign by slice. Only worth doing with a before/after `profile_collect.py` number.

### F-12 [Low] [Performance / tooling] Per-episode W&B logging
`rl/train.py:574-582` logs three keys per finished episode (~1.7M episodes per 100M lane). Today's s104 `wandb/` dir is 752 MB at 66M steps (672 MB at 57M - linear, ~1.15 GB by 100M); `history.csv` sizes were already a CLEANUP item (`CLEANUP.md:36`, 2.16 GB - COMPRESSION was decided against there; this fix is volume at the source, not compression, so it does not relitigate that ruling). `extract_history.py` loads every row. Fix: log per-rollout aggregates (mean/min/max/count of `rollout/episode_return` and `rollout/episode_length`) under the locked names plus a decimated per-episode sample; keep `time/steps_per_sec` per rollout.

### F-13 [Low] [Reproducibility] `git_dirty` conflates tracked changes with untracked files
`rl/train.py:122-127` uses `git status --porcelain`, so a stray `.md` marks every run dirty (CLAUDE.md rule 3 exists because of it). Fix: stamp both `git_dirty_tracked` (`--untracked-files=no`) and `untracked_files: [...]` so provenance stays exact without a launch-time trap.

### F-14 [Low] [Code quality] `except BaseException` swallows interrupts in the search line
`rl/search/matrix.py:202-205` wraps `calculate_damage` in `except BaseException: dmg = None`. A Ctrl-C or `SystemExit` during a search arm degrades into "no damage attribution" instead of stopping. Fix: [re-verified: the original prescription here was "Fix: `except Exception`", which is WRONG - it fixes the interrupt half and breaks the engine-fault half] re-raise `(KeyboardInterrupt, SystemExit)` explicitly and keep `except BaseException` for everything else — NOT a plain `except Exception`: `poke_engine` is PyO3 and a Rust panic surfaces as `pyo3_runtime.PanicException`, which derives from `BaseException`, not `Exception` (verified 2026-09-03: MRO `[PanicException, BaseException, object]`), so `except Exception` would let an engine panic kill the search seat's battle instead of degrading to `dmg = None` as it always has.

### F-15 [Low] [Showdown logic] The turn feature saturates at turn 50
`showdown.py:277` (`min(turn / 50, 1)`). Battles reach the turn-1000 Endless Battle Clause and end in a 0-reward tie; past turn 50 the policy cannot see the clock. [re-verified from the live lane logs at ~65M steps: 16 / 8 / 4 turn-1000 auto-ties (s104 / s112 / s120, seat-a "0 turns" warnings) and ~18 / 12 / 8 battles into the turn-900 countdown (864 / 480 / 336 `bigerror` lines at ~40 per battle) - rare against ~1.1M battles per lane, which is why this stays Low. The original "s83 hit it 482 times in 50M steps" could not be reproduced from any log on disk (`ch5_g9_lane_s83.log`: 98 lines, 2 auto-ties) and is withdrawn.] Fix: add a second, log-scaled or /1000 turn feature at the next encoder revision (an `OBS_DIM` change - evaluate outstanding finals first, per the landmine).

### F-16 [Low] [Observability] `time/steps_per_sec` on the async path is a poll-cadence estimator
`rl/train.py:573-583`: the rate is computed between polls that returned episodes, so update pauses land in one denominator and the series overstates realized throughput by ~57% (disclosed in the pre-reg). Fix: also log `time/realized_steps_per_sec = dStep/dWall` per rollout including pauses, so downstream never has to pick an estimator.

### F-17 [Low] [Known] `AgentOpponent.move` breaks on MPS
`pool.py:88`: `torch.multinomial(probs, 1, generator=self.generator)` with a CPU generator against an MPS tensor (landmine record, standing item 2). Fix when ruled: `torch.Generator(device=self.agent.device)`; note the RNG stream changes, so it is a new lane, not a faster copy.

### F-18 [Low] [Reproducibility] RNG state is not checkpointed; a resume re-seeds
`rl/common/checkpoint.py` saves agent/step/config/normalizers/extras only; `train()` calls `set_seed(cfg.seed)` unconditionally (`rl/train.py:219`), so on resume the torch/NumPy/random streams restart from step 0's state (minibatch permutations and action draws replay the run's first sequence). Harmless statistically on a server-rolled env; record it in `docs/landmines.md` under the resume section, or save `torch.get_rng_state()` / `np.random.get_state()` / `random.getstate()` in `extras`.

### F-19 [Low] [Showdown logic] `[Invalid choice]` re-requests produce a second learner row for the same turn
poke-env re-calls `_handle_battle_request(maybe_default_order=True)` after an `[Invalid choice]` error (`player.py:324-325` -> `:333-350`), which with `DEFAULT_CHOICE_CHANCE = 1/1000` sends a default order without calling `choose_move` at all and otherwise calls `choose_move` again; either way, on the async path the rejected first decision stays in the episode as a normal (s, a, logp) row and the retry is keyed `(turn, 1)`. Rate is that of the server-side race (measured ~2.5e-9/step on the sync path; effectively 0 on the async path). Fix: count them (`collect/rerequests`) so a poke-env or server bump that raises the rate is visible.

### F-20 [Refactor] [Architecture] Module size and layering
- `rl/envs/showdown.py` (1,341 LOC) holds the encoder, two reward shapers, the set prior hook, desync recovery, three opponent adapters and the Gym adapter; it also imports `rl.selfplay.pool` (env layer depending on the self-play layer). Split into `encoder.py` / `shaping.py` / `opponents.py` / `env.py`, and invert the pool dependency through the `Opponent` protocol.
- `rl/agents/ppo.py` (1,358 LOC) carries five closed research levers inline (BC-KL anchor, critic warm-up, L2-toward-init, opponent-action aux head with placebo and synthetic variants, privileged critic). Each is a well-fenced no-op at its default, but the production learner is now the union of every experiment. Introduce a lever/plugin seam (`levers: list[Lever]` with `on_batch`, `after_step`, `metrics` hooks) once the 100M readout is recorded, keeping the R0-3b bit-identity tests as the regression pin.
- The encode/mask/convert trio is duplicated 8x with divergent desync policy (CLEANUP B3, deferred); `rl/collect.py`'s `SeamPlayer`/`InferenceSeam` are not on the training path any more and should either be the shared helper or be retired.
- `PPOAgent.update()`'s 11-element positional tuple (CLEANUP A4): replace with a small `Transition` dataclass.
- `Config.load_config` type check (`config.py:96-102`) accepts `bool` for `int` fields; strictness for nested dicts is delegated to the consumers (agent kwargs, `selfplay_env_kwargs`, `_async_collector_mode`, `ShowdownEnv.__init__`) - adequate, but a single schema check at load would make the launch-time failure set explicit.

### Test coverage map (631 test functions / 665 collected)
| Area | Present | Missing |
|---|---|---|
| Masking | identity under all-True, exact-zero illegal mass, entropy finite/bounded, first-epoch ratio 1, end-to-end legality | gradient of `masked_entropy` at the sentinel is finite and zero at illegal positions |
| PPO | clip cases, KL estimator, cadence, anneal, param groups, warm-up, BC anchor, explained variance, grad clip frac | gradient isolation (policy loss puts no grad on the critic; aux grads never reach `scorer`/`slot_bias`); trailing-slice size policy |
| GAE / buffers | TD/MC limits, termination vs truncation, env independence, episode isolation, (T,N) equivalence | vectorized-GAE equivalence once F-10 lands |
| Async path | config validation, `update_episodes`, `act_logp` vs recompute, 1-row skip | everything in F-02 |
| Env / Showdown | outcome mapping, wait pump, discard assert, aliasing, shaping, pool player, desync recovery, live contract | Mimic/Transform slot alignment on a real request (currently trusted to poke-env) |
| Resume | pool round-trip, config drift refusal, killed run resumes | checkpoint/pool pairing (F-05); memory of a resumed pool (F-01) |

---

## 5. Prioritized action plan (all post-fleet; nothing here touches the running run)

1. **F-01 - snapshot only the nets in `AgentOpponent`.** One-file change, keeps every test, removes ~4 GB/lane from the sync fallback and from every async resume; add the size regression test. Do this before any lane is resumed by hand and before the sync fallback is ever launched.
2. **F-02 + F-03 + F-09 - make the async collector testable and self-diagnosing.** Injectable players, unit tests for the bookkeeping, one live pause/resume test, an in-loop liveness timeout that turns a silent stall into a resumable crash, and `len(self._ended)`.
3. **F-05 + F-06 - one atomic resume payload on its own cadence, and an in-loop eval budget that pays for itself.** Fold `pool.state_dict()` into `checkpoint.pt`'s `extras`, save every few updates, stamp and assert the pair; then, in the next pre-reg, lengthen or shrink the in-loop eval and stop producing `best_checkpoint.pt` on Showdown.
4. **F-04 - minibatch tail policy.** Drop or fold slices below `mbs // 2`; pre-register as a non-lever wire change because the numerics move; pin with a test on async-shaped batch sizes.
5. **F-07 + F-08 - config-driven encoder flags and a per-gen encoder seam** before the gen-4 chapter opens (the `EncoderSpec`; the format-derived action space is a gen-9 need - poke-env keeps 10 through gen 5); keep the 828-dim gen-1 encoding bit-identical under regression tapes. F-07's config-block move exceeds the ruled CLEANUP A2 (pure default flip) and needs its own ruling before it is scheduled.

Everything else in section 4 is opportunistic and can ride along with the module split (F-20).

---

## 6. Re-verification record (2026-09-02 ~19:35Z, read-only)

**Confirmed as written (location and mechanism re-read in the tree):** F-01 (`pool.py:74/134/237-238`, no `__deepcopy__` anywhere under `rl/`, `RolloutBuffer` obs + next_obs at (3840, 8, 828) float32 from `ppo.py:558` / `rollout.py:40-48`, step-0 push `train.py:429` before `agent.buffer = None` at `:519`, resume factory `train.py:407-411` = `make_agent` per member); F-02 (no test or script names `showdown_async`, `AsyncCollector`, `GatedSeam` or `CollectPlayer`; `test_async_launch.py` is 4 config tests); F-03 (`train.py:563-568`, `check()` at `showdown_async.py:312-320`); F-04 (see the corrected arithmetic); F-05 (`save_latest` `train.py:552-558`, called only at `:649` and `:653`; two renames; no pair check on load); F-06; F-07 (`showdown.py:139/152/554`, `OBS_DIM` at `:168`); F-09 (`showdown_async.py:343-345` iterates `_ended` while `_finish` appends from the loop thread - and `stats()` runs inside the paused block at `train.py:597`, which the battle-end callback does not respect); F-10 (`episode_gae` -> `compute_gae` over a (B, 1) column, Python loop `rollout.py:157-160`); F-11 (`showdown.py:320` and `:347`); F-12; F-13 (`git status --porcelain` at `train.py:124`); F-14 (`matrix.py:202-205`); F-15 (`showdown.py:277`); F-16 (`train.py:573-583`); F-17 (`pool.py:88`; `docs/landmines.md:151-161`); F-18 (`checkpoint.py` saves agent/step/config/normalizers/extras only); F-19; F-20 (`showdown.py:58` imports `rl.selfplay.pool`; `update()` unpacks an 11-tuple at `ppo.py:841-852`; `config.py:96-102` `isinstance` accepts bool for int; `SeamPlayer`/`InferenceSeam` are referenced only from `scripts/showdown_throughput.py`, `tests/test_collect.py`, `tests/test_showdown_env.py` and comments). Every section-2 citation that names a line was re-read: `ppo.py` 125-153, 505-525, 675-705, 920-931, 1001-1003, 1071-1075, 1101-1150, 1163-1171, 1201-1215, 1295-1321, 1353; `showdown.py` 194-258, 282-307, 343-345, 540, 623-711, 840-853, 892-898, 1063-1072, 1097-1110, 1274, 1299-1304, 1329-1337; `rollout.py` 61-64, 154-161; `episode.py` 35-42, 97-130; `masking.py` 39-45; `evaluation.py` 141-150; `opp_action.py` 338, 341; poke-env `singles_env.py` 110-132, 233-288, 291-304, `player.py` 324-350, `single_agent_wrapper.py` 36-42, `battle/move.py` 953-1001. The four named tests exist (`test_gen1_action_space_is_10`, `test_act_logp_samples_inside_mask_and_matches_recompute`, `test_snapshot_shares_no_storage_with_the_learner`, `test_full_episode_contract_against_live_server`), and `tests/test_masking.py` pins exact-zero illegal mass (`:37`), first-epoch ratio 1 (`:118`) and end-to-end legality (`:181`). `privileged_dim` is absent from the 100M config (off). LOC: 8,968 under `rl/`; `showdown.py` 1,341, `ppo.py` 1,358, `showdown_async.py` 364.

**Corrected:** F-08's gen table (poke-env is 10 through gen 5; gen 4 keeps the action space, loses the encoder); `entity_deepsets.py` citations (:57-105 for the layout assert, :180-181 for `out_dim`); wave-script flag exports (:29-30, not :26-27); F-15's "482 in s83" figure (withdrawn, live counts substituted); the test count (631 functions vs 665 collected); F-06's prize range (1-6%, the pre-reg's own 0.58 h estimate disagrees with the audit's 10-26 s read); F-07's fix scope against the CLEANUP A2 ruling; F-10's scipy suggestion (not a dependency); the fleet header (position, ETA, RSS peak vs the D-E line).

**Not re-verifiable read-only, stated as such:** per-eval `time/eval_sec` (needs `extract_history.py`, which writes into the run dir); the 1/10-scale deepcopy memory probe (not re-run; the arithmetic - 2 x 3840 x 8 x 828 x 4 B = 203.5 MB - stands on its own); the "keeps every test" claim for the F-01 fix (attribute surface checked by grep; the suite was not run while the fleet shares the box).

# Collection-loop re-architecture — Rung 0 engineering spec

Provenance: drafted 2026-08-07 by a session subagent from direct source reads of
gymnasium/poke-env/ps-ppo/metagrok plus offline microbenchmarks run on this machine
(embed_battle and MLP forward timings are MEASURED; Stage-2 projections are estimates
gated by experiments E1-E4). Curated and committed by the session. DESIGN r7 Rung 0
references this file; D14 governs its scope.

# COLLECTION-LOOP RE-ARCHITECTURE — Engineering Spec (Rung 0)

## 0. The headline finding, before anything else

**`num_envs` buys zero server-side concurrency. The 8 sub-envs' round-trips are perfectly serialized on the main thread.**

The chain:

- `gymnasium/vector/sync_vector_env.py:251,276` — `for i, (action, _) in enumerate(...): self.envs[i].step(action)` under `AutoresetMode.DISABLED`. Strictly sequential.
- `single_agent_wrapper.py:77` → `poke_env/environment/env.py:400` `PokeEnv.step`
- `env.py:431,434` — `battle_queue.race_get(...)` → `env.py:74` `asyncio.run_coroutine_threadsafe(...).result()`. **Blocks the main thread until that battle's server reply lands.**

Env *i+1*'s action is not even sent until env *i*'s reply arrives. Each `PokeEnv` does spawn its own event loop and daemon thread (`env.py:265-266`) — 8 loops + 8 threads per lane — but they never overlap, because the main thread serializes entry into them. (Note: `rl/collect.py:13-19` describes poke-env scheduling onto the singleton `POKE_LOOP`; that is true of plain `Player`, **not** of `PokeEnv`, which training uses. Worth correcting that docstring.)

Consequence: a vector step costs `N × 1.85 ms`, so `steps/s = N/(N × 1.85 ms) ≈ 540` **regardless of N**. Raising `num_envs` on the current stack is worth <1% (see E1).

### Reframing the brief: the target is per-lane, not aggregate

6-wide today already measures 501-506 steps/s/lane (`SESSION_LOGS_PREDECESSOR.md:1299`) = **~3.0k aggregate with zero code**. But a 250M *run* lives in one lane, and 6-wide gives 5.7 days/lane. Aggregate throughput across independent seeds does not shorten any run.

**The number that must move is per-lane `time/steps_per_sec`: 540 → ≥1,400.** Aggregate ≥4.2k at 3-wide falls out of it.

---

## 1. Measured-bottleneck decomposition plan

### 1a. What I already measured this session (offline, no server touched)

`embed_battle` on a full 6v6 gen-1 battle, 1 torch thread:

| encoder | OBS_DIM | µs/call |
|---|---|---|
| v1 | 611 | **52.7** |
| v2 | 807 | **58.6** |

Actor MLP 611→512→512→26 (589,338 params), `torch.set_num_threads(1)`:

| batch | µs/batch | µs/sample |
|---|---|---|
| 1 | 19.1 | 19.11 |
| 2 | 162.2 | 81.12 |
| 8 | **170.4** | 21.30 |
| 16 | 187.8 | 11.73 |
| 32 | 174.4 | 5.45 |
| 64 | 238.0 | 3.72 |
| 256 | 842.1 | 3.29 |
| 512 | 1831.2 | 3.58 |

Three implications, all load-bearing:

1. **Inference is ~1.2% of the current vector step** (170 µs of 14.81 ms). It is not the bottleneck; GPU inference is unjustified (§3).
2. **Batching is nearly free at scale**: B=8→64 costs +68 µs for 8× the decisions. K can grow to 64+ without inference cost.
3. **The batch-2 anomaly reproduces** (81 µs/sample, 4× worse than batch-1's 19). This is a GEMV→GEMM threshold. Any "batch whatever is ready" drain must avoid steady-state batches of 2-4 — target B=1 or B≥16.

### 1b. The budget as it stands

Basis: self-play 3-wide, 540 steps/s/lane, `num_envs: 8` (`configs/showdown_sp12m_v2.yaml:70`), split 94.8% collect / 5.2% update (`SESSION_LOGS_PREDECESSOR.md:1324-1325`).

```
vector step            14.81 ms  (8 steps / 540 s⁻¹)
├─ update               0.77 ms  (5.2%)  = 96 µs/env-step
└─ collect             14.04 ms  (94.8%)
   ├─ agent.act B=8     0.17 ms  (1.2%)   measured
   └─ envs.step        13.87 ms  = 8 × 1.73 ms serialized

per sub-env step (1.73 ms), self-play:
   embed_battle ×3      158 µs   env.py:449 (used) + env.py:453 (DISCARDED) + showdown.py:621 (pool member)
   AgentOpponent B=1     19 µs   pool.py:83-88
   masks ×3 + orders ×2 ~40 µs   est.
   ────────────────────────────
   attributed           217 µs  (13%)
   RESIDUAL           ~1.51 ms  (87%)  ← websocket RTT + Node sim + poke-env parse + cross-thread handoff
```

**~80% of the whole training loop is that residual, and the main thread is idle for most of it.** Corroboration: node CPU measured ~1 core total across 3 lanes on a 10-P-core box (`SESSION_LOGS_PREDECESSOR.md:1122`) — the server is ~10% utilized. The wait is latency, not saturation, therefore overlappable.

Note also `env.py:449` vs `:453`: `PokeEnv.step` encodes **both** battles every step; `SingleAgentWrapper.step:79` uses only agent1's. One full 611-dim encode per step is computed and thrown away.

### 1c. The experiments, in order (each ≤10 min)

**E1 — Serialization proof.** `num_envs ∈ {1,2,4,8,16}`, 1 lane, 30k steps, read `time/steps_per_sec`. Hold `rollout_steps × num_envs` constant so the update cadence doesn't move (the reason the 2026-08 sweep was dropped, `SESSION_LOGS_PREDECESSOR.md:1213-1225`; irrelevant here because we read *no* learning metric).
- **Flat in N** → serialization confirmed, Stage 2 is the whole answer, `num_envs` closed as a lever forever.
- **Rises with N** → the residual is server-side queueing, not main-thread blocking; re-open §2a (servers) ahead of §2b.

**E2 — reset vs step.** Separate timers around `envs.reset` (`train.py:465`) and `envs.step` (`train.py:375`). Each episode costs a full challenge/accept handshake (`env.py:495-502`, `battle_against(n_battles=1)` then a blocking `battle_queue.get`). At 24.2-step episodes × 8 envs, one reset fires every ~3 vector steps.
- **reset > 20% of collect** → per-episode matchmaking is first-class; the architecture must pipeline battle creation. This is exactly what ps-ppo's `rlspawn.ts` autospawn solves server-side (`rlspawn.ts:162-210`); the cheap client-side version is one pre-challenged spare per slot.
- **< 5%** → ignore; concurrency absorbs it.

**E3 — Sub-env decomposition.** `POKEMON_RL_PROFILE=1` timers around `ShowdownSingles.embed_battle`, `SinglesEnv.get_action_mask`, `opponent.choose_move`, and the `race_get` block. Report µs/decision each. Predicted from 1b: encode 158, opponent 19, masks/orders 40, `race_get` residual ~1.5 ms.
- **race_get > 70% of the sub-env step** → idle wait; concurrency converts it 1:1. This is the number Stage 2 is priced against.
- **< 40%** → the residual is CPU (poke-env parse), concurrency gives only partial relief, and the ceiling in §5 must be cut roughly in half.

**E4 — Is the residual wait or Node saturation?**
- **(a)** `top` on the node process group at 1 / 2 / 3 lanes. Prior reading says ~1 core at 3 lanes. If node < 1.5 cores → server has ≥6× headroom → one server suffices.
- **(b)** `scripts/showdown_throughput.py c --workers 1 --servers shared` against the existing `:8000`, sweeping in-flight ∈ {1,8,16,32,64}. **Read the SHAPE only, never the absolute number** — the script hardcodes `[64,64]` (CLAUDE.md landmine, root cause of two prior misreads, `SESSION_LOGS_PREDECESSOR.md:1205-1207`). The knee of the curve *is* the K to build for. **Then spend the ~5 lines to patch a local copy to `[512,512]` + the 611-dim encoder** — that single fix makes it the only trustworthy full-loop predictor we have, and it must be done before any absolute claim in §5 is defended.

**E5/E6 — done** (§1a). Record as-is.

**Open question E4 must settle:** does the recorded 11,313 dec/s single-server ceiling (`SESSION_LOGS_PREDECESSOR.md:1162-1166`) count one seat or two? At a 5k learner-steps/s self-play target both seats decide, so the server sees ~10k dec/s — 88% of that ceiling. The N-server verdict in §3 flips on this.

---

## 2. Candidate architecture, staged

### Stage 0 — Instrument (no behavior change)
New `scripts/profile_collect.py` (~150 lines) + a profile block in `_vector_loop` (~15 lines at `train.py:372-380`) + the `showdown_throughput.py` width patch (~5 lines). Runs E1-E4.

### Stage 1 — Delete the wasted work (optional; keeps SyncVectorEnv)
Return a cached zero vector from `ShowdownSingles.embed_battle` (`showdown.py:512-513`) when `battle is self.battle2` — that encode is discarded at `single_agent_wrapper.py:79`. **Gain +3%.** Feeding the pool member the already-computed obs instead of re-encoding (`showdown.py:621`) is awkward across the wrapper boundary and probably not worth it.

**Honest assessment: Stage 1 is a control for the instrumentation, not a win.** Ship it only if E3's encode attribution disagrees with §1a.

### Stage 2 — The async collector (this is where 3× lives)

**A hard constraint discovered while reading poke-env**: `PokeEnv.__init__` hardcodes `max_concurrent_battles=1` for both agents (`env.py:273,292`). It is not a parameter. **Therefore Stage 2 cannot extend the `PokeEnv`/`SinglesEnv`/`SingleAgentWrapper` stack — it must be built on plain `Player`, which is exactly what `rl/collect.py`'s `SeamPlayer` already is (`collect.py:63-84`).**

This is architecturally excellent news, because it cleanly splits the two paths:

- **Training** → the Player/seam path (new).
- **Eval** → the `ShowdownEnv`/`PokeEnv` scalar path (`make.py:123-143`), **completely untouched**, which is what makes the locked eval protocol survive the change by construction.
- `embed_battle` is already module-level for exactly this reason (`showdown.py:229-233`, docstring says so), and `scripts/obs_fidelity_check.py` already exists to prove the paths agree.

Design (ps-ppo's sync-main-thread / async-bridge, `worker.py:361-459`, adapted):

1. One process, one asyncio loop, **K concurrent battles** (K=32-64), each a `SeamPlayer`-derived learner + one opponent player.
2. Battle coroutines submit `(obs, mask, battle_tag)` to a queue and `await` a future — `InferenceSeam.request` generalized from batch-1 to batched. **`collect.py:7-12` pre-registers this exact change**: *"Batch-1 servicing is the initial implementation; micro-batched or lockstep-vector servicing changes the seam's internals only."*
3. Sync main thread: blocking `get`, short non-blocking drain, **one batched forward**, resolve futures via `loop.call_soon_threadsafe`, append rows to per-battle buffers.
4. On battle end: finalize the episode (rewards, `dones[-1]=1`, per-episode GAE with `last_value=0`), push to a flat dataset with a `lengths` vector.
5. Update when the dataset reaches the step budget. **No barrier** — learn only from finished episodes.

**Why no barrier**: a strict K-wide barrier costs `max` over K round-trips, not the mean, and every tick would pay the slowest reset's challenge handshake. ps-ppo's drain (`worker.py:452-458`) services whoever is ready. The price — a modest over-representation of short episodes at the cut — is quantified and gated in §4/G8.

**Why per-episode GAE is strictly simpler**: within an episode `next_value = values[t+1]`, terminal bootstraps to 0. No `next_obs` array, no truncation bootstrap. Our `ShowdownEnv.step` already forces `terminated, truncated = True, False` at every finish (`showdown.py:764`), so `last_value=0` is already what happens today — the semantics carry over exactly. It also **deletes the second critic pass** at `ppo.py:460`, cutting the update's critic forward ~50%.

**Cost:**

| file | change | lines |
|---|---|---|
| `rl/envs/showdown_async.py` | NEW — collector, battle lifecycle, account naming | ~350 |
| `rl/collect.py` | `InferenceSeam` batch-1 → batched drain (`:37-60`) | ~40 |
| `rl/buffers/episode.py` | NEW — flat dataset + `lengths` + per-episode GAE | ~120 |
| `rl/agents/ppo.py` | recorded `old_logp`, drop `next_obs` pass, per-episode GAE (`:421-480`) | ~80 |
| `rl/train.py` | `_async_loop` beside `_vector_loop`; fork at `:229-232` | ~120 |
| `rl/envs/showdown.py` | `PoolPlayer`/`MixturePlayer` per-battle-tag dicts | ~20 |
| tests + config | G1-G6 | ~220 |

**≈950 lines across 7 files. 2-4 evening sessions.** Not a small change; say so up front.

### Stage 3 — Batched inference at K≥32
Falls out of Stage 2's drain; ~0 extra lines. The only decision is the drain window (ps-ppo uses a bare `time.sleep(0.003)`, `worker.py:453`). **Recommend an adaptive drain** given the batch-2 anomaly: blocking get → non-blocking drain → if `2 ≤ B ≤ 15`, wait up to 1 ms more. Never sit in the B=2-4 regime.

### Stage 4 — Process layout for 10 P-cores

| component | count | cores | note |
|---|---|---|---|
| Showdown server | 1 proc, `simulator: 4` | 2.5-3 @ 10k dec/s | measured ~1 core @ 1.6k dec/s |
| Python lanes | 3 procs × (main + loop thread) | ~1.2 each = 3.6 | GIL-bound |
| **total** | | **6.1-6.6 of 10** | 4 E-cores absorb OS/wandb/eval |

- **`torch_threads: 1`, `OMP_NUM_THREADS=1` — unchanged.** At B=8-64 the forward is 170-238 µs; multithreaded GEMM overhead exceeds the gain at these sizes (measured above; corroborated by SAC 425→327 at 4 threads). **Revisit only for the update**, and only if minibatches reach ≥2048 (B=512 measured 1,831 µs) and `time/update_sec` exceeds 25% of the loop.
- **NEW finding — `network: 1`.** `showdown/config/config.js:105` still sets `network: 1`; only `simulator` was raised to 4 (`:111`). Its own comment (`:100-104`) says additional network processes "will likely give you the best performance." At 3 lanes × 64 battles = 192 websockets, the single network process is a live bottleneck candidate. **One-line contingency, gated on E4(a).**
- **Do not run 6 lanes.** 6-wide measures 501-506/lane today; under Stage 2 each lane demands ~3× the server throughput, so 6 lanes would saturate node and cost per-lane speed — which is the metric that matters (§0).
- `server_configuration` passthrough (~15 lines: `showdown.py:675-700` + the collector) is the 2-server contingency, gated on E4.

### Risks, per stage

| risk | where | severity | mitigation |
|---|---|---|---|
| **`old_logp` recompute is silently wrong** | `ppo.py:452-463`; comment at `:453-455` states the now-false assumption *"the policy hasn't changed since it acted"* | **CRITICAL, silent** | Record `old_logp` at act time. Without this the first-epoch ratio is exactly 1.0 by construction (`:458`), `clip_frac`→0, `approx_kl`→0, and the run looks perfectly healthy while doing uncorrected vanilla PG on stale rows. Gated in G5. |
| **`PoolPlayer` latch is a race under K battles** | `showdown.py:596-598, 618-620` — one `self._battle_tag` / `self._current`; docstring at `:575-577` states the one-battle-at-a-time assumption | **CRITICAL, silent** | With interleaved battles the latch flips on every alternation → `select()` re-draws per decision → per-episode swap boundary destroyed AND `report_outcome` (`:603-609`) credits the wrong member, corrupting PFSP forever with no metric that looks wrong. Convert both fields to per-battle-tag dicts. Same bug in `MixturePlayer` (`:556-565`). Gated in G6a. |
| **Username collisions at K account pairs** | `env.py:269` `AccountConfiguration.generate(rand=True)` off global `random`, seeded by `rl/common/seeding.py` | HIGH | 3 lanes × 64 slots = 384 accounts. Derive names deterministically as `f"rl{seed:03d}s{slot:03d}a/b"` (≤18 chars) instead of drawing from global random. Makes collisions structurally impossible across distinct-seed lanes and removes the ordering dependence. **Required, not optional** — this is the CLAUDE.md landmine at scale. |
| **Pool push spans in-flight battles** | `train.py:415-421, 431` | MEDIUM, accepted | Members freeze at push (`pool.py:77`) and `select()` fires once per battle, so a battle always plays ONE frozen member end-to-end even across a push — the per-episode invariant survives automatically. What degrades is "distribution fixed within a rollout." **Pre-register as a deliberate deviation: fixed within a *battle*, not a rollout.** The invariant's content is stationarity (variance), not PPO ratio correctness — the ratio is over the learner's policy, not the opponent's. |
| **Length bias from the no-barrier cut** | Stage 2 design | MEDIUM | At K=32-64 and 24.2-step episodes, an 8192-step window holds ~340 episodes; the in-flight tail is 10-19%. Gate `rollout/episode_length` to [23.2, 25.6] (G8). |
| **Ties scored as losses** | ps-ppo ships this bug (`worker.py:553`, both self-play seats get −1 on a tie) | MEDIUM | Our `battle_outcome` (`showdown.py:516-522`) is correct. **Preserve it and regression-test it** — it is exactly the bug to inherit by accident when copying their finalize path. |
| **Abandoned battles fabricate a terminal** | new finalize path | MEDIUM | Discard partial trajectories; count and log. Gate <1% (G4). |
| **Wait states** | `showdown.py:737-740` pump absorbs 6.4% of raw steps | LOW | Under the `Player` path `choose_move` is only called when a decision is required, so wait states never materialize. Assert rather than assume (G3). |
| SIGSEGV in torch lazy static init at lane start | CLAUDE.md landmine | LOW | Unchanged: stagger lane starts, verify every lane individually by battle *progress*. |

---

## 3. What NOT to build — with the arithmetic

**GPU / MPS inference — CUT, unconditionally (for the MLP trunk).**
At B=64 the forward is 238 µs / 64 = **3.7 µs per decision** against a ~500 µs decision budget = 0.7%. A *perfect* accelerator buys ≤0.7%. MPS is flaky for this workload (CLAUDE.md). **Reopen only if the trunk changes**: `SESSION_LOGS.md:1748` records that a d128/L2 pointer trunk inverts the split to ~55-60% *update* — that is a GPU decision about the update, and a different question.

**Ray / multi-node — CUT.**
One box, 10 P-cores, 3 independent lanes. Ray's value is cross-machine scheduling and a shared object store; we need neither. ps-ppo's Ray layout manufactured its own bottleneck: a single-threaded central `InferenceActor` with no `max_concurrency` serializing all 10 workers, and a blocking `ray.get` weight sync *inside* `infer_batch` (`inference.py:236-259`) that can stall every battle in the cluster for ~3 s every 5 s. Their batches are therefore per-worker (≤192), not global (≤1600) — 10× the kernel-launch overhead for 1/10th the batch.

**`AsyncVectorEnv` / subprocess vector envs — CUT PERMANENTLY.**
Structurally forbidden: poke-env's loop does not survive `fork` (deadlock), and `forkserver` reseeds identically across workers → identical account names → `|nametaken|` swallowed in a fire-and-forget task → presents as 8× 60 s "Agent is not challenging" *naming the wrong cause* (`SESSION_LOGS_PREDECESSOR.md:347-351`). Concurrency must be intra-process on one event loop.

**Raising `num_envs` on the current stack — CUT (E1 closes it).**
`sync_vector_env.py:251,276` serializes, so `steps/s = N/(N × 1.85 ms)` is constant in N. The only gain is inference batching: 170 µs of a 14.81 ms tick at N=8 → 174 µs of a 59.2 ms tick at N=32. **Total possible gain <1%.** E1's value is closing the door, not opening one.

**`rlspawn.ts` — CUT, with a stated cut-line.**
261 lines of TypeScript + a server rebuild + a ~120-line client reconcile/rescue loop (`worker.py:325-355`) + a GC sweeper. ps-ppo needs it *only* because they run 32 battles between **one** username pair, which PS's challenge system cannot do (`rlspawn.ts:162-210`). We use K distinct account pairs, so poke-env's normal `battle_against` path works — it works today. Arithmetic on what we'd be avoiding: at 24.2-step episodes a handshake of H ms amortizes to H/24.2 per decision; a 12 ms handshake is 496 µs/decision *if serialized* (≈100% of the budget — hence E2 matters) but ≈0 when overlapped, since only ~1/24 of slots are resetting at any instant and their waits overlap with others' play. **Concurrency alone should absorb it.** Cut-line: build a spawn plugin only if E2 shows reset >25% of collect **and** a client-side pre-challenge pipeline (~30 lines, one spare challenged battle per slot) fails to recover it.

**N-process Showdown servers — DEFER to a 2-server contingency, do not build 10.**
ps-ppo ran 10-11 server processes because they set **no `simulator: N` at all** (`start_servers.sh` ships no `config.js`; the whole strategy is one PS process per core). We already have `simulator: 4` (`showdown/config/config.js:111`), which does the same thing inside one server and measured **+26-50% better** than server-per-worker (`SESSION_LOGS_PREDECESSOR.md:1167-1169`). One server's measured ceiling is 11,313 dec/s.
**But the margin is thinner than it looks**: a 5k learner-steps/s self-play target puts ~10k dec/s on the server = 88% of that ceiling. So: keep 1 server as default, thread `server_configuration` through (~15 lines), and pre-register a 2-server split. **Build it only if E4(a) shows node >2.5 cores or E4(b) plateaus below 10k dec/s.** Try `network: 2` first — one line.

**Reminder on the number everyone repeats**: "`simulator: 4` = +81%" is **collection-only**. End-to-end it measured **+3.7%** (`SESSION_LOGS_PREDECESSOR.md:1180-1182`). Collection-only benchmarks overstate full-loop gains ~7× on this project's own record. No claim in §5 rests on one.

---

## 4. Acceptance gates — pre-registerable R0

Bitwise-equivalent learning is impossible (different battle streams, server-rolled teams — `showdown.py:26-28`). What IS asserted:

**G1 — Obs contract, elementwise.** For ≥2,000 live decisions, the async collector's `(obs, mask)` equals what the `PokeEnv` path produces on the same battle state. Extend `scripts/obs_fidelity_check.py`'s existing pattern (it already proves live == tape replay **bitwise on float32, not allclose**, `:26-33`). Assert `ENCODER_FINGERPRINT` (`showdown.py:149-153`) identical in both run dirs' `meta.yaml`. Failure prints the first differing feature index.

**G2 — Mask contract.** (a) every row's mask has ≥1 `True`; (b) the sampled action is always inside the mask — `action_to_order` runs at poke-env's strict default and must *raise*, never degrade to random (`collect.py:70-72`); (c) masking goes through `rl/common/masking` with the finite `-1e8` sentinel, no `mask is None` branch; (d) the value head is never masked. Counters over a 10k-decision smoke; **0 violations**.

**G3 — Wait states never surface.** Assert `not battle.wait` at the learner's `choose_move` (the twin of `showdown.py:617` and `collect.py:132`). Report the equivalent of `waits_absorbed` as 0.

**G4 — Episode integrity.** Every submitted trajectory: (a) ends in a decided game, `battle_outcome ∈ {-1,0,+1}` (`showdown.py:516-522`); (b) `dones[-1]==1`, no interior done; (c) **ties score 0 for both seats** — explicit regression test, this is precisely the bug ps-ppo ships (`worker.py:553`); (d) abandoned battles are discarded, counted, logged. Gate: discard rate <1%.

**G5 — On-policyness.** `old_logp` recorded at act time and used as the PPO reference (required change at `ppo.py:452-463`). Gate: **first-epoch mean |ratio − 1| > 0** and `loss/clip_frac ∈ [0.01, 0.20]`. **If `clip_frac` reads exactly 0.0 in epoch 1, the recorded-logp path is not wired — kill the run.** Plus a staleness histogram `collect/policy_version_lag` = (update index at finalize) − (update index at act); gate **p99 ≤ 1**. (ps-ppo has no version tag at all — `learner.py:401-413` — and accepts ~2-3 updates of implicit lag; we can do better for ~10 lines.)

**G6 — Pool-swap boundaries.** (a) each battle is played end-to-end by exactly one member — test K=8 interleaved battles against the new per-battle-tag dicts; (b) `pool.push` / `pool.refresh` still fire once per `push_every_updates`, `selfplay/pool_size` grows on the same schedule as a matched pre-change run; (c) `selfplay/winrate_anchor` and `selfplay/winrate_latest` present and in (0,1). **Pre-registered deviation: the opponent distribution is now fixed within a battle, not within a rollout.**

**G7 — Eval protocol unchanged, no checkpoint invalidated.** The locked protocol runs `scripts/eval_checkpoint.py` on the scalar `ShowdownEnv` path (`make.py:123-143`), which Stage 2 does not touch. Gate: `git diff --stat` shows zero change under `rl/common/evaluation.py`, `scripts/eval_checkpoint.py`, `make_eval_env`; `OBS_DIM` and `ENCODER_FINGERPRINT` unchanged (CLAUDE.md: changing `OBS_DIM` invalidates every checkpoint — **this change must not**).

**G8 — Throughput, with protocol.** Metric: `time/steps_per_sec` (locked name), median over the run **excluding the first 200k steps and all eval ticks**, read from `scripts/extract_history.py <run_dir>` → `history.csv`. Report `time/collect_sec` and `time/update_sec` per rollout (locked names). Config: the `showdown_sp12m_v2.yaml` recipe, 3 lanes, distinct seeds, staggered starts, one server at `simulator: 4`. Commit docs before launching; launch from a clean tree.
- **PRIMARY:** median ≥ **1,400 steps/s/lane at 3-wide**, on **all three lanes**, vs the 540 basis. (≥2.5×; aggregate ≥4.2k.)
- **SECONDARY:** collect share falls 94.8% → <85%; `rollout/episode_length` mean ∈ **[23.2, 25.6]** (P6 band 24.2-24.6 ±1.0, `DESIGN.md:182`) — the length-bias detector for the no-barrier cut.
- **R0 sanity, first 200k steps:** `loss/entropy ∈ [0.2, 1.0]` for a scratch run (standing gate, `STATUS.md:53-54`); `eval/win_rate` present and in (0,1); G2 counter 0; G5 `clip_frac ≠ 0.0`.
- **Action on branch:** ≥1,400 → credited, proceed to the H&L-scale pre-registration. 900-1,400 → credited but short; run E4(b) to decide 2nd server vs accept. <900 → the residual was CPU not wait; stop, re-read E3, halve §5.

**G9 — Learning-behavior equivalence (the honest version).** A 12M self-play run on the new loop must land **within the noise band of the recorded 0.3890 basis** (scratch self-play 12M, v2 + fixed pool, `STATUS.md:18`) under the locked eval protocol. Band: **|Δ| < 0.025** — i.e. the re-architecture must NOT be creditable as a learning change *in either direction*. This is a **null-expected** gate. It is the only thing that catches a silent correctness break (staleness, length bias, pool corruption) that no throughput metric would show, and at Stage-2 speed it costs ~7 h — cheap insurance on a 250M commitment.

---

## 5. Wall-clock table

Per-lane throughput assumptions: current 540 (3-wide) / 734 (solo), both measured. Stage 2 central estimate derived from the per-decision CPU budget:

```
embed_battle, learner seat            53 µs (v1) / 59 (v2)   measured
embed_battle, opponent seat           53 / 59                measured
masks ×2 + order conversion ×2       ~40                     est.
policy forward, amortized B=32         5.5                   measured
opponent forward, amortized            5.5                   measured
poke-env parse + asyncio scheduling  250-400                 predecessor decomposition, ×2 seats
PPO update, amortized                 96                     derived from the 5.2% split
────────────────────────────────────────────────
total                                500-660 µs  →  1,520-2,000 steps/s/lane solo
at 3-wide, applying the measured −20% lane penalty  →  1,220-1,600/lane
```

Central: **1,400/lane at 3-wide (4.2k aggregate); 1,750 solo.** Corroborated in order of magnitude by the collection-only 2,237 dec/s at W=1 / 16-in-flight (`SESSION_LOGS_PREDECESSOR.md:1162`), but **E4(b) at the real width must confirm before this is defended.**

**3 lanes (= a complete 3-seed protocol result; wall clock is per-lane)**

| budget | now (540) | Stage 1 (580) | **Stage 2 (1,400)** | Stage 2+3+4 (1,600) |
|---|---|---|---|---|
| 12M | 6.2 h | 5.7 h | **2.4 h** | 2.1 h |
| 50M | 25.7 h | 24.0 h | **9.9 h** | 8.7 h |
| 250M | **128.6 h (5.4 d)** | 119.7 h (5.0 d) | **49.6 h (2.1 d)** | 43.4 h (1.8 d) |
| aggregate steps/s | 1.62k | 1.74k | **4.2k** | 4.8k |

**1 lane owning the box**

| budget | now (734) | Stage 2 (1,750) | Stage 2+3+4 (2,000) |
|---|---|---|---|
| 12M | 4.5 h | 1.9 h | 1.7 h |
| 50M | 18.9 h | 7.9 h | 6.9 h |
| 250M | 94.6 h (3.9 d) | **39.7 h (1.7 d)** | 34.7 h (1.4 d) |

**The brief's goal is met at Stage 2**: H&L-scale 2-3e8 decisions goes from ~5.4 days/lane to ~2.1 days/lane — with all three protocol seeds finishing *simultaneously*, which is the comparison that matters.

**Uncounted upside**: at K=64 and `rollout_steps=128` the buffer is 8192 rows; at `minibatches: 4` that is 2048/minibatch versus today's 256. The forward measured 3.58 µs/sample at B=512 vs 21.30 at B=8 — so per-step *update* cost should fall materially, and the 96 µs/step term above is conservative.

**Not in scope, priced for completeness**: a 1-learner / 3-collector layout (ps-ppo's model) would put ~5-6k steps/s behind a *single* run → 250M in 12-14 h. It costs the on-policyness guarantee (transitions one weight version stale) and a shared-memory transport. **Stage 5, only if a single 250M run must finish in under a day.** Stage 2 at 3-wide already clears the stated target.

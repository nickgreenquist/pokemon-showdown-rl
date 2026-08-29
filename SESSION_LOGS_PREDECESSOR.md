# SESSION_LOGS_PREDECESSOR — the capstone's record from the predecessor repo

Recovered 2026-08-05 from `deep-rl-from-scratch@5d6a604` (full SHA
`5d6a604f9bc129512cfd556418ea678874fe52fe`, the last commit before its capstone-strip commit
`0c3b972` deleted these 36 entries from that repo). Extraction: the strip commit's deletion
patch identified the 36 entry titles; each entry was then taken WHOLE from the pre-strip file,
byte-for-byte. Five retained spine entries also had passing capstone references scrubbed at
`0c3b972`; those fragments are not reproduced here (recoverable from that commit's patch).

**Read protocol: same as SESSION_LOGS.md** — index with `grep -n '^- 20'`, then Read the
chosen entry by offset/limit. Never a broad keyword grep.

**These are historical records, frozen as written.** Where later work corrected a claim, the
correction lives in this repo's SESSION_LOGS.md, which wins on conflict. Known instances:
"past the BC clone" was later corrected to "level with the clone" (2026-08-05 entry);
`showdown_scratch12m` is the pure self-play arm (finals 0.3800), mislabeled "12M flat 0.417"
in one rescue list. Appendices A and B preserve the predecessor README's Phase-5 results
section and its PLAN.md Phase-5 spec (same source revision), which the strip also deleted.

---

- 2026-07-28 (capstone hardware line revised — a parallel-session advisory evaluated and accepted) —
  **The "rented cloud GPU" line was confirmed inherited from the Procgen-era capstone plan (it
  survived the 2026-07-26 Phase-5 rewrite in PLAN.md, CLAUDE.md and README.md) and is replaced:
  online self-play is CPU-first; a GPU enters only for offline supervised arms, the Procgen
  fallback, or an encoder grown past MLP scale.** The advisory (a separate chat session, no repo
  access) cited the MinAtar threading finding; the repo actually holds three independent
  measurements of the same tiny-net pathology (MinAtar 278→~1,550; Connect 4 2,196→8,473; SAC
  425→327 *with more* threads), plus ms-scale websocket env steps against µs-scale forwards and
  on-policy's inability to keep a device utilized — the advisory and the repo's measurements agree
  everywhere they overlap. Throughput measurement is **deferred to Phase 5 start** (it needs the
  poke-env + Node stack, forbidden until Phase 4 closes) with a four-item pre-registered list now in
  the Phase 5 section. Two additions landed with the revision: the **BC-on-replays diagnostic**
  recorded as named-optional (the one genuinely GPU-shaped workload; Phase 4's
  supervised-on-solver-labels is the same instrument at small scale), and a **collection-loop
  structural contract** — a single inference seam between battle coroutines and the policy — adopted
  now because it is cheap before the loop exists and keeps batching a config choice rather than a
  rewrite. One advisory detail corrected in place: the batch-1 forward pathology belongs to
  poke-env's native asyncio `Player` model, while the `SubprocVecEnv` route already batches at the
  vector boundary (at head-of-line-blocking cost). Procgen-era sweep (the advisory's standing note):
  grep found no other stale assumptions — the three hardware lines were the full residue. Advisory
  file (untracked) deleted after folding in.
- 2026-07-29 (Phase 5 opens: env plumbing landed) — **Origin synced (23 Phase-4 commits pushed,
  explicit go-ahead), then the capstone's step 1 landed as approved: poke-env pin, local server, env
  + adapter, 278 tests green (7 new), 2 commits.** *Dependency*: `poke-env==0.15.0` (still
  PyPI-latest — the exact version the 2026-07-26 API review audited, so every correction in the
  Phase 5 section applies as written; drags in pettingzoo 1.26.1 + websockets 16.0). *Server*:
  `smogon/pokemon-showdown` pinned at `59da482` by `scripts/setup_showdown.sh` into gitignored
  `showdown/` (pin-by-sha shallow fetch verified against GitHub); config = the example plus
  `exports.repl = false` — the REPL unix sockets crash `EINVAL` at boot on macOS + Node 25 (two
  CRASH stacks in a clean boot log, zero with repl off; the battle worker is unaffected either way).
  *Env* (`rl/envs/showdown.py`, registered `Showdown-v0` through `make_env` like Connect4):
  `ShowdownSingles(SinglesEnv)` with terminal-only reward = outcome (the Phase 4 shape) and a
  deliberately minimal 10-dim placeholder encoder (move base powers, type multipliers vs the
  opposing active, fainted fractions — the encoder-design step replaces it), plus the `ShowdownEnv`
  adapter doing exactly the two contract translations the review pre-registered: mask lifted from
  the obs `Dict` into `info["action_mask"]`, and `info["outcome"]` read from `battle.won`/`lost`,
  never from term/trunc (forfeit/timer arrive `truncated` but decided — the server sends `|win|`;
  only a tie leaves `won` None). Gen 1 action space = 10 (6 switches + 4 moves, no gimmicks), pinned
  by test. **One API fact beyond the review: plain `int` actions crash poke-env's `action_to_order`
  (it calls `action.item()` on the gimmick check) — the adapter casts to `np.int64`.** *Tests*:
  outcome/reward/encoder/opponent-factory units run fully offline (`start_listening=False`); the
  integration test plays a live episode acting only through the mask under poke-env's `strict=True`,
  which is the masking proof — any illegal converted order raises — and skips when nothing listens
  on :8000. *Smoke numbers*: scripted RandomPlayer-vs-MaxBasePower, 5 battles in 0.9 s; through the
  full `make_env` stack, 10 episodes per fixed opponent — mask-random loses 0/10 to `max_power` and
  `heuristics`, wins 8/10 vs `random` (milestone-1 headroom confirmed in both directions), at
  **~1,100 agent-steps/s, one env, one process, no policy net** — the env-only prior the four
  pre-registered throughput measurements start from. *Next*: the throughput measurements need the
  collection-loop seam (the single-inference-seam contract) — decide with the maintainer whether
  that seam or the milestone-1 train wiring comes first; encoder design after the measurements say
  what `embed_battle` may cost.

- 2026-07-29 (collection seam + throughput measurements (a) and (b)) — **The single-inference-seam
  contract is now code (`rl/collect.py`: `InferenceSeam` + `SeamPlayer`, batch-1 servicing, numpy
  boundary, counters as the timing hooks; 281 tests green, 3 new) and the first two pre-registered
  measurements ran (`scripts/showdown_throughput.py`, policy = real mlp[64,64] actor+critic on the
  placeholder encoder, torch 1 thread).** Architecture fact the numbers ride on: poke-env schedules
  every battle coroutine onto its singleton `POKE_LOOP` (daemon thread), so all in-flight battles in
  a process share one loop and one seam services them all — batch-1 inference blocks the same loop
  that services the websockets, the pathology represented honestly. **(a) Per-turn latency, 20
  battles / 1,257 decisions, one in flight: ~0.72 ms/decision — encode 0.018 ms, batch-1 inference
  0.098 ms, env gap 0.541 ms (p50 0.496, p90 0.677)** — the gap is ~75% of a decision and decomposes
  into protocol parsing 0.079 ms (both seats), websocket ping RTT 0.086 ms, residual ~0.38 ms
  (server compute + event-loop scheduling). The placeholder encoder is 2.5% of a decision — encoder
  headroom is large, as the hardware note predicted. Instrumentation lesson recorded: timing the
  async `_handle_message` spans awaited suspensions (it contains the whole decision path) and
  produced 5.1 s of "parsing" inside a 0.94 s run — parse is timed at the sync
  `Battle.parse_message`/`parse_request` instead. **(b) Concurrency curve, one process: ~1,700
  decisions/s at 1 battle in flight → saturation ~3,400 at 16, flat through 32, slight decline at 64
  (256 battles/point); batch-1 inference share of wall rises 0.15 → ~0.27 at the plateau.** Two
  readings: the asyncio ceiling is ~2× the serial rate and arrives early (16 battles); and by Amdahl
  even FREE inference buys ≤1.37× at the plateau — micro-batching's best case (measurement (d)'s
  question) is bounded before the real encoder exists. Scale check: 3.4k decisions/s is the same
  order as Connect 4 PPO's 8.5k steps/s — a 2M-decision collection ≈ 10 min/process at the plateau,
  before learner overhead. *Next*: measurement (c) multi-process scaling (workers ×
  battles-per-worker, one server per worker vs shared); (d) waits on the real encoder; then
  milestone-1 train wiring picks its collection route from (b)+(c).

- 2026-07-29 (throughput measurement (c): multi-process scaling — the collection stack's numbers are
  now complete except (d)) — **W spawned workers, each the (b)-plateau loop (16 in flight, 128
  battles/worker, barrier-synced battling spans, pid-based account names — poke-env's default
  per-process class-name counter would collide on a shared server), aggregate = total decisions /
  slowest worker's wall; machine = 14 logical / 10 performance cores.** **Shared single server
  (:8000): 3,646 / 5,910 / 5,100 / 5,141 / 4,533 decisions/s at W = 1/2/4/8/12 — peaks at TWO
  workers and declines**, with mean per-worker inference share falling 0.26 → 0.05: the lone node
  process saturates and the python workers idle against it. **One server per worker (ports 8100+i,
  booted and torn down by the script): 2,468 / 4,377 / 7,341 / 7,545 / 7,276 at W = 1/2/4/8/12 —
  scales to ~7.5k decisions/s (~115 battles/s) at W = 4–8, flat after**: the machine ceiling with
  server and worker sharing the same cores. One anomaly recorded: per-worker W=1 (2,468) reads BELOW
  shared W=1 (3,646) — the per-worker server is freshly booted (cold JIT) where :8000 has been
  serving all evening; the crossover is at W≥3 regardless. **Provisioning arithmetic that falls
  out**: milestone-1-scale collection (2M decisions) ≈ 4.5 min at the multi-process ceiling or ~10
  min in ONE process — single-process native-asyncio collection through the seam (3.4–3.6k/s)
  already outruns the whole Connect 4 pipeline (8.5k steps/s but WITH learning), and the Gym-adapter
  serial path (1.1k/s) is the floor, not the plan. CPU-first re-confirmed from the collection side:
  inference share never exceeds ~0.27 anywhere on the curve, so no accelerator changes any of these
  numbers. *Remaining*: measurement (d) (forward-pass share, batch-1 vs batched) waits on the real
  encoder; milestone-1 wiring now picks its collection route with (a)–(c) in hand — the open
  question is seam-loop-native vs `SubprocVecEnv`-over-Gym for TRAINING (the rollout buffer
  boundary), not for raw collection, where the seam route has won on measurement.

- 2026-07-29 (collection-architecture fork settled by a three-review pass; two env bugs found and
  fixed; milestone-1 config landed and smoked) — **The maintainer directed a three-reviewer
  adversarial pass (independent sessions, different lenses: correctness / harness integration /
  shipping pragmatism) over the proposed seam-native collector, and the proposal was REJECTED
  unanimously — the decision of record is now: milestone 1 trains on the zero-new-code path,
  `SyncVectorEnv` over `Showdown-v0`.** The three independent kill shots, each verified in source or
  measured live: (1) *correctness* — `PPOAgent.update` recomputes `old_logp`/values at drain on the
  premise "the policy hasn't changed since it acted" (`ppo.py:388-399`); battles spanning an
  `update()` violate it and the recompute forces ratio=1 on stale rows, silently, while also
  breaking the repo's `lr=0 ⇒ approx_kl==0` masking probe; (2) *concurrency* — "stop servicing the
  seam" is not a barrier (a request already inside the forward reads tensors `optimizer.step()` is
  mutating; `Categorical.sample` and `randperm` share the global torch generator across threads);
  (3) *economics* — measured process CPU/wall is **0.97 at just 8 battles in flight**, so the async
  collector recovers idle that does not exist: ≤15% over a lockstep facade at 2–4× the code, on a
  milestone whose slowest path (~1.2k dec/s, measured through `make_vec_env` working TODAY with
  `reset_mask` intact) finishes 2M decisions in ~30 min. **Two live bugs found in the landed
  adapter, both fixed with a stub-tested pump/remap in `ShowdownEnv.step` (battery `phase5_env.py`:
  4/4 real caught, 1/1 control survives)**: (i) *phantom transitions, measured 6.4% of raw steps vs
  max_power* — at `battle._wait` poke-env never asks our seat to move, `PokeEnv.step` silently
  discards the caller's action yet returns a full transition with a placeholder one-legal mask, rows
  with zero policy gradient that still skew advantage normalization, the entropy readout (Phase 4's
  health metric), and episode lengths; now absorbed inside `step()` (with a `waits_absorbed` counter
  and a live regression test) and guarded by an assert so any future discard path fails loudly; (ii)
  *truncation double-count* — poke-env marks forfeits/ties/timer losses `truncated=True`, and
  `compute_gae` keeps the bootstrap on truncated rows, stacking γ·V(final) on top of the terminal ±1
  at γ=1.0; every learner-visible finish is a completed game (reset/close-injected forfeits never
  surface), so finishes now map to `terminated=True` unconditionally. Also verified for later: the
  pause premise holds server-side (an order held 150 s mid-battle resumed cleanly; the 20 s
  `ping_timeout` is the real budget if POKE_LOOP itself ever blocks). **Named and deferred**: the
  decision-lockstep facade behind `make_vec_env` (owns both seats → batches opponent forwards, keeps
  `rl/train.py`/`RolloutBuffer`/PPO/pool wiring untouched) is the follow-up if the wall binds, gated
  on pre-registered **measurement (e)** — challenge-to-first-request slot-reset latency plus actual
  facade decisions/s vs the (b) curve, because 1,100-vs-3,400 was concurrency-vs-serial, not
  architecture-vs-architecture; the seam collector stays scoped to self-play scale with its three
  preconditions written down (collection-time logp/value storage, drain-to-quiescence barrier,
  forfeit-leak tagging). **`configs/showdown_maxbp_ppo.yaml` landed** (Phase 4 recipe where reasons
  transfer: γ=1.0 terminal-only, λ=0.95, clip 0.2, entropy 0.01; mlp[64,64] on the placeholder
  encoder; 8 envs × 128 rollout = the 1024 cadence) **and an 8,192-step smoke through the full
  harness ran clean**: all locked metric names emitted, eval/win_rate 0.2–0.4 vs max_power for an
  untrained policy with win-rate/return arithmetic mutually consistent, episode length 25–44,
  **~1,050 steps/s through the complete loop** — collection plus learning, on the predicted number.
  287 tests green. *Next*: the 2M milestone-1 run in the maintainer's terminal from a clean tree,
  then read the curve.

- 2026-07-29 (MILESTONE 1 PASSED: PPO beats MaxBasePowerPlayer — and the encoder is confirmed as
  milestone 2's lever) — **The 2M-step run (`showdown_maxbp_s0`, maintainer's terminal, clean tree
  at `31662e9`, `git_dirty: false`, ~34 min at 983 steps/s median) trained clean, and the headline
  stands on the locked protocol: FINAL checkpoint (never best — selection bias), 1,000 fresh battles
  at seeds past the training-eval ladder — 663/1000, win rate 0.663 ± 0.029 (95% CI), ties 2.5%.**
  The CI floor (0.634) clears the beat-the-bot bar without argument. Curve reads, all healthy:
  `eval/win_rate` 0.29 at 100k → plateau ~0.65 ± 0.05 from 500k on, final rung 0.72 (in-training
  rungs are 100-episode estimates, SE ≈ 0.05 — the 0.52 dip at 1.8M is noise-band); entropy 1.74 →
  0.58 with no collapse (against masked-max ≈ ln 10 = 2.30) — the phantom-row fix means this number
  is now trustworthy; `approx_kl` ≤ 0.004 throughout; `loss/value` RISES 0.16 → 0.34, the benign
  twin this time — early play loses near-deterministically (predictable −1), a ~0.65-win policy has
  genuinely uncertain outcomes (outcome variance ≈ 0.9, so 0.34 still carries real signal); episode
  length 33 → 24.5 (it wins faster, not just more). **The milestone-2 price, measured the same night
  (500-battle scratch probe, same final checkpoint, `eval_opponent` overridden to heuristics): 0.262
  ± 0.039** — the three-review pass's prediction confirmed in BOTH directions: the 10-dim
  placeholder encoder, whose only tactical content is move base power and type multipliers, is
  exactly sufficient against a bot that ignores type effectiveness and roughly a random policy's
  showing against `SimpleHeuristicsPlayer` (which reads HP, status, boosts, switch value — none of
  which the encoder represents). Phase 4's closing lesson lands intact on the new domain: the
  ceiling is what the policy can SEE and VISIT, not the training signal — `eval/win_rate` vs
  max_power plateaued by 500k with 1.5M steps buying ~nothing, the same shape as every Connect 4
  arm. *Next, in order*: encoder design (the real Phase 5 design work — observed-state features per
  PLAN's capstone spec; run measurement (d) forward-pass share at the real encoder while at it),
  then the milestone-2 run vs `SimpleHeuristicsPlayer`; the lockstep facade stays parked unless the
  wall binds. `final_eval_maxbp_1000.json` in the run dir is the headline artifact.

- 2026-07-30 (encoder design landed: the Gen 1 observable-state encoder replaces the placeholder;
  measurement (d) complete; milestone-2 config ready) — **Maintainer-approved design session settled
  the four pre-stated decision points: (1) NO species embedding — species identity enters only
  through base stats + types, both derivable from the observed species, so the obs stays a flat Box
  and the harness is untouched (an embedding table is the priced follow-up if milestone 2 stalls);
  (2) engineered type-chart multipliers AND raw type one-hots — the multiplier is the directly
  decision-relevant scalar under terminal-only reward, the one-hots let the net learn what the
  scalar can't express; (3) boosts as raw stage/6; (4) full 5-slot opponent bench blocks
  (revealed-or-zeros behind a revealed flag). OBS_DIM 10 → 611.** Layout (rl/envs/showdown.py, all
  offsets documented in fill helpers): global(5: turn, fainted fractions, force_switch, trapped) |
  our 6 team blocks (32 each: hp, fainted, is-active, status one-hot, level, 5 base stats, 15-type
  one-hot, best-multiplier matchup both directions vs the opposing active — the switch-value signal
  SimpleHeuristicsPlayer reads) | our active extras (16: 7 boosts, 7 volatiles, status_counter,
  preparing) | our 4 move blocks (23 each: known, bp, acc, PP fraction, multiplier vs foe,
  physical/status flags, priority, 15-type one-hot) | opponent mirror (revealed mons and revealed
  moves only — the information-set line). **Slot alignment pinned from poke-env source
  (singles_env.py): switch action i = list(battle.team.values())[i], move action 6+j =
  list(active.moves.values())[:4][j] — team and move blocks use exactly those orderings so the
  policy can associate slot-i features with action i.** One representational gap, documented not
  fudged: Gen 1 Light Screen is a per-mon volatile the sim emits as "|-start|...|Light Screen",
  which poke-env 0.15.0 maps to Effect.UNKNOWN (no LIGHT_SCREEN member) — dropped rather than
  parser-forked; Reflect parses fine. **Measurement (d) (new `showdown_throughput.py d`, offline
  forward microbench at the real encoder): batch-1 forward 58µs at 611 dims, per-sample 1.6µs at
  batch 128 (~37× batching headroom that nothing currently needs). Measurement (a) rerun live at the
  real encoder: encode 0.079ms/decision (4.4× the placeholder's 0.018 but still ~11% of the 0.71ms
  decision), inference 0.089ms, env gap unchanged at 0.545ms (~75%) — the encoder is NOT the
  bottleneck and no collection-architecture change is warranted, exactly as the hardware note
  predicted.** 8,192-step smoke through the full harness vs heuristics (config pattern, tensorboard
  logger): all locked metrics emitted, eval/win_rate 0–0.05 for a near-untrained policy (consistent
  with mask-random's 0/10), entropy 1.69 vs masked-max 2.30, value loss falling, win-rate/return
  arithmetic mutually consistent (−0.85 at 20 eps = 1W/1T/18L), **~870–1,000 steps/s through the
  complete loop — the 611-dim encoder costs ~8% against milestone 1's ~1,050, so the 2M milestone-2
  run stays ~35–40 min**. 290 tests green (5 new encoder tests — layout, slot order, per-block
  features, bounds — replacing the 2 placeholder tests; both live-server integration tests pass at
  the new encoder under strict=True). `configs/showdown_heuristics_ppo.yaml` landed: the milestone-1
  recipe verbatim except `opponent: heuristics` — hidden_sizes stays [64,64] on Phase 4's capacity
  finding. *Next*: the 2M milestone-2 run in the maintainer's terminal from a clean tree, then the
  locked-protocol 1000-battle final-checkpoint eval.

- 2026-07-30 (milestone-2 first run at the real encoder: NOT passed at 2M — but the curve never
  plateaued, which is the finding) — **`showdown_heur_s0` (2M steps vs SimpleHeuristicsPlayer,
  maintainer's terminal, 37.7 min at ~850 steps/s median). Provenance: stamped sha `7a4155f` with
  `git_dirty: true` — unavoidable and correct this once: the encoder the run trains on IS the
  uncommitted 2026-07-30 session work (six files, verified as the whole diff); the tree goes into
  the commits byte-identical, so the stamp resolves to those commits.** Headline on the locked
  protocol (FINAL checkpoint, 1000 fresh battles, seeds past the training ladder,
  `final_eval_heur_1000.json`): **292/1000, win rate 0.292 ± 0.028 (95% CI [0.264, 0.320]), ties
  1.7% — the beat-the-bot bar is not met.** The curve is the real result: `eval/win_rate` 0.06 at
  100k → 0.31–0.40 band at 1.8–2M and **still climbing at the wall — no plateau, where milestone 1
  plateaued by 500k with 1.5M wasted steps.** The encoder unambiguously moved the needle within-run
  (untrained smoke 0.00–0.05 → 0.40 peak rung; the milestone-1 placeholder policy sat at 0.26 and
  could not represent HP/status/boosts at all — cross-protocol, so indicative not paired). Secondary
  reads: entropy 1.72 → 0.355, lower than milestone-1's 0.58 endpoint and still falling — a watch
  item for a longer run (the Phase 4 entropy-floor lever is the tested instrument if it collapses);
  `loss/value` rises 0.15 → 0.26, the benign twin again (outcome variance at p≈0.3 is ~0.82, so 0.26
  MSE carries real signal); `approx_kl` ≈ 0.002 throughout; episode length 25 → 20. *Next, discussed
  with the maintainer*: budget is the obvious single-variable lever — a longer run (~19 min/M steps)
  before touching entropy floors or opponent mixing; both stay named fallbacks from Phase 4 if the
  curve stalls short of 0.5.

- 2026-07-31 (distribution lever at fixed-bot scale: NOT credited — the pre-registered band read
  fires 'at/below', and milestone-3 self-play moves up; first 3-seed read of the campaign) —
  **`showdown_mix512_s{0,1,2}` (70/20/10 heuristics/max_power/random MixturePlayer on the 512 trunk,
  6M × 3 seeds CONCURRENT — the Stage-0 pattern's first campaign use: ~653 steps/s each, all three
  in one ~2.6 h window; wandb behaved, exactly one offline-run dir per run). Locked-protocol
  headlines: 0.348 / 0.358 / 0.363, pooled 1069/3000 = 0.356 ± 0.017 — and the matched-budget
  control, run for exactly this comparison: the PURE-heuristics 512 run's 6M checkpoint under the
  same locked protocol scores 0.324 ± 0.029.** The pre-registered read (config header) was the
  RUNG-BAND comparison, and it fires 'at/below': mixture 4–6M bands 0.357/0.348/0.337 (mean 0.347)
  vs the capacity run's 0.346 — indistinguishable. The locked-eval comparison leans positive (+0.032
  pooled-vs-control, z ≈ 1.9, p ≈ 0.06 — marginal; plausibly inflated by the control checkpoint
  sitting in a rung dip, 0.324 vs its own 0.346 band) — so the honest bracket on the mixture effect
  at this scale is 0 to +0.03: REAL at most as a nudge, nowhere near the 0.09–0.14 gap, and the
  per-battle mechanism worked as designed (live-smoked 8/3/1 pick split; mixture seeds hold entropy
  HIGHER at 6M — 0.32–0.43 vs pure's ~0.30 — the random/max_power battles keep the policy stochastic
  without translating into eval strength). **Per pre-registration: fixed-bot state coverage is NOT
  the remaining constraint — milestone-3 self-play moves up the queue.** Methodological bonus, the
  campaign's first n=3: seed-std of the locked headline is 0.008 — far tighter than Phase 4's Elo
  spreads led us to fear at this budget — so the earlier n=1 lever reads (budget, capacity)
  retroactively gain credibility, and 3-seed reads are cheap enough (~2.6 h) to be the default going
  forward. Lever ledger for milestone 2 to date, all locked-protocol: encoder 0.262→(enabling),
  budget 0.292→0.358 (credited, exhausted), capacity 0.324@6M→0.408@12M (credited, biggest single
  lever, curve still creeping), distribution-via-fixed-bots ≤+0.03 (not credited). *Next*:
  milestone-3 self-play machinery — the Phase-4 pool + the seat-2 Player adapter driving our policy
  (not yet written), with the parked lockstep facade as the collection architecture of record there
  (async review 2026-07-30) and eval anchored on heuristics throughout (the milestone-2 bar stays
  the scoreboard; H&L and Metamon both got their strength from self-play + diversity, not fixed-bot
  grinding).

- 2026-07-31 (Stage-0 probe: concurrent seeded runs PASS — async shelved, campaign moves to 3-seed
  lever reads) — **The pre-registered free-lever probe (`configs/showdown_probe_100k.yaml`,
  timing-only 100k at the 512 recipe, maintainer's terminal per the throughput-measurement
  discipline): solo 859 steps/s (matches the 12M run's 840 median — probe representative); three
  concurrent runs 689/694/691 — a uniform −20% per run, under the ≤25% bar, aggregate 2,073 steps/s
  = 2.4× solo.** Decision of record, per the async-review pre-registration: **the async vec-env
  branch stays SHELVED** — concurrent seeds beat its honest estimate (~1,900 steps/s on one run) on
  aggregate throughput while also buying n=3 per lever read, at zero code and zero risk to the
  pool-identity seam. Server headroom note: 3 runs ≈ 24 battles in flight against a ~5.9k dec/s
  measured ceiling — do not extrapolate to 4+ without re-probing. A 3-seed 6M lever read now costs
  ~2.4 h wall. *Next*: MixturePlayer (lever 2, on the 512 trunk), then the first 3-seed run of the
  campaign.

- 2026-07-31 (CAPACITY WAS BINDING: [512,512] breaks the [64,64] ceiling — 0.408 at 12M and the
  curve still hasn't flattened) — **`showdown_heur_512_s0` (12M steps, [512,512] ≈ 1.16M params,
  maintainer's terminal, clean tree at `35314be`, 4.2 h at 840 steps/s median — the capacity lever
  cost ~2% throughput, not the predicted ~30%; even reviewer 3's live-measured 765 was pessimistic
  because early-run segments include eval rungs). Locked-protocol headline (FINAL checkpoint, 1000
  fresh battles, `final_eval_heur_1000.json`): 408/1000, win rate 0.408 ± 0.030 (95% CI [0.378,
  0.438]), ties 2.1%.** The pre-registered read (config header) fires cleanly: **the plateau MOVED —
  capacity was binding.** Two comparisons, ordered by cleanliness: (1) matched-budget
  single-variable read — at 4–6M the 512 rung band averages 0.346 where the [64,64] 6M run's
  same-band average was 0.312 and flat; (2) the shape difference is the louder fact — [64,64]
  flattened hard at ~0.31 from 2.5M on, while [512,512] climbs monotonically in 2M bands (0.219 /
  0.287 / 0.346 / 0.392 / 0.410) and is STILL creeping at 12M (9–12M vs 6–9M: +0.018, decelerating
  but not flat; last-10 rungs 0.30–0.50). The 0.408 headline vs the budget run's 0.358: CIs graze
  ([0.378,0.438] vs [0.328,0.388]) — but that pairing confounds capacity with budget; the
  attribution rests on (1)+(2). Mechanism reads, notably different at 1.16M params: entropy sits in
  a 0.29–0.36 band ALL run (no monotone decay to 0.27 like [64,64] — the bigger net holds
  exploration while improving, which may itself be part of why it keeps climbing); `approx_kl` ends
  ~0.013 vs [64,64]'s ~0.003 (larger net moves more per update at the same lr — worth watching
  against clip 0.2, not yet alarming); stalls stay rare (9 of 425k episodes ≥500 turns);
  win-rate/return arithmetic consistent (0.408/−0.163/2.1% ties). **Milestone-2 bar (0.5) NOT yet
  met — gap 0.09 — but for the first time in Phase 5 the curve is unflattened at the wall, so the
  bar is plausibly reachable rather than ceiling-blocked.** Phase 4's "capacity was never the
  problem" is now formally scoped: true at Connect4/10-dim scale, FALSE at 611-dim — the
  supervised-diagnostic instrument (BC arm, scoping GO'd 2026-07-30) can now price how much more
  capacity is worth from the offline side. *Next (unchanged morning agenda, sharpened)*: (1) Stage-0
  free-lever probe (3 concurrent 100k runs vs solo) — decides async shelving AND enables 3-seed
  reads; (2) MixturePlayer on the 512 trunk — the distribution lever now runs on an un-throttled
  net, exactly the stacking order the async review argued for; (3) candidate runs after the probe,
  in single-variable discipline: 512 + mixed opponents (lever 2 proper) vs 512 continued/bigger
  (capacity step 2 — weaker: the curve's deceleration says distribution likely binds next); budgets
  ~3–6M per the review's read-resolution finding — though note the 512 curve resolved its OWN read
  only past 6M, so "reads resolve by 3M" is per-lever, not a law.

- 2026-07-30 (async-collection proposal: three-review pass returns APPROVE-WITH-CONDITIONS ×3 — and
  demotes it behind free levers; protocol pre-registered) — **Maintainer-directed three-reviewer
  adversarial pass (independent Opus sessions: correctness / systems / experiment-design) over the
  proposed `vec_mode: async` (AsyncVectorEnv option in `make_vec_env`, Showdown-only, motivated by
  ~1 busy core of 14 during the 12M capacity run). Decision of record: the flag's design is sound
  (~25-line diff) but it is SHELVED behind zero-code levers; build it only if the wall re-binds.**
  The reframe (reviewer 3, verified against our own runs): the wall is partly self-inflicted — every
  lever read so far resolves by ~3M while we run 12M, and the machine + server fit ~3 CONCURRENT
  seeded runs (one process uses ~1k steps/s of a ~5-6k-ceiling server), which is 3×
  experiments/evening with zero code AND fixes the campaign's n=1-per-lever weakness; measured live
  during review, the 512 run does ~765 steps/s (~4.4 h wall), not the predicted ~600. The async
  prior re-priced honestly: realistic 1.8–2.6×, hard Amdahl ceiling 3.9× at the 512 config — "3–5×"
  retracted; ratio ≥4.0 in any future A/B is a falsifier (broken measurement), not a win. Two
  kill-shot-class findings if ever built, unanimous: (1) cloudpickled factories SEVER the
  shared-opponent-identity seam (`make.py:24-29`'s documented contract) — each worker would get a
  private SnapshotPool copy, `pool.push` never reaches envs, self-play silently trains vs a frozen
  step-0 opponent while `selfplay/*` metrics lie; existing identity tests reach through `.envs`
  (sync-only) and cannot catch it; mandatory guard: async hard-rejects non-scalar env_kwargs. (2)
  `context="spawn"` must be pinned: the parent is ALWAYS poke-env-dirty (gymnasium builds a dummy
  env parent-side — which also leaks 2 websockets/accounts for the run's life since
  `PokeEnv.close()` never closes websockets); fork deadlocks on POKE_LOOP, and forkserver is
  deterministic-catastrophic because `set_seed` runs before env construction → all 8 workers draw
  byte-identical account names → server `|nametaken|` swallowed inside a fire-and-forget task →
  presents as 8× 60 s "Agent is not challenging" timeouts naming the wrong cause. Further
  conditions: `vec_mode` a VALIDATED Config field (typo must raise, never silently run sync —
  load_config only type-checks today); teardown try/finally + `close(timeout=)` (untimed pipe
  recv/join + poke-env's untimed `_challenge_task.result()` = one wedged websocket hangs training
  exit forever); pid-based account names regardless of platform; re-baseline sync with `simulator:
  4` (config.js currently 1 — the single node simulator child IS measurement (c)'s shared-server
  saturation mechanism) before crediting async anything; measurement (e) (reset latency) is a
  PREREQUISITE, not a follow-up — under lockstep the whole vector stalls on one env's challenge
  round trip, and R alone spans the estimate 1.6–4.1×. The naive two-1M-run speedup test was
  unanimously rejected as noise-blind (eval/win_rate never traverses the changed code; rung SE ≈0.05
  hides phantom-class bugs; 1M is mid-climb; battles server-rolled so pairing is fiction) and
  replaced by a pre-registered ladder: (A) offline sync-vs-async bit-equality differential on a
  deterministic env INCLUDING the partial reset_mask path + mutation battery `phase5_vec.py`
  (dispatch→always-sync, dropped validation, dropped guard, dropped spawn; +1 control); (B)
  throughput A/B = six 100k runs S-A-S-A-S-A alternated on a fresh exclusive server, adopt iff
  median ratio ≥2.0 AND min(async)>max(sync); (C) equivalence on the same runs via mechanism
  invariants (entropy/KL/clip bands, episode-length KS, waits_absorbed rate ±20% — exposed via
  `envs.call`, and the lr=0 ⇒ approx_kl==0 probe under async, noting reviewer 1's caution that the
  probe canNOT detect cross-env permutation, which is what (A) pins); (D) 1M soak before any
  overnight async run (no resume path exists — a crash at hour 3 costs the evening); (E) first async
  campaign run = 6M replication, CI must overlap [0.328, 0.388]. If the gate fails the branch is
  DROPPED, not merged default-off (CLAUDE.md dead-configurability rule). Also recorded: reviewer
  consensus that gymnasium 1.3.0's async reset_mask/DISABLED/info-aggregation semantics are
  bit-compatible with sync (verified in source, both call the shared `_add_info`), async's
  `step_wait` is a full barrier so the seam-collector kill shots do NOT apply, `num_envs` under sync
  is a non-lever (serial stepping; raising it silently changes update cadence), and per-run
  `server_configuration` passthrough (~3 lines) is strictly more leverage per line than async — it
  composes with concurrent runs toward measurement (c)'s 7.5k/s per-worker-server ceiling and is a
  prerequisite for async ever scaling past one server. Milestone-3 note: the parked lockstep facade
  remains the architecture of record there (in-process, preserves pool identity); async is at most a
  milestone-2 expedient. *Next, in order (morning agenda)*: (1) 512 capacity verdict — locked
  1000-battle eval on `showdown_heur_512_s0` final checkpoint (auto-fires via watcher if the session
  holds; else run `scripts/eval_checkpoint.py runs/showdown_heur_512_s0/ckpt_012000000.pt --episodes
  1000 --out runs/showdown_heur_512_s0/final_eval_heur_1000.json` and read the curve); (2) Stage-0
  free-lever probe — 3 concurrent 100k runs vs 1 solo, steps/s degradation, decides whether async
  stays shelved; (3) MixturePlayer design+build (lever 2, ~20-30 lines, async-compatible by
  construction); (4) drop run budgets to ~3M now that reads resolve by then.

- 2026-07-30 (budget lever: credited, then exhausted — 6M run lands 0.358, flat from 2.5M on;
  capacity is next) — **`showdown_heur_6m_s0` (the 2M recipe verbatim at total_steps 6M,
  maintainer's terminal, clean tree at `dfdfbdc`, 116 min at ~860 steps/s). Locked-protocol headline
  (FINAL checkpoint, 1000 fresh battles, `final_eval_heur_1000.json`): 358/1000, win rate 0.358 ±
  0.030 (95% CI [0.328, 0.388]), ties 1.8%.** The verdict has two halves, both clean: (1) the 2M and
  6M CIs DO NOT overlap ([0.264, 0.320] vs [0.328, 0.388]) — budget bought a real +0.066, and the
  curve says where: the climb the 2M wall truncated completes by ~2.5M; (2) from there the curve is
  DONE — plateau halves 2.5–4.2M and 4.2–6M average 0.306 vs 0.312 (Δ0.006 across 1.75M steps), so
  further budget buys ~nothing and the remaining gap to the 0.5 bar is ~0.14. Secondary reads:
  entropy 1.68 → 0.267, still drifting slowly, never cratered — low-but-stable, not collapse, so the
  entropy floor stays third in the lever order; stall-to-tie episodes exist but stay rare (3 of 214k
  training episodes ≥500 turns; eval ties 1–4%/rung, 1.8% at the headline) — tie-farming is real,
  logged, and not the plateau's cause. **Architecture research (same evening, sources in the entry):
  the published bracket for beating heuristics at random battles is ~0.5M–1.5M params — Huang &
  Lee's gen7randombattle PPO used 1,327,618 params (structured: 128-dim entity embeddings, per-mon
  encoders, max-pool, shared action heads; 929/1000 vs most-damage, 612/1000 vs tree-search
  pmariglia, naive self-play, light shaping ±0.0125/faint), and Metamon's first heuristic-beating
  models were 500k–4M-param BC-RNNs with 15M chosen as the transformer floor for underfitting. Our
  trunk is ~45k params on a 611-dim obs — 30× under the closest precedent. Opponent-mixing canon
  verified while at it: OpenAI Five 80/20 current/past (the maintainer's remembered "20% random
  stuff"; AlphaZero never mixed opponents — its 25% was Dirichlet root noise), AlphaStar ~35%
  self-play + PFSP over the league, and Phase 4's own latest_prob 0.8 + fixed_mix 0.05 sits squarely
  in that canon — mixing's real home is milestone 3's pool, where the machinery already exists.**
  *Next (launching tonight)*: `showdown_heur_512_s0` — [64,64] → [512,512] (~1.16M params,
  Huang-&-Lee scale), 12M-step overnight budget, rungs unchanged so the first 6M is the exact paired
  capacity-vs-budget read; pre-registered in the config header: plateau shifts up ⇒ capacity was
  binding; stays ~0.31 ⇒ capacity exonerated and the distribution levers (MixturePlayer, then
  entropy floor) take over.

- 2026-07-30 (BC diagnostic scoping: GO-WITH-CAVEATS — a parallel research session's advisory,
  verified premises folded in, file deleted per the advisory precedent) — **The five-times-named
  diagnostic is FEASIBLE on data: ~109,147 archived `gen1randombattle` replays (~2.7M decisions at
  ~25/battle) in the HolidayOugi/pokemon-showdown-replays HF archive (README-reported count, NOT
  primary-verified; license unstated), and the official `replay.pokemonshowdown.com/search.json` API
  verified live and accumulating (~100–120 replays/day from a single ~10 h window —
  order-of-magnitude only). Programmatic JSON access is the documented, sanctioned path (WEB-API.md;
  no published rate limit — self-throttle ~1 req/s; full self-scrape ≈ low-tens-of-hours), preferred
  over the unlicensed third-party dump beyond prototyping.** The binding cost is the PARSER: Metamon
  (arXiv:2504.04395, code MIT, datasets CC-BY-NC) released parsed replays for Gen 1–4 OU/NU/UU/Ubers
  + Gen 9 OU ONLY — no random-battle format anywhere in the ecosystem has a spectator→first-person
  reconstruction, and Metamon's own docs call the problem inherently imperfect ("the server sends
  info to the players that it does not save to its replay... there is no way to be perfect"). **One
  leak verified on a live replay fetched during scoping: the raw log stores EXACT HP fractions for
  both sides (`|-damage|p2a: Chansey|241/481`) despite the `HP Percentage Mod` rule tag.** Sharpened
  against our own stack: poke-env's live battles give each seat the OPPONENT'S HP at /100 resolution
  while own-side HP is exact, so the parser rule is round-opponent-to-/100, keep-own-exact —
  otherwise the BC arm trains on precision the deployed encoder never sees (a train/deploy skew, not
  merely leaked omniscience). Quality caveat: accumulation is bursty and partly tournament-sourced
  (a Jan–Jul 2023 slice sampled as entirely `smogtours-*`) — stratify by rating/source, don't treat
  the corpus as IID ladder play. *Open questions carried*: (1) primary-source total count (~2,183
  paginated requests would settle it); (2) real accumulation rate (two timestamped queries N days
  apart); (3) log-schema drift across years; (4) whether a full-team reveal exists at battle end
  (2019 "full information replays" thread was Approved by Zarel — sample complete logs end-to-end
  before freezing parser assumptions); (5) HolidayOugi license clarification if ever used beyond
  private prototyping. Scoping was research-only — no repo files touched by the advisory session;
  PLAN.md's BC paragraph now carries the resolved verdict.

- 2026-07-31 (milestone-3 design session: three-review adversarial pass, then the machinery landed —
  PoolPlayer, init_from warm start, pool-health metrics, cross-play eval; campaign is warm-started
  self-play vs matched control) — **Design drafted (PoolPlayer = the seat-2 Player adapter; four
  forks: facade-vs-batch-1, anchor mixing, from-scratch-vs-warm-start, push cadence), then a
  maintainer-directed three-Opus adversarial pass (correctness / experiment design / systems).
  Verdicts, several against the draft: (A) NO lockstep facade — unanimous, but on corrected
  evidence: the draft's throughput constants were misattributed ([64,64] microbench read as
  [512,512] — `showdown_throughput.py` hardcodes [64,64]); at [512,512] batch-1 is
  compute-saturated, batching headroom ~zero, honest facade ceiling ~5%, and its real prize
  (decoupling battles-in-flight from num_envs, ~1.9×/process) is unbankable against a shared server
  at ~80% of ceiling — `simulator: 4` in `showdown/config/config.js` is the one-line lever if the
  wall ever binds, ahead of any facade. (B) Anchor mixing KILLED for run 1: 10% heuristics battles
  would train on the eval bot (self-fulfilling headline), the Phase-4 fixed_mix evidence re-read
  says it bought coverage "by construction" on 2 of 3 seeds with zero strength gain and WORSE
  forgetting proxies, and the proposed `mix:self=` mechanism had a provable stale-report bug (after
  an anchor battle `pool.report`'s identity match hits whichever member played last — silent,
  directionally biased PFSP corruption). Future anchors, if forgetting fires: max_power or a policy
  anchor, never heuristics. (C) Run 1 FLIPPED to warm-start + matched control (the 2-1 nominal split
  for from-scratch dissolved once init_from measured ~5 lines and the science argument stood:
  from-scratch changes opponent identity + strength trajectory + stationarity at once, and 12M ≈ 6%
  of H&L's from-scratch budget — 3.84M matches × both-sides collection ≈ 192M learner transitions —
  so a null is unattributable; warm-start + control is paired, single-knob, both arms in one ~5h
  evening). From-scratch 12M stays the pre-registered narrative arm if the paired read is flat
  (expected 0.20–0.35). (D) push_every_updates 150, not 20 or 100: the Bansal-validated quantity is
  the ~half-run history span — strided retention keeps anchor + 19 newest, so cadence 150 at 6M
  spans 48.6% where Phase 4's own setting spanned 19.5% (δ≈0.2, an unnoticed artifact) — and cadence
  has zero throughput content (deepcopy measured 1.3 ms, not the draft's ~150 ms). Two protocol
  kills adopted: the STALL-EQUILIBRIUM gate (terminal-only ±1 with tie=0 at γ=1 makes stalling
  dominate losing for BOTH seats under mirror self-play, and eval/win_rate cannot distinguish
  0.35W/0.60T from 0.35W/0.60L — R0: locked-eval ties ≤4.2%, mean episode length ≤1.5× the 12M
  run's, else the run reports as a degeneracy finding; related: the encoder's `turn/50` clock
  saturates at 50, dead vs heuristics, load-bearing under long self-play games — recorded, not
  fixable, warm start freezes the layout), and NO OVERNIGHT ON UNMEASURED THROUGHPUT (the one
  unmeasured term is the SimpleHeuristicsPlayer.choose_move cost the baseline already pays — ±5%
  band — so a 100k solo probe + 500k 3-wide shakeout, ~25 min, reads the facade trigger and the
  health gates before 5+ hours ride on new code). Verified true under attack, notably:
  `embed_battle` is genuinely egocentric on the seat-2 battle object (fields are per-battle; slot
  orderings match `action_to_order` on that same object) and `PPOAgent` deepcopies clean (no
  env/logger refs; snapshot ≈ 19–24 MB → pool ≈ 400–470 MB, noise). Sourcing corrections adopted:
  the 0.008 seed-std belongs to the 6M mixture n=3 (0.408 is n=1); plan 3-wide at ~653 steps/s
  (campaign-measured), not the probe's 690; pre-review test count was 296 with live, not 294.**
  **LANDED (all committed, 308 tests green INCLUDING both live tests twice on a free :8000 — the
  handoff's flake is cleared): `PoolPlayer` in rl/envs/showdown.py (sync choose_move per
  SingleAgentWrapper's non-awaitable assert; one per sub-env wrapping the ONE shared pool;
  per-battle member draw on battle_tag change with own-attribute tracking — reset_battles() is
  called on the opponent every battle; wait-state assert = the seat-2 twin of the discarded-action
  guard; first-reset seed latched per sub-env so member draws decorrelate — a shared stream would
  collapse pool diversity 8-fold), ShowdownEnv outcome→pool.report wiring (isinstance, never
  getattr: nothing cross-checks PFSP stats), `init_from` config field + train.py load BEFORE the
  step-0 push (ordering test: push-first would anchor the pool at random init and winrate_anchor
  would read ~1.0 forever; refuses lr_anneal_steps — the restored update count clamps lr to ~0
  silently), Showdown fixed_mix>0 hard-reject (measured: HeuristicOpponent crashes on a 611-dim obs
  but RandomOpponent silently plays legal uniform-random moves, unreported),
  `selfplay/winrate_anchor` + `winrate_latest` + `anchor_games` logged from train.py at rollout
  boundaries pre-push, read positionally (stats[0]/stats[-1] — the two indices eviction cannot
  misalign; winrate_anchor = the in-run H&L §V-C detector, under warm start the anchor IS the 0.408
  parent, ~se 0.01 by run end), `--opponent-checkpoint` cross-play on eval_checkpoint.py (seat 1
  deterministic per locked protocol, seat 2 samples per pool contract — run both orientations), and
  four configs (sp6m + cont6m differ in the selfplay block only; sp_probe 100k timing-only;
  sp_shakeout 500k 3-wide with pass gates). 8,192-step live smoke through the full harness: all
  locked metrics + the three new series; mean self-play return +0.014 over 292 episodes (the mirror
  equilibrium, and end-to-end proof of outcome wiring); ties 2.1%; entropy 0.296→0.321 (the 512
  run's band — warm start confirmed from inside; eval rungs 0.3–0.4 confirm it from outside); pool
  1→5 on the smoke cadence; winrate_anchor 0.42–0.47 on 33→104 cumulative games.** *Next, in order
  (probe gates each step)*: (1) solo probe `showdown_sp_probe.yaml` (~2 min; ≥700 steps/s ⇒ facade
  stays parked); (2) 3-wide shakeout `showdown_sp_shakeout.yaml` (~13 min; gates in header — steps/s
  ≥575 each, entropy ≥0.20, ties ≤4%, ep-length ≤~37, pool_size 4, winrate_anchor ~0.35–0.65); (3)
  overnight campaign — sp6m ×3 seeds then cont6m ×3, ~5.1 h, locked 1000-battle finals per seed; (4)
  evening-2 reads R0–R5 incl. the cross-play round robin (SP/CT/parent, both orientations), then
  exactly one of: latest_prob 0.8→0.5 (credited), contamination-free anchor arm (R4 fires), or the
  pre-registered from-scratch 12M narrative arm (flat).

- 2026-08-01 (milestone-3 run 1: self-play NOT credited at matched continuation budget — windowed
  anchor flat at 0.5 all run, cross-play dead even; control arm sets a new 3-seed best 0.432; all
  gates passed, all reads pre-registered) — **Campaign ran exactly as designed (launch 01:03 UTC,
  clean tree `35d4399`, 3-wide waves: sp6m ×3 at ~553 steps/s / 3.0 h, cont6m ×3 at ~600 / 2.8 h;
  solo probe beforehand: 717 steps/s ≥ the 700 architecture gate ⇒ facade stays parked; 3-wide
  shakeout 552–554 vs the derived 575 — inside the pre-stated judgment band, launched; the only
  launch incident was wandb prompting for login in a fresh shell — no credentials exist on this
  machine, all prior campaigns were ambient-offline — fixed with `WANDB_MODE=offline`, noted as a
  to-do to make offline the code default in logging.py). Locked finals (FINAL ckpt_006000000, 1000
  fresh battles each): SP 436/375/414 → pooled 1225/3000 = 0.408 ± 0.018; CT 421/446/428 → pooled
  1295/3000 = 0.432 ± 0.018. The reads, in pre-registered order: R0 GATE PASSED (training ties
  1.2–1.3%, ep len ~26.7 stable, eval ties 1.1–2.4% vs the 4.2% gate — the stall-equilibrium risk
  did not materialize); R1 Δ = −0.023, inside the ±0.025 indistinguishability floor (z ≈ −1.8),
  leaning CT; R2 4–6M bands SP 0.399 vs CT 0.410, same story; R3 CROSS-PLAY (matched seeds, both
  orientations, 6×1000 battles) 3008/6000 = 0.501 — NO strength difference; R4 — the maintainer's
  named primary signal and the campaign's cleanest fact — windowed winrate_anchor (cumulative
  counters differenced per 1M) sits at 0.465–0.551 ≈ 0.5 in EVERY window on EVERY seed (late-window
  n≈400, se 0.025; cumulative n≈10k/seed): the learner NEVER pulled away from its frozen 0.408
  parent and never sank — no improvement, no forgetting, H&L §V-C did not fire; R5 entropy
  0.384–0.391 late (top of the 512 band), no collapse. Verdict per pre-registration: SELF-PLAY NOT
  CREDITED as a training distribution at matched init + 6M continuation budget — and R4 sharpens it
  beyond "not credited": the null is not anchor-blindness (the intransitivity worry), because the
  learner didn't beat its own parent either; warm-started pool self-play at Phase-4 recipe
  (latest_prob 0.8, cadence 150, pool 20) produced zero measurable strength gradient anywhere.
  Meanwhile the control read is a real result twice over: continued fixed-bot training bought +0.024
  over the parent (18M cumulative, curve still creeping, expected-value band 0.42–0.44 hit dead
  center) and 0.432 pooled is the new best-ever headline — the first 3-SEED number in the lineage,
  retiring the n=1 caveat, seed-std 0.010. One asymmetry worth keeping: CT gained +0.024 on its own
  training distribution yet ties SP head-to-head — the anchor gain reads as
  heuristics-specialization, not generalizable strength, which is the R2-bias argument confirmed in
  the other direction. Seed spread note: SP finals spread 0.061 (s1 0.375) vs CT's 0.013 — self-play
  continuation variance is real. Milestone-2 bar: not met by either arm (0.432 best). *Open for the
  run-3 design discussion (the pre-registered tree's "R1 flat and R3 flat" branch fires →
  from-scratch 12M×3 narrative arm, expected 0.20–0.35, budget caveat 6% of H&L's 192M; but the tree
  predates knowing CT +0.024 / SP +0.000, so the alternative on the table is the latest_prob 0.8→0.5
  lever — 80% mirror-vs-near-current games is the plainest mechanism candidate for the zero gradient
  — at half the wall of the narrative arm; hypotheses worth pricing: budget, latest_prob curriculum,
  warm-start local equilibrium)*. Artifacts: final_eval_heur_1000.json ×6, xplay_vs_*.json ×6,
  histories in the wandb offline dirs.
- 2026-08-01 (run-3 design session: three-Opus adversarial pass + in-session re-analysis of run-1's
  own histories — the run-1 framing does not survive; every draft candidate killed except the
  narrative arm; from-scratch 12M×3 chosen at cadence 150, launch gated on the dropped R3 parent
  cells) — **Process: the run-3 draft (candidates: A latest_prob 0.8→0.5 warm-started 6M×3; A′ pool
  pre-seeded from parent-lineage rungs; B from-scratch 12M×3; C = A then B in one overnight; D
  bar-chasers) went through a three-Opus pass (experiment design/statistics, RL mechanism, research
  strategy/ops); every load-bearing number below was re-verified in-session from the extracted wandb
  histories before adoption.** *The re-analysis:* **(1) Run-1's framing overstates both halves.** CT
  never measurably improved in-run either — pooled eval late-3M minus early-3M +0.0034 ± 0.0073
  (z=0.47); SP −0.0119 ± 0.0073 (z=−1.63); CT's +0.024-over-parent is a single-endpoint read at
  z≈1.3; and at the seed-paired level (where the recipe claim lives) the CT−SP finals contrast is
  t(2)=0.92, p=0.45, MDE ≈ 0.14 — the ±0.025 "resolution floor" was a battle-level number licensing
  a recipe-level claim ~5× underpowered. **(2) The fixed-bot curve saturates geometrically**: parent
  per-2M return gains +0.153/+0.103/+0.061/+0.027/+0.016 (ratio ≈0.65), extrapolated asymptote ≈0.42
  vs heuristics (recorded as an extrapolation, not a measurement) — the 0.5 bar is unreachable by
  more fixed-bot budget in this configuration, killing bar-chaser D and re-reading CT's +0.024 as
  consuming most of the lineage's remaining headroom. **(3) The run-1 pool was PROVEN
  strength-homogeneous**: winrate_latest last-half means 0.4993/0.4986/0.5013 per seed; pooled
  last-3M windowed anchor 0.5028 ± 0.0084 — reweighting a draw over equal-strength members is a
  no-op, killing A at any dose by measurement. **(4) Run 1 did not exclude self-play improvement at
  the size the lineage was capable of**: achievable rate ~0.005 win-prob/1M and decaying; the
  per-seed anchor rule needed +0.05 to fire (20–30% power vs its own best case); SP's highest-n
  instrument (pooled training return, n≈98k/window) reads +0.0025 ± 0.0013, z=1.9 — edge of
  resolution, not zero. "Zero gradient" is retired for "below instrument resolution on a
  lineage-wide plateau." **(5) A significant seat effect hides in run-1's own cross-play**: the
  deterministic seat beats the sampling seat by +0.018 ± 0.0065 (z=2.8) at equal parameters;
  both-orientation averaging cancels it (R3's 0.501 stands) but any single-orientation read is
  biased ~2 points — protocol fact, recorded. **(6) R3 was executed incompletely**: the
  pre-registration locked a SP-final/CT-final/parent round robin; only the SP↔CT leg ran (6 xplay
  files on disk, no parent cells). Also noted: eval_checkpoint.py's paired-episode docstring promise
  is false on Showdown (per-battle return correlation ≤0.04 over all 21 run-pairs — the server rolls
  the teams); harmless, but no analysis plan may rely on it. *Candidate verdicts (convergent):* **A
  KILLED** (homogeneity above; its one real effect — tighter anchor precision — comes free by
  pooling seeds, already se 0.0084). **A′ KILLED at this rung** — two verified defects: pool.py
  evicts index 1 on overflow, flushing every pre-seed by ~push 19 of 39 (step ~2.9M of 6M), and
  pre-seeding silently redefines stats[0] = winrate_anchor into a spurious-success detector; deeper:
  one-trajectory rungs are ontogenetic not strategic diversity, and per-minibatch advantage
  normalization gives below-frontier games unit-scale gradient — a noise-floor increase, not just
  waste. If ever revived: pre-seed from the independent-seed mix512 runs, protected-slot retention,
  anchor ordering pinned. **C KILLED** (re-priced ~10.5 h against the 5.9 h measured precedent —
  run-1's true wall by ckpt mtimes, not the logged ~5.1 — and it puts the valuable arm in the
  unmeasured tail). **D KILLED** (finding 2; capacity step 2 stays queued). **B SURVIVES
  RELABELLED**: it cannot discriminate H-budget/H-mixture/H-equilibrium (all predict a rise from
  random init, where the achievable rate is ~9× the plateau's) — it is the narrative/ceiling arm the
  pre-registered tree selected when "R1 flat and R3 flat" fired, and both outcomes carry the
  write-up; the informative-only-on-success caveat from 2026-07-31 stands, accepted. *Decisions
  (maintainer):* **run 3 = B**, from-scratch 12M×3, **cadence 150 not the span-preserving 300**
  (Phase 4's working from-scratch precedent is the nearer regime on both axes — span 24.3% vs its
  19.5%, latest-staleness 154k vs 307k; a deliberate, recorded deviation from the half-run-span
  rule, which was adopted for run 1, which failed); lr_anneal_steps 0 pinned; R0 widened for the
  random-init regime (0–3M recorded not gated); winrate_anchor expected to saturate (strength read =
  eval rungs; winrate_latest is the mirror-equilibrium check). **Launch GATED on two things:** (i)
  closing the R3 parent cells — 12×1000 battles both orientations, decision rule pre-registered:
  both-orientation pooled SP-vs-parent (wins/total, ties count as losses, run-1 R3 convention)
  within 0.5 ± 0.013 (2se at n=6000) ⇒ run-1 null confirmed ⇒ launch; outside ⇒ HOLD, the tree
  re-opens; CT-vs-parent ≈0.5 confirms the +0.024 as specialization/endpoint noise, ≥0.55 would
  revise the re-analysis — and (ii) the scratch 500k 3-wide shakeout (random-init throughput and
  episode profile are unmeasured; the 12M wall estimate is recomputed from its mtimes before any
  overnight). Configs landed: showdown_scratch12m.yaml, showdown_scratch_shakeout.yaml. *Queued from
  the reviews, not committed to:* **P4 — BC-clone SimpleHeuristics through the 611-dim encoder +
  [512,512]** (the encoder-ceiling test, now the live suspect given the 0.42 asymptote; decisive if
  it FAILS, one-directional if it passes — to be pre-registered as such; a diagnostic outside the
  milestone ladder per the Phase-4 contamination framing; ~1 machinery session); P3 team-luck
  variance decomposition (~20 min, prices the SNR story); P5 rollout_steps 512 (the config's only
  true SNR knob — per-minibatch advantage normalization makes an lr test meaningless, explicitly
  rejected) and an entropy_coef 0.003 2M probe with a real prediction split; strategy advice
  recorded as recommendations: a stop rule for milestone 3 (ships after a bounded set — open), the
  0.5 bar stays unmoved with cross-play co-reported and the bar's date attached, replay-BC reframed
  as capstone INITIALIZER rather than diagnostic. HANDOFF.md folded in and restored to stub.
- 2026-08-01 (run-3 gates: R3 parent cells closed — run-1 null confirmed at se 0.0065 and CT's
  +0.024 does not generalize; scratch shakeout all-green; 12M×3 overnight launched) — **The dropped
  R3 leg (12×1000 battles, both orientations): SP-final-vs-parent pooled 3030/6000 = 0.5050 — inside
  the pre-registered [0.487, 0.513] launch band (z=+0.77 at se 0.0065). Six million steps of
  warm-started self-play left the policy within ±1.3 points of its parent: the lineage's tightest
  null, closing the read the 2026-08-01 re-analysis found missing. CT-final-vs-parent 3059/6000 =
  0.5098 — the control's +0.024-on-heuristics does NOT appear head-to-head (nowhere near the 0.55
  revision trigger): heuristics-specialization/endpoint-noise CONFIRMED by direct measurement rather
  than transitive inference.** Both pairs show the deterministic-seat edge in the first orientation
  (+0.02–0.04), consistent with the re-analysis's measured +0.018 seat effect. Operational lesson
  recorded: the handed-over 12-eval && chain (~2.7k chars) mangled on paste — the first 4 evals
  survived, the remaining 8 ran from a bash script in the session tmp dir; long command sets go in
  scripts from now on, never single chains. *Shakeout (500k ×3 concurrent, the first measurement of
  the random-init regime, all gates pre-registered in the config header):* steps/s **575/569/568**
  at 3-wide by mtimes (≥500 gate; faster than warm-SP's 553); entropy declining to 0.49/0.60/0.60
  (in [0.3, 1.8]); training ties 1.1–1.2%; ep len 34.4–36.4 mean, p99 80–86 (longer than the warm
  regime's 26.7, as predicted for random play — the widened R0 gate was right to exist); pool
  reaches 4 on cadence; **winrate_anchor vs the random step-0 init 0.925/0.917/0.922 (n≈4.8–5.2k
  each) — learning from scratch is unambiguous, the sharpest possible contrast with the warm-start
  regime's 0.5028**; eval rungs climb 0.04→0.20 / 0.08→0.25 / 0.10→0.28 inside 500k (rungs noisy at
  se 0.05; the anchor is the signal). Watch item for the morning read, not a blocker: entropy is
  falling fast — R4's <0.15-median trigger may engage mid-run (record-and-plan per pre-registration;
  never mid-run changes). **GO issued on all gates; 12M×3 launched 09:33:50–09:34:02, all three
  stamped `056b78f` / `git_dirty: false`, 3 live processes verified; wall estimate ~5.9 h at the
  slowest measured 568 steps/s.** Next session: locked finals (1000 fresh battles/seed), the R1–R4
  reads, R3 cross-play if R2 lands in band.
- 2026-08-01 (run 3 COMPLETE: from-scratch self-play LEARNS on Showdown — finals 0.380 ± 0.009
  pooled, above the pre-registered band; 0.484 head-to-head vs the equal-budget fixed-bot parent;
  all health gates green) — **The narrative arm ran exactly as designed: 12M ×3 seeds,
  09:34→15:39–15:41 (6h05, the 5.9 h estimate held), ~546 steps/s effective with evals, all stamped
  `056b78f` clean; every pre-registered read taken in order.** R0 PASSED (post-3M ties 1.1–1.2% vs
  the 4.2% gate, ep len 26.7–26.8 vs ≤40 — episode length converged to the warm regime's ~26.7 from
  the random-init ~35 as play got competent; no stall equilibrium). R1 PASSED decisively (windowed
  anchor vs the random init 0.972–0.982 already at 4M, final cumulative 0.949–0.955 at
  n≈10.6–10.9k/seed). R2: per-2M eval means climb monotonically to ~8–10M then flatten — s0
  0.247/0.312/0.343/0.390/0.395/0.365, s1 0.253/0.300/0.355/0.354/0.366/0.364, s2
  0.245/0.338/0.354/0.370/0.383/0.386; **locked finals (final ckpt, 1000 fresh battles/seed):
  0.369/0.398/0.373 → pooled 0.3800 ± 0.0089, seed spread 0.029 — ABOVE the pre-registered 0.20–0.35
  band**, short of parent parity (0.408) and the control (0.432); milestone-2 bar not met. R3
  CROSS-PLAY (both orientations, 1000/pair, matched seeds): **scratch-vs-parent 2902/6000 = 0.4837 ±
  0.0065 (z≈−2.5) — a small but resolvable deficit at EQUAL 12M budget against a policy trained on
  the eval bot's own distribution**; scratch-vs-sp6m 2845/6000 = 0.4742 ± 0.0064, per-seed
  0.434/0.498/0.489 — s0's cross-play weakness matches its last-2M eval dip (0.395→0.365): the
  Phase-4 "best rung ≠ final" late-regression pattern recurs on one seed of three (finals stay on
  the final ckpt per the locked protocol; best_checkpoint feeds no reported number). R4 CLEAN:
  winrate_latest 0.505–0.506 all run (mirror equilibrium as designed); late entropy medians
  0.397–0.427 and the <0.15-for-5-rungs trigger never engaged on any seed — **the Tesauro-dice
  prediction held: server-rolled teams supply the exploration that Connect 4's deterministic board
  did not, and the Phase-4 entropy collapse did not reproduce**. *The milestone-3 three-arm arc is
  now complete and coherent:* (1) warm-started self-play at matched budget moved nothing — 0.5050 vs
  parent at se 0.0065; (2) continued fixed-bot training gained only on its own anchor — +0.024 on
  heuristics, 0.5098 head-to-head: specialization; (3) from-scratch self-play, never having seen the
  eval bot, lands within ~3 points of the equal-budget fixed-bot policy on BOTH measures — 0.380 vs
  0.408 on the anchor, 0.484 head-to-head. **Self-play produces a genuine generalist that approaches
  the lineage's ~0.4 plateau from below; the plateau, not the training distribution, is the binding
  constraint — consistent with the re-analysis's geometric-asymptote read (~0.42) and Phase 4's
  visited-state-distribution finding, and it points every follow-up at the same place: P4, the
  encoder-ceiling BC diagnostic.** Next queue (per the design session, none launched): P4
  encoder-ceiling diagnostic; the milestone-3 write-up + stop-rule decision; P3 (team-luck variance)
  and P5 (rollout_steps 512) as mechanism follow-ups. Artifacts: final_eval_heur_1000.json ×3,
  xplay_vs_parent.json ×3, xplay_vs_scratch12m_s*.json ×3, xplay_vs_sp6m.json /
  xplay_vs_scratch12m.json ×3 pairs, full wandb offline histories.
- 2026-08-01 (P4 machinery: the BC-clone instrument built, smoke-tested end to end, and priced — the
  whole diagnostic is an in-session run, not a terminal one) — **Handoff folded in (nothing durable
  was missing from the log) and the stub restored; the encoder-ceiling diagnostic's two halves
  landed with the design/pre-registration deliberately NOT taken.** *Data path* (`RecordingPlayer`,
  rl/collect.py): a scripted bot plays its own battles over the websocket while the expert —
  resolved through the ONE opponent-spec resolver, so the expert surface is exactly the
  training-opponent surface — supplies orders on our battle object (MixturePlayer's delegation
  pattern); every decision is recorded as (obs, mask, action, battle_id) using SeamPlayer's exact
  encode/mask/convert trio, so a row is bitwise what a learner would have seen. Three guards, each
  load-bearing and each tested: the recorded action is **round-tripped back through
  `action_to_order` and string-compared to the expert's own order** (the move index is relative to
  `active_pokemon.moves`, or `available_moves` for Struggle — a mis-index would teach the clone to
  name a DIFFERENT move under the very conversion deployment uses, and the only symptom would be a
  weak clone, i.e. the diagnostic's own failure verdict); `action >= 0` BEFORE that check, because a
  default order round-trips to itself on its way to indexing the mask from the wrong end; and
  `mask[action]`. Rows carry a battle id because an honest holdout splits on battles, never rows.
  *Collector* (`scripts/make_bc_dataset.py`): asyncio `battle_against`, gitignored data/ .npz,
  prints the recorder's win rate / decisions-per-battle / forced-row share / switch-move split.
  *Trainer* (`scripts/train_bc.py`): masked cross-entropy on the EXACT capstone actor (make_agent +
  the showdown_heur_512 hparams, so the checkpoint re-evals through eval_checkpoint.py unchanged),
  battle-level holdout, agreement reported twice — overall and over multi-choice rows, against a
  uniform-over-legal floor — plus per-epoch metrics JSON; actor-only optimizer (no value labels
  exist, and handing the critic to Adam would imply otherwise). *Verification*: 315 tests green (9
  new: 5 offline recorder tests on a hand-built Gen 1 position with real Pokemon/Move objects, 1
  live-server recorder test, 2 wandb-mode tests, plus the existing suite); full collect -> train ->
  eval_checkpoint smoke run live. **The one failing test
  (test_full_episode_contract_against_live_server, 'Can not reset player's battles while they are
  still running') is PRE-EXISTING — reproduced on the stashed, unmodified tree — and fires only when
  the whole suite runs with a server up; it passes when its file runs alone.** *Operational numbers
  measured, and they change the shape of the run*: collection **2,825 decisions/s** (2,000 battles =
  45k decisions in 16 s), training **~0.7 s/epoch at 40k rows x [512,512]**, and a 1,000-battle
  deterministic re-eval extrapolates to **~50 s** (50 episodes in 2.6 s) — so the entire P4
  diagnostic runs in-session in minutes, and dataset size is not a constraint (1M decisions is ~6
  min of collection). Also closed the standing operational nit: **wandb now defaults to
  `mode=offline`** in `WandbLogger` (an explicit `WANDB_MODE` still wins), so no launch depends on
  remembering the export; verified against the real wandb 0.28.1 signature. *Contamination
  disclosure, stated because pre-registration comes next*: the machinery smoke (2,000
  heuristics-vs-heuristics battles, 3 epochs, [512,512]) reached **0.756 val agreement on
  multi-choice rows against a 0.188 uniform-over-legal floor** and was still climbing — a pathfinder
  observation from a throwaway run, NOT the diagnostic; no win-rate number was produced, and the
  headline read (the clone's win rate vs the bot it copied) is untouched. *Deliberately left to the
  design session*: the pre-registered bands and the one-directional caveat, dataset size and
  epochs/early stopping, WHERE the rows are collected (these are the expert's own visited states —
  Phase 4's 2026-07-29 finding was that in-distribution and off-distribution capability differ
  enormously, so this is a decision, not a default), whether the value head gets labels, and whether
  a mutation battery is warranted. *Next*: design/pre-registration pass, then the milestone-3
  write-up + stop-rule decision.

- 2026-08-02 (P4 pre-registered — and the design pass's feature audit changes what the diagnostic
  IS: SimpleHeuristics is a near-closed-form function of encoded features, its setup branch is dead
  code upstream, and a FAIL can no longer indict the encoder's information content) — **The locked
  spec is in PLAN.md (Phase 5, "P4 — encoder-ceiling BC diagnostic"); this entry records the
  evidence and the reframing.** *Audit of SimpleHeuristicsPlayer source (poke-env 0.15.0), every
  claim probed live*: (1) forced switches — measured 20.5% of decision rows over 8,943 live
  decisions — are argmax `_estimate_matchup`, whose four terms (both directional type multipliers,
  spe base comparison, both hp fractions) are LITERAL per-mon encoder features, ties resolved by
  team order = slot order = encoded; (2) move choice is argmax bp x STAB x stat-ratio x acc x
  expected_hits x multiplier — every factor encoded except `expected_hits` (multi-hit; exposed 1.8%
  of move rows, chosen 0.29%); (3) **the setup-move branch never fires: `move.target == "self"`
  compares the int enum `Target.SELF` to a string — always False.** Confirmed two ways: SH's
  verbatim predicate matches ZERO gen1 moves, and live status-clicked-while-damage-available is
  4/7,140, all explained by immunity zeroing every damage score and the 0-0 tie resolving to slot
  order. So in our stack SH is a pure damage-maximizer + matchup-switcher — weaker than nominal in
  EVERY poke-env 0.15.0 deployment (internal comparability unaffected: every milestone number used
  this same SH; possibly worth an upstream report); (4) the stochastic fallback (`active is None`)
  never fires — 0 label disagreements in 8,943 triple-called decisions, both actives present on
  every recorded row — **label-noise floor = 0**; (5) hazard/dynamax/tera branches dead in gen1; spd
  base stat derivable (mirrors spa for all real gen1 species; the apparent counterexamples were
  mega/hisui/gmax formes sharing dex numbers). *The reframing, which corrects the handoff's
  "decisive if it FAILS" line*: the audit proves the encoder's information sufficiency for SH
  analytically — SH's score is writable as an arithmetic circuit over encoded features up to the
  expected_hits residue — so a low-agreement fail indicts the TRUNK/optimization (if supervised SGD
  can't fit a near-closed-form target, PPO never had a chance) or the BC method (drift), never the
  encoder's information content. And the existence proof sharpens: a faithful clone scores the
  mirror baseline b ~= 0.49 (measured 0.485 n=2,000, 0.492 n=400) > 0.42, the re-analysis's plateau
  asymptote — so if the run verifies the audit, the RL plateau sits ~7 points below a policy that is
  not merely representable but SUPERVISED-LEARNABLE on this exact trunk, and the plateau is
  training-side with a mechanism demonstration. *Bands locked* (R0 collection sanity / R1 fit health
  incl. a 20k-vs-10k data check on a common val set / R2 agreement >= 0.93 as fit gate, prediction
  ~0.97 / R3 headline: pooled 3x1,000 best-ckpt deterministic vs b, pass at >= b - 0.04 (~3 sigma,
  absorbs the battle_against-vs-SingleAgentWrapper instrument mismatch; maintainer approved the
  recommended margin) / R4 disagreement-concentration always run). Conditional arms pre-authorized
  but built only if triggered: [1024,1024] capacity probe, one DAgger round, one doubling to 40k
  battles. Contamination disclosed in the spec (smoke 0.756@3ep; probe stats are audit evidence the
  bands were set on). A passing clone doubles as a warm-start candidate above the RL best (0.49 >
  0.408) — flagged in the spec as a ladder decision NOT taken. *Next*: run script handed over (~25
  min, maintainer's terminal, server up); reads in-session from the artifacts; then the milestone-3
  write-up + stop rule with P4's answer in hand.
- 2026-08-02 (P4 COMPLETE: the plateau is training-side — the clone through the exact capstone
  encoder + trunk plays 0.453-0.465 vs SimpleHeuristics, +0.045-0.057 above the RL best,
  demonstrated twice; R2 closes partial with the data curve extrapolating onto the audit's predicted
  ceiling) — **Both batteries ran to completion in the maintainer's terminal (20k battles/450,864
  decisions, then the R1-triggered pre-authorized doubling: fresh 40k/903,090 at 2,769 decisions/s);
  every read taken in the locked order; 40k is the battery of record.** R0 PASSED both times (b =
  0.489 n=20k / 0.486 n=40k; 22.5-22.6 decisions/battle; forced-switch share 0.2034 vs the probe's
  0.205). R1: seed spreads 0.0049/0.0060 pass; the data gate FIRED at 20k (common-val 20k-vs-10k
  delta 0.0271) and data is STILL binding at 40k (fresh-common-ground delta 0.0212, both
  generations' s0 checkpoints scored on the 40k val battles neither saw) — the one pre-authorized
  doubling is spent, and the shrinking slope (+0.027 to +0.021/doubling, ratio 0.78) geometrically
  extrapolates to ~0.97, exactly the audit's predicted ceiling. R2 PARTIAL: best val free-agreement
  0.9017/0.8987/0.9047 (best epochs 9/14/10 of 40; train free-agreement 0.951 at best-epoch, same as
  the 20k generation's 0.954). **Disclosed deviation from the locked spec: the partial-band capacity
  probe was NOT run** — it was pre-registered to discriminate capacity-from-information when
  agreement CAPS, and agreement is not capping (still-climbing data curve, extrapolation
  on-prediction); under a binding data constraint its read is uninterpretable, so R2 closes as
  partial-trajectory-consistent rather than verified. R3 PASSED TWICE (the headline): 40k battery
  0.451/0.454/0.454, pooled 1359/3000 = 0.4530 >= 0.446 (b - 0.04); 20k battery independently
  0.478/0.445/0.473, pooled 0.4653 >= 0.449; combined 2755/6000 = 0.4592; the between-battery
  difference is 0.96 sigma - noise. The clone pays a real ~0.03 cloning tax vs b (~4 sigma on the
  combined read), inside the pre-registered margin. R4 DIFFUSE both generations, sharper at 40k:
  rest-bucket 67.5% of disagreements at 78.1% share; all-status agreement 1.000 (the slot-order tie
  rule fully learned — a clean audit confirmation); multi-hit-exposed only 2.1% of disagreements
  (the one true encoder residue is immaterial); the two weakest buckets — forced-switch 0.866 (up
  from 0.846 at 20k) and voluntary-switch-label 0.556 — are both boundary sharpness on the
  analytically-covered matchup argmax near ties, i.e. generalization, not missing information.
  **VERDICT (pre-registered R3 pass branch): the ~0.4 plateau sits below a representable,
  supervised-learnable policy on this exact stack — a measured 0.453-0.465 vs the eval bot,
  +0.045-0.057 over the 0.408 RL best and above the 0.42 asymptote — so the plateau is TRAINING-SIDE
  (signal/distribution/optimization), and the encoder is exonerated for it; the one-directional
  caveat stands (nothing here shows PPO can REACH that policy under terminal-only reward).** The
  passing clone doubles as a warm-start candidate above the RL best — still flagged as a
  milestone-ladder decision NOT taken. Artifacts: data/bc_p4_{main,sub10k,40k}.npz;
  runs/bc_p4_512_{s0,s1,s2,sub10k}/ and runs/bc_p4_512_40k_s{0,1,2}/ (bc_metrics.json +
  p4_eval_heur_1000.json each). *Next*: milestone-3 write-up + stop-rule decision, with P4's answer
  in hand; P3/P5 behind it.

- 2026-08-02 (milestone-3 write-up SHIPPED after a three-Opus adversarial pass; stop rule adopted —
  M3 ships now, the bar stops being chased under this recipe class, BC-warm-start deferred to its
  own pre-registration) — **README gains "Results — Phase 5: PPO + self-play on Pokémon Showdown
  (milestones 1–3)" plus a house-style figure (`scripts/make_showdown_figure.py` →
  `assets/showdown_milestone3.png`: curves for heur_512 + the three scratch seeds vs the 0.5 bar /
  0.42 projection / clone band; right panel locked-protocol finals with 95% CIs); Phase-5 status row
  updated.** *Verification*: every number recomputed from run artifacts before commit (two script
  passes, `verify_m3_numbers.py` in the session tmp dir) — finals, both cross-play orientations,
  parent cells, clone batteries, val agreement (`best_agreement_free` 0.9017/0.8987/0.9047 at 40k;
  0.8808–0.8857 at 20k), 4–6M rung bands, per-2M return-gain series (+0.153/+0.103/+0.061/+0.027/
  +0.016 exact), entropy medians, winrate_latest, cumulative anchor finals, s0's 0.396→0.365 dip.
  All match the log. NOT on disk, cited from committed log/spec with provenance stated: b
  (0.489/0.486, collector printout), the 0.262 500-battle probe, the common-val data-gate deltas.
  One windowing note: the [64,64] 4–6M band recomputes to 0.316 (the log's 0.312 was the 4.2–6M
  half-average); the write-up prints 0.346-vs-0.316, both freshly computed on the same window.
  wandb histories extracted to `runs/*/history.csv` (gitignored) for the figure. *Review pass*
  (maintainer pre-authorized; correctness / experiment-design-statistics / research-strategy):
  verdicts APPROVE-WITH-CORRECTIONS ×2 + one REJECT-until-reworked; all findings resolved, none
  overturned a campaign conclusion. The write-up-shaping corrections adopted: capacity ledger row
  had reprinted the budget-confounded 0.324→0.408 pairing the log itself refuses — replaced with
  the matched-budget band + shape attribution; "zero measurable gradient" (retired 2026-08-01)
  had crept back — replaced with below-instrument-resolution + the z=1.9 training-return trend +
  the ±0.14 recipe-level MDE; the windowed anchor was quoted at cumulative n≈10k instead of
  n≈400/window — fixed; the clone's MISSED R2 fit gate (0.899–0.905 vs ≥0.93) is now disclosed in
  the section body next to the verdict, not buried; 0.484 is named a resolvable deficit (z≈−2.5)
  and 0.474-vs-sp6m co-reported; ± convention unified (1 se unless labelled) with n=1-seed
  headlines flagged; "above the band" demoted to calibration; the ~0.42 projection dropped from
  the clone's load-bearing chain (verdict now rests on 0.453 vs 0.408, z≈2.5); Glicko-1 not Elo,
  Gen 7 not "this domain"; "P4" never appears in the README (it's "the cloning diagnostic"); the
  poke-env dead-branch bug promoted to its own findings bullet; headline finding moved above the
  fold; closing reframed as research strategy. **STOP RULE (decision of record this session,
  reviewer-backed; maintainer ratifies before any push): (1) milestone 3 ships with this write-up
  — no queued run gates it; (2) P3 runs post-ship as an analysis appendix; P5 (rollout_steps 512)
  is a REAL training probe and gets a pre-registered read + band + an explicit
  what-would-amend-the-section condition before launch (the entropy_coef 0.003 probe stays queued
  in the same optional set); (3) fixed-bot budget stops being spent on the 0.5 bar — measured flat
  at [64,64], projected short at [512,512]; from-scratch self-play at 16× budget is UNTESTED and
  deferred on cost, not excluded on evidence; the bar stays on the board, unmet and unmoved;
  (4) BC-warm-start from the clone is deferred to its own design session with pre-registered
  meaning — deciding in advance what a 0.5 from a BC init would count as, rather than after
  seeing the number.** Suite green at 316; HANDOFF folded (nothing durable missing) and restored
  to stub. *Next*: maintainer reviews the shipped section + ratifies the stop rule; push decision
  (3 commits ahead before this session's); then P3, and the P5 pre-registration.

- 2026-08-02 (later: stop rule RATIFIED by the maintainer; the write-up's two hardening steps taken —
  clone final-ckpt evals close the best-vs-final asymmetry as a measured non-issue, and the n=1 RL
  wedge side gets a pre-registered 2-seed replication, handed over for overnight) — **Maintainer
  ratified the stop rule and green-lit both reservations from the post-ship self-assessment.**
  *Reservation 2 closed by measurement*: all six clones' FINAL checkpoints re-evaluated (1000
  battles each, same harness; read rule stated before results: per-seed |final−best| within 2·se ⇒
  non-issue). Result: 40k battery best→final 0.451/0.454/0.454 → 0.462/0.475/0.461 (pooled 0.4530 →
  0.4660, z=1.0 — final slightly HIGHER); 20k battery 0.478/0.445/0.473 → 0.446/0.453/0.465 (pooled
  0.4653 → 0.4547, z=0.8); every per-seed |z| ≤ 1.44, pooled deltas opposite in sign across
  batteries. No selection effect; README disclosure gains the measured parenthetical. Artifacts:
  runs/bc_p4_512{,_40k}_s{0,1,2}/p4_eval_final_heur_1000.json. R3-of-record stays the best-val read
  per the locked spec. *Reservation 1 — PRE-REGISTERED before launch*: `showdown_heur_512_s{1,2}`,
  the s0 config verbatim (12M, [512,512]), seeds 1/2, 2-wide concurrent, locked finals in the same
  script (final ckpt_012000000, 1000 fresh battles, default seed rung). **Locked read: the 3-seed
  pooled p_RL (n=3000) + seed spread REPLACES the n=1 0.408 in the README's wedge sentence and
  milestone table regardless of direction. Verdict retention rule: the "clone above the RL best"
  wedge stands as RESOLVED iff clone-40k pooled 0.4530 − p_RL ≥ 2·se_diff (se_diff ≈ 0.013, i.e.
  p_RL ≤ ~0.427); 0 < gap < 2·se_diff ⇒ downgraded to "consistent but not resolvable at these n"
  and the README amended to say so; p_RL ≥ 0.4530 ⇒ the wedge premise is FALSE as pooled and the
  training-side section gets a correction, not a reframing. Curve shapes and rungs recorded, not
  gated; the best-rung-≠-final watch continues; no gate on seed spread — it is the measurement.**
  Prediction, recorded as such: mix512's seed-std was 0.008 and sp6m continuation's 0.031; where
  fixed-bot 12M lands is genuinely open. Launch script `heur512_seeds.sh` in the session tmp dir,
  handed over for the maintainer's overnight terminal; tree committed clean before handover. *Next
  session*: the pre-registered read from disk, README amendment per the rule, then P3 and the P5
  pre-registration.

- 2026-08-02 (overnight close-out: heur_512 replication COMPLETE — the wedge survives its
  pre-registered test and SHARPENS; README amended per the locked rule) — **Both runs trained clean
  in the maintainer's terminal (launched 18:29:43, stamped `b87f6a0` / `git_dirty: false`, ~685
  steps/s 2-wide, done ~23:20; the script ran both locked finals itself; 30-min read-only
  monitoring loop reported throughout, no interventions).** *The pre-registered read, taken at
  23:30*: finals s1 411/1000 = 0.411 (ties 17), s2 432/1000 = 0.432 (ties 18); pooled with s0's
  408/1000: **p_RL = 1251/3000 = 0.4170 ± 0.0090, seed-std 0.0131, spread 0.024** — the fixed-bot
  12M cell is tight (nothing like sp6m's 0.061 continuation spread), s0 was the LOW seed, and the
  n=1 caveat on the lineage's key number is retired. **Retention rule fired RESOLVED: clone 0.4530
  − 0.4170 = +0.0360 ≥ 0.0256 (2·se_diff), z = 2.81** — the wedge narrowed in points (0.045 →
  0.036) and sharpened in resolution (z 2.5 → 2.8), and even the best fixed-bot seed (0.432) sits
  below the clone; the training-side verdict stands on a 3-seed RL base. Side notes: s2's 0.432
  equals the cont6m pooled endpoint — the 12M seed distribution reaches the continuation's value,
  consistent with the ~0.42 projection; the turn-1000 auto-tie warning appeared once in s1's log
  but eval ties stayed 1.7–2.1% (stall long-tail, rare as before). *README amended per the locked
  rule (9 edits)*: status row, protocol paragraph (only M1 is single-seed now), milestone-2 table
  cell (0.417 ± 0.009 pooled, per-seed listed), ledger header "four levers to ~0.42", capacity row
  (s0 final + replication), plateau bullet (0.38–0.42 band), the wedge sentence (+0.036, z ≈ 2.8,
  CI +0.011..+0.061, replication named), the milestone-2 caveat, compute line (~140M steps, ~27 h);
  figure regenerated with all three fixed-bot seeds and a pooled 3-seed finals row
  (`runs/showdown_heur_512_s{1,2}/history.csv` extracted for it). Artifacts:
  runs/showdown_heur_512_s{1,2}/ (full ckpt ladders, final_eval_heur_1000.json each, offline wandb).
  *Next*: push decision (maintainer), P3 (~20 min analysis), P5 pre-registration, BC-warm-start
  design session behind them.

- 2026-08-03 (pushed public; P3 COMPLETE — the observable draw prices at ~4% of outcome variance,
  real but modest; P5 pre-registered with its matched control evaluated before launch) — **Origin
  synced through `17ae11b` on the maintainer's go — the milestone-3 section is public.** *P3
  (team-luck variance decomposition, `scripts/p3_team_luck.py`, diagnostic outside the ladder)*:
  instrumented re-evals of the three heur_512 finals (1000 battles each, locked protocol ladder,
  own-team species + opponent LEAD recorded per battle — the opponent's revealed team is
  deliberately EXCLUDED as post-treatment: longer battles reveal more mons and would leak outcome;
  interpretation guard stated in the script docstring: a Bernoulli mixture has unchanged block
  variance, so team luck does not widen eval-mean se — the instrument prices the TRAINING signal).
  Read: ridge linear-probability on own-multi-hot + lead-one-hot, per-checkpoint centering, 5-fold
  CV R² maxed over a λ-grid against a permutation null running the identical procedure. **Result:
  CV R² = 0.0375 on n=3000 / 146 species vs null median ≈ 0 (95th pct 0.0015, p < 0.005) — the
  observable draw explains ~3.7–4% of per-battle outcome variance, a lower bound** (full opponent
  team, movesets and in-battle rolls are unobserved). Coefficients face-valid: own Electabuzz
  +0.098, Mewtwo +0.072, Abra/Alakazam +0.07 win-prob; Tangela/Parasect/Grimer ≈ −0.07. Fresh
  win-rate sanity: 0.406/0.398/0.430, within noise of the finals. **Verdict: "the draw decides the
  battle" is NOT supported at the species level — the training-signal noise floor is dominated by
  in-battle stochasticity and play, not the draw per se** (Gen 1's crit/freeze RNG lives in the
  residual, unseparated). Per the stop rule: log-only appendix, the shipped section is untouched.
  *P5 pre-registered* (`configs/showdown_r512.yaml`, full read in the header): rollout_steps 128 →
  512, one variable on the heur_512 recipe, 6M × 3 seeds. **Control evaluated BEFORE launch:
  heur_512 ckpt_006000000 s0/s1/s2 → 324/390/351 per 1000, pooled 0.3550 ± 0.0087 — credited iff
  the probe's pooled finals ≥ 0.381 (2·se_diff).** Side fact worth keeping: the 6M seed spread is
  0.066 where the 12M spread was 0.024 — the seeds CONVERGE as they approach the plateau, which is
  itself plateau-consistent behavior. Launch script `r512_probe.sh` in the session tmp dir (~2.6 h
  3-wide, finals in-script); handed over. *Next*: the P5 read per the config header when the run
  lands; then the BC-warm-start design session (the next chapter's opener).

- 2026-08-03 (P5 CREDITED — the first credited lever since capacity: rollout_steps 512 lifts the
  6M win rate 0.355 → 0.392 at z = 3.0, and the whole curve moves, not the endpoint) — **The probe
  ran clean in the maintainer's terminal (3-wide, ~587 steps/s, launched on the pre-registration
  commit `be8050e` / `git_dirty: false`, ~2.9 h, finals in-script; 30-min monitoring loop, no
  interventions). Every read per the locked header, in order.** R0 gates PASSED: late entropy
  medians 0.293–0.298 (band [0.2, 1.0]); eval ties 1.8–2.5% (≤4%); throughput 587/685 = 86% of the
  2-wide reference (within ~25%). **PRIMARY: per-seed 0.397/0.384/0.396, pooled 1177/3000 = 0.3923
  ± 0.0089 vs the pre-launch control 0.3550 ± 0.0087 → Δ = +0.0373, se_diff 0.0125, z = 3.00 —
  ABOVE the 0.381 credited line. CREDITED.** Secondaries (recorded): 4–6M rung bands
  0.396/0.383/0.386 vs the baseline recipe's 0.346 same-band — the whole trajectory is shifted,
  not a final-checkpoint artifact; late approx_kl medians 0.0055–0.0057 vs the baseline's ~0.013 —
  the 4× batch moves less per update at fixed lr, as the header predicted; seed spread 0.013.
  Headline reading, stated carefully: at HALF the budget the r512 recipe reaches 0.392, within
  noise of the base recipe's 12M s0 final (0.408) and ~2.8 se below the 12M pooled 0.417 — a real
  SNR effect on the APPROACH SPEED; whether it moves the ~0.42 plateau itself is exactly what the
  6M probe cannot say (the base recipe was also still climbing at 6M). Per the pre-stated
  amendment condition, the README "Where this goes next" paragraph gains the measured sentence for
  both mechanism reads, and the **12M-extension decision OPENS (~5.2 h 3-wide, not taken here)**:
  if a 12M r512 run cleared the 0.42 projection it would be the first recipe to move the plateau —
  and it would interact with the BC-warm-start chapter (a better base recipe changes what the
  warm start should be grafted onto). Maintainer decisions queued, in order: (1) 12M r512
  extension vs straight to the BC-warm-start design session; (2) push (this session's commits are
  local). Artifacts: runs/showdown_r512_s{0,1,2}/ (ckpt ladders, final_eval_heur_1000.json,
  histories, offline wandb).

- 2026-08-03 (prior-work verification: the maintainer's external briefing survives with corrections
  at the edges — three-Opus dig on Wang, ps-ppo, and the wider field; 0.39–0.42 sits inside the
  credible scratch-PPO band, and the two levers the literature actually credits are LR annealing
  and BC init) — **`PHASE5_PRIOR_WORK_BRIEFING.md` (maintainer's no-repo-access session: Wang
  thesis read in full, ps-ppo from a search snippet only) verified per its own provenance flags:
  one agent re-read the thesis PDF from DSpace, one cloned ps-ppo with full history and read all
  ~4.7k lines, one swept the field for independent pure-policy-vs-SH datapoints.** *Wang (Source
  A)*: every core claim verified verbatim — the LR-anneal ablation (constant lr stuck ~0.55 vs
  ~0.80 annealed, §3.1.4; the ONLY controlled single-variable ablation found anywhere in this
  literature, decay constants admittedly untuned), the exact hyperparameter table, sparse terminal
  reward, no recurrence (durations one-hot instead), the non-lockstep race-condition note,
  both-players collection, 3v3 surrogate tuning. Corrections: "search bought ~12 points" is
  arithmetic on a table with no stated N and no error bars, and Fig 4.1 reports ~0.85 vs SH for
  what Table 4.1 scores at 0.786 — unreconciled in the thesis; the env-stepping-bottleneck quote
  is about MCTS inference rollouts, not training collection; action count is ~495 and
  "switch-by-species" was an inference. **New, missed by the briefing: Fig 4.1 digitized
  (calibration self-validates against the thesis's stated 40M→0.80 / 150M→0.85 anchors) — winrate
  vs SH ≈ 0.30 at 2M, crosses 0.50 at ~4M, 0.575 at 6M, 0.64 at 8M** — the reference gen4 agent,
  with tuned hyperparameters and annealed lr, was at 0.575 at our exact budget; nearly all its
  remaining gain was bought 6M→60M. Also: NO opponent pool — pure latest-vs-latest self-play, SH
  the only external anchor, no pathologies reported; a curriculum negative result (k-Pokémon
  specialist bootstrapping tried, "no significant improvements" over scratch 6v6); total PPO loss
  ROSE all run (entropy + shrinking advantages — not a progress signal); eval determinism never
  stated; Wang explicitly rejected Gen 1 as a format ("no real counters to strong Psychic-types").
  *ps-ppo (Source B)*: the headline is real and understated — the committed ladder screenshot
  shows gen9randombattle Elo 2102 / GXE 76.7% / Glicko-1 1725 ± 25, single-forward-pass inference
  confirmed in code (sampling at temp 1.0, no search/damage calc), and the claim escalated
  1600 → >1600 → >1900 in step with a live run. But **the briefing's calibration number — "Wang
  MLP replication plateaued ~1100 Elo" — has ZERO support: no MLP exists anywhere in the repo or
  its git history**; treat as anecdote. The >85%-vs-SH figure is unreproducible (no eval script at
  HEAD, no methodology; training is mirror self-play and never touches SH), and the architecture
  attribution is confounded with no ablation: the transformer run also differs by obs encoding,
  BC-from-SH warm start, faint shaping (±0.1 vs ±1 terminal), and scale (>250M states, 2 days on a
  3090; model is only 14.5M params — not a scale story). Transferable regardless: **BC-fit-to-the-
  heuristic as an architecture screen** ("configurations that failed to imitate perfectly were
  discarded"), a second no-opponent-pool datapoint, and post-BC per-zone LR multipliers (backbone
  0.5×/0.1×, value head 2×). *In-repo checks (this session)*: all Showdown configs train FLAT lr
  2.5e-4 (scratch12m pins `lr_anneal_steps: 0`; the anneal machinery exists, `ppo.py:419`) — the
  2026-08-01 "lr test meaningless" rejection was about MAGNITUDE under per-minibatch advantage
  normalization, so a schedule probe is arguably not covered by it, and MinAtar's "anneal cost
  35%" is the in-repo counter-evidence to weigh. And **poke-env 0.15.0's SimpleHeuristicsPlayer
  `_stat_estimation` carries the boost bug ps-ppo patched** (`boosts[stat] > 1`: a +1 boost falls
  to the else branch and evaluates 2.0× — the +2 multiplier — instead of 1.5×): our numbers and
  Wang's are vs the stock bot, ps-ppo's vs a patched one — comparability caveat, not a
  mid-campaign change. *Field sweep (best of it)*: **VGC-Bench (arXiv 2506.10326; scratch
  transformer PPO, 5M steps, gen9 VGC doubles, 100 games/cell, 5 seeds) — scratch self-play 0.48
  vs SH, and BC-initialized variants 0.62–0.78: +25–30 points at matched budget, the largest
  well-evidenced lever found anywhere.** Its 1-team payoff matrix is cyclic (DO scores 0.0 vs SH
  while beating FP) — a single SH winrate is a projection, not a ranking; worth a README sentence
  someday. pokejax: gen4randombattle scratch PPO ~0.55 vs SH (n=20, wide CI) at 378M JAX-engine
  steps, plus a free bridge-bug checklist to audit ours against — stale `available_moves` for 1–2
  turns after every switch (they measured 15.9% of turns affected), PP never decrementing in local
  games, a sleep-turn off-by-one. Gen-1 specifics: Metamon measured SH at 16W–59L (~0.21) vs the
  human ladder in Gen1OU — SH's WEAKEST format relative to humans; the NeurIPS 2025 PokéAgent
  Challenge saw Foul Play (MCTS + Rust engine) win Gen9OU but place only #8 in Gen1OU, where pure-
  policy RL took #1 and #2 — **the pure-policy handicap is smallest in exactly the format this
  project chose**; and no public gen1randombattle RL agent was found — this appears to be the
  first. Metamon self-play correction (nuances the PLAN §5.3 cite): the paper's naive latest-
  checkpoint arm underdelivered, but post-paper, large DIVERSE agent-vs-agent datasets became the
  main driver — the surviving lesson is naive-vs-diverse, not self-play-fails. Also: poke-env
  issue #332 reports per-battle time growing over long runs. *Lever ranking by evidence*: (1) LR
  annealing (controlled ablation, one source); (2) BC init (three independent sources, biggest
  effect); (3) diverse-opponent self-play at scale; (4) train-opponent at least as strong as the
  eval opponent; curriculum-over-heuristics reported not-helping twice. Encoder-ceiling read: the
  briefing's architecture signal does not survive verification as evidence, but the BC-as-
  capacity-screen idea folds into the already-queued BC-warm-start design session. **No decisions
  taken — open for the maintainer, in order: (a) direction: 12M r512 extension vs an LR-anneal
  probe (new candidate; needs pre-registration and the scope reconciliation above) vs straight to
  the BC-warm-start design session; (b) push (local commits); (c) optional cheap bridge audit vs
  the pokejax checklist.** Verification artifacts (thesis PDF, ps-ppo clone) live in the session
  tmp dir — ephemeral; the briefing file stays untracked pending the direction discussion.

- 2026-08-03 (later: direction set by the maintainer — bridge audit CLEAN, P5b LR-anneal probe
  pre-registered for overnight, prior_work/ archived, origin synced) — **Maintainer decisions on
  the verification dig, verbatim intent: BC-warm-start design session confirmed HIGH-PRIO (next
  chapter's opener); LR annealing WILL be tested — the session's lean to fold it into the BC
  session was overridden, with the MinAtar anneal-cost-35% transfer explicitly discounted as
  cross-game — overnight run slots offered; bridge audit approved; push approved.** *Pushed
  through `957b4c1`*: the P3/P5 backlog, the verification fold, and `prior_work/` (index + the
  maintainer's briefing tracked; Wang/VGC-Bench/Metamon/PokéAgent PDFs, ps-ppo README +
  ladder screenshot, pokejax analyses + training log, EliteFurretAI RL.md, saketatreya write-up,
  Ivison post all archived LOCAL-ONLY under `prior_work/*` gitignore — third-party copyright +
  ~33 MB; `git add -f` if the maintainer ever wants them in history). *Bridge audit vs the
  pokejax bug list: CLEAN.* 30 battles / **866 decisions (402 immediately post-switch) against
  heuristics on the exact obs+mask path the agent sees: 0 stale `available_moves` (their 15.9%
  does not reproduce — our request-driven Gym path reads post-request state; their bridge
  presumably read mid-cycle), 0 action-mask mismatches** (probe recomputed expected move bits
  from known∩available plus the single-move fallback rule; 35 fallbacks seen, all by-design
  recharge/locks), **PP tracks** (551/866 decisions saw below-max PP, 362 observed post-use
  drops; the 72 unchanged-after-choice are unexecuted moves — sleep/full-para/locks, expected in
  Gen 1), sleep `status_counter` moves. The headline number is not depressed by this defect
  class. Probe `bridge_audit.py` in the session tmp dir, ephemeral. *P5b pre-registered*
  (`configs/showdown_r512_lra.yaml`, full locked read in the header): **one variable,
  `lr_anneal_steps` 0 → 6M (linear 2.5e-4 → 0, existing `ppo.py` machinery, no code change) on
  the credited r512 recipe, 6M × 3 seeds; control = the r512 probe itself, pooled 0.3923 ±
  0.0089, already evaluated under the locked protocol. CREDITED iff pooled finals ≥ 0.418
  (Δ ≥ +0.025 = 2·se_diff).** Stated divergence: Wang's schedule is a power decay with untuned
  constants; this tests the linear class the repo implements — a null exonerates linear
  annealing here, not annealing in general. Extension note pinned in the header: an annealed 6M
  ckpt cannot be warm-extended (`train.py` refuses `init_from` + `lr_anneal_steps`); a 12M
  anneal test is its own run. Launch script `lra_probe.sh` (session tmp) handed over — ~2.9 h
  3-wide. The 12M flat-lr r512 extension decision stays OPEN, untaken.

- 2026-08-03 (latest: Wang's GitHub forks read — the MCTS forward model turns out to be UPSTREAM,
  in our own checkout; scope decisions ratified: MCTS open as a follow-up phase, pure-self-play
  retired as an identity constraint) — **The maintainer located Wang's GitHub (`quadraticmuffin`)
  and provided full fork-vs-upstream diffs for his three repos (archived:
  `prior_work/wang_fork_diffs.md`); read in full, key claims verified against our tree.**
  *pokemon-showdown fork (13 commits, 6 files)* — the thesis's determinization machinery.
  Headline (spotted by the maintainer's teammate, verified here at file:line): **battle
  serialization is upstream Showdown, not Wang's work** — `State.serializeBattle`/
  `deserializeBattle`, `Battle.toJSON`/`fromJSON`, `resetRNG(seed=null)` (fresh chance draws per
  rollout), `restart()`, `undoChoice` all exist in our vendored checkout (`showdown/sim/
  state.ts:61,84`; `showdown/sim/battle.ts:318,322,360,1968,3029`). Wang added two stream
  commands — `>getstate` (state → JSON) and `>load` (deserialize + restart + undo pending choices
  + resetRNG(null) + reroll the opponent's unrevealed team under revealed constraints +
  re-request) — plus `SetCriteria`/`rerollTeam`/`replaceSet` and ~370 lines of gen4 constrained
  team-gen (hallucinated Hidden Power types, weather-probability ability sampling, volatile-aware
  move disabling). **MCTS cost estimate revised DOWN: the forking interface is a few hundred
  lines against existing machinery** (gen1 port target `showdown/data/random-battles/gen1/
  teams.ts`); the remaining cost is the search stack itself (Wang: 20 workers, 1000–2000
  rollouts/move, ~10 s/move — evals go ~100× slower). Gen-1-izing the constraint problem: no
  Encore/Taunt/choice items — the surviving volatile constraints are Disable (a resampled set
  must contain the disabled move), lock states (Wrap/Thrash/recharge: trivially satisfied, the
  locked move is revealed by use), and Transform. Also in the fork, RL server hygiene for long
  runs: clear players from finished rooms (usernames train*/eval*), gutted `onEnd` (no
  ladder/replay work per battle), tie-restriction removed — the fix pattern if a long run ever
  shows the poke-env-#332 slowdown signature (12M extension watch item). *poke-env fork (36
  commits)* — state-tracking corrections, almost no architecture. Both encoder-relevant fixes
  verified ALREADY UPSTREAMED in our 0.15.0 (`[from] lockedmove` → `use=False`; sleep
  `status_counter` incremented in `cant_move`); most of the rest is structurally impossible in
  gen1 (Max PP tables, Sleep Talk, Curse ???-type, ability weather, Trace, `_orig_item`, choice
  lock). The risk CLASS stays live — our own gen1 findings prove it (SH setup branch dead on the
  0.15.0 enum bug; Light Screen → `Effect.UNKNOWN`) — but is bounded by the clone (0.453 through
  this exact encoder). Optional hardening item, unregistered: a differential obs audit, encoder
  fields vs the raw protocol log over sampled battles. Notably absent from all three forks: the
  non-lockstep parallelization (it lives in his unpublished training code, as do masking and the
  LR schedule). *SB3 fork (8 commits)* — pure throughput instrumentation (rollout/train/callback/
  eval time splits, CSV logging): confirms stock SB3 PPO; the thesis hyperparameters are tuned
  values in SB3's knob shape. **Scope decisions (maintainer, in-discussion): (1) MCTS is OPEN as
  a follow-up phase — inference-time-only in Wang's pattern, so it composes with every training
  lever and nothing done now forecloses it; the Phase-4-era "no forward model" premise is
  formally revised in PLAN.md (it meant "no cheap forward model", and even that is now priced).
  Keep the value head healthy — search truncates rollouts at leaves with V. (2) The capstone
  need not be a pure self-play agent — BC init, reward shaping, and teacher data are first-class
  recipe components for the BC-warm-start design session, designed and pre-registered as a
  stack.** P5b launched by the maintainer ~20:56 on `5074c1b` (3 seeds up, liftoff clean, the
  auto-tie server notice benign as before).

- 2026-08-03 (latest+1: THROUGHPUT PRIORITIZED — the next chapter opens with a speed session,
  before the BC design session; Wang's training speed demystified by arithmetic) — **Maintainer
  decision: after the P5b read, a dedicated throughput session precedes the BC-warm-start design
  session — cheaper steps compound into every later pre-registration (budget was itself a
  credited lever). Goals recorded in the PLAN.md Phase 5 scope block.** The calibration that
  motivated it: **Wang's 150M steps / 4 days is ~434 steps/s AGGREGATE on 80 cloud CPU workers**
  (~5.4 steps/s/core; ~8.7 battles/s with both-perspective double-counting) — while the laptop's
  live 3-wide campaign runs ~1,760 steps/s through the full training loop on ~3 of 14 cores.
  Wang's scale was wall-clock and 2×-perspectives, not per-core speed; his 150M ≈ 3.5 days of
  single-lane laptop time at current rates. Live utilization during P5b (ps snapshot): three
  python lanes at 58–72% CPU each, node server group ~100% total (≈1 core) — consistent with the
  2026-07-29 measurement-(c) knee (shared server peaks at W=2, declines after; per-worker servers
  scaled to ~7.5k dec/s at W=4–8) and with the observed 685 → 587 per-run drop going 2-wide →
  3-wide. Framing settled in-discussion: **server sharding is the UNLOCK, not the prize** —
  direct gain on the 3-lane pattern is only +15–20% (undoing the shared-server regression), but
  it is what lets lane count scale to the cheap 2–3× aggregate; the decision-lockstep facade
  (gated on measurement (e)) remains the lever for long SINGLE runs; both-players collection is a
  self-play-only 2× (a scripted opponent's seat is off-policy data for PPO). Ops note pinned in
  STATUS: no `rl/` source edits until `lra_probe.sh` exits FULLY — its finals stage boots fresh
  python that imports `rl`.
- 2026-08-04 (P5b CREDITED — LR annealing is the second credited lever on the r512 recipe; first
  result above the ~0.42 plateau) — **Pooled 3-seed finals 1330/3000 = 0.4433 ± 0.0091 vs the r512
  flat-lr control 0.3923 ± 0.0089: delta +0.051, twice the +0.025 credit line (z ≈ 4.0). Per seed
  0.416 / 0.468 / 0.446 — every seed individually at or above the credit threshold.** Read taken
  exactly per the locked header in `configs/showdown_r512_lra.yaml`; runs launched 2026-08-03
  ~20:56 on `5074c1b`, finals landed ~23:47 (~2.85 h 3-wide), `lra_probe.sh` fully exited before
  any read. **R0 gates all pass:** late (≥5.5M) entropy 0.306–0.315 — frozen as pre-stated
  (lr → 0), inside [0.2, 1.0]; ties 1.7–2.2% (≤4%); steps/s 614–616 vs the 587 basis (within 5%,
  gate was 25%). **Secondaries (recorded, not gated):** the whole late band moved, not just the
  frozen endpoint — seed-mean rung win rates 4/5/6M = 0.410 / 0.437 / 0.407 vs r512's
  0.396 / 0.383 / 0.386 (rungs are n=100 noise; the n=1000 finals are the signal). approx_kl
  shrinks with the schedule as expected: 0.0044 (0–1M) → 0.0034 (2–3M) → 0.0018 (4–5M) → 0.0004
  (5.5–6M). Entropy falls 0.77 → ~0.35 by 2–3M and stops falling at ~0.31 from ~4M on. **What it
  means:** 6M annealed finals (0.4433) sit ABOVE the 12M flat-lr fixed-bot pooled 0.417 ± 0.009
  and its best seed 0.432, and within noise of the BC clone's 0.453 — the plateau moved via a
  training-side change, consistent with P4's training-side localization. Wang's anneal ablation
  transfers directionally at this scale (his 0.55 → 0.80; ours 0.392 → 0.443, smaller but real).
  **Amendment executed per the pre-stated condition:** README closing paragraph gained the
  measured sentence; the anneal joins the recipe for any 12M-extension question — which is now a
  from-scratch `lr_anneal_steps: 12000000` run (annealed ckpts cannot be warm-extended;
  train.py refuses). Next per the standing order: throughput session, then the BC-warm-start
  design session (the anneal verdict slots into that package as a now-credited component).
- 2026-08-04 (THROUGHPUT SESSION — the shared-server ceiling was `simulator: 1`, not the node
  process; collection-only benchmarks overstate full-loop gain ~7x; the facade closes as a
  self-play-scoped item; a startup-crash hazard found) — **Work item (1) resolved by a ONE-LINE
  edit to a gitignored file: `showdown/config/config.js` `simulator: 1 -> 4`. The planned
  server-port knob in the env seam and one-server-per-lane were never written; no `rl/` source
  changed this session.** The 2026-07-29 measurement-(c) basis for "shared server peaks at W=2,
  sharding is the unlock" had been taken against a single simulator child — the mechanism was
  identified in the 2026-07-30 async review and `simulator: 4` named as the lever to try ahead of
  any facade, but nobody had flipped it. **Shared-server collection, simulator: 4 (same machine,
  14 logical / 10 performance cores, script defaults 128 battles/worker, 16 in flight): 2,237 /
  5,246 / 7,096 / 9,233 / 11,024 / 11,313 / 9,966 decisions/s at W = 1/2/3/4/6/8/12** — monotone
  through W=8, plateau at W=6-8 (6->8 buys 2.6%), turns over by W=12 (-12%, mean inference share
  0.137). Against the simulator:1 shared curve that is **+81% at W=4 and +120% at W=8**, and it
  **BEATS one-server-per-worker at simulator:1** (7,341 at W=4, 7,545 at W=8) **by 26-50%**.
  Mean inference share now holds 0.19-0.23 across the curve where it used to collapse 0.26 ->
  0.05. **Server sharding is RETIRED as the lane-scaling unlock** — it would have been strictly
  worse than a config edit. W=1 reads low (2,237 vs 3,646 shared/simulator:1): cold-boot artifact,
  same class as the recorded per-worker W=1 anomaly; crossover is W>=2.
  **Full-loop lane scaling — the number the goal is actually denominated in** (150k-step lanes,
  `configs/showdown_r512_tput.yaml` = the r512 recipe with only `total_steps` and `run_name`
  changed, median of `time/steps_per_sec` with the first 10% dropped): **W=3 -> 659 steps/s per
  lane (mean 638), 3/3 lanes complete; W=6 -> 556 per lane (mean 542), 5/6 complete.** Goal (i),
  restore >=685 at 3-wide, **NOT met** (659, ~4% short). Goal (ii), lane scaling W=3-6 through the
  full loop, **met**: 3->6 costs 15.6% per lane and returns +41% aggregate across the five that
  ran (~+69% extrapolated to six) — a 3-seed probe takes ~19% longer at 6-wide but you can run two
  at once, which is the hypothesis-turnover compounding the PLAN scope block wanted.
  **THE FINDING, and it outranks everything else here: collection-only benchmarks overstate the
  full-loop gain by ~7x.** `simulator: 4` bought ~29% collection-side at W=3 and **+3.7%
  end-to-end** (P5b lanes averaged 615 steps/s; these averaged 638 — same recipe, same 3-wide,
  same machine, only `simulator` differs). **The loop is update-and-encode bound, not collection
  bound.** That contradicts a load-bearing Phase-5 planning assumption: the hardware note, the
  collection-loop architecture work, and the interest in surrogate-task tuning all rest on
  collection being the constraint. Highest-leverage optimization is now (1) the observation
  encoder — our own Python, run per decision — and (2) the PPO update, the one component where a
  GPU could plausibly matter at [512,512]. **Next item: instrument the loop split (collect /
  encode / update / eval as separate timers).** Wang needed exactly this instrument and could not
  get it from stock SB3: his stable-baselines3 fork is 8 commits and 7 are throughput
  instrumentation (`record fps for rollout only; ignore train, eval`, `track rollout, train,
  callback time separately`, `eval fps reporting in EvalCallback`, plus a later fix
  `train_fps should * n_envs`) — `prior_work/wang_fork_diffs.md` line 3998ff.
  **Decision-lockstep facade CLOSED — on reframing, not on a new measurement, and SCOPED not
  permanent.** Prize 1 (batching opponent forwards) priced today at the real width, offline, no
  server: **[512,512] batch-1 83.1 us/sample vs batch-8 41.4 us/sample = 2.04x**; at num_envs=8
  that replaces 676 us of serial batch-1 opponent forwards with one 351 us batch-8 forward, saving
  ~325 us of a ~13 ms vector step = **2.5% under self-play and EXACTLY 0% under
  `opponent: heuristics`**, where seat 2 is scripted Python with no network in it. Every queued
  run uses heuristics, so **the facade is a self-play-only item, not a throughput item.** Prize 2
  (decoupling battles-in-flight from num_envs) is bounded by how much server-wait exists to hide,
  and 29%-collection -> 3.7%-end-to-end says almost none — corroborating the recorded process
  CPU/wall of 0.97 at 8 battles in flight. **CORRECTION TO THE RECORD:** the late-July
  "at [512,512] batch-1 is compute-saturated, batching headroom ~zero" is measurably wrong — the
  headroom is 2.04x. Right verdict, wrong arithmetic. The `[64,64]` hardcode in
  `scripts/showdown_throughput.py` has now caused TWO misreads (that one, and this session's
  collection-vs-full-loop overstatement); anything quoted from that script must carry its width.
  Incidental: at [512,512], batch-2 costs MORE per sample (100.9 us) than batch-1 (83.1 us), a
  BLAS matrix-vector to matrix-matrix path switch — micro-batching at very small N is
  counterproductive here. **Revisit trigger:** when a self-play chapter is actually being
  designed, priced as a code-cost tradeoff (2-4x the code on the shared collection seam) at that
  recipe and hardware.
  **A `num_envs` sweep {8,16,32} at constant `n_steps x num_envs` was designed and DROPPED before
  running**, on three grounds: (a) it would run under `opponent: heuristics`, where prize 1 is
  zero by construction, so it cannot test what it was meant to test; (b) holding the product
  constant fixes the buffer at 4096 but shortens the per-env horizon — at a measured mean episode
  length of 27.7 steps that is 18.5 -> 9.2 -> 4.6 episodes per env per rollout and boundary
  truncation 5.4% -> 10.9% -> 21.7% at gamma 1.0 with terminal-only reward, a learning change
  rather than a throughput isolation, and `n_steps=128` gives back one of the two things P5
  changed (P5 moved rollout length AND batch together, 1024 -> 4096, and never isolated which half
  carried the +0.037); (c) the proposed 1.3x closure bar had no cost basis — this repo derives its
  thresholds (P5b's was 2*se_diff), and the real question is what gain justifies 2-4x the code on
  the shared seam. **Standing point: you cannot vary `num_envs` without moving either the buffer
  or the horizon — that coupling is exactly what the facade exists to break, so the sweep
  demonstrates the facade's motivation while failing to price it.**
  **STARTUP-CRASH HAZARD (new; affects every multi-seed launch).** W=6 lane s5 died with SIGSEGV
  before writing a single log line or creating its run dir, and `tput_lanes.sh` printed "done"
  over a 5-of-6 result. macOS crash report: `EXC_BAD_ACCESS` on the main thread in torch lazy
  static init — `THPVariable__parse_to` -> `PythonArgParser` ctor -> `_PyUnicode_InternMortal` ->
  `PyDict_SetDefaultRef`, bottoming at `PyEval_EvalCode`. **Not memory** (24 GB, 54% free). A
  second related crash at 2026-08-03 23:45:34 during the P5b finals: SIGABRT in
  `c10::InternedStrings::~InternedStrings()` under `__cxa_finalize_ranges` (libmalloc: pointer
  freed was not allocated) — process TEARDOWN, after artifacts were written. **P5b results are
  unaffected**: all three lanes carry ~214k-row histories and the finals came from separate eval
  processes; pooled 0.4433 stands. **Mitigation required in every future launcher: stagger lane
  starts, and assert all W run dirs exist with complete histories before reporting success** — the
  failure mode is a pre-registered pooled read that silently becomes 2 seeds instead of 3.
  Artifacts `runs/showdown_tput_w3_s{0,1,2}` and `runs/showdown_tput_w6_s{0..4}` are disposable.

- 2026-08-04 (later: loop-split instrument LANDED and it overturns half of this morning's
  inference — the update is 5.4% of the loop, not a bottleneck; P6 12M launched; a poke-env
  USERNAME COLLISION killed an entire arm and is now a standing constraint on concurrent runs) —
  **Instrument (`rl/train.py`, ~15 lines, both loops, always-on):** `time/collect_sec`,
  `time/update_sec`, `time/eval_sec` alongside `time/steps_per_sec`. Maintainer answered the two
  open questions: always-on (a flag is speculative configurability at microseconds of overhead)
  and additive metric names are fine (the locked-names rule prohibits renames, not additions) —
  the three names are now IN the CLAUDE.md invariant list. **Design correction vs the handoff's
  spec:** it called for "three `perf_counter` pairs per rollout (NOT per step)", but the loop is
  per-step with `agent.update()` called every step and returning truthy metrics only when the
  rollout drains, so the timers are per-step accumulators FLUSHED at the rollout boundary (vector
  path) or the episode boundary (scalar path, which has no rollout). Same output, ~4 extra
  `perf_counter` calls per step against a ~13 ms vector step. `tests/test_loop_timers.py` pins
  both paths; the load-bearing assertion is `collect + update <= wall clock`, which is what
  catches a missing accumulator reset. 288 tests green.
  **THE READ, first numbers, and it is not what this morning inferred.** Six live 12M lanes,
  measured at both 3-wide and 6-wide, every lane agreeing to within 0.5 pt:
  **collect (act + env.step) 94.5-95.0% of the loop, update (PPO epochs) 5.0-5.5%, eval
  negligible** (6.7-7.0 s vs 0.37-0.40 s per rollout at 6-wide; 5.52 s vs 0.32 s at 3-wide).
  This morning's entry concluded the loop is "update-and-encode bound"; **the update half is
  wrong — a GPU at [512,512] can buy at most ~5% end-to-end.** It also RECONCILES the 29%-
  collection-to-3.7%-end-to-end puzzle rather than contradicting it: `showdown_throughput.py`
  measures server-side decisions/s, which must therefore be a small slice of the collect phase,
  with our own Python encode + action inference the bulk of it. **Everything worth optimizing is
  inside collect**, which bundles server wait, `embed_battle`, and inference — so the handoff's
  step 2 (decompose collect Showdown-side by re-running measurement (a) at the real 611-dim
  encoder) is now TRIGGERED, and waits only on the lanes finishing, since it would load the same
  server.
  **POKE-ENV USERNAME COLLISION — an arm-killing constraint on every future concurrent launch.**
  P6's first launch put both arms on seeds 0,1,2. All three annealed lanes died ~30 s in.
  Mechanism: `rl/common/seeding.py` seeds the GLOBAL `random` module with `cfg.seed`, and
  poke-env derives each player's username from that same RNG
  (`ps_client/account_configuration.py`: `random.choices` over a 5-char space), so **two
  concurrent lanes at the same seed request identical Showdown usernames.** The flat arm claimed
  them first; the annealed lanes got `|nametaken|`, which surfaces as poke-env's badly misleading
  `TimeoutError: Agent is not challenging` at the first `reset` — the message names the challenge
  handshake and says nothing about login. Every prior multi-lane run in this repo used distinct
  seeds across ALL lanes, which is why nothing caught it. **Standing rule: concurrent lanes must
  carry distinct `--seed` values, full stop — including across arms of the same experiment.**
  Fix taken: annealed arm relaunched on seeds 3,4,5, recorded in the config. Cost to the read —
  the arms are UNPAIRED in seed value; the PRIMARY is a pooled 3000-vs-3000 proportion test that
  never assumed pairing, so it stands, but per-seed cross-arm comparison is meaningless and the
  known s0-weak-seed pattern cannot be matched out.
  **A SECOND vacuous-assertion lesson, on top of this morning's.** The launcher asserted run-dir
  existence at +180 s and reported success over three dead lanes: `_write_run_metadata` writes
  `config.yaml`/`meta.yaml`/`wandb/` BEFORE the first `reset`, so the directory exists for a lane
  that never trains. The replacement checks battle progress and greps for
  `nametaken|to be logged in|not challenging`. Related: a watchdog written with unquoted `$PIDS`
  loops declared all six lanes dead on its first tick — **zsh does not word-split unquoted
  variables**, so the pid loop ran once over the whole string and every `kill -0` failed. Any
  multi-item shell loop in this repo must run under `bash`, not the default zsh.
  **P6 LAUNCHED (pre-registered in `configs/showdown_r512_12m.yaml`, committed before launch):**
  flat vs annealed at 12M on the r512 recipe, 3 seeds per arm, 6-wide, both arms from scratch
  (an annealed checkpoint cannot be warm-extended, and `runs/showdown_scratch12m_s*` is not a
  control — it predates P5 at `rollout_steps: 128`). PRIMARY: pooled 3-seed finals, 1000
  battles/seed, ties as non-wins, credited iff delta >= +0.025 AND >= 2*se_diff. Throughput
  524-548 steps/s per lane, inside the R0 gate.
  **P6 RESULT (2026-08-05 ~02:30): 6/6 lanes completed the full 12M — a clean sweep after this
  session's collision killed an arm and last week's W=6 probe lost a lane to SIGSEGV. R0 gates
  PASSED on all six** (entropy 0.244-0.289; ties 1.0-2.4%; steps/s 501-506, the tightest spread
  yet recorded). **PRIMARY: annealed-12M pooled 1382/3000 = 0.4607 (per seed 0.449/0.451/0.482)
  vs flat-12M 1299/3000 = 0.4330 (0.425/0.424/0.450); delta +0.0277, se_diff 0.0128, z = +2.16,
  2*se_diff = 0.0257. THE ANNEAL IS CREDITED AT 12M — but narrowly**, clearing +0.025 by 0.0027
  and 2*se_diff by 0.0020, where P5b cleared its line by 2x. **The direction replicates; the
  magnitude does not** (+0.051 at 6M vs +0.028 at 12M), which is the expected shape if annealing
  mostly buys a cleaner endpoint rather than a better trajectory.
  SECONDARY: flat 6M -> 12M is **+0.0407** (0.3923 -> 0.4330) — doubling the budget on the flat
  recipe buys about as much as the anneal does, which cuts against the archive prior (VGC-Bench
  0.48 at 5M, pokejax ~0.55 at ~378M) that step count buys almost nothing at this scale.
  Annealed 6M -> 12M is +0.0174, confounded exactly as pre-registered (a 12M anneal is a SHALLOWER
  schedule, not merely a longer one).
  **THE CONSEQUENCE THAT OUTRANKS THE VERDICT: 0.4607 is the first RL result in this project to
  clear the BC clone (0.453), and it sits only 0.028 below the measured SH-vs-SH mirror baseline
  of 0.489.** P4's framing — the plateau is training-side, RL sits below a representable
  supervised policy — has been closed by training-side work, as P4 predicted. It also **undercuts
  DESIGN_P7's premise**: P7a's BC-from-SH warm start was designed to exploit a clone-vs-RL gap
  that no longer exists, and warm-starting from 0.453 would now start BEHIND the RL policy.
  Recorded in DESIGN_P7.md as revision 4; P7b (faint shaping) and P7c (distributional value) are
  unaffected, and §10 (the 109k-replay human corpus) is the only remaining proposal whose ceiling
  is not 0.489.
  MECHANISM (recorded in-flight): `approx_kl` HALVED on the annealed arm across the run
  (0.0044 at 2-4M -> 0.0027 at 6-8M) while the flat arm held flat (0.0058 -> 0.0057) — the
  schedule is demonstrably engaged. **Entropy did NOT separate** (0.284 flat vs 0.275 annealed at
  6-8M), contrary to P5b's pre-registration, which expected a frozen-entropy signature as the
  tell. The anneal shrinks step size, not the action distribution. Loop split held at
  **94.8% collect / 5.2% update** on all six lanes for the whole 12M.
  Artifacts: `runs/showdown_r512_{12m_s0,12m_s1,12m_s2,lra12m_s3,lra12m_s4,lra12m_s5}`
  (~425-431k history rows each); finals JSON under the session tmp dir's `finals_shim/`.
  **This is the last experiment run in this repo** — the capstone moves to `pokemon-showdown-rl`.

- 2026-08-04 (latest: ACTION SPACE CLOSED as a lever; ps-ppo read at the source and it corrects
  two claims this repo had recorded; the encoder fix we derived turns out to be what ps-ppo
  already encodes) — **Full detail is in `prior_work/README.md` (ps-ppo entry, rewritten from the
  code); this entry records only what changed and why.** The maintainer opened the action-space
  question after the briefing's note that our 10-way positional space was "a fork taken
  implicitly." Confirmed it was never chosen: `rl/envs/showdown.py:432` is
  `self.action_space = self._env.action_space` — poke-env's `SinglesEnv` wholesale, `Discrete(10)`
  = 6 switch + 4 move (pinned, `tests/test_showdown_env.py:79`). But the encoder was deliberately
  slot-ALIGNED to it (`showdown.py:187`), which makes it a described-action space, not a naive one.
  **CLOSED on external evidence: ps-ppo 14 (4 move + 6 switch + 4 tera-move) and Metamon 9 (4 move
  + 5 switch, "the meaning of each action index varies by turn") are BOTH positional, and they are
  the two strongest pure policies. Wang's 494-way identity space is the outlier, and his headline
  needed MCTS.** Redesign would invalidate every in-repo comparison and buy Wang's benefit only at
  Wang's data volume. Not the lever. Metamon also drops the always-illegal self-switch slot (5 vs
  our 6) — cosmetic, the mask already handles it.
  **THE ENCODER IS THE LIVE QUESTION, and two independent routes reached the same place.** Reading
  `poke_env/player/baselines.py` against our `_fill_move` (MOVE_DIM 23) found our observation is
  approximately the sufficient statistic for `SimpleHeuristicsPlayer` AND NOT MUCH MORE — which
  makes the plateau legible, since RL sits at 0.443 and the BC clone at 0.453, both at the 0.5
  mirror-match line. Missing vs SH's own inputs: **STAB** (`1.5 if m.type in active.types`,
  `baselines.py:326` — we precompute the HARDER cross-block term, `move.type.damage_multiplier(foe)`,
  and omit the easy one, which lives behind a dynamic "which of 6 team slots is active" lookup),
  `move.boosts`/`target=="self"` (the setup rule), `expected_hits`, and `active.stats` (vs the
  `base_stats` we encode). Hazard branches are dead in Gen 1. **Then the ps-ppo code turned out to
  encode exactly these** — `stab_flag`, `expected_hits`, `self_boost_sum` (same `target` gate),
  plus `status_prob` (secondary-effect chance), which our audit had filed under "beating SH needs
  this." Inverse design worth noting: **they precompute NO type effectiveness at all** (zero hits
  for `damage_multiplier`/`type_chart` in their tree) and let attention learn the chart, while we
  precompute it and skip STAB.
  **CORRECTIONS TO THE RECORD (both were recorded here before, both are now stronger/wrong).**
  (1) **The ps-ppo ">85% vs SimpleHeuristicsPlayer" figure must not be used at all.** 2026-08-03
  recorded it as "unreproducible (no eval script at HEAD)"; the truth is that **no script in all 49
  commits ever evaluated against SH** — `eval.py` (deleted at `7fb522c`) ladders against HUMANS via
  `ShowdownServerConfiguration` + `player.ladder(n)`. It is not comparable to any win rate here,
  and it was wrongly quoted beside our 0.443 earlier in this session. (2) **Param count is
  14,490,657, verified by instantiating the model** — our 14.5M was right and the author's "~55M"
  on Reddit is wrong (embeddings are only 141k, so the obvious reconciliation fails too).
  (3) The per-zone LR multipliers extracted 2026-08-03 as transferable (backbone 0.5×, value 2×)
  are **dead code at HEAD**: the multiplier dict is keyed on `imitation/warmup/ppo/...` but the
  default mode is `"ppo_with_jepa"`, so `.get(..., (1.0,1.0,1.0))` returns neutral.
  **HEAD IS NOT THE PUBLISHED SYSTEM** — undisclosed JEPA auxiliary objective (1.58M params),
  dynamic GAE lambda, and a KV-cache/`obs_transitions.py` temporal path that contradicts the
  author's own "single snapshot, no non-Markovian modelling" statement. Anything cited from that
  README or Reddit thread describes an earlier system. **Both remaining "MLP can't do it" claims
  (Wang-replication ~1100 Elo; "an MLP, even with dedicated subnets, was unable to perfectly mimic
  the bot") have NO code trace — no MLP exists anywhere in the history.** Anecdotes, and precisely
  why the BC-clone diagnostic is worth running ourselves: it separates "MLP cannot compose" from
  "MLP cannot represent even when handed the composition."
  **Operational:** full ps-ppo clone now lives at `/Users/nickgreenquist/Documents/Projects/ps-ppo`
  (machine-local, never committed); pointers added to STATUS "Operational" and a new
  `prior_work/README.md` "Local code checkouts" section so a session finds it unprompted. The
  Reddit thread is archived as a PDF in `prior_work/` since reddit.com is unfetchable from the
  sandbox. No `rl/` source changed; 288 tests green; P6 unaffected and healthy throughout.

- 2026-07-25 (capstone decision) — **Capstone decided: Pokémon Showdown Gen 1 singles (battle phase
  only) via poke-env + a local Node.js Showdown server, starting format `gen1randombattle`; hero
  algorithm PPO + self-play.** Milestone ladder (each independently shippable): beat
  MaxBasePowerPlayer → beat SimpleHeuristicsPlayer → self-play with a historical-checkpoint opponent
  pool → optional live-ladder Elo. Headline: win rate vs SimpleHeuristicsPlayer over ≥1000 battles,
  multi-seed (Elo is a flourish, not the metric). Documented fallback if self-play stalls: Procgen
  generalization study (train/test level gap). CLAUDE.md rule flipped from "undecided — no capstone
  scaffolding" to "decided — capstone-specific code deferred until Phase 3 completes" (no poke-env,
  no battle logic, no Pokémon encoders during Phases 2–3; env-agnostic harness contracts the
  capstone needs may land earlier). Immediate consequence, landing next: the action-masking harness
  contract — Showdown's legal actions change every turn (fainted Pokémon, PP depletion, forced
  switches) — all-True default, provable no-op on the spine envs.

---

# Appendix A — predecessor README, "Results — Phase 5" (verbatim @5d6a604)

## Results — Phase 5: PPO + self-play on Pokémon Showdown (milestones 1–3)

![Milestone 3 on Pokémon Showdown: training curves for the fixed-bot run and three from-scratch self-play seeds converging to ~0.4 vs SimpleHeuristics, against the 0.5 bar, the extrapolated 0.42 asymptote and the BC-clone band; right panel, locked-protocol finals for every arm with 95% CIs](assets/showdown_milestone3.png)

*[Caveat added 2026-08-29, maintainer-approved — the one permitted edit to
this frozen file: the figure above is a PREDECESSOR-ERA snapshot — 611-dim
encoder, ~0.4 vs SH. Production is the 828-dim encoder at 0.71825; do not
read these curves as the current agent.]*

The capstone is live: the same `PPOAgent`, rollout buffer and GAE that ran
MinAtar and MuJoCo now play Pokémon Showdown Gen 1 random battles over a
websocket to a local Node.js server, through a 611-dimensional
observable-state encoder written for this phase — revealed Pokémon and
revealed moves only, the information set a player at the table actually has.
Legal actions change every turn, which is what the harness-wide
action-masking contract was built for back in Phase 2.

**The headline: milestone 2's bar is not met, and the phase's result so far
is knowing why.** Every training distribution tried — fixed-bot,
warm-started self-play, from-scratch self-play — converges on the same ~0.4
win rate against poke-env's `SimpleHeuristicsPlayer` (SH). A behavioral
clone of that same bot, trained by supervised learning through the identical
encoder, trunk and masking, plays **0.453**: the architecture demonstrably
holds a better policy and supervised SGD demonstrably finds it, so the
plateau is training-side — signal, visited states, or optimization, not
representation. The caveat travels with the claim: nothing yet shows PPO can
*reach* that policy under terminal-only reward. This section reports where
the ceiling is not.

**Protocol, fixed before the runs.** The milestone ladder — beat
`MaxBasePowerPlayer` (always clicks the highest-base-power move), then beat
SH — was set on 2026-07-25, before the first Showdown run; "beat" means
above 0.5, and that bar has not moved. Headline evals use the **final**
checkpoint (never best — selection bias), 1,000 fresh battles per seed at
eval seeds disjoint from training's, deterministic policy, ties counted as
non-wins. Throughout this section ± is one standard error of a battle-level
proportion unless labelled otherwise; "pooled" is wins/total over all seeds'
battles and carries no seed variance, so seed spread is quoted where a claim
lives at the seed level. The milestone-1 headline is single-seed; every
other headline number is 3-seed (the fixed-bot 12M cell was replicated to
3 seeds on 2026-08-02 under a pre-registered read).

| Milestone | Result | Status |
|---|---|---|
| 1 — beat `MaxBasePowerPlayer` | **0.663 ± 0.029** (95% CI, n=1 seed) at 2M steps | **passed** |
| 2 — beat `SimpleHeuristicsPlayer` (0.5 bar) | best **0.417 ± 0.009** pooled, 3 seeds (0.408/0.411/0.432, spread 0.024; 12M, [512,512]); a 6M continuation reached 0.432 pooled but reads as specialization (below) | **not passed** |
| 3 — self-play with a historical-checkpoint opponent pool | from-scratch self-play **learns**: 0.380 pooled vs SH; 0.484 head-to-head vs the equal-budget fixed-bot policy (a resolvable deficit, z ≈ −2.5) | **complete** — no win-rate bar; the deliverables were the loop and its pre-registered reads |

### Milestone 2: four levers to ~0.42

A search path, not four confirmatory tests — each lever was chosen after
reading the previous one, two of the four rows are single-seed, and the
verdicts are campaign decisions ("was this worth more budget?"), not effect
estimates:

| Lever | Result | Verdict |
|---|---|---|
| Real encoder (10 → 611 dims) | ~0.26 (500-battle probe of the milestone-1 policy) → 0.292 ± 0.014 at 2M; the cross-protocol delta is not itself resolvable (z ≈ 1.2) | credited a priori — the placeholder encoder carried no HP/status/boost information at all, and the curve stopped plateauing |
| Budget (2M → 6M at [64,64]) | 0.292 → 0.358 ± 0.015, flat from ~2.5M on at this width | credited, exhausted |
| Capacity ([64,64] → [512,512]) | matched-budget 4–6M in-training bands 0.346 vs 0.316, and the shape: [64,64] flat from 2.5M, [512,512] still climbing at 12M (s0 final 0.408; later replicated ×3 — pooled 0.417 ± 0.009) | credited — biggest single lever; the 0.358 → 0.408 endpoint pairing confounds capacity with budget, so the attribution rests on the band and the shape |
| Distribution (70/20/10 SH/max-power/random mixture, 3 seeds, 6M) | pre-registered in-training read fired "at/below"; locked-eval delta +0.032 ± 0.017 (z ≈ 1.9, against a single-seed control likely sitting in an eval dip) | not credited — at most a nudge, nowhere near the ~0.1 gap to the bar |

The [512,512] curve's per-2M return gains decay geometrically
(+0.153 / +0.103 / +0.061 / +0.027 / +0.016), extrapolating to ≈ 0.42 win
rate vs SH — a projection from five points, not a measurement, but it is
what ended the fixed-bot campaign: more budget in this configuration was not
projected to reach 0.5, and self-play moved up the queue.

### Milestone 3: three arms, one plateau — and the clone that locates it

Self-play here is the Phase 4 machinery transplanted whole: a 20-snapshot
opponent pool, strided retention with the step-0 snapshot as anchor, 80/20
latest/historical draws, driving the opposing seat over the websocket. Every
read below was pre-registered before launch. (In-training evals — "rungs" —
are 100 episodes each, se ≈ 0.05; no claim here rests on a single rung.)

- **Warm-started self-play, with a matched control (6M continuation each,
  3 seeds).** Initialize both arms from the 0.408 fixed-bot policy; one
  continues in self-play, the control continues vs the fixed bot. Self-play
  produced no strength change any instrument could resolve: frozen-checkpoint
  cross-play vs its own parent 0.5050 ± 0.0065 (n=6000 — within ±1.3
  points); the windowed anchor (n ≈ 400/window, se 0.025) inside 0.465–0.551
  in every window of every seed; and the highest-n instrument, pooled
  training return, reads +0.0025 ± 0.0013 per window (z = 1.9) — edge of
  resolution, not zero. At the recipe level the 3-seed design resolves only
  ±0.14, so the null is about this initialization and budget, not the recipe
  class. Huang & Lee's published 15.4% self-play forgetting did not fire.
  The control gained +0.024 over its parent on the eval bot (0.432 pooled —
  the campaign's best number, though a single-endpoint read at z ≈ 1.3 with
  no measurable in-run improvement) yet ties both the self-play arm (0.501,
  n=6000) and its own parent (0.510) head-to-head: the gain reads as
  specialization to the bot it trained against, not strength.
- **From-scratch self-play (12M, 3 seeds) — the ceiling arm.** No
  warm-start, no fixed-bot games, the eval bot never seen in training, at
  ~6% of the only published from-scratch budget in this setting. The
  pre-registered expectation was 0.20–0.35; it landed above it — the
  forecast was low. Finals: **0.380 ± 0.009** pooled (per-seed
  0.369/0.398/0.373, spread 0.029); cumulative win rate against its own
  random init 0.949–0.955. Head-to-head it sits at **0.484 ± 0.007** against
  the equal-budget fixed-bot policy — a small but resolvable deficit
  (z ≈ −2.5), about 1.6 points below parity — and 0.474 ± 0.006 against the
  18M-step warm-started arm (z ≈ −4). Real deficits; what makes them worth
  reporting is that this policy never saw SH and gives up only that much to
  policies trained on it.
- **The plateau.** Two independent training regimes land in a 0.38–0.41
  band (from-scratch 0.380 ± 0.009; fixed-bot 12M pooled 0.417 ± 0.009 over
  3 seeds, spread 0.024), with
  from-scratch rungs flattening into 0.36–0.40 after ~8M, consistent with
  the ≈ 0.42 projection. (Warm-started self-play finishing at 0.408 is not
  independent evidence — a null returns its own initialization.)

**The cloning diagnostic.** Which side of the policy does the plateau live
on — representation or training? First, an audit of SH's source showed its
realized Gen 1 policy is a near-closed-form function of features the
encoder already carries (the one non-encoded factor is exposed on 1.8% of
move rows). Then the wedge: clone SH by supervised learning through the
exact capstone actor — same 611-dim encoder, same [512,512] trunk, same
masking — on 40k SH-vs-SH battles, and evaluate it through the same
1,000-battle harness. Two disclosed differences from the RL protocol: the
clone reports its best-validation checkpoint, not final, and the collection
instrument differs from the eval wrapper — the pre-registered pass margin
was set to absorb both. (The first was then measured to be a non-issue:
final-checkpoint re-evals of all six clones match their best-checkpoint
numbers within noise — pooled deltas +0.013 and −0.011 on the two
batteries, every per-seed |z| < 1.5.) The supervised fit gate was **not** met: best
validation agreement 0.899–0.905 across three fits against a ≥ 0.93 gate,
with the fit data-bound, not capacity-bound — agreement still climbing per
data doubling toward the audit's predicted ~0.97 — so the pre-registered
capacity probe was skipped as uninterpretable under a binding data
constraint (a disclosed deviation; the agreement read closed as
partial-trajectory-consistent, not verified). The win-rate read passed
twice: **0.453** pooled (battery of record; three fit seeds on one dataset,
so the interval is battle-level) and 0.465 on an earlier half-data
generation (0.96σ apart). Against SH's own mirror baseline — the recorder's
win rate over the collection battles, 0.489/0.486; ties-as-non-wins is why
a mirror sits below 0.5 — the clone pays a real ~0.03 cloning tax (≈ 4σ):
it is a demonstrably *imperfect* clone, and what is demonstrated is 0.453,
not 0.49. That is enough: 0.453 sits **+0.036 above the 12M fixed-bot
pooled final** (0.417 ± 0.009, 3 seeds; z ≈ 2.8, 95% CI +0.011 to +0.061)
— the pre-registered seed replication tightened the RL side from one seed
to three and the wedge sharpened rather than shrank, and even the best
fixed-bot seed (0.432) sits below the clone. Capacity was milestone 2's
biggest lever and the obvious next dose — a wider trunk — was never run;
the clone is why: this trunk already represents a 0.453 policy, so capacity
is not what binds.

Findings worth the compute:

- **Self-play's value depends on where you start — probably.** Warm-started
  on a fixed-bot policy, 6M steps of pool self-play changed nothing any
  instrument resolved; from scratch, the same recipe learned real play. But
  the two arms differ in initialization, pool composition and budget at
  once, so "the mirror opponent had nothing left to teach the warm-started
  policy" is the leading hypothesis, not a measured attribution.
- **Generalist vs specialist, measured from both sides.** The fixed-bot
  control posted the campaign's best anchor number while gaining nothing
  head-to-head against equal-budget policies; from-scratch self-play never
  saw the anchor bot and nearly matches the specialist on its own turf.
  Phase 4's visited-state-distribution lesson, recurring at capstone scale:
  what a policy is strong against is what it trained against.
- **The Phase 4 entropy collapse did not reproduce — as predicted.**
  Tesauro's dice argument transfers: server-rolled random teams inject the
  exploration Connect 4's deterministic board could not. Late entropy
  medians ≈ 0.40–0.42 on every from-scratch seed; the pre-registered
  collapse trigger never engaged; mirror self-play win rate held
  0.505–0.506 all run (the ~0.5 equilibrium is the health check, not a
  result).
- **The eval bot is weaker than its source intends — everywhere.** The
  audit found SH's setup-move branch is dead code upstream: poke-env 0.15.0
  compares an int enum to a string ("`move.target == "self"`", always
  False), so SimpleHeuristicsPlayer is a pure damage-maximizer plus
  matchup-switcher in every 0.15.0 deployment, not just ours. Found by
  auditing the baseline before cloning it. Internal comparability is
  unaffected — every number here faced the same SH — and it's worth an
  upstream report.
- **"Best rung ≠ final" recurs on Showdown.** One from-scratch seed of
  three regressed late (per-2M eval means 0.396 → 0.365 over the last 2M),
  and it is the weak seed in cross-play against the warm-started arm
  (0.434). Finals still report the final checkpoint per the locked
  protocol; the regression is disclosed rather than selected away.

Caveats stated rather than buried:

- **Milestone 2 is not passed.** The bar was set on 2026-07-25 and has not
  moved. Best measured is 0.417 ± 0.009 pooled fixed-bot (best seed 0.432) /
  0.432 (the 18M continuation, but
  specialization per the head-to-head).
- **The from-scratch result is a 6%-budget result.** Huang & Lee's
  from-scratch PPO self-play used ~192M learner transitions on Gen 7 random
  battles; this ran 12M. "Learns from scratch" is demonstrated; where it
  plateaus at 16× the budget is not — untested, not ruled out.
- **The clone result is one-directional.** Representable and
  supervised-learnable does not mean PPO-reachable under terminal-only
  reward. And its fit missed the pre-registered agreement gate (0.90 vs
  0.93) with the capacity probe skipped, as disclosed above.
- **The published anchors are context, not baselines.** Huang & Lee reached
  1677 Glicko-1 on the Gen 7 random-battle ladder; Metamon reaches
  human-level Gen 1 OU with offline RL and transformers. Neither number is
  commensurable with a win rate against a scripted bot, and mixing such
  protocols is the error this repo's Phase 2 taught.
- **A seat asymmetry exists in cross-play:** at equal parameters the
  deterministic eval seat beats the sampling seat by +0.018 ± 0.007. Every
  head-to-head above averages both orientations, which cancels it; any
  single-orientation number in this domain is biased by ~2 points.

The phase so far is ~140M environment steps across ~27 runs — about 27
hours of laptop-CPU wall clock, at most three concurrent runs against one
local Showdown server, no GPU. Every run directory is self-describing
(resolved config, git SHA, W&B history, checkpoints); the figure is
`scripts/make_showdown_figure.py`, evals are
`scripts/eval_checkpoint.py`.

**Where this goes next.** Fixed-bot budget is spent (measured flat at
[64,64], projected short at [512,512]) and every current-recipe self-play
arm converges to the same place, so the next win rate costs a change of
recipe, not more compute. Both queued mechanism reads are now in.
The team-luck decomposition prices the observable draw — own six species
plus the opponent's lead — at ~4% of per-battle outcome variance (real, but
the draw does not decide battles at the species level). The rollout-length
probe was credited: quadrupling the PPO rollout at fixed budget — the
config's one true signal-to-noise knob — lifted the 6M win rate from 0.355
to 0.392 (3 seeds each side, pre-registered read, z = 3.0), reaching at
half the budget roughly what the base recipe took 12M to reach. Its
pre-registered follow-up — linearly annealing the learning rate to zero
over the budget on top of that recipe, the one lever prior work offered a
controlled ablation for — was credited too: pooled 6M finals moved 0.392
to 0.443 ± 0.009 (3 seeds × 1000 battles), the first result on this board
above the ~0.42 plateau every earlier arm converged to, and within noise
of the BC clone's 0.453. The anneal joins the recipe for any 12M
extension, which must run from scratch — an annealed checkpoint cannot be
warm-extended.

That extension has now run, from scratch, both arms: at 12M the annealed
recipe reaches **0.461** pooled (3 seeds × 1000 battles, per seed
0.449/0.451/0.482) against **0.433** for the same recipe at flat learning
rate. The anneal is credited again — delta +0.028, z = 2.16 — but it clears
the pre-registered line by 0.003 where the 6M read cleared it by double.
The direction replicates; the magnitude does not, which is the shape you
would expect if annealing mostly buys a cleaner endpoint rather than a
better trajectory. Doubling the budget at flat learning rate bought +0.041
on its own, about as much as the schedule did.

The mechanism read is the part worth keeping: across the run the annealed
arm halved its per-update policy movement (`approx_kl` 0.0044 → 0.0027)
while the flat arm did not move at all — the schedule is demonstrably
engaged — yet **policy entropy did not separate between the arms**, which
is what the 6M pre-registration had expected as its tell. The anneal
shrinks step size, not the action distribution.

At 0.461, PPO has finally passed the behavioral clone (0.453) that had sat
above every RL policy on this board, and stands 0.028 short of the measured
SimpleHeuristics mirror baseline of 0.489 — the ceiling any imitator of
that bot is bounded by. The plateau this project spent three milestones
characterising was training-side, exactly as the cloning diagnostic
predicted, and training-side work closed it. What remains above 0.489
cannot come from imitating this teacher, which is where the capstone goes
next — in its own repository, and without the from-scratch constraint that
this one was built to honour.


---

# Appendix B — predecessor PLAN.md, Phase 5 spec (verbatim @5d6a604)

## Phase 5 — capstone (decided 2026-07-25: Pokémon Showdown Gen 1)

**Env:** Pokémon Showdown Gen 1 singles, battle phase only (no teambuilding) — poke-env driving a
local Node.js Showdown server, starting format `gen1randombattle`. **Hero algorithm:** the Phase 2
PPO with self-play. Legal actions change every turn (fainted Pokémon can't be switched to, moves run
out of PP, forced switches), which is why the action-masking contract lives in the harness now
(landed mid-Phase 2, env-agnostic, all-True default) while everything Pokémon-specific stays
deferred until Phase 4 completes: no poke-env dependency, no battle logic, no Pokémon observation
encoders during Phases 2–4.

**API corrections from the Phase 4 review (poke-env 0.15.0 source, 2026-07-26) — the plan named a
dead API.** `Gen*EnvSinglePlayer` was **removed in 0.8.4** (2025-04-20) along with `EnvPlayer` and
`OpenAIGymEnv`. The live surface is **`SinglesEnv`**: subclass, implement `calc_reward(battle)` and
`embed_battle(battle)`, assign `observation_spaces`. Three further shape facts, each a bounded known
cost rather than a surprise: (1) **the opponent does not live inside poke-env's env** — `PokeEnv` is
a PettingZoo `ParallelEnv` with two server-connected `_EnvPlayer`s and no `opponent` parameter, and
the opponent enters one level up via `SingleAgentWrapper(env, opponent)`; what transfers from Phase
4 is the learner-facing contract (`(obs, float, terminated, truncated, info)`, an opponent held as a
plain policy object, a `calc_reward(state)` hook), not the opponent's *location*. (2) **poke-env
puts the action mask in the OBSERVATION, not `info`** — it rewrites the obs space to
`Dict({"observation", "action_mask"})`, as PettingZoo classic does; our harness contract matches
Shimmy/OpenSpiel instead, so Phase 5 needs one adapter wrapper lifting `obs["action_mask"]` into
`info`. (3) **`truncated` is load-bearing here where it is dead on Connect 4** — `calc_term_trunc`
sets `terminated=True` only for a decisive wipe, while **forfeits, ties and timer losses all return
`truncated=True`**, and `reset`/`close` inject `ForfeitBattleOrder()`. Reward shape transfers
cleanly (`calc_reward(self, battle) -> float`, no sign-flip machinery — egocentricity is a property
of the state handed to each seat). Vectorization does not: poke-env is one battle per env instance
and scales via `SubprocVecEnv` over `SingleAgentWrapper` factories.

**Direct precedent (found 2026-07-25):** Huang & Lee, *"A Self-Play Policy Optimization Approach to
Battling Pokémon"* (IEEE CoG 2019) is this exact architecture — PPO + self-play on Pokémon Showdown,
actor-critic with GAE and an entropy bonus, and masked softmax over illegal actions. It reached 1677
Glicko-1 on the ladder and beat `pmariglia` (the tree-search SOTA bot) 612–388, over 3.84M self-play
matches (~6 days, ~$91 on GCP). **Three corrections from the Phase 4 review, all of which weaken the
original reading:** (a) they **renormalize after the softmax** (`π_i = s_i π'_i / (sᵀπ')`) where we
mask *logits* with a finite sentinel — same contract, different gradient path, so "our masking
contract, independently arrived at" overstates it; (b) "they needed dense reward shaping" is an
**inference** — no ablation is reported, they say only "to speed up learning", and Generals.io
(arXiv:2606.23348) argues shaping is a throughput artifact ("at low throughput few games finish, so
the terminal signal alone is too sparse") and finds sparse reward converges *more* cleanly; (c)
**their own §V-C reports catastrophic forgetting**: RL-meta, fine-tuned from RL-rb for only ~10%
additional training on a narrowed opponent distribution, wins **77/500 (15.4%)** against the model
it came from, in the format it was originally trained on. That is published, quantitative forgetting
in this domain, and it substantially weakens "naive self-play was sufficient" — naive self-play was
sufficient *to reach 1677 against ladder humans*, which is the defensible claim. Their
feedforward-with-LSTM-as-future-work finding stands, so recurrence remains an option rather than a
precondition.

**A stronger, more recent anchor: Metamon** (Grigsby et al., *Human-Level Competitive Pokémon via
Scalable Offline RL with Transformers*, RLJ 2025, arXiv:2504.04395). SynRL-V2 reaches **Gen1OU GXE
79.9%, Glicko-1 1761 ± 35 over 613 human ladder battles**, peak global rank #31 in Gen1OU. Protocols
differ from Huang & Lee's (different tier, different era, GXE vs raw Glicko) and **must not be
mixed**. Two findings directly load-bearing for us: they **do not mask actions** ("if the agent
selects an invalid action, it is replaced by a random valid action") and name invalid-action
selection from PP stalls as "their most noticeable flaw" — direct evidence our masking contract is
right; and their self-play arm overfit to its own checkpoints (§5.3, quoted in Phase 4's
pre-registered expectations), fixed by deliberate opponent and team diversification.

**Milestone ladder (each independently shippable):** beat `MaxBasePowerPlayer` → beat
`SimpleHeuristicsPlayer` → self-play with a historical-checkpoint opponent pool → optional: live
Showdown ladder Elo.

**Headline metric:** win rate vs `SimpleHeuristicsPlayer` over ≥1000 battles, multiple seeds. Ladder
Elo is an optional flourish, not the metric. Budget the eval variance off Huang & Lee's **1000
matches per matchup**, not off Phase 4's 400 — theirs is driven by team randomization, which
`gen1randombattle` has and Connect 4 does not.

**Fallback if self-play stalls:** Procgen generalization study (train/test level gap) — the previous
lean, kept ready.

**Scope decisions from the prior-work dig (2026-08-03, maintainer-ratified; evidence in the
2026-08-03 session-log entries and `prior_work/`):**

- **MCTS is an OPEN follow-up phase — deferred, not ruled out.** Inference-time-only policy
  improvement in Wang's pattern: training is untouched, the trained policy stays the artifact, and
  search bolts on at evaluation — so it composes with every training lever and no current work
  forecloses it. The Phase-4-era premise "tree search needs a forward model the capstone will not
  have" is REVISED: the forward model exists upstream in our own vendored server —
  `State.serializeBattle`/`deserializeBattle` (`showdown/sim/state.ts:61,84`) and
  `Battle.toJSON`/`fromJSON`/`resetRNG(null)`/`restart()`/`undoChoice`
  (`showdown/sim/battle.ts:318,322,360,1968,3029`) — and Wang's fork adds only two stream commands
  plus constrained team regeneration (diffs: `prior_work/wang_fork_diffs.md`). Gen 1 shrinks the
  determinization further (no items/abilities/Hidden-Power typing; volatile constraints reduce to
  Disable, lock states, Transform; port target `showdown/data/random-battles/gen1/teams.ts`).
  Deferred because the real cost is the search stack (Wang: 20 workers, 1000–2000 rollouts/move,
  ~10 s/move — evaluation ~100× slower) and search's measured edge is smallest in Gen 1 (PokéAgent
  2025: MCTS #8 in Gen1OU where pure policies took #1/#2). Standing consequence now: keep the value
  head healthy — search truncates rollouts at leaves with V.
- **"Pure self-play" is retired as an identity constraint.** The capstone agent may use teachers,
  shaping, and offline data. Concretely in scope for the BC-warm-start design session: BC init
  from `SimpleHeuristicsPlayer` (VGC-Bench: +25–30 pts vs SH at a matched 5M budget; ps-ppo used
  BC-fit-to-the-heuristic as an architecture screen), faint-based reward shaping (ps-ppo: ±0.1
  against the ±1 terminal; potential-based if policy invariance is wanted; their
  post-hoc-alignment off-by-one is the known trap), and the P5b LR-anneal verdict — CREDITED
  2026-08-04 (0.392 → 0.443 pooled at 6M; the anneal joins the recipe; annealed ckpts cannot be
  warm-extended, so any 12M arm is from-scratch). Design the
  recipe as a pre-registered stack, not one lever at a time.
- **Speed before the next science chapter (directed 2026-08-03).** After the P5b read, a
  throughput session precedes the BC-warm-start design session. The rationale is meta-level
  compounding: cheaper experiments raise hypothesis turnover — more levers tried per week, each
  verdict steering the next — which compounds in a way raw steps/s cannot (that only tops out at
  the machine ceiling). Budget was itself a credited lever, so cheaper steps also discount every
  later pre-registration. Measured basis
  (2026-07-29 measurement (c)): one shared Showdown server peaks at TWO workers and declines
  (the Node process saturates; the live 3-wide campaign uses ~3 of 14 cores, per-run throughput
  685 → 587), while one-server-per-worker scaled to ~7.5k decisions/s at W = 4–8. Work items:
  (1) a server-port knob in the env seam + one Showdown server per lane — goal: restore
  ≥685 steps/s per run at 3-wide and measure lane scaling W = 3–6 through the FULL training loop
  (the (c) curve was collection-only); (2) go/no-go on the deferred decision-lockstep facade,
  gated on the already-named measurement (e) — the facade is the lever for long SINGLE runs
  (12M+/Wang-scale), lane count is the lever for probe science; (3) long-run hygiene:
  **RESOLVED 2026-08-04 — see the session-log entry; both premises above are superseded.**
  (1) needed NO code: the shared-server ceiling was `simulator: 1` in the gitignored
  `showdown/config/config.js`, not the node process. At `simulator: 4` the shared server
  scales to W = 6–8 and BEATS one-server-per-lane by 26–50%, so **server sharding is retired
  as the unlock** and the port knob was never written. Lane scaling measured through the full
  loop: W=3 → 659 steps/s per lane, W=6 → 556 (3→6 costs 15.6% per lane, returns +41%
  aggregate); the ≥685 goal was NOT met. (2) is CLOSED as a **self-play-scoped** item —
  batching opponent forwards is 2.04× on the component but only ~2.5% of the loop under
  self-play and exactly 0% under `opponent: heuristics`; measurement (e) was never run and is
  not the gate. Revisit only when a self-play chapter is designed, priced as a code-cost
  tradeoff. **The finding that supersedes the framing above: collection-only benchmarks
  overstate full-loop gain ~7× (29% collection → 3.7% end-to-end). The loop is
  update-and-encode bound, not collection bound**, which contradicts the hardware note below,
  the collection-loop architecture work, and the surrogate-tuning interest. Next item is
  instrumenting the loop split (collect / encode / update / eval).
  `caffeinate`, and Wang's room-cleanup server hack if the poke-env-#332 slowdown signature ever
  appears. Engineering session under log-entry discipline — stated goals, no science claims.
  Calibration from the dig: Wang's 150M/4d is ~434 steps/s aggregate on 80 cloud workers (~5.4
  per core, both-perspective counting); the laptop already does ~1,760 full-loop. His scale is
  reachable by wall-clock, not hardware. Both-players collection is a self-play-only 2× (a
  scripted opponent's seat is off-policy data) — note for self-play chapters, not this one.

**Hardware (revised 2026-07-28 — the "rented cloud GPU" line was inherited from the Procgen-era
capstone and did not survive contact with the repo's own measurements; see the session log).**
Online self-play runs **CPU-first; no GPU is provisioned for it.** Reasoning of record: (1) the
tiny-net threading pathology is measured three independent times in this repo — MinAtar DQN 278 →
~1,550 steps/s single-threaded, Connect 4 PPO 2,196 → 8,473 (3.9×) at `torch_threads: 1`, and the
Phase-3 SAC probe where 4 threads *dropped* throughput 425 → 327 even at 256×256 nets — per-op work
this small loses to parallelization overhead, and a GPU is the same mistake at kernel-launch scale;
(2) the capstone encoder (structured vectors, MLP-scale, small Gen 1 embedding tables at most) is
the same regime as nets this repo already runs at 5.7k–12.5k steps/s on one core; (3) the env step
is a websocket round-trip to the Node server plus poke-env protocol parsing — milliseconds against
microsecond forwards, so the GPU-accelerable fraction of wall-clock is small; (4) on-policy PPO
holds no standing dataset to keep a device utilized. **A GPU re-enters for exactly three things**:
an offline supervised arm (the BC diagnostic below), the Procgen fallback (image observations — the
setting the old line was written for), or an encoder that outgrows MLP scale (a Metamon-shaped
transformer pivot). **Pre-registered Phase-5 throughput measurements** (each an evening once the
collection loop exists, before any provisioning decision, under the existing throughput-gate
discipline): (a) per-turn latency breakdown of one battle — server compute vs websocket RTT vs
poke-env parsing vs `embed_battle` encoding (if the encoder dominates, vectorizing it beats any
hardware change); (b) asyncio concurrency curve, aggregate turns/s vs battles-in-flight in one
process — the GIL ceiling; (c) multi-process scaling, workers × battles-per-worker, one Showdown
server per worker vs shared; (d) forward-pass share at the real encoder, batch-1 vs batched.
**Collection-loop structural contract (decided now, while it is cheap — before the loop is
written):** battle coroutines submit observations to a single inference seam rather than calling the
policy directly, so batch-1, micro-batched, and lockstep-vector inference stay config choices rather
than rewrites. Note the batch-1 small-tensor pathology belongs to poke-env's native asyncio `Player`
model; the `SubprocVecEnv`-over-`SingleAgentWrapper` route already batches at the vector boundary,
at the cost of head-of-line blocking on the slowest battle each turn. Whether micro-batching pays is
measurement (d)'s question, not an assumption. W&B merges local + cloud runs into one dashboard if a
cloud instance is ever used.

**Optional named diagnostic (the one workload where a GPU rents): behavioral cloning on Showdown
replays** — the same encoder + policy head trained supervised on a replay corpus, establishing an
architecture ceiling against which self-play results are interpreted (self-play ≈ BC ceiling ⇒ the
encoder is the bottleneck; self-play ≪ BC ceiling ⇒ the training is). Phase 4's
supervised-on-solver-labels diagnostic is this same instrument at smaller scale, and the
Pons-metrics finding there (no training variant moved tactical quality) is exactly the class of
question it answers. Scoping deferred to Phase 5 start: `gen1randombattle` replay availability and
parsing, and encoding from the acting player's observable state only. **Scoping RESOLVED
(2026-07-30, parallel-session advisory, folded in and deleted per the advisory precedent):
GO-WITH-CAVEATS.** Corpus clears the bar (~109k archived `gen1randombattle` replays ≈ 2.7M decisions
on the HolidayOugi HF archive — count not primary-verified, license unstated — with the official
`search.json` API confirmed live and accumulating; prefer a self-scrape through the documented JSON
endpoints, ~1 req/s etiquette, over the unlicensed dump). The work is the PARSER, not the data: no
random-battle format has an off-the-shelf spectator→first-person parser (Metamon's released datasets
are Gen 1–4 OU/NU/UU/Ubers + Gen 9 OU only; its MIT parser is read-for-reference prior art,
self-described "no way to be perfect"), and one omniscience leak is verified live — replay logs
store EXACT HP for both sides (e.g. 241/481) despite the HP-percentage rule, while the live client
gives each seat the opponent's HP at /100 resolution, so the parser must round opponent-side HP to
/100 (own side stays exact) or the BC arm trains on precision the deployed encoder never sees.
Corpus accumulation is bursty and partly tournament-sourced — stratify by rating/source. Open
questions (schema drift across years, possible end-of-battle full-team reveal per the approved 2019
full-info-replays thread, exact primary-source count) live in the 2026-07-30 session-log entry.

### P4 — encoder-ceiling BC diagnostic (pre-registered 2026-08-02; instrument landed 2026-08-01)

**Question.** Is the ~0.4 plateau vs SimpleHeuristics below what the 611-dim encoder + [512,512]
trunk provably supports? A feature audit of SimpleHeuristicsPlayer's source (2026-08-02 session-log
entry) answers the information half analytically; the run verifies it end to end and adds the
learnability half. Diagnostic outside the milestone ladder (Phase-4 contamination framing): the
clone never touches a pool, a tournament, or a milestone number.

**The audit, in one paragraph (evidence gathered before the bands were set — that is its job).**
SH's realized gen1 policy is a near-closed-form function of encoded features. Forced switches
(measured 20.5% of decision rows) are argmax `_estimate_matchup`, whose four terms — both
directional type multipliers, spe base-stat comparison, both hp fractions — are literal per-mon
encoder features, with ties broken by team order, which is slot order, which is encoded. Move choice
is argmax of bp × STAB × stat-ratio × accuracy × expected_hits × type multiplier — every factor
encoded except `expected_hits` (multi-hit moves; exposed on 1.8% of move rows, chosen on 0.29%).
**SH's setup-move branch is dead code upstream**: poke-env 0.15.0 compares `move.target` (int enum
`Target.SELF`) to the string `"self"`, always False — confirmed analytically (the verbatim predicate
matches zero gen1 moves) and empirically (status-clicked-while-damage-available 4/7,140, all
explained by immunity zeroing every damage score and the tie resolving to slot 0). Hazard, dynamax
and tera branches are dead in gen1. The stochastic fallback (`active is None`) never fires: 0
label disagreements in 8,943 triple-called live decisions, both actives present on every row —
**label noise ≈ 0**. Two consequences shape the bands: (1) a low-agreement FAIL cannot indict the
encoder's information content — the audit forecloses that reading; it would indict the trunk or the
optimization (itself a finding: if supervised SGD cannot fit a near-closed-form target on this
trunk, PPO never had a chance) or the BC method (compounding drift). (2) The existence proof
sharpens: a faithful clone scores the mirror baseline b ≈ 0.49 vs SH (measured 0.485 at n=2,000,
0.492 at n=400), and 0.49 > 0.42, the re-analysis's plateau asymptote. Side fact for the record: the
dead branch means SimpleHeuristicsPlayer is weaker than nominal in every poke-env 0.15.0 stack —
purely internal comparability for us (every milestone number used this same SH), possibly worth an
upstream report.

**Arms.** Primary: 20k SH-vs-SH battles (~450k decisions, ~3 min at the measured 2,825 decisions/s)
via `scripts/make_bc_dataset.py`, then `scripts/train_bc.py` at [512,512], 40 epochs, seeds 0/1/2
(one dataset, three fit seeds — init + battle-split + shuffle; collection noise is not the binding
term). Data check: one 10k-battle-subset fit (seed 0; the subset excludes the primary seed-0 val
battles, so both checkpoints score on the common val set). Conditional, built/run only if
triggered: a [1024,1024] capacity probe (R2 partial/fail) and one DAgger round — clone-visited
states relabeled by SH, refit, re-eval (R3 drift branch). Baseline b = the recorder's win rate over
the 20k collection battles themselves (n=20k, se 0.0035, ties count as non-wins — free from the
collection run).

**Reads, in order (locked):**

- **R0 — collection sanity:** b ∈ [0.45, 0.55]; ~22–23 decisions/battle; forced-switch share
  0.20 ± 0.05 (probe cross-check). Outside → HOLD interpretation.
- **R1 — fit health:** 3-seed val free-agreement spread ≤ 0.02 (multi-choice rows — decisions with
  >1 legal action; the uniform-over-legal floor is ~0.19); 20k-vs-10k common-val Δ < 0.01 = data
  non-binding (if ≥ 0.01: one pre-authorized doubling to 40k battles, nothing else changes).
- **R2 — agreement (fit gate, NOT the verdict):** val free-agreement ≥ 0.93 → audit verified
  (prediction ~0.97 given the enumerated residues). 0.90–0.93 → partial: capacity probe + R4 before
  any claim. < 0.90 → fit failure; explicitly not an encoder-information indictment (see audit);
  capacity probe, then investigate.
- **R3 — win rate (headline):** best-val checkpoint, deterministic, 1,000 battles/seed through
  `scripts/eval_checkpoint.py` (same seed rung as the campaign finals), pooled 3,000 (se 0.009)
  against b. **≥ b − 0.04** (≈3σ, and it absorbs the battle_against-vs-SingleAgentWrapper instrument
  mismatch we did not calibrate) → verdict: the architecture supports ≥ ~0.49 vs SH, so the
  0.408/0.42 plateau sits ≥ 7 points below a representable, supervised-learnable policy ⇒ **the
  plateau is training-side** (signal / distribution / optimization), not representational. The
  one-directional caveat attaches: nothing here shows PPO can REACH that policy under terminal-only
  reward — the claim is about where the ceiling is not. **< b − 0.04 with R2 passed** → compounding
  drift or strategically concentrated errors: run the DAgger round; closes → BC-method artifact,
  verdict as above; does not close → R4 names the sites — concentrated on expected_hits/status rows
  ⇒ a real-but-priced encoder gap (move identity; confirms the embedding follow-up), diffuse ⇒
  unaudited gap, back to a design session. **< b − 0.04 with R2 < 0.90** → no plateau verdict until
  the fit failure is understood.
- **R4 — disagreement concentration (always run; in-session analysis, no script changes):** val
  disagreements tabulated over {multi-hit-exposed, all-status-moves, forced-switch,
  switch-out-trigger, rest}. The audit predicts the first bucket dominates any shortfall.

**Contamination disclosed:** the machinery smoke saw 0.756 free-agreement at 3 epochs / 40k rows
(still climbing); the probe stats (b, forced share, branch deadness) were gathered in the design
pass — they are audit evidence the bands were deliberately set on. **Non-goals:** no value labels
(the collector records no outcomes; re-collection is 3 min if that ever changes); no cross-play vs
RL checkpoints. A passing clone is also a warm-start candidate above the RL best (0.49 > 0.408) —
flagged as a separate milestone-ladder decision, explicitly not taken here.

### Self-play priors carried from Phase 4 (verbatim)

- **~50% is the EQUILIBRIUM of self-play, not a failure.** With a randomized first player, a policy
  playing a frozen copy of itself scores ~0 net. Every "is it learning?" question is answered
  against the **fixed external anchors**, never against the pool — which is why `eval_opponent` can
  never resolve to a pool member. Published support: Metamon (RLJ 2025, arXiv:2504.04395 §5.3) let
  SynRL-V1 battle recent checkpoints of itself, got a model "significantly better against itself"
  that gave "inconsistent improvement against real players" — "battle replays make it clear that the
  model believes it is playing SynRL-V1" — in Gen 1 OU, the capstone's exact setting.

**What this deliberately does NOT de-risk** (budget separately): the async multi-battle collection
layer — our `SyncVectorEnv` of N in-process copies does not map onto poke-env's
asyncio-over-websockets to a single Node server, and that is the largest remaining capstone piece;
long horizons (≤42 plies vs Gen 1's >100 turns, so γ/λ/rollout length all need re-tuning); partial
observability; reward shaping; and eval-variance budgeting. Connect 4 is also, per Czarnecki et al.,
cyclic mainly in its mid-strength band, so the cycling detector gets built and only partially
exercised.


# Handoff — Stage 2 (the async collector), then the 100M run
Written 2026-08-31 23:45 EDT, maintainer-ordered. Run **Opus**.

Read `STATUS.md` first, then this. **A JOB IS RUNNING RIGHT NOW — §0.**

**THE GOAL, in the maintainer's words:** *"I want a 100M run, and I want it
done as fast as possible."* Everything below serves that. The 100M run is
~72 h on the current stack and takes the maintainer's laptop for three days,
so the standing order is: **finish every improvement and every open question
BEFORE that run starts.**

**Maintainer rulings already given this session — do not relitigate:**
- **CHAPTER5 §7 ruling 4 ("days at 100M is too much") is SUPERSEDED.** It was
  made believing no speedup was available. The 100M run is wanted. The
  supersession must be written explicitly into the 100M pre-reg header.
- **Build the speedups FIRST, then run 100M.** Not the other way round.
- **MPS is dead.** Measured, crashes, ~2.5% upside. Do not revisit.
- **~950 lines across seven files is acceptable**; git history is the safety net.

---

## 0. RUNNING NOW: R4S66 — check it before anything else

Launched 2026-09-01T01:40:48Z from a clean tree at `ce4c38e`, detached.

    ARMS="R4S66" bash scripts/ch5_r2_wave.sh   # log: logs/ch5_r2_wave_r4s66.log

3,000 battles, FP@20 search seat vs foul-play. **MEASURED IN FLIGHT: 3.21
s/battle** over the first 52 battles (including the 30 s start stagger; steady
state ~2.6), so **ETA ~2.2–2.7 h → finishing roughly 04:00–04:30Z**. It answers whether search still stacks on a batch lane — a
real input to which object we ladder — but it **ROUTES NOTHING** and cannot
touch R2's credited verdict.

It failed TWICE before tonight on the ORPHANED-ROOM DEADLOCK, which is now
FIXED (`9a0e54d`); this is the fix's first real workload. **If it wedges a
third time the fix is wrong and that is a bigger finding than the arm.**

- Progress, as a RATE (never artifacts): `grep -c 'Winner:'
  results/ch5_r2_offsh/r4s66.fp.stdout` against `grep -c 'Initialized battle-'`
  in the same file. **This arm's own measured rate is 3.21 s/battle** — use
  that, not CLAUDE.md's FP@20 1.2–1.5 s, which is the GREEDY seats' rate; a
  search seat plays 32–47% longer battles. 10x off means stalled.
- Orphan count = inits − winners; **1 is normal** (the battle in flight).
  Both prior attempts wedged at **exactly 4** and stayed there.
  With the timer fix a leaked room should now self-heal in ~300 s, and the
  seat's queue is 8 slots deep instead of 2. Orphans climbing past ~4 and
  staying is the signal the fix did not take.
- **The stall signature: process ALIVE, ZERO CPU, stale log, no crash.**
  `pgrep` NEVER catches it. `ps -o time= -p <pid>` twice, 15 s apart.
- Do not flip the username pair. It was already flipped (`956b909`) and the
  burned pair is recorded in the pre-reg's `burned_pairs`.
- Grade with `scripts/ch5_r2_grade.py`. **G2 is two tallies agreeing, never a
  subtraction.** The runner now also emits `fp_found_dead` /
  `fp_killed_while_alive` / `seat_frozen_at_kill` — if `seat_frozen_at_kill`
  is non-zero, the relaunches were OUR seat wedging, not foul-play crashing,
  and the crash-forfeit read rule does not apply to them. **That is an open
  maintainer question (§5), not yours to decide.**

---

## 1. STAGE 2 — the async collector. This is the job.

**Spec: `prior_work/THROUGHPUT_SPEC.md` §2 Stage 2 (design), §4 (gates).**
Read it before writing a line. Read `rl/collect.py` in full — it is only 162
lines and it is the foundation you build on.

**Why it exists.** The loop uses `SyncVectorEnv` with 8 sub-envs in lockstep:
every env step sends a move and WAITS for the reply before the next goes out.
E1 proved the serialization — `num_envs` 1→16 is flat at 523–550 steps/s, so
extra envs buy nothing. E3 found the round-trip wait is ~54% of a vector step.
**We are paying latency, not compute.** Stage 2 runs K concurrent battles per
worker and services whoever is ready, with no barrier.

**Build on the plain-`Player` path (`rl/collect.py`'s `SeamPlayer`), NOT
PokeEnv** — `poke_env/environment/env.py` hardcodes `max_concurrent_battles=1`
as a LITERAL at 273/292/355/375. This is architecturally lucky: **the eval
path (`ShowdownEnv`/`PokeEnv`, `make.py`) stays completely untouched, so the
locked eval protocol survives by construction.**

**K = 8–16, NOT the spec's original 32–64.** E4b measured the knee at K=8
(879 dec/s at K=1 → 1218 at K=8, flat to K=64 at ~1240).

### The honest expected gain — and it is LOWER than the spec says

The spec was written against the pre-batch-lever recipe (94.8% collect / 5.2%
update, `THROUGHPUT_SPEC.md:65`). **The batch lever tripled the update share.**
Measured tonight on the current recipe:

| quantity | value | source |
|---|---|---|
| collect / update per rollout | 45.83 s / 11.00 s | `runs/ch5_stage1_after/history.csv` |
| update share | **19.4%** | same (was 5.2% in the spec) |
| collection-only rate, solo | **670 steps/s** | 30,720 / 45.83 |
| async worker, entity width | **1240 dec/s** | E4b, `SESSION_LOGS.md:2697` |

So collection speedup ≈ **1.85×**, and Amdahl'd → **~1.55× end to end**, not
the spec's 2.6× or the audit's 2.0×. **Quote 1.5–1.6×, and re-derive it from
`history.csv` yourself before you quote it at all.**

100M at 3 lanes: 66 h today → **~43 h** at 1.55×. That is the prize.

### THE FIRST TASK IS NOT CODE — RE-BASE G8 AND G9

Both gates are calibrated on the pre-batch-lever recipe and **both will
misfire.** Do this before the build, not after.

- **G8** (`§4`) branches on `<900 steps/s → STOP`. Current 3-wide is **375
  steps/s/lane**; at 1.55× you land at **~580** — a clear win that trips a
  pre-registered stop. Re-base the thresholds on the batch recipe's own
  3-wide number, keeping the same *shape* (credited / short / stop).
- **G9** is the important one: a **null-expected** gate, |Δ| < 0.025 at 12M
  under the locked eval protocol, against a recorded **0.3890** basis that
  predates the entity trunk AND the batch recipe. It is the only thing that
  catches a silent correctness break no throughput metric would show.
  **THE CONTROL SIDE IS ALREADY ON DISK** — verified tonight:
  `runs/showdown_sp_batch50m_s{66,75,83}/ckpt_012000000.pt` all exist, and
  both resume seams (s66 @34.4M, s75 @47.2M) are far AFTER 12M, so all three
  12M rungs are clean. Evaluate them under the locked protocol (~20 min) and
  that is your new basis — **no 9-hour control fleet needed.**
  **Caveat that must go in the pre-reg:** those rungs come from a 50M run with
  `lr_anneal_steps: 50000000`, so the treatment must ALSO run the identical
  50M config and simply stop at 12M. Comparing against a 12M-annealed config
  would be comparing learning-rate schedules, not loops.
  **And remember the noise floor (§5): one rung re-draws ±0.02.** A |Δ|<0.025
  band against a single-rung basis is nearly untestable. Pool the three seeds
  and say so in the header.

### Two CRITICAL silent bugs the build must fix on the way

Both are currently *correct*, and only because the loop is synchronous.

1. **`old_logp` is recomputed at update start** (`rl/agents/ppo.py:886-896`).
   Exact today because the policy cannot change between collection and update.
   Under async collection it stays exact ONLY while updates are
   stop-the-world. **Record `old_logp` at action time instead** — you already
   have the logits there, and it removes the whole class of bug rather than
   depending on a property nobody will remember.
2. **`PoolPlayer` has a single `_battle_tag` latch**
   (`rl/envs/showdown.py:995-999`). On a tag change it re-selects a pool member
   and rebinds `self._current`/`self._member`. Under K interleaved battles
   that flips **which policy actually plays mid-battle**, not merely who gets
   PFSP credit. Per-battle-tag dicts. `MixturePlayer` has the same shape.
   **G6 already pre-registers the right gate**: each battle played end to end
   by exactly one member.

### File budget (spec's, unchanged)

`rl/envs/showdown_async.py` NEW ~350 · `rl/buffers/episode.py` NEW ~120 ·
`rl/collect.py` batched drain ~40 · `rl/agents/ppo.py` ~80 ·
`rl/train.py` `_async_loop` beside `_vector_loop` ~120 ·
`rl/envs/showdown.py` per-tag dicts ~20 · tests ~220.

**Suggested order — offline-testable first, so you are never far from green:**
`episode.py` → `ppo.py` (factor the epoch/minibatch loop out of `update()` so
a prepared batch can enter it; everything from `flat_obs` onward is reusable
verbatim) → per-tag dicts → `collect.py` drain → `showdown_async.py` →
`_async_loop`. **Land it green or not at all.**

Per-episode GAE is *simpler*, not harder: within an episode
`next_value = values[t+1]` and terminal bootstraps to 0. `ShowdownEnv.step`
already forces `terminated, truncated = True, False` at every finish, so
`last_value=0` is what happens today. It also deletes the second critic pass
(audit item 6, ~1%) for free.

### Measure it on/off, both directions — the maintainer asked for this

Baselines are banked and reproducible: `configs/ch5_mps_bench.yaml` is s83's
exact recipe cut to four rollouts (~4.5 min/run, first discarded as warm-up).
`runs/ch5_mps_bench_cpu1` is pre-Stage-1, `runs/ch5_stage1_after` is post.
Compare `time/collect_sec` and `time/update_sec` from `history.csv`, never
`scripts/showdown_throughput.py` (collection-only, ~7× overstated, hardcoded
`[64,64]`).

### DO NOT bundle A2 into Stage 2

Both-seat harvest makes batches return-balanced, which changes the data
distribution and **contaminates G9** — the null-expected gate that is the only
thing protecting a 3-day run. Land Stage 2 alone, pass G9, then A2 as its own
arm.

---

## 2. Then the 100M pre-reg — credit-seeking, full 2-Opus cycle

A 100M run needs its OWN pre-registration: arms, R0 sanity gates, PRIMARY read
with the credit line **restated verbatim including the larger-of (binomial vs
seed-clustered) se_diff clause**, the named across-lane aggregator, no unnamed
cells, and `journey_step` with its exit condition verbatim. Design decisions
for irreversible artifacts get **2 Opus agents + reviews** (maintainer,
2026-08-12).

It must also:
- **supersede CHAPTER5 §7 ruling 4 explicitly**, with the maintainer's
  reasoning: §7 assumed no speedup existed and priced 3 days as too much; the
  speedup now exists and 3 days is acceptable;
- read the PRIMARY off the **locked protocol**, NOT off single rungs (§5);
- keep `checkpoint_every: 500000` — the rung ladder is what made tonight's
  scale-shape read possible at all, and at 100M it is the only way the
  plateau question gets answered from the run itself;
- keep the case for 100M **independent of the scale-shape read**, which
  cannot distinguish plateau from noise at one seed and must not be
  load-bearing in either direction;
- state why 100M×3 beats the cheaper alternative it has to beat — **50M with
  more seeds.** σ_seed 0.0624 is the axis the read lives on, and two 50M
  fleets buy six seeds for roughly one 100M fleet's wall clock.

**Launch is the maintainer's** (rule 4: over 5 h is a hand-over).

---

## 3. Free measurement, whenever a lane is up

Per-lane core usage was never measured; the 1.2 cores/lane figure is an
estimate. E4a measured the Showdown server at **7.6% of one core** (max 15.7%)
at 1 lane against a budgeted 2.5–3, so the server has ~10× headroom. If 1.2
holds, a 3-lane run uses ~4 of 10 P-cores and **5–6 lanes cost ~15% per lane
and buy 67–100% more seeds** — the axis the read lives on. Buys no wall clock
(E1/§0: aggregate ≠ per-lane).

Attach it to R4S66 or any Stage-2 lane:

<command>
ps -A -o %cpu,command | grep -E "rl\.train|pokemon-showdown" | grep -v grep
</command>

`%cpu` on macOS is a LIFETIME average, so read it late in a lane, not at
startup.

---

## 4. Landed tonight — context you need, not work

- **THE ORPHANED-ROOM DEADLOCK IS FIXED** (`9a0e54d`), maintainer-ruled *ship
  everywhere, disclose*. `start_timer_on_battle_start=True` on every
  connecting seat. Verified live: a room whose opponent vanished RESOLVED in
  **300.0 s** returning its queue slot, vs **still open at a 420 s cap holding
  1/1** before. Regression scripts: `ch5_timer_smoke.py`, `ch5_orphan_demo.py`.
  **This matters for Stage 2**: a K-wide collector is the worst possible shape
  for that bug — each worker holds K rooms and leaks are cumulative. Pre-fix,
  Stage 2 would have been a fleet of slow-motion deadlocks. **Still count
  slots explicitly in the collector.**
- **STAGE 1 SHIPPED AND MEASURED** (`ce4c38e`): **+8.1% end to end**,
  `time/collect_sec` 50.547 → 45.827 (−9.3%). More than double the audit's
  estimate. (The −2.6% on `update_sec` is noise — neither change touches the
  learner. Read the collection number.) 72 h → 66.2 h on a 100M run.
- **MPS: measured and dead.** `device: mps` CRASHES at `rl/selfplay/pool.py:88`
  (CPU generator vs MPS probs — every self-play lane). Priced anyway on the
  learner: cpu@1 12.002 s, mps 10.449 s (1.15×), cpu@6 14.195 s (**0.85× —
  more threads is SLOWER**, so `torch_threads: 1` is now measured, not
  assumed). 1.15× of a 19% share is ~2.5% end to end. Numerics agree
  (argmax 512/512, `-1e8` sentinel intact) but not bitwise, so an MPS lane is
  a new lane, not a faster copy.
- **The audit's item 4 (eval cadence) is WRONG BY ~8× — it is off the list.**
  `time/eval_sec` is a locked metric and s83 logged 200 of them: mean 5.200 s,
  0.289 h total over 50M. At 100M that is **0.58 h of a 66 h run = 0.9%**, not
  4.6 h / 6.3%. Do not touch `eval_every`, and do not spend a pre-reg
  paragraph on it.

---

## 5. Open maintainer questions — escalate, do not answer

1. **CLAUDE.md:71's MPS wording.** Proposal on the table: keep CPU-only,
   replace "flaky" with the measured reason. **Not edited; his call.**
2. **Fix `rl/selfplay/pool.py:88` at all**, given the ~2.5% prize?
3. **May a stall-kill that forfeited no in-flight battle keep counting as a
   `crash_forfeit`?** A READ-RULE question against a frozen pre-reg. The
   runner now records the evidence (`seat_frozen_at_kill`) without acting on
   it. Live the moment R4S66 relaunches.
4. **A RESULTS disclosure line is OWED** with the next headline number: the
   wire differs from every pre-2026-08-31 arm's (`/timer on`).

**And the standing measurement trap, which will bite a checkpoint-ladder
read:** **one vs-SH rung at n=3000 is worth ±0.02, not the binomial ±0.008.**
Three re-draws of the SAME 50M checkpoint gave 0.76467 / 0.78467 / 0.78333,
spread 0.0200. Read a curve's SHAPE over tens of millions of steps; never one
rung against its neighbour.

---

## 6. Rules that cost hours, restated because this handoff spends the box

- `conda activate pokemon-showdown-rl` — never `base`, never shared.
- **Distinct `--seed`s on every concurrent lane**, including across arms.
- **Commit docs before launching; launch from a clean tree.**
- Job ownership by DURATION × KIND: training under 2 h yourself, 2–5 h ask,
  **over 5 h hand over**. Eval/analysis any length agent-side **if** detached,
  resume-safe, and readable as a RATE against a comparable arm.
- `showdown/config/config.js` must keep `simulator: 4` (line ~111, gitignored).
- **Watch the stall signature everywhere: ALIVE, ZERO CPU, stale output, no
  crash. `pgrep` never catches it. CPU-time deltas, 15 s apart.**

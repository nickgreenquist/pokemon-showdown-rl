# Landmines — the full incident record

**This file is the on-demand narrative behind `CLAUDE.md`'s one-line rules.**
Read a section only when you are about to touch the thing it covers, or when
a failure matches its signature. The rules themselves live in `CLAUDE.md`;
this file exists so they don't have to carry their war stories with them
(diet of 2026-08-29, REPO_CLEANUP §D2). Each incident is dated so it can be
cross-checked against `SESSION_LOGS.md`.

## Conda env

One env per repo: `pokemon-showdown-rl`, never `base`, never shared with
`deep-rl-from-scratch` — both ship a top-level `rl` package and the loser
imports silently from the wrong tree. No error, no warning; the wrong code
trains.

## Seeds and usernames

`rl/common/seeding.py` seeds global `random`, and poke-env derives its
Showdown usernames from that stream — so two concurrent lanes with the same
`--seed` (including ACROSS arms of different experiments) collide on
usernames and die with a misleading `TimeoutError` that reads as a server
problem.

## Launcher liveness

Run dirs (`config.yaml`, `meta.yaml`, `wandb/`) are written before the first
`reset`, so "directory exists" is true for a lane that never trained. A
launcher's liveness check must read battle PROGRESS, not artifacts. Related:
a lane can die at startup with SIGSEGV in torch lazy static init, before any
log line or run dir exists — stagger lane starts and verify every lane
individually.

## Progress is a rate, not an ETA

A wall-clock ETA is not progress. Sanity-check any long arm's s/battle
against a comparable completed arm (FP@20 ≈ 1.2–1.5 s, FP@100 ≈ 6–7 s); a
10× discrepancy means STALLED, not slow. The 3.6-hour zero-progress FP
incident below looked exactly like slow progress until the rate was checked.

## OBS_DIM and checkpoints

Changing `OBS_DIM` invalidates every existing checkpoint. Evaluate all
outstanding finals before any encoder change lands.

## eval/win_rate provenance

`eval/win_rate` comes from env-supplied `info["outcome"] ∈ {-1,0,+1}`, never
the sign of the return — a reward-sign inversion would report 100% and pass
its own detector (measured). `scripts/score_ladder.py` and
`scripts/eval_checkpoint.py` both report the env-supplied `win_rate`;
`wins_from_returns` is kept only as the sign-bug cross-check, and the two
must agree.

## ONE vs-SH RUNG IS WORTH +/- 0.02, NOT +/- 0.008 (2026-08-31)

The binomial se at n=3000 is 0.0077 and it UNDERSTATES what a re-run actually
moves. Measured on the CH5 scale-shape read: three independent n=3000 passes
over the SAME 50M checkpoint (`ckpt_050000000.pt`, s83) scored **0.76467,
0.78467 and 0.78333** — a spread of **0.0200**, 2.6x the binomial se, and the
two extremes are 1.9 se apart on the paired-se arithmetic that would have
called them a difference.

Showdown comparisons are UNPAIRED by construction (the server rolls teams and
damage, so the episode seed ladder buys nothing — `rl/common/evaluation.py`),
which is exactly why buying precision means buying BATTLES. The consequence for
any checkpoint-ladder read: **a curve's SHAPE over tens of millions of steps is
readable; one rung against its neighbour is not.** A single-rung dip or spike
of 0.02 is the instrument, not the policy. `scripts/ch5_scale_shape_report.py`
prints this re-draw check beside the curve so no one has to remember.

## vs-SH numbers are NOT ladder numbers

vs-SH gains can be SH-facing (measured 2026-08-23: +0.081 vs SH, negative vs
clone AND vs Foul Play; graded at z = −2.80). Never project a ladder number
from a vs-SH number, in either direction — the old "~40% GXE" rule of thumb
is RETIRED (RESULTS.md §15).

**The leaderboard/profile trap (2026-08-26 correction).** The top-500
leaderboard JSON contains only LISTED accounts, but the USER PROFILE carries
GXE and Glicko for any rated account. Our tooling polled the leaderboard and
declared the pre-registered primary read unmeasurable — false. Also
corrected: `L2.battles.jsonl`'s `rating` is the PRE-BATTLE rating, so the
long-quoted "Elo 1311" was the second-to-last value; the final is 1292.
LADDER R1's measured result: GXE 59.6%, Glicko-1 1573 ± 27, final Elo 1292
at n=200, not listed. Run a ladder with `scripts/ladder.py` per its own
pre-reg (`ladder_r3.yaml` is the template whose stopping rule reads the
profile and can actually fire); `scripts/score_ladder.py` is a
Connect-4-era false friend. Conversion caveats: top of `prior_work/README.md`.

## Foul-Play runner ops — four incidents, all fixed in `scripts/ch3_r4_fp_runner.sh`

Do not reintroduce any of these; the runner embodies all four fixes.

**(a) The subshell-pid orphan (cost: 15 relaunches, 14 orphans, 3.6 h at
zero progress).** `( ... ) &` makes `$!` the subshell's pid, so killing it
orphans a live foul-play holding the websocket AND the username — and it
looked exactly like slow progress. Use `exec` in the subshell, sweep by
`--ps-username`, abort on `nametaken`.

**(a2, 2026-08-26) Search workers are invisible to the username sweep.**
foul-play spawns multiprocessing SEARCH WORKERS whose command lines never
contain `--ps-username`, so killing the parent orphans them, they keep
server-side battle state alive, and the next seat/fp pair deadlocks at 0%
CPU on a battle neither side owns. Kill children FIRST
(`pkill -9 -P "$FP_PID"`) while the parent still owns them — once it dies
they reparent to init and `-P` cannot find them — then sweep
`foul-play/bin/python -c from multiprocessing` as belt.

**(a3, 2026-08-27, characterized across FOUR failures) Killing an arm
mid-battle poisons its username pair for HOURS.** The Showdown server keeps
the battle room open; any re-run under the same seat/fp names is handed the
stale room and foul-play dies in <10 s with `KeyError: 'battle\n'` out of
`fp/modes/base.py`'s battle-init parser — which reads as an FP bug, not an
ops failure. It recovers only when the room expires on the server's own
inactivity timer (C0 needed hours). So a killed arm must be re-run LAST, not
immediately, or under a fresh username pair (`ops_failure_rule` prescribes
exactly that). The runner's NO_PROGRESS abort catches the retry storm in
~80 s, so the cost is bounded — but the arm is still lost.

**(b) No forfeit at a clean boundary.** A crash at
`fp_completed == battles_requested` has no in-flight battle, so no forfeit
is owed — the blind `n_eff = seat − crash_forfeits` rule deletes a real
battle and fails a clean arm.

**(c) G2 is agreement, never subtraction.** The test is that two independent
tallies agree (FP's `Winner:` lines vs the seat's count).

**(2026-08-29 additions, from STATUS watch items)** foul-play can PANIC
(`Invalid PokemonMoveIndex: 4`, Rust) — twice in RS81 by battle 1580; a
mid-battle death poisons the pair (`burned_pairs_r10`: fresh pair, re-run
LAST). TIE-CRASH WEDGE: auto-tie + FP death on one battle hangs the seat
with no JSON.

## zsh vs bash

Shell loops run under `bash`, not zsh. Unquoted `$VAR` does not word-split
in zsh; `echo ===` is a glob error; inline `#` does not parse interactively;
`timeout` does not exist. `read -p` is a bash-ism — the zsh spelling is
`read -rs "P?prompt: "`. Anything handed to the maintainer runs in THEIR
zsh, so prompt-reading one-liners must be zsh-native.

## Throughput numbers

`scripts/showdown_throughput.py` measures server-side decisions/s only —
collection-only numbers overstate full-loop gains ~7×, and it hardcodes
`[64,64]` where production is `[512,512]`. Anything quoted from it must
carry its network width. (Both disclosures are also in the script's own
docstring.)

## MPS: MEASURED at last (2026-08-31) — 1.15x on the learner, and it CRASHES

"CPU only for the RL loop; MPS is flaky here" (CLAUDE.md, `rl/common/config.py`,
`docs/archive/DESIGN.md:548`) had NO benchmark, no session-log entry and no
narrative here — DESIGN.md called it "a repo convention". It now has all three.
**The wording of the CLAUDE.md rule is the maintainer's to change; this section
records only what was measured.**

**IT DOES NOT RUN.** `device: mps` dies on the FIRST opponent decision:
`rl/selfplay/pool.py:88` samples with
`torch.multinomial(probs, 1, generator=self.generator)`, where `probs` follows
`agent.device` but `self.generator` is always a CPU generator —
`RuntimeError: Expected a 'mps' device type for generator but found 'cpu'`.
So every self-play lane is affected, which is every lane. It is a ONE-SITE
defect, not a backend limitation, and it is why the three-arm training bench
returned one arm.

**WHAT A FIX WOULD BUY, priced on the learner in isolation**
(`scripts/ch5_mps_update_bench.py`, s83's exact recipe: `[512,512]`
entity-deepsets, 30,720-step rollout, 4 epochs x 120 minibatches of 256):

| arm | `update_sec` | vs cpu1 |
|---|---|---|
| cpu, `torch_threads: 1` | **12.002** (11.934–12.070) | 1.00x |
| mps | **10.449** (10.436–10.461) | **1.15x** |
| cpu, `torch_threads: 6` | **14.195** (13.869–14.520) | **0.85x** |

The proxy is validated: its cpu arm reads 12.002 s against **11.285 s** logged
by a real training run of the same config and **12.954 s** banked over s83's
1,627 rollouts.

**1.15x ON THE LEARNER IS ~2.5% END TO END.** Collection is Node-bound and
cannot benefit: a rollout on this box is 50.5 s collect + 11.3 s update, so the
whole prize is ~1.55 s in ~62 s. **Any headline "N x faster" that folds
collection in is wrong by construction** — and `scripts/showdown_throughput.py`
is not the instrument either (collection-only, ~7x overstated, hardcoded
`[64,64]`).

**`torch_threads: 6` IS SLOWER THAN 1** — 0.85x, on a 14-core box. Minibatches
are 256 rows wide; the threads spend their time on barriers. The existing
`torch_threads: 1` is not a leftover, it is the fast setting, and that is now
measured rather than assumed.

**NUMERICS ARE FINE, AND THAT IS NOT THE SAME AS REPRODUCIBLE.**
`scripts/ch5_mps_numerics.py` over 512 real observations: max abs diff on raw
logits 1.8e-4, on masked logits 1.8e-4, on masked entropy 2.0e-5, on values
1.1e-5; the `-1e8` sentinel is preserved on both devices, illegal actions carry
EXACTLY 0.0 probability mass on both, no NaN or Inf anywhere, and the
deterministic argmax agreed on 512 of 512. So the harness's masking contract
survives the backend. But 1.8e-4 on logits means an MPS lane is NOT
bit-comparable with a CPU one, and neither is the opponent sampler's RNG stream
once its generator moves device — a switch is a new lane, not a faster copy of
an old one.

## Job lifetime, not throughput (2026-08-26 correction)

CLAUDE.md claimed "~10× slower agent-launched" until 2026-08-26; the repo's
own measurement (2026-08-14) is 433 steps/s from the agent — near-native —
and the session log flagged the discrepancy at the time. What actually
breaks a long agent-side job is that it dies with the session. Hence the
three-part safety test in CLAUDE.md's job-ownership rule: detached,
resume-safe, progress readable as a rate.

## DESIGN-era traps (files now under `docs/archive/`)

DESIGN.md's D19 entry sent a whole session down a dead lever (2026-08-16)
because the file is not self-updating; r7 retired §10–11, so any
"DESIGN §11" pointer is dangling; its attention ruling (§4 Rung 2) is a
COST ruling — a 34.6× microbenchmark, never trained — not evidence that
attention fails. All of this is why `docs/archive/` exists: nothing under
it is read unless the maintainer names the file.

## THE SILENT LANE STALL (2026-08-31, R2 — the expensive one)

Two of three R2 lanes stalled mid-run **~10 h apart** with an identical
signature: s66 at 68.9 % (step 34,440,776) and s75 at 94.3 % (step
47,170,680). In both cases the training process stayed **ALIVE**, held its
~18 TCP sockets open, and burned **ZERO CPU** — 0.01 s over a 20 s sample
against ~14 s for a healthy lane. Logging went stale and RSS bled away as
the OS paged the idle process out (down to 0.08 GB from 2.3 GB). Both
followed a burst of Showdown `bigerror` turn-1000 auto-tie messages, which
is suggestive of a battle hitting the turn cap and leaving the lane waiting
on a socket that never resolves — suggestive, not proven.

**Why this is worse than a crash.** Every `pgrep -f "rl\.train"` check
passes forever. A dead lane announces itself; a stalled one does not. s75
sat frozen for **5.2 h** waiting on a maintainer ruling, and had the run
been unattended overnight it would have burned the whole night.

**Detection, in order of speed.** A step count is the ground truth but needs
two polls 20–30 min apart to be conclusive. **CPU-time deltas settle it in
15 seconds** — sample `ps -o time= -p <pid>` twice and diff:

    ps -o pid=,time= -p <pid>; sleep 15; ps -o pid=,time= -p <pid>

Identical CPU time on a training process means stalled, full stop. Cheap
corroborators: last history row age vs wall clock, `.wandb` file mtime,
and RSS falling instead of holding.

**Recovery is cheap and it works.** `--resume runs/<dir>` restores step,
loop state, optimizer and `pool.pt` (the pool snapshot exists, so the
"pool reseeded" disclosure path is NOT hit). Kill the hung pid, confirm the
sockets are released, then resume — the seed-derived usernames are reclaimed
cleanly once the process is gone.

## `checkpoint.pt` lags the last logged step by MORE than one update

The R2 handoff claimed a resume "discards <= 30,720 steps" (one update).
Measured: **s66 lost 190,776 steps** (from_step 34,250,000 vs last logged
34,440,776) and **s75 lost 170,680** (47,000,000 vs 47,170,680) — 5–6× the
quoted figure. `checkpoint.pt` is written on a coarser cadence than every
update. Still small against 50M (~0.4 %), but quote the REAL from_step out
of `meta.yaml`'s `resumes:` block, never the one-update assumption. Each
resume also costs one update in the ledger: both resumed lanes finished at
`updates_done` 1626 against the clean lane's 1627 (DISCLOSED by the
attestation rule, never a failure).

## A resume SPLITS the run's wandb history

Every resume starts a SECOND wandb offline run, and its step range OVERLAPS
the first (the re-run steps). Consequences:

- **`scripts/extract_history.py <run_dir>` HARD-FAILS** on a resumed lane —
  "expected exactly one offline run, found 2 — pass the .wandb file
  explicitly". This is the safe failure (an error, not a wrong answer), but
  the documented incantation simply stops working on those dirs.
- **Merging is not concatenation.** The overlapping steps were re-run with
  different data and the RESUMED run is authoritative over them. Rule: keep
  pre-resume rows with `_step < from_step` (from `meta.yaml`), then append
  the whole post-resume run. Verify monotonic in `_step` and check the seam.
- The **verdict path never reads history** — grader, wave, preflight and
  `eval_checkpoint.py` all work off `checkpoint.pt` and results JSON — so a
  mishandled merge corrupts curves and readouts, not the credit decision.

## Gate thresholds are calibrated at a FLEET WIDTH (2026-08-31)

R2's D-E memory gate (record > 3.0 GB, STOP > 4.5 GB) was set against a
measured 2.68 GB/lane **3-wide**. When the resumed s75 finished alone it
reached **5.87 GB** — over the STOP line — with the box 85 % free and swap
FALLING. Killing a lane at 94 % to satisfy a number calibrated under
different conditions would have been the error; the breach was DISCLOSED
and the run continued (maintainer ruling). Before acting on a resource gate,
check whether the fleet width it was measured at still holds. The reverse
also bit: early D-B windows that straddled startup read 366–373 st/s and
produced three spurious sub-371 "records"; the conforming window (post-1M,
>= 30 min) read 375–380 and no record stood.

## THE ORPHANED-ROOM DEADLOCK (2026-08-31) — one bug, three hangs, ~360k lost steps

**This is almost certainly the same bug as "THE SILENT LANE STALL" above.** Read
both together; that section describes the symptom, this one the mechanism.

**The chain.** A long game reaches Showdown's turn-1000 Endless Battle Clause.
Both sides are out of PP and use Struggle — **move index 4** — which panics
foul-play's Rust engine (`src/state.rs:106`, `Invalid PokemonMoveIndex: 4`).
The dead opponent leaves a battle room our client still holds. poke-env
releases a room's queue slot ONLY on `|win|`/`|tie|` (`player.py:311`), and
because `start_timer_on_battle_start` defaults to **False** we never send
`/timer on` — so that room never resolves and its slot is never returned. Once
leaked rooms fill `_battle_count_queue` (maxsize = `max_concurrent_battles`),
the next `|init|battle` blocks forever at `player.py:221`
`await self._battle_count_queue.put(None)`. The cycle is closed:
`accept_challenges` parks on the semaphore released only AFTER that put; the
put is woken only by a `get()` that only a finishing room performs.

**Measured, R2's FP wave** (`Initialized battle-` vs `INFO Winner:` in each
arm's `fp.stdout`, and `on turn 1000` in each `seat.stdout`):

| arm | inits | winners | ORPHANS | turn-1000 auto-ties |
|---|---|---|---|---|
| t66 / t75 / t83 (GREEDY) | 3000 | 3000 | **0** | **0** |
| r4s66 attempt 1 (SEARCH) | 2679 | 2675 | **4** | 240 |
| r4s66 attempt 2 (SEARCH) | 1540 | 1536 | **4** | 264 |

Both search attempts wedged at exactly 4 orphans against a 2-slot queue. Zero
orphans in 9,000 greedy battles. **The search policy plays long enough to reach
turn 1000; greedy never does** — which is why this arm failed twice and the
greedy arms never did. The pair-flip did NOT help and could not: the poisoned
room was never the cause.

**TRAINING IS STRICTLY WORSE.** `poke_env/environment/env.py` hardcodes
`max_concurrent_battles=1` as a LITERAL at lines 273/292/355/375 — it is not
forwardable from `rl/envs/showdown.py`. **One** leaked room wedges a lane
forever. The last activity before BOTH training hangs is a turn-1000 auto-tie
burst: s66 at `2026-08-31 01:29:16`, s75 at `07:54:33`. Cost: 190,776 + 170,680
re-run steps and a 5.2 h freeze.

**IT IS PROBABILISTIC, NOT DETERMINISTIC — do not over-claim.** s83 hit turn
1000 **482** times (more than s66's 192 or s75's 400) and never stalled. Turn
1000 is necessary, not sufficient; the room must actually orphan.

**The watchdog blames the wrong process.** `scripts/ch3_r4_fp_runner.sh`'s
`log_bytes()` (:122-126) reads `$FP_LOG` ONLY. A wedged SEAT starves foul-play
of anything to log, so fp is killed for "stalling" and `RELAUNCHES++` is
charged to fp. On a graded arm the crash-forfeit rule would have credited us
**4 phantom forfeits**. The wave's printed remedy ("re-run under a FRESH
username pair") is therefore the WRONG remedy for this failure.

**Fixed 2026-08-31 (commit `fc3066d`), but NOT the obvious way.**
Summing the SEAT log's bytes into `log_bytes()` was considered and REJECTED:
`ch3_fp_h2h.py` prints at start and at end and NOTHING per battle, so that log
does not grow during a healthy run and the sum would change no decision — it
would only give a growing FP log a way to hide a dead seat. The seat's real
liveness signal is CPU TIME (the instrument CLAUDE.md already mandates for this
signature), so the FP-log trigger stays and a 15 s CPU-delta probe ATTRIBUTES
at the moment of the kill. Attribution is RECORDED, NOT ACTED ON:
`fp_found_dead` / `fp_killed_while_alive` / `seat_frozen_at_kill` land in the
arm JSON while `crash_forfeits` keeps its frozen pre-reg meaning (= relaunches).
Whether a stall-kill forfeited a real in-flight battle is a READ-RULE question
against a frozen pre-reg and is the maintainer's to answer. Separately, the
`pid is gone` branch now calls `kill_fp`, so search-worker children are reaped
on the one path where the parent dies by itself.

**THE FIX, APPLIED 2026-08-31 (commit `9a0e54d`) under the maintainer's
"ship everywhere, disclose" ruling.** `start_timer_on_battle_start=True` on
every connecting seat: `rl/envs/showdown.py` (ShowdownEnv → ShowdownSingles →
PokeEnv — a knob, default True), `scripts/ch3_fp_h2h.py`, `scripts/ladder.py`,
`scripts/foulplay_vs_sh.py`. It attacks the CAUSE and is the ONLY fix available
to the training env, whose `max_concurrent_battles` is a hardcoded literal.
Secondary: the h2h seat's `max_concurrent_battles` 2 → 8 (pure slack; 4 orphans
< 8 would have carried both R4S66 attempts). **The ladder seat stays at 2 on
purpose** — its games are rated and matchmade, so extra slots would change the
very thing a ladder run measures.

**THE LADDER ALREADY HAD IT, AND THAT IS THE BEST EVIDENCE WE HAVE.**
`scripts/ladder.py` has forwarded `start_timer_on_battle_start` from the
pre-reg's `pacing.start_timer` since R1 (`ladder_r1.yaml:260`,
`ladder_r3.yaml:833`, both true; R1 records it VINDICATED at n=17 against a
staller). So **every banked LADDER number was produced with the timer on** —
the strongest evidence in the repo that it is inert for a bot answering in
milliseconds. Two consequences: the handoff's premise that `ladder.py:465`
needed the fix was wrong, and hardcoding it there raises `got multiple values
for keyword argument` on the real ladder path — it must be a
`kwargs.setdefault`. Nothing in the test suite covers that constructor, so the
first sign would have been a dead ladder run.

**IT IS WIRE-VISIBLE AND THE DISCLOSURE TRAVELS WITH IT.** Every battle from
here carries a timer; each seat receives ~25 extra inbound `|inactive|Time
left:` lines per battle (measured: 302 over 6 battles, against 0 before). The
accepted trade is that a process pause past the turn budget now becomes a
VISIBLE LOSS instead of an unbounded silent hang. The margin is 20x: these are
CHALLENGE battles, so 300 s/turn + 60 s grace (`STARTING_TIME_CHALLENGE` /
`MAX_TURN_TIME_CHALLENGE`, room-battle.ts:47-49) against a measured **max
`time/update_sec` of 15.34 s** over s83's 1,627 updates. **The LADDER is the
tighter path** — a ladder game is not a challenge, so it gets 150 s, not 300.
A RESULTS disclosure line is OWED with the next headline number.

**VERIFIED LIVE, TWICE — do not accept a code read here** (the two scripts are
the standing regression):
- `scripts/ch5_timer_smoke.py` — on the REAL training env: 12 `/timer on` sends
  over 6 battles, one per seat per battle, with 12 SERVER acknowledgements
  (`|inactive|Battle timer is ON`); the knob-False control sends 0 and sees 0.
- `scripts/ch5_orphan_demo.py` — the incident in miniature. A room whose
  opponent vanishes at turn 1 **RESOLVED after 300.0 s** (=
  `DISCONNECTION_BANK_TIME`) and RETURNED ITS QUEUE SLOT (0/1 held); the
  identical room without the timer was **still open at the 420 s cap, holding
  1/1 slots** — which at the training env's hardcoded
  `max_concurrent_battles=1` is the deadlock itself. So an orphan now costs
  ~5 minutes, not the lane.
  Writing that demo cost two false starts worth remembering: poke-env runs every
  player on its own background `POKE_LOOP` and only the wrapped entry points
  (`battle_against`, `stop_listening`) marshal across it, so awaiting
  `send_challenges` from your own loop hangs silently; and a local
  heuristics-vs-heuristics battle runs END TO END IN ~40 ms, so you cannot
  react to `|init|` from outside — mute the opponent's
  `_handle_battle_request` first, then drop its socket.

**Open question for the maintainer:** whether the FP anchor is runnable AT ALL
for search seats at n=3000 while foul-play panics on Struggle. Options — patch
foul-play (precedent: `scripts/patches/foulplay_gen1_local.patch` is already
sha-stamped in `wave.provenance.json`), accept lower n for search arms, or
pre-register exclusion of turn-1000 battles. All three touch a frozen pre-reg
and/or the G8 provenance stamp.

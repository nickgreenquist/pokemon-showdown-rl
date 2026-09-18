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
Connect-4-era false friend. Conversion caveats: top of `docs/prior_work/README.md`.

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

**Correction 2026-09-05 (gen4-build; `docs/design_gen4/research/foulplay_pokejax_audit.md` §2).** The "both sides out of PP → Struggle → move index 4" MECHANISM above does not survive foul-play's source: Struggle is never added to a move list (`fp/battle/protocol.py:766-768`) and the bot's list is rebuilt from the request every turn (`fp/battle/state.py:357-368`). The index hole is an unbounded `move:{i}` in `fp/search/poke_engine_helpers.py:117-126` (the 4-move truncation lives in a different function called later); no source-reachable 5-move path exists in gen 1 or in the vendored gen4 pool, so WHAT fired in RS81 / R4S66 is unresolved. Pre-flight detector: `grep "More than 4 moves on pokemon"` over the foul-play log (0 hits over the 525 recorded gen-4 FP battles — fp0 5, fp1 250, h2h0 20, fp2 250 (`docs/design_gen4/research/live/fp*`, `h2h0*`; every summary's `fp_log_greps.more_than_4_moves` is 0), 2026-09-05). The SYMPTOM chain — a dead opponent leaving a room we hold, and `/timer on` as the fix — stands unchanged.

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

## EVERY SEARCH NUMBER BEFORE 2026-09-11 MEASURES A BROKEN SELECTOR, NOT SEARCH

**Maintainer, 2026-09-11: "our search was BROKEN before. those results should have
a massive asterisk next to them."** They do now. Grep `PRE-D5` to find them.

**What was wrong.** `rl/search/matrix.py` clause **D4** took a hard `argmax` over
the renormalized matrix score, using the policy prior only as tie-break D3. On the
100M finals that **overrode the policy's own argmax on 72.8% of decisions** — a
0.789-strength policy, overruled three times in four, on a one-ply value estimate
whose leaf noise (sd 0.125) is **4.5x the decision margin** (0.028). That is the
textbook maximization-bias / optimizer's-curse amplifier: the argmax selects
whichever leaf drew the luckiest positive error. More leaves made it WORSE, which
is the signature — dose L read BELOW dose M, ungated.

**What fixed it.** Clause **D5**, the margin gate (2026-09-11): play the search's
action only if it beats the POLICY's argmax by more than `margin_delta`. Same
critic, same ~300 leaves, same 63 ms. On lane s112, n=3000 per arm, against
greedy 0.78233:

| selector | win rate | overrides |
|---|---|---|
| D4 (every pre-2026-09-11 number) | 0.74767 | 71% |
| D5 at delta 0.05 | 0.80867 | 23% |
| D5 at delta 0.10 | **0.82400** | 8.5% |

**-0.035 to +0.042 from the decision rule alone.**

**The rule this creates, and it is binding.** A pre-D5 search number measures
**the old selector**, not "search". It may not be used to argue that search does
not pay, that depth does not pay, that more dose does not pay, or that a searched
object ladders worse than a greedy one. Any such argument must be re-measured
under D5. This applies to **LADDER R3** (the only searched object ever laddered:
GXE 60.3 / Glicko-1 1579 / Elo 1232 — a D4 object), to chapter 3's credit
(+0.0693 at 12M) and its dose axis, to the search-depreciation curve (already
VACATED for a different reason 2026-09-10), and to every off-Foul-Play searched
number (0.396 / 0.406 on s112).

**What a pre-D5 number still supports.** It is a valid measurement of that
configuration. CH3 R2's +0.0693 at 12M was real: on a WEAK policy, overriding the
argmax 71% of the time was not obviously worse than trusting it. The defect only
bites once the policy is strong enough to be worth deferring to — which is exactly
why the sign flipped between 12M and 100M and why nobody caught it for a chapter.

**Not yet closed:** whether the D5 gain transfers off SimpleHeuristics. CH3 R2's
credit was SH-FACING and did NOT transfer (FP 0.388 -> 0.368; BC-clone 0.894 ->
0.860). `configs/eval/search_budget_ladder_offfp.yaml` stages that probe first,
precisely so the same mistake is not made twice.

## `taskpolicy -b` on an eval job costs ~7x and makes its timings incomparable (2026-09-11)

**What happened.** The EG10 queue was written with `taskpolicy -b` in front of
`ch3_eval.py`, copying the habit from the engine-port brief (which prescribes
background QoS for *builds*, and is right to). Its first chunk read **549.8
ms/decision** against **81.1** for the banked C10 arm at the same dose, the same
leaf count (347 vs 358) and a comparable number of concurrent jobs. That is a
**6.8x** penalty, and it projected the arm from ~2 h to ~12 h.

**Why.** This box is **10 performance + 4 efficiency cores**
(`sysctl hw.perflevel0.logicalcpu hw.perflevel1.logicalcpu`). `taskpolicy -b`
is BACKGROUND QoS, which on Apple Silicon schedules onto the EFFICIENCY cores
only. Three search lanes sharing four efficiency cores is the whole story.

**Two costs, and the second is worse.** The obvious one is wall clock. The
subtle one is that **every other eval queue in this repo runs at normal QoS**
(`search_s3_queue.sh`, `search_ladder_queue.sh`, `ch3_r4_run_sweep.sh` — none
of them call `taskpolicy`), so a `-b` arm's `search/ms_mean` is not comparable
to the banked arms it is being measured against. A timing read taken this way
is not a slow number, it is a **wrong** number.

**What it does NOT touch.** Outcomes. The eval is seeded per chunk, so QoS
changes speed and nothing else: win rates, leaf counts, override rates and
decision counts from a `-b` chunk are all valid and may be pooled. Only the
WALL-CLOCK fields (`search/ms_mean`, `ms_p50`, `ms_p99`, s/battle) are
contaminated, and only for the chunks that ran that way.

**The rule.** `taskpolicy -b` for BUILDS (cargo, pip) — yes, that is what the
engine-port brief means. For anything whose NUMBER you intend to quote, or
that you want to finish this decade: normal QoS. And when an arm's timing is
7x a comparable banked arm at the same leaf count, suspect the scheduler before
suspecting the lever — the first hypothesis here was "the LOO evaluator and the
margin gate interact superadditively", which was wrong and would have been a
much more interesting finding to report falsely.

**How it was caught.** Not by the wall clock (a slow arm looks like a busy
box). By comparing `chunk00` to `chunk00` across arms — same code path, same
measurement — where 77.1 / 81.1 / 549.8 at matched leaf counts is not a load
story.

**CONFIRMED the same night, by relaunching at normal QoS and comparing chunk to
chunk on the SAME job:**

| eg10_s104 | ms/decision | s/battle | leaves_mean |
|---|---:|---:|---:|
| chunk00, `taskpolicy -b` | 549.8 | 14.98 | 347 |
| chunk01, normal QoS | **79.4** | **2.21** | 351 |
| banked C10 chunk00 (PLAIN evaluator, normal QoS) | 81.1 | 2.23 | 358 |

**6.9x**, and the diagnosis is airtight in both directions: at normal QoS the
LOO-evaluator arm costs **79.4 ms against the plain evaluator's 81.1** — i.e.
the evaluator this was briefly blamed on is FREE at this dose, and the entire
gap was the scheduler. Leaf counts are unchanged throughout (347 / 351 / 358),
which is why the dose-match check was written on `leaves_mean` rather than on
wall clock and why it still holds across the QoS split.

## EVERY SEARCH NUMBER IN THIS REPO IS DEPTH-1. Do not read one as a verdict on search (2026-09-11)

`rl/search/` implements **one ply**. The dose dials (S/M/L/XL) buy more
DETERMINIZATIONS and more LEAVES at that single ply; **none of them is depth.**
There is no depth-2, there never has been, and `docs/search_relook/
ENGINE_SEARCH_DESIGN.md` prices building it at 8-11 blocks.

So a null on the evaluator axis, on the dose axis, or on the selector axis is a
statement about **depth-1 at a named dose and a named delta**, and nothing more.
Write it that way.

**This rule exists because the 2026-09-11 session broke it.** That session
measured EG10 (a better leaf evaluator under a working gate) at **-0.00044,
0.05 se** and logged it as *"EG10 CLOSES THE EVALUATOR AXIS: A BETTER EVALUATOR
BUYS ZERO"* — into STATUS.md and SESSION_LOGS.md, the two files every session is
required to read. At the moment those words were written:

* **dose XL (BLX) was still executing on the same box** — the deep rung of the
  budget ladder, unread;
* **P0 had passed its stop rule that same night** (sigma-margin ratio 0.509),
  i.e. depth-2 was explicitly **NOT killed**;
* the session had, hours earlier, written the **PRE-D5** landmine telling future
  agents never to cite a number to argue "search/depth/dose does not pay" — and
  then produced exactly the sentence a future agent would cite to do so;
* and the arm's OWN pre-reg carried the scope limit verbatim (*"DOES NOT
  LICENSE: ... anything about DEPTH"*), which simply was not carried into STATUS.

That is the whole failure mode: **the caveat lives in the pre-reg, which nobody
re-reads, while the headline lives in STATUS, which everybody does.** A scope
limit that is not in STATUS does not exist.

**The rule.** Any search result written into STATUS, SESSION_LOGS, RESULTS or a
README row names its DEPTH, its DOSE and its DELTA in the claim itself. Words
like "closes", "answers", "settles" or "buys zero" are barred for the search
axis until depth-2 exists and has been measured. The available words are the
honest ones: *"at depth-1, dose M, delta 0.10, X adds nothing."*


## SEEDS DO NOT PAIR BATTLES — "matched seed-for-seed" is not a paired design (2026-09-11 review)

The eval seed (`seed_start + episode`) pins OUR decision RNG and nothing about
the battle: the team draw and every damage roll come from the Showdown server,
which our seed never reaches. Measured from the chunk JSONs: per-battle
agreement between two arms on the same seed block sits where two INDEPENDENT
Bernoulli draws at p≈0.8 would put it (0.68) — greedy vs S3G10 0.686, greedy
s112 vs greedy s104 0.657, two exact-config replicates of the depth-1 tree
0.674, ENS3 vs ENSG 0.727.

Consequences:

* "Matched seed-for-seed with McNemar se" (STATUS 2026-09-11 16:14, the depth
  doc) is NOT a paired design. No number moved — on independent pairs
  McNemar's sqrt(b+c)/n equals the unpaired two-proportion se in expectation —
  but the words claim power that does not exist. Write "unpaired,
  two-proportion binomial se".
* The 16:14 corollary "a 300-seed arm may NOT be read against a 3000-seed
  pooled mean — on seeds 100–399 greedy runs +0.054 above its own pooled
  value" was a misdiagnosis: with no pairing there is no seed-block offset to
  correct for. A 300-battle subset has se 0.023 and +0.054 is a 2.3-se
  excursion among many arms — the existing "one rung is worth ±0.02"
  landmine, not a new mechanism. The rule is "n=300 cannot resolve ±0.05";
  "compare matched" buys nothing.
* Two runs of the SAME arm on the same seeds differ by ordinary sampling
  noise: TSAMP1 0.8144 vs TQV 0.7778 (n=900 each, identical dials), a 0.037
  gap. The 16:14 STATUS read one replicate as "the control reproduces the
  banked matrix" and did not report the other. **Replicates are the
  instrument; report every one that ran.**

## SMALL-RUN NULLS ARE NOT EVIDENCE, and every session re-quotes them anyway (ruled 2026-09-06, restated 2026-09-11)

The maintainer has said it repeatedly, and it is now CLAUDE.md rule 6: a 12M
(or 50M, 3–5 seed) A/B null closes nothing about a lever at 100M+. The bars at
that dose are 0.065–0.10 unpaired, so an advisory-scale effect (+0.02..0.05)
lands in the noise band whatever the truth is. Only a MEASURED MECHANISM
CEILING kills — shaping's algebraic inertness, a bounded information leg
measured on the format, an exploitability read. `docs/IDEAS_POST_100M.md` §3
classifies every kill by which kind it is.

**The failure that keeps recurring, in its exact shape.** Asked "what do you
think of the privileged critic?", four sessions in a row answered with D18's
12M × 5-seed win-rate null ("it predicted returns better but play did not
improve"), sometimes hedged with "dose-limited", as if the hedge made it
usable. It does not. The maintainer, 2026-09-11: *"I've said so many times WE
CANNOT MAKE CONCLUSIONS WITH such small runs ... I don't want to hear of a
single 'idea being killed' based on what was tried on a 12M run."*

**The rule in practice.**
* A number from a sub-100M A/B may appear in a doc as PROVENANCE ("D18 ran, here
  is what it read, it is dose-limited") and nowhere else. It never appears in an
  opinion, a recommendation, a ranking, or a "why we dropped X" sentence.
* When asked for an opinion on a lever, the inputs are: the mechanism, what the
  field does at scale (AlphaStar, MAPPO, OpenAI Five, Suphx, the plasticity
  literature), the format's own properties, and the cost. If none of those
  speak, say "unmeasured at scale", not "killed at 12M".
* "Dose-limited null" is a classification for §3, not a licence to cite. If the
  sentence would not survive deleting the number, delete the sentence.

## THE OVERRIDE RATE IS THE CONFOUND, AND A TREE ARM DOES NOT REPORT ONE (2026-09-17/18)

Two separate traps, one field.

**(1) An unmatched override rate turns a null into a result.** JOURNEY 11.5
measured depth-2 minus depth-1 at **−0.0007 (0.05 se)** when both arms were
matched on REALIZED override rate, and **−0.053 (3.34 se)** on the same
checkpoints, the same depth and the same everything else when they were run at
the same `margin_delta` instead. A deeper backup spreads leaf values wider, so
an identical delta lets ~2.4× as many overrides through. **Every depth number
this project published before 2026-09-17 compared arms that differed in how
often search was BELIEVED, not in how deep it looked.** The rule that came out
of it is general and is now in CLAUDE.md's conventions: **match the comparison
on the thing that is NOT being tested**, and let the pin read the matching
quantity and never a win rate (at n=60 a win rate carries se 0.065 — larger
than every effect these blocks look for).

**(2) A TREE arm reports `search/override_rate: None`.** That field is gated on
`margin_delta`, which belongs to the MATRIX selector; the tree carries its
margin in `tree.margin`. The quantity exists — it is
`search/flips / (decisions − placeholder_skips)` — but under different
bookkeeping. Taking the None at face value blocked the tree block's pin from
07:05Z to 10:45Z on 2026-09-18 with a bare `PIN FAILED`, and the same None
printed as `nan` in the readout. Both now fall back. **If you add a vehicle,
check what its override rate is CALLED before you match anything on it.**

**And the gate is not a nuisance parameter — it is the instrument.** RESULTS
§24: holding depth and opening the gate from ~6.5% to 16–19% costs our critic
0.006 (0.38 se) and Foul Play's hand-tuned heuristic 0.088 (5.59 se). At a
tight gate the two evaluators are 0.020 apart (1.56 se) and at an open one
0.102 (5.62 se). A tight gate does not make a comparison conservative; it makes
it POWERLESS, because the search changes ~2 decisions of a 30-turn battle.

## `_look_further` WAS OPTIMISTIC, AND ITS DOCSTRING SAID THAT WAS FINE (2026-09-18)

`rl/search/matrix.py::_look_further` took a MAX over our replies with the
opponent PINNED to the column the root assigned it, and defended that in prose:
"it biases every row the same way and the root decision is an argmax over rows".
**It does not.** Rows differ in how many replies they have and how good the best
one is, so a max over k noisy leaf estimates inflates exactly the rows with the
most escape hatches — and those are the rows the search then overrides into.
Measured (RESULTS §24): depth 1 and depth 2 are indistinguishable at a tight
gate (−0.0007) and **−0.047 at 2.57 se apart once the gate is open**; opening
the gate costs depth-2 0.052 against depth-1's 0.006. A tight gate was
discarding the inflated rows; an open gate plays them.

Fixed by `depth2.opp_k` (default 1 = the old backup, bit-identical). Two more
holes closed with it, both found by writing the tests rather than by reading
the code: **a leaf the lookahead could not expand was re-embedded at
`turn + 1 + plies` and RE-SCORED**, so merely turning depth on moved the value
of leaves it never looked past (every depth-2 arm before 2026-09-18 carries
that artifact — `docs/CLEANUP.md` L4); and **a SWITCH column produced ZERO
grandchildren**, because repeating "switch N" at ply 2 is illegal and the raise
landed in a bare `continue`.

**The general lesson is about the prose, not the code.** A docstring that
asserts a bias is harmless is a claim, and this one was load-bearing for three
published numbers. State such claims as something checkable, or check them.

## A RUNNING BLOCK IMPORTS THE WORKING TREE (2026-09-18)

Each arm of an FP block is a FRESH PROCESS launched when its turn comes, so it
imports whatever is in `rl/` at that moment. Edit a module mid-block and the
later arms run a different program than the earlier ones. The queue scripts
freeze THEMSELVES (`mktemp` + re-exec) precisely because of this hazard and do
nothing about the Python.

It happened on 2026-09-18: the tree block launched at 10:45Z, TV finished, and
the session then edited `agent.py`, `matrix.py`, `ensemble_search.py` and
`ch3_fp_h2h.py` before TG/TQ/TGR launched. **That instance was provably
harmless** — the fixture in `tests/test_tree_decision_golden.py` run against
the pre-edit tree (`git archive <sha> rl tests | tar -x -C tmp`, then
`PYTHONPATH=tmp`) gave bit-identical actions, decision stats and pre-existing
counters on all three decide rules; only wall-clock `tree/ms_*` differed, and
the arms are ITERATION-bounded (`iters: 100`), so timing cannot change what is
searched.

Three things make this cheap to handle, and all three exist now: **(i)** every
arm's JSON has carried `launch_git_sha` since CH4 R1's G8 block, **(ii)** the
readouts read it and say when a block spans more than one commit, and
**(iii)** the golden fixture answers "did my edit change the search?" in a
second.

**And (i) was itself wrong until this was written.** `launch_git_sha` was read
AFTER the battles, so it recorded the tree state at COMPLETION under a name
that says the opposite — and SESSION_LOGS records the opposite belief in prose.
It surfaced because TV, launched 10:45Z, came back stamped with a commit made
at 11:40Z. Now read before the first battle, with `finish_git_sha` beside it;
arms written earlier carry a finish-time value under the launch name and the
readouts label them. **A provenance field nothing reads is a field nobody
notices is wrong.** Whether a spanning block should be REFUSED is still a maintainer
ruling (`docs/CLEANUP.md` L5).

**Also pinned by that fixture, and worth knowing on its own: the ENCODER
VERSION is part of the search.** The tree encodes every leaf, so under the
suite's default (`OBS_DIM` 612, flags unset) `visits` and `gumbel` pick a
DIFFERENT ACTION on the same fixture than under the arms' 828.

## BATTLES CAN STALL TO A 1000-TURN CAP, AND THE TIE IS A NON-WIN (2026-09-18)

`scripts/tie_and_stall_audit.py` over **143,500 banked battles**, written after a
sideways observation: the open-gate arms of RESULTS §24 have a battle-length
standard deviation **three times** their anchor's (37.6 against 11.0). That is
not systematic lengthening — the medians are within a turn of each other. It is
**one or two battles hitting a 1000-turn cap**, which is enough to move an sd
and nothing else.

**What the audit found.**

- Overall tie rate **0.0014**; the worst single arm **0.0110**.
- **51% of all ties are 1000-turn caps** — a genuine stall, not a close finish.
- The tie rate is a **SYMPTOM OF WEAKNESS**: corr(win rate, tie rate) = **−0.31**,
  and the weaker half of arms tie **3.5×** as often as the stronger half. It is
  not a hidden lever and chasing it would be chasing a proxy.

**Why it still matters.** Ties are NON-WINS under the locked protocol, so a
stall-prone arm gives away win rate mechanically. **Within a block** every arm
sits near 0.001 and the term is negligible — this does not touch any
within-block comparison this project has published. **Across blocks** the spread
reaches **0.011**, half the size of the effects being chased, and it points the
same way as the session offset: against the weaker arm. Cross-block win-rate
comparisons were already barred; this is a second, independent reason.

**What it does NOT say.** Nothing about the matrix vehicle, the gate, or depth —
the two long battles that started this live in open-gate arms, but greedy anchors
and old greedy arms hit the cap at similar rates (`ch5_r1_offsh/rs81` is 15 of
3000 on a plain greedy seat).

**AND THE BEHAVIOUR IS NOW EXAMINED — 103 OF THE 104 CAPPED BATTLES IN THE REPO**
(`scripts/stall_forensics.py`, RESULTS §28). **100 of the 103 are a switch loop**
— ~900–990 switches, essentially 100% strictly alternating between two slots —
and in **94 of them (91.3%) the opponent is immobilised on ≥80% of turns**,
usually one Pokémon FROZEN SOLID (gen-1 freeze is permanent without a fire move).
Our seat oscillates instead of attacking a helpless target: turn cap, tie,
non-win. **A thrown-away win.** Six are the same loop against an opponent that
COULD act, and three logs are incomplete (an arm relaunched mid-battle).

**THAT NUMBER IS A CORRECTION.** This entry and §28 first said "one bug, every
time" on the strength of SIX battles, because the forensics script re-read a
200–900 MB log once per battle and only one arm had ever been swept. One pass
over all tags turned a sample into an enumeration. **A claim about "every" needs
the denominator, and getting it was ten minutes of work.**

**THE MECHANISM IS THE LOCKED PROTOCOL'S OWN DETERMINISM.** Argmax in a state
that has stopped changing repeats forever. Training SAMPLES, so this never
happens there: it is *created* by evaluating deterministically, and it is
invisible to every statistic that does not look at turn counts. A plain greedy
seat with no search dials at all produces it 15 times in 3000 battles, so search
neither causes nor prevents it.

**The fix, and why it is not applied.** `rl/common/loop_breaker.py` — on the
fourth occurrence of an identical (observation, action) pair inside one battle,
take the next-best legal action, escalating a rank per escape so a cycle of any
period unwinds. It stays DETERMINISTIC (a function of the episode's history, so
a replay plays the same moves) and it **cannot change a single non-looping
battle**, which is pinned by a test. But it is a change to the POLICY FORM and
the locked protocol names the policy, so **it is wired nowhere and needs a
maintainer ruling.** LADDER R5 never hit the bug (max 121 turns, zero ties) —
human opponents do not freeze-lock and then sit — so the risk is latent.

## THE REALIZED OVERRIDE RATE ALSO DRIFTS ACROSS SESSIONS (2026-09-18)

The standing rule is **match on the realized override rate, not on the delta**
(§22: the same arm reads −0.0007 or −0.053 depending on that alone). This is the
next layer down: **the realized rate itself is not reproducible across sessions
at a fixed delta.**

Measured on the same configuration — dose M, `margin_delta` 0.05, open gate,
ungated, the same three checkpoints:

| arm | session | n | override | win |
|---|---|---|---|---|
| CN1 | 2026-09-17 | 1500 | **0.1933** | 0.5627 |
| D1O | 2026-09-18 | 1000 | **0.1703** | 0.5510 |

**The same knob, a different realized rate, 0.023 apart** — the same order as the
~0.02 win-rate session offset, and for a related reason: the override rate is a
property of the POSITIONS the opponent leads you into, and Foul Play at 20 ms is
not the same opponent twice.

**What it breaks.** `scripts/backup_gate_pin.py` matched B2R to the **banked**
0.193 because the control had not run yet, so B2R lands ~0.027 from D1O's
in-session 0.170 — inside the ±0.03 gate, and closer to the edge than the design
intended. The pin was applied before any phase-R number existed and **must not be
re-pinned now that a win rate is visible**: a selection rule that reads only
override rates stops being one the moment it is re-run after seeing an outcome.

**The fix for the next block, and it is free: RUN THE CONTROL FIRST.** Put the
control arm at the head of phase R, then pin the treatment's delta to the
control's REALIZED in-session rate rather than to a banked one. It costs nothing
but an ordering, and it removes a whole layer of drift from the matching.

**A banked rate is a starting guess, never a target.** Every block that matches
on a rate should say which session its target came from.

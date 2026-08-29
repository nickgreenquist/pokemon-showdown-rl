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

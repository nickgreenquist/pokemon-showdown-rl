# Handoff — LADDER R3 IS RUNNING AND SELF-HEALING. Written 2026-08-28 11:41 EDT
# at n=183/200. Your job is to (1) re-arm a monitor, (2) read R3 out when it
# stops. Everything is committed; the tree is clean. 16 commits are UNPUSHED
# and the maintainer must be asked before any push.

## 0. FIRST: DO NOT KILL THE RUN

Killing mid-battle **forfeits a live rated game against a human** and
contaminates the rating R3 exists to measure. It cannot be undone. The run is
`nohup`-detached and survives any session ending.

    pgrep -fl "ladder_supervise|ladder_watchdog|scripts/ladder.py"

Expect three processes: supervisor `34153`, watchdog `34155`, and a runner
whose pid changes on every relaunch. `caffeinate` is tied to the supervisor.

## 1. RE-ARM THE MONITOR (the only thing that died with the last session)

The supervisor, watchdog and caffeinate are detached and unaffected. The
hourly progress Monitor was session-bound. Re-arm it:

    Monitor: /private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/cc04e2e6-2af8-47f5-81cd-c15d924eaa93/scratchpad/r3_watch.sh 34153

That scratchpad may be gone in a new session. If so, just poll instead — one
line, no machinery needed:

    python - <<'PY'
    import json,statistics
    r=[json.loads(l) for l in open('results/ladder/R3S.battles.jsonl')]
    n=len(r); w=sum(1 for x in r if x['outcome']=='win')
    d=[b['finished_at']-a['finished_at'] for a,b in zip(r,r[1:])]
    print(f"n={n}/200 {w}-{n-w}={w/n:.3f} | median s/battle {statistics.median(d[-30:]):.0f}")
    PY

**Read `s/battle` as a MEDIAN, never a mean** — outage gaps drag the mean and
inflate the ETA by hours. And never `wall_clock_sec / battles_total`; those
have different scopes and that division produced R1's wrong "217".

## 2. HOW IT SELF-HEALS, so you do not "fix" a working system

**poke-env NEVER RECONNECTS.** `ps_client.listen()` catches
`ConnectionClosedError`, logs it, and RETURNS. The process then stays ALIVE
with no TCP connection, hung on `ladder(1)` at 0.0% CPU. Two scripts handle it:

- `scripts/ladder_supervise.sh` relaunches on exit with the same CUMULATIVE
  `--battles 200`. Progress-checked against the JSONL; 12 no-progress attempts
  then abort; 300 s backoff.
- `scripts/ladder_watchdog.sh` kills a HUNG runner so the supervisor can
  relaunch. **It tests the SOCKET, not the clock** — a turn-1000 auto-tie is a
  real game that runs for hours and HAS a socket, so killing on a stall alone
  would forfeit it.

Four outages have been healed unattended. **The cause is a flapping LOCAL
link**, not Showdown: keepalive timeouts, `[Errno 60]` TCP read timeouts and
an `[Errno 8]` DNS failure, each on a link `curl` finds healthy seconds later.

**`lsof -p X -i...` NEEDS `-a`** or it ORs the selections and returns other
processes' sockets. It fails in the REASSURING direction and cost 35 minutes.
**macOS `ps` has no `etimes`** (Linux-only); it prints the keyword list instead
of erroring, which silently broke a numeric comparison.

## 3. WHEN IT STOPS — the exact sequence

It stops itself: at n=200 the runner polls and evaluates `rd <= 40 AND n >=
200`. R1 hit rd 26.6 at n=200, so it should fire immediately. The supervisor
sees `STOPPING RULE MET` and stops relaunching.

**(a) BACK UP FIRST. Ladder data is UNREPEATABLE and gitignored.**

    bash scripts/backup_ladder.sh

**(b) Then the readout. PASS EVERY FLAG** — all three readout scripts default
to R1's paths AND R1's name, and run bare they emit a normal-looking readout
OF R1:

    python scripts/ladder_readout.py --jsonl results/ladder/R3S.battles.jsonl --replays results/ladder/replays_r3 --name nickgen1rbrlbot2 --label R3 --compare-jsonl results/ladder/L2.battles.jsonl --out LADDER_R3_READOUT.md

`--label R3` is not cosmetic: it gates R3's two owed disclosures.

## 4. WHAT THE READOUT MUST SAY — non-negotiable

- **R3 IS STANDALONE DESCRIPTIVE. No R1-vs-R3 delta may be quoted as an
  effect, in either direction.** Seven confounds moved at once. The 76-Glicko
  bar is REFUSED. See `ladder_r3.yaml: comparison_ruling` and its
  `barred_language` list.
- **DISCLOSURE 1 — BLIND BREACH AT BATTLE 10.** A crash-resume printed the
  live rating into the log (GXE 56.4, Glicko 1550 +/- 85, Elo 1082). It does
  NOT void the read — the stopping rule is mechanical and cannot fire before
  n=200, and no stopping decision was taken on it — but it happened and must
  be stated.
- **DISCLOSURE 2 — REAL DISCONNECTIONS HAPPENED**, so a `timeout_midgame` in
  R3 may be OUR socket rather than a human abandoning. **Do not pool with R1's
  six.** Count supervisor attempts from `R3S.supervisor.log`.
- **R1's PUBLISHED BAND CELLS ARE WRONG AND THE PRE-REG PINS THE WRONG ONES.**
  They were built from the JSONL's advisory column and sum to 194/200. BI-4
  rebuilt from the replays (200/200, asserted). **The only licensed comparison,
  [1300,1400), is 0.319 — NOT the 0.340 the pre-reg cites.** `>=1400` is
  32, 0.375, not 28, 0.321. Aggregate implied true Elo 1214, not 1232. The
  config carries `bands_CORRECTED_2026_08_28` beside the superseded line.
- **NEVER** set R3's number beside the 12M cell 0.79283, read it as vs-SH, or
  quote "+N Elo from search". **Name the budget** on any FP number: FP@20.
- R3's object has **ONE of three anchors** (FP@20 only). Say so in those words.

## 5. AFTER THE READOUT — the ordered plan

Full derivation in SESSION_LOGS 2026-08-28 (02:30Z and 03:10Z). Short form:

0. **Rescore search@M on s81/s82 at n=3000** (~4.9 h, eval). The ONLY thing
   gating R2 — it decides whether R2's arms are scored greedy or searched.
   **Read it for s81, not s82** (s82 is the known-bad lane at 5.2 se).
1. **R2 = BATCH.** 3 new 50M lanes, s80/81/82 as the free control. PRIMARY read
   is STRENGTH against the 0.0717 bar. `sigma_seed` is a DESCRIPTIVE secondary
   carrying its (2,2)-df disclosure: **batch is NOT the instrument fix** —
   that framing was retracted, because detecting a sigma_seed change at k=3
   needs a 4.4x cut (F(2,2) crit 19.0).
2. **lambda** = a CONFIG choice on the explained-variance diagnostic, applied
   to BOTH arms. Not an arm; testing it needs training and would compete with
   batch. Check EV is even logged — it is not in the locked metric names.
3. **THEN** decide CURVE vs CREDITED WIN RATE. A policy change. It gates LANES
   AND SCALE, **not** batch. Note **k ~ 24**: the +0.025 credit floor needs 24
   lanes, so C2 cannot credit a +0.02-0.05 lever at any realistic k.
4. Descriptive, around the training: **D4's anchors, AMENDED to BC-clone h2h on
   ALL THREE lanes** (a free replication of the search-equalisation test),
   cross-play, one R2 arm scored both ways. Then `CLEANUP.md`.

**Live hypothesis worth knowing:** search may EQUALISE the lanes — off FP@20
the search-minus-greedy gain is monotone in lane weakness 3/3
(+0.051/+0.104/+0.148), collapsing a 0.123 spread to 0.026. **2 df, p~0.06,
CI contains greedy's 0.0617 — HYPOTHESIS, not finding.** Scoring levers under
search is a SCOPE CHANGE: the mechanism that buys the variance masks
value-head gains.

## 6. ACCOUNT RULING (2026-08-28) — affects R4, not R3

**All ITERATION runs share ONE account: `nickgen1rbrlbot`** (no suffix — a
suffix advertises a fleet). `nickgen1rbrlbot2` retires after R3. A fresh
account for a possible FINAL long run is **deferred, not decided**; if it
happens it is the third account and the **courtesy note to PS staff falls due
there**. Two gotchas for R4: `.env` currently holds **bot2's** credentials, and
**VOID (f) inverts** — on a persistent seat an existing rating is EXPECTED and
its absence is the alarm.

## 7. DO NOT

- Do not kill the run, or "fix" the supervisor/watchdog while a runner is live.
  Editing a bash script that bash is currently executing can corrupt it — swap
  only in a verified runner-free window.
- Do not open the profile, replay list or board before n=200 (G-BLIND).
- Do not push without asking. 16 commits are waiting.
- Do not run the readout scripts bare.

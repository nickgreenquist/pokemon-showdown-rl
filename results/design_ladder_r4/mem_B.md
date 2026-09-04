# mem_B — LADDER R4, OPERATIONS AND COST (designer B, 2026-09-04)

Object/lane ruled (BRIEF:17-22): greedy, s112,
`runs/showdown_sp_100m_s112/ckpt_100000008.pt`, sha `2ec16fbf85a9046d…` (full in
`configs/eval/ch5_100m_offfp.yaml:26`). I recommend; decisions get a
`<< MAINTAINER n >>`. Q2/Q5 are memo A's, touched only where they cost time.

## 0. Three disagreements with the brief

1. **"R3's 17 h was search-dominated" is wrong and it moves the budget.** R3's
   own arithmetic put our compute at ~1% — 41.3 decisions × 64.84 ms = 2.7 s of
   ~290 s (`configs/eval/ladder_r3.yaml:243-249`). From
   `results/ladder/R3S.battles.jsonl` `finished_at` deltas, R3's **median
   s/battle was 218.0 (211.5 excl. gaps >900 s), BELOW R1's greedy 229.5.** The
   search seat was not slower per battle. Greedy buys wall clock only through
   TURNS — ~1–2 h over 200 battles, not a halving.
2. **R3's realized span was 15.34 h, not 17**, and **2.87 h of it was five gaps
   >900 s** — outage, not play. Productive core ≈ 12.5 h.
3. **R1's "176 overnight" is not a rate.** R1's full 200-battle span was
   **13.63 h** at 246.5 s/battle (`L2.battles.jsonl`); 176 overnight is ~12 h of
   that same rate — consistent with the projection below, not faster.

## 1. Wall-clock projection for a GREEDY object

**Turns.** s112 greedy off FP@20: **28.403 mean turns** (`results/ch5_100m/
t112.json`, n=3000). Two (proxy → ladder) ratios exist and disagree: R1
25.95/27.44 = **0.946** (`ladder_r3.yaml:253-255`); R3 28.59/36.824 = **0.776**
— the 0.944 calibration predicted 34.8 turns and **overshot 18%**
(`ladder_r3.yaml:873` vs `readouts/LADDER_R3_READOUT.md:169`). Carry both:
projected human turns **22.0 – 26.9**.

| method | s/battle | ×199 intervals |
|---|---|---|
| R1 OLS `114.5 + 4.85·turns` (`ladder_r3.yaml:870`), 22.0–26.9 turns | 221–245 | **12.2–13.5 h** |
| R3 realized median excl. gaps | 211.5 | 11.7 h |
| R1 realized whole-run mean | 246.5 | 13.6 h |
| R3 realized whole-run mean (outages in) | 277.5 | 15.3 h |

**RECOMMEND plan 12–16 h, budget 17 h.** The spread between the last two rows is
the outage tail, and that tail is the honest uncertainty: R1 lost 0.41 h to one
gap, R3 lost 2.87 h to five. **Hard ceiling if rd binds and the run reaches
`max_battles_total: 300`: 299 × ~235 s ≈ 19.5 h + outage ≈ 22 h.** Put that in
the pre-reg rather than discover it at hour 18.

**Drivers.** (a) The ~114.5 s intercept — queue, matchmaking, preview, teardown —
is ~50% of every battle and invariant to policy: 6.4 h no object choice touches.
(b) The human's clock, 4.85 s/turn ≈ 116 s. (c) **Our compute <0.1%**: one greedy
forward pass is a strict subset of R1's 4-lane ensemble at **6.74 ms**
(`results/ladder/L2.report.json`) — ~30 decisions ≈ 0.2 s of ~230 s. (d) Outages,
3–19% of span.

**Two tail changes.** DROP R3's +1–2 h auto-tie tail: greedy took **1/0/0
auto-ties per 1000** vs search's 4/5/8 (`ladder_r3.yaml:270-271`) — ~0.07 games
at n=200, and no ladder run has come near the ceiling (R1 max 61 turns, R3 max
80). REPLACE with the **measured outage tail, 0–3 h.** Also off the programme
total: R3's ~2.7 h of post-ladder anchor buying (`ladder_r3.yaml:990`), since
R4's battery already exists (BRIEF:31-35). **Cost of the Q6 re-score option:** a
fresh off-FP@20 n=3000 on s112 is **1.29 h** agent-side (`t112.json`, 4651.8 s at
1.55 s/battle) — cost is no argument either way on Q2; decide it on validity.

## 2. The arms block `ladder.py` needs — verified

`_build_policy`'s greedy branch (`scripts/ladder.py:365-372`) reads exactly
`arm["kind"]`, `arm["lane"]`, and `checkpoints[lane]["path"]`/`["sha256"]` (sha
asserted before load, `:340-348`); `display_name` is read separately by
`_resolve_display_name` (`:646, :262`). **Nothing else is required or read** —
`dose`, `evaluator_lanes`, `checkpoint_seed` are search-only (`:386-405`), and a
stray key is silently ignored.

```yaml
checkpoints:
  s112: {path: runs/showdown_sp_100m_s112/ckpt_100000008.pt, sha256: 2ec16fbf85a9046d360328e50cdee5c732d8529599aafa2215a2a56128abcbb3}
arms:
  R4G: {kind: greedy, lane: s112, display_name: nickgen1rbrlbot3}
primary_arm: R4G
```

**Stamped provenance for greedy is exactly six keys** — `kind`, `obs_dim`,
`encoder_v2`, `encoder_ids`, `lane`, `sha256` (`:358-369`); no `dose`. RECOMMEND
the VOID (e) analogue assert that **key set exactly**, not a subset: a `dose`
key means a search arm was pasted in and half-edited.

Also required — runner: `save_replays` (`:695`; obligation (i) needs it ON),
`pacing` (`:645`), `max_battles_total` (`:674`), `stopping_rule` (`:758`).
Tests (`tests/test_ladder.py`, globbing `configs/eval/ladder_*.yaml` at `:48`):
`glicko_rd_max == 40` and `min_battles == 200` (`:574-576`, **hardcoded**),
`max_battles_total > 200` (`:578`), `set_pool_pin` with both shas (`:581-600`),
an `instruments:` block whose paths all exist (`:387-400`), `display_name`
containing "bot" (`:539`), `"Status: RATIFIED"` present and no markers (`:549-561`).

**VOID (c) still binds, for a different reason.** R3's argument was the search
determinizer (`ladder_r3.yaml:623-627`); greedy has none. But
`TestSetPoolIntegrity` exists because **the ENCODER's set-pool copy** feeds
`embed_battle` (`tests/test_ladder.py:404-412`) — drift means our features
describe a set pool the server is not using. Carry the pin and the upstream
re-check; restate the reason instead of copying R3's sentence.

**The decision-ms tell INVERTS.** R3's LG-4 asserted `mean_decision_ms > 30` to
prove search was ON (`ladder_r3.yaml:921`); R4 must assert **< 20** — the mirror
failure is laddering something heavier than the pre-registered object. Expect
**2–8 ms** (strictly under R1's 4-lane 6.74). **Calibrate the band from the local
smoke, don't guess it here** — the smoke stamps `mean_decision_ms` free
(`ladder.py:861-863, 880-882`).

**Paths.** `results_dir` is decorative, `--out-dir` decides (`ladder_r3.yaml:802-806`)
and the supervisor hardcodes `results/ladder` (`ladder_supervise.sh:66`). Keep R4
under that root — `backup_ladder.sh` takes it wholesale (`:26, :30`), so a separate
root leaves an unrepeatable measurement with one copy. Files `R4G.battles.jsonl` /
`.report.json` / `.run.log`; `save_replays: results/ladder/replays_r4`.

## 3. Stall / deadlock / disconnect watch for a greedy seat

**Unchanged and must stay so.** The kill test is SOCKET ABSENCE, never the clock
(`ladder_watchdog.sh:14-22`) — killing a socket-up seat forfeits a live rated
game, unrecoverable (`ladder_r3.yaml:312-318`). Keep `max_concurrent_battles=2`
(`ladder.py:487`): the poke-env deadlock is generic to
`Player._battle_count_queue`, not to search (`ladder_r3.yaml:663-668`), and
BI-5's observed value is the real claim (R3 stamped
`max_concurrent_live_battles: 1`). Keep the ping budget 60/120/60
(`ladder.py:461-463`) — R3's two keepalive drops in 40 min were link-level on a
link curl found healthy (`:452-454`). Keep `start_timer: true` (CLAUDE.md
orphaned-room rule).

**What changes with greedy.** BI-6's room-churn exposure falls away with the
auto-tie rate, and the `age > 240 s` startup guard (`ladder_watchdog.sh:60`) gets
more conservative — greedy never imports `rl.search.agent` or the poke-engine
bridge (`ladder.py:387-388` not executed). **Leave 240 anyway**; its failure mode
is an infinite self-kill loop. **Keep `STALL=900`** — the temptation with a
~25-turn object is to shorten it, but the slow path never kills a socket-up seat
(`ladder_watchdog.sh:80-82`), it only logs, so shortening buys nothing while a
clock-based kill reintroduces the risk the socket test removed. **One addition,
observation-only (BI-R4-3):** at 2×STALL with the socket UP, emit a distinct
escalation line — for a ~230 s object that state has no explanation but
matchmaking famine (~93 active players/day, `ladder_r3.yaml:981`), and a morning
log-read should tell it from a long game without reconstruction. No kill-path
change. **Carried, unfixed:** a relaunch that comes up with NO established socket
must WAIT, not be hammered — the server holds the session after a kill
(SESSION_LOGS 2026-08-28, "ONE THING REMAINS UNEXPLAINED"); the supervisor's
300 s no-progress back-off (`ladder_supervise.sh:84`) is that, do not lower it.

## 4. Courtesy note (D2's binding trigger)

D2 verbatim: *"A THIRD RATED ACCOUNT — any ladder run after R3 — REQUIRES A
COURTESY NOTE TO PS STAFF BEFORE LAUNCH"* (`ladder_r3.yaml:1013`). R4 is #3.
**Sending it is the maintainer's act** (BRIEF:62).

**Recipient.** I cannot verify from this repo which channel PS staff currently
prefer, and `prior_work/README.md`'s check-before-citing rule applies. By
auditability: (a) the **`Help` room** on play.pokemonshowdown.com — staff-
attended, public, fast, leaves a public record; (b) a **PM to a Global Staff
member** from `/staff` — conventional, not archived by us; (c) the **Smogon
forums** PS subforum — durable, slow; (d) the **PS! Discord** dev/staff channel.
**RECOMMEND (a) then (b):** ask in Help who to tell, then PM them. Confirm the
channel on the site before sending; do not send blind off this list. **Archive it:**
the note is a pre-registered gate and `results/` is gitignored, so paste the sent
text, timestamp, channel and recipient handle into a **tracked**
`readouts/LADDER_R4_COURTESY_NOTE.md`. **Send ≥24 h before launch**, timestamp
recorded as a gate, and **pre-register that a non-reply is NOT a block** — it is a
courtesy, not a permission request, and without that clause a silent channel
strands the run indefinitely, which is the real failure mode. If staff object:
stop at the next battle boundary, do not argue (`ladder_r3.yaml:757-759`), record it.

**Draft (maintainer edits freely; deliberately does not ask permission — an
unanswered request reads worse than an unanswered notice):**

> Hi — a heads-up rather than a request, in case it's useful to know.
>
> I run a small reinforcement-learning research project on Gen 1 random battles.
> It has played two short rated runs on the ladder, 200 games each in August,
> under `nickgen1rbrlbot` and `nickgen1rbrlbot2`. I'm about to do one more:
> about 200 rated `gen1randombattle` games over a single night, under
> `nickgen1rbrlbot3`.
>
> How it runs: one account, one game at a time, never concurrent; ~5 seconds
> between games; a hard cap of 300 games; no chat; timer on. It stops on its own
> at 200 games. It isn't chasing a ladder placement — the result is published as
> a research measurement, not a leaderboard claim.
>
> If you'd rather I didn't, or want it run differently, say so and I'll stop —
> no argument. Happy to answer anything about it.

Discloses: research bot, footprint and rate, account name, **both prior
accounts** (link volunteered, not discovered), duration, cap, standing stop
offer. `<< MAINTAINER 1 >>`

## 5. Account: registration and naming

**RECOMMEND `nickgen1rbrlbot3`.** Userid 16 ≤ 18 (`ladder.py:80`); contains "bot"
as the suite requires (`tests/test_ladder.py:539`). The linked stem was ruled on
for R3 and transparency is the reason (`ladder_r3.yaml:751-755`); **the courtesy
note now states the link to staff explicitly, which is stronger than any naming
convention.** Names are safe in code — `_resolve_display_name` makes the pre-reg
authoritative and SystemExits on a disagreeing `PS_USERNAME` (`ladder.py:230-283`),
which is why R3 ruled near-identical names fine forever (`ladder_r3.yaml:770-773`).

Fresh, not reused: bot2 carries R3's 208 rated games into R4's number. VOID (d)
evidence to capture as R3 did (`ladder_r3.yaml:762-765`): profile HTTP 200,
`registertime` set, `ratings: {}`. **Registration is by hand, by the maintainer**
— poke-env cannot register (`ladder.py:16-19`). `<< MAINTAINER 2 >>`

**The `.env` trap, and it is a launch gate.** `.env` holds
`PS_USERNAME=nickgen1rbrlbot2` (`ladder_r3.yaml:795-798`). Against a bot3 arm
`_resolve_display_name` aborts (`ladder.py:273`) — correct, but under the
supervisor it surfaces as a no-progress attempt after a torch import at whatever
hour it is. Update `.env` first; **the local smoke is the check** (it resolves the
display name on the same path, `:646`, before needing a password).

## 6. Supervisor invocation and resume-safety

`ladder_supervise.sh <arm> <target> <prereg>` — the pre-reg is a required 3rd arg
since 2026-08-29 (`:32-34`, REPO_CLEANUP item 9) precisely so an R4 run cannot
execute under R3's rules. Two detached processes, in this order (handed over as
two separate one-line `<command>` blocks per CLAUDE.md):

```
source .env && nohup scripts/ladder_supervise.sh R4G 200 configs/eval/ladder_r4.yaml >> results/ladder/R4G.supervisor.log 2>&1 &
```
```
nohup scripts/ladder_watchdog.sh R4G 900 >> results/ladder/R4G.watchdog.log 2>&1 &
```

**Resume-safety, improved by greedy.** `--battles` is CUMULATIVE
(`ladder.py:877-878`); the JSONL is the truth (`:667-672`); a death costs ≤1
battle. Proven under load: **10 runner launches, 8 SIGKILLs of a socketless
runner, all healed unattended** (`readouts/LADDER_R3_READOUT.md:127-135`). **New
for R4:** greedy `act` ignores `battle_index`/`decision_index` entirely
(`ladder.py:371-372`), so R3's resume wrinkle — search's RNG stream restarting,
battle indices repeating (`ladder_r3.yaml:502-505`) — **does not apply.** Every
decision is a pure function of the observation across any number of resumes; one
fewer disclosure, and it belongs in the readout. Keep `MAX_NOPROGRESS=12`
(~60 min, `ladder_supervise.sh:39-44`) and `PYTHONUNBUFFERED=1` (`:64` — LG-9
cannot read buffered startup lines).

## 7. Stopping-rule enforcement

Mechanical and in code (`ladder.py:571-622`), polled only at
`len(records) >= min_battles` and every `board_poll_every_battles` after
(`:808-817`). **RECOMMEND carrying `rd <= 40 AND n >= 200` unchanged** (Q1). Two
ops arguments beyond memo A's: `tests/test_ladder.py:574-576` **hardcodes 40/200**
across all ladder pre-regs, so changing n edits a test that pins an invariant;
and n=200 is what both the 12–16 h budget and the etiquette magnitude argument
(~600 games over three accounts vs ~93 players/day) rest on. Keep
`max_battles_total: 300` (`ladder.py:674-677` clamps).

**n is a floor on LOGGED games and the profile can exceed it.** R3's profile read
106-102 (208 rated) against a JSONL of 106-94 (200): the 8 extra losses were
battles in flight when our socket died, scored by the server, never logged
(`readouts/LADDER_R3_READOUT.md:137`). `stopping_rule_met` takes n from
`len(records)` (`ladder.py:811`) — our file — so outage losses do **not**
accelerate the stop. Conservative; state it so the mismatch is expected.

**G-BLIND.** R3's battle-10 breach is closed in code: the resume branch
suppresses values (`ladder.py:718-723`). The remaining leak is the per-battle
running W/L print (`:800-803`) — unavoidable, disclosed, not the primary read.
Do not open profile, replay list or board before n=200. Carry the
profile-unreachable procedure verbatim (`ladder_r3.yaml:375-386`): hand-pull, and
a hand pull showing rd ≤ 40 at n ≥ 200 **satisfies the rule.**

## 8. Backup / mirror

`backup_ladder.sh` copies `results/ladder` wholesale (`:26, :30`), so R4 is
mirrored and archived with no change. **The VERIFICATION is not:** `RUNS` is a
hardcoded list (`:40`) and without `"R4G:replays_r4"` the "OK — mirror matches
live" line says nothing about R4 — the exact BI-3 failure recorded at `:32-39`.
Third copy is the tracked readout markdown (`:14-17`). Run the backup **once
mid-run** as well as at the end; R3 ran 15 h with an appending JSONL and no
mid-run snapshot.

## 9. Launch checklist and who runs what

CLAUDE.md rule 4: eval-kind, agent-side if (i) detached, (ii) resume-safe,
(iii) rate-readable. All three, concretely: **(i)** supervisor and watchdog are
`nohup`'d, outside the agent's process tree — the agent dying touches neither;
**(ii)** cumulative `--battles` + JSONL truth + supervisor relaunch, over 10
launches in R3; **(iii)** the rate is the median `finished_at` delta against two
completed comparable arms — R1 greedy **229.5 s**, R3 search **211.5 s** — so
"10× off means stalled" has real anchors.

**Three items are the maintainer's regardless**, being non-compute: sending the
note (BRIEF:62), registering the account (`ladder.py:16`), the credentials.
**RECOMMEND the maintainer sends, registers, updates `.env`, and runs the launch**
— LG-9 requires reading the startup lines and aborting during the first 5 s sleep
(`ladder_r3.yaml:923`), i.e. a human at the terminal for ~90 s. **The agent then
owns** babysitting (CPU-delta and socket checks), mid-run backup, the readout, the
docs commit. **Shared standing duty:** moderator contact → stop at the next battle
boundary, do not argue (`ladder_r3.yaml:757-759`). `<< MAINTAINER 4 >>`

**Gates, in order.** LG-1 note SENT and archived with timestamp. LG-2 account
registered; profile 200, `registertime` set, `ratings: {}`. LG-3 `.env` updated to
bot3. LG-4 `pytest tests/test_ladder.py` green incl. `TestSetPoolIntegrity`.
LG-5 VOID (c) upstream half re-run within 24 h. LG-6 `--local-smoke` ≥2 battles
on R4G asserting kind=greedy, lane=s112, the sha, obs_dim 828, **no `dose` key in
`policy`**, `mean_decision_ms < 20` (needs the local server up,
`ladder.py:650-656`). LG-7 clean tree, docs committed, **local server stopped**
and nothing else on the box (`ladder_r3.yaml:922`; greedy runs at
`torch.set_num_threads(1)`, `ladder.py:351`, but a live rated game has a timer).
LG-8 BI-R4-1..4 landed or waived in writing with fallbacks. LG-9 read the startup
lines: kind=greedy, the s112 sha, the userid character-by-character, and
**"starting rating: none yet"** — an existing rating means the wrong account.
`<< MAINTAINER 5 >>`

## 10. Realized-cost accounting for the readout — new obligation (vii)

1. **s/battle three ways** from `finished_at` deltas: whole-run mean, median,
   median excluding gaps >900 s (R3: 277.5 / 218.0 / 211.5). **Never
   `wall_clock_sec / battles_total`** (`ladder_r3.yaml:550-557`).
2. **Outage ledger, first-class:** supervisor launches
   (`grep "SUPERVISOR: attempt" R4G.run.log`), watchdog kills and their battle
   indices (`R4G.watchdog.log`), count of gaps >900 s, their sum in hours and as
   a % of span. R3: 10 / 8 / 5 / 2.87 h / 19%.
3. **THE RECONCILE ITEM** (BRIEF:51-53), printed as an equation: profile `w+l+t`
   vs JSONL line count, difference attributed. R3's wins matched exactly; the 8
   extra server-side losses were our own outages. **The rating includes them, the
   descriptive rates do not** — name both denominators, never pool silently.
4. **Turn calibration:** realized mean turns beside 28.403 off FP@20
   (`t112.json`) and beside both ratios (0.946 R1, 0.776 R3). Third
   (proxy, ladder) pair and **the first greedy one at 100M** — what makes the next
   projection better than this one.
5. **Compute share:** `mean_decision_ms × decisions / sec_per_battle`, expected
   <0.1% — retires "search costs games per hour" as a live consideration in
   either direction.

## 11. Build items and maintainer markers

- **BI-R4-1 (blocking, 1 line).** `backup_ladder.sh:40` — add
  `"R4G:replays_r4"`. Fallback: verify counts by hand and say so.
- **BI-R4-2 (readout, not blocking).** `ladder_readout.py` hardcodes R1's cells
  (`R1_BANDS`/`R1_CATS`, `:70-73`) and takes one `--compare-jsonl` (`:116`); R4
  has TWO priors. Minimum: run with
  `--compare-jsonl results/ladder/R3S.battles.jsonl` and add R3's cells by hand,
  saying so. Better: parameterise. All five flags are required (`:108-123`).
- **BI-R4-3 (ops, not blocking).** Watchdog 2×STALL escalation line, socket up.
- **BI-R4-4 (BLOCKING, a trap).** `tests/test_ladder.py:48` globs
  `configs/eval/ladder_*.yaml`; `:549-561` asserts markers **ABSENT** and
  `"Status: RATIFIED"` **PRESENT**. **A draft `configs/eval/ladder_r4.yaml` with
  `<< MAINTAINER n >>` markers turns the suite red**, against CLAUDE.md's "end
  every session green". Draft at `results/design_ladder_r4/ladder_r4.draft.yaml`
  and `git mv` it into `configs/eval/` in the ratifying commit — which also makes
  the marker test fire at exactly the right moment.

`<< MAINTAINER 1 >>` courtesy note: text, channel, send timestamp, and the
non-reply-is-not-a-block clause. `<< MAINTAINER 2 >>` account: `nickgen1rbrlbot3`
(linked stem carried) vs a distinct name now the note discloses the link anyway;
who registers. `<< MAINTAINER 3 >>` schedule: ONE CONTINUOUS RUN to n=200 (D1
precedent), plan 12–16 h, budget 17 h, ceiling ~22 h at `max_battles_total: 300`.
`<< MAINTAINER 4 >>` ownership: maintainer launches, agent babysits.
`<< MAINTAINER 5 >>` BI-R4-1..4 landed or waived in writing with fallbacks.

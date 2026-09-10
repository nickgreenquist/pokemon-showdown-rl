# Engine port — state of play, 2026-09-10 ~02:00Z

Written so a session with no memory of today can pick this up. Durable record
is `docs/engine_port/NOTES.md` (incidents and gate numbers) and the git log;
this file is only "what is in flight and what was just decided".

## Running right now (all detached; survives any session change)

| what | where | eta |
|---|---|---|
| A-1 engine arm, 3 lanes x 12M, seeds 66/75/83, k=8 | `<worktree>/runs/engine_a1_s*` | ALL THREE PAST THE 12M RUNG |
| the gate chain (kills at the rung, then T-1(c), then A-1 descriptive evals) | `scripts/engine_gates.sh`, log `<worktree>/logs/engine_gates.log` | step 6 polls every 600 s |
| post-lane queue: teardown, `pytest tests/`, both A/B variants, readout (`scripts/engine_post_lane_queue.sh`) | `logs/post_lane_queue.log` | after the chain, **A/B held** |

**THE A/B IS HELD BEHIND A SENTINEL.** The maintainer asked (2026-09-10) to
close their own work and Chrome before anything measures wall clock, and no
check inside the script can see either. Teardown and `pytest` run unattended;
the A/B waits for `touch <repo>/.ab_go` and consumes the sentinel when it fires.

The lanes overran to 12.5-13M because step 6 polls every 600 s and waits for
the SLOWEST lane. Harmless: `rung_ckpt` takes the first `ckpt_0120*.pt`, so the
read is at 12M regardless and the extra steps are only wasted compute.

The A-1 lanes run out of the WORKTREE
(`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-engine`), so its
`runs/`, `results/` and `logs/` are the live ones until they finish. **The env
needs nothing** — checked 2026-09-10, `pkmn-engine-port` already resolves `rl`
to MAIN and `pkmn_gen1` to site-packages, so teardown is only: move those three
directories home, then `git worktree remove`. That runs itself as step 1 of
`scripts/engine_post_lane_queue.sh`.

**THE TEARDOWN HAZARD, WHICH NEARLY BIT TWICE.** `runs/`, `results/`, `logs/`
and `data/` are ALL gitignored, and `git worktree remove` treats a worktree
carrying only ignored files as CLEAN — it deletes them silently. First near
miss: migrating directory-by-directory would have stranded `results/t1`'s
leg_a/leg_b, because that directory exists in BOTH trees. Second, and worse:
`data/` was not on the migrate list at all, and it holds the 480 MB
5,000,000-pair team bank whose sha256 every gate record cites (41 min to
regenerate, different sha at the end). The list is no longer the safety — every
gitignored path git reports in the worktree must now be either migrated or
provably rebuildable, and anything else BLOCKS the removal.

## Overnight ops — what may and may not be killed

**Chrome may be killed freely if it is open overnight.** Nothing in this
project's pipeline uses it.

**Kill NOTHING else.** In particular do not touch `caffeinate` — someone closed
the maintainer's caffeinate terminal once already and the box then slept through
the night, which silently invalidated every wall-clock number taken across it
(2026-09-09; CPU-time deltas were the only honest progress read that day). The
gate chain, the A-1 lanes, the post-lane queue and the Showdown server are all
load-bearing and detached. If something looks stuck, read
`logs/engine_gates.log` and check a CPU-TIME DELTA (`ps -o time=` twice, 15 s
apart) before concluding anything — a lane can sit ALIVE AT ZERO CPU and every
`pgrep` check passes forever.

## Gate state

* PASS: B-0, B-1, P-1, P-2, P-3, P-4, **D-1** (n=10,000/matchup/simulator).
* **T-1(d) CREDITED** — the headline is that the Showdown server drops to
  **0.043 cores** while three engine lanes train, against 1.08 cores/lane on
  the Node path. Cores/lane 1.93 -> 1.02.
* T-1(a) 6,056 battles/s (= ~740k decisions/s) and T-1(b) 22,318 steps/s at
  K=256 are BELOW their bands; both bands were mis-specified and are corrected
  in the plan. The real T-1(b) finding is that OPPONENT inference is 60-75% of
  collection at every K.
* **A-1: NO VERDICT, by instruction.** `ratified_decisions` empty,
  `verdict_authorized: false`, and `scripts/engine_a1_grade.py` refuses.
* Fresh-env check PASSES (builds from committed pins into a clean env).

## How big does the A/B need to be? (answered with data, 2026-09-10)

Measured from a real Node lane's own history: per-update wall has a **CV of
2.5%**, so the STATISTICAL precision of a ratio is already fine at a small dose:

| dose | updates | se(rate) | se(RATIO) |
|---|---|---|---|
| 1M | 33 | 0.44% | 0.62% |
| 3M | 98 | 0.25% | 0.36% |
| 12M | 391 | 0.13% | 0.18% |

**So sample size is NOT the binding constraint** — the two systematics are.

*Startup.* The engine is the short arm, so a fixed ~20 s startup is **8%** of a
1M engine run against 2% of the Node run — an order of magnitude above the
statistical term, and it does not average down with dose. The harness therefore
reports a **steady-state** ratio with the first two updates dropped, which is
immune to startup at any dose. Both ratios are reported: `speedup_wall_clock`
is what you pay, `speedup_steady_state` is what the collector sustains.

*Drift.* The box warms and background load creeps, so a single A-then-B
ordering hands all of it to whichever arm ran second. **Fixed by alternation,
not by dose** (maintainer, 2026-09-09): the harness runs **ABBA** — two
replicates per arm, both averaging run position 2.5, so a linear trend cancels
out of the ratio exactly. `ABAB` would NOT do this (A at 2.0 against B at 3.0),
and six runs cannot balance at all: three integers cannot average 3.5. The
ratio is the mean of PER-PAIR ratios, and the sd/se across pairs is an
empirical error bar rather than an assumption — if the pairs disagree, the box
was not stable, which a single run could never have revealed. `--order
ABBAABBA` doubles the replicates; the maintainer ruled that overkill, and the
arithmetic agrees.

**"How many steps to be certain" has no answer in steps.** At 1M the ratio is
already good to 0.6%; what would make it wrong is startup, thermal drift and a
noisy neighbour — the first two are now designed out, and none of the three
are fixed by more steps. Dose stays at **1M**.

## The speed question — read this before quoting any number

The maintainer rejected cross-day comparisons, correctly. **The only
authoritative speed answer is `scripts/engine_ab_speed.py`** — same dose, both
collectors, back to back on one idle box — which is QUEUED and has not run yet.
Numbers that exist now and their status:

* 0.043 vs 1.08 server cores — MEASURED TODAY, both halves clean. Quotable.
* 1502 steps/s/lane at 3-wide — measured today, clean on its own.
* **2.62x — NOT QUOTABLE as the speedup.** It divides today's rate by a Node
  rate banked 2026-09-01. Recorded in NOTES with that caveat attached.

## THE SPEED PICTURE AS IT STANDS (2026-09-10 ~02:00Z)

**The port inverted the profile, and that is the headline finding, not the
multiplier.** Three lanes each side, both 3-wide, so the shares are comparable:

| | update share of wall | collection share |
|---|---|---|
| Node path, concurrency 8 | 0.2513 / 0.2502 / 0.2500 | 74.9% |
| engine path, k=8 | 0.6509 / 0.6562 / 0.6467 | 34.9% |

So **Amdahl caps any further COLLECTOR work at 1.54x** at k=8, and higher at
larger k (a contended probe at k=64 read ~84% update share). Essentially all
remaining headroom is in the learner.

**The learner's levers are complements, and that is the finding.** Idle box,
`update_episodes()`, one process per cell with OMP sized at launch, best of 3:

```
minibatches  rows/mb    T=1     T=2     T=4     T=6
    120         256    7.73    9.49    8.83    9.83   <- shipped recipe
     30        1024    7.98    7.54    6.38    6.43
      8        3840    9.89    6.66    5.38    5.11
```

Read the top row alone and threading is dead. Read the left column alone and
bigger minibatches are dead. **Crossed, 7.73 -> 5.11 s = 1.51x on the update,
~1.28x on the full loop.** Two independent sweeps would have closed both axes.

`torch.compile` IS dead: **0.82x** idle (worse than the 0.89x contended read).

Adoption is the uncomfortable part. `torch_threads` is free; `minibatches` is
NOT — 4 x 8 is 32 optimizer steps per update against the shipped 480, a
different trajectory. The gain needs both, so **the free part of this finding is
zero and the whole 1.51x sits behind a pre-reg.**

**One instrument trap, resolved, that would have invalidated all of the above.**
`update_episodes()` (async, what the engine calls) is NOT `update()` (sync,
what the 2026-08-31 bench timed at 12.002 s). The async path drops three
full-batch forwards over 30,720 rows the sync path performs — the second critic
pass over `next_obs` and the `old_logp` recompute (`ppo.py:1126-1145`). That
gap, not a faster box, is why numbers here land under 12 s, and it means the
banked 0.85x is a fact about `update()` that does not transfer unexamined.

**Lanes contend hard.** A solo engine lane reads ~2427 steps/s against 1539 at
width 3, so width 3 buys ~1.9x fleet throughput rather than 3x.

## Built tonight, all committed, none of it ratified

* **`scripts/engine_a1a.py` — the A-1a row-parity harness (RW-9).** Frozen
  checkpoint, no learning, four arms (2 engine + 2 node), and the null is
  MEASURED rather than assumed: the A/A pairs say what reseeding alone does at
  this n, and the A/B pairs are read against that. A 20-episode engine-vs-engine
  smoke — a TRUE NULL — gave `obs_smd_max` 1.086 and 412 of 828 dims over SMD
  0.10, which is the whole argument for not writing a fixed threshold.
  `version` is reported and never scored (staleness differs by construction).
  `--smoke` runs the engine arms alone, needs no server, and produces the A/A
  calibration rather than a throwaway. **It decides nothing on its own** and
  says so in its output.
* **`scripts/engine_speed_readout.py`** renders the speedup FROM THE JSON, with
  the scope and disclosures attached, so 2.62x / T-1(a,b) / T-1(d) cannot be
  quoted as "the speedup" by accident. Wired as step 4 of the queue.
* **A/B hardening**, two of which were real hazards: per-replicate seat tags
  (alternation ran both Node replicates at the same seed with no tag, so both
  got `as2s9301a/b` — a collision there poisons the pair for HOURS and takes
  the rest of the A/B with it); a `simulator: 4` assertion (gitignored file,
  worth +81% on the Node path, and getting it wrong inflates the ratio by
  exactly that); `steady_state` now divides by the config's own batch instead
  of a pasted 30720; and a bank preflight, since ABBA runs a Node arm first and
  a missing bank would otherwise surface 33 minutes in.
* **`tests/test_engine_ab_speed.py`** (10 tests) turns the fairness claim into
  a test: the arms differ in exactly {collector, env_kwargs, run_name}, and
  inside env_kwargs only in seat_tag.
* **The A-1 header said RATIFIED while the sidecar said WITHDRAWN** — for a
  day. Fixed, and `tests/test_engine_a1_prereg.py` now asserts the header
  cannot claim ratification while `ratified_decisions` is empty (verified to
  fail on the old wording before it passed on the new). RW-9 and RW-10 joined
  `rulings_wanted`; the RW-set test tolerates growth so a review can add a
  decision without editing a test.

## Open decision: another session's A-1 rulings (2026-09-09 evening)

Two rulings arrived. My assessment, with a second opus reviewer running:

* **ADOPT — A-1a, distributional row parity.** Fix a checkpoint, no learning,
  collect from BOTH collectors, compare row distributions. Attacks exactly the
  hole `track.rs` admits to ("the half of the port that gate P-1 deliberately
  does not test"), is far sharper than an outcome test, costs hours. Better
  than the P-1b design already in NOTES; likely subsumes it.
* **ADOPT — the team-source warning.** The engine draws from a fixed bank, the
  server rolls its own teams. Real confound for A-1a; must be resolved in the
  header before any data is looked at.
* **REJECT — the |delta| < 0.10 band.** The algebra is right, the constant is
  not: sigma 0.0617 is the 50M-dose off-FP number, and A-1 reads at 12M where
  the regime-matched sigma is 0.01499 (`scripts/engine_a1_sigma.py`, derived
  from named files). 2*se_diff at k=3 is 0.0245, not 0.1008, and equivalence
  needs k>=6 per arm, not 49. Decisive check: a 0.10 screen passes D25's
  credited +0.0739, CH3 R2's +0.0693, G9's own +0.02322 and `recharge_fix`'s
  +0.0106 — i.e. **a regression larger than every lever this project has ever
  credited**. That is a gate that cannot fail.
* **ADOPT WITH CHANGES — ruling 2 (no historical finals as the verdict arm).**
  Right conclusion, aimed at a baseline this pre-reg does not use: the header's
  baseline is the async acceptance fleet JOURNEY 7.5 names, and the four
  recipe12m runs were already disqualified on a stronger ground (a different
  RECIPE — 1,024 steps/update against 30,720). Contrary to the ruling they DO
  carry meta.yaml with `git_dirty: false`. A fresh Node arm is still worth an
  overnight for a reason the ruling does not give: **it yields the true
  same-box head-to-head A/B at 12M scale for free** and retires the
  historical-baseline question.

### Second opinion (independent opus reviewer) — where it CHANGED my verdicts

* **Band: REJECT — CONFIRMED by both.** No disagreement.
* **A-1a: my ADOPT was too loose. Correct verdict is ADOPT AS AN *ADDITIONAL*
  GATE, REJECT AS A REPLACEMENT.** The ruling has A-1a "carry the decision".
  It cannot: row parity at a FIXED checkpoint tests the collector's OUTPUT
  under a frozen policy, not LEARNING. A collector can emit identical rows and
  still break learning through staleness, the recorded-old_logp path, or GAE
  on unfinished episodes — none of which a frozen-policy comparison touches.
  A-1a is still worth building, because it is the sharpest instrument available
  against the `track.rs` hole; it is a complement to the outcome gate, not a
  substitute for it.
* **Team source: the ruling's PREMISE IS WRONG.** The bank calls literally the
  same PS generator object the server does (`showdown/sim/teams.ts:629-649`,
  invoked from `battle.ts:3172`), at the same pin, with the `battleHasDitto`
  pair coupling preserved. The team DISTRIBUTIONS match; A-1a would not fail
  spuriously on this. The residual the ruling gestures at is real but is a
  different thing — train-on-finite-support vs evaluate-on-fresh-teams, an
  asymmetry BETWEEN THE ARMS — and it is exactly what RW-6 already addresses:
  the 5,000,000-pair bank gives 0.078x recurrence at 12M. No distributional
  proof substitutes for bank size there.
* Also established: **"feed the server packed teams" is BLOCKED** for
  `gen1randombattle` — `team-validator.ts:381-387` refuses a user team before
  the sim is reached, and poke-env sends `/utm` unconditionally
  (`ps_client.py:328-332`). It is achievable only via a custom vendored format
  (a gitignored tree edit of the `simulator: 4` chore class). So of the
  ruling's three resolutions, (a) is expensive, (b) is a coarsening rather than
  a control, and (c) proves the wrong thing.
* **New, and actionable: a bank provenance discrepancy.** The server reseeds
  between the two teams (`battle.ts:3167-3169`, `:3174`); our generator does
  not. Verified in both files. Believed inert (ChaCha20 forward ratchet; Ditto
  coupling survives `setSeed`) and recorded in `scripts/engine_team_bank.js`
  rather than fixed, since a rebuild would invalidate the bank sha and every
  gate citing it for a difference with no known mechanism.

Nothing above is ratified. `rulings_wanted` in
`configs/engine_a1.prereg.yaml` still ends the sidecar with all eight open.

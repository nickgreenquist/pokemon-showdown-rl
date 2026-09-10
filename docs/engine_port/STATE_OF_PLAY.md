# Engine port — state of play, 2026-09-10 ~00:30Z

Written so a session with no memory of today can pick this up. Durable record
is `docs/engine_port/NOTES.md` (incidents and gate numbers) and the git log;
this file is only "what is in flight and what was just decided".

## Running right now (all detached; survives any session change)

| what | where | eta |
|---|---|---|
| A-1 engine arm, 3 lanes x 12M, seeds 66/75/83, k=8 | `<worktree>/runs/engine_a1_s*` | ~01:45Z |
| the gate chain (finishes with T-1(c) then A-1 descriptive evals) | `scripts/engine_gates.sh`, log `logs/engine_gates.log` | after lanes |
| post-lane queue: `pytest tests/` then BOTH A/B variants | `logs/post_lane_queue.log` | after the chain |

The A-1 lanes run out of the WORKTREE
(`/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-engine`) and the
`pkmn-engine-port` env's editable `rl` still points there. **Do not remove the
worktree or re-point the env until the lanes finish.** Teardown is one step:
`pip install -e .` from main, `pip install --no-build-isolation -e
engine/pkmn_gen1` from main, move `runs/engine_a1_s*` into main's `runs/`, then
`git worktree remove`.

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

**So sample size is NOT the binding constraint — startup is.** The engine is
the short arm, so a fixed ~20 s startup is **8%** of a 1M engine run against
2% of the Node run, an order of magnitude above the statistical term, and it
does not average down. Hence: dose raised to **3M** (startup falls to ~2.7%)
AND the harness now reports a **steady-state** ratio with the first two updates
dropped, which is immune to startup regardless of dose. Both ratios are
reported; `speedup_wall_clock` is what you pay, `speedup_steady_state` is what
the collector sustains.

Remaining systematic, stated not mitigated: Node runs first and is the long
arm, so the engine arm runs on a warmer box. On a laptop that biases AGAINST
the engine, so the reported speedup is conservative. Reversing the order bounds
it if the number is ever contested.

**"How many steps to be certain" has no answer in steps.** At 1M the ratio is
already good to 0.6%; what would make it wrong is startup, thermal drift and a
noisy neighbour, none of which more steps fix.

## The speed question — read this before quoting any number

The maintainer rejected cross-day comparisons, correctly. **The only
authoritative speed answer is `scripts/engine_ab_speed.py`** — same dose, both
collectors, back to back on one idle box — which is QUEUED and has not run yet.
Numbers that exist now and their status:

* 0.043 vs 1.08 server cores — MEASURED TODAY, both halves clean. Quotable.
* 1502 steps/s/lane at 3-wide — measured today, clean on its own.
* **2.62x — NOT QUOTABLE as the speedup.** It divides today's rate by a Node
  rate banked 2026-09-01. Recorded in NOTES with that caveat attached.

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

Nothing above is ratified. `rulings_wanted` in
`configs/engine_a1.prereg.yaml` still ends the sidecar with all eight open.

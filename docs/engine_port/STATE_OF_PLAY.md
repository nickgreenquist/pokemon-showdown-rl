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

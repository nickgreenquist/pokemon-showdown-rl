# FP500 R5 — the ladder committee against Foul Play at 500 ms

Generated from `results/fp500_r5/{w500,w020}.json` under
`configs/eval/fp500_r5.yaml` (sha256 `6176f662…`). Hacking run, 2026-09-17/18.
**CREDITS NOTHING.** RESULTS §25.

The maintainer asked, on 2026-09-17, what our win rate against FP@500 is. It did
not exist: the only banked FP@500 figure was **0.472 (n=500, 1 tie)** for the
**100M** committee, measured 2026-09-12.

## The object

The **R5 ladder committee exactly** — the masked log-prob ensemble of the three
200M W finals (`w104`/`w112`/`w120`, sha-pinned), **greedy, no search**. This is
the object that finished listed on the top-500, not a variant of it.

## The result

| arm | FP budget | our record | win rate | ties | se | vs even | s/battle |
|---|---|---|---|---|---|---|---|
| **W500** | **500 ms** | **280–220** | **0.5600** | 0 | 0.0222 | **+2.70 se** | 38.8 |
| W020 | 20 ms | 275–225 | 0.5500 | 0 | 0.0222 | +2.25 se | 1.59 |

**We beat Foul Play at 500 ms**, and **25× the budget buys Foul Play nothing**:
W500 − W020 = **+0.0100 at 0.32 se** (unpaired two-proportion; seeds do not pair
battles). The budget cost 24.4× the wall clock for a difference indistinguishable
from zero.

**Against the banked 100M committee at the same budget: 0.5600 vs 0.472.** That
comparison is CROSS-SESSION and the offset on this instrument is ~0.02, so read
it as a change in the object rather than as a measured delta — but the sign is
not in doubt at that size, and the direction matches the same pair's FP@20
readings (R5 0.5987 banked, 100M ENS3 0.5770).

## Why the 20 ms arm exists

Session offset on the Foul Play instruments is ~0.02 and it has produced a wrong
reading twice this week. W020 is the **same object, same session, same harness**,
so the budget comparison is internal. Without it, "500 ms buys FP nothing" would
have been a difference between two sessions.

## Provenance and gates

- Both arms: **500/500 battles finished**, `gate_all_challenges_resolved: true`,
  **0 ties**, **0 mask desyncs**, `max_concurrent_live_battles: 1` (fully serial,
  so neither seat was flattered by a divided box), `concurrent_decisions: 0`.
- Same encoder (`POKEMON_RL_ENCODER_V2=1`, `_IDS=1`, `process_obs_dim 828`),
  same pre-reg sha, same three checkpoint sha256s, deterministic policy.
- `launch_git_sha b94085d6` on both. (**Caveat added 2026-09-18:** that field was
  read AFTER the battles until this date, so it is the tree state at completion,
  not at launch — see `docs/CLEANUP.md` L5.)
- Committee diagnostics: the ensemble overrode its first member on **10.0%**
  (W500) and **9.7%** (W020) of decisions. Mean turns 30.5 and 28.1.

## Disclosures that travel with every Foul Play number, forever

1. **Name the budget in every quote.** "We beat Foul Play" is meaningless without
   it; this is 500 ms, and the standing gen-1 anchor is 20 ms.
2. **The equivalence test is weakly powered.** n=500 gives se 0.0224 at p≈0.5,
   which separates "clearly behind" from "clearly ahead" and nothing finer.
3. **The point estimate flatters us.**
4. **FP@500 is an INSTRUMENT, not a rung.** It is descriptive, never a verdict
   input, and nothing here projects to the ladder in either direction.

## What it changes

JOURNEY 11.5's search work was written on the premise that **"Foul Play beats us
using 500 ms"** — the argument in IDEAS §8.1 that our unspent inference budget
was the gap. **That premise is retracted for this object.** The remaining
question about the budget is not "more milliseconds on the same construction"
(25× bought Foul Play nothing either) but **where** the budget goes (IDEAS 8.5)
and **what the network learns from it** (IDEAS 4.9).

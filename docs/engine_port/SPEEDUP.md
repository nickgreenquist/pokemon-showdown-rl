# The pkmn/engine collector port — the measured speedup

**The question this answers:** how long does it take to train the same number of steps the old way (Node/Showdown server, poke-env, async collector) against the new way (in-process pkmn/engine)? Same dose, same box, back to back, one lane each.

Alternated **ABBA** — replicates, not one run each. The ratio's statistical se is already ~0.6% at 1M steps, so sample size was never the binding constraint; drift was. ABBA gives both arms the same mean run position, so a linear trend in the box (thermal, background creep) cancels out of the per-pair ratios instead of landing on whichever arm ran second. The reported sd is across pairs and is an EMPIRICAL error bar, not an assumption.

| variant | dose | reps n/e | node | engine | **speedup** | sd | steady-state |
|---|---|---|---|---|---|---|---|
| production (engine k=256) | 1,000,000 | 2/2 | 21.8 min | 5.4 min | **4.03x** | 0.009 | — |
| matched concurrency (engine k=8) | 1,000,000 | 2/2 | 21.8 min | 7.3 min | **2.98x** | 0.034 | — |

- production (engine k=256) per-pair ratios: 4.04x, 4.03x
- matched concurrency (engine k=8) per-pair ratios: 2.96x, 3.01x

## Which number to quote

**4.03x is the headline** — old way against new way, each collector at the width you would actually train it at. It BUNDLES the concurrency change with the collector change, because running the engine at k=8 in production would be leaving the port's main advantage on the table. Name the dose and the width when you quote it.

**2.98x is the controlled number** — engine k=8 against the Node arm's concurrency 8, so the COLLECTOR is the only delta. This is the apples-to-apples read and the one to use for any claim about the collector itself rather than about the pipeline.

## And if you MAX IT OUT: k x fleet width

The A/B above is ONE LANE at each collector's production width. This is the other axis — what the engine does when the box is pushed. Idle box, 200,000 steps per lane per cell, realized steps/s from each lane's own series with the startup window dropped.

| k | lanes | per-lane | fleet | peak RSS |
|---|---|---|---|---|
| 8 | 1 | 2,390 | 2,390 | 2.26 GB |
| 8 | 3 | 1,620 | 4,861 | 7.37 GB  <- today |
| 8 | 6 | 1,282 | 7,694 | 10.95 GB |
| 256 | 1 | 3,035 | 3,035 | 2.37 GB |
| 256 | 3 | 2,106 | 6,317 | 7.89 GB |
| 256 | 6 | 1,666 | 9,994 | 11.33 GB |

**Best fleet throughput: k=256 at width 6 — 9,994 steps/s, 2.06x today's setting**, on 11.3 GB of 24. Width 6 is not the ceiling.

**Best per-lane rate: k=256 at width 1 — 3,035 steps/s, 1.87x.** This is the only one of the two that shortens a SINGLE run.

**These two answer different questions and must not be multiplied together or added to the A/B.** A lane is a SEED, not a shard of one run: width buys seeds per hour and never a shorter run. And k costs 0.11 GB for 248 extra battle slots, so k and width are independent axes rather than substitutes.

**Neither is free.** Raising k changes the staleness profile (stale rows go 0.40% at k=8 to 12.6% at k=256) and needs its own pre-reg. Width does not change learning at all — a lane is an independent seed — so it is the one lever here that can be taken on merit.

## What the speedup is actually made of

**A large share of this number is INFERENCE BATCHING, not the engine.** The Node collector calls the policy one decision at a time — `rl/envs/showdown_async.py:118-123` passes `obs[None, :]`, and the opponent seat does the same at `rl/envs/showdown.py:1227`. A forward pass costs ~230 us almost regardless of how many rows are in it (fit across the k sweep, cross-checked at 352 us/batch-1-forward against a banked Node lane's own `inference_seconds / seam_requests`). So the Node path's measured knee of 1240 learner-decisions/s = 806 us each is **~85% two batch-1 forwards** — not a server limit and not an I/O limit. The engine path batches 8 learner rows into one forward, i.e. 44 us/row against 352.

That batching is a genuine property of the port — an in-process collector can hold k battles at a decision point simultaneously and a websocket-per-battle collector cannot — so it belongs in the number. But it is NOT the Rust engine being fast, and someone could in principle have batched the Node path's forwards without any of this work. Quote the speedup as the pipeline's, never as the engine's.

## What this is not

- **Not a fleet number.** One lane each, width 1. The fleet-width read is T-1(d), and it says something different and independently useful: the Showdown server drops to **0.043 cores** while three engine lanes train, against 1.08 cores per lane on the Node path.
- **Not a collection-throughput number.** T-1(a)/(b) measure collection with no update in the denominator; that overstates by ~7x and is not comparable to anything here.
- **Not 2.62x.** That figure divides today's engine rate by a Node rate banked on 2026-09-01 — two measurements subtracted, on different days. It is recorded in NOTES with that caveat and must not be quoted as the speedup.
- **Not a licence to switch collectors.** Speed is not the gate; A-1 is, and A-1's band is unresolved. A faster collector that trains a different agent is worth nothing.

## Disclosures carried from the harness

- ONE LANE each, width 1. This is not a fleet number.
- ALTERNATED ABBA with 2/2 completed replicates; the ratio is the mean of PER-PAIR ratios, so a monotone drift in the box cancels rather than landing on whichever arm ran second. The sd is across pairs and is an empirical error bar, not an assumption.
- engine k=256; the production setting, so this is old-way vs new-way and NOT a controlled test of the collector alone
- evals OFF in both arms; the locked protocol stays on the server either way, so including it would add the same constant to both
- the Showdown server ran with simulator: 4 (CLAUDE.md rule 5), checked at launch by the harness that produced these runs
- ONLY the wall-clock ratio survived the harness crash; the steady-state ratio, which excludes startup, is not available for this variant.
- engine k=8; MATCHED to the Node arm's concurrency 8, so the COLLECTOR is the only delta

Showdown server ran with `simulator: 4` (CLAUDE.md rule 5, checked at launch, not assumed).

Measured 2026-09-10T03:26:37Z, 2026-09-10T04:23:34Z by `scripts/engine_ab_speed.py`; raw JSON under `results/engine_a1/`.

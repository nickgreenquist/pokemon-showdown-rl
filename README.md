# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`), battle phase only — no team building. It is trained by
**pure self-play from random initialization**: no human replays, no behaviour
cloning, no scripted opponent in the training loop. It plays through
[poke-env](https://github.com/hsahovic/poke-env).

As of 2026-08-25 it plays on the **real Showdown ladder, against humans** —
LADDER R1 is complete at n=200 (GXE **59.6%**, Glicko-1 **1573 ± 27**).

## On the ladder — LADDER R1, complete

Account [`nickgen1rbrlbot`](https://pokemonshowdown.com/users/nickgen1rbrlbot),
playing the 4-lane ensemble policy, one battle at a time. Pre-registered in
[`configs/eval/ladder_r1.yaml`](configs/eval/ladder_r1.yaml) before the first
rated battle was played. **The run is finished and the pre-registered stopping
rule was met.**

| | |
|---|---|
| **GXE — the pre-registered primary read** | **59.6%** |
| **Glicko-1** | **1573 ± 27** |
| **PS Elo, final** | **1292** (highest observed 1348) |
| Record | 95–105 over **200** rated battles (0.475) |
| Opponents | 141 distinct, mean Elo 1229 (range 1000–1538) |
| Stopping rule `rd ≤ 40 AND n ≥ 200` | **satisfied** (rd 27, n 200) |
| Top-500 admission cutoff | Elo 1357 — **we are not listed** |

*Ratings read from the Showdown profile 2026-08-26. Run executed 2026-08-25/26,
12.07 h, 0 decision errors, 0 mask desyncs, both battle tallies agreeing at 200.*

**Four things this table is careful about, and they matter more than the numbers
in it:**

- **Nothing here credits anything.** The ladder rung is descriptive by
  construction: no A/B, no control arm, no threshold to clear. Calling a ladder
  number "credited" would be a category error in this repo's vocabulary.
- **GXE is opponent-adjusted and the raw record is not.** 59.6% against a raw
  47.5% is not a contradiction: GXE estimates the win rate against an *average*
  ladder player, and this account's opponents averaged 1229 Elo. Quote GXE, not
  the raw rate, and never quote either without n.
- **We are not on the top-500 list, and there is no "GXE cutoff" to clear.**
  **The list is ELO-RANKED.** Ranks 490–500, read off the live board on
  2026-08-26, sit at Elo 1357–1359 — a 2-point band — while their GXE spans
  66.2–77.2% and their Glicko spans 1627–1729. So admission is an Elo
  threshold (**1357**) and GXE is merely whatever the listed players happen to
  hold. We are at Elo 1292.
- **The gap to the top 500 is ~125 Elo of real strength, not the 65 the
  profile suggests — and more battles will not close it.** Win rate by
  opponent strength over the 200 rated battles: **0.688 vs sub-1100
  (n=48), 0.488 vs 1100–1200 (n=43), 0.464 vs 1200–1300 (n=28), 0.340 vs
  1300–1400 (n=47), 0.321 vs 1400+ (n=28).** Holding rank 500 means holding
  ~50% against the 1300–1400 band, where we score 34%. Inverting Elo's
  expected-score curve per band gives an implied true rating of **~1232**, so
  the profile's 1292 is *above* our own equilibrium and was still falling —
  the last battle took it 1311 → 1292, and the fresh-account start at 1000
  inflated everything before it. *(Caveat: the per-band estimates trend
  upward with opponent strength — 1154/1217/1245/1313 — which is either
  logistic mis-specification or a real effect; at n=28–47 per band this
  repo does not claim which. The aggregate direction is not in doubt.)*
  **Closing it is a model problem, which is what Chapter 5 is for.**
- **An earlier version of this table said GXE was unmeasurable, and that was
  wrong.** It claimed Showdown computes GXE only for listed accounts. It does
  not — the leaderboard *JSON* contains only listed accounts, but the **user
  profile carries GXE and Glicko for any rated account**, which is where these
  numbers come from. The run's tooling checked the leaderboard and concluded the
  primary read did not exist. It existed the whole time.

Ladder replays are kept as evidence for the pre-registered readouts. **They are
never training data** — see *The claim* below.

## The claim

The interesting property of this agent is not its strength; it is **where its
strength came from**. Weights are a function of random initialization,
self-play experience, and the environment — nothing else. No expert
demonstrations, no human games, no distillation from a stronger bot, at any
point in the lineage that produced the checkpoints on the ladder.

That constraint is enforced, not asserted: what "pure" means here, and how it
is checked, is written down in [`RESULTS.md` §1](RESULTS.md).

Per an adversarial prior-art search (2026-08-10; scope in `SESSION_LOGS.md`):
**no documented instance was found** of a pure self-play agent passing the
scripted benchmark in gen 1. That is stated as *none found*, not *proven
first*.

The agent plays humans; it does not learn from them. Foul Play and the Showdown
ladder are both opponents and both anchors — never sources of training signal.

## Results

Win rate vs poke-env's `SimpleHeuristicsPlayer` (SH) under the locked protocol:
final checkpoint, deterministic policy, ties count as non-wins, 3000
battles/seed pooled across seeds.

| | vs SH |
|---|---|
| pure self-play, 12M steps, flat MLP — the plateau | 0.3996 |
| + entity architecture (DeepSets + pointer head) | 0.5509 |
| same recipe at 50M steps | 0.5802 |
| + opponent-action auxiliary loss — **credited** | 0.6185 |
| **+ LR anneal (D26) — credited, the headline** | **0.7183** |
| 4-checkpoint log-prob ensemble (inference-only) | 0.7463 |
| **+ one-ply expectation search (CH3 R2) — best measured** | **0.7928** |
| *reference:* behaviour clone of SH | 0.4657 |
| *reference:* SH vs SH mirror (parity point) | 0.489 |
| *reference:* Foul Play engine (search bot) vs SH | 0.8307 |

**Read the search row with its caveat.** The +0.069 that search adds over the
same checkpoints played greedily is **SH-facing**: it does not transfer to
either off-SH opponent measured (BC clone 0.894 → 0.860, Foul Play 0.388 →
0.368). **LADDER R1 therefore ran the *ensemble*, not search** — argued and
ratified in the pre-reg header before any rated battle. **LADDER R3 REVERSES
that deployment call and ladders search**, on different and narrower evidence:
those numbers are 12M lanes off SH, while R1-B measured search on the 50M
fleet off Foul Play@20 and found it *helps* there (+0.1010 within-lane, 3.6
se). The reversal is recorded as a decision in
[`configs/eval/ladder_r3.yaml`](configs/eval/ladder_r3.yaml) (D6), and the
ceiling travels with it: it does **not** overturn the SH-facing finding above,
and the two sets of numbers may not be set side by side.

**A credit line, not a leaderboard.** A lever is credited here only if its
pooled delta is ≥ +0.025 **and** ≥ 2·se_diff, where se_diff is the *larger* of
the binomial and seed-clustered standard errors. On this task the clustered
term always wins, and three separate arms cleared +0.025 on the point estimate
and still did not credit. Full table with every disclosure, and the arms that
failed, in [`RESULTS.md` §15](RESULTS.md).

## What the project actually learned

The negative results are the durable part.

- **Structure beat both inputs and rewards.** At matched parameters, a better
  encoder moved the plateau +0.009 and reward shaping +0.014 (n.s.), while
  entity embeddings + DeepSets pooling + a shared per-action scorer moved it
  **+0.151**.
- **Search is real and inference-only.** One-ply expectation search beats its
  own greedy self by +0.15 in mirror games — but one round of expert iteration
  distilling 494,603 of its own decisions made *every* lane worse vs SH
  (−0.055, 4/4 negative). It does not compile into weights.
- **Losing to Foul Play was not an off-distribution hole.** A Bradley–Terry fit
  over ~30,000 battles put the anomaly at +0.005 ± 0.013 — we were simply
  weaker. The datum that motivated the whole hypothesis was an artifact of
  comparing a *sampling* policy against a *deterministic* rating.
- **Seed variance sets the floor on what is knowable.** At 12M steps, between-lane
  spread runs 0.024–0.049, which is why mechanism evidence has to carry rungs
  that win-rate deltas cannot.
- **A failure that returns a well-formed answer is worse than a crash.** Learned
  three separate times in one day, most sharply when a blocked User-Agent made
  every leaderboard call fail silently while reporting the specific, plausible
  and wrong message *"not yet on the top-500 list."*

## Setup

Python 3.13, CPU-first — the RL loop is collection-bound. All dependencies are
pinned exactly in `pyproject.toml`.

```
pip install -e ".[dev]"
```

The Showdown server is vendored at `showdown/` (gitignored). To set it up fresh,
run `scripts/setup_showdown.sh`, then set `simulator: 4` in
`showdown/config/config.js` (~line 111) — worth +81% collection throughput.

## Running

Start the server (required for anything touching the environment):

```
cd showdown && node pokemon-showdown start --no-security
```

Train:

```
python -m rl.train --config configs/<run>.yaml --seed N --run-name <name>
```

Evaluate a checkpoint against SH under the locked protocol:

```
python scripts/eval_checkpoint.py <run_dir>/checkpoint.pt --episodes 3000
```

Play the real Showdown ladder (needs a registered account and `PS_PASSWORD`;
`--battles` is a total across resumes, and the run resumes per-battle):

```
python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L2 --battles 200
```

W&B logging defaults to offline; `scripts/extract_history.py <run_dir>` writes
`history.csv`.

## Where things are written down

| file | what it is |
|---|---|
| [`RESULTS.md`](RESULTS.md) | **the account** — the claim, the evidence, what failed, every disclosure |
| `STATUS.md` | current state and next actions, rewritten in place |
| `SESSION_LOGS.md` | the dated record: every number, every correction |
| `configs/*.yaml` | each experiment's pre-registration, in the config header |
| `prior_work/README.md` | verified index of external systems — several widely-repeated claims about them do not survive contact with their code |
| `scripts/README.md` | why almost nothing in `scripts/` is safe to delete |
| `DESIGN.md` | **historical.** How the pivot was decided; spent as a roadmap |

## Provenance

This project began as the capstone phase of
[`deep-rl-from-scratch`](https://github.com/nickgreenquist/deep-rl-from-scratch),
which implemented DQN, PPO and SAC from scratch and benchmarked them across
classic-control, MinAtar, MuJoCo and board-game tracks. That work — and the
"no RL libraries" constraint it was built under — is complete and lives there.

**This repo is not held to that constraint.** The goal is the strongest agent we
can build, and it borrows where borrowing wins. Anything borrowed is named here
and in code comments. The `rl/` package keeps only what this project uses: the
from-scratch PPO learner, the masking contract, and the self-play machinery.

The one constraint that *is* enforced is the purity of the training signal, and
it is a scientific claim rather than an engineering preference — see *The claim*.

Notable external components: [poke-env](https://github.com/hsahovic/poke-env)
(environment), [Pokémon Showdown](https://github.com/smogon/pokemon-showdown)
(simulator, vendored), [Foul Play](https://github.com/pmariglia/foul-play)
(search-bot eval anchor, run with our patches), and a poke-engine-derived
forward model used inside search.

# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`), battle phase only — no team building. It is trained by
**pure self-play from random initialization**: no human replays, no behaviour
cloning, no scripted opponent in the training loop. It plays through
[poke-env](https://github.com/hsahovic/poke-env).

As of 2026-08-25 it plays on the **real Showdown ladder, against humans.**

## On the ladder right now

Account `nickgen1rbrlbot`, playing the 4-lane ensemble policy, one battle at a
time. This is a **measurement in progress**, pre-registered in
[`configs/eval/ladder_r1.yaml`](configs/eval/ladder_r1.yaml) before the first
rated battle was played.

| | |
|---|---|
| **PS Elo** | **1325** (peak 1348) |
| Top-500 admission cutoff | 1358 |
| Record | 19–11 over 30 rated battles |
| **GXE — the pre-registered primary read** | **not yet measured** |
| Progress toward the stopping rule | 30 / 200 battles, Glicko rd ≤ 40 |

*Numbers as of 2026-08-25, n=30; the run is live and they move. Refresh with
`python scripts/ladder_classify.py`.*

**Three things this table is careful about, and they matter more than the
numbers in it:**

- **There is no GXE yet, and GXE is the thing we pre-committed to reporting.**
  Showdown computes GXE only for accounts on the top-500 list, and we are ~33
  Elo short of admission. Until that changes the primary read is *unmeasured*,
  not *pending a good result*.
- **The raw record is not a ladder result.** n=30 against a pre-registered stop
  of 200, and a fresh account starts at Elo 1000, so early matchmaking pairs it
  with weak opponents — the early win rate is an *upper* bound that GXE exists
  to correct. Mean opponent Elo so far is 1258 (range 1000–1515).
- **Nothing here credits anything.** The ladder rung is descriptive by
  construction: no A/B, no control arm, no threshold to clear. Calling a ladder
  number "credited" would be a category error in this repo's vocabulary.

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
0.368). The ladder therefore runs the *ensemble*, not search — argued and
ratified in the pre-reg header before any rated battle.

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

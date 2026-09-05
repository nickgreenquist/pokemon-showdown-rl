# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`), battle phase only — no team building. It is trained by
**pure self-play from random initialization**: no human replays, no behaviour
cloning, no scripted opponent in the training loop. It plays through
[poke-env](https://github.com/hsahovic/poke-env).

It plays on the **real Showdown ladder, against humans**. Three pre-registered
runs are complete at n=200 each: LADDER R1 (2026-08-25, ensemble, GXE
**59.6%**, Glicko-1 **1573 ± 27**), LADDER R3 (2026-08-28, one-ply
expectation search on a 50M lane, GXE **60.3%**, Glicko-1 **1579 ± 25**) and
LADDER R4 (2026-09-04/05, the 100M final greedy, on R1's account reused and
warm-started, GXE **65.2%**, Glicko-1 **1618 ± 25**). During R4 the account was
**listed on the global top-500 for 42 of its 200 battles**, peaking near rank 350,
and finished one game's swing under the line. The runs are **not comparable** in
any direction — see the R3 and R4 sections.

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
| Opponents | 141 distinct, mean Elo 1231 (range 1000–1538) |
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
  ladder player, and this account's opponents averaged 1231 Elo (the replay
  `|player|` lines, which are authoritative — the JSONL column is advisory and
  the 1229 previously quoted here came from it). Quote GXE, not
  the raw rate, and never quote either without n.
- **We are not on the top-500 list, and there is no "GXE cutoff" to clear.**
  **The list is ELO-RANKED.** Ranks 490–500, read off the live board on
  2026-08-26, sit at Elo 1357–1359 — a 2-point band — while their GXE spans
  66.2–77.2% and their Glicko spans 1627–1729. So admission is an Elo
  threshold (**1357**) and GXE is merely whatever the listed players happen to
  hold. We are at Elo 1292.
- **The gap to the top 500 is ~143 Elo of real strength, not the 65 the
  profile suggests — and more battles will not close it.** Win rate by
  opponent strength over the 200 rated battles *(cells CORRECTED 2026-08-28,
  rebuilt from the replays with all 200 battles — the originally published
  table was built from an advisory column that silently dropped six)*:
  **0.694 vs sub-1100 (n=49), 0.477 vs 1100–1200 (n=44), 0.464 vs 1200–1300
  (n=28), 0.319 vs 1300–1400 (n=47), 0.375 vs 1400+ (n=32).** Holding rank
  500 means holding ~50% against the 1300–1400 band, where we score 32%.
  Inverting Elo's expected-score curve over all 200 battles gives an implied
  true rating of **~1214**, so the profile's 1292 is *above* our own
  equilibrium and was still falling — the last battle took it 1311 → 1292,
  and the fresh-account start at 1000 inflated everything before it.
  *(Caveat: the per-band estimates — 1171/1147/1217/1227/1351 — broadly
  rise with opponent strength, which is either logistic mis-specification
  or a real effect; at n=28–49 per band this repo does not claim which.
  The aggregate direction is not in doubt.)*
  **Closing it is a model problem, which is what Chapter 5 is for.**
- **An earlier version of this table said GXE was unmeasurable, and that was
  wrong.** It claimed Showdown computes GXE only for listed accounts. It does
  not — the leaderboard *JSON* contains only listed accounts, but the **user
  profile carries GXE and Glicko for any rated account**, which is where these
  numbers come from. The run's tooling checked the leaderboard and concluded the
  primary read did not exist. It existed the whole time.

## On the ladder — LADDER R3, complete

Account
[`nickgen1rbrlbot2`](https://pokemonshowdown.com/users/nickgen1rbrlbot2),
playing **one-ply expectation search (dose M) on the 50M lane s80** — the
deployment reversal recorded as D6 in
[`configs/eval/ladder_r3.yaml`](configs/eval/ladder_r3.yaml), pre-registered
before the first rated battle. **The run is finished and the pre-registered
stopping rule was met.**

| | |
|---|---|
| **GXE — the pre-registered primary read** | **60.3%** |
| **Glicko-1** | **1579 ± 25** |
| **PS Elo, final** | **1232** (highest pre-battle observed 1383) |
| Record | 106–94 over **200** rated battles (0.530); played-only 100/194 (0.515) |
| Opponents | 116 distinct, mean Elo 1201 |
| Stopping rule `rd ≤ 40 AND n ≥ 200` | **satisfied** (rd 25.4, n 200) |
| Top-500 admission cutoff | Elo 1360 — **we are not listed** |

**R3 is standalone descriptive, and it is not an R1 comparison.** Seven
confounds moved between the runs (model, policy kind, account and opponent
pool among them), so **no arithmetic difference between R1's and R3's GXE,
Glicko or Elo is a quantity** — the pre-reg's ratified comparison ruling
(D5) bars exactly that sentence, in both directions. R3's object carries
**one of three anchors (FP@20 only)**: no vs-SH number at the locked
protocol and no BC-clone h2h exists for search on any 50M lane.

The full readout, including every owed disclosure (two blind breaches; real
websocket disconnections, so some of its 19 mid-game timeouts are ours; the
profile's 106–102 against the JSONL's 106–94, the 8 extra losses being
battles our socket died under), is
[`readouts/LADDER_R3_READOUT.md`](readouts/LADDER_R3_READOUT.md). The run self-healed through
every outage unattended (supervisor + socket watchdog, 10 runner launches).

Ladder replays are kept as evidence for the pre-registered readouts. **They are
never training data** — see *The claim* below.

## On the ladder — LADDER R4, complete

Account [`nickgen1rbrlbot`](https://pokemonshowdown.com/users/nickgen1rbrlbot)
— **R1's account, reused** (multiple accounts are against Showdown's rules, a
maintainer ruling) — playing **the 100M final on lane s112, greedy**, the lane a
maintainer-ruled median-of-three rule named on the off-Foul-Play@20 primary.
Pre-registered in [`configs/eval/ladder_r4.yaml`](configs/eval/ladder_r4.yaml)
before the first rated battle. **The run is finished and the pre-registered
stopping rule was met.**

| | |
|---|---|
| **GXE — the pre-registered primary read** | **65.2%** |
| **Glicko-1** | **1618 ± 25** |
| **PS Elo, final** | **1354** (highest pre-battle observed 1431; started at R1's parked 1292) |
| Record, this run (runner-logged) | 104–96 over **200** rated battles (0.520); played-only 97/193 (0.503) |
| Record, the account (cumulative, incl. R1's 200) | 199–201 over 400 — reconciles exactly, zero unlogged games |
| Opponents | 122 distinct, mean Elo 1283 |
| Stopping rule `rd ≤ 40 AND n ≥ 200` | **satisfied** (rd 25.0, n 200), attempt 1, no relaunch |
| Top-500 admission cutoff | Elo 1359.7 at stop — **we are not listed** |

**It reached the global top-500 during the run.** By the replay-derived pre-battle
ratings the account was listed for **42 of its 200 battles, across 13 excursions**,
peaking at Elo 1431 (about rank 350 by the maintainer's screenshots, to be filed
under [`readouts/ladder_r4_evidence/`](readouts/ladder_r4_evidence/)), and finished
at 1354 against an admission line of 1359.7 — 5.7 Elo under, inside one game's
swing. **It did not hold the list**: 18–24 while listed, and 0.423 against the band
containing rank 500. Peak Elo is not a result; the stopping-rule figure is the
read. **The data does not exclude a pure self-play policy that holds the list**:
the gap at stop is inside the measurement's resolution (the licensed cell's se is
0.069 at n = 52), and closing it is what the gen1 return in
[`JOURNEY.md`](JOURNEY.md) (steps 8–11) is for.

**R4 is standalone descriptive, and it is not an R1 or R3 comparison.** Ten
confounds moved between the runs at once (policy kind, training scale and
recipe, the reused warm-started account, opponent memory under the same name
among them), so **no arithmetic difference between any two runs' GXE, Glicko
or Elo is a quantity** — the pre-reg's ratified comparison ruling bars exactly
that sentence in every direction, and bars **Elo(R4) − Elo(R1)** by name now
that one account spans both runs. The rating is a property of an account
carrying R1's 200 games, warm-started from R1's parked end state, not a fresh
measurement of this object alone. **s112 is not "the best 100M lane"**; its
anchors are quoted as pairs with the fleet pooled values (vs-SH 0.8000 /
0.79589, off-FP@20 0.50167 / 0.49844, BC-clone 0.930 / 0.9233).

The full readout — the pre-registered headline sentence, the band table with
its licensed [1300,1400) cell at 0.423 (n = 52, read one-sided against ~0.50,
no threshold), the exact record reconciliation, every VOID condition against
its evidence, and the disclosures (no courtesy note was sent, by ruling; the
run was blind; ops were clean: one launch, zero kills, zero unlogged games) —
is [`readouts/LADDER_R4_READOUT.md`](readouts/LADDER_R4_READOUT.md).

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
| + one-ply expectation search (CH3 R2) | 0.7928 |
| **batch recipe at 100M steps (CH5 C1, greedy) — current top training number** | **0.7959** |
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
and the two sets of numbers may not be set side by side. **LADDER R4
(pre-registered and ratified 2026-09-04,
[`configs/eval/ladder_r4.yaml`](configs/eval/ladder_r4.yaml)) returns to a
greedy deployment** — the 100M final on lane s112 — on R4S66's evidence
(search@20 hurt the batch recipe); the MU-8 ceiling still travels, and no
run-to-run delta is an effect. **R4 ran 2026-09-04/05 and is complete — see the
LADDER R4 section above.**

**The 100M row is not a credit.** Its pre-registered primary axis was off
Foul Play@20 (budget named; the equivalence test is weakly powered and the
point estimate flatters us), where it read **0.4984 vs the 50M control's
0.4746 — delta +0.0239 against a +0.025 floor: cell P3, within-band
positive, non-resolving**. The vs-SH row above is the locked-protocol
secondary (SN-N, descriptive), with the full anchor battery: BC-clone h2h
0.9233 pooled, FP@20 0.4984 pooled. The search row (0.7928) and the 100M
greedy row are different policy forms from different sessions and may not
be ranked against each other. S-SHAPE read: still climbing at 100M
(+0.029 over the last-20M vs prior-20M windows, ≥ 4× its threshold) — on
the 100M anneal, not comparable to a finished run at the same step. Full
table with every disclosure: [`RESULTS.md` §18](RESULTS.md).

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
python scripts/ladder.py --prereg configs/eval/ladder_r4.yaml --arm R4G --battles 200
```

(That is R3's invocation; R1's used `ladder_r1.yaml --arm L2`. Every ladder
run gets its own pre-reg — `ladder_r3.yaml` is the one whose stopping rule
reads the user profile and can actually fire. Long runs go through
`scripts/ladder_supervise.sh <arm> <target> <prereg>`, which survives
websocket drops.)

W&B logging defaults to offline; `scripts/extract_history.py <run_dir>` writes
`history.csv`.

## Where things are written down

| file | what it is |
|---|---|
| [`RESULTS.md`](RESULTS.md) | **the account** — the claim, the evidence, what failed, every disclosure |
| `STATUS.md` | current state and next actions, rewritten in place |
| `SESSION_LOGS.md` | the dated record: every number, every correction |
| `configs/*.yaml` | each experiment's pre-registration, in the config header |
| `docs/prior_work/README.md` | verified index of external systems — several widely-repeated claims about them do not survive contact with their code |
| `scripts/README.md` | why almost nothing in `scripts/` is safe to delete |
| `docs/IDEAS_POST_100M.md` | the live lever list, re-ranked after the 100M read; each entry owes its own pre-reg |
| [`readouts/`](readouts/) | committed ladder provenance, one file per run: [`LADDER_R1_READOUT.md`](readouts/LADDER_R1_READOUT.md), [`LADDER_R3_READOUT.md`](readouts/LADDER_R3_READOUT.md), [`LADDER_R4_READOUT.md`](readouts/LADDER_R4_READOUT.md) |
| `rl/envs/gen4/`, `docs/design_gen4/` | gen 4 groundwork (JOURNEY step 3, merged 2026-09-05): the design docs verified against recorded protocol tapes, encoder layout v0.1, `ShowdownGen4-v0`, the Foul Play gen-4 eval bot. No gen-4 model has been trained beyond a smoke; nothing there is a claim |
| `docs/` | the written record: `prior_work/` and `research_reports/` (external evidence), `IDEAS_POST_100M.md`, `CLEANUP.md`, `landmines.md`, `proposals/`, `design_gen4/` |
| `docs/archive/` | **history, never "what next"** — spent roadmaps (DESIGN, DESIGN2), the Chapter 5 brief and frozen audits, read only when named |

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
(search-bot eval anchor, run with our patches), a poke-engine-derived
forward model used inside search, **Wang (2024)** — the gen-4 PPO recipe the first
gen-4 run copies as its foundation, and his poke-env fork's state-tracking fixes
(`docs/prior_work/README.md`, `docs/design_gen4/research/`) — and **Huang & Lee's
metagrok** most-damage-typed rule (`rl/envs/most_damage_typed.py`).

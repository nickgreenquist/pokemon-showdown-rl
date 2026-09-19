# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`), battle phase only — no team building. It is trained by
**pure self-play from random initialization**: no human replays, no behaviour
cloning, no scripted opponent in the training loop. It plays through
[poke-env](https://github.com/hsahovic/poke-env).

It plays on the **real Showdown ladder, against humans**. Four pre-registered
runs are complete at n=200 each: LADDER R1 (2026-08-25, ensemble, GXE
**59.6%**, Glicko-1 **1573 ± 27**), LADDER R3 (2026-08-28, one-ply
expectation search on a 50M lane, GXE **60.3%**, Glicko-1 **1579 ± 25** — a
**PRE-D5 broken-selector object; see `docs/landmines.md`**),
LADDER R4 (2026-09-04/05, the 100M final greedy, on R1's account reused and
warm-started, GXE **65.2%**, Glicko-1 **1618 ± 25**) and
**LADDER R5** (2026-09-16, the committee of the 200M finals, same account,
GXE **73.9%**, Glicko-1 **1697 ± 25**, PS Elo **1457**). During R4 the account was
**listed on the global top-500 for 42 of its 200 battles** (a filed screenshot shows
rank 369 mid-run), and finished one game's swing under the line; **R5 entered 146 of
its 200 battles at or above the admission line and finished LISTED, ~103 Elo clear
of the cutoff.** The runs are **not comparable** in
any direction — see the R3, R4 and R5 sections.

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
peaking at Elo 1431 (the filed screenshot in
[`readouts/ladder_r4_evidence/`](readouts/ladder_r4_evidence/) shows rank 369 at Elo 1394
mid-run), and finished
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


## On the ladder — LADDER R5, complete

Account [`nickgen1rbrlbot`](https://pokemonshowdown.com/users/nickgen1rbrlbot)
— **R1's account, reused and warm-started** for the third time — playing the
**log-probability committee of the three 200M finals** of the wide-critic recipe
(regenerative L2-toward-init + a 1024-wide critic), **greedy**. The members were
not chosen by hand: a pre-stated rule picked them from a same-session
off-Foul-Play@20 read of every candidate committee. Pre-registered in
[`configs/eval/ladder_r5.yaml`](configs/eval/ladder_r5.yaml) before the first rated
battle, and **launched and babysat agent-side** — the first ladder run here not
started by a human. **The run is finished and the pre-registered stopping rule was met.**

| | |
|---|---|
| **GXE — the pre-registered primary read** | **73.9%** |
| **Glicko-1** | **1697 ± 25** |
| **PS Elo, final** | **1457** (highest pre-battle observed 1541; started at R4's parked 1354) |
| **Top-500 admission cutoff at the stop** | Elo **1354.2** — **listed, ~103 Elo clear** |
| Record, this run (runner-logged) | 128–72 over **200** rated battles (0.640); played-only 125/197 (0.635) |
| Record, the account (cumulative, incl. R1 + R4's 400) | 327–273 over 600 — reconciles exactly, zero unlogged games |
| Opponents | 102 distinct, mean Elo 1304 |
| Stopping rule `rd ≤ 40 AND n ≥ 200` | **satisfied** (rd 25.0, n 200), attempt 1, no relaunch |
| Instrument | mean decision 5.40 ms (band [1, 30], no VOID), 0 decision errors, 0 mask desyncs |

**It held the list rather than touching it.** By the replay-derived pre-battle ratings
the account entered **146 of its 200 battles at or above the admission line** (the cutoff
at the stop, 1354.17; against the n=0 pull it reads 148 — the readout prints both and
neither is pre-registered), across 9 excursions, peaked at Elo 1541, and **finished listed**. Its record while at or above the
line (93–53, 0.637) is indistinguishable from its record below it (35–19, 0.648). Peak Elo
is not a result; the stopping-rule figure is the read.

**The disclosures do not soften because the number is higher.** The rating is
**warm-started** — the account carried 400 games into this run, so GXE / Glicko / Elo at
the stop are properties of the ACCOUNT, not of these 200 battles alone. The run is a
**standalone descriptive measurement**: it has no A/B, no control arm and no threshold to
clear, it **credits nothing**, and **no delta between any two ladder runs may be quoted as
an effect** — the policy kind, training scale, training recipe, account history, calendar,
opponent pool and launch ownership all moved at once.

**The opponent pool is small and that bears on what n means.** 102 distinct opponents
supplied the 200 battles; 63.5% of battles were against someone already faced and the top
five accounts supplied 34.5% of the run. Two tests for opponents adapting to the bot both
came back null and both in our favour. Glicko counts 200 independent games; the effective
sample is smaller. Recorded as item L1 in [`docs/CLEANUP.md`](docs/CLEANUP.md) with a
proposal to spread the next run across sessions.

**Anchor battery for this object: COMPLETE (2026-09-16).** vs SimpleHeuristics under the
locked protocol **0.8386** (n=9000), Foul Play@20 **0.5987** (n=3000), and the BC-clone
head-to-head **0.9640** (n=500) — the last leg, which had been reported PENDING and turned
out to be blocked rather than undecided: its runner had been broken since 2026-09-05 and
had no ensemble seat. Against that frozen clone the 200M fleet and the 100M fleet are
indistinguishable (+0.009 at 1.1 se, same session), which is what a ~0.94 ceiling looks
like — **a clone number is never style evidence, and anchors are never verdict inputs**.
Full provenance: [`readouts/LADDER_R5_READOUT.md`](readouts/LADDER_R5_READOUT.md),
[`readouts/MONSTER_BCCLONE_READOUT.md`](readouts/MONSTER_BCCLONE_READOUT.md), evidence and
reads in [`RESULTS.md` §20](RESULTS.md) and the mechanism verdict in
[§21](RESULTS.md).

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
| batch recipe at 100M steps (CH5 C1, greedy) | 0.7959 |
| **wide-critic recipe at 200M (regenerative L2 + 1024 critic), greedy — credited** | **0.8217** |
| **3-checkpoint committee of those finals — the LADDER R5 object** | **0.8386** |
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

**The 200M rows, and what is credited in them.** The wide-critic recipe
(regenerative L2-toward-init plus a 1024-wide critic, 200M steps) is **credited**
against the 100M baseline: **+0.033 vs SH at 5.59 se** and **+0.046 off Foul
Play@20 at 4.79 se**, both on a same-session re-draw of the baseline rather than
its banked number. **The credit is for the RECIPE AS SHIPPED and never for width
as a separable lever** — no contrast isolates it. Its mechanism co-primary was
registered before any number existed and gave a split answer: the critic's
first-layer effective rank is **632 of 1024** against **5 of 384** on the
baseline, so the width is genuinely *used* — but **explained variance did not
move at all** (0.5881 against 0.5919). **2.67× the width and 126× the rank bought
zero explained variance**, and the next fleet may not be sized on it. At the
COMMITTEE level the recipe gain nearly vanishes (+0.015 at 2.01 se over the 100M
committee): **the recipe gain and the committee gain substitute for each other
rather than adding.** [`RESULTS.md` §21](RESULTS.md).

**A credit line, not a leaderboard.** A lever is credited here only if its
pooled delta is ≥ +0.025 **and** ≥ 2·se_diff, where se_diff is the *larger* of
the binomial and seed-clustered standard errors. On this task the clustered
term always wins, and three separate arms cleared +0.025 on the point estimate
and still did not credit. Full table with every disclosure, and the arms that
failed, in [`RESULTS.md` §15](RESULTS.md).

### Search — four constructions, and what they actually measured

The search rows above are **1-ply expectation search on a matrix of the
opponent's action classes**, and everything written about them before
2026-09-11 measured **a broken selector** (a hard argmax overrode a 0.789 policy
on 72.8% of decisions). September 2026 re-measured the axis properly, and the
result is worth stating plainly because it is mostly negative:

- **Depth buys nothing, and the earlier depth numbers were an artifact of
  something else.** Depth-2 against depth-1 at a **matched override rate** is
  −0.0007 (0.05 se, n=3000/arm) for 3.27× the compute. The same arm at the naive
  delta reads **−0.053 at 3.34 se** — same depth, same everything but the gate's
  threshold. **Every depth number this project published earlier compared arms
  that differed in how often the search was BELIEVED, not in how deep it
  looked.** [§22](RESULTS.md).
- **The gate was the instrument all along, and it falsified the standing
  explanation in the opposite direction.** At a tight gate the search changes
  about **two decisions of a thirty-turn battle**, which bounds what any leaf
  value can be worth. Opening it costs our critic **0.006** and costs Foul Play's
  hand-tuned heuristic **0.088**. **Our own critic is the robust evaluator** —
  the assumption that a PPO-fit value function would break on search-visited
  lines is measured false, in the opposite direction. [§24](RESULTS.md).
- **A real tree does not beat playing the policy's argmax either** — but it is
  the one vehicle not clearly below it. Decoupled UCT with our policy as the PUCT
  prior and our critic at the leaves reads **+0.021 at 0.96 se** against an
  in-session greedy anchor: **unresolved, not null.** What the block does
  establish is that **the rule that turns a finished tree into an action orders
  the arms, and the override rate does not**. [§26](RESULTS.md).
- **And then greedy beat EVERY search arm, which is a measured COST rather than
  another null.** A seven-arm block at n=1000 each, one session, with an
  in-block greedy anchor **and an in-block replicate of one configuration that
  agreed to 0.0020**: greedy **0.6050** tops the block, ungated depth-1 sits
  **−0.052 at 2.4 se** below it and depth-2 **−0.076 / −0.098 at 3.4–4.4 se**.
  A second result in the same block: **gating search onto 40% of decisions beat
  running it on 93%** (+0.0335 at 2.14 se), while choosing WHICH 40% by committee
  disagreement beat a **coin at the same rate** by only +0.0030 at 0.14 se — so
  spending less helped and knowing where did not. [§30](RESULTS.md).
- **Across every block, the vehicle separates and the dose does not.** Every
  matrix arm ever measured sits below its own block's greedy anchor; the only
  arms above one are trees (2 of 3). **Read as descriptive only** — arms enter
  that tally because a block wanted them, replicates count twice, and the matrix
  family has simply been run more, so its Fisher p moves as blocks land and that
  movement is accounting rather than evidence. [§26.1](RESULTS.md).

**And the agent beats Foul Play at Foul Play's own 500 ms budget** — 0.5600
(n=500, 0 ties), with 25× the budget buying Foul Play +0.010 at 0.32 se. The 100M
committee lost that matchup at 0.472. **FP@500 is an instrument, not a rung**, the
two Foul Play disclosures travel, and nothing here projects to the ladder.
[§25](RESULTS.md).

### How much of a gen-1 battle is decided by luck?

Enough to matter, and it was measured rather than assumed. Holding a position at
**our own observation** and varying both irreducible sources — the engine's chance
branches and the opponent's hidden team — over 707 positions and 22,358 self-play
rollouts: **~64% of the outcome variance at a mid-battle position is irreducible**.
The best possible critic reading our observation would reach **EV 0.363**; ours
reaches **0.218**.

So the evaluator is not finished, and the shape of what is left is specific: an
out-of-sample monotone recalibration closes only **~7%** of that gap, so **~93% of
it is the critic not knowing which position is better** — and no post-hoc
rescaling touches that. (Both figures are corrected: the first cross-validation
split at the OUTCOME level while the predictor is constant within a POSITION, so
every held-out outcome had its own position in training. Grouped properly the
gain is +0.0096, and a plain affine fit beats isotonic.)

The critic also **adds +0.059 to whichever side it is pointed at** (z 14.7), in a
zero-sum game where `V(s) + V(swap(s))` must be 0 — and the mechanism is
identified rather than guessed: that is its **training distribution's own mean
return**, because league play fits it against a pool of older, weaker checkpoints
(+0.036 whole-run) while evaluation is a mirror where the truth is 0. **A
train/eval distribution shift, not a seat asymmetry.** Both the ranking failure
and the bias are **worst in the opening**, which is where a battle is still open
and where a search looks. [§27, §27.1 and §31](RESULTS.md).

### Gen 4 — first run (a separate table; never a row in the gen-1 ladder above)

`gen4randombattle`, JOURNEY step 3 → 5. Wang's recipe (Table A.3) on our own
frozen gen-4 encoder and entity trunk, 50M seat-1 steps per lane × 3 lanes,
both seats harvested. Same locked protocol as the gen-1 table: final
checkpoint, deterministic, ties as non-wins, 3000 battles/lane pooled.

| | vs SH | anchors (descriptive, never verdict inputs) |
|---|---|---|
| **gen 4 — Wang's recipe on our encoder (50M/seat × 3), greedy** | **0.8788** | MDT h2h 0.902 · FP@20 h2h 0.293 · FP@500 h2h 0.264 · clone(FP@20) h2h 0.985 |
| *reference:* most-damage-typed baseline vs SH | 0.400 | |
| *reference:* behaviour clone of Foul Play@20 vs SH | 0.464 | |
| *reference:* Foul Play @20 ms vs SH | 0.904 | bot-vs-bot, n=250 |
| *reference:* Foul Play @500 ms vs SH | 0.912 | bot-vs-bot, n=250 |

**This run credits nothing.** It is a baseline, not a lever: no credit line is
applied to any number in it. The step-3 milestone (≥ 0.60) reads **M-YES** and
the step-5 exit (≥ 0.756, one-sided, the ruled floor from Wang's weaker cell)
reads **S5-MATCHED** at +0.1228 = 27× the larger printed se — "matched" is the
only strength word this run is permitted, and it carries seven named deviations
(dose 2/3, our PPO not SB3, our trunk, our action space, our encoder layout,
lockstep collection, ties as non-wins). Wang's 0.786 is his Table 4.1
NETWORK-ALONE cell (MCTS + NN is 0.908) while his Figure 4.1 digitizes to
≈ 0.836/0.849 — his own figure reads higher than the number we matched against.
**The two FP disclosures travel with every FP quote, forever:** the equivalence
test is weakly powered, and the point estimate flatters us; the budget is named
in every quote. **vs-SH is not a ladder number** — the gen-4 ladder is banked
and unrun. Full account with every disclosure: [`RESULTS.md` §19](RESULTS.md);
provenance: [`readouts/GEN4_WANG50M_READOUT.md`](readouts/GEN4_WANG50M_READOUT.md).

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
| [`readouts/`](readouts/) | committed ladder provenance, one file per run: [`LADDER_R1_READOUT.md`](readouts/LADDER_R1_READOUT.md), [`LADDER_R3_READOUT.md`](readouts/LADDER_R3_READOUT.md), [`LADDER_R4_READOUT.md`](readouts/LADDER_R4_READOUT.md), [`LADDER_R5_READOUT.md`](readouts/LADDER_R5_READOUT.md); plus the reads behind them — [`MECH200M_READOUT.md`](readouts/MECH200M_READOUT.md) (the mechanism co-primary) and [`MONSTER_BCCLONE_READOUT.md`](readouts/MONSTER_BCCLONE_READOUT.md) (the BC-clone anchor leg) |
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
metagrok** most-damage-typed rule (`rl/envs/most_damage_typed.py`), and
[**pkmn/engine**](https://github.com/pkmn/engine) (MIT, © 2021-2024 pkmn
contributors) — a Zig implementation of the Pokémon battle engine, vendored as
a submodule pinned to `9b88fd6c` and built in `-Dshowdown` mode so its RNG and
tie-breaks match Pokémon Showdown's. It backs an optional in-process gen-1
collector (`engine/pkmn_gen1`, a Rust + PyO3 wrapper) that removes the Node
simulator from the training loop, where it was a measured **56%** of a lane's
CPU. **It is not the default and does not become one here:** `collector.mode`
stays on the server path until gate A-1 accepts the engine, and on an A-1
failure gen-1 stays there permanently (JOURNEY 7.5). Anything the engine
produces is graded on the same Showdown server as everything else — the locked
eval protocol and the ladder never leave it.

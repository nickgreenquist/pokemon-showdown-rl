# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`) — battle phase only, no team building. The agent plays through
[poke-env](https://github.com/hsahovic/poke-env) against a local
[Pokémon Showdown](https://github.com/smogon/pokemon-showdown) server.

**→ [`RESULTS.md`](RESULTS.md) is the account of the chapter: the claim, what "pure
self-play" is enforced to mean, the evidence, what failed, and the honest scoping.
Start there.** `STATUS.md` is current state; `SESSION_LOGS.md` is the dated record.

## Provenance

This project began as the capstone phase of
[`deep-rl-from-scratch`](https://github.com/nickgreenquist/deep-rl-from-scratch), a portfolio project
that implemented DQN, PPO and SAC from scratch in PyTorch and benchmarked them across
classic-control, MinAtar, MuJoCo and board-game tracks. That work — including the
"no RL libraries" constraint it was built under — is complete and lives in that repo.

**This repo is not held to that constraint.** Its goal is the strongest agent we can
build, and it borrows where borrowing wins: external libraries, replay datasets,
pretrained teachers. Anything borrowed is named here and in code comments. The `rl/`
package keeps only what the capstone uses: the from-scratch PPO learner, the masking
contract, and the self-play machinery (snapshot pool, Elo, opponent protocol). That
machinery was built and validated in the predecessor on a Connect-4 self-play study —
implemented as the sanity check preparing for this project — and the Connect-4 env
survives here only as the two-player test fixture for the self-play harness tests.
CartPole/MinAtar PPO support stays for `DESIGN.md`'s Arm C spine gate; the rest of the
predecessor spine (DQN, SAC, MuJoCo, the Connect-4 study's solver and probes) was
pruned 2026-08-05.

## Chapter 3, closed 2026-08-25: search — what a forward model buys, and where it lives

The question was whether classical search on top of the self-play agent's own
heads could beat the agent alone, and if so, where that advantage lives. The
answer is now complete:

- **One-ply expectation search over a validated gen-1 forward model**
  (poke-engine-derived, transition agreement 0.909), using only our own
  policy/value/opponent-action heads, is the project's best number: **0.793 vs
  SH, +0.069 over the same checkpoints played greedily** (credited, all lanes
  positive). Caveat, measured not assumed: the increment is SH-facing — it does
  not transfer to the BC-clone or Foul Play anchors.
- **The advantage is real in self-play too**: in mirror games, search beats its
  own greedy self by **+0.15** (4/4 lanes) — twice its vs-SH increment.
- **But it does not compile into weights.** One iteration of expert iteration
  (494,603 own-search decisions, actor-only offline distillation, frozen
  critic, self-play collection) made every lane WORSE vs SH (**−0.055 pooled,
  4/4 negative** — B5+KILL, the pre-registered strongest-negative cell). The
  mechanism matched the pre-registered risk exactly: the model's uniform-switch
  optimism cancels inside a live comparison but is toxic once imitated
  (distilled switch rates roughly doubled). The actor expert-iteration family
  is closed for this chapter.
- **The critic is not the bottleneck in the ways we guessed**: it is not
  rank-collapsed (srank99 ~47/384 on the headline lanes), a 3-critic ensemble
  evaluator inside search was flat (+0.022, uncredited), and on-distribution
  critic disagreement is small (|v_LOO−v_own| ≈ 0.05–0.07 over 500k real
  decision points).

Net: **search@M's value is real, and it is inference-only.** The strongest
deployment of this project is the D26 checkpoint with search at decision time;
the strongest pure network remains the D26 checkpoint itself. The open problem
the next chapter inherits: everything here is strong against SH-like play and
still loses to Foul Play (0.39 h2h) — off-anchor strength, not more search, is
the path to ladder readiness.

## Results so far

Win rate vs poke-env's `SimpleHeuristicsPlayer` (SH). Locked protocol: final
checkpoint, deterministic policy, ties count as non-wins, 3 seeds × **3000
battles/seed** pooled. Rows marked † predate the 3000/seed protocol (1000/seed era);
rows marked * are single-seed probes, not headline-grade; the row marked ‡ is a
descriptive pool across two arms (its ± is the seed-clustered se over 5 lanes), never
a verdict input.

| agent | win rate |
|---|---|
| PPO trained *against* SH, 12M, flat / LR-annealed | 0.4330† / 0.4607† |
| Behaviour clone of SH (813k rows) | 0.4657† |
| SH vs SH mirror (parity point; caps SH imitators only) | 0.489 |
| **Pure self-play**, 12M, flat MLP — the plateau | 0.3996 ± 0.0052 |
| + H&L reward shaping (γ0.95, 5-term zero-sum) — null | 0.4131 ± 0.0052 |
| **+ entity architecture (DeepSets + pointer head), 12M** | **0.5509 ± 0.0052** |
| **same recipe at 50M** | **0.5802 ± 0.0052** |
| + privileged (asymmetric) critic, 12M, 5 seeds — null | 0.5364 ± 0.0066 |
| + regenerative L2-toward-init, 12M, 3 seeds — letter-met, not credited | 0.5897 ± 0.0066 |
| **+ opponent-action auxiliary loss, 12M, 5 seeds — CREDITED** | **0.6185 ± 0.0040** |
| ↳ same loss on SHUFFLED labels (placebo, 12M, 5 seeds) — flat on the comparator | 0.5415 ± 0.0041 |
| **+ LR anneal on top (D26), 12M, 4 seeds — CREDITED 2026-08-17, current best** | **0.7183 ± 0.0041** |
| ↳ same stack at 50M (D29r) — **PRIMARY VOID**: 1 of 3 lanes died at 35M (lane-failure rule); two surviving finals recorded individually, never pooled | 0.7327 / 0.7513 |
| ↳ 50M re-run (D29r2, 3 fresh seeds) — **R-A CREDIT** vs the bare 50M recipe (named cell: lanes do not fully separate); **R-B FLAT** vs the 12M stack — scale adds nothing | 0.7022 ± 0.0048 |
| ↳ all five 50M-stack lanes, descriptive only (pre-declared before the re-run's data) | 0.7181 ± 0.0224‡ |
| D28 zero-info dose control (12M, 5 seeds) — **A1: does NOT reproduce D25** (perm 1/252, strict separation); **not sealed** — the control's delivered dose collapsed once the task was learned (g 0.979) | 0.5224 ± 0.0041 |
| CH3 R0: log-prob ensemble of the four D26 checkpoints (inference-only, zero training) — **B1 CREDIT** vs their fresh greedy mean 0.7103; licenses "ensembling THESE four checkpoints", never "ensembling helps" (one committee, no seed replication, floor-governed) | 0.7463 ± 0.0046 |
| **CH3 R2: one-ply expectation search over a validated gen-1 forward model (transition agreement FG-2 = 0.9092 per the accept-with-named-strata ruling; ko_disagreement 0.092 on raw average-damage leaves, 0.0075 after the pre-registered 2-point roll expansion; average-damage approximation named; search inactive on ~5.0% of decisions — the gen-1 placeholder stratum), using only our own self-play policy/value/opponent-action heads — B1 CREDIT 2026-08-22, new best: +0.0693 over the identical checkpoints played greedily (fresh A0 0.7236, same session), all four lanes positive (worst +0.0497), operative bar 0.025 (floor-governed; largest se term 0.0069 unpaired-clustered). CAVEAT (pre-registered falsifier P2, ruled 2026-08-23): the search increment is SH-FACING on the anchors available — on the tested lane (s65) it does not transfer to the BC-clone anchor (greedy 0.894 → search 0.860; transfer > +0.008 excluded at ~95%) nor to Foul Play (0.388 → 0.368, n=250/arm); the D26 policy's own strength DOES transfer (rows below)** | **0.7928 ± 0.0037** |
| ↳ h2h vs the FP behaviour clone, s65 lane (falsifier anchor): greedy det-seat / search@M det-seat / greedy pooled-both-orientations | 0.894* / 0.860* / 0.795* |
| ↳ h2h vs Foul Play itself, s65 lane, n=250/arm ("FP + our patches"): greedy / search@M — our take off the teacher-class bot across generations: 0.124 → 0.172 → 0.388 | 0.388* / 0.368* |
| CH3 R4: LOO 3-critic ensemble evaluator inside search@M (pure inference-time, zero training; pre-registered credit test, REGISTERED 2026-08-23) — **verdict FLAT (B3), NOT credited, headline unchanged**: fresh same-session A1S (E0) 0.7896 → A1E (ensemble critic) 0.8120, paired delta **+0.0224** vs the 0.025 floor, ALL FOUR lanes positive (+0.0457/+0.0173/+0.0173/+0.0093), governing se paired-clustered 0.0080; normal-approx CI [+0.0068, +0.0381] — does not exclude the screen's +0.036, and at df=3 coverage (t₃ 3.18) does not exclude 0. Pre-registered power at the realized effect size was 0.21–0.49 ("a B3 is the modal outcome over much of the pre-registered band" — stated before data); the R3 screen's +0.036 did NOT reproduce at credit grade. Zero F-gates; era green (fresh A1S within 0.0033 of R2's 0.79283); anchors not run (iff-B1/B2, ruled). The 0.8120 level is DESCRIPTIVE — never quote it as a best | 0.8120* (uncredited) |
| CH3 R5: expert iteration — does the credited search advantage COMPILE INTO WEIGHTS? Stage 1 (r5a T-GATE, mirror diagnostic, n=1000/lane): search@M beats its own greedy self in SELF-PLAY by mean +0.1515 (4/4 lanes, 2·se 0.033) — mirror-regime margin, never a vs-SH number. Stage 2 (r5b, actor-only offline distillation of 494,603 own-search decisions, self-play collection, frozen critic): **verdict B5 + KILL 2026-08-25 — compiling search into the weights makes the agent WORSE vs SH: paired delta −0.0545 (bar 0.0442, paired-clustered governs), ALL FOUR lanes negative (−0.0077…−0.1117); the actor expert-iteration line is CLOSED for this chapter; search@M stands recorded as an inference-time lever that does not compile into weights (one iteration, this dose, these checkpoints)**. Disclosures that travel: the actor was fitted offline to its own search's decisions, backed up through poke-engine from the checkpoint's own self-play (RULE-1 provenance); the pre-registered D-2 gate (absolute +0.20) fired on 2/4 lanes and was amended result-blind-on-win-rates to a capture-fraction form before any evaluation battle ran (headline was capped regardless of outcome); C7 materialized — distilled switch rates roughly doubled (0.14–0.20 → 0.21–0.37), the search's uniform-switch-column optimism made permanent; F-P pairing overlap 0.78–0.80 vs the 0.80 floor (30 s stagger), era-immunity clause struck per lane, F-T GREEN (era-pin X0 0.7170). Anchors/placebo not run (iff-B1/B2, ruled). Durable rider: on-distribution critic disagreement |v_LOO−v_own| = 0.047–0.072 at 500k real decision points — design A's ~0.06 estimate confirmed, the 0.45 synthetic reading ~7× off | X1 0.6526* (X0 0.7071, both descriptive) |
| Behaviour clone of Foul Play (graded final / val-peak) | 0.5490 / 0.5777 |
| Foul Play engine (search bot, our patches) — eval anchor | 0.8307* |

**Read those ± with care: they are WITHIN-SEED BINOMIAL standard errors, and they are not
what governs a verdict.** This project's credit line uses the larger of the binomial and
the **seed-clustered** se, and on this task the clustered term always wins — for the
0.7183 headline the governing clustered se on its delta vs D25 is **0.0119, vs the
±0.0041 binomial shown** (between-lane sd 0.0112 over 4 seeds; delta +0.0998 credits at
a 0.0250 floor bar, exact 4v5 permutation p = 1/126). Between-lane spread has run 0.024–0.049 across arms, which is why three separate
arms cleared the +0.025 letter and still did not credit. Quote the clustered interval
whenever the number is doing work.

**The chapter that matters (2026-08-07 →): pure from-scratch self-play.** The project
pivoted from "strongest agent" to a novelty target: no BC init, no teacher or human
data, no scripted opponents in training — weights are a function of random init +
self-play experience + environment only. Three pre-registered rungs at 12M isolated
what binds the self-play bootstrap: a better *input* (encoder v2) did not (+0.009),
a better *signal* (Huang & Lee's shaping) did not (+0.0135, n.s.), and a better
*structure* — entity embeddings, a shared per-Pokémon subnet, DeepSets team pooling,
one shared per-action scorer — moved it **+0.151** at matched parameters. That run
cleared the pre-registered success milestone (**M3, "past SH": ≥0.510**), guarded by
head-to-heads against non-SH anchors (beats the Foul Play clone 0.657 pooled; the
engine's edge over our best shrank 0.876 → 0.824), and was formally claimed
2026-08-09. Per an adversarial prior-art search (2026-08-10, scope in
`SESSION_LOGS.md`): **no documented instance found of a pure self-play agent past
the scripted benchmark in gen1** — stated as "none found," not "proven first". A 4.2×
scale run (50M) then read out at **0.5802 pooled — crediting its pre-registered bar,
with a recorded caveat**: the seed spread tripled (0.509–0.659), so the scale effect
is not yet seed-robust; adjudication and the remaining anchor read are in
`SESSION_LOGS.md`. The first post-50M lever — a privileged (asymmetric) critic that
sees the opponent's true hidden team during training, itself with no documented
Pokémon-RL instance found — read out null at 12M × 5 seeds (0.5364 pooled) and was
killed by its own pre-registered falsifier: the critic's explained variance rose on
every seed while the win rate did not move, and its feature rank stayed as collapsed
as the controls' — the value function learned things the policy could not use. The
next lever — a regenerative L2-toward-init regularizer against the measured
plasticity pathology — read out at **+0.045 pooled over a 5-seed comparator but was
not credited** under the pre-registered seed-clustered rule: one seed hit 0.6463
(the repo's highest 12M result, above even the 50M pooled number) while its
arm-mates sat at 0.561. Its mechanism reads did land: the regularizer bound at the
predicted strength, critic feature rank recovered to 2-3× the control band, and the
final-vs-peak checkpoint gap shrank as predicted. The run also refreshed the
comparator with two fresh seeds, which landed 0.083 apart — the honest headline is
that **seed variance at 12M is large enough that win-rate deltas of the size these
levers produce cannot clear a seed-robust bar**; mechanism evidence has to carry
such rungs, and scale (50M+) is where win-rate claims live. The next lever broke
that pattern (2026-08-14): **an auxiliary opponent-action prediction loss** — the
agent's pooled context must also predict which of six action classes the opponent
takes each turn, labels harvested free from self-play's second seat — read out at
**0.6185 pooled × 5 seeds, +0.074 over its frozen comparator, crediting under the
seed-clustered rule with margin** (operative bar 0.583), the first credited lever
since the 50M run and the first ever under the stricter clustered rule. Its
mechanism co-primary fired at the minimum attainable exact-permutation p (1/252,
both label spaces): the pooled context became ~4× more decodable for the
opponent's next action on a frozen reference tape. **The pre-registered placebo
arm has now run and widened that scope (2026-08-16):** five more lanes trained
12M with the opponent-action labels SHUFFLED within each legality class —
identical head, identical coefficient, identical cadence, zero information —
land at **0.5415 pooled, dead on the 0.5445 comparator**, while the real labels
give 0.6185. The gap is +0.077 against a 0.034 seed-clustered bar, and the
shuffle is verified to have destroyed the information rather than merely
perturbed it (held-out gap-closure |g| = 0.012 on the placebo's own mirror
tapes, versus 0.75 for the real head; the placebo head sits at its marginal
floor on 4 of 5 lanes). The mechanism atom and the dormancy shift both separate
treatment from placebo at the minimum attainable p (1/252). So what is licensed
is now **"an explicit opponent-action model helps"** — with two confounds named
in the same breath: the labels are the agent's own mirror-self, so this is as
much a self-model as an opponent model, and the evidence is that the
representation became more decodable, not that the policy consults it. It is
NOT "the agent learned a belief state". One alternative stays live rather than
refuted: the placebo delivered only 3-31% of the real arm's auxiliary gradient
into the trunk (it converges to its floor and stops pushing), so "a generic
auxiliary gradient of matched size would help too" is untested here, not
eliminated.
That run also completed the pre-registered milestone ladder: **M4 — surpassing
the Foul Play behaviour clone under the locked protocol — was formally claimed
2026-08-15** (pooled 0.6185 vs the clone's 5×3000 re-scores of 0.5503
final / 0.5837 val-peak, guarded by two-orientation head-to-heads: 0.719
pooled over the clone, an edge that moved with the vs-SH number rather than
staying flat). M1–M4 are now all claimed on pure from-scratch self-play; the
search engine itself (0.8307) remains the open frontier.

**Honest scoping.** SH parity ≈ 40% GXE in human-ladder terms; the strongest
documented Gen 1 agents (Metamon-family, human-replay-bootstrapped offline RL) reach
~80% GXE. This chase is a *purity-lane* first in a generation where it had not been
shown — it is not a strength record and does not enter the published field. The
roadmap is `DESIGN.md` (r7 ratified). §12's queue is now spent: the privileged critic
read NULL, the regenerative-L2 rung was letter-met but not credited, and the auxiliary
opponent-TEAM head (D19) was **killed at zero lanes**. Not because gen-1 randbats teams
are random — the generator's type and weakness caps of 2 bind hard, so there is real
structure — but because of its *shape*: 88–90% of it is a deterministic cap mask, a
closed-form function of what the opponent has already revealed, leaving a genuine belief
residual of ~0.03 nats against a 4.955-nat target (measurement and controls in
`results/d19_closeout/`). It was re-targeted to opponent
*action* prediction, which became D25 and is the one lever that credited. What remains
is an open maintainer call on whether to spend the chase's last ~2 lane-days or close
the chapter here.

## Setup

Python 3.13, CPU-first (the RL loop is collection-bound; see `STATUS.md`).

```
pip install -e ".[dev]"
```

All dependencies are pinned exactly in `pyproject.toml`.

The Showdown server is vendored at `showdown/` (gitignored). If setting it up fresh,
clone it via `scripts/setup_showdown.sh`, then set `simulator: 4` in
`showdown/config/config.js` (~line 111) — it is worth +81% collection throughput.

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
python scripts/score_ladder.py <run_dir>
```

W&B logging defaults to offline; `scripts/extract_history.py <run_dir>` extracts
`history.csv` from a run directory.

## Repo layout

- `rl/` — training harness, PPO agent, Showdown env wrapper, action masking
- `scripts/` — evaluation, BC dataset generation and training, throughput probes
- `configs/` — run configs; headers carry each experiment's pre-registration
- `tests/` — harness and env contract tests (`pytest tests/`)
- `prior_work/` — verified index of external systems and papers (`prior_work/README.md`)
- `DESIGN.md` — live design proposal (under review)
- `STATUS.md` — current state, next actions

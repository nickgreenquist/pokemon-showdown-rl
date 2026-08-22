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

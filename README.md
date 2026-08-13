# pokemon-showdown-rl

A reinforcement-learning agent for **Pokémon Showdown Gen 1 random battles**
(`gen1randombattle`) — battle phase only, no team building. The agent plays through
[poke-env](https://github.com/hsahovic/poke-env) against a local
[Pokémon Showdown](https://github.com/smogon/pokemon-showdown) server.

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
rows marked * are single-seed probes, not headline-grade.

| agent | win rate |
|---|---|
| PPO trained *against* SH, 12M, flat / LR-annealed | 0.4330† / 0.4607† |
| Behaviour clone of SH (813k rows) | 0.4657† |
| SH vs SH mirror (parity point; caps SH imitators only) | 0.489 |
| **Pure self-play**, 12M, flat MLP — the plateau | 0.3996 ± 0.0052 |
| + H&L reward shaping (γ0.95, 5-term zero-sum) — null | 0.4131 ± 0.0052 |
| **+ entity architecture (DeepSets + pointer head), 12M** | **0.5509 ± 0.0052** |
| **same recipe at 50M — current best** | **0.5802 ± 0.0052** |
| + privileged (asymmetric) critic, 12M, 5 seeds — null | 0.5364 ± 0.0066 |
| + regenerative L2-toward-init, 12M, 3 seeds — letter-met, not credited | 0.5897 ± 0.0066 |
| Behaviour clone of Foul Play (graded final / val-peak) | 0.5490 / 0.5777 |
| Foul Play engine (search bot, our patches) — eval anchor | 0.8307* |

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
such rungs, and scale (50M+) is where win-rate claims live.

**Honest scoping.** SH parity ≈ 40% GXE in human-ladder terms; the strongest
documented Gen 1 agents (Metamon-family, human-replay-bootstrapped offline RL) reach
~80% GXE. This chase is a *purity-lane* first in a generation where it had not been
shown — it is not a strength record and does not enter the published field. The
roadmap is `DESIGN.md` (r7 ratified; §12's first lever, the privileged critic, is
read out and killed — a regenerative-L2 plasticity rung is next in its queue).

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

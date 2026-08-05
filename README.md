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
package still contains the predecessor's from-scratch training spine (PPO is the learner
in use; DQN/SAC/Connect-4/MinAtar code came along in the move and prunes over time).

## Results so far

Win rate vs poke-env's `SimpleHeuristicsPlayer` (SH). Protocol: final checkpoint,
1000 battles/seed, 3 seeds pooled, ties count as non-wins, deterministic policy.

| agent | win rate |
|---|---|
| PPO, 6M steps, flat LR | 0.3923 ± 0.0089 |
| **PPO, 6M steps, LR annealed to 0** | **0.4433 ± 0.0091** |
| Behaviour clone of SH (same encoder + trunk) | 0.453–0.465 |
| SH vs SH mirror (reference ceiling for SH-derived agents) | 0.489 |

The mirror baseline sits below 0.5 because ties count as non-wins. Two levers are
credited with real effects: rollout length 128→512 (+0.037 pooled) and a linear LR
anneal (+0.051 pooled). The supervised clone beating every RL result through the
identical network established that the current plateau is training-side, not a
representation problem — that finding drives the roadmap (see `DESIGN.md`).

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

"""P3 — team-luck variance decomposition (diagnostic, outside the ladder).

How much of a battle's win/loss is decided by the server's team draw rather
than by anything the policy does? Run the locked eval protocol against the
config's eval opponent while recording, per battle, the pre-battle draw —
our six species and the opponent's lead — plus the outcome; then measure
how much outcome variance those draw features explain out-of-fold.

Feature discipline: our full team and the opponent's LEAD are fixed at
battle start, so they are legitimate draw features. The opponent's revealed
team is NOT — longer battles reveal more mons, so revealed-count is
post-treatment and leaks outcome. It is recorded for the curious and
excluded from the analysis.

Interpretation guard: team luck does NOT widen the se of a win-rate mean
(a mixture of Bernoullis has the same block variance as a plain Bernoulli
at the pooled p), so this is not about eval precision. It prices the
TRAINING signal: under terminal-only ±1 reward, the share of the outcome
decided by the draw is noise every gradient step must average over.

Analysis: ridge linear-probability on {own-species multi-hot, lead one-hot},
outcome centered per checkpoint (3 checkpoints = 3 intercepts), 5-fold CV
R^2 maximized over a lambda grid — reported against a permutation null that
re-runs the identical procedure (same folds, same grid, same max) on
shuffled-within-checkpoint outcomes, so the selection optimism cancels.

    python scripts/p3_team_luck.py runs/<run>/ckpt.pt [more ckpts] --episodes 1000
    python scripts/p3_team_luck.py --analyze-only runs/<run>/p3_team_luck.json ...
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import EVAL_SEED_OFFSET
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def collect(ckpt_path: str, episodes: int) -> Path:
    ckpt = load_checkpoint(ckpt_path)
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)
    env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    rows = []
    for episode in range(episodes):
        # The locked re-eval ladder: seeds past the training-time evals.
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + cfg.eval_episodes + episode)
        mask = info.get("action_mask")
        done = False
        while not done:
            obs, reward, terminated, truncated, info = env.step(
                agent.act(obs, mask, deterministic=True)
            )
            mask = info.get("action_mask")
            done = terminated or truncated
        battle = env.unwrapped._env.env.battle1
        opp_revealed = [mon.species for mon in battle.opponent_team.values()]
        rows.append(
            {
                "outcome": info["outcome"],
                "own_team": sorted(mon.species for mon in battle.team.values()),
                "opp_lead": opp_revealed[0],  # first revealed = the lead
                "opp_revealed": opp_revealed,  # post-treatment; analysis excludes
            }
        )
    env.close()
    out = Path(ckpt_path).parent / "p3_team_luck.json"
    out.write_text(json.dumps({"checkpoint": ckpt_path, "episodes": episodes, "rows": rows}) + "\n")
    print(f"{out}: {len(rows)} battles, win rate {np.mean([r['outcome'] == 1 for r in rows]):.3f}")
    return out


def _cv_r2(X: np.ndarray, y: np.ndarray, folds: np.ndarray, lambdas: np.ndarray) -> float:
    """Max-over-lambda 5-fold CV R^2 (identical procedure for real and null)."""
    best = -np.inf
    for lam in lambdas:
        sse = sst = 0.0
        for k in range(5):
            tr, te = folds != k, folds == k
            A = X[tr].T @ X[tr] + lam * np.eye(X.shape[1])
            w = np.linalg.solve(A, X[tr].T @ y[tr])
            resid = y[te] - X[te] @ w
            sse += float(resid @ resid)
            sst += float(y[te] @ y[te])
        best = max(best, 1.0 - sse / sst)
    return best


def analyze(paths: list[Path], permutations: int = 200, seed: int = 0) -> None:
    rows, ckpt_ids = [], []
    for i, p in enumerate(paths):
        data = json.loads(Path(p).read_text())
        rows += data["rows"]
        ckpt_ids += [i] * len(data["rows"])
    ckpt_ids = np.array(ckpt_ids)
    species = sorted({s for r in rows for s in r["own_team"]} | {r["opp_lead"] for r in rows})
    idx = {s: j for j, s in enumerate(species)}
    d = len(species)
    X = np.zeros((len(rows), 2 * d))
    for i, r in enumerate(rows):
        for s in r["own_team"]:
            X[i, idx[s]] = 1.0
        X[i, d + idx[r["opp_lead"]]] = 1.0
    y = np.array([1.0 if r["outcome"] == 1 else 0.0 for r in rows])
    # Center outcome and features within checkpoint: 3 free intercepts, so
    # checkpoint-strength differences cannot masquerade as team signal.
    for i in range(len(paths)):
        m = ckpt_ids == i
        y[m] -= y[m].mean()
        X[m] -= X[m].mean(axis=0)

    rng = np.random.default_rng(seed)
    folds = rng.integers(0, 5, size=len(y))
    lambdas = np.array([1.0, 10.0, 100.0, 1000.0])
    r2 = _cv_r2(X, y, folds, lambdas)
    null = []
    for _ in range(permutations):
        y_perm = y.copy()
        for i in range(len(paths)):
            m = np.where(ckpt_ids == i)[0]
            y_perm[m] = y_perm[rng.permutation(m)]
        null.append(_cv_r2(X, y_perm, folds, lambdas))
    null = np.array(null)
    p_val = float(np.mean(null >= r2))
    print(f"n={len(y)} battles, {d} species, features=own-team multi-hot + opp-lead one-hot")
    print(f"CV R^2 (max over lambda, 5-fold): {r2:.4f}")
    print(f"permutation null ({permutations}x): median {np.median(null):.4f}, "
          f"95th pct {np.percentile(null, 95):.4f}, p = {p_val:.3f}")
    print(f"draw-explained share of outcome variance (lower bound): "
          f"{max(r2, 0.0):.1%} vs null median {max(float(np.median(null)), 0.0):.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="checkpoints to collect, or JSONs with --analyze-only")
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--permutations", type=int, default=200)
    args = parser.parse_args()
    jsons = [Path(p) for p in args.paths] if args.analyze_only else [
        collect(p, args.episodes) for p in args.paths
    ]
    analyze(jsons, permutations=args.permutations)


if __name__ == "__main__":
    main()

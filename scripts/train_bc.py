"""Behavioral cloning of a scripted bot through the Phase-5 stack — the
training half of the encoder-ceiling diagnostic (PLAN.md P4).

    python scripts/train_bc.py --data data/bc_heuristics_vs_heuristics.npz

Trains the EXACT actor the capstone RL runs use — built through make_agent
from the milestone-3 hparams, so `hidden_sizes` threads identically and the
checkpoint re-evaluates through scripts/eval_checkpoint.py unchanged — on
masked cross-entropy against the expert's own action. No server needed:
this step is offline over the recorded dataset.

    python scripts/eval_checkpoint.py runs/<run>/checkpoint.pt --episodes 1000

is the headline instrument (the clone plays the bot it copied, deterministic
policy, the standard eval protocol); the agreement numbers printed here are
the training-side read.

Pre-registered caveat, to be fixed in the design session before any run is
interpreted: a clone that CANNOT reproduce the bot it copies indicts the
encoder — the ~0.4 plateau is explained and the encoder must change. A
clone that CAN is only one-directional evidence: representable under
supervision does not imply reachable by PPO under a terminal-only reward.

Two measurement choices that keep the number honest:

- Holdout is by BATTLE, never by row. Consecutive decisions in one battle
  share a team, a turn context and an opponent, so a row-level split leaks
  validation states into training and inflates agreement.
- Agreement is reported twice. Decisions with a single legal action are
  free for any policy (the mask decides them), so `agreement_free` over
  the multi-choice rows is the real number, and `chance_free` — uniform
  over legal actions on those same rows — is its floor.

The critic rides along untrained: the dataset carries no value labels, and
nothing downstream reads it (deterministic eval is an argmax over masked
actor logits). It exists so the checkpoint keeps the standard shape.
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F

from rl.common.checkpoint import save_checkpoint
from rl.common.config import Config
from rl.common.masking import masked_logits
from rl.envs.showdown import OBS_DIM
from rl.train import make_agent

# The milestone-3 capstone hparams (configs/showdown_heur_512_s0.yaml).
# Only the net shape matters for a supervised fit; the PPO-specific values
# ride along so the config round-trips through Config/make_agent and every
# existing instrument reads the checkpoint unchanged.
AGENT = dict(
    algo="ppo", lr=2.5e-4, gamma=1.0, gae_lambda=0.95, rollout_steps=128,
    epochs=4, minibatches=4, clip_eps=0.2, entropy_coef=0.01,
    value_coef=0.5, max_grad_norm=0.5,
)


def battle_split(battle_ids: np.ndarray, val_frac: float, seed: int):
    """Row indices split by BATTLE: whole battles go to one side or the
    other. Returns (train_idx, val_idx, n_val_battles)."""
    battles = np.unique(battle_ids)
    order = np.random.default_rng(seed).permutation(battles)
    n_val = max(1, int(round(len(battles) * val_frac)))
    val_battles = set(order[:n_val].tolist())
    is_val = np.array([b in val_battles for b in battle_ids])
    return np.flatnonzero(~is_val), np.flatnonzero(is_val), n_val


@torch.no_grad()
def evaluate(actor, obs, masks, actions, free) -> dict[str, float]:
    """Cross-entropy plus agreement, overall and over the multi-choice rows."""
    logits = masked_logits(actor(obs), masks)
    picks = logits.argmax(dim=-1)
    agree = (picks == actions).float()
    return {
        "val_loss": float(F.cross_entropy(logits, actions)),
        "agreement": float(agree.mean()),
        "agreement_free": float(agree[free].mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/bc_heuristics_vs_heuristics.npz")
    parser.add_argument("--hidden", type=int, nargs="+", default=[512, 512],
                        help="actor/critic hidden sizes; the capstone's [512, 512]")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-name", default=None,
                        help="default bc_<expert>_<hidden>_s<seed>")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-frac", type=float, default=0.1)
    args = parser.parse_args()

    data = np.load(args.data)
    expert = str(data["expert"])
    hidden = "x".join(str(h) for h in args.hidden)
    run_name = args.run_name or f"bc_{expert}_{hidden}_s{args.seed}"

    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    cfg = Config(
        env_id="Showdown-v0", seed=args.seed, total_steps=0, eval_every=0,
        # eval_episodes is not used here (no training-time eval), but it is
        # what eval_checkpoint.py starts its seed ladder from: 100 puts the
        # clone's re-eval on the same rung the campaign's 1000-battle finals
        # used. Showdown episodes are server-rolled and not seed-reproducible
        # anyway, so this is consistency, not pairing.
        eval_episodes=100, run_name=run_name, logger="tensorboard",
        eval_win_rate=True,
        selfplay={"opponent": expert, "eval_opponent": expert},
        agent={**AGENT, "hidden_sizes": list(args.hidden)},
    )
    # Spaces only: a real env here would open websockets just to read shapes
    # (eval_checkpoint.py's cross-play path is the precedent). Bounds mirror
    # ShowdownSingles.observation_spaces.
    n_actions = data["masks"].shape[1]
    agent = make_agent(cfg, SimpleNamespace(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(n_actions),
    ))

    obs = torch.as_tensor(data["obs"], dtype=torch.float32)
    masks = torch.as_tensor(data["masks"], dtype=torch.bool)
    actions = torch.as_tensor(data["actions"], dtype=torch.int64)
    assert obs.shape[1] == OBS_DIM, f"dataset is {obs.shape[1]}-dim, encoder is {OBS_DIM}"
    train_idx, val_idx, n_val_battles = battle_split(
        data["battle_ids"], args.val_frac, args.seed
    )
    n_battles = len(np.unique(data["battle_ids"]))
    # Multi-choice rows: the ones a clone can actually get wrong.
    free = masks[val_idx].sum(dim=1) > 1
    chance_free = float((1.0 / masks[val_idx].sum(dim=1)[free].float()).mean())
    print(f"{run_name}: {len(train_idx)} train / {len(val_idx)} val decisions "
          f"({n_battles - n_val_battles}/{n_val_battles} battles), expert {expert}",
          flush=True)
    print(f"val multi-choice rows {float(free.float().mean()):.3f}, "
          f"uniform-over-legal agreement on them {chance_free:.3f}", flush=True)

    # Actor only: the value head has no labels here, and handing its params
    # to the optimizer would imply otherwise.
    optimizer = torch.optim.Adam(agent.actor.parameters(), lr=args.lr)
    generator = torch.Generator().manual_seed(args.seed)
    val = torch.as_tensor(val_idx)
    history, best = [], -1.0
    for epoch in range(1, args.epochs + 1):
        perm = torch.as_tensor(train_idx)[
            torch.randperm(len(train_idx), generator=generator)
        ]
        total = 0.0
        for i in range(0, len(perm), args.batch_size):
            idx = perm[i:i + args.batch_size]
            logits = masked_logits(agent.actor(obs[idx]), masks[idx])
            loss = F.cross_entropy(logits, actions[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(idx)
        metrics = evaluate(agent.actor, obs[val], masks[val], actions[val], free)
        metrics = {"epoch": epoch, "train_loss": total / len(perm), **metrics}
        history.append(metrics)
        print(f"epoch {epoch:3d}  train loss {metrics['train_loss']:.4f}  "
              f"val loss {metrics['val_loss']:.4f}  val agreement {metrics['agreement']:.3f}  "
              f"free {metrics['agreement_free']:.3f}", flush=True)
        if metrics["agreement_free"] > best:
            best = metrics["agreement_free"]
            save_checkpoint(f"runs/{run_name}/best_checkpoint.pt", agent, epoch, cfg)

    save_checkpoint(f"runs/{run_name}/checkpoint.pt", agent, args.epochs, cfg)
    report = {
        "run_name": run_name, "data": args.data, "expert": expert,
        "hidden_sizes": list(args.hidden), "seed": args.seed,
        "epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
        "train_decisions": len(train_idx), "val_decisions": len(val_idx),
        "val_battles": n_val_battles, "val_free_frac": float(free.float().mean()),
        "chance_free": chance_free, "best_agreement_free": best,
        "history": history,
    }
    Path(f"runs/{run_name}/bc_metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote runs/{run_name}/checkpoint.pt (final) and bc_metrics.json; "
          f"best val free-agreement {best:.3f}", flush=True)


if __name__ == "__main__":
    main()

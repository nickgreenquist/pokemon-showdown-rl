"""Supervised-on-solver-labels: the architecture-ceiling diagnostic (chunk 4).

    python scripts/train_supervised.py --data data/solver_dataset.npz --kernel-size 3

Trains the EXACT nets the RL agents use — built through make_agent from
the locked PPO hparams, so kernel_size threads identically and the saved
checkpoint loads through every existing instrument — but on exact solver
labels instead of self-play: cross-entropy against a uniform distribution
over the optimal-move set (through masked_logits, the same masking path),
plus value MSE against the position's game-theoretic sign (what the
gamma=1 critic is defined to learn).

Pre-registered read (PLAN.md, 2026-07-29): this run removes coverage and
label noise as variables, so its Pons agent metrics estimate what the
architecture CAN do. Supervised ~ the RL band (agreement 0.29-0.61)
=> the encoder is the ceiling and the training-side levers are aimed at
the wrong axis; supervised >> the band => the training signal is the
ceiling, and the gap prices the levers' headroom. Run at BOTH kernels to
de-confound k4's capacity from its (worst-measured) self-play collapse.

Evaluate with scripts/pons_agent_metrics.py --allow-non-selfplay — the
flag is the honest path past the not-a-self-play-run guard, which stays
default-on for everything else.
"""

import argparse

import numpy as np
import torch
import torch.nn.functional as F

from rl.common.checkpoint import save_checkpoint
from rl.common.config import Config
from rl.common.masking import masked_logits
from rl.envs.make import make_env
from rl.train import make_agent

ILLEGAL = -100

# The locked campaign hparams (configs/connect4_pool.yaml). Only the net
# shape matters here — the PPO-specific values ride along so the config
# round-trips through Config/make_agent unchanged.
AGENT = dict(
    algo="ppo", hidden_sizes=[128], lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=128, epochs=4, minibatches=4, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/solver_dataset.npz")
    parser.add_argument("--kernel-size", type=int, default=3, choices=(3, 4))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-name", default=None,
                        help="default supervised_k<kernel>_s<seed>")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-frac", type=float, default=0.05)
    args = parser.parse_args()
    run_name = args.run_name or f"supervised_k{args.kernel_size}_s{args.seed}"

    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    cfg = Config(
        env_id="Connect4-v0", seed=args.seed, total_steps=0, eval_every=0,
        eval_episodes=0, run_name=run_name, logger="tensorboard",
        agent={**AGENT, "kernel_size": args.kernel_size},
    )
    env = make_env("Connect4-v0", seed=args.seed)
    agent = make_agent(cfg, env)
    env.close()

    data = np.load(args.data)
    x = torch.as_tensor(data["planes"], dtype=torch.float32)
    scores = torch.as_tensor(data["move_scores"], dtype=torch.int32)
    legal = scores != ILLEGAL
    best = torch.where(legal, scores, torch.tensor(-(10**6))).max(dim=1, keepdim=True).values
    target = ((scores == best) & legal).float()
    target /= target.sum(dim=1, keepdim=True)
    value = torch.as_tensor(data["value_sign"], dtype=torch.float32)

    n = len(x)
    split = np.random.default_rng(args.seed).permutation(n)
    n_val = int(n * args.val_frac)
    val_idx, train_idx = torch.as_tensor(split[:n_val]), torch.as_tensor(split[n_val:])
    print(f"{run_name}: {len(train_idx)} train / {n_val} val positions", flush=True)

    optimizer = torch.optim.Adam(agent.params, lr=args.lr)
    generator = torch.Generator().manual_seed(args.seed)
    for epoch in range(1, args.epochs + 1):
        perm = train_idx[torch.randperm(len(train_idx), generator=generator)]
        for i in range(0, len(perm), args.batch_size):
            idx = perm[i:i + args.batch_size]
            logits = masked_logits(agent.actor(x[idx]), legal[idx])
            policy_loss = -(target[idx] * F.log_softmax(logits, dim=-1)).sum(dim=-1).mean()
            value_loss = F.mse_loss(agent.critic(x[idx]).squeeze(-1), value[idx])
            optimizer.zero_grad()
            (policy_loss + value_loss).backward()
            optimizer.step()
        with torch.no_grad():
            logits = masked_logits(agent.actor(x[val_idx]), legal[val_idx])
            moves = logits.argmax(dim=-1)
            agree = target[val_idx][torch.arange(n_val), moves].gt(0).float().mean()
            v = agent.critic(x[val_idx]).squeeze(-1)
            decisive = value[val_idx] != 0
            sign_acc = (torch.sign(v[decisive]) == value[val_idx][decisive]).float().mean()
        print(f"epoch {epoch:3d}  val optimal-move agreement {agree:.3f}  "
              f"val sign acc {sign_acc:.3f}", flush=True)

    save_checkpoint(f"runs/{run_name}/checkpoint.pt", agent, step=0, cfg=cfg)
    print(f"wrote runs/{run_name}/checkpoint.pt", flush=True)


if __name__ == "__main__":
    main()

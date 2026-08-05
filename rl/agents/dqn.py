"""DQN: Q-learning with function approximation — the same TD update as the
tabular agent, but the table becomes a network, and the deadly triad
(function approximation + bootstrapping + off-policy) costs the convergence
guarantee. Two stabilizers tame it in practice:

- Replay buffer: gradient steps use uniform random minibatches from the
  whole interaction history instead of the (correlated) latest transition.
  Off-policy learning is what makes training on stale data legal.
- Target network: TD targets are computed by a frozen copy of the Q-network,
  synced every `target_update_every` gradient steps, so each stretch of
  training is a regression toward stationary labels rather than a chase
  after targets that move with every update.

With `hidden_sizes=[]` the Q-network is a single linear layer — the Phase 1
on-ramp. Add hidden layers via config and this same class is DQN proper.

Config toggles (all default off = vanilla DQN):
- `double`: Double DQN (van Hasselt et al. 2016). The vanilla target
  max_a Q_target(s', a) lets one network both select and evaluate the best
  next action; with noisy estimates the max preferentially picks whichever
  action is currently over-estimated, so targets are systematically
  optimistic. Double DQN selects with the online net, evaluates with the
  target net — their errors are less correlated, damping the bias.
- `dueling`: dueling head (see DuelingMLP) — Q = V(s) + A(s, a) - mean(A).
- `n_step`: n-step returns. The target becomes
  r_t + ... + gamma^{n-1} r_{t+n-1} + gamma^n max Q(s_{t+n}) — n real
  rewards before the bootstrap term, so reward information propagates n
  states per update and the target leans less on early garbage estimates
  (less bias), at the cost of higher-variance targets and a mild
  off-policy impurity (the intermediate actions came from an old policy).
"""

from collections import deque
from typing import Any

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F

from rl.agents.base import Agent
from rl.buffers.replay import ReplayBuffer
from rl.common.masking import masked_logits, masked_sample
from rl.networks.conv import ConvQNet
from rl.networks.mlp import DuelingMLP, mlp


class NStepAccumulator:
    """Assembles n-step transitions from the per-step stream.

    Holds up to n pending (obs, action, reward, mask) entries. When the
    window fills, the oldest entry is emitted as an n-step transition; when
    an episode ends for any reason, all pending entries are flushed as
    partial-window transitions (m < n steps, discount gamma^m). Truncation
    must flush too — not for bootstrapping (a truncated episode still
    bootstraps) but because the next stream entry belongs to a new episode
    and must not be chained to this one.

    Masks ride the window: every emitted transition carries the oldest
    entry's acting mask plus the mask of its bootstrap state s_{t+m} — the
    flush-time next state. On an episode-end flush all partials share the
    terminal state's next_mask: a correctly-shaped array even when
    `terminated` makes the bootstrap (and therefore the mask) unused.
    """

    def __init__(self, n: int, gamma: float):
        self.n = n
        self.gamma = gamma
        self._pending: deque = deque()

    def push(self, obs, action, reward, next_obs, terminated, truncated, mask, next_mask) -> list[tuple]:
        """Feed one env transition; return the buffer-ready transitions
        (obs, action, n_step_return, next_obs, terminated, discount, mask,
        next_mask) it completes — usually 0 or 1, up to n on an episode end."""
        self._pending.append((obs, action, reward, mask))
        out = []
        if terminated or truncated:
            while self._pending:
                out.append(self._emit(next_obs, terminated, next_mask))
                self._pending.popleft()
        elif len(self._pending) == self.n:
            out.append(self._emit(next_obs, False, next_mask))
            self._pending.popleft()
        return out

    def _emit(self, next_obs, terminated, next_mask) -> tuple:
        ret = 0.0
        for i, (_, _, reward, _) in enumerate(self._pending):
            ret += self.gamma**i * reward
        obs, action, _, mask = self._pending[0]
        return (
            obs, action, ret, next_obs, float(terminated),
            self.gamma ** len(self._pending), mask, next_mask,
        )


class DQNAgent(Agent):
    def __init__(
        self,
        observation_space: gym.Space,
        action_space: gym.Space,
        device: str,
        lr: float,
        gamma: float,
        epsilon_start: float,
        epsilon_end: float,
        epsilon_decay_steps: int,
        buffer_capacity: int,
        batch_size: int,
        learning_starts: int,
        target_update_every: int,
        hidden_sizes: list[int],
        optimizer: str = "adam",
        double: bool = False,
        dueling: bool = False,
        n_step: int = 1,
    ):
        # Q(s, ·) needs a flat obs vector or channel-first image planes,
        # plus enumerable actions.
        if not isinstance(observation_space, gym.spaces.Box) or len(observation_space.shape) not in (1, 3):
            raise TypeError("DQNAgent requires a flat or channel-first image Box observation space")
        if not isinstance(action_space, gym.spaces.Discrete):
            raise TypeError("DQNAgent requires a Discrete action space")
        self.action_space = action_space
        self.device = torch.device(device)
        n_actions = int(action_space.n)
        if len(observation_space.shape) == 3:
            # Rank-3 obs (e.g. MinAtar planes) select the conv net; no config key.
            def build():
                return ConvQNet(observation_space.shape, hidden_sizes, n_actions, dueling)
        else:
            def build():
                net = DuelingMLP if dueling else mlp
                return net(observation_space.shape[0], hidden_sizes, n_actions)
        self.q = build().to(self.device)
        self.q_target = build().to(self.device)
        self.q_target.load_state_dict(self.q.state_dict())
        self.q_target.requires_grad_(False)
        # Adam by default; centered RMSprop(alpha=0.95, eps=0.01) is the
        # MinAtar paper's exact optimizer, wired in (not just noted) because
        # it's a planned ablation whenever our curves diverge from theirs.
        if optimizer == "adam":
            self.optimizer = torch.optim.Adam(self.q.parameters(), lr=lr)
        elif optimizer == "rmsprop":
            self.optimizer = torch.optim.RMSprop(
                self.q.parameters(), lr=lr, alpha=0.95, eps=0.01, centered=True
            )
        else:
            raise ValueError(f"unknown optimizer {optimizer!r}")
        # Keyword args, not positional: the buffer's signature carries action
        # shape/dtype now (the continuous track), so a positional call would
        # silently bind n_actions to obs_dtype.
        self.buffer = ReplayBuffer(
            buffer_capacity,
            observation_space.shape,
            obs_dtype=observation_space.dtype,
            n_actions=n_actions,
        )
        self.accumulator = NStepAccumulator(n_step, gamma)
        self.double = double
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay_steps = epsilon_decay_steps
        self.batch_size = batch_size
        self.learning_starts = learning_starts
        self.target_update_every = target_update_every
        self.transitions = 0  # env transitions seen; drives the epsilon anneal
        self.grad_steps = 0  # gradient steps taken; drives target syncs

    def _epsilon(self) -> float:
        frac = min(self.transitions / self.epsilon_decay_steps, 1.0)
        return self.epsilon_start + frac * (self.epsilon_end - self.epsilon_start)

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> int:
        if not deterministic and np.random.random() < self._epsilon():
            # Exploration respects the mask too: uniform over legal only.
            return masked_sample(self.action_space, action_mask)
        with torch.no_grad():
            obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
            mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=self.device)
            # Batch dim: Conv2d requires it, Linear tolerates it; argmax
            # flattens the (1, A) output either way (mask broadcasts).
            return int(masked_logits(self.q(obs_t.unsqueeze(0)), mask_t).argmax().item())

    def update(self, batch: Any) -> dict[str, float]:
        # The train loop hands over the fresh transition each step; it runs
        # through the n-step accumulator into the buffer, and the gradient
        # step trains on a sampled batch.
        self.transitions += 1
        for transition in self.accumulator.push(*batch):
            self.buffer.add(*transition)
        if len(self.buffer) < self.learning_starts:
            return {}

        obs, actions, rewards, next_obs, terminated, discounts, _masks, next_masks = (
            self.buffer.sample(self.batch_size)
        )
        # Obs get an explicit float32: the buffer may hold bool planes (MinAtar).
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.device)
        actions_t = torch.as_tensor(actions, device=self.device)
        rewards_t = torch.as_tensor(rewards, device=self.device)
        next_obs_t = torch.as_tensor(next_obs, dtype=torch.float32, device=self.device)
        terminated_t = torch.as_tensor(terminated, device=self.device)
        discounts_t = torch.as_tensor(discounts, device=self.device)
        next_masks_t = torch.as_tensor(next_masks, device=self.device)

        q_pred = self.q(obs_t).gather(1, actions_t.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            # The bootstrap max/argmax ranges over actions legal in s'
            # (next_mask): bootstrapping from an action that could never be
            # taken is the silent-corruption path masking exists to close.
            if self.double:
                # Online net selects the action, target net evaluates it.
                next_actions = masked_logits(self.q(next_obs_t), next_masks_t).argmax(
                    dim=1, keepdim=True
                )
                next_q = self.q_target(next_obs_t).gather(1, next_actions).squeeze(1)
            else:
                next_q = masked_logits(self.q_target(next_obs_t), next_masks_t).max(dim=1).values
            # Bootstrap only through non-terminal next states (same rule as
            # tabular Q: truncation is a cut, not an ending).
            target = rewards_t + discounts_t * (1.0 - terminated_t) * next_q
        # Huber, not MSE: TD targets are noisy early on; linear loss beyond
        # |error| = 1 keeps outlier targets from dominating the gradient.
        loss = F.smooth_l1_loss(q_pred, target)

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self.grad_steps += 1
        if self.grad_steps % self.target_update_every == 0:
            self.q_target.load_state_dict(self.q.state_dict())
        return {"loss/q": float(loss.item()), "loss/q_pred_mean": float(q_pred.mean().item())}

    def state_dict(self) -> dict[str, Any]:
        # Buffer and n-step accumulator are deliberately not checkpointed:
        # restore serves eval/watch; resuming training refills them.
        return {
            "q": self.q.state_dict(),
            "q_target": self.q_target.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "transitions": self.transitions,
            "grad_steps": self.grad_steps,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.q.load_state_dict(state["q"])
        self.q_target.load_state_dict(state["q_target"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.transitions = state["transitions"]
        self.grad_steps = state["grad_steps"]

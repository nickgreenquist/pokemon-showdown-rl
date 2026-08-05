"""REINFORCE: the policy-gradient core in isolation — the Phase 2 on-ramp
before PPO stacks GAE + clipping + vectorization on top.

Value-based methods (tabular Q, DQN) learn Q and act by argmax; here the
policy itself is the parameterized object — a network mapping obs to action
logits, trained by gradient ascent on expected return. The env sits between
the parameters and the reward, so nothing backpropagates through
`env.step()`; the score-function estimator (the policy gradient theorem)
sidesteps it:

    grad J = E[ sum_t grad log pi(a_t | s_t) * G_t ]

Only the log-probability of the agent's own actions is differentiated: each
action's log-prob is pushed up in proportion to the return that followed it
(and, since probabilities sum to one, every other action's is implicitly
pushed down). Unbiased, but Monte Carlo — high variance, the mirror image
of TD's biased-but-low-variance bootstrap. Two gradient-preserving variance
cuts, each foreshadowing a PPO component:

- Reward-to-go: weight log pi(a_t | s_t) by the return from t onward, not
  the whole-episode return — an action can't cause rewards that preceded
  it. Same expectation, less variance.
- Return normalization within the episode: subtracting anything that
  doesn't depend on the action leaves the gradient unbiased; normalizing is
  the cheap stand-in for a learned V(s) baseline (VPG), which becomes
  PPO's critic.

On-policy: the gradient is an expectation under the *current* policy, so
each episode is used for exactly one gradient step and discarded — the
opposite of DQN's replay. PPO's clipped objective exists to wring several
steps from a batch before staleness breaks this estimator.

Truncation caveat: Monte Carlo has no value function to bootstrap the tail
of a cut episode, so at a time limit (CartPole's 500-step cap) G_t is
biased low. Treated as an episode end here; the critic takes over this job
in PPO.
"""

from typing import Any

import gymnasium as gym
import numpy as np
import torch
from torch.distributions import Categorical

from rl.agents.base import Agent
from rl.common.masking import masked_entropy, masked_logits
from rl.networks.mlp import mlp


class ReinforceAgent(Agent):
    def __init__(
        self,
        observation_space: gym.Space,
        action_space: gym.Space,
        device: str,
        lr: float,
        gamma: float,
        hidden_sizes: list[int],
    ):
        if not isinstance(observation_space, gym.spaces.Box) or len(observation_space.shape) != 1:
            raise TypeError("ReinforceAgent requires a flat Box observation space")
        if not isinstance(action_space, gym.spaces.Discrete):
            raise TypeError("ReinforceAgent requires a Discrete action space")
        self.device = torch.device(device)
        self.gamma = gamma
        self.policy = mlp(observation_space.shape[0], hidden_sizes, int(action_space.n)).to(
            self.device
        )
        self.optimizer = torch.optim.Adam(self.policy.parameters(), lr=lr)
        # The episode in progress; cleared after its one gradient step.
        self._obs: list[Any] = []
        self._actions: list[int] = []
        self._rewards: list[float] = []
        # Masks are stored and reapplied at the episode-end recompute: the
        # recomputed log-probs must come from the same masked distribution
        # the actions were sampled under (see rl/common/masking.py).
        self._masks: list[Any] = []
        self.episodes = 0  # completed episodes = gradient steps taken

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> int:
        with torch.no_grad():
            mask_t = torch.as_tensor(action_mask, dtype=torch.bool, device=self.device)
            logits = masked_logits(
                self.policy(torch.as_tensor(obs, dtype=torch.float32, device=self.device)),
                mask_t,
            )
            if deterministic:
                # Eval-time policy: the mode. Exploration needs no epsilon —
                # it lives in the sampling itself.
                return int(logits.argmax().item())
            return int(Categorical(logits=logits).sample().item())

    def update(self, batch: Any) -> dict[str, float]:
        # The train loop hands over the fresh transition each step; it
        # accumulates until the episode ends, then one gradient step trains
        # on the whole episode.
        obs, action, reward, _, terminated, truncated, mask, _next_mask = batch
        self._obs.append(obs)
        self._actions.append(action)
        self._rewards.append(reward)
        self._masks.append(mask)
        if not (terminated or truncated):
            return {}

        # Discounted reward-to-go, right to left: G_t = r_t + gamma * G_{t+1}.
        returns = [0.0] * len(self._rewards)
        g = 0.0
        for t in range(len(self._rewards) - 1, -1, -1):
            g = self._rewards[t] + self.gamma * g
            returns[t] = g
        returns_t = torch.as_tensor(returns, dtype=torch.float32, device=self.device)
        # Population std (correction=0): a one-step episode normalizes to
        # zero instead of nan.
        returns_t = (returns_t - returns_t.mean()) / (returns_t.std(correction=0) + 1e-8)

        # Log-probs are recomputed in one batched forward pass — exact, since
        # the policy hasn't changed since the actions were sampled — under the
        # stored masks, i.e. the same distribution the actions came from.
        obs_t = torch.as_tensor(np.stack(self._obs), dtype=torch.float32, device=self.device)
        actions_t = torch.as_tensor(self._actions, device=self.device)
        masks_t = torch.as_tensor(np.stack(self._masks), device=self.device)
        logits = self.policy(obs_t)
        dist = Categorical(logits=masked_logits(logits, masks_t))
        loss = -(dist.log_prob(actions_t) * returns_t).mean()

        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        self._obs.clear()
        self._actions.clear()
        self._rewards.clear()
        self._masks.clear()
        self.episodes += 1
        # Entropy is the PG health metric: a premature fall toward zero means
        # the policy went near-deterministic before learning finished —
        # exploration is gone. PPO makes this a tuned bonus; here it's watched.
        return {
            "loss/policy": float(loss.item()),
            "loss/entropy": float(masked_entropy(logits, masks_t).mean().item()),
        }

    def state_dict(self) -> dict[str, Any]:
        # The episode in progress is deliberately not checkpointed: restore
        # serves eval/watch; resuming training restarts the episode.
        return {
            "policy": self.policy.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "episodes": self.episodes,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.policy.load_state_dict(state["policy"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.episodes = state["episodes"]

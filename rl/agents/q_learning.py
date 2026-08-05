"""Tabular Q-learning: the Phase 0 proof that one agent genuinely learns
through the harness. A lookup table, no network — the smallest possible
value-based agent, and the conceptual ancestor of DQN.

Q-learning is off-policy TD control: after every transition it nudges
Q[s, a] toward `r + gamma * max_a' Q[s', a']`. The max makes it off-policy —
the target assumes greedy behavior from s' onward, regardless of the
(epsilon-greedy) action actually taken there.
"""

from typing import Any

import gymnasium as gym
import numpy as np

from rl.agents.base import Agent
from rl.common.masking import NEG, masked_sample


class QLearningAgent(Agent):
    def __init__(
        self,
        observation_space: gym.Space,
        action_space: gym.Space,
        lr: float,
        gamma: float,
        epsilon_start: float,
        epsilon_end: float,
        epsilon_decay_steps: int,
    ):
        # A lookup table needs enumerable states and actions. This agent is
        # deliberately discrete-only (the shared harness is not).
        if not isinstance(observation_space, gym.spaces.Discrete) or not isinstance(
            action_space, gym.spaces.Discrete
        ):
            raise TypeError("QLearningAgent requires Discrete observation and action spaces")
        self.action_space = action_space
        self.q = np.zeros((observation_space.n, action_space.n))
        self.lr = lr
        self.gamma = gamma
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay_steps = epsilon_decay_steps
        self.updates = 0

    def _epsilon(self) -> float:
        frac = min(self.updates / self.epsilon_decay_steps, 1.0)
        return self.epsilon_start + frac * (self.epsilon_end - self.epsilon_start)

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> int:
        if not deterministic and np.random.random() < self._epsilon():
            return masked_sample(self.action_space, action_mask)
        # np.where with an all-True mask returns the row unchanged, so the
        # masked argmax is bitwise-identical on envs without illegal actions.
        return int(np.argmax(np.where(action_mask, self.q[obs], NEG)))

    def update(self, batch: Any) -> dict[str, float]:
        # `truncated` is unused: a 1-step update has no episode-boundary
        # bookkeeping, and truncation doesn't stop bootstrapping (below).
        obs, action, reward, next_obs, terminated, _truncated, _mask, next_mask = batch
        # Bootstrap only through non-terminal next states. On truncation
        # (time limit) the episode was cut, not ended, so the future value
        # max_a Q(s', a) still applies — hence `terminated`, not `done`.
        # The max ranges over actions legal in s' (next_mask): bootstrapping
        # from an action that could never be taken is the silent-corruption
        # path masking exists to close.
        target = (
            reward
            if terminated
            else reward + self.gamma * np.where(next_mask, self.q[next_obs], NEG).max()
        )
        td_error = target - self.q[obs, action]
        self.q[obs, action] += self.lr * td_error
        self.updates += 1
        return {"loss/td_error": abs(float(td_error))}

    def state_dict(self) -> dict[str, Any]:
        return {"q": self.q, "updates": self.updates}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.q = state["q"]
        self.updates = state["updates"]

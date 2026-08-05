"""Random policy: the Phase 0 pipeline check, and the floor baseline every
learning agent must beat."""

from typing import Any

import gymnasium as gym

from rl.agents.base import Agent
from rl.common.masking import masked_sample


class RandomAgent(Agent):
    def __init__(self, action_space: gym.Space):
        self.action_space = action_space

    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> Any:
        # No policy to be deterministic about; eval measures the random floor.
        return masked_sample(self.action_space, action_mask)

    def update(self, batch: Any) -> dict[str, float]:
        return {}

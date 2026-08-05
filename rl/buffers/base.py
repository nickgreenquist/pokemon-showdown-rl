"""Buffer interface. Deliberately thin: the two buffer patterns share only
writing and size — a replay buffer (off-policy: DQN, SAC) is sampled from
forever, a rollout buffer (on-policy: PPO) is filled, drained whole, and
cleared — so each subclass adds its own read method (`sample` vs `get`).
"""

from abc import ABC, abstractmethod
from typing import Any


class Buffer(ABC):
    @abstractmethod
    def add(self, *transition: Any) -> None:
        """Store one transition."""

    @abstractmethod
    def __len__(self) -> int:
        """Number of transitions currently stored."""

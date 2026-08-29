"""Buffer interface. Deliberately thin. RolloutBuffer is the only
implementer left (the off-policy replay buffer went with the predecessor's
DQN/SAC spine); the ABC survives as the write/size contract its tests pin,
not as speculative generality — collapse it into rollout.py if it ever
grows a second method.
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

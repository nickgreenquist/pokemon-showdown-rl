"""Agent interface every algorithm must fit — random, tabular Q, DQN, PPO, SAC.
Shared code (train loop, eval, checkpoint) talks only to this."""

from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    # Collection mode, a property of the algorithm: vectorized agents (PPO)
    # are driven by the train loop's vector path — act()/update() see batched
    # (num_envs, ...) arrays during training, while eval still calls act()
    # with a single unbatched obs.
    vectorized = False

    @abstractmethod
    def act(self, obs: Any, action_mask: Any = None, deterministic: bool = False) -> Any:
        """Pick an action for one observation. `action_mask` is the env's
        legality mask (bool [n_actions], True = legal), supplied by the
        harness on every call for Discrete-action envs — all-True when
        nothing is illegal, batched [N, n_actions] on the vector path; None
        only for continuous action spaces, which have no mask concept.
        `deterministic=True` is the eval-time policy (e.g. argmax instead of
        sampling)."""

    @abstractmethod
    def update(self, batch: Any) -> dict[str, float]:
        """One learning step from a batch; returns `loss/*` metrics."""

    def state_dict(self) -> dict[str, Any]:
        """Learnable state for checkpointing; stateless agents return {}."""
        return {}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        pass

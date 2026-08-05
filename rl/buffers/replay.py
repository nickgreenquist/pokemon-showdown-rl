"""Replay buffer: a preallocated NumPy ring buffer of transitions.

Stores every transition the agent experiences, across episode boundaries;
at capacity the oldest entries are overwritten. `sample` draws a uniform
random minibatch from the whole history, which breaks the temporal
correlation of consecutive env steps and reuses each transition many times.
Torch-free on purpose: agents convert sampled arrays to tensors themselves.
"""

import numpy as np

from rl.buffers.base import Buffer

Batch = tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray,
    np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None,
]


class ReplayBuffer(Buffer):
    def __init__(
        self,
        capacity: int,
        obs_shape: tuple[int, ...],
        obs_dtype=np.float32,
        action_shape: tuple[int, ...] = (),
        action_dtype=np.int64,
        n_actions: int | None = None,
    ):
        self.capacity = capacity
        # Obs arrays take whichever dtype the agent asks for — the narrowest
        # one its network can consume. DQN passes the env's: MinAtar's bool
        # planes stay 1 byte per entry (100k Seaquest transitions ~200MB, not
        # float32's 800MB). SAC passes float32 against MuJoCo's float64 obs,
        # the same principle pointing the other way, since the cast happens at
        # tensor time regardless and float64 storage would buy nothing.
        self.obs = np.zeros((capacity, *obs_shape), dtype=obs_dtype)
        # Action storage carries the space's own shape and dtype: () / int64
        # for Discrete, (act_dim,) / float32 for Box — the same generalization
        # the rollout buffer took for the continuous track.
        self.actions = np.zeros((capacity, *action_shape), dtype=action_dtype)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.next_obs = np.zeros((capacity, *obs_shape), dtype=obs_dtype)
        # float, not bool: used directly as the (1 - terminated) bootstrap mask
        self.terminated = np.zeros(capacity, dtype=np.float32)
        # Bootstrap discount for this transition: gamma^m, where m is the
        # number of env steps between obs and next_obs (m < n_step when an
        # episode end cut the window short; m = 1 for a 1-step agent like SAC).
        # The buffer stays gamma-ignorant; the agent computes it.
        self.discounts = np.zeros(capacity, dtype=np.float32)
        # Legality masks: `masks` for obs's actions, `next_masks` for the
        # bootstrap state's — the target max must range over actions legal in
        # s', or it bootstraps from an action that could never be taken.
        # Allocated only for Discrete spaces: continuous actions have no
        # legality concept, so `masks is None` here means "Box", a fact fixed
        # at construction — never a runtime branch inside algorithm code.
        self.masks = None if n_actions is None else np.zeros((capacity, n_actions), dtype=bool)
        self.next_masks = None if n_actions is None else np.zeros((capacity, n_actions), dtype=bool)
        self._ptr = 0
        self._size = 0

    def add(self, obs, action, reward, next_obs, terminated, discount, mask=None, next_mask=None) -> None:
        i = self._ptr
        self.obs[i] = obs
        self.actions[i] = action
        self.rewards[i] = reward
        self.next_obs[i] = next_obs
        self.terminated[i] = terminated
        self.discounts[i] = discount
        if self.masks is not None:
            self.masks[i] = mask
            self.next_masks[i] = next_mask
        self._ptr = (i + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def sample(self, batch_size: int) -> Batch:
        idx = np.random.randint(0, self._size, size=batch_size)
        return (
            self.obs[idx],
            self.actions[idx],
            self.rewards[idx],
            self.next_obs[idx],
            self.terminated[idx],
            self.discounts[idx],
            None if self.masks is None else self.masks[idx],
            None if self.next_masks is None else self.next_masks[idx],
        )

    def __len__(self) -> int:
        return self._size

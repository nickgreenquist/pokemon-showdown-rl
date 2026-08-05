"""A tiny env with genuinely illegal actions. The spine envs have none, so
this is the only place the masking contract can be exercised for real.

Each state draws a fresh random legal subset (always >= 1 legal) and reports
it in `info["action_mask"]`. Stepping with an illegal action RAISES — loud
failure by design, so any hole in the masking plumbing turns a test red
instead of silently collecting a penalty.
"""

import gymnasium as gym
import numpy as np

N_ACTIONS = 5
MIN_EP_LEN, MAX_EP_LEN = 15, 25  # varied so vectorized sub-envs desynchronize


class MaskedDummyEnv(gym.Env):
    def __init__(self, render_mode=None):  # accepted (unused): gym.make passes it
        self.action_space = gym.spaces.Discrete(N_ACTIONS)
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (3,), np.float32)
        self._mask = np.ones(N_ACTIONS, dtype=bool)
        self._t = 0
        self._ep_len = MAX_EP_LEN

    def _new_state(self):
        self._mask = self.np_random.random(N_ACTIONS) < 0.5
        if not self._mask.any():  # contract: at least one legal action
            self._mask[self.np_random.integers(N_ACTIONS)] = True
        return self.np_random.uniform(-1.0, 1.0, 3).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._t = 0
        self._ep_len = int(self.np_random.integers(MIN_EP_LEN, MAX_EP_LEN + 1))
        obs = self._new_state()
        return obs, {"action_mask": self._mask.copy()}

    def step(self, action):
        if not self._mask[int(action)]:
            raise ValueError(f"illegal action {action} selected (mask {self._mask})")
        self._t += 1
        obs = self._new_state()
        return obs, 1.0, self._t >= self._ep_len, False, {"action_mask": self._mask.copy()}


def register() -> None:
    """Make the env reachable through the real factory (`make_env`) for
    end-to-end train-loop tests."""
    if "MaskedDummy-v0" not in gym.registry:
        gym.register(id="MaskedDummy-v0", entry_point=MaskedDummyEnv)

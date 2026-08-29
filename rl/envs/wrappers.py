"""Env wrappers applied inside the env factory."""

import gymnasium as gym
import numpy as np


class ActionMask(gym.Wrapper):
    """Guarantee `info["action_mask"]` (bool [n_actions], True = legal) on
    every reset and step of a Discrete-action env: pass through a mask the
    env supplies, inject all-True otherwise. Algorithm code therefore never
    branches on a missing mask — the masked path is always exercised, and
    all-True makes it a provable no-op (see rl/common/masking.py). The mask
    lives in info, not the observation space, so existing encoders and all
    Phase 1 checkpoints stay valid."""

    def __init__(self, env: gym.Env):
        super().__init__(env)
        if not isinstance(env.action_space, gym.spaces.Discrete):
            raise TypeError("ActionMask requires a Discrete action space")
        self._all_true = np.ones(int(env.action_space.n), dtype=bool)

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        info.setdefault("action_mask", self._all_true)
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        info.setdefault("action_mask", self._all_true)
        return obs, reward, terminated, truncated, info

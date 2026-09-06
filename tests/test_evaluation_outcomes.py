"""rl/common/evaluation.py — outcome-less eval episodes (2026-09-06).

A gen-4 lane died at 5.43M because ONE of 100 in-loop eval episodes ran to
max_steps without a terminal and eval_metrics raised on any missing outcome.
Now: a minority of missing outcomes is scored as NON-WINS and counted
(eval/no_outcome, eval/no_outcome_frac); a majority still raises (the
plumbing failure the guard was written for); the episode loop logs the
cap-out with the battle tag.
"""

import logging
from types import SimpleNamespace

import gymnasium as gym
import numpy as np
import pytest

from rl.common.evaluation import _run_eval_episodes, eval_metrics


def test_a_minority_of_missing_outcomes_scores_as_non_wins_and_is_counted():
    m = eval_metrics([1.0, -1.0, 0.0, 1.0], [1, -1, None, 1], [None] * 4, win_rate=True)
    assert m["eval/win_rate"] == pytest.approx(0.5)      # 2 wins of 4, the None is a non-win
    assert m["eval/no_outcome"] == 1.0
    assert m["eval/no_outcome_frac"] == pytest.approx(0.25)


def test_no_missing_outcomes_emits_no_no_outcome_keys():
    m = eval_metrics([1.0, -1.0], [1, -1], [None, None], win_rate=True)
    assert m["eval/win_rate"] == pytest.approx(0.5)
    assert "eval/no_outcome" not in m and "eval/no_outcome_frac" not in m


def test_a_majority_of_missing_outcomes_still_raises():
    with pytest.raises(ValueError, match="supplied no info"):
        eval_metrics([0.0, 0.0, 1.0], [None, None, 1], [None] * 3, win_rate=True)


class _NeverEnds(gym.Env):
    observation_space = gym.spaces.Box(-1, 1, (2,), np.float32)
    action_space = gym.spaces.Discrete(3)

    def reset(self, seed=None, options=None):
        return np.zeros(2, np.float32), {"action_mask": np.ones(3, bool)}

    def step(self, action):
        return np.zeros(2, np.float32), 0.0, False, False, {"action_mask": np.ones(3, bool)}


def test_capped_out_episode_yields_none_and_logs_the_cap(caplog):
    agent = SimpleNamespace(act=lambda obs, mask, deterministic=True: 0)
    with caplog.at_level(logging.WARNING, logger="rl.common.evaluation"):
        returns, outcomes, faints = _run_eval_episodes(agent, _NeverEnds(), 2, max_steps=5)
    assert outcomes == [None, None] and faints == [None, None] and returns == [0.0, 0.0]
    assert sum("hit max_steps=5 without a terminal" in r.message for r in caplog.records) == 2

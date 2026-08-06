"""Encoder v2 (POKEMON_RL_ENCODER_V2=1): the appended move-effect block and
speed-edge feature.

The switch is read at module import, so these tests run the assertions in a
SUBPROCESS with the env var set — the parent process (and the rest of the
suite) keeps the default v1 encoder. A wrong-value assertion inside the child
fails the test through its exit code, with the child's stderr in the report.
"""

import os
import subprocess
import sys

_CHILD = r"""
import numpy as np
from rl.envs.showdown import (
    ACTIVE_DIM, EFFECT_DIM, GLOBAL_DIM, MON_DIM, MOVE_DIM, OBS_DIM,
    _effect_block, _speed_edge,
)

assert MON_DIM == 33 and MOVE_DIM == 46, (MON_DIM, MOVE_DIM)
assert OBS_DIM == GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM \
    + 6 * (MON_DIM + 1) + ACTIVE_DIM + 4 * MOVE_DIM == 807, OBS_DIM

# The audit's motivating example: Rest, Amnesia and Reflect were
# near-identical 23-dim vectors under v1. The effect block separates them.
rest, amnesia, reflect = map(_effect_block, ("rest", "amnesia", "reflect"))
assert rest[9] == 1.0 and amnesia[9] == 0.0          # heal
assert amnesia[7] == 1.0 and rest[7] == 0.0          # self boost sum /4
assert reflect[20] == 1.0                            # REFLECT volatile slot
assert not np.array_equal(rest, amnesia) and not np.array_equal(rest, reflect)

bs = _effect_block("bodyslam")
assert bs[2] == 1.0 and abs(bs[6] - 0.3) < 1e-6      # PAR at 30%
tw = _effect_block("thunderwave")
assert tw[2] == 1.0 and tw[6] == 1.0                 # PAR primary
assert _effect_block("explosion")[14] == 1.0         # self-destruct
assert _effect_block("hyperbeam")[15] == 1.0         # recharge
assert _effect_block("slash")[12] == 1.0             # crit ratio 2 -> /2
assert _effect_block("wrap")[18] == 1.0              # PARTIALLY_TRAPPED
assert abs(_effect_block("bite")[22] - 0.1) < 1e-6   # flinch chance-weighted
assert abs(_effect_block("psychic")[8] + 0.165) < 1e-3  # foe boosts, expected
assert np.all(_effect_block("tackle") == 0.0)        # plain damage: zeros

# Speed edge: symmetric, bounded, paralysis-aware.
class _Mon:
    def __init__(self, spe, level=100, boost=0, par=False):
        from poke_env.battle.status import Status
        self.base_stats = {"spe": spe}
        self.level = level
        self.boosts = {"spe": boost}
        self.status = Status.PAR if par else None

fast, slow = _Mon(120), _Mon(60)
assert _speed_edge(fast, slow, True) > 0 > _speed_edge(slow, fast, True)
assert abs(_speed_edge(fast, fast, True)) < 1e-9
assert _speed_edge(_Mon(120, par=True), slow, True) < 0  # paralysis quarters
assert -1.0 < _speed_edge(_Mon(5), _Mon(200), True) < _speed_edge(_Mon(200), _Mon(5), True) < 1.0
print("OK")
"""


def test_encoder_v2_dims_and_effect_block():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


def test_default_encoder_is_still_v1():
    env = {k: v for k, v in os.environ.items() if k != "POKEMON_RL_ENCODER_V2"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from rl.envs.showdown import OBS_DIM, MON_DIM, MOVE_DIM;"
            "assert (OBS_DIM, MON_DIM, MOVE_DIM) == (611, 32, 23)",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

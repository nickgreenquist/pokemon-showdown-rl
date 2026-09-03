"""D18 privileged block (rl/envs/showdown.py::privileged_block + the
ShowdownEnv info["privileged"] emission).

Slice arithmetic runs in-process against whatever flags the suite runs
under (the constants scale with them); the v2+ids layout (408 dims, id
sub-slices) runs in a subprocess with both env vars set, per
test_entity_deepsets's pattern. Emission wiring is tested offline by
monkeypatching embed_battle (no battle object needed); the live end-to-end
emission — including "the privileged view is fuller than the actor's" —
skips without a server on :8000.
"""

import os
import socket
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from rl.envs.showdown import (
    _PRIV_OWN_END,
    GLOBAL_DIM,
    MON_DIM,
    OBS_DIM,
    PRIV_DIM,
    PRIV_ID_DIM,
    ShowdownEnv,
    privileged_block,
)


def test_priv_dim_arithmetic():
    # Own-side block plus (flag only) the 10 own ids — never the opponent
    # half, never the global block.
    assert PRIV_DIM == (_PRIV_OWN_END - GLOBAL_DIM) + PRIV_ID_DIM


def test_privileged_block_is_the_own_side_slice_and_a_copy():
    vec = np.arange(OBS_DIM, dtype=np.float32)
    priv = privileged_block(vec)
    assert priv.shape == (PRIV_DIM,)
    own = vec[GLOBAL_DIM:_PRIV_OWN_END]
    np.testing.assert_array_equal(priv[: len(own)], own)
    priv[0] = -99.0  # a view would corrupt the source encoding
    assert vec[GLOBAL_DIM] == GLOBAL_DIM


_V2_CHILD = r"""
import numpy as np
from rl.envs.showdown import (
    _PRIV_OWN_END, GLOBAL_DIM, ID_DIM, OBS_DIM, PRIV_DIM, privileged_block,
)
assert OBS_DIM == 828, OBS_DIM
assert PRIV_DIM == 408, PRIV_DIM
vec = np.arange(OBS_DIM, dtype=np.float32)
priv = privileged_block(vec)
own = vec[GLOBAL_DIM:_PRIV_OWN_END]
np.testing.assert_array_equal(priv[:len(own)], own)
# The id tail: 6 own species then 4 own moves — never the opponent's ids.
o = OBS_DIM - ID_DIM
np.testing.assert_array_equal(priv[-10:-4], vec[o : o + 6])
np.testing.assert_array_equal(priv[-4:], vec[o + 12 : o + 16])
print("OK")
"""


def test_v2_ids_layout_is_408_with_own_ids_only():
    result = subprocess.run(
        [sys.executable, "-c", _V2_CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def _wired_env(privileged: bool, battle2) -> ShowdownEnv:
    env = ShowdownEnv.__new__(ShowdownEnv)
    env._privileged = privileged
    env._env = SimpleNamespace(
        env=SimpleNamespace(battle2=battle2, _type_chart={})
    )
    return env


def test_emission_wiring_flag_on_and_off(monkeypatch):
    import rl.envs.showdown as sd

    fake = np.arange(OBS_DIM, dtype=np.float32)
    monkeypatch.setattr(sd, "embed_battle", lambda battle, chart: fake)
    battle2 = object()

    info: dict = {}
    _wired_env(True, battle2)._emit_privileged(info)
    np.testing.assert_array_equal(info["privileged"], privileged_block(fake))

    info = {}
    _wired_env(False, battle2)._emit_privileged(info)
    assert "privileged" not in info

    with pytest.raises(AssertionError, match="seat 2"):
        _wired_env(True, None)._emit_privileged({})


def _server_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=0.5).close()
        return True
    except OSError:
        return False


@pytest.mark.live_server
@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_live_emission_is_fuller_than_the_actor_view():
    env = ShowdownEnv(opponent="max_power", privileged=True)
    try:
        obs, info = env.reset()
        for _ in range(3):
            priv = info["privileged"]
            assert priv.shape == (PRIV_DIM,) and priv.dtype == np.float32
            # All 6 of seat 2's own mons are populated (level slot at +9)...
            assert all(priv[i * MON_DIM + 9] > 0 for i in range(6))
            # ...while the actor's opponent view reveals fewer than 6 —
            # the emission genuinely carries hidden information.
            opp_off = _PRIV_OWN_END
            revealed = sum(obs[opp_off + i * (MON_DIM + 1)] > 0 for i in range(6))
            assert revealed < 6
            mask = info["action_mask"]
            obs, _, terminated, truncated, info = env.step(
                int(np.flatnonzero(mask)[0])
            )
            if terminated or truncated:
                break
    finally:
        env.close()

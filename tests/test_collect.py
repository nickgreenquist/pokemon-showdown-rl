"""Collection-loop seam (Phase 5): contract tests.

The seam itself is pure asyncio + numpy and tests offline. SeamPlayer's
full path (encode -> seam -> strict order conversion -> server round trip)
needs the live local server, same skip rule as tests/test_showdown_env.py;
completing battles under strict=True is the masking proof there too.
"""

import asyncio
import socket

import numpy as np
import pytest

from rl.collect import InferenceSeam, SeamPlayer
from rl.envs.showdown import OBS_DIM


def test_seam_calls_policy_batched_and_counts():
    seen = []

    def policy(obs, mask):
        seen.append((obs.copy(), mask.copy()))
        return np.flatnonzero(mask[0])[:1]  # first legal action, batch of 1

    seam = InferenceSeam(policy)
    obs = np.arange(OBS_DIM, dtype=np.float32)
    mask = np.zeros(10, dtype=bool)
    mask[3] = mask[7] = True

    action = asyncio.run(seam.request(obs, mask))

    assert action == 3 and isinstance(action, int)
    assert seam.requests == 1 and seam.inference_seconds > 0.0
    # The seam adds the batch axis; the policy never sees a bare vector.
    (obs_b, mask_b), = seen
    assert obs_b.shape == (1, OBS_DIM) and obs_b.dtype == np.float32
    assert mask_b.shape == (1, 10) and mask_b.dtype == np.bool_
    np.testing.assert_array_equal(obs_b[0], obs)


def test_seam_counters_accumulate():
    seam = InferenceSeam(lambda obs, mask: np.array([0]))

    async def many():
        for _ in range(5):
            await seam.request(np.zeros(OBS_DIM, np.float32), np.ones(10, bool))

    asyncio.run(many())
    assert seam.requests == 5


def _server_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=0.5).close()
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_seam_player_battles_against_live_server():
    from poke_env.player import RandomPlayer

    rng = np.random.default_rng(0)

    def policy(obs, mask):
        return np.array([rng.choice(np.flatnonzero(mask[0]))])

    seam = InferenceSeam(policy)
    player = SeamPlayer(seam, battle_format="gen1randombattle")
    opponent = RandomPlayer(battle_format="gen1randombattle")
    asyncio.run(player.battle_against(opponent, n_battles=2))

    assert player.n_finished_battles == 2
    turns = sum(b.turn for b in player.battles.values())
    # One decision per request; forced switches make requests >= turns.
    assert seam.requests >= turns > 0
    assert seam.inference_seconds > 0.0

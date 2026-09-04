"""Collection-loop seam (Phase 5): contract tests.

The seam itself is pure asyncio + numpy and tests offline. SeamPlayer's
full path (encode -> seam -> strict order conversion -> server round trip)
needs the live local server, same skip rule as tests/test_showdown_env.py;
completing battles under strict=True is the masking proof there too.
"""

import asyncio
import socket
from types import SimpleNamespace

import numpy as np
import pytest

from poke_env.data import GenData
from poke_env.player import SimpleHeuristicsPlayer

from rl.collect import InferenceSeam, RecordingPlayer, SeamPlayer
from rl.envs.showdown import OBS_DIM, embed_battle


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


def _stub_battle(tag="battle-gen1randombattle-1"):
    """A battle exposing what the encoder, the mask and both conversions
    read: Pikachu (active, thunderbolt + quickattack) and Tauros on the
    bench, Chansey opposite. Real Pokemon/Move objects — poke-env's
    converters index into them, so stubs would test nothing."""
    from poke_env.battle.move import Move
    from poke_env.battle.pokemon import Pokemon
    from poke_env.player import Player

    active, bench, foe = (
        Pokemon(gen=1, species=s) for s in ("pikachu", "tauros", "chansey")
    )
    moves = [Move("thunderbolt", gen=1), Move("quickattack", gen=1)]
    for move in moves:
        active._moves[move.id] = move
    orders = [Player.create_order(m) for m in moves] + [Player.create_order(bench)]
    return SimpleNamespace(
        battle_tag=tag, wait=False, _wait=False, turn=3, gen=1,
        force_switch=False, trapped=False,
        team={"p1: Pikachu": active, "p1: Tauros": bench},
        opponent_team={"p2: Chansey": foe},
        active_pokemon=active, opponent_active_pokemon=foe,
        available_switches=[bench], available_moves=moves,
        can_mega_evolve=False, can_z_move=False, can_dynamax=False,
        can_tera=False, valid_orders=orders, player_username="test", logger=None,
    ), orders


def _recorder(order_for):
    """A RecordingPlayer whose expert is stubbed out, built without touching
    the network (MixturePlayer's offline-test pattern)."""
    player = RecordingPlayer(battle_format="gen1randombattle", start_listening=False)
    player._expert = SimpleNamespace(choose_move=order_for)
    return player


def test_recorder_labels_are_the_experts_own_orders():
    battle, orders = _stub_battle()
    # Team order is (Pikachu, Tauros) and Pikachu is active, so the only
    # switch is action 1; moves are 6 and 7 in active.moves order.
    for order, expected in zip(orders, [6, 7, 1]):
        player = _recorder(lambda b, o=order: o)
        assert player.choose_move(battle) is order
        data = player.dataset()
        assert data["actions"].tolist() == [expected]
        assert data["masks"].tolist() == [[0, 1, 0, 0, 0, 0, 1, 1, 0, 0]]
        assert data["battle_ids"].tolist() == [0]
        assert data["obs"].shape == (1, OBS_DIM)
        # The recorded row is the pre-decision state, encoded exactly as the
        # Gym path would encode it.
        np.testing.assert_array_equal(
            data["obs"][0], embed_battle(battle, GenData.from_format("gen1randombattle").type_chart)
        )


def test_recorder_rejects_a_label_that_does_not_round_trip():
    # An order poke-env can convert but whose action does not convert back
    # to it would silently mislabel every row it touched; the guard is a
    # round-trip through the same converter deployment uses.
    battle, orders = _stub_battle()
    player = _recorder(lambda b: orders[0])
    from poke_env.environment import SinglesEnv

    # Restore the staticmethod OBJECT, not what attribute access unwraps it
    # to: rebinding the bare function would leave every later caller passing
    # an implicit self (it took down two live tests in this suite once).
    original = SinglesEnv.__dict__["order_to_action"]
    try:
        SinglesEnv.order_to_action = staticmethod(lambda *a, **k: np.int64(7))
        with pytest.raises(AssertionError, match="does not convert back"):
            player.choose_move(battle)
    finally:
        SinglesEnv.order_to_action = original
    assert player.dataset()["actions"].size == 0  # nothing recorded


def test_recorder_groups_rows_by_battle():
    first, orders = _stub_battle("battle-gen1randombattle-1")
    second, _ = _stub_battle("battle-gen1randombattle-2")
    player = _recorder(lambda b: orders[0])
    for battle in (first, second, first, second, second):
        player.choose_move(battle)
    # Concurrent battles interleave: ids identify the battle, they do not
    # index contiguous blocks of rows.
    assert player.dataset()["battle_ids"].tolist() == [0, 1, 0, 1, 1]


def test_recorder_refuses_a_non_action_order():
    # A default order round-trips to ITSELF (action -2 -> "/choose default"),
    # so only the sign check stands between it and mask[-2].
    from poke_env.player import DefaultBattleOrder

    battle, _ = _stub_battle()
    player = _recorder(lambda b: DefaultBattleOrder())
    with pytest.raises(AssertionError, match="non-action order"):
        player.choose_move(battle)
    assert player.dataset()["actions"].size == 0


def test_recorder_refuses_wait_states():
    battle, orders = _stub_battle()
    battle.wait = True
    with pytest.raises(AssertionError, match="wait state"):
        _recorder(lambda b: orders[0]).choose_move(battle)


def _server_up() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8000), timeout=0.5).close()
        return True
    except OSError:
        return False


@pytest.mark.live_server
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


@pytest.mark.live_server
@pytest.mark.skipif(not _server_up(), reason="no local Showdown server on :8000")
def test_recording_player_battles_against_live_server():
    """The offline tests pin one hand-built position; this is the proof over
    real Gen 1 traffic — forced switches, fainted mons, PP-exhausted turns.
    Every row's guards ran inside choose_move, so completing 2 battles is
    itself the assertion; the checks below pin the dataset's shape."""
    player = RecordingPlayer(expert="heuristics", battle_format="gen1randombattle")
    opponent = SimpleHeuristicsPlayer(battle_format="gen1randombattle")
    asyncio.run(player.battle_against(opponent, n_battles=2))

    data = player.dataset()
    rows = len(data["actions"])
    assert player.n_finished_battles == 2
    assert rows > 0 and data["obs"].shape == (rows, OBS_DIM)
    assert data["obs"].dtype == np.float32 and np.isfinite(data["obs"]).all()
    assert data["masks"].shape == (rows, 10)
    assert sorted(set(data["battle_ids"].tolist())) == [0, 1]
    # Every label legal under its own recorded mask — the property the whole
    # dataset rests on, restated over live traffic.
    assert data["masks"][np.arange(rows), data["actions"]].all()

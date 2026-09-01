"""G6a (THROUGHPUT_SPEC §4): under K interleaved battles, each battle is
played end-to-end by exactly ONE pool member / mixture sub-player, outcomes
credit the member that actually played, and the per-tag maps stay bounded.
These are the properties the old single-latch design silently violated."""

from types import SimpleNamespace

import numpy as np
import pytest

from rl.envs.showdown import _OPP_CHOICE_NONE, OBS_DIM, MixturePlayer, PoolPlayer


class _FakeMember:
    def __init__(self, action):
        self.action = action

    def move(self, obs, mask, rng):
        return self.action


class _FakePool:
    def __init__(self, members):
        self.members = members
        self.selects = 0
        self.reports = []

    def freeze(self):
        pass

    def select(self, rng):
        member = self.members[self.selects % len(self.members)]
        self.selects += 1
        return member

    def member_id(self, member):
        return self.members.index(member)

    def report(self, played, outcome):
        self.reports.append((played, outcome))


def _battle(tag, turn=1, finished=False):
    return SimpleNamespace(battle_tag=tag, wait=False, turn=turn, finished=finished)


@pytest.fixture
def trio(monkeypatch):
    monkeypatch.setattr(
        "rl.envs.showdown.embed_battle", lambda b, tc: np.zeros(OBS_DIM, np.float32)
    )
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.get_action_mask",
        staticmethod(lambda b: np.ones(10, np.int64)),
    )
    monkeypatch.setattr(
        "rl.envs.showdown.SinglesEnv.action_to_order",
        staticmethod(lambda a, b: int(a)),
    )


def test_interleaved_battles_keep_one_member_each(trio):
    pool = _FakePool([_FakeMember(a) for a in range(4)])
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    battles = [_battle(f"battle-x-{i}") for i in range(8)]
    first = {b.battle_tag: player.choose_move(b) for b in battles}
    # Heavy interleaving: 5 more rounds in scrambled orders.
    rng = np.random.default_rng(0)
    for _ in range(5):
        for i in rng.permutation(8):
            assert player.choose_move(battles[i]) == first[battles[i].battle_tag]
    assert pool.selects == 8  # one selection per battle, never per decision


def test_interleaved_reports_credit_the_right_member(trio):
    members = [_FakeMember(a) for a in range(3)]
    pool = _FakePool(members)
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    b = [_battle(f"battle-y-{i}") for i in range(3)]
    for battle in b:
        player.choose_move(battle)
    # Finish them out of start order, naming the battle (the async caller).
    player.report_outcome(-1, b[1].battle_tag)
    player.report_outcome(1, b[2].battle_tag)
    player.report_outcome(0, b[0].battle_tag)
    assert pool.reports == [(members[1], -1), (members[2], 1), (members[0], 0)]
    # Reporting pops: a second report for the same battle credits nobody.
    player.report_outcome(1, b[1].battle_tag)
    assert len(pool.reports) == 3


def test_finished_sweep_bounds_the_map(trio):
    pool = _FakePool([_FakeMember(0)])
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    stale = _battle("battle-z-old")
    player.choose_move(stale)
    stale.finished = True  # ended without a report (abandoned room)
    player.choose_move(_battle("battle-z-new"))
    assert "battle-z-old" not in player._by_tag


def test_choice_recording_keys_by_turn_and_index(trio, monkeypatch):
    monkeypatch.setattr(
        "rl.envs.showdown._order_identity", lambda order, battle: (1, order, 1)
    )
    pool = _FakePool([_FakeMember(3), _FakeMember(7)])
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    player.record_choices()
    b1, b2 = _battle("battle-r-1", turn=1), _battle("battle-r-2", turn=1)
    player.choose_move(b1)  # b1 turn 1, decision 0
    player.choose_move(b2)  # b2 turn 1, decision 0
    player.choose_move(b1)  # b1 turn 1, decision 1 (forced replacement)
    b1.turn = 2
    player.choose_move(b1)  # b1 turn 2, decision 0
    assert player.take_choices("battle-r-1") == {
        (1, 0): (1, 3, 1),
        (1, 1): (1, 3, 1),
        (2, 0): (1, 3, 1),
    }
    assert player.take_choices("battle-r-2") == {(1, 0): (1, 7, 1)}
    # take_choices pops — the record does not accumulate across battles.
    assert player.take_choices("battle-r-1") == {}


def test_recording_off_by_default_records_nothing(trio):
    pool = _FakePool([_FakeMember(0)])
    player = PoolPlayer(pool, battle_format="gen1randombattle", start_listening=False)
    player.choose_move(_battle("battle-q-1"))
    assert player._choices == {} and player._turn_counts == {}


def test_mixture_interleaved_battles_keep_one_subplayer_each():
    player = MixturePlayer(
        {"heuristics": 0.5, "random": 0.5},
        battle_format="gen1randombattle",
        start_listening=False,
    )
    seen = {}
    calls = []

    for name, sub in player._players.items():
        sub.choose_move = lambda b, name=name: calls.append((b.battle_tag, name))

    battles = [_battle(f"battle-m-{i}") for i in range(6)]
    rng = np.random.default_rng(1)
    for _ in range(4):
        for i in rng.permutation(6):
            player.choose_move(battles[i])
    for tag, name in calls:
        assert seen.setdefault(tag, name) == name, "sub-player flipped mid-battle"

"""IDEAS 4.11's data path: the three critic targets from an episode's last
decision row plus its outcome (rl/envs/outcome_targets.py), and the engine
collector's emission of them behind `outcome_targets=True` (no engine needed:
`_episode` is a plain method over the raw dict). Layout-agnostic: the vectors
are built from the same rl.envs.showdown constants the function reads."""
from types import SimpleNamespace

import numpy as np
import pytest

from rl.envs import showdown as sd
from rl.envs.outcome_targets import TARGET_NAMES, outcome_targets


def _row(own_fainted, opp_fainted, own_hp, opp_revealed_hp):
    """own_hp: 6 fractions; opp_revealed_hp: list of (revealed, hp) for 6 slots."""
    v = np.zeros(sd.OBS_DIM, dtype=np.float32)
    v[1] = own_fainted / 6.0
    v[2] = opp_fainted / 6.0
    for i, hp in enumerate(own_hp):
        v[sd.GLOBAL_DIM + i * sd.MON_DIM] = hp
    opp_off = sd.GLOBAL_DIM + 6 * sd.MON_DIM + sd.ACTIVE_DIM + 4 * sd.MOVE_DIM
    for j, (rev, hp) in enumerate(opp_revealed_hp):
        v[opp_off + j * (sd.MON_DIM + 1)] = float(rev)
        v[opp_off + j * (sd.MON_DIM + 1) + 1] = hp
    return v


def _episode(last_row, n=5):
    rows = np.zeros((n, sd.OBS_DIM), dtype=np.float32)
    rows[:-1] = 0.3          # earlier decisions must not matter
    rows[-1] = last_row
    return rows


def test_win_credits_our_survivors_and_hp_and_zeroes_theirs():
    last = _row(own_fainted=2, opp_fainted=5, own_hp=[0.0, 0.5, 1.0, 0.0, 0.25, 1.0],
                opp_revealed_hp=[(1, 0.0)] * 5 + [(1, 0.1)])
    t = outcome_targets(_episode(last), +1.0)
    assert t.shape == (5, 3) and t.dtype == np.float32
    assert np.allclose(t[0], [4 / 6, 0.0, 2.75 / 6])
    assert (t == t[0]).all()               # the same row on every step


def test_loss_charges_their_survivors_and_hp_with_unrevealed_at_full():
    last = _row(own_fainted=5, opp_fainted=1, own_hp=[0.0] * 5 + [0.2],
                opp_revealed_hp=[(1, 0.0), (1, 0.6), (0, 0.0), (0, 0.0), (1, 1.0), (0, 0.0)])
    t = outcome_targets(_episode(last), -1.0)
    # 5 live; revealed hp 0.6 + 1.0, plus three unrevealed at 1.0 each = 4.6
    assert np.allclose(t[0], [0.0, 5 / 6, -4.6 / 6])


def test_tie_keeps_both_sides_and_differences_hp():
    last = _row(own_fainted=3, opp_fainted=3, own_hp=[1.0, 0.0, 0.5, 0.0, 0.0, 0.5],
                opp_revealed_hp=[(1, 0.0)] * 3 + [(1, 0.5), (1, 0.5), (0, 0.0)])
    t = outcome_targets(_episode(last), 0.0)
    assert np.allclose(t[0], [3 / 6, 3 / 6, (2.0 - 2.0) / 6])


def test_names_and_width_guard():
    assert TARGET_NAMES == ("survivors_own", "survivors_opp", "hp_margin")
    with pytest.raises(AssertionError):
        outcome_targets(np.zeros((3, sd.OBS_DIM + 1), np.float32), 1.0)


def test_engine_collector_emits_the_block_only_when_asked():
    from rl.envs.engine_collector import EngineCollector

    last = _row(1, 6, [1.0] * 5 + [0.0], [(1, 0.0)] * 6)
    raw = {"length": 4, "reward": 1.0, "obs": _episode(last, n=4),
           "masks": np.ones((4, sd.N_ACTIONS), bool), "actions": np.zeros(4, np.int64),
           "old_logp": np.zeros(4, np.float32), "version": np.zeros(4, np.int64), "slot": 0}
    # The collector's own per-slot state that _episode reads since B5 (bc24570): the row tag and the T-op hook.
    base = dict(_opp_action=False, _privileged=False, _both_views=False, _seated_latest=[False], searcher=None)
    off = SimpleNamespace(**base, _outcome_targets=False)
    on = SimpleNamespace(**base, _outcome_targets=True)
    assert "outcome_targets" not in EngineCollector._episode(off, raw)
    ep = EngineCollector._episode(on, raw)
    assert ep["outcome_targets"].shape == (4, 3)
    assert np.allclose(ep["outcome_targets"][0], [5 / 6, 0.0, 5 / 6])


def test_engine_c6_seam_refuses_the_flag_without_the_port(monkeypatch):
    from rl.envs.engine_collector import _check_engine_c6

    monkeypatch.delenv("POKEMON_RL_ENCODER_C6", raising=False)
    _check_engine_c6(SimpleNamespace())                       # flag off: fine
    monkeypatch.setenv("POKEMON_RL_ENCODER_C6", "1")
    with pytest.raises(ValueError, match=r"does not implement the C6"):
        _check_engine_c6(SimpleNamespace())                   # flag on, no port
    _check_engine_c6(SimpleNamespace(ENCODER_C6=True))        # flag on, ported

"""rl/common/checkpoint.py refuses a gen-1 checkpoint whose run stamped the other
C6 encoder semantics (constant OBS_DIM, so no width check can see it)."""
import warnings

import pytest
import torch
import yaml

from rl.common.checkpoint import load_checkpoint


def _write(tmp_path, env_id="Showdown-v0", encoder=None, meta=True):
    p = tmp_path / "ckpt_000000001.pt"
    torch.save({"agent": {}, "step": 1, "config": {"env_id": env_id}}, p)
    if meta:
        (tmp_path / "meta.yaml").write_text(yaml.safe_dump({"encoder": encoder or {}}))
    return p


def test_matching_stamp_loads_and_mismatch_refuses(tmp_path, monkeypatch):
    p = _write(tmp_path, encoder={"obs_dim": 828, "c6": True})
    monkeypatch.setenv("POKEMON_RL_ENCODER_C6", "1")
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH", raising=False)
    assert load_checkpoint(p)["step"] == 1
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6")
    with pytest.raises(RuntimeError, match=r"stamped encoder c6=True"):
        load_checkpoint(p)


def test_legacy_stamp_without_c6_is_c6_off(tmp_path, monkeypatch):
    p = _write(tmp_path, encoder={"obs_dim": 828, "encoder": "v2", "ids": True})
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6", raising=False)
    assert load_checkpoint(p)["step"] == 1
    monkeypatch.setenv("POKEMON_RL_ENCODER_C6", "1")
    with pytest.raises(RuntimeError, match=r"stamped encoder c6=False"):
        load_checkpoint(p)


def test_allow_mismatch_downgrades_to_a_warning(tmp_path, monkeypatch):
    p = _write(tmp_path, encoder={"c6": True})
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6", raising=False)
    monkeypatch.setenv("POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH", "1")
    with pytest.warns(UserWarning, match=r"stamped encoder c6=True"):
        load_checkpoint(p)


def test_no_meta_warns_only_when_the_flag_is_on(tmp_path, monkeypatch):
    p = _write(tmp_path, meta=False)
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        load_checkpoint(p)
    monkeypatch.setenv("POKEMON_RL_ENCODER_C6", "1")
    with pytest.warns(UserWarning, match=r"cannot be verified"):
        load_checkpoint(p)


def test_non_showdown_checkpoints_are_never_guarded(tmp_path, monkeypatch):
    p = _write(tmp_path, env_id="Connect4-v0", encoder={"c6": True})
    monkeypatch.delenv("POKEMON_RL_ENCODER_C6", raising=False)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        load_checkpoint(p)

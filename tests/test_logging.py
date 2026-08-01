"""Logger seam: the W&B backend's offline default.

Every launch in this project runs offline; the default lives in code rather
than in a per-shell export so a forgotten `WANDB_MODE=offline` cannot put a
multi-hour run behind a network init. `wandb` is stubbed here — the point is
which arguments reach `init`, not that the service works.
"""

import sys
from types import SimpleNamespace

import pytest

from rl.common.config import Config
from rl.common.logging import WandbLogger


@pytest.fixture
def wandb_stub(monkeypatch):
    calls = {}
    monkeypatch.setitem(
        sys.modules,
        "wandb",
        SimpleNamespace(init=lambda **kwargs: calls.update(kwargs) or SimpleNamespace()),
    )
    return calls


def _cfg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # run_dir is relative to the cwd
    return Config(
        env_id="CartPole-v1", seed=0, total_steps=0, eval_every=0,
        eval_episodes=0, run_name="logging_test",
    )


def test_wandb_defaults_to_offline(tmp_path, monkeypatch, wandb_stub):
    monkeypatch.delenv("WANDB_MODE", raising=False)
    WandbLogger(_cfg(tmp_path, monkeypatch))
    assert wandb_stub["mode"] == "offline"
    # Offline data still colocates with the run dir, which is created first
    # (a missing dir makes wandb fall back to ./wandb with only a warning).
    assert wandb_stub["dir"] == "runs/logging_test"
    assert (tmp_path / "runs" / "logging_test").is_dir()


def test_explicit_wandb_mode_wins(tmp_path, monkeypatch, wandb_stub):
    monkeypatch.setenv("WANDB_MODE", "online")
    WandbLogger(_cfg(tmp_path, monkeypatch))
    assert wandb_stub["mode"] == "online"

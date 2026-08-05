"""Thin logging seam: the train loop logs through `Logger`, never through a
backend directly, and algorithm code never touches W&B (hard rule).

Metric names are locked in CLAUDE.md — reuse exactly:
`rollout/episode_return`, `rollout/episode_length`, `eval/return_mean`,
`eval/return_std`, `time/steps_per_sec`, plus `loss/*` per algorithm.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path

from rl.common.config import Config, run_dir

WANDB_PROJECT = "deep-rl-from-scratch"


class Logger(ABC):
    @abstractmethod
    def log(self, metrics: dict[str, float], step: int) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class WandbLogger(Logger):
    def __init__(self, cfg: Config):
        import wandb  # multi-second import; deferred so the offline path never pays it

        # Offline data lands under runs/<run_name>/wandb/ so every run dir is
        # self-contained and parallel runs never share a directory. Explicit
        # mkdir: a missing dir makes wandb fall back to ./wandb with only a
        # warning.
        out_dir = run_dir(cfg)
        out_dir.mkdir(parents=True, exist_ok=True)
        self._run = wandb.init(
            project=WANDB_PROJECT, name=cfg.run_name, config=asdict(cfg), dir=str(out_dir)
        )

    def log(self, metrics: dict[str, float], step: int) -> None:
        self._run.log(metrics, step=step)

    def close(self) -> None:
        self._run.finish()


class TensorBoardLogger(Logger):
    def __init__(self, cfg: Config):
        from torch.utils.tensorboard import SummaryWriter

        self._writer = SummaryWriter(log_dir=str(Path("runs") / cfg.run_name))

    def log(self, metrics: dict[str, float], step: int) -> None:
        for name, value in metrics.items():
            self._writer.add_scalar(name, value, step)

    def close(self) -> None:
        self._writer.close()


def make_logger(cfg: Config) -> Logger:
    if cfg.logger == "wandb":
        return WandbLogger(cfg)
    if cfg.logger == "tensorboard":
        return TensorBoardLogger(cfg)
    raise ValueError(f"logger must be 'wandb' or 'tensorboard', got {cfg.logger!r}")

"""Checkpoint save/load: agent state (optimizer included, via the agent's own
state_dict) + step + config + any extras the train loop registers (normalizer
statistics, pool state)."""

from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from rl.agents.base import Agent
from rl.common.config import Config


def save_checkpoint(
    path: str | Path, agent: Agent, step: int, cfg: Config, normalizers: dict | None = None,
    extras: dict | None = None,
) -> None:
    """`normalizers` maps a name to a RunningMeanStd whose statistics are read
    HERE, at save time, so a checkpoint always carries the statistics that
    were live when its weights were saved. Without them a restored policy is
    evaluated against the wrong observation scale — which does not crash, it
    just quietly scores badly.

    `extras` (resume-from-checkpoint): loop-level bookkeeping merged into the
    payload under keys the eval loaders never read — today {"loop":
    {"best_eval", "updates_done"}}. Absent in every pre-2026-08-23
    checkpoint; readers must .get() it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"agent": agent.state_dict(), "step": step, "config": asdict(cfg)}
    if normalizers:
        payload["normalizers"] = {name: rms.state_dict() for name, rms in normalizers.items()}
    if extras:
        payload.update(extras)
    # Write-then-rename: a run killed mid-save must not leave a truncated
    # file where a good checkpoint used to be.
    tmp = path.with_name(path.name + ".tmp")
    torch.save(payload, tmp)
    tmp.replace(path)


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    # weights_only=False: checkpoints are our own files, and agent state may
    # hold non-tensor objects (e.g. a NumPy Q-table) the safe loader rejects.
    return torch.load(Path(path), weights_only=False)

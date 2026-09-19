"""Checkpoint save/load: agent state (optimizer included, via the agent's own
state_dict) + step + config + any extras the train loop registers (normalizer
statistics, pool state)."""

import os
import warnings
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
    payload under keys the eval loaders never read — {"loop": {"best_eval",
    "updates_done"}} since 2026-08-23; since 2026-09-03 (F-05) {"pool":
    {"step", "state"}} so the self-play pool and the learner it pairs with
    land in ONE write-then-rename (pool.pt was a second rename a kill could
    split); and (F-18) {"rng": {"torch", "numpy", "python"}} so a resume
    continues the global streams instead of replaying the run's first
    sequence. Every key is absent from older checkpoints; readers must .get()
    it — rl/train.py's resume path is the reference reader."""
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


def _encoder_c6_guard(path: Path, ckpt: dict) -> None:
    """A gen-1 checkpoint is interpretable only under the encoder semantics it
    trained on (rl/envs/showdown.py::ENCODER_FINGERPRINT). C6 changes slot
    SEMANTICS at constant OBS_DIM, so no width check can catch a mismatch; the
    run's own meta.yaml carries the stamp. The env var is read here rather than
    imported from rl.envs.showdown so that loading a Connect-4 or MinAtar
    checkpoint never imports poke_env.

    Refuses on a mismatch; `POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH=1` downgrades
    it to a warning for a DISCLOSED mixed committee (R5 finals beside R6 finals
    under one encoder are a new object, measured rather than assumed). A
    checkpoint with no meta.yaml beside it cannot be verified: loads with a
    warning when the process flag is on, silently when it is off (every
    checkpoint written before 2026-09-19 is c6-off)."""
    cfg = ckpt.get("config") or {}
    if cfg.get("env_id") != "Showdown-v0":
        return
    proc = bool(os.environ.get("POKEMON_RL_ENCODER_C6"))
    meta_path = path.parent / "meta.yaml"
    stamped = None
    if meta_path.exists():
        try:
            import yaml

            enc = (yaml.safe_load(meta_path.read_text()) or {}).get("encoder") or {}
            stamped = bool(enc.get("c6", False))
        except Exception:  # noqa: BLE001 -- an unreadable meta is "unknown", not a crash
            stamped = None
    if stamped is None:
        if proc:
            warnings.warn(
                f"{path}: no readable meta.yaml beside it, so its C6 encoder stamp cannot "
                "be verified while POKEMON_RL_ENCODER_C6 is set", stacklevel=3)
        return
    if stamped != proc:
        msg = (f"{path}: the run stamped encoder c6={stamped} but this process has "
               f"POKEMON_RL_ENCODER_C6={'1' if proc else 'unset'}; the fixed-damage move "
               "slots would be read under the wrong semantics. Set the flag to match, or "
               "POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH=1 for a disclosed mixed committee.")
        if os.environ.get("POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH"):
            warnings.warn(msg, stacklevel=3)
            return
        raise RuntimeError(msg)


def load_checkpoint(path: str | Path) -> dict[str, Any]:
    # weights_only=False: checkpoints are our own files, and agent state may
    # hold non-tensor objects (e.g. a NumPy Q-table) the safe loader rejects.
    path = Path(path)
    ckpt = torch.load(path, weights_only=False)
    _encoder_c6_guard(path, ckpt)
    return ckpt

"""CH5 R1 BUILD gate — does the new FP ensemble seat decide IDENTICALLY to
the ladder path that actually played the 200 rated games?

The whole value of measuring L2 off-SH is that it rates THE OBJECT THAT
LADDERED. Two independent construction paths exist — `ladder.py::_load`
and `ch3_fp_h2h::_build_agent` — and "they look the same in the source" is
not a measurement. This runs both and compares decisions.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/ch5_seat_equiv.py

Two gates:
  E1  0 disagreements over N random masked states. This is the load-bearing
      one and it is exact.
  E2  the ensemble does NOT collapse onto any single member, i.e. the
      wrapper is doing something.

CAVEAT, stated because the number invites misreading: the states are random
Gaussian vectors, not real battle observations. That is fine for E1 — an
IDENTITY check is strongest on arbitrary inputs — but E2's divergence
percentages are OFF-DISTRIBUTION and must never be quoted as an in-play
flip rate. The in-play number is `ensemble/flip_rate`, which the seat now
stamps into every arm's report.
"""
import argparse
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

DEFAULT_PREREG = "configs/eval/ladder_r1.yaml"


def ladder_load(prereg, lane):
    """`ladder.py::_load`, verbatim — deliberately NOT imported, so that a
    future edit to either path shows up here as a disagreement."""
    from eval_checkpoint import _load_showdown_agent

    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config

    spec = prereg["checkpoints"][lane]
    h = hashlib.sha256()
    with open(spec["path"], "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    assert h.hexdigest() == spec["sha256"], f"sha256 mismatch on {spec['path']}"
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(1)
    return _load_showdown_agent(ckpt, cfg)


def random_state(rng, obs_dim, min_legal=1):
    obs = rng.standard_normal(obs_dim).astype(np.float32)
    mask = np.zeros(10, dtype=bool)
    k = rng.integers(min_legal, 11)
    mask[rng.choice(10, size=k, replace=False)] = True
    return obs, mask


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--prereg", default=DEFAULT_PREREG)
    ap.add_argument("--arm", default="L2")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260826)
    args = ap.parse_args()

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d protocol)"

    import ch3_fp_h2h as fp

    from rl.envs.showdown import OBS_DIM
    from rl.search.ensemble import EnsembleAgent

    prereg = yaml.safe_load(Path(args.prereg).read_text())
    lanes = list(prereg["arms"][args.arm]["lanes"])
    print(f"prereg={args.prereg} arm={args.arm} lanes={lanes} OBS_DIM={OBS_DIM}")

    a = EnsembleAgent([fp._build_agent(prereg["checkpoints"][x]) for x in lanes])
    b = EnsembleAgent([ladder_load(prereg, x) for x in lanes])
    print(f"A = ch3_fp_h2h._build_agent  (native_dim {fp._native_dim(a)})")
    print(f"B = ladder.py::_load recipe  (native_dim {fp._native_dim(b)})")

    rng = np.random.default_rng(args.seed)
    disagree = 0
    for _ in range(args.n):
        obs, mask = random_state(rng, OBS_DIM)
        if a.act(obs, mask, deterministic=True) != b.act(obs, mask, deterministic=True):
            disagree += 1
    print(f"\nE1  {args.n} random masked states -> DISAGREEMENTS = {disagree}")
    print(f"    A flip-vs-modal-member {a.flips}/{a.decisions} "
          f"= {a.flips / a.decisions:.3f}  (off-distribution; not an in-play rate)")
    assert disagree == 0, "E1 FAIL: the FP seat and the ladder path decide differently"

    singles = [fp._build_agent(prereg["checkpoints"][x]) for x in lanes]
    rng = np.random.default_rng(args.seed + 1)
    n2 = max(1, args.n // 2)
    diffs = [0] * len(lanes)
    for _ in range(n2):
        obs, mask = random_state(rng, OBS_DIM, min_legal=2)
        act = a.act(obs, mask, deterministic=True)
        for j, s in enumerate(singles):
            if s.act(obs, mask, deterministic=True) != act:
                diffs[j] += 1
    print(f"E2  ensemble differs from each single lane over {n2} states: "
          + ", ".join(f"{l} {d / n2:.1%}" for l, d in zip(lanes, diffs)))
    assert all(d > 0 for d in diffs), "E2 FAIL: ensemble collapsed onto a single lane"

    print("\nGATE PASS — identical to the ladder path, and genuinely an ensemble.")


if __name__ == "__main__":
    main()

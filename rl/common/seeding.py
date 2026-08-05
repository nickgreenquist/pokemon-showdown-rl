"""Seeding for every RNG source the harness touches, except envs.

Env seeding lives with the env factory (Phase 0, later chunk): gymnasium
envs carry their own RNG, seeded per-env at reset — and env spaces carry
yet another, seeded only via `space.seed()`, which a random policy using
`action_space.sample()` depends on. Both are the env factory's job.
"""

import random

import numpy as np
import torch


def set_seed(seed: int) -> None:
    """Seed Python's `random`, NumPy's global RNG, and torch.

    `torch.manual_seed` covers the CPU generator and every accelerator
    backend (CUDA, MPS) in one call.

    Caveats: this gives same-machine, same-version reproducibility of RNG
    draws — not bit-exact training runs. Kernel results can differ across
    devices, torch versions, and thread counts, and some GPU kernels are
    nondeterministic (reduction order, algorithm autotuning). We deliberately
    skip `torch.use_deterministic_algorithms(True)`: it trades speed for a
    guarantee that still doesn't hold across machines.

    NumPy restricts seeds to [0, 2**32); anything outside raises ValueError.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

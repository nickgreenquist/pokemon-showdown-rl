"""Inference-only nn.Linear on a cached CONTIGUOUS transposed weight (2026-09-26).

nn.Linear computes x @ W.T through addmm with the weight TRANSPOSED as a view. On this box's torch
(BLAS_INFO=accelerate) that transposed-B sgemm has a slow path at small row counts. A 1024x1024
layer costs ~620 us at 2..12 rows against ~50-60 us for the same product on a contiguous W.T:
10-12x, 2.5x at 32 rows, 1.7x at 64 (measured 2026-09-26: M4 Pro, torch 2.13.0, one thread,
beside the R7 fleet). At one row torch takes gemv and both cost ~15-20 us. On the W critic
(640->1024->1024) the whole forward is 2.4x faster at 8 rows.

The output is bitwise equal at large batches. At small ones it differs by float rounding (~3e-7,
the size of stock's own batch-to-batch difference), so a search's decisions can move only at exact
near-ties.

`enable(module)` swaps every nn.Linear under `module` to FastLinear IN PLACE: the same
parameters, the same state_dict. Under autograd (training) FastLinear is exactly nn.Linear. The
cached transpose is rebuilt when the weight changes (an optimizer step or load_state_dict bumps
its version), so shipping new weights into a collector needs nothing extra.
"""
from __future__ import annotations

import torch
from torch import nn


class FastLinear(nn.Linear):
    """nn.Linear whose no-grad forward is addmm(bias, x, W.T contiguous)."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if torch.is_grad_enabled():
            return super().forward(x)
        w = self.weight
        cache = self.__dict__.get("_wt_cache")
        if cache is None or cache[0] is not w or cache[1] != w._version:
            cache = (w, w._version, w.detach().t().contiguous())
            self.__dict__["_wt_cache"] = cache
        x2 = x.reshape(-1, x.shape[-1])
        y = torch.addmm(self.bias, x2, cache[2]) if self.bias is not None else x2 @ cache[2]
        return y.reshape(*x.shape[:-1], y.shape[-1])


def enable(module: nn.Module) -> int:
    """Swap every plain nn.Linear under `module` to FastLinear; returns how many."""
    n = 0
    for m in module.modules():
        if type(m) is nn.Linear:
            m.__class__ = FastLinear
            n += 1
    return n


def disable(module: nn.Module) -> int:
    """The inverse of `enable` (drops the caches)."""
    n = 0
    for m in module.modules():
        if type(m) is FastLinear:
            m.__dict__.pop("_wt_cache", None)
            m.__class__ = nn.Linear
            n += 1
    return n

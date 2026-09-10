#!/usr/bin/env python
"""Is the ACT path dispatch-bound, and does tracing fix it?

WHY THIS IS A DIFFERENT QUESTION FROM THE UPDATE. `torch.compile` was measured
at 0.82x on `update_episodes` and is dead there — the update runs 256-row
minibatches through a trunk that flattens entities into the batch dimension, so
it is compute-bound and there is nothing for a tracer to win.

The ACT path is the opposite regime. A collection model fit across the k sweep
put a forward pass at **~230 us almost regardless of how many rows are in it**,
cross-checked at 352 us/batch-1-forward against a banked Node lane's own
`inference_seconds / seam_requests`. For a 1.17M-parameter net that is ~4.6 us
per tensor op — dispatch and `nn.Module._call_impl`, not arithmetic. At the
shipped k=8 that fixed cost is ~82% of collection.

So this times `agent.actor` at the batch sizes the act path actually sees,
eager against `torch.jit.trace` + `freeze`, and — the part that decides how the
result may be used — checks whether the traced logits are BIT-IDENTICAL.

  bit-identical  -> purely mechanical, adoptable on merit.
  not identical  -> it changes sampled actions, so it is an RNG-stream change
                    needing its own pre-reg, the same class as the port itself.

    python scripts/engine_actpath_bench.py runs/<run>/ckpt_012000008.pt
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def bench(fn, iters: int) -> float:
    for _ in range(5):
        fn()
    best = float("inf")
    for _ in range(iters):
        t = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t)
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", type=pathlib.Path)
    ap.add_argument("--batches", default="1,2,4,8,16,64,256",
                    help="the act path sees the LEARNER's pending count per "
                         "poll (~k/4 at steady state) and the OPPONENT's "
                         "per-member counts, which are 2-4 rows at k=256")
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/actpath_bench.json"))
    args = ap.parse_args(argv)

    import torch
    from engine_a1a import build_agent

    torch.set_num_threads(1)
    agent, cfg = build_agent(args.checkpoint)
    actor = agent.actor
    actor.eval()

    obs_dim = cfg.agent.get("obs_dim") or 828
    rows = []
    traced = None
    for B in [int(x) for x in args.batches.split(",")]:
        obs = torch.randn(B, obs_dim)
        with torch.no_grad():
            eager_out = actor(obs)
        t_eager = bench(lambda: actor(obs) if False else _no_grad(actor, obs), args.iters)

        if traced is None:
            with torch.no_grad():
                tr = torch.jit.trace(actor, torch.randn(1, obs_dim), check_trace=False)
                traced = torch.jit.freeze(tr.eval())
        try:
            with torch.no_grad():
                tr_out = traced(obs)
            t_traced = bench(lambda: _no_grad(traced, obs), args.iters)
            d = (eager_out - tr_out).abs().max().item()
            ident = bool(torch.equal(eager_out, tr_out))
        except Exception as exc:                       # noqa: BLE001
            rows.append({"batch": B, "eager_us": t_eager * 1e6,
                         "error": f"{type(exc).__name__}: {exc}"})
            print(f"  B={B:>4}  eager {t_eager*1e6:8.1f} us   traced FAILED")
            continue

        rows.append({"batch": B, "eager_us": t_eager * 1e6,
                     "traced_us": t_traced * 1e6,
                     "speedup": t_eager / t_traced,
                     "max_abs_diff": d, "bit_identical": ident})
        print(f"  B={B:>4}  eager {t_eager*1e6:8.1f} us   traced {t_traced*1e6:8.1f} us"
              f"   {t_eager/t_traced:5.2f}x   maxdiff {d:.2e}"
              f"   {'BIT-IDENTICAL' if ident else 'differs'}")

    ok = [r for r in rows if "speedup" in r]
    allident = all(r["bit_identical"] for r in ok) if ok else False
    out = {
        "question": "does torch.jit.trace+freeze help the ACT path, which the "
                    "collection model says is dispatch-bound at ~230 us per "
                    "forward almost regardless of row count",
        "torch_threads": 1,
        "rows": rows,
        "all_bit_identical": allident,
        "classification": (
            "MECHANICAL — traced logits are bit-identical at every batch size "
            "tested, so this changes no sampled action and needs no pre-reg."
            if allident else
            "CHANGES THE RNG STREAM — traced logits differ, so sampled actions "
            "differ. Same class as the collector port itself: it needs its own "
            "pre-registration, not adoption on merit."),
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\n{out['classification']}\nwritten: {args.out}")
    return 0


def _no_grad(mod, x):
    import torch
    with torch.no_grad():
        return mod(x)


if __name__ == "__main__":
    raise SystemExit(main())

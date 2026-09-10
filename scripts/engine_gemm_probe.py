#!/usr/bin/env python
"""Does `torch_threads` reach the GEMMs at all, or only the elementwise ops?

THE QUESTION THIS SETTLES. Raising `torch_threads` measures SLOWER on this box
(0.84x at T=2 on the async update; a banked 0.85x at T=6 on the sync one), and
there were three candidate explanations: synchronisation cost scaling with the
number of parallel regions, heterogeneous cores (10 P + 4 E, unpinned, a static
parallel region running at its slowest thread's speed), or — the one this
tests — that `torch.set_num_threads()` never touches the GEMMs in the first
place.

This build reports `BLAS_INFO=accelerate` with `MKLDNN not found`, so every
`Linear` dispatches into Apple's Accelerate sgemm. `set_num_threads()` widens
ATen `parallel_for` regions — ReLU, LayerNorm, cat, index_select, the Adam
elementwise loop — and does NOT reach inside Accelerate. If that is right, the
threads knob is closed permanently on this box and no sweep over it will ever
find anything.

So: time a bare `torch.mm` at the scorer's exact production shape, one process
per thread count with OMP sized at launch. A FLAT curve means Accelerate owns
the GEMM and the threads question is over. A curve that scales means the knob
does reach the matmuls and the penalty seen in the full update lives somewhere
else — which would keep the crossed threads x minibatches sweep worth running.

Thirty seconds, no fleet, no server, no training.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time


def _child(m: int, k: int, n: int, iters: int) -> None:
    import torch
    a = torch.randn(m, k)
    b = torch.randn(k, n)
    for _ in range(3):                      # warm the allocator and the pages
        torch.mm(a, b)
    best = min((lambda: (lambda t0: (torch.mm(a, b), time.perf_counter() - t0)[1])(
        time.perf_counter()))() for _ in range(iters))
    print("@@RESULT@@" + json.dumps({
        "threads": torch.get_num_threads(),
        "omp": os.environ.get("OMP_NUM_THREADS"),
        "seconds_min": best,
        "gflops": 2 * m * k * n / best / 1e9,
    }))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shape", default="2560,512,256",
                    help="M,K,N. Default is the pointer scorer's production "
                         "shape at the shipped recipe: 256 rows x 10 actions "
                         "= 2560, ctx+entity = 512 wide, into 256.")
    ap.add_argument("--threads", default="1,2,4,6")
    ap.add_argument("--iters", type=int, default=50)
    ap.add_argument("--child", type=int, default=0)
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/gemm_probe.json"))
    args = ap.parse_args(argv)
    m, k, n = (int(x) for x in args.shape.split(","))

    if args.child:
        _child(m, k, n, args.iters)
        return 0

    rows = []
    for t in [int(x) for x in args.threads.split(",")]:
        env = dict(os.environ)
        for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS"):
            env[var] = str(t)
        r = subprocess.run([sys.executable, __file__, "--child", "1",
                            "--shape", args.shape, "--iters", str(args.iters)],
                           capture_output=True, text=True, env=env)
        line = next((l for l in r.stdout.splitlines()
                     if l.startswith("@@RESULT@@")), None)
        if not line:
            print(f"  T={t} FAILED: {(r.stderr or r.stdout)[-200:]}")
            continue
        row = json.loads(line[len("@@RESULT@@"):])
        rows.append(row)
        print(f"  T={t:<2} {row['seconds_min'] * 1e3:7.3f} ms  "
              f"{row['gflops']:7.1f} GFLOP/s", flush=True)

    if rows:
        base = rows[0]["seconds_min"]
        for r in rows:
            r["x_vs_T1"] = base / r["seconds_min"]
        spread = max(r["x_vs_T1"] for r in rows)
        verdict = (
            "FLAT — set_num_threads does NOT reach the GEMM. Accelerate owns "
            "it, the threads knob is closed on this box, and no sweep over it "
            "will find anything."
            if spread < 1.15 else
            f"SCALES ({spread:.2f}x at best) — the knob DOES reach the matmuls, "
            "so the slowdown in the full update lives elsewhere and the "
            "crossed threads x minibatches sweep is still worth running.")
        out = {"shape": [m, k, n], "rows": rows, "best_x_vs_T1": spread,
               "verdict": verdict,
               "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(out, indent=2) + "\n")
        print(f"\n{verdict}\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

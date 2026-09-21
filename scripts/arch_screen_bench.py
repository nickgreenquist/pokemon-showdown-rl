"""Train-step microbenchmark for the R7 architecture screen's throughput gate
(configs/bc_arch_screen.yaml).

    python scripts/arch_screen_bench.py --out results/arch_screen/throughput.json

THE GATE READS attention / entity_deepsets — the ratio against TODAY's trunk.
The flat [512,512] MLP is measured too, and only so the historical number
stays checkable: the 34.6x that retired this architecture on 2026-08-07 was
MLP-relative, and quoting it against the entity trunk is the exact error
JOURNEY.md §11.6 records ("the honest ratio against today's trunk is simply
unknown").

WHAT IS TIMED, precisely, because a throughput number with an unstated scope
is how the 2026-08-07 kill happened: ONE supervised train step of the ACTOR —
forward, masked soft cross-entropy, backward, Adam step — at batch 512 with
`torch.set_num_threads(1)`. That is train_bc's inner loop, not an RL update
and not a lane's steps/s. The critic's step is timed separately and reported
beside it, because an RL update pays for both and a reader projecting to the
loop needs the second number rather than an assumption about it.

Median of >= 30 timed steps after 5 warmup steps. Median rather than mean:
this box runs other work (an FP evaluation arm was live when the screen ran),
and one descheduled step should not move the number. The spread is reported
so the reader can see whether it did.
"""

import argparse
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from rl.common.masking import masked_logits
from rl.envs.showdown import N_ACTIONS, OBS_DIM
from rl.networks.entity_attention import EntityAttentionNet
from rl.networks.entity_deepsets import EntityDeepSetsNet
from rl.networks.mlp import mlp

# The two recipes the screen actually fits, imported from nowhere and typed
# once here ON PURPOSE would be the landmine; they come from train_bc so the
# bench cannot benchmark a different net from the one that was fitted.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_bc import ATTENTION_SHARED_KWARGS, ENTITY_TRUNK_KWARGS  # noqa: E402

BATCH = 512
WARMUP = 5
STEPS = 30


def _builders(d_model: int, n_layers: int, n_heads: int) -> dict:
    attn_kw = dict(ATTENTION_SHARED_KWARGS, d_model=d_model, n_layers=n_layers,
                   n_heads=n_heads)
    return {
        "attention": lambda out: EntityAttentionNet(OBS_DIM, out, **attn_kw),
        "entity_deepsets": lambda out: EntityDeepSetsNet(OBS_DIM, out, **ENTITY_TRUNK_KWARGS),
        "mlp_512x512": lambda out: mlp(OBS_DIM, [512, 512], out, activation=nn.Tanh),
    }


def _time_steps(net, head: str, steps: int, warmup: int, seed: int) -> list[float]:
    """Wall time per full train step. The data is drawn ONCE and reused so
    that batch assembly is not inside the timed region — the fits index a
    resident tensor too."""
    g = torch.Generator().manual_seed(seed)
    obs = torch.rand(BATCH, OBS_DIM, generator=g)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    if head == "policy":
        masks = torch.zeros(BATCH, N_ACTIONS, dtype=torch.bool)
        for i in range(BATCH):
            k = int(torch.randint(2, N_ACTIONS + 1, (1,), generator=g))
            masks[i, torch.randperm(N_ACTIONS, generator=g)[:k]] = True
        tgt = torch.rand(BATCH, N_ACTIONS, generator=g) * masks
        tgt = tgt / tgt.sum(-1, keepdim=True)

        def step():
            logits = masked_logits(net(obs), masks)
            return -(tgt * F.log_softmax(logits, dim=-1)).sum(-1).mean()
    else:
        val = torch.rand(BATCH, generator=g)

        def step():
            return F.mse_loss(net(obs).squeeze(-1), val)

    out = []
    for i in range(warmup + steps):
        t0 = time.perf_counter()
        loss = step()
        opt.zero_grad()
        loss.backward()
        opt.step()
        dt = time.perf_counter() - t0
        if i >= warmup:
            out.append(dt)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--steps", type=int, default=STEPS)
    p.add_argument("--warmup", type=int, default=WARMUP)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--d-model", type=int, default=128)
    p.add_argument("--n-layers", type=int, default=2)
    p.add_argument("--n-heads", type=int, default=4)
    p.add_argument("--note", default="")
    args = p.parse_args()

    torch.set_num_threads(1)
    assert torch.get_num_threads() == 1, torch.get_num_threads()

    rows = {}
    for name, build in _builders(args.d_model, args.n_layers, args.n_heads).items():
        rows[name] = {}
        for head, out_dim in (("policy", N_ACTIONS), ("value", 1)):
            torch.manual_seed(args.seed)
            net = build(out_dim)
            if hasattr(net, "init_head"):
                net.init_head(0.01 if head == "policy" else 1.0)
            ts = _time_steps(net, head, args.steps, args.warmup, args.seed)
            a = np.asarray(ts)
            rows[name][head] = {
                "params": sum(q.numel() for q in net.parameters()),
                "median_s": float(np.median(a)),
                "mean_s": float(a.mean()),
                "p10_s": float(np.percentile(a, 10)),
                "p90_s": float(np.percentile(a, 90)),
                "n_timed": int(a.size),
            }
            print(f"{name:16s} {head:7s} params {rows[name][head]['params']:>9,} "
                  f"median {1e3 * rows[name][head]['median_s']:8.2f} ms "
                  f"(p10 {1e3 * rows[name][head]['p10_s']:.2f}, "
                  f"p90 {1e3 * rows[name][head]['p90_s']:.2f})", flush=True)

    def ratio(a, b, head):
        return rows[a][head]["median_s"] / rows[b][head]["median_s"]

    report = {
        "what_is_timed": (
            "one supervised train step of ONE net -- forward, loss, backward, "
            f"Adam step -- at batch {BATCH}, torch threads 1, CPU. NOT an RL "
            "update and NOT a lane's steps/s."
        ),
        "batch": BATCH, "warmup": args.warmup, "steps": args.steps,
        "d_model": args.d_model, "n_layers": args.n_layers, "n_heads": args.n_heads,
        "obs_dim": OBS_DIM, "n_actions": N_ACTIONS,
        "rows": rows,
        "ratios": {
            "GATE_attention_over_entity_deepsets_policy": ratio(
                "attention", "entity_deepsets", "policy"),
            "attention_over_entity_deepsets_value": ratio(
                "attention", "entity_deepsets", "value"),
            "attention_over_mlp_policy_HISTORICAL_COMPARATOR": ratio(
                "attention", "mlp_512x512", "policy"),
            "entity_deepsets_over_mlp_policy": ratio(
                "entity_deepsets", "mlp_512x512", "policy"),
        },
        "env": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "torch": torch.__version__,
            "torch_threads": torch.get_num_threads(),
            "python": platform.python_version(),
            "encoder_v2": os.environ.get("POKEMON_RL_ENCODER_V2"),
            "encoder_ids": os.environ.get("POKEMON_RL_ENCODER_IDS"),
            "loadavg": os.getloadavg(),
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "note": args.note,
    }
    try:
        report["env"]["git_sha"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        ).stdout.strip()
    except Exception:  # pragma: no cover - provenance is best effort
        report["env"]["git_sha"] = None

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nGATE attention / entity_deepsets (policy train step) = "
          f"{report['ratios']['GATE_attention_over_entity_deepsets_policy']:.2f}x")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

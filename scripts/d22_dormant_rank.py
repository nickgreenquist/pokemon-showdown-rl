"""D22 read 4, stage 2 (DESIGN §12): dormant neurons + feature effective rank.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d22_dormant_rank.py [--runs-root runs] [--out results/d22]

For each lane, forwards that lane's own final-policy self-play obs
(d22_collect_obs.py output) through actor and critic at the listed
checkpoints, and measures:

- DORMANT FRACTION per post-ReLU layer (Sokar et al., ReDo): unit i is
  dormant iff  E_x[h_i]  /  mean_j E_x[h_j]  <= tau. Reported at the paper's
  tau=0.025 and a looser 0.1. Post-ReLU only — LayerNorm outputs recenter,
  so "dormant" is not meaningful there.
- EFFECTIVE RANK of the ctx_net output feature matrix (Kumar et al.,
  srank_0.99: smallest k with top-k singular mass >= 99%) plus participation
  ratio (sum s^2)^2 / sum s^4, and the same for the mon_net entity features
  (rows = batch x 12 tokens).

Same obs set per lane across all its checkpoints, so trajectories are
directly comparable within a lane.

Defaults reproduce the D22 50M read (lanes 35/36/37, six checkpoints).
D18 adaptation (scoped in configs/showdown_sp_priv12m.yaml, SECONDARY block):
a checkpoint whose agent config carries privileged_dim gets its CRITIC built
widened, forwarded on obs ‖ priv (the `priv` array the adapted collect script
saves); the actor is forwarded on obs alone, unchanged. A priv checkpoint
probed with a priv-less npz raises loudly — no silent wrong read. D18 read:

    python scripts/d22_dormant_rank.py --lanes 39,40,41,42,43 \
        --steps 400000,3000000,6000000,9000000,12000000 \
        --run-prefix showdown_sp_priv12m_s --out results/d18

(400k not 500k: D18's checkpoint_every is 200k, so 500k does not exist.)

(--out results/d18, NOT the default: the script writes dormant.csv /
effective_rank.csv into --out and must not clobber the D22 artifacts; the
collect stage's npz files for the D18 lanes go in results/d18 too.)

In a privileged critic the shared mon/move subnets fire a second time on the
priv tokens (_priv_features): dormant fractions count ALL traffic through a
unit (a unit alive only on priv tokens is not dormant), while the named mon
rank read keeps the FIRST call — the observed 12 tokens — so it stays
comparable with the D22 numbers.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from rl.common.checkpoint import load_checkpoint
from rl.networks.entity_deepsets import EntityDeepSetsNet

D22_LANES = (35, 36, 37)
D22_STEPS = (500_000, 6_000_000, 12_000_000, 25_000_000, 37_500_000, 50_000_000)


def build(part: str, trunk_kwargs: dict, privileged_dim: int = 0) -> EntityDeepSetsNet:
    return EntityDeepSetsNet(in_dim=828, out_dim=10 if part == "actor" else 1,
                             privileged_dim=privileged_dim if part == "critic" else 0,
                             **trunk_kwargs)


def probe(net: EntityDeepSetsNet, obs: torch.Tensor) -> tuple[dict, dict]:
    acts: dict[str, list[torch.Tensor]] = {}

    def hook(name):
        def fn(_m, _i, out):
            acts.setdefault(name, []).append(out.detach())
        return fn

    handles = [m.register_forward_hook(hook(n))
               for n, m in net.named_modules()
               if isinstance(m, (torch.nn.ReLU, torch.nn.LayerNorm))]
    handles.append(net.ctx_net.register_forward_hook(hook("ctx_out")))
    with torch.no_grad():
        net(obs)
    for h in handles:
        h.remove()

    dormant = {}
    for name, hs in acts.items():
        if "ctx_out" in name or ".3" in name:  # LayerNorm outputs: rank only
            continue
        flat = torch.cat([h.reshape(-1, h.shape[-1]) for h in hs])
        mean_act = flat.mean(dim=0)
        score = mean_act / mean_act.mean().clamp_min(1e-12)
        dormant[name] = {
            "tau025": float((score <= 0.025).float().mean()),
            "tau100": float((score <= 0.1).float().mean()),
            "n": hs[0].shape[-1],
        }

    ranks = {}
    for name, key in (("ctx_out", "ctx"), ("mon_net.3", "mon")):
        first = acts[name][0]
        m = first.reshape(-1, first.shape[-1])
        s = torch.linalg.svdvals(m.float())
        cum = torch.cumsum(s, 0) / s.sum()
        ranks[f"srank99_{key}"] = int((cum < 0.99).sum()) + 1
        ranks[f"pr_{key}"] = float((s.pow(2).sum() ** 2) / s.pow(4).sum())
    return dormant, ranks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--out", default="results/d22")
    ap.add_argument("--lanes", default=",".join(str(s) for s in D22_LANES),
                    help="comma-separated seeds")
    ap.add_argument("--steps", default=",".join(str(s) for s in D22_STEPS),
                    help="comma-separated checkpoint steps")
    ap.add_argument("--run-prefix", default="showdown_sp_struct50m_s",
                    help="run dir name is <prefix><seed>")
    ap.add_argument("--obs-prefix", default="obs_s",
                    help="obs npz name is <prefix><seed>.npz under --out")
    args = ap.parse_args()
    out = Path(args.out)
    lanes = tuple(int(s) for s in args.lanes.split(","))
    steps = tuple(int(s) for s in args.steps.split(","))

    d_rows, r_rows = [], []
    for seed in lanes:
        data = np.load(out / f"{args.obs_prefix}{seed}.npz")
        obs = torch.from_numpy(data["obs"])
        priv = torch.from_numpy(data["priv"]) if "priv" in data else None
        rd = Path(args.runs_root) / f"{args.run_prefix}{seed}"
        for step in steps:
            c = load_checkpoint(rd / f"ckpt_{step:09d}.pt")
            tk = c["config"]["agent"]["trunk_kwargs"]
            pd_dim = int(c["config"]["agent"].get("privileged_dim") or 0)
            if pd_dim and priv is None:
                raise SystemExit(
                    f"s{seed} ckpt_{step:09d} has privileged_dim={pd_dim} but "
                    f"{args.obs_prefix}{seed}.npz carries no priv array — "
                    "re-collect with the adapted d22_collect_obs.py"
                )
            for part in ("actor", "critic"):
                net = build(part, tk, pd_dim)
                net.load_state_dict(c["agent"][part])
                net.eval()
                x = obs
                if part == "critic" and pd_dim:
                    x = torch.cat([obs, priv], dim=-1)
                dormant, ranks = probe(net, x)
                for layer, d in dormant.items():
                    d_rows.append({"seed": seed, "step": step, "part": part,
                                   "layer": layer, **d})
                r_rows.append({"seed": seed, "step": step, "part": part, **ranks})
        print(f"s{seed} done")

    dd, rr = pd.DataFrame(d_rows), pd.DataFrame(r_rows)
    dd.to_csv(out / "dormant.csv", index=False)
    rr.to_csv(out / "effective_rank.csv", index=False)

    print("\n=== dormant fraction tau=0.025 (actor), by layer, across steps ===")
    for seed in lanes:
        d = dd[(dd.seed == seed) & (dd.part == "actor")]
        for layer in sorted(d.layer.unique()):
            t = d[d.layer == layer].set_index("step")["tau025"]
            traj = " -> ".join(f"{t[s]:.2f}" for s in steps)
            print(f"  s{seed} {layer:12s} {traj}")
    print("\n=== ctx effective rank (srank99 / PR of 384), actor | critic ===")
    for seed in lanes:
        for part in ("actor", "critic"):
            t = rr[(rr.seed == seed) & (rr.part == part)].set_index("step")
            traj = " -> ".join(
                f"{t.loc[s, 'srank99_ctx']}/{t.loc[s, 'pr_ctx']:.0f}" for s in steps)
            print(f"  s{seed} {part:6s} {traj}")


if __name__ == "__main__":
    main()

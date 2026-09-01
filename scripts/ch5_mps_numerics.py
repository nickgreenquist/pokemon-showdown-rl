"""MPS-vs-CPU NUMERICS CHECK for the masked policy (HANDOFF item 3).

Action masking is a HARNESS CONTRACT (CLAUDE.md): logits are masked with a
FINITE `-1e8` sentinel rather than `-inf`, precisely because
`0 * -inf = NaN` would flow silently into the entropy bonus. `-inf` and
denormal behaviour differ across backends, so before any MPS proposal can be
made the two devices must be shown to agree on:

  * the raw actor logits,
  * `masked_logits` -- the sentinel itself,
  * `masked_entropy` -- the term the sentinel exists to protect,
  * softmax mass at ILLEGAL positions, which must be EXACTLY 0.0, and
  * the deterministic argmax action, the only thing that changes behaviour.

Real observations, not synthetic ones: the entity trunk tokenizes species and
move ids out of the observation's id suffix, so random floats would exercise
a different code path than training does.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 python \
        scripts/ch5_mps_numerics.py runs/<run>/ckpt_050000000.pt
"""

import argparse
import dataclasses
import json

import numpy as np
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.masking import masked_entropy, masked_logits
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.train import make_agent


def collect(agent, env, n):
    """n real (obs, mask) pairs, played by the policy under test."""
    obs_out, mask_out = [], []
    episode = 0
    while len(obs_out) < n:
        obs, info = env.reset(seed=90_000 + episode)
        episode += 1
        done = False
        while not done and len(obs_out) < n:
            mask = info["action_mask"]
            obs_out.append(np.asarray(obs, dtype=np.float32))
            mask_out.append(np.asarray(mask, dtype=bool))
            obs, _, term, trunc, info = env.step(agent.act(obs, mask, deterministic=True))
            done = term or trunc
    return np.stack(obs_out), np.stack(mask_out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("checkpoint")
    ap.add_argument("--samples", type=int, default=512)
    args = ap.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)

    agents = {}
    for device in ("cpu", "mps"):
        agent = make_agent(dataclasses.replace(cfg, device=device), env)
        agent.load_state_dict(ckpt["agent"])
        agents[device] = agent

    obs, masks = collect(agents["cpu"], env, args.samples)
    env.close()

    out = {}
    for device, agent in agents.items():
        o = torch.as_tensor(obs, dtype=torch.float32, device=device)
        m = torch.as_tensor(masks, dtype=torch.bool, device=device)
        with torch.no_grad():
            raw = agent.actor(o)
            masked = masked_logits(raw, m)
            ent = masked_entropy(raw, m)
            probs = torch.softmax(masked, dim=-1)
            values = agent.critic(o).squeeze(-1)
            actions = masked.argmax(dim=-1)
        out[device] = {
            "raw": raw.float().cpu(),
            "masked": masked.float().cpu(),
            "entropy": ent.float().cpu(),
            "probs": probs.float().cpu(),
            "values": values.float().cpu(),
            "actions": actions.cpu(),
        }

    c, g = out["cpu"], out["mps"]
    illegal = ~torch.as_tensor(masks, dtype=torch.bool)
    report = {
        "checkpoint": args.checkpoint,
        "samples": int(obs.shape[0]),
        "actions_dim": int(c["raw"].shape[1]),
        "illegal_fraction": float(illegal.float().mean()),
        "max_abs_diff": {
            k: float((c[k] - g[k]).abs().max())
            for k in ("raw", "masked", "entropy", "probs", "values")
        },
        "actions_identical": bool(torch.equal(c["actions"], g["actions"])),
        "actions_disagreeing": int((c["actions"] != g["actions"]).sum()),
        "nan_or_inf": {
            f"{d}/{k}": bool(~torch.isfinite(v[k]).all())
            for d, v in out.items()
            for k in ("raw", "masked", "entropy", "probs", "values")
        },
        "illegal_prob_mass_exactly_zero": {
            d: bool((v["probs"][illegal] == 0.0).all()) for d, v in out.items()
        },
        "illegal_prob_mass_max": {
            d: float(v["probs"][illegal].max()) for d, v in out.items()
        },
        "sentinel_preserved": {
            d: bool((v["masked"][illegal] == -1e8).all()) for d, v in out.items()
        },
    }
    print(json.dumps(report, indent=2))

    fails = []
    if not report["actions_identical"]:
        fails.append(f"{report['actions_disagreeing']} argmax disagreements")
    if any(report["nan_or_inf"].values()):
        fails.append("non-finite values")
    for d in ("cpu", "mps"):
        if not report["illegal_prob_mass_exactly_zero"][d]:
            fails.append(f"{d}: illegal actions carry probability mass")
        if not report["sentinel_preserved"][d]:
            fails.append(f"{d}: -1e8 sentinel not preserved")
    print("\n" + ("FAIL: " + "; ".join(fails) if fails
                  else "PASS: MPS and CPU agree on the masked policy."))


if __name__ == "__main__":
    main()

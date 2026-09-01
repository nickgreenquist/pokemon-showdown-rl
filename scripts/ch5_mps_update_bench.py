"""LEARNER-ONLY micro-benchmark: `update()` at real width and real batch.

Why this exists rather than the training run: on current code **MPS cannot
run the training loop at all** -- `rl/selfplay/pool.py:88` samples the pool
opponent's move with `torch.multinomial(probs, 1, generator=self.generator)`
where `probs` follows `agent.device` but the generator is always a CPU one, so
an MPS lane dies with `Expected a 'mps' device type for generator but found
'cpu'` on the first opponent decision. That crash IS the headline finding; this
script prices what fixing it would buy.

It replays a fixed TAPE of transitions through `agent.update()` exactly as the
vector loop does -- one call per env step, so the 3,839 buffer appends are
timed too and the number is commensurable with the logged `time/update_sec`.
Shapes, dtypes and the observation id-suffix ranges are real: observations and
masks are collected from a LIVE env and tiled to the rollout. Rewards,
terminations and the D25 opponent-action labels are synthesised (a legal action
per row, which is that label's actual support). Content does not change the
work done; shape and validity do, and those are preserved.

VALIDATION: the cpu arm of this bench is compared against the REAL logged
`time/update_sec` from a training run of the same config. If they disagree the
proxy is not trustworthy and the MPS number should not be believed either.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 python \
        scripts/ch5_mps_update_bench.py --config configs/ch5_mps_bench.yaml
"""

import argparse
import dataclasses
import json
import time

import numpy as np
import torch
import yaml

from rl.common.config import Config
from rl.envs.make import make_env
from rl.train import make_agent

ARMS = {"cpu1": ("cpu", 1), "cpu6": ("cpu", 6), "mps": ("mps", 1)}


def _shim(cfg, num_envs):
    """The spaces + width `make_agent` reads, without opening eight websockets
    we would never step. Both the `single_*` and plain names: make_agent's
    `getattr(env, "single_...", env....)` evaluates its DEFAULT eagerly."""
    from types import SimpleNamespace

    probe = make_env(cfg.env_id, cfg.seed, env_kwargs={"opponent": "heuristics"})
    shim = SimpleNamespace(
        single_observation_space=probe.observation_space,
        single_action_space=probe.action_space,
        observation_space=probe.observation_space,
        action_space=probe.action_space,
        num_envs=num_envs,
    )
    probe.close()
    return shim


def collect_tape(cfg, steps, num_envs, rng):
    """Real (obs, mask, opp_choice) from a LIVE pool-backed env, tiled to
    (steps, num_envs, ...).

    Pool-backed, not heuristics: D25's `info["opp_choice"]` is a (kind, id,
    flags) TRIPLE emitted only by a PoolPlayer opponent, and the aux head's row
    filter reads it -- synthesising the triple would change how many rows the
    auxiliary loss actually trains on, which is exactly the work being timed.
    """
    from rl.selfplay.pool import SnapshotPool

    seed_agent = make_agent(dataclasses.replace(cfg, device="cpu"),
                            _shim(cfg, num_envs))
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(seed_agent)
    env = make_env(cfg.env_id, cfg.seed,
                   env_kwargs={"opponent": pool, "opp_action": True})

    obs_list, mask_list, choice_list = [], [], []
    want = max(512, num_envs * 8)
    episode = 0
    while len(obs_list) < want:
        obs, info = env.reset(seed=70_000 + episode)
        episode += 1
        done = False
        while not done and len(obs_list) < want:
            mask = np.asarray(info["action_mask"], dtype=bool)
            legal = np.flatnonzero(mask)
            prev_obs = np.asarray(obs, dtype=np.float32)
            obs, _, term, trunc, info = env.step(int(rng.choice(legal)))
            choice = info.get("opp_choice")
            if choice is None:          # wait states emit no decision
                done = term or trunc
                continue
            obs_list.append(prev_obs)
            mask_list.append(mask)
            choice_list.append(np.asarray(choice, dtype=np.int64))
            done = term or trunc
    env.close()

    real_obs = np.stack(obs_list)
    real_masks = np.stack(mask_list)
    real_choice = np.stack(choice_list)
    total = steps * num_envs
    idx = rng.integers(0, len(real_obs), size=total)
    return (real_obs[idx].reshape(steps, num_envs, -1),
            real_masks[idx].reshape(steps, num_envs, -1),
            real_choice[idx].reshape(steps, num_envs, -1))


def legal_actions(masks, rng):
    """A uniformly legal action per row -- the behaviour action's support. Only
    the ACTION is synthesised; observations, masks and the D25 opponent-action
    labels are all real (see collect_tape)."""
    flat = masks.reshape(-1, masks.shape[-1])
    out = np.empty(flat.shape[0], dtype=np.int64)
    for i, row in enumerate(flat):
        out[i] = rng.choice(np.flatnonzero(row))
    return out.reshape(masks.shape[:-1])


def run_arm(cfg, arm, tape, repeats):
    device, threads = ARMS[arm]
    torch.set_num_threads(threads)
    obs, masks, actions, opp_choice = tape
    steps, num_envs = actions.shape

    agent = make_agent(dataclasses.replace(cfg, device=device), _shim(cfg, num_envs))

    zeros_r = np.zeros(num_envs, dtype=np.float32)
    false_n = np.zeros(num_envs, dtype=bool)
    timings = []
    for r in range(repeats):
        t0 = time.perf_counter()
        for t in range(steps):
            nxt = (t + 1) % steps
            agent.update((
                obs[t], actions[t], zeros_r, obs[nxt], false_n, false_n,
                masks[t], masks[nxt], None, None, opp_choice[t],
            ))
        timings.append(time.perf_counter() - t0)
    return {"arm": arm, "device": device, "torch_threads": threads,
            "rollouts": timings,
            "warmup_sec": round(timings[0], 3),
            "update_sec_mean": round(float(np.mean(timings[1:])), 3) if len(timings) > 1 else None,
            "update_sec_min": round(float(min(timings[1:])), 3) if len(timings) > 1 else None,
            "update_sec_max": round(float(max(timings[1:])), 3) if len(timings) > 1 else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/ch5_mps_bench.yaml")
    ap.add_argument("--arms", default="cpu1,mps,cpu6")
    ap.add_argument("--repeats", type=int, default=3,
                    help="replays per arm; the first is discarded as warm-up")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config(**yaml.safe_load(open(args.config)))
    steps = cfg.agent["rollout_steps"]
    num_envs = cfg.num_envs
    rng = np.random.default_rng(0)

    print(f"tape: {steps} x {num_envs} = {steps * num_envs} steps, "
          f"{cfg.agent['epochs']} epochs x {cfg.agent['minibatches']} minibatches, "
          f"hidden {cfg.agent['hidden_sizes']}, trunk {cfg.agent['trunk']}",
          flush=True)
    obs, masks, opp_choice = collect_tape(cfg, steps, num_envs, rng)
    actions = legal_actions(masks, rng)
    tape = (obs, masks, actions, opp_choice)

    results = []
    for arm in args.arms.split(","):
        print(f"[{time.strftime('%H:%M:%S')}] {arm} ...", flush=True)
        try:
            results.append(run_arm(cfg, arm, tape, args.repeats))
        except Exception as exc:
            results.append({"arm": arm, "device": ARMS[arm][0],
                            "FAILED": f"{type(exc).__name__}: {exc}"})
        print(json.dumps(results[-1]), flush=True)

    print("\n=== LEARNER-ONLY update_sec (warm-up discarded) ===")
    base = next((r for r in results
                 if r["arm"] == "cpu1" and r.get("update_sec_mean")), None)
    for r in results:
        if r.get("FAILED"):
            print(f"  {r['arm']:6s} FAILED: {r['FAILED']}")
            continue
        line = (f"  {r['arm']:6s} {r['update_sec_mean']:.3f}s "
                f"({r['update_sec_min']:.3f}-{r['update_sec_max']:.3f}), "
                f"warm-up {r['warmup_sec']:.3f}s")
        if base:
            line += f"  -> {base['update_sec_mean'] / r['update_sec_mean']:.2f}x vs cpu1"
        print(line)
    print("\nLearner only. Collection is Node-bound and cannot benefit, so no "
          "end-to-end speedup follows from this column.")
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()

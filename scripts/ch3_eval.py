"""Chapter-3 eval driver: chunked, resumable, pre-reg-driven.

    python scripts/ch3_eval.py --prereg configs/eval/ch3_rung0.yaml --list-jobs
    python scripts/ch3_eval.py --prereg configs/eval/ch3_rung0.yaml --job a1_b0
    python scripts/ch3_eval.py --prereg configs/eval/ch3_rung0.yaml --selfcheck

Each job = one (arm, lane|batch): `battles` episodes in `chunks` sequential
calls to `_run_eval_episodes`, seed_start advanced per chunk (inert on
Showdown — battles are server-rolled; recorded anyway), ONE JSON PER CHUNK in
<results_dir>/. A killed job resumes at the chunk boundary; worst-case loss
is one chunk. When all chunks exist the job writes a merged
<job>.final.json. Report fields mirror scripts/eval_checkpoint.py:
`eval/win_rate` (env-supplied) is authoritative; `wins_from_returns` is the
sign-bug cross-check and MUST agree exactly (R0-a; the grader enforces).

Pre-flight, every invocation: checkpoint sha256s match the pre-reg (R0-d),
`simulator: 4` set in showdown/config/config.js, realized usernames printed.
--selfcheck runs the R0-c gate: for each lane, a single-member ensemble must
reproduce that member's argmax on 1000 synthetic decision points, 1000/1000.
"""

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

import numpy as np
import torch
import yaml

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import _run_eval_episodes, eval_metrics
from rl.envs.make import make_eval_env
from rl.envs.normalize import frozen_obs_env
from rl.envs.showdown import mask_desync_total
from rl.search.ensemble import EnsembleAgent
from rl.train import make_agent


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _load_prereg(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _jobs(prereg: dict) -> dict[str, dict]:
    jobs: dict[str, dict] = {}
    arms = prereg["arms"]
    for lane in arms["A0"]["lanes"]:
        jobs[f"a0_{lane}"] = {"arm": "A0", "members": [lane]}
    for b in range(arms["A1"]["batches"]):
        jobs[f"a1_b{b}"] = {"arm": "A1", "members": arms["A1"]["members"], "batch": b}
    for lane in arms["A2"]["members"]:
        members = [m for m in arms["A2"]["members"] if m != lane]
        jobs[f"a2_loo_{lane}"] = {"arm": "A2", "members": members}
    return jobs


def _preflight(prereg: dict) -> None:
    import os

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", (
            f"{var}=1 required (both encoder env vars at every eval — "
            "ch3_search_design_r2.md R2 protocol; the D26 checkpoints are "
            "828-d id-suffix objects)"
        )
    for lane, spec in prereg["checkpoints"].items():
        got = _sha256(spec["path"])
        assert got == spec["sha256"], (
            f"R0-d FAIL: {lane} checkpoint sha256 {got} != prereg {spec['sha256']}"
        )
    cfg_js = Path("showdown/config/config.js").read_text()
    m = re.search(r"^\s*simulator:\s*(\d+)", cfg_js, re.M)
    assert m and int(m.group(1)) >= 4, (
        "showdown/config/config.js: `simulator: 4` not set "
        "(the gitignored config was re-cloned? see CLAUDE.md)"
    )
    print("preflight: R0-d sha256 x4 OK; simulator>=4 OK")


def _load_member(prereg: dict, lane: str, env=None):
    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    if env is None:
        env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg, env


def _print_username(env) -> None:
    try:
        poke = env.unwrapped._env.env
        names = [getattr(p, "username", "?") for p in (poke.agent1, poke.agent2)]
    except AttributeError:
        try:
            poke = env.unwrapped._env.env
            names = [poke.username]
        except AttributeError:
            names = ["<not found>"]
    print(f"realized usernames: {names}")


def run_job(prereg: dict, name: str) -> None:
    job = _jobs(prereg)[name]
    arm = prereg["arms"][job["arm"]]
    battles, chunks = arm["battles"], arm["chunks"]
    chunk_size = battles // chunks
    out_dir = Path(prereg["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    first_lane = job["members"][0]
    agent0, cfg, env = _load_member(prereg, first_lane)
    torch.set_num_threads(cfg.torch_threads)
    if len(job["members"]) == 1 and job["arm"] == "A0":
        agent = agent0
    else:
        members = [agent0]
        for lane in job["members"][1:]:
            m, _, _ = _load_member(prereg, lane, env=env)
            members.append(m)
        agent = EnsembleAgent(members)
    _print_username(env)

    base = cfg.eval_episodes + job.get("batch", 0) * battles
    desync_before = mask_desync_total()
    for k in range(chunks):
        chunk_path = out_dir / f"{name}.chunk{k:02d}.json"
        if chunk_path.exists():
            print(f"{chunk_path.name}: exists, skipping")
            continue
        seed_start = base + k * chunk_size
        returns, outcomes, faints = _run_eval_episodes(
            agent, env, chunk_size, seed_start=seed_start
        )
        metrics = eval_metrics(returns, outcomes, faints, win_rate=True)
        desync_now = mask_desync_total()
        report = {
            "job": name,
            "arm": job["arm"],
            "members": job["members"],
            "chunk": k,
            "episodes": chunk_size,
            "seed_start": seed_start,
            **metrics,
            "return_mean": float(np.mean(returns)),
            "wins_from_returns": sum(1 for r in returns if r > 0) / len(returns),
            "ties_from_returns": sum(1 for r in returns if r == 0) / len(returns),
            "mask_desyncs_delta": desync_now - desync_before,
            "returns": returns,
        }
        if isinstance(agent, EnsembleAgent):
            report["ensemble_decisions"] = agent.decisions
            report["ensemble_flips"] = agent.flips
        desync_before = desync_now
        chunk_path.write_text(json.dumps(report, indent=2) + "\n")
        print(
            f"{chunk_path.name}: win_rate {report['eval/win_rate']:.4f} "
            f"({chunk_size} battles, seed_start {seed_start})"
        )
    _merge(prereg, name, out_dir, chunks)
    env.close()


def _merge(prereg: dict, name: str, out_dir: Path, chunks: int) -> None:
    paths = [out_dir / f"{name}.chunk{k:02d}.json" for k in range(chunks)]
    if not all(p.exists() for p in paths):
        return
    reports = [json.loads(p.read_text()) for p in paths]
    returns = [r for rep in reports for r in rep["returns"]]
    n = len(returns)
    wins = sum(rep["eval/win_rate"] * rep["episodes"] for rep in reports) / n
    wfr = sum(rep["wins_from_returns"] * rep["episodes"] for rep in reports) / n
    final = {
        "job": name,
        "arm": reports[0]["arm"],
        "members": reports[0]["members"],
        "episodes": n,
        "eval/win_rate": wins,
        "wins_from_returns": wfr,
        "mask_desyncs": sum(rep["mask_desyncs_delta"] for rep in reports),
        "chunks": chunks,
    }
    last = reports[-1]
    if "ensemble_decisions" in last:
        final["ensemble_decisions"] = last["ensemble_decisions"]
        final["ensemble_flips"] = last["ensemble_flips"]
        final["ensemble_flip_rate"] = (
            last["ensemble_flips"] / last["ensemble_decisions"]
            if last["ensemble_decisions"]
            else None
        )
    (out_dir / f"{name}.final.json").write_text(json.dumps(final, indent=2) + "\n")
    print(f"{name}.final.json: pooled win_rate {wins:.5f} over {n}")


def selfcheck(prereg: dict) -> None:
    """R0-c: single-member ensemble == member argmax, 1000/1000, per lane."""
    from rl.envs.showdown import OBS_DIM

    rng = random.Random(20260821)
    for lane in prereg["checkpoints"]:
        agent, cfg, _spaces_env = _load_member_spaces(prereg, lane)
        wrapped = EnsembleAgent([agent])
        agree = 0
        for i in range(1000):
            obs = np.array(
                [rng.gauss(0, 1) for _ in range(OBS_DIM)], dtype=np.float32
            )
            mask = np.array([rng.random() < 0.7 for _ in range(10)], dtype=bool)
            if not mask.any():
                mask[rng.randrange(10)] = True
            a = agent.act(obs, mask, deterministic=True)
            b = wrapped.act(obs, mask, deterministic=True)
            agree += int(a == b)
        assert agree == 1000, f"R0-c FAIL on {lane}: {agree}/1000"
        print(f"R0-c {lane}: 1000/1000")


def _load_member_spaces(prereg: dict, lane: str):
    """Load a member against spaces only (no websocket) — selfcheck path."""
    from types import SimpleNamespace

    import gymnasium as gym

    from rl.envs.showdown import OBS_DIM

    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    spaces = SimpleNamespace(
        observation_space=gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32),
        action_space=gym.spaces.Discrete(10),
    )
    agent = make_agent(cfg, spaces)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg, spaces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--job")
    parser.add_argument("--list-jobs", action="store_true")
    parser.add_argument("--selfcheck", action="store_true")
    args = parser.parse_args()
    prereg = _load_prereg(args.prereg)
    if args.list_jobs:
        for name in _jobs(prereg):
            print(name)
        return
    if args.selfcheck:
        _preflight(prereg)
        selfcheck(prereg)
        return
    assert args.job, "--job, --list-jobs or --selfcheck required"
    _preflight(prereg)
    run_job(prereg, args.job)


if __name__ == "__main__":
    main()

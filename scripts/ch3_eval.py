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

R2 (the search rungs): an arm with `kind: search` (plus `dose`, per-lane
`lanes`) runs each lane through rl/search's SearchAgent via
_SearchEvalAdapter — battle1 read live off the env, decision rng keyed by
the GLOBAL episode index so re-run chunks replay identically; per-chunk
reports carry search counter deltas + ms/leaves stats (R2-8 budget gate,
F3). `kind: policy` arms run the lane's bare checkpoint. Chunk 0 of EVERY
verdict arm installs the raise-on-access battle2 sentinel (SF-13): fatal
on any rl/search-originated read, transparent to the harness's own
battle2 machinery. The watchdog RAISES and kills the chunk — resume
re-runs it; there is no silent policy fallback anywhere.

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
import sys
import time
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


class PurityIncident(RuntimeError):
    """FG-4/SF-13: search code touched seat-2 state. Retraction, not caveat."""


class _Battle2Sentinel:
    """Raise-on-access sentinel for `battle2` (SF-13, chunk 0 of every
    verdict arm). A class-level DATA descriptor: poke-env's own machinery
    (race_get, the SingleAgentWrapper wait bypass) reads battle2
    legitimately, so the sentinel walks the caller's stack and raises ONLY
    when a frame under rl/search/ is present. Installed on the inner
    poke-env class for chunk 0, uninstalled after — the ~us-per-access
    stack walk never touches the timed arms. This class lives HERE and not
    under rl/search/ because FG-4's static grep forbids the string
    battle2 in that directory."""

    def __init__(self) -> None:
        self._store: dict[int, object] = {}

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        f = sys._getframe(1)
        while f is not None:
            fn = f.f_code.co_filename
            if "rl/search" in fn or "rl\\search" in fn:
                raise PurityIncident(
                    "battle2 accessed from rl/search "
                    f"({fn}:{f.f_lineno}) — FG-4/SF-13 purity incident"
                )
            f = f.f_back
        return self._store.get(id(obj))

    def __set__(self, obj, value) -> None:
        self._store[id(obj)] = value


def _install_battle2_sentinel(poke) -> tuple[type, object]:
    """Swap the instance's battle2 for the sentinel descriptor; returns the
    (class, sentinel) handle for uninstall."""
    cls = type(poke)
    assert not isinstance(
        cls.__dict__.get("battle2"), _Battle2Sentinel
    ), "battle2 sentinel already installed"
    sentinel = _Battle2Sentinel()
    current = poke.__dict__.pop("battle2", None)
    sentinel._store[id(poke)] = current
    setattr(cls, "battle2", sentinel)
    return cls, sentinel


def _uninstall_battle2_sentinel(poke, handle: tuple[type, object]) -> None:
    cls, sentinel = handle
    delattr(cls, "battle2")
    poke.battle2 = sentinel._store.get(id(poke))


class _SearchEvalAdapter:
    """SearchAgent -> the eval loop's `agent.act(obs, mask, deterministic)`
    interface. Reads battle1 (and ONLY battle1) live off the env; keys the
    D2 decision rng by the GLOBAL episode index (seed_start + episode,
    latched on battle_tag change) so a re-run chunk replays identical
    randomness. Collects per-decision wall ms and realized leaves for the
    R2-8 budget gate and F3 (searched decisions only — placeholder skips
    are excluded from the mean and reported separately, per F3)."""

    def __init__(self, search_agent, env):
        self._sa = search_agent
        self._env = env
        self._next_battle_index = 0
        self._battle_index = -1
        self._decision_index = 0
        self._tag = None
        self.ms: list[float] = []
        self.leaves: list[int] = []
        self._counter_snapshot = dict(search_agent.counters)

    def begin_chunk(self, base_battle_index: int) -> None:
        self._next_battle_index = base_battle_index
        self._tag = None

    def act(self, obs, mask, deterministic=True):
        assert deterministic, "R2 protocol is deterministic-only"
        poke = self._env.unwrapped._env.env
        battle = poke.battle1
        assert battle is not None, "search decision before battle1 exists"
        tag = battle.battle_tag
        if tag != self._tag:
            self._battle_index = self._next_battle_index
            self._next_battle_index += 1
            self._decision_index = 0
            self._tag = tag
        t0 = time.perf_counter()
        action, stats = self._sa.act(
            battle, obs, np.asarray(mask), self._battle_index, self._decision_index
        )
        if "search/leaves" in stats:  # searched (non-placeholder) decision
            self.ms.append((time.perf_counter() - t0) * 1e3)
            self.leaves.append(int(stats["search/leaves"]))
        self._decision_index += 1
        return action

    def chunk_summary(self) -> dict:
        """Per-chunk DELTAS (a resumed job restarts the SearchAgent's
        cumulative counters, so the merge sums chunk deltas)."""
        ms = np.array(self.ms) if self.ms else np.array([0.0])
        lv = np.array(self.leaves) if self.leaves else np.array([0])
        out = {
            "search/ms_mean": float(ms.mean()),
            "search/ms_p50": float(np.percentile(ms, 50)),
            "search/ms_p99": float(np.percentile(ms, 99)),
            "search/leaves_mean": float(lv.mean()),
            "search/leaves_max": int(lv.max()),
            "search/searched_decisions": len(self.ms),
            "oppact/entropy_median": self._sa.entropy_median(),
        }
        for key in ("search/decisions", "search/placeholder_skips", "search/flips"):
            out[key] = self._sa.counters[key] - self._counter_snapshot[key]
        self._counter_snapshot = dict(self._sa.counters)
        self.ms, self.leaves = [], []
        return out


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
    """One job per (arm, lane|batch), from the pre-reg's arm kinds:
    policy (bare checkpoint per lane), search (SearchAgent per lane, R2),
    ensemble (member batches, R0), ensemble_loo (leave-one-out, R0)."""
    jobs: dict[str, dict] = {}
    for arm_name, spec in prereg["arms"].items():
        kind, prefix = spec["kind"], arm_name.lower()
        if kind == "policy":
            for lane in spec["lanes"]:
                jobs[f"{prefix}_{lane}"] = {"arm": arm_name, "members": [lane]}
        elif kind == "search":
            for lane in spec["lanes"]:
                jobs[f"{prefix}_{lane}"] = {
                    "arm": arm_name, "members": [lane],
                    "search_dose": spec["dose"],
                }
        elif kind == "ensemble":
            for b in range(spec["batches"]):
                jobs[f"{prefix}_b{b}"] = {
                    "arm": arm_name, "members": spec["members"], "batch": b,
                }
        elif kind == "ensemble_loo":
            for lane in spec["members"]:
                jobs[f"{prefix}_loo_{lane}"] = {
                    "arm": arm_name,
                    "members": [m for m in spec["members"] if m != lane],
                }
        else:
            raise ValueError(f"unknown arm kind {kind!r} on {arm_name}")
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
    print(f"preflight: R0-d sha256 x{len(prereg['checkpoints'])} OK; "
          "simulator>=4 OK")


def _load_member(prereg: dict, lane: str, env=None):
    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    if env is None:
        env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg, env


def _resolve_evaluator(prereg, first_lane, spec_eval, env, agent0):
    """R3 E-cell dial + R4 F5 provenance. `loo` resolves its pool here: the
    OTHER lanes' agents, this lane excluded. F5 (ch3_r4 pre-reg): the
    membership asserts fire at resolution — pool size, own key absent, own
    agent excluded by IDENTITY — and the returned provenance dict is written
    into every chunk JSON so the gate is gradeable from disk."""
    if not spec_eval:
        return None, None
    evaluator = dict(spec_eval)
    provenance = {"kind": evaluator["kind"]}
    if evaluator["kind"] == "loo":
        pool = [x for x in evaluator.pop("pool") if x != first_lane]
        assert len(pool) == 3, f"F5: loo pool resolved to {pool}"
        assert first_lane not in pool, f"F5: own lane {first_lane} in pool"
        evaluator["agents"] = [
            _load_member(prereg, x, env=env)[0] for x in pool
        ]
        assert all(a is not agent0 for a in evaluator["agents"]), (
            "F5: the lane's own agent object is in the ensemble"
        )
        provenance["members"] = pool
        provenance["member_sha256"] = [
            prereg["checkpoints"][x]["sha256"] for x in pool
        ]
    return evaluator, provenance


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
    adapter = None
    if "search_dose" in job:
        from rl.search.agent import SearchAgent
        from rl.search.matrix import DOSES

        assert getattr(env.unwrapped, "_privileged", None) is False, (
            "SF-13: the eval env must not emit info['privileged']"
        )
        evaluator, eval_provenance = _resolve_evaluator(
            prereg, first_lane, prereg["arms"][job["arm"]].get("evaluator"),
            env, agent0,
        )
        sa = SearchAgent(
            agent0, DOSES[job["search_dose"]],
            checkpoint_seed=int(first_lane.lstrip("s")),
            evaluator=evaluator,
        )
        adapter = agent = _SearchEvalAdapter(sa, env)
    elif len(job["members"]) == 1:
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
        if adapter is not None:
            adapter.begin_chunk(seed_start)
        sentinel_handle = None
        if k == 0:
            # SF-13: the raise-on-access battle2 sentinel runs at chunk 0
            # of EVERY verdict arm (policy and search alike)
            sentinel_handle = _install_battle2_sentinel(env.unwrapped._env.env)
        started_at = time.time()
        try:
            returns, outcomes, faints = _run_eval_episodes(
                agent, env, chunk_size, seed_start=seed_start
            )
        finally:
            if sentinel_handle is not None:
                _uninstall_battle2_sentinel(env.unwrapped._env.env, sentinel_handle)
                print(f"chunk {k}: battle2 sentinel armed for the whole chunk, "
                      "0 rl/search accesses (SF-13)")
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
            # BI-2 (ch3_r4 F11): wall-clock span of this chunk, so the
            # lane-paired-wave claim is auditable from the artifacts
            "started_at": started_at,
            "finished_at": time.time(),
            "returns": returns,
        }
        if isinstance(agent, EnsembleAgent):
            report["ensemble_decisions"] = agent.decisions
            report["ensemble_flips"] = agent.flips
        if adapter is not None:
            report.update(adapter.chunk_summary())
            report["search_dose"] = job["search_dose"]
            if eval_provenance is not None:
                report["evaluator"] = eval_provenance
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
    if "evaluator" in reports[0]:
        final["evaluator"] = reports[0]["evaluator"]
    if "started_at" in reports[0]:
        final["started_at"] = reports[0]["started_at"]
        final["finished_at"] = reports[-1]["finished_at"]
    if "search/decisions" in reports[0]:
        dec = sum(rep["search/decisions"] for rep in reports)
        skips = sum(rep["search/placeholder_skips"] for rep in reports)
        flips = sum(rep["search/flips"] for rep in reports)
        searched = sum(rep["search/searched_decisions"] for rep in reports)
        final["search_dose"] = reports[0]["search_dose"]
        final["search/decisions"] = dec
        final["search/placeholder_skips"] = skips
        final["search/placeholder_skip_rate"] = skips / dec if dec else None
        final["search/flips"] = flips
        final["search/flip_rate"] = flips / max(dec - skips, 1)
        final["search/ms_mean"] = (
            sum(rep["search/ms_mean"] * rep["search/searched_decisions"]
                for rep in reports) / searched if searched else None
        )
        final["search/ms_p99_max_over_chunks"] = max(
            rep["search/ms_p99"] for rep in reports
        )
        final["search/leaves_mean"] = (
            sum(rep["search/leaves_mean"] * rep["search/searched_decisions"]
                for rep in reports) / searched if searched else None
        )
        final["search/leaves_max"] = max(rep["search/leaves_max"] for rep in reports)
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


def search_smoke(prereg: dict, lane: str, battles: int, dose: str) -> None:
    """Live end-to-end smoke of the search path: SearchAgent + adapter +
    battle2 sentinel on `battles` real battles. The R1 spike ran on
    REHYDRATED harvest snapshots; this is the first place the search reads
    a LIVE battle1 — the freeze/rehydrate contract says the surfaces
    match, and this proves it before any verdict arm."""
    agent0, cfg, env = _load_member(prereg, lane)
    torch.set_num_threads(cfg.torch_threads)
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES

    sa = SearchAgent(agent0, DOSES[dose], checkpoint_seed=int(lane.lstrip("s")))
    adapter = _SearchEvalAdapter(sa, env)
    adapter.begin_chunk(0)
    _print_username(env)
    handle = _install_battle2_sentinel(env.unwrapped._env.env)
    try:
        returns, outcomes, faints = _run_eval_episodes(
            adapter, env, battles, seed_start=0
        )
    finally:
        _uninstall_battle2_sentinel(env.unwrapped._env.env, handle)
    summary = adapter.chunk_summary()
    wins = sum(1 for o in outcomes if o == 1)
    print(json.dumps(summary, indent=2))
    print(f"search smoke: {wins}/{battles} wins, dose {dose}, lane {lane}; "
          "battle2 sentinel armed throughout, 0 rl/search accesses")
    env.close()


def selfcheck(prereg: dict) -> None:
    """R0-c: single-member ensemble == member argmax, 1000/1000, per lane."""
    from rl.envs.showdown import OBS_DIM

    rng = random.Random(20260821)
    # iterate ARM lanes, not every checkpoint pin — non-lane pins (the R4
    # clone anchor, 808-d pre-ids) are hashed by preflight but never play
    lanes = sorted({l for a in prereg["arms"].values() for l in a["lanes"]})
    for lane in lanes:
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


def r4_discrimination(prereg: dict) -> None:
    """R4-13 (BI-4): evaluator-discrimination smoke, serverless. On 1000
    synthetic decision points per A1E lane: (a) mean |v_LOO - v_own| >= 0.02
    in value units AND (b) the argmax over a collapsed 6-action x 4-det
    synthetic matrix (per-action value = mean over its dets, the solve
    aggregation shape) differs on >= 5% of points. FAILURE MEANS DO NOT
    LAUNCH (pre-reg R4-13). Values are transcribed into the pre-reg's
    r4_13_discrimination field before launch."""
    from rl.envs.showdown import OBS_DIM

    arm = prereg["arms"]["A1E"]
    lanes = arm["lanes"]
    pool = arm["evaluator"]["pool"]
    agents = {x: _load_member_spaces(prereg, x)[0] for x in dict.fromkeys(pool + lanes)}
    rng = np.random.default_rng(20260823)
    results = {}
    for lane in lanes:
        own = agents[lane]
        peers = [agents[x] for x in pool if x != lane]
        assert len(peers) == 3 and all(p is not own for p in peers)
        diffs, flips = [], 0
        for _ in range(1000):
            batch = rng.standard_normal((24, OBS_DIM)).astype(np.float32)
            t = torch.as_tensor(batch)
            with torch.no_grad():
                v_own = own.critic(t).reshape(-1).numpy()
                v_loo = torch.stack(
                    [p.critic(t).reshape(-1) for p in peers]
                ).mean(dim=0).numpy()
            diffs.append(float(np.mean(np.abs(v_loo - v_own))))
            flips += int(
                np.argmax(v_own.reshape(6, 4).mean(axis=1))
                != np.argmax(v_loo.reshape(6, 4).mean(axis=1))
            )
        mean_abs = float(np.mean(diffs))
        flip_frac = flips / 1000
        ok = mean_abs >= 0.02 and flip_frac >= 0.05
        results[lane] = {
            "mean_abs_diff": round(mean_abs, 4),
            "argmax_differ_frac": round(flip_frac, 3),
        }
        print(f"R4-13 {lane}: mean|v_LOO-v_own| {mean_abs:.4f} (>=0.02), "
              f"argmax differ {flip_frac:.3f} (>=0.05) -> "
              f"{'PASS' if ok else 'FAIL'}")
        assert ok, f"R4-13 FAIL on {lane}: DO NOT LAUNCH"
    print(json.dumps(results))


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
    parser.add_argument("--r4-discrimination", action="store_true",
                        help="R4-13 evaluator-discrimination smoke (serverless)")
    parser.add_argument("--search-smoke", metavar="LANE",
                        help="live search smoke: SearchAgent on N real battles")
    parser.add_argument("--battles", type=int, default=4)
    parser.add_argument("--dose", default="M")
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
    if args.r4_discrimination:
        _preflight(prereg)
        r4_discrimination(prereg)
        return
    if args.search_smoke:
        _preflight(prereg)
        search_smoke(prereg, args.search_smoke, args.battles, args.dose)
        return
    assert args.job, "--job, --list-jobs or --selfcheck required"
    _preflight(prereg)
    run_job(prereg, args.job)


if __name__ == "__main__":
    main()

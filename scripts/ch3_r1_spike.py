"""CH3 R1-0 — the end-to-end spike (ch3_search_design_r2.md §4 R1).

    python scripts/ch3_r1_spike.py --prereg configs/eval/ch3_rung0.yaml

Replays 200 REAL harvested decisions (50 per D26 lane, evenly strided over
the non-placeholder decisions of results/ch3_r1/harvest_<lane>.pkl) through
the COMPLETE Dose-M search — determinize x4, bridge, engine, top-6
retention, ShadowBattle, the one true encoder, the lane's own critic, BR
solve. Freezes the numbers every later rung prices against:

- ms/decision (mean + percentiles) -> R2-8's baseline, the dose/wall model
- leaves/decision realized vs cap  -> F3's baseline
- watchdog constants               -> node caps for S/L proposed from the
                                      realized max (M's 1500 was set in the
                                      design; the spike checks it holds)
- flip rate vs the recorded greedy action (descriptive, not a verdict)

Writes results/ch3_r1/r1_0_spike.json. Offline: no server, no battles.
PUBLIC FILE ONLY: reads harvest_<lane>.pkl, never harvest_priv_* (FG-4).
"""

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.search.agent import SearchAgent
from rl.search.harvest import rehydrate_battle
from rl.search.matrix import DOSES, SearchWatchdogError
from rl.train import make_agent


def _load_agent(spec: dict):
    import gymnasium as gym

    from rl.envs.showdown import OBS_DIM

    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    assert not getattr(cfg, "normalize_obs", False)
    env = gym.Env()
    env.observation_space = gym.spaces.Box(-1.0, 4.0, shape=(OBS_DIM,), dtype=np.float32)
    env.action_space = gym.spaces.Discrete(10)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])
    return agent, cfg


def spike_lane(prereg: dict, lane: str, n: int, harvest_dir: Path) -> list[dict]:
    agent, cfg = _load_agent(prereg["checkpoints"][lane])
    search = SearchAgent(agent, DOSES["M"], checkpoint_seed=cfg.seed)
    with open(harvest_dir / f"harvest_{lane}.pkl", "rb") as f:
        battles = pickle.load(f)
    # every (episode, step) whose decision actually searches (not locked)
    pool = [
        (bi, si)
        for bi, b in enumerate(battles)
        for si, row in enumerate(b["rows"])
        if not row["aliased"]
    ]
    idx = np.linspace(0, len(pool) - 1, num=n, dtype=int)
    out = []
    for k in idx:
        bi, si = pool[k]
        row = battles[bi]["rows"][si]
        battle = rehydrate_battle(row["battle"])
        t0 = time.perf_counter()
        try:
            action, stats = search.act(
                battle, row["obs"], row["mask"], battle_index=bi, decision_index=si
            )
            err = None
        except SearchWatchdogError as exc:  # a trip here is DATA, not a crash
            action, stats, err = -1, {}, str(exc)
        ms = (time.perf_counter() - t0) * 1e3
        out.append({
            "lane": lane, "episode": bi, "step": si, "turn": row["turn"],
            "ms": ms,
            "leaves": stats.get("search/leaves", 0),
            "rows": stats.get("search/rows", 0),
            "cols": stats.get("search/cols", 0),
            "chosen": int(action),
            "greedy_recorded": int(row["action"]),
            "placeholder_skip": int(stats.get("search/placeholder_skip", 0)),
            "other_move_mass": stats.get("oppact/other_move_mass"),
            "opp_locked": stats.get("search/opp_locked", 0),
            "force_switch": stats.get("search/force_switch", 0),
            "watchdog_error": err,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--harvest", default="results/ch3_r1")
    ap.add_argument("--per-lane", type=int, default=50)
    args = ap.parse_args()
    prereg = yaml.safe_load(Path(args.prereg).read_text())
    import os

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d D26 objects)"
    torch.set_num_threads(1)  # single-threaded search (design §3 D-clauses)

    rows = []
    for lane in prereg["checkpoints"]:
        print(f"spiking {lane} ({args.per_lane} decisions, Dose M)...")
        rows.extend(spike_lane(prereg, lane, args.per_lane, Path(args.harvest)))

    searched = [r for r in rows if not r["placeholder_skip"] and not r["watchdog_error"]]
    ms = np.array([r["ms"] for r in searched])
    leaves = np.array([r["leaves"] for r in searched])
    flips = [r for r in searched if r["chosen"] != r["greedy_recorded"]]
    summary = {
        "n_decisions": len(rows),
        "n_searched": len(searched),
        "n_placeholder_skips": int(sum(r["placeholder_skip"] for r in rows)),
        "n_watchdog_errors": int(sum(bool(r["watchdog_error"]) for r in rows)),
        "dose": "M",
        "torch_threads": 1,
        "ms_per_decision": {
            "mean": float(ms.mean()), "p50": float(np.percentile(ms, 50)),
            "p90": float(np.percentile(ms, 90)), "p99": float(np.percentile(ms, 99)),
            "max": float(ms.max()),
        },
        "leaves_per_decision": {
            "mean": float(leaves.mean()), "p50": float(np.percentile(leaves, 50)),
            "max": int(leaves.max()), "cap": DOSES["M"].leaf_cap,
            "realized_vs_cap": float(leaves.mean() / DOSES["M"].leaf_cap),
        },
        "flip_rate_vs_recorded_greedy": len(flips) / max(len(searched), 1),
        "opp_locked_frac": float(np.mean([r["opp_locked"] for r in searched])),
        "force_switch_frac": float(np.mean([r["force_switch"] for r in searched])),
        "implied_s_per_battle_at_27.4_dec": float(ms.mean() / 1e3 * 27.4),
        "implied_h_per_3000_battles_1wide": float(ms.mean() / 1e3 * 27.4 * 3000 / 3600),
        "proposed_node_caps": {
            "M": DOSES["M"].node_cap,
            "M_realized_max": int(leaves.max()),
            "S_proposal": int(np.ceil(leaves.max() / DOSES["M"].n_det * 1.4)),
            "L_proposal": int(np.ceil(leaves.max() * 4 * 1.4)),
        },
    }
    out = Path(args.harvest) / "r1_0_spike.json"
    out.write_text(json.dumps({"summary": summary, "decisions": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

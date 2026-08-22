"""CH3 R1 — the harvest recorder (ch3_search_design_r2.md §4 R1; no verdict).

    python scripts/ch3_harvest.py --prereg configs/eval/ch3_rung0.yaml --battles-per-lane 125

Plays battles-per-lane per D26 lane (default 125 x 4 = 500) vs the config's
SimpleHeuristics eval anchor and records BOTH seats:

- <out>/harvest_<lane>.pkl — SEAT-1 PUBLIC ONLY: per decision the frozen
  battle1 snapshot (rl/search/harvest.freeze_battle — rehydrates offline
  through determinize/bridge/embed), obs, mask, our action, placeholder
  flags, waits absorbed by the step; plus the post-battle final snapshot and
  outcome. This file is what the R1-0 spike and the search-side FG checks
  consume.
- <out>/harvest_priv_<lane>.pkl — SEAT-2 PRIVILEGED, OFFLINE-ONLY (FG-4):
  per battle the opponent's TRUE team (species/level/moves, from battle2)
  and per decision the opponent's actually-chosen order identity
  ([kind, id, flags] in the D25 seam's convention, from a recording wrapper
  around SimpleHeuristicsPlayer). Ground truth for FG-2 (joint action),
  FG-7 (sampler support) and oppact/sh_accuracy. NOTHING under rl/search/
  may read this file — the FG-4 static gate greps for it.

Tripwire, asserted on EVERY recorded decision: embed_battle(rehydrate(
freeze(battle1))) must be bit-identical to the live encoder output — a
snapshot that cannot reproduce its own obs would silently corrupt every
downstream FG number.
"""

import argparse
import os
import pickle
import re
from pathlib import Path

import numpy as np
import torch
import yaml

from poke_env.data import GenData
from poke_env.player import SimpleHeuristicsPlayer

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.envs.make import make_env, selfplay_env_kwargs
from rl.envs.normalize import frozen_obs_env
from rl.envs.showdown import (
    _move_slots_aliased,
    _order_identity,
    embed_battle,
    mask_desync_total,
)
from rl.search.harvest import freeze_battle, rehydrate_battle
from rl.train import make_agent

# Harvest resets must not collide with the locked eval battles or the R0
# audit stream (EVAL_SEED_OFFSET + eval_episodes + ep); disjoint by offset.
HARVEST_SEED_OFFSET = 50_000


class RecordingHeuristics(SimpleHeuristicsPlayer):
    """The eval anchor, with its per-decision order recorded (seat 2).

    SingleAgentWrapper calls choose_move synchronously on battle2 in its
    pre-resolution state; the FIRST call after clear() is the simultaneous
    decision (later calls inside a wait pump are forced replacements —
    ShowdownEnv.step's own take_choice convention)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pending = None

    def clear(self) -> None:
        self._pending = None

    def take(self) -> dict | None:
        return self._pending

    def choose_move(self, battle):
        order = super().choose_move(battle)
        if self._pending is None:
            kind, ident, flags = _order_identity(order, battle)
            self._pending = {
                "kind": int(kind),
                "id": int(ident),
                "flags": int(flags),
                "order": str(getattr(order, "message", order)),
                "turn": int(battle.turn),
            }
        return order


def _true_team(battle2) -> dict:
    """SEAT-2 PRIVILEGED: the opponent's own full team, from its battle."""
    return {
        mon.species: {
            "level": int(mon.level),
            "moves": sorted(mon.moves.keys()),
        }
        for mon in battle2.team.values()
    }


def _preflight(prereg: dict) -> None:
    import hashlib

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d D26 objects)"
    for lane, spec in prereg["checkpoints"].items():
        h = hashlib.sha256()
        with open(spec["path"], "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        assert h.hexdigest() == spec["sha256"], f"sha256 mismatch for {lane}"
    cfg_js = Path("showdown/config/config.js").read_text()
    m = re.search(r"^\s*simulator:\s*(\d+)", cfg_js, re.M)
    assert m and int(m.group(1)) >= 4, "simulator: 4 not set in showdown config"
    print("preflight: sha256 x4 OK; encoder vars OK; simulator>=4 OK")


def harvest_lane(prereg: dict, lane: str, battles: int, out_dir: Path) -> dict:
    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    assert not getattr(cfg, "normalize_obs", False), (
        "harvest assumes raw observations (id suffix must survive)"
    )
    torch.set_num_threads(cfg.torch_threads)

    env_kwargs = selfplay_env_kwargs(cfg, "eval_opponent")
    assert env_kwargs.get("opponent") == "heuristics", (
        f"eval anchor is {env_kwargs.get('opponent')!r}, expected 'heuristics'"
    )
    battle_format = env_kwargs.get("battle_format", "gen1randombattle")
    opp = RecordingHeuristics(battle_format=battle_format, start_listening=False)
    env = make_env(cfg.env_id, cfg.seed, env_kwargs=env_kwargs | {"opponent": opp})
    env = frozen_obs_env(env, cfg, ckpt)
    agent = make_agent(cfg, env)
    agent.load_state_dict(ckpt["agent"])

    poke = env.unwrapped._env.env
    type_chart = GenData.from_format(battle_format).type_chart

    public, priv = [], []
    for ep in range(battles):
        obs, info = env.reset(seed=HARVEST_SEED_OFFSET + ep)
        mask = info.get("action_mask")
        rows, choices = [], []
        done, steps = False, 0
        while not done and steps < 10_000:
            b = poke.battle1
            snap = freeze_battle(b)
            aliased = _move_slots_aliased(b)
            re_obs = embed_battle(rehydrate_battle(snap), type_chart)
            assert np.array_equal(re_obs, np.asarray(obs, dtype=np.float32)), (
                f"freeze/rehydrate obs mismatch, {lane} ep {ep} turn {snap['turn']}"
            )
            action = agent.act(obs, mask, deterministic=True)
            waits_before = env.unwrapped.waits_absorbed
            opp.clear()
            next_obs, reward, term, trunc, info = env.step(action)
            rows.append({
                "turn": snap["turn"],
                "aliased": aliased,
                "obs": np.asarray(obs, dtype=np.float32),
                "mask": np.asarray(mask, dtype=bool),
                "action": int(action),
                "battle": snap,
                "waits_after": env.unwrapped.waits_absorbed - waits_before,
                "reward": float(reward),
            })
            choices.append(opp.take())
            obs, mask = next_obs, info.get("action_mask")
            steps += 1
            done = term or trunc
        battle2 = poke.battle2
        public.append({
            "lane": lane,
            "episode": ep,
            "rows": rows,
            "final_battle": freeze_battle(poke.battle1),
            "outcome": int(info.get("outcome", 0)),
        })
        priv.append({
            "lane": lane,
            "episode": ep,
            "true_team": _true_team(battle2),
            "choices": choices,
        })
    env.close()

    n_dec = sum(len(b["rows"]) for b in public)
    with open(out_dir / f"harvest_{lane}.pkl", "wb") as f:
        pickle.dump(public, f, protocol=pickle.HIGHEST_PROTOCOL)
    with open(out_dir / f"harvest_priv_{lane}.pkl", "wb") as f:
        pickle.dump(priv, f, protocol=pickle.HIGHEST_PROTOCOL)
    stats = {
        "lane": lane,
        "battles": battles,
        "decisions": n_dec,
        "win_rate": float(np.mean([b["outcome"] > 0 for b in public])),
        "mask_desyncs": mask_desync_total(),
    }
    print(stats)
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--battles-per-lane", type=int, default=125)
    ap.add_argument("--out", default="results/ch3_r1")
    args = ap.parse_args()
    prereg = yaml.safe_load(Path(args.prereg).read_text())
    _preflight(prereg)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_stats = []
    for lane in prereg["checkpoints"]:
        print(f"harvesting {lane} ({args.battles_per_lane} battles)...")
        all_stats.append(harvest_lane(prereg, lane, args.battles_per_lane, out_dir))
    total = sum(s["decisions"] for s in all_stats)
    print(f"harvest complete: {total} decisions across "
          f"{sum(s['battles'] for s in all_stats)} battles")


if __name__ == "__main__":
    main()

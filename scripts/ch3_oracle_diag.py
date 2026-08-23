"""R3's CONTAINED oracle-team diagnostic — a SEPARATE BINARY on purpose.

    python scripts/ch3_oracle_diag.py --prereg configs/eval/ch3_rung3.yaml --battles 1000
    python scripts/ch3_oracle_diag.py --prereg configs/eval/ch3_rung3.yaml --battles 20 --smoke

Design §4 R3: "the CONTAINED oracle-team diagnostic (true team substituted;
separate binary, FG-4 disarmed with a loud banner, BARRED from
README/STATUS/headlines — D18-privileged discipline)."

What it measures: search@M on the s65 lane (the falsifier's pre-stated
median lane) with the determinization replaced by the TRUE opponent team,
read live off battle2 — BY THIS SCRIPT, never by rl/search (the leak grep
stays one directory; the det is injected through SearchAgent's det_fn seam
and passes the bridge's FG-4 assert only under fg4_disarm()). The gap
between oracle and RSD win rates bounds what determinization error costs —
"determinization error vs everything else" in the §7 instrument table.

DVs stay the EXPECTED_DVS max model even under oracle (the dial substitutes
the TEAM — species/moves/levels; stat-level oracle is a different, unbuilt
instrument and is named so the gap is not over-read).

Output: results/ch3_r3_oracle/ — a directory whose README.txt banner and
every JSON carry "BARRED" so nothing here migrates to a headline.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import _sha256, _SearchEvalAdapter  # noqa: E402
from eval_checkpoint import _load_showdown_agent  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.evaluation import _run_eval_episodes, eval_metrics  # noqa: E402
from rl.envs.make import make_eval_env  # noqa: E402
from rl.envs.normalize import frozen_obs_env  # noqa: E402
from rl.envs.showdown import mask_desync_total  # noqa: E402
from rl.search.agent import SearchAgent  # noqa: E402
from rl.search.bridge import fg4_disarm  # noqa: E402
from rl.search.determinize import EXPECTED_DVS  # noqa: E402
from rl.search.matrix import DOSES  # noqa: E402

BARRED = ("DIAGNOSTIC-ONLY (FG-4 disarmed): BARRED from README/STATUS/"
          "headlines per design §4 R3 / D18-privileged discipline")


def _oracle_det_fn(poke):
    """det_fn closure reading the TRUE opponent team off battle2 — the read
    lives HERE, in the diagnostic binary, not in rl/search."""

    def det_fn(battle, rng):
        b2 = poke.battle2
        assert b2 is not None, "oracle diagnostic needs battle2 (local env)"
        opponents = {}
        b1_opp = {m.species: m for m in battle.opponent_team.values()}
        for mon in b2.team.values():
            opponents[mon.species] = {
                "moves": list(mon.moves.keys()),
                "level": mon.level,
                "base_stats": dict(mon.base_stats) | {
                    "types": [t.name.lower() for t in mon.types if t is not None]
                },
                "live": b1_opp.get(mon.species),
                "dvs": dict(EXPECTED_DVS),
                "provenance": "oracle",
            }
        return {"opponents": opponents}

    return det_fn


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", default="configs/eval/ch3_rung3.yaml")
    parser.add_argument("--battles", type=int, default=1000)
    parser.add_argument("--lane", default="s65")
    parser.add_argument("--chunks", type=int, default=10)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required"

    fg4_disarm()

    prereg = yaml.safe_load(open(args.prereg))
    spec = prereg["checkpoints"][args.lane]
    assert _sha256(spec["path"]) == spec["sha256"], "checkpoint sha mismatch"
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)
    env = frozen_obs_env(make_eval_env(cfg), cfg, ckpt)
    agent0 = _load_showdown_agent(ckpt, cfg)
    poke = env.unwrapped._env.env

    sa = SearchAgent(
        agent0, DOSES["M"], checkpoint_seed=int(args.lane.lstrip("s")),
        det_fn=_oracle_det_fn(poke),
    )
    adapter = _SearchEvalAdapter(sa, env)

    out_dir = Path("results/ch3_r3_oracle")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "README.txt").write_text(BARRED + "\n")

    chunks = 1 if args.smoke else args.chunks
    chunk_size = args.battles // chunks
    prefix = "oracle_smoke" if args.smoke else "oracle"
    desync_before = mask_desync_total()
    for k in range(chunks):
        chunk_path = out_dir / f"{prefix}.chunk{k:02d}.json"
        if chunk_path.exists():
            print(f"{chunk_path.name}: exists, skipping")
            continue
        seed_start = cfg.eval_episodes + k * chunk_size
        adapter.begin_chunk(seed_start)
        returns, outcomes, faints = _run_eval_episodes(
            adapter, env, chunk_size, seed_start=seed_start
        )
        metrics = eval_metrics(returns, outcomes, faints, win_rate=True)
        wfr = sum(1 for r in returns if r > 0) / len(returns)
        assert metrics["eval/win_rate"] == wfr, "win_rate != wins_from_returns"
        desync_now = mask_desync_total()
        report = {
            "BARRED": BARRED,
            "lane": args.lane,
            "chunk": k,
            "episodes": chunk_size,
            "seed_start": seed_start,
            **metrics,
            "wins_from_returns": wfr,
            "mask_desyncs_delta": desync_now - desync_before,
            **adapter.chunk_summary(),
        }
        desync_before = desync_now
        chunk_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{chunk_path.name}: win_rate {report['eval/win_rate']:.4f}")
    env.close()


if __name__ == "__main__":
    main()

"""Foul Play (gen-4 engine build) vs OUR gen-4 checkpoint — the eval-bot path,
end to end, on a LOCAL server.

The gen-4 twin of scripts/foulplay_vs_sh.py's checkpoint seat: a LISTENING
`Gen4PoolPlayer` (rl/envs/gen4/env.py) drives a checkpoint through the gen-4
encoder + tracker on its OWN battle object, accepts Foul Play's challenges,
and records the tape; Foul Play runs from the `foul-play-gen4` env as a
subprocess in `challenge_user` mode (scripts/gen4_fp_smoke.py's launch). The
seat SAMPLES (PoolPlayer's form), as the historical --seat numbers did; a
deterministic arm is a one-line change when a pre-reg asks for it.

    python scripts/gen4_fp_h2h.py --checkpoint runs/gen4_smoke_heur_s1/checkpoint.pt --battles 20 --port 8001

Nothing here is a protocol number until a gen-4 pre-reg names the arm, the
budget, n and the seat form. Every FP@<ms> quote carries the two standing
disclosures (weakly powered equivalence test; the point estimate flatters us)
and its budget.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from poke_env.ps_client import AccountConfiguration  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.envs.gen4.env import GEN4_FORMAT, Gen4PoolPlayer, fake_spaces_gen4  # noqa: E402
from rl.envs.gen4.spec import OBS_DIM_GEN4  # noqa: E402
from rl.envs.gen4.tape import protocol_stats  # noqa: E402
from rl.envs.showdown import mask_desync_total  # noqa: E402
from rl.selfplay.pool import SnapshotPool  # noqa: E402
from rl.train import make_agent  # noqa: E402
from scripts.gen4_fp_smoke import _GREPS, FP_DIR, FP_PY, _server  # noqa: E402
from scripts.gen4_smoke import TapeMixin, _WarningTally  # noqa: E402


class TapeGen4PoolPlayer(TapeMixin, Gen4PoolPlayer):
    pass


def _seat(ckpt_path: str, username: str, port: int, tape: list, stats: Counter, seed: int) -> TapeGen4PoolPlayer:
    ckpt = load_checkpoint(ckpt_path)
    cfg = Config(**ckpt["config"])
    assert cfg.env_id.startswith("ShowdownGen4"), f"not a gen-4 checkpoint: env_id={cfg.env_id!r}"
    torch.set_num_threads(1)
    obs_space, act_space = fake_spaces_gen4()
    agent = make_agent(cfg, SimpleNamespace(observation_space=obs_space, action_space=act_space))
    agent.load_state_dict(ckpt["agent"])
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)
    seat = TapeGen4PoolPlayer(
        pool,
        battle_format=GEN4_FORMAT,
        account_configuration=AccountConfiguration(username, None),
        server_configuration=_server(port),
        max_concurrent_battles=1,
        start_timer_on_battle_start=True,  # every seat that plays foul-play sends /timer on
        log_level=logging.WARNING,
        tape=tape,
        stats=stats,
    )
    seat.seed_rng(seed)
    return seat


async def _run(args) -> dict:
    tape: list = []
    stats: Counter = Counter()
    pid = os.getpid() % 10000
    seat_name = f"g4h2h{args.tag[:3]}s{pid}"[:18]
    fp_name = f"g4h2h{args.tag[:3]}f{pid}"[:18]
    seat = _seat(args.checkpoint, seat_name, args.port, tape, stats, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fp_log = out / f"{args.tag}.foulplay.log"
    cmd = [
        str(FP_PY), "run.py",
        "--websocket-uri", f"ws://localhost:{args.port}/showdown/websocket",
        "--ps-username", fp_name,
        "--bot-mode", "challenge_user",
        "--user-to-challenge", seat_name,
        "--pokemon-format", GEN4_FORMAT,
        "--search-time-ms", str(args.search_time_ms),
        "--search-parallelism", str(args.search_parallelism),
        "--run-count", str(args.battles),
        "--log-level", args.fp_log_level,
    ]
    t0 = time.time()
    accept = asyncio.create_task(seat.accept_challenges(fp_name, args.battles))
    await asyncio.sleep(3.0)
    timed_out = False
    with fp_log.open("w") as fh:
        fp = subprocess.Popen(cmd, cwd=str(FP_DIR), stdout=fh, stderr=subprocess.STDOUT)
        try:
            await asyncio.wait_for(accept, timeout=args.timeout)
        except asyncio.TimeoutError:
            timed_out = True  # the seat stops accepting; the tape and summary below still land
        finally:
            try:
                fp.wait(timeout=60)
            except subprocess.TimeoutExpired:
                fp.kill()
                fp.wait()  # reap, so fp_exit_code is the signal, not None
    wall = time.time() - t0
    tape_path = out / f"{args.tag}.jsonl"
    with tape_path.open("w") as fh:
        for ev in tape:
            fh.write(json.dumps(ev) + "\n")
    text = fp_log.read_text(errors="replace")
    return {
        "checkpoint": args.checkpoint,
        "obs_dim": OBS_DIM_GEN4,
        "seat_form": "sampled (PoolPlayer)",
        "search_time_ms": args.search_time_ms,
        "battles": args.battles,
        "fp_exit_code": fp.returncode,
        "timed_out": timed_out,
        "wall_s": round(wall, 1),
        "s_per_battle": round(wall / max(args.battles, 1), 2),
        "seat_record_W_L_T": [seat.n_won_battles, seat.n_lost_battles, seat.n_tied_battles],
        "mask_desyncs": mask_desync_total(),
        "fp_log": str(fp_log),
        "fp_log_greps": {k: len(p.findall(text)) for k, p in _GREPS.items()},
        "decision_facts_seat": dict(stats.most_common()),
        "tape": str(tape_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--battles", type=int, default=20)
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--search-time-ms", type=int, default=20)
    ap.add_argument("--search-parallelism", type=int, default=1)
    ap.add_argument("--fp-log-level", default="INFO")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=7200.0)
    ap.add_argument("--tag", default="fp_h2h")
    ap.add_argument("--out", default="data/gen4_fp")
    args = ap.parse_args()
    tally = _WarningTally()
    logging.getLogger("poke-env").addHandler(tally)
    logging.getLogger().addHandler(tally)
    logging.getLogger().setLevel(logging.WARNING)
    summary = asyncio.run(_run(args))
    summary["poke_env_warnings"] = dict(tally.counts.most_common())
    summary["protocol"] = protocol_stats(summary["tape"])
    with open(Path(args.out) / f"{args.tag}.summary.json", "w") as fh:
        json.dump(summary, fh, indent=1, default=str)
    p = summary["protocol"]
    print(f"FP@{args.search_time_ms} vs checkpoint: battles={args.battles} fp_exit={summary['fp_exit_code']} "
          f"wall={summary['wall_s']}s s/battle={summary['s_per_battle']} seat W-L-T={summary['seat_record_W_L_T']} "
          f"outcomes={p['outcomes']} turns={p['turns']} mask_desyncs={summary['mask_desyncs']}")
    print("fp log greps:", summary["fp_log_greps"])
    print("seat errors:", p["errors"], "| poke-env warnings:", summary["poke_env_warnings"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

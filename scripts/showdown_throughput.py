"""Phase 5 pre-registered throughput measurements (a) and (b) — PLAN.md
hardware note. Needs the local Showdown server running:
cd showdown && node pokemon-showdown start --no-security

(a) Per-turn latency breakdown at one battle in flight: encode
    (embed_battle + mask) vs inference (the seam) vs the env gap between
    returning an order and the next decision request. The gap decomposes
    into poke-env message parsing (both players' ps_client._handle_message
    wrapped with timers), websocket RTT (measured by ping), and a residual
    that is server compute + event-loop scheduling.

    python scripts/showdown_throughput.py a --battles 20

(b) Aggregate decisions/s vs battles-in-flight in one process — the
    asyncio/GIL ceiling. All battles share poke-env's singleton POKE_LOOP,
    so this is the native collection path's scaling curve, batch-1
    inference blocking that loop included.

    python scripts/showdown_throughput.py b --concurrency 1 2 4 8 16 32 64

The policy is the real Phase 2 PPO discrete stack at CartPole scale
(mlp [64, 64] actor + critic, masked logits, sampled action) on the
placeholder 10-dim encoder — a lower bound on capstone-encoder cost, which
is the point: (a) shows where time goes BEFORE the encoder grows, and
measurement (d) later re-prices the forward at the real encoder.
"""

import argparse
import asyncio
import statistics
import time

import numpy as np
import torch
from torch.distributions import Categorical

from poke_env.concurrency import POKE_LOOP, handle_threaded_coroutines
from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.player import RandomPlayer

from rl.collect import InferenceSeam, SeamPlayer
from rl.envs.showdown import OBS_DIM, embed_battle
from rl.networks.mlp import mlp

FORMAT = "gen1randombattle"
N_ACTIONS = 10


def make_policy(seed: int = 0):
    torch.manual_seed(seed)
    actor = mlp(OBS_DIM, [64, 64], N_ACTIONS, activation=torch.nn.Tanh)
    critic = mlp(OBS_DIM, [64, 64], 1, activation=torch.nn.Tanh)
    from rl.common.masking import masked_logits

    @torch.no_grad()
    def policy(obs, mask):
        obs_t = torch.from_numpy(obs)
        logits = masked_logits(actor(obs_t), torch.from_numpy(mask))
        critic(obs_t)  # collection computes values too; charge for it
        return Categorical(logits=logits).sample().numpy()

    return policy


class TimedSeamPlayer(SeamPlayer):
    """(a) only: timestamps around each decision, keyed by battle so gaps
    never span the challenge setup between consecutive battles."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []  # (battle_tag, t_enter, encode_s, t_return)

    async def choose_move(self, battle):
        t_enter = time.perf_counter()
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        encode_s = time.perf_counter() - t_enter
        action = await self._seam.request(obs, mask)
        order = SinglesEnv.action_to_order(np.int64(action), battle)
        self.events.append((battle.battle_tag, t_enter, encode_s, time.perf_counter()))
        return order


def _wrap_parse_timers() -> list:
    """Time poke-env's synchronous protocol parsing (battle-state updates
    from |messages and the request JSON), class-level so both seats count.
    Timing the async _handle_message instead would span awaited suspensions
    — it contains the whole decision path — and overcount wildly (measured:
    5.1s of 'parsing' in a 0.94s run)."""
    from poke_env.battle.battle import Battle

    bucket = [0.0]
    for name in ("parse_message", "parse_request"):
        orig = getattr(Battle, name)

        def timed(self, *args, _orig=orig):
            t0 = time.perf_counter()
            out = _orig(self, *args)
            bucket[0] += time.perf_counter() - t0
            return out

        setattr(Battle, name, timed)
    return bucket


async def _ping_rtt(websocket, n: int = 50) -> float:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        waiter = await websocket.ping()
        await waiter
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


def _stats(xs, unit=1e3):
    xs = sorted(xs)
    return (
        f"mean {statistics.mean(xs) * unit:7.3f}  p50 {xs[len(xs) // 2] * unit:7.3f}  "
        f"p90 {xs[int(len(xs) * 0.9)] * unit:7.3f} ms  (n={len(xs)})"
    )


def measure_a(battles: int):
    seam = InferenceSeam(make_policy())
    player = TimedSeamPlayer(seam, battle_format=FORMAT)
    opponent = RandomPlayer(battle_format=FORMAT)
    parse = _wrap_parse_timers()

    t0 = time.perf_counter()
    asyncio.run(player.battle_against(opponent, n_battles=battles))
    wall = time.perf_counter() - t0

    rtt = asyncio.run(
        handle_threaded_coroutines(_ping_rtt(player.ps_client.websocket), POKE_LOOP)
    )

    encode = [e[2] for e in player.events]
    gaps = [
        b[1] - a[3]
        for a, b in zip(player.events, player.events[1:])
        if a[0] == b[0]  # same battle only
    ]
    n = seam.requests
    print(f"{battles} battles, {n} decisions, wall {wall:.2f}s")
    print(f"encode (embed_battle + mask):  {_stats(encode)}")
    print(f"inference (seam, batch-1):     mean {seam.inference_seconds / n * 1e3:7.3f} ms")
    print(f"env gap (order -> next req):   {_stats(gaps)}")
    print(f"  of which, per decision:")
    print(f"    parse (both seats) {parse[0] / n * 1e3:7.3f} ms")
    print(f"    ws ping RTT        {rtt * 1e3:7.3f} ms (median of 50)")
    print(f"    residual = gap - parse - RTT (server compute + loop scheduling)")


def measure_b(concurrency: list[int], battles_per_point: int | None):
    print("in-flight  battles  wall_s  decisions/s  battles/s  inference_share")
    for n in concurrency:
        n_battles = battles_per_point or max(8, 4 * n)
        seam = InferenceSeam(make_policy())
        player = SeamPlayer(seam, battle_format=FORMAT, max_concurrent_battles=n)
        opponent = RandomPlayer(battle_format=FORMAT, max_concurrent_battles=n)
        t0 = time.perf_counter()
        asyncio.run(player.battle_against(opponent, n_battles=n_battles))
        wall = time.perf_counter() - t0
        print(
            f"{n:9d}  {n_battles:7d}  {wall:6.2f}  {seam.requests / wall:11.1f}  "
            f"{n_battles / wall:9.2f}  {seam.inference_seconds / wall:15.3f}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurement", choices=["a", "b"])
    parser.add_argument("--battles", type=int, default=20, help="(a) battle count")
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32, 64]
    )
    parser.add_argument(
        "--battles-per-point", type=int, default=None,
        help="(b) battles per concurrency point; default max(8, 4n)",
    )
    args = parser.parse_args()
    # The repo's tiny-net lesson, third confirmation pending: 1 thread.
    torch.set_num_threads(1)
    if args.measurement == "a":
        measure_a(args.battles)
    else:
        measure_b(args.concurrency, args.battles_per_point)

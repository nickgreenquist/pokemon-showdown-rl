"""Phase 5 pre-registered throughput measurements (a) and (b) — SESSION_LOGS_PREDECESSOR.md
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

(c) Multi-process scaling: W spawned workers, each a (b)-style loop at a
    fixed in-flight count, barrier-synced so the battling spans overlap;
    aggregate decisions/s = total decisions / slowest worker's wall.
    --servers shared points every worker at :8000 (start it yourself);
    --servers per-worker boots one fresh server per worker on 8100+i and
    tears them down. Account names are pid-based — poke-env's default is a
    per-process class-name counter, which collides across workers on a
    shared server.

    python scripts/showdown_throughput.py c --workers 1 2 4 8 --servers shared
    python scripts/showdown_throughput.py c --workers 1 2 4 8 --servers per-worker

(d) Forward-pass share at the real encoder, batch-1 vs batched: an offline
    microbenchmark (no server needed) of the policy forward at batch sizes
    1..128 — per-sample cost and the implied ceiling on what micro-batching
    the seam could buy. The live in-situ shares come from rerunning (a) and
    (b), which price the current encoder automatically.

    python scripts/showdown_throughput.py d

The policy defaults to the historical tiny stack (mlp [64, 64] actor +
critic, masked logits, sampled action) so old shape-comparisons stay valid,
on whatever encoder rl/envs/showdown.py currently ships — the 10-dim
placeholder when (a)-(c) first ran (2026-07-29), the real Gen 1 encoder
since 2026-07-30. `--net` swaps in production-scale stacks (THROUGHPUT_SPEC
E4(b): absolute claims must never be made at [64,64] — the two prior
misreads): `mlp512` = [512, 512] (the spec's patch target), `entity` = the
Rung 2 entity_deepsets actor+critic at the credited trunk_kwargs (needs
both encoder env vars — refuses to run below OBS_DIM 828). Every output
header carries the net; quote nothing without it.

SECOND DISCLOSURE, EQUALLY BINDING (added 2026-08-28; the [64,64] caveat
above is only half of what CLAUDE.md records about this script). **Every
number here is COLLECTION-ONLY — server-side decisions/s.** It measures the
env/inference seam and nothing else: no PPO update, no eval, no checkpoint
I/O. So a speedup measured here OVERSTATES the full-loop gain by roughly 7x.
`simulator: 4`'s "+81% collection throughput" is a collection number in
exactly this sense. Any quote from this script must name BOTH the network
width and the fact that it is collection-only; the full-loop counterpart is
`time/steps_per_sec` from a real run.
"""

import argparse
import asyncio
import multiprocessing as mp
import os
import socket
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch.distributions import Categorical

from poke_env.concurrency import POKE_LOOP, handle_threaded_coroutines
from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.player import RandomPlayer
from poke_env.ps_client import AccountConfiguration, ServerConfiguration

from rl.collect import InferenceSeam, SeamPlayer
from rl.envs.showdown import OBS_DIM, embed_battle
from rl.networks.mlp import mlp

FORMAT = "gen1randombattle"
N_ACTIONS = 10
SHOWDOWN_DIR = Path(__file__).resolve().parents[1] / "showdown"


RUNG2_TRUNK_KWARGS = dict(  # the credited Rung 2/50M production trunk
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256],
    value_sizes=[384, 384],
)


def make_policy(seed: int = 0, net: str = "tiny"):
    torch.manual_seed(seed)
    if net == "entity":
        if OBS_DIM != 828:
            raise SystemExit(
                f"--net entity needs the production encoder (OBS_DIM 828, got "
                f"{OBS_DIM}): set POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1"
            )
        from rl.networks.entity_deepsets import EntityDeepSetsNet

        actor = EntityDeepSetsNet(OBS_DIM, N_ACTIONS, **RUNG2_TRUNK_KWARGS)
        critic = EntityDeepSetsNet(OBS_DIM, 1, **RUNG2_TRUNK_KWARGS)
    else:
        width = {"tiny": [64, 64], "mlp512": [512, 512]}[net]
        actor = mlp(OBS_DIM, width, N_ACTIONS, activation=torch.nn.Tanh)
        critic = mlp(OBS_DIM, width, 1, activation=torch.nn.Tanh)
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


def measure_a(battles: int, net: str = "tiny"):
    seam = InferenceSeam(make_policy(net=net))
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
    print(f"{battles} battles, {n} decisions, wall {wall:.2f}s  [net={net}]")
    print(f"encode (embed_battle + mask):  {_stats(encode)}")
    print(f"inference (seam, batch-1):     mean {seam.inference_seconds / n * 1e3:7.3f} ms")
    print(f"env gap (order -> next req):   {_stats(gaps)}")
    print(f"  of which, per decision:")
    print(f"    parse (both seats) {parse[0] / n * 1e3:7.3f} ms")
    print(f"    ws ping RTT        {rtt * 1e3:7.3f} ms (median of 50)")
    print(f"    residual = gap - parse - RTT (server compute + loop scheduling)")


def measure_b(concurrency: list[int], battles_per_point: int | None, net: str = "tiny"):
    print(f"[net={net}]")
    print("in-flight  battles  wall_s  decisions/s  battles/s  inference_share")
    for n in concurrency:
        n_battles = battles_per_point or max(8, 4 * n)
        seam = InferenceSeam(make_policy(net=net))
        player = SeamPlayer(seam, battle_format=FORMAT, max_concurrent_battles=n)
        opponent = RandomPlayer(battle_format=FORMAT, max_concurrent_battles=n)
        t0 = time.perf_counter()
        asyncio.run(player.battle_against(opponent, n_battles=n_battles))
        wall = time.perf_counter() - t0
        print(
            f"{n:9d}  {n_battles:7d}  {wall:6.2f}  {seam.requests / wall:11.1f}  "
            f"{n_battles / wall:9.2f}  {seam.inference_seconds / wall:15.3f}"
        )


def _server_configuration(port: int) -> ServerConfiguration:
    return ServerConfiguration(
        f"ws://localhost:{port}/showdown/websocket",
        "https://play.pokemonshowdown.com/action.php?",
    )


def _port_up(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
        return True
    except OSError:
        return False


def _worker_c(port, n_battles, in_flight, barrier, out_q, net):
    torch.set_num_threads(1)
    pid = os.getpid()
    seam = InferenceSeam(make_policy(net=net))
    cfg = _server_configuration(port)
    player = SeamPlayer(
        seam,
        battle_format=FORMAT,
        max_concurrent_battles=in_flight,
        server_configuration=cfg,
        account_configuration=AccountConfiguration(f"seam{pid}", None),
    )
    opponent = RandomPlayer(
        battle_format=FORMAT,
        max_concurrent_battles=in_flight,
        server_configuration=cfg,
        account_configuration=AccountConfiguration(f"rand{pid}", None),
    )
    barrier.wait()  # overlap the battling spans, not the setup skew
    t0 = time.perf_counter()
    asyncio.run(player.battle_against(opponent, n_battles=n_battles))
    out_q.put((seam.requests, time.perf_counter() - t0, seam.inference_seconds))


def _start_servers(ports: list[int]) -> list[subprocess.Popen]:
    procs = [
        subprocess.Popen(
            ["node", "pokemon-showdown", str(port), "--no-security"],
            cwd=SHOWDOWN_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for port in ports
    ]
    deadline = time.time() + 90
    for port in ports:
        while not _port_up(port):
            if time.time() > deadline:
                raise RuntimeError(f"server on :{port} not up after 90s")
            time.sleep(0.5)
    return procs


def measure_c(workers: list[int], battles_per_worker: int, in_flight: int, servers: str, net: str = "tiny"):
    print(f"in-flight {in_flight}/worker, {battles_per_worker} battles/worker, servers={servers}  [net={net}]")
    print("workers  wall_s(max)  decisions/s  battles/s  inference_share(mean)")
    ctx = mp.get_context("spawn")
    for w in workers:
        if servers == "per-worker":
            ports = [8100 + i for i in range(w)]
            server_procs = _start_servers(ports)
        else:
            if not _port_up(8000):
                raise RuntimeError("shared mode needs the :8000 server running")
            ports = [8000] * w
            server_procs = []
        try:
            barrier = ctx.Barrier(w)
            out_q = ctx.Queue()
            procs = [
                ctx.Process(target=_worker_c, args=(ports[i], battles_per_worker, in_flight, barrier, out_q, net))
                for i in range(w)
            ]
            for p in procs:
                p.start()
            results = [out_q.get(timeout=600) for _ in procs]
            for p in procs:
                p.join()
        finally:
            for p in server_procs:
                p.terminate()
            for p in server_procs:
                p.wait()
        decisions = sum(r[0] for r in results)
        wall = max(r[1] for r in results)
        share = statistics.mean(r[2] / r[1] for r in results)
        print(
            f"{w:7d}  {wall:11.2f}  {decisions / wall:11.1f}  "
            f"{w * battles_per_worker / wall:9.2f}  {share:21.3f}"
        )


def measure_d(batch_sizes: list[int], iters: int = 2000, net: str = "tiny"):
    policy = make_policy(net=net)
    rng = np.random.default_rng(0)
    print(f"policy forward (masked actor + critic + sample) at OBS_DIM={OBS_DIM}  [net={net}]")
    print("batch  total_us  per_sample_us  samples/s")
    for b in batch_sizes:
        obs = rng.random((b, OBS_DIM), dtype=np.float32)
        mask = np.ones((b, N_ACTIONS), dtype=bool)
        for _ in range(200):  # warmup
            policy(obs, mask)
        t0 = time.perf_counter()
        for _ in range(iters):
            policy(obs, mask)
        per_call = (time.perf_counter() - t0) / iters
        print(
            f"{b:5d}  {per_call * 1e6:8.1f}  {per_call / b * 1e6:13.2f}  "
            f"{b / per_call:9.0f}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurement", choices=["a", "b", "c", "d"])
    parser.add_argument("--battles", type=int, default=20, help="(a) battle count")
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32, 64]
    )
    parser.add_argument(
        "--battles-per-point", type=int, default=None,
        help="(b) battles per concurrency point; default max(8, 4n)",
    )
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--battles-per-worker", type=int, default=128)
    parser.add_argument(
        "--in-flight", type=int, default=16,
        help="(c) battles in flight per worker; default 16, measurement (b)'s plateau",
    )
    parser.add_argument("--servers", choices=["shared", "per-worker"], default="shared")
    parser.add_argument(
        "--net", choices=["tiny", "mlp512", "entity"], default="tiny",
        help="policy stack; absolute claims need mlp512/entity (E4b), tiny is "
        "shape-reads only",
    )
    args = parser.parse_args()
    # The repo's tiny-net lesson, third confirmation pending: 1 thread.
    torch.set_num_threads(1)
    if args.measurement == "a":
        measure_a(args.battles, net=args.net)
    elif args.measurement == "b":
        measure_b(args.concurrency, args.battles_per_point, net=args.net)
    elif args.measurement == "c":
        measure_c(args.workers, args.battles_per_worker, args.in_flight, args.servers,
                  net=args.net)
    else:
        measure_d([1, 2, 4, 8, 16, 32, 64, 128], net=args.net)

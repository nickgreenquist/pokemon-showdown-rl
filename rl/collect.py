"""Capstone collection loop: the single inference seam and the poke-env
Player that routes battle decisions through it.

This implements the Phase 5 structural contract (PLAN.md, decided
2026-07-28, before the loop existed): battle coroutines never call the
policy directly — they submit (obs, mask) to one seam and await an action.
Batch-1 servicing is the initial implementation; micro-batched or
lockstep-vector servicing changes the seam's internals only, and whether
that change pays is throughput measurement (d)'s question, not an
assumption.

Concurrency model this rides on: poke-env schedules every player coroutine
onto its singleton background event loop (poke_env.concurrency.POKE_LOOP, a
daemon thread), so all in-flight battles in a process share that loop and
one seam services them all. Batch-1 inference therefore blocks the same
loop that services the websockets — which is exactly the batch-1 pathology
the hardware note names, represented honestly rather than hidden on a side
thread.

The seam speaks numpy at its boundary (torch stays inside the policy
callable), keeping it env-agnostic.
"""

import time

import numpy as np

from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.player import Player

from rl.envs.showdown import embed_battle


class InferenceSeam:
    """All battle decisions funnel through request(); the policy is called
    nowhere else.

    `policy`: (obs [B, D] float32, mask [B, A] bool) -> [B] int actions.
    Called with B=1 today; the batch axis is in the signature so a batching
    seam never changes the policy contract either.

    Counters (requests, inference_seconds) are the timing hooks the
    pre-registered throughput measurements read; single-threaded on
    POKE_LOOP, so plain attributes suffice.
    """

    def __init__(self, policy):
        self._policy = policy
        self.requests = 0
        self.inference_seconds = 0.0

    async def request(self, obs: np.ndarray, mask: np.ndarray) -> int:
        t0 = time.perf_counter()
        action = int(self._policy(obs[None, :], mask[None, :])[0])
        self.inference_seconds += time.perf_counter() - t0
        self.requests += 1
        return action


class SeamPlayer(Player):
    """poke-env Player whose choose_move encodes the battle, asks the seam,
    and converts the action back to an order.

    Uses the same embed_battle / get_action_mask / action_to_order trio as
    the Gym path (rl/envs/showdown.py), so both collection routes see
    identical observations and identical legality. action_to_order runs
    with poke-env's strict default: an action outside the mask raises
    instead of degrading to a random move, so a masking bug cannot hide in
    throughput numbers or rollouts.
    """

    def __init__(self, seam: InferenceSeam, *, battle_format: str = "gen1randombattle", **kwargs):
        super().__init__(battle_format=battle_format, **kwargs)
        self._seam = seam
        self._type_chart = GenData.from_format(battle_format).type_chart

    async def choose_move(self, battle):
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        action = await self._seam.request(obs, mask)
        return SinglesEnv.action_to_order(np.int64(action), battle)

"""Capstone collection loop: the single inference seam and the poke-env
Players that route battle decisions through it — the policy's (SeamPlayer)
and, for the behavioral-cloning diagnostic, a scripted bot's
(RecordingPlayer).

This implements the Phase 5 structural contract (SESSION_LOGS_PREDECESSOR.md, decided
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

from rl.envs.showdown import embed_battle, opponent_player


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


class RecordingPlayer(Player):
    """A scripted bot playing its own battles with every decision recorded as
    an (obs, mask, action) row — the behavioral-cloning data path for the
    encoder-ceiling diagnostic (SESSION_LOGS_PREDECESSOR.md P4).

    The expert is held as a plain non-listening Player whose choose_move is
    called on OUR battle object (MixturePlayer's pattern, one level up): this
    seat owns the websocket, the expert only supplies orders. Encoding, mask
    and conversion are SeamPlayer's trio, so a recorded row is exactly what a
    learner would have seen at that decision — same encoder, same legality.

    The recorded action is round-tripped back through `action_to_order` and
    compared against the expert's own order before the row is kept. That is
    the dataset's correctness property, not a formality: the move index is
    relative to `active_pokemon.moves` (or, for Struggle, to
    `available_moves`), so a mis-indexed label would teach the clone to name
    a *different* move under the very conversion deployment uses, and no
    downstream number could reveal it — the clone would simply look weak,
    which is the diagnostic's own failure verdict.

    Rows carry a battle index because decisions inside one battle share a
    team, a turn context and an opponent: an honest holdout splits on
    battles, never on rows.
    """

    def __init__(
        self,
        expert: str = "heuristics",
        *,
        battle_format: str = "gen1randombattle",
        **kwargs,
    ):
        super().__init__(battle_format=battle_format, **kwargs)
        # The one opponent-spec resolver (rl/envs/showdown.py) — the expert
        # surface is exactly the training-opponent surface, mixtures included.
        self._expert = opponent_player(expert, battle_format)
        self._type_chart = GenData.from_format(battle_format).type_chart
        self._battle_ids: dict[str, int] = {}
        self.obs: list[np.ndarray] = []
        self.masks: list[np.ndarray] = []
        self.actions: list[int] = []
        self.battle_ids: list[int] = []

    def choose_move(self, battle):
        # Sync, like PoolPlayer and unlike SeamPlayer: nothing here awaits.
        assert not battle.wait, "wait state reached the recording player"
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        order = self._expert.choose_move(battle)
        action = int(SinglesEnv.order_to_action(order, battle))
        # Default (-2) and forfeit (-1) orders have no learner-facing action.
        # Checked before the round-trip, which a default order would PASS
        # (it converts back to itself) on its way to indexing the mask from
        # the wrong end.
        assert action >= 0, f"expert produced a non-action order: {order}"
        assert str(SinglesEnv.action_to_order(np.int64(action), battle)) == str(order), (
            f"action {action} does not convert back to the expert's order {order}"
        )
        assert mask[action], f"expert order {order} -> action {action} outside the mask"
        self.obs.append(obs)
        self.masks.append(mask)
        self.actions.append(action)
        self.battle_ids.append(
            self._battle_ids.setdefault(battle.battle_tag, len(self._battle_ids))
        )
        return order

    def dataset(self) -> dict[str, np.ndarray]:
        """The recorded rows as arrays, in decision order. Concurrent battles
        interleave, so rows are grouped by `battle_id`, not contiguous."""
        return {
            "obs": np.asarray(self.obs, dtype=np.float32),
            "masks": np.asarray(self.masks, dtype=bool),
            "actions": np.asarray(self.actions, dtype=np.int64),
            "battle_ids": np.asarray(self.battle_ids, dtype=np.int64),
        }

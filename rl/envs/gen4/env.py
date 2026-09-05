"""The gen-4 env classes: `Gen4ShowdownSingles` (two-seat poke-env env with
the gen-4 encoder) and `Gen4ShowdownEnv` (the single-agent adapter), plus
the gym registration hook for `ShowdownGen4-v0`.

Additive beside rl/envs/showdown.py: the gen-1 classes are subclassed or
mirrored, never edited. `Gen4ShowdownSingles` overrides construction (the
gen-4 obs width) and `embed_battle` (the gen-4 encoder with a per-battle
tracker); reward, the mask-desync recovery, the timer knob and the wait pump
are inherited unchanged. `Gen4ShowdownEnv` is ShowdownEnv's __init__ with
the inner class swapped — duplicated rather than parameterised so the gen-1
file stays untouched on this branch; fold into an `inner_cls` kwarg at merge.

`info["privileged"]` (D18) comes from `privileged_block_gen4` on seat 2's
own gen-4 encoding; the opponent-action label (D25) rides the same
`PoolPlayer` hook, but a gen-4 pool member must encode with THIS encoder —
`Gen4PoolPlayer` below overrides the encode.
"""

from __future__ import annotations

import numpy as np
from gymnasium import Env, spaces
from poke_env.data import GenData
from poke_env.environment import SingleAgentWrapper, SinglesEnv
from poke_env.player import Player

from rl.envs import showdown as sd
from rl.envs.gen4.encoder import embed_battle_gen4, privileged_block_gen4
from rl.envs.gen4.spec import ENCODER_FINGERPRINT_GEN4, N_ACTIONS_GEN4, OBS_DIM_GEN4
from rl.envs.gen4.tracker import BattleTracker
from rl.selfplay.pool import SnapshotPool

GEN4_FORMAT = "gen4randombattle"


def fake_spaces_gen4(obs_dim: int | None = None) -> tuple[spaces.Box, spaces.Discrete]:
    """(observation_space, action_space) without a websocket — the gen-4
    twin of rl/envs/showdown.py::fake_spaces."""
    width = OBS_DIM_GEN4 if obs_dim is None else obs_dim
    return (
        spaces.Box(low=-1.0, high=4.0, shape=(width,), dtype=np.float32),
        spaces.Discrete(N_ACTIONS_GEN4),
    )


class Gen4ShowdownSingles(sd.ShowdownSingles):
    """ShowdownSingles with the gen-4 encoder. One BattleTracker per battle
    object (the two seats share a battle_tag, so keying by object is the
    same rule `_faint_potential` follows); cleared at reset."""

    def __init__(self, *, battle_format: str = GEN4_FORMAT, **kwargs):
        assert GenData.from_format(battle_format).gen == 4, battle_format
        super().__init__(battle_format=battle_format, **kwargs)
        self._trackers: dict[object, BattleTracker] = {}
        self._seat2_zeros = np.zeros(OBS_DIM_GEN4, dtype=np.float32)
        self.observation_spaces = {
            agent: spaces.Box(low=-1.0, high=4.0, shape=(OBS_DIM_GEN4,), dtype=np.float32)
            for agent in self.possible_agents
        }

    def reset(self, seed=None, options=None):
        self._trackers.clear()
        return super().reset(seed=seed, options=options)

    def tracker_for(self, battle) -> BattleTracker:
        tracker = self._trackers.get(battle)
        if tracker is None:
            tracker = self._trackers[battle] = BattleTracker()
        return tracker

    def embed_battle(self, battle) -> np.ndarray:
        if self._discard_seat2_obs and battle is self.battle2:
            return self._seat2_zeros
        return embed_battle_gen4(battle, self._type_chart, self.tracker_for(battle))


class Gen4PoolPlayer(sd.PoolPlayer):
    """PoolPlayer whose members see gen-4 encodings (they were trained on
    them). One BattleTracker per battle TAG, popped exactly when the
    `_by_tag` entry is: at `report_outcome` (the sync training path, which
    pops the entry before the next battle's first choose_move can sweep it)
    and at the finished-battle sweep (the listening / async paths). Keying
    by object and pruning only in the sweep leaked one tracker per battle
    on the training path (2026-09-05 review)."""

    def __init__(self, pool: SnapshotPool, *, battle_format: str = GEN4_FORMAT, **kwargs):
        super().__init__(pool, battle_format=battle_format, **kwargs)
        self._trackers: dict[str, BattleTracker] = {}

    def _sweep_finished(self) -> None:
        for tag, (done, _, _) in list(self._by_tag.items()):
            if getattr(done, "finished", False):
                del self._by_tag[tag]
                self._choices.pop(tag, None)
                self._turn_counts.pop(tag, None)
                self._trackers.pop(tag, None)

    def report_outcome(self, outcome: int, battle_tag: str | None = None) -> None:
        if battle_tag is None and self._by_tag:
            battle_tag = next(iter(self._by_tag))  # PoolPlayer's sync-path resolution
        super().report_outcome(outcome, battle_tag)
        if battle_tag is not None:
            self._trackers.pop(battle_tag, None)

    def choose_move(self, battle):
        assert not battle.wait, "wait state reached the pool opponent"
        tag = battle.battle_tag
        entry = self._by_tag.get(tag)
        if entry is None:
            self._sweep_finished()
            member = self._pool.select(self._rng)
            entry = (battle, member, self._pool.member_id(member))
            self._by_tag[tag] = entry
        tracker = self._trackers.get(tag)
        if tracker is None:
            tracker = self._trackers[tag] = BattleTracker()
        obs = embed_battle_gen4(battle, self._type_chart, tracker)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        action = entry[1].move(obs, mask, self._rng)
        try:
            order = SinglesEnv.action_to_order(np.int64(action), battle)
        except ValueError as exc:
            self._choice = sd._OPP_CHOICE_NONE
            self._record_choice(battle, sd._OPP_CHOICE_NONE)
            return sd._recover_mask_desync(battle, exc)
        self._choice = sd._order_identity(order, battle)
        self._record_choice(battle, self._choice)
        return order


def opponent_player_gen4(spec, battle_format: str = GEN4_FORMAT) -> Player:
    """rl/envs/showdown.py::opponent_player with the gen-4 pool adapter."""
    if isinstance(spec, SnapshotPool):
        return Gen4PoolPlayer(spec, battle_format=battle_format, start_listening=False)
    return sd.opponent_player(spec, battle_format)


class Gen4ShowdownEnv(Env):
    """Single-agent adapter over SingleAgentWrapper(Gen4ShowdownSingles, opponent).
    Mirrors rl/envs/showdown.py::ShowdownEnv (its docstring holds; the
    orphaned-room / timer landmine applies verbatim)."""

    metadata = {"render_modes": []}
    fingerprint = ENCODER_FINGERPRINT_GEN4

    def __init__(
        self,
        opponent: str | Player = "max_power",
        battle_format: str = GEN4_FORMAT,
        render_mode: str | None = None,
        save_replays: bool | str = False,
        faint_shaping: float = 0.0,
        hl_shaping: float = 0.0,
        privileged: bool = False,
        opp_action: bool = False,
        start_timer_on_battle_start: bool = True,
    ):
        self.render_mode = render_mode
        inner = Gen4ShowdownSingles(
            battle_format=battle_format,
            save_replays=save_replays,
            faint_shaping=faint_shaping,
            hl_shaping=hl_shaping,
            start_timer_on_battle_start=start_timer_on_battle_start,
            discard_seat2_obs=True,
        )
        player = opponent_player_gen4(opponent, battle_format)
        self._opponent = player
        self._pool_player = player if isinstance(player, sd.PoolPlayer) else None
        self._env = SingleAgentWrapper(inner, player)
        self.action_space = self._env.action_space
        self.observation_space = self._env.observation_space["observation"]
        self._privileged = privileged
        self._opp_action = opp_action and self._pool_player is not None
        self.waits_absorbed = 0

    def _emit_privileged(self, info: dict) -> None:
        if not self._privileged:
            return
        inner = self._env.env
        battle2 = inner.battle2
        assert battle2 is not None, "privileged emission before seat 2's battle exists"
        info["privileged"] = privileged_block_gen4(
            embed_battle_gen4(battle2, inner._type_chart, inner.tracker_for(battle2))
        )

    # The step / reset bodies are ShowdownEnv's, unchanged (bound to this
    # class so `self._env` / `self._pool_player` resolve here).
    reset = sd.ShowdownEnv.reset
    step = sd.ShowdownEnv.step
    close = sd.ShowdownEnv.close


def ensure_registered() -> None:
    import gymnasium as gym

    if "ShowdownGen4-v0" not in gym.registry:
        gym.register(id="ShowdownGen4-v0", entry_point="rl.envs.gen4.env:Gen4ShowdownEnv")

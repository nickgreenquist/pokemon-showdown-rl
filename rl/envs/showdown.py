"""Pokémon Showdown battling env (Phase 5): a poke-env `SinglesEnv` subclass
plus the adapter presenting it through the harness's Gym + masking contract.

Layering (PLAN.md Phase 5, API review of poke-env 0.15.0): poke-env's
`PokeEnv` is a two-seat PettingZoo `ParallelEnv` whose players talk to a
local Showdown server over websockets; it has no opponent parameter — the
opponent enters one level up via poke-env's `SingleAgentWrapper`, which holds
a plain poke-env `Player` and drives the second seat. `ShowdownEnv` wraps
that stack and restores two harness contracts poke-env shapes differently:

1. poke-env puts the action mask in the OBSERVATION — it rewrites the obs
   space to Dict({"observation", "action_mask"}), PettingZoo-classic style —
   where the harness wants a plain obs and `info["action_mask"]`
   (Shimmy/OpenSpiel style; see rl/envs/wrappers.py). The adapter lifts it
   across, so the factory's `ActionMask` wrapper passes it through untouched.
2. `info["outcome"]` ∈ {-1, 0, +1} at episode end, read from `battle.won` /
   `battle.lost` and never from terminated/truncated: poke-env sets
   `terminated=True` only for a decisive wipe, while forfeits, ties and
   timer losses all arrive as `truncated=True`. A forfeit or timer loss is
   still a decided game (the server sends |win|, so `battle.won` is set);
   only a tie leaves it None.

Reward is terminal-only and equal to the outcome (+1 win, -1 loss, 0 tie),
matching Connect4Env — the sparse signal the Phase 4 campaign trained on.

Episodes are NOT reproducible from a seed: the server rolls the random teams
and damage ranges, so eval variance is handled by battle count (the Phase 5
headline metric budgets >=1000 battles per matchup), not by fixed seeds.
"""

import numpy as np
from gymnasium import Env, spaces

from poke_env.data import GenData
from poke_env.environment import SingleAgentWrapper, SinglesEnv
from poke_env.player import (
    MaxBasePowerPlayer,
    Player,
    RandomPlayer,
    SimpleHeuristicsPlayer,
)

# The Phase 5 milestone ladder's fixed opponents, weakest to strongest.
OPPONENT_PLAYERS: dict[str, type[Player]] = {
    "random": RandomPlayer,
    "max_power": MaxBasePowerPlayer,
    "heuristics": SimpleHeuristicsPlayer,
}

OBS_DIM = 10


def embed_battle(battle, type_chart) -> np.ndarray:
    """Baseline placeholder encoder (move base powers, move type
    effectiveness vs the opposing active, fainted fractions). Module-level
    so the asyncio collection path (rl/collect.py) encodes identically to
    the Gym path without an env instance; the Phase 5 encoder-design step
    replaces it."""
    vec = np.zeros(OBS_DIM, dtype=np.float32)
    active = battle.active_pokemon
    opponent = battle.opponent_active_pokemon
    if active is not None:
        # Slot order matches the action mapping: known moves, first 4.
        for i, move in enumerate(list(active.moves.values())[:4]):
            vec[i] = move.base_power / 100.0
            if opponent is not None:
                vec[4 + i] = move.type.damage_multiplier(
                    opponent.type_1, opponent.type_2, type_chart=type_chart
                )
    vec[8] = sum(mon.fainted for mon in battle.team.values()) / 6.0
    vec[9] = sum(mon.fainted for mon in battle.opponent_team.values()) / 6.0
    return vec


class ShowdownSingles(SinglesEnv):
    """The two-seat poke-env env: encoder + reward, no opponent knowledge."""

    def __init__(self, *, battle_format: str = "gen1randombattle", **kwargs):
        super().__init__(battle_format=battle_format, **kwargs)
        self._type_chart = GenData.from_format(battle_format).type_chart
        # Bounds: base_power/100 tops out at 2.5 (Explosion), damage
        # multipliers at 4. The __setattr__ hook on PokeEnv wraps each raw
        # space into Dict({"observation", "action_mask"}) as it is assigned.
        self.observation_spaces = {
            agent: spaces.Box(low=0.0, high=4.0, shape=(OBS_DIM,), dtype=np.float32)
            for agent in self.possible_agents
        }

    def calc_reward(self, battle) -> float:
        # Called once per step; battle.won/lost are None until the server
        # decides the game, so this is nonzero exactly once, at the end.
        if battle.won:
            return 1.0
        if battle.lost:
            return -1.0
        return 0.0

    def embed_battle(self, battle) -> np.ndarray:
        return embed_battle(battle, self._type_chart)


def battle_outcome(battle) -> int:
    """info["outcome"] for a finished battle: +1 won, -1 lost, 0 tie."""
    if battle.won:
        return 1
    if battle.lost:
        return -1
    return 0


def opponent_player(spec: str | Player, battle_format: str) -> Player:
    """Resolve a config opponent spec to a poke-env Player. The opponent's
    choose_move is called directly on the second seat's battle object, so it
    never needs its own server connection (start_listening=False)."""
    if isinstance(spec, Player):
        return spec
    if spec not in OPPONENT_PLAYERS:
        raise ValueError(
            f"unknown opponent {spec!r}; expected one of {sorted(OPPONENT_PLAYERS)} "
            "or a poke_env Player instance"
        )
    return OPPONENT_PLAYERS[spec](battle_format=battle_format, start_listening=False)


class ShowdownEnv(Env):
    """Single-agent adapter over SingleAgentWrapper(ShowdownSingles, opponent).

    Requires a running local Showdown server (scripts/setup_showdown.sh);
    construction opens the websocket connections and fails without one.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        opponent: str | Player = "max_power",
        battle_format: str = "gen1randombattle",
        render_mode: str | None = None,
    ):
        self.render_mode = render_mode
        inner = ShowdownSingles(battle_format=battle_format)
        self._env = SingleAgentWrapper(inner, opponent_player(opponent, battle_format))
        self.action_space = self._env.action_space
        self.observation_space = self._env.observation_space["observation"]
        # Wait-states pumped inside step() and never returned (see below);
        # exposed so the regression test can prove the pump path executes.
        self.waits_absorbed = 0

    def reset(self, *, seed=None, options=None):
        obs, info = self._env.reset(seed=seed, options=options)
        assert self._env.env.agent1_to_move, "reset returned a wait state"
        info["action_mask"] = obs["action_mask"].astype(bool)
        return obs["observation"], info

    def step(self, action):
        poke = self._env.env
        # PokeEnv.step converts and sends agent1's action ONLY when
        # agent1_to_move — otherwise it silently discards the action and
        # still returns a full transition. Fail loudly instead: a discarded
        # action entering the buffer is a phantom (s, a) pair.
        assert poke.agent1_to_move, "action would be silently discarded by poke-env"
        # np.int64, not int: poke-env's action_to_order calls action.item().
        obs, reward, terminated, truncated, info = self._env.step(np.int64(action))
        total_reward = float(reward)
        # Absorb wait states (our seat has nothing to choose — e.g. the
        # opponent is replacing a fainted mon; measured 6.4% of raw steps vs
        # max_power). As learner rows they carry a placeholder one-legal
        # mask and an ignored action: zero policy gradient, but they skew
        # advantage normalization, the entropy metric, and episode lengths.
        # The pump's dummy action is discarded by the same mechanism the
        # assert above guards.
        while not (terminated or truncated) and not poke.agent1_to_move:
            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))
            total_reward += float(reward)
            self.waits_absorbed += 1
        info["action_mask"] = obs["action_mask"].astype(bool)
        if terminated or truncated:
            assert poke.battle1 is not None
            info["outcome"] = battle_outcome(poke.battle1)
            # poke-env marks forfeits, ties and timer losses truncated=True
            # ("not a clean wipe"). To GAE, truncated means "episode cut
            # off, bootstrap gamma*V(final obs)" — stacked on top of the
            # terminal reward of a game that is OVER (at gamma=1, up to a
            # full extra +/-1 on the only reward-bearing row). Every
            # learner-visible finish is a completed game with its return
            # fully realized (reset/close-injected forfeits are consumed
            # inside poke-env and never surface here), so: terminal.
            terminated, truncated = True, False
        return obs["observation"], total_reward, terminated, truncated, info

    def close(self):
        self._env.close()

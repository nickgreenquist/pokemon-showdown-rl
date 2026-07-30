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

from poke_env.battle.effect import Effect
from poke_env.battle.move_category import MoveCategory
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
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

# --- Gen 1 observation encoder (designed 2026-07-30, replaces the 10-dim
# placeholder). Everything below is what the acting player can legitimately
# observe: own team fully, opponent mons/moves only once revealed. Species
# identity enters ONLY through base stats + types (both derivable from the
# observed species) — no embedding table, so the obs stays a flat Box and
# the harness is untouched; a species/move embedding is the priced follow-up
# if milestone 2 stalls. Type-chart multipliers are kept as engineered
# features ALONGSIDE raw type one-hots: the multiplier is the directly
# decision-relevant scalar (sample efficiency under terminal-only reward),
# the one-hots let the net learn what the scalar can't express.

# The 15 Gen 1 types, alphabetical. Fixed here (not from PokemonType, which
# carries all 20 modern members) so the one-hot layout is stable.
GEN1_TYPES = (
    PokemonType.BUG, PokemonType.DRAGON, PokemonType.ELECTRIC,
    PokemonType.FIGHTING, PokemonType.FIRE, PokemonType.FLYING,
    PokemonType.GHOST, PokemonType.GRASS, PokemonType.GROUND,
    PokemonType.ICE, PokemonType.NORMAL, PokemonType.POISON,
    PokemonType.PSYCHIC, PokemonType.ROCK, PokemonType.WATER,
)
_TYPE_INDEX = {t: i for i, t in enumerate(GEN1_TYPES)}

# FNT is excluded: the fainted flag carries it.
_STATUS_INDEX = {
    s: i
    for i, s in enumerate(
        (Status.BRN, Status.FRZ, Status.PAR, Status.PSN, Status.SLP, Status.TOX)
    )
}

# All 7 poke-env boost keys, sorted. Gen 1 has one Special stat — the server
# mirrors spa/spd — so one of the pair is redundant but harmless.
_BOOST_KEYS = ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe")

# spd is dropped: Gen 1 base data mirrors it from spa (one Special stat).
_BASE_STAT_KEYS = ("hp", "atk", "def", "spa", "spe")

# Gen 1 volatiles poke-env can represent. Light Screen is MISSING by
# necessity, not oversight: the Gen 1 sim emits it as a per-mon volatile
# ("|-start|...|Light Screen") and poke-env 0.15.0 has no LIGHT_SCREEN
# Effect member, so it parses to Effect.UNKNOWN — ambiguous, not worth a
# parser fork for one uncommon move. Reflect (its physical twin) parses.
_VOLATILES = (
    Effect.CONFUSION, Effect.FOCUS_ENERGY, Effect.LEECH_SEED,
    Effect.MUST_RECHARGE, Effect.PARTIALLY_TRAPPED, Effect.REFLECT,
    Effect.SUBSTITUTE,
)

# Block layouts (offsets documented in the fill helpers below).
GLOBAL_DIM = 5
MON_DIM = 32  # hp, fainted, active, status(6), level, stats(5), types(15), off/def matchup
ACTIVE_DIM = 16  # boosts(7), volatiles(7), status_counter, preparing
MOVE_DIM = 23  # known, bp, acc, pp, matchup, physical, status, priority, type(15)

# Layout: global | our 6 team blocks (switch-action order) | our active
# extras | our active's 4 move blocks (move-action order) | opponent's 6
# team blocks, each prefixed by a revealed flag (reveal order, zero-padded)
# | opponent active extras | opponent active's revealed move blocks.
OBS_DIM = GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM + 6 * (MON_DIM + 1) + ACTIVE_DIM + 4 * MOVE_DIM


def _best_multiplier(attacker, defender, type_chart) -> float:
    """Best type multiplier among the attacker's types vs the defender — the
    type-only switch-value proxy (ignores actual movesets by design)."""
    return max(
        t.damage_multiplier(defender.type_1, defender.type_2, type_chart=type_chart)
        for t in attacker.types
    )


def _fill_mon(vec, o, mon, foe, active, type_chart):
    """[o] hp | [+1] fainted | [+2] is-active | [+3..8] status one-hot |
    [+9] level | [+10..14] base stats | [+15..29] types | [+30] best
    multiplier of mon's types vs foe | [+31] of foe's types vs mon."""
    vec[o] = mon.current_hp_fraction
    vec[o + 1] = mon.fainted
    vec[o + 2] = mon is active
    status = _STATUS_INDEX.get(mon.status)
    if status is not None:
        vec[o + 3 + status] = 1.0
    vec[o + 9] = mon.level / 100.0
    for i, key in enumerate(_BASE_STAT_KEYS):
        vec[o + 10 + i] = mon.base_stats[key] / 255.0
    for t in mon.types:
        idx = _TYPE_INDEX.get(t)
        if idx is not None:
            vec[o + 15 + idx] = 1.0
    if foe is not None:
        vec[o + 30] = _best_multiplier(mon, foe, type_chart)
        vec[o + 31] = _best_multiplier(foe, mon, type_chart)


def _fill_active(vec, o, mon):
    """[o..6] boosts/6 | [+7..13] volatile flags | [+14] status counter
    (sleep/toxic turns, /16 = the toxic cap) | [+15] preparing (two-turn
    move charging)."""
    for i, key in enumerate(_BOOST_KEYS):
        vec[o + i] = mon.boosts[key] / 6.0
    for i, effect in enumerate(_VOLATILES):
        vec[o + 7 + i] = effect in mon.effects
    vec[o + 14] = mon.status_counter / 16.0
    vec[o + 15] = bool(mon.preparing)


def _fill_move(vec, o, move, foe, type_chart):
    """[o] slot known | [+1] base power/100 | [+2] accuracy | [+3] PP left |
    [+4] type multiplier vs foe | [+5] physical | [+6] status move |
    [+7] priority/5 | [+8..22] move type one-hot."""
    vec[o] = 1.0
    vec[o + 1] = move.base_power / 100.0
    vec[o + 2] = move.accuracy
    vec[o + 3] = move.current_pp / move.max_pp if move.max_pp else 0.0
    if foe is not None:
        vec[o + 4] = move.type.damage_multiplier(
            foe.type_1, foe.type_2, type_chart=type_chart
        )
    vec[o + 5] = move.category == MoveCategory.PHYSICAL
    vec[o + 6] = move.category == MoveCategory.STATUS
    vec[o + 7] = move.priority / 5.0
    idx = _TYPE_INDEX.get(move.type)
    if idx is not None:
        vec[o + 8 + idx] = 1.0


def embed_battle(battle, type_chart) -> np.ndarray:
    """Gen 1 observable-state encoder. Module-level so the asyncio
    collection path (rl/collect.py) encodes identically to the Gym path
    without an env instance.

    Slot alignment is load-bearing, pinned by poke-env's action mapping
    (singles_env.py): switch action i resolves to list(battle.team.values())
    [i] and move action 6+j to list(active.moves.values())[:4][j], so our
    team blocks and move blocks use exactly those orderings — the policy can
    associate the features in slot i with action i. Opponent blocks have no
    action attached and sit in reveal order, zero-padded, behind a
    revealed flag.
    """
    vec = np.zeros(OBS_DIM, dtype=np.float32)
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    vec[0] = min(battle.turn / 50.0, 1.0)
    vec[1] = sum(mon.fainted for mon in battle.team.values()) / 6.0
    vec[2] = sum(mon.fainted for mon in battle.opponent_team.values()) / 6.0
    vec[3] = bool(battle.force_switch)
    vec[4] = bool(battle.trapped)
    o = GLOBAL_DIM
    for i, mon in enumerate(list(battle.team.values())[:6]):
        _fill_mon(vec, o + i * MON_DIM, mon, theirs, ours, type_chart)
    o += 6 * MON_DIM
    if ours is not None:
        _fill_active(vec, o, ours)
        for i, move in enumerate(list(ours.moves.values())[:4]):
            _fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, move, theirs, type_chart)
    o += ACTIVE_DIM + 4 * MOVE_DIM
    for i, mon in enumerate(list(battle.opponent_team.values())[:6]):
        base = o + i * (MON_DIM + 1)
        vec[base] = 1.0  # revealed
        _fill_mon(vec, base + 1, mon, ours, theirs, type_chart)
    o += 6 * (MON_DIM + 1)
    if theirs is not None:
        _fill_active(vec, o, theirs)
        for i, move in enumerate(list(theirs.moves.values())[:4]):
            _fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, move, ours, type_chart)
    return vec


class ShowdownSingles(SinglesEnv):
    """The two-seat poke-env env: encoder + reward, no opponent knowledge."""

    def __init__(self, *, battle_format: str = "gen1randombattle", **kwargs):
        super().__init__(battle_format=battle_format, **kwargs)
        self._type_chart = GenData.from_format(battle_format).type_chart
        # Bounds: boosts/6 and priority/5 reach -1; damage multipliers top
        # out at 4 (everything else is a flag or a normalized fraction). The
        # __setattr__ hook on PokeEnv wraps each raw space into
        # Dict({"observation", "action_mask"}) as it is assigned.
        self.observation_spaces = {
            agent: spaces.Box(low=-1.0, high=4.0, shape=(OBS_DIM,), dtype=np.float32)
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

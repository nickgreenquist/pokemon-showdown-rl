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

import os
import random

import numpy as np
from gymnasium import Env, spaces

from poke_env.battle.effect import Effect
from poke_env.battle.move import Move
from poke_env.battle.move_category import MoveCategory
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.battle.target import Target
from poke_env.data import GenData
from poke_env.environment import SingleAgentWrapper, SinglesEnv
from functools import lru_cache

from poke_env.player import (
    MaxBasePowerPlayer,
    Player,
    RandomPlayer,
    SimpleHeuristicsPlayer,
)

from rl.envs.randbats_prior import conditional_move_probs, known_species
from rl.selfplay.pool import SnapshotPool

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

# poke-env's SPECIAL_MOVES (battle/move.py): when one of these is the only
# legal move-action, poke-env re-bases the move index onto `available_moves`,
# so move slot i stops meaning "the mon's move i". gen1's `fight` placeholder
# is the common case (~1.5% of decisions); struggle and recharge alias the
# same way.
_SPECIAL_MOVE_IDS = frozenset({"fight", "struggle", "recharge"})

# --- Encoder v2 (2026-08-06, BC-chapter screen), behind POKEMON_RL_ENCODER_V2=1.
# Appends (a) a 23-dim per-move EFFECT block — what the move DOES beyond damage:
# inflicted status + probability, self/foe boost sums, heal/recoil/drain,
# crit class, multi-hit, self-destruct, recharge/charge, volatiles — and (b) a
# per-mon speed-edge scalar vs the opposing active. Motivation (direction
# audit): under v1, Rest/Amnesia/Reflect are near-identical vectors, and the
# Foul Play teacher conditions on exactly these mechanics; the SH clone never
# needed them because SH doesn't read them. Feature list adapted from ps-ppo's
# move token (obs_moves.py, github.com/Nebraskinator/ps-ppo, MIT) — the
# secondary-status-probability and STAB-class fields our 2026-08-04 audit
# flagged — recomputed here from poke-env gen-1 move data. Default OFF: with
# the flag unset, OBS_DIM stays 611 and the encoding is bit-identical to v1.
_ENCODER_V2 = bool(os.environ.get("POKEMON_RL_ENCODER_V2"))

# Block layouts (offsets documented in the fill helpers below).
GLOBAL_DIM = 5
EFFECT_DIM = 23  # v2 only: appended to each move block
MON_DIM = 33 if _ENCODER_V2 else 32  # hp, fainted, active, status(6), level, stats(5), types(15), off/def matchup [, v2 speed edge]
ACTIVE_DIM = 16  # boosts(7), volatiles(7), status_counter, preparing
MOVE_DIM = (23 + EFFECT_DIM) if _ENCODER_V2 else 23  # known, bp, acc, pp, matchup, physical, status, priority, type(15) [, v2 effect block]

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
    multiplier of mon's types vs foe | [+31] of foe's types vs mon |
    v2 only: [+32] speed edge vs foe in (-1, 1)."""
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
        if _ENCODER_V2:
            vec[o + 32] = _speed_edge(mon, foe, mon is active)


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


def _fill_move(vec, o, move, foe, type_chart, prob: float = 1.0):
    """[o] slot known -- for the OPPONENT this is P(the mon has this move),
    read from the vendored randbats set prior, so an unrevealed but near-certain
    move is encoded as such instead of as a block of zeros. 1.0 for our own
    moves and for opponent moves already revealed. Reinterpreting this flag as
    a probability is what makes the set prior cost ZERO extra dimensions.
    | [+1] base power/100 | [+2] accuracy | [+3] PP left |
    [+4] type multiplier vs foe | [+5] physical | [+6] status move |
    [+7] priority/5 | [+8..22] move type one-hot."""
    vec[o] = prob
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
    if _ENCODER_V2:
        vec[o + 23 : o + 23 + EFFECT_DIM] = _effect_block(move.id)


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
        # ALIASING FIX. On a gen1 placeholder turn (active asleep/frozen/
        # partially trapped) Showdown replaces the move list with a single
        # `Fight`, and poke-env maps it to move-action slot 0 -- but these
        # blocks describe the four REAL moves, so the network would be taught
        # "slot-0 features X => take action 6" when action 6 means "stay in
        # with whatever gen1 forces". Same for Struggle/Recharge. Leave the
        # blocks zeroed: the `known` flags at 0 say the slots are inert, and
        # the SLP/FRZ/PARTIALLY_TRAPPED bits are already in _fill_mon and
        # _fill_active, so the state stays fully described.
        if not _move_slots_aliased(battle):
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
        # Opponent blocks carry NO action, so unlike our own they are free to
        # be filled from the set prior. Revealed moves first at p=1.0, then the
        # most likely unrevealed candidates. This is the information Foul Play
        # determinizes over and that we were discarding as zeros.
        for i, (move, prob) in enumerate(_opponent_move_slots(theirs)):
            _fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, move, ours, type_chart, prob)
    return vec


def _move_slots_aliased(battle) -> bool:
    """True when the only legal move-action is one of poke-env's SPECIAL_MOVES
    (fight / struggle / recharge), so move slot i no longer means move i."""
    avail = getattr(battle, "available_moves", None)
    return bool(avail) and len(avail) == 1 and avail[0].id in _SPECIAL_MOVE_IDS


@lru_cache(maxsize=4096)
def _move_obj(move_id: str):
    return Move(move_id, gen=1)


# --- Encoder-v2 helpers (inert unless POKEMON_RL_ENCODER_V2=1) -------------

# m.secondary carries lowercase status strings; indices match _STATUS_INDEX.
_SEC_STATUS_STR = {"brn": 0, "frz": 1, "par": 2, "psn": 3, "slp": 4, "tox": 5}

# Volatiles a MOVE can inflict, indexed within the effect block. MUST_RECHARGE
# (Hyper Beam) is omitted — the recharge flag carries it.
_MOVE_VOL_INDEX = {
    Effect.CONFUSION: 0,
    Effect.PARTIALLY_TRAPPED: 1,
    Effect.SUBSTITUTE: 2,
    Effect.REFLECT: 3,
    Effect.LEECH_SEED: 4,
    Effect.FLINCH: 5,
}
_SEC_VOL_STR = {"confusion": 0, "partiallytrapped": 1, "flinch": 5}


@lru_cache(maxsize=4096)
def _effect_block(move_id: str) -> np.ndarray:
    """v2: what the move DOES beyond damage. Static per move id, cached.

    [0..5] inflicted-status one-hot (BRN FRZ PAR PSN SLP TOX) | [6] its
    probability (1.0 primary, chance/100 secondary) | [7] self boost sum /4
    (Amnesia 1.0) | [8] foe boost sum /4, chance-weighted, signed (Growl
    -0.25, gen1 Psychic -0.165) | [9] heal fraction ('heal'-flagged moves
    with no numeric fraction, i.e. Rest, encode 1.0) | [10] recoil |
    [11] drain | [12] crit ratio /2 (Slash 1.0) | [13] extra hits /2
    (Double Kick 0.5) | [14] self-destruct | [15] recharge | [16] charge
    turn | [17..22] inflicted-volatile one-hot (CONFUSION PARTIALLY_TRAPPED
    SUBSTITUTE REFLECT LEECH_SEED FLINCH), chance-weighted (a secondary's
    chance overwrites the primary 1.0, e.g. Bite's flinch at 0.1)."""
    v = np.zeros(EFFECT_DIM, dtype=np.float32)
    try:
        m = _move_obj(move_id)
    except Exception:
        return v  # synthetic ids (the gen1 fight placeholder): stay zero
    if m.status is not None:
        idx = _STATUS_INDEX.get(m.status)
        if idx is not None:
            v[idx] = 1.0
            v[6] = 1.0
    boosts = m.boosts or {}
    if m.target == Target.SELF:
        v[7] = sum(boosts.values()) / 4.0
    else:
        v[8] = sum(boosts.values()) / 4.0
    vol = _MOVE_VOL_INDEX.get(m.volatile_status)
    if vol is not None:
        v[17 + vol] = 1.0
    for sec in m.secondary or []:
        chance = sec.get("chance", 100) / 100.0
        st = _SEC_STATUS_STR.get(sec.get("status"))
        if st is not None:
            v[st] = 1.0
            v[6] = max(v[6], chance)
        if "boosts" in sec:
            v[8] += sum(sec["boosts"].values()) * chance / 4.0
        svol = _SEC_VOL_STR.get(sec.get("volatileStatus"))
        if svol is not None:
            v[17 + svol] = chance
    v[9] = m.heal if m.heal else (1.0 if "heal" in m.flags else 0.0)
    v[10] = m.recoil
    v[11] = m.drain
    v[12] = m.crit_ratio / 2.0
    v[13] = (m.expected_hits - 1.0) / 2.0
    v[14] = bool(m.self_destruct)
    v[15] = "recharge" in m.flags
    v[16] = "charge" in m.flags
    return v


def _spe_est(mon, is_active: bool) -> float:
    """Crude actual-speed proxy: base speed scaled by level, with boost and
    paralysis applied for on-field mons. Monotone in the true gen1 stat
    (randbats DVs/stat exp are fixed), which is all the edge feature needs."""
    s = mon.base_stats["spe"] * mon.level / 100.0
    if is_active:
        b = mon.boosts["spe"]
        s *= (2 + b) / 2.0 if b >= 0 else 2.0 / (2 - b)
        if mon.status == Status.PAR:
            s *= 0.25
    return max(s, 1e-3)


def _speed_edge(mon, foe, mon_is_active: bool) -> float:
    """v2: (a-d)/(a+d) in (-1, 1); positive = mon outspeeds the foe active."""
    a = _spe_est(mon, mon_is_active)
    d = _spe_est(foe, True)
    return (a - d) / (a + d)


# Ablation switch. Set POKEMON_RL_NO_SET_PRIOR=1 to encode ONLY revealed
# opponent moves, i.e. the pre-2026-08-06 behaviour. Because the durable
# artefact is the raw tape, this makes "what did the set prior actually buy?"
# an offline re-embed rather than a re-collection.
_NO_SET_PRIOR = bool(os.environ.get("POKEMON_RL_NO_SET_PRIOR"))


def _opponent_move_slots(theirs):
    """Up to 4 (Move, probability) pairs for the opponent's active pokemon."""
    revealed = [m for m in list(theirs.moves.values())[:4]]
    slots = [(m, 1.0) for m in revealed]
    if len(slots) >= 4:
        return slots[:4]
    species = theirs.species
    if _NO_SET_PRIOR or species not in known_species():
        return slots
    seen = frozenset(m.id for m in revealed)
    for move_id, prob in conditional_move_probs(species, seen):
        if len(slots) >= 4:
            break
        try:
            slots.append((_move_obj(move_id), prob))
        except Exception:
            continue  # a pool entry poke-env cannot construct: skip, do not fail
    return slots


class ShowdownSingles(SinglesEnv):
    """The two-seat poke-env env: encoder + reward, no opponent knowledge.

    `faint_shaping` (0.0 = off, the shape every run before Arm B trained on)
    adds POTENTIAL-BASED faint shaping on top of the terminal ±1:

        Phi(s) = faint_shaping * (faints_opp(s) - faints_self(s)),  Phi(terminal) := 0
        shaping(s -> s') = Phi(s') - Phi(s)

    which is ±faint_shaping per faint, symmetric, exactly the ps-ppo term
    (their confirmed constants `faint_self: -0.1`, `faint_opp: +0.1`) PLUS
    the terminal cancellation that pins Phi to 0 at the end of the episode.
    The cancellation is the deliberate deviation (DESIGN.md §4), and it is
    load-bearing rather than cosmetic:

    - At gamma = 1.0 the shaping sum telescopes to Phi(s_T) - Phi(s_0) =
      Phi(s_T). WITHOUT the cancellation the effective outcome signal spans
      ±1.6 and a clean-sweeping 48%-win policy outscores a trading 50%-win
      one — the trade-down failure mode is then in the objective as written.
      Ng et al.'s policy-invariance result is exactly what forcing
      Phi(terminal) = 0 buys back.
    - Episode return stays the terminal ±1 exactly, so
      `rollout/episode_return` remains comparable to every prior run and no
      eval number moves.
    - Value targets stay in ±1. Advantages are normalized per minibatch but
      value targets are NOT, so shaping that survived to the terminal would
      silently inflate the value loss ~2.5x against `value_coef: 0.5`.

    Implemented as a state POTENTIAL rather than by attributing faint events
    to the transitions that caused them: the potential is recomputed from the
    two teams' fainted counts every step and only differenced, so there is no
    event bookkeeping to get wrong. That is deliberate — the known trap in
    this exact lever (ps-ppo commit `17e0955`) is an off-by-one in faint
    attribution, and a differenced potential has no attribution step to be
    off by one in.
    """

    def __init__(
        self,
        *,
        battle_format: str = "gen1randombattle",
        faint_shaping: float = 0.0,
        **kwargs,
    ):
        super().__init__(battle_format=battle_format, **kwargs)
        self._type_chart = GenData.from_format(battle_format).type_chart
        self.faint_shaping = faint_shaping
        # Phi(s) for the CURRENT state of each live battle, keyed by the
        # battle OBJECT: calc_reward is called once per step for each seat's
        # own battle, and the two share a battle_tag, so any key derived from
        # the tag would fuse the two seats' faint counts. Battle defines no
        # __eq__/__hash__, so this is identity keying. Cleared at reset, which
        # bounds it at two entries — the natural lifetime, since a potential
        # from a finished battle must never be differenced against a new one.
        self._faint_potential: dict[object, float] = {}
        # Bounds: boosts/6 and priority/5 reach -1; damage multipliers top
        # out at 4 (everything else is a flag or a normalized fraction). The
        # __setattr__ hook on PokeEnv wraps each raw space into
        # Dict({"observation", "action_mask"}) as it is assigned.
        self.observation_spaces = {
            agent: spaces.Box(low=-1.0, high=4.0, shape=(OBS_DIM,), dtype=np.float32)
            for agent in self.possible_agents
        }

    def reset(self, seed=None, options=None):
        # Potentials are per-battle and must not survive into the next one.
        self._faint_potential.clear()
        return super().reset(seed=seed, options=options)

    def calc_reward(self, battle) -> float:
        # Called once per step; battle.won/lost are None until the server
        # decides the game, so the outcome term is nonzero exactly once, at
        # the end.
        outcome = 1.0 if battle.won else -1.0 if battle.lost else 0.0
        if not self.faint_shaping:
            # Bit-for-bit the pre-Arm-B reward, and the only path any
            # existing config takes. Also the reason nothing below needs to
            # tolerate the reward-only stub battles the offline tests build.
            return outcome
        previous = self._faint_potential.pop(battle, 0.0)
        if battle.finished:
            # Phi(terminal) := 0, so the transition INTO it emits -Phi(s),
            # cancelling everything the episode accumulated. Note this fires
            # on `finished` — a decided game — and never on a truncation,
            # where the episode continues and the potential must be carried
            # (this env remaps every decided finish to terminal, so the two
            # cannot be confused, but the condition is written on the game's
            # state and not on the flag either way).
            return outcome - previous
        potential = self.faint_shaping * (
            sum(mon.fainted for mon in battle.opponent_team.values())
            - sum(mon.fainted for mon in battle.team.values())
        )
        self._faint_potential[battle] = potential
        return outcome + potential - previous

    def embed_battle(self, battle) -> np.ndarray:
        return embed_battle(battle, self._type_chart)


def battle_outcome(battle) -> int:
    """info["outcome"] for a finished battle: +1 won, -1 lost, 0 tie."""
    if battle.won:
        return 1
    if battle.lost:
        return -1
    return 0


class MixturePlayer(Player):
    """Per-battle mixture over the scripted opponents (training-distribution
    lever, 2026-07-31): each NEW battle is assigned one sub-player, sampled
    by weight, that drives it to the end — a battle is never a mid-game
    chimera. The training env holds one MixturePlayer per sub-env and each
    sub-env runs one battle at a time, so only the current battle's
    assignment is kept. Weights are normalized at construction; sampling
    uses a private RNG so the choice stream is independent of global
    seeding (battles are server-rolled and non-reproducible anyway).
    """

    def __init__(self, weights: dict[str, float], *, battle_format: str, **kwargs):
        super().__init__(battle_format=battle_format, **kwargs)
        unknown = weights.keys() - OPPONENT_PLAYERS.keys()
        if unknown or not weights:
            raise ValueError(
                f"mix weights must be non-empty and over {sorted(OPPONENT_PLAYERS)}; "
                f"got {sorted(weights) or '{}'}"
            )
        if any(w <= 0 for w in weights.values()):
            raise ValueError(f"mix weights must be positive, got {weights}")
        total = sum(weights.values())
        self._names = sorted(weights)
        self._weights = [weights[n] / total for n in self._names]
        self._players = {
            name: OPPONENT_PLAYERS[name](
                battle_format=battle_format, start_listening=False
            )
            for name in self._names
        }
        self._rng = random.Random(0)
        self._battle_tag: str | None = None
        self._current: Player | None = None

    def choose_move(self, battle):
        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._current = self._players[
                self._rng.choices(self._names, weights=self._weights)[0]
            ]
        return self._current.choose_move(battle)


class PoolPlayer(Player):
    """Seat-2 adapter driving battles from the shared SnapshotPool
    (milestone 3): each NEW battle draws one frozen snapshot via
    pool.select() — the per-episode swap boundary the pool contract pins —
    and that member plays the battle to the end. One PoolPlayer per sub-env
    (per-battle tracking assumes one battle at a time), all wrapping the ONE
    pool object that arrives through the caller-kwargs identity seam
    (rl/envs/make.py).

    choose_move is SYNC on purpose: SingleAgentWrapper.step calls it on the
    caller thread and asserts the result is not awaitable. SeamPlayer
    (rl/collect.py) is the precedent for the encode/mask/convert trio only,
    NOT for its async signature. Battle tracking uses our own attribute,
    never Player._battles — SingleAgentWrapper.reset calls reset_battles()
    on the opponent at every battle boundary.
    """

    def __init__(self, pool: SnapshotPool, *, battle_format: str, **kwargs):
        super().__init__(battle_format=battle_format, **kwargs)
        self._pool = pool
        # Installer contract (SnapshotPool.freeze docstring): every
        # installer calls freeze(), even though members freeze at push.
        pool.freeze()
        self._type_chart = GenData.from_format(battle_format).type_chart
        # Reseeded per sub-env via seed_rng() from the env's first seeded
        # reset. A shared fixed stream (MixturePlayer's pattern, fine for 3
        # scripted bots) would have every sub-env draw the SAME member
        # sequence, collapsing the pool's opponent diversity 8-fold.
        self._rng = np.random.default_rng(0)
        self._battle_tag: str | None = None
        self._current = None

    def seed_rng(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def report_outcome(self, outcome: int) -> None:
        """Learner-perspective outcome of the battle that just finished,
        credited to the member that played it — the pool's PFSP stats feed.
        Called by ShowdownEnv.step at the terminal step, which is always
        before the NEXT battle's first choose_move can re-select."""
        if self._current is not None:
            self._pool.report(self._current, outcome)

    def choose_move(self, battle):
        # Wrapper contract: wait states never reach the opponent
        # (SingleAgentWrapper.step's battle2.wait bypass). If one ever did,
        # the forward below would advance the member's generator on a
        # decision poke-env then discards — the seat-2 twin of
        # ShowdownEnv.step's discarded-action assert.
        assert not battle.wait, "wait state reached the pool opponent"
        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._current = self._pool.select(self._rng)
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        action = self._current.move(obs, mask, self._rng)
        # strict default: an out-of-mask action raises rather than degrading
        # to a random move (SeamPlayer precedent).
        return SinglesEnv.action_to_order(np.int64(action), battle)


def _parse_mix(spec: str) -> dict[str, float]:
    """"mix:heuristics=0.7,max_power=0.2,random=0.1" -> weight dict."""
    weights = {}
    for part in spec.removeprefix("mix:").split(","):
        name, sep, weight = part.partition("=")
        if not sep:
            raise ValueError(f"malformed mix component {part!r} in {spec!r}")
        weights[name.strip()] = float(weight)
    return weights


def opponent_player(spec: str | Player | SnapshotPool, battle_format: str) -> Player:
    """Resolve a config opponent spec to a poke-env Player. The opponent's
    choose_move is called directly on the second seat's battle object, so it
    never needs its own server connection (start_listening=False). A
    "mix:name=w,name=w" spec builds a MixturePlayer — kept a plain string so
    the config stays scalar-only (a hard requirement if collection ever
    moves to subprocess vector envs, per the 2026-07-30 async review). A
    SnapshotPool (what rl/train.py substitutes for `opponent: self`) gets a
    PoolPlayer; the pool object itself is the one thing that must cross the
    caller-kwargs seam by identity."""
    if isinstance(spec, Player):
        return spec
    if isinstance(spec, SnapshotPool):
        return PoolPlayer(spec, battle_format=battle_format, start_listening=False)
    if isinstance(spec, str) and spec.startswith("mix:"):
        return MixturePlayer(
            _parse_mix(spec), battle_format=battle_format, start_listening=False
        )
    if spec not in OPPONENT_PLAYERS:
        raise ValueError(
            f"unknown opponent {spec!r}; expected one of {sorted(OPPONENT_PLAYERS)}, "
            "a 'mix:name=w,...' spec, or a poke_env Player instance"
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
        save_replays: bool | str = False,
        faint_shaping: float = 0.0,
    ):
        # save_replays (False | True | directory) is poke-env's native replay
        # dump: each finished battle is written as a Showdown replay HTML
        # (the official animated viewer; needs internet to load its JS).
        # Both seats save, so every battle yields two near-identical files.
        self.render_mode = render_mode
        inner = ShowdownSingles(
            battle_format=battle_format,
            save_replays=save_replays,
            faint_shaping=faint_shaping,
        )
        player = opponent_player(opponent, battle_format)
        # isinstance, not getattr: a pool-backed opponent gets outcome
        # reports and per-sub-env seeding, and a renamed hook must fail
        # loudly — nothing cross-checks the pool's stats, so a silently
        # disabled report path would corrupt PFSP forever without a metric
        # that looks wrong.
        self._pool_player = player if isinstance(player, PoolPlayer) else None
        self._env = SingleAgentWrapper(inner, player)
        self.action_space = self._env.action_space
        self.observation_space = self._env.observation_space["observation"]
        # Wait-states pumped inside step() and never returned (see below);
        # exposed so the regression test can prove the pump path executes.
        self.waits_absorbed = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None and self._pool_player is not None:
            # The vector loop's first reset fans out seed + i per sub-env;
            # every later reset passes None. Latch it here: ShowdownEnv
            # never seeds gymnasium's np_random (episodes are server-rolled),
            # so this is the only per-sub-env stream the member draw can
            # decorrelate on.
            self._pool_player.seed_rng(seed)
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
            # Terminal faint counts (ours, theirs). Always emitted, shaping or
            # not: Arm B's pre-registered SECONDARY is the faint differential
            # CONDITIONAL ON LOSSES, which needs the same number from the
            # control arm to mean anything. The unconditional differential is
            # mechanically determined by the outcome and is not the read.
            info["faints"] = (
                sum(mon.fainted for mon in poke.battle1.team.values()),
                sum(mon.fainted for mon in poke.battle1.opponent_team.values()),
            )
            if self._pool_player is not None:
                self._pool_player.report_outcome(info["outcome"])
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

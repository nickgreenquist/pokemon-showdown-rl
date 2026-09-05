"""Pokémon Showdown battling env (Phase 5): a poke-env `SinglesEnv` subclass
plus the adapter presenting it through the harness's Gym + masking contract.

Layering (SESSION_LOGS_PREDECESSOR.md Phase 5, API review of poke-env 0.15.0): poke-env's
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

import logging
import os
import random
from collections import deque

import numpy as np
from gymnasium import Env, spaces

from poke_env.battle.effect import Effect
from poke_env.battle.move import Move
from poke_env.battle.move_category import MoveCategory
from poke_env.battle.pokemon import Pokemon
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

from rl.envs.encoder_spec import GEN1, EncoderSpec, spec_for_format
from rl.envs.players import MostDamageTypedPlayer
from rl.envs.randbats_prior import conditional_move_probs, known_species
from rl.selfplay.pool import SnapshotPool

# The Phase 5 milestone ladder's fixed opponents, weakest to strongest.
OPPONENT_PLAYERS: dict[str, type[Player]] = {
    "random": RandomPlayer,
    "max_power": MaxBasePowerPlayer,
    "heuristics": SimpleHeuristicsPlayer,
    # JOURNEY's pre-step-3 anchor (rl/envs/players.py): H&L's most-damage-typed
    # bot, the cross-generation denominator. Descriptive only; it joins the
    # anchor battery by maintainer ruling (open_questions.md Q36), not by
    # being registered here.
    "most_damage_typed": MostDamageTypedPlayer,
}

# --- Gen 1 observation encoder (designed 2026-07-30, replaces the 10-dim
# placeholder). Everything below is what the acting player can legitimately
# observe: own team fully, opponent mons/moves only once revealed. Species
# identity enters ONLY through base stats + types (both derivable from the
# observed species) — no embedding table, so the obs stays a flat Box and
# the harness is untouched; the priced follow-up (a species/move embedding)
# landed 2026-08-08 as the gated id suffix below. Type-chart multipliers are
# kept as engineered
# features ALONGSIDE raw type one-hots: the multiplier is the directly
# decision-relevant scalar (sample efficiency under terminal-only reward),
# the one-hots let the net learn what the scalar can't express.

# The per-gen tables (types, statuses, boost/base-stat keys, volatiles,
# poke-env's SPECIAL_MOVES, the id ranges) live in rl/envs/encoder_spec.py
# (F-08): the fill helpers read them off a `spec` argument that defaults to
# GEN1, and the names below are GEN1's — the same objects, in the same
# order — kept for the importers that pin layout against them (tests,
# scripts, the tokenizer). The tables' whys travel with them.
GEN1_TYPES = GEN1.types
_TYPE_INDEX = GEN1.type_index
_STATUS_INDEX = GEN1.status_index
_BOOST_KEYS = GEN1.boost_keys
_BASE_STAT_KEYS = GEN1.base_stat_keys
_VOLATILES = GEN1.volatiles  # incl. the D13(a) MUST_RECHARGE why, at GEN1
_SPECIAL_MOVE_IDS = GEN1.special_move_ids

# poke-env's Discrete size for the generation the encoder serves: 6 switches
# + 4 moves, no gimmick slots through gen 5 (singles_env.py). The sites that
# build an agent without opening a websocket read it through fake_spaces().
N_ACTIONS = GEN1.n_actions

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
# the flag unset, OBS_DIM stays 612 and the encoding is bit-identical to v1.
_ENCODER_V2 = bool(os.environ.get("POKEMON_RL_ENCODER_V2"))

# --- Encoder ids (2026-08-08, Rung 2 STRUCTURE), behind POKEMON_RL_ENCODER_IDS=1.
# The identity block the entity trunk's embedding tables index by
# (configs/showdown_sp_struct12m.yaml): species identity currently enters
# ONLY through base stats + types (the priced follow-up named below), and an
# embedding needs an INDEX, so the obs must carry one. PURE SUFFIX: 12
# species ids + 8 move ids appended after the v2 block, so vec[:808] stays
# bitwise v2 and, with the flag unset, OBS_DIM and the encoding are
# untouched — the "changing OBS_DIM invalidates every checkpoint" landmine
# stays closed. Values are emitted as id/256.0 in [0, 1): exact in float32
# (256 is a power of two), inside the declared Box(low=-1, high=4), and
# recovered as round(x*256) inside the tokenizer. Unknown/unrevealed -> 0.
_ENCODER_IDS = bool(os.environ.get("POKEMON_RL_ENCODER_IDS"))
ID_DIM = 20 if _ENCODER_IDS else 0  # 6 own + 6 opp species | 4 own + 4 opp moves
ID_SCALE = 256.0

# Block layouts (offsets documented in the fill helpers below).
GLOBAL_DIM = 6
EFFECT_DIM = 23  # v2 only: appended to each move block
# Block widths at GEN1: 33/32 mon (hp, fainted, active, status(6), level,
# stats(5), types(15), off/def matchup [, v2 speed edge]), 16 active
# (boosts(7), volatiles(7), status_counter, preparing), 46/23 move (known,
# bp, acc, pp, matchup, physical, status, priority, type(15) [, v2 effect
# block]). The v1 widths are the spec's (they follow its table lengths); the
# v2 extras are process flags, appended here.
MON_DIM = (GEN1.mon_dim_v1 + 1) if _ENCODER_V2 else GEN1.mon_dim_v1
ACTIVE_DIM = GEN1.active_dim
MOVE_DIM = (GEN1.move_dim_v1 + EFFECT_DIM) if _ENCODER_V2 else GEN1.move_dim_v1

# Layout: global | our 6 team blocks (switch-action order) | our active
# extras | our active's 4 move blocks (move-action order) | opponent's 6
# team blocks, each prefixed by a revealed flag (reveal order, zero-padded)
# | opponent active extras | opponent active's revealed move blocks
# | (ids flag only) the 20-dim identity suffix.
OBS_DIM = GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM + 6 * (MON_DIM + 1) + ACTIVE_DIM + 4 * MOVE_DIM + ID_DIM

# Stamped into run metadata and BC metrics (direction-audit watch item: the
# set prior and the aliasing fix changed obs SEMANTICS at constant OBS_DIM,
# and nothing recorded which semantics a checkpoint trained under).
ENCODER_FINGERPRINT = {
    "obs_dim": OBS_DIM,
    "encoder": "v2" if _ENCODER_V2 else "v1",
    "set_prior": not bool(os.environ.get("POKEMON_RL_NO_SET_PRIOR")),
    # Stage-0 MUST_RECHARGE fix (D13a, 2026-08-07): live recharge bool + the
    # global aliased-turn flag. Distinguishes v2/808 from the dead-slot v2/807.
    "recharge_fix": True,
    # Identity suffix (Rung 2, R0-1): true iff the 20-dim id block is on.
    "ids": _ENCODER_IDS,
}


def fake_spaces(
    battle_format: str = "gen1randombattle", obs_dim: int | None = None
) -> tuple[spaces.Box, spaces.Discrete]:
    """(observation_space, action_space) for the sites that build an agent
    WITHOUT opening a websocket just to read shapes — train.py's frozen
    opponent pool and async path, eval_checkpoint.py's loader (which passes
    the checkpoint's own width as `obs_dim` for its cross-encoder shim).
    Bounds mirror ShowdownSingles.observation_spaces. The action count is
    the FORMAT's, through poke-env (10 through gen 5, then 14/18/22/26), and
    spec_for_format refuses every generation the encoder cannot serve, so a
    gen-9 format fails here by name instead of as a silent Discrete(10)
    shape bug (F-08)."""
    n_actions = spec_for_format(battle_format).n_actions
    width = OBS_DIM if obs_dim is None else obs_dim
    return (
        spaces.Box(low=-1.0, high=4.0, shape=(width,), dtype=np.float32),
        spaces.Discrete(n_actions),
    )


def _best_multiplier(attacker, defender, type_chart) -> float:
    """Best type multiplier among the attacker's types vs the defender — the
    type-only switch-value proxy (ignores actual movesets by design)."""
    return max(
        t.damage_multiplier(defender.type_1, defender.type_2, type_chart=type_chart)
        for t in attacker.types
    )


def _fill_mon(vec, o, mon, foe, active, type_chart, spec: EncoderSpec = GEN1):
    """[o] hp | [+1] fainted | [+2] is-active | [+3..8] status one-hot |
    [+9] level | [+10..14] base stats | [+15..29] types | [+30] best
    multiplier of mon's types vs foe | [+31] of foe's types vs mon |
    v2 only: [+32] speed edge vs foe in (-1, 1). Offsets quoted at GEN1;
    they are the spec's `mon_*_off` properties."""
    vec[o] = mon.current_hp_fraction
    vec[o + 1] = mon.fainted
    vec[o + 2] = mon is active
    status = spec.status_index.get(mon.status)
    if status is not None:
        vec[o + spec.mon_status_off + status] = 1.0
    vec[o + spec.mon_level_off] = mon.level / 100.0
    o_st = o + spec.mon_stats_off
    for i, key in enumerate(spec.base_stat_keys):
        vec[o_st + i] = mon.base_stats[key] / 255.0
    o_ty = o + spec.mon_types_off
    for t in mon.types:
        idx = spec.type_index.get(t)
        if idx is not None:
            vec[o_ty + idx] = 1.0
    if foe is not None:
        o_mu = o + spec.mon_matchup_off
        vec[o_mu] = _best_multiplier(mon, foe, type_chart)
        vec[o_mu + 1] = _best_multiplier(foe, mon, type_chart)
        if _ENCODER_V2:
            vec[o_mu + 2] = _speed_edge(mon, foe, mon is active)


def _fill_active(vec, o, mon, spec: EncoderSpec = GEN1):
    """[o..6] boosts/6 | [+7..13] volatile flags (MUST_RECHARGE at +10 from
    the bool, see _VOLATILES) | [+14] status counter (sleep/toxic turns,
    /16 = the toxic cap) | [+15] preparing (two-turn move charging).
    Offsets quoted at GEN1 (the spec's `active_*_off`)."""
    for i, key in enumerate(spec.boost_keys):
        vec[o + i] = mon.boosts[key] / 6.0
    o_v = o + spec.active_volatiles_off
    for i, effect in enumerate(spec.volatiles):
        vec[o_v + i] = (
            mon.must_recharge if effect is Effect.MUST_RECHARGE
            else effect in mon.effects
        )
    o_c = o + spec.active_counter_off
    vec[o_c] = mon.status_counter / 16.0
    vec[o_c + 1] = bool(mon.preparing)


def _fill_move(
    vec, o, move, foe, type_chart, prob: float = 1.0, spec: EncoderSpec = GEN1
):
    """[o] slot known -- for the OPPONENT this is P(the mon has this move),
    read from the vendored randbats set prior, so an unrevealed but near-certain
    move is encoded as such instead of as a block of zeros. 1.0 for our own
    moves and for opponent moves already revealed. Reinterpreting this flag as
    a probability is what makes the set prior cost ZERO extra dimensions.
    | [+1] base power/100 | [+2] accuracy | [+3] PP left |
    [+4] type multiplier vs foe | [+5] physical | [+6] status move |
    [+7] priority/5 | [+8..22] move type one-hot (at the spec's
    `move_type_off`; the v2 effect block follows at `move_dim_v1`)."""
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
    idx = spec.type_index.get(move.type)
    if idx is not None:
        vec[o + spec.move_type_off + idx] = 1.0
    if _ENCODER_V2:
        o_e = o + spec.move_dim_v1
        vec[o_e : o_e + EFFECT_DIM] = _effect_block(move.id)


def embed_battle(battle, type_chart, spec: EncoderSpec = GEN1) -> np.ndarray:
    """Gen 1 observable-state encoder. Module-level so the asyncio
    collection path (rl/collect.py) encodes identically to the Gym path
    without an env instance.

    `spec` supplies the per-gen tables the FILL HELPERS read
    (rl/envs/encoder_spec.py). Everything around them is still gen 1's, so
    only the GEN1 singleton is accepted here — refused loudly rather than
    mis-encoded; the refusal message is the list of what a second spec must
    lift first.

    Slot alignment is load-bearing, pinned by poke-env's action mapping
    (singles_env.py): switch action i resolves to list(battle.team.values())
    [i] and move action 6+j to list(active.moves.values())[:4][j], so our
    team blocks and move blocks use exactly those orderings — the policy can
    associate the features in slot i with action i. Opponent blocks have no
    action attached and sit in reveal order, zero-padded, behind a
    revealed flag.
    """
    if spec is not GEN1:
        raise NotImplementedError(
            f"embed_battle serves the GEN1 spec only, got gen {spec.gen}: the "
            "block strides (MON_DIM / ACTIVE_DIM / MOVE_DIM) and OBS_DIM are "
            "module-level GEN1 values, _effect_block builds Move(id, gen=1), "
            "and _opponent_move_slots reads the gen-1 randbats prior — "
            "rl/envs/encoder_spec.py lists what a second spec must lift"
        )
    vec = np.zeros(OBS_DIM, dtype=np.float32)
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    vec[0] = min(battle.turn / 50.0, 1.0)
    vec[1] = sum(mon.fainted for mon in battle.team.values()) / 6.0
    vec[2] = sum(mon.fainted for mon in battle.opponent_team.values()) / 6.0
    vec[3] = bool(battle.force_switch)
    vec[4] = bool(battle.trapped)
    # Stage-0 fix (D13a): on gen1 placeholder turns the move blocks below are
    # deliberately zeroed. Sleep/freeze turns at least carried a status bit;
    # recharge and partial trap carried NOTHING (battle.trapped stays False on
    # nearly all of them, 1,262/1,273 measured). This flag states outright
    # that the move slots are aliased to poke-env's re-based single action.
    vec[5] = _move_slots_aliased(battle, spec=spec)
    o = GLOBAL_DIM
    for i, mon in enumerate(list(battle.team.values())[:6]):
        _fill_mon(vec, o + i * MON_DIM, mon, theirs, ours, type_chart, spec=spec)
    o += 6 * MON_DIM
    if ours is not None:
        _fill_active(vec, o, ours, spec=spec)
        # ALIASING FIX. On a gen1 placeholder turn (active asleep/frozen/
        # partially trapped) Showdown replaces the move list with a single
        # `Fight`, and poke-env maps it to move-action slot 0 -- but these
        # blocks describe the four REAL moves, so the network would be taught
        # "slot-0 features X => take action 6" when action 6 means "stay in
        # with whatever gen1 forces". Same for Struggle/Recharge. Leave the
        # blocks zeroed: the `known` flags at 0 say the slots are inert;
        # vec[5] plus the SLP/FRZ and (fixed) MUST_RECHARGE bits in _fill_mon
        # / _fill_active say why, so the state stays fully described. (Before
        # the Stage-0 fix that last claim was FALSE for recharge and partial
        # trap — those turns encoded as all-zero move blocks with no cause.)
        if not _move_slots_aliased(battle, spec=spec):
            for i, move in enumerate(list(ours.moves.values())[:4]):
                _fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, move, theirs, type_chart, spec=spec)
    o += ACTIVE_DIM + 4 * MOVE_DIM
    for i, mon in enumerate(list(battle.opponent_team.values())[:6]):
        base = o + i * (MON_DIM + 1)
        vec[base] = 1.0  # revealed
        _fill_mon(vec, base + 1, mon, ours, theirs, type_chart, spec=spec)
    o += 6 * (MON_DIM + 1)
    if theirs is not None:
        _fill_active(vec, o, theirs, spec=spec)
        # Opponent blocks carry NO action, so unlike our own they are free to
        # be filled from the set prior. Revealed moves first at p=1.0, then the
        # most likely unrevealed candidates. This is the information Foul Play
        # determinizes over and that we were discarding as zeros.
        for i, (move, prob) in enumerate(_opponent_move_slots(theirs)):
            _fill_move(vec, o + ACTIVE_DIM + i * MOVE_DIM, move, ours, type_chart, prob, spec=spec)
    if _ENCODER_IDS:
        _fill_ids(vec, battle, ours, theirs, spec=spec)
    return vec


def _fill_ids(vec, battle, ours, theirs, spec: EncoderSpec = GEN1) -> None:
    """The 20-dim identity suffix at [OBS_DIM - ID_DIM:], each value id/256.0:
    [+0..5] own team species (switch-action order) | [+6..11] opponent species
    (reveal order, zero-padded) | [+12..15] own active's moves (move-action
    order; zeroed on aliased turns, matching the zeroed move blocks — slot i
    must never carry move i's identity on a turn where action 6+i does not
    mean move i) | [+16..19] opponent active's move slots (the id of whatever
    move fills the block: revealed at p=1.0 AND prior-filled — the block and
    its id must describe the same move). _opponent_move_slots is deterministic
    in the battle state, so calling it again here re-derives the identical
    slot assignment the block fill used."""
    o = OBS_DIM - ID_DIM
    for i, mon in enumerate(list(battle.team.values())[:6]):
        vec[o + i] = _species_id(mon.species, spec) / ID_SCALE
    for i, mon in enumerate(list(battle.opponent_team.values())[:6]):
        vec[o + 6 + i] = _species_id(mon.species, spec) / ID_SCALE
    if ours is not None and not _move_slots_aliased(battle, spec=spec):
        for i, move in enumerate(list(ours.moves.values())[:4]):
            vec[o + 12 + i] = _move_id(move, spec) / ID_SCALE
    if theirs is not None:
        for i, (move, _) in enumerate(_opponent_move_slots(theirs)):
            vec[o + 16 + i] = _move_id(move, spec) / ID_SCALE


@lru_cache(maxsize=1024)
def _species_id(species: str, spec: EncoderSpec = GEN1) -> int:
    """Pokedex number inside the spec's range (gen 1: 1..151) — the species
    embedding row index. 0 (= unknown) for anything outside it, including
    the negative nums poke-env's dex carries for CAP/custom entries."""
    entry = GenData.from_gen(spec.gen).pokedex.get(species)
    num = entry["num"] if entry else 0
    lo, hi = spec.species_num_range
    return num if lo <= num <= hi else 0


def _move_id(move, spec: EncoderSpec = GEN1) -> int:
    """Move number inside the spec's range (gen 1: 1..165) — the move
    embedding row index. 0 for synthetic/out-of-gen entries (recharge is
    num -3 in poke-env's table)."""
    num = move.entry.get("num", 0)
    lo, hi = spec.move_num_range
    return num if lo <= num <= hi else 0


def _move_slots_aliased(battle, spec: EncoderSpec = GEN1) -> bool:
    """True when the only legal move-action is one of poke-env's SPECIAL_MOVES
    (fight / struggle / recharge), so move slot i no longer means move i."""
    avail = getattr(battle, "available_moves", None)
    return bool(avail) and len(avail) == 1 and avail[0].id in spec.special_move_ids


# --- D25 opponent-action labels (configs/showdown_sp_actpred12m.yaml, B1/B2) --
#
# The label the auxiliary head predicts: WHICH ACTION the pool opponent chose on
# the same simultaneous decision our own action was taken at. Free in self-play
# — the opponent is a frozen snapshot of the agent itself — and free in compute:
# PoolPlayer.choose_move already computes the decision, and SingleAgentWrapper.
# step calls it INSIDE our step from `battle2` in its pre-resolution state.
#
# WHAT CROSSES THE SEAM IS AN IDENTITY, NOT THE INDEX (B2). The raw 10-way index
# is in the OPPONENT's own frame (0..5 = its team order, 6..9 = its move order),
# and both orders are per-battle random permutations we never observe. So the
# order's target is resolved to the encoder's OWN _species_id / _move_id, which
# is also what the observation's id suffix carries — one id convention, so the
# canonicaliser can match a label against the actor's own obs row and nothing
# can drift between the two.
#
# An np.array, never a tuple: a tuple hits gymnasium VectorEnv._add_info's
# object-array branch. Emitted ALWAYS (sentinel included) so the vector info
# array keeps a stable (N, 3) int32 shape across sub-envs.
OPP_CHOICE_DIM = 3
OPP_CHOICE_PRESENT = 1  # flags bit 0: a real decision was made this step
OPP_CHOICE_ALIASED = 2  # flags bit 1: gen-1 re-based the opponent's move list
_OPP_CHOICE_NONE = (-1, -1, 0)


def _order_identity(order, battle) -> tuple[int, int, int]:
    """(kind, id, flags) for the opponent's BattleOrder — kind 0 switch, 1 move.

    Ids come from the encoder's own tables, so `_move_id` maps gen-1's
    placeholder moves (fight, recharge — no `num` in poke-env's table) to 0,
    which the canonicaliser reads as OTHER_MOVE. Struggle is a real num (165)
    and lands in OTHER_MOVE by the slot lookup failing instead, which is the
    same path any unslotted move takes.
    """
    flags = OPP_CHOICE_PRESENT | (
        OPP_CHOICE_ALIASED if _move_slots_aliased(battle) else 0
    )
    target = getattr(order, "order", None)
    if isinstance(target, Move):
        return (1, _move_id(target), flags)
    if isinstance(target, Pokemon):
        return (0, _species_id(target.species), flags)
    return _OPP_CHOICE_NONE  # a Default/Forfeit order names no entity


# --- Privileged (asymmetric-critic) block — D18, DESIGN §12 ----------------
#
# The opponent seat's TRUE own-side state, for widening the CRITIC's input
# during self-play training (never the actor's, never the obs space — the
# Baisero & Amato V(h,s) construction requires actor-obs ‖ privileged, and
# the "no OBS_DIM change" landmine requires the obs space untouched).
#
# Defined as a SLICE of the opponent seat's own embed_battle encoding rather
# than a new fill path: seat B's own-side blocks are computed by exactly the
# code that computes ours, so the privileged features carry bit-identical
# semantics (aliasing rule, set-free own moves, id suffix) with zero new
# encoder code to drift. The cost is encoding B's full vector and discarding
# its opponent-side half — accepted; the collection loop is I/O-dominated.
#
# Layout: 6 own-mon blocks | own-active extras | own-active's 4 move blocks
# (= embed_battle[GLOBAL_DIM : opp_mon_off], 398 dims at v2) | ids flag only:
# 6 own species ids + 4 own move ids (10 dims).
PRIV_ID_DIM = 10 if _ENCODER_IDS else 0
_PRIV_OWN_END = GLOBAL_DIM + 6 * MON_DIM + ACTIVE_DIM + 4 * MOVE_DIM
PRIV_DIM = (_PRIV_OWN_END - GLOBAL_DIM) + PRIV_ID_DIM


def privileged_block(vec: np.ndarray) -> np.ndarray:
    """The own-side slice of an embed_battle vector — call on the OPPONENT
    seat's encoding to get the privileged block for our critic. Returns a
    copy (the source vector is reused by the caller's encode path)."""
    own = vec[GLOBAL_DIM:_PRIV_OWN_END]
    if not _ENCODER_IDS:
        return own.copy()
    o = OBS_DIM - ID_DIM
    return np.concatenate([own, vec[o : o + 6], vec[o + 12 : o + 16]])


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


# --- Rung 1 (SIGNAL): Huang & Lee's 5-term zero-sum event shaping ----------
#
# Constants are metagrok `expts/01.json` VERBATIM (yuzeh/metagrok, MIT;
# local clone at ../metagrok) — they are absent from the paper. Attribution
# rule is `metagrok/pkmn/reward_shaper.py::NewRewardShaper` with
# zero_sum=True: a protocol line names one side's Pokemon
# ("|faint|p1a: Snorlax"); the named seat receives w and the other seat
# exactly -w. The four dash-tags are all in poke-env's MESSAGES_TO_IGNORE,
# so `battle._replay_data` (appended BEFORE the ignore filter) is the only
# place they survive; |faint| is not ignored but is read from the same log
# to keep ONE code path and one attribution rule
# (docs/prior_work/HISTORY_FEATURES_DESIGN.md).
#
# The |-fail| quirk is reproduced on purpose: Showdown names the Pokemon the
# failed action was AIMED AT, so our status move failing against an already-
# statused foe pays US +w. Verbatim fidelity to the one verified recipe is
# the point of Rung 1; the term stays exactly zero-sum so it cannot be
# farmed in mirror play (S6 tracks the rate; correcting it is a follow-up
# only if the arm credits).
_HL_WEIGHTS = {
    "faint": -0.0125,
    "-fail": -0.005,
    "-supereffective": -0.0025,
    "-resisted": 0.0025,
    "-immune": 0.005,
}


def hl_event_sum(events, who: str, start: int = 0) -> float:
    """Signed H&L event sum over `events[start:]` from seat `who`'s view
    (`who` in {"p1", "p2"}). Entries are poke-env split messages
    ["", tag, "p1a: Snorlax", ...]; entries shorter than 3 fields
    (["", "tie"], ["", "win", name]) are skipped. Antisymmetry is EXACT in
    IEEE 754 — negation and addition are sign-symmetric, so the p2 sum over
    the same events is bit-for-bit the negated p1 sum. The R0-2 gates
    (offline tape test + live smoke) assert that rather than argue it."""
    total = 0.0
    for entry in events[start:]:
        if len(entry) < 3:
            continue
        w = _HL_WEIGHTS.get(entry[1])
        if w is not None:
            total += w if entry[2].startswith(who) else -w
    return total


# --- Mask-desync recovery (2026-08-18, after D29r lane s90) ----------------
#
# poke-env's request state lives on its websocket listener thread
# (`parse_request` clears `_available_switches` before repopulating); the
# main thread's strict `action_to_order`/`order_to_action` re-reads
# `valid_orders` at conversion time. A re-request landing in that window
# (e.g. `[Unavailable choice]`/`[Invalid choice]` near gen-1 stall turns)
# makes a mask-legal action invalid at conversion — observed once in ~400M
# cumulative steps, and it killed a 50M lane at 70%. The exception must be
# absorbed HERE, at the conversion site, and nowhere shallower:
# `PokeEnv.step` flips `agent*_to_move` BEFORE converting, so an exception
# escaping `step` leaves the state machine half-mutated and any retry
# deadlocks in the timeout-less `battle_queue.race_get`.
#
# The recovery is poke-env's own non-strict fallback (`Player.
# choose_random_singles_move`, poke_env/player/player.py — one random draw
# from `valid_orders`, `choose_default_move()` if empty; note it consumes
# one draw from the global `random` stream that seeding.py seeds — harmless
# after construction, when usernames have already been derived). The mask
# contract stays LOUD: every recovery warns and counts, a second desync in
# the same battle raises, and more than _MASK_DESYNC_CAP recoveries inside
# a rolling _MASK_DESYNC_WINDOW of env steps raises — a systemic mask bug
# (encoder change, poke-env bump) fires on >=1e-3 of steps and dies within
# seconds, while the benign race (~2.5e-9/step observed) never trips it at
# any horizon. All state is module-level: per PROCESS (one lane = one
# process), not per instance — `num_envs: 8` must not multiply the cap.

_MASK_DESYNC_WINDOW = 100_000  # env steps
_MASK_DESYNC_CAP = 3  # recoveries allowed inside one window

_mask_desync_total = 0
_mask_desync_steps: "deque[int]" = deque()
_mask_desync_battles: set = set()
_env_step_counter = 0


class MaskDesyncCapExceeded(RuntimeError):
    """Systemic mask/valid-orders divergence: recovery budget exhausted."""


def mask_desync_total() -> int:
    """Lifetime recovered-desync count for this process (0 = clean run).
    Eval scripts surface it in their reports; any nonzero value on a locked
    number is a disclosure item."""
    return _mask_desync_total


def _reset_mask_desync_state() -> None:
    """Test hook: module-level counters would otherwise leak across cases."""
    global _mask_desync_total, _env_step_counter
    _mask_desync_total = 0
    _env_step_counter = 0
    _mask_desync_steps.clear()
    _mask_desync_battles.clear()


def _recover_mask_desync(battle, exc: ValueError):
    """One legal order in place of a raced one — loud, counted, capped."""
    global _mask_desync_total
    tag = getattr(battle, "battle_tag", "<unknown>")
    if tag in _mask_desync_battles:
        # One race in a battle is a race; two is a state-machine bug.
        raise MaskDesyncCapExceeded(
            f"second mask desync in {tag}: {exc}"
        ) from exc
    _mask_desync_battles.add(tag)
    _mask_desync_total += 1
    _mask_desync_steps.append(_env_step_counter)
    while (
        _mask_desync_steps
        and _env_step_counter - _mask_desync_steps[0] > _MASK_DESYNC_WINDOW
    ):
        _mask_desync_steps.popleft()
    if len(_mask_desync_steps) > _MASK_DESYNC_CAP:
        raise MaskDesyncCapExceeded(
            f"{len(_mask_desync_steps)} mask desyncs within "
            f"{_MASK_DESYNC_WINDOW} env steps (cap {_MASK_DESYNC_CAP}), "
            f"latest in {tag}: {exc}"
        ) from exc
    logger = getattr(battle, "logger", None) or logging.getLogger(__name__)
    logger.warning(
        "mask desync #%d in %s turn %s — recovering with a random legal "
        "order: %s",
        _mask_desync_total,
        tag,
        getattr(battle, "turn", "?"),
        exc,
    )
    return Player.choose_random_singles_move(battle)


class ShowdownSingles(SinglesEnv):
    """The two-seat poke-env env: encoder + reward, no opponent knowledge.

    `hl_shaping` (0.0 = off) adds Huang & Lee's NON-CANCELLED zero-sum event
    shaping (Rung 1 treatment; constants and rule above): each of the five
    protocol events pays ±hl_shaping*w the step it is consumed, attributed
    per seat from `battle._replay_data` behind a per-battle cursor. Unlike
    `faint_shaping` below it is a genuine change to the objective — no
    telescoping, no policy invariance. Its safety argument is symmetry, not
    cancellation: in mirror self-play both seats run the identical rule and
    every +delta harvested hands -delta to a copy of yourself. The two
    levers are independent and mutually exclusive in practice (Arm B is
    closed; no ratified config sets both).

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
        hl_shaping: float = 0.0,
        discard_seat2_obs: bool = False,
        **kwargs,
    ):
        super().__init__(battle_format=battle_format, **kwargs)
        # THROUGHPUT_SPEC Stage 1. PokeEnv.step encodes BOTH seats' battles,
        # and under SingleAgentWrapper seat 2's observation is thrown away
        # unread -- the wrapper returns only seat 1's and asks the opponent
        # for a move via `opponent.choose_move(battle2)`, which does its OWN
        # encode. Encoding is 133 us/decision of a ~1850 us vector step (E3),
        # so the discarded half is pure waste.
        # OFF BY DEFAULT, and that is the whole safety argument:
        # ShowdownSingles is a real two-seat PettingZoo env (16 test sites
        # construct it directly), and zeroing seat 2 unconditionally would
        # make it silently lie. Only ShowdownEnv -- which is definitionally
        # single-agent -- turns it on.
        self._discard_seat2_obs = discard_seat2_obs
        self._seat2_zeros = np.zeros(OBS_DIM, dtype=np.float32)
        self._type_chart = GenData.from_format(battle_format).type_chart
        self.faint_shaping = faint_shaping
        self.hl_shaping = hl_shaping
        # Next unconsumed index into each battle's _replay_data, keyed by the
        # battle OBJECT for the same reason as _faint_potential below (the
        # two seats share a battle_tag). Advanced to len(_replay_data) on
        # every calc_reward call, so each event is consumed exactly once per
        # seat no matter how the wait pump batches steps; cleared at reset.
        self._event_cursor: dict[object, int] = {}
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
        # Potentials and cursors are per-battle and must not survive into
        # the next one.
        self._faint_potential.clear()
        self._event_cursor.clear()
        return super().reset(seed=seed, options=options)

    # Mask-desync interception (see _recover_mask_desync above). These are
    # instance-attribute lookups at every in-poke-env conversion site —
    # both seats in PokeEnv.step and SingleAgentWrapper's opponent-order
    # conversion — so overriding here covers all of them with one path.
    # strict=False callers never raise and pass straight through.

    @staticmethod
    def action_to_order(action, battle, fake: bool = False, strict: bool = True):
        try:
            return SinglesEnv.action_to_order(action, battle, fake=fake, strict=strict)
        except ValueError as exc:
            return _recover_mask_desync(battle, exc)

    @staticmethod
    def order_to_action(order, battle, fake: bool = False, strict: bool = True):
        try:
            return SinglesEnv.order_to_action(order, battle, fake=fake, strict=strict)
        except ValueError as exc:
            fallback = _recover_mask_desync(battle, exc)
            # The fallback is drawn from the CURRENT valid_orders, so its
            # conversion should hold; strict=False guards the residual race
            # (poke-env then maps it to its own default action code).
            return SinglesEnv.order_to_action(
                fallback, battle, fake=fake, strict=False
            )

    def calc_reward(self, battle) -> float:
        # Called once per step; battle.won/lost are None until the server
        # decides the game, so the outcome term is nonzero exactly once, at
        # the end.
        outcome = 1.0 if battle.won else -1.0 if battle.lost else 0.0
        if not self.faint_shaping and not self.hl_shaping:
            # Bit-for-bit the pre-shaping reward, and the only path any
            # control config takes. Also the reason nothing below needs to
            # tolerate the reward-only stub battles the offline tests build.
            return outcome
        reward = outcome
        if self.hl_shaping:
            # The terminal frame is parsed before the terminal calc_reward
            # runs (battle_queue.race_get returns post-parse), so a deciding
            # |faint| is already in _replay_data here — R0-2(b) proves it.
            events = battle._replay_data
            start = self._event_cursor.get(battle, 0)
            reward += self.hl_shaping * hl_event_sum(events, battle.player_role, start)
            self._event_cursor[battle] = len(events)
        if not self.faint_shaping:
            return reward
        previous = self._faint_potential.pop(battle, 0.0)
        if battle.finished:
            # Phi(terminal) := 0, so the transition INTO it emits -Phi(s),
            # cancelling everything the episode accumulated. Note this fires
            # on `finished` — a decided game — and never on a truncation,
            # where the episode continues and the potential must be carried
            # (this env remaps every decided finish to terminal, so the two
            # cannot be confused, but the condition is written on the game's
            # state and not on the flag either way).
            return reward - previous
        potential = self.faint_shaping * (
            sum(mon.fainted for mon in battle.opponent_team.values())
            - sum(mon.fainted for mon in battle.team.values())
        )
        self._faint_potential[battle] = potential
        return reward + potential - previous

    def embed_battle(self, battle) -> np.ndarray:
        # Identity, not equality: the two seats share a battle_tag, and
        # `battle2` is seat 2's own object (the same reason _faint_potential
        # keys by object). Seat 1 never takes this branch, so its encoding is
        # bitwise unchanged -- asserted in tests, not assumed.
        if self._discard_seat2_obs and battle is self.battle2:
            return self._seat2_zeros
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
    chimera. Assignments are keyed by battle tag (Stage 2): the old single
    latch assumed one battle at a time, and under K interleaved battles it
    re-drew the sub-player on every alternation, silently destroying the
    per-battle boundary (THROUGHPUT_SPEC risk table; G6). Finished battles
    are swept from the map when a new one is assigned, which bounds it at
    the in-flight count. Weights are normalized at construction; sampling
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
        # battle_tag -> (battle, assigned sub-player). The battle object
        # rides along so the sweep can test `finished` on the real thing —
        # an entry may only be dropped once its battle cannot come back.
        self._by_tag: dict[str, tuple[object, Player]] = {}

    def choose_move(self, battle):
        entry = self._by_tag.get(battle.battle_tag)
        if entry is None:
            for tag, (done, _) in list(self._by_tag.items()):
                if getattr(done, "finished", False):
                    del self._by_tag[tag]
            entry = (
                battle,
                self._players[self._rng.choices(self._names, weights=self._weights)[0]],
            )
            self._by_tag[battle.battle_tag] = entry
        return entry[1].choose_move(battle)


class PoolPlayer(Player):
    """Seat-2 adapter driving battles from the shared SnapshotPool
    (milestone 3): each NEW battle draws one frozen snapshot via
    pool.select() — the per-episode swap boundary the pool contract pins —
    and that member plays the battle to the end. Assignments are keyed by
    battle tag (Stage 2): the old single latch assumed one battle at a
    time, and under K interleaved battles it re-selected per DECISION,
    destroying the per-episode swap boundary AND crediting outcomes to the
    wrong member — PFSP corruption with no metric that looks wrong
    (THROUGHPUT_SPEC risk table; G6a). The sync path (one PoolPlayer per
    sub-env, one battle at a time) holds at most one live entry, so its
    call order and rng consumption are unchanged. All instances wrap the
    ONE pool object that arrives through the caller-kwargs identity seam
    (rl/envs/make.py).

    choose_move is SYNC on purpose: SingleAgentWrapper.step calls it on the
    caller thread and asserts the result is not awaitable. SeamPlayer
    (rl/collect.py) is the precedent for the encode/mask/convert trio only,
    NOT for its async signature. Battle tracking uses our own attributes,
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
        # battle_tag -> (battle, member, push id). Entries leave through
        # report_outcome (the sync path's terminal step, or the async
        # collector's finalize); the finished-sweep on new-tag assignment is
        # the backstop for battles that end without a report.
        self._by_tag: dict[str, tuple[object, Any, int]] = {}
        # D25: the identity of the action this seat chose on the CURRENT inner
        # step, or the sentinel. Read by ShowdownEnv.step; see clear_choice.
        # A single latch is correct ONLY on the sync one-battle path; the
        # async collector reads the per-tag record below instead.
        self._choice = _OPP_CHOICE_NONE
        # Stage 2 label capture (off unless the collector opts in): every
        # decision's identity keyed (battle_tag, turn, nth-decision-this-
        # turn), so the learner's rows can be joined to the opponent's
        # simultaneous choices after the fact — the async replacement for
        # ShowdownEnv.step reading the latch synchronously.
        self._record_choices = False
        self._choices: dict[str, dict[tuple[int, int], tuple[int, int, int]]] = {}
        self._turn_counts: dict[str, dict[int, int]] = {}

    def take_member(self) -> int:
        """Push id of the member playing the sync path's single live battle
        (-1 before the first selection) — ShowdownEnv.step's D25 read."""
        if len(self._by_tag) == 1:
            return next(iter(self._by_tag.values()))[2]
        return -1

    def clear_choice(self) -> None:
        """Reset to the sentinel — called before EVERY inner env.step (B2).

        A `battle2.wait` turn issues a DefaultBattleOrder without ever calling
        choose_move, so without this the previous turn's label would silently
        be re-emitted on a step where this seat made no decision at all."""
        self._choice = _OPP_CHOICE_NONE

    def take_choice(self) -> tuple[int, int, int]:
        return self._choice

    def seed_rng(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def record_choices(self, on: bool = True) -> None:
        """Opt in to per-(tag, turn, index) choice capture — the async
        collector's label path. Off by default: the sync path reads the
        latch synchronously and must not accumulate a record nobody pops."""
        self._record_choices = on

    def take_choices(self, battle_tag: str) -> dict[tuple[int, int], tuple[int, int, int]]:
        """Pop and return one battle's recorded choices (empty if none)."""
        self._turn_counts.pop(battle_tag, None)
        return self._choices.pop(battle_tag, {})

    def report_outcome(self, outcome: int, battle_tag: str | None = None) -> None:
        """Learner-perspective outcome of the battle that just finished,
        credited to the member that played it — the pool's PFSP stats feed.
        The sync caller (ShowdownEnv.step, at the terminal step and always
        before the NEXT battle's first choose_move can re-select) passes no
        tag and resolves to its single live battle; the async collector
        names the battle. Popping the entry here is what keeps the map
        bounded on the sync path."""
        if battle_tag is None:
            if not self._by_tag:
                return
            battle_tag = next(iter(self._by_tag))
        entry = self._by_tag.pop(battle_tag, None)
        if entry is not None:
            self._pool.report(entry[1], outcome)

    def choose_move(self, battle):
        # Wrapper contract: wait states never reach the opponent
        # (SingleAgentWrapper.step's battle2.wait bypass). If one ever did,
        # the forward below would advance the member's generator on a
        # decision poke-env then discards — the seat-2 twin of
        # ShowdownEnv.step's discarded-action assert.
        assert not battle.wait, "wait state reached the pool opponent"
        entry = self._by_tag.get(battle.battle_tag)
        if entry is None:
            for tag, (done, _, _) in list(self._by_tag.items()):
                if getattr(done, "finished", False):
                    del self._by_tag[tag]
                    self._choices.pop(tag, None)
                    self._turn_counts.pop(tag, None)
            member = self._pool.select(self._rng)
            entry = (battle, member, self._pool.member_id(member))
            self._by_tag[battle.battle_tag] = entry
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        action = entry[1].move(obs, mask, self._rng)
        # strict, with counted recovery: an out-of-mask action raises unless
        # it is the listener-thread request race (SeamPlayer precedent for
        # the raise; _recover_mask_desync for why the race is survivable).
        try:
            order = SinglesEnv.action_to_order(np.int64(action), battle)
        except ValueError as exc:
            # Drop the label: a fallback order scored against the stale
            # buffered frame could flip the aux/illegal_label_frac == 0 and
            # frame_collision_frac == 0 hard gates, and canonicalise's
            # policy is drop, never zero-fill.
            self._choice = _OPP_CHOICE_NONE
            self._record_choice(battle, _OPP_CHOICE_NONE)
            return _recover_mask_desync(battle, exc)
        # D25 (B1/B2): record the chosen action's IDENTITY off the SAME
        # decision, before it becomes a protocol message. Costs no inference —
        # `action` was computed above regardless — and is unconditional
        # because the label carries no cost worth branching on.
        self._choice = _order_identity(order, battle)
        self._record_choice(battle, self._choice)
        return order

    def _record_choice(self, battle, identity: tuple[int, int, int]) -> None:
        """Stage 2 label capture: one record per decision, keyed by (turn,
        nth-decision-this-turn). The learner keys its own rows the same way,
        and the join reproduces the sync path's semantics exactly: first
        decisions of a turn pair (the simultaneous move choice), a forced
        replacement pairs only when BOTH seats replaced that turn, and any
        unmatched key resolves to the sentinel — which is what the sync
        path's clear-before-every-inner-step gives those rows today."""
        if not self._record_choices:
            return
        counts = self._turn_counts.setdefault(battle.battle_tag, {})
        idx = counts.get(battle.turn, 0)
        counts[battle.turn] = idx + 1
        self._choices.setdefault(battle.battle_tag, {})[(battle.turn, idx)] = identity


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
        hl_shaping: float = 0.0,
        privileged: bool = False,
        opp_action: bool = False,
        start_timer_on_battle_start: bool = True,
    ):
        # save_replays (False | True | directory) is poke-env's native replay
        # dump: each finished battle is written as a Showdown replay HTML
        # (the official animated viewer; needs internet to load its JS).
        # Both seats save, so every battle yields two near-identical files.
        self.render_mode = render_mode
        # THE ORPHANED-ROOM DEADLOCK (docs/landmines.md, 2026-08-31): a room
        # that never resolves never returns its slot to poke-env's
        # `_battle_count_queue`, and the next `|init|battle` then blocks
        # FOREVER at player.py:221 inside the single message-handling
        # coroutine -- the lane sits ALIVE at ZERO CPU with no crash. Training
        # is the exposed path because PokeEnv hardcodes
        # `max_concurrent_battles=1` as a LITERAL (poke_env/environment/env.py
        # 273/292/355/375), so ONE leaked room is fatal and no slack is
        # forwardable. `/timer on` is the only fix available here: it attacks
        # the cause, because Showdown's `nextRequest`/`nextTick`/`checkActivity`
        # all return early on `!this.timerRequesters.size`
        # (showdown/server/room-battle.ts:320/345/410), so WITHOUT a timer
        # requester a disconnected or dead opponent NEVER times out and the
        # room NEVER ends. Cost of not having it: 190,776 + 170,680 re-run
        # steps, a 5.2 h freeze and two dead R4S66 attempts.
        # Wire-visible, hence a knob: these are CHALLENGE battles, so the
        # server allows 300 s/turn + 60 s grace (STARTING_TIME_CHALLENGE /
        # MAX_TURN_TIME_CHALLENGE) against a measured max `time/update_sec` of
        # 15.3 s on the 50M batch lanes -- a 20x margin, but the argument is
        # ops, not a claim, and setting this False restores the pre-fix wire.
        inner = ShowdownSingles(
            battle_format=battle_format,
            save_replays=save_replays,
            faint_shaping=faint_shaping,
            hl_shaping=hl_shaping,
            start_timer_on_battle_start=start_timer_on_battle_start,
            # Seat 2's observation is discarded by SingleAgentWrapper before
            # anything reads it; skipping the encode is Stage 1 of
            # THROUGHPUT_SPEC. Safe HERE and only here -- see ShowdownSingles.
            # The privileged block (D18) is unaffected: _emit_privileged calls
            # the module-level embed_battle on battle2 directly, not this
            # method.
            discard_seat2_obs=True,
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
        # D18: emit info["privileged"] — the OPPONENT seat's own-side block —
        # at every decision point. Info-dict only, never the obs space; the
        # flag defaults off so every existing config's env is bit-identical.
        self._privileged = privileged
        # D25: emit info["opp_choice"] — the pool opponent's chosen action
        # identity at this step's simultaneous decision. INERT without a
        # PoolPlayer, which is what makes it safe at every EVAL site: cfg.
        # env_kwargs flows through make_eval_env to score_ladder.py and
        # eval_checkpoint.py, where the opponent is the fixed anchor and there
        # is no self-play label to capture (B15, R0-2b).
        self._opp_action = opp_action and self._pool_player is not None
        # Wait-states pumped inside step() and never returned (see below);
        # exposed so the regression test can prove the pump path executes.
        self.waits_absorbed = 0

    def _emit_privileged(self, info: dict) -> None:
        """info["privileged"] from seat 2's battle object. Called at exactly
        the points that emit info["action_mask"], so a consumer can rely on
        the pair arriving together. Seat 2's battle exists whenever a
        decision is returned (reset asserts agent1_to_move; the wait pump
        never returns mid-wait), so a missing battle is a wiring bug."""
        if not self._privileged:
            return
        battle2 = self._env.env.battle2
        assert battle2 is not None, "privileged emission before seat 2's battle exists"
        info["privileged"] = privileged_block(
            embed_battle(battle2, self._env.env._type_chart)
        )

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
        self._emit_privileged(info)
        return obs["observation"], info

    def step(self, action):
        # The mask-desync rate window is denominated in env steps; one
        # module-global counter across this process's instances (train env
        # sub-envs + eval env alike — the cap is per process by design).
        global _env_step_counter
        _env_step_counter += 1
        poke = self._env.env
        # PokeEnv.step converts and sends agent1's action ONLY when
        # agent1_to_move — otherwise it silently discards the action and
        # still returns a full transition. Fail loudly instead: a discarded
        # action entering the buffer is a phantom (s, a) pair.
        assert poke.agent1_to_move, "action would be silently discarded by poke-env"
        if self._opp_action:
            self._pool_player.clear_choice()
        # np.int64, not int: poke-env's action_to_order calls action.item().
        obs, reward, terminated, truncated, info = self._env.step(np.int64(action))
        # D25 (B3): TRANSITION-TIME info. The opponent's action is produced
        # DURING this call and belongs to row t — like info["outcome"], and
        # unlike info["action_mask"] / info["privileged"], which describe the
        # SUCCESSOR state and are carried forward by the train loop. So: no
        # carry variable, no next_* twin, and no reset merge (reset has no
        # preceding turn and emits no label).
        #
        # Read after the FIRST inner step only. The wait pump's later opponent
        # choices are forced post-faint replacements, not the simultaneous
        # decision, and are discarded.
        choice = self._pool_player.take_choice() if self._opp_action else None
        member = self._pool_player.take_member() if self._opp_action else -1
        total_reward = float(reward)
        # Absorb wait states (our seat has nothing to choose — e.g. the
        # opponent is replacing a fainted mon; measured 6.4% of raw steps vs
        # max_power). As learner rows they carry a placeholder one-legal
        # mask and an ignored action: zero policy gradient, but they skew
        # advantage normalization, the entropy metric, and episode lengths.
        # The pump's dummy action is discarded by the same mechanism the
        # assert above guards.
        while not (terminated or truncated) and not poke.agent1_to_move:
            if self._opp_action:
                self._pool_player.clear_choice()
            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))
            total_reward += float(reward)
            self.waits_absorbed += 1
        info["action_mask"] = obs["action_mask"].astype(bool)
        self._emit_privileged(info)
        if self._opp_action:
            info["opp_choice"] = np.array(choice, dtype=np.int32)
            # ALONGSIDE the three-field seam, deliberately not inside it (B2
            # pins the array at three fields): which pool member generated this
            # label. §6's build item — the manipulation check's oracle floor is
            # not specific unless A3 is evaluated on the member that actually
            # played, and the training loss never reads this.
            info["opp_member"] = np.int32(member)
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

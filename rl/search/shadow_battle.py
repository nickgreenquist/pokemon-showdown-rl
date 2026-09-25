"""ShadowBattle: engine State -> the exact attribute surface embed_battle
reads. The design's no-second-encoder invariant (ch3_search_design_r2.md
§2): a leaf is encoded by THE SAME `rl/envs/showdown.embed_battle` as live
play, fed a duck-typed mirror of the poke-env Battle — so FG-6 tests one
field map, never two encoders.

What the engine cannot supply, and where it comes from:
- base_stats/types per species: poke-env's static gen-1 pokedex (cached).
- turn: carried from the root battle (+1 at a depth-1 leaf).
- Move metadata (base_power/accuracy/type/category/priority/entry): a
  cached poke-env Move per id, wrapped in a per-leaf _MoveView that
  overrides current_pp with the engine's — the cache is shared and never
  mutated.
- effects: reverse of bridge.EFFECT_VOLATILE_MAP on the side's volatile
  set (active only; gen1 bench carries no volatiles).
- KNOWN NON-PARITY FAMILIES (FG-6's budget, measured not asserted):
  opponent HP quantisation (engine exact vs battle1's /100 fraction), PP
  (poke-env never decrements the opponent's), sleep-vs-Rest counter split
  (engine separates, poke-env conflates), preparing (engine models FLY/DIG
  as volatiles we do not map back), lightscreen (unobservable at the root).

det_blind (2026-09-10, docs/search_relook/DET_BLIND.md) — the INFORMATION
BOUNDARY option. Screen S1 measured that the as-is leaf encoding shifts the
critic by +0.0497 mean / 0.1254 sd against a median decision margin of
0.0277, because the determinizer's INVENTED opponent material (unrevealed
bench species, unrevealed movesets) is encoded AS IF REVEALED while the
critic only ever saw live encodings, where it is unknown. Passing a
`PublicView` of the ROOT battle re-imposes the live encoder's boundary on
the leaf: an opponent mon the root never saw is dropped from the shadow
team (its block stays the zeros the live encoder would emit) unless the
transition put it on the field, and the opponent active's move slots carry
only the root's revealed moves, leaving `_opponent_move_slots`' own
revealed-then-most-probable prior fill to complete them exactly as it does
on battle1. `view=None` (the default) is the pre-2026-09-10 code path,
byte-for-byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from poke_env.battle.effect import Effect
from poke_env.battle.move import Move as PEMove
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status

from rl.search.volatiles import EFFECT_VOLATILE_MAP  # poke_engine-free (2026-09-23)

_VOLATILE_EFFECT_MAP = {v: k for k, v in EFFECT_VOLATILE_MAP.items()}
# Keys are the ENGINE's full status names (bridge._STATUS_MAP values;
# probed+pinned 2026-08-22 — the 3-letter forms panic in the engine).
_STATUS_ENUM = {
    "burn": Status.BRN, "paralyze": Status.PAR, "poison": Status.PSN,
    "toxic": Status.TOX, "sleep": Status.SLP, "freeze": Status.FRZ,
}


@lru_cache(maxsize=512)
def _cached_move(move_id: str) -> PEMove:
    return PEMove(move_id, gen=1)


@lru_cache(maxsize=256)
def _static_species(species: str) -> tuple[dict, tuple]:
    from poke_env.data import GenData

    entry = GenData.from_gen(1).pokedex[species]
    types = tuple(
        PokemonType.from_name(t) for t in entry["types"]
    )
    return dict(entry["baseStats"]), types


class _MoveView:
    """Cached poke-env Move + the engine's live PP. Read-only delegate; the
    shared cache is never mutated."""

    __slots__ = ("_base", "current_pp")

    def __init__(self, base: PEMove, current_pp: int):
        self._base = base
        self.current_pp = current_pp

    def __getattr__(self, name):
        return getattr(self._base, name)


class _Effects(dict):
    """effects mapping with Effect-like keys (only .name is read)."""


@dataclass(frozen=True, eq=False)
class PublicView:
    """What `embed_battle` on battle1 knew about the OPPONENT at the ROOT.

    Carried into the leaf encoding by the `det_blind` option so a leaf is
    encoded at the information boundary the live encoder would have there,
    not at the determinizer's. Fields hold poke-env's own conventions:
    lowercase species ids, poke-env move ids in REVEAL ORDER (which is the
    order `_opponent_move_slots` fills its p=1.0 slots in), and the live
    `current_pp` battle1 tracks for each revealed move.

    Our own side is fully observed in both encodings, so nothing about it is
    carried; this is an opponent-side object only.
    """

    revealed_species: frozenset
    revealed_moves: dict  # species -> tuple[move id, ...], reveal order
    revealed_pp: dict     # species -> {move id: battle1's current_pp}

    def plus_move(self, species: str, move_id: str) -> "PublicView":
        """The view a LEAF has after `species` used `move_id` in the
        transition. The live game names the move in the protocol, so it
        joins the revealed set — appended LAST, exactly as poke-env appends
        a newly seen move to `mon.moves` — and its PP ticks down by one,
        exactly as poke-env's `Move.use()` does.

        DECLARED APPROXIMATION: on the branches where the opponent's active
        fainted before it could act, the live game would reveal nothing.
        The engine's PP is not a usable signal for that (poke-engine emits
        DecrementPP only for low-PP moves — measured), and the column's
        action is the only thing the matrix layer knows, so those leaves
        over-reveal by one move slot. Named in DET_BLIND.md §5.
        """
        cur = self.revealed_moves.get(species, ())
        pp = dict(self.revealed_pp.get(species, {}))
        prev = pp.get(move_id, _cached_move(move_id).max_pp or 0)
        pp[move_id] = max(0, int(prev) - 1)
        return PublicView(
            self.revealed_species,
            dict(self.revealed_moves) | {
                species: cur if move_id in cur else cur + (move_id,)
            },
            dict(self.revealed_pp) | {species: pp},
        )


def public_view(battle: Any) -> PublicView:
    """The ROOT battle's opponent-side public view. battle1 only (FG-4):
    `opponent_team` holds exactly the mons the server has shown us and
    `mon.moves` exactly the moves they have used."""
    species, moves, pp = set(), {}, {}
    for mon in battle.opponent_team.values():
        sp = mon.species
        species.add(sp)
        items = list(mon.moves.items())[:4]
        moves[sp] = tuple(mid for mid, _ in items)
        pp[sp] = {mid: int(m.current_pp) for mid, m in items}
    return PublicView(frozenset(species), moves, pp)


def _mon_view(mon: Any, side: Any, is_active: bool,
              view: PublicView | None = None) -> SimpleNamespace:
    # the engine UPPERCASES ids on applied-state readback (measured); all
    # downstream consumers (pokedex, encoder id block) want lowercase
    species = mon.id.lower()
    base_stats, types = _static_species(species)
    status = _STATUS_ENUM.get(str(mon.status).lower())
    fainted = mon.hp <= 0
    # applied-state readback UPPERCASES volatiles too (measured 2026-08-22,
    # same family as the mon-id uppercasing) — without .lower() every leaf
    # silently lost its volatiles at the shadow boundary
    vols = {v.lower() for v in side.volatile_statuses} if is_active else set()
    effects = _Effects()
    for v in vols:
        eff_name = _VOLATILE_EFFECT_MAP.get(v)
        # REAL Effect members, not name-alikes: the encoder tests membership
        # with `Effect.X in mon.effects` (hash equality), and SimpleNamespace
        # keys are unhashable anyway (found by FG-6 on real volatile states —
        # the synthetic tests carried no volatiles).
        if eff_name is not None and eff_name in Effect.__members__:
            effects[Effect[eff_name]] = 1
    moves = {}
    if view is None:
        for em in mon.moves:
            if em.id.lower() == "none":
                continue
            mid = em.id.lower()
            moves[mid] = _MoveView(_cached_move(mid), em.pp)
    else:
        # det_blind: keep ONLY what battle1 had revealed (plus whatever the
        # transition revealed, appended by PublicView.plus_move), in reveal
        # order and at battle1's own PP. The remaining slots are left for
        # `_opponent_move_slots` to fill from the set prior — the same fill,
        # from the same table, that the live encoder runs. Iterating the
        # VIEW rather than the engine's move list is what preserves reveal
        # order: the determinizer completes a revealed BENCH mon from a
        # frozenset, so the engine's order is arbitrary for any mon that was
        # not the root's active.
        # PP comes from the VIEW, never the engine leaf: poke-env tracks the
        # opponent's PP and the engine does not model it faithfully (it emits
        # DecrementPP only for low-PP moves — measured 2026-09-10), so the
        # engine's value is not something the live encoder could ever show.
        live_pp = view.revealed_pp.get(species, {})
        for mid in view.revealed_moves.get(species, ()):
            if mid == "none":
                continue
            base = _cached_move(mid)
            moves[mid] = _MoveView(base, live_pp.get(mid, base.max_pp or 0))
    boosts = dict.fromkeys(
        ("accuracy", "atk", "def", "evasion", "spa", "spd", "spe"), 0
    )
    if is_active:
        boosts["atk"] = side.attack_boost
        boosts["def"] = side.defense_boost
        boosts["spa"] = side.special_attack_boost
        boosts["spd"] = side.special_defense_boost
        boosts["spe"] = side.speed_boost
        boosts["accuracy"] = side.accuracy_boost
        boosts["evasion"] = side.evasion_boost
    return SimpleNamespace(
        species=species,
        level=mon.level,
        current_hp_fraction=(mon.hp / mon.maxhp if mon.maxhp else 0.0),
        fainted=fainted,
        status=Status.FNT if fainted else status,
        status_counter=int(mon.sleep_turns or 0) + int(mon.rest_turns or 0),
        base_stats=base_stats,
        types=list(types),
        type_1=types[0],
        type_2=types[1] if len(types) > 1 else None,
        boosts=boosts,
        effects=effects,
        preparing=False,
        must_recharge="mustrecharge" in vols,
        moves=moves,
    )


def shadow_battle(
    state: Any, turn: int, view: PublicView | None = None
) -> SimpleNamespace:
    """Engine State -> embed_battle's attribute surface. Seat 1 = us.

    `view` (det_blind) is the ROOT battle's opponent-side `PublicView`; None
    keeps the pre-2026-09-10 path byte-for-byte. With a view, an opponent
    mon the root never saw is OMITTED from `opponent_team` unless it is the
    leaf's active — the live encoder zero-pads that block, and a mon that
    switched or was dragged in IS on the field, so the live encoder would
    know its species (never its moves, which stay unknown until used).
    """
    def side_views(side, view=None):
        active_i = int(str(side.active_index)[-1]) if not isinstance(
            side.active_index, int
        ) else side.active_index
        views, active = {}, None
        for i, mon in enumerate(side.pokemon):
            if mon.id.lower() == "none":
                continue  # the engine pads sides to 6 with filler mons
            if (
                view is not None
                and i != active_i
                and mon.id.lower() not in view.revealed_species
            ):
                continue  # det_blind: a bench mon only the determinizer knows
            v = _mon_view(mon, side, is_active=(i == active_i), view=view)
            views[f"shadow: {mon.id.lower()}"] = v
            if i == active_i:
                active = v
        return views, active

    # our own side is fully observed in the live encoding — no view, ever
    team, active = side_views(state.side_one)
    opp_team, opp_active = side_views(state.side_two, view)
    available = [
        m for m in (active.moves.values() if active else [])
        if m.current_pp > 0
    ]
    return SimpleNamespace(
        active_pokemon=active,
        opponent_active_pokemon=opp_active,
        team=team,
        opponent_team=opp_team,
        turn=turn,
        # gen1: force_switch iff our active fainted — true at faint LEAVES
        # too, which is the state family the critic actually trained on
        # (poke-env flags it before the replacement); measured by FG-6
        # (dim 3 was the whole non-exempt violation set on 40 battles).
        force_switch=bool(active is not None and active.fainted),
        trapped=False,
        available_moves=available,
    )

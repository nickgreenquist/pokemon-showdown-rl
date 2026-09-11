#!/usr/bin/env python
"""Gate **R1-E** — root-init parity for the engine-native write-side bridge.

`docs/search_relook/ENGINE_SEARCH_DESIGN.md` §3.2/§3.3. Phase 1 builds a bridge
that constructs a MID-BATTLE engine state from a poke-env public view plus one
determinization. R1-E is the independent check on that construction, and it is
the reason Phase 1 exists as a separate phase: a subtly wrong root makes every
downstream search number a number about a different game, and NOTHING else in
the pipeline would notice. That is not hypothetical — it is the shape of the
defect gate A-1a caught in the collector (a foe's revealed-move PP hard-coded to
1.0), which gate P-1 structurally could not see because P-1 fills the observable
state FROM poke-env and therefore shared the defect with its own reference.

WHAT THIS DECIDES, AND WHAT IT DOES NOT [read this before quoting a number].
R1-E is ONE-DIRECTIONAL, exactly as `scripts/engine_a1a.py` is. FAILING it
blocks the write side and names the field to fix. PASSING it licenses only
this: *at the root, on this corpus, the constructed state encodes and offers
actions like the real one, outside a named list of families*. It says nothing
about the TRANSITION (Phase 2's decision-level agreement read owns that),
nothing about leaves (a root residual is not a leaf residual —
`DET_BLIND.md` §5.3), nothing about whether depth-1 search pays (S3's cells
own that), and nothing about the 100M-lane state distribution until the fresh
harvest §3.2 requires has been run through it. A PASS is a licence to BUILD
PHASE 2, never a licence to quote a search number.

THREE LEGS, AND WHY LEG C IS THE LOAD-BEARING ONE.

  Leg A — OBSERVATION PARITY. Encode the constructed root; compare BITWISE
    against the harvested LIVE `row["obs"]`, the vector the policy actually
    acted on. Every differing dim must fall in a DECLARED family; an
    undeclared dim is a BUG, not a family (the rule
    `scripts/engine_p1_run.py:127-129` already enforces).

  Leg B — INTERNAL CONSISTENCY, disclosed as internal-only and NEVER as
    parity. There is no external oracle for the foe seat or for the
    transition at the root, so leg B checks (i) W-VALIDATE on the constructed
    bytes, (ii) transition invariants that follow from the chosen action
    alone, and (iii) — when the engine backend lands — one-turn agreement
    with the poke_engine path on the fields both can express.

  Leg C — MASK PARITY, the independent oracle, and the load-bearing leg.
    The design says in terms that obs parity CANNOT see `order`, the
    `forced()` set, PP>0 or fainted-ness, and that there is no harvested FOE
    observation against which to check the privileged block. Leg C compares
    `mask_for(constructed)` against the harvested `row["mask"]` on every
    non-aliased root. Target 100%; **below 99.5% is the design's hard stop.**
    `mask_for` here reads the CONSTRUCTED STATE ONLY — never
    `battle.available_moves`, never `battle.trapped`, never the harvested
    mask. Sharing an input with the reference is what made the first version
    of gate P-1 unfalsifiable (`scripts/engine_p1.py` docstring), and the
    same trap is available here.

TWO BACKENDS, ONE SEAM.

  `--backend poke_engine` (default) runs TODAY, in conda env
    `pokemon-showdown-rl`, against the EXISTING poke_engine construction:
    `battle_to_state(battle1, det)` + `shadow_battle(..., view=public_view())`.
    The `view` is the stand-in for the engine's own `revealed` tracker: it
    re-imposes the live encoder's information boundary, which is what
    `SideTracker::from_root` will do in Rust. This backend exists so the
    GATE'S OWN MACHINERY is measured before the thing it gates exists — a
    gate whose plumbing is first exercised on the artefact it is supposed to
    judge has no null.

  `--backend engine` is the Phase-1 target. It is ONE function,
    `_build_engine_root`, and it names the three Rust symbols it waits on.
    `root_reveals()` — the `RootReveal` payload — is implemented FOR REAL
    today, in Python, from battle1 only; it is backend-independent data.

STAND-IN FAMILIES. Some differences the poke_engine backend produces are
artefacts OF THE STAND-IN and not of any declared engine family — the shadow
hard-codes `trapped=False` and `preparing=False`, and it conflates move-sleep
with Rest-sleep. Those are declared here as `S-*` families and they are
DECLARED ON THE `poke_engine` BACKEND ONLY. On `--backend engine` they are
UNDECLARED, i.e. a FAIL. The gate therefore gets STRICTER when the real
surface lands, which is the direction a stand-in must fail in.

USAGE (offline: no server, no websocket, no battles; PUBLIC harvest only —
never `harvest_priv_*`, FG-4):

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
      python scripts/search_r1e_gate.py --limit 200

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
      python scripts/search_r1e_gate.py --all --out results/search_r1e
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rl.envs.encoder_spec import GEN1  # noqa: E402
from rl.envs.showdown import (  # noqa: E402
    ACTIVE_DIM,
    ENCODER_FINGERPRINT,
    GLOBAL_DIM,
    ID_DIM,
    MON_DIM,
    MOVE_DIM,
    OBS_DIM,
    embed_battle,
)

# ---------------------------------------------------------------------------
# Pinned constants
# ---------------------------------------------------------------------------

LANES = ("s62", "s63", "s64", "s65")
N_ACTIONS = 10

# The determinization key. Pinned here so a re-run reproduces the same dets;
# distinct from FG-6's 2000 + i and from the S1 screens' keys so nothing can
# accidentally read one run's dets as another's.
R1E_SEED_BASE = 7000

# Design §3.2's proposed bar, calibrated against the det_blind residual
# (0.945 dims/root, 47.5% bit-identical, DET_BLIND.md:274-275). Restated
# verbatim, in one place, so the pass rule cannot drift from the doc.
BAR_TOTAL_DIMS_PER_ROOT = 1.5
BAR_MIN_BITWISE_FRAC = 0.40
BAR_WHP_DIMS_PER_ROOT = 0.60
BAR_WHP_MAX_ABS = 0.01
BAR_LEG_C_HARD_STOP = 0.995  # below this is the design's HARD STOP
LEG_C_TARGET = 1.0

# Families that must contribute ZERO dims. "If they do not, the claim that
# they are free is false" (§3.2).
ZERO_DIM_FAMILIES = ("W-ORDER", "W-SEED", "W-DET", "W-REQ")


# ---------------------------------------------------------------------------
# Block layout — computed from rl.envs.showdown's own dims, never hard-coded.
# `tests/test_search_r1e_gate.py` cross-checks every one of the 828 dims
# against `scripts/engine_p1.py::describe_index`, which is an independently
# written classifier over the same constants.
# ---------------------------------------------------------------------------

_OWN_MON = GLOBAL_DIM
_OWN_ACTIVE = _OWN_MON + 6 * MON_DIM
_OWN_MOVES = _OWN_ACTIVE + ACTIVE_DIM
_OPP_MON = _OWN_MOVES + 4 * MOVE_DIM
_OPP_ACTIVE = _OPP_MON + 6 * (MON_DIM + 1)
_OPP_MOVES = _OPP_ACTIVE + ACTIVE_DIM
_IDS = OBS_DIM - ID_DIM

# Offsets INSIDE a block, read off the encoder's own fill order
# (`rl/envs/showdown.py::_fill_mon` / `_fill_active` / `_fill_move`).
_MON_HP = 0
_MON_FAINTED = 1
_MON_STATUS0 = 3
_MON_LEVEL = 9
_MON_BASE0 = 10
_MON_TYPE0 = 15
_MON_MATCHUP0 = 30  # matchup_out, matchup_in, speed_edge
_ACTIVE_BOOST0 = 0
_ACTIVE_VOL0 = 7
_ACTIVE_STATUS_COUNTER = 14
_ACTIVE_PREPARING = 15
_MOVE_KNOWN = 0
_MOVE_PP = 3
_GLOBAL_TURN = 0
_GLOBAL_FORCE_SWITCH = 3
_GLOBAL_TRAPPED = 4
_GLOBAL_ALIASED = 5


@dataclass(frozen=True)
class DimInfo:
    """Where a dim lives. `block` is the coarse name the R1-E report uses."""

    index: int
    block: str          # global | own_mon<i> | own_active | own_move<j> | ...
    field: str          # the encoder's own field name inside the block
    slot: int           # mon index / move index, -1 for global & actives
    side: str           # own | opp | global


def classify_dim(i: int) -> DimInfo:
    """One of the 828 dims -> (block, field, slot, side). Boundaries come from
    GLOBAL_DIM / MON_DIM / ACTIVE_DIM / MOVE_DIM / ID_DIM, so an encoder-width
    change moves this classifier with the encoder instead of silently
    mislabelling every dim."""
    if not 0 <= i < OBS_DIM:
        raise IndexError(f"dim {i} outside the {OBS_DIM}-wide observation")
    if i < GLOBAL_DIM:
        names = ("turn", "own_fainted", "opp_fainted", "force_switch",
                 "trapped", "aliased")
        return DimInfo(i, "global", names[i], -1, "global")
    if i < _OWN_ACTIVE:
        k, off = divmod(i - _OWN_MON, MON_DIM)
        return DimInfo(i, f"own_mon{k}", _mon_field(off), k, "own")
    if i < _OWN_MOVES:
        off = i - _OWN_ACTIVE
        return DimInfo(i, "own_active", _active_field(off), -1, "own")
    if i < _OPP_MON:
        j, off = divmod(i - _OWN_MOVES, MOVE_DIM)
        return DimInfo(i, f"own_move{j}", _move_field(off), j, "own")
    if i < _OPP_ACTIVE:
        k, off = divmod(i - _OPP_MON, MON_DIM + 1)
        if off == 0:
            return DimInfo(i, f"opp_mon{k}", "revealed", k, "opp")
        return DimInfo(i, f"opp_mon{k}", _mon_field(off - 1), k, "opp")
    if i < _OPP_MOVES:
        off = i - _OPP_ACTIVE
        return DimInfo(i, "opp_active", _active_field(off), -1, "opp")
    if i < _IDS:
        j, off = divmod(i - _OPP_MOVES, MOVE_DIM)
        return DimInfo(i, f"opp_move{j}", _move_field(off), j, "opp")
    off = i - _IDS
    if off < 6:
        return DimInfo(i, "ids", f"own_species[{off}]", off, "own")
    if off < 12:
        return DimInfo(i, "ids", f"opp_species[{off - 6}]", off - 6, "opp")
    if off < 16:
        return DimInfo(i, "ids", f"own_move[{off - 12}]", off - 12, "own")
    return DimInfo(i, "ids", f"opp_move[{off - 16}]", off - 16, "opp")


def _mon_field(off: int) -> str:
    if off == _MON_HP:
        return "hp"
    if off == _MON_FAINTED:
        return "fainted"
    if off == 2:
        return "is_active"
    if _MON_STATUS0 <= off < _MON_STATUS0 + 6:
        return f"status[{off - _MON_STATUS0}]"
    if off == _MON_LEVEL:
        return "level"
    if _MON_BASE0 <= off < _MON_BASE0 + 5:
        return f"base_stat[{off - _MON_BASE0}]"
    if _MON_TYPE0 <= off < _MON_TYPE0 + 15:
        return f"type[{off - _MON_TYPE0}]"
    return ("matchup_out", "matchup_in", "speed_edge")[off - _MON_MATCHUP0]


def _active_field(off: int) -> str:
    # Boost and volatile NAMES come from the encoder's own spec, not from an
    # index, so a spec reorder relabels this classifier with the encoder rather
    # than leaving it quietly naming the wrong stat.
    if off < _ACTIVE_VOL0:
        return f"boost[{GEN1.boost_keys[off]}]"
    if off < _ACTIVE_STATUS_COUNTER:
        return f"volatile[{GEN1.volatiles[off - _ACTIVE_VOL0].name}]"
    return "status_counter" if off == _ACTIVE_STATUS_COUNTER else "preparing"


def _move_field(off: int) -> str:
    names = ("known", "base_power", "accuracy", "pp", "multiplier",
             "physical", "status", "priority")
    if off < len(names):
        return names[off]
    if off < len(names) + 15:
        return f"type[{off - len(names)}]"
    return f"effect[{off - len(names) - 15}]"


# ---------------------------------------------------------------------------
# Declared families (design Appendix A) and their OBSERVATION footprint.
#
# The single most useful thing this table records is which declared families
# the OBSERVATION CANNOT SEE AT ALL. Leg A is blind to every one of them, and
# that blindness is precisely why leg C is load-bearing.
# ---------------------------------------------------------------------------

FAMILY_DOC: dict[str, dict[str, Any]] = {
    "W-HP": {
        "fields": "opponent P_HP",
        "class": "grain",
        "obs_visible": True,
        "obs_dims": "opp_mon<k>.hp for revealed k",
        "why": "the engine carries exact HP; battle1 only the server's /100 "
               "public fraction, whose inverse is an interval of width ~maxhp/100",
        "seen_by": "leg A",
    },
    "W-STATS": {
        "fields": "opponent P_STATS",
        "class": "determinized",
        "obs_visible": False,
        "obs_dims": "-- the encoder reads BASE stats and level, never the "
                    "computed stat block",
        "why": "max-DV model, exact on 94.85% of realized stats; the team bank's "
               "min_atk variant is unmodelled",
        "seen_by": "NEITHER leg; it reaches the search only through damage",
    },
    "W-ACTIVESTATS": {
        "fields": "A_STATS",
        "class": "path-dependent",
        "obs_visible": False,
        "obs_dims": "-- `_spe_est` derives speed from base stats, level, the "
                    "boost stage and the PAR flag (encoder.rs:101-118)",
        "why": "AMENDED 2026-09-11 (see `amendments` A1). §2.6's claim 'exact "
               "when there are no boosts' is FALSE: the engine re-applies "
               "`statusModify` to the DEFENDER's ALREADY-MODIFIED active stats "
               "at the end of every stat change the FOE makes "
               "(`mechanics.zig:2580-2581` boost / `:2688-2689` unboost, both "
               "labelled 'GLITCH: Stat modification errors glitch'). Measured "
               "in-corpus by the write-side spike: stored spe 188, NO boosts, "
               "PAR -> the engine holds 11 (188/4/4) where §2.6's rule gives "
               "47. Correct domain: exact iff the active is neither paralysed "
               "nor burned -- not 'iff unboosted'.",
        "incidence": "AMENDED: 24.224% of non-aliased roots have the OPPONENT "
                     "active PAR|BRN, 5.875% our own, 28.031% either "
                     "(measured here on 13,396 roots; §2.5's 24.38% is the "
                     "same statistic over all 13,702 rows). The old bar said "
                     "2.26% / 1.08% -- the PAR|BRN-AND-a-stage intersection, "
                     "which is the wrong set.",
        "seen_by": "NEITHER leg; only the engine's turn order and damage see it",
    },
    "W-DISABLE": {
        "fields": "V_DISABLE_MOVE (u3, one-based live slot), V_DISABLE_DURATION",
        "class": "owner-visible, carried; NOT a residual",
        "obs_visible": False,
        "obs_dims": "-- the disabled SLOT is not encoded",
        "why": "ADDED 2026-09-11 (see `amendments` A2). §2.4 classes Disable "
               "as V, which is true for the POOL (0 of 146 species carry it, "
               "and 0 of 13,396 roots here show Effect.DISABLE) and false as a "
               "statement about the FIELD: dropping `disable_move` RE-OFFERS a "
               "move the request omits (`choices()` skips the slot, "
               "`mechanics.zig:3231`). That is leg C's HARD STOP, not a "
               "residual. The pair moves together -- a slot set with duration "
               "0 disables the move forever, because `beforeMove` only clears "
               "inside `if (disable_duration > 0)` -- so the spec must reject "
               "it; `spec.rs:486-489` defaults the duration to 4 of 1..=8.",
        "incidence": "0 of 13,396 non-aliased roots (measured). VACUOUS ON "
                     "THIS CORPUS, declared because the mechanism is not.",
        "seen_by": "**LEG C** -- and only leg C; it is an offered-set field",
    },
    "W-SLEEP": {
        "fields": "P_STATUS bits 0-2, the EXT bit",
        "class": "sampled per determinization",
        "obs_visible": False,
        "obs_dims": "-- turns REMAINING are hidden and never encoded; the "
                    "encoded `status_counter` is `sleep_observed`, which is "
                    "poke-env's own value and therefore exact",
        "why": "7.00% opp / 0.35% own asleep",
        "seen_by": "NEITHER leg directly; a wrong sleep_observed shows in leg A "
                   "(control C3)",
    },
    "W-CONF": {
        "fields": "V_CONFUSION_TURNS",
        "class": "sampled per determinization",
        "obs_visible": False,
        "obs_dims": "-- the FLAG is encoded (and is exact); the turns are hidden",
        "why": "0.74% of roots",
        "seen_by": "NEITHER leg",
    },
    "W-SUB": {
        "fields": "V_SUBSTITUTE_HP",
        "class": "defaulted to floor(maxhp/4)+1",
        "obs_visible": False,
        "obs_dims": "-- the FLAG is encoded; the HP is hidden",
        "why": "0 of 13,702 harvest roots have a Substitute up",
        "seen_by": "NEITHER leg (and vacuous on this corpus)",
    },
    "W-LASTDMG": {
        "fields": "B_LAST_DAMAGE, B_LAST_MOVES",
        "class": "reconstructed",
        "obs_visible": False,
        "obs_dims": "-- not encoded at all",
        "why": "read by Counter; 27/146 pool species carry it",
        "seen_by": "NEITHER leg",
    },
    "W-LASTMOVE": {
        "fields": "S_LAST_SELECTED_MOVE, S_LAST_USED_MOVE",
        "class": "sampled / defaulted",
        "obs_visible": False,
        "obs_dims": "-- not encoded",
        "why": "freeze_battle carries only the `preparing`/`must_recharge` "
               "booleans, so on harvest replay the LOCKED SLOT is not "
               "recoverable; 0.31% opp / 0.03% own preparing",
        "seen_by": "**LEG C** -- a hard lock offers exactly one move action and "
                   "`mask_for` needs last_selected_move to say WHICH",
    },
    "W-ORDER": {
        "fields": "S_ORDER[1..6]",
        "class": "free",
        "obs_visible": False,
        "obs_dims": "-- every action maps through slot_of_party_index",
        "why": "must contribute ZERO dims; if it does not, the freeness claim is false",
        "seen_by": "**LEG C** -- order[0] names the active and every switch "
                   "action indexes through the permutation",
    },
    "W-SEED": {
        "fields": "B_RNG",
        "class": "the chance dial",
        "obs_visible": False,
        "obs_dims": "-- must contribute ZERO dims",
        "why": "splitmix64(decision_key ^ col ^ det ^ s) per CRN-1",
        "seen_by": "NEITHER leg (by design -- it IS the sampling)",
    },
    "W-LS": {
        "fields": "V_LIGHT_SCREEN",
        "class": "NAMED UNMODELLABLE",
        "obs_visible": False,
        "obs_dims": "-- poke-env 0.15 has no Effect.LIGHT_SCREEN, so it is "
                    "invisible to BOTH encodings and can never be a diff",
        "why": "0 pool species: vacuous AND unmodellable, the safe combination",
        "seen_by": "NEITHER leg",
    },
    "W-REQ": {
        "fields": "the (Request, Request) pair",
        "class": "derived from fainted-ness",
        "obs_visible": True,
        "obs_dims": "global.force_switch",
        "why": "self-checking via Battle::update's legality check; must be 0 dims",
        "seen_by": "leg A (the flag) and **LEG C** (the whole offered set)",
    },
    "W-DET": {
        "fields": "the determinization itself",
        "class": "inherited, unchanged",
        "obs_visible": True,
        "obs_dims": "every dim of opp_mon<k> for k >= n_revealed, and "
                    "ids.opp_species[k] likewise",
        "why": "must contribute ZERO dims once the information boundary is "
               "imposed -- control C5 removes the boundary and this is what "
               "blows up (~35.9 dims/root)",
        "seen_by": "leg A",
    },
    "W-TRANSFORM": {
        "fields": "a transformed Ditto's copied base stats",
        "class": "unrepresentable from the static dex",
        "obs_visible": True,
        "obs_dims": "base stats, types, both matchups, the speed edge and every "
                    "move matchup downstream of them",
        "why": "Ditto is 1 of 146 pool species; DET_BLIND.md:281 priced it at "
               "0.375 dims/root over 32/1600 roots",
        "seen_by": "leg A",
    },
    # ---- stand-in families: poke_engine backend ONLY ----------------------
    "S-PREPARING": {
        "fields": "*_active.preparing",
        "class": "STAND-IN ARTEFACT",
        "obs_visible": True,
        "obs_dims": "own_active.preparing / opp_active.preparing",
        "why": "`shadow_battle._mon_view` hard-codes `preparing=False`; the "
               "ENGINE writes V_CHARGING from poke-env's own flag, so this "
               "family is expected to VANISH on --backend engine",
        "seen_by": "leg A",
    },
    "S-TRAPPED": {
        "fields": "global.trapped",
        "class": "STAND-IN ARTEFACT",
        "obs_visible": True,
        "obs_dims": "global.trapped",
        "why": "`shadow_battle` hard-codes `trapped=False`; the engine has "
               "`Volatiles::forced()`, which track.rs:310-312 states is exactly "
               "PS's `trapped: true`",
        "seen_by": "leg A",
    },
    "S-SLEEPREST": {
        "fields": "*_active.status_counter",
        "class": "STAND-IN ARTEFACT",
        "obs_visible": True,
        "obs_dims": "own_active.status_counter / opp_active.status_counter",
        "why": "the poke_engine path splits sleep_turns from rest_turns and the "
               "shadow sums them; the engine tracker carries poke-env's own "
               "`sleep_observed`",
        "seen_by": "leg A",
    },
}

STAND_IN_FAMILIES = frozenset(k for k, v in FAMILY_DOC.items()
                              if v["class"] == "STAND-IN ARTEFACT")


def declared_families(backend: str) -> frozenset[str]:
    """`S-*` families are declared on the STAND-IN backend only. On the engine
    backend they are UNDECLARED, i.e. a FAIL -- the gate gets stricter when the
    real surface lands, which is the only direction a stand-in may fail in."""
    if backend == "poke_engine":
        return frozenset(FAMILY_DOC)
    return frozenset(FAMILY_DOC) - STAND_IN_FAMILIES


# ---------------------------------------------------------------------------
# Leg A — per-dim family attribution
# ---------------------------------------------------------------------------

@dataclass
class RootFacts:
    """The few per-root facts the family classifier needs. All of them come
    from battle1 / the harvest row, never from the diff."""

    n_revealed: int
    transformed_ditto: bool
    own_sleeping: bool
    opp_sleeping: bool
    own_preparing: bool
    opp_preparing: bool
    trapped: bool


def classify_family(d: DimInfo, f: RootFacts) -> str:
    """Which DECLARED family a differing dim belongs to, or 'undeclared'.

    'undeclared' is a BUG, not a family -- the rule engine_p1_run.py:127-129
    already enforces. The order of the tests matters: the determinized bench
    (W-DET) is checked before anything else on an opponent mon block, because
    a dim inside an invented mon is invented whatever field it names."""
    if d.block.startswith("opp_mon") and d.slot >= f.n_revealed:
        return "W-DET"
    if d.block == "ids" and d.field.startswith("opp_species") and d.slot >= f.n_revealed:
        return "W-DET"
    if d.block == "global":
        if d.field == "trapped":
            return "S-TRAPPED"
        if d.field == "force_switch":
            return "W-REQ"
        return "undeclared"
    if d.field == "preparing":
        return "S-PREPARING"
    if d.field == "status_counter":
        sleeping = f.own_sleeping if d.side == "own" else f.opp_sleeping
        return "S-SLEEPREST" if sleeping else "undeclared"
    if f.transformed_ditto and d.field in _TRANSFORM_SENSITIVE:
        return "W-TRANSFORM"
    if d.block.startswith("opp_mon") and d.field == "hp":
        return "W-HP"
    return "undeclared"


# Every field a transformed Ditto's copied base stats can reach: the stats
# themselves, the types they imply, and everything the encoder derives from
# either (both matchups, the speed edge, and the per-move type multiplier).
_TRANSFORM_SENSITIVE = frozenset(
    [f"base_stat[{i}]" for i in range(5)]
    + [f"type[{i}]" for i in range(15)]
    + ["matchup_out", "matchup_in", "speed_edge", "multiplier"]
)


# ---------------------------------------------------------------------------
# Positive controls (design §3.3). Each corrupts exactly ONE rule in the
# CONSTRUCTION, never in the reference -- the reference is the harvested row
# and is immutable by construction. A control that does NOT break the gate is
# a FINDING ABOUT THE GATE and is reported as one (§3.3's closing line).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Control:
    id: str
    what: str
    must_move: str
    # the single construction rule this control corrupts
    reveal_swap: bool = False
    zero_move_uses: bool = False
    sleep_off_by_one: bool = False
    drop_faint_flags: bool = False
    all_revealed: bool = False
    flip_negative_boost: bool = False
    hp_floor: bool = False
    revive_fainted: bool = False
    beyond_design: bool = False


CONTROLS: tuple[Control, ...] = (
    Control("C1", "swap two entries of the opponent's reveal_order",
            f"the opp mon blocks [{_OPP_MON}..{_OPP_ACTIVE}) and the id suffix "
            f"[{_IDS + 6}..{_IDS + 12})", reveal_swap=True),
    Control("C2", "zero move_uses (re-introduce the A-1a defect exactly)",
            f"the opponent pp slots {_OPP_MOVES + _MOVE_PP}/"
            f"{_OPP_MOVES + MOVE_DIM + _MOVE_PP}/"
            f"{_OPP_MOVES + 2 * MOVE_DIM + _MOVE_PP}", zero_move_uses=True),
    Control("C3", "sleep_observed off by one",
            f"status_counter at [{_OPP_ACTIVE + _ACTIVE_STATUS_COUNTER}]",
            sleep_off_by_one=True),
    Control("C4", "drop flags_before_faint",
            "the recharging / preparing dims on the force-switch roots",
            drop_faint_flags=True),
    Control("C5", "THE AS-IS CONTROL: every opponent party slot revealed",
            "~35.9 dims/root (DET_BLIND.md:61), reproducing S1's artefact",
            all_revealed=True),
    Control("C6", "flip the sign of a negative boost",
            f"the boost block at [{_OWN_ACTIVE}..{_OWN_ACTIVE + 7}) / "
            f"[{_OPP_ACTIVE}..{_OPP_ACTIVE + 7})", flip_negative_boost=True),
    Control("C7", "write HP with floor instead of round",
            "must move INSIDE W-HP and still be bounded by W-HP's max|delta|",
            hp_floor=True),
    # ---- BEYOND THE DESIGN'S SEVEN -----------------------------------------
    # §3.3 names C1-C7 and every one of them is an OBSERVATION-side control:
    # each "must move" cell names encoder dims. So as written, §3.3 leaves
    # LEG C -- the leg the design itself calls load-bearing -- WITHOUT A
    # POSITIVE CONTROL, and a leg C that reports 100% is then
    # indistinguishable from a leg C that reports 100% unconditionally.
    # C8 corrupts fainted-ness, which §3.2 names as one of the four things
    # obs parity cannot see, and it is the cheapest thing that moves the
    # OFFERED SET without moving the mask function.
    Control("C8", "[beyond §3.3] revive a fainted bench mon in the construction",
            "LEG C: the offered set gains a switch slot that the live game "
            "did not offer. Also visible to leg A (own_mon<k>.hp / .fainted / "
            "global.own_fainted) -- see FINDING F3.",
            revive_fainted=True, beyond_design=True),
)

NO_CONTROL = Control("C0", "the gate as it runs", "nothing")


# ---------------------------------------------------------------------------
# RootReveal — §3.1's payload, built from battle1 ONLY.
#
# This is backend-INDEPENDENT data and it is implemented for real today, so
# that `BattleTracker::from_root` is a one-line call away rather than a
# rewrite. Engine ids: B-0 proved engine species 1..151 and moves 1..165 are
# poke-env's own `num` (env.rs:129-130), so `_species_id` / `_move_id` ARE the
# engine's id space -- no table.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RootReveal:
    reveal_order: list[int]               # party indices, first-switch-in order
    revealed_moves: list[list[int]]       # engine move ids, usage order, per slot
    move_uses: list[list[int]]            # observed PP spends, aligned
    sleep_observed: list[int]
    flags_before_faint: list[tuple[bool, bool]]  # (must_recharge, preparing)
    binding_victim_turns: int = 0

    def as_dict(self) -> dict:
        return {
            "reveal_order": list(self.reveal_order),
            "revealed_moves": [list(x) for x in self.revealed_moves],
            "move_uses": [list(x) for x in self.move_uses],
            "sleep_observed": list(self.sleep_observed),
            "flags_before_faint": [list(x) for x in self.flags_before_faint],
            "binding_victim_turns": int(self.binding_victim_turns),
        }


def _side_reveal(mons: list[Any]) -> RootReveal:
    from rl.envs.showdown import _move_id
    from rl.search.shadow_battle import _cached_move

    revealed_moves: list[list[int]] = []
    move_uses: list[list[int]] = []
    sleep_observed: list[int] = []
    flags: list[tuple[bool, bool]] = []
    for mon in mons:
        ids, uses = [], []
        for mid, mv in list(mon.moves.items())[:4]:
            # `_move_id` takes a Move OBJECT, not an id string, and returns
            # poke-env's `num` -- which B-0 proved IS the engine's move id.
            base = _cached_move(mid)
            ids.append(int(_move_id(base)))
            max_pp = int(base.max_pp or 0)
            # THE A-1a RULE, verbatim: observed spends, never a hard-coded
            # full clip. track.rs hard-coded pp = max_pp and P-1 could not
            # see it because P-1 fills the observable state FROM poke-env.
            uses.append(max(0, max_pp - int(mv.current_pp)))
        revealed_moves.append(ids)
        move_uses.append(uses)
        # SLEEP_OBSERVED SURVIVES THE FAINT, and that is not a guess -- it is
        # the one undeclared dim leg A found on the full 13,396-root corpus
        # (s64 ep48 step15, FINDING F5): a Slowbro that fainted while asleep
        # keeps `status_counter = 1` under `status = FNT`, the live encoder
        # writes 1/16 = 0.0625 into own_active.status_counter, and a rule
        # keyed on `status == SLP` writes 0. Same shape as
        # `flags_before_faint` (§3.1), which exists for exactly this reason.
        # TOX is the other counter-bearing status and is vacuous in gen 1
        # (0 pool species carry Toxic, §2.5).
        st = getattr(mon.status, "name", None)
        sleep_observed.append(int(getattr(mon, "status_counter", 0) or 0)
                              if st in ("SLP", "FNT") else 0)
        flags.append((bool(getattr(mon, "must_recharge", False)),
                      bool(getattr(mon, "preparing", False))))
    while len(revealed_moves) < 6:
        revealed_moves.append([])
        move_uses.append([])
        sleep_observed.append(0)
        flags.append((False, False))
    return RootReveal(
        reveal_order=list(range(len(mons))),
        revealed_moves=revealed_moves,
        move_uses=move_uses,
        sleep_observed=sleep_observed,
        flags_before_faint=flags,
        binding_victim_turns=0,  # vacuous in gen1randombattle (pool census)
    )


def charging_slot(mon: Any) -> int | None:
    """The ONE-BASED live move slot a charging mon is locked into, or None.

    NOT COSMETIC. `VolatileSpec::charging` carries the slot, and the engine
    derives BOTH `S_LAST_SELECTED_MOVE` and `B_LAST_MOVES[p].index` from it
    (`spec.rs:613`, `write_side.rs::charging_drives_both_derived_bytes_...`).
    An index of 0 is an unconditional OUT-OF-BOUNDS read -- `moves[-1]` -- and
    `build.rs:220` pins `-Doptimize=ReleaseFast` in every profile, so the
    `mslot > 0` assert is COMPILED OUT: the engine reads garbage rather than
    trapping. So a charging root must carry a real slot or must not be built.

    poke-env retains the charging move's identity as `_preparing_move`, so the
    LIVE path can fill this. `freeze_battle` carries `preparing` as a BOOLEAN
    ONLY (harvest.py:53), so on harvest replay this returns None -- declared
    family W-LASTMOVE, 47 of 13,396 roots (0.351%). Returning None is the
    point: the engine backend REFUSES those roots instead of defaulting them.
    """
    if not getattr(mon, "preparing", False):
        return None
    prep = getattr(mon, "_preparing_move", None) or getattr(mon, "preparing_move", None)
    mid = getattr(prep, "id", prep if isinstance(prep, str) else None)
    if not mid:
        return None
    for j, key in enumerate(list(mon.moves)[:4]):
        if key == mid:
            return j + 1  # one-based, as V_DISABLE_MOVE / charging are
    return None


def charging_roots_unbuildable(battle: Any) -> list[str]:
    """Which seats hold a charging active whose slot the source cannot supply.
    Non-empty means the engine backend must REFUSE this root, not default it."""
    out = []
    for tag, mon in (("p1", getattr(battle, "active_pokemon", None)),
                     ("p2", getattr(battle, "opponent_active_pokemon", None))):
        if mon is not None and getattr(mon, "preparing", False) \
                and charging_slot(mon) is None:
            out.append(tag)
    return out


def root_reveals(battle: Any) -> tuple[RootReveal, RootReveal]:
    """(`p1`, `p2`) `RootReveal`s from battle1's public surface.

    §3.1's simplification is taken: we choose the constructed party order, so
    the opponent's revealed mons sit at party indices 0..n_revealed-1 IN
    REVEAL ORDER and `reveal_order == [0, 1, ..., n-1]` by construction.
    poke-env's `opponent_team` is insertion-ordered by reveal, which is
    exactly that order (harvest.py:59, 65-66 preserves it)."""
    return (_side_reveal(list(battle.team.values())),
            _side_reveal(list(battle.opponent_team.values())))


# ---------------------------------------------------------------------------
# The mask law -- mirrored from the engine's own `action_to_choice`
# (`engine/pkmn_gen1/src/env.rs:82-124`) and `choices()`.
#
# READS THE CONSTRUCTED STATE ONLY. It never sees battle.available_moves,
# battle.trapped or the harvested mask, because a mask oracle that shares an
# input with its reference measures nothing (engine_p1.py's docstring records
# what that cost the first version of gate P-1).
# ---------------------------------------------------------------------------

# `Volatiles::forced()` == `mechanics.zig::isForced` == PS's `trapped: true`
# (layout.rs:199-203, track.rs:310-312): recharging | rage | thrashing |
# charging. `partiallytrapped` is added here because the poke_engine backend
# spells binding that way; 0 pool species carry it, so it is inert on gen 1.
FORCED_VOLATILES = ("mustrecharge", "rage", "thrashing", "charging",
                    "lockedmove", "partiallytrapped")


@dataclass
class MaskResult:
    mask: np.ndarray
    request: str          # "move" | "switch"  (W-REQ, from fainted-ness)
    forced: bool
    locked_slot: int      # -1 when not forced / not recoverable


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class PokeEngineBackend:
    """The STAND-IN, and the thing that runs today.

    Construction is the existing search path: `battle_to_state(battle1, det)`
    plus `shadow_battle(..., view=public_view(battle1))`. The `view` is what
    stands in for the engine's `revealed` tracker -- it re-imposes the LIVE
    encoder's information boundary on the constructed root, which is the same
    job `SideTracker::from_root` does in Rust. Without it the gate would be
    measuring control C5 on every root.
    """

    name = "poke_engine"
    licenses = ("obs parity", "mask parity", "W-VALIDATE",
                "transition invariants")
    cannot = ("the FOE-seat observation (no encoder for it on this path)",
              "the 384-byte layout (no bytes exist on this path)",
              "V_CHARGING and `trapped` (the shadow hard-codes both)")

    def __init__(self) -> None:
        from poke_env.data import GenData

        self.type_chart = GenData.from_gen(1).type_chart

    # -- construction ----------------------------------------------------
    def build(self, battle: Any, det: dict, ctl: Control) -> dict:
        from rl.search.bridge import BridgeCounters, battle_to_state
        from rl.search.shadow_battle import PublicView, public_view

        det = _apply_reveal_swap(det) if ctl.reveal_swap else det
        view = None if ctl.all_revealed else public_view(battle)
        if ctl.zero_move_uses and view is not None:
            view = PublicView(view.revealed_species, view.revealed_moves,
                              _max_pp_view(view))
        counters = BridgeCounters()
        if ctl.hp_floor:
            with _hp_floor_patch():
                state = battle_to_state(battle, det, counters)
        else:
            state = battle_to_state(battle, det, counters)
        return {"state": state, "view": view, "turn": int(battle.turn),
                "counters": counters}

    # -- leg A -----------------------------------------------------------
    def encode(self, root: dict) -> np.ndarray:
        from rl.search.shadow_battle import shadow_battle

        sb = shadow_battle(root["state"], turn=root["turn"], view=root["view"])
        return np.asarray(embed_battle(sb, self.type_chart), dtype=np.float32)

    # -- leg C -----------------------------------------------------------
    def mask(self, root: dict) -> MaskResult:
        return mask_for_poke_engine_state(root["state"])

    # -- leg B -----------------------------------------------------------
    def validate(self, root: dict) -> list[str]:
        return validate_poke_engine_state(root["state"])

    def step(self, root: dict, our_action: int, opp_action: str) -> dict | None:
        return step_poke_engine_state(root["state"], our_action, opp_action)


def mask_for_poke_engine_state(state: Any) -> MaskResult:
    """The 10-way mask, derived from a constructed poke_engine `State`.

    Mirrors `env.rs::action_to_choice` clause for clause:

      * W-REQ first. Our active fainted -> `Request::Switch`, and the offered
        set is the live bench ONLY. `forced()` is irrelevant under a Switch
        request -- the engine clears a fainted active's volatiles, while
        poke-env leaves `must_recharge` standing on the corpse (87 roots).
      * Otherwise `Request::Move`. Under a HARD LOCK the engine offers exactly
        `Move(1)` and no switch, and poke-env maps that to `6 + the locked
        move's STORED SLOT` -- which needs `S_LAST_SELECTED_MOVE`. The harvest
        does not carry it (family W-LASTMOVE), so `locked_slot` is -1 and the
        mask is left empty rather than guessed. That is a DECLARED gap, and it
        is the gap leg C is supposed to surface.
      * Otherwise: every live non-active party member, plus every live move
        slot with pp > 0.
    """
    s1 = state.side_one
    ai = _active_index(s1)
    act = s1.pokemon[ai]
    m = np.zeros(N_ACTIONS, dtype=bool)
    live_switches = [i for i, p in enumerate(s1.pokemon[:6])
                     if i != ai and p.hp > 0]
    if act.hp <= 0:
        for i in live_switches:
            m[i] = True
        return MaskResult(m, "switch", False, -1)
    vols = {str(v).lower() for v in s1.volatile_statuses}
    forced = any(v in vols for v in FORCED_VOLATILES)
    if forced:
        return MaskResult(m, "move", True, -1)
    for i in live_switches:
        m[i] = True
    for j, mv in enumerate(act.moves[:4]):
        # W-DISABLE: `choices()` SKIPS a disabled slot (mechanics.zig:3231), so
        # a mask that ignores `disabled` re-offers a move the request omits.
        # Vacuous on gen1randombattle (0 pool species carry Disable, 0 of
        # 13,396 roots show Effect.DISABLE) -- the clause is here because the
        # MECHANISM is not vacuous and this is the leg that would catch it.
        if (str(mv.id).lower() != "none" and mv.pp > 0
                and not getattr(mv, "disabled", False)):
            m[6 + j] = True
    return MaskResult(m, "move", False, -1)


def validate_poke_engine_state(state: Any, allow_terminal: bool = False
                               ) -> list[str]:
    """W-VALIDATE (design §2.4), on the fields this backend can express.

    `from_bytes` accepts anything, so the write side must validate before
    handing a state to `update`; the same discipline applies to the stand-in.
    Cheap, and it converts every write-side bug into a loud error.

    `allow_terminal` is for LEAVES: a depth-1 leaf may legitimately have a
    side wiped (the battle ended there), and at the root it may not. Measured
    on 200 stepped roots: 4 leaves with a wiped side, 1 with the empty offered
    set that implies -- both correct, both a false alarm without this flag."""
    out: list[str] = []
    wiped = any(
        not any(p.hp > 0 for p in side.pokemon if str(p.id).lower() != "none")
        for side in (state.side_one, state.side_two)
    )
    terminal = allow_terminal and wiped
    for tag, side in (("p1", state.side_one), ("p2", state.side_two)):
        mons = [p for p in side.pokemon if str(p.id).lower() != "none"]
        if not mons:
            out.append(f"{tag}: no party members")
            continue
        if len(mons) > 6:
            out.append(f"{tag}: {len(mons)} party members")
        if not any(p.hp > 0 for p in mons) and not terminal:
            out.append(f"{tag}: no unfainted mon")
        ai = _active_index(side)
        if not 0 <= ai < len(side.pokemon):
            out.append(f"{tag}: active_index {ai} out of range")
            continue
        for i, p in enumerate(side.pokemon):
            if str(p.id).lower() == "none":
                continue
            if p.hp > p.maxhp:
                out.append(f"{tag}.mon{i}: hp {p.hp} > maxhp {p.maxhp}")
            if p.hp < 0:
                out.append(f"{tag}.mon{i}: hp {p.hp} < 0")
            if p.maxhp <= 0:
                out.append(f"{tag}.mon{i}: maxhp {p.maxhp}")
            if len(p.moves) != 4:
                out.append(f"{tag}.mon{i}: {len(p.moves)} move slots")
            if not any(str(mv.id).lower() != "none" for mv in p.moves):
                out.append(f"{tag}.mon{i}: no move")
    # our own active must be able to act or to switch
    mr = mask_for_poke_engine_state(state)
    if not mr.mask.any() and not mr.forced and not terminal:
        out.append("p1: empty offered set under a non-forced request")
    return out


def step_poke_engine_state(state: Any, our_action: int, opp_action: str
                           ) -> dict | None:
    """One joint turn from the constructed root; returns the fields leg B
    compares plus the transition invariants it can check without a second
    simulator. `None` when the engine refuses the pair."""
    from poke_engine import generate_instructions

    s1 = state.side_one
    ai = _active_index(s1)
    if our_action < 6:
        a_str = str(s1.pokemon[our_action].id).lower()
    else:
        mv = s1.pokemon[ai].moves[our_action - 6]
        a_str = str(mv.id).lower()
    try:
        branches = generate_instructions(state, a_str, opp_action)
    except Exception as exc:  # the engine refused the pair -- leg B reports it
        return {"error": f"{type(exc).__name__}: {exc}"}
    if not branches:
        return {"error": "no branches"}
    mass = float(sum(b.percentage for b in branches))
    top = max(branches, key=lambda b: b.percentage)
    leaf = state.apply_instructions(top)
    l1 = leaf.side_one
    return {
        "branch_mass": mass,
        "n_branches": len(branches),
        "our_active_after": _active_index(l1),
        "our_active_species_after": str(l1.pokemon[_active_index(l1)].id).lower(),
        "opp_active_species_after": str(
            leaf.side_two.pokemon[_active_index(leaf.side_two)].id).lower(),
        "our_hp_after": [int(p.hp) for p in l1.pokemon[:6]],
        "opp_hp_after": [int(p.hp) for p in leaf.side_two.pokemon[:6]],
        "our_boosts_after": [int(l1.attack_boost), int(l1.defense_boost),
                             int(l1.special_attack_boost), int(l1.speed_boost)],
        "invalid_after": validate_poke_engine_state(leaf, allow_terminal=True),
    }


def _active_index(side: Any) -> int:
    ai = side.active_index
    return ai if isinstance(ai, int) else int(str(ai)[-1])


class EngineBackend:
    """THE SEAM. Phase 1's Rust write side plugs in here and nowhere else.

    Everything above this class is backend-independent: the corpus walk, the
    dim classifier, the family table, the controls, the pass rule and the
    report. What this class needs is four names, all of them the design's:

      1. `pkmn_gen1.BattleSpec(turn, seed, p1, p2, last_damage).build()` --
         design §2.4's field-by-field write, W-VALIDATE inside it. LANDING NOW
         in `engine/pkmn_gen1/src/spec.rs` + `python.rs`.
      2. `rl.search.engine_bridge.battle_spec(battle1, det)` -- the poke-env ->
         spec MAPPING, which `python.rs` says in terms is not its job: "the
         determinizer, the reveal order, the HP quantisation and the A-1a PP
         rule live in rl/search/engine_bridge.py and are graded by R1-E".
      3. `pkmn_gen1.BattleTracker.from_root(b, p1, p2)` -- design §3.1, whose
         `RootReveal` payload `root_reveals()` above ALREADY produces.
      4. a seat-X encode of arbitrary battle bytes and `mask_for(b, p, req,
         aliased)` exposed to Python (design §4.1, `env.rs:167-173`).

    Until they exist this RAISES, naming the ones actually missing at the time
    it is called. It never degrades: a gate that silently fell back to the
    stand-in would report the stand-in's numbers under the engine's name.
    """

    name = "engine"
    licenses = ("obs parity", "mask parity", "W-VALIDATE on the 384 bytes",
                "cross-seat agreement (leg B)")
    cannot = ("the transition's CHANCE distribution (Phase 2 owns that)",)

    # (probe, human name). The probe returns True when the symbol is usable.
    _NEEDED = (
        ("pkmn_gen1.BattleSpec(...).build()  (design §2.4 + W-VALIDATE)",
         lambda: hasattr(_pkmn(), "BattleSpec")),
        ("rl.search.engine_bridge.battle_spec(battle1, det)  (the poke-env -> "
         "spec mapping; python.rs says it is not the Rust side's job)",
         lambda: hasattr(_engine_bridge(), "battle_spec")),
        ("pkmn_gen1.BattleTracker.from_root(b, p1, p2)  (design §3.1; "
         "root_reveals() already produces the payload)",
         lambda: hasattr(_pkmn(), "BattleTracker")),
        ("a seat-X encode of arbitrary battle bytes + mask_for(b, p, req, "
         "aliased)  (design §4.1, env.rs:167-173)",
         lambda: hasattr(_pkmn(), "mask_for")),
    )

    def build(self, battle: Any, det: dict, ctl: Control) -> dict:
        return _build_engine_root(battle, det, ctl)

    def encode(self, root: dict) -> np.ndarray:  # pragma: no cover - stub
        raise NotImplementedError(self._msg())

    def mask(self, root: dict) -> MaskResult:  # pragma: no cover - stub
        raise NotImplementedError(self._msg())

    def validate(self, root: dict) -> list[str]:  # pragma: no cover - stub
        raise NotImplementedError(self._msg())

    def step(self, root: dict, our_action: int, opp_action: str):  # pragma: no cover
        raise NotImplementedError(self._msg())

    @classmethod
    def missing(cls) -> list[str]:
        out = []
        for name, probe in cls._NEEDED:
            try:
                ok = bool(probe())
            except Exception:
                ok = False
            if not ok:
                out.append(name)
        return out

    @classmethod
    def _msg(cls) -> str:
        return ("--backend engine needs the Phase-1 write side. Missing:\n  "
                + "\n  ".join(cls.missing() or ["(nothing -- wire "
                                                "_build_engine_root)"]))


def _pkmn():
    import pkmn_gen1

    return pkmn_gen1


def _engine_bridge():
    from rl.search import engine_bridge

    return engine_bridge


def _build_engine_root(battle: Any, det: dict, ctl: Control) -> dict:
    """THE SEAM (design §2.4 + §3.1), and it is deliberately four lines.

    Everything the gate needs from the engine goes through here. The Python
    side of the mapping -- determinization, reveal order, HP quantisation, the
    A-1a PP rule, and the CONTROLS -- belongs in `rl/search/engine_bridge.py`,
    which `python.rs` names as its counterpart; `ctl` is threaded through so a
    positive control corrupts the SPEC, never the reference.
    """
    if EngineBackend.missing():
        raise NotImplementedError(EngineBackend._msg())
    seats = charging_roots_unbuildable(battle)         # pragma: no cover - stub
    if seats:                                          # pragma: no cover
        # NOT a degraded build. `VolatileSpec::charging = None` on a mon the
        # server has locked would write B_LAST_MOVES.index = 0, which the
        # engine reads as `moves[-1]` with the bounds assert compiled out.
        raise ValueError(
            f"charging active on {','.join(seats)} with no recoverable live "
            "slot (W-LASTMOVE): `freeze_battle` carries `preparing` as a bool "
            "only. Refusing to build -- a defaulted B_LAST_MOVES.index is an "
            "OOB read, not a wrong answer. Use the LIVE path, where poke-env's "
            "`_preparing_move` supplies the slot."
        )
    pkmn, bridge = _pkmn(), _engine_bridge()          # pragma: no cover - stub
    spec = bridge.battle_spec(battle, det, ctl)        # pragma: no cover
    b, req1, req2 = spec.build()                       # pragma: no cover
    p1, p2 = root_reveals(battle)                      # pragma: no cover
    tracker = pkmn.BattleTracker.from_root(b, p1.as_dict(), p2.as_dict())
    return {"battle": b, "tracker": tracker, "req": req1, "foe_req": req2,
            "turn": int(battle.turn)}                  # pragma: no cover


BACKENDS = {"poke_engine": PokeEngineBackend, "engine": EngineBackend}


# ---------------------------------------------------------------------------
# Control machinery for the poke_engine backend
# ---------------------------------------------------------------------------

def _apply_reveal_swap(det: dict) -> dict:
    """C1: swap the first two entries of the opponent's reveal order. The
    determinizer builds `opponents` by iterating `battle.opponent_team`, which
    poke-env insertion-orders by reveal, so the dict's first entries ARE the
    reveal order."""
    opp = det["opponents"]
    keys = [k for k, v in opp.items() if v.get("live") is not None]
    if len(keys) < 2:
        return det  # not applicable on this root
    a, b = keys[0], keys[1]
    swapped = {}
    for k, v in opp.items():
        if k == a:
            swapped[b] = opp[b]
        elif k == b:
            swapped[a] = opp[a]
        else:
            swapped[k] = v
    return dict(det) | {"opponents": swapped}


def _max_pp_view(view: Any) -> dict:
    """C2: every revealed opponent move back at its FULL clip -- the A-1a
    defect, re-introduced exactly (`track.rs` hard-coded `pp = max_pp`)."""
    from rl.search.shadow_battle import _cached_move

    out = {}
    for sp, pp in view.revealed_pp.items():
        out[sp] = {mid: int(_cached_move(mid).max_pp or 0) for mid in pp}
    return out


def control_exposure(frozen: dict, ctl: Control) -> bool:
    """Is the rule this control corrupts PRESENT at this root?

    `engine_p1_run.py`'s family-EXPOSURE precedent, and it is not decoration:
    without it a control that reports zero on a sample where its rule never
    occurs is indistinguishable from a gate that is blind to the rule. Measured
    on the first smoke, C7 read BLIND on 30 early-turn roots for exactly that
    reason -- every opponent mon was at hp_fraction 1.0, where floor == round."""
    from rl.search.shadow_battle import _cached_move

    opp = frozen["opponent_team"]
    ai, oi = frozen["active_index"], frozen["opponent_active_index"]
    own_act = frozen["team"][ai] if ai is not None else None
    opp_act = opp[oi] if oi is not None else None
    if ctl.reveal_swap:
        return len(opp) >= 2
    if ctl.zero_move_uses:
        return any(int(pp) < int(_cached_move(mid).max_pp or 0)
                   for mon in opp for mid, pp in mon["moves"])
    if ctl.sleep_off_by_one:
        return any(m is not None and m["status"] == "SLP"
                   for m in (own_act, opp_act))
    if ctl.drop_faint_flags:
        return any(m is not None and (m["must_recharge"] or m["preparing"])
                   for m in (own_act, opp_act))
    if ctl.all_revealed:
        return len(opp) < 6
    if ctl.flip_negative_boost:
        return any(m is not None and any(v < 0 for v in m["boosts"].values())
                   for m in (own_act, opp_act))
    if ctl.hp_floor:
        # the corruption can only bite where the point estimate is not integral
        return any(0.0 < m["current_hp_fraction"] < 1.0 for m in opp)
    if ctl.revive_fainted:
        return any(m["fainted"] for i, m in enumerate(frozen["team"]) if i != ai)
    return True


def corrupt_battle(battle: Any, ctl: Control) -> Any:
    """C3/C4/C6 corrupt the CONSTRUCTION's INPUT VIEW of battle1. The battle
    handed here is a freshly rehydrated copy: the reference is the harvested
    `row["obs"]` / `row["mask"]`, which no control can reach."""
    if ctl.sleep_off_by_one:
        for mon in list(battle.team.values()) + list(battle.opponent_team.values()):
            if getattr(mon.status, "name", None) == "SLP":
                mon.status_counter = int(getattr(mon, "status_counter", 0)) + 1
    if ctl.drop_faint_flags:
        for mon in list(battle.team.values()) + list(battle.opponent_team.values()):
            mon.must_recharge = False
            mon.preparing = False
    if ctl.flip_negative_boost:
        for mon in (battle.active_pokemon, battle.opponent_active_pokemon):
            if mon is None or not getattr(mon, "boosts", None):
                continue
            mon.boosts = {k: (-v if v < 0 else v) for k, v in mon.boosts.items()}
    if ctl.revive_fainted:
        for mon in battle.team.values():
            if mon is battle.active_pokemon or not mon.fainted:
                continue
            mon.fainted = False
            mon.status = None
            mon.current_hp = 1
            mon.current_hp_fraction = 1.0 / max(int(mon.max_hp or 1), 1)
            break
    return battle


class _hp_floor_patch:
    """C7: the opponent's HP written with floor instead of round.

    `_det_pokemon` computes `round(hp_fraction * maxhp)`; engine `State` /
    `Pokemon` objects are IMMUTABLE from Python (measured, expansion.py), so
    the corruption goes in through the ARGUMENT. The wrapper calls the real
    builder once to learn `maxhp` -- it never re-derives the stat formula, so
    a change to the stat model cannot make this control quietly stop biting."""

    def __enter__(self):
        import rl.search.bridge as br

        self._orig = br._det_pokemon

        def floored(species, move_ids, hp_fraction, *a, **kw):
            real = self._orig(species, move_ids, hp_fraction, *a, **kw)
            maxhp = int(real.maxhp)
            target = int(math.floor(float(hp_fraction) * maxhp))
            if target == int(real.hp):
                return real
            return self._orig(species, move_ids, (target + 0.25) / maxhp, *a, **kw)

        br._det_pokemon = floored
        return self

    def __exit__(self, *exc):
        import rl.search.bridge as br

        br._det_pokemon = self._orig
        return False


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

@dataclass
class Root:
    lane: str
    lane_index: int
    episode: int
    step: int
    turn: int
    row: dict
    frozen: dict


def iter_corpus(harvest_dir: pathlib.Path, lanes=LANES,
                limit: int | None = None, stride: int = 1) -> Iterator[Root]:
    """Non-aliased harvested roots, in lane / episode / step order.

    Aliased roots are the DECLARED exception (§3.2, env.rs:90-95): Showdown
    re-bases the move list onto a placeholder there, so move slot i no longer
    means move i and neither leg has a stable reference."""
    import pickle

    emitted = 0
    seen = 0
    for li, lane in enumerate(lanes):
        path = harvest_dir / f"harvest_{lane}.pkl"
        if not path.exists():
            continue
        with open(path, "rb") as fh:
            episodes = pickle.load(fh)
        for bi, ep in enumerate(episodes):
            for si, row in enumerate(ep["rows"]):
                if row["aliased"]:
                    continue
                seen += 1
                if (seen - 1) % stride:
                    continue
                if limit is not None and emitted >= limit:
                    return
                emitted += 1
                yield Root(lane, li, bi, si, int(row["turn"]), row, row["battle"])


def root_facts(frozen: dict) -> RootFacts:
    """Per-root exposure facts, from the frozen battle only.

    TRANSFORM DETECTION READS TYPES AS WELL AS BASE STATS, and that is a
    correction this gate paid for. `bridge._our_transform_stats_override`
    (bridge.py:249-278) detects OUR OWN transformed Ditto by base-stat
    inequality alone. Measured here on s62 ep8 step6: poke-env carried the
    COPIED TYPES (`['WATER']`) while leaving `base_stats` at Ditto's own dex
    values (48 across the board), so the base-stat test is False and the
    transform is missed. Detecting on either signal is strictly wider and
    costs nothing."""
    from poke_env.data import GenData

    dex = GenData.from_gen(1).pokedex
    transformed = False
    for mon in frozen["team"] + frozen["opponent_team"]:
        if mon["species"] == "ditto":
            base = dex["ditto"]["baseStats"]
            dex_types = {str(t).upper() for t in dex["ditto"]["types"]}
            if any(int(mon["base_stats"].get(k, -1)) != int(base[k]) for k in base):
                transformed = True
            if {str(t).upper() for t in mon["types"]} != dex_types:
                transformed = True
    ai = frozen["active_index"]
    oi = frozen["opponent_active_index"]
    own = frozen["team"][ai] if ai is not None else None
    opp = frozen["opponent_team"][oi] if oi is not None else None
    return RootFacts(
        n_revealed=len(frozen["opponent_team"]),
        transformed_ditto=transformed,
        own_sleeping=bool(own and own["status"] == "SLP"),
        opp_sleeping=bool(opp and opp["status"] == "SLP"),
        own_preparing=bool(own and own["preparing"]),
        opp_preparing=bool(opp and opp["preparing"]),
        trapped=bool(frozen["trapped"]),
    )


# ---------------------------------------------------------------------------
# Accumulators
# ---------------------------------------------------------------------------

@dataclass
class LegA:
    n: int = 0
    exposed: int = 0          # roots where the active control's rule is present
    bitwise_identical: int = 0
    total_dims: int = 0
    fam_dims: Counter = field(default_factory=Counter)
    fam_roots: Counter = field(default_factory=Counter)
    fam_max_abs: dict = field(default_factory=lambda: defaultdict(float))
    undeclared: list = field(default_factory=list)
    top_fields: Counter = field(default_factory=Counter)
    # Per-root (n_differing_dims, sum|delta| quantised to 1e-6). The control
    # comparison needs BOTH: C7 (floor vs round) leaves the differing-dim SET
    # unchanged and moves only the magnitudes, so a count-only "did it fire"
    # test reads a working control as BLIND -- measured on the first 400-root
    # control sample, where C7's dims/root moved by exactly 0.0000.
    sig: list = field(default_factory=list)

    def add(self, v_new: np.ndarray, v_live: np.ndarray, facts: RootFacts,
            root: Root, max_undeclared: int = 40) -> None:
        self.n += 1
        idxs = np.flatnonzero(
            np.asarray(v_new, dtype=np.float32).view(np.uint32)
            != np.asarray(v_live, dtype=np.float32).view(np.uint32)
        )
        if idxs.size == 0:
            self.bitwise_identical += 1
            self.sig.append((0, 0))
            return
        self.total_dims += int(idxs.size)
        self.sig.append((
            int(idxs.size),
            int(round(float(np.abs(np.asarray(v_new, dtype=np.float64)[idxs]
                                   - np.asarray(v_live, dtype=np.float64)[idxs]).sum())
                      * 1e6)),
        ))
        here = set()
        for d in idxs.tolist():
            info = classify_dim(int(d))
            fam = classify_family(info, facts)
            self.fam_dims[fam] += 1
            here.add(fam)
            delta = abs(float(v_new[d]) - float(v_live[d]))
            self.fam_max_abs[fam] = max(self.fam_max_abs[fam], delta)
            self.top_fields[f"{info.block}.{info.field}"] += 1
            if fam == "undeclared" and len(self.undeclared) < max_undeclared:
                self.undeclared.append({
                    "lane": root.lane, "episode": root.episode,
                    "step": root.step, "turn": root.turn,
                    "dim": int(d), "block": info.block, "field": info.field,
                    "constructed": float(v_new[d]), "live": float(v_live[d]),
                })
        for fam in here:
            self.fam_roots[fam] += 1

    def report(self, backend: str) -> dict:
        n = max(self.n, 1)
        declared = declared_families(backend)
        fams = {}
        for fam, dims in sorted(self.fam_dims.items(), key=lambda kv: -kv[1]):
            doc = FAMILY_DOC.get(fam, {})
            fams[fam] = {
                "dims_per_root": dims / n,
                "dims_total": int(dims),
                "roots": int(self.fam_roots[fam]),
                "root_incidence": self.fam_roots[fam] / n,
                "max_abs": float(self.fam_max_abs[fam]),
                "declared": fam in declared,
                "class": doc.get("class"),
                "obs_visible": doc.get("obs_visible"),
                "obs_dims": doc.get("obs_dims"),
            }
        dims_per_root = self.total_dims / n
        bit_frac = self.bitwise_identical / n
        whp = self.fam_dims.get("W-HP", 0) / n
        whp_max = float(self.fam_max_abs.get("W-HP", 0.0))
        zeros = {f: int(self.fam_dims.get(f, 0)) for f in ZERO_DIM_FAMILIES}
        checks = {
            "no_undeclared_dims": self.fam_dims.get("undeclared", 0) == 0,
            "dims_per_root_le_bar": dims_per_root <= BAR_TOTAL_DIMS_PER_ROOT,
            "bitwise_frac_ge_bar": bit_frac >= BAR_MIN_BITWISE_FRAC,
            "w_hp_dims_le_bar": whp <= BAR_WHP_DIMS_PER_ROOT,
            "w_hp_max_abs_le_bar": whp_max <= BAR_WHP_MAX_ABS,
            "free_families_contribute_zero": all(v == 0 for v in zeros.values()),
        }
        return {
            "leg": "A -- observation parity (bitwise, outside declared families)",
            "n_roots": self.n,
            "bitwise_identical": self.bitwise_identical,
            "bitwise_identical_frac": bit_frac,
            "dims_per_root": dims_per_root,
            "dims_total": int(self.total_dims),
            "undeclared_dims": int(self.fam_dims.get("undeclared", 0)),
            "undeclared_roots": int(self.fam_roots.get("undeclared", 0)),
            "families": fams,
            "free_family_dims": zeros,
            "undeclared_examples": self.undeclared,
            "top_fields": self.top_fields.most_common(15),
            "bar": {
                "dims_per_root_max": BAR_TOTAL_DIMS_PER_ROOT,
                "bitwise_frac_min": BAR_MIN_BITWISE_FRAC,
                "w_hp_dims_per_root_max": BAR_WHP_DIMS_PER_ROOT,
                "w_hp_max_abs_max": BAR_WHP_MAX_ABS,
                "zero_dim_families": list(ZERO_DIM_FAMILIES),
            },
            "checks": checks,
            "pass": all(checks.values()),
        }


@dataclass
class LegC:
    n: int = 0
    exact: int = 0
    causes: Counter = field(default_factory=Counter)
    mismatches: list = field(default_factory=list)
    declared_gap: int = 0
    # Roots the ENGINE backend must REFUSE rather than default: a charging
    # active whose live slot the source cannot supply (FINDING F6).
    charging_unbuildable: int = 0

    def add(self, mr: MaskResult, root: Root, max_examples: int = 40) -> None:
        self.n += 1
        truth = np.asarray(root.row["mask"], dtype=bool)
        if np.array_equal(mr.mask, truth):
            self.exact += 1
            return
        cause, declared = self._cause(mr, root)
        self.causes[cause] += 1
        if declared:
            self.declared_gap += 1
        if len(self.mismatches) < max_examples:
            self.mismatches.append({
                "lane": root.lane, "episode": root.episode, "step": root.step,
                "turn": root.turn, "cause": cause, "declared": declared,
                "request": mr.request, "forced": mr.forced,
                "live_legal": _legal_names(truth),
                "constructed_legal": _legal_names(mr.mask),
            })

    @staticmethod
    def _cause(mr: MaskResult, root: Root) -> tuple[str, bool]:
        frozen = root.frozen
        own = frozen["team"][frozen["active_index"]]
        if mr.forced and own["preparing"]:
            # a two-turn charge: the engine offers exactly the locked move and
            # `S_LAST_SELECTED_MOVE` says which slot. freeze_battle does not
            # carry it -> DECLARED W-LASTMOVE.
            return "W-LASTMOVE: hard lock, locked slot not in the harvest", True
        if mr.forced and own["must_recharge"] and not frozen["trapped"]:
            # poke-env's flag OUTLIVED the server's lock: the request offered a
            # full choice set on this root. Writing it into V_RECHARGING makes
            # the constructed state offer NOTHING but the lock.
            return ("CONSTRUCTION: poke-env must_recharge stale, server offered "
                    "a full set"), False
        if mr.forced:
            return "forced, other", False
        if own["preparing"]:
            # STAND-IN ONLY: `_side_volatiles` has no mapping for poke-env's
            # `preparing` bool, so the constructed state is NOT forced and
            # offers the full set where the server offered one charge move and
            # no switch. The ENGINE has V_CHARGING and would be forced here --
            # but the LOCKED SLOT still needs S_LAST_SELECTED_MOVE, which the
            # harvest does not carry. So it is a declared W-LASTMOVE gap on
            # the engine backend and a stand-in gap here.
            return ("STAND-IN: `preparing` not expressible as a volatile "
                    "(V_CHARGING); the engine would be forced here"), True
        if mr.request == "switch":
            return "switch request, offered set differs", False
        return "move request, offered set differs", False

    def report(self) -> dict:
        n = max(self.n, 1)
        frac = self.exact / n
        strict = frac
        excl = (self.exact + self.declared_gap) / n
        return {
            "leg": "C -- MASK PARITY (the independent oracle; load-bearing)",
            "n_roots": self.n,
            "exact": self.exact,
            "exact_frac": strict,
            "exact_frac_excluding_declared_W_LASTMOVE": excl,
            "mismatches": self.n - self.exact,
            "declared_gap_roots": self.declared_gap,
            "causes": dict(self.causes),
            "charging_roots_unbuildable_on_the_engine_backend":
                self.charging_unbuildable,
            "examples": self.mismatches,
            "target": LEG_C_TARGET,
            "hard_stop_below": BAR_LEG_C_HARD_STOP,
            "sees_what_leg_A_cannot": [
                "S_ORDER -- every switch action indexes through it",
                "Volatiles::forced() -- the hard-lock set",
                "PP > 0 -- a 0-PP move is not offered",
                "fainted-ness -- and therefore the (Request, Request) pair",
            ],
            "pass": strict >= BAR_LEG_C_HARD_STOP,
            "hit_target": strict >= LEG_C_TARGET,
        }


def _legal_names(mask: np.ndarray) -> list[str]:
    return ([f"switch{i}" for i in range(6) if mask[i]]
            + [f"move{j}" for j in range(4) if mask[6 + j]])


# poke-engine's branch percentages are floats; the FULL set sums to 100 up to
# float error. Measured on 200 stepped roots: max |sum - 100| = 1.29e-05, and
# nothing above 1e-3. The tolerance is set an order of magnitude above the
# measured worst case, not at an invented round number.
BRANCH_MASS_TOL = 1e-3


@dataclass
class LegB:
    n: int = 0
    validate_violations: list = field(default_factory=list)
    n_invalid: int = 0
    stepped: int = 0
    step_errors: Counter = field(default_factory=Counter)
    inv_switch_ok: int = 0
    inv_switch_n: int = 0
    inv_mass_ok: int = 0
    inv_mass_max_dev: float = 0.0
    inv_leaf_valid: int = 0
    cross_sim_n: int = 0
    cross_sim_agree: int = 0

    def add_validate(self, problems: list[str], root: Root) -> None:
        self.n += 1
        if problems:
            self.n_invalid += 1
            if len(self.validate_violations) < 20:
                self.validate_violations.append({
                    "lane": root.lane, "episode": root.episode,
                    "step": root.step, "problems": problems[:6],
                })

    def add_step(self, res: dict | None, root: Root, target_species: str | None
                 ) -> None:
        if res is None:
            return
        if "error" in res:
            self.step_errors[res["error"][:80]] += 1
            return
        self.stepped += 1
        dev = abs(res["branch_mass"] - 100.0)
        self.inv_mass_max_dev = max(self.inv_mass_max_dev, dev)
        if dev < BRANCH_MASS_TOL:
            self.inv_mass_ok += 1
        if not res["invalid_after"]:
            self.inv_leaf_valid += 1
        if target_species is not None:
            self.inv_switch_n += 1
            if res["our_active_species_after"] == target_species:
                self.inv_switch_ok += 1

    def report(self, backend: str) -> dict:
        stepped = max(self.stepped, 1)
        cross = (
            {
                "status": "SELF-COMPARISON -- VACUOUS ON THIS BACKEND",
                "why": ("the constructed state IS the poke_engine path here, so "
                        "the one-turn comparison compares the path to itself "
                        "and measures nothing about the bridge. It becomes live "
                        "on --backend engine, where the engine's own transition "
                        "is compared against poke_engine's on the fields both "
                        "can express."),
                "n": 0,
            }
            if backend == "poke_engine"
            else {"status": "live", "n": self.cross_sim_n,
                  "agree": self.cross_sim_agree,
                  "agree_frac": self.cross_sim_agree / max(self.cross_sim_n, 1)}
        )
        checks = {
            "w_validate_clean": self.n_invalid == 0,
            "branch_mass_sums_to_100": self.inv_mass_ok == self.stepped,
            "switch_lands_named_species": self.inv_switch_ok == self.inv_switch_n,
            "leaf_passes_w_validate": self.inv_leaf_valid == self.stepped,
        }
        return {
            "leg": "B -- INTERNAL CONSISTENCY",
            "DISCLOSURE": (
                "INTERNAL-ONLY, NEVER PARITY. There is no harvested foe "
                "observation and no external oracle for a one-turn transition "
                "at the root, so nothing in leg B compares the construction "
                "against ground truth. It can only catch a construction that "
                "disagrees with ITSELF. Design §3.2 requires this sentence."
            ),
            "n_roots": self.n,
            "w_validate": {
                "invalid_roots": self.n_invalid,
                "violations": self.validate_violations,
            },
            "transition_invariants": {
                "stepped": self.stepped,
                "errors": dict(self.step_errors),
                "branch_mass_100": f"{self.inv_mass_ok}/{self.stepped}",
                "branch_mass_max_abs_dev": self.inv_mass_max_dev,
                "branch_mass_tol": BRANCH_MASS_TOL,
                "switch_lands_named_species": f"{self.inv_switch_ok}/{self.inv_switch_n}",
                "leaf_passes_w_validate": f"{self.inv_leaf_valid}/{stepped}",
            },
            "cross_simulator": cross,
            # Design §3.2's own leg B is the FOE SEAT: "there is no harvested
            # foe observation, so there is no external oracle", and the check
            # it proposes is cross-seat agreement plus the privileged block's
            # value test. Neither exists on the stand-in -- there is no
            # foe-seat encoder on the poke_engine path at all -- so they are
            # recorded here as OWED rather than silently dropped.
            "owed_on_the_engine_backend": [
                "cross-seat agreement (tracker_properties.rs:9-12): two seats "
                "derive the same public facts by different code paths, so a "
                "side-index swap or a reveal-order/party-index confusion shows "
                "up as a disagreement",
                "the privileged block's value test "
                "(docs/proposals/privileged_critic_engine_route.md:215-230, "
                "test_engine_privileged_block_is_the_python_block)",
                "one-turn agreement with the poke_engine path on the fields "
                "both can express (this file's `step` surface, live once "
                "--backend engine builds)",
            ],
            "checks": checks,
            "pass": all(checks.values()),
        }


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def run_leg_ac(backend: Any, roots: list[Root], ctl: Control, n_det: int = 1,
               legb: LegB | None = None, leg_b_limit: int = 0,
               seed_base: int = R1E_SEED_BASE) -> tuple[LegA, LegC]:
    """Legs A and C over a root list under one control. Leg B piggybacks when
    `legb` is given, because it needs the same constructed state."""
    from rl.search.determinize import sample_determinization
    from rl.search.harvest import rehydrate_battle
    from rl.search.matrix import decision_rng

    a, c = LegA(), LegC()
    for k, root in enumerate(roots):
        battle = rehydrate_battle(root.frozen)
        if ctl is not NO_CONTROL:
            a.exposed += int(control_exposure(root.frozen, ctl))
            battle = corrupt_battle(battle, ctl)
        rng = decision_rng(seed_base + root.lane_index, root.episode,
                           root.turn, root.step)
        det = sample_determinization(battle, rng)
        for _ in range(n_det - 1):
            det = sample_determinization(battle, rng)
        built = backend.build(battle, det, ctl)
        facts = root_facts(root.frozen)
        a.add(backend.encode(built), root.row["obs"], facts, root)
        c.charging_unbuildable += int(bool(charging_roots_unbuildable(battle)))
        c.add(backend.mask(built), root)
        if legb is not None and k < leg_b_limit:
            legb.add_validate(backend.validate(built), root)
            legb.add_step(*_leg_b_step(backend, built, root, det))
    return a, c


def _leg_b_step(backend: Any, built: dict, root: Root, det: dict):
    """(step result, root, expected post-switch species) for leg B."""
    action = int(root.row["action"])
    mask = np.asarray(root.row["mask"], dtype=bool)
    if not mask.any() or not mask[action]:
        return None, root, None
    frozen = root.frozen
    opp_i = frozen["opponent_active_index"]
    if opp_i is None:
        return None, root, None
    opp_species = frozen["opponent_team"][opp_i]["species"]
    if frozen["force_switch"]:
        opp_str = "none"
    else:
        moves = det["opponents"].get(opp_species, {}).get("moves") or []
        if not moves:
            return None, root, None
        opp_str = moves[0]
    target = (frozen["team"][action]["species"] if action < 6 else None)
    return backend.step(built, action, opp_str), root, target


def provenance(harvest_dir: pathlib.Path, args) -> dict:
    def sh(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=20, cwd=str(pathlib.Path(__file__).resolve().parents[1])
                                  ).stdout.strip()
        except Exception:
            return None

    shas = {}
    for lane in LANES:
        p = harvest_dir / f"harvest_{lane}.pkl"
        if p.exists():
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            shas[p.name] = {"sha256": h.hexdigest(), "bytes": p.stat().st_size}
    return {
        "gate": "R1-E",
        "design": "docs/search_relook/ENGINE_SEARCH_DESIGN.md §3.2/§3.3",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": sh(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(sh(["git", "status", "--porcelain"])),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "encoder_fingerprint": dict(ENCODER_FINGERPRINT),
        "obs_dim": OBS_DIM,
        "block_dims": {"GLOBAL_DIM": GLOBAL_DIM, "MON_DIM": MON_DIM,
                       "ACTIVE_DIM": ACTIVE_DIM, "MOVE_DIM": MOVE_DIM,
                       "ID_DIM": ID_DIM},
        "corpus": shas,
        "determinization_key": f"decision_rng({args.seed_base} + lane_index, "
                               f"episode, turn, step), n_det={args.n_det}",
        "args": {k: (str(v) if isinstance(v, pathlib.Path) else v)
                 for k, v in vars(args).items()},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gate R1-E (design §3.2/§3.3)")
    ap.add_argument("--harvest", default="results/ch3_r1", type=pathlib.Path)
    ap.add_argument("--out", default="results/search_r1e", type=pathlib.Path)
    ap.add_argument("--backend", choices=tuple(BACKENDS), default="poke_engine")
    ap.add_argument("--limit", type=int, default=200,
                    help="roots for legs A/C (smoke default); --all overrides")
    ap.add_argument("--all", action="store_true",
                    help="the full 13,396 non-aliased roots")
    ap.add_argument("--control-limit", type=int, default=2000,
                    help="roots per positive control (strided over the corpus)")
    ap.add_argument("--controls-all", action="store_true",
                    help="run every control on the full leg-A corpus")
    ap.add_argument("--leg-b-limit", type=int, default=500)
    ap.add_argument("--n-det", type=int, default=1)
    ap.add_argument("--seed-base", type=int, default=R1E_SEED_BASE)
    ap.add_argument("--no-controls", action="store_true")
    ap.add_argument("--lanes", default=",".join(LANES))
    args = ap.parse_args(argv)

    lanes = tuple(x for x in args.lanes.split(",") if x)
    limit = None if args.all else args.limit
    t0 = time.time()
    backend = BACKENDS[args.backend]()

    roots = list(iter_corpus(args.harvest, lanes, limit))
    if not roots:
        print(f"no roots under {args.harvest} for lanes {lanes}", file=sys.stderr)
        return 2
    print(f"[R1-E] backend={args.backend}  roots={len(roots)}  "
          f"lanes={','.join(lanes)}  n_det={args.n_det}", flush=True)

    legb = LegB()
    leg_a, leg_c = run_leg_ac(backend, roots, NO_CONTROL, args.n_det, legb,
                              args.leg_b_limit, args.seed_base)
    a_rep = leg_a.report(args.backend)
    c_rep = leg_c.report()
    b_rep = legb.report(args.backend)
    print(f"[R1-E] legs A/B/C done in {time.time() - t0:.1f}s", flush=True)

    controls = []
    if not args.no_controls:
        if args.controls_all:
            ctl_roots = roots
        else:
            stride = max(1, len(roots) // max(args.control_limit, 1))
            ctl_roots = roots[::stride][:args.control_limit]
        # ONE baseline for the control subsample, not one per control: the
        # control arms differ from it only in the single rule they corrupt.
        base_a, base_c = run_leg_ac(backend, ctl_roots, NO_CONTROL, args.n_det,
                                    seed_base=args.seed_base)
        for ctl in CONTROLS:
            t1 = time.time()
            ca, cc = run_leg_ac(backend, ctl_roots, ctl, args.n_det,
                                seed_base=args.seed_base)
            controls.append(control_report(ctl, base_a, base_c, ca, cc,
                                           time.time() - t1))
            print(f"[R1-E] {ctl.id} {'FIRES' if controls[-1]['fires'] else 'BLIND'}"
                  f"  exposed {ca.exposed}/{ca.n}"
                  f"  legA {base_a.total_dims / max(base_a.n,1):.3f} -> "
                  f"{ca.total_dims / max(ca.n,1):.3f} dims/root"
                  f"  legC {base_c.exact}/{base_c.n} -> {cc.exact}/{cc.n}"
                  f"  ({time.time() - t1:.0f}s)", flush=True)

    blind = [c["id"] for c in controls if c["status"] == "BLIND"]
    unexposed = [c["id"] for c in controls if c["status"] == "NOT_EXPOSED"]
    report = {
        "provenance": provenance(args.harvest, args),
        "backend": {
            "name": backend.name,
            "licenses": list(backend.licenses),
            "cannot_see": list(backend.cannot),
            "stand_in": args.backend == "poke_engine",
        },
        "leg_a": a_rep,
        "leg_b": b_rep,
        "leg_c": c_rep,
        "family_table": FAMILY_DOC,
        "declared_families": sorted(declared_families(args.backend)),
        "controls": controls,
        "blind_controls": blind,
        "unexposed_controls": unexposed,
        "amendments": AMENDMENTS,
        "amendment_disclosure": (
            "The two family amendments A1/A2 POST-DATE the first full-corpus "
            "run (banked unamended at results/search_r1e/"
            "r1e_prebar_2026-09-11T2136.json). Both are sourced from ENGINE "
            "SEMANTICS measured by cargo unit tests in "
            "engine/pkmn_gen1/tests/write_side.rs, not from anything about "
            "R1-E's own results: they correct a bar that was WRONG, not a bar "
            "that FAILED. Neither moves any measured quantity in this report "
            "-- W-ACTIVESTATS is obs-invisible and W-DISABLE has incidence 0 "
            "on this corpus -- so the old-bar and amended-bar verdicts are "
            "IDENTICAL leg for leg. §7's failure branch forbids loosening "
            "families silently; this block is the sequence, made visible."
        ),
        "findings": FINDINGS,
        "verdict": {
            "leg_a_pass": a_rep["pass"],
            "leg_b_pass": b_rep["pass"],
            "leg_c_pass": c_rep["pass"],
            "leg_c_hit_target": c_rep["hit_target"],
            "controls_all_fire": not blind,
            # Leg B is INTERNAL-ONLY and is reported, never a parity verdict.
            "R1E_PASS": bool(a_rep["pass"] and c_rep["pass"] and not blind),
        },
        "what_a_pass_licenses": [
            "BUILD PHASE 2 (the batched leaf path and Form A).",
        ],
        "what_a_pass_does_NOT_license": [
            "any search NUMBER -- R1-E measures the root, not a decision",
            "any claim about the TRANSITION -- Phase 2's decision-level "
            "agreement read owns that",
            "any claim about LEAVES -- a root residual is not a leaf residual "
            "(DET_BLIND.md §5.3)",
            "any claim about the 100M-lane state distribution -- §3.2 requires "
            "a fresh 100M-lane harvest and this run is the 12M-era R1 corpus",
            "any claim about W-ACTIVESTATS, W-STATS, W-LASTDMG, W-SEED, "
            "W-CONF, W-SUB, W-LS, W-ORDER, W-LASTMOVE or W-DISABLE -- NEITHER "
            "leg can see them (see family_table). W-ACTIVESTATS in particular "
            "is KNOWN wrong on up to 28.031% of roots after amendment A1 "
            "(anything with a PAR or BRN active on either side), and both legs "
            "report clean anyway",
            "the 47 charging roots (0.351%) -- the engine backend REFUSES "
            "them rather than defaulting a B_LAST_MOVES index the engine would "
            "read out of bounds (FINDING F6)",
        ],
        "wall_seconds": time.time() - t0,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "r1e.json"
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2, default=_jsonable)
    print_summary(report)
    print(f"\nwrote {path}")
    return 0 if report["verdict"]["R1E_PASS"] else 1


def control_report(ctl: Control, base_a: LegA, base_c: LegC, ca: LegA,
                   cc: LegC, secs: float) -> dict:
    """A control FIRES if it moves leg A's dim count or leg C's exact count.
    It is `applicable` on a root only if the rule it corrupts is present
    there -- `engine_p1_run.py`'s family-EXPOSURE precedent, without which a
    zero is true by construction and says nothing."""
    d_dims = ca.total_dims / max(ca.n, 1) - base_a.total_dims / max(base_a.n, 1)
    d_bit = base_a.bitwise_identical - ca.bitwise_identical
    d_mask = base_c.exact - cc.exact
    # Roots where the control moved leg A's OUTPUT -- either the set of
    # differing dims or their magnitudes. This is the firing test; the
    # aggregate deltas above are the report.
    moved_roots = sum(int(x != y) for x, y in zip(base_a.sig, ca.sig))
    moved_dimset = sum(int(x[0] != y[0]) for x, y in zip(base_a.sig, ca.sig))
    moved_magnitude_only = moved_roots - moved_dimset
    fires = bool(moved_roots or d_mask)
    if fires:
        status = "FIRES"
    elif ca.exposed == 0:
        status = "NOT_EXPOSED"
    else:
        status = "BLIND"
    moved_blocks = Counter()
    for fam, n in ca.fam_dims.items():
        if n - base_a.fam_dims.get(fam, 0):
            moved_blocks[fam] = int(n - base_a.fam_dims.get(fam, 0))
    moved_fields = {}
    for fld, n in ca.top_fields.items():
        d = n - base_a.top_fields.get(fld, 0)
        if d:
            moved_fields[fld] = int(d)
    return {
        "id": ctl.id,
        "beyond_design_section_3_3": ctl.beyond_design,
        "what": ctl.what,
        "must_move": ctl.must_move,
        "n_roots": ca.n,
        "exposed_roots": ca.exposed,
        "fires": fires,
        "status": status,
        "FINDING": None if fires else (
            "THIS CONTROL DID NOT BREAK THE GATE on a sample where the rule it "
            "corrupts was present on " + str(ca.exposed) + " roots. Per design "
            "§3.3 that is a finding ABOUT THE GATE, not a bug to hide: the gate "
            "cannot see the rule this control corrupts."
            if status == "BLIND" else
            "NOT EXPOSED: the rule this control corrupts occurs on 0 of the "
            + str(ca.n) + " sampled roots, so this sample does not test it. "
            "Not a blindness finding -- a coverage gap. Re-run with "
            "--controls-all or a larger --control-limit."
        ),
        "leg_a": {
            "roots_moved": moved_roots,
            "roots_moved_dim_set": moved_dimset,
            "roots_moved_magnitude_only": moved_magnitude_only,
            "dims_per_root_base": base_a.total_dims / max(base_a.n, 1),
            "dims_per_root_control": ca.total_dims / max(ca.n, 1),
            "delta_dims_per_root": d_dims,
            "bitwise_identical_base": base_a.bitwise_identical,
            "bitwise_identical_control": ca.bitwise_identical,
            "w_hp_max_abs_base": float(base_a.fam_max_abs.get("W-HP", 0.0)),
            "w_hp_max_abs_control": float(ca.fam_max_abs.get("W-HP", 0.0)),
            "w_hp_still_inside_bar": float(ca.fam_max_abs.get("W-HP", 0.0))
                                     <= BAR_WHP_MAX_ABS,
            "family_dim_deltas": dict(moved_blocks.most_common()),
            "field_deltas_top10": dict(sorted(moved_fields.items(),
                                              key=lambda kv: -abs(kv[1]))[:10]),
            "undeclared_dims_control": int(ca.fam_dims.get("undeclared", 0)),
        },
        "leg_c": {
            "exact_base": base_c.exact,
            "exact_control": cc.exact,
            "delta_exact": -d_mask,
            "causes_control": dict(cc.causes),
        },
        "seconds": secs,
    }


# ---------------------------------------------------------------------------
# Findings the gate itself turned up. These are STANDING statements about the
# construction rules and about §3's spec, not per-run numbers; the per-run
# numbers that back each one are in the leg reports beside them.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AMENDMENTS to the declared families, and the ORDER THEY HAPPENED IN.
#
# §7's failure branch pre-decided against loosening families after seeing
# results ("do not extend and do not LOOSEN THE FAMILIES SILENTLY"), so the
# sequence has to be visible or the amendment is worthless. Both of these
# post-date the first full-corpus run and BOTH ARE SOURCED FROM ENGINE
# SEMANTICS -- cargo unit tests in `engine/pkmn_gen1/tests/write_side.rs`,
# written by the write-side spike in parallel with this gate -- not from
# anything about R1-E's own numbers. They correct a bar that was WRONG, not a
# bar that FAILED.
# ---------------------------------------------------------------------------

AMENDMENTS = [
    {
        "id": "A1",
        "family": "W-ACTIVESTATS",
        "change": "incidence 2.26% opp / 1.08% own  ->  <=24.38%; and the "
                  "correct domain is 'exact iff the active is neither "
                  "paralysed nor burned', NOT §2.6's 'exact when there are no "
                  "boosts'",
        "source": "engine/pkmn_gen1/tests/write_side.rs::"
                  "the_stat_modification_glitch_compounds_status_on_the_defender; "
                  "mechanics.zig:2580-2581 (boost) and :2688-2689 (unboost), "
                  "both labelled 'GLITCH: Stat modification errors glitch'",
        "mechanism": "the engine re-applies `statusModify` to the DEFENDER's "
                     "already-modified active stats at the end of every stat "
                     "change the FOE makes. Nothing in the defender's public "
                     "description changes, so no observable distinguishes it.",
        "measured_here": "24.224% of 13,396 non-aliased roots have the "
                         "OPPONENT active PAR|BRN, 5.875% our own, 28.031% "
                         "either side",
        "post_dates_first_numbers": True,
        "effect_on_this_gate": "NONE on any measured quantity. W-ACTIVESTATS "
                               "is obs-INVISIBLE (the encoder's `_spe_est` "
                               "derives speed from base stats + stage + PAR, "
                               "never from A_STATS) and the mask does not read "
                               "stats, so it contributes 0 dims to leg A and 0 "
                               "roots to leg C under BOTH bars. What changes is "
                               "the DISCLOSURE: the thing neither leg can see "
                               "is now known to be wrong on up to 28% of roots "
                               "rather than 2-3%.",
    },
    {
        "id": "A2",
        "family": "W-DISABLE (new)",
        "change": "add V_DISABLE_MOVE / V_DISABLE_DURATION as a declared "
                  "family; §2.4 classed Disable as V (vacuous)",
        "source": "engine/pkmn_gen1/src/spec.rs:136-145, :443-489, :1151-1154; "
                  "choices() skips the disabled slot, mechanics.zig:3231",
        "mechanism": "V is true for the POOL and false for the FIELD: dropping "
                     "`disable_move` RE-OFFERS a move the request omits. That "
                     "is leg C's hard stop, not a residual. The slot and the "
                     "duration move together -- a slot with duration 0 disables "
                     "the move forever (`beforeMove` only clears inside "
                     "`if (disable_duration > 0)`).",
        "measured_here": "0 of 13,396 non-aliased roots show Effect.DISABLE -- "
                         "VACUOUS ON THIS CORPUS, declared anyway",
        "post_dates_first_numbers": True,
        "effect_on_this_gate": "NONE on any measured quantity (incidence 0). "
                               "`mask_for` now honours a disabled slot, which "
                               "is a no-op on this corpus and is the clause "
                               "that would catch it on any corpus where "
                               "Disable occurs.",
    },
]


FINDINGS = [
    {
        "id": "F6",
        "where": "a charging (preparing) root on the ENGINE backend",
        "what": "`VolatileSpec::charging` carries the one-based live SLOT, and "
                "the engine derives both `S_LAST_SELECTED_MOVE` and "
                "`B_LAST_MOVES[p].index` from it (`spec.rs:613`). An index of "
                "0 is an unconditional OUT-OF-BOUNDS read -- `moves[-1]` -- "
                "and `build.rs:220` pins `-Doptimize=ReleaseFast` in every "
                "profile, so the `mslot > 0` assert is COMPILED OUT. A "
                "defaulted charging root reads GARBAGE rather than failing.",
        "measured": "47 of 13,396 non-aliased roots have a charging active (43 "
                    "opponent, 4 own; 0.351%). `freeze_battle` carries "
                    "`preparing` as a BOOLEAN ONLY (harvest.py:53), so the "
                    "slot is unrecoverable on harvest replay -- declared "
                    "W-LASTMOVE. The LIVE path can fill it: poke-env retains "
                    "`_preparing_move`.",
        "recommendation": "`_build_engine_root` REFUSES a charging root whose "
                          "slot it cannot supply (`charging_roots_unbuildable`) "
                          "rather than defaulting it. Those 47 roots are "
                          "harvest-unbuildable and must be reported as such, "
                          "not silently constructed. This is also why §3.2's "
                          "FRESH 100M-LANE HARVEST should record "
                          "`_preparing_move`.",
    },
    {
        "id": "F1",
        "where": "leg C, the construction rule for V_RECHARGING",
        "what": "poke-env's `must_recharge` OUTLIVES the server's lock. On "
                "roots where the request offered a full choice set (not "
                "aliased, not trapped), poke-env still reports "
                "`must_recharge=True`. Writing that flag straight into "
                "V_RECHARGING makes `forced()` true and the constructed state "
                "then offers NO SWITCH AND ONE MOVE where the real game "
                "offered everything.",
        "measured": "39 of 13,396 non-aliased roots (0.291%) in the R1 harvest "
                    "carry must_recharge on a live, non-force-switch, "
                    "non-aliased, non-trapped active. 87 more carry it on a "
                    "FAINTED active, which W-REQ already handles (a Switch "
                    "request ignores forced()).",
        "recommendation": "the Rust write side should gate V_RECHARGING on the "
                          "request, not on poke-env's flag: write it only when "
                          "the root is aliased or trapped. Leg C is the only "
                          "leg that can see this -- the encoded "
                          "own_active.volatile[MUST_RECHARGE] dim agrees "
                          "between the two encoders precisely BECAUSE both read "
                          "poke-env's flag.",
    },
    {
        "id": "F2",
        "where": "`rl/search/bridge.py::_our_transform_stats_override`",
        "what": "OUR OWN transformed Ditto is detected by base-stat inequality "
                "against the dex. Measured on s62 ep8 step6: poke-env carried "
                "the COPIED TYPES (`['WATER']`) while leaving `base_stats` at "
                "Ditto's own dex values (48 across the board), so the "
                "base-stat test is False and the transform is missed. Design "
                "§2.4 says to REUSE this function on the engine side, which "
                "would inherit the miss.",
        "measured": "surfaced as UNDECLARED dims (own_mon0.type[10]/[14], both "
                    "matchups, opp_move multipliers) until this gate's own "
                    "detector was widened to test types as well as base stats.",
        "recommendation": "detect on EITHER signal. The gate does; the bridge "
                          "and the future engine spec builder should.",
    },
    {
        "id": "F3",
        "where": "design §3.3 as written",
        "what": "C1-C7 are ALL observation-side: every 'must move' cell names "
                "encoder dims. So §3.3 leaves LEG C -- the leg §3.2 itself "
                "calls load-bearing -- with NO positive control, and a leg C "
                "reporting 100% would be indistinguishable from one that "
                "reports 100% unconditionally. C8 (added here, marked "
                "`beyond_design_section_3_3`) corrupts fainted-ness, one of the "
                "four things §3.2 says obs parity cannot see.",
        "measured": "C1-C7 move leg C's exact count by 0 on every sample run.",
        "recommendation": "keep C8, and on the engine backend add the three "
                          "controls that are leg-C-ONLY there and have no "
                          "poke_engine analogue: permute S_ORDER[1..6] (W-ORDER "
                          "claims ZERO effect -- that claim is testable only on "
                          "the engine), flip one bit of Volatiles::forced(), "
                          "and mis-set S_LAST_SELECTED_MOVE under a hard lock.",
    },
    {
        "id": "F5",
        "where": "the sleep counter of a mon that FAINTED while asleep",
        "what": "poke-env keeps `status_counter` when a sleeping mon faints: "
                "the status becomes FNT and the counter survives. The live "
                "encoder writes it into `*_active.status_counter`, so a "
                "construction rule keyed on `status == SLP` writes 0 where the "
                "live obs has 1/16. `rl/search/bridge._our_pokemon` has that "
                "rule (`sleep_turns = status_counter if status == 'sleep'`), "
                "and so did this gate's own `RootReveal` builder until the "
                "full-corpus run caught it.",
        "measured": "exactly 1 of 13,396 non-aliased roots (s64 ep48 step15, a "
                    "Slowbro at status FNT / counter 1). It is the ONLY "
                    "undeclared dim on the whole corpus, so leg A reads FAIL "
                    "on the stand-in for this one dim and nothing else. Census: "
                    "741 actives carry a non-zero counter under SLP, 1 under "
                    "FNT, 0 under anything else.",
        "recommendation": "`SideTracker::from_root` must seed `sleep_observed` "
                          "from poke-env's `status_counter` for a FAINTED slot "
                          "too -- the same reason `flags_before_faint` exists "
                          "(§3.1). `root_reveals()` here does. It was NOT "
                          "widened into a declared family: the engine can get "
                          "this exactly right, so declaring it would license a "
                          "defect.",
    },
    {
        "id": "F4",
        "where": "the stand-in backend's reach",
        "what": "On `--backend poke_engine` there is NO construction corruption "
                "that leg C sees and leg A does not, because every field the "
                "stand-in can express is also encodable. The genuinely "
                "leg-C-only fields -- S_ORDER[1..6], the forced() bits as "
                "distinct from the request, S_LAST_SELECTED_MOVE -- are ENGINE "
                "fields with no poke_engine analogue.",
        "measured": "C8's leg-A delta is non-zero on every root it moves.",
        "recommendation": "read leg C's independence claim as PENDING until the "
                          "engine backend runs. Today leg C's value is that it "
                          "uses a DIFFERENT DERIVATION (the engine's choices() "
                          "law) of the same underlying state, not a different "
                          "field set.",
    },
]


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def print_summary(r: dict) -> None:
    v = r["verdict"]
    a, b, c = r["leg_a"], r["leg_b"], r["leg_c"]
    line = "=" * 76
    print(f"\n{line}\nGATE R1-E -- backend {r['backend']['name']}"
          f"{'  (STAND-IN)' if r['backend']['stand_in'] else ''}\n{line}")
    print(f"LEG A  observation parity, bitwise      "
          f"{'PASS' if a['pass'] else 'FAIL'}")
    print(f"       roots {a['n_roots']}   bit-identical {a['bitwise_identical']} "
          f"({100 * a['bitwise_identical_frac']:.1f}%, bar {100 * BAR_MIN_BITWISE_FRAC:.0f}%)"
          f"   {a['dims_per_root']:.4f} dims/root (bar {BAR_TOTAL_DIMS_PER_ROOT})")
    print(f"       {'family':<14}{'dims/root':>11}{'roots':>8}{'max|d|':>11}"
          f"  declared  obs-visible")
    for fam, s in a["families"].items():
        print(f"       {fam:<14}{s['dims_per_root']:>11.4f}{s['roots']:>8}"
              f"{s['max_abs']:>11.5f}  {str(s['declared']):<9} {s['obs_visible']}")
    if a["undeclared_examples"]:
        print("       UNDECLARED DIMS (a BUG, not a family):")
        for e in a["undeclared_examples"][:8]:
            print(f"         dim {e['dim']:<4} {e['block']}.{e['field']:<16} "
                  f"constructed={e['constructed']:.6g} live={e['live']:.6g}  "
                  f"({e['lane']} ep{e['episode']} step{e['step']})")
    print(f"\nLEG B  internal consistency             "
          f"{'PASS' if b['pass'] else 'FAIL'}   (INTERNAL-ONLY, NEVER PARITY)")
    print(f"       W-VALIDATE: {b['n_roots'] - b['w_validate']['invalid_roots']}"
          f"/{b['n_roots']} clean    "
          f"stepped {b['transition_invariants']['stepped']}   "
          f"branch-mass {b['transition_invariants']['branch_mass_100']}   "
          f"switch-lands {b['transition_invariants']['switch_lands_named_species']}   "
          f"leaf-valid {b['transition_invariants']['leaf_passes_w_validate']}")
    print(f"       cross-simulator: {b['cross_simulator']['status']}")
    print(f"\nLEG C  MASK PARITY (load-bearing)       "
          f"{'PASS' if c['pass'] else 'FAIL'}"
          f"{'  TARGET MET' if c['hit_target'] else ''}")
    print(f"       {c['exact']}/{c['n_roots']} exact = {100 * c['exact_frac']:.3f}%"
          f"   (hard stop {100 * BAR_LEG_C_HARD_STOP:.1f}%, target 100%)")
    print(f"       excluding declared W-LASTMOVE roots: "
          f"{100 * c['exact_frac_excluding_declared_W_LASTMOVE']:.3f}%")
    for cause, n in sorted(c["causes"].items(), key=lambda kv: -kv[1]):
        print(f"         {n:>5}  {cause}")
    print(f"       charging roots the ENGINE backend must REFUSE (F6): "
          f"{c['charging_roots_unbuildable_on_the_engine_backend']}")
    if r.get("amendments"):
        print(f"\nAMENDMENTS TO THE DECLARED FAMILIES (post-date the first run)")
        for am in r["amendments"]:
            print(f"       {am['id']}  {am['family']}: {am['change'][:120]}")
            print(f"           source: {am['source'][:110]}")
            print(f"           effect on this gate: "
                  f"{am['effect_on_this_gate'][:110]}")
    if r["controls"]:
        print(f"\nPOSITIVE CONTROLS  (n={r['controls'][0]['n_roots']} roots each)")
        print(f"       {'id':<4}{'status':<13}{'expsd':>6}{'moved':>7}"
              f"{'dims/root base->ctl':>26}{'legC exact':>15}   what")
        for cr in r["controls"]:
            la, lc = cr["leg_a"], cr["leg_c"]
            print(f"       {cr['id']:<4}{cr['status']:<13}{cr['exposed_roots']:>6}"
                  f"{la['roots_moved']:>7}"
                  f"{la['dims_per_root_base']:>11.4f} ->{la['dims_per_root_control']:>11.4f}"
                  f"{lc['exact_base']:>8}->{lc['exact_control']:<6}   {cr['what'][:38]}")
        if r["blind_controls"]:
            print(f"       BLIND: {', '.join(r['blind_controls'])} -- see FINDING "
                  f"in the JSON; per §3.3 this is a finding about the GATE")
        if r["unexposed_controls"]:
            print(f"       NOT EXPOSED: {', '.join(r['unexposed_controls'])} -- "
                  f"a COVERAGE gap in this sample, not gate blindness")
    print(f"\nFINDINGS (standing; numbers above)")
    for f in r["findings"]:
        print(f"       {f['id']}  {f['where']}")
        print(f"           {f['what'][:180]}")
    print(f"\n{line}\nR1-E {'PASS' if v['R1E_PASS'] else 'FAIL'}   "
          f"(A {'pass' if v['leg_a_pass'] else 'FAIL'} | "
          f"C {'pass' if v['leg_c_pass'] else 'FAIL'} | "
          f"controls {'all fire' if v['controls_all_fire'] else 'SOME BLIND'})")
    print("A PASS LICENSES: " + "; ".join(r["what_a_pass_licenses"]))
    print("A PASS DOES NOT LICENSE:")
    for x in r["what_a_pass_does_NOT_license"]:
        print(f"  - {x}")
    print(line)


if __name__ == "__main__":
    raise SystemExit(main())

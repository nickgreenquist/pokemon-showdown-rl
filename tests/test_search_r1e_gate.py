"""The R1-E gate harness's OWN tests — `scripts/search_r1e_gate.py`.

R1-E judges the write-side bridge, so the harness has to be judged first. The
failure mode this file exists to prevent is a gate that reports PASS because it
is measuring nothing: a dim classifier that lands every diff in the wrong block,
a family test that swallows an undeclared dim, a control that cannot bite, or
summary arithmetic that reports a bar as met when it is not. Every one of those
would read as a clean gate.

Four groups:

  1. THE DIM CLASSIFIER, cross-checked against `scripts/engine_p1.py`'s
     `describe_index` over ALL 828 dims. That file is an independently written
     classifier over the same `rl.envs.showdown` constants, so agreement on
     every dim is a real cross-check and not a tautology.
  2. THE FAMILY RULE: a synthetic mismatch OUTSIDE the declared families must
     FAIL leg A and be reported by dim, block and both values; one INSIDE must
     pass. Plus the backend-strictness rule -- an `S-*` family is declared on
     the stand-in and UNDECLARED on the engine backend.
  3. THE CONTROLS: each corruption must actually corrupt, and on real harvest
     roots each must be DETECTED. A control that cannot bite makes the gate
     unfalsifiable for the rule it names, which is the whole reason §3.3 exists.
  4. THE ARITHMETIC: leg A's bar checks, leg C's fractions and cause
     attribution, leg B's invariants, and `control_report`'s firing test.

Offline: no server, no checkpoints, no engine extension. The groups that need
the gitignored R1 harvest skip without it.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from poke_env.battle.move import Move as PEMove

from rl.envs.encoder_spec import GEN1
from rl.envs.showdown import (
    ACTIVE_DIM,
    GLOBAL_DIM,
    ID_DIM,
    MON_DIM,
    MOVE_DIM,
    OBS_DIM,
)

# The R1-E gate is a read of the 828-wide gen-1 observation: its dim classifier
# indexes OBS_DIM and its families are named against the v2+ids layout. Under
# the suite's documented invocation the flags are unset and OBS_DIM is 612, so
# this file SKIPS rather than mislabelling every dim -- the same gate
# tests/test_entity_scorer_factorization.py uses, and the same reason.
pytestmark = pytest.mark.skipif(
    ID_DIM == 0,
    reason="the R1-E gate reads the 828-wide encoder; set "
           "POKEMON_RL_ENCODER_V2=1 and POKEMON_RL_ENCODER_IDS=1 to run it",
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


G = _load("search_r1e_gate")

HARVEST = ROOT / "results" / "ch3_r1"
_needs_harvest = pytest.mark.skipif(
    not (HARVEST / "harvest_s62.pkl").exists(),
    reason="the R1 public harvest (results/ch3_r1/harvest_*.pkl) is gitignored",
)
# The harvested `row["obs"]` is a D26 artifact: 828-d, encoder v2 + ids. Any
# test that compares an encoding against it needs this process at that width.
_needs_d26_encoder = pytest.mark.skipif(
    OBS_DIM != 828,
    reason=f"the harvested live obs is 828-d; this process encodes {OBS_DIM}-d",
)


# ---------------------------------------------------------------------------
# 1. The dim classifier
# ---------------------------------------------------------------------------

def test_classify_dim_agrees_with_engine_p1_on_every_one_of_the_828_dims():
    """`engine_p1.describe_index` is an INDEPENDENT classifier over the same
    encoder constants (it is gate P-1's, written months earlier). Agreement on
    every dim is the cross-check; a disagreement means one of the two has the
    block boundaries wrong, and a mislabelled block silently retargets every
    family rule that keys on it."""
    p1 = _load("engine_p1")
    for i in range(OBS_DIM):
        info = G.classify_dim(i)
        theirs = p1.describe_index(i)
        block, _, field = theirs.partition(".")
        # engine_p1 spells slots as `own_mon[3]`; this harness as `own_mon3`
        ours_block = info.block.replace("ids", "ids")
        if "[" in block:
            head, _, idx = block.partition("[")
            assert ours_block == f"{head}{idx.rstrip(']')}", (i, theirs, info)
        else:
            assert ours_block == block, (i, theirs, info)
        assert info.field == field, (i, theirs, info)


def test_classify_dim_block_boundaries_come_from_the_encoder_constants():
    assert G.classify_dim(0).block == "global"
    assert G.classify_dim(GLOBAL_DIM - 1).field == "aliased"
    assert G.classify_dim(GLOBAL_DIM).block == "own_mon0"
    assert G.classify_dim(GLOBAL_DIM + MON_DIM).block == "own_mon1"
    own_active = GLOBAL_DIM + 6 * MON_DIM
    assert G.classify_dim(own_active).block == "own_active"
    assert G.classify_dim(own_active).field == f"boost[{GEN1.boost_keys[0]}]"
    own_moves = own_active + ACTIVE_DIM
    assert G.classify_dim(own_moves).block == "own_move0"
    opp_mon = own_moves + 4 * MOVE_DIM
    # the opponent mon block carries the `revealed` flag FIRST, so it is one
    # wider than our own -- getting this off by one shifts every opp field
    assert G.classify_dim(opp_mon).field == "revealed"
    assert G.classify_dim(opp_mon + 1).field == "hp"
    assert G.classify_dim(opp_mon + MON_DIM + 1).block == "opp_mon1"
    opp_active = opp_mon + 6 * (MON_DIM + 1)
    assert G.classify_dim(opp_active).block == "opp_active"
    assert G.classify_dim(OBS_DIM - ID_DIM).field == "own_species[0]"
    assert G.classify_dim(OBS_DIM - 1).field == "opp_move[3]"
    with pytest.raises(IndexError):
        G.classify_dim(OBS_DIM)


def test_the_dims_the_design_names_by_number_land_where_it_says():
    """Design §3.3 names specific dims in its `must move` column. If the
    classifier disagrees with those numbers, either the design or this harness
    is describing a different encoder."""
    if OBS_DIM != 828:
        pytest.skip("the design's dim numbers are the 828-d v2+ids encoder's")
    # C2: "dims 627 / 673 / 719 (the pp slots)", the A-1a defect's signature
    for d in (627, 673, 719):
        info = G.classify_dim(d)
        assert info.block.startswith("opp_move") and info.field == "pp", (d, info)
    # C3: "status_counter at [622]"
    assert G.classify_dim(622).block == "opp_active"
    assert G.classify_dim(622).field == "status_counter"
    # C6: "the boost block at [204..211) / [608..615)"
    for d in list(range(204, 211)) + list(range(608, 615)):
        assert G.classify_dim(d).field.startswith("boost["), (d, G.classify_dim(d))
    # C1: "the opp mon blocks [404..608) and the id suffix [814..820)"
    assert G.classify_dim(404).block == "opp_mon0"
    assert G.classify_dim(607).block == "opp_mon5"
    for d in range(814, 820):
        assert G.classify_dim(d).field.startswith("opp_species"), d


# ---------------------------------------------------------------------------
# 2. The family rule
# ---------------------------------------------------------------------------

def _facts(**kw):
    base = dict(n_revealed=2, transformed_ditto=False, own_sleeping=False,
                opp_sleeping=False, own_preparing=False, opp_preparing=False,
                trapped=False)
    base.update(kw)
    return G.RootFacts(**base)


def _dim_of(block_prefix: str, field: str) -> int:
    for i in range(OBS_DIM):
        info = G.classify_dim(i)
        if info.block.startswith(block_prefix) and info.field == field:
            return i
    raise AssertionError(f"no dim for {block_prefix}.{field}")


def test_a_mismatch_inside_a_declared_family_is_classified_not_flagged():
    opp_hp = _dim_of("opp_mon0", "hp")                 # W-HP
    assert G.classify_family(G.classify_dim(opp_hp), _facts()) == "W-HP"
    bench = _dim_of("opp_mon5", "hp")                   # slot 5 >= n_revealed
    assert G.classify_family(G.classify_dim(bench), _facts()) == "W-DET"
    prep = _dim_of("opp_active", "preparing")
    assert G.classify_family(G.classify_dim(prep), _facts()) == "S-PREPARING"
    sc = _dim_of("opp_active", "status_counter")
    assert G.classify_family(G.classify_dim(sc), _facts(opp_sleeping=True)) == \
        "S-SLEEPREST"
    ty = _dim_of("own_mon0", "type[3]")
    assert G.classify_family(G.classify_dim(ty),
                             _facts(transformed_ditto=True)) == "W-TRANSFORM"
    assert G.classify_family(G.classify_dim(3), _facts()) == "W-REQ"
    assert G.classify_family(G.classify_dim(4), _facts()) == "S-TRAPPED"


def test_a_mismatch_outside_the_declared_families_is_undeclared():
    """The rule engine_p1_run.py:127-129 enforces: 'undeclared' is a BUG, not
    a family. Each of these is a dim no declared family reaches."""
    for block, fld in (("own_mon0", "hp"), ("own_move0", "pp"),
                       ("opp_mon0", "level"), ("opp_move0", "pp"),
                       ("own_active", f"boost[{GEN1.boost_keys[1]}]"), ("global", "turn")):
        d = _dim_of(block, fld)
        assert G.classify_family(G.classify_dim(d), _facts()) == "undeclared", \
            (block, fld, d)
    # a sleeping-counter diff on a root with NOBODY asleep is not W-SLEEP
    sc = _dim_of("own_active", "status_counter")
    assert G.classify_family(G.classify_dim(sc), _facts()) == "undeclared"
    # a transform-sensitive field on a root with no transformed Ditto is not
    # W-TRANSFORM -- otherwise every stat diff anywhere would be absorbed
    ty = _dim_of("own_mon0", "type[3]")
    assert G.classify_family(G.classify_dim(ty), _facts()) == "undeclared"


def test_leg_a_FAILS_on_an_undeclared_dim_and_names_it():
    """The control on the whole of leg A. Without this the family table could
    swallow anything and the gate would still print PASS."""
    a = G.LegA()
    live = np.zeros(OBS_DIM, dtype=np.float32)
    new = live.copy()
    d = _dim_of("own_mon0", "level")
    new[d] = 0.5
    root = G.Root("s62", 0, 0, 0, 1, {"obs": live, "mask": np.zeros(10, bool)}, {})
    a.add(new, live, _facts(), root)
    rep = a.report("poke_engine")
    assert rep["pass"] is False
    assert rep["checks"]["no_undeclared_dims"] is False
    ex = rep["undeclared_examples"][0]
    assert ex["dim"] == d and ex["block"] == "own_mon0" and ex["field"] == "level"
    assert ex["constructed"] == pytest.approx(0.5) and ex["live"] == 0.0


def test_leg_a_PASSES_on_a_mismatch_inside_a_declared_family():
    a = G.LegA()
    live = np.zeros(OBS_DIM, dtype=np.float32)
    new = live.copy()
    d = _dim_of("opp_mon0", "hp")
    new[d] = 0.001                      # inside W-HP's max|delta| bar of 0.01
    root = G.Root("s62", 0, 0, 0, 1, {"obs": live, "mask": np.zeros(10, bool)}, {})
    for _ in range(10):                 # 10 roots, 1 differing dim on one of them
        a.add(new if _ == 0 else live, live, _facts(), root)
    rep = a.report("poke_engine")
    assert rep["pass"] is True
    assert rep["families"]["W-HP"]["dims_total"] == 1
    assert rep["families"]["W-HP"]["max_abs"] == pytest.approx(0.001)
    assert rep["bitwise_identical"] == 9


def test_w_hp_bar_bites_when_the_grain_is_too_coarse():
    a = G.LegA()
    live = np.zeros(OBS_DIM, dtype=np.float32)
    new = live.copy()
    new[_dim_of("opp_mon0", "hp")] = 0.5      # far outside the 0.01 max|d| bar
    root = G.Root("s62", 0, 0, 0, 1, {"obs": live, "mask": np.zeros(10, bool)}, {})
    a.add(new, live, _facts(), root)
    rep = a.report("poke_engine")
    assert rep["checks"]["w_hp_max_abs_le_bar"] is False
    assert rep["pass"] is False


def test_free_families_must_contribute_zero_dims():
    a = G.LegA()
    live = np.zeros(OBS_DIM, dtype=np.float32)
    new = live.copy()
    new[_dim_of("opp_mon5", "hp")] = 1.0      # W-DET, declared but must be ZERO
    root = G.Root("s62", 0, 0, 0, 1, {"obs": live, "mask": np.zeros(10, bool)}, {})
    a.add(new, live, _facts(), root)
    rep = a.report("poke_engine")
    assert rep["families"]["W-DET"]["dims_total"] == 1
    assert rep["checks"]["free_families_contribute_zero"] is False
    assert rep["pass"] is False


def test_stand_in_families_are_declared_only_on_the_stand_in_backend():
    """The gate must get STRICTER when the real surface lands: an `S-*` family
    is the stand-in's own artefact, so on --backend engine it is a FAIL."""
    assert "S-PREPARING" in G.declared_families("poke_engine")
    assert "S-PREPARING" not in G.declared_families("engine")
    assert "W-HP" in G.declared_families("engine")
    a = G.LegA()
    live = np.zeros(OBS_DIM, dtype=np.float32)
    new = live.copy()
    new[_dim_of("opp_active", "preparing")] = 1.0
    root = G.Root("s62", 0, 0, 0, 1, {"obs": live, "mask": np.zeros(10, bool)}, {})
    a.add(new, live, _facts(), root)
    assert a.report("poke_engine")["families"]["S-PREPARING"]["declared"] is True
    assert a.report("engine")["families"]["S-PREPARING"]["declared"] is False


def test_the_two_family_amendments_are_recorded_with_their_provenance():
    """§7's failure branch forbids loosening families silently, so the
    amendments must carry where they came from and whether they post-date the
    numbers. A1/A2 are sourced from ENGINE semantics (cargo tests in
    write_side.rs), not from R1-E's own results -- a wrong bar corrected, not
    a failed bar relaxed."""
    ids = [a["id"] for a in G.AMENDMENTS]
    assert ids == ["A1", "A2"]
    for am in G.AMENDMENTS:
        assert am["post_dates_first_numbers"] is True
        assert "write_side.rs" in am["source"] or "spec.rs" in am["source"]
        assert am["measured_here"] and am["mechanism"]
        # NEITHER amendment may move a measured quantity -- both families are
        # obs-invisible, and W-DISABLE has incidence 0 on this corpus
        assert am["effect_on_this_gate"].startswith("NONE")
    a1 = G.AMENDMENTS[0]
    assert "neither paralysed nor burned" in a1["change"]
    assert G.FAMILY_DOC["W-ACTIVESTATS"]["obs_visible"] is False
    assert "AMENDED" in G.FAMILY_DOC["W-ACTIVESTATS"]["incidence"]
    assert G.FAMILY_DOC["W-DISABLE"]["obs_visible"] is False
    assert "LEG C" in G.FAMILY_DOC["W-DISABLE"]["seen_by"]


def test_the_mask_law_skips_a_disabled_slot():
    """A2: `choices()` skips a disabled slot, so a mask that ignores
    `disabled` RE-OFFERS a move the request omits -- leg C's hard stop, not a
    residual. Vacuous on this pool; the clause is the falsifier."""
    s1 = _eside([_emon(["a", "b", "c"])])
    s1.pokemon[0].moves[1].disabled = True
    mr = G.mask_for_poke_engine_state(_estate(s1))
    assert G._legal_names(mr.mask) == ["move0", "move2"]


def test_a_charging_root_without_a_slot_is_refused_not_defaulted():
    """F6: `B_LAST_MOVES.index = 0` is `moves[-1]`, and ReleaseFast compiles
    the bounds assert out. Refusing is the only safe branch on a source that
    cannot supply the slot."""
    prep = SimpleNamespace(preparing=True, moves={"skyattack": object(),
                                                  "bodyslam": object()},
                           _preparing_move=None)
    assert G.charging_slot(prep) is None
    live = SimpleNamespace(preparing=True,
                           moves={"bodyslam": object(), "skyattack": object()},
                           _preparing_move=SimpleNamespace(id="skyattack"))
    assert G.charging_slot(live) == 2          # ONE-BASED, as the engine wants
    idle = SimpleNamespace(preparing=False, moves={"bodyslam": object()})
    assert G.charging_slot(idle) is None
    battle = SimpleNamespace(active_pokemon=prep, opponent_active_pokemon=idle)
    assert G.charging_roots_unbuildable(battle) == ["p1"]
    battle_ok = SimpleNamespace(active_pokemon=live, opponent_active_pokemon=idle)
    assert G.charging_roots_unbuildable(battle_ok) == []


def test_every_family_the_bar_names_has_a_row_in_the_family_table():
    for fam in ("W-HP", "W-STATS", "W-SLEEP", "W-CONF", "W-SUB", "W-LASTDMG",
                "W-LASTMOVE", "W-ACTIVESTATS", "W-LS", "W-ORDER", "W-SEED",
                "W-REQ", "W-DET", "W-TRANSFORM", "W-DISABLE"):
        assert fam in G.FAMILY_DOC, fam
        row = G.FAMILY_DOC[fam]
        assert set(row) >= {"fields", "class", "obs_visible", "obs_dims",
                            "why", "seen_by"}, fam
    # the honest half of the table: these are the families NEITHER leg can see,
    # and leg A reporting 0 dims for them is not evidence they are right
    invisible = {f for f, r in G.FAMILY_DOC.items() if not r["obs_visible"]}
    assert {"W-STATS", "W-ACTIVESTATS", "W-LASTDMG", "W-SEED", "W-CONF",
            "W-SUB", "W-LS", "W-ORDER", "W-SLEEP", "W-LASTMOVE",
            "W-DISABLE"} <= invisible


# ---------------------------------------------------------------------------
# 3. The mask law (leg C's oracle) and W-VALIDATE
# ---------------------------------------------------------------------------

def _emon(mid_list, hp=100, maxhp=100, pps=None):
    moves = []
    for j in range(4):
        if j < len(mid_list):
            moves.append(SimpleNamespace(id=mid_list[j],
                                         pp=(pps[j] if pps else 10)))
        else:
            moves.append(SimpleNamespace(id="none", pp=0))
    return SimpleNamespace(id=mid_list[0] if mid_list else "none", hp=hp,
                           maxhp=maxhp, moves=moves)


def _eside(mons, active=0, vols=()):
    return SimpleNamespace(pokemon=list(mons), active_index=active,
                           volatile_statuses=set(vols))


def _estate(s1, s2=None):
    return SimpleNamespace(side_one=s1, side_two=s2 or _eside([_emon(["tackle"])]))


def test_mask_offers_live_bench_and_live_moves():
    s1 = _eside([_emon(["a", "b", "c", "d"]), _emon(["e"]), _emon(["f"], hp=0)])
    mr = G.mask_for_poke_engine_state(_estate(s1))
    assert mr.request == "move" and mr.forced is False
    assert G._legal_names(mr.mask) == ["switch1", "move0", "move1", "move2", "move3"]


def test_mask_drops_a_zero_pp_move():
    """PP > 0 is one of the four things §3.2 says obs parity cannot see."""
    s1 = _eside([_emon(["a", "b"], pps=[0, 7, 0, 0])])
    mr = G.mask_for_poke_engine_state(_estate(s1))
    assert G._legal_names(mr.mask) == ["move1"]


def test_a_fainted_active_gives_a_switch_request_and_ignores_forced():
    """W-REQ first. The engine clears a fainted active's volatiles; poke-env
    leaves `must_recharge` standing on the corpse (87 roots in the R1 harvest),
    so reading `forced()` before the request masks off every switch."""
    s1 = _eside([_emon(["a"], hp=0), _emon(["b"]), _emon(["c"])],
                vols=("mustrecharge",))
    mr = G.mask_for_poke_engine_state(_estate(s1))
    assert mr.request == "switch"
    assert G._legal_names(mr.mask) == ["switch1", "switch2"]


def test_a_hard_lock_offers_nothing_rather_than_guessing_the_slot():
    """The locked slot needs S_LAST_SELECTED_MOVE, which `freeze_battle` does
    not carry (family W-LASTMOVE). Guessing would manufacture a pass."""
    s1 = _eside([_emon(["a", "b"]), _emon(["c"])], vols=("mustrecharge",))
    mr = G.mask_for_poke_engine_state(_estate(s1))
    assert mr.forced is True and mr.locked_slot == -1
    assert not mr.mask.any()


def test_forced_volatiles_match_the_engines_isForced_set():
    for v in ("mustrecharge", "rage", "thrashing", "charging"):
        assert v in G.FORCED_VOLATILES, v
    for v in ("reflect", "confusion", "substitute", "leechseed"):
        assert v not in G.FORCED_VOLATILES, v


def test_w_validate_catches_the_corruptions_it_is_for():
    good = _eside([_emon(["a", "b"]), _emon(["c"])])
    assert G.validate_poke_engine_state(_estate(good)) == []
    over = _eside([_emon(["a"], hp=200, maxhp=100), _emon(["b"])])
    assert any("hp 200 > maxhp" in p for p in G.validate_poke_engine_state(_estate(over)))
    dead = _eside([_emon(["a"], hp=0), _emon(["b"], hp=0)])
    probs = G.validate_poke_engine_state(_estate(dead))
    assert any("no unfainted mon" in p for p in probs)
    # ... but a LEAF may legitimately have a side wiped
    assert not any("no unfainted mon" in p
                   for p in G.validate_poke_engine_state(_estate(dead),
                                                         allow_terminal=True))


def test_leg_c_counts_and_attributes_causes():
    row_ok = {"obs": None, "mask": np.array([0, 1, 0, 0, 0, 0, 1, 0, 0, 0], bool)}
    frozen = {"team": [{"must_recharge": False, "preparing": False}],
              "active_index": 0, "trapped": False}
    r_ok = G.Root("s62", 0, 0, 0, 1, row_ok, frozen)
    c = G.LegC()
    m = np.zeros(10, bool)
    m[1] = m[6] = True
    c.add(G.MaskResult(m, "move", False, -1), r_ok)
    assert c.exact == 1 and c.n == 1
    # a stale must_recharge: the harvest offered a full set, the construction
    # offers nothing -- FINDING F1's shape
    frozen_stale = {"team": [{"must_recharge": True, "preparing": False}],
                    "active_index": 0, "trapped": False}
    r_bad = G.Root("s62", 0, 0, 1, 1, row_ok, frozen_stale)
    c.add(G.MaskResult(np.zeros(10, bool), "move", True, -1), r_bad)
    rep = c.report()
    assert rep["exact"] == 1 and rep["mismatches"] == 1
    assert rep["exact_frac"] == pytest.approx(0.5)
    assert any("must_recharge stale" in k for k in rep["causes"])
    # a hard lock whose slot the harvest cannot supply is a DECLARED gap and
    # must be separated from a construction defect
    frozen_prep = {"team": [{"must_recharge": False, "preparing": True}],
                   "active_index": 0, "trapped": True}
    c2 = G.LegC()
    c2.add(G.MaskResult(np.zeros(10, bool), "move", True, -1),
           G.Root("s62", 0, 0, 2, 1, row_ok, frozen_prep))
    rep2 = c2.report()
    assert rep2["declared_gap_roots"] == 1
    assert rep2["exact_frac"] == 0.0
    assert rep2["exact_frac_excluding_declared_W_LASTMOVE"] == 1.0


def test_leg_c_hard_stop_is_the_designs_995_and_the_target_is_100():
    assert G.BAR_LEG_C_HARD_STOP == 0.995 and G.LEG_C_TARGET == 1.0
    c = G.LegC()
    c.n, c.exact = 1000, 996
    assert c.report()["pass"] is True and c.report()["hit_target"] is False
    c.exact = 994
    assert c.report()["pass"] is False


# ---------------------------------------------------------------------------
# 4. RootReveal — §3.1's payload, and the A-1a rule inside it
# ---------------------------------------------------------------------------

def _pmon(species, moves, pps=None, status=None, counter=0, recharge=False):
    mv = {}
    for j, m in enumerate(moves):
        base = PEMove(m, gen=1)
        mv[m] = SimpleNamespace(id=m, current_pp=(pps[j] if pps else base.max_pp),
                                max_pp=base.max_pp)
    return SimpleNamespace(
        species=species, moves=mv,
        status=(SimpleNamespace(name=status) if status else None),
        status_counter=counter, must_recharge=recharge, preparing=False,
    )


def test_root_reveal_carries_the_A1a_rule_not_a_full_clip():
    """The defect A-1a caught: `track.rs` hard-coded `pp = max_pp`, and P-1
    could not see it. `move_uses` is the fix, and it is the ONE field a
    RootReveal cannot get wrong quietly."""
    blizzard = PEMove("blizzard", gen=1)
    mon = _pmon("articuno", ["blizzard"], pps=[blizzard.max_pp - 3])
    battle = SimpleNamespace(team={"a": mon}, opponent_team={"b": mon})
    p1, p2 = G.root_reveals(battle)
    assert p1.move_uses[0] == [3]
    # B-0: poke-env's `num` IS the engine's move id (1..165)
    assert p1.revealed_moves[0] == [int(blizzard.entry["num"])]
    assert 1 <= p1.revealed_moves[0][0] <= 165
    # §3.1's simplification: revealed mons sit at 0..n-1 in reveal order
    assert p1.reveal_order == [0]
    # six slots always, so the Rust side indexes by party slot without a branch
    assert len(p1.revealed_moves) == 6 and len(p1.sleep_observed) == 6
    assert len(p1.flags_before_faint) == 6


def test_root_reveal_sleep_observed_only_counts_when_asleep():
    awake = _pmon("tauros", ["bodyslam"], counter=3)
    asleep = _pmon("gengar", ["hypnosis"], status="SLP", counter=2)
    battle = SimpleNamespace(team={"a": awake, "b": asleep}, opponent_team={})
    p1, _ = G.root_reveals(battle)
    assert p1.sleep_observed[0] == 0 and p1.sleep_observed[1] == 2


def test_root_reveal_records_flags_before_faint():
    mon = _pmon("dragonite", ["hyperbeam"], recharge=True)
    battle = SimpleNamespace(team={"a": mon}, opponent_team={})
    p1, _ = G.root_reveals(battle)
    assert p1.flags_before_faint[0] == (True, False)
    assert p1.as_dict()["flags_before_faint"][0] == [True, False]


# ---------------------------------------------------------------------------
# 5. The controls
# ---------------------------------------------------------------------------

def test_the_designs_seven_controls_are_all_present_and_C8_is_marked_as_extra():
    ids = [c.id for c in G.CONTROLS]
    assert ids[:7] == ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    assert all(not c.beyond_design for c in G.CONTROLS[:7])
    # §3.3 names seven and every one is observation-side, so leg C -- the leg
    # §3.2 calls load-bearing -- has no control in the design as written.
    assert [c.id for c in G.CONTROLS if c.beyond_design] == ["C8"]
    assert any(f["id"] == "F3" for f in G.FINDINGS)


def test_each_control_corrupts_exactly_one_rule():
    flags = ("reveal_swap", "zero_move_uses", "sleep_off_by_one",
             "drop_faint_flags", "all_revealed", "flip_negative_boost",
             "hp_floor", "revive_fainted")
    for c in G.CONTROLS:
        assert sum(bool(getattr(c, f)) for f in flags) == 1, c.id
    assert all(not getattr(G.NO_CONTROL, f) for f in flags)


def _synthetic_battle():
    from tests.test_ch3_bridge import _mon

    ours = _mon("tauros", ["bodyslam", "blizzard", "earthquake", "hyperbeam"],
                active=True)
    bench = _mon("gengar", ["hypnosis"], hp_frac=0.0)
    theirs = _mon("chansey", ["softboiled"], level=76)
    theirs2 = _mon("starmie", ["surf"], level=76)
    return SimpleNamespace(
        active_pokemon=ours, opponent_active_pokemon=theirs,
        team={"p1: Tauros": ours, "p1: Gengar": bench},
        opponent_team={"p2: Chansey": theirs, "p2: Starmie": theirs2},
        turn=5, force_switch=False, trapped=False,
        available_moves=list(ours.moves.values()),
    )


def test_corrupt_battle_actually_corrupts():
    b = _synthetic_battle()
    b.active_pokemon.boosts["atk"] = -2
    b.active_pokemon.must_recharge = True
    b.opponent_active_pokemon.status = SimpleNamespace(name="SLP")
    b.opponent_active_pokemon.status_counter = 2

    c6 = G.corrupt_battle(_clone(b), _ctl(flip_negative_boost=True))
    assert c6.active_pokemon.boosts["atk"] == 2
    c4 = G.corrupt_battle(_clone(b), _ctl(drop_faint_flags=True))
    assert c4.active_pokemon.must_recharge is False
    c3 = G.corrupt_battle(_clone(b), _ctl(sleep_off_by_one=True))
    assert c3.opponent_active_pokemon.status_counter == 3
    c8 = G.corrupt_battle(_clone(b), _ctl(revive_fainted=True))
    revived = list(c8.team.values())[1]
    assert revived.fainted is False and revived.current_hp == 1


def _ctl(**kw):
    return G.Control("CX", "test", "test", **kw)


def _clone(b):
    import copy

    return copy.deepcopy(b)


def test_reveal_swap_reorders_only_the_revealed_prefix():
    det = {"opponents": {
        "chansey": {"live": object(), "moves": ["softboiled"]},
        "starmie": {"live": object(), "moves": ["surf"]},
        "gengar": {"live": None, "moves": ["hypnosis"]},
    }}
    out = G._apply_reveal_swap(det)
    assert list(out["opponents"]) == ["starmie", "chansey", "gengar"]
    # not applicable with fewer than two revealed mons: returns the input
    one = {"opponents": {"chansey": {"live": object()}, "gengar": {"live": None}}}
    assert G._apply_reveal_swap(one) is one


def test_zero_move_uses_restores_the_full_clip():
    from rl.search.shadow_battle import PublicView, _cached_move

    view = PublicView(frozenset({"chansey"}), {"chansey": ("softboiled",)},
                      {"chansey": {"softboiled": 1}})
    assert G._max_pp_view(view)["chansey"]["softboiled"] == \
        int(_cached_move("softboiled").max_pp)


def test_hp_floor_patch_changes_the_written_hp():
    import rl.search.bridge as br

    seen = {}
    real = br._det_pokemon

    def fake(species, move_ids, hp_fraction, *a, **kw):
        hp = int(round(float(hp_fraction) * 101))
        seen["hp"] = hp
        return SimpleNamespace(hp=hp, maxhp=101)

    br._det_pokemon = fake
    try:
        with G._hp_floor_patch():
            br._det_pokemon("chansey", ["softboiled"], hp_fraction=0.567)
        assert seen["hp"] == 57          # floor(0.567 * 101) == 57, round -> 57
        with G._hp_floor_patch():
            br._det_pokemon("chansey", ["softboiled"], hp_fraction=0.6)
        assert seen["hp"] == 60          # floor(60.6) == 60 vs round(60.6) == 61
    finally:
        br._det_pokemon = real
    assert br._det_pokemon is real       # the patch always restores


def test_control_exposure_is_counted_per_root_not_assumed():
    frozen = {
        "team": [{"must_recharge": False, "preparing": False, "fainted": False,
                  "status": None, "boosts": {"atk": 0}, "moves": [],
                  "current_hp_fraction": 1.0},
                 {"must_recharge": False, "preparing": False, "fainted": True,
                  "status": None, "boosts": {"atk": 0}, "moves": [],
                  "current_hp_fraction": 0.0}],
        "opponent_team": [{"must_recharge": False, "preparing": False,
                           "fainted": False, "status": None,
                           "boosts": {"atk": 0},
                           "moves": [("blizzard", 5)],
                           "current_hp_fraction": 0.43}],
        "active_index": 0, "opponent_active_index": 0, "trapped": False,
    }
    assert G.control_exposure(frozen, _ctl(reveal_swap=True)) is False   # 1 mon
    assert G.control_exposure(frozen, _ctl(zero_move_uses=True)) is True  # pp 5<8
    assert G.control_exposure(frozen, _ctl(sleep_off_by_one=True)) is False
    assert G.control_exposure(frozen, _ctl(hp_floor=True)) is True
    assert G.control_exposure(frozen, _ctl(revive_fainted=True)) is True
    assert G.control_exposure(frozen, _ctl(all_revealed=True)) is True
    frozen["team"][0]["boosts"]["atk"] = -1
    assert G.control_exposure(frozen, _ctl(flip_negative_boost=True)) is True


def test_control_report_fires_on_magnitude_alone_not_only_on_dim_counts():
    """C7 (floor vs round) leaves the DIFFERING-DIM SET unchanged and moves
    only the magnitudes. A count-only firing test read it as BLIND on the
    first 400-root sample; this is that bug pinned."""
    base = G.LegA(n=2, bitwise_identical=0, total_dims=2, sig=[(1, 100), (1, 100)])
    same_count = G.LegA(n=2, bitwise_identical=0, total_dims=2,
                        sig=[(1, 250), (1, 100)])
    rep = G.control_report(G.CONTROLS[6], base, G.LegC(n=2, exact=2),
                           same_count, G.LegC(n=2, exact=2), 0.1)
    assert rep["fires"] is True and rep["status"] == "FIRES"
    assert rep["leg_a"]["roots_moved"] == 1
    assert rep["leg_a"]["roots_moved_magnitude_only"] == 1
    assert rep["leg_a"]["delta_dims_per_root"] == 0.0


def test_control_report_separates_BLIND_from_NOT_EXPOSED():
    base = G.LegA(n=2, total_dims=2, sig=[(1, 100), (1, 100)])
    inert_exposed = G.LegA(n=2, exposed=2, total_dims=2, sig=[(1, 100), (1, 100)])
    r = G.control_report(G.CONTROLS[0], base, G.LegC(n=2, exact=2),
                         inert_exposed, G.LegC(n=2, exact=2), 0.1)
    assert r["status"] == "BLIND" and "DID NOT BREAK THE GATE" in r["FINDING"]
    inert_unexposed = G.LegA(n=2, exposed=0, total_dims=2, sig=[(1, 100), (1, 100)])
    r2 = G.control_report(G.CONTROLS[0], base, G.LegC(n=2, exact=2),
                          inert_unexposed, G.LegC(n=2, exact=2), 0.1)
    assert r2["status"] == "NOT_EXPOSED" and "coverage" in r2["FINDING"]
    assert r2["fires"] is False


def test_a_control_that_moves_leg_c_fires_even_with_leg_a_unchanged():
    base = G.LegA(n=2, total_dims=0, sig=[(0, 0), (0, 0)])
    same = G.LegA(n=2, exposed=2, total_dims=0, sig=[(0, 0), (0, 0)])
    r = G.control_report(G.CONTROLS[7], base, G.LegC(n=2, exact=2), same,
                         G.LegC(n=2, exact=1), 0.1)
    assert r["fires"] is True and r["leg_c"]["delta_exact"] == -1


# ---------------------------------------------------------------------------
# 6. End to end on real harvest roots — every control must be DETECTED
# ---------------------------------------------------------------------------

def _exposed_roots(ctl, want=6, scan=2500):
    out = []
    for root in G.iter_corpus(HARVEST, limit=scan):
        if G.control_exposure(root.frozen, ctl):
            out.append(root)
            if len(out) >= want:
                break
    return out


@_needs_harvest
@_needs_d26_encoder
@pytest.mark.parametrize("ctl", G.CONTROLS, ids=[c.id for c in G.CONTROLS])
def test_every_control_is_detected_on_real_roots(ctl):
    """§3.3's whole purpose: 'a gate that still reports 0 mismatches is blind'.
    The roots are chosen to be EXPOSED to the rule the control corrupts --
    without that, a control that never bites is indistinguishable from a gate
    that cannot see it (measured: C7 read BLIND on 30 early-turn roots where
    every opponent mon sat at hp_fraction 1.0)."""
    roots = _exposed_roots(ctl)
    if not roots:
        pytest.skip(f"{ctl.id}'s rule does not occur in the scanned prefix")
    be = G.PokeEngineBackend()
    base_a, base_c = G.run_leg_ac(be, roots, G.NO_CONTROL)
    ca, cc = G.run_leg_ac(be, roots, ctl)
    rep = G.control_report(ctl, base_a, base_c, ca, cc, 0.0)
    assert rep["fires"] is True, (ctl.id, rep)
    assert rep["exposed_roots"] == len(roots)


@_needs_harvest
@_needs_d26_encoder
def test_the_as_is_control_reproduces_S1s_artefact():
    """C5 is the strongest control: it removes the information boundary and
    must reproduce DET_BLIND.md:61's ~35.9 dims/root. It proves R1-E measures
    the BOUNDARY, not the plumbing."""
    roots = list(G.iter_corpus(HARVEST, limit=200))
    be = G.PokeEngineBackend()
    base_a, _ = G.run_leg_ac(be, roots, G.NO_CONTROL)
    ca, _ = G.run_leg_ac(be, roots, G.CONTROLS[4])
    assert base_a.total_dims / base_a.n < 2.0
    assert 25.0 < ca.total_dims / ca.n < 50.0
    assert ca.fam_dims["W-DET"] > 0


@_needs_harvest
@_needs_d26_encoder
def test_C2_moves_the_opponent_pp_dims_the_A1a_defect_moved():
    """The defect this gate exists for. C2 re-introduces it exactly, and the
    dims it moves must be the opponent move-pp slots -- 627/673/719 at the
    828-d encoder, the ones A-1a separated by 10x."""
    roots = _exposed_roots(G.CONTROLS[1], want=25)
    be = G.PokeEngineBackend()
    base_a, _ = G.run_leg_ac(be, roots, G.NO_CONTROL)
    ca, _ = G.run_leg_ac(be, roots, G.CONTROLS[1])
    moved = {f for f, n in ca.top_fields.items() if n > base_a.top_fields.get(f, 0)}
    assert any(f.startswith("opp_move") and f.endswith(".pp") for f in moved), moved
    # and it must land OUTSIDE every declared family -- the opponent's revealed
    # PP is exact under the A-1a rule, so a diff there is a BUG, not a family
    assert ca.fam_dims["undeclared"] > base_a.fam_dims["undeclared"]


@_needs_harvest
@_needs_d26_encoder
def test_C8_is_the_only_control_that_moves_leg_c_today():
    """FINDING F3/F4, pinned: on the stand-in, C1-C7 move leg A and leave leg
    C at 100%. If this ever changes, the finding is stale and the doc is
    wrong -- which is the point of pinning it."""
    roots = list(G.iter_corpus(HARVEST, limit=400))
    be = G.PokeEngineBackend()
    _, base_c = G.run_leg_ac(be, roots, G.NO_CONTROL)
    moved = []
    for ctl in G.CONTROLS:
        _, cc = G.run_leg_ac(be, roots, ctl)
        if cc.exact != base_c.exact:
            moved.append(ctl.id)
    assert moved == ["C8"], moved


@_needs_harvest
@_needs_d26_encoder
def test_the_gate_runs_end_to_end_and_the_summary_arithmetic_holds(tmp_path):
    rc = G.main(["--harvest", str(HARVEST), "--out", str(tmp_path),
                 "--limit", "120", "--control-limit", "40",
                 "--leg-b-limit", "20"])
    import json

    rep = json.loads((tmp_path / "r1e.json").read_text())
    a, b, c = rep["leg_a"], rep["leg_b"], rep["leg_c"]
    assert rc in (0, 1)
    # leg A arithmetic
    assert a["n_roots"] == 120
    assert a["bitwise_identical_frac"] == pytest.approx(
        a["bitwise_identical"] / a["n_roots"])
    assert a["dims_per_root"] == pytest.approx(a["dims_total"] / a["n_roots"])
    assert sum(f["dims_total"] for f in a["families"].values()) == a["dims_total"]
    for fam, s in a["families"].items():
        assert s["dims_per_root"] == pytest.approx(s["dims_total"] / a["n_roots"])
        assert s["root_incidence"] == pytest.approx(s["roots"] / a["n_roots"])
        assert s["roots"] <= a["n_roots"]
    # leg C arithmetic
    assert c["exact"] + c["mismatches"] == c["n_roots"]
    assert c["exact_frac"] == pytest.approx(c["exact"] / c["n_roots"])
    assert sum(c["causes"].values()) == c["mismatches"]
    # leg B is INTERNAL-ONLY and must say so in the artefact, not only in chat
    assert "NEVER PARITY" in b["DISCLOSURE"]
    assert b["cross_simulator"]["status"].startswith("SELF-COMPARISON")
    # the verdict composes exactly the three things it claims to compose
    v = rep["verdict"]
    assert v["R1E_PASS"] == (a["pass"] and c["pass"] and not rep["blind_controls"])
    # leg B is reported and NEVER a parity verdict input
    assert "leg_b_pass" in v
    # provenance
    p = rep["provenance"]
    assert p["git_sha"] and p["obs_dim"] == OBS_DIM
    assert p["encoder_fingerprint"]["obs_dim"] == OBS_DIM
    assert "harvest_s62.pkl" in p["corpus"]
    assert len(p["corpus"]["harvest_s62.pkl"]["sha256"]) == 64
    # the one-directional framing must be in the artefact
    assert rep["what_a_pass_does_NOT_license"]
    assert any("leaf" in x for x in rep["what_a_pass_does_NOT_license"])


@_needs_harvest
def test_the_corpus_is_the_non_aliased_roots_and_only_those():
    n = sum(1 for _ in G.iter_corpus(HARVEST))
    # §2.5's census: 13,702 rows, 306 aliased -> 13,396 non-aliased
    assert n == 13396
    assert all(not r.row["aliased"] for r in G.iter_corpus(HARVEST, limit=500))
    # --limit and the stride are honoured exactly
    assert sum(1 for _ in G.iter_corpus(HARVEST, limit=37)) == 37


def test_the_engine_backend_raises_with_the_symbols_it_waits_on(monkeypatch):
    """A gate that silently fell back to the stand-in would report the
    stand-in's numbers under the engine's name. R7 B6 (2026-09-23) landed every
    symbol, so where the extension is installed the seam is complete and the
    refusal is exercised by withholding one (before B6 this test expected the
    whole list, and it failed on the branch from B6 on)."""
    pytest.importorskip("pkmn_gen1")
    assert G.EngineBackend.missing() == []
    (name, _), *rest = G.EngineBackend._NEEDED
    monkeypatch.setattr(G.EngineBackend, "_NEEDED", ((name, lambda: False), *rest))
    be = G.EngineBackend()
    with pytest.raises(NotImplementedError) as exc:
        be.build(object(), {}, G.NO_CONTROL)
    msg = str(exc.value)
    assert "BattleSpec" in msg and "from_root" not in msg

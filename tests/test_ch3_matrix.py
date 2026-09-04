"""CH3 R1 matrix/agent tests: the L6 mapping law's plumbing, determinism
(D2/D3/D4), the raising watchdog, and the force-switch/locked-opponent
column substitutions. Offline: no server, no checkpoints (stub critic)."""

import numpy as np
import pytest
from poke_env.data import GenData

from rl.search.matrix import (
    DOSES,
    Dose,
    SearchWatchdogError,
    decision_rng,
    our_action_str,
    solve_decision,
)
from tests.test_ch3_bridge import _battle, _mon

_TYPE_CHART = GenData.from_format("gen1randombattle").type_chart


def _two_mon_battle():
    b = _battle()
    b.team["p1: Chansey"] = _mon(
        "chansey", ["softboiled", "icebeam", "thunderwave", "counter"]
    )
    return b


def _straddle_battle():
    # A fixture where `dmg` is LOAD-BEARING. At 25% HP the opponent straddles
    # the KO threshold on some branch, so expand_leaf's 2-point roll expansion
    # splits it and the leaf set depends on the damage rolls (measured on this
    # tree: real engine dmg -> search/leaves 103, search/expanded_leaves 12;
    # dmg=None -> 97 / 0). On the full-HP _two_mon_battle() NO branch straddles,
    # so every dmg (real, None, or wrong) yields the identical leaf set, EVs and
    # action — any dmg-handling test built on it is vacuous (F-14 review).
    b = _two_mon_battle()
    theirs = _mon("chansey", ["softboiled"], level=76, hp_frac=0.25)
    b.opponent_active_pokemon = theirs
    b.opponent_team = {"p2: Chansey": theirs}
    return b


def _mask(moves=True, switches=()):
    m = np.zeros(10, dtype=bool)
    if moves:
        m[6:10] = True
    for i in switches:
        m[i] = True
    return m


def _uniform_q():
    return np.full(6, 1.0 / 6.0)


def _zero_critic(batch):
    return np.zeros(batch.shape[0])


def _obs_critic(batch):
    # Non-zero and obs-dependent, so two DIFFERENT leaf sets give different
    # EVs: under _zero_critic every row EV is exactly 0.0, which leaves
    # search/row_ev and search/ev_matrix blind to the leaf set (F-14 review).
    return np.tanh(batch.sum(axis=1) / 100.0)


def test_our_action_str_mapping():
    b = _two_mon_battle()
    assert our_action_str(b, 1) == "chansey"  # switch: team slot 1
    assert our_action_str(b, 6) == "bodyslam"  # move slot 0
    assert our_action_str(b, 9) == "hyperbeam"


def test_solve_decision_deterministic_under_key():
    b = _two_mon_battle()
    prior = np.full(10, 0.1)
    outs = []
    for _ in range(2):
        rng = decision_rng(62, 3, b.turn, 7)
        outs.append(
            solve_decision(
                b, _mask(switches=[1]), _uniform_q(), prior,
                DOSES["S"], rng, _zero_critic, _TYPE_CHART,
            )
        )
    (a1, s1), (a2, s2) = outs
    assert a1 == a2
    assert s1["search/leaves"] == s2["search/leaves"]
    assert s1["search/row_ev"] == s2["search/row_ev"]


def test_tie_break_prior_then_lowest_index():
    # zero critic -> every row EV is exactly 0.0 -> prior decides (D3)
    b = _two_mon_battle()
    prior = np.zeros(10)
    prior[8] = 0.9  # blizzard
    rng = decision_rng(62, 0, b.turn, 0)
    action, stats = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), prior,
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 8
    # flat prior too: lowest action index wins
    rng = decision_rng(62, 0, b.turn, 0)
    action, _ = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 1


def test_watchdog_raises_never_falls_back():
    b = _two_mon_battle()
    tiny = Dose(n_det=1, top_branches=6, leaf_cap=324, node_cap=3)
    rng = decision_rng(62, 0, b.turn, 0)
    with pytest.raises(SearchWatchdogError):
        solve_decision(
            b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
            tiny, rng, _zero_critic, _TYPE_CHART,
        )


@pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
def test_interrupt_inside_calculate_damage_propagates(monkeypatch, exc):
    # F-14: the damage-attribution guard degrades engine errors to "no
    # attribution", never an interrupt — a Ctrl-C mid-search must stop it.
    # BOTH members of the guard's re-raise tuple are covered on purpose:
    # narrowing it to `except KeyboardInterrupt`, or reordering so SystemExit
    # falls into the `except BaseException` arm, restores half the defect
    # (a `sys.exit()` in a search seat would degrade to dmg=None and run on).
    def interrupted(*args):
        raise exc

    monkeypatch.setattr("rl.search.matrix.calculate_damage", interrupted)
    b = _two_mon_battle()
    rng = decision_rng(62, 0, b.turn, 0)
    with pytest.raises(exc):
        solve_decision(
            b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
            DOSES["S"], rng, _zero_critic, _TYPE_CHART,
        )


def test_engine_panic_inside_calculate_damage_degrades_to_no_attribution(monkeypatch):
    # F-14 twin: poke_engine is PyO3, so a Rust panic surfaces as
    # pyo3_runtime.PanicException — a BaseException that is NOT an Exception
    # (verified in this env: MRO [PanicException, BaseException, object]; the
    # module is created lazily on first panic and cannot be imported, hence
    # the stand-in class). The guard must degrade it to dmg=None exactly as
    # the pre-F-14 `except BaseException` did — never let it kill the decision.
    # Do not "simplify" the guard back to `except Exception`.
    class PanicException(BaseException):
        pass

    calls = []

    def panicked(*args):
        calls.append(args[1:3])  # (our action str, their action str)
        raise PanicException("index out of bounds: the len is 1 but the index is 8")

    # _straddle_battle, not _two_mon_battle: dmg must be load-bearing or the
    # comparisons below hold for ANY dmg handling and prove nothing.
    b = _straddle_battle()
    args = (b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1), DOSES["S"])

    def solve():
        return solve_decision(
            *args, decision_rng(62, 0, b.turn, 0), _obs_critic, _TYPE_CHART
        )

    # Record what the guard actually hands the expansion. "Degrades to
    # dmg=None" is the claim, and a wrong-but-plausible dmg can be
    # behaviourally identical to None on any one fixture (measured: a mutant
    # guard setting dmg=([999,999],[999,999]) passes the stats pin below), so
    # the stats comparison alone does not pin the value.
    from rl.search.expansion import expand_leaf

    seen_dmg = []

    def recording_expand_leaf(state, leaf, dmg):
        seen_dmg.append(dmg)
        return expand_leaf(state, leaf, dmg)

    real_a, real_s = solve()  # unpatched: the engine's real max-damage rolls
    monkeypatch.setattr("rl.search.matrix.expand_leaf", recording_expand_leaf)
    monkeypatch.setattr("rl.search.matrix.calculate_damage", panicked)
    got_a, got_s = solve()
    assert calls, "the guarded calculate_damage call was never reached"
    panic_dmg = list(seen_dmg)
    assert panic_dmg and all(d is None for d in panic_dmg)
    monkeypatch.setattr("rl.search.matrix.calculate_damage", lambda *a: None)
    want_a, want_s = solve()

    keys = ("search/leaves", "search/expanded_leaves", "search/row_ev", "search/ev_matrix")
    assert got_a == want_a
    for k in keys:
        assert got_s[k] == want_s[k], k
    # ...and the pin has power: on this fixture the real rolls DO split
    # branches, so a guard that swallowed the panic with a wrong dmg (rather
    # than None) would land on the real-dmg side of these inequalities.
    assert real_s["search/expanded_leaves"] > 0 and got_s["search/expanded_leaves"] == 0
    for k in keys:
        if k != "search/expanded_leaves":
            assert real_s[k] != got_s[k], k


def test_force_switch_single_none_column():
    b = _two_mon_battle()
    b.force_switch = True
    b.active_pokemon.current_hp_fraction = 0.0
    b.active_pokemon.fainted = True
    b.active_pokemon.current_hp = 0
    rng = decision_rng(62, 0, b.turn, 0)
    action, stats = solve_decision(
        b, _mask(moves=False, switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["M"], rng, _zero_critic, _TYPE_CHART,
    )
    assert action == 1
    assert stats["search/cols"] == 1
    assert stats["search/force_switch"] == 1
    assert stats["oppact/other_move_mass"] == 0.0


def test_locked_opponent_substituted_to_none():
    b = _two_mon_battle()
    b.opponent_active_pokemon.must_recharge = True
    rng = decision_rng(62, 0, b.turn, 0)
    _, stats = solve_decision(
        b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    assert stats["search/opp_locked"] == 1
    assert stats["search/cols"] == 1


def test_cell_count_and_other_move_mass():
    b = _two_mon_battle()
    q = np.array([0.3, 0.2, 0.1, 0.1, 0.2, 0.1])
    rng = decision_rng(62, 1, b.turn, 2)
    _, stats = solve_decision(
        b, _mask(switches=[1]), q, np.full(10, 0.1),
        DOSES["S"], rng, _zero_critic, _TYPE_CHART,
    )
    # 4 slots + SWITCH, OTHER_MOVE never simulated
    assert stats["search/cols"] == 5
    assert stats["oppact/other_move_mass"] == pytest.approx(0.2)
    assert stats["search/rows"] == 5  # 4 moves + 1 switch
    assert stats["search/leaves"] <= DOSES["S"].leaf_cap


def _engine_state(our_hp=300, their_hp=300, their_moves=("tackle",)):
    from poke_engine import Move as EMove
    from poke_engine import Pokemon as EPokemon
    from poke_engine import PokemonIndex, Side, State

    def emon(mid, moves, hp):
        return EPokemon(
            id=mid, level=68, types=("normal", "typeless"), hp=hp, maxhp=300,
            attack=200, defense=190, special_attack=150, special_defense=150,
            speed=220, status="none",
            moves=[EMove(id=m, pp=16, disabled=False) for m in moves],
        )

    return State(
        side_one=Side(pokemon=[emon("tauros", ["bodyslam"], our_hp)],
                      active_index=PokemonIndex.P0),
        side_two=Side(pokemon=[emon("chansey", list(their_moves), their_hp)],
                      active_index=PokemonIndex.P0),
    )


def test_ko_mass_exact_discrete_rolls():
    from rl.search.expansion import _ko_mass

    # floor(100 * r / 255) >= 93  <=>  r >= 238 -> 18 of the 39 rolls
    assert _ko_mass(100, 93) == 18 / 39
    assert _ko_mass(100, 101) == 0.0
    assert _ko_mass(100, 50) == 1.0


def test_roll_expansion_splits_straddling_branch():
    from poke_engine import calculate_damage, generate_instructions

    from rl.search.expansion import expand_leaf

    # bodyslam normal: max 79, avg 73 -> a 75-hp defender straddles the KO
    state = _engine_state(their_hp=75)
    dmg = calculate_damage(state, "bodyslam", "tackle", True)
    branches = generate_instructions(state, "bodyslam", "tackle")
    for br in branches:
        leaf = state.apply_instructions(br)
        them = leaf.side_two.pokemon[0]
        if 0 < them.hp < 75:  # the normal-hit branch (survived at average)
            out = expand_leaf(state, leaf, dmg)
            assert len(out) == 2
            (lv_no, w_no), (lv_ko, w_ko) = out
            assert abs(w_no + w_ko - 1.0) < 1e-9
            assert lv_ko.side_two.pokemon[0].hp == 0
            assert lv_no.side_two.pokemon[0].hp == them.hp
            # floor(79 r/255) >= 75 <=> r >= 243 -> 13/39
            assert abs(w_ko - 13 / 39) < 1e-9
            break
    else:
        raise AssertionError("no survived normal-hit branch found")


def test_ko_skip_recharge_stripped_on_kill():
    from poke_engine import calculate_damage, generate_instructions

    from rl.search.expansion import expand_leaf
    from rl.search.shadow_battle import shadow_battle

    # The engine already skips recharge on its OWN KO branches (measured).
    # The strip matters for EXPANSION-CREATED KO variants: a survived-at-
    # average hyper beam branch carries MUSTRECHARGE, and its high-roll KO
    # variant must drop it (gen1 KO-skip).
    probe = _engine_state(their_hp=300, their_moves=("tackle",))
    probe2 = _engine_state(their_hp=300)
    dmg_probe = calculate_damage(
        _hyperbeam_state(300), "hyperbeam", "tackle", True
    )
    normal_max = min(c for c in dmg_probe[0] if c > 0)
    hp = int(0.95 * normal_max)  # avg (0.925x) survives, max roll kills
    state = _hyperbeam_state(hp)
    dmg = calculate_damage(state, "hyperbeam", "tackle", True)
    branches = generate_instructions(state, "hyperbeam", "tackle")
    checked = False
    for br in branches:
        leaf = state.apply_instructions(br)
        them = leaf.side_two.pokemon[0]
        has_recharge = any(
            v.lower() == "mustrecharge" for v in leaf.side_one.volatile_statuses
        )
        if 0 < them.hp < hp and has_recharge:
            variants = expand_leaf(state, leaf, dmg)
            ko = [lv for lv, _w in variants if lv.side_two.pokemon[0].hp <= 0]
            alive = [lv for lv, _w in variants if lv.side_two.pokemon[0].hp > 0]
            assert ko and alive
            assert all(
                "mustrecharge" not in {v.lower() for v in lv.side_one.volatile_statuses}
                for lv in ko
            )
            assert all(
                "mustrecharge" in {v.lower() for v in lv.side_one.volatile_statuses}
                for lv in alive
            )
            assert not shadow_battle(ko[0], turn=2).active_pokemon.must_recharge
            assert shadow_battle(alive[0], turn=2).active_pokemon.must_recharge
            checked = True
    assert checked, "no survived hyper beam branch with recharge found"


def _hyperbeam_state(their_hp):
    from poke_engine import Move as EMove
    from poke_engine import Pokemon as EPokemon
    from poke_engine import PokemonIndex, Side, State

    def emon(mid, moves, hp):
        return EPokemon(
            id=mid, level=68, types=("normal", "typeless"), hp=hp, maxhp=300,
            attack=200, defense=190, special_attack=150, special_defense=150,
            speed=220, status="none",
            moves=[EMove(id=m, pp=16, disabled=False) for m in moves],
        )

    return State(
        side_one=Side(pokemon=[emon("tauros", ["hyperbeam"], 300)],
                      active_index=PokemonIndex.P0),
        side_two=Side(pokemon=[emon("chansey", ["tackle"], their_hp)],
                      active_index=PokemonIndex.P0),
    )


def test_healaware_band_reduces_to_strict_and_keeps_roll_variance():
    """The battery's heal-aware SECONDARY band (scripts/ch3_fidelity_check):
    identical to the strict band on a single pure-damage branch; on a
    net-heal branch (rest/softboiled + incoming damage) it must keep the
    incoming move's roll variance, which the strict band (zero variance at
    dmg_br <= 0) falsely fails."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from ch3_fidelity_check import _hp_band_ok, _hp_band_ok_ctx

    # pure damage: ctx band == strict band (d_move == dmg_br)
    for obs in (85, 92, 100, 108, 112):
        assert _hp_band_ok_ctx(obs, 100, 1.5, 100) == _hp_band_ok(obs, 100, 1.5)
    # net heal: rest 150 - incoming avg 100 => dmg_br = -50; observed low
    # roll (-58) and high roll (-42) are real outcomes the strict band fails
    assert not _hp_band_ok(-58, -50, 1.5)
    assert _hp_band_ok_ctx(-58, -50, 1.5, 100)
    assert _hp_band_ok_ctx(-42, -50, 1.5, 100)
    # but an outcome outside the move's roll band still fails
    assert not _hp_band_ok_ctx(-75, -50, 1.5, 100)
    assert not _hp_band_ok_ctx(-20, -50, 1.5, 100)
    # no damage event at all: exact, same as strict
    assert _hp_band_ok_ctx(-150, -150, 1.5, 0)
    assert not _hp_band_ok_ctx(-140, -150, 1.5, 0)

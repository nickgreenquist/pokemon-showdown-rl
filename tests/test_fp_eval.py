"""Is our port of Foul Play's gen-1 evaluator FAITHFUL?

`rl/search/fp_eval.py` reimplements `poke-engine 0.0.48`'s
`src/gen1/evaluate.rs` in Python because the Rust `evaluate` is not bound into
the extension. A silent divergence would invalidate every experiment built on
it, and "it looked right" is not a check — so every expected value below is
HAND-COMPUTED FROM THE RUST SOURCE and written out term by term in its own
comment. If a constant ever moves upstream these tests fail, which is the
point.
"""
import math

import pytest

from rl.search.fp_eval import (
    BOOST_MULTIPLIER,
    POKEMON_ALIVE,
    POKEMON_HP,
    evaluate,
    leaf_value,
    sigmoid,
)


class FakeMove:
    def __init__(self, mid):
        self.id = mid


class FakePokemon:
    def __init__(self, hp=100, maxhp=100, status="none", moves=(),
                 attack=100, special_attack=100, pid="pikachu"):
        self.hp, self.maxhp, self.status = hp, maxhp, status
        self.moves = [FakeMove(m) for m in moves]
        self.attack, self.special_attack = attack, special_attack
        self.id = pid


class FakeSide:
    def __init__(self, pokemon, active_index=0, volatile_statuses=(),
                 attack_boost=0, defense_boost=0, special_attack_boost=0,
                 speed_boost=0):
        self.pokemon = pokemon
        self.active_index = active_index
        self.volatile_statuses = set(volatile_statuses)
        self.attack_boost = attack_boost
        self.defense_boost = defense_boost
        self.special_attack_boost = special_attack_boost
        self.speed_boost = speed_boost


class FakeState:
    def __init__(self, s1, s2):
        self.side_one, self.side_two = s1, s2


def one(**kw):
    return FakeSide([FakePokemon(**kw)])


def test_mirror_positions_score_zero():
    """The function is side_one - side_two, so identical sides cancel."""
    assert evaluate(FakeState(one(), one())) == 0.0


def test_a_single_full_health_pokemon_is_alive_plus_hp():
    # evaluate_pokemon: POKEMON_HP * 1.0 = 100, floor(>=0), + POKEMON_ALIVE 30
    s = FakeState(one(), FakeSide([FakePokemon(hp=0)]))
    assert s.side_two.pokemon[0].hp == 0          # fainted: contributes nothing
    assert evaluate(s) == pytest.approx(POKEMON_HP + POKEMON_ALIVE)   # 130


def test_half_health_halves_only_the_hp_term():
    s = FakeState(one(hp=50), FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(50.0 + POKEMON_ALIVE)          # 80


@pytest.mark.parametrize("status,expected", [
    # 100 hp + status, floored at 0, + 30 alive
    ("freeze", 100 - 40 + 30),      # FROZEN -40   -> 90
    ("sleep", 100 - 25 + 30),       # ASLEEP -25   -> 105
    ("paralyze", 100 - 25 + 30),    # PARALYZED    -> 105
    ("toxic", 100 - 30 + 30),       # TOXIC -30    -> 100
    ("poison", 100 - 10 + 30),      # POISONED -10 -> 120
    ("none", 100 + 30),             #              -> 130
])
def test_status_terms_match_the_rust_constants(status, expected):
    s = FakeState(one(status=status), FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(expected)


def test_the_floor_is_applied_before_alive_not_after():
    """`if score < 0.0 { score = 0.0 }` sits BEFORE `score += POKEMON_ALIVE`.

    A 1-hp toxic mon: hp term 100*1/100... use 1/100 hp so the hp term is 1.0
    and toxic -30 drives it to -29, which floors to 0 and THEN gains 30.
    Applying the floor after ALIVE would give max(1 - 30 + 30, 0) = 1.
    """
    s = FakeState(one(hp=1, maxhp=100, status="toxic"),
                  FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(POKEMON_ALIVE)     # 30, not 1


def test_burn_scales_with_physical_move_count():
    """evaluate_burned: (# physical moves) * -25, halved if spa > atk."""
    # two physical moves (tackle, earthquake), physical attacker
    s = FakeState(one(status="burn", moves=("tackle", "earthquake"),
                      attack=100, special_attack=50),
                  FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(100 + 2 * -25 + 30)            # 80
    # same moves, SPECIAL attacker -> multiplier halved
    s = FakeState(one(status="burn", moves=("tackle", "earthquake"),
                      attack=50, special_attack=100),
                  FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(100 + 1 * -25 + 30)            # 105
    # no physical moves -> burn is FREE
    s = FakeState(one(status="burn", moves=("flamethrower", "thunderbolt")),
                  FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(100 + 30)                      # 130


def test_volatiles_and_boosts_count_for_the_ACTIVE_pokemon_only():
    bench = FakePokemon()
    active = FakePokemon()
    # substitute +40 on the active (index 1), nothing on the bench
    s1 = FakeSide([bench, active], active_index=1, volatile_statuses=("substitute",))
    s2 = FakeSide([FakePokemon(hp=0), FakePokemon(hp=0)])
    assert evaluate(FakeState(s1, s2)) == pytest.approx(2 * 130 + 40)
    # the same volatile with the OTHER mon active must not apply to the bench
    s1b = FakeSide([bench, active], active_index=0, volatile_statuses=("substitute",))
    assert evaluate(FakeState(s1b, s2)) == pytest.approx(2 * 130 + 40)


@pytest.mark.parametrize("boost,mult", sorted(BOOST_MULTIPLIER.items()))
def test_boost_multipliers_are_nonlinear_and_saturating(boost, mult):
    s = FakeState(one() if boost == 0 else FakeSide([FakePokemon()], attack_boost=boost),
                  FakeSide([FakePokemon(hp=0)]))
    assert evaluate(s) == pytest.approx(130 + mult * 30.0)
    # the curve saturates: +4 -> 3.0 but +6 -> only 3.3
    assert BOOST_MULTIPLIER[6] < 2 * BOOST_MULTIPLIER[3]


def test_antisymmetry_swapping_sides_negates_the_score():
    a = FakeSide([FakePokemon(hp=70, status="paralyze"), FakePokemon(hp=100)],
                 active_index=0, volatile_statuses=("reflect",), attack_boost=2)
    b = FakeSide([FakePokemon(hp=40), FakePokemon(hp=0)], active_index=0,
                 volatile_statuses=("leechseed",), speed_boost=-1)
    assert evaluate(FakeState(a, b)) == pytest.approx(-evaluate(FakeState(b, a)))


def test_pyo3_string_active_index_is_normalised():
    """`active_index` comes back as a STRING on some pyo3 builds; indexing with
    it raised a TypeError that a bare `except` swallowed on 2026-09-11."""
    s1 = FakeSide([FakePokemon(), FakePokemon()], active_index="PokemonIndex.P1",
                  volatile_statuses=("substitute",))
    s2 = FakeSide([FakePokemon(hp=0), FakePokemon(hp=0)])
    assert evaluate(FakeState(s1, s2)) == pytest.approx(2 * 130 + 40)


def test_the_sigmoid_matches_the_rust_comment():
    """src/mcts.rs: "Tuned so that ~200 points is very close to 1.0"."""
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(200.0) == pytest.approx(1 / (1 + math.exp(-2.5)), rel=1e-9)
    assert sigmoid(200.0) > 0.92
    assert sigmoid(400.0) > 0.99
    assert sigmoid(-200.0) == pytest.approx(1 - sigmoid(200.0))


def test_leaf_value_is_a_difference_from_the_root_on_our_scale():
    """Foul Play's whole construction: the leaf is scored RELATIVE to the
    root, so a constant bias in the evaluator cancels."""
    root = FakeState(one(hp=100), FakeSide([FakePokemon(hp=100)]))
    leaf_better = FakeState(one(hp=100), FakeSide([FakePokemon(hp=50)]))
    r = evaluate(root)
    assert r == 0.0
    v = leaf_value(leaf_better, r)
    assert 0.0 < v < 1.0                       # better than the root, not terminal
    # and on OUR scale: 2*sigmoid - 1, so an unchanged position is exactly 0
    assert leaf_value(root, r) == pytest.approx(0.0)
    # a constant offset applied to BOTH root and leaf changes nothing, which is
    # the property that makes a biased evaluator usable inside a tree
    assert leaf_value(leaf_better, r) == pytest.approx(
        2 * sigmoid(evaluate(leaf_better) - r) - 1)

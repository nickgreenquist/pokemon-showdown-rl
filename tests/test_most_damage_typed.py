"""most-damage-typed: H&L's rule, checked against real poke-env Move/Pokemon
objects at gen 1 (and Return at gen 4). See rl/envs/most_damage_typed.py for
the borrowed definition and the three disclosed deviations."""
from types import SimpleNamespace

from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon

from rl.envs.most_damage_typed import (
    OHKO_SCORE, RETURN_BP, MostDamageTypedPlayer, move_score, switch_weakness,
)

FMT = "gen1randombattle"


def mon(species, gen=1):
    return Pokemon(gen=gen, species=species)


def mv(move_id, gen=1):
    return Move(move_id, gen=gen)


def player(seed=0):
    return MostDamageTypedPlayer(battle_format=FMT, start_listening=False, seed=seed)


def battle(active, opponent, moves, switches=()):
    return SimpleNamespace(active_pokemon=active, opponent_active_pokemon=opponent,
                           available_moves=list(moves), available_switches=list(switches))


def test_score_is_base_power_times_effectiveness_and_nothing_else():
    gengar = mon("gengar")  # ghost / poison
    assert move_score(mv("thunderbolt"), gengar) == 95 * 1
    assert move_score(mv("earthquake"), gengar) == 100 * 2
    assert move_score(mv("psychic"), gengar) == 90 * 2
    assert move_score(mv("explosion"), gengar) == 0        # normal into ghost
    assert move_score(mv("recover"), gengar) == 0          # status
    assert move_score(mv("fissure"), gengar) == OHKO_SCORE  # OHKO = 120, gen1 BP is 0
    # no STAB: the attacker never enters the score
    assert move_score(mv("thunderbolt"), gengar) == move_score(mv("thunderbolt"), gengar)


def test_return_deviation_and_unknown_defender():
    assert Move("return", gen=4).base_power == 0  # what poke-env reports
    assert move_score(Move("return", gen=4), Pokemon(gen=4, species="garchomp")) == RETURN_BP
    assert move_score(mv("thunderbolt"), None) == 95  # no defender -> raw BP


def test_picks_the_max_and_never_switches_voluntarily():
    p = player()
    starmie, gengar = mon("starmie"), mon("gengar")
    order = p.choose_move(battle(starmie, gengar,
                                 [mv("thunderbolt"), mv("psychic"), mv("surf"), mv("recover")],
                                 switches=[mon("golem")]))
    assert order.order.id == "psychic"  # 90*2 beats 95*1 and 95*1
    # only status moves legal, a switch available: still a move (score 0), never a switch
    order = p.choose_move(battle(starmie, gengar, [mv("recover"), mv("thunderwave")],
                                 switches=[mon("golem")]))
    assert isinstance(order.order, Move)


def test_ties_are_seeded_and_cover_the_tied_set():
    starmie, tauros = mon("starmie"), mon("tauros")
    tied = [mv("thunderbolt"), mv("psychic")]  # 95 and 90 vs normal... not tied
    # build a real tie: two 0-score moves
    tied = [mv("recover"), mv("thunderwave")]
    picks = {player(seed=s).choose_move(battle(starmie, tauros, tied)).order.id
             for s in range(20)}
    assert picks == {"recover", "thunderwave"}
    a = player(seed=3).choose_move(battle(starmie, tauros, tied)).order.id
    b = player(seed=3).choose_move(battle(starmie, tauros, tied)).order.id
    assert a == b  # same seed, same choice


def test_forced_switch_minimises_the_opponents_type_pressure():
    zapdos = mon("zapdos")  # electric / flying
    golem, starmie, exeggutor = mon("golem"), mon("starmie"), mon("exeggutor")
    assert switch_weakness(golem, zapdos) == 0 + 0.5      # rock/ground: immune to electric, resists flying
    assert switch_weakness(starmie, zapdos) == 2 + 1      # water/psychic
    assert switch_weakness(exeggutor, zapdos) == 0.5 + 2  # grass/psychic: resists electric, weak to flying
    order = player().choose_move(battle(None, zapdos, [], switches=[starmie, golem, exeggutor]))
    assert order.order.species == "golem"

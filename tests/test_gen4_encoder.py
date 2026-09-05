"""gen-4 encoder bring-up (rl/envs/gen4): layout, tables, vocab, classes, the
exact set prior, the tracker's protocol reads, the effect block, and the
offline tape replay.

The tape gate here pins SHAPE and BOUNDS, not bytes: the gen-4 layout is
v0.1 and becomes a pre-registered artifact only when a gen-4 header freezes
it (docs/design_gen4/encoder_requirements.md §4.7). Tapes are local
collection artifacts (data/gen4_tapes/, gitignored; recorded by
scripts/gen4_smoke.py) — the replay tests skip loudly without them.
"""

import logging
from pathlib import Path

import numpy as np
import pytest
from poke_env.battle import Battle
from poke_env.battle.move import Move
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.data import GenData

from rl.envs.encoder_spec import GEN1
from rl.envs.gen4 import prior
from rl.envs.gen4.classes import (
    ABILITY_CLASS_INDEX,
    ABILITY_CLASSES,
    ITEM_CLASS_INDEX,
    ITEM_CLASSES,
    ability_type_multiplier,
)
from rl.envs.gen4.encoder import effect_block, embed_battle_gen4, move_base_power
from rl.envs.gen4.spec import GEN4, LAYOUT, OBS_DIM_GEN4, ENCODER_FINGERPRINT_GEN4
from rl.envs.gen4.tape import replay_tape
from rl.envs.gen4.tracker import BattleTracker, norm_ident
from rl.envs.gen4.vocab import VOCAB

_ROOT = Path(__file__).resolve().parents[1]
_TAPE = _ROOT / "data/gen4_tapes/t0_rnd_sh.jsonl"
_SHOWDOWN_COMMIT = "59da482eabc87245eb62313593e468e81ca537d9"


# --- (i) tables and layout ---------------------------------------------------


def test_gen4_spec_tables():
    names = [t.name for t in GEN4.types]
    assert names == sorted(names) and len(names) == 17
    assert "DARK" in names and "STEEL" in names and "FAIRY" not in names
    assert GEN4.base_stat_keys == ("hp", "atk", "def", "spa", "spd", "spe")
    assert GEN4.statuses == GEN1.statuses and GEN4.boost_keys == GEN1.boost_keys
    assert GEN4.special_move_ids == frozenset({"struggle", "recharge"})  # no gen-1 `fight`
    assert GEN4.n_actions == 10 == GEN1.n_actions
    assert GEN4.species_num_range == (1, 493) and GEN4.move_num_range == (1, 467)
    # the seam's registry is untouched: gen 4 is served by this package, not by spec_for_format
    from rl.envs.encoder_spec import spec_for_format
    with pytest.raises(NotImplementedError):
        spec_for_format("gen4randombattle")


def test_layout_v01_arithmetic():
    L = LAYOUT
    assert (L.global_dim, L.mon_dim, L.active_dim, L.move_dim, L.id_dim) == (36, 61, 31, 71, 44)
    assert L.obs_dim == OBS_DIM_GEN4 == (
        L.global_dim + 6 * L.mon_dim + L.active_dim + 4 * L.move_dim
        + 6 * (L.mon_dim + 1) + L.active_dim + 4 * L.move_dim + L.id_dim
    ) == 1448
    assert L.opp_mons_off == L.own_moves_off + 4 * L.move_dim
    assert L.ids_off + L.id_dim == L.obs_dim
    assert L.mon_speed_off + 1 == L.mon_dim
    assert L.active_extras_off + 3 == L.active_dim
    assert L.move_effect_off + L.effect_dim == L.move_dim
    assert L.priv_dim == (L.opp_mons_off - L.own_mons_off) + 22
    assert ENCODER_FINGERPRINT_GEN4["obs_dim"] == L.obs_dim and ENCODER_FINGERPRINT_GEN4["gen"] == 4


# --- (ii) vocab, classes, prior ---------------------------------------------


def test_vocab_is_the_pinned_pool():
    assert VOCAB.showdown_commit == _SHOWDOWN_COMMIT
    assert (len(VOCAB.species), len(VOCAB.moves), len(VOCAB.abilities), len(VOCAB.items)) == (300, 182, 101, 40)
    assert VOCAB.n_species == 301  # row 0 = unknown
    assert VOCAB.species_id("arceusghost") != VOCAB.species_id("arceuswater") != 0
    assert VOCAB.move_id("hiddenpowerfire") != VOCAB.move_id("hiddenpowerice") != 0
    assert VOCAB.move_id("struggle") and VOCAB.move_id("return") and VOCAB.move_id("recharge") == 0
    assert VOCAB.move_id("return102") == VOCAB.move_id("return")  # the request's happiness suffix
    assert VOCAB.move_id("hiddenpowerfire70") == 0 and VOCAB.move_id("hiddenpowerfire") != 0  # poke-env strips HP's digits itself
    assert VOCAB.item_id("unknown_item") == VOCAB.item_id("") == VOCAB.item_id(None) == 0
    assert VOCAB.item_id("Choice Band") == VOCAB.item_id("choiceband") != 0
    assert VOCAB.species_id("notaspecies") == 0
    assert VOCAB.levels["gengar"] and 67 <= min(VOCAB.levels.values()) and max(VOCAB.levels.values()) <= 100
    assert max(VOCAB.n_species, VOCAB.n_moves, VOCAB.n_abilities, VOCAB.n_items) / LAYOUT.id_scale < 4.0


def test_classes_partition_the_vocab():
    for name, index, classes, ids in (
        ("ability", ABILITY_CLASS_INDEX, ABILITY_CLASSES, VOCAB.abilities),
        ("item", ITEM_CLASS_INDEX, ITEM_CLASSES, VOCAB.items),
    ):
        assert set(index) == set(ids), name
        assert len(classes) == (12 if name == "ability" else 5)
    assert ability_type_multiplier("levitate", PokemonType.GROUND, 2.0) == 0.0
    assert ability_type_multiplier("levitate", PokemonType.FIRE, 2.0) == 2.0
    assert ability_type_multiplier("wonderguard", PokemonType.FIRE, 1.0) == 0.0
    assert ability_type_multiplier("wonderguard", PokemonType.FIRE, 2.0) == 2.0
    assert ability_type_multiplier("filter", PokemonType.FIRE, 4.0) == 3.0
    assert ability_type_multiplier(None, PokemonType.FIRE, 0.5) == 0.5


def test_prior_is_the_generators_output():
    ok, msg = prior.verify_against_vocab()
    assert ok, msg
    assert prior.stamp()["showdown_commit"] == _SHOWDOWN_COMMIT
    assert "gengar" in prior.known_species() and "notaspecies" not in prior.known_species()
    # three of four moves revealed: the fourth slot's candidates sum to one
    probs = prior.conditional_move_probs("gengar", frozenset({"focusblast", "shadowball", "sludgebomb"}))
    assert probs and abs(sum(p for _, p in probs) - 1.0) < 1e-6
    assert probs[0][1] >= probs[-1][1]  # high-probability first
    assert all(m not in {"focusblast", "shadowball", "sludgebomb"} for m, _ in probs)
    assert abs(sum(prior.ability_probs("snorlax").values()) - 1.0) < 1e-6
    assert set(prior.ability_probs("snorlax")) == {"thickfat", "immunity"}
    assert abs(sum(prior.item_probs("gengar").values()) - 1.0) < 1e-6
    # inconsistent evidence degrades to the unconditional table, never to nothing
    assert prior.conditional_move_probs("gengar", frozenset({"surf"})) == prior.conditional_move_probs("gengar", frozenset())
    assert prior.conditional_move_probs("notaspecies", frozenset()) == []


# --- (iii) the effect block and per-move overrides --------------------------


def test_effect_block_reads_gen4_move_data():
    assert move_base_power(Move("return", gen=4)) == 102.0  # poke-env says 0 (survey G7)
    assert effect_block("toxic")[5] == 1.0 and effect_block("toxic")[6] == 1.0  # TOX, certain
    assert effect_block("uturn")[33] == 1.0 and effect_block("roar")[32] == 1.0
    assert effect_block("spikes")[28] == 1.0 and effect_block("rapidspin")[39] == 1.0
    assert effect_block("protect")[38] == 1.0 and effect_block("seismictoss")[41] == 1.0
    assert effect_block("trick")[42] == 1.0 and effect_block("healbell")[43] == 1.0
    assert effect_block("explosion")[13] == 1.0
    assert effect_block("flareblitz")[11] > 0 and effect_block("flareblitz")[44] == 1.0
    assert effect_block("swordsdance")[7] == 0.5  # +2 atk / 4
    assert effect_block("thunderbolt")[2] == 1.0 and abs(effect_block("thunderbolt")[6] - 0.1) < 1e-6
    assert effect_block("rest")[9] == 1.0 and effect_block("roost")[9] == 0.5
    assert effect_block("return")[41] == 0.0  # the override makes it a plain 102-BP move
    assert not effect_block("recharge").any()  # placeholder: no gen-4 entry, stays zero
    assert effect_block("hiddenpowerfire").shape == (LAYOUT.effect_dim,)


# --- (iv) the tracker, fed poke-env's own parser -----------------------------


def _battle(role: str = "p1") -> Battle:
    logger = logging.getLogger("test_gen4")
    logger.addHandler(logging.NullHandler())
    b = Battle("battle-gen4randombattle-1", "me", logger, gen=4)
    b.parse_message(["", "player", "p1", "me" if role == "p1" else "them", "", ""])
    b.parse_message(["", "player", "p2", "them" if role == "p1" else "me", "", ""])
    b.parse_message(["", "switch", "p1a: Rotom", "Rotom-Heat, L82", "100/100"])
    b.parse_message(["", "switch", "p2a: Tyranitar", "Tyranitar, L78", "100/100"])
    return b


def test_norm_ident():
    assert norm_ident("p1a: Gengar") == "p1: Gengar" == norm_ident("p1: Gengar")
    assert norm_ident("p2b: Mr. Mime") == "p2: Mr. Mime"


def test_tracker_counts_sleep_attempts_where_pokeenv_counts_lines():
    """The Sleep Talk sequence recorded live (data/gen4_tapes/t0, battle 2):
    one `cant` per sleeping attempt, two `|move|` lines on a Sleep Talk turn.
    poke-env bumps on the `cant` AND on both move lines (survey G3); the
    tracker counts attempts, which is what the sim's counter does
    (showdown/data/mods/gen4/conditions.ts:41-47)."""
    b = _battle()
    tr = BattleTracker()
    mon = b.get_pokemon("p1a: Rotom")
    for sm in (
        ["", "move", "p1a: Rotom", "Rest", "p1a: Rotom"],
        ["", "-status", "p1a: Rotom", "slp", "[from] move: Rest"],
        ["", "turn", "3"],
        ["", "cant", "p1a: Rotom", "slp"],
        ["", "move", "p1a: Rotom", "Sleep Talk", "p1a: Rotom"],
        ["", "move", "p1a: Rotom", "Thunderbolt", "p2a: Tyranitar", "[from] move: Sleep Talk"],
        ["", "turn", "4"],
        ["", "cant", "p1a: Rotom", "slp"],
        ["", "turn", "5"],
    ):
        b.parse_message(sm)
    tr.update(b)
    assert mon.status == Status.SLP
    assert mon.status_counter == 4          # poke-env: cant + 2 move lines + cant
    assert tr.sleep_attempts["p1: Rotom"] == 2  # the sim: two attempts lost
    assert tr.first_move_since_switch["p1: Rotom"] == "rest"   # Choice lock target
    assert tr.last_move["p1: Rotom"] == "thunderbolt"          # the called move
    b.parse_message(["", "-curestatus", "p1a: Rotom", "slp", "[msg]"])
    tr.update(b)
    assert "p1: Rotom" not in tr.sleep_attempts
    # a switch does NOT reset the gen-4 sleep clock
    b.parse_message(["", "-status", "p1a: Rotom", "slp"])
    b.parse_message(["", "cant", "p1a: Rotom", "slp"])
    b.parse_message(["", "switch", "p1a: Rotom", "Rotom-Heat, L82", "100/100 slp"])
    tr.update(b)
    assert tr.sleep_attempts["p1: Rotom"] == 1


def test_tracker_weather_items_encore_substitute():
    b = _battle()
    tr = BattleTracker()
    for sm in (
        ["", "turn", "1"],
        ["", "-weather", "Sandstorm", "[from] ability: Sand Stream", "[of] p2a: Tyranitar"],
        ["", "-weather", "Sandstorm", "[upkeep]"],
        ["", "turn", "2"],
        ["", "-weather", "Sandstorm", "[upkeep]"],
        ["", "turn", "3"],
        ["", "move", "p1a: Rotom", "Thunderbolt", "p2a: Tyranitar"],
        ["", "-enditem", "p2a: Tyranitar", "Sitrus Berry", "[eat]"],
        ["", "-start", "p1a: Rotom", "Encore"],
        ["", "-start", "p2a: Tyranitar", "Substitute"],
        ["", "-activate", "p2a: Tyranitar", "Substitute", "[damage]"],
        ["", "-activate", "p1a: Rotom", "ability: Forewarn", "Stone Edge", "[of] p2a: Tyranitar"],
        ["", "-start", "p1a: Rotom", "ability: Flash Fire"],
    ):
        b.parse_message(sm)
    tr.update(b)
    assert tr.weather == "Sandstorm" and tr.weather_indefinite and tr.weather_start == 1
    assert tr.weather_elapsed(3) == 2
    assert tr.original_item["p2: Tyranitar"] == "sitrusberry" and "p2: Tyranitar" in tr.consumed
    assert tr.encored_move["p1: Rotom"] == "thunderbolt"
    assert tr.sub_hits["p2: Tyranitar"] == 1
    assert tr.revealed_ability["p1: Rotom"] == "forewarn"
    assert "p1: Rotom" in tr.flash_fire
    assert tr.choice_locked("p1: Rotom", "choicescarf") and not tr.choice_locked("p2: Tyranitar", "choicescarf")
    for sm in (
        ["", "-weather", "RainDance"],
        ["", "-end", "p2a: Tyranitar", "Substitute"],
        ["", "switch", "p1a: Rotom", "Rotom-Heat, L82", "100/100"],
        ["", "-weather", "none"],
    ):
        b.parse_message(sm)
    tr.update(b)
    assert tr.weather is None and not tr.weather_indefinite
    assert "p2: Tyranitar" not in tr.sub_hits and "p1: Rotom" not in tr.flash_fire
    assert "p1: Rotom" not in tr.encored_move and not tr.choice_locked("p1: Rotom", "choicescarf")


def test_embed_on_a_hand_built_battle():
    b = _battle()
    b.parse_message(["", "turn", "1"])
    b.parse_message(["", "-weather", "Sandstorm", "[from] ability: Sand Stream", "[of] p2a: Tyranitar"])
    tr = BattleTracker()
    vec = embed_battle_gen4(b, GenData.from_gen(4).type_chart, tr)
    L = LAYOUT
    assert vec.shape == (L.obs_dim,) and vec.dtype == np.float32
    assert not np.isnan(vec).any() and vec.min() >= -1.0 and vec.max() <= 4.0
    assert vec[L.weather_off + L.weather_index[__import__("poke_env.battle.weather", fromlist=["Weather"]).Weather.SANDSTORM]] == 1.0
    assert vec[L.weather_off + 4 + 1] == 1.0  # indefinite
    # opponent Tyranitar: revealed flag, Sand Stream is its only dex ability -> known, weather_setter class
    base = L.opp_mons_off
    assert vec[base] == 1.0
    assert vec[base + 1 + L.mon_ability_state_off] == 1.0
    assert vec[base + 1 + L.mon_ability_classes_off + ABILITY_CLASS_INDEX["sandstream"]] == 1.0
    assert vec[base + 1 + L.mon_item_state_off] == 1.0  # item unknown
    assert vec[base + 1 + L.mon_item_classes_off: base + 1 + L.mon_item_classes_off + 5].sum() > 0.99  # prior over items
    # ids: own species row, opponent species row, opponent ability known
    assert vec[L.ids_off] == VOCAB.species_id("rotomheat") / L.id_scale
    assert vec[L.ids_off + 6] == VOCAB.species_id("tyranitar") / L.id_scale
    assert vec[L.ids_off + 38] == VOCAB.ability_id("sandstream") / L.id_scale


# --- (v) the offline tape replay ----------------------------------------------


@pytest.mark.skipif(not _TAPE.exists(), reason="local gen-4 tape absent (scripts/gen4_smoke.py records it)")
def test_tape_replay_shape_and_bounds():
    tc = GenData.from_gen(4).type_chart
    trackers = {}
    seen = {"n": 0}

    def on_decision(battle, request, seat):
        tr = trackers.setdefault((seat, battle.battle_tag), BattleTracker())
        vec = embed_battle_gen4(battle, tc, tr)
        assert vec.shape == (OBS_DIM_GEN4,) and vec.dtype == np.float32
        assert not np.isnan(vec).any()
        assert vec.min() >= -1.0 and vec.max() <= 4.0, (vec.min(), vec.max())
        seen["n"] += 1

    r = replay_tape(_TAPE, on_decision)
    assert r["poisoned"] == 0 and not r["errors"], r
    assert r["decisions"] == seen["n"] > 200

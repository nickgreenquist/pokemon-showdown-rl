"""Gate B-0, Python half (docs/PKMN_ENGINE_RUST_PLAN.md §9).

The engine simulates with its OWN species/move tables; poke-env supplies the
tables the OBSERVATION is built from (plan §7.4). The whole encoder rests on the
two being the same game, and specifically on the encoder's ids being the engine's
enum values by construction -- so that is VERIFIED here, never assumed.

No server, no poke-env client: everything below is static data.

Skips cleanly if the extension is not installed, so this file is safe to collect
from a tree that has not built it.
"""

from __future__ import annotations

import json
import pathlib

import pytest

pkmn_gen1 = pytest.importorskip(
    "pkmn_gen1", reason="build it with: pip install --no-build-isolation -e engine/pkmn_gen1"
)

from poke_env import to_id_str  # noqa: E402
from poke_env.battle.move import Move  # noqa: E402
from poke_env.data import GenData  # noqa: E402

ENGINE_PIN = "9b88fd6c5467f703c38951d5b2e8a660314d410b"
VENDOR = pathlib.Path(__file__).resolve().parents[1] / "engine/pkmn_gen1/vendor/pkmn-engine"

# The engine's Type enum is cartridge order; the encoder's one-hot is
# alphabetical (rl/envs/showdown.py). The permutation is asserted, not assumed.
CARTRIDGE_TYPES = [
    "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost",
    "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon",
]


@pytest.fixture(scope="module")
def engine_data():
    path = VENDOR / "src/data/data.json"
    if not path.exists():
        pytest.skip("vendored engine missing: git submodule update --init")
    return json.loads(path.read_text())[0]


@pytest.fixture(scope="module")
def gen1():
    return GenData.from_gen(1)


def test_verify_reports_the_pinned_artifact():
    info = pkmn_gen1.verify()
    assert info["engine_sha"] == ENGINE_PIN
    assert info["engine_sha"] == info["engine_sha_pinned"]
    assert info["zig"] == "0.16.0"
    assert info["battle_size"] == 384 == pkmn_gen1.BATTLE_SIZE
    assert info["max_choices"] == 9
    assert info["options"] == {
        "showdown": True,
        "log": False,
        "chance": False,
        "calc": False,
    }


def test_engine_type_order_is_the_cartridge_order(engine_data):
    assert engine_data["types"] == CARTRIDGE_TYPES
    assert len(set(CARTRIDGE_TYPES)) == 15


def test_species_enum_is_the_national_dex_number(engine_data, gen1):
    """The encoder's `_species_id` is the dex num; the engine's Species enum is
    1..151 in dex order. Identity, or every species feature is silently wrong."""
    species = list(engine_data["species"])
    assert len(species) == 151
    for i, name in enumerate(species, start=1):
        key = to_id_str(name)
        entry = gen1.pokedex.get(key)
        assert entry is not None, f"poke-env gen 1 dex has no {name!r} (key {key!r})"
        assert entry["num"] == i, f"{name}: engine enum {i} != poke-env num {entry['num']}"


def test_move_enum_is_the_gen1_move_number(engine_data, gen1):
    moves = list(engine_data["moves"])
    assert len(moves) == 165
    assert moves[0] == "Pound" and moves[-1] == "Struggle"
    for i, name in enumerate(moves, start=1):
        key = to_id_str(name)
        entry = gen1.moves.get(key)
        assert entry is not None, f"poke-env gen 1 movedex has no {name!r} (key {key!r})"
        assert entry["num"] == i, f"{name}: engine enum {i} != poke-env num {entry['num']}"


def test_base_stats_and_types_agree(engine_data, gen1):
    """The engine simulates with data.json; the observation is built from
    poke-env. If they disagree the agent sees a different game than it plays."""
    for name, spec in engine_data["species"].items():
        key = to_id_str(name)
        entry = gen1.pokedex[key]
        bs = entry["baseStats"]
        assert (spec["stats"]["hp"], spec["stats"]["atk"], spec["stats"]["def"],
                spec["stats"]["spe"]) == (bs["hp"], bs["atk"], bs["def"], bs["spe"]), name
        # Gen 1 has one Special stat; PS stores it as spa == spd.
        assert bs["spa"] == bs["spd"] == spec["stats"]["spc"], name
        assert spec["types"] == entry["types"], name
        for t in spec["types"]:
            assert t in CARTRIDGE_TYPES, f"{name}: unknown type {t}"


def test_max_pp_table_agrees(engine_data):
    """PS `calculatePP` with 3 PP Ups is pp*8/5 capped at 61; the engine's helper
    is min(pp/5*8, 61) in integer arithmetic. Assert they agree for all 165."""
    for name, base_pp in engine_data["moves"].items():
        key = to_id_str(name)
        engine_max = min(base_pp // 5 * 8, 61)
        assert Move(key, gen=1).max_pp == engine_max, f"{name}: base pp {base_pp}"


def test_base_pp_table_agrees(engine_data, gen1):
    for name, base_pp in engine_data["moves"].items():
        key = to_id_str(name)
        assert gen1.moves[key]["pp"] == base_pp, name

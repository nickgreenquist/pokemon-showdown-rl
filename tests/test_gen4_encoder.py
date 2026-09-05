"""gen-4 encoder bring-up (rl/envs/gen4): layout, tables, vocab, classes, the
exact set prior, the tracker's protocol reads, the effect block, and the
offline tape replay.

The tape gate here pins SHAPE and BOUNDS, not bytes: the gen-4 layout is
v0.1 and becomes a pre-registered artifact only when a gen-4 header freezes
it (docs/design_gen4/encoder_requirements.md §4.7). Tapes are local
collection artifacts (data/gen4_tapes/, gitignored; recorded by
scripts/gen4_smoke.py); the first two battles of t0 are committed gzipped
under tests/fixtures/ so the replay gate runs on every clone, and the full
local tape is checked too when present.
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
_FIXTURE = _ROOT / "tests/fixtures/gen4_tape_t0_2battles.jsonl.gz"  # t0's first two rooms, 4 seat-battles
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
    assert VOCAB.move_id("return102") == VOCAB.move_id("return")  # the RAW request id; poke-env's Move.id is already `return`
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


def test_prior_resolves_an_untyped_hidden_power():
    """Showdown never names the type of an opponent's Hidden Power; poke-env
    stores the untyped `hiddenpower`, which matches no set row, so every prior
    read for such a mon fell back to the unconditional table (5.6 % of
    opponent-mon observations on t1+t2, 2026-09-05 review). The resolver picks
    the typed variant the realised sets favour and the encoder conditions on
    it; a species with no Hidden Power set keeps the stand-in and encodes NO
    type (poke-env's Normal is never the truth)."""
    from poke_env.battle.pokemon import Pokemon
    from rl.envs.gen4.encoder import _fill_move, _revealed, opponent_move_slots

    variants = {
        sp: sorted({m for r in rows for m in r[0] if m.startswith("hiddenpower")})
        for sp, rows in prior._sets().items()
    }
    single = sorted(sp for sp, v in variants.items() if len(v) == 1)[0]
    assert prior.hidden_power_variant(single) == variants[single][0]
    assert len(variants["magnezone"]) == 3 and prior.hidden_power_variant("magnezone") in variants["magnezone"]
    assert not variants.get("tyranitar") and prior.hidden_power_variant("tyranitar") is None

    mon = Pokemon(gen=4, species=single)
    mon._add_move("hiddenpower")
    assert mon.moves["hiddenpower"].id == "hiddenpower"  # poke-env's untyped stand-in
    seen = _revealed(mon)
    assert prior.HIDDEN_POWER not in seen and variants[single][0] in seen
    (move, p), *rest = opponent_move_slots(mon)
    assert move.id == variants[single][0] and p == 1.0 and move.base_power == 70
    assert all(not m.id.startswith("hiddenpower") for m, _ in rest)  # conditioned, not fallen back

    tc = GenData.from_gen(4).type_chart
    tyr = Pokemon(gen=4, species="tyranitar")
    tyr._add_move("hiddenpower")
    assert _revealed(tyr) == frozenset()  # dropped from the conditioning set, not a fallback trigger
    (move, _), *_ = opponent_move_slots(tyr)
    assert move.id == "hiddenpower"  # the slot keeps the untyped stand-in
    vec = np.zeros(LAYOUT.move_dim, dtype=np.float32)
    _fill_move(vec, 0, move, mon, {}, tc, LAYOUT)
    assert vec[LAYOUT.move_type_off:LAYOUT.move_type_off + 17].sum() == 0.0 and vec[4] == 0.0
    assert vec[1] == pytest.approx(move_base_power(move) / 100.0)


def test_effect_block_self_boosts_use_showdowns_self_key():
    """User stat drops live under `self: {boosts}` in Showdown's move data
    (not `selfBoost`); slot 7 is the chance-weighted self-boost sum / 4."""
    assert effect_block("overheat")[7] == pytest.approx(-0.5)
    assert effect_block("dracometeor")[7] == pytest.approx(-0.5)
    assert effect_block("closecombat")[7] == pytest.approx(-0.5)
    assert effect_block("superpower")[7] == pytest.approx(-0.5)
    assert effect_block("swordsdance")[7] == pytest.approx(0.5)
    assert effect_block("metalclaw")[7] == pytest.approx(0.1 / 4.0)  # 10 % +1 Atk


def test_tracker_rampage_lock():
    """Outrage locks for 2-3 turns; Showdown announces neither start nor end
    and poke-env strips `[from]lockedmove`, so the tracker derives it."""
    from poke_env.battle.effect import Effect

    b = _battle()
    tr = BattleTracker()
    for sm in (
        ["", "turn", "1"],
        ["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom"],
        ["", "turn", "2"],
    ):
        b.parse_message(sm)
    tr.update(b)
    assert tr.is_locked("p2: Tyranitar") and tr.lock_elapsed("p2: Tyranitar") == 1
    vec = embed_battle_gen4(b, GenData.from_gen(4).type_chart, tr)
    slot = LAYOUT.opp_active_off + LAYOUT.active_volatiles_off + GEN4.volatiles.index(Effect.LOCKED_MOVE)
    assert vec[slot] == 1.0
    assert vec[LAYOUT.opp_active_off + LAYOUT.active_counters_off + 3] == pytest.approx(1 / 8)
    for sm in (
        ["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom", "[from]lockedmove"],
        ["", "-start", "p2a: Tyranitar", "confusion", "[fatigue]"],
        ["", "turn", "3"],
    ):
        b.parse_message(sm)
    tr.update(b)
    assert not tr.is_locked("p2: Tyranitar") and tr.lock_elapsed("p2: Tyranitar") == 0
    # a miss ends it
    b.parse_message(["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom"])
    b.parse_message(["", "-miss", "p2a: Tyranitar", "p1a: Rotom"])
    tr.update(b)
    assert not tr.is_locked("p2: Tyranitar")
    # a Sleep Talk-called rampage never locks (the gen-4 mod drops a sleeper's lock)
    b.parse_message(["", "move", "p2a: Tyranitar", "Sleep Talk", "p2a: Tyranitar"])
    b.parse_message(["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom", "[from] move: Sleep Talk"])
    tr.update(b)
    assert not tr.is_locked("p2: Tyranitar")
    # three turns is the cap even when every end message is missed
    b.parse_message(["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom"])
    tr.update(b)
    assert tr.is_locked("p2: Tyranitar")
    for t in ("4", "5"):
        b.parse_message(["", "turn", t])
    tr.update(b)
    assert tr.is_locked("p2: Tyranitar") and tr.lock_elapsed("p2: Tyranitar") == 2
    b.parse_message(["", "turn", "6"])
    tr.update(b)
    assert not tr.is_locked("p2: Tyranitar")
    # a switch clears it
    b.parse_message(["", "move", "p2a: Tyranitar", "Outrage", "p1a: Rotom"])
    b.parse_message(["", "switch", "p2a: Tyranitar", "Tyranitar, L74", "100/100"])
    tr.update(b)
    assert not tr.is_locked("p2: Tyranitar")


def test_gen4_pool_player_trackers_are_bounded():
    """A tracker per battle TAG, popped exactly when PoolPlayer pops the
    `_by_tag` entry: at report_outcome (sync training path) and at the
    finished sweep (listening / async paths)."""
    from types import SimpleNamespace

    from rl.envs.gen4.env import Gen4PoolPlayer

    class _Pool:
        reports: list = []

        def freeze(self):
            pass

        def select(self, rng):
            return "m"

        def member_id(self, m):
            return 0

        def report(self, m, outcome):
            self.reports.append(outcome)

    player = Gen4PoolPlayer(_Pool(), battle_format="gen4randombattle", start_listening=False)
    player._by_tag["battle-a"] = (SimpleNamespace(finished=False), "m", 0)
    player._trackers["battle-a"] = BattleTracker()
    player.report_outcome(1)  # the sync caller names no battle
    assert not player._by_tag and not player._trackers and _Pool.reports == [1]
    player._by_tag["battle-b"] = (SimpleNamespace(finished=True), "m", 0)
    player._trackers["battle-b"] = BattleTracker()
    player._by_tag["battle-c"] = (SimpleNamespace(finished=False), "m", 0)
    player._trackers["battle-c"] = BattleTracker()
    player._sweep_finished()
    assert set(player._by_tag) == {"battle-c"} == set(player._trackers)


def test_most_damage_typed_at_gen4_and_reseeding():
    """main's rl/envs/most_damage_typed.py (the branch converged on it) at
    gen 4: base power x chart, STATUS 0, OHKO 120, Return 102; forced switch =
    least summed type weakness; the private tie-break stream ShowdownEnv.reset
    reseeds per sub-env reproduces under the same seed and moves under another."""
    from types import SimpleNamespace

    from poke_env.battle.pokemon import Pokemon

    from rl.envs.most_damage_typed import MostDamageTypedPlayer, move_score, switch_weakness

    magnezone = Pokemon(gen=4, species="magnezone")  # Electric / Steel
    gyarados = Pokemon(gen=4, species="gyarados")    # Water / Flying
    assert move_score(Move("earthquake", gen=4), magnezone) == 100 * 4
    assert move_score(Move("toxic", gen=4), magnezone) == 0.0
    assert move_score(Move("fissure", gen=4), magnezone) == 120.0
    assert move_score(Move("return", gen=4), magnezone) == 102 * 0.5
    assert switch_weakness(gyarados, magnezone) == 4.0 + 0.5  # Electric 2x2, Steel 0.5x1
    # ties: Thunderbolt and Flamethrower are both 95 BP neutral into a Normal type
    foe = Pokemon(gen=4, species="snorlax")
    moves = [Move("thunderbolt", gen=4), Move("flamethrower", gen=4)]
    battle = SimpleNamespace(opponent_active_pokemon=foe, available_moves=moves, available_switches=[])
    p = MostDamageTypedPlayer(battle_format="gen4randombattle", start_listening=False, seed=0)
    picks = [p.choose_move(battle).order.id for _ in range(16)]
    assert set(picks) == {"thunderbolt", "flamethrower"}
    q = MostDamageTypedPlayer(battle_format="gen4randombattle", start_listening=False, seed=0)
    assert [q.choose_move(battle).order.id for _ in range(16)] == picks
    q._rng.seed(1)  # what ShowdownEnv.reset does per sub-env
    assert [q.choose_move(battle).order.id for _ in range(16)] != picks


# --- (v) the offline tape replay ----------------------------------------------


@pytest.mark.parametrize(
    "tape, min_decisions",
    [
        pytest.param(_FIXTURE, 60, id="fixture"),
        pytest.param(
            _TAPE, 200, id="local-t0",
            marks=pytest.mark.skipif(not _TAPE.exists(), reason="local gen-4 tape absent (scripts/gen4_smoke.py records it)"),
        ),
    ],
)
def test_tape_replay_shape_and_bounds(tape, min_decisions):
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

    r = replay_tape(tape, on_decision)
    assert r["poisoned"] == 0 and not r["errors"], r
    assert r["decisions"] == seen["n"] > min_decisions


# ---- 2026-09-05 review fixes: pinned as tests so the hash gate freezes the fixes ----

def test_reveal_from_cause_files_the_ability_on_its_holder():
    from rl.envs.gen4.tracker import BattleTracker
    t = BattleTracker.__new__(BattleTracker)
    t.revealed_ability = {}
    # Water Absorb heals the TARGET; `[of]` is the attacker
    t._reveal_from_cause(["", "-heal", "p1a: Vaporeon", "100/100", "[from] ability: Water Absorb", "[of] p2a: Kingdra"])
    assert t.revealed_ability == {"p1: Vaporeon": "waterabsorb"}
    # Rough Skin damages the ATTACKER; `[of]` is the holder
    t._reveal_from_cause(["", "-damage", "p2a: Kingdra", "88/100", "[from] ability: Rough Skin", "[of] p1a: Garchomp"])
    assert t.revealed_ability["p1: Garchomp"] == "roughskin"
    assert "p2: Kingdra" not in t.revealed_ability or t.revealed_ability["p2: Kingdra"] != "roughskin"
    # Trace: the subject holds Trace, the `[of]` mon holds the traced ability
    t._reveal_from_cause(["", "-ability", "p1a: Gardevoir", "Thick Fat", "[from] ability: Trace", "[of] p2a: Snorlax"])
    assert t.revealed_ability["p1: Gardevoir"] == "trace"
    assert t.revealed_ability["p2: Snorlax"] == "thickfat"
    # no `[of]`: the subject
    t._reveal_from_cause(["", "-immune", "p2a: Bronzong", "[from] ability: Levitate"])
    assert t.revealed_ability["p2: Bronzong"] == "levitate"
    # weather names the setter through `[of]`
    t._reveal_from_cause(["", "-weather", "Sandstorm", "[from] ability: Sand Stream", "[of] p2a: Tyranitar"])
    assert t.revealed_ability["p2: Tyranitar"] == "sandstream"


def test_fail_on_the_target_keeps_the_rampage_lock():
    from rl.envs.gen4.tracker import BattleTracker
    t = BattleTracker.__new__(BattleTracker)
    t.revealed_ability = {}
    t.locked_move = {"p2: Salamence": ("outrage", 3)}
    t._apply(["", "-fail", "p2a: Salamence", "par"])  # Thunder Wave into a paralysed mon: TARGET named
    assert t.is_locked("p2: Salamence")
    t._apply(["", "-fail", "p2a: Salamence"])  # the user's own move failed
    assert not t.is_locked("p2: Salamence")


def test_effect_block_curse_wish_and_multihit_corrections():
    from rl.envs.gen4.encoder import effect_block
    curse = effect_block("curse")
    assert curse[7] == 0.25 and curse[16:] .sum() == 0.0  # stat Curse, no Ghost residual
    assert effect_block("wish")[9] == 0.5
    hw = effect_block("healingwish")
    assert hw[9] == 0.0 and hw[13] == 1.0
    assert abs(effect_block("rockblast")[12] - 1.0) < 1e-9  # (3.0 - 1) / 2


def test_hidden_power_slot_carries_the_variant_probability():
    from rl.envs.gen4 import prior
    probs = prior.hidden_power_variant_probs("bellossom")
    assert set(probs) and abs(sum(probs.values()) - 1.0) < 1e-9
    if len(probs) > 1:
        assert max(probs.values()) < 0.999  # a coin flip is not a certainty
    v = prior.hidden_power_variant("bellossom")
    assert v in probs


def test_battle_only_formes_share_the_base_species_prior():
    from rl.envs.gen4 import prior
    assert "castformsunny" in prior.known_species()
    assert prior.ability_probs("castformsunny") == prior.ability_probs("castform") != {}
    assert prior.conditional_move_probs("cherrimsunshine", frozenset()) == prior.conditional_move_probs("cherrim", frozenset())
    assert prior.species_level("castformrainy") == prior.species_level("castform")


def test_set_prior_data_is_pinned_to_the_vendored_sim():
    """The exact set prior's sets file must be the vendored checkout's, byte for
    byte, and the vocab's stamp must agree (2026-09-05 review: nothing gated it)."""
    import hashlib, json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ours = root / "rl/envs/gen4/data/gen4_randbats_sets.json"
    vocab = json.loads((root / "rl/envs/gen4/data/gen4_vocab.json").read_text())
    sha = hashlib.sha256(ours.read_bytes()).hexdigest()
    assert sha == vocab["sets_sha256"]
    vendored = root / "showdown/data/random-battles/gen4/sets.json"
    if vendored.exists():
        assert hashlib.sha256(vendored.read_bytes()).hexdigest() == sha

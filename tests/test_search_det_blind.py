"""det_blind — the information-boundary-preserving leaf encoding.

Two load-bearing contracts, plus the plumbing around them.

1. **OFF IS BYTE-IDENTICAL.** `leaf_encoding=None` (the default) must be the
   pre-2026-09-10 search path, bit for bit. The pin is a GOLDEN DIGEST over
   `solve_decision`'s full output — action + every stat, `search/ev_matrix`
   included — under a fixed linear critic, so ANY change to ANY leaf's
   encoding moves it. The digests below were computed on a clean worktree at
   the commit BEFORE the det_blind edit (2026-09-10), at all three live
   encoder fingerprints, and the post-edit code reproduces all six.

2. **ON, THE ROOT IS THE LIVE OBS.** With det_blind on, a determinized ROOT
   (no instruction applied) must encode to the harvested LIVE observation
   exactly, outside a short list of DECLARED non-parity families that
   det_blind does not claim to fix. That is the whole point: S1 measured the
   as-is root encoding shifting the critic by +0.0497 mean / 0.1254 sd
   against a 0.0277 median decision margin, and the shift is the encoder
   showing the critic opponent material the live game never revealed.
   `test_as_is_root_fails_the_same_parity_check` is the control — the same
   assertion on the as-is encoding, which must FAIL.

Declared non-parity families, MEASURED on 1600 root encodings (4 D26 lanes x
100 decisions x 4 determinizations, 2026-09-10). det_blind cuts the total
from 35.93 dims/root to 0.945, and 47.5% of roots become bit-identical:

  opp_hp_grain     0.5575/root, max |d| 0.0023 — the engine carries exact HP,
                   battle1 only the server's /100 public fraction.
  transform_ditto  32/1600 roots, ALL of them with a Ditto in play — a
                   transformed Ditto's copied base stats reach battle1 but
                   ShadowBattle reads the static dex, so base stats, types,
                   both matchup dims, the speed edge and the move matchups
                   move with them.
  preparing        8/1600 roots — the engine models FLY/DIG as volatiles we
                   do not map back.
  root_trapped     FG-6: 0.0002/root. Not seen in this sample; declared
                   because ShadowBattle hard-codes `trapped=False`.
  sleep_rest       FG-6: 0.0001/root. Not seen in this sample; declared
                   because the engine splits sleep/Rest and poke-env
                   conflates them.

Offline: no server, no checkpoints (the critic is a pinned projection).
"""

import hashlib
import json
import pickle
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from poke_env.battle.move import Move as PEMove
from poke_env.battle.pokemon_type import PokemonType
from poke_env.data import GenData

from rl.envs.encoder_spec import GEN1
from rl.envs.showdown import (
    ACTIVE_DIM,
    ENCODER_FINGERPRINT,
    GLOBAL_DIM,
    ID_DIM,
    MON_DIM,
    MOVE_DIM,
    OBS_DIM,
    _opponent_move_slots,
    embed_battle,
)
from rl.search.agent import LEAF_ENCODINGS, SearchAgent
from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.matrix import DOSES, N_L6, decision_rng, solve_decision
from rl.search.shadow_battle import (
    PublicView,
    _cached_move,
    _MoveView,
    public_view,
    shadow_battle,
)
from tests.test_ch3_bridge import _mon as _bridge_mon

_TYPE_CHART = GenData.from_format("gen1randombattle").type_chart
HARVEST = Path("results/ch3_r1")
_needs_harvest = pytest.mark.skipif(
    not (HARVEST / "harvest_s62.pkl").exists(),
    reason="the R1 public harvest (results/ch3_r1/harvest_*.pkl) is gitignored",
)
# The harvest's `row["obs"]` is a D26 artifact: 828-d, encoder v2 + ids. Any
# test that compares an encoding AGAINST it needs this process to be encoding
# at the same width.
HARVEST_OBS_DIM = 828
_needs_d26_encoder = pytest.mark.skipif(
    OBS_DIM != HARVEST_OBS_DIM,
    reason=(
        f"the harvested live obs is {HARVEST_OBS_DIM}-d; this process encodes "
        f"{OBS_DIM}-d (set POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1)"
    ),
)


# --------------------------------------------------------------------------
# contract 1: the golden
# --------------------------------------------------------------------------

# (encoder, ids) -> (synthetic digest, harvest digest). Computed at
# 899fdd9^{tree} in a detached worktree, i.e. BEFORE the det_blind edit.
GOLDEN = {
    ("v1", False): (
        "69425e96ac2bf8bfed0951452a8ad2165e0f75416363d6e93248f9ad3b8bd4f8",
        "b46da5a4bcdd67dbe402fe598df74c1b9ee00cd3032d1221c7794db57d0dce59",
    ),
    ("v2", False): (
        "3f256e37a3b573a3ce397bee56bd9fdb56fe44eb333c8634ffd04855d4237a05",
        "0bf455e5271811d201c99e7a09c9b7c17c311e33012169aa86acc68e8512bc47",
    ),
    ("v2", True): (
        "892407da14fb52e122f80dcfa1ef006ff085a2502dbc3be9cbd17de17e103746",
        "f2b85990a1e0126fdde5e59ce7572fc25d2a8d52dc3b56fc9e016736d7ba425d",
    ),
}
_FINGERPRINT = (ENCODER_FINGERPRINT["encoder"], ENCODER_FINGERPRINT["ids"])


def _fixed_critic(batch: np.ndarray) -> np.ndarray:
    """Deterministic, torch-free, and sensitive to EVERY obs dim: a pinned
    projection squashed into (-1, 1). A leaf-encoding change of any kind
    moves `search/ev_matrix`, hence the digest."""
    w = np.cos(np.arange(OBS_DIM, dtype=np.float64) * 0.7331 + 0.11)
    return np.tanh(np.asarray(batch, dtype=np.float64) @ w / 32.0)


def _round(o, nd=10):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v, nd) for v in o]
    return o


def _digest(records) -> str:
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _solve(battle, mask, seed, bi, si, dose="M", **kw):
    rng = decision_rng(seed, bi, int(battle.turn), si)
    prior = np.asarray(mask, dtype=np.float64)
    action, stats = solve_decision(
        battle, np.asarray(mask), np.full(N_L6, 1.0 / N_L6), prior / prior.sum(),
        DOSES[dose], rng, _fixed_critic, _TYPE_CHART, **kw
    )
    stats.pop("bridge/unmapped_effects", None)
    return {"action": int(action), "stats": _round(stats)}


def _syn_mon(species, moves, level=68, hp_frac=1.0, types=(PokemonType.NORMAL,)):
    m = _bridge_mon(species, moves, level=level, hp_frac=hp_frac)
    m.types = list(types)
    m.type_1 = types[0]
    m.type_2 = types[1] if len(types) > 1 else None
    m.moves = {mid: PEMove(mid, gen=1) for mid in moves}
    return m


def synthetic_battle():
    """Two mons a side, one opponent mon REVEALED with two of its four moves
    seen — the smallest fixture that exercises every det_blind branch:
    hidden bench, a partially-revealed moveset, and a legal switch."""
    ours = _syn_mon("tauros", ["bodyslam", "blizzard", "earthquake", "hyperbeam"])
    bench = _syn_mon(
        "alakazam", ["psychic", "recover", "thunderwave", "seismictoss"],
        types=(PokemonType.PSYCHIC,),
    )
    theirs = _syn_mon("chansey", ["softboiled"], level=76)
    seen = _syn_mon(
        "zapdos", ["thunderbolt", "drillpeck"], hp_frac=0.6,
        types=(PokemonType.ELECTRIC, PokemonType.FLYING),
    )
    return SimpleNamespace(
        active_pokemon=ours, opponent_active_pokemon=theirs,
        team={"p1: Tauros": ours, "p1: Alakazam": bench},
        opponent_team={"p2: Chansey": theirs, "p2: Zapdos": seen},
        turn=5, force_switch=False, trapped=False,
        available_moves=list(ours.moves.values()),
    )


def _synthetic_mask():
    mask = np.zeros(10, dtype=bool)
    mask[[1, 6, 7, 8, 9]] = True  # switch to the bench + all four moves
    return mask


def _harvest_decisions(lane, n):
    """A fixed `np.linspace` stride over the lane's non-aliased public rows —
    the same sample scripts/ch3_r1_spike.py and the S1/S2 screens take."""
    from rl.search.harvest import rehydrate_battle

    with open(HARVEST / f"harvest_{lane}.pkl", "rb") as f:
        battles = pickle.load(f)
    pool = [(bi, si) for bi, b in enumerate(battles)
            for si, row in enumerate(b["rows"]) if not row["aliased"]]
    for k in np.linspace(0, len(pool) - 1, num=n, dtype=int):
        bi, si = pool[int(k)]
        row = battles[bi]["rows"][si]
        yield bi, si, row, rehydrate_battle(row["battle"])


@pytest.mark.skipif(
    _FINGERPRINT not in GOLDEN,
    reason=f"no pre-change golden pinned for encoder {_FINGERPRINT}",
)
def test_det_blind_off_is_byte_identical_synthetic():
    b = synthetic_battle()
    got = _digest([_solve(b, _synthetic_mask(), 4242, 0, 0, dose="S")])
    assert got == GOLDEN[_FINGERPRINT][0], (
        "the default (as-is) leaf encoding changed: solve_decision's output "
        f"digest is {got}, the pre-det_blind golden is {GOLDEN[_FINGERPRINT][0]}"
    )


@_needs_harvest
@pytest.mark.skipif(
    _FINGERPRINT not in GOLDEN,
    reason=f"no pre-change golden pinned for encoder {_FINGERPRINT}",
)
def test_det_blind_off_is_byte_identical_on_harvested_decisions():
    """10 real decisions at Dose M — 3,707 leaves, each one encoded through
    the production path."""
    records = [
        _solve(battle, row["mask"], 62, bi, si)
        for bi, si, row, battle in _harvest_decisions("s62", 10)
    ]
    assert sum(r["stats"]["search/leaves"] for r in records) == 3707
    assert _digest(records) == GOLDEN[_FINGERPRINT][1]


def test_explicit_none_is_the_default_path():
    b, mask = synthetic_battle(), _synthetic_mask()
    assert (
        _solve(b, mask, 4242, 0, 0, dose="S")
        == _solve(b, mask, 4242, 0, 0, dose="S", leaf_view=None)
    )


# --------------------------------------------------------------------------
# the reveal rules
# --------------------------------------------------------------------------

def _spend_pp(mon, move_id, pp):
    """poke-env's Move.current_pp is read-only; the harvest rehydrator wraps
    it the same way (rl/search/harvest.py::_rehydrate_mon)."""
    mon.moves[move_id] = _MoveView(_cached_move(move_id), pp)


def test_public_view_carries_species_moves_and_live_pp():
    b = synthetic_battle()
    _spend_pp(b.opponent_team["p2: Zapdos"], "thunderbolt", 11)
    v = public_view(b)
    assert v.revealed_species == {"chansey", "zapdos"}
    assert v.revealed_moves == {
        "chansey": ("softboiled",), "zapdos": ("thunderbolt", "drillpeck")
    }
    assert v.revealed_pp["zapdos"]["thunderbolt"] == 11


def test_plus_move_appends_last_and_ticks_pp():
    v = public_view(synthetic_battle())
    used = v.plus_move("chansey", "icebeam")
    # appended LAST, exactly where poke-env puts a newly seen move
    assert used.revealed_moves["chansey"] == ("softboiled", "icebeam")
    assert used.revealed_pp["chansey"]["icebeam"] == PEMove("icebeam", gen=1).max_pp - 1
    # a second use of an already-revealed move re-ticks and does not duplicate
    again = used.plus_move("chansey", "icebeam")
    assert again.revealed_moves["chansey"] == ("softboiled", "icebeam")
    assert again.revealed_pp["chansey"]["icebeam"] == PEMove("icebeam", gen=1).max_pp - 2
    # the root view is untouched (views are values, one per column)
    assert v.revealed_moves["chansey"] == ("softboiled",)


def _root_state(battle, seed=11):
    det = sample_determinization(battle, np.random.default_rng(seed))
    return det, battle_to_state(battle, det, BridgeCounters())


def test_det_blind_hides_the_bench_the_root_never_saw():
    b = synthetic_battle()
    det, state = _root_state(b)
    assert len(det["opponents"]) == 6  # the determinizer invents a full team
    as_is = shadow_battle(state, turn=b.turn)
    blind = shadow_battle(state, turn=b.turn, view=public_view(b))
    assert len(as_is.opponent_team) == 6
    assert {v.species for v in blind.opponent_team.values()} == {"chansey", "zapdos"}
    # our own side is fully observed in both
    assert len(as_is.team) == len(blind.team) == 2


def test_det_blind_opponent_active_slots_are_the_live_prior_fill():
    """The revealed move keeps p=1.0 and its live PP; the rest of the slots
    come from the encoder's own set prior, so at least one is below 1.0 —
    where the as-is encoding shows the determinizer's four at p=1.0."""
    b = synthetic_battle()
    _spend_pp(b.opponent_active_pokemon, "softboiled", 5)
    _, state = _root_state(b)
    blind = shadow_battle(state, turn=b.turn, view=public_view(b))
    slots = _opponent_move_slots(blind.opponent_active_pokemon)
    assert slots[0][0].id == "softboiled" and slots[0][1] == 1.0
    assert slots[0][0].current_pp == 5
    assert any(p < 1.0 for _, p in slots[1:]), [(m.id, p) for m, p in slots]
    as_is = shadow_battle(state, turn=b.turn)
    assert all(p == 1.0 for _, p in _opponent_move_slots(as_is.opponent_active_pokemon))


def test_det_blind_reveals_a_switch_in_but_not_its_moves():
    """A determinized bench mon the transition puts ON THE FIELD is revealed
    — the live game shows its species — while its moves stay unknown."""
    from poke_engine import generate_instructions

    from rl.search.matrix import _opp_bench_target

    b = synthetic_battle()
    det, state = _root_state(b)
    hidden = [
        s for s in det["opponents"]
        if s not in ("chansey", "zapdos")
    ]
    target = _opp_bench_target(state, np.random.default_rng(3))
    assert target in hidden or target == "zapdos"
    branch = max(
        generate_instructions(state, "bodyslam", target), key=lambda x: x.percentage
    )
    leaf = state.apply_instructions(branch)
    blind = shadow_battle(leaf, turn=b.turn + 1, view=public_view(b))
    assert blind.opponent_active_pokemon.species == target.lower()
    assert target.lower() in {v.species for v in blind.opponent_team.values()}
    if target not in ("chansey", "zapdos"):  # never seen before this leaf
        # species known, moveset not: every slot comes from the set prior
        det_moves = set(det["opponents"][target]["moves"])
        slots = _opponent_move_slots(blind.opponent_active_pokemon)
        assert slots and {m.id for m, _ in slots} != det_moves or any(
            p < 1.0 for _, p in slots
        )


def test_det_blind_is_per_column_not_per_decision(monkeypatch):
    """Each opponent column reveals its OWN move and no other: the views the
    leaf encoder sees must differ across columns."""
    seen = []
    real = shadow_battle

    def spy(state, turn, view=None):
        seen.append(None if view is None else view.revealed_moves.get("chansey"))
        return real(state, turn, view=view)

    import rl.search.matrix as matrix_mod

    monkeypatch.setattr(matrix_mod, "shadow_battle", spy)
    b = synthetic_battle()
    _solve(b, _synthetic_mask(), 4242, 0, 0, dose="S", leaf_view=public_view(b))
    revealed = {s for s in seen if s is not None}
    assert ("softboiled",) in revealed, revealed
    # the opponent's other three slots each add exactly one move, last
    extra = {s for s in revealed if len(s) == 2}
    assert len(extra) == 3, revealed
    assert all(s[0] == "softboiled" for s in extra)


# --------------------------------------------------------------------------
# contract 2: root parity against the LIVE observation
# --------------------------------------------------------------------------

_MON_SUB = {}
for _k in range(MON_DIM):
    if _k == 0:
        _MON_SUB[_k] = "hp"
    elif _k == 1:
        _MON_SUB[_k] = "fainted"
    elif _k == 2:
        _MON_SUB[_k] = "is_active"
    elif GEN1.mon_status_off <= _k < GEN1.mon_status_off + len(GEN1.statuses):
        _MON_SUB[_k] = "status"
    elif _k == GEN1.mon_level_off:
        _MON_SUB[_k] = "level"
    elif GEN1.mon_stats_off <= _k < GEN1.mon_stats_off + len(GEN1.base_stat_keys):
        _MON_SUB[_k] = "base_stats"
    elif GEN1.mon_types_off <= _k < GEN1.mon_types_off + len(GEN1.types):
        _MON_SUB[_k] = "types"
    elif _k == GEN1.mon_matchup_off:
        _MON_SUB[_k] = "matchup_off"
    elif _k == GEN1.mon_matchup_off + 1:
        _MON_SUB[_k] = "matchup_def"
    else:
        _MON_SUB[_k] = "speed_edge"


def _active_sub(k):
    if k == GEN1.active_counter_off:
        return "status_counter"
    if k == GEN1.active_counter_off + 1:
        return "preparing"
    return "boost_or_volatile"


def _move_sub(k):
    return ["known", "bp", "acc", "pp", "matchup"][k] if k < 5 else "other"


def dim_family(i: int) -> tuple[str, str]:
    """(block, field) for one obs index, derived from the encoder's own
    offsets so a layout change moves this with it."""
    o = GLOBAL_DIM
    if i < o:
        return ("global", ["turn", "our_fainted", "opp_fainted",
                           "force_switch", "trapped", "aliased"][i])
    if i < o + 6 * MON_DIM:
        return ("our_mon", _MON_SUB[(i - o) % MON_DIM])
    o += 6 * MON_DIM
    if i < o + ACTIVE_DIM:
        return ("our_active", _active_sub(i - o))
    o += ACTIVE_DIM
    if i < o + 4 * MOVE_DIM:
        return ("our_move", _move_sub((i - o) % MOVE_DIM))
    o += 4 * MOVE_DIM
    if i < o + 6 * (MON_DIM + 1):
        k = (i - o) % (MON_DIM + 1)
        return ("opp_mon", "revealed" if k == 0 else _MON_SUB[k - 1])
    o += 6 * (MON_DIM + 1)
    if i < o + ACTIVE_DIM:
        return ("opp_active", _active_sub(i - o))
    o += ACTIVE_DIM
    if i < o + 4 * MOVE_DIM:
        return ("opp_move", _move_sub((i - o) % MOVE_DIM))
    o += 4 * MOVE_DIM
    return ("id", "species" if (i - o) < 12 else "move")


# The transformed-Ditto blast radius: a copied base-stat line reaches battle1
# but not the static dex ShadowBattle reads, and every downstream dim moves.
_DITTO_FIELDS = frozenset(
    {"base_stats", "types", "matchup_off", "matchup_def", "speed_edge"}
)


def _declared(i: int, delta: float, has_ditto: bool) -> bool:
    block, field = dim_family(i)
    if block == "opp_mon" and field == "hp":
        return delta <= 0.01                      # opp_hp_grain
    if block == "global" and field == "trapped":
        return True                               # root_trapped
    if field == "preparing":
        return True                               # preparing
    if field == "status_counter":
        return True                               # sleep_rest
    if has_ditto and (field in _DITTO_FIELDS or field == "matchup"):
        return True                               # transform_ditto
    return False


def _root_parity(lanes, per_lane, view_on: bool):
    """(violations, dims_differing_per_root, exactly_equal_roots, n_roots)
    over the determinized ROOT encodings vs the harvested LIVE obs."""
    violations, n_diff, n_exact, n_roots = [], 0, 0, 0
    for lane in lanes:
        seed = int(lane[1:])
        for bi, si, row, battle in _harvest_decisions(lane, per_lane):
            live = row["obs"].astype(np.float32)
            has_ditto = any(
                m.species == "ditto"
                for m in [*battle.team.values(), *battle.opponent_team.values()]
            )
            view = public_view(battle) if view_on else None
            rng = decision_rng(seed, bi, int(battle.turn), si)
            for _ in range(DOSES["M"].n_det):
                det = sample_determinization(battle, rng)
                state = battle_to_state(battle, det, BridgeCounters())
                enc = embed_battle(
                    shadow_battle(state, turn=int(battle.turn), view=view),
                    _TYPE_CHART,
                )
                d = np.abs(enc - live)
                idx = np.flatnonzero(d > 0)
                n_roots += 1
                n_diff += idx.size
                n_exact += int(idx.size == 0)
                violations += [
                    (lane, bi, si, int(i), dim_family(int(i)), float(d[i]))
                    for i in idx if not _declared(int(i), float(d[i]), has_ditto)
                ]
    return violations, n_diff / n_roots, n_exact, n_roots


@_needs_harvest
@_needs_d26_encoder
def test_det_blind_root_matches_the_live_obs_outside_declared_families():
    lanes = ("s62", "s63", "s64", "s65")
    bad, per_root, exact, n = _root_parity(lanes, 25, view_on=True)
    assert not bad, (
        f"{len(bad)} undeclared root-encoding differences over {n} roots; "
        f"first 5: {bad[:5]}"
    )
    # the declared residual itself stays small and the artefact is gone: as-is
    # measured 35.93 dims/root with 0.8% of roots exact
    assert per_root < 2.0, per_root
    assert exact / n > 0.25, (exact, n)


@_needs_harvest
@_needs_d26_encoder
def test_as_is_root_fails_the_same_parity_check():
    """The control. Without det_blind the identical assertion must FAIL, or
    the parity test above is measuring nothing."""
    bad, per_root, exact, n = _root_parity(("s62",), 25, view_on=False)
    assert bad, "the as-is root encoding matched the live obs — impossible"
    assert per_root > 10.0, per_root
    families = {f for *_, f, _ in bad}
    assert ("opp_mon", "revealed") in families, families


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------

class _StubAgent:
    def __init__(self):
        import torch

        self._torch = torch
        self.aux_head = self._aux

    def actor(self, obs_t, return_features=True):
        return self._torch.zeros((obs_t.shape[0], 10)), obs_t

    def _aux(self, feats):
        return self._torch.zeros((feats.shape[0], N_L6))

    def critic(self, t):
        return self._torch.zeros((t.shape[0],))


def test_search_agent_rejects_an_unknown_leaf_encoding():
    assert LEAF_ENCODINGS == (None, "det_blind")
    with pytest.raises(AssertionError, match="leaf_encoding"):
        SearchAgent(_StubAgent(), DOSES["S"], 7, leaf_encoding="bench_blind")


@pytest.mark.parametrize(
    "leaf_encoding,expect_view", [(None, False), ("det_blind", True)]
)
def test_search_agent_passes_the_view_only_when_asked(
    monkeypatch, leaf_encoding, expect_view
):
    import rl.search.agent as agent_mod

    seen = {}
    real = agent_mod.solve_decision

    def spy(*a, **kw):
        seen["leaf_view"] = kw.get("leaf_view")
        return real(*a, **kw)

    monkeypatch.setattr(agent_mod, "solve_decision", spy)
    sa = SearchAgent(
        _StubAgent(), DOSES["S"], 7, leaf_encoding=leaf_encoding
    )
    assert sa.leaf_encoding == leaf_encoding
    b = synthetic_battle()
    sa.act(b, np.zeros(OBS_DIM, dtype=np.float32), _synthetic_mask(), 3, 1)
    assert isinstance(seen["leaf_view"], PublicView) is expect_view


def test_ch3_eval_jobs_carry_the_leaf_encoder():
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import ch3_eval  # noqa: E402

    jobs = ch3_eval._jobs({
        "arms": {
            "S3M": {"kind": "search", "dose": "M", "lanes": ["s104"]},
            "S3B": {"kind": "search", "dose": "M", "lanes": ["s104"],
                    "leaf_encoding": "det_blind"},
        }
    })
    assert jobs["s3m_s104"]["leaf_encoding"] is None
    assert jobs["s3b_s104"]["leaf_encoding"] == "det_blind"

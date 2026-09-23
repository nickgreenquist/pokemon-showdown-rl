"""R7 G2's operator on a LIVE battle (`rl/search/lop.py::NativeLOp`), OFFLINE on
the R1 harvest corpus (the frozen poke-env battles gate R1-E read; no server,
no Foul Play). Skips without the corpus, the built extension, or a checkpoint.

(1) THE MATCHED GREEDY: with the gate shut (margin_gate huge) the L-op plays,
    on every decision, exactly the action the greedy `ensemble_seat` anchor
    (`EnsembleAgent.act`) plays -- the comparison G2 makes isolates the search.
(2) THE OPERATOR RUNS: at the working dials it builds worlds through B6's
    bridge (refusals counted by family, never silent), returns legal actions,
    moves off greedy on some decisions, and reports its counters; the soft-BR
    self-check inside `act` holds on every world (it raises otherwise).
(3) REPLAY: the same (battle_index, turn, decision_index) gives the same
    action and the same stats.
(4) THE DIALS are the signature's: an unknown `lop:` key or `solve:` key fails.
"""

from __future__ import annotations

import glob
import os
import pathlib
import pickle

import numpy as np
import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
HARVEST = ROOT / "results/ch3_r1/harvest_s62.pkl"
CKPTS = sorted(glob.glob("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/runs/showdown_monster200m_w_s1*/ckpt_2000000*.pt"))

pytestmark = pytest.mark.skipif(not HARVEST.exists() or len(CKPTS) < 2,
                                reason="the R1 harvest corpus or the R5 W finals are not on this box")


def _roots(n: int, stride: int = 7):
    from rl.search.harvest import rehydrate_battle

    with open(HARVEST, "rb") as fh:
        episodes = pickle.load(fh)
    out, seen = [], 0
    for bi, ep in enumerate(episodes):
        for si, row in enumerate(ep["rows"]):
            if row["aliased"]:
                continue
            seen += 1
            if seen % stride:
                continue
            out.append((bi, si, row, rehydrate_battle(row["battle"])))
            if len(out) >= n:
                return out
    return out


@pytest.fixture(scope="module")
def parts():
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from eval_checkpoint import _load_showdown_agent
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.envs.engine_tables import build_tables
    from rl.search.ensemble import EnsembleAgent

    members = []
    for p in CKPTS[:2]:
        c = load_checkpoint(p)
        a = _load_showdown_agent(c, Config(**c["config"]))
        a.actor.eval(); a.critic.eval()
        members.append(a)
    tables, _ = build_tables()
    return EnsembleAgent(members), tables, _roots(40)


SOLVE = {"cols_k": 4, "chance_s": 2, "tau": 0.05}


def test_the_gate_shut_plays_the_ensemble_seats_greedy_action(parts):
    from rl.search.lop import NativeLOp

    ens, tables, roots = parts
    lop = NativeLOp(ens, tables, worlds=2, margin_gate=1e9, seed=5, solve=SOLVE)
    for bi, si, row, battle in roots:
        a, _ = lop.act(battle, row["obs"], row["mask"], bi, si)
        assert a == ens.act(row["obs"], row["mask"], deterministic=True), (bi, si)
    assert lop.counters["search/overrides"] == 0


def test_the_operator_runs_builds_worlds_and_counts_refusals(parts):
    from rl.search.lop import NativeLOp

    ens, tables, roots = parts
    lop = NativeLOp(ens, tables, worlds=4, margin_gate=0.01, seed=5, solve=SOLVE)
    for bi, si, row, battle in roots:
        a, stats = lop.act(battle, row["obs"], row["mask"], bi, si)
        assert row["mask"][a], (bi, si, a)
        if stats:
            assert stats["search/leaves"] > 0 and 1 <= stats["lop/worlds"] <= 4
    rep = lop.report()
    assert rep["search/searched"] > 0.5 * len(roots), rep
    assert rep["lop/worlds_built_rate"] > 0.9, rep                  # R1-E: 256 of 13,396 roots refused
    assert rep["lop/mask_mismatch"] == 0, rep                        # R1-E: mask parity exact
    assert 0.0 <= rep["search/override_rate"] <= 0.5, rep
    assert all(isinstance(v, float) for v in rep["lop/refused"].values())


def test_a_decision_replays(parts):
    from rl.search.lop import NativeLOp

    ens, tables, roots = parts
    bi, si, row, battle = roots[3]
    one = NativeLOp(ens, tables, worlds=3, margin_gate=0.0, seed=9, solve=SOLVE).act(battle, row["obs"], row["mask"], bi, si)
    two = NativeLOp(ens, tables, worlds=3, margin_gate=0.0, seed=9, solve=SOLVE).act(battle, row["obs"], row["mask"], bi, si)
    assert one[0] == two[0] and one[1].keys() == two[1].keys()
    assert all(one[1][k] == two[1][k] for k in one[1] if k != "lop/ms")


def test_the_dials_are_the_signatures():
    from rl.search.lop import LOP_DIALS, NativeLOp, lop_from

    assert LOP_DIALS == ("worlds", "margin_gate", "seed", "solve"), LOP_DIALS
    assert lop_from({"worlds": 8, "margin_gate": 0.01}) == {"worlds": 8, "margin_gate": 0.01}
    with pytest.raises(ValueError, match="unknown L-op dial"):
        lop_from({"worlds": 8, "gate": 0.01})
    with pytest.raises(ValueError, match="unknown native-search dial"):
        NativeLOp(type("E", (), {"members": []})(), None, solve={"cols_k": 4, "tua": 0.05})
    with pytest.raises(ValueError, match="solve dials must be given"):
        NativeLOp(type("E", (), {"members": []})(), None)

"""DEEP SEARCH Step A -- the native tree as an inference operator on a LIVE battle
(`rl/search/tree_lop.py::NativeTreeLOp`), OFFLINE on the R1 harvest corpus (frozen
poke-env battles; no server, no Foul Play). Skips without the corpus, the built
extension, or the three R5 W finals.

(1) THE MATCHED GREEDY: with the gate shut the operator plays, on every decision,
    exactly the greedy `ensemble_seat` anchor's action -- an arm against that
    anchor isolates the search.
(2) THE OPERATOR RUNS: it builds worlds (refusals by family, never silent), searches
    them as one tree, returns legal actions, moves off greedy somewhere, and its
    report carries the dose in leaves AND depth.
(3) REPLAY: the same (battle_index, turn, decision_index) gives the same action and
    stats.
(4) THE DIALS are the signatures': an unknown `tree_lop:` or `tree:` key fails.
(5) The batched prior IS the root prior's arithmetic (EnsembleAgent.scores ->
    _softmax_masked), row for row.
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
MAIN = pathlib.Path("/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl")
HARVEST = next((p for p in (ROOT / "results/ch3_r1/harvest_s62.pkl", MAIN / "results/ch3_r1/harvest_s62.pkl")
                if p.exists()), ROOT / "results/ch3_r1/harvest_s62.pkl")
CKPTS = sorted(glob.glob(str(MAIN / "runs/showdown_monster200m_w_s1*/ckpt_2000000*.pt")))

pytestmark = pytest.mark.skipif(not HARVEST.exists() or len(CKPTS) < 3,
                                reason="the R1 harvest corpus or the three R5 W finals are not on this box")

TREE = {"sims": 400, "mode": "br_prior", "depth_cap": 6, "cols_k": 4, "chance_k": 2, "root_rule": "soft_br", "tau": 0.05}
# gumbel_mctx at mctx's sigma is argmax-Q in all but name: it moves off greedy, so the override path is exercised
SHARP = {**TREE, "root_rule": "gumbel_mctx"}


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
    for p in CKPTS[:3]:
        c = load_checkpoint(p)
        a = _load_showdown_agent(c, Config(**c["config"]))
        a.actor.eval(); a.critic.eval()
        members.append(a)
    tables, _ = build_tables()
    return EnsembleAgent(members), tables, _roots(12)


def test_the_gate_shut_plays_the_ensemble_seats_greedy_action(parts):
    from rl.search.tree_lop import NativeTreeLOp

    ens, tables, roots = parts
    op = NativeTreeLOp(ens, tables, worlds=2, margin_gate=1e9, seed=5, tree=TREE)
    for bi, si, row, battle in roots:
        a, _ = op.act(battle, row["obs"], row["mask"], bi, si)
        assert a == ens.act(row["obs"], row["mask"], deterministic=True), (bi, si)
    assert op.counters["search/overrides"] == 0


def test_the_operator_runs_and_reports_depth(parts):
    from rl.search.tree_lop import NativeTreeLOp

    ens, tables, roots = parts
    op = NativeTreeLOp(ens, tables, worlds=2, margin_gate=0.0, seed=5, tree=SHARP)
    for bi, si, row, battle in roots:
        a, stats = op.act(battle, row["obs"], row["mask"], bi, si)
        assert row["mask"][a], (bi, si, a)
        if stats:
            assert stats["search/leaves"] > 0 and 1 <= stats["tree_lop/worlds"] <= 2
            assert stats["tree/sims"] == TREE["sims"] or stats["tree/sims"] >= TREE["sims"]
    rep = op.report()
    assert rep["search/searched"] > 0.5 * len(roots), rep
    assert rep["tree_lop/worlds_built_rate"] > 0.9 and rep["tree_lop/mask_mismatch"] == 0, rep
    assert rep["tree_lop/errors"] == 0 and rep["tree_lop/tree_errors"] == 0 and rep["tree_lop/fallback"] == 0, rep
    assert rep["tree_lop/mean/tree/depth_mean"] > 1.5, rep            # it goes below the one-ply layer
    assert rep["tree_lop/argmax_moved_rate"] > 0 and rep["search/overrides"] > 0, rep   # the override path runs
    assert rep["search/override_rate"] <= 1.0, rep


def test_a_decision_replays(parts):
    from rl.search.tree_lop import NativeTreeLOp

    ens, tables, roots = parts
    bi, si, row, battle = roots[3]
    one = NativeTreeLOp(ens, tables, worlds=2, margin_gate=0.0, seed=9, tree=TREE).act(battle, row["obs"], row["mask"], bi, si)
    two = NativeTreeLOp(ens, tables, worlds=2, margin_gate=0.0, seed=9, tree=TREE).act(battle, row["obs"], row["mask"], bi, si)
    assert one[0] == two[0] and one[1].keys() == two[1].keys()
    timing = ("tree_lop/ms", "tree/ms_value", "tree/ms_prior", "search/rust_ms")
    assert all(one[1][k] == two[1][k] for k in one[1] if k not in timing)


def test_the_dials_are_the_signatures():
    from rl.search.tree_lop import TREE_LOP_DIALS, NativeTreeLOp, tree_lop_from

    assert TREE_LOP_DIALS == ("worlds", "margin_gate", "seed", "tree")
    assert tree_lop_from({"worlds": 8, "tree": {"sims": 100}}) == {"worlds": 8, "tree": {"sims": 100}}
    with pytest.raises(ValueError, match="unknown tree L-op dial"):
        tree_lop_from({"solve": {}})
    with pytest.raises(ValueError, match="unknown native-tree dial"):
        NativeTreeLOp(type("E", (), {"members": []})(), None, tree={"cols": 4})
    with pytest.raises(ValueError, match="tree dials must be given"):
        NativeTreeLOp(type("E", (), {"members": []})(), None)


def test_the_batched_prior_is_the_root_priors_arithmetic(parts):
    from rl.search.lop import _softmax_masked
    from rl.search.tree_lop import NativeTreeLOp

    ens, tables, roots = parts
    op = NativeTreeLOp(ens, tables, tree=TREE)
    obs = np.stack([row["obs"] for _b, _s, row, _bt in roots[:8]]).astype(np.float32)
    mask = np.stack([row["mask"] for _b, _s, row, _bt in roots[:8]]).astype(bool)
    got = op.prior_fn(obs, mask)
    for i in range(len(obs)):
        want = _softmax_masked(ens.scores(obs[i], mask[i]), mask[i])
        assert np.allclose(got[i], want, rtol=0, atol=1e-6), i
        assert int(np.argmax(got[i])) == int(np.argmax(want))

"""CH3 R0 offline tests: the ensemble agent's contracts, the grader's cells,
and the executable pre-reg's integrity. No server, no checkpoints."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import ch3_grade  # noqa: E402
from rl.search.ensemble import EnsembleAgent  # noqa: E402

PREREG = REPO / "configs/eval/ch3_rung0.yaml"


def _stub(logits_row):
    t = torch.tensor([logits_row], dtype=torch.float32)
    return SimpleNamespace(actor=lambda x: t.clone(), device="cpu", obs_rank=1)


OBS = np.zeros(8, dtype=np.float32)


def test_masked_action_never_wins():
    # action 0 has the max raw logit but is masked; ensemble must not pick it
    m = _stub([10.0, 1.0, 0.5])
    mask = np.array([False, True, True])
    a = EnsembleAgent([m]).act(OBS, mask, deterministic=True)
    assert a == 1


def test_single_member_reproduces_argmax():
    # R0-c's mechanism: log_softmax is monotone, so wrapper == member argmax
    rng = np.random.default_rng(0)
    for _ in range(50):
        row = rng.normal(size=6).tolist()
        mask = rng.random(6) < 0.7
        if not mask.any():
            mask[0] = True
        m = _stub(row)
        wrapped = EnsembleAgent([m]).act(OBS, mask, deterministic=True)
        from rl.common.masking import masked_logits

        direct = int(
            masked_logits(torch.tensor([row]), torch.tensor(mask)).argmax()
        )
        assert wrapped == direct


def test_mean_logprob_argmax_not_vote():
    # member A: confident on 0; members B, C: mildly prefer 1. The log-prob
    # MEAN picks 0 (A's confidence outweighs two mild votes) even though the
    # majority VOTE is 1 — the flip counter must see a flip.
    a = _stub([8.0, 0.0, -8.0])
    b = _stub([0.0, 0.4, -8.0])
    c = _stub([0.0, 0.4, -8.0])
    ens = EnsembleAgent([a, b, c])
    mask = np.array([True, True, False])
    chosen = ens.act(OBS, mask, deterministic=True)
    assert chosen == 0
    assert ens.decisions == 1 and ens.flips == 1  # modal member choice is 1


def test_ensemble_refuses_sampling():
    with pytest.raises(AssertionError):
        EnsembleAgent([_stub([0.0, 1.0])]).act(OBS, np.array([True, True]))


def test_grader_cells_and_boundaries():
    land, FLOOR = ch3_grade.land, ch3_grade.FLOOR
    hi = max(FLOOR, 2 * 0.02)  # 0.04 > floor: B2/B4 exist
    assert land(0.05, hi) == "B1"
    assert land(FLOOR, hi) == "B2"
    assert land(0.0, hi) == "B3"
    assert land(-FLOOR, hi) == "B4"
    assert land(-0.05, hi) == "B5"
    # floor governs: B2/B4 empty, boundaries collapse outward
    assert land(FLOOR, FLOOR) == "B1"
    assert land(-FLOOR, FLOOR) == "B5"
    ch3_grade.check_partition(FLOOR)
    ch3_grade.check_partition(0.0501)


def test_grader_selftest_green():
    ch3_grade.selftest()


def test_prereg_integrity():
    prereg = yaml.safe_load(PREREG.read_text())
    for field in (
        "rung", "title", "status", "results_dir", "checkpoints", "arms",
        "comparator", "pairing", "clustering_unit", "aggregator",
        "recorded_only", "credit_line", "se_terms", "se_rule", "branches",
        "dose_matched", "how_we_would_know", "readme_status_obligation",
        "ledger_days_projected", "lane_width", "burns_training_seeds",
    ):
        assert field in prereg, f"pre-reg missing required field {field}"
    assert prereg["credit_line"] == ch3_grade.CREDIT_LINE  # byte-equal (lesson 4)
    assert prereg["burns_training_seeds"] is False
    assert prereg["branches"] == "five_cell_floor"
    assert set(prereg["checkpoints"]) == {"s62", "s63", "s64", "s65"}
    for spec in prereg["checkpoints"].values():
        assert len(spec["sha256"]) == 64


def test_driver_job_enumeration():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ch3_eval", REPO / "scripts/ch3_eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prereg = yaml.safe_load(PREREG.read_text())
    jobs = mod._jobs(prereg)
    assert len(jobs) == 11  # 4 A0 + 3 A1 batches + 4 LOO
    assert jobs["a2_loo_s62"]["members"] == ["s63", "s64", "s65"]
    assert jobs["a1_b2"]["batch"] == 2


# ---------------------------------------------------------------------------
# R2 driver: job table kinds, the battle2 sentinel, the search adapter
# ---------------------------------------------------------------------------

import ch3_eval  # noqa: E402


def test_jobs_search_kind_and_legacy_shape():
    legacy = {"arms": {
        "A0": {"kind": "policy", "lanes": ["s62", "s63"]},
        "A1": {"kind": "ensemble", "batches": 2, "members": ["s62", "s63"]},
        "A2": {"kind": "ensemble_loo", "members": ["s62", "s63"]},
    }}
    jobs = ch3_eval._jobs(legacy)
    assert set(jobs) == {"a0_s62", "a0_s63", "a1_b0", "a1_b1",
                         "a2_loo_s62", "a2_loo_s63"}
    r2 = {"arms": {
        "A0": {"kind": "policy", "lanes": ["s62", "s63"]},
        "A1S": {"kind": "search", "lanes": ["s62", "s63"], "dose": "M"},
    }}
    jobs = ch3_eval._jobs(r2)
    assert set(jobs) == {"a0_s62", "a0_s63", "a1s_s62", "a1s_s63"}
    assert jobs["a1s_s62"] == {"arm": "A1S", "members": ["s62"],
                               "search_dose": "M"}
    assert "search_dose" not in jobs["a0_s62"]
    with pytest.raises(ValueError):
        ch3_eval._jobs({"arms": {"X": {"kind": "mcts"}}})


def test_battle2_sentinel_raises_only_from_search_frames(tmp_path):
    class FakePoke:
        pass

    poke = FakePoke()
    poke.battle2 = "seat2-state"
    handle = ch3_eval._install_battle2_sentinel(poke)
    try:
        # harness access: transparent, current value visible
        assert poke.battle2 == "seat2-state"
        # harness set intercepted, value flows through
        poke.battle2 = "next"
        assert poke.battle2 == "next"
        # access from an rl/search/-filenamed frame: PurityIncident
        search_file = tmp_path / "rl" / "search" / "evil.py"
        search_file.parent.mkdir(parents=True)
        search_file.write_text("def peek(p):\n    return p.battle2\n")
        ns = {}
        exec(compile(search_file.read_text(), str(search_file), "exec"), ns)
        with pytest.raises(ch3_eval.PurityIncident):
            ns["peek"](poke)
        # double install refuses
        with pytest.raises(AssertionError):
            ch3_eval._install_battle2_sentinel(poke)
    finally:
        ch3_eval._uninstall_battle2_sentinel(poke, handle)
    assert poke.battle2 == "next"          # restored to the instance
    assert "battle2" not in type(poke).__dict__


def test_search_adapter_indices_and_chunk_deltas():
    class StubSA:
        def __init__(self):
            self.counters = {"search/decisions": 0,
                             "search/placeholder_skips": 0, "search/flips": 0}
            self.calls = []

        def act(self, battle, obs, mask, battle_index, decision_index):
            self.counters["search/decisions"] += 1
            self.calls.append((battle.battle_tag, battle_index, decision_index))
            return 6, {"search/leaves": 10, "search/chosen": 6}

        def entropy_median(self):
            return 0.5

    class StubEnv:
        def __init__(self):
            self.unwrapped = SimpleNamespace(
                _env=SimpleNamespace(env=SimpleNamespace(battle1=None))
            )

        def set_tag(self, tag):
            self.unwrapped._env.env.battle1 = SimpleNamespace(battle_tag=tag)

    sa, env = StubSA(), StubEnv()
    ad = ch3_eval._SearchEvalAdapter(sa, env)
    ad.begin_chunk(300)  # chunk 1 of a 300-battle chunking
    env.set_tag("battle-1")
    ad.act(np.zeros(4), np.ones(10, bool))
    ad.act(np.zeros(4), np.ones(10, bool))
    env.set_tag("battle-2")
    ad.act(np.zeros(4), np.ones(10, bool))
    # global episode indexing from the chunk base; per-battle decision reset
    assert sa.calls == [("battle-1", 300, 0), ("battle-1", 300, 1),
                        ("battle-2", 301, 0)]
    s1 = ad.chunk_summary()
    assert s1["search/decisions"] == 3 and s1["search/searched_decisions"] == 3
    assert s1["search/leaves_mean"] == 10.0
    # deltas: a second chunk reports only its own counts
    ad.begin_chunk(600)
    env.set_tag("battle-3")
    ad.act(np.zeros(4), np.ones(10, bool))
    s2 = ad.chunk_summary()
    assert s2["search/decisions"] == 1
    assert sa.calls[-1] == ("battle-3", 600, 0)

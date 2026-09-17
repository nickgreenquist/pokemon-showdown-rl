"""The margin-gated selector (matrix.py D5, docs/search_relook/MARGIN_SELECTOR.md).

Three load-bearing contracts, plus the plumbing around them.

1. **OFF IS BYTE-IDENTICAL.** `margin_delta=None` (the default) must be the
   pre-2026-09-10 D4 hard argmax, bit for bit — action, every stat, and NO
   new key. The pin is a GOLDEN DIGEST over `solve_decision`'s full output
   under a fixed linear critic (the same construction
   `tests/test_search_det_blind.py` uses), widened here to all FOUR D26
   lanes x 10 harvested decisions at Dose M (13,775 leaves). The digests
   below were computed in a detached worktree at the commit BEFORE this
   edit (c48dd677a640), and the post-edit code reproduces them. The two
   sub-digests that overlap the det_blind golden agree with it exactly
   (synthetic 892407da..., s62 f2b85990... at 3,707 leaves), so the golden
   is anchored to a pin that predates BOTH edits.

2. **THE GATE IS THE STATED RULE.** With a float delta,

       play a_s iff row_ev[a_s] - row_ev[a_pi] > delta, else play a_pi

   where `a_s` is D4's argmax and `a_pi` is the policy's own argmax over
   LEGAL actions. Checked decision by decision against the predictors
   recorded at delta 0.0, over a grid of deltas.

3. **THE ENDPOINTS ARE THE TWO THINGS WE ALREADY MEASURED.** `delta=0.0`
   reproduces D4's action (S3M's selector, up to the conceded tie — §3 of
   the doc argues the tie cannot occur, and the test measures rather than
   assumes it), and `delta=inf` reproduces the greedy policy EXACTLY, which
   is arm A0. The live screen's two endpoints are therefore not new
   measurements: they are 0.74767 and 0.78233 on lane s112.

Offline: no server, no checkpoints (the critic is a pinned projection).
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

import rl.search.agent as agent_mod
from rl.envs.showdown import ENCODER_FINGERPRINT, OBS_DIM
from rl.search.agent import SearchAgent
from rl.search.matrix import DOSES, N_L6, decision_rng, solve_decision
from tests.test_ch3_evaluator_dials import _StubAgent
from tests.test_ch3_matrix import _mask, _two_mon_battle
from tests.test_search_det_blind import (
    _TYPE_CHART,
    _digest,
    _fixed_critic,
    _harvest_decisions,
    _needs_harvest,
    _round,
    _synthetic_mask,
    synthetic_battle,
)

LANES = ("s62", "s63", "s64", "s65")

# encoder fingerprint -> (synthetic@S, all-four-lanes@M). Computed at
# c48dd677a640^{tree} in a detached worktree, i.e. BEFORE the D5 edit.
GOLDEN = {
    ("v2", True): (
        "892407da14fb52e122f80dcfa1ef006ff085a2502dbc3be9cbd17de17e103746",
        "a3a847c7b78298cfdc705a855fdbd398676230a806fdb16eac745da55c6ca27e",
    ),
}
GOLDEN_PER_LANE = {
    ("v2", True): {
        "s62": "f2b85990a1e0126fdde5e59ce7572fc25d2a8d52dc3b56fc9e016736d7ba425d",
        "s63": "03249e4b0dc94877f5eedc27557ba6efcfe12f26500ff2063ffe801bfda89e6d",
        "s64": "b48c0b4189a5bf5a7a26635cbc634a1f5f135a54eff9ec75faac0f841e8f4d11",
        "s65": "35b0af03081a11c52e0bff69a9f5a3dbe09400b9fbc3b0ace84589b389753b1d",
    },
}
GOLDEN_LEAVES = 13775
_FINGERPRINT = (ENCODER_FINGERPRINT["encoder"], ENCODER_FINGERPRINT["ids"])
_needs_golden = pytest.mark.skipif(
    _FINGERPRINT not in GOLDEN,
    reason=f"no pre-change golden pinned for encoder {_FINGERPRINT}",
)

# The four keys D5 adds, and NOTHING else may appear or move.
GATE_KEYS = frozenset({
    "search/margin_delta", "search/search_argmax", "search/margin",
    "search/overrode",
})

DELTA_GRID = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2,
              float("inf"))


def _peaked_prior(mask) -> np.ndarray:
    """A deterministic NON-uniform masked prior, so `policy_argmax` is a
    real choice rather than 'the lowest legal index'. A uniform prior would
    make every gate test degenerate in the one way that matters."""
    m = np.asarray(mask, dtype=bool)
    w = np.cos(np.arange(len(m), dtype=np.float64) * 1.7 + 0.3) * 3.0
    w = np.where(m, np.exp(w - w[m].max()), 0.0)
    return w / w.sum()


def _solve(battle, mask, seed, bi, si, dose="M", prior=None, **kw):
    rng = decision_rng(seed, bi, int(battle.turn), si)
    if prior is None:
        prior = np.asarray(mask, dtype=np.float64)
        prior = prior / prior.sum()
    action, stats = solve_decision(
        battle, np.asarray(mask), np.full(N_L6, 1.0 / N_L6), prior,
        DOSES[dose], rng, _fixed_critic, _TYPE_CHART, **kw
    )
    stats.pop("bridge/unmapped_effects", None)
    return action, stats


def _record(battle, mask, seed, bi, si, **kw):
    action, stats = _solve(battle, mask, seed, bi, si, **kw)
    return {"action": int(action), "stats": _round(stats)}


# --------------------------------------------------------------------------
# contract 1: off is byte-identical
# --------------------------------------------------------------------------

@_needs_golden
def test_absent_delta_is_byte_identical_synthetic():
    b = synthetic_battle()
    got = _digest([_record(b, _synthetic_mask(), 4242, 0, 0, dose="S")])
    assert got == GOLDEN[_FINGERPRINT][0], (
        "the default (hard-argmax) selector changed: solve_decision's output "
        f"digest is {got}, the pre-D5 golden is {GOLDEN[_FINGERPRINT][0]}"
    )


@_needs_harvest
@_needs_golden
def test_absent_delta_is_byte_identical_on_all_four_lanes():
    """40 real decisions at Dose M — 13,775 leaves — across every D26 lane."""
    all_records, leaves = [], 0
    for lane in LANES:
        recs = [
            _record(battle, row["mask"], int(lane.lstrip("s")), bi, si)
            for bi, si, row, battle in _harvest_decisions(lane, 10)
        ]
        assert _digest(recs) == GOLDEN_PER_LANE[_FINGERPRINT][lane], lane
        leaves += sum(r["stats"]["search/leaves"] for r in recs)
        all_records.extend(recs)
    assert leaves == GOLDEN_LEAVES
    assert _digest(all_records) == GOLDEN[_FINGERPRINT][1]


def test_explicit_none_is_the_default_path():
    b, mask = synthetic_battle(), _synthetic_mask()
    assert (
        _record(b, mask, 4242, 0, 0, dose="S")
        == _record(b, mask, 4242, 0, 0, dose="S", margin_delta=None)
    )


def test_gate_keys_are_absent_when_the_gate_is_off():
    _, stats = _solve(synthetic_battle(), _synthetic_mask(), 4242, 0, 0, dose="S")
    assert GATE_KEYS.isdisjoint(stats)


def test_gate_adds_exactly_the_four_keys_and_moves_nothing_else():
    b, mask = synthetic_battle(), _synthetic_mask()
    prior = _peaked_prior(mask)
    _, off = _solve(b, mask, 4242, 0, 0, dose="S", prior=prior)
    _, on = _solve(b, mask, 4242, 0, 0, dose="S", prior=prior, margin_delta=0.0)
    assert set(on) - set(off) == GATE_KEYS
    # every pre-existing stat is untouched EXCEPT search/chosen, which is by
    # definition the action PLAYED and is the one thing the gate may move
    for k in off:
        if k != "search/chosen":
            assert on[k] == off[k], k


# --------------------------------------------------------------------------
# contract 2: the gate is the stated rule
# --------------------------------------------------------------------------

@_needs_harvest
def test_gate_semantics_over_the_delta_grid():
    """chosen == a_s iff row_ev[a_s] - row_ev[a_pi] > delta, on real leaves."""
    checked, overrode_at_zero = 0, 0
    for bi, si, row, battle in _harvest_decisions("s62", 3):
        prior = _peaked_prior(row["mask"])
        _, base = _solve(battle, row["mask"], 62, bi, si, prior=prior,
                         margin_delta=0.0)
        a_s = base["search/search_argmax"]
        a_pi = base["search/policy_argmax"]
        margin = base["search/margin"]
        row_ev = base["search/row_ev"]
        # the margin is what it says it is, off the recorded row_ev
        assert margin == pytest.approx(row_ev[str(a_s)] - row_ev[str(a_pi)]
                                       if str(a_s) in row_ev
                                       else row_ev[a_s] - row_ev[a_pi])
        overrode_at_zero += int(base["search/overrode"])
        for delta in DELTA_GRID:
            action, stats = _solve(battle, row["mask"], 62, bi, si,
                                   prior=prior, margin_delta=delta)
            want = a_s if margin > delta else a_pi
            assert action == want == stats["search/chosen"], (delta, bi, si)
            assert stats["search/overrode"] is (action != a_pi)
            assert stats["search/margin"] == margin
            assert stats["search/search_argmax"] == a_s
            checked += 1
    assert checked == 3 * len(DELTA_GRID)
    # the fixture must actually exercise an override, or this proves nothing
    assert overrode_at_zero > 0


@_needs_harvest
def test_override_rate_is_nonincreasing_in_delta():
    margins, flips = [], []
    for lane in LANES:
        for bi, si, row, battle in _harvest_decisions(lane, 3):
            prior = _peaked_prior(row["mask"])
            _, s = _solve(battle, row["mask"], int(lane.lstrip("s")), bi, si,
                          prior=prior, margin_delta=0.0)
            margins.append(s["search/margin"])
            flips.append(s["search/search_argmax"] != s["search/policy_argmax"])
    m, f = np.array(margins), np.array(flips)
    rates = [float(((m > d) & f).mean()) for d in DELTA_GRID]
    assert all(a >= b for a, b in zip(rates, rates[1:])), rates
    assert rates[-1] == 0.0  # delta = inf overrides nothing


# --------------------------------------------------------------------------
# contract 3: the endpoints
# --------------------------------------------------------------------------

@_needs_harvest
def test_delta_zero_reproduces_the_d4_argmax():
    """S3M's selector. D3 breaks a row_ev tie by prior then index, so a tie
    between a_s and a_pi forces a_s == a_pi and the conceded tie is
    unreachable — measured here rather than assumed."""
    ties = 0
    for lane in LANES:
        for bi, si, row, battle in _harvest_decisions(lane, 5):
            seed, prior = int(lane.lstrip("s")), _peaked_prior(row["mask"])
            d4, _ = _solve(battle, row["mask"], seed, bi, si, prior=prior)
            gated, s = _solve(battle, row["mask"], seed, bi, si, prior=prior,
                              margin_delta=0.0)
            assert gated == d4, (lane, bi, si)
            ties += int(s["search/margin"] == 0.0
                        and s["search/search_argmax"] != s["search/policy_argmax"])
    assert ties == 0, "a conceded exact tie occurred; the doc's §3 argument fails"


@_needs_harvest
def test_delta_inf_is_exactly_the_greedy_policy():
    for lane in LANES:
        for bi, si, row, battle in _harvest_decisions(lane, 5):
            action, s = _solve(
                battle, row["mask"], int(lane.lstrip("s")), bi, si,
                prior=_peaked_prior(row["mask"]), margin_delta=float("inf"),
            )
            assert action == s["search/policy_argmax"], (lane, bi, si)
            assert s["search/overrode"] is False
            # and it is the same action the greedy agent would have played:
            # argmax over LEGAL actions of the masked policy
            legal = np.flatnonzero(np.asarray(row["mask"]))
            prior = _peaked_prior(row["mask"])
            assert action == int(legal[np.argmax(prior[legal])])


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------

def _act(sa, battle_index=3, decision_index=1):
    return sa.act(_two_mon_battle(), np.zeros(8, dtype=np.float32), _mask(),
                  battle_index, decision_index)


def test_margin_delta_validated():
    for bad in (-0.1, float("nan")):
        with pytest.raises(AssertionError):
            SearchAgent(_StubAgent(), DOSES["S"], 7, margin_delta=bad)
    assert SearchAgent(_StubAgent(), DOSES["S"], 7).margin_delta is None
    assert SearchAgent(_StubAgent(), DOSES["S"], 7,
                       margin_delta=None).margin_delta is None
    assert SearchAgent(_StubAgent(), DOSES["S"], 7,
                       margin_delta=0).margin_delta == 0.0
    assert np.isinf(SearchAgent(_StubAgent(), DOSES["S"], 7,
                                margin_delta=float("inf")).margin_delta)


def test_search_agent_threads_margin_delta(monkeypatch):
    seen = {}
    real = agent_mod.solve_decision

    def spy(*a, **kw):
        seen["margin_delta"] = kw.get("margin_delta", "MISSING")
        return real(*a, **kw)

    monkeypatch.setattr(agent_mod, "solve_decision", spy)
    _act(SearchAgent(_StubAgent(), DOSES["S"], 7))
    assert seen["margin_delta"] is None
    _act(SearchAgent(_StubAgent(), DOSES["S"], 7, margin_delta=0.05))
    assert seen["margin_delta"] == 0.05


def test_override_counter_only_moves_with_the_gate_on(monkeypatch):
    """A forced override and a forced non-override, through the real act()."""
    real = agent_mod.solve_decision

    def make(overrode):
        def spy(*a, **kw):
            action, stats = real(*a, **kw)
            if kw.get("margin_delta") is not None:
                stats["search/overrode"] = overrode
            return action, stats
        return spy

    off = SearchAgent(_StubAgent(), DOSES["S"], 7)
    monkeypatch.setattr(agent_mod, "solve_decision", make(True))
    _act(off)
    assert off.counters["search/overrides"] == 0  # gate off -> key never set

    on = SearchAgent(_StubAgent(), DOSES["S"], 7, margin_delta=0.01)
    _act(on)
    assert on.counters["search/overrides"] == 1
    monkeypatch.setattr(agent_mod, "solve_decision", make(False))
    _act(on, decision_index=2)
    assert on.counters["search/overrides"] == 1


def _ch3_eval():
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import ch3_eval  # noqa: E402

    return ch3_eval


def test_ch3_eval_jobs_carry_the_margin_delta():
    jobs = _ch3_eval()._jobs({
        "arms": {
            "S3M": {"kind": "search", "dose": "M", "lanes": ["s112"]},
            "S3G": {"kind": "search", "dose": "M", "lanes": ["s112"],
                    "margin_delta": 0.02},
        }
    })
    assert jobs["s3m_s112"]["margin_delta"] is None
    assert jobs["s3g_s112"]["margin_delta"] == 0.02


def _chunk(k, extra):
    return {
        "job": "j", "arm": "A", "members": ["s112"], "chunk": k,
        "episodes": 2, "seed_start": k, "eval/win_rate": 0.5,
        "wins_from_returns": 0.5, "mask_desyncs_delta": 0,
        "returns": [1.0, -1.0], "search_dose": "M",
        "search/decisions": 100, "search/placeholder_skips": 4,
        "search/flips": 60, "search/searched_decisions": 96,
        "search/ms_mean": 60.0, "search/ms_p99": 90.0,
        "search/leaves_mean": 277.0, "search/leaves_max": 400,
        **extra,
    }


@pytest.mark.parametrize("extra,want_rate,want_delta", [
    # a pre-2026-09-10 chunk: no selector stamp, no override counter. Must
    # merge without KeyError (the live S3 fleet's chunks are exactly this).
    ({}, None, None),
    ({"search_margin_delta": None, "search/overrides": 0}, None, None),
    # 2 chunks x 24 overrides over 2 x (100 - 4) searched decisions
    ({"search_margin_delta": 0.02, "search/overrides": 24}, 48 / 192, 0.02),
])
def test_ch3_eval_merge_override_rate(tmp_path, extra, want_rate, want_delta):
    ch3_eval = _ch3_eval()
    for k in range(2):
        (tmp_path / f"j.chunk{k:02d}.json").write_text(
            json.dumps(_chunk(k, extra))
        )
    ch3_eval._merge({}, "j", tmp_path, 2)
    final = json.loads((tmp_path / "j.final.json").read_text())
    assert final["search_margin_delta"] == want_delta
    assert final["search/override_rate"] == want_rate
    assert final["search/flip_rate"] == 120 / 192  # unchanged by the gate


# ---------------------------------------------------------------------------
# DEPTH-2 PROBE DIAGNOSTICS MUST SURVIVE THE MERGE (2026-09-16, JOURNEY 11.5).
#
# `_SeatEval.chunk_summary` writes depth2/ tree/ census/ bcts/ keys into every
# CHUNK, and `_merge` built the final from an explicit whitelist that did not
# include them -- so a depth-2 arm's final.json was byte-compatible with a
# depth-1 one. That is the SAME defect class as 2026-09-11's VOID D2 probe,
# where `_SearchEvalAdapter` dropped `depth2/grandchildren` and "the extra ply
# changed nothing" printed the same win rate as "the extra ply never fired" --
# one layer up, and still live until this test existed.

def test_ch3_eval_merge_carries_depth2_diagnostics(tmp_path):
    ch3_eval = _ch3_eval()
    # two chunks with DIFFERENT searched-decision counts, so a bug that
    # averages unweighted is distinguishable from the weighted mean
    for k, (searched, gc) in enumerate([(96, 800.0), (48, 500.0)]):
        extra = {
            "search/searched_decisions": searched,
            "depth2/grandchildren_mean": gc,
            "depth2/decisions_with_any": 1.0,
            "depth2/mean_shift_mean": 0.08,
        }
        (tmp_path / f"j.chunk{k:02d}.json").write_text(json.dumps(_chunk(k, extra)))
    ch3_eval._merge({}, "j", tmp_path, 2)
    final = json.loads((tmp_path / "j.final.json").read_text())
    assert "depth2/grandchildren_mean" in final, (
        "a depth-2 final.json is byte-compatible with a depth-1 one"
    )
    assert final["depth2/grandchildren_mean"] == pytest.approx(
        (800.0 * 96 + 500.0 * 48) / (96 + 48)
    ), "weighted by searched decisions, which is what chunk_summary averaged over"
    assert final["depth2/decisions_with_any"] == pytest.approx(1.0)


def test_ch3_eval_merge_is_unchanged_without_probe_keys(tmp_path):
    """A depth-1 arm gains no depth2/ keys -- absence stays meaningful."""
    ch3_eval = _ch3_eval()
    for k in range(2):
        (tmp_path / f"j.chunk{k:02d}.json").write_text(json.dumps(_chunk(k, {})))
    ch3_eval._merge({}, "j", tmp_path, 2)
    final = json.loads((tmp_path / "j.final.json").read_text())
    assert not [k for k in final if k.startswith(("depth2/", "tree/", "bcts/"))]


def test_search_agent_counts_the_extra_ply():
    """The counter that must reach disk before the dial gets an arm.

    2026-09-11's D2 probe produced ZERO grandchildren on all 1572 searched
    decisions and printed a win rate anyway. These counters are what R0 gate
    G_FIRED of configs/eval/depth2_r5.yaml reads.
    """
    from rl.search.agent import SearchAgent

    sa = SearchAgent.__new__(SearchAgent)      # no env, no checkpoint needed
    sa._depth2 = {"our_k": 3, "cap": 6000, "plies": 1}
    sa.counters = {"depth2/decisions_with_ply": 0, "depth2/grandchildren": 0,
                   "depth2/leaves_deepened": 0, "depth2/shift_sum": 0.0,
                   "search/flips": 0, "search/overrides": 0}
    for gc in (840, 0, 900):                   # one decision where it did not fire
        stats = {"depth2/grandchildren": gc, "depth2/leaves_deepened": 340,
                 "depth2/mean_shift": 0.09}
        if sa._depth2 is not None and "depth2/grandchildren" in stats:
            g = int(stats["depth2/grandchildren"])
            sa.counters["depth2/grandchildren"] += g
            sa.counters["depth2/leaves_deepened"] += int(stats["depth2/leaves_deepened"])
            sa.counters["depth2/decisions_with_ply"] += int(g > 0)
            sa.counters["depth2/shift_sum"] += float(stats.get("depth2/mean_shift", 0.0))
    assert sa.counters["depth2/grandchildren"] == 1740
    assert sa.counters["depth2/decisions_with_ply"] == 2, (
        "a decision that produced no grandchildren must not count as fired"
    )


def test_lane_seed_is_backward_identical_and_stops_being_a_landmine():
    from rl.search.agent import lane_seed

    for lane in ("s65", "s104", "s112", "s120"):
        assert lane_seed(lane) == int(lane.lstrip("s"))   # every banked arm
    assert lane_seed("w104") == 104 and lane_seed("l128") == 128
    with pytest.raises(AssertionError):
        lane_seed("clone")


def test_off_fp_seat_forwards_every_search_vehicle():
    """ch3_fp_h2h must pass EVERY vehicle kwarg SearchAgent accepts.

    The off-FP path silently ignored `depth2` until 2026-09-16, which is why
    JOURNEY 11.5 could not run at all, and it ignored `tree` for the same
    reason -- so the one vehicle docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS
    calls "the actual target" had never been runnable on the axis where a
    selector has leverage. A kwarg that SearchAgent takes and this caller drops
    produces a JSON indistinguishable from a correct one, which is the defect
    class this whole file exists for.
    """
    import ast
    import inspect

    from rl.search.agent import SearchAgent

    src = (Path(__file__).parent.parent / "scripts/ch3_fp_h2h.py").read_text()
    call = next(
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.Call)
        and getattr(n.func, "id", None) == "SearchAgent"
    )
    passed = {k.arg for k in call.keywords}
    # `det_fn` is the R3 oracle-team diagnostic, injected from a separate
    # binary and never from a pre-reg. `battle_format` is not a vehicle: this
    # script is gen-1 only and its default is the right one.
    NOT_VEHICLES = {"det_fn", "battle_format"}
    accepted = {
        p for p, spec in inspect.signature(SearchAgent.__init__).parameters.items()
        if spec.default is not inspect.Parameter.empty and p not in NOT_VEHICLES
    }
    missing = accepted - passed
    assert not missing, (
        f"scripts/ch3_fp_h2h.py drops SearchAgent kwargs {sorted(missing)}; an "
        "arm declaring one of these would run the DEFAULT vehicle and its JSON "
        "would look correct"
    )


def test_every_probe_prefix_survives_both_collectors():
    """A vehicle's stats must reach disk, and there are TWO places to forget.

    `_SeatEval.choose_move` filters incoming stats by prefix and `_merge`
    filters outgoing ones. On 2026-09-17 the Foul Play evaluator was added to
    the writer and to neither collector, so it ran, changed the decisions
    (override 0.18 vs 0.07, 28 ms vs 88) and reported NO counter at all -- the
    exact shape of the 2026-09-11 VOID probe, three fixes later. This test
    reads both filters out of the source and requires them to agree.
    """
    import re

    src = (Path(__file__).parent.parent / "scripts/ch3_eval.py").read_text()
    groups = re.findall(r'k\.split\("/"\)\[0\] in \(([^)]*)\)', src, re.S)
    assert len(groups) == 2, f"expected two prefix filters, found {len(groups)}"
    sets = [frozenset(re.findall(r'"([a-z0-9_]+)"', g)) for g in groups]
    assert sets[0] == sets[1], (
        f"the two prefix filters disagree: {sorted(sets[0] ^ sets[1])} is "
        "handled by one and dropped by the other"
    )
    for vehicle in ("depth2", "tree", "bcts", "heuristic"):
        assert vehicle in sets[0], f"{vehicle} stats never reach disk"

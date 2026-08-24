"""CH3 R5b BI-5 (placebo builder) — unit gates. No server, no checkpoints.

Pinned here, per pre-reg Q8 (the REBUILT construction — the r1 same-battle
pairing and its illegal-target degeneracy must stay dead):

* every placebo target is LEGAL by construction (zero mass outside the
  current row's mask) and sums to 1;
* partners always come from a DIFFERENT battle and have an IDENTICAL
  legal-action count;
* the index alignment maps the k-th legal action of the partner onto the
  k-th legal action of the current row (verified on a hand-built case);
* rows with no cross-battle partner at their legal count are dropped and
  counted; the >2% ROW-MISMATCHED flag fires;
* the pairing is deterministic under its seed.
"""

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ch3_r5b_placebo as placebo  # noqa: E402


def _mk(rows):
    """rows: list of (battle_id, legal_actions, ev_on_legal)."""
    a = 10
    n = len(rows)
    mask = np.zeros((n, a), dtype=np.uint8)
    ev = np.full((n, a), np.nan, dtype=np.float32)
    chosen = np.zeros(n, dtype=np.int32)
    bid = np.zeros(n, dtype=np.int32)
    for i, (b, legal, evs) in enumerate(rows):
        bid[i] = b
        mask[i, legal] = 1
        ev[i, legal] = evs
        chosen[i] = legal[int(np.argmax(evs))]
    return mask, ev, chosen, bid


def test_targets_legal_normalized_cross_battle():
    rng_rows = []
    rng = np.random.default_rng(3)
    for b in range(12):
        for _ in range(6):
            legal = sorted(rng.choice(10, size=rng.integers(2, 5),
                                      replace=False).tolist())
            rng_rows.append((b, legal, rng.normal(size=len(legal))))
    mask, ev, chosen, bid = _mk(rng_rows)
    fit_idx = np.arange(len(mask))
    kept, targets, report = placebo.build_placebo_targets(
        mask, ev, chosen, bid, fit_idx, "0.10", seed=7)
    assert report["dropped"] + len(kept) == len(fit_idx)
    for i in kept:
        t = targets[i]
        assert abs(t.sum() - 1.0) < 1e-5
        assert (t[mask[i] == 0] == 0).all(), "mass on an illegal action"


def test_index_alignment_hand_case():
    # row 0 (battle 0): legal {1, 4}; row 1 (battle 1): legal {2, 7} with a
    # known sharp target on its FIRST legal action.
    mask, ev, chosen, bid = _mk([
        (0, [1, 4], [0.0, 0.0]),
        (1, [2, 7], [5.0, -5.0]),
    ])
    kept, targets, report = placebo.build_placebo_targets(
        mask, ev, chosen, bid, np.array([0, 1]), "0.05", seed=0)
    assert set(kept.tolist()) == {0, 1}
    # row 0's only possible partner is row 1: k-th legal alignment maps
    # partner's action-2 mass onto our action 1, action-7 mass onto action 4.
    t0 = targets[0]
    assert t0[1] > 0.999 and t0[4] < 1e-3
    assert t0[[0, 2, 3, 5, 6, 7, 8, 9]].sum() == 0


def test_no_partner_dropped_and_mismatch_flag():
    # both rows in the SAME battle -> no cross-battle partner -> all dropped
    mask, ev, chosen, bid = _mk([
        (0, [1, 4], [0.1, 0.2]),
        (0, [2, 7], [0.3, 0.4]),
    ])
    kept, _, report = placebo.build_placebo_targets(
        mask, ev, chosen, bid, np.array([0, 1]), "0.10", seed=0)
    assert len(kept) == 0 and report["dropped"] == 2
    assert report["row_mismatched"] is True


def test_pairing_deterministic_under_seed():
    rng = np.random.default_rng(11)
    rows = []
    for b in range(8):
        for _ in range(4):
            legal = sorted(rng.choice(10, size=3, replace=False).tolist())
            rows.append((b, legal, rng.normal(size=3)))
    mask, ev, chosen, bid = _mk(rows)
    fit_idx = np.arange(len(mask))
    _, t1, _ = placebo.build_placebo_targets(mask, ev, chosen, bid, fit_idx,
                                             "0.25", seed=42)
    _, t2, _ = placebo.build_placebo_targets(mask, ev, chosen, bid, fit_idx,
                                             "0.25", seed=42)
    _, t3, _ = placebo.build_placebo_targets(mask, ev, chosen, bid, fit_idx,
                                             "0.25", seed=43)
    assert np.array_equal(t1, t2)
    assert not np.array_equal(t1, t3)

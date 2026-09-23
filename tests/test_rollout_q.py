"""R7 B1 -- the rollout-Q instrument's ARITHMETIC (`scripts/rollout_q.py`),
pinned on synthetic matrices so the reads cannot drift silently:

  * the split-sample regret is UNBIASED under a zero true gap (the winner's
    curse the plain max carries -- amendment 2 item 1 -- is gone) and
    recovers a planted gap;
  * the permuted-split null sits at ~0 on the same data;
  * the fixed-action form (regret_critic_depth1) is the greedy-relative value
    of that action, not a max;
  * opp_model_gap, the top-k read, the tie-aware Spearman, the win-rate scale
    and the turn buckets are what the docstring says;
  * a rows file of another instrument version is REFUSED, never resumed.

No engine, no checkpoints: the functions are pure numpy.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_q as rq  # noqa: E402


def _outcomes(rng, true_q, s):
    """(n_rows, n_cols, s) Bernoulli +-1 outcomes around the true cell means."""
    n_rows, n_cols = true_q.shape
    p_win = (true_q + 1) / 2
    u = rng.random((n_rows, n_cols, s))
    return np.where(u < p_win[:, :, None], 1.0, -1.0)


def test_split_sample_regret_is_unbiased_at_zero_gap_and_recovers_a_planted_gap():
    rng = np.random.default_rng(0)
    n_rows, n_cols, s = 7, 5, 256
    q_col = np.full(n_cols, 1.0 / n_cols)
    half = np.zeros(s, dtype=bool); half[: s // 2] = True
    # Zero true gap everywhere: every row is worth exactly 0.
    zero = np.zeros((n_rows, n_cols))
    naive, split, null = [], [], []
    for _ in range(300):
        o = _outcomes(rng, zero, s)
        qbar = rq.cell_means(o) @ q_col
        naive.append(qbar.max() - qbar[0])                          # the max, in-sample: biased up
        split.append(rq.regret_split(o, q_col, 0, half))
        null.append(rq.permuted_null(o, q_col, 0, 4, rng))
    assert np.mean(naive) > 0.03, np.mean(naive)                    # the winner's curse is real
    assert abs(np.mean(split)) < 0.01, np.mean(split)               # and the split removes it
    assert abs(np.mean(null)) < 0.01, np.mean(null)
    # A planted gap: row 3 is worth +0.30 outcome over the greedy row 0.
    planted = np.zeros((n_rows, n_cols)); planted[3] = 0.30
    got, null_gap, resplit = [], [], []
    for _ in range(300):
        o = _outcomes(rng, planted, s)
        got.append(rq.regret_split(o, q_col, 0, half))
        null_gap.append(rq.permuted_null(o, q_col, 0, 4, rng, half=half))
        resplit.append(rq.resplit_replicate(o, q_col, 0, 4, rng))
    assert abs(np.mean(got) - 0.30) < 0.02, np.mean(got)
    # THE DISCRIMINATING CASE (rollout_q/2): with a TRUE gap the zero-gap null
    # stays at 0 while the estimate reads the gap -- and the re-split
    # replicate FOLLOWS the estimate (it is a second draw of it, not a null;
    # v1 reported this replicate as the null and the two read identical on
    # G0's rows).
    assert abs(np.mean(null_gap)) < 0.02, np.mean(null_gap)
    assert abs(np.mean(resplit) - 0.30) < 0.02, np.mean(resplit)


def test_fixed_action_regret_is_that_actions_value_relative_to_greedy():
    rng = np.random.default_rng(1)
    q = np.array([[0.2, 0.0], [-0.4, -0.4], [0.5, 0.1]])
    o = _outcomes(rng, q, 512)
    q_col = np.array([0.5, 0.5])
    half = np.zeros(512, dtype=bool); half[:256] = True
    r = rq.regret_split(o, q_col, 0, half, a_eval=2)
    assert abs(r - 0.20) < 0.06, r          # (0.5+0.1)/2 - (0.2+0.0)/2 = 0.20
    r_self = rq.regret_split(o, q_col, 0, half, a_eval=0)
    assert r_self == 0.0


def test_opp_model_gap_and_topk_read():
    q = np.array([[0.4, -0.6, 0.2],
                  [0.1, 0.1, 0.1]])
    q_col = np.array([0.6, 0.2, 0.2])
    # E_b: row0 = 0.24-0.12+0.04 = 0.16, row1 = 0.1 -> max 0.16; min_b: row0 = -0.6, row1 = 0.1 -> max 0.1
    assert abs(rq.opp_model_gap(q, q_col) - 0.06) < 1e-12
    pi = np.array([0.5, 0.1, 0.4])       # top-2 = cols {0, 2}
    assert rq.best_reply_outside_topk(q, 0, pi, 2) is True     # best reply to row 0 is col 1
    assert rq.best_reply_outside_topk(q, 0, pi, 3) is False
    assert rq.best_reply_outside_topk(q, 1, pi, 1) is False    # all equal -> col 0, which is top-1


def test_spearman_handles_ties_and_degenerate_input():
    assert abs(rq.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-12
    assert abs(rq.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-12
    assert np.isnan(rq.spearman([1, 1, 1, 1], [1, 2, 3, 4]))
    assert np.isnan(rq.spearman([1, 2, 3], [1, 2, 3]))
    # ties get the average rank: [1,1,2] vs [1,2,3] is less than perfect but positive
    r = rq.spearman([1, 1, 2, 3], [1, 2, 3, 4])
    assert 0.8 < r < 1.0


def test_scale_and_buckets_and_mean_se():
    assert rq.win_rate(0.02) == 0.01
    assert [rq.bucket_of(t) for t in (2, 8, 9, 15, 16, 22, 23, 400)] == [0, 0, 1, 1, 2, 2, 3, 3]
    m, se = rq.mean_se([1.0, 3.0])
    assert m == 2.0 and abs(se - 1.0) < 1e-12
    m, se = rq.mean_se([float("nan"), 2.0])
    assert m == 2.0 and np.isnan(se)


def test_cell_means_respect_the_half_mask():
    o = np.zeros((1, 1, 4)); o[0, 0] = [1, 1, -1, -1]
    half = np.array([True, True, False, False])
    assert rq.cell_means(o, half)[0, 0] == 1.0 and rq.cell_means(o, ~half)[0, 0] == -1.0
    assert rq.cell_means(o)[0, 0] == 0.0


def test_a_rows_file_of_another_version_is_refused(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps({"instrument_version": "rollout_q/0", "pid": 0}) + "\n")
    with pytest.raises(SystemExit, match="REFUSED"):
        rq.load_rows(p)
    p.write_text(json.dumps({"instrument_version": rq.INSTRUMENT_VERSION, "pid": 0}) + "\n")
    assert [r["pid"] for r in rq.load_rows(p)] == [0]
    assert rq.load_rows(tmp_path / "absent.jsonl") == []

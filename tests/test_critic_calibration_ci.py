"""scripts/critic_calibration.py, the R6 additions: the position-clustered bootstrap on
the by-turn r^2 and the unpaired --compare of two calibration JSONs (trio A's
mechanism co-primary read with error bars)."""
import math
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from critic_calibration import compare, r2_bootstrap  # noqa: E402


def test_r2_bootstrap_brackets_the_truth_and_tightens_with_n():
    rng = np.random.default_rng(0)
    m = rng.normal(size=400)
    v = 0.6 * m + rng.normal(size=400) * 0.8          # true r^2 ~ 0.36
    r2, se, lo, hi = r2_bootstrap(v, m, n_boot=400, seed=1)
    assert lo < r2 < hi and 0.25 < r2 < 0.5 and 0.0 < se < 0.1
    r2s, se_s, lo_s, hi_s = r2_bootstrap(v[:40], m[:40], n_boot=400, seed=1)
    assert se_s > se, "fewer positions must widen the interval"


def test_r2_bootstrap_handles_a_degenerate_resample_without_nan():
    v = np.array([0.0, 0.0, 0.0, 1.0]); m = np.array([0.0, 0.1, 0.2, 0.3])
    r2, se, lo, hi = r2_bootstrap(v, m, n_boot=200, seed=2)
    assert math.isfinite(r2) and math.isfinite(lo) and math.isfinite(hi)


def test_compare_reports_unpaired_delta_and_absent_buckets():
    a = {"label": "A", "by_turn": [{"turns": "2-8", "positions": 100, "r2": 0.30, "r2_se": 0.05},
                                   {"turns": "9-15", "positions": 90, "r2": 0.40, "r2_se": 0.06}]}
    b = {"label": "B", "by_turn": [{"turns": "2-8", "positions": 110, "r2": 0.45, "r2_se": 0.05},
                                   {"turns": "23-+", "positions": 80, "r2": 0.70, "r2_se": 0.04}]}
    rows = {r["turns"]: r for r in compare(a, b)}
    assert set(rows) == {"2-8", "9-15", "23-+"}
    r = rows["2-8"]
    assert math.isclose(r["delta"], 0.15) and math.isclose(r["se"], math.hypot(0.05, 0.05))
    assert math.isclose(r["z"], 0.15 / math.hypot(0.05, 0.05))
    assert rows["9-15"]["r2_b"] is None and "delta" not in rows["9-15"]
    assert rows["23-+"]["r2_a"] is None and rows["23-+"]["n_a"] == 0

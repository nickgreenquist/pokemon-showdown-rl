"""scripts/action_gap_readout.py: the winner's-curse companions to the naive action-gap
ceiling. Pins the ceiling arithmetic, the Gaussian shortfall against Monte Carlo, the
paired per-row se, and the two limiting worlds -- pure noise (the naive ceiling is
positive, the deconvolved one ~0) and noise-free (deconvolved == naive)."""
import math
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from action_gap_readout import ceiling, gauss_shortfall, per_row_se, readout  # noqa: E402


def _rows(gaps, var=0.5, n=48, corr=0.0):
    return [{"ep": i, "turn": 2 + (i % 30), "gap": float(g), "top1_is_played": 1,
             "var1": var, "var2": var, "n1": n, "n2": n, "corr_12": corr}
            for i, g in enumerate(gaps)]


def test_ceiling_is_half_the_expected_shortfall():
    # P(worse) 0.5, E[-gap | worse] 0.3 -> 0.15 outcome -> 0.075 win rate
    assert math.isclose(ceiling(np.array([0.5, -0.2, 0.0, -0.4])), 0.075)
    assert ceiling(np.array([0.1, 0.2])) == 0.0


def test_gauss_shortfall_matches_monte_carlo():
    rng = np.random.default_rng(0)
    for mu, tau in [(0.04, 0.16), (-0.1, 0.05), (0.3, 0.2)]:
        mc = np.maximum(0.0, -rng.normal(mu, tau, 2_000_000)).mean()
        assert math.isclose(gauss_shortfall(mu, tau), mc, abs_tol=5e-4), (mu, tau)
    assert gauss_shortfall(-0.2, 0.0) == 0.2 and gauss_shortfall(0.2, 0.0) == 0.0


def test_paired_se_subtracts_the_shared_world_component():
    ind, pair = per_row_se(_rows([0.0], var=0.5, n=48, corr=0.3))
    assert math.isclose(ind[0], math.sqrt(2 * 0.5 / 48))
    assert math.isclose(pair[0], math.sqrt((2 * 0.5 - 2 * 0.3 * 0.5) / 48))
    rows = _rows([0.0], corr=None)
    assert per_row_se(rows)[1][0] == per_row_se(rows)[0][0]


def test_pure_noise_prints_a_ceiling_that_deconvolves_away_and_noise_free_does_not():
    rng = np.random.default_rng(1)
    n, var, k = 400, 0.5, 48
    noise = rng.normal(0.0, math.sqrt(2 * var / k), n)
    o = readout(_rows(noise, var=var, n=k), boot=300)
    assert o["naive_ceiling"] > 0.02, "the curse: noise alone must print a ceiling"
    assert abs(o["noise_only_ceiling_paired"] - o["naive_ceiling"]) < 0.006
    d = o["deconvolution_paired"]
    assert abs(d["tau2"]) < 0.004 and d["deconvolved_ceiling"] < 0.3 * o["naive_ceiling"]
    real = rng.normal(0.05, 0.3, n)
    o2 = readout(_rows(real, var=1e-8, n=k), boot=300)
    assert o2["noise_only_ceiling_paired"] < 1e-3
    assert abs(o2["deconvolution_paired"]["deconvolved_ceiling"] - o2["naive_ceiling"]) < 0.01
    assert sum(b["n"] for b in o2["by_turn"]) == n

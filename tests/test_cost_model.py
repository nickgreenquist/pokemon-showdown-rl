"""The search's work-unit cost model (rl/search/cost_model.py) and the inference Linear it prices
(rl/common/fast_linear.py): the meter's segment arithmetic is exact under a piecewise-linear cost
table, a fit recovers known costs from synthetic jobs, the model round-trips and refuses a foreign
key, and FastLinear is nn.Linear to float rounding (exactly nn.Linear under autograd), with its
cached transpose following every weight change."""
from __future__ import annotations

import json

import numpy as np
import pytest

from rl.search import cost_model as cm


def test_segments_cover_every_row_count():
    assert cm.segment(1) == 0 and cm.segment(2) == 1 and cm.segment(3) == 2
    assert cm.segment(1024) == cm.N_SEG - 1 and cm.segment(5000) == cm.N_SEG - 1
    for n in range(1, 1200):
        s = cm.segment(n)
        assert cm.GRID[s] <= n and (n < cm.GRID[s + 1] or s == cm.N_SEG - 1), n
    with pytest.raises(ValueError):
        cm.segment(0)


def test_meter_is_exact_under_a_piecewise_linear_table():
    rng = np.random.default_rng(0)
    table = np.sort(rng.uniform(0.5, 60.0, len(cm.GRID))).tolist()     # any table; t need not be affine
    table[1] = table[0] + 5.0                                            # a jump like Accelerate's (1 -> 2 rows)
    m = cm.CallMeter()
    exact = {"v": 0.0, "p": 0.0}
    for _ in range(3000):
        net = "v" if rng.random() < 0.6 else "p"
        n = int(rng.integers(1, 1500))
        k = int(rng.integers(1, n + 1))
        m.add(net, k, n)
        exact[net] += k / n * cm.interp(table, n)
    u = m.units()
    for net in cm.NETS:
        assert cm.nn_table_ms(table, u["share"][net], u["rows"][net]) == pytest.approx(exact[net], rel=1e-12)
    with pytest.raises(ValueError):
        m.add("v", 3, 2)


def _synthetic_jobs(rng, model_truth: cm.CostModel, n_jobs: int, noise: float) -> list[dict]:
    jobs = []
    for i in range(n_jobs):
        meter = cm.CallMeter()
        for _ in range(int(rng.integers(5, 80))):
            n = int(rng.integers(1, 300))
            meter.add("v" if rng.random() < 0.5 else "p", int(rng.integers(1, n + 1)), n)
        u = meter.units()
        count = {"edges_tree": float(rng.integers(10, 900)), "nodes_tree": float(rng.integers(10, 2000)),
                 "sims_tree": float(rng.integers(64, 2000)), "depth_tree": float(rng.integers(64, 8000)),
                 "grid_rows": float(rng.integers(8, 400)), "worlds": float(rng.integers(1, 9)), "decisions": 1.0}
        units = {"share": u["share"], "rows": u["rows"], "count": count}
        p = model_truth.predict(units)
        f = lambda x: x * (1 + noise * rng.standard_normal())     # noqa: E731
        jobs.append({"config": f"c{i % 3}", "units": units, "ms_v": f(p["nn_v"]), "ms_p": f(p["nn_p"]),
                     "ms_engine": f(p["engine"]), "ms_total": f(p["total"])})
    return jobs


def test_fit_recovers_known_costs_and_validates():
    rng = np.random.default_rng(1)
    grid = np.array(cm.GRID, float)
    truth = cm.CostModel(key={}, t_ms={"v": (0.9 + 0.05 * grid).tolist(), "p": (0.8 + 0.03 * grid).tolist()},
                         kappa={"v": 1.15, "p": 1.05},
                         engine={"edges_tree": 0.04, "nodes_tree": 0.002, "grid_rows": 0.003, "worlds": 0.3},
                         python={"sims_tree": 0.1, "depth_tree": 0.01, "nodes_tree": 0.03, "grid_rows": 0.004,
                                 "worlds": 0.2, "decisions": 0.4})
    fit_jobs = _synthetic_jobs(rng, truth, 200, noise=0.02)
    model = cm.fit(truth.t_ms, fit_jobs, key={"k": 1}, load={})
    assert model.kappa["v"] == pytest.approx(1.15, rel=0.02) and model.kappa["p"] == pytest.approx(1.05, rel=0.02)
    for u in ("edges_tree", "worlds"):    # the well-identified terms (the intercepts are weak: every job is 1 decision)
        assert model.engine[u] == pytest.approx(truth.engine[u], rel=0.25), u
    v = cm.validate(model, _synthetic_jobs(rng, truth, 100, noise=0.02))
    assert v["accepted"] and v["median_abs_err"] < 0.03, v
    wrong = cm.CostModel(**{**json.loads(model.to_json()), "kappa": {"v": 2.0, "p": 2.0}})
    assert not cm.validate(wrong, _synthetic_jobs(rng, truth, 50, noise=0.0))["accepted"]


def test_round_trip_and_key_refusal():
    m = cm.CostModel(key={"cpu": "x", "linear": "fast"}, t_ms={"v": [1.0] * len(cm.GRID), "p": [1.0] * len(cm.GRID)},
                     kappa={"v": 1.0, "p": 1.0}, engine=dict.fromkeys(cm.ENGINE_UNITS, 0.0),
                     python=dict.fromkeys(cm.PYTHON_UNITS, 0.0), load={"probe_ms_median": 0.5})
    back = cm.CostModel.from_json(m.to_json())
    assert back == m
    m.check_key({"cpu": "x", "linear": "fast"})
    with pytest.raises(ValueError, match="key mismatch"):
        m.check_key({"cpu": "x", "linear": "stock"})
    with pytest.raises(ValueError, match="version"):
        cm.CostModel.from_json(json.dumps({**json.loads(m.to_json()), "version": "search_cost_model/0"}))


def test_units_refuse_a_result_without_the_meter_or_on_another_grid():
    with pytest.raises(KeyError):
        cm.units_of({"counters": {}})
    bad = {"cost_units": {"grid": [1, 2], "share": {}, "rows": {}}, "counters": {}}
    with pytest.raises(ValueError, match="grid"):
        cm.units_of(bad)


def test_fast_linear_matches_and_follows_the_weights():
    torch = pytest.importorskip("torch")
    from rl.common import fast_linear

    torch.manual_seed(0)
    net = torch.nn.Sequential(torch.nn.Linear(64, 256), torch.nn.ReLU(), torch.nn.Linear(256, 256),
                              torch.nn.ReLU(), torch.nn.Linear(256, 1))
    ref = [torch.nn.Linear(1, 1)]                          # a plain Linear stays plain elsewhere
    keys = sorted(net.state_dict())
    x = {n: torch.randn(n, 64) for n in (1, 3, 8, 32, 128)}
    with torch.no_grad():
        want = {n: net(v) for n, v in x.items()}
    assert fast_linear.enable(net) == 3 and type(ref[0]) is torch.nn.Linear
    assert sorted(net.state_dict()) == keys
    with torch.no_grad():
        for n, v in x.items():
            assert torch.allclose(net(v), want[n], rtol=0, atol=1e-5), n
    # under autograd it is nn.Linear exactly, and gradients flow
    y = net(x[8]).sum()
    y.backward()
    assert net[0].weight.grad is not None
    # the cached transpose follows an in-place step and a load_state_dict
    with torch.no_grad():
        net[0].weight.add_(0.5)
        stepped = net(x[8])
        fast_linear.disable(net)
        assert torch.allclose(net(x[8]), stepped, rtol=0, atol=1e-5)
        fast_linear.enable(net)
        other = {k: torch.randn_like(v) for k, v in net.state_dict().items()}
        net.load_state_dict(other)
        got = net(x[8])
        fast_linear.disable(net)
        assert torch.allclose(net(x[8]), got, rtol=0, atol=1e-5)
    assert fast_linear.disable(net) == 0

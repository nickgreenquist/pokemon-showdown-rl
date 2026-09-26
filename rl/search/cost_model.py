"""The search's WORK-UNIT cost model (2026-09-26; the maintainer: no more quiet-box rules).

A search's WORK is deterministic. The tree's counters are functions of its dials, the position and
its key, never of the load, so every budget and every cost comparison is stated in work, and a
one-time CALIBRATION converts work into milliseconds on a named setup.

THE UNITS (per decision; `native_tree.search` returns them as `res["cost_units"]`):
- Every network call is metered by its ROW COUNT n. A decision holding k of a call's n rows is
  charged the share k/n (the tree's own `_charge` rule). Calls are binned on the fixed GRID's
  segments [g_i, g_i+1]; per segment the meter keeps the decision's share sum S and row sum R.
  Under a cost curve t(n) that is linear on each segment (the calibration's piecewise-linear
  table), the segment's calls cost sum (k/n) t(n) = S * t(R / S) EXACTLY, for any batch-size mix.
  That matters: t(n) is far from affine. Accelerate's sgemm on nn.Linear's transposed weight
  costs ~620 us for a 1024x1024 layer at 2-12 rows and ~20 us at 1 row (2026-09-26), so rows
  and calls alone cannot predict a search whose calls change size.
- The engine and the Python tree, with the ROOT GRID's batched work kept apart from the tree's
  descents (one expand and one critic batch per world against one engine call and one Python
  walk per descent: pooled, they mis-priced a 64-simulation search 2x, 2026-09-26): tree sims,
  their summed depth, tree nodes and edges, grid rows, worlds, and one per decision.
- ROUNDS: the Python loop pays per round, not per simulation (~160 us a simulation at one descent
  a round, ~85 us at 32 descents a round, 2026-09-26), and a decision's share of the round's
  calls is already metered, so `call_share` (its summed shares over both nets) is the unit.

THE MODEL: ms = sum over nets of sum_seg S * t_net(R / S) + e . engine + p . python
- t_net: the network cost table, FITTED IN SITU: the interleaved micro-benchmark's table
  (`t_micro`, the SHAPE) times one scale per TABLE_BANDS band, fitted on the fit searches'
  measured network ms with the loop's own number as the prior (`t_scale`). A micro-benchmark
  alone misprices sizes whose in-search cost differs: stock nn.Linear's 2-row prior call costs
  ~2/3 in a search of what it costs in a loop (2026-09-26).
- e, p: non-negative least squares on the per-job medians of the measured engine ms and of the
  remainder.

LOAD is TAGGED, never gated. The micro-benchmark's cells and the full searches' jobs are
interleaved in shuffled rounds, so a load burst hits every cell alike; medians are kept; a fixed
probe is timed every round and its median is the calibration's LOAD LEVEL. The model is accepted
only if it predicts HELD-OUT full searches within 10% median absolute error.

THE KEY: the machine, torch, numpy, threads, each net's architecture signature, the Linear kernel
form, and the engine build. Predicting under another key refuses.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

import numpy as np

COST_MODEL_VERSION = "search_cost_model/2"
GRID: tuple[int, ...] = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024)
NETS: tuple[str, ...] = ("v", "p")     # the value net (leaf evaluator) and the prior net (policy)
N_SEG = len(GRID) - 1
ENGINE_UNITS: tuple[str, ...] = ("edges_tree", "nodes_tree", "grid_rows", "worlds")
PYTHON_UNITS: tuple[str, ...] = ("call_share", "sims_tree", "depth_tree", "nodes_tree", "grid_rows", "worlds",
                                 "decisions")
TABLE_BANDS: tuple[tuple[int, int], ...] = ((1, 1), (2, 3), (4, 12), (16, 48), (64, 1024))   # the in-situ scales
TABLE_PRIOR_WEIGHT = 0.1        # the micro-benchmark's pull on each band's scale, in relative units
ACCEPT_MEDIAN_ABS_ERR = 0.10


def segment(n: int) -> int:
    """The GRID segment [GRID[i], GRID[i+1]] a call of n rows is metered in (the last one extends)."""
    if n < 1:
        raise ValueError(f"a network call has at least one row, got {n}")
    return min(max(bisect.bisect_right(GRID, int(n)) - 1, 0), N_SEG - 1)


class CallMeter:
    """One decision's share of every network call, binned by the call's row count."""

    __slots__ = ("share", "rows")

    def __init__(self) -> None:
        self.share = {net: [0.0] * N_SEG for net in NETS}
        self.rows = {net: [0] * N_SEG for net in NETS}

    def add(self, net: str, k: int, n: int) -> None:
        """The decision held k of the call's n rows."""
        if not 0 < k <= n:
            raise ValueError(f"a decision holds 1..n of a call's rows, got k={k} of n={n}")
        s = segment(n)
        self.share[net][s] += k / n
        self.rows[net][s] += int(k)

    def units(self) -> dict[str, Any]:
        return {"grid": list(GRID), "share": {k: list(v) for k, v in self.share.items()},
                "rows": {k: list(v) for k, v in self.rows.items()}}


def units_of(res: dict[str, Any]) -> dict[str, Any]:
    """A search result's work units: the call meter plus the engine / Python counts."""
    cu = res.get("cost_units")
    if cu is None:
        raise KeyError("the result carries no cost_units (a native_tree result from before the cost model)")
    if list(cu["grid"]) != list(GRID):
        raise ValueError(f"cost_units were metered on grid {cu['grid']}, this model's is {list(GRID)}")
    c = res["counters"]
    return {"share": cu["share"], "rows": cu["rows"],
            "count": {"sims_tree": float(c["tree/sims"] - c["tree/sims_grid"]),
                      "depth_tree": float(c["tree/depth_sum"] - c["tree/depth_grid"]),
                      "nodes_tree": float(c["tree/nodes"] - c["tree/nodes_grid"]),
                      "edges_tree": float(c["tree/edges"] - c["tree/edges_grid"]),
                      "grid_rows": float(c["tree/evals_grid"]), "worlds": float(c["search/worlds"]),
                      "call_share": float(sum(cu["share"]["v"]) + sum(cu["share"]["p"])),
                      "decisions": 1.0}}


def interp(table: Sequence[float], x: float, s: int | None = None) -> float:
    """t(x) on the GRID, piecewise linear on segment s (default: x's own; the last extrapolates)."""
    if s is None:
        s = segment(max(1, int(math.floor(x))))
    x0, x1 = GRID[s], GRID[s + 1]
    return float(table[s] + (table[s + 1] - table[s]) * (x - x0) / (x1 - x0))


def table_basis(share: Sequence[float], rows: Sequence[float]) -> np.ndarray:
    """W with nn_table_ms(table, share, rows) == W @ table: each segment's share split between its two
    grid points by where R / S sits between them."""
    w = np.zeros(len(GRID))
    for s in range(N_SEG):
        if share[s] > 0:
            x = rows[s] / share[s]
            lam = (x - GRID[s]) / (GRID[s + 1] - GRID[s])
            w[s] += share[s] * (1.0 - lam)
            w[s + 1] += share[s] * lam
    return w


def nn_table_ms(table: Sequence[float], share: Sequence[float], rows: Sequence[float]) -> float:
    """sum over segments of S * t(R / S): exact under a piecewise-linear t (R / S is the calls'
    share-weighted harmonic mean size, which stays inside its segment)."""
    total = 0.0
    for s in range(N_SEG):
        if share[s] > 0:
            total += share[s] * interp(table, rows[s] / share[s], s)
    return total


@dataclass
class CostModel:
    key: dict[str, Any]
    t_ms: dict[str, list[float]]                  # net -> median ms per call at each GRID point
    kappa: dict[str, float]                       # net -> the in-situ factor
    engine: dict[str, float]                      # ENGINE_UNITS -> ms per unit
    python: dict[str, float]                      # PYTHON_UNITS -> ms per unit
    t_micro: dict[str, list[float]] = field(default_factory=dict)   # the micro-benchmark's table (the prior)
    t_scale: dict[str, list[float]] = field(default_factory=dict)   # the in-situ scale per TABLE_BANDS band
    load: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    version: str = COST_MODEL_VERSION

    def predict(self, units: dict[str, Any]) -> dict[str, float]:
        out = {f"nn_{net}": self.kappa[net] * nn_table_ms(self.t_ms[net], units["share"][net], units["rows"][net])
               for net in NETS}
        out["engine"] = sum(self.engine[u] * units["count"][u] for u in ENGINE_UNITS)
        out["python"] = sum(self.python[u] * units["count"][u] for u in PYTHON_UNITS)
        out["total"] = sum(out.values())
        return out

    def check_key(self, key: dict[str, Any]) -> None:
        diff = {k: (self.key.get(k), key.get(k)) for k in set(self.key) | set(key) if self.key.get(k) != key.get(k)}
        if diff:
            raise ValueError(f"cost model key mismatch (calibrated vs now): {diff}; re-calibrate on this setup")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "CostModel":
        d = json.loads(text)
        if d.get("version") != COST_MODEL_VERSION:
            raise ValueError(f"cost model version {d.get('version')} != {COST_MODEL_VERSION}")
        return cls(**d)


# ---- fitting ------------------------------------------------------------------------------------

def nnls(A: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Non-negative least squares, EXACT for the few unknowns here: the best unconstrained fit over
    every subset of the columns whose solution is non-negative (the optimum is one of them). No
    scipy, which the engine envs do not carry."""
    import itertools

    A, b = np.asarray(A, float), np.asarray(b, float)
    m = A.shape[1]
    if m > 12:
        raise ValueError(f"nnls enumerates column subsets; {m} columns is too many")
    best, best_r = np.zeros(m), float(b @ b)
    for k in range(1, m + 1):
        for cols in itertools.combinations(range(m), k):
            x, *_ = np.linalg.lstsq(A[:, cols], b, rcond=None)
            if np.all(x >= 0):
                r = b - A[:, cols] @ x
                if float(r @ r) < best_r:
                    best_r, best = float(r @ r), np.zeros(m)
                    best[list(cols)] = x
    return best


def band_of(i: int) -> int:
    """The TABLE_BANDS band of grid point i."""
    n = GRID[i]
    return next(b for b, (lo, hi) in enumerate(TABLE_BANDS) if lo <= n <= hi)


def fit_table(t_micro: Sequence[float], jobs: Sequence[dict], net: str,
              prior_weight: float = TABLE_PRIOR_WEIGHT) -> tuple[list[float], list[float]]:
    """The in-situ table: the micro-benchmark's SHAPE times one scale per TABLE_BANDS band, fitted by
    least squares in RELATIVE error on every fit job's measured ms for this net, with
    prior_weight * (scale - 1)^2 per band (a band no search uses keeps the loop's number). Free
    per-point values were tried first and were not identified at small sizes (2026-09-26)."""
    tm = np.asarray(t_micro, float)
    nb = len(TABLE_BANDS)
    rows, rhs = [], []
    for j in jobs:
        m = j["ms_" + net]
        if m <= 0:
            continue
        w = table_basis(j["units"]["share"][net], j["units"]["rows"][net]) * tm
        f = np.zeros(nb)
        for i in range(len(GRID)):
            f[band_of(i)] += w[i]
        rows.append(f / m)
        rhs.append(1.0)
    k = math.sqrt(prior_weight)
    for b in range(nb):
        e = np.zeros(nb)
        e[b] = k
        rows.append(e)
        rhs.append(k)
    c, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
    c = np.clip(c, 0.2, 5.0)
    return [float(tm[i] * c[band_of(i)]) for i in range(len(GRID))], c.tolist()


def fit_kappa(t_ms: dict[str, list[float]], jobs: Sequence[dict]) -> dict[str, float]:
    """Per net: the median over jobs of measured network ms / the table's prediction."""
    out = {}
    for net in NETS:
        r = [j["ms_" + net] / p for j in jobs
             if (p := nn_table_ms(t_ms[net], j["units"]["share"][net], j["units"]["rows"][net])) > 0]
        out[net] = float(np.median(r)) if r else 1.0
    return out


def fit_linear(jobs: Sequence[dict], names: Sequence[str], target: Callable[[dict], float]) -> dict[str, float]:
    A = np.array([[j["units"]["count"][u] for u in names] for j in jobs], float)
    b = np.array([target(j) for j in jobs], float)
    return dict(zip(names, nnls(A, b).tolist()))


def fit(t_ms: dict[str, list[float]], fit_jobs: Sequence[dict], key: dict, load: dict) -> CostModel:
    """`fit_jobs`: one per (config, root), each with its medians `ms_total`, `ms_v`, `ms_p`, `ms_engine`
    and its (deterministic) `units`."""
    fitted = {net: fit_table(t_ms[net], fit_jobs, net) for net in NETS}
    t_fit = {net: fitted[net][0] for net in NETS}
    kappa = fit_kappa(t_fit, fit_jobs)        # ~1 by construction: reported as the fit's own residual level
    engine = fit_linear(fit_jobs, ENGINE_UNITS, lambda j: j["ms_engine"])
    python = fit_linear(fit_jobs, PYTHON_UNITS, lambda j: max(0.0, j["ms_total"] - j["ms_v"] - j["ms_p"] - j["ms_engine"]))
    return CostModel(key=key, t_ms=t_fit, kappa=dict.fromkeys(NETS, 1.0), engine=engine, python=python, load=load,
                     t_micro={k: list(map(float, v)) for k, v in t_ms.items()},
                     t_scale={net: fitted[net][1] for net in NETS},
                     validation={"kappa_after_table_fit": kappa})


def validate(model: CostModel, jobs: Sequence[dict]) -> dict[str, Any]:
    """Relative error of the predicted total against each held-out job's measured median."""
    rel = []
    by_cfg: dict[str, list[float]] = {}
    for j in jobs:
        e = (model.predict(j["units"])["total"] - j["ms_total"]) / j["ms_total"]
        rel.append(e)
        by_cfg.setdefault(j["config"], []).append(e)
    a = np.abs(np.array(rel))
    return {"jobs": len(rel), "median_abs_err": float(np.median(a)) if rel else float("nan"),
            "p90_abs_err": float(np.percentile(a, 90)) if rel else float("nan"),
            "median_signed_err": float(np.median(rel)) if rel else float("nan"),
            "by_config": {k: {"median_signed_err": float(np.median(v)), "median_abs_err": float(np.median(np.abs(v))),
                              "n": len(v)} for k, v in sorted(by_cfg.items())},
            "accept_line": ACCEPT_MEDIAN_ABS_ERR,
            "accepted": bool(rel) and float(np.median(a)) <= ACCEPT_MEDIAN_ABS_ERR}


# ---- the key ------------------------------------------------------------------------------------

def arch_signature(module: Any) -> str:
    """The architecture, not the weights: every parameter's name, shape and dtype."""
    items = sorted((n, tuple(p.shape), str(p.dtype)) for n, p in module.state_dict().items())
    return hashlib.sha256(repr(items).encode()).hexdigest()[:16]


def machine_key(*, torch_threads: int, nets: dict[str, str], linear: str, engine_build: str) -> dict[str, Any]:
    import torch

    def sysctl(name: str) -> str:
        try:
            return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    return {"cpu": sysctl("machdep.cpu.brand_string") or platform.processor(),
            "p_cores": sysctl("hw.perflevel0.physicalcpu"), "e_cores": sysctl("hw.perflevel1.physicalcpu"),
            "os": platform.platform(), "python": platform.python_version(), "torch": torch.__version__,
            "numpy": np.__version__, "torch_threads": int(torch_threads), "nets": dict(sorted(nets.items())),
            "linear": linear, "engine_build": engine_build}


# ---- interleaved timing -------------------------------------------------------------------------

def time_sweeps(cells: Sequence[tuple[str, Callable[[], Any]]], rounds: int,
                probe: Callable[[], Any] | None = None, warmup: int = 3) -> dict[str, Any]:
    """The network cells in SIZE ORDER, ascending on even rounds and descending on odd ones, so every
    call follows a call of a neighbouring size, as in a search. A shuffled order put 1-row calls
    after 1024-row ones, whose activations evict the weights, and read them ~30% slow (2026-09-26).
    The probe runs once per round."""
    import time

    for _name, fn in cells:
        for _ in range(warmup):
            fn()
    out: dict[str, list[float]] = {name: [] for name, _fn in cells}
    probe_ms: list[float] = []
    for r in range(rounds):
        for name, fn in (cells if r % 2 == 0 else list(reversed(cells))):
            t0 = time.perf_counter_ns()
            fn()
            out[name].append((time.perf_counter_ns() - t0) / 1e6)
        if probe is not None:
            t0 = time.perf_counter_ns()
            probe()
            probe_ms.append((time.perf_counter_ns() - t0) / 1e6)
    return {"samples": out, "probe": probe_ms}


def time_interleaved(cells: dict[str, Callable[[], Any]], rounds: int, rng: np.random.Generator,
                     probe: Callable[[], Any] | None = None, warmup: int = 5) -> dict[str, Any]:
    """Every cell once per round, in a fresh shuffled order, with the probe timed once per round;
    returns each cell's samples (ms) and the probe's."""
    import time

    for fn in cells.values():
        for _ in range(warmup):
            fn()
    if probe is not None:
        for _ in range(warmup):
            probe()
    names = list(cells)
    out: dict[str, list[float]] = {n: [] for n in names}
    probe_ms: list[float] = []
    for _ in range(rounds):
        for i in rng.permutation(len(names)):
            t0 = time.perf_counter_ns()
            cells[names[i]]()
            out[names[i]].append((time.perf_counter_ns() - t0) / 1e6)
        if probe is not None:
            t0 = time.perf_counter_ns()
            probe()
            probe_ms.append((time.perf_counter_ns() - t0) / 1e6)
    return {"samples": out, "probe": probe_ms}

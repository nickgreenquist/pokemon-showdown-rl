"""A monotone recalibration of the critic's output, fitted once and carried.

RESULTS §27.1: the critic sits at EV 0.2176 against a ceiling of 0.3630, and an
out-of-sample recalibration moves it to 0.2279 (affine) or 0.2272 (isotonic).
That is **+0.0103 for one fitted curve and no training**, and it is the whole
calibration prize: the remaining ~93% of the gap is ranking, which no rescaling
touches.

CORRECTED 2026-09-19. This docstring published "+0.0195 ... to 0.2371 ... the
remaining 88%", and called isotonic "the best any monotone rescaling can do".
The cross-validation behind those figures split at the OUTCOME level while the
predictor is CONSTANT WITHIN A POSITION, so every held-out outcome had its own
position in training. Grouped by position the gain roughly halves, and the
optimality claim ("the best any monotone rescaling can do") was in-sample.

CORRECTED AGAIN, same day: a first pass also concluded "AFFINE NOW BEATS
ISOTONIC". That rested on ONE cross-validation fold draw. Over 40 seeds the
difference is +0.00055 +/- 0.00128 with affine ahead in 24/40 -- half of
isotonic's own seed-to-seed sd. WHICH MAP WINS IS UNRESOLVED at this n; both
buy ~+0.010. This class is fitted by `ValueCalibration.fit` (isotonic) because
that is what is wired; the choice is not evidence-backed.

IS IT INERT INSIDE THE SEARCH? The objection to expect is that a monotone map
cannot reorder leaves at a single node, so it cannot change an argmax. That is
true and it is not the whole story:

  * `matrix.py::row_ev` takes an EXPECTATION of leaf values over the opponent's
    column distribution, and an average of a non-linearly transformed quantity
    reorders -- `tests/test_value_calibration.py` constructs a case;
  * the D5 margin gate is a THRESHOLD on that same scale, so recalibrating
    changes the override rate and `margin_delta` MUST be re-swept with it (the
    standing rule: match on the realized rate, never on the knob);
  * the tree's `decide="q"` rule compares backed-up means, which are averages
    for the same reason.

CARRY THE FIT WITH THE CHECKPOINT. It is a property of THAT critic, not of the
format. A curve fitted on one checkpoint and applied to another is a new,
untested object -- `fit_meta` exists so a mismatch is visible in an artifact
rather than silent.

FITTING. Pool-adjacent-violators on (critic value, realized outcome) pairs, the
same estimator `scripts/critic_calibration.py` uses, so the number reported there
and the transform applied here cannot drift apart.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def pava(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Isotonic fit by pool adjacent violators; returns (xs, fitted) sorted."""
    idx = np.argsort(x, kind="mergesort")
    xs, ys = np.asarray(x)[idx], np.asarray(y)[idx]
    val: list[float] = []
    wt: list[float] = []
    for v in ys:
        val.append(float(v))
        wt.append(1.0)
        while len(val) > 1 and val[-2] > val[-1]:
            v2, w2 = val.pop(), wt.pop()
            v1, w1 = val.pop(), wt.pop()
            val.append((v1 * w1 + v2 * w2) / (w1 + w2))
            wt.append(w1 + w2)
    return xs, np.repeat(val, [int(w) for w in wt])


class ValueCalibration:
    """A fitted monotone map from critic output to calibrated value.

    `apply` is vectorised and CLAMPS at the fitted range: a leaf value outside
    the range the fit ever saw is mapped to the nearest endpoint rather than
    extrapolated, because an isotonic fit says nothing outside its support and
    extrapolating one is how a calibration becomes a fabrication.
    """

    def __init__(self, xs: np.ndarray, ys: np.ndarray, fit_meta: dict | None = None):
        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        assert xs.size == ys.size and xs.size >= 2, "a fit needs at least two knots"
        assert np.all(np.diff(xs) >= 0), "knots must be sorted"
        assert np.all(np.diff(ys) >= -1e-12), "the fit must be monotone"
        self.xs, self.ys = xs, ys
        self.fit_meta = dict(fit_meta or {})

    @classmethod
    def fit(cls, values, outcomes, fit_meta=None) -> "ValueCalibration":
        xs, ys = pava(np.asarray(values, dtype=np.float64),
                      np.asarray(outcomes, dtype=np.float64))
        # THIN TO BOTH ENDS OF EACH LEVEL SET, not just the first.
        #
        # WRONG UNTIL 2026-09-19: keeping only the FIRST x of each flat run turns
        # every isotonic STEP into a RAMP under np.interp, because the fit is a
        # step function and interpolation between retained knots invents the
        # slope. Measured on the real 22,358-pair fit: 42 knots retained, max
        # |deployed - true| = 0.158, and 27% OF THE FITTED GAIN thrown away
        # (in-sample EV +0.0213 full vs +0.0155 as deployed) -- while this
        # module's docstring claimed the estimator was shared with
        # scripts/critic_calibration.py "so the number reported there and the
        # transform applied here cannot drift apart". They had drifted.
        keep = np.zeros(xs.size, dtype=bool)
        keep[0] = keep[-1] = True
        step = np.flatnonzero(np.diff(ys) > 1e-12)
        keep[step] = True            # last x of the run that ENDS at the step
        keep[step + 1] = True        # first x of the run that BEGINS after it
        return cls(xs[keep], ys[keep], fit_meta)

    @classmethod
    def from_rows(cls, path) -> "ValueCalibration":
        """Fit from a `scripts/outcome_variance.py` rows JSONL."""
        rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
        v = np.array([r["critic"] for r in rows for _ in r["outcomes"]], dtype=np.float64)
        o = np.array([x for r in rows for x in r["outcomes"]], dtype=np.float64)
        return cls.fit(v, o, {"source": str(path), "positions": len(rows),
                              "outcomes": int(o.size)})

    def apply(self, v):
        return np.interp(np.asarray(v, dtype=np.float64), self.xs, self.ys)

    def to_dict(self) -> dict:
        return {"xs": self.xs.tolist(), "ys": self.ys.tolist(),
                "fit_meta": self.fit_meta}

    @classmethod
    def from_dict(cls, d: dict) -> "ValueCalibration":
        return cls(np.array(d["xs"]), np.array(d["ys"]), d.get("fit_meta"))

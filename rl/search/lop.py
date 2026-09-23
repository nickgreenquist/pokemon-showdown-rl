"""R7 -- the L-OP ON A LIVE BATTLE: G2's operator (plan §6 G2; AMENDMENT BOX 5 item 3).

The operator G1b's belief arm runs on the engine (`scripts/g1_engine_mirror.py`
/2, `LOpBelief`), fed by B6's write-side bridge instead of the engine resample,
so it can play from a poke-env battle -- off Foul Play, or on the ladder. At a
decision with more than one legal action:

  1. OUR PRIOR is the committee's on our own observation, with EnsembleAgent's
     rule (mask BEFORE log_softmax, the mean of the members' log-probs,
     `rl/search/ensemble.py`), so the GREEDY action -- what the L-op plays
     whenever it does not override -- is exactly the action the greedy
     `ensemble_seat` anchor plays in the same state: the comparison isolates
     the search.
  2. B WORLDS from our information set on the POKE-ENV side
     (`rl/search/determinize.py::sample_determinization`), each built into an
     engine root by `rl/search/engine_bridge.py::build_root` (gate R1-E: 99.7%
     of built roots bitwise with the live observation, mask parity exact). A
     world the bridge refuses (`Unbuildable`) is skipped and COUNTED BY FAMILY;
     a world whose OUR-side mask disagrees with poke-env's is skipped and
     counted (the prior is poke-env's, so the two must agree).
  3. THE FOE'S PRIOR in each world is the committee's on THAT world's foe view
     (`node.obs(tables, "p2")`) -- the same object G0, G1 and the belief read
     measured, with no peek: the foe view is the determinized one.
  4. `native.solve` scores each world at the operator's dials (the critic --
     the committee's mean observation critic -- at the leaves, one view: the
     fleet's form, box 5 item 5); Qbar per row is AVERAGED over the worlds
     (PIMC); the soft best response on the average (`native.solve`'s own
     arithmetic, self-checked against its pi' on every world) gives a';
     a' is played iff it moves off greedy by at least `margin_gate` critic
     units. No world built -> greedy, counted.

Every decision's RNG is keyed by (seed, battle_index, turn, decision_index),
`scripts/search_r1e_gate.py::decision_rng`'s rule, so an arm replays.

DIALS: `native.DIALS` for the solve (`native.dials_from`: the signature's
list, unknown keys fail) and this class's own keyword-only parameters
(`LOP_DIALS`, derived from `__init__`'s signature the same way). Counters are
exposed in `counters` and summarised by `report()`; a decision the operator
searched returns `search/leaves` in its stats (the FP harness's "searched"
test) with the per-decision `lop/*` reads beside it.
"""

from __future__ import annotations

import inspect
import math
import time
from collections import defaultdict
from typing import Any

import numpy as np

from rl.search import native

N_ACTIONS = 10


def _softmax_masked(scores: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """probabilities from EnsembleAgent.scores' masked mean log-probs (the
    geometric pool `scripts/rollout_q.py::Committee.probs` computes)."""
    s = np.where(mask, np.asarray(scores, np.float64), -np.inf)
    p = np.exp(s - s[mask].max())
    p[~mask] = 0.0
    return p / p.sum()


class NativeLOp:
    """The belief-sampled, gated L-op over a poke-env battle. `ensemble` is an
    `rl.search.ensemble.EnsembleAgent` (its `scores` and its members' critics
    are all the L-op reads); `tables` is `rl.envs.engine_tables.build_tables()`'s."""

    def __init__(self, ensemble: Any, tables: Any, *, worlds: int = 8, margin_gate: float = 0.01,
                 seed: int = 0, solve: dict | None = None):
        if worlds < 1:
            raise ValueError(f"worlds must be >= 1, got {worlds}")
        if not (margin_gate >= 0.0 and math.isfinite(margin_gate)):
            raise ValueError(f"margin_gate must be a finite float >= 0, got {margin_gate!r}")
        if not solve:
            raise ValueError("the solve dials must be given (the pre-reg names them; native's defaults are not the operator G1 read)")
        self.ens = ensemble
        self.members = list(ensemble.members)
        self.tables = tables
        self.worlds = int(worlds)
        self.margin_gate = float(margin_gate)
        self.seed = int(seed)
        self.solve_dials = native.dials_from(solve)
        if self.solve_dials.get("root_rule", "soft_br") != "soft_br":
            raise ValueError("the L-op's PIMC average re-implements the soft best response only; root_rule must be soft_br")
        self.tau = float(self.solve_dials.get("tau", 1.0))
        self.counters: dict[str, float] = defaultdict(float)

    # ---- the committee's surfaces ------------------------------------------------
    def _probs(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return _softmax_masked(self.ens.scores(np.asarray(obs, np.float32), np.asarray(mask, bool)), np.asarray(mask, bool))

    def _value_fn(self, e: dict) -> np.ndarray:
        import torch
        x = torch.as_tensor(np.ascontiguousarray(e["obs"]), dtype=torch.float32)
        with torch.no_grad():
            return torch.stack([m.critic(x).squeeze(-1) for m in self.members]).mean(dim=0).numpy().astype(np.float64)

    # ---- one decision -------------------------------------------------------------
    def act(self, battle: Any, obs: np.ndarray, mask: np.ndarray, battle_index: int,
            decision_index: int) -> tuple[int, dict[str, float]]:
        from rl.search.determinize import sample_determinization
        from rl.search.engine_bridge import Unbuildable, build_root

        mask = np.asarray(mask, bool)
        scores = np.asarray(self.ens.scores(np.asarray(obs, np.float32), mask), np.float64)
        greedy = int(np.argmax(np.where(mask, scores, -np.inf)))    # EnsembleAgent.act's action (lowest index on ties)
        self.counters["search/decisions"] += 1
        if mask.sum() <= 1:
            self.counters["lop/forced"] += 1
            return greedy, {}
        turn = int(getattr(battle, "turn", 0))
        key = hash((self.seed, int(battle_index), turn, int(decision_index)))
        rng = np.random.default_rng(key & 0xFFFFFFFFFFFFFFFF)
        prior = _softmax_masked(scores, mask)
        prior_m = prior[mask] / prior[mask].sum()      # native.solve's own renormalisation, bit for bit
        rows = np.flatnonzero(mask)
        ig = int(np.flatnonzero(rows == greedy)[0])
        t0 = time.perf_counter()
        qs, leaves = [], 0
        for b in range(self.worlds):
            det = sample_determinization(battle, rng)
            try:
                node, _r1, _r2 = build_root(battle, det, None, seed=int(rng.integers(0, 2**62)), rng=rng)
            except Unbuildable as err:
                self.counters[f"lop/refused/{err.family}"] += 1
                continue
            if not np.array_equal(np.asarray(node.mask(self.tables, "p1"), bool), mask):
                self.counters["lop/mask_mismatch"] += 1
                continue
            m2 = np.asarray(node.mask(self.tables, "p2"), bool)
            p2 = self._probs(np.asarray(node.obs(self.tables, "p2"), np.float32), m2) if m2.any() else np.zeros(N_ACTIONS)
            res = native.solve([native.World(node)], self.tables, "p1", prior, p2, self._value_fn,
                               (key * 31 + b + 1) & 0x7FFFFFFFFFFFFFFF, **self.solve_dials)
            q_w = np.asarray(res["q_row"], np.float64)[mask]
            lw = np.log(prior_m) + q_w / self.tau
            pw = np.exp(lw - lw.max())
            if not np.array_equal(pw / pw.sum(), np.asarray(res["pi"], np.float64)[mask]):
                raise RuntimeError("the L-op's soft BR disagrees with native.solve's pi' -- not the same operator")
            qs.append(q_w)
            leaves += int(res["counters"]["search/leaves"])
        ms = (time.perf_counter() - t0) * 1e3
        self.counters["lop/worlds_built"] += len(qs)
        self.counters["lop/worlds_tried"] += self.worlds
        if not qs:
            self.counters["lop/no_world"] += 1
            return greedy, {}
        q_avg = np.mean(qs, axis=0)
        logits = np.log(prior_m) + q_avg / self.tau
        pi = np.exp(logits - logits.max())
        pi /= pi.sum()
        j = int(np.argmax(pi))
        a_prime = int(rows[j])
        margin = float(q_avg[j] - q_avg[ig])
        action = a_prime if (a_prime != greedy and margin >= self.margin_gate) else greedy
        override = int(action != greedy)
        self.counters["search/searched"] += 1
        self.counters["search/overrides"] += override
        self.counters["lop/argmax_moved"] += int(a_prime != greedy)
        self.counters["lop/margin_sum"] += margin
        self.counters["lop/ms_sum"] += ms
        self.counters["search/leaves_sum"] += leaves
        return action, {"search/leaves": float(leaves), "lop/worlds": float(len(qs)), "lop/override": float(override),
                        "lop/margin": margin, "lop/ms": ms}

    def report(self) -> dict[str, Any]:
        """The arm's counters as the FP harness stamps them: the override rate
        beside every win rate (the landmine), the refusal families, the dose."""
        c = self.counters
        searched = max(c["search/searched"], 1.0)
        dec = c["search/decisions"]
        out = {
            "lop_dials": {"worlds": self.worlds, "margin_gate": self.margin_gate, "seed": self.seed, "solve": dict(self.solve_dials)},
            "search/decisions": dec,
            "search/searched": c["search/searched"],
            "search/overrides": c["search/overrides"],
            "search/override_rate": c["search/overrides"] / max(dec, 1.0),
            "search/override_rate_searched": c["search/overrides"] / searched,
            "lop/argmax_moved_rate": c["lop/argmax_moved"] / searched,
            "lop/margin_mean": c["lop/margin_sum"] / searched,
            "lop/ms_mean": c["lop/ms_sum"] / searched,
            "lop/leaves_mean": c["search/leaves_sum"] / searched,
            "lop/forced": c["lop/forced"],
            "lop/no_world": c["lop/no_world"],
            "lop/mask_mismatch": c["lop/mask_mismatch"],
            "lop/worlds_built_rate": c["lop/worlds_built"] / max(c["lop/worlds_tried"], 1.0),
            "lop/refused": {k.split("/", 2)[2]: v for k, v in c.items() if k.startswith("lop/refused/")},
        }
        return out


LOP_DIALS = tuple(p.name for p in inspect.signature(NativeLOp.__init__).parameters.values()
                  if p.kind is inspect.Parameter.KEYWORD_ONLY)
"""The L-op's own dials, read off the signature (`worlds`, `margin_gate`,
`seed`, `solve`) -- a pre-reg key outside this list fails (`lop_from`)."""


def lop_from(spec: dict | None) -> dict[str, Any]:
    """A pre-reg arm's `lop:` block -> NativeLOp's keyword arguments. Unknown
    keys are a HARD FAILURE (the typed-list landmine); the `solve` sub-block is
    validated by `native.dials_from` at construction."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(LOP_DIALS))
    if unknown:
        raise ValueError(f"unknown L-op dial(s) {unknown}; the dials are {list(LOP_DIALS)}")
    return spec

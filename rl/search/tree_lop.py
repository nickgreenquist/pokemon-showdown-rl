"""DEEP SEARCH Step A -- the native TREE as an inference operator on a LIVE battle.

`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md` r2 §2 Step A, gate (iii) and Step B's
tier 3. `rl/search/lop.py::NativeLOp` (G2's operator) with its one-ply
`native.solve` replaced by `rl/search/native_tree.py::search`; everything else is
the L-op's, so an arm of this against a greedy `ensemble_seat` over the same
committee isolates the search:

  1. OUR PRIOR is the committee's on our observation with EnsembleAgent's rule
     (mask BEFORE log_softmax, the mean of the members' log-probs), so the GREEDY
     action -- what this plays whenever it does not override -- is exactly the
     `ensemble_seat` anchor's.
  2. B WORLDS from our information set (`sample_determinization(sample_active=
     True)` -> `engine_bridge.build_root`, our side's reveal from a per-battle
     `RevealHistory`), refused by family and errors by type, never let into
     poke-env; a world whose OUR-side mask disagrees with poke-env's is skipped
     and counted.
  3. THE TREE searches the worlds together (`sims` TOTAL simulations; the foe's
     prior in each world is the committee on that world's foe view; the leaves are
     the committee's mean observation critic; the prior below the root the
     committee's policy on each node's views, batched).
  4. THE GATE: the tree's candidate (its root rule's argmax) is played iff it
     moves off greedy by at least `margin_gate` in the tree's own root Q
     (`search/margin`). No world built, or the tree fell back -> greedy, counted.

Every decision's RNG is keyed by (seed, battle_index, turn, decision_index), the
L-op's rule, so an arm replays. DIALS: this class's keyword-only parameters
(`TREE_LOP_DIALS`, from the signature) and the tree's under `tree:`
(`native_tree.dials_from`); an unknown key fails.
"""

from __future__ import annotations

import asyncio
import inspect
import math
import time
from collections import defaultdict
from typing import Any

import numpy as np

from rl.search import native_tree
from rl.search.lop import _softmax_masked

N_ACTIONS = 10
_NEVER_SWALLOW = (KeyboardInterrupt, SystemExit, GeneratorExit, asyncio.CancelledError)
# the per-decision tree counters averaged into the arm report (the FP seat also
# collects every `tree/*` stat a decision returns)
_TREE_MEANS = ("tree/sims", "tree/depth_mean", "tree/depth_max", "tree/upd_mean", "tree/turns_mean",
               "tree/turns_max", "tree/nodes", "tree/merges", "tree/pass_nodes", "tree/terminal_sims",
               "tree/capped_sims", "tree/world_agree", "tree/ms_value", "tree/ms_prior", "search/rust_ms",
               "search/kl_prior", "search/topk_mass")


class NativeTreeLOp:
    """The belief-sampled, gated TREE over a poke-env battle. `ensemble` is an
    `rl.search.ensemble.EnsembleAgent`; `tables` is `build_tables()`'s."""

    def __init__(self, ensemble: Any, tables: Any, *, worlds: int = 8, margin_gate: float = 0.0,
                 seed: int = 0, tree: dict | None = None):
        if worlds < 1:
            raise ValueError(f"worlds must be >= 1, got {worlds}")
        if not (margin_gate >= 0.0 and math.isfinite(margin_gate)):
            raise ValueError(f"margin_gate must be a finite float >= 0, got {margin_gate!r}")
        if not tree:
            raise ValueError("the tree dials must be given (a pre-reg or a smoke names them)")
        self.ens = ensemble
        self.members = list(ensemble.members)
        self.tables = tables
        self.worlds = int(worlds)
        self.margin_gate = float(margin_gate)
        self.seed = int(seed)
        self.tree_dials = native_tree.dials_from(tree)
        self.counters: dict[str, float] = defaultdict(float)
        from rl.search.engine_bridge import RevealHistory
        self._history = RevealHistory()

    # ---- the committee's surfaces --------------------------------------------------
    def prior_fn(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Batched: EnsembleAgent's masked mean log-probs, then `_softmax_masked` per
        row -- the root prior's arithmetic, over many rows at once."""
        import torch
        from rl.common.masking import masked_logits
        x = torch.as_tensor(np.ascontiguousarray(obs), dtype=torch.float32)
        m = torch.as_tensor(np.asarray(mask, bool))
        with torch.no_grad():
            lp = torch.stack([torch.log_softmax(masked_logits(a.actor(x), m), dim=-1) for a in self.members]).mean(dim=0)
        s = np.where(np.asarray(mask, bool), lp.numpy().astype(np.float64), -np.inf)
        p = np.exp(s - s.max(axis=1, keepdims=True))
        p[~np.asarray(mask, bool)] = 0.0
        return p / p.sum(axis=1, keepdims=True)

    def value_fn(self, e: dict) -> np.ndarray:
        import torch
        x = torch.as_tensor(np.ascontiguousarray(e["obs"]), dtype=torch.float32)
        with torch.no_grad():
            return torch.stack([m.critic(x).squeeze(-1) for m in self.members]).mean(dim=0).numpy().astype(np.float64)

    # ---- one decision -------------------------------------------------------------
    def act(self, battle: Any, obs: np.ndarray, mask: np.ndarray, battle_index: int,
            decision_index: int) -> tuple[int, dict[str, float]]:
        from rl.search.determinize import sample_determinization
        from rl.search.engine_bridge import Unbuildable, build_root, our_side_reveal
        from rl.search.native import World

        self._history.update(battle)                  # every decision, forced ones included
        mask = np.asarray(mask, bool)
        scores = np.asarray(self.ens.scores(np.asarray(obs, np.float32), mask), np.float64)
        greedy = int(np.argmax(np.where(mask, scores, -np.inf)))    # EnsembleAgent.act's action
        self.counters["search/decisions"] += 1
        if mask.sum() <= 1:
            self.counters["tree_lop/forced"] += 1
            return greedy, {}
        turn = int(getattr(battle, "turn", 0))
        key = hash((self.seed, int(battle_index), turn, int(decision_index)))
        rng = np.random.default_rng(key & 0xFFFFFFFFFFFFFFFF)
        prior = _softmax_masked(scores, mask)
        t0 = time.perf_counter()
        our = our_side_reveal(battle, self._history)
        worlds = []
        for _b in range(self.worlds):
            try:
                det = sample_determinization(battle, rng, sample_active=True)
                node, _r1, _r2 = build_root(battle, det, None, seed=int(rng.integers(0, 2**62)), rng=rng, our_reveal=our)
                if not np.array_equal(np.asarray(node.mask(self.tables, "p1"), bool), mask):
                    self.counters["tree_lop/mask_mismatch"] += 1
                    continue
                worlds.append(World(node))
            except Unbuildable as err:
                self.counters[f"tree_lop/refused/{err.family}"] += 1
            except _NEVER_SWALLOW:
                raise
            except BaseException as err:              # a pyo3 PanicException is a BaseException
                self.counters[f"tree_lop/error/{type(err).__name__}"] += 1
                self.counters["tree_lop/errors"] += 1
        self.counters["tree_lop/worlds_tried"] += self.worlds
        self.counters["tree_lop/worlds_built"] += len(worlds)
        if not worlds:
            self.counters["tree_lop/no_world"] += 1
            return greedy, {}
        try:
            res = native_tree.search(worlds, self.tables, "p1", prior, None, self.value_fn, self.prior_fn,
                                     key & 0x7FFFFFFFFFFFFFFF, **self.tree_dials)
        except _NEVER_SWALLOW:
            raise
        except BaseException as err:
            self.counters[f"tree_lop/error/{type(err).__name__}"] += 1
            self.counters["tree_lop/errors"] += 1
            self.counters["tree_lop/search_failed"] += 1
            return greedy, {}
        c = res["counters"]
        ms = (time.perf_counter() - t0) * 1e3
        if c["tree/fallback"]:
            self.counters["tree_lop/fallback"] += 1
            return greedy, {}
        if int(res["policy_action"]) != greedy:
            raise RuntimeError(f"the tree's policy action {res['policy_action']} != the committee's greedy {greedy}")
        a_prime = int(res["action"])
        margin = float(c["search/margin"])
        action = a_prime if (a_prime != greedy and margin >= self.margin_gate) else greedy
        override = int(action != greedy)
        cnt = self.counters
        cnt["search/searched"] += 1
        cnt["search/overrides"] += override
        cnt["tree_lop/argmax_moved"] += int(a_prime != greedy)
        cnt["tree_lop/margin_sum"] += margin
        cnt["tree_lop/ms_sum"] += ms
        cnt["search/leaves_sum"] += float(c["search/leaves"])
        for k in _TREE_MEANS:
            cnt[f"sum/{k}"] += float(c[k])
        cnt["tree_lop/tree_errors"] += float(c["tree/errors"])
        for k, v in c.items():
            if k.startswith("tree/error/"):
                cnt[f"tree_lop/{k[5:]}"] += float(v)
        stats = {"search/leaves": float(c["search/leaves"]), "tree_lop/worlds": float(len(worlds)),
                 "tree_lop/override": float(override), "tree_lop/margin": margin, "tree_lop/ms": ms}
        stats.update({k: float(c[k]) for k in _TREE_MEANS if k.startswith("tree/")})
        return action, stats

    def report(self) -> dict[str, Any]:
        """The arm's counters: the override rate beside every win rate (the
        landmine), the dose in leaves AND depth, refusals and errors by kind."""
        c = self.counters
        searched = max(c["search/searched"], 1.0)
        dec = c["search/decisions"]
        out = {
            "tree_lop_dials": {"worlds": self.worlds, "margin_gate": self.margin_gate, "seed": self.seed,
                               "tree": dict(self.tree_dials)},
            "search/decisions": dec,
            "search/searched": c["search/searched"],
            "search/overrides": c["search/overrides"],
            "search/override_rate": c["search/overrides"] / max(dec, 1.0),
            "search/override_rate_searched": c["search/overrides"] / searched,
            "tree_lop/argmax_moved_rate": c["tree_lop/argmax_moved"] / searched,
            "tree_lop/margin_mean": c["tree_lop/margin_sum"] / searched,
            "tree_lop/ms_mean": c["tree_lop/ms_sum"] / searched,
            "tree_lop/leaves_mean": c["search/leaves_sum"] / searched,
            "tree_lop/forced": c["tree_lop/forced"],
            "tree_lop/no_world": c["tree_lop/no_world"],
            "tree_lop/no_world_rate": c["tree_lop/no_world"] / max(dec, 1.0),
            "tree_lop/mask_mismatch": c["tree_lop/mask_mismatch"],
            "tree_lop/mask_mismatch_rate": c["tree_lop/mask_mismatch"] / max(c["tree_lop/worlds_tried"], 1.0),
            "tree_lop/worlds_built_rate": c["tree_lop/worlds_built"] / max(c["tree_lop/worlds_tried"], 1.0),
            "tree_lop/refused": {k.split("/", 2)[2]: v for k, v in c.items() if k.startswith("tree_lop/refused/")},
            "tree_lop/errors": c["tree_lop/errors"],
            "tree_lop/error_types": {k.split("/", 2)[2]: v for k, v in c.items() if k.startswith("tree_lop/error/")},
            "tree_lop/search_failed": c["tree_lop/search_failed"],
            "tree_lop/fallback": c["tree_lop/fallback"],
            "tree_lop/tree_errors": c["tree_lop/tree_errors"],
        }
        for k in _TREE_MEANS:
            out[f"tree_lop/mean/{k}"] = c[f"sum/{k}"] / searched
        return out


TREE_LOP_DIALS = tuple(p.name for p in inspect.signature(NativeTreeLOp.__init__).parameters.values()
                       if p.kind is inspect.Parameter.KEYWORD_ONLY)
"""This operator's own dials, read off the signature (`worlds`, `margin_gate`, `seed`,
`tree`) -- a config key outside this list fails (`tree_lop_from`)."""


def tree_lop_from(spec: dict | None) -> dict[str, Any]:
    """An arm's `tree_lop:` block -> NativeTreeLOp's keyword arguments. Unknown keys
    are a HARD FAILURE; the `tree:` sub-block is validated by `native_tree.dials_from`
    at construction."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(TREE_LOP_DIALS))
    if unknown:
        raise ValueError(f"unknown tree L-op dial(s) {unknown}; the dials are {list(TREE_LOP_DIALS)}")
    return spec

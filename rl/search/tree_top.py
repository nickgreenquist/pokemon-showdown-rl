"""DEEP SEARCH Step C's enabler -- the TREE-OP: `rl/search/top.py`'s T-op seams with the
native TREE in place of the one-ply solve (`docs/proposals/DEEP_SEARCH_PATH_2026-09-25.md`
r2 §2 Step C: "A collector-side TreeOp (the T-op's seams; dials derived from its
signature)").

Everything a lane sees is the T-op's, so a Step C lane differs from an R7 searched lane
in the SEARCH and nothing else:
  * WHICH DECISIONS: not forced (one legal row), not where pi_theta's top-1 >= `top1_skip`,
    then a coin at `frac` -- KataGo's playout-cap randomisation, a dose matched across
    arms. The opponent model is the learner's own actor on the foe's view.
  * THE TARGETS: the tree's improved policy pi' (its root rule's -- completed-Q
    gumbel_mctx is the proposal's training target, not visit counts) and its value v' =
    sum_a pi'(a) Qbar(a) with Qbar the foe-prior-weighted root Q (the proposal: v' =
    E_{a~pi'} E_{b~prior} Q, NEVER the root max). One record per learner decision; the
    finished episode takes them back in row order, asserted against its length.
  * PLAY: `play` has no default (a config that drops it fails). Under play the action is
    SAMPLED from pi' and log pi'(a) is the behaviour log-prob, from the same float32 pi'
    that is stored, so PPO's ratio reads exactly pi_theta(a) / pi'(a). The proposal's
    default for Step C is `play: false`: at tree@900 KL(pi' || prior) was 1.669, against
    the T-op's ~0.16, so a played pi' puts PPO's ratio far outside the clip.
  * B = 1, THE TRUE WORLD (P3: at training time the true world IS a posterior sample).
    Leaves render the acting seat's tracked view.
The difference that matters for cost: every row a round searches goes into ONE
`native_tree.search_many` call, so their trees share every forward -- a lone tree at
B = 1 carries only its own few descents per forward.

The leaf evaluator is `native.critic_value_fn(agent)` -- the learner's critic on the
acting seat's `obs` (the fleet's plain observation critic, plan box 5 item 5). Below the
root grid the tree hands a value function `{"obs": ...}` only, so a critic that reads the
foe's view or a privileged block fails loudly there; the constructor refuses one.

Counters (batch-level means since the last `stats()`): the T-op's `search/*` set --
`searched_frac`, `eligible_frac`, `played_frac`, `decisions`, `seconds`, and the
operator's `kl_prior`, `override`, `margin`, `ms`, `leaves`, `pi_top1`, `prior_top1`,
`topk_mass`, `terminal_frac`, `pass_leaf_frac`, `v`, `v_prior` over the searched rows --
plus the tree's dose: `tree/sims`, `tree/depth_mean`, `tree/depth_max`, `tree/upd_mean`,
`tree/turns_mean`, `tree/nodes`, `tree/merges`, `tree/pass_nodes`, `tree/capped_sims`,
`tree/errors`, `tree/fallback`, `tree/ms_value`, `tree/ms_prior`; and `tree/batch_rows`,
the rows one `search_many` call searched.
"""

from __future__ import annotations

import inspect
import time
from collections import defaultdict
from typing import Any

import numpy as np
import torch

from rl.common.masking import masked_logits
from rl.envs.showdown import N_ACTIONS
from rl.search import native, native_tree

# the per-searched-row counters averaged into stats(), besides the T-op's search/* set
_TREE_KEYS = ("tree/sims", "tree/depth_mean", "tree/depth_max", "tree/upd_mean", "tree/turns_mean", "tree/nodes",
              "tree/merges", "tree/pass_nodes", "tree/capped_sims", "tree/errors", "tree/fallback",
              "tree/ms_value", "tree/ms_prior")
_SEARCH_KEYS = ("search/kl_prior", "search/override", "search/margin", "search/ms", "search/leaves",
                "search/pi_top1", "search/prior_top1", "search/topk_mass", "search/terminal_frac",
                "search/pass_leaf_frac", "search/v", "search/v_prior")


class TreeOp:
    def __init__(
        self,
        agent: Any,
        tables: Any,
        *,
        seat: str,
        seed: int,
        frac: float = 0.4,
        top1_skip: float = 0.97,
        play: bool,
        tree: dict,
    ):
        if not 0.0 <= frac <= 1.0:
            raise ValueError(f"frac must be in [0, 1], got {frac}")
        if not 0.0 < top1_skip <= 1.0:
            raise ValueError(f"top1_skip must be in (0, 1], got {top1_skip}")
        if bool(getattr(agent, "antisymmetric_critic", False)) or int(getattr(agent, "privileged_dim", 0) or 0):
            raise ValueError("the tree values its leaves on the acting seat's obs alone; an antisymmetric or "
                             "privileged critic would read inputs the tree never renders below the root grid")
        self.agent = agent
        self.tables = tables
        self.seat = str(seat)
        self.foe = "p2" if self.seat == "p1" else "p1"
        self.frac = float(frac)
        self.top1_skip = float(top1_skip)
        self.play = bool(play)
        self.tree_dials = native_tree.dials_from(tree)
        self.value_fn = native.critic_value_fn(agent, both_views=False)
        self.rng = np.random.default_rng(int(seed))
        self._records: dict[int, list[tuple[bool, np.ndarray, float]]] = defaultdict(list)
        self._sums: dict[str, float] = defaultdict(float)
        self._n_searched = self._n_eligible = self._n_played = self._n_decisions = 0
        self._decision_counter = 0
        self._calls = 0
        self.seconds = 0.0

    # ---- the dial list, derived ------------------------------------------------------

    @classmethod
    def dials(cls) -> dict[str, inspect.Parameter]:
        """Every keyword-only parameter of the constructor except the wiring (`seat`,
        `seed`): a config's operator block must be a subset."""
        sig = inspect.signature(cls.__init__)
        return {n: p for n, p in sig.parameters.items()
                if p.kind is inspect.Parameter.KEYWORD_ONLY and n not in ("seat", "seed")}

    @classmethod
    def check_dials(cls, spec: dict | None) -> dict[str, Any]:
        spec = dict(spec or {})
        unknown = set(spec) - set(cls.dials())
        if unknown:
            raise ValueError(
                f"unknown tree-op key(s) {sorted(unknown)}; the TreeOp's dials are "
                f"{sorted(cls.dials())} (derived from TreeOp.__init__, never typed)"
            )
        missing = sorted(n for n, p in cls.dials().items()
                         if p.default is inspect.Parameter.empty and n not in spec)
        if missing:
            raise ValueError(f"the tree-op block is missing required key(s) {missing} (no default, by design)")
        native_tree.dials_from(spec["tree"])
        return spec

    # ---- the learner's policy, batched ----------------------------------------------------

    def _probs(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        obs_t = torch.as_tensor(np.ascontiguousarray(obs), dtype=torch.float32, device=self.agent.device)
        mask_t = torch.as_tensor(np.asarray(mask, bool), dtype=torch.bool, device=self.agent.device)
        with torch.no_grad():
            p = torch.softmax(masked_logits(self.agent.actor(obs_t), mask_t), dim=-1)
        p = p.cpu().numpy().astype(np.float64)
        p[~np.asarray(mask, bool)] = 0.0
        return p / p.sum(axis=1, keepdims=True)

    # ---- the decision hook ----------------------------------------------------------------

    def decide(self, env, idx, obs, mask, actions, logp):
        """The T-op's hook: after the policy sampled `actions` / `logp` for the pending
        learner rows (slots `idx`), search the selected rows TOGETHER and return the
        (possibly replaced) actions and log-probs; one record per row."""
        n = len(idx)
        actions = np.array(actions, dtype=np.int64, copy=True)
        logp = np.array(logp, dtype=np.float32, copy=True)
        if n == 0:
            return actions, logp
        t0 = time.perf_counter()
        mask = np.asarray(mask, dtype=bool)
        probs = self._probs(obs, mask)
        eligible = (mask.sum(axis=1) > 1) & (probs.max(axis=1) < self.top1_skip)
        coin = self.rng.random(n) < self.frac
        search = eligible & coin
        self._n_decisions += n
        self._n_eligible += int(eligible.sum())
        rows = np.flatnonzero(search).tolist()
        results: dict[int, dict] = {}
        if rows:
            specs = []
            nodes = [env.snapshot(int(idx[i])) for i in rows]
            foe_rows = []
            for i, node in zip(rows, nodes):
                fm = np.asarray(node.mask(self.tables, self.foe), dtype=bool)
                foe_rows.append((np.asarray(node.obs(self.tables, self.foe), dtype=np.float32), fm) if fm.any() else None)
            live = [k for k, fr in enumerate(foe_rows) if fr is not None]
            opp = [np.zeros(N_ACTIONS) for _ in rows]
            if live:
                pr = self._probs(np.stack([foe_rows[k][0] for k in live]), np.stack([foe_rows[k][1] for k in live]))
                for j, k in enumerate(live):
                    opp[k] = pr[j]
            for k, (i, node) in enumerate(zip(rows, nodes)):
                self._decision_counter += 1
                specs.append(([native.World(node)], probs[i], opp[k], self._decision_counter))
            out = native_tree.search_many(specs, self.tables, self.seat, self.value_fn, self._probs, **self.tree_dials)
            self._calls += 1
            self._sums["tree/batch_rows"] += len(rows)
            results = dict(zip(rows, out))
        zeros = np.zeros(N_ACTIONS, dtype=np.float32)
        for i in range(n):
            slot = int(idx[i])
            res = results.get(i)
            if res is None:
                self._records[slot].append((False, zeros, 0.0))
                continue
            pi = np.asarray(res["pi"], dtype=np.float64)
            # The STORED pi' is float32; the behaviour log-prob is taken from that same
            # rounded value, so `old_logp == float32(log search_pi[a])` to the bit (B5).
            pi32 = pi.astype(np.float32)
            if self.play:
                a = int(self.rng.choice(N_ACTIONS, p=pi / pi.sum()))
                actions[i] = a
                logp[i] = np.float32(np.log(np.float64(pi32[a])))
                self._n_played += 1
            self._records[slot].append((True, pi32, float(res["v"])))
            self._n_searched += 1
            c = res["counters"]
            for k in _SEARCH_KEYS + _TREE_KEYS:
                self._sums[k] += float(c[k])
        self.seconds += time.perf_counter() - t0
        return actions, logp

    def take(self, slot: int, n_rows: int) -> dict[str, np.ndarray]:
        """The finished battle's records, in row order; asserted against the episode's
        row count (the alignment landmine)."""
        recs = self._records.pop(int(slot), [])
        if len(recs) != n_rows:
            raise RuntimeError(
                f"slot {slot}: {len(recs)} tree-op records for a {n_rows}-row episode -- the "
                "per-decision record and the engine's rows are misaligned"
            )
        return {
            "search_mask": np.array([r[0] for r in recs], dtype=np.bool_),
            "search_pi": np.stack([r[1] for r in recs]).astype(np.float32) if recs else np.zeros((0, N_ACTIONS), np.float32),
            "search_v": np.array([r[2] for r in recs], dtype=np.float32),
        }

    def drop(self, slot: int) -> None:
        self._records.pop(int(slot), None)

    def stats(self) -> dict[str, float]:
        out = {
            "search/decisions": float(self._n_decisions),
            "search/searched_frac": self._n_searched / max(self._n_decisions, 1),
            "search/eligible_frac": self._n_eligible / max(self._n_decisions, 1),
            "search/played_frac": self._n_played / max(self._n_decisions, 1),
            "search/seconds": self.seconds,
            "tree/batch_rows": self._sums.pop("tree/batch_rows", 0.0) / max(self._calls, 1),
        }
        for k, v in self._sums.items():
            out[k] = v / max(self._n_searched, 1)
        self._sums.clear()
        self._n_searched = self._n_eligible = self._n_played = self._n_decisions = 0
        self._calls = 0
        self.seconds = 0.0
        return out


def searcher_class(spec: dict | None) -> type:
    """`collector.search` -> the operator class, validating the block: the TreeOp when it
    carries a `tree` block (the tree's dials), else R7's one-ply T-op. Either class's own
    `check_dials` runs, so an unknown key fails whichever operator it was meant for."""
    spec = dict(spec or {})
    if "tree" in spec:
        TreeOp.check_dials(spec)
        return TreeOp
    from rl.search.top import TOp

    TOp.check_dials(spec)
    return TOp

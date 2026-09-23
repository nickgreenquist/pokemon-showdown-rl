"""R7 B4b -- the T-OP: the training-time operator inside the engine collector
(plan §3's T-op row; §4 items 1-3; amendment box 4 on which decisions get
searched).

On a fraction of the learner's decisions the collector runs `native.solve` on
the TRUE world (P3, B=1) with the learner's own critic as the leaf evaluator
(`native.critic_value_fn`: the antisymmetric privileged form when the agent
has it), gets pi' and v', and -- under `play` -- SAMPLES the played action
from pi' and records log pi'(a) as the behaviour log-prob, so PPO's ratio
carries the correction with no learner change (B5). Every learner decision of
a battle, searched or not, appends one record to the slot's buffer; the
finished episode takes them back in row order as `search_mask` / `search_pi`
/ `search_v` (rl/buffers/episode.py), and the count is asserted against the
episode length -- the alignment a silent off-by-one would corrupt.

WHICH DECISIONS (amendment 4): not forced (one legal row), not decisions where
pi_theta's top-1 >= `top1_skip` (0.97: a confident policy is not where a
depth-1 improvement lives), then a coin at `frac` -- a DOSE, matched across
arms. The opponent model is the learner's own actor on the foe's view (the
self-play prior; what G0 measured against). The dial list is this class's
signature (`dials()`), never typed: a config key that is not a dial fails.

Counters, batch-level means since the last `stats()` (the collector merges
them into `collect/*`'s dict): `search/searched_frac`, `search/eligible_frac`,
`search/decisions`, and the operator's own `search/kl_prior`, `search/override`,
`search/margin`, `search/ms`, `search/leaves`, `search/pi_top1`,
`search/prior_top1`, `search/topk_mass`, `search/terminal_frac`,
`search/pass_leaf_frac`, `search/v`, `search/v_prior` averaged over the
searched decisions. Counters reach disk before any dial gets an arm.
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
from rl.search import native


class TOp:
    def __init__(
        self,
        agent: Any,
        tables: Any,
        *,
        seat: str,
        seed: int,
        frac: float = 0.4,
        top1_skip: float = 0.97,
        cols_k: int = 3,
        chance_s: int = 2,
        tau: float = 1.0,
        play: bool = True,
    ):
        if not 0.0 <= frac <= 1.0:
            raise ValueError(f"frac must be in [0, 1], got {frac}")
        if not 0.0 < top1_skip <= 1.0:
            raise ValueError(f"top1_skip must be in (0, 1], got {top1_skip}")
        self.agent = agent
        self.tables = tables
        self.seat = str(seat)
        self.foe = "p2" if self.seat == "p1" else "p1"
        self.frac = float(frac)
        self.top1_skip = float(top1_skip)
        self.cols_k = int(cols_k)
        self.chance_s = int(chance_s)
        self.tau = float(tau)
        self.play = bool(play)
        self.value_fn = native.critic_value_fn(agent)
        # The leaf renders what the critic reads, and no more (native.solve's
        # `both_views`): the foe's view and the privileged blocks only for an
        # antisymmetric or privileged critic -- the fleet's plain observation
        # critic (plan AMENDMENT BOX 5 item 5) reads `obs` alone.
        self.both_views = bool(getattr(agent, "antisymmetric_critic", False)) or bool(int(getattr(agent, "privileged_dim", 0) or 0))
        self.rng = np.random.default_rng(int(seed))
        self._records: dict[int, list[tuple[bool, np.ndarray, float]]] = defaultdict(list)
        self._sums: dict[str, float] = defaultdict(float)
        self._n_searched = 0
        self._n_eligible = 0
        self._n_decisions = 0
        self._decision_counter = 0
        self.seconds = 0.0

    # ---- the dial list, derived ------------------------------------------------

    @classmethod
    def dials(cls) -> dict[str, inspect.Parameter]:
        """Every keyword-only parameter of the constructor except the wiring
        (`seat`, `seed`): the config's `collector.search` keys must be a subset."""
        sig = inspect.signature(cls.__init__)
        return {n: p for n, p in sig.parameters.items()
                if p.kind is inspect.Parameter.KEYWORD_ONLY and n not in ("seat", "seed")}

    @classmethod
    def check_dials(cls, spec: dict | None) -> dict[str, Any]:
        spec = dict(spec or {})
        unknown = set(spec) - set(cls.dials())
        if unknown:
            raise ValueError(
                f"unknown collector.search key(s) {sorted(unknown)}; the T-op's dials are "
                f"{sorted(cls.dials())} (derived from TOp.__init__, never typed)"
            )
        return spec

    # ---- the decision hook ----------------------------------------------------------

    def _probs(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.agent.device)
        mask_t = torch.as_tensor(mask, dtype=torch.bool, device=self.agent.device)
        with torch.no_grad():
            p = torch.softmax(masked_logits(self.agent.actor(obs_t), mask_t), dim=-1)
        p = p.cpu().numpy().astype(np.float64)
        p[~mask] = 0.0
        return p / p.sum(axis=1, keepdims=True)

    def decide(self, env, idx, obs, mask, actions, logp):
        """Called by the collector after the policy sampled `actions` / `logp`
        for the pending learner rows (slots `idx`). Returns the (possibly
        replaced) actions and log-probs and records one entry per row."""
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
        zeros = np.zeros(N_ACTIONS, dtype=np.float32)
        for i in range(n):
            slot = int(idx[i])
            if not search[i]:
                self._records[slot].append((False, zeros, 0.0))
                continue
            node = env.snapshot(slot)
            foe_mask = np.asarray(node.mask(self.tables, self.foe), dtype=bool)
            if foe_mask.any():
                foe_obs = np.asarray(node.obs(self.tables, self.foe), dtype=np.float32)[None]
                opp_prior = self._probs(foe_obs, foe_mask[None])[0]
            else:
                opp_prior = np.zeros(N_ACTIONS)
            self._decision_counter += 1
            res = native.solve(
                [native.World(node)], self.tables, self.seat, probs[i], opp_prior, self.value_fn,
                self._decision_counter, cols_k=self.cols_k, chance_s=self.chance_s, tau=self.tau,
                both_views=self.both_views,
            )
            pi = np.asarray(res["pi"], dtype=np.float64)
            # The STORED pi' is float32; the behaviour log-prob is taken from
            # that same rounded value, so `old_logp == float32(log search_pi[a])`
            # holds to the bit and the learner's ratio identity (B5) reads
            # exactly pi_theta(a) / pi'(a) against the row it stores.
            pi32 = pi.astype(np.float32)
            if self.play:
                a = int(self.rng.choice(N_ACTIONS, p=pi / pi.sum()))
                actions[i] = a
                logp[i] = np.float32(np.log(np.float64(pi32[a])))
            self._records[slot].append((True, pi32, float(res["v"])))
            self._n_searched += 1
            for k, v in res["counters"].items():
                self._sums[k] += float(v)
        self.seconds += time.perf_counter() - t0
        return actions, logp

    def take(self, slot: int, n_rows: int) -> dict[str, np.ndarray]:
        """The finished battle's records, in row order; asserted against the
        episode's row count (the alignment landmine)."""
        recs = self._records.pop(int(slot), [])
        if len(recs) != n_rows:
            raise RuntimeError(
                f"slot {slot}: {len(recs)} T-op records for a {n_rows}-row episode -- the "
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
            "search/seconds": self.seconds,
        }
        for k, v in self._sums.items():
            out[k] = v / max(self._n_searched, 1)
        self._sums.clear()
        self._n_searched = self._n_eligible = self._n_decisions = 0
        self.seconds = 0.0
        return out

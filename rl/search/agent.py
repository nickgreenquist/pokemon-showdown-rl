"""SearchAgent — the depth-1 search wrapper around one D26 checkpoint.

Chapter-3 R1 (ch3_search_design_r2.md §3/§6). act() contract:
    action, stats = agent.act(battle, obs, mask, battle_index, decision_index)
`battle` is battle1 (live) or a rehydrated harvest snapshot — both expose
the same public surface. All randomness comes from `matrix.decision_rng`
keyed by (checkpoint_seed, battle_index, turn, decision_index) — clause D2.

Placeholder turns (our gen-1 locked turns: sleep/freeze/partial-trap Fight
placeholder, recharge): the search is SKIPPED and the policy argmax is
returned, counted as `search/placeholder_skips` (design §3 — the realized
skip rate travels with every rung-2 sentence). Aliased-but-searchable
states do not exist beyond these (the placeholder set IS the aliased set).

The oppact head is promoted from train-time-only to inference here (a role
change named as a confound in the design; `oppact/sh_accuracy` is measured
at R1 before R2 depends on it). q is the head's plain softmax posterior;
its per-decision entropy is recorded so R2's degenerate-q fallback
criterion (median H(q) > 0.95*ln 6 on SELF-PLAY states, MF-4) can be
evaluated without re-running anything.

No silent fallback-to-policy anywhere in the search path: matrix.py's
watchdog raises (DO-NOT-BUILD #16).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from poke_env.data import GenData

from rl.common.masking import masked_logits
from rl.search.bridge import is_locked_turn
from rl.search.matrix import N_L6, Dose, decision_rng, solve_decision

# R3 E-cell noise stream: keyed like decision_rng but with this salt so the
# noise draws NEVER share (or shift) the determinization stream — an E2 arm
# replays the exact determinizations of the E0 arm, differing only at leaves.
_NOISE_SALT = 0xE2C0DE


class SearchAgent:
    def __init__(
        self,
        agent: Any,
        dose: Dose,
        checkpoint_seed: int,
        battle_format: str = "gen1randombattle",
        evaluator: dict | None = None,
        det_fn=None,
    ):
        """`evaluator` — R3's E-cell dial (design §4 R3). None = E0, the
        R2-credited configuration, bit-identical (no extra rng draws, no
        wrapper on the critic). Screen-grade dials:
          {"kind": "noise", "sigma": s}  E2: v_leaf + N(0, s) in outcome
              units, own per-decision rng stream (salted; D2-clean).
          {"kind": "loo", "agents": [a, a, a]}  E3: leaf value = mean of
              the OTHER lanes' critics; this lane's critic unused. Pure —
              our own weights, zero training.
          {"kind": "oppact_uniform"}  the oppact ablation: q replaced by
              uniform over the N_L6 classes at the root (the head still
              runs; the real q's entropy is still recorded so the dial
              measures the head's decision contribution, not its stats).
        """
        assert agent.aux_head is not None, (
            "SearchAgent needs the oppact head (D26 checkpoints carry it)"
        )
        if evaluator is not None:
            kind = evaluator["kind"]
            assert kind in ("noise", "loo", "oppact_uniform"), kind
            if kind == "noise":
                assert float(evaluator["sigma"]) > 0.0
            if kind == "loo":
                assert evaluator["agents"], "loo needs the other lanes' agents"
        self._agent = agent
        self._dose = dose
        self._seed = int(checkpoint_seed)
        self._evaluator = evaluator
        # det_fn: R3 oracle-team diagnostic ONLY — injected from the
        # separate binary; None = RSD sampling (every other arm, ever).
        self._det_fn = det_fn
        self._type_chart = GenData.from_format(battle_format).type_chart
        self.counters = {
            "search/decisions": 0,
            "search/placeholder_skips": 0,
            "search/flips": 0,  # chosen != policy argmax
        }
        self._entropies: list[float] = []

    def _forward(self, obs: np.ndarray, mask: np.ndarray):
        obs_t = torch.as_tensor(obs, dtype=torch.float32).unsqueeze(0)
        mask_t = torch.as_tensor(np.asarray(mask), dtype=torch.bool)
        with torch.no_grad():
            logits, *feats = self._agent.actor(obs_t, return_features=True)
            prior = torch.softmax(masked_logits(logits, mask_t), dim=-1)[0].numpy()
            q = torch.softmax(self._agent.aux_head(*feats), dim=-1)[0].numpy()
        return prior, q

    def _critic_fn(self, batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            v = self._agent.critic(torch.as_tensor(batch, dtype=torch.float32))
        return v.reshape(-1).numpy()

    def _loo_critic_fn(self, batch: np.ndarray) -> np.ndarray:
        t = torch.as_tensor(batch, dtype=torch.float32)
        with torch.no_grad():
            vs = [a.critic(t).reshape(-1) for a in self._evaluator["agents"]]
        return torch.stack(vs).mean(dim=0).numpy()

    def _decision_critic(self, battle_index: int, turn: int, decision_index: int):
        """The leaf evaluator for ONE decision. E0 returns the bound method
        unchanged — the None path adds nothing to the R2 code path."""
        if self._evaluator is None:
            return self._critic_fn
        kind = self._evaluator["kind"]
        if kind == "loo":
            return self._loo_critic_fn
        if kind == "noise":
            sigma = float(self._evaluator["sigma"])
            key = hash((self._seed, battle_index, turn, decision_index, _NOISE_SALT))
            noise_rng = np.random.default_rng(key & 0xFFFFFFFFFFFFFFFF)
            base = self._critic_fn

            def noisy(batch: np.ndarray) -> np.ndarray:
                v = base(batch)
                return v + sigma * noise_rng.standard_normal(v.shape)

            return noisy
        return self._critic_fn  # oppact_uniform: evaluator untouched

    def act(
        self,
        battle: Any,
        obs: np.ndarray,
        mask: np.ndarray,
        battle_index: int,
        decision_index: int,
    ) -> tuple[int, dict]:
        self.counters["search/decisions"] += 1
        prior, q = self._forward(obs, mask)
        if is_locked_turn(battle):
            self.counters["search/placeholder_skips"] += 1
            legal = np.flatnonzero(np.asarray(mask))
            action = int(legal[np.argmax(prior[legal])])
            return action, {"search/placeholder_skip": 1, "search/chosen": action}
        self._entropies.append(float(-(q * np.log(q + 1e-12)).sum()))
        if self._evaluator is not None and self._evaluator["kind"] == "oppact_uniform":
            q = np.full(N_L6, 1.0 / N_L6)
        turn = int(battle.turn)
        rng = decision_rng(self._seed, battle_index, turn, decision_index)
        action, stats = solve_decision(
            battle, np.asarray(mask), q, prior, self._dose, rng,
            self._decision_critic(battle_index, turn, decision_index),
            self._type_chart,
            det_fn=self._det_fn,
        )
        if action != stats["search/policy_argmax"]:
            self.counters["search/flips"] += 1
        stats["oppact/entropy"] = self._entropies[-1]
        return action, stats

    def entropy_median(self) -> float:
        return float(np.median(self._entropies)) if self._entropies else float("nan")

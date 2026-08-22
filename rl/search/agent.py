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
from rl.search.matrix import Dose, decision_rng, solve_decision


class SearchAgent:
    def __init__(
        self,
        agent: Any,
        dose: Dose,
        checkpoint_seed: int,
        battle_format: str = "gen1randombattle",
    ):
        assert agent.aux_head is not None, (
            "SearchAgent needs the oppact head (D26 checkpoints carry it)"
        )
        self._agent = agent
        self._dose = dose
        self._seed = int(checkpoint_seed)
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
        rng = decision_rng(self._seed, battle_index, int(battle.turn), decision_index)
        action, stats = solve_decision(
            battle, np.asarray(mask), q, prior, self._dose, rng,
            self._critic_fn, self._type_chart,
        )
        if action != stats["search/policy_argmax"]:
            self.counters["search/flips"] += 1
        stats["oppact/entropy"] = self._entropies[-1]
        return action, stats

    def entropy_median(self) -> float:
        return float(np.median(self._entropies)) if self._entropies else float("nan")

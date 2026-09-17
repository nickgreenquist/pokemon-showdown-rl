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
from rl.search.shadow_battle import public_view

# Leaf-encoding options (docs/search_relook/DET_BLIND.md). None is the
# R2-credited as-is encoding; nothing else has ever run.
LEAF_ENCODINGS = (None, "det_blind")

# Margin-gate options (docs/search_relook/MARGIN_SELECTOR.md). None is the
# R2-credited hard-argmax selector (matrix.py D4); nothing else has ever run
# live. 0.0 is D4 with ties conceded to the policy; inf is the greedy policy.
MARGIN_DELTA_OFF = None

# R3 E-cell noise stream: keyed like decision_rng but with this salt so the
# noise draws NEVER share (or shift) the determinization stream — an E2 arm
# replays the exact determinizations of the E0 arm, differing only at leaves.
_NOISE_SALT = 0xE2C0DE


def lane_seed(lane: str) -> int:
    """The decision-RNG seed behind a lane name.

    Every call site used `int(lane.lstrip("s"))`, which works only for lanes
    named `s<digits>` and raises on any other scheme. The monster fleet's
    lanes are `w104` / `l128`, so the searched committee could not be named at
    all until this existed (2026-09-16, JOURNEY 11.5). Digits-only is
    BACKWARD-IDENTICAL on every lane name this repo has ever used -- `s112` ->
    112 either way -- and simply stops being a landmine on the next one.
    """
    digits = "".join(c for c in lane if c.isdigit())
    assert digits, f"lane {lane!r} carries no digits to seed the decision RNG"
    return int(digits)


class SearchAgent:
    def __init__(
        self,
        agent: Any,
        dose: Dose,
        checkpoint_seed: int,
        battle_format: str = "gen1randombattle",
        evaluator: dict | None = None,
        det_fn=None,
        leaf_encoding: str | None = None,
        margin_delta: float | None = None,
        mcts: dict | None = None,
        depth2: dict | None = None,
        tree: dict | None = None,
        bcts: dict | None = None,
        heuristic: dict | None = None,
    ):
        """`leaf_encoding` — the leaf ENCODER dial (S1's finding,
        docs/search_relook/DET_BLIND.md). None = as-is, the R2-credited
        configuration, bit-identical (no view built, no extra work).
        "det_blind" hands every leaf the ROOT battle's opponent-side
        `PublicView`, so the determinizer's invented bench and movesets are
        encoded as UNKNOWN exactly where the live encoder would leave them
        unknown. Orthogonal to `evaluator`: this fixes the evaluator's
        INPUT, that swaps the evaluator.

        `evaluator` — R3's E-cell dial (design §4 R3). None = E0, the
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

        `margin_delta` — the SELECTOR dial (matrix.py D5,
        docs/search_relook/MARGIN_SELECTOR.md). None = the R2-credited hard
        argmax, bit-identical (nothing computed, no extra stats key). A
        float delta plays the search's argmax only when it beats the
        POLICY's argmax by more than delta on the row_ev scale; 0.0 concedes
        exact ties to the policy, `inf` reproduces the greedy policy
        exactly. Orthogonal to `leaf_encoding` (which fixes the evaluator's
        INPUT) and to `evaluator` (which swaps the evaluator): this changes
        only how the finished matrix is turned into an action, and it is
        the one dial that can only ever move the search back TOWARDS the
        policy — it cannot invent an action the D4 argmax did not already
        pick.
        """
        assert agent.aux_head is not None, (
            "SearchAgent needs the oppact head (D26 checkpoints carry it)"
        )
        if evaluator is not None:
            kind = evaluator["kind"]
            assert kind in ("noise", "loo", "oppact_uniform", "ens_min"), kind
            if kind == "noise":
                assert float(evaluator["sigma"]) > 0.0
            if kind in ("loo", "ens_min"):
                assert evaluator["agents"], f"{kind} needs the pool's agents"
        assert leaf_encoding in LEAF_ENCODINGS, (
            f"unknown leaf_encoding {leaf_encoding!r}; one of {LEAF_ENCODINGS}"
        )
        if margin_delta is not None:
            margin_delta = float(margin_delta)
            assert margin_delta == margin_delta and margin_delta >= 0.0, (
                f"margin_delta must be None or a float >= 0.0 (inf allowed), "
                f"got {margin_delta!r}"
            )
        self.margin_delta = margin_delta
        # PROBE (rl/search/mcts_probe.py): swap our depth-1 matrix for a real
        # TREE -- poke_engine's own MCTS on our determinizations, decided by
        # visit share, gated against the policy. None = untouched.
        self._mcts = mcts
        self._depth2 = depth2   # selective 1-ply lookahead at every leaf
        # OUR prior + OUR critic inside a real tree (rl/search/tree.py). The
        # thing neither of the other two probes is: matrix.py has our critic
        # and one ply, mcts_probe.py has a tree and poke_engine's heuristic.
        self._tree = tree
        # BCTS (Hallak et al. 2021): the margin, derived per decision from the
        # measured on- vs off-policy Bellman-error split, instead of a flat
        # constant. Overrides margin_delta when set.
        self._bcts = bcts
        # FOUL PLAY'S OWN leaf evaluator + its root-differenced sigmoid
        # (rl/search/fp_eval.py). Swaps WHAT values a leaf, leaving the dose,
        # the opponent model and the selector shape untouched.
        self._heuristic = heuristic
        self._agent = agent
        self._dose = dose
        self._seed = int(checkpoint_seed)
        self._evaluator = evaluator
        self.leaf_encoding = leaf_encoding
        # det_fn: R3 oracle-team diagnostic ONLY — injected from the
        # separate binary; None = RSD sampling (every other arm, ever).
        self._det_fn = det_fn
        self._type_chart = GenData.from_format(battle_format).type_chart
        self.counters = {
            "search/decisions": 0,
            "search/placeholder_skips": 0,
            "search/flips": 0,  # chosen != policy argmax
            # D5 only: decisions where the gate LET the search override the
            # policy. Identical to `flips` whenever margin_delta is not None
            # (both are "played != policy argmax"); it stays 0 with the gate
            # off, where no override decision was ever taken. Kept separate
            # so the two are cross-checkable from disk and so a future
            # selector cannot silently alias them.
            "search/overrides": 0,
            # ens_min diagnostics: which lane supplies the min, and how far
            # apart the lanes are. A lane share near 1.0 means the "minimum"
            # is one critic and the pessimism is imaginary.
            "ens_min/argmin_lane0": 0,
            "ens_min/argmin_lane1": 0,
            "ens_min/argmin_lane2": 0,
            "ens_min/spread_sum": 0.0,
            "ens_min/leaves": 0,
            # DEPTH-2 COUNTERS, and they exist because of 2026-09-11's VOID
            # probe: `solve_decision` DID emit `depth2/grandchildren`, the
            # adapter dropped it, and "the extra ply changed nothing" printed
            # the same win rate as "the extra ply never fired" (the D2 arm
            # produced ZERO grandchildren on all 1572 searched decisions and
            # read 0.8400). docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md
            # made the rule: any future dial gets a counter that REACHES DISK
            # before it gets an arm. These are that counter.
            "depth2/decisions_with_ply": 0,
            "depth2/grandchildren": 0,
            "depth2/leaves_deepened": 0,
            "depth2/shift_sum": 0.0,
            # same rule, same reason: a vehicle that never fired and one that
            # fired and changed nothing must not print the same number
            "heuristic/decisions": 0,
            "heuristic/leaves_scored": 0,
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

    def _tree_eval_fn(self, obs: np.ndarray):
        """(logprobs, values, q) from ONE forward — the tree's whole network
        surface. UNMASKED log-probs: below the root the tree derives its own
        legality from the engine state, so a slot it never offers cannot be
        chosen no matter what mass the policy puts on it."""
        obs_t = torch.as_tensor(obs, dtype=torch.float32)
        with torch.no_grad():
            logits, *feats = self._agent.actor(obs_t, return_features=True)
            logp = torch.log_softmax(logits, dim=-1).numpy()
            q = torch.softmax(self._agent.aux_head(*feats), dim=-1).numpy()
            v = self._agent.critic(obs_t).reshape(-1).numpy()
        return logp, v, q

    def _critic_fn(self, batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            v = self._agent.critic(torch.as_tensor(batch, dtype=torch.float32))
        return v.reshape(-1).numpy()

    def _loo_critic_fn(self, batch: np.ndarray) -> np.ndarray:
        t = torch.as_tensor(batch, dtype=torch.float32)
        with torch.no_grad():
            vs = [a.critic(t).reshape(-1) for a in self._evaluator["agents"]]
        return torch.stack(vs).mean(dim=0).numpy()

    def _ens_min_critic_fn(self, batch: np.ndarray) -> np.ndarray:
        """PESSIMISTIC leaf value over the pool's critics.

        Search maximises over leaf values, so any upward error in a leaf is
        selected FOR -- and Hallak et al. (NeurIPS 2021) measure that the
        upward error is systematically larger off the policy's own action,
        which is what makes the bias grow with depth. Chang et al. (ICML 2026)
        report that a min over a value ensemble "effectively addresses this
        bias and enables effective search". The three 100M lanes are an
        independent-init ensemble we already have, so this costs three critic
        forwards and no retraining.

        TWO FORMS, because a plain MIN is not obviously pessimism here.
        These critics were trained separately and are not calibrated to each
        other, so if one lane simply sits lower than the others the min is
        that lane's critic everywhere and nothing has been made pessimistic --
        the evaluator has just been swapped. `lcb_k` gives the scale-free
        form, mean - k*std, which is invariant to a per-lane offset and
        penalises exactly the leaves the lanes DISAGREE about; k = 0 is the
        plain mean. `argmin_share` records which lane supplied the min so the
        degenerate case is visible on disk rather than assumed away.

        Unlike `loo`, this INCLUDES the lane's own critic -- it is not a screen
        for "would a better evaluator help", it is the evaluator.
        """
        t = torch.as_tensor(batch, dtype=torch.float32)
        with torch.no_grad():
            vs = torch.stack(
                [a.critic(t).reshape(-1) for a in self._evaluator["agents"]])
        k = self._evaluator.get("lcb_k")
        am = vs.argmin(dim=0)
        for i in range(vs.shape[0]):
            self.counters["ens_min/argmin_lane%d" % i] += int((am == i).sum())
        self.counters["ens_min/spread_sum"] += float(
            (vs.max(0).values - vs.min(0).values).sum())
        self.counters["ens_min/leaves"] += int(vs.shape[1])
        if k is None:
            return vs.min(dim=0).values.numpy()
        return (vs.mean(dim=0) - float(k) * vs.std(dim=0)).numpy()

    def _decision_critic(self, battle_index: int, turn: int, decision_index: int):
        """The leaf evaluator for ONE decision. E0 returns the bound method
        unchanged — the None path adds nothing to the R2 code path."""
        if self._evaluator is None:
            return self._critic_fn
        kind = self._evaluator["kind"]
        if kind == "loo":
            return self._loo_critic_fn
        if kind == "ens_min":
            return self._ens_min_critic_fn
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
        if self._tree is not None:
            from rl.search.tree import TreeCfg, tree_decision
            action, stats = tree_decision(
                battle, np.asarray(mask), prior, self._tree_eval_fn, rng,
                self._type_chart, TreeCfg(**self._tree),
            )
            if action != stats.get("search/policy_argmax", action):
                self.counters["search/flips"] += 1
            if stats.get("search/overrode"):
                self.counters["search/overrides"] += 1
            stats["oppact/entropy"] = self._entropies[-1]
            return action, stats
        if self._mcts is not None:
            from rl.search.mcts_probe import mcts_decision
            action, stats = mcts_decision(
                battle, np.asarray(mask), prior, rng,
                n_det=int(self._mcts.get("n_det", 2)),
                duration_ms=int(self._mcts.get("ms", 20)),
                margin=self._mcts.get("margin", 0.10),
            )
            if action != stats.get("search/policy_argmax", action):
                self.counters["search/flips"] += 1
            if stats.get("search/overrode"):
                self.counters["search/overrides"] += 1
            stats["oppact/entropy"] = self._entropies[-1]
            if self._mcts.get("census"):
                from rl.search.mcts_probe import depth_census
                stats.update(depth_census(
                    battle, rng, tuple(self._mcts["census"])))
            # `search/leaves` is the adapter's "this decision was searched"
            # flag; the MCTS path has no leaf count of its own, so it is set to
            # 0 here purely so the per-decision stats get aggregated at all.
            stats.setdefault("search/leaves", 0)
            return action, stats
        action, stats = solve_decision(
            battle, np.asarray(mask), q, prior, self._dose, rng,
            self._decision_critic(battle_index, turn, decision_index),
            self._type_chart,
            det_fn=self._det_fn,
            leaf_view=(
                public_view(battle) if self.leaf_encoding == "det_blind" else None
            ),
            margin_delta=self.margin_delta,
            depth2=self._depth2,
            bcts=self._bcts,
            heuristic=self._heuristic,
            root_v=(self._critic_fn(obs[None].astype(np.float32))[0]
                    if self._bcts is not None else None),
        )
        if action != stats["search/policy_argmax"]:
            self.counters["search/flips"] += 1
        if stats.get("search/overrode"):
            self.counters["search/overrides"] += 1
        if self._heuristic is not None and "heuristic/leaves_scored" in stats:
            self.counters["heuristic/decisions"] += 1
            self.counters["heuristic/leaves_scored"] += int(stats["heuristic/leaves_scored"])
        if self._depth2 is not None and "depth2/grandchildren" in stats:
            gc = int(stats["depth2/grandchildren"])
            self.counters["depth2/grandchildren"] += gc
            self.counters["depth2/leaves_deepened"] += int(stats["depth2/leaves_deepened"])
            self.counters["depth2/decisions_with_ply"] += int(gc > 0)
            self.counters["depth2/shift_sum"] += float(stats.get("depth2/mean_shift", 0.0))
        stats["oppact/entropy"] = self._entropies[-1]
        return action, stats

    def entropy_median(self) -> float:
        return float(np.median(self._entropies)) if self._entropies else float("nan")

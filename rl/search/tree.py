"""OUR policy as the PRIOR, OUR critic at the LEAVES, inside a real tree.

This is the thing every search number in this project has been missing.

  * `rl/search/matrix.py` has our critic but exactly ONE ply. Its dose dial
    (n_det, leaf_cap) buys WIDTH at that one ply, which is why S/M/L/XL read
    flat -- breadth saturates.
  * `rl/search/mcts_probe.py` has a real tree but poke_engine's HEURISTIC at
    the leaves, so a win there says "a tree helps", not "our value function
    in a tree helps".

Here both hold at once: decoupled UCT over determinized engine states, our
masked policy as the PUCT prior on our side, the oppact head's L6 posterior as
the prior on theirs, and our critic as the leaf value. That is Wang's
architecture (and AlphaZero's) on our self-play object.

DECOUPLED UCT, because Showdown turns are SIMULTANEOUS. Each node keeps
separate visit/value statistics per side and selects each side's action
independently; the pair is then played jointly. This is what poke_engine's own
MCTS does (`MctsResult` carries `side_one` and `side_two` results separately)
and it is the standard treatment -- a single joint-action bandit over 9x6
pairs would need an order of magnitude more iterations to say anything.

CHANCE NODES ARE REAL. `generate_instructions` returns a branch distribution
(crit / miss / secondary), so a (a, b) pair is not one child. The top branches
are retained and one is SAMPLED per visit, which is what makes the backed-up
value an expectation rather than a single lucky line.

THE DECISION RULE is visit share at the root, gated against the policy's own
argmax by a margin -- the D5 idea, on a visit-share scale. MP20 vs MP20T
measured that this gate is not a detail: the same tree at a 0.10 margin
(30.0% override) lost 0.034 and at 0.35 (10.9% override) gained 0.016.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
from poke_engine import generate_instructions

from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.matrix import _terminal_value, our_action_str
from rl.search.shadow_battle import shadow_battle

# oppact L6: 0-3 = the active's move slots, 4 = switch, 5 = other-move
SWITCH_CLASS, OTHER_CLASS = 4, 5


@dataclass
class TreeCfg:
    """Every dial that is not a law. Defaults are one FP@20-scale budget."""

    iters: int = 100           # simulations per determinization
    n_det: int = 2
    c_puct: float = 1.5
    depth_cap: int = 8         # plies below the root before a forced leaf eval
    top_branches: int = 2      # chance-node branches retained per (a, b)
    our_k: int = 6             # our branching at a node
    opp_k: int = 5             # theirs
    margin: float | None = 0.10
    root_dirichlet: float = 0.0   # 0 = off; exploration noise at the root only
    value_from: str = "critic"    # "critic" | "zero" (ablation: tree alone)
    # DECISION RULE.
    #   "visits" -- AlphaZero / FP: root visit share. Assumes enough
    #     iterations for search to overrule the prior. Measured on the first
    #     smoke: our prior is sharp enough that 90.9% of visits land on one
    #     action, so at this budget visit share is very nearly the prior and
    #     the tree can barely speak.
    #   "q" -- root mean value, gated by a margin. This is EXACTLY the shape
    #     of the banked depth-1 selector (`row_ev` + margin_delta), on the
    #     same critic-value scale, so S3G10 at delta 0.10 and this at 0.10
    #     differ in DEPTH and nothing else. That is the comparison worth
    #     having.
    decide: str = "visits"
    root_min_visits: int = 0   # force-visit every root action this many times


def _active(side) -> tuple[int, Any]:
    ai = side.active_index
    ai = int(str(ai)[-1]) if not isinstance(ai, int) else ai
    return ai, side.pokemon[ai]


def _legal_ours(state: Any, k: int) -> list[tuple[int, str]]:
    """(slot, engine string) for our legal actions at an ARBITRARY state.

    Slot is the index our policy head uses: 0-5 switch to team slot, 6-9 the
    active's move slot -- poke-env's pinned mapping, the same one
    `our_action_str` inverts at the root. Deriving it from the engine state
    rather than from a `battle` object is what lets the tree keep going below
    the root, where no `battle` exists.
    """
    ai, act = _active(state.side_one)
    bench = [
        (i, m.id) for i, m in enumerate(state.side_one.pokemon)
        if i != ai and m.id.lower() != "none" and m.hp > 0
    ]
    if act.hp <= 0:  # forced switch: moves are not offered
        return bench[:k]
    moves = [
        (6 + j, m.id) for j, m in enumerate(act.moves)
        if getattr(m, "pp", 0) > 0 and not getattr(m, "disabled", False)
        and m.id and m.id.lower() != "none"
    ]
    if not moves:  # struggle-shaped: let the engine resolve it
        moves = [(6, "none")]
    # moves first: a tree that spends its branching budget on switches learns
    # nothing about the attack lines, and the root's own switches are already
    # covered by the policy prior.
    return (moves + bench)[:k]


def _legal_theirs(state: Any, k: int) -> list[tuple[int, str]]:
    """Same, for the opponent, tagged with its L6 CLASS so the oppact head's
    posterior can be used as a prior. Class 4 is any switch."""
    ai, act = _active(state.side_two)
    if act.hp <= 0:
        return [
            (SWITCH_CLASS, m.id) for i, m in enumerate(state.side_two.pokemon)
            if i != ai and m.id.lower() != "none" and m.hp > 0
        ][:k]
    out = [
        (j, m.id) for j, m in enumerate(act.moves)
        if getattr(m, "pp", 0) > 0 and not getattr(m, "disabled", False)
        and m.id and m.id.lower() != "none"
    ][:4]
    bench = [
        (SWITCH_CLASS, m.id) for i, m in enumerate(state.side_two.pokemon)
        if i != ai and m.id.lower() != "none" and m.hp > 0
    ]
    if bench:
        out.append(bench[0])
    if not out:
        out = [(OTHER_CLASS, "none")]
    return out[:k]


@dataclass
class Node:
    state: Any
    turn: int
    depth: int
    terminal: float | None = None
    expanded: bool = False
    ours: list = field(default_factory=list)     # [(slot, str)]
    theirs: list = field(default_factory=list)   # [(l6_class, str)]
    p_ours: np.ndarray | None = None
    p_theirs: np.ndarray | None = None
    n_a: np.ndarray | None = None
    w_a: np.ndarray | None = None
    n_b: np.ndarray | None = None
    w_b: np.ndarray | None = None
    n: int = 0
    kids: dict = field(default_factory=dict)     # (ai, bi) -> (pcts, [Node|None])


class Tree:
    """One determinization, searched.

    `eval_fn(obs: (N, D) float32) -> (logprobs (N, A), values (N,), q (N, 6))`
    is the ONE network surface this needs: the prior, the leaf value and the
    opponent model all come from the same forward.
    """

    def __init__(self, root_state, turn: int, cfg: TreeCfg, eval_fn, rng,
                 type_chart: dict, root_actions=None):
        self.cfg = cfg
        # At the ROOT we have the live battle's action mask, which is the only
        # authority on legality (the engine state does not model gen-1
        # placeholder turns or partial-trapping locks). Below the root there is
        # no battle object and `_legal_ours` is all there is.
        self.root_actions = root_actions
        self.eval_fn = eval_fn
        self.rng = rng
        self.type_chart = type_chart
        self.root = Node(root_state, turn, 0)
        self.evals = 0
        self.transition_failures = 0
        # DEPTH IS THE WHOLE QUESTION, so it is measured, not assumed: how
        # deep each simulation actually got, per decision.
        self.max_depth = 0
        self.depth_sum = 0
        self.sims = 0

    # --- network ------------------------------------------------------
    def _evaluate(self, node: Node) -> float:
        """Expand `node` and return its value from OUR seat's point of view."""
        from rl.envs.showdown import embed_battle

        if node.terminal is not None:
            return node.terminal
        sb = shadow_battle(node.state, node.turn, view=None)
        obs = embed_battle(sb, self.type_chart)[None, :].astype(np.float32)
        logp, val, q = self.eval_fn(obs)
        self.evals += 1
        v = float(val[0]) if self.cfg.value_from == "critic" else 0.0

        node.ours = (
            self.root_actions if node.depth == 0 and self.root_actions
            else _legal_ours(node.state, self.cfg.our_k)
        )
        node.theirs = _legal_theirs(node.state, self.cfg.opp_k)
        p = np.array([float(np.exp(logp[0, s])) for s, _ in node.ours])
        node.p_ours = p / p.sum() if p.sum() > 0 else np.full(len(p), 1.0 / len(p))
        # L6 -> the concrete opponent actions at THIS node. Several actions can
        # share a class (two live bench mons are both class 4); the class mass
        # is split evenly among them, which is the same "one column, one
        # weight" law the depth-1 matrix uses.
        cls = np.array([c for c, _ in node.theirs])
        share = np.array([max(float(q[0, c]), 1e-6) for c in cls])
        for c in set(cls.tolist()):
            m = cls == c
            share[m] /= m.sum()
        node.p_theirs = share / share.sum()

        na, nb = len(node.ours), len(node.theirs)
        node.n_a, node.w_a = np.zeros(na), np.zeros(na)
        node.n_b, node.w_b = np.zeros(nb), np.zeros(nb)
        node.expanded = True
        return v

    # --- selection ----------------------------------------------------
    def _puct(self, n_vec, w_vec, prior, total, sign):
        q = np.zeros_like(n_vec)
        nz = n_vec > 0
        q[nz] = sign * (w_vec[nz] / n_vec[nz])
        u = self.cfg.c_puct * prior * np.sqrt(total + 1.0) / (1.0 + n_vec)
        return int(np.argmax(q + u))

    def _child(self, node: Node, ai: int, bi: int) -> Node | None:
        """Chance node: retain the top branches once, sample one per visit."""
        key = (ai, bi)
        if key not in node.kids:
            a_str, b_str = node.ours[ai][1], node.theirs[bi][1]
            try:
                brs = generate_instructions(node.state, a_str, b_str)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:  # PyO3 panics are BaseException (F-14)
                brs = []
            brs = sorted(brs, key=lambda b: -b.percentage)[: self.cfg.top_branches]
            if not brs:
                self.transition_failures += 1
                node.kids[key] = (None, None)
                return None
            tot = sum(b.percentage for b in brs) or 1.0
            pct = np.array([b.percentage / tot for b in brs])
            node.kids[key] = (pct, [None] * len(brs), brs)
        entry = node.kids[key]
        if entry[0] is None:
            return None
        pct, slots, brs = entry
        j = int(self.rng.choice(len(pct), p=pct))
        if slots[j] is None:
            try:
                st = node.state.apply_instructions(brs[j])
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                self.transition_failures += 1
                return None
            slots[j] = Node(st, node.turn + 1, node.depth + 1,
                            terminal=_terminal_value(st))
        return slots[j]

    def _simulate(self, node: Node) -> float:
        self.max_depth = max(self.max_depth, node.depth)
        if node.terminal is not None:
            return node.terminal
        if not node.expanded:
            return self._evaluate(node)
        if node.depth >= self.cfg.depth_cap:
            # depth cap: the critic's estimate at this node, already computed
            # when it was expanded, is the best we have
            return float(node.w_a.sum() / max(node.n, 1)) if node.n else 0.0
        if node.depth == 0 and self.cfg.root_min_visits:
            # A flat floor at the ROOT only: `decide: q` needs a value for
            # every root action, and PUCT starves an action the policy puts
            # 0.001 on. Below the root PUCT is untouched.
            under = np.flatnonzero(node.n_a < self.cfg.root_min_visits)
            ai = (int(under[np.argmin(node.n_a[under])]) if len(under)
                  else self._puct(node.n_a, node.w_a, node.p_ours, node.n, +1))
        else:
            ai = self._puct(node.n_a, node.w_a, node.p_ours, node.n, +1)
        bi = self._puct(node.n_b, node.w_b, node.p_theirs, node.n, -1)
        kid = self._child(node, ai, bi)
        v = self._evaluate_or_recurse(kid)
        node.n += 1
        node.n_a[ai] += 1
        node.w_a[ai] += v
        node.n_b[bi] += 1
        node.w_b[bi] += v
        return v

    def _evaluate_or_recurse(self, kid: Node | None) -> float:
        if kid is None:  # the engine refused this pair; treat it as neutral
            return 0.0
        return self._simulate(kid)

    def run(self) -> None:
        self._evaluate(self.root) if not self.root.expanded else None
        if self.cfg.root_dirichlet > 0 and self.root.p_ours is not None:
            d = self.rng.dirichlet(
                np.full(len(self.root.p_ours), self.cfg.root_dirichlet))
            self.root.p_ours = 0.75 * self.root.p_ours + 0.25 * d
        for _ in range(self.cfg.iters):
            before = self.max_depth
            self._simulate(self.root)
            self.sims += 1
            self.depth_sum += self.max_depth if self.max_depth > before else before


def tree_decision(
    battle: Any,
    mask: np.ndarray,
    prior: np.ndarray,
    eval_fn: Callable,
    rng: np.random.Generator,
    type_chart: dict,
    cfg: TreeCfg,
) -> tuple[int, dict]:
    """n_det determinizations, one tree each, pooled by ROOT VISIT SHARE over
    our slots, gated against the policy's argmax."""
    rows = [i for i in range(len(mask)) if mask[i]]
    assert rows, "no legal action"
    policy_argmax = int(max(rows, key=lambda a: prior[a]))
    if len(rows) == 1:
        return rows[0], {"search/chosen": rows[0],
                         "search/policy_argmax": rows[0], "search/leaves": 0}

    counters = BridgeCounters()
    turn = int(battle.turn)
    visits: dict[int, float] = {}
    vals: dict[int, float] = {}
    total = 0.0
    evals = fails = trees = 0
    max_depth = 0
    depth_sum = sims = 0
    for _ in range(cfg.n_det):
        try:
            st = battle_to_state(battle, sample_determinization(battle, rng),
                                 counters)
            t = Tree(st, turn, cfg, eval_fn, rng, type_chart,
                     root_actions=[(a, our_action_str(battle, a)) for a in rows])
            t.run()
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            continue
        trees += 1
        evals += t.evals
        fails += t.transition_failures
        max_depth = max(max_depth, t.max_depth)
        depth_sum += t.depth_sum
        sims += t.sims
        for i, (slot, _s) in enumerate(t.root.ours):
            visits[slot] = visits.get(slot, 0.0) + t.root.n_a[i]
            vals[slot] = vals.get(slot, 0.0) + t.root.w_a[i]
            total += t.root.n_a[i]
    if not trees or total <= 0:
        return policy_argmax, {"search/chosen": policy_argmax,
                               "search/policy_argmax": policy_argmax,
                               "tree/failed": 1.0, "search/leaves": 0}

    # A slot the tree explored but the LIVE mask forbids is dropped: the tree
    # derives legality from the engine state, which does not model gen-1
    # placeholder turns or partial-trapping locks (bridge.is_locked_turn).
    share = {a: visits.get(a, 0.0) / total for a in rows}
    if cfg.decide == "q":
        # Root mean value per action, pooled over determinizations. An action
        # nobody visited cannot be argued for, so it sits at -inf rather than
        # at a fabricated 0.0.
        score = {
            a: (vals.get(a, 0.0) / visits[a]) if visits.get(a, 0.0) > 0
            else -np.inf
            for a in rows
        }
        if not np.isfinite(score[policy_argmax]):
            return policy_argmax, {
                "search/chosen": policy_argmax,
                "search/policy_argmax": policy_argmax, "search/overrode": 0,
                "search/leaves": evals, "tree/policy_unvisited": 1.0}
    else:
        score = share
    tree_argmax = int(max(rows, key=lambda a: (score[a], prior[a], -a)))
    gap = score[tree_argmax] - score[policy_argmax]
    override = cfg.margin is not None and gap > float(cfg.margin)
    chosen = tree_argmax if override else policy_argmax
    return chosen, {
        "search/chosen": chosen,
        "search/policy_argmax": policy_argmax,
        "search/overrode": int(bool(override)),
        "search/leaves": evals,
        "tree/argmax": tree_argmax,
        "tree/gap": gap,
        "tree/share_best": share[tree_argmax],
        "tree/share_policy": share[policy_argmax],
        "tree/q_best": float(score[tree_argmax]) if cfg.decide == "q" else 0.0,
        "tree/q_policy": float(score[policy_argmax]) if cfg.decide == "q" else 0.0,
        "tree/evals": float(evals),
        "tree/max_depth": float(max_depth),
        "tree/mean_sim_depth": float(depth_sum / max(sims, 1)),
        "tree/transition_failures": float(fails),
        "tree/root_q_best": float(
            vals.get(tree_argmax, 0.0) / max(visits.get(tree_argmax, 0.0), 1.0)),
    }

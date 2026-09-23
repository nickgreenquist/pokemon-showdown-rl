"""R7 B3 -- the native search operator on `pkmn_gen1` (`docs/proposals/
R7_NATIVE_SEARCH_PLAN_2026-09-22.md` §3, amendment boxes 2-3).

ONE operator, three uses (the plan's table): the T-op inside the collector
(one world, ~40 leaves), the L-op at the ladder (B sampled worlds), and the
I-op's critic-side columns (`scripts/rollout_q.py`). It is depth-1 on purpose:
the first ply expanded EXACTLY by the engine, the leaves valued by the
critic, the root solved as a matrix game against the opponent's top-k replies.

    rows      = our legal actions (every one; the mask is the engine's)
    columns   = the opponent's top-k legal actions by pi_opp (k from G0's
                `opp_best_outside_topk` read, never typed -- the default here
                is the plan's placeholder and every use passes its own)
    chance    = S samples per cell under CRN-1 (seed keyed on the column and
                the sample, never the row: `pkmn_gen1.SearchNode.expand`)
    leaves    = both seats' views rendered by the engine; the critic is
                whatever `value_fn` the caller hands in (the antisymmetric
                critic reads [obs | obs2 (| priv | priv2)], B2)
    Q(a, b)   = mean over chance of V(leaf); terminal leaves are +-1 / 0
    Qbar(a)   = sum_b q(b) Q(a, b), q = pi_opp renormalised over the k columns
                -- THE VALUE ESTIMAND is the expectation under the OPPONENT'S
                PRIOR POLICY (amendment 1 item 3); minimax is never the target
    pi'(a)    ~ pi_theta(a) * exp(Qbar(a) / tau)   -- P4, Gumbel-MuZero's
                improved policy, the prior as the trust region
    v'        = sum_a pi'(a) Qbar(a)  -- the improved policy's one-step backup;
                `v_prior` = sum_a pi_theta(a) Qbar(a) is recorded beside it

Everything the operator decides is returned as COUNTERS (`search/*`), and the
dial list is DERIVED from `solve`'s signature (`dials_from`), never typed:
an unknown key is a hard failure, because a typed list silently drops a dial
and the arm runs as a control while its readout claims the dial
(`docs/landmines.md`, nine instances). Counters must reach disk before any
dial gets an arm.

What this file does NOT do: choose which decisions get searched (the sampler
is the collector's, plan §4), blend anything into GAE (amendment 1 item 2),
or search depth 2 (`docs/CLEANUP.md` L4; the plan says the depth-2 ceiling is
unmeasured before the fleet and leaves it so).
"""

from __future__ import annotations

import inspect
import math
import time
import typing
from dataclasses import dataclass
from typing import Any, Callable, Sequence

import numpy as np

N_ACTIONS = 10
# The chance-seed key: `seed_base` is `mix(decision_key, world)`; the engine
# then keys each leaf on (seed_base, col, sample). Two odd 64-bit constants,
# splitmix-style, so decision and world never alias.
_K_DECISION = 0x9E3779B97F4A7C15
_K_WORLD = 0xD1B54A32D192ED03


def seed_base(decision_key: int, world: int = 0) -> int:
    """CRN-1's per-(decision, world) base. The row never enters (the engine
    keys the rest on the column and the sample)."""
    x = (int(decision_key) * _K_DECISION + (int(world) + 1) * _K_WORLD) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    x ^= x >> 31
    return x & 0x7FFFFFFFFFFFFFFF


@dataclass
class World:
    """One determinization to search: a root over a (possibly resampled)
    battle. The T-op passes the true state (P3: at training time the true
    world IS a posterior sample); the L-op passes B of them (B1b's resample).
    `node` is a `pkmn_gen1.SearchNode`."""
    node: Any
    weight: float = 1.0


ValueFn = Callable[[dict], np.ndarray]
"""Maps `expand`'s dict (obs, obs2, priv, priv2, terminal, ...) to V per leaf
from the ACTING seat's view on the -1..+1 outcome scale. Terminal rows are
overwritten here (the critic is never asked about a finished battle)."""


def solve(
    worlds: Sequence[World],
    tables: Any,
    seat: str,
    prior: np.ndarray,
    opp_prior: np.ndarray,
    value_fn: ValueFn,
    decision_key: int,
    *,
    cols_k: int = 3,
    chance_s: int = 2,
    tau: float = 1.0,
    max_leaves_per_call: int = 4096,
    root_rule: str = "soft_br",
    rm_iters: int = 2000,
) -> dict[str, Any]:
    """The operator. Returns a dict with:

    `pi` (10,) the improved policy pi' (zero off the mask); `q_row` (10,) Qbar
    per action (NaN off the mask); `v` the root value v' under pi'; `v_prior`
    under pi_theta; `action` argmax pi'; `policy_action` argmax pi_theta;
    `q_cell` (n_rows, k) per world-averaged cell values; `rows`, `cols`; and
    `counters`, the `search/*` scalars:

      search/leaves, search/rows, search/cols, search/worlds, search/ms,
      search/rust_ms, search/override (argmax moved), search/kl_prior
      (KL(pi' || pi_theta) over the mask), search/margin (Qbar[argmax pi'] -
      Qbar[argmax pi_theta]), search/pi_top1, search/prior_top1,
      search/topk_mass (pi_opp mass the k columns cover; 1.0 when the foe
      owes a Pass), search/terminal_frac, search/pass_leaf_frac (leaves where
      WE owe a Pass -- a state the critic never trained on), search/v,
      search/v_prior.

    `prior` and `opp_prior` are (10,) probabilities over the ACTING seat's and
    the FOE's actions, already masked (illegal = 0); the masks are re-read
    from the engine and disagreement is an error, never a silent re-mask.
    """
    if not worlds:
        raise ValueError("solve() needs at least one world")
    if cols_k < 1 or chance_s < 1:
        raise ValueError(f"cols_k {cols_k} and chance_s {chance_s} must be >= 1")
    if not (tau > 0.0 and math.isfinite(tau)):
        raise ValueError(f"tau must be a positive finite float, got {tau!r}")
    if root_rule not in ROOT_RULES:
        raise ValueError(f"root_rule must be one of {ROOT_RULES}, got {root_rule!r}")
    if rm_iters < 1:
        raise ValueError(f"rm_iters must be >= 1, got {rm_iters}")
    seat = str(seat)
    foe = "p2" if seat == "p1" else "p1"
    prior = np.asarray(prior, dtype=np.float64).reshape(N_ACTIONS)
    opp_prior = np.asarray(opp_prior, dtype=np.float64).reshape(N_ACTIONS)
    t0 = time.perf_counter_ns()

    root = worlds[0].node
    if root.over():
        raise ValueError("solve() on a finished battle")
    mask = np.asarray(root.mask(tables, seat), dtype=bool)
    if not mask.any():
        raise ValueError(f"{seat} owes no decision at this root")
    rows = np.flatnonzero(mask).tolist()
    if (prior[~mask] != 0).any() or not (prior[mask] > 0).any():
        raise ValueError("prior must be masked to the engine's legal actions (and not all zero on them)")
    prior_m = prior[mask] / prior[mask].sum()

    foe_mask = np.asarray(root.mask(tables, foe), dtype=bool)
    if foe_mask.any():
        if (opp_prior[~foe_mask] != 0).any() or not (opp_prior[foe_mask] > 0).any():
            raise ValueError("opp_prior must be masked to the foe's legal actions")
        legal_cols = np.flatnonzero(foe_mask)
        order = legal_cols[np.argsort(-opp_prior[legal_cols], kind="stable")]
        cols = order[: min(cols_k, len(order))].tolist()
        q_col = opp_prior[cols] / opp_prior[cols].sum()
        topk_mass = float(opp_prior[cols].sum() / opp_prior[legal_cols].sum())
    else:
        # The foe owes a Pass (it is replacing a fainted mon): one column.
        cols = [-1]
        q_col = np.array([1.0])
        topk_mass = 1.0

    n_rows, n_cols = len(rows), len(cols)
    cells = [(r, c, chance_s) for r in rows for c in cols]
    leaves_per_world = n_rows * n_cols * chance_s
    if leaves_per_world > max_leaves_per_call:
        raise ValueError(
            f"{leaves_per_world} leaves per world > max_leaves_per_call {max_leaves_per_call}: "
            "chunk the cells (the L-op's job), do not raise the cap"
        )

    q_cell = np.zeros((n_rows, n_cols), dtype=np.float64)
    wsum = 0.0
    n_leaves = n_term = n_pass = 0
    rust_ns = 0
    for w_i, world in enumerate(worlds):
        node = world.node
        wm = np.asarray(node.mask(tables, seat), dtype=bool)
        if not np.array_equal(wm, mask):
            raise ValueError(f"world {w_i}: the acting seat's mask differs from world 0's -- "
                             "a resampled world must keep our own side")
        e = node.expand(tables, seat, cells, seed_base(decision_key, w_i), both_views=True)
        n = int(e["n"])
        rust_ns += int(e["rust_ns"])
        v = np.asarray(value_fn(e), dtype=np.float64).reshape(n)
        term = np.asarray(e["terminal"])
        live = term == 0
        v = np.where(live, v, np.where(term == 2, 0.0, term.astype(np.float64)))
        cell_idx = np.asarray(e["cell"])
        acc = np.zeros(n_rows * n_cols, dtype=np.float64)
        np.add.at(acc, cell_idx, v)
        q_cell += float(world.weight) * acc.reshape(n_rows, n_cols) / chance_s
        wsum += float(world.weight)
        n_leaves += n
        n_term += int((~live).sum())
        n_pass += int((np.asarray(e["req_next"])[:, 0] == 0)[live].sum())
    q_cell /= wsum

    q_row_m = q_cell @ q_col                       # (n_rows,) Qbar under pi_opp
    if root_rule == "soft_br":
        # P4: a soft best response to the foe's PRIOR (the default; bit-identical
        # to the pre-dial operator).
        logits = np.log(prior_m) + q_row_m / tau
        pi_m = np.exp(logits - logits.max())
        pi_m /= pi_m.sum()
    else:
        # "regret_matching": the matrix's equilibrium, the AVERAGE strategy of
        # regret matching on the root's payoff matrix (amendment box 4 item 5:
        # the read on G0's positions says greedy is exploitable by -0.052 win-
        # rate against a best reply and this rule halves it under a perfect
        # evaluator; under today's critic every rule is within noise). The
        # prior seeds the first iterate only; tau is unused.
        from rl.search.root_rules import regret_matching
        pi_m = regret_matching(q_cell, rm_iters, prior_m, q_col)[0]
        pi_m = np.maximum(pi_m, 0.0)
        pi_m /= pi_m.sum()
    pi = np.zeros(N_ACTIONS); pi[mask] = pi_m
    q_row = np.full(N_ACTIONS, np.nan); q_row[mask] = q_row_m
    # Ties broken toward the lowest action index, the repo's rule.
    action = int(rows[int(np.argmax(pi_m))])
    policy_action = int(rows[int(np.argmax(prior_m))])
    v_prime = float(pi_m @ q_row_m)
    v_prior = float(prior_m @ q_row_m)
    # xlogy semantics: a zero-mass row (regret matching's average strategy can
    # have them) contributes exactly 0; for pi_m > 0 the arithmetic is the
    # pre-dial expression bit for bit (the max is a no-op there).
    kl = float(np.sum(np.where(pi_m > 0, pi_m * (np.log(np.maximum(pi_m, 1e-300)) - np.log(prior_m)), 0.0)))
    margin = float(q_row[action] - q_row[policy_action])
    ms = (time.perf_counter_ns() - t0) / 1e6
    counters = {
        "search/leaves": float(n_leaves),
        "search/rows": float(n_rows),
        "search/cols": float(n_cols),
        "search/worlds": float(len(worlds)),
        "search/ms": ms,
        "search/rust_ms": rust_ns / 1e6,
        "search/override": float(action != policy_action),
        "search/kl_prior": kl,
        "search/margin": margin,
        "search/pi_top1": float(pi_m.max()),
        "search/prior_top1": float(prior_m.max()),
        "search/topk_mass": topk_mass,
        "search/terminal_frac": n_term / max(n_leaves, 1),
        "search/pass_leaf_frac": n_pass / max(n_leaves, 1),
        "search/v": v_prime,
        "search/v_prior": v_prior,
        "search/root_rule_rm": float(root_rule == "regret_matching"),
    }
    return {
        "pi": pi, "q_row": q_row, "v": v_prime, "v_prior": v_prior,
        "action": action, "policy_action": policy_action,
        "q_cell": q_cell, "rows": rows, "cols": cols, "q_col": q_col,
        "counters": counters,
    }


ROOT_RULES = ("soft_br", "regret_matching")

# ---------------------------------------------------------------------------
# The dial list, derived -- never typed.
# ---------------------------------------------------------------------------

_FIXED = ("worlds", "tables", "seat", "prior", "opp_prior", "value_fn", "decision_key")
DIALS = tuple(
    p for p in inspect.signature(solve).parameters if p not in _FIXED
)
"""Every keyword `solve` accepts beyond its per-call inputs -- the dials a
config may set. Read off the signature at import, so a dial added to `solve`
exists here the same day."""


def dials_from(spec: dict | None) -> dict[str, Any]:
    """A config's `search:` block -> `solve`'s keyword dials. Unknown keys are
    a HARD FAILURE (the typed-list landmine); values are coerced to the
    signature's annotated type so `cols_k: "3"` cannot ride through."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(DIALS))
    if unknown:
        raise ValueError(f"unknown native-search dial(s) {unknown}; the dials are {list(DIALS)}")
    # `from __future__ import annotations` makes `.annotation` a STRING, so the
    # types come from get_type_hints, never from the parameter object.
    hints = typing.get_type_hints(solve)
    out: dict[str, Any] = {}
    for k, v in spec.items():
        ann = hints.get(k)
        if ann is int:
            if isinstance(v, bool) or int(v) != float(v):
                raise ValueError(f"dial {k} must be an integer, got {v!r}")
            out[k] = int(v)
        elif ann is float:
            out[k] = float(v)
        else:
            out[k] = v
    return out


def counter_names() -> tuple[str, ...]:
    """The `search/*` keys `solve` writes, read off one solve of a trivial
    stand-in is impossible without an engine; listed from the docstring's
    contract and asserted equal by tests/test_native_search.py."""
    return (
        "search/leaves", "search/rows", "search/cols", "search/worlds", "search/ms",
        "search/rust_ms", "search/override", "search/kl_prior", "search/margin",
        "search/pi_top1", "search/prior_top1", "search/topk_mass",
        "search/terminal_frac", "search/pass_leaf_frac", "search/v", "search/v_prior",
        "search/root_rule_rm",
    )


# ---------------------------------------------------------------------------
# Value functions over `expand`'s dict.
# ---------------------------------------------------------------------------

def critic_value_fn(agent: Any, *, both_views: bool | None = None) -> ValueFn:
    """The agent's critic as a leaf evaluator. An antisymmetric critic (B2)
    reads [obs | obs2 (| priv | priv2)] -- both views, the block each view
    carries being the other seat's own side, exactly what `expand` renders;
    a plain critic reads obs (| priv). `both_views` defaults to the critic's
    own form."""
    import torch

    anti = bool(getattr(agent, "antisymmetric_critic", False))
    if both_views is None:
        both_views = anti
    priv_dim = int(getattr(agent, "privileged_dim", 0) or 0)
    critic = agent.critic

    def fn(e: dict) -> np.ndarray:
        parts = [e["obs"]]
        if anti:
            parts.append(e["obs2"])
            if priv_dim:
                parts += [e["priv"], e["priv2"]]
        elif priv_dim:
            parts.append(e["priv"])
        x = torch.from_numpy(np.ascontiguousarray(np.concatenate(parts, axis=1)))
        with torch.no_grad():
            v = critic(x).squeeze(-1)
        return v.cpu().numpy()

    return fn

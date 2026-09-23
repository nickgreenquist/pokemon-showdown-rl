"""Root rules for a SIMULTANEOUS-MOVE root (R7, after the 2026-09-23 note).

Showdown turns are simultaneous, so the root of any search here is a
normal-form game: our rows x the foe's columns, entries = the backed-up value
of the joint action (Qbar under chance). `native.solve` reads that matrix as a
BEST RESPONSE to the foe's PRIOR policy (P4: pi' ~ pi * exp(Qbar_row / tau),
Qbar_row = the prior-weighted row mean) -- a mixed policy, but one that
assumes the foe plays its prior. The literature for this class (Lisy,
Kovarik, Lanctot, Bosansky, NeurIPS 2013; Kovarik & Lisy 2015; Becker &
Sunberg 2025) solves the matrix instead: REGRET MATCHING (Hart & Mas-Colell
2000) run on the root's payoff matrix converges to a Nash equilibrium of that
matrix, and the strategy to play is the AVERAGE strategy -- while UCB /
argmax selection at a simultaneous root does not converge even in a
one-stage game (Shafiei et al., cited by Lisy 2013).

This module holds the rules as pure numpy over a payoff matrix so they can be
read on G0's saved positions against the rollout oracle before any of them
enters `native.solve` as a dial (the rows file already holds the full
matrices). Every rule returns a distribution over the ROWS; `evaluate` scores
a row distribution under a column distribution (the foe's prior) AND against
the foe's best reply (min over columns), which is the exploitability read a
best-response rule cannot see. All values are in the matrix's own units
(outcome, +-1); win-rate = outcome / 2.
"""

from __future__ import annotations

import numpy as np


def soft_best_response(q: np.ndarray, prior_rows: np.ndarray, q_col: np.ndarray, tau: float = 1.0) -> np.ndarray:
    """`native.solve`'s root rule: pi' ~ prior * exp(Qbar_row / tau) with
    Qbar_row = q @ q_col (the foe's prior over the columns)."""
    qbar = q @ q_col
    logits = np.log(np.maximum(prior_rows, 1e-300)) + qbar / tau
    p = np.exp(logits - logits.max())
    return p / p.sum()


def pure_best_response(q: np.ndarray, q_col: np.ndarray) -> np.ndarray:
    """The argmax row of Qbar under the foe's prior (ties to the lowest index)."""
    p = np.zeros(q.shape[0])
    p[int(np.argmax(q @ q_col))] = 1.0
    return p


def maximin(q: np.ndarray) -> np.ndarray:
    """The pure row that maximises the worst-case column value."""
    p = np.zeros(q.shape[0])
    p[int(np.argmax(q.min(axis=1)))] = 1.0
    return p


def regret_matching(q: np.ndarray, iters: int = 2000, prior_rows: np.ndarray | None = None,
                    prior_cols: np.ndarray | None = None, seed: int = 0) -> tuple[np.ndarray, np.ndarray, float]:
    """Hart & Mas-Colell regret matching on the zero-sum matrix `q` (row player
    maximises). Both players update simultaneously from their current
    strategies (no sampling: the matrix is known), and the AVERAGE strategies
    are returned with the exploitability gap of the pair -- the 2013 paper's
    output rule ("we always use the empirical frequencies").

    `prior_*` seed the first iterate and the average (uniform when None); they
    do not constrain the fixed point. `iters` 2000 on a 9x9 matrix costs ~1 ms.
    Returns (sigma_rows, sigma_cols, nash_gap) with
    nash_gap = max_row (q @ sigma_cols) - min_col (sigma_rows @ q) >= 0."""
    n, m = q.shape
    pr = np.full(n, 1.0 / n) if prior_rows is None else np.asarray(prior_rows, float) / float(np.sum(prior_rows))
    pc = np.full(m, 1.0 / m) if prior_cols is None else np.asarray(prior_cols, float) / float(np.sum(prior_cols))
    reg_r = np.zeros(n)
    reg_c = np.zeros(m)
    sr, sc = pr.copy(), pc.copy()
    avg_r, avg_c = pr.copy(), pc.copy()
    for t in range(1, iters + 1):
        u_r = q @ sc                    # our payoff per row against their current mix
        u_c = -(sr @ q)                 # their payoff per column (they minimise q)
        reg_r += u_r - float(sr @ u_r)
        reg_c += u_c - float(sc @ u_c)
        pos_r = np.maximum(reg_r, 0.0)
        pos_c = np.maximum(reg_c, 0.0)
        sr = pos_r / pos_r.sum() if pos_r.sum() > 0 else pr
        sc = pos_c / pos_c.sum() if pos_c.sum() > 0 else pc
        avg_r += (sr - avg_r) / (t + 1)
        avg_c += (sc - avg_c) / (t + 1)
    gap = float((q @ avg_c).max() - (avg_r @ q).min())
    return avg_r, avg_c, gap


def evaluate(sigma_rows: np.ndarray, q: np.ndarray, q_col: np.ndarray) -> dict[str, float]:
    """A row distribution's value on `q`: under the foe's prior over columns
    and against the foe's BEST REPLY to it (the exploitability read)."""
    v_cols = sigma_rows @ q                          # value vs each column
    return {"under_prior": float(v_cols @ q_col), "vs_best_reply": float(v_cols.min())}


RULES = ("greedy", "pure_br", "soft_br", "regret_matching", "maximin")


def apply_rule(rule: str, q: np.ndarray, prior_rows: np.ndarray, q_col: np.ndarray, greedy_row: int,
               tau: float = 1.0, rm_iters: int = 2000) -> np.ndarray:
    if rule == "greedy":
        p = np.zeros(q.shape[0]); p[int(greedy_row)] = 1.0
        return p
    if rule == "pure_br":
        return pure_best_response(q, q_col)
    if rule == "soft_br":
        return soft_best_response(q, prior_rows, q_col, tau)
    if rule == "regret_matching":
        return regret_matching(q, rm_iters, prior_rows, q_col)[0]
    if rule == "maximin":
        return maximin(q)
    raise ValueError(f"unknown root rule {rule!r}; one of {RULES}")

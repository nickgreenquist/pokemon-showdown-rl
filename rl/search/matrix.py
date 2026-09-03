"""Depth-1 matrix search: cell fill, L6 mapping law, BR solve, tie-breaks.

Chapter-3 R1 (ch3_search_design_r2.md §3/§6). One decision = one payoff
matrix over (our legal actions) x (opponent L6 classes), filled through
poke-engine one joint turn deep, leaves valued by the checkpoint's own
critic through ShadowBattle -> the one true encoder.

THE L6 -> ENGINE ACTION MAPPING LAW (design §3, verbatim table):
- slot j in {0..3}  -> the determinized active's Move.id for encoder slot j
  (bare id; containment law makes slots det-independent).
- OTHER_MOVE        -> NEVER simulated: q is renormalized over the remaining
  classes and `oppact/other_move_mass` is recorded per decision (a
  determinized mon has exactly 4 moves; no fifth exists).
- SWITCH            -> one bench target PER DETERMINIZATION, uniform over
  legal (unfainted, non-active) bench — declared; uniform averages over bad
  switch-ins, so the search is systematically OPTIMISTIC about our staying
  in (design §9).
Our own actions: mask index 0-5 -> that team slot's bare species id;
6+j -> our active's move j id (poke-env's pinned action mapping). Every
string handed to generate_instructions is derived from the determinized
state, never formatted from a class name (asserted at R2-4).

Locks the ENGINE does not enforce (measured; bridge docstring): a
must-recharge or partially-trapped OPPONENT cannot choose — all its columns
are substituted with the engine action "none" and the substitution counted
(`opp_locked`). Our own locked turns never reach this module (the agent's
placeholder skip). On our force_switch decisions the opponent does not act
simultaneously: single "none" column.

Determinism (design §3, four clauses): D1 node-count budget only (the
watchdog RAISES — no silent fallback-to-policy, DO-NOT-BUILD #16); D2 all
sampling from one caller-supplied numpy Generator keyed per decision
(`decision_rng`); D3 ties matrix score -> policy prior -> lowest action
index; D4 argmax over the renormalized matrix score. Shared
determinizations (MF-13): the same n_det determinizations serve EVERY cell.

Terminal leaves are valued +/-1 (all-fainted side) without asking the
critic; both-fainted values 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from poke_engine import calculate_damage, generate_instructions

from rl.envs.showdown import embed_battle
from rl.search.bridge import BridgeCounters, battle_to_state
from rl.search.determinize import sample_determinization
from rl.search.expansion import expand_leaf
from rl.search.shadow_battle import shadow_battle

# L6 class indices, pinned by rl/networks/opp_action.py (the header contract).
N_L6 = 6
OTHER_MOVE = 4
SWITCH = 5

# Volatiles under which the engine would let the opponent act but the server
# would not (the engine enforces sleep/freeze itself — attested).
_OPP_LOCK_VOLATILES = ("mustrecharge", "partiallytrapped")


class SearchWatchdogError(RuntimeError):
    """Node budget exceeded — raises, never silently falls back to policy."""


@dataclass(frozen=True)
class Dose:
    """node_cap None = not yet frozen (R1-0 spike freezes watchdog constants)."""

    n_det: int
    top_branches: int
    leaf_cap: int
    node_cap: int | None


DOSES = {
    "S": Dose(n_det=1, top_branches=6, leaf_cap=324, node_cap=None),
    "M": Dose(n_det=4, top_branches=6, leaf_cap=1296, node_cap=1500),
    "L": Dose(n_det=16, top_branches=6, leaf_cap=5184, node_cap=None),
}


def decision_rng(
    checkpoint_seed: int, battle_index: int, turn: int, decision_index: int
) -> np.random.Generator:
    """Determinism clause D2: the one Generator, keyed per decision. Tuple-of-
    int hash is stable across processes (ints are unsalted)."""
    key = hash((checkpoint_seed, battle_index, turn, decision_index))
    return np.random.default_rng(key & 0xFFFFFFFFFFFFFFFF)


def our_action_str(battle: Any, action: int) -> str:
    """Mask index -> engine action string (poke-env's pinned action mapping:
    0-5 = team slot switch, 6-9 = active's move slot)."""
    if action < 6:
        return list(battle.team.values())[action].species
    return list(battle.active_pokemon.moves.keys())[action - 6]


def _opp_bench_target(state: Any, rng: np.random.Generator) -> str | None:
    """SWITCH column: uniform over the determinized legal bench."""
    active_i = int(str(state.side_two.active_index)[-1]) if not isinstance(
        state.side_two.active_index, int
    ) else state.side_two.active_index
    bench = [
        mon.id for i, mon in enumerate(state.side_two.pokemon)
        if i != active_i and mon.id.lower() != "none" and mon.hp > 0
    ]
    if not bench:
        return None
    return str(bench[int(rng.integers(len(bench)))])


def _terminal_value(state: Any) -> float | None:
    """+1 opponent wiped, -1 we are wiped, 0 both; None = not terminal."""
    def wiped(side):
        mons = [m for m in side.pokemon if m.id.lower() != "none"]
        return bool(mons) and all(m.hp <= 0 for m in mons)

    ours, theirs = wiped(state.side_one), wiped(state.side_two)
    if ours and theirs:
        return 0.0
    if theirs:
        return 1.0
    if ours:
        return -1.0
    return None


def solve_decision(
    battle: Any,
    mask: np.ndarray,
    q: np.ndarray,
    prior: np.ndarray,
    dose: Dose,
    rng: np.random.Generator,
    critic_fn: Callable[[np.ndarray], np.ndarray],
    type_chart: dict,
    det_fn: Callable[[Any, np.random.Generator], dict] | None = None,
) -> tuple[int, dict]:
    """One depth-1 BR solve. `q` is the oppact head's plain L6 posterior at
    the root; `prior` the masked policy probabilities (tie-break only);
    `critic_fn` maps (N, OBS_DIM) float32 -> (N,) values. `det_fn` defaults
    to RSD sampling; the ONLY other caller is R3's contained oracle-team
    diagnostic, which injects true-team dets from outside rl/search (the
    bridge's FG-4 assert still governs what passes). Returns
    (action index, stats)."""
    rows = [i for i in range(len(mask)) if mask[i]]
    assert rows, "no legal action at a decision point"
    counters = BridgeCounters()
    det_fn = det_fn or sample_determinization
    dets = [det_fn(battle, rng) for _ in range(dose.n_det)]
    states = [battle_to_state(battle, det, counters) for det in dets]

    # --- opponent columns (the L6 law) ---------------------------------
    opp_active_species = battle.opponent_active_pokemon.species
    slot_moves = dets[0]["opponents"][opp_active_species]["moves"]
    opp_locked = any(
        v in states[0].side_two.volatile_statuses for v in _OPP_LOCK_VOLATILES
    )
    force_switch = bool(battle.force_switch)
    if force_switch or opp_locked:
        # no simultaneous opponent choice: one "none" column, full mass
        col_classes: list[int] = [-1]
        col_actions = [["none"] * dose.n_det]
        col_w = np.array([1.0])
        other_move_mass = 0.0
    else:
        col_classes = list(range(len(slot_moves[:4])))
        col_actions = [[mid] * dose.n_det for mid in slot_moves[:4]]
        switch_targets = [_opp_bench_target(s, rng) for s in states]
        if any(t is not None for t in switch_targets):
            col_classes.append(SWITCH)
            col_actions.append([t if t is not None else "none" for t in switch_targets])
        other_move_mass = float(q[OTHER_MOVE])
        w = np.array([float(q[c]) for c in col_classes], dtype=np.float64)
        col_w = (w / w.sum()) if w.sum() > 0 else np.full(len(w), 1.0 / len(w))

    # --- cell fill: shared determinizations, top-B retention ------------
    leaf_obs: list[np.ndarray] = []
    leaf_fixed: list[float] = []  # terminal values; nan = ask the critic
    leaf_at: list[tuple[int, int, int, float]] = []  # (row_i, col_i, det_i, w)
    n_leaves = 0
    retained_mass: list[float] = []  # kept mass per cell BEFORE renorm (Z2'/F-flag)
    turn = int(battle.turn)
    n_expanded = 0
    for ri, action in enumerate(rows):
        a_str = our_action_str(battle, action)
        for ci in range(len(col_classes)):
            for di, state in enumerate(states):
                b_str = col_actions[ci][di]
                branches = generate_instructions(state, a_str, b_str)
                branches = sorted(branches, key=lambda b: -b.percentage)
                kept = branches[: dose.top_branches]
                total = sum(b.percentage for b in kept)
                retained_mass.append(total / 100.0)
                if total <= 0:
                    continue
                try:  # max-damage rolls for the 2-point expansion (§2.1)
                    dmg = calculate_damage(state, a_str, b_str, True)
                except (KeyboardInterrupt, SystemExit):
                    raise  # interrupts propagate (F-14)
                except BaseException:  # engine faults INCLUDING Rust panics: poke_engine is
                    # PyO3, and a panic surfaces as pyo3_runtime.PanicException, which derives
                    # from BaseException, not Exception (F-14 review). The module is created
                    # lazily on first panic and is not importable, so it cannot be named here;
                    # `except Exception` would let a panic kill the search seat's battle.
                    dmg = None
                for br in kept:
                    leaf = state.apply_instructions(br)
                    for lv, w in expand_leaf(state, leaf, dmg):
                        n_leaves += 1
                        n_expanded += int(lv is not leaf)
                        if dose.node_cap is not None and n_leaves > dose.node_cap:
                            raise SearchWatchdogError(
                                f"{n_leaves} leaves > node cap {dose.node_cap} "
                                f"(dose n_det={dose.n_det}, {len(rows)} rows, "
                                f"{len(col_classes)} cols)"
                            )
                        tv = _terminal_value(lv)
                        if tv is None:
                            leaf_obs.append(
                                embed_battle(shadow_battle(lv, turn + 1), type_chart)
                            )
                            leaf_fixed.append(np.nan)
                        else:
                            leaf_obs.append(None)
                            leaf_fixed.append(tv)
                        leaf_at.append((ri, ci, di, w * br.percentage / total))

    # --- batched leaf valuation ----------------------------------------
    values = np.array(leaf_fixed, dtype=np.float64)
    need = [i for i, o in enumerate(leaf_obs) if o is not None]
    if need:
        batch = np.stack([leaf_obs[i] for i in need]).astype(np.float32)
        values[need] = np.asarray(critic_fn(batch), dtype=np.float64)

    # --- EV matrix + BR solve (D3/D4) ----------------------------------
    ev_cell = np.zeros((len(rows), len(col_classes), dose.n_det))
    for (ri, ci, di, w), v in zip(leaf_at, values):
        ev_cell[ri, ci, di] += w * v
    ev_matrix = ev_cell.mean(axis=2)  # (rows, cols)
    row_ev = ev_matrix @ col_w
    order = sorted(
        range(len(rows)),
        key=lambda i: (-row_ev[i], -float(prior[rows[i]]), rows[i]),
    )
    best = rows[order[0]]
    stats = {
        "search/leaves": n_leaves,
        "search/rows": len(rows),
        "search/cols": len(col_classes),
        "search/n_det": dose.n_det,
        "search/opp_locked": int(opp_locked),
        "search/force_switch": int(force_switch),
        "oppact/other_move_mass": other_move_mass,
        "search/row_ev": {int(rows[i]): float(row_ev[i]) for i in range(len(rows))},
        "search/chosen": int(best),
        "search/policy_argmax": int(max(rows, key=lambda a: prior[a])),
        "search/retained_mass_mean": float(np.mean(retained_mass)) if retained_mass else 1.0,
        "search/expanded_leaves": n_expanded,
        "search/ev_matrix": ev_matrix.tolist(),
        "search/col_classes": list(col_classes),
        "bridge/unmapped_effects": dict(counters.unmapped_effects),
    }
    return best, stats

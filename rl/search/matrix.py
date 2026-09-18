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

D5, the MARGIN GATE (2026-09-10, docs/search_relook/MARGIN_SELECTOR.md) —
OPTIONAL and OFF by default. `margin_delta=None` is the D4 behaviour
byte-for-byte (no extra work, no extra stats key). Any float delta makes
D4's argmax `a_s` a CANDIDATE that must beat the policy's own argmax
`a_pi` by more than delta on the same row_ev scale:

    play a_s iff row_ev[a_s] - row_ev[a_pi] > delta, else play a_pi

so delta=0.0 is D4 with ties conceded to the policy and delta=inf is the
greedy policy exactly. Motivation: Wang 2024 puts the policy prior INSIDE
the selection rule and decides by max VISIT COUNT rather than max Q,
"because less-visited actions may have higher variance in their Q
estimates" (p.22; docs/prior_work/WANG_SEARCH_DEEP_READ.md §2). Our D4 is
a hard argmax over single-digit-sample cell means and overrides a
0.789-strength policy on 72.8% of decisions while losing 6.8 points
(S3_READOUT.md). The gate is the cheap, retraining-free analogue of his
variance aversion: it is a CONFIDENCE THRESHOLD on the search, not a prior
inside the tree policy.

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
from rl.search.shadow_battle import PublicView, shadow_battle

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
    # XL added 2026-09-11 for the BUDGET LADDER (maintainer: "greedy / trivial /
    # shallow / deep"). It is 4x L on the SAME axis every other dose moves —
    # n_det, the number of sampled opponent teams — because that is the axis the
    # code has; DEPTH IS NOT A DIAL HERE (no depth-2 exists). So XL buys a
    # lower-variance estimate of the SAME one-ply quantity, not a deeper one.
    # Priced against Foul Play's own measured cost in this harness: M ~2.4 s per
    # battle ~ FP@20, L ~9.3 ~ FP@100, XL ~37 ~ FP@500. leaf_cap scales with
    # n_det exactly as S->M->L do (324/1296/5184 = 324 * 4^k).
    "XL": Dose(n_det=64, top_branches=6, leaf_cap=20736, node_cap=None),
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


def _leaf_our_moves(state: Any, k: int) -> list[str]:
    """Legal move ids for US at a child state: pp left, not disabled. Switches
    are skipped on purpose -- this probe asks whether looking one more ply at
    the ATTACK lines changes the root choice, and switches multiply the branch
    factor without being the thing in question."""
    side = state.side_one
    # `active_index` comes back from pyo3 as a STRING ('0'..'5'), not an int,
    # so `side.pokemon[side.active_index]` raises TypeError. Wrapped in a bare
    # `except: return []` that cost a whole void D2 arm -- 1572 decisions, zero
    # grandchildren, a win rate that looked like a result. Same unwrap as
    # matrix.py's opponent side and shadow_battle.py.
    ai = side.active_index
    active = side.pokemon[int(str(ai)[-1]) if not isinstance(ai, int) else ai]
    out = [m.id for m in active.moves
           if getattr(m, "pp", 0) > 0 and not getattr(m, "disabled", False)
           and m.id and m.id.lower() != "none"]
    return out[:k]


def _leaf_opp_moves(state: Any, col_action: str, k: int) -> list[str]:
    """The opponent's candidate replies at a grandchild-parent state.

    The COLUMN ACTION ALWAYS COMES FIRST and is always present, so `opp_k=1`
    reproduces the pinned-opponent backup exactly and every banked depth-2
    number stays reproducible. Beyond it: the opponent's own legal attacks,
    same filter as `_leaf_our_moves` on the other side. Switches are skipped
    for the same reason they are skipped for us -- they multiply the branch
    factor without being the thing in question.

    A SWITCH column has a real consequence here that `opp_k=1` cannot see: the
    opponent already switched during the root ply, so repeating "switch N" at
    ply 2 is illegal, `generate_instructions` raises and that leaf produced
    ZERO grandchildren. With `opp_k>1` those leaves get their real replies.
    """
    out = [col_action]
    if k <= 1:
        return out
    side = state.side_two
    ai = side.active_index
    active = side.pokemon[int(str(ai)[-1]) if not isinstance(ai, int) else ai]
    for m in active.moves:
        if len(out) >= k:
            break
        mid = m.id
        if (getattr(m, "pp", 0) > 0 and not getattr(m, "disabled", False)
                and mid and mid.lower() != "none" and mid not in out):
            out.append(mid)
    return out


def _look_further(values, need, leaf_states, col_actions, leaf_at, turn,
                  col_views, critic_fn, type_chart, depth2,
                  heuristic=None, root_evals=None):
    """SELECTIVE DEPTH. Replace a leaf's critic value with an N-PLY lookahead:
    from the leaf state, play our legal moves against the opponent's reply,
    repeat for `plies`, and back the values up to the leaf.

    THE BACK-UP IS THE WHOLE EXPERIMENT, and this docstring got it wrong once.
    Two modes, selected by `opp_k`:

      opp_k = 1  (DEFAULT, and what every arm before 2026-09-18 ran)
          The opponent is PINNED to the column the root assigned it, we take a
          MAX over our reply sequences, and that is all. The original argument
          for it -- "between the leaf and the horizon only WE choose, so the
          best sequence is the best endpoint" -- is sound GIVEN the pin, and
          the pin is the modelling error rather than the max.
          **It is OPTIMISTIC, and the claim that it "biases every row the same
          way" is FALSE.** Rows differ in how many replies they have and how
          good the best one is, so a max over k noisy leaf estimates inflates
          exactly the rows with the most escape hatches -- which are the rows
          the root then overrides into. MEASURED (RESULTS §24): depth 2 is
          indistinguishable from depth 1 at a tight gate (-0.0007) and -0.047
          at 2.57 se WORSE once the gate is open; opening the gate costs
          depth-2 0.052 against depth-1's 0.006. A tight gate was discarding
          the inflated rows; an open gate plays them.

      opp_k > 1  (the fix, IDEAS 2.10)
          The opponent answers each of our replies with up to `opp_k` moves
          (its column action first) and we take the MIN over its answers
          before the MAX over ours -- the standard minimax back-up, and the
          missing half of the asymmetry above. Cost multiplies by `opp_k`.

    At `plies=1` -- what every arm has ever run -- min-over-answers then
    max-over-ours IS minimax. At `plies>1` the min is taken over the
    opponent's whole PLAN rather than ply by ply, which is strictly more
    pessimistic than minimax; say so if a multi-ply arm is ever read.

    The opponent's ROOT distribution has not been dropped in either mode --
    `col_w = q` re-weights these values at the root, the same
    expectation-under-q the depth-1 `row_ev` takes.

    Selective on purpose -- `our_k` moves per ply, a hard `cap` on states --
    because EXHAUSTIVE depth-2 costs ~leaves^2, and that cost is the entire
    reason the engine port exists. Foul Play gets depth by being selective,
    not by being fast, and this is the cheapest imitation.
    """
    our_k = int(depth2.get("our_k", 3))
    cap = int(depth2.get("cap", 6000))
    plies = int(depth2.get("plies", 1))
    opp_k = int(depth2.get("opp_k", 1))
    # (state, origin leaf index, column index, determinization, PATH).
    # `path` names one sequence of OUR replies; every opponent answer along
    # that sequence shares it. The back-up is max-over-paths of
    # min-over-that-path, so opp_k=1 (one member per path) is bit-identical to
    # the pinned-opponent max this function shipped with.
    frontier = [(leaf_states[i], i, leaf_at[i][1], leaf_at[i][2], (i,))
                for i in need if leaf_states[i] is not None]
    fixed: list[tuple[int, tuple, float]] = []   # (origin leaf, path, value)
    expanded = 0
    opp_reply_count = 0
    opp_reply_states = 0
    for ply in range(plies):
        nxt = []
        for st, i, ci, di, path in frontier:
            if expanded >= cap:
                nxt.append((st, i, ci, di, path))   # out of budget: keep it a leaf
                continue
            b_strs = _leaf_opp_moves(st, col_actions[ci][di], opp_k)
            opp_reply_count += len(b_strs)
            opp_reply_states += 1
            grew = False
            for ai_, a_str in enumerate(_leaf_our_moves(st, our_k)):
                if expanded >= cap:
                    break
                sub = path + (ai_,)
                for b_str in b_strs:
                    if expanded >= cap:
                        break
                    try:
                        brs = generate_instructions(st, a_str, b_str)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException:
                        continue
                    if not brs:
                        continue
                    br = max(brs, key=lambda b: b.percentage)
                    try:
                        gc = st.apply_instructions(br)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except BaseException:
                        continue
                    grew = True
                    expanded += 1
                    tv = _terminal_value(gc)
                    if tv is not None:
                        fixed.append((i, sub, tv))
                    else:
                        nxt.append((gc, i, ci, di, sub))
            if not grew:   # nothing legal from here: it stays a leaf
                nxt.append((st, i, ci, di, path))
        frontier = nxt
        if not frontier:
            break
    if not (frontier or fixed):
        return values, {"depth2/grandchildren": 0.0, "depth2/leaves_deepened": 0.0,
                        "depth2/leaves_unexpanded": float(len(frontier)),
                        "depth2/opp_k": float(opp_k),
                        "depth2/opp_replies_mean": 0.0,
                        "depth2/minimax_drop": 0.0}

    # scored[(leaf, path)] -> list of values; the min over a path is taken
    # AFTER every member of it is scored, so a terminal answer and an
    # evaluated one compete on the same footing.
    scored: dict[tuple, list[float]] = {}

    def _put(i, path, v):
        scored.setdefault((i, path), []).append(float(v))

    for i, path, v in fixed:
        _put(i, path, v)
    # A state that was NEVER EXPANDED is not a lookahead and must keep the
    # value it already has. It used to be re-embedded at `turn + 1 + plies`
    # and re-scored, so merely TURNING DEPTH ON moved an un-deepenable leaf's
    # value by whatever the encoder does with a shifted turn count -- pure
    # noise, attributed to depth. `len(path) == 1` is exactly "still the
    # original leaf": `path` starts at `(i,)` and gains one element per
    # expansion. Every arm before 2026-09-18 carries the artifact; it is
    # disclosed rather than retro-fitted, and it is one more reason a depth
    # number from the matrix vehicle must be re-measured (IDEAS 2.10).
    unexpanded = sum(1 for e in frontier if len(e[4]) == 1)
    frontier = [e for e in frontier if len(e[4]) > 1]
    if frontier and heuristic is not None:
        # The DEEPER ply must be scored by the SAME evaluator as the shallower
        # one, or the depth comparison silently becomes an evaluator
        # comparison. Grandchildren are differenced against the root of their
        # own determinization, exactly as the leaves are.
        from rl.search import fp_eval

        for st, i, _ci, di, path in frontier:
            _put(i, path, fp_eval.leaf_value(st, root_evals[di]))
    elif frontier:
        obs, at = [], []
        for st, i, ci, _di, path in frontier:
            try:
                obs.append(embed_battle(
                    shadow_battle(st, turn + 1 + plies, view=col_views[ci]),
                    type_chart))
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                continue
            at.append((i, path))
        if obs:
            gv = np.asarray(
                critic_fn(np.stack(obs).astype(np.float32)), dtype=np.float64)
            for j, (i, path) in enumerate(at):
                _put(i, path, gv[j])

    best: dict[int, float] = {}
    best_optimistic: dict[int, float] = {}
    for (i, _path), vs in scored.items():
        v = min(vs)                      # the opponent picks inside the path
        if i not in best or v > best[i]:
            best[i] = v                  # we pick between paths
        vo = max(vs)
        if i not in best_optimistic or vo > best_optimistic[i]:
            best_optimistic[i] = vo
    out = values.copy()
    for i, v in best.items():
        out[i] = v
    return out, {
        "depth2/grandchildren": float(expanded),
        "depth2/leaves_deepened": float(len(best)),
        "depth2/plies": float(plies),
        "depth2/opp_k": float(opp_k),
        "depth2/paths": float(len(scored)),
        "depth2/leaves_unexpanded": float(unexpanded),
        "depth2/opp_replies_mean": (
            float(opp_reply_count / opp_reply_states) if opp_reply_states else 0.0),
        # how much the min-over-answers actually moved the backed-up value:
        # 0.0 whenever opp_k == 1, and the size of the correction otherwise.
        "depth2/minimax_drop": float(np.mean(
            [best_optimistic[i] - best[i] for i in best])) if best else 0.0,
        # NEVER let a NaN counter reach disk: `best` is empty whenever every
        # leaf was unexpanded, and np.mean([]) is NaN, which a readout then
        # prints as a number.
        "depth2/mean_shift": (
            float(np.mean([abs(out[i] - values[i]) for i in best])) if best else 0.0),
    }


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
    leaf_view: PublicView | None = None,
    margin_delta: float | None = None,
    depth2: dict | None = None,
    bcts: dict | None = None,
    root_v: float | None = None,
    heuristic: dict | None = None,
) -> tuple[int, dict]:
    """One depth-1 BR solve. `q` is the oppact head's plain L6 posterior at
    the root; `prior` the masked policy probabilities (tie-break only);
    `critic_fn` maps (N, OBS_DIM) float32 -> (N,) values. `det_fn` defaults
    to RSD sampling; the ONLY other caller is R3's contained oracle-team
    diagnostic, which injects true-team dets from outside rl/search (the
    bridge's FG-4 assert still governs what passes).

    `leaf_view` is the det_blind option (docs/search_relook/DET_BLIND.md):
    the ROOT battle's opponent-side `PublicView`, handed to every leaf's
    `shadow_battle` so the leaf is encoded at the live encoder's information
    boundary rather than the determinizer's. None = the as-is leaf encoding,
    byte-for-byte.

    `margin_delta` is D5, the margin gate (module docstring;
    docs/search_relook/MARGIN_SELECTOR.md). None = D4 alone, byte-for-byte:
    nothing is computed and NO new stats key appears, so a golden digest
    over this function's full output is unchanged. A float delta (>= 0.0,
    `inf` allowed) plays D4's argmax only when it beats the policy's own
    argmax by MORE than delta on the row_ev scale, and adds the four
    `search/margin_delta`, `search/search_argmax`, `search/margin`,
    `search/overrode` keys. `search/chosen` is always the action PLAYED.

    Returns (action index, stats)."""
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

    # det_blind: one view per COLUMN. A column's opponent action is the same
    # move id across determinizations (the containment law makes the active's
    # four slots det-independent), so the leaf's information set differs only
    # by which move the transition revealed. A SWITCH column names a species
    # and a locked/force-switch column names "none": neither reveals a move,
    # and the membership test against the active's own four slots is what
    # keeps a species that happens to spell a move id out of the set.
    if leaf_view is None:
        col_views: list[PublicView | None] = [None] * len(col_classes)
    else:
        own_moves = set(slot_moves[:4])
        col_views = [
            leaf_view.plus_move(opp_active_species, col_actions[ci][0])
            if col_actions[ci][0] in own_moves else leaf_view
            for ci in range(len(col_classes))
        ]

    # --- cell fill: shared determinizations, top-B retention ------------
    leaf_obs: list[np.ndarray] = []
    leaf_states: list[Any] = []   # depth2 probe: the engine state behind each leaf
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
                        keep_state = depth2 is not None or heuristic is not None
                        leaf_states.append(lv if keep_state else None)
                        tv = _terminal_value(lv)
                        if tv is None:
                            # With the heuristic vehicle the ENCODER IS NOT RUN:
                            # it exists only to feed a critic we are not asking.
                            # That is most of the per-decision cost (the tree
                            # probe measured 99 of 280 ms in embed_battle), so
                            # the cost difference between the two vehicles is a
                            # FINDING to report, never a confound to hide.
                            leaf_obs.append(None if heuristic is not None
                                            else embed_battle(
                                shadow_battle(lv, turn + 1, view=col_views[ci]),
                                type_chart,
                            ))
                            leaf_fixed.append(np.nan)
                        else:
                            leaf_obs.append(None)
                            leaf_fixed.append(tv)
                        leaf_at.append((ri, ci, di, w * br.percentage / total))

    # --- batched leaf valuation ----------------------------------------
    values = np.array(leaf_fixed, dtype=np.float64)
    h_stats: dict[str, float] = {}
    if heuristic is not None:
        # FOUL PLAY'S OWN VEHICLE (rl/search/fp_eval.py): every non-terminal
        # leaf is scored `2*sigmoid(k*(evaluate(leaf) - evaluate(root))) - 1`,
        # differenced against the root of ITS OWN determinization. Terminal
        # leaves keep the true +1/0/-1 that `_terminal_value` already fixed,
        # which is what `rollout` does when `battle_is_over`.
        from rl.search import fp_eval

        need = [i for i, v in enumerate(leaf_fixed) if np.isnan(v)]
        root_evals = [fp_eval.evaluate(st) for st in states]
        if need:
            values[need] = fp_eval.leaf_values(
                [leaf_states[i] for i in need], root_evals,
                [leaf_at[i][2] for i in need],
            )
        # the counter reaches disk before the dial gets an arm (the standing
        # rule after 2026-09-11's VOID probe): an unfired vehicle and an
        # ineffective one must never print the same number.
        h_stats = {
            "heuristic/leaves_scored": float(len(need)),
            "heuristic/root_eval_mean": float(np.mean(root_evals)) if root_evals else 0.0,
            "heuristic/value_mean": float(np.mean(values[need])) if need else 0.0,
            "heuristic/value_absmean": float(np.mean(np.abs(values[need]))) if need else 0.0,
        }
    else:
        need = [i for i, o in enumerate(leaf_obs) if o is not None]
        if need:
            batch = np.stack([leaf_obs[i] for i in need]).astype(np.float32)
            values[need] = np.asarray(critic_fn(batch), dtype=np.float64)
    d2_stats: dict[str, float] = {}
    if depth2 is not None and need:
        values, d2_stats = _look_further(
            values, need, leaf_states, col_actions, leaf_at, turn, col_views,
            critic_fn, type_chart, depth2,
            heuristic=heuristic,
            root_evals=(root_evals if heuristic is not None else None),
        )

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
    # `policy_argmax` is the action the GREEDY agent would play: argmax over
    # LEGAL actions of the same masked policy the SearchAgent wraps (softmax
    # is monotone, so this is argmax of the masked logits), ties to the
    # lowest index — exactly what `PPOAgent.act(deterministic=True)` does
    # and exactly what the placeholder-skip path in agent.py returns.
    policy_argmax = int(max(rows, key=lambda a: prior[a]))

    # --- D5: the MARGIN GATE (optional; MARGIN_SELECTOR.md) --------------
    # None short-circuits to nothing: no arithmetic, no stats key, so the
    # default path is byte-identical to the pre-2026-09-10 D4 behaviour.
    gate: dict[str, Any] = {}
    if bcts is not None and root_v is not None:
        # BCTS: the margin is DERIVED per decision, not a constant.
        #
        # Hallak, Dalal, Dalton, Frosio, Mannor & Chechik, "Improve Agents
        # without Retraining: Parallel Tree Search with Off-Policy Correction"
        # (NeurIPS 2021, arXiv:2107.01715). Their Assumption 1: a leaf value
        # whose FIRST action was the policy's is N(Q, sigma_o^2), any other is
        # N(Q, sigma_e^2), with sigma_o < sigma_e -- measured at 1.5-2x on
        # Atari. A max over higher-variance estimates is biased UP, so the
        # search systematically over-rates exactly the actions the policy
        # would not take, and the gap (their Lemma 3.4) is
        #     sqrt(2 log A) * (sigma_e*sqrt(d) - sigma_o*sqrt(d-1))
        # which GROWS with depth. That is the shape of our own dose-response:
        # -0.039 at one extra ply, -0.094 at two, under a CONSTANT delta 0.10
        # that cannot grow to meet it.
        #
        # Their Prop. 3.6 makes the estimate free: var_{n=2}[Q] = delta^2/2
        # where delta is a Bellman error, and "at depth 1 we have access to
        # delta(s0,a) of all a in A without additional computation". Here
        # row_ev[a] IS the one-ply backup and root_v is V(s0), so
        # delta(s0,a) = row_ev[a] - root_v costs nothing.
        #
        # A is the number of LEGAL actions THIS TURN, which in Pokemon varies
        # with forced switches and disabled moves -- the gate should be wider
        # when more actions compete, and this gets that for free.
        #
        # kappa is the one swept scale. The paper is explicit that it needs
        # one: "we found that multiplying its correction term ... by a
        # constant that we sweep over can improve performance". kappa=0 is the
        # ungated hard argmax; large kappa is the policy.
        kappa = float(bcts.get("kappa", 1.0))
        d = float(bcts.get("d", 1))
        pos = {a: i for i, a in enumerate(rows)}
        A = max(len(rows), 2)          # log A must be > 0
        errs = np.abs(row_ev - float(root_v))
        i_pi = pos[policy_argmax]
        d_o = float(errs[i_pi])
        others = [errs[i] for i in range(len(rows)) if i != i_pi]
        d_e = float(np.mean(others)) if others else d_o
        pen = kappa * (
            np.sqrt(np.log(A)) * (d_e * np.sqrt(d) - d_o * np.sqrt(d - 1.0))
            - (d_e - d_o) / np.sqrt(8.0)
        )
        # A NEGATIVE penalty would reward leaving the policy, which inverts
        # the correction; the paper's term is a bias to subtract, so it floors
        # at zero.
        pen = float(max(pen, 0.0))
        scored = row_ev - pen * np.array(
            [0.0 if a == policy_argmax else 1.0 for a in rows])
        order2 = sorted(range(len(rows)),
                        key=lambda i: (-scored[i], -float(prior[rows[i]]), rows[i]))
        search_argmax = best
        best = rows[order2[0]]
        gate = {
            "bcts/kappa": kappa,
            "bcts/penalty": pen,
            "bcts/delta_off": d_e,
            "bcts/delta_on": d_o,
            "bcts/ratio": float(d_e / d_o) if d_o > 1e-9 else float("nan"),
            "bcts/n_legal": float(len(rows)),
            "search/search_argmax": int(search_argmax),
            "search/margin": float(
                row_ev[pos[search_argmax]] - row_ev[pos[policy_argmax]]),
            "search/overrode": bool(best != policy_argmax),
        }
    elif margin_delta is not None:
        delta = float(margin_delta)
        assert delta == delta and delta >= 0.0, f"margin_delta {margin_delta!r}"
        pos = {a: i for i, a in enumerate(rows)}
        search_argmax = best
        margin = float(row_ev[pos[search_argmax]] - row_ev[pos[policy_argmax]])
        # STRICT >: at delta 0.0 an exact tie is conceded to the policy.
        # (D3 already resolves row_ev ties by prior then index, so a tie
        # between a_s and a_pi forces a_s == a_pi — see MARGIN_SELECTOR.md
        # §3 — but the strict comparison is what makes delta=inf exactly
        # greedy, and it is stated rather than relied upon.)
        best = search_argmax if margin > delta else policy_argmax
        gate = {
            "search/margin_delta": delta,
            "search/search_argmax": int(search_argmax),
            "search/margin": margin,
            "search/overrode": bool(best != policy_argmax),
        }
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
        "search/policy_argmax": policy_argmax,
        "search/retained_mass_mean": float(np.mean(retained_mass)) if retained_mass else 1.0,
        "search/expanded_leaves": n_expanded,
        "search/ev_matrix": ev_matrix.tolist(),
        "search/col_classes": list(col_classes),
        "bridge/unmapped_effects": dict(counters.unmapped_effects),
        **gate,
    }
    if depth2 is not None:
        stats.update(d2_stats)
    if heuristic is not None:
        stats.update(h_stats)
    return best, stats

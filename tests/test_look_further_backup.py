"""IDEAS 2.10 -- what does `_look_further` BACK UP, and does the fix bite?

`rl/search/matrix.py::_look_further` shipped with a max over OUR replies and
the opponent PINNED to its column. Its docstring defended that with "it biases
every row the same way"; RESULTS §24 measured that it does not -- depth 2 is
-0.047 at 2.57 se WORSE than depth 1 once the gate is open, because a max over
k noisy leaf estimates inflates exactly the rows with the most escape hatches,
and those are the rows the root then overrides into.

`opp_k` is the fix. These tests pin BOTH halves: that `opp_k=1` still
reproduces the old backup EXACTLY (every banked depth-2 number stays
reproducible, and the default is unchanged), and that `opp_k>1` takes the min
over the opponent's answers before the max over ours. The escape-hatch bias is
constructed explicitly in `test_the_escape_hatch_bias_is_real...` so the thing
the fix exists for is measured here rather than asserted in prose.
"""
import numpy as np
import pytest

from rl.search import matrix as M


class FakeMove:
    def __init__(self, mid):
        self.id, self.pp, self.disabled = mid, 8, False


class FakeMon:
    def __init__(self, hp=100, moves=(), mid="pikachu"):
        self.hp, self.id = hp, mid
        self.moves = [FakeMove(m) for m in moves]


class FakeSide:
    def __init__(self, mons, active_index=0):
        self.pokemon, self.active_index = mons, active_index


class FakeState:
    """Carries a LABEL: the sequence of (our move, their move) played to get
    here. `apply_instructions` extends it, so a grandchild's identity -- and
    therefore its value -- is fully determined by the path that reached it."""

    def __init__(self, label, our_moves, their_moves, hp=(100, 100)):
        self.label = label
        self._our, self._their = list(our_moves), list(their_moves)
        self.side_one = FakeSide([FakeMon(hp[0], our_moves)])
        self.side_two = FakeSide([FakeMon(hp[1], their_moves)])

    def apply_instructions(self, br):
        return FakeState(self.label + (br.step,), self._our, self._their,
                         hp=br.hp)


class FakeBranch:
    def __init__(self, step, hp=(100, 100)):
        self.step, self.hp, self.percentage = step, hp, 100.0


def gen_ok(monkeypatch, terminal=()):
    """`generate_instructions` that always succeeds; `terminal` names
    (our_move, their_move) pairs whose child is a WIPE for us."""
    def g(st, a, b):
        hp = (0, 100) if (a, b) in terminal else (100, 100)
        return [FakeBranch((a, b), hp=hp)]
    monkeypatch.setattr(M, "generate_instructions", g)


def critic_from(values, default=0.0):
    """A critic keyed by the grandchild's LABEL, wired through the same
    `embed_battle`/`shadow_battle` seam the real code uses."""
    seen = []

    def embed(battle, chart):
        seen.append(battle)
        return np.zeros(4, dtype=np.float32)

    def shadow(st, turn, view=None):
        return st.label

    def critic(batch):
        return np.array([values.get(lbl, default) for lbl in seen[-len(batch):]],
                        dtype=np.float64)

    return embed, shadow, critic


def run(monkeypatch, *, our_moves, their_moves, col_action, values,
        opp_k=1, our_k=3, terminal=(), leaf_values=(0.0,)):
    gen_ok(monkeypatch, terminal=terminal)
    embed, shadow, critic = critic_from(values)
    monkeypatch.setattr(M, "embed_battle", embed)
    monkeypatch.setattr(M, "shadow_battle", shadow)
    st = FakeState((), our_moves, their_moves)
    vals = np.array(leaf_values, dtype=np.float64)
    return M._look_further(
        vals, [0], [st], [[col_action]], [(0, 0, 0, 1.0)], 5, [None],
        critic, None, {"our_k": our_k, "cap": 6000, "plies": 1, "opp_k": opp_k})


# --------------------------------------------------------------- the default
def test_opp_k_1_is_the_old_max_over_our_replies(monkeypatch):
    """The DEFAULT must not move: every banked depth-2 arm ran this path."""
    out, stats = run(
        monkeypatch, our_moves=("a", "b", "c"), their_moves=("x", "y"),
        col_action="x",
        values={(("a", "x"),): 0.9, (("b", "x"),): 0.3, (("c", "x"),): -0.5})
    assert out[0] == pytest.approx(0.9)          # max over our three replies
    assert stats["depth2/grandchildren"] == 3.0  # one per reply, opponent pinned
    assert stats["depth2/opp_k"] == 1.0
    assert stats["depth2/opp_replies_mean"] == pytest.approx(1.0)
    assert stats["depth2/minimax_drop"] == pytest.approx(0.0), (
        "with one answer per path, min and max coincide by construction")


def test_opp_k_defaults_to_one_when_the_config_omits_it(monkeypatch):
    gen_ok(monkeypatch)
    embed, shadow, critic = critic_from({(("a", "x"),): 0.7})
    monkeypatch.setattr(M, "embed_battle", embed)
    monkeypatch.setattr(M, "shadow_battle", shadow)
    st = FakeState((), ("a",), ("x", "y"))
    out, stats = M._look_further(
        np.array([0.0]), [0], [st], [["x"]], [(0, 0, 0, 1.0)], 5, [None],
        critic, None, {"our_k": 3, "cap": 6000, "plies": 1})   # NO opp_k
    assert stats["depth2/opp_k"] == 1.0
    assert out[0] == pytest.approx(0.7)


# ------------------------------------------------------------------ the fix
def test_opp_k_2_mins_over_the_opponents_answers_before_maxing_over_ours(monkeypatch):
    """Reply `a` is a trap: superb against the pinned column, refuted by the
    opponent's other move. `b` is steady. The old backup plays the trap."""
    values = {
        (("a", "x"),): 0.9, (("a", "y"),): -0.8,
        (("b", "x"),): 0.3, (("b", "y"),): 0.2,
    }
    out1, _ = run(monkeypatch, our_moves=("a", "b"), their_moves=("x", "y"),
                  col_action="x", values=values, opp_k=1)
    assert out1[0] == pytest.approx(0.9), "the optimistic backup takes the trap"

    out2, stats = run(monkeypatch, our_moves=("a", "b"), their_moves=("x", "y"),
                      col_action="x", values=values, opp_k=2)
    assert out2[0] == pytest.approx(0.2), "max(min(0.9,-0.8), min(0.3,0.2))"
    assert stats["depth2/opp_replies_mean"] == pytest.approx(2.0)
    assert stats["depth2/paths"] == 2.0, "one path per OUR reply, not per leaf"
    assert stats["depth2/minimax_drop"] == pytest.approx(0.7), (
        "the correction is reported, not silent: 0.9 optimistic - 0.2 fixed")


def test_the_escape_hatch_bias_is_real_and_opp_k_removes_it(monkeypatch):
    """THE MECHANISM §24 NAMES, constructed. Two leaves whose TRUE value is the
    same; one has more replies. Under a max, more replies means a higher
    number -- a bias that is NOT common to both rows, which is what makes it
    change the root's argmax."""
    # every reply is worth 0.2 against the pinned column and -0.6 against the
    # refutation, so the honest value of both leaves is identical.
    vals = {}
    for m in ("a", "b", "c", "d"):
        vals[((m, "x"),)] = 0.2 + 0.05 * "abcd".index(m)   # noisy, mean 0.275
        vals[((m, "y"),)] = -0.6
    few, _ = run(monkeypatch, our_moves=("a", "b"), their_moves=("x", "y"),
                 col_action="x", values=vals, opp_k=1, our_k=4)
    many, _ = run(monkeypatch, our_moves=("a", "b", "c", "d"),
                  their_moves=("x", "y"), col_action="x", values=vals,
                  opp_k=1, our_k=4)
    assert many[0] > few[0], (
        "the optimistic backup rewards a leaf for HAVING more replies")

    few_fix, _ = run(monkeypatch, our_moves=("a", "b"), their_moves=("x", "y"),
                     col_action="x", values=vals, opp_k=2, our_k=4)
    many_fix, _ = run(monkeypatch, our_moves=("a", "b", "c", "d"),
                      their_moves=("x", "y"), col_action="x", values=vals,
                      opp_k=2, our_k=4)
    assert few_fix[0] == pytest.approx(many_fix[0]) == pytest.approx(-0.6), (
        "with the refutation visible, branch count stops buying value")


def test_a_terminal_answer_sinks_the_path_it_belongs_to(monkeypatch):
    """Terminal values and evaluated ones compete inside the SAME min --
    a line that loses on the spot cannot be hidden by a rosy sibling."""
    values = {(("a", "x"),): 0.9, (("b", "x"),): 0.1, (("b", "y"),): 0.1}
    out, stats = run(
        monkeypatch, our_moves=("a", "b"), their_moves=("x", "y"),
        col_action="x", values=values, opp_k=2,
        terminal=(("a", "y"),))       # our reply `a` gets us wiped
    assert out[0] == pytest.approx(0.1), "max(min(0.9,-1.0), min(0.1,0.1))"
    assert stats["depth2/leaves_deepened"] == 1.0


def test_a_switch_column_produces_no_grandchildren_until_opp_k_opens_it(monkeypatch):
    """A hole `opp_k=1` cannot see. The opponent already switched during the
    root ply, so repeating "switch 3" at ply 2 raises and the leaf is never
    deepened at all -- silently, because the raise lands in a `continue`."""
    def g(st, a, b):
        if b.startswith("switch"):
            raise ValueError("illegal: that pokemon is already active")
        return [FakeBranch((a, b))]
    monkeypatch.setattr(M, "generate_instructions", g)
    embed, shadow, critic = critic_from({(("a", "x"),): 0.4})
    monkeypatch.setattr(M, "embed_battle", embed)
    monkeypatch.setattr(M, "shadow_battle", shadow)

    def go(opp_k):
        st = FakeState((), ("a",), ("x", "y"))
        return M._look_further(
            np.array([0.05]), [0], [st], [["switch 3"]], [(0, 0, 0, 1.0)], 5,
            [None], critic, None,
            {"our_k": 3, "cap": 6000, "plies": 1, "opp_k": opp_k})

    out1, s1 = go(1)
    assert s1["depth2/grandchildren"] == 0.0
    assert s1["depth2/leaves_unexpanded"] == 1.0
    assert out1[0] == pytest.approx(0.05), (
        "an UNEXPANDED leaf keeps the value it already has -- it used to be "
        "re-embedded at a shifted turn and re-scored, so turning depth on "
        "moved the value of leaves it never looked past")
    out2, s2 = go(2)
    assert s2["depth2/grandchildren"] == 1.0
    assert out2[0] == pytest.approx(0.4)


# ------------------------------------------------------- the candidate list
def test_leaf_opp_moves_puts_the_column_action_first_and_dedupes():
    st = FakeState((), ("a",), ("x", "y", "z"))
    assert M._leaf_opp_moves(st, "x", 1) == ["x"], (
        "opp_k=1 must be EXACTLY the pin, or the default silently changes")
    assert M._leaf_opp_moves(st, "x", 3) == ["x", "y", "z"], (
        "the column action leads and is never duplicated")
    assert M._leaf_opp_moves(st, "q", 3) == ["q", "x", "y"], (
        "a column action the active mon cannot repeat still leads the list")
    assert len(M._leaf_opp_moves(st, "x", 99)) == 3, "bounded by legal moves"


def test_leaf_opp_moves_skips_spent_and_disabled_moves():
    st = FakeState((), ("a",), ("x", "y", "z"))
    st.side_two.pokemon[0].moves[1].pp = 0
    st.side_two.pokemon[0].moves[2].disabled = True
    assert M._leaf_opp_moves(st, "q", 4) == ["q", "x"]
    st.side_two.pokemon[0].moves[0].pp = 0
    assert M._leaf_opp_moves(st, "q", 4) == ["q"], (
        "a column action is offered even when nothing else is legal")


def test_leaf_opp_moves_unwraps_a_pyo3_string_active_index():
    """Same landmine as `_leaf_our_moves`: a bare except around this once cost
    a whole D2 arm -- 1572 decisions, zero grandchildren, a printed win rate."""
    st = FakeState((), ("a",), ("x",))
    st.side_two.pokemon = [FakeMon(100, ("x",)), FakeMon(100, ("w", "v"))]
    st.side_two.active_index = "PokemonIndex.P1"
    assert M._leaf_opp_moves(st, "q", 3) == ["q", "w", "v"]


def test_no_counter_is_ever_nan(monkeypatch):
    """`np.mean([])` is NaN and a readout prints NaN as a number. The
    all-unexpanded case is the one that produces an empty reduction."""
    def g(st, a, b):
        raise ValueError("nothing is legal here")
    monkeypatch.setattr(M, "generate_instructions", g)
    embed, shadow, critic = critic_from({})
    monkeypatch.setattr(M, "embed_battle", embed)
    monkeypatch.setattr(M, "shadow_battle", shadow)
    st = FakeState((), ("a",), ("x",))
    out, stats = M._look_further(
        np.array([0.42]), [0], [st], [["x"]], [(0, 0, 0, 1.0)], 5, [None],
        critic, None, {"our_k": 3, "cap": 6000, "plies": 1, "opp_k": 2})
    assert out[0] == pytest.approx(0.42)
    assert stats, "an unfired vehicle still reports, or it cannot be audited"
    bad = {k: v for k, v in stats.items() if not np.isfinite(v)}
    assert not bad, bad


def test_the_opp_k_dial_reaches_disk_before_it_gets_an_arm():
    """The standing rule after 2026-09-11's VOID probe and 2026-09-17's
    unreported heuristic: a dial gets a counter that reaches disk BEFORE it
    gets an arm. `opp_k` is a dial. Three places have to agree -- the solver
    emits, the agent accumulates, the h2h report writes -- and this reads all
    three out of the source rather than trusting that they do.
    """
    from pathlib import Path

    root = Path(__file__).parent.parent
    solver = (root / "rl/search/matrix.py").read_text()
    agent = (root / "rl/search/agent.py").read_text()
    report = (root / "scripts/ch3_fp_h2h.py").read_text()

    for key in ("depth2/opp_replies_mean", "depth2/minimax_drop",
                "depth2/leaves_unexpanded"):
        assert key in solver, f"{key} is never emitted by the solver"
    for key in ("depth2/opp_replies_sum", "depth2/drop_sum",
                "depth2/leaves_unexpanded"):
        assert key in agent, f"{key} is never accumulated across decisions"
    for key in ("depth2/opp_replies_mean", "depth2/minimax_drop",
                "depth2/leaves_unexpanded_total"):
        assert key in report, f"{key} never reaches the arm's JSON"


# ------------------------------------- end to end, through the REAL engine
def test_opp_k_really_fires_against_poke_engine_not_just_against_a_fake():
    """Every test above monkeypatches `generate_instructions`, which proves the
    ARITHMETIC and nothing about whether the real engine accepts the move ids
    `_leaf_opp_moves` hands it.

    That is the whole VOID class: on 2026-09-11 a depth-2 probe ran 1572
    decisions, produced ZERO grandchildren because a TypeError landed in a bare
    `except`, and printed a win rate anyway. This runs the real solver on the
    real engine and requires the counters to say the opponent actually replied.
    """
    from rl.search.matrix import DOSES, decision_rng, solve_decision
    from tests.test_ch3_matrix import (
        _TYPE_CHART, _mask, _two_mon_battle, _uniform_q, _zero_critic)

    b = _two_mon_battle()
    d2 = {"our_k": 3, "cap": 6000, "plies": 1}

    def run(opp_k):
        return solve_decision(
            b, _mask(switches=[1]), _uniform_q(), np.full(10, 0.1),
            DOSES["S"], decision_rng(62, 0, b.turn, 0), _zero_critic,
            _TYPE_CHART, depth2=dict(d2, opp_k=opp_k))[1]

    one, two = run(1), run(2)
    assert one["depth2/grandchildren"] > 0, "the extra ply never ran at all"
    assert one["depth2/opp_replies_mean"] == pytest.approx(1.0)
    assert two["depth2/opp_replies_mean"] > 1.2, (
        "the engine rejected every extra opponent reply, so opp_k=2 is opp_k=1 "
        "with a bigger number in the config")
    assert two["depth2/grandchildren"] > one["depth2/grandchildren"], (
        "more opponent replies must mean more grandchildren")
    # Paths can only GROW, and the reason is the third hole opp_k closes: a
    # reply whose only opponent answer was illegal (a SWITCH column repeated at
    # ply 2) produced nothing at all and vanished from the backup entirely.
    # Measured here on the real engine: 252 paths at opp_k=1, 297 at opp_k=2.
    assert two["depth2/paths"] >= one["depth2/paths"]
    assert two["depth2/leaves_unexpanded"] <= one["depth2/leaves_unexpanded"], (
        "giving the opponent more answers can only ever deepen more leaves")

"""IDEAS 4.11 -- outcome-decomposition targets for the critic (R6 trio A), the
DATA PATH. KataGo's rationale in our currency: decompose the +-1 outcome into
finer terminal quantities the value stack must also predict, so the critic's
representation learns HOW a game ends rather than only WHETHER it was won.
RESULTS 27.1 says ~93% of the critic's gap is RANKING; these targets carry far
less of RESULTS 27's 64% irreducible noise than the outcome does.

THREE TARGETS per episode, each in [-1, 1], broadcast to every row (like the
return): [0] our survivors / 6, [1] their survivors / 6, [2] HP margin / 6
(sum of our HP fractions minus the sum of theirs).

DEFINITION, stated exactly because it is an approximation. The episode's rows
are the learner's DECISIONS; no terminal observation is stored. So the
quantities are read at the LAST DECISION and combined with the known outcome:
  win  -> survivors_own = our live count then,  survivors_opp = 0,
          margin = +our HP sum then;
  loss -> survivors_own = 0, survivors_opp = their live count then,
          margin = -their HP sum then;
  tie  -> both live counts then, margin = the difference then.
What that misses is the FINAL TURN: a winner that lost a mon to Explosion or
took a hit before the KO is credited one mon / one hit too many, and a loser
that landed a hit before fainting is charged one hit too many. Small, one-sided
per side, and consistent -- and strictly more informative than +-1. An exact
version needs the Rust episode struct to carry the terminal snapshot.

Reads the gen-1 layout from rl/envs/showdown (the flags the process runs
under): own mon block i at GLOBAL_DIM + i*MON_DIM with hp at +0; the global
block carries fainted counts / 6 at [1] (ours) and [2] (theirs); opponent
blocks sit after our moves, each [revealed flag || mon block], and an
UNREVEALED mon is alive at full HP (randbats: never entered, never hit).
"""
from __future__ import annotations

import numpy as np

TARGET_NAMES = ("survivors_own", "survivors_opp", "hp_margin")


def outcome_targets(obs_rows: np.ndarray, outcome: float) -> np.ndarray:
    """(n, OBS_DIM) learner rows + the episode outcome -> (n, 3) float32."""
    from rl.envs import showdown as sd

    rows = np.asarray(obs_rows)
    assert rows.ndim == 2 and rows.shape[0] >= 1, rows.shape
    assert rows.shape[1] == sd.OBS_DIM, (rows.shape, sd.OBS_DIM)
    last = rows[-1].astype(np.float64)
    own_live = 6.0 - float(round(last[1] * 6.0))
    opp_live = 6.0 - float(round(last[2] * 6.0))
    own_hp = float(sum(last[sd.GLOBAL_DIM + i * sd.MON_DIM] for i in range(6)))
    opp_off = sd.GLOBAL_DIM + 6 * sd.MON_DIM + sd.ACTIVE_DIM + 4 * sd.MOVE_DIM
    width = sd.MON_DIM + 1
    revealed = [bool(last[opp_off + j * width] > 0.5) for j in range(6)]
    opp_hp = float(sum(last[opp_off + j * width + 1] for j in range(6) if revealed[j]))
    opp_hp += float(6 - sum(revealed))  # unrevealed: alive at full HP
    o = float(outcome)
    if o > 0:
        surv_own, surv_opp, margin = own_live, 0.0, own_hp
    elif o < 0:
        surv_own, surv_opp, margin = 0.0, opp_live, -opp_hp
    else:
        surv_own, surv_opp, margin = own_live, opp_live, own_hp - opp_hp
    row = np.array([surv_own / 6.0, surv_opp / 6.0, margin / 6.0], dtype=np.float32)
    return np.tile(row, (rows.shape[0], 1))

"""`ShowdownEngine-v0` — one gen-1 battle as a `gym.Env`, no server (plan §8.3).

Exists so `evaluate()` and the harness tests can run against the in-engine
scripted opponents without a Showdown server. It is a THIN wrapper over
`BatchEnv(k=1)`: same engine, same encoder, same mask, same episode semantics
as the collector, so an env-path bug and a collector-path bug are the same bug.

NOT AN EVAL INSTRUMENT. The locked protocol is 3000 battles/seed x 3 seeds vs
`SimpleHeuristicsPlayer` ON THE SERVER, and SH is deliberately not ported
(plan §8.2). An `eval/win_rate` measured here is descriptive only and is never
the locked number — say so wherever one is quoted.

The env follows the repo's harness contract: `info["action_mask"]` at reset and
after every step, a finite `-1e8` sentinel nowhere near here (masking is the
algorithm's job), and terminal outcome rewards only (win 1, loss -1, tie 0).
"""

from __future__ import annotations

import pathlib

import gymnasium as gym
import numpy as np

from rl.envs.engine_bank import read_bank

# The gen-1 observation width, read from the encoder module so a flag mismatch
# fails here rather than at the first forward.
from rl.envs.showdown import OBS_DIM

N_ACTIONS = 10

# The in-engine bots. `random` and `max_power` keep poke-env's names on purpose
# — gate D-1 plays the engine's against the server's under the same name, and
# "same rule, two simulators" is the comparison. `most_damage_typed_engine`
# does NOT: the bare name already means the SERVER anchor project-wide
# (`rl/envs/showdown.py::OPPONENT_PLAYERS`), whose h2h at 500 battles is a
# reported anchor-battery row, and there is no engine-vs-server comparison for
# it to earn the shared name with.
SCRIPTED = ("random", "max_power", "most_damage_typed_engine")

# Names refused BY NAME rather than as "unknown", each with where the real one
# lives. A silent substitution here would put an in-engine number in a row that
# means something else.
_REFUSED = {
    "heuristics": (
        "SimpleHeuristicsPlayer is the VERDICT DENOMINATOR for every banked "
        "number in this project and is deliberately not ported — a port that "
        "differed anywhere would redefine it silently. It stays on the server "
        "(plan §8.2); eval does not run here."
    ),
    "simple_heuristics": "see 'heuristics'",
    "most_damage_typed": (
        "`most_damage_typed` names the SERVER anchor "
        "(rl/envs/most_damage_typed.py), whose h2h at 500 battles is a reported "
        "anchor-battery row. The in-engine port is 'most_damage_typed_engine', "
        "and its numbers are DESCRIPTIVE ONLY — never a battery leg, never a "
        "verdict input, and not comparable to anything until gate D-1 passes."
    ),
}


class EngineEnv(gym.Env):
    """One battle at a time against an in-engine scripted opponent.

    `opponent` is one of `SCRIPTED`. `SimpleHeuristicsPlayer` is not available
    and never will be: it reads poke-env `Battle` objects, so an in-engine
    version would be a different bot with the same name.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        team_bank: str | pathlib.Path,
        opponent: str = "max_power",
        seed: int = 0,
        learner_seat: str = "p1",
        render_mode: str | None = None,
    ):
        import pkmn_gen1

        from rl.envs.engine_tables import build_tables

        if opponent in _REFUSED:
            why = _REFUSED[opponent]
            if why.startswith("see "):
                why = _REFUSED[why.removeprefix("see ").strip("'")]
            raise ValueError(f"engine opponent {opponent!r} is refused: {why}")
        if opponent not in SCRIPTED:
            raise ValueError(
                f"engine opponent {opponent!r} is not one of {list(SCRIPTED)}"
            )
        self._make = pkmn_gen1.BatchEnv
        self._tables, _fp = build_tables()
        self._header, self._payload = read_bank(pathlib.Path(team_bank))
        self._opponent = opponent
        self._seat = learner_seat
        self._seed = int(seed)
        self._env = None
        # `make_env` passes render_mode to every env; there is nothing to
        # render here, so it is accepted and ignored (metadata declares none).
        self.render_mode = render_mode
        self.observation_space = gym.spaces.Box(-1.0, 4.0, (OBS_DIM,), np.float32)
        self.action_space = gym.spaces.Discrete(N_ACTIONS)

    # ---- gym ---------------------------------------------------------------

    def reset(self, *, seed: int | None = None, options=None):
        # A new lane per reset, one battle wide. The battle counter advances
        # across resets so consecutive episodes are DIFFERENT battles — a lane
        # rebuilt at counter 0 every reset would evaluate on one team pair.
        if seed is not None:
            self._seed = int(seed)
            self._env = None
        counter = 0 if self._env is None else self._env.battle_counter
        self._env = self._make(
            1, self._seed, self._tables, self._payload, self._seat, counter
        )
        return self._observe()

    def step(self, action):
        idx, obs, mask, _member = self._env.pending("learner")
        if not len(idx):
            raise RuntimeError("step() with no decision owed; reset() first")
        if not mask[0][int(action)]:
            raise ValueError(f"action {int(action)} is outside the mask {mask[0]}")
        o_idx, o_actions = self._env.scripted_actions("opponent", self._opponent)
        self._env.step(
            [0], [int(action)], [0.0], 0, o_idx.tolist(), o_actions.tolist()
        )
        finished = self._env.drain_finished()
        if finished:
            ep = finished[0]
            reward = float(ep["reward"])
            info = {
                "action_mask": np.ones(N_ACTIONS, dtype=bool),
                "outcome": reward,
                "turns": int(ep["turns"]),
                "battle_seed": int(ep["seed"]),
            }
            # The terminal observation is the last one the learner acted on:
            # nothing follows it, and the algorithms bootstrap terminals to 0.
            return ep["obs"][-1], reward, True, False, info
        next_obs, next_info = self._observe()
        return next_obs, 0.0, False, False, next_info

    def close(self):
        self._env = None

    # ---- internals ---------------------------------------------------------

    def _observe(self):
        # A slot always owes the learner a decision at turn 1; mid-battle the
        # learner can owe nothing while the opponent replaces a fainted mon, so
        # the opponent's forced turns are pumped here rather than returned as
        # learner rows with a placeholder action (the sync path's wait-state
        # absorption, §7.6 — this is the one place the env differs from the
        # collector, which has other slots to work on instead of waiting).
        for _ in range(2000):
            idx, obs, mask, _m = self._env.pending("learner")
            if len(idx):
                return obs[0], {"action_mask": mask[0]}
            o_idx, o_actions = self._env.scripted_actions("opponent", self._opponent)
            if not len(o_idx):
                raise RuntimeError("neither seat owes a decision")
            self._env.step([], [], [], 0, o_idx.tolist(), o_actions.tolist())
            if self._env.drain_finished():
                raise RuntimeError(
                    "the battle ended on an opponent-only turn; the learner has "
                    "no row to attribute the outcome to"
                )
        raise RuntimeError("2000 opponent-only turns without a learner decision")

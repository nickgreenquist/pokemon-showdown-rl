"""Phase-5 mutation spec: the ShowdownEnv.step correctness guards.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/phase5_env.py

The three-review design pass (2026-07-29) found poke-env's silent-discard
path: PokeEnv.step sends agent1's action only when agent1_to_move, so a
wait state returned as a learner row becomes a phantom (s, a) pair —
measured at 6.4% of raw steps vs max_power — and decided-but-truncated
finishes would stack a gamma*V bootstrap on top of the terminal reward.
Each mutation here re-opens one of those holes; all four real ones are
caught OFFLINE by the stub tests, so this battery does not need the live
server (the live tests skip cleanly when :8000 is down).

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_showdown_env.py"]

ENV = "rl/envs/showdown.py"

MUTATIONS = [
    # ------------------------------------------------------- wait-state pump
    ("pump-loop-dropped", ENV,
     """        while not (terminated or truncated) and not poke.agent1_to_move:
            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))
            total_reward += float(reward)
            self.waits_absorbed += 1""",
     ""),
    ("pump-drops-reward", ENV,
     """            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))
            total_reward += float(reward)
            self.waits_absorbed += 1""",
     """            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))
            self.waits_absorbed += 1"""),
    # ------------------------------------------------- silent-discard guard
    ("discard-assert-dropped", ENV,
     '        assert poke.agent1_to_move, "action would be silently discarded by poke-env"',
     "        pass"),
    # ------------------------------------------------------ term/trunc remap
    ("remap-dropped", ENV,
     "            terminated, truncated = True, False",
     "            pass"),
    # ---------------------------------------------- mixture-opponent lever
    # Re-sampling every turn would make battles mid-game chimeras; pinning
    # the sample to the first name would silently collapse the mixture to
    # its alphabetically-first component.
    ("mix-resamples-every-turn", ENV,
     """        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._current = self._players[
                self._rng.choices(self._names, weights=self._weights)[0]
            ]""",
     """        self._current = self._players[
            self._rng.choices(self._names, weights=self._weights)[0]
        ]"""),
    ("mix-collapses-to-first", ENV,
     """            self._current = self._players[
                self._rng.choices(self._names, weights=self._weights)[0]
            ]""",
     """            self._current = self._players[self._names[0]]"""),
    ("mix-weights-unnormalized", ENV,
     "        self._weights = [weights[n] / total for n in self._names]",
     "        self._weights = [1.0 for n in self._names]"),
    # ------------------------------------------------- equivalence CONTROL
    # The pump's dummy action is discarded by poke-env (agent1_to_move is
    # False), so its value is arbitrary. If this is caught, a test is
    # pinning the dummy's value instead of the pump's behavior.
    ("C1-pump-dummy-action-is-one", ENV,
     "            obs, reward, terminated, truncated, info = self._env.step(np.int64(0))",
     "            obs, reward, terminated, truncated, info = self._env.step(np.int64(1))"),
]

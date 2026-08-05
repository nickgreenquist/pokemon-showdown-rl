"""Chunk-4 mutation spec: the PFSP and fixed-mix probe levers.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk4_levers.py

The levers change what the pool trains against, so a silent defect here
produces a wrong CAMPAIGN, not a crash: an inverted f_hard trains hardest
against the members already beaten, a flipped report sign does the same
from the other end, a draw consumed at fixed_mix 0 silently changes every
seeded pre-lever run, and a select() that refreshes weights continuously
breaks the fixed-distribution-within-a-rollout invariant PPO's importance
ratios rest on.

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_selfplay_pool.py"]

POOL = "rl/selfplay/pool.py"
ENV = "rl/envs/connect4.py"

MUTATIONS = [
    ("pfsp-weight-inverted", POOL,
     "        weights = (1.0 - x) ** self.pfsp_power",
     "        weights = x ** self.pfsp_power"),
    ("report-score-inverted", POOL,
     "                stat[0] += (outcome + 1) / 2  # learner score: win 1, draw 0.5",
     "                stat[0] += (1 - outcome) / 2  # learner score: win 1, draw 0.5"),
    ("unplayed-prior-drops-to-zero", POOL,
     "            stat[0] / stat[1] if stat[1] else 0.5 for stat in self.stats[:-1]",
     "            stat[0] / stat[1] if stat[1] else 0.0 for stat in self.stats[:-1]"),
    ("mix-consumes-a-draw-at-zero", POOL,
     "        if self.fixed_mix > 0.0 and rng.random() < self.fixed_mix:",
     "        if rng.random() < self.fixed_mix:"),
    ("select-refreshes-continuously", POOL,
     """        if self.pfsp_power > 0.0:
            return self.members[int(rng.choice(len(self.members) - 1, p=self._weights))]""",
     """        if self.pfsp_power > 0.0:
            self.refresh()
            return self.members[int(rng.choice(len(self.members) - 1, p=self._weights))]"""),
    ("env-report-sign-flipped", ENV,
     "            self.opponent_source.report(self._opponent, outcome)",
     "            self.opponent_source.report(self._opponent, -outcome)"),
    ("env-report-dropped", ENV,
     "            self.opponent_source.report(self._opponent, outcome)",
     "            _ = (self._opponent, outcome)"),
    # ------------------------------------------------ equivalence CONTROLS
    ("C1-report-score-by-multiplication", POOL,
     "                stat[0] += (outcome + 1) / 2  # learner score: win 1, draw 0.5",
     "                stat[0] += 0.5 * (outcome + 1)  # learner score: win 1, draw 0.5"),
    ("C2-uniform-fallback-via-ones", POOL,
     "        self._weights = weights / total if total > 0 else np.full(len(x), 1.0 / len(x))",
     "        self._weights = weights / total if total > 0 else np.ones(len(x)) / len(x)"),
]

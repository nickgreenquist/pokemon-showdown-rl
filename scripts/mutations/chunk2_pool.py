"""Chunk-2 mutation spec: SnapshotPool / AgentOpponent / train-loop wiring.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk2_pool.py

Result on 2026-07-27 (the chunk-2 landing, HEAD 6274410): 15/15 real
mutations caught, all 3 equivalence controls survived. Committed rather than
left in session scratch — chunk 1's spec died with its scratchpad, and
chunks 3-4 touch this code (AgentOpponent feeds the tournament), so the
battery must be re-runnable. If a control is ever reported caught, the
harness is measuring noise — see scripts/mutate.py's docstring.

`old` strings must match the current source exactly and uniquely; a refactor
that breaks one shows up as BAD-PATTERN, which is a prompt to update the
spec, not to delete the mutation.
"""

TESTS = ["tests/test_selfplay_pool.py", "tests/test_selfplay_harness.py"]

POOL = "rl/selfplay/pool.py"
TRAIN = "rl/train.py"

MUTATIONS = [
    # -------------------------------------------------------- AgentOpponent
    ("drop-deepcopy", POOL,
     "self.agent = copy.deepcopy(agent)",
     "self.agent = agent"),
    ("argmax-not-sample", POOL,
     "return int(torch.multinomial(probs, 1, generator=self.generator).item())",
     "return int(probs.argmax().item())"),
    ("global-stream-not-own-generator", POOL,
     "generator=self.generator",
     "generator=None"),
    # --------------------------------------------------------- SnapshotPool
    ("freeze-skipped-at-push", POOL,
     "        member.freeze()\n",
     "\n"),
    ("latest-prob-inverted", POOL,
     "if rng.random() < self.latest_prob:",
     "if rng.random() >= self.latest_prob:"),
    ("select-always-latest", POOL,
     "return self.members[int(rng.integers(len(self.members) - 1))]",
     "return self.members[-1]"),
    ("historical-draw-includes-latest", POOL,
     "rng.integers(len(self.members) - 1)",
     "rng.integers(len(self.members))"),
    ("evict-oldest", POOL,
     "del self.members[1 if self.pool_size > 1 else 0]",
     "del self.members[0]"),
    ("evict-newest", POOL,
     "del self.members[1 if self.pool_size > 1 else 0]",
     "del self.members[-1]"),
    ("naive-arm-keeps-its-random-init", POOL,
     "del self.members[1 if self.pool_size > 1 else 0]",
     "del self.members[1]"),
    ("no-capacity-cap", POOL,
     "if len(self.members) > self.pool_size:",
     "if False:"),
    # ------------------------------------------------------------- train.py
    ("no-preloop-push", TRAIN,
     "        pool.push(agent)\n        logger.log({\"selfplay/pool_size\": len(pool)}, 0)",
     "        logger.log({\"selfplay/pool_size\": len(pool)}, 0)"),
    ("push-every-update", TRAIN,
     "updates_done % push_every == 0",
     "True"),
    ("cadence-off-by-one", TRAIN,
     "updates_done % push_every == 0",
     "updates_done % push_every == 1"),
    ("scalar-guard-dropped", TRAIN,
     "        if not vectorized:\n            raise ValueError(\n                \"selfplay opponent 'self' needs a vectorized algorithm: \"",
     "        if False:\n            raise ValueError(\n                \"selfplay opponent 'self' needs a vectorized algorithm: \""),
    # ------------------------------------------------- equivalence CONTROLS
    ("C1-negative-index-spelled-out", POOL,
     "return self.members[-1]",
     "return self.members[len(self.members) - 1]"),
    ("C2-redundant-cadence-guard", TRAIN,
     "updates_done % push_every == 0",
     "push_every > 0 and updates_done % push_every == 0"),
    ("C3-flipped-comparison", POOL,
     "if rng.random() < self.latest_prob:",
     "if self.latest_prob > rng.random():"),
]

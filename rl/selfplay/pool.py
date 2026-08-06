"""Snapshot pool: the historical-opponent side of self-play (Phase 4 chunk 2).

Two objects. `AgentOpponent` wraps a frozen copy of a training agent behind
the `Opponent` protocol; `SnapshotPool` holds a population of them and IS an
`Opponent` itself, which is the whole wiring trick — `rl/train.py` passes the
pool through the same `env_kwargs` seam a name like "heuristic" travels, and
one pool object is shared by every sub-env because caller kwargs are never
deep-copied (see `rl/envs/make.py`).

Where the copy happens is the load-bearing decision: `agent.state_dict()`
ALIASES the live training tensors (probe-confirmed, PLAN.md), so a pool of
state_dicts would hold references into the learner and every "frozen"
opponent would silently track it — the Phase-3 log_alpha rebind failure
class. `AgentOpponent.__init__` therefore deep-copies the whole agent at
construction, where it cannot be forgotten by a call site. The deepcopy
carries the optimizer too (~2/3 of the ~1 MB per snapshot is dead optimizer
state) — accepted waste, per the locked spec.

Two distinct swap boundaries, enforced by WHERE things are called rather
than by state in here:

- which member plays is drawn per EPISODE — `select()` runs at env reset;
- new snapshots enter the pool only at a ROLLOUT boundary — `push()` is
  called from `rl/train.py` right after the `update()` that drained the
  buffer, so within a rollout the env is a *stochastic* env with a fixed
  opponent distribution, not a non-stationary one. That is what PPO's
  importance ratios actually require.

Retention on overflow is SPAN-PRESERVING THINNING (fixed 2026-08-06; the
ported rule deleted index 1 every time, which flushed a pre-seeded pool
within pool_size pushes and degenerated retention to anchor + recency
window — the recovered predecessor record measured exactly that). A plain
recency deque was the only pool-span design with a published ablation
against it (Bansal et al., ICLR 2018 — "training against the latest
opponent leads to worst performance"), so on overflow the pool evicts the
member whose push-time neighbors are closest together — the one whose
removal costs the least span coverage — never the step-0 anchor and never
the newest. Retained push ids stay ~uniform over [0, latest], so the
pool's span grows with training instead of trailing it. The exception is
`pool_size: 1` — the naive arm, a <=push-cadence-lagged copy of the
learner, which is what the self-play literature means by naive self-play —
where push must REPLACE, because keeping the oldest would pin the naive
arm to its random init forever.
"""

import copy

import numpy as np
import torch

from rl.common.masking import masked_logits
from rl.selfplay.opponents import HeuristicOpponent, Opponent, RandomOpponent


class AgentOpponent(Opponent):
    """A frozen agent snapshot playing as an env opponent.

    Samples from the policy rather than argmaxing: a deterministic opponent
    collapses an eval or tournament set to a couple of distinct games (the
    `eval/return_std > 0` failure), and stochastic play on both sides is the
    locked tournament protocol. The draw comes from this opponent's OWN
    `torch.Generator`, never the global torch stream — the learner's
    collection also samples from the global stream, so sharing it would let
    the number of learner steps between opponent moves change every seeded
    opponent decision, and a chunk-3 tournament matchup could never be
    replayed in isolation.

    `move()` runs its own forward instead of calling `agent.act()`: act()
    samples via `Categorical.sample()`, which only draws from the global
    stream.
    """

    def __init__(self, agent, seed: int = 0):
        self.agent = copy.deepcopy(agent)
        self.generator = torch.Generator().manual_seed(seed)

    def freeze(self) -> None:
        for net in (self.agent.actor, self.agent.critic):
            net.eval()
            for param in net.parameters():
                param.requires_grad_(False)

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.agent.device).unsqueeze(0)
        mask_t = torch.as_tensor(mask, dtype=torch.bool, device=self.agent.device)
        with torch.no_grad():
            probs = torch.softmax(masked_logits(self.agent.actor(obs_t), mask_t), dim=-1)
        return int(torch.multinomial(probs, 1, generator=self.generator).item())


class SnapshotPool(Opponent):
    """A population of `AgentOpponent` snapshots, itself an `Opponent`.

    `select()` is the 80/20 draw (OpenAI Five's split): `latest_prob` on the
    newest member, else uniform over the rest — the uniform historical draw
    is ours, not theirs (they weighted by quality scores over an unbounded
    pool). It draws from the RNG the env hands in, which is the env's own
    per-episode stream — the pinned draw order (flip, select, opponent
    moves) is unchanged, the select slot just consumes draws now.

    The two chunk-4 probe levers live here, inert at their defaults:
    `pfsp_power` turns the flat historical draw into AlphaStar's
    f_hard(x) = (1-x)^p over the learner's tracked win rate per member
    (fed by `report()`, snapshotted by `refresh()` at rollout boundaries),
    and `fixed_mix` routes that fraction of episodes to the random or
    heuristic anchor instead of the pool — the one lever aimed directly at
    the vs-random decline.

    The pool must be non-empty before the first env reset: `rl/train.py`
    pushes the step-0 snapshot before entering the loop, and `select()` on
    an empty pool raises rather than papering over a broken push order.
    """

    def __init__(self, pool_size: int, latest_prob: float,
                 pfsp_power: float = 0.0, fixed_mix: float = 0.0):
        if pool_size < 1:
            raise ValueError(f"pool_size must be >= 1, got {pool_size}")
        if not 0.0 <= latest_prob <= 1.0:
            raise ValueError(f"latest_prob must be a probability, got {latest_prob}")
        if pfsp_power < 0.0:
            raise ValueError(f"pfsp_power must be >= 0, got {pfsp_power}")
        if not 0.0 <= fixed_mix <= 1.0:
            raise ValueError(f"fixed_mix must be a probability, got {fixed_mix}")
        self.pool_size = pool_size
        self.latest_prob = latest_prob
        # The two chunk-4 probe levers, both inert at their defaults — at
        # pfsp_power 0 and fixed_mix 0 every rng draw and every selection
        # is byte-identical to the pre-lever pool (the one-key-diff
        # discipline extends to the seeded stream: the guards below
        # short-circuit before consuming a draw).
        self.pfsp_power = float(pfsp_power)
        self.fixed_mix = float(fixed_mix)
        self.members: list[AgentOpponent] = []
        # Per-member [learner score sum, games] fed by report(); x = the
        # learner's win rate vs the member, AlphaStar's f_hard(x) = (1-x)^p.
        self.stats: list[list[float]] = []
        self._weights: "np.ndarray | None" = None  # set by refresh()
        # The fixed-mix pool: the two cheap anchors, per the diagnostics
        # entry ("a few percent of fixed-bot games keeps external coverage
        # alive by construction"). Rule-based, so freeze() is a no-op.
        self._fixed = (RandomOpponent(), HeuristicOpponent())
        self.pushes = 0  # lifetime count; also seeds each member's generator
        self.push_ids: list[int] = []  # per-member push counter, for retention

    def __len__(self) -> int:
        return len(self.members)

    def push(self, agent) -> None:
        """Snapshot `agent` into the pool. The install point, so freezing
        happens here — a snapshot cannot enter the pool trainable."""
        member = AgentOpponent(agent, seed=self.pushes)
        member.freeze()
        self.members.append(member)
        self.stats.append([0.0, 0])
        self.push_ids.append(self.pushes)
        self.pushes += 1
        if len(self.members) > self.pool_size:
            evict = self._evict_index()
            del self.members[evict]
            del self.stats[evict]
            del self.push_ids[evict]
        # Membership only ever changes here, so weights recomputed here can
        # never be stale against the member list.
        self.refresh()

    def _evict_index(self) -> int:
        """Span-preserving thinning (module docstring). Never the step-0
        anchor, never the newest; among the rest, evict the member whose
        push-time neighbors are closest together — ties go to the oldest.
        At pool_size 1 (the naive arm) the sole member is replaced, because
        protecting the oldest would pin that arm to its random init."""
        if self.pool_size == 1:
            return 0
        ids = self.push_ids
        return min(range(1, len(ids) - 1), key=lambda i: (ids[i + 1] - ids[i - 1], i))

    def report(self, played: Opponent, outcome: int) -> None:
        """Accumulate the learner's result vs the member that played.
        Identity match on purpose: a fixed-mix opponent or a member evicted
        while its last episode was in flight is silently not a member, and
        neither should move any weight."""
        for member, stat in zip(self.members, self.stats):
            if member is played:
                stat[0] += (outcome + 1) / 2  # learner score: win 1, draw 0.5
                stat[1] += 1
                return

    def refresh(self) -> None:
        """Snapshot the PFSP weights over the historical members from the
        counts accumulated so far. Called from the training loop at ROLLOUT
        boundaries (and from push), never per episode: within a rollout the
        opponent distribution must stay fixed — the same invariant that
        pins the push cadence — so counts accumulate live but the draw only
        sees them from the next rollout on. An unplayed member scores the
        0.5 prior; if every historical member is fully beaten the weights
        all collapse to 0 and the draw falls back to uniform."""
        if len(self.members) <= 1:
            self._weights = None
            return
        x = np.array([
            stat[0] / stat[1] if stat[1] else 0.5 for stat in self.stats[:-1]
        ])
        weights = (1.0 - x) ** self.pfsp_power
        total = weights.sum()
        self._weights = weights / total if total > 0 else np.full(len(x), 1.0 / len(x))

    def select(self, rng: np.random.Generator) -> Opponent:
        if not self.members:
            raise IndexError("empty pool: push a snapshot before the first reset")
        if self.fixed_mix > 0.0 and rng.random() < self.fixed_mix:
            return self._fixed[int(rng.integers(2))]
        if len(self.members) == 1:
            return self.members[0]
        if rng.random() < self.latest_prob:
            return self.members[-1]
        if self.pfsp_power > 0.0:
            return self.members[int(rng.choice(len(self.members) - 1, p=self._weights))]
        return self.members[int(rng.integers(len(self.members) - 1))]

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        raise TypeError("the pool never plays; select() returns the member that does")

    def freeze(self) -> None:
        """No-op on purpose: members are frozen one by one at push(), which
        is their install point. The env still calls this when the pool is
        installed — the contract is that every installer calls freeze()."""
